"""INSEE, données carroyées à 200 mètres (Filosofi 2019), pour placer le point de départ des distances là où vivent les
habitants (demande de Lucas du 29 octobre 2026).

Chaque commune reçoit le centre de sa population, moyenne des centres de ses carreaux de 200 mètres pondérée par le
nombre d'habitants du carreau (variable ind, imputée sous 11 ménages, indicatrice i_est_200). Un carreau partagé entre
plusieurs communes (lcog_geo) va à celle dont le contour contient son centre. Le champ du fichier est l'Hexagone, la
Corse, la Martinique et La Réunion. En Guadeloupe, en Guyane et à Mayotte, le point de la commune est celui que donne
la Base Adresse Nationale (chef-lieu, service de géocodage de l'IGN), faute de carreaux, et le centre du contour pour
une commune que ni l'une ni l'autre ne situe (config.LIMITES["centres_population"]). Les distances restent à vol
d'oiseau. Les coordonnées des carreaux sont projetées (Lambert azimutal européen, EPSG 3035, pour l'Hexagone, UTM 20
nord pour la Martinique, EPSG 5490, UTM 40 sud pour La Réunion, EPSG 2975, ellipsoïde GRS 80), converties ici en
longitude et latitude par les formules de Snyder (Map Projections, a Working Manual, USGS 1987), contrôlées sur des
points connus (tests)."""
from __future__ import annotations

import io
import math
import re
import zipfile

import numpy as np
import pandas as pd

from .. import config
from ..util import JOURNAL, lire_meta, log, telecharger

SOURCE = "INSEE, données carroyées à 200 m (Filosofi 2019)"
DEST = config.BRUT / "insee_carreaux_200m_filosofi2019_csv.zip"
CACHE = config.INTER / "centres_population_communes.parquet"
CACHE_BAN = config.INTER / "chefs_lieux_ban.parquet"
FICHIERS = ("carreaux_200m_met.csv", "carreaux_200m_mart.csv", "carreaux_200m_reun.csv")

# ellipsoïde GRS 80
A, F = 6378137.0, 1 / 298.257222101
E2 = 2 * F - F * F
E = math.sqrt(E2)


def _q(phi):
    s = np.sin(phi)
    return (1 - E2) * (s / (1 - E2 * s * s) - np.log((1 - E * s) / (1 + E * s)) / (2 * E))


def laea_inverse(x, y, lat0=52.0, lon0=10.0, fe=4321000.0, fn=3210000.0):
    """Lambert azimutal équivalent, aspect oblique, ellipsoïde (Snyder, formules 24-28 et 3-18), en degrés."""
    phi1, lam0 = math.radians(lat0), math.radians(lon0)
    qp, q1 = float(_q(math.pi / 2)), float(_q(phi1))
    b1 = math.asin(q1 / qp)
    rq = A * math.sqrt(qp / 2)
    m1 = math.cos(phi1) / math.sqrt(1 - E2 * math.sin(phi1) ** 2)
    d = A * m1 / (rq * math.cos(b1))
    x, y = np.asarray(x, float) - fe, np.asarray(y, float) - fn
    rho = np.hypot(x / d, d * y)
    c = 2 * np.arcsin(np.clip(rho / (2 * rq), -1, 1))
    with np.errstate(invalid="ignore", divide="ignore"):
        bp = np.where(rho > 0, np.arcsin(np.cos(c) * math.sin(b1) + d * y * np.sin(c) * math.cos(b1) / rho), b1)
    lam = lam0 + np.arctan2(x * np.sin(c), d * rho * math.cos(b1) * np.cos(c) - d * d * y * math.sin(b1) * np.sin(c))
    phi = (bp + (E2 / 3 + 31 * E2 ** 2 / 180 + 517 * E2 ** 3 / 5040) * np.sin(2 * bp)
           + (23 * E2 ** 2 / 360 + 251 * E2 ** 3 / 3780) * np.sin(4 * bp) + 761 * E2 ** 3 / 45360 * np.sin(6 * bp))
    return np.degrees(lam), np.degrees(phi)


def utm_inverse(x, y, zone, sud=False):
    """Mercator transverse universelle, ellipsoïde (Snyder, formules 8-18 à 8-25), en degrés."""
    k0, lam0 = 0.9996, math.radians(-183 + 6 * zone)
    x = np.asarray(x, float) - 500000.0
    y = np.asarray(y, float) - (10000000.0 if sud else 0.0)
    ep2 = E2 / (1 - E2)
    mu = y / k0 / (A * (1 - E2 / 4 - 3 * E2 ** 2 / 64 - 5 * E2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - E2)) / (1 + math.sqrt(1 - E2))
    p1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * np.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * np.sin(4 * mu)
          + 151 * e1 ** 3 / 96 * np.sin(6 * mu) + 1097 * e1 ** 4 / 512 * np.sin(8 * mu))
    c1, t1 = ep2 * np.cos(p1) ** 2, np.tan(p1) ** 2
    n1 = A / np.sqrt(1 - E2 * np.sin(p1) ** 2)
    r1 = A * (1 - E2) / (1 - E2 * np.sin(p1) ** 2) ** 1.5
    d = x / (n1 * k0)
    phi = p1 - (n1 * np.tan(p1) / r1) * (d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24
                                         + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2) * d ** 6 / 720)
    lam = lam0 + (d - (1 + 2 * t1 + c1) * d ** 3 / 6
                  + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2) * d ** 5 / 120) / np.cos(p1)
    return np.degrees(lam), np.degrees(phi)


