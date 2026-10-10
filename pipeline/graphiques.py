"""Graphiques des rapports, en SVG, dans le style de l'atlas. Les couleurs passent par les variables CSS du
site (avec une valeur par défaut, pour qu'un fichier SVG ouvert seul reste lisible). Un graphique par
analyse, comme le veut le format commun du chantier 4. Les figures sont écrites dans
resultats/AAAA-MM-JJ/graphiques/ et insérées dans les pages du site à la place des marqueurs
<!--GRAPHIQUE nom--> du rapport."""
from __future__ import annotations

import math
from html import escape

import numpy as np
import pandas as pd

from . import config
from .lecture import nombre
from .util import log

ENCRE, DISCRET, LIGNE = "var(--ink, #1F2430)", "var(--muted, #5F6675)", "var(--line, #D9DCE3)"
VIOLET = ["var(--r5, #3E2563)", "var(--r4, #64458C)", "var(--r3, #8C6DAE)", "var(--r2, #B39BCB)"]
OCRE, OCRE_PALE, VIOLET_PALE = "var(--accent, #B07D0A)", "var(--d1, #B88A2E)", "var(--r1, #D5C6E3)"
PRINCIPALE = {"sm": "psychologue", "sante": "medecin_generaliste"}
LORENZ = {"sm": ["psychologue", "psychiatre", "psychotherapeute", "pedopsychiatre"],
          "sante": ["medecin_generaliste", "infirmier", "masseur_kinesitherapeute", "pediatre"]}


class Figure:
    """Petit outil de tracé, échelles linéaires ou logarithmiques et éléments SVG."""

    def __init__(self, w=640, h=380, marges=(48, 16, 16, 46)):
        self.w, self.h = w, h
        self.g, self.d, self.hh, self.b = marges   # gauche, droite, haut, bas
        self.el = []

    def echelles(self, x0, x1, y0, y1, xlog=False):
        self.x0, self.x1, self.y0, self.y1, self.xlog = x0, x1, y0, y1, xlog

    def X(self, v):
        if self.xlog:
            v, a, b = math.log10(max(v, 1e-9)), math.log10(self.x0), math.log10(self.x1)
        else:
            a, b = self.x0, self.x1
        return self.g + (v - a) / ((b - a) or 1) * (self.w - self.g - self.d)

    def Y(self, v):
        v = min(max(v, self.y0), self.y1)
        return self.h - self.b - (v - self.y0) / ((self.y1 - self.y0) or 1) * (self.h - self.hh - self.b)

    def ajout(self, s):
        self.el.append(s)

    def ligne(self, x1, y1, x2, y2, c=LIGNE, w=1, tirets=None):
        self.ajout(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{c}" stroke-width="{w}"'
                   + (f' stroke-dasharray="{tirets}"' if tirets else "") + "/>")

    def texte(self, x, y, t, ancre="start", c=DISCRET, taille=11, gras=False):
        self.ajout(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{ancre}" fill="{c}" font-size="{taille}"'
                   + (' font-weight="600"' if gras else "") + f">{escape(str(t))}</text>")

    def chemin(self, pts, c, w=1.5, remplir=None, tirets=None):
        d = "M" + "L".join(f"{self.X(x):.1f},{self.Y(y):.1f}" for x, y in pts)
        self.ajout(f'<path d="{d}" fill="{remplir or "none"}" stroke="{c}" stroke-width="{w}"'
                   + (f' stroke-dasharray="{tirets}"' if tirets else "") + "/>")

    def axes(self, xt, yt, fx=str, fy=str, titre_x="", titre_y=""):
        for v in yt:
            y = self.Y(v)
            self.ligne(self.g, y, self.w - self.d, y)
            self.texte(self.g - 6, y + 4, fy(v), "end")
        for v in xt:
            self.texte(self.X(v), self.h - self.b + 16, fx(v), "middle")
        self.ligne(self.g, self.h - self.b, self.w - self.d, self.h - self.b, DISCRET)
        if titre_x:
            self.texte(self.w - self.d, self.h - 6, titre_x, "end")
        if titre_y:
            self.texte(self.g, self.hh - 4 if self.hh > 14 else 11, titre_y)

    def svg(self, titre):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" role="img" '
                f'aria-label="{escape(titre)}" font-family="Work Sans, system-ui, sans-serif">'
                f"<title>{escape(titre)}</title>" + "".join(self.el) + "</svg>")


def pas_rond(v):
    """Pas de graduation lisible (1, 2 ou 5 fois une puissance de 10) proche de v."""
    e = 10 ** math.floor(math.log10(v))
    m = v / e
    return e * (10 if m > 7 else 5 if m > 3.5 else 2 if m > 1.5 else 1)


def _pct(v):
    return f"{nombre(v * 100)} %"


