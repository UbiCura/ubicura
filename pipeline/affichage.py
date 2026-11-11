"""Règle d'affichage unique des chiffres (plan de reprise de la présentation, étape 1, 30 octobre 2026).

Toute page et tout export lisent ici, pour un indicateur, un niveau et un territoire : la valeur, l'effectif et l'unité,
le repère et son nom, la médiane, la position, l'écart, la couleur, le statut, les arrondis, la source avec sa date et
sa licence, et la citation. Aucune page ne recalcule. Les pages écrites en Python (fiche d'un territoire, fiche d'un
indicateur, domaines) appellent cellule() ; les pages en JavaScript (comparateur, Croiser) lisent les mêmes valeurs,
déjà arrondies, avec leur couleur, leur statut et leur position, dans les données de l'atelier (publier()), et les
écrivent avec presentation/chiffres.js, qui applique les mêmes décimales.

Règles (docs/comparaison_et_feuille_de_route_2026-10-30.md, parties 3.2 et 3.5, décisions de Lucas du 30 octobre 2026).
- Unité, fixée par indicateur : une profession pour 10 000 habitants si la France en compte au moins 1 pour 10 000,
  sinon pour 100 000 ; les structures pour 100 000 personnes de leur public.
- Repère, le taux de l'ensemble des territoires du même niveau calculé comme le territoire, nommé « Ensemble des
  intercommunalités » (des départements, des régions), jamais le chiffre national ni « Moyenne » :
  - professions et structures, somme des effectifs rapportée à la somme des habitants concernés (structures, seulement
    là où le taux est publié) ;
  - distances, la distance médiane de tous les habitants du niveau (ceux de la France), calculée comme celle du
    territoire, et aucun repère pour un type recensé dans moins de 90 % des départements (« non recensé ») ;
  - part ou taux rapporté à la population (règle d'agrégation « moyenne pondérée » du catalogue), moyenne des
    territoires pondérée par leurs habitants, exacte pour une part de toute la population, approchée sinon ;
  - densité de population, somme des habitants rapportée à la somme des surfaces ;
  - indicateur qui ne s'additionne pas (médiane, taux standardisé, taux d'une sous-population inconnue par territoire),
    la médiane des territoires, nommée « Intercommunalité médiane » (« Département médian », « Région médiane »).
  Tous les territoires du niveau qui ont une valeur sont comptés pour le repère, la médiane et la position : Mayotte
  l'est, sauf pour la population concernée (sans recensement) et l'Assurance Maladie (régime non comparable).
- Couleur, seulement pour l'offre (professions et structures) : cuivre ou bleu si l'écart dépasse ce que le hasard
  explique et si le territoire est sous 0,8 fois ou au-dessus de 1,25 fois le repère, gris sinon. Le hasard est jugé
  comme dans le diagramme en entonnoir d'Explorer (analyses.limites_entonnoir) : si seul le hasard jouait, l'effectif
  suivrait une loi de Poisson de moyenne égale au repère multiplié par les habitants concernés ; l'écart dépasse le
  hasard quand l'effectif sort de l'intervalle qui contient 95 % de cette loi. Les seuils 0,8 et 1,25 sont ceux de la
  classe « proche » des cartes, si bien que la fiche et la carte disent la même chose. Aucune couleur pour le profil,
  les distances et les petits effectifs (moins de 5).
- Arrondis, dans arrondi() et nombre() seulement : densités et taux à une décimale, deux sous 1, aucune à partir de
  1 000 ; distances et pourcentages à une décimale ; euros à la dizaine ; effectifs entiers ; écarts entiers. Arrondi
  au plus proche, une demie vers le haut, sur l'écriture décimale de la valeur. Le CSV garde la pleine précision.
- Écart, rapport des deux valeurs pleines moins un, arrondi à l'écriture en pour cent entier (relecture du 31 octobre
  2026 : calculé sur les valeurs arrondies, il était faux d'un point ou plus pour 187 intercommunalités, et la phrase
  « dans la marge » contredisait parfois la couleur). Il peut différer d'un point du calcul refait à la main sur les
  valeurs affichées. Aucun écart pour une distance (on écrit les deux distances), un petit effectif ou un statut.
- Position, part des autres territoires du niveau dont la valeur est plus basse, « plus haut que 71 % des
  intercommunalités ».
- Statuts, écrits pareil partout (STATUTS).
"""
from __future__ import annotations

import bisect
import json
import math
import re
import statistics
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path

NIVEAUX = ("reg", "dep", "epci")
NIV_PLURIEL = {"reg": "régions", "dep": "départements", "epci": "intercommunalités"}
ENSEMBLE = {"reg": "Ensemble des régions", "dep": "Ensemble des départements", "epci": "Ensemble des intercommunalités"}
MEDIANE = {"reg": "Région médiane", "dep": "Département médian", "epci": "Intercommunalité médiane"}
PROCHE = (0.8, 1.25)
NIVEAU_HASARD = 0.95
PETIT_EFFECTIF = 5
SEUIL_RARE = 1.0          # pour 10 000 habitants en France, sous ce seuil une profession s'écrit pour 100 000
FINE = " "

# statuts d'une valeur, les mêmes mots sur les pages, dans les exports du comparateur et dans les CSV publiés
STATUTS = {
    "aucun": "aucun inscrit",
    "petit": "petit effectif",
    "non_recense": "non recensé",
    "non_publie": "non publié",
    "non_diffuse": "non diffusé",
    "estime": "estimé",
    "departement": "donnée du département",
}
AUCUNE_STRUCTURE = "aucune structure"   # « CMP pour adultes, aucune structure », jamais « aucune inscrite » après un nom masculin (audit du 6 novembre 2026)
# un zéro sans statut ne reste jamais seul (règle du projet) : la phrase qui dit ce qu'il signifie
ZERO = {"dist": "type présent dans la commune d'au moins la moitié des habitants",
        "ctx": "valeur nulle dans la source"}
# une lettre par statut ou couleur, pour les données des pages en JavaScript
CODES = {"aucun": "a", "petit": "p", "non_recense": "r", "non_publie": "n", "non_diffuse": "d", "estime": "e",
         "departement": "D", "haut": "h", "bas": "b"}
NATURE_REPERE = {
    "somme": "somme des effectifs rapportée à la somme des habitants des territoires du niveau",
    "mediane_habitants": "distance médiane de tous les habitants des territoires du niveau",
    # sans « moyenne » : le repère s'appelle partout « Ensemble des … » (règles du projet, partie 5, relecture du 1er novembre)
    "ponderee": "somme des valeurs des territoires du niveau pondérées par leurs habitants, rapportée au total des habitants",
    "surface": "somme des habitants rapportée à la somme des surfaces des territoires du niveau",
    "mediane_territoires": "médiane des territoires du niveau, l'indicateur ne s'additionnant pas",
}
SENS = {"offre": "offre de soins, comparée au repère avec une couleur",
        "acces": "accès, sans couleur de jugement", "contexte": "contexte, sans couleur de jugement"}


