"""Pages par domaine (présentation du 30 octobre 2026, maquette a-sante-mentale validée).

Au centre, l'offre de soins, en deux pages qui ne s'additionnent jamais : santé mentale et santé. Chacune est faite de
questions, chaque question reprend la section du rapport national qui y répond, déjà vérifiée : le résultat d'abord, la
figure avec ses variantes par profession (« Faire varier »), le lien qui la règle dans Explorer ou l'atlas, le « Comment
lire », puis les chiffres détaillés et la méthode repliés. Aucun chiffre n'est calculé ici, tout est relu dans les
rapports de la version (rapport_sante_mentale.md, rapport_sante.md) et leurs figures (graphiques/).

Autour, une page pour chacun des sept domaines : pourquoi il compte pour l'accès aux soins, la répartition des
territoires pour ses indicateurs phares (une figure, une variante par indicateur, comme les fiches des indicateurs), la
question préparée de l'atelier « Croiser », tous ses indicateurs avec leur fiche et les bases à venir.
"""
import re
from pathlib import Path

from . import domaines as D
from .fiche_indicateur import NOMS, de, repartition

# questions du centre : titre de la question, intertitre du rapport, figures reprises de la section, autre page utile ;
# « -⁠ils », gardé sur une ligne au téléphone par un gluon invisible (audit du 6 novembre 2026)
QUESTIONS = {
    "sm": [
        ("Combien de professionnels, et où exercent-⁠ils ?", "Les professions de santé mentale", ["carte_dep_sm", "lorenz_sm"], None),
        ("Qui est compté dans les densités ?", "Du répertoire aux densités", ["parcours_sm"], None),
        ("L’offre suit-elle le niveau de vie des habitants ?", "Offre selon le niveau de vie des territoires", ["escalier_sm"], None),
        ("À quelle distance sont les structures de soins psychiques ?", "Distance aux structures de soins selon le niveau de vie et le type de territoire", ["eloignement_sm"],
         ("zone.html", "Autour d’un lieu, les structures de votre zone")),
        ("Quelle accessibilité, au-delà de la distance ?", "Distance et accessibilité", ["distance_sm"], None),
        ("Quels territoires s’écartent plus que le hasard ?", "Écarts qui dépassent le hasard", ["entonnoir_sm"], None),
        ("L’offre suit-elle le profil des habitants ?", "Liens avec le profil des habitants", ["effet_ville_sm"],
         ("croiser.html", "Croiser librement deux indicateurs")),
        ("L’offre est-elle là où les indicateurs de recours sont élevés ?", "Offre face aux indicateurs de besoin", ["quadrants_sm"],
         ("croiser.html", "Croiser librement deux indicateurs")),
        ("Qui porte l’offre ?", "Qui porte l'offre", ["porte_sm"], None),
        ("Où trouve-t-on une profession sans l’autre ?", "Quelles professions sont présentes ensemble", ["combinaisons_sm"], None),
        ("De l’offre aux consommations en addictologie", "Consommations d'alcool et de tabac, par région", ["addicto_regions"], None),
    ],
    "sante": [
        ("Combien de professionnels, et où exercent-⁠ils ?", "Les professions de santé", ["carte_dep_sante", "lorenz_sante"], None),
        ("Qui est compté dans les densités ?", "Du répertoire aux densités", ["parcours_sante"], None),
        ("L’offre suit-elle le niveau de vie des habitants ?", "Offre selon le niveau de vie des territoires", ["escalier_sante"], None),
        ("À quelle distance sont les structures de soins ?", "Distance aux structures de soins selon le niveau de vie et le type de territoire", ["eloignement_sante"],
         ("zone.html#fam=sante", "Autour d’un lieu, les structures de votre zone")),
        ("Quelle accessibilité, au-delà de la distance ?", "Distance et accessibilité", ["distance_sante"], None),
        ("Quels territoires s’écartent plus que le hasard ?", "Écarts qui dépassent le hasard", ["entonnoir_sante"], None),
        ("L’offre suit-elle le profil des habitants ?", "Liens avec le profil des habitants", ["effet_ville_sante"],
         ("croiser.html", "Croiser librement deux indicateurs")),
        ("Qui porte l’offre ?", "Qui porte l'offre", ["porte_sante"], None),
    ],
}
PAGES_CENTRE = {"sm": ("sante-mentale", "Santé mentale", "rapport_sante_mentale.md", "sante-mentale",
                       "Psychologues, psychiatres et structures de soins psychiques, rapportés aux habitants et croisés avec leur profil. Les professions de santé générale sont sur la page Santé, jamais additionnées à celles-ci."),
                "sante": ("sante", "Santé", "rapport_sante.md", "sante",
                          "Médecins, autres professions de santé et structures de soins, rapportés aux habitants et croisés avec leur profil. Les professions de santé mentale ont leur propre page, jamais additionnées à celles-ci.")}


