r"""Recouvrements des points de structures sur la carte du territoire des fiches : deux points se touchent ou se
recouvrent quand la distance de leurs centres est sous la somme de leurs rayons, trait compris (relectures des fiches
construites du 1er novembre 2026 : 130 paires à Lille, 274 dans la métropole de Lyon, 300 dans les Bouches-du-Rhône,
puis des contacts trait compris dans le Grand Paris). Mesuré dans le SVG, à toute largeur d'écran.

    .\.venv\Scripts\python.exe outils\recouvrements_points.py               # toutes les fiches du site construit
    .\.venv\Scripts\python.exe outils\recouvrements_points.py epci/200093201
Code de retour 1 si une fiche a des points qui se recouvrent.
"""
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

CERCLE = re.compile(r"<circle\b[^>]*>")


def _attr(tag: str, nom: str) -> float | None:
    m = re.search(rf'\b{nom}="([-\d.]+)"', tag)
    return float(m.group(1)) if m else None


def recouvrements(html: str) -> int:
    """Nombre de paires de points de la couche des structures qui se touchent ou se recouvrent, trait compris. Un trait
    fixe en pixels (vector-effect) se compte à la largeur de la carte sur ordinateur, 690 px."""
    m = re.search(r'<g class="couche c-structures">(.*?)</g>', html, re.S)
    if not m:
        return 0
    vb = re.search(r'<svg class="carte-svg plan" viewBox="[-\d.]+ [-\d.]+ ([\d.]+)', html)
    px = float(vb.group(1)) / 690 if vb else 0
    pts = []
    for tag in CERCLE.findall(m.group(1)):
        sw = _attr(tag, "stroke-width") or 0
        if "non-scaling-stroke" in tag:
            sw *= px
        pts.append((_attr(tag, "cx"), _attr(tag, "cy"), _attr(tag, "r") + sw / 2))
    n = 0
    for i, (x, y, r) in enumerate(pts):
        for (a, b, s) in pts[i + 1:]:
            if (x - a) ** 2 + (y - b) ** 2 < (r + s) ** 2:
                n += 1
    return n


def main(argv=None) -> int:
    from pipeline import site as S
    args = argv if argv is not None else sys.argv[1:]
    pages = [S.SITE / "territoire" / f"{a}.html" for a in args] if args else sorted((S.SITE / "territoire").glob("*/*.html"))
    fautes = {p.relative_to(S.SITE).as_posix(): n for p in pages if (n := recouvrements(p.read_text(encoding="utf-8")))}
    for k, n in sorted(fautes.items(), key=lambda kv: -kv[1])[:30]:
        print(f"{k} : {n} paires de points qui se recouvrent")
    print(f"recouvrements : {len(fautes)} fiches sur {len(pages)}")
    return 1 if fautes else 0


if __name__ == "__main__":
    sys.exit(main())
