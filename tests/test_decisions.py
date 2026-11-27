"""Une décision ou un défaut relevé par un audit, un test : ce qui a été tranché ne se perd plus sans qu'un test
échoue (remarque du 6 novembre 2026, la carte de l'accueil décidée le 2 novembre avait été oubliée). Tests sur
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


# Table des déplacements de la structure validée le 26 novembre 2026 (prototypes/structure_2026-11-25/notes.md) : ce qui
# quitte une page y laisse un renvoi, ou trouve une place nouvelle. (élément, place d'avant, place nouvelle, page
# construite où la place nouvelle se vérifie, marque qui la prouve). Rien ne disparaît sans place nouvelle (règle 18).
DEPLACEMENTS = [
    ("Atlas réglable intégré à l'accueil (carte, encadré du territoire)", "index.html, cadre « La carte, territoire par territoire »",
     "atlas.html entier, à un clic : « Ouvrir l’atlas » sous la carte des psychiatres de l'accueil", "index.html",
     'href="atlas.html">Ouvrir l’atlas</a>'),
    ("Carte des psychiatres par département", "domaine/sante-mentale.html, question 1",
     "gardée à sa place, et reprise sur l'accueil avec sa légende et son « Comment lire »", "index.html",
     'class="carte-accueil'),
    ("Chiffres de la France (trois tuiles)", "index.html, sous la carte", "en-tête de l'accueil, à droite, et page Offre de soins",
     "domaine/offre-de-soins.html", 'class="nationaux"'),
    ("Accès transversaux (Autour d'un lieu, Croiser, Rapports, Pour la recherche)", "index.html, bas de page",
     "liste unique d'outils de l'accueil", "index.html", 'href="rapports.html"><strong>Rapports</strong>'),
    ("Portes Santé mentale et Santé de l'Offre de soins", "domaine/offre-de-soins.html, deux portes",
     "têtes de liste des deux familles, avec leur texte", "domaine/offre-de-soins.html", 'id="t-fam-sm"'),
    ("Lien vers l'archive complète des données", "methode-fichiers.html, en tête",
     "« Les fichiers principaux », première carte", "methode-fichiers.html", "<strong>Toutes les données de la version</strong>"),
    ("Liste alphabétique des fichiers", "methode-fichiers.html, un tableau", "mêmes fichiers, rangés par thème",
     "methode-fichiers.html", 'class="theme-f"'),
    ("Liens « Ouvrir », « Lire », « Lire »", "territoires/index.html, trois colonnes",
     "« Fiche », « Rapport santé mentale », « Rapport santé », colonne « Pages du territoire »", "territoires/index.html",
     ">Rapport santé mentale</a>"),
    # la fenêtre « Croiser deux indicateurs » d'Explorer rejoint Croiser (planches 1 et 6)
    ("Nuage des territoires de « Croiser deux indicateurs »", "explorer.html, question du profil des habitants",
     "Croiser, encadré « Nuage des territoires »", "croiser.html", 'id="t-nuage">Nuage des territoires'),
    ("Échelle logarithmique de l'axe vertical du nuage", "explorer.html, réglage de la fenêtre",
     "Croiser, réglage « Échelle de l’axe vertical », logarithmique au départ", "croiser.html", 'data-ech="log"'),
    ("Données par territoire du nuage, tableau filtrable", "explorer.html, onglet de la fenêtre",
     "Croiser, encadré « Données par territoire »", "croiser.html", 'id="filtre-terr"'),
    ("Tableau des questions préparées entre départements", "explorer.html, onglet de la fenêtre",
     "Croiser, encadré « Questions préparées »", "croiser.html", 'id="table-prep"'),
    ("Fenêtre « Croiser deux indicateurs »", "explorer.html, question du profil des habitants",
     "renvoi « Réglages dans Croiser » à sa place", "explorer.html", 'id="cxCroiser"'),
]


def test_table_des_deplacements_rien_ne_disparait():
    """Structure du site validée le 26 novembre 2026 : chaque élément déplacé a sa place nouvelle dans le site construit
    (table DEPLACEMENTS), et ce qui partait de l'accueil y laisse un renvoi."""
    assert len(DEPLACEMENTS) >= 8 and all(len(d) == 5 and all(d) for d in DEPLACEMENTS)
    if not (SITE / "index.html").exists() or 'id="cadre-atlas"' in (SITE / "index.html").read_text(encoding="utf-8"):
        return   # site d'avant la structure du 26 novembre 2026
    manque = [(d[0], d[3]) for d in DEPLACEMENTS
              if not (SITE / d[3]).exists() or d[4] not in (SITE / d[3]).read_text(encoding="utf-8")]
    assert not manque, manque


