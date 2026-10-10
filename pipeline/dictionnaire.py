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
    (r"^effectifs_(com|epci|dep|reg)_(all|lib|sal)\.csv$",
     lambda m: f"Effectifs et densités par {NIVEAUX[m.group(1)]}, {MODES[m.group(2)]}. Une ligne par territoire, "
               "une paire de colonnes par profession."),
    (r"^effectifs_france\.csv$", lambda m: "Effectifs nationaux par profession et mode d'exercice, en personnes "
                                           "distinctes, activités sans lieu d'exercice comprises."),
    (r"^professions\.csv$", lambda m: "Liste des professions, qualifications et comptages du périmètre élargi."),
    (r"^secteurs\.csv$", lambda m: "Effectifs par secteur d'activité déclaré au RPPS, France et départements."),
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
                                               "activité déclarée, sans lieu d'exercice, avec un lieu, exerçant seulement "
                                               "sans soins à la population et comptées dans les densités des territoires."),
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
    (r"^sans_soins_seulement$", "Personnes dont toutes les activités localisées sont sans soins à la population "
                                "(sièges, contrôle médical, industrie, recherche, téléconsultation...). Retirées des "
                                "densités, comptées dans l'effectif national."),
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
    (r"^densite_nationale$", "Somme des effectifs des territoires rapportée à la population, pour 10 000 habitants."),
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
                       "proche où exerce au moins un professionnel."),
    (r"^part_population_dans_la_commune$", "Part des habitants qui ont au moins un professionnel dans leur commune."),
    (r"^distance_(mediane|moyenne)_km$", "Distance médiane ou moyenne des habitants au professionnel le plus proche (km)."),
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
                     "prévention pour un public particulier, gardés dans les densités) ou sans_soins (retirés des "
                     "densités et comptés à part). Liste dans config.SECTEURS_CATEGORIES."),
    (r"^categorie_libelle$", "Libellé de la catégorie."),
    (r"^dont_teleconsultation$", "Personnes dont au moins une de ces activités est exercée pour une société de téléconsultation."),
    (r"^sans_autre_lieu_de_soins$", "Personnes comptées dans aucune densité, car toutes leurs activités avec un lieu d'exercice sont de cette catégorie (même définition que sans_soins_seulement de parcours_activites.csv)."),
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
    (r"^statut$", "Position dans l'entonnoir, -2 nettement en dessous, -1 en dessous, 0 dans la norme, 1 au-dessus, "
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
