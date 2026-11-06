"""Contrôles de la règle d'affichage, qui bloquent la construction du site (plan de reprise de la présentation, étape 1,
30 octobre 2026, docs/comparaison_et_feuille_de_route_2026-10-30.md, partie 3.5).

1. Cohérence. Pour 20 territoires et 20 indicateurs, la valeur, le repère et le statut écrits par la règle d'affichage
   (pipeline/affichage.py) se retrouvent à l'identique sur la fiche du territoire, dans les données du comparateur et
   de Croiser, dans l'atlas, dans le rapport du département et dans les fichiers CSV publiés.
2. Aucune chaîne de maquette : « réel » ou « réelle », « exemple » hors de « par exemple », lien vide href="#".
3. Une seule date par source : la date du répertoire RPPS écrite dans les pages est celle du journal des sources.
4. Aucun « 0 » sans statut sur les fiches des territoires.
5. Chaque indicateur du catalogue porte tous ses champs (affichage.CHAMPS_CATALOGUE).

controler() rend une liste de (niveau, texte), niveau « bloquant », « à regarder » ou « info ». bloquer() lève une
erreur s'il y a un bloquant ; outils/verifier_changement.py reprend les mêmes contrôles dans son compte rendu.
"""
from __future__ import annotations

import csv
import html as H
import json
import re
from pathlib import Path

from . import affichage as AF

# 20 indicateurs : professions (dont une rare et un mode d'exercice), structures, distances, profil, recours
INDICATEURS = ["prof:psychologue:all", "prof:psychiatre:all", "prof:q_psychiatrie_enfant:all", "prof:psychologue:lib",
               "prof:medecin_generaliste:all", "prof:infirmier:all", "prof:masseur_kinesitherapeute:all",
               "prof:sage_femme:all", "lieux_lieu_cmp_adultes", "lieux_lieu_cmp_enfants", "lieux_lieu_cattp",
               "lieux_lieu_cmpp", "lieux_lieu_csapa", "dist_lieu_cmp_adultes", "dist_lieu_urgences", "revenu_median",
               "taux_pauvrete", "part_0_14", "densite_pop", "suicides"]
# territoires nommés par l'audit (Ain, Cher, Vierzon, Colmar), d'autres choisis à pas fixe dans chaque niveau
NOMMES = [("dep", "01"), ("dep", "18"), ("reg", "84"), ("reg", "24")]
NOMS_EPCI = ("Vierzon", "Colmar")
N_TERRITOIRES = 20