def sections(md: str) -> dict[str, list[str]]:
    """Lignes de chaque section du rapport, de son intertitre au suivant, quel que soit son niveau."""
    out, titre, lignes = {}, None, []
    for l in md.split("\n"):
        if l.startswith("#"):
            if titre and titre not in out:
                out[titre] = lignes
            titre, lignes = l.lstrip("#").strip(), []
        else:
            lignes.append(l)
    if titre and titre not in out:
        out[titre] = lignes
    return out


def decouper_savoir(bloc: str) -> list[str]:
    """Un « À savoir » qui mêle plusieurs sujets devient un encadré par sujet, Mayotte à part, les sources en note
    (audit de contrôle du 30 octobre 2026, F10)."""
    import re as _re
    texte = bloc.replace("**À savoir.**", "").strip()
    phrases = [x.strip() for x in _re.split(r"(?<=[.])\s+(?=[A-ZÀÂÉÈÊÎÔÛÇ0-9])", texte) if x.strip()]
    mayotte = [x for x in phrases if "Mayotte" in x]
    sources = [x for x in phrases if x.startswith("Sources")]
    reste = [x for x in phrases if x not in mayotte and x not in sources]
    out = []
    if reste:
        out.append("**À savoir.** " + " ".join(reste))
    if mayotte:
        out.append("**À savoir, Mayotte.** " + " ".join(mayotte))
    if sources:
        out.append('<div class="sources-note" markdown="1">\n\n' + " ".join(sources) + "\n\n</div>")
    return out or [bloc]


def morceaux(lignes: list[str], figures: list[str]) -> dict:
    """Le résultat (premier paragraphe), les figures retenues, le lien « Faire varier », le « Comment lire » et le reste,
    replié sous la figure. Les « À savoir » restent visibles, ce sont les limites. Les autres figures de la section ne
    sont pas reprises, le rapport les garde."""
    blocs, cur = [], []
    for l in lignes + [""]:
        if l.strip() == "" and cur and not (cur[0].startswith("<details") and not any(x.startswith("</details") for x in cur)):
            blocs.append("\n".join(cur))
            cur = []
        elif l.strip() or cur:
            cur.append(l)
    resultat, varier, lire, savoir, reste, vu_figure = None, [], None, [], [], False
    for b in blocs:
        b0 = b.lstrip()
        m = re.match(r"<!--GRAPHIQUE (\S+)-->", b0)
        if m:
            vu_figure = True
            continue
        # une section qui s'ouvre sur un tableau (effectifs des professions) le garde comme résultat
        if resultat is None and not vu_figure and b0.startswith("|"):
            resultat = b0
            continue
        if "faire-varier" in b0:
            varier.append(b0)
        elif b0.startswith("**Comment lire.**"):
            lire = lire or b0
        elif b0.startswith("**À savoir.**"):
            savoir.append(b0)
        elif resultat is None and not b0.startswith(("<", "|", "!", "*", "-")):
            resultat = b0
        else:
            reste.append(b0)
    return {"resultat": resultat or "", "figures": [f for f in figures if any(f"GRAPHIQUE {f}-->" in x for x in lignes)],
            "varier": varier, "lire": lire, "savoir": [x for b in savoir for x in decouper_savoir(b)], "reste": reste}


