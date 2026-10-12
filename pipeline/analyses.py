"""Analyses statistiques. Toutes portent sur des territoires (analyse écologique) et sur un
recensement exhaustif, les p-valeurs sont donc indicatives et toujours accompagnées d'une taille
d'effet. Les tests multiples sont corrigés par Benjamini-Hochberg."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import cdist

from . import config
from .util import JOURNAL, log

CLASSES_DENSITE = [(0, 25, "Très peu dense (moins de 25 hab./km²)"), (25, 100, "Peu dense (25 à 100)"),
                   (100, 300, "Intermédiaire (100 à 300)"), (300, np.inf, "Dense (plus de 300)")]


# ---------------------------------------------------------------- tables de base
def moyenne_territoires(effectifs, prof, population, mode="all"):
    """Densité de référence d'un niveau de territoires pour 10 000 habitants. Somme des effectifs des territoires
    (code, prof, mode, n) rapportée à la population totale, c'est-à-dire la moyenne des densités des territoires
    pondérée par leur population. Les territoires sont comparés à elle, et non au chiffre national, qui compte en
    plus les activités sans lieu et sans soins à la population (décision de Lucas du 5 octobre 2026)."""
    if effectifs is None or not population:
        return float("nan")
    n = effectifs.loc[(effectifs["prof"] == prof) & (effectifs["mode"] == mode), "n"].sum()
    return n / population * 1e4


def tables(agg, ref, niveau, mode="all"):
    """Effectifs et densités pour 10 000 habitants, une ligne par territoire, une colonne par profession."""
    base = {"com": ref.communes, "epci": ref.epci, "dep": ref.deps, "reg": ref.regs}[niveau].set_index("code")
    e = agg.effectifs[niveau]
    e = e[e["mode"] == mode].pivot_table(index="code", columns="prof", values="n", aggfunc="sum", fill_value=0)
    n = e.reindex(base.index).fillna(0).astype(int)
    pop = base["pop"].astype(float)
    ok = pop > 0
    dens = n[ok].div(pop[ok], axis=0) * 1e4
    return n[ok], dens, pop[ok]


# ---------------------------------------------------------------- outils statistiques
def benjamini_hochberg(p):
    p = np.asarray(p, float)
    q = np.full_like(p, np.nan)
    m = ~np.isnan(p)
    if not m.any():
        return q
    pv = p[m]
    ordre = np.argsort(pv)
    r = pv[ordre] * len(pv) / (np.arange(len(pv)) + 1)
    r = np.minimum.accumulate(r[::-1])[::-1]
    out = np.empty_like(pv)
    out[ordre] = np.minimum(r, 1)
    q[m] = out
    return q


def lorenz(n, pop, points=None):
    """Courbe de Lorenz de la répartition des professionnels rapportée à la population."""
    n, pop = np.asarray(n, float), np.asarray(pop, float)
    ordre = np.argsort(n / pop)
    x = np.concatenate([[0], np.cumsum(pop[ordre]) / pop.sum()])
    y = np.concatenate([[0], np.cumsum(n[ordre]) / max(n.sum(), 1e-12)])
    gini = 1 - np.sum((x[1:] - x[:-1]) * (y[1:] + y[:-1]))
    if points:
        xs = np.linspace(0, 1, points)
        return gini, xs, np.interp(xs, x, y)
    return gini, x, y


def theil(n, pop):
    n, pop = np.asarray(n, float), np.asarray(pop, float)
    s, p = n / n.sum(), pop / pop.sum()
    m = s > 0
    return float(np.sum(s[m] * np.log(s[m] / p[m])))


def spearman_bootstrap(x, y, B, rng):
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = ~(np.isnan(x) | np.isnan(y))
    x, y = x[m], y[m]
    if len(x) < 8 or np.nanstd(x) == 0 or np.nanstd(y) == 0:
        return np.nan, np.nan, np.nan, np.nan, len(x)
    rho, p = stats.spearmanr(x, y)
    if B:
        idx = rng.integers(0, len(x), size=(B, len(x)))
        rx = stats.rankdata(x[idx], axis=1)
        ry = stats.rankdata(y[idx], axis=1)
        rx -= rx.mean(1, keepdims=True)
        ry -= ry.mean(1, keepdims=True)
        den = np.sqrt((rx ** 2).sum(1) * (ry ** 2).sum(1))
        bs = np.where(den > 0, (rx * ry).sum(1) / np.where(den > 0, den, 1), np.nan)
        lo, hi = np.nanpercentile(bs, [2.5, 97.5])
    else:
        lo = hi = np.nan
    return rho, p, lo, hi, len(x)


def _residus_rangs(r, rz):
    """Résidus des rangs r (une ligne par tirage) après régression linéaire sur les rangs rz."""
    r = r - r.mean(-1, keepdims=True)
    rz = rz - rz.mean(-1, keepdims=True)
    pente = (r * rz).sum(-1, keepdims=True) / (rz ** 2).sum(-1, keepdims=True)
    return r - pente * rz


def _corr_lignes(a, b):
    den = np.sqrt((a ** 2).sum(-1) * (b ** 2).sum(-1))
    return np.where(den > 0, (a * b).sum(-1) / np.where(den > 0, den, 1), np.nan)


def spearman_partiel_bootstrap(x, y, z, B, rng):
    """Corrélation partielle de rang entre x et y à z égal (z, en pratique la densité de population).
    Les rangs de x et de y sont corrigés de leur relation linéaire avec les rangs de z, puis corrélés.
    Renvoie rho partiel, p-valeur (test t à n-3 degrés de liberté), bornes à 95 % par bootstrap, n."""
    x, y, z = (np.asarray(v, float) for v in (x, y, z))
    m = ~(np.isnan(x) | np.isnan(y) | np.isnan(z))
    x, y, z = x[m], y[m], z[m]
    n = len(x)
    if n < 10 or np.nanstd(x) == 0 or np.nanstd(y) == 0 or np.nanstd(z) == 0:
        return np.nan, np.nan, np.nan, np.nan, n
    rx, ry, rz = (stats.rankdata(v) for v in (x, y, z))
    rho = float(_corr_lignes(_residus_rangs(rx, rz), _residus_rangs(ry, rz)))
    t = rho * np.sqrt((n - 3) / max(1 - rho ** 2, 1e-12))
    p = float(2 * stats.t.sf(abs(t), n - 3))
    lo = hi = np.nan
    if B:
        idx = rng.integers(0, n, size=(B, n))
        rxb, ryb, rzb = (stats.rankdata(v[idx], axis=1) for v in (x, y, z))
        bs = _corr_lignes(_residus_rangs(rxb, rzb), _residus_rangs(ryb, rzb))
        lo, hi = np.nanpercentile(bs, [2.5, 97.5])
    return rho, p, lo, hi, n


def indice_concentration(n, pop, rang):
    """Indice de concentration des professionnels selon un classement des territoires (par exemple le
    niveau de vie, du plus modeste au plus aisé). Territoires triés selon le rang, part cumulée de la
    population en abscisse, part cumulée des professionnels en ordonnée. L'indice vaut 1 moins deux fois
    l'aire sous la courbe. Il est nul si les professionnels suivent la population, positif s'ils sont
    concentrés dans les territoires aisés, négatif s'ils le sont dans les territoires modestes."""
    n, pop, rang = (np.asarray(v, float) for v in (n, pop, rang))
    o = np.argsort(rang, kind="mergesort")
    x = np.concatenate([[0], np.cumsum(pop[o]) / pop.sum()])
    y = np.concatenate([[0], np.cumsum(n[o]) / max(n.sum(), 1e-12)])
    return float(1 - np.sum((x[1:] - x[:-1]) * (y[1:] + y[:-1]))), x, y


def deciles_population(valeur, pop, k=10):
    """Classe chaque territoire dans un décile de la valeur (1 = valeurs les plus faibles), pondéré par
    la population, de sorte que chaque décile réunisse environ un dixième des habitants."""
    valeur, pop = np.asarray(valeur, float), np.asarray(pop, float)
    o = np.argsort(valeur, kind="mergesort")
    cum = np.cumsum(pop[o]) - pop[o] / 2
    d = np.empty(len(valeur), int)
    d[o] = np.minimum((cum / pop.sum() * k).astype(int) + 1, k)
    return d


def standardisation_directe(cas, pop, pop_ref):
    """Taux standardisé sur l'âge par la méthode directe. cas et pop sont des tableaux (territoires x
    âges), pop_ref la population de référence par âge. Les cases de cas manquantes (secret statistique)
    sont comptées comme nulles, la part qu'elles représentent est contrôlée par l'appelant."""
    cas, pop = np.nan_to_num(np.asarray(cas, float)), np.asarray(pop, float)
    w = np.asarray(pop_ref, float) / np.sum(pop_ref)
    with np.errstate(divide="ignore", invalid="ignore"):
        taux = np.where(pop > 0, cas / pop, 0.0)
    return taux @ w


def limites_entonnoir(pop, taux, niveaux=(.95, .998)):
    """Limites de Poisson d'un diagramme en entonnoir. Pour une population donnée et un taux de
    référence (professionnels par habitant), renvoie les effectifs bas et haut entre lesquels un
    territoire se situerait avec la probabilité indiquée si seul le hasard jouait."""
    mu = np.asarray(pop, float) * taux
    out = {}
    for nv in niveaux:
        a = (1 - nv) / 2
        out[nv] = (stats.poisson.ppf(a, mu), stats.poisson.ppf(1 - a, mu))
    return out


def pearson_pondere(x, y, w):
    m = ~(np.isnan(x) | np.isnan(y) | np.isnan(w))
    x, y, w = x[m], y[m], w[m]
    if len(x) < 8:
        return np.nan
    mx, my = np.average(x, weights=w), np.average(y, weights=w)
    cov = np.average((x - mx) * (y - my), weights=w)
    return cov / np.sqrt(np.average((x - mx) ** 2, weights=w) * np.average((y - my) ** 2, weights=w))


