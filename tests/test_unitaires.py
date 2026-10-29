"""Tests des briques statistiques et de classement.  python tests/test_unitaires.py"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import analyses as A  # noqa: E402
from pipeline.sources import rpps  # noqa: E402
from pipeline.util import norm, trouver_colonne  # noqa: E402



def test_dependances_compensation():
    """Cas construit, y dépend de b et négativement de a, a et b corrélés positivement : a seul n'a presque pas de
    lien, le coefficient de a dépend de b."""
    from pipeline.croisements_indicateurs import dependances
    rng = np.random.default_rng(1)
    b = rng.normal(size=400)
    a = .6 * b + .8 * rng.normal(size=400)
    c = rng.normal(size=400)
    y = b - .6 * a + .3 * c + .3 * rng.normal(size=400)
    d = dependances(y, np.column_stack([a, b, c]), ["a", "b", "c"])
    assert d["a"][0] == "b", d
    assert abs(d["a"][1]) < .15, d
    assert d["c"][0] in ("a", "b")

def test_bh():
    q = A.benjamini_hochberg([0.01, 0.04, 0.03, 0.5])
    # valeurs de référence (R, p.adjust method="BH") 0.04 0.0533 0.0533 0.5
    assert np.allclose(q, [0.04, 0.0533333, 0.0533333, 0.5], atol=1e-6), q


def test_gini():
    g, *_ = A.lorenz([10, 20, 30], [100, 200, 300])
    assert abs(g) < 1e-12, g
    g, *_ = A.lorenz([0, 0, 0, 100], [1, 1, 1, 1])
    assert abs(g - 0.75) < 1e-12, g


def test_theil():
    assert abs(A.theil([1, 2], [1, 2])) < 1e-12


def test_poisson():
    rng = np.random.default_rng(0)
    n = 4000
    X = rng.normal(size=(n, 2))
    pop = rng.integers(1000, 100000, n).astype(float)
    mu = pop * 1e-3 * np.exp(0.3 * X[:, 0] - 0.2 * X[:, 1])
    y = rng.poisson(mu)
    coefs, *_ = A.poisson_robuste(y.astype(float), X, np.log(pop), ["a", "b"])
    b = coefs.set_index("variable")["coef"]
    assert abs(b["a"] - 0.3) < 0.02 and abs(b["b"] + 0.2) < 0.02 and abs(b["constante"] - np.log(1e-3)) < 0.02, b


def test_spearman_ic():
    rng = np.random.default_rng(1)
    x = rng.normal(size=500)
    y = x + rng.normal(size=500)
    rho, p, lo, hi, n = A.spearman_bootstrap(x, y, 300, rng)
    assert lo < rho < hi and n == 500 and p < 1e-10


def test_moran():
    import pandas as pd
    # chaîne de 50 territoires, valeurs croissantes, forte autocorrélation positive
    codes = [str(i) for i in range(50)]
    v = {c: {str(int(c) - 1), str(int(c) + 1)} & set(codes) for c in codes}
    I, p = A.moran(pd.Series(np.arange(50.0), index=codes), v, permutations=199)
    assert I > 0.8 and p < 0.05, (I, p)


def test_spearman_partiel():
    rng = np.random.default_rng(2)
    z = rng.normal(size=800)
    # x et y ne sont liés que par z, le lien disparaît à z égal
    x, y = z + rng.normal(scale=.5, size=800), z + rng.normal(scale=.5, size=800)
    rho, p, lo, hi, n = A.spearman_partiel_bootstrap(x, y, z, 200, rng)
    assert abs(rho) < .1 and lo < 0 < hi and n == 800, (rho, lo, hi)
    assert A.spearman_bootstrap(x, y, 0, rng)[0] > .6
    # lien propre entre x et y en plus de z, il subsiste à z égal
    e = rng.normal(size=800)
    rho2, p2, *_ = A.spearman_partiel_bootstrap(z + e, z + e + rng.normal(scale=.5, size=800), z, 0, rng)
    assert rho2 > .5 and p2 < 1e-10, rho2


def test_concentration():
    c, *_ = A.indice_concentration([10, 20, 30, 40], [100, 200, 300, 400], [1, 2, 3, 4])
    assert abs(c) < 1e-12, c
    c, *_ = A.indice_concentration([0, 0, 0, 10], [1, 1, 1, 1], [1, 2, 3, 4])
    assert abs(c - .75) < 1e-12, c
    c, *_ = A.indice_concentration([10, 0, 0, 0], [1, 1, 1, 1], [1, 2, 3, 4])
    assert abs(c + .75) < 1e-12, c
    d = A.deciles_population(np.arange(100), np.ones(100))
    assert all((d == k).sum() == 10 for k in range(1, 11)) and d[0] == 1 and d[-1] == 10


def test_standardisation():
    # deux territoires, deux âges. Taux par âge identiques (1 % et 10 %), structures d'âge différentes.
    cas = [[1, 100], [9, 10]]
    pop = [[100, 1000], [900, 100]]
    s = A.standardisation_directe(cas, pop, [500, 500])
    # même taux standardisé (5,5 %) malgré des taux bruts très différents (9,2 % et 1,9 %)
    assert np.allclose(s, [.055, .055]), s


def test_moran_local():
    import pandas as pd
    # grille 12 x 12, voisinage par les côtés. Tiers gauche bas, tiers droit haut, bruit léger.
    rng = np.random.default_rng(3)
    cases = [(i, j) for i in range(12) for j in range(12)]
    nom = lambda i, j: f"{i}_{j}"  # noqa: E731
    v = {nom(i, j): {nom(a, b) for a, b in [(i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)] if 0 <= a < 12 and 0 <= b < 12}
         for i, j in cases}
    x = pd.Series([(0 if j < 4 else 5 if j < 8 else 10) + rng.normal(0, .3) for i, j in cases],
                  index=[nom(i, j) for i, j in cases])
    r = A.moran_local(x, v).set_index("code")
    assert r.at["6_1", "type"] == "LL" and r.at["6_10", "type"] == "HH"
    assert r.at["6_1", "p"] < .01 and r.at["6_10", "p"] < .01 and r.at["6_1", "I"] > 0
    # le calcul analytique va dans le même sens que les permutations
    rp = A.moran_local(x, v, permutations=999, rng=rng).set_index("code")
    assert rp.at["6_1", "p"] < .05 and rp.at["6_6", "p"] > .5 and r.at["6_6", "p"] > .5
    # sans structure spatiale, peu de territoires significatifs
    y = pd.Series(rng.normal(size=144), index=x.index)
    assert (A.moran_local(y, v)["p"] < .05).mean() < .15


def test_accessibilite():
    # distance Paris (Notre-Dame) Lyon (Bellecour), environ 392 km à vol d'oiseau
    xyz = A.coords_3d([2.3499, 4.8320], [48.8530, 45.7578])
    d = A.corde_vers_km(np.linalg.norm(xyz[0] - xyz[1]))
    assert 385 < d < 400, d
    assert np.allclose(A.poids_distance([0, 10, 12, 18, 25]), [1, 1, .66, .33, 0])
    # deux communes à 5 km l'une de l'autre, un professionnel dans la première, 1 000 habitants chacune.
    # Étape 1, ratio 1 / 2 000. Étape 2, chaque commune y a accès entièrement, 5 pour 10 000 habitants.
    lon0, lat0 = 2.0, 46.0
    xyz = A.coords_3d([lon0, lon0 + 5 / (111.32 * np.cos(np.radians(lat0)))], [lat0, lat0])
    acc = A.accessibilite_2sfca(xyz, [1, 0], [1000, 1000])
    assert np.allclose(acc, [5, 5], atol=1e-6), acc
    # une troisième commune à 100 km n'a aucun accès
    xyz3 = np.vstack([xyz, A.coords_3d([lon0 + 1.3], [lat0])])
    assert A.accessibilite_2sfca(xyz3, [1, 0, 0], [1000, 1000, 1000])[2] == 0


def test_theil_decomposition():
    n, pop, g = [10, 30, 20, 40], [100, 100, 100, 100], ["a", "a", "b", "b"]
    t, e, d = A.theil_decomposition(n, pop, g)
    assert abs(t - (e + d)) < 1e-12 and t > 0          # additivité exacte
    # groupes homogènes en interne, toute l'inégalité est entre groupes
    t2, e2, d2 = A.theil_decomposition([10, 10, 30, 30], [100, 100, 100, 100], g)
    assert abs(d2) < 1e-12 and abs(t2 - e2) < 1e-12
    lo, hi = A.gini_bootstrap([10, 30, 20, 40, 5, 25], [100] * 6, 200, np.random.default_rng(1))
    assert lo <= A.lorenz([10, 30, 20, 40, 5, 25], [100] * 6)[0] <= hi


def test_quadrant():
    q, mo, mb = A.quadrant([1, 2, 3, 4, np.nan], [4, 3, 2, 1, 5])
    assert mo == 2.5 and mb == 2.5
    assert list(q) == ["besoin+offre-", "besoin+offre-", "besoin-offre+", "besoin-offre+", None], q


def test_lot_a():
    """Densité par public concerné, combinaisons d'offre et psychologues par psychiatre, sur un cas construit."""
    import pandas as pd
    from types import SimpleNamespace
    from pipeline import config
    from pipeline.sources.referentiel import Referentiel
    com = pd.DataFrame({"code": ["A", "B", "C"], "nom": list("abc"), "pop": [1000, 1000, 2000],
                        "dep": ["01", "01", "02"], "reg": ["84", "84", "84"], "epci": ["E1", "E2", "E3"]})
    ref = Referentiel(com, pd.DataFrame({"code": ["E1", "E2", "E3"], "nom": list("xyz"), "pop": [1000, 1000, 2000],
                                         "dep": ["01", "01", "02"]}),
                      pd.DataFrame({"code": ["01", "02"], "nom": ["d1", "d2"], "reg": ["84", "84"], "pop": [2000, 2000]}),
                      pd.DataFrame({"code": ["84"], "nom": ["r"], "pop": [4000]}), {}, {})
    eff = pd.DataFrame({"code": ["E1", "E2", "E3", "E1", "E3"], "prof": ["pediatre", "pediatre", "pediatre",
                        "psychologue", "psychologue"], "mode": "all", "n": [1, 1, 2, 4, 2]})
    eff = pd.concat([eff, pd.DataFrame({"code": ["E1"], "prof": ["psychiatre"], "mode": "all", "n": [2]})])
    agg = SimpleNamespace(effectifs={"epci": eff, "com": eff.assign(code=eff["code"].map({"E1": "A", "E2": "B", "E3": "C"})),
                                     "dep": pd.DataFrame(columns=["code", "prof", "mode", "n"])},
                          national=pd.DataFrame({"prof": ["pediatre"], "mode": ["all"], "n": [4]}))
    # E1 et E2 ont 20 % d'enfants, E3 10 %. Densité générale égale partout pour les pédiatres (1 pour 1 000).
    ctx = {"epci": pd.DataFrame({"part_0_14": [20.0, 20.0, 10.0]}, index=["E1", "E2", "E3"])}
    avant, config.NIVEAUX_ANALYSE = config.NIVEAUX_ANALYSE, ["epci"]
    try:
        res, terr = A.densite_cible(agg, ref, ctx)
        comp = A.composition_sante_mentale(agg, ref)
    finally:
        config.NIVEAUX_ANALYSE = avant
    r = res.set_index("prof").loc["pediatre"]
    assert abs(r["gini_population"]) < 1e-12 and r["gini_public"] > 0   # égal par habitant, inégal par enfant
    assert abs(r["densite_nationale_cible"] - 4 / 600 * 1e4) < 1e-9   # 200 enfants dans chaque EPCI
    assert terr.set_index("code").at["E3", "densite_cible"] == 2 / 200 * 1e4
    cb = A.combinaisons(agg, ref).query("niveau == 'epci'").set_index(["psychologue", "psychiatre"])
    assert abs(cb["part_population"].sum() - 1) < 1e-12
    assert cb.loc[(True, False), "population"].sum() == 2000      # E3, psychologue sans psychiatre
    c = comp.set_index("code")
    assert c.at["E1", "psychologues_par_psychiatre"] == 2 and np.isnan(c.at["E3", "psychologues_par_psychiatre"])


def test_entonnoir():
    L = A.limites_entonnoir([10000], 1e-3)
    # Poisson de moyenne 10, quantiles 2,5 % et 97,5 % égaux à 4 et 17
    assert L[.95][0][0] == 4 and L[.95][1][0] == 17, L
    assert L[.998][0][0] < 4 and L[.998][1][0] > 17


def test_complements():
    """Mécanisme des bases complémentaires, remontée des communes vers l'EPCI, le département et la région,
    et lecture d'une base départementale."""
    import json
    import tempfile
    import pandas as pd
    from pipeline.sources import complements
    from pipeline.sources.referentiel import Referentiel
    com = pd.DataFrame({"code": ["01001", "01002", "02001"], "nom": ["A", "B", "C"], "pop": [100, 300, 600],
                        "dep": ["01", "01", "02"], "reg": ["84", "84", "32"], "epci": ["E1", "E1", "E2"]})
    ref = Referentiel(com, pd.DataFrame({"code": ["E1", "E2"], "nom": ["e1", "e2"], "pop": [400, 600], "dep": ["01", "02"]}),
                      pd.DataFrame({"code": ["01", "02"], "nom": ["d1", "d2"], "reg": ["84", "32"], "pop": [400, 600]}),
                      pd.DataFrame({"code": ["84", "32"], "nom": ["r1", "r2"], "pop": [400, 600]}), {}, {})
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        (t / "com.csv").write_text("codgeo;nb;taux\n1001;10;5\n01002;30;15\n02001;60;20\n", encoding="utf-8")
        (t / "dep.csv").write_text("dep;v\n1;4\n02;6\n", encoding="utf-8")
        (t / "a.json").write_text(json.dumps({"nom": "test com", "local": True, "fichier": "com.csv", "niveau": "com",
            "colonne_code": "codgeo", "indicateurs": [
                {"colonne": "nb", "id": "nb", "libelle": "Nb", "agregation": "somme", "pour_10000_habitants": True},
                {"colonne": "taux", "id": "taux", "libelle": "Taux", "agregation": "moyenne", "famille": "Santé mentale"}]}),
            encoding="utf-8")
        (t / "b.json").write_text(json.dumps({"nom": "test dep", "local": True, "fichier": "dep.csv", "niveau": "dep",
            "colonne_code": "dep", "indicateurs": [{"colonne": "v", "id": "v", "libelle": "V", "agregation": "somme"}]}),
            encoding="utf-8")
        ctx, defs = complements.charger(ref, None, descripteurs=t)
    assert abs(ctx["epci"].at["E1", "nb"] - 40 / 400 * 1e4) < 1e-9
    assert abs(ctx["dep"].at["01", "taux"] - (5 * 100 + 15 * 300) / 400) < 1e-9   # moyenne pondérée
    assert ctx["dep"].at["01", "v"] == 4 and ctx["reg"].at["32", "v"] == 6
    assert {d["id"] for d in defs} == {"nb", "taux", "v"} and next(d for d in defs if d["id"] == "taux")["famille"] == "Santé mentale"


def test_site_markdown():
    """Conversion d'un rapport en HTML, volets repliés à l'écran et ouverts à l'impression, figures et dates."""
    from pipeline import site
    from pipeline.lecture import date_longue
    assert date_longue("2026-10-04") == "4 octobre 2026" and date_longue("2026-10-01") == "1er octobre 2026"
    md = "# Titre\n\n## Partie\n\n<!--GRAPHIQUE absent-->\n\n<details>\n<summary>Pour aller plus loin</summary>\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n</details>\n"
    titre, corps, toc = site.md_html(md, None)
    assert titre == "Titre" and "<table>" in corps and "<details" in corps and " open" not in corps
    assert "GRAPHIQUE" not in corps and "Partie" in toc
    # à l'impression, le volet part dans l'annexe technique, un renvoi reste à sa place (décision du 22 octobre 2026)
    imp = site.md_html(md, None, imprimer=True)[1]
    assert "<details" not in imp and "annexe technique A1" in imp and 'id="annexe-a1">A1. Partie' in imp
    assert site.en_bref("### En bref\n\n- Un.\n- Deux.\n\nSuite") == ["Un.", "Deux."]


def test_chiffres_cles():
    """Chiffres clés en tête de partie (audit du 22 octobre 2026), deux à quatre tuiles, et chaque valeur d'une tuile
    figure aussi dans le texte du rapport, une tuile ne montre jamais un chiffre qui n'est pas ailleurs."""
    import re
    from pipeline import rapport
    assert rapport._cles(("1", "a")) == [] and rapport._cles(None, ("1", "a"), ("2", "b"))
    assert rapport._cles(*[(str(i), "x") for i in range(6)])[0].count('class="v"') == 4
    d = _dernier_resultats()
    for nom in ("rapport_sante_mentale.md", "rapport_sante.md"):
        f = d / nom
        if not f.exists():
            raise Ignore(nom)
        texte = f.read_text(encoding="utf-8")
        tuiles = re.findall(r'<div class="cles">.*?</div></div></div>', texte)
        assert tuiles, nom
        reste = re.sub(r'<div class="cles">.*', "", texte)
        for v in re.findall(r'<div class="v">([^<]+)</div>', " ".join(tuiles)):
            nu = v.replace("× ", "").replace("+", "").replace("−", "")
            assert nu in reste, (nom, v)


def test_methode_en_pages():
    """La méthode en cinq pages (audit du 22 octobre 2026), chaque section hors de la vue d'ensemble a sa redirection
    depuis l'ancienne adresse methode.html#section, pour que les liens déjà diffusés restent bons."""
    import re
    from pipeline import config
    g = (config.RACINE / "gabarits" / "methode.html").read_text(encoding="utf-8")
    vues = re.findall(r"\{% if vue == '(\w+)' %\}", g)
    assert set(vues) >= {"entree", "structures", "indicateurs", "controles", "fichiers"}
    redir = dict(re.findall(r'(\w+):"(methode-\w+\.html)"', g))
    morceaux = re.split(r"\{% if vue == '(\w+)' %\}", g)
    for vue, corps in zip(morceaux[1::2], morceaux[2::2]):
        for ident in re.findall(r'<h2 id="(\w+)"', corps):
            if vue != "entree":
                assert redir.get(ident) == f"methode-{vue}.html", (ident, vue)


def test_pdf_a_savoir_coupures():
    """PDF, une limite de config.LIMITES déjà donnée devient un renvoi à sa section, les noms de fichiers reçoivent des
    points de coupure hors des balises, un tableau de trois colonnes ou moins est marqué étroit."""
    from pipeline import config, site
    t = config.LIMITES["suicides"]["texte"]
    corps = (f'<h3>Un</h3><p class="a-savoir"><strong>À savoir.</strong> {t} Source, x.</p>'
             f'<h3>Deux</h3><p class="a-savoir"><strong>À savoir.</strong> {t} Source, x.</p>')
    sortie = site.a_savoir_une_fois(corps)
    assert sortie.count(t) == 1 and "Même précaution que dans la section « Un »" in sortie
    assert site.coupures_fichiers('<a href="a_b.csv">voir lieux_soins.csv</a>') == \
        '<a href="a_b.csv">voir lieux_<wbr>soins.csv</a>'
    assert 'class="etroite"' in site.tableaux_etroits("<table><tr><th>a</th><th>b</th></tr></table>")
    assert "etroite" not in site.tableaux_etroits("<table><tr><th>a</th><th>b</th><th>c</th><th>d</th></tr></table>")


def test_pas_rond():
    from pipeline.graphiques import pas_rond
    assert pas_rond(4.2) == 5 and pas_rond(0.18) == 0.2 and pas_rond(13) == 10 and pas_rond(1.2) == 1


def test_classement():
    assert rpps.classer_profession("Masseur-Kinésithérapeute")[0] == "masseur_kinesitherapeute"
    assert rpps.classer_profession("Psychologue")[0] == "psychologue"
    assert rpps.classer_profession("Médecin") is None
    assert rpps.classer_medecin("Psychiatrie de l'enfant et de l'adolescent")[0] == "pedopsychiatre"
    assert rpps.classer_medecin("Psychiatrie")[0] == "psychiatre"
    assert rpps.classer_medecin("Qualifié en Médecine Générale")[0] == "medecin_generaliste"
    assert rpps.classer_medecin("")[0] == "medecin_non_precise"
    # libellés relevés dans le RPPS le 5 octobre 2026 (DES de 2017 et options)
    assert rpps.classer_medecin("Gynéco-obstétrique et Gynéco médicale option Gynéco-obst")[0] == "gynecologue"
    assert rpps.classer_medecin("Méd cardiovasculaire opt card interventionnelle")[0] == "cardiologue"
    # la chirurgie cardio-vasculaire n'est jamais comptée avec les cardiologues
    assert rpps.classer_medecin("Chirurgie thoracique et cardio-vasculaire")[0] == "chirurgien_thoracique"
    assert rpps.classer_medecin("Pédiatrie option néonatologie")[0] == "pediatre"
    assert rpps.classer_medecin("Ophtalmologie opt chir ophtalmopéd strabologique")[0] == "ophtalmologue"
    # spécialités ajoutées le 11 octobre 2026 (version 2), libellés relevés dans le fichier savoir-faire du RPPS
    cas = {"Chirurgie pédiatrique option orthopédie pédiatrique": "chirurgien_pediatrique",
           "Anesthésie-réanimation opt anesthésie-pédiatrique": "anesthesiste",
           "Médecine intensive-réanimation": "reanimateur",
           "O.R.L et chirurgie cervico faciale": "orl", "Oto-rhino-laryngologie": "orl",
           "ORL - chir cervico-faciale opt audiophonologie": "orl",
           "Oncologie option radiothérapie": "radiotherapeute", "Radio-thérapie": "radiotherapeute",
           "Radio-diagnostic": "radiologue", "Radiologie et imagerie médicale opt radio inter av": "radiologue",
           "Oncologie (option onco-hématologie)": "oncologue", "Hématologie (option Onco-hématologie)": "hematologue",
           "Chirurgie maxillo-faciale et stomatologie": "chirurgien_maxillo_facial", "CHIRURGIE ORALE": "chirurgien_maxillo_facial",
           "Neuro-chirurgie": "neurochirurgien", "Chirurgie vasculaire": "chirurgien_vasculaire",
           "Médecine vasculaire": "medecin_vasculaire", "Médecine du travail": "medecin_travail",
           "Endocrinologie, diabétologie, nutrition": "endocrinologue", "Génétique médicale": "medecin_autre",
           # un médecin déjà classé le reste (généraliste avant toute autre spécialité)
           "Anesthesie-réanimation ; Médecine Générale": "medecin_generaliste"}
    for lib, attendu in cas.items():
        assert rpps.classer_medecin(lib)[0] == attendu, (lib, rpps.classer_medecin(lib)[0])


def test_colonnes():
    cols = ["Identification nationale PP", "Code commune (coord. structure)", "Libellé secteur d'activité"]
    assert trouver_colonne(cols, [r"^code commune coord structure$"]) == cols[1]
    assert trouver_colonne(cols, [r"^libelle secteur d ?activite$"]) == cols[2]
    assert norm("Élève-Infirmier(e)") == "eleve infirmier e"


def test_format_fr():
    from pipeline.util import format_fr
    assert format_fr("90.9%") == "90,9 %", format_fr("90.9%")
    assert format_fr("348021 lignes, 9.0%") == "348 021 lignes, 9,0 %"
    assert format_fr("millésime 2023") == "millésime 2023"


def test_lecture():
    from pipeline import lecture as Lc
    assert Lc.pluriel("Médecin généraliste") == "médecins généralistes"
    # un intervalle de confiance qui comprend zéro empêche de présenter le lien comme établi
    assert Lc.phrase_correlation(-.19, "Taux de suicide", "Psychologue", (-.39, .04)).startswith("Aucun lien net")
    assert "comptent plutôt moins" in Lc.phrase_correlation(-.38, "Taux de suicide", "Psychiatre", (-.54, -.19))
    assert Lc.pluriel("Masseur-kinésithérapeute") == "masseurs-kinésithérapeutes"
    assert Lc.pluriel("Sage-femme") == "sages-femmes"
    assert Lc.pluriel("Technicien de laboratoire") == "techniciens de laboratoire"
    assert Lc.pluriel("Infirmier, en établissement psychiatrique") == "infirmiers, en établissement psychiatrique"
    assert Lc.un_pour(11.8) == "un pour 850 habitants", Lc.un_pour(11.8)
    assert Lc.un_pour(0.5) == "un pour 20 000 habitants", Lc.un_pour(0.5)
    assert Lc.fois(15.8, 7.0) == "2,3 fois plus"
    assert Lc.fois(1.2, 1).replace(" ", " ") == "20 % de plus"
    assert Lc.force(-0.35) == "modéré"
    assert Lc.nom_classe({"Psychologue": 40, "Psychiatre": 30, "Infirmier": 60}).startswith(
        "Territoires nettement moins dotés pour presque toutes")
    assert Lc.nom_classe({"Psychologue": 60, "Psychiatre": 70, "Infirmier": 75}).startswith("Territoires moins dotés")
    n = Lc.noms_classes({1: {"A": 60, "B": 70, "C": 75}, 2: {"A": 62, "B": 71, "C": 74}})
    assert n[1] != n[2] and "indice médian" in n[1]
    n = Lc.noms_classes({1: {"A": 41, "B": 30, "C": 45}, 2: {"A": 11, "B": 8, "C": 15}})
    assert n[1].endswith("(environ 2,4 fois moins que la moyenne)") and n[2].endswith("(environ 9 fois moins que la moyenne)")
    assert Lc.ecart_moyenne(80) == "environ 20 % de moins" and Lc.ecart_moyenne(250) == "environ 2,5 fois plus"
    assert "mieux dotés pour les psychiatres" in Lc.nom_classe({"Psychologue": 30, "Psychiatre": 200, "Infirmier": 40})
    assert Lc.nom_classe({"Psychologue": 100, "Psychiatre": 110}) == "Territoires proches de la moyenne"
    assert "moins dotés pour les psychiatres" in Lc.nom_classe({"Psychologue": 100, "Psychiatre": 60, "Infirmier": 105})


