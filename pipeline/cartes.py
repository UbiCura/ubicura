"""Cartes SVG des rapports territoriaux. Les contours des communes (le fichier qui sert déjà au voisinage et
aux distances) sont réunis par morceau d'intercommunalité situé dans un département, et par département.
Les contours simplifiés sont gardés en cache dans donnees/intermediaire/, et refaits si le fichier des
contours ou le découpage des communes change."""
from __future__ import annotations

import json
import math
from html import escape

from . import config
from .graphiques import DISCRET, ENCRE, LIGNE, OCRE, VIOLET, VIOLET_PALE
from .lecture import nombre
from .util import JOURNAL, log

CACHE = config.INTER / "fonds_territoires.json"
CACHE_COMMUNES = config.INTER / "fonds_communes.json"
# noms des territoires par code (départements, intercommunalités, morceaux, communes), pour les info-bulles
NOMS: dict = {}
# signaux « donnée fragile ici » (9 octobre 2026), symbole ocre marqué « ! », la couleur du territoire ne change pas
FRAGILE = "var(--d1, #B88A2E)"
SIGNAL_MAYOTTE = "Mayotte, données incomplètes, densités surestimées d'environ un quart (population de 2017)"
SIGNAL_SUICIDE = "Île-de-France, décès par suicide nettement sous-déclarés"
MAYOTTE: set = {"976"}   # jamais « 06 », qui est aussi le code des Alpes-Maritimes


def symbole_fragile(x, y, info, r=5.5) -> str:
    return (f'<g><title>{escape(info)}</title><circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{FRAGILE}" '
            f'stroke="var(--bg, #FFFFFF)" stroke-width="1"/><text x="{x:.1f}" y="{y + r * .55:.1f}" text-anchor="middle" '
            f'font-size="{r * 1.5:.0f}" font-weight="700" fill="var(--bg, #FFFFFF)">!</text></g>')


def signaux(codes, suicide=False) -> dict:
    """Signal de chaque territoire concerné, Mayotte toujours, l'Île-de-France sur les figures du suicide.
    Codes de départements, d'intercommunalités ou de communes seulement, jamais de régions (« 06 » et « 11 » sont
    aussi les Alpes-Maritimes et l'Aude)."""
    out = {}
    for c in codes:
        c = str(c)
        if c in MAYOTTE or c.startswith("976"):
            out[c] = SIGNAL_MAYOTTE
        elif suicide and c in config.DEPS_ILE_DE_FRANCE:
            out[c] = SIGNAL_SUICIDE
    return out


def lignes_signal(lab, largeur=560, x=8) -> list[str]:
    """Libellé coupé en lignes qui tiennent dans la figure, quelle que soit la police (6,2 px par signe à 11 px)."""
    import math
    import textwrap
    maxi = max(20, int((largeur - x - 30) / 6.2))
    n = math.ceil(len(lab) / maxi)
    # lignes de longueur voisine, pour ne jamais laisser un mot seul sur la dernière ligne
    return textwrap.wrap(lab, min(maxi, math.ceil(len(lab) / n) + 8))


def legende_signaux(el, x, y, libelles, largeur=560) -> float:
    for lab in sorted(set(libelles)):
        el.append(symbole_fragile(x + 7, y + 6, lab))
        lignes = lignes_signal(lab, largeur, x)
        el.append(f'<text x="{x + 20}" y="{y + 10}" font-size="11" fill="{DISCRET}">'
                  + "".join(f'<tspan x="{x + 20}" dy="{0 if i == 0 else 14}">{escape(t)}</tspan>' for i, t in enumerate(lignes))
                  + '</text>')
        y += 20 + 14 * (len(lignes) - 1)
    return y


def retenir_noms(ref, extra: dict | None = None):
    """Noms affichés au survol et au clic des cartes et des points."""
    NOMS.update(ref.deps.set_index("code")["nom"].to_dict())
    NOMS.update(ref.epci.set_index("code")["nom"].to_dict())
    NOMS.update(ref.communes.set_index("code")["nom"].to_dict())
    NOMS.update(extra or {})
    com = ref.communes
    MAYOTTE.update(com.loc[com["dep"] == "976", "epci"].dropna().astype(str))
    MAYOTTE.update(com.loc[com["dep"] == "976", "code"].astype(str))


def nom(code) -> str:
    return str(NOMS.get(code, code))
TOLERANCE_COMMUNES = .004   # simplification forte des communes (environ 300 à 400 m), pour des rapports légers
TOLERANCE = .002        # simplification des contours des rapports, en degrés (environ 150 à 200 m)
TOLERANCE_ATLAS = .006  # simplification plus forte pour l'atlas, qui affiche toute la France
FOND_ATLAS = config.INTER / "fond_atlas.topojson.json"

# classes de densité rapportée à la moyenne des territoires du même niveau (décision de Lucas du 5 octobre 2026),
# de la plus faible à la plus forte. Palette divergente,
# ocre en dessous de la moyenne, violet au-dessus, et un gris neutre pour les territoires proches de la moyenne,
# pour que la couleur soit réservée aux vrais écarts (révision du 4 octobre 2026).
CLASSES = [(None, "var(--d0, #7A4E00)", "aucun professionnel"),
           (.5, "var(--d1, #B88A2E)", "moins de la moitié de la moyenne"),
           (.8, "var(--d2, #E6D3A6)", "de la moitié à 0,8 fois la moyenne"),
           (1.25, "var(--d3, #E9E7EC)", "proche de la moyenne (0,8 à 1,25 fois)"),
           (2, "var(--d4, #C6B3DB)", "de 1,25 à 2 fois la moyenne"),
           (math.inf, "var(--d6, #3E2563)", "plus de 2 fois la moyenne")]


