"""Page « Indicateurs » (navigation, étape 2, décision de Lucas du 8 novembre 2026) : tous les indicateurs du site,
cherchables sans accents ni pluriels et filtrables par domaine, thème et niveau, chacun vers sa page. Fabriquée depuis le
catalogue unique (affichage.catalogue), si bien qu'une base ajoutée y paraît d'elle-même avec ses étiquettes de thème
(pipeline/themes_indicateurs.csv). Les données (presentation/catalogue.json) servent aussi à la recherche de l'en-tête."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import affichage as AF
from . import domaines as D
from . import themes as TH

NOM_NIVEAU = {"fr": "France", "reg": "région", "dep": "département", "epci": "intercommunalité"}


def source_courte(src: str) -> str:
    """Le producteur en quelques mots, pour une liste : « RPPS », « FINESS et ROR », « INSEE », « Santé publique France »."""
    if "FINESS" in src and "ROR" in src:
        return "FINESS et ROR"
    return re.sub(r"\s*\([^)]*\)", "", src.split(",")[0]).strip()


def date_courte(an: str | None) -> str:
    """« 4 novembre 2026 » pour « répertoire RPPS du 4 novembre 2026 », l'année telle quelle sinon."""
    return re.sub(r"^(répertoire RPPS du|recensement|millésime)\s+", "", an or "").strip()


def donnees(sd: dict, dernier: Path, A: dict, fiches: dict) -> list[dict]:
    """Une entrée par indicateur qui a sa page, dans l'ordre des domaines et de leurs sous-groupes."""
    ind = {e["id"]: e for e in A.get("ind", [])}
    ordre_dom = {d["id"]: k for k, d in enumerate(D.DOMAINES)}
    ordre_sous = {(d["id"], s): k for d in D.DOMAINES for k, s in enumerate(d.get("sous", []))}
    out = []
    for e in AF.catalogue(sd, dernier):
        cle = TH.cle(e["id"])
        slug = fiches.get(cle)
        if not slug:
            continue
        a = ind.get(e["id"]) or {}
        prof = e["id"].startswith("prof:")
        niveaux = (["fr"] if prof else []) + [lv for lv in ("reg", "dep", "epci") if lv in (e.get("niveaux") or [])]
        date = (e.get("annees") or [None])[0]
        from .fiche_indicateur import titre_indicateur
        out.append({"id": cle, "nom": titre_indicateur(e.get("nom_court") or e["nom_long"], e.get("unite")),
                    "page": f"indicateur/{slug}.html",
                    "domaine": D.PAR_ID[e["domaine"]]["nom"], "domaine_id": e["domaine"], "sous": e.get("sous_theme") or "",
                    "definition": (a.get("exp") or "").strip(), "source": source_courte(e.get("source") or ""),
                    "source_longue": e.get("source") or "", "date": date_courte(date), "niveaux": [NOM_NIVEAU[x] for x in niveaux],
                    "themes": [TH.PAR_ID[t]["nom"] for t in e.get("themes", []) if t in TH.PAR_ID],
                    "sensible": bool(e.get("sensible")), "licence": e.get("licence") or "",
                    "_ordre": (ordre_dom.get(e["domaine"], 99), ordre_sous.get((e["domaine"], e.get("sous_theme")), 99))})
    out.sort(key=lambda x: (x["_ordre"], x["nom"]))
    for x in out:
        x.pop("_ordre")
    # une définition commune à toute une famille (les professions) passe en tête de son groupe, une seule fois
    compte: dict = {}
    for x in out:
        compte[x["definition"]] = compte.get(x["definition"], 0) + 1
    for x in out:
        x["commune"] = bool(x["definition"]) and compte[x["definition"]] > 5
    return out


def construire(env, commun: dict, sd: dict, dernier: Path, site: Path, A: dict, fiches: dict) -> list[Path]:
    C = donnees(sd, dernier, A, fiches)
    (site / "presentation" / "catalogue.json").write_text(json.dumps(C, ensure_ascii=False, separators=(",", ":")),
                                                          encoding="utf-8")
    domaines = list(dict.fromkeys(x["domaine"] for x in C))
    themes = [t for t in TH.THEMES]
    html = env.get_template("indicateurs.html").render(dict(
        commun, racine="", page="indicateurs", titre="Indicateurs", n=len(C), domaines=domaines, themes=themes,
        description=f"Les {len(C)} indicateurs du site, cherchables et filtrables par domaine, thème et niveau, chacun "
                    "avec sa page : définition, carte, source et limites."))
    (site / "indicateurs.html").write_text(html, encoding="utf-8")
    return [site / "indicateurs.html"]