# -- arrondis et écriture des nombres -------------------------------------------------------------------------------
def genre(unite: str | None, ident: str = "") -> str:
    """Genre d'arrondi d'un indicateur d'après son unité : taux (densités et taux), part, distance, euros."""
    u = (unite or "").strip()
    if ident.startswith(("dist_", "distp_")) or u == "km":
        return "distance"
    if u.startswith("€") or u.endswith("€"):
        return "euros"
    if u.startswith("%"):
        return "part"
    if u.startswith(("minute", "min")):
        return "minutes"
    if u.startswith("patients"):            # patientèle moyenne des libéraux, un nombre de personnes
        return "entier"
    return "taux"


def _arr(v: float, d: int) -> float:
    """Arrondi au plus proche, une demie vers le haut, sur l'écriture décimale la plus courte de la valeur (10,45 s'écrit
    10,5, comme dans le CSV qui l'écrit 10,45 et comme Intl.NumberFormat dans les pages en JavaScript, et non 10,4 que
    donnerait sa valeur binaire 10,4499...) ; d négatif arrondit aux dizaines (-1)."""
    x = Decimal(repr(float(v)))
    if d >= 0:
        return float(x.quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))
    pas = Decimal(10) ** -d
    return float((x / pas).quantize(Decimal(1), rounding=ROUND_HALF_UP) * pas)


def decimales(v: float, g: str) -> int:
    """Décimales d'une valeur selon son genre, décidées sur la valeur arrondie (0,996 s'écrit 1,0)."""
    if g in ("entier", "euros", "ecart", "minutes"):
        return 0
    if g == "correlation":
        return 3
    if g in ("distance", "part"):
        return 1
    if abs(_arr(v, 2)) < 1:
        return 2
    return 0 if abs(_arr(v, 1)) >= 1000 else 1


def arrondi(v, g: str = "taux"):
    """Valeur arrondie comme elle s'écrit sur les pages, None conservé."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    v = float(v)
    if g == "euros":
        return _arr(v, -1)
    r = _arr(v, decimales(v, g))
    return 0.0 if r == 0 else r


def nombre(v, g: str = "taux") -> str:
    """Nombre à la française, arrondi selon son genre : espace fine insécable des milliers, virgule, vrai signe moins."""
    r = arrondi(v, g)
    if r is None:
        return ""
    d = 0 if r == 0 else decimales(r, g)
    s = f"{abs(r):,.{d}f}".replace(",", FINE).replace(".", ",")
    return ("−" if r < 0 else "") + s


def ecart_txt(e) -> str:
    """Écart en pour cent entier, signé (« −17 % »)."""
    if e is None:
        return ""
    p = int(Decimal(e * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return ("+" if p > 0 else "−" if p < 0 else "") + f"{abs(p)}{FINE}%"


def ecart_mots(e) -> str:
    """« 46 % sous l'ensemble », « 12 % au-dessus de l'ensemble » : l'écart dit en mots, sans signe à lire à côté d'une
    position (remarque du 31 octobre 2026 : « −46 % » près de « plus haut que 73 % » paraissait contraire)."""
    if e is None:
        return ""
    p = int(Decimal(abs(e) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return "au niveau de l'ensemble" if p == 0 else f"{p}{FINE}% {'sous' if e < 0 else 'au-dessus de'} l'ensemble"


# mots de la position, les seuls employés sur les pages (constats compris)
SENS_POSITION = {"haut": "plus haut que", "bas": "plus bas que", "loin": "plus loin que", "pres": "plus près que"}

# la clé en mots, quand l'écart et la position vont en sens contraire, la même sous un tableau et dans un constat
CLE_CONTRAIRE = {
    "haut": "L'ensemble est calculé sur le total de tous les territoires, donc tiré par les plus peuplés : un territoire "
            "peut être sous l'ensemble et plus haut que la plupart des {niveaux}.",
    "bas": "L'ensemble est calculé sur le total de tous les territoires, donc tiré par les plus peuplés : un territoire "
           "peut être au-dessus de l'ensemble et plus bas que la plupart des {niveaux}.",
    # distances, sans écart écrit : le « mais » se lit sur la valeur et l'ensemble affichés (1er novembre 2026)
    "pres": "L'ensemble est calculé sur les habitants de tous les territoires, donc tiré par les plus peuplés, où les "
            "distances sont courtes : un territoire peut être plus loin que l'ensemble et plus près que la plupart des "
            "{niveaux}.",
    "loin": "L'ensemble est calculé sur les habitants de tous les territoires, donc tiré par les plus peuplés : un "
            "territoire peut être plus près que l'ensemble et plus loin que la plupart des {niveaux}.",
}


def sens_contraire(e, pos_txt: str) -> str | None:
    """« haut » quand le territoire est sous l'ensemble et pourtant plus haut que la plupart des territoires, « bas »
    dans l'autre sens, None sinon (remarques de Lucas du 31 octobre 2026 : « 17 % sous l'ensemble » à côté de « plus
    haut que 71 % » se lisait comme une contradiction, sur la fiche comme dans les constats). Un écart qui s'arrondit à
    0 % n'est pas contraire."""
    if e is None or not pos_txt or not ecart_mots(e) or ecart_mots(e).startswith("au niveau"):
        return None
    if e < 0 and pos_txt.startswith(SENS_POSITION["haut"]):
        return "haut"
    if e > 0 and pos_txt.startswith(SENS_POSITION["bas"]):
        return "bas"
    return None


def _nombre_affiche(t) -> float | None:
    """« 22 680 », « 2,6 » ou « 2,6 km » relu en nombre, tel que le lecteur le voit."""
    t = re.sub(r"[\s  ]|km|€|%", "", str(t or "")).replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def sens_contraire_affiche(v_txt, ref_txt, pos_txt: str) -> str | None:
    """Sens contraire lu sur les deux nombres que le lecteur voit côte à côte, la valeur et l'ensemble, quand aucun écart
    n'est écrit (distances, petits effectifs) : « 4,4 km… ensemble : 2,6 km, plus près que 52 % » se lisait comme une
    contradiction (relecture des fiches construites du 1er novembre 2026, 407 tuiles). Deux nombres égals à l'affichage ne
    sont pas contraires. « haut » ou « loin » quand la valeur est sous l'ensemble et la position au-dessus, « bas » ou
    « pres » dans l'autre sens."""
    v, r = _nombre_affiche(v_txt), _nombre_affiche(ref_txt)
    if v is None or r is None or v == r or not pos_txt:
        return None
    for cle in (("haut", "loin") if v < r else ("bas", "pres")):
        if pos_txt.startswith(SENS_POSITION[cle]):
            return cle
    return None


