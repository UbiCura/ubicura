"""Contrôle du site construit face aux décisions de Lucas (docs/decisions_a_verifier.md), sur toutes les pages et tous
les rapports, et non sur un échantillon (demande de Lucas du 6 novembre 2026 : les audits trouvaient chaque fois
d'autres défauts, la machine les cherche désormais partout à chaque construction).

    python outils/controle_decisions.py            # dernier site construit, code de sortie 1 s'il reste un défaut

Chaque contrôle dit « ok » ou le nombre de défauts, avec trois exemples. Les versions archivées (rapports et
territoires d'avant la dernière date) restent telles qu'elles ont été publiées et ne sont pas jugées. Le contrôle lit
le site, les rapports Markdown et le texte des deux PDF nationaux ; il ne recalcule aucun chiffre depuis les sources
(c'est le rôle de outils/controle_independant.py)."""
from __future__ import annotations

import collections
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from pipeline import config  # noqa: E402
from pipeline.affichage import nombre, unite_prof  # noqa: E402
from pipeline.libelles import termes_proscrits  # noqa: E402

SITE = RACINE / "site"
# menu à sept entrées depuis le 8 novembre 2026 (Explorer entre Comparer et Croiser, version A validée sur captures)
MENU = ["Offre de soins", "Domaines", "Territoires", "Comparer", "Explorer", "Croiser", "Méthode et données"]
# entrée du menu allumée selon la page (gabarits/nav.html)
MENU_ATTENDU = {"comparer.html": "Comparer", "croiser.html": "Croiser", "liens.html": "Croiser", "explorer.html": "Explorer",
                "domaines.html": "Domaines", "methode.html": "Méthode et données", "domaine/offre-de-soins.html": "Offre de soins",
                # les deux pages centre (santé mentale, santé) relèvent de l'offre de soins (pipeline/pages_domaine.py)
                "domaine/sante-mentale.html": "Offre de soins", "domaine/sante.html": "Offre de soins",
                "atlas.html": "Offre de soins", "territoires/index.html": "Territoires"}
ESP = "[\\s  ]"
defauts: dict[str, list] = collections.OrderedDict()


def note(controle: str, liste: list):
    defauts[controle] = liste


