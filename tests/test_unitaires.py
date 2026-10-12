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
    assert " open" in site.md_html(md, None, imprimer=True)[1]
    assert site.en_bref("### En bref\n\n- Un.\n- Deux.\n\nSuite") == ["Un.", "Deux."]


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
    a_verifier = [racine / "atlas" / "atlas_template.html"]
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
    cat = pd.Series(["soins", "sans_soins", "soins", "sans_soins", "sans_soins", "soins"], index=act.index)
    loc = act[act["com"].notna() & (cat != "sans_soins")]
    t = build.parcours(act, cat, loc).set_index("prof").loc["psychologue"]
    # a soigne (compté), b et e sans lieu, c seulement téléconsultation, d seulement industrie
    assert (t["avec_activite"], t["sans_lieu"], t["avec_lieu"], t["dans_densites"]) == (5, 2, 3, 1)
    assert (t["sans_soins_seulement"], t["dont_teleconsultation"]) == (2, 1)


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
    assert build.categories_activites(act).tolist() == ["soins", "sans_soins", "public_particulier", "sans_soins", "sans_soins",
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


if __name__ == "__main__":
    n = 0
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            f()
            n += 1
            print("ok", nom)
    print(f"{n} tests réussis")
