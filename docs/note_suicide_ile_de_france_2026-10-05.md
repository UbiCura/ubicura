# Suicides et gestes auto-infligés en Île-de-France, vérification du 5 octobre 2026

Question de Lucas. « Les données sur le suicide et les gestes auto-infligés en région parisienne ont l'air faibles, est-ce juste ? »

## Ce que disent nos données
Taux de décès par suicide standardisé sur l'âge, pour 100 000 habitants (Santé publique France, Odissé, année 2023). Médiane des départements 13,9.

| Département | Suicides | Rang sur 101 | Hospitalisations pour geste auto-infligé | Passages aux urgences pour geste auto-infligé |
|---|---|---|---|---|
| Paris | 9,6 | 15 | 66,9 | 260,2 |
| Seine-et-Marne | 7,3 | 4 | 82,3 | 320,9 |
| Yvelines | 7,5 | 6 | 58,3 | 294,2 |
| Essonne | 9,2 | 11 | 84,7 | 278,0 |
| Hauts-de-Seine | 8,4 | 8 | 72,0 | 281,2 |
| Seine-Saint-Denis | 7,4 | 5 | 44,1 | 164,5 |
| Val-de-Marne | 6,5 | 3 | 77,7 | 317,9 |
| Val-d'Oise | 7,8 | 7 | 55,5 | 191,2 |

Médianes des départements, 128,3 hospitalisations et 435,1 passages aux urgences pour 100 000 habitants. Le Rhône est aussi très bas pour le suicide (5,3). Les valeurs sont bien celles publiées par Santé publique France, la lecture n'est pas en cause.

## Ce que disent les producteurs
- **Suicides.** Les décès de cause inconnue (code R99) et d'intention indéterminée (Y10 à Y34) ne sont pas comptés comme suicides, et leur nombre varie d'un département à l'autre. Les volets complémentaires du certificat de décès établis après une autopsie ne remontent pas tous. Santé publique France demande donc d'interpréter avec précaution les écarts entre départements ([bulletin Île-de-France, bilan 2024](https://www.santepubliquefrance.fr/regions-et-territoires/ile-de-france/bulletin-regional/conduites-suicidaires-en-ile-de-france-bilan-2024)). L'Observatoire national du suicide rappelle une étude du CépiDc sur les décès de 2006, avec une sous-estimation de 9,4 % en France métropolitaine, de 46 % en Île-de-France et de 22 % en Rhône-Alpes. Il signale aussi l'absence de transmission des résultats de l'institut médico-légal de Paris pour 2001 à 2003 et 2015 à 2017 ([ONS, 5e rapport, fiche 14](https://drees.solidarites-sante.gouv.fr/sites/default/files/2022-09/Fiche%2014%20-%20Donn%C3%A9es%20%C3%A9pid%C3%A9miologiques%20sur%20les%20d%C3%A9c%C3%A8s%20par%20suicide%20en%20France%20en%202017.pdf)). Les écarts entre régions seraient en partie dus à l'hétérogénéité des remontées d'information.
- **Passages aux urgences.** Seules les urgences générales sont couvertes (deux services d'urgences psychiatriques seulement participent en France), 115 des 127 services franciliens transmettent leurs données, le taux de codage des diagnostics va de 85 % (Essonne) à 95 % (Val-d'Oise), et la circonstance du geste n'est pas toujours connue à l'accueil. Santé publique France présume une sous-estimation. Un défaut de logiciel a aussi sous-estimé les passages en Provence-Alpes-Côte d'Azur et en Corse de 2022 à avril 2024, et Santé publique France ne présente pas ces régions pour 2022 à 2024 dans ses bulletins (même bulletin).
- **Hospitalisations.** Le PMSI MCO ne couvre pas les séjours en établissement psychiatrique, recueillis dans une autre base.

## Effet sur nos résultats
Corrélation de rang entre la densité de psychiatres et chaque indicateur, entre départements.

| Indicateur | Tous (101) | Sans l'Île-de-France (93) | Sans l'Île-de-France ni le Rhône (92) | Hexagone sans l'Île-de-France (88) |
|---|---|---|---|---|
| Décès par suicide | −0,38 | −0,35 | −0,33 | −0,41 |
| Hospitalisations pour geste auto-infligé | −0,28 | −0,23 | −0,21 | −0,30 |
| Passages aux urgences pour geste auto-infligé | +0,05 | +0,16 | +0,16 | +0,11 |

Le lien négatif entre psychiatres et suicide reste modéré quand on retire l'Île-de-France. Le biais francilien le renforce un peu, sans le créer. Le lien avec les passages aux urgences, déjà négligeable, est le plus sensible.

## Propositions
1. Mention visible, avec les sources, partout où ces indicateurs sont montrés (rapports, page d'un territoire francilien, analyse offre et besoins), et dans la page méthode.
2. Analyse de sensibilité produite à chaque exécution (corrélations et quadrants sans l'Île-de-France), contrôle au journal, phrase dans le résultat.
3. Signaler les passages aux urgences de 2024 en Provence-Alpes-Côte d'Azur et en Corse comme possiblement sous-estimés.
4. Pour la version 2.0, chercher si les décès de cause inconnue ou d'intention indéterminée sont publiés par département (CépiDc), pour un indicateur de sensibilité.
