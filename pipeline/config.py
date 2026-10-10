"""Configuration centrale. Tout ce qui peut changer côté producteurs de données est ici."""
import os
from pathlib import Path

# OFFRE_SOINS_RACINE permet de travailler dans un autre dossier (tests, plusieurs jeux de données)
RACINE = Path(os.environ.get("OFFRE_SOINS_RACINE") or Path(__file__).resolve().parent.parent)
DONNEES = RACINE / "donnees"
BRUT = DONNEES / "brut"            # fichiers téléchargés, tels quels
INTER = DONNEES / "intermediaire"  # tables nettoyées (parquet)
RESULTATS = RACINE / "resultats"   # sorties datées + historique

USER_AGENT = "offre-soins-pipeline/1.0 (recherche, contact via data.gouv)"
DATAGOUV_API = "https://www.data.gouv.fr/api/1/datasets/{}/"

# Durée pendant laquelle un fichier téléchargé est réutilisé sans être retéléchargé (jours)
CACHE_JOURS = {"rpps": 7, "finess": 30, "insee": 90, "ref": 90, "contours": 365, "complements": 30, "ameli": 30, "odisse": 30,
               "acces_route": 90, "apl": 90, "drees_isd": 30, "sae": 30,
               "drees_demographie": 30, "ald": 30, "caf": 30, "insee_estimations": 90}

# familles d'offre (voir la section Professions plus bas)
SANTE_MENTALE, SANTE = "Santé mentale", "Santé"

# ---------------------------------------------------------------- RPPS
RPPS_DATASET = ("annuaire-sante-extractions-des-donnees-en-libre-acces-des-"
                "professionnels-intervenant-dans-le-systeme-de-sante-rpps")
# Motifs recherchés dans le titre, l'URL ou le nom de fichier de chaque ressource.
# Si aucun ne correspond, repli sur l'ordre de taille (activité > diplômes > savoir-faire).
RPPS_RESSOURCES = {
    "activite": r"personne.?activit",
    "diplomes": r"dipl",
    "savoirfaire": r"savoir.?faire",
}

# ---------------------------------------------------------------- FINESS
# Le flux historique est gelé depuis mai 2026, Finess+ le remplace.
FINESS_NOUVEAU = "finess-structures-1"
FINESS_HISTORIQUE = "53699569a3a729239d2046eb"
# Colonnes du flux historique (fichier sans en-tête, section "structureet")
FINESS_COLONNES_HISTO = [
    "section", "nofinesset", "nofinessej", "rs", "rslongue", "complrs", "compldistrib",
    "numvoie", "typvoie", "voie", "compvoie", "lieuditbp", "commune", "departement",
    "libdepartement", "ligneacheminement", "telephone", "telecopie", "categetab",
    "libcategetab", "categagretab", "libcategagretab", "siret", "codeape", "codemft",
    "libmft", "codesph", "libsph", "dateouv", "dateautor", "maj", "numuai",
]

# ---------------------------------------------------------------- Référentiel géographique
# Version publiée du paquet, résolue par le registre npm (dernière version et date de publication), puis figée
# dans l'adresse des fichiers pour que la version lue soit toujours consignée (vérifié le 5 octobre 2026,
# version 6.0.0 du 9 mars 2026, populations municipales 2023).
REF_REGISTRE = "https://registry.npmjs.org/@etalab%2fdecoupage-administratif"
REF_BASE = "https://cdn.jsdelivr.net/npm/@etalab/decoupage-administratif@{version}/data/{nom}.json"
REF_FICHIERS = ["communes", "epci", "departements", "regions"]
DEPS_DROM = {"971", "972", "973", "974", "976"}

# ---------------------------------------------------------------- INSEE
INSEE_PAGE_DOSSIER = "https://www.insee.fr/fr/statistiques/5359146"
# Depuis 2026 l'INSEE publie le dossier complet au format long (une ligne par territoire, tableau,
# mesure et année). Chaque variable est désignée par son tableau (ID_TAB) et un motif sur le code
# de mesure (TAB_MEASURE). Plusieurs mesures correspondant au motif sont additionnées. L'année la
# plus récente est retenue. Codes relevés dans le fichier du 3 octobre 2026 (recensement 2023,
# revenus 2023).
INSEE_MESURES = {
    "pop": ("POP_T1", r"^POP$"),
    "pop0014": ("POP_T1", r"^POP_AGE_Y_LT15$"),
    "pop1524": ("POP_T1", r"^POP_AGE_Y15T24$"),
    "pop6579": ("POP_T1", r"^POP_AGE_Y65T79$"),
    "pop80p": ("POP_T1", r"^POP_AGE_Y_GE80$"),
    "superf": ("POP_T2", r"^SUP$"),
    "med": ("REV_T1", r"^MED_SL$"),
    "tp60": ("REV_T1", r"^PR_MD60$"),
    "chom": ("EMP_T4", r"^POP_EMPSTA_ENQ_2_AGE_Y15T64$"),
    "act": ("EMP_T4", r"^POP_EMPSTA_ENQ_1T2_AGE_Y15T64$"),
    "pop15p": ("POP_T7", r"^POP_AGE_Y_GE15$"),
    "cs3": ("POP_T7", r"^POP_AGE_Y_GE15_PCS_3$"),
    "cs6": ("POP_T7", r"^POP_AGE_Y_GE15_PCS_6$"),
    "fam": ("FAM_T3", r"^NBFAM$"),
    "fammono": ("FAM_T3", r"^NBFAM_TFN_1$"),
    "pseul": ("FAM_G2", r"^ONEPERS_AGE_.*_NOC_P1$"),
    "popmen15p": ("FAM_G2", r"^DWELLINGS_POPSIZE_AGE_"),
}
# Vulnérabilité psychosociale (chantier 5, demande de Lucas du 4 octobre 2026). Mêmes règles de lecture,
# codes relevés le 4 octobre 2026. Ces indicateurs entrent dans les croisements mais pas dans le modèle de
# l'effectif attendu (sans accord de Lucas).
INSEE_MESURES.update({
    "pop1564": ("EMP_T1", r"^POP_AGE_Y15T64$"),
    "occupes1564": ("EMP_T1", r"^POP_EMPSTA_ENQ_1_AGE_Y15T64$"),
    "salaire": ("SAL_T1", r"^SALAIRE_NET_EQTP_MENSUEL_MOYENNE$"),
    "sans_diplome": ("FOR_T3", r"^POP_EDUC_001T100_RP$"),
    "non_scolarises": ("FOR_T3", r"^POP$"),
    "emplois_precaires": ("ACT_T2", r"^POP_SEX_[MF]_AGE_Y_GE15_EMPFORM_22T27_EMPSTA_ENQ_1$"),
    "actifs_occupes": ("ACT_T2", r"^POP_SEX_[MF]_AGE_Y_GE15_EMPSTA_ENQ_1$"),
    "suroccupes": ("LOG_T7", r"^DWELLINGS_OCC_IND_\w+_OVER_OCC$"),
    "logements_occupation": ("LOG_T7", r"^DWELLINGS_OCC_IND_"),
    "seuls80": ("FAM_G2", r"^ONEPERS_AGE_Y_GE80_NOC_P1$"),
    "menages80": ("FAM_G2", r"^DWELLINGS_POPSIZE_AGE_Y_GE80$"),
    "locataires_hlm": ("LOG_T10", r"^DWELLINGS_OCS_DW_MAIN_TSH_221$"),
    "residences_principales": ("LOG_T10", r"^DWELLINGS_OCS_DW_MAIN_TSH_(100|200|300)$"),
    "minima_sociaux": ("REV_T2", r"^S_SOC_BEN_DI_MIN_SOC$"),
})
CONTEXTE_VULNERABILITE = [
    ("taux_emploi", "Taux d'emploi des 15-64 ans", "%", "occupes1564", "pop1564"),
    ("salaire_moyen", "Salaire net mensuel moyen", "€", "salaire", None),
    ("part_sans_diplome", "Part des personnes sans diplôme", "%", "sans_diplome", "non_scolarises"),
    ("part_emplois_precaires", "Part des emplois à durée limitée", "%", "emplois_precaires", "actifs_occupes"),
    ("part_logements_suroccupes", "Part des logements suroccupés", "%", "suroccupes", "logements_occupation"),
    ("part_80p_seuls", "Part des 80 ans et plus vivant seuls", "%", "seuls80", "menages80"),
    ("part_logement_social", "Part des ménages locataires d'un logement social", "%", "locataires_hlm",
     "residences_principales"),
    ("part_minima_sociaux", "Part des minima sociaux dans le revenu disponible", "%", "minima_sociaux", None),
]
GROUPE_VULNERABILITE = "Vulnérabilité psychosociale"

# Ancien format large (archives datées de la même page), utilisé en repli. Expressions régulières
# sur les noms de colonnes, millésime le plus récent retenu.
INSEE_VARIABLES = {
    "pop": r"^P(\d\d)_POP$",
    "pop0014": r"^P(\d\d)_POP0014$",
    "pop1524": r"^P(\d\d)_POP1524$",
    "pop80p": r"^P(\d\d)_POP80P$",
    "superf": r"^SUPERF$",
    "med": r"^MED(\d\d)$",
    "tp60": r"^TP60(\d\d)$",
    "chom": r"^P(\d\d)_CHOM1564$",
    "act": r"^P(\d\d)_ACT1564$",
    "pop15p": r"^C(\d\d)_POP15P$",
    "cs3": r"^C(\d\d)_POP15P_CS3$",
    "cs6": r"^C(\d\d)_POP15P_CS6$",
    "fam": r"^C(\d\d)_FAM$",
    "fammono": r"^C(\d\d)_FAMMONO$",
    "pseul": r"^P(\d\d)_POP15P_PSEUL$",
    "popmen15p": r"^P(\d\d)_POP15P$",
}
# Indicateurs de contexte dérivés (id, libellé, unité, numérateur, dénominateur ou None si lu directement)
CONTEXTE = [
    ("densite_pop", "Densité de population", "hab./km²", "pop", "superf"),
    ("part_0_14", "Part des moins de 15 ans", "%", "pop0014", "pop"),
    ("part_15_24", "Part des 15-24 ans", "%", "pop1524", "pop"),
    ("part_65_79", "Part des 65-79 ans", "%", "pop6579", "pop"),
    ("part_80p", "Part des 80 ans et plus", "%", "pop80p", "pop"),
    ("revenu_median", "Niveau de vie médian", "€", "med", None),
    ("taux_pauvrete", "Taux de pauvreté", "%", "tp60", None),
    ("taux_chomage", "Taux de chômage des 15-64 ans", "%", "chom", "act"),
    ("part_cadres", "Part des cadres parmi les 15 ans et plus", "%", "cs3", "pop15p"),
    ("part_ouvriers", "Part des ouvriers parmi les 15 ans et plus", "%", "cs6", "pop15p"),
    ("part_monoparentales", "Part des familles monoparentales", "%", "fammono", "fam"),
    ("part_seuls", "Part des 15 ans et plus vivant seuls", "%", "pseul", "popmen15p"),
]