def liens_du_domaine(L: dict, dom: str) -> dict:
    """Liens des indicateurs d'un domaine avec les professions, par intercommunalité à densité de population égale,
    ou par département quand l'indicateur n'existe pas par intercommunalité, selon la règle unique du lien."""
    from .regle_lien import est_lien
    lignes = [l for l in L["lignes"] if l["dom"] == dom]
    sortie, testes = [], 0
    for l in lignes:
        for niv in ("epci", "dep"):
            cases = [(c, L["cases"][niv].get(f"{c['id']}|{l['id']}")) for fam in ("sm", "sante") for c in L["colonnes"][fam]]
            cases = [(c, x) for c, x in cases if x]
            if not cases:
                continue
            testes += 1
            ok = sorted([(c, x) for c, x in cases if est_lien(x[4], x[7])], key=lambda cx: -abs(cx[1][4]))
            if ok:
                sortie.append({"l": l, "niv": niv, "liens": [{"lab": c["lab"], "court": c.get("court") or c["lab"], "r": x[4]} for c, x in ok[:6]],
                               "n": len(ok)})
            break
    sortie.sort(key=lambda o: -abs(o["liens"][0]["r"]))
    return {"lignes": sortie, "testes": testes, "fort": sortie[0] if sortie else None}


def _rendre(md_html, texte: str, graphiques: Path, donnees: dict) -> str:
    """Markdown du rapport en HTML, figures comprises, chaque tableau dans un cadre qui défile sur téléphone."""
    html = md_html(texte, graphiques, donnees=donnees)[1]
    return re.sub(r"(<table.*?</table>)", r'<div class="defile">\1</div>', html, flags=re.S)


