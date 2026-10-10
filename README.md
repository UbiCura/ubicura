# Ubi Cura, offre de soins et santé mentale en France

Ce dépôt réunit le code qui récupère les bases publiques sur les professionnels de santé, compte les professionnels par territoire, les croise avec le profil des populations et produit des rapports, un atlas et un site statique. La santé mentale est traitée à part, puis l'offre de soins générale.

## Installation

Python 3.10 ou plus récent. Dans un terminal, depuis ce dossier.

Sous Windows (PowerShell)

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:PYTHONUTF8=1
```

Sous Linux ou macOS

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Prévoir 8 Go de mémoire vive et environ 5 Go d'espace disque. La première exécution télécharge environ 2 Go, puis lit région par région les temps de trajet de l'INSEE (16 Go au total, un seul fichier régional à la fois sur le disque, environ 3 Go d'espace temporaire). Elle dure de 30 minutes à une heure selon la connexion. Les suivantes réutilisent les fichiers déjà téléchargés et durent une dizaine de minutes.

## Utilisation

```
python run.py                  # exécution complète
python run.py --hors-ligne     # sans réseau, avec les fichiers déjà présents
python run.py --rafraichir     # force le retéléchargement de toutes les sources
python run.py --sans-spatial   # saute l'analyse spatiale (plus rapide)
python run.py --sans-pdf       # n'imprime pas les rapports nationaux en PDF
python run.py --inspecter      # affiche les colonnes des fichiers téléchargés
python -m pipeline.site        # reconstruit seulement le site à partir des derniers résultats
```

Une source absente ou cassée est consignée dans le journal et n'arrête pas le reste. Seuls le répertoire RPPS et le référentiel géographique sont indispensables. Si une source change de format, `python run.py --inspecter` liste les colonnes trouvées, et le motif correspondant s'ajuste dans `pipeline/config.py` ou `pipeline/sources/`.

Les offres d'emploi de France Travail sont facultatives. Elles demandent un compte développeur sur francetravail.io et deux variables d'environnement.

```powershell
$env:FT_CLIENT_ID="..."
$env:FT_CLIENT_SECRET="..."
```

## Sources

Toutes les sources sont récupérées par API ou par une adresse stable, avec la date de mise à jour annoncée par le producteur. Producteur, licence et lien de chaque source sont repris dans la page « Méthode et données » du site et à la fin de chaque rapport.

| Source | Producteur | Licence | Ce qu'elle apporte |
|---|---|---|---|
| RPPS, activités, savoir-faire, diplômes | Agence du numérique en santé | Licence Ouverte | Professionnels de santé, lieu et mode d'exercice, secteur, spécialité des médecins |
| FINESS (Finess+, sinon flux historique) | ANS, ministère chargé de la santé | Licence Ouverte | Catégorie des établissements (CMP, CMPP, IME, EHPAD...) |
| Découpage administratif | Etalab, d'après l'INSEE | Licence Ouverte | Communes, intercommunalités, départements, régions, populations |
| Dossier complet | INSEE | Licence Ouverte | Âges, revenus, pauvreté, emploi, diplômes, logement, structure familiale |
| Temps d'accès aux équipements | INSEE | Licence Ouverte | Temps de trajet par la route jusqu'au professionnel ou à la structure la plus proche |
| Contours des communes, ADMIN EXPRESS COG CARTO PE | IGN | Licence Ouverte | Voisinages, distances, cartes |
| Cartographie des pathologies | Assurance Maladie | ODbL | Personnes prises en charge pour un trouble psychique, psychotropes |
| Secteurs conventionnels, patients sans médecin traitant | Assurance Maladie | ODbL | Dépassements d'honoraires possibles, accès au médecin traitant |
| Suicides, gestes auto-infligés, Baromètre | Santé publique France (Odissé) | Licence Ouverte | Indicateurs moins dépendants de l'offre, enquête déclarative régionale |
| Accessibilité potentielle localisée (APL) | DREES | Licence Ouverte | Validation de l'accessibilité calculée ici |
| Statistique annuelle des établissements (SAE) | DREES | Licence Ouverte | Psychiatrie à l'hôpital, lits, places, CMP, temps plein |
| Indicateurs sociaux départementaux | DREES | Licence Ouverte | Protection de l'enfance, handicap |
| Offres d'emploi (facultatif) | France Travail | Conditions de l'API | Tension sur le marché du travail |

Les données de l'Assurance Maladie sont sous licence ODbL (partage à l'identique). Elles et ce qui en dérive sont isolées dans les fichiers suffixés `_odbl`. Les données intégrées à l'atlas, qui les contiennent, sont aussi sous ODbL.

Les activités sans soins à la population (téléconsultation, contrôle médical, industrie, recherche...) sont retirées des densités et comptées à part, et les activités pour un public particulier (médecine du travail, santé scolaire...) restent comptées mais repérables. La liste est dans `config.SECTEURS_CATEGORIES`.

## Analyses produites

- Effectifs et densités par commune, intercommunalité, département et région, par profession et mode d'exercice.
- Inégalités de répartition (Gini, Theil, courbes de Lorenz), avec intervalles de confiance et sensibilité à l'échelle.
- Liens avec le profil des territoires (corrélations de rang avec intervalle par bootstrap, correction de Benjamini-Hochberg, corrélations partielles à densité de population égale), gradient selon le niveau de vie et indice de concentration.
- Effectif attendu compte tenu du profil des territoires (régression de Poisson), diagramme en entonnoir, zones de désert et de concentration (Moran local).
- Distance et accessibilité (méthode à deux étapes), temps de trajet de l'INSEE, comparaison avec l'APL de la DREES.
- Besoins et recours en santé mentale, quadrants offre et besoin, vulnérabilité psychosociale, psychiatrie à l'hôpital, accès financier, protection de l'enfance et handicap.
- Analyses pour chercheurs (décomposition de Theil, substitution entre professions, structure spatiale des écarts au modèle, outre-mer).

## Sorties

Tout est écrit dans `resultats/AAAA-MM-JJ/`. Les CSV utilisent le point-virgule et la virgule décimale pour s'ouvrir directement dans un tableur, et `dictionnaire_des_colonnes.md` décrit chaque fichier et chaque colonne. On y trouve aussi les rapports nationaux (santé mentale, santé), les rapports par région et par département (`territoires/`) et les données de l'atlas. Le dossier `resultats/historique/` conserve les effectifs départementaux de chaque exécution.

Le site statique est construit dans `site/` (accueil, atlas, rapports nationaux en HTML et PDF, rapports par territoire, méthode et données, à propos).

## Organisation du code

```
run.py                       point d'entrée
pipeline/config.py           sources, nomenclatures, paramètres, licences
pipeline/util.py             téléchargement, journal des sources, détection des colonnes
pipeline/sources/            un module par source
pipeline/build.py            agrégation des effectifs, catégories des secteurs d'activité
pipeline/analyses.py         analyses statistiques
pipeline/rapport.py          rapports nationaux
pipeline/rapport_territoire.py  rapports par région et par département
pipeline/graphiques.py, cartes.py  figures et cartes SVG
pipeline/export.py           CSV, données du site
pipeline/site.py             site statique (gabarits dans gabarits/)
atlas/                       atlas interactif
contenus/                    textes rédigés à la main (page À propos)
tests/test_unitaires.py      tests des briques statistiques sur des cas connus
```

Pour tester sans réseau, sur les vraies bases déjà téléchargées dans `donnees/brut/` (le projet n'utilise aucune donnée factice)

```
python tests/test_unitaires.py
python run.py --hors-ligne
```

## Précautions de lecture

Le RPPS enregistre des lieux d'exercice déclarés, pas une activité réelle ni un temps de travail. Un professionnel exerçant dans plusieurs territoires compte dans chacun, mais une seule fois au niveau national. Les analyses portent sur des territoires et non sur des individus. Le RPPS étant un recensement, les p-valeurs sont indicatives, les tailles d'effet sont l'information principale. L'effectif attendu décrit ce qu'on observe dans des territoires comparables, ce n'est pas un besoin de santé. Les personnes prises en charge par l'Assurance Maladie mesurent le recours aux soins, pas le besoin.
