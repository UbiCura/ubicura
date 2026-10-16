"""Contrôle indépendant de chiffres publiés, recalculés depuis les fichiers bruts par un autre code que celui du
programme (lecture directe des fichiers, calculs refaits avec numpy et scipy). Porte sur les derniers résultats.

    python outils/controle_independant.py

Temps de trajet recalculés depuis le fichier brut de l'INSEE pour la Corse (59 Mo, téléchargé dans un dossier
temporaire puis supprimé), lecture de l'APL comparée à une lecture indépendante du classeur de la DREES, ALD comparées
aux cellules du classeur de l'Assurance Maladie, CAF et populations comparées aux fichiers bruts, croisements entre
indicateurs et régressions recalculés. Chaque ligne dit ok ou ÉCART, le code de sortie vaut 1 s'il y a un écart."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import stats

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from pipeline import config  # noqa: E402
from pipeline.sources import apl as A  # noqa: E402
from pipeline.util import _session  # noqa: E402

R = sorted(p for p in (RACINE / "resultats").glob("20*") if (p / "site_data.json").exists())[-1]
B = RACINE / "donnees" / "brut"
lignes = []


def note(quoi, publie, recalcule, tol):
    ok = (publie is not None and recalcule is not None and np.isfinite(publie) and np.isfinite(recalcule)
          and abs(publie - recalcule) <= tol)
    lignes.append(("ok   " if ok else "ÉCART") + f" | {quoi} | publié {publie} | recalculé {recalcule} | tolérance {tol}")


def lire(f, **k):
    return pd.read_csv(R / f, sep=";", decimal=",", encoding="utf-8-sig", **k)


# ------------------------------------------------------------------ 1. temps de trajet, Corse, depuis le fichier brut
tmp = Path(tempfile.mkdtemp(prefix="controle_"))
try:
    meta = json.loads((B / "acces_route" / "acces_2025_reg94.meta.json").read_text(encoding="utf-8"))
    with _session().get(meta["url"], stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp / "reg94.parquet", "wb") as f:
            for b in r.iter_content(1 << 20):
                f.write(b)
    raw = pq.read_table(tmp / "reg94.parquet", columns=["depcom", "typeeq_id", "duree", "pop"]).to_pandas()
finally:
    shutil.rmtree(tmp, ignore_errors=True)
raw["depcom"] = raw["depcom"].astype(str)
resume = pd.read_csv(B / "acces_route" / "acces_2025_reg94.csv", dtype={"depcom": str})
for com in ["2A004", "2B033", "2B096"]:
    for eq in ["D109", "D265", "D250"]:
        d = raw[(raw["depcom"] == com) & (raw["typeeq_id"] == eq)]
        ok = d["duree"].notna()
        moy = (d.loc[ok, "pop"] * d.loc[ok, "duree"]).sum() / d.loc[ok, "pop"].sum()
        p20 = d.loc[ok & (d["duree"] > 20), "pop"].sum() / d.loc[ok, "pop"].sum()
        r = resume[(resume["depcom"] == com) & (resume["typeeq_id"] == eq)]
        if r.empty:
            lignes.append(f"ÉCART | temps {com} {eq} absent du résumé")
            continue
        r = r.iloc[0]
        note(f"temps moyen {com} {eq} (min)", round(r["pd"] / r["pop_calcule"], 3), round(moy, 3), .001)
        note(f"part à plus de 20 min {com} {eq}", round(r["sup_20"] / r["pop_calcule"], 4), round(p20, 4), .0001)
ta = lire("temps_acces.csv", dtype={"code": str})
ids = {"D109": "psychiatrie_ambulatoire", "D265": "generaliste_liberal", "D250": "psychologue_liberal", "D269": "psychiatre_liberal"}
for dep in ["2A", "2B"]:
    for eq, ident in ids.items():
        d = raw[raw["depcom"].str.startswith(dep) & (raw["typeeq_id"] == eq) & raw["duree"].notna()]
        moy = (d["pop"] * d["duree"]).sum() / d["pop"].sum()
        s = d.sort_values("duree")   # médiane exacte pondérée, sans regroupement par minute
        c = s["pop"].cumsum()
        med = s.loc[c >= c.iloc[-1] / 2, "duree"].iloc[0]
        p = ta[(ta["niveau"] == "dep") & (ta["code"] == dep) & (ta["equipement"] == ident)]
        if p.empty:
            lignes.append(f"ÉCART | temps_acces dep {dep} {ident} absent")
            continue
        p = p.iloc[0]
        note(f"temps moyen {dep} {ident}", round(p["temps_moyen_min"], 2), round(moy, 2), .02)
        note(f"temps médian {dep} {ident} (publié par tranches d'une minute)", round(p["temps_median_min"], 2), round(med, 2), 1.0)

# ------------------------------------------------------------------ 2. APL, lecture du classeur de la DREES
for prof in ["medecin_generaliste", "infirmier"]:
    f = B / f"apl_{prof}.xlsx"
    prog, annee, _u = A._lire(f)
    xl = pd.ExcelFile(f)
    trouve = False
    # lecture indépendante, feuille du millésime retenu, colonnes repérées par leur intitulé
    for sh in sorted(xl.sheet_names, key=lambda n: str(annee) not in n):
        brut = xl.parse(sh, header=None, dtype=str)
        for i in range(min(15, len(brut))):
            ent = [str(x).lower() for x in brut.iloc[i].tolist()]
            if any("code" in e and "commune" in e for e in ent) and any("apl" in e for e in ent):
                t = xl.parse(sh, header=i, dtype=str)
                cc = next(c for c in t.columns if "code" in str(c).lower() and "commune" in str(c).lower())
                ca = [c for c in t.columns if "apl" in str(c).lower()]
                t = t[[cc] + ca].dropna(subset=[cc])
                t["v"] = pd.to_numeric(t[ca[0]].astype(str).str.replace(",", "."), errors="coerce")
                m = prog.merge(t.rename(columns={cc: "code"})[["code", "v"]], on="code", how="inner")
                ecart = (m["apl"] - m["v"]).abs().max()
                lignes.append(("ok   " if ecart < 1e-6 and len(m) > 30000 else "ÉCART") +
                              f" | APL {prof} {annee}, feuille « {sh} », {len(m)} communes comparées, écart maximal {ecart}")
                trouve = True
                break
        if trouve:
            break
    if not trouve:
        lignes.append(f"ÉCART | APL {prof}, structure du classeur non reconnue par le contrôle")

# ------------------------------------------------------------------ 3. ALD, cellules du classeur de l'Assurance Maladie
ald = lire("ald_departements.csv", dtype={"code": str})
t = pd.read_excel(B / "ald_departements.xls", sheet_name=0, header=1, dtype={"Code département": str})
t["Code département"] = t["Code département"].astype(str).str.strip()
for code_dep, n_ald in [("75", 23), ("13", 23), ("59", 8), ("2A", 15), ("971", 23)]:
    col = [c for c in t.columns if f"(ALD{n_ald})" in str(c)][0]
    brut = pd.to_numeric(t.loc[t["Code département"] == code_dep, col], errors="coerce").sum()
    p = ald[(ald["code"] == code_dep) & (ald["ald"] == n_ald)]["effectif"]
    note(f"ALD {n_ald} dép. {code_dep}, effectif", float(p.iloc[0]) if len(p) else None, float(brut), 0)
col = [c for c in t.columns if "(ALD23)" in str(c)][0]
dep = t["Code département"].str.match(r"^(\d\d|2A|2B|97\d)$")
note("ALD 23, somme des départements", float(ald[ald["ald"] == 23]["effectif"].sum()),
     float(pd.to_numeric(t.loc[dep, col], errors="coerce").sum()), 0)

# ------------------------------------------------------------------ 4. CAF, fichier brut départemental et population
caf = pd.read_csv(B / "caf_s_ben_dep.csv", sep=";", dtype={"numdep": str})
pub = lire("allocataires_caf.csv", dtype={"code": str})
com = json.loads((B / "ref_communes.json").read_text(encoding="utf-8"))
popdep = pd.DataFrame([c for c in com if c.get("type", "commune-actuelle") == "commune-actuelle"]).groupby("departement")["population"].sum()
for dep in ["59", "93", "23"]:
    brut = pd.to_numeric(caf.loc[caf["numdep"] == dep, "indben_aah"], errors="coerce").sum()
    p = pub[(pub["niveau"] == "dep") & (pub["code"] == dep) & (pub["indicateur"] == "caf_aah")].iloc[0]
    note(f"CAF AAH dép. {dep}, effectif", float(p["effectif"]), float(brut), 0)
    note(f"CAF AAH dép. {dep}, pour 1 000 habitants", round(p["valeur"], 3), round(brut / p["population"] * 1000, 3), .0015)
    note(f"population dép. {dep} utilisée pour la CAF (référentiel Etalab)", float(p["population"]), float(popdep.get(dep, np.nan)), 0)

# ------------------------------------------------------------------ 5. évolution, populations de l'INSEE
est = pd.read_csv(B / "insee_estimations_dep.csv", sep=";", dtype={"code": str})
evo = lire("evolution_offre.csv", dtype={"code": str})
for an in [2016, 2024]:
    for dep in ["FR", "75", "23"]:
        p = evo[(evo["code"] == dep) & (evo["annee"] == an)]
        if p.empty:
            continue
        brut = est.loc[est["annee"] == an, "population"].sum() if dep == "FR" else \
            est.loc[(est["annee"] == an) & (est["code"] == dep), "population"].sum()
        note(f"évolution, population {dep} {an} (INSEE, estimations)", float(p["population"].iloc[0]), float(brut), 1)
e = evo.dropna(subset=["effectif", "population", "densite"])
note("évolution, densité = effectif / population x 10 000 (toutes les lignes)", 0.0,
     round(float((e["effectif"] / e["population"] * 1e4 - e["densite"]).abs().max()), 4), .001)

# ------------------------------------------------------------------ 6. croisements entre indicateurs et régressions
ctx = lire("contexte_dep.csv", dtype={"code": str}).set_index("code")
odbl = R / "contexte_dep_odbl.csv"
if odbl.exists():
    ctx = ctx.join(pd.read_csv(odbl, sep=";", decimal=",", encoding="utf-8-sig", dtype={"code": str}).set_index("code"),
                   rsuffix="_o")
cr = lire("croisements_indicateurs.csv")
for a, b in [("suicides", "hospit_gestes_auto_infliges"), ("suicides", "taux_pauvrete"), ("caf_aah", "ald_23")]:
    row = cr[((cr["variable_a"] == a) & (cr["variable_b"] == b)) | ((cr["variable_a"] == b) & (cr["variable_b"] == a))]
    if row.empty or a not in ctx or b not in ctx:
        lignes.append(f"ÉCART | croisement {a} et {b} absent")
        continue
    d = ctx[[a, b]].dropna().drop(index=config.DEPARTEMENTS_EXCLUS_CROISEMENTS, errors="ignore")
    note(f"croisement {a} et {b}, rho", round(row["rho"].iloc[0], 4), round(stats.spearmanr(d[a], d[b])[0], 4), .0005)
    note(f"croisement {a} et {b}, départements", float(row["departements"].iloc[0]), float(len(d)), 0)
    d2 = d.drop(index=[i for i in config.DEPS_ILE_DE_FRANCE if i in d.index])
    note(f"croisement {a} et {b}, rho sans l'Île-de-France", round(row["rho_sans_ile_de_france"].iloc[0], 4),
         round(stats.spearmanr(d2[a], d2[b])[0], 4), .0005)

reg = lire("regressions_indicateurs.csv")
X_ = list(config.REGRESSION_EXPLICATIVES)
for res in ["suicides", "hospit_gestes_auto_infliges"]:
    hexa = [i for i in ctx.index if len(str(i)) == 2]   # Hexagone et Corse, codes à deux caractères
    d = ctx.loc[hexa, [res] + X_].dropna()
    d["densite_pop"] = np.log(d["densite_pop"])          # densité en logarithme, comme annoncé dans la méthode
    pub = reg[(reg["resultat"] == res) & (reg["champ"] == "hexagone")].set_index("variable")
    if pub.empty:
        lignes.append(f"ÉCART | régression {res} absente")
        continue
    z = (d - d.mean()) / d.std(ddof=1)
    Xm = np.column_stack([np.ones(len(z))] + [z[c] for c in X_])
    beta, *_ = np.linalg.lstsq(Xm, z[res].values, rcond=None)
    resid = z[res].values - Xm @ beta
    r2 = 1 - (resid ** 2).sum() / ((z[res] - z[res].mean()) ** 2).sum()
    note(f"régression {res}, départements", float(pub["departements"].iloc[0]), float(len(d)), 0)
    note(f"régression {res}, R²", round(pub["r2"].iloc[0], 4), round(r2, 4), .0005)
    bread = np.linalg.inv(Xm.T @ Xm)
    h = np.einsum("ij,jk,ik->i", Xm, bread, Xm)
    se = np.sqrt(np.diag(bread @ (Xm.T @ (Xm * (resid ** 2 / (1 - h) ** 2)[:, None])) @ bread))   # HC3
    for k, c in enumerate(X_):
        note(f"régression {res}, coefficient {c}", round(pub.loc[c, "coef_standardise"], 4), round(beta[k + 1], 4), .0005)
        note(f"régression {res}, erreur type HC3 {c}", round(pub.loc[c, "erreur_std"], 4), round(se[k + 1], 4), .0005)

# ------------------------------------------------------------------ lieux de soins, FINESS et ROR réunis
# Tous les CMP actifs de FINESS, relus directement dans Finess+, doivent se retrouver dans la liste des lieux (sous
# leur numéro, ou rapprochés d'un lieu du ROR), et la somme des départements doit redonner le total de la liste.
import gzip  # noqa: E402
fp = json.load(gzip.open(B / "finess_plus.json.gz", "rt", encoding="utf-8"))
cmp_fin = {(e.get("informationsGeneralesEGE") or {}).get("numFinessEge") for pm in fp.get("pmej", [])
           for e in (pm.get("ege") or []) if e.get("etatObjet") == "A" and e.get("categorieentiteGeographiqueExercice") == "156"}
ls = lire("lieux_soins.csv", dtype={"finess": str, "finess_rapproche": str, "finess_absorbes": str, "commune": str,
                                   "dep": str})
c = ls[ls["type"] == "lieu_cmp"]
# depuis le 12 octobre 2026, un établissement enregistré comme CMP dont le nom désigne autre chose (équipe mobile,
# CATTP, unité en milieu pénitentiaire...) est rangé dans le type que son nom désigne, il doit se retrouver là
retrouves = set(ls["finess"].dropna()) | set(ls["finess_rapproche"].dropna())
# un CMP inscrit deux fois et réuni à un autre garde son numéro dans finess_absorbes (13 octobre 2026)
if "finess_absorbes" in ls:
    retrouves |= {n for v in ls["finess_absorbes"].dropna().astype(str) for n in v.split(",") if n}
# une inscription écartée par la liste vérifiée de son établissement est consignée dans structures_non_retenues.csv
if (R / "structures_non_retenues.csv").exists():
    _nr = pd.read_csv(R / "structures_non_retenues.csv", sep=";", dtype=str)
    retrouves |= {n for v in _nr["finess"].dropna() for n in v.split(",") if n}
note("CMP actifs de FINESS retrouvés dans les lieux réunis (comme CMP ou sous le type que désigne leur nom)",
     float(len(cmp_fin)), float(len(cmp_fin & retrouves)), 0)
ld = lire("lieux_soins_dep.csv", dtype={"code": str})
note("CMP, somme des départements et liste des lieux", float(ld["n_lieu_cmp"].sum()), float(len(c.dropna(subset=["dep"]))), 0)
note("Lieux sans nom de personne tiré du ROR", 0.0,
     float(ls["unite_ror"].fillna("").str.contains(r"\b(?:Dr|Docteur|Professeur)\b\.?\s", case=False).sum()), 0)

# confirmation des CMP par la certification HAS, recalculée depuis les fichiers bruts de la HAS (dernière démarche de
# chaque entité juridique, sites dont le nom dit CMP)
if "site_certification_has" in ls and (B / "has" / "has_2021_2025_sites.csv").exists():
    import re as _re
    _l = lambda f: pd.read_csv(B / "has" / f, sep=None, engine="python", dtype=str, encoding="utf-8-sig")  # noqa: E731
    _g = []
    for cle in ("has_2021_2025", "has_6e_cycle"):
        _s, _d = _l(f"{cle}_sites.csv"), _l(f"{cle}_demarches.csv")
        _g.append(_s.merge(_d[["code_demarche", "date_de_decision"]], on="code_demarche"))
    _g = pd.concat(_g)
    for _c in ("FINESS_EJ", "FINESS_EG"):
        _g[_c] = _g[_c].astype(str).str.zfill(9)
    _g["_d"] = pd.to_datetime(_g["date_de_decision"], dayfirst=True, errors="coerce")
    _der = _g.dropna(subset=["_d"]).sort_values("_d").groupby("FINESS_EJ")["code_demarche"].last()
    _g = _g[_g.set_index(["FINESS_EJ", "code_demarche"]).index.isin(list(_der.items()))]
    _eg = set(_g.loc[_g["RS_eg"].fillna("").str.contains(r"\bC\s?\.?\s?M\s?\.?\s?P\b(?!\s?\.?\s?P)|M[EÉ]DICO.?PSYCHOLOG|"
                                                         r"\bCMPEA\b|\bCMPI\b|\bCMPPA\b", case=False, regex=True),
                     "FINESS_EG"])
    _c = c.copy()
    _n = _c.apply(lambda r: bool(({str(r.get("finess")), str(r.get("finess_rapproche"))}
                                  | set(str(r.get("finess_absorbes") or "").split(","))) & _eg), axis=1)
    note("CMP confirmés par un site de la certification HAS", float(_c["site_certification_has"].astype(str).eq("True").sum()),
         float(_n.sum()), 0)

print("\n".join(lignes))
print(f"\nRésultats contrôlés, {R}")
print(f"{sum(l.startswith('ok') for l in lignes)} contrôles conformes, {sum(l.startswith('ÉCART') for l in lignes)} écarts")
sys.exit(1 if any(l.startswith("ÉCART") for l in lignes) else 0)
