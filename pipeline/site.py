"""Site statique (chantier 6). Pages générées avec Jinja2 à partir des résultats de chaque exécution.

site/index.html                      accueil, chiffres clés et « En bref »
site/index.html                      atlas, première page du site (atlas.html y renvoie)
site/rapports.html                   liste des versions
site/rapports/AAAA-MM-JJ/            sante-mentale.html, sante.html et leurs PDF
site/territoires/                    rapports par région et par département (dernière version seulement)
site/methode.html                    sources, contrôles, indicateurs, libellés, licences, fichiers
site/donnees/AAAA-MM-JJ/             CSV à télécharger et dictionnaire des colonnes
site/publications.html               page réservée (chantier 9)
site/a-propos.html                   présentation, indépendance, citation, contact (texte dans contenus/a_propos.md)

Chaque version datée de resultats/ devient une version des rapports. Les PDF sont imprimés par un
navigateur sans fenêtre (Edge sous Windows, Chromium ou Chrome sous Linux). Usage seul,
python -m pipeline.site"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config, dictionnaire, libelles, limites, mises_a_jour
from .lecture import nombre, date_longue
from .util import JOURNAL, controles_publics, date_version, lire_meta, log

SITE = config.RACINE / "site"
GABARITS = config.RACINE / "gabarits"
RAPPORTS = {"sante-mentale": ("rapport_sante_mentale.md", "Rapport santé mentale"),
            "sante": ("rapport_sante.md", "Rapport santé")}


# ---------------------------------------------------------------- Markdown vers HTML
# données de chaque figure, par début de nom de figure (fichier CSV de la version, lien sous la figure)
DONNEES_FIGURES = [("addicto_regions", "sante_mentale_sante_publique_france.csv"), ("lorenz_", "lorenz.csv"), ("effet_ville_", "correlations_contexte.csv"),
                   ("escalier_", "escalier_social.csv"), ("entonnoir_", "entonnoir.csv"), ("porte_", "porte_offre.csv"),
                   ("distance_", "accessibilite_communes.csv"), ("parcours_", "parcours_activites.csv"),
                   ("quadrants_", "quadrants.csv"), ("bivariee_", "contexte_dep.csv"), ("gwr_", "gwr_coefficients.csv"),
                   ("carte_dep_", "effectifs_dep_all.csv"), ("tuiles_dep_", "effectifs_dep_all.csv"),
                   ("multiples_", "effectifs_dep_all.csv"), ("unites_", "temps_acces.csv"),
                   ("_position", "effectifs_dep_all.csv"), ("_carte", "effectifs_epci_all.csv"),
                   ("_trajet", "temps_acces_communes.csv"), ("_unites", "temps_acces.csv"),
                   ("eloignement_", "escalier_distance_lieux.csv"), ("_distlieux", "distances_lieux_communes.csv"),
                   ("_sm_secteurs", "secteurs_psychiatrie.csv")]
# figures où l'on zoome et où l'on clique sur un point ou une zone pour lire son nom
ZOOMABLES = ("entonnoir_", "quadrants_", "carte_dep_", "multiples_", "bivariee_", "gwr_", "_carte", "_trajet",
             "_position", "tuiles_dep_", "_distlieux", "_secteurs")


def md_html(texte: str, graphiques: Path | None, imprimer=False, donnees: dict | None = None):
    """Convertit un rapport Markdown en HTML. Les volets « Pour aller plus loin » restent repliés à
    l'écran et sont ouverts à l'impression. Les marqueurs de graphiques sont remplacés par les figures.
    Renvoie (titre, corps, sommaire)."""
    lignes = texte.split("\n")
    titre = lignes[0].lstrip("# ").strip() if lignes and lignes[0].startswith("# ") else ""
    corps_md = "\n".join(lignes[1:] if titre else lignes)
    corps_md = corps_md.replace("<details>", '<details markdown="1" open>' if imprimer else '<details markdown="1">')
    md = markdown.Markdown(extensions=["tables", "md_in_html", "sane_lists", "toc"],
                           extension_configs={"toc": {"toc_depth": "2-4", "slugify": _ancre}})
    corps = md.convert(corps_md)
    if imprimer:
        corps = _parties_imprimees(corps)
        # un tableau de plus de 15 lignes peut se couper entre deux lignes, son en-tête est répété (style.css)
        corps = re.sub(r"<table>(.*?)</table>", lambda m: ('<table class="longue">' if m.group(1).count("<tr") > 16
                                                            else "<table>") + m.group(1) + "</table>", corps, flags=re.S)
        # un petit titre suivi d'un tableau court forme un bloc insécable, sinon le titre peut rester seul en bas de
        # page (rapport santé du 13 octobre 2026, « Handicap, adultes »)
        corps = re.sub(r"(<h([4-6])[^>]*>(?:(?!</h\2>).)*</h\2>\s*)(<table>(?:(?!</table>).)*</table>)",
                       r'<div class="ensemble">\1\3</div>', corps, flags=re.S)

    numero = [0]

    def figure(m):
        nom = m.group(1)
        f = graphiques / f"{nom}.svg" if graphiques else None
        if not f or not f.exists():
            return ""
        svg = f.read_text(encoding="utf-8")
        legende = re.search(r"<title>(.*?)</title>", svg)
        numero[0] += 1
        # autres professions de la même figure, proposées par des boutons (pas à l'impression)
        from .graphiques import VARIANTES
        ordre = [q for l in VARIANTES.values() for q in l] + ["q_psychiatrie_enfant"]
        variantes = [] if imprimer else sorted(
            graphiques.glob(f"{nom}__*.svg"),
            key=lambda v: ordre.index(v.stem.split("__", 1)[1]) if v.stem.split("__", 1)[1] in ordre else 99)
        choix, contenu = "", svg
        if variantes:
            svgs = [svg] + [v.read_text(encoding="utf-8") for v in variantes]
            noms = [(re.search(r'data-variante="([^"]*)"', x) or [None, f"Choix {i + 1}"])[1] for i, x in enumerate(svgs)]
            choix = ('<div class="choix-variante" role="group" aria-label="Profession affichée">'
                     + "".join(f'<button type="button" aria-pressed="{"true" if i == 0 else "false"}">{n}</button>'
                               for i, n in enumerate(noms)) + "</div>")
            contenu = "".join(f'<div class="variante"{"" if i == 0 else " hidden"}>{x}</div>' for i, x in enumerate(svgs))
        zoom = any(z in nom for z in ZOOMABLES) and not imprimer
        # données de la figure, proposées par « Citer et exporter » (gabarits/figures.js)
        attr = ""
        if donnees:
            csv = next((c for k, c in DONNEES_FIGURES if (nom.startswith(k) if k.endswith("_") else k in nom)), None)
            src = donnees["dossier"] / csv if csv else None
            if src is not None and src.exists():
                fichier = csv + (".zip" if src.stat().st_size > 2_000_000 else "")
                attr = f' data-donnees="{donnees["prefixe"]}{fichier}" data-donnees-nom="{fichier}"'
        # titre au-dessus de la figure, comme dans l'atlas, puis la figure elle-même
        return (f'<figure class="graphique{" zoomable" if zoom else ""}"{attr}>'
                + (f'<figcaption class="small muted"><strong>Figure {numero[0]}.</strong> <span class="leg">'
                   f'{legende.group(1)}</span>.</figcaption>' if legende else "")
                + f'<div class="fig-corps">{choix}{contenu}</div></figure>')
    corps = re.sub(r"<!--GRAPHIQUE (\S+)-->", figure, corps)
    # les paragraphes « Comment lire » en encadré, comme dans l'atlas
    corps = corps.replace("<p><strong>Comment lire.</strong>", '<p class="comment-lire"><strong>Comment lire.</strong>')
    corps = corps.replace("<p><strong>À savoir.</strong>", '<p class="a-savoir"><strong>À savoir.</strong>')
    corps = tableaux_larges(corps)
    if imprimer:
        corps = tableaux_etroits(coupures_fichiers(annexe_technique(a_savoir_une_fois(corps))))
    return titre, corps, md.toc


# ---------------------------------------------------------------- PDF des rapports (harmonisation, lot 5, 22 octobre 2026)
# Décisions de Lucas du 22 octobre 2026, les volets « Pour aller plus loin » réunis dans une annexe technique à la fin
# du PDF avec un renvoi à leur place, texte justifié sans trous, un même « À savoir » imprimé une seule fois.

def _sans_balises(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t)).strip()


def annexe_technique(corps: str) -> str:
    """Volets « Pour aller plus loin » déplacés dans une annexe numérotée (A1, A2...), un renvoi à leur place, avec le
    titre de la section où ils se trouvaient."""
    entrees = []

    def deplace(m):
        avant = corps[:m.start()]
        titres = re.findall(r"<h[2-5][^>]*>(.*?)</h[2-5]>", avant, flags=re.S)
        section = _sans_balises(titres[-1]) if titres else ""
        contenu = re.sub(r"<summary>.*?</summary>", "", m.group(1), count=1, flags=re.S).strip()
        n = len(entrees) + 1
        entrees.append(f'<section class="annexe-entree"><h4 id="annexe-a{n}">A{n}. {section}</h4>{contenu}</section>')
        return f'<p class="renvoi-annexe">Pour aller plus loin, annexe technique A{n}.</p>'
    corps2 = re.sub(r"<details[^>]*>(.*?)</details>", deplace, corps, flags=re.S)
    if not entrees:
        return corps
    return (corps2 + '<h2 class="annexe" id="annexe-technique">Annexe technique</h2><p>Les détails de méthode, les '
            "contrôles de solidité et les listes complètes de chaque analyse, dans l'ordre du rapport. Chaque section y "
            "renvoie par son numéro.</p>" + "".join(entrees))


def a_savoir_une_fois(corps: str) -> str:
    """Les encadrés « À savoir » mettent bout à bout les limites de config.LIMITES. À l'impression, une limite déjà
    donnée plus haut est retirée et remplacée par un renvoi à la section de sa première mention, un encadré qui
    n'apporte plus rien de nouveau devient ce seul renvoi."""
    from html import escape as _esc
    textes = [l["texte"] for l in config.LIMITES.values() if isinstance(l, dict) and l.get("texte")]
    vus = {}

    def un(m):
        box = m.group(0)
        titres = re.findall(r"<h[2-5][^>]*>(.*?)</h[2-5]>", corps[:m.start()], flags=re.S)
        section = _sans_balises(titres[-1]) if titres else ""
        renvois = []
        for tx in textes:
            forme = next((f for f in (tx, _esc(tx, quote=False)) if f in box), None)
            if forme is None:
                continue
            if tx in vus:
                box = box.replace(forme + " ", "", 1) if forme + " " in box else box.replace(forme, "", 1)
                if vus[tx] not in renvois:
                    renvois.append(vus[tx])
            else:
                vus[tx] = section
        if not renvois:
            return box
        noms = [f"« {r} »" for r in renvois]
        ou = (f"dans la section {noms[0]}" if len(noms) == 1
              else f"dans les sections {', '.join(noms[:-1])} et {noms[-1]}")
        reste = re.sub(r"\s*Sources?, .*$", "", _sans_balises(box), flags=re.S).replace("À savoir.", "").strip()
        if not reste:
            return f'<p class="a-savoir renvoi"><strong>À savoir.</strong> Même précaution que {ou}.</p>'
        return box.replace("<strong>À savoir.</strong>", f"<strong>À savoir.</strong> Voir aussi la précaution donnée {ou}.", 1)
    return re.sub(r'<p class="a-savoir">.*?</p>', un, corps, flags=re.S)


