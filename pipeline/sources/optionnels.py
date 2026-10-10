"""Sources optionnelles.
France Travail : nombre d'offres d'emploi par département (identifiants API requis).
Contours : voisinage des EPCI et des départements pour l'autocorrélation spatiale (shapely requis)."""
from __future__ import annotations

import json
import os
import time

import pandas as pd

from .. import config
from ..util import JOURNAL, log


# ---------------------------------------------------------------- France Travail
def offres_france_travail(ref, hors_ligne=False) -> pd.DataFrame | None:
    cid, secret = os.environ.get("FT_CLIENT_ID"), os.environ.get("FT_CLIENT_SECRET")
    if hors_ligne or not (cid and secret):
        JOURNAL.note("France Travail, offres d'emploi", "ignoré",
                     "définir FT_CLIENT_ID et FT_CLIENT_SECRET pour activer (compte francetravail.io)")
        return None
    import requests
    try:
        tok = requests.post(config.FT_TOKEN, data={"grant_type": "client_credentials", "client_id": cid,
                                                    "client_secret": secret, "scope": config.FT_SCOPE},
                            timeout=30).json()["access_token"]
        s = requests.Session()
        s.headers["Authorization"] = f"Bearer {tok}"
        lignes = []
        for dep in ref.deps["code"]:
            for rome, prof in config.FT_ROME.items():
                r = s.get(config.FT_OFFRES, params={"codeROME": rome, "departement": dep, "range": "0-0"}, timeout=30)
                total = 0
                if r.status_code in (200, 206):
                    cr = r.headers.get("Content-Range", "")
                    total = int(cr.rsplit("/", 1)[-1]) if "/" in cr else len(r.json().get("resultats", []))
                elif r.status_code != 204:
                    log.warning("France Travail %s %s : HTTP %s", rome, dep, r.status_code)
                lignes.append({"dep": dep, "prof": prof, "rome": rome, "offres": total})
                time.sleep(0.12)  # limite de débit de l'API
        df = pd.DataFrame(lignes)
        JOURNAL.note("France Travail, offres d'emploi", "ok", f"{df['offres'].sum()} offres comptées",
                     url=config.FT_OFFRES, date_donnees=pd.Timestamp.now().strftime("%Y-%m-%d"))
        return df
    except Exception as e:  # noqa: BLE001
        JOURNAL.note("France Travail, offres d'emploi", "erreur", str(e)[:300])
        return None


# ---------------------------------------------------------------- contours et voisinage
def voisinages(ref, hors_ligne=False, rafraichir=False) -> dict | None:
    """Renvoie {niveau: {code: set(codes voisins)}} pour epci et dep."""
    try:
        from shapely.geometry import shape
        from shapely.strtree import STRtree
    except ImportError:
        JOURNAL.note("Contours (analyse spatiale)", "ignoré", "installer shapely pour activer")
        return None
    try:
        from . import contours
        dest = contours.charger(hors_ligne, rafraichir)
        gj = json.loads(dest.read_text(encoding="utf-8"))
        actuels = set(ref.communes["code"])
        geoms, codes = [], []
        centres = {}   # code commune actuel -> (longitude, latitude, surface) du plus grand morceau
        for f in gj["features"]:
            c = f["properties"].get("code")
            c = c if c in actuels else ref.anciens.get(c)
            if c:
                g = shape(f["geometry"])
                g = g if g.is_valid else g.buffer(0)
                geoms.append(g)
                codes.append(c)
                pt = g.representative_point()
                if c not in centres or g.area > centres[c][2]:
                    centres[c] = (pt.x, pt.y, g.area)
        arbre = STRtree(geoms)
        rattach = ref.communes.set_index("code")[["epci", "dep"]]
        voisins = {"epci": {}, "dep": {}}
        for i, g in enumerate(geoms):
            for j in arbre.query(g, predicate="intersects"):
                if j <= i:
                    continue
                a, b = codes[i], codes[j]
                for niv in ("epci", "dep"):
                    x, y = rattach.at[a, niv], rattach.at[b, niv]
                    if x != y:
                        voisins[niv].setdefault(x, set()).add(y)
                        voisins[niv].setdefault(y, set()).add(x)
        voisins["centres"] = {c: (x, y) for c, (x, y, _a) in centres.items()}
        contours.note_journal(f"{len(voisins['epci'])} EPCI et {len(voisins['dep'])} départements avec voisins, "
                              f"{len(centres)} communes situées")
        JOURNAL.controle("Communes du référentiel situées sur la carte (pour les distances)",
                         f"{len(centres) / len(actuels):.1%}")
        return voisins
    except Exception as e:  # noqa: BLE001
        JOURNAL.note("Contours (analyse spatiale)", "erreur", str(e)[:300])
        return None