def echantillon(sd: dict) -> list[tuple[str, str]]:
    us = sd["niveaux"]
    out = list(NOMMES)
    for mot in NOMS_EPCI:
        c = next((u["c"] for u in us["epci"]["units"] if mot in u["nm"]), None)
        if c:
            out.append(("epci", c))
    # puis, à pas fixe dans chaque niveau, sans doublon, jusqu'à N_TERRITOIRES
    for lv, n in (("dep", 6), ("epci", 6), ("reg", 2)):
        codes = sorted(u["c"] for u in us[lv]["units"])
        pas, ajoutes = max(1, len(codes) // (n + 1)), 0
        for c in codes[pas::pas] + codes:
            if ajoutes == n or len(out) == N_TERRITOIRES:
                break
            if (lv, c) not in out:
                out.append((lv, c))
                ajoutes += 1
    return out


def _texte(fragment: str) -> str:
    t = H.unescape(re.sub(r"<[^>]+>", "\x00", fragment))
    return [x.strip() for x in t.split("\x00") if x.strip()]


def _fiche(site: Path, lv: str, code: str) -> dict:
    """Valeur, repère et textes des lignes marquées data-ind de la fiche d'un territoire."""
    f = site / "territoire" / lv / f"{code}.html"
    if not f.exists():
        return {}
    s = f.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r'<tr[^>]*data-ind="([^"]+)"[^>]*>(.*?)</tr>', s, re.S):
        tds = re.findall(r'<td class="v( np)?">(.*?)</td>\s*<td class="v m">(.*?)</td>', m.group(2), re.S)
        if not tds:
            # fiche B+ (étape 2, 31 octobre 2026) : la valeur en gras dans td.v, ou son statut ; le repère dans la
            # description de la réglette, « valeur, position, nom du repère valeur ; … »
            v = re.search(r'<td class="v">(.*?)</td>', m.group(2), re.S)
            if not v:
                continue
            st = re.search(r'<span class="statut">(.*?)</span>', v.group(1), re.S)
            b = re.search(r"<b>(.*?)</b>", v.group(1), re.S)
            aria = re.search(r'<div class="rg[^"]*"[^>]*aria-label="([^"]*)"', m.group(2))
            parts = H.unescape(aria.group(1)).split(" ; ")[0].split(", ") if aria else []
            # le repère : l'ensemble des territoires du niveau, ou, pour les indicateurs comparés à la médiane, le
            # territoire médian (la position manque quand la valeur n'est pas publiée)
            nom = next((p for p in parts if p.startswith("ensemble des ")), None) or \
                next((p for p in parts if re.search(r"\bmédiane? ", p)), None)
            ref = re.search(r"(\S*\d[\d   ]*(?:,\d+)?)(?:[\s  ]km)?$", nom) if nom else None
            out[m.group(1)] = {"v": "" if st or not b else re.sub(r"[\s  ]km$", "", _texte(b.group(1))[0]),
                               # statut : écrit à la place de la valeur, ou en note sous elle (« valeur nulle dans la
                               # source »), l'unité (« pour 10 000 ») mise à part
                               "statut": _texte(st.group(1))[0] if st else next(
                                   (t for t in _texte(v.group(1))[1:] if not t.startswith("pour ")
                                    and not re.search(r"(sous|au-dessus de|au niveau de) l'ensemble$", t)), ""),
                               "ref": ref.group(1).strip() if ref else None,
                               "brut": _texte(m.group(2))}
            continue
        np_, val, ref = tds[0]
        tv = _texte(val)
        out[m.group(1)] = {"v": "" if np_ else (tv[0] if tv else ""), "statut": tv[0] if np_ and tv else
                           next((t for t in tv[1:] if not re.match(r"^[\d  ]+$", t)), ""),
                           "ref": (_texte(ref) or [""])[0], "brut": tv}
    for m in re.finditer(r'<li data-ind="([^"]+)">(.*?)</li>', s, re.S):
        t = re.search(r'<span class="taux">(.*?)</span>', m.group(2), re.S)
        out[m.group(1)] = {"taux": H.unescape(re.sub(r"<[^>]+>", "", t.group(1))) if t else ""}
    return out


def _atelier(site: Path) -> dict | None:
    f = site / "presentation" / "atelier_donnees.js"
    if not f.exists():
        return None
    s = f.read_text(encoding="utf-8")
    return json.loads(s[s.index("{"):s.rstrip().rstrip(";").rindex("}") + 1])


def _js_cellule(A: dict, ident: str, lv: str, k: int) -> dict | None:
    """Ce que presentation/chiffres.js écrit pour une cellule, refait en Python à partir des mêmes données."""
    a = ((A.get("aff") or {}).get("lv") or {}).get(lv, {}).get(ident)
    zero = (A.get("aff") or {}).get("zero") or {}
    if a is None:
        return None
    i = A["aff"]["ind"].get(ident) or {}
    g = i.get("g", "taux")
    code = a["c"][k]
    st = A["aff"]["statuts"].get(code, "")
    if code == "a" and i.get("k") == "lieux":
        st = A["aff"]["aucune"]
    x = None if code == "r" else (a.get("x") or {}).get(str(k), A["val"][lv][ident][k])
    if x is not None and AF.arrondi(x, g) == 0 and not st and zero.get(i.get("k")):
        st = zero[i.get("k")]
    return {"v": AF.nombre(x, g), "ref": AF.nombre(a["r"], g), "statut": st}


def _atlas(site: Path) -> dict | None:
    fs = sorted(site.glob("atlas_donnees.*.js"))
    if not fs:
        return None
    s = fs[-1].read_text(encoding="utf-8")
    return json.JSONDecoder().raw_decode(s, s.index("{"))[0]


