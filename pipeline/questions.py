"""Table unique des questions de l'offre de soins (structure du site validée le 26 novembre 2026, « un seul lieu par
question », prototypes/structure_2026-11-25/notes.md, partie 1).

Le lieu principal d'une question est la section où son résultat publié est montré et expliqué : les pages de famille
(Santé mentale, Santé) pour leurs questions, Explorer pour les deux questions qui n'existent que là. Explorer et Croiser
sont les lieux des réglages et y renvoient. Les pages de famille, la page « Offre de soins », l'accueil, les thèmes,
la recherche et Explorer lisent leurs titres ici : une question porte le même titre partout.

FAMILLES : pour chaque famille, ses questions dans l'ordre de la page (q1, q2, ...), chacune avec son titre, l'intertitre
de la section du rapport qu'elle reprend, ses figures, une autre page utile, et l'endroit où elle se règle :
  ("explorer", question d'Explorer, fenêtre de la figure ou None) ou ("croiser", None, None), ou None.
EXPLORER : titre de chaque question d'Explorer, dans l'ordre de la page, par l'ancre de sa section.
EXPLORER_SEULEMENT : les questions sans section dans une page de famille, dont Explorer est le lieu principal.
"""
from __future__ import annotations

import re

# titres unifiés entre les pages de famille et Explorer (le plus précis des deux, notes.md, partie 1)
NIVEAU_DE_VIE = "L’offre suit-elle le niveau de vie des habitants ?"
DISTANCE = "À quelle distance sont les structures de soins ?"
DISTANCE_SM = "À quelle distance sont les structures de soins psychiques ?"
ADDICTO = "De l’offre aux consommations en addictologie"
PROFIL = "L’offre suit-elle le profil des habitants ?"
SANS_L_AUTRE = "Où trouve-t-on une profession sans l’autre ?"

EXPLORER = {
    "qInegalites": NIVEAU_DE_VIE,
    "qDistances": DISTANCE,
    "qTypologie": "Quels profils d’offre distinguent les intercommunalités ?",
    "qPaires": SANS_L_AUTRE,
    "qTraj": "Les départements modestes rattrapent-ils leur retard depuis 2016 ?",
    "qAddicto": ADDICTO,
    "qCroisements": PROFIL,
}
EXPLORER_SEULEMENT = ["qTypologie", "qTraj"]

