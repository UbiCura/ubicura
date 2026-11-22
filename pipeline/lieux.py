"""Structures de soins, réunion de FINESS et du ROR sans double compte (version 2, 12 octobre 2026).

Les unités du ROR (pipeline/sources/ror.py) et les établissements de FINESS (pipeline/sources/finess.py) sont classés
dans les types de config.LIEUX_TYPES. Une structure est un endroit où une offre d'un type est implantée. Sa clé est le numéro
FINESS d'établissement et la commune, si bien que plusieurs unités d'une même structure (consultations adultes, soins
ambulatoires...) et un établissement présent dans les deux bases ne comptent qu'une fois. Un établissement de FINESS
absent du ROR sous son numéro est rapproché d'une structure du ROR du même type, de la même entité juridique gestionnaire et
de la même commune (cas des CMP enregistrés dans FINESS sous leur propre numéro mais rattachés à l'hôpital dans le
ROR). Chaque structure garde sa provenance (FINESS et ROR, FINESS seul, ROR seul).

Emplacement, par ordre de préférence, coordonnées de FINESS (déjà géocodées par la Base Adresse Nationale),
coordonnées du ROR (Corse et PACA), adresse géocodée par le service de l'IGN (config.GEOCODAGE_CSV, cache dans
donnees/intermediaire), centre de la commune. La précision est écrite pour chaque structure.

Les professionnels déclarés sur place viennent du RPPS (numéro FINESS et commune de l'activité). Ils ne sont jamais
additionnés aux structures, et une structure sans professionnel déclaré peut accueillir des consultations de professionnels
déclarés à leur hôpital de rattachement (config.LIMITES["lieux"]).
"""
from __future__ import annotations

import io
import re
import unicodedata

import numpy as np
import pandas as pd

from . import config, lieux_profil
from .lecture import nombre
from .util import JOURNAL, entier_fr, log, norm

PROVENANCES = {"les_deux": "FINESS et ROR", "finess": "FINESS seul", "ror": "ROR seul",
               "ror_type": "ROR, type que FINESS ne distingue pas",
               "sources": "Absente des deux bases, d'après les sources de l'établissement",
               "nom_cmp": "Annoncé par le nom d'un CMP (CMP-CATTP), au même lieu",
               "autorisation": "Activité autorisée et exercée selon FINESS, sans unité de ce type dans le ROR"}
PRECISIONS = {"finess": "coordonnées FINESS", "ror": "coordonnées du ROR", "adresse": "adresse géocodée au numéro",
              "rue": "adresse géocodée à la rue", "lieu_dit": "adresse géocodée au lieu-dit",
              "commune": "centre de la commune",
              # chef-lieu dans la Base Adresse Nationale, plus près des habitants que le centre du contour (29 octobre
              # 2026), le libellé commence comme le précédent pour rester lu comme une position approchée
              "chef_lieu": "centre de la commune, au chef-lieu",
              # adresse du gestionnaire reprise pour une structure d'une autre commune (29 octobre 2026), jamais
              # géocodée dans la commune de la structure, où elle tomberait sur une rue homonyme
              "chef_lieu_gestionnaire": "centre de la commune, au chef-lieu (adresse du gestionnaire reprise)",
              "commune_gestionnaire": "centre de la commune (adresse du gestionnaire reprise)",
              "rattachement": "adresse de l'établissement de rattachement, lieu exact inconnu",
              # adresse lue sur une source de l'établissement (contenus/adresses_verifiees.csv, 31 octobre 2026)
              "verifiee_adresse": "adresse vérifiée sur une source de l'établissement, géocodée au numéro",
              "verifiee_rue": "adresse vérifiée sur une source de l'établissement, géocodée à la rue"}
CACHE_GEO = config.INTER / "geocodage_lieux.parquet"
REQUETE_GEO = "voie développée et commune, nom de rue plus long accepté, commune voisine"   # forme de la requête et de la règle
                                                                           # d'acceptation, un échec d'une autre forme
                                                                           # est cherché de nouveau
# abréviations des voies dans FINESS et le ROR, développées pour le géocodage (« R » rue, « AV » avenue, 29 octobre
# 2026, environ un dixième des adresses jusque-là introuvables retrouvées à la rue ou au numéro)
ABREVIATIONS = {"R": "Rue", "AV": "Avenue", "AVE": "Avenue", "BD": "Boulevard", "BLD": "Boulevard", "CHE": "Chemin",
                "CH": "Chemin", "PL": "Place", "RTE": "Route", "IMP": "Impasse", "ALL": "Allée", "LD": "Lieu-dit",
                "QU": "Quai", "QUA": "Quartier", "CRS": "Cours", "SQ": "Square", "PROM": "Promenade", "FG": "Faubourg",
                "HAM": "Hameau", "RES": "Résidence", "ST": "Saint", "STE": "Sainte", "GAL": "Général",
                "MAL": "Maréchal", "DR": "Docteur", "PDT": "Président"}


def voie_developpee(v: str) -> str:
    return " ".join(ABREVIATIONS.get(m.upper().strip("."), m) for m in str(v).split())
# professions dont on compte les personnes déclarées dans chaque lieu
PROFESSIONS = ["psychiatre", "pedopsychiatre", "q_psychiatrie_enfant", "psychologue", "infirmier", "orthophoniste",
               "psychomotricien", "ergotherapeute", "medecin_generaliste", "pediatre", "geriatre", "sage_femme",
               "masseur_kinesitherapeute", "urgentiste"]


def _enfants(u: pd.DataFrame) -> pd.Series:
    """Unité réservée aux enfants et aux adolescents, d'après la catégorie, l'âge maximal des patients ou le nom.
    Une unité de catégorie enfants dont les âges déclarés ne reçoivent que des adultes (18 ans au moins) n'en est pas
    une : « CMP ADULTES SAINT JUST EN CHEVALET », catégorie 281, de 18 à 150 ans, seule dans ce cas en France
    (relecture du 17 novembre 2026, réunie à tort au CMP pour enfants de la même rue)."""
    adultes_seuls = u["age_min"].notna() & (u["age_min"] >= 18)
    return ((u["categorie"].isin(["281", "282"]) & ~adultes_seuls)
            | (u["age_max"].notna() & (u["age_max"] <= config.AGE_MAX_ENFANTS))
            | u["nom"].fillna("").map(norm).str.contains(config.NOM_ENFANTS, regex=True))


def _simple(s) -> str:
    """Nom réduit pour les comparaisons, minuscules sans accents ni ponctuation, « st » écrit « saint »."""
    s = re.sub(r"[^a-z0-9]+", " ", norm(s or "")).strip()
    return re.sub(r"\bste?\b", lambda m: "sainte" if m.group(0) == "ste" else "saint", s)


SECTEUR = re.compile(r"\b(\d{2}|2a|2b|97[1-6])\s?([giz])\s?(\d{1,2})\b")


def code_secteur(*noms) -> str | None:
    """Code du secteur de psychiatrie cité dans un nom (« CMP Ados Neuilly 93G16 », « 31 I 01 »), écrit « 93G16 »,
    « 31I01 », « 13Z01 » (G psychiatrie générale, I infanto-juvénile, Z intersecteur), ou rien. Premier pas vers une
    carte de la sectorisation (version 2), qui demandera les arrêtés des ARS."""
    for n in noms:
        if isinstance(n, str) and n:
            m = SECTEUR.search(_simple(n))
            if m:
                return f"{m.group(1).upper()}{m.group(2).upper()}{int(m.group(3)):02d}"
    return None


# « Unité administrative », nom d'unité du ROR de neuf structures (trois CMPP de l'Aidaphi à Blois et Vendôme, audit
# du 30 octobre 2026), ne désigne aucun lieu de soins, le nom de la structure ou de FINESS le remplace
NOMS_VAGUES = (r"(accompagnements?|accompagnements? individuels?|consultations?|suivi|accueil|prise en charge|soins|"
               r"soins ambulatoires|ambulatoire|hospitalisation|unite|equipe)( .{0,12})?|tous types de deficiences.*|"
               r"unites? administratives?|services? administratifs?|administration|siege( social)?")
GENERIQUES = re.compile(r"\b(cmp|cattp|cattg|centre|medico|psychologique|consultations?|soins|ambulatoires?|"
                        r"adultes?|enfants?|adolescents?|psy|psychiatrie|et|de|des|du|la|le|les|d|l)\b")


def _distinctif(nom) -> str:
    """Mots d'un nom d'unité qui la distinguent des autres unités du même établissement."""
    return re.sub(r"\s+", " ", GENERIQUES.sub(" ", _simple(nom))).strip()


GENERIQUES_SAUF_PUBLIC = re.compile(r"\b(cmp|cattp|cattg|centre|medico|psychologique|consultations?|soins|"
                                    r"ambulatoires?|psy|psychiatrie|et|de|des|du|la|le|les|d|l)\b")


def _distinctif_public(nom) -> str:
    """Comme _distinctif, en gardant les mots qui disent le public (adultes, enfants, adolescents)."""
    return re.sub(r"\s+", " ", GENERIQUES_SAUF_PUBLIC.sub(" ", _simple(nom))).strip()


# Réécriture respectueuse des noms d'établissements (terme à remplacer, remplacement), appliquée dans l'ordre, sans
# tenir compte de la casse ni des accents
_DEFICIENCES = {"auditif": "auditive", "auditifs": "auditive", "visuel": "visuelle", "visuels": "visuelle",
                "intellectuel": "intellectuelle", "intellectuels": "intellectuelle", "moteur": "motrice",
                "moteurs": "motrice"}
# Terme employé comme nom (« IME polyhandicapés », « foyer pour handicapés »), précédé ou non d'une préposition
_PREP = r"\b((?:pour|aux|des|de|du)\s+(?:les\s+)?)?"
# Terme employé comme adjectif après un nom de personnes (« enfants handicapés »)
_PERS = r"\b(adultes?|enfants?|jeunes|travailleurs|adolescents?|personnes?|pers\.|pers)(?:\s+|(?<=\.))"


def _comme_nom(groupe):
    """Remplacement d'un terme employé comme nom par « personnes ... », la préposition d'origine gardée ou « pour »
    ajouté (« IME polyhandicapés » devient « IME pour personnes en situation de polyhandicap »)."""
    def f(m):
        prep = m.group(1)
        prep = prep if prep else "pour "
        if prep.strip().lower() in ("de", "du"):
            prep = "de "
        return prep + "personnes " + groupe
    return f


REECRITURES = [
    (_PERS + r"poly[\s-]?handicap[ée]e?s?\b", lambda m: _pers(m.group(1)) + " en situation de polyhandicap"),
    (_PERS + r"handicap[ée]e?s?\b", lambda m: _pers(m.group(1)) + " en situation de handicap"),
    (_PREP + r"poly[\s-]?handicap[ée]e?s?\b", _comme_nom("en situation de polyhandicap")),
    (_PREP + r"handicap[ée]e?s?\b", _comme_nom("en situation de handicap")),
    (_PREP + r"(?:pers(?:onnes?|\.)?\s+)?[âa]g[ée]e?s\s+d[ée]pendant(?:e|es|s)?\b", _comme_nom("âgées en perte d'autonomie")),
    (_PREP + r"alcooliques?\b", _comme_nom("ayant une addiction à l'alcool")),
    (_PREP + r"toxicomanes?\b", _comme_nom("ayant une addiction")),
    (r"\bd[ée]ficience\s+mentale\b", lambda m: "déficience intellectuelle"),
    (_PERS + r"d[ée]ficient(?:e|s|es)?\s+(auditifs?|visuels?|intellectuels?|moteurs?)\b",
     lambda m: _pers(m.group(1)) + " avec une déficience " + _DEFICIENCES[m.group(2).lower()]),
    (_PREP + r"d[ée]ficient(?:e|s|es)?\s+(auditifs?|visuels?|intellectuels?|moteurs?)\b",
     lambda m: _comme_nom("avec une déficience " + _DEFICIENCES[m.group(2).lower()])(m)),
    (_PERS + r"d[ée]ficient(?:e|s|es)?\b", lambda m: _pers(m.group(1)) + " avec une déficience"),
    (_PREP + r"d[ée]ficient(?:e|s|es)?\b", _comme_nom("avec une déficience")),
    (_PREP + r"malades?\s+mentaux\b", _comme_nom("vivant avec des troubles psychiques")),
    (r"\bmaladies?\s+mentales?\b", lambda m: "troubles psychiques"),
    (_PERS + r"inadapt[ée]e?s?\b", lambda m: _pers(m.group(1)) + " en difficulté"),
    (r"\binadapt[ée]e?s?\b", lambda m: "en difficulté"),
]


def _pers(mot):
    """« pers. » développé en « personnes »."""
    return "personnes" if mot.lower().startswith("pers") and not mot.lower().startswith("personne") else mot


def _casse(f):
    """Le remplacement prend la casse du texte d'origine (tout en capitales dans la plupart des raisons sociales)."""
    def g(m):
        s = f(m)
        return s.upper() if m.group(0).isupper() else s
    return g


