"""Le code public passe le contrôle de outils/preparer_code_public.py à chaque lancement des tests, et non plus seulement
au moment de la mise en ligne (6 novembre 2026 : une mention interdite ajoutée en cours de semaine n'était vue qu'à la
publication, qui s'arrêtait). Repris par tests/test_unitaires.py."""
from __future__ import annotations

import importlib.util
import subprocess

from pipeline import config


def test_code_public_sans_mention_interdite():
    """Même analyse que la préparation du code public (mention de l'assistant, adresse personnelle, identifiant RPPS,
    chemin interdit), sur les fichiers suivis tels qu'ils sont sur le disque, commit ou non."""
    R = config.RACINE
    spec = importlib.util.spec_from_file_location("pcp", R / "outils" / "preparer_code_public.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    regles = m.INTERDITS_TEXTE + m.motifs_prives()
    suivis = subprocess.run(["git", "ls-files"], cwd=R, capture_output=True, text=True, check=True).stdout.split("\n")
    pb = []
    for f in suivis:
        if not f or not (f in m.DOCS_PUBLICS or not m.EXCLUS.match(f)):
            continue
        if m.INTERDITS_CHEMIN.search(f):
            pb.append((f, "chemin interdit"))
            continue
        chemin = R / f
        if not chemin.exists() or chemin.stat().st_size > 5_000_000:
            continue
        for i, ligne in enumerate(chemin.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for rx, quoi in regles:
                if rx.search(ligne):
                    pb.append((f, i, quoi))
    assert not pb, pb[:10]


def test_aucune_fonction_redefinie_dans_un_module():
    """Deux fonctions du même nom au niveau d'un module : la seconde remplace la première sans bruit (7 novembre 2026,
    la couleur des cartes en tiers portait le nom de la carte bivariée, qui a disparu du rapport de santé mentale)."""
    import ast
    import collections
    pb = []
    for f in sorted(list((config.RACINE / "pipeline").glob("*.py")) + list((config.RACINE / "outils").glob("*.py"))):
        arbre = ast.parse(f.read_text(encoding="utf-8"))
        noms = collections.Counter(n.name for n in arbre.body
                                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
        pb += [(f.name, n) for n, k in noms.items() if k > 1]
    assert not pb, pb