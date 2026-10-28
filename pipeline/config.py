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
               "drees_demographie": 30, "ald": 30, "caf": 30, "insee_estimations": 90, "ror": 7}

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
# Territoires d'un seul tenant pour les distances au plus proche (structure ou professionnel). Une commune ne cherche
# que sur son territoire, l'Hexagone, la Corse ou chaque département d'outre-mer, jamais par-dessus la mer (Mayotte
# vers La Réunion jusqu'à 1 450 km, Guyane vers les Antilles, outre-mer vers l'Hexagone jusqu'à 9 000 km, note
# docs/note_valeurs_aberrantes_2026-10-28.md, 28 octobre 2026). Les îles proches des côtes restent avec leur
# territoire (Belle-Île, Marie-Galante). Sans structure de ce type sur le territoire, la distance reste vide. La Corse
# à part, confirmé par Lucas le 28 octobre 2026.
ZONES_TERRESTRES = {"2A": "corse", "2B": "corse", "971": "971", "972": "972", "973": "973", "974": "974",
                    "976": "976"}
# Carte bivariée offre et besoin (audit 4.2), palette bleu et rouge de Joshua Stevens (depuis le 23 octobre 2026, avec
# la palette encre bleue et cuivre du site), 3 tiers de l'offre (bleu) sur 3 tiers de l'indicateur (rouge). Indice
# offre x 3 + indicateur, du plus bas au plus haut.
BIVARIEE = ["#e8e8e8", "#e4acac", "#c85a5a", "#b0d5df", "#ad9ea5", "#985356", "#64acbe", "#627f8c", "#574249"]

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
    # addictions (jeux Odissé vérifiés par l'API le 22 octobre 2026, Licence Ouverte 2.0, régions seulement, note
    # docs/note_statistiques_addictologie_2026-10-22.md, accord de Lucas du 22 octobre 2026)
    {"dataset": "alcool-indicateurs-du-barometre-de-sante-publique-france-2024-detail-region",
     "niveau": "reg", "code": "nouvelles_regions",
     "where": ('indicateur="Dépassement des repères de consommation d\'alcool" and sexe="Tous" and classe_d_age="Tous" '
               'and diplome="Tous" and pcs="Tous" and situation_financiere_percue="Tous" '
               'and depassement_des_reperes_de_consommation_d_alcool="Tous"'),
     "valeur": "estimation", "ic_bas": "ic_inf", "ic_haut": "ic_sup", "groupe": "Addictions",
     "id": "alcool_depassement_reperes", "libelle": "Adultes qui dépassent les repères de consommation d'alcool",
     "phrase": "de {min} à {max} % des adultes dépassent les repères de consommation d'alcool ({annee})",
     "unite": "% des adultes", "source": ODISSE_SOURCE + ", Baromètre de Santé publique France",
     "explication": "Part des adultes de 18 à 79 ans qui déclarent boire plus que les repères de consommation à "
                    "moindre risque (au plus dix verres par semaine, deux par jour, et pas tous les jours). Mesure "
                    "déclarée, disponible seulement par région."},
    {"dataset": "tabac-consommation-quotidienne_reg", "niveau": "reg", "code": "reg",
     "where": 'sexe="Hommes et Femmes"', "valeur": "tab_quo_v", "ic_bas": "tab_quo_icb", "ic_haut": "tab_quo_ich",
     "groupe": "Addictions", "id": "tabac_quotidien", "libelle": "Adultes qui fument chaque jour",
     "phrase": "de {min} à {max} % des adultes fument chaque jour ({annee})",
     "unite": "% des adultes", "source": ODISSE_SOURCE + ", Baromètre de Santé publique France",
     "explication": "Part des adultes de 18 à 75 ans qui déclarent fumer tous les jours. Mesure déclarée, disponible "
                    "seulement par région."},
    {"dataset": "tabac-deces-attribuables-au-tabac_reg", "niveau": "reg", "code": "reg",
     "where": 'sexe="Hommes et Femmes"', "valeur": "taux_std", "ic_bas": "taux_std_inf", "ic_haut": "taux_std_sup",
     "groupe": "Addictions", "id": "deces_attribuables_tabac", "libelle": "Décès attribuables au tabac",
     "phrase": "et l'on estime de {min} à {max} décès dus au tabac pour 100 000 habitants, à structure d'âge égale ({annee})",
     "unite": "pour 100 000 hab., standardisé sur l'âge", "source": ODISSE_SOURCE + ", d'après le CépiDc (Inserm)",
     "explication": "Nombre estimé de décès dus au tabac, rapporté à la population à structure d'âge égale. C'est une "
                    "estimation, tirée de la mortalité par cause et de la part de fumeurs, avec sa fourchette. "
                    "Disponible seulement par région."},
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
# contrôle du temps vers la psychiatrie ambulatoire face à notre distance au CMP (lieux.controle_route_cmp)
ROUTE_CMP_MINUTES, ROUTE_CMP_KM = 30, 8
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
    # version 2, spécialités ajoutées le 11 octobre 2026, regroupements publiés par la DREES dans le même classeur
    # (colonnes « spécialités » et « spécialités agrégées », lues le 11 octobre 2026)
    (r"^medecins rpps", r"agr:autres specialites", "all", ["ens_medecin_specialiste"],
     "Médecins spécialistes, hors généralistes", _RPPS),
    (r"^medecins rpps", r"anesthesie", "all", ["anesthesiste", "reanimateur"],
     "Anesthésistes-réanimateurs et médecins réanimateurs", _RPPS + ", la DREES range la médecine intensive-réanimation avec l'anesthésie"),
    (r"^medecins rpps", r"oto rhino", "all", ["orl"], "Oto-rhino-laryngologistes", _RPPS),
    (r"^medecins rpps", r"gastro", "all", ["gastro_enterologue"], "Gastro-entérologues", _RPPS),
    (r"^medecins rpps", r"pneumolog", "all", ["pneumologue"], "Pneumologues", _RPPS),
    (r"^medecins rpps", r"^chirurgie$", "all",
     ["chirurgien_orthopediste", "chirurgien_general", "urologue", "chirurgien_visceral", "chirurgien_plasticien",
      "chirurgien_maxillo_facial", "chirurgien_vasculaire", "neurochirurgien", "chirurgien_thoracique",
      "chirurgien_pediatrique"], "Chirurgiens (hors ORL, ophtalmologie et gynécologie)",
     _RPPS + ", regroupement « chirurgie » de la DREES, dont la composition exacte peut différer un peu"),
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
# HAS, certification des établissements de santé, sites rattachés à chaque démarche (jeux data.gouv vérifiés par
# l'API le 13 octobre 2026), slug, motif du titre du fichier des sites, motif du fichier des démarches, clé locale
HAS_CERTIFICATION = [
    ("certification-des-etablissements-de-sante-pour-la-qualite-des-soins-referentiel-deploye-2021-2025",
     r"etablissement-geo", r"demarche", "has_2021_2025"),
    ("certification-des-etablissements-de-sante-pour-la-qualite-des-soins-6eme-cycle",
     r"etablissement_geo", r"demarche", "has_6e_cycle"),
]
HAS_PAGE = ("https://www.data.gouv.fr/datasets/certification-des-etablissements-de-sante-pour-la-qualite-des-soins-"
            "referentiel-deploye-2021-2025")
# INSEE, base Sirene des entreprises et de leurs établissements (jeu data.gouv vérifié par l'API le 13 octobre 2026)
SIRENE_JEU = "base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret"
SIRENE_PAGE = "https://www.data.gouv.fr/datasets/" + SIRENE_JEU
SIRENE_TYPES_VOIE = {"AV": "avenue", "BD": "boulevard", "PL": "place", "CHE": "chemin", "RTE": "route", "ALL": "allée",
                     "IMP": "impasse", "QUA": "quai", "CRS": "cours", "R": "rue", "SQ": "square", "PROM": "promenade",
                     "LD": "lieu-dit", "RES": "résidence", "CITE": "cité", "FG": "faubourg", "PASS": "passage"}
# Types de structures confirmés par des listes indépendantes de FINESS et du ROR (pipeline/confirmation.py), avec le
# motif du nom qui désigne le type, cherché dans l'enseigne Sirene et dans le nom des sites de certification HAS. CMP
# d'abord (13 octobre 2026), puis CATTP, hôpitaux de jour, CMPP, CAMSP et addictologie (accord de Lucas du
# 16 octobre 2026). Un hôpital de jour d'une autre discipline ne confirme pas un hôpital de jour en psychiatrie.
_HDJ_AUTRE = (r"GERIAT|G[EÉ]RONTO|P[EÉ]DIATR|ONCOLOG|CANCER|DIAB[EÈ]T|N[EÉ]PHRO|CHIRUR|M[EÉ]DECINE|R[EÉ][EÉ]DUC|"
              r"R[EÉ]ADAPT|\bSSR\b|\bSMR\b|ALLERG|DIALY|DOULEUR|ADDICT|NUTRI|RHUMAT|DERMAT|H[EÉ]MATO|CARDIO|NEURO|"
              r"PNEUMO|GASTRO|ENDOCRIN|INFECTI|MATERNIT|OBST[EÉ]T|AMBULATOIRE")