def avant_position(e_mots: str, e_ecrit: bool, mais: bool, ref_txt, kind, v_txt=None) -> str:
    """Ce qui précède la position dans une cellule ou une ligne, pour que « mais » ne commence jamais une cellule ni une
    phrase (relecture v2 des fiches construites, 1er novembre 2026 : 1 814 cellules commençaient par « mais ») :
    l'écart quand il est écrit (« 45 % sous l'ensemble »), sinon, quand la position va contre la valeur, le sens de la
    valeur par rapport à l'ensemble, avec l'ensemble (« plus loin que l'ensemble (2,6 km) », « sous l'ensemble
    (10,8) ») : « ensemble 3,2 km, mais plus près que 56 % » n'opposait rien (audit du 6 novembre 2026) ; rien sinon."""
    if e_ecrit and e_mots:
        return e_mots
    if mais and ref_txt:
        km = " km" if kind == "dist" else ""
        v, r = _nombre_affiche(v_txt), _nombre_affiche(ref_txt)
        if v is None or r is None or v == r:
            return f"ensemble {ref_txt}{km}"
        if kind == "dist":
            sens = "plus loin que l'ensemble" if v > r else "plus près que l'ensemble"
        else:
            sens = "au-dessus de l'ensemble" if v > r else "sous l'ensemble"
        return f"{sens} ({ref_txt}{km})"
    return ""


# une distance médiane qui s'arrondit à 0 : la formule du tableau des distances, jamais « 0 km » ni « à moins de 0 km »
DANS_COMMUNE = "dans la commune d'au moins la moitié des habitants"


def distance_nulle(v_txt) -> bool:
    """Vrai quand la distance affichée vaut 0 (« 0 km », « 0,0 km ») : Nord Basse-Terre, Montluçon (relecture v2)."""
    return _nombre_affiche(v_txt) == 0


def contraire(e, e_ecrit: bool, v_txt, ref_txt, pos_txt: str) -> str | None:
    """La règle du « mais », une seule pour la fiche : sur l'écart quand il est écrit à côté de la position, sur la
    valeur et l'ensemble affichés sinon."""
    return sens_contraire(e, pos_txt) if e_ecrit else sens_contraire_affiche(v_txt, ref_txt, pos_txt)


# Indicateurs dont un intervalle de confiance est prévu : les effectifs du répertoire (taux de professionnels) et les
# ALD standardisées. Les mesures de recensement (population, revenus, pauvreté) et les distances n'en auront pas, et
# n'annoncent rien (relecture de clarté du 31 octobre 2026, défaut 3).
INTERVALLE_IDS = {"ald_23"}


def intervalle_prevu(ident: str, kind: str) -> bool:
    return kind == "prof" or ident in INTERVALLE_IDS


def cle_contraire(sens: str | None, lv: str) -> str:
    return CLE_CONTRAIRE[sens].format(niveaux=NIV_PLURIEL[lv]) if sens else ""


def cle_contraire_plusieurs(sens: list, lv: str) -> str:
    """Une seule phrase quand plusieurs sens contraires se lisent côte à côte (tuiles d'une fiche) : deux clés presque
    identiques se suivaient (audit du 6 novembre 2026). Le début commun est dit une fois, les cas sont joints par « ou »."""
    sens = [s for s in dict.fromkeys(sens) if s]
    if len(sens) < 2:
        return cle_contraire(sens[0], lv) if sens else ""
    cas = {"haut": "sous l'ensemble et plus haut que la plupart des {niveaux}",
           "bas": "au-dessus de l'ensemble et plus bas que la plupart des {niveaux}",
           "pres": "plus loin que l'ensemble et plus près que la plupart des {niveaux}",
           "loin": "plus près que l'ensemble et plus loin que la plupart des {niveaux}"}
    return ("L'ensemble est calculé sur le total de tous les territoires et de leurs habitants, donc tiré par les plus "
            "peuplés : un territoire peut être " + ", ou ".join(cas[s] for s in sens).format(niveaux=NIV_PLURIEL[lv]) + ".")


def position_txt(p, lv: str, kind: str = "", pb=None) -> str:
    """« plus haut que 71 % des intercommunalités » ; sous la moitié, l'autre sens, « plus bas que 94 % » (pb, la part
    des autres territoires dont la valeur est plus haute) ; pour une distance, « plus loin que » ou « plus près que »
    (relectures du 30 octobre 2026)."""
    q = position_code(p, pb)
    if q is None:
        return ""
    bas = q < 0
    mot = SENS_POSITION[("pres" if bas else "loin") if kind == "dist" else ("bas" if bas else "haut")]
    if abs(q) == 100:
        # accordé : « tous les autres départements », « toutes les autres intercommunalités » (relecture v2, mineur 3)
        return f"{mot} {'tous les autres' if lv == 'dep' else 'toutes les autres'} {NIV_PLURIEL[lv]}"
    return f"{mot} {abs(q)}{FINE}% des {NIV_PLURIEL[lv]}"


def position_code(p, pb=None) -> int | None:
    """La position en un nombre, publié tel quel pour les pages en JavaScript (presentation/chiffres.js), pour que la
    fiche et Comparer écrivent les mêmes mots (audit du 6 novembre 2026) : n pour « plus haut que n % », −n pour « plus
    bas que n % », ±100 pour « tous les autres »."""
    if p is None:
        return None
    bas = pb is not None and p < .5
    q = pb if bas else p
    # au contact (défaut m9, Mayotte « plus bas que 100 % ») : « tous les autres » quand c'est exact, et 99 % au plus
    # quand l'arrondi ferait croire qu'aucun territoire ne reste de l'autre côté
    n = 100 if q >= 1 else min(99, int(Decimal(q * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)))
    return -n if bas else n


def mediane_mots(med, med_txt: str, kind: str, lv: str) -> str:
    """« médiane 7,3 », ou, quand la moitié des territoires n'a aucun inscrit, la phrase plutôt qu'un 0 ou « aucun »."""
    if med == 0 and kind in ("prof", "lieux"):
        return f"la moitié des {NIV_PLURIEL[lv]} sans {'inscrit' if kind == 'prof' else 'structure'}"
    return f"médiane {med_txt}"


def conserver(v, d: int = 2):
    """Valeur arrondie à d décimales pour site_data.json, avec une décimale de plus tant que cet arrondi changerait
    celui des pages (5,24563 gardé 5,246 et non 5,25, qui s'écrirait 5,3 au lieu de 5,2)."""
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return None
    v = float(v)
    for k in range(d, 9):
        r = _arr(v, k)
        if all(_arr(r, q) == _arr(v, q) for q in (-1, 0, 1, 2)):
            return r
    return v


def unite_prof(n_france, pop_france) -> int:
    """10 000, ou 100 000 pour une profession rare (moins de 1 pour 10 000 habitants en France)."""
    if n_france is None or not pop_france:
        return 10000
    return 100000 if n_france / pop_france * 1e4 < SEUIL_RARE else 10000


def par_habitants(sd: dict, prof: str) -> int:
    n = (sd.get("france", {}).get("n", {}).get(prof) or [None, None, None])[2]
    return unite_prof(n, sd.get("france", {}).get("pop"))


def txt_unite(fac: int) -> str:
    return "pour 100 000 habitants" if fac == 100000 else "pour 10 000 habitants"


# -- dates des sources, lues dans un seul fichier de la version (journal.json) ----------------------------------------
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
        "décembre"]


