"""Temps de route vers nos propres structures de soins, par le service d'isochrone de la Géoplateforme de l'IGN
(décision du 30 octobre 2026, note docs/note_temps_trajet_2026-10-30.md, méthode 1).

Le temps de l'INSEE vers la psychiatrie ambulatoire ignore vraisemblablement un CMP sur trois. Ici, le temps est
calculé vers les structures que nous recensons (FINESS et ROR réunis, les mêmes que pour les distances). Pour chaque
structure d'un type, le service rend la zone d'où l'on arrive à la structure en voiture en 10, 15, 20, 30 et 45
minutes (isochrone d'arrivée, moteur Valhalla sur la BD TOPO, profil voiture). Chaque carreau habité de 200 m de
l'INSEE (Filosofi 2019) reçoit la plus petite tranche dont une zone contient son centre, comme dans l'étude de la DREES
sur les maternités (Études et Résultats n° 1201, juillet 2021, carreaux de 200 m et distancier OSRM). En Guadeloupe, en
Guyane et à Mayotte, faute de carreaux, le point de la commune est son chef-lieu. On en tire, par territoire, la part
des habitants à plus de 15, 20, 30 et 45 minutes et un temps médian interpolé dans sa tranche.

Service, vérifié par des appels le 30 octobre 2026 : https://data.geopf.fr/navigation/isochrone, sans clé, ressource
bdtopo-valhalla (bdtopo-osrm, que conseille la documentation, n'existe plus), version du réseau rendue à chaque réponse
(resourceVersion, refaite presque chaque jour, notée avec chaque isochrone). Limite d'usage de 5 requêtes par seconde
et par adresse IP pour l'isochrone (conditions générales d'utilisation de la Géoplateforme, version du 15 octobre 2024,
annexe 3, article 3.2), erreur 429 et blocage de 5 secondes au-delà. Limite revue le 31 octobre 2026 sur la
documentation de la Géoplateforme, 5 requêtes par seconde et par adresse IP pour le calcul d'isochrone
(https://ignf.github.io/cartes.gouv.fr-documentation/fr/guides-utilisateur/acceder-aux-geodonnees/limites-d-usage et
https://geoservices.ign.fr/node/1612). 4 requêtes par seconde au plus ici, recul progressif après une erreur 429 ou
5xx, arrêt quand plus de 2 % des appels échouent (TAUX_ERREURS_MAX). Seules les parts d'habitants sortent du calcul,
jamais les contours des isochrones. Chaque isochrone est gardée dans donnees/intermediaire/trajets/ (une ligne par isochrone, écrite dès
la réponse), si bien qu'un calcul interrompu reprend où il s'était arrêté et qu'une mise à jour ne demande que les
structures nouvelles ou déplacées.

Limites : trajet en voiture aux vitesses du réseau, sans trafic ni heure de la journée, ni transports en commun ; une
structure placée au centre de sa commune faute d'adresse donne un temps approché. Les résultats ne sont pas publiés tant
que leur réutilisation n'est pas établie (pipeline/licences.py, « cgu-geoplateforme »).

    python -m pipeline.trajets pilote --dep 18            pilote du Cher (appels au service)
    python -m pipeline.trajets pilote --dep 18 --cache    même calcul sur le seul cache, sans appel
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

import numpy as np
import pandas as pd

from . import config
from .util import JOURNAL, log

URL = "https://data.geopf.fr/navigation/isochrone"
RESSOURCE = "bdtopo-valhalla"
SEUILS = (10, 15, 20, 30, 45)                  # minutes, bornes des tranches
DEBIT = 4.0                                    # requêtes par seconde au plus (limite du service, 5)
TAUX_ERREURS_MAX = 0.02                        # part des appels en erreur au-delà de laquelle le calcul s'arrête
APPELS_AVANT_TAUX = 200                        # appels avant de juger ce taux
TOLERANCE = 0.0005                             # simplification des contours en degrés (environ 50 m)
MARGE_KM = 90                                  # structures cherchées autour de la zone (45 minutes de route au plus)
DOSSIER = config.INTER / "trajets"
# types du pilote, la psychiatrie ambulatoire, et les urgences et les maternités qui servent à la validation (temps de
# l'INSEE pour les urgences, étude de la DREES pour les maternités)
TYPES_PILOTE = ("lieu_cmp_adultes", "lieu_cmp_enfants", "lieu_cattp", "lieu_hdj_psy_adultes", "lieu_urgences",
                "lieu_maternite")


class TropDErreurs(Exception):
    """Plus de TAUX_ERREURS_MAX des appels au service ont échoué, le calcul s'arrête (il reprendra du cache)."""