def construire(env, commun: dict, A: dict, sd: dict, dernier: Path, site: Path, registre: Path, doi: str | None,
               fiches: dict) -> list[Path]:
    from .site import _ancre, md_html
    dossier = site / "domaine"
    dossier.mkdir(parents=True, exist_ok=True)
    graphiques = dernier / "graphiques"
    donnees = {"prefixe": f"../donnees/{dernier.name}/", "dossier": dernier}
    pages = []
    for cle, (nom_page, titre, rapport, page_rapport, chapeau) in PAGES_CENTRE.items():
        f = dernier / rapport
        if not f.exists():
            continue
        secs = sections(f.read_text(encoding="utf-8"))
        qs = []
        for k, (question, intertitre, figs, autre) in enumerate(QUESTIONS[cle]):
            if intertitre not in secs:
                continue
            m = morceaux(secs[intertitre], figs)
            haut = "\n\n".join([m["resultat"]] + [f"<!--GRAPHIQUE {x}-->" for x in m["figures"]] + m["varier"]
                               + ([m["lire"]] if m["lire"] else []) + m["savoir"])
            html = _rendre(md_html, haut, graphiques, donnees)
            preuve = _rendre(md_html, "\n\n".join(m["reste"]), graphiques, donnees) if m["reste"] else ""
            # liens du rapport ramenés à la place de la page (figures titrées sans numéro, 1er novembre 2026)
            html, preuve = (h.replace('href="../../', 'href="../') for h in (html, preuve))
            # pronom inversé jamais séparé de son verbe en fin de ligne (« trouve-t-on », « exercent-ils »), par un gluon
            # invisible après chaque trait d'union (contre-audit du 6 novembre 2026)
            question = re.sub(r"-(?!⁠)(?=(?:t-)?(?:ils?|elles?|on)|t-)", "-⁠", question)
            qs.append({"id": f"q{k + 1}", "question": question, "html": html, "preuve": preuve, "autre": autre,
                       "section": f"../rapports/{dernier.name}/{page_rapport}.html#{_ancre(intertitre, '-')}"})
        # bases à venir de l'offre (et du recours pour la santé mentale), rangées selon qu'elles parlent de santé mentale
        sm_mot = re.compile(r"psy|mentale|secteur|suicid|addict", re.I)
        venir = [n for d, ns in D.bases_a_venir(registre).items() for n in ns
                 if (d == "offre" or (cle == "sm" and d == "recours")) and bool(sm_mot.search(n)) == (cle == "sm")]
        cit = f"{commun['citation_auteur']} ({commun['annee_version']}). {titre}, questions et figures. Ubi Cura, version du {commun['date_longue']}" + (f", doi:{doi}" if doi else "")
        html = env.get_template("page_domaine.html").render(dict(
            commun, racine="../", page="offre", titre=titre, classe_main="domaine", centre=True, cle=cle, chapeau=chapeau,
            questions=qs, venir=venir, citation=cit, rapport=f"../rapports/{dernier.name}/{page_rapport}.html",
            description=f"{titre}, les questions principales, chacune avec son résultat, sa figure et sa méthode."))
        (dossier / f"{nom_page}.html").write_text(html, encoding="utf-8")
        pages.append(dossier / f"{nom_page}.html")

    # l'entrée « Offre de soins », qui mène aux deux familles sans jamais les additionner (audit de contrôle du
    # 30 octobre 2026, point I3)
    centre = next(d for d in D.DOMAINES if d.get("centre"))
    html = env.get_template("page_domaine.html").render(dict(
        commun, racine="../", page="offre", titre=centre["nom"], classe_main="domaine", centre=False, porte=True,
        d=centre, chapeau=centre["pourquoi"], citation=None,
        description="L'offre de soins, en santé mentale et en santé, au centre des sept domaines du site."))
    (dossier / "offre-de-soins.html").write_text(html, encoding="utf-8")
    pages.append(dossier / "offre-de-soins.html")

    # matrice des liens, une fois pour les sept domaines
    from .cartes_presentation import choroplethe
    from .liens import donnees as donnees_liens
    Lm = donnees_liens(sd, dernier, dernier.name, doi, fiches)

    # les sept domaines autour de l'offre
    inds = {e["id"]: e for e in A["ind"]}
    venir = D.bases_a_venir(registre)
    from .portail import catalogue
    cat = catalogue(sd)
    # repère calculé une seule fois (affichage.Affichage), le même que la fiche, Comparer et l'atlas : ensemble des
    # territoires pondéré par la population, ou territoire médian selon l'indicateur (audit du 6 novembre 2026, une
    # moyenne simple des territoires s'écrivait ici « repère » et différait des autres pages)
    from . import affichage as AF
    T = AF.Affichage(sd, dernier)
    for d in D.DOMAINES:
        if d.get("centre"):
            continue
        variantes = []
        for pid in d.get("phares", []):
            e = inds.get(pid)
            if not e or not e["niv"]:
                continue
            lv = "epci" if "epci" in e["niv"] else "dep" if "dep" in e["niv"] else "reg"
            S = T.serie(pid, lv)
            if S is None or S.ref is None:
                continue
            r = repartition(S.v, S.ref, NOMS[lv][1], e.get("u") or "", S.genre)
            svg = r["svg"].replace("<svg ", f'<svg data-variante="{e["lab"]}" ', 1)
            variantes.append({"svg": svg, "lab": e["lab"], "u": e.get("u") or "", "nom": NOMS[lv][1], "de": de(NOMS[lv][1]),
                              "q1": r["q1"], "q3": r["q3"], "rep": S.ref, "rep_lib": S.ref_lib(), "genre": S.genre,
                              "fiche": fiches.get(pid), "src": e.get("src"), "an": e.get("an")})
        mes = [i for i in cat if i["domaine"] == d["id"]]
        for i in mes:
            i["fiche"] = fiches.get(i["id"], "")
        # gabarit commun (audit de contrôle du 30 octobre 2026, point I4) : phrase de réponse et bloc « Ce domaine et
        # l'offre de soins » tirés de la matrice des liens, carte d'un indicateur phare, indicateurs, bases à venir
        liens_dom = liens_du_domaine(Lm, d["id"])
        carte, carte_ind = None, None
        for pid in d.get("phares", []):
            e = inds.get(pid)
            if e and "dep" in e["niv"]:
                carte = choroplethe(A, "dep", pid, e["lab"], e.get("u") or "")
                carte_ind = {"lab": e["lab"], "u": e.get("u") or "", "fiche": fiches.get(pid), "id": pid}
                break
        cit = f"{commun['citation_auteur']} ({commun['annee_version']}). {d['nom']}. Ubi Cura, version du {commun['date_longue']}" + (f", doi:{doi}" if doi else "")
        html = env.get_template("page_domaine.html").render(dict(
            commun, racine="../", page="domaines", titre=d["nom"], classe_main="domaine", centre=False, d=d,
            chapeau=d["pourquoi"], variantes=variantes, croiser=d.get("croiser"), liens_dom=liens_dom, carte=carte,
            carte_ind=carte_ind, n_ind=len(mes),
            par_sous=[(so, [i for i in mes if i["sous"] == so]) for so in d["sous"]], venir=venir.get(d["id"], []),
            citation=cit, description=f"{d['nom']}, ses indicateurs autour de l'offre de soins, leur répartition et les bases à venir."))
        (dossier / f"{d['id']}.html").write_text(html, encoding="utf-8")
        pages.append(dossier / f"{d['id']}.html")
    return pages
