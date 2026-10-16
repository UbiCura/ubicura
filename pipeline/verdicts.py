"""Verdicts de la vérification à la main des CMP (contenus/verdicts_verification.csv, décisions de Lucas du 15 octobre 2026).

Chaque verdict porte la clé de la structure dans la liste de vérification (outils/structures_verifiees.py
a-verifier), formée du gestionnaire, du premier numéro FINESS, du nom de la commune et du début du nom simplifié.
- doublon, ferme, introuvable. La structure et ses lignes par public sont retirées, et consignées parmi les
  inscriptions non retenues avec la raison.
- pas_un_cmp. La structure quitte les CMP. Elle est rangée dans son type réel (type_reel) quand il est donné, sinon
  retirée comme ci-dessus.
- existe. La structure est gardée, remise si la liste vérifiée de son établissement l'avait écartée, et son niveau
  de confirmation devient « examinée à la main » quand aucune liste officielle ne la confirmait. Une adresse corrigée
  (adresse_reelle, « rue, code postal commune ») remplace celle des bases.
- tranche. Constat d'ensemble sur plusieurs structures, sans effet ligne à ligne.
Une réponse sans source vérifiable ne change pas le statut d'une structure (règle du 15 octobre 2026), elle n'est
donc jamais consignée comme verdict.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import config
from .util import JOURNAL, log

FICHIER = config.RACINE / "contenus" / "verdicts_verification.csv"
RETIRES = {"doublon": "doublon d'une autre structure", "ferme": "fermée", "introuvable": "introuvable sur toutes les sources",
           "pas_un_cmp": "n'est pas un CMP"}
PARENT = "lieu_cmp"


def _simple(s) -> str:
    from .lieux import _simple as s_
    return s_(s)


def _txt(v) -> str:
    return v if isinstance(v, str) else ""


def cle(ej, finess, commune_nom, nom) -> str:
    """Même clé que la liste de vérification (outils/structures_verifiees.py)."""
    return "|".join([_txt(ej), _txt(finess).split(",")[0], _txt(commune_nom), _simple(_txt(nom))[:40]])


def charger() -> pd.DataFrame:
    cols = ["cle", "etablissement", "structure", "verdict", "type_reel", "adresse_reelle", "commentaire", "date"]
    if not FICHIER.exists():
        return pd.DataFrame(columns=cols)
    v = pd.read_csv(FICHIER, sep=";", dtype=str).fillna("")
    v = v[v["verdict"].isin(list(RETIRES) + ["existe", "tranche"])]
    return v.drop_duplicates("cle", keep="last").reindex(columns=cols, fill_value="")


def _cles(r, nom_com: pd.Series) -> set:
    """Clés possibles d'une structure, selon le nom (affiché, d'origine, de FINESS) et le numéro retenus par la liste."""
    nums = [n for n in (_txt(r.get("finess")), _txt(r.get("finess_rapproche"))) if n]
    tous = sorted({n for c in ("finess", "finess_rapproche", "finess_absorbes") for n in _txt(r.get(c)).split(",") if n})
    if tous:
        nums.append(tous[0])
    nums = list(dict.fromkeys(nums)) or [""]
    noms = [n for n in (_txt(r.get("nom_affiche")), _txt(r.get("nom")), _txt(r.get("nom_finess"))) if n]
    com = nom_com.get(r.get("commune"), "")
    return {cle(r.get("ej"), f, com, n) for f in nums for n in noms}


def _index(x: pd.DataFrame, nom_com: pd.Series) -> dict:
    out = {}
    for i, r in x[x["type"] == PARENT].iterrows():
        for k in _cles(r, nom_com):
            out.setdefault(k, i)
    return out


def _adresse(texte: str, commune_actuelle, ref):
    """« 11 bis boulevard des Danois, 02220 Braine » donne l'adresse et le code de la commune (même département que
    le code postal). Sans code postal, l'adresse seule et la commune actuelle."""
    m = re.match(r"^(.*?),\s*(\d{5})\s+(.+)$", texte.strip())
    if not m:
        return texte.strip(), commune_actuelle
    voie, cp, nom = m.group(1).strip(), m.group(2), m.group(3).strip()
    c = ref.communes
    dep = cp[:3] if cp.startswith("97") else ("2A" if cp[:3] in ("200", "201") else "2B" if cp[:2] == "20" else cp[:2])
    cand = c[(c["nom"].map(_simple) == _simple(nom)) & (c["dep"] == dep)]
    return voie, (cand["code"].iloc[0] if len(cand) else commune_actuelle)


