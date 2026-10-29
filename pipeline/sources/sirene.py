"""INSEE, répertoire Sirene des entreprises et de leurs établissements (data.gouv, Licence Ouverte 2.0).

Le stock des établissements (format parquet, environ 2,2 Go, mis à jour chaque mois) est téléchargé, réduit aux
établissements des entités juridiques de FINESS (par leur numéro SIREN, lu dans Finess+), puis supprimé. Seul cet
extrait reste dans donnees/brut/sirene/, avec la date de la version du producteur (maj_source). L'enseigne de chaque
établissement d'un hôpital (« CMP-CATTP ENFANTS ») et son adresse permettent de confirmer une structure de FINESS ou du
ROR et d'en préciser l'adresse (vérification du 13 octobre 2026). Limite, les hôpitaux ferment rarement leurs anciens
établissements dans Sirene, un établissement « actif » peut donc avoir cessé son activité.
"""
from __future__ import annotations

import gzip
import json
from datetime import datetime

import pandas as pd

from .. import config
from ..util import JOURNAL, LectureLocaleImpossible, date_version, lire_meta, log, meta_path, ressources_datagouv, telecharger

DOSSIER = config.BRUT / "sirene"
EXTRAIT = DOSSIER / "etablissements_finess.parquet"
SOURCE = "INSEE, répertoire Sirene, établissements des gestionnaires de FINESS"
COLONNES = ["siren", "siret", "etatAdministratifEtablissement", "dateCreationEtablissement", "dateDebut",
            "enseigne1Etablissement", "enseigne2Etablissement", "enseigne3Etablissement",
            "denominationUsuelleEtablissement", "numeroVoieEtablissement", "indiceRepetitionEtablissement",
            "typeVoieEtablissement", "libelleVoieEtablissement", "complementAdresseEtablissement",
            "codePostalEtablissement", "libelleCommuneEtablissement", "codeCommuneEtablissement",
            "activitePrincipaleEtablissement"]


def sirens_finess() -> dict[str, str]:
    """Numéro SIREN de chaque entité juridique de Finess+ (numéro FINESS de l'entité juridique)."""
    fp = json.load(gzip.open(config.BRUT / "finess_plus.json.gz", "rt", encoding="utf-8"))
    out = {}
    for pm in fp.get("pmej", []):
        ig = pm.get("informationsGeneralesPMEJ") or {}
        if ig.get("numFinessPm") and ig.get("siren"):
            out[ig["numFinessPm"]] = ig["siren"]
    return out


def _mettre_a_jour(rafraichir: bool):
    res = [r for r in ressources_datagouv(config.SIRENE_JEU)
           if r["titre"].startswith("Sirene : Fichier StockEtablissement -") and r["format"] == "parquet"]
    if not res:
        raise IOError("stock des établissements Sirene introuvable")
    r = res[0]
    if EXTRAIT.exists() and lire_meta(EXTRAIT).get("maj_source") == r["maj"] and not rafraichir:
        return
    import pyarrow.dataset as ds
    import pyarrow.parquet as pq
    gros = DOSSIER / "StockEtablissement.parquet"
    try:
        telecharger(r["url"], gros, "sirene", rafraichir=True, taille_min=100_000_000, extra_meta={"maj_source": r["maj"]})
        sirens = sorted(set(sirens_finess().values()))
        d = ds.dataset(gros)
        t = d.to_table(columns=[c for c in COLONNES if c in d.schema.names], filter=ds.field("siren").isin(sirens))
        pq.write_table(t, EXTRAIT)
    finally:
        gros.unlink(missing_ok=True)
        meta_path(gros).unlink(missing_ok=True)
    meta = {"url": r["url"], "titre": r["titre"], "maj_source": r["maj"],
            "telecharge_le": datetime.now().isoformat(timespec="seconds")}
    meta_path(EXTRAIT).write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("Sirene, %s établissements des gestionnaires de FINESS gardés", t.num_rows)


def charger(hors_ligne=False, rafraichir=False) -> dict | None:
    """Renvoie {"etablissements": DataFrame (une ligne par établissement, enseigne et adresse lisibles), "siren": dict
    numéro FINESS de l'entité juridique -> SIREN, "maj"} ou None."""
    try:
        DOSSIER.mkdir(parents=True, exist_ok=True)
        if not hors_ligne:
            _mettre_a_jour(rafraichir)
        if not EXTRAIT.exists():
            raise FileNotFoundError(EXTRAIT)
    except Exception as e:  # noqa: BLE001
        # le nom de l'exception quand son message est vide (lecture échouée sans texte le 29 octobre 2026)
        JOURNAL.note(SOURCE, "erreur", (str(e) or type(e).__name__)[:300])
        log.warning("Sirene indisponible : %r", e)
        return None
    # fichiers en cache, une lecture qui échoue arrête la chaîne (util.LectureLocaleImpossible)
    try:
        s = pd.read_parquet(EXTRAIT)
        siren = sirens_finess()
    except Exception as e:  # noqa: BLE001
        JOURNAL.note(SOURCE, "erreur", f"lecture locale impossible, {type(e).__name__} {e}"[:300])
        raise LectureLocaleImpossible(f"Sirene en cache illisible, {type(e).__name__} {e}"[:300]) from e
    ens = s[["enseigne1Etablissement", "enseigne2Etablissement", "enseigne3Etablissement",
             "denominationUsuelleEtablissement"]].fillna("").agg(" / ".join, axis=1)
    s = s.assign(enseigne=ens.str.replace(r"(\s/\s)+", " / ", regex=True).str.strip(" /"))
    voie = (s[["numeroVoieEtablissement", "indiceRepetitionEtablissement", "typeVoieEtablissement",
               "libelleVoieEtablissement"]].fillna("").astype(str).agg(" ".join, axis=1)
            .str.replace(r"\s+", " ", regex=True).str.strip())
    s["adresse"] = voie.str.replace(r"\b(" + "|".join(config.SIRENE_TYPES_VOIE) + r")\b",
                                    lambda m: config.SIRENE_TYPES_VOIE[m.group(1)], regex=True)
    maj = date_version(lire_meta(EXTRAIT))
    JOURNAL.note(SOURCE, "ok", f"{len(s)} établissements de {s['siren'].nunique()} gestionnaires, dont "
                 f"{int((s['etatAdministratifEtablissement'] == 'A').sum())} actifs", date_donnees=maj, lignes=len(s))
    return {"etablissements": s, "siren": siren, "maj": maj}
