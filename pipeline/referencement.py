"""Référencement du site par les moteurs de recherche et aperçu des liens partagés (feuille de route de la
communication, phase 1, accord de Lucas du 29 octobre 2026). Rien n'est publié ici, ces balises partent avec le site
quand Lucas le met en ligne.

- Adresse de référence (canonical) et aperçu des liens (Open Graph, carte des réseaux) sur chaque page.
- Balises de citation des rapports pour Google Scholar (citation_*), d'après ses consignes aux éditeurs,
  https://scholar.google.com/intl/fr/scholar/inclusion.html#indexing (lues le 29 octobre 2026).
- Description du jeu de données en schema.org Dataset pour Google Dataset Search, https://schema.org/Dataset et
  https://developers.google.com/search/docs/appearance/structured-data/dataset (lues le 29 octobre 2026).
- sitemap.xml et robots.txt.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import config
from .util import JOURNAL, log

IMAGE_APERCU = "apercu.png"
LARGEUR_APERCU, HAUTEUR_APERCU = 1200, 630   # format conseillé pour les aperçus de liens (Open Graph)
TEXTE_APERCU = "Carte des départements de France, densité de psychiatres comparée à la moyenne des départements"
# dossiers du site qui ne sont jamais mis en ligne (outils/publier.ps1) ou réservés au travail
EXCLUS = re.compile(r"^(prototype\d*|maquettes|_.*)$")
MARQUE = "<!-- referencement -->"
LICENCE_OUVERTE = "https://www.data.gouv.fr/pages/legal/licences/etalab-2.0/"   # page du registre pipeline/licences.py


def _adresse() -> str:
    return config.ADRESSE_SITE.rstrip("/")


def pages_publiques(site: Path) -> list[Path]:
    """Pages HTML qui partent en ligne, hors des dossiers exclus de la publication."""
    return sorted(p for p in site.rglob("*.html")
                  if not any(EXCLUS.match(x) for x in p.relative_to(site).parts[:-1]))


def _chemin(site: Path, page: Path) -> str:
    rel = page.relative_to(site).as_posix()
    return "" if rel == "index.html" else rel


def _attr(v: str) -> str:
    return html.escape(v, quote=True)


def _meta(nom: str, valeur: str, propriete=False) -> str:
    return f'<meta {"property" if propriete else "name"}="{nom}" content="{_attr(valeur)}">'


def balises_page(chemin: str, avec_image: bool) -> str:
    """Adresse de référence et aperçu du lien. Le titre et la description viennent déjà de base.html."""
    url = f"{_adresse()}/{chemin}"
    out = [f'<link rel="canonical" href="{_attr(url)}">', _meta("og:url", url, True)]
    if avec_image:
        img = f"{_adresse()}/{IMAGE_APERCU}"
        out += [_meta("og:image", img, True), _meta("og:image:width", str(LARGEUR_APERCU), True),
                _meta("og:image:height", str(HAUTEUR_APERCU), True), _meta("og:image:alt", TEXTE_APERCU, True),
                _meta("twitter:card", "summary_large_image"), _meta("twitter:image:alt", TEXTE_APERCU)]
    else:
        out.append(_meta("twitter:card", "summary"))
    return "".join(out)


def balises_rapport(cle: str, iso: str, titre: str, pdf: bool) -> str:
    """Balises de citation d'une version d'un rapport national (Google Scholar). Le DOI n'est donné que pour la version
    archivée sur Zenodo, une version de travail n'a que son adresse."""
    out = [_meta("citation_title", titre), _meta("citation_author", "Pithon, Lucas"),
           _meta("citation_author_orcid", f"https://orcid.org/{config.ORCID}"),
           _meta("citation_publication_date", iso.replace("-", "/")),
           _meta("citation_technical_report_institution", config.NOM_PROJET),
           _meta("citation_language", "fr"),
           _meta("citation_abstract_html_url", f"{_adresse()}/rapports/{iso}/{cle}.html")]
    if pdf:
        out.append(_meta("citation_pdf_url", f"{_adresse()}/rapports/{iso}/{cle}.pdf"))
    doi = config.DOI_RAPPORTS.get(cle)
    if doi and iso == config.VERSION_ZENODO:
        out.append(_meta("citation_doi", doi))
    return "".join(out)


