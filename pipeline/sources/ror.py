"""Répertoire opérationnel des ressources (ROR), extraction « Offres de santé » de l'Agence du numérique en santé.

Jeu data.gouv config.ROR_JEU (Licence Ouverte), un zip par région, mis à jour chaque semaine. Chaque zip contient un
fichier XML au format IHE CSD. On en tire les unités élémentaires (facilityDirectory), c'est-à-dire les lieux de prise
en charge décrits par les établissements eux-mêmes (CMP, hôpitaux de jour, unités d'hospitalisation, CMPP, CAMSP...),
avec leur catégorie, leur champ d'activité, leur mode de prise en charge, l'âge des patients, la commune, l'adresse et,
en Corse et en PACA seulement, les coordonnées, et les structures (organizationDirectory) auxquelles elles sont
rattachées, avec leur numéro FINESS.

Les codes renvoient aux nomenclatures de l'ANS (config.ROR_NOMENCLATURE). Les contacts (téléphones, courriels) ne sont
jamais lus. L'extraction publique ne contient pas les professionnels. La lecture d'une région est gardée en cache
(parquet à côté du zip) tant que le zip ne change pas.
"""
from __future__ import annotations

import io
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from .. import config
from ..util import JOURNAL, date_version, lire_meta, log, ressources_datagouv, telecharger

SOURCE = "ANS, offres de santé (ROR)"
DOSSIER = config.BRUT / "ror"
VERSION_LECTURE = 4   # à augmenter quand la lecture change, pour relire les zips déjà téléchargés

_NS = re.compile(r"^\{[^}]*\}")


def _tag(e) -> str:
    return _NS.sub("", e.tag)


def _enfant(e, nom):
    if e is None:
        return None
    for c in e:
        if _tag(c) == nom:
            return c
    return None


def _enfants(e, nom):
    return [] if e is None else [c for c in e if _tag(c) == nom]


def _code(e, nom):
    c = _enfant(e, nom)
    return c.get("code") if c is not None else None


def _texte(e, nom):
    c = _enfant(e, nom)
    return (c.text or "").strip() or None if c is not None and c.text else None


def _age(pt, nom):
    a = _enfant(pt, nom)
    if a is None:
        return None
    v, u = _texte(a, "value"), _code(a, "unit")
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    # unités UCUM, années (a), mois (mo), semaines (wk), jours (d)
    return {"a": v, "mo": v / 12, "wk": v / 52, "d": v / 365}.get(u, v)


def _maj(e):
    """Date de dernière mise à jour déclarée de l'élément (record updated)."""
    r = _enfant(e, "record")
    return (r.get("updated") or "")[:10] if r is not None else None


def _adresse(loc):
    """Adresse postale (numéro, type et nom de voie, code postal, commune), sans boîte postale."""
    a = _enfant(_enfant(loc, "address"), "addressLine")
    if a is None:
        return None, None
    voie = " ".join(x for x in (a.get("houseNumber") or a.get("streetNumber"), a.get("streetNumberRepetitionIndex"),
                                a.get("streetType"), a.get("streetName")) if x)
    return (re.sub(r"\s+", " ", voie).strip() or None), a.get("postCode")


def _geo(loc):
    geo = _enfant(loc, "geoCoordinates")
    if geo is None:
        return None, None
    try:
        return float(_texte(geo, "latitude")), float(_texte(geo, "longitude"))
    except (TypeError, ValueError):
        return None, None


def _finess_ins(v):
    return v[1:] if v and len(v) == 10 and v[0] == "1" else None


def lire_xml(flux) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Unités élémentaires et structures d'un fichier de l'extraction, lus au fil de l'eau."""
    unites, structures, services = [], [], {}
    for _ev, e in ET.iterparse(flux, events=("end",)):
        t = _tag(e)
        if t == "service":
            ct = _enfant(e, "codedType")
            if ct is not None and e.get("entityID"):
                services[e.get("entityID")] = ct.get("code")
            e.clear()
        elif t == "facility" and _enfant(e, "primaryName") is not None:
            ext = _enfant(e, "extension")
            loc = _enfant(ext, "location")
            pt = _enfant(ext, "patientsType")
            beds = _enfant(_enfant(ext, "accommodationCapacity"), "beds")
            liens = [(o.get("entityID"), [s.get("entityID") for s in _enfants(o, "service")])
                     for o in _enfants(_enfant(e, "organizations"), "organization")]
            voie, cp = _adresse(loc)
            lat, lon = _geo(loc)
            unites.append({
                "id": e.get("entityID"),
                "nom": _texte(e, "primaryName"),
                # niveau d'organisation (TRE_R207), 4 pour une unité élémentaire, les pôles et services la regroupent
                "niveau_organisation": _code(e, "codedType"),
                "categorie": _code(ext, "facilityType"),
                "champ": _code(ext, "typeActivity"),
                "mode": _code(ext, "careMode"),
                "type_maternite": _code(ext, "maternityHospitalType"),
                "age_min": _age(pt, "patientTypeAgeMin"),
                "age_max": _age(pt, "patientTypeAgeMax"),
                "public": ",".join(c.get("code") for c in _enfants(pt, "supportedPatient")),
                "lits": pd.to_numeric(beds.get("total"), errors="coerce") if beds is not None else None,
                "commune": _code(loc, "cityNumber"),
                "voie": voie, "code_postal": cp, "lat": lat, "lon": lon,
                "sensible": _texte(ext, "sensitiveUnit"),
                "maj": _maj(e),
                "structures": "|".join(o for o, _s in liens if o),
                "services_ids": "|".join(s for _o, ss in liens for s in ss if s),
            })
            e.clear()
        elif t == "organization" and e.get("entityID") and _enfant(e, "primaryName") is not None:
            ids = {o.get("assigningAuthorityName"): o.get("code") for o in _enfants(e, "otherID")}
            loc = _enfant(_enfant(e, "extension"), "location")
            cts = {c.get("codingScheme"): c.get("code") for c in _enfants(e, "codedType")}
            parent = _enfant(e, "parent")
            voie, cp = _adresse(loc)
            lat, lon = _geo(loc)
            structures.append({
                "id": e.get("entityID"),
                "nom": _texte(e, "primaryName"),
                # numéro FINESS, ou à défaut l'identifiant national de structure (1 suivi du numéro FINESS)
                "finess": ids.get(config.ROR_OID_FINESS) or _finess_ins(ids.get(config.ROR_OID_IDNST)),
                "categorie_finess": cts.get(config.ROR_OID_CATEGORIE_FINESS),
                "parent": parent.get("entityID") if parent is not None else None,
                "commune": _code(loc, "cityNumber"),
                "voie": voie, "code_postal": cp, "lat": lat, "lon": lon,
                "maj": _maj(e),
            })
            e.clear()
    u = pd.DataFrame(unites)
    if len(u):
        u["activites"] = [",".join(sorted({services.get(s, "") for s in x.split("|") if services.get(s)}))
                          for x in u.pop("services_ids")]
    return u, pd.DataFrame(structures)


