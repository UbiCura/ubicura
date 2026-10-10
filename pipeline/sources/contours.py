"""Contours des communes, IGN ADMIN EXPRESS COG CARTO PE (petite échelle), Licence Ouverte 2.0.

La couche est lue par le service WFS de la Géoplateforme de l'IGN, page par page, en GeoJSON (coordonnées en
degrés, WGS84). Seul le code INSEE de chaque commune est gardé avec sa géométrie. La date de mise à jour côté
producteur est celle du jeu ADMIN EXPRESS sur data.gouv (champ last_update), consignée comme maj_source.

Ces contours servent au voisinage des territoires, aux distances entre communes, aux cartes des rapports
territoriaux et au fond de carte de l'atlas."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from .. import config
from ..util import JOURNAL, get_json, lire_meta, log, meta_path

FICHIER = config.BRUT / "contours_communes_ign.geojson"


def _maj_source() -> str:
    try:
        return (get_json(config.DATAGOUV_API.format(config.CONTOURS_DATAGOUV)).get("last_update") or "")[:10]
    except Exception as e:  # noqa: BLE001
        log.warning("date de mise à jour d'ADMIN EXPRESS indisponible (%s)", e)
        return ""


def _recuperer() -> dict:
    feats, debut, total = [], 0, None
    while total is None or debut < total:
        params = {"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature", "TYPENAMES": config.CONTOURS_COUCHE,
                  "OUTPUTFORMAT": "application/json", "COUNT": config.CONTOURS_PAGE, "STARTINDEX": debut,
                  "SORTBY": "code_insee"}
        url = config.CONTOURS_WFS + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        j = get_json(url)
        total = j.get("numberMatched") or 0
        page = j.get("features") or []
        if not page:
            break
        for f in page:
            feats.append({"type": "Feature", "properties": {"code": f["properties"]["code_insee"]},
                          "geometry": f["geometry"]})
        debut += len(page)
        log.info("  contours IGN : %d communes sur %d", debut, total)
    codes = {f["properties"]["code"] for f in feats}
    if total and len(codes) != total:
        raise IOError(f"contours incomplets, {len(codes)} communes distinctes pour {total} annoncées")
    return {"type": "FeatureCollection", "features": feats}


def charger(hors_ligne=False, rafraichir=False) -> Path:
    """Chemin du GeoJSON des contours des communes, téléchargé si besoin."""
    meta = lire_meta(FICHIER)
    if FICHIER.exists() and not rafraichir:
        age = datetime.now() - datetime.fromtimestamp(FICHIER.stat().st_mtime)
        if hors_ligne:
            log.info("cache %s (%.1f Mo, %d j)", FICHIER.name, FICHIER.stat().st_size / 1e6, age.days)
            return FICHIER
        # en ligne, la date du jeu chez le producteur décide, l'âge du cache ne sert que si elle est inconnue
        maj = _maj_source()
        if (maj and maj == meta.get("maj_source")) or (not maj and age < timedelta(days=config.CACHE_JOURS["contours"])):
            log.info("cache %s, version du producteur inchangée (%s)", FICHIER.name, maj or "date inconnue")
            return FICHIER
    if hors_ligne:
        raise FileNotFoundError(f"Mode hors ligne et fichier absent : {FICHIER}")
    gj = _recuperer()
    tmp = FICHIER.with_suffix(".part")
    tmp.write_text(json.dumps(gj, separators=(",", ":")), encoding="utf-8")
    tmp.replace(FICHIER)
    meta_path(FICHIER).write_text(json.dumps(
        {"url": f"{config.CONTOURS_WFS} ({config.CONTOURS_COUCHE})", "telecharge_le": datetime.now().isoformat(timespec="seconds"),
         "maj_source": _maj_source(), "communes": len(gj["features"]), "jeu_datagouv": config.CONTOURS_DATAGOUV},
        ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("téléchargé %s (%.1f Mo)", FICHIER.name, FICHIER.stat().st_size / 1e6)
    return FICHIER


def date_source() -> str:
    return lire_meta(FICHIER).get("maj_source", "")


def note_journal(detail: str):
    JOURNAL.note("Contours des communes (IGN)", "ok", detail, url=config.CONTOURS_PAGE_PRODUCTEUR,
                 date_donnees=date_source())
