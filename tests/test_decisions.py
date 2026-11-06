"""Une décision de Lucas ou un défaut relevé par un audit, un test : ce qui a été tranché ne se perd plus sans qu'un test
échoue (remarque de Lucas du 6 novembre 2026, la carte de l'accueil décidée le 2 novembre avait été oubliée). Tests sur
les gabarits et, quand il existe, sur le site construit (site/), jamais sur des données factices. Repris par
tests/test_unitaires.py."""
from __future__ import annotations

import html as _html
import json
import re

from pipeline import config

GAB = config.RACINE / "gabarits"
SITE = config.RACINE / "site"


def _texte(chemin) -> str:
    t = chemin.read_text(encoding="utf-8")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", t)))


def test_accueil_montre_la_carte_cliquable_de_l_atlas():
    """Lucas, 2 novembre 2026 : l'accueil garde la carte cliquable de l'atlas, avec l'encadré du territoire et celui des
    structures de soins. L'atlas a une vue « accueil » sans en-tête ni onglets, et la page d'accueil l'affiche."""
    p = (GAB / "portail.html").read_text(encoding="utf-8")
    assert 'id="cadre-atlas"' in p and "?vue=accueil" in p and 'loading="lazy"' in p
    at = (config.RACINE / "atlas" / "moteur" / "atlas.js").read_text(encoding="utf-8")
    assert 'get("vue")==="accueil"' in at and 'ubicura:"hauteur"' in at
    tpl = (config.RACINE / "atlas" / "atlas_template.html").read_text(encoding="utf-8")
    assert "html.vue-accueil" in tpl and 'classList.add("vue-accueil")' in tpl
    idx = SITE / "index.html"
    if idx.exists() and 'id="cadre-atlas"' in idx.read_text(encoding="utf-8"):
        assert "atlas.html?vue=accueil" in idx.read_text(encoding="utf-8")


def test_offre_de_soins_mene_a_l_atlas():
    """Remarque de Lucas du 6 novembre 2026 : depuis le menu à six entrées, l'atlas n'était plus atteint que par le pied de
    page. La page « Offre de soins » le propose à côté des deux familles, et ses pages allument l'entrée « Offre de soins »."""
    p = (GAB / "page_domaine.html").read_text(encoding="utf-8")
    assert '<a href="../{{ page_atlas }}"><strong>L’atlas</strong>' in p
    py = (config.RACINE / "pipeline" / "pages_domaine.py").read_text(encoding="utf-8")
    assert 'page="domaines", titre=centre["nom"]' not in py and 'page="offre", titre=centre["nom"]' in py
    assert 'page="offre", titre=titre, classe_main="domaine", centre=True' in py


def test_comment_lire_jamais_replie_derriere_un_bouton():
    """Décision de Lucas du 5 novembre 2026, « Comment lire » toujours visible : l'audit du 6 novembre en trouvait encore
    replié dans les rapports (figures.js), Croiser, la matrice des liens et la zone. Aucun gabarit ne garde de bouton
    « Comment lire » ; l'atlas déplie les siens à l'ouverture (noyau.js, deplierCommentLire)."""
    for nom in ("croiser.html", "liens.html", "zone.html", "comparer.html", "page_domaine.html", "portail.html"):
        h = (GAB / nom).read_text(encoding="utf-8")
        assert not re.search(r"<button[^>]*>\s*Comment lire\s*</button>", h), nom
        assert not re.search(r'class="panneau" id="lire-[^"]*" hidden', h), nom
    fj = (GAB / "figures.js").read_text(encoding="utf-8")
    assert "lireReplie" not in fj and "lire-fig" not in fj
    assert ".comment-lire.repli" not in (GAB / "style.css").read_text(encoding="utf-8")
    assert "deplierCommentLire" in (config.RACINE / "atlas" / "moteur" / "noyau.js").read_text(encoding="utf-8")


