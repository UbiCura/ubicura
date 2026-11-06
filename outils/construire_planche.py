"""Planche de style du site (étape 1 du plan de reprise de la présentation, 30 octobre 2026).

Écrit site/_planche.html, page de travail non liée au site, qui montre la direction visuelle (docs/direction_visuelle.md)
sur des données réelles déjà construites : grille, cinq tailles, espacements, couleurs sur les deux fonds, encadré type,
ligne type d'un indicateur avec sa réglette, cartes au national et à l'échelle locale, tableau, légendes, en-tête et
menu de six entrées, paragraphe justifié à côté d'un encadré aligné à gauche.

Aucune donnée n'est recalculée dans la chaîne. La page lit ce que la construction du site a déjà écrit :
- site/presentation/atelier_donnees.js (valeurs, effectifs, repères « Ensemble des intercommunalités », contours) ;
- site/presentation/zone_fond/18.json (contours des communes du Cher) ;
- site/territoire/epci/200090561.html (plan des structures de soins psychiques de la CC Vierzon-Sologne-Berry) ;
- resultats/historique/effectifs_dep_*.csv aux dates des versions publiées (donnees/publication.json), série courte.
La position, la médiane et la couleur des lignes type sont lues ici pour juger la forme ; sur le site, elles viendront
du module des chiffres. Lancer :
    .\\.venv\\Scripts\\python.exe outils\\construire_planche.py [--resultats D:\\offre_soins\\resultats]
"""
import argparse
import csv
import json
import math
import re
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from pipeline import config  # noqa: E402
from pipeline.cartes_presentation import ecarter, projection  # noqa: E402
from pipeline.lecture import nombre  # noqa: E402
from pipeline.site import GABARITS, PRESENTATION, SITE, _environnement  # noqa: E402

EPCI = "200090561"   # CC Vierzon-Sologne-Berry, exemple de l'audit du 30 octobre 2026
DEP = "18"
LIGNES = ["prof:psychologue:all", "prof:psychiatre:all", "prof:psychotherapeute:all", "prof:pedopsychiatre:all"]
DENSITE = ["var(--r0)", "var(--r1)", "var(--r2)", "var(--r3)", "var(--r5)"]
# écart au repère, classes 0,5, 0,8, 1,25 et 2 fois (règle d'affichage, 3.2)
ECART = [(0.5, "var(--d0)"), (0.8, "var(--d1)"), (1.25, "var(--d3)"), (2.0, "var(--d5)"), (math.inf, "var(--d6)")]
ENCARTS = {"971": "Guadeloupe", "972": "Martinique", "973": "Guyane", "974": "La Réunion", "976": "Mayotte"}
# nom de trois lettres sous ou à droite de chaque encart (code de l'ISO 3166), relecture esthétique du 30 octobre 2026
SIGLES = {"971": "GLP", "972": "MTQ", "973": "GUF", "974": "REU", "976": "MYT"}


def _atelier(site: Path) -> dict:
    t = (site / "presentation" / "atelier_donnees.js").read_text(encoding="utf-8")
    return json.loads(t[t.index("=") + 1:t.rstrip().rindex(";")])


def _fr(x, d=1):
    return nombre(x, d)


def _hachure(i):
    return (f'<defs><pattern id="hachure-{i}" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            f'<rect width="5" height="5" fill="var(--nodata)"/><line x1="0" y1="0" x2="0" y2="5" stroke="var(--muted)" '
            f'stroke-width="1"/></pattern></defs>')


