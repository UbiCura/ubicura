"""Tri de la veille des bases (refonte du 8 novembre 2026, remarque de Lucas du 7 novembre : « je ne peux pas tout
traiter »). Tests sur les vraies données en cache (donnees/veille) et le vrai registre (docs/veille/registre_bases.csv).
Lancement seul : python tests/test_veille.py. Sans cache de la veille, chaque test le dit et s'arrête sans échouer."""
from __future__ import annotations

import copy
import csv
import json
import shutil
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from outils import veille as v  # noqa: E402

__all__ = ["test_veille_tri_statut_partout", "test_veille_ecart_toujours_motive", "test_veille_point_dix_au_plus",
           "test_veille_regles_sur_vrais_candidats", "test_veille_registre_alimente_sans_toucher_aux_decisions",
           "test_veille_reponses_de_lucas", "test_veille_releve_trie_a_l_arrivee"]


def _donnees():
    cands = v.lire_json(v.CANDIDATS, {})
    lignes = v.lire_registre()
    if not cands or not lignes:
        print("  cache de la veille ou registre absent, test sans objet")
        return None, None
    return cands, lignes


def test_veille_tri_statut_partout():
    """Chaque candidat relevé a un statut (au registre ou écarté) et une règle connue ; le tri enregistré est celui que
    les règles redonnent (reproductible) ; le fichier versionné du tri a une ligne par candidat."""
    cands, lignes = _donnees()
    if cands is None:
        return
    sans = [k for k, c in cands.items() if (c.get("tri") or {}).get("statut") not in v.STATUTS_TRI]
    assert not sans, f"{len(sans)} candidat(s) sans statut, par exemple {sans[:5]}"
    assert all(c["tri"]["regle"] in v.REGLES_TRI for c in cands.values())
    refait = v.trier(cands, lignes, v.marques())
    ecarts = [k for k, r in refait.items() if any(r[x] != cands[k]["tri"][x] for x in ("statut", "regle", "raison"))]
    assert not ecarts, f"tri enregistré différent du tri refait : {ecarts[:5]} (relancer veille.py trier)"
    with v.TRI_CSV.open(encoding="utf-8", newline="") as h:
        rangs = {x["cle"]: x for x in csv.DictReader(h, delimiter=";")}
    assert set(rangs) == set(cands), "docs/veille/tri_candidats.csv ne couvre pas tous les candidats"
    assert all(rangs[k]["statut"] == c["tri"]["statut"] for k, c in cands.items())


def test_veille_ecart_toujours_motive():
    """Aucun candidat écarté sans raison écrite, et tout candidat « au registre » y a sa ligne, non écartée."""
    cands, lignes = _donnees()
    if cands is None:
        return
    sans_raison = [k for k, c in cands.items() if c["tri"]["statut"] == "écarté" and len(c["tri"]["raison"]) < 10]
    assert not sans_raison, sans_raison[:5]
    index = {k: x for x in lignes for k in x["cle_veille"].split()}
    for k, c in cands.items():
        if c["tri"]["statut"] == "au registre":
            x = next((index[m] for m in [k, *c.get("membres", [])] if m in index), None)
            assert x is not None, f"{k} au registre sans ligne"
            assert x["statut"] != "écartée", f"{k} au registre sur une ligne écartée ({x['id']})"
    # le tri ne laisse pas tout passer ni tout écarter
    n = len(cands)
    au_registre = sum(1 for c in cands.values() if c["tri"]["statut"] == "au registre")
    assert 0 < au_registre < n / 2, au_registre


