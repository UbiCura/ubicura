"""DREES, accessibilité potentielle localisée (APL) aux professionnels de santé (Licence Ouverte).

L'APL est l'indicateur officiel d'accessibilité, calculé par commune pour les médecins généralistes, les
infirmiers, les masseurs-kinésithérapeutes, les sages-femmes et les chirurgiens-dentistes. Il tient compte des
temps de trajet par la route, de l'activité de chaque professionnel et des besoins liés à l'âge. Il n'existe pas
pour les psychologues ni pour les psychiatres. Il sert ici à vérifier que l'accessibilité calculée par le
programme, plus sommaire, classe les territoires de la même façon pour les professions où les deux existent.

Les classeurs sont listés par l'API Opendatasoft de la DREES, aucune adresse n'est écrite en dur. La date de
mise à jour de chaque pièce jointe (en-tête Last-Modified) est consignée pour la future tâche planifiée."""
from __future__ import annotations

import re

import pandas as pd

from .. import config
from ..util import JOURNAL, _session, date_version, get_json, lire_meta, log, norm, telecharger

SOURCE = "DREES, accessibilité potentielle localisée (APL) aux professionnels de santé"
LIBELLES = {"medecin_generaliste": "médecins généralistes", "infirmier": "infirmiers",
            "masseur_kinesitherapeute": "masseurs-kinésithérapeutes", "sage_femme": "sages-femmes",
            "chirurgien_dentiste": "chirurgiens-dentistes"}


def _pieces_jointes():
    pj = get_json(config.APL_API + "/attachments").get("attachments", [])
    out = {}
    for motif, prof in config.APL_PROFESSIONS:
        cand = [a["metas"] for a in pj if re.search(motif, norm(a["metas"].get("title", "")))
                and norm(a["metas"].get("title", "")).endswith("xlsx")]
        if cand:
            # la pièce jointe la plus récente l'emporte (l'ancienne nomenclature reste en ligne)
            s = _session()
            dates = {c["id"]: s.head(c["url"], timeout=60, allow_redirects=True).headers.get("Last-Modified", "")
                     for c in cand}
            c = max(cand, key=lambda c: pd.to_datetime(dates[c["id"]] or "1900", utc=True))
            out[prof] = (c["url"], dates[c["id"]], c.get("title", ""))
    return out


def _lire(chemin):
    """Dernière feuille « APL AAAA » d'un classeur, ligne d'en-tête repérée par « Code commune »."""
    feuilles = pd.read_excel(chemin, sheet_name=None, header=None, dtype=str)
    annees = {int(m.group(1)): k for k in feuilles if (m := re.search(r"apl (\d{4})", norm(k)))}
    if not annees:
        raise ValueError("aucune feuille de millésime")
    annee = max(annees)
    x = feuilles[annees[annee]]
    entete = next(i for i in range(min(40, len(x))) if norm(x.iat[i, 0]).startswith("code commune"))
    cols = [str(v) for v in x.iloc[entete]]
    unite = x.iloc[entete + 1]
    c_apl = next(j for j, c in enumerate(cols) if norm(c).startswith("apl aux") and "ans ou moins" not in norm(c))
    c_pop = next(j for j, c in enumerate(cols) if norm(c).startswith("population totale"))
    d = x.iloc[entete + 2:, [0, c_apl, c_pop]].copy()
    d.columns = ["code", "apl", "population"]
    d = d[d["code"].notna() & d["code"].str.match(r"^\w{5}$")]
    d["apl"] = pd.to_numeric(d["apl"], errors="coerce")
    d["population"] = pd.to_numeric(d["population"], errors="coerce")
    return d, annee, str(unite.iloc[c_apl]).strip()


def charger(ref, hors_ligne=False, rafraichir=False):
    """Renvoie {"communes": DataFrame(code, prof, apl, population), "defs": {prof: {...}}} ou None."""
    tables, defs = [], {}
    try:
        pj = None if hors_ligne else _pieces_jointes()
        for _motif, prof in config.APL_PROFESSIONS:
            dest = config.BRUT / f"apl_{prof}.xlsx"
            if pj is not None:
                if prof not in pj:
                    JOURNAL.note(f"DREES, APL {prof}", "absent", "pièce jointe introuvable")
                    continue
                url, maj, titre = pj[prof]
                ancien = lire_meta(dest).get("maj_source")
                telecharger(url, dest, "apl", rafraichir or (bool(ancien) and ancien != maj),
                            extra_meta={"maj_source": maj, "titre": titre})
            elif not dest.exists():
                continue
            d, annee, unite = _lire(dest)
            d["code"] = d["code"].map(ref.anciens).fillna(d["code"])
            d = d.assign(ap=d["apl"] * d["population"]).groupby("code", as_index=False).agg(
                population=("population", "sum"), ap=("ap", "sum"))
            d["apl"] = d["ap"] / d["population"]
            d["prof"] = prof
            tables.append(d.drop(columns="ap"))
            defs[prof] = {"annee": annee, "unite": unite, "maj_source": lire_meta(dest).get("maj_source", "")}
            log.info("APL %s, millésime %s, %d communes", prof, annee, len(d))
    except Exception as e:  # noqa: BLE001
        JOURNAL.note("DREES, accessibilité potentielle localisée", "erreur", str(e)[:300])
        return None
    if not tables:
        JOURNAL.note("DREES, accessibilité potentielle localisée", "absent", "aucun classeur lu")
        return None
    t = pd.concat(tables, ignore_index=True)
    connues = set(ref.communes["code"])
    JOURNAL.controle("APL de la DREES, communes rattachées au référentiel", f"{t['code'].isin(connues).mean():.1%}")
    JOURNAL.note("DREES, accessibilité potentielle localisée", "ok",
                 ", ".join(f"{LIBELLES.get(p, p)} {v['annee']}" for p, v in defs.items())
                 + ". Pour les médecins généralistes, l'indicateur tous âges est utilisé, la DREES met en avant celui des "
                 "65 ans ou moins (3,3 consultations par habitant en 2024).",
                 url="https://data.drees.solidarites-sante.gouv.fr/explore/dataset/530_l-accessibilite-potentielle-localisee-apl/",
                 lignes=len(t), date_donnees=max((date_version(v) for v in defs.values()), default=""))
    return {"communes": t, "defs": defs}
