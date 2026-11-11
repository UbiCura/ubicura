"""Fiche de territoire resserrée (validée par Lucas le 31 octobre 2026, prototype dans prototypes/fiche_resserree/) :
les bandes de domaine, toutes sur un même gabarit, et « En bref » en matrice. Ce module ne fait que ranger ce que
fiche_territoire.fiche et constats.constats ont déjà calculé : lignes types, constats, phrases, cartes, comptages. Il ne
calcule aucun chiffre ; les cartes propres à la fiche resserrée (départements d'une région, outre-mer sur toute la
France) se dessinent avec cartes_presentation, sur les classes des petites cartes.

- bandes() : santé mentale, offre de soins, puis un domaine du contexte par bande, chacune avec son titre, son
  comptage, ses phrases de synthèse, son « Comment lire », ses lignes groupées par thème (lecture et source visibles),
  sa carte de bloc, ses autres indicateurs et ses détails techniques ;
- tableau_de_bord() : les constats, liste fixe (constats.CANDIDATS), groupés par section ;
- carte_region(), carte_france() : les deux cartes ajoutées.
"""
from __future__ import annotations

from . import affichage as AF
from . import cartes_presentation as CP

# indicateurs des chiffres clés en tuiles (fiche_territoire.fiche, f["cles"]) : leur phrase rédigée reste visible
TUILES = {"prof:psychologue:all", "prof:psychiatre:all", "dist_lieu_cmp_adultes"}
# noms courts des domaines dans la barre collante (avis du regard neuf, § 2) ; le nom entier reste en titre de bande
COURT = {"sm": "Santé mentale", "sante": "Offre de soins", "recours": "État de santé", "population": "Population",
         "revenus": "Revenus", "enfance": "Enfance", "mobilite": "Distances", "violences": "Violences",
         "environnement": "Cadre de vie"}
LISTE_COURTE = 5    # lignes visibles d'une liste longue (« Où exercent »), le reste replié


def ancre(ident: str) -> str:
    return "l-" + ident.lower().replace(":", "-").replace("_", "-")


def phrase_seule(k: dict, ens: str) -> str:
    """Phrase rédigée d'un constat, sans la phrase sur l'ensemble, écrite une seule fois sous les tuiles (défaut m5 de
    docs/corrections_avant_mise_en_ligne.md)."""
    return " ".join(p.replace(ens, "").strip() for p in k["phrases"]).replace("  ", " ").strip()


def mais(e, pos_txt, kind=None, e_mots=True, code=None, v_txt=None, ref_txt=None) -> bool:
    """« mais » devant la position quand ce que le lecteur voit à côté d'elle va en sens contraire (affichage.contraire) :
    l'écart quand il est écrit (offre, hors petit effectif et absence), sinon la valeur et l'ensemble affichés
    (distances, petits effectifs, contexte ; relecture des fiches construites du 1er novembre 2026)."""
    if code == "aucun" or not pos_txt:
        return False
    ecrit = kind in ("prof", "lieux") and bool(e_mots) and code != "petit"
    return bool(AF.contraire(e, ecrit, v_txt, ref_txt, pos_txt))