# ---------------------------------------------------------------- Assurance Maladie, cartographie des pathologies
# Jeu data.gouv et API data.ameli.fr vérifiés le 3 octobre 2026 (CNAM, licence ODbL, mise à jour du
# 6 juillet 2026, années 2015 à 2024, 5,8 millions de lignes). Seules les lignes utiles sont demandées
# à l'API (filtre sur le code « top »). Licence ODbL, partage à l'identique, les indicateurs qui en
# dérivent sont écrits dans des fichiers à part.
AMELI_DATAGOUV = "effectif-de-patients-par-pathologie-sexe-classe-dage-et-territoire-departement-region"
AMELI_API = "https://data.ameli.fr/api/explore/v2.1/catalog/datasets/effectifs"
AMELI_LICENCE = "ODbL"
# code top, identifiant, libellé d'affichage, explication. Libellé officiel conservé dans les fichiers.
AMELI_INDICATEURS = [
    ("PSY_CAT_CAT", "pec_troubles_psy", "Personnes prises en charge pour troubles psychiques",
     "Part des habitants pris en charge par l'Assurance Maladie pour un trouble psychique repéré (hospitalisation, "
     "affection de longue durée ou traitement caractéristique), tous troubles confondus."),
    ("PSY_PSC_IND", "pec_psychotiques", "Personnes prises en charge pour troubles psychotiques",
     "Dont troubles psychotiques (schizophrénie et troubles apparentés)."),
    ("PSY_TNH_CAT", "pec_humeur", "Personnes prises en charge pour troubles névrotiques et de l'humeur",
     "Dont troubles de l'humeur (dépression, troubles bipolaires) et troubles anxieux."),
    ("PSY_DME_IND", "pec_deficience", "Personnes prises en charge pour déficience intellectuelle",
     "Dont déficience intellectuelle."),
    ("PSY_ADD_CAT", "pec_addictions", "Personnes prises en charge pour troubles addictifs",
     "Dont troubles liés à l'alcool, au tabac, au cannabis ou à d'autres substances."),
    ("PSY_ENF_IND", "pec_enfance", "Personnes prises en charge pour troubles débutant dans l'enfance",
     "Dont troubles psychiques apparus dans l'enfance (troubles du neurodéveloppement notamment)."),
    ("PSY_AUT_IND", "pec_autres_psy", "Personnes prises en charge pour d'autres troubles psychiques",
     "Dont autres troubles psychiques repérés."),
    ("TPS_CAT_EXC", "psychotropes", "Personnes sous traitement psychotrope sans trouble psychique repéré",
     "Part des habitants qui reçoivent régulièrement des médicaments psychotropes sans qu'un trouble psychique "
     "soit repéré par ailleurs."),
    ("TPS_ADR_EXC", "antidepresseurs", "Personnes sous antidépresseurs ou thymorégulateurs, sans trouble repéré",
     "Dont antidépresseurs ou thymorégulateurs."),
    ("TPS_ANX_EXC", "anxiolytiques", "Personnes sous anxiolytiques, sans trouble repéré", "Dont anxiolytiques."),
    ("TPS_HYP_EXC", "hypnotiques", "Personnes sous hypnotiques, sans trouble repéré", "Dont hypnotiques."),
    ("TPS_NLE_EXC", "neuroleptiques", "Personnes sous neuroleptiques, sans trouble repéré", "Dont neuroleptiques."),
]
AMELI_COUVERTURE_MIN = .95   # part des patients présente dans les cases d'âge pour standardiser
AMELI_DEPARTEMENTS_EXCLUS = ["976"]   # Mayotte, régime distinct et couverture très partielle
AMELI_REGIONS_EXCLUES = ["06"]        # Mayotte comme région
# Départements écartés de tous les croisements entre départements (corrélations, loi inverse des soins, concordance
# des besoins). Mayotte, faute de recensement exhaustif la population de référence y est incertaine, et les données
# de l'Assurance Maladie et de la CAF y sont absentes ou partielles. Règle écrite dans les rapports et l'atlas.
DEPARTEMENTS_EXCLUS_CROISEMENTS = ["976"]
# Carte bivariée offre et besoin (audit 4.2), palette violet et or de Joshua Stevens, 3 tiers de l'offre (violet)
# sur 3 tiers de l'indicateur (or). Indice offre x 3 + indicateur, du plus bas au plus haut.
BIVARIEE = ["#e8e8e8", "#e4d9ac", "#c8b35a", "#cbb8d7", "#c8ada0", "#af8e53", "#9972af", "#976b82", "#804d36"]

# ---------------------------------------------------------------- Assurance Maladie, accès financier et médecin traitant
GROUPE_ACCES = "Accès financier et médecin traitant"
# Jeux data.ameli.fr vérifiés le 4 octobre 2026 (ODbL). Effectifs de libéraux par secteur conventionnel (1, 2 avec
# Optam, 2 sans Optam, non conventionnés), par spécialité, département et région, 2010 à 2024, mis à jour en février
# 2026. Part des patients en affection longue durée sans médecin traitant, par département et région, 2018 à 2025.
AMELI_SECTEURS_API = "https://data.ameli.fr/api/explore/v2.1/catalog/datasets/demographie-secteurs-conventionnels"
AMELI_ALD_API = "https://data.ameli.fr/api/explore/v2.1/catalog/datasets/patients-longueduree-annuelle"
# spécialité dans le jeu (libellé exact), identifiant, libellé d'affichage, famille
AMELI_SECTEURS_PROFESSIONS = [
    ("Psychiatres", "psychiatre", "Psychiatres", SANTE_MENTALE),
    ("Pédiatres", "pediatre", "Pédiatres", SANTE),
    ("Médecins généralistes (hors médecins à expertise particulière - MEP)", "medecin_generaliste",
     "Médecins généralistes", SANTE),
    ("Gynécologues médicaux et obstétriciens", "gynecologue", "Gynécologues", SANTE),
    ("Ophtalmologues", "ophtalmologue", "Ophtalmologues", SANTE),
]
AMELI_SECTEURS_EFFECTIF_MIN = 5   # en dessous, la part n'est pas calculée pour le département (trop instable)

# ---------------------------------------------------------------- DREES, SAE, psychiatrie hospitalière
# Bases statistiques de la SAE, jeu 708 du portail de la DREES, vérifié le 4 octobre 2026 (Licence Ouverte, une
# archive 7z par millésime, SAE 2024 publiée le 17 décembre 2025). Variables du bordereau PSY vérifiées dans le
# dictionnaire officiel (SAE2024_Dictionnaire des variables par bordereaux.xlsx). La discipline TOT est la somme de
# GEN, INF et PEN, on n'utilise que TOT pour les totaux.
SAE_API = "https://data.drees.solidarites-sante.gouv.fr/api/explore/v2.1/catalog/datasets/708_bases-statistiques-sae"
SAE_MOTIF = r"sae_(\d{4})_bases_statistiques_formats_sas_csv_7z$"
GROUPE_HOPITAL_PSY = "Psychiatrie à l'hôpital (SAE)"
SAE_DEPARTEMENTS_OUTRE_MER = {"9A": "971", "9B": "972", "9C": "973", "9D": "974", "9F": "976"}
# identifiant, discipline, variables additionnées, libellé, unité, dénominateur (tous ou moins15), explication
SAE_INDICATEURS = [
    ("sae_lits_psy", "TOT", ["CAP_HTP"], "Lits d'hospitalisation à temps plein en psychiatrie", "pour 100 000 habitants",
     "tous", "Lits installés au 31 décembre dans les établissements autorisés en psychiatrie, adultes et enfants."),
    ("sae_places_jour_psy", "TOT", ["CAP_HDJ", "CAP_HDN"], "Places d'hospitalisation de jour ou de nuit en psychiatrie",
     "pour 100 000 habitants", "tous", "Places installées au 31 décembre en hôpital de jour ou de nuit."),
    ("sae_cmp", "TOT", ["NB_CMP_SEUL"], "Centres médico-psychologiques (CMP)", "pour 100 000 habitants", "tous",
     "Nombre de CMP déclarés par les établissements, adultes et enfants."),
    ("sae_etp_psychiatres", "TOT", ["ETPSAL_PKT"], "Psychiatres salariés en psychiatrie hospitalière, en temps plein",
     "ETP pour 100 000 habitants", "tous", "Équivalents temps plein annuels moyens des psychiatres salariés (hors "
     "internes) qui concourent à l'activité de psychiatrie de l'établissement."),
    ("sae_etp_psychologues", "TOT", ["ETP_PSY"], "Psychologues en psychiatrie hospitalière, en temps plein",
     "ETP pour 100 000 habitants", "tous", "Équivalents temps plein annuels moyens des psychologues qui concourent "
     "à l'activité de psychiatrie de l'établissement."),
    ("sae_file_active", "TOT", ["FIL_TOT"], "Patients suivis en psychiatrie hospitalière (file active)",
     "pour 1 000 habitants", "tous", "Patients vus au moins une fois dans l'année par les services de psychiatrie, "
     "comptés une fois par établissement. Un patient suivi par deux établissements compte deux fois."),
    ("sae_infanto", "INF", ["CAP_HTP", "CAP_HDJ", "CAP_HDN"], "Lits et places en psychiatrie de l'enfant et de l'adolescent",
     "pour 100 000 moins de 15 ans", "moins15", "Lits et places installés en psychiatrie infanto-juvénile, rapportés aux "
     "moins de 15 ans (le recensement ne publie pas les moins de 18 ans)."),
]