def ols_hc1(y, X, noms):
    """Moindres carrés avec erreurs standard robustes HC1. X sans constante (ajoutée ici)."""
    n, k = X.shape
    Xc = np.column_stack([np.ones(n), X])
    XtX_inv = np.linalg.pinv(Xc.T @ Xc)
    beta = XtX_inv @ Xc.T @ y
    res = y - Xc @ beta
    meat = (Xc * res[:, None] ** 2).T @ Xc
    V = XtX_inv @ meat @ XtX_inv * n / (n - k - 1)
    se = np.sqrt(np.diag(V))
    t = beta / se
    p = 2 * stats.norm.sf(np.abs(t))
    r2 = 1 - res.var() / y.var()
    vif = []
    for j in range(k):
        autres = np.delete(X, j, axis=1)
        if autres.shape[1] == 0:
            vif.append(1.0)
            continue
        Z = np.column_stack([np.ones(n), autres])
        b = np.linalg.lstsq(Z, X[:, j], rcond=None)[0]
        r2j = 1 - (X[:, j] - Z @ b).var() / X[:, j].var()
        vif.append(1 / max(1 - r2j, 1e-9))
    coefs = pd.DataFrame({"variable": ["constante"] + noms, "coef": beta, "erreur_std": se, "t": t, "p": p,
                          "vif": [np.nan] + vif})
    return coefs, Xc @ beta, r2


def moran(valeurs: pd.Series, voisins: dict, permutations=999, rng=None):
    codes = [c for c in valeurs.index if c in voisins and voisins[c]]
    if len(codes) < 10:
        return np.nan, np.nan
    pos = {c: i for i, c in enumerate(codes)}
    x = valeurs.loc[codes].to_numpy(float)
    z = x - x.mean()
    lignes, cols = [], []
    for c in codes:
        vs = [pos[v] for v in voisins[c] if v in pos]
        lignes += [pos[c]] * len(vs)
        cols += vs
    lignes, cols = np.array(lignes), np.array(cols)
    deg = np.bincount(lignes, minlength=len(codes)).astype(float)
    w = 1 / deg[lignes]

    def stat(zz):
        return (len(zz) / w.sum()) * np.sum(w * zz[lignes] * zz[cols]) / np.sum(zz ** 2)

    I = stat(z)
    rng = rng or np.random.default_rng(config.GRAINE)
    sim = np.array([stat(rng.permutation(z)) for _ in range(permutations)])
    p = (np.sum(np.abs(sim - sim.mean()) >= abs(I - sim.mean())) + 1) / (permutations + 1)
    return float(I), float(p)


def moran_local(valeurs: pd.Series, voisins: dict, permutations=0, rng=None):
    """Indice de Moran local (LISA) par territoire, poids normalisés par ligne. Renvoie un DataFrame
    code, I, z, p, type. Type HH (territoire élevé entouré de territoires élevés, concentration), LL (bas
    entouré de bas, désert), HL et LH (territoire qui contraste avec ses voisins).

    P-valeur par défaut analytique, approximation normale sous l'hypothèse de randomisation (Anselin 1995,
    espérance et variance exactes). Elle n'a pas de plancher, contrairement aux permutations, dont la plus
    petite p-valeur possible (1 / (permutations + 1)) empêche la correction de Benjamini-Hochberg d'aboutir
    sur un millier de territoires. Avec permutations > 0, p-valeur par permutations conditionnelles."""
    codes = [c for c in valeurs.index if c in voisins and any(v in valeurs.index for v in voisins[c])]
    if len(codes) < 10:
        return pd.DataFrame(columns=["code", "I", "z", "p", "type"])
    x = valeurs.loc[codes].to_numpy(float)
    z = (x - x.mean()) / x.std()
    n = len(codes)
    b2 = np.mean(z ** 4)   # m4 / m2², z ayant une variance égale à 1
    pos = {c: i for i, c in enumerate(codes)}
    rng = rng or np.random.default_rng(config.GRAINE)
    out = []
    for i, c in enumerate(codes):
        vs = [pos[v] for v in voisins[c] if v in pos]
        lag = z[vs].mean()
        I = z[i] * lag
        if permutations:
            tirages = rng.choice(np.delete(np.arange(n), i), size=(permutations, len(vs)))
            sim = z[i] * z[tirages].mean(axis=1)
            p, zi = (np.sum(np.abs(sim) >= abs(I)) + 1) / (permutations + 1), np.nan
        else:
            w2 = 1 / len(vs)   # somme des poids au carré, poids égaux à 1 / nombre de voisins
            esp = -1 / (n - 1)
            var = w2 * (n - b2) / (n - 1) + (1 - w2) * (2 * b2 - n) / ((n - 1) * (n - 2)) - esp ** 2
            zi = (I - esp) / np.sqrt(var) if var > 0 else np.nan
            p = 2 * stats.norm.sf(abs(zi)) if np.isfinite(zi) else np.nan
        typ = ("H" if z[i] > 0 else "L") + ("H" if lag > 0 else "L")
        out.append((c, I, zi, p, typ))
    return pd.DataFrame(out, columns=["code", "I", "z", "p", "type"])


def lisa(agg, ref, voisins, rng):
    """Zones de désert et de concentration (point 4), par intercommunalité, principales professions.
    Correction de Benjamini-Hochberg sur les p-valeurs de chaque profession."""
    if not voisins or "epci" not in voisins:
        return None
    n, dens, pop = tables(agg, ref, "epci", "all")
    out = []
    for p in config.PROFESSIONS_PRINCIPALES:
        if p not in dens or n[p].sum() < 100:
            continue
        r = moran_local(np.log1p(dens[p]), voisins["epci"], rng=rng)
        if r.empty:
            continue
        r["q"] = benjamini_hochberg(r["p"])
        r["zone"] = np.where(r["q"] < .05, r["type"].map({"HH": "concentration", "LL": "desert",
                                                           "HL": "isole_haut", "LH": "isole_bas"}), "non_significatif")
        r.insert(0, "prof", p)
        r["population"] = r["code"].map(pop)
        r["densite"] = r["code"].map(dens[p])
        out.append(r)
    return pd.concat(out, ignore_index=True) if out else None


def porte_offre(agg, ref, ctx):
    """Qui porte l'offre (point 9). Répartition des professionnels par grand secteur d'exercice (libéral,
    hôpital public, privé, médico-social, centre de santé) selon la densité de population de
    l'intercommunalité. Une personne qui exerce dans plusieurs secteurs compte dans chacun."""
    import re as _re
    from .util import norm
    s = agg.secteurs
    if s is None or "epci" not in set(s["niveau"]) or "epci" not in ctx or "densite_pop" not in ctx["epci"]:
        return None
    s = s[s["niveau"] == "epci"].copy()

    def groupe(lib):
        n = norm(lib)
        return next((g for motif, g in config.SECTEURS_GROUPES if _re.search(motif, n)), config.SECTEUR_AUTRE)
    s["groupe"] = s["secteur"].map({lib: groupe(lib) for lib in s["secteur"].unique()})
    dp = ctx["epci"]["densite_pop"]
    classe = pd.Series(np.nan, index=dp.index, dtype=object)
    for a, b, lab in CLASSES_DENSITE:
        classe[(dp >= a) & (dp < b)] = lab
    s["classe"] = s["code"].map(classe)
    s = s.dropna(subset=["classe"])
    t = s.groupby(["prof", "classe", "groupe"], observed=True)["n"].sum().reset_index()
    t["part"] = t["n"] / t.groupby(["prof", "classe"])["n"].transform("sum")
    tot = s.groupby(["prof", "groupe"])["n"].sum().reset_index().assign(classe="Ensemble")
    tot["part"] = tot["n"] / tot.groupby("prof")["n"].transform("sum")
    return pd.concat([t, tot], ignore_index=True)


# ---------------------------------------------------------------- accessibilité (points 5 et 18)
RAYON_TERRE = 6371.0


def coords_3d(lon, lat):
    """Coordonnées cartésiennes (km) sur la sphère, pour des recherches de voisins par arbre k-d."""
    lo, la = np.radians(np.asarray(lon, float)), np.radians(np.asarray(lat, float))
    return np.column_stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)]) * RAYON_TERRE


def corde_vers_km(c):
    """Distance à vol d'oiseau (grand cercle) à partir de la corde entre deux points de la sphère."""
    return 2 * RAYON_TERRE * np.arcsin(np.clip(np.asarray(c, float) / (2 * RAYON_TERRE), 0, 1))


def km_vers_corde(d):
    return 2 * RAYON_TERRE * np.sin(np.asarray(d, float) / (2 * RAYON_TERRE))


def poids_distance(d, portee=20.0):
    """Décroissance avec la distance, transposée de l'APL de la DREES (qui raisonne en minutes de trajet).
    Pour la portée de référence de 20 km, poids 1 jusqu'à 10 km, 0,66 de 10 à 15 km, 0,33 de 15 à 20 km, 0 au-delà.
    Une autre portée garde les mêmes proportions (paliers à la moitié et aux trois quarts de la portée)."""
    d = np.asarray(d, float)
    return np.select([d <= portee / 2, d <= portee * .75, d <= portee], [1.0, .66, .33], 0.0)


def accessibilite_2sfca(xyz, offre, population, portee=20.0):
    """Accessibilité potentielle à deux étapes (2SFCA avec décroissance par paliers), pour chaque lieu.
    Étape 1, chaque lieu d'exercice j a un ratio offre sur population pondérée dans sa portée.
    Étape 2, chaque commune additionne les ratios des lieux à sa portée, pondérés par la distance.
    Renvoie des professionnels pour 10 000 habitants, comparables à une densité."""
    from scipy.sparse import coo_matrix, identity
    from scipy.spatial import cKDTree
    arbre = cKDTree(xyz)
    D = arbre.sparse_distance_matrix(arbre, km_vers_corde(portee), output_type="coo_matrix")
    hors_diag = D.row != D.col   # la diagonale n'est pas toujours stockée, elle est ajoutée une seule fois
    w = poids_distance(corde_vers_km(D.data[hors_diag]), portee)
    n = len(xyz)
    W = (coo_matrix((w, (D.row[hors_diag], D.col[hors_diag])), shape=(n, n)) + identity(n)).tocsr()
    offre, population = np.asarray(offre, float), np.asarray(population, float)
    demande = W @ population
    ratio = np.where(demande > 0, offre / np.where(demande > 0, demande, 1), 0.0)
    return (W @ ratio) * 1e4


