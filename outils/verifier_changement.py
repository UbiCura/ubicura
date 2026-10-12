"""Vérification d'un changement, avant de le présenter à Lucas ou de le publier (demande de Lucas du 11 octobre 2026).

Deux couches. Ce script fait la première, les contrôles qui se calculent. La seconde est la relecture critique avec
la grille docs/grille_relecture.md (esprit et objectif du projet, incertitudes, risques de mauvaise lecture).

    python outils\\verifier_changement.py                     dernière version de resultats, comparée à la publiée
    python outils\\verifier_changement.py --reference D:\\offre_soins\\resultats\\2026-10-10
    python outils\\verifier_changement.py --rapide            sans les tests ni le contrôle indépendant

Contrôles. Tests unitaires, contrôle indépendant des chiffres, comparaison avec la version de référence (effectifs,
fichiers, pages), mise en page des PDF, puis le registre des exigences sur ce que lit le public, tirets cadratins,
nombres en notation scientifique, termes et vocabulaire à éviter, palmarès, sources sans licence, précisions
manquantes des spécialités surtout salariées, écarts avec la DREES, tableaux trop larges pour être lus. Compte rendu
dans donnees/verifications/, code de sortie 0 (rien à signaler), 10 (à regarder), 20 (bloquant).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from html import unescape
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils"))
import comparer_versions as cv  # noqa: E402
from pipeline import config, libelles  # noqa: E402

PALMARES = re.compile(r"mauvais(es)? élèves?|meilleurs? élèves?|palmarès|les pires|lanterne rouge|bon dernier",
                      re.IGNORECASE)
SCIENTIFIQUE = re.compile(r"(?<![\w.#-])\d+(?:[.,]\d+)?e[+-]\d+(?![\w])")
TIRET = "\u2014"
ECART_DREES = .05            # écart avec la DREES à regarder (après prolongement de sa tendance à la même date)
COLONNES_MAX = 9             # au-delà, un tableau de rapport devient difficile à lire


def texte_visible(html: str) -> str:
    html = re.sub(r"<(script|style|svg)[\s\S]*?</\1>", " ", html)
    return unescape(re.sub(r"<[^>]+>", " ", html))


def lancer(c, titre, commande, attendu=(0,), niveau_echec=20):
    r = subprocess.run(commande, cwd=RACINE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    fin = [x for x in (r.stdout + r.stderr).strip().splitlines() if x.strip()][-1:] or [""]
    if r.returncode in attendu:
        c.note(0, f"{titre}, réussi ({fin[0][:120]})")
    else:
        c.note(niveau_echec, f"{titre}, échec (code {r.returncode}), {fin[0][:200]}")


def _larges(version: Path) -> set:
    """En-têtes des tableaux de rapport de plus de COLONNES_MAX colonnes."""
    out = set()
    for f in version.glob("rapport_*.md"):
        lignes = f.read_text(encoding="utf-8").splitlines()
        for i, ligne in enumerate(lignes):
            if ligne.startswith("|---") and ligne.count("|") - 1 > COLONNES_MAX and i:
                out.add(f"{f.name}, « {lignes[i - 1][:70].strip('| ')}… »")
    return out


def registre(c, version: Path, reference: Path | None = None):
    # textes lus par le public, rapports nationaux et territoriaux, pages du site
    textes = {f.relative_to(RACINE): f.read_text(encoding="utf-8") for f in list(version.glob("rapport_*.md"))
              + sorted((version / "territoires").glob("*.md"))[:40]}
    site = RACINE / "site"
    for f in list(site.glob("*.html")) + list((site / "rapports" / version.name).glob("*.html")):
        textes[f.relative_to(RACINE)] = texte_visible(f.read_text(encoding="utf-8", errors="ignore"))
    pb_tiret, pb_sci, pb_mots, pb_palm = [], [], [], []
    for nom, t in textes.items():
        if TIRET in t:
            pb_tiret.append(f"{nom} ({t.count(TIRET)})")
        m = SCIENTIFIQUE.search(t)
        if m:
            pb_sci.append(f"{nom} ({m.group()})")
        pb_mots += [f"{nom}, {x}" for x in libelles.termes_proscrits(t)]
        m = PALMARES.search(t)
        if m:
            pb_palm.append(f"{nom} ({m.group()})")
    for titre, ls, niv in (("Tirets cadratins dans un texte lu par le public", pb_tiret, 10),
                           ("Nombres en notation scientifique", pb_sci, 10),
                           ("Termes ou vocabulaire à éviter", pb_mots, 10),
                           ("Formulation de palmarès", pb_palm, 10)):
        if ls:
            c.note(niv, f"{titre}, " + "; ".join(ls[:8]) + (" ..." if len(ls) > 8 else ""))
        else:
            c.note(0, f"{titre}, aucun")

    # tableaux trop larges dans les rapports, seuls les nouveaux sont à regarder, les anciens restent une dette connue
    larges, avant = _larges(version), (_larges(reference) if reference else set())
    nouveaux, anciens = sorted(larges - avant), sorted(larges & avant)
    c.note(10 if nouveaux else 0, f"Nouveaux tableaux de plus de {COLONNES_MAX} colonnes, "
           + ("; ".join(nouveaux) if nouveaux else "aucun"))
    if anciens:
        c.note(0, "Tableaux larges déjà présents avant (dette connue), " + "; ".join(anciens))

    # chaque source lue a son producteur et sa licence
    jf = version / "journal.json"
    if jf.exists():
        sans = sorted({e["source"] for e in json.loads(jf.read_text(encoding="utf-8")).get("sources", [])
                       if e.get("statut") == "ok" and not (e.get("producteur") and e.get("licence"))})
        c.note(10 if sans else 0, "Sources sans producteur ou sans licence, " + (", ".join(sans) if sans else "aucune"))

    # précisions des spécialités surtout salariées, présentes dans les données du site
    sd = version / "site_data.json"
    if sd.exists():
        data = json.loads(sd.read_text(encoding="utf-8"))
        lim = data.get("limites") or {}
        manquantes = []
        ef = version / "effectifs_france.csv"
        if ef.exists():
            e = pd.read_csv(ef, sep=";", decimal=",").pivot_table(index="prof", columns="mode", values="n", aggfunc="sum")
            groupes = set(config.GROUPES_SPECIALITES) - {config.G_PREV}
            for p in (x["id"] for x in data.get("professions", []) if x.get("groupe") in groupes):
                if p in e.index and e.at[p, "all"] and (e.at[p, "lib"] if "lib" in e and e.at[p, "lib"] == e.at[p, "lib"]
                                                       else 0) / e.at[p, "all"] < config.SEUIL_LIBERAL_SPECIALITE \
                        and f"prof:{p}" not in lim:
                    manquantes.append(p)
        c.note(10 if manquantes else 0, "Spécialités surtout salariées sans leur précision, "
               + (", ".join(manquantes) if manquantes else "aucune"))

    # écarts avec la DREES
    # écarts avec la DREES, à regarder s'ils sont nouveaux ou s'ils augmentent de plus de 2 points
    cf = version / "concordance_effectifs.csv"
    if cf.exists():
        t = pd.read_csv(cf, sep=";", decimal=",")
        col = "ecart_a_l_attendu" if "ecart_a_l_attendu" in t else "ecart"
        ref = {}
        if reference and (reference / cf.name).exists():
            r0 = pd.read_csv(reference / cf.name, sep=";", decimal=",")
            ref = dict(zip(r0["libelle"], r0[col if col in r0 else "ecart"]))
        gros = t[t[col].abs() > ECART_DREES]
        a_voir = gros[[(lib not in ref) or abs(v) > abs(ref[lib]) + .02 for lib, v in zip(gros["libelle"], gros[col])]]
        connus = gros[~gros.index.isin(a_voir.index)]
        fmt = lambda d: "; ".join(f"{r['libelle']} {r[col] * 100:+.1f} %" for _, r in d.iterrows())  # noqa: E731
        c.note(10 if len(a_voir) else 0, f"Écarts nouveaux ou en hausse de plus de {round(ECART_DREES * 100)} % avec "
               f"la DREES (même date), " + (fmt(a_voir) if len(a_voir) else f"aucun sur {len(t)} comparaisons"))
        if len(connus):
            c.note(0, "Écarts déjà connus et expliqués dans la page méthode, " + fmt(connus))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Vérification d'un changement (outils/verifier_changement.py)")
    ap.add_argument("--reference", help="dossier de la version de référence (par défaut la dernière publiée)")
    ap.add_argument("--version", help="dossier de la version à vérifier (par défaut la plus récente)")
    ap.add_argument("--rapide", action="store_true", help="sans les tests ni le contrôle indépendant")
    a = ap.parse_args(argv)
    vs = cv.versions()
    version = Path(a.version) if a.version else vs[-1]
    if a.reference:
        reference = Path(a.reference)
    else:
        pub = cv.PUBLICATION
        nom = json.loads(pub.read_text(encoding="utf-8-sig")).get("version") if pub.exists() else None
        reference = cv.RESULTATS / nom if nom and (cv.RESULTATS / nom).exists() and nom != version.name else (
            vs[-2] if len(vs) > 1 else None)
    c = cv.Compte()
    py = sys.executable
    if not a.rapide:
        lancer(c, "Tests unitaires", [py, "tests/test_unitaires.py"])
        lancer(c, "Contrôle indépendant des chiffres publiés", [py, "outils/controle_independant.py"], niveau_echec=10)
    if reference and reference.exists():
        cv.comparer(reference, version, c)
    else:
        c.note(0, "Aucune version de référence, pas de comparaison")
    cv.verifier_site(c)
    if list((RACINE / "site" / "rapports" / version.name).glob("*.pdf")):
        lancer(c, "Mise en page des PDF", [py, "outils/controle_pdf.py", str(RACINE / "site" / "rapports" / version.name)],
               niveau_echec=10)
    registre(c, version, reference)

    dossier = RACINE / "donnees" / "verifications"
    dossier.mkdir(parents=True, exist_ok=True)
    sortie = dossier / f"verification_{datetime.now():%Y-%m-%d_%H%M}.md"
    verdict = {0: "Rien à signaler dans les contrôles calculés.",
               10: "Des points sont à regarder avant de présenter ou de publier.",
               20: "Problème bloquant, ne pas publier."}[c.niveau]
    texte = [f"# Vérification du changement, {datetime.now():%d/%m/%Y %H:%M}", "",
             f"Version vérifiée, {version}. Référence, {reference or 'aucune'}.", "", f"**{verdict}**", ""]
    for niveau in ("bloquant", "à regarder", "info"):
        ls = [t for n, t in c.lignes if n == niveau]
        if ls:
            texte += [f"## {niveau.capitalize()}", ""] + [f"- {t}" for t in ls] + [""]
    texte += ["## Relecture critique", "",
              "Les contrôles calculés ne suffisent pas. Relire le changement avec la grille docs/grille_relecture.md "
              "(esprit et objectif du projet, incertitudes, risques de mauvaise lecture) et en faire un court compte "
              "rendu pour Lucas.", ""]
    sortie.write_text("\n".join(texte), encoding="utf-8")
    print("\n".join(texte))
    print(f"Compte rendu, {sortie}")
    return c.niveau


if __name__ == "__main__":
    sys.exit(main())