def test_accueil_structure_du_26_novembre():
    """Accueil plus court (décision du 26 novembre 2026, planche_2_accueil) : la carte des psychiatres par département,
    avec sa légende de page, son « Comment lire », « Citer et exporter » et « Ouvrir l’atlas », à la place de l'atlas
    intégré (qui remplace la décision du 2 novembre) ; les chiffres de la France en tête avec la phrase des deux totaux ;
    une seule liste d'outils avec Rapports et Pour la recherche ; les questions de santé mentale vers leur section ; des
    étiquettes claires ; le texte d'aide « Commune, territoire ou indicateur »."""
    p = (GAB / "portail.html").read_text(encoding="utf-8")
    assert 'id="cadre-atlas"' not in p and 'class="transverse"' not in p
    for x in ('class="leg-carte"', "Ouvrir l’atlas", 'class="comment-lire lire-carte"', "deux_totaux", "data-citation",
              'href="rapports.html"', "Pour la recherche", 'placeholder="Commune, territoire ou indicateur"',
              "questions_sm"):
        assert x in p, x
    assert "escalier, inégalités" not in p and "<span>combinaisons</span>" not in p
    assert p.count('<nav class="outils') == 1
    idx = SITE / "index.html"
    if not idx.exists() or 'id="cadre-atlas"' in idx.read_text(encoding="utf-8"):
        return
    h = idx.read_text(encoding="utf-8")
    t = _texte(idx).replace(" ", " ").replace("\xa0", " ")
    fig = re.search(r'<section class="carte-accueil.*?</section>', h, flags=re.S).group(0)
    # la carte des psychiatres, zoomable, avec ses données ; sa légende de page (six classes et Mayotte), sur ordinateur
    # et au téléphone, et la valeur de l'échelle
    assert fig.count("<path") > 90 and "zoomable" in fig and 'data-donnees="donnees/' in fig
    assert fig.count('<li><i style="background:') == 12 and fig.count("Mayotte, données incomplètes") >= 2
    assert re.search(r"Écart à l’ensemble des départements, \d+,\d psychiatres pour 10 000 habitants", t)
    # la légende dessinée (texte de 8 unités) est hors du cadre : le dessin s'arrête au-dessus d'elle
    vb = int(re.search(r'viewBox="0 0 560 (\d+)"', fig).group(1))
    ys = [int(y) for y in re.findall(r'<rect x="8" y="(\d+)" width="14" height="12"', fig)]
    assert ys and vb < min(ys)
    assert "Sur les cartes, un département reste en gris" in t and "indice de Gini entre intercommunalités" in t
    # les deux totaux, avec le lien au titre de la page d'indicateur, et sa cible
    assert "le chiffre de la France compte chaque personne une fois" in t and "Pourquoi plusieurs totaux, et lequel citer" in t
    assert 'id="t-tot"' in (SITE / "indicateur" / "prof-psychologue.html").read_text(encoding="utf-8")
    # les questions mènent à leur section publiée, qui existe
    sm = (SITE / "domaine" / "sante-mentale.html").read_text(encoding="utf-8")
    liste = re.search(r'<ul class="questions">(.*?)</ul>', h, flags=re.S).group(1)
    cibles = re.findall(r'href="domaine/sante-mentale\.html#(q\d+)"', liste)
    assert len(cibles) == 4 and all(f'id="{q}"' in sm for q in cibles), cibles
    assert not re.search(r'<ul class="questions">(?:(?!</ul>).)*explorer\.html', h, flags=re.S)


