"""Croisement des indicateurs de santé mentale et de vulnérabilité entre eux, par département, sans les professionnels
(demande de Lucas du 8 octobre 2026).

Deux analyses. (1) Corrélation de rang entre chaque paire d'indicateurs (config.INDICATEURS_CROISES), avec intervalle
de confiance par bootstrap et correction de Benjamini-Hochberg. (2) Régression linéaire multiple de quelques indicateurs
de besoin (config.REGRESSION_RESULTATS) sur un petit jeu d'indicateurs sociaux (config.REGRESSION_EXPLICATIVES),
variables centrées et réduites, erreurs standard robustes (HC3), sur les départements de l'Hexagone, avec un contrôle sans
l'Île-de-France. Ce sont des analyses écologiques, elles décrivent des départements et ne disent rien d'une cause."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import config
from .lecture import minuscule
from .analyses import benjamini_hochberg, spearman_bootstrap
from .util import JOURNAL


def ols_robuste(y, X, noms):
    """Moindres carrés ordinaires sur des variables centrées et réduites, erreurs standard robustes HC3.
    Renvoie (coefficients, R², R² ajusté, n). Les coefficients sont standardisés, un écart-type de la variable
    explicative pour un écart-type de la variable expliquée."""
    y, X = np.asarray(y, float), np.asarray(X, float)
    m = ~(np.isnan(y) | np.isnan(X).any(1))
    y, X = y[m], X[m]
    n, k = X.shape
    ys = (y - y.mean()) / y.std()
    Xs = (X - X.mean(0)) / np.where(X.std(0) == 0, 1, X.std(0))
    Xc = np.column_stack([np.ones(n), Xs])
    XtX_inv = np.linalg.pinv(Xc.T @ Xc)
    beta = XtX_inv @ Xc.T @ ys
    e = ys - Xc @ beta
    h = np.einsum("ij,jk,ik->i", Xc, XtX_inv, Xc)
    meat = (Xc.T * (e / (1 - h)) ** 2) @ Xc
    se = np.sqrt(np.diag(XtX_inv @ meat @ XtX_inv))
    r2 = 1 - (e ** 2).sum() / ((ys - ys.mean()) ** 2).sum()
    r2a = 1 - (1 - r2) * (n - 1) / (n - k - 1)
    t = beta / se
    p = 2 * stats.t.sf(np.abs(t), n - k - 1)
    tc = stats.t.ppf(.975, n - k - 1)
    # facteur d'inflation de la variance, au-delà de 5 les variables explicatives se recouvrent trop
    vif = [1 / max(1 - _r2(Xs[:, j], np.delete(Xs, j, 1)), 1e-9) for j in range(k)]
    coefs = pd.DataFrame({"variable": noms, "coef_standardise": beta[1:], "ic95_bas": beta[1:] - tc * se[1:],
                          "ic95_haut": beta[1:] + tc * se[1:], "erreur_std": se[1:], "p": p[1:], "vif": vif})
    return coefs, r2, r2a, n


def dependances(y, X, noms):
    """Pour chaque variable explicative, l'autre variable sans laquelle son coefficient standardisé se rapproche le
    plus de zéro, et ce coefficient sans elle. Sert à repérer un effet de compensation (un lien qui n'apparaît
    qu'une fois une autre variable prise en compte). Renvoie {variable: (autre, coefficient sans l'autre)}."""
    y, X = np.asarray(y, float), np.asarray(X, float)
    m = ~(np.isnan(y) | np.isnan(X).any(1))
    y, X = y[m], X[m]
    ys = (y - y.mean()) / y.std()
    Xs = (X - X.mean(0)) / np.where(X.std(0) == 0, 1, X.std(0))

    def coefs(cols):
        Xc = np.column_stack([np.ones(len(ys)), Xs[:, cols]])
        return np.linalg.lstsq(Xc, ys, rcond=None)[0][1:]

    complet = coefs(list(range(len(noms))))
    sortie = {}
    for j, v in enumerate(noms):
        meilleur = None
        for w in range(len(noms)):
            if w == j:
                continue
            cols = [c for c in range(len(noms)) if c != w]
            b = coefs(cols)[cols.index(j)]
            # l'autre variable qui ramène le plus le coefficient vers zéro (ou le fait changer de signe)
            ecart = abs(b) if np.sign(b) == np.sign(complet[j]) else -abs(b)
            if meilleur is None or ecart < meilleur[2]:
                meilleur = (noms[w], b, ecart)
        sortie[v] = (meilleur[0], meilleur[1]) if meilleur else (None, np.nan)
    return sortie


def _r2(y, X):
    Xc = np.column_stack([np.ones(len(y)), X])
    b = np.linalg.lstsq(Xc, y, rcond=None)[0]
    e = y - Xc @ b
    return 1 - (e ** 2).sum() / ((y - y.mean()) ** 2).sum()


def _hexagone(c):
    return c[~c.index.isin(config.DEPS_DROM)]


def croiser(ctx, rng) -> pd.DataFrame | None:
    """Corrélation de rang entre chaque paire d'indicateurs, par département (Hexagone et outre-mer)."""
    if ctx is None or "dep" not in ctx:
        return None
    c = ctx["dep"]
    vs = [v for v in config.INDICATEURS_CROISES if v in c and c[v].notna().sum() > 30]
    out = []
    for i, a in enumerate(vs):
        for b in vs[i + 1:]:
            d = c[[a, b]].dropna()
            d = d[~d.index.isin(config.DEPARTEMENTS_EXCLUS_CROISEMENTS)]
            rho, p, lo, hi, k = spearman_bootstrap(d[a], d[b], config.BOOTSTRAP, rng)
            sans = d[~d.index.isin(config.DEPS_ILE_DE_FRANCE)]
            r_sans = stats.spearmanr(sans[a], sans[b])[0] if len(sans) > 20 else np.nan
            out.append({"variable_a": a, "variable_b": b, "departements": k, "rho": rho, "ic95_bas": lo,
                        "ic95_haut": hi, "p": p, "rho_sans_ile_de_france": r_sans})
    if not out:
        return None
    t = pd.DataFrame(out)
    t["q_bh"] = benjamini_hochberg(t["p"].to_numpy())
    nets = int(((t["ic95_bas"] > 0) | (t["ic95_haut"] < 0)).sum())
    JOURNAL.controle("Croisement des indicateurs de besoin, de recours et de conditions de vie entre eux",
                     f"{len(vs)} indicateurs, {len(t)} paires, {nets} liens dont la fourchette exclut zéro")
    return t


