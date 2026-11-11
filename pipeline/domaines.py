"""Modèle des domaines de la présentation (partie 6 du second audit externe, 30 octobre 2026).

L'offre de soins est au centre, sept domaines l'entourent, chacun avec une phrase qui dit ce qu'il éclaire de l'accès
aux soins. La santé mentale n'est pas un domaine de plus : c'est l'entrée du site, qui traverse l'offre, le recours aux
soins et les distances, d'où le drapeau « santé mentale » porté par chaque indicateur (famille de la profession ou
groupe du catalogue). Source unique pour l'accueil, la fiche d'un territoire, l'atelier, la recherche et la page du
modèle ; le site en tire domaines.json. Renommer un domaine se fait ici, une seule fois.

Le rangement des indicateurs suit leur identifiant et leur groupe dans le catalogue (site_data["contexte"]). Quand le
catalogue portera lui-même le domaine et le sous-thème, ce module lira ces champs à la place des règles ci-dessous.
"""

DOMAINES = [
    {"id": "offre", "nom": "Offre de soins", "court": "Offre de soins", "centre": True,
     "pourquoi": "Qui exerce, où, dans quelles structures, à quelles conditions de tarif, et comment "
                 "cette offre a changé depuis 2016.",
     "sous": ["Professionnels", "Structures de soins", "Psychiatrie à l'hôpital", "Âge et évolution des professionnels",
              "Accès financier"]},
    {"id": "recours", "nom": "État de santé et recours aux soins", "court": "Santé et recours",
     "pourquoi": "L'état de santé des habitants et les soins qu'ils reçoivent, approchés par les affections de longue "
                 "durée, les gestes suicidaires, les consommations et les traitements. Un recours dépend aussi de l'offre "
                 "disponible, il ne mesure pas à lui seul un besoin de soins.",
     "sous": ["Santé mentale", "Addictions", "Maladies chroniques", "Médecin traitant"],
     "phares": ["ald_8", "ald_30", "ald_5", "ald_1", "ald_sans_medecin_traitant"],
     "croiser": ["Les diabétiques et les médecins généralistes", "x=ald_8&y=prof:medecin_generaliste:all&lv=dep"]},
    {"id": "population", "nom": "Population et logement", "court": "Population et logement",
     "pourquoi": "L'âge, la composition des ménages et le logement décrivent qui vit sur le territoire, et donc quelle "
                 "offre y est attendue.",
     "sous": ["Âges", "Ménages", "Logement", "Densité"],
     "phares": ["densite_pop", "part_0_14", "part_80p", "part_80p_seuls", "part_logements_suroccupes"],
     "croiser": ["Les généralistes là où vivent les plus âgés", "x=part_80p&y=prof:medecin_generaliste:all&lv=epci"]},
    {"id": "revenus", "nom": "Revenus, emploi et pauvreté", "court": "Revenus et pauvreté",
     "pourquoi": "Le revenu pèse sur le reste à charge. Pour plusieurs professions, les libéraux sont plus nombreux "
                 "dans les territoires aisés, ce qui ne dit pas pourquoi.",
     "sous": ["Revenus et pauvreté", "Emploi", "Prestations sociales"],
     "phares": ["revenu_median", "taux_pauvrete", "taux_chomage", "caf_rsa", "part_emplois_precaires"],
     "croiser": ["Les psychologues selon le niveau de vie", "x=revenu_median&y=prof:psychologue:all&lv=epci"]},
    {"id": "enfance", "nom": "Enfance, éducation et familles", "court": "Enfance et familles",
     "pourquoi": "Les familles, la protection de l'enfance et le handicap de l'enfant éclairent l'offre pour l'enfant, "
                 "CMP pour enfants, CMPP, CAMSP et psychiatres qualifiés pour l'enfant.",
     "sous": ["Familles", "Protection de l'enfance", "Handicap de l'enfant", "Formation"],
     "phares": ["part_monoparentales", "ase_mesures", "handicap_places_enfants", "eleves_handicap", "caf_aeeh"],
     "croiser": ["Familles monoparentales et distance au CMP pour enfants",
                 "x=part_monoparentales&y=dist_lieu_cmp_enfants&lv=epci"]},
    {"id": "mobilite", "nom": "Distances et mobilité", "court": "Distances et mobilité",
     "pourquoi": "Une structure n'est accessible que si l'on peut s'y rendre. Distances depuis le lieu de vie, puis "
                 "temps de route et transports en commun.",
     "sous": ["Distance aux structures", "Temps de trajet et transports"],
     "phares": ["dist_lieu_maternite", "dist_lieu_ehpad", "dist_lieu_centre_sante", "dist_lieu_ime", "dist_lieu_sessad"],
     "croiser": ["Les 80 ans et plus et la distance à l'EHPAD", "x=part_80p&y=dist_lieu_ehpad&lv=epci"]},
    {"id": "violences", "nom": "Violences et victimes", "court": "Violences et victimes",
     "pourquoi": "Les violences subies, intrafamiliales et sexuelles d'abord, et l'aide aux victimes, à mettre en "
                 "regard de l'offre de soins psychiques.",
     "sous": ["Violences enregistrées", "Aide aux victimes"]},
    {"id": "environnement", "nom": "Environnement et cadre de vie", "court": "Environnement",
     "pourquoi": "Chaleur, espaces verts, urbanisation et sécurité routière décrivent le cadre dans lequel vivent les "
                 "habitants.",
     "sous": ["Occupation du sol", "Chaleur et espaces verts", "Sécurité routière"]},
]
PAR_ID = {d["id"]: d for d in DOMAINES}

