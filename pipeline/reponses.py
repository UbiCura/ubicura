"""Réponses directes de la recherche de l'en-tête (navigation, étape 2, validée par Lucas le 8 novembre 2026).

« psychiatres rodez » : la recherche reconnaît un indicateur et un lieu, rattache une commune à son intercommunalité, et
montre la valeur de la fiche de ce territoire. Les chiffres viennent de la règle d'affichage unique
(affichage.Affichage.cellule), la même que la fiche, Comparer et l'atlas : un fichier par territoire,
territoire/<niveau>/<code>.json, chargé seulement quand il sert.

Règle des réponses directes :
- une commune répond par son intercommunalité, et la réponse le dit (« dont Rodez fait partie ») ;
- un indicateur publié seulement au département répond au département de rattachement de l'intercommunalité (celui
  dont la fiche montre les chiffres), et la réponse le dit ;
- la position s'écrit comme sur la ligne de la fiche : l'écart ou le sens de la valeur, puis « mais » quand la position
  va en sens contraire (bandes_fiche.mais, affichage.avant_position) ; aucun inscrit s'écrit « aucun », avec la part
  des territoires dans le même cas, jamais avec une position ;
- une valeur non diffusée, non recensée ou absente le dit, comme la fiche ;
- un indicateur marqué sensible au catalogue ne répond jamais d'office avec un indicateur de santé mentale (la réponse
  ne porte que sur l'indicateur demandé)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import affichage as AF
from . import themes as TH
from .affichage import AUCUNE_STRUCTURE
from .fiche_territoire import NIV_PLURIEL, Donnees, _part_aucun, de_nom

# devant un nom sans article : « en Bretagne », « en Île-de-France », « en Ille-et-Vilaine », mais « à Mayotte »,
# « à La Réunion », « à Paris » (audit indépendant du 8 novembre 2026, « dans Bretagne »)
A_ILE_VILLE = {("reg", "04"), ("dep", "974"), ("reg", "06"), ("dep", "976"), ("dep", "75")}
EN_OUTRE_MER = {("reg", "01"), ("dep", "971"), ("reg", "02"), ("dep", "972"), ("reg", "03"), ("dep", "973")}


def dans(lv: str, code: str, nom: str) -> str:
    """« dans l'Aveyron », « dans les Yvelines », « dans la CA Rodez Agglomération », « en Bretagne », « à Mayotte » :
    l'article des titres de fiche (fiche_territoire.de_nom, typeLiaison de l'INSEE), tourné avec « dans »."""
    if (lv, code) in A_ILE_VILLE or (lv == "epci" and code.startswith("C")):
        return "à " + nom   # une île, une ville, une commune hors intercommunalité (« à Ouessant »)
    if (lv, code) in EN_OUTRE_MER:
        return "en " + nom   # « en Guadeloupe », « en Guyane »
    d = de_nom(lv, code, nom)
    for de, da in (("de la ", "dans la "), ("de l’", "dans l’"), ("de l'", "dans l’"), ("du ", "dans le "),
                   ("des ", "dans les ")):
        if d.startswith(de):
            return da + d[len(de):]
    if lv in ("reg", "dep"):
        return "en " + nom   # région ou département sans article : « en Occitanie », « en Saône-et-Loire »
    return "dans " + nom     # « dans Toulouse Métropole »


def pluriel_nom(lib: str) -> str:
    """Pluriel d'un nom de profession pour la phrase de réponse : comme lecture.pluriel, mais « et » n'arrête pas
    l'accord (« chirurgiens thoraciques et cardiovasculaires »), rien ne s'accorde après une virgule (« médecins,
    spécialités non renseignées ») et les sigles gardent leurs capitales (« ORL »). Audit du 8 novembre 2026."""
    from .lecture import _MOTS_LIAISON
    out, fige, paren = [], False, False
    for mot in lib.split(" "):
        m = re.match(r"^(.*?)([,.;]*)$", mot)
        corps, ponct = m.group(1), m.group(2)
        # rien ne s'accorde entre parenthèses : « médecins spécialistes (toutes spécialités) », jamais « spécialités)s »
        # (contre-audit du 8 novembre 2026)
        if paren or corps.startswith("("):
            paren = not corps.endswith(")")
            out.append((corps if corps.strip("()").isupper() else corps.lower()) + ponct)
            continue
        sigle = corps.strip("()").isupper() and len(corps.strip("()")) > 1
        bas = corps if sigle else corps.lower()
        if fige or not bas or sigle or bas.startswith("(") or (bas.split("'")[0] in _MOTS_LIAISON and bas != "et"):
            fige = fige or (bool(bas) and not sigle and bas != "et" and not bas.startswith("("))
            out.append(bas + ponct)
            continue
        if bas == "et":
            out.append(bas)
            continue
        morceaux = bas.split("-")
        parts = []
        for k, p in enumerate(morceaux):
            if k < len(morceaux) - 1 and p.endswith("o") or not p or p.endswith(("s", "x")):
                parts.append(p)
            elif p.endswith("al"):
                parts.append(p[:-2] + "aux")
            else:
                parts.append(p + "s")
        out.append("-".join(parts) + ponct)
        if "," in ponct:
            fige = True
    return " ".join(out)


def singulier_nom(lib: str) -> str:
    """Nom d'une profession au singulier dans la phrase de réponse : le libellé du catalogue en minuscules, sauf les
    sigles (« médecin ORL »)."""
    return " ".join(m if m.strip("(),").isupper() and len(m.strip("(),")) > 1 else m.lower() for m in lib.split(" "))


def relation(T, c: dict) -> tuple[str, bool]:
    """Ce que la ligne de la fiche écrit à côté de la valeur : (« plus loin que l'ensemble (6,3 km), mais plus près que
    64 % des départements », True si l'ensemble y est déjà écrit). Aucun inscrit : « comme dans 90 % des
    intercommunalités », sans position."""
    from .bandes_fiche import mais
    if c["statut"] == "aucun":
        part = _part_aucun(T, c)
        return (f"comme dans {part} des {NIV_PLURIEL[c['lv']]}" if part else ""), False
    pos = c["pos_txt"] or ""
    ecrit = c["kind"] in ("prof", "lieux") and bool(c["e_txt"]) and c["statut"] != "petit"
    m = mais(c["e"], pos, c["kind"], c["e_mots"], c["statut"], c["v_txt"], c["ref_txt"])
    avant = AF.avant_position(c["e_mots"], ecrit, m, c["ref_txt"], c["kind"], c["v_txt"])
    if not pos:
        return avant, "(" in avant
    if not avant:
        return pos, False
    return f"{avant}{', mais ' if m else ', '}{pos}", "(" in avant or avant.startswith("ensemble ")


def limite_txt(dn, ident: str, lv: str, code: str) -> str:
    """La limite que la fiche pose à côté de la valeur, avec son « ! » : la phrase propre au territoire si elle existe,
    sinon la phrase courte (contre-audit du 8 novembre 2026, « limites là où la donnée est montrée »)."""
    k = TH.cle(ident)
    lim = dn.limite(k, lv, code) or (dn.limite(ident, lv, code) if ident != k else None)
    if not lim:
        return ""
    return (lim.get("territoire") or lim.get("court") or "").strip()


def ecrire(sd: dict, dernier: Path, site: Path) -> int:
    T = AF.Affichage(sd, dernier)
    dn = Donnees(sd, dernier)
    code_reg = {u["nm"]: u["c"] for u in sd["niveaux"]["reg"]["units"]}
    reg_dep = {u["c"]: code_reg.get(u.get("p")) for u in sd["niveaux"]["dep"]["units"]}
    cat = AF.catalogue(sd, dernier)
    # nom à écrire dans la phrase (au pluriel pour une profession, comme les tuiles de la fiche) et unité de la valeur
    # et, pour une profession, le nom au singulier pour un seul inscrit (« 1 pédopsychiatre dans … »)
    meta = {TH.cle(e["id"]): [pluriel_nom(e["nom_court"]) if e["id"].startswith("prof:")
                              else e["nom_court"].split(", pour ")[0], e.get("unite") or ""]
            + ([singulier_nom(e["nom_court"])] if e["id"].startswith("prof:") else []) for e in cat}
    (site / "presentation").mkdir(parents=True, exist_ok=True)
    (site / "presentation" / "reponses.json").write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n = 0
    for lv in ("reg", "dep", "epci"):
        dossier = site / "territoire" / lv
        dossier.mkdir(parents=True, exist_ok=True)
        for u in sd["niveaux"][lv]["units"]:
            ind = {}
            for e in cat:
                if lv not in (e.get("niveaux") or []):
                    continue
                c = T.cellule(e["id"], lv, u["c"])
                if c is None:
                    continue
                # aucune structure d'un type recensé s'écrit « aucune », comme la fiche, même quand le taux n'est pas
                # publié (« CATTP : 0 … non publié », contre-audit du 8 novembre 2026)
                zero_lieux = c["kind"] == "lieux" and c["n"] == 0
                aucun = c["statut"] == "aucun" or zero_lieux
                rel, ens_ecrit = ("", False) if zero_lieux and c["statut"] != "aucun" else relation(T, c)
                sans_valeur = not aucun and not c["v_txt"]
                statut = AUCUNE_STRUCTURE if zero_lieux else (c["statut_txt"] or c["note"])
                # effectif, valeur, phrase de position, limite, repère, statut ou note du zéro, genre : ce que la fiche
                # écrit ; sans valeur, ni position ni repère
                ind[TH.cle(e["id"])] = ["aucun" if aucun else c["n_txt"], "" if aucun else c["v_txt"],
                                        "" if sans_valeur else rel, limite_txt(dn, e["id"], lv, u["c"]),
                                        "" if ens_ecrit or sans_valeur else c["ref_lib"],
                                        "" if ens_ecrit or sans_valeur else c["ref_txt"], statut, c["kind"]]
            j = {"nom": u["nm"], "dans": dans(lv, u["c"], u["nm"]), "de": de_nom(lv, u["c"], u["nm"]),
                 "pop": u.get("pop"), "ind": ind}
            if lv == "epci" and u.get("p"):
                j["dep"] = u["p"]   # département de rattachement, pour les indicateurs publiés seulement au département
            if lv == "dep" and reg_dep.get(u["c"]):
                j["reg"] = reg_dep[u["c"]]   # région, pour les indicateurs publiés seulement par région
            (dossier / f"{u['c']}.json").write_text(json.dumps(j, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            n += 1
    return n
