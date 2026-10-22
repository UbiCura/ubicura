"""FINESS, catégories des établissements sanitaires et médico-sociaux.
Sert à qualifier la structure d'exercice des professionnels salariés (CMP, CMPP, IME, EHPAD...).

Depuis 2026, Finess+ (JSON compressé, une entité juridique contient ses établissements) remplace le
flux historique gelé en mai 2026. Finess+ donne le numéro, le nom et le code de catégorie de chaque
établissement, mais pas les libellés. Les libellés de catégorie et d'agrégat sont repris du flux
historique, qui suit la même nomenclature. Une catégorie absente de l'historique reçoit un libellé
de repli signalé dans le journal. Si Finess+ est indisponible, le flux historique sert seul."""
from __future__ import annotations

import gzip
import json

import pandas as pd

from .. import config
from ..util import (JOURNAL, choisir_ressource, date_version, lire_meta, log, ressources_datagouv, telecharger)

SORTIE = ["nofinesset", "rs", "categetab", "libcategetab", "categagretab", "libcategagretab", "com", "actif"]
# colonnes ajoutées le 12 octobre 2026 pour réunir FINESS et le ROR sans double compte (pipeline/lieux.py), entité
# juridique gestionnaire, adresse et coordonnées (Finess+ seulement, géocodées par la Base Adresse Nationale)
LIEU = ["nofinessej", "adresse", "lat", "lon", "score_ban", "finess_porteuse"]
# codes de département du flux historique pour l'outre-mer
DOM_HISTO = {"9A": "971", "9B": "972", "9C": "973", "9D": "974", "9F": "976"}


def _encodage(chemin) -> str:
    """Le flux historique est publié en UTF-8 depuis 2024, en latin-1 auparavant."""
    with open(chemin, "rb") as f:
        debut = f.read(1 << 20)
    try:
        debut.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError as e:
        # une coupure au milieu d'un caractère en fin de bloc n'invalide pas l'UTF-8
        return "utf-8" if e.start > len(debut) - 4 else "latin-1"


def _historique(hors_ligne, rafraichir):
    dest = config.BRUT / "finess_historique.csv"
    if not hors_ligne:
        res = ressources_datagouv(config.FINESS_HISTORIQUE)
        r = choisir_ressource(res, r"cs1100507", formats={"csv"}) or \
            max([r for r in res if r["format"] == "csv"], key=lambda r: r["taille"] or 0)
        telecharger(r["url"], dest, "finess", rafraichir, extra_meta={"titre": r["titre"], "maj_source": r["maj"]})
    elif not dest.exists():
        raise FileNotFoundError(dest)
    lignes = []
    n = len(config.FINESS_COLONNES_HISTO)
    with open(dest, encoding=_encodage(dest), errors="replace") as f:
        for ligne in f:
            if ligne.startswith("structureet;"):
                champs = ligne.rstrip("\r\n").split(";")
                if len(champs) >= n:
                    lignes.append(champs[:n])
    df = pd.DataFrame(lignes, columns=config.FINESS_COLONNES_HISTO)
    # code commune de l'INSEE, département et numéro de commune (« 9A » et suivants pour l'outre-mer)
    df["com"] = [DOM_HISTO[d] + c[1:] if d in DOM_HISTO else d + c
                 for d, c in zip(df["departement"].str.strip(), df["commune"].str.strip())]
    df["actif"] = True   # le flux historique ne contient que les établissements ouverts
    df["adresse"] = (df["numvoie"].str.strip() + " " + df["typvoie"].str.strip() + " " + df["voie"].str.strip()).str.strip()
    df["lat"] = df["lon"] = df["score_ban"] = float("nan")
    df["finess_porteuse"] = None   # le flux historique ne décrit pas les relations de budget entre établissements
    return df[SORTIE + LIEU].copy(), dest


def _degres(geo: dict) -> tuple:
    """Latitude et longitude en degrés. Finess+ range tantôt les degrés dans coordonneeY et coordonneeX et le Lambert 93
    (en mètres) dans directionLatitude et directionLongitude, tantôt l'inverse (environ 24 000 établissements le
    15 octobre 2026). La paire retenue est celle dont la latitude est en degrés, sinon aucune."""
    for la, lo in (("coordonneeY", "coordonneeX"), ("directionLatitude", "directionLongitude")):
        try:
            y, x = float(geo.get(la)), float(geo.get(lo))
        except (TypeError, ValueError):
            continue
        if -90 <= y <= 90 and -180 <= x <= 180:
            return y, x
    return None, None