def test_questions_un_seul_titre_et_un_seul_lieu():
    """Un seul lieu par question (26 novembre 2026) : la table unique (pipeline/questions.py) donne le titre de chaque
    question, le même dans les pages de famille, Offre de soins, l'accueil, les thèmes et Explorer ; chaque réglage
    mène à une ancre qui existe dans Explorer ; les questions qui se règlent sont celles de la planche (santé mentale 1,
    3, 4, 6, 10 et 11 dans Explorer, 7 et 8 dans Croiser ; santé 1, 3, 4 et 6 dans Explorer, 7 dans Croiser)."""
    from pipeline import pages_domaine as PD, questions as QQ, themes as TH
    outil = {fam: {k: (QQ.reglage(q, fam) or (None, None))[1] for k, q in enumerate(L, 1)} for fam, L in QQ.FAMILLES.items()}
    assert [k for k, o in outil["sm"].items() if o == "Explorer"] == [1, 3, 4, 6, 10, 11]
    assert [k for k, o in outil["sm"].items() if o == "Croiser"] == [7, 8]
    assert [k for k, o in outil["sante"].items() if o == "Explorer"] == [1, 3, 4, 6]
    assert [k for k, o in outil["sante"].items() if o == "Croiser"] == [7]
    assert [q[0].replace("⁠", "") for q in PD.QUESTIONS["sm"]] == [q["titre"] for q in QQ.FAMILLES["sm"]]
    anciens = ("moins bien dotés", "vit-on", "L'addictologie, de l'offre", "L’addictologie, de l’offre")
    for th in TH.THEMES:
        assert not any(a in t for _u, t in th.get("explorer", []) for a in anciens), th["id"]
    assert QQ.EXPLORER["qInegalites"] == QQ.NIVEAU_DE_VIE and QQ.EXPLORER["qAddicto"] == QQ.ADDICTO
    assert set(QQ.EXPLORER_SEULEMENT) <= set(QQ.EXPLORER)
    ex = SITE / "explorer.html"
    if ex.exists():
        h = ex.read_text(encoding="utf-8")
        for fam, L in QQ.FAMILLES.items():
            for q in L:
                r = QQ.reglage(q, fam)
                if r and r[1] == "Explorer":
                    ancre = r[0].split("#", 1)[1].split("?", 1)[0]
                    assert f'id="{ancre}"' in h, (fam, q["titre"], ancre)
        for qid in QQ.EXPLORER:
            assert f'id="{qid}' in h, qid


def test_offre_de_soins_table_des_questions():
    """La page « Offre de soins » devient la table des questions de l'offre (planche_1_offre_de_soins) : les chiffres de
    la France, chaque question des deux familles vers sa section, son réglage sur sa propre ligne, les deux questions
    d'Explorer seulement, les portes de l'atlas et des indicateurs."""
    from pipeline import questions as QQ
    f = SITE / "domaine" / "offre-de-soins.html"
    if not f.exists() or 'class="questions-offre"' not in f.read_text(encoding="utf-8"):
        return
    h = f.read_text(encoding="utf-8")
    assert len(re.findall(r'<section class="nationaux"', h)) == 1 and h.count('<span class="n">') == 3
    for fam, L in QQ.FAMILLES.items():
        page = QQ.PAGES[fam][0]
        cible = (SITE / "domaine" / f"{page}.html").read_text(encoding="utf-8")
        for k, q in enumerate(L, 1):
            m = re.search(rf'<li><a href="{page}\.html#q{k}">([^<]+)</a>(<a class="reg-q" href="\.\./([^"]+)">la '
                          rf'régler dans (\w+)</a>)?</li>', h)
            assert m, (fam, k)
            lu = re.sub("[  ]", " ", _html.unescape(m.group(1)).replace("⁠", ""))
            assert lu == q["titre"], (fam, k, lu)
            assert f'id="q{k}"' in cible
            r = QQ.reglage(q, fam)
            assert (m.group(4) if m.group(2) else None) == (r[1] if r else None), (fam, k)
            if r:
                assert _html.unescape(m.group(3)) == r[0]
    for qid in QQ.EXPLORER_SEULEMENT:
        assert f'href="../explorer.html#{qid}"' in h
    assert "Dans Explorer seulement" in h and "L’atlas et les indicateurs" in h
    assert 'href="../atlas.html"><strong>L’atlas</strong>' in h and 'href="../indicateurs.html#dom=' in h


