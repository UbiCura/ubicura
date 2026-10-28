"""Vérification des sources sans téléchargement (python run.py --verifier).

Pour chaque fichier brut, la version annoncée par le producteur (date de mise à jour, millésime) est demandée par les
mêmes appels que ceux des modules de sources, puis comparée à celle consignée dans le .meta.json du fichier en cache.
Le résultat dit, jeu par jeu, s'il est à jour, si une nouvelle version existe, ou s'il n'a pas pu être vérifié. Il est
écrit dans donnees/verification.json et repris par le script de mise à jour (outils/mise_a_jour.ps1).

Codes de sortie, 0 tout est à jour, 10 au moins un jeu a une nouvelle version, 20 la vérification est incomplète
(producteur injoignable) sans nouvelle version repérée."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from . import config
from .mises_a_jour import _groupe, date_iso
from .util import _session, choisir_ressource, get_json, get_texte, lire_meta, log, norm, ressources_datagouv, slug

FICHIER = config.DONNEES / "verification.json"
A_JOUR, NOUVELLE, ABSENT, INCONNU = "à jour", "nouvelle version", "absent en local", "non vérifiable"


def _modifie(api: str) -> str:
    """Date de modification d'un jeu Opendatasoft (Assurance Maladie, Santé publique France, DREES, CAF)."""
    return (get_json(api).get("metas", {}).get("default", {}) or {}).get("modified", "")


def _rpps():
    from .sources import rpps
    res = ressources_datagouv(config.RPPS_DATASET)
    for k, motif in config.RPPS_RESSOURCES.items():
        r = choisir_ressource(res, motif)
        yield rpps.FICHIERS[k], (r or {}).get("maj", ""), {}


def _finess():
    res = ressources_datagouv(config.FINESS_HISTORIQUE)
    r = choisir_ressource(res, r"cs1100507", formats={"csv"}) or \
        max([r for r in res if r["format"] == "csv"], key=lambda r: r["taille"] or 0)
    yield config.BRUT / "finess_historique.csv", r["maj"], {}
    res = ressources_datagouv(config.FINESS_NOUVEAU)
    cands = [r for r in res if "mensuel" in r["titre"].lower() and r["titre"].lower().endswith(".json.gz")] or \
            [r for r in res if r["titre"].lower().endswith(".json.gz")]
    yield config.BRUT / "finess_plus.json.gz", max(cands, key=lambda r: r["maj"])["maj"], {}


def _insee():
    page = get_texte(config.INSEE_PAGE_DOSSIER)
    m = re.search(r"Paru le.{0,400}?(\d{2})/(\d{2})/(\d{4})", page, re.S)
    yield config.BRUT / "insee_dossier_complet.parquet", f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else "", {}


def _insee_estimations():
    from .sources import insee_estimations
    yield insee_estimations.DEST, get_json(config.INSEE_ESTIMATIONS_API.replace("/data/", "/catalog/")).get("modified", ""), {}


def _acces_route():
    from .sources import acces_route
    annee, fichiers = acces_route._fichiers()
    for reg, res in sorted(fichiers.items()):
        yield acces_route.DOSSIER / f"acces_{annee}_reg{reg}", res["maj"], {"annee": annee}


def _referentiel():
    from .sources import referentiel
    version, publie = referentiel._version()
    if not version:
        raise IOError("registre npm injoignable")
    for nom in config.REF_FICHIERS:
        yield config.BRUT / f"ref_{nom}.json", publie, {"version": version}


def _contours():
    from .sources import contours
    maj = contours._maj_source()
    if not maj:
        raise IOError("date du jeu ADMIN EXPRESS indisponible")
    yield contours.FICHIER, maj, {}


def _apl():
    from .sources import apl
    pj = apl._pieces_jointes()
    for _m, prof in config.APL_PROFESSIONS:
        if prof in pj:
            yield config.BRUT / f"apl_{prof}.xlsx", pj[prof][1], {}


def _drees_demographie():
    from .sources import drees_demographie
    for motif, (_url, maj, _t) in drees_demographie._pieces_jointes().items():
        yield drees_demographie._fichier(motif), maj, {}


def _drees_isd():
    for jeu in dict.fromkeys(x[0] for x in config.DREES_ISD):
        yield config.BRUT / f"drees_isd_{jeu.split('_')[0]}.csv", _modifie(config.DREES_API + jeu), {}


def _sae():
    from .sources import sae
    annee, url = sae._archive()
    maj = _session().head(url, timeout=60, allow_redirects=True).headers.get("Last-Modified", "")
    yield sae.DOSSIER / "psy.csv", maj, {"annee": annee}


def _ameli():
    yield config.BRUT / "ameli_pathologies_psy.csv", _modifie(config.AMELI_API), {}
    yield config.BRUT / "ameli_secteurs_conventionnels.csv", _modifie(config.AMELI_SECTEURS_API), {}
    yield config.BRUT / "ameli_ald_sans_medecin_traitant.csv", _modifie(config.AMELI_ALD_API), {}
    yield config.BRUT / "ameli_honoraires.csv", _modifie(config.AMELI_HONORAIRES_API), {}


def _ald():
    from .sources import ameli_ald
    res = [r for r in ressources_datagouv(config.ALD_DATAGOUV) if re.search(config.ALD_MOTIF, norm(r["titre"]))]
    r = max(res, key=lambda r: int(re.search(config.ALD_MOTIF, norm(r["titre"])).group(1)))
    yield ameli_ald.DEST, r["maj"], {"annee": re.search(config.ALD_MOTIF, norm(r["titre"])).group(1)}


def _odisse():
    for ind in config.ODISSE:
        yield config.BRUT / f"odisse_{slug(ind['id'])}.csv", _modifie(config.ODISSE_API + ind["dataset"]), {}