def _nouveau(hors_ligne, rafraichir, libelles: pd.DataFrame | None):
    dest = config.BRUT / "finess_plus.json.gz"
    if not hors_ligne:
        res = ressources_datagouv(config.FINESS_NOUVEAU)
        cands = [r for r in res if "mensuel" in r["titre"].lower() and r["titre"].lower().endswith(".json.gz")] or \
                [r for r in res if r["titre"].lower().endswith(".json.gz")]
        if not cands:
            raise RuntimeError("aucune ressource .json.gz dans Finess+")
        r = max(cands, key=lambda r: r["maj"])
        telecharger(r["url"], dest, "finess", rafraichir, extra_meta={"titre": r["titre"], "maj_source": r["maj"]})
    elif not dest.exists():
        raise FileNotFoundError(dest)
    with gzip.open(dest, "rt", encoding="utf-8") as f:
        d = json.load(f)
    lignes = []
    # relations de budget entre établissements (roleEge, rôle « B »), l'établissement non porteuse est une antenne de
    # l'établissement porteuse (schéma de Finess+, constat du 16 octobre 2026 sur les CMPP et les CAMSP)
    num_de, relations = {}, []
    for pm in d.get("pmej", []):
        for e in pm.get("ege", []) or []:
            info = e.get("informationsGeneralesEGE") or {}
            if info.get("egeId"):
                num_de[str(info["egeId"])] = info.get("numFinessEge") or ""
            for r in e.get("roleEge") or []:
                if r.get("roleRelationEge") == "B" and r.get("idEgeNonPorteuse") and r.get("idEgePorteuse"):
                    relations.append((str(r["idEgeNonPorteuse"]), str(r["idEgePorteuse"])))
            adr = next((a for a in (e.get("adresse") or []) if a.get("cogCommune")), {}) or {}
            geo = adr.get("coordonneesGeographique") or {}
            ej = (pm.get("informationsGeneralesPMEJ") or {}).get("numFinessPm") or ""
            lignes.append((info.get("numFinessEge") or "", info.get("nomEgeLong") or info.get("nomEgeCourt") or "",
                           e.get("categorieentiteGeographiqueExercice") or "", e.get("etatObjet") or "",
                           adr.get("cogCommune") or "", ej, adr.get("ligneQuatre") or "",
                           *_degres(geo), geo.get("scoreBAN")))
    df = pd.DataFrame(lignes, columns=["nofinesset", "rs", "categetab", "etat", "com", "nofinessej", "adresse",
                                       "lat", "lon", "score_ban"])
    porteuse = {num_de.get(a, "").strip().zfill(9): num_de.get(b, "").strip().zfill(9) for a, b in relations
                if num_de.get(a) and num_de.get(b) and a != b}
    df["finess_porteuse"] = df["nofinesset"].str.strip().str.zfill(9).map(porteuse)
    JOURNAL.controle("Finess+, établissements rattachés à un établissement porteur (relation de budget)",
                     f"{int(df['finess_porteuse'].notna().sum())} établissements, {len(set(porteuse.values()))} porteurs")
    for c in ("lat", "lon", "score_ban"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["actif"] = df["etat"] == "A"
    if df.empty:
        raise ValueError("aucun établissement lu dans Finess+ (structure du fichier modifiée ?)")
    lab = libelles.drop_duplicates("categetab").set_index("categetab") if libelles is not None else None
    if lab is not None:
        for c in ["libcategetab", "categagretab", "libcategagretab"]:
            df[c] = df["categetab"].map(lab[c])
    else:
        df[["libcategetab", "categagretab", "libcategagretab"]] = None
    sans = df["libcategetab"].isna() & (df["categetab"] != "")
    df.loc[sans, "libcategetab"] = "Catégorie " + df.loc[sans, "categetab"] + " (libellé inconnu)"
    df["libcategagretab"] = df["libcategagretab"].fillna("Agrégat inconnu")
    JOURNAL.controle("Finess+, établissements actifs et fermés", f"{(df['etat'] == 'A').sum()} actifs, "
                     f"{(df['etat'] != 'A').sum()} fermés ou inactifs (gardés, le RPPS peut y faire référence)")
    if sans.any():
        JOURNAL.controle("Finess+, catégories sans libellé dans la nomenclature historique",
                         f"{df.loc[sans, 'categetab'].nunique()} catégories, {int(sans.sum())} établissements")
    JOURNAL.controle("Finess+, établissements actifs avec coordonnées géographiques",
                     f"{int((df['actif'] & df['lat'].notna()).sum())} sur {int(df['actif'].sum())}")
    return df[SORTIE + LIEU].copy(), dest


def charger(hors_ligne=False, rafraichir=False) -> pd.DataFrame | None:
    histo = None
    try:
        histo, dest_h = _historique(hors_ligne, rafraichir)
    except Exception as e:  # noqa: BLE001
        log.warning("FINESS historique indisponible : %s", e)
        JOURNAL.note("FINESS historique (gelé en mai 2026)", "erreur", str(e)[:300])
    essais = [("Finess+", lambda: _nouveau(hors_ligne, rafraichir, histo))]
    if histo is not None:
        essais.append(("FINESS historique (gelé en mai 2026)", lambda: (histo, dest_h)))
    for nom, fonction in essais:
        try:
            df, dest = fonction()
            df["nofinesset"] = df["nofinesset"].str.strip().str.zfill(9)
            df = df[df["nofinesset"].str.len() == 9].drop_duplicates("nofinesset")
            if df.empty:
                raise ValueError("table vide après lecture")
            meta = lire_meta(dest)
            detail = f"{len(df)} établissements"
            if nom == "Finess+" and histo is not None:
                detail += ", libellés de catégorie repris du flux historique"
            JOURNAL.note(f"FINESS ({nom})", "ok", detail,
                         url=meta.get("url", ""), date_donnees=date_version(meta), lignes=len(df))
            return df
        except Exception as e:  # noqa: BLE001
            log.warning("FINESS via %s indisponible : %s", nom, e)
            JOURNAL.note(f"FINESS ({nom})", "erreur", str(e)[:300])
    return None