def test_menu_allume_l_entree_de_la_page():
    """Entrée du menu allumée (26 novembre 2026, planche_1_lieux_schema) : l'atlas allume Territoires ; À venir, Journal
    et Publications allument Méthode et données ; les pages de famille gardent Offre de soins."""
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(GAB)))
    attendu = {"atlas": "Territoires", "a-venir": "Méthode et données", "journal": "Méthode et données",
               "publications": "Méthode et données", "offre_famille": "Offre de soins", "offre": "Offre de soins",
               "territoires": "Territoires", "indicateur": "Domaines"}
    for page, entree in attendu.items():
        h = env.get_template("nav.html").render(racine="", page=page, nom_projet="Ubi Cura", sous_titre="")
        assert re.findall(r'<a class="l on"[^>]*>([^<]+)</a>', h) == [entree], page
    for nom, entree in (("atlas.html", "Territoires"), ("a-venir.html", "Méthode et données"),
                        ("journal.html", "Méthode et données"), ("publications.html", "Méthode et données")):
        f = SITE / nom
        if not f.exists():
            continue
        nav = re.search(r'<div class="liens" id="liens-site">(.*?)</div>', f.read_text(encoding="utf-8"), flags=re.S)
        if nav and "l on" in nav.group(1):
            assert re.findall(r'<a class="l on"[^>]*>([^<]+)</a>', nav.group(1)) == [entree], nom


def test_territoires_liens_qui_disent_ou_ils_menent():
    """Territoires (planche_7_territoires) : « Fiche », « Rapport santé mentale », « Rapport santé » dans une colonne
    « Pages du territoire », à la place de « Ouvrir », « Lire », « Lire », et une porte vers l'atlas."""
    g = (GAB / "territoires.html").read_text(encoding="utf-8")
    assert ">Ouvrir</a>" not in g and ">Lire</a>" not in g and "<th>Pages du territoire</th>" in g
    assert "{{ page_atlas }}" in g and "(PDF)</a>" not in g
    f = SITE / "territoires" / "index.html"
    if f.exists() and "Pages du territoire" in f.read_text(encoding="utf-8"):
        h = f.read_text(encoding="utf-8")
        lignes = re.findall(r'<td class="pages-t">(.*?)</td>', h, flags=re.S)
        assert len(lignes) > 100 and all(">Fiche</a>" in x for x in lignes)
        assert all(">Rapport santé mentale</a>" in x and ">Rapport santé</a>" in x for x in lignes)
        assert 'href="../atlas.html">L’atlas</a>' in h


def test_telecharger_par_theme():
    """Télécharger (planche_7_telecharger) : l'archive complète et trois fichiers principaux en tête, puis chaque fichier
    dans un thème, avec son niveau, et un seul champ « Filtrer le tableau ». Le thème vient de pipeline/dictionnaire.py :
    un fichier ajouté y prend place de lui-même ; aucun fichier n'est perdu."""
    from pipeline import dictionnaire as DI
    assert DI.theme_fichier("effectifs_epci_all.csv") == "Professionnels"
    assert DI.theme_fichier("lieux_soins_dep.csv") == "Structures de soins"
    assert DI.theme_fichier("prevalences_odbl.csv") == "Assurance Maladie, sous licence ODbL"
    assert DI.theme_fichier("concordance_effectifs.csv") == "Contrôles, concordances et sensibilité"
    assert DI.theme_fichier("liste_indicateurs.csv") == "Références"
    assert DI.theme_fichier("un_fichier_nouveau.csv") in DI.ORDRE_THEMES
    assert DI.niveau_fichier("effectifs_dep_all.csv") == "Département" and DI.niveau_fichier("lisa.csv") == "Plusieurs ou aucun"
    assert set(DI.ORDRE_THEMES) == {t for t, _d, _m in DI.THEMES_FICHIERS} | {DI.THEME_REFERENCES[0], DI.THEME_CONTROLES[0]}
    f = SITE / "methode-fichiers.html"
    if not f.exists() or 'class="theme-f"' not in f.read_text(encoding="utf-8"):
        return
    h = f.read_text(encoding="utf-8")
    themes = re.findall(r'<h3 class="theme-f" id="([^"]+)">([^<]+)<span>(\d+)(?:\xa0| | )fichiers?', h)
    assert [t[1] for t in themes] == [t for t in DI.ORDRE_THEMES if any(x[1] == t for x in themes)] and len(themes) >= 7
    tables = re.findall(r'<table class="simple fichiers">.*?</table>', h, flags=re.S)
    n = sum(x.count("<tr><td>") for x in tables)
    assert n == sum(int(t[2]) for t in themes) and n >= 140
    dossier = sorted((SITE / "donnees").glob("20*"))[-1]
    publies = {p.name for p in dossier.glob("*.csv")} | {p.name for p in dossier.glob("*.csv.zip")}
    assert len(publies) == n, (len(publies), n)
    assert h.count('id="filtre-fichiers"') == 1 and "filtrable fichiers" not in h
    principaux = re.search(r'<ul class="principaux">(.*?)</ul>', h, flags=re.S).group(1)
    assert principaux.count("<li>") == 1 + len(DI.FICHIERS_PRINCIPAUX)
    assert all(x in principaux for x in DI.FICHIERS_PRINCIPAUX)