def _simplifier(d: dict, tol: float) -> dict:
    """Simplifie un ensemble de territoires jointifs en gardant des frontières communes entre voisins."""
    import numpy as np
    import shapely
    cles = list(d)
    try:
        geoms = shapely.coverage_simplify(np.array([d[k] for k in cles], dtype=object), tol)
    except Exception as e:  # noqa: BLE001
        log.warning("simplification par couverture impossible (%s), simplification séparée", e)
        geoms = [d[k].simplify(tol, preserve_topology=True) for k in cles]
    return {k: g for k, g in zip(cles, geoms) if g is not None and not g.is_empty}


def fonds(ref) -> dict | None:
    """Renvoie {"piece": {dep_epci: géométrie}, "dep": {code: géométrie}} pour les rapports territoriaux, et
    {"atlas_epci", "atlas_dep"} plus simplifiés pour l'atlas, ou None sans contours."""
    try:
        import shapely
        from shapely.geometry import shape
    except ImportError:
        return None
    from .sources import contours
    src = contours.FICHIER
    if not src.exists():
        return None
    cle = {"source": src.stat().st_mtime, "communes": int(len(ref.communes)), "tolerance": TOLERANCE,
           "tolerance_atlas": TOLERANCE_ATLAS, "epci": int(ref.communes["epci"].nunique()), "version": 2}
    if CACHE.exists():
        try:
            c = json.loads(CACHE.read_text(encoding="utf-8"))
            if c.get("cle") == cle:
                return {niv: {k: shapely.from_wkt(v) for k, v in d.items()} for niv, d in c["fonds"].items()}
        except Exception as e:  # noqa: BLE001
            log.warning("cache des fonds de carte illisible (%s), il est refait", e)
    gj = json.loads(src.read_text(encoding="utf-8"))
    actuels = set(ref.communes["code"])
    rat = ref.communes.set_index("code")[["dep", "epci"]]
    par_piece = {}
    for f in gj["features"]:
        c = f["properties"].get("code")
        c = c if c in actuels else ref.anciens.get(c)
        if not c:
            continue
        g = shape(f["geometry"])
        g = g if g.is_valid else g.buffer(0)
        par_piece.setdefault(f"{rat.at[c, 'dep']}_{rat.at[c, 'epci']}", []).append(g)
    piece = {k: shapely.union_all(v) for k, v in par_piece.items()}
    par_dep, par_epci = {}, {}
    for k, g in piece.items():
        d, e = k.split("_", 1)
        par_dep.setdefault(d, []).append(g)
        par_epci.setdefault(e, []).append(g)
    dep = {k: shapely.union_all(v) for k, v in par_dep.items()}
    epci = {k: shapely.union_all(v) for k, v in par_epci.items()}
    out = {"piece": _simplifier(piece, TOLERANCE), "dep": _simplifier(dep, TOLERANCE),
           "atlas_epci": _simplifier(epci, TOLERANCE_ATLAS), "atlas_dep": _simplifier(dep, TOLERANCE_ATLAS)}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({"cle": cle, "fonds": {n: {k: g.wkt for k, g in d.items()} for n, d in out.items()}}),
                     encoding="utf-8")
    JOURNAL.controle("Fonds de carte (contours IGN réunis)",
                     f"{len(piece)} morceaux d'intercommunalité, {len(epci)} intercommunalités, {len(dep)} départements")
    return out


def fonds_communes(ref) -> dict | None:
    """Contours simplifiés des communes, regroupés par département, {dep: {commune: géométrie}}, pour les cartes des
    temps de trajet des rapports départementaux (audit 4.6). Cache dans donnees/intermediaire."""
    try:
        import shapely
        from shapely.geometry import shape
    except ImportError:
        return None
    from .sources import contours
    src = contours.FICHIER
    if not src.exists():
        return None
    cle = {"source": src.stat().st_mtime, "communes": int(len(ref.communes)), "tolerance": TOLERANCE_COMMUNES,
           "version": 1}
    if CACHE_COMMUNES.exists():
        try:
            c = json.loads(CACHE_COMMUNES.read_text(encoding="utf-8"))
            if c.get("cle") == cle:
                return {d: {k: shapely.from_wkt(v) for k, v in m.items()} for d, m in c["fonds"].items()}
        except Exception as e:  # noqa: BLE001
            log.warning("cache des contours des communes illisible (%s), il est refait", e)
    gj = json.loads(src.read_text(encoding="utf-8"))
    actuels = set(ref.communes["code"])
    dep = ref.communes.set_index("code")["dep"]
    par_com = {}
    for f in gj["features"]:
        c = f["properties"].get("code")
        c = c if c in actuels else ref.anciens.get(c)
        if not c:
            continue
        g = shape(f["geometry"])
        par_com.setdefault(c, []).append(g if g.is_valid else g.buffer(0))
    com = {k: shapely.union_all(v) for k, v in par_com.items()}
    simple = _simplifier(com, TOLERANCE_COMMUNES)
    out = {}
    for k, g in simple.items():
        out.setdefault(dep[k], {})[k] = g
    CACHE_COMMUNES.parent.mkdir(parents=True, exist_ok=True)
    CACHE_COMMUNES.write_text(json.dumps({"cle": cle, "fonds": {d: {k: shapely.to_wkt(g, rounding_precision=4)
                                                                     for k, g in m.items()} for d, m in out.items()}}),
                              encoding="utf-8")
    return out


