"""Liste vérifiée des structures de soins (décision du 13 octobre 2026).

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
# inscriptions des bases laissées de côté, une par ligne avec sa raison (règle du 19 novembre 2026 : dans le doute, une
# structure reste comptée). Une inscription absente de la liste vérifiée de son établissement et absente de ce fichier
# est gardée : 233 inscriptions retirées sans raison propre trouvées le 20 novembre 2026 (hôpitaux de jour de
# gérontopsychiatrie de l'EPSY Var écrits en CATTP, consultation du lycée Raynouard de Brignoles).
FICHIER_LAISSEES = config.RACINE / "contenus" / "inscriptions_laissees.csv"
COLS_LAISSEES = ["ej", "type", "nom", "commune", "finess", "categorie", "raison", "date"]
CATEGORIES_LAISSEES = {"liste_complete": "absente de la liste complète et actuelle de l'établissement",
                       "doublon": "doublon d'une structure de la liste vérifiée",
                       "pas_ce_type": "n'est pas une structure de ce type selon la source de l'établissement",
                       "fermee": "fermée selon la source de l'établissement"}


def charger_laissees() -> pd.DataFrame:
    return (pd.read_csv(FICHIER_LAISSEES, sep=";", dtype=str, encoding="utf-8").fillna("")
            if FICHIER_LAISSEES.exists() else pd.DataFrame(columns=COLS_LAISSEES))
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
    """Empreinte des inscriptions de FINESS et du ROR d'un établissement pour ces types, qui change dès qu'une base
    ajoute, retire ou déplace une inscription. Elle ne retient que ce que donnent les bases, numéros FINESS et noms des
    unités du ROR avec leur commune, en ensemble sans doublon, et non les clés des structures réunies, qui portent le
    nom et l'adresse normalisés par nos règles. Un changement de règle (une structure réunie autrement, ou copiée dans
    un autre type vérifié) ne la change donc plus (point sur la tâche planifiée du 28 octobre 2026, huit établissements
    signalés à tort depuis la règle CMP-CATTP du 16 octobre)."""
    from .lieux import _simple
    g = lieux[(lieux["ej"] == ej) & lieux["type"].isin(types)]
    if dep and "dep" in g:
        g = g[g["dep"] == dep]
    ids = set()
    for r in g.to_dict("records"):
        com = str(r.get("commune") or "")
        ids |= {f"F|{n}|{com}" for n in _nums_ligne(r)}
        unites = r.get("noms_unites")
        if isinstance(unites, str):
            ids |= {f"R|{_simple(u)}|{com}" for u in unites.split(" | ") if u.strip()}
    return hashlib.sha1("\n".join(sorted(ids)).encode("utf-8")).hexdigest()[:12]


def _mots(s: str) -> set[str]:
    from .lieux import _distinctif, _simple
    return set(_distinctif(_simple(s)).split()) - {"cmp", "cattp", "hdj", "hj", "centre", "hopital", "jour"}


def _public_du_nom(s) -> set[str]:
    """Public que le nom annonce (« CMP Adulte », « CMP PEDO », « Infanto-Juvénile »), vide s'il n'en dit rien ou
    nomme les deux."""
    from .lieux import _simple
    s = _simple(s if isinstance(s, str) else "")
    enf = re.search(r"\b(enfants?|enfance|infanto\w*|p[ée]do\w*|ados?|adolescen\w*|juvenile|cmpea?|perinat\w*|bebes?)\b", s)
    adu = re.search(r"\b(adultes?)\b", s)
    if re.search(r"\bcmp\b", s) and re.search(r"\bcmpea?\b", s):  # « CMP, CMPEA et CATTP d'Arudy » : les deux
        return set()
    return {"enfants"} if enf and not adu else {"adultes"} if adu and not enf else set()


def _partager(r, lies: list, soeurs: pd.DataFrame, b: pd.DataFrame, x: pd.DataFrame, t: str) -> list:
    """Inscriptions d'un même numéro FINESS, dans une commune où plusieurs lignes de la liste vérifiée portent ce
    numéro (CMP pour adultes et CMP pour enfants d'un hôpital inscrits sous un seul numéro) : chacune revient à la
    ligne qui lui ressemble le plus, par les mots du nom, la rue et le public, et non à la première ligne lue
    (relecture du 21 novembre 2026 : à Mirande, Friville-Escarbotin, Fumel, Marseille et Avignon, une ligne prenait
    les deux inscriptions et les deux publics, et l'autre perdait son public ou disparaissait). Une seule inscription
    pour plusieurs lignes va de même à celle qui lui ressemble le plus (CATTP pour adultes de Bras-Fusil, Saint-Benoît).
    À égalité, la première ligne lue la prend, et elle n'est plus offerte aux suivantes (pris)."""
    enf = ENFANTS_DE.get(t, [])

    def pub_ligne(l_):
        p = str(l_.get("public") or "").lower()
        out = ({"adultes"} if "adulte" in p else set()) | ({"enfants"} if "enfant" in p else set())
        return out or _public_du_nom(l_.get("nom"))

    def pub_insc(i):
        ty = set(x.loc[(x["lieu"] == b.at[i, "lieu"]) & x["type"].isin(enf), "type"])
        out = {("adultes" if c.endswith("adultes") else "enfants") for c in ty}
        return out or _public_du_nom(b.at[i, "nom"] if isinstance(b.at[i, "nom"], str) else b.loc[i].get("nom_finess"))

    def score(l_, i):
        nom_i = b.at[i, "nom"] if isinstance(b.at[i, "nom"], str) else str(b.loc[i].get("nom_finess") or "")
        rv = _rue(l_.get("adresse"))
        s_ = len(_mots(l_["nom"]) & _mots(nom_i)) + 2 * (bool(rv) and _rue(b.at[i, "adresse"]) == rv)
        pl, pi = pub_ligne(l_), pub_insc(i)
        if pl and pi:
            s_ += 3 if pl & pi else -3
        return s_

    garde = []
    for i in lies:
        sc = {k: score(l_, i) for k, l_ in soeurs.iterrows()}
        if sc[r.name] == max(sc.values()):
            garde.append(i)
    return garde


def _rue(s: str) -> str:
    from .lieux import _simple
    return re.sub(r"^\d+\s*(?:bis|ter|b|t)?\s+", "", _simple(s or ""))


def _voie(s) -> tuple[str, str]:
    """Numéro et rue d'une adresse, abréviations développées (« PL JEAN TAVE » et « place Jean-Tavé »)."""
    from .lieux import _simple, voie_developpee
    a = _simple(voie_developpee(s if isinstance(s, str) else ""))
    m = re.match(r"^(\d+\s*(?:bis|ter|b|t)?)\s+(.*)$", a)
    return (m.group(1).replace(" ", ""), m.group(2)) if m else ("", a)


def meme_adresse(a: tuple[str, str], b: tuple[str, str]) -> bool:
    """Même rue, et même numéro ou numéro absent d'un côté."""
    return bool(a[1]) and a[1] == b[1] and (a[0] == b[0] or not a[0] or not b[0])


TYPES_MEME_ADRESSE = ("lieu_cmp_adultes", "lieu_cmp_enfants", "lieu_cattp", "lieu_hdj_psy_adultes",
                      "lieu_hdj_psy_enfants", "lieu_csapa", "lieu_cmpp", "lieu_camsp", "lieu_caarud")


def meme_adresse_deux_gestionnaires(x: pd.DataFrame, ej: str = "ej", verifiee=None) -> list[dict]:
    """Structures du même type (et du même public pour les CMP) à la même adresse sous deux gestionnaires, dont une
    attestée par la liste vérifiée de son gestionnaire. Le plus souvent la même structure inscrite deux fois : quand une
    liste vérifiée en retire une, l'inscription des bases revient gardée « dans le doute » si rien ne dit qu'elle est
    laissée de côté (CMPEA de Blanquefort, Eysines, Saint-Médard et Pauillac, gérés par l'association Rénovation pour
    le CH Charles-Perrens, comptés deux fois, relecture du 22 novembre 2026). verifiee, la série booléenne des lignes
    attestées (par défaut le statut etablissement ou source_publique)."""
    if verifiee is None:
        verifiee = x.get("statut_verification", pd.Series("", index=x.index)).isin(["etablissement", "source_publique"])
    y = x[x["type"].isin(TYPES_MEME_ADRESSE)].assign(attestee_=verifiee)
    y = y.assign(voie_n_=y.get("adresse", pd.Series("", index=y.index)).map(_voie))
    # gestionnaire connu des deux côtés : une unité du ROR sans établissement n'est pas « d'un autre gestionnaire »
    y = y[y[ej].fillna("").astype(str).str.strip() != ""]
    out = []
    for (t, c), g in y.groupby(["type", "commune"]):
        if g[ej].nunique() < 2 or not g["attestee_"].any():
            continue
        for a in g[g["attestee_"]].itertuples():
            for b in g.itertuples():
                if getattr(b, ej) != getattr(a, ej) and meme_adresse(a.voie_n_, b.voie_n_):
                    # même numéro des deux côtés, ou numéro absent d'un côté (alors seulement la même rue)
                    out.append({"type": t, "commune": c, "verifiee": _nom_vu(a), "autre": _nom_vu(b),
                                "i_autre": b.Index, "autre_attestee": bool(b.attestee_),
                                "meme_numero": bool(a.voie_n_[0] and b.voie_n_[0])})
    return out


FICHIER_PAIRES_DISTINCTES = config.RACINE / "contenus" / "paires_distinctes.csv"


def paires_distinctes() -> set:
    """Paires de structures à la même adresse sous deux gestionnaires que les sources disent distinctes, chacune avec sa
    source (relecture du 19 novembre 2026) : (type, nom de la structure attestée, nom de l'autre)."""
    if not FICHIER_PAIRES_DISTINCTES.exists():
        return set()
    d = pd.read_csv(FICHIER_PAIRES_DISTINCTES, sep=";", dtype=str, encoding="utf-8").fillna("")
    return {(r.type, r.nom_attestee, r.nom_autre) for r in d.itertuples()}


def _nom_vu(r) -> str:
    n = getattr(r, "nom_affiche", None)
    return n if isinstance(n, str) and n else str(r.nom)


def _nums_ligne(r) -> set[str]:
    """Numéros FINESS d'une inscription (le sien, celui rapproché, ceux réunis à elle)."""
    out = set()
    for c in ("finess", "finess_rapproche", "finess_absorbes"):
        v = r.get(c)
        if isinstance(v, str) and v:
            out |= set(v.split(","))
    return out


def placer(n: pd.DataFrame, centres: dict | None, hors_ligne: bool, chefs_lieux=None) -> pd.DataFrame:
    """Coordonnées des structures vérifiées, par leur adresse géocodée (service de l'IGN, avec cache), sinon
    l'emplacement de l'inscription rapprochée, sinon le chef-lieu de leur commune (chefs_lieux, même règle que les autres
    structures depuis le 29 octobre 2026, oubliée ici jusqu'au 20 novembre 2026), sinon le centre de son contour."""
    from .lieux import _geocoder
    n = n.copy()
    n["lat"], n["lon"], n["precision"] = float("nan"), float("nan"), None
    a = n[["adresse", "commune"]].rename(columns={"adresse": "voie"})
    cache = _geocoder(a, hors_ligne)
    g = cache.dropna(subset=["lat"]).drop_duplicates(["voie", "commune"]).set_index(["voie", "commune"])
    sans = sorted({c for v, c in zip(n["adresse"], n["commune"]) if (v, c) not in g.index and isinstance(c, str)})
    ch = (chefs_lieux(sans) or {}) if chefs_lieux is not None and sans else {}
    for i, (v, c) in enumerate(zip(n["adresse"], n["commune"])):
        if (v, c) in g.index:
            n.iloc[i, n.columns.get_loc("lat")] = float(g.at[(v, c), "lat"])
            n.iloc[i, n.columns.get_loc("lon")] = float(g.at[(v, c), "lon"])
            n.iloc[i, n.columns.get_loc("precision")] = g.at[(v, c), "niveau"]
        elif "lat_base" in n and pd.notna(n["lat_base"].iloc[i]):
            n.iloc[i, n.columns.get_loc("lat")] = float(n["lat_base"].iloc[i])
            n.iloc[i, n.columns.get_loc("lon")] = float(n["lon_base"].iloc[i])
            n.iloc[i, n.columns.get_loc("precision")] = n["precision_base"].iloc[i]
        elif ch.get(c):
            n.iloc[i, n.columns.get_loc("lon")] = ch[c][0]
            n.iloc[i, n.columns.get_loc("lat")] = ch[c][1]
            n.iloc[i, n.columns.get_loc("precision")] = "chef_lieu"
        elif centres and centres.get(c):
            n.iloc[i, n.columns.get_loc("lon")] = centres[c][0]
            n.iloc[i, n.columns.get_loc("lat")] = centres[c][1]
            n.iloc[i, n.columns.get_loc("precision")] = "commune"
    return n.drop(columns=[c for c in ("lat_base", "lon_base", "precision_base") if c in n])


def fermees_finess(fin: pd.DataFrame | None) -> dict:
    """Numéros FINESS fermés et date de leur fermeture d'après Finess+ (le flux historique ne la donne pas)."""
    if fin is None or "date_fermeture" not in fin:
        return {}
    f = fin[~fin["actif"].astype(bool) & fin["date_fermeture"].notna()]
    return dict(zip(f["nofinesset"].astype(str).str.zfill(9), f["date_fermeture"].astype(str).str[:10]))


def fermee_depuis(r, fermees: dict) -> str | None:
    """Date de fermeture dans FINESS d'une structure de la liste vérifiée qui ne doit plus être comptée, quand tous ses
    numéros FINESS relevés sont fermés (règle du 29 octobre 2026, précisée le même jour), sinon None.
    - Fermeture postérieure à la vérification, la structure n'est plus comptée, quelle que soit la source.
    - Fermeture antérieure, selon la source de la vérification (statut). L'établissement qui présente encore la
      structure après la fermeture l'emporte, elle reste comptée (antenne de Puget-Théniers du CH Sainte-Marie, page
      de l'établissement du 29 octobre 2026, numéro fermé le 22 septembre). Une autre source publique peut retarder,
      la fermeture l'emporte si elle date de moins d'un an (DUREE_JOURS, durée de validité d'une vérification), comme
      pour les CMP de Sainte-Marie fermés les 20 et 22 septembre et encore décrits par des pages lues le 15 octobre ;
      plus ancienne, elle était connue et la structure a été trouvée, souvent passée sous un autre numéro. Une
      structure gardée sur la seule foi des bases n'est plus attestée par rien, elle n'est plus comptée."""
    nums = {n.strip().zfill(9) for n in str(r.get("finess") or "").split(",") if n.strip()}
    if not nums or not all(n in fermees for n in nums) or not r.get("date"):
        return None
    date = max(fermees[n] for n in nums)
    try:
        ecart = (dt.date.fromisoformat(r["date"]) - dt.date.fromisoformat(date)).days
    except ValueError:
        return None
    statut = r.get("statut") or ""
    if ecart < 0 or statut == "bases":
        return date
    if statut == "etablissement":
        return None
    return date if ecart < DUREE_JOURS else None


def appliquer(lieux: pd.DataFrame, ref, centres: dict | None = None,
              hors_ligne: bool = True, garder: set | None = None,
              fermees: dict | None = None, chefs_lieux=None) -> tuple[pd.DataFrame, dict]:
    """Remplace, pour chaque établissement vérifié, ses structures des types vérifiés par la liste vérifiée. Les
    numéros FINESS des inscriptions rapprochées restent attachés (finess_absorbes), celles qui ne correspondent à
    aucune structure vérifiée sont consignées. Une inscription non citée par la source mais confirmée par une autre
    liste officielle (index dans garder, certification HAS ou Sirene) est gardée en attendant une vérification à la
    main (décision du 14 octobre 2026). Une structure de la liste fermée depuis dans FINESS (fermees, numéro
    et date) et qu'aucune inscription active ne décrit n'est plus comptée, et son établissement est à revérifier
    (fermee_depuis). Renvoie les structures et un compte rendu."""
    e, s = charger()
    garder, fermees = garder or set(), fermees or {}
    # deux structures de même nom générique dans une commune (« Centre médico-psychologique » à Paris), à deux
    # adresses : l'adresse entre dans leur clé (vérification par lots du 18 novembre 2026)
    _cles = ("V" + s["ej"] + "|" + s["commune"] + "|"
             + s["nom"].str.lower().map(lambda v: re.sub(r"\W+", "-", v).strip("-")) + "#" + s["type"])
    cles_doubles = {k.split("#")[0] for k in _cles[_cles.duplicated(keep=False)]}
    rendu = {"etablissements": e, "a_reverifier": [], "non_retenues": [], "gardees": [], "ajoutees": 0, "fermees": []}
    gardes = []
    lai = charger_laissees()
    # plusieurs lignes peuvent partager un nom dans une commune (deux « CATTP adulte » à Flers) : chacune garde son
    # numéro FINESS, exigé pour laisser de côté une inscription qui en porte un (relecture du 22 novembre 2026)
    laissees: dict = {}
    for r in lai.itertuples():
        laissees.setdefault((r.ej, r.type, r.commune, r.nom.strip()), []).append(
            (str(r.finess) if isinstance(r.finess, str) else "", r.categorie, r.raison))
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
            # numéros FINESS que les lignes de la vérification revendiquent : une ligne sans numéro ne prend pas une
            # inscription qu'une autre ligne réclame par son numéro (CMP pour adultes de Valence prenant, par le nom
            # de la commune, celle du CMP pour enfants, vérification de Montauban du 16 novembre 2026)
            # (un numéro d'hôpital porte des unités de plusieurs communes : seul le couple numéro et commune est réservé)
            reclames = {(n.strip(), c) for x, c in zip(v["finess"].fillna(""), v["commune"])
                        for n in str(x).split(",") if n.strip()}
            pris = set()
            adresses_ver = []
            for _, r in v.iterrows():
                # inscriptions des bases rapprochées, même commune, puis mots du nom ou rue en commun
                # d'abord les numéros FINESS relevés à la vérification (colonne finess), puis le rapprochement
                voulus = {n.strip() for n in str(r.get("finess") or "").split(",") if n.strip()}
                if voulus:
                    nums_b = b.apply(lambda c: {str(c.get(k)) for k in ("finess", "finess_rapproche")
                                                if isinstance(c.get(k), str)}
                                     | set(str(c.get("finess_absorbes") or "").split(",")), axis=1)
                    # numéros que cette ligne est seule à réclamer dans sa commune : l'inscription qui les porte lui
                    # revient même si une autre ligne l'a déjà prise par un numéro qu'elle avait absorbé (Givors,
                    # Cergy, Marseille, constat du 20 novembre 2026)
                    a_soi = {n for n in voulus if sum(n in {m.strip() for m in str(f).split(",")}
                                                       for f, c in zip(v["finess"].fillna(""), v["commune"])
                                                       if c == r["commune"]) == 1}
                    lies = [i for i in b.index if i not in pris and nums_b[i] & voulus] or \
                        [i for i in b.index if nums_b[i] & a_soi and b.at[i, "commune"] == r["commune"]]
                    # un numéro d'hôpital porte plusieurs unités, on ne garde que celles de la même commune
                    if len(lies) > 1:
                        lies = [i for i in lies if b.at[i, "commune"] == r["commune"]] or lies[:1]
                    if lies:
                        soeurs = v[(v["commune"] == r["commune"]) & v["finess"].fillna("").map(
                            lambda f: bool({n.strip() for n in str(f).split(",") if n.strip()} & voulus))]
                        if len(soeurs) > 1:
                            lies = _partager(r, lies, soeurs, b, x, t)
                    # plus les unités du ROR sans établissement de la même commune, de même rue ou de même nom
                    # (CMP Anatole-France de Charenton-le-Pont, inscrit aussi comme « CMP périnatalité 94I03 » sans
                    # établissement, constat du 15 octobre 2026)
                    cand = b[b.index.isin(orph.index) & (b["commune"] == r["commune"]) & ~b.index.isin(pris)
                             & ~b.index.isin(lies)]
                else:
                    lies = None
                    cand = b[(b["commune"] == r["commune"]) & ~b.index.isin(pris)]
                    if reclames and "finess" in cand:
                        cand = cand[[(str(f), c) not in reclames for f, c in zip(cand["finess"], cand["commune"])]]
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
                ferme = None if lies else fermee_depuis(r, fermees)
                if ferme:
                    raison = (f"fermée dans FINESS le {ferme} (numéro {r['finess']}), aucune inscription active de FINESS "
                              f"ni du ROR, vérification du {r['date']} à refaire")
                    rendu["fermees"].append({"ej": ej, "etablissement": et["etablissement"], "type": t, "nom": r["nom"],
                                             "commune": r["commune"], "nom_commune": nom_com.get(r["commune"], ""),
                                             "finess": r["finess"], "provenance": "sources", "raison": raison})
                    if ej not in {a[0] for a in rendu["a_reverifier"]}:
                        rendu["a_reverifier"].append((ej, et["etablissement"], "structure de la liste fermée depuis dans FINESS"))
                    continue
                nums = set()
                for i in lies:
                    for c in ("finess", "finess_rapproche", "finess_absorbes"):
                        val = b.at[i, c] if c in b else None
                        if isinstance(val, str) and val:
                            nums |= set(val.split(","))
                prov = "sources"
                # sans inscription propre (déjà prise par une autre ligne de la commune, souvent l'autre public au même
                # numéro), une ligne qui porte un numéro inscrit dans les bases n'est pas « absente des deux bases » :
                # elle reprend la provenance de l'inscription de ce numéro (relecture du 21 novembre 2026, 25 lignes)
                lies_prov = lies or ([i for i in b.index if nums_b[i] & voulus] if voulus else [])
                src_prov = b
                if not lies_prov and voulus:
                    # numéro inscrit sous un autre type de l'établissement (« Atelier 18 », hôpital de jour au ROR)
                    src_prov = x[x["ej"] == ej]
                    lies_prov = [i for i, c in src_prov.iterrows() if voulus & {
                        n.strip() for k in ("finess", "finess_rapproche", "finess_absorbes")
                        for n in str(c.get(k) or "").split(",") if n.strip()}]
                if not lies_prov and r.get("statut") == "bases":
                    # ligne « inscrite dans les bases » sans numéro : son inscription, au même nom dans la commune
                    src_prov = x[(x["ej"] == ej) & (x["commune"] == r["commune"])]
                    nom_r = r["nom"].strip().lower()
                    lies_prov = [i for i, c in src_prov.iterrows()
                                 if nom_r in {str(c.get(k) or "").strip().lower() for k in ("nom", "nom_finess")}]
                if lies_prov:
                    # un site ajouté par son activité autorisée est inscrit dans FINESS, sans être une unité de ce
                    # type : la ligne vérifiée est « FINESS seul », jamais « activité autorisée » (CMP de Mayotte)
                    pv = {{"autorisation": "finess"}.get(p_, p_) for p_ in src_prov.loc[lies_prov, "provenance"]
                          if p_ in ("les_deux", "finess", "ror", "ror_type", "autorisation")} or {"sources"}
                    # ordre fixe : un ensemble se parcourt dans un ordre qui change d'une exécution à l'autre
                    prov = "les_deux" if "les_deux" in pv or {"finess", "ror"} <= pv else                         next(p_ for p_ in ("finess", "ror", "ror_type", "autorisation", "sources") if p_ in pv)
                # le numéro de la ligne est celui qu'elle réclame ; un numéro qu'une autre ligne de la même commune
                # réclame ne lui est jamais attribué, même absorbé par l'inscription rapprochée (20 novembre 2026)
                nums -= {n for n, c in reclames if c == r["commune"]} - voulus
                num = (sorted(nums & voulus) or sorted(nums) or [None])[0]
                cle = "V" + ej + "|" + r["commune"] + "|" + re.sub(r"\W+", "-", r["nom"].lower()).strip("-")
                if cle in cles_doubles:
                    cle += "|" + re.sub(r"\W+", "-", str(r["adresse"]).lower()).strip("-")
                adr = r["adresse"] or next((b.at[i, "adresse"] for i in lies if isinstance(b.at[i, "adresse"], str)
                                            and b.at[i, "commune"] == r["commune"]), "")
                # catégorie FINESS de l'inscription qui porte le numéro de la ligne, gardée pour les CSAPA seulement :
                # le compte des établissements CSAPA de FINESS la lit (« 674 lieux de CSAPA correspondent à 6
                # établissements de FINESS », relecture du 21 novembre 2026). Les autres types ne la reprennent pas,
                # pour qu'une catégorie des bases ne change pas le type d'une structure vérifiée.
                cat_v = None
                if t == "lieu_csapa" and lies and "categorie_finess" in b:
                    cats_ = [b.at[i, "categorie_finess"] for i in lies
                             if num and num in str(b.at[i, "finess"] or "").split(",")]                         or [b.at[i, "categorie_finess"] for i in lies]
                    cat_v = next((c_ for c_ in cats_ if isinstance(c_, str) and c_), None)
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
                         "date_verification": r["date"], "remarque_verification": r.get("remarque", ""), "nom_finess": None, "categorie_finess": cat_v,
                         "unites_ror": int(b.loc[lies, "unites_ror"].fillna(0).sum()) if lies and "unites_ror" in b else 0}
                nouvelles.append(ligne)
                adresses_ver.append((r["commune"], _voie(adr)))
                pub = (r.get("public") or "").lower()
                # public laissé vide par la source : celui des inscriptions rapprochées, pour qu'un CMP vérifié ne
                # sorte pas des CMP pour adultes ou pour enfants (CH d'Abbeville, 18 novembre 2026, cinq CMP sans public)
                if not pub and lies:
                    pub = " ".join(("adultes" if e_.endswith("adultes") else "enfants") for e_ in sorted(set(
                        x.loc[x["lieu"].isin(set(b.loc[lies, "lieu"])) & x["type"].isin(ENFANTS_DE.get(t, [])), "type"])))
                    if pub:
                        rendu.setdefault("public_des_bases", []).append((ej, r["nom"], pub))
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
                # une inscription confirmée par la HAS ou Sirene n'est pas gardée quand la liste vérifiée de son
                # établissement compte déjà une structure du même type à la même adresse : c'est la même, inscrite de
                # nouveau sous un autre numéro (CMP Daviers d'Angers du CESAME, numéro 490025012 apparu après la
                # vérification d'octobre, constat du 17 novembre 2026)
                deja = any(c == b.at[i, "commune"] and meme_adresse(a, _voie(b.at[i, "adresse"]))
                           for c, a in adresses_ver)
                nom_i = b.at[i, "nom"] if isinstance(b.at[i, "nom"], str) else b.loc[i].get("nom_finess")
                # laissée de côté seulement avec une raison écrite pour elle (inscriptions_laissees.csv), ou au même
                # endroit qu'une structure de la liste ; sinon gardée, dans le doute (règle du 19 novembre 2026)
                nums_i = _nums_ligne(b.loc[i])
                lai_i = next(((cat, rai) for fi, cat, rai in laissees.get((ej, t, b.at[i, "commune"], str(nom_i or "").strip()), [])
                              if not fi or not nums_i or set(fi.split(",")) & nums_i), None)
                garde = not deja and not lai_i
                if garde:
                    gardes.append(i)
                (rendu["gardees"] if garde else rendu["non_retenues"]).append({
                    "ej": ej, "etablissement": et["etablissement"], "type": t, "nom": nom_i,
                    "commune": b.at[i, "commune"], "nom_commune": nom_com.get(b.at[i, "commune"], ""),
                    "finess": ",".join(sorted(_nums_ligne(b.loc[i]))) or None, "provenance": b.at[i, "provenance"],
                    "raison": ("absente de la liste vérifiée, gardée car confirmée par la certification HAS ou Sirene, "
                               "à vérifier à la main") if garde and i in garder else
                              ("absente de la liste vérifiée de l'établissement, qui ne donne pas de raison de la "
                               "laisser de côté : gardée, à vérifier") if garde else
                              ("même adresse qu'une structure de la liste vérifiée de l'établissement, déjà comptée"
                               if deja else f"{CATEGORIES_LAISSEES.get(lai_i[0], lai_i[0])} : {lai_i[1]}")})
    # inscriptions gardées, avec leurs lignes pour adultes ou pour enfants
    if gardes:
        lieux_gardes = set(x.loc[gardes, "lieu"])
        enfants = sum(ENFANTS_DE.values(), [])
        retirer = [i for i in retirer if i not in set(gardes)
                   and not (x.at[i, "type"] in enfants and x.at[i, "lieu"] in lieux_gardes)]
    x = x.drop(index=retirer)
    if nouvelles:
        n = pd.DataFrame(nouvelles)
        n = placer(n, centres, hors_ligne, chefs_lieux)
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
    JOURNAL.controle("Structures de soins, établissements vérifiés sur leurs propres sources, au moment de la liste "
                     "vérifiée (avant la réunion des CMP du même public à la même adresse)",
                     f"{n_et} établissements, {int(x['verifiee'].sum())} structures vérifiées, "
                     f"{rendu['ajoutees']} absentes des deux bases, {len(rendu['non_retenues'])} inscriptions non retenues, "
                     f"{len(rendu['gardees'])} gardées en attente de vérification (dont "
                     f"{sum(r['raison'].startswith('absente de la liste vérifiée, gardée car') for r in rendu['gardees'])}"
                     f" confirmées par la HAS ou Sirene, les autres faute de raison écrite pour les laisser de côté)")
    f = rendu["fermees"]
    JOURNAL.controle("Structures des listes vérifiées fermées depuis dans FINESS, plus comptées (attendu, aucune)",
                     "aucune" if not f else f"{len(f)}, " + "; ".join(f"{r['nom']} ({r['nom_commune']}), "
                                                                  f"{r['raison'].split(' (')[0]}" for r in f[:8]))
    # le contrôle n'en cite que les dix premiers, la liste entière est dans etablissements_verifies.csv
    # (raison_reverification), d'où la comparaison avant publication relit le nombre exact
    JOURNAL.controle("Structures de soins, établissements à revérifier (attendu, aucun)",
                     "aucun" if not rendu["a_reverifier"] else
                     "; ".join(f"{n} ({r})" for _, n, r in rendu["a_reverifier"][:10]))
    if len(rendu["a_reverifier"]) > 10:
        JOURNAL.controle("Structures de soins, nombre d'établissements à revérifier",
                         f"{len(rendu['a_reverifier'])}, liste et raisons dans etablissements_verifies.csv")
    return x, rendu
