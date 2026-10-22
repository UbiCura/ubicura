"""Lecture et contrôle du registre des structures de soins (config.LIEUX_PROFIL, 16 octobre 2026).

Le registre dit, pour chaque type activé, son public, son dénominateur, ses sources de confirmation, sa référence publiée
et les analyses à lui appliquer. Les analyses (pipeline/structures_analyses.py, pipeline/lieux.py, pipeline/graphiques.py)
lisent ces fonctions au lieu de listes écrites à la main. Activer une analyse pour un type, c'est ajouter son nom à la
liste « analyses » du type dans config.py.
"""
from __future__ import annotations

from . import config

# Une analyse s'écrit « nom » ou « nom:paramètre » dans la liste « analyses » d'un type.
#   indicateur            le type devient un indicateur de contexte (lieux_* et dist_*), donc croisable, avec son escalier
#                         de distance selon le niveau de vie et son indice de concentration
#   sensibilite           résultats recalculés avec les seules structures confirmées
#   zones                 zones d'éloignement contiguës (Moran local, Benjamini-Hochberg)
#   double_eloignement:X  le type compte dans le champ X de config.DOUBLE_ELOIGNEMENT_CHAMPS
#   charge                charge par CMP d'après la SAE
#   typologie:X           décrit dans le profil de la typologie de la famille X (sm, sante, tout)
#   eloignement:X         figure de l'éloignement selon le niveau de vie de la famille X (sm, sante), le premier type est
#                         commenté dans le rapport
ANALYSES = {"indicateur", "sensibilite", "zones", "double_eloignement", "charge", "typologie", "eloignement"}
AVEC_PARAMETRE = {"double_eloignement", "typologie", "eloignement"}
PUBLICS = {"adultes", "enfants", "tous", "grand_age"}
GENRES_REFERENCE = {"sae", "publiee"}
SOURCES_CONFIRMATION = {"etablissement", "source_publique", "has", "has_essms", "sirene", "sae", "principal"}
CLES = {"public", "denominateur", "confirmation", "reference", "analyses", "limite", "a_venir"}
# analyses dont les types doivent être recensés dans au moins config.LIEUX_COUVERTURE_MIN des départements
ANALYSES_TERRITORIALES = {"indicateur", "sensibilite", "zones", "double_eloignement", "typologie", "eloignement"}
# analyses qui testent une hypothèse, leur sortie porte les colonnes p et q_bh
ANALYSES_STATISTIQUES = {"zones"}


def decouper(tag: str) -> tuple[str, str | None]:
    nom, _, param = tag.partition(":")
    return nom, (param or None)


def types_avec(analyse: str, param: str | None = None) -> list[str]:
    """Types du registre portant l'analyse (et le paramètre s'il est donné), dans l'ordre du registre."""
    return [t for t, p in config.LIEUX_PROFIL.items()
            if any(decouper(tag) == (analyse, param) if param else decouper(tag)[0] == analyse for tag in p["analyses"])]


def parametres(analyse: str) -> list[str]:
    """Paramètres distincts d'une analyse (champs du double éloignement, familles de la typologie), dans l'ordre."""
    vus: list[str] = []
    for p in config.LIEUX_PROFIL.values():
        for tag in p["analyses"]:
            nom, param = decouper(tag)
            if nom == analyse and param and param not in vus:
                vus.append(param)
    return vus


def types_eloignement() -> dict:
    """Types de la figure de l'éloignement selon le niveau de vie, par famille (sm, sante). Le premier est commenté."""
    return {fam: types_avec("eloignement", fam) for fam in parametres("eloignement")}


def denominateur(tid: str) -> tuple[list[str], str]:
    """Colonnes de contexte donnant la part du public du type et son libellé, ([], \"\") pour la population entière."""
    d = (config.LIEUX_PROFIL.get(tid) or {}).get("denominateur")
    return (list(d[0]), d[1]) if d else ([], "")


def champs_double_eloignement() -> dict:
    """Champs du double éloignement au format {clé: (professions, types, libellé)}, types tirés du registre."""
    out = {}
    for cle, (profs, lib) in config.DOUBLE_ELOIGNEMENT_CHAMPS.items():
        out[cle] = (list(profs), types_avec("double_eloignement", cle), lib)
    return out


def references() -> list[tuple]:
    """Chiffres publiés auxquels des types sont confrontés, au format (type, chiffre, date, objet, (titre, adresse))."""
    return sorted((t, r["valeur"], r["date"], r["objet"], r["source"])
                  for t, p in config.LIEUX_PROFIL.items() if (r := p.get("reference")) and r["genre"] == "publiee")


def valider() -> None:
    """Contrôle la forme du registre. Une erreur d'écriture est une erreur de configuration, pas une donnée à signaler."""
    ids = {t[0] for t in config.LIEUX_TYPES}
    for tid, p in config.LIEUX_PROFIL.items():
        assert tid in ids, f"{tid} : type inconnu de LIEUX_TYPES"
        assert set(p) <= CLES and {"public", "analyses"} <= set(p), f"{tid} : clés {sorted(set(p) ^ CLES)}"
        assert p["public"] in PUBLICS, f"{tid} : public {p['public']}"
        assert set(p.get("confirmation", [])) <= SOURCES_CONFIRMATION, f"{tid} : source de confirmation inconnue"
        d = p.get("denominateur")
        assert d is None or (len(d) == 2 and d[0] and isinstance(d[1], str)), f"{tid} : dénominateur"
        r = p.get("reference")
        if r:
            assert r["genre"] in GENRES_REFERENCE and 0 < r["ecart_max"] < 1, f"{tid} : référence"
            assert (r["genre"] == "sae" and r.get("champ")) or (
                r["genre"] == "publiee" and {"valeur", "date", "objet", "source"} <= set(r)), f"{tid} : référence"
        lim = p.get("limite")
        assert lim is None or lim in config.LIMITES, f"{tid} : limite {lim}"
        for tag in p["analyses"]:
            nom, param = decouper(tag)
            assert nom in ANALYSES, f"{tid} : analyse {tag}"
            assert (param is not None) == (nom in AVEC_PARAMETRE), f"{tid} : paramètre de {tag}"
            if nom == "double_eloignement":
                assert param in config.DOUBLE_ELOIGNEMENT_CHAMPS, f"{tid} : champ {param}"
