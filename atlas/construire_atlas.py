"""Assemble atlas.html, page autonome (bibliothèques, fond de carte et données intégrés).
Usage  python atlas/construire_atlas.py [site_data.json]
Sans argument, prend le site_data.json de la dernière exécution (resultats/AAAA-MM-JJ/).
L'atlas ne contient que des données réelles produites par run.py. Le site (pipeline/site.py) appelle
construire() avec une barre de navigation."""
import json
import os
import re
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
from pipeline import config  # noqa: E402


def dernier_site_data() -> Path:
    dates = sorted(p for p in config.RESULTATS.glob("20*") if (p / "site_data.json").exists())
    if not dates:
        raise FileNotFoundError("Aucun site_data.json trouvé. Lancez d'abord python run.py.")
    return dates[-1] / "site_data.json"


# Mention de la licence ISC de d3 et de topojson-client, à reproduire dans toute copie
ISC = ("/* Copyright {} Mike Bostock\n"
       "Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is "
       "hereby granted, provided that the above copyright notice and this permission notice appear in all copies.\n"
       "THE SOFTWARE IS PROVIDED \"AS IS\" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE "
       "INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR "
       "ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, "
       "DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN "
       "CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE. */\n")


def _fond() -> Path:
    """Fond de carte fabriqué par python run.py à partir des contours de l'IGN (pipeline.cartes)."""
    sys.path.insert(0, str(ICI.parent))
    from pipeline import cartes
    if not cartes.FOND_ATLAS.exists():
        raise FileNotFoundError("Fond de carte absent. Lancez d'abord python run.py.")
    return cartes.FOND_ATLAS


def _tuiles() -> dict | None:
    """Position de chaque département sur la grille de la carte en tuiles, la même que dans les rapports."""
    try:
        from pipeline import cartes
        from pipeline.sources import referentiel
        f = cartes.fonds(referentiel.charger(True, False))
        return {k: list(v) for k, v in cartes.grille_tuiles(f["dep"]).items()} if f else None
    except Exception:  # noqa: BLE001, la carte classique suffit si les contours manquent
        return None


def _polices() -> str:
    """Polices Newsreader et Work Sans (licence OFL) intégrées à l'atlas, pour ne rien charger chez un tiers."""
    import base64
    dossier = ICI.parent / "gabarits" / "polices"
    css = (dossier / "polices.css").read_text(encoding="utf-8")
    return re.sub(r"url\(([\w.-]+\.woff2)\)", lambda m: "url(data:font/woff2;base64,"
                  + base64.b64encode((dossier / m.group(1)).read_bytes()).decode() + ")", css)


def construire(src: Path, dest: Path, nav: str = "") -> Path:
    data = json.loads(Path(src).read_text(encoding="utf-8"))
    data.setdefault("tuiles", _tuiles())
    # citation de l'atlas et de ses graphiques, DOI repris dès qu'il est renseigné dans config
    data["citation"] = {"projet": config.NOM_PROJET, "auteur_court": config.CITATION_AUTEUR, "doi": config.DOI_DONNEES,
                        "adresse": config.ADRESSE_SITE, "titre_donnees": config.TITRES_DEPOTS["donnees"],
                        "version_zenodo": config.VERSION_ZENODO}
    # limites des données relues dans config, pour qu'une précision ajoutée paraisse sans attendre la prochaine exécution
    data["limites"] = {k: {"risque": L["risque"], "texte": L["texte"], "sources": L["sources"],
                           "territoires": L.get("territoires", {})} for k, L in config.LIMITES.items()}
    data["limites_alias"] = config.LIMITES_ALIAS
    # rapports par territoire publiés à côté de l'atlas, pour y renvoyer depuis la fiche d'un territoire
    # l'atlas autonome (atlas/atlas.html) renvoie aux rapports publiés dans site/territoires
    dossier = Path(dest).parent / "territoires"
    if not dossier.exists():
        dossier = config.RACINE / "site" / "territoires"
    data["rapports_territoires"] = sorted(f.stem for f in dossier.glob("*-*-*.html"))
    data["rapports_dossier"] = os.path.relpath(dossier, Path(dest).parent).replace("\\", "/")
    # dossier du site, pour renvoyer chaque indicateur à la fiche de son jeu de données
    data["site_dossier"] = os.path.relpath(dossier.parent, Path(dest).parent).replace("\\", "/")
    html = (ICI / "atlas_template.html").read_text(encoding="utf-8")
    remplacements = {
        "/*D3*/": ISC.format("2010-2023") + (ICI / "vendor" / "d3.min.js").read_text(encoding="utf-8"),
        "/*TOPO*/": ISC.format("2012-2019") + (ICI / "vendor" / "topojson-client.min.js").read_text(encoding="utf-8"),
        "/*TOPOLOGY*/": "window.TOPO=" + _fond().read_text(encoding="utf-8") + ";",
        "/*DONNEES*/": "window.DONNEES=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";",
        "/*POLICES*/": _polices(),
    }
    for k, v in remplacements.items():
        html = html.replace(k, v.replace("</script", "<\\/script"), 1)
    html = html.replace("<!--NAV-->", nav, 1)
    # graphiques interactifs, même module que les rapports du site (gabarits/figures.js)
    fig = (ICI.parent / "gabarits" / "figures.js").read_text(encoding="utf-8")
    reglage = ('window.FIGURES={zoom:"#scatter,#cbPlot,#funnel,#acpPlan,#lorenz,#escalier",'
               'bulle:"#scatter,#cbPlot,#indPlot,#regPlot,#lorenz,#escalier,#funnel,#acpPlan,#effetVille"};')
    html = html.replace("</body>", "<script>" + reglage + fig + "</script>\n</body>", 1)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    return dest


if __name__ == "__main__":
    try:
        src = Path(sys.argv[1]) if len(sys.argv) > 1 else dernier_site_data()
    except FileNotFoundError as e:
        sys.exit(str(e))
    d = construire(src, ICI / "atlas.html")
    print(f"atlas.html écrit ({d.stat().st_size / 1e6:.1f} Mo) à partir de {src}")
