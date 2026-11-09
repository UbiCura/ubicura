"""Accueil, page du modèle des domaines, données de la recherche et du glossaire (présentation du 30 octobre 2026).

L'accueil part de la recherche d'un territoire (commune, code postal, intercommunalité, département, région) ou d'un
indicateur, puis la santé mentale, les sept domaines autour de l'offre et les derniers ajouts. Chaque chiffre est relu
dans les résultats de la version, aucun n'est écrit à la main.
"""
import csv
import json
import shutil
from pathlib import Path

from . import config, domaines as D
from . import themes as TH
from .fiche_territoire import FINE, annee_source, nombre

NIVEAUX = ("reg", "dep", "epci")


def _lire(f: Path) -> list[dict]:
    if not f.exists():
        return []
    with f.open(encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def _nb(s):
    return float(str(s).replace(",", ".")) if s not in (None, "") else None


def catalogue(site_data: dict) -> list[dict]:
    """Indicateurs du site, professions comprises, avec leur domaine, leur sous-thème et leur drapeau santé mentale."""
    from .atelier import profession_croisable
    sortie = []
    for p in site_data.get("professions", []):
        # une profession présente dans moins de 10 territoires à chaque niveau n'entre ni dans Croiser ni dans le
        # compte des indicateurs (même règle, atelier.profession_croisable)
        if site_data.get("niveaux") and not profession_croisable(site_data, p["id"]):
            continue
        ind = {"id": "prof:" + p["id"], "label": p.get("libelle") or p["id"], "famille": p.get("famille", "")}
        dom, sous = D.classer(ind)
        sortie.append({**ind, "domaine": dom, "sous": sous, "sm": D.sante_mentale(ind)})
    for c in site_data.get("contexte", []):
        dom, sous = D.classer(c)
        sortie.append({"id": c["id"], "label": c.get("label"), "famille": c.get("famille", ""), "unite": c.get("unite"),
                       "domaine": dom, "sous": sous, "sm": D.sante_mentale(c), "source": c.get("source")})
    return sortie


def recherche(site_data: dict, dernier: Path, brut: Path, fiches: dict | None = None) -> dict:
    """Données de la recherche : territoires, communes (avec leur intercommunalité) et indicateurs, chacun avec le
    chemin de sa fiche quand elle existe (fiches, identifiant du catalogue vers le nom de la page)."""
    niv = site_data["niveaux"]
    noms_dep = {u["c"]: u["nm"] for u in niv["dep"]["units"]}
    terr = {lv: [[u["c"], u["nm"], u["pop"], noms_dep.get(u.get("p"), u.get("p", "")) if lv == "epci" else u.get("p", "")]
                 for u in niv[lv]["units"]] for lv in NIVEAUX}
    epci_de = {}
    for l in _lire(dernier / "accessibilite_communes.csv"):
        epci_de.setdefault(l["code"], l["epci"])
    communes, arrondissements = [], []
    ref = brut / "ref_communes.json"
    if ref.exists():
        lus = json.loads(ref.read_text(encoding="utf-8"))
        for c in lus:
            if c.get("type") != "commune-actuelle" or not epci_de.get(c["code"]):
                continue
            cps = c.get("codesPostaux") or []
            communes.append([c["code"], c["nom"], " ".join(cps), int(c.get("population") or 0), epci_de[c["code"]]])
        # les 45 arrondissements municipaux de Paris, Lyon et Marseille (type « arrondissement-municipal » du
        # référentiel, avec le code de leur commune) : « Paris 15e » ou « psychiatres Lyon 3e » ne trouvaient rien
        # (contre-audit de la recherche, 8 novembre 2026). Ils mènent à la fiche de leur commune, comme elle : [code, nom,
        # codes postaux, habitants, intercommunalité de la commune, code de la commune]. À part des communes, pour que
        # la recherche de l'accueil (recherche.js) reste telle quelle.
        for c in lus:
            if c.get("type") == "arrondissement-municipal" and epci_de.get(c.get("commune")):
                arrondissements.append([c["code"], c["nom"], " ".join(c.get("codesPostaux") or []),
                                        int(c.get("population") or 0), epci_de[c["commune"]], c["commune"]])
    inds = [[i["id"], i["label"], D.PAR_ID[i["domaine"]]["nom"], i["domaine"], (fiches or {}).get(i["id"], "")]
            for i in catalogue(site_data) if i.get("label")]
    return {"territoires": terr, "communes": communes, "arrondissements": arrondissements, "indicateurs": inds}


def pages_recherche(site: Path) -> list[list[str]]:
    """Pages, outils, thèmes et questions que la recherche de l'en-tête propose (navigation, étape 2, 8 novembre 2026) :
    [titre, adresse depuis la racine, genre, précision]. Les questions d'Explorer sont lues sur sa page construite, celles
    des pages de l'offre sur pages_domaine.QUESTIONS, les thèmes sur themes.THEMES : rien n'est recopié à la main."""
    import re
    from . import pages_domaine as PD, themes as TH
    out = [["Autour d’un lieu", "zone.html", "outil", "les habitants et les structures de soins dans un rayon autour d’une commune"],
           ["Comparer des territoires", "comparer.html", "outil", "deux à quatre territoires côte à côte"],
           ["Croiser deux indicateurs", "croiser.html", "outil", "tout indicateur contre tout autre"],
           ["Explorer", "explorer.html", "outil", "les questions des rapports en figures réglables"],
           ["Atlas", "atlas.html", "outil", "la carte de chaque profession et le profil de chaque territoire"],
           ["Indicateurs", "indicateurs.html", "page", "tous les indicateurs, avec la recherche et les filtres"],
           ["Territoires", "territoires/index.html", "page", "les fiches et les rapports de chaque territoire"],
           ["Rapports nationaux", "rapports.html", "page", "santé mentale et santé, archivés avec leur DOI"],
           ["Télécharger les données", "methode-fichiers.html", "page", "les fichiers, leur dictionnaire et leur licence"],
           ["Sources des données", "donnees-sources.html", "page", "chaque jeu de données, son producteur et sa date"],
           ["Méthode et données", "methode.html", "page", "d’où viennent les chiffres et ce qu’ils ne disent pas"]]
    for th in TH.THEMES:
        if not th.get("a_venir"):
            out.append([th["nom"], th.get("page") or f"theme/{TH.slug(th['id'])}.html", "thème", "indicateurs de plusieurs domaines"])
    ex = site / "explorer.html"
    if ex.exists():
        # chaque question d'Explorer, avec l'ancre de sa section ou, à défaut, celle de sa première fenêtre (« Les
        # départements modestes rattrapent-ils leur retard depuis 2016 ? », les trajectoires, n'avait pas d'ancre)
        for sec in re.findall(r"<section[^>]*class=\"question\"[\s\S]*?(?=<section[^>]*class=\"question\"|$)", ex.read_text(encoding="utf-8")):
            h2 = re.search(r"<h2[^>]*>(.*?)</h2>", sec, flags=re.S)
            ancre = re.search(r'<section[^>]*id="([^"]+)"', sec) or re.search(r'<article[^>]*id="([^"]+)"', sec)
            if h2 and ancre:
                out.append([re.sub(r"<[^>]+>", "", h2.group(1)).strip(), f"explorer.html#{ancre.group(1)}", "question",
                            "Explorer, figure réglable"])
    for cle, page in (("sm", "domaine/sante-mentale.html"), ("sante", "domaine/sante.html")):
        for k, q in enumerate(PD.QUESTIONS[cle]):
            out.append([q[0].replace("\u2060", ""), f"{page}#q{k + 1}", "question",
                        "santé mentale" if cle == "sm" else "santé"])
    return out


def glossaire(site_data: dict, sigles: Path) -> dict:
    g = {l["sigle"]: l["definition"] for l in _lire(sigles)}
    for e in (site_data.get("meta") or {}).get("glossaire", []):
        if e.get("terme") and e.get("definition"):
            g.setdefault(e["terme"], e["definition"])
    return g


def chiffres_nationaux(site_data: dict, dernier: Path) -> list[dict]:
    """Trois chiffres datés et sourcés de l'accueil, relus dans les résultats."""
    out = []
    fr = site_data.get("france", {})
    n = (fr.get("n") or {}).get("psychologue")
    if n and fr.get("pop"):
        out.append({"n": nombre(n[-1], "entier"), "texte": f"psychologues, soit {nombre(n[-1] / fr['pop'] * 1e4, 'distance')} pour 10{FINE}000 habitants.",
                    "source": "RPPS, Agence du numérique en santé"})
    d = next((l for l in _lire(dernier / "distances_lieux_france.csv") if l["type"] == "lieu_cmp_adultes"), None)
    if d:
        out.append({"n": f"{nombre(_nb(d['distance_mediane_km']), 'distance')}{FINE}km",
                    "texte": "séparent la moitié des habitants du CMP pour adultes le plus proche, à vol d'oiseau.",
                    "source": "FINESS et ROR réunis, INSEE"})
    s = next((l for l in _lire(dernier / "concordance_cmp_sae.csv") if l["niveau"] == "fr"), None)
    if s:
        an = annee_source(site_data, "SAE")
        out.append({"n": nombre(_nb(s["cmp"]), "entier"),
                    "texte": f"CMP inscrits dans les bases, pour {nombre(_nb(s['sae_cmp']), 'entier')} déclarés par les hôpitaux à la SAE{(' de ' + str(an)) if an else ''}.",
                    "source": "FINESS, ROR, SAE de la DREES"})
    return out


def part_psychologue_sans_psychiatre(dernier: Path):
    """Part des habitants dans une intercommunalité où exerce un psychologue mais aucun psychiatre déclaré."""
    lignes = [l for l in _lire(dernier / "combinaisons.csv") if l["niveau"] == "epci" and l["psychologue"] == "True"
              and l["psychiatre"] == "False"]
    return sum(_nb(l["part_population"]) for l in lignes) if lignes else None


def derniers_ajouts(journal: Path, n=4) -> list[list[str]]:
    from .site import date_longue
    sortie = []
    for l in _lire(journal)[-n:][::-1]:
        # la phrase qui date une ancienne extraction du répertoire n'est pas reprise, l'accueil ne donne qu'une date du
        # RPPS, celle de la version en ligne (audit de contrôle du 30 octobre 2026, point B3)
        phrases = [x for x in l["texte"].split(". ") if "extraction du répertoire" not in x] or l["texte"].split(". ")
        texte = phrases[0].rstrip(".") + "."
        sortie.append([l["date"], date_longue(l["date"]).rsplit(" ", 1)[0], texte])
    return sortie


def construire(env, commun: dict, dernier: Path, site_data: dict, site: Path, gabarits: Path, registre: Path) -> list[Path]:
    """Écrit l'accueil (index.html), la page des domaines, les scripts et les données de la présentation."""
    dossier = site / "presentation"
    dossier.mkdir(parents=True, exist_ok=True)
    for f in (gabarits / "presentation").glob("*.js"):
        shutil.copy(f, dossier / f.name)
    (dossier / "glossaire.json").write_text(json.dumps(glossaire(site_data, config.RACINE / "contenus" / "sigles.csv"),
                                                       ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    cat = catalogue(site_data)
    venir = D.bases_a_venir(registre)
    tuiles = []
    for d in D.DOMAINES:
        mes = [i for i in cat if i["domaine"] == d["id"]]
        exemples = []
        for so in d["sous"]:
            e = next((i for i in mes if i["sous"] == so), None)
            if e and len(exemples) < 3:
                exemples.append(e["label"])
        exemples += venir.get(d["id"], [])[:3 - len(exemples)]
        tuiles.append({**d, "n": len(mes), "venir": len(venir.get(d["id"], [])), "exemples": exemples,
                       "sm": sum(1 for i in mes if i["sm"])})
    nsm = sum(1 for i in cat if i["sm"])
    part = part_psychologue_sans_psychiatre(dernier)
    pages = []
    # atelier « Croiser », tout indicateur contre tout autre (reprend « Croiser deux indicateurs » d'Explorer)
    from . import atelier
    from .site import doi_cite
    A = atelier.construire(site_data, dernier, site, registre, commun["date_longue"], doi_cite("donnees", dernier.name))
    # fiche de chaque indicateur, puis la recherche qui y mène
    from . import fiche_indicateur
    p_ind, fiches = fiche_indicateur.construire(env, commun, A, site_data, dernier, site, doi_cite("donnees", dernier.name))
    pages += p_ind
    donnees_r = recherche(site_data, dernier, config.BRUT, fiches)
    donnees_r["pages"] = pages_recherche(site)
    (dossier / "recherche.json").write_text(json.dumps(donnees_r, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # réponses directes de la recherche de l'en-tête, un fichier par territoire, chiffres de la règle d'affichage unique
    from . import reponses
    reponses.ecrire(site_data, dernier, site)
    for i in cat:
        i["fiche"] = fiches.get(i["id"], "")
    # page « Indicateurs », fabriquée depuis le catalogue unique (navigation, étape 2, 8 novembre 2026)
    from . import page_indicateurs
    pages += page_indicateurs.construire(env, commun, site_data, dernier, site, A, fiches)
    # pages par domaine, la santé mentale et la santé au centre, les sept domaines autour
    from . import pages_domaine
    pages += pages_domaine.construire(env, commun, A, site_data, dernier, site, registre, doi_cite("donnees", dernier.name), fiches)
    # pages des thèmes transversaux (navigation, étape 2, 8 novembre 2026)
    pages += pages_domaine.construire_themes(env, commun, site_data, dernier, site, A, fiches, doi_cite("donnees", dernier.name))
    ctx = dict(commun, racine="", page="accueil", tuiles=tuiles, nationaux=chiffres_nationaux(site_data, dernier),
               part_sans_psychiatre=(nombre(part * 100, "distance") + FINE + "%") if part else None,
               n_sm=nsm, n_total=len(cat), ajouts=derniers_ajouts(config.RACINE / "contenus" / "journal_resume.csv"),
               dernier=dernier.name, classe_main="accueil")
    (site / "index.html").write_text(env.get_template("portail.html").render(ctx, titre="L’offre de soins en France, territoire par territoire"), encoding="utf-8")
    pages.append(site / "index.html")
    doms = []
    for d in D.DOMAINES:
        mes = [i for i in cat if i["domaine"] == d["id"]]
        # n et venir comme dans le schéma : la liste qui le remplace au téléphone écrivait « aucun indicateur » partout
        # (relecture de l'étape 4, 5 novembre 2026)
        doms.append({**d, "indicateurs": mes, "venir_liste": venir.get(d["id"], []), "n": len(mes),
                     "venir": len(venir.get(d["id"], [])),
                     "par_sous": [(so, [i for i in mes if i["sous"] == so]) for so in d["sous"]]})
    (site / "domaines.html").write_text(env.get_template("domaines.html").render(
        dict(commun, racine="", page="domaines", titre="L’offre de soins au centre, sept domaines autour",
             classe_main="domaines", domaines=doms, schema=schema(tuiles), n_sm=nsm,
             themes=[dict(x, slug=TH.slug(x["id"])) for x in TH.THEMES],
             doi=doi_cite("donnees", dernier.name))), encoding="utf-8")
    pages.append(site / "domaines.html")
    (site / "croiser.html").write_text(env.get_template("croiser.html").render(
        dict(commun, racine="", page="croiser", titre="Croiser librement", classe_main="croiser",
             description="Tout indicateur du site contre tout autre, à chaque niveau géographique, avec la mesure du lien et les limites des sources.")),
        encoding="utf-8")
    pages.append(site / "croiser.html")
    # matrice des liens entre l'offre et les autres domaines, vue d'ensemble de l'atelier
    from . import liens
    liens.construire(site_data, dernier, site, commun["date_longue"], doi_cite("donnees", dernier.name), fiches)
    (site / "liens.html").write_text(env.get_template("liens.html").render(
        dict(commun, racine="", page="croiser", titre="Les liens entre l’offre et les autres domaines", classe_main="liens",
             description="Matrice des liens entre chaque profession et les indicateurs des autres domaines, à densité de population égale, au-delà d'un seuil unique.")),
        encoding="utf-8")
    pages.append(site / "liens.html")
    (site / "comparer.html").write_text(env.get_template("comparer.html").render(
        dict(commun, racine="", page="comparer", titre="Comparer des territoires", classe_main="comparer",
             description="Jusqu'à quatre territoires côte à côte, chaque valeur face au repère de son niveau.")),
        encoding="utf-8")
    pages.append(site / "comparer.html")
    # autour d'un lieu, ou sur un périmètre composé commune par commune
    from . import zone
    zone.construire(dernier, site, commun["date_longue"], doi_cite("donnees", dernier.name), site_data)
    (site / "zone.html").write_text(env.get_template("zone.html").render(
        dict(commun, racine="", page="territoires", titre="Autour d’un lieu, ou sur un périmètre", classe_main="zone",
             description="Les habitants et les structures de soins dans un rayon autour d'une commune, ou sur un périmètre composé commune par commune.")),
        encoding="utf-8")
    pages.append(site / "zone.html")
    return pages


def schema(tuiles: list[dict]) -> dict:
    """Positions du schéma du modèle, l'offre au centre et sept domaines sur une ellipse (viewBox 980 x 520)."""
    import math
    cx, cy = 490, 266
    autour = [t for t in tuiles if not t.get("centre")]
    noeuds = []
    for k, t in enumerate(autour):
        a = -math.pi / 2 + (k + .5) * 2 * math.pi / len(autour)
        # nom long, le même que sur l'accueil et les pages de domaine (référentiel unique de pipeline/domaines.py,
        # audit de contrôle du 30 octobre 2026, point I3), coupé en deux lignes d'au plus 20 caractères environ
        nom, l1, l2 = t["nom"], t["nom"], ""
        if len(nom) > 20:
            mots, l1 = nom.split(" "), ""
            for k, m in enumerate(mots):
                if len((l1 + " " + m).strip()) > 20 and l1:
                    l2 = " ".join(mots[k:])
                    break
                l1 = (l1 + " " + m).strip()
        noeuds.append({**t, "x": round(cx + 400 * math.cos(a), 1), "y": round(cy + 200 * math.sin(a), 1), "l1": l1, "l2": l2})
    centre = next(t for t in tuiles if t.get("centre"))
    return {"cx": cx, "cy": cy, "noeuds": noeuds, "centre": centre}
