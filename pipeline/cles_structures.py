"""Clé persistante des structures de soins (identifiant attendu par le contrat de données de l'API, 29 octobre 2026).

La clé interne d'une structure (colonne lieu) est faite de son numéro FINESS ou de son nom et de sa commune, elle change
quand un établissement réinscrit ses structures sous de nouveaux numéros (CH Sainte-Marie de Nice, août 2025 et
septembre 2026) ou que le ROR renomme une unité. La clé persistante (id_structure) suit la structure elle-même d'une
version à l'autre. Elle est tenue dans un registre (resultats/historique/registre_structures.csv), jamais réutilisée,
et une structure disparue y garde sa clé avec la dernière version où elle figurait.

Règle de rapprochement entre la version du jour et le registre, structure par structure, de même type, un à un, dans cet
ordre, chaque étape ne portant que sur ce que les précédentes n'ont pas rapproché :
0. la même clé interne (rien n'a changé) ;
1. un numéro FINESS en commun (numéro, rapprochés et absorbés) dans la même commune ;
2. la même unité du ROR (nom normalisé) chez le même gestionnaire dans la même commune ;
3. le même nom normalisé dans la même commune, ou la même voie chez le même gestionnaire dans la même commune (une
   unité du ROR peut perdre son gestionnaire et son numéro d'une version à l'autre, 450 cas le 26 octobre 2026) ;
4. le même gestionnaire, à moins de 100 mètres, quand les deux emplacements sont connus à l'adresse.
Une structure que rien ne rapproche reçoit une clé nouvelle. Les lignes par public (CMP pour adultes, pour enfants)
prennent la clé de leur structure. Contrôle dans le journal, nombre rapproché à chaque étape, nouvelles, disparues, et
aucune clé portée par deux structures."""
from __future__ import annotations

import hashlib
import math

import numpy as np
import pandas as pd

from . import config
from .util import JOURNAL

REGISTRE = config.RESULTATS / "historique" / "registre_structures.csv"
COLS = ["id_structure", "type", "lieu", "entite_juridique", "commune", "nom", "adresse", "numeros", "unites", "latitude",
        "longitude", "precis", "premiere_version", "derniere_version"]
PRECIS = ("adresse géocodée au numéro", "adresse géocodée à la rue", "coordonnées FINESS", "coordonnées du ROR")
ETAPES = ("clé interne", "numéro FINESS", "unité du ROR", "nom ou voie", "emplacement")


def _parents() -> dict:
    """Type parent de chaque type de lignes par public."""
    return {t[0]: t[4]["parent"] for t in config.LIEUX_TYPES if t[4].get("parent")}


def _txt(v) -> str:
    return v if isinstance(v, str) else ""


def _simple(s) -> str:
    from .lieux import _simple as s_
    return s_(_txt(s))


def _rue(s) -> str:
    from .structures_verifiees import _rue as r_
    return r_(_txt(s))


def _numeros(r) -> frozenset:
    return frozenset(n for c in ("finess", "finess_rapproche", "finess_absorbes") for n in _txt(r.get(c)).split(",") if n)


def _unites(r) -> frozenset:
    return frozenset(_simple(u) for u in _txt(r.get("unites_noms") or r.get("unite_ror")).split(" | ") if u.strip())


def _lieu(t: pd.DataFrame) -> pd.Series:
    """Clé interne de la structure (colonne lieu), ou, dans un fichier publié qui ne la porte pas, ce qui la tient
    lieu pour réunir une structure et ses lignes par public (commune, nom, numéro FINESS, adresse, unité du ROR,
    provenance)."""
    if "lieu" in t:
        return t["lieu"]
    base = (t["commune"].map(_txt) + "|" + t["nom"].map(_txt) + "|" + t["finess"].map(_txt) + "|"
            + t["adresse"].map(_txt) + "|" + t.get("unite_ror", pd.Series("", index=t.index)).map(_txt)
            + "|" + t.get("provenance", pd.Series("", index=t.index)).map(_txt))
    # deux lignes identiques d'un même type (structure décrite deux fois) restent deux structures distinctes
    return base + "#" + base.groupby([t["type"], base]).cumcount().astype(str)


