"""Lecture grand public. Un glossaire unique (repris par le rapport et par l'atlas) et des
fonctions qui traduisent les résultats chiffrés en phrases simples, avec les précautions utiles.
Les seuils utilisés ici sont repris à l'identique dans l'atlas (atlas_template.html)."""
from __future__ import annotations

import math

import numpy as np
import re

SM = "Santé mentale"

# (identifiant, terme, définition, famille). Une famille vide signifie que la notion vaut pour
# toute l'offre de soins. L'atlas filtre le glossaire selon la famille choisie.
GLOSSAIRE = [
    ("lieux", "Structures de soins",
     "Établissements ou services de soins (CMP, CMPP, CAMSP, hôpital de jour, service d'urgences, maternité, "
     "établissement médico-social...) recensés par FINESS ou par le Répertoire opérationnel des ressources (ROR), à une "
     "adresse donnée. Deux structures distinctes à la même adresse comptent pour deux, une même structure décrite par les "
     "deux bases ou inscrite deux fois ne compte qu'une fois. Une structure n'est pas une capacité, et les structures ne "
     "s'ajoutent pas aux professionnels, elles se lisent à côté.", ""),
    ("acces_lieux", "Accès aux structures de soins",
     "Le temps de trajet vient de l'INSEE, en voiture aux heures creuses, vers l'équipement le plus proche recensé "
     "dans sa base des équipements. La distance à la structure de soins la plus proche est mesurée ici à vol d'oiseau, depuis "
     "le centre de la commune des habitants. Ce n'est pas un temps de trajet. Pour un territoire, la valeur donnée est "
     "la médiane des habitants, la moitié d'entre eux est plus près, l'autre moitié plus loin.", ""),
    ("densite", "Densité pour 10 000 habitants",
     "Nombre de professionnels rapporté à la population. Une densité de 5 signifie 5 professionnels pour 10 000 "
     "habitants, soit environ un pour 2 000 habitants. C'est la mesure qui permet de comparer un petit territoire "
     "et une grande ville.", ""),
    ("moyenne", "Moyenne des territoires",
     "Densité de référence à laquelle un territoire est comparé, par exemple la moyenne des départements. C'est le "
     "nombre de professionnels de tous les départements rapporté à la population de la France, compté comme pour "
     "chaque département, avec les seules activités de soins qui ont un lieu d'exercice. Elle diffère un peu du "
     "chiffre de la France entière, qui compte chaque personne une fois, y compris les remplacements et les "
     "activités non rattachées à un territoire (téléconsultation, activités sans soins à la population).", ""),
    ("effectif", "Effectif",
     "Nombre de personnes distinctes qui déclarent exercer dans le territoire. Une personne qui exerce dans deux "
     "territoires compte dans chacun, mais une seule fois pour la France entière.", ""),
    ("modes", "Libéral, salarié",
     "Le mode d'exercice déclaré au répertoire RPPS. Libéral signifie installé à son compte (cabinet), salarié "
     "signifie employé par un hôpital, un centre, une association ou une collectivité. Une même personne peut "
     "avoir les deux.", ""),
    ("familles", "Santé mentale et santé",
     "Les professions sont réparties en deux familles. La santé mentale réunit les psychologues, les "
     "psychothérapeutes, les psychiatres et les pédopsychiatres. La santé réunit toutes les autres professions. "
     "Les psychomotriciens, orthophonistes, ergothérapeutes et infirmiers sont rangés en santé, même si une partie "
     "d'entre eux travaille en psychiatrie. Ceux-là apparaissent dans le périmètre élargi.", ""),
    ("elargi", "Périmètre élargi de la santé mentale",
     "Toutes les personnes salariées d'un établissement psychiatrique ou médico-psychologique (centre hospitalier "
     "spécialisé, CMP, CATTP, CMPP, BAPU, CSAPA...), quelle que soit leur profession. Il fait apparaître les "
     "infirmiers, psychomotriciens ou ergothérapeutes du secteur psychiatrique. Il se lit à côté du périmètre "
     "strict, jamais à sa place, et les deux ne s'additionnent pas. Les services de psychiatrie des hôpitaux "
     "généraux n'y figurent pas, faute de pouvoir les repérer dans les données.", SM),
    ("specialite", "Spécialité ordinale",
     "La spécialité sous laquelle un médecin est inscrit à l'Ordre des médecins. Chaque médecin n'en a qu'une, "
     "ce qui permet de compter chaque personne une seule fois.", ""),
    ("qualification", "Qualification complémentaire",
     "Un médecin peut avoir, en plus de sa spécialité, une compétence, une capacité ou un diplôme complémentaire, "
     "par exemple en addictologie ou en psychiatrie de l'enfant. Ces comptages montrent qui détient la "
     "qualification. Un même médecin y figure en plus de sa spécialité, on ne peut donc pas les additionner aux "
     "professions. C'est pourquoi l'atlas donne deux chiffres pour la pédopsychiatrie, les pédopsychiatres "
     "inscrits comme tels et l'ensemble des psychiatres qualifiés pour l'enfant et l'adolescent.", SM),
    ("epci", "Intercommunalité",
     "Regroupement de communes (communauté de communes, d'agglomération, urbaine ou métropole). Il y en a environ "
     "1 250 en France. C'est une échelle proche des bassins de vie, plus fine que le département et moins "
     "instable que la commune, où beaucoup de petites communes n'ont aucun professionnel par simple effet de "
     "taille.", ""),
    ("indice100", "Indice 100",
     "Comparaison à la moyenne des territoires du même niveau. Un indice de 150 signifie une densité supérieure de "
     "moitié à cette moyenne, un indice de 50 une densité deux fois plus faible.", ""),
    ("gini", "Indice de Gini",
     "Mesure de l'inégalité de répartition, entre 0 et 1. À 0, chaque territoire a exactement autant de "
     "professionnels que son poids dans la population. Plus on s'approche de 1, plus les professionnels sont "
     "concentrés dans quelques territoires. En pratique, en dessous de 0,2 la répartition est assez homogène, "
     "au-delà de 0,5 elle est très concentrée.", ""),
    ("lorenz", "Courbe de Lorenz",
     "On classe les territoires du moins bien doté au mieux doté, puis on regarde quelle part des professionnels "
     "dessert quelle part de la population. Si la répartition était parfaitement égale, la courbe suivrait la "
     "diagonale. Plus elle s'en écarte vers le bas, plus l'offre est inégale.", ""),
    ("sans_pro", "Population sans aucun professionnel",
     "Part des habitants qui vivent dans un territoire où personne de la profession ne déclare exercer. "
     "Cela ne veut pas dire qu'ils n'y ont pas accès, le professionnel le plus proche peut être juste à côté.", ""),
    ("correlation", "Corrélation de rang (Spearman)",
     "Indique si deux choses varient ensemble d'un territoire à l'autre. Elle va de -1 à +1. Positive, les "
     "territoires où l'indicateur est élevé ont plutôt plus de professionnels. Négative, plutôt moins. Proche de 0, "
     "pas de lien visible. On l'appelle « de rang » parce qu'elle compare des classements, ce qui la rend peu "
     "sensible aux valeurs extrêmes.", ""),
    ("force", "Force d'un lien",
     "Par convention, une corrélation inférieure à 0,1 en valeur absolue est négligeable, de 0,1 à 0,3 faible, "
     "de 0,3 à 0,5 modérée, au-delà forte. Un lien faible peut être réel, mais il explique peu de chose.", ""),
    ("effet_ville", "Effet ville",
     "Les villes concentrent à la fois les hôpitaux, les cabinets et certaines populations (personnes seules, "
     "familles monoparentales, ménages pauvres). Beaucoup de liens entre l'offre et le profil des habitants "
     "viennent de là. Une corrélation brute ne dit donc pas si le lien tient encore entre territoires aussi "
     "urbains l'un que l'autre. C'est pourquoi le rapport et l'atlas donnent aussi la corrélation à densité de "
     "population égale, qui retire cet effet.", ""),
    ("escalier", "Escalier social",
     "Les territoires sont classés du plus modeste au plus aisé selon le niveau de vie médian de leurs habitants, "
     "puis regroupés en dix tranches qui réunissent chacune un dixième de la population. Chaque marche donne la "
     "densité de professionnels de la tranche. Une très grande intercommunalité peut remplir presque seule une "
     "tranche, ce qui crée des ruptures dans l'escalier.", ""),
    ("concentration", "Indice de concentration",
     "Résume en un nombre la répartition des professionnels entre territoires modestes et aisés. Il vaut 0 si les "
     "professionnels suivent la population, il est positif s'ils sont plus présents dans les territoires aisés et "
     "négatif s'ils le sont dans les territoires modestes. Il va de -1 à +1.", ""),
    ("entonnoir", "Diagramme en entonnoir",
     "Dans un petit territoire, quelques arrivées ou départs font beaucoup varier la densité. Le diagramme place "
     "chaque territoire selon sa population et sa densité, et trace autour de la moyenne des territoires des limites qui "
     "se resserrent quand la population augmente. Entre les limites, l'écart à la moyenne peut tenir au hasard. "
     "Sous la limite basse à 99,8 %, le territoire est nettement en dessous, ce que le hasard expliquerait au plus "
     "deux fois sur mille.", ""),
    ("q", "Significativité corrigée (q)",
     "Quand on teste des centaines de croisements, certains paraissent liés par pur hasard. La valeur q corrige "
     "cet effet (méthode de Benjamini-Hochberg). En dessous de 0,05, le lien a peu de chances d'être un artefact. "
     "Comme les données couvrent tous les professionnels et non un échantillon, ce critère reste indicatif, la "
     "force du lien compte davantage.", ""),
    ("ic", "Intervalle de confiance",
     "Fourchette dans laquelle la vraie valeur a de bonnes chances de se trouver si les territoires avaient été "
     "un peu différents. Elle est calculée en refaisant le calcul des centaines de fois sur des tirages au hasard "
     "parmi les territoires (bootstrap). Une fourchette étroite signifie un résultat stable.", ""),
    ("attendu", "Écart à l'attendu",
     "On estime combien de professionnels on trouverait dans un territoire s'il ressemblait aux "
     "territoires de même profil (âge, revenus, pauvreté, densité de population...). Un rapport de 1 signifie "
     "conforme à ce profil, 0,5 deux fois moins que prévu, 2 deux fois plus. Ce n'est pas une mesure du besoin de "
     "soins, seulement une comparaison avec des territoires semblables (modèle de régression de Poisson).", ""),
    ("gradient", "Gradient urbain et rural",
     "Comparaison des densités de professionnels entre territoires classés selon leur densité de population, "
     "des plus ruraux aux plus urbains.", ""),
    ("typologie", "Typologie",
     "Regroupement statistique des intercommunalités qui ont un profil d'offre semblable, séparément pour la "
     "santé mentale, pour la santé et pour l'ensemble (classification ascendante hiérarchique, méthode de Ward). Le "
     "nombre de groupes est choisi pour qu'ils soient le plus distincts possible. Le nom de chaque groupe résume ses "
     "indices.", ""),
    ("regression_multiple", "Régression multiple",
     "Méthode qui décrit le lien entre un indicateur et plusieurs autres à la fois. Chaque coefficient dit de combien "
     "l'indicateur étudié varie quand un autre augmente, les autres restant égaux. Il peut différer du lien simple entre "
     "deux indicateurs, car il retire ce que les autres expliquent déjà. Sur des territoires, il décrit des ensembles et "
     "ne dit rien des personnes ni d'une cause.", ""),
    ("acp", "Analyse en composantes principales",
     "Méthode qui résume plusieurs densités en quelques axes. Chaque axe réunit les professions qui varient ensemble "
     "d'un territoire à l'autre, et sa part indique combien des différences entre territoires il résume. La "
     "corrélation d'une profession avec un axe, de -1 à +1, dit combien elle y pèse. Les axes décrivent des "
     "territoires et ne disent rien d'une cause.", ""),
    ("moran", "Ressemblance entre voisins (indice de Moran)",
     "Indique si les territoires voisins se ressemblent. Positif, les territoires bien dotés ont tendance à être "
     "voisins entre eux, de même pour les moins bien dotés, ce qui dessine des zones sur la carte. Proche de 0, "
     "la situation d'un territoire ne dit rien de ses voisins.", ""),
    ("accessibilite", "Accessibilité",
     "Mesure qui tient compte à la fois de la distance aux professionnels et du nombre d'habitants qui se les "
     "partagent, y compris dans les communes voisines (jusqu'à 20 km, avec un poids qui baisse avec la "
     "distance). Elle s'exprime comme une densité, en professionnels pour 10 000 habitants. Elle s'inspire de "
     "l'indicateur APL de la DREES, mais avec des distances à vol d'oiseau et sans tenir compte de l'activité "
     "des professionnels.", ""),
    ("apl", "Accessibilité potentielle localisée (APL)",
     "Indicateur officiel de la DREES, calculé par commune pour les médecins généralistes, les infirmiers, les "
     "masseurs-kinésithérapeutes, les sages-femmes et les chirurgiens-dentistes. Il tient compte des temps de "
     "trajet par la route, du volume d'activité de chaque professionnel et des besoins liés à l'âge des habitants. "
     "Il n'existe pas pour les psychologues ni pour les psychiatres. Le rapport s'en sert pour vérifier son propre "
     "calcul d'accessibilité.", ""),
    ("temps_trajet", "Temps de trajet",
     "Durée d'un trajet en voiture, aux heures creuses, entre le lieu de résidence et l'équipement ou le "
     "professionnel libéral le plus proche, calculée par l'INSEE pour chaque carré habité de 200 mètres de côté. "
     "Le temps médian est celui en dessous duquel vit la moitié des habitants.", ""),
    ("zones","Zones peu dotées et zones de concentration",
     "Un territoire mal doté n'est pas forcément un désert, ses habitants peuvent consulter juste à côté. Une zone "
     "peu dotée réunit des territoires voisins tous en dessous de la moyenne, ce qui rend le recours de proximité "
     "plus difficile. Une zone de concentration est l'inverse. Ces zones sont repérées par un calcul qui vérifie "
     "que la ressemblance entre voisins ne tient pas au hasard (indice de Moran local).", ""),
    ("ecologique", "Corrélation n'est pas causalité",
     "Tous les liens décrits ici portent sur des territoires, pas sur des personnes. Si les territoires aisés "
     "comptent plus de psychologues, cela ne dit ni que les personnes aisées consultent davantage, ni que le "
     "revenu attire les psychologues. D'autres facteurs, comme la présence d'une université ou d'un hôpital, "
     "peuvent expliquer les deux.", ""),
    ("rpps", "Ce que mesure le RPPS",
     "Le répertoire national des professionnels de santé enregistre des lieux d'exercice déclarés. Il ne dit rien "
     "du temps de travail, des délais d'attente ni du nombre de patients reçus. Deux territoires avec la même "
     "densité peuvent offrir un accès très différent.", ""),
]
DEFINITIONS = {g[0]: g[2] for g in GLOSSAIRE}

