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
# variables qui rangent les territoires (dixièmes des paires, groupes des trajectoires), tirées du catalogue des
# indicateurs (site_data.json, contexte), un seul catalogue pour le site, l'atlas, Explorer et l'API (décision de
# Lucas du 28 octobre 2026). Une base ajoutée au catalogue paraît d'elle-même dans Explorer, rangée dans son thème.
# Réglages de lecture seulement, pour quelques variables, le nom des groupes extrêmes, le sens des dixièmes et la
# forme du nom dans une phrase ; les autres variables reçoivent une formule générale.
LECTURE_GROUPES = {
    "revenu_median": ("les plus modestes", "les plus aisés"),
    "taux_pauvrete": ("à la pauvreté la plus faible", "à la pauvreté la plus forte"),
    "densite_pop": ("les moins denses", "les plus denses"),
    "part_80p": ("les moins âgés", "les plus âgés"),
    "part_0_14": ("qui comptent le moins d'enfants", "qui comptent le plus d'enfants"),
    "taux_chomage": ("au chômage le plus faible", "au chômage le plus fort")}
LECTURE_GENERALE = ("à la valeur la plus basse", "à la valeur la plus haute")
SENS_DIXIEMES = {"revenu_median": "du plus modeste au plus aisé", "densite_pop": "de la moins dense à la plus dense"}
ARTICLES = {"revenu_median": "le niveau de vie médian", "taux_pauvrete": "le taux de pauvreté",
            "densite_pop": "la densité de population", "taux_chomage": "le taux de chômage",
            "part_80p": "la part des 80 ans et plus", "part_0_14": "la part des moins de 15 ans",
            "part_monoparentales": "la part des familles monoparentales", "part_cadres": "la part des cadres"}
NIVEAU_CATALOGUE = {"epci": "intercommunalités", "dep": "départements"}
DEPARTEMENTS_EXCLUS = ("976",)   # Mayotte, comme dans les croisements entre départements


def _lire(dossier: Path, nom: str) -> pd.DataFrame | None:
    f = dossier / nom
    return pd.read_csv(f, sep=";", decimal=",", dtype={"code": str}, encoding="utf-8-sig", low_memory=False) if f.exists() else None


def catalogue(dossier: Path, niveau: str, colonnes) -> list[dict]:
    """Indicateurs du catalogue (site_data.json, contexte) publiés au niveau voulu et présents dans le fichier de
    contexte de ce niveau, dans l'ordre du catalogue, avec leur thème."""
    f = dossier / "site_data.json"
    if not f.exists():
        return []
    ctx = json.loads(f.read_text(encoding="utf-8")).get("contexte", [])
    return [c for c in ctx if NIVEAU_CATALOGUE[niveau] in (c.get("niveaux") or []) and c["id"] in colonnes]


def _premiere_minuscule(s: str) -> str:
    return s if s[:2].isupper() else s[:1].lower() + s[1:]


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
    variables = {v["id"]: {"lib": v["label"], "unite": v.get("unite", ""), "groupe": v.get("groupe") or "Autres",
                           "famille": v.get("famille") or "",
                           "sens": SENS_DIXIEMES.get(v["id"], "de la valeur la plus basse à la plus haute"),
                           "article": ARTICLES.get(v["id"], f"« {_premiere_minuscule(v['label'])} »"),
                           "valeurs": {k: _v(x) for k, x in c[v["id"]].items()}}
                 for v in catalogue(dossier, "epci", c.columns)}
    return {"profs": {p: {"lib": prof.at[p, "libelle"], "groupe": prof.at[p, "groupe"], "famille": prof.at[p, "famille"]}
                      for p in P},
            "ordre": P, "groupes": list(dict.fromkeys(prof.loc[P, "groupe"])),
            "epci": {r["code"]: [r["nom"], int(r["population"])] + [int(r[f"n_{p}"]) for p in P] for _, r in e.iterrows()},
            "vars": variables}


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
    variables = {}
    for v in catalogue(dossier, "dep", ctx.columns):
        valeurs = {k: _v(x) for k, x in ctx[v["id"]].items()}
        if sum(x is not None for x in valeurs.values()) < 30:      # trop peu de départements pour former des groupes
            continue
        bas, haut = LECTURE_GROUPES.get(v["id"], LECTURE_GENERALE)
        variables[v["id"]] = {"libelle": v["label"], "bas": bas, "haut": haut, "groupe": v.get("groupe") or "Autres",
                              "famille": v.get("famille") or "", "valeurs": valeurs,
                              "article": ARTICLES.get(v["id"], f"« {_premiere_minuscule(v['label'])} »")}
    return {"profs": profs, "vars": variables}


# niveaux des outils d'inégalités, ceux pour lesquels le niveau de vie et l'entonnoir sont calculés (lot 2, 28 octobre 2026)
NIVEAUX_INEGALITES = ("dep", "epci")
# code des outils repris de l'atlas, un fichier par question, chargés après explorer.js
FICHIERS_OUTILS = ("explorer_inegalites.js", "explorer_typologie.js")
CLES_LIEUX = ("types", "escalier", "classes", "fr", "concentration", "tests")