def decrire(t: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par structure (lignes par public écartées), avec ce qui sert au rapprochement."""
    par = _parents()
    lieu = _lieu(t)
    est_enfant = t["type"].isin(par)
    # une ligne par public sans sa ligne « tous publics » est décrite comme une structure à part entière
    meres = set(zip(t.loc[~est_enfant, "type"], lieu[~est_enfant]))
    orpheline = est_enfant & ~pd.Series([(par.get(ty), li) in meres for ty, li in zip(t["type"], lieu)], index=t.index)
    p = t[~est_enfant | orpheline].copy()
    d = pd.DataFrame({"lieu": _lieu(p), "type": p["type"], "entite_juridique": p["entite_juridique"].map(_txt),
                      "commune": p["commune"].map(_txt), "nom": p["nom"].map(_txt), "adresse": p["adresse"].map(_txt)})
    d["numeros"] = [",".join(sorted(_numeros(r))) for r in p.to_dict("records")]
    d["unites"] = [" | ".join(sorted(_unites(r))) for r in p.to_dict("records")]
    for c in ("latitude", "longitude"):
        d[c] = pd.to_numeric(p[c].astype(str).str.replace(",", "."), errors="coerce") if c in p else np.nan
    d["precis"] = p["emplacement"].isin(PRECIS) if "emplacement" in p else False
    return d.reset_index(drop=True)


def _nouvelle(r, version: str, prises: set) -> str:
    base = f"{r['type']}|{r['entite_juridique']}|{r['commune']}|{_simple(r['nom'])}|{version}"
    k = 0
    while True:
        cle = "S" + hashlib.sha1(f"{base}|{k}".encode("utf-8")).hexdigest()[:11]
        if cle not in prises:
            return cle
        k += 1


def _km(a, b) -> float:
    (y1, x1), (y2, x2) = a, b
    return 6371 * math.hypot(math.radians(x2 - x1) * math.cos(math.radians((y1 + y2) / 2)), math.radians(y2 - y1))


def rapprocher(d: pd.DataFrame, reg: pd.DataFrame) -> tuple[dict, dict]:
    """Index d'une structure du jour vers l'index de sa ligne du registre, et étape du rapprochement."""
    libres = set(reg.index)
    pris, etape = {}, {}
    cles = [
        lambda r: [(r["type"], r["lieu"])] if r["lieu"] else [],
        lambda r: [(r["type"], n, r["commune"]) for n in r["numeros"].split(",") if n],
        lambda r: [(r["type"], r["entite_juridique"], r["commune"], u) for u in r["unites"].split(" | ") if u and r["entite_juridique"]],
        lambda r: ([(r["type"], r["commune"], "n", _simple(r["nom"]))] if r["nom"] else [])
        + ([(r["type"], r["entite_juridique"], r["commune"], "r", _rue(r["adresse"]))] if r["entite_juridique"] and _rue(r["adresse"]) else []),
    ]
    for k, f in enumerate(cles):
        index = {}
        for j in libres:
            for c in f(reg.loc[j]):
                index.setdefault(c, set()).add(j)
        choix = {}
        for i, r in d.iterrows():
            if i in pris:
                continue
            cands = set().union(*[index.get(c, set()) for c in f(r)]) & libres if f(r) else set()
            if len(cands) == 1:
                choix[i] = cands.pop()
        # un à un, une ligne du registre désignée par deux structures du jour n'est rapprochée d'aucune
        demandes = pd.Series(list(choix.values())).value_counts() if choix else pd.Series(dtype=int)
        for i, j in choix.items():
            if demandes[j] == 1:
                pris[i], etape[i] = j, ETAPES[k]
                libres.discard(j)
    # étape 4, emplacement à moins de 100 mètres, même type et même gestionnaire, emplacements connus à l'adresse
    reste = d[~d.index.isin(list(pris)) & d["precis"] & (d["entite_juridique"] != "")]
    candidats = reg.loc[[j for j in libres if bool(reg.at[j, "precis"])]]
    for i, r in reste.iterrows():
        g = candidats[(candidats["type"] == r["type"]) & (candidats["entite_juridique"] == r["entite_juridique"])
                      & candidats.index.isin(list(libres))]
        proches = [j for j in g.index if _km((r["latitude"], r["longitude"]), (g.at[j, "latitude"], g.at[j, "longitude"])) < .1]
        if len(proches) == 1:
            pris[i], etape[i] = proches[0], ETAPES[4]
            libres.discard(proches[0])
    return pris, etape


def attribuer(t: pd.DataFrame, version: str, registre: pd.DataFrame | None = None) -> tuple[pd.Series, pd.DataFrame, dict]:
    """Clé persistante de chaque ligne de t (lieux du jour), registre mis à jour et compte rendu."""
    reg = registre if registre is not None else (
        pd.read_csv(REGISTRE, sep=";", dtype=str, keep_default_na=False) if REGISTRE.exists() else pd.DataFrame(columns=COLS))
    reg = reg.reindex(columns=COLS, fill_value="").reset_index(drop=True)
    for c in ("latitude", "longitude"):
        reg[c] = pd.to_numeric(reg[c].astype(str).str.replace(",", "."), errors="coerce")
    reg["precis"] = reg["precis"].astype(str).isin(["True", "true", "1"])
    d = decrire(t)
    pris, etape = rapprocher(d, reg)
    deja = set(reg["id_structure"])
    ids = []
    for i, r in d.iterrows():
        if i in pris:
            ids.append(reg.at[pris[i], "id_structure"])
        else:
            ids.append(_nouvelle(r, version, deja))
            deja.add(ids[-1])
    d["id_structure"] = ids
    if d["id_structure"].duplicated().any():
        raise ValueError("clé persistante portée par deux structures")
    # registre, lignes du jour mises à jour, disparues gardées telles quelles
    vus = {pris[i] for i in pris}
    jour = d.assign(derniere_version=version)
    jour["premiere_version"] = [reg.at[pris[i], "premiere_version"] if i in pris else version for i in d.index]
    nouveau = pd.concat([jour[COLS], reg.loc[~reg.index.isin(list(vus)), COLS]], ignore_index=True)
    compte = {e: sum(1 for x in etape.values() if x == e) for e in ETAPES}
    compte["nouvelles"] = len(d) - len(pris)
    # disparues depuis la version précédente, celles qui y figuraient encore et que rien ne rapproche
    precedente = reg["derniere_version"].max() if len(reg) else ""
    compte["disparues"] = int((~reg.index.isin(list(vus)) & (reg["derniere_version"] == precedente)).sum()) if len(reg) else 0
    par_lieu = dict(zip(zip(d["type"], d["lieu"]), d["id_structure"]))
    parents = _parents()
    cle = pd.Series([par_lieu.get((parents.get(ty, ty), li)) or par_lieu.get((ty, li))
                     for ty, li in zip(t["type"], _lieu(t))], index=t.index)
    return cle, nouveau, compte


def appliquer(t: pd.DataFrame, version: str) -> pd.Series:
    """Clé persistante des structures du jour, registre écrit, contrôle dans le journal."""
    cle, reg, c = attribuer(t, version)
    REGISTRE.parent.mkdir(parents=True, exist_ok=True)
    reg.to_csv(REGISTRE, sep=";", index=False, encoding="utf-8")
    JOURNAL.controle("Clé persistante des structures, rapprochées de la version précédente",
                     ", ".join(f"{c[e]} par {e}" for e in ETAPES) + f", {c['nouvelles']} nouvelles, "
                     f"{c['disparues']} disparues depuis (clé gardée, jamais réutilisée)")
    JOURNAL.controle("Clé persistante des structures, lignes sans clé (attendu, aucune)",
                     "aucune" if cle.notna().all() else str(int(cle.isna().sum())))
    return cle