def bandes(ctx: dict) -> list[dict]:
    """Les bandes de domaine de la fiche, dans l'ordre : santé mentale, offre de soins, puis les domaines du contexte.
    Chaque bande a le même gabarit : titre, comptage des écarts, phrases de synthèse, « Comment lire », groupes de lignes
    (thème, lecture et source visibles), carte de bloc, autres indicateurs et détails techniques repliés."""
    f, ks, x = ctx["f"], ctx["constats"], ctx["extras"]
    niv, lv = f["niv_pluriel"], f["niveau"]
    ens = f["cle_ensemble"]
    par_id = {k["id"]: k for k in ks}
    date_rpps = ctx.get("date_rpps")
    rpps = f"Sources : répertoire RPPS{(' du ' + date_rpps) if date_rpps else ''}, recensement de l'INSEE. Licence Ouverte 2.0."
    vus_lim = set()

    def ligne(l, evol=None, s=None):
        r = dict(l)
        i = l.get("id")
        k = par_id.get(i) if i else None
        r["ancre"] = ancre(i) if i else None
        r["k"] = None
        if k:
            lim_ligne = ((l.get("limite") or {}).get("court") or "")
            lim_k = k.get("limite") or k["pourquoi"].get("limite")
            r["k"] = {"phrase": phrase_seule(k, ens), "calcul": k["pourquoi"]["calcul"], "source": k["pourquoi"]["source"],
                      "carte": i, "titre": k["titre"], "attendu": k.get("attendu") or "",
                      # la limite du constat reste visible sur la ligne, quand la ligne ne la porte pas déjà
                      "limite": lim_k if lim_k and lim_k not in lim_ligne and lim_k not in vus_lim else None}
            if lim_k:
                vus_lim.add(lim_k)
        r["tuile"] = i in TUILES
        # la phrase de lecture des douze indicateurs de « En bref » reste visible sous leur ligne (règle de la partie 6 :
        # une phrase de lecture ne se replie pas ; validé par Lucas le 31 octobre 2026)
        r["phrase_visible"] = bool(k)
        r["mais"] = mais(l.get("e"), l.get("pos_txt"), l.get("kind"), l.get("e_mots"), l.get("code"), l.get("txt"), l.get("ref_txt"))
        ecrit = l.get("kind") in ("prof", "lieux") and bool(l.get("e_txt")) and l.get("code") not in ("aucun", "petit")
        r["avant"] = AF.avant_position(l.get("e_mots"), ecrit, r["mais"], l.get("ref_txt"), l.get("kind"), l.get("txt"))
        r["avant_ecart"] = ecrit
        r["att"] = x["attendu"].get(i)
        r["evol"] = evol
        r["s"] = s
        return r

    def avec_evolution(lignes, serie):
        """L'évolution depuis 2016 (DREES) posée sur la ligne de la profession ; une profession que seule la DREES suit
        (gynécologues, ophtalmologues) garde sa ligne, sans effectif ni taux du répertoire."""
        par_nom = {e["lib"].split(",")[0]: e for e in serie}
        out, pris = [], set()
        for l in lignes:
            e = par_nom.get(l["lib"]) if not l.get("sous") else None
            if e:
                pris.add(e["lib"])
            out.append(ligne(l, e))
        for e in serie:
            if e["lib"] not in pris:
                out.append({"lib": e["lib"], "txt": None, "statut": "suivie seulement par la DREES", "evol": e, "k": None,
                            "id": None, "ancre": None, "seule_drees": True})
        return out

    ev = f.get("evolution") or {}
    ev_ou = ev.get("ou")
    lire_evol = ("Professionnels pour 10 000 habitants au 1er janvier, pour 100 000 pour une profession rare comme sur sa "
                 "ligne, d'après les séries de la DREES"
                 + (f", pour le département ({ev_ou})" if ev_ou else "") + ", de la première à la dernière année. Une densité "
                 "peut baisser alors que le nombre de professionnels augmente, si la population augmente plus vite. Ces "
                 "densités peuvent différer de celles du tableau, qui comptent une personne dans chaque territoire où elle "
                 "exerce ; les séries de la DREES comptent chaque professionnel une seule fois, dans le département de son "
                 "activité principale, et les populations des trois dernières années sont provisoires. Les psychologues, les "
                 "infirmiers et les autres professions du répertoire ADELI ne figurent pas dans ces séries, qui changent de "
                 "source en 2024.")
    src_evol = "DREES, démographie des professionnels de santé ; INSEE, estimations de population. Licence Ouverte 2.0."

    # -- santé mentale
    g_sm = [{"titre": "Professionnels de la santé mentale", "id": "t-sm-pro", "quoi": "Profession", "unite": "Taux",
             "avec_eff": True, "unites": True, "cle": True,
             "lire": "Le taux porte son unité : une profession rare se lit pour 100 000 habitants. « Dont libéraux » compte "
                     "ceux qui exercent en cabinet. L'écart à l'ensemble suit la valeur ; sous 5 inscrits, aucun écart n'est "
                     "calculé.", "lire_evol": lire_evol if ev.get("sm") else "",
             "source": rpps + (" " + src_evol if ev.get("sm") else ""),
             "lignes": avec_evolution(f["sm_pro"], ev.get("sm") or []), "evol": bool(ev.get("sm")),
             "contraire": f["contraire"].get("sm_pro")},
            {"titre": "Structures de soins psychiques", "id": "t-sm-str", "quoi": "Type de structure", "eff_titre": "Inscrites",
             "unite": "Pour 100 000", "avec_eff": True,
             "lire": "Une structure est comptée là où les patients sont reçus. Le taux se rapporte à tous les habitants, et "
                     "pour les structures pour enfants aux moins de 15 ans. Confirmée, d'après la liste de l'établissement, une autre source publique, la HAS ou "
                     "Sirene ; « recoupée » quand la statistique annuelle des établissements (SAE) confirme leur nombre, pas "
                     "leur adresse ; « sans source de confirmation » quand aucune liste publique ne couvre ce type ; un type "
                     "mal recensé s'écrit « non recensé ».",
             "source": "Sources : FINESS et Répertoire opérationnel des ressources. Licence Ouverte 2.0. " + ctx["confiance_france"],
             "limite": ctx.get("limite_sae"), "reserves": f["reserves_structures"],
             "lignes": [ligne(s["ligne"], s=s) for s in f["structures"]], "contraire": f["contraire"].get("structures")},
            {"titre": "Distance à la structure la plus proche", "id": "t-sm-dist", "quoi": "Structure", "unite": "Médiane, km",
             "avec_eff": False,
             "lire": f"La moitié des habitants vit plus près que la distance donnée. L'ensemble est la distance médiane de "
                     f"tous les habitants des {niv} ; une distance n'a ni écart ni couleur de jugement.",
             "source": "Sources : FINESS et Répertoire opérationnel des ressources, à vol d'oiseau depuis le centre de la "
                       "commune. Licence Ouverte 2.0.",
             "lignes": [ligne(l) for l in f["sm_dist"]]}]
    au_dep = lv == "epci"
    if f["sm_recours"]:
        a_valeur = any(l.get("txt") for l in f["sm_recours"])
        g_sm.append({"titre": "Recours aux soins", "id": "t-sm-rec", "quoi": "Indicateur", "unite": "Pour 100 000 hab.",
                     "avec_eff": False, "au_dep": au_dep,
                     "nd": (f"Ces taux ne sont publiés que par département. Voici ceux du département, {f['parent']}, "
                            "situé parmi les départements.") if au_dep else None,
                     "note": None if au_dep else f["phrases"]["recours"],
                     "lire": "Taux standardisés sur l'âge, publiés par département et situés parmi les départements. Ils "
                             "décrivent des habitants, ils ne mesurent ni un besoin de soins ni la qualité de l'offre.",
                     "source": f["source_recours"], "lignes": [ligne(l) for l in f["sm_recours"]] if a_valeur else []})
    if f["sae"]:
        g_sm.append({"titre": "Psychiatrie à l'hôpital", "id": "t-sm-sae", "quoi": "Indicateur et unité", "unite": "Valeur",
                     "avec_eff": False, "au_dep": au_dep,
                     "nd": ("La statistique annuelle des établissements n'est publiée que par département : ces chiffres "
                            "sont ceux de son département, situé parmi les départements.") if au_dep else None,
                     "note": None if au_dep else (f"Lits, places, CMP, personnels et patients suivis des établissements "
                                                  f"autorisés en psychiatrie, situés parmi les {niv}."),
                     "lire": "Le total est déclaré par les établissements autorisés en psychiatrie dont le siège est dans le "
                             "territoire, en équivalents temps plein pour les personnels. Un territoire voisin peut accueillir "
                             "une partie de ses habitants.",
                     "source": "Sources : DREES, statistique annuelle des établissements de santé (SAE). Licence Ouverte 2.0.",
                     "pli_tel": True,   # replié au téléphone, son titre et sa lecture restent visibles (relecture, m11)
                     "lignes": [ligne(l) for l in f["sae"]]})
    ph = f["phrases"]
    sm = {"id": "sm", "nom": "Santé mentale", "groupes": g_sm, "ouvert_tel": True,
          "synthese": [(ph["sm_pro"], ph.get("sm_pro_liste")), (ph["structures"], False), (ph["sm_dist"], False)],
          "autres": f["sm_autres"], "autres_n": f["sm_autres_n"], "exercice": (f.get("exercice") or {}).get("sm"),
          "exercice_qui": "les psychiatres et les psychologues"}
    # -- offre de soins
    g_sa = [{"titre": "Professionnels de santé", "id": "t-sa-pro", "quoi": "Profession", "unite": "Taux", "avec_eff": True,
             "unites": True, "cle": True,
             "lire": "Chaque profession se lit seule, jamais additionnée aux autres. Mêmes repères, réglettes et couleurs que "
                     "pour la santé mentale.", "lire_evol": lire_evol if ev.get("sante") else "",
             "source": rpps + (" " + src_evol if ev.get("sante") else ""),
             "lignes": avec_evolution(f["sante_pro"], ev.get("sante") or []), "evol": bool(ev.get("sante")),
             "contraire": f["contraire"].get("sante_pro")},
            {"titre": "Distance au service d'urgences et à la maison de santé", "id": "t-sa-dist", "quoi": "Structure",
             "unite": "Médiane, km", "avec_eff": False,
             "lire": "À vol d'oiseau, depuis le centre de la commune des habitants, médiane des habitants. Ce n'est pas un "
                     "temps de trajet.",
             "source": "Sources : FINESS et Répertoire opérationnel des ressources. Licence Ouverte 2.0.",
             "lignes": [ligne(l) for l in f["sante_dist"]]}]
    sa = {"id": "sante", "nom": "Offre de soins", "groupes": g_sa,
          "synthese": [(ph["sante_pro"], ph.get("sante_pro_liste")), (ph["sante_dist"], False)],
          "autres": [], "autres_n": 0, "exercice": (f.get("exercice") or {}).get("sante"),
          "exercice_qui": "les médecins généralistes"}
    out = [sm, sa]
    from .fiche_territoire import synthese_offre
    for b, quoi in ((sm, "professions et structures"), (sa, "professions")):
        c = synthese_offre([l for g in b["groupes"] for l in g["lignes"]], quoi)
        b["n_ecarts"], b["compte"] = c["haut"] + c["bas"], c["phrase"]
    # -- contexte, un domaine par bande
    for d in f["autour"]:
        # le comptage du contexte suit une autre règle (la marge seule, sans hasard) : il reste dans la bande, la barre
        # des domaines ne le montre pas à côté des écarts nets de l'offre (relecture, M5)
        out.append({"id": d["id"], "nom": d["nom"], "contexte": True, "synthese": [], "compte": d["synthese"],
                    "n_ecarts": None, "vide": not d["rows"], "lire_dom": d["lire"] if d["rows"] else "",
                    "groupes": [{"titre": "Indicateurs phares", "id": f"t-{d['id']}", "quoi": "Indicateur, unité et année",
                                 "unite": "Valeur", "avec_eff": False, "lignes": [ligne(l) for l in d["phares"]]}] if d["rows"] else [],
                    "autres": [{"nom": "Autres indicateurs du domaine", "rows": d["autres"]}] if d["autres"] else [],
                    "autres_n": sum(1 for r in d["autres"] if not r.get("sous")), "venir": ctx["venir"].get(d["id"]) or []})
    # cartes de bloc : les petites cartes des constats de la bande, une seule montrée à la fois
    for b in out:
        ids = [l.get("id") for g in b["groupes"] for l in g["lignes"]]
        b["cartes"] = []
        for k in ks:
            if k["id"] not in ids:
                continue
            svg = x["cartes_france"].get(k["id"]) or k.get("carte")
            if svg:
                b["cartes"].append({"id": k["id"], "nom": k["nom_ind"], "svg": svg, "cases": k["cases"], "bornes": k["bornes"],
                                    "unite_leg": k["unite_leg"], "lv": k["lv"], "france": k["id"] in x["cartes_france"],
                                    "situe": "" if k["id"] in x["cartes_france"] else (k.get("situe") or "")})
        # le nom court dans le choix de la carte, avec ce qu'il mesure quand deux indicateurs portent le même nom (« CMP
        # pour adultes » en densité et en distance ; relecture du 1er novembre 2026, mineur 6)
        courts = [c["nom"].split(", ")[0] for c in b["cartes"]]
        for c, n in zip(b["cartes"], courts):
            c["choix"] = n if courts.count(n) == 1 else (n + ", distance" if c["id"].startswith("dist_") else n + ", nombre pour 100 000"
                                                          if c["id"].startswith("lieux_") else c["nom"])
        b["versions"] = [{"nom": (k.get("nom_ind") or k["nom"]).split(",")[0], "serie": k["serie"]} for k in ks if k["serie"] and k["id"] in ids]
        b["a_venir_ic"] = any(par_id[i]["intervalle"] for i in ids if i in par_id)
        b["att"] = any(l.get("att") for g in b["groupes"] for l in g["lignes"])
    from .fiche_territoire import ecart_contraire
    for j, b in enumerate(out):
        b["num"] = f"{j + 1:02d}"
        b["court"] = COURT.get(b["id"], b["nom"])
        # sous chaque tableau, la clé du « mais » que montrent ses lignes, distances et contexte compris (relecture v2)
        for g in b["groupes"]:
            g["contraire"] = AF.cle_contraire(ecart_contraire(g["lignes"]), f["niveau"])
    return out