def accessibilite(agg, ref, voisins):
    """Distance au professionnel le plus proche (à vol d'oiseau, entre centres de communes) et accessibilité
    potentielle à deux étapes, par commune, résumées par profession et par intercommunalité."""
    from scipy.spatial import cKDTree
    centres = (voisins or {}).get("centres")
    if not centres:
        return None, None, None
    com = ref.communes[ref.communes["code"].isin(centres)].copy()
    com = com[com["pop"] > 0]
    xy = np.array([centres[c] for c in com["code"]])
    xyz = coords_3d(xy[:, 0], xy[:, 1])
    n, _d, _p = tables(agg, ref, "com", "all")
    n = n.reindex(com["code"]).fillna(0)
    # version libérale, pour comparer avec l'APL de la DREES qui ne compte que l'activité libérale
    n_lib, _d, _p = tables(agg, ref, "com", "lib")
    n_lib = n_lib.reindex(com["code"]).fillna(0)
    apl_profs = {p for _m, p in config.APL_PROFESSIONS}
    pop = com["pop"].to_numpy(float)
    lignes, resume = [], []
    for p in config.PROFESSIONS_PRINCIPALES:
        if p not in n or n[p].sum() < 100:
            continue
        offre = n[p].to_numpy(float)
        d, _ = cKDTree(xyz[offre > 0]).query(xyz)
        d = corde_vers_km(d)
        acc = accessibilite_2sfca(xyz, offre, pop)
        lignes.append(pd.DataFrame({"code": com["code"].to_numpy(), "epci": com["epci"].to_numpy(),
                                    "dep": com["dep"].to_numpy(), "prof": p, "population": pop,
                                    "distance_km": d, "accessibilite": acc,
                                    "accessibilite_liberale": (accessibilite_2sfca(xyz, n_lib[p].to_numpy(float), pop)
                                                               if p in apl_profs and p in n_lib else np.nan)}))
        o = np.argsort(d)
        cum = np.cumsum(pop[o]) / pop.sum()
        res = {"prof": p, "part_population_dans_la_commune": float(pop[d == 0].sum() / pop.sum()),
               "distance_mediane_km": float(d[o][np.searchsorted(cum, .5)]),
               "distance_moyenne_km": float(np.average(d, weights=pop))}
        for s in (5, 10, 20, 30):
            res[f"part_population_a_plus_de_{s}_km"] = float(pop[d > s].sum() / pop.sum())
        resume.append(res)
    if not lignes:
        return None, None, None
    tc = pd.concat(lignes, ignore_index=True)
    epci = (tc.assign(dp=tc["distance_km"] * tc["population"], ap=tc["accessibilite"] * tc["population"])
            .groupby(["prof", "epci"]).agg(population=("population", "sum"), dp=("dp", "sum"), ap=("ap", "sum"))
            .reset_index())
    epci["distance_moyenne_km"] = epci["dp"] / epci["population"]
    epci["accessibilite"] = epci["ap"] / epci["population"]
    return pd.DataFrame(resume), tc, epci.drop(columns=["dp", "ap"])


def sensibilite_accessibilite(agg, ref, voisins, portees=(10.0, 30.0), profs=None):
    """Solidité de l'accessibilité à deux étapes face au choix de la portée (20 km par défaut). Pour chaque
    profession, corrélation de rang entre intercommunalités et part des intercommunalités du quart le moins
    accessible qui y restent quand la portée change."""
    centres = (voisins or {}).get("centres")
    if not centres:
        return None
    com = ref.communes[ref.communes["code"].isin(centres)].copy()
    com = com[com["pop"] > 0]
    xy = np.array([centres[c] for c in com["code"]])
    xyz = coords_3d(xy[:, 0], xy[:, 1])
    n, _d, _p = tables(agg, ref, "com", "all")
    n = n.reindex(com["code"]).fillna(0)
    pop = com["pop"].to_numpy(float)
    profs = profs or ["psychologue", "psychiatre", "pedopsychiatre", "medecin_generaliste", "orthophoniste"]
    out = []
    for p in profs:
        if p not in n or n[p].sum() < 100:
            continue
        def par_epci(acc):
            t = pd.DataFrame({"epci": com["epci"].to_numpy(), "ap": acc * pop, "pop": pop}).groupby("epci").sum()
            return t["ap"] / t["pop"]
        ref_ = par_epci(accessibilite_2sfca(xyz, n[p].to_numpy(float), pop, 20.0))
        bas_ref = set(ref_[ref_ <= ref_.quantile(.25)].index)
        for portee in portees:
            alt = par_epci(accessibilite_2sfca(xyz, n[p].to_numpy(float), pop, portee))
            bas_alt = set(alt[alt <= alt.quantile(.25)].index)
            out.append({"prof": p, "portee_km": portee, "rho_epci": stats.spearmanr(ref_, alt.reindex(ref_.index))[0],
                        "quart_bas_conserve": len(bas_ref & bas_alt) / max(len(bas_ref), 1)})
    return pd.DataFrame(out) if out else None


def loi_inverse(agg, ref, ctx, rng):
    """Loi inverse des soins (Tudor Hart, 1971). Indice de concentration des professionnels entre départements
    classés du besoin le plus faible au plus fort (suicide, gestes auto-infligés, personnes prises en charge).
    Négatif, l'offre est plus présente là où le besoin mesuré est faible, ce que décrit la loi inverse."""
    if ctx is None or "dep" not in ctx:
        return None
    n, _d, pop = tables(agg, ref, "dep", "all")
    c = ctx["dep"].reindex(pop.index)
    out = []
    for besoin in config.LOI_INVERSE_BESOINS:
        if besoin not in c:
            continue
        for p in config.LOI_INVERSE_PROFESSIONS:
            if p not in n:
                continue
            m = c[besoin].notna() & ~pop.index.isin(config.DEPARTEMENTS_EXCLUS_CROISEMENTS)
            y, w, r = n.loc[m, p].to_numpy(float), pop[m].to_numpy(float), c.loc[m, besoin].to_numpy(float)
            ci, *_ = indice_concentration(y, w, r)
            bs = []
            for _ in range(config.BOOTSTRAP):
                i = rng.integers(0, len(y), len(y))
                bs.append(indice_concentration(y[i], w[i], r[i])[0])
            lo, hi = np.percentile(bs, [2.5, 97.5])
            out.append({"prof": p, "variable": besoin, "departements": int(m.sum()), "indice_concentration": ci,
                        "ic95_bas": lo, "ic95_haut": hi})
    return pd.DataFrame(out) if out else None


def concordance_besoins(ctx):
    """Corrélations de rang entre indicateurs de besoin en santé mentale, entre départements."""
    if ctx is None or "dep" not in ctx:
        return None
    c = ctx["dep"]
    vs = [v for v in config.CONCORDANCE_BESOINS if v in c]
    out = []
    for i, a in enumerate(vs):
        for b in vs[i + 1:]:
            d = c[[a, b]].dropna()
            d = d[~d.index.isin(config.DEPARTEMENTS_EXCLUS_CROISEMENTS)]
            if len(d) > 20:
                out.append({"variable_a": a, "variable_b": b, "rho": stats.spearmanr(d[a], d[b])[0], "departements": len(d)})
    return pd.DataFrame(out) if out else None


def croisements(agg, ref, ctx, rng, route=None):
    """Croisements départementaux (config.CROISEMENTS), corrélation de rang brute et à densité de population égale,
    avec intervalles de confiance par bootstrap. « route:équipement » désigne le temps médian par la route vers
    l'équipement le plus proche (temps_acces, départements)."""
    if ctx is None or "dep" not in ctx:
        return None
    _n, d_all, pop = tables(agg, ref, "dep", "all")
    _n, d_lib, _p = tables(agg, ref, "dep", "lib")
    c = ctx["dep"].reindex(pop.index)

    def serie(cle):
        if cle.startswith("route:"):
            if not isinstance(route, pd.DataFrame) or route.empty:
                return None
            r = route[(route["niveau"] == "dep") & (route["equipement"] == cle[6:])]
            return r.set_index("code")["temps_median_min"].reindex(pop.index) if len(r) else None
        if cle.startswith("dens_lib:"):
            p = cle.split(":", 1)[1]
            return d_lib[p] if p in d_lib else None
        if cle.startswith("dens:"):
            p = cle.split(":", 1)[1]
            return d_all[p] if p in d_all else None
        v = cle.split(":", 1)[1] if cle.startswith("ctx:") else cle
        return c[v] if v in c else None
    z = np.log(c["densite_pop"]) if "densite_pop" in c else None
    out, points = [], {}
    for xa, yb, theme, _q in config.CROISEMENTS:
        x, y = serie(xa), serie(yb)
        if x is None or y is None:
            continue
        m = x.notna() & y.notna() & ~x.index.isin(config.DEPARTEMENTS_EXCLUS_CROISEMENTS)
        rho, p, lo, hi, k = spearman_bootstrap(x[m], y[m], config.BOOTSTRAP, rng)
        r = {"theme": theme, "mesure": xa, "variable": yb, "departements": k, "rho": rho, "ic95_bas": lo, "ic95_haut": hi}
        points[(xa, yb)] = [(c_, float(a), float(b)) for c_, a, b in zip(x[m].index, x[m], y[m])]
        if z is not None:
            rp, _pp, lp, hp, _k = spearman_partiel_bootstrap(x[m], y[m], z[m], config.BOOTSTRAP, rng)
            r.update({"rho_partiel_densite": rp, "ic95_bas_partiel": lp, "ic95_haut_partiel": hp})
        out.append(r)
    if not out:
        return None
    t = pd.DataFrame(out)
    t.attrs["points"] = points   # valeurs par département, pour le nuage de l'atlas (pas écrites dans le CSV)
    return t


def ombre_urbaine(agg, ref, acces_epci):
    """Effet frontière (point 18). Parmi les intercommunalités du quart le moins dense en professionnels,
    distingue celles dont l'accessibilité reste au-dessus de la médiane (« ombre urbaine », les habitants
    trouvent des professionnels juste à côté) de celles qui restent dans le quart le plus bas (« désert »)."""
    if acces_epci is None or acces_epci.empty:
        return None
    n, dens, pop = tables(agg, ref, "epci", "all")
    out = []
    for p, g in acces_epci.groupby("prof"):
        if p not in dens:
            continue
        a = g.set_index("epci")["accessibilite"].reindex(dens.index)
        d = dens[p]
        bas = d <= d.quantile(.25)
        cat = np.select([bas & (a >= a.median()), bas & (a <= a.quantile(.25)), bas],
                        ["ombre_urbaine", "desert", "intermediaire"], "hors_quart_bas")
        out.append(pd.DataFrame({"prof": p, "code": dens.index, "densite": d.to_numpy(), "accessibilite": a.to_numpy(),
                                 "population": pop.to_numpy(), "categorie": cat}))
    return pd.concat(out, ignore_index=True) if out else None


# ---------------------------------------------------------------- temps de trajet (INSEE) et APL (DREES)
def mediane_histogramme(minutes, poids):
    """Médiane pondérée d'une variable regroupée en tranches d'une minute [m, m + 1), avec interpolation
    linéaire dans la tranche qui contient la moitié du poids total."""
    h = pd.Series(np.asarray(poids, float), index=np.asarray(minutes, int)).groupby(level=0).sum().sort_index()
    if h.sum() <= 0:
        return np.nan
    cum = h.cumsum()
    moitie = h.sum() / 2
    k = int(np.searchsorted(cum.to_numpy(), moitie))
    avant = cum.iloc[k - 1] if k > 0 else 0.0
    return float(h.index[k] + (moitie - avant) / h.iloc[k])


