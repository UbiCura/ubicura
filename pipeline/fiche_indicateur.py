"""Fiche de chaque indicateur (présentation du 30 octobre 2026, maquette e-indicateur validée).

Une page par indicateur du catalogue (profil des territoires, et chaque profession avec ses trois modes d'exercice) :
la réponse en une phrase, la répartition des territoires autour du repère de leur niveau, la définition, la source, la
licence, les niveaux, l'année, les limites, et pour une profession les différents totaux des fichiers et celui qu'il faut
citer. Valeurs relues dans les données de l'atelier (pipeline/atelier.py), elles-mêmes relues dans site_data.json, et
dans les fichiers publiés de la version. Aucun calcul statistique nouveau, seulement des quartiles et des sommes.
Repère, médiane et répartition viennent de la règle d'affichage unique (pipeline/affichage.py), les mêmes que la fiche
d'un territoire, le comparateur et Croiser, sur tous les territoires du niveau, Mayotte comprise.
"""
import csv
import html as _html
import re
from functools import lru_cache
from pathlib import Path

from . import config
from . import affichage as AF
from .affichage import FINE, nombre
from .lecture import pluriel
from .affichage import par_habitants

NOMS = {"reg": ("région", "régions"), "dep": ("département", "départements"), "epci": ("intercommunalité", "intercommunalités")}
ORDRE = ("epci", "dep", "reg")


def slug(ind_id: str) -> str:
    return ind_id.replace("prof:", "prof-").replace(":all", "").replace(":", "-").replace("_", "-")


@lru_cache(maxsize=16)
def _lire(f: Path) -> list[dict]:
    """Fichier publié de la version, lu une fois pour toutes les fiches."""
    if not f.exists():
        return []
    with open(f, encoding="utf-8-sig") as h:
        return list(csv.DictReader(h, delimiter=";"))


def _num(s):
    try:
        return float(str(s).replace(",", "."))
    except (TypeError, ValueError):
        return None