def _lire_csv(f: Path) -> dict[str, dict]:
    if not f.exists():
        return {}
    with f.open(encoding="utf-8-sig") as h:
        return {l["code"]: l for l in csv.DictReader(h, delimiter=";")}


def _num(x):
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return None


def coherence(site: Path, dernier: Path, sd: dict, T: AF.Affichage) -> list[tuple[str, str]]:
    out, ecarts, vus = [], [], 0
    A = _atelier(site)
    atlas = _atlas(site)
    rapports = {}
    for lv, code in echantillon(sd):
        fiche = _fiche(site, lv, code)
        if not fiche:
            ecarts.append(f"fiche {lv} {code} absente")
            continue
        u = sd["niveaux"][lv]["units"][T.pos[lv][code]]
        for ident in INDICATEURS:
            c = T.cellule(ident, lv, code)
            echelle = None
            if (c is None or (c["v"] is None and not c["statut"])) and lv == "epci" and u.get("p") in T.pos["dep"]:
                c, echelle = T.cellule(ident, "dep", u["p"], "dep"), "dep"
            if c is None:
                continue
            vus += 1
            attendu_v = c["v_txt"]
            lieu = f"{lv} {code} {ident}"
            # fiche du territoire
            if ident.startswith("lieux_") and "taux" in (fiche.get(ident) or {"taux": None}):
                t = (fiche.get(ident) or {}).get("taux")
                if t is not None and (c["n"] or 0) > 0:
                    if attendu_v and not t.startswith(attendu_v + " "):
                        ecarts.append(f"fiche {lieu} : « {t} » au lieu de {attendu_v}")
                    if c["ref_txt"] and not t.endswith(" " + c["ref_txt"]):
                        ecarts.append(f"fiche {lieu} : repère « {t} » au lieu de {c['ref_txt']}")
                    if c["statut_txt"] and c["statut_txt"] not in t:
                        ecarts.append(f"fiche {lieu} : statut « {c['statut_txt']} » absent de « {t} »")
            elif ident in fiche:
                fl = fiche[ident]
                # une valeur nulle dite par son statut (« aucune structure ») plutôt que par « 0 », statut vérifié dessous
                if fl["v"] != attendu_v and not (fl["v"] == "" and fl["statut"] and c["statut"]):
                    ecarts.append(f"fiche {lieu} : valeur « {fl['v']} » au lieu de « {attendu_v} »")
                if fl["ref"] is not None and fl["ref"] != c["ref_txt"]:
                    ecarts.append(f"fiche {lieu} : repère « {fl['ref']} » au lieu de « {c['ref_txt']} »")
                if c["statut_txt"] and not any(c["statut_txt"] in t for t in fl["brut"]) and c["statut_txt"] != fl["statut"]:
                    ecarts.append(f"fiche {lieu} : statut « {c['statut_txt']} » absent ({fl['brut']})")
            # comparateur et Croiser, mêmes données (presentation/atelier_donnees.js)
            if A is not None:
                lv2, code2 = (("dep", u["p"]) if echelle else (lv, code))
                cs = [x["c"] for x in A["units"][lv2]]
                if code2 in cs and ident in (A.get("val", {}).get(lv2) or {}):
                    j = _js_cellule(A, ident, lv2, cs.index(code2))
                    if j is None:
                        ecarts.append(f"comparateur et Croiser {lieu} : indicateur absent des données publiées")
                    else:
                        if j["v"] != attendu_v:
                            ecarts.append(f"comparateur et Croiser {lieu} : valeur « {j['v']} » au lieu de « {attendu_v} »")
                        if j["ref"] != c["ref_txt"]:
                            ecarts.append(f"comparateur et Croiser {lieu} : repère « {j['ref']} » au lieu de « {c['ref_txt']} »")
                        st = (c["statut_txt"] if c["statut"] != "departement" else "") or c["note"]
                        if j["statut"] != st:
                            ecarts.append(f"comparateur et Croiser {lieu} : statut « {j['statut']} » au lieu de « {st} »")
            # fichiers publiés, pleine précision
            ecarts += _csv(dernier, lv if not echelle else "dep", code if not echelle else u["p"], ident, c, T)
            # atlas : densités des professions dans leur unité, arrondies comme les autres pages, repère somme sur somme
            if atlas is not None and ident.startswith("prof:") and not echelle:
                ecarts += _atlas_ecart(atlas, lv, code, ident, c)
            # rapport du département ou de la région, phrase des densités
            if lv in ("dep", "reg") and ident in ("prof:psychologue:all", "prof:psychiatre:all"):
                ecarts += _rapport_ecart(site, dernier, lv, code, ident, c, rapports)
    out.append(("info", f"Cohérence entre les pages, {vus} valeurs de {len(echantillon(sd))} territoires et "
                        f"{len(INDICATEURS)} indicateurs comparées sur la fiche, le comparateur et Croiser, l'atlas, "
                        f"le rapport et les fichiers CSV"))
    for e in dict.fromkeys(ecarts):
        # l'atlas suit la règle des autres pages depuis le 5 novembre 2026 (C4) : un écart y arrête la construction ; le
        # rapport par territoire, refait par l'exécution complète seulement, reste à regarder
        out.append(("à regarder" if e.startswith("rapport") or ATTENDU_AVANT_EXECUTION in e else "bloquant",
                    "Cohérence, " + e))
    return out