def test_pages_de_domaine_ont_un_comment_lire():
    """Audit du 6 novembre 2026 : la carte, « En bref » et les liens des sept domaines n'avaient aucune explication."""
    h = (GAB / "page_domaine.html").read_text(encoding="utf-8")
    assert h.count('<p class="comment-lire"><strong>Comment lire.</strong>') >= 3
    assert "Bleu, les deux" not in h and "En canard, les deux montent ensemble" in h


def test_repere_des_pages_de_domaine_est_celui_des_fiches():
    """Audit du 6 novembre 2026 : « En bref » des pages de domaine donnait une moyenne simple des territoires (taux de
    pauvreté 14,0) quand les fiches et Comparer donnent l'ensemble des intercommunalités (16,3). Le repère vient
    d'affichage.Affichage, nommé comme ailleurs, et la page construite écrit ce même chiffre."""
    py = (config.RACINE / "pipeline" / "pages_domaine.py").read_text(encoding="utf-8")
    assert "sum(x for x in vals if x is not None)" not in py and "T.serie(pid, lv)" in py
    assert "{{ v.rep_lib|lower }} {{ v.rep|nombre(v.genre) }}" in (GAB / "page_domaine.html").read_text(encoding="utf-8")
    page = SITE / "domaine" / "revenus.html"
    if not page.exists() or "repère " in _texte(page):
        return    # site construit avant la correction : la prochaine construction le vérifie
    from pipeline import affichage as AF
    from pipeline.fiche_territoire import _nombre_filtre
    dernier = sorted(p for p in config.RESULTATS.glob("20*") if (p / "site_data.json").exists())[-1]
    sd = json.loads((dernier / "site_data.json").read_text(encoding="utf-8"))
    S = AF.Affichage(sd, dernier).serie("taux_pauvrete", "epci")
    if S is None:
        return
    t = _texte(page)
    attendu = f"{S.ref_lib().lower()} {_nombre_filtre(S.ref, S.genre)}"
    assert attendu in t, (attendu, t[t.find("Taux de pauvreté"):t.find("Taux de pauvreté") + 160])


def test_historique_des_versions_ne_confond_pas_deux_effectifs():
    """Audit du 6 novembre 2026 : « 4 111 inscrits à la version du 9 octobre comme à celle du 30 octobre » alors que le
    9 octobre en comptait 4 091. « comme à celle » seulement quand les deux effectifs sont égaux."""
    h = (GAB / "fiche_territoire.html").read_text(encoding="utf-8")
    i = h.index("comme à celle du")
    assert "{% if s.debut[1] == s.fin[1] %}" in h[max(0, i - 300):i]


def test_position_ecrite_pareil_sur_la_fiche_et_comparer():
    """Audit du 6 novembre 2026 : Comparer écrivait « plus haut que 15 % des départements » là où la fiche écrit « plus
    bas que 85 % », et « plus haut que 0 % ». Comparer lit le nombre publié par affichage.position_code."""
    from pipeline import affichage as AF
    assert AF.position_txt(.15, "dep", "", .85) == f"plus bas que 85{AF.FINE}% des départements"
    assert AF.position_code(.15, .85) == -85 and AF.position_code(0, 1.0) == -100 and AF.position_code(1.0, 0) == 100
    assert AF.position_txt(0, "reg", "", 1.0) == "plus bas que toutes les autres régions"
    js = (GAB / "presentation" / "chiffres.js").read_text(encoding="utf-8")
    assert "function posTxt(q, kind, lv, A)" in js and "a.q ? a.q[k]" in js
    assert '"q": [position_code(S.pos[k], S.posb[k]) for k in garde]' in (
        config.RACINE / "pipeline" / "affichage.py").read_text(encoding="utf-8")