def phares_absents(ks: list) -> list[str]:
    """Les indicateurs phares (constats.CANDIDATS) sans donnée publiée pour le territoire, nommés : « En bref » annonçait
    douze indicateurs là où 152 fiches en ont moins (relecture des fiches construites du 1er novembre 2026, mineur 1)."""
    from .constats import CANDIDATS, NOM_COURT
    vus = {k["id"] for k in ks}
    out = []
    for _s, ident, plur, _sing, _g in CANDIDATS:
        if ident in vus:
            continue
        nom = NOM_COURT.get(ident) or plur
        out.append(f"{nom} (distance)" if ident.startswith("dist_") else f"{nom} (nombre)" if ident.startswith("lieux_") else nom)
    return out


def tableau_de_bord(ctx: dict) -> list[dict]:
    """« En bref » en matrice : les constats, liste fixe dans l'ordre d'un diagnostic (constats.CANDIDATS), groupés par
    section, chacun avec sa valeur, sa réglette et sa position."""
    f, ks = ctx["f"], ctx["constats"]
    sections = []
    for k in ks:
        if not sections or sections[-1]["nom"] != k["section_nom"]:
            sections.append({"nom": k["section_nom"], "lignes": []})
        c = k["cel"]
        pos = c["pos_txt"] or ""
        nom, _, unite = (k.get("nom_ind") or k["nom"]).partition(", ")
        sections[-1]["lignes"].append({
            "nom": nom, "unite": unite or k["unite"], "id": k["id"], "ancre": ancre(k["id"]), "dep": k["echelle"] == "dep",
            "v": c["v_txt"] if c["v"] is not None and c["statut"] != "aucun" and not (c["kind"] == "dist" and AF.distance_nulle(c["v_txt"])) else None,
            "statut": AF.DANS_COMMUNE if c["kind"] == "dist" and c["v"] is not None and AF.distance_nulle(c["v_txt"]) else (c["statut_txt"] or "non publié"),
            "km": c["kind"] == "dist", "reglette": k["reglette"],
            "mais": mais(c["e"], pos, c["kind"], c["e_mots"], c["statut"], c["v_txt"], c["ref_txt"]),
            # l'écart en mots, comme dans les tableaux, pour que « mais » s'appuie sur lui
            "ecart": c["e_mots"] if c["kind"] in ("prof", "lieux") and c["e_mots"] and c["statut"] not in ("aucun", "petit") else "",
            "avant": AF.avant_position(c["e_mots"], c["kind"] in ("prof", "lieux") and c["statut"] not in ("aucun", "petit"),
                                       mais(c["e"], pos, c["kind"], c["e_mots"], c["statut"], c["v_txt"], c["ref_txt"]),
                                       c["ref_txt"], c["kind"], c["v_txt"]),
            "couleur": c["couleur"],
            # la position dit toujours son ensemble, en entier (remarque de Lucas du 31 octobre 2026)
            "pos": pos})
    return sections