def ligne_type(T, A: dict, ind_id: str, i: int) -> dict | None:
    """Ligne type d'un indicateur pour l'intercommunalité i : valeur, effectif, repère, médiane, position, écart, couleur,
    statut et réglette lus dans le module des chiffres (pipeline/affichage.py), le même que les fiches. L'unité est
    celle de l'indicateur (pour 100 000 habitants pour une profession rare)."""
    from pipeline import affichage as AF
    code = A["units"]["epci"][i]["c"]
    c = T.cellule(ind_id, "epci", code)
    if c is None:
        return None
    r = T.reglette(ind_id, "epci", code, c)
    e = T.echelle(ind_id, "epci")
    ind = next(x for x in A["ind"] if x["id"] == ind_id)
    statut = c["statut"] or c["couleur"] or "neutre"
    zero = None
    if c["statut"] == "aucun":
        S = T.serie(ind_id, "epci")
        ns = [k for k in S.n if k is not None]
        zero = f"{round(100 * sum(1 for k in ns if k == 0) / len(ns))}{AF.FINE}%"
    q = lambda x: AF.nombre(x, c["genre"])  # noqa: E731
    return {"nom": ind["lab"], "unite": AF.txt_unite(c["fac"]), "rare": c["fac"] == 100000, "v": c["v_txt"],
            "n": c["n"], "n_txt": c["n_txt"], "rep": c["ref_txt"], "med": q(c["med"]) if c["med"] else c["med_mots"],
            "med_zero": not c["med"],
            "pos": c["pos_txt"].split(" des ")[0] if c["pos_txt"] else "", "zero": zero,
            "ecart": c["e_mots"], "statut": statut,
            "q1": r["q1"], "q3": r["q3"], "prep": r["rep"], "pmed": r["med"], "pval": r["val"], "distrib": r["distrib"],
            "h": r.get("h"), "classe": r["classe"], "aria": r["aria"],
            "info": r["info"],
            "src": ind["src"], "lic": ind["lic"], "an": ind["an"], "lim": ind.get("lim", "")}


def carte_nationale(A: dict, ind_id: str, mode: str, choisi: str, k: int, lv: str = "epci") -> str:
    vals = A["val"][lv][ind_id]
    codes = [u["c"] for u in A["units"][lv]]
    v = {c: x for c, x in zip(codes, vals) if x is not None}
    rep = next(x for x in A["ind"] if x["id"] == ind_id)["moy"][lv]
    tri = sorted(v.values())
    bornes = [tri[int(len(tri) * q / 5)] for q in range(1, 5)]

    def couleur(c):
        if c not in v:
            return f"url(#hachure-{k})"
        if mode == "densite":
            return DENSITE[sum(1 for b in bornes if v[c] >= b)]
        return next(col for seuil, col in ECART if v[c] / rep < seuil)

    s = [f'<svg class="carte-svg" viewBox="0 0 {A["W"]} {A["H"] + 24}" role="img" aria-label="Psychologues pour 10 000 habitants, '
         f'par {"intercommunalité" if lv == "epci" else "département"}, '
         f'{"en cinq classes de même effectif" if mode == "densite" else "rapport au repère"}">', _hachure(k)]
    for c, chemin in A["geo"][lv].items():
        s.append(f'<path class="aplat" d="{chemin}" fill="{couleur(c)}"/>')
    if choisi in A["geo"][lv]:
        s.append(f'<path class="choisi" d="{A["geo"][lv][choisi]}"/>')
    s.append("</svg>")
    lim = [tri[0]] + bornes + [tri[-1]]
    return "".join(s), [_fr(x, 1) for x in lim]


