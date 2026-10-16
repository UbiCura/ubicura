"""Analyses complémentaires des structures de soins (accord de Lucas du 15 octobre 2026), réglées par type dans config
pour servir aussi aux structures vérifiées plus tard.

1. Sensibilité au niveau de confirmation. Les résultats clés (nombre, distance des habitants, comparaison des
   départements, inégalités selon le niveau de vie) sont recalculés avec les seules structures confirmées par une
   source indépendante de FINESS et du ROR, et l'on dit si la conclusion change.
2. Double éloignement. Part des habitants qui vivent dans une intercommunalité sans professionnel déclaré et à plus de
   config.DOUBLE_ELOIGNEMENT_KM d'une structure du même champ (config.DOUBLE_ELOIGNEMENT).
3. Charge par CMP d'après la SAE. File active ambulatoire et psychiatres salariés en temps plein rapportés aux CMP que
   les établissements déclarent, par département et discipline, une seule source pour le numérateur et le dénominateur.
4. Zones d'éloignement contiguës. Moran local des distances médianes par intercommunalité, correction de
   Benjamini-Hochberg (config.LIEUX_ZONES).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .util import JOURNAL, log

# niveaux de confirmation indépendants de FINESS et du ROR (pipeline/confirmation.py). « examinee » (vérification à la
# main sans source officielle) n'en fait pas partie, par prudence.
CONFIRMES = {"etablissement", "source_publique", "has_sirene", "has", "sirene"}


def _confirmees(lieux: pd.DataFrame) -> pd.DataFrame:
    """Structures gardées pour l'analyse de sensibilité, celles des types qui ont un niveau de confirmation seulement si
    elles sont confirmées, toutes les autres telles quelles."""
    if "confirmation" not in lieux:
        return lieux
    a_niveau = set(lieux.loc[lieux["confirmation"].notna(), "type"])
    garde = ~lieux["type"].isin(a_niveau) | lieux["confirmation"].isin(CONFIRMES)
    return lieux[garde]


def _mediane(x, w):
    if w.sum() <= 0:
        return np.nan
    o = np.argsort(x)
    return float(x[o][np.searchsorted(np.cumsum(w[o]) / w.sum(), .5)])


def sensibilite(L: dict, ref, centres: dict | None, ctx_epci: pd.DataFrame | None, rng) -> pd.DataFrame | None:
    """Résultats clés avec toutes les structures et avec les seules structures confirmées (types de
    config.LIEUX_SENSIBILITE). Une ligne par mesure, avec la conclusion de chaque version."""
    if not L or not centres:
        return None
    from scipy import stats
    from . import lieux as lieux_mod
    x = L["lieux"]
    types = [t for t in config.LIEUX_SENSIBILITE if t in set(x["type"])]
    if not types or "confirmation" not in x:
        return None
    sous = _confirmees(x)
    d_tout = L["distances_communes"]
    d_conf = lieux_mod.distances(sous[sous["type"].isin(types)], ref, centres)
    com = ref.communes.set_index("code")
    pop = com["pop"].astype(float).reindex(d_tout.index).fillna(0).to_numpy()
    dep_c = com["dep"].reindex(d_tout.index)
    pop_dep = ref.deps.set_index("code")["pop"].astype(float)
    lignes = []
    lib = {t[0]: t[1] for t in config.LIEUX_TYPES}
    for t in types:
        n_t, n_c = int((x["type"] == t).sum()), int((sous["type"] == t).sum())
        lignes.append({"type": t, "mesure": "Nombre de structures, France", "toutes": n_t, "confirmees": n_c,
                       "conclusion_identique": True})
        a, b = d_tout[t].to_numpy(), d_conf[t].reindex(d_tout.index).to_numpy()
        ma, mb = _mediane(a, pop), _mediane(b, pop)
        pa, pb = float(pop[a > 20].sum() / pop.sum()), float(pop[b > 20].sum() / pop.sum())
        lignes.append({"type": t, "mesure": "Distance médiane des habitants (km), France", "toutes": ma,
                       "confirmees": mb, "conclusion_identique": abs(mb - ma) < 1})
        lignes.append({"type": t, "mesure": "Part des habitants à plus de 20 km", "toutes": pa, "confirmees": pb,
                       "conclusion_identique": abs(pb - pa) < .02})
        # rang des départements, structures pour 100 000 habitants et distance médiane
        c_t = x[x["type"] == t].groupby("dep").size().reindex(pop_dep.index).fillna(0) / pop_dep * 1e5
        c_c = sous[sous["type"] == t].groupby("dep").size().reindex(pop_dep.index).fillna(0) / pop_dep * 1e5
        rho = stats.spearmanr(c_t, c_c, nan_policy="omit")[0]
        lignes.append({"type": t, "mesure": "Classement des départements, structures pour 100 000 habitants "
                       "(corrélation de rang entre les deux versions)", "toutes": 1.0, "confirmees": float(rho),
                       "conclusion_identique": rho >= .9})
        md_t = pd.Series({d: _mediane(a[(dep_c == d).to_numpy()], pop[(dep_c == d).to_numpy()]) for d in pop_dep.index})
        md_c = pd.Series({d: _mediane(b[(dep_c == d).to_numpy()], pop[(dep_c == d).to_numpy()]) for d in pop_dep.index})
        rho_d = stats.spearmanr(md_t, md_c, nan_policy="omit")[0]
        lignes.append({"type": t, "mesure": "Classement des départements, distance médiane des habitants "
                       "(corrélation de rang entre les deux versions)", "toutes": 1.0, "confirmees": float(rho_d),
                       "conclusion_identique": rho_d >= .9})
    # inégalités selon le niveau de vie, indice de concentration des habitants-kilomètres
    if ctx_epci is not None and "revenu_median" in ctx_epci:
        L_conf = dict(L, lieux=sous, distances_communes=d_tout.assign(**{t: d_conf[t].reindex(d_tout.index) for t in types}))
        i_t = (L.get("inegalites") or {}).get("concentration")
        i_c = (lieux_mod.inegalites_distances(L_conf, ref, ctx_epci, rng) or {}).get("concentration")
        if isinstance(i_t, pd.DataFrame) and isinstance(i_c, pd.DataFrame) and len(i_t) and len(i_c):
            for t in types:
                a_, b_ = i_t[i_t["type"] == t], i_c[i_c["type"] == t]
                if a_.empty or b_.empty:
                    continue
                a_, b_ = a_.iloc[0], b_.iloc[0]
                sens = lambda r: "net" if (r["ic95_bas"] > 0 or r["ic95_haut"] < 0) else "pas net"  # noqa: E731
                lignes.append({"type": t, "mesure": "Éloignement selon le niveau de vie (indice de concentration)",
                               "toutes": float(a_["indice_concentration"]), "confirmees": float(b_["indice_concentration"]),
                               "conclusion_identique": sens(a_) == sens(b_)
                               and np.sign(a_["indice_concentration"]) == np.sign(b_["indice_concentration"])})
    out = pd.DataFrame(lignes)
    out.insert(1, "libelle_type", out["type"].map(lib))
    diff = out[~out["conclusion_identique"]]
    JOURNAL.controle("Sensibilité des résultats au niveau de confirmation des structures",
                     f"{len(out) - len(diff)} résultats sur {len(out)} gardent la même conclusion avec les seules "
                     f"structures confirmées" + (", à signaler, " + "; ".join(
                         f"{lib[r.type].split(',')[0]} {r.mesure.split(',')[0].lower()}" for r in diff.itertuples())
                         if len(diff) else ""))
    return out


def double_eloignement(agg, L: dict, ref) -> pd.DataFrame | None:
    """Pour chaque champ de config.DOUBLE_ELOIGNEMENT (professions, structures), part des habitants dont
    l'intercommunalité ne compte aucun de ces professionnels déclarés et dont la commune est à plus de
    config.DOUBLE_ELOIGNEMENT_KM de la plus proche de ces structures. France, régions et départements."""
    if not L or agg is None:
        return None
    from .analyses import tables
    dist = L["distances_communes"]
    n, _dens, _pop = tables(agg, ref, "epci", "all")
    com = ref.communes.set_index("code").reindex(dist.index)
    pop = com["pop"].astype(float).fillna(0)
    lignes = []
    for cle_, (profs, types, lib) in config.DOUBLE_ELOIGNEMENT.items():
        profs = [p for p in profs if p in n]
        types = [t for t in types if t in dist]
        if not profs or not types:
            continue
        sans = (n[profs].sum(axis=1) == 0)
        sans_c = com["epci"].map(sans).fillna(False).astype(bool)
        loin_c = dist[types].min(axis=1) > config.DOUBLE_ELOIGNEMENT_KM
        for niv in ("fr", "reg", "dep"):
            grp = pd.Series("FR", index=dist.index) if niv == "fr" else com[niv]
            for code, idx in grp.groupby(grp).groups.items():
                w = pop.loc[idx]
                if w.sum() <= 0:
                    continue
                s_, l_ = sans_c.loc[idx], loin_c.loc[idx]
                lignes.append({"champ": cle_, "libelle": lib, "niveau": niv, "code": code, "population": w.sum(),
                               "part_sans_professionnel": float(w[s_].sum() / w.sum()),
                               "part_loin_structure": float(w[l_].sum() / w.sum()),
                               "part_double_eloignement": float(w[s_ & l_].sum() / w.sum()),
                               "habitants_double_eloignement": float(w[s_ & l_].sum())})
    out = pd.DataFrame(lignes)
    if len(out):
        noms = {"reg": ref.regs.set_index("code")["nom"], "dep": ref.deps.set_index("code")["nom"]}             if "nom" in ref.regs and "nom" in ref.deps else {}
        out["nom"] = [noms[n].get(c, c) if n in noms else "France" for n, c in zip(out["niveau"], out["code"])]
        fr = out[out["niveau"] == "fr"]
        JOURNAL.controle("Double éloignement (aucun professionnel déclaré dans l'intercommunalité et structure à plus "
                         f"de {config.DOUBLE_ELOIGNEMENT_KM} km)",
                         ", ".join(f"{r.libelle} {r.part_double_eloignement:.1%}".replace(".", ",")
                                   for r in fr.itertuples()))
    return out


def charge_cmp(sae: dict | None, ref) -> pd.DataFrame | None:
    """File active ambulatoire et psychiatres salariés en temps plein par CMP déclaré à la SAE, par département (du
    siège de l'établissement), région et France, adultes (psychiatrie générale) et enfants (infanto-juvénile)."""
    if not sae or not isinstance(sae.get("charge_disciplines"), pd.DataFrame):
        return None
    c = sae["charge_disciplines"].copy()
    dep_reg = ref.deps.set_index("code")["reg"]
    c["reg"] = c["dep"].map(dep_reg)
    lignes = []
    for niv in ("fr", "reg", "dep"):
        g = c.assign(code="FR" if niv == "fr" else c[niv])
        s = g.groupby(["code", "DIS"])[["FIL_AMB", "NB_CMP_SEUL", "ETPSAL_PKT"]].sum(min_count=1).reset_index()
        for r in s.itertuples():
            ncmp = r.NB_CMP_SEUL
            lignes.append({"niveau": niv, "code": r.code, "public": {"GEN": "adultes", "INF": "enfants"}.get(r.DIS, r.DIS),
                           "cmp_sae": ncmp, "file_active_ambulatoire": r.FIL_AMB, "etp_psychiatres": r.ETPSAL_PKT,
                           "patients_par_cmp": r.FIL_AMB / ncmp if ncmp and ncmp > 0 else np.nan,
                           "etp_psychiatres_par_cmp": r.ETPSAL_PKT / ncmp if ncmp and ncmp > 0 else np.nan})
    out = pd.DataFrame(lignes)
    fr = out[out["niveau"] == "fr"]
    JOURNAL.controle("Charge par CMP déclaré à la SAE (file active ambulatoire, psychiatres en temps plein)",
                     ", ".join(f"{r.public} {r.patients_par_cmp:,.0f} patients et {r.etp_psychiatres_par_cmp:.1f} ETP "
                               f"de psychiatres par CMP".replace(",", " ").replace(".", ",") for r in fr.itertuples()))
    return out


def zones_eloignement(ctx_epci: pd.DataFrame | None, voisins: dict | None, rng=None) -> pd.DataFrame | None:
    """Zones où l'éloignement se concentre. Moran global et local des distances médianes des habitants à la structure
    la plus proche, par intercommunalité (types de config.LIEUX_ZONES), Benjamini-Hochberg par type."""
    if ctx_epci is None or not voisins or "epci" not in voisins:
        return None
    from .analyses import benjamini_hochberg, moran, moran_local
    out = []
    for t in config.LIEUX_ZONES:
        col = f"dist_{t}"
        if col not in ctx_epci:
            continue
        v = np.log1p(ctx_epci[col].dropna())
        r = moran_local(v, voisins["epci"])
        if r.empty:
            continue
        I, p = moran(v, voisins["epci"], rng=rng)
        r["q"] = benjamini_hochberg(r["p"])
        r["zone"] = np.where(r["q"] < .05, r["type"].map({"HH": "eloignement_groupe", "LL": "proximite_groupee",
                                                           "HL": "eloigne_isole", "LH": "proche_isole"}),
                             "non_significatif")
        r.insert(0, "type_structure", t)
        r["distance_mediane_km"] = r["code"].map(ctx_epci[col])
        r["moran_global"], r["p_moran_global"] = I, p
        out.append(r)
    if not out:
        return None
    z = pd.concat(out, ignore_index=True)
    lib = {x[0]: x[1] for x in config.LIEUX_TYPES}
    JOURNAL.controle("Zones d'éloignement contiguës (Moran local des distances, Benjamini-Hochberg)",
                     ", ".join(f"{lib[t].split(',')[0]} {int((g['zone'] == 'eloignement_groupe').sum())} "
                               f"intercommunalités, Moran global {g['moran_global'].iloc[0]:.2f}".replace(".", ",")
                               for t, g in z.groupby("type_structure")))
    return z


def appliquer_tout(L: dict, ref, centres, ctx: dict | None, voisins, sae, rng) -> None:
    """Calcule et range dans L les analyses qui ne dépendent pas des effectifs (sensibilité, charge, zones)."""
    if not L:
        return
    ctx_epci = (ctx or {}).get("epci")
    for cle_, f in (("sensibilite", lambda: sensibilite(L, ref, centres, ctx_epci, rng)),
                    ("charge_cmp", lambda: charge_cmp(sae, ref)),
                    ("zones_eloignement", lambda: zones_eloignement(ctx_epci, voisins, rng))):
        try:
            L[cle_] = f()
        except Exception as e:  # noqa: BLE001
            log.exception("analyse des structures, %s", cle_)
            JOURNAL.note(f"Structures de soins, {cle_}", "erreur", str(e)[:300])