# Explication de chaque indicateur de contexte (identifiants de config.CONTEXTE)
EXPLICATIONS_CONTEXTE = {
    "densite_pop": "Nombre d'habitants par kilomètre carré. Elle distingue les territoires ruraux des territoires "
                   "urbains.",
    "part_0_14": "Part des habitants de moins de 15 ans, recensement de la population.",
    "part_15_24": "Part des habitants de 15 à 24 ans, recensement de la population.",
    "part_65_79": "Part des habitants de 65 à 79 ans, recensement de la population.",
    "part_80p": "Part des habitants de 80 ans ou plus, recensement de la population.",
    "revenu_median": "Niveau de vie qui partage les habitants en deux moitiés égales. Il tient compte de la taille "
                     "du ménage (revenu disponible par unité de consommation, source Filosofi).",
    "taux_pauvrete": "Part des habitants dont le niveau de vie est inférieur à 60 % du niveau de vie médian "
                     "national.",
    "taux_chomage": "Part des chômeurs parmi les actifs de 15 à 64 ans, au sens du recensement (déclaration des "
                    "personnes, différente du chômage au sens du BIT).",
    "part_cadres": "Part des cadres et professions intellectuelles supérieures parmi les 15 ans ou plus, "
                   "retraités compris dans le dénominateur.",
    "part_ouvriers": "Part des ouvriers parmi les 15 ans ou plus, retraités compris dans le dénominateur.",
    "part_monoparentales": "Part des familles composées d'un seul parent avec au moins un enfant.",
    "part_seuls": "Part des personnes de 15 ans ou plus qui vivent seules dans leur logement.",
    "taux_emploi": "Part des personnes de 15 à 64 ans qui ont un emploi.",
    "salaire_moyen": "Salaire net mensuel moyen des salariés qui habitent le territoire, en équivalent temps plein.",
    "part_sans_diplome": "Part des personnes de 15 ans ou plus sorties de l'école sans diplôme ou avec le seul "
                         "certificat d'études.",
    "part_emplois_precaires": "Part des personnes en emploi qui ont un contrat à durée limitée (CDD, intérim, "
                              "emplois aidés, apprentissage, stage), selon le recensement de l'INSEE.",
    "part_logements_suroccupes": "Part des résidences principales qui comptent moins de pièces que le nombre "
                                 "jugé nécessaire pour le ménage.",
    "part_80p_seuls": "Part des personnes de 80 ans ou plus qui vivent seules, un repère de l'isolement des plus âgés.",
    "part_logement_social": "Part des résidences principales louées dans le parc social (HLM).",
    "part_minima_sociaux": "Part des minima sociaux (RSA, minimum vieillesse, AAH...) dans le revenu disponible des "
                           "habitants.",
}