def test_mais_s_appuie_toujours_sur_ce_qui_precede():
    """Audit du 6 novembre 2026 : « ensemble 3,2 km, mais plus près que 56 % » n'opposait rien. Sans écart écrit, le sens
    de la valeur est dit avant « mais »."""
    from pipeline import affichage as AF
    assert AF.avant_position("", False, True, "3,2", "dist", "4,1") == "plus loin que l'ensemble (3,2 km)"
    assert AF.avant_position("", False, True, "10,8", "ctx", "9,9") == "sous l'ensemble (10,8)"
    assert AF.avant_position("12 % sous l'ensemble", True, True, "10,8", "prof", "9,5") == "12 % sous l'ensemble"
    deux = AF.cle_contraire_plusieurs(["haut", "pres"], "epci")
    assert deux.count("L'ensemble est calculé") == 1 and ", ou " in deux


def test_doi_d_une_autre_version_jamais_donne_comme_le_sien():
    """Audit du 6 novembre 2026 : le filigrane de l'atlas et la couverture du rapport attachaient aux données du 6 novembre
    le DOI de la version archivée du 30 octobre. Le filigrane ne donne le DOI propre qu'à une version archivée, la
    couverture dit « dernière version archivée » ; un lien ne prend jamais la parenthèse qui suit l'adresse."""
    noyau = (config.RACINE / "atlas" / "moteur" / "noyau.js").read_text(encoding="utf-8")
    assert "D.citation.archivee!==false&&!D.citation.posterieure" in noyau
    r = (GAB / "rapport.html").read_text(encoding="utf-8")
    assert "DOI de la dernière version archivée du rapport" in r
    from pipeline.site import liens
    h = str(liens("Version de travail (https://doi.org/10.5281/zenodo.1), https://ubicura.fr/x.html."))
    assert 'href="https://doi.org/10.5281/zenodo.1"' in h and 'href="https://ubicura.fr/x.html"' in h


def test_phrases_vraies_sur_mayotte_et_sans_cause():
    """Audit du 6 novembre 2026 : Comparer disait Mayotte écartée des comparaisons alors qu'elle compte dans les repères
    et les positions ; le chapeau des revenus prêtait une cause (« que les territoires aisés attirent »)."""
    c = (GAB / "comparer.html").read_text(encoding="utf-8")
    assert "écartée des croisements et des comparaisons" not in c and "compte dans les repères" in c
    d = (config.RACINE / "pipeline" / "domaines.py").read_text(encoding="utf-8")
    assert "attirent davantage" not in d


def test_adresse_d_une_source_sans_espace():
    """Audit du 6 novembre 2026 : « https://data.geopf.fr/wfs/ows (ADMINEXPRESS…) » entier dans le lien."""
    assert '<a href="{{ p.split(" ")[0] }}">' in (GAB / "donnees_sources.html").read_text(encoding="utf-8")
    page = SITE / "donnees-sources.html"
    if page.exists():
        hrefs = re.findall(r'href="([^"]*)"', page.read_text(encoding="utf-8"))
        if any("wfs/ows" in h for h in hrefs) and not any(" " in h for h in hrefs if "wfs/ows" in h):
            assert not [h for h in hrefs if h.startswith("http") and " " in h]


def test_atlas_sans_palmares_et_couleurs_selon_la_regle():
    """Audit du 6 novembre 2026 sur la liste des décisions : l'atlas nommait « les territoires les moins et les mieux
    dotés » (règle 13, pas de palmarès), et ses barres d'indice se coloraient hors de la marge 0,8 à 1,25 et du hasard."""
    at = (config.RACINE / "atlas" / "moteur" / "atlas.js").read_text(encoding="utf-8")
    assert "Les territoires les moins et les mieux dotés" not in at and "Les mieux dotés</h3>" not in at
    assert "marque=(ind<80||ind>125)&&stE!==0" in at and "c=!marque?dv[3]" in at
    assert "dans la marge ou au hasard" in at


def test_atlas_a_le_pied_de_page_et_une_source_entiere():
    """Audit du 6 novembre 2026 : l'atlas n'avait pas de pied de page (décision 9), sa mention de source était coupée au
    téléphone, et l'accueil montrait deux barres de défilement."""
    tpl = (config.RACINE / "atlas" / "atlas_template.html").read_text(encoding="utf-8")
    assert '<footer class="pied-atlas">' in tpl and '<a href="publications.html">Publications</a>' in tpl
    assert ".vue-accueil .grid.carte .defile{overflow:visible" in tpl
    assert 'sg.setAttribute("textLength",max)' in (config.RACINE / "atlas" / "moteur" / "noyau.js").read_text(encoding="utf-8")