def test_libelles():
    from pipeline import libelles
    assert libelles.affichage("Centre Hospitalier Spécialisé lutte Maladies Mentales").startswith("CHS")
    assert libelles.affichage("Etab. pour Handicapés") == "Établissement pour personnes en situation de handicap"
    assert libelles.affichage("Libellé inconnu") == "Libellé inconnu"
    assert libelles.termes_proscrits("Foyer pour adultes handicapés")
    assert libelles.termes_proscrits("Centre de lutte contre les maladies mentales")
    assert not libelles.termes_proscrits("MDPH (maison départementale des personnes handicapées)")
    assert not libelles.termes_proscrits("Personnes en situation de handicap, déficience intellectuelle")
    assert libelles.termes_proscrits("Un service pour les schizophrènes")
    assert not libelles.termes_proscrits("Adultes déclarant des épisodes dépressifs caractérisés")
    # tous les libellés d'affichage de la table doivent être conformes
    for r in libelles.table():
        assert not libelles.termes_proscrits(r["libelle_affichage"]), r


def test_perimetre_elargi():
    import pandas as pd
    from pipeline import build, config
    act = pd.DataFrame({"id": ["a", "b", "c"] * 60, "prof": ["infirmier"] * 180, "mode": ["sal", "sal", "lib"] * 60,
                        "finess": ["000000001", "000000002", ""] * 60, "com": ["75056"] * 180})
    act["id"] = act["id"] + act.index.astype(str)
    fin = pd.DataFrame({"nofinesset": ["000000001", "000000002"], "categetab": ["156", "355"]})
    prof = pd.DataFrame({"id": ["infirmier"], "libelle": ["Infirmier"], "groupe": ["x"], "famille": [config.SANTE],
                         "nature": ["profession"]})
    min_avant, config.ELARGI_EFFECTIF_MIN = config.ELARGI_EFFECTIF_MIN, 10
    try:
        act2, prof2 = build.perimetre_elargi(act, fin, prof)
    finally:
        config.ELARGI_EFFECTIF_MIN = min_avant
    esm = act2[act2["prof"] == "esm_infirmier"]
    # seuls les salariés d'un CMP (156) entrent dans le périmètre, pas ceux d'un CH (355) ni les libéraux
    assert len(esm) == 60 and set(esm["finess"]) == {"000000001"}, len(esm)
    assert prof2.set_index("id").at["esm_infirmier", "nature"] == "perimetre_elargi"


def test_langage_sorties():
    """Aucun terme à proscrire dans ce qu'un lecteur voit. Vérifie le gabarit de l'atlas et, s'ils
    existent, le dernier rapport et le dernier site_data.json produits."""
    import json
    from pipeline import config, libelles
    racine = Path(__file__).resolve().parent.parent
    a_verifier = [racine / "atlas" / "atlas_template.html", *(racine / "atlas" / "moteur").glob("*.js")]
    dates = sorted(p for p in (config.RESULTATS).glob("20*") if p.is_dir())
    if dates:
        a_verifier += [dates[-1] / "rapport.md", dates[-1] / "site_data.json"]
    for p in a_verifier:
        if not p.exists():
            continue
        texte = p.read_text(encoding="utf-8")
        if p.suffix == ".json":
            d = json.loads(texte)
            d.pop("structures", None)   # raisons sociales, noms propres d'établissements
            texte = json.dumps(d, ensure_ascii=False)
        pb = libelles.termes_proscrits(texte)
        assert not pb, f"{p.name} contient des termes à proscrire :\n" + "\n".join(pb[:10])


def test_sans_territoires():
    # sans le territoire c, x et y vont exactement dans le même sens, avec lui le lien s'affaiblit
    r, n, r2, n2 = A.sans_territoires([1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, -9], list("abcdef"), ["f"])
    assert n == 6 and n2 == 5 and abs(r2 - 1) < 1e-12 and r < r2, (r, r2)
    # un territoire exclu absent des données ne change rien
    r, n, r2, n2 = A.sans_territoires([1, 3, 2, 5, 4], [2, 1, 4, 3, 5], list("abcde"), ["z"])
    assert n == n2 == 5 and abs(r - r2) < 1e-12


def test_evolution_densite():
    from types import SimpleNamespace
    import pandas as pd
    from pipeline import config, evolution
    # 10 pour 10 000 puis 11 pour 10 000, soit +10 %, même avec une population qui change
    assert abs(evolution.evolution_densite(100, 100_000, 121, 110_000) - .1) < 1e-12
    assert evolution.evolution_densite(0, 1000, 5, 1000) is None
    assert evolution.evolution_densite(5, 0, 5, 1000) is None
    # deux départements d'une même région, la région est la somme de ses départements
    ref = SimpleNamespace(deps=pd.DataFrame({"code": ["01", "02"], "reg": ["R", "R"]}))
    d0, d1 = config.EVOLUTION_DEBUT, config.EVOLUTION_FIN
    drees = pd.DataFrame({"motif": "^sages femmes rpps", "spec": "", "niveau": "dep",
                          "code": ["01", "01", "02", "02"], "annee": [d0, d1, d0, d1], "effectif": [10., 20, 30, 30]})
    pops = pd.DataFrame({"code": ["01", "01", "02", "02"], "annee": [d0, d1, d0, d1],
                         "population": [10_000., 10_000, 10_000, 20_000]})
    r = evolution.calculer(drees, pops, ref)["evolution_offre_resume"].set_index(["niveau", "code"])
    assert abs(r.at[("dep", "01"), "evolution_densite"] - 1) < 1e-12        # 10 à 20 pour 10 000
    assert abs(r.at[("dep", "02"), "evolution_densite"] + .5) < 1e-12       # 30 à 15 pour 10 000
    assert abs(r.at[("reg", "R"), "evolution_densite"] - (50 / 30_000) / (40 / 20_000) + 1) < 1e-12
    assert abs(r.at[("FR", "FR"), "densite_fin"] - 50 / 30_000 * 1e4) < 1e-12


def test_acp_cah():
    import numpy as np
    rng = np.random.default_rng(1)
    # deux variables presque identiques et une troisième indépendante, le premier axe réunit les deux premières
    x = rng.normal(size=300)
    Z = np.column_stack([x, x + rng.normal(scale=.05, size=300), rng.normal(size=300)])
    Z = (Z - Z.mean(0)) / Z.std(0)
    vp, part, coords, charges = A.acp(Z)
    assert abs(vp.sum() - 3) < 1e-9 and part[0] > .6
    assert charges[0, 0] > .98 and charges[1, 0] > .98 and abs(charges[2, 0]) < .3 and charges[2, 1] > .9
    assert abs(np.corrcoef(coords[:, 0], x)[0, 1]) > .99
    # trois groupes nettement séparés sont retrouvés, numérotés du plus peuplé au moins peuplé
    G = np.vstack([rng.normal(c, .1, size=(n, 2)) for c, n in ((0, 50), (5, 30), (10, 20))])
    lab, k, sil, r2 = A.cah_ward(G, 2, 5)
    assert k == 3 and sil > .9 and r2 > .99 and list(np.bincount(lab)[1:]) == [50, 30, 20]


def test_ols_robuste():
    import numpy as np
    from pipeline.croisements_indicateurs import ols_robuste
    rng = np.random.default_rng(2)
    x1, x2 = rng.normal(size=400), rng.normal(size=400)
    y = 2 * x1 + rng.normal(scale=1, size=400)
    co, r2, r2a, n = ols_robuste(y, np.column_stack([x1, x2]), ["x1", "x2"])
    c = co.set_index("variable")
    # coefficient standardisé de x1 proche de 2 / racine de 5, x2 sans lien, peu de recouvrement entre x1 et x2
    assert abs(c.at["x1", "coef_standardise"] - 2 / 5 ** .5) < .05 and c.at["x1", "ic95_bas"] > 0
    assert c.at["x2", "ic95_bas"] < 0 < c.at["x2", "ic95_haut"]
    assert abs(r2 - .8) < .05 and n == 400 and c["vif"].max() < 1.1


def test_journal_mises_a_jour():
    import json
    import tempfile
    from pathlib import Path
    from pipeline import mises_a_jour
    assert mises_a_jour.date_iso("Tue, 21 Jul 2026 16:11:45 GMT") == "2026-07-21"
    assert mises_a_jour.date_iso("2026-10-03T12:45:18.783000+00:00") == "2026-10-03"
    with tempfile.TemporaryDirectory() as d:
        brut = Path(d)
        (brut / "odisse_a.csv.meta.json").write_text(json.dumps({"maj_source": "2026-01-09T09:55:06+00:00",
                                                                 "telecharge_le": "2026-10-03T20:30:41"}))
        (brut / "odisse_b.csv.meta.json").write_text(json.dumps({"maj_source": "2025-12-11T09:30:00+00:00"}))
        (brut / "inconnu.csv.meta.json").write_text(json.dumps({"maj_source": "2026-01-01"}))
        avant = mises_a_jour.etat_sources(brut)
        assert list(avant) == ["Indicateurs de santé mentale, portail Odissé"]
        j = avant["Indicateurs de santé mentale, portail Odissé"]
        assert j["maj"] == "2026-01-09" and j["recupere"] == "2026-10-03" and len(j["fichiers"]) == 2
        assert mises_a_jour.comparer(avant, avant) == []
        (brut / "odisse_b.csv.meta.json").write_text(json.dumps({"maj_source": "2026-09-09T09:02:38+00:00"}))
        (brut / "caf_x.csv.meta.json").write_text(json.dumps({"etag": "abc"}))
        ch = {c["jeu"]: c for c in mises_a_jour.comparer(avant, mises_a_jour.etat_sources(brut))}
        o = ch["Indicateurs de santé mentale, portail Odissé"]
        assert o["nature"] == "modifié" and o["fichiers"] == 1 and o["total"] == 2 and o["maj"] == "2026-09-09"
        assert ch["Allocataires de l'AAH, de l'AEEH et du RSA"]["nature"] == "nouveau"


def test_moran_bivarie():
    import numpy as np
    import pandas as pd
    from pipeline.spatial_offre_besoin import moran_bivarie
    # 40 territoires en ligne, x élevé à gauche, y faible à gauche : les premiers sont du type HL
    codes = [f"t{i:02d}" for i in range(40)]
    vois = {c: {codes[j] for j in (i - 1, i + 1) if 0 <= j < 40} for i, c in enumerate(codes)}
    x = pd.Series(np.linspace(2, -2, 40), index=codes)
    y = pd.Series(np.linspace(-2, 2, 40), index=codes)
    r = moran_bivarie(x, y, vois, permutations=199, rng=np.random.default_rng(1)).set_index("code")
    assert r.at["t01", "type"] == "HL" and r.at["t38", "type"] == "LH" and r.at["t01", "I"] < 0
    assert r.at["t01", "p"] < .05 and r["p"].min() >= 1 / 200


def test_gwr():
    import numpy as np
    from pipeline.spatial_offre_besoin import gwr
    rng = np.random.default_rng(3)
    g = np.array([(i, j) for i in range(20) for j in range(20)], float) * 10   # grille de 400 points, 10 km
    x1, x2 = rng.normal(size=400), rng.normal(size=400)
    # coefficient de x1 qui passe de -1 à +1 d'ouest en est, celui de x2 constant
    b1 = (g[:, 0] / g[:, 0].max()) * 2 - 1
    y = b1 * x1 + .5 * x2 + rng.normal(scale=.3, size=400)
    r = gwr(y, np.column_stack([x1, x2]), g, rng=np.random.default_rng(4), permutations=19)
    assert np.corrcoef(r["beta"][:, 1], b1)[0, 1] > .9          # les coefficients locaux suivent la vraie pente
    assert r["p_variation"][0] <= .05 and r["p_variation"][1] > .05   # x1 varie dans l'espace, x2 non
    assert 20 <= r["k"] <= 400 and r["enp"] > 3 and r["seuil_t"] > 1.96


def test_professions_gwr():
    # sur les effectifs réels par intercommunalité de la dernière exécution : chaque profession retenue est présente dans
    # au moins une intercommunalité sur deux, les professions rares sont écartées, les trois d'origine viennent d'abord
    import json
    import pandas as pd
    from pipeline import config
    from pipeline.spatial_offre_besoin import professions_gwr
    f = sorted(p for p in config.RESULTATS.glob("20*") if (p / "site_data.json").exists())[-1] / "site_data.json"
    n = json.loads(f.read_text(encoding="utf-8"))["niveaux"]["epci"]["n"]
    df = pd.DataFrame({p: v["all"] for p, v in n.items() if isinstance(v, dict) and v.get("all")})
    r = professions_gwr(df)
    assert r[:3] == ["psychologue", "psychiatre", "medecin_generaliste"]
    assert "pedopsychiatre" not in r and "pediatre" not in r and "infirmier" in r
    assert all((df[p] > 0).mean() >= config.GWR_PRESENCE_MIN for p in r)
    assert all(not p.startswith(("ens_", "q_")) for p in r)


def test_lieux_libelles():
    """Libellés des types de lieux conformes au langage respectueux, identifiants uniques, catégories en texte."""
    from pipeline import config, libelles
    ids = [x[0] for x in config.LIEUX_TYPES]
    assert len(ids) == len(set(ids))
    for tid, lib, fam, groupe, r in config.LIEUX_TYPES:
        assert not libelles.termes_proscrits(lib) and not libelles.termes_proscrits(groupe), lib
        assert all(c is None or isinstance(c, str) for c in r.get("cats", set()) | r.get("finess", set())), tid


def test_coherence_config():
    """Chaque liste de config.py ne contient que des éléments de sa forme (un ajout placé dans la mauvaise liste avait
    créé des indicateurs fantômes le 12 octobre 2026), chaque thème de croisement a sa question dans les rapports."""
    from pipeline import config, rapport
    for x in config.AMELI_SECTEURS_PROFESSIONS:
        assert len(x) == 4 and x[3] in (config.SANTE_MENTALE, config.SANTE) and ":" not in x[1], x
    themes = {t for t in (x[2] for x in config.CROISEMENTS)}
    connus = {t for d in rapport.THEMES_CROISEMENTS.values() for t in d} | set(rapport.THEMES_ADDICTO)
    assert themes <= connus, themes - connus
    for xa, yb, theme, q in config.CROISEMENTS:
        assert isinstance(q, str) and xa != yb, (xa, yb)
    premiers = {}
    for _xa, _yb, theme, q in config.CROISEMENTS:
        premiers.setdefault(theme, q)
    assert all(premiers.values()), [t for t, q in premiers.items() if not q]


def test_escalier_distances():
    """Distance au lieu le plus proche par dixième de la population classé selon le niveau de vie."""
    from types import SimpleNamespace
    import numpy as np
    import pandas as pd
    from pipeline.lieux import escalier_distances
    codes = [f"c{i:02d}" for i in range(20)]
    ref = SimpleNamespace(communes=pd.DataFrame({"code": codes, "pop": [100] * 20,
                                                 "epci": [f"e{i:02d}" for i in range(20)]}))
    # la distance croît avec le niveau de vie, deux intercommunalités par dixième
    L = {"distances_communes": pd.DataFrame({"lieu_cmp_adultes": np.arange(20.0)}, index=codes),
         "couverture": pd.DataFrame({"type": ["lieu_cmp_adultes"], "complet": [True]})}
    rev = pd.Series(np.arange(20) * 1000.0, index=[f"e{i:02d}" for i in range(20)])
    t = escalier_distances(L, ref, rev)
    assert list(t["decile"]) == list(range(1, 11))
    assert (t["population"] == 200).all()
    assert t["distance_mediane_km"].is_monotonic_increasing
    assert t.loc[t["decile"] == 10, "part_plus_20_km"].iloc[0] == 0
    assert t.loc[t["decile"] == 1, "niveau_de_vie_max"].iloc[0] == 1000
    assert escalier_distances(L, ref, None) is None


def test_structures_verifiees():
    """La liste vérifiée remplace les inscriptions des bases d'un établissement vérifié, garde leurs numéros FINESS,
    ajoute une structure absente des bases et consigne une inscription non retenue."""
    import tempfile
    from pathlib import Path
    import pandas as pd
    from pipeline import structures_verifiees as sv
    d = Path(tempfile.mkdtemp())
    origine = (sv.FICHIER_ETAB, sv.FICHIER)
    sv.FICHIER_ETAB, sv.FICHIER = d / "e.csv", d / "s.csv"
    pd.DataFrame([{"ej": "E", "etablissement": "CH", "departement": "06", "types": "lieu_cmp", "date": "2026-10-13",
                   "sources": "site", "empreinte": "", "remarque": ""}]).to_csv(sv.FICHIER_ETAB, sep=";", index=False)
    pd.DataFrame([{"ej": "E", "etablissement": "CH", "type": "lieu_cmp", "public": "adultes", "nom": "CMP Rembrandt",
                   "adresse": "", "commune": "06088", "statut": "etablissement", "finess": "111", "source": "site",
                   "adresse_source": "https://x", "date": "2026-10-13", "remarque": ""},
                  {"ej": "E", "etablissement": "CH", "type": "lieu_cmp", "public": "enfants", "nom": "CMP Carros",
                   "adresse": "", "commune": "06033", "statut": "etablissement", "finess": "", "source": "site",
                   "adresse_source": "https://x", "date": "2026-10-13", "remarque": ""}]).to_csv(sv.FICHIER, sep=";",
                                                                                                 index=False)
    lieux = pd.DataFrame({"type": ["lieu_cmp", "lieu_cmp_adultes", "lieu_cmp", "lieu_cmp"],
                          "lieu": ["a", "a", "b", "c"], "nom": ["CMP LE REMBRANDT", "CMP LE REMBRANDT", "CMP X", "CMP Y"],
                          "ej": ["E", "E", "E", "F"], "finess": ["111", "111", "222", "333"],
                          "commune": ["06088", "06088", "06088", "06088"], "dep": ["06"] * 4,
                          "adresse": ["R A", "R A", "R B", "R C"], "provenance": ["les_deux", "les_deux", "finess", "ror"],
                          "lat": [43.7] * 4, "lon": [7.2] * 4, "precision": ["finess"] * 4})

    class Ref:
        communes = pd.DataFrame({"code": ["06088", "06033"], "nom": ["Nice", "Carros"], "dep": ["06", "06"],
                                 "epci": ["X", "X"], "reg": ["93", "93"]})
    x, r = sv.appliquer(lieux, Ref(), {"06033": (7.18, 43.78)}, True)
    assert set(x.loc[x["type"] == "lieu_cmp", "nom"]) == {"CMP Rembrandt", "CMP Carros", "CMP Y"}
    assert set(x.loc[x["type"] == "lieu_cmp_enfants", "nom"]) == {"CMP Carros"}
    assert x.loc[(x["nom"] == "CMP Rembrandt") & (x["type"] == "lieu_cmp"), "provenance"].iloc[0] == "les_deux"
    assert x.loc[(x["nom"] == "CMP Carros") & (x["type"] == "lieu_cmp"), "provenance"].iloc[0] == "sources"
    sv.FICHIER_ETAB, sv.FICHIER = origine
    assert [n["finess"] for n in r["non_retenues"]] == ["222"] and r["ajoutees"] == 1


def test_structures_verifiees_sans_etablissement():
    """Une unité du ROR sans établissement, dans la commune d'une structure vérifiée et de nom concordant, lui est
    rattachée au lieu de compter à part. Une autre unité sans établissement de la même commune reste."""
    import tempfile
    from pathlib import Path
    import pandas as pd
    from pipeline import structures_verifiees as sv
    d = Path(tempfile.mkdtemp())
    origine = (sv.FICHIER_ETAB, sv.FICHIER)
    sv.FICHIER_ETAB, sv.FICHIER = d / "e.csv", d / "s.csv"
    pd.DataFrame([{"ej": "E", "etablissement": "CHU", "departement": "", "types": "lieu_cmp", "date": "2026-10-14",
                   "sources": "site", "empreinte": "", "remarque": ""}]).to_csv(sv.FICHIER_ETAB, sep=";", index=False)
    pd.DataFrame([{"ej": "E", "etablissement": "CHU", "type": "lieu_cmp", "public": "adultes", "nom": "CMP de Saint-Renan",
                   "adresse": "56 rue de Saint-Mathieu", "commune": "29260", "statut": "etablissement", "finess": "",
                   "source": "site", "adresse_source": "https://x", "date": "2026-10-14", "remarque": ""}]
                 ).to_csv(sv.FICHIER, sep=";", index=False)
    lieux = pd.DataFrame({"type": ["lieu_cmp", "lieu_cmp_adultes", "lieu_cmp"], "lieu": ["a", "a", "b"],
                          "nom": ["CMP adulte Saint Renan 29G01", "CMP adulte Saint Renan 29G01", "CMP Kerzouar"],
                          "ej": [None, None, None], "finess": [None] * 3, "commune": ["29260"] * 3, "dep": ["29"] * 3,
                          "adresse": ["RUE DE BREST", "RUE DE BREST", "RUE X"], "provenance": ["ror"] * 3,
                          "lat": [48.4] * 3, "lon": [-4.6] * 3, "precision": ["ror"] * 3})

    class Ref:
        communes = pd.DataFrame({"code": ["29260"], "nom": ["Saint-Renan"], "dep": ["29"], "epci": ["X"], "reg": ["53"]})
    x, r = sv.appliquer(lieux, Ref(), {"29260": (-4.62, 48.43)}, True)
    sv.FICHIER_ETAB, sv.FICHIER = origine
    assert set(x.loc[x["type"] == "lieu_cmp", "nom"]) == {"CMP de Saint-Renan", "CMP Kerzouar"}
    assert list(x.loc[x["type"] == "lieu_cmp_adultes", "nom"]) == ["CMP de Saint-Renan"]
    assert x.loc[x["nom"] == "CMP de Saint-Renan", "provenance"].iloc[0] == "ror" and r["non_retenues"] == []


def test_structures_analyses():
    """Analyses complémentaires des structures. Médiane pondérée, structures confirmées gardées pour la sensibilité,
    double éloignement sur un cas construit, charge par CMP d'après la SAE."""
    import numpy as np
    import pandas as pd
    from types import SimpleNamespace
    from pipeline import structures_analyses as sa, config
    assert sa._mediane(np.array([1., 5., 30.]), np.array([1., 1., 10.])) == 30.0
    x = pd.DataFrame({"type": ["lieu_cmp_adultes"] * 3 + ["lieu_urgences"],
                      "confirmation": ["has", "bases", "examinee", None]})
    k = sa._confirmees(x)
    assert k["type"].tolist() == ["lieu_cmp_adultes", "lieu_urgences"] and k["confirmation"].iloc[0] == "has"
    # double éloignement, deux intercommunalités (E1 sans psychiatre), trois communes
    ref = SimpleNamespace(communes=pd.DataFrame({"code": ["c1", "c2", "c3"], "epci": ["E1", "E1", "E2"],
                                                 "dep": ["01", "01", "01"], "reg": ["84", "84", "84"],
                                                 "pop": [100, 300, 600]}),
                          epci=pd.DataFrame({"code": ["E1", "E2"], "pop": [400, 600]}),
                          deps=pd.DataFrame({"code": ["01"], "pop": [1000]}), regs=pd.DataFrame({"code": ["84"], "pop": [1000]}))
    agg = SimpleNamespace(effectifs={"epci": pd.DataFrame({"code": ["E1", "E2"], "mode": ["all", "all"],
                                                           "prof": ["psychiatre", "psychiatre"], "n": [0, 3]})})
    L = {"distances_communes": pd.DataFrame({"lieu_cmp_adultes": [25., 5., 30.]}, index=["c1", "c2", "c3"])}
    # le champ « adultes » du registre porte les psychiatres et le CMP pour adultes, le champ des enfants est ignoré
    # faute de ses professionnels et de ses structures dans ce cas construit
    d = sa.double_eloignement(agg, L, ref)
    fr = d[d["niveau"] == "fr"].iloc[0]
    # c1 (100 habitants) sans psychiatre et à 25 km, c2 sans psychiatre mais proche, c3 loin mais avec psychiatres
    assert abs(fr["part_double_eloignement"] - .1) < 1e-9 and abs(fr["part_sans_professionnel"] - .4) < 1e-9
    assert abs(fr["part_loin_structure"] - .7) < 1e-9
    # charge par CMP, deux départements, adultes
    sae = {"charge_disciplines": pd.DataFrame({"dep": ["01", "02"], "DIS": ["GEN", "GEN"], "FIL_AMB": [1000., 3000.],
                                               "NB_CMP_SEUL": [2., 4.], "ETPSAL_PKT": [4., 6.]})}
    ref2 = SimpleNamespace(deps=pd.DataFrame({"code": ["01", "02"], "reg": ["84", "84"]}))
    c = sa.charge_cmp(sae, ref2)
    f = c[(c["niveau"] == "fr")].iloc[0]
    assert f["patients_par_cmp"] == 4000 / 6 and abs(f["etp_psychiatres_par_cmp"] - 10 / 6) < 1e-9
    assert c[(c["niveau"] == "dep") & (c["code"] == "01")]["patients_par_cmp"].iloc[0] == 500


def test_verdicts_appliques():
    """Verdicts de la vérification à la main. Un doublon est retiré avec sa ligne par public, une unité qui n'est pas
    un CMP est rangée dans son type réel, un CMP qui existe passe au niveau « examinée à la main », un CMP écarté par
    la liste de son établissement est remis, un verdict sans structure est compté à part."""
    import pandas as pd
    from types import SimpleNamespace
    from pipeline import verdicts
    ref = SimpleNamespace(communes=pd.DataFrame({"code": ["62215", "62427"], "nom": ["Carvin", "Hénin-Beaumont"],
                                                 "dep": ["62", "62"], "epci": ["E1", "E1"], "reg": ["32", "32"]}))
    base = {"ej": "EJ", "provenance": "les_deux", "epci": "E1", "dep": "62", "reg": "32", "lat": 50.4, "lon": 2.9,
            "precision": "finess", "adresse": "rue X", "nom_finess": None, "finess_rapproche": None, "finess_absorbes": None}
    x = pd.DataFrame([
        {**base, "type": "lieu_cmp", "lieu": "L1", "nom": "CMP A", "nom_affiche": "CMP A", "finess": "1", "commune": "62215", "confirmation": "bases"},
        {**base, "type": "lieu_cmp_adultes", "lieu": "L1", "nom": "CMP A", "nom_affiche": "CMP A", "finess": "1", "commune": "62215", "confirmation": "bases"},
        {**base, "type": "lieu_cmp", "lieu": "L2", "nom": "HDJ B", "nom_affiche": "HDJ B", "finess": "2", "commune": "62215", "confirmation": "bases"},
        {**base, "type": "lieu_cmp", "lieu": "L3", "nom": "CMP C", "nom_affiche": "CMP C", "finess": "3", "commune": "62427", "confirmation": "bases"},
    ])
    avant = pd.concat([x, pd.DataFrame([{**base, "type": "lieu_cmp", "lieu": "L4", "nom": "CMP D", "nom_affiche": "CMP D",
                                         "finess": "4", "commune": "62427", "confirmation": "has"}])], ignore_index=True)
    k = lambda f, c, n: verdicts.cle("EJ", f, c, n)  # noqa: E731
    v = pd.DataFrame([
        {"cle": k("1", "Carvin", "CMP A"), "verdict": "doublon"},
        {"cle": k("2", "Carvin", "HDJ B"), "verdict": "pas_un_cmp", "type_reel": "lieu_hdj_psy_adultes"},
        {"cle": k("3", "Hénin-Beaumont", "CMP C"), "verdict": "existe", "commentaire": "Sirene"},
        {"cle": k("4", "Hénin-Beaumont", "CMP D"), "verdict": "existe", "commentaire": "site"},
        {"cle": k("9", "Carvin", "CMP Z"), "verdict": "ferme"},
    ]).fillna("").assign(etablissement="", structure="", adresse_reelle="", date="")
    for c in ("type_reel", "commentaire"):
        v[c] = v[c].fillna("")
    out, rendu = verdicts.appliquer(x, avant, ref, None, True, v)
    t = out.set_index(["type", "lieu"])
    assert ("lieu_cmp", "L1") not in t.index and ("lieu_cmp_adultes", "L1") not in t.index
    assert ("lieu_cmp", "L2") not in t.index and ("lieu_hdj_psy_adultes", "L2") in t.index
    assert t.at[("lieu_cmp", "L3"), "confirmation"] == "examinee" and t.at[("lieu_cmp", "L3"), "examen"] == "Sirene"
    assert ("lieu_cmp", "L4") in t.index and t.at[("lieu_cmp", "L4"), "confirmation"] == "has"
    assert len(rendu["non_trouves"]) == 1 and rendu["remises"] == 1 and len(rendu["retirees"]) == 2