def carte_locale(A: dict, site: Path) -> str:
    """La CC Vierzon-Sologne-Berry à l'échelle locale : communes en fond (Cher et départements voisins), intercommunalités
    et département en contours, l'intercommunalité cernée, ses structures de soins psychiques en points selon leur
    confirmation (lus dans la fiche construite)."""
    geo = A["geo"]
    deps = geo["dep"][DEP]
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", geo["epci"][EPCI])]
    xs, ys = nums[0::2], nums[1::2]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    # cadre de l'intercommunalité et de ses abords, au format 4:3
    cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) * 1.6, (y1 - y0) * 1.6
    w, h = max(w, h * 4 / 3), max(h, w * 3 / 4)
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    k = 700 / (x1 - x0)   # pixels par unité de la carte, pour les rayons
    s = [f'<svg class="carte-svg" viewBox="{x0:.2f} {y0:.2f} {x1 - x0:.2f} {y1 - y0:.2f}" role="img" '
         f'aria-label="Plan des structures de soins psychiques de la CC Vierzon-Sologne-Berry, sur le fond des communes">']
    pr = projection()
    for dep in (DEP, "41", "36", "45"):
        f = site / "presentation" / "zone_fond" / f"{dep}.json"
        if not f.exists():
            continue
        fond = json.loads(f.read_text(encoding="utf-8"))
        ox, oy = fond["o"]
        for anneaux in fond["c"].values():
            d, dedans = [], False
            for a in anneaux:
                x, y, pts = a[0], a[1], []
                pts.append(pr(ox + x / 1e4, oy + y / 1e4))
                for j in range(2, len(a), 2):
                    x, y = x + a[j], y + a[j + 1]
                    pts.append(pr(ox + x / 1e4, oy + y / 1e4))
                dedans = dedans or any(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in pts)
                d.append("M" + "L".join(f"{p[0]:.2f} {p[1]:.2f}" for p in pts) + "Z")
            if dedans:
                s.append(f'<path class="fond-commune" d="{"".join(d)}"/>')
    s.append(f'<path d="{geo["epci"][EPCI]}" fill="var(--r1)" fill-opacity=".35" stroke="none"/>')
    for c, chemin in geo["epci"].items():
        n = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", chemin)]
        if c != EPCI and any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in zip(n[0::2], n[1::2])):
            s.append(f'<path class="contour secondaire" d="{chemin}"/>')
    s.append(f'<path class="contour" d="{deps}"/>')
    s.append(f'<path class="choisi" d="{geo["epci"][EPCI]}"/>')
    fiche = (site / "territoire" / "epci" / f"{EPCI}.html").read_text(encoding="utf-8")
    m = re.search(r'<svg class="carte-svg plan".*?</svg>', fiche, re.S)
    sit = m.group(0) if m else ""
    r = 6 / k     # 12 px de diamètre, avec un liseré de la couleur du fond (style.css)
    # les structures de l'intercommunalité (points pleins du plan de sa fiche), plusieurs à la même adresse en un point,
    # puis décalées d'un cran quand deux points se chevauchent
    lieux: dict[tuple, list] = {}
    for cx, cy, fill, reste, titre in re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="[\d.]+" fill="([^"]+)"([^>]*)><title>([^<]*)</title>', sit):
        if "opacity" not in reste:
            lieux.setdefault((float(cx), float(cy), "pt-confirmee" if "action" in fill else "pt-a-verifier"), []).append(titre)
    for x, y, cl, titres in ecarter([(x, y, cl, t) for (x, y, cl), t in sorted(lieux.items(), key=lambda q: q[0][2] != "pt-confirmee")], r):
        s.append(f'<circle class="{cl}" cx="{x}" cy="{y}" r="{r:.2f}"><title>{" ; ".join(titres)}</title></circle>')
    for cx, cy, reste, titre in re.findall(r'<rect x="[\d.]+" y="[\d.]+"[^>]*rotate\(45 ([\d.]+) ([\d.]+)\)"([^>]*)><title>([^<]*)</title>', sit):
        if "opacity" in reste:
            continue
        q = r * 0.8
        s.append(f'<rect class="pt-recoupee" x="{float(cx) - q:.2f}" y="{float(cy) - q:.2f}" width="{2 * q:.2f}" height="{2 * q:.2f}" '
                 f'transform="rotate(45 {cx} {cy})"><title>{titre}</title></rect>')
    s.append("</svg>")
    return "".join(s)


def serie(resultats: Path) -> dict | None:
    """Psychologues inscrits dans la CC Vierzon-Sologne-Berry aux dates des versions publiées (série courte de la
    réglette), lus dans effectifs_epci_all.csv de chaque version."""
    pub = resultats.parent / "donnees" / "publication.json"
    if not pub.exists():
        pub = config.RACINE / "donnees" / "publication.json"
    if not pub.exists():
        return None
    dates = json.loads(pub.read_text(encoding="utf-8-sig")).get("versions_publiees") or []
    pts = []
    for d in dates:
        f = resultats / d / "effectifs_epci_all.csv"
        if not f.exists():
            continue
        with f.open(encoding="utf-8-sig") as fh:
            for l in csv.DictReader(fh, delimiter=";"):
                if l["code"] == EPCI and l.get("n_psychologue") not in (None, ""):
                    pts.append((d, int(float(l["n_psychologue"]))))
    if len(pts) < 2:
        return None
    # échelle d'au moins 10 % de la valeur, pour qu'un inscrit de plus ne dessine pas une falaise
    lo, hi = min(n for _, n in pts), max(n for _, n in pts)
    marge = max(0.0, (0.10 * hi - (hi - lo)) / 2)
    lo, hi = lo - marge, hi + marge
    ech = lambda n: 18 - 16 * (n - lo) / (hi - lo) if hi > lo else 10  # noqa: E731
    xs = [100 * j / (len(pts) - 1) for j in range(len(pts))]
    return {"d": "M" + " L".join(f"{x:.1f} {ech(n):.1f}" for x, (_, n) in zip(xs, pts)),
            "debut_xy": (xs[0], ech(pts[0][1])), "fin": (xs[-1], ech(pts[-1][1])), "debut": pts[0], "dernier": pts[-1],
            "nb": len(pts)}


