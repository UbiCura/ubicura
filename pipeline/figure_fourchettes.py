"""Figure « Chaque région et sa fourchette » des pages d'indicateur (maquette validée le 23 novembre 2026,
prototypes/intervalle_barometre/).

Pour un indicateur que Santé publique France publie par région avec un intervalle de confiance (Baromètre, décès
attribuables au tabac) : chaque région, sa valeur et sa fourchette, la région médiane du site en pointillé (même repère
que les fiches). Point vide quand la fourchette contient la médiane, point plein sinon. Les régions dans un ordre fixe,
la France hexagonale puis l'outre-mer par ordre alphabétique, jamais rangées par valeur (pas de palmarès, registre 13),
sans couleur (indicateurs de contexte). Deux dessins, l'un pour l'ordinateur, l'autre pour le téléphone (nom au-dessus
du trait), lisibles sans agrandir.
"""
from __future__ import annotations

import html
import math

from .fiche_territoire import MARGE_LIGNE, _decimales, _ecrire_dec, bornes_intervalle
from .mots_lecteur import sans_accents

OUTRE_MER = {"01", "02", "03", "04", "06"}
esc = html.escape


def _graduations(lo: float, hi: float) -> list[tuple[float, str]]:
    pas = 10 ** math.floor(math.log10((hi - lo) / 4))
    for k in (1, 2, 5, 10):
        if (hi - lo) / (pas * k) <= 6:
            pas *= k
            break
    d = max(0, -int(math.floor(math.log10(pas))))
    t = math.ceil(lo / pas) * pas
    out = []
    while t <= hi + 1e-9:
        out.append((t, _ecrire_dec(t, d)))
        t += pas
    return out


def _svg(lignes: list[dict], med: float, medtxt: str, unite: str, titre: str, tel: bool) -> str:
    lo = min(r["bas"] for r in lignes)
    hi = max(r["haut"] for r in lignes)
    pad = (hi - lo) * 0.06
    lo, hi = lo - pad, hi + pad
    if tel:
        W, G, D, H0, PAS, fs = 340, 8, 332, 62, 36, 13
    else:
        W, G, D, H0, PAS, fs = 640, 200, 620, 62, 22, 12.5

    def X(v):
        return G + (v - lo) / (hi - lo) * (D - G)
    haut = H0 + PAS * len(lignes) + 40
    p = [f'<svg class="{"fig-tel" if tel else "fig-ord"}" viewBox="0 0 {W} {haut}" role="img" aria-label="{esc(titre)} : '
         f'chaque région, sa valeur et sa fourchette, la France hexagonale puis l’outre-mer, région médiane en '
         f'pointillé">']
    p.append(f'<circle cx="{G + 5}" cy="10" r="4" fill="var(--ink)"/><text x="{G + 14}" y="14" font-size="{fs - 1}" '
             f'fill="var(--ink)">fourchette qui ne contient pas la médiane</text>'
             f'<circle cx="{G + 5}" cy="28" r="4" fill="var(--bg)" stroke="var(--ink)" stroke-width="1.5"/>'
             f'<text x="{G + 14}" y="32" font-size="{fs - 1}" fill="var(--ink)">fourchette qui la contient</text>')
    for t, lab in _graduations(lo, hi):
        x = X(t)
        p.append(f'<line x1="{x:.1f}" y1="{H0 - 4}" x2="{x:.1f}" y2="{haut - 34}" stroke="var(--line)" stroke-width="1"/>'
                 f'<text x="{x:.1f}" y="{haut - 20}" font-size="12" text-anchor="middle" fill="var(--muted)">{lab}</text>')
    p.append(f'<text x="{(G + D) / 2:.1f}" y="{haut - 4}" font-size="12" text-anchor="middle" fill="var(--muted)">'
             f'{esc(unite)}</text>')
    xm = X(med)
    anc = "end" if xm > (G + D) / 2 else "start"
    p.append(f'<line x1="{xm:.1f}" y1="{H0 - 10}" x2="{xm:.1f}" y2="{haut - 34}" stroke="var(--ink)" stroke-width="1" '
             f'stroke-dasharray="3 3"/><text x="{xm + (-4 if anc == "end" else 4):.1f}" y="{H0 - 13}" font-size="12" '
             f'text-anchor="{anc}" fill="var(--ink)">région médiane {medtxt}</text>')
    for k, r in enumerate(lignes):
        y = H0 + PAS * k + (PAS - 10 if tel else PAS / 2)
        if tel:
            lab = (f'<text x="{G}" y="{y - 9:.1f}" font-size="{fs}" fill="var(--ink)" stroke="var(--bg)" stroke-width="4" '
                   f'paint-order="stroke" stroke-linejoin="round">{esc(r["nom"])}</text>')
        else:
            lab = (f'<text x="{G - 12}" y="{y + 4:.1f}" font-size="{fs}" text-anchor="end" fill="var(--ink)">'
                   f'{esc(r["nom"])}</text>')
        pt = (f'<circle cx="{X(r["v"]):.1f}" cy="{y:.1f}" r="4" fill="var(--ink)"/>' if r["hors"] else
              f'<circle cx="{X(r["v"]):.1f}" cy="{y:.1f}" r="4" fill="var(--bg)" stroke="var(--ink)" stroke-width="1.5"/>')
        p.append(f'<g><title>{esc(r["nom"])}, {r["txt"]} {esc(unite)}, entre {r["ic"][0]} et {r["ic"][1]}, '
                 f'{"fourchette qui ne contient pas la médiane" if r["hors"] else MARGE_LIGNE}</title>{lab}'
                 f'<line x1="{X(r["bas"]):.1f}" y1="{y:.1f}" x2="{X(r["haut"]):.1f}" y2="{y:.1f}" stroke="var(--muted)" '
                 f'stroke-width="2"/>{pt}</g>')
    p.append("</svg>")
    return "".join(p)