def donnees_inegalites(site_data: dict) -> dict | None:
    """Données des outils des onglets Inégalités et Typologie de l'atlas, déplacés dans Explorer (note du 28 octobre 2026), prises
    telles quelles dans site_data.json pour redonner les mêmes chiffres que l'atlas, effectifs de chaque territoire par
    mode d'exercice, statut dans l'entonnoir, escalier et indice de concentration selon le niveau de vie, limites de
    l'entonnoir, distances aux structures de soins."""
    niv, profs = site_data.get("niveaux", {}), site_data.get("professions", [])
    if not all(lv in niv for lv in NIVEAUX_INEGALITES) or not profs:
        return None
    garder = [p for p in profs if p.get("nature") in NATURES and sum((site_data["france"]["n"].get(p["id"]) or [0])) > 0]
    ids = [p["id"] for p in garder]
    sortie = {"profs": {p["id"]: {"lib": p["libelle"], "groupe": p.get("groupe") or "Autres", "famille": p.get("famille")}
                        for p in garder},
              "france": {"pop": site_data["france"]["pop"], "n": {p: site_data["france"]["n"][p] for p in ids}},
              "niv": {}, "revenu": site_data.get("revenu", {}), "entonnoir": site_data.get("entonnoir", {}),
              "lieux": {k: site_data.get("lieux", {}).get(k) for k in CLES_LIEUX}}
    for lv in NIVEAUX_INEGALITES:
        L = niv[lv]
        sortie["niv"][lv] = {"units": [[u["c"], u["nm"], u["pop"]] for u in L["units"]],
                             "n": {p: L["n"][p] for p in ids if p in L.get("n", {})},
                             "statut": {p: v for p, v in (L.get("entonnoir") or {}).items() if p in ids}}
    # typologie et analyse en composantes principales des intercommunalités (lot 3), mêmes données que l'atlas
    e, libelles = niv["epci"], {p["id"]: (p["libelle"], p.get("groupe") or "Autres médecins") for p in profs}
    profils = site_data.get("typologie", [])
    sortie["typo"] = {"classe": e.get("classe"), "acp_pts": e.get("acp"), "profils": profils,
                      "acp": site_data.get("acp", {}), "noms": (site_data.get("meta") or {}).get("noms_classes", {}),
                      "lieux": (site_data.get("lieux") or {}).get("typologie", []),
                      "libelles": {p: libelles.get(p, (p, "Autres médecins")) for p in {r["prof"] for r in profils}},
                      "parent": [u.get("p") for u in e["units"]],
                      "deps": {u["c"]: u["nm"] for u in niv["dep"]["units"]}}
    return sortie


def gini_territoires(di: dict, lv: str, p: str, mode: str = "all") -> float:
    """Indice de Gini entre territoires, même calcul que la courbe de Lorenz de la page (territoires classés par
    densité, aire sous la courbe par les trapèzes), sert au contrôle face à inegalites.csv."""
    L = di["niv"][lv]
    a = sorted(((u[2], L["n"][p][mode][i]) for i, u in enumerate(L["units"]) if u[2] > 0), key=lambda t: t[1] / t[0])
    P, N = sum(t[0] for t in a), sum(t[1] for t in a) or 1
    cx = cy = g = 0.0
    for pop, n in a:
        nx, ny = cx + pop / P, cy + n / N
        g += (nx - cx) * (ny + cy)
        cx, cy = nx, ny
    return 1 - g


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
    # outils repris de l'atlas (lots 2 et 3), mêmes données que l'atlas, Gini recalculé face à inegalites.csv
    di = donnees_inegalites(site_data)
    if di:
        (out / "donnees_outils.js").write_text(f"const DI={js(di)};\n", encoding="utf-8")
        for code in FICHIERS_OUTILS:
            shutil.copyfile(config.RACINE / "gabarits" / code, out / code)
        pub = {(r["niv"], r["prof"]): r["gini"] for r in site_data.get("inegalites", []) if r.get("mode") == "all"}
        ecarts = [abs(gini_territoires(di, lv, p) - g) for (lv, p), g in pub.items()
                  if lv in di["niv"] and p in di["niv"][lv]["n"]]
        ecart = f"{max(ecarts, default=0):.4f}".replace(".", ",")
        JOURNAL.controle("Explorer, inégalités", f"{len(di['profs'])} professions, Gini recalculé sur {len(ecarts)} "
                         f"couples niveau et profession, écart maximal avec inegalites.csv {ecart}")
    else:
        JOURNAL.controle("Explorer, inégalités", "non écrites, niveaux absents de site_data.json")
    JOURNAL.controle("Page Explorer", f"{len(paires['ordre'])} professions pour les paires, {len(paires['epci'])} "
                     f"intercommunalités, {len(traj['profs'])} séries de la DREES, psychologue sans psychiatre déclaré "
                     f"{part_une_sans_l_autre(paires, 'psychologue', 'psychiatre') * 100:.1f} % des habitants".replace(".", ","))
    return True