class Service:
    """Appels au service d'isochrone, au plus `debit` par seconde, avec reprise après une erreur 429 (attente de
    l'en-tête Retry-After, 5 secondes sinon) ou une panne passagère (attente croissante). ouvrir, horloge et dormir
    sont remplaçables pour les tests."""

    def __init__(self, debit=DEBIT, ouvrir=None, horloge=time.monotonic, dormir=time.sleep, essais=6):
        self.intervalle = 1 / debit
        self.ouvrir = ouvrir or (lambda url: urllib.request.urlopen(url, timeout=60))
        self.horloge, self.dormir, self.essais = horloge, dormir, essais
        self.prochain = 0.0
        self.appels = self.refus = self.erreurs = 0

    def _attendre(self):
        t = self.horloge()
        if t < self.prochain:
            self.dormir(self.prochain - t)
        self.prochain = max(t, self.prochain) + self.intervalle

    def _erreur(self):
        self.erreurs += 1
        if self.appels >= APPELS_AVANT_TAUX and self.erreurs / self.appels > TAUX_ERREURS_MAX:
            raise TropDErreurs(f"{self.erreurs} appels en erreur sur {self.appels} "
                               f"({self.erreurs / self.appels:.1%}), au-delà de {TAUX_ERREURS_MAX * 100:.0f} %")

    def isochrone(self, lon: float, lat: float, minutes: int) -> dict:
        q = urllib.parse.urlencode({"resource": RESSOURCE, "profile": "car", "costType": "time", "timeUnit": "minute",
                                    "costValue": minutes, "direction": "arrival", "point": f"{lon:.6f},{lat:.6f}",
                                    "geometryFormat": "geojson"})
        for k in range(self.essais):
            self._attendre()
            self.appels += 1
            try:
                with self.ouvrir(f"{URL}?{q}") as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    self.refus += 1
                    self._erreur()
                    self.dormir(max(float((e.headers or {}).get("Retry-After") or 5) + 1, min(60, 2 ** k)))
                elif e.code >= 500:
                    self._erreur()
                    self.dormir(min(60, 2 ** k))
                else:
                    raise
            except (urllib.error.URLError, TimeoutError):
                self._erreur()
                self.dormir(min(60, 2 ** k))
        raise RuntimeError(f"isochrone impossible après {self.essais} essais ({lon:.4f}, {lat:.4f}, {minutes} min)")


# structures restées sans une de leurs isochrones (échec du service, ou absente du cache sans appel), (type, clé)
SANS_ISOCHRONE: set = set()


def cle_structure(s) -> str:
    """Clé d'une structure dans le cache, son identifiant et son emplacement : une structure déplacée est recalculée."""
    return f"{s['id_structure']}|{float(s['lon']):.5f}|{float(s['lat']):.5f}"


def lire_cles(type_lieu: str) -> set:
    """Clés (structure, seuil) en cache pour un type, sans lire les contours."""
    f = DOSSIER / f"{type_lieu}.jsonl"
    if not f.exists():
        return set()
    out = set()
    for ligne in f.open(encoding="utf-8"):
        if ligne.strip():
            x = json.loads(ligne)
            out.add((x["cle"], int(x["seuil"])))
    return out


def controle_appels(val: dict) -> str:
    """Phrase du contrôle des appels (calcul national, puis reprise dans le journal de l'exécution)."""
    a, e = int(val.get("appels") or 0), int(val.get("erreurs") or 0)
    taux = f"{e / a * 100:.2f} %".replace(".", ",") if a else "sans objet"
    return (f"{a} appels lors du dernier calcul, {e} en erreur ({taux}, arrêt au-delà de {TAUX_ERREURS_MAX * 100:.0f} %), "
            f"{int(val.get('refus_429') or 0)} refus pour débit, {int(val.get('structures_sans_isochrone') or 0)} "
            f"structures sans isochrone (attendu, aucune), {int(val.get('isochrones_en_cache') or 0)} isochrones en cache")


def lire_cache(type_lieu: str) -> dict:
    """{(clé, seuil): (géométrie, version du réseau)} pour un type, depuis donnees/intermediaire/trajets/<type>.jsonl."""
    import shapely
    f = DOSSIER / f"{type_lieu}.jsonl"
    out = {}
    if f.exists():
        for ligne in f.read_text(encoding="utf-8").splitlines():
            if ligne.strip():
                x = json.loads(ligne)
                out[(x["cle"], int(x["seuil"]))] = (shapely.from_wkt(x["wkt"]), x.get("version", ""))
    return out


