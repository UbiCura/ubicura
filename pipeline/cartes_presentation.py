"""Cartes statiques des pages de la présentation (audit de contrôle du 30 octobre 2026, points I1 et I4).

Fond de l'atelier « Croiser » (A["geo"], contours d'Explorer projetés une fois, outre-mer en encarts), aucune donnée
nouvelle. Règle 15 du registre : au national un aplat par territoire, des points seulement à l'échelle locale.
- choroplethe, carte de France d'un indicateur, en cinq classes de même effectif (quintiles des territoires), dans la
  gamme bleue neutre, car un indicateur du profil ne dit pas un niveau souhaitable, territoires sans valeur hachurés.
- situation, le territoire dans son département (ou sa région pour un département), et pour une intercommunalité ou
  un département le plan de ses structures de soins psychiques, en symboles selon leur confirmation.
Figures exportables par « Citer et exporter » (figure.graphique), couleurs en variables avec leur valeur du fond clair.
"""
import html
import re

from .atelier import COS, MET, W, H

CLASSES = ["var(--r0, #579891)", "var(--r1, #3B7E78)", "var(--r2, #2A6B66)", "var(--r3, #1C5652)", "var(--r5, #0D3D3B)"]
VIDE = "url(#hachure)"
DEFS = ('<defs><pattern id="hachure" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
        '<rect width="5" height="5" fill="var(--nodata, #E6E6E9)"/><line x1="0" y1="0" x2="0" y2="5" '
        'stroke="var(--muted, #5D6371)" stroke-width="1"/></pattern></defs>')


def projection():
    """Projection de la métropole, la même que celle du fond de l'atelier (pipeline/atelier._fond)."""
    x0, y0, x1, y1 = MET
    s = min((W - 10) / ((x1 - x0) * COS), (H - 10) / (y1 - y0))
    return lambda lon, lat: ((lon - x0) * COS * s + 65, (y1 - lat) * s + 5)