# ---------------------------------------------------------------- dates
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]


def date_longue(d: str) -> str:
    """« 2026-10-04 » devient « 4 octobre 2026 », « 2026-10-01 » devient « 1er octobre 2026 »."""
    a, m, j = (int(x) for x in str(d)[:10].split("-"))
    return f"{j}{'er' if j == 1 else ''} {MOIS[m - 1]} {a}"


# ---------------------------------------------------------------- nombres
def nombre(x, d=0) -> str:
    """Nombre au format français, espace insécable pour les milliers (le nombre ne se coupe pas en fin de ligne),
    virgule décimale."""
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return ""
    s = f"{x:,.{d}f}".replace(",", " ").replace(".", ",")
    # pas de « -0,00 » pour une valeur qui s'arrondit à zéro
    return s[1:] if s.startswith("-") and not s.strip("-0,") else s


def pct(x, d=1) -> str:
    """Proportion (entre 0 et 1) en pourcentage français."""
    if x is None or not math.isfinite(x):
        return ""
    if x == 0:
        return "0 %"
    if 0 < abs(x) < .5 * 10 ** -(d + 2):   # trop petit pour la précision demandée, mais pas nul
        return f"moins de {nombre(10 ** -d, d)} %"
    return nombre(100 * x, d) + " %"


