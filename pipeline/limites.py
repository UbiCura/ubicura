"""Limites connues des données (config.LIMITES), mises en forme pour les rapports, la page méthode et le site.
Chaque limite est dite là où la donnée est montrée, avec un lien vers la source qui l'établit."""
from __future__ import annotations

from . import config


def cle(identifiant: str) -> str | None:
    """Clé de config.LIMITES pour un indicateur, une profession (« prof:psychologue ») ou « route »."""
    if identifiant in config.LIMITES:
        return identifiant
    for debut, k in config.LIMITES_ALIAS.items():
        if identifiant.startswith(debut):
            return k
    return None


def sources_md(L: dict) -> str:
    return ", ".join(f"[{t}]({u})" for t, u in L["sources"])


A_SAVOIR = "**À savoir.** "


def phrase_md(identifiants, code: str | None = None) -> str:
    """Texte Markdown des limites des indicateurs donnés, chacune suivie de ses sources, sans doublon."""
    vues, textes, sources = set(), [], {}
    for i in identifiants:
        k = cle(i)
        if not k or k in vues:
            continue
        vues.add(k)
        L = config.LIMITES[k]
        t = L["texte"]
        if code and code in L.get("territoires", {}):
            t += " " + L["territoires"][code]
        textes.append(t)
        for titre, url in L["sources"]:
            sources.setdefault(url, titre)
    if not textes:
        return ""
    return A_SAVOIR + " ".join(textes) + (" Sources, " if len(sources) > 1 else " Source, ") + \
        ", ".join(f"[{t}]({u})" for u, t in sources.items()) + "."


# nom lisible de chaque limite, pour la page méthode
NOMS = {"suicides": "Décès par suicide", "hospit_gestes_auto_infliges": "Hospitalisations pour geste auto-infligé",
        "urgences_gestes_auto_infliges": "Passages aux urgences pour geste auto-infligé",
        "prof:infirmier": "Infirmiers", "prof:psychiatre": "Psychiatres, lieu d'exercice", "prof:pedopsychiatre": "Pédopsychiatres, définition",
        "prof:psychologue": "Psychologues", "route": "Temps de trajet par la route",
        "sae": "Psychiatrie à l'hôpital (SAE)", "ald": "Affections de longue durée",
        "caf": "Allocations de la CAF", "evolution": "Évolution depuis 2016 (séries de la DREES)",
        "mayotte": "Mayotte", "prof:medecin_travail": "Médecins du travail",
        "prof:medecin_sante_publique": "Médecins de santé publique", "prof:orthophoniste": "Orthophonistes, tous les âges",
        "prof:psychomotricien": "Psychomotriciens, tous les âges",
        "lieux": "Structures de soins, FINESS et ROR réunis"}


def specialites_salariees(national, professions) -> dict:
    """Précision « exercice surtout salarié » pour chaque spécialité médicale dont moins d'un tiers des médecins exercent
    en libéral (config.SEUIL_LIBERAL_SPECIALITE, validé par Lucas le 11 octobre 2026), calculée sur l'effectif
    national de l'exécution. Ajoutée à config.LIMITES, elle suit le chiffre partout où il est montré."""
    if national is None or professions is None or not len(national):
        return {}
    t = national.pivot_table(index="prof", columns="mode", values="n", aggfunc="sum")
    groupes = set(config.GROUPES_SPECIALITES) - {config.G_PREV}
    sortie = {}
    for _, r in professions[professions["groupe"].isin(groupes)].iterrows():
        p = r["id"]
        if p not in t.index or not t.at[p, "all"]:
            continue
        part = (t.at[p, "lib"] if "lib" in t.columns and t.at[p, "lib"] == t.at[p, "lib"] else 0) / t.at[p, "all"]
        if part < config.SEUIL_LIBERAL_SPECIALITE:
            sortie[f"prof:{p}"] = {
                "risque": "exercice surtout salarié",
                "texte": (f"Pour cette spécialité ({r['libelle'].lower()}), {round(part * 100)} % seulement des médecins "
                          "exercent en libéral. La plupart sont salariés, le plus souvent à l'hôpital, si bien que leur "
                          "densité par territoire montre surtout où se trouvent les établissements, pas l'accès des "
                          "habitants, qui consultent souvent dans un territoire voisin."),
                "sources": [config.SRC_RPPS], "nom": f"{r['libelle']}, exercice surtout salarié"}
    return sortie


def phrase_specialites_md(cles) -> str:
    """Les limites des spécialités, réunies en un seul paragraphe « À savoir », une phrase pour toutes les spécialités
    surtout salariées (avec leur part en libéral) plutôt qu'une phrase répétée par spécialité, puis les autres."""
    import re
    sal, autres = [], []
    for k in cles:
        L = config.LIMITES.get(k)
        if not L:
            continue
        m = re.search(r"\(([^)]+)\), (\d+) %", L["texte"]) if L["risque"] == "exercice surtout salarié" else None
        (sal if m else autres).append((k, m))
    texte = ""
    if sal:
        liste = ", ".join(f"{m.group(1)} {m.group(2)} %" for _k, m in sal)
        texte = (f"Pour certaines spécialités, moins d'un tiers des médecins exercent en libéral ({liste}). La plupart "
                 "sont salariés, le plus souvent à l'hôpital, si bien que leur densité par territoire montre surtout où "
                 "se trouvent les établissements, pas l'accès des habitants, qui consultent souvent dans un territoire "
                 f"voisin. Source, [{config.SRC_RPPS[0]}]({config.SRC_RPPS[1]}).")
    reste = phrase_md([k for k, _m in autres])
    if reste:
        texte = (texte + " " + reste[len(A_SAVOIR):]) if texte else reste[len(A_SAVOIR):]
    return A_SAVOIR + texte if texte else ""


def completer(extra: dict | None) -> None:
    """Ajoute à config.LIMITES les limites calculées à l'exécution (spécialités surtout salariées), relues depuis
    site_data.json quand le site est reconstruit seul."""
    for k, L in (extra or {}).items():
        if k not in config.LIMITES:
            config.LIMITES[k] = {c: L[c] for c in ("risque", "texte", "sources") if c in L} | (
                {"territoires": L["territoires"]} if L.get("territoires") else {})
            NOMS.setdefault(k, L.get("nom") or k)


def tableau() -> list[dict]:
    """Une ligne par limite, pour la page méthode."""
    return [{"cle": NOMS.get(k, k), "risque": L["risque"], "texte": L["texte"],
             "sources": [{"titre": t, "url": u} for t, u in L["sources"]]} for k, L in config.LIMITES.items()]