# ---------------------------------------------------------------- DREES, indicateurs sociaux départementaux (ISD)
# Jeux du portail de la DREES vérifiés le 4 octobre 2026 (Licence Ouverte, mis à jour le 3 septembre 2026), format
# long (année, département, indicateur, valeur). Les totaux régionaux portent le code département « 1000 ».
DREES_API = "https://data.drees.solidarites-sante.gouv.fr/api/explore/v2.1/catalog/datasets/"
GROUPE_ENFANCE_HANDICAP = "Protection de l'enfance et handicap"
# jeu, identifiant DREES, identifiant ici, libellé, unité, facteur (proportion en %), famille, explication
DREES_ISD = [
    ("596_enfance-et-jeunesse-en-danger", "ase_tx_mesures_0_20", "ase_mesures", "Mesures d'aide sociale à l'enfance",
     "% des 0-20 ans", 100, SANTE_MENTALE,
     "Enfants et jeunes de 0 à 20 ans qui font l'objet d'une mesure de l'aide sociale à l'enfance (placement ou "
     "action éducative). Repère de situations de vulnérabilité, à rapprocher de l'offre en psychiatrie de l'enfant."),
    ("596_enfance-et-jeunesse-en-danger", "ase_tx_mesures_placement_0_20", "ase_placements",
     "Enfants accueillis à l'aide sociale à l'enfance", "% des 0-20 ans", 100, SANTE_MENTALE,
     "Enfants et jeunes de 0 à 20 ans confiés à l'aide sociale à l'enfance et accueillis hors de leur famille."),
    ("627_personnes-en-situation-de-handicap", "ph_tx_benef_pch_actp_1000hab_m60", "handicap_compensation",
     "Bénéficiaires d'une prestation de compensation du handicap, moins de 60 ans", "pour 1 000 habitants", 1, SANTE,
     "Personnes de moins de 60 ans qui reçoivent la prestation de compensation du handicap ou l'allocation "
     "compensatrice pour tierce personne."),
    ("627_personnes-en-situation-de-handicap", "ph_enfants_tx_equip_etab_1000_m20", "handicap_places_enfants",
     "Places en établissement pour enfants en situation de handicap", "pour 1 000 moins de 20 ans", 1, SANTE,
     "Places en établissement médico-social pour enfants et adolescents en situation de handicap (IME, ITEP...)."),
    ("627_personnes-en-situation-de-handicap", "ph_enfants_tx_equip_sessad_1000_m20", "handicap_places_sessad",
     "Places en SESSAD", "pour 1 000 moins de 20 ans", 1, SANTE,
     "Places en service d'éducation spéciale et de soins à domicile (SESSAD), qui accompagne l'enfant dans son "
     "milieu de vie."),
    ("627_personnes-en-situation-de-handicap", "ph_enfants_part_eleves_handicap_1_2_deg_1000", "eleves_handicap",
     "Élèves en situation de handicap", "pour 1 000 élèves", 1, SANTE,
     "Élèves en situation de handicap scolarisés en milieu ordinaire ou en établissement, pour 1 000 élèves."),
]

# ---------------------------------------------------------------- Santé publique France, portail Odissé
# Portail Opendatasoft de Santé publique France, Licence Ouverte 2.0. Jeux vérifiés le 3 octobre 2026
# (champs, années, niveaux géographiques). Pour chaque indicateur, l'année la plus récente disponible est
# retenue. Un indicateur régional n'est jamais attribué aux départements.
ODISSE_API = "https://odisse.santepubliquefrance.fr/api/explore/v2.1/catalog/datasets/"
ODISSE_SOURCE = "Santé publique France, portail Odissé"
ODISSE = [
    {"dataset": "suicides-deces-departement", "niveau": "dep", "code": "num_departement",
     "where": 'classe_d_age="Tous" and sexe="Hommes et Femmes"', "valeur": "taux_standardise",
     "id": "suicides", "libelle": "Décès par suicide", "unite": "pour 100 000 hab., standardisé sur l'âge",
     "source": ODISSE_SOURCE + ", d'après le CépiDc (Inserm)",
     "explication": "Nombre de décès par suicide rapporté à la population, à structure d'âge égale. Les décès "
                    "d'intention indéterminée ne sont pas comptés, le chiffre est donc probablement sous-estimé. "
                    "C'est l'indicateur qui dépend le moins de l'offre de soins."},
    {"dataset": "gestes-auto-infliges-patients-hospitalises-departement", "niveau": "dep", "code": "num_departement",
     "where": 'classe_d_age="Tous" and sexe="Hommes et Femmes"', "valeur": "taux_standardise",
     "id": "hospit_gestes_auto_infliges", "libelle": "Personnes hospitalisées pour geste auto-infligé",
     "unite": "pour 100 000 hab., standardisé sur l'âge", "source": ODISSE_SOURCE + ", d'après le PMSI-MCO",
     "explication": "Personnes hospitalisées au moins une fois dans l'année pour une tentative de suicide ou une "
                    "automutilation, en hôpital général. Les hospitalisations en établissement psychiatrique ne sont "
                    "pas comptées."},
    {"dataset": "gestes-auto-infliges-passages-aux-urgences-departement", "niveau": "dep", "code": "new_dpt",
     "where": 'classe_d_age="Tous" and sexe="Hommes et Femmes"', "valeur": "part_activite",
     "id": "urgences_gestes_auto_infliges", "libelle": "Passages aux urgences pour geste auto-infligé",
     "unite": "pour 100 000 passages aux urgences", "source": ODISSE_SOURCE + ", d'après le réseau OSCOUR",
     "explication": "Part des passages aux urgences motivés par une tentative de suicide, une automutilation ou une "
                    "intoxication médicamenteuse volontaire, parmi l'ensemble des passages. Ce n'est pas un taux "
                    "rapporté à la population, il dépend aussi de l'usage des urgences dans le département."},
    {"dataset": "sante-mentale-episodes-depressifs-caracterises-dans-les-12-derniers-mois_reg", "niveau": "reg",
     "code": "reg", "where": 'sexe="Hommes et Femmes"', "valeur": "taux_depisodes_depressifs_12_derniers_mois",
     "ic_bas": "borne_inferieure_de_lintervalle_de_confiance_du_taux_depisodes_depressifs_au_cours_des_12_derniers_m",
     "ic_haut": "borne_superieure_de_lintervalle_de_confiance_du_taux_depisodes_depressifs_au_cours_des_12_derniers_m",
     "id": "episode_depressif_declare", "libelle": "Adultes déclarant un épisode dépressif dans l'année",
     "unite": "% des adultes", "source": ODISSE_SOURCE + ", Baromètre de Santé publique France",
     "explication": "Part des adultes interrogés dont les réponses correspondent à un épisode dépressif "
                    "caractérisé au cours des 12 derniers mois. Mesure déclarée par les personnes elles-mêmes, "
                    "indépendante du recours aux soins. Disponible seulement par région."},
    {"dataset": "conduites-suicidaires-indicateurs-du-barometre-de-sante-publique-france-2024-detail-region",
     "niveau": "reg", "code": "nouvelles_regions",
     "where": 'indicateur="Pensées suicidaires au cours des 12 derniers mois" and classe_d_age="Tous" and sexe="Tous"',
     "valeur": "estimation", "ic_bas": "ic_inf", "ic_haut": "ic_sup",
     "id": "pensees_suicidaires_declarees", "libelle": "Adultes déclarant des pensées suicidaires dans l'année",
     "unite": "% des adultes", "source": ODISSE_SOURCE + ", Baromètre de Santé publique France",
     "explication": "Part des adultes interrogés qui déclarent avoir pensé au suicide au cours des 12 derniers mois. "
                    "Disponible seulement par région."},
    {"dataset": "conduites-suicidaires-indicateurs-du-barometre-de-sante-publique-france-2024-detail-region",
     "niveau": "reg", "code": "nouvelles_regions",
     "where": 'indicateur="Tentative de suicide au cours de la vie" and classe_d_age="Tous" and sexe="Tous"',
     "valeur": "estimation", "ic_bas": "ic_inf", "ic_haut": "ic_sup",
     "id": "tentative_suicide_vie_declaree", "libelle": "Adultes déclarant une tentative de suicide au cours de la vie",
     "unite": "% des adultes", "source": ODISSE_SOURCE + ", Baromètre de Santé publique France",
     "explication": "Part des adultes interrogés qui déclarent avoir fait une tentative de suicide au cours de leur "
                    "vie. Disponible seulement par région."},
]

# ---------------------------------------------------------------- INSEE, temps d'accès par la route
# « Données sur la localisation et l'accès de la population aux équipements », jeu data.gouv vérifié le
# 4 octobre 2026 (identifiant 67fe0fe2423db9c4a05d8ced, Licence Ouverte, millésimes 2024 et 2025). Un fichier
# parquet par région, carreaux de 200 m, durée en voiture vers l'équipement le plus proche de chaque type de
# la base permanente des équipements (BPE). Chaque fichier régional (16 Go par millésime au total) est
# téléchargé, résumé par commune puis supprimé, seul le résumé reste en cache. Les professionnels de la BPE sont ceux qui
# exercent à titre libéral. Codes et libellés vérifiés dans le fichier des gammes BPE 2025 de l'INSEE.
ACCES_ROUTE_DATAGOUV = "67fe0fe2423db9c4a05d8ced"
ACCES_ROUTE_MOTIF = r"donnees_(\d{4})_reg(\d{2})\.parquet"
ACCES_ROUTE_SEUILS = (15, 20, 30)     # minutes
ACCES_ROUTE = [  # code BPE, identifiant, libellé d'affichage, famille, profession RPPS comparable
    ("D250", "psychologue_liberal", "Psychologue libéral", SANTE_MENTALE, "psychologue"),
    ("D269", "psychiatre_liberal", "Psychiatre libéral", SANTE_MENTALE, "psychiatre"),
    ("D109", "psychiatrie_ambulatoire", "Structure de psychiatrie ambulatoire, dont les centres médico-psychologiques (CMP)",
     SANTE_MENTALE, None),
    ("D104", "etablissement_psychiatrie", "Établissement spécialisé en psychiatrie", SANTE_MENTALE, None),
    ("D114", "addictions", "Service de prise en charge des addictions", SANTE_MENTALE, None),
    ("D265", "generaliste_liberal", "Médecin généraliste libéral", SANTE, "medecin_generaliste"),
    ("D272", "pediatre_liberal", "Pédiatre libéral", SANTE, "pediatre"),
    ("D282", "orthophoniste_liberal", "Orthophoniste libéral", SANTE, "orthophoniste"),
    ("D248", "psychomotricien_liberal", "Psychomotricien libéral", SANTE, "psychomotricien"),
    ("D281", "infirmier_liberal", "Infirmier libéral", SANTE, "infirmier"),
    ("D106", "urgences", "Service d'urgences", SANTE, None),
]