# ---------------------------------------------------------------- libellés
_MOTS_LIAISON = {"de", "du", "des", "d", "en", "pour", "a", "au", "aux", "l", "la", "le", "et"}


def pluriel(libelle: str) -> str:
    """Pluriel d'un libellé de profession, en minuscules. « Médecin généraliste » devient
    « médecins généralistes ». Seuls les mots placés avant la première préposition s'accordent."""
    out, fige = [], False
    for mot in libelle.lower().split(" "):
        m = re.match(r"^(.*?)([,.;]*)$", mot)
        corps, ponct = m.group(1), m.group(2)
        if fige or not corps or corps.split("'")[0] in _MOTS_LIAISON or corps.startswith("("):
            fige = True
            out.append(mot)
            continue
        parts = []
        for p in corps.split("-"):
            if not p or p.endswith(("s", "x")):
                parts.append(p)
            elif p.endswith("al"):
                parts.append(p[:-2] + "aux")
            else:
                parts.append(p + "s")
        out.append("-".join(parts) + ponct)
    return " ".join(out)


# ---------------------------------------------------------------- phrases
def force(rho: float) -> str:
    a = abs(rho)
    return "négligeable" if a < .1 else "faible" if a < .3 else "modéré" if a < .5 else "fort"


def phrase_gini(g: float) -> str:
    if g < .2:
        return "assez homogène sur le territoire"
    if g < .35:
        return "modérément inégale"
    if g < .5:
        return "nettement inégale"
    return "très concentrée dans certains territoires"


