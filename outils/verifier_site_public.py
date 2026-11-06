"""Garde-fou avant publication, aucune page de l'offre professionnelle dans le site publié.

Décision de Lucas du 28 octobre 2026, rappelée le 30 octobre : rien de ce qui touche aux services payants
n'apparaît sur le site avant que l'offre soit finalisée (ni page « Pour les professionnels », « Modèle économique »
ou « Accès professionnel », ni lien vers elles depuis les menus ou l'accueil). publier.ps1 appelle ce contrôle sur le
dossier qu'il s'apprête à envoyer, et s'arrête s'il trouve quelque chose. Un test le vérifie.

Usage : python outils/verifier_site_public.py <dossier du site à publier>   (code 0 si propre, 1 sinon)
"""
import re
import sys
from pathlib import Path

# Pages de l'offre, par leur nom de fichier ou de dossier.
NOMS = re.compile(r"(^|[\\/])(f-professionnels|pour-les-professionnels|professionnels|acces-professionnel|"
                  r"modele-economique|tarifs|offre)(\.html?|[\\/]|$)", re.I)
# Marqueur posé dans chaque page de l'offre, et titres qui la désignent.
CONTENU = re.compile(r'name="ubicura-offre"|<h1[^>]*>\s*(Pour les professionnels|Modèle économique|Accès professionnel)',
                     re.I)
# Liens vers ces pages depuis une page publiée.
LIENS = re.compile(r'href="[^"]*(f-professionnels|pour-les-professionnels|acces-professionnel|modele-economique)'
                   r'(\.html)?[^"]*"', re.I)
# Dossiers que publier.ps1 écarte de la copie (robocopy /XD), à garder identiques ; les pages de travail « _*.html »
# sont aussi écartées (robocopy /XF), et sautées ici.
DOSSIERS_EXCLUS = ("prototype", "prototype2", "prototype3", "prototype4", "maquettes", "_maquettes")


def pages_offre(dossier):
    """Fichiers du dossier qui sont, ou qui annoncent, une page de l'offre. Les dossiers exclus de la copie sont sautés,
    comme le fait publier.ps1."""
    racine = Path(dossier)
    trouves = []
    for f in sorted(racine.rglob("*")):
        rel = f.relative_to(racine)
        if any(p in DOSSIERS_EXCLUS for p in rel.parts[:-1]) or not f.is_file() or (f.name.startswith("_") and f.suffix == ".html"):
            continue
        if NOMS.search(rel.as_posix()):
            trouves.append(f"{rel.as_posix()}, nom d'une page de l'offre")
            continue
        if f.suffix.lower() in (".html", ".htm"):
            texte = f.read_text(encoding="utf-8", errors="ignore")
            if CONTENU.search(texte):
                trouves.append(f"{rel.as_posix()}, page de l'offre")
            elif LIENS.search(texte):
                trouves.append(f"{rel.as_posix()}, lien vers une page de l'offre")
    return trouves


if __name__ == "__main__":
    t = pages_offre(sys.argv[1])
    for x in t:
        print(x)
    sys.exit(1 if t else 0)
