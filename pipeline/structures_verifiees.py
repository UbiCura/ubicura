"""Liste vérifiée des structures de soins (décision de Lucas du 13 octobre 2026).

FINESS et le ROR réunis automatiquement donnent une première liste. Elle contient des erreurs que seules les sources
des établissements permettent de corriger, par exemple des CMP déclarés à l'adresse de l'hôpital, un hôpital de jour
décrit comme un CMP, ou une structure fermée encore inscrite. Pour chaque établissement gestionnaire vérifié, la liste
de ses structures est reprise une à une sur des sources fiables (site de l'établissement, liste des sites de sa
certification par la HAS, documents de l'ARS ou des collectivités, données ouvertes publiques, Santé.fr consulté sans
être repris), avec l'adresse, la source et la date de chaque structure. Cette liste remplace alors, pour cet
établissement et ces types, la réunion automatique.

Deux fichiers versionnés, dans contenus/.
- etablissements_verifies.csv, un établissement par ligne : ej (numéro FINESS de l'entité juridique), etablissement,
  departement, types (identifiants de config.LIEUX_TYPES séparés par des virgules, suivis de « :adultes » ou
  « :enfants » quand la source ne couvre qu'un public), date, sources, empreinte (empreinte
  des inscriptions de FINESS et du ROR au moment de la vérification), remarque.
- structures_verifiees.csv, une structure par ligne : ej, etablissement, type, public (adultes, enfants, ou adultes et
  enfants pour un CMP), nom, adresse, commune (code INSEE), source, adresse_source, date, remarque.

À chaque mise à jour, un établissement est signalé à revérifier quand ses inscriptions dans FINESS ou le ROR ont changé
depuis la vérification (empreinte différente) ou quand la vérification a plus d'un an. Rien n'est jamais déduit en
silence, chaque inscription des bases qui n'est pas retenue est consignée avec la raison.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re

import pandas as pd

from . import config
from .util import JOURNAL

FICHIER_ETAB = config.RACINE / "contenus" / "etablissements_verifies.csv"
FICHIER = config.RACINE / "contenus" / "structures_verifiees.csv"
BASES = config.INTER / "structures_avant_verification.parquet"   # inscriptions des bases, jamais publiées
DUREE_JOURS = 365
COLS_ETAB = ["ej", "etablissement", "departement", "types", "date", "sources", "empreinte", "remarque"]
COLS = ["ej", "etablissement", "type", "public", "nom", "adresse", "commune", "statut", "finess", "source",
        "adresse_source", "date", "remarque"]
# statut de chaque structure, du plus sûr au moins sûr
STATUTS = {"etablissement": "confirmée par l'établissement",
           "source_publique": "confirmée par une autre source publique (HAS, ARS, collectivité, Acceslibre)",
           "bases": "inscrite dans FINESS ou le ROR, non confirmée par les sources de l'établissement"}
ENFANTS_DE = {t[4]["parent"]: [] for t in config.LIEUX_TYPES if t[4].get("parent")}
for _t in config.LIEUX_TYPES:
    if _t[4].get("parent"):
        ENFANTS_DE[_t[4]["parent"]].append(_t[0])


def charger() -> tuple[pd.DataFrame, pd.DataFrame]:
    e = pd.read_csv(FICHIER_ETAB, sep=";", dtype=str, encoding="utf-8").fillna("") if FICHIER_ETAB.exists() else \
        pd.DataFrame(columns=COLS_ETAB)
    s = pd.read_csv(FICHIER, sep=";", dtype=str, encoding="utf-8").fillna("") if FICHIER.exists() else \
        pd.DataFrame(columns=COLS)
    return e, s


def types_de(e_types: str) -> list[str]:
    """Types vérifiés d'un établissement, avec les CMP pour adultes et pour enfants quand le CMP l'est."""
    ts = [t.strip().split(":")[0] for t in e_types.split(",") if t.strip()]
    return ts + [c for t in ts for c in ENFANTS_DE.get(t, [])]


def perimetres(e_types: str) -> dict[str, str]:
    """Public seul vérifié pour un type (« lieu_cmp:adultes » quand l'établissement ne publie que ses CMP pour
    adultes, constat du CHU de Montpellier le 14 octobre 2026). Les inscriptions de l'autre public restent alors telles
    que les bases les donnent."""
    out = {}
    for t in e_types.split(","):
        t, _, p = t.strip().partition(":")
        if p:
            out[t] = p.strip()
    return out


def empreinte(lieux: pd.DataFrame, ej: str, types: list[str], dep: str = "") -> str:
    """Empreinte des inscriptions de FINESS et du ROR d'un établissement pour ces types (clés des structures réunies,
    numéros FINESS), qui change dès qu'une base ajoute, retire ou déplace une inscription."""
    g = lieux[(lieux["ej"] == ej) & lieux["type"].isin(types)]
    if dep and "dep" in g:
        g = g[g["dep"] == dep]
    cles = sorted(f"{t}|{l}|{f}" for t, l, f in zip(g["type"], g["lieu"], g["finess"].fillna("")))
    return hashlib.sha1("\n".join(cles).encode("utf-8")).hexdigest()[:12]