def medianes_histogramme(h: pd.DataFrame, cles: list) -> pd.DataFrame:
    """Version vectorisée de mediane_histogramme pour de nombreux groupes. h porte les colonnes cles, minute et
    pop, renvoie une ligne par groupe avec temps_median_min (même interpolation dans la tranche d'une minute)."""
    g = h.groupby(cles + ["minute"], as_index=False, observed=True)["pop"].sum().sort_values(cles + ["minute"])
    g = g[g["pop"] > 0].copy()
    g["cum"] = g.groupby(cles, observed=True)["pop"].cumsum()
    g["moitie"] = g.groupby(cles, observed=True)["pop"].transform("sum") / 2
    t = g[g["cum"] >= g["moitie"]].groupby(cles, as_index=False, observed=True).first()
    t["temps_median_min"] = t["minute"] + (t["moitie"] - (t["cum"] - t["pop"])) / t["pop"]
    return t[cles + ["temps_median_min"]]


def temps_acces(ar, ref):
    """Temps de trajet en voiture vers l'équipement le plus proche, résumé par territoire (France, région,
    département, intercommunalité). Moyenne et parts pondérées par la population des carreaux, médiane tirée
    de l'histogramme par minute, gardé par commune depuis le 5 octobre 2026 (médiane à tous les niveaux)."""
    if not ar:
        return None
    seuils = config.ACCES_ROUTE_SEUILS
    ids = {d["code"]: d["id"] for d in ar["defs"]}
    c = ar["communes"].copy()
    c["equipement"] = c["typeeq_id"].map(ids)
    com = ref.communes.set_index("code")
    c["epci"], c["dep_ref"] = c["depcom"].map(com["epci"]), c["depcom"].map(com["dep"])
    dep_reg = ref.deps.set_index("code")["reg"]
    c["reg"] = c["dep_ref"].map(dep_reg)
    sommes = ["pop", "pop_calcule", "pd"] + [f"sup_{s}" for s in seuils]
    out = []
    for niv, cle in [("FR", None), ("reg", "reg"), ("dep", "dep_ref"), ("epci", "epci")]:
        g = (c.groupby("equipement")[sommes].sum().reset_index().assign(code="FR") if cle is None
             else c.dropna(subset=[cle]).groupby([cle, "equipement"])[sommes].sum().reset_index()
             .rename(columns={cle: "code"}))
        g.insert(0, "niveau", niv)
        out.append(g)
    t = pd.concat(out, ignore_index=True)
    t["temps_moyen_min"] = t["pd"] / t["pop_calcule"].where(t["pop_calcule"] > 0)
    for s in seuils:
        t[f"part_population_a_plus_de_{s}_min"] = t[f"sup_{s}"] / t["pop_calcule"].where(t["pop_calcule"] > 0)
    t["part_population_non_calculee"] = 1 - t["pop_calcule"] / t["pop"]
    # médianes par l'histogramme des durées, rattaché aux territoires par la commune, comme le résumé
    h = ar["histogramme"].copy()
    h["equipement"] = h["typeeq_id"].map(ids)
    h["epci"], h["dep"] = h["depcom"].map(com["epci"]), h["depcom"].map(com["dep"])
    h["reg"], h["FR"] = h["dep"].map(dep_reg), "FR"
    med = []
    for niv, cle in [("FR", "FR"), ("reg", "reg"), ("dep", "dep"), ("epci", "epci")]:
        m = medianes_histogramme(h.dropna(subset=[cle]), [cle, "equipement"]).rename(columns={cle: "code"})
        med.append(m.assign(niveau=niv))
    t = t.merge(pd.concat(med, ignore_index=True), on=["niveau", "code", "equipement"], how="left")
    t = t.rename(columns={"pop": "population"}).drop(columns=["pop_calcule", "pd"] + [f"sup_{s}" for s in seuils])
    t.insert(3, "libelle", t["equipement"].map({d["id"]: d.get("libelle", d["id"]) for d in ar["defs"]}))
    return t


def comparaison_route(ar, acc_communes):
    """Ressemblance, commune par commune, entre la distance à vol d'oiseau calculée par le programme
    (professionnels de tous modes d'exercice) et le temps de trajet de l'INSEE (professionnels libéraux)."""
    if not ar or acc_communes is None or acc_communes.empty:
        return None
    c = ar["communes"]
    out = []
    for d in ar["defs"]:
        p = d["prof"]
        if not p or p not in set(acc_communes["prof"]):
            continue
        x = c[c["typeeq_id"] == d["code"]]
        x = x.assign(t=x["pd"] / x["pop_calcule"].where(x["pop_calcule"] > 0)).set_index("depcom")["t"]
        a = acc_communes[acc_communes["prof"] == p].set_index("code")
        j = a[["distance_km", "population"]].join(x.rename("temps"), how="inner").dropna()
        if len(j) < 50:
            continue
        out.append({"prof": p, "equipement": d["id"], "communes": len(j),
                    "rho_spearman": stats.spearmanr(j["distance_km"], j["temps"])[0]})
    return pd.DataFrame(out) if out else None


def comparaison_apl(apl, acc_communes, acc_epci, agg, ref):
    """Ressemblance entre l'accessibilité calculée par le programme et l'APL de la DREES, par commune et par
    intercommunalité. L'APL ne compte que l'activité libérale (et les centres de santé pour les généralistes),
    la comparaison porte donc sur l'accessibilité calculée avec les seuls libéraux, et, pour mémoire, sur la
    densité de libéraux."""
    if not apl or acc_communes is None or acc_communes.empty:
        return None
    t = apl["communes"]
    _n, dens, _pop = tables(agg, ref, "epci", "lib")
    epci_com = ref.communes.set_index("code")["epci"]
    rho = lambda x, y: stats.spearmanr(x, y)[0] if len(x) > 50 else np.nan  # noqa: E731
    out = []
    for p, g in t.groupby("prof"):
        a = acc_communes[acc_communes["prof"] == p]
        if a.empty or p not in dens or a["accessibilite_liberale"].isna().all():
            continue
        a = a.set_index("code")
        j = a[["accessibilite_liberale"]].join(g.set_index("code")[["apl", "population"]], how="inner").dropna()
        j = j[j["population"] > 0]
        ge = g.assign(epci=g["code"].map(epci_com), ap=g["apl"] * g["population"]).dropna(subset=["epci"])
        ge = ge.groupby("epci").agg(ap=("ap", "sum"), population=("population", "sum"))
        ae = (a.assign(x=a["accessibilite_liberale"] * a["population"]).groupby("epci")
              .agg(x=("x", "sum"), population=("population", "sum")))
        je = pd.concat([(ae["x"] / ae["population"]).rename("acc"), (ge["ap"] / ge["population"]).rename("apl"),
                        dens[p].rename("dens")], axis=1).dropna()
        out.append({"prof": p, "annee_apl": apl["defs"][p]["annee"], "communes": len(j),
                    "rho_communes": rho(j["accessibilite_liberale"], j["apl"]), "intercommunalites": len(je),
                    "rho_epci": rho(je["acc"], je["apl"]), "rho_densite_epci": rho(je["dens"], je["apl"])})
    return pd.DataFrame(out) if out else None


# ---------------------------------------------------------------- lot D, pour les chercheurs
def theil_decomposition(n, pop, groupes):
    """Décomposition de l'indice de Theil (forme T, parts de professionnels rapportées aux parts de
    population) en une part entre groupes et une part dans les groupes. Renvoie (total, entre, dans)."""
    n, pop, groupes = np.asarray(n, float), np.asarray(pop, float), np.asarray(groupes)
    total = theil(n, pop)
    s, p = n / n.sum(), pop / pop.sum()
    entre = dans = 0.0
    for g in pd.unique(groupes):
        m = groupes == g
        Sg, Pg = s[m].sum(), p[m].sum()
        if Sg > 0:
            entre += Sg * np.log(Sg / Pg)
            dans += Sg * theil(n[m], pop[m])
    return total, entre, dans


def decomposition_theil(agg, ref, ctx):
    """Point 7. Les inégalités entre intercommunalités tiennent-elles surtout aux écarts entre départements
    (ou entre classes urbaines et rurales), ou aux écarts à l'intérieur de chacun ?"""
    n, dens, pop = tables(agg, ref, "epci", "all")
    dep = ref.epci.set_index("code")["dep"].reindex(n.index)
    classe = pd.Series("inconnue", index=n.index)
    if ctx and "epci" in ctx and "densite_pop" in ctx["epci"]:
        dp = ctx["epci"]["densite_pop"].reindex(n.index)
        for a, b, lab in CLASSES_DENSITE:
            classe[(dp >= a) & (dp < b)] = lab
    out = []
    for p in config.PROFESSIONS_PRINCIPALES:
        if p not in n or n[p].sum() < 100:
            continue
        for nom, g in [("départements", dep), ("classes de densité", classe)]:
            ok = g.notna()
            t, e, d = theil_decomposition(n.loc[ok, p], pop[ok], g[ok])
            out.append({"prof": p, "groupes": nom, "theil": t, "entre": e, "dans": d,
                        "part_entre": e / t if t > 0 else np.nan})
    return pd.DataFrame(out)


def substitution(agg, ref, ctx, rng):
    """Point 8. Les professions se cumulent-elles (présentes ensemble) ou se substituent-elles (l'une là
    où l'autre manque) ? Corrélation de rang entre densités, brute et à densité de population égale."""
    n, dens, pop = tables(agg, ref, "epci", "all")
    ville = ctx["epci"]["densite_pop"].reindex(dens.index) if ctx and "epci" in ctx else None
    out = []
    for a, b in config.PAIRES_SUBSTITUTION:
        if a not in dens or b not in dens:
            continue
        rho, _p, lo, hi, nn = spearman_bootstrap(dens[a], dens[b], config.BOOTSTRAP, rng)
        rp = lp = hp = np.nan
        if ville is not None:
            rp, _pp, lp, hp, _ = spearman_partiel_bootstrap(dens[a], dens[b], ville, config.BOOTSTRAP, rng)
        out.append({"prof_a": a, "prof_b": b, "rho": rho, "ic95_bas": lo, "ic95_haut": hi,
                    "rho_partiel_densite": rp, "ic95_bas_partiel": lp, "ic95_haut_partiel": hp, "territoires": nn})
    return pd.DataFrame(out)


