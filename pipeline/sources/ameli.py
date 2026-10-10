"""Assurance Maladie, cartographie des pathologies et des dépenses (data.ameli.fr, licence ODbL).

Nombre de personnes prises en charge pour un trouble psychique, ou sous traitement psychotrope sans
trouble repéré, par département. Ces chiffres mesurent le recours aux soins, pas le besoin, et
dépendent eux-mêmes de l'offre. Ils servent d'indicateurs indirects, toujours présentés à côté
d'autres et jamais combinés en un score.

Récupération entièrement automatique par l'API Opendatasoft de data.ameli.fr, filtrée sur les
catégories utiles. La date de modification du jeu est consignée pour la future tâche planifiée.
La prévalence standardisée sur l'âge est calculée ici (méthode directe, population de référence,
France entière tous régimes), car le jeu ne la fournit pas."""
from __future__ import annotations

from urllib.parse import quote

import numpy as np
import pandas as pd

from .. import config
from ..analyses import standardisation_directe
from ..util import JOURNAL, get_json, lire_meta, log, telecharger

FAMILLE = config.SANTE_MENTALE
SOURCE = "Assurance Maladie, cartographie des pathologies (data.ameli.fr, licence ODbL)"


def _telecharger(hors_ligne, rafraichir):
    dest = config.BRUT / "ameli_pathologies_psy.csv"
    if hors_ligne:
        if not dest.exists():
            raise FileNotFoundError(dest)
        return dest
    infos = get_json(config.AMELI_API)
    maj = (infos.get("metas", {}).get("default", {}) or {}).get("modified", "")
    annees = get_json(config.AMELI_API + "/records?select=annee&group_by=annee&limit=50")["results"]
    annee = max(str(r["annee"])[:4] for r in annees)
    tops = ",".join(f'"{t}"' for t, *_ in config.AMELI_INDICATEURS)
    where = f'top in ({tops}) and sexe="9" and annee=date\'{annee}\''
    url = (config.AMELI_API + "/exports/csv?delimiter=%3B&select="
           + quote("annee,top,patho_niv1,patho_niv2,cla_age_5,region,dept,ntop,npop")
           + "&where=" + quote(where))
    # le cache est invalidé si le producteur a modifié le jeu depuis le dernier téléchargement
    ancien = lire_meta(dest).get("maj_source")
    telecharger(url, dest, "ameli", rafraichir or (bool(ancien) and ancien != maj), taille_min=10_000,
                extra_meta={"maj_source": maj, "annee": annee, "jeu_datagouv": config.AMELI_DATAGOUV})
    return dest