# système de chaque fichier, d'après le préfixe des identifiants (CRS3035, CRS5490, CRS2975)
PROJECTIONS = {"3035": lambda x, y: laea_inverse(x, y), "5490": lambda x, y: utm_inverse(x, y, 20),
               "2975": lambda x, y: utm_inverse(x, y, 40, sud=True)}
IDCAR = re.compile(r"^CRS(\d+)RES(\d+)mN(\d+)E(\d+)$")


def centres_carreaux(ids: pd.Series) -> pd.DataFrame:
    """Longitude et latitude du centre de chaque carreau, d'après son identifiant (coin sud-ouest et côté)."""
    p = ids.str.extract(IDCAR.pattern)
    p.columns = ["crs", "cote", "n", "e"]
    out = pd.DataFrame(index=ids.index, columns=["lon", "lat"], dtype=float)
    for crs, g in p.groupby("crs"):
        demi = g["cote"].astype(float) / 2
        lon, lat = PROJECTIONS[crs](g["e"].astype(float) + demi, g["n"].astype(float) + demi)
        out.loc[g.index, "lon"], out.loc[g.index, "lat"] = lon, lat
    return out


def _lire_carreaux() -> pd.DataFrame:
    """Les trois fichiers, extraits dans un dossier temporaire de donnees/intermediaire puis lus colonne par colonne,
    pour ne pas tenir en mémoire les fichiers entiers (environ 2,3 millions de carreaux)."""
    import shutil

    import py7zr
    dossier = config.INTER / "insee_carreaux_200m"
    dossier.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(DEST) as z, py7zr.SevenZipFile(io.BytesIO(z.read(z.namelist()[0]))) as a:
        a.extract(path=dossier, targets=list(FICHIERS))
    try:
        return pd.concat([pd.read_csv(dossier / nom, usecols=["idcar_200m", "lcog_geo", "ind", "i_est_200"],
                                      dtype={"idcar_200m": str, "lcog_geo": str}) for nom in FICHIERS],
                         ignore_index=True)
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def _commune(car: pd.DataFrame, formes: dict | None, actuelle) -> pd.Series:
    """Commune de chaque carreau, la seule citée par lcog_geo, sinon la première de la liste dont le contour contient le
    centre du carreau (la première citée si aucun contour ne le contient). Un test vectorisé par commune candidate."""
    codes = car["lcog_geo"].fillna("").str.findall(r"\d[\dAB]\d{3}")
    com = codes.str[0].map(lambda c: actuelle(c) if isinstance(c, str) else None)
    plusieurs = codes.str.len() > 1
    if plusieurs.any() and formes:
        import shapely
        e = codes[plusieurs].explode().rename("code").to_frame()
        e["rang"] = e.groupby(level=0).cumcount()
        e["code"] = e["code"].map(actuelle)
        e = e.reset_index(names="i")
        e["dedans"] = False
        xs, ys = car["lon"].to_numpy(), car["lat"].to_numpy()
        for c, g in e.groupby("code"):
            f = formes.get(c)
            if f is not None:
                e.loc[g.index, "dedans"] = shapely.contains_xy(f, xs[g["i"].to_numpy()], ys[g["i"].to_numpy()])
        choix = e[e["dedans"]].sort_values(["i", "rang"]).drop_duplicates("i").set_index("i")["code"]
        com.loc[choix.index] = choix
    return com