def _caf():
    from .sources import caf
    mois = caf._dernier_decembre()
    for jeu, _cle in config.CAF_JEUX.values():
        yield config.BRUT / f"caf_{jeu}.csv", _modifie(config.CAF_API + jeu), {"mois": mois}


def _ror():
    from .sources import ror
    for r in ressources_datagouv(config.ROR_JEU):
        if r["url_directe"].lower().endswith(".zip"):
            yield ror.DOSSIER / r["url_directe"].rsplit("/", 1)[-1], r["maj"], {}


def _has_certification():
    from .sources import has_certification as h
    for slug_, mg, md, cle in config.HAS_CERTIFICATION:
        res = ressources_datagouv(slug_)
        for motif, suffixe in ((mg, "sites"), (md, "demarches")):
            r = next((x for x in res if x["format"] == "csv" and re.match(motif, x["titre"].lower())), None)
            yield h.DOSSIER / f"{cle}_{suffixe}.csv", (r or {}).get("maj", ""), {}


def _has_essms():
    from .sources import has_essms as h
    r = h.ressource()
    yield h.DEST, (r or {}).get("maj", ""), {}


def _sirene():
    from .sources import sirene as s
    r = [x for x in ressources_datagouv(config.SIRENE_JEU)
         if x["titre"].startswith("Sirene : Fichier StockEtablissement -") and x["format"] == "parquet"]
    yield s.EXTRAIT, r[0]["maj"] if r else "", {}


VERIFICATIONS = [_rpps, _finess, _insee, _insee_estimations, _acces_route, _referentiel, _contours, _apl,
                 _drees_demographie, _drees_isd, _sae, _ameli, _ald, _odisse, _caf, _ror, _has_certification, _has_essms, _sirene]


def comparer(dest: Path, distante: str, attendu: dict) -> tuple[str, str]:
    """Statut d'un fichier et version locale, d'après son .meta.json."""
    meta = lire_meta(dest)
    if not meta:
        return ABSENT, ""
    locale = meta.get("maj_source") or ""
    if not distante:
        return INCONNU, locale
    if locale != distante or any(str(meta.get(k)) != str(v) for k, v in attendu.items()):
        return NOUVELLE, locale
    return A_JOUR, locale


def verifier() -> dict:
    """Interroge chaque producteur, compare avec le cache et écrit donnees/verification.json."""
    fichiers, erreurs = [], []
    for f in VERIFICATIONS:
        nom = f.__name__.strip("_")
        try:
            for dest, distante, attendu in f():
                statut, locale = comparer(Path(dest), distante, attendu)
                fichiers.append({"fichier": Path(dest).relative_to(config.BRUT).as_posix(), "statut": statut,
                                 "version_locale": locale, "version_producteur": distante, **attendu})
        except Exception as e:  # noqa: BLE001
            log.warning("vérification %s impossible : %s", nom, e)
            erreurs.append({"verification": nom, "erreur": str(e)[:300]})
    # regroupement par jeu de données, comme dans le journal des mises à jour
    jeux = {}
    for x in fichiers:
        jeu, producteur = _groupe(x["fichier"])
        j = jeux.setdefault(jeu or x["fichier"], {"jeu": jeu or x["fichier"], "producteur": producteur or "", "fichiers": []})
        j["fichiers"].append(x)
    for j in jeux.values():
        st = [x["statut"] for x in j["fichiers"]]
        j["statut"] = NOUVELLE if NOUVELLE in st or ABSENT in st else INCONNU if INCONNU in st else A_JOUR
        j["version_locale"] = max((date_iso(x["version_locale"]) for x in j["fichiers"]), default="")
        j["version_producteur"] = max((date_iso(x["version_producteur"]) for x in j["fichiers"]), default="")
    resultat = {"verifie_le": datetime.now().isoformat(timespec="seconds"), "jeux": sorted(jeux.values(), key=lambda j: j["jeu"]),
                "erreurs": erreurs}
    resultat["a_mettre_a_jour"] = any(j["statut"] == NOUVELLE for j in jeux.values())
    resultat["complete"] = not erreurs and all(j["statut"] != INCONNU for j in jeux.values())
    FICHIER.parent.mkdir(parents=True, exist_ok=True)
    FICHIER.write_text(json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8")
    return resultat


def afficher(r: dict) -> int:
    """Résumé lisible dans la console, renvoie le code de sortie."""
    print(f"\nVérification des sources du {r['verifie_le'][:10]} à {r['verifie_le'][11:16]}\n")
    for j in r["jeux"]:
        detail = ""
        if j["statut"] == NOUVELLE:
            n = sum(x["statut"] in (NOUVELLE, ABSENT) for x in j["fichiers"])
            detail = f", version du producteur {j['version_producteur'] or 'non datée'}, en cache {j['version_locale'] or 'aucune'}" + \
                     (f", {n} fichier{'s' if n > 1 else ''} sur {len(j['fichiers'])}" if len(j["fichiers"]) > 1 else "")
        elif j["statut"] == A_JOUR:
            detail = f", version du {j['version_producteur']}" if j["version_producteur"] else ""
        print(f"  {j['statut']:<17} {j['jeu']}{detail}")
    for e in r["erreurs"]:
        print(f"  {'non vérifiable':<17} {e['verification']}, {e['erreur'][:120]}")
    n = sum(j["statut"] == NOUVELLE for j in r["jeux"])
    print("\n" + (f"{n} jeu{'x' if n > 1 else ''} de données à mettre à jour." if n else "Aucune nouvelle version.")
          + ("" if r["complete"] else " La vérification est incomplète, certains producteurs n'ont pas répondu.")
          + f"\nDétail dans {FICHIER}\n")
    return 10 if r["a_mettre_a_jour"] else 0 if r["complete"] else 20