def graduations(vmax, n=4, v0=0.0):
    """Graduations rondes de v0 à vmax (pas de 1, 2 ou 5 fois une puissance de 10)."""
    pas = pas_rond((vmax - v0) / n)
    debut = math.ceil(v0 / pas) * pas
    return [round(debut + k * pas, 10) for k in range(int((vmax - debut) / pas) + 1)], pas


TRAITS = [None, None, "7 4", "2 3"]   # profession principale en trait plein épais, les autres différenciées


def lorenz(R, lab, cle):
    lz = R.get("lorenz")
    if not isinstance(lz, pd.DataFrame) or lz.empty:
        return None
    profs = [p for p in LORENZ[cle] if p in set(lz["prof"])]
    ineg = R.get("inegalites")
    gini = {}
    if isinstance(ineg, pd.DataFrame) and not ineg.empty:
        g0 = ineg[(ineg["niveau"] == "epci") & (ineg["mode"] == "all")]
        gini = dict(zip(g0["prof"], g0["gini"]))
    f = Figure(marges=(48, 200, 24, 46))
    f.echelles(0, 1, 0, 1)
    f.axes([0, .25, .5, .75, 1], [0, .25, .5, .75, 1], _pct, _pct, "Part cumulée des habitants", "Part cumulée des professionnels")
    for k, p in enumerate(profs):
        t = lz[(lz["niveau"] == "epci") & (lz["prof"] == p)].sort_values("x")
        pts = list(zip(t["x"], t["y"]))
        if k == 0:
            # aire entre la diagonale et la courbe, celle que mesure l'indice de Gini
            f.chemin([(0, 0)] + pts + [(1, 1), (0, 0)], "none", 0, remplir=VIOLET_PALE)
            f.el[-1] = f.el[-1].replace('fill="', 'fill-opacity=".35" fill="', 1)
        f.chemin(pts, VIOLET[k], 2.8 if k == 0 else 1.8, tirets=TRAITS[k])
        y = f.hh + 16 + 34 * k
        f.ligne(f.w - f.d + 12, y - 4, f.w - f.d + 40, y - 4, VIOLET[k], 2.8 if k == 0 else 1.8, TRAITS[k])
        f.texte(f.w - f.d + 48, y, lab.get(p, p), c=ENCRE, gras=k == 0)
        if p in gini:
            f.texte(f.w - f.d + 48, y + 14, f"indice de Gini {nombre(gini[p], 2)}")
    f.chemin([(0, 0), (1, 1)], DISCRET, 1, tirets="3 3")
    f.texte(f.X(.42), f.Y(.47), "répartition égale", c=DISCRET, taille=10)
    return f.svg("Courbes de Lorenz, répartition des professionnels entre intercommunalités")


def effet_ville(R, lab, ctxlab, cle, p=None):
    cc = R.get("correlations_contexte")
    p = p or PRINCIPALE[cle]
    if not isinstance(cc, pd.DataFrame) or "rho_partiel_densite" not in cc:
        return None
    t = cc[(cc["niveau"] == "epci") & (cc["mode"] == "all") & (cc["prof"] == p) & (cc["variable"] != "densite_pop")
           & cc["variable"].isin(ctxlab)].copy()
    t = t[t["variable"].isin([c[0] for c in config.CONTEXTE])].sort_values("rho_spearman", key=abs, ascending=False)
    if t.empty:
        return None
    bh = 11
    f = Figure(h=56 + len(t) * (2 * bh + 9), marges=(250, 20, 40, 28))
    f.echelles(-.8, .8, 0, 1)
    for v in [-.6, -.3, 0, .3, .6]:
        f.ligne(f.X(v), f.hh, f.X(v), f.h - f.b, DISCRET if v == 0 else LIGNE, 1, None if v == 0 else "3 3")
        f.texte(f.X(v), f.h - 8, nombre(v, 1), "middle")
    for k, (_, r) in enumerate(t.iterrows()):
        y0 = f.hh + k * (2 * bh + 9)
        f.texte(f.g - 8, y0 + bh + 3, ctxlab[r["variable"]], "end", ENCRE)
        for j, (v, c) in enumerate([(r["rho_spearman"], DISCRET), (r["rho_partiel_densite"], VIOLET[2])]):
            if pd.notna(v):
                x0, x1 = sorted([f.X(0), f.X(max(min(v, .8), -.8))])
                f.ajout(f'<rect x="{x0:.1f}" y="{y0 + j * bh:.1f}" width="{x1 - x0:.1f}" height="{bh - 2}" fill="{c}"/>')
    f.texte(8, 14, lab.get(p, p), c=ENCRE, gras=True)
    f.ajout(f'<rect x="8" y="22" width="12" height="8" fill="{DISCRET}"/>')
    f.texte(24, 30, "tous territoires")
    f.ajout(f'<rect x="130" y="22" width="12" height="8" fill="{VIOLET[2]}"/>')
    f.texte(146, 30, "à densité de population égale")
    return f.svg(f"Liens entre la densité de {lab.get(p, p).lower()} et le profil des habitants, avant et après "
                 f"retrait de l'effet ville")


