"""Comparaison de deux versions des résultats avant publication (demande de Lucas du 9 octobre 2026).

Compare la version qui va être publiée à la précédente (par défaut la dernière publiée, inscrite dans
donnees/publication.json, sinon l'avant-dernière version de resultats/). Repère ce qui serait incohérent, fichier
disparu, effectif national qui bouge brutalement, département qui perd ou gagne beaucoup de professionnels d'un coup,
indicateur qui se vide, page du site manquante. Écrit un compte rendu lisible dans donnees/journaux/ et rend un code,
0 rien d'anormal, 10 des écarts à regarder (la publication attend la validation de Lucas), 20 un problème bloquant.

    python outils/comparer_versions.py                    compare la nouvelle version à la dernière publiée
    python outils/comparer_versions.py 2026-10-08 2026-10-09
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
RESULTATS = RACINE / "resultats"
SITE = RACINE / "site"
JOURNAUX = RACINE / "donnees" / "journaux"
PUBLICATION = RACINE / "donnees" / "publication.json"

# seuils, un écart au-delà du premier est à regarder, au-delà du second il bloque la publication
NATIONAL = (.05, .20)          # variation relative d'un effectif national
DEPARTEMENT = (.25, .60)       # variation relative d'un effectif départemental (au moins 30 professionnels)
POPULATION = (.01, .05)        # variation de la population totale
LIGNES = (.20, .50)            # variation du nombre de lignes d'un fichier
VIDES = .05                    # hausse de la part de valeurs manquantes d'un indicateur
LIEUX = (.15, .40)             # variation du nombre de lieux de soins d'un type (FINESS et ROR, mis à jour chaque semaine)
PRINCIPALES = ["psychologue", "psychiatre", "pedopsychiatre", "psychotherapeute", "medecin_generaliste", "infirmier",
               "masseur_kinesitherapeute", "orthophoniste", "psychomotricien", "pharmacien", "chirurgien_dentiste",
               "sage_femme", "pediatre"]
PAGES = ["index.html", "atlas.html", "methode.html", "methode-structures.html", "methode-indicateurs.html",
         "methode-controles.html", "methode-fichiers.html", "rapports.html", "donnees-sources.html", "journal.html",
         "territoires/index.html"]


def lire(f: Path) -> pd.DataFrame | None:
    try:
        return pd.read_csv(f, sep=";", decimal=",", dtype={"code": str}, low_memory=False)
    except Exception:  # noqa: BLE001
        return None


def versions() -> list[Path]:
    return sorted(p for p in RESULTATS.iterdir() if p.is_dir() and p.name[:2] == "20" and (p / "site_data.json").exists())


class Compte:
    def __init__(self):
        self.lignes, self.niveau = [], 0

    def note(self, niveau: int, texte: str):
        self.niveau = max(self.niveau, niveau)
        self.lignes.append(({0: "info", 10: "à regarder", 20: "bloquant"}[niveau], texte))


def comparer(avant: Path, apres: Path, c: Compte):
    # 1. fichiers
    fa, fb = {f.name for f in avant.glob("*.csv")}, {f.name for f in apres.glob("*.csv")}
    for f in sorted(fa - fb):
        c.note(20, f"Fichier disparu, {f}")
    for f in sorted(fb - fa):
        c.note(0, f"Nouveau fichier, {f}")
    for f in sorted(fa & fb):
        na, nb = sum(1 for _ in open(avant / f, encoding="utf-8-sig")), sum(1 for _ in open(apres / f, encoding="utf-8-sig"))
        if na > 50:
            # un fichier qui maigrit est suspect, un fichier qui grossit vient le plus souvent d'une analyse ajoutée
            v = (nb - na) / na
            if v < -LIGNES[0]:
                c.note(20 if v < -LIGNES[1] else 10, f"{f}, {na} lignes avant, {nb} après ({v:+.0%})")
            elif v > LIGNES[1]:
                c.note(0, f"{f}, {na} lignes avant, {nb} après ({v:+.0%})")
    # 2. effectifs nationaux
    a, b = lire(avant / "effectifs_france.csv"), lire(apres / "effectifs_france.csv")
    if a is None or b is None:
        c.note(20, "Effectifs nationaux illisibles")
    else:
        a = a[a["mode"] == "all"].set_index("prof")["n"]
        b = b[b["mode"] == "all"].set_index("prof")["n"]
        for p in PRINCIPALES:
            if p in a and p in b and a[p] > 0:
                v = (b[p] - a[p]) / a[p]
                if abs(v) > NATIONAL[0]:
                    c.note(20 if abs(v) > NATIONAL[1] else 10,
                           f"Effectif national, {p}, {int(a[p])} avant, {int(b[p])} après ({v:+.1%})")
            elif p in a and p not in b:
                c.note(20, f"Effectif national, {p} a disparu")
        c.note(0, "Effectifs nationaux des professions principales, " + ", ".join(
            f"{p} {int(b[p])}" for p in PRINCIPALES if p in b))
    # 3. départements
    a, b = lire(avant / "effectifs_dep_all.csv"), lire(apres / "effectifs_dep_all.csv")
    if a is not None and b is not None:
        a, b = a.set_index("code"), b.set_index("code")
        if len(b) < len(a):
            c.note(20, f"Départements, {len(a)} avant, {len(b)} après")
        pa, pb = a["population"].sum(), b["population"].sum()
        v = (pb - pa) / pa
        if abs(v) > POPULATION[0]:
            c.note(20 if abs(v) > POPULATION[1] else 10, f"Population totale, {pa:,.0f} avant, {pb:,.0f} après ({v:+.1%})")
        for p in PRINCIPALES:
            col = f"n_{p}"
            if col not in a or col not in b:
                continue
            x = pd.DataFrame({"a": a[col], "b": b[col].reindex(a.index)}).dropna()
            x = x[x["a"] >= 30]
            x["v"] = (x["b"] - x["a"]) / x["a"]
            fort = x[x["v"].abs() > DEPARTEMENT[0]]
            if len(fort):
                pire = fort["v"].abs().idxmax()
                c.note(20 if fort["v"].abs().max() > DEPARTEMENT[1] else 10,
                       f"{p}, {len(fort)} département(s) dont l'effectif change de plus de {DEPARTEMENT[0]:.0%}, le plus "
                       f"fort {a.at[pire, 'nom']} ({int(x.at[pire, 'a'])} avant, {int(x.at[pire, 'b'])} après)")
    # 4. indicateurs qui se vident
    for f in ["contexte_dep.csv", "contexte_epci.csv"]:
        a, b = lire(avant / f), lire(apres / f)
        if a is None or b is None:
            continue
        for col in a.columns:
            if col in ("code", "nom") or col not in b or not np.issubdtype(a[col].dtype, np.number):
                continue
            va, vb = a[col].isna().mean(), b[col].isna().mean()
            if vb - va > VIDES:
                c.note(10, f"{f}, l'indicateur {col} a {vb:.0%} de valeurs manquantes contre {va:.0%} avant")
        for col in sorted(set(a.columns) - set(b.columns)):
            c.note(10, f"{f}, l'indicateur {col} a disparu")
    # 5. lieux de soins par type, le ROR étant rempli par les établissements, une région peut changer d'un coup
    a, b = lire(avant / "lieux_soins.csv"), lire(apres / "lieux_soins.csv")
    if a is not None and b is not None:
        na, nb = a.groupby("libelle_type").size(), b.groupby("libelle_type").size()
        for k in na.index:
            if na[k] >= 30:
                v = (nb.get(k, 0) - na[k]) / na[k]
                if abs(v) > LIEUX[0]:
                    c.note(20 if abs(v) > LIEUX[1] else 10, f"Lieux de soins, {k}, {int(na[k])} avant, {int(nb.get(k, 0))} après ({v:+.0%})")
    elif a is not None and b is None:
        c.note(20, "Lieux de soins, fichier lieux_soins.csv disparu")
    # 6. rapports territoriaux
    ta, tb = len(list((avant / "territoires").glob("*.md"))), len(list((apres / "territoires").glob("*.md")))
    if tb < ta:
        c.note(20, f"Rapports territoriaux, {ta} avant, {tb} après")
    # 7. cohérence des indicateurs et des croisements (exigence de Lucas du 12 octobre 2026, après des indicateurs
    # fantômes nés d'un ajout placé dans la mauvaise liste de config.py)
    coherence(apres, c)


# libellé qui laisse voir un identifiant du code (« lieux_psy libéraux... »)
IDENTIFIANT = re.compile(r"\b[a-z0-9]+_[a-z0-9_]+\b|\b(?:dens|ctx|route|dens_lib):")


def coherence(version: Path, c: Compte):
    """Chaque indicateur de contexte a un identifiant unique, un libellé lisible et des données à au moins un niveau.
    Chaque question de croisement de config.CROISEMENTS produit un résultat, sinon la source manque ou la question
    est mal écrite."""
    sd = version / "site_data.json"
    if not sd.exists():
        return
    data = json.loads(sd.read_text(encoding="utf-8"))
    ind = data.get("contexte") or []
    ids = [x.get("id") for x in ind]
    doubles = sorted({i for i in ids if ids.count(i) > 1})
    vides = [x["id"] for x in ind if not x.get("niveaux")]
    bruts = [f'{x["id"]} (« {x.get("label", "")[:60]} »)' for x in ind if IDENTIFIANT.search(x.get("label") or "")]
    labs = [x.get("label") for x in ind]
    memes = sorted({l_ for l_ in labs if l_ and labs.count(l_) > 1})
    for titre, ls in (("Indicateurs en double", doubles), ("Indicateurs sans donnée à aucun niveau", vides),
                      ("Indicateurs dont le libellé laisse voir un identifiant du code", bruts),
                      ("Indicateurs différents sous le même libellé", memes)):
        c.note(20 if ls else 0, f"{titre}, " + ("; ".join(ls[:8]) + (" ..." if len(ls) > 8 else "") if ls else "aucun"))
    sys.path.insert(0, str(RACINE))
    from pipeline import config
    faits = {x.get("theme") for x in data.get("croisements_bases") or []}
    attendus = []
    for _xa, _yb, theme, q in config.CROISEMENTS:
        if theme not in attendus:
            attendus.append(theme)
    manquants = [t for t in attendus if t not in faits]
    c.note(10 if manquants else 0, "Questions de croisement sans résultat, "
           + (", ".join(manquants) if manquants else f"aucune sur {len(attendus)}"))
    # chiffres des rapports confrontés aux tableaux publiés (demande de Lucas du 13 octobre 2026)
    sys.path.insert(0, str(RACINE / "outils"))
    import coherence_rapports
    ecarts = coherence_rapports.controler(version)
    c.note(20 if ecarts else 0, "Chiffres des rapports différents des tableaux, "
           + ("; ".join(ecarts[:6]) + (f" ... ({len(ecarts)} en tout)" if len(ecarts) > 6 else "") if ecarts
              else "aucun"))


RPPS = re.compile(r"(?<![\d.,])10\d{9}(?![\d.,])")   # identifiant RPPS, onze chiffres commençant par 10


def verifier_site(c: Compte):
    # aucune donnée personnelle ne doit partir en ligne, ni identifiant RPPS
    for f in SITE.rglob("*"):
        if f.is_file() and f.suffix in (".html", ".csv", ".json", ".js", ".md", ".txt") and "prototype" not in str(f):
            m = RPPS.search(f.read_text(encoding="utf-8", errors="ignore"))
            if m:
                c.note(20, f"Ce qui ressemble à un identifiant RPPS ({m.group()}) figure dans {f.relative_to(SITE)}")
    for p in PAGES:
        if not (SITE / p).exists():
            c.note(20, f"Page du site absente, {p}")
    for f in SITE.rglob("*.html"):
        if f.stat().st_size < 500:
            c.note(20, f"Page du site presque vide, {f.relative_to(SITE)}")


def main(args):
    vs = versions()
    if len(args) == 2:
        avant, apres = RESULTATS / args[0], RESULTATS / args[1]
    else:
        apres = vs[-1]
        publiee = json.loads(PUBLICATION.read_text(encoding="utf-8-sig")).get("version") if PUBLICATION.exists() else None
        avant = RESULTATS / publiee if publiee and (RESULTATS / publiee).exists() and publiee != apres.name else (
            vs[-2] if len(vs) > 1 else None)
    c = Compte()
    if avant is None:
        c.note(0, "Première version, rien à comparer")
    else:
        comparer(avant, apres, c)
    verifier_site(c)
    JOURNAUX.mkdir(parents=True, exist_ok=True)
    sortie = JOURNAUX / f"comparaison_{datetime.now():%Y-%m-%d_%H%M}.md"
    verdict = {0: "Rien d'anormal, la publication peut se faire.",
               10: "Des écarts sont à regarder, la publication attend la validation de Lucas.",
               20: "Problème bloquant, rien n'est publié."}[c.niveau]
    texte = [f"# Comparaison avant publication, {datetime.now():%d/%m/%Y %H:%M}", "",
             f"Version précédente, {avant.name if avant else 'aucune'}. Nouvelle version, {apres.name}.", "",
             f"**{verdict}**", ""]
    for niveau in ("bloquant", "à regarder", "info"):
        ls = [t for n, t in c.lignes if n == niveau]
        if ls:
            texte += [f"## {niveau.capitalize()}", ""] + [f"- {t}" for t in ls] + [""]
    sortie.write_text("\n".join(texte), encoding="utf-8")
    print("\n".join(texte))
    print(f"Compte rendu, {sortie}")
    return c.niveau


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