def test_structures_verifiees_garde_confirmees():
    """Une inscription absente de la liste vérifiée mais confirmée par la HAS ou Sirene (garder) reste, avec sa ligne
    pour adultes, et elle est consignée à part. Une inscription non confirmée est retirée."""
    import tempfile
    from pathlib import Path
    import pandas as pd
    from pipeline import structures_verifiees as sv
    d = Path(tempfile.mkdtemp())
    origine = (sv.FICHIER_ETAB, sv.FICHIER)
    sv.FICHIER_ETAB, sv.FICHIER = d / "e.csv", d / "s.csv"
    pd.DataFrame([{"ej": "E", "etablissement": "CH", "departement": "", "types": "lieu_cmp", "date": "2026-10-14",
                   "sources": "site", "empreinte": "", "remarque": ""}]).to_csv(sv.FICHIER_ETAB, sep=";", index=False)
    pd.DataFrame([{"ej": "E", "etablissement": "CH", "type": "lieu_cmp", "public": "adultes", "nom": "CMP Rembrandt",
                   "adresse": "", "commune": "06088", "statut": "etablissement", "finess": "111", "source": "site",
                   "adresse_source": "https://x", "date": "2026-10-14", "remarque": ""}]).to_csv(sv.FICHIER, sep=";",
                                                                                                 index=False)
    lieux = pd.DataFrame({"type": ["lieu_cmp", "lieu_cmp", "lieu_cmp_adultes", "lieu_cmp"], "lieu": ["a", "b", "b", "c"],
                          "nom": ["CMP LE REMBRANDT", "CMP GARDE", "CMP GARDE", "CMP RETIRE"], "ej": ["E"] * 4,
                          "finess": ["111", "222", "222", "333"], "commune": ["06088"] * 4, "dep": ["06"] * 4,
                          "adresse": ["R A", "R B", "R B", "R C"], "provenance": ["les_deux"] * 4,
                          "lat": [43.7] * 4, "lon": [7.2] * 4, "precision": ["finess"] * 4})

    class Ref:
        communes = pd.DataFrame({"code": ["06088"], "nom": ["Nice"], "dep": ["06"], "epci": ["X"], "reg": ["93"]})
    x, r = sv.appliquer(lieux, Ref(), {}, True, garder={1})
    sv.FICHIER_ETAB, sv.FICHIER = origine
    assert set(x.loc[x["type"] == "lieu_cmp", "nom"]) == {"CMP Rembrandt", "CMP GARDE"}
    assert list(x.loc[x["type"] == "lieu_cmp_adultes", "nom"]) == ["CMP Rembrandt", "CMP GARDE"] or \
        set(x.loc[x["type"] == "lieu_cmp_adultes", "nom"]) == {"CMP Rembrandt", "CMP GARDE"}
    assert [g["finess"] for g in r["gardees"]] == ["222"] and [n["finess"] for n in r["non_retenues"]] == ["333"]


def test_structures_verifiees_un_public():
    """Liste vérifiée pour les seuls CMP pour adultes (« lieu_cmp:adultes ») : un CMP pour adultes non cité est retiré,
    un CMP pour enfants et un CMP au public non précisé restent tels que les bases les donnent."""
    import tempfile
    from pathlib import Path
    import pandas as pd
    from pipeline import structures_verifiees as sv
    d = Path(tempfile.mkdtemp())
    origine = (sv.FICHIER_ETAB, sv.FICHIER)
    sv.FICHIER_ETAB, sv.FICHIER = d / "e.csv", d / "s.csv"
    pd.DataFrame([{"ej": "E", "etablissement": "CHU", "departement": "", "types": "lieu_cmp:adultes",
                   "date": "2026-10-15", "sources": "site", "empreinte": "", "remarque": ""}]).to_csv(
        sv.FICHIER_ETAB, sep=";", index=False)
    pd.DataFrame([{"ej": "E", "etablissement": "CHU", "type": "lieu_cmp", "public": "adultes", "nom": "CMP Massane",
                   "adresse": "", "commune": "34172", "statut": "etablissement", "finess": "111", "source": "site",
                   "adresse_source": "https://x", "date": "2026-10-15", "remarque": ""}]).to_csv(sv.FICHIER, sep=";",
                                                                                                 index=False)
    lieux = pd.DataFrame({"type": ["lieu_cmp", "lieu_cmp_adultes", "lieu_cmp", "lieu_cmp_adultes", "lieu_cmp",
                                   "lieu_cmp_enfants", "lieu_cmp"],
                          "lieu": ["a", "a", "b", "b", "c", "c", "d"],
                          "nom": ["CMP MASSANE", "CMP MASSANE", "CMP GIGNAC", "CMP GIGNAC", "CMP ENFANTS LUNEL",
                                  "CMP ENFANTS LUNEL", "CMP SANS PUBLIC"], "ej": ["E"] * 7,
                          "finess": ["111", "111", "222", "222", "333", "333", "444"], "commune": ["34172"] * 7,
                          "dep": ["34"] * 7, "adresse": ["R A", "R A", "R B", "R B", "R C", "R C", "R D"],
                          "provenance": ["les_deux"] * 7, "lat": [43.6] * 7, "lon": [3.9] * 7,
                          "precision": ["finess"] * 7})

    class Ref:
        communes = pd.DataFrame({"code": ["34172"], "nom": ["Montpellier"], "dep": ["34"], "epci": ["X"], "reg": ["76"]})
    x, r = sv.appliquer(lieux, Ref(), {}, True)
    sv.FICHIER_ETAB, sv.FICHIER = origine
    assert set(x.loc[x["type"] == "lieu_cmp", "nom"]) == {"CMP Massane", "CMP ENFANTS LUNEL", "CMP SANS PUBLIC"}
    assert list(x.loc[x["type"] == "lieu_cmp_adultes", "nom"]) == ["CMP Massane"]
    assert list(x.loc[x["type"] == "lieu_cmp_enfants", "nom"]) == ["CMP ENFANTS LUNEL"]
    assert [n["finess"] for n in r["non_retenues"]] == ["222"] and not r["gardees"]


def test_structures_verifiees_orphelin_meme_rue():
    """Une structure vérifiée donnée par son numéro FINESS absorbe aussi l'unité du ROR sans établissement de la même
    commune et de la même rue, pas celle d'une autre rue."""
    import tempfile
    from pathlib import Path
    import pandas as pd
    from pipeline import structures_verifiees as sv
    d = Path(tempfile.mkdtemp())
    origine = (sv.FICHIER_ETAB, sv.FICHIER)
    sv.FICHIER_ETAB, sv.FICHIER = d / "e.csv", d / "s.csv"
    pd.DataFrame([{"ej": "E", "etablissement": "H", "departement": "", "types": "lieu_cmp", "date": "2026-10-15",
                   "sources": "site", "empreinte": "", "remarque": ""}]).to_csv(sv.FICHIER_ETAB, sep=";", index=False)
    pd.DataFrame([{"ej": "E", "etablissement": "H", "type": "lieu_cmp", "public": "enfants", "nom": "CMP Anatole-France",
                   "adresse": "33 avenue Anatole France", "commune": "94018", "statut": "etablissement",
                   "finess": "111", "source": "site", "adresse_source": "https://x", "date": "2026-10-15",
                   "remarque": ""}]).to_csv(sv.FICHIER, sep=";", index=False)
    lieux = pd.DataFrame({"type": ["lieu_cmp"] * 3, "lieu": ["a", "b", "c"],
                          "nom": ["CMP ANATOLE FRANCE", "CMP perinatalite 94I03", "CMP AUTRE 94I03"],
                          "ej": ["E", None, None], "finess": ["111", None, None], "commune": ["94018"] * 3,
                          "dep": ["94"] * 3, "adresse": ["AV ANATOLE FRANCE", "AVENUE ANATOLE FRANCE", "RUE DE PARIS"],
                          "provenance": ["les_deux", "ror", "ror"], "lat": [48.8] * 3, "lon": [2.4] * 3,
                          "precision": ["finess"] * 3})

    class Ref:
        communes = pd.DataFrame({"code": ["94018"], "nom": ["Charenton-le-Pont"], "dep": ["94"], "epci": ["X"],
                                 "reg": ["11"]})
    x, r = sv.appliquer(lieux, Ref(), {}, True)
    sv.FICHIER_ETAB, sv.FICHIER = origine
    assert set(x.loc[x["type"] == "lieu_cmp", "nom"]) == {"CMP Anatole-France", "CMP AUTRE 94I03"}


def test_confirmation():
    """Un CMP est confirmé par la HAS quand son numéro FINESS est un site de certification nommé CMP, par Sirene
    quand son gestionnaire a un établissement actif sous une enseigne de CMP dans la même commune. Un établissement
    Sirene sans correspondant est listé, pas ajouté."""
    import pandas as pd
    from pipeline.confirmation import confirmer
    L = pd.DataFrame({"type": ["lieu_cmp", "lieu_cmp", "lieu_cmp", "lieu_cmp_adultes"], "lieu": ["a", "b", "c", "a"],
                      "nom": ["CMP Les Lilas", "CMP Nord", "CMP X", "CMP Les Lilas"], "ej": ["E"] * 4,
                      "finess": ["111", "222", "333", "111"], "commune": ["01001", "01002", "01003", "01001"],
                      "adresse": ["rue A", "rue B", "rue C", "rue A"], "statut_verification": [None] * 4})
    has = {"sites": pd.DataFrame({"FINESS_EJ": ["E", "E"], "FINESS_EG": ["111", "333"],
                                  "RS_eg": ["CMP LES LILAS", "HOPITAL DE JOUR"]})}
    sir = {"siren": {"E": "S1"}, "etablissements": pd.DataFrame({
        "siren": ["S1", "S1", "S1"], "siret": ["1", "2", "3"], "etatAdministratifEtablissement": ["A", "A", "F"],
        "enseigne": ["CMP NORD", "CMP SUD", "CMP X"], "adresse": ["rue B", "rue D", "rue C"],
        "codeCommuneEtablissement": ["01002", "01004", "01003"], "dateCreationEtablissement": ["2000", "2001", "1999"]})}
    x, sans = confirmer(L, has, sir)
    c = x[x["type"] == "lieu_cmp"].set_index("lieu")["confirmation"]
    assert c["a"] == "has" and c["b"] == "sirene" and c["c"] == "bases"
    assert x.loc[x["type"] == "lieu_cmp_adultes", "confirmation"].iloc[0] == "has"
    assert list(sans["siret"]) == ["2"]


def test_confirmation_autres_types():
    """Un CMPP évalué par la HAS sous la catégorie des CMPP est confirmé, pas un CMPP évalué sous une autre catégorie.
    Un hôpital de jour pour adultes n'est confirmé ni par un établissement Sirene pour enfants, ni par un hôpital de
    jour d'une autre discipline. Un hôpital de jour pour enfants l'est par l'enseigne pour enfants."""
    import pandas as pd
    from pipeline.confirmation import confirmer
    L = pd.DataFrame({"type": ["lieu_cmpp", "lieu_cmpp", "lieu_hdj_psy_adultes", "lieu_hdj_psy_adultes",
                               "lieu_hdj_psy_enfants"],
                      "lieu": ["p1", "p2", "h1", "h2", "h3"], "nom": ["CMPP A", "CMPP B", "HDJ Rivage", "HDJ Mistral",
                                                                    "HDJ Petits Pas"],
                      "ej": ["A", "A", "E", "E", "E"], "finess": ["111", "222", "333", "333", "333"],
                      "commune": ["01001", "01001", "01002", "01003", "01002"], "adresse": ["r"] * 5,
                      "statut_verification": [None] * 5})
    ess = {"evaluations": pd.DataFrame({"finess": ["111", "222"], "categorie": ["189", "190"],
                                        "date": pd.to_datetime(["2024-01-01"] * 2)})}
    sir = {"siren": {"E": "S1"}, "etablissements": pd.DataFrame({
        "siren": ["S1"] * 3, "siret": ["1", "2", "3"], "etatAdministratifEtablissement": ["A"] * 3,
        "enseigne": ["HDJ PEDOPSYCHIATRIE LES PETITS PAS", "HOPITAL DE JOUR GERIATRIQUE", "HDJ MISTRAL"],
        "adresse": ["r"] * 3, "codeCommuneEtablissement": ["01002", "01002", "01003"],
        "dateCreationEtablissement": ["2000"] * 3})}
    x, sans = confirmer(L, None, sir, ess)
    c = x.set_index("lieu")["confirmation"]
    assert c["p1"] == "has" and c["p2"] == "bases"
    assert c["h1"] == "bases" and c["h2"] == "sirene" and c["h3"] == "sirene"
    assert x.set_index("lieu").at["h3", "siret_sirene"] == "1"


def test_confirmation_par_sae():
    """Un CATTP non confirmé d'un hôpital au nombre concordant avec la SAE prend le niveau « sae », pas celui d'un
    hôpital en écart, et un CATTP déjà confirmé par la HAS garde son niveau."""
    import pandas as pd
    from pipeline.confirmation import confirmer_par_sae
    L = pd.DataFrame({"type": ["lieu_cattp"] * 3 + ["lieu_cmp"], "ej": ["A", "A", "B", "A"],
                      "confirmation": ["bases", "has", "bases", "bases"]})
    e = pd.DataFrame({"ej": ["A", "B"], "statut_cattp": ["concorde", "moins ici qu'à la SAE"]})
    x = confirmer_par_sae(L, e)
    assert x["confirmation"].tolist() == ["sae", "has", "bases", "bases"]
    # hôpitaux de jour, places déclarées à la SAE pour le site, dans la discipline du public
    H = pd.DataFrame({"type": ["lieu_hdj_psy_adultes", "lieu_hdj_psy_enfants", "lieu_hdj_psy_enfants"],
                      "ej": ["A"] * 3, "finess": ["111", "111", "222"], "confirmation": ["bases"] * 3})
    h = confirmer_par_sae(H, None, {"hdj_sites": {"GEN": {"111"}, "INF": {"222"}}})
    assert h["confirmation"].tolist() == ["sae", "bases", "sae"]


def test_cattp_des_cmp():
    """Un CMP qui annonce un CATTP dans son nom ou son enseigne Sirene reçoit un CATTP au même lieu, sauf si son
    gestionnaire a déjà un CATTP dans la commune. Le niveau de confirmation suit la source qui l'annonce."""
    import pandas as pd
    from pipeline.lieux import cattp_des_cmp
    L = pd.DataFrame({"type": ["lieu_cmp", "lieu_cmp", "lieu_cmp", "lieu_cattp", "lieu_cmp"],
                      "lieu": ["a", "b", "c", "d", "e"],
                      "nom_affiche": ["CMP-CATTP Les Lilas", "CMP Nord", "CMP CATTP Sud", "CATTP Sud", "CMP Est"],
                      "nom": [None] * 5, "enseigne_sirene": [None, "CMP CATTP NORD", None, None, None],
                      "ej": ["A", "A", "B", "B", "C"], "commune": ["1", "2", "3", "3", "4"],
                      "statut_verification": [None] * 5, "confirmation": ["has", "sirene", "bases", "bases", "bases"],
                      "provenance": ["les_deux"] * 5})
    x, n = cattp_des_cmp(L)
    ajout = x[x["provenance"] == "nom_cmp"].set_index("lieu")
    assert n == 2 and set(ajout.index) == {"a|cattp", "b|cattp"}
    assert ajout.at["a|cattp", "confirmation"] == "bases" and ajout.at["b|cattp", "confirmation"] == "sirene"
    assert (ajout["type"] == "lieu_cattp").all()


def test_fusion_meme_adresse():
    """Un même lieu déclaré deux fois à la même adresse est réuni, deux lieux distincts de la même avenue restent deux."""
    import pandas as pd
    from pipeline.lieux import fusion_meme_adresse
    L = pd.DataFrame({
        "type": ["lieu_cmp", "lieu_cmp", "lieu_cmp", "lieu_cmp", "lieu_cmp_adultes", "lieu_cmp_adultes"],
        "lieu": ["a|A", "b|A", "c|A", "d|A", "a|A", "b|A"],
        "nom": ["CMP Le Petit Nice", "CMP Petit Nice - 05G05", "CMP La Viste", "CMP Le Parc", "CMP Le Petit Nice",
                "CMP Petit Nice - 05G05"],
        "adresse": ["R de la liberté", "R DE LA LIBERTE", "AV DE LA VISTE", "AV DE LA VISTE", "R de la liberté",
                    "R DE LA LIBERTE"],
        "commune": ["05046"] * 2 + ["13215"] * 2 + ["05046"] * 2, "ej": ["E1"] * 2 + ["E2"] * 2 + ["E1"] * 2,
        "finess": ["111", "222", "333", "444", "111", "222"], "provenance": ["les_deux"] * 6,
        "categorie_finess": ["156", "292", "156", "156", "156", "292"]})
    r, n = fusion_meme_adresse(L)
    assert n == 1 and len(r[r["type"] == "lieu_cmp"]) == 3
    assert r.loc[(r["type"] == "lieu_cmp") & (r["lieu"] == "a|A"), "finess_absorbes"].iloc[0] == "222"
    assert len(r[r["type"] == "lieu_cmp_adultes"]) == 1
    # deux établissements de FINESS de la même catégorie, ou de deux catégories propres au type, restent deux lieux
    L3 = L.assign(type="lieu_foyers_handicap", categorie_finess=["382", "252", "382", "382", "382", "252"])
    r3, n3 = fusion_meme_adresse(L3)
    assert n3 == 0
    L2 = L.assign(categorie_finess="156")
    r2, n2 = fusion_meme_adresse(L2)
    assert n2 == 0
    # deux structures du ROR seul sous deux numéros FINESS médico-sociaux restent deux, même si leurs noms se ressemblent
    L4 = L.assign(type="lieu_foyers_handicap", provenance="ror", categorie_finess=None,
                  nom=["FOYER LE RIOU - Accueil de Jour", "FOYER LE RIOU - Hébergement complet"] + ["x", "y"] * 2)
    assert fusion_meme_adresse(L4, pd.Series({"111": "382", "222": "252"}))[1] == 0
    # sous le numéro d'un hôpital, un même CMP décrit deux fois est réuni, deux secteurs ou deux publics restent deux
    L5 = L.assign(provenance="ror", categorie_finess=None, finess="999",
                  nom=["CATTP Gaillac 81I01", "CATTP Gaillac 81G01", "CMP pédo La Possession", "CMP La Possession",
                       "a", "b"])
    assert fusion_meme_adresse(L5, pd.Series({"999": "355"}))[1] == 0
    L6 = L5.assign(nom=["CMP Autun", "CMP adultes Autun", "CMP x", "CMP y", "a", "b"])
    assert fusion_meme_adresse(L6, pd.Series({"999": "355"}))[1] == 1
    # un CMP du ROR seul placé à l'adresse de son hôpital (commune tirée du nom) rejoint le CMP du même hôpital, du même
    # public et de la même commune décrit avec son adresse, sauf s'il dit un autre public (gérontopsychiatrie)
    L7 = pd.DataFrame({"type": ["lieu_cmp"] * 3, "lieu": ["p|A", "q|A", "s|A"],
                       "nom": ["PLVD - CMP Apt", "CMP APT - Secteur PSEV", "Gérontopsychiatrie Apt"],
                       "adresse": ["AV DE LA PINEDE", "R PHILIPPE DE GIRARD", "AV DE LA PINEDE"],
                       "commune": ["84003"] * 3, "ej": ["E"] * 3, "finess": ["9", "8", "9"],
                       "provenance": ["ror", "les_deux", "ror"], "origine_commune": ["nom", "unite", "nom"],
                       "categorie_finess": [None, "156", None]})
    r7, n7 = fusion_meme_adresse(L7, pd.Series({"9": "292", "8": "156"}))
    assert n7 == 1 and set(r7["nom"]) == {"CMP APT - Secteur PSEV", "Gérontopsychiatrie Apt"}
    # même CMP décrit à deux adresses (ancienne et nouvelle), noms réduits à la commune et à un sigle de pôle, réunis à
    # l'adresse donnée par l'unité du ROR. Deux CMP de FINESS de même nom, ou « Nord » et « Sud », restent deux.
    L8 = pd.DataFrame({"type": ["lieu_cmp"] * 6, "lieu": ["c1|E", "c2|E", "m1", "m2", "t1|A", "t2|A"],
                       "nom": ["CMPI CAVAILLON - Secteur PES", "PPEA - CMPEA CAVAILLON", "CMP DE MANTES",
                               "CMP DE MANTES", "CMP Troyes Nord", "CMP Troyes Sud"],
                       "adresse": ["R du comtat", "AV de verdun", "222 BD", "222 BD", "AV PASTEUR", "AV FOCH"],
                       "commune": ["84035", "84035", "78361", "78361", "10387", "10387"], "ej": ["E", "E", "M", "M", "T", "T"],
                       "finess": ["1", "2", "3", "4", "5", "6"],
                       "provenance": ["les_deux", "ror", "finess", "finess", "les_deux", "ror"],
                       "origine_commune": ["unite", "unite", None, None, "unite", "unite"], "categorie_finess": None})
    noms_c = pd.Series({"84035": "Cavaillon", "78361": "Mantes-la-Jolie", "10387": "Troyes"})
    r8, n8 = fusion_meme_adresse(L8, None, noms_c)
    assert n8 == 1 and len(r8) == 5
    assert r8.loc[r8["lieu"] == "c1|E", "adresse"].iloc[0] == "AV de verdun"


def test_concordance_etablissements():
    """Confrontation des CMP à la SAE hôpital par hôpital, tolérance de 20 % ou d'un CMP."""
    import pandas as pd
    from pipeline.lieux import concordance_etablissements, niveau_concordance
    L = {"lieux": pd.DataFrame({"type": ["lieu_cmp"] * 5 + ["lieu_cmp_adultes"] * 5,
                                "ej": ["A", "A", "B", "C", "C"] * 2, "nom_finess": ["x"] * 10})}
    s = pd.DataFrame({"sae_adultes": [2, 10, 2], "sae_enfants": [0, 0, 0], "sae_cattp": [0, 0, 0],
                      "nom_sae": ["Hôpital A", "Hôpital B", "Hôpital D"], "dep_siege": ["01", "02", "03"]},
                     index=pd.Index(["A", "B", "D"], name="ej"))
    t = concordance_etablissements(L, {"etablissements": s}).set_index("ej")
    assert t.at["A", "statut"] == "concorde" and t.at["B", "statut"] == "moins ici qu'à la SAE"
    assert t.at["C", "statut"] == "absent de la SAE" and t.at["D", "statut"] == "moins ici qu'à la SAE"
    assert t.at["B", "ecart"] == -9
    assert niveau_concordance(.1) == "les sources concordent" and niveau_concordance(-.5).startswith("écart important")


def test_concordance_cattp():
    """CATTP confrontés à la SAE par département, région et France, et hôpital par hôpital (statut_cattp vide pour un
    hôpital sans CATTP ni ici ni à la SAE)."""
    import pandas as pd
    from pipeline.lieux import concordance_cattp, concordance_etablissements

    class Ref:
        deps = pd.DataFrame({"code": ["01", "02"], "reg": ["84", "84"]})
    L = {"lieux": pd.DataFrame({"type": ["lieu_cattp"] * 4 + ["lieu_cmp"], "dep": ["01", "01", "01", "02", "02"],
                                "reg": ["84"] * 5, "fr": ["FR"] * 5, "ej": ["A", "A", "A", "B", "B"],
                                "nom_finess": ["x"] * 5})}
    sae = {"cattp_disciplines": pd.DataFrame({"GEN": [2, 5], "INF": [1, 0]}, index=pd.Index(["01", "02"], name="dep"))}
    t = concordance_cattp(L, sae, Ref()).set_index(["niveau", "code"])
    assert t.loc[("dep", "01"), "cattp"] == 3 and t.loc[("dep", "01"), "sae_cattp"] == 3
    assert t.loc[("dep", "02"), "ecart_relatif"] == -0.8 and t.loc[("reg", "84"), "sae_cattp"] == 8
    assert t.loc[("fr", "FR"), "cattp"] == 4 and t.loc[("dep", "01"), "concordance"] == "les sources concordent"
    s = pd.DataFrame({"sae_adultes": [1, 1, 1], "sae_enfants": [0, 0, 0], "sae_cattp": [3, 6, 0],
                      "nom_sae": ["A", "B", "C"], "dep_siege": ["01", "02", "02"]}, index=pd.Index(["A", "B", "C"], name="ej"))
    e = concordance_etablissements(L, {"etablissements": s}).set_index("ej")
    assert e.at["A", "statut_cattp"] == "concorde" and e.at["B", "statut_cattp"] == "moins ici qu'à la SAE"
    assert pd.isna(e.at["C", "statut_cattp"])