def test_fiche_part_sans_structure_comme_sa_reglette():
    """Audit du 6 novembre 2026 : « (aucun : 49 %) » sur la réglette et « Aucune structure, comme dans 54 % » sur la même
    ligne. Les deux comptent les mêmes territoires, ceux dont la valeur est publiée."""
    py = (config.RACINE / "pipeline" / "fiche_territoire.py").read_text(encoding="utf-8")
    i = py.index("def _part_aucun")
    corps = py[i:py.index("\ndef ", i + 10)]
    assert "S.v" in corps and "S.n" not in corps


def test_evolutions_et_doi_des_fiches():
    """Audit du 6 novembre 2026 : évolutions de la DREES à deux décimales (« de 3,73 à 3,92 ») sur les fiches, « mais »
    sans antécédent dans les Repères, et DOI général sans « toutes les versions »."""
    py = (config.RACINE / "pipeline" / "fiche_territoire.py").read_text(encoding="utf-8")
    assert 'nombre(v(x, "densite_debut") * k, "taux")' in py and "nombre_rapport(v(x, \"densite_debut\")" not in py
    g = (GAB / "fiche_territoire.html").read_text(encoding="utf-8")
    assert "{{ R.cmp.ref }} km ; {% if R.cmp.mais %}mais" not in g
    assert "DOI {% if doi_toutes %}de toutes les versions" in g


def test_methode_dit_pourquoi_les_moyens_ne_sont_pas_montres():
    """Règles du projet, partie 3 (Lucas, 30 octobre 2026) : la page méthode dit pourquoi les moyens des suicides ne sont jamais
    montrés par territoire, avec ses sources, et sans allusion à une offre payante."""
    m = (GAB / "methode.html").read_text(encoding="utf-8")
    i = m.index('id="moyens-suicide"')
    bloc = m[i:i + 2500]
    assert "Papageno" in bloc and "who.int/publications/i/item/9789240076846" in bloc and "Werther" in bloc
    assert "professionnel" not in bloc.lower()


def test_raisons_sociales_gardees_telles_quelles():
    """Lucas, 6 novembre 2026 : « Centre rééducation déficients visuels » (Clermont-Ferrand) garde son nom, comme la MDPH
    dans sa forme abrégée du RPPS ; le contrôle du langage relève toujours le mot ailleurs."""
    from pipeline import libelles as L
    assert not L.termes_proscrits("centre reeducation deficients visuels clermont ferrand")
    assert not L.termes_proscrits("gip maison dep personnes handicapees plerin")
    assert L.termes_proscrits("des enfants deficients")


def _rapports_du_jour():
    """Rapports générés après les corrections du 6 novembre 2026 (11 h 30), pour ne pas juger des fichiers plus anciens."""
    import datetime
    d = sorted(p for p in config.RESULTATS.glob("20*") if (p / "site_data.json").exists())[-1]
    limite = datetime.datetime(2026, 11, 6, 11, 30).timestamp()
    fichiers = [f for f in [d / "rapport_sante_mentale.md", d / "rapport_sante.md", *sorted((d / "territoires").glob("*.md"))]
                if f.exists() and f.stat().st_mtime > limite]
    return fichiers


def test_rapports_non_archives_ne_se_disent_pas_archives():
    """Audit du 6 novembre 2026 : les rapports du 6 novembre se disaient « archivés » sous le DOI de la version du
    30 octobre. Une version de travail le dit, la phrase « archivées avec un identifiant permanent » reste aux versions
    archivées."""
    from pipeline import site
    for nom in ("rapport.html", "territoire.html"):
        h = (GAB / nom).read_text(encoding="utf-8")
        assert '"ersion de travail" in citation.texte' in h and "Ces données sont une version de travail" in h, nom
    c = site.citation("sante-mentale", "Rapport santé mentale", "6 novembre 2026", "2026-11-06")
    if not site.mention_version("2026-11-06")["archivee"]:
        assert "ersion de travail" in c["texte"] or "Dernière version archivée" in c["texte"]
    t = site.citation_territoire("Offre de soins en santé mentale, Eure", "6 novembre 2026", "dep-27-sante-mentale.html",
                                 "2026-11-06")
    if not site.mention_version("2026-11-06")["archivee"]:
        assert "ersion de travail" in t["texte"]


