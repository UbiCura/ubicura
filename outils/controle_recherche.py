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
]


def fichiers() -> list[tuple[str, str]]:
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
            elif not re.match(r"^(dans |à )", d):
                pb.append((r, f"article : « {d} »"))
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
        cps = {c[0]: set(c[2].split()) for c in json.loads(rj.read_text(encoding="utf-8"))["communes"]}
        for c in ref:
            if c["code"] in cps and set(c.get("codesPostaux") or []) - cps[c["code"]]:
                pb.append(("presentation/recherche.json", f"commune {c['code']} : codes postaux manquants"))
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
        '<script>var Q=' + req + ',R=' + rendus + ';(function go(){if(!window.UbiChercher){return setTimeout(go,50)}'
        'UbiChercher.charger().then(function(){var out=Q.map(function(q){'
        'var a=UbiChercher.analyser(q);return a?[q,a.ind[0].c,a.terr.t,a.terr.c]:[q,"aucune",null,null]}),vus={};'
        'function un(k){if(k>=R.length){document.getElementById("sortie").textContent=JSON.stringify([out,vus]);return}'
        'UbiChercher.chercher(R[k]);setTimeout(function(){vus[R[k]]=document.getElementById("res-tete").innerText;un(k+1)},1500)}'
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
    for q, ind, lv, code in REQUETES:
        o = obtenu.get(q) or [None, None, None]
        if (ind and o[0] != ind) or o[1] != lv or o[2] != code:
            pb.append(("presentation/chercher.js", f"« {q} » : obtenu {o}, attendu {[ind or '…', lv, code]}"))
    return pb


def controler() -> list[tuple[str, str]]:
    return fichiers() + essais()


if __name__ == "__main__":
    d = controler()
    for x in d:
        print("DÉFAUT", *x)
    print("Aucun défaut." if not d else f"{len(d)} défaut(s).")
    sys.exit(1 if d else 0)