def test_offre_de_soins_mene_a_l_atlas():
    """Remarque du 6 novembre 2026 : depuis le menu à six entrées, l'atlas n'était plus atteint que par le pied de
    page. La page « Offre de soins » le propose à côté des deux familles, et ses pages allument l'entrée « Offre de soins »."""
    p = (GAB / "page_domaine.html").read_text(encoding="utf-8")
    assert '<a href="../{{ page_atlas }}"><strong>L’atlas</strong>' in p
    py = (config.RACINE / "pipeline" / "pages_domaine.py").read_text(encoding="utf-8")
    assert 'page="domaines", titre=centre["nom"]' not in py and 'page="offre", titre=centre["nom"]' in py
    # les pages des deux familles ont leur propre clé, qui allume l'entrée « Offre de soins » (nav.html, 8 novembre 2026)
    assert 'page="offre_famille", titre=titre, classe_main="domaine", centre=True' in py
    assert "'offre_famille': 'offre'" in (GAB / "nav.html").read_text(encoding="utf-8")


def test_comment_lire_jamais_replie_derriere_un_bouton():
    """Décision du 5 novembre 2026, « Comment lire » toujours visible : l'audit du 6 novembre en trouvait encore
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
    """Règles du projet, partie 3 (30 octobre 2026) : la page méthode dit pourquoi les moyens des suicides ne sont jamais
    montrés par territoire, avec ses sources, et sans allusion à une offre payante."""
    m = (GAB / "methode.html").read_text(encoding="utf-8")
    i = m.index('id="moyens-suicide"')
    bloc = m[i:i + 2500]
    assert "Papageno" in bloc and "who.int/publications/i/item/9789240076846" in bloc and "Werther" in bloc
    assert "professionnel" not in bloc.lower()


def test_raisons_sociales_gardees_telles_quelles():
    """Décision du 6 novembre 2026 : « Centre rééducation déficients visuels » (Clermont-Ferrand) garde son nom, comme la MDPH
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
    else:
        # une version archivée se cite par son propre DOI, jamais par celui d'une autre version (7 novembre 2026)
        propre = site.doi_version("sante-mentale", "2026-11-06")
        assert propre and propre in c["texte"], c["texte"]


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


def test_etiquettes_de_theme_completes():
    """Chaque indicateur du catalogue unique a sa ligne dans pipeline/themes_indicateurs.csv (thèmes et marque sensible),
    aucun thème inconnu, aucun indicateur sensible proposé d'office avec la santé mentale (décision du
    8 novembre 2026, navigation, étape 2 ; liste à cocher d'une nouvelle base, étape 9 quater)."""
    import json
    from pipeline import affichage as AF, config, themes as TH
    dernier = sorted(p for p in config.RESULTATS.glob("20*") if (p / "site_data.json").exists())[-1]
    sd = json.loads((dernier / "site_data.json").read_text(encoding="utf-8"))
    pb = TH.controler([e["id"] for e in AF.catalogue(sd, dernier)])
    assert not pb, pb[:10]