_HDJ = r"^(?!.*(?:" + _HDJ_AUTRE + r")).*(?:H[OÔ]PITAL DE JOUR|\bH\.?\s?D\.?\s?J\b)"
SIRENE_ENSEIGNES = {
    "lieu_cmp": r"\bC\s?\.?\s?M\s?\.?\s?P\b(?!\s?\.?\s?P)|M[EÉ]DICO.?PSYCHOLOG|\bCMPEA\b|\bCMPI\b|\bCMPPA\b",
    "lieu_cattp": r"\bC\.?\s?A\.?\s?T\.?\s?T\.?\s?P\b|ACCUEIL TH[EÉ]RAPEUTIQUE",
    "lieu_hdj_psy_adultes": _HDJ,
    "lieu_hdj_psy_enfants": _HDJ,
    "lieu_cmpp": r"\bC\.?\s?M\.?\s?P\.?\s?P\b(?!\s?\.?\s?A)|PSYCHO.?P[EÉ]DAGOG",
    "lieu_camsp": r"\bC\.?\s?A\.?\s?M\.?\s?S\.?\s?P\b|ACTION M[EÉ]DICO.?SOCIALE PR[EÉ]COCE",
    "lieu_csapa": r"\bC\.?\s?S\.?\s?A\.?\s?P\.?\s?A\b|\bC\.?\s?J\.?\s?C\b|JEUNES CONSOMMATEURS",
    "lieu_caarud": r"\bC\.?\s?A\.?\s?A\.?\s?R\.?\s?U\.?\s?D\b|R[EÉ]DUCTION DES RISQUES",
}
# Nom d'un établissement Sirene ou d'un site HAS qui désigne un public d'enfants ou d'adolescents
NOM_PUBLIC_ENFANTS = r"ENFAN|INFANT|\bADO|P[EÉ]DO|JEUN|JUV[EÉ]N|\bIJ\b|PETITE ENFANCE"
NOM_PUBLIC_ADULTES = r"ADULT"
# HAS, résultats d'évaluation des établissements et services sociaux et médico-sociaux (jeu data.gouv vérifié par
# l'API le 16 octobre 2026, Licence Ouverte 2.0, mis à jour en continu), fichier de l'échelle de qualité (parquet)
HAS_ESSMS_JEU = "resultats-devaluation-des-etablissements-et-services-sociaux-et-medico-sociaux-essms"
HAS_ESSMS_MOTIF = "open_data_echelle_qualite"
HAS_ESSMS_PAGE = "https://www.data.gouv.fr/datasets/" + HAS_ESSMS_JEU

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
    (r"^HAS, certification", "Haute Autorité de santé (HAS)", "Licence Ouverte 2.0", HAS_PAGE),
    (r"^HAS, évaluation", "Haute Autorité de santé (HAS)", "Licence Ouverte 2.0", HAS_ESSMS_PAGE),
    (r"^INSEE, répertoire Sirene", "Institut national de la statistique et des études économiques (INSEE)",
     "Licence Ouverte 2.0", SIRENE_PAGE),
    (r"^ANS, offres de santé", "Agence du numérique en santé (ANS), Répertoire opérationnel des ressources",
     "Licence Ouverte 2.0", "https://www.data.gouv.fr/datasets/offres-de-sante-sanitaire-medico-social-et-de-ville-en-"
     "france-metropolitaine-et-drom-1"),
    (r"^IGN, géocodage", "IGN, service de géocodage de la Géoplateforme (Base Adresse Nationale)", "Licence Ouverte 2.0",
     "https://geoservices.ign.fr/documentation/services/services-geoplateforme/geocodage"),
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
# Chaque médecin reçoit une seule spécialité, celle de son inscription à l'Ordre. Groupes des spécialités (version 2,
# validés par Lucas le 11 octobre 2026), d'après le partage des diplômes d'études spécialisées entre spécialités
# médicales, chirurgicales et médico-techniques, plus la prévention et la santé publique, qui ne sont pas des soins
# à la population.
G_MED, G_CHIR, G_TECH, G_PREV = ("Spécialités médicales", "Spécialités chirurgicales", "Spécialités médico-techniques",
                                 "Prévention et santé publique")
GROUPES_SPECIALITES = [G_MED, G_CHIR, G_TECH, G_PREV]
SPECIALITES_MEDECINS = [
    (r"psychiatr.*(enfant|adolescent)|pedopsychiatr", "pedopsychiatre", "Pédopsychiatre", "Psychiatrie", SANTE_MENTALE),
    (r"psychiatr", "psychiatre", "Psychiatre", "Psychiatrie", SANTE_MENTALE),
    (r"medecine generale", "medecin_generaliste", "Médecin généraliste", "Premier recours", SANTE),
    # « pédiatrie » seulement, pas la chirurgie pédiatrique ni la réanimation pédiatrique (vérifié le 5 octobre 2026)
    (r"\bpediatrie\b", "pediatre", "Pédiatre", G_MED, SANTE),
    (r"neurolog", "neurologue", "Neurologue", G_MED, SANTE),
    (r"geriatr", "geriatre", "Gériatre", G_MED, SANTE),
    # « gyneco » couvre aussi le DES de 2017 « Gynéco-obstétrique et Gynéco médicale option... »
    (r"gyneco", "gynecologue", "Gynécologue", G_CHIR, SANTE),
    (r"ophtalmolog", "ophtalmologue", "Ophtalmologue", G_CHIR, SANTE),
    # « Méd cardiovasculaire opt... » est le DES de cardiologie depuis 2017, la chirurgie cardio-vasculaire est exclue
    (r"cardiolog|\bmed\w* cardiovasculaire", "cardiologue", "Cardiologue", G_MED, SANTE),
    (r"dermatolog", "dermatologue", "Dermatologue", G_MED, SANTE),
    # Spécialités ajoutées le 11 octobre 2026 (version 2), placées après les précédentes pour que les médecins déjà
    # classés le restent. Libellés anciens et diplômes de la réforme de 2017 réunis (inventaire du fichier
    # savoir-faire du RPPS du 10 octobre 2026). L'ordre compte, la radiothérapie avant la radiologie et l'oncologie,
    # l'anesthésie avant la réanimation, la chirurgie pédiatrique avant l'orthopédie.
    (r"radiotherap|radio therap", "radiotherapeute", "Radiothérapeute", G_TECH, SANTE),
    (r"anesthes", "anesthesiste", "Anesthésiste-réanimateur", G_TECH, SANTE),
    (r"^oncologie", "oncologue", "Oncologue médical", G_MED, SANTE),
    (r"hematolog", "hematologue", "Hématologue", G_MED, SANTE),
    (r"chirurgie infantile|chirurgie pediatrique", "chirurgien_pediatrique", "Chirurgien pédiatrique", G_CHIR, SANTE),
    (r"gastro entero", "gastro_enterologue", "Gastro-entérologue", G_MED, SANTE),
    (r"pneumolog", "pneumologue", "Pneumologue", G_MED, SANTE),
    (r"medecine interne", "interniste", "Médecin interniste", G_MED, SANTE),
    (r"medecine d urgence", "urgentiste", "Médecin urgentiste", G_MED, SANTE),
    (r"medecine physique|readaptation", "medecin_mpr", "Médecin de médecine physique et de réadaptation", G_MED, SANTE),
    (r"rhumatolog", "rhumatologue", "Rhumatologue", G_MED, SANTE),
    (r"endocrinolog|diabetolog", "endocrinologue", "Endocrinologue", G_MED, SANTE),
    (r"nephrolog", "nephrologue", "Néphrologue", G_MED, SANTE),
    (r"medecine vasculaire", "medecin_vasculaire", "Médecin vasculaire", G_MED, SANTE),
    (r"medecine intensive|reanimation", "reanimateur", "Médecin réanimateur", G_MED, SANTE),
    (r"maladies infectieuses", "infectiologue", "Infectiologue", G_MED, SANTE),
    (r"allergolog", "allergologue", "Allergologue", G_MED, SANTE),
    (r"orthoped", "chirurgien_orthopediste", "Chirurgien orthopédiste", G_CHIR, SANTE),
    (r"\bo r l\b|\borl\b|oto rhino", "orl", "Oto-rhino-laryngologiste (ORL)", G_CHIR, SANTE),
    (r"urolog", "urologue", "Urologue", G_CHIR, SANTE),
    (r"viscerale", "chirurgien_visceral", "Chirurgien viscéral et digestif", G_CHIR, SANTE),
    (r"plastique", "chirurgien_plasticien", "Chirurgien plasticien", G_CHIR, SANTE),
    (r"maxillo|stomatolog|chirurgie orale", "chirurgien_maxillo_facial", "Chirurgien maxillo-facial et stomatologue",
     G_CHIR, SANTE),
    (r"chirurgie vasculaire", "chirurgien_vasculaire", "Chirurgien vasculaire", G_CHIR, SANTE),
    (r"neuro ?chirurg", "neurochirurgien", "Neurochirurgien", G_CHIR, SANTE),
    (r"thoracique", "chirurgien_thoracique", "Chirurgien thoracique et cardiovasculaire", G_CHIR, SANTE),
    (r"chirurgie generale", "chirurgien_general", "Chirurgien général", G_CHIR, SANTE),
    (r"radiolog|radio diagnostic|imagerie medicale", "radiologue", "Radiologue", G_TECH, SANTE),
    (r"biologie medicale", "biologiste", "Biologiste médical", G_TECH, SANTE),
    (r"anatomie", "anatomopathologiste", "Anatomopathologiste", G_TECH, SANTE),
    (r"medecine nucleaire", "medecin_nucleaire", "Médecin nucléaire", G_TECH, SANTE),
    (r"medecine du travail", "medecin_travail", "Médecin du travail", G_PREV, SANTE),
    (r"sante publique", "medecin_sante_publique", "Médecin de santé publique", G_PREV, SANTE),
]
# spécialités ajoutées en version 2, regroupées sous « autre spécialité » dans le périmètre élargi de la santé
# mentale, où elles sont trop peu nombreuses une à une (build.perimetre_elargi)
SPECIALITES_AJOUTEES = [e[1] for e in SPECIALITES_MEDECINS[[e[1] for e in SPECIALITES_MEDECINS].index("dermatologue") + 1:]]
MEDECIN_AUTRE = ("medecin_autre", "Médecin, autre spécialité", "Autres médecins", SANTE)
MEDECIN_INCONNU = ("medecin_non_precise", "Médecin, spécialité non renseignée", "Autres médecins", SANTE)
# Repère « médecins spécialistes, ensemble » (version 2, 11 octobre 2026), chaque médecin spécialiste compté une fois
# quelle que soit sa spécialité, hors généralistes, comme dans les séries de la DREES. Il réunit les spécialités et ne
# s'y ajoute pas (nature « ensemble », préfixe écarté des sommes comme les qualifications).
PREFIXE_ENSEMBLE = "ens_"
ENSEMBLE_SPECIALISTES = ("ens_medecin_specialiste", "Médecin spécialiste (toutes spécialités)", "Médecins spécialistes, ensemble",
                         SANTE, "ensemble")
# Précision « exercice surtout salarié », écrite pour toute spécialité dont moins d'un tiers des médecins exercent en
# libéral (calculée à chaque exécution, build.limites_specialites), validée par Lucas le 11 octobre 2026
SEUIL_LIBERAL_SPECIALITE = 1 / 3
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
    "chirurgien_dentiste", "sage_femme", "pediatre", "ens_medecin_specialiste",
]

# Public concerné par une profession, pour la densité rapportée à ce public (indicateurs de part de
# config.CONTEXTE additionnés). Le recensement publie les moins de 15 ans, pas les moins de 18 ans.
PUBLICS_CIBLES = {
    "pedopsychiatre": (["part_0_14"], "moins de 15 ans"),
    "q_psychiatrie_enfant": (["part_0_14"], "moins de 15 ans"),
    "pediatre": (["part_0_14"], "moins de 15 ans"),
    # orthophonistes et psychomotriciens retirés le 12 octobre 2026 (remarque de Lucas), ils soignent tous les âges
    # (LIMITES["prof:orthophoniste"] et ["prof:psychomotricien"])
    "geriatre": (["part_65_79", "part_80p"], "65 ans et plus"),
}

