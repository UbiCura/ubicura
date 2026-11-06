"""Adresses vérifiées sur les sources des établissements, pour tout type de structure (chantier des structures précises,
31 octobre 2026).

Une structure dont FINESS et le ROR ne donnent ni coordonnées ni adresse utilisable reste au centre de sa commune, ou
porte l'adresse du siège de son gestionnaire dans une autre commune. Le fichier contenus/adresses_verifiees.csv donne,
pour une structure désignée par son type, sa commune et son numéro FINESS (sinon son nom), l'adresse où elle reçoit,
lue sur une source de l'établissement ou une autre source publique, avec cette source et la date de lecture. Les
verdicts des CMP (pipeline/verdicts.py) gardent leur propre colonne adresse_reelle, ce fichier vaut pour les autres
types et pour les CMP sans verdict.

Règles.
- Une ligne désigne une seule structure, du même type (ou du type parent pour les lignes par public des CMP), dans la
  même commune, qui porte ce numéro FINESS (le sien, rapproché ou réuni) ou, sans numéro, ce nom simplifié. Plusieurs
  structures possibles, ou aucune, la ligne n'est pas appliquée et le contrôle le dit.
- L'adresse est géocodée comme les autres (service de géocodage de l'IGN, avec cache). Trouvée au numéro ou à la rue,
  elle remplace l'emplacement de la structure, avec une précision qui dit qu'elle a été vérifiée. Introuvable, la
  structure garde son emplacement.
- Une adresse dans une autre commune (« rue, code postal commune ») fait compter la structure dans cette commune, celle
  où elle reçoit, comme pour les adresses trouvées dans une commune voisine (décision de Lucas du 29 octobre 2026), sa
  commune d'inscription reste dans commune_inscription.
- Une ligne sans source ou sans date n'est pas appliquée (une réponse sans source vérifiable ne change pas le statut
  d'une donnée).
- Comme les listes vérifiées des établissements (pipeline/structures_verifiees.py), une adresse se revérifie au bout
  d'un an (DUREE_JOURS), et aussi quand elle ne désigne plus une seule structure ou que le géocodage ne la trouve
  plus. Le contrôle du journal « Structures de soins, adresses vérifiées à revérifier » les liste, et
  outils/comparer_versions.py le signale avant toute publication.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from . import config
from .util import JOURNAL, entier_fr

FICHIER = config.RACINE / "contenus" / "adresses_verifiees.csv"
COLS = ["type", "commune", "finess", "nom", "adresse", "source", "date", "commentaire"]
NIVEAUX = {"adresse": "verifiee_adresse", "rue": "verifiee_rue"}
REVERIFIER = "Structures de soins, adresses vérifiées à revérifier"


def _txt(v) -> str:
    return v if isinstance(v, str) else ""


def charger() -> pd.DataFrame:
    if not FICHIER.exists():
        return pd.DataFrame(columns=COLS)
    v = pd.read_csv(FICHIER, sep=";", dtype=str, encoding="utf-8").fillna("")
    return v.reindex(columns=COLS, fill_value="")


def _famille(type_lieu: str) -> set:
    """Le type et ses lignes par public (CMP pour adultes et pour enfants pour un CMP), ou le type parent et ses
    lignes pour une ligne par public."""
    parents = {t[0]: t[4]["parent"] for t in config.LIEUX_TYPES if t[4].get("parent")}
    p = parents.get(type_lieu, type_lieu)
    return {p} | {k for k, v in parents.items() if v == p}


def designer(x: pd.DataFrame, r) -> list:
    """Indices des lignes de la structure désignée par la ligne r (toutes ses lignes par public), [] si aucune ou
    plusieurs structures répondent."""
    from .lieux import _simple
    fam = _famille(r.type)
    m = x["type"].isin(fam) & (x["commune"].astype(str) == r.commune)
    cand = x[m]
    if r.finess:
        nums = cand.apply(lambda s: {n for c in ("finess", "finess_rapproche", "finess_absorbes")
                                     for n in _txt(s.get(c)).split(",") if n}, axis=1) if len(cand) else pd.Series(dtype=object)
        cand = cand[[r.finess in n for n in nums]] if len(cand) else cand
    if r.nom and (len(cand) > 1 or not r.finess):
        cible = _simple(r.nom)
        noms = cand.apply(lambda s: {_simple(_txt(s.get(c))) for c in ("nom_affiche", "nom", "nom_finess")}, axis=1) \
            if len(cand) else pd.Series(dtype=object)
        cand = cand[[cible in n for n in noms]] if len(cand) else cand
    # une structure et ses lignes par public portent la même clé de lieu (un CMP pour adultes et un CMP pour enfants du
    # même hôpital dans la même commune en ont deux, pipeline/lieux.py)
    lieux = set(cand["lieu"].astype(str)) if "lieu" in cand else set()
    if len(lieux) != 1:
        return []
    return list(x.index[x["type"].isin(fam) & (x["lieu"].astype(str) == next(iter(lieux)))])


def a_reverifier(v: pd.DataFrame, rendu: dict, aujourd: dt.date | None = None) -> list[str]:
    """Lignes à revérifier, vérification de plus d'un an, sans structure unique ou introuvable au géocodage."""
    from .structures_verifiees import DUREE_JOURS
    aujourd = aujourd or dt.date.today()
    out = []
    for r in v.itertuples():
        try:
            age = (aujourd - dt.date.fromisoformat(r.date.strip())).days
        except ValueError:
            age = None
        if age is None or age > DUREE_JOURS:
            out.append(f"{r.nom} ({r.commune}), vérification de plus d'un an ou non datée")
    out += [f"{x['nom'] or x['finess']} ({x['commune']}), plus de structure unique correspondante"
            for x in rendu.get("non_designees", [])]
    if not rendu.get("hors_ligne"):
        out += [f"{x['nom']} ({x['commune']}), adresse introuvable au géocodage" for x in rendu.get("non_geocodees", [])]
    return out


