"""Page « Explorer les données » (décision de Lucas du 26 octobre 2026), des analyses que le lecteur règle lui-même,
rangées par question. Ce module prépare les données de la page à partir des résultats de la version (aucun calcul
nouveau, les mêmes comptes que les rapports) et copie les bibliothèques et le fond de carte dans site/explorer/.

Outils de la première étape, « une profession sans l'autre » (présence ou absence de deux professions par
intercommunalité, jamais additionnées, toutes les professions de la famille choisie) et « croiser des trajectoires »
(toutes les séries de la DREES depuis 2016, evolution_explorer.csv, par groupe de départements ou une courbe par
profession en base 100). Le code de la page est dans gabarits/explorer.html et gabarits/explorer.js.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from . import cartes, config
from .util import JOURNAL

# professions proposées, toutes celles d'une famille (santé mentale, santé), rangées par groupe comme dans l'atlas
NATURES = ("profession", "qualification")
# variables qui rangent les départements en groupes pour les trajectoires (colonne de contexte_dep.csv, libellé,
# groupe du bas, groupe du haut)
TRAJECTOIRES_VARIABLES = [
    ("revenu_median", "Niveau de vie médian", "les plus modestes", "les plus aisés"),
    ("taux_pauvrete", "Taux de pauvreté", "à la pauvreté la plus faible", "à la pauvreté la plus forte"),
    ("densite_pop", "Densité de population", "les moins denses", "les plus denses"),
    ("part_80p", "Part des 80 ans et plus", "les moins âgés", "les plus âgés"),
    ("part_0_14", "Part des moins de 15 ans", "qui comptent le moins d'enfants", "qui comptent le plus d'enfants"),
    ("part_monoparentales", "Part des familles monoparentales", "à la part la plus faible", "à la part la plus forte"),
    ("taux_chomage", "Taux de chômage", "au chômage le plus faible", "au chômage le plus fort"),
    ("part_cadres", "Part des cadres", "à la part la plus faible", "à la part la plus forte")]
DEPARTEMENTS_EXCLUS = ("976",)   # Mayotte, comme dans les croisements entre départements


def _lire(dossier: Path, nom: str) -> pd.DataFrame | None:
    f = dossier / nom
    return pd.read_csv(f, sep=";", decimal=",", dtype={"code": str}, encoding="utf-8-sig", low_memory=False) if f.exists() else None


def _v(x):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else float(x)


def _professions(dossier: Path) -> pd.DataFrame | None:
    prof = _lire(dossier, "professions.csv")
    if prof is None:
        return None
    return prof[prof["nature"].isin(NATURES)].set_index("id")


def donnees_paires(dossier: Path) -> dict | None:
    """Effectifs de toutes les professions par intercommunalité, avec leur famille et leur groupe, le niveau de vie et
    la densité de population."""
    e, ctx, prof = _lire(dossier, "effectifs_epci_all.csv"), _lire(dossier, "contexte_epci.csv"), _professions(dossier)
    if e is None or prof is None:
        return None
    P = [p for p in prof.index if f"n_{p}" in e and e[f"n_{p}"].sum() > 0]
    c = ctx.set_index("code") if ctx is not None else pd.DataFrame()
    return {"profs": {p: {"lib": prof.at[p, "libelle"], "groupe": prof.at[p, "groupe"], "famille": prof.at[p, "famille"]}
                      for p in P},
            "ordre": P,
            "epci": {r["code"]: [r["nom"], int(r["population"])] + [int(r[f"n_{p}"]) for p in P] for _, r in e.iterrows()},
            "revenu": {k: _v(v) for k, v in c.get("revenu_median", pd.Series(dtype=float)).items()},
            "densite": {k: _v(v) for k, v in c.get("densite_pop", pd.Series(dtype=float)).items()}}


def part_une_sans_l_autre(paires: dict, a: str, b: str) -> float:
    """Part des habitants dans une intercommunalité qui compte au moins un professionnel de a et aucun de b (même
    calcul que la page, sert au contrôle)."""
    i, j = 2 + paires["ordre"].index(a), 2 + paires["ordre"].index(b)
    pop = sum(r[1] for r in paires["epci"].values())
    return sum(r[1] for r in paires["epci"].values() if r[i] > 0 and r[j] == 0) / pop


def donnees_trajectoires(dossier: Path) -> dict | None:
    """Toutes les séries de la DREES par département (effectif et population par année, source), avec la famille et
    le groupe de la profession, et les variables de groupement."""
    ev, ctx, prof = _lire(dossier, "evolution_explorer.csv"), _lire(dossier, "contexte_dep.csv"), _lire(dossier, "professions.csv")
    if ev is None or ctx is None or prof is None:
        return None
    prof = prof.set_index("id")
    ev = ev[~ev["code"].isin(DEPARTEMENTS_EXCLUS)]
    profs = {}
    for p, g in ev.groupby("prof"):
        base = {"chirurgiens": "chirurgien_general"}.get(p, p.replace("_lib", "").replace("_sal", ""))
        profs[p] = {"libelle": g["libelle"].iloc[0], "source": g["source"].iloc[0],
                    "groupe": prof.at[base, "groupe"] if base in prof.index else "Autres",
                    "famille": prof.at[base, "famille"] if base in prof.index else "Santé",
                    "deps": {c: {str(int(r.annee)): [int(r.effectif), int(r.population)] for r in h.itertuples()}
                             for c, h in g.groupby("code")}}
    ctx = ctx[~ctx["code"].isin(DEPARTEMENTS_EXCLUS)].set_index("code")
    variables = {v: {"libelle": l, "bas": b, "haut": h, "valeurs": {k: _v(x) for k, x in ctx[v].items()}}
                 for v, l, b, h in TRAJECTOIRES_VARIABLES if v in ctx}
    return {"profs": profs, "vars": variables}


def ecrire(dossier: Path, site: Path, site_data: dict) -> bool:
    """Écrit site/explorer/ (données, bibliothèques, fond de carte, code de la page). Renvoie False si une pièce manque."""
    out = site / "explorer"
    out.mkdir(parents=True, exist_ok=True)
    paires, traj = donnees_paires(dossier), donnees_trajectoires(dossier)
    if not paires or not traj or not cartes.FOND_ATLAS.exists():
        JOURNAL.controle("Page Explorer", "non écrite, données ou fond de carte absents")
        return False
    noms = {u["c"]: u["nm"] for u in site_data["niveaux"]["dep"]["units"] if u["c"] not in DEPARTEMENTS_EXCLUS}
    js = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))  # noqa: E731
    (out / "donnees.js").write_text(f"const DC={js(paires)};\nconst DT={js(traj)};\nconst NOMS={js(noms)};\n",
                                    encoding="utf-8")
    (out / "fond.js").write_text("window.TOPO=" + cartes.FOND_ATLAS.read_text(encoding="utf-8") + ";", encoding="utf-8")
    sys_atlas = config.RACINE / "atlas"
    from importlib import util as iu
    spec = iu.spec_from_file_location("construire_atlas", sys_atlas / "construire_atlas.py")
    isc = iu.module_from_spec(spec)
    spec.loader.exec_module(isc)
    for nom, annees in (("d3.min.js", "2010-2023"), ("topojson-client.min.js", "2012-2019")):
        (out / nom).write_text(isc.ISC.format(annees) + (sys_atlas / "vendor" / nom).read_text(encoding="utf-8"),
                               encoding="utf-8")
    shutil.copyfile(config.RACINE / "gabarits" / "explorer.js", out / "explorer.js")
    JOURNAL.controle("Page Explorer", f"{len(paires['ordre'])} professions pour les paires, {len(paires['epci'])} "
                     f"intercommunalités, {len(traj['profs'])} séries de la DREES, psychologue sans psychiatre déclaré "
                     f"{part_une_sans_l_autre(paires, 'psychologue', 'psychiatre') * 100:.1f} % des habitants".replace(".", ","))
    return True
