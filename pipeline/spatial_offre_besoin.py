"""Analyses spatiales de l'audit du 4 octobre 2026, ajoutées le 8 octobre (accord de Lucas).

1. Moran local bivarié (point 2.5). Pour chaque département, l'indicateur de besoin du département est rapproché de
   l'offre moyenne de ses voisins. Il repère des zones où un indicateur élevé est entouré d'une offre faible, ou
   l'inverse, au-delà du hasard (permutations conditionnelles, correction de Benjamini-Hochberg).
2. Régression géographiquement pondérée (point 2.6). Le lien entre le niveau de vie et la densité d'une profession
   est estimé localement, intercommunalité par intercommunalité, avec ses voisines les plus proches (noyau bicarré
   adaptatif, nombre de voisines choisi par le critère AICc). Un test par permutations des positions dit si le lien
   varie vraiment d'une région à l'autre. Méthode de Fotheringham, Brunsdon et Charlton (2002), seuil des tests
   locaux ajusté selon da Silva et Fotheringham (2016).

Analyses écologiques, elles décrivent des territoires et ne disent rien d'une cause."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import config
from .analyses import benjamini_hochberg, tables
from .util import JOURNAL, log

ZONES_BIVARIEES = {"HL": "indicateur élevé, offre faible alentour", "HH": "indicateur élevé, offre élevée alentour",
                   "LL": "indicateur bas, offre faible alentour", "LH": "indicateur bas, offre élevée alentour"}


# ---------------------------------------------------------------- Moran local bivarié
def moran_bivarie(x: pd.Series, y: pd.Series, voisins: dict, permutations=999, rng=None) -> pd.DataFrame:
    """Moran local bivarié, I_i = z_x(i) fois la moyenne de z_y sur les voisins de i (poids normalisés par ligne).
    p-valeur par permutations conditionnelles (les valeurs de y des autres territoires sont tirées au hasard).
    Renvoie code, I, p, type (x du territoire haut ou bas, y des voisins haut ou bas)."""
    d = pd.DataFrame({"x": x, "y": y}).dropna()
    codes = [c for c in d.index if c in voisins and any(v in d.index for v in voisins[c])]
    if len(codes) < 10:
        return pd.DataFrame(columns=["code", "I", "p", "type"])
    d = d.loc[codes]
    zx = ((d["x"] - d["x"].mean()) / d["x"].std(ddof=0)).to_numpy()
    zy = ((d["y"] - d["y"].mean()) / d["y"].std(ddof=0)).to_numpy()
    pos = {c: i for i, c in enumerate(codes)}
    rng = rng or np.random.default_rng(config.GRAINE)
    n, out = len(codes), []
    for i, c in enumerate(codes):
        vs = [pos[v] for v in voisins[c] if v in pos]
        lag = zy[vs].mean()
        I = zx[i] * lag
        autres = np.delete(np.arange(n), i)
        tirages = np.array([rng.choice(autres, size=len(vs), replace=False) for _ in range(permutations)])
        sim = zx[i] * zy[tirages].mean(axis=1)
        p = (np.sum(np.abs(sim) >= abs(I)) + 1) / (permutations + 1)
        out.append((c, I, p, ("H" if zx[i] > 0 else "L") + ("H" if lag > 0 else "L")))
    return pd.DataFrame(out, columns=["code", "I", "p", "type"])


def offre_besoin(agg, ref, ctx, voisins, rng) -> pd.DataFrame | None:
    """Moran local bivarié par département, indicateur de besoin du département et densité moyenne des voisins,
    pour les principales professions de santé mentale (config.PROFESSIONS_QUADRANTS)."""
    if not voisins or "dep" not in voisins or ctx is None or "dep" not in ctx:
        return None
    n, dens, pop = tables(agg, ref, "dep", "all")
    c = ctx["dep"].reindex(dens.index).drop(index=config.DEPARTEMENTS_EXCLUS_CROISEMENTS, errors="ignore")
    out = []
    for p in [p for p in config.PROFESSIONS_QUADRANTS if p in dens]:
        for v in [v for v in config.LOI_INVERSE_BESOINS if v in c]:
            r = moran_bivarie(c[v], np.log1p(dens[p]).reindex(c.index), voisins["dep"], rng=rng)
            if r.empty:
                continue
            r["q"] = benjamini_hochberg(r["p"].to_numpy())
            r["zone"] = np.where(r["q"] < .05, r["type"], "non_significatif")
            r.insert(0, "variable", v)
            r.insert(0, "prof", p)
            out.append(r)
    if not out:
        return None
    t = pd.concat(out, ignore_index=True)
    x = t[(t["prof"] == "psychiatre") & (t["variable"] == "suicides")]
    JOURNAL.controle("Moran local bivarié, suicides et psychiatres des départements voisins",
                     (f"aucune zone au-delà du hasard sur {len(x)} départements" if not (x["zone"] != "non_significatif").any()
                      else f"{int((x['zone'] == 'HL').sum())} départements où un taux élevé est entouré d'une offre faible, "
                           f"{int((x['zone'] != 'non_significatif').sum())} zones au-delà du hasard sur {len(x)} départements"))
    return t


# ---------------------------------------------------------------- régression géographiquement pondérée
def _poids(dist: np.ndarray, k: int) -> np.ndarray:
    """Noyau bicarré adaptatif, la k-ième distance de chaque ligne sert de portée (poids nul au-delà)."""
    h = np.partition(dist, k - 1, axis=1)[:, k - 1][:, None]
    u = dist / np.where(h > 0, h, 1e-9)
    return np.where(u < 1, (1 - u ** 2) ** 2, 0.0)


def _ajuster(y, X, W):
    """Coefficients locaux, résidus, trace de la matrice chapeau et erreurs types locales pour des poids W."""
    XtWX = np.einsum("ij,jk,jl->ikl", W, X, X)
    XtWy = np.einsum("ij,jk,j->ik", W, X, y)
    inv = np.linalg.inv(XtWX)
    beta = np.einsum("ikl,il->ik", inv, XtWy)
    yhat = np.einsum("ik,ik->i", X, beta)
    # diagonale de la matrice chapeau, h_ii = x_i (X'W_iX)^-1 x_i' w_ii
    h = np.einsum("ik,ikl,il->i", X, inv, X) * np.diag(W)
    res = y - yhat
    return beta, res, h, inv


def _aicc(y, res, h):
    n, tr = len(y), h.sum()
    s2 = (res ** 2).sum() / n
    return n * np.log(s2) + n * np.log(2 * np.pi) + n * (n + tr) / (n - 2 - tr)


def gwr(y: np.ndarray, X: np.ndarray, coords: np.ndarray, k: int | None = None, rng=None, permutations=49) -> dict:
    """Régression géographiquement pondérée. y (n), X (n, p) sans constante, coords (n, 2) en kilomètres.
    Variables centrées et réduites, coefficients comparables entre eux. Renvoie les coefficients, erreurs types et
    t locaux, le nombre de voisines retenu, le nombre effectif de paramètres (ENP), l'AICc, le R² global et local,
    le seuil ajusté des tests locaux et, pour chaque variable, la p-valeur du test de variation spatiale."""
    y = (y - y.mean()) / y.std()
    X = (X - X.mean(axis=0)) / X.std(axis=0)
    Xc = np.column_stack([np.ones(len(y)), X])
    n, p = Xc.shape
    dist = np.sqrt(((coords[:, None, :] - coords[None, :, :]) ** 2).sum(-1))

    def critere(kk):
        b, r, h, _i = _ajuster(y, Xc, _poids(dist, kk))
        return _aicc(y, r, h)
    if k is None:
        # recherche par section dorée du nombre de voisines, entre 2p + 10 et n
        a, b = max(2 * p + 10, 20), n
        g = (np.sqrt(5) - 1) / 2
        c1, c2 = int(round(b - g * (b - a))), int(round(a + g * (b - a)))
        f1, f2 = critere(c1), critere(c2)
        while b - a > 4:
            if f1 < f2:
                b, c2, f2 = c2, c1, f1
                c1 = int(round(b - g * (b - a)))
                f1 = critere(c1)
            else:
                a, c1, f1 = c1, c2, f2
                c2 = int(round(a + g * (b - a)))
                f2 = critere(c2)
        k = min(range(a, b + 1), key=critere)
    W = _poids(dist, k)
    beta, res, h, inv = _ajuster(y, Xc, W)
    enp = h.sum()
    s2 = (res ** 2).sum() / (n - 2 * enp + (h ** 2).sum())
    # erreurs types locales, var(beta_i) = C C' s², C = (X'W_iX)^-1 X'W_i
    C = np.einsum("ikl,jl,ij->ikj", inv, Xc, W)
    se = np.sqrt(np.einsum("ikj,ikj->ik", C, C) * s2)
    t = beta / se
    alpha = .05 / (enp / p)   # da Silva et Fotheringham (2016)
    seuil = stats.t.ppf(1 - alpha / 2, n - enp)
    # R² local, pondéré par les poids de chaque régression locale
    yb = (W * y).sum(1) / W.sum(1)
    tss = (W * (y[None, :] - yb[:, None]) ** 2).sum(1)
    rl = y[None, :] - np.einsum("ik,jk->ij", beta, Xc)
    r2_local = 1 - (W * rl ** 2).sum(1) / tss
    r2 = 1 - (res ** 2).sum() / ((y - y.mean()) ** 2).sum()
    # test de variation spatiale, écart-type des coefficients locaux comparé à celui obtenu en mélangeant les
    # positions (Fotheringham et al. 2002, 9.8), à nombre de voisines constant
    rng = rng or np.random.default_rng(config.GRAINE)
    ecarts = beta[:, 1:].std(axis=0)
    plus = np.zeros(p - 1)
    for _ in range(permutations):
        o = rng.permutation(n)
        b2, *_r = _ajuster(y[o], Xc[o], W)
        plus += b2[:, 1:].std(axis=0) >= ecarts
    p_var = (plus + 1) / (permutations + 1)
    return {"beta": beta, "se": se, "t": t, "k": int(k), "enp": float(enp), "aicc": float(_aicc(y, res, h)),
            "r2": float(r2), "r2_local": r2_local, "seuil_t": float(seuil), "alpha": float(alpha), "p_variation": p_var}


def ols_aicc(y, X):
    """AICc de la régression ordinaire sur les mêmes variables centrées et réduites, pour comparaison."""
    y = (y - y.mean()) / y.std()
    X = (X - X.mean(axis=0)) / X.std(axis=0)
    Xc = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(Xc, y, rcond=None)
    res = y - Xc @ beta
    n, p = Xc.shape
    s2 = (res ** 2).sum() / n
    return float(n * np.log(s2) + n * np.log(2 * np.pi) + n * (n + p + 1) / (n - p - 3)), beta


def centres_epci(ref, voisins) -> pd.DataFrame | None:
    """Centre de chaque intercommunalité de l'Hexagone, moyenne des centres des communes pondérée par la population,
    en kilomètres (projection équirectangulaire autour de 46,5 degrés de latitude)."""
    cs = (voisins or {}).get("centres")
    if not cs:
        return None
    com = ref.communes.set_index("code")
    t = pd.DataFrame([(c, x, y) for c, (x, y) in cs.items()], columns=["code", "lon", "lat"]).set_index("code")
    t = t.join(com[["epci", "dep", "pop"]], how="inner")
    t = t[~t["dep"].astype(str).str.startswith("97") & t["epci"].notna()]
    t["kx"] = t["lon"] * 111.32 * np.cos(np.radians(46.5))
    t["ky"] = t["lat"] * 110.57
    w = t["pop"].clip(lower=1)
    g = t.assign(wx=t["kx"] * w, wy=t["ky"] * w, w=w).groupby("epci")[["wx", "wy", "w"]].sum()
    return pd.DataFrame({"cx": g["wx"] / g["w"], "cy": g["wy"] / g["w"]})


def professions_gwr(n_epci: pd.DataFrame, seuil: float | None = None) -> list[str]:
    """Professions retenues pour la régression géographiquement pondérée : celles présentes dans au moins une
    intercommunalité sur deux (config.GWR_PRESENCE_MIN). Pour une profession plus rare, la densité est nulle dans la
    plupart des intercommunalités et le lien local n'a pas de sens (demande de Lucas du 23 octobre 2026, ouvrir le
    calcul au-delà des trois professions d'origine). Psychologues, psychiatres et généralistes d'abord, puis l'ordre
    de config.PROFESSIONS."""
    seuil = config.GWR_PRESENCE_MIN if seuil is None else seuil
    ordre = ["psychologue", "psychiatre", "medecin_generaliste"] + [p[1] for p in config.PROFESSIONS]
    vus, sortie = set(), []
    for prof in ordre:
        if prof in vus or prof not in n_epci.columns:
            continue
        vus.add(prof)
        if (n_epci[prof] > 0).mean() >= seuil:
            sortie.append(prof)
    return sortie


def gwr_niveau_de_vie(agg, ref, ctx, voisins, rng):
    """Lien local entre le niveau de vie et la densité de chaque profession présente dans au moins une
    intercommunalité sur deux (professions_gwr), à densité de population égale, par intercommunalité de l'Hexagone."""
    if ctx is None or "epci" not in ctx:
        return None, None
    cen = centres_epci(ref, voisins)
    c = ctx["epci"]
    if cen is None or "revenu_median" not in c or "densite_pop" not in c:
        return None, None
    n, dens, pop = tables(agg, ref, "epci", "all")
    coef, resume = [], []
    retenues = professions_gwr(n)
    JOURNAL.controle("Régression géographiquement pondérée, professions retenues (présentes dans au moins "
                     f"{config.GWR_PRESENCE_MIN:.0%} des intercommunalités)".replace("%", " %"), f"{len(retenues)}, {', '.join(retenues)}")
    for prof in [p for p in retenues if p in dens]:
        d = pd.DataFrame({"y": np.log1p(dens[prof]), "revenu": c["revenu_median"].reindex(dens.index),
                          "densite": np.log(c["densite_pop"].reindex(dens.index))}).join(cen, how="inner").dropna()
        if len(d) < 100:
            continue
        log.info("régression géographiquement pondérée, %s, %d intercommunalités", prof, len(d))
        X = d[["revenu", "densite"]].to_numpy(float)
        r = gwr(d["y"].to_numpy(float), X, d[["cx", "cy"]].to_numpy(float), rng=rng)
        a_ols, b_ols = ols_aicc(d["y"].to_numpy(float), X)
        sig = np.abs(r["t"][:, 1]) > r["seuil_t"]
        coef.append(pd.DataFrame({"prof": prof, "code": d.index, "coef_niveau_de_vie": r["beta"][:, 1],
                                  "erreur_std": r["se"][:, 1], "t": r["t"][:, 1], "net": sig,
                                  "coef_densite_pop": r["beta"][:, 2], "r2_local": r["r2_local"]}))
        b = r["beta"][:, 1]
        resume.append({"prof": prof, "intercommunalites": len(d), "voisines": r["k"], "parametres_effectifs": r["enp"],
                       "aicc_gwr": r["aicc"], "aicc_ols": a_ols, "r2_gwr": r["r2"], "coef_global_niveau_de_vie": b_ols[1],
                       "coef_local_q1": np.quantile(b, .25), "coef_local_mediane": np.median(b),
                       "coef_local_q3": np.quantile(b, .75), "part_positif_net": float((sig & (b > 0)).mean()),
                       "part_negatif_net": float((sig & (b < 0)).mean()), "seuil_t_ajuste": r["seuil_t"],
                       "p_variation_niveau_de_vie": float(r["p_variation"][0]),
                       "p_variation_densite_pop": float(r["p_variation"][1])})
    if not resume:
        return None, None
    res = pd.DataFrame(resume)
    x = res[res["prof"] == "psychologue"]
    if len(x):
        x = x.iloc[0]
        JOURNAL.controle("Régression géographiquement pondérée, psychologues et niveau de vie",
                         f"{int(x['voisines'])} voisines, AICc {x['aicc_gwr']:.0f} contre {x['aicc_ols']:.0f} en régression "
                         f"ordinaire, test de variation spatiale p = {x['p_variation_niveau_de_vie']:.2f}".replace(".", ","))
    return pd.concat(coef, ignore_index=True), res
