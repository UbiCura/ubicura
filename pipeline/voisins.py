"""Indicateurs voisins d'une page d'indicateur (étape 3 des portes d'entrée, maquette P3 validée le 14 novembre 2026,
prototypes/entrees/p2_p3/). Six à huit liens tirés du catalogue unique, jamais d'une corrélation : la même profession ou
structure sous ses autres mesures, puis le même sous-thème, puis les indicateurs phares du thème. Un indicateur marqué
sensible au catalogue n'est jamais proposé à côté d'un indicateur de santé mentale (règles du projet, partie 6)."""
from __future__ import annotations

# famille de mesure lue au début de l'identifiant, et son rang : la densité avant l'âge, la patientèle, les dépassements
PREFIXES = ("prof:esm_", "prof:", "sae_etp_", "age60_", "file_active_", "patients_mt_", "depassements_",
            "taux_depassement_", "lieux_lieu_", "sae_", "dist_lieu_", "distp_lieu_")

# indicateurs phares d'un thème : ceux de la partie « Offre en santé mentale » du tableau de bord des fiches
PHARES = {"Santé mentale": ["prof:psychologue", "prof:psychiatre", "lieux_lieu_cmp_adultes", "prof:q_psychiatrie_enfant"]}


def objet(ident: str) -> tuple[str, int]:
    """Profession ou type de structure d'un indicateur, lu dans son identifiant, et le rang de sa mesure."""
    for k, p in enumerate(PREFIXES):
        if ident.startswith(p):
            o = ident[len(p):]
            return (o[:-1] if p == "sae_etp_" and o.endswith("s") else o), k
    return "", 99


def apparentes(a: str, b: str) -> bool:
    return bool(a and b) and (a == b or a.startswith(b + "_") or b.startswith(a + "_"))


def prefixe_commun(a: str, b: str) -> int:
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return n


def voisins(ident: str, cat: list[dict]) -> list[tuple[str, list[dict]]]:
    """Groupes (titre, entrées du catalogue) pour l'indicateur ident, chacun dans l'ordre où il se lit."""
    par_id = {x["id"]: x for x in cat}
    e = par_id.get(ident)
    if e is None:
        return []
    o, _ = objet(ident)
    sm = "Santé mentale" in e["themes"]
    # dans les deux sens : ni un indicateur sensible à côté de la santé mentale, ni la santé mentale à côté d'un
    # indicateur sensible (relecture indépendante de l'étape 3, 15 novembre 2026)
    ok = lambda x: x["id"] != ident and not (sm and x["sensible"]) and not (e["sensible"] and "Santé mentale" in x["themes"])  # noqa: E731
    A = sorted((x for x in cat if ok(x) and apparentes(objet(x["id"])[0], o)), key=lambda x: objet(x["id"])[1])[:4]
    pris = {x["id"] for x in A}
    fam = next((p for p in PREFIXES if ident.startswith(p)), "")
    B = [x for x in cat if ok(x) and x["id"] not in pris and x["sous"] == e["sous"]
         and (not fam.startswith("prof:") or x["id"].startswith(fam))]
    B = sorted(B, key=lambda x: -prefixe_commun(objet(x["id"])[0], o))
    # deux voisins au moins ; au-delà, seulement une profession ou une structure de nom proche (CMP, CMPP)
    B = [x for k, x in enumerate(B) if k < 2 or prefixe_commun(objet(x["id"])[0], o) >= 2][:max(2, 7 - len(A) - 2)]
    pris |= {x["id"] for x in B}
    th = e["themes"][0] if e["themes"] else None
    C = []
    for x in [par_id[k] for k in PHARES.get(th, []) if k in par_id]:
        if len(C) < 2 and ok(x) and x["id"] not in pris:
            C.append(x)
            pris.add(x["id"])
    mot = "profession" if ident.startswith("prof:") else "structure" if o else "mesure"
    groupes = [(f"La même {mot}, autres mesures", A), (f"Même sous-thème, {e['sous'].lower()}", B),
               (f"Même thème, {th.lower()}" if th else "Même domaine", C)]
    return [(t, L) for t, L in groupes if L]
