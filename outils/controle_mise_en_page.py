"""Contrôle de mise en page du site construit, page type par page type (méthode de travail, Lucas, 6 novembre 2026).

Chaque type de page est ouvert dans Edge sans fenêtre, à 1 280 px et à 375 px, puis tel qu'il s'imprime pour les pages
qui ont un PDF (rapports nationaux, rapports par territoire, fiches). Le contrôle de finition (outils/controle_finition.js)
y relève les chevauchements, y compris dans les figures, les textes coupés, les pages qui défilent en largeur, le texte
qui ne va pas jusqu'au bord droit de la figure de sa colonne, les couleurs trop proches du fond, les réglettes illisibles.
En papier, les rapports n'ont que deux tailles de texte courant (10,5 et 9 points, Lucas, 6 novembre 2026).

    .\\.venv\\Scripts\\python.exe outils\\controle_mise_en_page.py          # code de sortie 1 s'il reste un défaut

Le contrôle des chiffres et des textes est outils/controle_decisions.py ; les deux passent avant toute mise en ligne."""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils"))
import controle_finition as CF  # noqa: E402
from pipeline import config  # noqa: E402

SITE = RACINE / "site"
LARGEURS = {"ordinateur": (1280, 900), "telephone": (375, 812)}
TAILLES_PAPIER_MAX = 2      # texte courant et tableaux, dans les rapports imprimés
FILS = 3                    # navigateurs ouverts à la fois


def pages_types(date: str) -> list[tuple[str, bool]]:
    """Un exemplaire de chaque type de page, et s'il s'imprime en PDF. Les exemples sont choisis pour couvrir les cas
    difficiles : département d'outre-mer, région, intercommunalité de deux départements."""
    def premier(motif: str) -> str | None:
        f = sorted(SITE.glob(motif))
        return f[0].relative_to(SITE).as_posix() if f else None
    pages = [("index.html", False), ("atlas.html", False), ("atlas.html#?fam=tout&prof=ens_medecin_specialiste&niv=epci", False), ("explorer.html", False), ("croiser.html", False),
             ("comparer.html", False), ("domaines.html", False), ("liens.html", False), ("methode.html", False),
             ("zone.html", False), ("zone.html#lieu=12202&rayon=20", False), ("rapports.html", False), ("journal.html", False), ("donnees-sources.html", False),
             ("territoires/index.html", False), ("domaine/offre-de-soins.html", False),
             ("domaine/sante-mentale.html", False), ("domaine/sante.html", False),
             (premier("domaine/[a-r]*.html") or "", False), (premier("indicateur/prof-psychiatre*.html") or "", False),
             (premier("indicateur/lieux-*.html") or "", False),
             ("territoire/dep/12.html", True), ("territoire/dep/971.html", True), ("territoire/reg/76.html", True),
             ("territoire/epci/200018653.html", True),
             (f"rapports/{date}/sante-mentale.html", True), (f"rapports/{date}/sante.html", True),
             (f"territoires/{date}/dep-12-sante-mentale.html", True), (f"territoires/{date}/reg-76-sante.html", True)]
    vus, out = set(), []
    for p, papier in pages:
        if p and p not in vus and (SITE / p.partition("#")[0]).exists():
            vus.add(p)
            out.append((p, papier))
    return out


def controler() -> int:
    from pipeline.util import marquer_seance
    marquer_seance()
    date = sorted(p.name for p in config.RESULTATS.glob("20*") if (p / "site_data.json").exists())[-1]
    pages = pages_types(date)
    exe = CF._navigateur()
    serveur = CF._serveur(SITE)
    taches = [(p, nom, l, h, None) for p, _ in pages for nom, (l, h) in LARGEURS.items()]
    taches += [(p, "papier", *CF.PAPIER, "papier") for p, papier in pages if papier]
    defauts: list[str] = [f"style.css : {d}" for d in CF.palettes()]

    def une(t):
        page, nom, l, h, theme = t
        return t, CF.controler(SITE, page, exe, serveur, l, h, theme, suffixe=f"_{nom}")
    try:
        with ThreadPoolExecutor(FILS) as ex:
            resultats = list(ex.map(une, taches))
        # une vue en défaut est refaite seule : sous la charge de trois navigateurs, la page la plus lourde (Explorer) ne
        # finissait pas toujours sa composition à temps, et ses paragraphes paraissaient justifiés sur téléphone
        # (7 novembre 2026). Un défaut de mise en page vrai se retrouve à la seconde mesure, faite sans charge.
        resultats = [(t, une(t)[1]) if (r.get("defauts") or "erreur" in r) else (t, r) for t, r in resultats]
    finally:
        serveur.shutdown()
    for (page, nom, l, h, theme), r in resultats:
        if "erreur" in r:
            defauts.append(f"{page}, {nom} : {r['erreur']}")
            continue
        d = r["defauts"] + (r["couleurs"] + CF.defilements_ordinateur(r, nom) + r.get("reglettes", []) if theme is None else [])
        if theme is None and len(r["tailles"]) > CF.TAILLES_MAX:
            d.append(f"{len(r['tailles'])} tailles de texte : " + ", ".join(f"{t['px']} px" for t in r["tailles"]))
        if theme == "papier" and page.startswith(("rapports/", "territoires/")):
            tt = r.get("tailles_texte", [])
            if len(tt) > TAILLES_PAPIER_MAX:
                d.append(f"{len(tt)} tailles de texte courant à l'impression (deux au plus) : "
                         + ", ".join(f"{t['px']} px ({t['exemple'][:50]})" for t in tt))
        defauts += [f"{page}, {nom} : {x}" for x in d]
    for page, _ in pages:
        defauts += [f"{page} : {x}" for x in CF.liseres((SITE / page.partition("#")[0]).read_text(encoding="utf-8"))]
    defauts = list(dict.fromkeys(defauts))
    print(f"Contrôle de mise en page ({date}), {len(pages)} types de page, {len(taches)} vues")
    for x in defauts:
        print("  DÉFAUT", x)
    print("Aucun défaut." if not defauts else f"{len(defauts)} défaut(s).")
    return 1 if defauts else 0


if __name__ == "__main__":
    sys.exit(controler())