def topojson(objets: dict, q=100_000) -> dict:
    """TopoJSON minimal (un arc par anneau, coordonnées quantifiées et codées en écarts). objets associe un
    nom de couche à (nom de la propriété, {code: géométrie})."""
    from shapely.geometry.polygon import orient
    geoms = [g for _p, d in objets.values() for g in d.values()]
    b = [g.bounds for g in geoms]
    x0, y0 = min(x[0] for x in b), min(x[1] for x in b)
    x1, y1 = max(x[2] for x in b), max(x[3] for x in b)
    kx, ky = (x1 - x0) / (q - 1), (y1 - y0) / (q - 1)
    arcs, out = [], {}
    for nom, (prop, d) in objets.items():
        gs = []
        for code, g in d.items():
            polys = []
            for p in getattr(g, "geoms", [g]):
                if p.is_empty or not hasattr(p, "exterior"):
                    continue
                p = orient(p, sign=-1.0)   # anneau extérieur dans le sens des aiguilles, convention de d3
                anneaux = []
                for r in [p.exterior] + list(p.interiors):
                    pts, prec = [], None
                    for x, y, *_ in r.coords:
                        c = (round((x - x0) / kx), round((y - y0) / ky))
                        if c != prec:
                            pts.append(c)
                            prec = c
                    if len(pts) < 4:
                        continue
                    delta = [list(pts[0])] + [[pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]]
                                              for i in range(1, len(pts))]
                    arcs.append(delta)
                    anneaux.append([len(arcs) - 1])
                if anneaux:
                    polys.append(anneaux)
            if polys:
                gs.append({"type": "MultiPolygon", "arcs": polys, "properties": {prop: code}})
        out[nom] = {"type": "GeometryCollection", "geometries": gs}
    return {"type": "Topology", "transform": {"scale": [kx, ky], "translate": [x0, y0]}, "objects": out, "arcs": arcs}


def ecrire_fond_atlas(ref) -> bool:
    """Fond de carte de l'atlas (intercommunalités, départements et régions), fabriqué à partir des contours de
    l'IGN. Les régions sont la réunion de leurs départements simplifiés, leurs frontières suivent donc exactement
    celles des départements."""
    import shapely
    f = fonds(ref)
    if not f:
        return False
    region = ref.deps.set_index("code")["reg"]
    par_reg = {}
    for d, g in f["atlas_dep"].items():
        if d in region.index:
            par_reg.setdefault(region[d], []).append(g)
    reg = {k: shapely.union_all(v) for k, v in par_reg.items()}
    topo = topojson({"epci": ("epci", f["atlas_epci"]), "dep": ("dep", f["atlas_dep"]), "reg": ("reg", reg)})
    FOND_ATLAS.write_text(json.dumps(topo, separators=(",", ":")), encoding="utf-8")
    log.info("fond de carte de l'atlas écrit (%.1f Mo)", FOND_ATLAS.stat().st_size / 1e6)
    return True


def classe(rapport):
    """Indice de la classe d'une densité rapportée à la moyenne des territoires du même niveau (rapport = densité /
    moyenne)."""
    if rapport is None or not math.isfinite(rapport) or rapport <= 0:
        return 0
    return next(i for i, (borne, _c, _l) in enumerate(CLASSES) if borne is not None and rapport < borne)


def _anneaux(g):
    polys = getattr(g, "geoms", [g])
    for p in polys:
        if p.is_empty or not hasattr(p, "exterior"):
            continue
        yield list(p.exterior.coords)
        for i in p.interiors:
            yield list(i.coords)


MARQUE_CMP = "aucun psychiatre déclaré, mais au moins un CMP selon FINESS"


