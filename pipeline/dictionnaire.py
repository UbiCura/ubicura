"""Dictionnaire des colonnes. Décrit chaque fichier CSV produit et chacune de ses colonnes, à partir
des fichiers réellement écrits. Une colonne sans description est signalée comme telle, ce qui
permet de repérer un oubli quand le programme évolue."""
from __future__ import annotations

import re
from pathlib import Path

from . import config

NIVEAUX = {"com": "commune", "epci": "intercommunalité", "dep": "département", "reg": "région"}
MODES = {"all": "tous modes d'exercice", "lib": "exercice libéral", "sal": "exercice salarié"}

# (motif sur le nom de fichier, description du fichier)
FICHIERS = [
    (r"^sensibilite_confirmation\.csv$", lambda m: "Résultats clés sur les structures de soins recalculés avec les seules "
     "structures confirmées par une source indépendante de FINESS et du ROR (sources de l'établissement, autre source "
     "publique, certification de la HAS, Sirene), pour dire si la conclusion tient sans les structures non confirmées."),
    (r"^double_eloignement\.csv$", lambda m: "Part des habitants qui vivent dans une intercommunalité sans professionnel "
     "déclaré du champ et à plus de 20 km à vol d'oiseau d'une structure du même champ, France, régions et départements."),
    (r"^charge_cmp_sae\.csv$", lambda m: "File active ambulatoire et psychiatres salariés en temps plein rapportés aux CMP "
     "que les établissements déclarent à la statistique annuelle des établissements de santé (SAE), par discipline. "
     "Département du siège de l'établissement. La file active ambulatoire compte aussi les patients vus hors CMP "
     "(CATTP, consultations, liaison)."),
    (r"^zones_eloignement\.csv$", lambda m: "Zones où l'éloignement des habitants à une structure de soins se concentre, "
     "Moran local des distances médianes par intercommunalité, avec correction de Benjamini-Hochberg."),
    (r"^lieux_soins\.csv$", lambda m: "Structures de soins réunies de FINESS et du Répertoire opérationnel des ressources (ROR), "
                                       "sans double compte. Une ligne par structure et par type, avec son emplacement, sa "
                                       "provenance et les professionnels déclarés sous son numéro FINESS quand elle est "
                                       "seule à le porter dans sa commune."),
    (r"^declares_etablissements\.csv$", lambda m: "Professionnels déclarés au répertoire dans un établissement dont plusieurs "
                                                   "structures de la même commune partagent le numéro FINESS, une ligne par "
                                                   "établissement. Cet effectif n'est attribué à aucune de ces structures."),
    (r"^lieux_soins_(epci|dep|reg)\.csv$", lambda m: f"Nombre de structures de soins de chaque type par {NIVEAUX[m.group(1)]}, "
                                                    "et pour 100 000 habitants."),
    (r"^distances_lieux_(epci|dep|reg|france)\.csv$",
     lambda m: "Distance à vol d'oiseau des habitants à la structure de soins la plus proche de chaque type, "
               + (f"par {NIVEAUX[m.group(1)]}." if m.group(1) in NIVEAUX else "France entière.")),
    (r"^distances_lieux_classes_densite\.csv$", lambda m: "Distance des habitants à la structure de soins la plus proche selon "
                                                            "le type de territoire (classes de densité des "
                                                            "intercommunalités), avec le test de l'écart entre classes."),
    (r"^concentration_distance_lieux\.csv$", lambda m: "Indice de concentration de la distance aux structures de soins selon "
                                                         "le niveau de vie des intercommunalités, avec sa fourchette."),
    (r"^concordance_cmp_sae\.csv$", lambda m: "CMP recensés par FINESS et le ROR confrontés aux CMP que les "
                                               "établissements déclarent à la SAE de la DREES, par département et région."),
    (r"^exercice_structures\.csv$", lambda m: "Professionnels qui déclarent exercer dans une structure de santé "
                                                "mentale enregistrée sous son propre numéro FINESS (CMP, CATTP, CMPP, "
                                                "CAMSP, CSAPA, CAARUD), par type, en France, par région et par "
                                                "département, en personnes distinctes."),
    (r"^concordance_cattp_sae\.csv$", lambda m: "CATTP recensés par FINESS et le ROR confrontés aux CATTP que les "
                                                 "établissements déclarent à la SAE de la DREES, par département et "
                                                 "région."),
    (r"^sirene_sans_correspondant\.csv$", lambda m: "Établissements actifs du répertoire Sirene, sous une enseigne "
                                                     "de CMP ou d'une autre structure de santé mentale (CATTP, hôpital "
                                                     "de jour, CMPP, CAMSP, CSAPA, CAARUD), sans structure "
                                                     "correspondante dans FINESS ou le ROR, à vérifier."),
    (r"^verdicts_sans_structure\.csv$", lambda m: "Verdicts de la vérification à la main qui ne retrouvent plus leur structure "
     "(clé changée par une mise à jour des bases ou structure déjà réunie à une autre), à revoir."),
    (r"^etablissements_verifies\.csv$", lambda m: "Établissements dont les structures ont été reprises une à une sur "
                                                    "leurs propres sources (liste vérifiée)."),
    (r"^structures_non_retenues\.csv$", lambda m: "Inscriptions de FINESS ou du ROR qui ne correspondent à aucune "
                                                  "structure de la liste vérifiée de leur établissement."),
    (r"^structures_gardees_a_verifier\.csv$", lambda m: "Inscriptions de FINESS ou du ROR absentes de la liste "
                                                        "vérifiée de leur établissement mais confirmées par la "
                                                        "certification HAS ou Sirene, gardées en attendant une "
                                                        "vérification à la main."),
    (r"^concordance_cmp_etablissements\.csv$", lambda m: "CMP et CATTP confrontés hôpital par hôpital (entité juridique) "
                                                         "aux déclarations de la SAE, pour repérer les établissements à "
                                                         "vérifier."),
    (r"^relecture_structures\.csv$", lambda m: "Relecture de FINESS et du ROR, chaque correction apportée avec le nombre "
                                                 "de structures concernées."),
    (r"^cmp_par_public\.csv$", lambda m: "Centres médico-psychologiques par public, pour adultes, pour enfants et "
                                          "adolescents, accueillant les deux, au public non précisé, par territoire."),
    (r"^typologie_lieux\.csv$", lambda m: "Structures de soins et distances décrites dans chaque groupe de la typologie, à "
                                           "titre descriptif (ils ne servent pas à former les groupes)."),
    (r"^escalier_distance_lieux\.csv$", lambda m: "Distance des habitants à la structure de soins la plus proche selon le niveau "
                                                    "de vie de leur intercommunalité, par dixième de la population."),
    (r"^distances_lieux_communes\.csv$", lambda m: "Distance à vol d'oiseau du centre de chaque commune à la structure de soins la "
                                                     "plus proche de chaque type recensé presque partout."),
    (r"^concordance_finess_ror\.csv$", lambda m: "Provenance des structures de soins par département et par type, dans les "
                                                  "deux bases, dans FINESS seul ou dans le ROR seul."),
    (r"^lieux_couverture\.csv$", lambda m: "Part des départements où chaque type de lieu est recensé. Sous 90 %, le type "
                                            "est listé mais pas comparé entre territoires."),
    (r"^lieux_references\.csv$", lambda m: "Nombre de lieux rapproché des chiffres publiés par la DREES."),
    (r"^effectifs_(com|epci|dep|reg)_(all|lib|sal)\.csv$",
     lambda m: f"Effectifs et densités par {NIVEAUX[m.group(1)]}, {MODES[m.group(2)]}. Une ligne par territoire, "
               "une paire de colonnes par profession."),
    (r"^effectifs_france\.csv$", lambda m: "Effectifs nationaux par profession et mode d'exercice, en personnes "
                                           "distinctes, activités sans lieu d'exercice comprises."),
    (r"^professions\.csv$", lambda m: "Liste des professions, qualifications et comptages du périmètre élargi."),
    (r"^secteurs\.csv$", lambda m: "Effectifs par secteur d'activité déclaré au RPPS, France et départements."),
    (r"^secteurs_psychiatrie\.csv$", lambda m: "Sectorisation psychiatrique d'après les arrêtés des agences régionales de "
     "santé reçus (Hauts-de-France, arrêté du 26 décembre 2023), une ligne par commune, type de secteur et secteur, avec "
     "l'établissement responsable. Documents administratifs communiqués, réutilisables sans altération avec leur source et "
     "leur date (code des relations entre le public et l'administration, articles L321-1 et L322-1). Les autres régions "
     "n'y figurent pas, leur arrêté n'étant pas encore reçu."),
    (r"^categories_etablissements\.csv$", lambda m: "Effectifs salariés par catégorie d'établissement FINESS, "
                                                    "France et départements."),
    (r"^structures_principales\.csv$", lambda m: "Principales structures d'exercice salarié par profession, "
                                                 "France et départements (raisons sociales d'établissements)."),
    (r"^controle_appariement_finess\.csv$", lambda m: "Contrôle de l'appariement entre le RPPS et FINESS."),
    (r"^contexte_(com|epci|dep|reg)\.csv$", lambda m: f"Indicateurs de contexte INSEE par {NIVEAUX[m.group(1)]}."),
    (r"^inegalites\.csv$", lambda m: "Indicateurs d'inégalité de répartition par profession, niveau et mode."),
    (r"^lorenz\.csv$", lambda m: "Points des courbes de Lorenz (21 points par profession et niveau)."),
    (r"^correlations_contexte\.csv$", lambda m: "Corrélations entre densité de chaque profession et indicateurs "
                                                "de contexte."),
    (r"^correlations_professions_(epci|dep)\.csv$",
     lambda m: f"Matrice des corrélations de rang entre densités de professions, par {NIVEAUX[m.group(1)]}."),
    (r"^classes_densite\.csv$", lambda m: "Densités de professionnels par classe de densité de population."),
    (r"^tests_classes_densite\.csv$", lambda m: "Tests de différence entre classes de densité de population."),
    (r"^modeles_coefficients\.csv$", lambda m: "Coefficients des régressions de Poisson (effectif attendu)."),
    (r"^modeles_qualite\.csv$", lambda m: "Qualité d'ajustement des régressions de Poisson."),
    (r"^ecarts_attendu\.csv$", lambda m: "Effectif observé et attendu par intercommunalité et profession."),
    (r"^typologie_affectation\.csv$", lambda m: "Groupe de chaque intercommunalité dans les trois typologies (santé "
                                                 "mentale, santé, ensemble) et sa position sur les deux premiers axes "
                                                 "de l'analyse en composantes principales."),
    (r"^typologie_profils\.csv$", lambda m: "Profil de chaque groupe de la typologie (indice 100 = France)."),
    (r"^typologie_qualite\.csv$", lambda m: "Qualité de chaque typologie, nombre de groupes, silhouette et part des "
                                             "différences entre intercommunalités résumée par les groupes et les axes."),
    (r"^acp_inertie\.csv$", lambda m: "Valeur propre et part des différences entre intercommunalités résumée par chaque "
                                       "axe de l'analyse en composantes principales."),
    (r"^acp_charges\.csv$", lambda m: "Corrélation de chaque profession avec les premiers axes de l'analyse en "
                                       "composantes principales."),
    (r"^spatial\.csv$", lambda m: "Indices de Moran (ressemblance entre territoires voisins)."),
    (r"^tension\.csv$", lambda m: "Offres d'emploi France Travail rapportées aux professionnels."),
    (r"^diplomes_psychologues\.csv$", lambda m: "Diplômes déclarés par les psychologues."),
    (r"^concentration_revenu\.csv$", lambda m: "Indice de concentration des professionnels selon le niveau de vie "
                                               "des territoires, avec intervalle de confiance."),
    (r"^escalier_social\.csv$", lambda m: "Densité de professionnels par dixième de la population, territoires "
                                          "classés par niveau de vie croissant."),
    (r"^entonnoir\.csv$", lambda m: "Position de chaque territoire dans le diagramme en entonnoir."),
    (r"^entonnoir_resume\.csv$", lambda m: "Part des territoires et des habitants hors des limites de l'entonnoir."),
    (r"^entonnoir_limites\.csv$", lambda m: "Limites de l'entonnoir selon la population (pour tracer le graphique)."),
    (r"^public_cible\.csv$", lambda m: "Densité de certaines professions rapportée à leur public (moins de 15 ans, "
                                       "65 ans et plus), comparée à la densité par habitant."),
    (r"^public_cible_territoires\.csv$", lambda m: "Densité rapportée au public concerné, par territoire."),
    (r"^combinaisons\.csv$", lambda m: "Combinaisons de présence du médecin généraliste, du psychologue et du "
                                       "psychiatre, par commune et par intercommunalité."),
    (r"^composition_sante_mentale\.csv$", lambda m: "Psychologues et psychiatres par territoire, et nombre de "
                                                    "psychologues pour un psychiatre."),
    (r"^decomposition_theil\.csv$", lambda m: "Décomposition de l'indice de Theil entre et dans les départements, "
                                              "et entre et dans les classes de densité."),
    (r"^substitution\.csv$", lambda m: "Corrélations entre densités de paires de professions, brutes et à densité "
                                       "de population égale."),
    (r"^robustesse_gini\.csv$", lambda m: "Indice de Gini avec intervalle de confiance, et selon l'échelle "
                                          "géographique."),
    (r"^variance_niveaux\.csv$", lambda m: "Part de la variation de densité entre intercommunalités due aux "
                                           "départements."),
    (r"^moran_residus\.csv$", lambda m: "Indice de Moran des écarts à l'attendu des régressions de Poisson."),
    (r"^outre_mer\.csv$", lambda m: "Densités des départements d'outre-mer comparées à l'Hexagone."),
    (r"^accessibilite\.csv$", lambda m: "Distance au professionnel le plus proche, résumée par profession (part des "
                                        "habitants à plus de 5, 10, 20 et 30 km)."),
    (r"^accessibilite_communes\.csv$", lambda m: "Distance au professionnel le plus proche et accessibilité potentielle "
                                                 "à deux étapes, par commune."),
    (r"^accessibilite_epci\.csv$", lambda m: "Distance moyenne et accessibilité moyenne des habitants, par "
                                             "intercommunalité."),
    (r"^ombre_urbaine\.csv$", lambda m: "Intercommunalités peu dotées, distinguées selon leur accessibilité (ombre "
                                        "d'un pôle voisin ou désert)."),
    (r"^lisa\.csv$", lambda m: "Zones de désert et de concentration (indice de Moran local) par intercommunalité."),
    (r"^porte_offre\.csv$", lambda m: "Répartition des professionnels par grand secteur d'exercice selon la densité "
                                      "de population."),
    (r"^secteurs_conventionnels\.csv$", lambda m: "Libéraux par secteur conventionnel (secteur 1, secteur 2 avec ou "
                                                  "sans Optam, non conventionnés), par spécialité, en France, par "
                                                  "région et par département (Assurance Maladie)."),
    (r"^honoraires\.csv$", lambda m: "Honoraires des libéraux et dépassements réellement facturés, par spécialité, en "
                                     "France, par région et par département (Assurance Maladie, dernière année)."),
    (r"^age_professionnels\.csv$", lambda m: "Part des professionnels de 60 ans et plus, par profession, en France et "
                                             "par département, première et dernière année des séries de la DREES."),
    (r"^psychiatrie_hopital\.csv$", lambda m: "Psychiatrie à l'hôpital d'après la SAE de la DREES (lits, places, CMP, "
                                              "temps plein de psychiatres et psychologues, file active), par "
                                              "département, région et pour la France."),
    (r"^activites_particulieres\.csv$", lambda m: "Professionnels qui déclarent des activités sans soins à la "
                                                  "population (retirées des densités) ou pour un public particulier "
                                                  "(gardées), en France."),
    (r"^activites_particulieres_(\w+)\.csv$", lambda m: f"Mêmes activités comptées par territoire ({NIVEAUX.get(m.group(1), m.group(1))})."),
    (r"^exercice_multisites\.csv$", lambda m: "Part des professionnels qui exercent dans plusieurs communes ou "
                                              "intercommunalités."),
    (r"^liens_entre_intercommunalites\.csv$", lambda m: "Nombre de professionnels exerçant à la fois dans deux "
                                                        "intercommunalités (au moins 3)."),
    (r"^feminisation\.csv$", lambda m: "Part de femmes (civilité déclarée) par profession, en France et par "
                                       "département."),
    (r"^concordance_besoins\.csv$", lambda m: "Corrélation de rang entre deux indicateurs de besoin ou de recours aux "
                                               "soins en santé mentale, entre départements. Montre si les approches "
                                               "du besoin vont dans le même sens."),
    (r"^croisements\.csv$", lambda m: "Croisements départementaux entre une mesure de l'offre et un indicateur du "
                                       "profil ou du besoin, corrélation de rang brute et à densité de population "
                                       "égale, avec intervalles de confiance par bootstrap."),
    (r"^loi_inverse\.csv$", lambda m: "Indice de concentration des professionnels entre départements classés de la "
                                       "valeur la plus faible à la plus forte d'un indicateur de besoin. Négatif, "
                                       "l'offre est plus présente là où l'indicateur est faible."),
    (r"^sensibilite_accessibilite\.csv$", lambda m: "Sensibilité de l'accessibilité à deux étapes à la portée retenue, "
                                                     "comparée au calcul de référence à 20 km."),
    (r"^croisements_indicateurs\.csv$", lambda m: "Corrélation de rang entre chaque paire d'indicateurs de santé mentale, "
                                                   "de recours aux soins et de vulnérabilité, par département, avec "
                                                   "intervalle de confiance, correction de Benjamini-Hochberg et valeur "
                                                   "sans l'Île-de-France."),
    (r"^regressions_indicateurs\.csv$", lambda m: "Régression linéaire multiple de quelques indicateurs de santé mentale "
                                                   "sur des indicateurs sociaux, départements de l'Hexagone, avec et sans "
                                                   "l'Île-de-France, coefficients standardisés."),
    (r"^ald_departements\.csv$", lambda m: "Personnes en affection de longue durée (ALD) par département, pour les "
                                            "30 affections de la liste, d'après l'Assurance Maladie (régime général, "
                                            "Licence Ouverte). Effectifs arrondis à la dizaine et taux standardisés "
                                            "sur l'âge. Une ALD mesure une maladie reconnue, pas toutes les personnes "
                                            "malades."),
    (r"^allocataires_caf\.csv$", lambda m: "Bénéficiaires de l'AAH et de l'AEEH, et population couverte par le RSA, "
                                            "d'après la CAF (décembre), par intercommunalité, département et région, "
                                            "avec l'effectif, la population du territoire et la valeur rapportée. Les "
                                            "allocataires du régime agricole (MSA) ne sont pas comptés."),
    (r"^evolution_offre\.csv$", lambda m: "Effectif et densité de chaque année, par profession, pour la France, les "
                                           "régions et les départements, d'après les séries de démographie de la DREES "
                                           "(un professionnel compté une fois, dans le département de son activité "
                                           "principale) et les estimations de population de l'INSEE au 1er janvier."),
    (r"^evolution_explorer\.csv$", lambda m: "Effectif et population de chaque année depuis 2016, par département, pour "
                                              "toutes les séries de démographie de la DREES (colonne source, RPPS, ADELI "
                                              "jusqu'en 2024, SNDS pour les infirmiers libéraux, base Tous salariés pour "
                                              "les infirmiers salariés), données des trajectoires de la page Explorer."),
    (r"^evolution_offre_resume\.csv$", lambda m: "Évolution de la densité entre la première et la dernière année de "
                                                  "la période, par profession et territoire."),
    (r"^sensibilite_ile_de_france\.csv$", lambda m: "Corrélation de rang entre l'offre de santé mentale et les "
                                                     "indicateurs de besoin, avec tous les départements et sans ceux "
                                                     "d'Île-de-France, où les suicides sont nettement sous-déclarés."),
    (r"^quadrants\.csv$", lambda m: "Position de chaque département selon sa densité de professionnels et un "
                                    "indicateur de besoin, chacun comparé à sa médiane."),
    (r"^temps_acces_communes\.csv$", lambda m: "Temps de trajet médian en voiture des habitants de chaque commune "
                                              "jusqu'à la structure de psychiatrie ambulatoire (CMP) et au service "
                                              "d'urgences les plus proches, données des cartes des rapports "
                                              "départementaux (INSEE, distancier, Licence Ouverte)."),
    (r"^temps_acces\.csv$", lambda m: "Temps de trajet en voiture vers l'équipement ou le professionnel libéral le "
                                      "plus proche (INSEE), par France, région, département et intercommunalité."),
    (r"^comparaison_route\.csv$", lambda m: "Ressemblance, commune par commune, entre la distance à vol d'oiseau "
                                            "calculée ici et le temps de trajet de l'INSEE."),
    (r"^offre_besoin_lisa\.csv$", lambda m: "Moran local bivarié par département, indicateur de besoin du département "
                                             "et densité moyenne de ses voisins, pour les principales professions de "
                                             "santé mentale, 999 permutations, correction de Benjamini-Hochberg."),
    (r"^gwr_coefficients\.csv$", lambda m: "Régression géographiquement pondérée, coefficients locaux par "
                                            "intercommunalité de l'Hexagone (psychologues, psychiatres, généralistes)."),
    (r"^gwr_resume\.csv$", lambda m: "Régression géographiquement pondérée, résumé par profession (voisines, AICc, "
                                      "répartition des coefficients locaux, test de variation spatiale)."),
    (r"^parcours_activites\.csv$", lambda m: "Du répertoire aux densités. Pour chaque profession, personnes inscrites "
                                               "(quand la profession correspond à un libellé du RPPS), personnes avec une "
                                               "activité déclarée, sans lieu d'exercice, avec un lieu, n'exerçant qu'en "
                                               "téléconsultation ou sans soins à la population, et comptées dans les "
                                               "densités des territoires."),
    (r"^inscrits_sans_activite\.csv$", lambda m: "Personnes inscrites au RPPS (hors étudiants) et personnes ayant au "
                                                 "moins une activité déclarée, par profession. Sans activité déclarée ne "
                                                 "veut pas dire sans exercice, le fichier ne dit rien de ces inscrits."),
    (r"^concordance_effectifs\.csv$", lambda m: "Effectifs nationaux rapprochés des séries publiées par la DREES "
                                                "(démographie des professionnels de santé), avec le champ de chaque source "
                                                "et l'explication de l'écart."),
    (r"^concordance_effectifs_dep\.csv$", lambda m: "Effectifs par département rapprochés de ceux de la DREES, "
                                                    "ressemblance du classement et rapport entre les deux effectifs."),
    (r"^comparaison_apl\.csv$", lambda m: "Ressemblance entre l'accessibilité calculée ici et "
                                          "l'accessibilité potentielle localisée (APL) de la DREES."),
    (r"^sante_mentale_sante_publique_france\.csv$",
     lambda m: "Indicateurs de Santé publique France (portail Odissé), décès par suicide, gestes auto-infligés, "
               "Baromètre de Santé publique France, par département ou par région selon l'indicateur."),
    (r"^sante_mentale_assurance_maladie\.csv$",
     lambda m: "Personnes prises en charge pour troubles psychiques ou sous psychotropes, par département et région "
               "(Assurance Maladie, cartographie des pathologies). Mesure le recours aux soins, pas le besoin."),
]