class _Texte(HTMLParser):
    """Texte lu par le lecteur, comme le navigateur le découpe (le contenu des scripts et des styles n'en fait pas
    partie, même quand il contient des balises entre guillemets)."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.morceaux, self.cache = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "template"):
            self.cache += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "template") and self.cache:
            self.cache -= 1

    def handle_data(self, data):
        if not self.cache:
            self.morceaux.append(data)


def texte(s: str) -> str:
    # les scripts sont retirés avant la lecture : leurs chaînes contiennent des balises (« <title> ») que l'analyseur
    # prendrait pour du texte
    s = re.sub(r"<script\b[^>]*>.*?</script\s*>|<style\b[^>]*>.*?</style\s*>", " ", s, flags=re.S | re.I)
    t = _Texte()
    t.feed(s)
    return re.sub(r"\s+", " ", " ".join(t.morceaux)).replace("­", "")


def cellules(ligne: str) -> list[str]:
    return [html.unescape(re.sub(r"<[^>]+>", "", c)).replace("­", "").replace(" ", " ").replace(" ", " ").strip()
            for c in re.findall(r"<t[hd][^>]*>.*?</t[hd]>", ligne, flags=re.S)]


def derniers_resultats() -> Path:
    return sorted(p for p in (RACINE / "resultats").glob("20*") if (p / "site_data.json").exists())[-1]


def pages_publiques(date: str) -> list[Path]:
    out = []
    for p in SITE.rglob("*.html"):
        rel = p.relative_to(SITE).as_posix()
        top = rel.split("/")[0]
        if top.startswith("prototype") or top in ("maquettes", "_maquettes") or p.name.startswith("_"):
            continue
        # versions archivées, publiées telles quelles
        m = re.match(r"(rapports|territoires)/(\d{4}-\d{2}-\d{2})/", rel)
        if m and m.group(2) != date:
            continue
        out.append(p)
    return sorted(out)


def controler() -> int:
    from pipeline.util import marquer_seance
    marquer_seance()
    R = derniers_resultats()
    date = R.name
    sd = json.loads((R / "site_data.json").read_text(encoding="utf-8"))
    pages = pages_publiques(date)
    # le code des scripts n'est pas lu par le lecteur : ses chaînes (« '<title>' + … ») ne sont jamais jugées
    sources = {p: re.sub(r"<script\b[^>]*>.*?</script\s*>", " ", p.read_text(encoding="utf-8"), flags=re.S | re.I)
               for p in pages}
    textes = {p: texte(s) for p, s in sources.items()}
    rel = lambda p: p.relative_to(SITE).as_posix()   # noqa: E731

    # professions rares (règle unique, affichage.unite_prof) et leurs noms, au singulier et au pluriel
    from pipeline.lecture import pluriel
    pop = sd["france"]["pop"]
    rares, communes = set(), set()
    for pr in sd["professions"]:
        n = (sd["france"]["n"].get(pr["id"]) or [None] * 3)[2]
        if not n:
            continue
        noms = {pr["libelle"].lower(), pluriel(pr["libelle"]).lower()}
        (rares if unite_prof(n, pop) == 100000 else communes).update(noms)
    rares -= communes

    # 1. liens internes vers un fichier absent
    casses = []
    for p, s in sources.items():
        for h in set(re.findall(r'(?:href|src)="([^"]+)"', re.sub(r"<script.*?</script>", "", s, flags=re.S))):
            h = html.unescape(h)
            if re.match(r"(https?:|mailto:|data:|javascript:|tel:|#|//)", h) or "${" in h or "{{" in h:
                continue
            chemin = unquote(urlsplit(h).path)
            if chemin and not (p.parent / chemin).resolve().exists():
                casses.append((rel(p), h))
    note("Liens internes vers un fichier absent", casses)

    # 2. menu à six entrées identique, la bonne entrée allumée
    menus = []
    for p, s in sources.items():
        m = re.search(r'<nav class="site".*?</nav>', s, flags=re.S)
        if not m:
            if 'http-equiv="refresh"' not in s and not rel(p).startswith(("atlas_", "explorer/")):
                menus.append((rel(p), "pas de menu"))
            continue
        ent = [html.unescape(re.sub("<[^>]+>", "", x)).strip() for x in re.findall(r'<a class="l[^"]*"[^>]*>.*?</a>', m.group(0), flags=re.S)]
        if ent != MENU:
            menus.append((rel(p), ent))
        on = [html.unescape(x).strip() for x in re.findall(r'<a class="l on"[^>]*>([^<]*)</a>', m.group(0))]
        att = MENU_ATTENDU.get(rel(p)) or ("Territoires" if rel(p).startswith(("territoire/", "territoires/")) else
                                            "Domaines" if rel(p).startswith(("domaine/", "indicateur/")) else None)
        if att and on != [att]:
            menus.append((rel(p), f"allumé {on}, attendu {att}"))
    note("Menu à sept entrées et entrée allumée", menus)

    # 3. mots de programme visibles et code HTML brut affiché au lecteur
    brut = []
    for p, s in sources.items():
        t = textes[p]
        for w in re.findall(r"\b(undefined|NaN|None|nan|null|\[object Object\])\b", t):
            brut.append((rel(p), w))
        for a in re.findall(r'(?:title|aria-label)="([^"]*)"', s):
            if re.search(r"\b(undefined|NaN|None|nan)\b", a):
                brut.append((rel(p), a[:100]))
        for m in re.finditer(r"<title>([^<]*)</title>", s):
            if re.search(r"\b(undefined|NaN|None|nan)\b", m.group(1)):
                brut.append((rel(p), m.group(1)[:100]))
        if re.search(r"<(a|span|div|p|strong|b|i)[\s>]|</(a|span|div|p)>|&lt;|&gt;", t):
            m = re.search(r".{0,50}(<(a|span|div|p|strong|b|i)[\s>]|</(a|span|div|p)>|&lt;|&gt;).{0,50}", t)
            brut.append((rel(p), "code HTML visible : " + m.group(0)))
    note("Mots du programme ou code HTML visibles (undefined, NaN, None, balises)", brut)

    # 3 bis. intitulé laissé sans texte (« Comment lire. » vide dans les groupes d'indicateurs phares des fiches,
    # vu le 10 novembre 2026 sur les captures de la population concernée)
    vides = []
    for p, s in sources.items():
        for m in re.finditer(r"<b>([^<]{2,40}\.)</b>(?:\s|&nbsp;)*</(p|span|div|li)>", s):
            vides.append((rel(p), m.group(1)))
    note("Aucun intitulé sans texte (« Comment lire. » vide)", vides)

    # 3 ter. guillemets français tenus par une espace insécable dans le texte lu : les pages de domaine, d'indicateur
    # et la page Indicateurs s'écrivaient sans la règle des insécables (relecture du 10 novembre 2026, « » et les
    # infirmiers » rejeté en début de ligne sur téléphone)
    from pipeline.typographie import _PROTEGES
    guill = []
    for p, s in sources.items():
        morceaux = _PROTEGES.split(s)
        lu = " ".join(morceaux[i] for i in range(0, len(morceaux), 3))
        m = re.search(r".{0,30}(« | »).{0,30}", lu)
        if m:
            guill.append((rel(p), m.group(0).strip()))
    note("Guillemets français tenus par une espace insécable", guill)

    # 3 quater. une sous-ligne de population concernée garde ses limites là où elle se lit : son tableau dit « à vol
    # d'oiseau » et « pas un temps de trajet » (relecture du 10 novembre 2026, bande santé mentale sans ces limites)
    lim_sous = []
    for p, s in sources.items():
        for t in re.findall(r"<table\b.*?</table>", s, flags=re.S):
            if 'data-ind="distp_' in t and not (re.search(r"vol d(?:'|&#39;|’)oiseau", t) and "temps de trajet" in t):
                lim_sous.append((rel(p), "tableau avec une sous-ligne de population concernée sans ses limites"))
    note("Limites des sous-lignes de population concernée dites dans leur tableau", lim_sous)

    # 3 quinquies. chaque fiche de territoire garde sa carte (« Où les patients sont reçus », « Ses départements ») :
    # construites dans un dossier neuf, les fiches du brouillon du 10 novembre 2026 l'avaient perdue sans bruit, le fond
    # de carte d'Explorer n'y étant pas encore écrit (ne rien perdre, règle 18)
    sans_carte = [(rel(p), "fiche sans sa carte") for p, s in sources.items()
                  if re.match(r"territoire/(dep|reg|epci)/[^/_][^/]*\.html$", rel(p))
                  and not re.search(r'class="carte-svg plan\b', s)]
    note("Chaque fiche de territoire garde sa carte", sans_carte)

    # 3 sexies. relecture indépendante du 11 novembre 2026 : la limite Mayotte d'un seul tenant et ses sources une seule
    # fois (2.1) ; « la l'ensemble » (2.2) ; la petite France annoncée seulement si elle est dessinée (2.6)
    savoir, articles, petite = [], [], []
    for p, s in sources.items():
        r = rel(p)
        for b in re.findall(r"<(?:p|div)\b[^>]*>(.*?)</(?:p|div)>", s, flags=re.S):
            if "recensement exhaustif mené fin 2025" in b and "À Mayotte" not in b:
                savoir.append((r, "phrase de la limite Mayotte séparée de son sujet"))
        if r.startswith("domaine/"):
            src = [texte(x).strip() for x in re.findall(r"<p\b[^>]*>\s*(Sources\b.*?)</p>", s, flags=re.S)]
            vus = set()
            for x in src:
                if x and x in vus:
                    savoir.append((r, "paragraphe de sources écrit deux fois : " + x[:60]))
                vus.add(x)
        for m in re.finditer(r"\b(?:[Dd]e la|[Ll]a|[Ll]e|[Dd]u) l['’][a-zàâçéèêëîïôûùüÿœæ]", textes[p]):
            articles.append((r, textes[p][max(0, m.start() - 30):m.end() + 20]))
        if re.match(r"territoire/", r) and "La petite France situe la carte" in textes[p] and 'class="situer"' not in s:
            petite.append((r, "petite France annoncée, absente"))
    note("Limite Mayotte d'un seul tenant, sources une seule fois", savoir)
    note("Aucun article devant l'article élidé (« de la l'ensemble »)", articles)
    note("Petite France annoncée seulement si elle est dessinée", petite)

    # 3 octies. audit du 12 novembre 2026 : chaque limite de la page Méthode a un nom lisible (« file_active »,
    # « addictions » s'affichaient) ; un seul séparateur des milliers, l'espace fine insécable, dans tout le texte lu
    noms_lim, milliers = [], []
    v_site = max((d.name for d in (SITE / "rapports").iterdir() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.name)), default="")
    for p, s in sources.items():
        r = rel(p)
        for t in re.findall(r'<table class="simple limites">(.*?)</table>', s, flags=re.S):
            for c in re.findall(r"<tr><td>(.*?)</td>", t, flags=re.S):
                c = texte(c).strip()
                if "_" in c or not c[:1].isupper():
                    noms_lim.append((r, c))
        # sur le texte brut : textes[p] ram\u00e8ne toute espace (fine comprise) \u00e0 l'espace ordinaire, et ne peut donc pas
        # distinguer les s\u00e9parateurs (faux d\u00e9faut sur 1 635 pages le 12 novembre 2026) ; une balise devient \x00 pour ne
        # pas souder deux cellules voisines
        if re.match(r"rapports/(\d{4}-\d{2}-\d{2})/", r) and r.split("/")[1] != v_site:
            continue  # rapports des versions passées, archivés tels qu'ils ont été publiés
        brut = html.unescape(re.sub(r"<[^>]+>", "\x00", re.sub(
            r"<script\b[^>]*>.*?</script\s*>|<style\b[^>]*>.*?</style\s*>", "\x00", s, flags=re.S | re.I)))
        n = len(re.findall(r"\d[ \u00a0]\d{3}(?!\d)", brut))
        if n:
            milliers.append((r, f"{n} nombre(s) à espace ordinaire ou large"))
    note("Chaque limite de la page Méthode a un nom lisible", noms_lim)
    # un lien qui porte le titre d'une partie de la page mais mène ailleurs, alors que le sommaire mène à cette partie
    # sous le même intitulé (thème Addictologie, deux « De l'offre aux consommations en addictologie », audit du
    # 12 novembre 2026, point 22) ; les liens d'action répétés sous chaque figure ne sont pas concernés
    homonymes = []
    for p, s in sources.items():
        m = re.search(r"<main\b.*?</main>", s, flags=re.S)
        corps = m.group(0) if m else ""
        titres = {texte(t).strip() for t in re.findall(r"<h[23]\b[^>]*>(.*?)</h[23]>", corps, flags=re.S)
                  if "<a " not in t}   # un titre qui est lui-même un lien n'a pas d'homonyme
        for h, t in re.findall(r'<a\b[^>]*href="([^"]*)"[^>]*>(.*?)</a>', corps, flags=re.S):
            t = texte(t).strip()
            if t in titres and len(t) >= 12 and not h.startswith("#") and h.split("#")[0] != p.name:
                homonymes.append((rel(p), t[:60]))   # un onglet vers la page elle-même n'est pas un homonyme
    note("Un lien au titre d'une partie de la page mène à cette partie", homonymes)
    note("Séparateur des milliers : l'espace fine insécable seulement", milliers)

    # 3 septies. le repère d'une page d'indicateur dit si Mayotte y est comptée, d'après les valeurs mêmes (relecture du
    # 11 novembre 2026, 2.3 : « Mayotte comprise » sous une patientèle calculée sans elle)
    from pipeline import affichage as AF_, fiche_indicateur as FI_
    T_ = AF_.Affichage(sd, R)
    pages_ind = {rel(p): s for p, s in sources.items() if rel(p).startswith("indicateur/")}
    mayotte_rep = []
    for e in AF_.catalogue(sd, R):
        f = f"indicateur/{FI_.slug(e['id'])}.html"
        s = pages_ind.get(f)
        if not s or "Mayotte" not in s:
            continue
        for lv, code in (("dep", "976"), ("reg", "06")):
            S_ = T_.serie(e["id"], lv)
            if S_ is None or S_.med is None:
                continue
            k = S_.codes.index(code) if code in S_.codes else None
            a_valeur = k is not None and S_.v[k] is not None and S_.v[k] == S_.v[k]
            dit = texte(s)
            if a_valeur and "sauf Mayotte" in dit:
                mayotte_rep.append((f, "dit « sauf Mayotte », qui a une valeur"))
            if not a_valeur and "Mayotte comprise" in dit:
                mayotte_rep.append((f, "dit « Mayotte comprise », qui n'a pas de valeur"))
            break
    note("Repère des pages d'indicateur : Mayotte dite comptée seulement si elle l'est", mayotte_rep)

    # 4. DOI écrit sans lien, DOI général présenté comme celui d'une version archivée
    dois = []
    for p, s in sources.items():
        for d in set(re.findall(r"10\.5281/zenodo\.\d+", textes[p])):
            if not re.search(r'href="[^"]*' + re.escape(d) + '"', s):
                dois.append((rel(p), d))
        for m in re.finditer(r"version archivée[^<]{0,30}<a href=\"https://doi.org/([^\"]+)\"", s):
            if m.group(1) == config.DOI_DONNEES:
                dois.append((rel(p), "DOI de toutes les versions dit « version archivée »"))
        if f'data-doi="{config.DOI_DONNEES}"' in s and "data-doi-general" in s:
            dois.append((rel(p), "data-doi porte le DOI de toutes les versions"))
    note("DOI cliquables et nommés selon la version", dois)

    # 5. textes : termes proscrits, « Figure N. », « moyenne » comme repère, offre payante
    mots = []
    for p in pages:
        t = textes[p]
        mots += [(rel(p), x[:140]) for x in termes_proscrits(t)]
        for m in re.finditer(r"\b(Figure|Tableau|Carte|Graphique)\s+\d+\s*[.:]", t):
            mots.append((rel(p), t[max(0, m.start() - 30):m.end() + 30]))
        for m in re.finditer(r"\b[Mm]oyenne des (intercommunalités|départements|régions|territoires)\b", t):
            mots.append((rel(p), t[max(0, m.start() - 40):m.end() + 20]))
    note("Vocabulaire (termes proscrits, Figure N., « moyenne » des territoires)", mots)

    # 6. une profession rare jamais lue pour 10 000 (infobulles, lignes de tableau, phrases courtes)
    unite = []
    motif_r = re.compile(r"\b(" + "|".join(sorted((re.escape(x) for x in rares), key=len, reverse=True)) + r")\b") if rares else None
    for p, s in sources.items():
        morceaux = re.findall(r"<title>([^<]*)</title>", s) + [" ".join(cellules(l)) for l in re.findall(r"<tr.*?</tr>", s, flags=re.S)]
        for x in morceaux:
            x = html.unescape(x).replace(" ", " ").replace(" ", " ")
            if motif_r and motif_r.search(x.lower()) and re.search(r"pour 10 000 hab", x) and "100 000" not in x:
                if not re.search(r"(et|,) [^,]*pour 10 000", x):        # deux nombres, chacun son unité
                    unite.append((rel(p), x[:140]))
    note("Professions rares pour 100 000 habitants", unite)

    # 7. arrondis de la règle unique : une densité de 1 ou plus a une décimale (« 1,68 pour 10 000 » est faux)
    arr = []
    for p, s in sources.items():
        for x in [textes[p]] + re.findall(r"<title>([^<]*)</title>", s):
            x = html.unescape(x).replace(" ", " ").replace(" ", " ")
            for m in re.finditer(r"(?<![\d,])[1-9]\d{0,2},\d{2}(?![\d%])\s(pour 10 000|pour 100 000)", x):
                arr.append((rel(p), x[max(0, m.start() - 50):m.end()]))
    note("Arrondis des densités (une décimale à partir de 1)", arr)

    # 8. aucun 0 seul : tableaux des rapports, infobulles « 0 pour … », « 0,0 fois »
    zeros = []
    for f in sorted(R.glob("rapport*.md")) + sorted((R / "territoires").glob("*.md")):
        for l in f.read_text(encoding="utf-8").splitlines():
            if l.startswith("|") and re.search(r"\| 0 (?=\|)", l):
                zeros.append((f.name, l[:120]))
    for p, s in sources.items():
        for x in re.findall(r"<title>([^<]*)</title>", s) + re.findall(r'(?:data-tip|data-info|title)="([^"]*)"', s):
            x = html.unescape(x).replace(" ", " ").replace(" ", " ")
            if re.search(r"(^|[ :]|, )0([,.]0+)? (pour 1|fois l)|, 0([,.]0+)?$", x):
                zeros.append((rel(p), x[:120]))
        for l in re.findall(r"<tr.*?</tr>", s, flags=re.S):
            c = cellules(l)
            if re.match(r"(rapports|territoires)/", rel(p)) and any(re.fullmatch(r"0", v) for v in c[1:]):
                zeros.append((rel(p), " | ".join(c)[:120]))
            # toutes les pages : une cellule « 0 » porte son infobulle, ou la ligne son signe ou son abréviation (même
            # règle que controle_finition.js, qui ne voit qu'une page par type ; quartiles à 0 des pages d'indicateur,
            # 13 novembre 2026)
            elif "<abbr" not in l and 'class="sig' not in l:
                for attrs, v in re.findall(r"<td\b([^>]*)>(.*?)</td>", l, flags=re.S):
                    if "title=" not in attrs and html.unescape(re.sub(r"<[^>]+>", "", v)).strip() == "0":
                        zeros.append((rel(p), " | ".join(c)[:120]))
                        break
    note("Aucun 0 laissé seul", zeros)

    # noms des fichiers à télécharger sur une ligne : aucun point de coupure dans leur tableau, qu'Edge suit malgré
    # white-space: nowrap (audit du 13 novembre 2026, R3)
    coupes = []
    for p, s in sources.items():
        for t in re.findall(r'<table class="[^"]*\bfichiers\b[^"]*">.*?</table>', s, flags=re.S):
            if "<wbr" in t:
                coupes.append((rel(p), str(t.count("<wbr"))))
    note("Noms des fichiers à télécharger jamais coupés", coupes)

    # un groupe de mots répété aussitôt après une virgule, la reprise en majuscule (« publie vers les urgences, Vers les
    # urgences, 5,0 % », audit du 13 novembre 2026, R5), dans les paragraphes seulement (les listes de tableaux se
    # répètent par nature)
    repete, rx_rep = [], re.compile(r"\b(\w+(?:['’ ]\w+){1,4}), (\1)\b", re.I)
    for p, s in sources.items():
        for par in re.findall(r"<p\b[^>]*>(.*?)</p>", s, flags=re.S):
            x = html.unescape(re.sub(r"<[^>]+>", "", par))
            for m in rx_rep.finditer(x):
                if m.group(2)[0].isupper() and m.group(1)[0].islower():
                    repete.append((rel(p), x[max(0, m.start() - 40):m.end() + 20]))
    note("Aucun groupe de mots répété deux fois de suite", repete)

    # « 1er », jamais « 1e », dans les ordinaux que le site écrit (infobulles des dixièmes, audit du 13 novembre
    # 2026, R8) ; une raison sociale (« SSR Gériatrique 1e Lagache ») reste telle quelle
    premier = []
    for p, s in sources.items():
        for x in [textes[p]] + re.findall(r"<title>([^<]*)</title>", s) + re.findall(r'(?:title|aria-label)="([^"]*)"', s):
            if re.search(r"(?<![\w,])1e (?:dixième|décile|quart|quartile|centile|tranche|groupe|rang|classe)", html.unescape(x)):
                premier.append((rel(p), x[:120]))
                break
    note("« 1er », jamais « 1e »", premier)

    # 9. un même chiffre sur la fiche et dans le rapport du département (effectif et densité, toutes les professions
    #    des deux tableaux, tous les départements)
    ecarts = []
    for fiche in sorted((SITE / "territoire" / "dep").glob("*.html")):
        c = fiche.stem
        f = fiche.read_text(encoding="utf-8")
        fi = {}
        for ligne in re.findall(r'<tr id="l-prof-[a-z-]+-all".*?</tr>', f, flags=re.S):
            th = re.search(r"<th[^>]*>(.*?)</th>", ligne, flags=re.S)
            eff = re.search(r'<td class="eff">(.*?)</td>', ligne, flags=re.S)
            v = re.search(r'<td class="v">(.*?)</td>', ligne, flags=re.S)
            if not (th and eff and v):
                continue
            b = re.search(r"<b>(.*?)</b>", v.group(1), flags=re.S)
            net = lambda x: html.unescape(re.sub(r"<[^>]+>", " ", x)).replace(" ", " ").replace(" ", " ")  # noqa: E731
            e = re.sub(r"\s+", " ", net(eff.group(1))).replace("petit effectif", "").strip()
            e = re.sub(r" inscrits?$", "", e)
            d = re.sub(r"\s+", " ", net(b.group(1) if b else v.group(1))).strip()
            fi[re.sub(r"\s+", " ", net(th.group(1))).strip().lower()] = (e, d)
        for dom in ("sante", "sante-mentale"):
            r = SITE / "territoires" / date / f"dep-{c}-{dom}.html"
            if not r.exists():
                continue
            for t in re.findall(r"<table.*?</table>", r.read_text(encoding="utf-8"), flags=re.S):
                lignes = re.findall(r"<tr.*?</tr>", t, flags=re.S)
                if not lignes or cellules(lignes[0])[:2] != ["Profession", "Effectif"]:
                    continue
                for l in lignes[1:]:
                    x = cellules(l)
                    nom = re.sub(r" \(pour 100 000\)$", "", x[0]).lower()
                    cle = next((k for k in fi if k in (nom, pluriel(nom))), None)
                    if not cle:
                        continue
                    eff_f, dens_f = fi[cle]
                    eff_r = x[1].replace("aucun", "0")
                    dens_r = x[2]
                    if eff_f.replace("aucun", "0") != eff_r or (dens_r not in ("aucun inscrit",) and dens_f != dens_r):
                        ecarts.append((f"dep {c} {cle}", f"fiche {eff_f} / {dens_f}, rapport {eff_r} / {dens_r}"))
                break
    note("Même effectif et même densité sur la fiche et dans le rapport du département", ecarts)

    # 10. titres de fiches avec l'article et l'élision (« Fiche de l'Aveyron », « d'Orléans Métropole »)
    titres = []
    for p, s in sources.items():
        for m in re.finditer(r'data-titre="Fiche (de|du|des|d’|de la|de l’) ?([^"]*)"', s):
            if m.group(1) == "de" and re.match(r"[AEIOUYÉÈÊÎÏÔÂH]", m.group(2)):
                titres.append((rel(p), m.group(0)))
    note("Titres des fiches avec l'article du territoire", titres)

    # 11. PDF nationaux : un nombre jamais coupé entre ses groupes de chiffres en fin de ligne
    pdf = []
    try:
        from pypdf import PdfReader
        for f in sorted((SITE / "rapports" / date).glob("*.pdf")):
            for i, pg in enumerate(PdfReader(str(f)).pages, 1):
                lignes = (pg.extract_text() or "").splitlines()
                for a, b in zip(lignes, lignes[1:]):
                    # une liste de codes (« 95 / 971 972 973 ») n'est pas un nombre coupé
                    if (re.search(r"(?<![\d,])\d{1,3}$", a.strip()) and re.match(r"\d{3}\b", b.strip())
                            and not re.match(r"\d{3} \d{3}\b", b.strip())):
                        pdf.append((f"{f.name} p. {i}", f"{a.strip()[-30:]} / {b.strip()[:20]}"))
    except ImportError:
        pdf.append(("pypdf", "absent, contrôle des PDF non fait"))
    note("PDF : nombres jamais coupés en fin de ligne", pdf)

    # 12. tout chiffre d'une figure se lit aussi au survol (règle de Lucas du 6 novembre 2026) : une figure de données
    #     (role="img") dont les barres, points ou territoires n'ont pas d'infobulle est signalée
    survol = []
    for p, s in sources.items():
        for m in re.finditer(r'<svg\b([^>]*role="img"[^>]*)>(.*?)</svg>', s, flags=re.S):
            att, g = m.group(1), m.group(2)
            if 'aria-hidden="true"' in att or "Schéma" in att:
                continue
            g = re.sub(r"<defs>.*?</defs>", "", g, flags=re.S)
            marques = [x for x in re.findall(r"<(?:rect|circle|use)\b[^>]*>", g)
                       # les territoires de contexte, sans valeur à lire (fond gris « nodata »), ne sont pas comptés
                       if 'fill="none"' not in x and "choisi" not in x and "--nodata" not in x and 'class="nd"' not in x
                       and not re.search(r'width="(16|92|12|0)"', x)]
            if len(marques) < 5 or "<g><title>" in g:
                continue
            if g.count("<title>") < .3 * len(marques):
                lab = re.search(r'aria-label="([^"]*)"', att)
                survol.append((rel(p), html.unescape(lab.group(1))[:90] if lab else "figure sans nom"))
    note("Valeurs des figures lisibles au survol", survol)

    # 13. règle d'affichage des chiffres sur tout le site (pipeline/controle_affichage.py) : même valeur, même repère et
    #     même statut sur toutes les pages et dans les CSV. Faite ici aussi, car une reconstruction de quelques pages
    #     (pipeline.site --pages) la laisse au contrôle d'avant publication.
    from pipeline import controle_affichage
    regle = [("règle d'affichage", t[:200]) for n, t in controle_affichage.controler(SITE, R, sd) if n == "bloquant"]
    note("Règle d'affichage des chiffres (même valeur, même repère, même statut partout)", regle)

    # 14. ne rien perdre (registre 18) : une figure que le rapport annonce existe, et aucune figure de la version
    #     précédente ne manque à celle-ci (7 novembre 2026 : la carte bivariée de santé mentale avait disparu sans bruit,
    #     son échec n'était qu'un avertissement du journal et le site retire en silence un emplacement vide)
    perdues = []
    faites = {p.stem for p in (R / "graphiques").glob("*.svg")}
    for md in sorted(R.glob("rapport*.md")):
        for nom in re.findall(r"<!--GRAPHIQUE (\S+)-->", md.read_text(encoding="utf-8")):
            if nom not in faites:
                perdues.append((md.name, nom, "annoncée, absente"))
    avant = [p for p in sorted((RACINE / "resultats").glob("20*")) if p.name < date and (p / "graphiques").is_dir()
             and any((p / "graphiques").glob("*.svg"))]
    if avant:
        for nom in sorted({p.stem for p in (avant[-1] / "graphiques").glob("*.svg")} - faites):
            perdues.append((avant[-1].name, nom, "présente dans la version précédente, absente ici"))
    note("Aucune figure perdue (annoncée par le rapport, présente dans la version précédente)", perdues)

    # 15. navigation (audit du 8 novembre 2026, étape 1 validée par Lucas) : chaque fiche relie le territoire qui la
    #     contient et ceux qu'elle contient, propose « Autour d'un lieu » ; chaque page a au pied « Autour d'un lieu » et
    #     « Télécharger les données » ; plus d'ancien nom « Données sources »
    nav = []
    for p, s in sources.items():
        r = rel(p)
        m = re.match(r"territoire/(reg|dep|epci)/([^/]+)\.html$", r)
        if m:
            lv = m.group(1)
            tete = re.search(r'<p class="tete-l2">(.*?)</p>', s, flags=re.S)
            tete = tete.group(1) if tete else ""
            if lv in ("dep", "epci") and 'href="../reg/' not in tete:
                nav.append((r, "pas de lien vers la région"))
            if lv == "epci" and 'href="../dep/' not in tete:
                nav.append((r, "pas de lien vers le département"))
            if lv in ("reg", "dep") and 'id="territoires-inclus"' not in s:
                nav.append((r, "pas de liste des territoires contenus"))
            if "zone.html" not in (re.search(r'<p class="tete-outils.*?</p>', s, flags=re.S) or [""])[0]:
                nav.append((r, "pas d'« Autour d'un lieu » en tête de fiche"))
        pied = re.search(r'<p class="pied-liens">.*?</p>', s, flags=re.S)
        if pied and not ("zone.html" in pied.group(0) and "methode-fichiers.html" in pied.group(0)):
            nav.append((r, "pied de page sans « Autour d'un lieu » ou « Télécharger les données »"))
        if "Données sources" in textes[p]:
            nav.append((r, "ancien nom « Données sources »"))
    note("Navigation : liens entre niveaux, « Autour d'un lieu », pied de page", nav)

    # 16. une unité n'est jamais répétée dans un titre (« CSAPA, pour 100 000 habitants, pour 100 000 hab. », dix pages
    #     d'indicateur, relevé par la relecture du 8 novembre 2026)
    double = []
    for p, s in sources.items():
        for h in re.findall(r"<h1[^>]*>(.*?)</h1>", s, flags=re.S):
            t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", h)).replace(" ", " ").replace(" ", " "))
            if len(re.findall(r"pour 1[0 ]*0 hab", t)) > 1 or t.count("%") > 1:
                double.append((rel(p), t))
    note("Aucune unité répétée dans un titre", double)

    # 17. catalogue des indicateurs complet (navigation, étape 2) : chaque page d'indicateur y figure, chaque entrée mène
    #     à une page qui existe (8 novembre 2026 : « prof:allergologue:all » perdait son lien, 216 sur 217)
    cat_pb = []
    f_cat = SITE / "presentation" / "catalogue.json"
    if f_cat.exists():
        C = json.loads(f_cat.read_text(encoding="utf-8"))
        dans = {x["page"] for x in C}
        cat_pb += [(p, "page d'indicateur absente du catalogue") for p in sorted(rel(q) for q in (SITE / "indicateur").glob("*.html")) if p not in dans]
        cat_pb += [(x["page"], "entrée du catalogue sans page") for x in C if not (SITE / x["page"]).exists()]
    else:
        cat_pb.append(("presentation/catalogue.json", "absent"))
    note("Catalogue des indicateurs complet", cat_pb)

    # 16 bis. une unité jamais écrite deux fois de suite, dans tout texte lu et dans le catalogue (« EHPAD, pour 100 000
    #     personnes de 80 ans et plus, pour 100 000 personnes de 80 ans et plus », audit indépendant du 8 novembre 2026)
    rep = re.compile(r"(pour [^,;.]{6,}), \1\b")
    deux = [(rel(p), m.group(0)[:80]) for p in pages if (m := rep.search(textes[p]))]
    if f_cat.exists():
        deux += [("presentation/catalogue.json", x["nom"]) for x in json.loads(f_cat.read_text(encoding="utf-8")) if rep.search(x["nom"])]
    note("Aucune unité écrite deux fois de suite", deux)

    # 18. recherche de l'en-tête et réponses directes (outils/controle_recherche.py) : articles, « aucun » sans position,
    #     département de rattachement, pluriels, codes postaux, et requêtes types essayées dans le navigateur
    sys.path.insert(0, str(RACINE / "outils"))
    import controle_recherche
    note("Recherche de l'en-tête et réponses directes", controle_recherche.controler())

    # compte rendu
    total = 0
    print(f"Contrôle des décisions sur le site construit ({date}), {len(pages)} pages")
    for k, v in defauts.items():
        total += len(v)
        if not v:
            print(f"  ok      {k}")
        else:
            print(f"  {len(v):>5}   {k}")
            for x in v[:3]:
                print(f"            {x}")
    print("Aucun défaut." if not total else f"{total} défaut(s).")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(controler())