def gini_bootstrap(n, pop, B, rng):
    """Intervalle de confiance à 95 % de l'indice de Gini par bootstrap sur les territoires."""
    n, pop = np.asarray(n, float), np.asarray(pop, float)
    bs = []
    for _ in range(B):
        i = rng.integers(0, len(n), len(n))
        if n[i].sum() > 0:
            bs.append(lorenz(n[i], pop[i])[0])
    return tuple(np.percentile(bs, [2.5, 97.5])) if bs else (np.nan, np.nan)


def robustesse(agg, ref, ineg, rng):
    """Points 12 et 17. Indice de Gini avec intervalle de confiance, et sensibilité à l'échelle
    (communes, intercommunalités, départements, régions)."""
    out = []
    n, _d, pop = tables(agg, ref, "epci", "all")
    piv = ineg[ineg["mode"] == "all"].pivot_table(index="prof", columns="niveau", values="gini") \
        if isinstance(ineg, pd.DataFrame) else pd.DataFrame()
    for p in config.PROFESSIONS_PRINCIPALES:
        if p not in n or n[p].sum() < 100:
            continue
        lo, hi = gini_bootstrap(n[p], pop, config.BOOTSTRAP, rng)
        lig = {"prof": p, "gini_epci": lorenz(n[p], pop)[0], "ic95_bas": lo, "ic95_haut": hi}
        for niv in ["com", "epci", "dep", "reg"]:
            lig[f"gini_{niv}"] = piv.at[p, niv] if p in piv.index and niv in piv.columns else np.nan
        out.append(lig)
    return pd.DataFrame(out)


def variance_niveaux(agg, ref):
    """Point 12, approche multiniveau simple. Part de la variation du logarithme de la densité entre
    intercommunalités qui tient aux différences entre départements (eta², équivalent d'un coefficient de
    corrélation intraclasse descriptif), pondérée par la population."""
    n, dens, pop = tables(agg, ref, "epci", "all")
    dep = ref.epci.set_index("code")["dep"].reindex(dens.index)
    out = []
    for p in config.PROFESSIONS_PRINCIPALES:
        if p not in dens or n[p].sum() < 100:
            continue
        y, w = np.log1p(dens[p]), pop
        m = (y * w).sum() / w.sum()
        tot = (w * (y - m) ** 2).sum()
        md = (y * w).groupby(dep).sum() / w.groupby(dep).sum()
        entre = (w * (dep.map(md) - m) ** 2).sum()
        out.append({"prof": p, "part_entre_departements": entre / tot if tot > 0 else np.nan})
    return pd.DataFrame(out)


def moran_residus(R, voisins, rng):
    """Point 20, contrôle spatial des modèles. Indice de Moran des résidus (log du rapport observé sur
    attendu) des régressions de Poisson. Un indice nettement positif signale une structure spatiale que le
    modèle n'explique pas, et des erreurs standard probablement trop optimistes."""
    ea = R.get("ecarts_attendu")
    if not voisins or not isinstance(ea, pd.DataFrame) or ea.empty:
        return None
    out = []
    for p, g in ea.groupby("prof"):
        r = np.log((g["effectif"] + .5) / (g["effectif_attendu"] + .5))
        I, pv = moran(pd.Series(r.to_numpy(), index=g["code"]), voisins["epci"], rng=rng)
        out.append({"prof": p, "moran_residus": I, "p_permutation": pv})
    return pd.DataFrame(out)


def outre_mer(agg, ref):
    """Point 19. Densités des départements d'outre-mer comparées à l'Hexagone, principales professions."""
    n, dens, pop = tables(agg, ref, "dep", "all")
    om = [d for d in dens.index if d in config.DEPS_DROM]
    hexa = [d for d in dens.index if d not in config.DEPS_DROM]
    out = []
    for p in config.PROFESSIONS_PRINCIPALES:
        if p not in n:
            continue
        lig = {"prof": p, "hexagone": n.loc[hexa, p].sum() / pop[hexa].sum() * 1e4}
        for d in om:
            lig[d] = dens.at[d, p]
        out.append(lig)
    return pd.DataFrame(out)


# ---------------------------------------------------------------- analyses
def inegalites(agg, ref, professions):
    lignes, courbes = [], []
    for niv in ["epci", "dep", "reg", "com"]:
        for mode in ["all", "lib", "sal"]:
            n, dens, pop = tables(agg, ref, niv, mode)
            for p in n.columns:
                if n[p].sum() == 0:
                    continue
                g, xs, ys = lorenz(n[p], pop, points=21)
                d = dens[p]
                zero = n[p] == 0
                lignes.append({
                    "niveau": niv, "mode": mode, "prof": p, "effectif": int(n[p].sum()),
                    "densite_nationale": n[p].sum() / pop.sum() * 1e4,
                    "moyenne": d.mean(), "mediane": d.median(), "p10": d.quantile(.1), "p90": d.quantile(.9),
                    "rapport_p90_p10": d.quantile(.9) / d.quantile(.1) if d.quantile(.1) > 0 else np.nan,
                    "gini": g, "theil": theil(n[p], pop),
                    "territoires_sans_professionnel": int(zero.sum()),
                    "part_population_sans_professionnel": pop[zero].sum() / pop.sum(),
                })
                if niv in ("epci", "dep") and mode == "all":
                    courbes += [{"niveau": niv, "prof": p, "x": x, "y": y} for x, y in zip(xs, ys)]
    return pd.DataFrame(lignes), pd.DataFrame(courbes)


def correlations_contexte(agg, ref, ctx, rng):
    lignes = []
    for niv in config.NIVEAUX_ANALYSE:
        if niv not in ctx:
            continue
        for mode in ["all", "lib", "sal"]:
            _n, dens, pop = tables(agg, ref, niv, mode)
            c = ctx[niv].reindex(dens.index)
            # contrôle de l'effet ville, logarithme de la densité de population (les rangs n'en dépendent pas)
            ville = c["densite_pop"] if "densite_pop" in c else None
            for p in dens.columns:
                if _n[p].sum() < 30:
                    continue
                B = config.BOOTSTRAP if p in config.PROFESSIONS_PRINCIPALES and mode == "all" else 0
                for v in c.columns:
                    rho, pv, lo, hi, nn = spearman_bootstrap(c[v], dens[p], B, rng)
                    rp = pearson_pondere(c[v].to_numpy(float), np.log(dens[p].to_numpy(float) + .5),
                                         pop.to_numpy(float))
                    lig = {"niveau": niv, "mode": mode, "prof": p, "variable": v, "n": nn,
                           "rho_spearman": rho, "ic95_bas": lo, "ic95_haut": hi, "p": pv,
                           "r_pearson_pondere_log": rp}
                    if ville is not None and v != "densite_pop":
                        rq, pq, lq, hq, _nq = spearman_partiel_bootstrap(c[v], dens[p], ville, B, rng)
                        lig.update({"rho_partiel_densite": rq, "ic95_bas_partiel": lq, "ic95_haut_partiel": hq,
                                    "p_partiel": pq})
                    lignes.append(lig)
    df = pd.DataFrame(lignes)
    if len(df):
        df["q_bh"] = np.nan
        if "p_partiel" in df:
            df["q_bh_partiel"] = np.nan
        for (niv, mode), g in df.groupby(["niveau", "mode"]):
            df.loc[g.index, "q_bh"] = benjamini_hochberg(g["p"])
            if "p_partiel" in df:
                df.loc[g.index, "q_bh_partiel"] = benjamini_hochberg(g["p_partiel"])
        df["force"] = pd.cut(df["rho_spearman"].abs(), [0, .1, .3, .5, 1.01],
                             labels=["négligeable", "faible", "modérée", "forte"], right=False)
    return df


def revenu(agg, ref, ctx, rng):
    """Offre selon le niveau de vie des territoires. Indice de concentration (territoires classés du plus
    modeste au plus aisé) avec intervalle de confiance par bootstrap, et « escalier social », densité de
    professionnels par décile de niveau de vie (chaque décile réunit environ 10 % des habitants)."""
    conc, esc = [], []
    for niv in config.NIVEAUX_ANALYSE:
        if niv not in ctx or "revenu_median" not in ctx[niv]:
            continue
        for mode in ["all", "lib", "sal"]:
            n, _dens, pop = tables(agg, ref, niv, mode)
            rev = ctx[niv]["revenu_median"].reindex(n.index)
            ok = rev.notna().to_numpy()
            n, pop, rev = n[ok], pop[ok], rev[ok]
            dec = deciles_population(rev, pop)
            for p in n.columns:
                # par mode d'exercice, seulement les principales professions (lot A, point 16)
                if n[p].sum() < 100 or (mode != "all" and p not in config.PROFESSIONS_PRINCIPALES):
                    continue
                y = n[p].to_numpy(float)
                ci, *_ = indice_concentration(y, pop, rev)
                bs = []
                for _ in range(config.BOOTSTRAP):
                    i = rng.integers(0, len(y), len(y))
                    bs.append(indice_concentration(y[i], pop.to_numpy()[i], rev.to_numpy()[i])[0])
                lo, hi = np.percentile(bs, [2.5, 97.5])
                conc.append({"niveau": niv, "mode": mode, "prof": p, "indice_concentration": ci, "ic95_bas": lo,
                             "ic95_haut": hi, "territoires": int(len(y))})
                if mode != "all":
                    continue
                for d in range(1, 11):
                    m = dec == d
                    esc.append({"niveau": niv, "prof": p, "decile": d, "niveau_de_vie_min": rev[m].min(),
                                "niveau_de_vie_max": rev[m].max(), "population": pop[m].sum(),
                                "effectif": int(y[m].sum()), "densite": y[m].sum() / pop[m].sum() * 1e4})
    return pd.DataFrame(conc), pd.DataFrame(esc)