def test_cmp_publics_et_retypage():
    """Le total des CMP se retrouve par public, et un établissement enregistré comme CMP dont le nom désigne autre chose
    (équipe mobile, CATTP, unité pénitentiaire) est rangé dans le bon type, sans écarter un CMP pour personnes âgées."""
    import re
    import pandas as pd
    from pipeline import config
    from pipeline.lieux import repartition_cmp
    from pipeline.util import norm
    L = pd.DataFrame({"type": ["lieu_cmp"] * 4 + ["lieu_cmp_adultes", "lieu_cmp_enfants", "lieu_cmp_adultes",
                                                   "lieu_cmp_enfants"],
                      "lieu": ["a", "b", "c", "d", "a", "b", "c", "c"], "dep": ["01"] * 8})
    r = repartition_cmp(L, "dep").loc["01"]
    assert (r["cmp"], r["adultes"], r["enfants"], r["les_deux"], r["non_precise"]) == (4, 2, 2, 1, 1)
    assert r["adultes"] + r["enfants"] - r["les_deux"] + r["non_precise"] == r["cmp"]
    def cible(nom):
        n = norm(nom)
        return next((t for m, t in config.RETYPAGE_CMP_FINESS if re.search(m, n)), None)
    assert cible("EQUIPE MOBILE DE SOUTIEN AU LOGEMENT") == "lieu_mobile_psy"
    assert cible("USMP MAISON CENTRALE ARLES") == "lieu_consult_psy"
    assert cible("EQUIPE DE LIAISON EN SOINS EN ADDICTOLOGIE (ELSA)") == "lieu_addicto_hosp"
    assert cible("CMP FORCALQUIER") is None
    assert not re.search(config.LIEUX_EXCLUS_CMP, norm("CMPPA")) and re.search(config.NOM_CMP, norm("CMPPA"))
    assert re.search(config.LIEUX_EXCLUS_CMP, norm("CMPP Les Tilleuls"))
    assert re.search(config.NOM_SECTEUR_ENFANTS, norm("CENTRE MEDICO-PSYCHOLOGIQUE 59I12"))
    assert re.search(config.NOM_ADULTES, norm("LIAISON URGENCES LISIEUX (14G07)"))


def test_lieux_noms_respectueux():
    """Les termes à proscrire des raisons sociales sont remplacés sans perdre le sigle ni le nom propre."""
    from pipeline import libelles
    from pipeline.lieux import nom_respectueux as n
    assert n("IME POLY HANDICAPES LES MUSCARIS") == "IME POUR PERSONNES EN SITUATION DE POLYHANDICAP LES MUSCARIS"
    assert n("Foyer pour adultes handicapés") == "Foyer pour adultes en situation de handicap"
    assert n("EHPAD PERS AGEES DEPENDANTES") == "EHPAD POUR PERSONNES ÂGÉES EN PERTE D'AUTONOMIE"
    assert n("Centre pour alcooliques") == "Centre pour personnes ayant une addiction à l'alcool"
    assert n("ESAT Les Papillons") == "ESAT Les Papillons"
    for s in ["SESSAD DEFICIENTS AUDITIFS", "AIDE AUX HANDICAPES", "CURE POUR TOXICOMANES", "ENFANTS INADAPTES"]:
        assert not libelles.termes_proscrits(n(s)), s
    # nom affiché, nom propre gardé, terme retiré s'il reste de quoi identifier le lieu, réécrit sinon
    from pipeline.lieux import nom_lisible as nl
    assert nl("IME POLY HANDICAPES LES MUSCARIS")[0] == "IME LES MUSCARIS"
    assert nl("ESAT LES OLIVIERS - Aide par le travail pour Adultes Handicapés - Accueil de jour - "
              "Déficience intellectuelle")[0] == "ESAT LES OLIVIERS"
    assert nl("SAMSAH - LES PAPILLONS BLANCS")[0] == "SAMSAH - LES PAPILLONS BLANCS"
    assert nl("Hébergement pour personnes âgées dépendantes", "EHPAD Le Parc") == ("EHPAD Le Parc", "rattachement")
    assert nl("FOYER POUR HANDICAPES")[1] == "reecrit"
    assert nl("CMP Munster - Psy adulte")[0] == "CMP Munster - Psy adulte"


def test_lieux_enfants_et_communes():
    """Unités pour enfants (âge, catégorie, nom) et commune citée dans le nom d'une unité."""
    import pandas as pd
    from types import SimpleNamespace
    from pipeline import lieux
    u = pd.DataFrame({"categorie": ["10", "281", "10", "10"], "age_max": [21.0, 150.0, 150.0, 65.0],
                      "nom": ["CMP Rouffach", "CMP", "CMP pédopsychiatrie Nord", "CMP Munster - Psy adulte"]})
    assert lieux._enfants(u).tolist() == [True, True, True, False]
    ref = SimpleNamespace(communes=pd.DataFrame({"code": ["68226", "68287", "68004", "68005"],
                                                 "nom": ["Munster", "Rouffach", "Saint-Louis", "Saint-Louis"],
                                                 "dep": ["68", "68", "68", "68"]}))
    noms = pd.Series(["CMP Munster - Psy adulte", "CMP Pavillon 4", "CMP St Louis"], index=[10, 11, 12])
    r = lieux.communes_du_nom(noms, pd.Series(["68", "68", "68"], index=noms.index), ref)
    # Munster trouvée, aucune commune dans « Pavillon 4 », « St Louis » ambigu (deux communes de ce nom) écarté
    assert r.to_dict() == {10: "68226"}, r
    # le nom de l'hôpital gestionnaire, cité en fin de nom, n'est pas la commune de l'unité (constat du 15 octobre 2026)
    ref = SimpleNamespace(communes=pd.DataFrame({"code": ["62215", "62427", "59606"],
                                                 "nom": ["Carvin", "Hénin-Beaumont", "Valenciennes"],
                                                 "dep": ["62", "62", "59"]}))
    noms = pd.Series(["CMP ADULTES CARVIN CH HENIN BEAUMONT", "CMP 59G30 CONDE/ESCAU CH VALENCIENNES"], index=[1, 2])
    r = lieux.communes_du_nom(noms, pd.Series(["62", "59"], index=noms.index), ref)
    # sans commune avant le nom de l'hôpital, le nom entier est lu
    assert r.to_dict() == {1: "62215", 2: "59606"}, r
    # Valenciennes, seulement dans le nom de l'hôpital et commune d'un hôpital du gestionnaire, n'est pas retenue
    r = lieux.communes_du_nom(noms, pd.Series(["62", "59"], index=noms.index), ref,
                              pd.Series({1: {"62427"}, 2: {"59606"}}))
    assert r.to_dict() == {1: "62215"}, r


def test_lieux_reunion_sans_double_compte():
    """Un même établissement dans les deux bases compte une fois, un CMP de FINESS rattaché dans le ROR à son hôpital
    (même entité juridique et même commune) aussi, deux CMP de FINESS d'un même hôpital restent deux lieux."""
    import pandas as pd
    from pipeline import lieux
    lr = pd.DataFrame({"type": ["lieu_cmp"] * 3, "lieu": ["F111|01001", "F900|02002|A", "F900|02002|E"],
                       "finess": ["111", "900", "900"], "ej": ["EJ1", "EJ9", "EJ9"], "commune": ["01001", "02002", "02002"],
                       "nom": ["CMP A", "CMP adultes B", "CMP enfants B"], "structure_nom": ["CMP A", "CH", "CH"]})
    lf = pd.DataFrame({"type": ["lieu_cmp"] * 4, "lieu": ["F111|01001", "F201|02002", "F202|02002", "F301|03003"],
                       "finess": ["111", "201", "202", "301"], "ej": ["EJ1", "EJ9", "EJ9", "EJ3"],
                       "commune": ["01001", "02002", "02002", "03003"], "nom_finess": ["CMP A", "CMP B1", "CMP B2", "CMP C"],
                       "categorie_finess": ["156"] * 4})
    cat = pd.Series({"111": "156", "900": "292", "201": "156", "202": "156", "301": "156"})
    out, stats = lieux.reunir(lr, lf, cat)
    assert len(out) == 4 and not out.duplicated(["type", "lieu"]).any(), out
    assert stats["rapproches_entite_juridique"] == 2 and stats["finess_seul"] == 1, stats
    assert out["provenance"].value_counts().to_dict() == {"les_deux": 3, "finess": 1}


def test_lieux_unite_a_la_commune_du_siege():
    """Un CMP enregistré sous son propre numéro FINESS, que le ROR déclare dans la commune de l'hôpital de son
    gestionnaire, prend la commune et l'adresse de FINESS. Déclaré dans une commune sans hôpital du gestionnaire, il
    garde celle du ROR (cas de Carvin et d'une antenne réelle)."""
    import numpy as np
    import pandas as pd
    from pipeline import lieux
    fin = pd.DataFrame({"nofinesset": ["H1", "C1", "C2", "K1"], "nofinessej": ["EJ"] * 4,
                        "categetab": ["355", "156", "156", "292"], "com": ["62427", "62215", "62413", "62160"],
                        "adresse": ["rue de l'hôpital", "29 rue Florent-Évrard", "rue Émile-Zola", "163 rue du Chemin-Vert"],
                        "rs": ["CH Hénin-Beaumont", "CMP Carvin", "CMP Harnes", "CMP CATTP Le Chemin vert"]})
    u = pd.DataFrame({"cle": ["u1", "u2", "u3"], "commune": ["62427", "62999", "62427"], "structure": ["s1", "s2", "s3"],
                      "finess_ror": ["C1", "C2", "K1"], "voie": ["29 rue Florent Evrard", "place X", "163 rue du Chemin vert"],
                      "nom": ["CMP adultes Carvin CH Hénin", "CMP adultes Harnes", "CMP Chemin vert"],
                      "lat": [50.4, 50.5, 50.4], "lon": [2.9, 2.9, 2.9], "categorie": ["10"] * 3, "age_min": [18.0] * 3,
                      "age_max": [99.0] * 3, "lits": [0] * 3, "maj": ["2026"] * 3, "structure_nom": ["CMP"] * 3,
                      "origine_commune": ["unite"] * 3})
    classes = pd.DataFrame({"cle": ["u1", "u2", "u3"], "type": ["lieu_cmp"] * 3})
    x = lieux._lieux_ror(u, classes, fin).set_index("finess")
    # Carvin, déclaré à Hénin-Beaumont (commune de l'hôpital), placé à Carvin avec l'adresse de FINESS
    assert x.at["C1", "commune"] == "62215" and x.at["C1", "voie"] == "29 rue Florent-Évrard"
    assert np.isnan(x.at["C1", "lat_ror"])
    # déclaré ailleurs que dans une commune d'hôpital du gestionnaire, le ROR garde la main
    assert x.at["C2", "commune"] == "62999"
    # un CMP que FINESS range parmi les hôpitaux spécialisés n'est pas pris pour un hôpital
    assert x.at["K1", "commune"] == "62160"


def test_finess_coordonnees_en_degres():
    """Finess+ range parfois le Lambert 93 dans coordonneeX et coordonneeY et les degrés dans les champs direction,
    la paire en degrés est retenue."""
    from pipeline.sources import finess
    assert finess._degres({"coordonneeX": "5.254203", "coordonneeY": "46.211257",
                           "directionLatitude": "6570414.61", "directionLongitude": "873766.07"}) == (46.211257, 5.254203)
    assert finess._degres({"coordonneeX": "872835.21", "coordonneeY": "6569568.1",
                           "directionLatitude": "46.203876", "directionLongitude": "5.241822"}) == (46.203876, 5.241822)
    assert finess._degres({"coordonneeX": None, "coordonneeY": "6569568.1"}) == (None, None)


def test_lieux_hors_commune():
    """Un point hors du contour de sa commune (à la tolérance près) est repéré, un point sans contour connu non."""
    import pandas as pd
    from shapely.geometry import box
    from pipeline import lieux
    formes = {"A": box(0, 0, 1, 1)}
    lat = pd.Series([0.5, 2.0, 1.001, 0.5])
    lon = pd.Series([0.5, 0.5, 0.5, 0.5])
    r = lieux.hors_commune(lat, lon, pd.Series(["A", "A", "A", "B"]), formes)
    assert r.tolist() == [False, True, False, False], r
    assert not lieux.hors_commune(lat, lon, pd.Series(["A"] * 4), None).any()


def test_parcours():
    import pandas as pd
    from pipeline import build
    act = pd.DataFrame({
        "id": ["a", "a", "b", "c", "d", "e"],
        "prof": ["psychologue"] * 6,
        "com": ["75056", "13055", None, "75056", "75056", None],
        "secteur": ["Cabinet", "Société de téléconsultation", "Cabinet", "Société de téléconsultation",
                    "Industrie", "Cabinet"],
    })
    cat = pd.Series(["soins", "a_distance", "soins", "a_distance", "sans_soins", "soins"], index=act.index)
    loc = act[act["com"].notna() & ~cat.isin(["a_distance", "sans_soins"])]
    t = build.parcours(act, cat, loc).set_index("prof").loc["psychologue"]
    # a soigne (compté), b et e sans lieu, c seulement téléconsultation, d seulement industrie
    assert (t["avec_activite"], t["sans_lieu"], t["avec_lieu"], t["dans_densites"]) == (5, 2, 3, 1)
    assert (t["a_distance_seulement"], t["sans_soins_seulement"]) == (1, 1)


def test_journal_meme_jour():
    import tempfile
    from pathlib import Path
    import pandas as pd
    from pipeline import mises_a_jour as M
    fichier, etat_sources = M.FICHIER, M.etat_sources
    jeu = lambda maj: {"RPPS": {"producteur": "ANS", "maj": maj, "recupere": maj,  # noqa: E731
                                "fichiers": {"rpps_a.txt": {"maj": maj, "signature": maj, "recupere": maj}}}}
    nat = lambda n: pd.DataFrame({"prof": ["psychologue"], "mode": ["all"], "n": [n]})  # noqa: E731
    try:
        with tempfile.TemporaryDirectory() as d:
            M.FICHIER = Path(d) / "journal.json"
            M.etat_sources = lambda: jeu("2026-10-03")
            e1 = M.consigner("2026-10-08", nat(80765), {"psychologue": "Psychologue"})
            assert e1["premiere"] and e1["sources"] == []
            # même jour, nouvelle version du RPPS, le changement doit apparaître dans l'entrée du jour
            M.etat_sources = lambda: jeu("2026-10-08")
            e2 = M.consigner("2026-10-08", nat(80900), {"psychologue": "Psychologue"})
            assert [s["jeu"] for s in e2["sources"]] == ["RPPS"] and e2["sources"][0]["maj_avant"] == "2026-10-03"
            assert e2["variations"][0]["avant"] == 80765 and e2["variations"][0]["apres"] == 80900
            assert len(M.lire()) == 1
            # jour suivant sans changement, l'entrée du 8 est gardée, la nouvelle ne signale rien
            e3 = M.consigner("2026-10-09", nat(80900), {"psychologue": "Psychologue"})
            assert e3["sources"] == [] and e3["variations"] == [] and len(M.lire()) == 2
    finally:
        M.FICHIER, M.etat_sources = fichier, etat_sources


def test_verification_versions():
    import json
    import tempfile
    from pathlib import Path
    from pipeline import verification as V
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "caf_x.csv"
        assert V.comparer(f, "2026-09-28T01:15:12+00:00", {})[0] == V.ABSENT
        (Path(d) / "caf_x.csv.meta.json").write_text(json.dumps({"maj_source": "2026-09-28T01:15:12+00:00", "mois": "2024-12"}))
        assert V.comparer(f, "2026-09-28T01:15:12+00:00", {"mois": "2024-12"}) == (V.A_JOUR, "2026-09-28T01:15:12+00:00")
        assert V.comparer(f, "2026-10-28T01:15:12+00:00", {"mois": "2024-12"})[0] == V.NOUVELLE
        # même date mais nouveau millésime publié
        assert V.comparer(f, "2026-09-28T01:15:12+00:00", {"mois": "2025-12"})[0] == V.NOUVELLE
        assert V.comparer(f, "", {})[0] == V.INCONNU


def test_minuscule():
    from pipeline.lecture import minuscule, phrase_correlation
    assert minuscule("Taux de pauvreté") == "taux de pauvreté"
    assert minuscule("AAH versée") == "AAH versée" and minuscule("") == ""
    assert "« bénéficiaires de l'AAH »" in phrase_correlation(.4, "Bénéficiaires de l'AAH", "Psychologue")


def test_ald_tableau():
    import pandas as pd
    from pipeline.sources import ameli_ald
    feuille = pd.DataFrame([["", "", "Tableau VII", ""],
                            ["Code département", "Nom du département", "Diabète de type 1 et diabète de type 2 (ALD8)",
                             "Affections psychiatriques de longue durée (ALD23)"],
                            ["01", "Ain", "1200", "<10"], ["2A", "Corse-du-Sud", "300", "40"],
                            ["* Pour Mayotte", "", "", ""]])
    t = ameli_ald._tableau(feuille)
    assert list(t["code"].unique()) == ["01", "2A"] and set(t["ald"]) == {8, 23}
    assert t.loc[(t["code"] == "01") & (t["ald"] == 23), "brut"].iloc[0] == "<10"
    assert t.loc[t["ald"] == 8, "libelle_officiel"].iloc[0] == "Diabète de type 1 et diabète de type 2"


def test_temps_acces():
    from types import SimpleNamespace
    import pandas as pd
    # poids uniformes dans chaque tranche d'une minute, la moitié du poids est atteinte à 2 minutes
    assert abs(A.mediane_histogramme([0, 1, 2], [1, 1, 2]) - 2.0) < 1e-12
    assert abs(A.mediane_histogramme([5], [3]) - 5.5) < 1e-12
    ref = SimpleNamespace(communes=pd.DataFrame({"code": ["A", "B", "C"], "epci": ["E1", "E1", "E2"],
                                                 "dep": ["01", "01", "02"]}),
                          deps=pd.DataFrame({"code": ["01", "02"], "reg": ["R", "R"]}))
    # la commune C a 100 habitants dont la durée n'est pas calculée
    com = pd.DataFrame({"depcom": ["A", "B", "C"], "typeeq_id": "D250", "pop": [100., 100, 200],
                        "pop_calcule": [100., 100, 100], "pd": [1000., 3000, 4000],
                        "sup_15": [0., 100, 100], "sup_20": [0., 100, 100], "sup_30": [0., 0, 100]})
    his = pd.DataFrame({"depcom": ["A", "B", "C"], "typeeq_id": "D250", "minute": [10, 30, 40], "pop": [100., 100, 100]})
    # médianes vectorisées, identiques à la version par groupe
    hm = pd.DataFrame({"g": ["a", "a", "a", "b"], "minute": [0, 1, 2, 5], "pop": [1., 1, 2, 3]})
    m = A.medianes_histogramme(hm, ["g"]).set_index("g")["temps_median_min"]
    assert abs(m["a"] - A.mediane_histogramme([0, 1, 2], [1, 1, 2])) < 1e-12 and abs(m["b"] - 5.5) < 1e-12, m
    ar = {"communes": com, "histogramme": his, "defs": [{"code": "D250", "id": "psy", "prof": "psychologue"}]}
    t = A.temps_acces(ar, ref).set_index(["niveau", "code"])
    fr, e1 = t.loc[("FR", "FR")], t.loc[("epci", "E1")]
    assert abs(fr["temps_moyen_min"] - 80 / 3) < 1e-9, fr
    assert abs(fr["part_population_a_plus_de_20_min"] - 2 / 3) < 1e-9
    assert abs(fr["part_population_non_calculee"] - .25) < 1e-9
    assert abs(fr["temps_median_min"] - 30.5) < 1e-9, fr["temps_median_min"]
    assert abs(e1["temps_moyen_min"] - 20) < 1e-9 and abs(e1["part_population_a_plus_de_20_min"] - .5) < 1e-9
    # médiane de l'intercommunalité E1, 100 habitants à 10 min et 100 à 30 min, la moitié est atteinte à 11 min
    assert abs(e1["temps_median_min"] - 11) < 1e-9, e1["temps_median_min"]



def test_rapport_territoire():
    import pandas as pd
    from pipeline import rapport_territoire as RT
    # intervalle exact de Garwood, valeurs de référence (R, poisson.test)
    lo, hi = RT.ic_poisson(0, 1e4)
    assert lo == 0 and abs(hi - 3.688879) < 1e-5, hi
    lo, hi = RT.ic_poisson(10, 1e4)
    assert abs(lo - 4.795389) < 1e-5 and abs(hi - 18.390356) < 1e-5, (lo, hi)
    v = list(range(1, 9))   # quartiles 2,75 / 4,5 / 6,25
    assert [RT.position(x, v) for x in (1, 4, 5, 8)] == ["quart le moins doté", "sous le milieu",
                                                         "au-dessus du milieu", "quart le mieux doté"]
    assert RT.part(.0001) == "moins de 0,1 %" and RT.part(.25) == "25,0 %"
    # le département le plus proche de 01 est 02, les départements d'outre-mer n'ont pas de semblables
    rng = np.random.default_rng(1)
    codes = ["01", "02", "03", "04", "05", "06", "07", "971"]
    x = pd.DataFrame(rng.normal(size=(8, len(RT.SEMBLABLES))), index=codes, columns=RT.SEMBLABLES)
    x["densite_pop"] = np.exp(x["densite_pop"] + 5)
    x.loc["02"] = x.loc["01"] * 1.01
    s = RT.semblables(x, k=3)
    assert s["01"][0] == "02" and "971" not in s and all("971" not in v for v in s.values()), s
    assert len(s["01"]) == 3 and "01" not in s["01"]


def test_categories_secteurs():
    import pandas as pd
    from pipeline import build
    act = pd.DataFrame({"secteur": ["Cabinet individuel", "Société de téléconsultation", "Ministère & Serv. déconcentrés",
                                    "Ministère & Serv. déconcentrés", "Organisme de Sécurité Sociale",
                                    "Services de Prévention et de Santé au Travail", "Secteur non renseigné"],
                        "prof": ["psychologue", "medecin_generaliste", "psychologue", "medecin_generaliste",
                                 "medecin_generaliste", "infirmier", "psychiatre"]})
    assert build.categories_activites(act).tolist() == ["soins", "a_distance", "public_particulier", "sans_soins", "sans_soins",
                                              "public_particulier", "soins"]

def test_moyenne_territoires():
    import pandas as pd
    from pipeline.analyses import moyenne_territoires
    e = pd.DataFrame({"code": ["A", "B", "A", "B"], "prof": ["p", "p", "p", "q"], "mode": ["all", "all", "lib", "all"],
                      "n": [3, 1, 2, 5]})
    # 4 professionnels pour 20 000 habitants, soit 2 pour 10 000, quel que soit le découpage
    assert abs(moyenne_territoires(e, "p", 20000) - 2) < 1e-12
    assert abs(moyenne_territoires(e, "p", 20000, "lib") - 1) < 1e-12
    assert moyenne_territoires(e, "absent", 20000) == 0


def test_binomiale_negative():
    # comptages simulés (mélange gamma-Poisson) de paramètres connus, alpha = 0,5 et pente 0,3
    rng = np.random.default_rng(7)
    n = 4000
    x = rng.normal(size=n)
    pop = rng.integers(2000, 50000, n).astype(float)
    mu = pop * np.exp(-8 + .3 * x)
    y = rng.poisson(rng.gamma(1 / .5, .5 * mu))
    beta, _mu, alpha, _ll = A.binomiale_negative(y.astype(float), x[:, None], np.log(pop))
    assert abs(alpha - .5) < .06, alpha
    assert abs(beta[1] - .3) < .04 and abs(beta[0] + 8) < .05, beta

def test_citation_zenodo():
    """Une version archivée est citée par Zenodo et son DOI, une version plus récente par l'adresse du site, avec le DOI
    de la dernière version archivée. Les fichiers déposés sur Zenodo forcent la citation d'une version archivée."""
    from pipeline import config, site
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "outils"))
    import zenodo
    arch = site.citation("sante", "Rapport santé", "9 octobre 2026", config.VERSION_ZENODO)["texte"]
    assert "Zenodo. https://doi.org/" in arch and config.ADRESSE_SITE not in arch
    if config.ADRESSE_SITE:
        recente = site.citation("sante", "Rapport santé", "1er janvier 2099", "2099-01-01")["texte"]
        assert "/rapports/2099-01-01/sante.html" in recente and "Dernière version archivée" in recente
        forcee = site.citation("sante", "Rapport santé", "1er janvier 2099", "2099-01-01", archivee=True)["texte"]
        assert forcee.endswith("Zenodo. https://doi.org/" + config.DOI_RAPPORTS["sante"])
    assert zenodo.concept("10.5281/zenodo.23264933") == "23264933"


def test_specialites_salariees():
    """Une spécialité dont moins d'un tiers des médecins exercent en libéral reçoit sa précision, pas les autres, ni
    les spécialités de prévention, qui ont leur propre texte."""
    import pandas as pd
    from pipeline import config, limites
    nat = pd.DataFrame({"prof": ["reanimateur"] * 2 + ["radiologue"] * 2 + ["medecin_travail"] * 2,
                        "mode": ["all", "lib"] * 3, "n": [100, 9, 100, 77, 100, 1]})
    pro = pd.DataFrame({"id": ["reanimateur", "radiologue", "medecin_travail"],
                        "libelle": ["Médecin réanimateur", "Radiologue", "Médecin du travail"],
                        "groupe": [config.G_MED, config.G_TECH, config.G_PREV]})
    r = limites.specialites_salariees(nat, pro)
    assert set(r) == {"prof:reanimateur"} and "9 %" in r["prof:reanimateur"]["texte"]


def test_consultations_non_sectorisees():
    """Une consultation de psychiatrie non sectorisée que le ROR range parmi les CMP compte parmi les consultations
    hors CMP, un CMP ordinaire reste un CMP."""
    import pandas as pd
    from pipeline import config, lieux
    noms = ["Consultation psychiatrie non sectorisée", "CMP de Créteil", "Consultations Psychiatrie Adultes",
            "Psychiatrie consultations", "Consultations psychiatrie adultes 62G05", "CMP consultations adultes"]
    n = len(noms)
    u = pd.DataFrame({"cle": list("abcdef"), "nom": noms, "categorie": ["10"] * n, "champ": [config.CHAMP_PSY] * n,
                      "mode": ["02"] * n, "age_max": [None] * n})
    t = lieux.classer_unites(u).groupby("cle")["type"].apply(set)
    assert t["a"] == {"lieu_consult_psy"} and "lieu_cmp" in t["b"] and "lieu_consult_psy" not in t["b"]
    # consultations d'hôpital ou de clinique au nom seulement générique, sans CMP ni numéro de secteur
    assert t["c"] == {"lieu_consult_psy"} and t["d"] == {"lieu_consult_psy"}
    assert "lieu_cmp" in t["e"] and "lieu_cmp" in t["f"]


