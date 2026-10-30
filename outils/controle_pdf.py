"""Contrôle de la mise en page des rapports PDF, titres restés seuls en bas de page, pages presque vides et texte
qui se copie abîmé (césures invisibles ou mots coupés par une espace).

    python outils\\controle_pdf.py [dossier de la version, par défaut la plus récente de site\\rapports]

Pour chaque PDF, les titres (h1 à h4) de la page HTML correspondante sont cherchés dans le texte de chaque page. Un titre
parmi les dernières lignes d'une page est signalé, comme une page qui ne porte que quelques lignes. Le texte extrait du
PDF est aussi comparé aux mots de la page HTML : une césure invisible (U+00AD) ou un mot coupé en deux par une espace
(« rap port ») est signalé, c'est ce que copierait un lecteur (audit externe du 30 octobre 2026). Code de sortie 0 si
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


MOT = re.compile(r"[a-zà-öø-ÿœæ]+", re.I)


def mots_coupes(texte: str, vocabulaire: set[str]) -> list[str]:
    """Mots du texte extrait coupés par une césure invisible ou par une espace. Un morceau absent du vocabulaire de la
    page HTML qui, collé au suivant, redonne un mot de ce vocabulaire est un mot coupé (« rap port »). Une coupure en
    fin de ligne avec son tiret (« médico-psychologique ») n'est pas comptée, c'est une vraie coupure de mise en page."""
    out = [m.group(0) for m in re.finditer(r"\w+­\s*\w+", texte)]
    # paires de mots qui se chevauchent (« Ce rap », « rap port »), d'où l'anticipation
    for m in re.finditer(r"(?<![\wà-öø-ÿœæ])(?=([a-zà-öø-ÿœæ]{2,}) ([a-zà-öø-ÿœæ]{2,})(?![\wà-öø-ÿœæ]))", texte,
                         flags=re.I):
        a, b = m.group(1).lower(), m.group(2).lower()
        if (a + b) in vocabulaire and (a not in vocabulaire or b not in vocabulaire):
            out.append(f"{m.group(1)} {m.group(2)}")
    return out


def controle_texte(pdf: Path, html: Path, exemples: int = 5) -> list[str]:
    """Texte copié depuis le PDF, mots coupés comptés sur tout le document."""
    vocab = {w.lower() for w in MOT.findall(norm(html.read_text(encoding="utf-8")))}
    texte = "\n".join(p.extract_text() or "" for p in PdfReader(pdf).pages)
    c = mots_coupes(texte, vocab)
    if not c:
        return []
    return [f"{pdf.name}, {len(c)} mot(s) coupé(s) dans le texte copié, par exemple "
            + ", ".join(f"« {x} »" for x in list(dict.fromkeys(c))[:exemples])]


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
        # la dernière ligne, ou l'avant-dernière quand la dernière est aussi un titre (un mot de fin de cellule de
        # tableau, « handicap », n'est pas un titre, faux signal du 13 octobre 2026)
        est_titre = lambda l: any(t[:30] and l.startswith(t[:30]) and len(l) <= len(t) + 3 for t in ts)  # noqa: E731
        fin = lignes[-2:] if len(lignes) >= 2 and est_titre(lignes[-1]) else lignes[-1:]
        for t in ts:
            # la ligne doit être le titre lui-même, pas une phrase qui commence par les mêmes mots
            if any(t[:30] and l.startswith(t[:30]) and len(l) <= len(t) + 3 for l in fin):
                pb.append(f"{pdf.name}, page {k}, titre en bas de page, « {t[:60]} »")
                break
        # une page occupée par une figure porte peu de texte, elle n'est pas « presque vide »
        if len(lignes) <= 4 and k not in (1, len(pages)) and not any(l.startswith("figure ") for l in lignes):
            pb.append(f"{pdf.name}, page {k}, page presque vide ({len(lignes)} lignes)")
    return pb


def main() -> int:
    dossier = Path(sys.argv[1]) if len(sys.argv) > 1 else sorted((RACINE / "site" / "rapports").glob("20*"))[-1]
    pb = []
    for pdf in sorted(dossier.glob("*.pdf")):
        html = dossier / f"{pdf.stem}.html"
        if html.exists():
            pb += controle(pdf, html) + controle_texte(pdf, html)
    for x in pb:
        print(x)
    print(f"{len(pb)} problème(s) de mise en page dans {dossier}")
    return 10 if pb else 0


if __name__ == "__main__":
    sys.exit(main())
