# Vérification de la fiabilité, 8 octobre 2026

Suite de `docs/verification_2026-10-05.md`. Elle porte sur les points restés ouverts (temps d'accès, APL) et sur les ajouts faits depuis le 7 octobre (ALD, CAF, évolution, croisements entre indicateurs, régressions). Les chiffres sont recalculés depuis les fichiers bruts par un code distinct de celui du programme (`outils/controle_independant.py`, relancé après chaque mise à jour par `outils/mise_a_jour.ps1`). Résultats du 8 octobre 2026, avec le RPPS du 8 octobre, **91 contrôles conformes, aucun écart**.

## Ce qui est contrôlé

| Thème | Contrôle | Résultat |
|---|---|---|
| Temps de trajet (INSEE) | Fichier brut de la Corse retéléchargé (59 Mo), temps moyen et part à plus de 20 minutes recalculés pour trois communes et trois équipements, puis moyenne et médiane exacte pour les deux départements | Moyennes identiques au millième. Médianes à moins de 0,15 minute près, l'écart vient du regroupement des durées par minute, annoncé dans la méthode |
| APL (DREES) | Classeur relu par un code indépendant, feuille du millésime 2024, comparaison commune par commune | 34 883 communes, écart maximal nul, généralistes et infirmiers |
| ALD (Assurance Maladie) | Cellules du classeur départemental pour cinq départements et trois affections, somme des départements pour l'ALD 23 | Identiques, 1 606 120 personnes en ALD 23 |
| Allocations (CAF) | Effectif de l'AAH pour trois départements depuis le fichier brut, taux pour 1 000 habitants, population du référentiel | Identiques |
| Évolution | Populations de l'INSEE (estimations) pour la France et deux départements en 2016 et 2024, cohérence densité, effectif et population sur toutes les lignes | Identiques |
| Croisements entre indicateurs | Corrélation de rang, nombre de départements et valeur sans l'Île-de-France pour trois paires | Identiques |
| Régressions | Coefficients standardisés, R² et erreurs types robustes (HC3) recalculés avec numpy pour deux indicateurs | Identiques au dix-millième |

## Corrections faites

1. **Mises à jour fondées sur la version du producteur.** Le RPPS, FINESS et les bases complémentaires étaient repris selon l'âge de la copie locale. Une nouvelle version pouvait être ignorée pendant la durée du cache (7 jours pour le RPPS), et une copie inchangée retéléchargée. Désormais, quand le producteur annonce la date de sa version, c'est elle qui décide (`util.telecharger`). Les contours de l'IGN et la SAE ne consultaient le producteur qu'après 365 et 30 jours, ils le consultent à chaque exécution. Le dossier complet de l'INSEE n'était jamais repris sans `--rafraichir`, il l'est maintenant dès que sa date de parution change.
2. **Mayotte dans les croisements.** Mayotte était écartée de tous les croisements entre départements par une règle prévue pour les seules données de l'Assurance Maladie, sans que les textes le disent pour les croisements entre indicateurs. La règle est désormais nommée (`config.DEPARTEMENTS_EXCLUS_CROISEMENTS`), justifiée (population de référence incertaine faute de recensement exhaustif) et écrite dans le rapport et l'atlas. Les chiffres publiés ne changent pas.
3. **Journal des mises à jour.** Deux exécutions le même jour effaçaient les changements de la première. Le changement de RPPS du 8 octobre a été rétabli d'après le compte rendu de la mise à jour, les effectifs d'avant n'ayant pas été conservés. Les exécutions du même jour s'ajoutent désormais à l'entrée du jour (test `test_journal_meme_jour`).

## Vérification des sources et mise à jour

- `python run.py --verifier` demande à chaque producteur la version de chacun des fichiers suivis, sans rien télécharger, et la compare à celle du cache. Résultat dans la console et dans `donnees/verification.json`. Codes de sortie 0 à jour, 10 à mettre à jour, 20 vérification incomplète.
- `outils/mise_a_jour.ps1` enchaîne la vérification, la chaîne complète si une source a changé, une vérification après coup et le contrôle indépendant. Il ne fait rien si la dernière vérification complète date de moins de six jours (`-Forcer` pour passer outre), `-Simuler` montre ce qui serait fait. Compte rendu de chaque passage dans `donnees/journaux/`, état dans `donnees/etat_mise_a_jour.json`.
- Essai réel du 8 octobre au soir, nouvelle version du RPPS repérée (8 octobre, copie locale du 3), seuls les trois fichiers du RPPS retéléchargés, chaîne complète en 10,8 minutes, vérification après coup sans nouvelle version restante.
