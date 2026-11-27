"""Fiche courte et dossier complet d'un territoire (structure du site validée le 26 novembre 2026, maquettes dans
prototypes/structure_2026-11-25/, notes.md, sections 3 bis et 5).

La fiche courte, à l'adresse de chaque fiche (territoire/<niveau>/<code>.html), montre dans l'ordre : l'en-tête ; les
tuiles de chiffres clés, chacune avec sa réglette, sa phrase de lecture, sa définition et sa limite ; « Repères en santé
mentale » et « Repères en santé », dix indicateurs chacun ; la carte « Où les patients sont reçus » en 7 + 5 avec le bloc
« CMP pour adultes » ; chaque domaine en trois indicateurs phares ; les domaines sans base en une ligne de renvoi ; les
territoires contenus et voisins ; « Citer cette fiche ». Le dossier complet (territoire/<niveau>/<code>-complet.html) est
la fiche entière, avec un lien de retour.

Ce module ne calcule aucun chiffre : il choisit et range les lignes que fiche_territoire.fiche, constats.constats et
bandes_fiche.bandes ont déjà écrites avec la règle d'affichage unique (pipeline/affichage.py). Deux lectures seulement,
chacune faite ici une fois : le chiffre de la France de chaque profession, dans effectifs_france.csv, et les territoires
voisins, dans le fond de carte du site.

Les règles de choix, écrites et sans choix à la main :
- Repères : d'abord les indicateurs d'« En bref » (constats.CANDIDATS) de la partie, sans ceux des tuiles, puis les lignes
  suivantes des tableaux de la partie, dans leur ordre, jusqu'à dix ; un indicateur qu'aucun territoire du niveau n'a
  (CMP tous publics, dont le taux n'est pas publié) est écarté, pour tous les territoires du niveau ;
- domaines : les trois premiers indicateurs phares du domaine (pipeline/domaines.py) que le territoire possède ;
- voisins : territoires du même niveau dont le contour partage des sommets dans le fond de carte du site.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from . import affichage as AF
from .affichage import FINE, nombre

# les tuiles de chiffres clés, dans l'ordre de fiche_territoire.fiche (f["cles"]) : leurs indicateurs ne sont pas
# répétés dans les Repères
TUILES = ("prof:psychologue:all", "prof:psychiatre:all", "dist_lieu_cmp_adultes")
NB_REPERES = 10
NB_PHARES = 3
SUFFIXE_COMPLET = "-complet"
MOTS = {1: "Un", 2: "Deux", 3: "Trois", 4: "Quatre", 5: "Cinq", 6: "Six", 7: "Sept", 8: "Huit", 9: "Neuf", 10: "Dix"}
NIV_PLURIEL = {"reg": "régions", "dep": "départements", "epci": "intercommunalités"}

# chaque bloc de la fiche entière et sa place : fiche courte, dossier complet (ancre). Le test « ne rien perdre » suit
# chaque bloc à sa place dans les deux pages construites (planche_8_ne_rien_perdre.png, validée le 26 novembre 2026).
# (bloc, ancre au dossier complet, place sur la fiche courte, ancre ou sélecteur sur la fiche courte)
PLACES = [
    ("En-tête (niveau, territoire parent, habitants, version, DOI, outils)", "", "en tête", "tete-fiche"),
    ("Tuiles de chiffres clés", "", "après l'en-tête", "cles-fiche"),
    ("Tous les indicateurs de ce territoire", "porte", "lien « Dossier complet »", "lien-complet"),
    ("Barre des domaines", "", "remplacée par l'ordre de la page", ""),
    ("Carte « Où les patients sont reçus »", "bord", "après les Repères", "bord"),
    ("Repères en santé mentale (sectorisation, CMP)", "t-reperes", "à droite de la carte, « CMP pour adultes »", "t-reperes"),
    ("Lire les réglettes", "t-lire-r", "en tête des Repères", "t-lire-r"),
    ("En bref, douze indicateurs phares", "t-bref", "dans les Repères et les domaines", ""),
    ("Santé mentale, tableaux, cartes, évolution", "d-sm", "dix lignes dans « Repères en santé mentale », lien", "d-sm"),
    ("Offre de soins, tableaux, cartes, évolution", "d-sante", "dix lignes dans « Repères en santé », lien", "d-sante"),
    ("État de santé et recours aux soins", "d-recours", "trois indicateurs phares, lien vers les autres", "d-recours"),
    ("Population et logement", "d-population", "trois indicateurs phares, lien vers les autres", "d-population"),
    ("Revenus, emploi et pauvreté", "d-revenus", "trois indicateurs phares, lien vers les autres", "d-revenus"),
    ("Enfance, éducation et familles", "d-enfance", "trois indicateurs phares, lien vers les autres", "d-enfance"),
    ("Distances et mobilité", "d-mobilite", "trois indicateurs phares, lien vers les autres", "d-mobilite"),
    ("Violences et victimes (sans base)", "d-violences", "ligne de renvoi, bases nommées", "d-violences"),
    ("Environnement et cadre de vie (sans base)", "d-environnement", "ligne de renvoi", "d-environnement"),
    ("Comparer avec", "comparer", "lien « Comparer » de l'en-tête", ""),
    ("Confiance et citation", "confiance", "« Citer cette fiche » gardé", "citer"),
    ("Les territoires contenus", "territoires-inclus", "« Territoires »", "territoires-inclus"),
    ("Tous les indicateurs, en un tableau", "tout-terr", "lien « Dossier complet »", ""),
]


def adresse_complet(code: str) -> str:
    """Nom du fichier du dossier complet, à côté de la fiche courte."""
    return f"{code}{SUFFIXE_COMPLET}.html"


# -- chiffre de la France de chaque profession -------------------------------------------------------------------------
_FRANCE: dict = {}


def france_professions(dernier: Path, sd: dict) -> dict:
    """Chiffre de la France de chaque profession, en personnes distinctes (chaque personne une fois, téléconsultation et
    activités sans soins à la population comprises) : {profession: {"n", "dens", "fac", "txt"}}. L'effectif est lu dans
    effectifs_france.csv (mode « all ») ; la densité le rapporte à la population de la France de la version
    (site_data["france"]["pop"]), comme la page de l'indicateur, dans l'unité de la profession."""
    cle = str(dernier)
    if cle in _FRANCE:
        return _FRANCE[cle]
    out = {}
    f = Path(dernier) / "effectifs_france.csv"
    pop = (sd.get("france") or {}).get("pop")
    if f.exists() and pop:
        with f.open(encoding="utf-8-sig") as fh:
            for l in csv.DictReader(fh, delimiter=";"):
                if l.get("mode") != "all" or not (l.get("n") or "").strip():
                    continue
                n = int(float(l["n"].replace(",", ".")))
                fac = AF.par_habitants(sd, l["prof"])
                d = n / pop * fac
                out[l["prof"]] = {"n": n, "dens": d, "fac": fac,
                                  "txt": f"France : {nombre(d)} {AF.txt_unite(fac)}, "
                                         f"{nombre(n, 'entier')} personnes"}
    _FRANCE[cle] = out
    return out


def phrase_totaux(lv: str) -> str:
    """La phrase des deux totaux, une fois par bloc de professions (planche_5_deux_totaux.png, validée le 26 novembre
    2026), sans le lien, que le gabarit pose."""
    niv = NIV_PLURIEL[lv]
    return (f"Chaque territoire se compare à l'ensemble des {niv} : la somme de leurs professionnels rapportée à la somme "
            f"de leurs habitants. Le chiffre de la France compte chaque personne une fois, y compris celles qu'aucun "
            f"territoire ne compte (téléconsultation, activités sans soins à la population) ; la somme des {niv} compte "
            f"dans chacune une personne qui exerce dans plusieurs. Selon la profession, le repère est donc plus haut ou "
            f"plus bas que la France.")


def poser_france(lignes: list, france: dict) -> None:
    """« France : 2,3 pour 10 000, 15 746 personnes » sur la ligne de chaque profession (tous modes d'exercice), sous sa
    position ; une ligne « dont libéraux » n'en porte pas."""
    for l in lignes:
        i = l.get("id") or ""
        if i.startswith("prof:") and i.endswith(":all") and not l.get("sous"):
            fr = france.get(i.split(":")[1])
            l["france"] = fr["txt"] if fr else ""


def page_totaux(lignes: list, cat_pages: dict) -> str:
    """La page de la première profession d'un bloc, où se lit « Pourquoi plusieurs totaux, et lequel citer »."""
    for l in lignes:
        i = l.get("id") or ""
        if i.startswith("prof:") and i.endswith(":all"):
            p = cat_pages.get(":".join(i.split(":")[:2]))
            if p:
                return p
    return ""


# -- une ligne des Repères et des domaines ------------------------------------------------------------------------------
def _unite(l: dict, cat: dict, niv_fiche: str) -> str:
    """L'unité d'une ligne, toujours avec sa population de référence (« pour 100 000 habitants », jamais « pour 100 000 »
    seul) ; une ligne dont le nom porte déjà l'unité (indicateurs du contexte) n'en a pas d'autre. La population est celle
    que le catalogue nomme : aucune n'est devinée ici (les affections de longue durée se rapportent aux personnes du régime
    général, pas aux habitants ; test_unites_population_nommee)."""
    k = l.get("kind")
    if k == "prof":
        return AF.txt_unite(l.get("fac"))
    if k == "dist":
        return "km, médiane des habitants"
    return ((cat.get(l.get("id")) or {}).get("unite") or "").replace(" hab.", " habitants")


def _nom(l: dict) -> str:
    """Les distances se nomment comme dans Comparer, « Distance au … » ; un nom qui dit déjà « distance » est gardé."""
    lib = l.get("lib") or ""
    if (l.get("id") or "").startswith("dist_") and "distance" not in lib.lower():
        t = lib if lib[:3].isupper() else lib[:1].lower() + lib[1:]
        return "Distance au " + t
    return lib


def _limites(l: dict, k: dict | None) -> list[str]:
    """Les limites d'une ligne, comme la ligne détaillée les écrit (fiche_territoire.html, limite_ligne), et celle de son
    constat ; la note du nom de ligne (CATTP au même lieu qu'un CMP) se lit comme une limite."""
    out = []
    if l.get("precision"):
        out.append(l["precision"][:1].upper() + l["precision"][1:] + ".")
    lim = l.get("limite")
    if lim and lim.get("court"):
        out.append(lim["court"] + ((" " + lim["territoire"]) if lim.get("territoire") else ""))
    if k:
        lk = k.get("limite") or (k.get("pourquoi") or {}).get("limite")
        if lk and not any(lk in x for x in out):
            out.append(lk)
    return out


def ligne(l: dict, f: dict, cat: dict, constats: dict, avec_unite: bool = True) -> dict:
    """Une ligne de la matrice des Repères et des domaines, tirée de la ligne détaillée de la fiche entière (même valeur,
    même réglette, même position, même définition, même limite, même phrase de lecture)."""
    k = constats.get(l.get("id"))
    dep = (l.get("echelle") == "dep" or l.get("code") == "departement") and f["niveau"] != "dep"
    rep = ""
    if l.get("ref_type") == "mediane_territoires" and l.get("ref_txt"):
        e = cat.get(l.get("id")) or {}
        std = "standardis" in ((e.get("unite") or "") + (e.get("label") or ""))
        rep = (f"Repère, médiane des {NIV_PLURIEL.get(l.get('lv'), f['niv_pluriel'])} : {l['ref_txt']} ("
               + ("taux standardisé sur l'âge, qui ne s'additionne pas" if std else "indicateur qui ne s'additionne pas")
               + ").")
    publie = bool(l.get("txt")) and l.get("code") != "aucun"
    zero = ""
    if l.get("zero"):
        zero = (("Aucun inscrit" if l.get("kind") == "prof" else "Aucune structure") + f", comme dans {l['zero']} des "
                + (f["niv_pluriel"] if l.get("lv") == f["niveau"] else "départements") + ".")
    # le menu de la ligne sans « Voir sur la carte » : la carte de bloc est au dossier complet
    menu = dict(l, k=dict(l["k"], carte=None) if l.get("k") else None)
    return {"id": l.get("id"), "ancre": l.get("ancre"), "lv": l.get("lv"), "code_terr": l.get("code"),
            "nom": _nom(l), "page": l.get("page"), "sig": bool(l.get("limite") or (l.get("k") or {}).get("limite")),
            "etiq": (f"donnée du département{', ' + f['parent'] if f.get('parent') and f['niveau'] == 'epci' else ''}"
                     if dep else ""),
            "unite": _unite(l, cat, f["niveau"]) if avec_unite else "",
            "reg": l.get("reg"), "v": (l["txt"] + (" km" if l.get("kind") == "dist" else "")) if publie else "",
            "statut": "" if publie else (l.get("statut") or "non publié"),
            "raison": ((l.get("s") or {}).get("raison") or "") if not publie else "",
            "note": l.get("note") or "", "ic": l.get("ic"),
            "avant": l.get("avant") if publie else "", "avant_ecart": l.get("avant_ecart"), "couleur": l.get("couleur"),
            "mais": l.get("mais"), "pos": l.get("pos_txt") if publie else "", "marge": l.get("marge"),
            "zero": zero, "rep_med": rep, "defn": l.get("defn") or "", "lims": _limites(l, k),
            "phrase": (l.get("k") or {}).get("phrase") or "", "france": l.get("france") or "", "menu": menu}


def limites_communes(rangs: list[dict]) -> list[str]:
    """Une limite répétée à l'identique sur plusieurs lignes d'un bloc s'écrit une fois sous son « Comment lire », et
    n'est plus répétée sur les lignes."""
    c = Counter(x for r in rangs for x in dict.fromkeys(r["lims"]))
    communes = [x for x, n in c.items() if n >= 2]
    for r in rangs:
        r["lims"] = [x for x in r["lims"] if x not in communes]
    return communes


# -- les Repères ------------------------------------------------------------------------------------------------------
def niveau_serie(ident: str, lv: str) -> str:
    """Niveau où se lit un indicateur sur la fiche : celui du territoire, ou le département pour un indicateur publié
    seulement par département sur la fiche d'une intercommunalité (recours aux soins, psychiatrie à l'hôpital)."""
    from .fiche_territoire import RECOURS_DEP
    if lv == "epci" and (ident in {i for i, _ in RECOURS_DEP} or ident.startswith("sae_")):
        return "dep"
    return lv


def publie_au_niveau(dn, ident: str, lv: str) -> bool:
    """Un territoire au moins du niveau a une valeur publiée : sinon la ligne n'est jamais une valeur (CMP tous publics,
    dont le taux n'est pas publié) et n'entre pas dans les Repères, pour aucun territoire du niveau."""
    cache = dn.__dict__.setdefault("_publie_niv", {})
    k = (ident, niveau_serie(ident, lv))
    if k not in cache:
        S = dn.T.serie(ident, k[1])
        cache[k] = bool(S is not None and any(v is not None for v in S.v))
    return cache[k]


def choix_reperes(bande: dict, dn, lv: str, section: str) -> list[dict]:
    """Les lignes des Repères d'une partie : d'abord les indicateurs d'« En bref » de la partie (constats.CANDIDATS, la
    santé mentale avec l'accès au CMP pour adultes et le recours, la santé avec l'accès aux autres structures), sans ceux
    des tuiles, puis les lignes suivantes des tableaux de la partie, dans leur ordre, jusqu'à dix. Les mêmes indicateurs
    pour tous les territoires du niveau."""
    from .constats import CANDIDATS
    if section == "sm":
        en_bref = [i for s, i, *_ in CANDIDATS if s == "sm" or (s == "acces" and "cmp" in i) or s == "recours"]
    else:
        en_bref = [i for s, i, *_ in CANDIDATS if s == "sante" or (s == "acces" and "cmp" not in i)]
    lignes = [l for g in bande["groupes"] if not g.get("region") for l in g["lignes"] if l.get("id") and not l.get("sous")]
    par_id = {}
    for l in lignes:
        par_id.setdefault(l["id"], l)
    ordre = list(dict.fromkeys(en_bref + [l["id"] for l in lignes]))
    out = [par_id[i] for i in ordre if i in par_id and i not in TUILES and publie_au_niveau(dn, i, lv)]
    return out[:NB_REPERES]


# -- les territoires ---------------------------------------------------------------------------------------------------
def _sommets(T: dict) -> list:
    out = []
    for arc in T["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x, y))
        out.append(pts)
    return out


def _arcs(g: dict) -> set:
    def plat(x):
        if isinstance(x, int):
            yield x if x >= 0 else ~x
        else:
            for y in x:
                yield from plat(y)
    return set(plat(g.get("arcs", [])))


_VOISINS: dict = {}


def voisins_fond(fond: Path | None, pres: int = 1) -> dict:
    """Territoires voisins, lus dans le fond de carte du site (explorer/fond.js) : deux territoires du même niveau sont
    voisins quand leurs contours ont au moins deux sommets communs, à la précision du fond de carte. Le fond est
    simplifié : un voisin qui ne touche que par un point ou par un tronçon très court peut manquer (test_voisins_ign)."""
    if fond is None or not Path(fond).exists():
        return {}
    cle = str(fond)
    if cle in _VOISINS:
        return _VOISINS[cle]
    t = Path(fond).read_text(encoding="utf-8")
    T = json.JSONDecoder().raw_decode(t, t.index("{"))[0]
    S = _sommets(T)
    out = {}
    for niv, obj in T["objects"].items():
        par_pt = defaultdict(set)
        for g in obj.get("geometries", []):
            c = str((g.get("properties") or {}).get(niv))
            for a in _arcs(g):
                for (x, y) in S[a]:
                    par_pt[(x // pres, y // pres)].add(c)
        n = defaultdict(lambda: defaultdict(int))
        for cs in par_pt.values():
            if len(cs) > 1:
                for a in cs:
                    for b in cs - {a}:
                        n[a][b] += 1
        out[niv] = {a: sorted(b for b, k in d.items() if k >= 2) for a, d in n.items()}
    _VOISINS[cle] = out
    return out


def voisins_ign(contours: Path, ref_communes: Path, accessibilite: Path) -> dict:
    """Territoires voisins d'après le découpage de l'IGN (ADMIN EXPRESS, contours des communes en cache) : deux
    territoires sont voisins quand deux de leurs communes ont un sommet commun. Sert au contrôle des voisins du fond de
    carte (test_voisins_ign)."""
    G = json.loads(Path(contours).read_text(encoding="utf-8"))
    niv = {"epci": {}, "dep": {}, "reg": {}}
    for c in json.loads(Path(ref_communes).read_text(encoding="utf-8")):
        if c.get("type") == "commune-actuelle":
            niv["dep"][c["code"]], niv["reg"][c["code"]] = c.get("departement"), c.get("region")
    with Path(accessibilite).open(encoding="utf-8-sig") as fh:
        for l in csv.DictReader(fh, delimiter=";"):
            niv["epci"].setdefault(l["code"], l["epci"])
    par = defaultdict(set)
    for ft in G["features"]:
        c, g = ft["properties"]["code"], ft["geometry"]
        for p in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
            for anneau in p:
                for x, y in anneau:
                    par[(round(x * 1e6), round(y * 1e6))].add(c)
    out = {k: defaultdict(set) for k in niv}
    for cs in par.values():
        if len(cs) < 2:
            continue
        for k, m in niv.items():
            ts = {m.get(c) for c in cs} - {None, ""}
            for a in ts:
                out[k][a] |= ts - {a}
    return {k: {a: sorted(b) for a, b in v.items()} for k, v in out.items()}


def communes_epci(dn) -> dict:
    """Les communes de chaque intercommunalité, par leur nom (référentiel des communes en cache), dans l'ordre
    alphabétique : {code de l'intercommunalité: [noms]}."""
    if getattr(dn, "_communes_epci", None) is None:
        from . import config
        from .fiche_territoire import _cle_nom
        epci = {}
        for l in dn._csv("accessibilite_communes.csv"):
            epci.setdefault(l["code"], l.get("epci") or "")
        par: dict = {}
        f = config.BRUT / "ref_communes.json"
        if f.exists():
            for c in json.loads(f.read_text(encoding="utf-8")):
                e = epci.get(c["code"])
                if c.get("type") == "commune-actuelle" and e:
                    par.setdefault(e, []).append(c["nom"])
        dn._communes_epci = {e: sorted(v, key=_cle_nom) for e, v in par.items()}
    return dn._communes_epci


def territoires(dn, lv: str, code: str, niveaux: dict, voisins: dict) -> dict:
    """Les territoires de la fin de la fiche courte : ceux qu'il contient (ses communes pour une intercommunalité), et
    ses voisins du même niveau, liés à leur fiche."""
    from .fiche_territoire import _cle_nom
    noms = dn.noms[lv]
    vs = sorted((c for c in (voisins.get(lv) or {}).get(code, []) if c in noms), key=lambda c: _cle_nom(noms[c]))
    titre_v = {"epci": "Intercommunalités voisines", "dep": "Départements voisins", "reg": "Régions voisines"}[lv]
    if len(vs) == 1:
        titre_v = {"epci": "Intercommunalité voisine", "dep": "Département voisin", "reg": "Région voisine"}[lv]
    return {"communes": communes_epci(dn).get(code, []) if lv == "epci" else [],
            "voisins": [(c, noms[c]) for c in vs], "voisins_titre": titre_v, "voisins_niveau": lv}


# -- la fiche courte -------------------------------------------------------------------------------------------------
def donnees(f: dict, bandes: list, ks: list, dn, cat: dict, cat_pages: dict, niveaux: dict, voisins: dict,
            lire_confirmation: str, confiance_france: str) -> dict:
    """Ce que montre la fiche courte, rangé pour le gabarit fiche_courte.html."""
    lv, code = f["niveau"], f["code"]
    constats = {k["id"]: k for k in ks}
    par_id = {}
    for b in bandes:
        for g in b["groupes"]:
            if g.get("region"):
                continue
            for l in g["lignes"]:
                if l.get("id"):
                    par_id.setdefault(l["id"], l)
    complet = adresse_complet(code)
    # sous chaque tuile : sa réglette, sa phrase de lecture, sa définition et sa limite, et le lien vers sa ligne détaillée
    sous = []
    for c in f["cles"]:
        i = c.get("id")
        if i == "structures":
            sous.append({"structures": True, "defn": lire_confirmation, "ensemble": confiance_france,
                         "lims": [x for x in (f.get("reserves_structures") or [])[:1]], "lien": f"{complet}#t-sm-str"})
            continue
        l = par_id.get(i)
        if not l:
            sous.append(None)
            continue
        r = ligne(l, f, cat, constats)
        if not r["defn"] and i.startswith("dist_"):
            g = next((g for b in bandes for g in b["groupes"] if g.get("id") == "t-sm-dist"), None)
            r["defn"] = (g or {}).get("lire") or ""
        r["lien"] = f"{complet}#{l.get('ancre')}"
        sous.append(r)
    blocs = []
    for b, titre, tid, quoi in (
            (next(x for x in bandes if x["id"] == "sm"), "Repères en santé mentale", "t-rep-sm",
             "d’abord le CMP pour adultes, les psychiatres qualifiés pour l’enfant et les affections psychiatriques de "
             "longue durée, qui résument l’offre et le recours"),
            (next(x for x in bandes if x["id"] == "sante"), "Repères en santé", "t-rep-sante",
             "d’abord les médecins généralistes, les infirmiers et la distance au service d’urgences, qui résument "
             "l’offre et l’accès")):
        choix = choix_reperes(b, dn, lv, b["id"])
        rangs = [ligne(l, f, cat, constats) for l in choix]
        communes = limites_communes(rangs)
        medians = any(r["rep_med"] for r in rangs)
        profs = [l for l in choix if (l.get("id") or "").startswith("prof:")]
        blocs.append({"id": "d-" + b["id"], "titre": titre, "tid": tid, "rangs": rangs, "communes": communes,
                      "n_mot": MOTS.get(len(rangs), str(len(rangs))), "quoi": quoi, "tuiles": b["id"] == "sm",
                      "medians": medians, "totaux": phrase_totaux(lv) if profs else "",
                      "page_totaux": page_totaux(profs, cat_pages) if profs else "",
                      "lien": f"{complet}#d-{b['id']}"})
    doms, renvois = [], []
    for b in bandes:
        if not b.get("contexte"):
            continue
        if b.get("vide"):
            renvois.append({"id": "d-" + b["id"], "nom": b["nom"], "bases": list(b.get("venir") or [])})
            continue
        g = b["groupes"][0] if b["groupes"] else {"lignes": []}
        phares = [l for l in g["lignes"] if not l.get("sous")][:NB_PHARES]
        rangs = [ligne(l, f, cat, constats, avec_unite=False) for l in phares]
        communes = limites_communes(rangs)
        n_tous = sum(1 for l in g["lignes"] if not l.get("sous")) + (b.get("autres_n") or 0)
        lire = (b.get("lire_dom") or "") + (" " if b.get("lire_dom") else "") + \
            f"Valeur, ensemble et position parmi les {f['niv_pluriel']}, sans couleur de jugement."
        doms.append({"id": "d-" + b["id"], "nom": b["nom"], "compte": b["compte"], "lire": lire, "rangs": rangs,
                     "communes": communes, "autres": n_tous - len(rangs), "lien": f"{complet}#d-{b['id']}"})
    sous_f = [s for s in sous]
    prof_tuiles = [par_id[i] for i in TUILES[:2] if i in par_id]
    return {"complet": complet, "sous_tuiles": sous_f, "reperes": blocs, "domaines": doms, "renvois": renvois,
            "territoires": territoires(dn, lv, code, niveaux, voisins),
            "totaux_tuiles": phrase_totaux(lv) if prof_tuiles else "",
            "page_totaux_tuiles": page_totaux(prof_tuiles, cat_pages) if prof_tuiles else ""}