def un_pour(densite: float) -> str:
    if not densite or densite <= 0 or not math.isfinite(densite):
        return ""
    n = 1e4 / densite
    arrondi = round(n, -2) if n >= 1000 else round(n, -1) if n >= 100 else round(n)
    return f"un pour {int(arrondi):,} habitants".replace(",", " ")


def de(mot: str) -> str:
    """« de psychologues », mais « d'infirmiers »."""
    return ("d'" if mot[:1].lower() in "aeiouyéèêàâîôûh" else "de ") + mot


def minuscule(libelle: str) -> str:
    """Première lettre en minuscule, sauf pour un sigle (AAH, RSA...)."""
    if not libelle or (len(libelle) > 1 and libelle[1].isupper()):
        return libelle
    return libelle[0].lower() + libelle[1:]


def phrase_correlation(rho: float, indicateur: str, profession: str, ic=None) -> str:
    """Phrase descriptive d'une corrélation de rang. Quand l'intervalle de confiance est donné et contient zéro, le
    lien n'est pas présenté comme établi."""
    if not math.isfinite(rho):
        return ""
    f = force(rho)
    if ic is not None and all(math.isfinite(x) for x in ic) and ic[0] < 0 < ic[1] and f != "négligeable":
        r, a, b = (f"{x:.2f}".replace(".", ",") for x in (rho, *ic))
        return (f"Aucun lien net n'apparaît entre l'indicateur « {minuscule(indicateur)} » et la présence "
                f"{de(pluriel(profession))}. La corrélation mesurée ({r}) est trop incertaine pour conclure, elle "
                f"pourrait aussi bien être nulle (fourchette plausible de {a} à {b}).")
    if f == "négligeable":
        return f"Aucun lien notable entre l'indicateur « {minuscule(indicateur)} » et la présence {de(pluriel(profession))}."
    sens = "plus" if rho > 0 else "moins"
    r = f"{rho:.2f}".replace(".", ",")
    return (f"Les territoires où l'indicateur « {minuscule(indicateur)} » est élevé comptent plutôt {sens} "
            f"{de(pluriel(profession))}. Le lien est {f} (rho = {r}).")