def _csv(dernier: Path, lv: str, code: str, ident: str, c: dict, T: AF.Affichage) -> list[str]:
    lieu = f"{lv} {code} {ident}"
    out = []
    if ident.startswith("prof:"):
        _, p, mode = ident.split(":")
        l = _lire_csv_cache(dernier / f"effectifs_{lv}_{mode}.csv").get(code)
        if l is None or f"n_{p}" not in l:
            return [f"CSV {lieu} : ligne ou colonne absente de effectifs_{lv}_{mode}.csv"]
        n, pop = _num(l[f"n_{p}"]), _num(l.get("population"))
        if n != c["n"]:
            out.append(f"CSV {lieu} : effectif {n} au lieu de {c['n']}")
        if n is not None and pop and AF.nombre(n / pop * c["fac"]) != c["v_txt"]:
            out.append(f"CSV {lieu} : densité {n / pop * c['fac']} au lieu de {c['v_txt']}")
    elif ident.startswith("lieux_"):
        l = _lire_csv_cache(dernier / f"lieux_soins_{lv}.csv").get(code)
        typ = ident[6:]
        if l is None or f"n_{typ}" not in l:
            return [f"CSV {lieu} : ligne ou colonne absente de lieux_soins_{lv}.csv"]
        if _num(l[f"n_{typ}"]) != c["n"]:
            out.append(f"CSV {lieu} : {l[f'n_{typ}']} structures au lieu de {c['n']}")
        t = _num(l.get(f"pour_100000_{typ}"))
        if "taux_non_publies" not in l:
            out.append(f"CSV lieux_soins_{lv}.csv : fichier écrit avant la règle commune des taux (pas de colonne "
                       f"taux_non_publies), à refaire par la prochaine exécution")
        elif (t is None) != (c["v"] is None) or (t is not None and AF.nombre(t) != c["v_txt"]):
            out.append(f"CSV {lieu} : taux « {l.get(f'pour_100000_{typ}')} » au lieu de « {c['v_txt'] or c['statut_txt']} »")
        elif c["statut"] == "non_publie" and not l.get("taux_non_publies"):
            out.append(f"CSV {lieu} : statut « non publié » absent de taux_non_publies")
    elif ident.startswith("dist_"):
        rows = _lire_lignes_cache(dernier / f"distances_lieux_{lv}.csv")
        l = next((r for r in rows if r["code"] == code and r["type"] == ident[5:]), None)
        if l is None:
            if c["v"] is not None:
                out.append(f"CSV {lieu} : ligne absente de distances_lieux_{lv}.csv")
        else:
            d = _num(l.get("distance_mediane_km"))
            if (d is None) != (c["v"] is None) or (d is not None and AF.nombre(d, "distance") != c["v_txt"]):
                out.append(f"CSV {lieu} : distance « {l.get('distance_mediane_km')} » au lieu de « {c['v_txt'] or c['statut_txt']} »")
            if c["statut"] == "non_recense" and l.get("recensement_complet") != "False":
                out.append(f"CSV {lieu} : « non recensé » sur les pages, recensement_complet vrai dans le fichier")
    else:
        odbl = "ODbL" in (T.ctx[ident][1].get("licence") or "")
        l = _lire_csv_cache(dernier / f"contexte_{lv}{'_odbl' if odbl else ''}.csv").get(code)
        if l is not None and ident in l:
            v = _num(l[ident])
            if (v is None) != (c["v"] is None) or (v is not None and AF.nombre(v, c["genre"]) != c["v_txt"]):
                out.append(f"CSV {lieu} : « {l[ident]} » au lieu de « {c['v_txt'] or c['statut_txt']} »")
    return out