# Professions croisées avec les indicateurs de besoin en santé mentale (quadrants offre et besoin)
PROFESSIONS_QUADRANTS = ["psychiatre", "psychologue", "q_psychiatrie_enfant", "medecin_generaliste"]
# régression géographiquement pondérée du lien avec le niveau de vie : professions présentes dans au moins une
# intercommunalité sur deux (décision de Lucas du 23 octobre 2026, au-delà des trois professions d'origine)
GWR_PRESENCE_MIN = 0.5
# part de l'exercice libéral par territoire, indicateur de « Croiser deux indicateurs » (demande de Lucas du 23 octobre
# 2026). Calculée seulement quand le territoire compte au moins PART_LIBERAL_EFFECTIF_MIN professionnels de la
# profession (en dessous, une ou deux personnes font passer la part de 0 à 100 %), pour les professions principales où
# libéraux et salariés pèsent tous deux en France et qui atteignent ce minimum dans au moins un département sur deux
PART_LIBERAL_EFFECTIF_MIN = 10
PART_LIBERAL_BORNES = (0.10, 0.90)
PART_LIBERAL_PRESENCE_MIN = 0.5

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
#   a_distance            soins à distance pour une société de téléconsultation, déclarés à l'adresse de son siège,
#                         donc impossibles à rattacher au territoire des patients. Ce sont bien des soins (remarque
#                         de Lucas du 12 octobre 2026), retirés des densités et comptés à part.
#   sans_soins            activités sans soins à la population, souvent déclarées au siège d'un organisme, retirées
#                         des densités et comptées à part, territoire par territoire. Les personnes restent dans
#                         l'effectif national.
SECTEUR_TELECONSULTATION = r"teleconsultation"
MEDECINS = ({x[1] for x in SPECIALITES_MEDECINS} | {MEDECIN_AUTRE[0], MEDECIN_INCONNU[0]}
            | {x[1] for x in QUALIFICATIONS_MEDECINS})
SECTEURS_CATEGORIES = [
    (SECTEUR_TELECONSULTATION, None, "a_distance"),
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
                       "a_distance": "Soins à distance (téléconsultation)",
                       "sans_soins": "Sans soins à la population"}
# catégories retirées des densités, comptées à part dans chaque territoire où elles sont déclarées
CATEGORIES_HORS_DENSITES = ("a_distance", "sans_soins")

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
SRC_ROR = ("Agence du numérique en santé, offres de santé du Répertoire opérationnel des ressources (data.gouv)",
           "https://www.data.gouv.fr/datasets/offres-de-sante-sanitaire-medico-social-et-de-ville-en-france-metropolitaine-et-drom-1")
SRC_ARS_MARTINIQUE = ("ARS Martinique, offre de soins en psychiatrie (document de 2018)",
                      "https://www.martinique.ars.sante.fr/media/9531/download")
SRC_RPPS = ("Annuaire santé, extractions en libre accès du RPPS (data.gouv)",
            "https://www.data.gouv.fr/datasets/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps")
FINESS_CMP = "156"   # catégorie FINESS des centres médico-psychologiques

# ---------------------------------------------------------------- lieux de soins, ROR et FINESS réunis
# Extraction « Offres de santé » du Répertoire opérationnel des ressources (ROR), Agence du numérique en santé, un zip
# par région, mis à jour chaque semaine, Licence Ouverte (vérifié le 12 octobre 2026 sur l'API de data.gouv).
ROR_JEU = "offres-de-sante-sanitaire-medico-social-et-de-ville-en-france-metropolitaine-et-drom-1"
ROR_PAGE = "https://www.data.gouv.fr/datasets/" + ROR_JEU
# identifiants des structures dans le fichier IHE CSD (numéro FINESS, catégorie d'établissement FINESS)
ROR_OID_FINESS = "1.2.250.1.213.3.2"
ROR_OID_IDNST = "1.2.250.1.71.4.2.2"   # identifiant national de structure, 1 suivi du numéro FINESS
ROR_OID_CATEGORIE_FINESS = "1.2.250.1.213.1.6.1.8"
# Nomenclatures de l'ANS (NOS) dont les codes sont repris ici, vérifiées le 12 octobre 2026 sur mos.esante.gouv.fr,
# catégorie d'organisation (TRE_R244), champ d'activité (TRE_R227), mode de prise en charge (TRE_R213)
ROR_NOMENCLATURE = "https://mos.esante.gouv.fr/NOS/TRE_R244-CategorieOrganisation/"
ROR_CHAMP_VILLE = "05"   # consultations de ville, déclarées seulement en Île-de-France, écartées
# Géocodage des adresses sans coordonnées dans FINESS, service de l'IGN sur la Géoplateforme qui remplace l'API Adresse
# de data.gouv depuis janvier 2026 (vérifié le 12 octobre 2026), Base Adresse Nationale, Licence Ouverte
GEOCODAGE_CSV = "https://data.geopf.fr/geocodage/search/csv"
GEOCODAGE_PAGE = "https://geoservices.ign.fr/documentation/services/services-geoplateforme/geocodage"
GEOCODAGE_SCORE_MIN = 0.5
# modes de prise en charge (TRE_R213) regroupés
MODES_CONSULTATION = {"02", "20", "32", "54", "57"}
MODES_MOBILE = {"10", "11", "43", "44", "45", "52", "53", "59"}
MODES_HC = {"28", "34"}
MODES_TEMPS_PARTIEL = {"29", "30", "42", "47"}
CHAMP_PSY = "03"
# Une unité est réservée aux enfants et aux adolescents quand l'âge maximal de ses patients ne dépasse pas cette
# limite (des CMP pour enfants et adolescents déclarent 21 ans, constat du 12 octobre 2026 dans le Haut-Rhin), ou
# quand son nom le dit
AGE_MAX_ENFANTS = 21
NOM_ENFANTS = r"enfant|adolescen|\bados?\b|pedo|infanto|juvenil|bebe|perinat|petite enfance|cmpea|cmpi\b"
# Mots qui ne désignent jamais une commune quand on cherche la commune d'une unité dans son nom (beaucoup d'unités de
# psychiatrie du ROR n'ont pas de commune propre, constat du 12 octobre 2026)
MOTS_NON_COMMUNES = {"centre", "pavillon", "secteur", "adulte", "adultes", "enfant", "enfants", "psy", "maison",
                     "hopital", "clinique", "consultation", "consultations", "cmp", "cattp", "cattg", "unite", "pole",
                     "service", "soins", "accueil", "jour", "nuit", "equipe", "mobile", "site", "antenne",
                     "intersecteur", "ado", "ados", "age", "avance", "sud", "nord", "est", "ouest", "ville", "val",
                     "plaine", "bourg", "village",
                     # prénom dans un nom d'unité (CMP Marie-Béatrice de Menton, pas la commune de Marie)
                     "marie"}
# Nom de l'établissement gestionnaire cité à la fin du nom d'une unité (« CMP ADULTES CARVIN CH HENIN BEAUMONT »,
# « CMP 59G30 CONDE/ESCAU CH VALENCIENNES », « CMP CATTP LE CHEMIN VERT IDAC CAMIERS »). Ce qui suit ces mots est
# retiré avant de chercher la commune de l'unité dans son nom, sinon la commune de l'hôpital l'emportait (constat du
# 15 octobre 2026, une quarantaine de CMP placés dans la commune de leur hôpital)
NOM_ETABLISSEMENT_GESTIONNAIRE = r"\b(?:ch|chs|chu|chi|chr|chg|chic|chru|epsm|epsmd|eps|idac|ghu|aphp|ap hp|centre hospitalier)\b.*$"
# Unités de la catégorie CMP qui sont en réalité des équipes mobiles, de la liaison ou d'autres activités, écartées du
# comptage des CMP (constat du 12 octobre 2026 en Martinique, voir docs/plan_lieux_de_soins_2026-10-12.md)
# « cmpp » seul, pas « cmppa » (CMP pour personnes âgées de l'Ain, écarté à tort jusqu'au 12 octobre 2026), et les
# consultations spécialisées que des hôpitaux déclarent comme CMP (stimulation magnétique, électroconvulsivothérapie)
LIEUX_EXCLUS_CMP = (r"equipe|liaison|sociotherap|mobile|intervention|pedagogique|\bcmpp\b|\btms\b|stimulation magnetique|"
                    r"sismotherap|electro.?convuls|psycho.?legal|psychiatrie legale|\beapl\b|\breseau\b|"
                    # addictologie, milieu pénitentiaire et soins pénalement ordonnés déclarés comme CMP (Charente,
                    # 12 octobre 2026), ils ont leurs propres types
                    r"\bcsapa\b|maison d.?arret|detention|peniten[ct]|\busmp\b|\bsmpr\b|medico.?psychologique regional|judiciaire|"
                    # urgences psychiatriques et cellule d'urgence médico-psychologique déclarées comme CMP (Moselle,
                    # Doubs, 13 octobre 2026)
                    r"^urgences psychiatriques|cellule d.?urgence|"
                    # unités spécialisées rangées parmi les CMP par le ROR, qui ont leur propre type ou ne sont pas des
                    # CMP (revue de tous les noms qui ne disent pas CMP, 13 octobre 2026)
                    r"tabacolog|\bucsa\b|\buhcd\b|carceral|recidive|\bemopsi\b|appartements? de transition|"
                    r"ssr delocalise|autis[mt]|\bted\b|\bcrtla\b|troubles des apprentissages|"
                    # sauf quand le nom dit aussi CMP (« HJ CMP CATTP », « CMP addictologie », « CMP MDA »)
                    r"^(?!.*(?:\bcmp|\bc m p\b|medico psycho)).*(?:maisons? des ado|\bmda\b|addictolog|alcoolog|"
                    r"\bhj\b|hopital de jour|surdite|clinique (?:de psy|medicale)|psychotraumato|"
                    # équipes et dispositifs qui ne sont pas des CMP (revue des noms restant à vérifier, 14 octobre 2026)
                    r"\bempp\b|perinatal|rehabilitation|therapie familiale|accueil familial|\bsaft\b|"
                    r"groupes au long cours|enfants victimes|psy\w* legal|"
                    # groupes pour les proches, thérapie familiale, diagnostic et orientation (15 octobre 2026)
                    r"psycho ?education|entretiens familiaux|troubles globaux du developpement|"
                    r"accueil d.?evaluation et d.?orientation|"
                    # unités d'hospitalisation et CATTP rangés parmi les CMP (revue du 15 octobre 2026)
                    r"hospitalisation|\bcattp\b)|"
                    # consultations qui ne sont pas celles d'un secteur (voir LIEUX_CONSULT_HORS_CMP)
                    r"non sectoris|transculturel|consultation de psych\w* maternite|avis specialise|"
                    r"consultation regionale|consultation psychologie clinique|"
                    r"pathologie du travail|souffrance au travail|cons ext specialisees|^ce psychiatrie$|relais etudiants|"
                    # unités nommées seulement « Consultation(s) de psychiatrie » (voir CONSULT_GENERIQUE)
                    r"^(?:psychiatrie )?consult\w*(?: (?:de|des|en|psy\w*|pedo ?psy\w*|geronto ?psy\w*|adultes?|"
                    r"generale?s?|ambulatoires?|externes?|medicales?|et|plus|60|ans|psychologie))*$")
