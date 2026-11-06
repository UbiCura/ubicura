"""Défauts du site relevés par l'audit indépendant du 6 novembre 2026 (troisième audit avant la mise en ligne), un test
par défaut corrigé. Repris par tests/test_unitaires.py, comme tests/test_decisions.py."""
from __future__ import annotations

import re

from pipeline import config

GAB = config.RACINE / "gabarits"
RAC = config.RACINE


def test_explorer_trajectoires_unite_de_chaque_profession():
    """Onglet Trajectoires : une profession rare se lit pour 100 000 habitants, comme sur les autres pages."""
    js = (GAB / "explorer.js").read_text(encoding="utf-8")
    debut = js.index("function densite(p, g, i, a)")
    fin = js.index("function trajectoires()")
    morceau = js[debut:js.index("\n}", js.index("function trajectoires()"))]
    assert "1e4" not in js[debut:fin].replace("|| 1e4", "")
    assert "* FAC_T(p)" in js and "uniteT(p)" in morceau and "pour 10 000 habitants dans les départements" not in js
    assert "Math.abs(v) < 0.995 ? fr.format(\",.2f\")(v)" in js     # arrondis de la règle unique
    py = (RAC / "pipeline" / "explorer.py").read_text(encoding="utf-8")
    assert '"fac": AF.unite_prof(der["effectif"].sum(), der["population"].sum())' in py
    from pipeline import explorer as EX
    rs = sorted(p for p in config.RESULTATS.glob("20*") if (p / "evolution_explorer.csv").exists())
    if rs:
        t = EX.donnees_trajectoires(rs[-1])["profs"]
        if "chirurgiens" in t:
            assert t["chirurgiens"]["fac"] == 10000          # 2,1 pour 10 000 en France, toutes spécialités
        rares = [p for p in t if "ophtalm" in p]
        assert rares and all(t[p]["fac"] == 100000 for p in rares)


def test_fiche_ophtalmologues_et_gynecologues_ont_leur_ligne_du_repertoire():
    """Le répertoire compte les ophtalmologues et les gynécologues : leur ligne porte l'évolution de la DREES, jamais
    « suivie seulement par la DREES » ; le texte de l'évolution dit l'unité des professions rares."""
    from pipeline import fiche_territoire as FT
    ids = {p for p, _ in FT.PROFS_SANTE}
    assert {"ophtalmologue", "gynecologue"} <= ids
    bf = (RAC / "pipeline" / "bandes_fiche.py").read_text(encoding="utf-8")
    assert "pour 100 000 pour une profession rare comme sur sa" in bf


def test_fiche_titre_avec_article_du_territoire():
    """« Fiche de l'Aveyron », « des Yvelines », jamais « Fiche de Aveyron » (type de liaison de l'INSEE)."""
    from pipeline.fiche_territoire import de_nom
    if not (config.BRUT / "ref_departements.json").exists():
        return
    assert de_nom("dep", "12", "Aveyron") == "de l’Aveyron"
    assert de_nom("dep", "78", "Yvelines") == "des Yvelines"
    assert de_nom("dep", "30", "Gard") == "du Gard"
    assert de_nom("reg", "76", "Occitanie") == "d’Occitanie"
    g = (GAB / "fiche_territoire.html").read_text(encoding="utf-8")
    assert 'data-titre="Fiche {{ f.de_nom }}"' in g and "Fiche de {{ f.nom }}" not in g


def test_fiche_doi_general_jamais_dit_version_archivee():
    """Une version non archivée cite le DOI de toutes les versions sous ce nom, jamais comme « version archivée »."""
    g = (GAB / "fiche_territoire.html").read_text(encoding="utf-8")
    assert "data-doi=\"{{ '' if doi_toutes else" in g and "data-doi-general=\"{{ doi_donnees if doi_toutes" in g
    js = (GAB / "figures.js").read_text(encoding="utf-8")
    assert "', toutes les versions'" in js and '", toutes les versions doi:"+d.doiGeneral' in js