def charger(ref, hors_ligne=False, rafraichir=False):
    """Renvoie {"contexte": {"dep": DataFrame, "reg": DataFrame}, "defs": [...], "table": DataFrame} ou None."""
    try:
        chemin = _telecharger(hors_ligne, rafraichir)
        df = pd.read_csv(chemin, sep=";", dtype={"dept": str, "region": str, "top": str, "cla_age_5": str})
        df["ntop"] = pd.to_numeric(df["ntop"], errors="coerce")
        df["npop"] = pd.to_numeric(df["npop"], errors="coerce")
        df["dept"] = df["dept"].str.strip().str.zfill(2)
        df["region"] = df["region"].str.strip().str.zfill(2)
    except Exception as e:  # noqa: BLE001
        JOURNAL.note("Assurance Maladie, pathologies", "erreur", str(e)[:300])
        return None

    meta = lire_meta(chemin)
    # Mayotte relève d'un régime de sécurité sociale distinct, très partiellement couvert par ces données
    # (environ 130 000 assurés pour plus de 300 000 habitants). Ses valeurs ne sont pas comparables.
    exclus = df["dept"].isin(config.AMELI_DEPARTEMENTS_EXCLUS) | (
        (df["dept"] == "999") & df["region"].isin(config.AMELI_REGIONS_EXCLUES))
    if exclus.any():
        noms = {"976": "Mayotte"}
        JOURNAL.controle("Assurance Maladie, départements exclus (couverture non comparable)",
                         ", ".join(noms.get(c, c) for c in config.AMELI_DEPARTEMENTS_EXCLUS))
        df = df[~exclus]
    ages = sorted(a for a in df["cla_age_5"].unique() if a != "tsage")
    # dept 999 désigne les totaux régionaux officiels, region 99 la France entière
    france = (df["dept"] == "999") & (df["region"] == "99")
    regions = (df["dept"] == "999") & (df["region"] != "99")
    lignes, ctx = [], {"dep": {}, "reg": {}}
    for top, iid, lab, _expl in config.AMELI_INDICATEURS:
        d = df[df["top"] == top]
        if d.empty:
            continue
        ref_age = d[france[d.index] & (d["cla_age_5"] != "tsage")].set_index("cla_age_5")["npop"].reindex(ages)
        for niv, cle, masque in [("dep", "dept", df["dept"] != "999"), ("reg", "region", regions)]:
            x = d[masque[d.index]]
            tot = x[x["cla_age_5"] == "tsage"].groupby(cle)[["ntop", "npop"]].sum(min_count=1)
            par_age = x[x["cla_age_5"] != "tsage"]
            cas = par_age.pivot_table(index=cle, columns="cla_age_5", values="ntop", aggfunc="sum").reindex(columns=ages)
            pop = par_age.pivot_table(index=cle, columns="cla_age_5", values="npop", aggfunc="sum").reindex(columns=ages)
            cas, pop = cas.reindex(tot.index), pop.reindex(tot.index)
            couverture = cas.sum(axis=1) / tot["ntop"]
            std = pd.Series(standardisation_directe(cas.to_numpy(), pop.to_numpy(), ref_age.to_numpy()),
                            index=tot.index) * 100
            std[(couverture < config.AMELI_COUVERTURE_MIN) | tot["ntop"].isna()] = np.nan
            brut = tot["ntop"] / tot["npop"] * 100
            ctx[niv][iid] = std
            lignes.append(pd.DataFrame({"niveau": niv, "code": tot.index, "indicateur": iid, "top": top,
                                        "libelle_officiel": (d["patho_niv2"].dropna().tolist() or d["patho_niv1"].dropna().tolist() or [top])[0],
                                        "patients": tot["ntop"].to_numpy(), "population": tot["npop"].to_numpy(),
                                        "prevalence_brute_pct": brut.to_numpy(), "prevalence_standardisee_pct": std.to_numpy(),
                                        "couverture_ages": couverture.to_numpy()}))
    if not lignes:
        JOURNAL.note("Assurance Maladie, pathologies", "erreur", "aucune ligne lue")
        return None
    table = pd.concat(lignes, ignore_index=True)
    out = {niv: pd.DataFrame(v) for niv, v in ctx.items()}
    defs = [{"id": iid, "libelle": lab, "unite": "% standardisé sur l'âge", "explication": expl + " Prévalence "
             "standardisée sur la structure d'âge de la France, pour comparer des départements plus ou moins âgés. "
             "Mesure le recours aux soins, pas le besoin.", "source": SOURCE, "famille": FAMILLE,
             "licence": config.AMELI_LICENCE, "niveau_origine": "dep"} for _t, iid, lab, expl in config.AMELI_INDICATEURS
            if iid in out["dep"]]
    manq = table[(table["niveau"] == "dep") & table["prevalence_standardisee_pct"].isna()]
    JOURNAL.note("Assurance Maladie, pathologies", "ok",
                 f"année {meta.get('annee', '')}, {len(defs)} indicateurs, {table.loc[table['niveau'] == 'dep', 'code'].nunique()} départements",
                 url=meta.get("url", "")[:200], date_donnees=(meta.get("maj_source") or "")[:10], lignes=len(df))
    JOURNAL.controle("Assurance Maladie, valeurs standardisées non calculées (secret statistique trop important)",
                     f"{len(manq)} sur {int((table['niveau'] == 'dep').sum())}")
    log.info("Assurance Maladie, %d indicateurs chargés", len(defs))
    return {"contexte": out, "defs": defs, "table": table, "annee": meta.get("annee")}