def nom_respectueux(nom):
    """Nom d'établissement dont seuls les termes à proscrire sont remplacés, sigle et nom propre gardés."""
    if not isinstance(nom, str):
        return nom
    s = nom
    for motif, rempl in REECRITURES:
        s = re.sub(motif, _casse(rempl), s, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", s).strip()


# Termes retirés d'un nom quand il reste de quoi identifier le lieu (« IME Poly Handicapés Les Muscaris » devient
# « IME Les Muscaris »), avec la préposition et le nom de personnes qui les portent
_TERMES = (r"(?:poly[\s-]?handicap[ée]e?s?|handicap[ée]e?s?|[âa]g[ée]e?s\s+d[ée]pendant(?:e|es|s)?|alcooliques?|"
           r"toxicomanes?|d[ée]ficient(?:e|s|es)?(?:\s+(?:auditifs?|visuels?|intellectuels?|moteurs?))?|"
           r"malades?\s+mentaux|inadapt[ée]e?s?)\b")
_RETRAIT = re.compile(r"(?:\b(?:pour|aux|des|de|du)\s+(?:les\s+)?|\bd['’]\s*)?"
                      r"(?:\b(?:adultes?|enfants?|jeunes|travailleurs|adolescents?|personnes?|pers\.|pers)(?:\s+|(?<=\.)))?"
                      r"\b" + _TERMES, re.IGNORECASE)
# mots qui ne suffisent pas à identifier un lieu (sigles et noms communs des établissements)
_MOTS_COMMUNS = set("""ime mas fam eam eanm esat sessad samsah savs ehpad eehpad ehpa usld ssiad itep cmpp camsp foyer fv fh
    vie hebergement heb accueil jour nuit centre maison residence unite service etablissement institut medico social
    sociale educatif educative professionnel pour de des du la le les l d et a au aux en sur avec sans personnes
    personne adultes adulte enfants enfant travail aide soins domicile""".split())
# vocabulaire des nomenclatures (activité, mode d'accueil, public), qu'un morceau de nom du ROR ne fait que reprendre
_MOTS_NOMENCLATURE = _MOTS_COMMUNS | set("""accompagnement non medical medicalise medicalisee specialise specialisee
    complet internat externat semi temporaire permanent permanente ordinaire milieu ord prestation prestations tous type
    types deficiences deficience def deficients intellectuelle intellectuel intel psychisme psychique handicap handicaps
    troubles trouble tr autisme spectre polyhandicap alzheimer maladies maladie apparentees app cognitif specifique autre
    indic retard mental leger associes ass comportement comp diff auditive visuelle motrice sensorielle moteur cerebro
    lesion lesions traumatises cranien craniens pa ph dependantes dependants dependance agees age ages projets projet
    educatifs therapeutiques pedagogiques ouvert sequentiel accueils hebergements pers handic indication par
    vieillissantes vieillissants hospitalisation complete partielle hbgt hand ou heberg inter acc ah grave preparation
    profess professionnelle dans tsa di ret moyen profond severe temporaire protegee protege uvp uhr pasa""".split())
# sigles d'établissements gardés en tête d'un nom (« SAMSAH - Les Papillons blancs de Lille »)
_SIGLES = set("""ime mas fam eam eanm esat sessad samsah savs ehpad eehpad ehpa usld ssiad itep cmpp camsp eeap iem fv fh fo
    cajm saj mecs cmp cattp hdj csapa caarud ssr smr""".split())


def retirer_termes(nom):
    """Nom dont les termes à proscrire sont retirés, avec leur préposition."""
    if not isinstance(nom, str):
        return nom
    s = _RETRAIT.sub(" ", nom)
    s = re.sub(r"\s+", " ", s).strip(" -.,;:_")
    return re.sub(r"\s+(pour|aux|des|de|du|et|-)$", "", s, flags=re.IGNORECASE).strip()


def _sans_nom_propre(morceau) -> bool:
    """Vrai quand un morceau de nom ne contient que du vocabulaire de nomenclature, une fois les termes à proscrire
    retirés (« Hébergement pour personnes âgées dépendantes », « Tous Types de Déficiences Pers.Handicap. »)."""
    mots = [m for m in _simple(retirer_termes(morceau)).split() if len(m) > 1 and not m.isdigit()]
    return all(m in _MOTS_NOMENCLATURE for m in mots)


def _sigle(morceau) -> bool:
    """Vrai quand le morceau n'est qu'un sigle d'établissement (« SAMSAH », « S.A.V.S »)."""
    s = _simple(morceau).split()
    if s and all(len(m) == 1 for m in s):
        s = ["".join(s)]
    return len(s) == 1 and s[0] in _SIGLES


def nom_court(nom):
    """Nom du ROR débarrassé des morceaux qui ne font que décrire l'activité ou le public (séparés par un tiret entouré
    d'au moins une espace, des deux-points ou un tiret bas). Le sigle de tête est gardé s'il reste un nom propre.
    None quand aucun morceau ne porte de nom propre."""
    if not isinstance(nom, str):
        return nom
    morceaux = [m.strip(" .,;") for m in re.split(r"\s+[-–]\s*|\s*[-–]\s+|\s*:\s+|_", nom) if m.strip(" .,;")]
    propres = [i for i, m in enumerate(morceaux) if not _sans_nom_propre(m)]
    if not propres:
        return None
    if len(morceaux) < 2:
        return nom
    garder = set(propres) | ({0} if _sigle(morceaux[0]) else set())
    return " - ".join(m for i, m in enumerate(morceaux) if i in garder)


def nom_lisible(nom, secours=None):
    """Nom affiché d'une structure. D'abord le nom propre (morceaux descriptifs du ROR retirés), ou le nom de secours
    (structure de rattachement) quand le nom n'est qu'une description. Puis, s'il contient un terme à proscrire, ce
    terme est retiré quand il reste de quoi identifier le lieu, réécrit sinon (nom_respectueux).
    Renvoie (nom, traitement)."""
    from . import libelles
    if not isinstance(secours, str) or not secours.strip():
        secours = None
    court, traitement = nom_court(nom), "court"
    if court is None and secours:
        court, traitement = nom_court(secours) or secours, "rattachement"
    # un nom réduit à un sigle de public ou à du vocabulaire de nomenclature (« TSA », « Unité temporaire ») cède la
    # place au nom de la structure
    if court is not None and secours and (_sans_nom_propre(court) or len(_simple(court).replace(" ", "")) <= 4):
        court, traitement = nom_court(secours) or secours, "rattachement"
    if court is None:
        court, traitement = nom, ""
    if court == nom:
        traitement = ""
    if libelles.termes_proscrits(court):
        sans = retirer_termes(court)
        if not _sans_nom_propre(sans) and not libelles.termes_proscrits(sans):
            return sans, "retire"
        return nom_respectueux(court), "reecrit"
    return court, traitement


def _hopitaux(fin: pd.DataFrame) -> pd.Series:
    """Vrai pour un hôpital de FINESS, catégorie hospitalière et nom qui ne désigne pas une structure de consultation
    (FINESS enregistre des CMP sous la catégorie des centres hospitaliers spécialisés, « CMP CATTP Le Chemin vert » à
    Boulogne-sur-Mer)."""
    return fin["categetab"].isin(config.FINESS_HOPITAUX) & \
        ~fin["rs"].map(_simple).str.contains(r"\bcmp|\bc m p\b|\bcattp|\bcattg|medico psycho", regex=True)


# mot qui, placé juste avant un nom de commune dans le nom d'une unité, montre que ce nom n'y désigne pas une commune :
# un article (« ESAT la Fontaine », « Domaine du Château », « hors les murs »), un lieu-dit, un bâtiment ou une voie (« Palais Belvédère », « Cap Sizun », « Jardin fleuri »). Mesure nationale du
# 16 novembre 2026 (chantier des structures, constat C1, docs/structures/mesure_2026-11-16/)
# Pas de règle pour « saint » : la mise en forme des noms développe « ST » en « saint » (« PAV - ST Carpentras »,
# soins de transition, serait perdu), et la commune n'est cherchée que dans le département de l'unité (banc d'essai
# du 16 novembre 2026, outils/essai_lieux.py).
AVANT_NON_COMMUNE = {"le", "la", "les", "l", "cap", "pays", "palais", "domaine", "villa",
                     "residence", "parc", "jardin", "jardins", "hors", "rue", "avenue", "boulevard", "allee", "chemin",
                     "place", "quai", "impasse", "square", "jules"}
# « du », « des », « au », « aux » contiennent l'article : ils précèdent normalement une commune qui le porte (« site
# du Mée-sur-Seine », « CMP du Havre »), jamais une autre (« Domaine du Château »)
CONTRACTES = {"du", "des", "au", "aux"}


def _plus_longue(mots: list, dico: dict, d: str, doubles: set, sans_article: set | None = None) -> str | None:
    """Code de la commune nommée par la plus longue suite de mots (cinq au plus), ou rien. Une suite précédée d'un
    article, d'un lieu-dit ou d'une voie (AVANT_NON_COMMUNE) n'est pas lue comme commune ; précédée de
    « du », « des », « au » ou « aux », seulement si c'est le nom d'une commune qui porte l'article (sans_article)."""
    for k in range(min(5, len(mots)), 0, -1):
        for j in range(len(mots) - k + 1):
            g = " ".join(mots[j:j + k])
            if g not in dico or (d, g) in doubles:
                continue
            avant = mots[j - 1] if j > 0 else ""
            if avant in AVANT_NON_COMMUNE or (avant in CONTRACTES and (d, g) not in (sans_article or set())):
                continue
            return dico[g]
    return None


def departements_homonymes(ref) -> set:
    """Codes des communes qui portent le nom de leur département (Doubs, Corrèze, Mayenne, Paris)."""
    deps = getattr(ref, "deps", None)
    if deps is None or not len(deps):
        return set()
    noms = dict(zip(deps["code"], deps["nom"].map(_simple)))
    c = ref.communes
    return {k for k, n, d in zip(c["code"], c["nom"].map(_simple), c["dep"]) if noms.get(d) == n}


def sans_departement_homonyme(autres: pd.Series, propre: pd.Series, ref) -> pd.Series:
    """Communes lues dans le nom des unités (autres), sans celles qui portent le nom de leur département quand l'unité
    est enregistrée sous son propre établissement hors hôpital (propre, booléen par unité)."""
    if not len(autres):
        return autres
    p_ = propre.reindex(autres.index).fillna(False).astype(bool)
    return autres[~(autres.isin(departements_homonymes(ref)) & p_)]


# mots d'un nom qui annoncent un lieu de consultation détaché (« Relais Pays d'Arles », « site de Chanteheux »)
MOTS_SITE = r"\b(?:antenne|site|relais|unite|annexe|permanence)\b"
# type de voie en tête d'une adresse simplifiée (« route de macon », « r de caen »)
MOTS_VOIE = r"\b(?:rue|r|route|rte|avenue|av|chemin|che|boulevard|bd|impasse|imp|allee|all|place|pl|quai|cours|faubourg|fg)\b"


def sans_pays_ni_voie(autres: pd.Series, propre: pd.Series, noms: pd.Series, voies: pd.Series, ref) -> pd.Series:
    """Communes lues dans le nom des unités (autres), sans celles que le nom ne cite que comme pays (« CPTS du Pays de
    Gex », « Centre Ressources Autisme des Pays de la Loire » lu Loiré) ou que l'adresse de l'unité porte dans le nom de
    sa voie (« 412 route de Mâcon » à Hurigny, « 40 rue de Bétheny » à Reims), quand l'unité est enregistrée sous son
    propre établissement hors hôpital. Mesure du 31 octobre 2026 sur les 680 structures placées par leur nom hors de
    la commune de leur établissement FINESS : 17 concernées, l'adresse de FINESS juste pour toutes celles relues."""
    if not len(autres):
        return autres
    nom_com = ref.communes.set_index("code")["nom"]
    p_ = propre.reindex(autres.index).fillna(False).astype(bool)
    garde = []
    for i, code in autres.items():
        v = _simple(nom_com.get(code, ""))
        n = _simple(noms.get(i) if isinstance(noms.get(i), str) else "")
        a = _simple(voies.get(i) if isinstance(voies.get(i), str) else "")
        pays = bool(re.search(rf"\bpays (?:de |des |du |d )?(?:la |l |le )?{re.escape(v)}\b", n)) and not re.search(MOTS_SITE, n)
        voie = bool(re.search(rf"{MOTS_VOIE}.*\b{re.escape(v)}\b", a))
        garde.append(not (p_[i] and v and (pays or voie)))
    return autres[garde]


def communes_du_nom(noms: pd.Series, deps: pd.Series, ref, exclure: pd.Series | None = None) -> pd.Series:
    """Commune citée dans le nom d'une unité (« CMP Munster - Psy adulte »), cherchée parmi les communes du
    département de son établissement de rattachement. La plus longue suite de mots qui est le nom d'une seule commune
    du département l'emporte. La commune citée avant le nom de l'hôpital gestionnaire (« CMP ADULTES CARVIN CH HENIN
    BEAUMONT ») passe d'abord. Une commune trouvée seulement dans le nom de l'hôpital n'est pas retenue quand elle
    figure dans exclure (ensemble de codes par unité, les communes des hôpitaux de son gestionnaire), le nom ne fait
    alors que citer le gestionnaire. Renvoie le code de la commune, ou rien."""
    c = ref.communes.assign(s=ref.communes["nom"].map(_simple))
    n = c.groupby(["dep", "s"])["code"].transform("size")
    index, sans_article = {}, set()
    for d, s, code in zip(c["dep"], c["s"], c["code"]):
        if s and s not in config.MOTS_NON_COMMUNES and len(s) >= 3:
            index.setdefault(d, {})[s] = code
            # nom cité sans son article (« CMPEA Isle-sur-la-Sorgue » pour L'Isle-sur-la-Sorgue, constat du
            # 13 octobre 2026), seulement s'il reste au moins deux mots
            sans = re.sub(r"^(?:l|le|la|les) ", "", s)
            if sans != s and len(sans.split()) >= 2:
                index[d].setdefault(sans, code)
                sans_article.add((d, sans))
    doubles = set(zip(c.loc[n > 1, "dep"], c.loc[n > 1, "s"]))
    out = {}
    for i, n_, d in zip(noms.index, noms, deps):
        interdites = exclure.get(i) if exclure is not None else None
        interdites = interdites if isinstance(interdites, set) else set()
        dico = index.get(d)
        if not dico or not isinstance(n_, str):
            continue
        # la commune citée avant le nom de l'hôpital gestionnaire l'emporte (« CMP ADULTES CARVIN CH HENIN BEAUMONT »),
        # sinon le nom entier est lu (« Biologie délocalisée CH Pont-à-Mousson » désigne bien Pont-à-Mousson)
        complet = _simple(n_)
        avant = re.sub(config.NOM_ETABLISSEMENT_GESTIONNAIRE, "", complet)
        trouve = _plus_longue(avant.split(), dico, d, doubles, sans_article) if avant != complet else None
        if trouve is None:
            trouve = _plus_longue(complet.split(), dico, d, doubles, sans_article)
            # la commune trouvée seulement dans le nom de l'hôpital, si elle est exclue, n'est pas remplacée par une
            # plus courte (« Mousson » dans « Pont-à-Mousson »)
            if avant != complet and trouve in interdites:
                trouve = None
        if trouve:
            out[i] = trouve
    return pd.Series(out, dtype=object)


def classer_unites(u: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par unité et par type qui lui correspond (une unité peut relever de plusieurs types, par exemple
    « CMP, tous publics » et « CMP pour enfants »)."""
    nom = u["nom"].fillna("").map(norm)
    enf = _enfants(u)
    out = []
    for tid, _lab, _fam, _g, r in config.LIEUX_TYPES:
        if not r.get("cats"):
            continue
        cats = {c for c in r["cats"] if c is not None}
        m = u["categorie"].isin(cats)
        if None in r["cats"]:
            m |= u["categorie"].isna()
        if r.get("champs"):
            m &= u["champ"].isin(r["champs"])
        if r.get("modes"):
            m &= u["mode"].isin(r["modes"])
        if r.get("modes_seuls"):
            m |= u["mode"].isin(r["modes_seuls"]) & u["champ"].isin(r.get("champs_seuls") or set(u["champ"].dropna()))
        if r.get("maternite") and "type_maternite" in u:
            mt = r["maternite"]
            m |= u["type_maternite"].notna() & (u["categorie"].isin(mt["cats"]) | nom.str.contains(mt["nom"], regex=True))
        if r.get("noms_sans_categorie"):
            m |= (u["categorie"].isna() & u["champ"].isin(r.get("champs") or set(u["champ"].dropna()))
                  & u["mode"].isin(r.get("modes") or set(u["mode"].dropna()))
                  & nom.str.contains(r["noms_sans_categorie"], regex=True))
        if r.get("noms_categories"):
            # unités d'autres catégories que leur nom range dans ce type (consultations non sectorisées du ROR)
            cs, motif = r["noms_categories"]
            m |= (u["categorie"].isin(cs) & u["champ"].isin(r.get("champs") or set(u["champ"].dropna()))
                  & u["mode"].isin(r.get("modes") or set(u["mode"].dropna())) & nom.str.contains(motif, regex=True))
        if r.get("public") == "enfants":
            m &= enf
        elif r.get("public") == "adultes":
            m &= ~enf
        if r.get("hors"):
            m &= ~nom.str.contains(r["hors"], regex=True)
        if m.any():
            out.append(pd.DataFrame({"cle": u.loc[m, "cle"].to_numpy(), "type": tid}))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["cle", "type"])


def _unites_retenues(ror: dict, ref, fin: pd.DataFrame | None = None) -> pd.DataFrame:
    """Unités élémentaires de soins, hors consultations de ville, avec leur commune actuelle, leur structure de
    rattachement et le numéro FINESS de celle-ci."""
    u = ror["unites"]
    s = ror["structures"].set_index("cle")
    u = u[(u["niveau_organisation"].fillna("4") == "4") & (u["champ"] != config.ROR_CHAMP_VILLE)].copy()
    # première structure de rattachement qui porte un numéro FINESS, sinon la première
    def struct(liste):
        cles = [c for c in (liste or "").split("|") if c]
        for c in cles:
            if c in s.index and pd.notna(s.at[c, "finess"]):
                return c
        return cles[0] if cles else None
    u["structure"] = u["structures"].map(struct)
    u["finess_ror"] = u["structure"].map(s["finess"])
    u["structure_nom"] = u["structure"].map(s["nom"])
    actuels = set(ref.communes["code"])

    def actuelle(c):
        return c.where(c.isin(actuels), c.map(ref.anciens))
    # beaucoup d'unités de psychiatrie n'ont pas de commune propre (41 % le 12 octobre 2026). Leur commune est déduite
    # du nom de l'unité quand il cite une commune du département, sinon c'est celle de l'établissement de
    # rattachement, et l'unité garde alors son identité propre (elle n'est pas fusionnée avec l'hôpital)
    u["commune"] = actuelle(u["commune"])
    u["origine_commune"] = np.where(u["commune"].notna(), "unite", None)
    com_struct = actuelle(u["structure"].map(s["commune"]))
    dep_struct = com_struct.map(ref.communes.set_index("code")["dep"])
    # un bloc ou une salle d'un service (« Bloc obstétrical - Salles de césarienne ») n'est jamais déplacé par son nom :
    # dix blocs de maternité de Gironde, du Lot-et-Garonne et du Tarn étaient placés à Salles (constat C1 du 16 novembre
    # 2026)
    # reconnue par son nom seulement : un hôpital à plusieurs sites nomme ses urgences par la ville du site (« S.A.U
    # NOYON », « Urgences - CH Ste-Foy-la-Grande »), une catégorie ne suffit pas (banc d'essai du 16 novembre 2026)
    interne = u["nom"].fillna("").map(norm).str.contains(config.NOM_UNITE_INTERNE, regex=True)
    sans = u["commune"].isna() & dep_struct.notna() & ~interne
    deduites = communes_du_nom(u.loc[sans, "nom"], dep_struct[sans], ref)
    u.loc[deduites.index, "commune"] = deduites
    u.loc[deduites.index, "origine_commune"] = "nom"
    # une unité déclarée à l'adresse de son établissement, mais dont le nom cite une autre commune du département
    # (« CMP Munster » déclaré à l'hôpital de Rouffach), est placée dans la commune de son nom
    # Un nom qui ne cite que son hôpital gestionnaire ne déplace pas l'unité (« CMP 59G30 CONDE/ESCAU CH VALENCIENNES »
    # reste à Condé-sur-l'Escaut, constat du 15 octobre 2026), d'où les communes des hôpitaux du gestionnaire exclues
    copie = (u["origine_commune"] == "unite") & (u["commune"] == com_struct) & dep_struct.notna() & ~interne
    exclure = None
    if fin is not None:
        est_hop = _hopitaux(fin)
        villes = fin[est_hop].groupby("nofinessej")["com"].agg(set)
        fi = fin.set_index("nofinesset").assign(hopital=est_hop.to_numpy())
        # seulement pour une unité rattachée à son propre établissement (un CMP enregistré sous son numéro). Rattachée
        # à un hôpital, son nom peut désigner l'hôpital local où elle se trouve (« Urgences - CH Ste-Foy-la-Grande »)
        propre = ~u.loc[copie, "finess_ror"].map(fi["hopital"]).fillna(False).astype(bool)
        exclure = u.loc[copie, "finess_ror"].map(fi["nofinessej"]).map(villes).where(propre)
    autres = communes_du_nom(u.loc[copie, "nom"], dep_struct[copie], ref, exclure)
    autres = autres[autres != u.loc[autres.index, "commune"]]
    # une commune qui porte le nom de son département (Doubs, Corrèze, Mayenne) n'est pas lue dans le nom d'une unité
    # enregistrée sous son propre établissement, hors hôpital, dont FINESS donne déjà la commune : le nom y cite le
    # département (« CAMSP DOUBS » de Besançon, « HAUT DOUBS SESSAD VALDAHON », cinq structures placées à Doubs
    # jusqu'au 31 octobre 2026). Rattachée à un hôpital, l'unité peut porter le nom de la ville (« CeGIDD - Antenne
    # Mayenne » du CH de Laval).
    if fin is not None:
        autres = sans_departement_homonyme(autres, propre, ref)
        autres = sans_pays_ni_voie(autres, propre, u["nom"], u["voie"], ref)
    u.loc[autres.index, "commune"] = autres
    u.loc[autres.index, "origine_commune"] = "nom"
    reste = u["commune"].isna()
    u.loc[reste, "commune"] = com_struct[reste]
    u.loc[reste & u["commune"].notna(), "origine_commune"] = "structure"
    # adresse, celle de l'unité, celle de l'établissement quand l'unité y est placée faute de mieux, aucune quand la
    # commune vient du nom (on ne connaît alors que la commune)
    u["voie"] = np.where(u["origine_commune"] == "unite", u["voie"],
                         np.where(u["origine_commune"] == "structure", u["structure"].map(s["voie"]), None))
    JOURNAL.controle("ROR, commune des unités retenues",
                     ", ".join(f"{k} {v:.0%}".replace(".", ",") for k, v in
                               u["origine_commune"].map({"unite": "propre", "nom": "déduite du nom de l'unité",
                                                         "structure": "celle de l'établissement de rattachement"})
                               .value_counts(normalize=True).items()))
    return u


def _lieux_ror(u: pd.DataFrame, classes: pd.DataFrame, fin: pd.DataFrame) -> pd.DataFrame:
    """Lieux tirés du ROR, une ligne par type et par structure. Clé, numéro FINESS d'établissement et commune quand la
    structure de rattachement est un établissement de FINESS, sinon la structure du ROR et la commune."""
    x = classes.merge(u, on="cle", how="left")
    x = x[x["commune"].notna()]
    eg = set(fin["nofinesset"])
    ej_de = fin.set_index("nofinesset")["nofinessej"]
    est_eg = x["finess_ror"].isin(eg)
    est_ej = ~est_eg & x["finess_ror"].isin(set(fin["nofinessej"]))
    # Une unité rattachée dans le ROR à un établissement de FINESS qui n'est pas un hôpital (un CMP enregistré sous son
    # propre numéro), mais déclarée dans la commune d'un hôpital de son gestionnaire alors que FINESS place ce numéro
    # dans une autre commune, prend la commune et l'adresse de FINESS. Le ROR a repris la commune du siège (constat du
    # 15 octobre 2026, CMP de Carvin et de Harnes comptés à Hénin-Beaumont, antennes de Cruseilles, Faverges et Thônes
    # comptées à Annecy, confirmé par l'annuaire des CMP des Hauts-de-France de la F2RSM Psy). Quand le ROR place
    # l'unité dans une commune sans hôpital du gestionnaire, il garde la main (il décrit le lieu où l'on reçoit).
    fi = fin.set_index("nofinesset")
    est_hop = _hopitaux(fin)
    hop = fin[est_hop].groupby("nofinessej")["com"].agg(set)
    fi = fi.assign(hopital=est_hop.to_numpy())
    com_f = x["finess_ror"].map(fi["com"])
    villes = x["finess_ror"].map(fi["nofinessej"]).map(hop)
    siege = pd.Series([isinstance(v, set) and c in v and cf not in v for c, cf, v in zip(x["commune"], com_f, villes)],
                      index=x.index)
    corr = est_eg & ~x["finess_ror"].map(fi["hopital"]).fillna(False).astype(bool) & com_f.notna() \
        & (com_f != x["commune"]) & siege
    x.loc[corr, "commune"] = com_f[corr]
    x.loc[corr, "voie"] = x.loc[corr, "finess_ror"].map(fi["adresse"])
    x.loc[corr, "origine_commune"] = "unite"
    x.loc[corr, ["lat", "lon"]] = np.nan
    JOURNAL.controle("ROR, unités déclarées dans la commune d'un hôpital de leur gestionnaire, placées à la commune "
                     "de leur numéro FINESS", entier_fr(int(corr.sum())))
    x["finess"] = x["finess_ror"].where(est_eg)
    x["ej"] = np.where(est_eg, x["finess_ror"].map(ej_de), np.where(est_ej, x["finess_ror"], None))
    x["lieu"] = np.where(est_eg, "F" + x["finess_ror"].fillna(""), "R" + x["structure"].fillna(x["cle"])) + "|" + x["commune"]
    # Un lieu est un endroit. Les unités d'un même établissement dans une même commune ne forment un seul lieu que si
    # elles ont la même adresse (consultations adultes et soins ambulatoires d'un même CMP). À des adresses
    # différentes, ce sont des lieux différents (plusieurs CMP d'un hôpital dans une grande ville, constat du
    # 12 octobre 2026 à Cayenne). Une unité sans adresse propre, placée dans la commune de son établissement faute de
    # mieux ou dans la commune citée par son nom, garde son identité par les mots distinctifs de son nom.
    # La règle ne vaut que pour une unité rattachée à un établissement d'une autre catégorie que celle du type (un CMP
    # rattaché à son hôpital) ou sans numéro FINESS. Rattachée à un établissement de sa catégorie (un EHPAD, un CMP
    # enregistré comme tel), le numéro FINESS désigne déjà le lieu.
    propres = _categories_propres()
    cat = x["finess_ror"].map(fin.set_index("nofinesset")["categetab"])
    a_part = pd.Series([ty in propres and c not in propres[ty] for ty, c in zip(x["type"], cat)], index=x.index) | ~est_eg
    # rue sans le numéro, le ROR déclare parfois la même unité avec et sans numéro (« 5 rue de Koenigshoffen » et
    # « rue de Koenigshoffen », CMP de Strasbourg compté deux fois jusqu'au 13 octobre 2026)
    adr = (x["voie"].map(_simple).str.replace(r"^\d+\s*(?:bis|ter|b|t)?\s+", "", regex=True)
           .where(x["origine_commune"] == "unite", "").fillna(""))
    suffixe = np.where(adr.str.len() > 0, "|a:" + adr, "|n:" + x["nom"].map(_distinctif))
    x["lieu"] = x["lieu"] + np.where(a_part, suffixe, "")
    # pour les CMP, un lieu pour adultes et un lieu pour enfants d'un même hôpital dans une même commune restent deux
    # lieux (FINESS les enregistre séparément, constat du 12 octobre 2026 dans le Tarn)
    famille_publics = {t[0] for t in config.LIEUX_TYPES if t[4].get("parent")} | \
        {t[4]["parent"] for t in config.LIEUX_TYPES if t[4].get("parent")}
    pub = x["type"].isin(famille_publics).to_numpy()
    x.loc[pub, "lieu"] = x.loc[pub, "lieu"] + np.where(_enfants(x.loc[pub]), "|E", "|A")
    agg = (x.groupby(["type", "lieu"], as_index=False)
           .agg(nom=("nom", "first"), structure_nom=("structure_nom", "first"), finess=("finess", "first"),
                ej=("ej", "first"), commune=("commune", "first"), voie=("voie", "first"),
                lat_ror=("lat", "first"), lon_ror=("lon", "first"), categories_ror=("categorie", lambda s: ",".join(sorted({c for c in s if pd.notna(c)}))),
                age_min=("age_min", "min"), age_max=("age_max", "max"), lits=("lits", "sum"),
                unites_ror=("cle", "nunique"), maj_ror=("maj", "max"),
                noms_unites=("nom", lambda s: " | ".join(sorted({n for n in s if isinstance(n, str)}))),
                origine_commune=("origine_commune", "first")))
    agg["dans_ror"] = True
    return agg


def _categories_propres() -> dict:
    """Catégories FINESS propres à chaque type (celles du type, ou de son parent pour les CMP adultes et enfants)."""
    out = {}
    for tid, _l, _f, _g, r in config.LIEUX_TYPES:
        cats = r.get("finess") or next((x[4].get("finess") for x in config.LIEUX_TYPES if x[0] == r.get("parent")), None)
        if cats:
            out[tid] = set(cats)
    return out


def _lieux_finess(fin: pd.DataFrame, ref) -> pd.DataFrame:
    """Établissements actifs de FINESS dont la catégorie correspond à un type, une ligne par type."""
    f = fin[fin["actif"]].copy()
    actuels = set(ref.communes["code"])
    f["com"] = f["com"].where(f["com"].isin(actuels), f["com"].map(ref.anciens))
    out = []
    for tid, _lab, _fam, _g, r in config.LIEUX_TYPES:
        if r.get("finess"):
            g = f[f["categetab"].isin(r["finess"]) & f["com"].notna()]
            if tid == "lieu_cattp":
                # catégorie 366 de FINESS, « atelier thérapeutique » : pas un CATTP, sauf si son nom le dit (relecture
                # des structures laissées de côté, 18 novembre 2026, neuf ateliers parmi 62 inscriptions)
                atelier = (g["categetab"] == config.FINESS_ATELIER_THERAPEUTIQUE) & ~g["rs"].fillna("").map(norm).str.contains(
                    r"catt[pg]|temps partiel|accueil therapeutique", regex=True)
                if atelier.any():
                    JOURNAL.controle("FINESS, ateliers thérapeutiques (catégorie 366) non comptés comme CATTP",
                                     f"{int(atelier.sum())} établissements ouverts")
                g = g[~atelier]
            out.append(pd.DataFrame({"type": tid, "lieu": "F" + g["nofinesset"] + "|" + g["com"], "finess": g["nofinesset"],
                                     "ej": g["nofinessej"], "commune": g["com"], "nom_finess": g["rs"],
                                     "categorie_finess": g["categetab"]}))
    # CMP enregistrés dans FINESS sous une autre catégorie, reconnus par leur nom
    nm = f["rs"].fillna("").map(norm)
    g = f[f["categetab"].isin(config.FINESS_CMP_PAR_NOM) & f["com"].notna()
          & nm.str.contains(config.NOM_CMP, regex=True)
          & ~nm.str.contains(config.LIEUX_EXCLUS_CMP + r"|vaccination", regex=True)]
    if len(g):
        out.append(pd.DataFrame({"type": "lieu_cmp", "lieu": "F" + g["nofinesset"] + "|" + g["com"], "finess": g["nofinesset"],
                                 "ej": g["nofinessej"], "commune": g["com"], "nom_finess": g["rs"],
                                 "categorie_finess": g["categetab"]}))
        _releve("FINESS", "Établissements dont le nom dit CMP, enregistrés sous une autre catégorie (hôpital, "
                "établissement de santé mentale, CATTP, centre de santé)", len(g), "Comptés comme CMP")
        JOURNAL.controle("FINESS, CMP enregistrés sous une autre catégorie et reconnus par leur nom",
                         f"{len(g)} établissements ouverts, " + ", ".join(
                             f"catégorie {k} {v}" for k, v in g["categetab"].value_counts().items()))
    if not out:
        return pd.DataFrame()
    lf = pd.concat(out, ignore_index=True)
    # un établissement enregistré comme CMP dont le nom dit autre chose est rangé dans le type que son nom désigne
    n = lf["nom_finess"].fillna("").map(norm)
    cmp_ = lf["type"] == "lieu_cmp"
    nouveau = pd.Series(None, index=lf.index, dtype=object)
    a_cmp = n.str.contains(config.NOM_CMP, regex=True)
    for motif, tid in config.RETYPAGE_CMP_FINESS:
        m = cmp_ & nouveau.isna() & n.str.contains(motif, regex=True)
        if tid == "hdj":
            # un hôpital de jour enregistré comme CMP, sauf s'il porte aussi un CMP (« Hôpital de jour CMP »)
            m &= ~a_cmp
            enf = n.str.contains(config.NOM_ENFANTS, regex=True)
            nouveau[m & enf] = "lieu_hdj_psy_enfants"
            nouveau[m & ~enf] = "lieu_hdj_psy_adultes"
            continue
        nouveau[m] = tid
    m = cmp_ & nouveau.isna() & n.str.contains(config.RETYPAGE_CATTP, regex=True) & \
        ~n.str.contains(config.NOM_CMP, regex=True)
    nouveau[m] = "lieu_cattp"
    if nouveau.notna().any():
        lf.loc[nouveau.notna(), "type"] = nouveau[nouveau.notna()]
        lib = {t[0]: t[1] for t in config.LIEUX_TYPES}
        _releve("FINESS", "Établissements enregistrés comme CMP dont le nom désigne autre chose (équipe mobile, CATTP, "
                "liaison, milieu pénitentiaire, CSAPA, hôpital de jour)", int(nouveau.notna().sum()),
                "Rangés dans le type que désigne leur nom, " + ", ".join(
                    f"{_court(lib[k], k)} {v}" for k, v in nouveau.value_counts().items()))
        JOURNAL.controle("FINESS, établissements enregistrés comme CMP rangés dans le type que désigne leur nom",
                         f"{int(nouveau.notna().sum())} sur {int(cmp_.sum())}, " + ", ".join(
                             f"{_court(lib[k], k)} {v}" for k, v in nouveau.value_counts().items()))
    return lf


def _suivre_parents(x: pd.DataFrame, remplace: dict) -> pd.DataFrame:
    """Quand un CMP « tous publics » est réuni à un autre lieu, ses lignes « CMP pour adultes » et « CMP pour enfants »
    prennent la clé du lieu gardé (sinon un CMP pour enfants resterait sans CMP tous publics, constat du 13 octobre
    2026, CMP de l'Ariane à Nice, un CMP de Doullens et un CMP de Seine-et-Marne)."""
    if not remplace:
        return x
    enfants_de = {t_[0]: t_[4]["parent"] for t_ in config.LIEUX_TYPES if t_[4].get("parent")}
    x = x.assign(_suivi=False)
    for enf, par in enfants_de.items():
        rp = {anc: nv for (ty, anc), nv in remplace.items() if ty == par}
        m = (x["type"] == enf) & x["lieu"].isin(rp)
        if not m.any():
            continue
        x.loc[m, "lieu"] = x.loc[m, "lieu"].map(rp)
        x.loc[m, "_suivi"] = True
        # la ligne reprend le nom et l'emplacement du lieu gardé, pour que les listes par public nomment la même structure
        parent = x[x["type"] == par].drop_duplicates("lieu").set_index("lieu")
        for col in ("nom", "nom_affiche", "nom_finess", "adresse", "voie", "lat", "lon", "precision", "finess", "commune"):
            if col in x and col in parent:
                v = x.loc[m, "lieu"].map(parent[col])
                x.loc[m, col] = v.where(v.notna(), x.loc[m, col])
    # la ligne propre au lieu gardé passe avant celle qui le rejoint
    x = x.sort_values("_suivi", kind="stable").drop_duplicates(["type", "lieu"]).drop(columns="_suivi")
    return x.sort_index()


def _court(libelle: str, tid: str) -> str:
    """Libellé court d'un type pour une énumération (« Hôpitaux de jour en psychiatrie (adultes) »)."""
    tete, _, reste = libelle.partition(", ")
    if tete.count("(") != tete.count(")"):
        return libelle   # virgule dans une parenthèse (« (PASS, LHSS...) »), le libellé reste entier
    # le public reste quand un autre type porte la même tête de libellé (hôpitaux de jour, hospitalisation complète en
    # psychiatrie : relecture du 17 novembre 2026, un même libellé pour les adultes et pour les enfants)
    tetes = [x[1].partition(", ")[0] for x in config.LIEUX_TYPES]
    return f"{tete} ({reste})" if reste and tetes.count(tete) > 1 else tete


def reunir(lr: pd.DataFrame, lf: pd.DataFrame, fin_cat: pd.Series | None = None) -> tuple[pd.DataFrame, dict]:
    """Réunion sans double compte. Même clé, une seule structure « FINESS et ROR ». Un établissement de FINESS absent du ROR
    sous son numéro est rattaché à une structure du ROR du même type, de la même entité juridique et de la même commune
    s'il en existe un (le lieu devient « FINESS et ROR »), sinon il est ajouté comme « FINESS seul »."""
    stats = {}
    if lf.empty:
        lr = lr.assign(provenance="ror")
        return lr, {"rapproches_meme_numero": 0, "rapproches_entite_juridique": 0, "finess_seul": 0}
    m = lr.merge(lf[["type", "lieu", "nom_finess", "categorie_finess"]], on=["type", "lieu"], how="left", indicator=True)
    m["provenance"] = np.where(m["_merge"] == "both", "les_deux", "ror")
    m["finess_rapproche"] = None
    m = m.drop(columns="_merge")
    stats["rapproches_meme_numero"] = int((m["provenance"] == "les_deux").sum())
    reste = lf[~lf.set_index(["type", "lieu"]).index.isin(lr.set_index(["type", "lieu"]).index)]
    # même numéro FINESS dans une autre commune (le ROR place l'unité là où elle reçoit, FINESS parfois au siège), un
    # seul lieu, celui du ROR (constat du 12 octobre 2026, CMPP de Martinique)
    par_num = m[m["finess"].notna()].drop_duplicates(["type", "finess"]).set_index(["type", "finess"])["lieu"]
    k = pd.MultiIndex.from_frame(reste[["type", "finess"]])
    meme = np.asarray(k.isin(par_num.index))
    vises = pd.MultiIndex.from_arrays([k[meme].get_level_values(0), par_num.reindex(k[meme]).to_numpy()])
    m.loc[np.asarray(m.set_index(["type", "lieu"]).index.isin(vises)), "provenance"] = "les_deux"
    stats["rapproches_meme_numero_autre_commune"] = int(meme.sum())
    reste = reste[~meme]
    # rapprochement par entité juridique et commune, un établissement de FINESS pour un lieu du ROR, appariés un à un
    # dans l'ordre (deux CMP de FINESS et deux structures du ROR d'un même hôpital dans une même commune font deux paires)
    cles = ["type", "ej", "commune"]
    cand = m[m["ej"].notna() & (m["provenance"] == "ror")].sort_values("lieu")
    cand = cand.assign(_k=cand.groupby(cles).cumcount())
    reste = reste.sort_values("lieu")
    reste = reste.assign(_k=reste.groupby(cles).cumcount())
    r2 = reste.merge(cand[cles + ["_k", "lieu"]].rename(columns={"lieu": "lieu_ror"}), on=cles + ["_k"],
                     how="left").drop(columns="_k")
    lie = r2[r2["lieu_ror"].notna()]
    stats["rapproches_entite_juridique"] = len(lie)
    cle = m.set_index(["type", "lieu"]).index
    idx = pd.MultiIndex.from_frame(lie[["type", "lieu_ror"]])
    sel = cle.isin(idx)
    m.loc[sel, "provenance"] = "les_deux"
    infos = lie.set_index(["type", "lieu_ror"])
    m.loc[sel, "nom_finess"] = [infos.at[k, "nom_finess"] for k in cle[sel]]
    m.loc[sel, "finess_rapproche"] = [infos.at[k, "finess"] for k in cle[sel]]
    seul = r2[r2["lieu_ror"].isna()].drop(columns="lieu_ror")
    stats["finess_seul"] = len(seul)
    seul = seul.assign(provenance="finess", dans_ror=False)
    out = pd.concat([m, seul], ignore_index=True)
    # même type, même commune et même nom, l'un sans numéro FINESS (structure du ROR non rattachée à FINESS),
    # l'autre avec, une seule structure (constat du 12 octobre 2026, « CMP de l'Ariane » à Nice)
    nom = out["nom"].fillna(out["nom_finess"]).map(_simple)
    autre = out["nom_finess"].fillna(out.get("structure_nom")).map(_simple)
    sans_num = out["lieu"].str.startswith("R")
    cles_num = set(zip(out.loc[~sans_num, "type"], out.loc[~sans_num, "commune"], nom[~sans_num])) | \
        set(zip(out.loc[~sans_num, "type"], out.loc[~sans_num, "commune"], autre[~sans_num]))
    # un nom générique (porté par au moins dix lieux en France) ne prouve rien, et une unité qui porte déjà un
    # établissement de FINESS rapproché n'est jamais retirée (constat du 12 octobre 2026, une résidence autonomie)
    generique = nom.map(nom.value_counts()) >= 10
    porte = out["finess_rapproche"].notna()
    double = sans_num & ~generique & ~porte & pd.Series([k in cles_num for k in zip(out["type"], out["commune"], nom)],
                                                       index=out.index)
    vises = set(zip(out.loc[double, "type"], out.loc[double, "commune"], nom[double]))
    cible = ~sans_num & pd.Series([(a, b, c) in vises or (a, b, d) in vises for a, b, c, d in
                                   zip(out["type"], out["commune"], nom, autre)], index=out.index)
    out.loc[cible & (out["provenance"] == "finess"), "provenance"] = "les_deux"
    stats["rapproches_nom"] = int(double.sum())
    # lieu gardé de chaque lieu retiré, pour que les CMP pour adultes et pour enfants suivent leur CMP « tous publics »
    remplace = {}
    garde_nom = {}
    for j in out.index[cible]:
        for cle_ in ((out.at[j, "type"], out.at[j, "commune"], nom[j]), (out.at[j, "type"], out.at[j, "commune"], autre[j])):
            garde_nom.setdefault(cle_, out.at[j, "lieu"])
    for i in out.index[double]:
        g_ = garde_nom.get((out.at[i, "type"], out.at[i, "commune"], nom[i]))
        if g_ is not None:
            remplace[(out.at[i, "type"], out.at[i, "lieu"])] = g_
    out = out[~double]
    # Même CMP déclaré deux fois, une fois sous l'hôpital de rattachement (ou une structure sans numéro) et une fois sous
    # son propre numéro FINESS (« CMP Bully les Mines » et « CMP de Bully-les-Mines », constat du 12 octobre 2026).
    # Dans un même type et une même commune, une unité du ROR rattachée à un établissement qui n'est pas de la
    # catégorie du type, dont le nom a les mêmes mots distinctifs (adultes et enfants compris) qu'un lieu enregistré
    # sous sa propre catégorie, est réunie à ce lieu. Deux établissements de la bonne catégorie ne sont jamais réunis.
    cat_num = (fin_cat if fin_cat is not None else pd.Series(dtype=object))
    propres = _categories_propres()
    num = out["lieu"].str.extract(r"^F(\d{8}[0-9AB]|\d{9})\|")[0]
    cat = num.map(cat_num)
    propre = pd.Series([c in propres.get(ty, set()) for ty, c in zip(out["type"], cat)], index=out.index)
    dd = out["nom"].fillna(out["nom_finess"]).map(_distinctif_public)
    a_tester = out["type"].isin(propres) & (dd.str.len() >= 3) & (dd.map(dd.value_counts()) < 10)
    cles_propres = set(zip(out.loc[a_tester & propre, "type"], out.loc[a_tester & propre, "commune"], dd[a_tester & propre]))
    # une unité qui porte déjà un CMP de FINESS rapproché par l'entité juridique n'est jamais réunie à un autre lieu,
    # sinon ce CMP disparaîtrait (constat du contrôle indépendant du 12 octobre 2026, un CMP de Nice)
    porte_finess = out["finess_rapproche"].notna() if "finess_rapproche" in out else False
    retirer = out.index[a_tester & ~propre & (out["provenance"] != "finess") & ~porte_finess
                        & pd.Series([k in cles_propres for k in zip(out["type"], out["commune"], dd)], index=out.index)]
    vises = set(zip(out.loc[retirer, "type"], out.loc[retirer, "commune"], dd[retirer]))
    gardes = out.index[a_tester & propre & pd.Series([k in vises for k in zip(out["type"], out["commune"], dd)],
                                                     index=out.index)]
    out.loc[gardes, "provenance"] = "les_deux"
    # les numéros FINESS des lieux absorbés restent attachés au lieu gardé, pour la traçabilité et le contrôle
    # « aucun établissement perdu » (doublon de FINESS sous deux entités juridiques, CMP de Bully-les-Mines)
    if "finess_absorbes" not in out:
        out["finess_absorbes"] = None
    cle_garde = {k: i for k, i in zip(zip(out.loc[gardes, "type"], out.loc[gardes, "commune"], dd[gardes]), gardes)}
    for i in retirer:
        g = cle_garde.get((out.at[i, "type"], out.at[i, "commune"], dd[i]))
        nums = {str(v) for v in (out.at[i, "finess"], out.at[i, "finess_rapproche"] if "finess_rapproche" in out else None,
                                 out.at[i, "finess_absorbes"]) if isinstance(v, str) and v}
        if g is not None:
            remplace[(out.at[i, "type"], out.at[i, "lieu"])] = out.at[g, "lieu"]
        if g is not None and nums:
            deja = out.at[g, "finess_absorbes"]
            out.at[g, "finess_absorbes"] = ",".join(sorted(set((deja.split(",") if isinstance(deja, str) else []) + list(nums))))
    stats["rapproches_nom_distinctif"] = len(retirer)
    out = out.drop(index=retirer)
    out = _suivre_parents(out, remplace)
    dup = int(out.duplicated(["type", "lieu"]).sum())
    if dup:
        raise ValueError(f"{dup} lieux en double après la réunion de FINESS et du ROR")
    return out, stats


_ARRONDISSEMENTS: dict | None = None


def arrondissements() -> dict:
    """Arrondissements municipaux de Paris, Lyon et Marseille et le code de leur commune (75115 vers 75056), d'après le
    référentiel d'Etalab. FINESS et la Base Adresse Nationale situent une adresse dans son arrondissement, le projet
    compte par commune : sans cette table, les coordonnées de FINESS et le géocodage de ces trois villes étaient écartés
    comme « hors de la commune » et leurs 2 300 structures posées au centre de la commune (constat du 29 octobre
    2026, toutes les structures de Paris)."""
    global _ARRONDISSEMENTS
    if _ARRONDISSEMENTS is None:
        import json
        try:
            brut = json.loads((config.BRUT / "ref_communes.json").read_text(encoding="utf-8"))
            _ARRONDISSEMENTS = {c["code"]: c["commune"] for c in brut
                                if c.get("type") == "arrondissement-municipal" and c.get("commune")}
        except (OSError, ValueError, KeyError) as e:
            log.warning("arrondissements municipaux illisibles dans le référentiel : %s", e)
            _ARRONDISSEMENTS = {}
    return _ARRONDISSEMENTS


_NOMS_COMMUNES: dict | None = None


def noms_communes() -> dict:
    """Nom de chaque commune actuelle, d'après le référentiel d'Etalab, pour le géocodage."""
    global _NOMS_COMMUNES
    if _NOMS_COMMUNES is None:
        import json
        try:
            brut = json.loads((config.BRUT / "ref_communes.json").read_text(encoding="utf-8"))
            _NOMS_COMMUNES = {c["code"]: c["nom"] for c in brut if c.get("type") == "commune-actuelle"}
        except (OSError, ValueError, KeyError) as e:
            log.warning("noms des communes illisibles dans le référentiel : %s", e)
            _NOMS_COMMUNES = {}
    return _NOMS_COMMUNES


def commune_de(code: pd.Series) -> pd.Series:
    """Code de commune, l'arrondissement municipal ramené à sa commune."""
    arr = arrondissements()
    return code.map(lambda c: arr.get(c, c) if isinstance(c, str) else c)


GEOCODAGE_SCORE_RUE = 0.3   # score minimal d'une rue trouvée dans la bonne commune sous un nom plus long
_MOTS_GENERIQUES_VOIE = {"rue", "avenue", "boulevard", "chemin", "route", "place", "allee", "impasse", "quai", "cours",
                         "de", "du", "des", "la", "le", "les", "l", "d", "et", "a", "au", "aux", "en", "sur", "bis", "ter"}


def mots_voie(voie) -> set:
    """Mots distinctifs d'un nom de voie (sans le type de voie, les articles ni les numéros), pour comparer une rue
    cherchée et une rue trouvée."""
    s = unicodedata.normalize("NFD", str(voie or "")).encode("ascii", "ignore").decode().lower()
    return {w for w in re.findall(r"[a-z]+", s) if w not in _MOTS_GENERIQUES_VOIE and len(w) > 1}


_VOIES_SANS_NOM = re.compile(r"^(?:le |la )?bourg$|route (?:nationale|departementale|communale)|^(?:rn|rd|vc)\b|"
                             r"^(?:place|rue) (?:de l )?(?:eglise|mairie|gare)$")
_CODES_POSTAUX = None


def codes_postaux() -> dict:
    """Codes postaux de chaque commune actuelle et communes de chaque code postal, d'après le référentiel d'Etalab."""
    global _CODES_POSTAUX
    if _CODES_POSTAUX is None:
        import json
        de, communes = {}, {}
        try:
            brut = json.loads((config.BRUT / "ref_communes.json").read_text(encoding="utf-8"))
            for c in brut:
                if c.get("type") == "commune-actuelle":
                    de[c["code"]] = sorted(c.get("codesPostaux") or [])
                    for cp in de[c["code"]]:
                        communes.setdefault(cp, set()).add(c["code"])
        except (OSError, ValueError, KeyError) as e:
            log.warning("codes postaux illisibles dans le référentiel : %s", e)
        _CODES_POSTAUX = (de, communes)
    return _CODES_POSTAUX


def voie_a_nom_propre(voie) -> bool:
    """Vrai pour une voie qui porte un nom propre, faux pour « Le Bourg », « Route nationale », « Place de l'Église »,
    qui existent dans presque chaque commune."""
    m = mots_voie(voie)
    if not m:
        return False
    s = " ".join(re.findall(r"[a-z]+", unicodedata.normalize("NFD", str(voie)).encode("ascii", "ignore").decode().lower()))
    s = re.sub(r"^\d+\s*(?:bis|ter)?\s*", "", s)
    return not _VOIES_SANS_NOM.search(s)


def _commune_voisine(lot: pd.DataFrame, requests) -> pd.DataFrame | None:
    """Adresses introuvables dans leur commune, cherchées dans le code postal de cette commune (décision du 29
    octobre 2026). Une adresse est acceptée dans une commune voisine qui partage ce code postal, au numéro ou à la rue,
    avec un score d'au moins config.GEOCODAGE_SCORE_MIN, quand tous les mots de la rue cherchée sont dans la rue trouvée et
    que la rue a un nom propre (« 34 rue Pasteur » à Mayot pour une structure inscrite à La Fère, code postal 02800). Renvoie voie, commune (celle de l'inscription), lat, lon, score, niveau et commune_adresse."""
    if lot.empty:
        return None
    de, communes = codes_postaux()
    l2 = lot.assign(postcode=lot["commune"].map(lambda c: (de.get(c) or [""])[0]))
    l2 = l2[l2["postcode"] != ""]
    if l2.empty:
        return None
    corps = l2[["voie", "commune", "voie_q", "postcode"]].to_csv(index=False)
    try:
        r = requests.post(config.GEOCODAGE_CSV, files={"data": ("adresses.csv", corps.encode("utf-8"))},
                          data={"columns": ["voie_q"], "postcode": "postcode"}, timeout=300)
        r.raise_for_status()
        g = pd.read_csv(io.StringIO(r.content.decode("utf-8")), dtype=str)
    except Exception as e:  # noqa: BLE001
        log.warning("géocodage dans le code postal indisponible : %s", e)
        return None
    sc = pd.to_numeric(g.get("result_score"), errors="coerce")
    trouvee = commune_de(g.get("result_citycode"))
    rue = g.get("result_street", pd.Series(index=g.index, dtype=object)).fillna(
        g.get("result_name", pd.Series(index=g.index, dtype=object)))
    ok = pd.Series([isinstance(t, str) and t != c and t in communes.get(cp, set()) and voie_a_nom_propre(q)
                    and bool(mots_voie(q)) and mots_voie(q) <= mots_voie(ru)
                    for t, c, cp, q, ru in zip(trouvee, g["commune"], g["postcode"], g["voie_q"], rue)], index=g.index)
    ok &= (sc >= config.GEOCODAGE_SCORE_MIN) & g.get("result_type").isin(["housenumber", "street"])
    g = g[ok]
    return pd.DataFrame({"voie": g["voie"], "commune": g["commune"],
                         "lat": pd.to_numeric(g["latitude"], errors="coerce"),
                         "lon": pd.to_numeric(g["longitude"], errors="coerce"), "score": sc[ok],
                         "niveau": g["result_type"].map({"housenumber": "adresse", "street": "rue"}),
                         "commune_adresse": trouvee[ok]})


def _geocoder(adresses: pd.DataFrame, hors_ligne: bool) -> pd.DataFrame:
    """Coordonnées des adresses (voie, commune) par le service de géocodage de l'IGN, avec cache. En mode hors ligne,
    seul le cache sert. Ne garde que les résultats situés dans la commune attendue, avec un score suffisant. La requête
    porte la voie et le nom de la commune (29 octobre 2026) : avec la voie seule, le score restait autour de 0,4 même
    pour une adresse trouvée dans la bonne commune, sous le seuil de config.GEOCODAGE_SCORE_MIN, et 4 200 structures
    étaient posées au centre de leur commune. Un échec obtenu avec la voie seule est cherché de nouveau."""
    cols = ["voie", "commune", "lat", "lon", "score", "niveau", "requete", "commune_adresse"]
    cache = pd.read_parquet(CACHE_GEO) if CACHE_GEO.exists() else pd.DataFrame(columns=cols)
    # échecs gardés pour Paris, Lyon et Marseille avant le 29 octobre 2026, dus au code d'arrondissement rendu par le
    # service et non à l'adresse, cherchés de nouveau
    villes = set(arrondissements().values())
    cache = cache[~(cache["commune"].isin(villes) & cache["lat"].isna())]
    for c in ("requete", "commune_adresse"):
        if c not in cache:
            cache[c] = None
    cache = cache[cache["lat"].notna() | (cache["requete"] == REQUETE_GEO)]
    a = adresses.dropna().drop_duplicates()
    a = a[a["voie"].str.len() > 2]
    connus = set(zip(cache["voie"], cache["commune"]))
    manque = a[[(v, c) not in connus for v, c in zip(a["voie"], a["commune"])]]
    if len(manque) and not hors_ligne:
        import requests
        nouveaux = []
        for i in range(0, len(manque), 2000):
            lot = manque.iloc[i:i + 2000]
            lot = lot.assign(nom_commune=lot["commune"].map(noms_communes()).fillna(""),
                             voie_q=lot["voie"].map(voie_developpee))
            corps = lot.rename(columns={"commune": "citycode"}).to_csv(index=False)
            try:
                r = requests.post(config.GEOCODAGE_CSV, files={"data": ("adresses.csv", corps.encode("utf-8"))},
                                  data={"columns": ["voie_q", "nom_commune"], "citycode": "citycode"}, timeout=300)
                r.raise_for_status()
                g = pd.read_csv(io.StringIO(r.content.decode("utf-8")), dtype=str)
            except Exception as e:  # noqa: BLE001
                log.warning("géocodage indisponible : %s", e)
                JOURNAL.note("IGN, géocodage des adresses", "erreur", str(e)[:300], page=config.GEOCODAGE_PAGE)
                break
            sc = pd.to_numeric(g.get("result_score"), errors="coerce")
            meme = commune_de(g.get("result_citycode")) == g["citycode"]
            # une rue trouvée dans la bonne commune sous un nom plus long que celui de la base (« Rue Marceau » pour
            # « Rue François Séverin Marceau » à Cholet, score 0,44) est acceptée sous le seuil quand tous les mots de la
            # rue cherchée sont dans la rue trouvée (constat du 29 octobre 2026, 41 structures de plus à leur rue)
            rue = g.get("result_street", pd.Series(index=g.index, dtype=object)).fillna(
                g.get("result_name", pd.Series(index=g.index, dtype=object)))
            plus_long = [bool(mots_voie(q)) and mots_voie(q) <= mots_voie(t) for q, t in zip(lot["voie_q"], rue)]
            ok = meme & ((sc >= config.GEOCODAGE_SCORE_MIN) |
                         ((sc >= GEOCODAGE_SCORE_RUE) & g.get("result_type").isin(["housenumber", "street"])
                          & pd.Series(plus_long, index=g.index)))
            niveau = g.get("result_type").map({"housenumber": "adresse", "street": "rue", "locality": "lieu_dit",
                                                "municipality": "commune"})
            res = pd.DataFrame({"voie": g["voie"], "commune": g["citycode"],
                                "lat": pd.to_numeric(g["latitude"], errors="coerce").where(ok),
                                "lon": pd.to_numeric(g["longitude"], errors="coerce").where(ok),
                                "score": sc, "niveau": niveau.where(ok), "requete": REQUETE_GEO, "commune_adresse": None})
            voisine = _commune_voisine(lot[~ok.to_numpy()], requests)
            if voisine is not None and len(voisine):
                res = res.set_index(["voie", "commune"])
                v = voisine.set_index(["voie", "commune"])
                res.update(v)
                res = res.reset_index()
            nouveaux.append(res)
        if nouveaux:
            cache = pd.concat([cache] + nouveaux, ignore_index=True).drop_duplicates(["voie", "commune"], keep="last")
            CACHE_GEO.parent.mkdir(parents=True, exist_ok=True)
            cache.to_parquet(CACHE_GEO, index=False)
            JOURNAL.note("IGN, géocodage des adresses", "ok", f"{sum(len(n) for n in nouveaux)} adresses géocodées",
                         url=config.GEOCODAGE_CSV, page=config.GEOCODAGE_PAGE)
    return cache


def hors_commune(lat: pd.Series, lon: pd.Series, communes: pd.Series, formes: dict | None,
                 tolerance: float = 0.003) -> pd.Series:
    """Vrai pour un point situé hors du contour de sa commune, à plus de la tolérance près (environ 300 mètres, en
    degrés). Un point sans contour connu n'est pas jugé."""
    out = pd.Series(False, index=lat.index)
    if not formes:
        return out
    from shapely.geometry import Point
    for i, y, x_, c in zip(lat.index, lat, lon, communes):
        g = formes.get(c)
        if g is not None and pd.notna(y) and pd.notna(x_) and g.distance(Point(float(x_), float(y))) > tolerance:
            out.at[i] = True
    return out


def _cle_adresse(a) -> str | None:
    if not isinstance(a, str) or not a.strip():
        return None
    s = unicodedata.normalize("NFD", voie_developpee(a)).encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", s)) or None


def adresse_du_gestionnaire(x: pd.DataFrame, f: pd.DataFrame) -> pd.Series:
    """Vrai pour une structure dont l'adresse est celle d'un établissement de son gestionnaire situé dans une autre
    commune (29 octobre 2026). Le ROR et FINESS reprennent souvent l'adresse du siège pour chaque site (les services
    d'accompagnement de l'ADAPEI du Morbihan à Lorient, Pontivy et Ploërmel sous « 36 boulevard de la Résistance »), et
    le géocodage, limité à la commune de la structure, trouvait alors une rue homonyme. Seulement quand la même adresse
    du même gestionnaire est reprise dans plusieurs communes et que FINESS enregistre un établissement de ce gestionnaire
    à cette adresse dans une autre commune. f, établissements de FINESS indexés par numéro (adresse, com, nofinessej)."""
    out = pd.Series(False, index=x.index)
    if "ej" not in x or "nofinessej" not in f:
        return out
    k = x["adresse"].map(_cle_adresse)
    p = pd.DataFrame({"ej": f["nofinessej"], "k": f["adresse"].map(_cle_adresse), "c": commune_de(f["com"])}).dropna()
    proprio = p.groupby(["ej", "k"])["c"].agg(set)
    g = pd.DataFrame({"ej": x["ej"], "k": k, "c": x["commune"]}).dropna()
    plusieurs = g.groupby(["ej", "k"])["c"].transform("nunique") > 1
    for i in g.index[plusieurs]:
        cs = proprio.get((g.at[i, "ej"], g.at[i, "k"]))
        out[i] = bool(cs) and g.at[i, "c"] not in cs
    return out


def localiser(lieux: pd.DataFrame, fin: pd.DataFrame, centres: dict | None, hors_ligne: bool,
              formes: dict | None = None, chefs_lieux=None) -> pd.DataFrame:
    """Coordonnées et précision de chaque structure (voir le texte du module)."""
    f = fin.set_index("nofinesset")
    x = lieux.copy()
    num = x["finess"].fillna(x.get("finess_rapproche"))
    origine = x["origine_commune"] if "origine_commune" in x else pd.Series(None, index=x.index, dtype=object)
    # une unité dont la commune est déduite de son nom n'a pas d'adresse, elle est placée au centre de la commune
    meme_commune = (commune_de(num.map(f["com"])) == x["commune"]) & (origine != "nom")
    x["lat"] = num.map(f["lat"]).where(meme_commune)
    x["lon"] = num.map(f["lon"]).where(meme_commune)
    x["lat"], x["lon"] = x["lat"].astype(float), x["lon"].astype(float)
    x["precision"] = pd.Series(np.where(x["lat"].notna(), "finess", None), index=x.index, dtype=object)
    for c in ("lat_ror", "lon_ror"):
        x[c] = pd.to_numeric(x[c], errors="coerce") if c in x else np.nan
    m = x["lat"].isna() & x["lat_ror"].notna()
    x.loc[m, "lat"] = x.loc[m, "lat_ror"].to_numpy(float)
    x.loc[m, "lon"] = x.loc[m, "lon_ror"].to_numpy(float)
    x.loc[m, "precision"] = "ror"
    # des coordonnées hors de la commune de la structure sont celles d'un autre lieu (le ROR donne souvent celles de
    # l'hôpital de rattachement, constat du 15 octobre 2026 dans le Var et le Vaucluse). Elles sont écartées, la
    # structure est alors placée à son adresse, sinon au centre de sa commune.
    loin = hors_commune(x["lat"], x["lon"], x["commune"], formes)
    x.loc[loin, ["lat", "lon"]] = np.nan
    x.loc[loin, "precision"] = None
    JOURNAL.controle("Structures dont les coordonnées de FINESS ou du ROR tombent hors de leur commune, replacées",
                     entier_fr(int(loin.sum())))
    # adresse, celle du ROR, sinon celle de FINESS
    x["adresse"] = x.get("voie").fillna(num.map(f["adresse"])) if "voie" in x else num.map(f["adresse"])
    gestionnaire = adresse_du_gestionnaire(x, f)
    # une unité d'un service qui ne se tient qu'à l'hôpital, sans adresse propre, dont le ROR donne une commune voisine
    # de son site FINESS, est dans ce site : les unités du CHU de Poitiers site de Châtellerault (inscrites à Antran), du
    # CH de Sens (Maillot), du CH de la Haute-Gironde (Saint-Seurin-de-Cursac) étaient placées au chef-lieu de la commune
    # voisine alors que FINESS et la SAE les situent à l'hôpital (constat C3 du 16 novembre 2026). Jamais pour un CMP ou
    # une structure extrahospitalière, dont la commune du ROR est souvent juste quand l'adresse manque.
    # sans adresse propre, ou avec la rue même de son site (« rue du Docteur-Luc-Montagnier » inscrite à Antran)
    sans_voie = x["voie"].isna() if "voie" in x else pd.Series(True, index=x.index)
    rue = lambda a: re.sub(r"^(?:\d+\s*(?:bis|ter|b|t)?\s+)", "", _cle_adresse(a) or "") or None  # noqa: E731
    meme_rue = x["adresse"].map(rue) == num.map(f["adresse"]).map(rue)
    com_site = commune_de(num.map(f["com"]))
    au_site = (x["type"].isin(config.TYPES_INTERNES_HOPITAL) & (sans_voie | meme_rue) & (origine == "unite") & num.notna()
               & com_site.notna() & (com_site != x["commune"]) & x["lat"].isna())
    # FINESS inscrit parfois la commune postale (l'hôpital de Honfleur est à Équemauville, celui de Cognac à
    # Châteaubernard) : seulement quand le point géocodé du site tombe dans la commune de FINESS et hors de celle du ROR
    lat_s, lon_s = num.map(f["lat"]).astype(float), num.map(f["lon"]).astype(float)
    au_site &= lat_s.notna()
    if au_site.any() and formes:
        au_site &= ~hors_commune(lat_s, lon_s, com_site, formes) & hors_commune(lat_s, lon_s, x["commune"], formes)
    elif not formes:
        au_site &= False
    if au_site.any():
        if "commune_inscription" not in x:
            x["commune_inscription"] = None
        x.loc[au_site, "commune_inscription"] = x.loc[au_site, "commune"]
        x.loc[au_site, "commune"] = com_site[au_site]
        x.loc[au_site, "lat"] = num[au_site].map(f["lat"]).astype(float)
        x.loc[au_site, "lon"] = num[au_site].map(f["lon"]).astype(float)
        x.loc[au_site & x["lat"].notna(), "precision"] = "finess"
        gestionnaire = gestionnaire & ~au_site
    JOURNAL.controle("Unités d'un service hospitalier sans adresse, inscrites au ROR dans une commune voisine de leur site, "
                     "replacées à leur site FINESS", entier_fr(int(au_site.sum())))
    m = x["lat"].isna() & x["adresse"].notna() & ~gestionnaire
    if m.any():
        cache = _geocoder(x.loc[m, ["adresse", "commune"]].rename(columns={"adresse": "voie"}), hors_ligne)
        g = cache.dropna(subset=["lat"]).set_index(["voie", "commune"])
        cles = list(zip(x.loc[m, "adresse"], x.loc[m, "commune"]))
        trouve = [k in g.index for k in cles]
        idx = x.index[m][trouve]
        if len(idx):
            gg = g.loc[[k for k, t in zip(cles, trouve) if t]]
            x.loc[idx, "lat"] = pd.to_numeric(gg["lat"], errors="coerce").to_numpy(float)
            x.loc[idx, "lon"] = pd.to_numeric(gg["lon"], errors="coerce").to_numpy(float)
            x.loc[idx, "precision"] = gg["niveau"].to_numpy()
            # adresse trouvée dans une commune voisine du même code postal (décision du 29 octobre 2026), la
            # structure est comptée là où elle reçoit, sa commune d'inscription reste dans commune_inscription
            ca = gg["commune_adresse"].to_numpy() if "commune_adresse" in gg else np.full(len(idx), None)
            autre = pd.Series([isinstance(v, str) and v != c for v, c in zip(ca, x.loc[idx, "commune"])], index=idx)
            if autre.any():
                if "commune_inscription" not in x:
                    x["commune_inscription"] = None
                i2 = autre[autre].index
                x.loc[i2, "commune_inscription"] = x.loc[i2, "commune"]
                x.loc[i2, "commune"] = ca[autre.to_numpy()]
            enfants = {t_[0] for t_ in config.LIEUX_TYPES if t_[4].get("parent")}
            v_ = x.loc[autre[autre].index]
            JOURNAL.controle("Structures dont l'adresse se trouve dans une commune voisine du même code postal, "
                             "comptées dans la commune de leur adresse",
                             entier_fr(len(v_[~v_["type"].isin(enfants)].drop_duplicates(["type", "lieu"])
                                           if "lieu" in v_ else v_)))
    # une unité placée à son établissement de rattachement faute de mieux est signalée comme telle
    x.loc[(origine == "structure") & x["lat"].notna(), "precision"] = "rattachement"
    m = x["lat"].isna()
    # adresse inconnue ou introuvable, le chef-lieu de la commune (chefs_lieux, fonction des codes de commune vers leur
    # point dans la Base Adresse Nationale), sinon le centre de son contour
    if chefs_lieux is not None and m.any():
        ch = chefs_lieux(sorted(set(x.loc[m, "commune"].dropna())))
        c = x.loc[m, "commune"].map(lambda k: ch.get(k))
        idx = c[c.notna()].index
        x.loc[idx, "lon"] = [v[0] for v in c[idx]]
        x.loc[idx, "lat"] = [v[1] for v in c[idx]]
        x.loc[idx, "precision"] = np.where(gestionnaire[idx], "chef_lieu_gestionnaire", "chef_lieu")
        m = x["lat"].isna()
    if centres and m.any():
        c = x.loc[m, "commune"].map(lambda k: centres.get(k))
        ok = c.notna()
        idx = c[ok].index
        x.loc[idx, "lon"] = [v[0] for v in c[ok]]
        x.loc[idx, "lat"] = [v[1] for v in c[ok]]
        x.loc[idx, "precision"] = np.where(gestionnaire[idx], "commune_gestionnaire", "commune")
    # structures replacées faute d'adresse propre, une par type et par clé, sans les lignes par public des CMP ni les
    # inscriptions qui ont leurs propres coordonnées dans FINESS ou le ROR
    enfants = {t_[0] for t_ in config.LIEUX_TYPES if t_[4].get("parent")}
    r = x[x["precision"].isin(["chef_lieu_gestionnaire", "commune_gestionnaire"]) & ~x["type"].isin(enfants)]
    r = r.drop_duplicates(["type", "lieu"]) if "lieu" in r else r
    JOURNAL.controle("Structures qui portent l'adresse d'un établissement de leur gestionnaire situé dans une autre "
                     "commune, placées au chef-lieu ou au centre de leur commune et non sur une rue homonyme",
                     f"{entier_fr(len(r))} (au chef-lieu {entier_fr(int((r['precision'] == 'chef_lieu_gestionnaire').sum()))}, "
                     f"au centre du contour {entier_fr(int((r['precision'] == 'commune_gestionnaire').sum()))})")
    return x


def professionnels(lieux: pd.DataFrame, act: pd.DataFrame) -> pd.DataFrame:
    """Personnes distinctes déclarant une activité à l'établissement et dans la commune de la structure, par profession. Les
    lieux du ROR sans numéro FINESS d'établissement n'en ont pas. Le répertoire rattache une activité à un établissement
    (numéro FINESS), pas à une structure : quand plusieurs structures partagent ce numéro dans la même commune, l'effectif
    est celui de l'établissement, pas de chacune d'elles. La colonne partage_par donne ce nombre de structures, et un
    effectif partagé n'est jamais attribué à une structure ni additionné entre elles (règle des trois temps, constat du
    29 octobre 2026, 3 882 numéros partagés par 12 910 structures). Les structures sont comptées tous types confondus,
    une par type et par clé de lieu (la même clé porte souvent l'hospitalisation complète et l'hôpital de jour d'un
    hôpital, 710015587 à Montceau-les-Mines, constat de la séance de l'API du 29 octobre 2026), sans compter les lignes
    par public d'une même structure (types enfants, CMP pour adultes et pour enfants)."""
    a = act[act["finess"].fillna("") != ""][["id", "prof", "finess", "com"]].copy()
    a["prof"], a["com"] = a["prof"].astype(str), a["com"].astype(str)
    a = a[a["prof"].isin(PROFESSIONS)]
    num = lieux["finess"].fillna(lieux.get("finess_rapproche"))
    l = pd.DataFrame({"lieu": lieux["lieu"], "finess": num, "commune": lieux["commune"]}).dropna().drop_duplicates("lieu")
    j = a.merge(l, left_on=["finess", "com"], right_on=["finess", "commune"])
    t = j.groupby(["lieu", "prof"])["id"].nunique().unstack(fill_value=0)
    t = t.reindex(columns=[p for p in PROFESSIONS if p in t.columns])
    # toutes les clés de lieu à numéro FINESS, même sans professionnel déclaré, pour que le partage soit connu de chacune
    # (sinon une structure à numéro partagé sans déclaré recevait 0 au lieu de rien, 2 224 dans la version du 29 octobre)
    t = t.reindex(pd.Index(l["lieu"].unique(), name=t.index.name), fill_value=0)
    # structures distinctes sous chaque numéro et dans chaque commune, une par type et par clé de lieu, hors types enfants
    enfants = {t_[0] for t_ in config.LIEUX_TYPES if t_[4].get("parent")}
    s = pd.DataFrame({"type": lieux["type"], "lieu": lieux["lieu"], "finess": num, "commune": lieux["commune"]})
    s = s[~s["type"].isin(enfants)].dropna().drop_duplicates(["type", "lieu"])
    n_struct = s.groupby(["finess", "commune"]).size()
    n_types = s.groupby(["finess", "commune"])["type"].nunique()
    # partage d'une clé de lieu : le plus grand des partages des numéros de ses lignes, et au moins son nombre de types.
    # Une clé de la liste vérifiée porte souvent plusieurs types sous un nom (« CMP / CATTP / HDJ »), chacun sous son
    # numéro : avec le seul numéro de sa première ligne, l'hôpital de jour de Saint-Chamond recevait les déclarés du CMP
    # (constat du 20 novembre 2026, 13 structures)
    n_lieu = pd.Series(list(zip(s["finess"], s["commune"])), index=s.index).map(n_struct)
    partage = n_lieu.groupby(s["lieu"]).max().combine(s.groupby("lieu")["type"].nunique(), max)
    t["partage_par"] = t.index.map(partage).fillna(1).astype(int)
    # contrôle permanent, la somme attribuée aux structures d'un même établissement ne dépasse jamais l'effectif qui y est
    # déclaré, puisqu'un effectif partagé n'est attribué à aucune
    propres = t[t["partage_par"] == 1].drop(columns="partage_par")
    etab = j.groupby(["finess", "commune", "prof"])["id"].nunique().unstack(fill_value=0)
    cle = l.set_index("lieu")[["finess", "commune"]]
    somme = propres.join(cle).groupby(["finess", "commune"]).sum()
    depasse = int((somme.sub(etab.reindex(somme.index).reindex(columns=somme.columns).fillna(0)) > 0).any(axis=1).sum())
    # contrôle permanent, aucune clé de lieu portée par plusieurs types n'est créditée comme une structure seule
    cles_types = s.groupby("lieu")["type"].nunique()
    seule_a_tort = int((t.index.map(cles_types).fillna(1).to_numpy() > t["partage_par"].to_numpy()).sum())
    JOURNAL.controle("Professionnels déclarés par structure, numéros FINESS partagés entre plusieurs structures d'une "
                     "même commune, tous types confondus (effectif de l'établissement, attribué à aucune)",
                     f"{int((n_struct > 1).sum())} numéros, dont {int((n_types > 1).sum())} portés par des structures "
                     f"de plusieurs types, {int(n_struct[n_struct > 1].sum())} structures, "
                     f"{int(((t['partage_par'] > 1) & (t.drop(columns='partage_par').sum(axis=1) > 0)).sum())} clés de "
                     f"lieu avec des déclarés ; établissements dont la somme "
                     f"attribuée dépasse l'effectif déclaré (attendu, aucun) {depasse} ; clés de lieu de plusieurs types "
                     f"créditées comme une structure seule (attendu, aucune) {seule_a_tort}")
    return t


def exercice_structures(lieux: pd.DataFrame, act: pd.DataFrame,
                        cat_finess: pd.Series | None = None) -> pd.DataFrame | None:
    """Personnes distinctes de chaque profession qui déclarent au RPPS une activité dans une structure de santé mentale
    enregistrée sous son propre numéro FINESS (config.LIEUX_EXERCICE_TYPES), par type, en France, par région et par
    département (lieu de la structure). Une personne qui exerce dans deux types compte dans chacun, une fois dans
    « ensemble ». Le lieu déclaré est souvent l'hôpital de rattachement, les structures sont donc sous-comptées."""
    if act is None or lieux is None or lieux.empty:
        return None
    a = act[act["finess"].fillna("") != ""][["id", "prof", "finess", "com"]].copy()
    a["prof"], a["com"] = a["prof"].astype(str), a["com"].astype(str)
    a = a[a["prof"].isin(config.LIEUX_EXERCICE_PROFESSIONS)]
    propres = _categories_propres()
    x = lieux[lieux["type"].isin(config.LIEUX_EXERCICE_TYPES)].copy()
    cat = x["categorie_finess"].fillna("").astype(str) if "categorie_finess" in x else pd.Series("", index=x.index)
    # catégorie de FINESS lue par le numéro quand la réunion avec le ROR l'a laissée vide (relecture du 17 novembre
    # 2026 : 2 015 CMP de FINESS et du ROR écartés, 51 psychiatres comptés dans les CMP contre 256 CMP qui en déclarent)
    if cat_finess is not None and "finess" in x:
        cat = cat.where(cat != "", x["finess"].map(cat_finess).fillna("").astype(str))
    x = x[[c in propres.get(t, set()) for t, c in zip(x["type"], cat)]]
    l = pd.DataFrame({"type": x["type"], "finess": x["finess"], "commune": x["commune"], "dep": x["dep"],
                      "reg": x["reg"]}).dropna(subset=["finess"]).drop_duplicates(["type", "finess", "commune"])
    j = a.merge(l, left_on=["finess", "com"], right_on=["finess", "commune"])
    if j.empty:
        return None
    j["fr"] = "FR"
    out = []
    for niv in ("fr", "reg", "dep"):
        g = j.groupby([niv, "type", "prof"])["id"].nunique().rename("personnes").reset_index()
        e = j.groupby([niv, "prof"])["id"].nunique().rename("personnes").reset_index().assign(type="ensemble")
        out.append(pd.concat([g, e]).rename(columns={niv: "code"}).assign(niveau=niv))
    t = pd.concat(out, ignore_index=True)[["niveau", "code", "type", "prof", "personnes"]]
    fr = t[(t["niveau"] == "fr") & (t["type"] == "ensemble")].set_index("prof")["personnes"]
    JOURNAL.controle("Professionnels déclarés dans une structure de santé mentale à numéro FINESS propre (France)",
                     ", ".join(f"{p} {int(fr.get(p, 0))}" for p in ("psychiatre", "psychologue", "infirmier")
                               if p in fr.index))
    return t


def distances(lieux: pd.DataFrame, ref, centres: dict) -> pd.DataFrame:
    """Distance à vol d'oiseau du centre de chaque commune à la structure la plus proche de chaque type, en km, cherchée
    sur le territoire de la commune (Hexagone, Corse, chaque département d'outre-mer, config.ZONES_TERRESTRES).
    Infinie quand ce territoire n'a aucune structure de ce type, ce que les résumés écrivent comme une case vide."""
    from .analyses import coords_3d, plus_proche_km, zone_terrestre
    com = ref.communes[ref.communes["code"].isin(centres)]
    xy = np.array([centres[c] for c in com["code"]])
    xyz = coords_3d(xy[:, 0], xy[:, 1])
    zones = zone_terrestre(com["dep"])
    out = {}
    for tid, g in lieux.dropna(subset=["lat", "lon"]).groupby("type"):
        p = coords_3d(g["lon"].to_numpy(float), g["lat"].to_numpy(float))
        out[tid] = plus_proche_km(xyz, zones, p, zone_terrestre(g["dep"]))
    return pd.DataFrame(out, index=com["code"].to_numpy())


def resumer_distances(dist: pd.DataFrame, ref, niveaux=("epci", "dep", "reg")) -> dict:
    """Par territoire et par type, distance médiane des habitants et part à plus de 20 et 30 km. Un habitant dont le
    territoire n'a aucune structure de ce type compte au-delà de 20 et de 30 km, et la médiane reste vide quand elle
    tombe sur lui (analyses.mediane_ponderee)."""
    from .analyses import mediane_ponderee
    sans = np.isinf(dist.to_numpy())
    if sans.any():
        com_dep = ref.communes.set_index("code")["dep"].reindex(dist.index)
        par = {t: sorted(set(com_dep[np.isinf(dist[t].to_numpy())])) for t in dist.columns if np.isinf(dist[t]).any()}
        JOURNAL.controle("Distances aux structures, types absents du territoire de la commune (Corse et chaque "
                         "département d'outre-mer comptés à part, aucune distance par-dessus la mer)",
                         f"{nombre(int(sans.sum()))} couples commune et type sur {nombre(sans.size)}, " + "; ".join(
                             f"{dep} {sum(dep in v for v in par.values())} types"
                             for dep in sorted({d for v in par.values() for d in v})))
    com = ref.communes.set_index("code").reindex(dist.index)
    pop = com["pop"].astype(float).fillna(0)
    res = {}
    for niv in niveaux + ("fr",):
        grp = pd.Series("FR", index=dist.index) if niv == "fr" else com[niv]
        lignes = []
        for code, idx in grp.groupby(grp).groups.items():
            w = pop.loc[idx].to_numpy()
            if w.sum() <= 0:
                continue
            for tid in dist.columns:
                d = dist.loc[idx, tid].to_numpy()
                lignes.append((code, tid, mediane_ponderee(d, w), float(w[d > 20].sum() / w.sum()),
                               float(w[d > 30].sum() / w.sum())))
        res[niv] = pd.DataFrame(lignes, columns=["code", "type", "distance_mediane_km", "part_plus_20_km",
                                                 "part_plus_30_km"])
    return res


# Relecture des bases, chaque correction apportée à FINESS et au ROR avec le nombre de structures concernées, montrée
# sur la page méthode et dans le rapport national (demande du 13 octobre 2026, « bien préciser la relecture »)
RELEVE: list[dict] = []


def retyper_cattp(lieux: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    """Ateliers thérapeutiques rangés avec la réhabilitation psychosociale et CATTP en milieu pénitentiaire rangés
    comme les CMP en milieu pénitentiaire (décisions du 16 octobre 2026, voir config). Renvoie les structures
    et les deux nombres."""
    x = lieux.copy()
    m = x["type"] == "lieu_cattp"
    if not m.any():
        return x, 0, 0
    nom = pd.Series("", index=x.index)
    for c in ("nom_affiche", "nom", "noms_unites"):
        if c in x:
            nom = nom + " " + x[c].fillna("").astype(str)
    nom = nom.map(_simple)
    dit_cattp = nom.str.contains(config.RETYPAGE_CATTP, regex=True)
    cat = x["categorie_finess"].fillna("").astype(str) if "categorie_finess" in x else pd.Series("", index=x.index)
    prison = m & nom.str.contains(config.NOM_PENITENTIAIRE, regex=True)
    atelier = m & ~prison & ~dit_cattp & ((cat == config.FINESS_ATELIER_THERAPEUTIQUE)
                                          | nom.str.contains(config.NOM_ATELIER_THERAPEUTIQUE, regex=True))
    types = {t[0]: t for t in config.LIEUX_TYPES}
    for mm, tid in ((atelier, "lieu_rehab_psy"), (prison, "lieu_consult_psy")):
        t = types[tid]
        x.loc[mm, ["type", "libelle_type", "famille", "groupe"]] = [t[0], t[1], t[2], t[3]]
        if "confirmation" in x:
            x.loc[mm, "confirmation"] = None
    JOURNAL.controle("CATTP rangés dans un autre type",
                     f"{int(atelier.sum())} ateliers thérapeutiques avec la réhabilitation psychosociale, "
                     f"{int(prison.sum())} CATTP en milieu pénitentiaire écartés du compte des territoires")
    return x, int(atelier.sum()), int(prison.sum())


ROLES = {"structure": "structure principale", "antenne": "antenne", "site": "site supplémentaire",
         "cjc": "consultation jeunes consommateurs", "hebergement": "hébergement",
         "penitentiaire": "milieu pénitentiaire", "equipe": "équipe sans lieu propre (liaison)"}


def roles_addictologie(lieux: pd.DataFrame) -> pd.DataFrame:
    """Rôle lu dans le nom pour les structures d'addictologie (config.ROLES_ADDICTOLOGIE), après la relation de budget
    de FINESS. Un nom qui ne dit rien garde le rôle de la relation (ou « structure »)."""
    x = lieux.copy()
    if "role_structure" not in x:
        x["role_structure"] = None
    nom = pd.Series("", index=x.index)
    for c in ("nom_affiche", "nom", "noms_unites"):
        if c in x:
            nom = nom + " " + x[c].fillna("").astype(str)
    nom = nom.map(_simple)
    for tid, regles in config.ROLES_ADDICTOLOGIE.items():
        m = x["type"] == tid
        if not m.any():
            continue
        x.loc[m & x["role_structure"].isna(), "role_structure"] = "structure"
        pris = pd.Series(False, index=x.index)
        for role, motif in regles:
            r = m & ~pris & nom.str.contains(motif, regex=True)
            x.loc[r, "role_structure"] = role
            pris |= r
        v = x.loc[m, "role_structure"].value_counts()
        lib = {t[0]: t[1] for t in config.LIEUX_TYPES}[tid]
        JOURNAL.controle(f"Rôles lus dans le nom, {lib}", ", ".join(f"{ROLES.get(k, k)} {int(n)}" for k, n in v.items()))
    return x


def comptes_csapa(lieux: pd.DataFrame) -> dict:
    """Trois comptes des CSAPA jamais additionnés (décision du 16 octobre 2026). Lieux (chaque site d'accueil),
    établissements FINESS de catégorie CSAPA, et établissements dont aucune ligne n'est désignée par son nom comme site
    annexe ou consultation jeunes consommateurs."""
    g = lieux[lieux["type"] == "lieu_csapa"]
    if g.empty:
        return {}
    cats = _categories_propres().get("lieu_csapa", set())
    num = g["finess"].fillna(g["finess_rapproche"]) if "finess_rapproche" in g else g["finess"]
    cat = g["categorie_finess"].fillna("") if "categorie_finess" in g else pd.Series("", index=g.index)
    etab = num[cat.isin(cats) & num.notna()]
    # un établissement est principal dès qu'une de ses lignes n'est désignée par son nom ni comme antenne ni comme CJC
    # (règle de la note, la relation de budget de FINESS ne sert pas à ce compte)
    nom = pd.Series("", index=g.index)
    for c in ("nom_affiche", "nom", "noms_unites"):
        if c in g:
            nom = nom + " " + g[c].fillna("").astype(str)
    nom = nom.map(_simple)
    motifs = "|".join(m for r, m in config.ROLES_ADDICTOLOGIE["lieu_csapa"] if r in ("antenne", "cjc"))
    annexe = nom.str.contains(motifs, regex=True)
    principaux = set(etab[~annexe.reindex(etab.index)])
    return {"lieux": len(g), "etablissements": int(etab.nunique()), "principaux": len(principaux)}


def roles_antennes(lieux: pd.DataFrame, fin: pd.DataFrame | None) -> tuple[pd.DataFrame, dict]:
    """Rôle de chaque CMPP et CAMSP (config.LIEUX_ANTENNES_FINESS), structure principale, antenne ou site
    supplémentaire, et confirmation héritée du site principal (niveau « principal ») pour une antenne ou un site que
    rien ne confirme directement, quand son principal est confirmé (décision du 16 octobre 2026). Le site
    d'accueil (chaque ligne) reste l'unité des distances et de la carte."""
    x = lieux.copy()
    x["role_structure"] = None
    if fin is None or "finess_porteuse" not in fin:
        return x, {}
    f = fin.drop_duplicates("nofinesset").set_index("nofinesset")
    port, cat = f["finess_porteuse"].dropna(), f["categetab"]
    num = x["finess"].fillna(x["finess_rapproche"]) if "finess_rapproche" in x else x["finess"]
    rendu = {}
    for tid in config.LIEUX_ANTENNES_FINESS:
        m = x["type"] == tid
        if not m.any():
            continue
        cats = _categories_propres().get(tid, set())
        g = x[m]
        nb = num[m]
        partage = nb.duplicated(keep=False) & nb.notna()
        site = partage & (g["provenance"] == "ror")
        antenne = ~site & nb.map(lambda n: isinstance(n, str) and n in port.index and cat.get(port[n]) in cats)
        role = pd.Series("structure", index=g.index)
        role[antenne] = "antenne"
        role[site] = "site"
        x.loc[g.index, "role_structure"] = role
        # principal de chaque ligne, numéro du porteur pour une antenne, de la ligne non ROR au même numéro pour un site
        conf_num = {}
        for i in g.index[role == "structure"]:
            conf_num.setdefault(nb[i], []).append(x.at[i, "confirmation"])
        for i in g.index[role == "antenne"]:
            conf_num.setdefault(nb[i], []).append(x.at[i, "confirmation"])
        ok = {"etablissement", "source_publique", "has_sirene", "has", "sirene", "examinee"}
        herite = 0
        if "confirmation" in x:
            for i in g.index[role != "structure"]:
                if x.at[i, "confirmation"] != "bases":
                    continue
                princ = port.get(nb[i]) if role[i] == "antenne" else nb[i]
                if role[i] == "site" and princ in port.index and cat.get(port[princ]) in cats:
                    princ = port[princ] if any(c in ok for c in conf_num.get(port[princ], [])) else princ
                if any(c in ok for c in conf_num.get(princ, [])):
                    x.at[i, "confirmation"] = "principal"
                    herite += 1
        v = role.value_counts()
        rendu[tid] = {"structure": int(v.get("structure", 0)), "antenne": int(v.get("antenne", 0)),
                      "site": int(v.get("site", 0)), "herite": herite}
        lib = {t[0]: t[1] for t in config.LIEUX_TYPES}[tid]
        JOURNAL.controle(f"Structures principales, antennes et sites, {lib}",
                         f"{len(g)} sites d'accueil, {rendu[tid]['structure']} sites désignés comme structure principale par leur nom ou leur rattachement, "
                         f"{rendu[tid]['antenne']} antennes, {rendu[tid]['site']} sites supplémentaires, {herite} "
                         f"confirmés par leur site principal")
    return x, rendu


def cattp_des_cmp(lieux: pd.DataFrame, verifies: set | None = None, gardees: list | None = None,
                  noms_etab: dict | None = None) -> tuple[pd.DataFrame, int]:
    """CATTP tenus dans un CMP (décision du 16 octobre 2026, un CATTP est le lieu où l'hôpital déclare cette
    activité). Quand le nom d'un CMP, une unité du ROR qu'il réunit ou l'enseigne Sirene de son établissement annonce un
    CATTP (« CMP-CATTP enfants ») et que son gestionnaire n'a aucun CATTP dans la même commune, un CATTP est compté au
    même lieu. Son niveau de confirmation suit la source qui l'annonce (Sirene, liste vérifiée de l'établissement, ou
    les bases seulement). Un gestionnaire qui a déjà un CATTP dans la commune n'en reçoit pas, le CATTP annoncé est
    alors sans doute celui-là, décrit à une autre adresse (constat sur Ville-Évrard et la Savoie, 16 octobre 2026).
    Le nom de l'établissement de FINESS qui porte le CMP compte aussi (« CMP-CATTP ADULTES MOREZ », « HJ CMP CATTP
    ENFANTS ARBOIS » : aucun CATTP n'était compté dans le Jura, chantier des structures du 16 novembre 2026), une fois
    par établissement et par commune quand plusieurs CMP le partagent, et seulement pour un CMP placé là où est
    l'établissement (pas un CMP dont la commune est lue dans son nom). Un établissement dont les CATTP sont vérifiés
    (`verifies`, couples entité juridique et département, vide pour tous ses départements) en reçoit un seulement
    sans raison écrite de le laisser de côté (contenus/inscriptions_laissees.csv, type lieu_cattp, nom du CMP) : dans
    le doute, le CATTP annoncé reste compté (règle du 19 novembre 2026 ; le 21 novembre, 57 CATTP annoncés ainsi
    disparaissaient sans raison à mesure que les listes vérifiées s'achevaient, dont sept dans le Jura). Son niveau
    suit la source qui l'annonce ; ceux que seules les bases annoncent sont ajoutés à `gardees`, la liste des
    structures gardées en attente de vérification."""
    motif = config.SIRENE_ENSEIGNES["lieu_cattp"] + r"|\bCATTG\b"
    x = lieux
    c = x[x["type"] == "lieu_cmp"]
    dep_c = c["dep"] if "dep" in c else pd.Series("", index=c.index)
    sous_liste = pd.Series([bool(verifies) and ((e, d) in verifies or (e, "") in verifies)
                            for e, d in zip(c["ej"], dep_c)], index=c.index, dtype=bool)
    if sous_liste.any():
        from .structures_verifiees import charger_laissees
        lai = charger_laissees()
        lai = lai[lai["type"] == "lieu_cattp"]
        cles = {(r.ej, r.commune, r.nom.strip()) for r in lai.itertuples()}
        noms = lambda r: {str(r.get(k) or "").strip() for k in ("nom", "nom_affiche", "nom_finess")} - {""}  # noqa: E731
        laisse = pd.Series([bool(s_) and any((r["ej"], r["commune"], n_) in cles for n_ in noms(r))
                            for s_, (_, r) in zip(sous_liste, c.iterrows())], index=c.index, dtype=bool)
        c, sous_liste = c[~laisse], sous_liste[~laisse]
    if c.empty:
        return x, 0
    col = lambda n: c[n].fillna("").astype(str) if n in c else pd.Series("", index=c.index)  # noqa: E731
    # le nom de l'établissement ne vaut que pour une unité placée dans sa commune, pas pour une unité dont la commune
    # est lue dans son propre nom (« CMP CATTP DE BRIVE » pour les CMP d'Egletons et de Tulle, banc d'essai du
    # 16 novembre 2026)
    hors_struct = col("origine_commune") == "nom"
    par_nom = (col("nom_affiche") + " " + col("nom") + " " + col("noms_unites")).str.contains(motif, case=False, regex=True)         | ((col("structure_nom") + " " + col("nom_finess")).str.contains(motif, case=False, regex=True) & ~hors_struct)
    par_sirene = col("enseigne_sirene").str.contains(motif, case=False, regex=True)
    ca = x[x["type"] == "lieu_cattp"]
    deja = set(zip(ca["ej"].fillna(""), ca["commune"]))
    sans_ej = set(ca.loc[ca["ej"].isna(), "commune"])
    libre = [(e or "", k) not in deja and not (not e and k in sans_ej)
             for e, k in zip(c["ej"].where(c["ej"].notna(), None), c["commune"])]
    m = (par_nom | par_sirene) & pd.Series(libre, index=c.index)
    # un établissement de FINESS qui porte plusieurs CMP d'une commune (« HJ CMP CATTP ENFANTS ADOS LONS ») annonce un
    # seul CATTP : un par gestionnaire, commune et nom d'établissement
    struct = (col("structure_nom") + " " + col("nom_finess")).str.strip()
    m &= ~pd.Series(list(zip(c["ej"].fillna(""), c["commune"], struct)), index=c.index).where(struct != "").duplicated()         | (struct == "")
    if not m.any():
        return x, 0
    n = c[m].copy()
    t = next(t for t in config.LIEUX_TYPES if t[0] == "lieu_cattp")
    n["type"], n["libelle_type"], n["famille"], n["groupe"] = t[0], t[1], t[2], t[3]
    n["lieu"] = n["lieu"] + "|cattp"
    n["provenance"] = "nom_cmp"
    st = n["statut_verification"] if "statut_verification" in n else pd.Series(None, index=n.index)
    nom_verif = col("nom_affiche")[m].str.contains(motif, case=False, regex=True)
    niv = pd.Series("bases", index=n.index, dtype=object)
    niv[par_sirene[m]] = "sirene"
    v = st.isin(["etablissement", "source_publique"]) & nom_verif
    niv[v] = st[v]
    n["confirmation"] = niv
    for k in ("verdict", "examen", "verifiee"):
        if k in n:
            n[k] = None if k != "verifiee" else False
    if "siret_sirene" in n:
        for k in ("siret_sirene", "enseigne_sirene", "adresse_sirene"):
            n[k] = n[k].where(par_sirene[m], None)
    if "confirmee_has" in n:
        n["confirmee_has"] = False
    # la vérification du CMP ne vaut pour son CATTP que si le nom vérifié l'annonce : sinon le CATTP ne reprend ni son
    # statut ni sa source (« confirmée par l'établissement » pour un CATTP que la liste ne cite pas, relecture du
    # 21 novembre 2026, 71 cas)
    for k in ("statut_verification", "source_verification", "adresse_source", "date_verification",
              "remarque_verification"):
        if k in n:
            n[k] = n[k].where(v, None)
    # ceux que le nom vérifié n'annonce pas restent à vérifier ; « CMP-CATTG de Parthenay », nom de la liste vérifiée,
    # confirme son CATTP par l'établissement
    gv = sous_liste[m] & (niv == "bases").values
    if gardees is not None and gv.any():
        for _, r in n[gv.values].iterrows():
            gardees.append({"ej": r.get("ej"), "etablissement": (noms_etab or {}).get(r.get("ej")) or r.get("structure_nom"),
                            "type": "lieu_cattp", "nom": r.get("nom"), "commune": r.get("commune"),
                            "nom_commune": r.get("nom_commune"), "finess": r.get("finess"), "provenance": "nom_cmp",
                            "raison": "CATTP annoncé par le nom du CMP, absent de la liste vérifiée de l'établissement, "
                                      "qui ne donne pas de raison de le laisser de côté : gardé, à vérifier"})
    out = pd.concat([x, n], ignore_index=True)
    JOURNAL.controle("CATTP annoncés par le nom d'un CMP, comptés au même lieu",
                     f"{int(m.sum())} CATTP ({int((par_sirene & m).sum())} par l'enseigne Sirene, "
                     f"{int((par_nom & ~par_sirene & m).sum())} par le nom seulement), "
                     f"{int((par_nom | par_sirene).sum() - m.sum())} CMP qui en annoncent un sans ajout, leur gestionnaire "
                     f"ayant déjà un CATTP dans la commune, {int(gv.sum())} d'un établissement dont la liste vérifiée "
                     f"ne le cite pas, gardés à vérifier")
    return out, int(m.sum())


def _releve(base: str, constat: str, nombre_: int, traitement: str):
    RELEVE.append({"base": base, "constat": constat, "nombre": int(nombre_), "traitement": traitement})


# mots qui décrivent une modalité d'accueil ou une mention d'autorisation, sans distinguer deux structures
_MODALITES = re.compile(r"\bmention\b[^-_]*|\b(temporaires?|permanents?|internat|externat|hebergement|complet|accueil|"
                        r"jour|nuit|sequentiel)\b")
_CODE_SECTEUR = re.compile(r"\b(?:\d{2}|2a|2b)\s?[gi]\s?\d{1,2}\b")
_MARQUE_ENFANTS = re.compile(r"\b(enfants?|pedo\w*|infanto\w*|juvenile?s?|jeunes?)\b")
_MARQUE_ADOS = re.compile(r"\bado\w*")
# sigles de pôle et mots génériques qui ne distinguent pas deux CMP (« PPEA », « Secteur », « CH »), et mots courts qui
# distinguent au contraire deux lieux d'une même ville (« Troyes Nord » et « Troyes Sud »)
_MOTS_POLE = {"secteur", "intersecteur", "pole", "cmpi", "cmpe", "cmpa", "cmpea", "ch", "chs", "chu", "chi", "epsm",
              "infanto", "juvenile", "adulte", "adultes", "enfant", "enfants", "ado", "adolescents", "general",
              "generale", "psychiatrie", "pedopsychiatrie", "consultations", "consultation"}
_MOTS_LIEU = {"nord", "sud", "est", "ouest", "haut", "bas", "gare", "port", "mer", "val", "mont", "bois", "parc",
              "ile", "cite", "pont", "lac"}
# sigle court de pôle ou de secteur (« PPEA », « PES », « PAV »), mot de quatre lettres au plus commençant par p ou
# sans voyelle, à la différence d'un nom (« Jean », « Aymé »)
_SIGLE_COURT = re.compile(r"^(?:p[a-z]{1,3}|[^aeiouy\d]{1,4})$")
_SIGLE_POLE = re.compile(r"^(?!cmp)[a-z]{2,5} cmp")
_ANTENNE = re.compile(r"antenne|permanence|consultations? avancee|\bant\b")
# consultation spécialisée, qui ne se confond pas avec le CMP de secteur de la même commune
_SPECIALISE = re.compile(r"addicto|alcoolo|perinat|bebe|petite enfance|surdi|autis|psychotrauma|precarite|ecoute|"
                         r"crise|urgence")
_MARQUE_AGES = re.compile(r"\b(geronto\w*|agees?|vieillissement)\b")


def _public_nom(s: str) -> tuple:
    """Public que dit un nom, enfants (avec ou sans adolescents), adolescents seuls, personnes âgées."""
    enf, ado = bool(_MARQUE_ENFANTS.search(s)), bool(_MARQUE_ADOS.search(s))
    return ("enf" if enf else "ado" if ado else ""), bool(_MARQUE_AGES.search(s))


def controle_doublons(lieux: pd.DataFrame) -> tuple[int, int]:
    """Contrôle permanent (29 octobre 2026) : aucune paire de structures du même type, du même numéro FINESS, de la même
    commune, du même nom lisible et de la même adresse (abréviations développées). Les paires d'un CMP pour adultes et
    d'un CMP pour enfants au même lieu sont comptées à part, deux structures selon la règle, à vérifier (antenne
    d'Hornoy-le-Bourg, CMP Emmaüs d'Aulnay-sous-Bois). Renvoie les deux nombres."""
    enfants = {t[0] for t in config.LIEUX_TYPES if t[4].get("parent")}
    p = lieux[~lieux["type"].isin(enfants) & lieux["finess"].notna()]
    nom = (p["nom_affiche"] if "nom_affiche" in p else p["nom"]).fillna(p["nom"]).fillna("").map(_simple)
    adr = p["adresse"].fillna("").map(lambda s: _simple(voie_developpee(s)))
    pub = p["lieu"].str.extract(r"\|([AE])$")[0].fillna("")
    cle = pd.DataFrame({"type": p["type"], "f": p["finess"], "c": p["commune"], "n": nom, "a": adr, "p": pub})
    dbl = cle[cle.duplicated(["type", "f", "c", "n", "a"], keep=False)]
    publics = dbl.groupby(["type", "f", "c", "n", "a"])["p"].nunique()
    vrais = int((publics == 1).sum())
    par_public = int((publics > 1).sum())
    JOURNAL.controle("Structures en double, même type, même numéro FINESS, même commune, même nom et même adresse "
                     "(attendu, aucune)", f"{vrais} paires ; {par_public} paires d'un CMP pour adultes et d'un CMP pour "
                     f"enfants au même lieu, deux structures à vérifier")
    return vrais, par_public


def fusion_meme_adresse(lieux: pd.DataFrame, cat_finess: pd.Series | None = None,
                        noms_communes: pd.Series | None = None) -> tuple[pd.DataFrame, int]:
    """Une même structure déclarée deux fois (« CMP Le Petit Nice » et « CMP Petit Nice - 05G05 » à Embrun, le même CMP du ROR
    avec et sans numéro de rue) est réuni en un seul (constat du 13 octobre 2026, Bas-Rhin, vérifié sur toute la
    France). Deux lieux du même type sont réunis quand ils ont le même établissement gestionnaire (entité juridique), la
    même commune, la même rue et le même public, le même numéro ou un numéro absent d'un côté, le même nom à des mots
    descriptifs près sans code de secteur ni public différents, que l'un vient du ROR seul ou que les deux sont une double
    inscription dans FINESS, et que leurs numéros FINESS sont égaux ou que l'un est celui d'un hôpital. Audit du 13 octobre
    2026, une règle plus large réunissait à tort des foyers distincts d'une même association. Les
    numéros FINESS de la structure absorbée restent attachés à la structure gardée. Renvoie les structures et le nombre de structures réunies."""
    x = lieux.copy()
    if "finess_absorbes" not in x:
        x["finess_absorbes"] = None
    # voie aux abréviations développées (« CHE DE LUGUEL » et « CHEMIN DE LUGUEL », foyer de Limoux décrit deux fois
    # par le ROR, constat du 29 octobre 2026)
    adr = (x["adresse"].fillna("").map(lambda s: _simple(voie_developpee(s))) if "adresse" in x
           else pd.Series("", index=x.index))
    num = adr.str.extract(r"^(\d+)")[0]
    rue = adr.str.replace(r"^\d+\s*(?:bis|ter|b|t)?\s+", "", regex=True)
    pub = x["lieu"].str.extract(r"\|([AE])$")[0].fillna("")
    noms = x["nom"].fillna(x.get("nom_finess")).fillna("").map(_simple)
    mots = noms.map(lambda s: set(_distinctif(_MODALITES.sub(" ", s)).split()) - {"cmp", "cmpea"})
    codes = noms.map(lambda s: frozenset(_CODE_SECTEUR.findall(s)))
    publics = noms.map(_public_nom)
    # pour la première règle, le nom lisible est comparé aussi, débarrassé de la description de l'unité du ROR
    # (« Hébergement complet internat », « Prestations en milieu ordinaire, troubles du spectre de l'autisme ») : le ROR
    # décrit souvent une même structure par une unité par mode d'accueil ou par déficience (constat du 29 octobre
    # 2026). Les noms concordent quand le nom d'origine ou le nom lisible concorde. Dans le nom lisible, les mots du
    # libellé du type ne comptent pas (« Soins palliatifs : hospitalisation complète » devenu « Soins palliatifs » ne
    # dit rien de plus que son type, Saint-Priest-en-Jarez), et le nom d'un hôpital mis à la place d'un nom d'unité
    # trop vague ne compte pas (« CATTP » déclaré sous le numéro du CH de Roanne et affiché « CH de Roanne »).
    cat_num = cat_finess if cat_finess is not None else pd.Series(dtype=object)
    lisible = (x["nom_affiche"] if "nom_affiche" in x else pd.Series(None, index=x.index)).fillna(noms).map(_simple)
    etab = x["structure_nom"] if "structure_nom" in x else pd.Series(None, index=x.index, dtype=object)
    etab = etab.fillna(x["nom_finess"] if "nom_finess" in x else None).fillna("").map(_simple)
    nom_hopital = x["finess"].map(cat_num).isin(config.FINESS_HOPITAUX) & (lisible == etab) & (lisible != noms)
    lisible = lisible.where(~nom_hopital, noms)
    mots_type = x["type"].map({t_[0]: set(_simple(t_[1]).split()) for t_ in config.LIEUX_TYPES}).map(
        lambda s: s if isinstance(s, set) else set())
    formes = [(mots, codes, publics),
              (pd.Series([set(_distinctif(_MODALITES.sub(" ", s)).split()) - {"cmp", "cmpea"} - mt
                          for s, mt in zip(lisible, mots_type)], index=x.index),
               lisible.map(lambda s: frozenset(_CODE_SECTEUR.findall(s))), lisible.map(_public_nom))]
    # catégorie FINESS de chaque numéro (cat_num), pour reconnaître le numéro d'un hôpital sous lequel le ROR déclare
    # ses unités
    hopitaux = set(config.FINESS_CMP_PAR_NOM)
    cat = x["categorie_finess"] if "categorie_finess" in x else pd.Series(None, index=x.index, dtype=object)
    propres = _categories_propres()
    enfants_de = {t_[0]: t_[4]["parent"] for t_ in config.LIEUX_TYPES if t_[4].get("parent")}
    remplace = {}   # (type, lieu absorbé) -> lieu gardé
    a_retirer = []
    cand = x[(rue != "") & x["ej"].notna() & ~x["type"].isin(set(enfants_de))]
    # la structure gardée est celle inscrite dans FINESS sous une catégorie de son type, quand il y en a une (EHPAD Les
    # Carmes d'Aiglun gardé, et non l'unité « UHR - Centre des Carmes USLD » déclarée sous le numéro de l'USLD, 29 octobre
    # 2026). Sauf pour les types des listes vérifiées (CMP), dont les verdicts et l'empreinte tiennent à la clé gardée.
    from .structures_verifiees import FICHIER_ETAB
    verifies = set()
    if FICHIER_ETAB.exists():
        for ts in pd.read_csv(FICHIER_ETAB, sep=";", dtype=str)["types"].dropna():
            verifies |= {t.split(":")[0].strip() for t in ts.split(",")}
    for (ty, *_r), g in cand.groupby([cand["type"], cand["commune"], cand["ej"], rue[cand.index], pub[cand.index]]):
        if len(g) < 2:
            continue
        ordre = list(g.index)
        if ty not in verifies and propres.get(ty):
            ordre.sort(key=lambda j: cat[j] not in propres[ty])
        gardes = []
        for i in ordre:
            cible = None
            for k in gardes:
                n1, n2 = num[i], num[k]
                meme_num = isinstance(n1, str) and isinstance(n2, str) and n1 == n2
                num_ok = meme_num or not (isinstance(n1, str) and isinstance(n2, str))
                # vrais doublons seulement, l'un vient du ROR seul, ou les deux sont dans FINESS sous deux catégories
                # différentes (double inscription). Deux établissements de FINESS de la même catégorie à la même
                # adresse (un foyer de vie et un foyer d'hébergement, deux SESSAD) restent deux lieux.
                ror_seul = x.at[i, "provenance"] in ("ror", "ror_type") or x.at[k, "provenance"] in ("ror", "ror_type")
                ci, ck = cat[i], cat[k]
                # double inscription, deux catégories dont l'une n'est pas celle du type (un CMP enregistré aussi sous la
                # catégorie de son hôpital). Deux catégories propres au type (foyer de vie et foyer d'hébergement)
                # désignent deux structures distinctes.
                pr = propres.get(x.at[i, "type"], set())
                double = (isinstance(ci, str) and isinstance(ck, str) and ci != ck
                          and (ci not in pr or ck not in pr))
                # deux numéros FINESS différents désignent deux établissements distincts (un foyer de vie et un accueil
                # de jour de la même association, décrits par le ROR seul), sauf double inscription dans FINESS
                f1, f2 = x.at[i, "finess"], x.at[k, "finess"]
                autre_num = isinstance(f1, str) and isinstance(f2, str) and f1 != f2
                # sauf quand l'un des deux numéros est celui d'un hôpital (le ROR y déclare souvent ses CMP)
                if autre_num and not double and cat_num.get(f1) not in hopitaux and cat_num.get(f2) not in hopitaux:
                    continue
                # même nom à des mots descriptifs près (l'un contient tous les mots distinctifs de l'autre), sans
                # secteur ni public différents (« CATTP 13I11 » et « CATTP 13G26 », « CATTP pédo » et « CATTP »)
                meme_nom = any(bool(m[i]) and bool(m[k]) and (m[i] <= m[k] or m[k] <= m[i])
                               and not (c[i] and c[k] and c[i] != c[k]) and p[i] == p[k] for m, c, p in formes)
                if num_ok and meme_nom and (ror_seul or double):
                    cible = k
                    break
            if cible is None:
                gardes.append(i)
                continue
            a_retirer.append(i)
            remplace[(x.at[i, "type"], x.at[i, "lieu"])] = x.at[cible, "lieu"]
            nums = {str(v) for v in (x.at[i, "finess"], x.at[i, "finess_rapproche"] if "finess_rapproche" in x else None,
                                     x.at[i, "finess_absorbes"])
                    if isinstance(v, str) and v}
            deja = x.at[cible, "finess_absorbes"]
            x.at[cible, "finess_absorbes"] = ",".join(sorted(set((deja.split(",") if isinstance(deja, str) else [])
                                                                 + list(nums)))) or None
            if x.at[cible, "provenance"] != x.at[i, "provenance"]:
                x.at[cible, "provenance"] = "les_deux"
    # Un CMP décrit par le ROR seul sans adresse propre (placé à l'adresse de son hôpital, la commune tirée de son nom)
    # est la même structure qu'un CMP du même hôpital, du même public et de la même commune, décrit avec son adresse,
    # quand il est le seul de ce public dans la commune ou que leurs noms concordent (constat du 13 octobre 2026,
    # CMP du Vaucluse et du Var décrits deux fois par le ROR, sous l'ancien et le nouveau nom de pôle).
    x_ = x.drop(index=a_retirer)
    if "origine_commune" in x_:
        c_ = x_[x_["type"] == "lieu_cmp"]
        sans_adr = c_.index[(c_["provenance"] == "ror") & (c_["origine_commune"] == "nom") & c_["ej"].notna()]
        for i in sans_adr:
            if i in a_retirer:
                continue
            autres = c_[(c_["commune"] == c_.at[i, "commune"]) & (c_["ej"] == c_.at[i, "ej"]) & (pub[c_.index] == pub[i])
                        & (c_.index != i) & ~c_.index.isin(sans_adr)]
            if autres.empty:
                continue
            meme = [k for k in autres.index if mots[i] and mots[k] and (mots[i] <= mots[k] or mots[k] <= mots[i])
                    and not (codes[i] and codes[k] and codes[i] != codes[k]) and publics[i] == publics[k]]
            # sans nom concordant, seulement s'il est le seul CMP sans adresse de ce public dans la commune, que l'autre
            # est le seul avec adresse, et que leurs noms ne disent pas deux publics différents (gérontopsychiatrie)
            seul = sum(1 for j in sans_adr if c_.at[j, "commune"] == c_.at[i, "commune"]
                       and c_.at[j, "ej"] == c_.at[i, "ej"] and pub[j] == pub[i] and publics[j] == publics[i]) == 1
            k = meme[0] if len(meme) == 1 else (
                autres.index[0] if len(autres) == 1 and not meme and seul and publics[i] == publics[autres.index[0]]
                and not _SPECIALISE.search(noms[i]) else None)
            if k is None:
                continue
            a_retirer.append(i)
            remplace[(x.at[i, "type"], x.at[i, "lieu"])] = x.at[k, "lieu"]
            if x.at[k, "provenance"] == "finess":
                x.at[k, "provenance"] = "les_deux"
    # Deux CMP du même hôpital, du même public et de la même commune, dont les noms ne disent rien d'autre que la
    # commune, un sigle de pôle ou un code de secteur (« PPEA - CMPEA CAVAILLON » et « CMPI CAVAILLON - Secteur
    # PES »), l'un décrit par une seule base, sont la même structure décrite à deux adresses, l'ancienne et la
    # nouvelle (constats du 13 octobre 2026, Cavaillon, avenue de Verdun, et Tarare, rue Gaston-Salet).
    # Seulement quand ils sont exactement deux dans ce cas, hors antennes, permanences et consultations spécialisées.
    if noms_communes is not None:
        x_ = x.drop(index=a_retirer)
        c_ = x_[(x_["type"] == "lieu_cmp") & x_["ej"].notna()]
        com_mots = c_["commune"].map(noms_communes).fillna("").map(lambda s: set(_simple(s).split()))
        reste_ = {i: {w for w in mots[i] - com_mots[i] - _MOTS_POLE
                      if not _SIGLE_COURT.match(w) or w in _MOTS_LIEU} - {c.replace(" ", "") for c in codes[i]} for i in c_.index}
        elig = [i for i in c_.index if not reste_[i] and not _ANTENNE.search(noms[i]) and not _SPECIALISE.search(noms[i])]
        # public du lieu, celui de sa clé, sinon celui que dit son nom (un CMP de FINESS seul n'a pas d'âges déclarés)
        pub_c = pd.Series({i: pub[i] or ("E" if publics[i][0] else "A" if re.search(r"\badultes?\b", noms[i]) else "?")
                           for i in elig}, dtype=object)
        cles_ = c_.loc[elig].groupby([c_.loc[elig, "ej"], c_.loc[elig, "commune"], pub_c,
                                      pd.Series([publics[i] for i in elig], index=elig).astype(str)]).groups
        for _k, idx in cles_.items():
            idx = list(idx)
            if len(idx) != 2:
                continue
            a, b = idx
            if codes[a] and codes[b] and codes[a] != codes[b]:
                continue
            pa, pb = x.at[a, "provenance"], x.at[b, "provenance"]
            # deux structures décrites par les deux bases, ou deux établissements de FINESS (souvent le CMP pour
            # adultes et le CMP pour enfants, à Mantes-la-Jolie ou Sainte-Maxime), restent deux
            if pa == pb:
                continue
            # la structure décrite par les deux bases est gardée, sinon celle de FINESS
            garde, part = (a, b) if (pa == "les_deux" or (pa == "finess" and pb != "les_deux")) else (b, a)
            # la structure retirée est une inscription de FINESS seul, ou une unité du ROR seul nommée d'après son
            # pôle (« PPEA - »), signe d'une description sous la nouvelle organisation. Deux unités du ROR nommées
            # seulement « CMP » à deux adresses restent deux structures.
            if not (x.at[part, "provenance"] == "finess" or _SIGLE_POLE.match(noms[part])):
                continue
            # une structure du ROR seul avec sa propre adresse donne l'adresse la plus récente
            if x.at[part, "provenance"] == "ror" and x.get("origine_commune", pd.Series(dtype=object)).get(part) == "unite":
                memes = x.index[x["type"].isin(enfants_de) & (x["lieu"] == x.at[garde, "lieu"])].tolist() + [garde]
                for col in ("adresse", "voie", "lat", "lon", "precision"):
                    if col in x:
                        x.loc[memes, col] = x.at[part, col]
            nums = {str(v) for v in (x.at[part, "finess"], x.at[part, "finess_absorbes"]) if isinstance(v, str) and v}
            if nums and x.at[part, "provenance"] == "finess":
                deja = x.at[garde, "finess_absorbes"]
                x.at[garde, "finess_absorbes"] = ",".join(sorted(set((deja.split(",") if isinstance(deja, str) else [])
                                                                     + list(nums))))
            a_retirer.append(part)
            remplace[(x.at[part, "type"], x.at[part, "lieu"])] = x.at[garde, "lieu"]
            x.at[garde, "provenance"] = "les_deux" if x.at[garde, "provenance"] != x.at[part, "provenance"] else \
                x.at[garde, "provenance"]
    x = x.drop(index=a_retirer)
    # les CMP pour adultes et pour enfants suivent la fusion de leur lieu « tous publics »
    return _suivre_parents(x, remplace), len(a_retirer)


def repartition_cmp(lieux: pd.DataFrame, niv: str) -> pd.DataFrame:
    """Par territoire, CMP en tout, pour adultes, pour enfants et adolescents, accueillant les deux publics, et au public
    non précisé (CMP connu de FINESS seul sans âges ni indice dans son nom). Adultes plus enfants moins les deux, plus
    les non précisés, redonne le total (constat du 12 octobre 2026 sur les CMP de l'Ain)."""
    c = lieux[lieux["type"] == "lieu_cmp"][["lieu", niv]] if niv != "fr" else         lieux[lieux["type"] == "lieu_cmp"][["lieu"]].assign(fr="FR")
    ad = set(lieux.loc[lieux["type"] == "lieu_cmp_adultes", "lieu"])
    en = set(lieux.loc[lieux["type"] == "lieu_cmp_enfants", "lieu"])
    c = c.assign(adultes=c["lieu"].isin(ad), enfants=c["lieu"].isin(en))
    c = c.assign(les_deux=c["adultes"] & c["enfants"], non_precise=~c["adultes"] & ~c["enfants"])
    # antennes et permanences (en mairie, en CCAS, en maison de santé), comptées parmi les CMP et signalées comme
    # telles (décision du 13 octobre 2026, cas du Var)
    m = lieux["type"] == "lieu_cmp"
    noms = (lieux.loc[m, "nom"] if "nom" in lieux else pd.Series("", index=lieux.index[m])).fillna(
        lieux.loc[m, "nom_finess"] if "nom_finess" in lieux else "").fillna("")
    c = c.assign(antennes=noms.map(_simple).str.contains(_ANTENNE).reindex(c.index).fillna(False))
    g = c.groupby(niv if niv != "fr" else "fr")
    out = pd.DataFrame({"cmp": g.size(), "adultes": g["adultes"].sum(), "enfants": g["enfants"].sum(),
                        "les_deux": g["les_deux"].sum(), "non_precise": g["non_precise"].sum(),
                        "antennes": g["antennes"].sum()}).astype(int)
    out.index.name = "code"
    return out


def concordance_sae(L: dict, sae: dict | None, ref) -> pd.DataFrame | None:
    """CMP recensés ici (FINESS et ROR réunis) confrontés aux CMP que les établissements déclarent à la SAE de la DREES,
    psychiatrie générale (adultes) et infanto-juvénile (enfants et adolescents), par département et par région
    (demande du 12 octobre 2026, vérifier par d'autres sources). La SAE range tous les CMP d'un établissement
    dans le département de son siège, les écarts départementaux tiennent donc en partie aux établissements qui
    gèrent des CMP dans un département voisin, la comparaison régionale les efface en grande partie."""
    if not L or not sae or not isinstance(sae.get("cmp_disciplines"), pd.DataFrame):
        return None
    s = sae["cmp_disciplines"].rename(columns={"GEN": "sae_adultes", "INF": "sae_enfants"})
    s.index.name = "code"
    ur = L.get("unites_cmp_ror")
    if isinstance(ur, pd.Series):
        s = s.join(ur.rename("unites_ror"), how="outer").fillna(0)
    lignes = []
    dep_reg = ref.deps.set_index("code")["reg"]
    for niv in ("dep", "reg", "fr"):
        r = repartition_cmp(L["lieux"], niv)
        if niv == "dep":
            ss = s
        elif niv == "reg":
            ss = s.groupby(s.index.map(dep_reg)).sum()
        else:
            ss = s.sum().to_frame("FR").T
        t = r.join(ss, how="outer").fillna(0)
        t.index.name = "code"
        t["sae_cmp"] = t.get("sae_adultes", 0) + t.get("sae_enfants", 0)
        t["ecart_relatif"] = np.where(t["sae_cmp"] > 0, (t["cmp"] - t["sae_cmp"]) / t["sae_cmp"].where(t["sae_cmp"] > 0), np.nan)
        lignes.append(t.reset_index().assign(niveau=niv))
    out = pd.concat(lignes, ignore_index=True)
    for niv, lab in (("dep", "départements"), ("reg", "régions")):
        x = out[(out["niveau"] == niv) & out["ecart_relatif"].notna()]
        fr = out[out["niveau"] == "fr"].iloc[0]
        JOURNAL.controle(f"CMP recensés ici et CMP déclarés à la SAE, {lab}",
                         f"{int((x['ecart_relatif'].abs() <= .2).sum())} {lab} sur {len(x)} à 20 % près, "
                         f"France {int(fr['cmp'])} ici, {int(fr['sae_cmp'])} à la SAE "
                         f"({int(fr['sae_adultes'])} adultes, {int(fr['sae_enfants'])} enfants)")
    out["concordance"] = out["ecart_relatif"].map(niveau_concordance)
    return out


def concordance_cattp(L: dict, sae: dict | None, ref) -> pd.DataFrame | None:
    """CATTP recensés ici (FINESS et ROR réunis) confrontés aux CATTP que les établissements déclarent à la SAE,
    psychiatrie générale et infanto-juvénile, par département, région et France (16 octobre 2026). Même lecture que
    pour les CMP, la SAE range les CATTP d'un établissement dans le département de son siège."""
    if not L or not sae or not isinstance(sae.get("cattp_disciplines"), pd.DataFrame):
        return None
    s = sae["cattp_disciplines"].rename(columns={"GEN": "sae_cattp_adultes", "INF": "sae_cattp_enfants"})
    for c in ("sae_cattp_adultes", "sae_cattp_enfants"):
        if c not in s:
            s[c] = 0
    s = s[["sae_cattp_adultes", "sae_cattp_enfants"]]
    x = L["lieux"]
    x = x[x["type"] == "lieu_cattp"]
    dep_reg = ref.deps.set_index("code")["reg"]
    lignes = []
    for niv in ("dep", "reg", "fr"):
        ici = x.groupby(niv).size() if niv != "fr" else pd.Series({"FR": len(x)})
        ss = s if niv == "dep" else s.groupby(s.index.map(dep_reg)).sum() if niv == "reg" else s.sum().to_frame("FR").T
        t = ss.join(ici.rename("cattp"), how="outer").fillna(0)
        t.index.name = "code"
        t["sae_cattp"] = t["sae_cattp_adultes"] + t["sae_cattp_enfants"]
        t["ecart_relatif"] = np.where(t["sae_cattp"] > 0,
                                      (t["cattp"] - t["sae_cattp"]) / t["sae_cattp"].where(t["sae_cattp"] > 0), np.nan)
        lignes.append(t.reset_index().assign(niveau=niv))
    out = pd.concat(lignes, ignore_index=True)
    fr = out[out["niveau"] == "fr"].iloc[0]
    for niv, lab in (("dep", "départements"), ("reg", "régions")):
        y = out[(out["niveau"] == niv) & out["ecart_relatif"].notna()]
        JOURNAL.controle(f"CATTP recensés ici et CATTP déclarés à la SAE, {lab}",
                         f"{int((y['ecart_relatif'].abs() <= .2).sum())} {lab} sur {len(y)} à 20 % près, "
                         f"France {int(fr['cattp'])} ici, {int(fr['sae_cattp'])} à la SAE "
                         f"({int(fr['sae_cattp_adultes'])} adultes, {int(fr['sae_cattp_enfants'])} enfants)")
    out["concordance"] = out["ecart_relatif"].map(niveau_concordance)
    return out


CONCORDANCE = [(.2, "les sources concordent"), (.4, "écart modéré entre les sources"),
               (float("inf"), "écart important entre les sources")]


def niveau_concordance(ecart) -> str | None:
    """Niveau de concordance entre les CMP recensés ici et ceux déclarés à la SAE, d'après l'écart relatif."""
    if ecart is None or pd.isna(ecart):
        return None
    return next(lab for seuil, lab in CONCORDANCE if abs(ecart) <= seuil)


# Types que la SAE permet de recouper, par département (audit des chiffres du 30 octobre 2026, constats 2 et 4) : table
# de la SAE et discipline (GEN adultes, INF enfants et adolescents, None les deux). Les CMP et les CATTP sont des
# nombres déclarés par établissement, rangés au département de son siège ; les hôpitaux de jour se comptent par les
# sites qui déclarent des places d'hôpital de jour (un site peut porter plusieurs hôpitaux de jour, le compte de la SAE
# est donc un minimum).
SAE_RECOUPE = {"lieu_cmp_adultes": ("cmp_disciplines", "GEN"), "lieu_cmp_enfants": ("cmp_disciplines", "INF"),
               "lieu_cattp": ("cattp_disciplines", None), "lieu_hdj_psy_adultes": ("hdj_sites", "GEN"),
               "lieu_hdj_psy_enfants": ("hdj_sites", "INF")}
# Un département (ou une région) dont les bases inscrivent moins de la moitié des structures que la SAE y déclare
# n'a ni distance au plus proche ni nombre pour 100 000 publiés pour ce type, la mesure serait faite jusqu'aux
# structures des départements voisins (Haute-Vienne, aucun CATTP inscrit pour 6 déclarés, distance médiane de 50 km)
SAE_PART_MIN = .5


def _dep_finess(n: str) -> str:
    """Département d'un numéro FINESS, ses deux premiers caractères (2A et 2B pour la Corse), et outre-mer « 97 » suivi
    du quatrième chiffre (970100012, Guadeloupe 971 ; 9703 Guyane, 9704 La Réunion, 9706 Mayotte)."""
    n = str(n).strip().zfill(9)
    return "97" + n[3] if n.startswith("970") else n[:2]


def annee_source(source: str, adresse: str) -> int | None:
    """Année la plus récente que cite le nom d'une source (« guide Psycom, édition 2018 »), sinon son adresse web
    (« /2025-11/ »), None pour une page actuelle non datée. L'année du nom prime : l'adresse d'un guide de 2018 peut
    porter l'année de son dépôt en ligne."""
    for t in (source, adresse):
        ys = [int(y) for y in re.findall(r"(?<!\d)(20[0-4]\d)(?!\d)", str(t or ""))]
        if ys:
            return max(ys)
    return None


def etablissements_sources_recentes(lignes: pd.DataFrame, aujourd: int | None = None) -> set:
    """Entités juridiques dont toutes les lignes vérifiées s'appuient sur une source de moins de
    config.VERIFICATION_SOURCE_ANS ans (décision 1 du 16 novembre 2026) : l'inventaire de l'ARS PACA de 2017 ne prouve
    pas qu'un CMP reçoit encore en 2026 (Châteaurenard, fermé en 2024, y figurait)."""
    import datetime as dt
    aujourd = aujourd or dt.date.today().year
    if lignes is None or lignes.empty:
        return set()
    an = [annee_source(s, a) for s, a in zip(lignes["source"], lignes["adresse_source"])]
    vieux = pd.Series([a is not None and a < aujourd - config.VERIFICATION_SOURCE_ANS for a in an], index=lignes.index)
    return set(lignes["ej"]) - set(lignes.loc[vieux, "ej"])


def manques_sae(L: dict, sae: dict | None, ref) -> pd.DataFrame | None:
    """Pour chaque type que la SAE permet de recouper, chaque département et chaque région, structures inscrites dans
    FINESS et le ROR face aux structures déclarées à la SAE, et « manque » quand les bases en inscrivent moins de
    SAE_PART_MIN de ce que la SAE déclare. Les intercommunalités suivent le département qui porte l'essentiel de leur
    population. Colonnes type, niveau, code, inscrites, declarees, manque."""
    if not L or not sae:
        return None
    x = L["lieux"]
    dep_reg = ref.deps.set_index("code")["reg"]
    lignes = []
    for tid, (table, dis) in SAE_RECOUPE.items():
        s = sae.get(table)
        if table == "hdj_sites":
            if not isinstance(s, dict) or dis not in s:
                continue
            dec = pd.Series([_dep_finess(n) for n in s[dis]], dtype=object).value_counts()
        else:
            if not isinstance(s, pd.DataFrame):
                continue
            cols = [dis] if dis else [c for c in ("GEN", "INF") if c in s]
            if not all(c in s for c in cols):
                continue
            dec = s[cols].sum(axis=1)
        dec = dec[dec > 0].astype(float)
        ins = x[x["type"] == tid].groupby("dep").size().astype(float)
        for niv, d_, i_ in (("dep", dec, ins), ("reg", dec.groupby(dec.index.map(dep_reg)).sum(),
                                                   ins.groupby(ins.index.map(dep_reg)).sum())):
            t = pd.DataFrame({"declarees": d_}).join(i_.rename("inscrites"), how="left").fillna(0)
            t = t[t.index.notna()]
            lignes.append(t.assign(type=tid, niveau=niv, manque=t["inscrites"] < SAE_PART_MIN * t["declarees"])
                          .rename_axis("code").reset_index())
    if not lignes:
        return None
    out = pd.concat(lignes, ignore_index=True)
    # décision 1 du chantier des structures (docs/structures/decisions_2026-11-16.md), acceptée le 16 novembre 2026 : un
    # territoire dont 90 % au moins des CMP déclarés à la SAE relèvent d'établissements vérifiés sur leurs propres sources
    # récentes n'est pas masqué, la SAE comptant des unités de secteur et non des lieux (constat C11)
    if config.MASQUAGE_PAR_VERIFICATION:
        from . import structures_verifiees as sv
        e_, s_ = sv.charger()
        recents = etablissements_sources_recentes(s_)
        e_ = e_[e_["ej"].isin(recents)]
        publics = {}
        for ej_, types_ in zip(e_["ej"], e_["types"]):
            for t_ in str(types_).split(","):
                t_, _, p_ = t_.strip().partition(":")
                if t_ == "lieu_cmp":
                    publics.setdefault(ej_, set()).update({p_} if p_ else {"adultes", "enfants"})
        # la part se mesure sur les CMP que chaque établissement déclare à la SAE, pas sur les CMP inscrits : un
        # établissement sans aucun CMP inscrit compte aussi (Haut-Rhin, 16 novembre 2026 : le CH de Rouffach, vérifié,
        # portait 12 des 13 CMP pour adultes inscrits, mais le GHR Mulhouse Sud-Alsace et les Hôpitaux civils de Colmar
        # en déclarent 15 à la SAE sur 34, aucun inscrit, et Saint-Louis aurait été montrée sans CMP)
        etab = sae.get("etablissements")
        if isinstance(etab, pd.DataFrame) and len(etab):
            # département lu dans le numéro FINESS, sauf outre-mer où il n'en donne que deux chiffres (« 98 » pour
            # Mayotte, 976) : alors celui du siège déclaré à la SAE (relecture du 17 novembre 2026)
            dep_f = pd.Series([_dep_finess(f) for f in etab.index], index=etab.index)
            dep_s = (etab["dep_siege"].astype("string").str.strip() if "dep_siege" in etab
                     else pd.Series(pd.NA, index=etab.index, dtype="string"))
            om = dep_f.astype(str).str.match(r"^9[78]") & dep_s.fillna("").str.match(r"^9[78]\d$")
            et = etab.assign(dep=dep_f.where(~om, dep_s))
            for tid, col in (("lieu_cmp_adultes", "sae_adultes"), ("lieu_cmp_enfants", "sae_enfants")):
                pub = tid.rsplit("_", 1)[1]
                ver = [pub in publics.get(str(j), set()) or pub in publics.get(str(f), set())
                       for f, j in zip(et.index, et["ej_sae"])]
                d_ = et.assign(dec=et[col].fillna(0), dec_ver=et[col].fillna(0).where(ver, 0))
                for niv, cle in (("dep", d_["dep"]), ("reg", d_["dep"].map(dep_reg))):
                    g = d_.groupby(cle)[["dec", "dec_ver"]].sum()
                    part = (g["dec_ver"] / g["dec"]).where(g["dec"] > 0)
                    sel = ((out["type"] == tid) & (out["niveau"] == niv)
                           & out["code"].map(part).ge(config.PART_VERIFIEE_MIN))
                    out.loc[sel, "manque"] = False
    # intercommunalités, d'après le département qui porte l'essentiel de leur population
    dep_m = out[(out["niveau"] == "dep") & out["manque"]]
    e = ref.epci[["code", "dep"]]
    ep = [e[e["dep"] == r.code].assign(type=r.type, niveau="epci", inscrites=np.nan, declarees=np.nan, manque=True,
                                       dep_manque=r.code)[["code", "type", "niveau", "inscrites", "declarees", "manque",
                                                           "dep_manque"]]
          for r in dep_m.itertuples()]
    if ep:
        out = pd.concat([out] + ep, ignore_index=True)
    lab = {t[0]: t[1] for t in config.LIEUX_TYPES}
    m = out[(out["niveau"] == "dep") & out["manque"]]
    JOURNAL.controle("Structures inscrites face à la SAE, départements où les bases en inscrivent moins de la moitié "
                     "(distance et nombre pour 100 000 non publiés pour ce type)",
                     "; ".join(f"{_court(lab[t], t)} {len(g)} ({', '.join(f'{c} {int(i)} pour {int(d)}' for c, i, d in zip(g['code'], g['inscrites'], g['declarees']))})"
                               for t, g in m.groupby("type")) or "aucun")
    return out


def masquer_manques(L: dict, ref) -> dict:
    """Retire des distances par territoire (L["distances"]) les mesures des territoires où les bases inscrivent moins de
    la moitié des structures que la SAE déclare (manques_sae, rangé dans L["manques_sae"]). La distance médiane et les
    parts à plus de 20 et 30 km y deviennent vides. Renvoie la limite à ajouter à config.LIMITES (une seule, « manque_sae »,
    avec une phrase par territoire qui nomme chaque type touché et ses nombres), sa phrase courte et les alias des
    indicateurs."""
    m = L.get("manques_sae")
    if not isinstance(m, pd.DataFrame) or not m["manque"].any():
        return {}
    m = m[m["manque"]]
    for niv in ("epci", "dep", "reg"):
        d = (L.get("distances") or {}).get(niv)
        if not isinstance(d, pd.DataFrame):
            continue
        cle_m = set(zip(m.loc[m["niveau"] == niv, "type"], m.loc[m["niveau"] == niv, "code"]))
        touche = [(t, c) in cle_m for t, c in zip(d["type"], d["code"])]
        d.loc[touche, ["distance_mediane_km", "part_plus_20_km", "part_plus_30_km"]] = np.nan
    lab = {t[0]: t[1] for t in config.LIEUX_TYPES}
    noms_dep = ref.deps.set_index("code")["nom"]
    # une seule limite pour tous les types et une seule phrase par territoire, qui nomme chaque type touché avec ses
    # nombres (remarque du 30 octobre 2026, trois « À savoir » presque identiques s'empilaient dans la fiche de Limoges)
    noms = {"lieu_cattp": "CATTP", "lieu_cmp_adultes": "CMP pour adultes", "lieu_cmp_enfants": "CMP pour enfants et adolescents",
            "lieu_hdj_psy_adultes": "hôpitaux de jour en psychiatrie pour adultes",
            "lieu_hdj_psy_enfants": "hôpitaux de jour en psychiatrie pour enfants et adolescents"}

    def morceau(tid, dec, ins):
        dec, ins = int(dec), int(ins)
        inscrits = "aucun inscrit" if not ins else f"{nombre(ins)} inscrit{'s' if ins > 1 else ''}"
        if tid.startswith("lieu_hdj"):
            return (f"les {noms[tid]} ({nombre(dec)} site{'s' if dec > 1 else ''} qui déclare{'nt' if dec > 1 else ''} des "
                    f"places, {inscrits})")
        return f"les {noms.get(tid, _court(lab[tid], tid))} ({nombre(dec)} déclaré{'s' if dec > 1 else ''}, {inscrits})"

    def liste(xs):
        return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " et " + xs[-1]

    terr = {}
    for (niv, code), g in m.groupby(["niveau", "code"]):
        if niv == "epci":
            deps = sorted(set(g["dep_manque"]))
            src = m[(m["niveau"] == "dep") & m["code"].isin(deps) & m["type"].isin(g["type"])]
            ou = (f", dans le département qui porte l'essentiel de la population de ce territoire "
                  f"({noms_dep.get(deps[0], deps[0])})")
        else:
            src, ou = g, ""
        items = [morceau(r.type, r.declarees, r.inscrites) for r in src.sort_values("type").itertuples()]
        # une région porte la clé « reg: » suivie de son code, qui sinon se confondrait avec un département (région 03
        # Guyane et département 03 Allier, 01 Guadeloupe et Ain, 04 La Réunion et Alpes-de-Haute-Provence)
        terr[f"reg:{code}" if niv == "reg" else code] = ("FINESS et le Répertoire opérationnel des ressources inscrivent moins de la moitié des structures que "
                      "les établissements déclarent à la statistique annuelle des établissements de santé (SAE) pour "
                      f"{liste(items)}{ou}. Leur distance et leur nombre pour 100 000 n'y sont pas publiés.")
    limites_ = {"manque_sae": {
        "risque": "recensement incomplet",
        "nom": "Structures déclarées à la SAE et absentes des bases",
        "court": "Structures déclarées à la SAE et absentes des bases, distance et nombre non publiés.",
        "texte": ("Dans quelques départements, la statistique annuelle des établissements de santé (SAE), que remplit "
                  "chaque établissement, déclare bien plus de CMP, de CATTP ou de sites d'hôpital de jour que FINESS et le "
                  "Répertoire opérationnel des ressources n'en inscrivent (moins de la moitié). Une distance mesurée là "
                  "irait jusqu'aux structures des départements voisins, elle n'est donc pas publiée, pas plus que le "
                  "nombre pour 100 000. La SAE range les structures d'un établissement au département de son siège."),
        "sources": [config.SRC_DREES_SAE],
        "territoires": terr}}
    alias = {f"{p}{tid}": "manque_sae" for tid in m["type"].unique() for p in ("lieux_", "dist_")}
    JOURNAL.controle("Distances retirées faute de structures inscrites (départements, intercommunalités, régions)",
                     ", ".join(f"{_court(lab[t], t)} {int((g['niveau'] == 'dep').sum())} départements, "
                               f"{int((g['niveau'] == 'epci').sum())} intercommunalités, {int((g['niveau'] == 'reg').sum())} régions"
                               for t, g in m.groupby("type")))
    return {"limites": limites_, "alias": alias}


def masquer_distances_communes(L: dict, ref) -> None:
    """Distances des communes des départements touchés (manques_sae) rendues vides pour le type, juste avant
    l'écriture des fichiers et des rapports, une fois faites les analyses nationales qui s'appuient sur elles."""
    m = L.get("manques_sae")
    dc = L.get("distances_communes")
    if not isinstance(m, pd.DataFrame) or not isinstance(dc, pd.DataFrame):
        return
    com_dep = ref.communes.set_index("code")["dep"].reindex(dc.index)
    for r in m[(m["niveau"] == "dep") & m["manque"]].itertuples():
        if r.type in dc.columns:
            dc.loc[(com_dep == r.code).to_numpy(), r.type] = np.nan


def concordance_etablissements(L: dict, sae: dict | None, fin: pd.DataFrame | None = None) -> pd.DataFrame | None:
    """CMP et CATTP confrontés hôpital par hôpital (entité juridique) aux déclarations de la SAE (13 octobre 2026).
    Un écart désigne un établissement précis à vérifier. Les CMP d'un hôpital sont ceux que FINESS ou le ROR
    rattachent à son entité juridique, où qu'ils soient. Écart toléré, 20 % ou un CMP."""
    if not L or not sae or not isinstance(sae.get("etablissements"), pd.DataFrame):
        return None
    x = L["lieux"]
    x = x[x["ej"].notna()]

    def n(tid):
        return x[x["type"] == tid].groupby("ej").size()
    ici = pd.DataFrame({"ici_cmp": n("lieu_cmp"), "ici_adultes": n("lieu_cmp_adultes"),
                        "ici_enfants": n("lieu_cmp_enfants"), "ici_cattp": n("lieu_cattp")})
    s = sae["etablissements"].copy()
    if "fi" == s.index.name:
        # chaque établissement de la SAE ramené à son entité juridique actuelle dans FINESS, l'ancienne sinon
        ej_actuelle = fin.set_index("nofinesset")["nofinessej"] if fin is not None else pd.Series(dtype=str)
        ej_actuelle = ej_actuelle[~ej_actuelle.index.duplicated()]
        s["ej"] = (pd.Series(s.index.map(ej_actuelle), index=s.index).fillna(s["ej_sae"]) if len(ej_actuelle)
                   else s["ej_sae"])
        nom = s.groupby("ej")["nom_sae"].first()
        dep = s.groupby("ej")["dep_siege"].first()
        s = s.groupby("ej")[["sae_adultes", "sae_enfants", "sae_cattp"]].sum()
        s["nom_sae"], s["dep_siege"] = nom, dep
    t = s.join(ici, how="outer")
    ur = L.get("unites_cmp_ror_ej")
    if isinstance(ur, pd.Series):
        t = t.join(ur.rename("unites_ror"), how="left")
    for c in ("sae_adultes", "sae_enfants", "sae_cattp", "ici_cmp", "ici_adultes", "ici_enfants", "ici_cattp", "unites_ror"):
        if c in t:
            t[c] = t[c].fillna(0).astype(int)
    t["sae_cmp"] = t["sae_adultes"] + t["sae_enfants"]
    # un hôpital qui ne déclare aucun CMP à la SAE et n'en a aucun ici n'est pas comparé
    t = t[(t["sae_cmp"] > 0) | (t["ici_cmp"] > 0)].copy()
    t["ecart"] = t["ici_cmp"] - t["sae_cmp"]
    tol = (t["sae_cmp"] * .2).clip(lower=1)
    t["statut"] = np.where(t["sae_cmp"] == 0, "absent de la SAE",
                           np.where(t["ecart"].abs() <= tol, "concorde",
                                    np.where(t["ecart"] < 0, "moins ici qu'à la SAE", "plus ici qu'à la SAE")))
    # CATTP, même règle, seulement pour les hôpitaux qui en déclarent à la SAE ou en ont ici
    tol_c = (t["sae_cattp"] * .2).clip(lower=1)
    ec = t["ici_cattp"] - t["sae_cattp"]
    t["statut_cattp"] = np.where((t["sae_cattp"] == 0) & (t["ici_cattp"] == 0), None,
                                 np.where(t["sae_cattp"] == 0, "aucun CATTP déclaré à la SAE",
                                          np.where(ec.abs() <= tol_c, "concorde",
                                                   np.where(ec < 0, "moins ici qu'à la SAE", "plus ici qu'à la SAE"))))
    nom_fin = x.drop_duplicates("ej").set_index("ej")["nom_finess"] if "nom_finess" in x else pd.Series(dtype=str)
    t["nom"] = t["nom_sae"].fillna(nom_fin.reindex(t.index))
    t.index.name = "ej"
    v = t["statut"].value_counts()
    moins, plus = "moins ici qu'à la SAE", "plus ici qu'à la SAE"
    JOURNAL.controle("CMP confrontés à la SAE hôpital par hôpital",
                     f"{int(v.get('concorde', 0))} hôpitaux concordants, {int(v.get(moins, 0))} avec moins de CMP ici, "
                     f"{int(v.get(plus, 0))} avec plus, {int(v.get('absent de la SAE', 0))} absents de la SAE")
    vc = t["statut_cattp"].value_counts()
    JOURNAL.controle("CATTP confrontés à la SAE hôpital par hôpital",
                     f"{int(vc.get('concorde', 0))} hôpitaux concordants, {int(vc.get(moins, 0))} avec moins de CATTP "
                     f"ici, {int(vc.get(plus, 0))} avec plus, {int(vc.get('aucun CATTP déclaré à la SAE', 0))} sans aucun CATTP "
                     f"déclaré à la SAE")
    return t.reset_index()


def phrase_publics_cmp(r) -> str:
    """Phrase qui décompose les CMP d'un territoire par public, dont le total se retrouve."""
    from .lecture import nombre
    s = (f"{nombre(r['adultes'])} accueillent des adultes et {nombre(r['enfants'])} des enfants et adolescents"
         + (f", dont {nombre(r['les_deux'])} les deux publics" if r["les_deux"] else "") + ".")
    if r["non_precise"] == 1:
        s += " Pour l'un d'eux, aucune source ne précise le public."
    elif r["non_precise"]:
        # sans dire d'où ils viennent : FINESS seul, ou les sources de leur établissement (relecture du 21 novembre
        # 2026, 11 des 31 venaient des établissements)
        s += f" Pour {nombre(r['non_precise'])} d'entre eux, aucune source ne précise le public."
    a = int(r.get("antennes", 0) or 0)
    if a == 1:
        s += " L'un d'eux est une antenne ou une permanence (en mairie, en CCAS ou en maison de santé, par exemple)."
    elif a:
        s += (f" {nombre(a)} d'entre eux sont des antennes ou des permanences (en mairie, en CCAS ou en maison de "
              f"santé, par exemple).")
    return s


def controle_route_cmp(ar, L: dict, ref) -> dict | None:
    """Communes où le temps de route de l'INSEE vers la psychiatrie ambulatoire (BPE, D109) contredit la distance au CMP
    le plus proche de nos structures (temps moyen au-delà de config.ROUTE_CMP_PENTE minutes par km à vol d'oiseau plus
    config.ROUTE_CMP_MARGE minutes). Témoin, la même règle sur les urgences (D106), où les deux sources concordent,
    journalisée à côté. Cause probable, la BPE ne compterait que les CMP inscrits sous leur
    propre catégorie dans FINESS (note docs/note_valeurs_aberrantes_2026-10-28.md, à confirmer sur la documentation de
    l'INSEE). Résultat gardé dans L["incoherence_route_cmp"] pour le rapport, communes en cause dans
    L["route_cmp_contredites"] pour analyses.temps_acces."""
    dist = (L or {}).get("distances_communes")
    if not ar or not isinstance(dist, pd.DataFrame) or "lieu_cmp" not in dist:
        return None
    c = ar["communes"]
    pop = ref.communes.set_index("code")["pop"]

    def contredit(eq, type_lieu):
        code = next((d["code"] for d in ar["defs"] if d["id"] == eq), None)
        if code is None or type_lieu not in dist:
            return None, None
        x = c[c["typeeq_id"] == code]
        t = (x["pd"] / x["pop_calcule"].where(x["pop_calcule"] > 0)).groupby(x["depcom"]).first()
        j = pd.DataFrame({"temps": t, "km": dist[type_lieu]}).dropna()
        return j, j["temps"] > config.ROUTE_CMP_PENTE * j["km"] + config.ROUTE_CMP_MARGE

    j, m = contredit("psychiatrie_ambulatoire", "lieu_cmp")
    if j is None:
        return None
    com = ref.communes.set_index("code").reindex(j.index[m])
    r = {"communes": int(m.sum()), "habitants": float(com["pop"].fillna(0).sum()),
         "part_habitants": float(com["pop"].fillna(0).sum() / pop.reindex(j.index).fillna(0).sum()),
         "departements": int(com["dep"].nunique()), "comparees": len(j),
         "rho_spearman": float(j["temps"].corr(j["km"], method="spearman")) if len(j) > 50 else np.nan}
    ju, mu = contredit("urgences", "lieu_urgences")
    if ju is not None:
        r["part_habitants_temoin"] = float(pop.reindex(ju.index[mu]).fillna(0).sum() / pop.reindex(ju.index).fillna(0).sum())
    L["incoherence_route_cmp"] = r
    # communes où le temps contredit la distance, pour ne plus publier le temps des territoires touchés
    L["route_cmp_contredites"] = j.index[m]
    JOURNAL.controle(f"Temps de route de l'INSEE vers la psychiatrie ambulatoire, communes où il dépasse "
                     f"{config.ROUTE_CMP_PENTE} minutes par km jusqu'au CMP le plus proche, plus {config.ROUTE_CMP_MARGE} "
                     f"minutes",
                     f"{nombre(r['communes'])} communes sur {nombre(r['comparees'])}, {nombre(r['habitants'])} habitants "
                     f"({nombre(100 * r['part_habitants'], 1)} %), {r['departements']} départements, corrélation de rang "
                     f"{nombre(r['rho_spearman'], 2)}"
                     + (f", témoin des urgences {nombre(100 * r['part_habitants_temoin'], 2)} % des habitants"
                        if "part_habitants_temoin" in r else ""))
    return r


def population_concernee_visible() -> bool:
    """Les chiffres de la population concernée entrent au catalogue (fiches, atlas, Explorer) seulement dans une
    exécution en brouillon, jamais publiée, tant que l'auteur n'a pas validé leur présentation sur maquette
    (config.POPULATION_CONCERNEE_PUBLIEE, rien de visible sans maquette validée)."""
    return bool(config.POPULATION_CONCERNEE_PUBLIEE) or config.RESULTATS.name == "brouillons"


def public_du_type(tid: str) -> str | None:
    """Clé du public que sert un type de structure (config.PUBLICS_CONCERNES), une seule définition : le dénominateur
    du registre (densités publiées) d'abord, puis config.PUBLIC_DES_LIEUX ; None pour un type qui sert tous les
    habitants ou qui est écarté (config.PUBLIC_EXCLUS)."""
    if tid in config.PUBLIC_EXCLUS:
        return None
    parts = tuple(lieux_profil.denominateur(tid)[0])
    if parts:
        return config.PUBLIC_DU_DENOMINATEUR.get(parts)
    return config.PUBLIC_DES_LIEUX.get(tid)


def libelle_du_public(cle: str, periode=None) -> str:
    """Nom d'un public concerné dans les fichiers, le même que sur les fiches (« mères des enfants nés de 2017 à
    2022 », contre-relecture du 10 novembre 2026)."""
    if cle == "naissances":
        return ("mères des enfants nés " + (f"de {periode[0]} à {periode[1]}" if periode
                                             else "entre les deux derniers recensements"))
    return config.PUBLICS_CONCERNES[cle][1]


def population_concernee(L: dict, ref, publics: pd.DataFrame | None) -> pd.DataFrame | None:
    """Distance à la structure la plus proche et nombre de structures, pour tous les habitants et pour le public que
    sert la structure (config.PUBLIC_DES_LIEUX : naissances, au domicile de la mère, pour une maternité, moins de
    15 ans pour un CAMSP...). Par territoire (intercommunalité, département, région, France) et par type : distance médiane et part à
    plus de 30 km, pondérées par les habitants (population du référentiel, comme les distances publiées) puis par le
    public (INSEE, communes). Un nombre de structures ou une distance dit où elles sont, pas si elles suffisent.
    Relecture indépendante du 9 novembre 2026 : seuls les types recensés presque partout (L["couverture"]) ; une
    distance retirée du site (structures déclarées à la SAE et absentes des bases) l'est ici aussi ; Mayotte, sans
    recensement, sort des deux pondérations ; les densités restent celles du registre (taux_publics), calculées une
    seule fois."""
    if not L or publics is None or L.get("distances_communes") is None:
        return None
    from .analyses import mediane_ponderee
    dist = L["distances_communes"]
    com = ref.communes.set_index("code").reindex(dist.index)
    pub = publics.reindex(dist.index)
    # communes sans recensement (Mayotte) hors des deux pondérations, pour comparer le même champ
    champ = pub["pop"].notna().to_numpy() if "pop" in pub else np.ones(len(dist), bool)
    tous = np.where(champ, com["pop"].astype(float).fillna(0).to_numpy(), 0.0)
    pub = pub.fillna(0)
    complets = set(L["couverture"].loc[L["couverture"]["complet"], "type"]) if "couverture" in L else set(dist.columns)
    publies = L.get("distances") or {}
    lignes = []
    for niv in ("epci", "dep", "reg", "fr"):
        grp = pd.Series("FR", index=dist.index) if niv == "fr" else com[niv]
        # distances que le site laisse vides (masquer_manques), laissées vides ici aussi
        pub_niv = publies.get(niv)
        vides = (set(map(tuple, pub_niv.loc[pub_niv["distance_mediane_km"].isna(), ["code", "type"]].to_numpy()))
                 if isinstance(pub_niv, pd.DataFrame) else set())
        for tid in dist.columns:
            cle = public_du_type(tid)
            if not cle or tid not in complets or cle not in pub:
                continue
            d_all = dist[tid].to_numpy(float)
            for code, idx in grp.groupby(grp).groups.items():
                m = dist.index.get_indexer(idx)
                d, wt, wp = d_all[m], tous[m], pub[cle].to_numpy(float)[m]
                if wt.sum() <= 0 or wp.sum() <= 0:
                    continue
                vide = (code, tid) in vides
                lignes.append({"niveau": niv, "code": code, "type": tid, "public": cle,
                               "libelle_public": libelle_du_public(cle, L.get("periode_naissances")),
                               "distance_mediane_km": np.nan if vide else mediane_ponderee(d, wt),
                               "distance_mediane_km_public": np.nan if vide else mediane_ponderee(d, wp),
                               "part_plus_30_km": np.nan if vide else float(wt[d > 30].sum() / wt.sum()),
                               "part_plus_30_km_public": np.nan if vide else float(wp[d > 30].sum() / wp.sum()),
                               "communes": int((wt > 0).sum()), "population": float(wt.sum()),
                               "population_public": float(wp.sum())})
    out = pd.DataFrame(lignes)
    if not out.empty:
        fr = out[(out["niveau"] == "fr") & (out["type"] == "lieu_maternite")]
        if len(fr):
            r = fr.iloc[0]
            JOURNAL.controle("Population concernée, maternité la plus proche, France entière hors Mayotte (distance "
                             "médiane, tous les habitants et domicile des mères des enfants nés entre les deux derniers recensements)",
                             f"{nombre(r['distance_mediane_km'], 1)} km et {nombre(r['distance_mediane_km_public'], 1)} km")
    return out


def escalier_distances(L: dict, ref, revenu_epci: pd.Series | None) -> pd.DataFrame | None:
    """Distance des habitants à la structure la plus proche selon le niveau de vie de leur intercommunalité. Les
    intercommunalités sont classées par revenu médian et réparties en dix groupes d'environ un dixième des habitants
    (même méthode que l'escalier social des densités), puis, dans chaque groupe, la distance médiane des habitants et
    la part à plus de 20 km sont calculées commune par commune. Types recensés presque partout seulement."""
    if not L or revenu_epci is None or revenu_epci.dropna().empty:
        return None
    from .analyses import deciles_population, mediane_ponderee
    dist = L["distances_communes"]
    ok = set(L["couverture"].loc[L["couverture"]["complet"], "type"])
    types = [t for t in lieux_profil.types_avec("indicateur") if t in ok and t in dist.columns]
    com = ref.communes.set_index("code").reindex(dist.index)
    pop = com["pop"].astype(float).fillna(0)
    par_epci = pop.groupby(com["epci"]).sum()
    rev = revenu_epci.reindex(par_epci.index)
    garde = rev.notna() & (par_epci > 0)
    dec = pd.Series(deciles_population(rev[garde], par_epci[garde]), index=rev[garde].index)
    d_com = com["epci"].map(dec)
    lignes = []
    for tid in types:
        for d in range(1, 11):
            m = (d_com == d).to_numpy()
            w, x = pop.to_numpy()[m], dist[tid].to_numpy()[m]
            if w.sum() <= 0:
                continue
            r = rev[dec.index[dec == d]]
            lignes.append({"type": tid, "decile": d, "niveau_de_vie_min": r.min(), "niveau_de_vie_max": r.max(),
                           "population": w.sum(), "distance_mediane_km": mediane_ponderee(x, w),
                           "part_plus_20_km": float(w[x > 20].sum() / w.sum())})
    return pd.DataFrame(lignes) if lignes else None


def _types_comparables(L: dict) -> list:
    """Types recensés presque partout, ceux qu'on compare entre territoires (registre, analyse « indicateur »)."""
    ok = set(L["couverture"].loc[L["couverture"]["complet"], "type"])
    return [t for t in lieux_profil.types_avec("indicateur") if t in ok and t in L["distances_communes"].columns]


def _par_epci(L: dict, ref, types):
    """Population et habitants-kilomètres (population de chaque commune fois sa distance) par intercommunalité."""
    dist = L["distances_communes"]
    com = ref.communes.set_index("code").reindex(dist.index)
    pop = com["pop"].astype(float).fillna(0)
    # vide pour une intercommunalité dont le territoire n'a aucune structure de ce type (lieux.distances)
    hk = dist[types].replace(np.inf, np.nan).mul(pop, axis=0)
    return pop.groupby(com["epci"]).sum(), hk.groupby(com["epci"]).sum(min_count=1)


def inegalites_distances(L: dict, ref, ctx_epci: pd.DataFrame | None, rng, cle: str = "toutes") -> dict | None:
    """Inégalités de distance aux structures de soins (demande du 12 octobre 2026).
    1. Selon le type de territoire, classes de densité de population des intercommunalités (mêmes classes que les
       professions), distance médiane des habitants, part à plus de 20 km, test de Kruskal-Wallis sur les distances
       médianes des intercommunalités avec sa taille d'effet (epsilon carré), correction de Benjamini-Hochberg.
    2. Selon le niveau de vie, indice de concentration des habitants-kilomètres, intercommunalités classées du plus
       modeste au plus aisé. Négatif quand l'éloignement pèse surtout sur les territoires modestes, positif quand il
       pèse sur les territoires aisés. Fourchette à 95 % par bootstrap des intercommunalités."""
    if not L or ctx_epci is None:
        return None
    from scipy import stats
    from .analyses import CLASSES_DENSITE, benjamini_hochberg, indice_concentration, mediane_ponderee, tirage
    types = _types_comparables(L)
    if not types:
        return None
    dist = L["distances_communes"]
    com = ref.communes.set_index("code").reindex(dist.index)
    pop_c = com["pop"].astype(float).fillna(0)
    pop_e, hk_e = _par_epci(L, ref, types)
    dens = ctx_epci["densite_pop"].reindex(pop_e.index) if "densite_pop" in ctx_epci else None
    classes, tests, conc = [], [], []
    de = (L.get("distances") or {}).get("epci")
    if dens is not None:
        cl_e = pd.Series(np.nan, index=pop_e.index, dtype=object)
        for a, b, lab in CLASSES_DENSITE:
            cl_e[(dens >= a) & (dens < b)] = lab
        cl_c = com["epci"].map(cl_e)
        for tid in types:
            groupes = []
            for _a, _b, lab in CLASSES_DENSITE:
                m = (cl_c == lab).to_numpy()
                w, x = pop_c.to_numpy()[m], dist[tid].to_numpy()[m]
                if w.sum() <= 0:
                    continue
                classes.append({"type": tid, "classe": lab, "population": w.sum(),
                                "distance_mediane_km": mediane_ponderee(x, w),
                                "part_plus_20_km": float(w[x > 20].sum() / w.sum())})
                if isinstance(de, pd.DataFrame):
                    v = de[de["type"] == tid].set_index("code")["distance_mediane_km"]
                    g = v.reindex(cl_e.index[cl_e == lab]).dropna().to_numpy()
                    if len(g) >= 5:
                        groupes.append(g)
            if len(groupes) >= 2:
                H, p = stats.kruskal(*groupes)
                N = sum(len(g) for g in groupes)
                tests.append({"type": tid, "kruskal_H": H, "p": p, "epsilon2": H / (N - 1), "intercommunalites": N})
    if "revenu_median" in ctx_epci:
        rev = ctx_epci["revenu_median"].reindex(pop_e.index)
        ok = rev.notna() & (pop_e > 0)
        for tid in types:
            ok_t = ok & hk_e[tid].notna()
            y, w, r = hk_e.loc[ok_t, tid].to_numpy(), pop_e[ok_t].to_numpy(), rev[ok_t].to_numpy()
            ci, *_ = indice_concentration(y, w, r)
            bs, g = [], tirage("concentration_distances", cle, tid)
            for _ in range(config.BOOTSTRAP):
                i = g.integers(0, len(y), len(y))
                bs.append(indice_concentration(y[i], w[i], r[i])[0])
            lo, hi = np.percentile(bs, [2.5, 97.5])
            conc.append({"type": tid, "indice_concentration": ci, "ic95_bas": lo, "ic95_haut": hi,
                         "intercommunalites": int(ok_t.sum())})
    t = pd.DataFrame(tests)
    if len(t):
        t["q_bh"] = benjamini_hochberg(t["p"])
    c = pd.DataFrame(conc)
    if len(c):
        lib = {x[0]: x[1] for x in config.LIEUX_TYPES}
        nets = c[(c["ic95_bas"] > 0) | (c["ic95_haut"] < 0)]
        JOURNAL.controle("Distance aux structures de soins selon le niveau de vie (indice de concentration)"
                         + ("" if cle == "toutes" else ", avec les seules structures confirmées"),
                         f"{len(nets)} types sur {len(c)} avec un lien net, " + ", ".join(
                             f"{lib[r.type].split(',')[0]} {r.indice_concentration:+.2f}" for r in c.itertuples()
                             if r.type in ("lieu_cmp_adultes", "lieu_urgences")))
    return {"classes": pd.DataFrame(classes), "tests": t, "concentration": c}


def typologie_lieux(affect: pd.DataFrame | None, L: dict, ref) -> pd.DataFrame | None:
    """Structures de soins décrites dans chaque groupe de la typologie, à titre descriptif seulement (elles ne servent pas à
    former les groupes). Structures pour 100 000 habitants, indice 100 pour la France, et distance médiane des habitants
    à la structure la plus proche (décision du 12 octobre 2026)."""
    if not L or not isinstance(affect, pd.DataFrame) or affect.empty:
        return None
    from .analyses import mediane_ponderee
    types = _types_comparables(L)
    dist = L["distances_communes"]
    com = ref.communes.set_index("code").reindex(dist.index)
    pop_c = com["pop"].astype(float).fillna(0)
    n_e = L["comptes"]["epci"].pivot_table(index="code", columns="type", values="n", aggfunc="sum").fillna(0)
    lignes = []
    for fam, g in affect.groupby("famille"):
        voulus = [t for t in lieux_profil.types_avec("typologie", fam) if t in types]
        cl = g.set_index("code")["classe"]
        cl_c = com["epci"].map(cl)
        pop_e = pop_c.groupby(com["epci"]).sum().reindex(cl.index).fillna(0)
        n = n_e.reindex(cl.index).fillna(0)
        for tid in voulus:
            if tid not in n:
                continue
            nat = n[tid].sum() / pop_e.sum() * 1e5
            for k in sorted(cl.unique()):
                m = cl == k
                taux = n.loc[m, tid].sum() / pop_e[m].sum() * 1e5 if pop_e[m].sum() else np.nan
                mc = (cl_c == k).to_numpy()
                w, x = pop_c.to_numpy()[mc], dist[tid].to_numpy()[mc]
                med = mediane_ponderee(x, w) if w.sum() else np.nan
                lignes.append({"famille": fam, "classe": int(k), "type": tid, "lieux_pour_100000": taux,
                               "indice_vs_national": 100 * taux / nat if nat else np.nan,
                               "distance_mediane_km": med})
    return pd.DataFrame(lignes) if lignes else None


MOTIF_NON_PUBLIE = "non publié, moins de la moitié des structures de la SAE inscrites dans FINESS et le ROR"


def taux_publics(c: pd.DataFrame, pop: pd.Series, cn: pd.DataFrame | None, mq: pd.DataFrame | None,
                 niv: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Structures pour 100 000 personnes de leur public, la même règle pour le site (indicateurs) et pour les fichiers
    lieux_soins_<niveau>.csv (export), qui rapportaient tout à la population et ne masquaient rien jusqu'au 30 octobre
    2026 (audit du soir, CA Colmar Agglomération). c, nombres par territoire (lignes) et type (colonnes) ; pop, population
    des territoires ; cn, contexte du niveau (parts de la population par âge, lieux_profil.denominateur), sans quoi le
    type est rapporté à toute la population ; mq, manques de la SAE (manques_sae), qui vident le taux. Renvoie les taux
    et un tableau vrai/faux des taux retirés par les manques."""
    t = c.div(pop.astype(float).where(pop > 0), axis=0) * 1e5
    # structures d'un public particulier rapportées à ce public (dénominateur du registre, 15 octobre 2026)
    for tp in c.columns:
        parts = lieux_profil.denominateur(tp)[0]
        if parts and isinstance(cn, pd.DataFrame) and all(p_ in cn for p_ in parts):
            pp = pop.astype(float) * cn[parts].sum(axis=1).reindex(pop.index) / 100
            t[tp] = c[tp] / pp.where(pp > 0) * 1e5
    # territoires où les bases inscrivent moins de la moitié des structures que la SAE déclare (manques_sae)
    retire = pd.DataFrame(False, index=t.index, columns=t.columns)
    if isinstance(mq, pd.DataFrame):
        for r in mq[(mq["niveau"] == niv) & mq["manque"]].itertuples():
            if r.type in t.columns and r.code in t.index:
                t.loc[r.code, r.type] = np.nan
                retire.loc[r.code, r.type] = True
    return t, retire


def indicateurs(L: dict, ref, ctx: dict | None = None) -> dict | None:
    from .lecture import minuscule
    """Structures pour 100 000 habitants et distance médiane des habitants à la structure la plus proche, par intercommunalité,
    département et région, pour les types du registre (analyse « indicateur ») recensés presque partout. Même forme que les
    autres sources de contexte (« contexte » par niveau et « defs »)."""
    if not L:
        return None
    ok = set(L["couverture"].loc[L["couverture"]["complet"], "type"])
    types = [t for t in lieux_profil.types_avec("indicateur") if t in ok]
    lab = {t[0]: t for t in config.LIEUX_TYPES}
    pops = {"epci": ref.epci.set_index("code")["pop"], "dep": ref.deps.set_index("code")["pop"],
            "reg": ref.regs.set_index("code")["pop"]}
    # « sortie » et non « ctx » : le même nom écrasait le contexte de l'INSEE reçu en paramètre, et du 15 au 30 octobre
    # 2026 les structures d'un public particulier (EHPAD, CMP pour enfants, CMPP, CAMSP...) étaient rapportées à toute la
    # population sous un libellé qui annonçait leur public (signalé, EHPAD de la Sologne des Étangs)
    sortie = {}
    for niv, pop in pops.items():
        c = L["comptes"][niv].pivot_table(index="code", columns="type", values="n", fill_value=0)
        c = c.reindex(index=pop.index, columns=types).fillna(0)
        cn = (ctx or {}).get(niv)
        t = taux_publics(c, pop, cn, L.get("manques_sae"), niv)[0]
        t = t.add_prefix("lieux_")
        d = (L.get("distances") or {}).get(niv)
        if isinstance(d, pd.DataFrame):
            dd = d[d["type"].isin(types)].pivot_table(index="code", columns="type", values="distance_mediane_km")
            t = t.join(dd.reindex(columns=types).add_prefix("dist_"), how="left")
        # même distance, médiane du public que sert la structure (naissances, au domicile de la mère, pour une maternité)
        pc = L.get("population_concernee")
        if population_concernee_visible() and isinstance(pc, pd.DataFrame) and not pc.empty:
            tp_pub = [tp for tp in types if public_du_type(tp)]
            dp = pc[(pc["niveau"] == niv) & pc["type"].isin(tp_pub)].pivot_table(
                index="code", columns="type", values="distance_mediane_km_public")
            t = t.join(dp.reindex(columns=tp_pub).add_prefix("distp_"), how="left")
        sortie[niv] = t
        if niv == "reg" and isinstance(cn, pd.DataFrame):
            # contrôle permanent du dénominateur, valeur France de chaque type rapporté à son public
            vals = []
            for tp in types:
                parts, public = lieux_profil.denominateur(tp)
                if parts and all(p_ in cn for p_ in parts):
                    cible = (pop.astype(float) * cn[parts].sum(axis=1).reindex(pop.index) / 100).sum()
                    vals.append(f"{_court(lab[tp][1], tp)} {nombre(c[tp].sum() / cible * 1e5, 1)} pour 100 000 "
                                f"{'enfants' if public.startswith('moins') else 'personnes'} de {public}")
            JOURNAL.controle("Structures rapportées à leur public, France (attendu, ni à toute la population ni vide)",
                             ", ".join(vals) if vals else "aucun type rapporté à son public, contexte absent")
    defs = []
    for tp in types:
        lib = lab[tp][1]
        court = _court(lib, tp)
        public = lieux_profil.denominateur(tp)[1] if ctx else ""
        # « pour 100 000 personnes de 80 ans et plus » et non « pour 100 000 80 ans et plus », qui se lisait comme
        # « pour 100 000 habitants » (remarque du 30 octobre 2026)
        qui = (f"enfants de {public}" if public.startswith("moins") else f"personnes de {public}") if public else "habitants"
        defs.append({"id": f"lieux_{tp}", "libelle": f"{court}, pour 100 000 {qui}",
                     "unite": f"pour 100 000 {qui}" if public else "pour 100 000 hab.",
                     "explication": f"Nombre de structures du type « {lib} » recensées par FINESS et le Répertoire "
                                    "opérationnel des ressources, réunis sans double compte, rapporté "
                                    + (f"aux {public} (le recensement ne publie pas les moins de 18 ans). " if public.startswith("moins")
                                       else f"aux personnes de {public}. " if public else "à la population. ")
                                    + "Une structure n'est pas une capacité, une antenne peut n'ouvrir que quelques "
                                    "demi-journées.",
                     "source": config.SOURCE_LIEUX, "famille": "", "licence": "Licence Ouverte 2.0",
                     "niveau_origine": "commune", "groupe": config.GROUPE_LIEUX})
        defs.append({"id": f"dist_{tp}", "libelle": f"Distance à la structure la plus proche, {minuscule(court)}",
                     "unite": "km",
                     "explication": f"Distance à vol d'oiseau entre le centre de la commune des habitants et la "
                                    f"structure la plus proche du type « {lib} », médiane des habitants du territoire. Ce n'est pas "
                                    "un temps de trajet.",
                     "source": config.SOURCE_LIEUX, "famille": "", "licence": "Licence Ouverte 2.0",
                     "niveau_origine": "commune", "groupe": config.GROUPE_DISTANCES})
        cle = public_du_type(tp)
        pc = L.get("population_concernee")
        if cle and population_concernee_visible() and isinstance(pc, pd.DataFrame):
            variables, qui = config.PUBLICS_CONCERNES[cle]
            an = (L.get("millesimes_insee") or {}).get(variables[0]) or L.get("millesime_naissances")
            per = L.get("periode_naissances")
            # part des territoires où la distance du public égale exactement celle de tous les habitants, au niveau de la
            # fiche qui la montre (relecture du 10 novembre 2026 : 64 % des intercommunalités mais 14 % des départements
            # pour une maternité, la part des intercommunalités lue sur une fiche de département trompait)
            noms_niv = {"epci": "intercommunalités", "dep": "départements", "reg": "régions"}
            egales = {}
            for niv in noms_niv:
                x = pc[(pc["niveau"] == niv) & (pc["type"] == tp)].dropna(
                    subset=["distance_mediane_km", "distance_mediane_km_public"])
                if len(x):
                    egales[niv] = ((x["distance_mediane_km"] - x["distance_mediane_km_public"]).abs() < 1e-6).mean()

            def part(niv):
                e = egales.get(niv)
                return (f" ; même valeur que pour tous les habitants dans {nombre(100 * e, 0)}\u202f% des {noms_niv[niv]}"
                        if e is not None and e > 0.05 else "")
            # « naissances récentes » ne se comprenait pas, même avec sa définition (10 novembre 2026) : le public
            # se nomme par ce qu'il est, les mères des enfants nés pendant une période dite en années. Les naissances
            # viennent de l'état civil, publiées dans la série historique du recensement (DS_RP_SERIE_HISTORIQUE).
            gens = ("enfants de " if qui.startswith("moins") else "personnes de ") + qui
            if cle == "naissances":
                annees = f"de {per[0]} à {per[1]}" if per else "entre les deux derniers recensements"
                src = f" (INSEE, état civil, publié avec le recensement de {an})" if an else " (INSEE, état civil)"
                pour = f"depuis le domicile des mères (enfants nés {annees})"
                depuis = (f"depuis la commune où vivait la mère de chaque enfant né {annees}{src}. Ces communes "
                          "approchent mieux le lieu de vie des futures mères que celles de tous les habitants.")
            else:
                src = f" (INSEE, recensement de {an})" if an else " (INSEE)"
                pour = f"pour les {gens}"
                depuis = f"depuis la commune des {gens}{src}, et non depuis celle de tous les habitants."
            # la définition complète, au catalogue, se lit seule (page de l'indicateur, Explorer) et garde toutes ses
            # limites ; la courte se lit sous sa ligne mère, sur la fiche, avec la part du niveau de la fiche, et garde
            # « à vol d'oiseau » et « pas un temps de trajet », que la ligne mère ne dit pas toujours (bande santé mentale)
            # la complète se lit à tous les niveaux (page de l'indicateur, Explorer, API) : elle donne les trois parts
            vus = [f"{nombre(100 * egales[n], 0)} % des {noms_niv[n]}" for n in noms_niv
                   if egales.get(n) is not None and egales[n] > 0.05]
            toutes_parts = (" Même valeur que pour tous les habitants dans " + (", ".join(vus[:-1]) + " et " + vus[-1]
                            if len(vus) > 1 else vus[0]) + ".") if vus else ""
            courtes = {niv: "Distance médiane à vol d'oiseau, comptée " + depuis
                       + " Ensemble et position sur ce même public, hors Mayotte" + part(niv)
                       + ". Ce n'est pas un temps de trajet." for niv in noms_niv}
            defs.append({"id": f"distp_{tp}", "libelle": f"Distance à la structure la plus proche, {minuscule(court)}, "
                                                          f"{pour}",
                         "unite": "km",
                         "explication": f"Distance médiane à vol d'oiseau entre le centre de la commune et la structure "
                                        f"la plus proche du type « {lib} », comptée " + depuis
                                        + " La valeur, l'ensemble, la médiane et la position portent sur ce public, "
                                        "parmi les territoires hors Mayotte, qui n'a pas de recensement ; Paris, Lyon et "
                                        "Marseille comptent pour un point." + toutes_parts
                                        + " Ce n'est pas un temps de trajet, et une structure proche ne dit pas "
                                        "qu'elle suffit.",
                         "explication_courte": courtes["dep"],
                         "explication_courte_niveaux": courtes,
                         # l'INSEE pondère le calcul : sa source est nommée avec celle des structures
                         "source": config.SOURCE_LIEUX + (" ; INSEE, état civil et recensement" if cle == "naissances"
                                                          else " ; INSEE, recensement"),
                         "famille": "", "licence": "Licence Ouverte 2.0",
                         "niveau_origine": "commune", "groupe": config.GROUPE_DISTANCES})
    return {"contexte": sortie, "defs": defs}


# distance en deçà de laquelle un site autorisé est tenu pour une structure du même type déjà dans la liste sous un
# autre numéro (le Groupe hospitalier mutualiste de Grenoble, devenu Cité hospitalière des Alpes à la même adresse ; le
# centre de dialyse du Lensois dans le CH de Lens ; le second site de l'Hôpital américain ; l'antenne de Sainte-Foy-la-
# Grande du CH de Libourne), banc d'essai du 16 novembre 2026
AUTORISATION_MEME_LIEU_KM = 0.5


def completer_par_autorisations(lieux: pd.DataFrame, hors_ligne: bool, fin: pd.DataFrame | None = None,
                                urgences_specialisees: set | None = None, ref=None) -> tuple[pd.DataFrame, dict]:
    """Quatrième source des types hospitaliers (chantier des structures, constat C10 du 16 novembre 2026) : un
    établissement géographique qui exerce une activité autorisée (urgences, maternité, dialyse, HAD, réadaptation, flux
    « FINESS - Activités » de l'ANS) et que la liste n'a pas sous ce type la reçoit, comme une structure de FINESS, à
    son adresse FINESS (urgences de Dunkerque, maternité de Sarreguemines, cliniques de réadaptation absentes du ROR).
    Il faut qu'il soit ouvert dans FINESS et dans une commune du référentiel (pas Saint-Martin, Saint-Barthélemy ni
    Saint-Pierre-et-Miquelon). Une fois les structures placées, `ecarter_autorisations_meme_lieu` retire celles qui
    tombent à moins de AUTORISATION_MEME_LIEU_KM d'une structure du même type : c'est alors la même, sous un autre
    numéro. La ligne est construite depuis FINESS, jamais recopiée d'une unité du ROR d'un autre type (une ligne recopiée
    gardait les unités, catégories et rapprochements de cette unité : « PASS » en dialyse à Pau, banc d'essai du
    16 novembre 2026). Une structure de la liste dont le numéro n'exerce pas l'activité est comptée, sans être retirée
    (un numéro de site peut différer de celui de l'autorisation)."""
    from .sources import finess_activites
    a = finess_activites.charger(hors_ligne)
    rendu = {"ajoutees": 0, "absentes_de_la_liste": 0, "sans_autorisation": 0, "par_type": {}}
    if not a or fin is None:
        return lieux, rendu
    f = fin[fin["actif"]].drop_duplicates("nofinesset").set_index("nofinesset")
    com = f["com"]
    if ref is not None:
        actuels = set(ref.communes["code"])
        com = com.where(com.isin(actuels), com.map(ref.anciens)).where(lambda c: c.isin(actuels))
    f = f.assign(com=commune_de(com))
    ajouts = []
    for t, sites in a["sites"].items():
        du_type = lieux["type"] == t
        deja = set(lieux.loc[du_type, "finess"].dropna())
        if "finess_rapproche" in lieux:
            deja |= set(lieux.loc[du_type, "finess_rapproche"].dropna())
        c = f.loc[sorted((sites - deja) & set(f.index[f["com"].notna()]))]
        if t == "lieu_urgences":
            # comme pour les unités du ROR (config.LIEUX_TYPES, « hors »), pas les urgences d'une maternité ni d'une
            # spécialité, que l'autorisation de médecine d'urgence ne distingue pas
            c = c[~c.index.isin(urgences_specialisees or set())]
            c = c[~c["rs"].fillna("").map(norm).str.contains(r"matern|obstetri|gyneco|ophtalm|\borl\b|tete et cou",
                                                             regex=True)]
        et_ = c.index.to_series()
        n = pd.DataFrame({"type": t, "lieu": "F" + et_ + "|" + c["com"], "finess": et_, "ej": c["nofinessej"],
                          "commune": c["com"], "nom_finess": c["rs"], "nom_affiche": c["rs"],
                          "categorie_finess": c["categetab"], "provenance": "autorisation", "dans_ror": "False"})
        ajouts.append(n.reset_index(drop=True))
        rendu["par_type"][t] = [len(n), len(sites - deja) - len(n), len(deja - sites - {""})]
        rendu.setdefault("sites", {})[t] = sites
        rendu["sans_autorisation"] += len(deja - sites - {""})
    if ajouts:
        lieux = pd.concat([lieux] + ajouts, ignore_index=True)
    return lieux, rendu


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance en mètres entre deux points (formule de haversine), NaN si un point manque."""
    if any(pd.isna(v) for v in (lat1, lon1, lat2, lon2)):
        return float("nan")
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return float(2 * 6371000 * np.arcsin(np.sqrt(a)))


def un_lieu_par_adresse_cmp(lieux: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """Décision 1 du chantier des structures (acceptée le 16 novembre 2026) : un lieu de CMP, c'est une adresse et un public.
    Deux CMP pour adultes (ou deux CMP pour enfants) à la même adresse numérotée de la même commune, souvent deux
    secteurs dans un même immeuble (Carcassonne, Le Mans, Étampes), ne comptent qu'une fois ; un CMP pour adultes et un
    CMP pour enfants à la même adresse restent deux lieux. Le CMP « tous publics » d'un lieu réuni n'est retiré que s'il
    n'accueille plus aucun public. Renvoie les structures et la liste des lignes retirées, avec leur raison."""
    x = lieux
    adr = (x["adresse"].fillna("").map(lambda s: _simple(voie_developpee(s))) if "adresse" in x
           else pd.Series("", index=x.index))
    num = adr.str.extract(r"^(\d+\s*(?:bis|ter|b|t)?)\s")[0]
    rue = adr.str.replace(r"^\d+\s*(?:bis|ter|b|t)?\s+", "", regex=True)
    retirer, retirees = set(), []
    lieux_retires = {}
    for tid in ("lieu_cmp_adultes", "lieu_cmp_enfants"):
        m = (x["type"] == tid) & num.notna() & (rue != "")
        g = x[m].assign(_cle=x.loc[m, "commune"] + "|" + num[m].str.replace(" ", "") + "|" + rue[m])
        for _, grp in g.groupby("_cle"):
            if grp["lieu"].nunique() < 2:
                continue
            garde = grp["lieu"].iloc[0]
            for i, r in grp[grp["lieu"] != garde].iterrows():
                retirer.add(i)
                lieux_retires.setdefault(r["lieu"], set()).add(tid)
                retirees.append({"ej": r.get("ej"), "etablissement": None, "type": tid,
                                 "nom": r.get("nom_affiche") if isinstance(r.get("nom_affiche"), str) else r.get("nom"),
                                 "commune": r.get("commune"), "nom_commune": None,
                                 "finess": r.get("finess") if isinstance(r.get("finess"), str) else None,
                                 "provenance": r.get("provenance"),
                                 "raison": "même adresse et même public qu'un autre CMP, un seul lieu"})
        # même rue de la même commune, numéro absent d'au moins un côté (« PL JEAN TAVE » et « place Jean-Tavé » à
        # Tulle, « R des prêtres » à Merville, constat du 17 novembre 2026) : même lieu quand les deux points sont à
        # moins de CMP_MEME_RUE_M mètres et que le gestionnaire est le même ou le code de secteur le même (« CMP
        # 94G12 » et « CMP Paul-Brousse d'Ivry-sur-Seine (94G12) »). Sans ces conditions, une longue rue peut porter
        # deux lieux distincts (boulevard Béranger à Tours, deux établissements).
        reste = x[(x["type"] == tid) & (rue != "") & ~x.index.isin(retirer)]
        for _, grp in reste.groupby([reste["commune"], rue[reste.index]]):
            if grp["lieu"].nunique() < 2 or grp.index.map(num).notna().all():
                continue
            # la structure vérifiée, puis celle dont l'adresse est numérotée, est gardée
            ver_ = grp["verifiee"].fillna(False).astype(bool) if "verifiee" in grp else pd.Series(False, index=grp.index)
            ordre = sorted(grp.index, key=lambda i: (not ver_[i], pd.isna(num[i]), str(grp.at[i, "lieu"])))
            gardes_ = []
            for i in ordre:
                r = x.loc[i]
                nom_i = _simple(r.get("nom_affiche") if isinstance(r.get("nom_affiche"), str) else r.get("nom"))
                meme = None
                for j in gardes_:
                    q = x.loc[j]
                    if isinstance(num[i], str) and isinstance(num[j], str):
                        continue
                    nom_j = _simple(q.get("nom_affiche") if isinstance(q.get("nom_affiche"), str) else q.get("nom"))
                    codes = set(_CODE_SECTEUR.findall(nom_i)) & set(_CODE_SECTEUR.findall(nom_j))
                    meme_ej = isinstance(r.get("ej"), str) and r.get("ej") == q.get("ej")
                    try:
                        d = _distance_m(float(r["lat"]), float(r["lon"]), float(q["lat"]), float(q["lon"]))
                    except (TypeError, ValueError, KeyError):
                        d = float("nan")
                    if (meme_ej or codes) and d <= config.CMP_MEME_RUE_M:
                        meme = j
                        break
                if meme is None:
                    gardes_.append(i)
                    continue
                retirer.add(i)
                lieux_retires.setdefault(r["lieu"], set()).add(tid)
                retirees.append({"ej": r.get("ej"), "etablissement": None, "type": tid,
                                 "nom": r.get("nom_affiche") if isinstance(r.get("nom_affiche"), str) else r.get("nom"),
                                 "commune": r.get("commune"), "nom_commune": None,
                                 "finess": r.get("finess") if isinstance(r.get("finess"), str) else None,
                                 "provenance": r.get("provenance"),
                                 "raison": "même rue et même public qu'un autre CMP du même établissement ou du même "
                                           "secteur, au même point, un seul lieu"})
    # le CMP « tous publics » d'un lieu dont tous les publics ont été réunis à un autre lieu
    enfants = x[x["type"].isin(["lieu_cmp_adultes", "lieu_cmp_enfants"]) & ~x.index.isin(retirer)]
    restants = set(enfants["lieu"])
    for lieu in lieux_retires:
        if lieu not in restants:
            retirer |= set(x.index[(x["type"] == "lieu_cmp") & (x["lieu"] == lieu)])
    x = x.drop(index=sorted(retirer))
    JOURNAL.controle("CMP réunis : même adresse numérotée et même public, un seul lieu (décision du 16 novembre 2026)",
                     ", ".join(f"{t.removeprefix('lieu_')} {sum(r['type'] == t for r in retirees)}"
                               for t in ("lieu_cmp_adultes", "lieu_cmp_enfants")))
    return x, retirees


def ecarter_autorisations_meme_lieu(lieux: pd.DataFrame, rendu: dict, fin: pd.DataFrame | None = None) -> pd.DataFrame:
    """Après le placement : une structure ajoutée par son autorisation (`completer_par_autorisations`) à moins de
    AUTORISATION_MEME_LIEU_KM d'une structure du même type déjà dans la liste dont le numéro n'exerce pas lui-même
    l'activité est la même sous un autre numéro : elle est retirée. Une structure voisine dont le numéro l'exerce aussi
    est un autre site (au CHRU de Brabois, à Nancy, le centre de dialyse de l'hôpital et les unités d'autodialyse de
    l'ALTIR, trois sites de la SAE), à condition d'être dans la commune de ce numéro : l'unité d'urgences de
    Sainte-Foy-la-Grande porte dans le ROR le numéro du site principal du CH de Libourne. Plusieurs sites ajoutés au même point (moins de 50 m : quatre cliniques regroupées
    à Montaudran, Toulouse) ne font qu'une structure. Écrit les contrôles du journal."""
    if not rendu.get("par_type"):
        return lieux
    retire = pd.Series(False, index=lieux.index)
    exemples = []
    for t in rendu["par_type"]:
        m = lieux["type"] == t
        aut = m & (lieux["provenance"] == "autorisation")
        if not aut.any():
            continue
        sites = rendu.get("sites", {}).get(t, set())
        num_r = lieux["finess_rapproche"] if "finess_rapproche" in lieux else pd.Series(None, index=lieux.index)
        com_f = fin.drop_duplicates("nofinesset").set_index("nofinesset")["com"] if fin is not None else pd.Series(dtype=object)
        chez = lambda n: n.isin(sites) & (commune_de(n.map(com_f)) == lieux["commune"])  # noqa: E731
        exerce = chez(lieux["finess"]) | chez(num_r)
        base = lieux[m & ~aut & ~exerce & lieux["lat"].notna()]
        la, lo = list(base["lat"].astype(float)), list(base["lon"].astype(float))
        nla, nlo = [], []
        for i, r in lieux[aut].iterrows():
            if pd.isna(r["lat"]):
                continue
            cos = np.cos(np.radians(r["lat"]))
            pres = la and np.hypot((np.array(la) - r["lat"]) * 111.2,
                                   (np.array(lo) - r["lon"]) * 111.2 * cos).min() < AUTORISATION_MEME_LIEU_KM
            meme_point = nla and np.hypot((np.array(nla) - r["lat"]) * 111.2,
                                          (np.array(nlo) - r["lon"]) * 111.2 * cos).min() < 0.05
            if pres or meme_point:
                retire[i] = True
                # nom entier, une seule fois (relecture du 17 novembre 2026, noms tronqués et répétés)
                if len(exemples) < 6 and str(r["nom_affiche"]) not in exemples:
                    exemples.append(str(r["nom_affiche"]))
                continue
            nla.append(float(r["lat"]))
            nlo.append(float(r["lon"]))
        n_ret = int((retire & m).sum())
        rendu["par_type"][t][0] -= n_ret
        rendu["par_type"][t][1] += n_ret
    lieux = lieux[~retire].reset_index(drop=True)
    rendu["ajoutees"] = sum(v[0] for v in rendu["par_type"].values())
    rendu["absentes_de_la_liste"] = sum(v[1] for v in rendu["par_type"].values())
    JOURNAL.controle("FINESS - Activités, sites qui exercent une activité hospitalière autorisée, ajoutés sous ce type",
                     ", ".join(f"{t.removeprefix('lieu_')} {v[0]} ajoutés, {v[1]} non ajoutés (même lieu qu'une "
                               f"structure du type, hors du référentiel, fermés ou urgences spécialisées), {v[2]} numéros "
                               f"de la liste sans l'activité" for t, v in rendu["par_type"].items())
                     + f" ; {int(retire.sum())} retirés au même lieu qu'une structure du type, dont "
                     + ", ".join(exemples))
    _releve("FINESS - Activités", "Établissements qui exercent une activité hospitalière autorisée (urgences, maternité, "
            "dialyse, HAD, réadaptation) sans structure de ce type dans le ROR ni à moins de 500 m", rendu["ajoutees"],
            "Ajoutés sous ce type, à leur adresse de FINESS")
    return lieux


def calculer(ror: dict | None, fin: pd.DataFrame | None, act: pd.DataFrame, ref, voisins, hors_ligne=False,
             has: dict | None = None, sirene: dict | None = None, essms: dict | None = None) -> dict | None:
    """Structures de soins réunies, comptes par territoire, distances, concordance des deux bases et contrôles."""
    if not ror or fin is None:
        return None
    RELEVE.clear()
    u = _unites_retenues(ror, ref, fin)
    # unités du ROR déclarées comme CMP, comptées avant réunion en lieux (plusieurs unités d'un même CMP, ou des CMP
    # déclarés à l'adresse de l'hôpital sans lieu distinct, ne font qu'un lieu), pour la confrontation à la SAE
    uc0 = u[(u["champ"] == config.CHAMP_PSY) & u["categorie"].isin(["10", "281"])]
    uc = uc0[~uc0["nom"].fillna("").map(norm).str.contains(config.LIEUX_EXCLUS_CMP, regex=True)]
    _releve("ROR", "Unités déclarées comme CMP qui sont des équipes mobiles, de la liaison, des urgences, des "
            "consultations non sectorisées ou spécialisées, des maisons des adolescents, des hôpitaux de jour ou des soins en milieu "
            "pénitentiaire", len(uc0) - len(uc),
            "Non comptées parmi les CMP")
    unites_cmp = uc.assign(dep=uc["commune"].map(ref.communes.set_index("code")["dep"])).groupby("dep").size()
    ej_de = fin.set_index("nofinesset")["nofinessej"]
    unites_cmp_ej = uc["finess_ror"].map(ej_de).fillna(uc["finess_ror"]).value_counts()
    perso = u["nom"].fillna("").map(norm).str.contains(config.NOM_PERSONNE, regex=True)
    if perso.any():
        JOURNAL.controle("ROR, unités écartées parce que leur nom contient un nom de personne", f"{int(perso.sum())}")
        _releve("ROR", "Consultations nominatives (nom d'une personne dans le nom de l'unité)", int(perso.sum()),
                "Écartées, aucun nom de personne n'est publié")
        u = u[~perso]
    classes = classer_unites(u)
    lr = _lieux_ror(u, classes, fin)
    lf = _lieux_finess(fin, ref)
    lieux, stats = reunir(lr, lf, fin.set_index("nofinesset")["categetab"])
    # un CMP connu de FINESS seul n'a pas d'âges déclarés, son public est déduit de son nom (« infanto-juvénile »,
    # « adultes », code de secteur). Sans indice, il reste compté parmi les CMP, au public non précisé, et le dire
    # partout (constat du 12 octobre 2026, 22 CMP dans l'Ain pour 11 adultes et 10 enfants)
    cmp_ = lieux[lieux["type"] == "lieu_cmp"]
    deja = set(lieux.loc[lieux["type"].isin(["lieu_cmp_adultes", "lieu_cmp_enfants"]), "lieu"])
    sans = cmp_[~cmp_["lieu"].isin(deja)]
    nm = sans["nom"].fillna(sans.get("nom_finess")).fillna("").map(norm) if len(sans) else pd.Series(dtype=str)
    enf = nm.str.contains(config.NOM_ENFANTS + "|" + config.NOM_SECTEUR_ENFANTS, regex=True)
    adu = ~enf & nm.str.contains(config.NOM_ADULTES, regex=True)
    ajout = pd.concat([sans[enf].assign(type="lieu_cmp_enfants"), sans[adu].assign(type="lieu_cmp_adultes")])
    if len(ajout):
        lieux = pd.concat([lieux, ajout], ignore_index=True)
    stats["cmp_public_deduit_du_nom"] = int(len(ajout))
    stats["cmp_public_non_precise"] = int(len(sans) - len(ajout))
    _releve("FINESS", "CMP connus de FINESS seul, sans âges déclarés", int(len(sans)),
            f"Public déduit du nom pour {int(enf.sum()) + int(adu.sum())} ({int(enf.sum())} pour enfants et adolescents, "
            f"{int(adu.sum())} pour adultes), écrit « public non précisé » pour {int(len(sans) - len(ajout))}, avant vérification et réunion des doublons")
    JOURNAL.controle("CMP dont le public est déduit du nom (FINESS seul, sans âges déclarés)",
                     f"{int(enf.sum())} pour enfants et adolescents, {int(adu.sum())} pour adultes, "
                     f"{int(len(sans) - len(ajout))} au public non précisé")
    # les CMP pour adultes et pour enfants reprennent la provenance du lieu « CMP, tous publics » de même clé
    for tid, _l, _f, _g, r in config.LIEUX_TYPES:
        if r.get("parent"):
            prov = lieux[lieux["type"] == r["parent"]].set_index("lieu")["provenance"]
            m = lieux["type"] == tid
            lieux.loc[m, "provenance"] = lieux.loc[m, "lieu"].map(prov).fillna(lieux.loc[m, "provenance"])
    # un type que FINESS ne distingue pas (unités hospitalières, équipes mobiles...) ne peut être que dans le ROR
    propres = _categories_propres()
    # sauf un établissement de FINESS rangé dans ce type par son nom (un CMP de FINESS qui est une équipe mobile)
    lieux.loc[~lieux["type"].isin(propres) & (lieux["provenance"] == "ror"), "provenance"] = "ror_type"
    # nom affiché, celui de l'unité du ROR (« CMP Munster »), sauf s'il est vague (« Accompagnement »), alors celui de
    # la structure, et la raison sociale de FINESS pour un lieu absent du ROR. Aucun nom d'unité du ROR ne doit
    # contenir de nom de personne (les unités concernées ont été écartées plus haut).
    simple = lieux["nom"].map(_simple)
    # un nom d'unité porté par au moins dix lieux en France (« Hébergement pour personnes âgées dépendantes ») est vague
    frequent = simple.map(simple.value_counts()) >= 10
    vague = simple.str.fullmatch(NOMS_VAGUES) | frequent | lieux["nom"].isna()
    lieux["nom_affiche"] = lieux["nom"].where(~vague, lieux["structure_nom"].fillna(lieux.get("nom_finess")))
    lieux["nom_affiche"] = lieux["nom_affiche"].fillna(lieux.get("nom_finess")).fillna(lieux["nom"])
    bad = lieux["nom"].fillna("").map(norm).str.contains(config.NOM_PERSONNE, regex=True)
    if bad.any():
        raise ValueError(f"{int(bad.sum())} lieux tirés du ROR portent un nom de personne")
    # une structure sans adresse va au centre du contour de sa commune, les distances partent du centre de sa population
    geo = (voisins or {}).get("centres_geo") or (voisins or {}).get("centres")
    centres = (voisins or {}).get("centres")
    # sites dont le ROR ne décrit que des urgences spécialisées (tête et cou, ophtalmologie, mains...) : l'autorisation
    # de médecine d'urgence ne les distingue pas (hôpitaux Huriez à Lille et Gui-de-Chauliac à Montpellier, vérifiés
    # sur les sites des CHU le 16 novembre 2026)
    hors_urg = next(r["hors"] for t, *_m, r in config.LIEUX_TYPES if t == "lieu_urgences")
    # toutes les unités nommées « urgences », quelle que soit leur catégorie : le ROR en laisse sans catégorie
    # (« Urgences Ophtalmologie » à Huriez, « Accueil des urgences médicales » au site mère-enfant du CHU de Martinique)
    nm_u = u["nom"].fillna("").map(norm)
    urg = u[(u["categorie"] == "20") | nm_u.str.contains(r"urgenc", regex=True)]
    urg = urg.assign(_spe=nm_u.reindex(urg.index).str.contains(hors_urg, regex=True))
    specialisees = set(urg.loc[urg["_spe"], "finess_ror"].dropna()) - set(urg.loc[~urg["_spe"], "finess_ror"].dropna())
    lieux, stats["activites_autorisees"] = completer_par_autorisations(lieux, hors_ligne, fin, specialisees, ref)
    from .sources import insee_carreaux
    lieux = localiser(lieux, fin, geo, hors_ligne, (voisins or {}).get("formes"),
                      chefs_lieux=lambda codes: insee_carreaux.chefs_lieux_ban(ref, codes, hors_ligne))
    lieux = ecarter_autorisations_meme_lieu(lieux, stats["activites_autorisees"], fin)
    rattach = ref.communes.set_index("code")[["epci", "dep", "reg"]]
    lieux = lieux.join(rattach, on="commune")
    labels = {t[0]: t for t in config.LIEUX_TYPES}
    lieux["libelle_type"] = lieux["type"].map(lambda t: labels[t][1])
    lieux["famille"] = lieux["type"].map(lambda t: labels[t][2])
    lieux["groupe"] = lieux["type"].map(lambda t: labels[t][3])
    # Nom affiché lisible (règle choisie le 12 octobre 2026). Le type du lieu est affiché à côté, les morceaux
    # du nom du ROR qui ne font que le décrire (« Hébergement Complet Internat ») sont retirés. Un terme à proscrire est
    # retiré quand il reste de quoi identifier le lieu (« IME Les Muscaris »), réécrit sinon, et en dernier recours le
    # lieu est désigné par son type et sa commune. Le nom d'origine reste dans unite_ror (libellé officiel).
    from . import libelles
    secours = lieux["structure_nom"].fillna(lieux.get("nom_finess")) if "structure_nom" in lieux else None
    res = [nom_lisible(n, s) for n, s in zip(lieux["nom_affiche"],
                                             secours if secours is not None else [None] * len(lieux))]
    lieux["nom_affiche"] = [r[0] for r in res]
    trait = pd.Series([r[1] for r in res], index=lieux.index)
    reste = lieux["nom_affiche"].fillna("").map(lambda s: bool(libelles.termes_proscrits(s)))
    nom_com = ref.communes.set_index("code")["nom"]
    if reste.any():
        lieux.loc[reste, "nom_affiche"] = (lieux.loc[reste, "libelle_type"].astype(str).str.split(",").str[0] + ", "
                                           + lieux.loc[reste, "commune"].map(nom_com).fillna("").astype(str))
    # une raison sociale de FINESS qui est le nom d'une personne (« Monsieur ... », relecture de l'édition corrective du
    # 17 novembre 2026, un centre de santé) n'est jamais montrée : le lieu est désigné par son type et sa commune
    perso = lieux["nom_affiche"].fillna("").map(norm).str.contains(config.CIVILITE_EN_TETE, regex=True)
    if perso.any():
        lieux.loc[perso, "nom_affiche"] = (lieux.loc[perso, "libelle_type"].astype(str).str.split(",").str[0] + ", "
                                           + lieux.loc[perso, "commune"].map(nom_com).fillna("").astype(str))
    JOURNAL.controle("Structures de soins dont un nom inscrit est celui d'une personne, désignées par leur type et leur "
                     "commune", f"{int(perso.sum())}")
    JOURNAL.controle("Noms des structures de soins rendus lisibles",
                     f"{int(trait.isin(['court', 'rattachement']).sum())} noms raccourcis à leur nom propre, "
                     f"{int((trait == 'retire').sum())} débarrassés d'un terme à proscrire, {int((trait == 'reecrit').sum())} "
                     f"réécrits, {int(reste.sum())} désignés par leur type et leur commune pour un terme à proscrire")
    _releve("FINESS et ROR", "Noms d'unités du ROR formés de la description de l'activité, ou noms comprenant un terme "
            "daté ou stigmatisant", int(trait.isin(['court', 'rattachement', 'retire', 'reecrit']).sum() + reste.sum()),
            f"Nom propre gardé pour {entier_fr(int(trait.isin(['court', 'rattachement']).sum()))}, terme retiré pour "
            f"{entier_fr(int((trait == 'retire').sum()))}, réécrit pour {entier_fr(int((trait == 'reecrit').sum()))}, nom d'origine conservé dans les "
            f"fichiers")
    lieux, n_fus = fusion_meme_adresse(lieux, fin.drop_duplicates("nofinesset").set_index("nofinesset")["categetab"],
                                       ref.communes.set_index("code")["nom"])
    controle_doublons(lieux)
    _releve("FINESS et ROR", "Même structure décrite deux fois (deux fois par le ROR, par exemple sous l'ancien et le "
            "nouveau nom de son pôle ou à son ancienne et à sa nouvelle adresse, ou sous deux catégories de FINESS)", n_fus,
            "Réunies en une seule, numéros FINESS gardés")
    # liste vérifiée établissement par établissement sur les sources des établissements (décision du
    # 13 octobre 2026), qui remplace la réunion automatique pour les établissements vérifiés. Les inscriptions des
    # bases avant remplacement sont gardées pour préparer les vérifications (jamais publiées).
    from . import structures_verifiees as sv
    try:
        # numéros rapprochés et absorbés compris, que l'empreinte des établissements vérifiés compte : sans eux,
        # l'empreinte calculée par outils/structures_verifiees.py valider différait de celle de la chaîne et
        # signalait à tort 43 des 48 établissements à revérifier (constat du 29 octobre 2026)
        avant = lieux[[c for c in ("type", "lieu", "nom", "nom_finess", "ej", "finess", "finess_rapproche",
                                   "finess_absorbes", "commune", "adresse", "provenance", "unites_ror", "noms_unites",
                                   "lat", "lon", "precision", "categorie_finess") if c in lieux]].copy()
        avant.to_parquet(sv.BASES, index=False)
    except Exception as e:  # noqa: BLE001
        log.warning("structures avant vérification non enregistrées : %s", e)
    # inscriptions confirmées par la certification HAS ou par Sirene avant la liste vérifiée, gardées même quand la
    # source de l'établissement ne les cite pas, en attendant une vérification à la main (décision du
    # 14 octobre 2026)
    from . import confirmation
    pre, _ = confirmation.confirmer(lieux, has, sirene, essms, etape="avant les listes vérifiées")
    garder = set(pre.index[pre["confirmation"].isin(["has", "sirene", "has_sirene"])])
    avant_liste = pre.copy()
    lieux, verif = sv.appliquer(lieux, ref, geo, hors_ligne, garder=garder,
                                fermees=sv.fermees_finess(fin),
                                chefs_lieux=lambda codes: insee_carreaux.chefs_lieux_ban(ref, codes, hors_ligne))
    # nom affiché des structures des listes vérifiées, recopié de la source (raison sociale de FINESS comprise) : même
    # traitement des termes à proscrire que les autres lieux, terme retiré ou réécrit, sinon type et commune (constat du
    # 20 novembre 2026, « Centre spécialisé de soins aux toxicomanes » dans quinze rapports territoriaux)
    ver = lieux["verifiee"].fillna(False).astype(bool) if "verifiee" in lieux else pd.Series(False, index=lieux.index)
    a_revoir = ver & lieux["nom_affiche"].fillna("").map(lambda s: bool(libelles.termes_proscrits(s)))
    for i in lieux.index[a_revoir]:
        lieux.at[i, "nom_affiche"] = nom_lisible(lieux.at[i, "nom_affiche"])[0]
    reste_v = a_revoir & lieux["nom_affiche"].fillna("").map(lambda s: bool(libelles.termes_proscrits(s)))
    if reste_v.any():
        lieux.loc[reste_v, "nom_affiche"] = (lieux.loc[reste_v, "type"].map(lambda t: labels[t][1]).str.split(",").str[0]
                                             + ", " + lieux.loc[reste_v, "commune"].map(nom_com).fillna("").astype(str))
    JOURNAL.controle("Noms des structures des listes vérifiées débarrassés d'un terme à proscrire",
                     f"{int(a_revoir.sum())}, dont " + (f"{int(reste_v.sum())} désignés" if reste_v.sum() else "aucun désigné")
                     + " par leur type et leur commune")
    # structures des listes vérifiées fermées depuis dans FINESS (29 octobre 2026), rangées avec les inscriptions non
    # retenues, leur raison le dit
    verif["non_retenues"] = list(verif["non_retenues"]) + verif["fermees"]
    # confirmation par la certification HAS et par Sirene (listes indépendantes de FINESS et du ROR)
    lieux, sirene_seul = confirmation.confirmer(lieux, has, sirene, essms,
                                                 etape="après les listes vérifiées, avant les verdicts et la réunion des CMP à la même adresse")
    # verdicts de la vérification à la main (décisions du 15 octobre 2026, pipeline/verdicts.py)
    from . import verdicts as verdicts_mod
    lieux, rendu_verdicts = verdicts_mod.appliquer(lieux, avant_liste, ref, geo, hors_ligne)
    verif["non_retenues"] = list(verif["non_retenues"]) + rendu_verdicts["retirees"]
    rendu_verdicts["non_trouves"] = verdicts_mod.situation_orphelins(rendu_verdicts["non_trouves"], lieux,
                                                                     sv.fermees_finess(fin))
    verif["verdicts"] = rendu_verdicts
    # ateliers thérapeutiques et CATTP en milieu pénitentiaire rangés dans leur type (16 octobre 2026)
    lieux, n_atelier, n_prison = retyper_cattp(lieux)
    if n_atelier or n_prison:
        _releve("FINESS et ROR", "CATTP qui sont des ateliers thérapeutiques (catégorie FINESS ou nom), ou tenus en "
                "milieu pénitentiaire", n_atelier + n_prison,
                f"Ateliers rangés avec la réhabilitation psychosociale ({n_atelier}), CATTP en milieu pénitentiaire "
                f"rangés avec les consultations hors CMP ({n_prison}), comme les CMP en milieu pénitentiaire")
    # CATTP tenus dans un CMP qui l'annonce dans son nom (16 octobre 2026)
    e_v = sv.charger()[0]
    cattp_v = {(r["ej"], r["departement"]) for _, r in e_v.iterrows() if "lieu_cattp" in sv.types_de(r["types"])}
    lieux, n_cattp_cmp = cattp_des_cmp(lieux, cattp_v, verif.setdefault("gardees", []),
                                       dict(zip(e_v["ej"], e_v["etablissement"])))
    # structures principales, antennes et sites des CMPP, CAMSP, CSAPA et CAARUD, puis rôles lus dans le nom pour
    # l'addictologie (16 octobre 2026)
    lieux, roles_ms = roles_antennes(lieux, fin)
    lieux = roles_addictologie(lieux)
    # adresses vérifiées sur les sources des établissements, tout type, après les changements de type (31 octobre 2026)
    from . import adresses_verifiees
    lieux, verif["adresses_verifiees"] = adresses_verifiees.appliquer(lieux, ref, hors_ligne)
    # verdicts de la vérification à la main pour les types autres que les CMP (doublons, structures fermées), chacun
    # avec sa source datée (chantier des structures, 16 novembre 2026)
    from . import verdicts_structures
    lieux, verif["verdicts_structures"] = verdicts_structures.appliquer(lieux, ref)
    if verif["verdicts_structures"]["retirees"]:
        verif["non_retenues"] = list(verif["non_retenues"]) + verif["verdicts_structures"]["retirees"]
        _releve("Sources des établissements", "Structures autres que les CMP inscrites deux fois ou fermées, d'après "
                "une vérification à la main sourcée", len(verif["verdicts_structures"]["retirees"]), "Retirées")
    # un lieu de CMP, c'est une adresse et un public (décision 1 du chantier des structures, 16 novembre 2026)
    if config.CMP_UN_LIEU_PAR_ADRESSE:
        lieux, reunis = un_lieu_par_adresse_cmp(lieux)
        if reunis:
            verif["non_retenues"] = list(verif["non_retenues"]) + reunis
            _releve("FINESS et ROR", "CMP du même public à la même adresse (plusieurs secteurs dans un même lieu)",
                    len(reunis), "Comptés comme un seul lieu")
    # même structure inscrite sous deux gestionnaires (relecture du 22 novembre 2026) : chaque paire est relue, puis
    # laissée de côté avec sa source (inscriptions_laissees.csv) ou gardée comme deux structures distinctes
    paires = sv.meme_adresse_deux_gestionnaires(lieux)
    # le lecteur le sait : la structure non attestée de chaque paire porte, avec sa confirmation, « même adresse (ou même
    # rue) que ..., d'un autre gestionnaire, peut-être la même structure », sauf quand les sources les disent distinctes
    # (décision du 22 novembre 2026)
    distinctes = sv.paires_distinctes()
    lieux["meme_adresse_que"] = None
    lieux["meme_adresse_numero"] = None
    for p in paires:
        if p["autre_attestee"] or (p["type"], p["verifiee"], p["autre"]) in distinctes:
            continue
        parent = next((t[4].get("parent") for t in config.LIEUX_TYPES if t[0] == p["type"]), None)
        m = (lieux["lieu"] == lieux.at[p["i_autre"], "lieu"]) & lieux["type"].isin([p["type"], parent])
        lieux.loc[m, "meme_adresse_que"] = p["verifiee"]
        lieux.loc[m, "meme_adresse_numero"] = p["meme_numero"]
    JOURNAL.controle("Structures du même type à la même adresse sous deux gestionnaires, dont une attestée par sa liste "
                     "vérifiée, chacune relue : laissée de côté avec sa source, distincte d'après les sources, ou gardée dans le doute avec une mention",
                     "aucune" if not paires else f"{len(paires)}, dont " + " ; ".join(
                         f"{p['verifiee']} et {p['autre']}" for p in paires[:5]))
    if n_cattp_cmp:
        _releve("FINESS, ROR et Sirene", "CMP dont le nom, une unité du ROR ou l'enseigne Sirene annonce aussi un CATTP "
                "(« CMP-CATTP »), sans autre CATTP de leur gestionnaire dans la commune", n_cattp_cmp,
                "Un CATTP compté au même lieu que le CMP")
    if verif["non_retenues"] or verif["ajoutees"]:
        _releve("Sources des établissements", "Structures reprises une à une sur les sources des établissements "
                "vérifiés", int(lieux["verifiee"].sum()),
                f"{verif['ajoutees']} absentes des deux bases ajoutées, {len(verif['non_retenues'])} inscriptions des "
                f"bases non retenues")
    # chaque CMP pour adultes ou pour enfants a son CMP « tous publics » (sinon les comptes par public ne refont pas
    # le total publié)
    _cles_cmp = set(lieux.loc[lieux["type"] == "lieu_cmp", "lieu"])
    orphelins = lieux[lieux["type"].isin(["lieu_cmp_adultes", "lieu_cmp_enfants"]) & ~lieux["lieu"].isin(_cles_cmp)]
    JOURNAL.controle("CMP pour adultes ou pour enfants sans CMP tous publics (attendu, aucun)",
                     "aucun" if orphelins.empty else f"{len(orphelins)}, " + ", ".join(orphelins["nom"].astype(str)[:5]))
    JOURNAL.controle("Lieux déclarés deux fois à la même adresse, réunis",
                     f"{n_fus} structures réunies à une autre du même type, du même établissement, à la même adresse")
    pros = professionnels(lieux, act)
    exercice = exercice_structures(lieux, act, fin.drop_duplicates("nofinesset").set_index("nofinesset")["categetab"]
                                   if fin is not None else None)
    # comptes par territoire et couverture
    comptes = {}
    lieux["com"] = lieux["commune"]
    for niv in ("com", "epci", "dep", "reg"):
        comptes[niv] = lieux.groupby([niv, "type"]).size().rename("n").reset_index().rename(columns={niv: "code"})
    deps = set(ref.deps["code"]) - set(config.DEPARTEMENTS_EXCLUS_CROISEMENTS)
    couv = (lieux[lieux["dep"].isin(deps)].groupby("type")["dep"].nunique() / len(deps)).rename("part_departements")
    couv = couv.reindex([t[0] for t in config.LIEUX_TYPES]).fillna(0).reset_index().rename(columns={"index": "type"})
    couv["complet"] = couv["part_departements"] >= config.LIEUX_COUVERTURE_MIN
    # un type présent presque partout peut n'être recensé qu'en partie : les PMI, 1 152 dans la liste pour 4 616 points
    # fixes de consultation déclarés à la DREES en 2024 (constat C4 du 16 novembre 2026, décision 2, fermée tant
    # qu'elle n'est pas acceptée)
    if config.LIEUX_NON_RECENSES:
        couv.loc[couv["type"].isin(config.LIEUX_NON_RECENSES), "complet"] = False
    conc = (lieux.groupby(["dep", "type", "provenance"]).size().unstack(fill_value=0)
            .reindex(columns=list(PROVENANCES), fill_value=0).reset_index())
    # un lieu en milieu pénitentiaire et une équipe sans lieu propre restent listés, sans entrer dans les distances
    sans_dist = lieux["role_structure"].isin(config.ROLES_SANS_DISTANCE) if "role_structure" in lieux else False
    dist = distances(lieux[~sans_dist], ref, centres) if centres else None
    resume = resumer_distances(dist, ref) if dist is not None else None
    # contrôles
    prov = lieux["provenance"].value_counts()
    _enf = {t[0] for t in config.LIEUX_TYPES if t[4].get("parent")}
    _p = lieux.loc[~lieux["type"].isin(_enf), "provenance"].value_counts()
    _releve("FINESS et ROR", "Structures présentes dans les deux bases, rapprochées par le numéro FINESS, l'entité "
            "juridique et la commune, ou le nom", int(_p.get("les_deux", 0)),
            f"Comptées une seule fois ({nombre(int(_p.get('finess', 0)))} dans FINESS seul, "
            f"{nombre(int(_p.get('ror', 0)) + int(_p.get('ror_type', 0)))} dans le ROR seul, dont "
            f"{nombre(int(_p.get('ror_type', 0)))} unités hospitalières que FINESS ne distingue pas)")
    JOURNAL.controle("Structures de soins, réunion de FINESS et du ROR",
                     f"{nombre(len(lieux))} lieux-types, types rattachés compris (CMP par public, antennes), "
                     f"{nombre(prov.get('les_deux', 0))} dans les deux bases, "
                     f"{nombre(prov.get('finess', 0))} dans FINESS seul, {nombre(prov.get('ror', 0))} dans le ROR seul et "
                     f"{nombre(prov.get('ror_type', 0))} unités hospitalières du ROR, "
                     f"{nombre(stats['rapproches_entite_juridique'])} rapprochés par l'entité juridique et la commune")
    cmp_ = lieux[lieux["type"] == "lieu_cmp"]["provenance"].value_counts()
    JOURNAL.controle("CMP réunis (structures distinctes)",
                     f"{nombre(int(cmp_.sum()))}, dont {nombre(cmp_.get('les_deux', 0))} dans les deux bases, "
                     f"{nombre(cmp_.get('finess', 0))} dans FINESS seul, {nombre(cmp_.get('ror', 0))} dans le ROR seul"
                     # le reste vient des sources des établissements, absent des deux bases : la somme est complète
                     # (relecture du 17 novembre 2026)
                     + (f", {nombre(int(cmp_.sum()) - sum(int(cmp_.get(k, 0)) for k in ('les_deux', 'finess', 'ror')))} "
                        f"absents des deux bases, ajoutés depuis les sources des établissements"
                        if int(cmp_.sum()) > sum(int(cmp_.get(k, 0)) for k in ('les_deux', 'finess', 'ror')) else ""))
    prec = lieux["precision"].value_counts(normalize=True)
    JOURNAL.controle("Structures de soins, emplacement",
                     ", ".join(f"{PRECISIONS[k]} {v:.0%}".replace(".", ",") for k, v in prec.items() if k in PRECISIONS))
    hc = u[(u["champ"] == config.CHAMP_PSY) & u["mode"].isin(config.MODES_HC)]
    JOURNAL.controle("ROR, lits d'hospitalisation complète en psychiatrie (à comparer à la SAE)",
                     nombre(float(pd.to_numeric(hc["lits"], errors="coerce").sum())))
    incomplets = couv[~couv["complet"]]["type"].map(lambda t: labels[t][1]).tolist()
    if incomplets:
        JOURNAL.controle("Types de structures recensées dans moins de 90 % des départements (listés, non comparés)",
                         ", ".join(incomplets))
    # aucun établissement actif de FINESS de la catégorie d'un type ne doit manquer dans les lieux réunis (sous son
    # numéro ou rapproché d'un lieu du ROR), sinon un lieu aurait été perdu à la réunion
    perdus = []
    for tid, _l, _f, _g, r in config.LIEUX_TYPES:
        if not r.get("finess"):
            continue
        attendus = set(lf.loc[lf["type"] == tid, "finess"]) if len(lf) else set()
        g = lieux[lieux["type"] == tid]
        trouves = set(g["finess"].dropna()) | set(g.get("finess_rapproche", pd.Series(dtype=object)).dropna())
        trouves |= {n for v in g.get("finess_absorbes", pd.Series(dtype=object)).dropna() for n in str(v).split(",")}
        # une inscription écartée par la liste vérifiée de son établissement est consignée, pas perdue
        trouves |= {n for r in verif["non_retenues"] if isinstance(r.get("finess"), str) for n in r["finess"].split(",")}
        if attendus - trouves:
            perdus.append(f"{labels[tid][1]} {len(attendus - trouves)}")
    JOURNAL.controle("Structures de soins, établissements de FINESS perdus à la réunion (attendu, aucun)",
                     "aucun" if not perdus else ", ".join(perdus))
    # confrontation aux chiffres publiés (références du registre) et aux lits de la SAE
    refs = []
    for tid, n_pub, date_pub, quoi, (titre, url) in lieux_profil.references():
        n = int((lieux["type"] == tid).sum())
        refs.append({"type": tid, "lieux": n, "reference": n_pub, "date_reference": date_pub, "objet": quoi,
                     "ecart": n / n_pub - 1, "source": titre, "adresse": url})
        JOURNAL.controle(f"Structures de soins, {labels[tid][1].lower()}, rapprochées du chiffre publié",
                         f"{nombre(n)} lieux, {nombre(n_pub)} {quoi} ({date_pub}, {titre})")
    references = pd.DataFrame(refs)
    return {"lieux": lieux, "pros": pros, "comptes": comptes, "couverture": couv, "concordance": conc,
            "references": references,
            "distances_communes": dist, "distances": resume, "stats": stats, "unites_cmp_ror": unites_cmp, "relecture": pd.DataFrame(RELEVE), "verification": verif, "sirene_seul": sirene_seul,
            "unites_cmp_ror_ej": unites_cmp_ej, "exercice": exercice}
