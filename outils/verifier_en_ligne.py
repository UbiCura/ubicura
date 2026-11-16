"""Après l'envoi du site, vérifie que le site en ligne sert bien les pages envoyées, octet pour octet.

La seule présence de la page de la version ne suffit pas : quand on republie la même édition après une correction de
pages, cette page existe déjà en ligne et ne prouve rien (republication du 14 novembre 2026). On compare donc au
dossier envoyé des pages témoins : l'accueil, la feuille de style, le journal, la page de la version, et quelques pages
tirées au hasard. publier.ps1 appelle ce contrôle et relit le site jusqu'à ce que toutes les pages témoins soient
identiques, au plus dix minutes.

Usage : python outils/verifier_en_ligne.py <dossier envoyé> <adresse du site> <version> [--attendre secondes]
        (code 0 si toutes les pages témoins sont identiques, 1 sinon)
"""
import hashlib
import random
import sys
import time
import urllib.request
from pathlib import Path

FIXES = ("index.html", "style.css", "journal.html")
NB_HASARD = 5


def temoins(dossier: Path, version: str, graine=None) -> list[str]:
    """Chemins relatifs des pages témoins présentes dans le dossier envoyé : les pages fixes, la page de la version et
    quelques pages HTML tirées au hasard, pour qu'une page oubliée par le déploiement ait sa chance d'être vue."""
    fixes = [*FIXES, f"donnees/{version}/dictionnaire.html"]
    choisis = [p for p in fixes if (dossier / p).is_file()]
    autres = sorted(p.relative_to(dossier).as_posix() for p in dossier.rglob("*.html")
                    if p.relative_to(dossier).as_posix() not in choisis)
    choisis += random.Random(graine).sample(autres, min(NB_HASARD, len(autres)))
    return choisis


def lire(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "ubicura-verification"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read() if r.status == 200 else None
    except Exception:
        return None


def differences(dossier: Path, adresse: str, chemins: list[str]) -> list[str]:
    """Pages témoins dont le contenu servi diffère du fichier envoyé (ou qui ne sont pas servies)."""
    jeton = f"{time.time_ns()}"
    ecarts = []
    for p in chemins:
        servi = lire(f"{adresse.rstrip('/')}/{p}?v={jeton}")
        local = (dossier / p).read_bytes()
        if servi is None or hashlib.sha256(servi).digest() != hashlib.sha256(local).digest():
            ecarts.append(p)
    return ecarts


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    dossier, adresse, version = Path(argv[0]), argv[1], argv[2]
    attendre = int(argv[argv.index("--attendre") + 1]) if "--attendre" in argv else 600
    chemins = temoins(dossier, version)
    fin = time.monotonic() + attendre
    while True:
        ecarts = differences(dossier, adresse, chemins)
        if not ecarts:
            print(f"{len(chemins)} pages témoins identiques au site envoyé : {', '.join(chemins)}")
            return 0
        if time.monotonic() >= fin:
            print(f"Pages encore différentes du site envoyé : {', '.join(ecarts)}")
            return 1
        time.sleep(15)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