def test_evolutions_drees_avec_les_arrondis_des_pages():
    """Audit du 6 novembre 2026 : « de 17,31 à 16,61 », deux décimales au-dessus de 1. Les évolutions de la DREES
    suivent affichage.nombre (genre « taux »)."""
    from pipeline import rapport_bases as RB
    assert RB._dens(17.31) == "17,3" and RB._dens(0.884) == "0,88" and RB._dens(2.04) == "2,0"
    src = (config.RACINE / "pipeline" / "rapport_bases.py").read_text(encoding="utf-8")
    assert '{"debut": _dens, "fin": _dens' in src and "f2 = lambda v: nombre(v, 2)" not in src
    for f in _rapports_du_jour():
        t = f.read_text(encoding="utf-8")
        i = t.find("volution depuis 2016")
        if i >= 0:
            bloc = t[i:i + 3000].split("\n\n#")[0]
            assert not re.search(r"\| [1-9]\d*,\d\d \|", bloc), (f.name, bloc[:300])


def test_rapports_par_territoire_nomment_repere_et_position_comme_les_fiches():
    """Audit du 6 novembre 2026 : les rapports par territoire écrivaient « milieu des départements », « quart le mieux
    doté », « sous le milieu », « Taux de la France ». Repère nommé par affichage.ENSEMBLE ou MEDIANE, position par
    affichage.position_txt."""
    from pipeline import affichage as AF
    from pipeline import rapport_territoire as RT
    assert RT.position(5, [1, 2, 3, 4, 5, 6, 7, 8], "dep") == AF.position_txt(4 / 7, "dep", "", 3 / 7)
    assert RT.position(1, [1, 2, 3], "reg") == "plus bas que toutes les autres régions"
    for nom in ("rapport_territoire.py", "rapport_bases.py"):
        src = (config.RACINE / "pipeline" / nom).read_text(encoding="utf-8")
        visibles = [l for l in src.splitlines() if not l.strip().startswith("#") and ('"' in l or "'" in l)]
        for mot in ("Milieu des", "milieu des départements", "quart le mieux doté\"", "sous le milieu\"",
                    "Taux de la France", "Départements semblables (milieu)"):
            assert not [l for l in visibles if mot in l], (nom, mot)
    for f in _rapports_du_jour():
        if f.parent.name == "territoires":
            t = f.read_text(encoding="utf-8")
            for mot in ("Milieu des", "quart le mieux doté", "sous le milieu", "au-dessus du milieu", "Taux de la France"):
                assert mot not in t, (f.name, mot)


def test_rapports_nationaux_sans_zero_seul_dans_les_tableaux_nommes():
    """Audit du 6 novembre 2026 : « Mayotte 0 » (outre-mer), « 0 | 0 % » (zones), « CAARUD 0 » (structures) dans les
    tableaux des rapports nationaux. Un compte ou une part nuls s'écrivent en mots."""
    from pipeline import rapport as R
    assert R._aucune(0) == "aucune" and R._aucun_habitant(0) == "aucun habitant" and R._aucun_habitant(0.122) != "aucun habitant"
    for f in _rapports_du_jour():
        if f.parent.name == "territoires":
            continue
        t = f.read_text(encoding="utf-8")
        for titre in ("Intercommunalités en zone peu dotée", "Les deux à la fois", "Au moins une de ces structures",
                      "| Profession | Hexagone |"):
            i = t.find(titre)
            if i < 0:
                continue
            tableau = t[i:].split("\n\n")[0]
            assert not re.search(r"\| 0( %)? \|", tableau), (f.name, titre)