def lire_zip(chemin: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    with zipfile.ZipFile(chemin) as z:
        noms = [n for n in z.namelist() if n.lower().endswith(".xml")]
        if not noms:
            raise IOError(f"aucun fichier XML dans {chemin.name}")
        us, ss = [], []
        for n in noms:
            with z.open(n) as f:
                u, s = lire_xml(io.BufferedReader(f))
                us.append(u)
                ss.append(s)
    return pd.concat(us, ignore_index=True), pd.concat(ss, ignore_index=True)


def _region(chemin: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lecture d'un zip régional, gardée en cache tant que le zip et la lecture ne changent pas."""
    cu, cs = chemin.with_suffix(f".unites.v{VERSION_LECTURE}.parquet"), chemin.with_suffix(f".structures.v{VERSION_LECTURE}.parquet")
    if cu.exists() and cs.exists() and cu.stat().st_mtime >= chemin.stat().st_mtime:
        return pd.read_parquet(cu), pd.read_parquet(cs)
    u, s = lire_zip(chemin)
    region = chemin.stem
    u, s = u.assign(region=region), s.assign(region=region)
    # une même unité peut figurer deux fois dans le fichier, la première description complète est gardée
    u = u.drop_duplicates("id")
    s = s.drop_duplicates("id")
    u.to_parquet(cu, index=False)
    s.to_parquet(cs, index=False)
    return u, s


def charger(hors_ligne=False, rafraichir=False):
    """Renvoie {"unites": DataFrame, "structures": DataFrame} pour toute la France, ou None si le jeu est indisponible.
    Les identifiants des unités et des structures sont préfixés par la région, ils ne sont uniques que dans une région."""
    try:
        DOSSIER.mkdir(parents=True, exist_ok=True)
        if hors_ligne:
            zips = sorted(DOSSIER.glob("*.zip"))
            if not zips:
                raise FileNotFoundError(DOSSIER / "*.zip")
        else:
            res = [r for r in ressources_datagouv(config.ROR_JEU) if r["url_directe"].lower().endswith(".zip")]
            if not res:
                raise RuntimeError("aucune ressource zip dans le jeu des offres de santé")
            zips = []
            for r in res:
                dest = DOSSIER / r["url_directe"].rsplit("/", 1)[-1]
                telecharger(r["url"], dest, "ror", rafraichir, taille_min=10_000,
                            extra_meta={"titre": r["titre"], "maj_source": r["maj"]})
                zips.append(dest)
        us, ss = [], []
        for z in zips:
            u, s = _region(z)
            us.append(u)
            ss.append(s)
        u, s = pd.concat(us, ignore_index=True), pd.concat(ss, ignore_index=True)
        for d in (u, s):
            d["cle"] = d["region"] + "#" + d["id"].astype(str)
        u["structures"] = [("|".join(f"{r}#{x}" for x in v.split("|") if x)) for r, v in zip(u["region"], u["structures"])]
        s["parent"] = [f"{r}#{p}" if p else None for r, p in zip(s["region"], s["parent"])]
        metas = [lire_meta(z) for z in zips]
        dates = sorted(date_version(m) for m in metas if date_version(m))
        JOURNAL.note(SOURCE, "ok", f"{len(zips)} régions, {len(u)} unités, {len(s)} structures",
                     url=config.ROR_PAGE, page=config.ROR_PAGE, date_donnees=dates[-1] if dates else "",
                     lignes=len(u))
        JOURNAL.controle("ROR, régions lues et plus ancienne version régionale",
                         f"{len(zips)} régions, version la plus ancienne {dates[0] if dates else 'inconnue'}")
        return {"unites": u, "structures": s}
    except Exception as e:  # noqa: BLE001
        log.warning("ROR indisponible : %s", e)
        JOURNAL.note(SOURCE, "erreur", str(e)[:300], page=config.ROR_PAGE)
        return None