def densite_cible(agg, ref, ctx):
    """Densité rapportée au public concerné (point 13). Par exemple les pédopsychiatres pour 10 000 moins
    de 15 ans. Compare la répartition à celle de la densité générale (inégalité, classement des
    territoires, part du public concerné sans aucun professionnel)."""
    resume, lignes = [], []
    nat = agg.national[agg.national["mode"] == "all"].set_index("prof")["n"]
    for niv in config.NIVEAUX_ANALYSE:
        if niv not in ctx:
            continue
        n, dens, pop = tables(agg, ref, niv, "all")
        c = ctx[niv].reindex(n.index)
        for p, (parts, public) in config.PUBLICS_CIBLES.items():
            if p not in n or not all(x in c for x in parts):
                continue
            cible = sum(c[x] for x in parts) / 100 * pop
            ok = cible.notna() & (cible > 0)
            y, cb, pp = n.loc[ok, p], cible[ok], pop[ok]
            dc = y / cb * 1e4
            g_gen, *_ = lorenz(y, pp)
            g_cib, *_ = lorenz(y, cb)
            a, b = dens.loc[ok, p], dc
            rho = stats.spearmanr(a, b)[0] if a.nunique() > 1 and b.nunique() > 1 else np.nan
            resume.append({"niveau": niv, "prof": p, "public": public,
                           "densite_nationale_cible": nat.get(p, 0) / cb.sum() * 1e4,
                           "gini_population": g_gen, "gini_public": g_cib, "rho_classements": rho,
                           "part_public_sans_professionnel": cb[y == 0].sum() / cb.sum()})
            lignes.append(pd.DataFrame({"niveau": niv, "prof": p, "public": public, "code": y.index,
                                        "effectif": y.to_numpy(), "population_cible": cb.to_numpy(),
                                        "densite_cible": dc.to_numpy()}))
    return pd.DataFrame(resume), (pd.concat(lignes, ignore_index=True) if lignes else pd.DataFrame())


def combinaisons(agg, ref, profs=("medecin_generaliste", "psychologue", "psychiatre")):
    """Combinaisons d'offre par territoire (point 14). Pour chaque combinaison de présence ou d'absence
    des professions données, nombre de territoires et part de la population."""
    out = []
    for niv in ["com", "epci"]:
        n, _dens, pop = tables(agg, ref, niv, "all")
        pres = pd.DataFrame({p: (n[p] > 0) if p in n else False for p in profs})
        g = pres.assign(_pop=pop).groupby(list(profs)).agg(territoires=("_pop", "size"), population=("_pop", "sum"))
        g = g.reset_index()
        g["part_population"] = g["population"] / pop.sum()
        g.insert(0, "niveau", niv)
        out.append(g)
    return pd.concat(out, ignore_index=True)


def composition_sante_mentale(agg, ref):
    """Psychologues par psychiatre, par territoire (point 15). Vide (NaN) sans psychiatre."""
    out = []
    for niv in config.NIVEAUX_ANALYSE:
        n, _dens, pop = tables(agg, ref, niv, "all")
        if "psychologue" not in n or "psychiatre" not in n:
            continue
        out.append(pd.DataFrame({"niveau": niv, "code": n.index, "population": pop.to_numpy(),
                                 "psychologues": n["psychologue"].to_numpy(), "psychiatres": n["psychiatre"].to_numpy(),
                                 "psychologues_par_psychiatre": (n["psychologue"] / n["psychiatre"].replace(0, np.nan)).to_numpy()}))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def entonnoir(agg, ref):
    """Diagramme en entonnoir. Chaque territoire est situé par rapport aux limites de Poisson à 95 % et
    99,8 % autour de la densité nationale, qui dépendent de sa population. Statut de -2 (nettement en
    dessous) à +2 (nettement au-dessus), 0 dans la norme. Mesure aussi la surdispersion, part des
    territoires hors des limites à 95 % (5 % attendus si seul le hasard jouait)."""
    lignes, resume, grilles = [], [], []
    for niv in config.NIVEAUX_ANALYSE:
        n, _dens, pop = tables(agg, ref, niv, "all")
        grille = np.unique(np.geomspace(max(pop.min(), 100), pop.max(), 60).round())
        for p in n.columns:
            if n[p].sum() < 100:
                continue
            y = n[p].to_numpy(float)
            taux = y.sum() / pop.sum()
            L = limites_entonnoir(pop.to_numpy(float), taux)
            b95, h95 = L[.95]
            b998, h998 = L[.998]
            statut = np.select([y < b998, y < b95, y > h998, y > h95], [-2, -1, 2, 1], 0)
            lignes.append(pd.DataFrame({"niveau": niv, "code": n.index, "prof": p, "population": pop.to_numpy(),
                                        "effectif": y.astype(int), "effectif_au_taux_national": pop.to_numpy() * taux,
                                        "statut": statut}))
            resume.append({"niveau": niv, "prof": p, "densite_nationale": taux * 1e4,
                           "part_hors_95": float(np.mean(statut != 0)),
                           "part_nettement_en_dessous": float(np.mean(statut == -2)),
                           "part_population_nettement_en_dessous": float(pop[statut == -2].sum() / pop.sum())})
            G = limites_entonnoir(grille, taux)
            grilles.append(pd.DataFrame({"niveau": niv, "prof": p, "population": grille,
                                         "bas_95": G[.95][0] / grille * 1e4, "haut_95": G[.95][1] / grille * 1e4,
                                         "bas_998": G[.998][0] / grille * 1e4, "haut_998": G[.998][1] / grille * 1e4}))
    cat = lambda L: pd.concat(L, ignore_index=True) if L else pd.DataFrame()  # noqa: E731
    return cat(lignes), pd.DataFrame(resume), cat(grilles)


QUADRANTS = {"besoin+offre-": "Indicateur élevé, offre faible", "besoin+offre+": "Indicateur élevé, offre élevée",
             "besoin-offre-": "Indicateur bas, offre faible", "besoin-offre+": "Indicateur bas, offre élevée"}


def quadrant(offre, besoin):
    """Classe chaque territoire selon que sa densité de professionnels et son indicateur de besoin sont
    au-dessus ou au-dessous de leur médiane (strictement au-dessus pour « + »). Valeur manquante si l'un
    des deux manque."""
    offre, besoin = np.asarray(offre, float), np.asarray(besoin, float)
    ok = ~(np.isnan(offre) | np.isnan(besoin))
    mo, mb = np.median(offre[ok]), np.median(besoin[ok])
    out = np.array([None] * len(offre), dtype=object)
    out[ok] = ["besoin" + ("+" if b > mb else "-") + "offre" + ("+" if o > mo else "-")
               for o, b in zip(offre[ok], besoin[ok])]
    return out, mo, mb


def sans_territoires(x, y, codes, exclus):
    """Corrélation de rang avec tous les territoires et sans ceux de la liste exclus (sensibilité à une
    sous-déclaration connue). Renvoie (rho, n, rho sans, n sans)."""
    from scipy.stats import spearmanr
    d = pd.DataFrame({"x": np.asarray(x, float), "y": np.asarray(y, float)}, index=list(codes)).dropna()
    s = d.drop([c for c in exclus if c in d.index])
    r = spearmanr(d["x"], d["y"])[0] if len(d) > 4 else np.nan
    r2 = spearmanr(s["x"], s["y"])[0] if len(s) > 4 else np.nan
    return float(r), len(d), float(r2), len(s)


def sensibilite_sous_declaration(agg, ref, ctx):
    """Corrélations entre l'offre de santé mentale et les indicateurs de besoin, avec et sans l'Île-de-France, où
    les suicides sont nettement sous-déclarés (config.LIMITES)."""
    if "dep" not in ctx:
        return pd.DataFrame()
    n, dens, pop = tables(agg, ref, "dep", "all")
    c = ctx["dep"].reindex(dens.index)
    lignes = []
    for p in [p for p in config.PROFESSIONS_QUADRANTS if p in dens]:
        for v in [v for v in ["suicides", "hospit_gestes_auto_infliges", "urgences_gestes_auto_infliges"] if v in c]:
            r, k, r2, k2 = sans_territoires(c[v], dens[p], dens.index, config.DEPS_ILE_DE_FRANCE)
            lignes.append({"prof": p, "variable": v, "rho_tous": r, "n_tous": k, "rho_sans_ile_de_france": r2,
                           "n_sans_ile_de_france": k2})
    t = pd.DataFrame(lignes)
    if len(t):
        x = t[(t["prof"] == "psychiatre") & (t["variable"] == "suicides")]
        if len(x):
            JOURNAL.controle("Psychiatres et suicides, corrélation avec et sans l'Île-de-France",
                             f"{x['rho_tous'].iloc[0]:.2f} et {x['rho_sans_ile_de_france'].iloc[0]:.2f}".replace(".", ","))
    return t


def quadrants(agg, ref, ctx):
    """Offre face aux indicateurs de besoin, par département, pour les principales professions de santé
    mentale. Les indicateurs de besoin sont ceux des bases complémentaires disponibles par département."""
    if "dep" not in ctx:
        return pd.DataFrame()
    base = {c[0] for c in config.CONTEXTE + config.CONTEXTE_VULNERABILITE}   # ni profil ni vulnérabilité
    n, dens, pop = tables(agg, ref, "dep", "all")
    c = ctx["dep"].reindex(dens.index)
    # Mayotte écartée comme dans tous les croisements entre départements (population de référence incertaine)
    c.loc[c.index.isin(config.DEPARTEMENTS_EXCLUS_CROISEMENTS)] = np.nan
    besoins = [v for v in c.columns if v not in base and c[v].notna().sum() >= 30]
    lignes = []
    for p in [p for p in config.PROFESSIONS_QUADRANTS if p in dens]:
        for v in besoins:
            q, mo, mb = quadrant(dens[p].to_numpy(), c[v].to_numpy())
            lignes.append(pd.DataFrame({"prof": p, "variable": v, "code": dens.index, "densite": dens[p].to_numpy(),
                                        "valeur": c[v].to_numpy(), "population": pop.to_numpy(), "quadrant": q,
                                        "mediane_densite": mo, "mediane_indicateur": mb}))
    return pd.concat(lignes, ignore_index=True) if lignes else pd.DataFrame()


def correlations_professions(agg, ref):
    out = {}
    for niv in config.NIVEAUX_ANALYSE:
        n, dens, _pop = tables(agg, ref, niv, "all")
        cols = [p for p in dens.columns if n[p].sum() >= 30]
        out[niv] = dens[cols].corr(method="spearman")
    return out


def classes_densite(agg, ref, ctx):
    lignes, tests = [], []
    for niv in config.NIVEAUX_ANALYSE:
        if niv not in ctx or "densite_pop" not in ctx[niv]:
            continue
        n, dens, pop = tables(agg, ref, niv, "all")
        dp = ctx[niv]["densite_pop"].reindex(dens.index)
        cl = pd.Series(np.nan, index=dens.index, dtype=object)
        for a, b, lab in CLASSES_DENSITE:
            cl[(dp >= a) & (dp < b)] = lab
        for p in dens.columns:
            if n[p].sum() < 30:
                continue
            groupes = []
            for _a, _b, lab in CLASSES_DENSITE:
                m = cl == lab
                if m.sum():
                    lignes.append({"niveau": niv, "prof": p, "classe": lab, "territoires": int(m.sum()),
                                   "population": pop[m].sum(), "densite_mediane": dens.loc[m, p].median(),
                                   "densite_agregee": n.loc[m, p].sum() / pop[m].sum() * 1e4})
                    groupes.append(dens.loc[m, p].to_numpy())
            groupes = [g for g in groupes if len(g) >= 5]
            if len(groupes) >= 2:
                H, ph = stats.kruskal(*groupes)
                N = sum(len(g) for g in groupes)
                u = stats.mannwhitneyu(groupes[0], groupes[-1])
                rb = 1 - 2 * u.statistic / (len(groupes[0]) * len(groupes[-1]))
                tests.append({"niveau": niv, "prof": p, "kruskal_H": H, "p": ph, "epsilon2": H / (N - 1),
                              "biserial_extremes": rb, "p_mann_whitney_extremes": u.pvalue})
    t = pd.DataFrame(tests)
    if len(t):
        t["q_bh"] = benjamini_hochberg(t["p"])
    return pd.DataFrame(lignes), t