def carte(geoms: dict, rapports: dict, etiquettes: dict, titre: str, largeur=560, hauteur_max=520, legende=True,
          marques=None, legende_marque=MARQUE_CMP) -> str:
    """Carte choroplèthe. geoms {code: géométrie}, rapports {code: densité / densité France},
    etiquettes {code: texte court posé sur le territoire}."""
    geoms = {k: g for k, g in geoms.items() if g is not None and not g.is_empty}
    if not geoms:
        return ""
    xs0, ys0, xs1, ys1 = zip(*(g.bounds for g in geoms.values()))
    x0, x1, y0, y1 = min(xs0), max(xs1), min(ys0), max(ys1)
    k = math.cos(math.radians((y0 + y1) / 2))
    lw, lh = (x1 - x0) * k or 1e-6, (y1 - y0) or 1e-6
    marques = [c for c in (marques or []) if c in geoms]
    marge, leg = 8, (22 * (len(CLASSES) + (1 if marques else 0)) + 12) if legende else 0
    s = min((largeur - 2 * marge) / lw, (hauteur_max - 2 * marge) / lh)
    h = lh * s + 2 * marge
    P = lambda x, y: (marge + (x - x0) * k * s, marge + (y1 - y) * s)  # noqa: E731
    el = []
    for code, g in geoms.items():
        c = CLASSES[classe(rapports.get(code))][1]
        d = _trace_relatif(_anneaux(g), P)
        r_ = rapports.get(code)
        info = nom(code) + (f", indice {nombre(r_ * 100)} (moyenne = 100)" if r_ is not None and math.isfinite(r_) else "")
        el.append(f'<path d="{d}" fill="{c}" fill-rule="evenodd" stroke="var(--bg, #FFFFFF)" stroke-width=".8">'
                  f'<title>{escape(info)}</title></path>')
    for code, t in etiquettes.items():
        if code in geoms:
            px, py = P(*geoms[code].representative_point().coords[0])
            el.append(f'<text x="{px:.1f}" y="{py + 4:.1f}" text-anchor="middle" font-size="11" font-weight="600" '
                      f'fill="{ENCRE}" stroke="var(--bg, #FFFFFF)" stroke-width="3" paint-order="stroke">{escape(str(t))}</text>')
    # signal d'une limite des données posé sur le territoire, sans changer sa couleur (demande de Lucas du 9 octobre)
    fragiles = signaux(geoms)
    for lab in sorted(set(fragiles.values())):
        el.append(symbole_fragile(largeur - 10, 10, lab))
    if legende and fragiles:
        leg += sum(22 + 14 * (len(lignes_signal(lab, largeur, marge)) - 1) for lab in set(fragiles.values()))
    for code in marques:
        px, py = P(*geoms[code].representative_point().coords[0])
        el.append(f'<circle cx="{px + 13:.1f}" cy="{py - 9:.1f}" r="4.5" fill="var(--bg, #FFFFFF)" stroke="{ENCRE}" '
                  f'stroke-width="1.6"><title>{escape(nom(code))}, {escape(legende_marque)}</title></circle>')
    for i, (_b, c, lab) in enumerate(CLASSES if legende else []):
        y = h + 8 + 22 * i
        el.append(f'<rect x="{marge}" y="{y:.1f}" width="16" height="14" fill="{c}" stroke="{LIGNE}"/>')
        el.append(f'<text x="{marge + 24}" y="{y + 11:.1f}" font-size="12" fill="{DISCRET}">{escape(lab)}</text>')
    if legende and fragiles:
        legende_signaux(el, marge, h + 8 + 22 * (len(CLASSES) + (1 if marques else 0)), fragiles.values(), largeur)
    if legende and marques:
        y = h + 8 + 22 * len(CLASSES)
        el.append(f'<circle cx="{marge + 8}" cy="{y + 7:.1f}" r="4.5" fill="var(--bg, #FFFFFF)" stroke="{ENCRE}" '
                  f'stroke-width="1.6"/>')
        el.append(f'<text x="{marge + 24}" y="{y + 11:.1f}" font-size="12" fill="{DISCRET}">{escape(legende_marque)}</text>')
    H = h + leg
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largeur} {H:.0f}" role="img" '
            f'aria-label="{escape(titre)}" font-family="Work Sans, system-ui, sans-serif">'
            f"<title>{escape(titre)}</title>" + "".join(el) + "</svg>")