def escalier(R, lab, cle, densite_nationale, p=None):
    """densite_nationale est la moyenne des intercommunalités, calculée comme les barres (somme des effectifs des
    intercommunalités rapportée à la population)."""
    es = R.get("escalier_social")
    p = p or PRINCIPALE[cle]
    if not isinstance(es, pd.DataFrame) or es.empty:
        return None
    t = es[(es["niveau"] == "epci") & (es["prof"] == p)].sort_values("decile")
    if t.empty:
        return None
    vmax = max(t["densite"].max(), densite_nationale) * 1.15
    f = Figure()
    f.echelles(.5, 10.5, 0, vmax)
    pas = pas_rond(vmax / 4)
    f.axes(range(1, 11), np.arange(0, vmax, pas), lambda v: str(v), lambda v: nombre(v, 1 if pas < 1 else 0),
           "Dixième de la population, du plus modeste au plus aisé", f"{lab.get(p, p)}s pour 10 000 habitants")
    largeur = (f.X(2) - f.X(1)) * .7
    for _, r in t.iterrows():
        x = f.X(r["decile"]) - largeur / 2
        c = OCRE_PALE if r["densite"] < densite_nationale else VIOLET[2]
        f.ajout(f'<rect x="{x:.1f}" y="{f.Y(r["densite"]):.1f}" width="{largeur:.1f}" '
                f'height="{f.Y(0) - f.Y(r["densite"]):.1f}" fill="{c}" rx="2"/>')
        f.texte(x + largeur / 2, f.Y(r["densite"]) - 5, nombre(r["densite"], 1), "middle", ENCRE, 10)
    f.ligne(f.g, f.Y(densite_nationale), f.w - f.d, f.Y(densite_nationale), OCRE, 1.5, "5 3")
    f.texte(f.w - f.d, f.Y(densite_nationale) - 5, f"Moyenne {nombre(densite_nationale, 1)}", "end", OCRE)
    return f.svg(f"Densité de {lab.get(p, p).lower()}s selon le niveau de vie des territoires")