def construire(resultats: Path, site: Path = SITE) -> Path:
    from pipeline.lecture import date_longue
    from pipeline import affichage as AF
    A = _atelier(site)
    dernier = max(d for d in resultats.glob("20*") if (d / "site_data.json").exists())
    T = AF.Affichage(json.loads((dernier / "site_data.json").read_text(encoding="utf-8")), dernier)
    i = next(j for j, u in enumerate(A["units"]["epci"]) if u["c"] == EPCI)
    lignes = [l for l in (ligne_type(T, A, x, i) for x in LIGNES) if l]
    carte_d, bornes_d = carte_nationale(A, "prof:psychologue:all", "densite", EPCI, 1)
    # l'écart au repère par département : par intercommunalité, le repère pesé par la population place 69 % des
    # intercommunalités sous 0,8 fois, et la carte devient presque toute cuivre (question remontée, voir la note)
    carte_e, _ = carte_nationale(A, "prof:psychologue:all", "ecart", DEP, 2, "dep")
    carte_e2, _ = carte_nationale(A, "prof:psychologue:all", "ecart", DEP, 3, "dep")
    carte_e3, _ = carte_nationale(A, "prof:psychologue:all", "ecart", DEP, 4, "dep")
    W, H = A["W"], A["H"]
    # Guadeloupe et Martinique : le sigle à droite de l'encart ; Guyane, La Réunion, Mayotte : dessous
    HB = H + 24
    encarts = []
    for c, b in A["encarts"].items():
        if c not in ENCARTS:
            continue
        droite = c in ("971", "972")
        # sous l'encart, calé à gauche (Mayotte à droite), pour que les sigles voisins ne se touchent pas au téléphone
        x, y = (b[0] + b[2] + 4, b[1] + b[3] / 2 - 8) if droite else (b[0] + (b[2] - 26 if c == "976" else 0), b[1] + b[3] + 2)
        encarts.append({"nom": ENCARTS[c], "sigle": SIGLES[c], "x": f"{100 * x / W:.2f}%", "y": f"{100 * y / HB:.2f}%"})
    rpps = lignes[0]["an"]
    ctx = {"titre": "Planche de style", "racine": "", "page": "", "menu_six": True,
           "presentation": PRESENTATION, "description": "Planche de style du site, page de travail.",
           "version_css": __import__("hashlib").sha1((GABARITS / "style.css").read_bytes()).hexdigest()[:10],
           "date_longue": A["version"], "date_calcul": f"Calculé le {A['version']}, {rpps}",
           "citation_auteur": config.CITATION_AUTEUR, "annee_version": "2026", "adresse_site": config.ADRESSE_SITE.rstrip("/"),
           "licences": "", "compteur": "", "classe_main": "planche",
           "nom_epci": A["units"]["epci"][i]["nm"], "pop_epci": nombre(A["units"]["epci"][i]["pop"]),
           "lignes": lignes, "carte_densite": carte_d, "bornes_densite": bornes_d, "carte_ecart": carte_e,
           "carte_ecart_clair": carte_e2, "carte_ecart_sombre": carte_e3, "encarts": encarts,
           "carte_locale": carte_locale(A, site),
           "rep_dep": _fr(next(x for x in A["ind"] if x["id"] == "prof:psychologue:all")["moy"]["dep"], 1), "serie": serie(resultats), "doi": A.get("doi"),
           "date_version": date_longue}
    from pipeline.site import rendre
    html = rendre(_environnement(), "planche.html", ctx)
    cible = site / "_planche.html"
    cible.write_text(html, encoding="utf-8")
    return cible


if __name__ == "__main__":
    a = argparse.ArgumentParser(description="Écrit la planche de style site/_planche.html")
    a.add_argument("--resultats", default=str(config.RESULTATS), help="dossier des résultats (pour l'historique publié)")
    args = a.parse_args()
    print(construire(Path(args.resultats)))