# (motif sur le nom de colonne, description)
COLONNES = [
    (r"^mesure$", "Résultat recalculé (nombre, distance médiane, part à plus de 20 km, classement des départements, "
                  "éloignement selon le niveau de vie)."),
    (r"^toutes$", "Valeur avec toutes les structures recensées."),
    (r"^confirmees$", "Valeur avec les seules structures confirmées par une source indépendante de FINESS et du ROR."),
    (r"^conclusion_identique$", "Vrai quand la conclusion ne change pas (écart de moins d'un kilomètre ou de deux points, "
                                "corrélation de rang d'au moins 0,9, même sens et même netteté du lien)."),
    (r"^champ$", "Champ du double éloignement (adultes, enfants)."),
    (r"^part_sans_professionnel$", "Part des habitants dont l'intercommunalité ne compte aucun professionnel déclaré du champ."),
    (r"^part_loin_structure$", "Part des habitants à plus de 20 km de la structure du champ la plus proche."),
    (r"^part_double_eloignement$", "Part des habitants dans les deux situations à la fois."),
    (r"^habitants_double_eloignement$", "Nombre d'habitants dans les deux situations à la fois."),
    (r"^public$", "Public de la discipline, adultes (psychiatrie générale) ou enfants (psychiatrie infanto-juvénile)."),
    (r"^cmp_sae$", "CMP déclarés à la SAE par les établissements de la discipline."),
    (r"^file_active_ambulatoire$", "Patients vus au moins une fois dans l'année en ambulatoire, déclarés à la SAE."),
    (r"^etp_psychiatres$", "Psychiatres salariés en équivalents temps plein, déclarés à la SAE."),
    (r"^patients_par_cmp$", "File active ambulatoire rapportée au nombre de CMP déclarés."),
    (r"^etp_psychiatres_par_cmp$", "Psychiatres salariés en temps plein rapportés au nombre de CMP déclarés."),
    (r"^type_structure$", "Type de structure dont la distance est étudiée."),
    (r"^zone$", "Zone d'éloignement groupé (intercommunalité éloignée entourée d'intercommunalités éloignées), de "
                "proximité groupée, intercommunalité éloignée ou proche isolée, ou non significatif après correction."),
    (r"^(moran_global|p_moran_global)$", "Indice de Moran global des distances et sa p-valeur par permutations."),
    (r"^sae_(cmp|adultes|enfants)$", "CMP déclarés à la SAE (bordereau psychiatrie), en tout, en psychiatrie générale "
                                     "(adultes) ou infanto-juvénile (enfants et adolescents), dans le département ou la "
                                     "région du siège de l'établissement."),
    (r"^unites_ror$", "Unités déclarées comme CMP dans le ROR, avant leur réunion en lieux (plusieurs unités d'un même "
                      "CMP, ou des CMP déclarés à l'adresse de leur hôpital, ne font qu'une structure)."),
    (r"^ecart_relatif$", "Écart relatif entre les structures recensées ici (CMP ou CATTP selon le fichier) et celles "
                         "déclarées à la SAE."),
    (r"^classe_confirmation$", "Classe de confirmation montrée au lecteur, confirmée (nommée par une source "
                               "indépendante de FINESS et du ROR), recoupée par la statistique des hôpitaux (SAE, nombre de CATTP de "
                               "l'établissement ou places d'hôpital de jour du site, l'adresse n'est pas confirmée) ou à "
                               "vérifier (inscrite dans FINESS ou le ROR seulement). Vide quand le niveau n'est pas établi "
                               "pour ce type. Détail par source dans la colonne confirmation."),
    (r"^confirmation$", "Niveau de confirmation de la structure (vérifiée sur les sources de l'établissement, sur une "
                        "autre source publique, confirmée par la HAS (certification de l'hôpital ou évaluation de la "
                        "structure médico-sociale) ou par Sirene, concordante avec la SAE (nombre de CATTP de son établissement, "
                        "places d'hôpital de jour de son site), examinée à la main et maintenue, ou à vérifier). Vide pour les types qui ne sont pas "
                        "encore confrontés à ces listes."),
    (r"^role$", "Pour les CMPP, CAMSP, CSAPA et CAARUD, structure principale, antenne (établissement rattaché à un "
                "principal par la relation de budget de FINESS, ou désigné comme antenne par son nom) ou site "
                "supplémentaire (lieu du ROR au numéro d'une autre structure). En addictologie aussi consultation jeunes "
                "consommateurs, hébergement, milieu pénitentiaire, ou équipe de liaison sans lieu propre. Chaque ligne "
                "est un site d'accueil, compté pour les distances et la carte, sauf le milieu pénitentiaire et les "
                "équipes de liaison."),
    (r"^site_certification_has$", "Vrai quand un numéro FINESS de la structure est un site de la dernière "
                                  "certification HAS de son établissement dont le nom désigne son type, ou une "
                                  "structure médico-sociale évaluée par la HAS sous la catégorie de son type."),
    (r"^siret_sirene$", "Numéro SIRET de l'établissement Sirene correspondant."),
    (r"^enseigne_sirene$", "Enseigne de cet établissement dans Sirene."),
    (r"^adresse_sirene$", "Adresse de cet établissement dans Sirene."),
    (r"^verdict$", "Résultat de la vérification à la main d'une structure inscrite seulement dans les bases ou absente "
                   "de la liste de son établissement (existe, ou pas_un_cmp pour une unité rangée dans son type réel). "
                   "Vide sans vérification à la main."),
    (r"^examen$", "Constat et source de cette vérification à la main (site de l'établissement, Sirene, fiche "
                  "Santé.fr, appel téléphonique...)."),
    (r"^siret$", "Numéro SIRET de l'établissement Sirene."),
    (r"^enseigne$", "Enseigne de l'établissement dans Sirene."),
    (r"^date_creation$", "Date de création de l'établissement dans Sirene."),
    (r"^verification$", "Statut de la structure dans la liste vérifiée (confirmée par l'établissement, par une autre "
                        "source publique, ou seulement inscrite dans les bases), vide hors liste vérifiée."),
    (r"^source_verification$", "Source qui confirme la structure."),
    (r"^adresse_source_verification$", "Adresse de la page de cette source."),
    (r"^date_verification$", "Date de la vérification."),
    (r"^types$", "Types de structures vérifiés pour cet établissement."),
    (r"^sources$", "Sources consultées."),
    (r"^structures_etablissement$", "Structures confirmées par l'établissement."),
    (r"^structures_source_publique$", "Structures confirmées par une autre source publique."),
    (r"^structures_bases$", "Structures seulement inscrites dans FINESS ou le ROR."),
    (r"^a_reverifier$", "Vrai quand les inscriptions des bases ont changé depuis la vérification, qu'elle a plus d'un an, "
                        "ou qu'une structure de sa liste a été fermée depuis dans FINESS."),
    (r"^id_structure$", "Clé persistante de la structure, la même d'une version à l'autre même quand son numéro FINESS, son "
                        "nom ou son inscription au ROR changent, jamais réutilisée (règle dans pipeline/cles_structures.py)."),
    (r"^raison_reverification$", "Pourquoi l'établissement est à revérifier (inscriptions de FINESS ou du ROR modifiées, "
                                 "vérification de plus d'un an, structure de sa liste fermée depuis dans FINESS), vide sinon."),
    (r"^situation$", "Ce qu'est devenue l'inscription d'un verdict sans structure, d'après le numéro FINESS de sa clé "
                     "(numéro fermé dans FINESS, renommée sous le même numéro, même nom mais autre commune ou "
                     "autre gestionnaire, disparue des bases)."),
    (r"^structure_actuelle$", "Nom de la structure qui porte aujourd'hui le même numéro FINESS, quand l'inscription a été "
                              "renommée. Le verdict ne lui est pas reporté."),
    (r"^raison$", "Raison pour laquelle l'inscription n'est pas retenue."),
    (r"^ej$", "Numéro FINESS de l'entité juridique (l'hôpital ou l'association gestionnaire)."),
    (r"^dep_siege$", "Département du siège de l'établissement d'après la SAE."),
    (r"^ici_(cmp|adultes|enfants|cattp)$", "CMP (tous, pour adultes, pour enfants) ou CATTP recensés ici et rattachés à "
                                          "l'établissement."),
    (r"^sae_cattp$", "CATTP déclarés à la SAE, par l'établissement ou dans le territoire (département ou région du "
                     "siège de l'établissement)."),
    (r"^sae_cattp_(adultes|enfants)$", "CATTP déclarés à la SAE en psychiatrie générale (adultes) ou "
                                       "infanto-juvénile (enfants et adolescents)."),
    (r"^personnes$", "Personnes distinctes."),
    (r"^cattp$", "CATTP recensés ici (FINESS et ROR réunis)."),
    (r"^statut_cattp$", "Pour les CATTP, concorde (écart d'au plus 20 % ou d'un CATTP), moins ici, plus ici, ou "
                        "aucun CATTP déclaré à la SAE (l'hôpital y figure sans CATTP, ou n'y figure pas). Vide quand l'hôpital "
                        "n'a de CATTP ni ici ni à la SAE."),
    (r"^ecart$", "CMP recensés ici moins CMP déclarés à la SAE."),
    (r"^statut$", "Concorde (écart d'au plus 20 % ou d'un CMP), moins ici, plus ici, ou établissement absent de la SAE."),
    (r"^concordance$", "Niveau de concordance des sources, d'après l'écart avec la SAE (20 % et 40 %)."),
    (r"^base$", "Base relue (FINESS, ROR, ou les deux)."),
    (r"^constat$", "Ce qui a été constaté dans la base."),
    (r"^traitement$", "Ce qui en a été fait."),
    (r"^libelle_type$", "Libellé du type de structure de soins."),
    (r"^groupe$", "Groupe du type de lieu ou de la profession."),
    (r"^unite_ror$", "Nom de l'unité dans le ROR (vide pour une structure présente dans FINESS seul)."),
    (r"^secteur_psychiatrie$", "Code du secteur de psychiatrie dans l'arrêté de l'ARS (59G22, G pour la psychiatrie "
                               "générale des adultes, I pour la psychiatrie infanto-juvénile)."),
    (r"^type_secteur$", "Type de secteur de psychiatrie, générale (adultes) ou infanto-juvénile."),
    (r"^etablissement_responsable$", "Établissement de santé responsable du secteur, tel que l'arrêté le nomme."),
    (r"^finess_entite_juridique$", "Numéro FINESS de l'entité juridique de l'établissement responsable."),
    (r"^partie$", "Partie de commune quand une ville est découpée entre plusieurs secteurs (« LILLE NORD »), vide sinon."),
    (r"^code_arrete$", "Code de commune écrit dans l'arrêté, avant rattachement à la commune actuelle."),
    (r"^nom_arrete$", "Nom de commune écrit dans l'arrêté."),
    (r"^rattachement$", "Façon dont la commune actuelle a été retrouvée, par son code, par l'ancien code d'une commune "
                        "fusionnée, ou par son nom quand le code a changé depuis l'arrêté."),
    (r"^document$", "Document source, arrêté de l'agence régionale de santé."),
    (r"^date_document$", "Date du document source."),
    (r"^secteur$", "Code du secteur de psychiatrie quand le nom de la structure le cite (93G16, 31I01, G pour la psychiatrie générale, I pour la psychiatrie infanto-juvénile, Z pour un intersecteur), vide sinon. Il ne dit pas quelles communes le secteur dessert."),
    (r"^finess_rapproche$", "Numéro FINESS d'un CMP de FINESS rapproché de la structure du ROR par l'entité juridique et la commune."),
    (r"^finess_rapproche$", "Numéro FINESS d'un CMP de FINESS rapproché de la structure du ROR par l'entité juridique et la "
                            "commune."),
    (r"^entite_juridique$", "Numéro FINESS de l'entité juridique gestionnaire."),
    (r"^nom_commune$", "Nom de la commune."),
    (r"^commune_inscription$", "Commune d'inscription de la structure dans FINESS ou le ROR, quand son adresse se trouve "
                               "dans une commune voisine du même code postal, où elle est comptée (règle du 29 octobre "
                               "2026). Vide sinon."),
    (r"^adresse$", "Adresse de la structure (voie), quand elle est connue."),
    (r"^(latitude|longitude)$", "Coordonnées de la structure, en degrés (WGS 84)."),
    (r"^emplacement$", "Précision de l'emplacement, coordonnées de FINESS, du ROR, adresse géocodée (numéro, rue ou "
                       "lieu-dit), établissement de rattachement ou centre de la commune."),
    (r"^provenance$", "FINESS et ROR, FINESS seul ou ROR seul."),
    (r"^categories_ror$", "Codes des catégories du ROR des unités réunies dans le lieu (nomenclature TRE_R244 de l'ANS)."),
    (r"^categorie_finess$", "Code de catégorie FINESS de l'établissement, quand le lieu y est présent."),
    (r"^age_(min|max)$", "Âge minimal ou maximal des patients déclaré dans le ROR, en années."),
    (r"^lits_ror$", "Lits déclarés dans le ROR pour les unités de la structure."),
    (r"^unites_ror$", "Nombre d'unités du ROR réunies dans le lieu."),
    (r"^declares_partage_par$", "Nombre de structures de la commune, tous types confondus, qui partagent le numéro FINESS "
                                "de celle-ci. Le répertoire rattache une activité à l'établissement, pas à la structure, l'effectif de l'établissement "
                                "n'est alors attribué à aucune d'elles et figure une seule fois dans "
                                "declares_etablissements.csv. Vide quand la structure est seule sous son numéro."),
    (r"^structures_partageant$", "Nombre de structures de la commune, tous types confondus, qui partagent ce "
                                 "numéro FINESS."),
    (r"^declares_(.+)$", "Personnes déclarant au répertoire une activité sous le numéro FINESS de la structure et dans sa "
                         "commune, pour cette profession, quand la structure est seule sous ce numéro dans la commune. Vide "
                         "pour une structure sans numéro FINESS propre, et pour une structure qui partage son numéro avec "
                         "d'autres (voir declares_partage_par), l'effectif étant alors celui de l'établissement. Une "
                         "personne déclarée dans deux structures compte dans chacune, ces effectifs ne s'additionnent pas."),
    (r"^n_lieu_.+$", "Nombre de structures de ce type dans le territoire."),
    (r"^pour_100000_lieu_.+$", "Nombre de structures de ce type pour 100 000 habitants."),
    (r"^lieux_lieu_.+$", "Nombre de structures de ce type pour 100 000 habitants (FINESS et ROR réunis)."),
    (r"^dist_lieu_.+$", "Distance médiane des habitants à la structure la plus proche de ce type, en km, à vol d'oiseau."),
    (r"^finess_absorbes$", "Autres numéros FINESS du même lieu, enregistré plusieurs fois (sous deux entités juridiques "
                           "ou deux catégories) et compté une seule fois."),
    (r"^cmp$", "Centres médico-psychologiques distincts, tous publics (FINESS et ROR réunis)."),
    (r"^(adultes|enfants)$", "CMP qui accueillent les adultes, ou les enfants et adolescents (un CMP qui accueille les "
                             "deux compte dans les deux colonnes)."),
    (r"^les_deux$", "CMP qui accueillent à la fois les adultes et les enfants."),
    (r"^non_precise$", "CMP connus de FINESS seul, sans âges déclarés ni indice du public dans leur nom."),
    (r"^antennes$", "CMP dont le nom dit qu'il s'agit d'une antenne ou d'une permanence (en mairie, en CCAS, en maison "
                    "de santé), comptés parmi les CMP et signalés comme tels."),
    (r"^lieux_pour_100000$", "Nombre de structures de soins de ce type pour 100 000 habitants."),
    (r"^distance_mediane_km$", "Distance médiane des habitants à la structure la plus proche, en km, à vol d'oiseau, cherchée sur le même territoire (Hexagone, Corse ou département d'outre-mer), vide quand ce territoire n'en compte aucune."),
    (r"^part_plus_(20|30)_km$", "Part des habitants à plus de 20 ou 30 km de la structure la plus proche."),
    (r"^recensement_complet$", "Vrai quand ce type de structure est recensé dans au moins 90 % des départements. Faux, "
                               "les distances sont trop longues, la structure existant souvent sans être inscrite sous "
                               "ce type dans FINESS ou le ROR."),
    (r"^lieux_(les_deux|finess|ror)$", "Lieux présents dans les deux bases, dans FINESS seul ou dans le ROR seul."),
    (r"^part_departements$", "Part des départements (Mayotte écartée) où au moins une structure de ce type est recensée."),
    (r"^complet$", "Vrai quand le type est recensé dans au moins 90 % des départements et comparé entre territoires."),
    (r"^(lieux|reference|date_reference|objet|ecart)$", "Lieux recensés ici, chiffre publié, sa date, ce qu'il compte, "
                                                        "écart relatif."),
    (r"^ald$", "Numéro de l'affection dans la liste des ALD (1 à 30)."),
    (r"^resultat$", "Indicateur étudié par la régression."),
    (r"^champ$", "Départements retenus, Hexagone avec ou sans l'Île-de-France."),
    (r"^coef_standardise$", "Variation de l'indicateur étudié, en écarts-types, pour un écart-type de plus de l'indicateur "
                            "explicatif, les autres restant égaux."),
    (r"^vif$", "Facteur d'inflation de la variance, au-delà de 5 les indicateurs explicatifs se recouvrent trop."),
    (r"^r2$|^r2_ajuste$", "Part des écarts entre départements résumée par le modèle (ajustée du nombre d'indicateurs)."),
    (r"^variable_[ab]$", "Identifiant de l'indicateur comparé (voir les indicateurs de contexte)."),
    (r"^theme$", "Thème du croisement."),
    (r"^mesure$", "Mesure de l'offre croisée (« dens: » densité toutes activités, « dens_lib: » densité libérale, "
                  "« ctx: » indicateur de contexte), suivie de l'identifiant."),
    (r"^effectif_attendu_nb$", "Effectif attendu selon le modèle binomial négatif, qui tolère une variabilité plus forte "
                               "que le modèle de Poisson."),
    (r"^rapport_nb$", "Effectif observé rapporté à l'effectif attendu du modèle binomial négatif."),
    (r"^aic_(poisson|nb)$", "Critère d'information d'Akaike du modèle ({0}), plus bas pour un meilleur ajustement."),
    (r"^alpha_nb$", "Paramètre de surdispersion du modèle binomial négatif (0 pour un modèle de Poisson)."),
    (r"^retrait_(poisson|nb)$", "Nombre de territoires dont l'effectif est inférieur à la moitié de l'attendu, avec au "
                                "moins 5 professionnels attendus, selon le modèle ({0})."),
    (r"^retrait_communs$", "Territoires repérés en retrait par les deux modèles à la fois."),
    (r"^rho_rapports_poisson_nb$", "Corrélation de rang entre les rapports observé sur attendu des deux modèles."),
    (r"^portee_km$", "Portée de l'accessibilité à deux étapes, en kilomètres."),
    (r"^quart_bas_conserve$", "Part des intercommunalités du quart le moins accessible à 20 km qui y restent avec "
                              "cette portée."),
    (r"^rho_tous$", "Corrélation de rang avec tous les départements."),
    (r"^rho_sans_ile_de_france$", "Corrélation de rang sans les huit départements d'Île-de-France."),
    (r"^libelle_officiel$", "Libellé officiel de l'affection dans la liste des ALD."),
    (r"^secret$", "Vrai si l'effectif est inférieur à 10 et n'est pas publié par l'Assurance Maladie."),
    (r"^taux_standardise$", "Personnes en ALD pour 100 000 personnes protégées du régime général, taux standardisé sur l'âge."),
    (r"^mois$", "Mois de référence des données de la CAF (décembre)."),
    (r"^annee_debut$|^annee_fin$", "Première et dernière année de la période d'évolution."),
    (r"^effectif_debut$|^effectif_fin$", "Effectif de la profession au 1er janvier de la première et de la dernière année (DREES)."),
    (r"^densite_debut$|^densite_fin$", "Professionnels pour 10 000 habitants au 1er janvier de la première et de la dernière année."),
    (r"^evolution_densite$", "Variation relative de la densité entre les deux années (0,10 pour une hausse de 10 %)."),
    (r"^code$", "Code officiel du territoire (COG pour communes et départements, SIREN pour les EPCI). Un code "
                "commençant par C désigne une commune qui n'appartient à aucune intercommunalité."),
    (r"^nom$", "Nom du territoire."),
    (r"^population$|^pop$", "Population du territoire (référentiel Etalab, population municipale)."),
    (r"^n_(.+)$", "Nombre de personnes distinctes de la profession « {0} » qui déclarent exercer dans le territoire."),
    (r"^densite_(?!pop$|nationale$|mediane$|agregee$)(.+)$", "Nombre de professionnels « {0} » pour 10 000 habitants."),
    (r"^prof$", "Identifiant de la profession (voir professions.csv)."),
    (r"^libelle$", "Libellé de la profession."),
    (r"^professions$", "Identifiants des professions additionnées ici pour la comparaison avec la DREES."),
    (r"^libelle_rpps$", "Libellé de la profession dans le RPPS."),
    (r"^inscrits$", "Personnes inscrites au RPPS pour cette profession, hors étudiants."),
    (r"^avec_activite$", "Personnes ayant au moins une activité déclarée (effectif national publié ici)."),
    (r"^sans_activite_declaree$", "Personnes inscrites sans aucune activité déclarée. Le fichier ne donne ni lieu, "
                                  "ni âge, ni date pour elles, on ne sait donc pas si elles exercent."),
    (r"^part_sans_activite_declaree$", "Part des inscrits sans activité déclarée."),
    (r"^sans_lieu$", "Personnes dont aucune activité n'a de commune d'exercice (remplacements, exercice sans site "
                     "fixe). Comptées dans l'effectif national, pas dans les territoires."),
    (r"^avec_lieu$", "Personnes ayant au moins une activité avec une commune d'exercice."),
    (r"^a_distance_seulement$", "Personnes dont aucune activité localisée n'entre dans les densités et qui ont au "
                                "moins une activité pour une société de téléconsultation (soins à distance, déclarés "
                                "au siège de la société). Retirées des densités, comptées dans l'effectif national."),
    (r"^sans_soins_seulement$", "Personnes dont toutes les activités localisées sont sans soins à la population "
                                "(sièges, contrôle médical, industrie, recherche...), sans téléconsultation. Retirées "
                                "des densités, comptées dans l'effectif national."),
    (r"^dans_densites$", "Personnes ayant au moins une activité localisée de soins ou pour un public particulier, "
                         "comptées dans la densité d'au moins un territoire."),
    (r"^nous$", "Effectif calculé ici, personnes ayant au moins une activité dans l'extraction du RPPS."),
    (r"^date_rpps$", "Date de mise à jour de l'extraction du RPPS utilisée."),
    (r"^drees$", "Effectif publié par la DREES pour la dernière année disponible."),
    (r"^annee_drees$", "Année de l'effectif publié par la DREES."),
    (r"^champ_drees$", "Qui la DREES compte dans cette série (répertoire, date, âge, activité)."),
    (r"^ecart$", "Écart relatif entre l'effectif calculé ici et celui de la DREES (0,03 pour 3 % de plus)."),
    (r"^croissance_annuelle_drees$", "Croissance de l'effectif entre les deux dernières années publiées par la DREES."),
    (r"^attendu_a_la_date$", "Effectif de la DREES prolongé jusqu'à la date de l'extraction du RPPS, à croissance "
                             "constante. Comparaison pertinente seulement quand la DREES utilise aussi le RPPS."),
    (r"^ecart_a_l_attendu$", "Écart relatif entre l'effectif calculé ici et l'effectif prolongé."),
    (r"^explication$", "Explication de l'écart par la différence de champ ou de date."),
    (r"^fichier_drees$", "Nom du classeur de la DREES lu."),
    (r"^source$", "Page du jeu de données chez le producteur."),
    (r"^departements$", "Nombre de départements comparés."),
    (r"^rang_spearman$", "Corrélation de rang de Spearman entre les effectifs départementaux calculés ici et ceux de "
                         "la DREES (1 pour un classement identique)."),
    (r"^rapport_(median|p10|p90|min|max)$", "Rapport entre l'effectif calculé ici et celui de la DREES, par "
                                            "département ({0})."),
    (r"^dep_(min|max)$", "Code du département où le rapport est le plus bas (min) ou le plus haut (max)."),
    (r"^note$", "Différence de définition entre les deux comptages départementaux."),
    (r"^mode$", "Mode d'exercice, all (tous), lib (libéral), sal (salarié), aut (autre, bénévole)."),
    (r"^n$", "Nombre de personnes distinctes."),
    (r"^id$", "Identifiant de la profession."),
    (r"^groupe$", "Groupe de professions, niveau de détail sous la famille."),
    (r"^famille$", "Famille, « Santé mentale » ou « Santé » (dans les fichiers de la typologie, sm, sante ou tout)."),
    (r"^axe([12])$", "Coordonnée de l'intercommunalité sur l'axe {0} de l'analyse en composantes principales."),
    (r"^axe$", "Numéro de l'axe de l'analyse en composantes principales."),
    (r"^valeur_propre$", "Valeur propre de l'axe (variance qu'il résume, sur des données centrées et réduites)."),
    (r"^part_inertie$", "Part des différences entre intercommunalités résumée par l'axe."),
    (r"^correlation$", "Corrélation de la profession avec l'axe, de -1 à +1."),
    (r"^classes$", "Nombre de groupes retenu."),
    (r"^silhouette$", "Silhouette moyenne de la partition, de -1 à 1, sous 0,25 les groupes sont peu séparés."),
    (r"^part_inertie_classes$", "Part des différences entre intercommunalités expliquée par les groupes."),
    (r"^part_inertie_axes_1_2$", "Part des différences résumée par les deux premiers axes."),
    (r"^variables$", "Nombre de professions utilisées."),
    (r"^nature$", "profession (chaque personne y figure une fois), qualification (qualification complémentaire "
                  "d'un médecin, non additive) ou perimetre_elargi (salariés d'un établissement psychiatrique, "
                  "non additif)."),
    (r"^base$", "Pour le périmètre élargi, profession d'origine."),
    (r"^niveau$", "Niveau géographique (FR, com, epci, dep, reg)."),
    (r"^secteur$", "Secteur d'activité, libellé d'affichage."),
    (r"^secteur_libelle_officiel$", "Secteur d'activité, libellé officiel de la nomenclature RPPS."),
    (r"^secteur_1$", "Libéraux conventionnés en secteur 1 (tarif de la Sécurité sociale)."),
    (r"^secteur_2$", "Libéraux conventionnés en secteur 2 (dépassements possibles), avec ou sans Optam."),
    (r"^secteur_2_optam$", "Libéraux en secteur 2 ayant adhéré à l'Optam (dépassements encadrés)."),
    (r"^secteur_2_sans_optam$", "Libéraux en secteur 2 sans Optam."),
    (r"^non_conventionnes$", "Libéraux non conventionnés."),
    (r"^liberaux$", "Total des libéraux, conventionnés ou non."),
    (r"^part_depassements$", "Part des libéraux pouvant pratiquer des dépassements d'honoraires (secteur 2 et non "
                             "conventionnés), non calculée sous 5 libéraux."),
    (r"^part_depassements_libres$", "Part des libéraux en secteur 2 sans Optam ou non conventionnés."),
    (r"^profession_sante$", "Spécialité, libellé de l'Assurance Maladie."),
    (r"^hono_sans_depassement_totaux$", "Honoraires sans dépassement des libéraux de la spécialité, en euros."),
    (r"^depassements_totaux$", "Dépassements d'honoraires facturés par les libéraux de la spécialité, en euros, vide "
                               "sous secret statistique."),
    (r"^depassements_moyens$", "Dépassements moyens par libéral de la spécialité, en euros, vide sous secret statistique."),
    (r"^taux_depassement_s2$", "Dépassements des libéraux de secteur 2 en part de leurs honoraires sans dépassement, "
                               "tel que publié, vide sous secret statistique ou sans libéral de secteur 2."),
    (r"^plus_60$", "Professionnels de 60 ans et plus (DREES)."),
    (r"^somme_tranches$", "Somme des tranches d'âge, contrôle face à l'effectif publié."),
    (r"^part_60$", "Part des professionnels de 60 ans et plus."),
    (r"^nombre$", "Nombre brut (lits, places, CMP, équivalents temps plein ou patients selon l'indicateur)."),
    (r"^categorie$", "Catégorie d'établissement, libellé d'affichage."),
    (r"^categorie_libelle_officiel$", "Catégorie d'établissement, libellé officiel de la nomenclature FINESS."),
    (r"^agregat$", "Agrégat de catégories, libellé d'affichage."),
    (r"^agregat_libelle_officiel$", "Agrégat de catégories, libellé officiel de la nomenclature FINESS."),
    (r"^rs$", "Raison sociale de l'établissement."),
    (r"^commune$", "Commune de l'établissement."),
    (r"^activites_avec_finess$", "Activités salariées portant un numéro FINESS."),
    (r"^appariees$", "Activités dont le numéro FINESS est retrouvé dans FINESS."),
    (r"^taux$", "Part des activités appariées."),
    (r"^effectif$", "Effectif (personnes distinctes, somme sur les territoires pour inegalites.csv)."),
    (r"^effectif_attendu$", "Effectif attendu compte tenu du profil sociodémographique (régression de Poisson). "
                            "Ce n'est pas une mesure du besoin."),
    (r"^densite_nationale$", "Somme des effectifs des territoires du niveau rapportée à la population, pour 10 000 habitants. "
                             "Un professionnel qui exerce dans plusieurs territoires y compte une fois par territoire, "
                             "c'est la moyenne calculée comme les territoires et non la densité de la France, dont "
                             "l'effectif (chaque personne une fois) est dans effectifs_france.csv."),
    (r"^moyenne$|^mediane$|^p10$|^p90$", "Statistique de la densité pour 10 000 habitants entre territoires."),
    (r"^rapport_p90_p10$", "Rapport entre le 9e et le 1er décile des densités."),
    (r"^gini$", "Indice de Gini de la répartition rapportée à la population (0 égalité, 1 concentration totale)."),
    (r"^theil$", "Indice de Theil de la répartition rapportée à la population."),
    (r"^territoires_sans_professionnel$", "Nombre de territoires sans aucun professionnel."),
    (r"^part_population_sans_professionnel$", "Part de la population vivant dans un territoire sans professionnel."),
    (r"^x$|^y$", "Coordonnées de la courbe de Lorenz (part cumulée de la population, part cumulée des professionnels)."),
    (r"^variable$", "Indicateur de contexte ou variable du modèle."),
    (r"^rho_spearman$", "Corrélation de rang de Spearman."),
    (r"^ic95_bas$|^ic95_haut$", "Bornes de l'intervalle de confiance à 95 % (bootstrap)."),
    (r"^p$", "p-valeur (indicative, les données sont un recensement)."),
    (r"^q_bh$", "q-valeur après correction de Benjamini-Hochberg."),
    (r"^r_pearson_pondere_log$", "Corrélation de Pearson pondérée par la population, sur le logarithme de la densité."),
    (r"^force$", "Force du lien (négligeable, faible, modérée, forte)."),
    (r"^classe$", "Classe de densité de population ou groupe de la typologie."),
    (r"^territoires$", "Nombre de territoires."),
    (r"^densite_mediane$", "Densité médiane des territoires de la classe."),
    (r"^densite_agregee$", "Effectif total de la classe rapporté à sa population, pour 10 000 habitants."),
    (r"^kruskal_H$", "Statistique du test de Kruskal-Wallis."),
    (r"^epsilon2$", "Taille d'effet epsilon² du test de Kruskal-Wallis."),
    (r"^biserial_extremes$", "Corrélation bisériale de rang entre classes extrêmes."),
    (r"^p_mann_whitney_extremes$", "p-valeur du test de Mann-Whitney entre classes extrêmes."),
    (r"^coef$", "Coefficient (logarithme du rapport de taux pour une variable standardisée)."),
    (r"^rapport_de_taux$", "Rapport de taux, exponentielle du coefficient."),
    (r"^erreur_std$", "Erreur standard robuste."),
    (r"^z$|^t$", "Statistique de test."),
    (r"^vif$", "Facteur d'inflation de la variance."),
    (r"^pseudo_r2$", "Part de la déviance expliquée par le modèle."),
    (r"^dispersion$", "Paramètre de dispersion de Pearson (1 si la variance suit le modèle de Poisson)."),
    (r"^observe$", "Densité observée pour 10 000 habitants."),
    (r"^attendu$", "Densité attendue pour 10 000 habitants."),
    (r"^manque$", "Effectif attendu moins effectif observé."),
    (r"^rapport$", "Effectif observé divisé par l'effectif attendu (1 conforme au profil, 0,5 deux fois moins)."),
    (r"^indice_vs_national$", "Indice de densité, 100 pour la moyenne des intercommunalités."),
    (r"^moran_I$", "Indice de Moran."),
    (r"^p_permutation$", "p-valeur par permutations."),
    (r"^diplome$", "Libellé du diplôme."),
    (r"^annee$", "Année des données (pour le fichier des diplômes, année d'obtention, non disponible dans l'extraction publique actuelle)."),
    (r"^psychologues$", "Nombre de psychologues."),
    (r"^dep$", "Code du département."),
    (r"^code_actuel$", "Code officiel de la commune dans le découpage en vigueur (après fusions de communes)."),
    (r"^epci$", "Code SIREN de l'intercommunalité."),
    (r"^reg$", "Code de la région."),
    (r"^indicateur$", "Identifiant de l'indicateur (voir les indicateurs de contexte)."),
    (r"^top$", "Code de la catégorie dans la cartographie des pathologies de l'Assurance Maladie."),
    (r"^libelle_officiel$", "Libellé officiel de la nomenclature de l'Assurance Maladie."),
    (r"^patients$", "Nombre de personnes prises en charge (tous âges, tous sexes)."),
    (r"^prevalence_brute_pct$", "Patients rapportés à la population couverte, en %."),
    (r"^prevalence_standardisee_pct$", "Prévalence standardisée sur la structure d'âge de la France (méthode "
                                       "directe), en %. Vide si le secret statistique masque trop de cases d'âge."),
    (r"^groupes$", "Découpage utilisé pour la décomposition (départements ou classes de densité)."),
    (r"^entre$|^dans$", "Part de l'indice de Theil entre les groupes ou dans les groupes."),
    (r"^part_entre$", "Part de l'inégalité qui tient aux écarts entre groupes."),
    (r"^prof_(a|b)$", "Identifiant de chacune des deux professions comparées."),
    (r"^rho$", "Corrélation de rang de Spearman."),
    (r"^gini_(com|epci|dep|reg)$", "Indice de Gini calculé à l'échelle indiquée."),
    (r"^part_entre_departements$", "Part de la variation du logarithme de la densité expliquée par le département."),
    (r"^moran_residus$", "Indice de Moran des écarts à l'attendu."),
    (r"^hexagone$", "Densité pour 10 000 habitants dans l'Hexagone."),
    (r"^(97\d)$", "Densité pour 10 000 habitants dans le département d'outre-mer {0}."),
    (r"^distance_km$", "Distance à vol d'oiseau (km) entre le centre de la commune et celui de la commune la plus "
                       "proche où exerce au moins un professionnel, sur le même territoire (Hexagone, Corse ou département d'outre-mer), "
                       "vide quand ce territoire n'en compte aucun."),
    (r"^part_population_dans_la_commune$", "Part des habitants qui ont au moins un professionnel dans leur commune."),
    (r"^distance_(mediane|moyenne)_km$", "Distance médiane ou moyenne des habitants au professionnel le plus proche (km), sans "
     "traverser la mer, la moyenne sur les seuls habitants dont le territoire compte au moins un de ces professionnels."),
    (r"^part_population_a_plus_de_(\d+)_km$", "Part des habitants à plus de {0} km du professionnel le plus proche."),
    (r"^accessibilite$", "Accessibilité potentielle à deux étapes, en professionnels pour 10 000 habitants."),
    (r"^accessibilite_liberale$", "Même calcul limité aux professionnels libéraux, pour comparer avec l'APL de la DREES (cinq professions seulement)."),
    (r"^equipement$", "Type d'équipement ou de professionnel libéral de la base permanente des équipements (INSEE)."),
    (r"^temps_(moyen|median)_min$", "Temps de trajet {0} en voiture (minutes) vers l'équipement le plus proche, "
                                    "pondéré par la population, à tous les niveaux."),
    (r"^part_population_a_plus_de_(\d+)_min$", "Part des habitants à plus de {0} minutes de route de l'équipement le "
                                               "plus proche."),
    (r"^part_population_non_calculee$", "Part des habitants pour lesquels l'INSEE ne calcule pas de temps de trajet."),
    (r"^rho_communes$", "Corrélation de rang entre les deux indicateurs, calculée sur les communes."),
    (r"^rho_epci$", "Corrélation de rang entre les deux indicateurs, calculée sur les intercommunalités."),
    (r"^rho_densite_epci$", "Corrélation de rang entre la densité simple et l'APL, sur les intercommunalités."),
    (r"^annee_apl$", "Millésime de l'APL publiée par la DREES."),
    (r"^intercommunalites$", "Nombre d'intercommunalités comparées."),
    (r"^communes$", "Nombre de communes comparées."),
    (r"^categorie$", "ombre_urbaine (peu doté mais bonne accessibilité), desert (peu doté et faible accessibilité), "
                     "intermediaire ou hors_quart_bas."),
    (r"^z$", "Statistique centrée réduite de l'indice de Moran local."),
    (r"^I$", "Indice de Moran local du territoire."),
    (r"^type$", "Première lettre, valeur du territoire haute (H) ou basse (L), seconde lettre, valeur de ses voisins. Dans "
                "lisa.csv, la même densité. Dans offre_besoin_lisa.csv, l'indicateur du département puis l'offre des voisins."),
    (r"^q$", "q-valeur après correction de Benjamini-Hochberg."),
    (r"^zone$", "Zone repérée au-delà du hasard (q < 0,05). Dans lisa.csv, desert, concentration, isole_haut ou "
                "isole_bas. Dans offre_besoin_lisa.csv, le type (HL, indicateur élevé et offre faible alentour, HH, LL, LH). "
                "non_significatif sinon."),
    (r"^coef_niveau_de_vie$", "Coefficient local du niveau de vie médian, en écarts-types de la densité (en logarithme) "
                              "pour un écart-type de niveau de vie, à densité de population égale."),
    (r"^coef_densite_pop$", "Coefficient local de la densité de population (en logarithme)."),
    (r"^net$", "Vrai si le coefficient local dépasse le seuil ajusté des tests locaux (da Silva et Fotheringham 2016)."),
    (r"^r2_local$", "Part des écarts expliquée par la régression locale, pondérée par les poids des voisines."),
    (r"^t$", "Rapport du coefficient local à son erreur standard."),
    (r"^voisines$", "Nombre d'intercommunalités voisines retenues par le noyau, choisi par le critère AICc."),
    (r"^parametres_effectifs$", "Nombre effectif de paramètres de la régression géographiquement pondérée."),
    (r"^aicc_gwr$|^aicc_ols$", "Critère AICc de la régression pondérée et de la régression ordinaire, plus bas est meilleur."),
    (r"^r2_gwr$", "Part des écarts entre intercommunalités résumée par la régression pondérée."),
    (r"^coef_global_niveau_de_vie$", "Coefficient du niveau de vie dans la régression ordinaire sur toute l'Hexagone."),
    (r"^coef_local_(q1|mediane|q3)$", "Premier quartile, médiane et troisième quartile des coefficients locaux."),
    (r"^part_(positif|negatif)_net$", "Part des intercommunalités où le coefficient local est positif (négatif) et net."),
    (r"^seuil_t_ajuste$", "Seuil des tests locaux, ajusté au nombre effectif de paramètres."),
    (r"^p_variation_(niveau_de_vie|densite_pop)$", "Test de variation spatiale du coefficient, par 49 permutations des "
                                                   "positions. Faible, le lien change vraiment d'une région à l'autre."),
    (r"^groupe$", "Grand secteur d'exercice."),
    (r"^part$", "Part dans la classe de territoires."),
    (r"^personnes$", "Nombre de personnes distinctes."),
    (r"^categorie$", "Catégorie du secteur d'activité, soins (soins à la population), public_particulier (soins ou "
                     "prévention pour un public particulier, gardés dans les densités), a_distance (téléconsultation, "
                     "soins à distance déclarés au siège de la société, retirés des densités et comptés à part) ou "
                     "sans_soins (sans soins à la population, retirés des densités et comptés à part). Liste dans "
                     "config.SECTEURS_CATEGORIES."),
    (r"^categorie_libelle$", "Libellé de la catégorie."),
    (r"^sans_autre_lieu_de_soins$", "Personnes comptées dans aucune densité, car toutes leurs activités avec un lieu d'exercice sont de cette catégorie (même définition que a_distance_seulement et sans_soins_seulement de parcours_activites.csv)."),
    (r"^part_profession$", "Part de la profession en France."),
    (r"^plusieurs_(communes|epci)$", "Personnes exerçant dans au moins deux communes ou intercommunalités."),
    (r"^part_plusieurs_(communes|epci)$", "Part de ces personnes."),
    (r"^communes_moyennes$", "Nombre moyen de communes d'exercice par personne."),
    (r"^epci_(a|b)$", "Code des deux intercommunalités reliées."),
    (r"^nom_(a|b)$", "Nom des deux intercommunalités reliées."),
    (r"^femmes$", "Nombre de femmes (civilité déclarée « Madame »)."),
    (r"^part_femmes$", "Part de femmes."),
    (r"^public$", "Public concerné par la profession."),
    (r"^densite_nationale_cible$", "Professionnels en France pour 10 000 personnes du public concerné."),
    (r"^gini_(population|public)$", "Indice de Gini, rapporté à la population entière ou au public concerné."),
    (r"^rho_classements$", "Corrélation de rang entre densité par habitant et densité par personne du public."),
    (r"^part_public_sans_professionnel$", "Part du public vivant dans un territoire sans ce professionnel."),
    (r"^population_cible$", "Nombre de personnes du public concerné dans le territoire."),
    (r"^densite_cible$", "Professionnels pour 10 000 personnes du public concerné."),
    (r"^(medecin_generaliste|psychologue|psychiatre)$", "Présence (True) ou absence (False) de la profession."),
    (r"^part_population$", "Part de la population."),
    (r"^psychiatres$", "Nombre de psychiatres."),
    (r"^psychologues_par_psychiatre$", "Nombre de psychologues pour un psychiatre (vide sans psychiatre)."),
    (r"^quadrant$", "besoin+offre- (indicateur au-dessus de la médiane, densité au-dessous), et ainsi de suite."),
    (r"^mediane_(densite|indicateur)$", "Médiane des départements utilisée comme seuil."),
    (r"^valeur$", "Valeur de l'indicateur, dans l'unité indiquée par le dictionnaire des indicateurs."),
    (r"^ic_(bas|haut)$", "Borne de l'intervalle de confiance à 95 % (indicateurs d'enquête)."),
    (r"^couverture_ages$", "Part des patients retrouvée dans les cases d'âge (contrôle du secret statistique)."),
    (r"^offres$", "Nombre d'offres d'emploi en cours."),
    (r"^professionnels$", "Nombre de professionnels en exercice."),
    (r"^offres_pour_100_professionnels$", "Offres pour 100 professionnels."),
    (r"^rho_partiel_densite$", "Corrélation partielle de rang à densité de population égale (effet ville retiré)."),
    (r"^ic95_(bas|haut)_partiel$", "Borne de l'intervalle de confiance à 95 % de la corrélation partielle."),
    (r"^p_partiel$", "p-valeur de la corrélation partielle (test t)."),
    (r"^q_bh_partiel$", "q-valeur de la corrélation partielle après correction de Benjamini-Hochberg."),
    (r"^indice_concentration$", "Indice de concentration selon le niveau de vie (0 égalité, positif en faveur des "
                                "territoires aisés)."),
    (r"^decile$", "Dixième de la population, de 1 (territoires les plus modestes) à 10 (les plus aisés)."),
    (r"^niveau_de_vie_(min|max)$", "Niveau de vie médian le plus bas ou le plus haut des territoires de la tranche (€)."),
    (r"^densite$", "Professionnels pour 10 000 habitants."),
    (r"^statut$", "Position dans l'entonnoir, -2 nettement en dessous, -1 en dessous, 0 proche de la moyenne, 1 au-dessus, "
                  "2 nettement au-dessus."),
    (r"^effectif_au_taux_national$", "Effectif qu'aurait le territoire avec la densité nationale."),
    (r"^part_hors_95$", "Part des territoires hors des limites à 95 %."),
    (r"^part_nettement_en_dessous$", "Part des territoires sous la limite basse à 99,8 %."),
    (r"^part_population_nettement_en_dessous$", "Part des habitants vivant dans ces territoires."),
    (r"^(bas|haut)_(95|998)$", "Limite de l'entonnoir en densité pour 10 000 habitants (95 % ou 99,8 %)."),
]