# ---------------------------------------------------------------- audit 3 du 6 novembre 2026, rapports
def _apres_audit3(fichiers):
    """Fichiers écrits après les corrections de l'audit 3 du 6 novembre 2026 (13 h 45), pour ne pas juger les anciens."""
    import datetime
    limite = datetime.datetime(2026, 11, 6, 13, 45).timestamp()
    return [f for f in fichiers if f.exists() and f.stat().st_mtime > limite]


def _resultats_du_jour():
    return sorted(p for p in config.RESULTATS.glob("20*") if (p / "site_data.json").exists())[-1]


def test_cartes_des_rapports_ne_colorent_qu_au_dela_du_hasard():
    """Audit 3 (B6) : sur les cartes des rapports, une intercommunalité à 1 psychiatre pour environ 1,3 attendus était
    colorée en cuivre. La couleur suit la règle des fiches (affichage.couleur) : hors de 0,8 à 1,25 fois l'ensemble et
    au-delà du hasard, gris sinon."""
    from pipeline import cartes as C
    ref = 1.3 / 5629 * 1e4      # CC Aveyron Bas Ségala Viaur, 5 629 habitants, 1 psychiatre pour 1,3 attendu
    assert C.au_hasard({"a": (1 / 5629 * 1e4) / ref}, {"a": 1}, {"a": 5629}, ref) == {"a"}
    ref = 6.6 / 5156 * 1e4      # CC du Réquistanais, 4 psychologues pour 6,6 attendus
    assert C.au_hasard({"b": (4 / 5156 * 1e4) / ref}, {"b": 4}, {"b": 5156}, ref) == {"b"}
    ref = 10.0                  # 20 professionnels pour 100 attendus, au-delà du hasard : la couleur reste
    assert C.au_hasard({"c": .2}, {"c": 20}, {"c": 100000}, ref) == set()
    assert C.classe(.2, True) == C.GRIS and C.classe(.2) == 1
    src = (config.RACINE / "pipeline" / "rapport_territoire.py").read_text(encoding="utf-8")
    assert "effectifs=t.set_index" in src and "bases=t.set_index" in src
    g = (config.RACINE / "pipeline" / "graphiques.py").read_text(encoding="utf-8")
    assert g.count("cartes.au_hasard(") >= 2
    for f in _apres_audit3(sorted((_resultats_du_jour() / "territoires" / "graphiques").glob("*_carte*.svg"))):
        t = f.read_text(encoding="utf-8")
        assert "hasard" in t, f.name


def test_infobulles_des_rapports_dans_l_unite_et_les_arrondis_des_tableaux():
    """Audit 3 (B3, B5) : « Ain, 0,0 » pour des pédopsychiatres donnés pour 100 000 dans le tableau, « 0,8 pour 10 000 »
    sur la carte et « 0,75 » dans le tableau, « 0,0 pour 10 000 habitants, 0,0 fois l'ensemble »."""
    from pipeline import affichage as AF, cartes as C
    C.NOMS["x"] = "Territoire"
    e = lambda t: re.sub(r"[  ]", " ", t)  # noqa: E731
    assert e(C.info_territoire("x", .75, 1.0, 10000)) == "Territoire, 0,75 pour 10 000 habitants, 25 % sous l'ensemble"
    assert C.info_territoire("x", 0.0, 1.0) == "Territoire, " + AF.STATUTS["aucun"]
    assert e(C.info_territoire("x", .5, .18, 100000)).startswith("Territoire, 0,90 pour 100 000 habitants")
    assert C._info_point("x", 0.0, 100000) == "Territoire, " + AF.STATUTS["aucun"]
    assert e(C._info_point("x", .18, 100000)) == "Territoire, 1,8 pour 100 000 habitants"
    assert "pour 100 000 hab." in e(C.libelles_classes(1.2, fac=100000)[2])
    src = (config.RACINE / "pipeline" / "rapport_territoire.py").read_text(encoding="utf-8")
    assert '"fac": B.C.fac(p)' in src and "fac=B.C.fac(p)" in src
    for f in _apres_audit3(sorted((_resultats_du_jour() / "territoires" / "graphiques").glob("*.svg"))):
        t = f.read_text(encoding="utf-8")
        assert not re.search(r", 0,0( pour|<)|0,0 fois l", t), f.name


