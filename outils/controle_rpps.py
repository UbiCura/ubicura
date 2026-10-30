"""Recalcul indépendant des effectifs et des densités des professions depuis l'extraction du RPPS en cache (audit des
chiffres du 30 octobre 2026). Lecture directe du fichier d'activité (et du fichier des savoir-faire pour la
spécialité ordinale des médecins), règles de comptage réécrites ici sans appeler le programme :
- les lignes d'étudiants et les lignes sans aucune situation d'exercice (ni mode d'exercice, ni structure) sont écartées ;
- un professionnel compte une fois en France, et une fois dans chaque territoire où il a au moins une activité
  localisée qui n'est ni un soin à distance ni une activité sans soins à la population (secteurs repris de
  config.SECTEURS_CATEGORIES, seule définition empruntée) ;
- le département vient du code commune de la structure (trois caractères outre-mer, arrondissements ramenés à leur
  ville), l'intercommunalité de la table des membres du référentiel Etalab ;
- la densité publiée est l'effectif rapporté à la population du référentiel, pour 10 000 habitants.

    python outils/controle_rpps.py [dossier de résultats] [--lignes N]

Le fichier d'activité fait près de 800 Mo, le contrôle est lourd (mémoire). --lignes N le restreint aux N premières
lignes, pour vérifier le code seulement (les comparaisons sont alors fausses par construction). Appelé par
outils/controle_independant.py quand la variable OFFRE_CONTROLE_RPPS vaut 1."""
from __future__ import annotations

import csv
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

# professions hors médecins, libellé exact du RPPS vers l'identifiant publié
PROFESSIONS = {"psychologue": "psychologue", "infirmier": "infirmier", "masseur-kinesitherapeute": "masseur_kinesitherapeute",
               "orthophoniste": "orthophoniste", "psychomotricien": "psychomotricien", "sage-femme": "sage_femme",
               "chirurgien-dentiste": "chirurgien_dentiste", "pharmacien": "pharmacien", "ergotherapeute": "ergotherapeute",
               "pedicure-podologue": "pedicure_podologue", "orthoptiste": "orthoptiste"}
# médecins, spécialité ordinale du fichier des savoir-faire vers l'identifiant publié, libellés relevés dans
# l'extraction du 30 octobre 2026 (« Spécialiste en Médecine Générale », « Qualifié en Médecine Générale »,
# « Médecine Générale » ; « Psychiatrie », « Neuro-psychiatrie », hors options de l'enfant et de l'adolescent ;
# « Pédiatrie » et ses options, hors chirurgie et réanimation pédiatriques)
def specialite(lib: str) -> str | None:
    t = simple(lib)
    if t in ("specialiste en medecine generale", "qualifie en medecine generale", "medecine generale"):
        return "medecin_generaliste"
    if "psychiatrie" in t and ("enfant" in t or "adolescent" in t):
        return "pedopsychiatre"
    if "psychiatrie" in t:
        return "psychiatre"
    if t.startswith("pediatrie"):
        return "pediatre"
    return None


def simple(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9-]+", " ", s)).strip()


