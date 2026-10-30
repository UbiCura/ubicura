"""Registre des licences des sources (demande de Lucas du 28 octobre 2026, « être précis pour les licences spécifiques,
je veux me protéger juridiquement »).

Une entrée par licence, avec chaque fait lu sur sa page officielle et daté. Ce qui n'a pas été lu reste « à confirmer ».
Le catalogue (pipeline/indicateurs.py) relie chaque indicateur à l'identifiant de sa licence. Le libellé affiché sur le
site vient d'ici, pour qu'il ne change pas de texte sans raison. L'offre payante n'admet que les licences dont l'usage
commercial est établi (offre_payante), un test le vérifie sur les vraies données.

Faits relevés le 28 octobre 2026, détail et citations dans docs/note_offre_professionnelle_2026-10-28.md, partie 1.
"""
from __future__ import annotations

import re

OUI, NON, A_CONFIRMER = "oui", "non", "à confirmer"

LICENCES = {
    "lo-2.0": {
        "nom": "Licence Ouverte 2.0 (Etalab)",
        "affiche": "Licence Ouverte 2.0",
        "page": "https://www.data.gouv.fr/pages/legal/licences/etalab-2.0/",
        "lue_le": "2026-10-28",
        "usage_commercial": OUI,             # « à des fins commerciales ou non »
        "partage_identique": NON,
        "mention": "Le nom du producteur et la date de dernière mise à jour des données.",
        "obligations": ("Ne pas laisser croire à une caution officielle. Respecter le droit des données personnelles quand "
                        "l'information en contient. Sans altération ni dénaturation (CRPA, L322-1). Aucune garantie du "
                        "producteur."),
        "statut": "vérifié",
    },
    "lo-1.0": {
        "nom": "Licence Ouverte 1.0 (Etalab, octobre 2011)",
        "affiche": "Licence Ouverte 1.0",
        # PDF d'Etalab, qui renvoie vers une ressource de data.gouv (static.data.gouv.fr, jeu licence-ouverte-2-0), texte
        # « Licence Ouverte, octobre 2011 », « Cette licence est une version 1.0 de la Licence Ouverte »
        "page": "https://www.etalab.gouv.fr/wp-content/uploads/2014/05/Licence_Ouverte.pdf",
        "lue_le": "2026-10-28",
        "usage_commercial": OUI,             # « Exploiter l'Information à titre commercial »
        "partage_identique": NON,
        "mention": "La source (a minima le nom du producteur) et la date de dernière mise à jour de l'information.",
        "obligations": ("Données personnelles soumises à la loi du 6 janvier 1978. Droit français. Compatible avec la "
                        "version 2.0, qui la remplace pour les nouvelles publications."),
        "statut": "vérifié",
    },
    "odbl-1.0": {
        "nom": "Open Database License 1.0 (ODbL)",
        "affiche": "ODbL 1.0 (partage à l'identique)",
        "page": "https://opendatacommons.org/licenses/odbl/1-0/",
        "lue_le": "2026-10-28",
        "usage_commercial": OUI,             # article 3.1, « explicitly include commercial use »
        "partage_identique": OUI,            # article 4.4
        "mention": ("Contient des informations issues de la base [nom], diffusée sous licence Open Database License "
                    "(ODbL) (article 4.3)."),
        "obligations": ("Une base dérivée utilisée publiquement reste sous ODbL (4.4). Une copie lisible par machine de la "
                        "base dérivée est offerte gratuitement à qui la reçoit (4.6). Conditions de la Cnam, "
                        "https://data.ameli.fr/terms/terms-and-conditions/ (lues le 28 octobre 2026)."),
        "statut": "vérifié",
    },
    "ign-lo-2.0": {
        # réponse écrite de l'IGN à la question du 28 octobre 2026 (Relation utilisateurs de cartes.gouv.fr, 29 octobre
        # 2026, dossier DRG CRM:0072209), « tous usages, pour tous acteurs, sont autorisés gratuitement même pour des
        # prestations payantes », sauf SCAN 25, SCAN 100 et SCAN OACI ; page de l'IGN lue le 29 octobre 2026
        "nom": "Licence Ouverte 2.0 (Etalab), produits de l'IGN dont le Plan IGN",
        "affiche": "Licence Ouverte 2.0 (IGN)",
        "page": "https://www.ign.fr/institut/espace-presse/ign-operateur-data-et-cartographe-au-service-de-la-transition-ecologique",
        "lue_le": "2026-10-29",
        "usage_commercial": OUI,             # « même pour des prestations payantes » (réponse de l'IGN)
        "partage_identique": NON,
        "mention": "© IGN – nom du produit, par exemple « © IGN – Plan IGN » (forme demandée par l'IGN).",
        "obligations": ("Celles de la Licence Ouverte 2.0. Hors de ce champ, SCAN 25, SCAN 100 et SCAN OACI, payants pour le "
                        "grand public au-delà de forfaits."),
        "statut": "vérifié",
    },
    "cgu-geoplateforme": {
        "nom": "Conditions générales d'utilisation de la Géoplateforme (IGN)",
        "affiche": "Conditions de la Géoplateforme (IGN)",
        "page": "https://cartes.gouv.fr/cgu",
        "lue_le": "2026-10-28",              # version du 15 octobre 2024
        "usage_commercial": A_CONFIRMER,      # données de l'IGN sous Licence Ouverte (voir ign-lo-2.0), résultats des calculs non dits
        "partage_identique": NON,
        "mention": "© IGN – nom du produit, pour les données de l'IGN (réponse de l'IGN du 29 octobre 2026).",
        "obligations": ("Itinéraire 10 requêtes par seconde, isochrone 5, WMTS sans limite d'usage. La réponse de l'IGN du "
                        "29 octobre 2026 (dossier DRG CRM:0072209) ne dit pas explicitement si les résultats des calculs "
                        "d'itinéraire et d'isochrone peuvent être conservés et republiés dans un service payant, question "
                        "précisée dans un second courriel."),
        "statut": "à confirmer",
    },
    "crpa-document-communique": {
        # documents administratifs communiqués sur demande (arrêtés de sectorisation psychiatrique des ARS, demande du 28
        # octobre 2026). Articles L321-1 et L322-1 du code des relations entre le public et l'administration, Légifrance,
        # version en vigueur depuis le 19 mars 2016, lus le 29 octobre 2026
        "nom": "Informations publiques d'un document administratif communiqué (CRPA, articles L321-1 et L322-1)",
        "affiche": "Document administratif communiqué (CRPA)",
        "page": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000032255220",
        "lue_le": "2026-10-29",
        "usage_commercial": A_CONFIRMER,      # L321-1, réutilisation « à d'autres fins que celles de la mission de service
                                              # public », redevance possible (L324-1), à confirmer par le juriste
        "partage_identique": NON,
        "mention": "La source (l'administration émettrice et le document) et la date de sa dernière mise à jour (L322-1).",
        "obligations": ("Sans altération ni dénaturation du sens (L322-1). Aucune donnée personnelle reprise (L322-2), les "
                        "noms des agents qui ont transmis le document restent dans la messagerie, jamais publiés."),
        "statut": "à confirmer",
    },
}