def _libelles() -> dict:
    """Libellés des indicateurs de contexte, pour des messages lisibles."""
    try:
        return {c[0]: c[1] for c in config.CONTEXTE + config.CONTEXTE_VULNERABILITE} | {
            "suicides": "Décès par suicide", "hospit_gestes_auto_infliges": "Hospitalisations pour geste auto-infligé",
            "ald_23": "Affections psychiatriques de longue durée (ALD 23)"}
    except Exception:  # noqa: BLE001
        return {}


def regressions(ctx) -> pd.DataFrame | None:
    """Régression de chaque indicateur de besoin sur les indicateurs sociaux, départements de l'Hexagone, avec et sans
    l'Île-de-France."""
    if ctx is None or "dep" not in ctx:
        return None
    c = _hexagone(ctx["dep"])
    expl = [v for v in config.REGRESSION_EXPLICATIVES if v in c]
    X = c[expl].copy()
    if "densite_pop" in X:
        X["densite_pop"] = np.log(X["densite_pop"])
    lignes = []
    for res in [r for r in config.REGRESSION_RESULTATS if r in c]:
        for champ, sel in (("hexagone", c.index), ("hexagone_sans_ile_de_france", c.index[~c.index.isin(config.DEPS_ILE_DE_FRANCE)])):
            co, r2, r2a, n = ols_robuste(c.loc[sel, res], X.loc[sel].to_numpy(float), expl)
            co["q_bh"] = benjamini_hochberg(co["p"].to_numpy())
            # lien simple (corrélation de rang) et indicateur sans lequel le coefficient se rapproche le plus de zéro
            co["rho_simple"] = [stats.spearmanr(c.loc[sel, res], X.loc[sel, v], nan_policy="omit")[0] for v in expl]
            dep = dependances(c.loc[sel, res], X.loc[sel].to_numpy(float), expl)
            co["depend_de"] = [dep[v][0] for v in expl]
            co["coef_sans_depend_de"] = [dep[v][1] for v in expl]
            lignes.append(co.assign(resultat=res, champ=champ, r2=r2, r2_ajuste=r2a, departements=n))
    if not lignes:
        return None
    t = pd.concat(lignes, ignore_index=True)[["resultat", "champ", "variable", "coef_standardise", "ic95_bas",
                                              "ic95_haut", "erreur_std", "p", "q_bh", "vif", "r2", "r2_ajuste",
                                              "departements", "rho_simple", "depend_de", "coef_sans_depend_de"]]
    lab = _libelles()
    for res, g in t[t["champ"] == "hexagone"].groupby("resultat"):
        nets = [minuscule(lab.get(v, v)) for v in g[(g["ic95_bas"] > 0) | (g["ic95_haut"] < 0)]["variable"]]
        JOURNAL.controle(f"Régression multiple, {minuscule(lab.get(res, res))}",
                         f"R² {g['r2'].iloc[0]:.2f}, {g['departements'].iloc[0]} départements, liens nets avec "
                         f"{', '.join(nets) or 'aucun indicateur'}, facteur d'inflation de la variance maximal "
                         f"{g['vif'].max():.1f}".replace(".", ","))
    return t