def test_code_secteur():
    """Code du secteur de psychiatrie lu dans un nom, écrit sur deux chiffres, rien quand le nom n'en cite pas."""
    from pipeline.lieux import code_secteur
    assert code_secteur("CMP Ados Neuilly 93G16") == "93G16"
    assert code_secteur("CMP Adultes Brignoles - Secteur 83 G 6") == "83G06"
    assert code_secteur("CMP de Lons", "Secteur 31I01.") == "31I01"
    assert code_secteur("CMP de Lons") is None and code_secteur(None) is None


def test_exclus_cmp_noms():
    """Groupes pour les proches, entretiens familiaux et centres de diagnostic rangés parmi les CMP sont écartés, sauf
    quand leur nom dit CMP."""
    import re
    from pipeline import config
    from pipeline.lieux import _simple
    ex = re.compile(config.LIEUX_EXCLUS_CMP)
    for nom in ["Psycho Education des aidants Pontivy 56G09", "CTRE ENTRETIENS FAMILIAUX DU LITTORAL",
                "Centre de diagnostic et d'évaluation pour les troubles globaux du développement",
                "CADEO CENTRE D'ACCUEIL D'EVALUATION ET D'ORIENTATION", "CMM HOSPITALISATION",
                "Psychiatrie 2 - CATTP Ambulatoire CE CAREST EMOTION (3794)", "CE psychiatrie",
                "Consultation de psychiatrie générale et de psycho-pathologie du travail", "Relais Etudiants Lycéens"]:
        assert ex.search(_simple(nom)), nom
    for nom in ["CMP Addictologie adulte Loudéac", "CMP POUR L ENFANT ET LA FAMILLE", "CMP enfant Rostrenen 22I03",
                "CMP CATTP hospitalisation à domicile", "Pédopsychiatrie CMP consultations externes"]:
        assert not ex.search(_simple(nom)), nom


# --------------------------------------------------------------------------- registre des structures de soins
# Les tests suivants parcourent config.LIEUX_PROFIL sur les vrais résultats (dernier dossier resultats/ produit par
# run.py --hors-ligne). Un type ajouté au registre est testé sans écrire de test (16 octobre 2026).
class Ignore(Exception):
    """Test qui ne peut pas tourner faute de résultats, dit à voix haute à la fin."""


def _atlas() -> str:
    """Code de l'atlas tel qu'il part dans la page, gabarit et modules du moteur réunis (découpage du 29 octobre 2026)."""
    from atlas import construire_atlas
    return construire_atlas.source()


def _dernier_resultats():
    """Dossier de résultats le plus récent qui contient la liste des structures de soins."""
    import re
    from pipeline import config
    ds = [d for d in config.RESULTATS.glob("*") if d.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}", d.name)
          and (d / "lieux_soins.csv").exists()]
    if not ds:
        raise Ignore("aucun dossier resultats/AAAA-MM-JJ, lancer run.py --hors-ligne")
    return max(ds, key=lambda d: d.stat().st_mtime)


def _csv(dossier, nom, **kw):
    import pandas as pd
    f = dossier / nom
    if not f.exists():
        return None
    return pd.read_csv(f, sep=";", decimal=",", encoding="utf-8-sig", low_memory=False, **kw)


def test_lieux_profil_forme():
    """Le registre est bien formé (types connus, clés, analyses, champs de double éloignement) et ses analyses sont
    cohérentes : une sensibilité suppose une confirmation, une charge suppose une référence de la SAE, un public
    d'enfants ou de grand âge a son dénominateur."""
    from pipeline import config, lieux_profil as lp
    assert config.LIEUX_PROFIL
    lp.valider()
    for tid, p in config.LIEUX_PROFIL.items():
        tags = {lp.decouper(t)[0] for t in p["analyses"]}
        assert "sensibilite" not in tags or p.get("confirmation"), f"{tid} : sensibilité sans confirmation"
        assert "charge" not in tags or (p.get("reference") or {}).get("genre") == "sae", f"{tid} : charge sans SAE"
        assert p["public"] not in ("enfants", "grand_age") or p.get("denominateur"), f"{tid} : public sans dénominateur"
    for cle, (profs, types, lib) in lp.champs_double_eloignement().items():
        assert profs and types and lib, cle


def test_lieux_profil_croisements():
    """Chaque structure citée par un croisement de config.CROISEMENTS est un indicateur du registre."""
    from pipeline import config, lieux_profil as lp
    indic = set(lp.types_avec("indicateur"))
    cites = set()
    for xa, yb, _theme, _q in config.CROISEMENTS:
        for v in (xa, yb):
            for pre in ("lieux_", "dist_"):
                if v.startswith(pre + "lieu_"):
                    cites.add(v[len(pre):])
    assert cites <= indic, f"croisements sur des structures hors du registre : {sorted(cites - indic)}"