def jeu_de_donnees(iso: str, archive: str, sources: list[str]) -> dict:
    """Description schema.org du jeu de données de la version, pour la page des fichiers à télécharger. Les sources
    d'origine sont les pages des jeux de la page « Données sources »."""
    adresse = _adresse()
    return {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": config.TITRES_DEPOTS["donnees"],
        "alternateName": f"{config.NOM_PROJET}, données",
        "description": ("Effectifs et densités des professionnels de santé et de santé mentale, structures de soins et "
                        "profil des habitants, par commune, intercommunalité, département et région, en France. "
                        "Données agrégées tirées des bases publiques (répertoire RPPS, FINESS, Répertoire opérationnel "
                        "des ressources, INSEE, DREES, Assurance Maladie, Santé publique France, CAF, HAS), avec les "
                        "contrôles, les limites connues et le dictionnaire des colonnes."),
        "url": f"{adresse}/methode-fichiers.html",
        "identifier": f"https://doi.org/{config.DOI_DONNEES}",
        "sameAs": f"https://doi.org/{config.DOI_DONNEES}",
        "version": iso, "dateModified": iso, "inLanguage": "fr", "isAccessibleForFree": True,
        "license": LICENCE_OUVERTE,
        "creator": {"@type": "Person", "name": "Lucas Pithon", "sameAs": f"https://orcid.org/{config.ORCID}"},
        "keywords": ["offre de soins", "santé mentale", "professionnels de santé", "démographie médicale",
                     "structures de soins", "géographie de la santé", "France", "RPPS", "FINESS"],
        "spatialCoverage": {"@type": "Place", "name": "France"},
        "temporalCoverage": f"2016-01-01/{iso}",
        "distribution": [{"@type": "DataDownload", "encodingFormat": "application/zip",
                          "contentUrl": f"{adresse}/{archive}"}],
        "isBasedOn": list(dict.fromkeys(s for s in sources if s.startswith("http"))),
    }


def _sans_bloc(texte: str) -> str:
    """Page sans le bloc d'une application précédente (page d'une ancienne version gardée telle quelle)."""
    return re.sub(re.escape(MARQUE) + r"[\s\S]*?\n(?=</head>)", "", texte, count=1) if MARQUE in texte else texte


def _injecter(texte: str, balises: str) -> str:
    """Balises posées juste avant </head>, le bloc précédent remplacé, jamais doublé."""
    texte = _sans_bloc(texte)
    if "</head>" not in texte:
        return texte
    return texte.replace("</head>", f"{MARQUE}{balises}\n</head>", 1)


def image_apercu(site: Path, carte_svg: str, exe: str | None, iso: str) -> bool:
    """Image d'aperçu des liens partagés, la carte de l'accueil sur fond blanc (règle 16 des exports) avec le nom du
    site, une phrase et ce que montre la carte (règle 4 des figures), photographiée par le navigateur sans fenêtre.
    Aucun nom de territoire."""
    from .lecture import date_longue
    cible = site / IMAGE_APERCU
    if not (exe and carte_svg):
        return cible.exists()
    polices = (site / "polices" / "polices.css").resolve().as_uri()
    page = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><link rel="stylesheet" href="{polices}">