_POP = {"densite_pop": "Densité", "part_0_14": "Âges", "part_15_24": "Âges", "part_65_79": "Âges", "part_80p": "Âges",
        "part_seuls": "Ménages", "part_80p_seuls": "Ménages", "part_logements_suroccupes": "Logement",
        "part_logement_social": "Logement"}
_REV = {"revenu_median": "Revenus et pauvreté", "taux_pauvrete": "Revenus et pauvreté",
        "salaire_moyen": "Revenus et pauvreté", "part_minima_sociaux": "Prestations sociales",
        "caf_rsa": "Prestations sociales", "caf_aah": "Prestations sociales", "handicap_compensation": "Prestations sociales",
        "taux_chomage": "Emploi", "taux_emploi": "Emploi", "part_cadres": "Emploi", "part_ouvriers": "Emploi",
        "part_emplois_precaires": "Emploi"}
_ENF = {"part_monoparentales": "Familles", "ase_mesures": "Protection de l'enfance",
        "ase_placements": "Protection de l'enfance", "handicap_places_enfants": "Handicap de l'enfant",
        "handicap_places_sessad": "Handicap de l'enfant", "eleves_handicap": "Handicap de l'enfant",
        "caf_aeeh": "Handicap de l'enfant", "part_sans_diplome": "Formation"}
GROUPES_SANTE_MENTALE = ("Santé mentale", "Psychiatrie", "Addictions")
TYPES_SANTE_MENTALE = ("cmp", "cattp", "hdj_psy", "hc_psy", "cmpp", "camsp", "csapa", "caarud", "addicto")


def classer(ind: dict) -> tuple[str, str]:
    """Domaine et sous-thème d'un indicateur du catalogue (contexte de site_data, ou profession préfixée prof:)."""
    i, g = ind["id"], ind.get("groupe", "")
    if i.startswith("prof:"):
        return "offre", "Professionnels"
    if i.startswith(("evol:", "age60_")):
        return "offre", "Âge et évolution des professionnels"
    if i.startswith("lieux_"):
        return "offre", "Structures de soins"
    if i.startswith(("dist_", "distp_")):
        return "mobilite", "Distance aux structures"
    if i.startswith(("route_", "temps_")) or g.startswith("Temps de trajet"):
        return "mobilite", "Temps de trajet et transports"
    if i == "sae_file_active":
        return "recours", "Santé mentale"
    if i.startswith("sae_"):
        return "offre", "Psychiatrie à l'hôpital"
    if i.startswith(("depassements_", "taux_depassement_")):
        return "offre", "Accès financier"
    if i.startswith(("file_active_", "patients_mt_")):
        return "offre", "Activité des libéraux"
    if i == "ald_sans_medecin_traitant":
        return "recours", "Médecin traitant"
    if i in _REV:
        return "revenus", _REV[i]
    if i.startswith("ald_"):
        return "recours", "Santé mentale" if sante_mentale(ind) else "Maladies chroniques"
    if g.startswith("Addictions"):
        return "recours", "Addictions"
    if g.startswith("Santé mentale"):
        return "recours", "Santé mentale"
    if i in _POP:
        return "population", _POP[i]
    if i in _ENF:
        return "enfance", _ENF[i]
    return "population", "Ménages"


