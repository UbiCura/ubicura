# Bases complémentaires

Chaque fichier JSON de ce dossier décrit une base ouverte à croiser avec l'offre de soins. Elle est récupérée, lue, agrégée aux niveaux géographiques supérieurs et ajoutée aux indicateurs de contexte. Elle entre alors dans les corrélations, le rapport et l'atlas.

Tout doit rester automatisable. Une base est donc résolue soit par data.gouv (`datagouv`, slug ou identifiant du jeu, et `ressource`, motif sur le titre de la ressource), soit par une adresse stable (`url`). Un descripteur sans l'un ni l'autre est refusé.

Une base n'est ajoutée qu'après vérification de son existence, de son format, de sa licence et de son niveau géographique, avec la date de vérification dans le champ `verifie_le`. Ses libellés passent par la table `pipeline/libelles.csv`. Une base sous licence ODbL porte `"licence": "ODbL"`, ses indicateurs sont alors écrits dans des fichiers à part.

La cartographie des pathologies de l'Assurance Maladie, qui demande un traitement particulier (filtrage par l'API, standardisation sur l'âge), a son propre module, `pipeline/sources/ameli.py`.

Le format complet d'un descripteur est documenté en tête de `pipeline/sources/complements.py`.