# fichier lieux_soins_<niveau>.csv écrit avant la règle commune des taux (branche v2-lieux-csv, 30 octobre 2026) :
# avertissement nommé tant que la version n'a pas été refaite, et non blocage ; dès que le fichier porte la colonne
# taux_non_publies, tout écart de taux avec les pages bloque
ATTENDU_AVANT_EXECUTION = "fichier écrit avant la règle commune des taux"
_CACHE: dict = {}


def _lire_csv_cache(f: Path) -> dict:
    if f not in _CACHE:
        _CACHE[f] = _lire_csv(f)
    return _CACHE[f]


def _lire_lignes_cache(f: Path) -> list:
    k = ("l", f)
    if k not in _CACHE:
        if f.exists():
            with f.open(encoding="utf-8-sig") as h:
                _CACHE[k] = list(csv.DictReader(h, delimiter=";"))
        else:
            _CACHE[k] = []
    return _CACHE[k]


def _atlas_ecart(D: dict, lv: str, code: str, ident: str, c: dict) -> list[str]:
    """L'atlas écrit chaque densité dans l'unité de la profession qu'il lit dans ses données (D["unites"], 10 000 ou
    100 000 habitants) et l'arrondit comme les autres pages (noyau.js, FAC et fD, C4 du 5 novembre 2026). Le contrôle
    refait ce calcul depuis les données de l'atlas et compare l'unité, la valeur et le repère à ceux de la fiche."""
    _, p, mode = ident.split(":")
    L = D["niveaux"].get(lv)
    if not L or p not in L["n"]:
        return []
    k = next((i for i, u in enumerate(L["units"]) if u["c"] == code), None)
    if k is None:
        return []
    fac = (D.get("unites") or {}).get(p, 10000)
    a = L["n"][p][mode]
    d = a[k] / L["units"][k]["pop"] * fac if L["units"][k]["pop"] else None
    P = sum(u["pop"] for u in L["units"])
    r = sum(x for x in a if x) / P * fac if P else None
    out = []
    if fac != c["fac"]:
        return [f"atlas {lv} {code} {ident} : densité écrite pour {fac:,} habitants, pour {c['fac']:,} sur les autres pages"
                .replace(",", AF.FINE)]
    if d is not None and AF.nombre(d) != c["v_txt"]:
        out.append(f"atlas {lv} {code} {ident} : « {AF.nombre(d)} » au lieu de « {c['v_txt']} »")
    if r is not None and AF.nombre(r) != c["ref_txt"]:
        out.append(f"atlas {lv} {code} {ident} : repère « {AF.nombre(r)} » au lieu de « {c['ref_txt']} »")
    return out