def reglette(lignes: list[dict], titre: str, largeur=640) -> str:
    """Position d'un territoire parmi les autres, une ligne par profession. Chaque dict porte libelle,
    valeurs (densités de tous les territoires comparés) et valeur (celle du territoire). Échelle
    logarithmique, pour que quelques territoires très denses n'écrasent pas les autres."""
    lignes = [l for l in lignes if len(l["valeurs"]) and l["valeur"] is not None and math.isfinite(l["valeur"])]
    if not lignes:
        return ""
    import numpy as np
    g, d, hl = 190, 70, 34
    H = 30 + hl * len(lignes) + 26
    el = []
    for i, l in enumerate(lignes):
        v = np.asarray([x for x in l["valeurs"] if x > 0], float)
        if not len(v):
            continue
        lo, hi = math.log10(v.min()), math.log10(v.max())
        X = lambda x: g + ((math.log10(max(x, v.min())) - lo) / ((hi - lo) or 1)) * (largeur - g - d)  # noqa: E731
        y = 30 + hl * i + 12
        q1, me, q3 = np.percentile(v, [25, 50, 75])
        el.append(f'<text x="{g - 10}" y="{y + 4}" text-anchor="end" font-size="12" fill="{ENCRE}">{escape(l["libelle"])}</text>')
        el.append(f'<line x1="{g}" y1="{y}" x2="{largeur - d}" y2="{y}" stroke="{LIGNE}" stroke-width="2"/>')
        el.append(f'<rect x="{X(q1):.1f}" y="{y - 5}" width="{max(X(q3) - X(q1), 1):.1f}" height="10" fill="{VIOLET_PALE}"/>')
        el.append(f'<line x1="{X(me):.1f}" y1="{y - 8}" x2="{X(me):.1f}" y2="{y + 8}" stroke="{DISCRET}" stroke-width="2"/>')
        c = OCRE if l["valeur"] < me else VIOLET[0]
        el.append(f'<circle cx="{X(l["valeur"]):.1f}" cy="{y}" r="6" fill="{c}" stroke="var(--bg, #FFFFFF)" stroke-width="1.5"/>')
        el.append(f'<text x="{largeur - d + 8}" y="{y + 4}" font-size="12" fill="{ENCRE}">{nombre(l["valeur"], 1 if l["valeur"] >= 1 else 2)}</text>')
    el.append(f'<text x="{g}" y="18" font-size="11" fill="{DISCRET}">la moins dotée</text>')
    el.append(f'<text x="{largeur - d}" y="18" text-anchor="end" font-size="11" fill="{DISCRET}">la mieux dotée</text>')
    y = 30 + hl * len(lignes) + 8
    el.append(f'<rect x="{g}" y="{y}" width="14" height="8" fill="{VIOLET_PALE}"/>'
              f'<text x="{g + 20}" y="{y + 8}" font-size="11" fill="{DISCRET}">moitié centrale des territoires</text>'
              f'<line x1="{g + 214}" y1="{y - 2}" x2="{g + 214}" y2="{y + 10}" stroke="{DISCRET}" stroke-width="2"/>'
              f'<text x="{g + 222}" y="{y + 8}" font-size="11" fill="{DISCRET}">milieu</text>'
              f'<circle cx="{g + 284}" cy="{y + 4}" r="5" fill="{OCRE}"/><circle cx="{g + 296}" cy="{y + 4}" r="5" fill="{VIOLET[0]}"/>'
              f'<text x="{g + 306}" y="{y + 8}" font-size="11" fill="{DISCRET}">ce territoire</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largeur} {H}" role="img" '
            f'aria-label="{escape(titre)}" font-family="Work Sans, system-ui, sans-serif">'
            f"<title>{escape(titre)}</title>" + "".join(el) + "</svg>")


# ---------------------------------------------------------------- diagrammes de l'audit du 4 octobre 2026
def _legende(el, x, y, largeur):
    """Légende des classes, sur une ou deux lignes selon la largeur."""
    colonnes = 2 if largeur < 700 else 3
    pas = largeur / colonnes
    for i, (_b, c, lab) in enumerate(CLASSES):
        xx, yy = x + (i % colonnes) * pas, y + (i // colonnes) * 20
        el.append(f'<rect x="{xx:.0f}" y="{yy}" width="14" height="12" fill="{c}" stroke="{LIGNE}"/>')
        el.append(f'<text x="{xx + 20:.0f}" y="{yy + 10}" font-size="11" fill="{DISCRET}">{escape(lab)}</text>')
    return y + 20 * ((len(CLASSES) + colonnes - 1) // colonnes)


def _svg(largeur, hauteur, titre, el):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largeur} {hauteur:.0f}" role="img" '
            f'aria-label="{escape(titre)}" font-family="Work Sans, system-ui, sans-serif">'
            f"<title>{escape(titre)}</title>" + "".join(el) + "</svg>")


OUTRE_MER = ["971", "972", "973", "974", "976"]


def carte_france(geoms: dict, rapports: dict, titre: str, largeur=560, legende=True, couleurs=None,
                 legende_fn=None, suicide=False) -> str:
    """Carte classique des départements, Hexagone et Corse, avec l'outre-mer en médaillons sous la carte."""
    metro = {k: g for k, g in geoms.items() if k not in OUTRE_MER and g is not None}
    if not metro:
        return ""
    el, marques = [], []
    sig = signaux(geoms, suicide)
    groupes: dict = {}   # (libellé du signal, médaillon) -> géométries et projection, un contour et un symbole par groupe

    def dessine(gs, x0, y0, w, h):
        xs0, ys0, xs1, ys1 = zip(*(g.bounds for g in gs.values()))
        bx0, bx1, by0, by1 = min(xs0), max(xs1), min(ys0), max(ys1)
        k = math.cos(math.radians((by0 + by1) / 2))
        s = min(w / ((bx1 - bx0) * k or 1e-6), h / ((by1 - by0) or 1e-6))
        for code, g in gs.items():
            c = (couleurs.get(code) or "var(--nodata, #E3E4E8)") if couleurs is not None else CLASSES[classe(rapports.get(code))][1]
            d = _trace_relatif(_anneaux(g), lambda x, y: (x0 + (x - bx0) * k * s, y0 + (by1 - y) * s))
            r_ = rapports.get(code) if rapports else None
            info = nom(code) + (f", indice {nombre(r_ * 100)} (moyenne = 100)" if r_ is not None and
                                isinstance(r_, (int, float)) and math.isfinite(r_) else "")
            el.append(f'<path data-code="{escape(code)}" d="{d}" fill="{c}" fill-rule="evenodd" stroke="var(--bg, #FFFFFF)" '
                      f'stroke-width=".6"><title>{escape(info)}</title></path>')
            if code in sig:
                proj = (x0, y0, bx0, by1, k, s)
                groupes.setdefault((sig[code], proj), []).append(g)
    dessine(metro, 8, 8, largeur - 16, largeur - 40)
    y = largeur - 20
    w = (largeur - 16) / len(OUTRE_MER)
    for i, code in enumerate(OUTRE_MER):
        if geoms.get(code) is not None:
            dessine({code: geoms[code]}, 8 + i * w + 6, y, w - 12, 70)
            el.append(f'<text x="{8 + i * w + w / 2:.0f}" y="{y + 84}" text-anchor="middle" font-size="10" '
                      f'fill="{DISCRET}">{code}</text>')
    om = any(geoms.get(c) is not None for c in OUTRE_MER)
    debut = y + 96 if om else largeur - 4   # sans médaillons d'outre-mer, la légende suit l'Hexagone
    fin = (legende_fn(el, 8, debut, largeur - 16) if legende_fn else
           _legende(el, 8, debut, largeur - 16) if legende else debut - 6)
    # contour ocre du groupe de territoires concernés et symbole en son centre, la couleur des territoires ne change pas
    from shapely.ops import unary_union
    for (lab, (x0, y0, bx0, by1, k, s)), gs in groupes.items():
        u = unary_union(gs)
        tr = lambda x, y: (x0 + (x - bx0) * k * s, y0 + (by1 - y) * s)  # noqa: E731
        marques.append(f'<path d="{_trace_relatif(_anneaux(u), tr)}" fill="none" stroke="{FRAGILE}" stroke-width="1.6" '
                       f'stroke-linejoin="round" pointer-events="none"/>')
        px, py, *_ = u.representative_point().coords[0]
        marques.append(symbole_fragile(*tr(px, py), lab))
    el += marques
    if legende and marques:
        fin = legende_signaux(el, 8, fin + 4, sorted({lab for lab, _ in groupes}), largeur)
    return _svg(largeur, fin + 6, titre, el)