def phrase_correlations(items, indicateur: str) -> str:
    """Une phrase pour les liens d'un indicateur avec plusieurs professions. items, liste de (profession, rho, ic).
    Les liens nets sont regroupés par sens, les liens nuls ou incertains en une seule mention."""
    if len(items) == 1:
        return phrase_correlation(items[0][1], indicateur, items[0][0], items[0][2])
    plus, moins, nuls = [], [], []
    for prof, rho, ic in items:
        if not math.isfinite(rho):
            continue
        incertain = ic is not None and all(math.isfinite(x) for x in ic) and ic[0] < 0 < ic[1]
        if force(rho) == "négligeable" or incertain:
            nuls.append(prof)
        else:
            (plus if rho > 0 else moins).append(f"{de(pluriel(prof))} (lien {force(rho)}, rho = {rho:.2f})".replace(".", ","))

    def liste(xs):
        return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " et " + xs[-1]
    ind = minuscule(indicateur)
    morceaux = []
    if plus:
        morceaux.append("plutôt plus " + liste(plus))
    if moins:
        morceaux.append("plutôt moins " + liste(moins))
    ph = (f"Les territoires où l'indicateur « {ind} » est élevé comptent " + ", et ".join(morceaux) + ".") if morceaux else ""
    if nuls:
        q = [de(pluriel(p)) for p in nuls]
        ou = q[0] if len(q) == 1 else ", ".join(q[:-1]) + " ou " + q[-1]
        ph += (" " if ph else "") + (f"Aucun lien net n'apparaît avec la présence {ou}." if morceaux else
                                     f"Aucun lien net entre l'indicateur « {ind} » et la présence {ou}.")
    return ph


def fois(a: float, b: float) -> str:
    """Formule « 2,3 fois plus » ou « 40 % de moins » selon le rapport a / b."""
    if not b or not math.isfinite(a / b):
        return ""
    r = a / b
    if r >= 1.5:
        return f"{r:.1f} fois plus".replace(".", ",")
    if r >= 1:
        return f"{(r - 1) * 100:.0f} % de plus"
    if r > .67:
        return f"{(1 - r) * 100:.0f} % de moins"
    return f"{1 / r:.1f} fois moins".replace(".", ",") if r > 0 else "aucun"


