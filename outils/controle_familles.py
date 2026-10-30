"""Recalcul indépendant de chaque famille d'indicateurs publiés, sur tous les territoires et tous les niveaux (audit
des chiffres du 30 octobre 2026). Le code lit les fichiers d'origine en cache (donnees/brut) et les fichiers publiés
(resultats/AAAA-MM-JJ) et refait chaque calcul avec pandas, sans appeler aucune fonction du programme. Seules les
définitions écrites (libellés, unités et motifs des mesures de l'INSEE dans pipeline/config.py) sont reprises, pour
vérifier justement que chaque chiffre correspond à son libellé : le facteur (pour 100, 1 000, 10 000 ou 100 000) et
le dénominateur (population, moins de 15 ans, 80 ans et plus) sont lus dans l'unité publiée.

    python outils/controle_familles.py [dossier de résultats]

Appelé par outils/controle_independant.py. Chaque famille donne une ligne ok ou ÉCART avec le nombre de valeurs
comparées, le nombre hors tolérance et le pire écart. Code de sortie 1 s'il y a un écart."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from pipeline import config  # noqa: E402  (définitions écrites seulement)

B = config.BRUT
lignes: list[str] = []


def dernier() -> Path:
    return sorted(p for p in config.RESULTATS.glob("20*") if (p / "site_data.json").exists())[-1]


def lire(R: Path, f: str, **k) -> pd.DataFrame | None:
    p = R / f
    if not p.exists():
        return None
    k.setdefault("dtype", {"code": str})
    return pd.read_csv(p, sep=";", decimal=",", encoding="utf-8-sig", low_memory=False, **k)


def comparer(famille: str, publie: pd.Series, recalcule: pd.Series, tol: float, relatif: bool = False,
             vides_attendus: pd.Index | None = None, part_admise: float = 0.0):
    """Compare deux séries indexées par code. Une valeur publiée vide là où le recalcul en donne une n'est un écart que
    hors des vides attendus (territoires sans mesure publiée par règle)."""
    x = pd.DataFrame({"p": pd.to_numeric(publie, errors="coerce"), "r": pd.to_numeric(recalcule, errors="coerce")})
    vides = x["p"].isna() & x["r"].notna()
    if vides_attendus is not None:
        vides &= ~x.index.isin(vides_attendus)
    x = x.dropna()
    e = (x["p"] - x["r"]).abs()
    if relatif:
        e = e / x["r"].abs().where(x["r"].abs() > 0, 1)
    hors = e > tol
    pire = e.idxmax() if len(e) else None
    # part_admise, territoires hors tolérance admis pour une raison écrite (intercommunalités de la carte de 2026
    # que le fichier de l'INSEE ne connaît pas encore)
    ok = hors.sum() <= part_admise * len(x) and vides.sum() <= part_admise * len(x) and len(x) > 0
    lignes.append(("ok   " if ok else "ÉCART") + f" | {famille} | {len(x)} valeurs comparées, {int(hors.sum())} hors "
                  f"tolérance ({tol:g}{' relatif' if relatif else ''}), {int(vides.sum())} vides inattendues"
                  + (f" | pire {pire} publié {x.at[pire, 'p']:.4g} recalculé {x.at[pire, 'r']:.4g}" if pire is not None else ""))


# ------------------------------------------------------------------ référentiel et INSEE, lus sans le programme
def referentiel() -> dict:
    com = pd.DataFrame(json.loads((B / "ref_communes.json").read_text(encoding="utf-8")))
    com = com[com["type"] == "commune-actuelle"]
    epci = json.loads((B / "ref_epci.json").read_text(encoding="utf-8"))
    c2e = {m["code"]: e["code"] for e in epci for m in e.get("membres", [])}
    com = com.assign(epci=com["code"].map(c2e), pop=pd.to_numeric(com["population"], errors="coerce").fillna(0))
    return {"com": com, "pop": {"dep": com.groupby("departement")["pop"].sum(), "reg": com.groupby("region")["pop"].sum(),
                                "epci": com.dropna(subset=["epci"]).groupby("epci")["pop"].sum()}}


def insee(objets=("DEP", "REG", "EPCI")) -> dict:
    """Mesures du dossier complet de l'INSEE aux niveaux demandés, lues sur le fichier long (une ligne par territoire,
    tableau, mesure et année), année la plus récente de chaque mesure, mesures du même motif additionnées."""
    import pyarrow.compute as pc
    import pyarrow.dataset as ds
    tabs = sorted({t for t, _m in config.INSEE_MESURES.values()})
    d = ds.dataset(B / "insee_dossier_complet.parquet")
    t = d.to_table(columns=["GEO_OBJECT", "GEO", "TIME_PERIOD", "ID_TAB", "TAB_MEASURE", "OBS_VALUE"],
                   filter=pc.field("GEO_OBJECT").isin(list(objets)) & pc.field("ID_TAB").isin(tabs)).to_pandas()
    t = t.drop_duplicates(["GEO_OBJECT", "GEO", "ID_TAB", "TAB_MEASURE", "TIME_PERIOD"])
    out = {}
    for cle, (tab, motif) in config.INSEE_MESURES.items():
        s = t[(t["ID_TAB"] == tab) & t["TAB_MEASURE"].str.match(motif)]
        if s.empty:
            continue
        an = s["TIME_PERIOD"].max()
        s = s[s["TIME_PERIOD"] == an]
        out[cle] = s.groupby(["GEO_OBJECT", "GEO"])["OBS_VALUE"].sum(min_count=1)
    return out


NIV_INSEE = {"dep": "DEP", "reg": "REG", "epci": "EPCI"}


def mesure(I: dict, cle: str, niv: str) -> pd.Series:
    s = I.get(cle)
    if s is None:
        return pd.Series(dtype=float)
    try:
        return s.xs(NIV_INSEE[niv], level="GEO_OBJECT")
    except KeyError:
        return pd.Series(dtype=float)


# ------------------------------------------------------------------ 1. profil des populations (INSEE)
def profil(R: Path, I: dict, ref: dict):
    defs = [(c[0], c[2], c[3], c[4]) for c in config.CONTEXTE] + [(c[0], c[2], c[3], c[4]) for c in config.CONTEXTE_VULNERABILITE]
    for niv in ("dep", "reg", "epci"):
        pub = lire(R, f"contexte_{niv}.csv")
        if pub is None:
            continue
        pub = pub.set_index("code")
        for iid, unite, num, den in defs:
            # un indicateur que la source ne publie pas à ce niveau (minima sociaux par intercommunalité) n'a rien à comparer
            if iid not in pub or pub[iid].notna().sum() == 0:
                continue
            n = mesure(I, num, niv)
            if den is None:
                r = n
            elif iid == "densite_pop":
                r = n / mesure(I, den, niv)
            else:
                r = n / mesure(I, den, niv) * 100
            if r.empty:
                lignes.append(f"ÉCART | profil {iid} {niv} | mesure de l'INSEE introuvable")
                continue
            tol = .06 if unite == "%" else (1.0 if unite == "€" else .02)
            # intercommunalités, 1 % des territoires admis hors tolérance : intercommunalités nouvelles de la carte de
            # 2026 absentes du fichier de l'INSEE (reconstituées depuis leurs communes) ou au périmètre changé
            comparer(f"profil, {iid}, {niv} ({unite})", pub[iid], r.reindex(pub.index), tol,
                     relatif=unite not in ("%",), part_admise=.01 if niv == "epci" else 0.0)


# ------------------------------------------------------------------ 2. structures pour 100 000, dénominateur lu dans l'unité
def denominateur(unite: str, I: dict, ref: dict, niv: str) -> pd.Series:
    u = unite or ""
    if "moins de 15 ans" in u:
        return mesure(I, "pop0014", niv)
    if "80 ans et plus" in u:
        return mesure(I, "pop80p", niv)
    return ref["pop"][niv]


def facteur(unite: str) -> float:
    m = re.search(r"pour ([\d  ]+)", unite or "")
    return float(re.sub(r"\D", "", m.group(1))) if m else 1.0


def structures(R: Path, I: dict, ref: dict):
    l = lire(R, "lieux_soins.csv", dtype=str, usecols=["id_structure", "type", "epci", "dep", "reg"])
    sd = json.loads((R / "site_data.json").read_text(encoding="utf-8"))
    cat = {d["id"]: d for d in sd["contexte"]}
    # territoires où la mesure n'est pas publiée par règle (bases qui inscrivent moins de la moitié de ce que la SAE
    # déclare), vides attendus
    # (une seule limite « manque_sae » depuis le 30 octobre au soir, les anciennes limites par type restent lues)
    lim = sd.get("limites") or {}
    alias = sd.get("limites_alias") or {}
    manques = {}
    for k, v in lim.items():
        if k.startswith("manque_sae:"):
            manques.setdefault(k.split(":", 1)[1], set()).update(v.get("territoires") or {})
        elif k == "manque_sae":
            for ind, cle in alias.items():
                if cle == "manque_sae" and ind.startswith("lieux_"):
                    manques.setdefault(ind[len("lieux_"):], set()).update(v.get("territoires") or {})
    if l is None:
        return
    for niv in ("epci", "dep", "reg"):
        pub = lire(R, f"contexte_{niv}.csv")
        if pub is None:
            continue
        pub = pub.set_index("code")
        for col in [c for c in pub.columns if c.startswith("lieux_lieu_")]:
            tid, unite = col[len("lieux_"):], cat.get(col, {}).get("unite", "")
            n = l[l["type"] == tid].drop_duplicates("id_structure").groupby(niv).size()
            den = denominateur(unite, I, ref, niv)
            # pour les publics particuliers, la part de l'INSEE appliquée à la population du référentiel, comme le
            # libellé l'annonce (personnes de 80 ans et plus, enfants de moins de 15 ans)
            if den is not ref["pop"][niv]:
                den = ref["pop"][niv] * den / mesure(I, "pop", niv)
            r = n.reindex(pub.index).fillna(0) / den.reindex(pub.index) * facteur(unite)
            comparer(f"structures, {col}, {niv} ({unite})", pub[col], r, .02, relatif=True,
                     vides_attendus=pd.Index(sorted(
                         {k[4:] for k in manques.get(tid, set()) if k.startswith("reg:")} if niv == "reg"
                         else {k for k in manques.get(tid, set()) if not k.startswith("reg:")})))


# ------------------------------------------------------------------ 3. densités des professions
def densites(R: Path, ref: dict):
    for niv in ("dep", "reg", "epci"):
        e = lire(R, f"effectifs_{niv}_all.csv")
        if e is None:
            continue
        e = e.set_index("code")
        comparer(f"professions, population des {niv} (référentiel Etalab)", e["population"],
                 ref["pop"][niv].reindex(e.index), 0)
        for col in [c for c in e.columns if c.startswith("densite_")]:
            p = col[len("densite_"):]
            if f"n_{p}" in e:
                comparer(f"professions, {col}, {niv} (pour 10 000)", e[col], e[f"n_{p}"] / e["population"] * 1e4, .01,
                         relatif=True)


# ------------------------------------------------------------------ 4. SAE, depuis le bordereau brut
def sae(R: Path, I: dict, ref: dict):
    p = pd.read_csv(B / "sae" / "psy.csv", sep=";", encoding="latin-1", low_memory=False, dtype={"FI": str})
    i = pd.read_csv(B / "sae" / "id.csv", sep=";", encoding="latin-1", low_memory=False, dtype=str)
    i.columns = [c.lower() for c in i.columns]
    dep = i.drop_duplicates("fi").set_index("fi")["dep"].str.strip().replace(config.SAE_DEPARTEMENTS_OUTRE_MER)
    p["dep"] = p["FI"].map(dep)
    cat = {d["id"]: d for d in json.loads((R / "site_data.json").read_text(encoding="utf-8"))["contexte"]}
    pub = lire(R, "contexte_dep.csv")
    if pub is None:
        return
    pub = pub.set_index("code")
    for iid, dis, cols, _lab, unite, par, _e in config.SAE_INDICATEURS:
        if iid not in pub:
            continue
        x = p[p["DIS"] == dis]
        s = x[cols].apply(pd.to_numeric, errors="coerce").groupby(x["dep"]).sum(min_count=1).sum(axis=1, min_count=1)
        s = s.reindex(pub.index).fillna(0)
        den = ref["pop"]["dep"]
        if par == "moins15":
            den = den * mesure(I, "pop0014", "dep") / mesure(I, "pop", "dep")
        u = cat.get(iid, {}).get("unite", unite)
        comparer(f"SAE, {iid}, départements ({u})", pub[iid], s / den.reindex(pub.index) * facteur(u), .01, relatif=True)


# ------------------------------------------------------------------ 5. CAF, tous les départements et intercommunalités
def caf(R: Path, ref: dict):
    cat = {d["id"]: d for d in json.loads((R / "site_data.json").read_text(encoding="utf-8"))["contexte"]}
    champs = {"caf_aah": "indben_aah", "caf_aeeh": "indben_aeeh", "caf_rsa": "indnbp_rsa"}
    for niv, f, cle in (("dep", "caf_s_ben_dep.csv", "numdep"), ("epci", "caf_s_ben_epci_f.csv", "numepci")):
        brut = pd.read_csv(B / f, sep=";", dtype={cle: str}).set_index(cle)
        pub = lire(R, f"contexte_{niv}.csv")
        if pub is None:
            continue
        pub = pub.set_index("code")
        for iid, champ in champs.items():
            if iid not in pub or champ not in brut:
                continue
            u = cat.get(iid, {}).get("unite", "")
            fac = 100 if u.strip() == "%" else facteur(u)
            n = pd.to_numeric(brut[champ], errors="coerce")
            comparer(f"CAF, {iid}, {niv} ({u})", pub[iid], n.reindex(pub.index) / ref["pop"][niv].reindex(pub.index) * fac,
                     .002, relatif=True)


# ------------------------------------------------------------------ 6. Santé publique France (Odissé), valeurs reprises
def odisse(R: Path):
    pubs = {niv: lire(R, f"contexte_{niv}.csv") for niv in ("dep", "reg")}
    for f in sorted(B.glob("odisse_*.csv")):
        iid = f.stem[len("odisse_"):]
        b = pd.read_csv(f, sep=";", dtype=str)
        code = next((c for c in b.columns if re.fullmatch(r"(num_)?(departement|dep|new_dpt|dpt)", c.lower())), None)
        niv = "dep"
        if code is None:
            code, niv = next((c for c in b.columns if re.fullmatch(r"(nouvelles_)?(regions?|reg)", c.lower())), None), "reg"
        pub = pubs[niv]
        if pub is None or iid not in pub:
            continue
        pub = pub.set_index("code")
        val = next((c for c in b.columns if c not in ("annee", code) and not re.search(r"^ic_|_ic[bh]$|_inf$|_sup$|borne", c)), None)
        if code is None or val is None:
            continue
        b["_an"] = b["annee"].str[:4]
        b = b[b["_an"] == b["_an"].max()]
        # codes à trois caractères dans certains fichiers (« 001 », « 02A »), ramenés au code du département
        b[code] = b[code].str.strip().map(lambda c: c[1:] if len(c) == 3 and c.startswith("0") else c)
        r = pd.to_numeric(b.set_index(code)[val].str.replace(",", "."), errors="coerce")
        comparer(f"Santé publique France, {iid}, {'départements' if niv == 'dep' else 'régions'}", pub[iid],
                 r.reindex(pub.index), .051)


# ------------------------------------------------------------------ 7. inégalités entre territoires, formules refaites
def inegalites(R: Path):
    """Gini (courbe de Lorenz des professionnels rapportés à la population, territoires rangés par densité), Theil,
    médiane, déciles et part de la population sans professionnel, recalculés depuis les effectifs publiés."""
    pub = lire(R, "inegalites.csv")
    if pub is None:
        return
    pub = pub[pub["mode"] == "all"].set_index(["niveau", "prof"])
    for niv in ("epci", "dep", "reg"):
        e = lire(R, f"effectifs_{niv}_all.csv")
        if e is None:
            continue
        e = e[e["population"] > 0]
        pop = e["population"].astype(float).to_numpy()
        ecarts = {k: [] for k in ("gini", "theil", "mediane", "p10", "p90", "part_population_sans_professionnel",
                                  "densite_nationale")}
        for col in [c for c in e.columns if c.startswith("n_")]:
            p = col[2:]
            if (niv, p) not in pub.index:
                continue
            n = e[col].astype(float).to_numpy()
            if n.sum() == 0:
                continue
            d = n / pop * 1e4
            o = np.argsort(d, kind="stable")
            x = np.r_[0, np.cumsum(pop[o])] / pop.sum()
            y = np.r_[0, np.cumsum(n[o])] / n.sum()
            gini = float(1 - ((x[1:] - x[:-1]) * (y[1:] + y[:-1])).sum())
            s_, p_ = n / n.sum(), pop / pop.sum()
            theil_ = float((s_[s_ > 0] * np.log(s_[s_ > 0] / p_[s_ > 0])).sum())
            r = {"gini": gini, "theil": theil_, "mediane": float(np.median(d)), "p10": float(np.quantile(d, .1)),
                 "p90": float(np.quantile(d, .9)), "part_population_sans_professionnel": float(pop[n == 0].sum() / pop.sum()),
                 "densite_nationale": float(n.sum() / pop.sum() * 1e4)}
            # fichiers publiés à six chiffres significatifs, écart relatif
            for k, v in r.items():
                ecarts[k].append((abs(float(pub.at[(niv, p), k]) - v) / max(abs(v), 1e-3), p))
        for k, v in ecarts.items():
            if not v:
                continue
            m, p = max(v)
            lignes.append(("ok   " if m <= 1e-4 else "ÉCART") + f" | inégalités, {k}, {niv} | {len(v)} professions, écart "
                          f"relatif maximal {m:.2g} ({p})")


# ------------------------------------------------------------------ 8. écart à l'effectif attendu, cohérence interne
def attendu(R: Path):
    """L'effectif attendu d'un modèle de Poisson avec constante redonne, sommé sur les territoires, l'effectif observé.
    Les colonnes dérivées (pour 10 000, rapport, écart) se recalculent depuis l'effectif, l'attendu et la population."""
    a = lire(R, "ecarts_attendu.csv")
    if a is None:
        return
    for p, g in a.groupby("prof"):
        tot = abs(g["effectif_attendu"].sum() / g["effectif"].sum() - 1)
        # fichier publié à six chiffres significatifs, écart rapporté à la valeur
        rel = lambda a, b: ((a - b).abs() / b.abs().clip(lower=1e-3)).max()  # noqa: E731
        d = max(rel(g["observe"], g["effectif"] / g["pop"] * 1e4), rel(g["attendu"], g["effectif_attendu"] / g["pop"] * 1e4),
                rel(g["rapport"], g["effectif"] / g["effectif_attendu"]),
                ((g["manque"] - (g["effectif_attendu"] - g["effectif"])).abs()
                 / g["effectif_attendu"].abs().clip(lower=1)).max())
        lignes.append(("ok   " if tot < .01 and d < 1e-3 else "ÉCART") + f" | effectif attendu, {p} | {len(g)} "
                      f"intercommunalités, somme des attendus face aux observés {tot:.2%}, colonnes dérivées écart maximal {d:.2g}")


# ------------------------------------------------------------------ 9. accessibilité et distances, des communes au territoire
def accessibilite(R: Path):
    """Valeurs nationales de l'accessibilité aux professionnels recalculées depuis le fichier des communes (population
    à plus de 5, 10, 20 et 30 km, distance moyenne pondérée par la population)."""
    c, f = lire(R, "accessibilite_communes.csv"), lire(R, "accessibilite.csv")
    if c is None or f is None:
        return
    f = f.set_index("prof")
    for p, g in c.groupby("prof"):
        if p not in f.index:
            continue
        # un habitant sans professionnel sur son territoire (distance vide) compte au-delà de chaque seuil
        w = g["population"].astype(float)
        dk = g["distance_km"].fillna(np.inf)
        for seuil in (5, 10, 20, 30):
            col = f"part_population_a_plus_de_{seuil}_km"
            if col in f:
                note_ = float((w[dk > seuil].sum()) / w.sum())
                comparer(f"accessibilité, {p}, {col}", pd.Series({"FR": f.at[p, col]}), pd.Series({"FR": note_}), .002)
        ok = g["distance_km"].notna()
        comparer(f"accessibilité, {p}, distance moyenne (km)", pd.Series({"FR": f.at[p, "distance_moyenne_km"]}),
                 pd.Series({"FR": float((w[ok] * g.loc[ok, "distance_km"]).sum() / w[ok].sum())}), .02)


def distances(R: Path, ref: dict):
    """Part des habitants à plus de 20 et 30 km de la structure la plus proche, par département, recalculée depuis
    les distances des communes publiées et la population du référentiel (les communes sans distance publiée, dont
    celles des départements sans mesure, sont laissées de côté)."""
    c, d = lire(R, "distances_lieux_communes.csv"), lire(R, "distances_lieux_dep.csv")
    if c is None or d is None:
        return
    pop = ref["com"].set_index("code")["pop"]
    c = c.set_index("code")
    c["pop"] = pop.reindex(c.index).fillna(0).to_numpy()
    for col in [k for k in c.columns if k.startswith("dist_")]:
        tid = col[5:]
        # distances des communes publiées au dixième de kilomètre, une commune proche du seuil peut tomber d'un côté
        # ou de l'autre : la part publiée doit se tenir entre les deux bornes (communes à moins de 0,05 km du seuil
        # comptées au-delà, puis en deçà) ; une distance vide compte au-delà (aucune structure sur le territoire)
        x = c[[col, "dep", "pop"]].dropna(subset=["dep"]).assign(**{col: lambda t: t[col].fillna(np.inf)})
        for seuil in (20, 30):
            g = x.groupby("dep")
            haut = g.apply(lambda t: t.loc[t[col] > seuil - .05, "pop"].sum() / t["pop"].sum() if t["pop"].sum() else np.nan)
            bas = g.apply(lambda t: t.loc[t[col] > seuil + .05, "pop"].sum() / t["pop"].sum() if t["pop"].sum() else np.nan)
            pub = d[d["type"] == tid].set_index("code")[f"part_plus_{seuil}_km"]
            v = pd.DataFrame({"p": pub, "bas": bas.reindex(pub.index), "haut": haut.reindex(pub.index)}).dropna()
            hors = (v["p"] < v["bas"] - .001) | (v["p"] > v["haut"] + .001)
            lignes.append(("ok   " if not hors.any() and len(v) else "ÉCART") + f" | distances, {tid}, part à plus de "
                          f"{seuil} km, départements | {len(v)} comparés, {int(hors.sum())} hors des bornes de l'arrondi"
                          + (f", par exemple {hors.idxmax()} publié {v.at[hors.idxmax(), 'p']:.4g} bornes "
                             f"{v.at[hors.idxmax(), 'bas']:.4g} à {v.at[hors.idxmax(), 'haut']:.4g}" if hors.any() else ""))


# ------------------------------------------------------------------ 10. Assurance Maladie, ALD et prises en charge
def ald(R: Path):
    """Taux standardisés des ALD, classeur départemental de l'Assurance Maladie (tableau VIII), lu ici sans le
    programme : en-tête sur la deuxième ligne, une colonne par affection « (ALDn) »."""
    pub = lire(R, "contexte_dep.csv")
    f = B / "ald_departements.xls"
    if pub is None or not f.exists():
        return
    pub = pub.set_index("code")
    x = pd.ExcelFile(f)
    t = x.parse(next(n for n in x.sheet_names if "VIII" in n), header=None)
    entete = [str(h) for h in t.iloc[1]]
    j_code = next(j for j, h in enumerate(entete) if "code" in h.lower())
    corps = t.iloc[2:]
    corps = corps[corps.iloc[:, j_code].astype(str).str.fullmatch(r"\d[\dAB]\d?")]
    codes = corps.iloc[:, j_code].astype(str).str.zfill(2).to_numpy()
    for j, h in enumerate(entete):
        m = re.search(r"\(ALD\s*(\d+)\)\s*$", h)
        if m and f"ald_{m.group(1)}" in pub:
            r = pd.Series(pd.to_numeric(corps.iloc[:, j], errors="coerce").to_numpy(), index=codes)
            # Mayotte, données non exhaustives d'après l'Assurance Maladie, non publiée en indicateur
            comparer(f"Assurance Maladie, ald_{m.group(1)}, départements (tableau VIII)", pub[f"ald_{m.group(1)}"],
                     r.reindex(pub.index), .51, vides_attendus=pd.Index(["976"]))


def pathologies(R: Path):
    """Prévalence standardisée sur l'âge des prises en charge pour troubles psychiques et des traitements
    psychotropes, méthode directe sur la structure d'âge de la France (ligne France du fichier, 999 et 99), refaite
    pour les départements où aucune classe d'âge n'est masquée par le secret statistique."""
    pub = lire(R, "contexte_dep_odbl.csv")
    f = B / "ameli_pathologies_psy.csv"
    if pub is None or not f.exists():
        return
    pub = pub.set_index("code")
    d = pd.read_csv(f, sep=";", dtype=str)
    d = d[d["annee"] == d["annee"].max()]
    for c in ("ntop", "npop"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    for top, iid, _lab, _e in config.AMELI_INDICATEURS:
        if iid not in pub:
            continue
        x = d[d["top"] == top]
        fr = x[(x["dept"] == "999") & (x["region"] == "99") & (x["cla_age_5"] != "tsage")].set_index("cla_age_5")["npop"]
        w = fr / fr.sum()
        dep = x[(x["dept"] != "999") & (x["cla_age_5"] != "tsage")]
        cas = dep.pivot_table(index="dept", columns="cla_age_5", values="ntop", aggfunc="sum").reindex(columns=w.index)
        pop = dep.pivot_table(index="dept", columns="cla_age_5", values="npop", aggfunc="sum").reindex(columns=w.index)
        complets = cas.notna().all(axis=1) & pop.notna().all(axis=1) & (pop > 0).all(axis=1)
        r = ((cas[complets] / pop[complets]) * w).sum(axis=1) * 100
        # vides attendus, Mayotte (régime distinct) et les départements dont les classes d'âge, arrondies à la
        # dizaine, couvrent moins de 95 % des patients (seuil de publication)
        tot = x[(x["dept"] != "999") & (x["cla_age_5"] == "tsage")].groupby("dept")["ntop"].sum()
        couv = cas.sum(axis=1) / tot.reindex(cas.index)
        attendus = pd.Index(list(config.AMELI_DEPARTEMENTS_EXCLUS) + list(couv.index[couv < config.AMELI_COUVERTURE_MIN]))
        comparer(f"Assurance Maladie, {iid}, départements sans classe d'âge masquée (standardisation directe)",
                 pub[iid].reindex(r.index), r, .001, vides_attendus=attendus)


# ------------------------------------------------------------------ 11. DREES, indicateurs sociaux et âge des professionnels
def drees_isd(R: Path):
    """Aide sociale à l'enfance et handicap, dernière année de chaque indicateur des fichiers de la DREES, multipliée
    par le facteur écrit dans la définition (part en %, ou valeur déjà pour 1 000)."""
    pub = lire(R, "contexte_dep.csv")
    if pub is None:
        return
    pub = pub.set_index("code")
    for jeu, ind, iid, _lab, unite, fac, _fam, _e in config.DREES_ISD:
        f = B / f"drees_isd_{jeu.split('_')[0]}.csv"
        if iid not in pub or not f.exists():
            continue
        d = pd.read_csv(f, sep=";", dtype=str)
        # départements seulement (« 1000 » porte les valeurs régionales, « 20R » la Corse entière)
        cd = d["code_dep"].fillna("").str.strip()
        d = d[(d["id_indicateur"] == ind) & cd.str.fullmatch(r"\d{2}|2A|2B|97\d")]
        d = d[d["annee"] == d["annee"].max()]
        dbl = d[d.duplicated("code_dep", keep=False)]
        if len(dbl) and dbl.groupby("code_dep")["value"].nunique().gt(1).any():
            lignes.append(f"ÉCART | DREES, {iid} | valeurs différentes pour un même département la même année, "
                          f"{sorted(dbl['code_dep'].unique())[:5]}")
        d = d.drop_duplicates("code_dep")
        r = pd.to_numeric(d.set_index(d["code_dep"].str.strip())["value"], errors="coerce") * fac
        comparer(f"DREES, {iid}, départements ({unite})", pub[iid], r.reindex(pub.index), .006)


def _simple_age(v) -> str:
    return unicodedata.normalize("NFKD", str(v or "")).encode("ascii", "ignore").decode().lower().strip()


def _borne_age(t) -> int | None:
    t = _simple_age(t)
    if "ensemble" in t:
        return None
    t = re.sub(r"^\s*\d+\s*-\s*", "", t)
    m = re.findall(r"\d+", t)
    if not m:
        return None
    return 0 if "moins" in t else int(m[0])


def drees_age(R: Path, fichiers=("chirurgiens_dentistes_rpps", "sages_femmes_rpps", "pharmaciens_rpps")):
    """Part des 60 ans et plus par département pour quelques professions, depuis les classeurs de la DREES
    (feuille des effectifs, toutes les autres dimensions à « Ensemble », dernière année)."""
    import openpyxl
    pub = lire(R, "contexte_dep.csv")
    if pub is None:
        return
    pub = pub.set_index("code")
    ids = {"chirurgiens_dentistes_rpps": "age60_chirurgien_dentiste", "sages_femmes_rpps": "age60_sage_femme",
           "pharmaciens_rpps": "age60_pharmacien"}
    for nom in fichiers:
        f = B / "drees_demographie" / f"{nom}.xlsx"
        iid = ids[nom]
        if not f.exists() or iid not in pub:
            continue
        wb = openpyxl.load_workbook(f, read_only=True)
        ws = next(w for w in wb.worksheets if _simple_age(w.title).startswith("effectif"))
        it = ws.iter_rows(values_only=True)
        h = [_simple_age(x) for x in next(it)]
        an = max(int(m.group(1)) for x in h if (m := re.match(r"effectif[ _](\d{4})$", x or "")))
        j_an = next(j for j, x in enumerate(h) if re.match(rf"effectif[ _]{an}$", x or ""))
        j_dep = next(j for j, x in enumerate(h) if x.startswith("departement"))
        j_age = next(j for j, x in enumerate(h) if (x or "").startswith("tranche"))
        autres = [j for j, x in enumerate(h) if x and not x.startswith("effectif") and j not in (j_dep, j_age)
                  and not x.startswith(("region", "territoire"))]
        tot, plus = {}, {}
        for r in it:
            if not r or r[j_dep] is None:
                continue
            if not all(("ensemble" in _simple_age(r[j]) or "france entiere" in _simple_age(r[j])) for j in autres):
                continue
            m = re.match(r"^\s*(\w{2,3})\s*-", str(r[j_dep]))
            if not m:
                continue
            c = m.group(1).upper()
            c = c[1:] if len(c) == 3 and c.startswith("0") else c
            v = pd.to_numeric(r[j_an], errors="coerce")
            b = _borne_age(r[j_age])
            if b is None and "ensemble" in _simple_age(r[j_age]):
                tot[c] = v
            elif b is not None and b >= 60:
                plus[c] = plus.get(c, 0) + (v if v == v else 0)
        wb.close()
        t = pd.Series(tot, dtype=float)
        rec = pd.Series({c: plus.get(c, 0) / t[c] * 100 for c in t.index if t[c] > 0}, dtype=float)
        comparer(f"DREES, {iid}, départements (tranches d'âge, {an})", pub[iid], rec.reindex(pub.index), .06)


# ------------------------------------------------------------------ 12. cohérence entre site_data.json et les CSV
def coherence(R: Path):
    """Valeurs du profil des territoires et effectifs des professions identiques entre site_data.json (atlas,
    Explorer) et les CSV publiés, aux trois niveaux. site_data.json arrondit à deux décimales."""
    sd = json.loads((R / "site_data.json").read_text(encoding="utf-8"))
    ids = [d["id"] for d in sd["contexte"]]
    for niv in ("epci", "dep", "reg"):
        bloc = sd["niveaux"].get(niv)
        if not bloc:
            continue
        codes = [u["c"] for u in bloc["units"]]
        x = pd.DataFrame([u.get("x") or [None] * len(ids) for u in bloc["units"]], index=codes, columns=ids)
        parts = [t.set_index("code") for t in (lire(R, f"contexte_{niv}.csv"), lire(R, f"contexte_{niv}_odbl.csv"))
                 if t is not None]
        csv_ = pd.concat(parts, axis=1)
        csv_ = csv_.loc[:, ~csv_.columns.duplicated()]
        commun = [c for c in ids if c in csv_.columns]
        a = x[commun].apply(pd.to_numeric, errors="coerce")
        # comparaison au CSV non arrondi, à l'arrondi près de site_data.json (deux décimales, ou quatre chiffres
        # significatifs pour les grandes valeurs), 13,675 km dans le CSV et 13,67 dans l'atlas ne sont pas un écart
        b = csv_.reindex(codes)[commun].apply(pd.to_numeric, errors="coerce")
        diff = (a - b).abs() - (.0005 * b.abs())
        n_val = int(a.notna().sum().sum())
        hors = int((diff > .0051).sum().sum())
        vides = int((a.isna() & b.notna()).sum().sum() + (a.notna() & b.isna()).sum().sum())
        lignes.append(("ok   " if not hors and not vides else "ÉCART") + f" | cohérence site_data.json et contexte_{niv}.csv | "
                      f"{n_val} valeurs, {hors} différentes, {vides} présentes d'un seul côté")
        e = lire(R, f"effectifs_{niv}_all.csv")
        if e is not None:
            e = e.set_index("code").reindex(codes)
            ecarts = sum(int((pd.Series(v["all"], index=codes) != e[f"n_{p}"].fillna(0)).sum())
                         for p, v in bloc["n"].items() if f"n_{p}" in e)
            lignes.append(("ok   " if not ecarts else "ÉCART") + f" | cohérence des effectifs, site_data.json et "
                          f"effectifs_{niv}_all.csv | {len(bloc['n'])} professions, {ecarts} effectifs différents")


# ------------------------------------------------------------------ voie légère (descripteurs de complements/)
def _nom_colonne(colonnes, motif) -> str | None:
    """Colonne nommée par le descripteur, par son nom exact ou par le motif écrit, sans le code du programme."""
    for m in (motif if isinstance(motif, list) else [motif]):
        nu = m.strip("^$")
        if m in colonnes or nu in colonnes:
            return m if m in colonnes else nu
        trouve = [c for c in colonnes if re.search(m, str(c).lower())]
        if trouve:
            return trouve[0]
    return None


def _code_territoire(s: pd.Series, niv: str) -> pd.Series:
    s = s.astype(str).str.strip().str.upper().str.replace(r"\.0$", "", regex=True)
    if niv == "dep":
        s = s.where(~(s.str.len().eq(3) & s.str.startswith("0")), s.str[1:])
        return s.where(s.str.len() != 1, s.str.zfill(2))
    return s.str.zfill(5 if niv == "com" else 2)


def voie_legere(R: Path, ref: dict, brouillons: bool = False):
    """Chaque indicateur des descripteurs actifs de la voie légère (version 2, champ « etat »), refait depuis le fichier
    d'origine en cache avec pandas seul (filtre, dernière année, secret, code du territoire, somme ou moyenne), comparé
    au fichier publié, avec ses niveaux supérieurs quand il s'agrège et ses dérivés (rapport de deux indicateurs
    publiés). Les brouillons ne sont contrôlés que sur les résultats d'une exécution de contrôle des brouillons."""
    vus = 0
    for f in sorted((RACINE / "complements").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("etat") not in ("actif", "brouillon") or (d["etat"] == "brouillon" and not brouillons):
            continue
        brut = config.DONNEES / "complements" / (d.get("fichier") or f"{d['id']}.csv")
        if not brut.exists():
            lignes.append(f"ÉCART | voie légère, {d['id']} | fichier d'origine absent du cache")
            continue
        enc = d.get("encodage", "utf-8-sig")
        tete = brut.read_text(encoding=enc, errors="replace").split("\n", 1)[0]
        sep = d.get("separateur") or max(";,\t|", key=tete.count)
        x = pd.read_csv(brut, sep=sep, dtype=str, encoding=enc, keep_default_na=False)
        for motif, v in (d.get("filtre") or {}).items():
            x = x[x[_nom_colonne(x.columns, motif)].isin([str(a) for a in (v if isinstance(v, list) else [v])])]
        cols, niv = d.get("colonnes") or {}, d["niveau"]
        if niv == "fra":
            continue
        x = x.assign(_code=_code_territoire(x[_nom_colonne(x.columns, cols.get("code") or d.get("colonne_code"))], niv),
                     _an=x[_nom_colonne(x.columns, cols["annee"])].str[:4] if cols.get("annee") else "")
        odbl = "odbl" in str(d.get("licence", "")).lower()
        pubs = {n: lire(R, f"contexte_{n}{'_odbl' if odbl else ''}.csv") for n in ("com", "epci", "dep", "reg")}
        secret = {str(s) for s in d.get("secret") or []}
        for ind in d["indicateurs"]:
            col = _nom_colonne(x.columns, ind["colonne"])
            v = pd.to_numeric(x[col].where(~x[col].isin(secret)).str.replace(",", ".").str.replace(" ", ""),
                              errors="coerce")
            y = x.assign(_v=v).dropna(subset=["_v"])
            if cols.get("annee"):
                y = y[y["_an"] == (y["_an"].max() if d.get("annee", "derniere") == "derniere" else str(d["annee"]))]
            agr = ind["agregation"]
            rec = y.groupby("_code")["_v"].sum() if agr == "somme" else y.groupby("_code")["_v"].mean()
            pub = pubs[niv]
            if pub is None or ind["id"] not in pub:
                lignes.append(f"ÉCART | voie légère, {ind['id']} | absent de contexte_{niv}.csv")
                continue
            p = pub.set_index("code")[ind["id"]]
            fac = (1e4 / ref["pop"][niv]) if ind.get("pour_10000_habitants") and niv in ref["pop"] else 1
            r_ = (rec * fac).reindex(p.index)
            comparer(f"voie légère, {ind['id']} ({niv})", p, r_, 1e-6, relatif=True)
            vus += 1
            if agr in ("somme", "moyenne") and niv == "dep" and pubs["reg"] is not None and ind["id"] in pubs["reg"]:
                d2r = ref["com"].drop_duplicates("departement").set_index("departement")["region"]
                t = pd.DataFrame({"v": rec}).assign(reg=lambda z: z.index.map(d2r), pop=lambda z: z.index.map(ref["pop"]["dep"]))
                complets = set(d2r.index) - set(rec.index)
                incomplets = set(d2r[d2r.index.isin(complets)])
                t = t[~t["reg"].isin(incomplets)]
                r2 = t.groupby("reg")["v"].sum() if agr == "somme" else \
                    (t["v"] * t["pop"]).groupby(t["reg"]).sum() / t["pop"].groupby(t["reg"]).sum()
                p2 = pubs["reg"].set_index("code")[ind["id"]]
                comparer(f"voie légère, {ind['id']} (reg)", p2, r2.reindex(p2.index), 1e-6, relatif=True,
                         vides_attendus=pd.Index(sorted(incomplets)))
        for dv in d.get("derives") or []:
            for n, pub in pubs.items():
                if pub is not None and {dv["id"], dv["numerateur"], dv["denominateur"]} <= set(pub.columns):
                    q = pub.set_index("code")
                    comparer(f"voie légère, dérivé {dv['id']} ({n})", q[dv["id"]],
                             q[dv["numerateur"]] / q[dv["denominateur"]] * float(dv.get("facteur", 1)), 1e-4, relatif=True)
    lignes.append(f"info  | voie légère, {vus} indicateur(s) de descripteurs contrôlé(s)"
                  + (" (brouillons compris)" if brouillons else ""))


def tout(R: Path | None = None) -> list[str]:
    R = R or dernier()
    lignes.append(f"info  | résultats contrôlés, {R.name}")
    ref = referentiel()
    densites(R, ref)
    inegalites(R)
    attendu(R)
    accessibilite(R)
    distances(R, ref)
    caf(R, ref)
    odisse(R)
    ald(R)
    pathologies(R)
    drees_isd(R)
    drees_age(R)
    coherence(R)
    I = insee()
    profil(R, I, ref)
    structures(R, I, ref)
    sae(R, I, ref)
    voie_legere(R, ref, brouillons="brouillons" in R.parts)
    return lignes


if __name__ == "__main__":
    res = tout(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    print("\n".join(res))
    sys.exit(1 if any(x.startswith("ÉCART") for x in res) else 0)