def appliquer(lieux: pd.DataFrame, ref, hors_ligne: bool, v: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict]:
    """Applique les adresses vérifiées. Renvoie les structures et un compte rendu (appliquées, sans source, sans
    structure, ambiguës ou absentes, introuvables au géocodage)."""
    from .lieux import _geocoder
    from .verdicts import _adresse
    v = charger() if v is None else v
    rendu = {"lignes": len(v), "appliquees": 0, "sans_source": 0, "non_designees": [], "non_geocodees": [],
             "autre_commune": 0, "hors_ligne": hors_ligne}
    if v.empty or lieux.empty:
        return lieux, rendu
    x = lieux.copy()
    rattach = ref.communes.set_index("code")[["epci", "dep", "reg"]]
    for c in ("adresse_verifiee_source", "adresse_verifiee_date"):
        if c not in x:
            x[c] = None
    a_geo = []
    plan = []
    for r in v.itertuples():
        if not (r.source.strip() and r.date.strip() and r.adresse.strip()):
            rendu["sans_source"] += 1
            continue
        idx = designer(x, r)
        if not idx:
            rendu["non_designees"].append({"type": r.type, "commune": r.commune, "finess": r.finess, "nom": r.nom})
            continue
        voie, com = _adresse(r.adresse, r.commune, ref)
        a_geo.append((voie, com))
        plan.append((r, idx, voie, com))
    if not plan:
        return x, rendu
    g = _geocoder(pd.DataFrame(a_geo, columns=["voie", "commune"]), hors_ligne).dropna(subset=["lat"])
    g = g.drop_duplicates(["voie", "commune"]).set_index(["voie", "commune"])
    for r, idx, voie, com in plan:
        if (voie, com) not in g.index or g.at[(voie, com), "niveau"] not in NIVEAUX:
            rendu["non_geocodees"].append({"type": r.type, "commune": r.commune, "nom": r.nom, "adresse": r.adresse})
            continue
        x.loc[idx, "adresse"] = voie
        x.loc[idx, "lat"] = float(g.at[(voie, com), "lat"])
        x.loc[idx, "lon"] = float(g.at[(voie, com), "lon"])
        x.loc[idx, "precision"] = NIVEAUX[g.at[(voie, com), "niveau"]]
        x.loc[idx, "adresse_verifiee_source"] = r.source.strip()
        x.loc[idx, "adresse_verifiee_date"] = r.date.strip()
        if com != r.commune and com in rattach.index:
            if "commune_inscription" not in x:
                x["commune_inscription"] = None
            x.loc[idx, "commune_inscription"] = x.loc[idx, "commune"]
            x.loc[idx, "commune"] = com
            for c in ("epci", "dep", "reg"):
                if c in x:
                    x.loc[idx, c] = rattach.at[com, c]
            rendu["autre_commune"] += 1
        rendu["appliquees"] += 1
    JOURNAL.controle("Adresses vérifiées sur les sources des établissements (contenus/adresses_verifiees.csv), appliquées",
                     f"{entier_fr(rendu['appliquees'])} sur {entier_fr(rendu['lignes'])} ("
                     f"{entier_fr(rendu['autre_commune'])} comptées dans la commune de leur adresse, "
                     f"{entier_fr(rendu['sans_source'])} sans source ou sans date, "
                     f"{entier_fr(len(rendu['non_designees']))} sans structure unique correspondante, "
                     f"{entier_fr(len(rendu['non_geocodees']))} introuvables au géocodage)")
    # hors ligne, une adresse nouvelle n'est pas encore dans le cache du géocodage, elle n'est pas « à revérifier »
    rv = a_reverifier(v, rendu)
    rendu["a_reverifier"] = rv
    JOURNAL.controle(REVERIFIER + " (attendu, aucune)", "aucune" if not rv else f"{len(rv)} : " + " ; ".join(rv[:10]))
    return x, rendu