# ---------------------------------------------------------------- Assurance Maladie, affections de longue durée
# Jeu data.gouv « Bénéficiaires du dispositif des affections de longue durée (ALD) », vérifié le 7 octobre 2026
# (Cnam, Licence Ouverte, et non ODbL comme la cartographie des pathologies). Un classeur .xls par année, tableau VII
# (effectifs arrondis à la dizaine) et tableau VIII (taux standardisé sur l'âge pour 100 000 personnes protégées),
# les 30 affections par département, régime général seulement. Les 30 affections sont écrites dans
# ald_departements.csv. Seules les affections fréquentes deviennent des indicateurs (taux plus stables).
ALD_DATAGOUV = "55095017c751df68c9882844"
ALD_MOTIF = r"par departement en (\d{4})"
GROUPE_ALD = "Maladies chroniques (ALD)"
# numéro, libellé d'affichage, famille
ALD_INDICATEURS = [
    (23, "Affections psychiatriques de longue durée", SANTE_MENTALE),
    (15, "Maladie d'Alzheimer et autres démences", SANTE_MENTALE),
    (8, "Diabète", SANTE),
    (30, "Cancers (tumeurs malignes)", SANTE),
    (5, "Maladies cardiaques graves", SANTE),   # nom officiel complet dans l'explication de l'indicateur
    (13, "Maladie coronaire", SANTE),
    (1, "Accident vasculaire cérébral invalidant", SANTE),
    (14, "Insuffisance respiratoire chronique grave", SANTE),
    (16, "Maladie de Parkinson", SANTE),
]

# ---------------------------------------------------------------- CAF, allocataires par prestation
# Portail Opendatasoft de la CNAF, vérifié le 7 octobre 2026 (Licence Ouverte). s_ben_epci_f, une ligne par
# intercommunalité et par mois de décembre depuis 2020, effectifs arrondis à 5. s_ben_dep, une ligne par département
# et par mois depuis 2016. Le même mois de décembre est retenu aux deux niveaux, les régions sont la somme des
# départements. Les allocataires du régime agricole (MSA) ne sont pas comptés.
CAF_API = "https://data.caf.fr/api/explore/v2.1/catalog/datasets/"
CAF_PAGE = "https://data.caf.fr/explore/dataset/{}/"
CAF_JEUX = {"epci": ("s_ben_epci_f", "numepci"), "dep": ("s_ben_dep", "numdep")}
# identifiant ici, champ CAF, libellé, unité, facteur (pour 1 000 ou %), groupe, explication
CAF_INDICATEURS = [
    ("caf_aah", "indben_aah", "Bénéficiaires de l'AAH", "pour 1 000 habitants", 1000, "Protection de l'enfance et handicap",
     "Personnes qui perçoivent l'AAH, l'allocation versée par la CAF aux adultes en situation de handicap, en "
     "décembre, rapportées à la population. Repère de la place du handicap reconnu chez les adultes."),
    ("caf_aeeh", "indben_aeeh", "Bénéficiaires de l'AEEH", "pour 1 000 habitants", 1000, "Protection de l'enfance et handicap",
     "Bénéficiaires de l'AEEH, l'allocation versée par la CAF aux parents d'un enfant de moins de 20 ans en "
     "situation de handicap, rapportés à la population."),
    ("caf_rsa", "indnbp_rsa", "Population couverte par le RSA", "%", 100, "Vulnérabilité psychosociale",
     "Allocataires du revenu de solidarité active (RSA) versé par la CAF, avec leur conjoint et leurs enfants à "
     "charge, rapportés à la population."),
]

# ---------------------------------------------------------------- INSEE, estimations de population
# Interface Melodi de l'INSEE, jeu DS_ESTIMATION_POPULATION vérifié le 7 octobre 2026 (Licence Ouverte), population
# au 1er janvier par département depuis 1975 (Mayotte depuis 2014), provisoire pour les trois dernières années. Sert
# seulement aux densités de l'évolution de l'offre.
INSEE_ESTIMATIONS_API = "https://api.insee.fr/melodi/data/DS_ESTIMATION_POPULATION"
INSEE_ESTIMATIONS_PAGE = "https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DS_ESTIMATION_POPULATION"
# évolution de l'offre sur dix ans, d'après les séries de la DREES tirées du RPPS (les séries ADELI sont interrompues)
EVOLUTION_DEBUT, EVOLUTION_FIN = 2016, 2026
EVOLUTION_SERIES = [  # motif DREES, spécialité, profession ici, libellé
    (r"^medecins rpps", r"medecine generale", "medecin_generaliste", "Médecins généralistes"),
    (r"^medecins rpps", r"psychiatrie", "psychiatre", "Psychiatres, y compris psychiatres de l'enfant"),
    (r"^medecins rpps", r"pediatrie", "pediatre", "Pédiatres"),
    (r"^medecins rpps", r"gynecologie", "gynecologue", "Gynécologues"),
    (r"^medecins rpps", r"ophtalmologie", "ophtalmologue", "Ophtalmologues"),
    (r"^chirurgiens dentistes rpps", None, "chirurgien_dentiste", "Chirurgiens-dentistes"),
    (r"^kinesitherapeutes rpps", None, "masseur_kinesitherapeute", "Masseurs-kinésithérapeutes"),
    (r"^sages femmes rpps", None, "sage_femme", "Sages-femmes"),
    (r"^pharmaciens rpps", None, "pharmacien", "Pharmaciens"),
]

# ---------------------------------------------------------------- DREES, accessibilité potentielle localisée
# Jeu 530 du portail de la DREES (Opendatasoft), vérifié le 4 octobre 2026, Licence Ouverte. Un classeur par
# profession, une feuille par millésime (2022 à 2024), une ligne par commune. Sert à vérifier que notre
# accessibilité à deux étapes classe les territoires comme l'indicateur officiel, pour les professions où il
# existe. Les pièces jointes sont listées par l'API, aucune adresse de fichier n'est écrite en dur.
APL_API = ("https://data.drees.solidarites-sante.gouv.fr/api/explore/v2.1/catalog/datasets/"
           "530_l-accessibilite-potentielle-localisee-apl")
APL_PROFESSIONS = [  # motif sur le titre de la pièce jointe (sans accents), profession RPPS
    (r"apl aux medecins generalistes", "medecin_generaliste"),
    (r"apl aux infirmi", "infirmier"),
    (r"apl aux kinesitherapeutes", "masseur_kinesitherapeute"),
    (r"apl aux sages femmes", "sage_femme"),
    (r"apl aux chirurgiens dentistes", "chirurgien_dentiste"),
]

# ---------------------------------------------------------------- DREES, démographie des professionnels de santé
# Séries publiées par la DREES (RPPS, Adeli jusqu'en 2024, SNDS et base Tous salariés pour les infirmières).
# Elles ne servent pas aux résultats, seulement au tableau de concordance qui vérifie nos effectifs
# (pipeline/concordance.py). Jeu et pièces jointes vérifiés par l'API le 5 octobre 2026, Licence Ouverte.
DREES_DEMOGRAPHIE_API = ("https://data.drees.solidarites-sante.gouv.fr/api/explore/v2.1/catalog/datasets/"
                         "la-demographie-des-professionnels-de-sante-depuis-2012")
DREES_DEMOGRAPHIE_PAGE = ("https://data.drees.solidarites-sante.gouv.fr/explore/dataset/"
                          "la-demographie-des-professionnels-de-sante-depuis-2012/information/")
# (motif sur le titre de la pièce jointe sans accents, motif sur la spécialité DREES ou None, mode du programme,
#  professions du programme, libellé, champ de la DREES). « medecins » désigne toutes les spécialités de médecins.
_RPPS = "actifs au 1er janvier, inscrits à l'ordre, toutes activités en France"
_ADELI = "inscrits au répertoire Adeli, actifs occupés au 1er janvier, âgés de moins de 62 ans"
DREES_DEMOGRAPHIE = [
    (r"^medecins rpps", None, "all", ["medecins"], "Médecins, toutes spécialités", _RPPS),
    (r"^medecins rpps", r"medecine generale", "all", ["medecin_generaliste"], "Médecins généralistes", _RPPS),
    (r"^medecins rpps", r"psychiatrie", "all", ["psychiatre", "pedopsychiatre"],
     "Psychiatres, dont psychiatres de l'enfant", _RPPS),
    (r"^medecins rpps", r"pediatrie", "all", ["pediatre"], "Pédiatres",
     _RPPS + ", la DREES range aussi la génétique médicale avec la pédiatrie"),
    (r"^medecins rpps", r"gynecologie", "all", ["gynecologue"], "Gynécologues", _RPPS),
    (r"^medecins rpps", r"ophtalmologie", "all", ["ophtalmologue"], "Ophtalmologues", _RPPS),
    (r"^medecins rpps", r"cardiologie", "all", ["cardiologue"], "Cardiologues", _RPPS),
    (r"^medecins rpps", r"dermatologie", "all", ["dermatologue"], "Dermatologues", _RPPS),
    (r"^chirurgiens dentistes rpps", None, "all", ["chirurgien_dentiste"], "Chirurgiens-dentistes", _RPPS),
    (r"^kinesitherapeutes rpps", None, "all", ["masseur_kinesitherapeute"], "Masseurs-kinésithérapeutes", _RPPS),
    (r"^sages femmes rpps", None, "all", ["sage_femme"], "Sages-femmes", _RPPS),
    (r"^pharmaciens rpps", None, "all", ["pharmacien"], "Pharmaciens", _RPPS),
    (r"^pedicures podologues rpps", None, "all", ["pedicure_podologue"], "Pédicures-podologues", _RPPS),
    (r"^psychologues adeli", None, "all", ["psychologue"], "Psychologues", _ADELI),
    (r"^psychomotriciens adeli", None, "all", ["psychomotricien"], "Psychomotriciens", _ADELI),
    (r"^orthophonistes adeli", None, "all", ["orthophoniste"], "Orthophonistes", _ADELI),
    (r"^orthoptistes adeli", None, "all", ["orthoptiste"], "Orthoptistes", _ADELI),
    (r"^ergotherapeutes adeli", None, "all", ["ergotherapeute"], "Ergothérapeutes", _ADELI),
    (r"^dieteticiens adeli", None, "all", ["dieteticien"], "Diététiciens", _ADELI),
    (r"^audioprothesistes adeli", None, "all", ["audioprothesiste"], "Audioprothésistes", _ADELI),
    (r"^manipulateurs erm adeli", None, "all", ["manipulateur_erm"], "Manipulateurs en électroradiologie", _ADELI),
    (r"^opticiens lunetiers adeli", None, "all", ["opticien_lunetier"], "Opticiens-lunetiers", _ADELI),
    (r"^techniciens de laboratoire adeli", None, "all", ["technicien_labo"], "Techniciens de laboratoire", _ADELI),
    (r"^infirmieres liberales snds", None, "lib", ["infirmier"], "Infirmiers libéraux",
     "infirmières libérales ayant eu une activité remboursée dans l'année (SNDS), hors Mayotte"),
    (r"^infirmieres salariees bts", None, "sal", ["infirmier"], "Infirmiers salariés",
     "personnes en poste principal d'infirmière salariée au 31 décembre (base Tous salariés de l'INSEE), "
     "hors Mayotte"),
]

