# Proposer une base de données

Chercheurs, observatoires, agences, associations ou simples lecteurs peuvent proposer une base de données publique qui éclairerait l'offre de soins ou les besoins de la population. Chaque proposition est examinée, et la décision est indiquée sur la page « À venir » du site.

## Ce qui est attendu de la base

- **Données publiques**, sous une licence ouverte (Licence Ouverte, ODbL), ou avec l'accord écrit du producteur.
- **Un producteur identifié**, administration, agence ou organisme de recherche.
- **Un niveau géographique** utile, commune, intercommunalité, département ou région.
- **Un accès stable**, une adresse ou une interface (API) qui permet de récupérer la base à chaque mise à jour, sans manipulation à la main.
- **Une documentation**, définition des variables, années couvertes, limites connues.

## Ce qu'il faut indiquer

1. Le nom du jeu de données et le lien vers sa page chez le producteur.
2. Le producteur et la licence.
3. Le niveau géographique et les années couvertes.
4. La question à laquelle la base aiderait à répondre.
5. Les limites connues (sous-déclaration, champ incomplet, années manquantes), avec leur source si possible.

## Comment l'envoyer

Par une demande sur ce dépôt, avec le modèle « Proposer une base de données », ou par courriel à l'adresse du projet indiquée sur la page « À propos » du site.

## Décrire soi-même la base

Une base peut aussi être décrite par un court fichier JSON placé dans le dossier `complements/`. Il dit où trouver la base (jeu de data.gouv ou adresse stable), à quel niveau géographique la lire et quels indicateurs en tirer. Le format est documenté en tête de `pipeline/sources/complements.py` et dans `complements/README.md`. Une base ainsi décrite entre dans toutes les analyses après vérification.

## Comment une proposition est examinée

1. Vérification de la licence, de l'accès et de la documentation.
2. Lecture des fichiers et comparaison avec les valeurs publiées par le producteur.
3. Repérage des limites (sous-déclaration, champ, années manquantes), écrites avec leur source là où la donnée est montrée.
4. Intégration, ou réponse motivée si la base n'est pas retenue.

## Règles communes

- Seuls des agrégats sont publiés, jamais de données sur des personnes.
- Aucune donnée n'est aspirée depuis un annuaire ou un site qui ne la publie pas en données ouvertes.
- Les libellés des nomenclatures sont présentés avec un vocabulaire respectueux des personnes (table `pipeline/libelles.csv`).