def quantile(vals: list[float], p: float) -> float:
    i = (len(vals) - 1) * p
    lo, hi = int(i), min(int(i) + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (i - lo)


def graduations(lo: float, hi: float, n: int = 5) -> list[float]:
    """Graduations rondes (1, 2, 2,5 ou 5 fois une puissance de dix) comprises entre lo et hi, n environ."""
    import math
    brut = (hi - lo) / n
    p = 10 ** math.floor(math.log10(brut)) if brut > 0 else 1
    pas = next(m * p for m in (1, 2, 2.5, 5, 10) if m * p >= brut)
    x, out = math.ceil(lo / pas) * pas, []
    while x <= hi + 1e-9:
        out.append(round(x, 10))
        x += pas
    return out


def de(nom: str) -> str:
    """« de régions », « d'intercommunalités »."""
    return ("d’" if nom[:1] in "aeiouyéèh" else "de ") + nom


def repartition(vals: list, repere: float | None, nom_niv: str, unite: str, g: str = "taux") -> dict:
    """Histogramme des territoires (SVG statique, 640 x 250), bornes aux 1er et 99e centiles, valeurs au-delà rangées
    dans les classes extrêmes, repère en pointillé."""
    v = sorted(x for x in vals if x is not None)
    lo, hi = quantile(v, .01), quantile(v, .99)
    if hi <= lo:
        lo, hi = v[0], v[-1] + 1e-9
    nb = 20
    pas = (hi - lo) / nb
    h = [0] * nb
    for x in v:
        h[min(nb - 1, max(0, int((x - lo) / pas)))] += 1
    W, H, ml, mr, mt, mb = 640, 272, 48, 14, 30, 44
    top = max(h) or 1
    sx = lambda x: ml + (x - lo) / (hi - lo) * (W - ml - mr)
    sy = lambda n: H - mb - n / top * (H - mb - mt)
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Nombre {de(nom_niv)} par classe de valeur, repère en pointillé">']
    for k, n in enumerate(h):
        x0 = lo + k * pas
        bord = " et moins" if k == 0 and v[0] < lo else " et plus" if k == nb - 1 and v[-1] > hi else ""
        s.append(f'<rect x="{sx(x0) + 1:.1f}" y="{sy(n):.1f}" width="{max(1, sx(x0 + pas) - sx(x0) - 2):.1f}" '
                 f'height="{H - mb - sy(n):.1f}" fill="var(--r2, #2A6B66)"><title>{nombre(x0, g)} à {nombre(x0 + pas, g)}{bord}, '
                 f'{n} {nom_niv if n > 1 else nom_niv[:-1]}</title></rect>')
    for x in graduations(lo, hi):
        s.append(f'<text x="{sx(x):.1f}" y="{H - 22}" text-anchor="middle" font-size="14" fill="var(--muted, #5D6371)" '
                 f'font-family="Work Sans, sans-serif">{nombre(x, 'entier') if x == int(x) else nombre(x)}</text>')
    s.append(f'<text x="{W - mr}" y="{H - 4}" text-anchor="end" font-size="14" fill="var(--muted, #5D6371)" '
             f'font-family="Work Sans, sans-serif">{unite}</text>')
    for n in (0, top):
        s.append(f'<text x="{ml - 8}" y="{sy(n) + 4:.1f}" text-anchor="end" font-size="14" fill="var(--muted, #5D6371)" '
                 f'font-family="Work Sans, sans-serif">{n}</text>')
    s.append(f'<line x1="{ml}" x2="{W - mr}" y1="{H - mb}" y2="{H - mb}" stroke="var(--line, #DCDDE0)"/>')
    if repere is not None and lo <= repere <= hi:
        s.append(f'<line x1="{sx(repere):.1f}" x2="{sx(repere):.1f}" y1="{mt}" y2="{H - mb}" stroke="var(--ink, #1C2028)" '
                 f'stroke-width="1.5"/>')   # repère en encre, trait plein, comme sur la fiche ; l'ocre reste au signal « ! »
        s.append(f'<text x="{sx(repere) + (6 if sx(repere) < W / 2 else -6):.1f}" y="{mt - 10}" '
                 f'text-anchor="{"start" if sx(repere) < W / 2 else "end"}" font-size="14" fill="var(--ink, #1C2028)" '
                 f'font-family="Work Sans, sans-serif">repère {nombre(repere, g)}</text>')
    s.append("</svg>")
    return {"svg": "".join(s), "n": len(v), "q1": quantile(v, .25), "med": quantile(v, .5), "q3": quantile(v, .75),
            "min": v[0], "max": v[-1], "nzero": sum(1 for x in v if x == 0)}


def totaux(pid: str, dernier: Path, france: dict) -> list[dict]:
    """Totaux de la profession dans les fichiers publiés : France en personnes distinctes, rattachées à un territoire,
    puis la somme de chaque niveau, chacun juste pour ce qu'il compte."""
    pop_fr = france["pop"]
    out = []
    n_fr = (france["n"].get(pid) or [None, None, None])[2]
    if n_fr is not None:
        out.append({"quoi": "France, personnes distinctes qui exercent", "n": n_fr, "pop": pop_fr, "fichier": "effectifs_france.csv", "choisi": True})
    for l in _lire(dernier / "parcours_activites.csv"):
        if l["prof"] == pid and _num(l.get("dans_densites")) is not None:
            out.append({"quoi": "Rattachées à un territoire, hors téléconsultation et activités sans soins",
                        "n": int(_num(l["dans_densites"])), "pop": pop_fr, "fichier": "parcours_activites.csv"})
    for lv, quoi in (("reg", "Somme des régions"), ("dep", "Somme des départements, base du repère des départements"),
                     ("epci", "Somme des intercommunalités, base du repère des intercommunalités"), ("com", "Somme des communes")):
        lignes = _lire(dernier / f"effectifs_{lv}_all.csv")
        if not lignes or f"n_{pid}" not in lignes[0]:
            continue
        n = sum(_num(l[f"n_{pid}"]) or 0 for l in lignes)
        p = sum(_num(l["population"]) or 0 for l in lignes if _num(l[f"n_{pid}"]) is not None)
        out.append({"quoi": quoi, "n": int(n), "pop": p, "fichier": f"effectifs_{lv}_all.csv"})
    for o in out:
        o["dens"] = o["n"] / o["pop"] * 1e4 if o["pop"] else None
    return out


def construire(env, commun: dict, A: dict, sd: dict, dernier: Path, site: Path, doi: str | None) -> tuple[list[Path], dict]:
    """Écrit indicateur/<slug>.html et rend les pages et, pour la recherche, le chemin de la fiche de chaque indicateur
    du catalogue (identifiant du catalogue, « prof:psychiatre » pour une profession)."""
    from .atelier import _limite
    dossier = site / "indicateur"
    dossier.mkdir(parents=True, exist_ok=True)
    gabarit = env.get_template("fiche_indicateur.html")
    doms = {d["id"]: d for d in A["domaines"]}
    conc = {(l["professions"], l["mode"]): l for l in _lire(dernier / "concordance_effectifs.csv")}
    ctx = {c["id"]: c for c in sd["contexte"]}
    mayotte = (sd.get("limites") or {}).get("mayotte") or {}
    version = dernier.name
    pages, index = [], {}
    modes = {e["id"]: e for e in A["ind"] if e.get("type") == "prof"}
    T = AF.Affichage(sd, dernier)
    for e in A["ind"]:
        if e.get("type") == "ctx":
            pass
        elif e.get("type") == "prof" and e.get("mode") == "all":
            pass
        else:
            continue
        niveaux = [lv for lv in ORDRE if lv in e["niv"]]
        if not niveaux:
            continue
        prof = e["type"] == "prof"
        par_niv = []
        for lv in niveaux:
            S = T.serie(e["id"], lv)
            if S is None or S.med is None:
                continue
            par_niv.append({"lv": lv, "nom": NOMS[lv][1], "rep": S.ref, "de": de(NOMS[lv][1]), "rep_lib": S.ref_lib(),
                            **repartition(S.v, S.ref, NOMS[lv][1], e.get("u") or "", S.genre)})
        if not par_niv:
            continue
        g = T.serie(e["id"], par_niv[0]["lv"]).genre
        nature = AF.NATURE_REPERE[T.serie(e["id"], par_niv[0]["lv"]).ref_type]
        fin = par_niv[0]
        limites = []
        li = _limite(sd, ("prof:" + e["prof"]) if prof else e["id"])
        if li and (li.get("texte") or li.get("court")):
            limites.append(li.get("texte") or li.get("court"))
        if prof:
            limites.append("Une densité de personnes ne dit ni le temps de travail, ni les délais de rendez-vous, ni le reste à charge.")
        if mayotte.get("texte"):
            limites.append(mayotte["texte"])
        c = ctx.get(e["id"], {})
        # espaces insécables dans les nombres des titres (« pour 10 000 habitants » ne se coupe pas, F3)
        insec = lambda t: re.sub(r"(\d) (\d{3})", lambda m: m.group(1) + "\u00a0" + m.group(2), t or "")  # noqa: E731
        f = {"id": e["id"], "slug": slug(e["id"]), "lab": insec(e["lab"]), "u": insec(e.get("u")), "prof": prof,
             "dom": doms.get(e.get("domb"), {}), "sous": e.get("sous"), "sm": e.get("sm"),
             "exp": e.get("exp") or "", "src": e.get("src") or "", "lic": e.get("lic") or "", "an": e.get("an") or "",
             "niveaux": [NOMS[lv][1] for lv in niveaux], "par_niv": par_niv, "fin": fin, "limites": limites,
             "agregation": c.get("agregation"), "fiche_source": c.get("fiche"), "grp": e.get("grp"), "g": g,
             "nature_repere": nature}
        if prof:
            pid = e["prof"]
            f["n_fr"] = (sd["france"]["n"].get(pid) or [None] * 3)
            fac = par_habitants(sd, pid)
            f["par"] = "100 000" if fac == 100000 else "10 000"
            f["dens_fr"] = f["n_fr"][2] / sd["france"]["pop"] * fac if f["n_fr"][2] else None
            f["totaux"] = totaux(pid, dernier, sd["france"])
            for t in f["totaux"]:
                t["dens"] = t["n"] / t["pop"] * fac if t["pop"] else None
            f["modes"] = [(nm, modes.get(f"prof:{pid}:{m}")) for m, nm in (("lib", "libéraux"), ("sal", "salariés"))]
            k = conc.get((pid, "all"))
            if k and _num(k.get("ecart")) is not None:
                f["drees"] = {"n": int(_num(k["drees"])), "annee": k["annee_drees"], "champ": k["champ_drees"],
                              "ecart": _num(k["ecart"]), "attendu": _num(k.get("ecart_a_l_attendu")), "source": k.get("source")}
            f["fichiers"] = [(f"effectifs_{lv}_all.csv", NOMS[lv][1]) for lv in niveaux] + [("parcours_activites.csv", "du nombre d'inscrits au nombre compté dans les densités")]
            f["croiser"] = f"croiser.html#x={e['id']}"
            f["atlas"] = f"atlas.html#?fam={'sm' if e.get('sm') else 'sante'}&prof={pid}"
        else:
            odbl = "ODbL" in (e.get("lic") or "")
            f["fichiers"] = [(f"contexte_{lv}{'_odbl' if odbl else ''}.csv", NOMS[lv][1]) for lv in niveaux]
            f["croiser"] = f"croiser.html#y={e['id']}"
        f["fichiers"] = [x for x in f["fichiers"] if (dernier / x[0]).exists()]
        # petite carte de France, en aplat par département (audit de contrôle du 30 octobre 2026, point I1, règle 15)
        from .cartes_presentation import choroplethe
        f["carte"] = choroplethe(A, "dep", e["id"], f["lab"], f["u"]) if "dep" in niveaux else None
        f["donnees_fig"] = f"../donnees/{version}/{f['fichiers'][0][0]}" if f["fichiers"] else ""
        cit = f"{commun['citation_auteur']} ({commun['annee_version']}). {f['lab']}, {f['u']}. {config.NOM_PROJET}, version du {commun['date_longue']}" + ((f", toutes les versions doi:{doi}" if doi == config.DOI_DONNEES else f", doi:{doi}") if doi else "")
        html = gabarit.render(dict(commun, racine="../", page="domaines", titre=f"{f['lab']}, {f['u']}" if f["u"] else f["lab"],
                                   classe_main="indicateur", f=f, version=version, doi=doi, citation=cit,
                                   # DOI cliquable dans la citation (règle 11), le lien posé ici et non dans le gabarit,
                                   # qui l'échapperait (contre-audit du 6 novembre 2026)
                                   citation_html=_html.escape(cit, quote=False).replace(
                                       f"doi:{doi}", f'<a href="https://doi.org/{doi}">doi:{doi}</a>') if doi
                                   else _html.escape(cit, quote=False),
                                   description=f"Fiche de l'indicateur {f['lab']}, définition, source, répartition des territoires et limites."))
        (dossier / f"{f['slug']}.html").write_text(html, encoding="utf-8")
        pages.append(dossier / f"{f['slug']}.html")
        index[e["id"].replace(":all", "")] = f["slug"]
    return pages, index