# ---------------------------------------------------------------- Contours (analyse spatiale, optionnelle)
# IGN, ADMIN EXPRESS COG CARTO PE (petite échelle), Licence Ouverte 2.0, lu par le service WFS de la
# Géoplateforme. Vérifié le 4 octobre 2026 (34 877 communes, COG en vigueur, Hexagone et DROM, GeoJSON en WGS84,
# pages de 5 000 objets). Remplace le dépôt tiers france-geojson (IGN 2018). Date de mise à jour côté producteur,
# champ last_update du jeu ADMIN EXPRESS sur data.gouv.
CONTOURS_WFS = "https://data.geopf.fr/wfs/ows"
CONTOURS_COUCHE = "ADMINEXPRESS-COG-CARTO-PE.LATEST:commune"
CONTOURS_PAGE = 5000
CONTOURS_DATAGOUV = "5808de39c751df1e0679df72"
CONTOURS_PAGE_PRODUCTEUR = ("https://www.data.gouv.fr/datasets/admin-express-admin-express-cog-admin-express-cog-carto-"
                            "admin-express-cog-carto-pe-admin-express-cog-carto-plus-pe")

# ---------------------------------------------------------------- producteurs et licences des sources
# Repris par le journal (util.JOURNAL.note) pour la page « Méthode et données » et la fin des rapports. Licences
# vérifiées le 4 octobre 2026 sur l'API de data.gouv (champ license), les métadonnées des portails Opendatasoft
# (Assurance Maladie, Santé publique France, DREES) et les pages des producteurs. Motif sur le nom de la source
# dans le journal, producteur, licence, page de présentation du jeu de données.
SOURCES_INFO = [
    (r"^RPPS", "Agence du numérique en santé (ANS)", "Licence Ouverte 2.0",
     "https://www.data.gouv.fr/datasets/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps"),
    (r"^FINESS \(Finess\+\)", "Agence du numérique en santé (ANS)", "Licence Ouverte 2.0",
     "https://www.data.gouv.fr/datasets/finess-structures-1"),
    (r"^FINESS", "Ministère chargé de la santé", "Licence Ouverte 2.0",
     "https://www.data.gouv.fr/datasets/finess-extraction-du-fichier-des-etablissements"),
    (r"^INSEE dossier", "INSEE", "Licence Ouverte 2.0", INSEE_PAGE_DOSSIER),
    (r"^INSEE, temps", "INSEE", "Licence Ouverte 2.0 (distancier fondé sur OpenStreetMap, © ses contributeurs)",
     "https://www.data.gouv.fr/datasets/donnees-sur-la-localisation-et-lacces-de-la-population-aux-equipements"),
    (r"^Assurance Maladie, pathologies", "Caisse nationale de l'Assurance Maladie (Cnam)",
     "ODbL 1.0 (partage à l'identique)", "https://data.ameli.fr/explore/dataset/effectifs/"),
    (r"^Assurance Maladie, affections de longue durée", "Caisse nationale de l'Assurance Maladie (Cnam)",
     "Licence Ouverte 2.0", "https://www.data.gouv.fr/datasets/beneficiaires-du-dispositif-des-affections-de-longue-duree-ald"),
    (r"^CAF", "Caisse nationale des allocations familiales (CNAF)", "Licence Ouverte 2.0", None),   # page notée par le module
    (r"^INSEE, estimations", "INSEE", "Licence Ouverte 2.0", INSEE_ESTIMATIONS_PAGE),
    (r"^Assurance Maladie", "Caisse nationale de l'Assurance Maladie (Cnam)", "ODbL 1.0 (partage à l'identique)",
     None),   # page notée par le module
    (r"^Santé publique France", "Santé publique France", "Licence Ouverte 2.0", None),   # page déduite de l'adresse
    (r"^DREES, démographie", "DREES", "Licence Ouverte 2.0", DREES_DEMOGRAPHIE_PAGE),
    (r"^DREES, accessibilité", "DREES", "Licence Ouverte 2.0",
     "https://data.drees.solidarites-sante.gouv.fr/explore/dataset/530_l-accessibilite-potentielle-localisee-apl/"),
    (r"^DREES", "DREES", "Licence Ouverte 2.0", None),   # page notée par le module
    (r"^Référentiel", "Etalab, d'après le Code officiel géographique et les populations légales de l'INSEE",
     "Licence Ouverte 2.0", "https://github.com/etalab/decoupage-administratif"),
    (r"^Contours", "IGN, ADMIN EXPRESS COG CARTO PE", "Licence Ouverte 2.0", CONTOURS_PAGE_PRODUCTEUR),
]

# ---------------------------------------------------------------- France Travail (optionnel)
FT_TOKEN = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
FT_OFFRES = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
FT_SCOPE = "api_offresdemploiv2 o2dsoffre"
# Codes ROME et profession correspondante (à vérifier si France Travail fait évoluer le ROME)
FT_ROME = {
    "K1104": "psychologue",
    "J1102": "medecin_generaliste",
    "J1506": "infirmier",
    "J1404": "masseur_kinesitherapeute",
    "J1406": "orthophoniste",
}

# ---------------------------------------------------------------- Professions
# Chaque entrée associe un motif (sur le libellé normalisé) à un identifiant, un libellé, un groupe
# et une famille. La famille sépare l'offre en santé mentale du reste de l'offre de soins. Pour
# changer le classement d'une profession, il suffit de modifier sa famille ici.
# Classement validé avec Lucas le 3 octobre 2026. Psychomotriciens, orthophonistes, ergothérapeutes
# et infirmiers restent en « Santé » au sens strict. Ceux qui travaillent dans un établissement
# psychiatrique sont repris dans le périmètre élargi (voir FINESS_SANTE_MENTALE).
FAMILLES = [SANTE_MENTALE, SANTE]
PROFESSIONS = [
    (r"psychologue", "psychologue", "Psychologue", "Psychologie et psychothérapie", SANTE_MENTALE),
    (r"psychotherapeute", "psychotherapeute", "Psychothérapeute", "Psychologie et psychothérapie", SANTE_MENTALE),
    (r"psychomotricien", "psychomotricien", "Psychomotricien", "Rééducation", SANTE),
    (r"orthophoniste", "orthophoniste", "Orthophoniste", "Rééducation", SANTE),
    (r"orthoptiste", "orthoptiste", "Orthoptiste", "Rééducation", SANTE),
    (r"ergotherapeute", "ergotherapeute", "Ergothérapeute", "Rééducation", SANTE),
    (r"kinesitherapeute", "masseur_kinesitherapeute", "Masseur-kinésithérapeute", "Rééducation", SANTE),
    (r"pedicure|podologue", "pedicure_podologue", "Pédicure-podologue", "Rééducation", SANTE),
    (r"dieteticien", "dieteticien", "Diététicien", "Rééducation", SANTE),
    (r"infirmier", "infirmier", "Infirmier", "Premier recours", SANTE),
    (r"sage.?femme", "sage_femme", "Sage-femme", "Premier recours", SANTE),
    (r"chirurgien.?dentiste", "chirurgien_dentiste", "Chirurgien-dentiste", "Premier recours", SANTE),
    (r"pharmacien", "pharmacien", "Pharmacien", "Premier recours", SANTE),
    (r"audio.?prothesiste", "audioprothesiste", "Audioprothésiste", "Appareillage", SANTE),
    (r"opticien", "opticien_lunetier", "Opticien-lunetier", "Appareillage", SANTE),
    (r"orthopediste|orthesiste|orthoprothesiste|podo.?orthesiste|ocularis|epithesiste", "appareilleur", "Appareilleur",
     "Appareillage", SANTE),
    (r"manipulateur", "manipulateur_erm", "Manipulateur en électroradiologie", "Médico-technique", SANTE),
    (r"technicien de laboratoire", "technicien_labo", "Technicien de laboratoire", "Médico-technique", SANTE),
    (r"physicien medical", "physicien_medical", "Physicien médical", "Médico-technique", SANTE),
    (r"assistant dentaire", "assistant_dentaire", "Assistant dentaire", "Premier recours", SANTE),
    (r"osteopathe", "osteopathe", "Ostéopathe", "Rééducation", SANTE),
    (r"chiropracteur", "chiropracteur", "Chiropracteur", "Rééducation", SANTE),
]
# Spécialités des médecins (libellé normalisé de la spécialité ordinale), par ordre de priorité.
# Chaque médecin reçoit une seule spécialité, celle de son inscription à l'Ordre.
SPECIALITES_MEDECINS = [
    (r"psychiatr.*(enfant|adolescent)|pedopsychiatr", "pedopsychiatre", "Pédopsychiatre", "Psychiatrie", SANTE_MENTALE),
    (r"psychiatr", "psychiatre", "Psychiatre", "Psychiatrie", SANTE_MENTALE),
    (r"medecine generale", "medecin_generaliste", "Médecin généraliste", "Premier recours", SANTE),
    # « pédiatrie » seulement, pas la chirurgie pédiatrique ni la réanimation pédiatrique (vérifié le 5 octobre 2026)
    (r"\bpediatrie\b", "pediatre", "Pédiatre", "Médecins spécialistes", SANTE),
    (r"neurolog", "neurologue", "Neurologue", "Médecins spécialistes", SANTE),
    (r"geriatr", "geriatre", "Gériatre", "Médecins spécialistes", SANTE),
    # « gyneco » couvre aussi le DES de 2017 « Gynéco-obstétrique et Gynéco médicale option... »
    (r"gyneco", "gynecologue", "Gynécologue", "Médecins spécialistes", SANTE),
    (r"ophtalmolog", "ophtalmologue", "Ophtalmologue", "Médecins spécialistes", SANTE),
    # « Méd cardiovasculaire opt... » est le DES de cardiologie depuis 2017, la chirurgie cardio-vasculaire est exclue
    (r"cardiolog|\bmed\w* cardiovasculaire", "cardiologue", "Cardiologue", "Médecins spécialistes", SANTE),
    (r"dermatolog", "dermatologue", "Dermatologue", "Médecins spécialistes", SANTE),
]
MEDECIN_AUTRE = ("medecin_autre", "Médecin, autre spécialité", "Médecins spécialistes", SANTE)
MEDECIN_INCONNU = ("medecin_non_precise", "Médecin, spécialité non renseignée", "Médecins spécialistes", SANTE)
GROUPE_AUTRES = ("Autres", SANTE)   # libellés RPPS non reconnus par les motifs ci-dessus
# Libellés RPPS qui ne désignent pas une profession de soin et sont écartés des comptages.
# « Acteur du système de santé caractérisé par un rôle » regroupe environ 65 000 personnes
# (personnels administratifs et d'appui) dans l'extraction du 3 octobre 2026.
PROFESSIONS_EXCLUES = [r"caracterise par un role"]