def entonnoir(R, lab, cle, p=None):
    en, lim = R.get("entonnoir"), R.get("entonnoir_limites")
    p = p or PRINCIPALE[cle]
    if not isinstance(en, pd.DataFrame) or en.empty:
        return None
    t = en[(en["niveau"] == "epci") & (en["prof"] == p) & (en["population"] > 0)]
    g = lim[(lim["niveau"] == "epci") & (lim["prof"] == p)].sort_values("population")
    if t.empty or g.empty:
        return None
    dens = t["effectif"] / t["population"] * 1e4
    ymax = max(np.quantile(dens, .98), g["haut_95"].iloc[len(g) // 3]) * 1.1
    yt, pas = graduations(ymax)
    ymax = yt[-1] + pas * .5
    f = Figure(h=420, marges=(48, 16, 58, 46))
    f.echelles(t["population"].min(), t["population"].max(), 0, ymax, xlog=True)
    xt = [v for v in [1e3, 1e4, 1e5, 1e6, 1e7] if f.x0 <= v <= f.x1]
    f.axes(xt, yt, lambda v: nombre(v), lambda v: nombre(v, 0 if pas >= 1 else 1),
           "Habitants (échelle logarithmique)", f"{lab.get(p, p)}s pour 10 000 habitants")
    haut = [(r["population"], r["haut_95"]) for _, r in g.iterrows()]
    bas = [(r["population"], r["bas_95"]) for _, r in g.iterrows()][::-1]
    d = "M" + "L".join(f"{f.X(x):.1f},{f.Y(y):.1f}" for x, y in haut + bas) + "Z"
    f.ajout(f'<path d="{d}" fill="{VIOLET_PALE}" opacity=".3"/>')
    for k in ("bas_998", "haut_998"):
        f.chemin(list(zip(g["population"], g[k])), DISCRET, 1, tirets="3 3")
    taux = t["effectif"].sum() / t["population"].sum() * 1e4
    f.ligne(f.g, f.Y(taux), f.w - f.d, f.Y(taux), OCRE, 1.5)
    couleurs = {-2: "var(--d0, #7A4E00)", -1: OCRE_PALE, 0: DISCRET, 1: VIOLET[2], 2: VIOLET[0]}
    from .cartes import MAYOTTE, SIGNAL_MAYOTTE, nom, symbole_fragile
    for (_, r), v in zip(t.iterrows(), dens):
        cx, c = f.X(r["population"]), couleurs[int(r["statut"])]
        if str(r["code"]) in MAYOTTE and v <= ymax:
            f.ajout(symbole_fragile(cx, f.Y(v), f'{nom(r["code"])}, {SIGNAL_MAYOTTE}', 4.5))
            continue
        info = (f'<title>{escape(nom(r["code"]))}, {nombre(v, 1)} pour 10 000 habitants, '
                f'{nombre(r["population"])} habitants</title>')
        if v > ymax:   # territoire au-delà du cadre, signalé par un petit triangle en haut
            f.ajout(f'<path d="M{cx - 3:.1f},{f.hh + 5:.1f}L{cx + 3:.1f},{f.hh + 5:.1f}L{cx:.1f},{f.hh:.1f}Z" '
                    f'fill="{c}">{info}</path>')
        else:
            # territoires dans la norme en retrait, les écarts au hasard en avant
            f.ajout(f'<circle cx="{cx:.1f}" cy="{f.Y(v):.1f}" r="2.2" fill="{c}" '
                    f'fill-opacity="{.35 if int(r["statut"]) == 0 else .9}">{info}</circle>')
    leg = [(-2, "nettement en dessous"), (-1, "en dessous"), (0, "dans la norme"), (1, "au-dessus"),
           (2, "nettement au-dessus")]
    x = f.g
    for k, l in leg:
        f.ajout(f'<circle cx="{x + 4}" cy="12" r="4" fill="{couleurs[k]}"/>')
        f.texte(x + 12, 16, l, c=ENCRE, taille=10.5)
        x += 22 + 6.2 * len(l)
    f.ajout(f'<rect x="{f.g}" y="24" width="14" height="9" fill="{VIOLET_PALE}" opacity=".3"/>')
    f.texte(f.g + 20, 32, "limites à 95 %", taille=10.5)
    f.ligne(f.g + 120, 28, f.g + 142, 28, DISCRET, 1, "3 3")
    f.texte(f.g + 148, 32, "limites à 99,8 %", taille=10.5)
    f.ligne(f.g + 250, 28, f.g + 272, 28, OCRE, 1.5)
    f.texte(f.g + 278, 32, "moyenne des intercommunalités", taille=10.5)
    return f.svg(f"Diagramme en entonnoir, {lab.get(p, p).lower()}s par intercommunalité")


def quadrants(R, lab, ctxlab, p="psychiatre"):
    qd = R.get("quadrants")
    if not isinstance(qd, pd.DataFrame) or qd.empty:
        return None
    var = "suicides" if "suicides" in set(qd["variable"]) else qd["variable"].iloc[0]
    t = qd[(qd["prof"] == p) & (qd["variable"] == var)].dropna(subset=["quadrant"])
    if t.empty:
        return None
    xt, _px = graduations(t["valeur"].max() * 1.05, 5)
    yt, py = graduations(t["densite"].quantile(.98) * 1.1)
    f = Figure(marges=(48, 16, 24, 46))
    f.echelles(0, xt[-1] + _px * .3, 0, yt[-1] + py * .4)
    f.axes(xt, yt, lambda v: nombre(v, 0), lambda v: nombre(v, 1),
           ctxlab.get(var, var), f"{pluriel_simple(lab.get(p, p))} pour 10 000 habitants")
    mx, my = t["mediane_indicateur"].iloc[0], t["mediane_densite"].iloc[0]
    f.ligne(f.X(mx), f.hh, f.X(mx), f.h - f.b, OCRE, 1.2, "4 3")
    f.ligne(f.g, f.Y(my), f.w - f.d, f.Y(my), OCRE, 1.2, "4 3")
    f.texte(f.w - f.d - 4, f.h - f.b - 6, "indicateur élevé, offre faible", "end", OCRE)
    if var == "suicides":
        from .cartes import symbole_fragile as _sf, SIGNAL_SUICIDE
        f.ajout(_sf(f.g + 10, f.hh + 8, SIGNAL_SUICIDE, 5))
        f.texte(f.g + 20, f.hh + 12, SIGNAL_SUICIDE, taille=10.5)
    from .cartes import nom, signaux, symbole_fragile
    sig = signaux(t["code"], suicide=var == "suicides")
    for _, r in t.iterrows():
        if r["code"] in sig:
            f.ajout(symbole_fragile(f.X(r["valeur"]), f.Y(min(r["densite"], f.y1)),
                                    f'{nom(r["code"])}, {sig[r["code"]]}', 5))
            continue
        c = "var(--d0, #7A4E00)" if r["quadrant"] == "besoin+offre-" else VIOLET[2]
        f.ajout(f'<circle cx="{f.X(r["valeur"]):.1f}" cy="{f.Y(min(r["densite"], f.y1)):.1f}" r="3.2" fill="{c}" '
                f'fill-opacity=".8"><title>{escape(nom(r["code"]))}, {nombre(r["valeur"], 1)} et '
                f'{nombre(r["densite"], 2)} pour 10 000 habitants</title></circle>')
    return f.svg(f"Départements selon l'indicateur « {ctxlab.get(var, var).lower()} » et la densité "
                 f"{'de ' if pluriel_simple(lab.get(p, p))[0] not in 'AEIOUÉ' else 'd’'}"
                 f"{pluriel_simple(lab.get(p, p)).lower()}")


def porte(R, lab, cle, p=None):
    """Barres empilées, répartition par grand secteur selon la classe de densité de population."""
    from .analyses import CLASSES_DENSITE
    po = R.get("porte_offre")
    p = p or PRINCIPALE[cle]
    if not isinstance(po, pd.DataFrame) or po.empty or p not in set(po["prof"]):
        return None
    t = po[po["prof"] == p].pivot_table(index="classe", columns="groupe", values="part", fill_value=0)
    classes = [c[2] for c in CLASSES_DENSITE if c[2] in t.index]
    groupes = [g for _m, g in config.SECTEURS_GROUPES if g in t.columns] + \
              ([config.SECTEUR_AUTRE] if config.SECTEUR_AUTRE in t.columns else [])
    couleurs = [VIOLET[0], VIOLET[1], VIOLET[2], OCRE, "var(--d2, #E6D3A6)", "var(--nodata, #E3E4E8)"]
    bh, h = 30, 70 + len(classes) * 44
    f = Figure(h=h, marges=(250, 20, 56, 20))
    f.echelles(0, 1, 0, 1)
    for k, c in enumerate(classes):
        y = f.hh + k * 44
        f.texte(f.g - 8, y + bh / 2 + 4, c, "end", ENCRE)
        x0 = 0.0
        for j, g in enumerate(groupes):
            v = float(t.at[c, g])
            if v > 0:
                f.ajout(f'<rect x="{f.X(x0):.1f}" y="{y}" width="{f.X(x0 + v) - f.X(x0):.1f}" height="{bh}" '
                        f'fill="{couleurs[j % len(couleurs)]}"><title>{escape(g)}, {nombre(v * 100)} %</title></rect>')
                if v >= .08:
                    # texte foncé sur les segments pâles ou neutres, clair sur les segments colorés
                    f.texte(f.X(x0) + 4, y + bh / 2 + 4, f"{nombre(v * 100)} %",
                            c=ENCRE if j % len(couleurs) >= 4 else "var(--bg, #fff)", taille=10)
            x0 += v
    for j, g in enumerate(groupes):   # légende
        ligne, col = divmod(j, 3)
        xx, yy = 8 + col * 210, 12 + ligne * 18
        f.ajout(f'<rect x="{xx}" y="{yy - 8}" width="10" height="10" fill="{couleurs[j % len(couleurs)]}"/>')
        f.texte(xx + 14, yy + 1, g.split(" (")[0], taille=10)
    return f.svg(f"Secteurs d'exercice des {lab.get(p, p).lower()}s selon la densité de population")


def distances(R, lab, cle):
    """Part de la population à moins de x km du professionnel le plus proche, courbes cumulées."""
    tc = R.get("accessibilite_communes")
    if not isinstance(tc, pd.DataFrame) or tc.empty:
        return None
    profs = [p for p in LORENZ[cle] if p in set(tc["prof"])][:4]
    f = Figure(marges=(48, 170, 24, 46))
    xmax = 40
    f.echelles(0, xmax, 0, 1)
    f.axes([0, 5, 10, 20, 30, 40], [0, .25, .5, .75, 1], lambda v: f"{int(v)} km", _pct,
           "Distance à vol d'oiseau du professionnel le plus proche", "Part des habitants")
    for v in (5, 10, 20, 30):
        f.ligne(f.X(v), f.hh, f.X(v), f.h - f.b, LIGNE, 1, "3 3")
    xs = np.linspace(0, xmax, 161)
    for k, p in enumerate(profs):
        t = tc[tc["prof"] == p]
        o = np.argsort(t["distance_km"].to_numpy())
        d, w = t["distance_km"].to_numpy()[o], t["population"].to_numpy()[o]
        cum = np.cumsum(w) / w.sum()
        ys = np.interp(xs, d, cum, left=cum[0] if len(cum) else 0)
        f.chemin(list(zip(xs, ys)), VIOLET[k], 2.8 if k == 0 else 1.8, tirets=TRAITS[k])
        y = f.hh + 16 + 24 * k
        f.ligne(f.w - f.d + 12, y - 4, f.w - f.d + 40, y - 4, VIOLET[k], 2.8 if k == 0 else 1.8, TRAITS[k])
        f.texte(f.w - f.d + 48, y, lab.get(p, p), c=ENCRE, gras=k == 0)
    return f.svg("Part des habitants selon la distance au professionnel le plus proche")


CARTE_PRINCIPALE = {"sm": "psychiatre", "sante": "medecin_generaliste"}
# professions proposées sous les figures qui n'en montrent qu'une (boutons de la version en ligne)
VARIANTES = {"sm": ["psychologue", "psychiatre", "pedopsychiatre", "psychotherapeute"],
             "sante": ["medecin_generaliste", "infirmier", "masseur_kinesitherapeute", "orthophoniste",
                       "chirurgien_dentiste", "sage_femme", "pediatre"]}


def marquer(svg: str, libelle: str) -> str:
    """Nom de la variante porté par la figure (attribut data-variante de l'élément svg), lu par le site."""
    return svg.replace("<svg ", f'<svg data-variante="{escape(libelle)}" ', 1)
# petits multiples (audit 4.7), professions principales de chaque famille, mêmes classes de couleur
MULTIPLES = {"sm": ["psychologue", "psychiatre", "psychotherapeute", "q_psychiatrie_enfant"],
             "sante": ["medecin_generaliste", "infirmier", "masseur_kinesitherapeute", "orthophoniste",
                       "chirurgien_dentiste", "sage_femme"]}
UNITES = {"sm": ("psychiatre_liberal", "d'un psychiatre libéral"), "sante": ("urgences", "d'un service d'urgences")}


def cartes_nationales(agg, ref, lab, R):
    """Carte classique et carte en tuiles des départements pour la profession principale de chaque famille,
    et graphique en unités des habitants éloignés de plus de 20 minutes par la route."""
    from . import cartes
    from .analyses import tables
    out = {}
    try:
        f = cartes.fonds(ref)
    except Exception:  # noqa: BLE001
        f = None
    n, d, pop = tables(agg, ref, "dep", "all")
    if f:
        pos = cartes.grille_tuiles(f["dep"])
        for cle, p in CARTE_PRINCIPALE.items():
            if p not in d:
                continue
            fr = n[p].sum() / pop.sum() * 1e4
            rap = (d[p] / fr).to_dict()
            nom = pluriel_simple(lab.get(p, p))
            out[f"carte_dep_{cle}"] = cartes.carte_france(f["atlas_dep"], rap, f"{nom} pour 10 000 habitants, par département, "
                                                                         f"comparés à la moyenne des départements")
            out[f"tuiles_dep_{cle}"] = cartes.carte_tuiles(pos, rap, "Même carte en tuiles, un carré par département")
        for cle, profs in MULTIPLES.items():
            courts = {"q_psychiatrie_enfant": "Psychiatres qualifiés pour l'enfant"}
            series = [(courts.get(p) or pluriel_simple(lab.get(p, p)), (d[p] / (n[p].sum() / pop.sum() * 1e4)).to_dict())
                      for p in profs if p in d and n[p].sum() > 0]
            if len(series) > 1:
                out[f"multiples_{cle}"] = cartes.petits_multiples(
                    f["atlas_dep"], series, "Professions principales côte à côte, densité par département comparée à la "
                    "moyenne des départements, mêmes classes de couleur", colonnes=2 if len(series) <= 4 else 3)
    ta = R.get("temps_acces")
    if isinstance(ta, pd.DataFrame) and not ta.empty:
        fr = ta[ta["niveau"] == "FR"].set_index("equipement")
        for cle, (e, quoi) in UNITES.items():
            if e in fr.index:
                v = fr.at[e, "part_population_a_plus_de_20_min"]
                out[f"unites_{cle}"] = cartes.unites(v, "Habitants à plus de 20 minutes par la route",
                                                     f"Sur 100 habitants, {round(v * 100)} vivent à plus de 20 minutes {quoi}")
    return out


def pluriel_simple(lib):
    from .lecture import pluriel
    return pluriel(lib).capitalize()


ETAPES_PARCOURS = [
    # colonne, intitulé de l'étape, raison de l'écart avec l'étape précédente
    ("inscrits", "Inscrits au répertoire", ""),
    ("avec_activite", "Avec une activité déclarée", "sans activité déclarée"),
    ("avec_lieu", "Avec un lieu d'exercice", "sans lieu fixe (remplacements, exercice sans site)"),
    ("dans_densites", "Comptés dans les densités", "seulement des activités sans soins à la population"),
]


def parcours(agg, lab, prof):
    """Du répertoire aux densités, une barre par étape et, sous chacune, ce qui est écarté et pourquoi."""
    t = agg.parcours
    if not isinstance(t, pd.DataFrame) or prof not in set(t["prof"]):
        return None
    r = t.set_index("prof").loc[prof]
    ins = getattr(agg, "inscrits_par_prof", {}).get(prof)
    vals = {"inscrits": ins, **{c: int(r[c]) for c in ("avec_activite", "avec_lieu", "dans_densites")}}
    etapes = [e for e in ETAPES_PARCOURS if vals.get(e[0])]
    total = vals[etapes[0][0]]
    # barres fines, libellé au-dessus et valeur à droite, comme dans l'atlas (9 octobre 2026)
    f = Figure(w=640, h=12 + len(etapes) * 52, marges=(0, 0, 6, 6))
    f.echelles(0, total, 0, 1)
    prec = None
    for k, (col, titre, raison) in enumerate(etapes):
        y, v = f.hh + k * 52, vals[col]
        der = col == "dans_densites"
        f.texte(0, y + 13, titre, c=ENCRE, taille=12.5, gras=der)
        f.texte(f.w, y + 13, nombre(v), "end", ENCRE, 12.5, gras=der)
        f.ajout(f'<rect x="0" y="{y + 19}" width="{f.w}" height="7" rx="1.5" fill="var(--nodata, #E3E4E8)"/>')
        f.ajout(f'<rect x="0" y="{y + 19}" width="{max(f.X(v), 1):.1f}" height="7" rx="1.5" '
                f'fill="{VIOLET[1] if der else VIOLET[2]}"><title>{escape(titre)}, {nombre(v)}</title></rect>')
        if prec is not None and prec > v:
            f.ajout(f'<rect x="{f.X(v):.1f}" y="{y + 19}" width="{f.X(prec) - f.X(v):.1f}" height="7" '
                    f'fill="none" stroke="{OCRE_PALE}" stroke-dasharray="3 2"/>')
            detail = f"− {nombre(prec - v)} {raison}"
            if der and int(r["dont_teleconsultation"]):
                detail += f", dont {nombre(int(r['dont_teleconsultation']))} en téléconsultation"
            f.texte(0, y + 42, detail, taille=11)
        prec = v
    return f.svg(f"Du répertoire aux densités, {pluriel_simple(lab.get(prof, prof)).lower()}")


def tiers(v: pd.Series) -> pd.Series:
    """Tiers d'une série (0, 1, 2), bornes aux quantiles 1/3 et 2/3 des valeurs connues."""
    a, b = v.quantile(1 / 3), v.quantile(2 / 3)
    return pd.Series(np.where(v.isna(), np.nan, np.where(v > b, 2, np.where(v > a, 1, 0))), index=v.index)


def classes_bivariees(dens: pd.Series, ind: pd.Series) -> pd.Series:
    """Indice de couleur de la carte bivariée, offre (tiers) x 3 + indicateur (tiers), Mayotte écartée."""
    d = pd.DataFrame({"o": dens, "b": ind}).drop(index=config.DEPARTEMENTS_EXCLUS_CROISEMENTS, errors="ignore").dropna()
    return (tiers(d["o"]) * 3 + tiers(d["b"])).astype(int)


def _legende_bivariee(nom_offre, nom_ind):
    def f(el, x, y, largeur):
        c = 18
        for o in range(3):
            for b in range(3):
                el.append(f'<rect x="{x + 60 + o * c}" y="{y + (2 - b) * c}" width="{c}" height="{c}" '
                          f'fill="{config.BIVARIEE[o * 3 + b]}"/>')
        el.append(f'<text x="{x + 60 + 1.5 * c}" y="{y + 3 * c + 14}" text-anchor="middle" font-size="11" '
                  f'fill="{DISCRET}">{escape(nom_offre)} →</text>')
        el.append(f'<text x="{x + 52}" y="{y + 1.5 * c + 4}" text-anchor="end" font-size="11" '
                  f'fill="{DISCRET}">{escape(nom_ind)} ↑</text>')
        el.append(f'<rect x="{x + 150}" y="{y + 2}" width="12" height="12" fill="{config.BIVARIEE[2]}"/>')
        el.append(f'<text x="{x + 168}" y="{y + 12}" font-size="11" fill="{DISCRET}">indicateur dans le tiers le plus '
                  f'haut, offre dans le tiers le plus bas</text>')
        return y + 3 * c + 22
    return f


def bivariee(ref, ctx, agg, lab, ctxlab, prof="psychiatre", var="suicides"):
    """Carte bivariée des départements, offre (densité) et indicateur, chacun en tiers."""
    from . import cartes
    from .analyses import tables
    if ctx is None or "dep" not in ctx or var not in ctx["dep"]:
        return None
    f = cartes.fonds(ref)
    _n, d, _pop = tables(agg, ref, "dep", "all")
    if not f or prof not in d:
        return None
    cl = classes_bivariees(d[prof], ctx["dep"][var].reindex(d.index))
    couleurs = {c: config.BIVARIEE[i] for c, i in cl.items()}
    nom = pluriel_simple(lab.get(prof, prof))
    return cartes.carte_france(f["atlas_dep"], {}, f"{nom} et {ctxlab.get(var, var).lower()}, par département, en tiers",
                               couleurs=couleurs, legende_fn=_legende_bivariee(nom.lower(), ctxlab.get(var, var).lower()),
                               suicide=var == "suicides")


GWR_COULEURS = [("negatif_fort", "var(--d0, #7A4E00)", "lien négatif net, fort"),
                ("negatif", "var(--d1, #B88A2E)", "lien négatif net"),
                ("non_net", "var(--d3, #EFEDF2)", "pas de lien net"),
                ("positif", "var(--r3, #8C6DAE)", "lien positif net"),
                ("positif_fort", "var(--r5, #3E2563)", "lien positif net, fort")]


def classe_gwr(coef, net):
    """Classe d'un coefficient local, fort au-delà de 0,3 écart-type."""
    if not net:
        return "non_net"
    return ("positif" if coef > 0 else "negatif") + ("_fort" if abs(coef) >= .3 else "")


def gwr_carte(ref, R, lab, prof="psychologue"):
    """Carte des intercommunalités de l'Hexagone, coefficient local du niveau de vie (régression pondérée)."""
    from . import cartes
    co = R.get("gwr_coefficients")
    if not isinstance(co, pd.DataFrame) or prof not in set(co["prof"]):
        return None
    f = cartes.fonds(ref)
    if not f or "atlas_epci" not in f:
        return None
    g = co[co["prof"] == prof]
    coul = dict(GWR_COULEURS[i][:2] for i in range(len(GWR_COULEURS)))
    couleurs = {c: coul[classe_gwr(b, n)] for c, b, n in zip(g["code"], g["coef_niveau_de_vie"], g["net"])}
    geoms = {c: f["atlas_epci"][c] for c in couleurs if c in f["atlas_epci"]}

    def leg(el, x, y, largeur):
        for i, (_k, c, t) in enumerate(GWR_COULEURS):
            xx, yy = x + (i % 3) * (largeur / 3), y + (i // 3) * 20
            el.append(f'<rect x="{xx:.0f}" y="{yy}" width="14" height="12" fill="{c}" stroke="{LIGNE}"/>')
            el.append(f'<text x="{xx + 20:.0f}" y="{yy + 10}" font-size="11" fill="{DISCRET}">{escape(t)}</text>')
        return y + 40
    return cartes.carte_france(geoms, {}, f"Lien local entre niveau de vie et densité de {pluriel_simple(lab.get(prof, prof)).lower()}, "
                                          "à densité de population égale", couleurs=couleurs, legende_fn=leg)


def ecrire(out, agg, ref, professions, contexte, R):
    """Écrit les figures dans out/graphiques/ et renvoie la liste des noms produits."""
    from . import indicateurs
    dossier = out / "graphiques"
    dossier.mkdir(exist_ok=True)
    lab = dict(zip(professions["id"], professions["libelle"]))
    ctxlab = indicateurs.libelles(contexte)
    from .cartes import retenir_noms
    retenir_noms(ref)
    # inscrits au répertoire par profession, quand la profession correspond à un libellé du RPPS
    from .export import _parcours
    pc = _parcours(agg, professions.attrs.get("inscrits"), lab)
    agg.inscrits_par_prof = ({} if pc is None or "inscrits" not in pc else
                             {p: int(v) for p, v in zip(pc["prof"], pc["inscrits"]) if pd.notna(v)})
    from .analyses import tables
    n_epci, _d, pop_epci = tables(agg, ref, "epci", "all")
    moy_epci = n_epci.sum() / pop_epci.sum() * 1e4
    figures = {}

    def variantes(nom, fn, profs, defaut):
        """Figure par défaut (celle que commente le texte) et une variante par autre profession."""
        for q in [defaut] + [x for x in profs if x != defaut]:
            try:
                svg = fn(q)
            except Exception as e:  # noqa: BLE001
                log.warning("figure %s pour %s impossible (%s)", nom, q, e)
                svg = None
            if svg:
                figures[nom if q == defaut else f"{nom}__{q}"] = marquer(svg, pluriel_simple(lab.get(q, q)))
            elif q == defaut:
                return

    variantes("quadrants_sm", lambda q: quadrants(R, lab, ctxlab, q), ["psychiatre", "psychologue", "q_psychiatrie_enfant"],
              "psychiatre")
    for cle in ("sm", "sante"):
        pr = VARIANTES[cle]
        figures[f"lorenz_{cle}"] = lorenz(R, lab, cle)
        variantes(f"effet_ville_{cle}", lambda q, c=cle: effet_ville(R, lab, ctxlab, c, q), pr, PRINCIPALE[cle])
        variantes(f"escalier_{cle}", lambda q, c=cle: escalier(R, lab, c, moy_epci.get(q, 0), q), pr, PRINCIPALE[cle])
        variantes(f"entonnoir_{cle}", lambda q, c=cle: entonnoir(R, lab, c, q), pr, PRINCIPALE[cle])
        variantes(f"porte_{cle}", lambda q, c=cle: porte(R, lab, c, q), pr, PRINCIPALE[cle])
        figures[f"distance_{cle}"] = distances(R, lab, cle)
        variantes(f"parcours_{cle}", lambda q: parcours(agg, lab, q), pr, PRINCIPALE[cle])
    figures.update(cartes_nationales(agg, ref, lab, R))
    ctx = contexte["contexte"] if contexte else None
    variantes("bivariee_sm", lambda q: bivariee(ref, ctx, agg, lab, ctxlab, q), ["psychiatre", "psychologue"], "psychiatre")
    variantes("gwr_sm", lambda q: gwr_carte(ref, R, lab, q), ["psychologue", "psychiatre"], "psychologue")
    faites = []
    for nom, svg in figures.items():
        if svg:
            (dossier / f"{nom}.svg").write_text(svg, encoding="utf-8")
            faites.append(nom)
    return faites
