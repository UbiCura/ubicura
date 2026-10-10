# Note, secteurs d'activité du RPPS qui ne soignent pas la population

Note préparée le 4 octobre 2026 pour décision de Lucas.

**Décision de Lucas (4 octobre 2026).** Tout garder, mais de façon identifiable. Trois catégories, soins à la population (chiffres principaux), public particulier (gardé dans les densités et repérable), sans soins à la population (retiré des densités et compté à part par territoire, les personnes restant dans l'effectif national). Le secteur « Ministère » est rangé en public particulier, sauf pour les médecins (sans soins), parce qu'il réunit surtout des infirmiers et psychologues de l'Éducation nationale, des infirmiers de PMI et des services sociaux des départements, et pour les médecins surtout de l'administration. Liste dans `config.SECTEURS_CATEGORIES`.

## Le constat

Le répertoire RPPS rattache chaque activité à un secteur (cabinet, hôpital, centre de santé, organisme de sécurité sociale...). Certains secteurs ne correspondent pas à des soins offerts aux habitants, et leurs professionnels sont souvent déclarés à l'adresse d'un siège. Ils gonflent alors la densité du territoire où se trouve ce siège.

La téléconsultation a déjà été retirée des comptages par territoire. Malgré cela, Paris compte encore 32,5 médecins généralistes pour 10 000 habitants, contre 15,2 en France. Paris réunit 3,1 % de la population, mais par exemple 41 % des généralistes des organismes de sécurité sociale, 52 % de ceux de la recherche et la totalité des 1 255 généralistes du secteur « Autres structures du SSA », tous déclarés dans un seul établissement, « SSA Paris ».

Les chiffres ci-dessous comptent des personnes distinctes par secteur, en France, d'après l'exécution du 4 octobre 2026. Une même personne peut exercer dans plusieurs secteurs.

## Groupe 1, activités sans soins à la population

Contrôle médical de l'Assurance Maladie, assurances, industrie et distribution du médicament, conseil, recrutement, ordres professionnels, sièges d'établissements, recherche, agences d'intérim (déclarées à l'adresse de l'agence), et le secteur « Autres structures du SSA » déclaré en un seul lieu.

| Secteur (libellé du RPPS) | Généralistes | Psychiatres | Psychologues | Infirmiers | Part des généralistes du secteur déclarés à Paris |
|---|---|---|---|---|---|
| Organisme de Sécurité Sociale | 1 018 | 16 | 42 | 1 114 | 41 % |
| Autres structures du SSA | 1 255 | 10 | 20 | 1 911 | 100 % |
| Assurances Privées | 176 | 0 | 26 | 275 | 16 % |
| Fab. Exploit. Import. Méd. DM | 170 | 6 | 8 | 152 | 14 % |
| Répart. Distrib. Médicament DM | 7 | 0 | 0 | 236 | 86 % |
| Répart. Distrib. Médicament DM et Fab. Exploit. Im | 8 | 0 | 1 | 178 | 12 % |
| Com/Marketing/Consulting/Media | 14 | 0 | 33 | 58 | 50 % |
| Recrutement & gestion RH | 0 | 0 | 129 | 2 |  |
| Ordre de professionnels de santé | 0 | 0 | 10 | 4 |  |
| Siège social d'ES répertoriés dans FINESS | 60 | 19 | 69 | 59 | 30 % |
| Recherche | 66 | 8 | 63 | 383 | 52 % |
| Entreprise d'intérim | 0 | 0 | 2 | 426 |  |

## Groupe 2, soins ou prévention pour un public particulier

Médecine du travail et prévention en entreprise, santé scolaire et universitaire, services de l'État (médecins et psychologues de l'Éducation nationale, ARS, MDPH, OFII...), collectivités, pompiers, hôpitaux militaires, don du sang, enseignement (instituts de formation).

| Secteur (libellé du RPPS) | Généralistes | Psychiatres | Psychologues | Infirmiers | Part des généralistes du secteur déclarés à Paris |
|---|---|---|---|---|---|
| Ministère & Serv. déconcentrés | 1 669 | 42 | 1 364 | 7 059 | 13 % |
| Prév. et Soins en Entreprise | 733 | 13 | 178 | 1 266 | 8 % |
| Services de Prévention et de Santé au Travail | 48 | 0 | 26 | 1 725 | 8 % |
| Entreprises industrielles et tertiaires hors indus | 405 | 12 | 53 | 655 | 26 % |
| Etablissement scolaire & universitaire | 549 | 16 | 1 091 | 5 587 | 8 % |
| Etab. d'enseignement | 54 | 10 | 293 | 3 817 | 11 % |
| Collectivités Territoriales | 346 | 23 | 169 | 364 | 1 % |
| Incendies et secours | 330 | 3 | 3 | 242 | 4 % |
| Services départementaux d'incendie et de secours | 32 | 0 | 2 | 604 | 0 % |
| Hôpitaux militaires | 323 | 36 | 41 | 1 861 | 0 % |
| Centre de transfusion sanguine | 311 | 1 | 12 | 1 516 | 3 % |

Le secteur « Ministère & Serv. déconcentrés » est mixte. Pour les psychologues, il s'agit surtout des psychologues de l'Éducation nationale, qui voient des élèves mais sont déclarés à l'adresse de l'académie ou de la direction départementale. Pour les généralistes, il s'agit de médecins de l'éducation, des centres de gestion de la fonction publique, des MDPH, des ARS ou de l'OFII.

## Effet d'un retrait des groupes 1 et 2 (simulation)

| Profession | Paris, pour 10 000 habitants, aujourd'hui | Paris, sans les groupes 1 et 2 | Baisse au milieu des autres départements |
|---|---|---|---|
| Médecins généralistes | 32,5 | 22,8 | 1,8 % |
| Psychiatres | 10,6 | 10,4 | 0,0 % |
| Psychologues | 36,1 | 34,9 | 1,6 % |
| Infirmiers | 122,6 | 108,4 | 2,0 % |

Ailleurs, l'effet reste faible, sauf quelques cas. La Lozère perd 14 % de ses généralistes (médecins-conseils et médecins de l'État à Mende), les Hauts-de-Seine 11 %. Le Cher perd 8 % de ses psychologues (psychologues de l'Éducation nationale).

## Le secteur non renseigné

18 841 généralistes ont au moins une activité sans secteur renseigné. Ces activités n'ont presque jamais de lieu d'exercice, elles ne changent donc pas les comptages par territoire. Elles restent dans l'effectif national.

## Proposition

1. **Groupe 1, retirer des comptages par territoire**, comme la téléconsultation, en gardant les personnes dans l'effectif national et en les décrivant dans un encadré « Activités sans soins à la population » des rapports nationaux, avec un fichier CSV.
2. **Groupe 2, garder dans les comptages**, parce que ces professionnels voient des personnes, mais le signaler. Le compter à part pourrait se discuter pour la médecine du travail et la santé scolaire, qui ne reçoivent pas tout public.
3. **Secteur « Ministère »**, garder pour les psychologues (Éducation nationale) et le retirer pour les médecins, ou le garder pour tous en le signalant. Un tri par raison sociale serait plus fin mais plus fragile d'une mise à jour à l'autre.
4. Liste des secteurs retenus dans `config.py`, modifiable sans toucher au reste du code, avec un contrôle dans le journal (nombre d'activités et de personnes retirées).

## Questions pour Lucas

- Retirer le groupe 1 des comptages par territoire, oui ou non ?
- Le groupe 2, tout garder, ou retirer certains secteurs (lesquels) ?
- Le secteur « Ministère », garder pour les psychologues seulement, pour tous, ou pour personne ?