# Unités du ROR nommées seulement « Consultation(s) », « Consultations psychiatrie adultes », « Psychiatrie
# consultations », sans CMP ni numéro de secteur. Ce sont les consultations d'un hôpital ou d'une clinique privée (Garches,
# Meudon, Ville-d'Avray, Crosne, Saint-Mandé, Osny, Meaux, Nantes...), pas un CMP de secteur (revue des CMP restant à
# vérifier, 14 octobre 2026). Le CMP d'un hôpital à la même adresse, s'il existe, est inscrit sous son propre nom.
CONSULT_GENERIQUE = (r"^(?:psychiatrie )?consult\w*(?: (?:de|des|en|psy\w*|pedo ?psy\w*|geronto ?psy\w*|adultes?|"
                     r"generale?s?|ambulatoires?|externes?|medicales?|et|plus|60|ans|psychologie))*$")
# Consultations de psychiatrie que le ROR range parmi les CMP mais qui n'en sont pas (un CMP est la consultation d'un
# secteur), comptées parmi les consultations hors CMP (AP-HP, Nancy, Caen, Besançon, revue du 14 octobre 2026)
LIEUX_CONSULT_HORS_CMP = (r"non sectoris|transculturel|consultation de psych\w* maternite|avis specialise|"
                          r"consultation regionale|consultation psychologie clinique|"
                          # consultations externes, du travail et des étudiants (revue du 15 octobre 2026)
                          r"pathologie du travail|souffrance au travail|cons ext specialisees|^ce psychiatrie$|"
                          r"relais etudiants|" + CONSULT_GENERIQUE)
# Nom d'un CMP, pour reconnaître les unités de consultation en psychiatrie qui n'ont pas de catégorie dans le ROR
# (constat du 12 octobre 2026 en Guyane, « Centre médico-psychologique adulte » sans catégorie)
NOM_CMP = r"\bcmp\b|\bcmpea\b|\bcmpi\b|\bcmppa\b|medico.?psy?c?h?ologique|centre de sante mentale"
# Établissements enregistrés dans FINESS comme CMP (catégorie 156) dont le nom dit qu'ils sont autre chose, rangés dans
# le type que leur nom désigne, comme les unités du ROR (constat de Lucas du 12 octobre 2026, CMP de l'Ain, vérifié
# sur toute la France). Motif sur le nom sans accents ni majuscules, type visé, dans l'ordre, le premier qui convient.
# Un nom qui cite aussi un CMP (« CMP CATTP de Barriol ») reste un CMP pour les CATTP seulement.
RETYPAGE_CMP_FINESS = [
    (r"\belsa\b|liaison.{0,40}addicto|addicto.{0,40}liaison", "lieu_addicto_hosp"),
    (r"equipe|\beq\b|mobile|liaison|intervention|\bempp\b", "lieu_mobile_psy"),
    (r"urgence|\bcrise\b|\bcap \d", "lieu_crise_psy"),
    (r"post.?traumat|psychotrauma|enfants victimes", "lieu_psychotrauma"),
    (r"autis[mt]|neuro.?developpement|\btnd\b", "lieu_tnd"),
    (r"usmp|smpr|medico.?psychologique regional|\bucsa\b|carceral|detention|maison (?:centrale|d.?arret)|peniten[ct]|psycho.?legal|psychiatrie legale|psy\w* legal|judiciaire",
     "lieu_consult_psy"),
    (r"\bcsapa\b", "lieu_csapa"),
    (r"hop(?:ital)? de jour|\bhj\b|\bhdj\b", "hdj"),
    (r"appart|\bappts?\b|rehab|sociotherap|accueil familial|\bsaft\b", "lieu_rehab_psy"),
    (r"plateforme|precarite|\bpass\b|consultations? (?:memoire|externes|avancees)|non sectoris|transculturel|avis specialise|\bcmpp\b|pedagogique|\btms\b|therap\w* famil|entretiens familiaux|psycho ?education|"
     r"troubles globaux du developpement|groupes au long cours",
     "lieu_consult_psy"),
]
RETYPAGE_CATTP = r"cattp|cattg|accueil therapeutique"
# CATTP qui n'en sont pas pour le compte (décisions de Lucas du 16 octobre 2026). Les ateliers thérapeutiques, que la SAE
# et les chambres régionales des comptes comptent à part des CATTP, vont avec la réhabilitation psychosociale (catégorie
# FINESS 366 ou nom d'atelier, sauf quand le nom dit aussi CATTP). Les CATTP en milieu pénitentiaire sont écartés du
# compte des territoires et rangés comme les CMP en milieu pénitentiaire.
FINESS_ATELIER_THERAPEUTIQUE = "366"
# Types dont les antennes se lisent dans la relation de budget de FINESS (décision de Lucas du 16 octobre 2026, note
# docs/note_sources_cmpp_camsp_2026-10-16.md). Structure principale, antenne (établissement non porteuse d'un
# établissement de même catégorie), site supplémentaire (lieu du ROR seul au numéro d'une autre structure du type).
# « Où ils exercent » dans les structures de santé mentale (demande de Lucas du 21 octobre 2026). Seules les structures
# enregistrées sous leur propre numéro FINESS sont retenues, une déclaration au RPPS y désigne bien la structure, alors
# que les unités hospitalières du ROR partagent le numéro de leur hôpital.
LIEUX_EXERCICE_TYPES = ["lieu_cmp", "lieu_cattp", "lieu_cmpp", "lieu_camsp", "lieu_csapa", "lieu_caarud"]
LIEUX_EXERCICE_PROFESSIONS = ["psychiatre", "pedopsychiatre", "q_psychiatrie_enfant", "psychologue", "infirmier",
                              "psychomotricien", "orthophoniste", "ergotherapeute", "medecin_generaliste"]
LIEUX_ANTENNES_FINESS = ["lieu_cmpp", "lieu_camsp", "lieu_csapa", "lieu_caarud"]
NOM_ATELIER_THERAPEUTIQUE = r"atelier|ergotherap|art ?therap|groupe animation|theatre"
NOM_PENITENTIAIRE = (r"usmp|smpr|medico.?psychologique regional|\bucsa\b|carceral|detention|maison (?:centrale|d.?arret)|"
                     r"peniten[ct]")
# Rôles lus dans le nom pour l'addictologie (décision de Lucas du 16 octobre 2026, note
# docs/note_sources_addictologie_2026-10-16.md), dans cet ordre. Un lieu en milieu pénitentiaire et une équipe de
# liaison (ELSA, sans lieu propre) restent listés et comptés avec leur rôle, mais n'entrent pas dans les distances.
ROLES_ADDICTOLOGIE = {
    "lieu_csapa": [("penitentiaire", NOM_PENITENTIAIRE), ("cjc", r"\bcjc\b|jeunes? consommateurs?"),
                   ("antenne", r"antenne|permanence|consultations? avancees?|annexe|\bsite de\b"),
                   ("hebergement", r"appartement|communaute therap|residentiel|hebergement|post.?cure")],
    "lieu_caarud": [("penitentiaire", NOM_PENITENTIAIRE), ("antenne", r"antenne|permanence|annexe|\bsite de\b")],
    "lieu_addicto_hosp": [("equipe", r"\belsa\b|liaison")],
}
ROLES_SANS_DISTANCE = {"penitentiaire", "equipe"}
# Repère national des CSAPA (OFDT, bilan RECAP 2024, édition 2026, 497 CSAPA dans le champ de l'enquête, adresse vérifiée
# le 16 octobre 2026)
OFDT_CSAPA = (497, "2024", "OFDT, bilan RECAP 2024 (édition 2026)",
              "https://www.ofdt.fr/sites/ofdt/files/2026-08/bilan-recap-2024-ed-2026.pdf")
# Établissements de FINESS dont le nom dit CMP mais enregistrés dans une autre catégorie (centre hospitalier spécialisé,
# centre hospitalier, CHR, CATTP...), environ 490 en France (constat du 13 octobre 2026, « HJ - CMP Loudun » du CH
# Laborit, CMP adultes de l'Allier). Ils sont comptés comme CMP, sauf les services médico-psychologiques régionaux en
# milieu pénitentiaire (415) et les centres de vaccination (645) dont le sigle se ressemble.
FINESS_CMP_PAR_NOM = {"292", "355", "101", "106", "161", "425", "365", "366", "362"}
# Catégories FINESS des hôpitaux (centres hospitaliers régionaux et universitaires, centres hospitaliers, centres
# hospitaliers spécialisés en psychiatrie...), qui servent à reconnaître une unité du ROR déclarée dans la commune d'un
# hôpital de son gestionnaire plutôt qu'à son propre lieu
FINESS_HOPITAUX = {"101", "106", "355", "292", "362", "365", "366"}
# public d'un CMP connu de FINESS seul (sans âges déclarés dans le ROR), déduit de son nom. Codes de secteur de
# psychiatrie, « G » pour la psychiatrie générale (adultes), « I » pour les intersecteurs infanto-juvéniles
NOM_SECTEUR_ENFANTS = r"\b(?:\d{2}|2a|2b)\s?i\s?\d{1,2}\b"
NOM_ADULTES = r"adulte|\b(?:\d{2}|2a|2b)\s?g\s?\d{1,2}\b|geronto|sujet age|personnes agees|psychiatrie generale"
# Aucun nom de personne n'est publié. Une unité du ROR dont le nom en contient un (consultation nominative) est écartée,
# et un contrôle bloquant le vérifie sur les noms tirés du ROR. Les raisons sociales d'établissements de FINESS, qui
# portent parfois le nom d'un fondateur (« EHPAD Docteur ... »), sont autorisées.
NOM_PERSONNE = r"\b(?:dr|docteur|professeur)\b\.?\s"