def test_comparer_allume_son_entree_du_menu():
    py = (RAC / "pipeline" / "portail.py").read_text(encoding="utf-8")
    assert 'page="comparer", titre="Comparer des territoires"' in py
    nav = (GAB / "nav.html").read_text(encoding="utf-8")
    assert "('comparer', 'comparer.html', 'Comparer')" in nav


def test_carte_des_departements_arrondis_communs_et_noms():
    """Pages d'indicateur et de domaine : l'infobulle nomme le territoire, suit la règle d'arrondi unique et écrit
    « aucun inscrit » plutôt qu'un 0 seul."""
    py = (RAC / "pipeline" / "cartes_presentation.py").read_text(encoding="utf-8")
    debut = py.index("def choroplethe(")
    corps = py[debut:py.index("\ndef ", debut + 10)]
    assert "_fr(" not in corps and "AF.nombre(v[c], g)" in corps and "aucun inscrit" in corps and "noms.get(c, c)" in corps


def test_fiche_indicateur_dictionnaire_et_doi_cliquable():
    g = (GAB / "fiche_indicateur.html").read_text(encoding="utf-8")
    assert "dictionnaire_des_colonnes.md" not in g and "/dictionnaire.html" in g
    assert "{{ citation_html|safe }}" in g and "|e|replace(" not in g
    py = (RAC / "pipeline" / "fiche_indicateur.py").read_text(encoding="utf-8")
    assert """f'<a href="https://doi.org/{doi}">doi:{doi}</a>'""" in py
    site = RAC / "site" / "donnees"
    if site.exists():
        for d in sorted(p for p in site.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name))[-1:]:
            assert (d / "dictionnaire.html").exists(), d


def test_structure_absente_mot_neutre():
    """« CMP pour adultes, aucune structure », jamais « aucune inscrite » après un nom masculin."""
    from pipeline import affichage as AF
    assert AF.AUCUNE_STRUCTURE == "aucune structure"


def test_atlas_pluriel_decide_sur_la_valeur_arrondie_et_signature_resserree():
    at = (RAC / "atlas" / "moteur" / "atlas.js").read_text(encoding="utf-8")
    assert 'fD(d)+" "+(d>=2?' not in at and '+fD(d).replace(' in at
    no = (RAC / "atlas" / "moteur" / "noyau.js").read_text(encoding="utf-8")
    debut = no.index("function normaliserTextes(svg)")
    assert 'text.signature' in no[debut:debut + 2500] and "textLength" in no[debut:debut + 2500]


def test_question_du_domaine_sans_coupure_au_trait_d_union():
    from pipeline import pages_domaine as PD
    qs = [q for v in PD.QUESTIONS.values() for q, *_ in v if "ils ?" in q]
    assert qs and all("-⁠ils" in q for q in qs)
    g = (GAB / "page_domaine.html").read_text(encoding="utf-8")
    assert "white-space:nowrap\">-ils" not in g


def test_aucun_zero_seul_dans_tous_les_tableaux_des_rapports():
    """Tous les tableaux des rapports, nationaux et par territoire, volets repliés compris (spécialités médicales,
    activités sans soins à la population) : un zéro s'écrit en mots (audit du 6 novembre 2026, partie 4)."""
    # un compte ou un indice nul ; un coefficient « 0,00 » ou un effet « 0 % » suivis de leur fourchette restent des valeurs
    zero = re.compile(r"\| 0 (?=\|)")
    rs = sorted(p for p in config.RESULTATS.glob("20*") if (p / "site_data.json").exists())
    if not rs:
        return
    # seuls les rapports écrits par le code actuel sont jugés (plus récents que les modules qui les écrivent)
    limite = max((RAC / "pipeline" / m).stat().st_mtime for m in ("rapport.py", "rapport_territoire.py"))
    for f in sorted(rs[-1].glob("rapport*.md")) + sorted((rs[-1] / "territoires").glob("*.md")):
        if f.stat().st_mtime < limite:
            continue
        mauvais = [l for l in f.read_text(encoding="utf-8").splitlines() if l.startswith("|") and zero.search(l)]
        assert not mauvais, (f.name, mauvais[:3])