def poisson_robuste(y, X, offset, noms, iterations=50):
    """Régression de Poisson avec offset (log population), estimée par IRLS.
    Erreurs standard sandwich (robustes à la surdispersion). X sans constante."""
    n, k = X.shape
    Xc = np.column_stack([np.ones(n), X])
    beta = np.zeros(k + 1)
    beta[0] = np.log(max(y.sum(), 1e-9) / np.exp(offset).sum())
    for _ in range(iterations):
        eta = np.clip(Xc @ beta + offset, -30, 30)
        mu = np.exp(eta)
        z = eta - offset + (y - mu) / mu
        XtW = Xc.T * mu
        nouveau = np.linalg.solve(XtW @ Xc + 1e-9 * np.eye(k + 1), XtW @ z)
        if np.max(np.abs(nouveau - beta)) < 1e-8:
            beta = nouveau
            break
        beta = nouveau
    mu = np.exp(np.clip(Xc @ beta + offset, -30, 30))
    bread = np.linalg.pinv((Xc.T * mu) @ Xc)
    meat = (Xc.T * (y - mu) ** 2) @ Xc
    V = bread @ meat @ bread * n / (n - k - 1)
    se = np.sqrt(np.diag(V))
    with np.errstate(divide="ignore", invalid="ignore"):
        dev = 2 * np.sum(np.where(y > 0, y * np.log(y / mu), 0) - (y - mu))
        mu0 = y.sum() / np.exp(offset).sum() * np.exp(offset)
        dev0 = 2 * np.sum(np.where(y > 0, y * np.log(y / mu0), 0) - (y - mu0))
    disp = np.sum((y - mu) ** 2 / mu) / (n - k - 1)
    coefs = pd.DataFrame({"variable": ["constante"] + noms, "coef": beta, "rapport_de_taux": np.exp(beta),
                          "erreur_std": se, "z": beta / se, "p": 2 * stats.norm.sf(np.abs(beta / se))})
    return coefs, mu, 1 - dev / dev0, disp


def binomiale_negative(y, X, offset, iterations=100):
    """Régression binomiale négative (variance mu + alpha mu²) avec offset, par maximum de vraisemblance.
    Alternance entre IRLS sur les coefficients à alpha fixé et maximisation du log de vraisemblance en alpha.
    X sans constante. Renvoie (beta, mu, alpha, log de vraisemblance)."""
    from scipy.optimize import minimize_scalar
    from scipy.special import gammaln
    n, k = X.shape
    Xc = np.column_stack([np.ones(n), X])
    beta = np.zeros(k + 1)
    beta[0] = np.log(max(y.sum(), 1e-9) / np.exp(offset).sum())
    alpha = .1

    def loglik(a, mu):
        r = 1 / a
        return np.sum(gammaln(y + r) - gammaln(r) - gammaln(y + 1) + r * np.log(r / (r + mu)) + y * np.log(mu / (r + mu)))

    for _ in range(iterations):
        for _ in range(25):
            eta = np.clip(Xc @ beta + offset, -30, 30)
            mu = np.exp(eta)
            w = mu / (1 + alpha * mu)
            z = eta - offset + (y - mu) / mu
            XtW = Xc.T * w
            nouveau = np.linalg.solve(XtW @ Xc + 1e-9 * np.eye(k + 1), XtW @ z)
            fini = np.max(np.abs(nouveau - beta)) < 1e-9
            beta = nouveau
            if fini:
                break
        mu = np.exp(np.clip(Xc @ beta + offset, -30, 30))
        res = minimize_scalar(lambda la: -loglik(np.exp(la), mu), bounds=(-12, 4), method="bounded")
        nouvel_alpha = float(np.exp(res.x))
        if abs(nouvel_alpha - alpha) < 1e-7:
            alpha = nouvel_alpha
            break
        alpha = nouvel_alpha
    mu = np.exp(np.clip(Xc @ beta + offset, -30, 30))
    return beta, mu, alpha, float(loglik(alpha, mu))


def modeles(agg, ref, ctx):
    """Effectif attendu compte tenu de la population et du profil sociodémographique
    (régression de Poisson, offset population), et écart observé / attendu par territoire."""
    coefs_all, ecarts, qualite = [], [], []
    niv = "epci"
    if niv not in ctx:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    n, dens, pop = tables(agg, ref, niv, "all")
    # seuls les indicateurs sociodémographiques de base expliquent l'effectif attendu, qui reste
    # « compte tenu du profil de la population » et jamais des bases complémentaires
    base = [c[0] for c in config.CONTEXTE]
    X = ctx[niv].reindex(dens.index)[[c for c in base if c in ctx[niv]]]
    X = X.drop(columns=[c for c in X.columns if X[c].notna().mean() < .9])
    if "densite_pop" in X:
        X["densite_pop"] = np.log1p(X["densite_pop"])
    noms = list(X.columns)
    for p in config.PROFESSIONS_PRINCIPALES:
        if p not in n or n[p].sum() < 100:
            continue
        d = pd.concat([n[p].rename("_y"), pop.rename("_pop"), X], axis=1).dropna()
        if len(d) < 50:
            continue
        Xm = d[noms].to_numpy(float)
        mu_, sd = Xm.mean(0), Xm.std(0)
        sd[sd == 0] = 1
        coefs, attendu, pseudo_r2, disp = poisson_robuste(d["_y"].to_numpy(float), (Xm - mu_) / sd,
                                                          np.log(d["_pop"].to_numpy(float)), noms)
        coefs.insert(0, "prof", p)
        coefs["ic95_bas"] = np.exp(coefs["coef"] - 1.96 * coefs["erreur_std"])
        coefs["ic95_haut"] = np.exp(coefs["coef"] + 1.96 * coefs["erreur_std"])
        hors = coefs["variable"] != "constante"
        coefs.loc[hors, "q_bh"] = benjamini_hochberg(coefs.loc[hors, "p"].to_numpy())
        coefs_all.append(coefs)
        e = pd.DataFrame({"code": d.index, "prof": p, "effectif": d["_y"].to_numpy(), "effectif_attendu": attendu,
                          "pop": d["_pop"].to_numpy()})
        e["observe"] = e["effectif"] / e["pop"] * 1e4
        e["attendu"] = e["effectif_attendu"] / e["pop"] * 1e4
        e["rapport"] = e["effectif"] / e["effectif_attendu"]
        e["manque"] = e["effectif_attendu"] - e["effectif"]
        # contrôle de solidité, modèle binomial négatif qui tient compte de la surdispersion
        y = d["_y"].to_numpy(float)
        _b, mu_nb, alpha, ll_nb = binomiale_negative(y, (Xm - mu_) / sd, np.log(d["_pop"].to_numpy(float)))
        e["effectif_attendu_nb"] = mu_nb
        e["rapport_nb"] = e["effectif"] / mu_nb
        ll_p = float(np.sum(stats.poisson.logpmf(y, attendu)))
        nb_param = Xm.shape[1] + 1
        retrait_p, retrait_nb = set(e.loc[(e["rapport"] < .5) & (e["effectif_attendu"] >= 5), "code"]),             set(e.loc[(e["rapport_nb"] < .5) & (e["effectif_attendu_nb"] >= 5), "code"])
        ecarts.append(e)
        qualite.append({"prof": p, "n": len(d), "pseudo_r2": pseudo_r2, "dispersion": disp, "alpha_nb": alpha,
                        "aic_poisson": 2 * nb_param - 2 * ll_p, "aic_nb": 2 * (nb_param + 1) - 2 * ll_nb,
                        "rho_rapports_poisson_nb": stats.spearmanr(e["rapport"], e["rapport_nb"])[0],
                        "retrait_communs": len(retrait_p & retrait_nb), "retrait_poisson": len(retrait_p),
                        "retrait_nb": len(retrait_nb)})
    return (pd.concat(coefs_all, ignore_index=True) if coefs_all else pd.DataFrame(),
            pd.concat(ecarts, ignore_index=True) if ecarts else pd.DataFrame(), pd.DataFrame(qualite))


def acp(Z):
    """Analyse en composantes principales d'une matrice déjà centrée et réduite (lignes, territoires, colonnes,
    variables). Renvoie les valeurs propres, la part d'inertie de chaque axe, les coordonnées des lignes et la
    corrélation de chaque variable avec chaque axe."""
    Z = np.asarray(Z, float)
    n = len(Z)
    U, sv, Vt = np.linalg.svd(Z, full_matrices=False)
    vp = sv ** 2 / n
    coords = U * sv
    # corrélation variable et axe, signe fixé pour que la plus forte charge de chaque axe soit positive
    charges = Vt.T * np.sqrt(vp)
    signe = np.sign(charges[np.abs(charges).argmax(0), range(charges.shape[1])])
    signe[signe == 0] = 1
    return vp, vp / vp.sum(), coords * signe, charges * signe


def silhouette(D, lab):
    """Silhouette moyenne d'une partition, D matrice des distances."""
    lab = np.asarray(lab)
    a = np.array([D[i, lab == lab[i]].sum() / max((lab == lab[i]).sum() - 1, 1) for i in range(len(lab))])
    b = np.array([min(D[i, lab == j].mean() for j in set(lab) if j != lab[i]) for i in range(len(lab))])
    return float(np.mean((b - a) / np.maximum(a, b)))