def test_aucun_caractere_de_controle_dans_les_gabarits_et_l_atlas():
    """Défaut vu à l'œil le 8 novembre 2026 : la flèche de « Autour d'un lieu » (colonne Outils de l'accueil) s'affichait
    en carré, l'échappement CSS \2192 ayant été lu comme un caractère de contrôle. Aucun gabarit, style ou script de
    l'atlas n'en contient."""
    fichiers = [f for d in (GAB, config.RACINE / "atlas" / "moteur") for f in d.rglob("*")
                if f.is_file() and f.suffix in (".css", ".html", ".js")]
    assert fichiers
    pb = [f"{f.relative_to(config.RACINE)}:{i}" for f in fichiers
          for i, l in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
          if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", l)]
    assert not pb, "caractère de contrôle : " + ", ".join(pb[:10])


def test_mediane_jamais_arrondie_sous_sa_valeur_apres_moins_de():
    """Relecture indépendante du 8 novembre 2026 : « la moitié des habitants vit à moins de 2 minutes » pour une médiane de
    2,3 minutes. Une médiane écrite après « moins de » garde sa décimale, jamais arrondie à l'unité inférieure."""
    import re
    for f in ("rapport.py", "constats.py", "fiche_territoire.py", "affichage.py"):
        py = (config.RACINE / "pipeline" / f).read_text(encoding="utf-8")
        assert not re.search(r"moins de \{nombre\([^}]*median[^}]*, 0\)", py), f


# l'article de chacun des 101 départements dans la réponse de la recherche, relu un par un le 9 novembre 2026 : « en »
# devant un nom féminin qui commence par une consonne, « dans la » devant un nom simple d'une syllabe (Larousse, article
# « en », reponses.DANS_LA)
DANS_DEPARTEMENTS = {
    "01": "dans l’Ain", "02": "dans l’Aisne", "03": "dans l’Allier", "04": "dans les Alpes-de-Haute-Provence",
    "05": "dans les Hautes-Alpes", "06": "dans les Alpes-Maritimes", "07": "en Ardèche", "08": "dans les Ardennes",
    "09": "en Ariège", "10": "dans l’Aube", "11": "dans l’Aude", "12": "dans l’Aveyron",
    "13": "dans les Bouches-du-Rhône", "14": "dans le Calvados", "15": "dans le Cantal", "16": "en Charente",
    "17": "en Charente-Maritime", "18": "dans le Cher", "19": "en Corrèze", "21": "en Côte-d'Or",
    "22": "dans les Côtes-d'Armor", "23": "dans la Creuse", "24": "en Dordogne", "25": "dans le Doubs",
    "26": "dans la Drôme", "27": "dans l’Eure", "28": "en Eure-et-Loir", "29": "dans le Finistère",
    "2A": "en Corse-du-Sud", "2B": "en Haute-Corse", "30": "dans le Gard", "31": "en Haute-Garonne",
    "32": "dans le Gers", "33": "en Gironde", "34": "dans l’Hérault", "35": "en Ille-et-Vilaine", "36": "dans l’Indre",
    "37": "en Indre-et-Loire", "38": "en Isère", "39": "dans le Jura", "40": "dans les Landes",
    "41": "dans le Loir-et-Cher", "42": "dans la Loire", "43": "en Haute-Loire", "44": "en Loire-Atlantique",
    "45": "dans le Loiret", "46": "dans le Lot", "47": "dans le Lot-et-Garonne", "48": "en Lozère",
    "49": "en Maine-et-Loire", "50": "dans la Manche", "51": "dans la Marne", "52": "en Haute-Marne",
    "53": "en Mayenne", "54": "en Meurthe-et-Moselle", "55": "dans la Meuse", "56": "dans le Morbihan",
    "57": "en Moselle", "58": "dans la Nièvre", "59": "dans le Nord", "60": "dans l’Oise", "61": "dans l’Orne",
    "62": "dans le Pas-de-Calais", "63": "dans le Puy-de-Dôme", "64": "dans les Pyrénées-Atlantiques",
    "65": "dans les Hautes-Pyrénées", "66": "dans les Pyrénées-Orientales", "67": "dans le Bas-Rhin",
    "68": "dans le Haut-Rhin", "69": "dans le Rhône", "70": "en Haute-Saône", "71": "en Saône-et-Loire",
    "72": "dans la Sarthe", "73": "en Savoie", "74": "en Haute-Savoie", "75": "à Paris", "76": "en Seine-Maritime",
    "77": "en Seine-et-Marne", "78": "dans les Yvelines", "79": "dans les Deux-Sèvres", "80": "dans la Somme",
    "81": "dans le Tarn", "82": "dans le Tarn-et-Garonne", "83": "dans le Var", "84": "dans le Vaucluse",
    "85": "en Vendée", "86": "dans la Vienne", "87": "en Haute-Vienne", "88": "dans les Vosges", "89": "dans l’Yonne",
    "90": "dans le Territoire de Belfort", "91": "en Essonne", "92": "dans les Hauts-de-Seine",
    "93": "en Seine-Saint-Denis", "94": "dans le Val-de-Marne", "95": "dans le Val-d'Oise", "971": "en Guadeloupe",
    "972": "en Martinique", "973": "en Guyane", "974": "à La Réunion", "976": "à Mayotte"}


def test_dans_chaque_departement():
    """Contre-audit de la recherche du 8 novembre 2026 : « dans la Lozère », « dans la Seine-Saint-Denis ». La réponse
    écrit « en Lozère », « en Seine-Saint-Denis », « en Nouvelle-Aquitaine », mais « dans la Manche », pour chacun des
    101 départements (liste relue un par un), dans le code et dans les fichiers du site construit."""
    from pipeline import reponses as R
    assert len(DANS_DEPARTEMENTS) == 101
    noms = {r["code"]: r["nom"] for r in json.loads((config.BRUT / "ref_departements.json").read_text(encoding="utf-8"))}
    faux = {c: R.dans("dep", c, noms[c]) for c, d in DANS_DEPARTEMENTS.items() if R.dans("dep", c, noms[c]) != d}
    assert not faux, faux
    assert R.dans("reg", "75", "Nouvelle-Aquitaine") == "en Nouvelle-Aquitaine"
    assert R.dans("reg", "24", "Centre-Val de Loire") == "en Centre-Val de Loire"
    # communes sans intercommunalité (relecture indépendante du 9 novembre 2026)
    assert R.dans("epci", "C85113", "L'Île-d'Yeu") == "à l'Île-d'Yeu" and R.dans("epci", "C29083", "Île-de-Sein") == "à l'Île-de-Sein"
    assert set(R.DANS_LA) == {c for c, d in DANS_DEPARTEMENTS.items() if d.startswith("dans la ")}
    dossier = SITE / "territoire" / "dep"
    if dossier.exists():
        lus = {f.stem: json.loads(f.read_text(encoding="utf-8")).get("dans") for f in dossier.glob("*.json")}
        if any(v and v.startswith("en Lozère") for v in lus.values()):   # site reconstruit depuis la correction
            assert {c: v for c, v in lus.items() if v != DANS_DEPARTEMENTS.get(c)} == {}


def test_pluriel_des_rapports_comme_celui_des_reponses():
    """Contre-audit de la recherche du 8 novembre 2026 : le pluriel des rapports (lecture.pluriel) arrêtait l'accord à
    « et » (« chirurgiens thoraciques et cardiovasculaire »). Il suit la règle de la recherche (reponses.pluriel_nom)
    pour toutes les professions du dernier site construit."""
    from pipeline.lecture import pluriel
    from pipeline.reponses import pluriel_nom
    assert pluriel("Chirurgien thoracique et cardiovasculaire") == "chirurgiens thoraciques et cardiovasculaires"
    assert pluriel("Chirurgien viscéral et digestif") == "chirurgiens viscéraux et digestifs"
    assert pluriel("Oto-rhino-laryngologiste (ORL)") == "oto-rhino-laryngologistes (ORL)"
    assert pluriel("Médecin, spécialité non renseignée") == "médecins, spécialité non renseignée"
    assert pluriel("Technicien de laboratoire") == "techniciens de laboratoire"
    ds = sorted(d for d in config.RESULTATS.glob("20*") if (d / "site_data.json").exists())
    if not ds:
        return
    sd = json.loads((ds[-1] / "site_data.json").read_text(encoding="utf-8"))
    p = sd.get("professions") or {}
    libs = {x["libelle"] for x in (p.values() if isinstance(p, dict) else p) if isinstance(x, dict) and x.get("libelle")}
    assert libs
    faux = {l: (pluriel(l), pluriel_nom(l)) for l in libs if pluriel(l) != pluriel_nom(l)}
    assert not faux, faux


def test_arrondissements_dans_la_recherche():
    """Contre-audit de la recherche du 8 novembre 2026 : « Paris 15e », « Lyon 3e », « Marseille 8e » ne trouvaient
    rien. Les 45 arrondissements municipaux du référentiel sont dans l'index de la recherche, avec la commune et
    l'intercommunalité de leur commune, et chercher.js les trouve sous leurs formes d'usage (essais du navigateur :
    outils/controle_recherche.py)."""
    from pipeline import portail as P
    ref = json.loads((config.BRUT / "ref_communes.json").read_text(encoding="utf-8"))
    attendus = {c["code"]: c["commune"] for c in ref if c.get("type") == "arrondissement-municipal"}
    assert len(attendus) == 45 and set(attendus.values()) == {"75056", "69123", "13055"}
    js = (GAB / "presentation" / "chercher.js").read_text(encoding="utf-8")
    assert "d.arrondissements" in js and "function rangs(" in js
    # la recherche de l'accueil, du comparateur et de « Autour d'un lieu » aussi ; un arrondissement choisi vaut sa
    # commune, la seule que connaissent ces pages
    acc = (GAB / "presentation" / "recherche.js").read_text(encoding="utf-8")
    assert "d.arrondissements" in acc and "function formes(" in acc and "choisir(cible(commune(courant[0]))" in acc
    assert '"arrondissements": arrondissements' in (config.RACINE / "pipeline" / "portail.py").read_text(encoding="utf-8")
    rj = SITE / "presentation" / "recherche.json"
    if rj.exists():
        d = json.loads(rj.read_text(encoding="utf-8"))
        if "arrondissements" in d:   # site reconstruit depuis la correction
            assert {a[0]: a[5] for a in d["arrondissements"]} == attendus
            epci = {c[0]: c[4] for c in d["communes"]}
            assert all(a[4] == epci[a[5]] for a in d["arrondissements"])
    assert P.recherche  # la fonction qui les écrit


def test_recherche_suit_le_catalogue():
    """Décision du 9 novembre 2026 : la recherche de l'en-tête s'adapte aux bases et variables ajoutées. L'index est fabriqué
    depuis le catalogue unique (portail.catalogue) ; sur le site construit, ses indicateurs sont exactement ceux de
    presentation/catalogue.json, chacun a sa réponse directe, et chaque thème et question d'Explorer y est
    (outils/controle_recherche.catalogue_recherche)."""
    import sys
    sys.path.insert(0, str(config.RACINE / "outils"))
    import controle_recherche as CR
    py = (config.RACINE / "pipeline" / "portail.py").read_text(encoding="utf-8")
    assert "for i in catalogue(site_data) if i.get(\"label\")" in py and "for th in TH.THEMES:" in py
    pb = CR.catalogue_recherche()
    assert not pb, pb[:10]


def test_commune_hors_intercommunalite_ecrite_avec_son_article():
    """Contre-audit de la recherche du 8 novembre 2026 : la fiche d'Ouessant écrivait « Aucun psychiatre n'est inscrit
    dans Ouessant ». Une commune hors intercommunalité (code en C) est sujet des phrases sous la forme « la commune
    d'Ouessant » ; la recherche écrit « à Ouessant », sans « dont Ouessant fait partie »."""
    from pipeline import fiche_territoire as FT
    from pipeline import reponses as R
    assert FT.nom_article("epci", "C29155", "Ouessant") == "la commune d'Ouessant"
    assert FT.nom_article("epci", "C85113", "L'Île-d'Yeu") == "la commune de l'Île-d'Yeu"
    assert FT.nom_article("epci", "C22016", "Île-de-Bréhat") == "la commune de l'Île-de-Bréhat"
    assert FT.nom_article("epci", "C29083", "Île-de-Sein") == "la commune de l'Île-de-Sein"
    assert FT.nom_article("epci", "241200187", "CA Rodez Agglomération") == FT.avec_article("CA Rodez Agglomération")
    assert FT.nom_article("dep", "12", "Aveyron") == "Aveyron"
    assert R.dans("epci", "C29155", "Ouessant") == "à Ouessant"
    assert "function seule(" in (GAB / "presentation" / "chercher.js").read_text(encoding="utf-8")
    # arrivée par la recherche de l'accueil ou « Autour d'un lieu » (?commune=29155) : pas de « fait partie de » sur sa
    # propre fiche
    assert '(f.code[:1] == "C")|tojson' in (GAB / "fiche_territoire.html").read_text(encoding="utf-8")
    for f in sorted((SITE / "territoire" / "epci").glob("C*.html")) if (SITE / "territoire" / "epci").exists() else []:
        t = _texte(f)
        nom = json.loads(f.with_suffix(".json").read_text(encoding="utf-8"))["nom"] if f.with_suffix(".json").exists() else None
        if nom and FT.nom_article("epci", f.stem, nom) in t:   # fiche reconstruite depuis la correction
            assert not re.search(r"\b(dans|Pour) " + re.escape(nom) + r"\b", t), f.name