def _decrire_colonne(col, ctx):
    if col in ctx:
        return ctx[col]
    for motif, desc in COLONNES:
        m = re.match(motif, col)
        if m:
            return desc.format(*m.groups()) if m.groups() else desc
    return "Description manquante, à compléter dans pipeline/dictionnaire.py."


def ecrire(out: Path, indicateurs=None):
    if indicateurs is None:
        indicateurs = [{"id": c[0], "label": c[1], "unite": c[2], "source": "INSEE"} for c in config.CONTEXTE]
    ctx = {d["id"]: f"{d['label']} ({d['unite']}), source {d['source']}."
           + (f" Publié pour les {', '.join(d['niveaux'])}, vide aux autres niveaux." if d.get("niveaux") else "")
           for d in indicateurs}
    L = ["# Dictionnaire des colonnes", "",
         "Tous les fichiers CSV utilisent le point-virgule comme séparateur et la virgule comme séparateur "
         "décimal, pour s'ouvrir directement dans un tableur.", ""]
    for p in sorted(out.glob("*.csv")):
        nom = re.sub(r"_odbl\.csv$", ".csv", p.name)
        desc = next((f(re.match(m, nom)) for m, f in FICHIERS if re.match(m, nom)), "Description manquante.")
        if p.name.endswith("_odbl.csv"):
            desc += (" Partie issue de données sous licence ODbL (Assurance Maladie), diffusée sous la même licence "
                     "(partage à l'identique).")
        local = dict(ctx)
        if p.name == "porte_offre.csv":
            local.update({"groupe": "Grand secteur d'exercice (libéral, hôpital public, privé, médico-social...).",
                          "classe": "Classe de densité de population de l'intercommunalité, ou Ensemble."})
        if p.name == "secteurs_psychiatrie.csv":
            local.update({"commune": "Code de la commune actuelle (code officiel géographique) rattachée au secteur.",
                          "type": "Type de secteur dans l'arrêté (G psychiatrie générale, I psychiatrie infanto-juvénile)."})
        if p.name == "libelles.csv":
            desc = "Table de correspondance entre libellés officiels et libellés d'affichage."
            local.update({"source": "Nomenclature d'origine.", "code": "Code dans la nomenclature, s'il existe.",
                          "libelle_origine": "Libellé officiel de la nomenclature.",
                          "libelle_affichage": "Libellé affiché au lecteur.",
                          "statut": "Statut de validation.", "remarque": "Justification ou point de vigilance."})
        with open(p, encoding="utf-8-sig") as f:
            cols = f.readline().rstrip("\r\n").split(";")
        L += [f"## {p.name}", "", desc, "", "| Colonne | Description |", "|---|---|"]
        if p.name.startswith("correlations_professions_"):
            L += [f"| `{cols[0]}` | Identifiant de la profession en ligne. |",
                  "| `<profession>` | Corrélation de rang de Spearman entre la densité de la profession en ligne et "
                  "celle de la profession en colonne. |", ""]
            continue
        vus = set()
        for c in cols:
            d = _decrire_colonne(c, local)
            cle = re.sub(r"^(n|densite)_.+$", r"\1_*", c) if c not in local and re.match(r"^(n|densite)_(?!pop$|nationale$|mediane$|agregee$)", c) else c
            if cle in vus:
                continue
            vus.add(cle)
            if cle != c:
                c, d = cle.replace("*", "<profession>"), d.replace(f"« {c.split('_', 1)[1]} »", "<profession>")
            L.append(f"| `{c}` | {d} |")
        L.append("")
    (out / "dictionnaire_des_colonnes.md").write_text("\n".join(L), encoding="utf-8")