def appliquer(lieux: pd.DataFrame, avant: pd.DataFrame | None, ref, centres: dict | None = None,
              hors_ligne: bool = True, v: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict]:
    """Applique les verdicts aux structures. avant, les structures avant la liste vérifiée (pour remettre une
    structure qu'elle avait écartée). Renvoie les structures et un compte rendu (verdicts appliqués par sorte,
    inscriptions retirées, verdicts sans structure correspondante)."""
    from .lieux import _geocoder
    v = charger() if v is None else v
    rendu = {"appliques": {}, "retirees": [], "non_trouves": [], "remises": 0, "retypees": 0, "adresses": 0}
    if v.empty or lieux.empty:
        return lieux, rendu
    x = lieux.copy()
    for c in ("verdict", "examen"):
        if c not in x:
            x[c] = None
    nom_com = ref.communes.set_index("code")["nom"]
    rattach = ref.communes.set_index("code")[["epci", "dep", "reg"]]
    labels = {t[0]: t for t in config.LIEUX_TYPES}
    enfants = [t[0] for t in config.LIEUX_TYPES if t[4].get("parent") == PARENT]
    idx = _index(x, nom_com)
    absents = None
    if avant is not None and len(avant):
        absents = avant[~avant.set_index(["type", "lieu"]).index.isin(x.set_index(["type", "lieu"]).index)]
    idx_avant = _index(absents, nom_com) if absents is not None else {}
    retirer, ajouter = [], []
    for r in v.itertuples():
        sorte = r.verdict
        if sorte == "tranche":
            continue
        i = idx.get(r.cle)
        if i is None and r.cle in idx_avant:
            # écartée par la liste vérifiée de son établissement
            j = idx_avant[r.cle]
            lieu = absents.at[j, "lieu"]
            if sorte == "existe":
                remise = absents[(absents["lieu"] == lieu) & absents["type"].isin([PARENT] + enfants)].copy()
                conf = remise["confirmation"] if "confirmation" in remise else pd.Series(None, index=remise.index)
                remise["confirmation"] = conf.where(conf.isin(["has_sirene", "has", "sirene"]), "examinee")
                remise["verdict"], remise["examen"] = "existe", r.commentaire
                ajouter.append(remise)
                rendu["remises"] += 1
            elif sorte == "pas_un_cmp" and r.type_reel in labels:
                ajouter.append(_retype(absents.loc[[j]], r, labels))
                rendu["retypees"] += 1
            rendu["appliques"][sorte] = rendu["appliques"].get(sorte, 0) + 1
            continue
        if i is None:
            rendu["non_trouves"].append({"cle": r.cle, "structure": r.structure, "verdict": sorte})
            continue
        lieu = x.at[i, "lieu"]
        lignes = x.index[(x["lieu"] == lieu) & x["type"].isin([PARENT] + enfants)]
        rendu["appliques"][sorte] = rendu["appliques"].get(sorte, 0) + 1
        if sorte in RETIRES:
            if sorte == "pas_un_cmp" and r.type_reel in labels:
                ajouter.append(_retype(x.loc[[i]], r, labels))
                rendu["retypees"] += 1
            retirer += list(lignes)
            rendu["retirees"].append({
                "ej": x.at[i, "ej"], "etablissement": r.etablissement, "type": PARENT,
                "nom": x.loc[i].get("nom_affiche") if isinstance(x.loc[i].get("nom_affiche"), str) else x.at[i, "nom"],
                "commune": x.at[i, "commune"], "nom_commune": nom_com.get(x.at[i, "commune"], ""),
                "finess": ",".join(sorted({n for c in ("finess", "finess_rapproche", "finess_absorbes")
                                           for n in _txt(x.loc[i].get(c)).split(",") if n})) or None,
                "provenance": x.at[i, "provenance"],
                "raison": f"vérification à la main, {RETIRES[sorte]}"
                          + (f", rangée parmi les {labels[r.type_reel][1].lower()}" if sorte == "pas_un_cmp" and r.type_reel in labels else "")})
            continue
        # existe
        x.loc[lignes, "verdict"] = "existe"
        x.loc[lignes, "examen"] = r.commentaire
        if "confirmation" in x:
            sans = lignes[x.loc[lignes, "confirmation"].isin(["bases"]) | x.loc[lignes, "confirmation"].isna()]
            x.loc[sans, "confirmation"] = "examinee"
        if r.adresse_reelle:
            voie, com = _adresse(r.adresse_reelle, x.at[i, "commune"], ref)
            x.loc[lignes, "adresse"] = voie
            if com != x.at[i, "commune"] and com in rattach.index:
                x.loc[lignes, "commune"] = com
                for c in ("epci", "dep", "reg"):
                    x.loc[lignes, c] = rattach.at[com, c]
            g = _geocoder(pd.DataFrame({"voie": [voie], "commune": [com]}), hors_ligne).dropna(subset=["lat"])
            g = g[(g["voie"] == voie) & (g["commune"] == com)]
            if len(g):
                x.loc[lignes, "lat"], x.loc[lignes, "lon"] = float(g["lat"].iloc[0]), float(g["lon"].iloc[0])
                x.loc[lignes, "precision"] = g["niveau"].iloc[0]
            elif centres and com in centres:
                x.loc[lignes, "lon"], x.loc[lignes, "lat"] = centres[com][0], centres[com][1]
                x.loc[lignes, "precision"] = "commune"
            rendu["adresses"] += 1
    x = x.drop(index=sorted(set(retirer)))
    if ajouter:
        n = pd.concat(ajouter, ignore_index=True)
        n = n[~n.set_index(["type", "lieu"]).index.isin(x.set_index(["type", "lieu"]).index)]
        # une structure rangée dans son type réel n'est pas ajoutée quand son gestionnaire en a déjà une de ce type dans
        # la même commune (elle y est déjà comptée, sous son propre numéro, constat du CSAPA de Brignoles)
        deja = set(zip(x["type"], x["ej"].fillna(""), x["commune"]))
        dbl = (n["verdict"] == "pas_un_cmp") & pd.Series([k in deja for k in zip(n["type"], n["ej"].fillna(""), n["commune"])],
                                                         index=n.index)
        rendu["retypees"] -= int(dbl.sum())
        rendu["deja_comptees"] = int(dbl.sum())
        n = n[~dbl]
        x = pd.concat([x, n], ignore_index=True)
    if "verifiee" in x:
        x["verifiee"] = x["verifiee"].fillna(False).astype(bool)
    dup = int(x.duplicated(["type", "lieu"]).sum())
    if dup:
        x = x.drop_duplicates(["type", "lieu"], keep="first")
        log.warning("verdicts, %d structures en double écartées", dup)
    a = rendu["appliques"]
    JOURNAL.controle("Vérification à la main des CMP, verdicts appliqués",
                     f"{sum(a.values())} sur {int((v['verdict'] != 'tranche').sum())} ("
                     + ", ".join(f"{k} {n}" for k, n in sorted(a.items())) + f"), {len(rendu['retirees'])} retirées, "
                     f"{rendu['retypees']} rangées dans leur type réel ({rendu.get('deja_comptees', 0)} y étaient déjà), "
                     f"{rendu['remises']} remises, "
                     f"{rendu['adresses']} adresses corrigées, {len(rendu['non_trouves'])} sans structure correspondante")
    return x, rendu


def _retype(ligne: pd.DataFrame, r, labels: dict) -> pd.DataFrame:
    """Copie d'une structure rangée dans son type réel (« pas un CMP »)."""
    n = ligne.copy()
    t = labels[r.type_reel]
    n["type"], n["libelle_type"], n["famille"], n["groupe"] = t[0], t[1], t[2], t[3]
    n["verdict"], n["examen"] = "pas_un_cmp", r.commentaire
    if "confirmation" in n:
        n["confirmation"] = np.nan
    return n