def coupures_fichiers(corps: str) -> str:
    """Points de coupure après les tirets bas des noms de fichiers du texte (jamais dans les balises), pour qu'un nom
    long passe à la ligne au lieu de creuser des blancs dans une ligne justifiée."""
    morceaux = re.split(r"(<[^>]+>)", corps)
    for i in range(0, len(morceaux), 2):
        morceaux[i] = re.sub(r"\b[\w-]+(?:_[\w-]+)+(?:\.(?:csv|md|json|zip))?",
                             lambda m: m.group(0).replace("_", "_<wbr>"), morceaux[i])
    return "".join(morceaux)


def tableaux_etroits(corps: str) -> str:
    """Tableau de trois colonnes ou moins, à sa largeur naturelle à l'impression au lieu d'être étiré."""
    def classe(m):
        entete = re.search(r"<tr>.*?</tr>", m.group(0), re.S)
        n = len(re.findall(r"<t[hd][ >]", entete.group(0))) if entete else 0
        return re.sub(r"<table( class=\"([^\"]*)\")?>", lambda t: f'<table class="{(t.group(2) or "") + " etroite"}">'.replace('" ', '"'),
                      m.group(0), count=1) if n and n <= 3 else m.group(0)
    return re.sub(r"<table[^>]*>.*?</table>", classe, corps, flags=re.S)


CESURES = re.compile(r"(Psycho|psycho|Pédo|pédo|Kinési|kinési|Ortho|ortho|Gynéco|gynéco|Ophtalmo)(?=\w)")


def _confirmation(dossier, lire, nb):
    """Niveaux de confirmation des structures, une colonne par type confronté aux listes indépendantes (page
    méthode). Les CMP pour adultes et pour enfants suivent leur CMP « tous publics », ils ne sont pas répétés."""
    f = dossier / "lieux_soins.csv"
    if not f.exists():
        return None
    import pandas as pd
    from . import config
    x = pd.read_csv(f, sep=";", dtype=str, usecols=lambda c: c in ("type", "confirmation"))
    if "confirmation" not in x:
        return None
    from .confirmation import NIVEAUX
    court = {"lieu_hdj_psy_adultes": "Hôpitaux de jour, adultes", "lieu_hdj_psy_enfants": "Hôpitaux de jour, enfants"}
    lib = {t[0]: court.get(t[0], t[1].split(",")[0]) for t in config.LIEUX_TYPES}
    types = [t for t in config.SIRENE_ENSEIGNES if x.loc[x["type"] == t, "confirmation"].notna().any()]
    if not types:
        return None
    n = {t: x.loc[x["type"] == t, "confirmation"].value_counts() for t in types}
    rows = [{"niveau": niv[0].upper() + niv[1:], "n": [nb(int(n[t].get(niv, 0))) for t in types]}
            for niv in NIVEAUX.values() if any(n[t].get(niv, 0) for t in types)]
    rows.append({"niveau": "Total", "n": [nb(int(n[t].sum())) for t in types]})
    fs = dossier / "sirene_sans_correspondant.csv"
    ns = nc = 0
    for r in (lire(fs) if fs.exists() else []):
        ns += 1
        nc += r.get("type") == "lieu_cmp"
    resume = (f"Sirene compte en outre {nb(ns)} établissements actifs sous une enseigne de l'un de ces types sans "
              f"structure correspondante, dont {nb(nc)} sous une enseigne de CMP, vérifiés établissement par "
              f"établissement. Les autres restent à vérifier. Tous sont listés dans sirene_sans_correspondant.csv.")
    return {"types": [lib.get(t, t) for t in types], "niveaux": rows, "resume": resume}


def _liste_verifiee(dossier, lire, nb):
    """Établissements dont la liste des structures a été vérifiée sur leurs propres sources (page méthode)."""
    fe, fn = dossier / "etablissements_verifies.csv", dossier / "structures_non_retenues.csv"
    if not fe.exists():
        return None
    from . import config
    lib = {t[0]: t[1].split(",")[0] for t in config.LIEUX_TYPES}
    non = {}
    for r in (lire(fn) if fn.exists() else []):
        non[(r["ej"], r["etablissement"])] = non.get((r["ej"], r["etablissement"]), 0) + 1
    rows = []
    for r in lire(fe):
        rows.append({"etablissement": r["etablissement"], "departement": r["departement"],
                     "types": ", ".join(lib.get(t.strip(), t) for t in r["types"].split(",")),
                     "etab": nb(r.get("structures_etablissement", 0)), "publique": nb(r.get("structures_source_publique", 0)),
                     "bases": nb(r.get("structures_bases", 0)),
                     "non_retenues": nb(non.get((r["ej"], r["etablissement"]), 0)), "sources": r["sources"],
                     "date": r["date"], "a_reverifier": r.get("a_reverifier") in ("True", "true", "1")})
    if not rows:
        return None
    n = len(rows)
    resume = (f"{n} établissement{'s' if n > 1 else ''} vérifié{'s' if n > 1 else ''} à ce jour. La vérification de "
              f"tous les établissements qui gèrent des CMP est en cours.")
    return {"etablissements": rows, "resume": resume}


def _parties_imprimees(corps: str) -> str:
    """À l'impression, chaque grande partie d'un rapport national (titre de niveau 3 sous « Santé mentale » ou « Santé »,
    hors « En bref ») commence une nouvelle page, pour qu'aucun titre de partie ne reste en bas de page avec son
    introduction (demande de Lucas du 10 octobre 2026)."""
    famille = [False]

    def marque(m):
        balise, attrs = m.group(1), m.group(2) or ""
        if balise == "h2":
            famille[0] = bool(re.search(r'id="sante(-mentale)?"', attrs))
            return m.group(0)
        if famille[0] and 'id="en-bref' not in attrs:
            return f'<h3 class="partie"{attrs}>'
        return m.group(0)
    return re.sub(r"<(h2|h3)(\s[^>]*)?>", marque, corps)


def tableaux_larges(corps: str) -> str:
    """Césures possibles dans les en-têtes (noms de professions longs) et classe « large » pour les tableaux
    de dix colonnes ou plus, imprimés en plus petit pour tenir dans la largeur de la page."""
    corps = re.sub(r"<th([^>]*)>(.*?)</th>", lambda m: f"<th{m.group(1)}>{CESURES.sub(lambda c: c.group(1) + "&shy;", m.group(2))}</th>",
                   corps, flags=re.S)

    def classe(m):
        entete = re.search(r"<thead>.*?</thead>", m.group(0), re.S)
        n = len(re.findall(r"<th[ >]", entete.group(0))) if entete else 0
        return m.group(0).replace("<table>", '<table class="large">', 1) if n >= 10 else m.group(0)
    return re.sub(r"<table>.*?</table>", classe, corps, flags=re.S)


def _ancre(texte, sep):
    from .util import norm
    return norm(texte).replace(" ", sep)[:60]


# Une seule mise en page pour les pages de texte (harmonisation, 22 octobre 2026). Le titre et le chapeau prennent la
# largeur du cadre, puis viennent le sommaire à gauche, tiré des intertitres, et la colonne de texte, au même endroit que
# dans les rapports et la page méthode. Une page sans au moins deux intertitres n'a ni sommaire ni marge vide, son
# contenu s'aligne sur le titre. Mise en page choisie page par page (demande de Lucas du 22 octobre 2026), la page des
# rapports nationaux, faite de cartes, et la page des publications, courte, gardent la leur.
EN_COLONNE = {"page.html", "donnees_sources.html", "journal.html", "territoires.html"}


def en_colonne(page: str) -> str:
    m = re.search(r'<div class="(?:corps )?etroit">', page)
    if not m:
        return page
    prof, fin = 1, None
    for t in re.finditer(r"<div\b|</div>", page[m.end():]):
        prof += 1 if t.group() == "<div" else -1
        if prof == 0:
            fin = m.end() + t.start()
            break
    if fin is None:
        return page
    dedans = page[m.end():fin]
    h = re.match(r'\s*(<h1\b.*?</h1>)\s*(<p class="chapeau[^"]*">.*?</p>)?', dedans, re.S)
    tete = (h.group(1) + "\n" + (h.group(2) or "")) if h else ""
    reste = dedans[h.end():] if h else dedans
    lignes = []

    def ancre(mm):
        attrs, texte = mm.group(1), mm.group(2)
        brut = re.sub(r"<[^>]+>", "", texte).strip()
        idm = re.search(r'id="([^"]+)"', attrs)
        ident = idm.group(1) if idm else _ancre(brut, "-")
        lignes.append((ident, brut))
        return f'<h2{attrs}>{texte}</h2>' if idm else f'<h2{attrs} id="{ident}">{texte}</h2>'
    reste = re.sub(r"<h2([^>]*)>(.*?)</h2>", ancre, reste, flags=re.S)
    # un tableau trop large pour un téléphone défile dans son cadre au lieu d'élargir la page
    reste = re.sub(r'(?<!<div class="defile">)(<table\b.*?</table>)', r'<div class="defile">\1</div>', reste, flags=re.S)
    if len(lignes) < 2:
        # sans sommaire, pas de colonne vide à gauche, le contenu s'aligne sur le titre (remarque de Lucas du 22 octobre)
        return page[:m.start()] + tete + f'\n<div class="corps etroit">{reste}</div>' + page[fin + len("</div>"):]
    aside = ('<aside class="sommaire" aria-label="Sommaire de la page"><ul>'
             + "".join(f'<li><a href="#{i}">{t}</a></li>' for i, t in lignes) + "</ul></aside>")
    return (page[:m.start()] + tete + f'\n<div class="rapport colonne">{aside}<div class="corps">{reste}</div></div>'
            + page[fin + len("</div>"):])


def rendre(env, nom: str, *args, **kw) -> str:
    html = env.get_template(nom).render(*args, **kw)
    return en_colonne(html) if nom in EN_COLONNE else html


def en_bref(texte: str) -> list[str]:
    """Phrases de la première liste « En bref » d'un rapport Markdown."""
    i = texte.find("### En bref")
    if i < 0:
        return []
    out = []
    for l in texte[i:].split("\n")[2:]:
        if l.startswith("- "):
            out.append(l[2:].strip())
        elif out:
            break
    return out


def _part_liberal_methode(site_data) -> dict | None:
    """Règle de la part de l'exercice libéral (indicateur calculé dans l'atlas), pour la page « Indicateurs »."""
    pl = (site_data.get("meta") or {}).get("part_liberal")
    if not pl:
        return None
    lab = {p["id"]: p["libelle"] for p in site_data.get("professions", [])}
    return {"minimum": pl["minimum"], "professions": [lab.get(p, p) for p in pl["professions"]]}


def _suivi_methode() -> dict:
    """Photographies des comptes gardées, une par extraction du RPPS (pipeline/photographies.py)."""
    f = config.RESULTATS / "historique" / "photographies" / "index.json"
    idx = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    from .lecture import date_longue
    return {"n": len(idx), "premiere": date_longue(idx[0]["date_rpps"]) if idx else None,
            "derniere": date_longue(idx[-1]["date_rpps"]) if idx else None}