# Qualifications complémentaires des médecins. Elles ne remplacent pas la spécialité, elles
# s'y ajoutent. Un médecin peut donc être compté à la fois comme psychiatre et dans
# « psychiatrie de l'enfant, toutes voies ». Ces comptages ne doivent jamais être additionnés
# aux professions. Motif sur le libellé du savoir-faire, tous types confondus (spécialité,
# compétence, capacité, DESC, FST, droit d'exercice complémentaire).
QUALIFICATIONS_MEDECINS = [
    (r"psychiatr.*(enfant|adolescent)|pedopsychiatr", "q_psychiatrie_enfant",
     "Psychiatre qualifié pour l'enfant et l'adolescent (toutes voies)", SANTE_MENTALE),
    (r"addictolog", "q_addictologie", "Médecin qualifié en addictologie", SANTE_MENTALE),
]
GROUPE_QUALIFICATIONS = "Qualifications complémentaires"

# ---------------------------------------------------------------- Santé mentale, périmètre élargi
# Catégories FINESS d'établissements psychiatriques ou médico-psychologiques. Tout professionnel
# salarié d'un de ces établissements entre dans le périmètre élargi, quelle que soit sa profession.
# L'hôpital de jour psychiatrique n'a pas de catégorie propre, il est enregistré sous le CHS ou le
# CMP dont il dépend. Les services de psychiatrie des hôpitaux généraux (catégorie 355) ne sont pas
# repérables et restent hors périmètre. Codes vérifiés dans le flux FINESS du 4 mai 2026 et Finess+
# de septembre 2026 (le 3 octobre 2026).
FINESS_SANTE_MENTALE = {
    "292": "Centre hospitalier spécialisé en psychiatrie (CHS, EPSM)",
    "156": "Centre médico-psychologique (CMP)",
    "425": "Centre d'accueil thérapeutique à temps partiel (CATTP)",
    "161": "Maison de santé spécialisée en psychiatrie",
    "444": "Centre de crise et d'accueil permanent en psychiatrie",
    "430": "Centre de postcure psychiatrique",
    "412": "Appartement thérapeutique",
    "366": "Atelier thérapeutique",
    "415": "Service médico-psychologique régional (SMPR, prison)",
    "189": "Centre médico-psycho-pédagogique (CMPP)",
    "221": "Bureau d'aide psychologique universitaire (BAPU)",
    "197": "Centre de soins, d'accompagnement et de prévention en addictologie (CSAPA)",
}
PREFIXE_ELARGI = "esm_"
GROUPE_ELARGI = "Salariés des établissements psychiatriques (périmètre élargi)"
ELARGI_EFFECTIF_MIN = 100   # en dessous, la profession n'est pas présentée dans le périmètre élargi

# Professions retenues pour les analyses les plus coûteuses (modèles, typologie, spatial)
PROFESSIONS_PRINCIPALES = [
    "psychologue", "psychiatre", "pedopsychiatre", "medecin_generaliste", "infirmier",
    "masseur_kinesitherapeute", "orthophoniste", "psychomotricien", "pharmacien",
    "chirurgien_dentiste", "sage_femme", "pediatre",
]

# Public concerné par une profession, pour la densité rapportée à ce public (indicateurs de part de
# config.CONTEXTE additionnés). Le recensement publie les moins de 15 ans, pas les moins de 18 ans.
PUBLICS_CIBLES = {
    "pedopsychiatre": (["part_0_14"], "moins de 15 ans"),
    "q_psychiatrie_enfant": (["part_0_14"], "moins de 15 ans"),
    "pediatre": (["part_0_14"], "moins de 15 ans"),
    "orthophoniste": (["part_0_14"], "moins de 15 ans"),
    "psychomotricien": (["part_0_14"], "moins de 15 ans"),
    "geriatre": (["part_65_79", "part_80p"], "65 ans et plus"),
}

# Professions croisées avec les indicateurs de besoin en santé mentale (quadrants offre et besoin)
PROFESSIONS_QUADRANTS = ["psychiatre", "psychologue", "q_psychiatrie_enfant", "medecin_generaliste"]

# Paires de professions testées pour la substitution ou le cumul (point 8 du chantier 4)
PAIRES_SUBSTITUTION = [("medecin_generaliste", "psychologue"), ("medecin_generaliste", "psychiatre"),
                       ("psychologue", "psychiatre"), ("psychiatre", "pedopsychiatre"),
                       ("orthophoniste", "psychomotricien"), ("pediatre", "medecin_generaliste"),
                       ("infirmier", "medecin_generaliste")]

# Effectif minimal publié dans les croisements très fins (liens entre territoires)
SECRET_MIN = 3

# Regroupement des secteurs d'activité du RPPS pour « qui porte l'offre » (libellés officiels, motifs normalisés)
SECTEURS_GROUPES = [
    (r"cabinet|exercice en societe|maison de sante|pole de sante", "Libéral (cabinet, société, maison de santé)"),
    (r"etablissement public de sante|hopitaux militaires", "Hôpital public"),
    (r"prive", "Établissement de santé privé"),
    (r"handicap|personnes agees|protection enfance|hebergt readaptation|aide a la famille", "Médico-social"),
    (r"centres? de sante", "Centre de santé"),
]
SECTEUR_AUTRE = "Autre ou non renseigné"

# Catégorie de chaque secteur d'activité du RPPS (décision de Lucas du 4 octobre 2026, voir
# docs/note_secteurs_hors_soins.md). Motif sur le libellé normalisé (util.norm), professions concernées (None pour
# toutes), catégorie. La première ligne qui correspond l'emporte, un secteur absent de la liste relève des soins.
#   soins                 soins à la population, chiffres principaux (densités, cartes, comparaisons)
#   public_particulier    soins ou prévention pour un public particulier, gardés dans les chiffres principaux
#                         et repérables dans les fichiers
#   sans_soins            activités sans soins à la population, souvent déclarées au siège d'un organisme, retirées
#                         des densités et comptées à part, territoire par territoire. Les personnes restent dans
#                         l'effectif national.
SECTEUR_TELECONSULTATION = r"teleconsultation"
MEDECINS = ({x[1] for x in SPECIALITES_MEDECINS} | {MEDECIN_AUTRE[0], MEDECIN_INCONNU[0]}
            | {x[1] for x in QUALIFICATIONS_MEDECINS})
SECTEURS_CATEGORIES = [
    (SECTEUR_TELECONSULTATION, None, "sans_soins"),
    (r"^organisme de securite sociale$", None, "sans_soins"),          # contrôle médical
    (r"^autres structures du ssa$", None, "sans_soins"),              # un seul établissement, « SSA Paris »
    (r"^assurances privees$", None, "sans_soins"),
    (r"^fab exploit import med dm$|^repart distrib medicament", None, "sans_soins"),
    (r"^com marketing consulting media$", None, "sans_soins"),
    (r"^recrutement gestion rh$", None, "sans_soins"),
    (r"^ordre de professionnels de sante$", None, "sans_soins"),
    (r"^siege social d es", None, "sans_soins"),
    (r"^recherche$", None, "sans_soins"),
    (r"^entreprise d interim$", None, "sans_soins"),                 # déclarée à l'adresse de l'agence
    # Services de l'État et des départements. Pour les médecins, surtout de l'administration (ARS, préfectures,
    # ministères, MDPH, OFII). Pour les autres professions, surtout des soins pour un public particulier
    # (psychologues et infirmiers de l'Éducation nationale, infirmiers de PMI, services sociaux des départements).
    (r"^ministere serv deconcentres$", MEDECINS, "sans_soins"),
    (r"^ministere serv deconcentres$", None, "public_particulier"),
    (r"^prev et soins en entreprise$|^services de prevention et de sante au travail$"
     r"|^entreprises industrielles et tertiaires", None, "public_particulier"),
    (r"^etablissement scolaire universitaire$|^etab d enseignement$", None, "public_particulier"),
    (r"^collectivites territoriales$", None, "public_particulier"),
    (r"^incendies et secours$|^services departementaux d incendie", None, "public_particulier"),
    (r"^hopitaux militaires$", None, "public_particulier"),
    (r"^centre de transfusion sanguine$", None, "public_particulier"),
]
CATEGORIES_SECTEURS = {"soins": "Soins à la population", "public_particulier": "Public particulier",
                       "sans_soins": "Sans soins à la population"}

# Loi inverse des soins (Tudor Hart), indicateurs de besoin qui classent les départements et professions testées
# ---------------------------------------------------------------- limites connues des données
# Demande de Lucas du 5 octobre 2026. Chaque fois qu'une donnée risque d'être sous-déclarée ou incomplète, le dire
# là où elle est montrée et renvoyer vers la source qui l'établit. Sources lues et vérifiées le 5 octobre 2026
# (note docs/note_suicide_ile_de_france_2026-10-05.md). Clés, identifiant d'indicateur, « prof:<profession> » ou
# « route ». « territoires », précision propre à certains départements.
SRC_SPF_IDF_2024 = ("Santé publique France, Conduites suicidaires en Île-de-France, bilan 2024",
                    "https://www.santepubliquefrance.fr/regions-et-territoires/ile-de-france/bulletin-regional/conduites-suicidaires-en-ile-de-france-bilan-2024")
SRC_ONS_FICHE14 = ("Observatoire national du suicide, 5e rapport, fiche 14 (DREES)",
                   "https://drees.solidarites-sante.gouv.fr/sites/default/files/2022-09/Fiche%2014%20-%20Donn%C3%A9es%20%C3%A9pid%C3%A9miologiques%20sur%20les%20d%C3%A9c%C3%A8s%20par%20suicide%20en%20France%20en%202017.pdf")
SRC_DREES_INFIRMIERES = ("DREES, démographie des infirmières et des aides-soignantes, données détaillées (mars 2025)",
                         "https://drees.solidarites-sante.gouv.fr/communique-de-presse-jeux-de-donnees/jeux-de-donnees/250325_DATA_d%C3%A9mographie-infirmieres-aides-soignantes-donnees")
SRC_ANS_BASCULE = ("Agence du numérique en santé, bascule des professionnels ADELI dans le RPPS",
                   "https://esante.gouv.fr/offres-services/annuaire-sante/bascule-des-professionnels-adeli-dans-le-rpps")
