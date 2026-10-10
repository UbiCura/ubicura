"""Contrôle de la mise en page des rapports PDF, titres restés seuls en bas de page et pages presque vides.

    python outils\\controle_pdf.py [dossier de la version, par défaut la plus récente de site\\rapports]

Pour chaque PDF, les titres (h1 à h4) de la page HTML correspondante sont cherchés dans le texte de chaque page. Un titre
parmi les dernières lignes d'une page est signalé, comme une page qui ne porte que quelques lignes. Code de sortie 0 si
tout va bien, 10 sinon.
"""
from __future__ import annotations

import re
import sys
from html import unescape
from pathlib import Path

from pypdf import PdfReader

RACINE = Path(__file__).resolve().parent.parent


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", t))).strip().lower()


def titres(html: str) -> list[str]:
    return [norm(m) for m in re.findall(r"<h[1-4][^>]*>(.*?)</h[1-4]>", html, flags=re.S) if norm(m)]


def controle(pdf: Path, html: Path) -> list[str]:
    ts = [t[:45] for t in titres(html.read_text(encoding="utf-8")) if len(t) > 3]
    pb = []
    pages = PdfReader(pdf).pages
    for k, page in enumerate(pages, 1):
        lignes = [norm(x) for x in (page.extract_text() or "").split("\n") if norm(x)]
        # numéro de page ou pied éventuel ignorés
        while lignes and re.fullmatch(r"\d+( / \d+)?", lignes[-1]):
            lignes.pop()
        if not lignes:
            continue
        fin = lignes[-2:]
        for t in ts:
            if any(t[:30] and l.startswith(t[:30]) for l in fin):
                pb.append(f"{pdf.name}, page {k}, titre en bas de page, « {t[:60]} »")
                break
        if len(lignes) <= 4 and k not in (1, len(pages)):
            pb.append(f"{pdf.name}, page {k}, page presque vide ({len(lignes)} lignes)")
    return pb


def main() -> int:
    dossier = Path(sys.argv[1]) if len(sys.argv) > 1 else sorted((RACINE / "site" / "rapports").glob("20*"))[-1]
    pb = []
    for pdf in sorted(dossier.glob("*.pdf")):
        html = dossier / f"{pdf.stem}.html"
        if html.exists():
            pb += controle(pdf, html)
    for x in pb:
        print(x)
    print(f"{len(pb)} problème(s) de mise en page dans {dossier}")
    return 10 if pb else 0


if __name__ == "__main__":
    sys.exit(main())
