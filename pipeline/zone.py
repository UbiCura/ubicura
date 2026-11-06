"""Données de la page « Autour d'un lieu, ou sur un périmètre » (présentation du 30 octobre 2026, maquette d-zone).

Une zone se trace autour d'une commune, dans un rayon à vol d'oiseau, ou se compose commune par commune (périmètre
d'une CPTS, d'un contrat local de santé). La page compte les habitants et les structures de soins de la zone, et
mesure la plus proche de chaque type. Lecture seule des fichiers publiés de la version (lieux_soins.csv,
distances_lieux_dep.csv, accessibilite_communes.csv) et du référentiel des communes, aucun calcul statistique ici.

Centre de chaque commune, celui de sa population d'après les carreaux de 200 m de l'INSEE
(donnees/intermediaire/centres_population_communes.parquet), le milieu de l'emprise de son plus grand polygone sinon.
Les temps de route vers ces structures (pipeline/trajets.py) viennent de temps_route_centres.json : tranche de temps,
à l'échelle du distancier de l'INSEE, depuis le centre de la population de chaque commune (clé « trajets », décision
de Lucas du 31 octobre 2026).
"""
import csv
import json
from pathlib import Path

from . import config

# Types montrés, santé mentale d'abord (tous les types de la famille), puis la santé de proximité et les urgences.
TYPES_SM = ["lieu_cmp_adultes", "lieu_cmp_enfants", "lieu_cmp", "lieu_cattp", "lieu_hdj_psy_adultes",
            "lieu_hdj_psy_enfants", "lieu_hc_psy_adultes", "lieu_hc_psy_enfants", "lieu_crise_psy", "lieu_mobile_psy",
            "lieu_consult_psy", "lieu_rehab_psy", "lieu_psychotrauma", "lieu_cmpp", "lieu_camsp", "lieu_tnd", "lieu_mda",
            "lieu_bapu", "lieu_csapa", "lieu_caarud", "lieu_addicto_hosp"]
TYPES_SANTE = ["lieu_urgences", "lieu_smur", "lieu_soins_non_programmes", "lieu_maternite", "lieu_perinatal_proximite",
               "lieu_pmi", "lieu_msp", "lieu_centre_sante", "lieu_cpts", "lieu_sante_sexuelle", "lieu_precarite",
               "lieu_dialyse", "lieu_ehpad"]
CLASSES = {"confirmée": "c", "à vérifier": "v", "recoupée par la statistique des hôpitaux": "r"}


def _lire(f: Path) -> list[dict]:
    with open(f, encoding="utf-8-sig") as h:
        return list(csv.DictReader(h, delimiter=";"))


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def centres(brut: Path, inter: Path) -> dict[str, tuple]:
    """Centre de la population de chaque commune, milieu de l'emprise de son plus grand polygone à défaut."""
    sortie = {}
    contours = brut / "contours_communes_ign.geojson"
    if contours.exists():
        for f in json.loads(contours.read_text(encoding="utf-8"))["features"]:
            g = f["geometry"]
            if not g:
                continue
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            anneau = max((p[0] for p in polys), key=len)
            xs, ys = [p[0] for p in anneau], [p[1] for p in anneau]
            sortie[f["properties"]["code"]] = (round((min(xs) + max(xs)) / 2, 4), round((min(ys) + max(ys)) / 2, 4), 0)
    f = inter / "centres_population_communes.parquet"
    if f.exists():
        import pandas as pd
        for r in pd.read_parquet(f, columns=["code", "lon", "lat"]).itertuples():
            if r.lon == r.lon and r.lat == r.lat:
                sortie[str(r.code)] = (round(float(r.lon), 4), round(float(r.lat), 4), 1)
    return sortie


def trajets_zone(t: dict, rang: dict) -> dict:
    """Tranches de temps de temps_route_centres.json (pipeline/trajets.py) pour la page : seulement les types montrés,
    « calcules » donne leur rang dans les types de la page, une valeur par type calculé pour chaque commune."""
    garde = [k for k, x in enumerate(t["types"]) if x in rang]
    return {"seuils": t["seuils"], "rapport": t.get("rapport_moteur"), "calcules": [rang[t["types"][k]] for k in garde],
            "communes": {c: [v[k] for k in garde] for c, v in t["communes"].items()}}


