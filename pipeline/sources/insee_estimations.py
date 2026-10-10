"""INSEE, estimations localisées de population au 1er janvier, par département (Licence Ouverte).

Lues par l'interface Melodi de l'INSEE (config.INSEE_ESTIMATIONS_API), jeu DS_ESTIMATION_POPULATION, population totale
tous âges et deux sexes. Les trois dernières années sont provisoires (statut « P »). Ces populations ne servent qu'au
calcul des densités de l'évolution de l'offre, les autres densités reposent sur les populations du référentiel."""
from __future__ import annotations

import json

import pandas as pd

from .. import config
from ..util import JOURNAL, get_json, lire_meta, meta_path

SOURCE = "INSEE, estimations de population"
DEST = config.BRUT / "insee_estimations_dep.csv"
FILTRE = "?GEO=DEP&EP_MEASURE=POP_JAN_1ST&SEX=_T&AGE=_T&maxResult=10000"


def charger(hors_ligne=False, rafraichir=False):
    """Renvoie un DataFrame (code, annee, population, statut) ou None."""
    try:
        if not hors_ligne:
            cat = get_json(config.INSEE_ESTIMATIONS_API.replace("/data/", "/catalog/"))
            maj = cat.get("modified", "")
            ancien = lire_meta(DEST)
            if rafraichir or not DEST.exists() or ancien.get("maj_source") != maj:
                obs, url = [], config.INSEE_ESTIMATIONS_API + FILTRE
                while url:
                    j = get_json(url)
                    obs += j.get("observations", [])
                    url = (j.get("paging") or {}).get("next")
                lignes = [{"code": o["dimensions"]["GEO"].split("-")[-1], "annee": int(o["dimensions"]["TIME_PERIOD"]),
                           "population": o["measures"]["OBS_VALUE_NIVEAU"]["value"],
                           "statut": (o.get("attributes") or {}).get("OBS_STATUS", "")} for o in obs]
                if len(lignes) < 1000:
                    raise IOError(f"réponse incomplète ({len(lignes)} observations)")
                pd.DataFrame(lignes).sort_values(["code", "annee"]).to_csv(DEST, sep=";", index=False)
                meta_path(DEST).write_text(json.dumps({"url": config.INSEE_ESTIMATIONS_API + FILTRE, "maj_source": maj,
                                                       "observations": len(lignes)}, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
        if not DEST.exists():
            raise FileNotFoundError(DEST)
        t = pd.read_csv(DEST, sep=";", dtype={"code": str, "statut": str})
    except Exception as e:  # noqa: BLE001
        JOURNAL.note(SOURCE, "erreur", str(e)[:300])
        return None
    meta = lire_meta(DEST)
    prov = sorted(t.loc[t["statut"] == "P", "annee"].unique())
    JOURNAL.note(SOURCE, "ok", f"{t['code'].nunique()} départements, {t['annee'].min()} à {t['annee'].max()}"
                 + (f", provisoires {prov[0]} à {prov[-1]}" if prov else ""),
                 url=meta.get("url", ""), date_donnees=(meta.get("maj_source") or "")[:10])
    return t