def petits_multiples(geoms: dict, series: list, titre: str, colonnes=2, largeur=760) -> str:
    """Même carte des départements pour plusieurs professions (audit 4.7), mêmes classes de couleur, une seule
    légende. series, liste de (nom, {code: rapport à la moyenne})."""
    import re as _re
    if not series:
        return ""
    w = largeur / colonnes
    el, y, hmax = [], 0.0, 0.0
    for i, (nom, rap) in enumerate(series):
        col = i % colonnes
        if col == 0 and i:
            y += hmax + 34
            hmax = 0.0
        svg = carte_france(geoms, rap, nom, largeur=560, legende=False)
        if not svg:
            continue
        vb = _re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
        lw, lh = float(vb.group(1)), float(vb.group(2))
        ech = (w - 12) / lw
        h = lh * ech
        hmax = max(hmax, h)
        x0 = col * w
        el.append(f'<text x="{x0 + 6:.0f}" y="{y + 16:.0f}" font-size="14" font-weight="600" fill="{ENCRE}">'
                  f'{escape(nom)}</text>')
        interieur = _re.sub(r"^<svg[^>]*>", "", svg).rsplit("</svg>", 1)[0]
        interieur = _re.sub(r"<title>.*?</title>", "", interieur, count=1)
        el.append(f'<svg x="{x0 + 6:.0f}" y="{y + 24:.0f}" width="{w - 12:.0f}" height="{h:.0f}" '
                  f'viewBox="0 0 {lw:.0f} {lh:.0f}">{interieur}</svg>')
    fin = _legende(el, 8, y + hmax + 40, largeur - 16)
    sig = signaux(geoms)
    if sig:
        fin = legende_signaux(el, 8, fin + 4, sig.values(), largeur)
    return _svg(largeur, fin + 6, titre, el)


# temps de trajet par commune (audit 4.6), du plus court au plus long, gris neutre puis ocre de plus en plus foncé
CLASSES_TEMPS = [(10, "var(--d3, #E9E7EC)", "moins de 10 minutes"),
                 (20, "var(--d2, #E6D3A6)", "de 10 à 20 minutes"),
                 (30, "var(--d1, #B88A2E)", "de 20 à 30 minutes"),
                 (math.inf, "var(--d0, #7A4E00)", "30 minutes et plus")]


def _trace_relatif(anneaux, P) -> str:
    """Tracé SVG compact, coordonnées entières relatives, points répétés supprimés."""
    morceaux = []
    for r in anneaux:
        pts, prec = [], None
        for x, y, *_ in r:
            q = tuple(round(v) for v in P(x, y))
            if q != prec:
                pts.append(q)
                prec = q
        if len(pts) < 3:
            continue
        d = [f"M{pts[0][0]},{pts[0][1]}l"]
        d += [f"{b[0] - a[0]},{b[1] - a[1]}" for a, b in zip(pts, pts[1:])]
        morceaux.append(d[0] + " ".join(d[1:]) + "z")
    return "".join(morceaux)