def date_longue(iso: str | None) -> str | None:
    if not iso or not re.match(r"\d{4}-\d{2}-\d{2}", iso):
        return None
    a, m, j = iso[:10].split("-")
    return f"{int(j)}{'er' if j == '01' else ''} {MOIS[int(m) - 1]} {a}"


@lru_cache(maxsize=8)
def _journal(dossier: str) -> dict:
    f = Path(dossier) / "journal.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def dates_sources(dernier: Path) -> dict[str, str]:
    """Date des données de chaque source (« RPPS activité » : « 2026-10-29 »), une seule par source, lue dans le journal
    des sources de la version (journal.json, colonne date_donnees), le seul fichier qui date les sources."""
    return {s["source"]: s["date_donnees"] for s in _journal(str(dernier)).get("sources", []) if s.get("date_donnees")}


def date_source(dernier: Path, nom: str) -> str | None:
    """Date longue d'une source du journal (« 29 octobre 2026 »)."""
    return date_longue(dates_sources(dernier).get(nom))


def date_rpps(dernier: Path) -> str | None:
    """Date de l'extraction du répertoire RPPS de la version, la même sur toutes les pages."""
    return date_source(dernier, "RPPS activité")


# source du journal de chaque indicateur, d'après sa source dans le catalogue (première règle qui s'applique)
SOURCES_JOURNAL = [
    (r"^prof:", "RPPS activité"),
    # mêmes classeurs de la DREES que la série des effectifs (même page, même date)
    (r"^age60_", "DREES, démographie des professionnels de santé"),
    (r"^(lieux_|dist_|distp_)", "FINESS (Finess+)"),
    (r"INSEE, dossier complet", "INSEE dossier complet"),
    (r"CépiDc|suicide", "Santé publique France, décès par suicide"),
]


def source_journal(ind: dict, sources: dict[str, str]) -> str | None:
    """Nom de la source du journal qui date l'indicateur, ou None."""
    ident, src = ind.get("id", ""), ind.get("source") or ""
    for motif, nom in SOURCES_JOURNAL:
        if re.search(motif, ident) or re.search(motif, src):
            return nom if nom in sources else None
    mots = [m for m in re.split(r"[\s,()]+", src) if len(m) > 3]
    best, score = None, 0
    for nom in sources:
        s = sum(1 for m in mots if m.lower() in nom.lower())
        if s > score:
            best, score = nom, s
    return best if score >= 2 else None


# -- calcul -----------------------------------------------------------------------------------------------------------
def _poisson_bornes(mu: float) -> tuple[float, float]:
    from scipy import stats
    a = (1 - NIVEAU_HASARD) / 2
    return stats.poisson.ppf(a, mu), stats.poisson.ppf(1 - a, mu)


def couleur(n, v, ref, base, fac) -> str | None:
    """« haut », « bas » ou None (gris) pour un effectif n d'une densité v, au repère ref (même unité), base habitants
    concernés, fac l'unité (10 000 ou 100 000)."""
    if n is None or v is None or not ref or not base or n < PETIT_EFFECTIF:
        return None
    rapport = v / ref
    if PROCHE[0] <= rapport <= PROCHE[1]:
        return None
    bas, haut = _poisson_bornes(ref / fac * base)
    if rapport < PROCHE[0] and n < bas:
        return "bas"
    if rapport > PROCHE[1] and n > haut:
        return "haut"
    return None


class Serie:
    """Valeurs d'un indicateur à un niveau, alignées sur les territoires de site_data, avec repère et répartition."""
    __slots__ = ("id", "lv", "codes", "v", "n", "base", "st", "ref", "ref_type", "med", "pos", "posb", "coul", "fac",
                 "genre", "kind")

    def ref_lib(self):
        return MEDIANE[self.lv] if self.ref_type == "mediane_territoires" else ENSEMBLE[self.lv]