def carte_france(F, lv: str, code: str, vals: dict, bornes: list, cadre: tuple, titre: str, valeur=None) -> str:
    """Carte de bloc d'un département d'outre-mer : toute la France et ses encarts, faute de voisins à son niveau ; son
    encart, petit à cette échelle, est entouré d'un cercle qui le fait trouver."""
    bx = F.boite(lv, code)
    r = max(bx[2] - bx[0], bx[3] - bx[1]) / 2 + (cadre[2] - cadre[0]) / 40
    cercle = (f'<circle cx="{(bx[0] + bx[2]) / 2:.1f}" cy="{(bx[1] + bx[3]) / 2:.1f}" r="{r:.1f}" fill="none" '
              'stroke="var(--choisi, #1C2028)" stroke-width="2" vector-effect="non-scaling-stroke" class="reperage-encart"/>')
    return CP.mini_carte(F, lv, code, vals, bornes, cadre, titre, valeur=valeur).replace("</svg>", cercle + "</svg>")


def carte_region(F, code: str, deps: list, vals: dict, bornes: list, genre: str, noms: dict) -> dict:
    """Carte des départements d'une région, en classes de même effectif des psychologues parmi tous les départements
    (mêmes classes que les petites cartes), chaque département lié à sa fiche, la région cernée ; elle remplace la
    silhouette vide de la carte du territoire."""
    from .fiche_territoire import bornes_legende
    cadre = CP.cadre_autour([F.boite("dep", d) for d in deps], .06, 1.1)
    x0, y0, x1, y1 = cadre
    s = [f'<svg class="carte-svg plan region-deps" viewBox="{x0:.2f} {y0:.2f} {x1 - x0:.2f} {y1 - y0:.2f}" role="img" '
         f'aria-label="Départements de la région, psychologues pour 10 000 habitants, en cinq classes de même effectif">'
         '<g class="aplats" stroke="var(--contour, #F4F4F1)" stroke-width=".8">']
    for c in F.dans("dep", cadre):
        if c not in deps:
            s.append(F.forme("dep", c, fill="var(--nodata, #E6E6E9)", fill_opacity=".6"))
    for c in deps:
        v = vals.get(c)
        cl = "nd" if v is None else f"q{CP.PALIERS[len(bornes) + 1][sum(1 for b in bornes if v >= b)]}"
        t = f"{noms.get(c, c)} : {AF.nombre(v, 'taux')} psychologues pour 10 000 habitants" if v is not None else noms.get(c, c)
        s.append(f'<a href="../dep/{c}.html" aria-label="{t}"><title>{t}</title>{F.forme("dep", c, **{"class": cl})}</a>')
    s.append("</g>")
    s.append(CP.lisere(F, "reg", code))
    s.append(F.forme("reg", code, fill="none", stroke="var(--choisi, #1C2028)", stroke_width="2.5", **{"class": "choisi"}))
    s.append("</svg>")
    n = len(bornes) + 1
    return {"svg": "".join(s), "cases": CP.legende_classes(bornes),
            "bornes": [(t, f"{100 * (j + 1) / n:.2f}%") for j, t in enumerate(bornes_legende(bornes, genre))],
            "deps": [(c, noms.get(c, c)) for c in deps]}