def donnees(dernier: Path, brut: Path, inter: Path, version: str, doi: str | None = None, sd: dict | None = None) -> dict:
    lieux = _lire(dernier / "lieux_soins.csv")
    types = TYPES_SM + TYPES_SANTE
    libelles = {}
    for l in lieux:
        libelles.setdefault(l["type"], l["libelle_type"])
    types = [t for t in types if t in libelles]
    rang = {t: k for k, t in enumerate(types)}
    epci = {}
    for l in _lire(dernier / "accessibilite_communes.csv"):
        epci.setdefault(l["code"], l["epci"])
    cen = centres(brut, inter)
    communes, n_pop = [], 0
    for c in json.loads((brut / "ref_communes.json").read_text(encoding="utf-8")):
        if c.get("type") != "commune-actuelle":
            continue
        x, y, p = cen.get(c["code"], (None, None, 0))
        n_pop += p
        communes.append([c["code"], c["nom"], " ".join(c.get("codesPostaux", [])[:3]), c.get("population") or 0,
                         epci.get(c["code"], ""), c["departement"], x, y])
    structures = []
    for l in lieux:
        if l["type"] in rang and l["latitude"] and l["longitude"]:
            # [type, nom, lon, lat, confirmation (c, v, r ou vide, sans objet), commune où les patients sont reçus,
            #  1 si la structure est placée au centre de sa commune faute d'adresse]
            structures.append([rang[l["type"]], l["nom"][:70], round(_num(l["longitude"]), 4),
                               round(_num(l["latitude"]), 4), CLASSES.get(l["classe_confirmation"], ""), l["commune"],
                               1 if l["emplacement"].startswith("centre de la commune") else 0])
    # départements où la limite des manques de la SAE retire distance et taux d'un type (distance vide)
    # types recensés dans moins de 90 % des départements (recensement_complet faux) : la structure existe souvent sans
    # être inscrite sous ce type, la plus proche n'est pas donnée et le nombre de la zone est un minimum
    masques, incomplets = {}, set()
    for l in _lire(dernier / "distances_lieux_dep.csv"):
        if l["type"] in rang and not l["distance_mediane_km"]:
            masques.setdefault(l["code"], []).append(rang[l["type"]])
        if l["type"] in rang and l.get("recensement_complet") == "False":
            incomplets.add(rang[l["type"]])
    # types non recensés et mots des statuts lus dans la règle d'affichage (pipeline/affichage.py), les mêmes que sur la
    # fiche d'un territoire, le comparateur et Croiser ; le fichier des distances doit dire la même chose
    from . import affichage as AF
    sd = sd if sd is not None else json.loads((dernier / "site_data.json").read_text(encoding="utf-8"))
    T = AF.Affichage(sd, dernier)
    non_recenses = {rang[t] for t in types if T.complet.get(t) is False}
    if non_recenses != incomplets:
        from .util import JOURNAL
        JOURNAL.controle("Zone, types non recensés, fichier des distances face à la règle d'affichage (attendu, égaux)",
                         f"{len(incomplets ^ non_recenses)} types différents")
    incomplets = non_recenses
    deps = {d["code"]: d["nom"] for d in json.loads((brut / "ref_departements.json").read_text(encoding="utf-8"))}
    # temps de route depuis le centre de chaque commune, types calculés seulement (rang dans types), une valeur par type
    # calculé : indice du seuil de l'INSEE sous lequel est la structure la plus proche, None au-delà du dernier
    f = dernier / "temps_route_centres.json"
    trajets = trajets_zone(json.loads(f.read_text(encoding="utf-8")), rang) if f.exists() else None
    return {"version": version, "doi": doi, "citation": config.CITATION_AUTEUR, "types": [libelles[t] for t in types], "codes": types, "sm": sum(1 for t in types if t in TYPES_SM),
            "communes": communes, "structures": structures, "masques": masques, "incomplets": sorted(incomplets), "departements": {k: deps[k] for k in masques if k in deps},
            "centres_population": n_pop, "trajets": trajets,
            "statuts": AF.pour_js()["statuts"]}


def fonds(brut: Path, site: Path, ref_dep: dict[str, str], tolerance: float = 0.0015) -> int:
    """Contours des communes simplifiés (environ 150 m, ADMIN EXPRESS de l'IGN, contours_communes_ign.geojson), un
    fichier par département dans presentation/zone_fond/, chargé à la demande par la page (audit de contrôle du
    30 octobre 2026, point I2). Coordonnées entières au dix-millième de degré, écrites en écarts successifs depuis
    l'origine du département : {"o": [lon, lat], "c": {code: [[x0, y0, dx, dy, ...], ...]}}."""
    from shapely.geometry import shape
    f = brut / "contours_communes_ign.geojson"
    if not f.exists():
        return 0
    par_dep: dict[str, dict] = {}
    for feat in json.loads(f.read_text(encoding="utf-8"))["features"]:
        code = feat["properties"]["code"]
        dep = ref_dep.get(code)
        if not dep or not feat["geometry"]:
            continue
        g = shape(feat["geometry"]).simplify(tolerance, preserve_topology=True)
        polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
        par_dep.setdefault(dep, {})[code] = [list(p.exterior.coords) for p in polys if not p.is_empty]
    dossier = site / "presentation" / "zone_fond"
    dossier.mkdir(parents=True, exist_ok=True)
    for dep, coms in par_dep.items():
        xs = [x for anneaux in coms.values() for a in anneaux for x, _ in a]
        ys = [y for anneaux in coms.values() for a in anneaux for _, y in a]
        ox, oy = round(min(xs), 4), round(min(ys), 4)
        sortie = {}
        for code, anneaux in coms.items():
            enc = []
            for a in anneaux:
                px = py = None
                r = []
                for x, y in a:
                    ix, iy = round((x - ox) * 1e4), round((y - oy) * 1e4)
                    if px is None:
                        r += [ix, iy]
                    elif (ix, iy) != (px, py):
                        r += [ix - px, iy - py]
                    px, py = ix, iy
                if len(r) >= 6:
                    enc.append(r)
            sortie[code] = enc
        (dossier / f"{dep}.json").write_text(json.dumps({"o": [ox, oy], "c": sortie}, separators=(",", ":")), encoding="utf-8")
    return len(par_dep)


def construire(dernier: Path, site: Path, version: str, doi: str | None = None, sd: dict | None = None) -> Path:
    Z = donnees(dernier, config.BRUT, config.INTER, version, doi, sd)
    fonds(config.BRUT, site, {c[0]: c[5] for c in Z["communes"]})
    sortie = site / "presentation" / "zone_donnees.js"
    sortie.write_text("var Z=" + json.dumps(Z, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    return sortie