class Affichage:
    """Toutes les valeurs affichées d'une version, calculées une fois (site_data.json et journal.json)."""

    def __init__(self, sd: dict, dernier: Path | None = None):
        from . import lieux_profil
        self.sd = sd
        self.dernier = Path(dernier) if dernier else None
        self.niv = sd["niveaux"]
        self.pos = {lv: {u["c"]: k for k, u in enumerate(self.niv[lv]["units"])} for lv in NIVEAUX}
        self.ctx = {c["id"]: (j, c) for j, c in enumerate(sd.get("contexte", []))}
        types = (sd.get("lieux") or {}).get("types", [])
        self.complet = {t["id"]: bool(t.get("complet")) for t in types}
        self.lib_type = {t["id"]: t.get("lib") for t in types}
        self.fr_dist = {k: (v[0] if isinstance(v, list) and v else None) for k, v in ((sd.get("lieux") or {}).get("fr") or {}).items()}
        self.fr_distp = {k: (v[0] if isinstance(v, list) and v else None)
                         for k, v in ((sd.get("lieux") or {}).get("fr_public") or {}).items()}
        self.parts = {t: lieux_profil.denominateur(t)[0] for t in self.complet}
        lim = (sd.get("limites") or {}).get("manque_sae") or {}
        self.manques = set((lim.get("territoires") or {}).keys())
        self.profs = {p["id"]: p for p in sd.get("professions", [])}
        self._cache = {}
        self._pleins = {}

    # -- catalogue minimal ------------------------------------------------------------------------------------------
    def meta(self, ident: str) -> dict | None:
        """Unité, genre, nature (prof, lieux, dist, ctx) et unité écrite d'un indicateur."""
        if ident.startswith("prof:"):
            p = ident.split(":")
            if p[1] not in self.profs:
                return None
            fac = par_habitants(self.sd, p[1])
            return {"id": ident, "kind": "prof", "prof": p[1], "mode": p[2] if len(p) > 2 else "all", "fac": fac,
                    "unite": txt_unite(fac), "genre": "taux", "sens": "offre", "repere": "somme"}
        if ident not in self.ctx:
            return None
        c = self.ctx[ident][1]
        if ident.startswith("lieux_"):
            kind, sens, rep = "lieux", "offre", "somme"
        elif ident.startswith(("dist_", "distp_")):
            kind, sens, rep = "dist", "acces", "mediane_habitants"
        else:
            kind, sens = "ctx", "contexte"
            agr, tv = c.get("agregation") or "", c.get("type_valeur") or ""
            rep = "ponderee" if agr.startswith("moyenne_ponderee") else "surface" if tv == "densité" else "mediane_territoires"
        return {"id": ident, "kind": kind, "fac": 100000 if kind == "lieux" else 1, "unite": c.get("unite") or "",
                "genre": genre(c.get("unite"), ident), "sens": sens, "repere": rep}

    # -- séries -----------------------------------------------------------------------------------------------------
    def serie(self, ident: str, lv: str) -> Serie | None:
        cle = (ident, lv)
        if cle not in self._cache:
            self._cache[cle] = self._serie(ident, lv)
        return self._cache[cle]

    def _x(self, lv, ident):
        """Valeurs d'un indicateur du catalogue à un niveau, en pleine précision quand le fichier contexte_<niveau>.csv
        de la version les donne (site_data.json les garde à deux décimales, qu'un second arrondi à une décimale
        pourrait fausser : 5,24563 km s'écrit 5,2, et 5,25 s'écrirait 5,3), sinon celles de site_data.json."""
        j = self.ctx[ident][0]
        x = [(u["x"][j] if u.get("x") and j < len(u["x"]) else None) for u in self.niv[lv]["units"]]
        col = self._precis(lv).get(ident)
        if col is None:
            return x
        return [(col.get(u["c"], v) if v is not None else None) for u, v in zip(self.niv[lv]["units"], x)]

    def _precis(self, lv) -> dict:
        if lv not in self._pleins:
            import csv
            out = {}
            for suffixe in ("", "_odbl"):
                f = self.dernier / f"contexte_{lv}{suffixe}.csv" if self.dernier else None
                if not f or not f.exists():
                    continue
                with f.open(encoding="utf-8-sig") as h:
                    for l in csv.DictReader(h, delimiter=";"):
                        for k, v in l.items():
                            if k in self.ctx and v not in ("", None):
                                try:
                                    out.setdefault(k, {})[l["code"]] = float(v.replace(",", "."))
                                except ValueError:
                                    pass
            self._pleins[lv] = out
        return self._pleins[lv]

    def _serie(self, ident: str, lv: str) -> Serie | None:
        m = self.meta(ident)
        if m is None or lv not in self.niv:
            return None
        us = self.niv[lv]["units"]
        S = Serie()
        S.id, S.lv, S.codes, S.fac, S.genre, S.kind = ident, lv, [u["c"] for u in us], m["fac"], m["genre"], m["kind"]
        S.ref_type = m["repere"]
        pops = [u["pop"] for u in us]
        N = len(us)
        S.n, S.base, S.st, S.coul = [None] * N, [None] * N, [None] * N, [None] * N
        if m["kind"] == "prof":
            a = (self.niv[lv]["n"].get(m["prof"]) or {}).get(m["mode"])
            if not a:
                return None
            S.n = list(a)
            S.base = pops
            S.v = [(k / p * m["fac"]) if (k is not None and p) else None for k, p in zip(a, pops)]
            tn = sum(k for k in a if k is not None)
            tp = sum(p for k, p in zip(a, pops) if k is not None)
            S.ref = tn / tp * m["fac"] if tp else None
            for i, k in enumerate(a):
                if k == 0:
                    S.st[i] = "aucun"
                elif k is not None and k < PETIT_EFFECTIF:
                    S.st[i] = "petit"
        elif m["kind"] == "lieux":
            typ = ident[6:]
            x = self._x(lv, ident)
            cnt = (self.niv[lv].get("lieux") or {}).get(typ) or [None] * N
            # habitants concernés, parts du public en pleine précision comme lieux.taux_publics
            parts = [self._x(lv, p) for p in (self.parts.get(typ) or []) if p in self.ctx]
            S.n, S.v = list(cnt), x
            for i, u in enumerate(us):
                b = u["pop"]
                if self.parts.get(typ):
                    q = [col[i] for col in parts]
                    b = b * sum(q) / 100 if len(q) == len(self.parts[typ]) and all(t is not None for t in q) else None
                S.base[i] = b
            num = sum(k for k, v, b in zip(S.n, x, S.base) if v is not None and k is not None and b)
            den = sum(b for k, v, b in zip(S.n, x, S.base) if v is not None and k is not None and b)
            S.ref = num / den * 1e5 if den else None
            comp = self.complet.get(typ, True)
            for i, (k, v) in enumerate(zip(S.n, x)):
                if not comp:
                    S.st[i] = "non_recense"
                elif v is None and k is not None:
                    S.st[i] = "non_publie"
                elif k == 0:
                    S.st[i] = "aucun"
                elif k is not None and k < PETIT_EFFECTIF:
                    S.st[i] = "petit"
        elif m["kind"] == "dist":
            # « distp_ » : médiane du public que sert la structure, comparée à la médiane du même public en France
            public = ident.startswith("distp_")
            typ = ident.split("_", 1)[1]
            S.v = self._x(lv, ident)
            comp = self.complet.get(typ, True)
            S.ref = (self.fr_distp if public else self.fr_dist).get(typ) if comp else None
            for i, v in enumerate(S.v):
                if not comp:
                    S.st[i] = "non_recense"
                elif v is None and self._manque(lv, S.codes[i], us[i]):
                    S.st[i] = "non_publie"
        else:
            S.v = self._x(lv, ident)
            c = self.ctx[ident][1]
            np_ = (c.get("non_publies") or {}).get(lv) or {}
            for i, v in enumerate(S.v):
                if v is None and S.codes[i] in np_:
                    S.st[i] = "non_diffuse"
            if (c.get("etat") or "").startswith("estim"):
                S.st = [s or ("estime" if v is not None else None) for s, v in zip(S.st, S.v)]
            ok = [(v, p) for v, p in zip(S.v, pops) if v is not None and p]
            if S.ref_type == "ponderee":
                S.ref = sum(v * p for v, p in ok) / sum(p for _, p in ok) if ok else None
            elif S.ref_type == "surface":
                surf = sum(p / v for v, p in ok if v > 0)
                S.ref = sum(p for v, p in ok if v > 0) / surf if surf else None
            else:
                S.ref = statistics.median([v for v, _ in ok]) if ok else None
        # valeurs montrées : un type non recensé ne montre ni taux ni distance
        S.v = [None if s_ == "non_recense" else v for v, s_ in zip(S.v, S.st)]
        vals = sorted(v for v in S.v if v is not None)
        if not vals and not any(S.st):
            return None
        S.med = statistics.median(vals) if vals else None
        if S.ref_type == "mediane_territoires":
            S.ref = S.med
        S.pos = [(bisect.bisect_left(vals, v) / (len(vals) - 1)) if (v is not None and len(vals) > 1) else None
                 for v in S.v]
        S.posb = [((len(vals) - bisect.bisect_right(vals, v)) / (len(vals) - 1)) if (v is not None and len(vals) > 1)
                  else None for v in S.v]
        if m["sens"] == "offre":
            S.coul = [couleur(k, v, S.ref, b, S.fac) if not s_ else None
                      for k, v, b, s_ in zip(S.n, S.v, S.base, S.st)]
        return S

    def _manque(self, lv, code, u):
        return code in self.manques or f"{lv}:{code}" in self.manques or (lv == "epci" and u.get("p") in self.manques)

    # -- une valeur prête à écrire ----------------------------------------------------------------------------------
    def cellule(self, ident: str, lv: str, code: str, echelle: str | None = None) -> dict | None:
        """Tout ce qu'une page écrit pour un indicateur et un territoire. echelle « dep » : valeur du département,
        montrée sur la fiche d'une intercommunalité (statut « donnée du département »)."""
        S = self.serie(ident, lv)
        if S is None or code not in self.pos[lv]:
            return None
        k = self.pos[lv][code]
        v, n, st, g = S.v[k], S.n[k], S.st[k], S.genre
        if echelle == "dep":
            st = st or "departement"
        va, ra = arrondi(v, g), arrondi(S.ref, g)
        e = None
        if va is not None and ra and v is not None and S.ref and S.kind != "dist"                 and st not in ("aucun", "petit", "non_recense", "non_publie"):
            e = v / S.ref - 1   # valeurs pleines, l'arrondi ne vient qu'à l'écriture
        coul = S.coul[k] if S.kind in ("prof", "lieux") else None
        statut = st
        s_txt = (AUCUNE_STRUCTURE if statut == "aucun" and S.kind == "lieux" else STATUTS[statut]) if statut else ""
        note = ZERO.get(S.kind, "") if va == 0 and statut in (None, "departement") else ""
        return {"id": ident, "lv": lv, "code": code, "kind": S.kind, "genre": g, "fac": S.fac,
                "v": v, "va": va, "v_txt": nombre(v, g), "n": n, "n_txt": nombre(n, "entier") if n is not None else "",
                "ref": S.ref, "ra": ra, "ref_txt": nombre(S.ref, g), "ref_lib": S.ref_lib(), "ref_type": S.ref_type,
                "med": S.med, "med_txt": nombre(S.med, g), "med_lib": MEDIANE[lv],
                "pos": S.pos[k], "pos_txt": position_txt(S.pos[k], lv, S.kind, S.posb[k]),
                "med_mots": mediane_mots(S.med, nombre(S.med, g), S.kind, lv),
                "e": e, "e_txt": ecart_txt(e), "e_mots": ecart_mots(e), "couleur": coul, "statut": statut, "statut_txt": s_txt, "note": note}

    # -- réglette d'une ligne ---------------------------------------------------------------------------------------
    def echelle(self, ident: str, lv: str) -> dict | None:
        """Échelle commune à toutes les réglettes d'un indicateur à un niveau : bornes, quartiles, répartition des
        territoires en 24 classes (chemin de l'aire grise, viewBox 0 0 100 16). L'offre et les distances partent de 0 ;
        le contexte du 2e centile. Les 2 % les plus hauts sortent de l'échelle, leur point est posé au bord."""
        cle = ("echelle", ident, lv)
        if cle in self._cache:
            return self._cache[cle]
        S = self.serie(ident, lv)
        vals = sorted(v for v in (S.v if S else []) if v is not None)
        e = None
        if len(vals) >= 3:
            q = lambda p: vals[min(len(vals) - 1, int(p * (len(vals) - 1) + .5))]  # noqa: E731
            haut = q(.98)
            bas = 0.0 if S.kind in ("prof", "lieux", "dist") or q(.02) >= 0 and q(.02) < .25 * haut else q(.02)
            haut += .04 * (haut - bas)
            haut = max(haut, (S.ref or 0) * 1.08, (S.med or 0) * 1.08)
            if haut > bas:
                n = [0] * 24
                for v in vals:
                    n[min(23, max(0, int(24 * (v - bas) / (haut - bas))))] += 1
                m = max(n)
                d = "M0 16" + "".join(f"V{16 - 15 * k / m:.1f}H{(i + 1) * 100 / 24:.2f}" for i, k in enumerate(n)) + "V16Z"
                e = {"bas": bas, "haut": haut, "q1": statistics.quantiles(vals, n=4)[0],
                     "q3": statistics.quantiles(vals, n=4)[2], "distrib": d.replace(".00", "")}
        self._cache[cle] = e
        return e

    def reglette(self, ident: str, lv: str, code: str, cel: dict | None = None) -> dict | None:
        """Positions de la réglette d'un territoire, en pour cent de la largeur (--q1, --q3, --rep, --med, --val), sa
        classe (haut, bas, petit, sans) et sa description pour les lecteurs d'écran. Mêmes valeurs que cellule()."""
        cel = cel or self.cellule(ident, lv, code)
        e = self.echelle(ident, lv)
        if cel is None or e is None:
            return None
        pc = lambda x: None if x is None else f"{min(100, max(0, 100 * (x - e['bas']) / (e['haut'] - e['bas']))):.1f}%"  # noqa: E731
        st = cel["statut"]
        classe = "sans" if st == "aucun" or cel["v"] is None else "petit" if st == "petit" else cel["couleur"] or ""
        g = cel["genre"]
        mots = [cel["v_txt"] or STATUTS.get(st, ""), cel["pos_txt"],
                f"{cel['ref_lib'].lower()} {cel['ref_txt']}" if cel["ref_txt"] else "",
                # une médiane nulle se dit en mots, jamais « 0 » (défaut m6)
                (cel["med_mots"] if cel["med"] == 0 and cel["kind"] in ("prof", "lieux")
                 else f"{cel['med_lib'].lower()} {cel['med_txt']}") if cel["ref_type"] != "mediane_territoires" else ""]
        info = (f"{cel['ref_lib'].lower()} {cel['ref_txt']} ; {cel['med_mots']} ; la moitié des {NIV_PLURIEL[lv]} "
                f"entre {nombre(e['q1'], g)} et {nombre(e['q3'], g)}")
        r = {"info": info, "q1": pc(e["q1"]), "q3": pc(e["q3"]), "rep": pc(cel["ref"]), "med": pc(cel["med"]),
             "val": pc(cel["v"]) if cel["v"] is not None and st != "aucun" else "0%", "distrib": e["distrib"],
             "classe": classe, "hors": cel["v"] is not None and cel["v"] > e["haut"],
             "aria": ", ".join(m for m in mots if m), "bornes": (nombre(e["bas"], g), nombre(e["haut"], g))}
        r["h"] = self.histogramme(ident, lv, cel)
        return r

    BARRES = 30
    BARRE_MIN = 1.0    # hauteur d'une barre non vide, en dix-huitièmes : posée sur l'axe plein, au moins 1 px
    PART_AUCUN = .4    # au-delà, la barre des territoires sans inscrit se détache, à sa propre échelle

    @staticmethod
    def nb_barres(n: int) -> int:
        """30 barres pour les intercommunalités, 20 pour les départements, 12 pour les régions : une barre doit réunir
        assez de territoires pour que la forme se lise (18 régions en 30 barres faisaient des barres éparses)."""
        return 30 if n >= 200 else 20 if n >= 60 else 12

    def histogramme(self, ident: str, lv: str, cel: dict) -> dict | None:
        """Réglette de la direction visuelle (validation de Lucas du 31 octobre 2026) : histogramme des territoires du
        même niveau, axe arrêté au 98e centile (chevron quand des territoires vont au-delà) mais élargi pour que le
        repère, la médiane et le point du territoire restent visibles ; positions en pour cent de la largeur ;
        étiquettes du repère et de la médiane attachées à leur marque, alignées à gauche ou à droite près des bords.
        Lisibilité (relecture du 31 octobre 2026) : une distribution très étalée, dont le 98e centile dépasse trois fois
        le 90e (densité de population), arrête son axe au 90e centile, sinon tout se tasse contre le zéro ; le nombre de
        barres suit le nombre de territoires (nb_barres) ; une barre non vide garde une hauteur visible (BARRE_MIN).
        Relecture esthétique du même jour : la hauteur des barres suit la racine carrée du nombre de territoires, pour que
        les classes peu peuplées restent lisibles sans écraser la forme ; quand plus de 40 % des territoires n'ont aucun
        inscrit ou aucune structure, leur barre se détache, sur la même échelle que les autres (la plus haute, donc),
        et leur part est écrite dessus (« aucun : 83 % »), ou dans l'étiquette de la médiane quand l'étiquette de
        l'ensemble est trop près du bord gauche."""
        S = self.serie(ident, lv)
        vals = sorted(v for v in (S.v if S else []) if v is not None)
        if len(vals) < 3:
            return None
        q = lambda p: vals[min(len(vals) - 1, int(p * (len(vals) - 1) + .5))]  # noqa: E731
        kind, g = cel["kind"], cel["genre"]
        centile = 90 if q(.9) > 0 and q(.98) > 3 * q(.9) else 98
        bas = 0.0 if kind in ("prof", "lieux", "dist") or 0 <= q(.02) < .25 * q(.98) else q(.02)
        haut = q(centile / 100)
        v = cel["v"] if cel["v"] is not None and cel["statut"] != "aucun" else None
        for x in (cel["ref"], cel["med"], v):
            if x is not None and x > haut:
                haut = x * 1.04
        if haut <= bas:
            return None
        nb = self.nb_barres(len(vals))
        n = [0] * nb
        for x in vals:
            if bas <= x <= haut:
                n[min(nb - 1, int(nb * (x - bas) / (haut - bas)))] += 1
        zeros = sum(1 for x in vals if x == 0) if kind in ("prof", "lieux") and bas == 0 else 0
        detache = zeros > self.PART_AUCUN * len(vals)
        if detache:
            n[0] -= zeros     # la barre « aucun » à part, sur la même échelle que les autres : la plus haute
        m = max(max(n), zeros) or 1
        pc = lambda x: round(max(0.0, min(100.0, 100 * (x - bas) / (haut - bas))), 2)  # noqa: E731
        u = " km" if kind == "dist" else ""
        med_seule = cel["ref_type"] == "mediane_territoires"
        # jamais un 0 seul : une médiane nulle s'écrit en mots
        med_txt = (": aucun inscrit" if kind == "prof" else ": aucune structure") if cel["med"] == 0 and kind in ("prof", "lieux")             else cel["med_txt"] + u
        cote = lambda p: "g" if p < 14 else "d" if p > 86 else "c"  # noqa: E731
        rep = None if med_seule or cel["ref"] is None else pc(cel["ref"])
        med = None if cel["med"] is None else pc(cel["med"])
        # la part des territoires sans inscrit écrite sur leur barre (« aucun : 83 % ») ; si l'étiquette de l'ensemble la
        # touche dans la page, figures.js la reporte dans celle de la médiane
        part = nombre(100 * zeros / len(vals), "entier") + " %" if detache else ""
        aucun_lab = f"aucun : {part}" if detache else ""
        # un seul chemin pour toutes les barres (viewBox 0 0 nb 18), bien plus léger que des rectangles ; hauteur en
        # racine carrée de l'effectif de la barre, « aucun » compris, si bien que la hauteur croît toujours avec la part
        hauteur = lambda k: max(self.BARRE_MIN, 18 * (k / m) ** .5)  # noqa: E731
        comptes = ([zeros] if detache else []) + [k for k in n if k]
        chemin = (f"M.12 18v-{hauteur(zeros):.2f}h.76V18z" if detache else "") + "".join(
            f"M{i + .12:g} 18v-{hauteur(k):.2f}h.76V18z" for i, k in enumerate(n) if k)
        return {"chemin": chemin, "nb": nb, "centile": centile, "val": None if v is None else pc(v), "rep": rep, "med": med,
                "cote_rep": cote(rep) if rep is not None else "", "cote_med": cote(med) if med is not None else "",
                "rep_txt": cel["ref_txt"] + u, "med_txt": med_txt, "chevron": vals[-1] > haut,
                "axe": f"axe de {nombre(bas, g)} à {nombre(haut, g)}{u}" + (", quelques territoires au-delà" if vals[-1] > haut else "")
                       + (", arrêté au 90e centile, la répartition étant très étalée" if centile == 90 else "")
                       + (f", {part} des territoires sans {'inscrit' if kind == 'prof' else 'structure'}" if detache else ""),
                "aucun": part, "aucun_lab": aucun_lab, "comptes": comptes}

    # -- publication pour les pages en JavaScript ---------------------------------------------------------------------
    def publier(self, ident: str, lv: str, garde: list[int]) -> dict | None:
        """Repère, médiane, codes de statut ou de couleur et positions d'un indicateur, pour les territoires gardés par
        l'atelier (indices de site_data)."""
        S = self.serie(ident, lv)
        if S is None:
            return None
        codes = "".join(CODES.get(S.st[k] or S.coul[k] or "", ".") for k in garde)
        return {"r": arrondi(S.ref, S.genre), "t": S.ref_type, "m": arrondi(S.med, S.genre),
                "c": codes, "p": [None if S.pos[k] is None else int(Decimal(S.pos[k] * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)) for k in garde],
                "q": [position_code(S.pos[k], S.posb[k]) for k in garde]}

    def valeurs(self, ident: str, lv: str, garde: list[int]) -> list | None:
        """Valeurs arrondies comme sur les pages, pour les territoires gardés."""
        S = self.serie(ident, lv)
        if S is None:
            return None
        return [arrondi(S.v[k], S.genre) for k in garde]


