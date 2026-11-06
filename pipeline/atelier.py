"""Données de l'atelier « Croiser » (présentation du 30 octobre 2026, maquette de l'atelier validée).

Tout indicateur du catalogue contre tout autre, à chaque niveau où les deux existent : indicateurs du profil des
territoires, densités de toutes les professions dans les trois modes d'exercice, évolutions depuis 2016, bases à venir
du registre. Valeurs relues dans site_data.json, aucun calcul statistique ici, l'atelier calcule dans la page la
corrélation de rang, son intervalle, la corrélation partielle et la correction de Benjamini-Hochberg. Le fond de carte
est celui d'Explorer, projeté une fois pour toutes. Mayotte est écartée des croisements entre territoires
(config.DEPARTEMENTS_EXCLUS_CROISEMENTS), mais comptée dans le repère des professions, comme dans la fiche.
"""
import json
import math
from pathlib import Path

from . import config, domaines as D
from .fiche_territoire import _date_rpps, annee_indicateur
from .lecture import pluriel
from . import affichage as AF
from .affichage import par_habitants

NIVEAUX = ("reg", "dep", "epci")
NOMS_NIV = {"reg": "Régions", "dep": "Départements", "epci": "Intercommunalités"}
REG_MAYOTTE = "06"


def _r4(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    if x == 0:
        return 0
    return round(x, max(0, 3 - int(math.floor(math.log10(abs(x))))))


def _limite(sd: dict, cid: str):
    lim, alias = sd.get("limites", {}), sd.get("limites_alias", {})
    if cid in lim:
        return lim[cid]
    for k, v in alias.items():
        if (cid == k or cid.startswith(k)) and v in lim:
            return lim[v]
    return None


# une profession entre dans les croisements à un niveau où elle est présente dans au moins 10 territoires
SEUIL_CROISABLE = 10


def _garde(sd: dict, lv: str) -> list[int]:
    """Territoires gardés dans les croisements (Mayotte exclue, config.DEPARTEMENTS_EXCLUS_CROISEMENTS)."""
    exclus_dep = set(getattr(config, "DEPARTEMENTS_EXCLUS_CROISEMENTS", ["976"]))
    return [k for k, u in enumerate(sd["niveaux"][lv]["units"])
            if not (lv == "dep" and u["c"] in exclus_dep) and not (lv == "reg" and u["c"] == REG_MAYOTTE)
            and not (lv == "epci" and u.get("p") in exclus_dep)]


def profession_croisable(sd: dict, pid: str, m: str = "all") -> bool:
    """Vrai si la profession a au moins un niveau où elle entre dans Croiser. Même règle pour le catalogue
    (portail.catalogue) et pour l'atelier, pour que le nombre d'indicateurs soit le même partout (relecture du
    5 novembre 2026 : « Médecin, spécialité non renseignée », 4 personnes, comptée sur Domaines et absente de Croiser)."""
    for lv in NIVEAUX:
        a = ((sd["niveaux"][lv]["n"].get(pid) or {}).get(m))
        if a and sum(1 for k in _garde(sd, lv) if a[k]) >= SEUIL_CROISABLE:
            return True
    return False


def donnees(sd: dict, dernier: Path, fond: Path, registre: Path, version: str, doi: str | None) -> dict:
    units, ind, val = {}, [], {lv: {} for lv in NIVEAUX}
    for lv in NIVEAUX:
        us = sd["niveaux"][lv]["units"]
        garde = _garde(sd, lv)
        units[lv] = {"garde": garde, "u": [{"c": us[k]["c"], "nm": us[k]["nm"], "p": us[k].get("p"), "pop": us[k]["pop"]}
                                           for k in garde]}

    def ranger(e, src):
        dom, sous = D.classer(src)
        e.update({"domb": dom, "sous": sous, "sm": D.sante_mentale(src)})

    for j, c in enumerate(sd["contexte"]):
        e = {"id": c["id"], "lab": c["label"], "u": c.get("unite"), "src": c.get("source"), "lic": c.get("licence"),
             "grp": c.get("groupe"), "exp": c.get("explication", ""), "niv": [], "type": "ctx",
             "an": str(annee_indicateur(c, sd) or "")}
        ranger(e, c)
        for lv in NIVEAUX:
            us = sd["niveaux"][lv]["units"]
            v = [_r4(us[k]["x"][j]) if us[k].get("x") and j < len(us[k]["x"]) else None for k in units[lv]["garde"]]
            if sum(x is not None for x in v) >= 10:
                val[lv][c["id"]] = v
                e["niv"].append(lv)
        li = _limite(sd, c["id"])
        if li:
            e["lim"] = li.get("court") or li.get("texte")
            e["limT"] = li.get("territoires") or {}
        if c.get("non_publies"):
            e["np"] = c["non_publies"]
        if e["niv"]:
            ind.append(e)

    date_rpps = _date_rpps(dernier)
    profs = [p for p in sd["professions"] if p.get("famille") in ("Santé mentale", "Santé")]
    for p in profs:
        pid, plur = p["id"], pluriel(p["libelle"])
        plur = plur[:1].upper() + plur[1:]
        # professions rares pour 100 000 habitants (affichage.par_habitants, audit du 30 octobre 2026, F17)
        fac = par_habitants(sd, pid)
        for m, nm in (("all", ""), ("lib", ", libéraux"), ("sal", ", salariés")):
            e = {"id": f"prof:{pid}:{m}", "prof": pid, "mode": m, "lab": plur + nm,
                 "u": "pour 100 000 habitants" if fac == 100000 else "pour 10 000 habitants",
                 "src": "RPPS (Agence du numérique en santé), population INSEE", "lic": "Licence Ouverte 2.0",
                 "grp": "Professionnels de santé", "exp": "Professionnels qui soignent la population, chacun compté une "
                 "fois dans chaque territoire où il exerce.", "niv": [], "type": "prof", "moy": {}, "an": ("répertoire RPPS du " + date_rpps) if date_rpps else ""}
            ranger(e, {"id": "prof:" + pid, "famille": p.get("famille")})
            li = _limite(sd, "prof:" + pid)
            if li:
                e["lim"] = li.get("court") or (li.get("texte") or "").split(". ")[0]
            for lv in NIVEAUX:
                L = sd["niveaux"][lv]
                a = (L["n"].get(pid) or {}).get(m)
                if not a:
                    continue
                g = units[lv]["garde"]
                pops = [L["units"][k]["pop"] for k in g]
                ns = [a[k] for k in g]
                if sum(1 for n in ns if n) < SEUIL_CROISABLE:
                    continue
                val[lv][e["id"]] = [_r4(n / q * fac) if (q and n is not None) else None for n, q in zip(ns, pops)]
                e["niv"].append(lv)
            if m == "all":
                e["modes"] = True
            if e["niv"]:
                ind.append(e)

    for e0 in sd.get("evolution", []):
        pid = e0["prof"]
        fam = next((p.get("famille") for p in sd["professions"] if p["id"] == pid), "")
        e = {"id": f"evol:{pid}", "prof": pid, "lab": f"{e0['lib']}, évolution de la densité de {e0['debut']} à {e0['fin']}",
             "u": "%", "src": "RPPS, photographies annuelles", "lic": "Licence Ouverte 2.0", "grp": "Évolution dans le temps",
             "exp": f"Variation de la densité pour 10 000 habitants entre {e0['debut']} et {e0['fin']}, même source aux deux dates.",
             "niv": [], "type": "evol", "debut": e0["debut"], "fin": e0["fin"], "d0": {}, "d1": {}, "an": f"{e0['debut']} à {e0['fin']}"}
        ranger(e, {"id": "evol:" + pid, "famille": fam})
        for lv in NIVEAUX:
            a = sd["niveaux"][lv].get("evolution", {}).get(pid)
            if not a:
                continue
            trip = [a[k] if a[k] else None for k in units[lv]["garde"]]
            val[lv][e["id"]] = [_r4(x[2] * 100) if x and x[2] is not None else None for x in trip]
            e["d0"][lv] = [_r4(x[0]) if x else None for x in trip]
            e["d1"][lv] = [_r4(x[1]) if x else None for x in trip]
            e["niv"].append(lv)
        if e["niv"]:
            ind.append(e)

    for d, noms in D.bases_a_venir(registre).items():
        for k, nom in enumerate(noms):
            ind.append({"id": f"venir:{d}:{k}", "lab": nom, "type": "venir", "domb": d, "sous": "À venir", "grp": "À venir",
                        "u": "", "niv": [], "sm": False, "src": "", "niveau": ""})

    cnt = {lv: {} for lv in NIVEAUX}
    for lv in NIVEAUX:
        L, g = sd["niveaux"][lv], units[lv]["garde"]
        for p in profs:
            a = (L["n"].get(p["id"]) or {}).get("all")
            if a:
                cnt[lv]["prof:" + p["id"]] = [a[k] for k in g]
        for typ, a in L.get("lieux", {}).items():
            cnt[lv][typ] = [a[k] for k in g]

    # repère, médiane, position, couleur et statut de chaque indicateur, calculés une fois par la règle d'affichage
    # (pipeline/affichage.py), les mêmes que la fiche d'un territoire ; les pages les écrivent sans rien recalculer
    # (presentation/chiffres.js). x, les valeurs dont l'arrondi à quatre chiffres des données ci-dessus s'écrirait
    # autrement que la valeur exacte (une demie à la frontière), données à leur arrondi d'affichage.
    T = AF.Affichage(sd, dernier)
    ref = {lv: {} for lv in NIVEAUX}
    aff = {"lv": {lv: {} for lv in NIVEAUX}, "ind": {}, **AF.pour_js()}
    for e in ind:
        if e.get("type") not in ("ctx", "prof"):
            continue
        S0 = None
        for lv in e["niv"]:
            S = T.serie(e["id"], lv)
            if S is None:
                continue
            S0 = S
            g = units[lv]["garde"]
            pub = T.publier(e["id"], lv, g)
            x = {}
            for j, k in enumerate(g):
                v4 = val[lv][e["id"]][j]
                if S.v[k] is not None and AF.nombre(S.v[k], S.genre) != AF.nombre(v4, S.genre):
                    x[j] = AF.arrondi(S.v[k], S.genre)
            if x:
                pub["x"] = x
            aff["lv"][lv][e["id"]] = pub
            if S.ref is not None:
                ref[lv][e["id"]] = round(S.ref, 6)
                if e.get("type") == "prof":
                    e["moy"][lv] = round(S.ref, 6)
        if S0 is not None:
            aff["ind"][e["id"]] = {"g": S0.genre, "k": S0.kind}
            e["g"] = S0.genre
        # fiche de l'indicateur (pipeline/fiche_indicateur.py), celle de tous les modes pour une profession
        from .fiche_indicateur import slug
        e["fi"] = slug(f"prof:{e['prof']}:all" if e.get("type") == "prof" else e["id"])
    return {"version": version, "doi": doi, "niveaux": NOMS_NIV, "units": {lv: units[lv]["u"] for lv in NIVEAUX},
            "n": cnt, "ref": ref, "aff": aff, "ind": ind, "val": val, "geo": _fond(fond, sd), "W": 660, "H": 560, "encarts": ENCARTS,
            "domaines": [{"id": d["id"], "nom": d["nom"], "court": d["court"], "sous": d["sous"]} for d in D.DOMAINES],
            "citation": config.CITATION_AUTEUR}


# -- fond de carte, projeté une fois pour toutes (métropole et encarts d'outre-mer) --------------------------------
W, H, PAS = 600, 560, 0.9
COS = math.cos(math.radians(46.5))
MET = (-5.3, 41.2, 9.7, 51.2)
ENCARTS = {"971": (6, 380, 76, 70), "972": (6, 456, 76, 50), "973": (6, 512, 76, 46), "974": (90, 500, 60, 56), "976": (156, 506, 48, 50)}
DEP_REG_DROM = {"01": "971", "02": "972", "03": "973", "04": "974", "06": "976"}


def _fond(fond: Path, sd: dict) -> dict:
    f = fond.read_text(encoding="utf-8")
    topo = json.JSONDecoder().raw_decode(f, f.index("{"))[0]
    sc, tr = topo["transform"]["scale"], topo["transform"]["translate"]
    arcs = []
    for a in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in a:
            x += dx
            y += dy
            pts.append((x * sc[0] + tr[0], y * sc[1] + tr[1]))
        arcs.append(pts)

    def anneau(idx):
        out = []
        for i in idx:
            pts = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(pts if not out else pts[1:])
        return out

    def polys_of(g):
        a = g["arcs"]
        if g["type"] == "Polygon":
            a = [a]
        return [[anneau(r) for r in poly] for poly in a]

    def bbox(polys):
        xs = [p[0] for poly in polys for r in poly for p in r]
        ys = [p[1] for poly in polys for r in poly for p in r]
        return min(xs), min(ys), max(xs), max(ys)

    x0, y0, x1, y1 = MET
    s = min((W - 10) / ((x1 - x0) * COS), (H - 10) / (y1 - y0))
    pm = lambda lon, lat: ((lon - x0) * COS * s + 65, (y1 - lat) * s + 5)  # noqa: E731

    def encart(bb, boite):
        a0, b0, a1, b1 = bb
        bx, by, bw, bh = boite
        c = math.cos(math.radians((b0 + b1) / 2))
        k = min(bw / ((a1 - a0) * c or 1), bh / ((b1 - b0) or 1))
        ox, oy = bx + (bw - (a1 - a0) * c * k) / 2, by + (bh - (b1 - b0) * k) / 2
        return lambda lon, lat: ((lon - a0) * c * k + ox, (b1 - lat) * k + oy)

    def chemin(polys, proj):
        parts = []
        for poly in polys:
            for r in poly:
                pts, last = [], None
                for lon, lat in r:
                    q = proj(lon, lat)
                    q = (round(q[0], 1), round(q[1], 1))
                    if last is None or abs(q[0] - last[0]) + abs(q[1] - last[1]) >= PAS:
                        pts.append(q)
                        last = q
                if len(pts) >= 3:
                    parts.append("M" + "L".join(f"{x:g},{y:g}" for x, y in pts) + "Z")
        return "".join(parts)

    dep_geo = {g["properties"]["dep"]: polys_of(g) for g in topo["objects"]["dep"]["geometries"]}
    pe = {d: encart(bbox(dep_geo[d]), ENCARTS[d]) for d in ENCARTS if d in dep_geo}
    dep_of_epci = {u["c"]: u.get("p") for u in sd["niveaux"]["epci"]["units"]}
    geo = {}
    for lv in NIVEAUX:
        geo[lv] = {}
        for g in topo["objects"][lv]["geometries"]:
            c = g["properties"][lv]
            d = c if lv == "dep" else (DEP_REG_DROM.get(c) if lv == "reg" else dep_of_epci.get(c))
            proj = pe.get(d) if d in ENCARTS else pm
            if proj is not None:
                geo[lv][c] = chemin(polys_of(g), proj)
    return geo


def construire(site_data: dict, dernier: Path, site: Path, registre: Path, version: str, doi: str | None) -> dict:
    """Écrit presentation/atelier_donnees.js, chargé par la page croiser.html seulement, et rend les données, reprises
    par les fiches des indicateurs."""
    A = donnees(site_data, dernier, site / "explorer" / "fond.js", registre, version, doi)
    f = site / "presentation" / "atelier_donnees.js"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("const A=" + json.dumps(A, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    return A