# Types de lieux. Identifiant, libellé, famille, groupe, règle. Règle, catégories du ROR (TRE_R244, None pour les unités
# sans catégorie), champs d'activité, modes de prise en charge, public (enfants ou adultes), motif d'exclusion sur le
# nom, catégories FINESS réunies au ROR sans double compte (pipeline/lieux.py), type dont la provenance est reprise
# (parent), modes ou type de maternité qui suffisent à eux seuls. Un lieu compte une fois par type, sa clé étant son
# numéro FINESS d'établissement et sa commune.
G_PSY, G_PSY_A, G_PSY_E = "Psychiatrie, tous âges", "Psychiatrie, adultes", "Psychiatrie, enfants et adolescents"
G_ENF, G_ADD, G_URG = "Enfance et développement", "Addictions", "Urgences et soins non programmés"
G_PERI, G_HOP, G_SMR = "Périnatalité et santé sexuelle", "Hôpital, médecine et chirurgie", "Réadaptation et domicile"
G_PA, G_HE, G_HA = "Personnes âgées", "Handicap, enfants", "Handicap, adultes"
G_PREC, G_PREM = "Précarité et prévention", "Premier recours organisé"
_C = MODES_CONSULTATION
LIEUX_TYPES = [
    # santé mentale
    ("lieu_cmp", "CMP, tous publics", SANTE_MENTALE, G_PSY,
     {"cats": {"10", "281"}, "champs": {CHAMP_PSY}, "modes": _C, "hors": LIEUX_EXCLUS_CMP, "finess": {FINESS_CMP},
      "noms_sans_categorie": NOM_CMP}),
    ("lieu_cmp_adultes", "CMP pour adultes", SANTE_MENTALE, G_PSY_A,
     {"cats": {"10"}, "champs": {CHAMP_PSY}, "modes": _C, "public": "adultes", "hors": LIEUX_EXCLUS_CMP,
      "parent": "lieu_cmp", "noms_sans_categorie": NOM_CMP}),
    ("lieu_cmp_enfants", "CMP pour enfants et adolescents", SANTE_MENTALE, G_PSY_E,
     {"cats": {"10", "281"}, "champs": {CHAMP_PSY}, "modes": _C, "public": "enfants", "hors": LIEUX_EXCLUS_CMP,
      "parent": "lieu_cmp", "noms_sans_categorie": NOM_CMP}),
    # consultations de psychiatrie déclarées sans catégorie ou comme unité hospitalière, qui ne se disent pas CMP
    # (consultations de secteur dans un hôpital général, à Thiers, Ambert ou Mayotte par exemple)
    ("lieu_consult_psy", "Consultations de psychiatrie hors CMP", SANTE_MENTALE, G_PSY,
     {"cats": {None, "174", "16", "69", "282"}, "champs": {CHAMP_PSY}, "modes": _C,
      "hors": (r"^(?!.*(?:" + LIEUX_CONSULT_HORS_CMP + r"))(?:.*(?:" + LIEUX_EXCLUS_CMP + "|" + NOM_CMP +
               "|urgence|crise|addicto|csapa|criavs|maison des adolescents))"),
      "noms_categories": ({"10"}, LIEUX_CONSULT_HORS_CMP)}),
    ("lieu_cattp", "CATTP, accueil thérapeutique à temps partiel", SANTE_MENTALE, G_PSY,
     {"cats": {"05", "02"}, "champs": {CHAMP_PSY}, "finess": {"425", "366"}}),
    ("lieu_hdj_psy_adultes", "Hôpitaux de jour en psychiatrie, adultes", SANTE_MENTALE, G_PSY_A,
     {"cats": {"11", "12", "16", "174", None}, "champs": {CHAMP_PSY}, "modes": MODES_TEMPS_PARTIEL, "public": "adultes"}),
    ("lieu_hdj_psy_enfants", "Hôpitaux de jour en psychiatrie, enfants et adolescents", SANTE_MENTALE, G_PSY_E,
     {"cats": {"11", "12", "16", "174", "282", None}, "champs": {CHAMP_PSY}, "modes": MODES_TEMPS_PARTIEL,
      "public": "enfants"}),
    ("lieu_hc_psy_adultes", "Hospitalisation complète en psychiatrie, adultes", SANTE_MENTALE, G_PSY_A,
     {"cats": {"16", "174", "15", "68", "18", "17", "14", None}, "champs": {CHAMP_PSY}, "modes": MODES_HC,
      "public": "adultes"}),
    ("lieu_hc_psy_enfants", "Hospitalisation complète en psychiatrie, enfants et adolescents", SANTE_MENTALE, G_PSY_E,
     {"cats": {"16", "282", "174", "119", None}, "champs": {CHAMP_PSY}, "modes": MODES_HC, "public": "enfants"}),
    ("lieu_crise_psy", "Urgences psychiatriques, centres de crise et d'accueil permanent", SANTE_MENTALE, G_PSY,
     {"cats": {"301", "06", "302", "04", "76", "07"}, "finess": {"444"}}),
    ("lieu_mobile_psy", "Équipes mobiles de psychiatrie", SANTE_MENTALE, G_PSY,
     {"cats": {"280", "77", "78", "144", "279", "283", "300", "70"}}),
    ("lieu_rehab_psy", "Réhabilitation psychosociale, appartements et accueil familial thérapeutiques", SANTE_MENTALE,
     G_PSY, {"cats": {"113", "01", "13"}, "finess": {"412"}}),
    ("lieu_psychotrauma", "Psychotraumatisme et urgences médico-psychologiques", SANTE_MENTALE, G_PSY,
     {"cats": {"127", "03"}}),
    ("lieu_cmpp", "CMPP, centres médico-psycho-pédagogiques", SANTE_MENTALE, G_ENF, {"cats": {"62"}, "finess": {"189"}}),
    ("lieu_camsp", "CAMSP, centres d'action médico-sociale précoce", SANTE_MENTALE, G_ENF,
     {"cats": {"61"}, "finess": {"190"}}),
    ("lieu_mda", "Maisons des adolescents", SANTE_MENTALE, G_ENF, {"cats": {"134"}}),
    ("lieu_bapu", "BAPU, aide psychologique universitaire", SANTE_MENTALE, G_ENF, {"cats": {"64"}, "finess": {"221"}}),
    ("lieu_tnd", "Repérage et diagnostic des troubles du neurodéveloppement", SANTE_MENTALE, G_ENF, {"cats": {"08", "84"}}),
    ("lieu_csapa", "CSAPA, soins et prévention en addictologie", SANTE_MENTALE, G_ADD, {"cats": {"80"}, "finess": {"197"}}),
    ("lieu_caarud", "CAARUD, réduction des risques", SANTE_MENTALE, G_ADD, {"cats": {"81"}, "finess": {"178"}}),
    ("lieu_addicto_hosp", "Addictologie à l'hôpital", SANTE_MENTALE, G_ADD, {"cats": {"145", "147", "108", "272"}}),
    # santé
    # beaucoup d'unités hospitalières du ROR n'ont pas de catégorie, les urgences sont aussi repérées par leur mode
    # (accueil des urgences), les maternités par leur type de maternité
    # services d'urgences générales ou pédiatriques, comme la DREES, sans les urgences spécialisées ni les salles
    # d'accueil des urgences vitales, qui font partie d'un service compté par ailleurs (constat du 12 octobre 2026)
    ("lieu_urgences", "Services d'urgences", SANTE, G_URG,
     {"cats": {"20"}, "modes_seuls": {"33"}, "champs_seuls": {"01"},
      "hors": r"obstetri|gyneco|psychiatr|dentaire|odonto|ophtalm|\bmains?\b|vasculaire|tete et cou|\bsauv\b|"
              r"urgences vitales|maternite|salle de naissance"}),
    ("lieu_smur", "SMUR, interventions d'urgence", SANTE, G_URG, {"cats": {"247"}}),
    ("lieu_soins_non_programmes", "Soins non programmés", SANTE, G_URG, {"cats": {"138", "92", "278"}}),
    # le type de maternité est attaché à toutes les unités d'un hôpital qui en a une, il ne compte que pour les unités
    # d'obstétrique, de gynécologie ou de grossesse, ou dont le nom le dit (constat du 12 octobre 2026)
    ("lieu_maternite", "Maternités", SANTE, G_PERI,
     {"cats": {"290"}, "maternite": {"cats": {"288", "293"}, "nom": r"matern|obstetri|accouch|naissance|salle de naissance"}}),
    ("lieu_neonatalogie", "Néonatalogie", SANTE, G_PERI, {"cats": {"289", "286", "287", "288"}}),
    ("lieu_perinatal_proximite", "Centres périnatals de proximité", SANTE, G_PERI, {"cats": {"251"}}),
    ("lieu_pmi", "PMI, protection maternelle et infantile", SANTE, G_PERI, {"cats": {"125"}, "finess": {"223"}}),
    ("lieu_sante_sexuelle", "Centres de santé sexuelle", SANTE, G_PERI, {"cats": {"89", "98"}, "finess": {"228", "649"}}),
    ("lieu_pediatrie", "Pédiatrie à l'hôpital", SANTE, G_HOP, {"cats": {"162", "241"}}),
    ("lieu_medecine", "Médecine polyvalente à l'hôpital", SANTE, G_HOP, {"cats": {"238", "176"}}),
    ("lieu_geriatrie", "Gériatrie à l'hôpital", SANTE, G_HOP, {"cats": {"156"}}),
    ("lieu_cardiologie", "Cardiologie à l'hôpital", SANTE, G_HOP, {"cats": {"149", "262"}}),
    ("lieu_neurologie", "Neurologie à l'hôpital", SANTE, G_HOP, {"cats": {"161", "263"}}),
    ("lieu_cancerologie", "Cancérologie et radiothérapie", SANTE, G_HOP, {"cats": {"171", "117", "118", "116"}}),
    ("lieu_reanimation", "Réanimation et soins intensifs", SANTE, G_HOP,
     {"cats": {"121", "122", "123", "124", "139", "264"}}),
    ("lieu_chirurgie", "Chirurgie à l'hôpital", SANTE, G_HOP,
     {"cats": {"150", "153", "152", "151", "160", "242", "234", "173", "172", "166", "157"}}),
    ("lieu_dialyse", "Dialyse", SANTE, G_HOP, {"cats": {"275", "273", "274", "271"}, "finess": {"141", "146"}}),
    ("lieu_soins_palliatifs", "Soins palliatifs", SANTE, G_HOP, {"cats": {"175", "252", "253"}}),
    ("lieu_douleur", "Structures douleur chronique", SANTE, G_HOP, {"cats": {"126", "265"}}),
    ("lieu_smr", "Soins médicaux et de réadaptation", SANTE, G_SMR,
     {"cats": {"100", "101", "102", "103", "104", "105", "106", "107", "109", "110", "111", "112"}}),
    ("lieu_had", "Hospitalisation à domicile", SANTE, G_SMR, {"cats": {"128", "129", "130", "131"}, "finess": {"127"}}),
    ("lieu_ssiad", "Soins infirmiers à domicile (SSIAD)", SANTE, G_SMR, {"cats": {"28", "75"}, "finess": {"354"}}),
    ("lieu_ehpad", "EHPAD", SANTE, G_PA, {"cats": {"21", "23", "24", "26"}, "finess": {"500"}}),
    ("lieu_residence_autonomie", "Résidences autonomie", SANTE, G_PA, {"cats": {"22", "27"}, "finess": {"202"}}),
    ("lieu_usld", "Soins de longue durée (USLD)", SANTE, G_PA, {"cats": {"249"}, "finess": {"362"}}),
    ("lieu_alzheimer", "Équipes spécialisées Alzheimer, accueil de jour et répit", SANTE, G_PA,
     {"cats": {"29", "38"}, "finess": {"207"}}),
    ("lieu_ime", "Instituts médico-éducatifs (IME)", SANTE, G_HE, {"cats": {"48"}, "finess": {"183"}}),
    ("lieu_itep", "Instituts thérapeutiques, éducatifs et pédagogiques (ITEP)", SANTE, G_HE,
     {"cats": {"50"}, "finess": {"186"}}),
    ("lieu_sessad", "Services d'éducation spéciale et de soins à domicile (SESSAD)", SANTE, G_HE,
     {"cats": {"57", "58", "59", "60"}, "finess": {"182"}}),
    ("lieu_polyhandicap_enfants", "Établissements pour enfants en situation de polyhandicap, de handicap moteur ou sensoriel",
     SANTE, G_HE, {"cats": {"51", "49", "52", "53", "54"}, "finess": {"188", "192", "194", "195", "390", "396"}}),
    ("lieu_mas_fam", "Maisons d'accueil spécialisées et foyers d'accueil médicalisés", SANTE, G_HA,
     {"cats": {"40", "39"}, "finess": {"255", "437"}}),
    ("lieu_foyers_handicap", "Foyers de vie et d'hébergement pour adultes en situation de handicap", SANTE, G_HA,
     {"cats": {"41", "96", "97", "256"}, "finess": {"382", "252", "253", "395"}}),
    ("lieu_esat", "Établissements et services d'accompagnement par le travail (ESAT)", SANTE, G_HA,
     {"cats": {"43"}, "finess": {"246"}}),
    ("lieu_accompagnement_handicap", "Services d'accompagnement à domicile pour adultes en situation de handicap",
     SANTE, G_HA, {"cats": {"31", "32"}, "finess": {"445", "446"}}),
    ("lieu_precarite", "Soins pour personnes en situation de précarité (PASS, LHSS, LAM, ACT)", SANTE, G_PREC,
     {"cats": {"295", "93", "95", "94", "142", "115"}, "finess": {"180", "213", "165", "608"}}),
    ("lieu_depistage", "Dépistage, vaccination et lutte antituberculeuse", SANTE, G_PREC,
     {"cats": {"250", "268", "269", "270"}, "finess": {"638", "645", "646", "143", "637"}}),
    ("lieu_msp", "Maisons de santé pluriprofessionnelles", SANTE, G_PREM, {"cats": {"99"}, "finess": {"603"}}),
    ("lieu_centre_sante", "Centres de santé", SANTE, G_PREM, {"finess": {"124"}}),
    ("lieu_cpts", "Communautés professionnelles territoriales de santé (CPTS)", SANTE, G_PREM, {"cats": {"255"}}),
]
# Un type n'est présenté par territoire (cartes, croisements, comparaisons) que s'il est recensé dans au moins cette
# part des départements. En dessous, il reste dans la liste des lieux avec la mention d'un recensement incomplet.
LIEUX_COUVERTURE_MIN = 0.9
# Chiffre publié auquel un type est confronté (clé « reference » du registre). Vérifié le 12 octobre 2026.
DREES_PANORAMA_ES_2025 = ("DREES, Les établissements de santé en 2023, édition 2025",
                          "https://drees.solidarites-sante.gouv.fr/publications-communique-de-presse-documents-de-reference/"
                          "panoramas-de-la-drees/250522_Panorama_etablissements-de-sante2025")