def pour_js() -> dict:
    """Mots et règles partagés avec presentation/chiffres.js."""
    return {"statuts": {CODES[k]: v for k, v in STATUTS.items()}, "aucune": AUCUNE_STRUCTURE, "zero": ZERO,
            "ensemble": ENSEMBLE, "mediane": MEDIANE, "pluriel": NIV_PLURIEL, "proche": PROCHE,
            "nature": NATURE_REPERE}


# -- citation -----------------------------------------------------------------------------------------------------------
def citation(auteur: str, titre: str, unite: str | None, projet: str, date_version: str, adresse: str | None = None,
             doi: str | None = None) -> str:
    """Citation d'un encadré : titre exact, unité après une virgule, adresse affichée (sans « .html »), DOI de la
    version. « Pithon L. (2026). Professionnels de santé mentale, pour 10 000 habitants. Ubi Cura, version du ... »"""
    t = titre.strip().rstrip(".")
    if unite:
        u = unite.strip()
        t += ", " + (u[:1].lower() + u[1:] if not re.match(r"^[A-Z]{2}", u) else u)
    s = f"{auteur} ({date_version[-4:]}). {t}. {projet}, version du {date_version}"
    if adresse:
        s += ", " + re.sub(r"\.html$", "", adresse.replace("https://", ""))
    if doi:
        s += f", doi:{doi}"
    return s + "."