def isochrones(structures: pd.DataFrame, type_lieu: str, service: Service | None, seuils=SEUILS) -> dict:
    """Isochrones de chaque structure du type, {seuil: [géométries]}, prises dans le cache ou demandées au service
    (service None : cache seul). Chaque réponse est écrite dans le cache dès qu'elle arrive."""
    import shapely
    cache = lire_cache(type_lieu)
    DOSSIER.mkdir(parents=True, exist_ok=True)
    out = {m: [] for m in seuils}
    manquantes = 0
    with open(DOSSIER / f"{type_lieu}.jsonl", "a", encoding="utf-8") as f:
        for _, s in structures.iterrows():
            cle = cle_structure(s)
            for m in seuils:
                if (cle, m) not in cache:
                    if service is None:
                        manquantes += 1
                        continue
                    try:
                        r = service.isochrone(float(s["lon"]), float(s["lat"]), m)
                    except RuntimeError as e:
                        # structure laissée sans cette isochrone, comptée (contrôle du journal), reprise au calcul suivant
                        log.warning("trajets, %s : %s", type_lieu, e)
                        SANS_ISOCHRONE.add((type_lieu, cle))
                        continue
                    g = shapely.make_valid(shapely.geometry.shape(r["geometry"])).simplify(TOLERANCE)
                    cache[(cle, m)] = (g, r.get("resourceVersion", ""))
                    f.write(json.dumps({"cle": cle, "seuil": m, "wkt": g.wkt, "version": r.get("resourceVersion", ""),
                                        "date": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False) + "\n")
                    f.flush()
                out[m].append(cache[(cle, m)][0])
    if manquantes:
        log.warning("trajets, %s : %s isochrones absentes du cache", type_lieu, manquantes)
        SANS_ISOCHRONE.update((type_lieu, cle_structure(s)) for _, s in structures.iterrows()
                              if any((cle_structure(s), m) not in cache for m in seuils))
    return out


def versions_reseau(type_lieu: str) -> list[str]:
    return sorted({v for _g, v in lire_cache(type_lieu).values() if v})


def tranches(lon, lat, isos: dict) -> np.ndarray:
    """Pour chaque point, la plus petite borne de temps dont une isochrone le contient, l'infini au-delà de la plus
    grande (plus de 45 minutes)."""
    import shapely
    pts = shapely.points(np.asarray(lon, float), np.asarray(lat, float))
    t = np.full(len(pts), np.inf)
    for m in sorted(isos):
        geoms = [g for g in isos[m] if g is not None and not g.is_empty]
        if not geoms:
            continue
        reste = np.flatnonzero(np.isinf(t))
        if not len(reste):
            break
        i, _j = shapely.STRtree(geoms).query(pts[reste], predicate="within")
        t[reste[np.unique(i)]] = m
    return t


def mediane_tranches(t: np.ndarray, w: np.ndarray, seuils=SEUILS) -> float:
    """Temps médian des habitants, interpolé dans sa tranche en supposant les habitants répartis également dans la
    tranche (comme la médiane de l'histogramme de l'INSEE, analyses.medianes_histogramme). NaN quand la médiane tombe
    au-delà de la plus grande borne."""
    w = np.asarray(w, float)
    if w.sum() <= 0:
        return np.nan
    bornes = (0,) + tuple(seuils)
    moitie, cumul = w.sum() / 2, 0.0
    for a, b in zip(bornes[:-1], bornes[1:]):
        p = w[np.asarray(t) == b].sum()
        if cumul + p >= moitie and p > 0:
            return a + (moitie - cumul) / p * (b - a)
        cumul += p
    return np.nan


def resumer(points: pd.DataFrame, cles: list[str]) -> pd.DataFrame:
    """Par groupe (cles) et par type, habitants, temps médian et parts à plus de 15, 20, 30 et 45 minutes. points a
    les colonnes type, minutes (borne de la tranche, infini au-delà de 45), pop et les colonnes de cles."""
    lignes = []
    for k, g in points.groupby(cles + ["type"]):
        w, t = g["pop"].to_numpy(float), g["minutes"].to_numpy(float)
        if w.sum() <= 0:
            continue
        d = dict(zip(cles + ["type"], k if isinstance(k, tuple) else (k,)))
        d.update({"habitants": w.sum(), "temps_median_min": mediane_tranches(t, w)})
        for s in (15, 20, 30, 45):
            d[f"part_plus_{s}_min"] = w[t > s].sum() / w.sum()
        lignes.append(d)
    return pd.DataFrame(lignes)


# ---------------------------------------------------------------- points de départ
def points_habitants(ref, deps: set[str] | None = None) -> pd.DataFrame:
    """Carreaux habités de 200 m (longitude, latitude, habitants, commune), gardés en cache dans
    donnees/intermediaire/trajets/carreaux.parquet, puis le chef-lieu des communes sans carreaux (Guadeloupe, Guyane,
    Mayotte) avec leur population. Un carreau partagé entre plusieurs communes va à la première citée par l'INSEE."""
    from .sources import insee_carreaux as ic
    f = DOSSIER / "carreaux.parquet"
    if f.exists():
        car = pd.read_parquet(f)
    else:
        brut = ic._lire_carreaux()
        brut = pd.concat([brut, ic.centres_carreaux(brut["idcar_200m"])], axis=1)
        actuels, anciens = set(ref.communes["code"]), ref.anciens
        brut["code"] = ic._commune(brut, None, lambda c: c if c in actuels else anciens.get(c, c))
        brut = brut[brut["code"].isin(actuels) & (brut["ind"] > 0)]
        car = pd.DataFrame({"lon": brut["lon"].astype("float32"), "lat": brut["lat"].astype("float32"),
                            "pop": brut["ind"].astype("float32"), "code": brut["code"].astype(str)})
        DOSSIER.mkdir(parents=True, exist_ok=True)
        car.to_parquet(f, index=False)
    com = ref.communes.set_index("code")
    sans = sorted(set(com.index) - set(car["code"]))
    if sans:
        ban = ic.chefs_lieux_ban(ref, sans, hors_ligne=True)
        car = pd.concat([car, pd.DataFrame({"lon": [ban[c][0] for c in sans if c in ban],
                                            "lat": [ban[c][1] for c in sans if c in ban],
                                            "pop": [float(com.at[c, "pop"]) for c in sans if c in ban],
                                            "code": [c for c in sans if c in ban]})], ignore_index=True)
    car["dep"] = car["code"].map(com["dep"])
    car["epci"] = car["code"].map(com["epci"])
    return car[car["dep"].isin(deps)] if deps else car


def structures(types=TYPES_PILOTE) -> pd.DataFrame:
    """Structures des types demandés avec leurs coordonnées, depuis lieux_soins.csv de la dernière version (les mêmes
    que pour les distances, lieux.distances)."""
    dossiers = sorted(d for d in config.RESULTATS.glob("20*") if (d / "lieux_soins.csv").exists())
    if not dossiers:
        raise FileNotFoundError("aucun lieux_soins.csv dans resultats/")
    t = pd.read_csv(dossiers[-1] / "lieux_soins.csv", sep=";", dtype=str,
                    usecols=["id_structure", "type", "latitude", "longitude", "dep"])
    t = t[t["type"].isin(types)].rename(columns={"latitude": "lat", "longitude": "lon"})
    # CSV publiés en virgule décimale (export.py)
    for c in ("lat", "lon"):
        t[c] = pd.to_numeric(t[c].str.replace(",", ".", regex=False), errors="coerce")
    t = t.dropna(subset=["lat", "lon"])
    if t.empty:
        raise ValueError("aucune structure avec ses coordonnées dans lieux_soins.csv")
    return t


def autour(s: pd.DataFrame, pts: pd.DataFrame, km=MARGE_KM) -> pd.DataFrame:
    """Structures à moins de km de l'enveloppe des points (au-delà, 45 minutes de route ne suffisent pas)."""
    dlat, dlon = km / 111.0, km / (111.0 * np.cos(np.radians(pts["lat"].mean())))
    return s[s["lat"].between(pts["lat"].min() - dlat, pts["lat"].max() + dlat)
             & s["lon"].between(pts["lon"].min() - dlon, pts["lon"].max() + dlon)]


# ---------------------------------------------------------------- validation
# repère publié pour les maternités (texte lu le 30 octobre 2026) : DREES, Bergonzoni A., avec Simon M., « La part des
# femmes en âge de procréer résidant à plus de 45 minutes d'une maternité augmente entre 2000 et 2017 », Études et
# Résultats n° 1201, juillet 2021. Femmes de 15 à 44 ans, carreaux de 200 m, distancier OSRM sur OpenStreetMap 2018,
# maternités de la SAE 2017. France : temps médian de 9 minutes, autour de 7 % à plus de 30 minutes, entre 1 et 2 % à
# plus de 45 minutes ; Nièvre, 16 % à plus de 45 minutes en 2017. Le nombre de maternités a baissé depuis (496 en 2017,
# 445 en 2024 d'après le Panorama 2026 de la DREES, fiche 19) et nos parts portent sur tous les habitants, l'écart attendu
# va donc dans le sens d'un éloignement plus grand ici.
REPERE_DREES = {"source": "DREES, Études et Résultats n° 1201, juillet 2021",
                "url": "https://drees.solidarites-sante.gouv.fr/sites/default/files/2021-07/ER1201.pdf",
                "annee_donnees": 2017, "france_median_min": 9, "france_plus_30": 0.07, "france_plus_45": (0.01, 0.02),
                "par_departement_plus_45": {"58": 0.16}}
def plausibilite(com_temps: pd.Series, com_km: pd.Series) -> dict:
    """Temps médian de chaque commune face à sa distance à vol d'oiseau à la structure la plus proche. La règle qui
    écarte le temps de l'INSEE vers la psychiatrie ambulatoire (plus de 3 minutes par km plus 10 minutes,
    config.ROUTE_CMP_PENTE et ROUTE_CMP_MARGE) doit ne retenir presque aucune commune, et aucun temps ne doit être plus
    court que la distance parcourue à 100 km/h (0,6 minute par km)."""
    j = pd.DataFrame({"t": com_temps, "km": com_km}).dropna()
    j = j[np.isfinite(j["t"]) & np.isfinite(j["km"])]
    trop_long = j["t"] > config.ROUTE_CMP_PENTE * j["km"] + config.ROUTE_CMP_MARGE
    # la tranche donne une borne haute à 5 ou 10 minutes près, la comparaison au plus court se fait sur la borne basse
    trop_court = j["t"] + 10 < 0.6 * j["km"]
    return {"communes": len(j), "trop_long": int(trop_long.sum()), "trop_court": int(trop_court.sum()),
            "rho_spearman": float(j["t"].corr(j["km"], method="spearman")) if len(j) > 20 else np.nan}


def comparer_insee(nous: pd.DataFrame, ar, equipement: str = "urgences") -> dict:
    """Commune par commune, part des habitants à plus de 30 minutes et temps, face au temps de l'INSEE pour un équipement
    où l'INSEE et FINESS concordent (urgences, D106). nous a les colonnes code, part_plus_30_min, temps_median_min,
    habitants."""
    code = next((d["code"] for d in ar["defs"] if d["id"] == equipement), None)
    c = ar["communes"]
    x = c[c["typeeq_id"] == code].groupby("depcom")[["pop", "pop_calcule", "pd", "sup_30"]].sum()
    insee = pd.DataFrame({"insee_moyen": x["pd"] / x["pop_calcule"].where(x["pop_calcule"] > 0),
                          "insee_30": x["sup_30"] / x["pop_calcule"].where(x["pop_calcule"] > 0)})
    j = nous.set_index("code").join(insee, how="inner").dropna(subset=["insee_30"])
    w = j["habitants"]
    return {"communes": len(j),
            "part_30_nous": float((j["part_plus_30_min"] * w).sum() / w.sum()),
            "part_30_insee": float((j["insee_30"] * w).sum() / w.sum()),
            "ecart_absolu_moyen_30": float(((j["part_plus_30_min"] - j["insee_30"]).abs() * w).sum() / w.sum()),
            "rho_temps": float(j["temps_median_min"].corr(j["insee_moyen"], method="spearman")),
            "ecart_temps_median_min": float((j["temps_median_min"] - j["insee_moyen"]).median())}


# ---------------------------------------------------------------- calcul
# types du calcul national, ceux du pilote et les autres structures de psychiatrie et de l'enfance suivies par l'atlas
TYPES_NATIONAL = TYPES_PILOTE + ("lieu_hdj_psy_enfants", "lieu_hc_psy_adultes", "lieu_cmpp", "lieu_camsp", "lieu_csapa")
# Décision de Lucas du 31 octobre 2026 (note docs/note_temps_trajet_2026-10-30.md, « D'où vient l'écart ») : chiffre
# principal à l'échelle de l'INSEE, la fourchette du moteur prudent dans « Comment lire », les SMUR comptés avec les
# urgences. Même origine (carreaux de 200 m) et même destination, le moteur de la Géoplateforme met 1,31 fois le temps
# du distancier de l'INSEE (Metric-OSRM), rapport médian commune par commune sur les urgences (outils/
# calibrage_trajets.py). Ce rapport n'est pas constant, 1,13 dans le rural peu dense où sont les longs trajets, 1,34 à
# 1,40 en ville : avec un seul facteur, la part à plus de 30 minutes des urgences tombait à 3,6 % contre 5,5 % pour
# l'INSEE (calcul national du 31 octobre 2026). Chaque seuil T de l'INSEE est donc lu sur l'isochrone dont la part des
# habitants au-delà reproduit celle de l'INSEE sur les urgences, commune par commune (choix (b) de la séance principale
# du 31 octobre 2026) : 15 sur 20 minutes (calé à 19,6), 20 sur 26 (calé à 25,0, seuil existant gardé), 30 sur 36
# (calé entre 35,2 et 36,5). L'INSEE ne publie pas de part au-delà de 10 ni de 45 minutes : 10 sur 13 et 45 sur 59
# minutes, au rapport médian. La validation se fait sur les maternités face à la DREES (test
# test_trajets_references_publiees).
RAPPORT_MOTEUR = 1.31
SEUILS_INSEE = SEUILS
SEUILS_ICI = (13, 20, 26, 36, 59)
# références publiées (test test_trajets_references_publiees, décision de la séance principale du 1er novembre 2026).
# L'INSEE, même nature de mesure (mêmes communes, même année de population, même destination), valide le calage à 1 point
# près. La DREES mesure les femmes de 15 à 44 ans en 2017, avant des fermetures de maternités : une comparaison
# expliquée, pas une validation. Son écart est écrit et chiffré sur la page méthode et dans « Comment lire » ; au-delà
# de 4 points, ce serait un défaut et non une différence de champ.
TOLERANCES = {"urgences_insee_plus_30": 0.01, "maternites_drees_ecart_max": 0.04}
# destinations réunies, l'équipement « Urgences » (D106) de la base permanente des équipements regroupe « les services
# d'intervention (SAMU - SMUR) et d'accueil » (INSEE, liste des types d'équipements de la BPE au 1er janvier 2025)
DESTINATIONS = {"lieu_urgences": ("lieu_urgences", "lieu_smur")}


def isochrones_destinations(tout: pd.DataFrame, tid: str, service, seuils, pts: pd.DataFrame | None = None) -> dict:
    """Isochrones de toutes les structures qui comptent comme destination du type (le type lui-même, et les SMUR pour
    les urgences), {seuil: [géométries]}. pts, les points de départ, limite les structures à celles qui peuvent être
    atteintes (calcul d'une zone)."""
    out = {m: [] for m in seuils}
    for dt in DESTINATIONS.get(tid, (tid,)):
        s = tout[tout["type"] == dt]
        if pts is not None:
            s = autour(s, pts)
        iso = isochrones(s, dt, service, seuils)
        for m in seuils:
            out[m] += iso[m]
    return out


def echelle_insee(isos_ici: dict) -> dict:
    """Isochrones de nos seuils SEUILS_ICI rangées sous les seuils de l'INSEE qu'elles représentent."""
    return {si: isos_ici[sc] for si, sc in zip(SEUILS_INSEE, SEUILS_ICI) if sc in isos_ici}


def calculer(ref, deps: set[str] | None, types, service, sortie, deps_maternite: set[str] | None = None,
             niveaux=("dep", "epci")) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Temps par type, résumé aussitôt par commune et par territoire (les carreaux d'un type ne restent pas en mémoire
    au type suivant, 2,3 millions pour la France). deps None, toute la France. Deux échelles : le chiffre principal à
    l'échelle de l'INSEE (colonnes sans suffixe, isochrones de SEUILS_ICI), et le moteur prudent tel quel (colonnes
    « _prudent », isochrones de SEUILS). Écrit communes_<type>.csv au fil du calcul, puis communes.csv et
    territoires.csv dans sortie. Un calcul interrompu reprend grâce au cache des isochrones."""
    tout = structures(tuple(dict.fromkeys(list(types) + [d for t in types for d in DESTINATIONS.get(t, ())])))
    dep_reg = ref.deps.set_index("code")["reg"]
    coms, terrs, versions = [], [], {}
    for tid in types:
        fait = sortie / f"communes_{tid}.csv"
        zdeps = (deps | (deps_maternite or set())) if deps and tid == "lieu_maternite" else deps
        pts = points_habitants(ref, zdeps)
        t0 = time.time()
        zone = pts if deps else None
        principal = echelle_insee(isochrones_destinations(tout, tid, service, SEUILS_ICI, zone))
        prudent = isochrones_destinations(tout, tid, service, SEUILS, zone)
        pts = pts.assign(type=tid, minutes=tranches(pts["lon"], pts["lat"], principal),
                         minutes_prudent=tranches(pts["lon"], pts["lat"], prudent), reg=pts["dep"].map(dep_reg), FR="FR")

        def deux(cles):
            a = resumer(pts, cles)
            b = resumer(pts.assign(minutes=pts["minutes_prudent"]), cles)
            mesures = [c for c in b.columns if c not in cles + ["type", "habitants"]]
            return a.merge(b[cles + ["type"] + mesures].rename(columns={c: c + "_prudent" for c in mesures}),
                           on=cles + ["type"], how="left")
        c = deux(["code"])
        t = pd.concat([deux([n]).rename(columns={n: "code"}).assign(niveau=n) for n in niveaux])
        c.to_csv(fait, sep=";", decimal=",", index=False, encoding="utf-8-sig")
        coms.append(c)
        terrs.append(t)
        versions[tid] = sorted({v for dt in DESTINATIONS.get(tid, (tid,)) for v in versions_reseau(dt)})
        log.info("trajets, %s : %s points, %.0f s", tid, len(pts), time.time() - t0)
        del pts, principal, prudent
    com, terr = pd.concat(coms, ignore_index=True), pd.concat(terrs, ignore_index=True)
    com.to_csv(sortie / "communes.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")
    terr.to_csv(sortie / "territoires.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")
    return com, terr, versions


def tranches_centres(ref, types, service=None) -> dict:
    """Pour la page « Autour d'un lieu » (Z.trajets de pipeline/zone.py) : tranche de temps, à l'échelle de l'INSEE,
    depuis le centre de la population de chaque commune vers la structure la plus proche de chaque type, {« seuils »:
    SEUILS_INSEE, « types »: [...], « communes »: {code: [indice du seuil, None au-delà du dernier]}}. Cache seul par
    défaut."""
    from .sources import insee_carreaux as ic
    cen = pd.read_parquet(ic.CACHE)[["code", "lon", "lat"]]
    tout = structures(tuple(dict.fromkeys(list(types) + [d for t in types for d in DESTINATIONS.get(t, ())])))
    rang = {s: k for k, s in enumerate(SEUILS_INSEE)}
    par_type = []
    for tid in types:
        t = tranches(cen["lon"], cen["lat"], echelle_insee(isochrones_destinations(tout, tid, service, SEUILS_ICI)))
        par_type.append([None if np.isinf(v) else rang[int(v)] for v in t])
    communes = {c: [par_type[k][i] for k in range(len(types))] for i, c in enumerate(cen["code"])}
    return {"seuils": list(SEUILS_INSEE), "types": list(types), "rapport_moteur": RAPPORT_MOTEUR, "communes": communes}


def national(appeler=True) -> dict:
    """Calcul pour toute la France, tous les types de TYPES_NATIONAL, dans donnees/intermediaire/trajets/national/.
    Les isochrones déjà en cache ne sont pas redemandées. Validation, plausibilité de chaque type face aux distances
    et urgences face à l'INSEE sur toute la France. Rien n'est publié."""
    from .sources import acces_route, referentiel
    ref = referentiel.charger(hors_ligne=True)
    service = Service() if appeler else None
    SANS_ISOCHRONE.clear()
    sortie = DOSSIER / "national"
    sortie.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    com, terr, versions = calculer(ref, None, TYPES_NATIONAL, service, sortie, niveaux=("FR", "reg", "dep", "epci"))
    val = {"versions_reseau": versions, "appels": service.appels if service else 0,
           "refus_429": service.refus if service else 0, "erreurs": service.erreurs if service else 0,
           "structures_sans_isochrone": len({k for k in SANS_ISOCHRONE}),
           "isochrones_en_cache": sum(len(lire_cles(t)) for t in {d for tid in TYPES_NATIONAL
                                                                   for d in DESTINATIONS.get(tid, (tid,))}),
           "duree_min": round((time.time() - t0) / 60)}
    JOURNAL.controle("Temps de route, appels au service d'isochrone de la Géoplateforme",
                     controle_appels(val))
    dossiers = sorted(d for d in config.RESULTATS.glob("20*") if (d / "distances_lieux_communes.csv").exists())
    if dossiers:
        dist = pd.read_csv(dossiers[-1] / "distances_lieux_communes.csv", sep=";", decimal=",",
                           dtype={"code": str, "dep": str}).set_index("code")
        val["plausibilite"] = {tid: plausibilite(com[com["type"] == tid].set_index("code")["temps_median_min"],
                                                 dist.get("dist_" + tid, pd.Series(dtype=float)))
                               for tid in TYPES_NATIONAL if "dist_" + tid in dist}
    ar = acces_route.charger(ref, hors_ligne=True)
    if ar:
        # le chiffre principal est à l'échelle de l'INSEE, l'écart doit être faible ; le moteur prudent est gardé
        val["urgences_insee"] = comparer_insee(com[com["type"] == "lieu_urgences"], ar)
        prud = com[com["type"] == "lieu_urgences"].copy()
        prud["temps_median_min"], prud["part_plus_30_min"] = prud["temps_median_min_prudent"], prud["part_plus_30_min_prudent"]
        val["urgences_insee_moteur_prudent"] = comparer_insee(prud, ar)
    (sortie / "validation.json").write_text(json.dumps(val, ensure_ascii=False, indent=1, default=float),
                                            encoding="utf-8")
    # tranches depuis le centre de chaque commune, pour la page « Autour d'un lieu »
    (sortie / "centres.json").write_text(json.dumps(tranches_centres(ref, TYPES_NATIONAL), separators=(",", ":")),
                                         encoding="utf-8")
    return val


# ---------------------------------------------------------------- publication
FICHIERS_PUBLIES = {"communes.csv": "temps_route_communes.csv", "territoires.csv": "temps_route_territoires.csv",
                    "centres.json": "temps_route_centres.json"}


def publier(out) -> list[str]:
    """Recopie dans la version (out) les résultats du calcul national, s'ils sont à l'échelle de l'INSEE (colonnes du
    moteur prudent présentes) : temps_route_communes.csv, temps_route_territoires.csv et temps_route_centres.json
    (page « Autour d'un lieu »). Le calcul lui-même ne tourne pas pendant l'exécution, il se fait à part (python -m
    pipeline.trajets national) et se reprend du cache. Renvoie les fichiers écrits."""
    import shutil
    from pathlib import Path
    nat = DOSSIER / "national"
    f = nat / "communes.csv"
    if not f.exists() or "temps_median_min_prudent" not in f.open(encoding="utf-8-sig").readline():
        JOURNAL.note("Géoplateforme de l'IGN, temps de route vers les structures", "ignoré",
                     "calcul national à l'échelle de l'INSEE absent (python -m pipeline.trajets national)")
        return []
    ecrits = []
    # noms de colonnes propres aux temps de route vers nos structures, distincts de ceux de l'INSEE (temps_acces.csv)
    noms = lambda c: (c.replace("temps_median_min", "temps_route_median_min")  # noqa: E731
                      .replace("part_plus_", "part_route_plus_"))
    for src, dst in FICHIERS_PUBLIES.items():
        if not (nat / src).exists():
            continue
        if src.endswith(".csv"):
            t = pd.read_csv(nat / src, sep=";", decimal=",", dtype={"code": str})
            t.rename(columns=noms).to_csv(Path(out) / dst, sep=";", decimal=",", index=False, encoding="utf-8-sig")
        else:
            shutil.copy2(nat / src, Path(out) / dst)
        ecrits.append(dst)
    val = json.loads((nat / "validation.json").read_text(encoding="utf-8")) if (nat / "validation.json").exists() else {}
    versions = sorted({v for vs in (val.get("versions_reseau") or {}).values() for v in vs})
    JOURNAL.note("Géoplateforme de l'IGN, temps de route vers les structures", "ok",
                 f"isochrones du service {RESSOURCE}, réseau du " + ", ".join(versions), url=URL)
    if "appels" in val:
        JOURNAL.controle("Temps de route, appels au service d'isochrone de la Géoplateforme", controle_appels(val))
    u = val.get("urgences_insee") or {}
    if u:
        JOURNAL.controle("Temps de route, urgences à l'échelle de l'INSEE face à l'INSEE, part des habitants à plus de "
                         "30 minutes (attendu, proches)",
                         (f"{u.get('part_30_nous', float('nan')) * 100:.1f} % ici, "
                          f"{u.get('part_30_insee', float('nan')) * 100:.1f} % pour l'INSEE, corrélation de rang "
                          f"{u.get('rho_temps', float('nan')):.2f}").replace(".", ","))
    return ecrits


# ---------------------------------------------------------------- pilote
def pilote(deps: set[str], types=TYPES_PILOTE, appeler=True, deps_maternite: set[str] | None = None) -> dict:
    """Calcul sur une zone (départements deps), puis validation. Écrit donnees/intermediaire/trajets/pilote_<deps>/
    (communes.csv, territoires.csv, validation.json). Rien n'est publié."""
    from .sources import referentiel
    ref = referentiel.charger(hors_ligne=True)
    service = Service() if appeler else None
    zone = "-".join(sorted(deps))
    sortie = DOSSIER / f"pilote_{zone}"
    sortie.mkdir(parents=True, exist_ok=True)
    com, terr, versions = calculer(ref, deps, types, service, sortie, deps_maternite)
    val = {"zone": sorted(deps), "versions_reseau": versions,
           "appels": service.appels if service else 0, "refus_429": service.refus if service else 0}
    # plausibilité face aux distances à vol d'oiseau de la même version
    dossiers = sorted(d for d in config.RESULTATS.glob("20*") if (d / "distances_lieux_communes.csv").exists())
    if dossiers:
        dist = pd.read_csv(dossiers[-1] / "distances_lieux_communes.csv", sep=";", decimal=",",
                           dtype={"code": str, "dep": str}).set_index("code")
        val["plausibilite"] = {tid: plausibilite(com[com["type"] == tid].set_index("code")["temps_median_min"],
                                                 dist.get("dist_" + tid, pd.Series(dtype=float)))
                               for tid in types if "dist_" + tid in dist}
    # urgences face à l'INSEE
    from .sources import acces_route
    ar = acces_route.charger(ref, hors_ligne=True)
    if ar and "lieu_urgences" in types:
        val["urgences_insee"] = comparer_insee(com[(com["type"] == "lieu_urgences")
                                                   & com["code"].map(ref.communes.set_index("code")["dep"]).isin(deps)],
                                               ar)
    # maternités face au repère de la DREES, départements qu'elle cite
    m = terr[(terr.get("type") == "lieu_maternite") & (terr["niveau"] == "dep")].set_index("code")
    val["maternites_drees"] = {"repere": REPERE_DREES["source"], "url": REPERE_DREES["url"],
                               "departements": {d: {"drees_2017_femmes_15_44": v,
                                                    "ici_tous_habitants": float(m.at[d, "part_plus_45_min"])}
                                                for d, v in REPERE_DREES["par_departement_plus_45"].items()
                                                if d in m.index}}
    (sortie / "validation.json").write_text(json.dumps(val, ensure_ascii=False, indent=1, default=float),
                                            encoding="utf-8")
    JOURNAL.controle(f"Temps de route vers nos structures, pilote {zone}", json.dumps(val, ensure_ascii=False,
                                                                                      default=float)[:400])
    return val


def main(argv=None):
    a = argparse.ArgumentParser(description="Temps de route vers nos structures (isochrones de la Géoplateforme)")
    a.add_argument("action", choices=["pilote", "national"])
    a.add_argument("--dep", nargs="+", default=[])
    a.add_argument("--maternite-dep", nargs="*", default=[], help="départements ajoutés pour les seules maternités")
    a.add_argument("--cache", action="store_true", help="sans appel au service, sur le seul cache")
    a.add_argument("--types", nargs="*", default=list(TYPES_PILOTE), help="types de structures (lieu_...)")
    x = a.parse_args(argv)
    if x.action == "national":
        try:
            r = national(appeler=not x.cache)
        except TropDErreurs as e:
            print(f"Calcul arrêté, trop d'erreurs du service : {e}. Il reprendra du cache.")
            raise SystemExit(2)
    else:
        if not x.dep:
            a.error("--dep est demandé pour le pilote")
        r = pilote(set(x.dep), types=tuple(x.types), appeler=not x.cache, deps_maternite=set(x.maternite_dep))
    print(json.dumps(r, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
