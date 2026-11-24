"""Mots du lecteur de la recherche de l'en-tête (étape 4 des portes d'entrée ; table validée le 23 novembre 2026,
contenus/mots_du_lecteur.csv, maquette prototypes/entrees/p4_p6/).

Une table relue comme les libellés : à chaque mot d'usage (« dépression », « désert médical », « nouveautés »), des
cibles, un indicateur du catalogue, une page (« page:journal.html ») ou une partie de fiche (« partie:d-sm », avec un
territoire : « santé mentale Rhône » ouvre la partie 01 de la fiche du Rhône). Les cibles passent en tête de leur groupe
de résultats. « Désert médical » mène aux indicateurs sans être écrit dans aucun résultat.

Toute cible doit exister, et aucun mot ne désigne un moyen de suicide (règle du 30 octobre 2026) : une ligne fautive est
écartée et consignée dans le journal des contrôles, et un test échoue.
"""
from __future__ import annotations

import csv
import re
import unicodedata

from . import config
from . import domaines as D
from .util import JOURNAL

FICHIER = config.RACINE / "contenus" / "mots_du_lecteur.csv"
# un moyen de suicide ne mène jamais nulle part depuis la recherche, même par un mot d'usage
MOYENS = (r"pendaison|pendre|pendu|arme|fusil|medicament|intoxication|surdose|overdose|noyade|noyer|saut|se jeter|"
          r"defenestr|precipit|veneneu|poison|gaz|monoxyde|charbon|corde|couteau|phlebotomie|immolation|pont|train|"
          r"voie ferree")


AIDE_CIBLES = ("suicides", "pensees_suicidaires_declarees", "tentative_suicide_vie_declaree")


def sans_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def parties() -> dict:
    """Parties de la fiche d'un territoire, les mêmes à tous les niveaux (bandes_fiche.bandes) : identifiant de la bande
    vers [numéro, titre]. Santé mentale, puis l'offre de soins, puis les domaines du contexte."""
    ordre = [("sm", "Santé mentale"), ("sante", "Offre de soins")]
    ordre += [(d["id"], d["nom"]) for d in D.DOMAINES if d["id"] != "offre"]
    return {f"d-{i}": [f"{k + 1:02d}", nom] for k, (i, nom) in enumerate(ordre)}


def erreurs_table(lignes: list[dict], ids: set, pages: set) -> list[str]:
    """Ce qui empêche une ligne de la table d'entrer dans la recherche."""
    out = []
    P = parties()
    for l in lignes:
        c = l["cible"]
        for m in l["mots"]:
            if re.search(MOYENS, sans_accents(m)):
                out.append(f"mot proscrit (moyen de suicide) : {m}")
        if c.startswith("page:") and c[5:] not in pages:
            out.append(f"page absente de la recherche : {c[5:]}")
        elif c.startswith("partie:") and c[7:] not in P:
            out.append(f"partie absente des fiches : {c[7:]}")
        elif not c.startswith(("page:", "partie:")) and c not in ids:
            out.append(f"indicateur absent du catalogue : {c}")
    return out


def lire() -> list[dict]:
    if not FICHIER.exists():
        return []
    with FICHIER.open(encoding="utf-8-sig") as f:
        L = list(csv.DictReader(f, delimiter=";"))
    # « regle: » décrit une règle codée dans la recherche (codes de département), pas une cible
    return [{"cible": l["cible"].strip(), "mots": [m.strip() for m in (l.get("mots_du_lecteur") or "").split("|") if m.strip()]}
            for l in L if l.get("cible") and not l["cible"].startswith("regle:")]


def donnees(ids: set, pages: list[list[str]], catalogue: list[dict]) -> dict:
    """Ce que recherche.json reprend : les lignes valides, les parties de fiche, et le nombre d'indicateurs publiés
    seulement par région dans chaque partie (« santé mentale Rhône » mène aussi à la partie de la fiche de la région)."""
    L = lire()
    urls = {p[1] for p in pages}
    mauvaises = erreurs_table(L, ids, urls)
    if mauvaises:
        JOURNAL.controle("Mots du lecteur de la recherche écartés (cible absente ou mot proscrit)",
                         f"{len(mauvaises)} : " + "; ".join(mauvaises[:10]))
    bon = [l for l in L if not erreurs_table([l], ids, urls)]
    # catalogue : les indicateurs de l'atelier (atelier.construire, A["ind"]), avec leurs niveaux et leur domaine
    reg_seul = {}
    for p in parties():
        dom = {"sante": "offre"}.get(p[2:], p[2:])
        reg_seul[p] = sum(1 for e in catalogue if list(e.get("niv") or []) == ["reg"]
                          and ((dom == "sm" and e.get("sm")) or (dom != "sm" and e.get("domb") == dom)))
    # une recherche qui mène aux indicateurs du suicide fait paraître, au-dessus des résultats, la ligne du 3114
    # (décision du 23 novembre 2026, texte de la maquette de l'étape 4 ; numéro vérifié sur 3114.fr le même jour)
    return {"lignes": bon, "parties": parties(), "reg_seul": reg_seul, "aide": [c for c in AIDE_CIBLES if c in ids]}