def ligne_source(sources: list[tuple[str, str | None, str | None]]) -> str:
    """Ligne de source d'un encadré, au même format partout : « RPPS du 29 octobre 2026, Licence Ouverte 2.0 ; ... »."""
    out = []
    for nom, date, lic in sources:
        out.append(nom + (f" du {date}" if date else "") + (f", {lic}" if lic else ""))
    return " ; ".join(out) + "." if out else ""


# -- catalogue : les champs qui font apparaître un indicateur de lui-même (partie 4.7) ---------------------------------
CHAMPS_CATALOGUE = ("id", "nom_court", "nom_long", "domaine", "sous_theme", "unite", "base", "sens", "repere",
                    "niveau_fin", "niveaux", "annees", "source", "date", "licence", "diffusion", "limite", "couche",
                    "phrase")
# limite en une ligne d'un indicateur sans limite propre, ce que toute valeur de sa nature ne dit pas
LIMITE_NATURE = {
    "prof": "Une densité de personnes ne dit ni le temps de travail, ni les délais de rendez-vous, ni le reste à charge.",
    "lieux": "Une structure est comptée là où les patients sont reçus, sans sa capacité ni ses horaires.",
    "dist": "Distance à vol d'oiseau depuis le centre de la commune des habitants, pas un temps de trajet.",
    "ctx": "Décrit les habitants du territoire, ne mesure pas un besoin de soins.",
}
PHRASE = {
    "offre": "{territoire} compte {valeur} {unite} ({effectif}), {position}, face à l'{repere_nom} ({repere}).",
    "acces": "La moitié des habitants de {territoire} vit à moins de {valeur} km, face à {repere} km pour l'{repere_nom}.",
    "contexte": "{indicateur} : {valeur} {unite} pour {territoire}, {position} ({repere_nom}, {repere}).",
}
NIVEAU_CODE = {"communes": "com", "intercommunalités": "epci", "départements": "dep", "régions": "reg"}