def carte_temps(geoms: dict, minutes: dict, titre: str, largeur=560, hauteur_max=520) -> str:
    """Carte des communes d'un département selon le temps médian de leurs habitants jusqu'à l'équipement le plus
    proche, en quatre classes. Une commune sans valeur reste en gris clair."""
    geoms = {k: g for k, g in geoms.items() if g is not None and not g.is_empty}
    if not geoms or not any(minutes.get(k) is not None for k in geoms):
        return ""
    xs0, ys0, xs1, ys1 = zip(*(g.bounds for g in geoms.values()))
    x0, x1, y0, y1 = min(xs0), max(xs1), min(ys0), max(ys1)
    k = math.cos(math.radians((y0 + y1) / 2))
    lw, lh = (x1 - x0) * k or 1e-6, (y1 - y0) or 1e-6
    marge = 8
    s = min((largeur - 2 * marge) / lw, (hauteur_max - 2 * marge) / lh)
    h = lh * s + 2 * marge
    P = lambda x, y: (marge + (x - x0) * k * s, marge + (y1 - y) * s)  # noqa: E731
    el = ['<g fill-rule="evenodd" stroke="var(--bg, #FFFFFF)" stroke-width=".4">']
    for code, g in geoms.items():
        m = minutes.get(code)
        c = ("var(--nodata, #E3E4E8)" if m is None or not math.isfinite(m) else
             next(col for borne, col, _l in CLASSES_TEMPS if m < borne))
        d = _trace_relatif(_anneaux(g), P)
        if d:
            info = nom(code) + (f", {nombre(m)} min" if m is not None and math.isfinite(m) else ", non couverte")
            el.append(f'<path d="{d}" fill="{c}"><title>{escape(info)}</title></path>')
    el.append("</g>")
    for i, (_b, c, lab) in enumerate(CLASSES_TEMPS):
        xx, yy = marge + (i % 2) * (largeur / 2), h + 8 + 20 * (i // 2)
        el.append(f'<rect x="{xx:.0f}" y="{yy:.0f}" width="14" height="12" fill="{c}" stroke="{LIGNE}"/>')
        el.append(f'<text x="{xx + 20:.0f}" y="{yy + 10:.0f}" font-size="11" fill="{DISCRET}">{escape(lab)}</text>')
    return _svg(largeur, h + 8 + 20 * 2 + 4, titre, el)


def legende_html() -> str:
    """Légende des classes en HTML, qui garde une taille lisible quand la carte est réduite."""
    return ('<ul class="legende">' + "".join(f'<li><span style="background:{c}"></span>{escape(lab)}</li>'
                                              for _b, c, lab in CLASSES) + "</ul>")


def grille_tuiles(geoms: dict) -> dict:
    """Place chaque département de l'Hexagone sur une grille régulière, au plus près de sa position réelle
    (affectation optimale par la méthode hongroise). Les départements d'outre-mer forment une ligne à part."""
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    metro = {k: g for k, g in geoms.items() if k not in OUTRE_MER and g is not None}
    codes = sorted(metro)
    pts = np.array([metro[c].representative_point().coords[0] for c in codes])
    pts[:, 0] *= math.cos(math.radians(46.5))
    colonnes, lignes = 12, 11
    x0, x1, y0, y1 = pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max()
    cases = np.array([(x0 + (x1 - x0) * i / (colonnes - 1), y1 - (y1 - y0) * j / (lignes - 1))
                      for j in range(lignes) for i in range(colonnes)])
    cout = ((pts[:, None, :] - cases[None, :, :]) ** 2).sum(-1)
    r, c = linear_sum_assignment(cout)
    pos = {codes[i]: (int(j % colonnes), int(j // colonnes)) for i, j in zip(r, c)}
    for i, code in enumerate(OUTRE_MER):
        pos[code] = (i, lignes + 1)
    return pos


def carte_tuiles(pos: dict, rapports: dict, titre: str, largeur=560, legende=True) -> str:
    """Carte en tuiles, un carré de même taille par département, quel que soit son territoire."""
    if not pos:
        return ""
    colonnes = max(x for x, _y in pos.values()) + 1
    lignes = max(y for _x, y in pos.values()) + 1
    cote = (largeur - 16) / colonnes
    el = []
    sig = signaux(pos)
    for code, (x, y) in pos.items():
        c = CLASSES[classe(rapports.get(code))][1]
        px, py = 8 + x * cote, 8 + y * cote
        el.append(f'<rect data-code="{escape(code)}" x="{px:.1f}" y="{py:.1f}" width="{cote - 2:.1f}" '
                  f'height="{cote - 2:.1f}" rx="3" fill="{c}"><title>{escape(nom(code))}</title></rect>')
        sombre = classe(rapports.get(code)) in (0, len(CLASSES) - 1)
        el.append(f'<text x="{px + (cote - 2) / 2:.1f}" y="{py + (cote - 2) / 2 + 4:.1f}" text-anchor="middle" '
                  f'font-size="{max(8, min(11, cote / 3.2)):.0f}" fill="{"var(--bg, #fff)" if sombre else ENCRE}">'
                  f'{escape(code)}</text>')
        if code in sig:
            el.append(symbole_fragile(px + cote - 7, py + 5, nom(code) + ", " + sig[code], 4.5))
    el.append(f'<text x="8" y="{8 + (lignes - 1) * cote - 6:.0f}" font-size="10" fill="{DISCRET}">Outre-mer</text>')
    fin = _legende(el, 8, 8 + lignes * cote + 6, largeur - 16) if legende else 8 + lignes * cote
    if legende and sig:
        fin = legende_signaux(el, 8, fin + 4, sig.values(), largeur)
    return _svg(largeur, fin + 6, titre, el)


def halteres(lignes: list[dict], titre: str, largeur=640) -> str:
    """Écart d'un territoire à la moyenne des territoires du même niveau, une ligne par indicateur. Chaque dict porte
    libelle, valeur (territoire), reference (moyenne), et facultativement q1 et q3 (moitié centrale des territoires
    comparés) et tous (valeurs des autres territoires, dessinées en petits points, audit 4.3). Échelle en indice, 100
    pour la moyenne, logarithmique pour que « deux fois moins » et « deux fois plus » soient à même distance."""
    lignes = [l for l in lignes if l.get("reference") and l.get("valeur") is not None
              and math.isfinite(l["valeur"]) and l["reference"] > 0]
    if not lignes:
        return ""
    g, d, h = 200, 60, 34
    lo, hi = math.log(.25), math.log(4)
    X = lambda v: g + (min(max(math.log(max(v, 1e-6)), lo), hi) - lo) / (hi - lo) * (largeur - g - d)  # noqa: E731
    el = []
    H = 34 + h * len(lignes) + 24
    for v, lab in [(.25, "4 fois moins"), (.5, "2 fois moins"), (1, "Moyenne"), (2, "2 fois plus"), (4, "4 fois plus")]:
        el.append(f'<line x1="{X(v):.1f}" y1="26" x2="{X(v):.1f}" y2="{H - 24}" stroke="{LIGNE}" '
                  f'stroke-width="{2 if v == 1 else 1}"/>')
        el.append(f'<text x="{X(v):.1f}" y="18" text-anchor="middle" font-size="10" fill="{DISCRET}">{lab}</text>')
    for i, l in enumerate(lignes):
        y = 34 + h * i + 10
        ind = l["valeur"] / l["reference"]
        el.append(f'<text x="{g - 10}" y="{y + 4}" text-anchor="end" font-size="12" fill="{ENCRE}">{escape(l["libelle"])}</text>')
        if l.get("q1") and l.get("q3"):
            a, b = X(l["q1"] / l["reference"]), X(l["q3"] / l["reference"])
            el.append(f'<rect x="{a:.1f}" y="{y - 5}" width="{max(b - a, 1):.1f}" height="10" fill="{VIOLET_PALE}" rx="2"/>')
        # les autres territoires en petits points, décalés en hauteur de façon fixe pour qu'ils ne se recouvrent pas
        tous = sorted(l.get("tous") or [], key=lambda cv: cv[1])
        if tous:
            el.append(f'<g fill="{DISCRET}" fill-opacity=".45">' + "".join(
                f'<circle cx="{X(v / l["reference"]):.0f}" cy="{y + ((k * 7) % 5 - 2) * 2.4:.0f}" r="2">'
                f'<title>{escape(nom(c))}, {nombre(v, 1)}</title></circle>'
                for k, (c, v) in enumerate(tous)) + "</g>")
        c = OCRE if ind < 1 else VIOLET[0]
        el.append(f'<line x1="{X(1):.1f}" y1="{y}" x2="{X(ind):.1f}" y2="{y}" stroke="{c}" stroke-width="3"/>')
        el.append(f'<circle cx="{X(1):.1f}" cy="{y}" r="4" fill="var(--bg, #fff)" stroke="{DISCRET}" stroke-width="1.5"/>')
        el.append(f'<circle cx="{X(ind):.1f}" cy="{y}" r="6" fill="{c}"/>')
        el.append(f'<text x="{largeur - d + 6}" y="{y + 4}" font-size="11" fill="{ENCRE}">{nombre(ind * 100)}</text>')
    y = H - 10
    el.append(f'<circle cx="{g + 6}" cy="{y - 4}" r="5" fill="{OCRE}"/><circle cx="{g + 18}" cy="{y - 4}" r="5" fill="{VIOLET[0]}"/>'
              f'<text x="{g + 28}" y="{y}" font-size="11" fill="{DISCRET}">ce territoire (indice, moyenne = 100)</text>'
              f'<circle cx="{g + 228}" cy="{y - 4}" r="2.4" fill="{DISCRET}" fill-opacity=".6"/>'
              f'<text x="{g + 236}" y="{y}" font-size="11" fill="{DISCRET}">les autres</text>'
              f'<rect x="{g + 300}" y="{y - 9}" width="14" height="9" fill="{VIOLET_PALE}"/>'
              f'<text x="{g + 320}" y="{y}" font-size="11" fill="{DISCRET}">moitié centrale</text>')
    return _svg(largeur, H, titre, el)


def unites(part: float, titre: str, phrase: str, largeur=520) -> str:
    """Graphique en unités, 100 personnes dont la part concernée est colorée (part entre 0 et 1)."""
    if part is None or not math.isfinite(part):
        return ""
    k = int(round(part * 100))
    pas, r = 24, 8
    el = [f'<text x="0" y="16" font-size="14" font-weight="600" fill="{ENCRE}">{escape(phrase)}</text>']
    for i in range(100):
        x, y = 12 + (i % 20) * pas, 40 + (i // 20) * (pas + 8)
        c = OCRE if i < k else LIGNE
        el.append(f'<circle cx="{x}" cy="{y}" r="{r * .55:.1f}" fill="{c}"/>'
                  f'<path d="M{x - r},{y + r + 7} Q{x},{y + 2} {x + r},{y + r + 7} Z" fill="{c}"/>')
    return _svg(largeur, 40 + 5 * (pas + 8) + 4, titre, el)