def _mots(s: str) -> set[str]:
    from .lieux import _distinctif, _simple
    return set(_distinctif(_simple(s)).split()) - {"cmp", "cattp", "hdj", "hj", "centre", "hopital", "jour"}


def _rue(s: str) -> str:
    from .lieux import _simple
    return re.sub(r"^\d+\s*(?:bis|ter|b|t)?\s+", "", _simple(s or ""))


def _nums_ligne(r) -> set[str]:
    """Numéros FINESS d'une inscription (le sien, celui rapproché, ceux réunis à elle)."""
    out = set()
    for c in ("finess", "finess_rapproche", "finess_absorbes"):
        v = r.get(c)
        if isinstance(v, str) and v:
            out |= set(v.split(","))
    return out


def placer(n: pd.DataFrame, centres: dict | None, hors_ligne: bool) -> pd.DataFrame:
    """Coordonnées des structures vérifiées, par leur adresse géocodée (service de l'IGN, avec cache), sinon le centre
    de leur commune."""
    from .lieux import _geocoder
    n = n.copy()
    n["lat"], n["lon"], n["precision"] = float("nan"), float("nan"), None
    a = n[["adresse", "commune"]].rename(columns={"adresse": "voie"})
    cache = _geocoder(a, hors_ligne)
    g = cache.dropna(subset=["lat"]).drop_duplicates(["voie", "commune"]).set_index(["voie", "commune"])
    for i, (v, c) in enumerate(zip(n["adresse"], n["commune"])):
        if (v, c) in g.index:
            n.iloc[i, n.columns.get_loc("lat")] = float(g.at[(v, c), "lat"])
            n.iloc[i, n.columns.get_loc("lon")] = float(g.at[(v, c), "lon"])
            n.iloc[i, n.columns.get_loc("precision")] = g.at[(v, c), "niveau"]
        elif "lat_base" in n and pd.notna(n["lat_base"].iloc[i]):
            n.iloc[i, n.columns.get_loc("lat")] = float(n["lat_base"].iloc[i])
            n.iloc[i, n.columns.get_loc("lon")] = float(n["lon_base"].iloc[i])
            n.iloc[i, n.columns.get_loc("precision")] = n["precision_base"].iloc[i]
        elif centres and centres.get(c):
            n.iloc[i, n.columns.get_loc("lon")] = centres[c][0]
            n.iloc[i, n.columns.get_loc("lat")] = centres[c][1]
            n.iloc[i, n.columns.get_loc("precision")] = "commune"
    return n.drop(columns=[c for c in ("lat_base", "lon_base", "precision_base") if c in n])