def nom_classe(indices: dict) -> str:
    """Nom lisible d'une classe de la typologie à partir de ses indices (100 = moyenne des intercommunalités).
    indices associe un libellé de profession à son indice. Seuils, en dessous de 80 moins doté, au-dessus de 120
    mieux doté, « nettement » quand l'indice médian est sous 50 ou au-dessus de 180. Formulation descriptive, sans
    jugement."""
    if not indices:
        return ""
    n = len(indices)
    bas = sorted([p for p, v in indices.items() if v < 80], key=indices.get)
    haut = sorted([p for p, v in indices.items() if v > 120], key=indices.get, reverse=True)
    med = float(np.median(list(indices.values())))

    def liste(ps):
        ps = [pluriel(p) for p in ps[:3]]
        return ps[0] if len(ps) == 1 else ", ".join(ps[:-1]) + " et " + ps[-1]
    if len(bas) >= .8 * n:
        nom = ("Territoires nettement moins dotés" if med < 50 else "Territoires moins dotés") + " pour presque toutes les professions"
        return nom + (f", mieux dotés pour les {liste(haut)}" if haut else
                      f", sauf pour les {liste([p for p in indices if indices[p] >= 100])}"
                      if any(v >= 100 for v in indices.values()) else "")
    if len(haut) >= .8 * n:
        nom = ("Territoires nettement mieux dotés" if med > 180 else "Territoires mieux dotés") + " pour presque toutes les professions"
        return nom + (f", moins dotés pour les {liste(bas)}" if bas else
                      f", sauf pour les {liste([p for p in indices if indices[p] <= 100])}"
                      if any(v <= 100 for v in indices.values()) else "")
    if len(bas) >= .5 * n:
        return f"Territoires plutôt moins dotés, surtout pour les {liste(bas)}" + (
            f", mieux dotés pour les {liste(haut)}" if haut else "")
    if len(haut) >= .5 * n:
        return f"Territoires plutôt mieux dotés, surtout pour les {liste(haut)}" + (
            f", moins dotés pour les {liste(bas)}" if bas else "")
    if not bas and not haut:
        return "Territoires proches de la moyenne"
    morceaux = []
    if bas:
        morceaux.append(f"moins dotés pour les {liste(bas)}")
    if haut:
        morceaux.append(f"mieux dotés pour les {liste(haut)}")
    return "Territoires proches de la moyenne, " + ", ".join(morceaux)


def ecart_moyenne(indice: float) -> str:
    """Écart d'un indice (100 = moyenne) dit en mots, « environ 9 fois moins », « environ 2,4 fois moins »,
    « environ 20 % de moins »."""
    r = indice / 100
    if r <= 0 or not math.isfinite(r):
        return "aucun professionnel"
    if r < .67 or r > 1.5:
        x = 1 / r if r < 1 else r
        return f"environ {x:.0f} fois {'moins' if r < 1 else 'plus'}" if x >= 3 else             f"environ {x:.1f} fois {'moins' if r < 1 else 'plus'}".replace(".", ",")
    # arrondi à 5 % près, deux groupes très proches gardent alors le même écart et sont départagés par l'indice
    return f"environ {round(abs(r - 1) * 20) * 5} % de {'moins' if r < 1 else 'plus'}"


def noms_classes(profils: dict) -> dict:
    """Noms de toutes les classes d'une typologie. Quand deux noms se répètent, chacun reçoit l'écart de son indice
    médian à la moyenne, dit en mots (« environ 9 fois moins que la moyenne »), et l'indice médian en dernier
    recours si ces écarts se confondent. profils associe le numéro de classe à ses indices."""
    noms = {k: nom_classe(v) for k, v in profils.items()}
    med = {k: float(np.median(list(v.values()))) for k, v in profils.items()}
    doubles = {nom for nom in noms.values() if list(noms.values()).count(nom) > 1}
    out = {k: f"{nom} ({ecart_moyenne(med[k])} que la moyenne)" if nom in doubles else nom for k, nom in noms.items()}
    encore = {nom for nom in out.values() if list(out.values()).count(nom) > 1}
    return {k: f"{nom[:-1]}, indice médian {round(med[k])})" if nom in encore else nom for k, nom in out.items()}