def test_veille_point_dix_au_plus():
    """Le point de la semaine tient en dix bases au plus, chacune avec la décision attendue de Lucas et la
    recommandation, et seulement des décisions qui lui reviennent (licence, juridique, sensible, libellés). La
    limite tient même quand toutes les lignes à examiner du vrai registre demanderaient une décision."""
    cands, lignes = _donnees()
    point = v.lire_json(v.POINT, {})
    if cands is None or not point:
        print("  point de la semaine absent, test sans objet")
        return
    assert len(point["lignes"]) <= v.POINT_MAX == 10
    for x in point["lignes"]:
        assert x["decision"] in v.DECISIONS_LUCAS and x["decision"], x["id"]
        assert "Recommandation" in x["recommandation"], x["id"]
    tout = [dict(x, decision="licence", recommandation="Recommandation : essai.") if x["statut"] == "à examiner"
            else x for x in copy.deepcopy(lignes)]
    assert sum(1 for x in tout if x["decision"]) > v.POINT_MAX
    assert len(v.point_de_la_semaine(tout, {})) == v.POINT_MAX
    # une ligne répondue sort du point, une ligne « plus tard » y revient après quatre semaines
    premier = v.point_de_la_semaine(tout, {})[0]["id"]
    import datetime as dt
    jour = dt.date(2026, 11, 9)
    assert premier not in [x["id"] for x in v.point_de_la_semaine(tout, {premier: {"reponse": "accord",
                                                                                   "le": "2026-11-08"}}, jour)]
    tard = {premier: {"reponse": "plus_tard", "le": "2026-11-08"}}
    assert premier not in [x["id"] for x in v.point_de_la_semaine(tout, tard, jour)]
    assert premier in [x["id"] for x in v.point_de_la_semaine(tout, tard, jour + dt.timedelta(days=28))]


def test_veille_regles_sur_vrais_candidats():
    """Règles du tri sur des candidats réels relevés le 29 octobre 2026 : annuaires nominatifs, articles de Zenodo,
    jeux d'une seule collectivité, tables de la CNAF déjà intégrée, thèmes hors du site, moyens des suicides jamais
    retenus ; marques de Lucas gardées telles quelles."""
    cands, lignes = _donnees()
    if cands is None:
        return
    par_regle = {}
    for c in cands.values():
        par_regle.setdefault(c["tri"]["regle"], []).append(c)
    for regle in ("regle_projet", "article", "local", "rattache", "hors_domaine"):
        assert par_regle.get(regle), f"aucun candidat écarté par la règle {regle}"
    assert all(c["source"] == "zenodo" for c in par_regle["article"])
    caf = [c for c in cands.values() if c["source"] == "caf"]
    assert caf and all(c["tri"]["statut"] == "écarté" and c["tri"]["registre"] in ("caf", "caf_communes_qpv")
                       for c in caf)
    for c in cands.values():
        t = v.plat(c["titre"])
        if "annuaire" in t:
            assert c["tri"]["statut"] == "écarté", c["cle"]
        if "moyens utilises" in t:
            assert c["tri"]["statut"] == "écarté", c["cle"]
    # les marques déjà posées par Lucas ne changent pas, ses bases « intéressantes » restent au registre
    for cle, m in v.marques().items():
        if cle in cands and m.get("marque") == "interessant":
            assert cands[cle]["tri"]["statut"] == "au registre", cle
    # thèmes proposés pris parmi ceux du site (pipeline/themes.py)
    from pipeline import themes
    assert set(v.THEMES_CONNUS) == {t["id"] for t in themes.THEMES}


def test_veille_registre_alimente_sans_toucher_aux_decisions():
    """Le registre réel passe le contrôle de forme, l'alimentation refaite ne change aucune ligne déjà décidée
    (intégrée, à intégrer, écartée) et chaque ligne ajoutée par la veille a sa pertinence."""
    cands, lignes = _donnees()
    if cands is None:
        return
    assert not v.controler_registre(lignes), v.controler_registre(lignes)[:5]
    avant = copy.deepcopy(lignes)
    b = v.alimenter_registre(ecrire=False, lignes=copy.deepcopy(lignes), cands=copy.deepcopy(cands))
    apres = {x["id"]: x for x in b["lignes"]}
    for x in avant:
        if x["statut"] != "à examiner":
            y = apres[x["id"]]
            assert {k: x[k] for k in x if k != "derniere_maj"} == {k: y[k] for k in y if k != "derniere_maj"}, x["id"]
    assert b["ajoutees"] == 0, "le registre n'est pas à jour du tri (relancer veille.py trier)"
    for x in lignes:
        if x["raison"].startswith("relevée par la veille") and x["statut"] == "à examiner":
            assert x["pertinence"] in ("forte", "moyenne", "faible"), x["id"]


