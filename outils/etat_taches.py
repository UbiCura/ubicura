"""Onglet « État » de la fenêtre du courrier : d'un coup d'œil, les tâches qui tournent seules vont-elles bien
(demande de Lucas du 1er novembre 2026) ? Relève du courrier, statistiques, veille des bases, relève hebdomadaire du
RPPS et archive mensuelle, place sur le disque. Lecture seule, rien n'est lancé d'ici.

Chaque ligne a un état : « bien » (dans les temps), « à regarder » (en retard), « en panne » (rien depuis longtemps
ou une erreur), avec la date du dernier passage et une phrase.
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DONNEES = RACINE / "donnees"

# délais au-delà desquels une tâche est en retard, puis en panne (en jours)
DELAIS = {"courrier": (1.5, 4), "statistiques": (1.5, 4), "veille": (8, 15), "rpps": (8, 15)}


def _etat(nom: str, age_jours: float | None) -> str:
    if age_jours is None:
        return "en panne"
    retard, panne = DELAIS[nom]
    return "bien" if age_jours <= retard else "à regarder" if age_jours <= panne else "en panne"


def _age(quand: dt.datetime | None, maintenant: dt.datetime) -> float | None:
    return None if quand is None else (maintenant - quand).total_seconds() / 86400


def _lire(f: Path, defaut):
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaut


def etats(maintenant: dt.datetime | None = None) -> list[dict]:
    """Une ligne par tâche : {tache, etat, quand, detail}."""
    m = maintenant or dt.datetime.now()
    sortie = []
    # relève du courrier, chaque matin
    e = _lire(DONNEES / "messagerie" / "etat.json", {})
    q = dt.datetime.fromisoformat(e["derniere_releve"][:19]) if e.get("derniere_releve") else None
    sortie.append({"tache": "Relève du courrier", "etat": _etat("courrier", _age(q, m)), "quand": q,
                   "detail": "chaque matin à 7 h 33"})
    # statistiques, une photographie par jour
    fs = sorted((DONNEES / "statistiques").glob("????-??-??.json"))
    q = dt.datetime.fromisoformat(fs[-1].stem) if fs else None
    sortie.append({"tache": "Statistiques", "etat": _etat("statistiques", _age(q, m) and max(0, _age(q, m) - 1)),
                   "quand": q, "detail": f"{len(fs)} jour(s) relevés"})
    # veille des bases, une fois par semaine
    p = _lire(DONNEES / "veille" / "passages.json", {}).get("passages") or []
    q = dt.datetime.fromisoformat(p[-1]["date"][:19]) if p else None
    ko = [k for k, v in (p[-1].get("catalogues") or {}).items() if not v.get("ok")] if p else []
    sortie.append({"tache": "Veille des bases", "etat": _etat("veille", _age(q, m)), "quand": q,
                   "detail": "une fois par semaine" + (f" ; catalogue illisible : {', '.join(ko)}" if ko else "")})
    if ko and sortie[-1]["etat"] == "bien":
        sortie[-1]["etat"] = "à regarder"
    # relève hebdomadaire du RPPS et semaines manquantes
    import sys
    sys.path.insert(0, str(RACINE))
    sys.path.insert(0, str(RACINE / "outils"))
    import releve_rpps as R
    idx = _lire(RACINE / "resultats" / "historique" / "photographies" / "index.json", [])
    dates = [dt.date.fromisoformat(i["date_rpps"]) for i in idx if i.get("date_rpps")]
    q = dt.datetime.combine(max(dates), dt.time()) if dates else None
    manque = R.semaines_manquantes(dates, m.date())
    journal = DONNEES / "releve_rpps.log"
    derniere_ligne = ""
    if journal.exists():
        lignes = [l.strip() for l in journal.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
        derniere_ligne = lignes[-1][:140] if lignes else ""
    sortie.append({"tache": "Mémoire du RPPS", "etat": _etat("rpps", _age(q, m)), "quand": q,
                   "detail": f"{len(dates)} photographie(s)"
                             + (f", {len(manque)} semaine(s) manquante(s)" if manque else ", aucune semaine manquante")
                             + (f" ; dernier passage : {derniere_ligne}" if derniere_ligne else "")})
    # archive mensuelle du RPPS, sans les noms
    arch = sorted((DONNEES / "archives" / "rpps").glob("rpps_*.zip"))
    q = dt.datetime.fromisoformat(arch[-1].stem.split("_")[1]) if arch else None
    mois_ok = q is not None and (q.year, q.month) == (m.year, m.month)
    sortie.append({"tache": "Archive mensuelle du RPPS", "etat": "bien" if mois_ok else "à regarder" if arch else "en panne",
                   "quand": q, "detail": f"{len(arch)} mois gardé(s), sans les noms"
                                         + ("" if mois_ok else " ; celle du mois en cours viendra à la prochaine relève")})
    # place sur le disque
    libre = shutil.disk_usage(RACINE).free / 1024 ** 3
    sortie.append({"tache": "Place sur le disque", "etat": "bien" if libre > 20 else "à regarder" if libre > 5 else "en panne",
                   "quand": m, "detail": f"{libre:.0f} Go libres"})
    return sortie


def onglet(onglets, racine, c: dict, police, petite) -> dict:
    """Onglet « État », une ligne par tâche avec une pastille (canard bien, ocre à regarder, cuivre en panne)."""
    import tkinter as tk
    from tkinter import ttk

    page = ttk.Frame(onglets, padding=0)
    onglets.add(page, text="État")
    corps = tk.Frame(page, bg=c["fond"], padx=16, pady=12)
    corps.pack(fill="both", expand=True)
    couleur = {"bien": "#0E5A5A", "à regarder": c["ocre"], "en panne": c["cuivre"]}

    def rafraichir():
        for w in corps.winfo_children():
            w.destroy()
        tk.Label(corps, text="Les tâches qui tournent seules", bg=c["fond"], fg=c["encre"], font=police,
                 anchor="w").pack(fill="x", pady=(0, 8))
        for l in etats():
            ligne = tk.Frame(corps, bg=c["panneau"], padx=10, pady=8)
            ligne.pack(fill="x", pady=3)
            pastille = tk.Canvas(ligne, width=14, height=14, bg=c["panneau"], highlightthickness=0)
            pastille.create_oval(2, 2, 12, 12, fill=couleur[l["etat"]], outline="")
            pastille.pack(side="left", padx=(0, 10))
            quand = l["quand"].strftime("%d/%m à %H h %M") if l["quand"] and l["quand"].time() != dt.time() else \
                (l["quand"].strftime("%d/%m") if l["quand"] else "jamais")
            tk.Label(ligne, text=f"{l['tache']} · {l['etat']} · {quand}", bg=c["panneau"], fg=c["encre"],
                     font=police, anchor="w").pack(side="top", fill="x")
            tk.Label(ligne, text=l["detail"], bg=c["panneau"], fg=c["discret"], font=petite, anchor="w",
                     justify="left", wraplength=900).pack(side="top", fill="x")
        ttk.Button(corps, text="Actualiser", command=rafraichir).pack(anchor="e", pady=(10, 0))

    rafraichir()
    return {"page": page, "rafraichir": rafraichir}


if __name__ == "__main__":
    for l in etats():
        print(f"{l['etat']:>11} | {l['tache']} | {l['quand']} | {l['detail']}")