def catalogue(sd: dict, dernier: Path | None = None) -> list[dict]:
    """Catalogue des indicateurs publiés (professions et indicateurs du profil, structures et distances comprises), avec
    les champs dont les gabarits, les exports et l'API ont besoin. Un champ manquant bloque la construction
    (controle_affichage.catalogue)."""
    from . import domaines as D
    from . import themes as TH
    from .fiche_territoire import annee_indicateur
    T = Affichage(sd, dernier)
    srcs = dates_sources(dernier) if dernier else {}
    det = {s["source"]: s.get("detail", "") for s in _journal(str(dernier)).get("sources", [])} if dernier else {}
    lim = sd.get("limites") or {}
    alias = sd.get("limites_alias") or {}

    def limite(cle, kind):
        li = lim.get(cle) or next((lim[v] for k, v in alias.items() if (cle == k or cle.startswith(k)) and v in lim), None)
        t = (li or {}).get("court") or ((li or {}).get("texte") or "").split(". ")[0]
        return t.rstrip(".") + "." if t else LIMITE_NATURE[kind]

    out = []
    rpps = date_rpps(dernier) if dernier else None
    for p in sd.get("professions", []):
        ident = f"prof:{p['id']}:all"
        m = T.meta(ident)
        niv = [lv for lv in ("epci", "dep", "reg") if (sd["niveaux"][lv]["n"].get(p["id"]) or {}).get("all")]
        dom, sous = D.classer({"id": "prof:" + p["id"], "famille": p.get("famille")})
        nom = p.get("libelle") or p["id"]
        out.append({"id": ident, "nom_court": nom, "nom_long": f"{nom}, {m['unite']}", "domaine": dom, "sous_theme": sous,
                    "unite": m["unite"], "base": m["fac"], "sens": m["sens"], "repere": m["repere"],
                    "niveau_fin": niv[0] if niv else None, "niveaux": niv,
                    "annees": [f"répertoire RPPS du {rpps}"] if rpps else [], "source": "RPPS, Agence du numérique en santé",
                    "date": srcs.get("RPPS activité"), "licence": "Licence Ouverte 2.0", "diffusion": "ouverte",
                    "limite": limite("prof:" + p["id"], "prof"), "couche": "aplats", "phrase": PHRASE[m["sens"]],
                    # thèmes transversaux et marque sensible (pipeline/themes_indicateurs.csv, 8 novembre 2026)
                    "themes": TH.themes_de("prof:" + p["id"]), "sensible": TH.sensible("prof:" + p["id"])})
    for c in sd.get("contexte", []):
        m = T.meta(c["id"])
        nom_src = source_journal(c, srcs)
        an = annee_indicateur(c, sd)
        # année écrite dans la définition de l'indicateur (« Année 2024. », « au 1er janvier 2026 »), sinon dans le
        # détail de sa source au journal (« année 2024 », « années 2024 à 2025 », « décembre 2024 »)
        for texte in (c.get("explication") or "", det.get(nom_src, "") if nom_src else ""):
            if an is not None:
                break
            r = re.search(r"[Aa]nnées? (\d{4})(?: à (\d{4}))?|millésime (\d{4})|au 1er \w+ (\d{4})|(?:janvier|février|mars|"
                          r"avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre) (\d{4})", texte)
            if r:
                an = r.group(1) + (f" à {r.group(2)}" if r.group(2) else "") if r.group(1) else next(g for g in r.groups()[2:] if g)
        if an is None and m["kind"] in ("lieux", "dist") and srcs.get("FINESS (Finess+)"):
            an = srcs["FINESS (Finess+)"][:4]
        niv = [x for x in (c.get("niveaux_codes") or [NIVEAU_CODE.get(n) for n in c.get("niveaux", [])]) if x != "com"]
        dom, sous = D.classer(c)
        odbl = "ODbL" in (c.get("licence") or "")
        out.append({"id": c["id"], "nom_court": c.get("label"), "nom_long": ", ".join(x for x in (c.get("label"), c.get("unite")) if x),
                    "domaine": dom, "sous_theme": sous, "unite": c.get("unite"),
                    "base": {"taux": 100000 if m["kind"] == "lieux" else None, "part": "%", "distance": "km",
                             "euros": "€", "minutes": "minutes"}.get(m["genre"]) or c.get("unite"),
                    "sens": m["sens"], "repere": m["repere"], "niveau_fin": niv[0] if niv else None, "niveaux": niv,
                    "annees": [str(an)] if an else [], "source": c.get("source"), "date": srcs.get(nom_src) if nom_src else None,
                    "licence": c.get("licence"),
                    "diffusion": "fichiers _odbl, hors de l'offre payante" if odbl else "ouverte",
                    "limite": limite(c["id"], m["kind"]), "couche": "aplats", "phrase": PHRASE[m["sens"]],
                    "themes": TH.themes_de(c["id"]), "sensible": TH.sensible(c["id"])})
    return out


def champs_manquants(cat: list[dict]) -> dict[str, list[str]]:
    manque: dict[str, list[str]] = {}
    for e in cat:
        for ch in CHAMPS_CATALOGUE:
            if e.get(ch) in (None, "", []):
                manque.setdefault(ch, []).append(e["id"])
    return manque