# ---------------------------------------------------------------- PDF
def navigateur() -> str | None:
    for nom in ("msedge", "chromium", "chromium-browser", "google-chrome", "chrome"):
        p = shutil.which(nom)
        if p:
            return p
    for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe"]:
        if Path(p).exists():
            return p
    # Depuis octobre 2026, Edge s'installe dans EdgeCore\<version>\msedge.exe
    for base in (r"C:\Program Files (x86)\Microsoft\EdgeCore", r"C:\Program Files\Microsoft\EdgeCore"):
        exes = sorted(Path(base).glob("*/msedge.exe"),
                      key=lambda x: [int(n) if n.isdigit() else 0 for n in x.parent.name.split(".")])
        if exes:
            return str(exes[-1])
    return None


def proteger_pdf(pdf: Path, titre: str, sujet: str, doi: str | None = None) -> None:
    """Métadonnées (titre, auteur, sujet, DOI) et verrouillage de la modification. L'impression et la copie de texte
    restent permises, pour citer et pour les lecteurs d'écran. Aucun mot de passe n'est demandé à l'ouverture. Ce
    verrou décourage la modification sans l'empêcher absolument, la version de référence reste celle déposée avec son
    DOI."""
    import secrets

    from pypdf import PdfReader, PdfWriter
    from pypdf.constants import UserAccessPermissions as P
    w = PdfWriter(clone_from=PdfReader(pdf))
    w.add_metadata({"/Title": titre, "/Author": config.AUTEUR, "/Subject": sujet, "/Creator": config.NOM_PROJET,
                    **({"/Keywords": f"doi:{doi}"} if doi else {})})
    w.encrypt(user_password="", owner_password=secrets.token_hex(16), algorithm="AES-256",
              permissions_flag=P.PRINT | P.PRINT_TO_REPRESENTATION | P.EXTRACT | P.EXTRACT_TEXT_AND_GRAPHICS)
    tmp = pdf.with_suffix(".tmp.pdf")
    with open(tmp, "wb") as f:
        w.write(f)
    tmp.replace(pdf)


def lisez_moi_donnees(dossier: Path, archivee: bool | None = None) -> str:
    """Notice de l'archive des données (dépôt Zenodo et page Données), sources, licences et citation. La licence ODbL
    demande que la notice accompagne les données qui en dérivent."""
    import json
    from .export import LICENCE_ODBL
    version = dossier.name
    sources, vus = [], set()
    jf = dossier / "journal.json"
    if jf.exists():
        for e in json.loads(jf.read_text(encoding="utf-8")).get("sources", []):
            if e.get("producteur") and e.get("statut") == "ok" and e["source"] not in vus:
                vus.add(e["source"])
                sources.append(f"- {e['source']}, {e['producteur']}, {e.get('licence', '')}"
                               + (f", données du {e['date_donnees']}" if e.get("date_donnees") else "")
                               + (f", {e['page']}" if e.get("page") else ""))
    lignes = [f"# {config.TITRES_DEPOTS['donnees']}", "",
              f"Version du {date_longue(version)}. Auteur, {config.AUTEUR} (ORCID {config.ORCID}). "
              f"Contact, {config.CONTACT}.", "",
              "Effectifs de professionnels de santé et indicateurs de contexte agrégés par territoire (France, régions, "
              "départements, intercommunalités, communes), avec les analyses publiées dans les rapports. Aucun nom ni "
              "identifiant de professionnel. Le fichier dictionnaire_des_colonnes.md décrit chaque fichier et chaque "
              "colonne. Les fichiers CSV sont séparés par des points-virgules, avec la virgule comme séparateur décimal.",
              "", "## Licences", "", LICENCE_ODBL, "",
              "Les fichiers dont le nom finit par _odbl contiennent des données de l'Assurance Maladie (Cnam, "
              "data.ameli.fr) et sont diffusés sous la licence Open Database License (ODbL) 1.0, "
              "https://opendatacommons.org/licenses/odbl/1-0/. Toute base qui en dérive doit être partagée sous la même "
              "licence. Les autres fichiers sont sous Licence Ouverte 2.0 (Etalab), "
              "https://www.etalab.gouv.fr/licence-ouverte-open-licence/.", "",
              "## Comment citer", "",
              citation_donnees(version, archivee), "",
              "## Sources", ""] + sources + [""]
    return "\n".join(lignes)


