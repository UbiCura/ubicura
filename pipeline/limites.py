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
        "mayotte": "Mayotte"}


def tableau() -> list[dict]:
    """Une ligne par limite, pour la page méthode."""
    return [{"cle": NOMS.get(k, k), "risque": L["risque"], "texte": L["texte"],
             "sources": [{"titre": t, "url": u} for t, u in L["sources"]]} for k, L in config.LIMITES.items()]
