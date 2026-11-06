"""Règle unique pour dire « lien » ou « pas de lien » entre deux indicateurs, sur tout le site (avis de l'auditeur
externe du 30 octobre 2026, docs/avis_carte_des_liens_2026-10-30.md, suivi par Lucas).

Même mesure partout, la corrélation de rang de Spearman entre territoires d'un même niveau. Même correction des tests
multiples, Benjamini-Hochberg (q-valeur sous ALPHA). Même seuil d'intensité, une valeur absolue d'au moins SEUIL_RHO.
Un lien qui passe les deux est un lien ; sinon le site écrit « pas de lien au-delà du seuil retenu », sans dire
« aucun lien ». À densité de population égale (corrélation partielle) par défaut dans la matrice des liens, brute en
option. Pas de lien dit au niveau régional, trop peu de territoires (13 ou 18) pour un intervalle utile.

Seuil confirmé sur les données du 30 octobre 2026 (correlations de site_data.json, mode « tous modes ») : 49 % des
couples passent la correction, 30 % la passent avec |rho| d'au moins 0,3, 42 % avec 0,2. À 0,3 la matrice garde les
liens au moins modérés de la convention déjà écrite dans la page méthode (lecture.force) et reste lisible.
Le moteur de l'atlas et les pages lisent les mêmes valeurs dans gabarits/presentation/lien.js, un test vérifie
qu'elles sont égales.
"""
import math

SEUIL_RHO = 0.3
ALPHA = 0.05
NIVEAUX = ("dep", "epci")


def est_lien(rho, q) -> bool:
    """Vrai quand la corrélation passe la correction de Benjamini-Hochberg et atteint le seuil d'intensité."""
    if rho is None or q is None or not (math.isfinite(rho) and math.isfinite(q)):
        return False
    return q < ALPHA and abs(rho) >= SEUIL_RHO


def verdict(rho, q) -> str:
    """« lien positif », « lien négatif » ou « sous le seuil »."""
    if not est_lien(rho, q):
        return "sous le seuil"
    return "lien positif" if rho > 0 else "lien négatif"


def phrase_seuil() -> str:
    """La règle en une phrase, pour les pages et les rapports."""
    s = f"{SEUIL_RHO:.1f}".replace(".", ",")
    return (f"Sur tout le site, deux indicateurs sont dits liés quand leur corrélation de rang entre territoires atteint "
            f"au moins {s} en valeur absolue et passe la correction de Benjamini-Hochberg des tests multiples.")