def test_veille_reponses_de_lucas():
    """Une réponse de Lucas au point de la semaine passe au registre : « non » écarte la ligne avec la date, « d'accord »
    la garde à examiner avec la recommandation acceptée. Dans un dossier temporaire, sur une vraie ligne du registre."""
    cands, lignes = _donnees()
    if cands is None:
        return
    x = next((y for y in lignes if y["decision"] and y["statut"] == "à examiner"), None)
    if x is None:
        print("  aucune ligne en attente de décision, test sans objet")
        return
    avant = v.DECISIONS
    tmp = Path(tempfile.mkdtemp(prefix="veille_"))
    try:
        v.DECISIONS = tmp / "decisions.json"
        v.repondre(x["id"], "refus", x["recommandation"])
        b = v.alimenter_registre(ecrire=False, lignes=copy.deepcopy(lignes), cands=copy.deepcopy(cands))
        y = next(z for z in b["lignes"] if z["id"] == x["id"])
        assert y["statut"] == "écartée" and "par Lucas le" in y["raison"] and b["reponses"] == 1
        v.repondre(x["id"], "accord", x["recommandation"])
        b = v.alimenter_registre(ecrire=False, lignes=copy.deepcopy(lignes), cands=copy.deepcopy(cands))
        y = next(z for z in b["lignes"] if z["id"] == x["id"])
        assert y["statut"] == "à examiner" and y["raison"].startswith("recommandation acceptée par Lucas le")
        try:
            v.repondre(x["id"], "peut-être")
            raise AssertionError("réponse inconnue acceptée")
        except ValueError:
            pass
    finally:
        v.DECISIONS = avant
        shutil.rmtree(tmp, ignore_errors=True)


def test_veille_releve_trie_a_l_arrivee():
    """Une relève de la semaine trie chaque nouveau candidat à son arrivée. Dans un dossier temporaire, le catalogue
    rend des métadonnées réelles déjà relevées ; le vrai registre est lu, jamais écrit."""
    cands, lignes = _donnees()
    if cands is None:
        return
    echantillon = [{k: c[k] for k in ("cle", "source", "ident", "titre", "producteur", "licence", "niveau", "date",
                                      "adresse", "description", "score", "raisons", "domaine")}
                   for c in sorted(cands.values(), key=lambda c: c["cle"])[:40]]
    registre_avant = v.REGISTRE.read_bytes()
    avant = (v.DOSSIER, v.CANDIDATS, v.MARQUES, v.EXAMENS, v.PASSAGES)
    tmp = Path(tempfile.mkdtemp(prefix="veille_"))
    try:
        v.DOSSIER, v.CANDIDATS, v.MARQUES, v.EXAMENS, v.PASSAGES = (tmp, tmp / "c.json", tmp / "m.json", tmp / "e",
                                                                    tmp / "p.json")
        b = v.relever(catalogues={"insee": lambda _d: json.loads(json.dumps(echantillon))})
        trouves = v.lire_json(v.CANDIDATS, {})
        assert trouves and all((c.get("tri") or {}).get("statut") in v.STATUTS_TRI for c in trouves.values())
        assert sum(b["tri"]["par_statut"].values()) == len(trouves)
    finally:
        v.DOSSIER, v.CANDIDATS, v.MARQUES, v.EXAMENS, v.PASSAGES = avant
        shutil.rmtree(tmp, ignore_errors=True)
    assert v.REGISTRE.read_bytes() == registre_avant, "la relève a écrit le registre"


if __name__ == "__main__":
    n = 0
    for nom in __all__:
        globals()[nom]()
        n += 1
        print("ok", nom)
    print(f"{n} tests réussis")
