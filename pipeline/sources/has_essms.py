"""HAS, résultats d'évaluation des établissements et services sociaux et médico-sociaux (ESSMS), données ouvertes
(Licence Ouverte 2.0).

Depuis 2023, chaque ESSMS est évalué tous les cinq ans par un organisme accrédité selon le référentiel de la HAS. Le
jeu data.gouv publie une ligne par évaluation, avec le numéro FINESS géographique de la structure évaluée, sa catégorie
FINESS et les dates de l'évaluation (vérifié par l'API le 16 octobre 2026). On garde le petit fichier de l'échelle de
qualité (parquet), pas la base des rapports (plus de 350 Mo). Une structure évaluée sous la catégorie de son type
confirme qu'elle est en activité à la date de l'évaluation (accord de Lucas du 16 octobre 2026). Le cycle court sur cinq
ans, une structure pas encore évaluée n'est pas douteuse pour autant.
"""
from __future__ import annotations

import pandas as pd

from .. import config
from ..util import JOURNAL, date_version, lire_meta, log, ressources_datagouv, telecharger

DOSSIER = config.BRUT / "has"
DEST = DOSSIER / "has_essms_evaluations.parquet"
SOURCE = "HAS, évaluation des établissements et services médico-sociaux"


def ressource() -> dict | None:
    """Fichier de l'échelle de qualité au format parquet, trouvé par le motif de son titre."""
    return next((r for r in ressources_datagouv(config.HAS_ESSMS_JEU)
                 if r["format"] == "parquet" and config.HAS_ESSMS_MOTIF in r["titre"].lower()), None)


def charger(hors_ligne=False, rafraichir=False) -> dict | None:
    """Renvoie {"evaluations": DataFrame (finess, categorie, date), "maj"} ou None."""
    try:
        if not hors_ligne:
            r = ressource()
            if r is None:
                raise IOError(f"ressource {config.HAS_ESSMS_MOTIF} introuvable dans {config.HAS_ESSMS_JEU}")
            telecharger(r["url"], DEST, "has", rafraichir, hors_ligne, taille_min=100_000,
                        extra_meta={"maj_source": r["maj"]})
        e = pd.read_parquet(DEST, columns=["finess_geo", "essms_categ_finess_code", "eval_date_fin"])
    except Exception as ex:  # noqa: BLE001
        JOURNAL.note(SOURCE, "erreur", str(ex)[:300])
        log.warning("évaluations des ESSMS indisponibles : %s", ex)
        return None
    e = pd.DataFrame({"finess": e["finess_geo"].astype(str).str.strip().str.zfill(9),
                      "categorie": e["essms_categ_finess_code"].astype(str).str.strip(),
                      "date": pd.to_datetime(e["eval_date_fin"], errors="coerce")})
    e = e.sort_values("date").drop_duplicates(["finess", "categorie"], keep="last").reset_index(drop=True)
    meta = lire_meta(DEST)
    maj = date_version(meta)
    # une date de fin postérieure à la version du fichier est une erreur de saisie, l'évaluation compte quand même
    # (la structure a été évaluée), mais la date n'entre pas dans la période affichée
    futur = e["date"] > pd.Timestamp(maj or pd.Timestamp.today().date())
    d = e.loc[~futur, "date"]
    JOURNAL.note(SOURCE, "ok", f"{e['finess'].nunique()} structures évaluées, évaluations achevées du "
                 f"{d.min():%d/%m/%Y} au {d.max():%d/%m/%Y}", date_donnees=maj, lignes=len(e),
                 url=meta.get("url", ""))
    JOURNAL.controle("Évaluations des établissements médico-sociaux datées après la version du fichier (attendu, "
                     "aucune)", "aucune" if not futur.any() else f"{int(futur.sum())}, gardées comme évaluations, "
                     f"date écartée de la période")
    return {"evaluations": e, "maj": maj}
