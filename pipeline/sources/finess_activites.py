"""FINESS, activités de soins autorisées et exercées par établissement géographique (flux FINESS+ de l'ANS).

Jeu « FINESS - Activités » de l'Agence du numérique en santé sur data.gouv.fr (identifiant finess-activites-1, Licence
Ouverte 2.0, fichier quotidien et instantané mensuel au format JSON), lu par l'API de data.gouv.fr et vérifié le
16 novembre 2026. Il donne, pour chaque entité juridique (pmej) et chacun de ses établissements géographiques (ege),
les activités de soins autorisées et exercées, à l'ancien format (AMF : activité, modalité, forme) ou au nouveau (AMM :
activité, modalité, mention). C'est la référence la plus récente des activités hospitalières par site : la SAE décrit
l'année 2024, et près d'un site sur trois y a changé depuis (chantier des structures, constat C10,
docs/structures/mesure_2026-11-16/constats.md).

Le fichier, très volumineux une fois décompressé, est lu ligne à ligne, sans le charger en mémoire : seuls les champs
utiles sont relevés, quelle que soit l'indentation. Une activité est retenue quand elle est active (état « A ») et
n'a pas de date de fin effective.

Codes (nomenclatures de l'ANS, TRE R381 activités, R382 modalités, R383 mentions, guide des terminologies de santé,
version du 30 mars 2026 ; ancien format, « Activités modalités formes utilisées dans FINESS », data.gouv.fr, jeu
finess-extraction-des-principales-nomenclatures) : voir AUTORISATIONS.
"""
from __future__ import annotations

import gzip
import re

import pandas as pd

from .. import config
from ..util import JOURNAL, log, ressources_datagouv, telecharger

DATASET = config.FINESS_ACTIVITES
FICHIER = config.BRUT / "finess_activites.json.gz"
SOURCE = "ANS, FINESS - Activités (activités de soins autorisées et exercées)"
PAGE = "https://www.data.gouv.fr/datasets/finess-activites-1"

# type de la liste des structures : (nature, activité, modalités retenues ou None pour toutes)
AUTORISATIONS = {
    # médecine d'urgence : structure des urgences et antenne de médecine d'urgence (pas le SAMU ni le SMUR)
    "lieu_urgences": [("AMM", "QA014", {"MO032", "MO033"}), ("AMF", "14", {"23", "24"})],
    # gynécologie-obstétrique (les accouchements), sans la seule néonatologie
    "lieu_maternite": [("AMM", "QA003", {"MO016"}), ("AMF", "03", None)],
    # hémodialyse en centre et en unités, sans la dialyse à domicile
    "lieu_dialyse": [("AMM", "QA016", {"MO020", "MO021", "MO022", "MO023"}),
                     ("AMF", "16", {"40", "41", "42", "43", "44"})],
    "lieu_had": [("AMM", "QA020", None)],
    "lieu_smr": [("AMM", "QA050", None)] + [("AMF", str(c), None) for c in range(50, 60)],
}

_KV = re.compile(r'^\s*"(\w+)"\s*:\s*"?([^",]*)"?,?\s*$')


def _telecharger(hors_ligne: bool, rafraichir: bool):
    if hors_ligne:
        if not FICHIER.exists():
            raise FileNotFoundError(FICHIER)
        return FICHIER
    res = ressources_datagouv(DATASET)
    cands = [r for r in res if "mensuel" in r["titre"].lower() and r["titre"].lower().endswith(".json.gz")] or \
            [r for r in res if r["titre"].lower().endswith(".json.gz")]
    if not cands:
        raise RuntimeError("aucune ressource .json.gz dans FINESS - Activités")
    r = max(cands, key=lambda r: r["maj"])
    return telecharger(r["url"], FICHIER, "finess", rafraichir, taille_min=10_000_000,
                       extra_meta={"titre": r["titre"], "maj_source": r["maj"]})


def lire(chemin) -> pd.DataFrame:
    """Une ligne par activité d'un établissement géographique : finess_ej, finess_et, nature, etat, fin_effective,
    activite, modalite, forme_ou_mention."""
    lignes, ej, et, cur = [], None, None, {}
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        for ligne in f:
            m = _KV.match(ligne)
            if not m:
                continue
            k, v = m.groups()
            if k == "numFiness":
                ej, et = v, None
            elif k == "numFinessEge":
                et = v
            elif k == "activiteAeId" and v != "null" and v != cur.get("id"):
                # une activité d'une autre nature (médico-sociale, sans fin AMM ni AMF) ne bloque pas la suivante
                cur = {"id": v}
            elif "id" in cur and k in ("etatObjet", "dateFinEffectiveActivite", "codeNature") and k not in cur:
                cur[k] = v
            elif "id" in cur and k in ("activiteAMM", "modaliteAMM", "mentionAMM", "activiteAMF", "modaliteActivite",
                                       "formeActivite"):
                cur[k] = v
            if "id" in cur and k in ("declarationAMM", "formeActivite"):
                amf = k == "formeActivite"
                if et:
                    lignes.append((ej, et, cur.get("codeNature"), cur.get("etatObjet"),
                                   cur.get("dateFinEffectiveActivite"),
                                   cur.get("activiteAMF" if amf else "activiteAMM"),
                                   cur.get("modaliteActivite" if amf else "modaliteAMM"),
                                   cur.get("formeActivite" if amf else "mentionAMM")))
                cur = {}
    return pd.DataFrame(lignes, columns=["finess_ej", "finess_et", "nature", "etat", "fin_effective", "activite",
                                         "modalite", "forme_ou_mention"])


def sites_par_type(a: pd.DataFrame) -> dict[str, set]:
    """Numéros FINESS des établissements géographiques qui exercent l'activité de chaque type, aujourd'hui."""
    a = a[(a["etat"] == "A") & a["fin_effective"].isin(["null", "", None])]
    out = {}
    for t, regles in AUTORISATIONS.items():
        m = pd.Series(False, index=a.index)
        for nat, act, mods in regles:
            m |= (a["nature"] == nat) & (a["activite"] == act) & (a["modalite"].isin(mods) if mods else True)
        out[t] = set(a.loc[m, "finess_et"].str.strip().str.zfill(9))
    return out


def charger(hors_ligne=False, rafraichir=False) -> dict | None:
    """Sites qui exercent chaque activité, ou None si la source manque (notée, n'arrête pas le reste)."""
    try:
        chemin = _telecharger(hors_ligne, rafraichir)
        a = lire(chemin)
    except Exception as e:  # noqa: BLE001
        JOURNAL.note("FINESS - Activités", "erreur", f"source indisponible, {type(e).__name__} {e}"[:300])
        log.warning("FINESS - Activités indisponible : %s", e)
        return None
    if a.empty:
        JOURNAL.note("FINESS - Activités", "erreur", "aucune activité lue (structure du fichier modifiée ?)")
        return None
    s = sites_par_type(a)
    JOURNAL.controle("FINESS - Activités, établissements qui exercent l'activité",
                     ", ".join(f"{t.removeprefix('lieu_')} {len(v)}" for t, v in s.items()))
    return {"sites": s, "activites": a}