def centres_population(ref, formes: dict | None, hors_ligne=False, rafraichir=False) -> dict:
    """Centre de la population de chaque commune couverte, {code: (longitude, latitude)}. Calculé une fois par version
    du fichier de l'INSEE et gardé dans donnees/intermediaire."""
    if not hors_ligne:
        telecharger(config.INSEE_CARREAUX_URL, DEST, "insee_carreaux", rafraichir, taille_min=10_000_000,
                    extra_meta={"maj_source": config.INSEE_CARREAUX_DATE})
    elif not DEST.exists():
        raise FileNotFoundError(DEST)
    meta = lire_meta(DEST)
    cle = f"{meta.get('telecharge_le', '')}|{meta.get('octets', '')}|{'contours' if formes else 'sans contours'}"
    if CACHE.exists():
        c = pd.read_parquet(CACHE)
        if len(c) and c["version"].iloc[0] == cle:
            return {k: (x, y) for k, x, y in zip(c["code"], c["lon"], c["lat"])}
    car = _lire_carreaux()
    car = pd.concat([car, centres_carreaux(car["idcar_200m"])], axis=1)
    anciens, actuels = ref.anciens, set(ref.communes["code"])
    car["code"] = _commune(car, formes, lambda c: c if c in actuels else anciens.get(c, c))
    car = car[car["code"].isin(actuels) & (car["ind"] > 0)]
    g = car.assign(px=car["lon"] * car["ind"], py=car["lat"] * car["ind"]).groupby("code")
    t = pd.DataFrame({"pop": g["ind"].sum(), "lon": g["px"].sum() / g["ind"].sum(), "lat": g["py"].sum() / g["ind"].sum(),
                      "carreaux": g.size(), "imputes": g["i_est_200"].sum()}).reset_index()
    t["version"] = cle
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    t.to_parquet(CACHE, index=False)
    JOURNAL.note(SOURCE, "ok", f"{len(car)} carreaux habités, {len(t)} communes situées par le centre de leur population",
                 url=config.INSEE_CARREAUX_URL, lignes=len(car), date_donnees=config.INSEE_CARREAUX_DATE)
    return {k: (x, y) for k, x, y in zip(t["code"], t["lon"], t["lat"])}


def chefs_lieux_ban(ref, codes, hors_ligne=False) -> dict:
    """Point de chaque commune dans la Base Adresse Nationale (résultat de type commune, le chef-lieu), par le service
    de géocodage de l'IGN, gardé dans donnees/intermediaire. Hors ligne, seul ce qui est gardé sert."""
    t = pd.read_parquet(CACHE_BAN) if CACHE_BAN.exists() else pd.DataFrame(columns=["code", "lon", "lat"])
    manque = [c for c in codes if c not in set(t["code"])]
    if manque and not hors_ligne:
        import requests
        noms = ref.communes.set_index("code")["nom"]
        lignes = []
        for c in manque:
            try:
                r = requests.get(config.GEOCODAGE_RECHERCHE, params={"q": noms.get(c, c), "type": "municipality",
                                                                      "citycode": c, "limit": 1}, timeout=60).json()
                f = (r.get("features") or [None])[0]
                if f and f["properties"].get("citycode") == c:
                    lignes.append((c, *f["geometry"]["coordinates"]))
            except Exception as e:  # noqa: BLE001
                log.warning("chef-lieu de %s introuvable : %s", c, e)
        if lignes:
            t = pd.concat([t, pd.DataFrame(lignes, columns=["code", "lon", "lat"])], ignore_index=True)
            CACHE_BAN.parent.mkdir(parents=True, exist_ok=True)
            t.to_parquet(CACHE_BAN, index=False)
    return {k: (x, y) for k, x, y in zip(t["code"], t["lon"], t["lat"]) if k in set(codes)}


DOM_SANS_CARREAUX = ("971", "973", "976")


def centres_depart(ref, geo: dict, formes: dict | None, hors_ligne=False, rafraichir=False) -> dict:
    """Point de départ des distances de chaque commune, le centre de sa population, sinon, en Guadeloupe, en Guyane et
    à Mayotte, son chef-lieu dans la Base Adresse Nationale, sinon le centre de son contour (geo). Contrôle dans le
    journal, par origine du point et pour chaque département d'outre-mer."""
    try:
        pop = centres_population(ref, formes, hors_ligne, rafraichir)
    except Exception as e:  # noqa: BLE001
        log.warning("données carroyées de l'INSEE indisponibles : %s", e)
        JOURNAL.note(SOURCE, "erreur", str(e)[:300], url=config.INSEE_CARREAUX_URL)
        pop = {}
    dep = ref.communes.set_index("code")["dep"]
    sans = [c for c in geo if c not in pop and dep.get(c) in DOM_SANS_CARREAUX]
    try:
        ban = chefs_lieux_ban(ref, sans, hors_ligne) if sans else {}
    except Exception as e:  # noqa: BLE001
        log.warning("chefs-lieux de la Base Adresse Nationale indisponibles : %s", e)
        ban = {}
    origine = {c: "population" if c in pop else "chef-lieu" if c in ban else "contour" for c in geo}
    habitees = set(ref.communes.loc[ref.communes["pop"] > 0, "code"])
    n = pd.Series({c: o for c, o in origine.items() if c in habitees}).value_counts()
    JOURNAL.controle("Point de départ des distances, communes habitées situées par le centre de leur population, leur "
                     "chef-lieu ou le centre de leur contour",
                     f"{int(n.get('population', 0))} par leur population, {int(n.get('chef-lieu', 0))} par leur chef-lieu, "
                     f"{int(n.get('contour', 0))} par leur contour")
    for d in ("971", "972", "973", "974", "976"):
        o = pd.Series({c: x for c, x in origine.items() if dep.get(c) == d and c in habitees}).value_counts()
        JOURNAL.controle(f"Point de départ des distances, département {d}",
                         ", ".join(f"{int(v)} {k}" for k, v in o.items()) or "aucune commune")
    return {c: pop.get(c) or ban.get(c) or geo[c] for c in geo}