<style>html,body{{margin:0;width:{LARGEUR_APERCU}px;height:{HAUTEUR_APERCU}px;overflow:hidden;background:#fff}}
body{{display:flex;align-items:center;font-family:"Work Sans",system-ui,sans-serif;color:#15171C}}
.texte{{flex:1;padding:0 40px 0 72px}}.nom{{font:600 30px "Work Sans",sans-serif;color:#1D4D87;margin:0 0 26px}}
h1{{font:500 54px/1.12 "Newsreader",Georgia,serif;margin:0 0 26px}}p{{font-size:24px;line-height:1.4;margin:0;color:#4A4F5A}}
.carte{{width:470px;height:{HAUTEUR_APERCU}px;display:flex;align-items:center;justify-content:center;padding-right:40px}}
.carte svg{{height:590px;width:auto}}.leg{{font-size:17px;line-height:1.4;color:#5A606C;margin-top:30px}}</style></head><body>
<div class="texte"><p class="nom">{config.NOM_PROJET}</p><h1>L’offre de soins en France, territoire par territoire</h1>
<p>Professionnels et structures de santé et de santé mentale, profil des habitants. Données publiques, sourcées et
citables.</p><p class="leg">Carte, psychiatres pour 10 000 habitants par département, comparés à la moyenne des
départements. Données du {date_longue(iso)}.</p></div><div class="carte">{carte_svg}</div></body></html>"""
    profil = tempfile.mkdtemp(prefix="profil_apercu_")
    source = Path(tempfile.mkdtemp(prefix="apercu_")) / "apercu.html"
    source.write_text(page, encoding="utf-8")
    try:
        subprocess.run([exe, "--headless=new", "--disable-gpu", f"--user-data-dir={profil}", "--no-first-run",
                        "--hide-scrollbars", f"--window-size={LARGEUR_APERCU},{HAUTEUR_APERCU}",
                        "--virtual-time-budget=4000", f"--screenshot={cible}", source.as_uri()],
                       capture_output=True, timeout=120, check=False)
    except Exception as e:  # noqa: BLE001
        log.warning("image d'aperçu impossible : %s", e)
    finally:
        shutil.rmtree(profil, ignore_errors=True)
        shutil.rmtree(source.parent, ignore_errors=True)
    return cible.exists() and cible.stat().st_size > 5_000


def sitemap(site: Path, pages: list[Path], iso: str) -> str:
    """Plan du site, chaque page publique avec la date de la version (les pages sont toutes refaites à chaque version)."""
    lignes = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in pages:
        lignes.append(f"  <url><loc>{html.escape(_adresse() + '/' + _chemin(site, p))}</loc><lastmod>{iso}</lastmod></url>")
    lignes.append("</urlset>")
    return "\n".join(lignes) + "\n"


def robots() -> str:
    return f"User-agent: *\nAllow: /\n\nSitemap: {_adresse()}/sitemap.xml\n"


def appliquer(site: Path, iso: str, rapports: dict[str, dict], fichiers: dict | None, exe: str | None,
              carte_svg: str) -> dict:
    """Pose les balises sur toutes les pages publiques, écrit l'image d'aperçu, sitemap.xml et robots.txt.
    rapports, {chemin relatif: {cle, iso, titre, pdf}} ; fichiers, {page, archive, sources} pour la page des données."""
    avec_image = image_apercu(site, carte_svg, exe, iso)
    # une page de renvoi (atlas.html vers index.html) garde sa propre adresse de référence et sort du plan du site
    pages = [p for p in pages_publiques(site) if 'http-equiv="refresh"' not in p.read_text(encoding="utf-8")]
    n_cit = n_jeu = 0
    for p in pages:
        chemin = _chemin(site, p)
        balises = balises_page(chemin, avec_image)
        r = rapports.get(p.relative_to(site).as_posix())
        if r:
            balises += balises_rapport(r["cle"], r["iso"], r["titre"], r["pdf"])
            n_cit += 1
        if fichiers and p.relative_to(site).as_posix() == fichiers["page"]:
            # « </ » échappé pour qu'aucun texte du jeu ne ferme la balise script
            jeu = json.dumps(jeu_de_donnees(iso, fichiers["archive"], fichiers["sources"]),
                             ensure_ascii=False).replace("</", "<\\/")
            balises += f'<script type="application/ld+json">{jeu}</script>'
            n_jeu += 1
        texte = _sans_bloc(p.read_text(encoding="utf-8"))
        # la première page vient de l'atlas (atlas_template.html), qui ne porte ni le nom du site ni la description
        # de l'aperçu, ajoutés ici sans toucher au gabarit de l'atlas
        if 'property="og:site_name"' not in texte:
            balises += _meta("og:type", "website", True) + _meta("og:site_name", config.NOM_PROJET, True)
        if 'property="og:description"' not in texte:
            m = re.search(r'<meta name="description" content="([^"]*)"', texte)
            if m:
                balises += _meta("og:description", html.unescape(m.group(1)), True)
        nouveau = _injecter(texte, balises)
        if nouveau != p.read_text(encoding="utf-8"):
            p.write_text(nouveau, encoding="utf-8")
    (site / "sitemap.xml").write_text(sitemap(site, pages, iso), encoding="utf-8")
    (site / "robots.txt").write_text(robots(), encoding="utf-8")
    bilan = {"pages": len(pages), "citations": n_cit, "jeu": n_jeu, "image": avec_image}
    JOURNAL.controle("Site, référencement (adresse de référence, aperçu, citation des rapports, jeu de données)",
                     f"{len(pages)} pages, {n_cit} rapports avec balises de citation, {n_jeu} page de données décrite, "
                     f"image d'aperçu {'présente' if avec_image else 'absente'}")
    return bilan