def fourchettes(T, ident: str, intervalles: dict, noms: dict, unite: str, titre: str) -> dict | None:
    """La figure et son « Comment lire » pour un indicateur publié par région avec une fourchette, ou None. T, la règle
    d'affichage (valeurs affichées et région médiane, les mêmes que sur les fiches) ; intervalles, {(niveau, code,
    indicateur): (valeur, bas, haut)} du fichier publié de Santé publique France ; noms, {code: nom} des régions."""
    S = T.serie(ident, "reg")
    if S is None or S.ref is None:
        return None
    lignes = []
    for code in S.codes:
        x = intervalles.get(("reg", code, ident))
        cel = T.cellule(ident, "reg", code)
        if not x or not cel or cel["v"] is None or not cel["v_txt"]:
            continue
        # l'intervalle n'accompagne que la valeur publiée elle-même
        if abs(x[0] - cel["v"]) > 1e-6 * max(1.0, abs(x[0])):
            continue
        lignes.append({"code": code, "nom": noms.get(code, code), "v": cel["v"], "txt": cel["v_txt"], "bas": x[1],
                       "haut": x[2], "ic": bornes_intervalle(cel["v_txt"], x[1], x[2]),
                       "hors": not (x[1] <= S.ref <= x[2])})
    if len(lignes) < 3:
        return None
    # ordre alphabétique sans tenir compte des accents (Île-de-France entre Hauts-de-France et Normandie)
    lignes.sort(key=lambda r: (r["code"] in OUTRE_MER, sans_accents(r["nom"])))
    # la médiane écrite au nombre de décimales des bornes : « 7,14 » et non « 7,1 » à côté de « 7,12 à 7,26 »
    k = max(max(_decimales(r["ic"][0]) for r in lignes), max(_decimales(r["txt"]) for r in lignes))
    medtxt = _ecrire_dec(S.ref, k)
    dans = sum(1 for r in lignes if not r["hors"])
    n_reg = len(lignes)
    manque = len(S.codes) - n_reg
    absentes = ("Mayotte n'en a pas" if manque == 1 and "06" not in {r["code"] for r in lignes}
                else f"{manque} régions n'en ont pas" if manque > 1 else "")
    lire = ("Chaque point est la valeur publiée pour une région, le trait sa fourchette (intervalle de confiance à 95 %) : "
            "la valeur vraie se trouve probablement dans ce trait. Un point vide dit que la fourchette contient la valeur "
            "de la région médiane : l'écart à la médiane n'est pas assez grand, au regard de la précision de la mesure, "
            "pour être tenu pour établi. Un point plein dit qu'elle ne la contient pas. Les régions sont dans le même "
            "ordre pour toutes les mesures, la France hexagonale puis l'outre-mer, sans classement. "
            f"Ici, {dans} des {n_reg} régions qui ont une valeur publiée{f' ({absentes})' if absentes else ''} ont une "
            "fourchette qui contient la médiane.")
    return {"lire": lire, "svg_ord": _svg(lignes, S.ref, medtxt, unite, titre, False),
            "svg_tel": _svg(lignes, S.ref, medtxt, unite, titre, True), "n": n_reg, "dans": dans}