def test_nuage_suicide_densite_chaque_nombre_a_son_unite():
    """Audit 3 (B4) : « Aveyron, 9,4 et 1,3 pour 10 000 habitants », alors que 9,4 est un taux de suicide pour
    100 000. Chaque nombre de l'infobulle porte son unité."""
    import pandas as pd
    from pipeline import cartes as C, graphiques as G
    f = _resultats_du_jour() / "quadrants.csv"
    if not f.exists():
        return
    q = pd.read_csv(f, sep=";", decimal=",", dtype={"code": str})
    C.NOMS["12"] = "Aveyron"
    svg = G.quadrants({"quadrants": q}, {"psychiatre": "Psychiatre"}, {"suicides": "Décès par suicide"}, "psychiatre",
                      {"suicides": "pour 100 000 hab., standardisé sur l'âge"})
    infos = re.findall(r"<title>(Aveyron[^<]*)</title>", svg)
    assert infos and all("suicide" in i and "pour 100 000 habitants, psychiatres" in i for i in infos), infos


def test_rapports_par_territoire_sans_zero_seul_dans_les_tableaux():
    """Audit 3 (B9) : 5 362 cases « 0 » dans 208 rapports par territoire (« Chirurgien plasticien (pour 100 000) | 0 |
    0 | 2,2 », « Départements semblables (médiane) 0 »). Un zéro s'écrit en mots, comme sur les fiches."""
    import pandas as pd
    from pipeline import rapport as R
    df = pd.DataFrame({"a": ["x"], "n": [0], "p": [0.0]})
    t = R._tableau(df, ["a", "n", "p"], ["A", "N", "P"], {"n": str, "p": lambda v: "0 %"},
                   zero={"n": "aucun", "p": "aucun habitant"})
    assert "| x | aucun | aucun habitant |" in t
    assert R._aucun_accorde("Places d'hospitalisation de jour") == "aucune" and R._aucun_accorde("Lits") == "aucun"
    zero = re.compile(r"\| 0([,.]0+)?([\s\u00a0\u202f]?%)? (?=\|)")
    for f in _apres_audit3(sorted((_resultats_du_jour() / "territoires").glob("*.md"))):
        lignes = [l for l in f.read_text(encoding="utf-8").splitlines() if l.startswith("|")]
        assert not [l for l in lignes if zero.search(l)], (f.name, [l for l in lignes if zero.search(l)][:3])


def test_rapports_par_territoire_mediane_avec_article_et_unite_insecable():
    """Audit 3 : « Département médian est à 4,5 % » sans article ; « 100 / 000 » coupé dans l'en-tête des PDF."""
    from pipeline import affichage as AF, rapport as R, rapport_territoire as RT
    assert RT.LE_MEDIAN == {"dep": "Le département médian", "reg": "La région médiane", "epci": "L'intercommunalité médiane"}
    src = (config.RACINE / "pipeline" / "rapport_territoire.py").read_text(encoding="utf-8")
    assert "{AF.MEDIANE[T['niveau']]} est à" not in src and "{AF.MEDIANE['dep']} est à" not in src
    C = type("C", (), {"fac": lambda self, p: 100000})()
    assert R.entete_densite(C, ["x"]) == f"Pour 10{AF.FINE}000 habitants, pour 100{AF.FINE}000 pour les professions rares"
    for f in _apres_audit3(sorted((_resultats_du_jour() / "territoires").glob("*.md"))):
        t = f.read_text(encoding="utf-8")
        assert not re.search(r"(^|\. )(Département médian|Région médiane|Intercommunalité médiane) est", t, re.M), f.name