def appliquer(lieux: pd.DataFrame, ref, centres: dict | None = None,
              hors_ligne: bool = True, garder: set | None = None) -> tuple[pd.DataFrame, dict]:
    """Remplace, pour chaque établissement vérifié, ses structures des types vérifiés par la liste vérifiée. Les
    numéros FINESS des inscriptions rapprochées restent attachés (finess_absorbes), celles qui ne correspondent à
    aucune structure vérifiée sont consignées. Une inscription non citée par la source mais confirmée par une autre
    liste officielle (index dans garder, certification HAS ou Sirene) est gardée en attendant une vérification à la
    main (décision de Lucas du 14 octobre 2026). Renvoie les structures et un compte rendu."""
    e, s = charger()
    garder = garder or set()
    rendu = {"etablissements": e, "a_reverifier": [], "non_retenues": [], "gardees": [], "ajoutees": 0}
    gardes = []
    if e.empty:
        return lieux, rendu
    x = lieux.copy()
    x["verifiee"] = False
    aujourd = dt.date.today()
    nom_com = ref.communes.set_index("code")["nom"]
    nouvelles, retirer = [], []
    for _, et in e.iterrows():
        ej, types = et["ej"], types_de(et["types"])
        parents = [t for t in types if t not in sum(ENFANTS_DE.values(), [])]
        dep = et["departement"]
        emp = empreinte(x, ej, parents, dep)
        age = (aujourd - dt.date.fromisoformat(et["date"])).days if et["date"] else 9999
        if et["empreinte"] and emp != et["empreinte"]:
            rendu["a_reverifier"].append((ej, et["etablissement"], "inscriptions de FINESS ou du ROR modifiées"))
        elif age > DUREE_JOURS:
            rendu["a_reverifier"].append((ej, et["etablissement"], f"vérification de plus d'un an ({et['date']})"))
        base = x[(x["ej"] == ej) & x["type"].isin(types) & ((x["dep"] == dep) if dep else True)]
        # une ligne « CMP pour adultes » ou « pour enfants » suit sa ligne « tous publics » même quand son entité
        # juridique n'est pas renseignée (unité du ROR réunie à un CMP de FINESS, constat du 13 octobre 2026)
        lieux_par = set(base.loc[base["type"].isin(ENFANTS_DE), "lieu"])
        enf_types = [c for t in parents for c in ENFANTS_DE.get(t, [])]
        base = pd.concat([base, x[x["type"].isin(enf_types) & x["lieu"].isin(lieux_par) & ~x.index.isin(base.index)]])
        # vérification limitée à un public, les inscriptions de l'autre public restent telles quelles, celles dont le
        # public n'est pas précisé (ou qui accueillent les deux) peuvent être rapprochées mais ne sont jamais retirées
        perim = perimetres(et["types"])
        incertains, autre_lieux = set(), {}
        for t, p in perim.items():
            enf = ENFANTS_DE.get(t, [])
            l_p = set(base.loc[base["type"].isin([c for c in enf if c.endswith(p)]), "lieu"])
            l_a = set(base.loc[base["type"].isin([c for c in enf if not c.endswith(p)]), "lieu"])
            autre_lieux[t] = l_a
            hors = base.index[base["lieu"].isin(l_a - l_p) & base["type"].isin([t] + enf)]
            base = base.drop(index=hors)
            incertains |= set(base.index[(base["type"] == t) & (~base["lieu"].isin(l_p) | base["lieu"].isin(l_a))])
        retirer += base.index.tolist()
        ver = s[(s["ej"] == ej) & s["type"].isin(parents)]
        if dep:
            ver = ver[ver["commune"].map(ref.communes.set_index("code")["dep"]) == dep]
        # unités du ROR sans établissement de rattachement, dans une commune de la liste vérifiée. Elles ne sont
        # retirées que si leur nom ou leur rue les rapproche d'une structure vérifiée (CMP de Saint-Renan du CHU de
        # Brest, inscrit au ROR sans numéro FINESS, constat du 14 octobre 2026)
        orph = x[x["ej"].isna() & x["type"].isin(parents) & x["commune"].isin(set(ver["commune"]))
                 & ~x.index.isin(retirer)]
        for t in parents:
            b = pd.concat([base[base["type"] == t], orph[orph["type"] == t]])
            v = ver[ver["type"] == t]
            pris = set()
            for _, r in v.iterrows():
                # inscriptions des bases rapprochées, même commune, puis mots du nom ou rue en commun
                # d'abord les numéros FINESS relevés à la vérification (colonne finess), puis le rapprochement
                voulus = {n.strip() for n in str(r.get("finess") or "").split(",") if n.strip()}
                if voulus:
                    nums_b = b.apply(lambda c: {str(c.get(k)) for k in ("finess", "finess_rapproche")
                                                if isinstance(c.get(k), str)}
                                     | set(str(c.get("finess_absorbes") or "").split(",")), axis=1)
                    lies = [i for i in b.index if i not in pris and nums_b[i] & voulus]
                    # un numéro d'hôpital porte plusieurs unités, on ne garde que celles de la même commune
                    if len(lies) > 1:
                        lies = [i for i in lies if b.at[i, "commune"] == r["commune"]] or lies[:1]
                    # plus les unités du ROR sans établissement de la même commune, de même rue ou de même nom
                    # (CMP Anatole-France de Charenton-le-Pont, inscrit aussi comme « CMP périnatalité 94I03 » sans
                    # établissement, constat du 15 octobre 2026)
                    cand = b[b.index.isin(orph.index) & (b["commune"] == r["commune"]) & ~b.index.isin(pris)
                             & ~b.index.isin(lies)]
                else:
                    lies = None
                    cand = b[(b["commune"] == r["commune"]) & ~b.index.isin(pris)]
                mv, rv = _mots(r["nom"]), _rue(r["adresse"])
                score = {i: len(mv & _mots(str(c.get("nom") or c.get("nom_finess") or "")))
                         + 2 * (bool(rv) and _rue(c.get("adresse")) == rv) for i, c in cand.iterrows()}
                meilleurs = [i for i, sc in score.items() if sc > 0]
                if lies is not None:
                    # seulement par la rue, un mot du nom (souvent la commune) ne suffit pas ici
                    lies = lies + [i for i in meilleurs if rv and _rue(cand.at[i, "adresse"]) == rv]
                else:
                    propres = cand[~cand.index.isin(orph.index)]
                    lies = sorted(meilleurs, key=lambda i: -score[i])[:1] or (
                        propres.index[:1].tolist() if len(cand) == 1 and len(propres) == 1
                        and len(v[v["commune"] == r["commune"]]) == 1 else [])
                pris |= set(lies)
                nums = set()
                for i in lies:
                    for c in ("finess", "finess_rapproche", "finess_absorbes"):
                        val = b.at[i, c] if c in b else None
                        if isinstance(val, str) and val:
                            nums |= set(val.split(","))
                prov = "sources"
                if lies:
                    pv = set(b.loc[lies, "provenance"])
                    prov = "les_deux" if "les_deux" in pv or {"finess", "ror"} <= pv else next(iter(pv))
                num = sorted(nums)[0] if nums else None
                cle = "V" + ej + "|" + r["commune"] + "|" + re.sub(r"\W+", "-", r["nom"].lower()).strip("-")
                adr = r["adresse"] or next((b.at[i, "adresse"] for i in lies if isinstance(b.at[i, "adresse"], str)
                                            and b.at[i, "commune"] == r["commune"]), "")
                ligne = {"type": t, "lieu": cle, "nom": r["nom"], "nom_affiche": r["nom"], "ej": ej,
                         "commune": r["commune"], "voie": adr, "adresse": adr,
                         "origine_commune": "unite", "provenance": prov, "finess": num,
                         # emplacement de l'inscription rapprochée, gardé quand l'adresse vérifiée est la sienne
                         **({"lat_base": b.at[lies[0], "lat"], "lon_base": b.at[lies[0], "lon"],
                             "precision_base": b.at[lies[0], "precision"]}
                            if lies and not r["adresse"] and "lat" in b and b.at[lies[0], "commune"] == r["commune"]
                            else {}),
                         "finess_absorbes": ",".join(sorted(nums - {num})) or None, "verifiee": True,
                         "statut_verification": r.get("statut", ""), "source_verification": r["source"], "adresse_source": r["adresse_source"],
                         "date_verification": r["date"], "remarque_verification": r.get("remarque", ""), "nom_finess": None, "categorie_finess": None,
                         "unites_ror": int(b.loc[lies, "unites_ror"].fillna(0).sum()) if lies and "unites_ror" in b else 0}
                nouvelles.append(ligne)
                pub = (r.get("public") or "").lower()
                # public de la liste vérifiée, plus l'autre public quand l'inscription rapprochée l'accueillait aussi
                # et que la vérification ne portait que sur un public
                aussi = bool(t in perim and set(b.loc[lies, "lieu"]) & autre_lieux.get(t, set()))
                for enf in ENFANTS_DE.get(t, []):
                    if (enf.endswith("adultes") and "adulte" in pub) or (enf.endswith("enfants") and "enfant" in pub)                             or (aussi and not enf.endswith(perim[t])):
                        nouvelles.append({**ligne, "type": enf})
                rendu["ajoutees"] += prov == "sources"
            pris_orph = [i for i in pris if i in orph.index]
            retirer += pris_orph + x.index[x["type"].isin(ENFANTS_DE.get(t, []))
                                           & x["lieu"].isin(set(x.loc[pris_orph, "lieu"]))].tolist()
            # inscriptions au public incertain non rapprochées, laissées telles quelles avec leurs lignes par public
            reste = [i for i in b.index.difference(list(pris)) if i in incertains]
            lieux_reste = set(x.loc[reste, "lieu"])
            retirer = [i for i in retirer if i not in set(reste)
                       and not (x.at[i, "type"] in ENFANTS_DE.get(t, []) and x.at[i, "lieu"] in lieux_reste)]
            for i in b.index.difference(list(pris)).difference(orph.index).difference(reste):
                garde = i in garder
                if garde:
                    gardes.append(i)
                (rendu["gardees"] if garde else rendu["non_retenues"]).append({
                    "ej": ej, "etablissement": et["etablissement"], "type": t,
                    "nom": b.at[i, "nom"] if isinstance(b.at[i, "nom"], str) else b.loc[i].get("nom_finess"),
                    "commune": b.at[i, "commune"], "nom_commune": nom_com.get(b.at[i, "commune"], ""),
                    "finess": ",".join(sorted(_nums_ligne(b.loc[i]))) or None, "provenance": b.at[i, "provenance"],
                    "raison": ("absente de la liste vérifiée, gardée car confirmée par la certification HAS ou Sirene, "
                               "à vérifier à la main") if garde else "absente de la liste vérifiée de l'établissement"})
    # inscriptions gardées, avec leurs lignes pour adultes ou pour enfants
    if gardes:
        lieux_gardes = set(x.loc[gardes, "lieu"])
        enfants = sum(ENFANTS_DE.values(), [])
        retirer = [i for i in retirer if i not in set(gardes)
                   and not (x.at[i, "type"] in enfants and x.at[i, "lieu"] in lieux_gardes)]
    x = x.drop(index=retirer)
    if nouvelles:
        n = pd.DataFrame(nouvelles)
        n = placer(n, centres, hors_ligne)
        rattach = ref.communes.set_index("code")[["epci", "dep", "reg"]]
        n = n.join(rattach, on="commune")
        labels = {t[0]: t for t in config.LIEUX_TYPES}
        n["libelle_type"] = n["type"].map(lambda t: labels[t][1])
        n["famille"] = n["type"].map(lambda t: labels[t][2])
        n["groupe"] = n["type"].map(lambda t: labels[t][3])
        x = pd.concat([x, n], ignore_index=True)
    x["verifiee"] = x["verifiee"].fillna(False).astype(bool)
    dup = int(x.duplicated(["type", "lieu"]).sum())
    if dup:
        raise ValueError(f"{dup} structures en double après la liste vérifiée (deux lignes de même nom dans la même "
                         f"commune pour un même établissement)")
    n_et = len(e)
    JOURNAL.controle("Structures de soins, établissements vérifiés sur leurs propres sources",
                     f"{n_et} établissements, {int(x['verifiee'].sum())} structures vérifiées, "
                     f"{rendu['ajoutees']} absentes des deux bases, {len(rendu['non_retenues'])} inscriptions non retenues, "
                     f"{len(rendu['gardees'])} gardées en attente de vérification (confirmées par la HAS ou Sirene)")
    JOURNAL.controle("Structures de soins, établissements à revérifier (attendu, aucun)",
                     "aucun" if not rendu["a_reverifier"] else
                     "; ".join(f"{n} ({r})" for _, n, r in rendu["a_reverifier"][:10]))
    return x, rendu