SRC_INSEE_ROUTE = ("INSEE, données sur la localisation et l'accès de la population aux équipements",
                   "https://www.data.gouv.fr/datasets/donnees-sur-la-localisation-et-lacces-de-la-population-aux-equipements")
SRC_DREES_SAE = ("DREES, bases statistiques de la SAE", "https://data.drees.solidarites-sante.gouv.fr/explore/dataset/708_bases-statistiques-sae/")
DEPS_ILE_DE_FRANCE = ["75", "77", "78", "91", "92", "93", "94", "95"]
DEPS_PACA_CORSE = ["04", "05", "06", "13", "83", "84", "2A", "2B"]
SRC_ALD = ("Assurance Maladie, bénéficiaires du dispositif des ALD (data.gouv)",
           "https://www.data.gouv.fr/datasets/beneficiaires-du-dispositif-des-affections-de-longue-duree-ald")
SRC_ALD_DEMANDE = ("ameli.fr, demande de prise en charge en ALD",
                   "https://www.ameli.fr/assure/droits-demarches/maladie-accident-hospitalisation/affection-longue-duree-ald/demande-prise-en-charge-en-ald")
SRC_ALD_HTA = ("Décret n° 2011-726 du 24 juin 2011 (Légifrance)", "https://www.legifrance.gouv.fr/loda/id/JORFTEXT000024249276/")
SRC_CAF_MSA = ("Mon parcours handicap, la Caf et la MSA",
               "https://www.monparcourshandicap.gouv.fr/principaux-interlocuteurs/la-caf-et-la-msa")
SRC_FINESS = ("FINESS, établissements sanitaires et médico-sociaux (Finess+, data.gouv)",
              "https://www.data.gouv.fr/datasets/finess-structures-1")
SRC_RPPS = ("Annuaire santé, extractions en libre accès du RPPS (data.gouv)",
            "https://www.data.gouv.fr/datasets/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps")
FINESS_CMP = "156"   # catégorie FINESS des centres médico-psychologiques
SRC_INSEE_MAYOTTE = ("INSEE, au 1er janvier 2026 la population de Mayotte est de 323 153 habitants",
                     "https://www.insee.fr/fr/information/9022279")
SRC_CAF_EPCI = ("CAF, allocataires par prestation et par intercommunalité", "https://data.caf.fr/explore/dataset/s_ben_epci_f/")
LIMITES = {
    "suicides": {
        "risque": "sous-déclaration",
        "texte": ("Les décès par suicide sont sous-déclarés. Les décès de cause inconnue ou d'intention indéterminée "
                  "ne sont pas comptés, et une partie des conclusions d'autopsie ne remontent pas. Pour les décès de "
                  "2006, la sous-estimation était évaluée à 9,4 % en France métropolitaine, 22 % en Rhône-Alpes et "
                  "46 % en Île-de-France. Santé publique France demande de lire les écarts entre départements avec "
                  "prudence."),
        "sources": [SRC_SPF_IDF_2024, SRC_ONS_FICHE14],
        "territoires": {d: ("En Île-de-France, la sous-déclaration des suicides est nettement plus forte qu'ailleurs, le "
                            "taux affiché est à lire comme un minimum.") for d in DEPS_ILE_DE_FRANCE}},
    "hospit_gestes_auto_infliges": {
        "risque": "champ incomplet",
        "texte": ("Seuls les séjours en hôpital de médecine, chirurgie et obstétrique sont comptés. Les séjours en "
                  "établissement psychiatrique ne le sont pas."),
        "sources": [SRC_SPF_IDF_2024]},
    "urgences_gestes_auto_infliges": {
        "risque": "sous-déclaration",
        "texte": ("Seuls les services d'urgences générales qui transmettent leurs données sont comptés, et le geste "
                  "n'est pas toujours identifié à l'accueil, d'où une sous-estimation probable. En Provence-Alpes-Côte "
                  "d'Azur et en Corse, un défaut de logiciel a sous-estimé ces passages de 2022 à avril 2024."),
        "sources": [SRC_SPF_IDF_2024],
        "territoires": {d: ("Dans ce département, un défaut de logiciel a sous-estimé les passages aux urgences pour "
                            "geste auto-infligé jusqu'en avril 2024.") for d in DEPS_PACA_CORSE}},
    "prof:infirmier": {
        "risque": "sous-enregistrement",
        "texte": ("Beaucoup d'infirmiers, surtout salariés, ne sont pas encore inscrits au RPPS malgré l'obligation. "
                  "Leurs effectifs sont donc sous-estimés ici, la DREES les compte à partir d'autres sources."),
        "sources": [SRC_DREES_INFIRMIERES]},
    "mayotte": {
        "risque": "données incomplètes",
        "texte": ("À Mayotte, la population de référence est celle du recensement de 2017 (256 518 habitants). Le "
                  "recensement exhaustif mené fin 2025 en compte 323 153 au 1er janvier 2026, soit environ un quart de "
                  "plus. Les densités de Mayotte sont donc surestimées d'autant. Les données de l'Assurance Maladie y "
                  "sont partielles et celles de la CAF absentes. Mayotte est écartée des croisements entre départements."),
        "sources": [SRC_INSEE_MAYOTTE]},
    "prof:psychiatre": {
        "risque": "lieu déclaré",
        "texte": ("Le répertoire situe chaque psychiatre à l'adresse de la structure où il déclare exercer. La plupart "
                  "des centres médico-psychologiques (CMP) de FINESS n'ont aucun psychiatre déclaré à leur adresse, "
                  "les consultations y sont rattachées à l'établissement dont ils dépendent. Un territoire sans "
                  "psychiatre déclaré peut donc accueillir des consultations de psychiatrie, le nombre de CMP de "
                  "chaque territoire est donné à côté quand il est connu."),
        "sources": [SRC_RPPS, SRC_FINESS]},
    "prof:pedopsychiatre": {
        "risque": "définition étroite",
        "texte": ("La spécialité « pédopsychiatrie » déclarée au répertoire ne concerne qu'une partie des médecins qui "
                  "soignent des enfants et des adolescents. La plupart sont inscrits comme psychiatres, avec une "
                  "qualification pour l'enfant obtenue par une autre voie. La Cour des comptes comptait 545 "
                  "pédopsychiatres au sens strict en 2021, et environ 2 000 en ajoutant les psychiatres qualifiés pour "
                  "l'enfant. Un territoire sans pédopsychiatre déclaré comme tel peut donc compter des psychiatres qui "
                  "soignent des enfants. Le nombre de psychiatres qualifiés pour l'enfant et l'adolescent, toutes "
                  "voies, est donné à côté."),
        "sources": [("Cour des comptes, la pédopsychiatrie, un accès et une offre de soins à réorganiser, mars 2023",
                     "https://www.ccomptes.fr/fr/publications/la-pedopsychiatrie"), SRC_RPPS]},
    "prof:psychologue": {
        "risque": "répertoire récent",
        "texte": ("Les psychologues sont inscrits au RPPS depuis la reprise du répertoire ADELI. Leur nombre est un "
                  "peu en dessous de la tendance des séries ADELI de la DREES, l'écart est détaillé dans la page "
                  "méthode."),
        "sources": [SRC_ANS_BASCULE, ("DREES, la démographie des professionnels de santé", DREES_DEMOGRAPHIE_PAGE)]},
    "route": {
        "risque": "champ limité",
        "texte": ("Temps d'un trajet en voiture aux heures creuses vers le professionnel libéral le plus proche. Il ne "
                  "dit rien des délais de rendez-vous, des tarifs ni des transports en commun, et ne couvre que "
                  "l'Hexagone, la Martinique et La Réunion."),
        "sources": [SRC_INSEE_ROUTE]},
    "sae": {
        "risque": "rattachement",
        "texte": ("Les moyens de la psychiatrie hospitalière sont déclarés par les établissements et rattachés au "
                  "département de l'établissement, pas à celui des patients."),
        "sources": [SRC_DREES_SAE]},
}
LIMITES["ald"] = {
    "risque": "reconnaissance administrative",
    "texte": ("Une affection de longue durée est reconnue à la demande du médecin, après accord du service médical de "
              "l'Assurance Maladie. Les chiffres comptent les personnes dont la maladie a été reconnue, pas toutes les "
              "personnes malades, et dépendent donc aussi du recours aux soins. Ils ne couvrent que le régime général. "
              "L'hypertension artérielle sévère n'ouvre plus de nouvelle ALD depuis juin 2011."),
    "sources": [SRC_ALD, SRC_ALD_DEMANDE, SRC_ALD_HTA],
    "territoires": {"976": "Pour Mayotte, l'Assurance Maladie indique que les données ne sont pas exhaustives."}}
LIMITES["caf"] = {
    "risque": "champ incomplet",
    "texte": ("Les allocations comptées ici sont celles versées par la CAF. Les personnes qui relèvent du régime "
              "agricole les reçoivent de la MSA et ne sont pas comptées, ce qui sous-estime ces chiffres surtout dans "
              "les territoires ruraux. Par intercommunalité, les effectifs sont arrondis à 5."),
    "sources": [SRC_CAF_MSA, SRC_CAF_EPCI],
    "territoires": {"976": "Mayotte n'apparaît pas dans ces données de la CAF."}}
LIMITES["evolution"] = {
    "risque": "champ différent",
    "texte": ("L'évolution vient des séries de la DREES, qui comptent chaque professionnel une seule fois, dans le "
              "département de son activité principale, alors que les autres chiffres de ce site comptent une personne "
              "dans chaque territoire où elle exerce. Les populations des trois dernières années sont provisoires."),
    "sources": [("DREES, la démographie des professionnels de santé", DREES_DEMOGRAPHIE_PAGE),
                ("INSEE, estimations localisées de population", INSEE_ESTIMATIONS_PAGE)]}
LIMITES_ALIAS = {"sae_": "sae", "ald_": "ald", "caf_": "caf", "evol:": "evolution"}

LOI_INVERSE_BESOINS = ["suicides", "hospit_gestes_auto_infliges", "pec_troubles_psy"]
LOI_INVERSE_PROFESSIONS = ["psychiatre", "psychologue", "q_psychiatrie_enfant", "medecin_generaliste"]
# Concordance entre indicateurs de besoin en santé mentale (départements)
CONCORDANCE_BESOINS = ["suicides", "hospit_gestes_auto_infliges", "urgences_gestes_auto_infliges", "pec_troubles_psy",
                       "pec_humeur", "antidepresseurs", "ase_mesures"]
