"""Relève hebdomadaire du RPPS : une photographie des comptes chaque semaine, sans exécution complète (constat du
1er novembre 2026 : trois photographies seulement en octobre, une par exécution complète, alors que la mémoire du
répertoire est promise chaque semaine). Lancée par la relève du courrier du matin (messagerie.py relever), dans un
processus à part pour ne pas la retarder.

Elle ne fait rien si une photographie a moins de six jours, si moins de 6 Go de mémoire sont libres (règle des
exécutions lourdes), ou si une autre exécution tient le verrou. Sinon elle télécharge l'extraction du RPPS (archive
mensuelle sans les noms comprise), compte les professionnels comme l'exécution complète (mêmes fonctions : lecture des
activités, périmètre élargi, agrégats) et écrit la photographie. Rien n'est publié. Une semaine manquante est signalée
par `controle`.

    python outils\\releve_rpps.py photographier [--forcer]   photographie si elle est due
    python outils\\releve_rpps.py controle                    semaines sans photographie depuis la première
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

INTERVALLE_JOURS = 6        # une photographie par semaine, avec un jour de marge
MEMOIRE_MIN_GO = 6.0        # règles du projet, partie 2 : 6 Go libres avant une exécution lourde


def memoire_libre_go() -> float:
    import psutil
    return psutil.virtual_memory().available / 1024 ** 3


def derniere_photographie() -> dt.date | None:
    from pipeline import config
    f = config.RESULTATS / "historique" / "photographies" / "index.json"
    if not f.exists():
        return None
    dates = [i.get("date_rpps") for i in json.loads(f.read_text(encoding="utf-8"))]
    return max((dt.date.fromisoformat(d) for d in dates if d), default=None)


def due(derniere: dt.date | None, aujourd_hui: dt.date, memoire_go: float, forcer: bool = False) -> tuple[bool, str]:
    """Faut-il photographier aujourd'hui ? Renvoie la décision et sa raison, écrite telle quelle dans la relève."""
    if memoire_go < MEMOIRE_MIN_GO:
        return False, f"mémoire libre {memoire_go:.1f} Go, il en faut {MEMOIRE_MIN_GO:.0f} ; reportée à demain"
    if forcer or derniere is None:
        return True, "première photographie" if derniere is None else "forcée"
    ecart = (aujourd_hui - derniere).days
    if ecart < INTERVALLE_JOURS:
        return False, f"dernière photographie il y a {ecart} jour{'s' if ecart > 1 else ''}"
    return True, f"dernière photographie il y a {ecart} jours"


def semaines_manquantes(dates: list[dt.date], aujourd_hui: dt.date) -> list[dt.date]:
    """Lundis des semaines, depuis la première photographie, qui n'en ont aucune (la semaine en cours exceptée)."""
    if not dates:
        return []
    lundis = {d - dt.timedelta(days=d.weekday()) for d in dates}
    l, fin, manque = min(lundis), aujourd_hui - dt.timedelta(days=aujourd_hui.weekday()), []
    while l < fin:
        if l not in lundis:
            manque.append(l)
        l += dt.timedelta(days=7)
    return manque


def photographier(forcer: bool = False) -> str:
    """Photographie due ou raison de ne pas la prendre, en une ligne."""
    ok, raison = due(derniere_photographie(), dt.date.today(), memoire_libre_go(), forcer)
    if not ok:
        return f"Relève du RPPS : rien à faire ({raison})."
    import run
    # finess et referentiel sont dans pipeline.sources : l'import d'origine (1er novembre 2026) échouait à chaque relève,
    # et aucune photographie hebdomadaire n'a été prise par cette voie (constat du 12 novembre 2026)
    from pipeline import build, photographies
    from pipeline.sources import finess, referentiel, rpps
    with run.verrou_execution():
        ref = referentiel.charger(True, False)
        fichiers = rpps.telecharger_tout(False, False)
        act, professions = rpps.lire_activites(fichiers, ref)
        fin = finess.charger(True, False)
        act, professions = build.perimetre_elargi(act, fin, professions)
        agg = build.agreger(act, ref, fin, None)
        entree = photographies.ecrire(agg, dt.date.today().isoformat())
    if not entree:
        return "Relève du RPPS : photographie non écrite (date de l'extraction inconnue)."
    return f"Relève du RPPS : photographie de l'extraction du {entree['date_rpps']} ({entree['lignes']} lignes, {raison})."


def lancer_en_fond() -> None:
    """Pour la relève du courrier : vérifie seulement si la photographie est due, puis la confie à un processus à part
    (le téléchargement et le comptage prennent de longues minutes). N'échoue jamais."""
    try:
        ok, raison = due(derniere_photographie(), dt.date.today(), memoire_libre_go())
    except Exception as e:  # noqa: BLE001
        print(f"Relève du RPPS impossible ({e.__class__.__name__}).")
        return
    if not ok:
        return
    journal = RACINE / "donnees" / "releve_rpps.log"
    try:
        with open(journal, "a", encoding="utf-8") as sortie:
            subprocess.Popen([sys.executable, str(Path(__file__)), "photographier"], cwd=RACINE, stdout=sortie,
                             stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        print(f"Relève du RPPS lancée en fond ({raison}), suivi dans {journal.name}.")
    except OSError as e:
        print(f"Relève du RPPS non lancée ({e}).")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    s = p.add_subparsers(dest="cmd", required=True)
    ph = s.add_parser("photographier")
    ph.add_argument("--forcer", action="store_true")
    s.add_parser("controle")
    a = p.parse_args(argv)
    if a.cmd == "photographier":
        print(photographier(a.forcer))
        return 0
    from pipeline import config
    f = config.RESULTATS / "historique" / "photographies" / "index.json"
    dates = [dt.date.fromisoformat(i["date_rpps"]) for i in json.loads(f.read_text(encoding="utf-8"))] if f.exists() else []
    manque = semaines_manquantes(dates, dt.date.today())
    print("Aucune semaine manquante." if not manque else
          f"{len(manque)} semaine(s) sans photographie du RPPS : " + ", ".join(l.strftime("%d/%m/%Y") for l in manque))
    return 1 if manque else 0


if __name__ == "__main__":
    sys.exit(main())
