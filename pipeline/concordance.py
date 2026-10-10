"""Tableau de concordance des effectifs avec les séries publiées par la DREES.

Pour chaque profession comparable, l'effectif national du programme (personnes ayant au moins une activité dans
l'extraction du RPPS) est rapproché de la dernière valeur publiée par la DREES, avec le champ de chaque source et
l'écart attendu du seul fait de la date (croissance annuelle observée par la DREES). Par département, on compare le
classement des départements (corrélation de rang) et le rapport entre les deux effectifs. Les écarts de champ ne
sont pas corrigés, ils sont décrits, pour que chaque chiffre publié puisse être rapproché d'une source officielle."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from . import config
from .util import JOURNAL, lire_meta

MEDECINS = [x[1] for x in config.SPECIALITES_MEDECINS] + [config.MEDECIN_AUTRE[0], config.MEDECIN_INCONNU[0]]
NOTE_DEP = ("La DREES place chaque professionnel dans le département de son activité la plus récente. Ici, une "
            "personne compte dans chaque département où elle a une activité de soins avec un lieu, les activités sans "
            "soins à la population et les activités sans lieu (remplacements) sont exclues.")


def _date_rpps():
    m = lire_meta(config.BRUT / "rpps_activite.txt")
    d = pd.to_datetime(m.get("maj_source") or m.get("telecharge_le"), errors="coerce", utc=True)
    return None if pd.isna(d) else d.date()


def _date_reference(motif, annee):
    """Date à laquelle la DREES mesure l'effectif de l'année indiquée."""
    if "salariees" in motif:
        return date(annee, 12, 31)       # postes au 31 décembre
    if "liberales" in motif:
        return date(annee, 7, 1)         # activité au cours de l'année, milieu d'année par convention
    return date(annee, 1, 1)


def _profs(profs):
    return MEDECINS if profs == ["medecins"] else profs


def _explication(motif, annee, jour, attendu, champ=""):
    """Phrase qui explique l'écart, complétée par la précision de champ propre à la ligne s'il y en a une."""
    base = _explication_base(motif, annee, jour, attendu)
    # la précision est ce qui suit le champ commun des séries tirées du RPPS (config._RPPS)
    precision = champ[len(config._RPPS):].lstrip(", ") if champ.startswith(config._RPPS) else ""
    return base + (f" Écart de définition, {precision}." if precision else "")


def _explication_base(motif, annee, jour, attendu):
    if "adeli" in motif:
        return (f"Champs différents. La DREES compte les inscrits au répertoire Adeli, actifs de moins de 62 ans, au "
                f"1er janvier {annee}, dernière année publiée avant le passage au RPPS. Ici, toutes les personnes ayant "
                f"au moins une activité au RPPS le {jour:%d/%m/%Y}, sans limite d'âge.")
    if "liberales" in motif:
        return ("Champs différents. La DREES compte les infirmières libérales ayant eu une activité remboursée dans "
                "l'année. Ici, toutes les personnes ayant au moins une activité libérale déclarée au RPPS, active ou "
                "non, remplaçantes comprises.")
    if "salariees" in motif:
        return ("Champs différents. La DREES compte les postes principaux d'infirmière salariée déclarés par les "
                "employeurs. Le RPPS sous-enregistre les infirmières salariées, en particulier à l'hôpital, la DREES "
                "juge d'ailleurs ce répertoire encore insuffisant pour décrire les infirmières.")
    n = f"{attendu:,.0f}".replace(",", "\u00a0")
    return (f"Même répertoire. La DREES compte les actifs au 1er janvier {annee}, l'extraction utilisée ici date du "
            f"{jour:%d/%m/%Y}. À la croissance annuelle observée par la DREES, on attendrait environ {n} à cette date.")


def calculer(agg, drees):
    """Renvoie {"concordance_effectifs": ..., "concordance_effectifs_dep": ...} (tables vides sans la source)."""
    if drees is None or drees.empty:
        return {}
    jour = _date_rpps() or date.today()
    nat = agg.national
    dep = agg.effectifs["dep"]
    lignes, lignes_dep = [], []
    for motif, spec, mode, profs, libelle, champ in config.DREES_DEMOGRAPHIE:
        d = drees[(drees["motif"] == motif) & (drees["spec"] == (spec or "")) & drees["effectif"].notna()]
        fr = d[d["niveau"] == "france"].sort_values("annee")
        if fr.empty:
            continue
        p = _profs(profs)
        nous = int(nat.loc[nat["prof"].isin(p) & (nat["mode"] == mode), "n"].sum())
        a, v = int(fr["annee"].iloc[-1]), float(fr["effectif"].iloc[-1])
        croissance = fr["effectif"].iloc[-1] / fr["effectif"].iloc[-2] - 1 if len(fr) >= 2 else np.nan
        ans = (jour - _date_reference(motif, a)).days / 365.25
        attendu = v * (1 + croissance) ** ans if pd.notna(croissance) else np.nan
        lignes.append({"libelle": libelle, "professions": " + ".join(profs), "mode": mode, "nous": nous,
                       "date_rpps": jour.isoformat(), "drees": int(v), "annee_drees": a, "champ_drees": champ,
                       "ecart": nous / v - 1, "croissance_annuelle_drees": croissance,
                       "attendu_a_la_date": attendu, "ecart_a_l_attendu": nous / attendu - 1 if attendu else np.nan,
                       "explication": _explication(motif, a, jour, attendu, champ),
                       "fichier_drees": fr["titre"].iloc[-1], "source": config.DREES_DEMOGRAPHIE_PAGE})
        # départements, dernière année publiée
        dd = d[(d["niveau"] == "dep") & (d["annee"] == a)].set_index("code")["effectif"]
        nd = dep[dep["prof"].isin(p) & (dep["mode"] == mode)].groupby("code")["n"].sum()
        j = pd.concat([dd.rename("drees"), nd.rename("nous")], axis=1, join="inner").dropna()
        j = j[j["drees"] > 0]
        if len(j) >= 10:
            r = j["nous"] / j["drees"]
            lignes_dep.append({"libelle": libelle, "mode": mode, "annee_drees": a, "departements": len(j),
                               "rang_spearman": spearmanr(j["nous"], j["drees"]).statistic,
                               "rapport_median": r.median(), "rapport_p10": r.quantile(.1),
                               "rapport_p90": r.quantile(.9), "rapport_min": r.min(), "dep_min": r.idxmin(),
                               "rapport_max": r.max(), "dep_max": r.idxmax(), "note": NOTE_DEP})
    t = pd.DataFrame(lignes)
    td = pd.DataFrame(lignes_dep)
    for _, x in t.iterrows():
        dd = td[td["libelle"] == x["libelle"]]
        rang = f", rang des départements {dd['rang_spearman'].iloc[0]:.3f}" if len(dd) else ""
        attendu = (f", écart à la tendance {x['ecart_a_l_attendu']:+.1%}"
                   if "rpps" in x["fichier_drees"].lower() and pd.notna(x["ecart_a_l_attendu"]) else "")
        JOURNAL.controle(f"Concordance avec la DREES, {x['libelle'].lower()}",
                         f"{x['nous']} ici, {x['drees']} pour la DREES ({x['annee_drees']}), écart {x['ecart']:+.1%}"
                         f"{attendu}{rang}")
    return {"concordance_effectifs": t, "concordance_effectifs_dep": td}