_CROISER = ("croiser", None, None)
FAMILLES = {
    "sm": [
        {"titre": "Combien de professionnels, et où exercent-ils ?", "intertitre": "Les professions de santé mentale",
         "figures": ["carte_dep_sm", "lorenz_sm"], "autre": None, "reglage": ("explorer", "qInegalites", "iFenConcentration")},
        {"titre": "Qui est compté dans les densités ?", "intertitre": "Du répertoire aux densités",
         "figures": ["parcours_sm"], "autre": None, "reglage": None},
        {"titre": NIVEAU_DE_VIE, "intertitre": "Offre selon le niveau de vie des territoires",
         "figures": ["escalier_sm"], "autre": None, "reglage": ("explorer", "qInegalites", "iFenEscalier")},
        {"titre": DISTANCE_SM, "intertitre": "Distance aux structures de soins selon le niveau de vie et le type de territoire",
         "figures": ["eloignement_sm"], "autre": ("zone.html", "Autour d’un lieu, les structures de votre zone"),
         "reglage": ("explorer", "qDistances", None)},
        {"titre": "Quelle accessibilité, au-delà de la distance ?", "intertitre": "Distance et accessibilité",
         "figures": ["distance_sm"], "autre": None, "reglage": None},
        {"titre": "Quels territoires s’écartent plus que le hasard ?", "intertitre": "Écarts qui dépassent le hasard",
         "figures": ["entonnoir_sm"], "autre": None, "reglage": ("explorer", "qInegalites", "iFenEntonnoir")},
        {"titre": PROFIL, "intertitre": "Liens avec le profil des habitants", "figures": ["effet_ville_sm"],
         "autre": ("croiser.html", "Croiser librement deux indicateurs"), "reglage": _CROISER},
        {"titre": "L’offre est-elle là où les indicateurs de recours sont élevés ?",
         "intertitre": "Offre face aux indicateurs de santé mentale", "figures": ["quadrants_sm"],
         "autre": ("croiser.html", "Croiser librement deux indicateurs"), "reglage": _CROISER},
        {"titre": "Qui porte l’offre ?", "intertitre": "Qui porte l'offre", "figures": ["porte_sm"], "autre": None,
         "reglage": None},
        {"titre": SANS_L_AUTRE, "intertitre": "Quelles professions sont présentes ensemble",
         "figures": ["combinaisons_sm"], "autre": None, "reglage": ("explorer", "qPaires", "paires")},
        {"titre": ADDICTO, "intertitre": "Consommations d'alcool et de tabac, par région", "figures": ["addicto_regions"],
         "autre": None, "reglage": ("explorer", "qAddicto", None)},
    ],
    "sante": [
        {"titre": "Combien de professionnels, et où exercent-ils ?", "intertitre": "Les professions de santé",
         "figures": ["carte_dep_sante", "lorenz_sante"], "autre": None,
         "reglage": ("explorer", "qInegalites", "iFenConcentration")},
        {"titre": "Qui est compté dans les densités ?", "intertitre": "Du répertoire aux densités",
         "figures": ["parcours_sante"], "autre": None, "reglage": None},
        {"titre": NIVEAU_DE_VIE, "intertitre": "Offre selon le niveau de vie des territoires",
         "figures": ["escalier_sante"], "autre": None, "reglage": ("explorer", "qInegalites", "iFenEscalier")},
        {"titre": DISTANCE, "intertitre": "Distance aux structures de soins selon le niveau de vie et le type de territoire",
         "figures": ["eloignement_sante"], "autre": ("zone.html#fam=sante", "Autour d’un lieu, les structures de votre zone"),
         "reglage": ("explorer", "qDistances", None)},
        {"titre": "Quelle accessibilité, au-delà de la distance ?", "intertitre": "Distance et accessibilité",
         "figures": ["distance_sante"], "autre": None, "reglage": None},
        {"titre": "Quels territoires s’écartent plus que le hasard ?", "intertitre": "Écarts qui dépassent le hasard",
         "figures": ["entonnoir_sante"], "autre": None, "reglage": ("explorer", "qInegalites", "iFenEntonnoir")},
        {"titre": PROFIL, "intertitre": "Liens avec le profil des habitants", "figures": ["effet_ville_sante"],
         "autre": ("croiser.html", "Croiser librement deux indicateurs"), "reglage": _CROISER},
        {"titre": "Qui porte l’offre ?", "intertitre": "Qui porte l'offre", "figures": ["porte_sante"], "autre": None,
         "reglage": None},
    ],
}
PAGES = {"sm": ("sante-mentale", "Santé mentale"), "sante": ("sante", "Santé")}
# intertitres renommés, avec leur ancien nom, que garde un rapport écrit avant le changement (une mesure n'est jamais
# présentée comme un besoin de soins, audit du 27 novembre 2026) : la page de domaine retrouve la section sous l'un ou
# l'autre
INTERTITRES_ANCIENS = {"Offre face aux indicateurs de santé mentale": ("Offre face aux indicateurs de besoin",)}

