"""HAS, certification des établissements de santé pour la qualité des soins (données ouvertes, Licence Ouverte 2.0).

Deux jeux data.gouv de la Haute Autorité de santé, le référentiel déployé de 2021 à 2025 et le sixième cycle, publient
pour chaque démarche de certification la liste des sites géographiques (numéros FINESS d'établissement) que
l'établissement a rattachés à sa démarche, et la date de la décision. On garde, pour chaque entité juridique, la
démarche la plus récente. Un site cité sert à confirmer qu'une structure inscrite dans FINESS fait bien partie du
périmètre déclaré par l'établissement à cette date (vérification du 13 octobre 2026). La liste vient des numéros
FINESS déclarés par l'établissement, elle ne dit ni l'adresse ni l'activité réelle du site.
"""
from __future__ import annotations

import re

import pandas as pd

from .. import config
from ..util import JOURNAL, date_version, lire_meta, log, ressources_datagouv, telecharger

DOSSIER = config.BRUT / "has"
SOURCE = "HAS, certification des établissements de santé, sites rattachés"


def _jeu(slug: str, motif_geo: str, motif_dem: str, cle: str, hors_ligne: bool, rafraichir: bool):
    geo, dem = DOSSIER / f"{cle}_sites.csv", DOSSIER / f"{cle}_demarches.csv"
    if not hors_ligne:
        res = ressources_datagouv(slug)
        for motif, dest in ((motif_geo, geo), (motif_dem, dem)):
            r = next((x for x in res if x["format"] == "csv" and re.match(motif, x["titre"].lower())), None)
            if r is None:
                raise IOError(f"ressource {motif} introuvable dans {slug}")
            telecharger(r["url"], dest, "has", rafraichir, hors_ligne, taille_min=1000, extra_meta={"maj_source": r["maj"]})
    lire = lambda f: pd.read_csv(f, sep=None, engine="python", dtype=str, encoding="utf-8-sig")  # noqa: E731
    g, d = lire(geo), lire(dem)
    g = g.merge(d[["code_demarche", "date_de_decision"]], on="code_demarche", how="left")
    g["cycle"] = cle
    return g, lire_meta(geo)


def charger(hors_ligne=False, rafraichir=False) -> dict | None:
    """Renvoie {"sites": DataFrame (FINESS_EJ, FINESS_EG, RS_eg, code_demarche, date, cycle), "meta"} ou None."""
    try:
        DOSSIER.mkdir(parents=True, exist_ok=True)
        parts, metas = [], []
        for slug, mg, md, cle in config.HAS_CERTIFICATION:
            g, m = _jeu(slug, mg, md, cle, hors_ligne, rafraichir)
            parts.append(g)
            metas.append(m)
    except Exception as e:  # noqa: BLE001
        JOURNAL.note(SOURCE, "erreur", str(e)[:300])
        log.warning("certification HAS indisponible : %s", e)
        return None
    g = pd.concat(parts, ignore_index=True)
    for c in ("FINESS_EJ", "FINESS_EG"):
        g[c] = g[c].astype(str).str.strip().str.zfill(9)
    g["date"] = pd.to_datetime(g["date_de_decision"], errors="coerce", dayfirst=True)
    derniere = g.dropna(subset=["date"]).sort_values("date").groupby("FINESS_EJ")["code_demarche"].last()
    garder = set(derniere.items())
    g = g[[(e, c) in garder for e, c in zip(g["FINESS_EJ"], g["code_demarche"])]]
    # un même site peut figurer sous deux libellés (deux cycles de la même démarche), les deux sont gardés
    g = g.drop_duplicates(["FINESS_EJ", "FINESS_EG", "RS_eg"])
    maj = max((date_version(m) for m in metas), default="")
    JOURNAL.note(SOURCE, "ok", f"{g['FINESS_EJ'].nunique()} entités juridiques, {len(g)} sites, décisions du "
                 f"{g['date'].min():%d/%m/%Y} au {g['date'].max():%d/%m/%Y}", date_donnees=maj, lignes=len(g))
    return {"sites": g, "maj": maj}