def test_lieux_profil_donnees():
    """Pour chaque type du registre, sur les résultats réels : compte non vide, couverture, niveau de confirmation,
    concordance avec la référence, indicateurs sans doublon ni libellé brut, colonnes p et q_bh des analyses
    statistiques et lignes de chaque analyse déclarée. Toutes les erreurs sont listées avec le nom du type."""
    import json
    import sys
    from pipeline import config, confirmation, lieux_profil as lp
    d = _dernier_resultats()
    ls, cou = _csv(d, "lieux_soins.csv", dtype={"dep": str}), _csv(d, "lieux_couverture.csv")
    cdep = _csv(d, "contexte_dep.csv", dtype={"code": str})
    sd = json.loads((d / "site_data.json").read_text(encoding="utf-8"))
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "outils"))
    from comparer_versions import IDENTIFIANT
    err = []
    # indicateurs de contexte du site, identifiants uniques
    ids = [x["id"] for x in sd["contexte"]]
    err += [f"indicateur en double, {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    ctx = {x["id"]: x for x in sd["contexte"]}
    niveaux_ok = set(confirmation.NIVEAUX.values())
    cles_sirene = set(config.SIRENE_ENSEIGNES) | {t[0] for t in config.LIEUX_TYPES
                                                    if t[4].get("parent") in config.SIRENE_ENSEIGNES}
    fichiers = {"sensibilite": "sensibilite_confirmation.csv", "zones": "zones_eloignement.csv",
                "double_eloignement": "double_eloignement.csv", "charge": "charge_cmp_sae.csv",
                "typologie": "typologie_lieux.csv", "escalier": "escalier_distance_lieux.csv"}
    for tid, p in config.LIEUX_PROFIL.items():
        g = ls[ls["type"] == tid]
        tags = [lp.decouper(t) for t in p["analyses"]]
        noms = {n for n, _ in tags}
        if g.empty:
            err.append(f"{tid} : aucune structure")
            continue
        # couverture
        c = cou[cou["type"] == tid]
        if (noms & lp.ANALYSES_TERRITORIALES) and (c.empty or float(c["part_departements"].iloc[0]) < config.LIEUX_COUVERTURE_MIN):
            err.append(f"{tid} : recensé dans moins de {config.LIEUX_COUVERTURE_MIN:.0%} des départements")
        # confirmation
        if p.get("confirmation"):
            if g["confirmation"].isna().any():
                err.append(f"{tid} : {int(g['confirmation'].isna().sum())} structures sans niveau de confirmation")
            if not set(g["confirmation"].dropna()) <= niveaux_ok:
                err.append(f"{tid} : niveau de confirmation inconnu {sorted(set(g['confirmation'].dropna()) - niveaux_ok)}")
            if tid not in cles_sirene:
                err.append(f"{tid} : confirmation déclarée mais absente de config.SIRENE_ENSEIGNES")
        elif tid in cles_sirene:
            err.append(f"{tid} : confirmé par config.SIRENE_ENSEIGNES, sources à déclarer dans le registre")
        # référence
        r = p.get("reference")
        if r and r["genre"] == "publiee":
            e = len(g) / r["valeur"] - 1
            if abs(e) > r["ecart_max"]:
                err.append(f"{tid} : {len(g)} structures contre {r['valeur']} publiées ({e:+.1%}, tolérance {r['ecart_max']:.0%})")
            ref = _csv(d, "lieux_references.csv")
            ligne = None if ref is None else ref[ref["type"] == tid]
            if ligne is None or ligne.empty or int(ligne["lieux"].iloc[0]) != len(g) or int(ligne["reference"].iloc[0]) != r["valeur"]:
                err.append(f"{tid} : ligne de lieux_references.csv absente ou différente")
        elif r:
            conc = _csv(d, "concordance_cmp_sae.csv")
            fr = conc[conc["niveau"] == "fr"].iloc[0]
            ici = fr[r["champ"].replace("sae_", "")]
            e = ici / fr[r["champ"]] - 1
            if int(ici) != len(g) or abs(e) > r["ecart_max"]:
                err.append(f"{tid} : {int(ici)} contre {int(fr[r['champ']])} à la SAE ({e:+.1%}, tolérance {r['ecart_max']:.0%}), "
                           f"{len(g)} dans la liste")
        # indicateurs
        if "indicateur" in noms:
            for i in (f"lieux_{tid}", f"dist_{tid}"):
                if cdep is None or i not in cdep or cdep[i].notna().sum() == 0:
                    err.append(f"{tid} : colonne {i} absente ou vide de contexte_dep.csv")
                if i not in ctx:
                    err.append(f"{tid} : indicateur {i} absent du site")
                elif IDENTIFIANT.search(ctx[i]["label"]) or not ctx[i].get("niveaux"):
                    err.append(f"{tid} : indicateur {i} au libellé brut ou sans donnée ({ctx[i]['label'][:50]})")
            es, co = _csv(d, "escalier_distance_lieux.csv"), _csv(d, "concentration_distance_lieux.csv")
            if es is None or int((es["type"] == tid).sum()) != 10:
                err.append(f"{tid} : l'escalier de distance n'a pas ses dix dixièmes de population")
            if co is None or co[co["type"] == tid].empty:
                err.append(f"{tid} : indice de concentration de la distance absent")
            cols, _lib = lp.denominateur(tid)
            err += [f"{tid} : dénominateur {c_} absent de contexte_dep.csv" for c_ in cols if cdep is None or c_ not in cdep]
        # analyses
        for nom, param in tags:
            if nom == "eloignement":
                premier = lp.types_avec("eloignement", param)[0] == tid
                svg = d / "graphiques" / (f"eloignement_{param}" if premier else f"eloignement_{param}__{tid}") 
                if not svg.with_suffix(".svg").exists():
                    err.append(f"{tid} : figure {svg.name}.svg absente")
            f = fichiers.get(nom)
            if not f:
                continue
            t = _csv(d, f)
            if t is None:
                err.append(f"{tid} : fichier {f} absent")
                continue
            if nom == "double_eloignement":
                n = int(((t["champ"] == param) & (t["niveau"] == "fr")).sum())
            elif nom == "charge":
                n = int(((t["niveau"] == "fr") & (t["public"] == p["public"])).sum())
            elif nom == "typologie":
                n = int(((t["type"] == tid) & (t["famille"] == param)).sum())
            else:
                n = int((t["type_structure" if nom == "zones" else "type"] == tid).sum())
            if n == 0:
                err.append(f"{tid} : aucune ligne pour {nom}{':' + param if param else ''} dans {f}")
            if nom in lp.ANALYSES_STATISTIQUES:
                if not {"p", "q_bh"} <= set(t.columns):
                    err.append(f"{f} : colonnes p et q_bh attendues")
                else:
                    s = t[t["type_structure"] == tid].dropna(subset=["p", "q_bh"])
                    if ((s["p"] < 0) | (s["p"] > 1) | (s["q_bh"] < s["p"] - 1e-9) | (s["q_bh"] > 1 + 1e-9)).any():
                        err.append(f"{tid} : p ou q_bh hors de leurs bornes dans {f}")
    assert not err, "\n".join(err)


def test_publics_et_cattp_meme_lieu():
    """Public de chaque CMP montré dans l'atlas, mêmes comptes que lieux.repartition_cmp, et CATTP à l'adresse d'un CMP
    (même adresse et même commune), sur les structures en cache."""
    import pandas as pd
    from pipeline import config, export, lieux
    p = config.RACINE / "donnees" / "intermediaire" / "structures_avant_verification.parquet"
    if not p.exists():
        return
    x = pd.read_parquet(p)
    pub, ant = export._publics_cmp(x)
    r = lieux.repartition_cmp(x, "fr").iloc[0]
    v = pd.Series(pub).value_counts()
    assert len(pub) == r["cmp"] and v.get("d", 0) == r["les_deux"] and v.get("n", 0) == r["non_precise"]
    assert v.get("a", 0) + v.get("d", 0) == r["adultes"] and v.get("e", 0) + v.get("d", 0) == r["enfants"]
    assert len(ant) == r["antennes"]
    m = export._cattp_meme_lieu_cmp(x)
    ca = x[x["type"] == "lieu_cattp"]
    assert 0 < len(m) < len(ca) and m <= set(ca.index)
    cle = lambda i: norm(x.at[i, "adresse"]) + "|" + str(x.at[i, "commune"])  # noqa: E731
    adr_cmp = {cle(i) for i in x.index[(x["type"] == "lieu_cmp") & x["adresse"].fillna("").str.strip().ne("")]}
    assert all(cle(i) in adr_cmp for i in m)
    assert not any(not str(x.at[i, "adresse"] or "").strip() for i in m)



def test_retyper_cattp():
    """Un atelier thérapeutique (catégorie FINESS 366 ou nom) va avec la réhabilitation psychosociale, sauf si son nom
    dit aussi CATTP. Un CATTP en milieu pénitentiaire va avec les consultations hors CMP."""
    import pandas as pd
    from pipeline.lieux import retyper_cattp
    L = pd.DataFrame({"type": ["lieu_cattp"] * 4 + ["lieu_cmp"],
                      "nom_affiche": ["Atelier théâtre", "CATTP adulte Atelier thérapeutique Quimper", "CATTP Maison d'arrêt",
                                      "Les Tilleuls", "Atelier"],
                      "categorie_finess": [None, None, None, "366", None], "confirmation": ["bases"] * 5})
    x, na, npn = retyper_cattp(L)
    assert x["type"].tolist() == ["lieu_rehab_psy", "lieu_cattp", "lieu_consult_psy", "lieu_rehab_psy", "lieu_cmp"]
    assert (na, npn) == (2, 1)


def test_roles_antennes():
    """CMPP principal, antenne (non porteuse d'un CMPP dans FINESS) et site supplémentaire (ROR seul au numéro d'une
    autre ligne). L'antenne et le site non confirmés héritent de leur principal confirmé, pas d'un principal non confirmé."""
    import pandas as pd
    from pipeline.lieux import roles_antennes
    fin = pd.DataFrame({"nofinesset": ["P", "A", "Q", "B"], "categetab": ["189"] * 4,
                        "finess_porteuse": [None, "P", None, "Q"]})
    L = pd.DataFrame({"type": ["lieu_cmpp"] * 5, "finess": ["P", "A", "P", "Q", "B"], "finess_rapproche": [None] * 5,
                      "provenance": ["les_deux", "finess", "ror", "les_deux", "finess"],
                      "confirmation": ["has", "bases", "bases", "bases", "bases"]})
    x, r = roles_antennes(L, fin)
    assert x["role_structure"].tolist() == ["structure", "antenne", "site", "structure", "antenne"]
    assert x["confirmation"].tolist() == ["has", "principal", "principal", "bases", "bases"]
    assert r["lieu_cmpp"]["herite"] == 2


def test_roles_addictologie():
    """Rôles lus dans le nom (CJC, antenne, hébergement, milieu pénitentiaire, équipe de liaison), et trois comptes des
    CSAPA, lieux, établissements FINESS de catégorie CSAPA, établissements sans ligne d'antenne ni de CJC."""
    import pandas as pd
    from pipeline.lieux import comptes_csapa, roles_addictologie
    L = pd.DataFrame({"type": ["lieu_csapa"] * 5 + ["lieu_addicto_hosp"],
                      "nom_affiche": ["CSAPA Le Fil", "CJC du Fil", "Antenne CSAPA Nord", "Appartements thérapeutiques",
                                      "CSAPA maison d'arrêt", "ELSA CH Nord"],
                      "finess": ["1", "1", "2", "3", "4", None], "finess_rapproche": [None] * 6,
                      "categorie_finess": ["197", "197", "197", "197", "197", None]})
    x = roles_addictologie(L)
    assert x["role_structure"].tolist() == ["structure", "cjc", "antenne", "hebergement", "penitentiaire", "equipe"]
    c = comptes_csapa(x)
    assert c == {"lieux": 5, "etablissements": 4, "principaux": 3}


def test_classes_confirmation():
    """Trois classes montrées au lecteur, qui refont le nombre de structures au niveau établi."""
    import pandas as pd
    from pipeline.confirmation import NIVEAUX, classe, compter_classes
    assert {classe(k) for k in NIVEAUX} == {"confirmee", "recoupee", "a_verifier"}
    assert classe("bases") == "a_verifier" and classe("sae") == "recoupee" and classe("principal") == "confirmee"
    assert classe(None) is None
    c = compter_classes(pd.Series(["has", "sae", "bases", "etablissement", None]))
    assert c == {"confirmee": 2, "recoupee": 1, "a_verifier": 1}


def test_exercice_structures():
    """Personnes distinctes déclarées dans une structure à numéro FINESS propre, par type et au total, sans compter une
    unité hospitalière qui partage le numéro de son hôpital."""
    import pandas as pd
    from pipeline.lieux import exercice_structures
    L = pd.DataFrame({"type": ["lieu_cmp", "lieu_cattp", "lieu_cmp"], "finess": ["1", "2", "9"],
                      "commune": ["A", "A", "B"], "dep": ["01"] * 3, "reg": ["84"] * 3,
                      "categorie_finess": ["156", "425", "106"]})
    act = pd.DataFrame({"id": ["p1", "p1", "p2", "p3"], "prof": ["psychiatre", "psychiatre", "psychologue", "psychiatre"],
                        "finess": ["1", "2", "1", "9"], "com": ["A", "A", "A", "B"]})
    t = exercice_structures(L, act)
    fr = t[t["niveau"] == "fr"].set_index(["type", "prof"])["personnes"]
    assert fr[("lieu_cmp", "psychiatre")] == 1 and fr[("lieu_cattp", "psychiatre")] == 1
    assert fr[("ensemble", "psychiatre")] == 1 and fr[("ensemble", "psychologue")] == 1


def test_addicto_odisse():
    """Les indicateurs de la partie « Addictologie » sont déclarés dans Odissé, régionaux, avec leur intervalle et le
    groupe Addictions, et la limite qui les accompagne existe."""
    from pipeline import config
    od = {i["id"]: i for i in config.ODISSE}
    for i in config.ADDICTO_ODISSE:
        assert i in od and od[i]["niveau"] == "reg" and od[i].get("ic_bas") and od[i].get("groupe") == "Addictions"
    assert "addictions" in config.LIMITES


def test_css_libelle_valeur_ecart():
    """Une ligne qui met un libellé et sa valeur face à face (grille « 1fr auto » ou flex « space-between ») a toujours
    un écart, sinon un libellé qui passe à la ligne vient toucher le nombre (remarque de Lucas du 22 octobre 2026)."""
    import re
    from pipeline import config
    for f in (config.RACINE / "gabarits" / "style.css", config.RACINE / "atlas" / "atlas_template.html"):
        css = f.read_text(encoding="utf-8")
        for regle in re.findall(r"[^{}]*\{[^{}]*\}", css):
            if re.search(r"grid-template-columns:[^;}]*auto|justify-content:space-between", regle):
                assert re.search(r"(^|[;{])\s*(column-)?gap:", regle), (f.name, regle.strip()[:120])


def test_fiche_territoire():
    """Fiche d'un territoire de l'atlas (remarques de Lucas du 28 octobre 2026) : une fenêtre comme les autres encadrés,
    une légende en couleur et non un paragraphe, des groupes en colonnes équilibrées et non une colonne courte à côté
    d'une longue, aucun indice 0 laissé seul pour une profession absente, aucune mention encadrée, pas de titre
    « Profil de la population » répété sous le titre du même nom."""
    import re
    from pipeline import config
    t = _atlas()
    corps = t[t.index("function selCard(){"):t.index("function hbars(")]
    assert "legende-barres" not in t and "selcols" not in t
    assert 'class="fiche-legende"' in corps and 'class="fiche-colonnes"' in corps
    assert re.search(r"\.fiche-colonnes\{[^}]*columns:", t)
    assert re.search(r"\.grid\.carte>\.selzone\{[^}]*border:6px solid var\(--fen\)", t)
    assert "if(nP===0)" in corps and "aucun déclaré" in corps
    assert 'class="tag"' not in corps
    assert 'g==="Profil de la population"?\'\'' in corps
    # tête en barre de fenêtre, repli par le symbole des fenêtres d'Explorer, plus de bouton encadré (28 octobre 2026)
    assert 'class="pastilles"><button id="selReplier"' in corps and "btn ghost" not in corps
    assert "Masquer le détail" not in t


def test_ecart_attendu_sans_manque_ni_norme():
    """L'écart à l'effectif attendu est décrit, jamais présenté comme un manque, et un écart à la moyenne n'est pas un
    écart à une norme (remarque de Lucas du 28 octobre 2026) : contrôlé dans l'atlas, Explorer et le code des rapports,
    et par le vocabulaire à éviter de pipeline.libelles pour tout texte publié."""
    import re
    from pipeline import config, libelles
    fichiers = [config.RACINE / "atlas" / "atlas_template.html", *(config.RACINE / "atlas" / "moteur").glob("*.js"),
                *(config.RACINE / "gabarits").glob("*.js"),
                *(config.RACINE / "pipeline").glob("rapport*.py"), config.RACINE / "pipeline" / "graphiques.py"]
    for f in fichiers:
        t = f.read_text(encoding="utf-8")
        assert not re.search(r"il en manque|(dans|hors de) la norme", t), f.name
    assert libelles.termes_proscrits("il en manque environ 5") and libelles.termes_proscrits("ce territoire est dans la norme")
    assert not libelles.termes_proscrits("l'effectif attendu est d'environ 50, on en compte environ 5 de moins")
    # règle 13, pas de « mauvais élève »
    assert libelles.termes_proscrits("un territoire mal doté") and libelles.termes_proscrits("des intercommunalités mal dotées")
    assert not libelles.termes_proscrits("un territoire peu doté, moins doté que ses voisins")
    # les versions déjà publiées des rapports restent telles quelles, seul le langage de la dernière est contrôlé
    site = (config.RACINE / "pipeline" / "site.py").read_text(encoding="utf-8")
    assert "if d == dernier:\n                pages.append(dossier / f\"{cle}.html\")" in site.replace("\r\n", "\n")


def test_carte_corse_et_plan_des_structures():
    """Carte nationale et encadré des structures (remarques de Lucas du 28 octobre 2026) : la Corse est rapprochée du
    continent par un même décalage pour ses contours et ses structures, le cadrage en tient compte, le lecteur en est
    averti ; les commandes de la carte sont dans sa barre de titre, en mots et en symboles au trait, chacune avec son nom
    accessible ; l'encadré des structures donne le résultat d'abord (phrase et légende en couleur), puis le plan sur
    toute la largeur, puis la liste par type en trois colonnes, jamais coupée."""
    import re
    from pipeline import config
    from pipeline.lecture import GLOSSAIRE
    t = _atlas()
    d = float(re.search(r"DLON_CORSE=([\d.]+)", t).group(1))
    assert 0 < d < 2
    assert "estCorse(lv,f)?P.corse:P.metro" in t and "metro([ll[0]-DLON_CORSE,ll[1]])" in t
    assert "CORSE.includes(f.properties.dep)?{...f,geometry:decaler(f.geometry)}" in t
    assert "zones,epci,corse" in t and any(g[0] == "corse" for g in GLOSSAIRE)
    assert ".lx-corps{display:grid;grid-template-columns:minmax(0,1fr);" in t
    assert "position:sticky;top:200px" not in t
    # commandes de la carte dans la barre de titre, plus posées sur la carte
    outils = t[t.index('<div id="mapOutils"'):t.index('<div id="mapLimite"')]
    assert 'class="map-commandes"' in outils and 'data-k="vue"' in outils and 'data-carte="map"' in outils
    assert "Tuiles</button>" not in t and "À taille égale</button>" in outils
    zoom = outils[outils.index('class="zoombar"'):]
    assert zoom.count("aria-label=") >= 4 and "Recentrer" not in zoom
    assert "#mapOutils .zoombar svg" in t
    # encadré des structures, le résultat, puis le plan, puis la liste par type en trois colonnes
    corps = t[t.index("function structuresTerritoire(){"):t.index("// ---------- carte du territoire choisi")]
    assert corps.index('class="lx-legende lx-resultat"') < corps.index("carteTerritoireHtml(lignesPlan)") < corps.index('class="lx-table"')
    assert '<th scope="col">Niveau de confirmation</th>' in corps and 'colspan="5"' not in corps and 'colspan="4"' not in corps
    assert "Un clic sur une structure la repère" not in corps


def _js_noms(code: str) -> tuple[set, set]:
    """Noms déclarés au premier niveau d'un module du moteur, et noms qu'il emploie (commentaires, chaînes, expressions
    régulières et propriétés retirés, variables locales aussi). Approximation suffisante pour contrôler les dépendances."""
    import re
    sortie, i, n, prec = [], 0, len(code), ""
    while i < n:
        c = code[i]
        if code.startswith("//", i):
            j = code.find("\n", i)
            i = n if j < 0 else j
        elif code.startswith("/*", i):
            i = code.find("*/", i + 2) + 2
        elif c in "'\"":
            j = i + 1
            while j < n and code[j] != c:
                j += 2 if code[j] == "\\" else 1
            sortie.append('""')
            i, prec = j + 1, '"'
        elif c == "/" and (prec == "" or prec in "(,=:[!&|?{};+-*%<>~^" or prec in ("return", "typeof")):
            j, classe = i + 1, False
            while j < n and code[j] != "\n" and (code[j] != "/" or classe):
                classe = (code[j] == "[") or (classe and code[j] != "]")
                j += 2 if code[j] == "\\" else 1
            j += 1
            while j < n and code[j].isalpha():
                j += 1
            sortie.append("0")
            i, prec = j, "0"
        else:
            m = re.compile(r"[A-Za-z_$][\w$]*").match(code, i)
            if m and (i == 0 or not (code[i - 1].isalnum() or code[i - 1] in "_$")):
                sortie.append(m.group(0))
                i, prec = m.end(), m.group(0) if m.group(0) in ("return", "typeof") else "a"
                continue
            sortie.append(c)
            prec = c if not c.isspace() else prec
            i += 1
    t = "".join(sortie)
    haut = set()
    for ligne in t.split("\n"):
        m = re.match(r"(?:async function|function|const|let|var)\s+([A-Za-z_$][\w$]*)", ligne)
        if m:
            haut.add(m.group(1))
            if not ligne.startswith(("function", "async")):   # autres noms de la même déclaration, hors parenthèses
                profondeur, debut = 0, m.end()
                for k, ch in enumerate(ligne[debut:], debut):
                    profondeur += (ch in "([{") - (ch in ")]}")
                    if profondeur == 0 and ch == ";":
                        break
                    if profondeur == 0 and ch == ",":
                        suite = re.match(r",\s*([A-Za-z_$][\w$]*)\s*=(?!=)", ligne[k:])
                        if suite:
                            haut.add(suite.group(1))
        haut |= set(re.findall(r";\s*function\s+([A-Za-z_$][\w$]*)", ligne))
    locaux = set(re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)", t)) | set(re.findall(r",\s*([A-Za-z_$][\w$]*)\s*=(?!=)", t))
    employes = set(re.findall(r"(?<![\w$.])(?<!\?\.)([A-Za-z_$][\w$]*)", t))
    return haut, employes - (locaux - haut)


def test_moteur_atlas_modules():
    """Moteur de l'atlas en modules (découpage du 29 octobre 2026) : chaque nom est déclaré dans un seul module, le noyau
    ne s'appuie sur aucun autre, la carte sur le noyau seulement, les croisements et le nuage sur le noyau et la carte,
    plus ce que la page qui les charge fournit (render, syncBar, ouvrirNuage). Le nuage, « Croiser deux indicateurs »,
    n'est chargé que par Explorer avec son adaptateur. Le gabarit ne contient plus de code du moteur."""
    from atlas import construire_atlas as ca
    tous = list(dict.fromkeys(ca.MODULES + ca.MODULES_EXPLORER))
    permis = {"noyau": (), "carte": ("noyau",), "croisements": ("noyau", "carte"), "nuage": ("noyau", "carte"),
              "structures": tous, "atlas": tous}
    fournis = {"croisements": {"render", "syncBar", "ouvrirNuage"}, "nuage": {"render", "syncBar"}}
    noms = {m: _js_noms((ca.ICI / "moteur" / f"{m}.js").read_text(encoding="utf-8")) for m in tous}
    vus = {}
    for m, (haut, _) in noms.items():
        for x in haut:
            assert x not in vus, f"{x} déclaré dans {vus[x]} et dans {m}"
            vus[x] = m
    for m, (haut, employes) in noms.items():
        hors = {x for x in employes if x in vus and vus[x] != m and vus[x] not in permis[m]}
        hors -= fournis.get(m, set())
        assert not hors, f"le module {m} emploie {sorted(hors)}"
    # la page de l'atlas fournit tout ce que ses modules attendent, l'adaptateur d'Explorer ce qu'attend le nuage, et
    # le nuage ne vit qu'à un seul endroit (lot 2 du 29 octobre 2026)
    assert fournis["croisements"] <= noms["atlas"][0]
    adaptateur = _js_noms((ca.ICI.parent / "gabarits" / "explorer_croisements.js").read_text(encoding="utf-8"))[0]
    assert fournis["nuage"] <= adaptateur
    assert "nuage" not in ca.MODULES and "nuage" in ca.MODULES_EXPLORER
    gabarit = (ca.ICI / "atlas_template.html").read_text(encoding="utf-8")
    assert "(function(){\n/*MOTEUR*/\n})();" in gabarit.replace("\r\n", "\n") and "function render(" not in gabarit
    assert ca.source().count("function render(") == 1
    assert 'id="scatter"' not in ca.source() and 'id="lienNuage"' in ca.source()
    page = (ca.ICI.parent / "gabarits" / "explorer.html").read_text(encoding="utf-8")
    assert 'id="scatter"' in page and "data-moteur" in page


def test_meme_largeur_atlas_explorer():
    """L'atlas (première page) et les autres pages du site, Explorer compris, ont la même largeur de contenu
    (décision du 22 octobre 2026, remarque de Lucas du 28 octobre 2026 sur l'atlas plus large qu'Explorer)."""
    import re
    from pipeline import config
    css = (config.RACINE / "gabarits" / "style.css").read_text(encoding="utf-8")
    t = _atlas()
    site = int(re.search(r"(?m)^main\{max-width:(\d+)px", css).group(1))
    assert re.search(r"\.wrap\{max-width:var\(--largeur-contenu,%dpx\)" % site, t)
    assert set(int(x) for x in re.findall(r"--largeur-contenu[:,](\d+)px", t)) == {site}
    explorer = (config.RACINE / "gabarits" / "explorer.html").read_text(encoding="utf-8")
    assert not re.search(r"main\{[^}]*max-width:(?!%dpx)\d+px" % site, explorer)


def test_plan_ign_structures():
    """Plan IGN sous les structures d'un territoire (28 octobre 2026) : Leaflet intégré à la page avec l'empreinte
    contrôlée et sa licence, fond de la Géoplateforme avec sa mention, plan SVG gardé pour l'export, molette réservée
    au défilement, et la page À propos dit que ce fond est chargé chez l'IGN."""
    from pipeline import config
    from atlas import construire_atlas as ca
    js = ca._leaflet("leaflet.js")
    assert "BSD 2-Clause License" in js and "Leaflet 1.9.4" in js
    assert "BSD 2-Clause License" in ca._leaflet("leaflet.css")
    t = _atlas()
    assert "<script>/*LEAFLET*/</script>" in t and "<style>/*LEAFLET_CSS*/</style>" in t
    assert "https://data.geopf.fr/wmts?" in t and "LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2" in t
    # mention demandée par l'IGN (réponse du 29 octobre 2026), Plan IGN vérifié dans le registre des licences
    assert "© IGN – <a" in t and "TODO mention exacte du Plan IGN" not in t
    from pipeline import licences
    assert licences.identifiant("Plan IGN") == "ign-lo-2.0" and licences.LICENCES["ign-lo-2.0"]["statut"] == "vérifié"
    assert "scrollWheelZoom:false" in t and 'svg id="lxCarte"' in t
    assert "Géoplateforme de l'IGN" in (config.RACINE / "contenus" / "a_propos.md").read_text(encoding="utf-8")


def test_sans_caractere_de_controle():
    """Aucun caractère de contrôle dans le code et les textes des pages (un remplacement raté du 28 octobre 2026 avait mis
    un caractère invisible à la place d'un chiffre, « 10 % » devenu « 1 % » à l'affichage)."""
    import re
    from pipeline import config
    fichiers = [*(config.RACINE / "gabarits").glob("*.*"), config.RACINE / "atlas" / "atlas_template.html",
                *(config.RACINE / "atlas" / "moteur").glob("*.js"), *(config.RACINE / "contenus").glob("*.md")]
    for f in fichiers:
        if f.suffix in (".html", ".js", ".css", ".md"):
            t = f.read_text(encoding="utf-8")
            m = re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", t)
            assert not m, (f.name, repr(t[max(0, m.start() - 30):m.start() + 10]))


def test_fond_des_cellules():
    """Dans un tableau, toutes les cellules ont le fond de la fenêtre qui le contient, colonnes figées comprises, seul
    le survol d'une ligne peut l'éclaircir (défaut signalé par Lucas le 28 octobre 2026, première colonne plus claire
    dans le tableau d'accès aux structures de l'atlas). Une cellule figée prend donc le fond de son conteneur
    (--fond-cellule), et aucune règle à l'écran ne colore une ligne sur deux."""
    import re
    from pipeline import config
    for f in (config.RACINE / "gabarits" / "style.css", config.RACINE / "atlas" / "atlas_template.html"):
        css = f.read_text(encoding="utf-8")
        for sel, corps in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            if re.search(r"\b(td|th)\b", sel) and "position:sticky" in corps and "left:0" in corps:
                fond = re.search(r"background:([^;}]+)", corps)
                assert fond and "--fond-cellule" in fond.group(1), (f.name, sel.strip()[:80])
            if "nth-child(even)" in sel and re.search(r"\b(td|tr)\b", sel):
                assert re.search(r"background:\s*none", corps), (f.name, sel.strip()[:80], "ligne sur deux colorée")


def test_classe_barre_resserree_sans_conflit():
    """La classe que prend la barre du site quand on descend n'a aucune règle à elle seule hors de nav.site, sinon la
    barre hérite d'un réglage d'autres éléments (overflow-x:auto de .defile cachait la liste « Le projet », remarque de
    Lucas du 28 octobre 2026)."""
    import re
    from pipeline import config
    js = (config.RACINE / "gabarits" / "figures.js").read_text(encoding="utf-8")
    m = re.search(r'n\.classList\.toggle\("([\w-]+)",\(window\.scrollY', js)
    assert m, "classe de la barre resserrée introuvable dans figures.js"
    classe = m.group(1)
    for f in (config.RACINE / "gabarits" / "style.css", config.RACINE / "atlas" / "atlas_template.html"):
        css = f.read_text(encoding="utf-8")
        for selecteurs in re.findall(r"([^{}]+)\{[^{}]*\}", css):
            for s in selecteurs.split(","):
                if re.search(rf"\.{classe}(?![\w-])", s):
                    assert re.search(rf"nav\.site\.{classe}(?![\w-])", s), (f.name, s.strip()[:120])


def test_typo_commune():
    """Les figures des rapports et de l'atlas suivent la même échelle typographique (harmonisation du 22 octobre 2026),
    jamais moins de 11,5 pixels à l'écran, et une taille convertie selon la largeur de la figure."""
    import re
    from pipeline import config, graphiques
    atlas = _atlas()
    m = re.search(r"const TYPO=\{titre:([\d.]+),texte:([\d.]+),petit:([\d.]+)\}", atlas)
    assert m and tuple(map(float, m.groups())) == (graphiques.TYPO["titre"], graphiques.TYPO["texte"],
                                                     graphiques.TYPO["petit"])
    assert min(graphiques.TYPO.values()) >= 11.5
    assert graphiques.taille_role("texte", graphiques.LARGEUR_ECRAN) == graphiques.TYPO["texte"]
    assert graphiques.taille_role("petit", 2 * graphiques.LARGEUR_ECRAN) == 2 * graphiques.TYPO["petit"]


def test_odisse_codes_et_decimales():
    """Le tableau publié des indicateurs de Santé publique France ne garde que de vrais territoires (pas les lignes
    d'ensemble, codes 10 et 99) et écrit ses fourchettes avec la virgule décimale comme les autres colonnes."""
    import re
    from pipeline.sources import referentiel
    d = _dernier_resultats()
    f = d / "sante_mentale_sante_publique_france.csv"
    if not f.exists():
        raise Ignore("pas de tableau Santé publique France")
    assert not re.search(r"\d\.\d", f.read_text(encoding="utf-8-sig")), "point décimal dans le CSV publié"
    t = _csv(d, "sante_mentale_sante_publique_france.csv", dtype={"code": str})
    ref = referentiel.charger(True, False)
    for niv, codes in (("reg", set(ref.regs["code"])), ("dep", set(ref.deps["code"]))):
        hors = set(t.loc[t["niveau"] == niv, "code"]) - codes
        assert not hors, (niv, hors)

def test_combinaisons_par_territoire():
    """Classe de combinaison d'une intercommunalité (carte des combinaisons, 23 octobre 2026). La règle couvre chaque
    cas de présence, et les classes recalculées à partir des effectifs publiés par intercommunalité redonnent les
    comptes de combinaisons.csv."""
    from pipeline.analyses import classe_combinaison
    assert classe_combinaison(True, True, True) == "trois"
    assert classe_combinaison(True, True, False) == "sans_psychiatre"
    assert classe_combinaison(True, False, False) == "generaliste_seul"
    assert classe_combinaison(True, False, True) == "sans_psychologue"
    assert classe_combinaison(False, True, True) == "autre"
    d = _dernier_resultats()
    e, cb = _csv(d, "effectifs_epci_all.csv", dtype={"code": str}), _csv(d, "combinaisons.csv")
    if e is None or cb is None:
        raise Ignore("effectifs ou combinaisons absents")
    cl = [classe_combinaison(g > 0, ps > 0, pt > 0) for g, ps, pt in
          zip(e["n_medecin_generaliste"], e["n_psychologue"], e["n_psychiatre"])]
    x = cb[cb["niveau"] == "epci"]
    attendu = {("trois", True, True, True), ("sans_psychiatre", True, True, False),
               ("generaliste_seul", True, False, False), ("sans_psychologue", True, False, True)}
    for k, g, ps, pt in attendu:
        n = x[(x["medecin_generaliste"] == g) & (x["psychologue"] == ps) & (x["psychiatre"] == pt)]["territoires"].sum()
        assert cl.count(k) == n, (k, cl.count(k), n)


def test_part_liberal():
    """Part de l'exercice libéral (indicateur de « Croiser deux indicateurs », 23 octobre 2026), sur les effectifs
    publiés par département. Aucune part sous l'effectif minimal, une part toujours entre 0 et 1 (un libéral est
    compté une fois parmi tous les professionnels), et des professions retenues qui respectent les deux critères."""
    import numpy as np
    from pipeline import config
    from pipeline.analyses import part_liberal, professions_part_liberal
    d = _dernier_resultats()
    a, l = _csv(d, "effectifs_dep_all.csv", dtype={"code": str}), _csv(d, "effectifs_dep_lib.csv", dtype={"code": str})
    fr = _csv(d, "effectifs_france.csv")
    if a is None or l is None or fr is None:
        raise Ignore("effectifs absents")
    l = l.set_index("code").reindex(a["code"]).fillna(0)
    for p in ("psychologue", "psychiatre", "medecin_generaliste", "infirmier"):
        v = part_liberal(l[f"n_{p}"].to_numpy(), a[f"n_{p}"].to_numpy())
        petit = a[f"n_{p}"].to_numpy() < config.PART_LIBERAL_EFFECTIF_MIN
        assert np.isnan(v[petit]).all() and not np.isnan(v[~petit]).any(), p
        assert ((v[~petit] >= 0) & (v[~petit] <= 1)).all(), p
    assert np.isnan(part_liberal([3], [9])[0]) and part_liberal([5], [10])[0] == .5
    nat = fr.pivot_table(index="prof", columns="mode", values="n", aggfunc="sum", fill_value=0)
    n_dep = a.set_index("code")[[c for c in a.columns if c.startswith("n_")]].rename(columns=lambda c: c[2:])
    retenues = professions_part_liberal(nat, n_dep)
    assert "psychologue" in retenues and "medecin_generaliste" in retenues, retenues
    bas, haut = config.PART_LIBERAL_BORNES
    for p in retenues:
        assert bas <= nat.at[p, "lib"] / nat.at[p, "all"] <= haut, p
        assert (n_dep[p] >= config.PART_LIBERAL_EFFECTIF_MIN).mean() >= config.PART_LIBERAL_PRESENCE_MIN, p


def test_photographies():
    """Photographie des comptes à chaque extraction du RPPS (26 octobre 2026). La dernière photographie redonne, par
    profession, les effectifs publiés par intercommunalité et par département, sans ligne à zéro ni nom de personne."""
    import json
    import pandas as pd
    from pipeline import photographies
    idx = photographies.DOSSIER / "index.json"
    if not idx.exists():
        raise Ignore("aucune photographie, lancer run.py --hors-ligne")
    dern = json.loads(idx.read_text(encoding="utf-8"))[-1]
    ph = pd.read_csv(photographies.DOSSIER / dern["fichier"], sep=";", dtype={"code": str})
    assert list(ph.columns) == ["niveau", "code", "prof", "mode", "n"] and (ph["n"] > 0).all()
    assert set(ph["niveau"]) == set(photographies.NIVEAUX)
    d = _dernier_resultats()
    for niv in ("epci", "dep"):
        e = _csv(d, f"effectifs_{niv}_all.csv", dtype={"code": str})
        if e is None:
            raise Ignore(f"effectifs_{niv}_all.csv absent")
        x = ph[(ph["niveau"] == niv) & (ph["mode"] == "all")].groupby("prof")["n"].sum()
        for p in ("psychologue", "psychiatre", "medecin_generaliste"):
            assert int(x.get(p, 0)) == int(e[f"n_{p}"].sum()), (niv, p)


def test_age_professionnels():
    """Part des 60 ans et plus d'après les classeurs de la DREES en cache (28 octobre 2026). Les tranches d'âge
    additionnées redonnent l'effectif publié, les séries d'Adeli (actifs de moins de 62 ans) sont écartées, seuls de
    vrais codes de département sont gardés, et la borne de chaque tranche est lue correctement."""
    from pipeline import config
    from pipeline.sources import drees_demographie as dd
    assert dd._borne("08-entre 60 et 64 ans") == 60 and dd._borne("10- 65 ans et plus") == 65
    assert dd._borne("01-moins de 30 ans") == 0 and dd._borne("00-Ensemble") is None
    assert dd._borne("09 - Entre 60 et 64 ans") == 60
    prof = _csv(_dernier_resultats(), "professions.csv")
    if prof is None or not dd._fichier(r"^medecins rpps").exists():
        raise Ignore("classeurs de la DREES absents du cache")
    r = dd.ages(dict(zip(prof["id"], prof["famille"])))
    assert r and len(r["defs"]) >= 15
    t = r["table"]
    fr = t[t["niveau"] == "france"]
    assert ((fr["somme_tranches"] - fr["effectif"]).abs() <= fr["effectif"] * .005).all()
    assert t["part_60"].between(0, 1).all()
    assert t.loc[t["niveau"] == "dep", "code"].str.fullmatch(r"\d{2}|2A|2B|97\d").all()
    adeli = {p for x in config.DREES_DEMOGRAPHIE if x[5] == config._ADELI for p in x[3]}
    assert not any(d["id"] == f"age60_{p}" for d in r["defs"] for p in adeli), "série d'Adeli gardée"
    assert all(d["famille"] in (config.SANTE_MENTALE, config.SANTE) for d in r["defs"])
    assert next(d for d in r["defs"] if d["id"] == "age60_psychiatre")["famille"] == config.SANTE_MENTALE


def test_taux_depassement():
    """Taux de dépassement des libéraux de secteur 2 (montants des honoraires de l'Assurance Maladie, 28 octobre
    2026). Repris tel que publié, sauf sous secret statistique (« NS », le jeu écrit alors 0) et dans un territoire sans
    libéral de secteur 2, où il reste une valeur manquante, jamais un faux 0."""
    import pandas as pd
    from pipeline import config
    from pipeline.sources import ameli_acces
    if not (config.BRUT / "ameli_honoraires.csv").exists() or not (config.BRUT / "ameli_secteurs_conventionnels.csv").exists():
        raise Ignore("jeux de l'Assurance Maladie absents du cache")
    brut = pd.read_csv(config.BRUT / "ameli_honoraires.csv", sep=";", dtype=str)
    r = ameli_acces.charger(None, hors_ligne=True)
    h, s = r["honoraires"], r["secteurs"]
    assert h is not None and len(h) and {f"taux_depassement_{i}" for _p, i, _l, _f in config.AMELI_SECTEURS_PROFESSIONS} <= {d["id"] for d in r["defs"]}
    ns = brut["depassements_totaux"].fillna("").str.strip().isin(["NS", ""])
    assert ns.any(), "aucun montant sous secret dans le jeu, le test ne vérifie plus rien"
    assert h.loc[h["depassements_totaux"].isna(), "taux_depassement_s2"].isna().all()
    s2 = s.set_index(["niveau", "code", "prof"])["secteur_2"]
    sans = s2.reindex(pd.MultiIndex.from_frame(h[["niveau", "code", "prof"]])).to_numpy() == 0
    assert h.loc[sans, "taux_depassement_s2"].isna().all()
    fr = h[(h["niveau"] == "FR") & (h["prof"] == "psychiatre")]["taux_depassement_s2"]
    publie = brut[(brut["departement"] == "999") & (brut["region"] == "99") & (brut["profession_sante"] == "Psychiatres")]
    assert len(fr) == 1 and abs(fr.iloc[0] - float(publie["taux_depassement_s2"].iloc[0])) < 1e-9


def test_explorer():
    """Page « Explorer » (26 octobre 2026). Ses données redonnent les comptes publiés, la part des habitants avec un
    psychologue mais aucun psychiatre déclaré est celle de combinaisons.csv, et les trajectoires couvrent les séries de
    la DREES sans Mayotte."""
    from pipeline import explorer
    d = _dernier_resultats()
    paires, traj, cb = explorer.donnees_paires(d), explorer.donnees_trajectoires(d), _csv(d, "combinaisons.csv")
    if not paires or not traj or cb is None:
        raise Ignore("résultats incomplets")
    x = cb[(cb["niveau"] == "epci") & cb["psychologue"] & ~cb["psychiatre"]]["part_population"].sum()
    assert abs(explorer.part_une_sans_l_autre(paires, "psychologue", "psychiatre") - x) < 1e-5   # CSV à six chiffres
    assert len(paires["epci"]) == int(cb.loc[cb["niveau"] == "epci", "territoires"].sum())
    assert "psychiatre" in traj["profs"] and "revenu_median" in traj["vars"]
    assert traj["profs"]["psychologue"]["source"] == "ADELI" and traj["profs"]["psychologue"]["famille"] == "Santé mentale"
    assert {"infirmier_lib", "infirmier_sal"} <= set(traj["profs"]), "deux séries d'infirmiers, jamais additionnées"
    assert all(v["famille"] in ("Santé", "Santé mentale") for v in paires["profs"].values())
    assert all("976" not in s["deps"] for s in traj["profs"].values())


def test_explorer_inegalites():
    """Outils de l'onglet Inégalités déplacés dans Explorer (lot 2, 28 octobre 2026). Les données sont celles de
    site_data.json sans calcul nouveau, le Gini de la page retombe sur inegalites.csv, et aucun outil n'est présent à la
    fois dans l'atlas et dans Explorer."""
    import json
    from pipeline import config, explorer
    d = _dernier_resultats()
    f = d / "site_data.json"
    if not f.exists():
        raise Ignore("site_data.json absent")
    sd = json.loads(f.read_text(encoding="utf-8"))
    di = explorer.donnees_inegalites(sd)
    assert di and set(di["niv"]) == {"dep", "epci"}
    assert di["typo"]["profils"] == sd["typologie"] and di["typo"]["acp"] == sd["acp"]
    assert len(di["typo"]["parent"]) == len(di["niv"]["epci"]["units"])
    assert di["revenu"] == sd["revenu"] and di["entonnoir"] == sd["entonnoir"]
    ecarts = [abs(explorer.gini_territoires(di, r["niv"], r["prof"]) - r["gini"]) for r in sd["inegalites"]
              if r["mode"] == "all" and r["niv"] in di["niv"] and r["prof"] in di["niv"][r["niv"]]["n"]]
    assert len(ecarts) > 50 and max(ecarts) < 1e-3, max(ecarts)   # inegalites.csv arrondi à trois décimales
    atlas = _atlas()
    page = (config.RACINE / "gabarits" / "explorer.html").read_text(encoding="utf-8")
    for fonction, fenetre in (("function escalier(", "iFenEscalier"), ("function funnel(", "iFenEntonnoir"),
                              ("function lorenzOf(", "iFenConcentration"), ("function inegLieux(", "iFenDistNv"),
                              ("function typologie(", "tyFenProfils"), ("function acpPanneau(", "tyFenAcp")):
        assert fonction not in atlas and f'id="{fenetre}"' in page, fenetre
    # l'atlas n'a plus d'onglet Inégalités ni Typologie, il renvoie vers la question d'Explorer
    assert 'data-t="inegalites"' not in atlas and 'data-t="typologie"' not in atlas
    assert 'explorer.html#qInegalites' in atlas and 'id="qInegalites"' in page


def test_explorer_catalogue():
    """Explorer lit ses variables dans le catalogue des indicateurs (site_data.json, contexte), un seul catalogue pour
    le site, l'atlas, Explorer et l'API (décision de Lucas du 28 octobre 2026). Tout indicateur du catalogue publié par
    intercommunalité est proposé pour les dixièmes, tout indicateur publié par département pour les trajectoires, rangé
    dans son thème, et aucune liste d'indicateurs n'est écrite à la main dans le code de la page."""
    import json
    from pipeline import config, explorer
    d = _dernier_resultats()
    f = d / "site_data.json"
    if not f.exists():
        raise Ignore("site_data.json absent")
    cat = json.loads(f.read_text(encoding="utf-8"))["contexte"]
    paires, traj = explorer.donnees_paires(d), explorer.donnees_trajectoires(d)
    epci = _csv(d, "contexte_epci.csv")
    attendus = {c["id"] for c in cat if "intercommunalités" in c.get("niveaux", []) and c["id"] in epci.columns}
    assert attendus and attendus == set(paires["vars"]), attendus ^ set(paires["vars"])
    # un indicateur hors des anciennes listes écrites à la main, avec son thème du catalogue
    nouveau = next(c for c in cat if c["id"] in paires["vars"] and c["id"] not in ("revenu_median", "densite_pop"))
    assert paires["vars"][nouveau["id"]]["groupe"] == nouveau["groupe"]
    dep = [c for c in cat if "départements" in c.get("niveaux", []) and c["id"] in traj["vars"]]
    assert len(dep) > 8 and all(traj["vars"][c["id"]]["groupe"] == c["groupe"] for c in dep)
    js = (config.RACINE / "gabarits" / "explorer.js").read_text(encoding="utf-8")
    assert "DC.revenu" not in js and "DC.densite" not in js and "taux_pauvrete:" not in js


def test_fenetres_repliables():
    """Fenêtres repliables d'Explorer (note du 28 octobre 2026). Chaque fenêtre a un identifiant, une barre avec la
    place des pastilles et un titre, un corps avec sa phrase de résultat, que la fenêtre repliée recopie. Une figure
    posée dans une fenêtre n'a pas de second cadre. Les deux boutons de la barre (replier, agrandir) sont de vrais
    boutons avec un nom accessible, placés à droite du titre (choix de Lucas du 28 octobre 2026)."""
    import re
    from pipeline import config
    g = config.RACINE / "gabarits"
    page, js, css = ((g / n).read_text(encoding="utf-8") for n in ("explorer.html", "figures.js", "style.css"))
    fens = re.findall(r'<article class="fenetre repliable[^"]*" id="([\w-]+)"(.*?)</article>', page, re.S)
    assert len(fens) >= 2, "fenêtres d'Explorer introuvables"
    for ident, corps in fens:
        assert '<span class="pastilles"></span>' in corps and re.search(r"<h3 id=", corps), ident
        assert 'class="fen-resume"' in corps and 'class="resultat"' in corps, ident
        assert 'class="fen-lire-bouton"' in corps and 'class="fen-lire" hidden' in corps, ident
    for b in ("p-replier", "p-agrandir"):
        assert f'class="{b}"' in js and re.search(rf'class="{b}"[^>]*aria-(label|controls)', js), b
    assert "aria-expanded" in js and 'aria-pressed' in js and "Escape" in js
    assert re.search(r"\.outil figure\.graphique\{background:none;border:0", page), "figure sans second cadre"
    assert re.search(r"\.fen-tete \.pastilles\{grid-column:2", css), "boutons à droite du titre"
def test_empreinte_inscriptions_brutes():
    """Empreinte d'un établissement vérifié, sur les inscriptions réelles en cache. Elle ne dépend pas des clés produites
    par nos règles (clé remplacée, structure copiée dans un autre type vérifié) et change quand une inscription des bases
    disparaît."""
    import pandas as pd
    from pipeline import structures_verifiees as sv
    if not sv.BASES.exists():
        raise Ignore("inscriptions des bases absentes")
    b = pd.read_parquet(sv.BASES)
    e, _ = sv.charger()
    r = e.iloc[0]
    ts = [t for t in sv.types_de(r["types"]) if t not in sum(sv.ENFANTS_DE.values(), [])]
    g = b[(b["ej"] == r["ej"]) & b["type"].isin(ts)]
    if len(g) < 2:
        raise Ignore("établissement trop petit pour le test")
    ref0 = sv.empreinte(b, r["ej"], ts)
    autre = b.assign(lieu="cle_" + b.index.astype(str))
    assert sv.empreinte(autre, r["ej"], ts) == ref0, "l'empreinte dépend des clés des règles"
    copie = pd.concat([b, g.head(1).assign(type=ts[-1] if len(ts) > 1 else ts[0])], ignore_index=True)
    assert sv.empreinte(copie, r["ej"], ts) == ref0, "une copie dans un autre type vérifié change l'empreinte"
    assert sv.empreinte(b.drop(index=g.index[0]), r["ej"], ts) != ref0 or g.iloc[0]["finess"] in set(g["finess"].iloc[1:]), \
        "une inscription disparue ne change pas l'empreinte"


_API = {}


def _api_tables():
    """Tables de l'API préparées une fois à partir de la dernière version des résultats (outils/api_donnees.py)."""
    if not _API:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "outils"))
        try:
            import api_donnees
        except ModuleNotFoundError:   # prototype de l'API absent du code public tant que l'offre n'est pas finalisée
            raise Ignore("prototype de l'API absent")
        d = _dernier_resultats()
        if not (d / "lieux_soins.csv").exists() or not (d / "evolution_explorer.csv").exists():
            raise Ignore("résultats incomplets")
        _API.update(module=api_donnees, version=d, tables=api_donnees.preparer(d))
    return _API