# Questions préparées entre départements (config.CROISEMENTS), par thème, en trois groupes : santé mentale et santé (les
# parties « croisements » des deux rapports) et addictologie (partie « Addictologie » du rapport de santé mentale). Les
# rapports, Explorer et Croiser lisent leur titre ici ; un thème absent du tableau gardait un titre vide sous Croiser
# (les trois lignes de l'addictologie, audit du 27 novembre 2026).
PREPAREES = {
    "sm": {"hopital_liberal": "L'offre hospitalière est-elle plus forte là où les psychiatres libéraux sont moins nombreux ?",
           "secteur2_revenu": "Dans les territoires aisés, l'offre de psychiatres est-elle plus chère ?",
           "enfance": "L'offre en psychiatrie de l'enfant suit-elle la protection de l'enfance ?",
           "trajet_suicide": "Les départements éloignés d'un psychiatre libéral ont-ils plus de suicides, au-delà de la "
                             "ruralité ?",
           "lieux_psy": "Les CMP, CATTP et hôpitaux de jour sont-ils plus nombreux là où les psychiatres manquent ?",
           "lieux_enfants": "Les structures de soins pour enfants suivent-elles l'offre de psychiatres pour l'enfant ?",
           "lieux_social": "Les habitants des départements modestes sont-ils plus loin des CMP et des CSAPA ?"},
    "sante": {"reeducation": "L'offre libérale de rééducation suit-elle l'offre médico-sociale pour les enfants ?",
              "medecin_traitant": "Les patients sans médecin traitant sont-ils plus nombreux là où les généralistes "
                                  "libéraux manquent, ou là où la population est âgée ?",
              "lieux_urgences": "Les départements éloignés des urgences comptent-ils plus ou moins de passages pour "
                                "geste auto-infligé ?",
              "lieux_maternite": "Les départements où les maternités sont loin ont-ils moins d'enfants ?",
              "charge_liberaux": "Là où les libéraux sont moins nombreux, chacun voit-il plus de patients ?"},
    "addicto": {"lieux_addicto": "Les structures d'addictologie sont-elles plus nombreuses là où plus de personnes "
                                 "sont prises en charge pour une addiction ?"},
}


def titre_preparee(theme: str | None, defaut: str = "") -> str:
    """Titre d'une question préparée par son thème (PREPAREES), ou le titre donné à défaut (questions de la voie
    légère, décrites avec leur base)."""
    for groupe in PREPAREES.values():
        if theme in groupe:
            return groupe[theme]
    return defaut or ""


def titrer_preparees(lignes) -> list:
    """Lignes des questions préparées (site_data.json, croisements_bases), chacune avec le titre de la table unique."""
    return [dict(r, question=titre_preparee(r.get("theme"), r.get("question", ""))) for r in (lignes or [])]


def sans_coupure(titre: str) -> str:
    """Pronom inversé jamais séparé de son verbe en fin de ligne (« trouve-t-on », « exercent-ils »), par un gluon
    invisible après chaque trait d'union (contre-audit du 6 novembre 2026)."""
    return re.sub(r"-(?!⁠)(?=(?:t-)?(?:ils?|elles?|on)\b|t-)", "-⁠", titre)


def reglage(q: dict, fam: str | None = None) -> tuple[str, str] | None:
    """Adresse (depuis la racine du site) et nom de l'outil où se règle une question de famille, ou None."""
    r = q.get("reglage")
    if not r:
        return None
    outil, qid, fen = r
    if outil == "croiser":
        return "croiser.html", "Croiser"
    ancre = fen or qid
    return f"explorer.html#{ancre}" + (f"?fam={fam}" if fam and fen else ""), "Explorer"


def renvois_explorer() -> dict[str, list[tuple[str, int, str]]]:
    """Pour chaque question d'Explorer, les questions de famille qui y renvoient pour leurs réglages, dans l'ordre :
    [(famille, numéro de la question, adresse de sa section depuis la racine)]. Explorer en tire « Résultat publié et
    méthode »."""
    out: dict[str, list] = {}
    for fam, L in FAMILLES.items():
        for k, q in enumerate(L, 1):
            r = q.get("reglage")
            if r and r[0] == "explorer":
                out.setdefault(r[1], []).append((fam, k, f"domaine/{PAGES[fam][0]}.html#q{k}"))
    # la question du profil des habitants se règle dans Croiser, mais Explorer la nomme encore et y renvoie
    for fam, L in FAMILLES.items():
        for k, q in enumerate(L, 1):
            if q["titre"] == PROFIL:
                out.setdefault("qCroisements", []).append((fam, k, f"domaine/{PAGES[fam][0]}.html#q{k}"))
    return out


def section(fam: str, titre: str) -> str | None:
    """Adresse, depuis la racine, de la section d'une famille qui porte ce titre (premier égal)."""
    for k, q in enumerate(FAMILLES[fam], 1):
        if q["titre"] == titre:
            return f"domaine/{PAGES[fam][0]}.html#q{k}"
    return None