GROUPE_LIEUX = "Structures de soins (FINESS et ROR)"
# Public de chaque type de structure, pour la rapporter aux habitants concernés plutôt qu'à toute la population (accord
# de Lucas du 15 octobre 2026, même règle que PUBLICS_CIBLES pour les professions). Le recensement publie les moins de
# 15 ans, pas les moins de 18 ans.
_MOINS_15 = (["part_0_14"], "moins de 15 ans")
_80_PLUS = (["part_80p"], "80 ans et plus")
_SOURCES_CMP = ["etablissement", "source_publique", "has", "sirene"]
_SOURCES_MEDICO_SOCIAL = _SOURCES_CMP + ["has_essms", "principal"]   # CMPP, CAMSP, CSAPA, CAARUD, évalués par la HAS
DOUBLE_ELOIGNEMENT_KM = 20
# Registre des types de structures de soins activés (16 octobre 2026, lu par pipeline/lieux_profil.py). LIEUX_TYPES dit
# ce qu'est un type, ce registre dit ce qu'on en fait. Un type ajouté ici est testé sans écrire de test
# (tests/test_unitaires.py, test_lieux_profil_*) et paraît dans le tableau d'avancement (docs/avancement_structures.md).
#   public          adultes, enfants, tous ou grand_age
#   denominateur    (colonnes de contexte, libellé) du public auquel le type est rapporté, absent pour la population
#   confirmation    sources de confirmation indépendantes de FINESS et du ROR, vide si aucune (confirmation.py)
#   reference       chiffre auquel le type est confronté, genre « sae » (champ de concordance_cmp_sae.csv) ou
#                   « publiee » (valeur, date, objet, source), avec l'écart relatif toléré
#   analyses        voir pipeline/lieux_profil.py, l'ordre du registre fixe l'ordre des colonnes et des figures
#   limite          clé de LIMITES rappelée avec le type
#   a_venir         mot qui annonce le type dans contenus/a_venir.md
LIEUX_PROFIL = {
    "lieu_cmp": {"public": "tous", "confirmation": _SOURCES_CMP, "limite": "lieux", "analyses": [],
                 "reference": {"genre": "sae", "champ": "sae_cmp", "ecart_max": .2}},
    "lieu_cmp_adultes": {
        "public": "adultes", "confirmation": _SOURCES_CMP, "limite": "lieux",
        "reference": {"genre": "sae", "champ": "sae_adultes", "ecart_max": .2},
        "analyses": ["indicateur", "sensibilite", "zones", "double_eloignement:adultes", "charge", "typologie:sm",
                     "typologie:tout", "eloignement:sm"]},
    "lieu_cmp_enfants": {
        "public": "enfants", "denominateur": _MOINS_15, "confirmation": _SOURCES_CMP, "limite": "lieux",
        "reference": {"genre": "sae", "champ": "sae_enfants", "ecart_max": .2},
        "analyses": ["indicateur", "sensibilite", "zones", "double_eloignement:enfants", "charge", "typologie:sm",
                     "typologie:tout", "eloignement:sm"]},
    "lieu_cattp": {"public": "tous", "confirmation": _SOURCES_CMP + ["sae"], "limite": "lieux", "a_venir": "CATTP",
                   "analyses": ["indicateur", "sensibilite", "zones", "typologie:sm"]},
    "lieu_hdj_psy_adultes": {"public": "adultes", "confirmation": _SOURCES_CMP, "limite": "lieux",
                             "a_venir": "hôpitaux de jour",
                             "analyses": ["indicateur", "sensibilite", "zones", "typologie:sm"]},
    "lieu_hdj_psy_enfants": {"public": "enfants", "denominateur": _MOINS_15, "confirmation": _SOURCES_CMP,
                             "limite": "lieux", "a_venir": "hôpitaux de jour",
                             "analyses": ["indicateur", "sensibilite", "typologie:sm"]},
    "lieu_hc_psy_adultes": {"public": "adultes", "limite": "lieux", "analyses": ["indicateur"]},
    "lieu_cmpp": {"public": "enfants", "denominateur": _MOINS_15, "confirmation": _SOURCES_MEDICO_SOCIAL,
                  "limite": "lieux", "a_venir": "CMPP",
                  "analyses": ["indicateur", "sensibilite", "zones", "typologie:sm", "double_eloignement:enfants",
                               "eloignement:sm"]},
    "lieu_camsp": {"public": "enfants", "denominateur": _MOINS_15, "confirmation": _SOURCES_MEDICO_SOCIAL,
                   "limite": "lieux", "a_venir": "CAMSP",
                   "analyses": ["indicateur", "sensibilite", "typologie:sm", "double_eloignement:enfants"]},
    "lieu_csapa": {"public": "tous", "confirmation": _SOURCES_MEDICO_SOCIAL, "limite": "lieux",
                   "a_venir": "addictologie", "analyses": ["indicateur", "sensibilite", "zones", "typologie:sm"]},
    "lieu_caarud": {"public": "tous", "confirmation": _SOURCES_MEDICO_SOCIAL, "limite": "lieux",
                    "a_venir": "addictologie", "analyses": ["indicateur"]},
    "lieu_urgences": {
        "public": "tous", "limite": "lieux",
        "reference": {"genre": "publiee", "valeur": 685, "date": "2023", "ecart_max": .1,
                      "objet": "structures des urgences générales ou pédiatriques", "source": DREES_PANORAMA_ES_2025},
        "analyses": ["indicateur", "zones", "typologie:sante", "typologie:tout", "eloignement:sante"]},
    "lieu_maternite": {
        "public": "tous", "limite": "lieux",
        "reference": {"genre": "publiee", "valeur": 457, "date": "fin 2023", "ecart_max": .1, "objet": "maternités",
                      "source": DREES_PANORAMA_ES_2025},
        "analyses": ["indicateur", "typologie:sante", "typologie:tout", "eloignement:sante"]},
    "lieu_ehpad": {"public": "grand_age", "denominateur": _80_PLUS, "limite": "lieux",
                   "analyses": ["indicateur", "typologie:sante", "eloignement:sante"]},
    "lieu_ime": {"public": "enfants", "denominateur": _MOINS_15, "limite": "lieux", "analyses": ["indicateur"]},
    "lieu_sessad": {"public": "enfants", "denominateur": _MOINS_15, "limite": "lieux", "analyses": ["indicateur"]},
    "lieu_msp": {"public": "tous", "limite": "lieux", "analyses": ["indicateur", "typologie:sante", "typologie:tout"]},
    "lieu_centre_sante": {"public": "tous", "limite": "lieux", "analyses": ["indicateur", "typologie:sante"]},
}
# indicateurs d'Odissé réunis dans la partie « Addictologie » du rapport santé mentale et de l'atlas (22 octobre 2026)
ADDICTO_ODISSE = ["alcool_depassement_reperes", "tabac_quotidien", "deces_attribuables_tabac"]
# Champs du double éloignement (pipeline/structures_analyses.py), professions et libellé. Les structures de chaque champ
# sont celles du registre qui portent « double_eloignement:<champ> ».
DOUBLE_ELOIGNEMENT_CHAMPS = {
    "adultes": (["psychiatre"],
                "Sans psychiatre déclaré dans l'intercommunalité et à plus de 20 km d'un CMP pour adultes"),
    "enfants": (["q_psychiatrie_enfant"],
                "Sans psychiatre qualifié pour l'enfant dans l'intercommunalité et à plus de 20 km d'un CMP pour "
                "enfants, d'un CMPP ou d'un CAMSP"),
}
GROUPE_DISTANCES = "Distance aux structures de soins"
SOURCE_LIEUX = "ANS, offres de santé (ROR) et FINESS, réunis sans double compte"
# groupes de lieux montrés point par point dans l'atlas (carte et fiche d'un territoire), les autres restent dans les
# fichiers publiés, pour garder l'atlas léger
LIEUX_ATLAS_GROUPES = {G_PSY, G_PSY_A, G_PSY_E, G_ENF, G_ADD, G_URG, G_PERI, G_HE}
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
                  "des centres médico-psychologiques (CMP) n'ont aucun psychiatre déclaré à leur adresse, les "
                  "consultations y sont rattachées à l'établissement dont ils dépendent. Un territoire sans "
                  "psychiatre déclaré peut donc accueillir des consultations de psychiatrie. Le nombre de CMP de "
                  "chaque territoire, recensés par FINESS et le ROR réunis sans double compte, est donné à côté."),
        "sources": [SRC_RPPS, SRC_FINESS, SRC_ROR]},
    "prof:pedopsychiatre": {
        "risque": "définition étroite",
        "texte": ("La spécialité « pédopsychiatrie » déclarée au répertoire ne concerne qu'une partie des médecins qui "
                  "soignent des enfants et des adolescents. La plupart sont inscrits comme psychiatres, avec une "
                  "qualification pour l'enfant obtenue par une autre voie. La Cour des comptes comptait 545 "
                  "pédopsychiatres au sens strict en 2021, et environ 2 000 en ajoutant les psychiatres qualifiés pour "
                  "l'enfant. Un territoire sans pédopsychiatre déclaré comme tel peut donc compter des psychiatres qui "
                  "soignent des enfants. Le nombre de psychiatres qualifiés pour l'enfant et l'adolescent, toutes "
                  "voies, est donné à côté. Comme les psychiatres, ils consultent aussi dans des structures où ils ne "
                  "sont pas déclarés, rattachées à un hôpital ou à une association, CMP pour enfants et adolescents, "
                  "centres médico-psycho-pédagogiques (CMPP) ou centres d'action médico-sociale précoce (CAMSP). Un "
                  "territoire sans pédopsychiatre déclaré peut donc accueillir des consultations pour enfants. Ces "
                  "lieux, recensés par FINESS et le ROR réunis sans double compte, sont donnés à côté."),
        "sources": [("Cour des comptes, la pédopsychiatrie, un accès et une offre de soins à réorganiser, mars 2023",
                     "https://www.ccomptes.fr/fr/publications/la-pedopsychiatrie"), SRC_RPPS, SRC_FINESS, SRC_ROR]},
    "lieux": {
        "risque": "recensement incomplet",
        "texte": ("Les structures de soins réunissent FINESS et le Répertoire opérationnel des ressources (ROR), rapprochés "
                  "par le numéro FINESS d'établissement, l'entité juridique gestionnaire et la commune, puis par le nom, "
                  "pour qu'une même structure ne compte qu'une fois. Ni l'une ni l'autre base n'est complète. FINESS "
                  "enregistre souvent un CMP sous le numéro de son hôpital, et le ROR est rempli par les établissements "
                  "eux-mêmes, avec une complétude inégale selon les régions et des catégories parfois approximatives "
                  "(équipes mobiles rangées parmi les CMP, unités sans catégorie). Ces erreurs de classement sont "
                  "corrigées par des règles appliquées à toute la France, décrites et chiffrées dans la page méthode. "
                  "Certaines structures manquent aux deux bases, par exemple deux CMP de Martinique cités par l'ARS en "
                  "2018, ou des CMP listés sur le site de leur hôpital (voir les vérifications sur d'autres sources). Une structure n'est pas une capacité, une antenne peut n'ouvrir "
                  "que quelques demi-journées. Un CATTP est compté comme FINESS et la statistique annuelle des "
                  "établissements de santé le comptent, un lieu où l'hôpital déclare cette activité, souvent tenue "
                  "dans un CMP ou un centre de jour qui porte un autre nom. Quand un CMP annonce un CATTP dans son nom ou son "
                  "enseigne (« CMP-CATTP ») et que son gestionnaire n'en a pas d'autre dans la commune, un CATTP est "
                  "compté au même lieu. Les professionnels déclarés sur place viennent du RPPS, beaucoup "
                  "déclarent leur hôpital de rattachement plutôt que le lieu où ils consultent. Les distances sont "
                  "mesurées à vol d'oiseau depuis le centre de chaque commune, l'emplacement d'une structure sans coordonnées "
                  "connues étant le centre de sa commune. Un type recensé dans moins de 90 % des départements est "
                  "listé, mais pas comparé entre territoires."),
        "sources": [SRC_ROR, SRC_FINESS, SRC_ARS_MARTINIQUE,
                    ("IGN, service de géocodage de la Géoplateforme", GEOCODAGE_PAGE)]},
    "confirmation": {
        "risque": "confirmation incomplète",
        "texte": ("Chaque CMP, CATTP, hôpital de jour en psychiatrie, CMPP, CAMSP, CSAPA et CAARUD est confronté à "
                  "des listes indépendantes de FINESS et du ROR, les sites que son établissement déclare à sa "
                  "certification par la HAS, les évaluations des établissements médico-sociaux publiées par la HAS, "
                  "et les établissements de son gestionnaire inscrits au répertoire Sirene sous une enseigne de son "
                  "type. La liste de la certification reprend les numéros FINESS déclarés par l'établissement à la "
                  "date de sa certification, parfois ancienne de plusieurs années, sans adresse ni activité réelle. "
                  "Les évaluations des établissements médico-sociaux ont commencé en 2023 et chaque structure est "
                  "évaluée une fois tous les cinq ans, une structure pas encore évaluée n'est donc pas douteuse pour "
                  "autant. Les hôpitaux ferment rarement leurs anciens établissements dans Sirene, un établissement "
                  "encore actif dans Sirene peut avoir cessé son activité. Une structure confirmée par l'une de ces "
                  "listes existe dans les listes officielles de son établissement, une structure confirmée par aucune "
                  "reste à vérifier sur les sources de l'établissement. Les rapports et l'atlas réunissent ces "
                  "sources en trois classes, confirmée (nommée par une source indépendante des deux bases), "
                  "recoupée par la statistique des hôpitaux (SAE, nombre de CATTP de l'hôpital ou places d'hôpital de jour du site, "
                  "l'adresse n'étant pas confirmée) et à vérifier (inscrite dans FINESS ou le ROR seulement)."),
        "sources": [("HAS, certification des établissements de santé, données ouvertes", HAS_PAGE),
                    ("HAS, résultats d'évaluation des établissements et services sociaux et médico-sociaux",
                     HAS_ESSMS_PAGE),
                    ("INSEE, base Sirene des entreprises et de leurs établissements", SIRENE_PAGE)]},
    "addictions": {
        "risque": "mesure déclarée ou estimée",
        "texte": ("Les consommations d'alcool et de tabac viennent du Baromètre de Santé publique France, une enquête "
                  "où les personnes déclarent elles-mêmes ce qu'elles consomment, ce qui sous-estime en général les "
                  "consommations. Elles ne sont publiées que par région, avec une fourchette souvent large dans les "
                  "petites régions et en outre-mer. Les décès attribuables au tabac sont une estimation. Les personnes "
                  "prises en charge pour une addiction (Assurance Maladie) mesurent le recours aux soins, qui dépend "
                  "aussi de l'offre, et non le besoin."),
        "sources": [("Santé publique France, Baromètre de Santé publique France 2024, alcool",
                     "https://odisse.santepubliquefrance.fr/explore/dataset/"
                     "alcool-indicateurs-du-barometre-de-sante-publique-france-2024-detail-region/"),
                    ("Santé publique France, consommation quotidienne de tabac par région",
                     "https://odisse.santepubliquefrance.fr/explore/dataset/tabac-consommation-quotidienne_reg/"),
                    ("Santé publique France, décès attribuables au tabac par région",
                     "https://odisse.santepubliquefrance.fr/explore/dataset/tabac-deces-attribuables-au-tabac_reg/")]},
    "prof:orthophoniste": {
        "risque": "tous les âges",
        "texte": ("Les orthophonistes soignent des patients de tous les âges, pas seulement des enfants. Le code de la "
                  "santé publique vise les troubles congénitaux, développementaux ou acquis, ce qui comprend les "
                  "troubles du langage après un accident vasculaire cérébral, les maladies neurodégénératives, la voix "
                  "et la déglutition. Leur densité est donc rapportée à toute la population, et un croisement avec "
                  "l'offre pour les enfants n'en décrit qu'une partie de l'activité."),
        "sources": [("Code de la santé publique, article L4341-1 (Légifrance)",
                     "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000047568519"), SRC_RPPS]},
    "prof:psychomotricien": {
        "risque": "tous les âges",
        "texte": ("Les psychomotriciens interviennent auprès des jeunes enfants et des adolescents, mais aussi des "
                  "adultes et des personnes âgées, en psychiatrie, en gériatrie et en établissement pour personnes "
                  "âgées. Leur densité est donc rapportée à toute la population. Beaucoup sont salariés d'un "
                  "établissement, un croisement avec la seule offre libérale n'en décrit qu'une partie."),
        "sources": [("Onisep, fiche métier psychomotricien ou psychomotricienne",
                     "https://www.onisep.fr/ressources/univers-metier/metiers/psychomotricien-psychomotricienne"),
                    ("Ministère de la Santé, répertoire des métiers de la fonction publique hospitalière, psychomotricien",
                     "http://www.metiers-fonctionpubliquehospitaliere.sante.gouv.fr/spip.php?page=fiche-metier&idmet=13"),
                    SRC_RPPS]},
    "prof:medecin_travail": {
        "risque": "pas de soins à la population",
        "texte": ("Les médecins du travail suivent les salariés de leur entreprise ou de leur service de santé au "
                  "travail. Ils ne soignent pas la population du territoire où ils sont déclarés."),
        "sources": [SRC_RPPS]},
    "prof:medecin_sante_publique": {
        "risque": "pas de soins à la population",
        "texte": ("Les médecins de santé publique exercent surtout dans des administrations, des agences ou des services "
                  "d'épidémiologie et de prévention, rarement en soins à la population."),
        "sources": [SRC_RPPS]},
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
    # mesuré à chaque exécution par lieux.controle_route_cmp (note docs/note_valeurs_aberrantes_2026-10-28.md)
    "route_psychiatrie_ambulatoire": {
        "risque": "recensement incomplet",
        "texte": ("Le temps de route de l'INSEE vers la psychiatrie ambulatoire contredit, dans de nombreuses communes, "
                  "la distance au CMP le plus proche (plus de 30 minutes alors qu'un CMP est à moins de 8 km). La base "
                  "permanente des équipements ne compte vraisemblablement que les CMP inscrits sous leur propre "
                  "catégorie dans FINESS, alors qu'un CMP sur trois n'y figure que sous le numéro de son hôpital ou "
                  "seulement dans le ROR. La distance au CMP le plus proche, tirée de FINESS et du ROR réunis, est plus "
                  "sûre."),
        "sources": [SRC_INSEE_ROUTE, SRC_FINESS, SRC_ROR]},
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
# Phrase courte de chaque limite, montrée seule sous la figure de l'atlas, le texte entier s'ouvrant au clic (chantier
# d'organisation de l'atlas, 22 octobre 2026). Sans phrase courte, la première phrase du texte sert. Chaque phrase
# résume le texte de la limite sans rien y ajouter.
LIMITES_COURT = {
    "mayotte": ("À Mayotte, les densités sont surestimées d'environ un quart (population de 2017) et Mayotte est écartée "
                "des croisements entre départements."),
    "prof:psychiatre": "Un territoire sans psychiatre déclaré peut accueillir des consultations de psychiatrie, dans les CMP.",
    "prof:psychologue": ("Les psychologues sont inscrits au RPPS depuis la reprise d'ADELI, leur nombre est un peu en "
                         "dessous des séries de la DREES."),
    "lieux": "Ni FINESS ni le ROR ne sont complets, certaines structures manquent aux deux bases ou y sont mal classées.",
    "confirmation": ("Une structure à vérifier n'est pas douteuse pour autant, les listes qui servent à confirmer sont "
                     "incomplètes ou anciennes."),
    "route": ("Temps en voiture vers le libéral le plus proche, sans les délais de rendez-vous, les tarifs ni les "
              "transports en commun."),
    "route_psychiatrie_ambulatoire": ("Le temps de l'INSEE vers la psychiatrie ambulatoire ignore vraisemblablement un "
                                      "CMP sur trois, la distance au CMP le plus proche est plus sûre."),
    "ald": "Les ALD comptent les personnes dont la maladie a été reconnue, pas toutes les personnes malades.",
    "caf": "Les allocations versées par la MSA ne sont pas comptées, ce qui sous-estime ces chiffres surtout en zone rurale.",
    "evolution": ("Les séries de la DREES comptent chaque professionnel une seule fois, dans le département de son "
                  "activité principale."),
}
LIMITES_ALIAS = {"route:psychiatrie_ambulatoire": "route_psychiatrie_ambulatoire",
                 "sae_": "sae", "ald_": "ald", "caf_": "caf", "evol:": "evolution", "lieu_": "lieux", "lieux:": "lieux"}

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
    # la psychiatrie ambulatoire de l'INSEE (D109) est retirée le 28 octobre 2026, elle ignore un CMP sur trois
    # (LIMITES["route_psychiatrie_ambulatoire"])
    ("route:psychiatre_liberal", "suicides", "trajet_suicide",
     "Les départements éloignés d'un psychiatre libéral ont-ils plus de suicides, au-delà de la ruralité ?"),
    ("ctx:handicap_places_enfants", "dens_lib:orthophoniste", "reeducation",
     "L'offre libérale de rééducation suit-elle l'offre médico-sociale pour les enfants ?"),
    ("ctx:handicap_places_enfants", "dens_lib:psychomotricien", "reeducation", ""),
    ("ctx:handicap_places_sessad", "dens_lib:orthophoniste", "reeducation", ""),
    ("dens_lib:medecin_generaliste", "ald_sans_medecin_traitant", "medecin_traitant",
     "Les patients sans médecin traitant sont-ils plus nombreux là où les généralistes libéraux manquent ?"),
    ("ctx:part_80p", "ald_sans_medecin_traitant", "medecin_traitant", ""),
    # lieux de soins, FINESS et ROR réunis (version 2, 12 octobre 2026)
    ("dens_lib:psychiatre", "lieux_lieu_cmp_adultes", "lieux_psy",
     "Les CMP, CATTP et hôpitaux de jour sont-ils plus nombreux là où les psychiatres manquent ?"),
    ("dens:psychiatre", "lieux_lieu_cmp_adultes", "lieux_psy", ""),
    ("dens:psychiatre", "lieux_lieu_cattp", "lieux_psy", ""),
    ("dens:psychiatre", "lieux_lieu_hdj_psy_adultes", "lieux_psy", ""),
    ("dens:q_psychiatrie_enfant", "lieux_lieu_cmp_enfants", "lieux_enfants",
     "Les structures de soins pour enfants suivent-elles l'offre de psychiatres pour l'enfant ?"),
    ("dens:q_psychiatrie_enfant", "lieux_lieu_cmpp", "lieux_enfants", ""),
    ("dens:q_psychiatrie_enfant", "lieux_lieu_camsp", "lieux_enfants", ""),
    ("dens:q_psychiatrie_enfant", "lieux_lieu_hdj_psy_enfants", "lieux_enfants", ""),
    ("ctx:ase_mesures", "lieux_lieu_cmp_enfants", "enfance", ""),
    ("ctx:ase_mesures", "lieux_lieu_cmpp", "enfance", ""),
    ("ctx:taux_pauvrete", "dist_lieu_cmp_adultes", "lieux_social",
     "Les habitants des départements modestes sont-ils plus loin des CMP et des CSAPA ?"),
    ("ctx:taux_pauvrete", "dist_lieu_cmp_enfants", "lieux_social", ""),
    ("ctx:taux_pauvrete", "dist_lieu_csapa", "lieux_social", ""),
    # addictologie (21 octobre 2026, demande de Lucas de tirer des nouvelles structures tout ce qu'elles permettent)
    ("pec_addictions", "lieux_lieu_csapa", "lieux_addicto",
     "Les structures d'addictologie sont-elles plus nombreuses là où plus de personnes sont prises en charge pour une "
     "addiction ?"),
    ("dens:q_addictologie", "lieux_lieu_csapa", "lieux_addicto", ""),
    ("pec_addictions", "lieux_lieu_caarud", "lieux_addicto", ""),
    ("dist_lieu_urgences", "urgences_gestes_auto_infliges", "lieux_urgences",
     "Les départements éloignés des urgences comptent-ils plus ou moins de passages pour geste auto-infligé ?"),
    ("dist_lieu_maternite", "ctx:part_0_14", "lieux_maternite",
     "Les départements où les maternités sont loin ont-ils moins d'enfants ?"),
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
# Mesure d'audience sans cookie, pour le seul porteur du projet (demande de Lucas du 23 octobre 2026). GoatCounter,
# logiciel libre (EUPL 1.2), service hébergé dans l'Union européenne (Hetzner, Finlande et Allemagne), aucun cookie,
# aucune adresse IP conservée, totaux par page seulement. Pages vérifiées le 23 octobre 2026,
# https://www.goatcounter.com/help/start, https://www.goatcounter.com/help/privacy, https://www.goatcounter.com/help/countjs-versions
# (count.v5.js du 9 juin 2025, empreinte ci-dessous, ce fichier versionné ne change jamais). Code du compte créé par Lucas
# (tutoriel 08) ; vide, aucun script n'est ajouté aux pages.
GOATCOUNTER = "ubicura"   # compte créé par Lucas le 23 octobre 2026, tableau de bord https://ubicura.goatcounter.com
GOATCOUNTER_SCRIPT = "https://gc.zgo.at/count.v5.js"
GOATCOUNTER_INTEGRITE = "sha384-atnOLvQb9t+jTSipvd75X2yginT4PjVbqDdlJAmxMm+wYElFmeR6EmLP5bYeoRVQ"