def simple_secteur(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def note(quoi, publie, recalcule, tol, relatif=True):
    ok = publie is not None and recalcule is not None and np.isfinite(publie) and np.isfinite(recalcule)
    if ok:
        e = abs(publie - recalcule) / (abs(recalcule) or 1) if relatif else abs(publie - recalcule)
        ok = e <= tol
    lignes.append(("ok   " if ok else "ÉCART") + f" | {quoi} | publié {publie} | recalculé {recalcule} | tolérance {tol:g}"
                  + (" relatif" if relatif else ""))


def colonnes(chemin: Path) -> list[str]:
    with open(chemin, encoding="utf-8-sig", errors="replace") as f:
        return f.readline().rstrip("\r\n").split("|")


def lire(chemin: Path, voulues: dict, n_lignes: int | None):
    cols = colonnes(chemin)
    use = {k: next(c for c in cols if c == v) for k, v in voulues.items()}
    it = pd.read_csv(chemin, sep="|", dtype=str, usecols=list(use.values()), quoting=csv.QUOTE_NONE,
                     encoding="utf-8-sig", encoding_errors="replace", keep_default_na=False, chunksize=300_000,
                     nrows=n_lignes)
    for ch in it:
        yield ch.rename(columns={v: k for k, v in use.items()})


def specialites(n_lignes: int | None) -> dict:
    """Identifiant vers profession publiée pour les médecins, d'après la spécialité ordinale."""
    out = {}
    for ch in lire(B / "rpps_savoirfaire.txt", {"id": "Identification nationale PP", "prof": "Libellé profession",
                                               "type": "Libellé type savoir-faire", "sf": "Libellé savoir-faire"}, n_lignes):
        ch = ch[(ch["prof"] == "Médecin") & ch["type"].map(simple).str.contains("specialite ordinale")]
        for i, sf in zip(ch["id"], ch["sf"]):
            sp = specialite(sf)
            if sp:
                out.setdefault(i, set()).add(sp)
    # un médecin qui porte plusieurs spécialités ordinales compte dans la première de cet ordre (psychiatrie de
    # l'enfant, psychiatrie, médecine générale, pédiatrie), quatre personnes en France le 30 octobre 2026
    ordre = ["pedopsychiatre", "psychiatre", "medecin_generaliste", "pediatre"]
    choix = {i: next(o for o in ordre if o in v) for i, v in out.items()}
    return {i: v for i, v in choix.items() if v != "pedopsychiatre"}


def hors_densites(secteur: pd.Series, prof: pd.Series) -> pd.Series:
    regles = [(re.compile(m), profs, c) for m, profs, c in config.SECTEURS_CATEGORIES]
    def cat(s, p):
        return next((c for rx, profs, c in regles if rx.search(s) and (profs is None or p in profs)), "soins")
    cache = {}
    out = []
    for s, p in zip(secteur.map(simple_secteur), prof):
        k = (s, p)
        if k not in cache:
            cache[k] = cat(s, p) in config.CATEGORIES_HORS_DENSITES
        out.append(cache[k])
    return pd.Series(out, index=secteur.index)


def dep_de(code: pd.Series) -> pd.Series:
    c = code.str.strip()
    return c.where(c == "", c.str[:3].where(c.str.startswith("97"), c.str[:2]))


def communes():
    """Communes actuelles (départements à deux caractères et départements d'outre-mer, Saint-Martin et
    Saint-Barthélemy n'en font pas partie), ancien code ou commune déléguée vers sa commune actuelle, code postal vers
    la commune la plus peuplée qui le porte, commune vers son intercommunalité (ou une pseudo-intercommunalité « C »
    suivie du code pour les communes isolées, comme le publié)."""
    brut = json.loads((B / "ref_communes.json").read_text(encoding="utf-8"))
    act = [c for c in brut if c.get("type") == "commune-actuelle"
           and (len(str(c.get("departement", ""))) == 2 or c.get("departement") in ("971", "972", "973", "974", "976"))]
    dep = {c["code"]: c["departement"] for c in act}
    pop = {c["code"]: c.get("population") or 0 for c in act}
    anciens = {c["code"]: (c.get("chefLieu") or c.get("commune")) for c in brut if c.get("type") != "commune-actuelle"
               and (c.get("chefLieu") or c.get("commune")) in dep}
    cps = {}
    for c in act:
        for cp in c.get("codesPostaux") or []:
            if cp not in cps or pop[c["code"]] > pop[cps[cp]]:
                cps[cp] = c["code"]
    epci = json.loads((B / "ref_epci.json").read_text(encoding="utf-8"))
    c2e = {m["code"]: e["code"] for e in epci for m in e.get("membres", [])}
    return dep, anciens, cps, c2e


def recompter(n_lignes: int | None = None) -> dict:
    med = specialites(n_lignes)
    dep_c, anciens, cps, c2e = communes()
    nat, loc = [], []
    for ch in lire(B / "rpps_activite.txt", {"id": "Identification nationale PP", "prof": "Libellé profession",
                                            "cat": "Libellé catégorie professionnelle", "mode": "Libellé mode exercice",
                                            "struct": "Identifiant technique de la structure",
                                            "com": "Code commune (coord. structure)",
                                            "cp": "Code postal (coord. structure)",
                                            "secteur": "Libellé secteur d'activité"}, n_lignes):
        ch = ch[~ch["cat"].map(simple).str.contains("etudiant")]
        ch = ch[~((ch["mode"].str.strip() == "") & (ch["struct"].str.strip() == ""))]
        p = ch["prof"].map(simple).map(PROFESSIONS)
        est_med = ch["prof"] == "Médecin"
        p[est_med] = ch.loc[est_med, "id"].map(med)
        ch = ch.assign(p=p).dropna(subset=["p"])
        nat.append(ch[["p", "id"]].drop_duplicates())
        # commune actuelle, d'après le code saisi, son ancien code, ou à défaut le code postal
        c = ch["com"].str.strip().str.upper()
        c = c.where(c.isin(dep_c), c.map(anciens))
        c = c.where(c.isin(dep_c), ch["cp"].str.strip().map(cps))
        ok = c.notna() & ~hors_densites(ch["secteur"], ch["p"])
        x, c = ch[ok], c[ok]
        loc.append(pd.DataFrame({"p": x["p"], "id": x["id"], "dep": c.map(dep_c),
                                 "epci": c.map(lambda k: c2e.get(k, "C" + k))}).drop_duplicates())
    nat = pd.concat(nat).drop_duplicates()
    loc = pd.concat(loc).drop_duplicates()
    return {"fr": nat.groupby("p")["id"].nunique(),
            "dep": loc.drop_duplicates(["p", "id", "dep"]).groupby(["dep", "p"])["id"].size().unstack(fill_value=0),
            "epci": loc.dropna(subset=["epci"]).drop_duplicates(["p", "id", "epci"]).groupby(["epci", "p"])["id"].size()
            .unstack(fill_value=0)}


def comparer(R: Path, r: dict):
    fr = pd.read_csv(R / "effectifs_france.csv", sep=";", decimal=",", encoding="utf-8-sig")
    fr = fr[fr["mode"] == "all"].set_index("prof")["n"]
    for p, n in r["fr"].items():
        note(f"RPPS, effectif national, {p}", float(fr.get(p, np.nan)), float(n), .002)
    for niv in ("dep", "epci"):
        e = pd.read_csv(R / f"effectifs_{niv}_all.csv", sep=";", decimal=",", encoding="utf-8-sig", dtype={"code": str})
        e = e.set_index("code")
        t = r[niv]
        for p in t.columns:
            col = f"n_{p}"
            if col not in e:
                continue
            x = pd.DataFrame({"pub": e[col], "rec": t[p].reindex(e.index).fillna(0)}).dropna()
            ecart = (x["pub"] - x["rec"]).abs() / x["rec"].clip(lower=10)
            hors = ecart > .02
            pire = ecart.idxmax()
            lignes.append(("ok   " if not hors.any() else "ÉCART") + f" | RPPS, effectifs {p}, {niv} | {len(x)} territoires, "
                          f"{int(hors.sum())} à plus de 2 % (sur au moins 10), pire {pire} publié {x.at[pire, 'pub']:.0f} "
                          f"recalculé {x.at[pire, 'rec']:.0f}")
            # la densité de l'atlas et des rapports, effectif rapporté à la population pour 10 000 habitants
            if f"densite_{p}" in e:
                # densité publiée arrondie, écart relatif d'un millième au plus
                d = ((e[f"densite_{p}"] - e[col] / e["population"] * 1e4).abs()
                     / (e[col] / e["population"] * 1e4).abs().clip(lower=.01))
                lignes.append(("ok   " if (d < 1e-3).all() else "ÉCART") + f" | densité {p}, {niv}, effectif sur population "
                              f"pour 10 000 | écart relatif maximal {d.max():.2g}")


def tout(R: Path | None = None, n_lignes: int | None = None) -> list[str]:
    R = R or sorted(p for p in config.RESULTATS.glob("20*") if (p / "site_data.json").exists())[-1]
    lignes.append(f"info  | RPPS recompté depuis l'extraction en cache, résultats {R.name}"
                  + (f", {n_lignes} premières lignes seulement (essai)" if n_lignes else ""))
    comparer(R, recompter(n_lignes))
    return lignes


if __name__ == "__main__":
    a = sys.argv[1:]
    n = int(a[a.index("--lignes") + 1]) if "--lignes" in a else None
    a = [x for i, x in enumerate(a) if x != "--lignes" and (i == 0 or a[i - 1] != "--lignes")]
    res = tout(Path(a[0]) if a else None, n)
    print("\n".join(res))
    sys.exit(1 if any(x.startswith("ÉCART") for x in res) and not n else 0)