def test_api_donnees():
    """Données de l'API, sur les résultats réels. Aucun identifiant RPPS ni indicateur sous ODbL, aucune colonne hors du
    contrat pour les structures, totaux égaux aux fichiers du site, règle de confidentialité des zones libres."""
    import pandas as pd
    from comparer_versions import RPPS
    A_ = _api_tables()
    a, d, t = A_["module"], A_["version"], A_["tables"]
    for nom, x in t.items():
        for c in x.columns:
            if x[c].dtype == object:
                assert not x[c].astype(str).str.contains(RPPS).any(), f"identifiant RPPS possible dans {nom}.{c}"
    odbl = a.colonnes_odbl(d)
    assert odbl, "liste des indicateurs sous ODbL vide"
    assert not set(t["contexte"]["indicateur"]) & odbl and not set(t["catalogue"]["indicateur"]) & odbl
    assert not any(set(x.columns) & odbl for x in t.values())
    permis = set(a.COLS_STRUCTURES) | {"id", "numero_partage"}
    assert {c for c in t["structures"].columns if not c.startswith("declares_")} <= permis
    e = t["effectifs"]
    dep = pd.read_csv(d / "effectifs_dep_all.csv", sep=";", decimal=",", dtype={"code": str})
    for p in ("psychologue", "psychiatre", "infirmier"):
        assert e[(e["niveau"] == "dep") & (e["prof"] == p) & (e["mode"] == "all")]["n"].sum() == dep[f"n_{p}"].sum()
    fr = pd.read_csv(d / "effectifs_france.csv", sep=";")
    assert int(e[(e["niveau"] == "fra") & (e["prof"] == "psychologue") & (e["mode"] == "all")]["n"].iloc[0]) == \
        int(fr[(fr["prof"] == "psychologue") & (fr["mode"] == "all")]["n"].iloc[0])
    com, ec = t["communes"], t["effectifs_communes"]
    try:
        a.zone(com, ec, [])
        raise AssertionError("une zone vide doit être refusée")
    except a.ZoneRefusee:
        pass
    petite = com[com["population"] > 0].sort_values("population").iloc[0]["code"]
    zp = a.zone(com, ec, [petite])
    attendu = ec[ec["code"] == petite].groupby(["prof", "mode"])["n"].sum()
    assert all(l["n"] == attendu[(l["prof"], l["mode"])] for l in zp["effectifs"]), "commune entière, chiffres exacts"
    # valeurs aberrantes contrôlées (constat du 28 octobre 2026), aucune distance par-dessus la mer en outre-mer, temps de
    # l'INSEE vers la psychiatrie ambulatoire signalé dans sa limite, contrôles consignés
    v = t["criteres_communes"].merge(com[["code", "dep"]], on="code")
    for dep, km in a.DOM_DISTANCE_MAX.items():
        x = v[v["dep"] == dep]
        for c in [c for c in v.columns if c.endswith("|distance")]:
            assert not (x[c] > km).any(), f"distance par-dessus la mer, {dep} {c}"
    num = v.drop(columns=["code", "dep"]).apply(pd.to_numeric, errors="coerce")
    assert not num.isin([float("inf"), float("-inf")]).any().any(), "distance infinie servie par l'API"
    crit = t["criteres"].set_index("critere")
    assert crit["moyenne_communes"].dropna().map(abs).lt(float("inf")).all()
    if "route:psychiatrie_ambulatoire|temps" in crit.index:   # retiré en amont le 28 octobre 2026, limite si présent
        assert crit.at["route:psychiatrie_ambulatoire|temps", "limite"]
    # la table des contrôles existe, elle peut être vide une fois les distances corrigées en amont
    assert {"controle", "critere", "communes"} <= set(t["controles"].columns) or t["controles"].empty
    z = a.zone(com, ec, com.nlargest(3, "population")["code"].tolist())
    assert all((l["n"] is None) == (l["classe"] is not None) for l in z["effectifs"])
    assert all(l["n"] is None or l["n"] >= a.ZONE_EFFECTIF_MIN for l in z["effectifs"])


def test_api_serveur():
    """Serveur d'essai de l'API sur les tables réelles. Clé exigée, fiche d'un département, CSV à la française, zone
    trop petite refusée."""
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        raise Ignore("FastAPI absent")
    A_ = _api_tables()
    import api_serveur
    m = {"version": A_["version"].name, "date_rpps": None, "licence": "essai"}
    c = TestClient(api_serveur.creer_app(A_["tables"], m, {"cle-test": {"palier": "essai"}, "cle-g": {"palier": "gratuit"}}))
    # petite porte gratuite (décision de Lucas du 28 octobre 2026), territoires standards ouverts, le reste payant
    g = {"X-Cle": "cle-g"}
    assert c.get("/v0/territoires/dep/78", headers=g).status_code == 200
    assert c.get("/v0/rapport?niveau=dep&code=78&format=html", headers=g).status_code == 200
    for q in ("/v0/zone?lat=48.8&lon=2.13&rayon_km=5", "/v0/recherche?critere=population|valeur:>:1000",
              "/v0/comparer?sites=47.2,-1.5;47.4,-0.5", "/v0/rapport?lat=48.8&lon=2.13&rayon_km=5&format=html"):
        assert c.get(q, headers=g).status_code == 403, q
    assert c.get("/v0/series?prof=psychiatre", headers=g).json()["photographies_rpps"] == []
    assert c.get("/v0/meta").status_code == 401
    h = {"X-Cle": "cle-test"}
    f = c.get("/v0/territoires/dep/78", headers=h).json()
    psy = [x for x in f["effectifs"] if x["prof"] == "psychiatre" and x["mode"] == "all"][0]
    assert psy["densite_moyenne_niveau"] and abs(psy["ecart"] - (psy["densite"] / psy["densite_moyenne_niveau"] - 1)) < 1e-9
    r = c.get("/v0/effectifs?niveau=dep&prof=psychologue&format=csv", headers=h)
    assert r.text.startswith("﻿") and ";" in r.text.splitlines()[0]
    assert c.get("/v0/zone?communes=00000", headers=h).status_code == 422
    z = c.get("/v0/zone?lat=48.80&lon=2.13&rayon_km=5&format=csv", headers=h)
    assert z.text.startswith("﻿")
    gz = c.get("/v0/zone/structures?lat=48.80&lon=2.13&rayon_km=5", headers=h).json()
    assert gz["type"] == "FeatureCollection" and gz["features"]
    g = c.get("/v0/structures?niveau=dep&code=78&type=lieu_cmp&format=geojson", headers=h).json()
    assert g["type"] == "FeatureCollection" and g["features"]
    # recherche multicritère, chaque commune rendue remplit toutes les conditions, sans note ni classement
    crit = c.get("/v0/criteres", headers=h).json()["lignes"]
    assert crit and all(x["libelle"] and x["unite"] is not None and x["source"] for x in crit)
    noms = {x["critere"] for x in crit}
    assert {"population|valeur", "psychiatre|distance"} <= noms and any(n.startswith("route:") for n in noms)
    r = c.get("/v0/recherche?critere=psychiatre|distance:>:15&critere=population|valeur:>=:5000", headers=h).json()
    assert r["communes_trouvees"] > 0
    assert all(x["psychiatre|distance"] > 15 and x["population"] >= 5000 for x in r["communes"])
    route = next(n for n in noms if n.startswith("route:"))
    assert c.get(f"/v0/recherche?critere={route}:>:moyenne", headers=h).status_code == 200
    assert c.get("/v0/recherche?critere=inconnu|valeur:>:1", headers=h).status_code == 400
    # comparaison de sites
    cp = c.get("/v0/comparer?sites=47.218,-1.553;47.478,-0.563&rayon_km=10", headers=h).json()
    assert len(cp["sites"]) == 2 and all(z["population"] > 0 for z in cp["sites"])
    assert c.get("/v0/comparer?sites=47.218,-1.553&rayon_km=10", headers=h).status_code == 400
    # rapport d'un territoire et d'une zone, carte, sources et licences, aucun identifiant RPPS
    for q in ("niveau=dep&code=71", "lat=46.6684&lon=4.3672&rayon_km=15"):
        rp = c.get(f"/v0/rapport?{q}&format=html", headers=h)
        assert rp.status_code == 200 and "<svg" in rp.text and "Sources et licences" in rp.text and "Licence Ouverte" in rp.text
        from comparer_versions import RPPS
        assert not RPPS.search(rp.text)


def test_api_catalogue():
    """L'API se nourrit du catalogue du site (principe du 28 octobre 2026). Chaque indicateur de contexte hors ODbL,
    chaque profession et chaque type de structure présent dans les résultats figure au catalogue avec son libellé, son
    unité, sa source, sa licence et ses niveaux, et le point d'accès générique le sert à chacun de ses niveaux."""
    import json
    import pandas as pd
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        raise Ignore("FastAPI absent")
    A_ = _api_tables()
    import api_serveur
    a, d, t = A_["module"], A_["version"], A_["tables"]
    cat = t["catalogue"]
    sd = json.loads((d / "site_data.json").read_text(encoding="utf-8"))
    odbl = a.colonnes_odbl(d)
    attendus = {m["id"] for m in sd["contexte"] if m["id"] not in odbl}
    attendus |= set(pd.read_csv(d / "professions.csv", sep=";", dtype=str)["id"])
    attendus |= set(pd.read_csv(d / "lieux_soins.csv", sep=";", dtype=str, usecols=["type"])["type"])
    assert attendus <= set(cat["indicateur"]), sorted(attendus - set(cat["indicateur"]))[:10]
    assert not cat["indicateur"].duplicated().any()
    for c in ("libelle", "unite", "source", "licence", "niveaux"):
        assert cat[c].fillna("").astype(str).str.strip().ne("").all(), f"catalogue, {c} vide"
    c = TestClient(api_serveur.creer_app(t, {"version": d.name, "licence": "essai"}, {"k": {"palier": "gratuit"}}))
    vides = [f"{r.indicateur}@{n}" for r in cat.itertuples() for n in r.niveaux.split(",")
             if not c.get(f"/v0/indicateurs/{r.indicateur}?niveau={n}", headers={"X-Cle": "k"}).json().get("lignes")]
    assert not vides, f"indicateurs du catalogue sans valeur à un niveau déclaré : {vides[:10]}"


def test_comparaison_structures_verifiees():
    """Comparaison avant publication, sur les résultats réels. Une version comparée à elle-même ne signale rien à
    regarder pour les structures vérifiées à la main, et les établissements à revérifier du journal sont relus."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "outils"))
    import comparer_versions as cv
    d = _dernier_resultats()
    if not (d / "journal.json").exists() or not (d / "verdicts_sans_structure.csv").exists():
        raise Ignore("résultats incomplets")
    c = cv.Compte()
    cv.structures_verifiees(d, d, c)
    assert c.niveau == 0, c.lignes
    r = cv.a_reverifier(d)
    assert r is not None and all(isinstance(s, str) and s for s in r)
    assert not r or any("déjà signalés" in t for _, t in c.lignes)


def test_structures_fermees_dans_finess():
    """Une structure d'une liste vérifiée dont tous les numéros FINESS ont été fermés dans Finess+ pendant l'année de
    validité de la vérification, ou après, et qu'aucune inscription active ne décrit, n'est plus comptée et son
    établissement est à revérifier (règle du 29 octobre 2026, CMP du CH Sainte-Marie de Nice fermés les 20 et
    22 septembre 2026). Selon la source de la vérification, une fermeture antérieure laisse comptée une structure que
    l'établissement présente encore, écarte une structure attestée par les seules bases, et n'écarte une structure
    vérifiée sur une autre source publique que si elle date de moins d'un an. Lignes réelles de la liste vérifiée, dates
    de fermeture relevées dans Finess+ de septembre 2026, derniers résultats."""
    import pandas as pd
    from pipeline import structures_verifiees as sv
    s = pd.read_csv(sv.FICHIER, sep=";", dtype=str).fillna("").set_index("nom")
    cas = {"Antenne de CMP de Puget-Théniers": ("2026-09-22", False),    # l'établissement la présente le 29 octobre
           "Permanence du CMP à Thaon-les-Vosges": ("2019-03-01", False),  # établissement, fermeture ancienne
           "CMP pour enfants de Modane": ("2017-07-31", False),           # autre source publique, plus d'un an
           "Antenne du CMP à Aiguebelle": ("2026-08-21", True),           # autre source publique, moins d'un an
           "CMP Infanto-Juvénile de Feillens": ("2025-03-31", True)}      # seules les bases l'attestaient
    for nom, (date, ecartee) in cas.items():
        r = s.loc[nom]
        f = {n.strip().zfill(9): date for n in r["finess"].split(",")}
        assert (sv.fermee_depuis(r, f) == date) is ecartee, (nom, r["statut"], r["date"])
        assert sv.fermee_depuis(r, {}) is None
    # revérification du 29 octobre 2026, les CMP fermés de Sainte-Marie sont des verdicts « ferme » avec leur source
    assert "CMP Les Eaux Vives" not in s.index and "Antenne de CMP de Puget-Théniers" in s.index
    from pipeline import verdicts
    v = verdicts.charger().set_index("cle")
    assert v.loc["630786754|060033677|Nice|cmp les eaux vives", "verdict"] == "ferme"
    assert "chsmnice.ahsm.fr" in v.loc["630786754|060787686|Beausoleil|cmp de beausoleil", "commentaire"]
    d = _dernier_resultats()
    l = _csv(d, "lieux_soins.csv", dtype=str, usecols=lambda c: c in ("nom", "entite_juridique", "type"))
    sm = l[l["entite_juridique"] == "630786754"]
    assert not sm["nom"].isin(["CMP Les Eaux Vives", "CMP Michel-Ange", "CMP de Beausoleil"]).any()
    assert sm["nom"].eq("Antenne de CMP de Puget-Théniers").any()


def test_arrondissements_municipaux():
    """Les arrondissements de Paris, Lyon et Marseille sont ramenés à leur commune pour comparer la commune d'une
    adresse de FINESS ou d'un résultat de géocodage à celle de la structure (29 octobre 2026). Avant, toutes les
    structures de Paris étaient posées au centre de la commune. Référentiel d'Etalab et derniers résultats."""
    import pandas as pd
    from pipeline import lieux
    a = lieux.arrondissements()
    if not a:
        raise Ignore("référentiel absent")
    assert len(a) == 45 and a["75115"] == "75056" and a["69383"] == "69123" and a["13205"] == "13055"
    assert list(lieux.commune_de(pd.Series(["75115", "06088", None]))[:2]) == ["75056", "06088"]
    d = _dernier_resultats()
    l = _csv(d, "lieux_soins.csv", dtype=str, usecols=lambda c: c in ("commune", "emplacement"))
    for ville in ("75056", "69123", "13055"):
        v = l[l["commune"] == ville]
        part = (v["emplacement"] == "centre de la commune").mean()
        assert part < .05, (ville, round(part, 3))


def test_verdicts_orphelins_situation():
    """Chaque verdict qui ne retrouve plus sa structure dit ce qu'est devenue son inscription (contrôle permanent des
    inscriptions renommées, 29 octobre 2026), d'après le numéro FINESS de sa clé, sans que le verdict soit reporté sur
    une autre structure."""
    d = _dernier_resultats()
    v = _csv(d, "verdicts_sans_structure.csv", dtype=str)
    if v is None or "situation" not in v:
        raise Ignore("verdicts_sans_structure.csv sans la colonne situation")
    assert v["situation"].notna().all()
    assert v["situation"].str.match(r"numéro fermé dans FINESS le \d{4}-\d{2}-\d{2}|renommée|disparue|sans numéro|même nom").all()
    beausoleil = v[v["cle"].str.contains("060787686", na=False)]
    assert beausoleil.empty or beausoleil["situation"].str.startswith("numéro fermé dans FINESS le 2026-09-20").all()
    nyons = v[v["cle"].str.contains("260021845", na=False)]
    assert nyons.empty or nyons["situation"].str.startswith("même nom sous ce numéro").all()
    renommees = v[v["situation"].str.startswith(("renommée", "même nom"))]
    assert renommees["structure_actuelle"].notna().all()


def test_projections_carreaux():
    """Coordonnées des carreaux de l'INSEE converties en longitude et latitude par les formules de Snyder, contrôlées sur
    l'exemple de calcul de l'EPSG pour le Lambert azimutal européen (guidance note 7-2, 50° N et 5° E) et sur le méridien
    central d'une zone UTM (45° N, arc de méridien de l'ellipsoïde GRS 80 réduit de 0,9996)."""
    from pipeline.sources import insee_carreaux as ic
    lon, lat = ic.laea_inverse(3962799.45, 2999718.85)
    assert abs(lon - 5) < 1e-6 and abs(lat - 50) < 1e-6
    lon, lat = ic.laea_inverse(4321000, 3210000)
    assert abs(lon - 10) < 1e-6 and abs(lat - 52) < 1e-6
    lon, lat = ic.utm_inverse(500000, 4982950.400, 20)   # arc de méridien par la série directe de Snyder (3-21)
    assert abs(lon + 63) < 1e-9 and abs(lat - 45) < 1e-5
    lon, lat = ic.utm_inverse(500000, 10000000, 40, sud=True)
    assert abs(lon - 57) < 1e-9 and abs(lat) < 1e-9
    import pandas as pd
    c = ic.centres_carreaux(pd.Series(["CRS3035RES200mN2999618E3962699"]))
    assert abs(c.at[0, "lon"] - 5) < 1e-4 and abs(c.at[0, "lat"] - 50) < 1e-4   # coin sud-ouest plus 100 mètres


def test_centres_population():
    """Point de départ des distances au centre de la population de chaque commune (29 octobre 2026), d'après les vraies
    données carroyées en cache. Le centre de Paris tombe au centre de la ville, celui de Saint-Laurent-du-Maroni, que les
    carreaux ne couvrent pas, sur son chef-lieu au bord du fleuve et non au milieu de la forêt, et presque toutes les
    communes habitées de l'Hexagone sont situées par leur population."""
    from pipeline.sources import insee_carreaux as ic
    if not ic.CACHE.exists():
        raise Ignore("centres de population non calculés")
    import pandas as pd
    c = pd.read_parquet(ic.CACHE).set_index("code")
    assert 2.30 < c.at["75056", "lon"] < 2.40 and 48.84 < c.at["75056", "lat"] < 48.88
    assert abs(c["pop"].sum() / 64e6 - 1) < .06, c["pop"].sum()
    assert not c.index.str.startswith(("971", "973", "976")).any()
    if ic.CACHE_BAN.exists():
        b = pd.read_parquet(ic.CACHE_BAN).set_index("code")
        if "97311" in b.index:
            assert b.at["97311", "lat"] > 5.4
    d = _dernier_resultats()
    import json
    j = json.loads((d / "journal.json").read_text(encoding="utf-8"))
    ctl = dict((k, v) for k, v in j.get("controles", []))
    v = ctl.get("Point de départ des distances, communes habitées situées par le centre de leur population, leur "
                "chef-lieu ou le centre de leur contour")
    if v is None:
        raise Ignore("résultats antérieurs au point de départ pondéré")
    n_pop = int(v.split(" par leur population")[0].replace(" ", ""))
    assert n_pop > 33000, v


def test_cle_persistante_structures():
    """Clé persistante des structures (29 octobre 2026). Sur deux vraies versions publiées de part et d'autre de la
    nouvelle version du ROR du 26 octobre 2026, presque toutes les structures du 28 octobre gardent leur clé le
    29 octobre, y compris celles que FINESS a renommées ou que le ROR a renumérotées, aucune clé n'est
    portée par deux structures, les lignes par public prennent la clé de leur structure, et une version comparée à
    elle-même garde toutes ses clés."""
    import pandas as pd
    from pipeline import cles_structures as cs, config
    v28, v29 = config.RESULTATS / "2026-10-28" / "lieux_soins.csv", _dernier_resultats() / "lieux_soins.csv"
    if not v28.exists() or not v29.exists():
        raise Ignore("versions du 28 octobre et du jour absentes")
    a = pd.read_csv(v28, sep=";", dtype=str)
    b = pd.read_csv(v29, sep=";", dtype=str)
    ca, reg, _ = cs.attribuer(a, "2026-10-28", pd.DataFrame(columns=cs.COLS))
    cb, reg2, c = cs.attribuer(b, "2026-10-29", reg)
    assert ca.notna().all() and cb.notna().all()
    parents = ~b["type"].isin(cs._parents())
    assert not cb[parents].duplicated().any()
    # CMP pour adultes de la même structure, même clé que la ligne « tous publics »
    cmp_ = b[b["type"] == "lieu_cmp"].assign(id=cb).set_index(["commune", "nom", "adresse"])["id"]
    cmp_ = cmp_[~cmp_.index.duplicated(keep=False)]
    adu = b[b["type"] == "lieu_cmp_adultes"].assign(id=cb)
    commun = adu.set_index(["commune", "nom", "adresse"])["id"]
    commun = commun[commun.index.isin(cmp_.index) & ~commun.index.duplicated(keep=False)]
    assert (commun == cmp_.reindex(commun.index)).mean() > .99
    retrouvees = sum(c[e] for e in cs.ETAPES)
    assert retrouvees / len(reg) > .99, c
    assert c["numéro FINESS"] + c["unité du ROR"] + c["nom ou voie"] > 100, c   # clé interne changée, structure retrouvée
    _c, _r, soi = cs.attribuer(b, "2026-10-30", reg2)
    assert soi["nouvelles"] == 0 and soi["disparues"] == 0, soi


def test_voies_developpees():
    """Abréviations des voies développées pour le géocodage (29 octobre 2026), sur de vraies adresses de FINESS."""
    from pipeline.lieux import voie_developpee
    assert voie_developpee("R Anne De Ticheville") == "Rue Anne De Ticheville"
    assert voie_developpee("27 AV DU GAL LECLERC") == "27 Avenue DU Général LECLERC"
    assert voie_developpee("LD SITE DE TATTONE") == "Lieu-dit SITE DE TATTONE"
    assert voie_developpee("RUE DU 8 MAI 1945") == "RUE DU 8 MAI 1945"


def test_empreinte_meme_calcul():
    """L'empreinte d'un établissement vérifié se calcule de la même façon dans la chaîne et dans l'outil qui la
    renouvelle (outils/structures_verifiees.py valider) : le fichier des inscriptions des bases porte les numéros FINESS
    rapprochés et absorbés que l'empreinte compte. Sans eux, 43 des 48 établissements étaient signalés à revérifier
    sans que rien n'ait changé (constat du 29 octobre 2026). Sur les vraies inscriptions en cache, un établissement que
    la dernière exécution ne signale pas a la même empreinte recalculée ici."""
    import pandas as pd
    from pipeline import structures_verifiees as sv
    from pipeline.sources import referentiel
    if not sv.BASES.exists():
        raise Ignore("inscriptions des bases absentes")
    b = pd.read_parquet(sv.BASES)
    assert {"finess_rapproche", "finess_absorbes"} <= set(b.columns)
    d = _dernier_resultats()
    e = _csv(d, "etablissements_verifies.csv", dtype=str)
    if e is None or "raison_reverification" not in e:
        raise Ignore("résultats antérieurs à la raison de revérification")
    ref = referentiel.charger(True)
    b = b.assign(dep=b["commune"].map(ref.communes.set_index("code")["dep"]))
    etab, _s = sv.charger()
    stock = etab.set_index(["ej", "etablissement"])
    ok = e[e["raison_reverification"].isna()]
    assert len(ok) > 40
    for r in ok.itertuples():
        x = stock.loc[(r.ej, r.etablissement)]
        if not x["empreinte"]:
            continue
        ts = [t for t in sv.types_de(x["types"]) if t not in sum(sv.ENFANTS_DE.values(), [])]
        assert sv.empreinte(b, r.ej, ts, x["departement"]) == x["empreinte"], r.etablissement