def cah_ward(Z, kmin=3, kmax=6):
    """Classification ascendante hiérarchique (Ward) sur les lignes de Z, nombre de classes choisi par la
    silhouette moyenne entre kmin et kmax. Déterministe. Renvoie (classes numérotées de 1 à k, k, silhouette,
    part de l'inertie expliquée par la partition)."""
    from scipy.cluster.hierarchy import fcluster, linkage
    Z = np.asarray(Z, float)
    arbre = linkage(Z, method="ward")
    D = cdist(Z, Z)
    meilleur = None
    for k in range(kmin, kmax + 1):
        lab = fcluster(arbre, k, criterion="maxclust")
        if len(set(lab)) < k:
            continue
        sil = silhouette(D, lab)
        if meilleur is None or sil > meilleur[2]:
            meilleur = (lab, k, sil)
    lab, k, sil = meilleur
    total = ((Z - Z.mean(0)) ** 2).sum()
    intra = sum(((Z[lab == c] - Z[lab == c].mean(0)) ** 2).sum() for c in set(lab))
    # classes renumérotées de la plus peuplée à la moins peuplée, pour un affichage stable
    ordre = {c: i + 1 for i, c in enumerate(pd.Series(lab).value_counts().index)}
    return np.array([ordre[c] for c in lab]), k, sil, 1 - intra / total


TYPOLOGIE_FAMILLES = {
    "sm": ["psychologue", "psychiatre", "q_psychiatrie_enfant", "psychotherapeute"],
    "sante": ["medecin_generaliste", "infirmier", "masseur_kinesitherapeute", "orthophoniste", "psychomotricien",
              "pharmacien", "chirurgien_dentiste", "sage_femme", "pediatre", "ens_medecin_specialiste"],
    "tout": None,   # professions principales des deux familles
}
# Professions décrites dans le profil de chaque groupe sans servir à former les groupes (version 2, 11 octobre 2026,
# demande de Lucas), toutes les spécialités médicales pour la santé et l'ensemble.
TYPOLOGIE_DECRITES = {f: [pid for _m, pid, _l, _g, fam in config.SPECIALITES_MEDECINS if fam == config.SANTE]
                      + [config.MEDECIN_AUTRE[0]] for f in ("sante", "tout")}


def typologie(agg, ref, rng=None):
    """Profils d'offre des intercommunalités, une typologie par famille (santé mentale, santé, ensemble).
    ACP sur le logarithme des densités centrées et réduites, puis classification ascendante hiérarchique (Ward)
    sur les mêmes données. Renvoie (affectations, profils, inertie des axes, charges, qualité)."""
    n, dens, pop = tables(agg, ref, "epci", "all")
    affect, profils, inertie, charges, qualite = [], [], [], [], []
    for fam, liste in TYPOLOGIE_FAMILLES.items():
        profs = [p for p in (liste or config.PROFESSIONS_PRINCIPALES) if p in dens and n[p].sum() >= 100]
        if len(profs) < 3:
            continue
        Z = np.log1p(dens[profs].to_numpy())
        Z = (Z - Z.mean(0)) / np.where(Z.std(0) == 0, 1, Z.std(0))
        vp, part, coords, ch = acp(Z)
        lab, k, sil, r2 = cah_ward(Z)
        affect.append(pd.DataFrame({"famille": fam, "code": dens.index, "classe": lab,
                                    "axe1": coords[:, 0], "axe2": coords[:, 1]}))
        decrites = [p for p in TYPOLOGIE_DECRITES.get(fam, []) if p in dens and p not in profs and n[p].sum() > 0]
        tous = profs + decrites
        nat = n[tous].sum() / pop.sum() * 1e4
        for c in range(1, k + 1):
            m = lab == c
            dc = n[tous][m].sum() / pop[m].sum() * 1e4
            for p in tous:
                profils.append({"famille": fam, "classe": c, "prof": p, "indice_vs_national": 100 * dc[p] / nat[p],
                                "territoires": int(m.sum()), "population": pop[m].sum(),
                                "dans_typologie": p in profs})
        inertie += [{"famille": fam, "axe": i + 1, "valeur_propre": vp[i], "part_inertie": part[i]} for i in range(len(vp))]
        charges += [{"famille": fam, "prof": p, "axe": a + 1, "correlation": ch[j, a]}
                    for j, p in enumerate(profs) for a in range(min(3, len(profs)))]
        qualite.append({"famille": fam, "classes": k, "silhouette": sil, "part_inertie_classes": r2,
                        "part_inertie_axes_1_2": part[:2].sum(), "variables": len(profs)})
        nom = {"sm": "santé mentale", "sante": "santé", "tout": "ensemble"}[fam]
        JOURNAL.controle(f"Typologie des EPCI, {nom}",
                         f"{k} classes, silhouette moyenne {sil:.2f}, classes {r2:.0%} de l'inertie, "
                         f"axes 1 et 2 de l'ACP {part[:2].sum():.0%}")
    if not affect:
        return None, None, None, None, None
    return (pd.concat(affect, ignore_index=True), pd.DataFrame(profils), pd.DataFrame(inertie),
            pd.DataFrame(charges), pd.DataFrame(qualite))


def spatial(agg, ref, voisins, rng):
    if not voisins:
        return None
    lignes = []
    for niv in ["epci", "dep"]:
        n, dens, _pop = tables(agg, ref, niv, "all")
        for p in config.PROFESSIONS_PRINCIPALES:
            if p in dens and n[p].sum() >= 100:
                I, pv = moran(np.log1p(dens[p]), voisins[niv], rng=rng)
                lignes.append({"niveau": niv, "prof": p, "moran_I": I, "p_permutation": pv})
    return pd.DataFrame(lignes)


def tension(agg, ref, offres):
    if offres is None or offres.empty:
        return None
    n, _d, _p = tables(agg, ref, "dep", "all")
    t = offres.copy()
    t["professionnels"] = [n.at[d, p] if (d in n.index and p in n.columns) else 0 for d, p in zip(t["dep"], t["prof"])]
    t["offres_pour_100_professionnels"] = 100 * t["offres"] / t["professionnels"].replace(0, np.nan)
    return t


def tout(agg, ref, ctx, voisins, offres, externes=None):
    rng = np.random.default_rng(config.GRAINE)
    R = {}
    log.info("analyse : inégalités")
    R["inegalites"], R["lorenz"] = inegalites(agg, ref, None)
    if ctx:
        log.info("analyse : corrélations avec le contexte")
        R["correlations_contexte"] = correlations_contexte(agg, ref, ctx, rng)
        log.info("analyse : gradient urbain-rural")
        R["classes_densite"], R["tests_classes_densite"] = classes_densite(agg, ref, ctx)
        log.info("analyse : modèles de densité attendue")
        R["modeles_coefficients"], R["ecarts_attendu"], R["modeles_qualite"] = modeles(agg, ref, ctx)
        log.info("analyse : offre selon le niveau de vie")
        R["concentration_revenu"], R["escalier_social"] = revenu(agg, ref, ctx, rng)
        log.info("analyse : offre face aux indicateurs de besoin")
        R["quadrants"] = quadrants(agg, ref, ctx)
        R["sensibilite_ile_de_france"] = sensibilite_sous_declaration(agg, ref, ctx)
        log.info("analyse : densité rapportée au public concerné")
        R["public_cible"], R["public_cible_territoires"] = densite_cible(agg, ref, ctx)
        log.info("analyse : qui porte l'offre")
        R["porte_offre"] = porte_offre(agg, ref, ctx)
    log.info("analyse : combinaisons d'offre et composition de la santé mentale")
    R["combinaisons"] = combinaisons(agg, ref)
    R["composition_sante_mentale"] = composition_sante_mentale(agg, ref)
    log.info("analyse : diagramme en entonnoir")
    R["entonnoir"], R["entonnoir_resume"], R["entonnoir_limites"] = entonnoir(agg, ref)
    R["correlations_professions"] = correlations_professions(agg, ref)
    log.info("analyse : typologie")
    (R["typologie_affectation"], R["typologie_profils"], R["acp_inertie"], R["acp_charges"],
     R["typologie_qualite"]) = typologie(agg, ref, rng)
    log.info("analyse : autocorrélation spatiale")
    R["spatial"] = spatial(agg, ref, voisins, rng)
    log.info("analyse : zones de désert et de concentration (Moran local)")
    R["lisa"] = lisa(agg, ref, voisins, rng)
    log.info("analyse : accessibilité (distances et méthode à deux étapes)")
    R["accessibilite"], R["accessibilite_communes"], R["accessibilite_epci"] = accessibilite(agg, ref, voisins)
    R["ombre_urbaine"] = ombre_urbaine(agg, ref, R["accessibilite_epci"])
    log.info("analyse : sensibilité de l'accessibilité à la portée")
    R["sensibilite_accessibilite"] = sensibilite_accessibilite(agg, ref, voisins)
    # temps de trajet calculés avant les croisements, qui s'en servent (audit du 4 octobre, 3.3)
    externes = externes or {}
    log.info("analyse : temps de trajet (INSEE) et comparaison avec l'APL (DREES)")
    R["temps_acces"] = temps_acces(externes.get("acces_route"), ref)
    if ctx is not None:
        log.info("analyse : loi inverse des soins, concordance des indicateurs de besoin, croisements")
        R["loi_inverse"] = loi_inverse(agg, ref, ctx, rng)
        R["concordance_besoins"] = concordance_besoins(ctx)
        R["croisements"] = croisements(agg, ref, ctx, rng, R["temps_acces"])
        from . import croisements_indicateurs
        log.info("analyse : croisement des indicateurs de santé mentale entre eux, régressions multiples")
        R["croisements_indicateurs"] = croisements_indicateurs.croiser(ctx, rng)
        R["regressions_indicateurs"] = croisements_indicateurs.regressions(ctx)
        from . import spatial_offre_besoin as sob
        log.info("analyse : Moran local bivarié offre et besoin, régression géographiquement pondérée")
        R["offre_besoin_lisa"] = sob.offre_besoin(agg, ref, ctx, voisins, rng)
        R["gwr_coefficients"], R["gwr_resume"] = sob.gwr_niveau_de_vie(agg, ref, ctx, voisins, rng)
    R["comparaison_route"] = comparaison_route(externes.get("acces_route"), R["accessibilite_communes"])
    R["comparaison_apl"] = comparaison_apl(externes.get("apl"), R["accessibilite_communes"],
                                           R["accessibilite_epci"], agg, ref)
    log.info("analyse : compléments pour les chercheurs (Theil, substitution, robustesse, niveaux, outre-mer)")
    R["decomposition_theil"] = decomposition_theil(agg, ref, ctx)
    R["substitution"] = substitution(agg, ref, ctx, rng)
    R["robustesse_gini"] = robustesse(agg, ref, R.get("inegalites"), rng)
    R["variance_niveaux"] = variance_niveaux(agg, ref)
    R["moran_residus"] = moran_residus(R, voisins, rng)
    R["outre_mer"] = outre_mer(agg, ref)
    R["tension"] = tension(agg, ref, offres)
    return R