# Libellés libres trouvés aujourd'hui dans config.SOURCES_INFO, le catalogue et les portails, vers leur identifiant
MOTIFS = [
    (r"odbl|open database", "odbl-1.0"),
    (r"licence ouverte (?:v ?)?1(?:\.0)?\b|fr-lo", "lo-1.0"),
    (r"licence ouverte|etalab|lov2", "lo-2.0"),
    (r"plan ign", "ign-lo-2.0"),
    (r"g[ée]oplateforme", "cgu-geoplateforme"),
    (r"document administratif communiqu", "crpa-document-communique"),
]

# Sources dont la licence relevée sur data.gouv diffère du libellé de config.SOURCES_INFO (API data.gouv, champ license,
# lue le 28 octobre 2026). Motif sur le nom de la source, comme dans config.SOURCES_INFO.
SOURCES_PARTICULIERES = [
    (r"^FINESS(?! \(Finess\+\))", "lo-1.0", "jeu finess-extraction-du-fichier-des-etablissements, license fr-lo"),
    (r"^Assurance Maladie, affections de longue durée", "lo-1.0", "jeu 55095017c751df68c9882844, license fr-lo"),
]

# Mentions à ajouter pour une source, en plus de celle de sa licence
ATTRIBUTIONS = [
    (r"^INSEE, temps", "Distancier fondé sur OpenStreetMap, © les contributeurs d'OpenStreetMap et du projet OSRM."),
]


def identifiant(libelle: str | None, source: str | None = None) -> str | None:
    """Identifiant de licence d'un libellé libre, ou de la source quand elle est particulière. None si inconnu, un test
    l'empêche."""
    for motif, ident, _ in SOURCES_PARTICULIERES:
        if source and re.search(motif, source):
            return ident
    t = (libelle or "").lower()
    return next((ident for motif, ident in MOTIFS if re.search(motif, t)), None)


def affiche(ident: str | None) -> str:
    return LICENCES[ident]["affiche"] if ident in LICENCES else ""


def offre_payante(ident: str | None) -> bool:
    """Seules les licences dont l'usage commercial est établi sur leur texte entrent dans l'offre payante."""
    return ident in LICENCES and LICENCES[ident]["usage_commercial"] == OUI


def attribution(source: str) -> str:
    return " ".join(texte for motif, texte in ATTRIBUTIONS if re.search(motif, source or ""))