def _rapport_ecart(site: Path, dernier: Path, lv: str, code: str, ident: str, c: dict, cache: dict) -> list[str]:
    f = site / "territoires" / dernier.name / f"{lv}-{code}-sante-mentale.html"
    if not f.exists():
        return []
    if f not in cache:
        cache[f] = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", f.read_text(encoding="utf-8"))))
    t = cache[f]
    nom = {"prof:psychologue:all": "psychologues", "prof:psychiatre:all": "psychiatres"}[ident]
    m = re.search(rf"([\d   ]+) {nom} exercent dans (?:le département|la région), soit ([\d,   ]+) pour "
                  rf"10[   ]000 habitants[^.]*?contre (?:[^.]*? et )?([\d,   ]+) "
                  rf"(?:en moyenne dans les|pour l'ensemble des)", t)
    if not m:
        return [f"rapport {lv} {code} {ident} : phrase des densités introuvable"]
    norm = lambda x: re.sub(r"[   ]", "", x)  # noqa: E731
    out = []
    if norm(m.group(2)) != norm(c["v_txt"]):
        out.append(f"rapport {lv} {code} {ident} : densité « {m.group(2).strip()} » au lieu de « {c['v_txt']} »")
    if norm(m.group(3)) != norm(c["ref_txt"]):
        out.append(f"rapport {lv} {code} {ident} : repère « {m.group(3).strip()} » au lieu de « {c['ref_txt']} »")
    if "en moyenne dans les" in m.group(0):
        out.append(f"rapport {lv} {code} {ident} : repère nommé « en moyenne dans les », au lieu de « l'ensemble des »")
    return out


# -- chaînes de maquette, dates, zéros ------------------------------------------------------------------------------
# « trajets réels » ou « dépassements réellement facturés » restent permis, seules les chaînes de maquette sont refusées
INTERDITS = [(re.compile(r"\bréelles?\b|\b(?:version|donnée|page|carte|offre)s? (?:réel|complet)(?:le)?s?\b", re.I),
              "« réelle », ou « version réelle » et ses semblables"),
             (re.compile(r"(?<!par )\bexemples?\b(?! :)", re.I), "« exemple » hors de « par exemple »")]


def _visible(s: str) -> str:
    s = re.sub(r"<(script|style|svg)[\s\S]*?</\1>", " ", s)
    return H.unescape(re.sub(r"<[^>]+>", " ", s))


def pages_presentation(site: Path) -> list[Path]:
    noms = ["index.html", "croiser.html", "comparer.html", "zone.html", "domaines.html", "liens.html", "a-venir.html"]
    fs = [site / n for n in noms if (site / n).exists()]
    for d in ("territoire", "indicateur", "domaine"):
        fs += sorted((site / d).rglob("*.html")) if (site / d).exists() else []
    return fs


def maquette(site: Path) -> list[tuple[str, str]]:
    out, n = [], 0
    fichiers = pages_presentation(site) + sorted((site / "presentation").glob("*.js"))
    for f in fichiers:
        s = f.read_text(encoding="utf-8")
        n += 1
        if 'href="#"' in s:
            out.append(("bloquant", f"Lien vide href=\"#\" dans {f.relative_to(site)}"))
        if f.suffix == ".html":
            v = _visible(s)
            for motif, nom in INTERDITS:
                m = motif.search(v)
                if m:
                    out.append(("bloquant", f"Chaîne de maquette {nom} dans {f.relative_to(site)} : "
                                            f"« {v[max(0, m.start() - 40):m.end() + 40].strip()} »"))
    return out + [("info", f"Chaînes de maquette et liens vides cherchés dans {n} pages et scripts")]


def dates(site: Path, dernier: Path) -> list[tuple[str, str]]:
    """Une seule date par source : la date du répertoire écrite dans les pages est celle du journal des sources, et le
    fichier de concordance la donne pareil."""
    out = []
    d = AF.date_rpps(dernier)
    if not d:
        return [("bloquant", "Date du répertoire RPPS absente du journal des sources (journal.json)")]
    f = dernier / "concordance_effectifs.csv"
    if f.exists():
        with f.open(encoding="utf-8-sig") as h:
            autres = {l["date_rpps"][:10] for l in csv.DictReader(h, delimiter=";") if l.get("date_rpps")}
        iso = AF.dates_sources(dernier).get("RPPS activité")
        if autres and autres != {iso}:
            out.append(("bloquant", f"Date du RPPS, {sorted(autres)} dans concordance_effectifs.csv, {iso} dans le journal"))
    motif = re.compile(r"(?:RPPS|répertoire(?: des professionnels)?(?: RPPS)?)(?:\s+\w+){0,3}? du (\d{1,2}(?:er)? \w+ \d{4})")
    vues = {}
    for p in pages_presentation(site):
        for m in motif.finditer(_visible(p.read_text(encoding="utf-8"))):
            vues.setdefault(m.group(1), p)
    for dt, p in vues.items():
        if dt != d:
            out.append(("bloquant", f"Date du répertoire « {dt} » dans {p.relative_to(site)}, au lieu de « {d} »"))
    return out + [("info", f"Date du répertoire, {d}, une seule dans les pages")]


