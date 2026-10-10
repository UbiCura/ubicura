# Vérification de la fiabilité, 5 octobre 2026

Étape 0 de la version de base (demande de Lucas du 4 octobre 2026 au soir). Chaque chiffre publié doit être juste, et l'on doit pouvoir dire de quelle source et de quel calcul il sort. Cette note consigne ce qui a été vérifié, contre quelle référence, et ce qui a été corrigé.

Méthode. Trois niveaux de contrôle.
1. **Recompte indépendant.** Relire le fichier brut sans le code du pipeline et retrouver le chiffre publié.
2. **Comparaison avec le producteur.** Rapprocher le chiffre publié de la valeur que publie le producteur ou un organisme officiel (DREES, INSEE, Assurance Maladie), avec un lien et une date.
3. **Contrôle automatique.** Quand c'est possible, la comparaison est refaite à chaque exécution et consignée dans le journal, donc dans la page « Méthode et données ».

## 1. Effectifs de professionnels

### Le chiffre de 77 000 psychologues

Il correspond très probablement à la série de la DREES, **77 047 psychologues au 1er janvier 2024**, tirée du répertoire Adeli (inscrits actifs occupés, âgés de moins de 62 ans), dernière année publiée avant le passage des psychologues au RPPS ([jeu de données de la DREES](https://data.drees.solidarites-sante.gouv.fr/explore/dataset/la-demographie-des-professionnels-de-sante-depuis-2012/information/), classeur « Psychologues ADELI 2012-2024 », Licence Ouverte).

Le projet compte **80 765 psychologues**, personnes ayant au moins une activité déclarée dans l'extraction du RPPS mise à jour le 3 octobre 2026, sans limite d'âge. Ce chiffre a été retrouvé à l'identique par un recompte indépendant du fichier brut.

Ce que contient le fichier RPPS pour les psychologues.

| | Personnes |
|---|---|
| Inscrits au RPPS | 119 818 |
| dont au moins une activité déclarée (chiffre publié) | 80 765 |
| dont une activité avec un lieu (commune) | 77 577 |
| Inscrits sans aucune activité déclarée | 39 053 |

Les 39 053 inscrits sans activité n'ont dans le fichier ni lieu, ni mode d'exercice, ni âge, ni date. On ne peut pas dire qu'ils n'exercent pas (retraite, autre métier, congé, ou activité non déclarée), seulement qu'aucune activité n'est déclarée.

Écart avec la DREES (+4,8 %). Les deux comptages ne portent ni sur la même date (janvier 2024 contre octobre 2026), ni sur le même répertoire, ni sur les mêmes âges. La série de la DREES progressait de 3,8 % par an entre 2023 et 2024. Prolongée à octobre 2026, elle donnerait environ 85 000 psychologues de moins de 62 ans. Notre chiffre, sans limite d'âge, est donc plutôt bas que haut. Hypothèse à confirmer quand la DREES publiera la série RPPS des psychologues, une partie des inscrits d'Adeli n'a pas déclaré d'activité au RPPS lors de la bascule. Ce point reste ouvert et sera signalé comme tel.

### Tableau de concordance, toutes professions

Le tableau est désormais produit à chaque exécution (`pipeline/concordance.py`, source `pipeline/sources/drees_demographie.py`), publié dans la page « Méthode et données » et dans `concordance_effectifs.csv` et `concordance_effectifs_dep.csv`. Valeurs de l'exécution du 5 octobre 2026.

« Écart à la tendance » compare notre effectif à celui de la DREES prolongé jusqu'au 3 octobre 2026 à sa croissance de la dernière année. « Rang » est la corrélation de rang entre départements (1 pour un classement identique).

| Profession | Ici | DREES | Année | Écart | Écart à la tendance | Rang |
|---|---|---|---|---|---|---|
| Médecins, toutes spécialités | 248 177 | 242 185 | 2026 | +2,5 % | +0,9 % | 0,996 |
| Médecins généralistes | 103 795 | 100 974 | 2026 | +2,8 % | +2,1 % | 0,997 |
| Psychiatres, dont de l'enfant | 16 377 | 16 199 | 2026 | +1,1 % | +0,1 % | 0,997 |
| Pédiatres | 9 666 | 9 848 | 2026 | −1,8 % | −4,4 % (1) | 0,995 |
| Gynécologues | 8 197 | 8 017 | 2026 | +2,2 % | +0,3 % | 0,994 |
| Ophtalmologues | 6 216 | 6 119 | 2026 | +1,6 % | −0,1 % | 0,976 |
| Cardiologues | 7 886 | 7 704 | 2026 | +2,4 % | +0,9 % | 0,970 |
| Dermatologues | 3 734 | 3 698 | 2026 | +1,0 % | +1,0 % | 0,991 |
| Chirurgiens-dentistes | 50 127 | 48 690 | 2026 | +3,0 % | +1,3 % | 0,999 |
| Masseurs-kinésithérapeutes | 112 564 | 111 384 | 2026 | +1,1 % | −1,2 % | 0,998 |
| Sages-femmes | 27 004 | 26 428 | 2026 | +2,2 % | +0,2 % | 0,996 |
| Pharmaciens | 75 873 | 75 335 | 2026 | +0,7 % | −0,1 % | 0,995 |
| Pédicures-podologues | 14 959 | 14 638 | 2026 | +2,2 % | +1,1 % | 0,998 |
| Psychologues | 80 765 | 77 047 | 2024 (2) | +4,8 % | | 0,993 |
| Psychomotriciens | 18 658 | 15 453 | 2024 (2) | +20,7 % | | 0,991 |
| Orthophonistes | 31 334 | 25 161 | 2024 (2) | +24,5 % | | 0,997 |
| Orthoptistes | 7 120 | 6 410 | 2024 (2) | +11,1 % | | 0,981 |
| Ergothérapeutes | 17 864 | 15 651 | 2024 (2) | +14,1 % | | 0,990 |
| Diététiciens | 17 875 | 17 369 | 2024 (2) | +2,9 % | | 0,995 |
| Audioprothésistes | 6 262 | 4 952 | 2024 (2) | +26,5 % | | 0,969 |
| Manipulateurs en électroradiologie | 35 510 | 31 772 | 2024 (2) | +11,8 % | | 0,986 |
| Opticiens-lunetiers | 41 017 | 44 238 | 2024 (2) | −7,3 % | | 0,989 |
| Techniciens de laboratoire | 56 339 | 45 406 | 2024 (2) | +24,1 % | | 0,994 |
| Infirmiers libéraux | 132 122 | 98 854 | 2023 (3) | +33,7 % | | 0,998 |
| Infirmiers salariés | 437 105 | 508 790 | 2023 (4) | −14,1 % | | 0,988 |

(1) La DREES range la génétique médicale (371 médecins) avec la pédiatrie. En ajoutant nos 367 généticiens, l'écart à la tendance tombe à environ −0,8 %.
(2) Adeli, actifs occupés de moins de 62 ans au 1er janvier 2024. Champs, répertoires et dates différents, l'écart n'est pas une erreur mais n'est pas non plus réductible à un seul facteur. Le classement des départements est très proche (0,97 à 0,997).
(3) SNDS, infirmières ayant eu une activité remboursée dans l'année. Le RPPS compte toute personne ayant une activité libérale déclarée, active ou non.
(4) Base Tous salariés de l'INSEE, poste principal au 31 décembre. Le RPPS sous-enregistre les infirmières salariées (la DREES le juge encore insuffisant pour décrire cette profession).

**Conclusion.** Pour les treize professions et spécialités que la DREES compte aussi à partir du RPPS, nos effectifs sont à moins de 2,1 % de la série officielle prolongée à la même date, et les départements sont classés de façon quasi identique (rang 0,97 à 0,999). Les écarts des autres professions s'expliquent par le changement de répertoire, l'âge et la date, et sont décrits sur le site.

Par département, la DREES place chaque professionnel dans le département de son activité la plus récente, alors qu'ici une personne compte dans chaque département où elle a une activité de soins avec un lieu, sans les activités sans soins à la population (téléconsultation, industrie...). D'où des rapports locaux qui s'écartent de 1, par exemple l'Eure-et-Loir pour les pharmaciens (0,62), où 141 pharmaciens travaillent dans l'industrie du médicament.

### Erreurs trouvées et corrigées

1. **764 médecins classés en « spécialité non renseignée ».** Ils n'ont pas de spécialité ordinale mais une compétence exclusive (751 en gynécologie médicale ou gynécologie médicale et obstétrique, 8 en urologie, 5 en obstétrique). La DREES les classe dans leur spécialité. Correction dans `rpps.specialites_medecins`, la spécialité ordinale d'abord, à défaut la compétence exclusive, puis la qualification PAC.
2. **Libellés des diplômes d'études spécialisées de 2017 non reconnus.** « Gynéco-obstétrique et Gynéco médicale option... » (182 médecins) et « Méd cardiovasculaire opt... » (245 médecins) tombaient dans « autre spécialité ». Motifs corrigés dans `config.SPECIALITES_MEDECINS`.
3. **Chirurgiens pédiatriques comptés comme pédiatres.** Le motif « pediatr » prenait aussi la chirurgie pédiatrique et l'anesthésie pédiatrique (66 médecins). Motif restreint à « pédiatrie ».
4. Tests unitaires ajoutés pour ces libellés (`test_classement`).

Effet. Gynécologues de 7 265 à 8 197 (écart avec la DREES de −9,4 % à +2,2 %), cardiologues de 7 641 à 7 886, spécialité non renseignée de 795 à 4.

Vérifié sans erreur. Les 18 625 étudiants (internes remplaçants) sont bien écartés. Les 67 080 lignes « Acteur du système de santé caractérisé par un rôle » sont bien exclues. Le total des médecins est identique au recompte indépendant (248 177).

## 2. Population et indicateurs de l'INSEE

- **Population.** Le référentiel d'Etalab (paquet decoupage-administratif, version 6.0.0 du 9 mars 2026) donne la population municipale 2023 de l'INSEE, identique commune par commune (Paris 2 103 778 dans les deux). Le référentiel était lu en « dernière version » sans que la version soit consignée. Corrigé, la version est résolue par le registre npm, figée dans l'adresse et notée dans le journal. Nouveau contrôle automatique, population du référentiel et population INSEE identiques par département.
- **Indicateurs.** Pour la Seine-Saint-Denis et la Creuse, les indicateurs de l'INSEE publiés ici (densité, âges, chômage, cadres, ouvriers, familles monoparentales, revenu médian, pauvreté, emploi, salaire, diplôme, logements suroccupés, logement social, minima sociaux) sont identiques à ceux du [dossier complet de l'INSEE](https://www.insee.fr/fr/statistiques/2011101?geo=DEP-93) (consulté le 5 octobre 2026). La part des emplois précaires est elle aussi exacte (14,73 % en Seine-Saint-Denis, tableau ACT T2), mais son libellé « CDD, intérim » était trop étroit, car l'INSEE y range aussi les emplois aidés, l'apprentissage et les stages. Libellé corrigé en « Part des emplois à durée limitée », explication complétée.
- Précision de lecture, « part des minima sociaux » est la part des minima sociaux dans le revenu disponible des ménages (Filosofi), pas la part des personnes qui en perçoivent.

## 3. Santé publique France (Odissé)

Décès par suicide, personnes hospitalisées et passages aux urgences pour geste auto-infligé. Pour les 101 départements, la valeur publiée est identique à celle du fichier brut de la dernière année (2023 pour les suicides, 2024 pour les deux autres). Les seuls codes du fichier non repris sont Saint-Barthélemy et Saint-Martin, qui ne sont pas des départements.

## 4. DREES

- **Indicateurs sociaux départementaux** (protection de l'enfance et handicap, six indicateurs). Valeurs publiées identiques au fichier brut pour tous les départements. Les codes propres à la DREES (Rhône hors métropole 69D, métropole de Lyon 69M, Collectivité européenne d'Alsace 6AE, Corse 20R) ne sont pas mélangés avec les départements, qui gardent leur propre valeur (69, 67, 68).
- **SAE, psychiatrie.** 50 621 lits d'hospitalisation à temps plein en psychiatrie fin 2024 dans le fichier brut (adultes, enfants et pénitentiaire), pour environ 50 600 dans [« Les établissements de santé », édition 2026 de la DREES](https://drees.solidarites-sante.gouv.fr/sites/default/files/2026-07/ES%202026%20-%20Fiche%2002%20-%20Les%20capacit%C3%A9s%20d%E2%80%99accueil%20en%20hospitalisation%20compl%C3%A8te%20et%20partielle.pdf) (recul de 7 100 lits, soit −12,3 %, depuis 2013), avec la même définition.

## 5. Assurance Maladie (ODbL)

- **Cartographie des pathologies.** La prévalence brute calculée ici (patients / population) est identique au champ « prev » publié par data.ameli (Creuse 7,341 %, Paris 4,313 %, Seine-Saint-Denis 3,557 %, maladies psychiatriques, 2024). La prévalence standardisée sur l'âge, calculée ici, va dans le sens attendu (la Creuse, plus âgée, baisse à 6,75 %, la Seine-Saint-Denis, plus jeune, monte à 3,97 %).
- **Secteurs conventionnels.** Les codes 1 à 5 correspondent bien aux libellés de l'Assurance Maladie (1 secteur 1, 2 secteur 2, 3 et 4 secteur 2 avec ou sans Optam, 5 non conventionnés). Part des psychiatres libéraux pouvant pratiquer des dépassements, recalculée à la main, Paris 73,1 %, Seine-Saint-Denis 26,9 %, Creuse 40 % (5 libéraux), identique aux valeurs publiées.

## 6. Statistiques

- **Densités et indice de Gini.** Recalculés de façon indépendante à partir des CSV publiés (effectifs et populations des départements) pour les psychologues, les psychiatres, les généralistes et les infirmiers. Identiques aux valeurs publiées (Gini des psychologues entre départements 0,17251 dans les deux cas).
- **Patients en affection longue durée sans médecin traitant.** Identiques au fichier brut de l'Assurance Maladie dans les 100 départements (Mayotte exclue comme pour les autres données de l'Assurance Maladie).
- Les autres indices (concentration selon le revenu, corrélations partielles, modèles) sont couverts par les tests unitaires sur cas connus (30 tests).
- **Temps de trajet (INSEE).** 5,5 % des habitants couverts (Hexagone, Martinique, La Réunion) vivent à plus de 30 minutes d'un service d'urgences selon le distancier de l'INSEE résumé ici. La DREES publiait environ 6 % (près de 4 millions de personnes) fin 2015, avec une autre méthode. Ordre de grandeur cohérent, pas une comparaison exacte. Le fichier brut (16 Go) n'est pas conservé, seul son résumé par commune l'est, ce qui empêche un recompte indépendant après coup.

- **APL de la DREES.** Relecture indépendante des classeurs 2024, identique à la lecture du pipeline (3,728 consultations par habitant en moyenne pour les généralistes, 34 890 communes). Moyennes nationales recalculées selon la méthode de la DREES (professionnels de 65 ans ou moins, population standardisée), identiques aux valeurs publiées, médecins généralistes 3,3, infirmiers 154,8, sages-femmes 22,2, masseurs-kinésithérapeutes 123,2, chirurgiens-dentistes 61,5 ([communiqué de la DREES](https://drees.solidarites-sante.gouv.fr/communique-de-presse-jeux-de-donnees/jeux-de-donnees/260722-accessibilite-aux-soins-de-premier-recours-en-2024)). Le pipeline utilise pour les généralistes l'indicateur tous âges, comme son propre calcul d'accessibilité, et n'affiche que des corrélations de rang, aucune valeur d'APL. Libellés de la ligne des sources corrigés.

## 7. Point de méthode à trancher, la moyenne nationale de comparaison

Les territoires sont comparés à une « moyenne nationale » (couleurs des cartes, « deux fois moins que la moyenne », position par quarts, atlas). Cette moyenne est calculée avec toutes les personnes ayant une activité en France, y compris les remplacements sans lieu et les activités sans soins à la population. Or ces activités sont retirées des effectifs des territoires. Les deux chiffres ne sont donc pas calculés de la même façon.

| Profession | Moyenne « France » actuelle | Moyenne des départements | Écart | Départements sous la moyenne, actuelle / cohérente |
|---|---|---|---|---|
| Médecins généralistes | 15,2 | 13,6 | −10,5 % | 83 / 51 |
| Pharmaciens | 11,1 | 9,8 | −11,6 % | 84 / 57 |
| Infirmiers | 80,5 | 74,1 | −8,0 % | 61 / 43 |
| Masseurs-kinésithérapeutes | 16,5 | 15,2 | −7,5 % | 69 / 60 |
| Psychologues | 11,8 | 12,1 | +2,5 % | 68 / 73 |
| Psychiatres | 2,29 | 2,30 | +0,3 % | 80 / 80 |

Pour les généralistes, 17 départements changent de couleur sur la carte selon la référence choisie. Les psychiatres et les psychologues sont peu touchés.

**Décidé par Lucas le 5 octobre 2026 et corrigé.** Chaque territoire est comparé à la moyenne des territoires du même niveau, calculée comme eux (somme des effectifs des territoires rapportée à la population), nommée « moyenne des départements » ou « moyenne des intercommunalités ». Rapports nationaux et territoriaux, cartes, escalier social, typologie, entonnoir et atlas utilisent cette référence (`analyses.moyenne_territoires`, test `test_moyenne_territoires`). Le nombre de professionnels en France (80 765 psychologues) reste le chiffre national affiché, avec sa définition. La typologie, l'entonnoir et les cartes nationales calculaient déjà leur référence ainsi, seul leur libellé « moyenne nationale » a changé.

## 8. Reste à faire

- Table « d'où vient chaque chiffre » ajoutée à la page « Méthode et données », à relire par Lucas.
- Inscrits sans activité déclarée, publiés par profession (`inscrits_sans_activite.csv` et page méthode), décision de Lucas du 5 octobre 2026.