def doi_version(cle: str, version: str | None = None) -> str | None:
    """DOI propre à une version archivée sur Zenodo (« donnees », « sante-mentale », « sante »), relevé par
    outils/zenodo.py constater dans donnees/zenodo.json (audit externe du 30 octobre 2026, le DOI général renvoie
    toujours à la dernière version et ne fige pas les chiffres cités). None quand il n'est pas relevé."""
    try:
        e = json.loads((config.DONNEES / "zenodo.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return ((e.get("doi_versions") or {}).get(version or config.VERSION_ZENODO) or {}).get(cle)


def doi_cite(cle: str, version: str | None = None) -> str | None:
    """DOI à citer, celui de la version quand il est relevé, sinon le DOI général du dépôt."""
    general = config.DOI_DONNEES if cle == "donnees" else config.DOI_RAPPORTS.get(cle)
    return doi_version(cle, version) or general


# dépôt public du code (branche main de UbiCura/ubicura, publié depuis le 22 octobre 2026)
DEPOT_CODE = "https://github.com/UbiCura/ubicura"


def sources_publiques(sources: list[dict]) -> list[dict]:
    """Sources montrées sur la page Méthode. Une source facultative non activée (« ignoré ») n'est pas une source du
    site et n'est pas listée ; une source absente ou en erreur est dite non disponible, sans le message du programme."""
    out = []
    for s in sources:
        if s.get("statut") == "ignoré":
            continue
        if s.get("statut") != "ok":
            s = dict(s, detail="Non disponible dans cette version.")
        out.append(s)
    return out


def taille_fichier(octets: int) -> str:
    """Taille lisible d'un fichier, en Ko sous un mégaoctet (« 0,0 Mo » relevé par l'audit externe du 30 octobre 2026),
    en Mo au-delà."""
    if octets < 1e6:
        return f"{max(1, round(octets / 1e3))} Ko"
    return f"{octets / 1e6:.1f} Mo".replace(".", ",")


_IDENTIQUES: dict[str, bool] = {}


def identique_archive(iso: str) -> bool:
    """Vrai quand les résultats de la version iso sont ceux déposés sur Zenodo. La version en ligne peut être refaite
    le jour même de l'archive (seconde mise en ligne du 30 octobre 2026 à 12 h 47, archive préparée à 11 h 43) : les CSV
    sont comparés à ceux de l'archive par leur empreinte CRC32, gardée dans le zip (0,3 seconde). Sans archive sur
    cette machine, la date seule fait foi."""
    if iso != config.VERSION_ZENODO:
        return False
    if iso not in _IDENTIQUES:
        import zipfile
        import zlib
        z, d = config.DONNEES / "zenodo" / iso / f"donnees_{iso}.zip", config.RESULTATS / iso
        if not z.exists() or not d.is_dir():
            _IDENTIQUES[iso] = True
        else:
            with zipfile.ZipFile(z) as zz:
                crc = {i.filename: i.CRC for i in zz.infolist() if i.filename.endswith(".csv")}
            _IDENTIQUES[iso] = ({f.name for f in d.glob("*.csv")} == set(crc)
                                and all(zlib.crc32((d / n).read_bytes()) == c for n, c in crc.items()))
    return _IDENTIQUES[iso]


def mention_version(iso: str, archivee: bool | None = None) -> dict:
    """État d'une version pour sa citation (rapport Zenodo du 30 octobre 2026, partie 3.1). archivee, la version est
    celle déposée sur Zenodo ; posterieure, version de travail refaite après la dernière archive, datée à la minute
    quand elle a le même jour que l'archive (heure de calcul des résultats) ; texte, « version du … » ou « version de
    travail du …, postérieure à la version archivée du … »."""
    if archivee is None:
        archivee = identique_archive(iso)
    posterieure = not archivee and iso >= config.VERSION_ZENODO
    texte = f"version du {date_longue(iso)}"
    if posterieure:
        heure = ""
        sd = config.RESULTATS / iso / "site_data.json"
        if iso == config.VERSION_ZENODO and sd.exists():
            from datetime import datetime
            h = datetime.fromtimestamp(sd.stat().st_mtime)
            heure = f", {h.hour} h {h.minute:02d}"
        texte = (f"version de travail du {date_longue(iso)}{heure}, postérieure à la version archivée du "
                 f"{date_longue(config.VERSION_ZENODO)}")
    return {"archivee": archivee, "posterieure": posterieure, "texte": texte}


def citation_donnees(version: str, archivee: bool | None = None) -> str:
    """Citation des données d'une version. Archivée, par son DOI propre puis le DOI général (toutes les versions) ;
    sinon par l'adresse du site, avec le DOI de la dernière version archivée et le DOI général."""
    m = mention_version(version, archivee)
    doi = doi_cite("donnees", version if m["archivee"] else config.VERSION_ZENODO)
    tout = (f" Toutes les versions, https://doi.org/{config.DOI_DONNEES}."
            if config.DOI_DONNEES and doi and doi != config.DOI_DONNEES else "")
    debut = f"{config.CITATION_AUTEUR} ({version[:4]}). {config.TITRES_DEPOTS['donnees']}"
    if m["archivee"] or not config.ADRESSE_SITE:
        return f"{debut}. Version du {date_longue(version)}. Zenodo." + (f" https://doi.org/{doi}." if doi else "") + tout
    if m["posterieure"]:
        return (f"{debut}. {m['texte'][0].upper()}{m['texte'][1:]}" + (f" (https://doi.org/{doi})" if doi else "")
                + f", {config.ADRESSE_SITE}." + tout)
    return (f"{debut}. Version du {date_longue(version)}, {config.ADRESSE_SITE}."
            + (f" Dernière version archivée, Zenodo, https://doi.org/{doi}." if doi else "") + tout)


def a_propos_variables(version: str) -> dict:
    """Valeurs reprises dans contenus/a_propos.md (citations, DOI, contact), toutes tirées de config."""
    return {"version": date_longue(version), "annee": version[:4], "nom_projet": config.NOM_PROJET,
            "version_zenodo": date_longue(config.VERSION_ZENODO), "annee_zenodo": config.VERSION_ZENODO[:4],
            "sous_titre": config.SOUS_TITRE[0].lower() + config.SOUS_TITRE[1:], "orcid": config.ORCID,
            "contact": config.CONTACT, "doi_donnees": doi_cite("donnees") or "",
            "doi_sm": doi_cite("sante-mentale") or "", "doi_sante": doi_cite("sante") or "",
            "doi_general": config.DOI_DONNEES or "",
            "titre_donnees": config.TITRES_DEPOTS["donnees"], "titre_sm": config.TITRES_DEPOTS["sante-mentale"],
            "titre_sante": config.TITRES_DEPOTS["sante"]}


def citation_territoire(titre: str, date: str, page: str, iso: str | None = None) -> dict:
    """Citation d'un rapport par territoire. Ces rapports ne sont pas archivés sur Zenodo, la citation donne l'adresse
    datée de la page (territoires/AAAA-MM-JJ/, comme les rapports nationaux, audit externe du 30 octobre 2026) et le DOI
    des données."""
    chemin = f"territoires/{iso}/{page}" if iso else f"territoires/{page}"
    adresse = f"{config.ADRESSE_SITE.rstrip('/')}/{chemin}" if config.ADRESSE_SITE else chemin
    titre = re.sub(r",\s*\d{1,2}(er)?\s+\S+\s+\d{4}\s*$", "", titre)   # la date du titre est donnée par la version
    m = mention_version(iso) if iso else {"texte": f"version du {date}"}
    texte = f"{config.CITATION_AUTEUR} ({date[-4:]}). {titre}. {m['texte'][0].upper()}{m['texte'][1:]}. {config.NOM_PROJET}, {adresse}"
    return {"texte": texte, "doi_rapport": None, "doi_donnees": doi_cite("donnees")}


def citation(cle: str, titre: str, date: str, iso: str | None = None, archivee: bool | None = None) -> dict:
    """Citation d'un rapport, avec les DOI quand ils existent. Une version qui n'est pas archivée sur Zenodo est citée par
    son adresse sur le site, avec le DOI général de la dernière version archivée. archivee=True force la citation d'une
    version archivée, pour les fichiers déposés sur Zenodo (outils/zenodo.py)."""
    if iso:
        m = mention_version(iso, archivee)
    else:
        m = {"archivee": True if archivee is None else archivee, "posterieure": False, "texte": ""}
    archivee = m["archivee"]
    # DOI propre à la version citée quand elle est archivée, sinon à la dernière version archivée, puis le DOI général
    doi_r = doi_cite(cle, iso if archivee and iso else config.VERSION_ZENODO) if config.DOI_RAPPORTS.get(cle) else None
    doi_d = doi_cite("donnees", iso if archivee and iso else config.VERSION_ZENODO)
    general = config.DOI_RAPPORTS.get(cle)
    tout = f" Toutes les versions, https://doi.org/{general}." if general and doi_r and doi_r != general else ""
    if doi_r and not archivee and config.ADRESSE_SITE and m["posterieure"]:
        texte = (f"{config.CITATION_AUTEUR} ({date[-4:]}). {config.TITRES_DEPOTS.get(cle, titre)}. "
                 f"{m['texte'][0].upper()}{m['texte'][1:]} (https://doi.org/{doi_r}), "
                 f"{config.ADRESSE_SITE.rstrip('/')}/rapports/{iso}/{cle}.html.{tout}")
    elif doi_r and not archivee and config.ADRESSE_SITE:
        texte = (f"{config.CITATION_AUTEUR} ({date[-4:]}). {config.TITRES_DEPOTS.get(cle, titre)}. Version du {date}, "
                 f"{config.ADRESSE_SITE.rstrip('/')}/rapports/{iso}/{cle}.html. Dernière version archivée, Zenodo, "
                 f"https://doi.org/{doi_r}.{tout}")
    # citation formelle sur le titre du dépôt Zenodo, sans le nom du site
    elif doi_r:
        texte = (f"{config.CITATION_AUTEUR} ({date[-4:]}). {config.TITRES_DEPOTS.get(cle, titre)}. Version du {date}. "
                 f"Zenodo. https://doi.org/{doi_r}.{tout}")
    else:
        texte = (f"{config.CITATION_AUTEUR} ({date[-4:]}). {titre}, version du {date}. {config.NOM_PROJET}."
                 + (f" {config.ADRESSE_SITE}" if config.ADRESSE_SITE else ""))
    return {"texte": texte, "doi_rapport": doi_r, "doi_donnees": doi_d}


def imprimer_pdf(html: Path, pdf: Path, exe: str) -> bool:
    """Impression sans fenêtre. Un profil temporaire est indispensable, sinon un navigateur déjà ouvert sur la session
    reçoit la commande et ne produit aucun fichier (constaté le 8 octobre 2026, aucun PDF depuis le 4 octobre)."""
    import tempfile
    profil = tempfile.mkdtemp(prefix="profil_pdf_")
    cmd = [exe, "--headless=new", "--disable-gpu", f"--user-data-dir={profil}", "--no-first-run",
           "--no-pdf-header-footer", "--print-to-pdf-no-header", "--virtual-time-budget=8000",
           f"--print-to-pdf={pdf}", html.resolve().as_uri()]
    try:
        subprocess.run(cmd, capture_output=True, timeout=180, check=False)
    except Exception as e:  # noqa: BLE001
        log.warning("impression PDF impossible (%s) : %s", html.name, e)
        return False
    finally:
        shutil.rmtree(profil, ignore_errors=True)
    return pdf.exists() and pdf.stat().st_size > 10_000


# ---------------------------------------------------------------- données sources
def donnees_sources(dernier: Path, site_data: dict) -> list[dict]:
    """Une fiche par jeu de données suivi, producteur, licence, page du jeu, fichiers lus avec leur adresse, version,
    versions constatées, usage et indicateurs qui en dérivent (demande de Lucas du 5 octobre 2026)."""
    journal = json.loads((dernier / "journal.json").read_text(encoding="utf-8"))
    hist = mises_a_jour.lire()
    etat = hist[-1]["etat"] if hist else mises_a_jour.etat_sources()
    dl = lambda d: date_longue(d) if d else ""  # noqa: E731
    fiches = []
    for _motif, nom, producteur, motif_src, usage in config.SOURCES_SUIVIES:
        ent = [s for s in journal["sources"] if re.search(motif_src, s["source"])]
        e = etat.get(nom, {})
        fichiers = []
        for chemin in sorted(e.get("fichiers") or {}):
            meta = lire_meta(config.BRUT / chemin)
            url = str(meta.get("url") or "")
            fichiers.append({"nom": chemin.rsplit("/", 1)[-1], "url": url if url.startswith("http") else "",
                             "version": dl(date_version(meta)), "titre": meta.get("titre", "")})
        pages = list(dict.fromkeys(s["page"] for s in ent if s.get("page")))
        versions = [dl(x["date"]) for x in hist if any(s["jeu"] == nom and s["nature"] != "retiré" for s in x["sources"])]
        inds = [c for c in site_data.get("contexte", []) if mises_a_jour.jeu_de_source(c.get("source") or "") == nom]
        fiches.append({"ancre": mises_a_jour.ancre(nom), "nom": nom, "producteur": ent[0]["producteur"] if ent else producteur,
                       "licences": list(dict.fromkeys(s["licence"] for s in ent if s.get("licence"))), "pages": pages,
                       "usage": usage, "version": dl(e.get("maj")), "recupere": dl(e.get("recupere")),
                       "suivi_depuis": dl(next((x["date"] for x in hist if nom in x["etat"]), "")),
                       "versions": versions, "fichiers": fichiers, "indicateurs": inds,
                       "lu": [{"source": s["source"], "detail": s.get("detail", ""), "statut": s["statut"]} for s in ent]})
    return fiches


# ---------------------------------------------------------------- journal des mises à jour
def journal_page() -> dict:
    """Entrées du journal mises en forme pour la page, de la plus récente à la plus ancienne."""
    entrees = mises_a_jour.lire()
    dl = lambda d: date_longue(d) if d else ""
    etat = []
    if entrees:
        for jeu, j in sorted(entrees[-1]["etat"].items()):
            vu = [e["date"] for e in entrees if any(s["jeu"] == jeu and s["nature"] != "retiré" for s in e["sources"])]
            premiere = next((e["date"] for e in entrees if jeu in e["etat"]), "")
            etat.append({"jeu": jeu, "producteur": j["producteur"], "maj": dl(j["maj"]), "recupere": dl(j["recupere"]),
                         "change": dl(vu[-1]) if vu else f"aucun depuis le {dl(premiere)}"})
    # résumé de l'essentiel par jour (contenus/journal_resume.csv), à la place des lignes « Journal: » des commits,
    # trop détaillées pour le lecteur (point 11 de la version 2, demande de Lucas du 11 octobre 2026). Le détail reste
    # dans l'historique du dépôt.
    resume = {}
    f_resume = config.RACINE / "contenus" / "journal_resume.csv"
    if f_resume.exists():
        with open(f_resume, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter=";"):
                resume.setdefault(r["date"], []).append(r["texte"])
    sortie = []
    for e in reversed(entrees):
        sources = [dict(s, maj=dl(s.get("maj")), maj_avant=dl(s.get("maj_avant"))) for s in e["sources"]]
        variations = [dict(v, avant_txt=nombre(v["avant"]), apres_txt=nombre(v["apres"]),
                           ecart_txt=("+" if v["apres"] > v["avant"] else "−") + nombre(abs(v["apres"] - v["avant"])))
                      for v in e.get("variations", [])]
        site_ = resume.get(e["date"], e.get("site") or [])
        # un jour sans changement de données, d'effectifs ni du site n'apparaît pas (sauf la première entrée)
        if not (e.get("premiere") or sources or variations or site_):
            continue
        sortie.append(dict(e, date_longue=dl(e["date"]), sources=sources, variations=variations, site=site_,
                           n_jeux=len(e["etat"])))
    # regroupement par mois, le plus récent ouvert, les autres repliés
    from .lecture import MOIS
    mois = []
    for e in sortie:
        a, m = e["date"][:4], int(e["date"][5:7])
        lib = f"{MOIS[m - 1]} {a}"
        if not mois or mois[-1]["mois"] != lib:
            mois.append({"mois": lib, "entrees": []})
        mois[-1]["entrees"].append(e)
    return {"entrees": sortie, "mois": mois, "etat": etat}


# ---------------------------------------------------------------- briques partagées avec outils/zenodo.py
def liens(texte: str):
    """Texte échappé dont les adresses web (DOI, pages du site) deviennent des liens cliquables. Le point final d'une
    phrase n'entre pas dans le lien."""
    from markupsafe import Markup, escape
    return Markup(re.sub(r"(https?://[^\s<]+?)(?=[.,;)]?(?:\s|$))", r'<a href="\1">\1</a>', str(escape(texte))))


def _environnement() -> Environment:
    env = Environment(loader=FileSystemLoader(GABARITS), autoescape=select_autoescape(["html"]))
    env.globals.update(nom_projet=config.NOM_PROJET, sous_titre=config.SOUS_TITRE)
    env.filters["liens"] = liens
    return env


def _commun(dernier: Path, site_data: dict) -> dict:
    return {"date_longue": date_longue(dernier.name), "licences": site_data["meta"].get("licences", ""),
            "description": "Offre de soins et de santé mentale en France, par territoire, à partir des données publiques.",
            # citation de la page, reprise par « Citer et exporter » des tableaux et figures des pages sans citation propre
            "citation_auteur": config.CITATION_AUTEUR, "annee_version": dernier.name[:4],
            "adresse_site": config.ADRESSE_SITE.rstrip("/"),
            # empreinte de la feuille de style, pour que les navigateurs chargent la nouvelle version après une mise à jour
            "version_css": hashlib.sha1((GABARITS / "style.css").read_bytes()).hexdigest()[:10],
            "compteur": _compteur()}


def _compteur() -> str:
    """Script de mesure d'audience sans cookie (config.GOATCOUNTER), vide tant qu'aucun compte n'est indiqué. Le
    navigateur qui demande à ne pas être suivi n'est pas compté (option no_onload de GoatCounter)."""
    if not config.GOATCOUNTER:
        return ""
    return ('<script>window.goatcounter={no_onload:navigator.doNotTrack==="1"||window.doNotTrack==="1"}</script>'
            f'<script data-goatcounter="https://{config.GOATCOUNTER}.goatcounter.com/count" async '
            f'src="{config.GOATCOUNTER_SCRIPT}" crossorigin="anonymous" integrity="{config.GOATCOUNTER_INTEGRITE}"></script>')


def imprimer_rapport(env: Environment, ctx: dict, d: Path, cle: str, cible_pdf: Path, exe: str) -> bool:
    """Imprime le rapport national cle de la version d en PDF (volets ouverts), puis pose métadonnées et verrou. La page
    d'impression est écrite à côté des pages du site, pour que la feuille de style et les polices soient trouvées."""
    fichier, titre = RAPPORTS[cle]
    t, corps_imp, _ = md_html((d / fichier).read_text(encoding="utf-8"), d / "graphiques", imprimer=True)
    dossier = SITE / "rapports" / d.name
    dossier.mkdir(parents=True, exist_ok=True)
    tmp = dossier / f"{cle}.{cible_pdf.stem}.impression.html"
    tmp.write_text(env.get_template("rapport.html").render(ctx, titre_rapport=t, corps=corps_imp, sommaire="", pdf=None,
                                                           impression=True), encoding="utf-8")
    ok = imprimer_pdf(tmp, cible_pdf, exe)
    tmp.unlink(missing_ok=True)
    if ok:
        proteger_pdf(cible_pdf, f"{titre}, {date_longue(d.name)}",
                     config.TITRES_DEPOTS.get(cle, f"{config.NOM_PROJET}, rapport national"), config.DOI_RAPPORTS.get(cle))
    return ok


def archive_donnees(dossier: Path, cible: Path, archivee: bool | None = None) -> Path:
    """Archive zip de tous les fichiers CSV d'une version, avec le dictionnaire des colonnes et la notice LISEZ-MOI.md."""
    import zipfile
    with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(dossier.glob("*.csv")):
            z.write(f, f.name)
        z.write(dossier / "dictionnaire_des_colonnes.md", "dictionnaire_des_colonnes.md")
        z.writestr("LISEZ-MOI.md", lisez_moi_donnees(dossier, archivee))
    return cible


def html_autonome(iso: str, cle: str, cible: Path, archivee: bool = True) -> Path:
    """Rapport national en un seul fichier HTML qui s'ouvre sans connexion, feuille de style, polices et figures
    intégrées, pour le dépôt sur Zenodo. Les liens de navigation renvoient vers le site. Les données des figures sont
    dans l'archive des données de la même version, citée en tête du rapport par son DOI."""
    import base64
    d = config.RESULTATS / iso
    fichier, titre = RAPPORTS[cle]
    env = _environnement()
    commun = _commun(d, json.loads((d / "site_data.json").read_text(encoding="utf-8")))
    racine = config.ADRESSE_SITE.rstrip("/") + "/" if config.ADRESSE_SITE else ""
    autre = "sante" if cle == "sante-mentale" else "sante-mentale"
    ctx = dict(commun, date_longue=date_longue(iso), racine=racine, page="rapports",
               citation=citation(cle, titre, date_longue(iso), iso, archivee=archivee),
               titre=f"{titre}, {date_longue(iso)}", autre_lien=f"{racine}rapports/{iso}/{autre}.html",
               autre_titre="Lire le rapport santé" if cle == "sante-mentale" else "Lire le rapport santé mentale")
    t, corps, sommaire = md_html((d / fichier).read_text(encoding="utf-8"), d / "graphiques")
    html = env.get_template("rapport.html").render(ctx, titre_rapport=t, corps=corps, sommaire=sommaire, pdf=None)
    polices = (GABARITS / "polices" / "polices.css").read_text(encoding="utf-8")
    polices = re.sub(r"url\(([\w.-]+\.woff2)\)", lambda m: "url(data:font/woff2;base64," + base64.b64encode(
        (GABARITS / "polices" / m.group(1)).read_bytes()).decode("ascii") + ")", polices)
    html = re.sub(r'<link rel="stylesheet" href="[^"]*polices/polices\.css">', lambda m: f"<style>{polices}</style>", html)
    html = re.sub(r'<link rel="stylesheet" href="[^"]*style\.css[^"]*">',
                  lambda m: "<style>" + (GABARITS / "style.css").read_text(encoding="utf-8") + "</style>", html)
    if "<link rel=\"stylesheet\"" in html:
        raise RuntimeError("feuille de style non intégrée dans le rapport HTML autonome")
    cible.write_text(html, encoding="utf-8")
    return cible


def fichiers_zenodo(iso: str, cible: Path) -> dict[str, list[Path]]:
    """Les fichiers d'une version à déposer sur Zenodo, l'archive des données, et chaque rapport national en PDF et en
    HTML autonome. Ils portent la citation d'une version archivée (titre du dépôt, Zenodo, DOI général), puisqu'ils seront la
    version archivée. Ceux du site gardent la citation par l'adresse du site tant que Zenodo n'a pas publié la version."""
    d = config.RESULTATS / iso
    if not (d / "rapport_sante_mentale.md").exists():
        raise FileNotFoundError(f"aucun résultat complet pour la version {iso} dans {config.RESULTATS}")
    exe = navigateur()
    if not exe:
        raise RuntimeError("aucun navigateur Edge, Chrome ou Chromium trouvé pour imprimer les rapports en PDF")
    cible.mkdir(parents=True, exist_ok=True)
    env = _environnement()
    commun = _commun(d, json.loads((d / "site_data.json").read_text(encoding="utf-8")))
    sortie = {"donnees": [archive_donnees(d, cible / f"donnees_{iso}.zip", archivee=True)]}
    for cle, (_fichier, titre) in RAPPORTS.items():
        autre = "sante" if cle == "sante-mentale" else "sante-mentale"
        ctx = dict(commun, date_longue=date_longue(iso), racine="../../", page="rapports",
                   citation=citation(cle, titre, date_longue(iso), iso, archivee=True),
                   titre=f"{titre}, {date_longue(iso)}", autre_lien=f"{autre}.html",
                   autre_titre="Lire le rapport santé" if cle == "sante-mentale" else "Lire le rapport santé mentale")
        pdf = cible / f"{cle}.pdf"
        pdf.unlink(missing_ok=True)
        if not imprimer_rapport(env, ctx, d, cle, pdf, exe):
            raise RuntimeError(f"le rapport {cle} de la version {iso} n'a pas pu être imprimé en PDF")
        sortie[cle] = [pdf, html_autonome(iso, cle, cible / f"{cle}.html")]
    return sortie


# ---------------------------------------------------------------- construction
def construire(pdf=True) -> Path:
    dates = sorted(p for p in config.RESULTATS.glob("20*") if (p / "rapport_sante_mentale.md").exists())
    # seules les versions depuis la première mise en ligne sont publiées (donnees/publication.json, écrit par
    # outils/publier.ps1), les versions de travail antérieures restent sur le PC
    pub = config.RACINE / "donnees" / "publication.json"
    etat_pub = json.loads(pub.read_text(encoding="utf-8-sig")) if pub.exists() else {}
    premiere = etat_pub.get("premiere_version")
    # versions réellement mises en ligne (ajoutées par publier.ps1), plus la dernière, les versions de travail
    # intermédiaires ne partent pas
    vp = etat_pub.get("versions_publiees") or []
    publiees = {vp} if isinstance(vp, str) else set(vp)
    if premiere:
        dates = [d for d in dates if d.name >= premiere] or dates[-1:]
    if publiees and dates:
        dates = [d for d in dates if d.name in publiees or d == dates[-1]]
    if premiere or publiees:
        gardees = {d.name for d in dates}
        for vieux in (SITE / "rapports").glob("20*"):
            if vieux.name not in gardees:
                shutil.rmtree(vieux, ignore_errors=True)
    if not dates:
        raise FileNotFoundError("aucun résultat avec rapports séparés, lancez d'abord python run.py")
    dernier = dates[-1]
    SITE.mkdir(exist_ok=True)
    shutil.copy(GABARITS / "style.css", SITE / "style.css")
    # polices hébergées sur le site (licence OFL, texte joint), aucune requête vers un service tiers
    shutil.copytree(GABARITS / "polices", SITE / "polices", dirs_exist_ok=True)
    # césure française du texte justifié (module hyphen, licence ISC, texte joint), servie par le site lui-même
    shutil.copytree(GABARITS / "cesure", SITE / "cesure", dirs_exist_ok=True)
    env = _environnement()
    site_data = json.loads((dernier / "site_data.json").read_text(encoding="utf-8"))
    # limites calculées à l'exécution (spécialités surtout salariées), reprises pour la page méthode
    limites.completer(site_data.get("limites"))
    commun = _commun(dernier, site_data)
    exe = navigateur() if pdf else None
    if pdf and not exe:
        JOURNAL.note("Site, PDF des rapports", "ignoré", "aucun navigateur Edge, Chrome ou Chromium trouvé")
    pages = []

    # rapports, une version par date
    versions = []
    rapports_cites = {}   # balises de citation de chaque version (pipeline/referencement.py)
    for d in reversed(dates):
        dossier = SITE / "rapports" / d.name
        dossier.mkdir(parents=True, exist_ok=True)
        v = {"date_longue": date_longue(d.name), "dossier": f"rapports/{d.name}"}
        for cle, (fichier, titre) in RAPPORTS.items():
            texte = (d / fichier).read_text(encoding="utf-8")
            autre = "sante" if cle == "sante-mentale" else "sante-mentale"
            ctx = dict(commun, date_longue=date_longue(d.name), racine="../../", page="rapports",
                       citation=citation(cle, titre, date_longue(d.name), d.name),
                       titre=f"{titre}, {date_longue(d.name)}", autre_lien=f"{autre}.html",
                       autre_titre="Lire le rapport santé" if cle == "sante-mentale" else "Lire le rapport santé mentale")
            t, corps, sommaire = md_html(texte, d / "graphiques", donnees=(
                {"prefixe": f"../../donnees/{d.name}/", "dossier": d} if d == dernier else None))
            cible_pdf = dossier / f"{cle}.pdf"
            refaire = d == dernier or not cible_pdf.exists()
            # une version archivée sur Zenodo garde sur le site le PDF exact qui y est déposé (outils/zenodo.py)
            depose = config.DONNEES / "zenodo" / d.name / f"{cle}.pdf"
            if d.name == config.VERSION_ZENODO and depose.exists() and identique_archive(d.name):
                shutil.copy2(depose, cible_pdf)
                refaire = False
            html = env.get_template("rapport.html").render(ctx, titre_rapport=t, corps=corps, sommaire=sommaire,
                                                           pdf=f"{cle}.pdf" if (cible_pdf.exists() or (exe and refaire)) else None)
            (dossier / f"{cle}.html").write_text(html, encoding="utf-8")
            # le langage n'est contrôlé que sur la dernière version, les versions déjà publiées restent telles quelles
            # (archives citables, décision du 28 octobre 2026)
            if d == dernier:
                pages.append(dossier / f"{cle}.html")
            if exe and refaire:
                if not imprimer_rapport(env, ctx, d, cle, cible_pdf, exe):
                    log.warning("PDF non produit pour %s %s", d.name, cle)
            v["pdf_sm" if cle == "sante-mentale" else "pdf_sante"] = cible_pdf.exists()
            rapports_cites[f"rapports/{d.name}/{cle}.html"] = {
                "cle": cle, "iso": d.name, "titre": config.TITRES_DEPOTS.get(cle, titre), "pdf": cible_pdf.exists()}
        versions.append(v)
    ctx = dict(commun, racine="", page="rapports", titre="Rapports nationaux")
    (SITE / "rapports.html").write_text(rendre(env, "rapports.html",
        ctx, versions=versions,
        citation_donnees=citation_donnees(dernier.name),
        citation_sm=citation("sante-mentale", "Rapport santé mentale", date_longue(dernier.name), dernier.name)["texte"],
        citation_sante=citation("sante", "Rapport santé", date_longue(dernier.name), dernier.name)["texte"]), encoding="utf-8")
    pages.append(SITE / "rapports.html")
    pages += _territoires(env, commun, dernier)

    # données à télécharger et dictionnaire des colonnes
    # seule la dernière version des données est publiée (les précédentes iront sur Zenodo). Les fichiers de plus
    # de 2 Mo sont compressés en zip, et une archive réunit tous les fichiers de la version.
    if (SITE / "donnees").exists():
        shutil.rmtree(SITE / "donnees")
    ddir = SITE / "donnees" / dernier.name
    ddir.mkdir(parents=True, exist_ok=True)
    import zipfile
    tout = archive_donnees(dernier, ddir / f"donnees_{dernier.name}.zip")
    fichiers = []
    for f in sorted(dernier.glob("*.csv")):
        cible = ddir / f.name
        if f.stat().st_size > 2_000_000:
            cible = ddir / (f.name + ".zip")
            with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
                z.write(f, f.name)
        else:
            shutil.copy(f, cible)
        nom = re.sub(r"_odbl\.csv$", ".csv", f.name)
        desc = next((g(re.match(m, nom)) for m, g in dictionnaire.FICHIERS if re.match(m, nom)), "")
        if f.name == "libelles.csv":
            desc = "Table de correspondance entre libellés officiels et libellés affichés."
        if f.name.endswith("_odbl.csv"):
            desc += " Licence ODbL."
        fichiers.append({"nom": f.name + (" (archive zip)" if cible.suffix == ".zip" else ""),
                         "lien": f"donnees/{dernier.name}/{cible.name}", "description": desc,
                         "taille": taille_fichier(cible.stat().st_size)})
    _, corps, _ = md_html((dernier / "dictionnaire_des_colonnes.md").read_text(encoding="utf-8"), None)
    ctx = dict(commun, racine="../../", page="methode", titre="Dictionnaire des colonnes")
    (ddir / "dictionnaire.html").write_text(rendre(env, "page.html",
        ctx, corps="<h1>Dictionnaire des colonnes</h1>" + corps), encoding="utf-8")

    # méthode
    journal = json.loads((dernier / "journal.json").read_text(encoding="utf-8"))
    with open(dernier / "libelles.csv", encoding="utf-8") as fh:
        table_lib = list(csv.DictReader(fh, delimiter=";"))
    concordance = _concordance(dernier)
    inscrits = _inscrits(dernier)
    lieux_m = _lieux_methode(dernier)
    ctx = dict(commun, racine="", page="methode", titre="Méthode, données et limites", limites=limites.tableau(),
               logiciels=logiciels())
    # la méthode en cinq pages (audit du 22 octobre 2026, lot 3), une vue d'ensemble courte et une page par grand
    # ensemble de consultation, sommaire commun
    contenu = dict(sources=sources_publiques(journal["sources"]), controles=controles_publics(journal["controles"]),
                   indicateurs=site_data["contexte"], depot_code=DEPOT_CODE,
                   libelles=table_lib, fichiers=fichiers, concordance=concordance, inscrits=inscrits, lieux=lieux_m,
                   archive={"lien": f"donnees/{dernier.name}/{tout.name}", "taille": f"{tout.stat().st_size / 1e6:.0f} Mo"},
                   lien_dictionnaire=f"donnees/{dernier.name}/dictionnaire.html",
                   lien_libelles=f"donnees/{dernier.name}/libelles.csv",
                   part_liberal=_part_liberal_methode(site_data), suivi=_suivi_methode())
    lim, logi = ctx.get("limites"), ctx.get("logiciels")
    pages_methode = [
        ("entree", "methode.html", "Vue d'ensemble", [("methode", "Comment les chiffres sont établis")]
         + ([("limites", "Limites connues des données")] if lim else []) + [("sources", "Sources"),
            ("origine", "D'où vient chaque chiffre")] + ([("inscrits", "Inscrits sans activité déclarée")] if inscrits else [])
         + [("suivi", "Suivi dans le temps")]
         + ([("logiciels", "Logiciels et reproductibilité")] if logi else [])
         + [("libelles", "Noms des établissements"), ("licences", "Licences et conditions de réutilisation")]),
        ("structures", "methode-structures.html", "Structures de soins", [("lieux", "Structures de soins, FINESS et ROR réunis")]),
        ("indicateurs", "methode-indicateurs.html", "Indicateurs du profil des territoires",
         [("indicateurs", "Indicateurs du profil des territoires")]),
        ("controles", "methode-controles.html", "Contrôles et concordance",
         ([("concordance", "Concordance des effectifs avec les chiffres officiels")] if concordance else [])
         + [("controles", "Contrôles")]),
        ("fichiers", "methode-fichiers.html", "Fichiers à télécharger", [("telecharger", "Données à télécharger")]),
    ]
    chapeaux = {"entree": "Comment les chiffres sont produits, d'où ils viennent, ce qu'ils ne disent pas, comment les "
                          "vérifier et les réutiliser. Les structures de soins, les indicateurs, les contrôles et les "
                          "fichiers ont chacun leur page.",
                "structures": "Comment les structures de soins de FINESS et du Répertoire opérationnel des ressources "
                              "sont réunies, relues, confirmées et confrontées à la statistique des hôpitaux.",
                "indicateurs": "Chaque indicateur du profil des territoires, son unité, ce qu'il mesure, les niveaux où il "
                               "est disponible et sa source.",
                "controles": "Les effectifs confrontés aux chiffres officiels de la DREES, et les contrôles de cohérence "
                             "de la version.",
                "fichiers": "Toutes les données de la version, en fichiers CSV, avec le dictionnaire des colonnes."}
    for cle, fichier, titre_v, _a in pages_methode:
        titre_page = "Méthode, données et limites" if cle == "entree" else titre_v
        (SITE / fichier).write_text(env.get_template("methode.html").render(
            dict(ctx, titre=titre_page), vue=cle, pages_methode=pages_methode, titre_page=titre_page,
            chapeau_page=chapeaux[cle], **contenu), encoding="utf-8")
        pages.append(SITE / fichier)

    # à propos, texte versionné dans contenus/a_propos.md
    src = config.RACINE / "contenus" / "a_propos.md"
    if src.exists():
        texte = src.read_text(encoding="utf-8")
        for cle, val in a_propos_variables(dernier.name).items():
            texte = texte.replace("{" + cle + "}", val)
        _t, corps, _s = md_html(texte, None)
        ctx = dict(commun, racine="", page="apropos", titre="À propos")
        (SITE / "a-propos.html").write_text(rendre(env, "page.html",
            ctx, corps="<h1>À propos</h1>" + corps), encoding="utf-8")
        pages.append(SITE / "a-propos.html")

    # ajouts prévus et propositions de bases (demande de Lucas du 5 octobre 2026), textes dans contenus/
    for fichier, sortie, titre in (("a_venir.md", "a-venir.html", "À venir"),
                                   ("contribuer.md", "contribuer.html", "Proposer une base de données")):
        src = config.RACINE / "contenus" / fichier
        if src.exists():
            texte = src.read_text(encoding="utf-8").replace("{contact}", config.CONTACT).replace("{depot_code}", DEPOT_CODE)
            _t, corps, _s = md_html(texte, None)
            ctx = dict(commun, racine="", page=sortie[:-5], titre=titre)
            (SITE / sortie).write_text(rendre(env, "page.html",
                ctx, corps=f"<h1>{titre}</h1>" + corps), encoding="utf-8")
            pages.append(SITE / sortie)

    # explorer les données (décision de Lucas du 26 octobre 2026), analyses réglées par le lecteur
    from . import explorer
    if explorer.ecrire(dernier, SITE, site_data):
        ctx = dict(commun, racine="", page="explorer", titre="Explorer les données")
        cit = (f"{commun['citation_auteur']} ({commun['annee_version']}). Explorer les données. {config.NOM_PROJET}, "
               f"version du {commun['date_longue']}, {commun['adresse_site'].rstrip('/')}/explorer.html")
        # empreinte du code et des données de la page, pour que les navigateurs prennent la nouvelle version
        # « Croiser deux indicateurs » compris (code du moteur et données), qui restait sinon en cache après une mise à jour
        fichiers = ("explorer.js", "donnees.js", "donnees_outils.js", "croisements.js", "donnees_croisements.js",
                    *explorer.FICHIERS_OUTILS)
        empreinte = hashlib.sha1(b"".join((SITE / "explorer" / f).read_bytes() for f in fichiers
                                          if (SITE / "explorer" / f).exists())).hexdigest()[:10]
        (SITE / "explorer.html").write_text(rendre(env, "explorer.html", ctx, citation=cit, version_explorer=empreinte),
                                            encoding="utf-8")
        pages.append(SITE / "explorer.html")

    # données sources, une fiche par jeu
    ctx = dict(commun, racine="", page="sources", titre="Données sources")
    fiches_sources = donnees_sources(dernier, site_data)
    (SITE / "donnees-sources.html").write_text(rendre(env, "donnees_sources.html",
        ctx, fiches=fiches_sources), encoding="utf-8")
    pages.append(SITE / "donnees-sources.html")

    # journal des mises à jour (jeux de données modifiés, effectifs nationaux, nouveautés du site)
    ctx = dict(commun, racine="", page="journal", titre="Journal des mises à jour")
    (SITE / "journal.html").write_text(rendre(env, "journal.html", ctx, **journal_page()), encoding="utf-8")
    pages.append(SITE / "journal.html")

    ctx = dict(commun, racine="", page="publications", titre="Publications", contact=config.CONTACT)
    (SITE / "publications.html").write_text(rendre(env, "publications.html", ctx), encoding="utf-8")

    # l'atlas est la première page du site (décisions de Lucas du 28 octobre 2026, la page d'accueil précédente n'était
    # « pas très pro », puis une seule page plutôt qu'un accueil et un atlas presque identiques), sous un en-tête
    # purement typographique ; atlas.html renvoie vers index.html pour les liens déjà partagés, gabarits/accueil.html
    # n'est plus utilisé
    sys.path.insert(0, str(config.RACINE / "atlas"))
    import construire_atlas  # noqa: E402
    nav = ("<style>" + _css_nav() + "</style>"
           + env.get_template("nav.html").render(racine="", page="atlas") + _compteur())
    entete = (f'<header class="bandeau-accueil">'
              f'<h1>L’offre de soins en France, territoire par territoire</h1>'
              f'<p class="lede">Où exercent les professionnels de santé et de santé mentale, et ce qui accompagne leur '
              f'présence dans le profil des habitants. Données publiques, chaque chiffre est sourcé et citable.</p>'
              f'<div class="portes"><a href="explorer.html">Explorer les données</a>'
              f'<a href="rapports/{dernier.name}/sante-mentale.html">Rapport santé mentale</a>'
              f'<a href="rapports/{dernier.name}/sante.html">Rapport santé</a>'
              f'<a href="territoires/index.html">Rapports par territoire</a>'
              f'<a href="methode.html">Méthode, données et limites</a>'
              f'<span class="version">Données du {commun["date_longue"]}, '
              f'<a href="https://doi.org/{doi_cite("donnees")}">doi:{doi_cite("donnees")}</a></span></div></header>')
    # données, fond de carte et bibliothèques dans des fichiers à part, chargés au même endroit (page de 15 Mo qu'un
    # réseau d'entreprise n'ouvrait pas, 29 octobre 2026), l'atlas autonome de Zenodo garde tout dans la page
    construire_atlas.construire(dernier / "site_data.json", SITE / "index.html", nav, accueil=entete,
                                titre=f"{config.NOM_PROJET}, l’offre de soins en France, territoire par territoire",
                                externes=True)
    # contours des secteurs de psychiatrie, chargés par le plan de l'atlas à la demande (29 octobre 2026)
    if (dernier / "secteurs_psychiatrie.geojson").exists():
        shutil.copy(dernier / "secteurs_psychiatrie.geojson", SITE / "secteurs_psychiatrie.geojson")
    (SITE / "atlas.html").write_text(
        '<!doctype html>\n<html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>Atlas de l’offre de soins · {config.NOM_PROJET}</title>'
        '<link rel="canonical" href="index.html"><meta http-equiv="refresh" content="0; url=index.html">'
        '<script>location.replace("index.html" + location.search + location.hash)</script>'
        '<style>body{font-family:system-ui,sans-serif;background:#121419;color:#E8E9EE;padding:40px}a{color:#9DC7FE}</style>'
        '</head><body><p>L’atlas de l’offre de soins est désormais la première page du site. '
        '<a href="index.html">Ouvrir l’atlas</a>.</p></body></html>\n', encoding="utf-8")

    # référencement, adresse de référence et aperçu des liens sur chaque page, citation des rapports, description du
    # jeu de données, plan du site (feuille de route de la communication, phase 1, 29 octobre 2026)
    from . import referencement
    referencement.appliquer(SITE, dernier.name, rapports_cites,
                            {"page": "methode-fichiers.html", "archive": f"donnees/{dernier.name}/{tout.name}",
                             "sources": [u for f in fiches_sources for u in f["pages"]]},
                            exe, _apercu_carte(dernier))
    # identifiant Bluesky @ubicura.fr, prouvé par un fichier du site (phase 2, tutoriel 11)
    identifiant_bluesky(SITE, config.BLUESKY_DID)

    # contrôle du langage sur les pages (le texte visible, sans les balises)
    pb = []
    for p in pages:
        texte = re.sub(r"<[^>]+>", " ", re.sub(r"<(svg|script|style)[\s\S]*?</\1>", " ", p.read_text(encoding="utf-8")))
        pb += [f"{p.name} : {x}" for x in libelles.termes_proscrits(texte)]
    for x in pb:
        log.warning("terme à proscrire dans le site : %s", x)
    JOURNAL.controle("Site, termes à proscrire dans les pages", "aucun" if not pb else f"{len(pb)} occurrence(s)")
    # mise en page des PDF de la dernière version, aucun titre seul en bas de page (outils/controle_pdf.py)
    if exe:
        sys.path.insert(0, str(config.RACINE / "outils"))
        import controle_pdf  # noqa: E402
        pb_pdf = [x for f in sorted((SITE / "rapports" / dernier.name).glob("*.pdf")) if f.with_suffix(".html").exists()
                  for x in controle_pdf.controle(f, f.with_suffix(".html"))]
        for x in pb_pdf:
            log.warning("mise en page PDF : %s", x)
        JOURNAL.controle("Rapports PDF, titres seuls en bas de page ou pages presque vides",
                         "aucun" if not pb_pdf else f"{len(pb_pdf)} cas")
    nb_pdf = len(list((SITE / "rapports").glob("*/*.pdf")))
    JOURNAL.note("Site statique", "ok", f"{len(versions)} version(s) des rapports, {nb_pdf} PDF, dossier {SITE}")
    return SITE


def _territoires(env, commun, dernier) -> list[Path]:
    """Rapports par région et par département de la dernière version. Chaque page est écrite deux fois, à l'adresse
    stable territoires/dep-18-sante-mentale.html, qui montre toujours la dernière version, et à l'adresse datée
    territoires/AAAA-MM-JJ/dep-18-sante-mentale.html, que donne la citation (audit externe du 30 octobre 2026). Les
    dossiers datés ne sont gardés que pour la dernière version et la version archivée sur Zenodo (config.VERSION_ZENODO),
    pour que le site garde un poids raisonnable (67 Mo par version). Pas de PDF stocké, le lecteur imprime la page s'il
    veut en garder une copie."""
    src = dernier / "territoires"
    dossier = SITE / "territoires"
    gardes = {dernier.name, config.VERSION_ZENODO}
    if dossier.exists():
        for f in dossier.iterdir():
            if f.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", f.name) and f.name in gardes - {dernier.name}:
                continue
            shutil.rmtree(f) if f.is_dir() else f.unlink()
    if not (src / "index.json").exists():
        return []
    date_dossier = dossier / dernier.name
    date_dossier.mkdir(parents=True)
    index = json.loads((src / "index.json").read_text(encoding="utf-8"))
    reg_avec_rapport = {t["code"] for t in index if t["niveau"] == "reg" and t["fichiers"]}
    pages = []
    for t in index:
        for cle, fichier in t["fichiers"].items():
            texte = (src / fichier).read_text(encoding="utf-8")
            autre = "sante" if cle == "sante-mentale" else "sante-mentale"
            base = f"{t['niveau']}-{t['code']}"
            # le corps ne dépend de l'emplacement de la page que par le chemin des données, posé ensuite
            titre_r, corps, sommaire = md_html(texte, src / "graphiques",
                                               donnees={"prefixe": f"@RACINE@donnees/{dernier.name}/", "dossier": dernier})
            for cible, racine in ((dossier, "../"), (date_dossier, "../../")):
                ctx = dict(commun, date_longue=date_longue(dernier.name), racine=racine, page="territoires",
                           classe_main="territoire", titre=titre_r)
                html = env.get_template("territoire.html").render(
                    ctx, titre_rapport=titre_r, corps=corps.replace("@RACINE@", racine), sommaire=sommaire,
                    autre_lien=f"{base}-{autre}.html" if autre in t["fichiers"] else "index.html",
                    autre_titre="Lire le rapport santé" if cle == "sante-mentale" else "Lire le rapport santé mentale",
                    lien_region=f"reg-{t['reg']}-{cle}.html" if t["niveau"] == "dep" and t["reg"] in reg_avec_rapport
                    else None,
                    lien_national=f"rapports/{dernier.name}/{cle}.html", lien_index=f"{racine}territoires/index.html",
                    citation=citation_territoire(titre_r, date_longue(dernier.name), f"{base}-{cle}.html", dernier.name))
                (cible / f"{base}-{cle}.html").write_text(html, encoding="utf-8")
            pages.append(dossier / f"{base}-{cle}.html")
    lien = lambda t, c: f"{t['niveau']}-{t['code']}-{c}.html" if c in t["fichiers"] else None  # noqa: E731
    regions = []
    for r in sorted({t["reg"] for t in index}):
        nr = next((t for t in index if t["niveau"] == "reg" and t["code"] == r), None)
        deps = [t for t in index if t["niveau"] == "dep" and t["reg"] == r]
        nom = nr["nom"] if nr else (deps[0]["nom"] if deps else r)
        regions.append({"nom": nom,
                        "rapport": {"sm": lien(nr, "sante-mentale"), "sante": lien(nr, "sante")} if nr else None,
                        "deps": [{"nom": d["nom"], "code": d["code"], "sm": lien(d, "sante-mentale"),
                                  "sante": lien(d, "sante")} for d in deps]})
    from .util import norm
    regions.sort(key=lambda r: norm(r["nom"]))
    ctx = dict(commun, racine="../", page="territoires", titre="Rapports par territoire")
    (dossier / "index.html").write_text(rendre(env, "territoires.html",
        ctx, regions=regions,
        exemple_citation=citation_territoire("Offre de soins en santé mentale, Eure", date_longue(dernier.name),
                                             "dep-27-sante-mentale.html", dernier.name)["texte"]),
                                        encoding="utf-8")
    pages.append(dossier / "index.html")
    return pages


def _css_nav() -> str:
    """Styles de la barre de navigation, repris de style.css pour l'atlas (qui a ses propres styles)."""
    css = (GABARITS / "style.css").read_text(encoding="utf-8")
    lignes, simples, mobiles, tel = css.split("\n"), [], [], False
    for l in lignes:
        # au téléphone, les règles du menu sont dans le bloc @media (max-width:760px) de la fin du fichier
        if l.strip() == "@media (max-width:760px){":
            tel = True
        elif l.strip() == "}":
            tel = False
        elif l.startswith("nav.site"):
            (mobiles if tel else simples).append(l)
    return "\n".join(simples) + ("\n@media (max-width:760px){" + "\n".join(mobiles) + "}" if mobiles else "")


DID_VALIDE = re.compile(r"did:(plc:[a-z2-7]{24}|web:[a-z0-9.-]+)")


def identifiant_bluesky(site: Path, did: str) -> bool:
    """Écrit .well-known/atproto-did, le DID du compte Bluesky du projet seul, sans espace ni retour à la ligne, pour
    l'identifiant @ubicura.fr (https://atproto.com/specs/handle, lu le 29 octobre 2026). Sans DID valide, le fichier est
    retiré. GitHub Pages le sert en application/octet-stream et non en text/plain, toléré par la spécification, qui ne
    demande pas de vérifier le type ; la résolution se vérifie après la mise en ligne (tutoriel 11, partie C)."""
    f = site / ".well-known" / "atproto-did"
    did = (did or "").strip()
    if not did:
        f.unlink(missing_ok=True)
        JOURNAL.controle("Site, identifiant Bluesky (.well-known/atproto-did)", "aucun DID indiqué, pas de fichier")
        return False
    if not DID_VALIDE.fullmatch(did):
        f.unlink(missing_ok=True)
        log.warning("DID Bluesky illisible dans config.BLUESKY_DID, fichier .well-known/atproto-did non écrit")
        JOURNAL.controle("Site, identifiant Bluesky (.well-known/atproto-did)", "DID illisible, pas de fichier")
        return False
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(did.encode("ascii"))
    JOURNAL.controle("Site, identifiant Bluesky (.well-known/atproto-did)", f"écrit, {did}")
    return True


def _apercu_carte(dossier: Path) -> str:
    """Carte des psychiatres par département du rapport santé mentale, reprise telle quelle sur l'accueil."""
    f = dossier / "graphiques" / "carte_dep_sm.svg"
    return f.read_text(encoding="utf-8") if f.exists() else ""


def _tuiles(sd) -> list[dict]:
    pop = sd["france"]["pop"]
    n = {p: v[2] for p, v in sd["france"]["n"].items()}
    lab = {p["id"]: p["libelle"] for p in sd["professions"]}
    from .lecture import nombre, pluriel, un_pour
    t = []
    for p in ["psychologue", "psychiatre", "medecin_generaliste"]:
        if n.get(p):
            t.append({"valeur": nombre(n[p]), "libelle": f"{pluriel(lab[p]).lower()} en exercice, {un_pour(n[p] / pop * 1e4)}"})
    z = next((r for r in sd.get("inegalites", []) if r["niv"] == "epci" and r["mode"] == "all" and r["prof"] == "psychiatre"), None)
    if z:
        t.append({"valeur": f"{nombre(z['zero'] * 100, 1)} %",
                  "libelle": "des habitants vivent dans une intercommunalité sans psychiatre"})
    return t


def _fenetres(sd, dossier: Path) -> dict:
    """Données des fenêtres de l'accueil (essai du 23 octobre 2026, d'après reactbits.dev, demande de Lucas).
    « Professions » : pour chaque profession, l'effectif national et, par département, la classe et l'indice de la
    carte du rapport (densité rapportée à la moyenne des départements, comme analyses.moyenne_territoires : somme des
    effectifs sur somme des populations, puis cartes.classe), pour recolorer la carte de l'accueil sans autre calcul.
    « Version et contrôles » : la date de l'extraction RPPS, les comparaisons aux séries de la DREES, le millésime de
    population et la dernière version archivée, tirés des fichiers de la version."""
    from .cartes import CLASSES, classe
    from .lecture import pluriel, un_pour
    lab = {p["id"]: p["libelle"] for p in sd["professions"]}
    fam = {p["id"]: p["famille"] for p in sd["professions"]}
    dep = sd["niveaux"]["dep"]
    pops = [float(u.get("pop") or 0) for u in dep["units"]]
    profs = []
    for p in ["psychiatre", "pedopsychiatre", "psychologue", "medecin_generaliste", "infirmier", "masseur_kinesitherapeute"]:
        n = (dep["n"].get(p) or {}).get("all")
        nfr = (sd["france"]["n"].get(p) or [None, None, None])[2]
        if not n or not nfr:
            continue
        moy = sum(n) / sum(pops) * 1e4
        cl = {u["c"]: [classe(k / po * 1e4 / moy), round(k / po * 1e4 / moy * 100)]
              for u, k, po in zip(dep["units"], n, pops) if po > 0}
        profs.append({"id": p, "nom": pluriel(lab[p]), "famille": fam[p], "effectif": nombre(nfr),
                      "densite": un_pour(nfr / sd["france"]["pop"] * 1e4), "classes": cl})
    controles = []
    f = dossier / "concordance_effectifs.csv"
    if f.exists():
        with open(f, encoding="utf-8-sig") as fh:
            lignes = list(csv.DictReader(fh, delimiter=";"))
        if lignes:
            controles.append(f"Répertoire RPPS, extraction du {date_longue(lignes[0]['date_rpps'])}")
            ecarts = sorted(abs(float(r["ecart_a_l_attendu"].replace(",", "."))) for r in lignes if r.get("ecart_a_l_attendu"))
            if ecarts:
                controles.append(f"{len(lignes)} effectifs comparés aux séries de la DREES, écart médian de "
                                 f"{nombre(ecarts[len(ecarts) // 2] * 100, 1)} %")
    mil = (sd.get("meta") or {}).get("millesimes_insee", {}).get("pop")
    if mil:
        controles.append(f"Population de l'INSEE, millésime {mil}, {nombre(sd['france']['pop'])} habitants")
    controles.append(f"Dernière version archivée le {date_longue(config.VERSION_ZENODO)}, DOI {config.DOI_DONNEES}")
    return {"profs": profs, "couleurs": [c for _b, c, _l in CLASSES], "controles": controles}


def _inscrits(dossier):
    """Inscrits au RPPS et inscrits sans activité déclarée, par profession, pour la page méthode."""
    f = dossier / "inscrits_sans_activite.csv"
    if not f.exists():
        return []
    with open(f, encoding="utf-8-sig") as fh:
        lignes = list(csv.DictReader(fh, delimiter=";"))

    def nb(v):
        return f"{int(float(v)):,}".replace(",", "\u00a0")
    return [{"libelle": r["libelle_rpps"], "inscrits": nb(r["inscrits"]), "avec": nb(r["avec_activite"]),
             "sans": nb(r["sans_activite_declaree"]),
             "part": f"{float(r['part_sans_activite_declaree'].replace(',', '.')):.0%}".replace("%", "\u00a0%")}
            for r in lignes]


# bibliothèques dont dépendent les calculs, avec leur rôle (versions lues à chaque construction du site)
BIBLIOTHEQUES = [("pandas", "lecture des fichiers, tableaux, agrégation par territoire"),
                 ("numpy", "calcul numérique, indices d'inégalité, rééchantillonnage"),
                 ("scipy", "corrélations de rang, tests, intervalles, typologie"),
                 ("pyarrow", "lecture des fichiers Parquet de l'INSEE et des temps de trajet"),
                 ("shapely", "contours des territoires, voisinages, distances"),
                 ("requests", "interrogation des API des producteurs et téléchargements"),
                 ("openpyxl", "lecture des tableaux Excel de la DREES"),
                 ("py7zr", "lecture des archives de la SAE"),
                 ("jinja2", "pages du site"),
                 ("markdown", "conversion des rapports en pages")]


def logiciels() -> dict:
    """Version de Python et des bibliothèques installées, pour la reproductibilité."""
    from importlib.metadata import PackageNotFoundError, version
    libs = []
    for nom, role in BIBLIOTHEQUES:
        try:
            v = version(nom)
        except PackageNotFoundError:
            v = "non installée"
        libs.append({"nom": nom, "version": v, "role": role})
    return {"python": sys.version.split()[0], "bibliotheques": libs, "graine": config.GRAINE}


def _lieux_methode(dossier):
    """Tableaux de la page méthode sur les structures de soins, couverture et provenance de chaque type, confrontation aux
    chiffres publiés."""
    fc, fr, fl = dossier / "lieux_couverture.csv", dossier / "lieux_references.csv", dossier / "lieux_soins.csv"
    if not fc.exists() or not fl.exists():
        return None

    def lire(chemin):
        with open(chemin, encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh, delimiter=";"))

    def nb(v):
        return f"{float(str(v).replace(',', '.')):,.0f}".replace(",", "\u00a0") if v not in ("", None) else ""

    def pc(v, signe=False):
        return (f"{float(str(v).replace(',', '.')):{'+' if signe else ''}.0%}".replace("%", "\u00a0%")
                if v not in ("", None) else "")
    prov = {}
    for r in lire(fl):
        d = prov.setdefault(r["type"], {"FINESS et ROR": 0, "FINESS seul": 0, "ROR seul": 0,
                                        "ROR, type que FINESS ne distingue pas": 0})
        d[r["provenance"]] = d.get(r["provenance"], 0) + 1
    couverture = []
    for r in lire(fc):
        p = prov.get(r["type"], {})
        n = sum(p.values())
        if not n:
            continue
        seul_ror = p.get("ROR, type que FINESS ne distingue pas", 0) == n
        couverture.append({"libelle": r["libelle_type"], "n": nb(n),
                           "deux": "sans objet" if seul_ror else nb(p.get("FINESS et ROR", 0)),
                           "finess": "sans objet" if seul_ror else nb(p.get("FINESS seul", 0)),
                           # le ROR seul compte aussi les unités d'un type que FINESS ne distingue pas, pour que les
                           # trois colonnes refassent le total
                           "ror": "sans objet" if seul_ror else nb(p.get("ROR seul", 0)
                                                                   + p.get("ROR, type que FINESS ne distingue pas", 0)),
                           "sources": "sans objet" if seul_ror else nb(
                               p.get("Absente des deux bases, d'après les sources de l'établissement", 0)
                               + p.get("Annoncé par le nom d'un CMP (CMP-CATTP), au même lieu", 0)),
                           "part": pc(r["part_departements"]),
                           "compare": "oui" if r["complet"] in ("True", "true", "1") else "non, listé seulement"})
    refs = [{"libelle": r.get("objet", ""), "nous": nb(r["lieux"]), "pub": nb(r["reference"]),
             "date": r["date_reference"], "ecart": pc(r["ecart"], True), "source": r["source"], "adresse": r["adresse"]}
            for r in lire(fr)] if fr.exists() else []
    # CMP confrontés à la SAE par région (les CMP d'un établissement sont rangés au département de son siège)
    sae, fs = [], dossier / "concordance_cmp_sae.csv"
    if fs.exists():
        rows = lire(fs)
        for r in [x for x in rows if x["niveau"] == "reg"] + [x for x in rows if x["niveau"] == "fr"]:
            sae.append({"nom": r["nom"], "cmp": nb(r["cmp"]), "adultes": nb(r["adultes"]), "enfants": nb(r["enfants"]),
                        "np": nb(r["non_precise"]), "ur": nb(r.get("unites_ror", "")), "sae": nb(r["sae_cmp"]),
                        "sae_a": nb(r["sae_adultes"]),
                        "sae_e": nb(r["sae_enfants"]), "ecart": pc(r["ecart_relatif"], True)})
        dep = [x for x in rows if x["niveau"] == "dep" and x["ecart_relatif"] not in ("", None)]
        proches = sum(abs(float(x["ecart_relatif"].replace(",", "."))) <= .2 for x in dep)
        sae_resume = f"{proches} départements sur {len(dep)}"
    else:
        sae_resume = ""
    # confrontation hôpital par hôpital, établissements en écart (13 octobre 2026)
    etab, etab_resume, fe = [], "", dossier / "concordance_cmp_etablissements.csv"
    if fe.exists():
        rows = lire(fe)
        compte = {}
        for r in rows:
            compte[r["statut"]] = compte.get(r["statut"], 0) + 1
        etab_resume = ", ".join(f"{v} {k}" for k, v in sorted(compte.items(), key=lambda kv: -kv[1]))
        ecarts = [r for r in rows if r["statut"] in ("moins ici qu'à la SAE", "plus ici qu'à la SAE")]
        ecarts.sort(key=lambda r: -abs(float(str(r["ecart"]).replace(",", ".") or 0)))
        etab = [{"nom": r["nom"], "dep": r["dep_siege"], "sae": f"{nb(r['sae_adultes'])} et {nb(r['sae_enfants'])}",
                 "ici": f"{nb(r['ici_adultes'])} et {nb(r['ici_enfants'])}", "ror": nb(r["unites_ror"]),
                 "statut": r["statut"]} for r in ecarts]
    relecture, fr_ = [], dossier / "relecture_structures.csv"
    if fr_.exists():
        relecture = [{"base": r["base"], "constat": r["constat"], "nombre": nb(r["nombre"]), "traitement": r["traitement"]}
                     for r in lire(fr_)]
    from . import verifications_lieux
    verifs = [{"code": r["code"], "etablissement": r["etablissement"], "date": r["date"], "source": r["source"],
               "adresse": r["adresse"], "constat": r["constat"], "a_refaire": bool(r["a_refaire"])}
              for _, r in verifications_lieux.charger().iterrows()]
    return {"couverture": couverture, "references": refs, "sae": sae, "sae_resume": sae_resume, "etab": etab,
            "etab_resume": etab_resume, "verifs": verifs, "relecture": relecture,
            "liste_verifiee": _liste_verifiee(dossier, lire, nb), "confirmation": _confirmation(dossier, lire, nb)}


def _concordance(dossier):
    """Lignes du tableau de concordance des effectifs avec la DREES, mises en forme pour la page méthode."""
    f, fd = dossier / "concordance_effectifs.csv", dossier / "concordance_effectifs_dep.csv"
    if not f.exists():
        return []

    def lire(chemin):
        with open(chemin, encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh, delimiter=";"))

    def nb(v):
        return f"{float(v.replace(',', '.')):,.0f}".replace(",", "\u00a0") if v else ""

    def pct(v):
        return f"{float(v.replace(',', '.')):+.1%}".replace(".", ",").replace("%", "\u00a0%") if v else ""
    dep = {(d["libelle"], d["mode"]): d for d in lire(fd)} if fd.exists() else {}
    out = []
    for r in lire(f):
        d = dep.get((r["libelle"], r["mode"]))
        rpps = "rpps" in r["fichier_drees"].lower()
        out.append({"libelle": r["libelle"], "nous": nb(r["nous"]), "drees": nb(r["drees"]), "annee": r["annee_drees"],
                    "ecart": pct(r["ecart"]), "tendance": pct(r["ecart_a_l_attendu"]) if rpps else "sans objet",
                    "rang": f"{float(d['rang_spearman'].replace(',', '.')):.3f}".replace(".", ",") if d else "",
                    "explication": r["explication"]})
    return out


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    print(construire(pdf="--sans-pdf" not in sys.argv))