ZERO = re.compile(r"^0(?:,0+)?$")


def zeros(site: Path) -> list[tuple[str, str]]:
    out, n = [], 0
    for f in sorted((site / "territoire").rglob("*.html")) if (site / "territoire").exists() else []:
        for ident, l in _fiche(site, f.parent.name, f.stem).items():
            if "v" in l and ZERO.match(l["v"] or ""):
                n += 1
                if not l["statut"]:
                    out.append(("bloquant", f"« 0 » sans statut, {f.parent.name} {f.stem} {ident}"))
    return out[:30] if out else [("info", f"Zéros des fiches, {n} trouvés, chacun avec son statut")]


def catalogue(sd: dict, dernier: Path) -> list[tuple[str, str]]:
    manque = AF.champs_manquants(AF.catalogue(sd, dernier))
    if not manque:
        return [("info", "Catalogue, chaque indicateur porte tous ses champs")]
    out = []
    for champ, ids in sorted(manque.items()):
        out.append(("bloquant", f"Catalogue, champ « {champ} » absent pour {len(ids)} indicateurs, dont "
                                f"{', '.join(ids[:5])}"))
    return out


def reperes_comparateur(site: Path, T: AF.Affichage) -> list[tuple[str, str]]:
    """Repère et médiane de chaque indicateur, à chaque niveau, identiques dans le comparateur et Croiser (données de
    l'atelier, A.aff) et sur les fiches (règle d'affichage), tels qu'ils s'écrivent. Ajouté le 31 octobre 2026 : le
    comparateur donnait 14 pour le taux de pauvreté de l'ensemble des intercommunalités (moyenne simple, avant la règle
    unique), la fiche 16,3 (taux de l'ensemble, pondéré par les habitants)."""
    A = _atelier(site)
    if A is None:
        return [("à regarder", f"Repères du comparateur, {ATTENDU_AVANT_EXECUTION} (atelier_donnees.js absent)")]
    out, n = [], 0
    for lv, inds in ((A.get("aff") or {}).get("lv") or {}).items():
        for ident, a in inds.items():
            S = T.serie(ident, lv)
            if S is None:
                continue
            g = ((A["aff"]["ind"].get(ident) or {}).get("g")) or S.genre
            n += 1
            for nom, js, py in (("repère", a.get("r"), S.ref), ("médiane", a.get("m"), S.med)):
                if AF.nombre(js, g) != AF.nombre(py, g):
                    out.append(("bloquant", f"{nom} de {ident} ({AF.NIV_PLURIEL[lv]}) : {AF.nombre(js, g)} dans le "
                                            f"comparateur, {AF.nombre(py, g)} sur les fiches"))
    return out or [("info", f"Repères et médianes identiques dans le comparateur et sur les fiches ({n} séries)")]


def controler(site: Path, dernier: Path, sd: dict | None = None) -> list[tuple[str, str]]:
    site, dernier = Path(site), Path(dernier)
    sd = sd or json.loads((dernier / "site_data.json").read_text(encoding="utf-8"))
    T = AF.Affichage(sd, dernier)
    _CACHE.clear()
    return (coherence(site, dernier, sd, T) + reperes_comparateur(site, T) + maquette(site) + dates(site, dernier)
            + zeros(site) + catalogue(sd, dernier))


def bloquer(site: Path, dernier: Path, sd: dict | None = None) -> list[tuple[str, str]]:
    r = controler(site, dernier, sd)
    b = [t for n, t in r if n == "bloquant"]
    if b:
        raise RuntimeError(f"Règle d'affichage, {len(b)} contrôles bloquants :\n- " + "\n- ".join(b[:40]))
    return r