# Croisement des indicateurs entre eux, par département, sans les professionnels (8 octobre 2026). Indicateurs de santé
# mentale, de recours aux soins et de vulnérabilité. Les indicateurs sous ODbL vont dans les fichiers _odbl.
INDICATEURS_CROISES = ["suicides", "hospit_gestes_auto_infliges", "urgences_gestes_auto_infliges", "ald_23", "ald_15",
                       "pec_troubles_psy", "pec_humeur", "antidepresseurs", "ase_mesures", "ase_placements", "caf_aah",
                       "caf_aeeh", "caf_rsa", "taux_pauvrete", "taux_chomage", "part_seuls", "part_monoparentales",
                       "part_sans_diplome", "part_logements_suroccupes", "part_80p_seuls", "part_minima_sociaux",
                       "densite_pop", "part_80p"]
# Régression multiple, indicateurs de besoin expliqués et petit jeu d'indicateurs sociaux peu redondants (densité en log)
REGRESSION_RESULTATS = ["suicides", "hospit_gestes_auto_infliges", "ald_23"]
REGRESSION_EXPLICATIVES = ["densite_pop", "part_80p", "taux_pauvrete", "part_seuls", "part_sans_diplome"]
# Croisements départementaux, mesure d'offre, indicateur croisé, question posée
CROISEMENTS = [
    ("dens_lib:psychiatre", "sae_etp_psychiatres", "hopital_liberal",
     "L'hôpital compense-t-il la faiblesse des psychiatres libéraux ?"),
    ("dens_lib:psychiatre", "sae_lits_psy", "hopital_liberal", ""),
    ("dens_lib:psychiatre", "sae_cmp", "hopital_liberal", ""),
    ("ctx:revenu_median", "depassements_psychiatre", "secteur2_revenu",
     "Dans les territoires aisés, l'offre de psychiatres est-elle plus chère ?"),
    ("dens:psychiatre", "depassements_psychiatre", "secteur2_revenu", ""),
    ("ctx:ase_mesures", "dens:q_psychiatrie_enfant", "enfance",
     "L'offre en psychiatrie de l'enfant suit-elle l'activité de protection de l'enfance ?"),
    ("ctx:ase_mesures", "sae_infanto", "enfance", ""),
    ("ctx:ase_mesures", "dens:pedopsychiatre", "enfance", ""),
    # audit du 4 octobre 2026, 3.3, 3.5 et 3.6 (temps médian par la route de l'INSEE, préfixe route:)
    ("route:psychiatrie_ambulatoire", "suicides", "trajet_suicide",
     "Les départements éloignés des CMP ont-ils plus de suicides, au-delà de la ruralité ?"),
    ("route:psychiatre_liberal", "suicides", "trajet_suicide", ""),
    ("ctx:handicap_places_enfants", "dens_lib:orthophoniste", "reeducation",
     "L'offre libérale de rééducation suit-elle l'offre médico-sociale pour les enfants ?"),
    ("ctx:handicap_places_enfants", "dens_lib:psychomotricien", "reeducation", ""),
    ("ctx:handicap_places_sessad", "dens_lib:orthophoniste", "reeducation", ""),
    ("dens_lib:medecin_generaliste", "ald_sans_medecin_traitant", "medecin_traitant",
     "Les patients sans médecin traitant sont-ils plus nombreux là où les généralistes libéraux manquent ?"),
    ("ctx:part_80p", "ald_sans_medecin_traitant", "medecin_traitant", ""),
]

NIVEAUX = ["com", "epci", "dep", "reg"]
NIVEAUX_ANALYSE = ["epci", "dep"]   # niveaux où les croisements statistiques sont calculés
BOOTSTRAP = 500                      # rééchantillonnages pour les intervalles de confiance
GRAINE = 20261003                    # reproductibilité

# ---------------------------------------------------------------- citation et identifiants pérennes
# Les DOI seront attribués par Zenodo au moment de la publication (chantier 8, accord de Lucas). Tant qu'ils valent
# None, les rapports, les PDF et l'atlas affichent la citation sans DOI.
# nom du site, choisi par Lucas le 9 octobre 2026 (« ubi cura », là où est le soin, en latin), et sous-titre descriptif
NOM_PROJET = "Ubi Cura"
SOUS_TITRE = "Offre de soins et santé mentale en France, territoire par territoire"
AUTEUR = "Lucas Pithon"
ORCID = "0000-0003-2400-368X"         # identifiant ORCID de Lucas (9 octobre 2026)
CONTACT = "contact@ubicura.fr"      # adresse de contact du site, chez OVHcloud (9 octobre 2026)
CITATION_AUTEUR = "Pithon L."
# DOI généraux (versions 1 publiées le 9 octobre 2026, rapport santé mentale 10.5281/zenodo.23265074, rapport santé 10.5281/zenodo.23265209). DOI réservés sur Zenodo le 9 octobre 2026 (première version, à publier avant la mise en ligne, tutoriel 05). Après la
# première publication, les remplacer par les DOI généraux, qui renvoient toujours à la dernière version.
DOI_DONNEES = "10.5281/zenodo.23264933"   # DOI général des données (première version publiée le 9 octobre 2026, 10.5281/zenodo.23264934)
DOI_RAPPORTS = {"sante-mentale": "10.5281/zenodo.23265073", "sante": "10.5281/zenodo.23265208"}
# dernière version archivée sur Zenodo (date du dossier de résultats). Une version plus récente du site est citée par son
# adresse, avec le DOI général à côté. À mettre à jour à chaque nouvelle version publiée sur Zenodo (tutoriels 05 et 07).
VERSION_ZENODO = "2026-10-09"
# titres des dépôts Zenodo, descriptifs et sans le nom du site (décision de Lucas du 9 octobre 2026), repris par les
# citations
TITRES_DEPOTS = {"donnees": "Offre de soins et santé mentale en France par territoire, données agrégées",
                 "sante-mentale": "L'offre de soins en santé mentale en France, rapport national",
                 "sante": "L'offre de soins en France, rapport national"}
ADRESSE_SITE = "https://ubicura.fr"   # adresse publique du site, en ligne depuis le 10 octobre 2026 (GitHub Pages)

# ---------------------------------------------------------------- journal des mises à jour
# Chaque fichier brut porte sa date côté producteur (maj_source dans le .meta.json). Le journal regroupe les fichiers
# par jeu de données, compare avec l'exécution précédente et dit quels jeux ont changé (pipeline/mises_a_jour.py).
# Motif sur le chemin du fichier dans donnees/brut, nom lu par le public, producteur.
SOURCES_SUIVIES = [
    # motif du fichier, nom du jeu, producteur, motif des noms de source (journal et indicateurs), à quoi sert le jeu
    (r"^rpps_", "Répertoire RPPS des professionnels de santé", "Agence du numérique en santé", r"^RPPS",
     "Effectifs et densités de toutes les professions, lieux et modes d'exercice, secteurs d'activité."),
    (r"^finess_", "FINESS, établissements sanitaires et sociaux", "Ministère chargé de la santé", r"^FINESS",
     "Catégorie des établissements où exercent les salariés, périmètre élargi de la santé mentale."),
    (r"^insee_dossier_complet", "Dossier complet, recensement et revenus", "INSEE", r"^INSEE,? dossier",
     "Profil des territoires (âge, revenus, pauvreté, emploi, diplômes, logement), effectif attendu."),
    (r"^insee_estimations", "Estimations annuelles de population", "INSEE", r"^INSEE, estimations",
     "Populations annuelles depuis 2016, dénominateur des densités dans l'évolution de l'offre."),
    (r"^acces_route/", "Temps de trajet par la route vers les équipements", "INSEE", r"^INSEE, temps",
     "Temps de trajet en voiture vers le professionnel ou la structure le plus proche."),
    (r"^ref_", "Découpage administratif (communes, intercommunalités, départements, régions)", "Etalab",
     r"^Référentiel", "Rattachement des communes aux territoires, populations légales, dénominateur des densités."),
    (r"^contours_communes", "Contours des communes, ADMIN EXPRESS", "IGN", r"^Contours",
     "Fonds de carte de l'atlas et des rapports, distances entre communes."),
    (r"^apl_", "Accessibilité potentielle localisée (APL)", "DREES", r"^DREES, (accessibilité|APL)",
     "Comparaison avec l'accessibilité calculée ici."),
    (r"^drees_demographie/", "Démographie des professionnels de santé", "DREES", r"^DREES, démographie",
     "Concordance des effectifs et évolution de l'offre depuis 2016."),
    (r"^drees_isd_", "Indicateurs sociaux départementaux", "DREES",
     r"^DREES, (protection|personnes en situation|indicateurs sociaux)",
     "Protection de l'enfance et handicap, par département."),
    (r"^sae/", "Statistique annuelle des établissements de santé, psychiatrie", "DREES", r"^DREES, (SAE|Statistique annuelle)",
     "Psychiatrie à l'hôpital, lits, places, CMP, temps plein et file active, par département."),
    (r"^ameli_pathologies", "Cartographie des pathologies", "Assurance Maladie", r"^Assurance Maladie, (pathologies|cartographie)",
     "Personnes prises en charge pour troubles psychiques et traitements psychotropes, par département."),
    (r"^ameli_secteurs", "Démographie des libéraux par secteur conventionnel", "Assurance Maladie",
     r"^Assurance Maladie, (secteurs|effectifs de libéraux)", "Part des libéraux pouvant pratiquer des dépassements d'honoraires."),
    (r"^ameli_ald_sans", "Patients en affection longue durée sans médecin traitant", "Assurance Maladie",
     r"^Assurance Maladie, (affection longue durée sans|patients en affection)",
     "Part des patients en affection longue durée sans médecin traitant, par département."),
    (r"^ald_departements", "Affections de longue durée par département", "Assurance Maladie",
     r"^Assurance Maladie, affections de longue", "Personnes en affection de longue durée, 30 affections, par département."),
    (r"^odisse_", "Indicateurs de santé mentale, portail Odissé", "Santé publique France", r"^Santé publique France",
     "Suicides, gestes auto-infligés, indicateurs du Baromètre de Santé publique France."),
    (r"^caf_", "Allocataires de l'AAH, de l'AEEH et du RSA", "CAF", r"^CAF",
     "Allocations liées au handicap et au revenu de solidarité active, par intercommunalité et département."),
]
# Professions dont l'effectif national figure dans le journal quand il change
JOURNAL_PROFESSIONS = ["psychologue", "psychiatre", "pedopsychiatre", "medecin_generaliste", "infirmier",
                       "masseur_kinesitherapeute", "orthophoniste", "psychomotricien", "sage_femme", "pediatre"]
# Ligne de message de commit reprise dans le journal comme évolution du site (« Journal: texte pour le lecteur »)
JOURNAL_MOTIF_COMMIT = r"^Journal\s*:\s*(.+)$"
