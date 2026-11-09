"""Contrôle de la recherche de l'en-tête et de ses réponses directes (navigation, étape 2), sur tous les fichiers du site
construit. Chaque règle vient d'un défaut relevé par l'audit indépendant du 8 novembre 2026 :

- l'article de chaque territoire (« en Bretagne », « à Mayotte », « dans l'Aveyron », jamais « dans Bretagne ») ;
- aucune position à côté de « aucun » (la fiche écrit « comme dans 90 % des intercommunalités ») ;
- l'ensemble jamais écrit deux fois (« plus loin que l'ensemble (6,3 km) » puis « Ensemble : 6,3 ») ;
- le département de rattachement écrit dans chaque intercommunalité, pour les indicateurs publiés par département ;
- les noms au pluriel sans faute (« nons », sigle en minuscules), et au singulier pour un seul inscrit ;
- tous les codes postaux de chaque commune dans l'index de recherche (75015 était perdu) ;
- et la recherche elle-même, essayée dans le navigateur sur des requêtes types : « psychiatres à Rodez » répond par les
  psychiatres, jamais par les lits d'hospitalisation.

Contre-audit du même jour : aucune valeur vide écrite comme un chiffre (« :  % »), aucun « 0 » de structure sans « aucune »,
aucun zéro sans la note de la fiche, la limite de la fiche reprise, aucun pluriel dans une parenthèse, « Autour d'… »
élidé, l'article et le sigle facultatifs dans un nom de lieu, Paris par son code postal comme par son nom, les homonymes
proposés, l'indicateur et le lieu proposés séparément quand la phrase n'a pas de réponse directe, le repli sur la région.

Second contre-audit : les 45 arrondissements de Paris, Lyon et Marseille trouvés et menant à la fiche de leur commune,
« en » devant un département féminin qui commence par une consonne (« en Lozère », mais « dans la Manche »,
reponses.DANS_LA), une commune hors intercommunalité écrite « à Ouessant », jamais « dans Ouessant » ni « dont Ouessant
fait partie », dans la réponse comme sur sa fiche.

    python outils/controle_recherche.py      # aussi appelé par outils/controle_decisions.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils"))
SITE = RACINE / "site"

from pipeline.reponses import DANS_LA  # noqa: E402

# requête, indicateur attendu, niveau et code du territoire reconnu (une commune répond par son intercommunalité)
REQUETES = [
    ("psychiatres à Rodez", "prof:psychiatre", "com", "12202"),
    ("psychiatres Rodez", "prof:psychiatre", "com", "12202"),
    ("psychiatres en Bretagne", "prof:psychiatre", "reg", "53"),
    ("médecins généralistes à Lyon", "prof:medecin_generaliste", "com", "69123"),
    ("psychiatres 75015", "prof:psychiatre", "dep", "75"),
    ("psychiatres Réunion", "prof:psychiatre", "dep", "974"),
    ("psychiatres Havre", "prof:psychiatre", "com", "76351"),
    ("psychiatres Rodez Agglomération", "prof:psychiatre", "epci", "241200187"),
    ("distance CMP Rodez", "dist_lieu_cmp_adultes", "com", "12202"),
    ("médecins Lyon", "prof:medecin_generaliste", "com", "69123"),
    ("logement Rennes", "aucune", None, None),
    ("emploi Lyon", "aucune", None, None),
    ("places de jour Mayotte", "sae_places_jour_psy", "dep", "976"),
    ("psychiatres guadeloupe", "prof:psychiatre", "dep", "971"),
    ("psychologues dans l'Aveyron", "prof:psychologue", "dep", "12"),
    ("CMP Aveyron", "lieux_lieu_cmp_adultes", "dep", "12"),
    # arrondissements : Paris répond par le département, Lyon et Marseille par l'arrondissement, rattaché à la métropole
    ("psychiatres Paris 15e", "prof:psychiatre", "dep", "75"),
    ("psychiatres Paris 15", "prof:psychiatre", "dep", "75"),
    ("psychiatres Lyon 3e", "prof:psychiatre", "com", "69383"),
    ("psychiatres Lyon 1er", "prof:psychiatre", "com", "69381"),
    ("psychiatres Marseille 8ème", "prof:psychiatre", "com", "13208"),
    ("psychiatres Lozère", "prof:psychiatre", "dep", "48"),
]

# recherche de l'accueil, du comparateur et de « Autour d'un lieu » (recherche.js) : requête, premier résultat attendu ;
# les arrondissements s'y trouvent comme dans le panneau, sans passer devant Paris quand la recherche n'a pas de chiffre
ACCUEIL = [
    ("Paris 15e", "75115"),
    ("paris 15", "75115"),
    ("Lyon 1er", "69381"),
    ("Lyon 3e", "69383"),
    ("Marseille 8ème", "13208"),
    ("Marseille 8e arrondissement", "13208"),
    ("Paris", "75"),
    ("Lyon", "69123"),
    ("Rodez", "12202"),
    # l'arrondissement dont c'est le code postal avant la commune (relecture indépendante du 9 novembre 2026)
    ("75015", "75115"),
]

# requête, textes attendus dans le panneau, textes interdits (expressions régulières)
RENDUS = [
    ("taux de pauvreté Mayotte", ["non diffusé|pas de valeur publiée|non publié"], [r":\s+%", r":\s+€", r"soit\s+pour"]),
    ("revenu médian Guadeloupe", [], [r":\s+€", r"(Département|Ensemble).*:\s*\d"]),
    ("CATTP Haute-Corse", ["aucune"], [r"\b0 dans", r"soit\s+pour"]),
    ("psychiatres Avignon", ["Autour d'Avignon"], ["Autour de A"]),
    ("psychiatres Le Havre", ["Autour du Havre"], ["Autour de Le"]),
    ("psychiatres Saint-Denis", ["Autres lieux de ce nom"], []),
    ("psychiatres auvergne", ["Pas de réponse directe"], ["Rien ne porte ce nom"]),
    ("pensées suicidaires Aveyron", ["Occitanie", "publié par région"], ["pas de valeur publiée"]),
    ("médecins spécialistes Rodez", [], [r"\)s\b"]),
    ("psychiatres à Rodez", ["4,8 pour 10 000 habitants", "Autour de Rodez"], ["’"]),
    ("Paris 15e", ["Paris 15e arrondissement"], ["Rien ne porte ce nom"]),
    ("Lyon 3e", ["Lyon 3e arrondissement"], ["Rien ne porte ce nom"]),
    ("Marseille 8e", ["Marseille 8e arrondissement"], ["Rien ne porte ce nom"]),
    ("psychiatres Paris 15e", ["à Paris, dont Paris 15e arrondissement fait partie"], []),
    ("psychiatres Lyon 3e", ["dont Lyon 3e arrondissement fait partie", "Autour de Lyon"], ["Autour de Lyon 3e"]),
    ("psychiatres Ouessant", ["à Ouessant"], ["dont Ouessant fait partie", "dans Ouessant"]),
    ("Ouessant", ["Ouessant"], ["dans Ouessant"]),
    ("psychiatres Lozère", ["en Lozère"], ["dans la Lozère"]),
    ("psychiatres Seine-Saint-Denis", ["en Seine-Saint-Denis"], ["dans la Seine-Saint-Denis"]),
    ("psychiatres Manche", ["dans la Manche"], ["en Manche"]),
    # relecture indépendante du 9 novembre 2026 : l'article des îles, aucun 0 % laissé seul, Paris et ses arrondissements
    # vers la fiche du département, une grande commune jamais « trop petite », la commune sans intercommunalité nommée
    ("psychologues ile d'yeu", ["à l'Île-d'Yeu"], ["à L'Île"]),
    ("infirmiers île-de-sein", ["moins de 1"], [r"(^|[^\d,])0\s?%"]),
    ("psychiatres Isère", ["en Isère"], ["dans l'Isère"]),
    ("psychiatres Paris 15e", ["Autour de Paris"], []),
    ("Paris 15e", ["territoire/dep/75.html", "75015, à Paris"], ["commune=75115", "arrondissement, 75015"]),
    ("Lyon 3e", ["arr=Lyon%203e", "grande=1", "nom=Lyon&"], []),
    ("Ouessant", ["commune sans intercommunalité"], ["commune=", "Ouessantintercommunalité"]),
]


def fichiers() -> list[tuple[str, str]]:
    from pipeline.reponses import commune_seule
    """Défauts des fichiers des réponses directes : (fichier, défaut)."""
    pb = []
    ref = json.loads((RACINE / "donnees" / "brut" / "ref_communes.json").read_text(encoding="utf-8")) \
        if (RACINE / "donnees" / "brut" / "ref_communes.json").exists() else None
    for lv in ("reg", "dep", "epci"):
        for f in sorted((SITE / "territoire" / lv).glob("*.json")):
            r = f"territoire/{lv}/{f.name}"
            j = json.loads(f.read_text(encoding="utf-8"))
            d = j.get("dans") or ""
            if lv in ("reg", "dep"):
                if not re.match(r"^(dans (la |le |les |l’)|en |à )", d):
                    pb.append((r, f"article : « {d} »"))
                # « dans la Lozère » : « en » devant un nom féminin qui commence par une consonne, sauf les noms d'une
                # syllabe de reponses.DANS_LA (« dans la Manche »)
                if d.startswith("dans la ") != (lv == "dep" and f.stem in DANS_LA):
                    pb.append((r, f"article : « {d} », attendu « {'dans la' if f.stem in DANS_LA else 'en'} »"))
            elif not re.match(r"^(dans |à )", d):
                pb.append((r, f"article : « {d} »"))
            elif f.stem.startswith("C") and d != "à " + commune_seule(j["nom"]):
                # « à l'Île-d'Yeu », « à l'Île-de-Sein » (relecture indépendante du 9 novembre 2026)
                pb.append((r, f"commune hors intercommunalité : « {d} », attendu « à {commune_seule(j['nom'])} »"))
            if lv == "epci" and f.stem.startswith("C"):
                # la fiche de la commune : « n'est inscrit dans la commune d'Ouessant », jamais « dans Ouessant »
                page = f.with_suffix(".html")
                txt = page.read_text(encoding="utf-8").replace("&#39;", "'") if page.exists() else ""
                if re.search(r"\b(dans|Pour) " + re.escape(j["nom"]) + r"\b", txt):
                    pb.append((f"territoire/epci/{page.name}", f"« dans {j['nom']} » ou « Pour {j['nom']} » sans « la commune »"))
            for k, v in j["ind"].items():
                if v[7] == "lieux" and v[0] == "0":
                    pb.append((r, f"{k} : « 0 » structure au lieu de « aucune »"))
                if v[1] == "0" and v[0] != "aucun" and not v[6] and v[7] in ("ctx", "dist"):
                    pb.append((r, f"{k} : zéro sans la note de la fiche"))
                if not v[1] and v[0] != "aucun" and (v[4] or v[2]):
                    pb.append((r, f"{k} : repère ou position écrits sans valeur"))
                if v[0] in ("aucun", "0") and re.search(r"plus (haut|bas|loin|près) que \d", v[2] or ""):
                    pb.append((r, f"{k} : position écrite à côté de « aucun »"))
                if v[4] and "l'ensemble (" in (v[2] or ""):
                    pb.append((r, f"{k} : ensemble écrit deux fois"))
                if v[2] and re.search(r"^, |, ,|mais ,", v[2]):
                    pb.append((r, f"{k} : phrase de position mal formée « {v[2]} »"))
            if lv == "epci" and not f.stem.startswith("C") and not j.get("dep"):
                pb.append((r, "département de rattachement absent"))
    # aucun « 0 % » laissé seul, ni dans les réponses ni sur les fiches (« C'est le cas de 0 % des intercommunalités »,
    # Île-de-Sein, relecture indépendante du 9 novembre 2026)
    zero = re.compile(r"(cas de|comme dans) 0[\s  ]?%")
    for f in sorted((SITE / "territoire").glob("*/*.*")):
        if f.suffix in (".json", ".html") and zero.search(f.read_text(encoding="utf-8")):
            pb.append((f"territoire/{f.parent.name}/{f.name}", "« 0 % » laissé seul"))
    m = SITE / "presentation" / "reponses.json"
    if m.exists():
        for k, (nom, _u, *sing) in json.loads(m.read_text(encoding="utf-8")).items():
            if not k.startswith("prof:"):
                continue
            # « 1 pédopsychiatres » : un seul inscrit s'écrit au singulier (contrôle du 8 novembre 2026)
            if not sing or not sing[0] or sing[0] == nom or re.search(r"[A-ZÉ][a-zé]", sing[0]):
                pb.append(("presentation/reponses.json", f"{k} : singulier absent ou faux « {sing} »"))
            avant, et, apres = nom.split(",")[0].partition(" et ")
            # « chirurgiens thoraciques et cardiovasculaire » : le mot après « et » s'accorde, sauf après une préposition
            libre = et and not re.search(r" (pour|de|du|des|en|à|au|aux) |['’]", avant)
            if re.search(r"\bnons\b|\([a-z]{2,6}\)|\)s\b", nom) or (libre and not re.match(r"[^ ]+[sx]\b", apres)):
                pb.append(("presentation/reponses.json", f"{k} : pluriel « {nom} »"))
    rj = SITE / "presentation" / "recherche.json"
    if rj.exists() and ref is not None:
        jr = json.loads(rj.read_text(encoding="utf-8"))
        cps = {c[0]: set(c[2].split()) for c in jr["communes"]}
        for c in ref:
            if c["code"] in cps and set(c.get("codesPostaux") or []) - cps[c["code"]]:
                pb.append(("presentation/recherche.json", f"commune {c['code']} : codes postaux manquants"))
        # chaque arrondissement municipal du référentiel, avec la commune et l'intercommunalité de sa commune
        epci_com = {c[0]: c[4] for c in jr["communes"]}
        arr = {a[0]: a for a in jr.get("arrondissements", [])}
        for c in ref:
            if c.get("type") != "arrondissement-municipal":
                continue
            a = arr.get(c["code"])
            if not a:
                pb.append(("presentation/recherche.json", f"arrondissement {c['code']} {c['nom']} absent de la recherche"))
            elif (a[5] != c.get("commune") or a[4] != epci_com.get(c.get("commune"))
                  or set(c.get("codesPostaux") or []) - set(a[2].split())):
                pb.append(("presentation/recherche.json", f"arrondissement {c['code']} : commune, intercommunalité ou codes postaux faux"))
    return pb


def essais() -> list[tuple[str, str]]:
    """La recherche essayée dans le navigateur sans fenêtre (Edge), avec le script publié."""
    from pipeline import site as S
    import controle_finition as CF
    exe = S.navigateur()
    if not exe:
        return [("presentation/chercher.js", "navigateur introuvable, recherche non essayée")]
    page = SITE / "_controle_chercher.html"
    req = json.dumps([q for q, *_ in REQUETES], ensure_ascii=False)
    rendus = json.dumps([q for q, *_ in RENDUS], ensure_ascii=False)
    page.write_text(
        '<!doctype html><html data-racine=""><head><meta charset="utf-8"></head><body>'
        '<button id="bouton-chercher"></button><div id="panneau-chercher" hidden><input id="q-tete">'
        '<p id="etat-tete"></p><div id="res-tete"></div></div>'
        '<pre id="sortie">attente</pre><script src="presentation/chercher.js"></script>'
        '<script src="presentation/recherche.js"></script>'
        '<script>var Q=' + req + ',R=' + rendus + ',A=' + json.dumps([q for q, _ in ACCUEIL], ensure_ascii=False) +
        ';(function go(){if(!window.UbiChercher){return setTimeout(go,50)}'
        'Promise.all([UbiChercher.charger(),Recherche.charger("")]).then(function(){var out=Q.map(function(q){'
        'var a=UbiChercher.analyser(q);return a?[q,a.ind[0].c,a.terr.t,a.terr.c]:[q,"aucune",null,null]}),vus={};'
        'vus.__accueil=A.map(function(q){var r=Recherche.chercher(q);return r.length?r[0].c:null});'
        'function un(k){if(k>=R.length){document.getElementById("sortie").textContent=JSON.stringify([out,vus]);return}'
        'UbiChercher.chercher(R[k]);setTimeout(function(){vus[R[k]]=document.getElementById("res-tete").innerText+" "+Array.prototype.map.call(document.querySelectorAll("#res-tete a"),function(a){return a.getAttribute("href")}).join(" ");un(k+1)},1500)}'
        'un(0)})})();</script>'
        '</body></html>', encoding="utf-8")
    serveur = CF._serveur(SITE)
    try:
        url = f"http://127.0.0.1:{serveur.server_address[1]}/{page.name}"
        dom = subprocess.run([exe, "--headless=new", "--disable-gpu", "--virtual-time-budget=60000", "--dump-dom", url],
                             capture_output=True, text=True, encoding="utf-8", timeout=180).stdout
    finally:
        serveur.shutdown()
        page.unlink(missing_ok=True)
    m = re.search(r'<pre id="sortie">(.*?)</pre>', dom or "", flags=re.S)
    if not m or m.group(1).strip() == "attente":
        return [("presentation/chercher.js", "la recherche n'a pas répondu dans le navigateur (erreur de script ?)")]
    import html as H
    lignes, vus = json.loads(H.unescape(m.group(1)))
    obtenu = {r[0]: r[1:] for r in lignes}
    pb = []
    for q, attendus, interdits in RENDUS:
        txt = vus.get(q) or ""
        for a in attendus:
            if not re.search(a, txt):
                pb.append(("presentation/chercher.js", f"« {q} » : « {a} » absent du panneau ({txt[:160]!r})"))
        for x in interdits:
            if re.search(x, txt):
                pb.append(("presentation/chercher.js", f"« {q} » : « {x} » dans le panneau ({txt[:160]!r})"))
    for (q, code), o in zip(ACCUEIL, vus.get("__accueil") or [None] * len(ACCUEIL)):
        if o != code:
            pb.append(("presentation/recherche.js", f"accueil, « {q} » : premier résultat {o}, attendu {code}"))
    for q, ind, lv, code in REQUETES:
        o = obtenu.get(q) or [None, None, None]
        if (ind and o[0] != ind) or o[1] != lv or o[2] != code:
            pb.append(("presentation/chercher.js", f"« {q} » : obtenu {o}, attendu {[ind or '…', lv, code]}"))
    return pb


def catalogue_recherche() -> list[tuple[str, str]]:
    """La recherche suit les ajouts de bases et de variables (Lucas, 9 novembre 2026) : les indicateurs de l'index sont
    exactement ceux du catalogue unique du site construit (presentation/catalogue.json), chacun a sa réponse directe
    (presentation/reponses.json), et chaque page de thème et chaque question d'Explorer est dans les pages proposées.
    Une base ajoutée qui manquerait à la recherche fait échouer le contrôle."""
    from pipeline import themes as TH
    rj, cj, mj = (SITE / "presentation" / n for n in ("recherche.json", "catalogue.json", "reponses.json"))
    if not rj.exists():
        return []
    r = json.loads(rj.read_text(encoding="utf-8"))
    ids = [i[0] for i in r["indicateurs"]]
    pb = [("presentation/recherche.json", f"indicateur {i} en double dans la recherche") for i in sorted({i for i in ids if ids.count(i) > 1})]
    if cj.exists():
        cat = {e["id"] for e in json.loads(cj.read_text(encoding="utf-8"))}
        pb += [("presentation/recherche.json", f"indicateur {i} du catalogue absent de la recherche") for i in sorted(cat - set(ids))]
        pb += [("presentation/recherche.json", f"indicateur {i} de la recherche absent du catalogue") for i in sorted(set(ids) - cat)]
    else:
        pb.append(("presentation/catalogue.json", "catalogue absent, recherche non comparée"))
    if mj.exists():
        m = json.loads(mj.read_text(encoding="utf-8"))
        pb += [("presentation/reponses.json", f"indicateur {i} sans réponse directe") for i in ids if TH.cle(i) not in m]
    else:
        pb.append(("presentation/reponses.json", "réponses directes absentes"))
    urls = {p[1] for p in r.get("pages", [])}
    titres = {re.sub(r"\s+", " ", p[0]).strip() for p in r.get("pages", [])}
    for f in sorted((SITE / "theme").glob("*.html")):
        if f"theme/{f.name}" not in urls:
            pb.append(("presentation/recherche.json", f"page de thème theme/{f.name} absente de la recherche"))
    for th in TH.THEMES:
        if not th.get("a_venir") and th["nom"] not in titres:
            pb.append(("presentation/recherche.json", f"thème « {th['nom']} » absent de la recherche"))
    ex = SITE / "explorer.html"
    if ex.exists():
        for sec in re.findall(r"<section[^>]*class=\"question\"[\s\S]*?(?=<section[^>]*class=\"question\"|$)",
                              ex.read_text(encoding="utf-8")):
            h2 = re.search(r"<h2[^>]*>(.*?)</h2>", sec, flags=re.S)
            q = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h2.group(1))).strip() if h2 else None
            if q and q not in titres:
                pb.append(("presentation/recherche.json", f"question d'Explorer « {q} » absente de la recherche"))
    return pb


def controler() -> list[tuple[str, str]]:
    return fichiers() + catalogue_recherche() + essais()


if __name__ == "__main__":
    d = controler()
    for x in d:
        print("DÉFAUT", *x)
    print("Aucun défaut." if not d else f"{len(d)} défaut(s).")
    sys.exit(1 if d else 0)
