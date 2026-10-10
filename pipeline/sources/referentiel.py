"""Référentiel géographique Etalab (découpage administratif en vigueur).
Fournit les tables de communes, EPCI, départements, régions et les correspondances
ancien code commune -> commune actuelle, code postal -> commune."""
from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd

from .. import config
from ..util import JOURNAL, get_json, lire_meta, log, telecharger


@dataclass
class Referentiel:
    communes: pd.DataFrame      # code, nom, pop, dep, reg, epci
    epci: pd.DataFrame          # code, nom, pop, dep (majoritaire)
    deps: pd.DataFrame          # code, nom, reg, pop
    regs: pd.DataFrame          # code, nom, pop
    anciens: dict               # ancien code -> code actuel
    codes_postaux: dict         # code postal -> code commune (la plus peuplée)

    def resoudre(self, code_commune: pd.Series, code_postal: pd.Series) -> pd.Series:
        """Code commune actuel à partir du code saisi au RPPS, avec repli sur le code postal."""
        actuels = set(self.communes["code"])
        c = code_commune.fillna("").str.strip().str.upper()
        c = c.where(c.isin(actuels), c.map(self.anciens))
        cp = code_postal.fillna("").str.strip().map(self.codes_postaux)
        return c.where(c.isin(actuels), cp)


def _version():
    """Dernière version publiée du paquet d'Etalab et sa date, ou (None, "") si le registre ne répond pas."""
    try:
        d = get_json(config.REF_REGISTRE)
        v = d["dist-tags"]["latest"]
        return v, d.get("time", {}).get(v, "")
    except Exception as e:  # noqa: BLE001
        log.warning("registre npm injoignable (%s), version en cache conservée", e)
        return None, ""


def charger(hors_ligne=False, rafraichir=False) -> Referentiel:
    brut = {}
    version, publie = (None, "") if hors_ligne else _version()
    for nom in config.REF_FICHIERS:
        dest = config.BRUT / f"ref_{nom}.json"
        ancienne = lire_meta(dest).get("version")
        if version:
            # une nouvelle version publiée remplace le cache, quel que soit son âge
            telecharger(config.REF_BASE.format(version=version, nom=nom), dest, "ref",
                        rafraichir or (bool(ancienne) and ancienne != version) or (dest.exists() and not ancienne),
                        extra_meta={"version": version, "maj_source": publie})
        else:
            telecharger(config.REF_BASE.format(version=ancienne or "latest", nom=nom), dest, "ref", rafraichir, hors_ligne)
        brut[nom] = json.loads(dest.read_text(encoding="utf-8"))
    meta = lire_meta(config.BRUT / "ref_communes.json")

    def garder(dep):
        return isinstance(dep, str) and (len(dep) == 2 or dep in config.DEPS_DROM)

    actuelles = [c for c in brut["communes"] if c.get("type") == "commune-actuelle" and garder(c.get("departement"))]
    c2e, noms_epci = {}, {}
    for e in brut["epci"]:
        noms_epci[e["code"]] = e["nom"]
        for m in e.get("membres", []):
            c2e[m["code"]] = e["code"]
    com = pd.DataFrame({
        "code": [c["code"] for c in actuelles],
        "nom": [c["nom"] for c in actuelles],
        "pop": [c.get("population") or 0 for c in actuelles],
        "dep": [c["departement"] for c in actuelles],
        "reg": [c.get("region") for c in actuelles],
    })
    com["epci"] = com["code"].map(c2e).fillna("C" + com["code"])
    noms_pseudo = dict(zip("C" + com["code"], com["nom"]))
    actuels = set(com["code"])

    anciens = {}
    for c in brut["communes"]:
        if c.get("type") == "commune-actuelle":
            continue
        cible = c.get("chefLieu") or c.get("commune")
        if cible in actuels:
            anciens[c["code"]] = cible

    pop = dict(zip(com["code"], com["pop"]))
    cps = {}
    for c in actuelles:
        for cp in c.get("codesPostaux") or []:
            if cp not in cps or pop[c["code"]] > pop[cps[cp]]:
                cps[cp] = c["code"]

    ep = com.groupby("epci").agg(pop=("pop", "sum")).reset_index().rename(columns={"epci": "code"})
    ep["nom"] = ep["code"].map(lambda k: noms_epci.get(k) or noms_pseudo.get(k, k))
    dep_maj = (com.groupby(["epci", "dep"])["pop"].sum().reset_index()
               .sort_values("pop", ascending=False).drop_duplicates("epci"))
    ep["dep"] = ep["code"].map(dict(zip(dep_maj["epci"], dep_maj["dep"])))

    deps = pd.DataFrame([{"code": d["code"], "nom": d["nom"], "reg": d["region"]}
                         for d in brut["departements"] if garder(d["code"])])
    deps["pop"] = deps["code"].map(com.groupby("dep")["pop"].sum()).fillna(0).astype(int)
    regs = pd.DataFrame([{"code": r["code"], "nom": r["nom"]} for r in brut["regions"]])
    regs["pop"] = regs["code"].map(com.groupby("reg")["pop"].sum()).fillna(0).astype(int)
    regs = regs[regs["pop"] > 0]

    JOURNAL.note("Référentiel Etalab", "ok",
                 f"version {meta.get('version', 'non consignée')} du paquet decoupage-administratif, {len(com)} communes, "
                 f"{len(ep)} EPCI, {len(deps)} départements",
                 url=meta.get("url", ""), lignes=len(com), date_donnees=(meta.get("maj_source") or "")[:10])
    JOURNAL.controle("Population totale du référentiel", f"{com['pop'].sum():,}".replace(",", " "))
    return Referentiel(com, ep[["code", "nom", "pop", "dep"]], deps, regs, anciens, cps)