def _boite(chemins):
    nums = [float(x) for d in chemins for x in re.findall(r"-?\d+(?:\.\d+)?", d)]
    xs, ys = nums[0::2], nums[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def _fr(x, d=1):
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def choroplethe(A: dict, lv: str, ind: str, titre: str, unite: str, largeur=660) -> str | None:
    vals = A["val"].get(lv, {}).get(ind)
    if not vals:
        return None
    codes = [u["c"] for u in A["units"][lv]]
    v = {c: x for c, x in zip(codes, vals) if x is not None}
    if len(v) < 10:
        return None
    tri = sorted(v.values())
    bornes = [tri[int(len(tri) * k / 5)] for k in range(1, 5)]
    # arrondis de la règle unique (affichage.nombre selon le genre de l'indicateur), chaque infobulle nomme son
    # territoire et son unité, un 0 d'une profession s'écrit « aucun inscrit » (audit du 6 novembre 2026)
    from . import affichage as AF
    g = ((A.get("aff") or {}).get("ind", {}).get(ind) or {}).get("g") or AF.genre(unite, ind)
    noms = {u["c"]: u.get("nm", u["c"]) for u in A["units"][lv]}
    prof = ind.startswith("prof")

    def info(c):
        if c not in v:
            return f"{noms.get(c, c)}, non publié"
        if v[c] == 0 and prof:
            return f"{noms.get(c, c)}, aucun inscrit"
        if v[c] == 0 and ind.startswith("lieux"):
            return f"{noms.get(c, c)}, {AF.AUCUNE_STRUCTURE}"
        return f"{noms.get(c, c)}, {AF.nombre(v[c], g)}" + (f" {unite}" if unite else "")

    def classe(x):
        return sum(1 for b in bornes if x >= b)

    s = [f'<svg viewBox="0 0 {A["W"]} {A["H"] + 46}" role="img" aria-label="{titre}, par {"département" if lv == "dep" else "intercommunalité"}, en cinq classes">', DEFS]
    for c, chemin in A["geo"][lv].items():
        f = CLASSES[classe(v[c])] if c in v else VIDE
        s.append(f'<path d="{chemin}" fill="{f}" stroke="var(--panel, #FFFFFF)" stroke-width="{0.3 if lv == "epci" else 0.6}">'
                 f'<title>{html.escape(info(c))}</title></path>')
    y = A["H"] + 8
    lim = [tri[0]] + bornes + [tri[-1]]
    for k in range(5):
        x = 70 + k * 96
        s.append(f'<rect x="{x}" y="{y}" width="92" height="12" fill="{CLASSES[k]}"/>')
        s.append(f'<text x="{x}" y="{y + 28}" font-size="12" fill="var(--muted, #5D6371)" font-family="Work Sans, sans-serif">'
                 f'{AF.nombre(lim[k], g) or "0"} à {AF.nombre(lim[k + 1], g)}</text>')
    s.append(f'<rect x="{70 + 5 * 96 + 8}" y="{y}" width="16" height="12" fill="{VIDE}"/><text x="{70 + 5 * 96 + 28}" y="{y + 11}" '
             f'font-size="12" fill="var(--muted, #5D6371)" font-family="Work Sans, sans-serif">non publié</text>')
    s.append("</svg>")
    return "".join(s)


# -- cartes de la fiche d'un territoire (étape 2 du plan de reprise, 30 octobre 2026) -----------------------------------
# Les contours d'un territoire sont écrits une seule fois par page (Formes.defs, <path id>) et repris par chaque carte
# (<use>), si bien qu'une fiche porte une carte de situation et une petite carte par constat sans s'alourdir. À
# l'export, figures.js remplace chaque <use> par le contour qu'il reprend. Couleurs en variables avec leur valeur du
# fond clair, pour l'export. Chaque territoire porte data-t="<niveau>:<code>", que « Ton territoire partout » cerne.
DENSITE = [("--r0", "#579891"), ("--r1", "#3B7E78"), ("--r2", "#2A6B66"), ("--r3", "#1C5652"), ("--r5", "#0D3D3B")]
LETTRE = {"reg": "R", "dep": "D", "epci": "E"}


def ecarter(lieux: list, r: float) -> list:
    """Points d'un plan, chacun (x, y, ...), décalés d'un cran autour de leur place quand ils en chevauchent un autre
    déjà posé (relecture esthétique du 30 octobre 2026) : un point garde sa place, les suivants tournent autour, à
    deux rayons et demi, trait compris, pour que deux points ne se touchent pas (1er novembre 2026). Le trait suit la
    taille du point (en unités de la carte) : un trait fixe en pixels faisait se toucher des points sur un écran étroit."""
    import math
    poses, sortie = [], []
    for lieu in lieux:
        x, y = lieu[0], lieu[1]
        for k in range(60):   # dix tours de six places, du plus près au plus loin
            if all((x - a) ** 2 + (y - b) ** 2 >= (2.5 * r) ** 2 for a, b in poses):
                break
            ang, ray = k * 2.4, 2.6 * r * (1 + k // 6)
            x, y = lieu[0] + ray * math.cos(ang), lieu[1] + ray * math.sin(ang)
        poses.append((x, y))
        sortie.append((round(x, 3), round(y, 3)) + tuple(lieu[2:]))
    return sortie


def regrouper(lieux: list, d: float) -> list:
    """Lieux (x, y, classe, dedans, titres) d'une même classe de confirmation, dedans ou hors du territoire, à moins de d
    l'un de l'autre : un seul point, à la place du premier, qui porte tous les noms. Au-delà d'une certaine densité,
    ecarter ne trouve plus de place et les points se recouvraient (Bouches-du-Rhône, Lyon, Lille ; 1er novembre 2026)."""
    groupes: list = []
    for x, y, cl, dedans, titres in lieux:
        g = next((g for g in groupes if g[2] == cl and g[3] == dedans and (g[0] - x) ** 2 + (g[1] - y) ** 2 < d * d), None)
        if g:
            g[4].extend(titres)
        else:
            groupes.append([x, y, cl, dedans, list(titres)])
    return [tuple(g) for g in groupes]


def rayon_points(r: float, n: int, n_aise: int = 40) -> float:
    """Rayon des points d'un plan selon leur nombre : r jusqu'à n_aise lieux, puis en raison inverse de la racine du
    nombre, pour que la surface couverte reste la même, sans descendre sous 40 % de r (un point reste visible). À Lille,
    231 lieux de 18 à 30 px se recouvraient par 130 paires (relecture des fiches construites du 1er novembre 2026)."""
    return r if n <= n_aise else max(.4 * r, r * (n_aise / n) ** .5)


def _v(nom: str, repli: str) -> str:
    return f"var({nom}, {repli})"


class Formes:
    """Contours d'une page : chaque forme demandée est gardée, puis écrite une fois par defs()."""

    _boites: dict = {}
    _compacts: dict = {}
    _france: str | None = None

    def __init__(self, A: dict):
        self.A = A
        self.vus: dict[str, str] = {}
        if not Formes._boites:
            for lv, g in A["geo"].items():
                for c, d in g.items():
                    Formes._boites[(lv, c)] = _boite([d])

    @staticmethod
    def ident(lv: str, code: str) -> str:
        return f"g{LETTRE[lv]}{code}"

    def boite(self, lv, code):
        return Formes._boites.get((lv, code))

    def forme(self, lv: str, code: str, **attr) -> str:
        """<use> d'un contour, gardé pour defs()."""
        i = self.ident(lv, code)
        if (lv, code) not in Formes._compacts:
            Formes._compacts[(lv, code)] = compacter(self.A["geo"][lv][code])
        self.vus[i] = Formes._compacts[(lv, code)]
        a = "".join(f' {k.replace("_", "-")}="{v}"' for k, v in attr.items())
        return f'<use href="#{i}"{a}/>'

    def dans(self, lv: str, cadre: tuple) -> list[str]:
        """Territoires du niveau dont la boîte touche le cadre (x0, y0, x1, y1)."""
        x0, y0, x1, y1 = cadre
        return [c for c in self.A["geo"][lv] if (b := Formes._boites.get((lv, c)))
                and b[0] <= x1 and b[2] >= x0 and b[1] <= y1 and b[3] >= y0]

    def france(self) -> str:
        """Silhouette simplifiée de la métropole, pour le petit repère de chaque carte locale."""
        if Formes._france is None:
            from shapely.geometry import Polygon
            from shapely.ops import unary_union
            polys = []
            for c, d in self.A["geo"]["reg"].items():
                if c in ("01", "02", "03", "04", "06"):
                    continue
                for anneau in re.findall(r"M([^MZ]+)Z", d):
                    pts = [tuple(map(float, p.split(","))) for p in anneau.split("L")]
                    if len(pts) >= 3:
                        polys.append(Polygon(pts).buffer(0))
            g = unary_union(polys).buffer(1.2).buffer(-1.2).simplify(1.6)
            parts = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
            Formes._france = "".join("M" + "L".join(f"{x:.0f},{y:.0f}" for x, y in p.exterior.coords) + "Z"
                                     for p in parts if p.area > 4)
        self.vus["gFR"] = Formes._france
        return '<use href="#gFR"/>'

    def defs(self) -> str:
        """Le SVG caché qui porte les contours de la page, à placer une fois avant les cartes."""
        corps = "".join(f'<path id="{i}" d="{d}" vector-effect="non-scaling-stroke"/>' for i, d in self.vus.items())
        return ('<svg class="formes" width="0" height="0" aria-hidden="true" focusable="false" style="position:absolute">'
                f'<defs>{DEFS[6:-7]}{corps}</defs></svg>')


def _n(x: float) -> str:
    s = f"{x:.1f}".rstrip("0").rstrip(".")
    return s.replace("0.", ".", 1) if s.startswith("0.") else s.replace("-0.", "-.", 1) if s.startswith("-0.") else s or "0"


def compacter(d: str, tolerance: float = .15) -> str:
    """Contour simplifié (Douglas-Peucker, 0,15 unité de carte, environ 250 m) et écrit en déplacements relatifs au
    dixième, pour les cartes de la fiche. Les anneaux plus petits que la tolérance disparaissent."""
    from shapely.geometry import LinearRing
    out = []
    for anneau in re.findall(r"M([^MZ]+)Z", d):
        pts = [tuple(map(float, q.split(","))) for q in anneau.split("L")]
        if len(pts) < 3:
            continue
        try:
            r = LinearRing(pts).simplify(tolerance)
        except Exception:  # noqa: BLE001
            r = None
        co = list(r.coords)[:-1] if r is not None and not r.is_empty and len(r.coords) >= 4 else pts
        q = [(round(x * 10), round(y * 10)) for x, y in co]
        s = f"M{_n(q[0][0] / 10)},{_n(q[0][1] / 10)}l"
        morceaux = []
        for (a, b), (c, e) in zip(q, q[1:]):
            if (a, b) != (c, e):
                morceaux.append(f"{_n((c - a) / 10)}{',' if (e - b) >= 0 else ''}{_n((e - b) / 10)}")
        out.append(s + "".join(m if k == 0 or m[0] == "-" else " " + m for k, m in enumerate(morceaux)) + "z")
    return "".join(out)


def cadre_autour(boites: list, marge: float, ratio: float = 4 / 3, mini: float = 0) -> tuple:
    """Cadre (x0, y0, x1, y1) qui contient les boîtes, élargi de la marge, au rapport largeur sur hauteur donné."""
    x0 = min(b[0] for b in boites)
    y0 = min(b[1] for b in boites)
    x1 = max(b[2] for b in boites)
    y1 = max(b[3] for b in boites)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = max(x1 - x0, mini) * (1 + 2 * marge), max(y1 - y0, mini / ratio) * (1 + 2 * marge)
    w, h = max(w, h * ratio), max(h, w / ratio)
    return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2


def _reperage(F: Formes, cadre: tuple, point: tuple | None = None) -> str:
    """Petit repère en haut à droite d'une carte locale : la France, le cadre de la carte, et le point du territoire.
    Aucun repère quand la carte montre déjà la France, ni outre-mer (encarts à une autre échelle)."""
    x0, y0, x1, y1 = cadre
    if (x1 - x0) > 300 or x0 < 150 and y0 > 370:
        return ""
    w = (x1 - x0) * .2
    k = w / 520
    tx, ty = x1 - w - (x1 - x0) * .02 - 60 * k, y0 + (y1 - y0) * .03 - 5 * k
    g = [f'<g transform="translate({tx:.2f} {ty:.2f}) scale({k:.4f})" aria-hidden="true" class="reperage">',
         f'<rect x="40" y="-15" width="580" height="590" fill="{_v("--bg", "#F4F4F1")}" fill-opacity=".9"/>',
         F.france().replace("/>", f' fill="{_v("--line-fort", "#9A9FA9")}" fill-opacity=".6" stroke="none"/>'),
         f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" fill="none" '
         f'stroke="{_v("--ink", "#1C2028")}" stroke-width="1.2" vector-effect="non-scaling-stroke"/>']
    if point:
        g.append(f'<circle cx="{point[0]:.1f}" cy="{point[1]:.1f}" r="9" fill="{_v("--ink", "#1C2028")}"/>')
    g.append("</g>")
    return "".join(g)


def classes_densite(valeurs: list) -> list | None:
    """Bornes des classes de même effectif (quintiles des territoires du niveau). Une borne répétée ou égale au
    minimum (beaucoup de territoires à zéro) ne fait pas de classe vide : il reste alors moins de cinq classes."""
    tri = sorted(v for v in valeurs if v is not None)
    if len(tri) < 10:
        return None
    return sorted({tri[int(len(tri) * k / 5)] for k in range(1, 5)} - {tri[0]})


# classes de couleur selon le nombre de classes, réparties sur les cinq paliers du bleu d'encre
PALIERS = {1: [0], 2: [0, 4], 3: [0, 2, 4], 4: [0, 1, 3, 4], 5: [0, 1, 2, 3, 4]}
FOND_PALIER = ["--r0", "--r1", "--r2", "--r3", "--r5"]


def legende_classes(bornes: list) -> list[str]:
    """Variables de couleur des cases de la légende, de la classe la plus basse à la plus haute."""
    return [FOND_PALIER[i] for i in PALIERS[len(bornes) + 1]]


def lisere(F: Formes, lv: str, code: str) -> str:
    """Liseré de 3 px de la couleur du fond sous le contour du territoire choisi : sans lui, le contour se perdait dans
    les classes foncées des cartes (1,4 à 1,9:1 en canard sur fond clair, contre-vérification esthétique du
    31 octobre 2026). outils/controle_finition.py vérifie que chaque contour choisi a le sien."""
    return F.forme(lv, code, fill="none", stroke=_v("--bg", "#F4F4F1"), stroke_width="8.5", stroke_linejoin="round",
                   **{"class": "choisi-lisere"})


def mini_carte(F: Formes, lv: str, code: str, codes_vals: dict, bornes: list, cadre: tuple, titre: str,
               contour: tuple | None = None) -> str:
    """Petite carte d'un constat : les territoires du niveau autour de celui de la fiche, en cinq classes de même
    effectif de l'indicateur (bleu d'encre, sans jugement), le territoire cerné, la France en repère."""
    x0, y0, x1, y1 = cadre
    s = [f'<svg class="carte-svg mini" viewBox="{x0:.1f} {y0:.1f} {x1 - x0:.1f} {y1 - y0:.1f}" role="img" '
         f'aria-label="{titre}"><g class="aplats" stroke="{_v("--contour", "#F4F4F1")}" stroke-width=".5">']
    # classes q0 à q4 (bleu d'encre, style.css), nd sans valeur ; figures.js écrit les couleurs dans l'export
    for c in F.dans(lv, cadre):
        v = codes_vals.get(c)
        s.append(F.forme(lv, c, **{"class": "nd" if v is None else f"q{PALIERS[len(bornes) + 1][sum(1 for b in bornes if v >= b)]}"}))
    s.append("</g>")
    if contour:
        s.append(F.forme(*contour, fill="none", stroke=_v("--ink", "#1C2028"), stroke_width="1", stroke_opacity=".55"))
    s.append(lisere(F, lv, code))
    s.append(F.forme(lv, code, fill="none", stroke=_v("--choisi", "#1C2028"), stroke_width="2.5", **{"class": "choisi"}))
    s.append("</svg>")
    return "".join(s)


def situer(F: Formes, cadre: tuple, point: tuple | None) -> str:
    """Petite France qui situe une carte locale, posée à côté d'elle et non plus sur elle (relecture esthétique du
    31 octobre 2026 : le cadre de situation cachait des territoires). Rien pour une carte qui montre déjà la France."""
    x0, y0, x1, y1 = cadre
    if (x1 - x0) > 300 or x0 < 160 and y0 > 370:   # la France entière, ou un encart d'outre-mer
        return ""
    m = max(0.0, 22 - (x1 - x0)) / 2, max(0.0, 22 - (y1 - y0)) / 2
    return "".join([
        '<svg class="situer" viewBox="40 -15 600 590" aria-hidden="true" focusable="false">',
        F.france().replace("/>", f' fill="{_v("--line-fort", "#9A9FA9")}" fill-opacity=".55" stroke="none"/>'),
        f'<rect x="{x0 - m[0]:.1f}" y="{y0 - m[1]:.1f}" width="{x1 - x0 + 2 * m[0]:.1f}" height="{y1 - y0 + 2 * m[1]:.1f}" '
        f'fill="none" stroke="{_v("--ink", "#1C2028")}" stroke-width="1.5" vector-effect="non-scaling-stroke"/>',
        (f'<circle cx="{point[0]:.1f}" cy="{point[1]:.1f}" r="12" fill="{_v("--ink", "#1C2028")}"/>' if point else ""),
        "</svg>"])


def plan(F: Formes, lv: str, code: str, sous: list[tuple], points: list, deps_fond: list[str], cadre: tuple,
         parent: tuple | None) -> str:
    """Carte de situation et plan des structures de soins psychiques. Intercommunalité : ses communes et celles
    d'alentour en fond (dessinées par la page depuis presentation/zone_fond), les intercommunalités voisines en
    contour, le département, les structures en points. Département : ses intercommunalités, ses structures en points.
    Région : ses départements, sans points (règle 15). points : (x, y, classe, titre, dedans)."""
    x0, y0, x1, y1 = cadre
    w = x1 - x0
    r = w / 80     # environ 12 px de diamètre sur la carte de 470 px de la fiche
    s = [f'<svg class="carte-svg plan" viewBox="{x0:.2f} {y0:.2f} {w:.2f} {y1 - y0:.2f}" role="img" '
         f'aria-label="Situation du territoire{", et ses structures de soins psychiques" if points else ""}"'
         + (f' data-communes="{" ".join(deps_fond)}"' if deps_fond else "") + ">"]
    fond, trait = _v("--nodata", "#E6E6E9"), _v("--bg", "#F4F4F1")
    s.append('<g class="communes"></g>')
    # territoires voisins du niveau, puis subdivisions du territoire
    for c in F.dans(lv, cadre):
        if c != code:
            s.append(F.forme(lv, c, fill=fond, fill_opacity=".55" if deps_fond else "1", stroke=trait, stroke_width="1.2",
                             data_t=f"{lv}:{c}"))
    s.append(F.forme(lv, code, fill=f"color-mix(in srgb, {_v('--r1', '#3B7E78')} 38%, {fond})",
                     fill_opacity=".75" if deps_fond else "1", stroke="none", data_t=f"{lv}:{code}", **{"class": "terr-fond"}))
    for lv_s, c in sous:
        s.append(F.forme(lv_s, c, fill="none", stroke=_v("--line-fort", "#9A9FA9"), stroke_width=".8", data_t=f"{lv_s}:{c}"))
    if parent:
        s.append(F.forme(*parent, fill="none", stroke=_v("--ink", "#1C2028"), stroke_width="1", stroke_opacity=".6"))
    # secteurs de psychiatrie (contours) et leurs codes, dessinés par la page depuis presentation/couches
    s.append('<g class="couche c-secteurs"></g>')
    s.append(lisere(F, lv, code))
    s.append(F.forme(lv, code, fill="none", stroke=_v("--choisi", "#1C2028"), stroke_width="2.5", **{"class": "choisi"}))
    s.append('<g class="couche c-secteurs etiquettes"></g><g class="couche c-structures">')
    # plusieurs structures à une même adresse font un seul point, qui porte tous leurs noms
    lieux: dict = {}
    for (x, y, cl, titre, dedans) in points:
        if x0 <= x <= x1 and y0 <= y <= y1:
            lieux.setdefault((round(x, 2), round(y, 2), cl, dedans), []).append(titre)
    ordre = {"recoupee": 0, "a_verifier": 1, "confirmee": 2}
    r = rayon_points(r, len(lieux))
    poses = ecarter(regrouper([(x, y, cl, dedans, titres) for (x, y, cl, dedans), titres in
                               sorted(lieux.items(), key=lambda kv: (not kv[0][3], -ordre.get(kv[0][2], 0)))], 2.5 * r), r)
    for (x, y, cl, dedans, titres) in sorted(poses, key=lambda q: (q[3], ordre.get(q[2], 0))):
        t = f"<title>{' ; '.join(titres)}</title>"
        if not dedans:
            # hors du territoire : un simple contour, plus petit, pour que les structures du territoire se lisent d'abord
            s.append(f'<circle cx="{x}" cy="{y}" r="{r * .6:.3f}" fill="none" stroke="{_v("--muted", "#5D6371")}" '
                     f'stroke-width="{r * .15:.3f}" class="hors">{t}</circle>')
            continue
        # confirmation en trois formes (validation du 31 octobre 2026) : plein, creux, tireté ; sans source, petit point gris
        act = _v("--action", "#0E5A5A")
        if cl == "confirmee":
            s.append(f'<circle cx="{x}" cy="{y}" r="{r:.3f}" fill="{act}" stroke="{trait}" stroke-width="{r * .3:.3f}" '
                     f'class="pt plein">{t}</circle>')
        elif cl == "a_verifier":
            s.append(f'<circle cx="{x}" cy="{y}" r="{r * .85:.3f}" fill="{trait}" stroke="{act}" stroke-width="{r * .38:.3f}" '
                     f'class="pt creux">{t}</circle>')
        elif cl == "recoupee":
            s.append(f'<circle cx="{x}" cy="{y}" r="{r * .85:.3f}" fill="{trait}" stroke="{act}" stroke-width="{r * .36:.3f}" '
                     f'stroke-dasharray="{r * .55:.3f} {r * .4:.3f}" class="pt tirete">{t}</circle>')
        else:
            s.append(f'<circle cx="{x}" cy="{y}" r="{r * .6:.3f}" fill="{_v("--muted", "#5D6371")}" class="pt objet">{t}</circle>')
    s.append("</g></svg>")
    return "".join(s)


def situation(A: dict, lv: str, code: str, parent: str | None, points: list, confirmation: list) -> str | None:
    """Le territoire dans son département (intercommunalité) ou dans sa région (département), avec pour une
    intercommunalité ou un département le plan de ses structures de soins psychiques (points, échelle locale)."""
    geo = A["geo"]
    if lv == "epci":
        voisins = [u["c"] for u in A["units"]["epci"] if u.get("p") == parent and u["c"] in geo["epci"]]
        fond = {c: geo["epci"][c] for c in voisins}
        cadre = [geo["dep"][parent]] if parent in geo["dep"] else list(fond.values())
    elif lv == "dep":
        deps = [u["c"] for u in A["units"]["dep"] if u.get("p") == parent and u["c"] in geo["dep"]] or [code]
        fond = {c: geo["dep"][c] for c in deps}
        cadre = list(fond.values())
    else:
        return None
    if code not in geo[lv]:
        return None
    x0, y0, x1, y1 = _boite(cadre)
    m = max(x1 - x0, y1 - y0) * 0.06
    x0, y0, x1, y1 = x0 - m, y0 - m, x1 + m, y1 + m
    w, h = x1 - x0, y1 - y0
    k = 520 / max(w, h)
    s = [f'<svg viewBox="{x0:.1f} {y0:.1f} {w:.1f} {h:.1f}" role="img" aria-label="Situation du territoire'
         f'{" et plan de ses structures de soins psychiques" if points else ""}">']
    for c, chemin in fond.items():
        if c != code:
            s.append(f'<path d="{chemin}" fill="var(--nodata, #E6E6E9)" stroke="var(--panel, #FFFFFF)" stroke-width="{0.8 / k:.2f}"/>')
    s.append(f'<path d="{geo[lv][code]}" fill="color-mix(in srgb, var(--r1, #3B7E78) 45%, var(--nodata, #E6E6E9))" '
             f'stroke="var(--r4, #0E5A5A)" stroke-width="{1.6 / k:.2f}"/>')
    r = 4.2 / k
    for (x, y, cl, titre) in points:
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            continue
        t = f"<title>{titre}</title>"
        if cl == "confirmee":
            s.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" fill="var(--r4, #0E5A5A)" stroke="var(--panel, #FFFFFF)" stroke-width="{r / 4:.2f}">{t}</circle>')
        elif cl == "a_verifier":
            s.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r * .9:.2f}" fill="var(--panel, #FFFFFF)" stroke="var(--r4, #0E5A5A)" stroke-width="{r / 2.5:.2f}">{t}</circle>')
        else:
            s.append(f'<rect x="{x - r * .75:.2f}" y="{y - r * .75:.2f}" width="{r * 1.5:.2f}" height="{r * 1.5:.2f}" '
                     f'transform="rotate(45 {x:.2f} {y:.2f})" fill="var(--muted, #5D6371)">{t}</rect>')
    s.append("</svg>")
    return "".join(s)