def sante_mentale(ind: dict) -> bool:
    """Drapeau « santé mentale » d'un indicateur : famille de la profession, groupe du catalogue ou type de structure."""
    i, g = ind["id"], ind.get("groupe", "")
    if ind.get("famille") == "Santé mentale":
        return True
    if i.startswith(("lieux_lieu_", "dist_lieu_", "distp_lieu_")):
        return any(t in i for t in TYPES_SANTE_MENTALE)
    if i in ("ald_23", "ald_15"):
        return True
    return g.startswith(GROUPES_SANTE_MENTALE) or i.startswith("sae_")


# Domaine de chaque base du registre de la veille (docs/veille/registre_bases.csv), choisi base par base. Les bases
# de la géographie politique (chantier 11) restent hors du modèle. Seules les bases « à intégrer » sont annoncées sur le
# site, et jamais une source que les règles du projet rangent parmi les sources écartées.
REGISTRE_DOMAINE = {
    "offre": ["zonages_ps", "ameli_file_active", "ameli_patientele_mt", "ameli_installations", "ameli_assistants_medicaux",
              "ameli_sas", "ameli_patientele", "ameli_ages", "ameli_exercice", "drees_psychiatrie_2008_2019", "drees_ares",
              "drees_sae_administratives", "drees_maternites", "sante_psy_etudiant", "lits_soins_critiques",
              "enquete_urgences", "mon_soutien_psy_departement", "sectorisation_autres_regions", "f2rsm_cmp",
              "besoins_main_oeuvre", "projections_medecins", "projections_infirmieres", "revenus_liberaux",
              "drees_514_la_demographie_des_professionnels_de", "datagouv_6490ec5bd5cd90c7b343d766"],
    "recours": ["odisse_ptsm", "odisse_gestes_sejours", "odisse_urgences_region", "drees_gestes_depuis_2012",
                "odisse_pensees_suicidaires_series", "epds", "odisse_post_partum", "odisse_preconception", "enabee",
                "barometre_2024_depression", "barometre_2024_anxiete", "mois_sans_tabac", "atlas_sante_mentale",
                "morbidite_hospitaliere", "snds", "ma_region_sante_mentale", "epicov", "drees_elsa_suicides_idf",
                "maladies_pro_psychiques", "datagouv_55ed58b488ee385430a46ec1", "datagouv_53d3862ca3a72904270136a0",
                "ameli_depenses", "series_urgences", "open_damir_psychologues"],
    "population": ["projections_population", "typologies_insee", "rpls", "sitadel", "projections_epp4"],
    "revenus": ["filosofi_2023", "qpv", "caf_communes_qpv", "aide_sociale_departementale"],
    "enfance": ["ips_colleges"],
    "mobilite": ["apl_structures_personnes_agees", "diagnostic_soins_urgents", "insee_bpe", "gtfs"],
    "violences": ["ssmsi_delinquance", "ssmsi_series", "ssmsi_cvs", "ssmsi_victimes_mis_en_cause", "aide_victimes_dila",
                  "aide_victimes_completes"],
    "environnement": ["ocs_ge", "corine_land_cover", "bd_topo", "ilots_chaleur", "espaces_verts", "accidents_circulation"],
}
REGISTRE_HORS_MODELE = {"resultats_electoraux"}
REGISTRE_ECARTEES: set[str] = set()
# Formulation propre à une base dont la donnée n'est pas acquise, pour ne rien promettre (séance principale, 30 octobre
# 2026) : la demande de documents à la Cnam est partie le 26 octobre 2026, sans réponse à ce jour. Jamais l'annuaire.
REGISTRE_LIBELLE = {"mon_soutien_psy_departement": "Mon soutien psy par département, données demandées à l'Assurance "
                                                   "Maladie le 26 octobre 2026, en attente de réponse"}
_REG_PAR_ID = {i: d for d, ids in REGISTRE_DOMAINE.items() for i in ids}


def bases_a_venir(registre) -> dict[str, list[str]]:
    """Noms courts des bases « à intégrer » du registre, par domaine du modèle. Fichier absent, dictionnaire vide."""
    import csv
    from pathlib import Path
    sortie: dict[str, list[str]] = {}
    f = Path(registre)
    if not f.exists():
        return sortie
    with f.open(encoding="utf-8") as fh:
        for l in csv.DictReader(fh, delimiter=";"):
            d = _REG_PAR_ID.get(l["id"])
            if l.get("statut") != "à intégrer" or not d or l["id"] in REGISTRE_HORS_MODELE | REGISTRE_ECARTEES:
                continue
            sortie.setdefault(d, []).append(REGISTRE_LIBELLE.get(l["id"]) or l["nom"].split(" (")[0])
    return sortie