DOI_DONNEES = "10.5281/zenodo.23264933"   # DOI général des données (première version publiée le 9 octobre 2026, 10.5281/zenodo.23264934)
DOI_RAPPORTS = {"sante-mentale": "10.5281/zenodo.23265073", "sante": "10.5281/zenodo.23265208"}
# dernière version archivée sur Zenodo (date du dossier de résultats). Une version plus récente du site est citée par son
# adresse, avec le DOI général à côté. À mettre à jour à chaque nouvelle version publiée sur Zenodo (tutoriels 05 et 07).
VERSION_ZENODO = "2026-10-09"
# les versions suivantes sont constatées sur Zenodo par outils/zenodo.py (tutoriel 07), qui l'écrit dans donnees/zenodo.json
if (DONNEES / "zenodo.json").exists():
    import json as _json
    VERSION_ZENODO = _json.loads((DONNEES / "zenodo.json").read_text(encoding="utf-8")).get("version_archivee") or VERSION_ZENODO
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
    (r"^has/(?!has_essms)", "Certification des établissements de santé, sites rattachés", "Haute Autorité de santé",
     r"^HAS, certification", "Confirmation des structures inscrites dans FINESS par les sites que chaque établissement "
     "déclare à sa certification."),
    (r"^has/has_essms", "Évaluation des établissements et services sociaux et médico-sociaux", "Haute Autorité de santé",
     r"^HAS, évaluation", "Confirmation des CMPP, CAMSP, CSAPA et CAARUD évalués sous la catégorie de leur type."),
    (r"^sirene/", "Répertoire Sirene des établissements", "INSEE", r"^INSEE, répertoire Sirene",
     "Confirmation des CMP et des autres structures de santé mentale par l'enseigne des établissements de leur "
     "gestionnaire, et leur adresse."),
    (r"^ror/", "Offres de santé, Répertoire opérationnel des ressources (ROR)", "Agence du numérique en santé",
     r"^ANS, offres de santé",
     "Structures de soins (CMP, CATTP, hôpitaux de jour, CMPP, CAMSP, urgences, maternités, établissements médico-sociaux...), "
     "réunies à FINESS sans double compte, distances aux structures les plus proches."),
]
# Professions dont l'effectif national figure dans le journal quand il change
JOURNAL_PROFESSIONS = ["psychologue", "psychiatre", "pedopsychiatre", "medecin_generaliste", "infirmier",
                       "masseur_kinesitherapeute", "orthophoniste", "psychomotricien", "sage_femme", "pediatre"]
# Ligne de message de commit reprise dans le journal comme évolution du site (« Journal: texte pour le lecteur »)
JOURNAL_MOTIF_COMMIT = r"^Journal\s*:\s*(.+)$"
