"""Données de la matrice des liens de l'atelier « Croiser » (avis de l'auditeur externe du 30 octobre 2026,
docs/avis_carte_des_liens_2026-10-30.md, suivi par Lucas).

L'offre en colonnes (professions de santé mentale, ou principales professions de santé), les indicateurs des autres
domaines en lignes, rangés par domaine. Chaque case garde la corrélation de rang brute et à densité de population égale,
leurs intervalles à 95 %, leurs q-valeurs de Benjamini-Hochberg et le nombre de territoires, relus dans le fichier
publié correlations_contexte.csv. La page n'affiche un lien que s'il passe la règle unique (pipeline/regle_lien.py).
Départements et intercommunalités seulement, pas de lien dit entre régions. Aucun calcul statistique ici.
"""
import csv
import json
from pathlib import Path

from . import domaines as D
from .regle_lien import ALPHA, NIVEAUX, SEUIL_RHO

# nom court d'en-tête, le nom long reste au survol (audit de contrôle du 30 octobre 2026, point F14)
COURTS = {"q_psychiatrie_enfant": "Psychiatres de l’enfant", "q_addictologie": "Addictologues",
          "masseur_kinesitherapeute": "Kinésithérapeutes", "chirurgien_dentiste": "Dentistes",
          "medecin_generaliste": "Généralistes"}
COLONNES = {"sm": ["psychologue", "psychiatre", "pedopsychiatre", "psychotherapeute", "q_psychiatrie_enfant", "q_addictologie"],
            "sante": ["medecin_generaliste", "infirmier", "masseur_kinesitherapeute", "orthophoniste", "psychomotricien",
                      "pharmacien", "chirurgien_dentiste", "sage_femme", "pediatre"]}


def _num(s):
    try:
        x = float(str(s).replace(",", "."))
        return round(x, 4) if x == x else None
    except (TypeError, ValueError):
        return None


def donnees(sd: dict, dernier: Path, version: str, doi: str | None, fiches: dict) -> dict:
    from .lecture import pluriel
    ctx = {c["id"]: c for c in sd["contexte"]}
    profs = {p["id"]: p for p in sd["professions"]}
    cols = {k: [p for p in v if p in profs] for k, v in COLONNES.items()}
    garde = {p for v in cols.values() for p in v}
    cases = {lv: {} for lv in NIVEAUX}
    variables = set()
    with open(dernier / "correlations_contexte.csv", encoding="utf-8-sig") as f:
        for l in csv.DictReader(f, delimiter=";"):
            if l["mode"] != "all" or l["niveau"] not in NIVEAUX or l["prof"] not in garde or l["variable"] not in ctx:
                continue
            dom, _ = D.classer(ctx[l["variable"]])
            if dom == "offre":
                continue
            variables.add(l["variable"])
            # [rho, bas, haut, q, rho partiel, bas, haut, q partiel, territoires]
            cases[l["niveau"]][f"{l['prof']}|{l['variable']}"] = [
                _num(l["rho_spearman"]), _num(l["ic95_bas"]), _num(l["ic95_haut"]), _num(l["q_bh"]),
                _num(l["rho_partiel_densite"]), _num(l["ic95_bas_partiel"]), _num(l["ic95_haut_partiel"]),
                _num(l["q_bh_partiel"]), int(float(l["n"])) if l["n"] else None]
    lignes = []
    for d in D.DOMAINES:
        if d.get("centre"):
            continue
        ids = [v for v in ctx if v in variables and D.classer(ctx[v])[0] == d["id"]]
        for v in ids:
            c = ctx[v]
            # les distances aux structures sont de l'offre comparée à l'offre, rangées à part (point I5)
            dist = v.startswith("dist_")
            lab = c["label"].replace("Distance à la structure la plus proche, ", "Distance, ") if dist else c["label"]
            lignes.append({"id": v, "lab": lab, "long": c["label"], "u": c.get("unite") or "",
                           "dom": "distances" if dist else d["id"], "sm": D.sante_mentale(c), "fiche": fiches.get(v, "")})
    lignes.sort(key=lambda l: l["dom"] == "distances")
    return {"version": version, "doi": doi, "seuil": SEUIL_RHO, "alpha": ALPHA,
            "domaines": [{"id": d["id"], "nom": d["nom"]} for d in D.DOMAINES if not d.get("centre")]
                        + [{"id": "distances", "nom": "Distances aux structures de soins, l'offre comparée à l'offre"}],
            "colonnes": {k: [{"id": p, "lab": pluriel(profs[p]["libelle"]).capitalize(),
                              "court": COURTS.get(p) or pluriel(profs[p]["libelle"]).capitalize(), "fiche": fiches.get("prof:" + p, "")}
                             for p in v] for k, v in cols.items()},
            "lignes": lignes, "cases": cases}


def construire(sd: dict, dernier: Path, site: Path, version: str, doi: str | None, fiches: dict) -> Path:
    L = donnees(sd, dernier, version, doi, fiches)
    f = site / "presentation" / "liens_donnees.js"
    f.write_text("var L=" + json.dumps(L, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    return f