def test_declares_numero_partage():
    """Un effectif déclaré au répertoire sous un numéro FINESS que plusieurs structures de la commune partagent est celui
    de l'établissement, jamais attribué à l'une d'elles (règle des trois temps, constat du 29 octobre 2026, numéro
    840000541 du CH de Montfavet, dont les 54 psychiatres étaient recopiés sur un CATTP, deux CMP et une maison
    d'accueil spécialisée). Sur les vraies inscriptions et les vraies activités du RPPS en cache, Vaucluse : chaque
    structure qui partage son numéro le sait (partage_par), la somme attribuée aux structures seules sous leur numéro
    ne dépasse jamais l'effectif de l'établissement, et le dernier fichier publié n'attribue aucun effectif partagé."""
    import pandas as pd
    import pyarrow.dataset as ds
    from pipeline import config, lieux as lieux_mod, structures_verifiees as sv
    act_f = config.INTER / "rpps_activites.parquet"
    if not sv.BASES.exists() or not act_f.exists():
        raise Ignore("inscriptions ou activités du RPPS absentes du cache")
    b = pd.read_parquet(sv.BASES)
    b = b[b["commune"].str.startswith("84", na=False)]
    nums = sorted(set(b["finess"].dropna()) | set(b["finess_rapproche"].dropna()))
    act = ds.dataset(act_f).to_table(columns=["id", "prof", "finess", "com"], filter=ds.field("finess").isin(nums)).to_pandas()
    pros = lieux_mod.professionnels(b, act)
    assert "partage_par" in pros
    montfavet = b[(b["finess"] == "840000541") & (b["commune"] == "84007")]["lieu"].unique()
    assert len(montfavet) > 1 and (pros.loc[pros.index.isin(montfavet), "partage_par"] == len(montfavet)).all()
    seules = pros[pros["partage_par"] == 1].drop(columns="partage_par")
    cle = b.drop_duplicates("lieu").set_index("lieu")[["finess", "commune"]]
    somme = seules.join(cle).groupby(["finess", "commune"]).sum()
    a = act.assign(prof=act["prof"].astype(str), com=act["com"].astype(str))
    etab = a.groupby(["finess", "com", "prof"])["id"].nunique().unstack(fill_value=0)
    for (f, c), r in somme.iterrows():
        for p, v in r.items():
            assert v <= (etab.at[(f, c), p] if (f, c) in etab.index and p in etab else 0), (f, c, p)
    d = _dernier_resultats()
    l = _csv(d, "lieux_soins.csv", dtype=str)
    if l is None or "declares_partage_par" not in l:
        raise Ignore("dernier fichier publié antérieur à la correction")
    partages = l["declares_partage_par"].notna()
    assert partages.any() and l.loc[partages, "declares_psychiatre"].isna().all()
    e = _csv(d, "declares_etablissements.csv", dtype=str)
    assert e is not None and (e["structures_partageant"].astype(int) > 1).all()


def test_lecture_locale_arrete_la_chaine():
    """Finess+ ou Sirene en cache mais illisibles (mémoire saturée) arrêtent la chaîne au lieu de la laisser se
    rabattre sur le flux FINESS historique sans coordonnées (exécution du 29 octobre 2026 à 14 h 37). L'échec de lecture
    est provoqué ici sur les vrais fichiers du cache, sans donnée inventée."""
    from unittest import mock
    from pipeline import config
    from pipeline.sources import finess, sirene
    from pipeline.util import LectureLocaleImpossible
    if not (config.BRUT / "finess_plus.json.gz").exists():
        raise Ignore("Finess+ absent du cache")
    with mock.patch.object(finess.gzip, "open", side_effect=MemoryError()):
        try:
            finess.charger(hors_ligne=True)
            raise AssertionError("la lecture impossible de Finess+ n'a pas arrêté la chaîne")
        except LectureLocaleImpossible:
            pass
    if sirene.EXTRAIT.exists():
        with mock.patch.object(sirene.pd, "read_parquet", side_effect=MemoryError()):
            try:
                sirene.charger(hors_ligne=True)
                raise AssertionError("la lecture impossible de Sirene n'a pas arrêté la chaîne")
            except LectureLocaleImpossible:
                pass


def test_seuil_structures_au_centre():
    """La comparaison avant publication bloque une version dont plus de 10 % des structures sont posées au centre de leur
    commune (source de coordonnées perdue), et laisse passer la dernière version."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "outils"))
    import comparer_versions as cv
    d = _dernier_resultats()
    p = cv.part_au_centre(d)
    if p is None:
        raise Ignore("lieux_soins.csv absent")
    assert p < cv.PART_CENTRE_BLOQUANT, p
    c = cv.Compte()
    cv.emplacements(d, d, c)
    assert c.niveau == 0 and any("centre de leur commune" in t for _, t in c.lignes)


def test_verdict_ne_retire_pas_une_structure_attestee():
    """Un verdict de retrait (doublon, fermée, introuvable, pas un CMP) porte sur une inscription des bases. Il ne retire
    jamais une structure que la liste vérifiée de son établissement atteste par l'établissement ou par une autre source
    publique (CMP Le Petit Nice d'Embrun, attesté par la HAS, retiré le 29 octobre 2026 par le verdict « doublon » d'une
    autre inscription). Une structure gardée sur la seule foi des bases reste soumise aux verdicts (CMP de Paul-Brousse).
    Sur les derniers résultats et les vraies listes."""
    import json
    import pandas as pd
    from pipeline import structures_verifiees as sv
    d = _dernier_resultats()
    j = json.loads((d / "journal.json").read_text(encoding="utf-8"))
    if not any(k.startswith("Verdicts de retrait qui désignent une structure attestée") for k, _v in j.get("controles", [])):
        raise Ignore("résultats antérieurs à la règle")
    s = pd.read_csv(sv.FICHIER, sep=";", dtype=str).fillna("")
    nr = _csv(d, "structures_non_retenues.csv", dtype=str)
    v = nr[nr["raison"].str.startswith("vérification à la main", na=False)]
    attestees = set(zip(*[s.loc[s["statut"].isin(["etablissement", "source_publique"]), c] for c in ("ej", "nom", "commune")]))
    assert not [r for r in zip(v["ej"], v["nom"], v["commune"]) if r in attestees]
    l = _csv(d, "lieux_soins.csv", dtype=str, usecols=lambda c: c in ("nom", "commune", "type"))
    assert ((l["nom"] == "CMP Le Petit Nice") & (l["commune"] == "05046") & (l["type"] == "lieu_cmp")).any()
    assert ((v["nom"] == "CMP de Paul-Brousse") & (v["commune"] == "94076")).any()


def test_distances_sans_traverser_la_mer():
    """Une distance au plus proche est cherchée sur le territoire de la commune (Hexagone, Corse, chaque département
    d'outre-mer), jamais par-dessus la mer (note docs/note_valeurs_aberrantes_2026-10-28.md). Sur les vraies structures,
    un point de Mayotte n'a pas de voisin quand seules celles de La Réunion sont proposées, il en a un tout près parmi
    celles de Mayotte. Les distances publiées des départements d'outre-mer et de la Corse restent sous 300 km."""
    import numpy as np
    from pipeline.analyses import coords_3d, mediane_ponderee, plus_proche_km, zone_terrestre
    d = _dernier_resultats()
    l = _csv(d, "lieux_soins.csv", dtype={"dep": str}, usecols=lambda c: c in ("dep", "latitude", "longitude", "type"))
    l = l.dropna(subset=["latitude", "longitude"]).rename(columns={"latitude": "lat", "longitude": "lon"})
    may, reu = l[l["dep"] == "976"].head(20), l[l["dep"] == "974"]
    if may.empty or reu.empty:
        raise Ignore("pas de structures à Mayotte ou à La Réunion")
    xm, xr = coords_3d(may["lon"], may["lat"]), coords_3d(reu["lon"], reu["lat"])
    zm, zr = zone_terrestre(may["dep"]), zone_terrestre(reu["dep"])
    assert np.isinf(plus_proche_km(xm, zm, xr, zr)).all()
    assert (plus_proche_km(xm, zm, xm, zm) == 0).all()
    assert list(zone_terrestre(["2A", "2B", "75", "971", None])) == ["corse", "corse", "hexagone", "971", "hexagone"]
    assert np.isnan(mediane_ponderee([1.0, np.inf, np.inf], [1, 1, 1]))
    assert mediane_ponderee([1.0, 2.0, np.inf], [1, 5, 1]) == 2.0
    t = _csv(d, "distances_lieux_dep.csv", dtype={"code": str})
    loin = t[t["code"].str.match(r"97|2A|2B") & (t["distance_mediane_km"] > 300)]
    assert loin.empty, loin[["code", "type", "distance_mediane_km"]].head().to_dict("records")


def test_envoi_programme():
    """Envoi programmé de la fenêtre du courrier (28 octobre 2026). Dates lues sous les deux formes, empreinte qui
    change avec le texte ou les destinataires, sur un vrai brouillon (sans rien écrire ni envoyer)."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from outils import messagerie as m
    assert m.lire_date("2026-11-03T09:30") == m.lire_date("03/11/2026 09:30")
    assert m.lire_date("03/11/2026 9h") is not None and m.lire_date("demain") is None
    bs = m.brouillons()
    if not bs:
        raise Ignore("aucun brouillon")
    b = dict(bs[0])
    e = m.empreinte(b)
    assert m.empreinte(dict(b, corps=b["corps"] + " ")) != e
    assert m.empreinte(dict(b, a=b["a"] + ["x@exemple.fr"])) != e
    assert m.empreinte(dict(b, envoi_prevu="2026-11-03T09:30")) == e
    assert not m.controler_brouillon({k: v for k, v in b.items() if k in
                                      {"id", "a", "cc", "objet", "corps", "motif", "sources", "en_reponse_a"}}
                                     | {"envoi_prevu": "2026-11-03T09:30"})
    assert m.controler_brouillon({"id": "essai", "a": ["a@b.fr"], "objet": "o", "corps": "c", "motif": "m",
                                  "envoi_prevu": "bientôt"})


def test_registre_licences():
    """Registre des licences (demande de Lucas du 28 octobre 2026). Chaque licence vérifiée porte son adresse officielle et
    sa date de lecture, une licence non vérifiée n'entre jamais dans l'offre payante, chaque source suivie et chaque
    indicateur publié trouvent leur licence, les affections de longue durée sont en Licence Ouverte 1.0 (data.gouv)."""
    import json
    from pipeline import licences
    for ident, l in licences.LICENCES.items():
        assert {"nom", "affiche", "page", "lue_le", "usage_commercial", "partage_identique", "mention", "statut"} <= set(l)
        assert l["usage_commercial"] in (licences.OUI, licences.NON, licences.A_CONFIRMER)
        if l["statut"] == "vérifié":
            assert l["page"].startswith("https://") and l["lue_le"], ident
        else:
            assert not licences.offre_payante(ident), f"licence non vérifiée dans l'offre payante, {ident}"
    assert licences.offre_payante("lo-2.0") and licences.offre_payante("odbl-1.0")
    assert licences.offre_payante("lo-1.0") and not licences.offre_payante(None)   # texte de 2011 relu le 28 octobre 2026
    d = _dernier_resultats()
    j = json.loads((d / "journal.json").read_text(encoding="utf-8"))
    for s in j["sources"]:
        if s.get("licence"):
            assert licences.identifiant(s["licence"], s["source"]) in licences.LICENCES, s["source"]
    assert licences.identifiant("Licence Ouverte 2.0", "Assurance Maladie, affections de longue durée") == "lo-1.0"
    assert licences.identifiant("Licence Ouverte 2.0", "FINESS (Finess+)") == "lo-2.0"
    assert licences.identifiant("ODbL", "Assurance Maladie, pathologies") == "odbl-1.0"
    assert "OpenStreetMap" in licences.attribution("INSEE, temps d'accès par la route")


def test_catalogue_enrichi():
    """Catalogue unique, sur les vraies données (tables de contexte et indicateurs de la dernière version). Chaque
    indicateur porte l'identifiant de sa licence dans le registre, ses niveaux en codes, sa règle d'agrégation et le type
    de sa valeur. Les indicateurs sous ODbL sont ceux du registre, une part n'est jamais déclarée exactement agrégeable,
    une médiane ou un taux standardisé jamais agrégeable."""
    import json
    import pandas as pd
    from pipeline import config, indicateurs, licences
    d = _dernier_resultats()
    sd = json.loads((d / "site_data.json").read_text(encoding="utf-8"))
    tables = {}
    for niv in ("com", "epci", "dep", "reg"):
        f = d / f"contexte_{niv}.csv"
        if f.exists():
            x = pd.read_csv(f, sep=";", decimal=",", dtype={"code": str})
            o = d / f"contexte_{niv}_odbl.csv"
            if o.exists():
                x = x.merge(pd.read_csv(o, sep=";", decimal=",", dtype={"code": str}), on="code", how="left")
            tables[niv] = x.set_index("code")
    propres = {c[0] for c in config.CONTEXTE} | {c[0] for c in config.CONTEXTE_VULNERABILITE}
    autres = [{"id": m["id"], "libelle": m["label"], "unite": m["unite"], "explication": m.get("explication", ""),
               "source": m["source"], "famille": m.get("famille", ""), "licence": m["licence"], "groupe": m.get("groupe")}
              for m in sd["contexte"] if m["id"] not in propres]
    cat = indicateurs.liste({"contexte": tables, "indicateurs": autres})
    assert len(cat) >= len(sd["contexte"]) - 2
    regles = {"moyenne_ponderee_population", "moyenne_ponderee_population_approchee", "non_agregeable"}
    for x in cat:
        assert x["licence_id"] in licences.LICENCES, x["id"]
        assert x["licence"] == licences.affiche(x["licence_id"])
        assert x["agregation"] in regles and x["type_valeur"], x["id"]
        assert set(x["niveaux_codes"]) <= {"com", "epci", "dep", "reg"}
        if x["unite"] == "%":
            assert x["agregation"] != "moyenne_ponderee_population", x["id"]
        if "standardis" in x["unite"] or x["unite"] in ("km", "€"):
            assert x["agregation"] == "non_agregeable", x["id"]
    odbl_site = {m["id"] for m in sd["contexte"] if "odbl" in str(m["licence"]).lower()}
    assert indicateurs.odbl({"contexte": tables, "indicateurs": autres}) >= odbl_site
    ald = [x for x in cat if x["source"].startswith("Assurance Maladie, affections de longue durée")]
    assert ald and all(x["licence_id"] == "lo-1.0" for x in ald)


def test_api_offre_payante_licences():
    """Aucune donnée dont la licence n'établit pas l'usage commercial n'est servie dans un palier payant. La porte
    gratuite, qui ne donne que ce qui est déjà gratuit sur le site, peut les servir."""
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        raise Ignore("FastAPI absent")
    import api_serveur
    A_ = _api_tables()
    cat = A_["tables"]["catalogue"]
    assert {"licence_id", "offre_payante", "attribution"} <= set(cat.columns)
    hors = set(cat.loc[~cat["offre_payante"].astype(bool), "indicateur"])
    m = {"version": A_["version"].name, "date_rpps": None, "licence": "essai"}
    c = TestClient(api_serveur.creer_app(A_["tables"], m, {"p": {"palier": "essai"}, "g": {"palier": "gratuit"}}))
    servis = {x["indicateur"] for x in c.get("/v0/catalogue", headers={"X-Cle": "p"}).json()["lignes"]}
    assert not servis & hors, sorted(servis & hors)[:5]
    if hors:
        i = sorted(hors)[0]
        assert c.get(f"/v0/indicateurs/{i}", headers={"X-Cle": "p"}).status_code == 403
        gratuit = {x["indicateur"] for x in c.get("/v0/catalogue", headers={"X-Cle": "g"}).json()["lignes"]}
        assert hors <= gratuit
    fiche = c.get("/v0/territoires/dep/78", headers={"X-Cle": "p"}).json()
    assert not {x["indicateur"] for x in fiche["contexte"]} & hors


def test_verrou_execution():
    """Une seule exécution à la fois (incident du 29 octobre 2026, tâche planifiée et exécution à la main en même temps).
    Verrou d'un processus disparu repris, verrou d'un processus Python vivant refusé, verrou retiré à la fin."""
    import os
    import sys
    import tempfile
    import psutil
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import run
    from pipeline import config
    ancien = config.DONNEES
    try:
        with tempfile.TemporaryDirectory() as d:
            config.DONNEES = Path(d)
            f = config.DONNEES / "execution.verrou"
            mort = max(psutil.pids()) + 1000
            f.write_text(f"{mort} 2026-10-29T08:00:00", encoding="utf-8")
            with run.verrou_execution():
                assert f.read_text(encoding="utf-8").split()[0] == str(os.getpid())
            assert not f.exists()
            vivant = next((q.pid for q in psutil.process_iter(["name"]) if q.pid != os.getpid()
                           and "python" in (q.info["name"] or "").lower()), None)
            if vivant:
                f.write_text(f"{vivant} 2026-10-29T08:00:00", encoding="utf-8")
                try:
                    with run.verrou_execution():
                        raise AssertionError("verrou d'une exécution vivante ignoré")
                except SystemExit as e:
                    assert e.code == 3
                assert f.exists()
    finally:
        config.DONNEES = ancien


def test_referencement():
    """Phase 1 de la communication (29 octobre 2026) : balises de citation des rapports pour Google Scholar, DOI
    seulement pour la version archivée, jeu de données schema.org avec les champs demandés par Google, et sur le site
    construit, une adresse de référence par page, aucune page exclue de la publication dans le plan du site."""
    import json
    import re
    import xml.etree.ElementTree as ET
    from pipeline import config, referencement as rf
    b = rf.balises_rapport("sante-mentale", config.VERSION_ZENODO, config.TITRES_DEPOTS["sante-mentale"], True)
    for nom in ("citation_title", "citation_author", "citation_publication_date", "citation_pdf_url", "citation_doi"):
        assert f'name="{nom}"' in b, nom
    assert config.VERSION_ZENODO.replace("-", "/") in b and config.DOI_RAPPORTS["sante-mentale"] in b
    b2 = rf.balises_rapport("sante", "2026-10-01", "Rapport", False)
    assert "citation_doi" not in b2 and "citation_pdf_url" not in b2
    j = rf.jeu_de_donnees("2026-10-29", "donnees/2026-10-29/donnees.zip", ["https://www.data.gouv.fr/datasets/x", "x.html"])
    assert 50 <= len(j["description"]) <= 5000 and j["license"].startswith("https://")
    assert j["creator"]["sameAs"].endswith(config.ORCID) and j["identifier"].endswith(config.DOI_DONNEES)
    assert j["isBasedOn"] == ["https://www.data.gouv.fr/datasets/x"]
    assert rf._injecter(rf._injecter("<head></head>", "<a>"), "<b>") == f"<head>{rf.MARQUE}<b>\n</head>"
    site = config.RACINE / "site"
    if not (site / "sitemap.xml").exists():
        raise Ignore("site non construit")
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [e.text for e in ET.parse(site / "sitemap.xml").getroot().findall("s:url/s:loc", ns)]
    assert locs and all(u.startswith(config.ADRESSE_SITE) for u in locs)
    assert not any(re.search(r"/(prototype\d*|maquettes|_[^/]*)/", u) for u in locs)
    assert f"{config.ADRESSE_SITE.rstrip('/')}/" in locs and not any(u.endswith("/atlas.html") for u in locs)
    for p in rf.pages_publiques(site):
        t = p.read_text(encoding="utf-8")
        assert t.count('rel="canonical"') == 1 and t.count(rf.MARQUE) <= 1, p
    fichiers = (site / "methode-fichiers.html").read_text(encoding="utf-8")
    jeu = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', fichiers).group(1))
    assert jeu["@type"] == "Dataset" and jeu["distribution"][0]["contentUrl"].endswith(".zip")
    assert "Sitemap:" in (site / "robots.txt").read_text(encoding="utf-8")


def test_reseaux_messages():
    """Onglet « Réseaux » (phase 2 de la communication, 29 octobre 2026), sans rien publier, sur les trois premiers
    messages rédigés à partir de constats publiés (docs/reseaux/messages). Contrôles passés, version Bluesky de
    300 graphèmes au plus, facettes de lien en octets UTF-8 qui retombent sur le lien, texte LinkedIn échappé, figure
    PNG de 2 Mo au plus avec son texte de remplacement, et un message modifié après sa programmation jamais publié."""
    import datetime as dt
    import json
    import shutil
    import tempfile
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from outils import reseaux as r
    fichiers = sorted((Path(__file__).resolve().parent.parent / "docs" / "reseaux" / "messages").glob("*.json"))
    if not fichiers:
        raise Ignore("aucun message rédigé")
    ms = [json.loads(f.read_text(encoding="utf-8")) for f in fichiers]
    for m in ms:
        assert not r.controler_message(m), (m["id"], r.controler_message(m))
        texte = m["bluesky"]
        assert r.graphemes(texte) <= r.BLUESKY_GRAPHEMES and len(texte.encode("utf-8")) <= r.BLUESKY_OCTETS
        brut = texte.encode("utf-8")
        for f in r.facettes(texte):
            lien = brut[f["index"]["byteStart"]:f["index"]["byteEnd"]].decode("utf-8")
            assert f["features"][0]["uri"] in (lien, "https://" + lien) and not lien.endswith((".", ","))
        rec = r.enregistrement_bluesky(m, {"$type": "blob"}, 1600, 900, dt.datetime(2026, 11, 3, 9, 30))
        assert rec["createdAt"].endswith("Z") and rec["embed"]["images"][0]["alt"] and rec["langs"] == ["fr"]
        c = r.corps_linkedin(m, "urn:li:person:x", "urn:li:image:x")
        assert c["content"]["media"]["altText"] and c["visibility"] == "PUBLIC"
        assert "\\(" in c["commentary"] or "(" not in m["linkedin"]
    # graphèmes, accents séparés et emoji composés comptent pour un
    assert r.graphemes("é") == 1 and r.graphemes("é") == 1 and r.graphemes("👩‍🔬") == 1
    assert r.graphemes("🇫🇷") == 1 and r.graphemes("a\r\nb") == 3
    assert r.echapper_linkedin("(a) #b @c") == "\\(a\\) \\#b \\@c"
    assert [x[2] for x in r.liens("voir ubicura.fr/explorer.html. Et https://doi.org/10.5281/x,")] == \
        ["https://ubicura.fr/explorer.html", "https://doi.org/10.5281/x"]
    assert r.controler_message(dict(ms[0], bluesky=ms[0]["bluesky"] + " x" * 200))
    assert r.controler_message(dict(ms[0], alt=""))
    assert r.controler_message(dict(ms[0], linkedin=ms[0]["linkedin"] + "\nRésultat : rien"))
    # un message programmé puis modifié n'est jamais publié, il revient à relire
    avant = (r.MESSAGES, r.FIGURES, r.JOURNAL_PUBLICATIONS)
    tmp = Path(tempfile.mkdtemp(prefix="reseaux_"))
    try:
        r.MESSAGES, r.FIGURES, r.JOURNAL_PUBLICATIONS = tmp / "messages", tmp / "figures", tmp / "journal.csv"
        r.FIGURES.mkdir(parents=True)
        m = dict(ms[0])
        shutil.copyfile(r.chemin_figure(m), r.FIGURES / f"{m['id']}.png")
        m.update(figure=f"{m['id']}.png", publications={})
        r.programmer(m, dt.datetime.now() - dt.timedelta(minutes=1))
        assert r.empreinte(m) == m["empreinte_validee"]
        m["bluesky"] += " Ajout."
        r.enregistrer(m)

        def interdit(_m):
            raise AssertionError("message modifié publié")
        assert r.publier_programmes({"linkedin": interdit, "bluesky": interdit}) == 0
        assert r.lire_json(r.MESSAGES / f"{m['id']}.json")["statut"] == "a_relire"
        # même chose quand seule la figure change
        m = r.lire_json(r.MESSAGES / f"{m['id']}.json")
        r.programmer(m, dt.datetime.now() - dt.timedelta(minutes=1))
        (r.FIGURES / f"{m['id']}.png").write_bytes((r.FIGURES / f"{m['id']}.png").read_bytes() + b"\0")
        assert r.publier_programmes({"linkedin": interdit, "bluesky": interdit}) == 0
        assert r.lire_json(r.MESSAGES / f"{m['id']}.json")["statut"] == "a_relire"
        assert not r.JOURNAL_PUBLICATIONS.exists()
    finally:
        r.MESSAGES, r.FIGURES, r.JOURNAL_PUBLICATIONS = avant
        shutil.rmtree(tmp, ignore_errors=True)


def test_identifiant_bluesky():
    """Fichier .well-known/atproto-did de l'identifiant @ubicura.fr, le DID seul sans retour à la ligne, retiré sans DID
    valide (forme did:plc de 24 caractères en base 32, https://atproto.com/specs/handle)."""
    import tempfile
    from pipeline import config, site
    d = Path(tempfile.mkdtemp(prefix="site_"))
    f = d / ".well-known" / "atproto-did"
    did = "did:plc:" + "a2" * 12
    assert site.identifiant_bluesky(d, did) and f.read_bytes() == did.encode("ascii")
    assert not site.identifiant_bluesky(d, "did:plc:trop-court") and not f.exists()
    site.identifiant_bluesky(d, did)
    assert not site.identifiant_bluesky(d, "") and not f.exists()
    assert not config.BLUESKY_DID or site.DID_VALIDE.fullmatch(config.BLUESKY_DID)
    publie = config.RACINE / "site" / ".well-known" / "atproto-did"
    if config.BLUESKY_DID and publie.exists():
        assert publie.read_text(encoding="ascii") == config.BLUESKY_DID


if __name__ == "__main__":
    n = 0
    ignores = []
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            try:
                f()
            except Ignore as e:
                ignores.append(nom)
                print("ignoré", nom, "-", e)
                continue
            n += 1
            print("ok", nom)
    print(f"{n} tests réussis" + (f", {len(ignores)} ignorés faute de résultats : {', '.join(ignores)}" if ignores else ""))
