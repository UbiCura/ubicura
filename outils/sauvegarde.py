"""Sauvegarde hors du PC de ce qui ne se retélécharge pas (fiche docs/revue_plan_2026-11-16/chantier_sauvegarde_hors_pc.md).

Le disque de sauvegarde est reconnu par un fichier témoin à sa racine (TEMOIN), posé une fois par la commande
`preparer` (tutoriel 16). Sans chiffrement (décision du 23 novembre 2026) : l'archive du RPPS ne garde que
l'identifiant, tiré d'une extraction publique sous Licence Ouverte, et rien d'autre de personnel n'est copié. La copie n'efface jamais rien sur le
disque : un fichier supprimé ou abîmé par erreur sur le PC reste sauvegardé. L'historique du dépôt est copié en un
paquet Git (git bundle, toutes les branches), les quatre derniers gardés. Après la copie, l'empreinte de chaque
archive du RPPS et de chaque photographie est comparée à l'original.

    python outils\\sauvegarde.py sauvegarder [--si-branche]   copie vers le disque témoin (code 0 faite, 10 aucun
                                                             disque branché, 20 erreur)
    python outils\\sauvegarde.py etat                         date de la dernière sauvegarde, en mots
    python outils\\sauvegarde.py preparer E:                  pose le fichier témoin sur le disque E: (une fois)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import string
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

TEMOIN = "UbiCura_sauvegarde.txt"
DOSSIER = "UbiCura_sauvegarde"
ETAT = RACINE / "donnees" / "sauvegarde.json"
ALERTE_JOURS = 10
PAQUETS_GARDES = 4

# ce qui ne se retélécharge pas, relatif à la racine du projet (fiche, partie 2) ; l'historique du dépôt part à part
COPIES = ["resultats/historique", "donnees/archives", "contenus", "docs", "donnees/brut"]
# et les fichiers Markdown de la racine (règles du projet, présentation du dépôt)
RACINE_MD = "*.md"
# copies dont chaque fichier est vérifié par son empreinte après la copie : elles ne se refont jamais
VERIFIEES = ["resultats/historique", "donnees/archives"]


def disque_temoin() -> Path | None:
    """Le premier lecteur, autre que celui du projet, qui porte le fichier témoin à sa racine."""
    projet = RACINE.drive.upper()
    for lettre in string.ascii_uppercase:
        racine = Path(f"{lettre}:\\")
        if f"{lettre}:" == projet:
            continue
        try:
            if (racine / TEMOIN).is_file():
                return racine
        except OSError:
            continue
    return None


def empreinte(f: Path) -> str:
    h = hashlib.sha256()
    with f.open("rb") as fh:
        for bloc in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def copier(source: Path, cible: Path) -> int:
    """Copie sans suppression (robocopy sans /MIR ni /PURGE) ; codes de robocopy sous 8 = réussite."""
    if source.is_file():
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, cible)
        return 0
    r = subprocess.run(["robocopy", str(source), str(cible), "/E", "/R:2", "/W:5", "/NP", "/NFL", "/NDL", "/NJH", "/NJS"],
                       capture_output=True, text=True)
    return 0 if r.returncode < 8 else r.returncode


def verifier(source: Path, cible: Path) -> list[str]:
    erreurs = []
    for f in source.rglob("*"):
        if f.is_file():
            c = cible / f.relative_to(source)
            if not c.is_file():
                erreurs.append(f"absent : {source.name}/{f.relative_to(source).as_posix()}")
            elif f.stat().st_size != c.stat().st_size or empreinte(f) != empreinte(c):
                erreurs.append(f"différent : {source.name}/{f.relative_to(source).as_posix()}")
    return erreurs


def paquet_git(dest: Path) -> list[str]:
    d = dest / "depot"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"depot_{dt.date.today():%Y-%m-%d}.bundle"
    r = subprocess.run(["git", "-C", str(RACINE), "bundle", "create", str(f), "--all"], capture_output=True, text=True)
    if r.returncode != 0:
        return [f"paquet Git : {r.stderr.strip()[:200]}"]
    v = subprocess.run(["git", "-C", str(RACINE), "bundle", "verify", str(f)], capture_output=True, text=True)
    if v.returncode != 0:
        return [f"paquet Git illisible : {v.stderr.strip()[:200]}"]
    for vieux in sorted(d.glob("depot_*.bundle"))[:-PAQUETS_GARDES]:
        vieux.unlink()
    return []


def fichiers_racine() -> list[Path]:
    return sorted(RACINE.glob(RACINE_MD))


def sauvegarder(disque: Path) -> dict:
    dest = disque / DOSSIER
    debut = dt.datetime.now()
    erreurs = []
    for rel in COPIES:
        src = RACINE / rel
        if not src.exists():
            erreurs.append(f"introuvable sur le PC : {rel}")
            continue
        code = copier(src, dest / rel)
        if code:
            erreurs.append(f"copie de {rel} en erreur (robocopy {code})")
    for f in fichiers_racine():
        if copier(f, dest / f.name):
            erreurs.append(f"copie de {f.name} en erreur")
    for rel in VERIFIEES:
        if (RACINE / rel).exists():
            erreurs += verifier(RACINE / rel, dest / rel)
    erreurs += paquet_git(dest)
    etat = {"date": debut.isoformat(timespec="seconds"), "disque": str(disque), "reussie": not erreurs,
            "erreurs": erreurs[:20], "duree_min": round((dt.datetime.now() - debut).total_seconds() / 60, 1)}
    ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
    return etat


def etat_en_mots(aujourd: dt.date | None = None) -> tuple[str, str]:
    """Ligne de la fenêtre « Ubi Cura » et son ton (discret, alerte)."""
    aujourd = aujourd or dt.date.today()
    try:
        e = json.loads(ETAT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ("Aucune sauvegarde hors du PC encore. Branche le disque Samsung T5 (tutoriel 16).", "alerte")
    jour = dt.date.fromisoformat(e["date"][:10])
    if not e.get("reussie"):
        return (f"La sauvegarde hors du PC du {jour:%d/%m} a échoué ({(e.get('erreurs') or ['?'])[0]}).", "alerte")
    n = (aujourd - jour).days
    if n > ALERTE_JOURS:
        return (f"Dernière sauvegarde hors du PC le {jour:%d/%m}, il y a {n} jours. Branche le disque Samsung T5.",
                "alerte")
    return (f"Dernière sauvegarde hors du PC le {jour:%d/%m}.", "discret")


def main() -> int:
    p = argparse.ArgumentParser()
    sous = p.add_subparsers(dest="cmd", required=True)
    s = sous.add_parser("sauvegarder")
    s.add_argument("--si-branche", action="store_true", help="sans disque branché, ne rien dire (tâche planifiée)")
    sous.add_parser("etat")
    pr = sous.add_parser("preparer")
    pr.add_argument("lecteur")
    a = p.parse_args()
    if a.cmd == "etat":
        print(etat_en_mots()[0])
        return 0
    if a.cmd == "preparer":
        racine = Path(a.lecteur.rstrip("\\/") + "\\")
        if racine.drive.upper() == RACINE.drive.upper():
            print("Ce lecteur est celui du projet, pas un disque de sauvegarde.")
            return 20
        if not racine.exists():
            print(f"Lecteur {racine} introuvable.")
            return 20
        (racine / TEMOIN).write_text("Disque de sauvegarde d'Ubi Cura (dossier UbiCura_sauvegarde). Ne pas effacer.\n",
                                     encoding="utf-8")
        print(f"Témoin posé sur {racine}. Lancer ensuite : python outils\\sauvegarde.py sauvegarder")
        return 0
    disque = disque_temoin()
    if disque is None:
        if not a.si_branche:
            print(f"Aucun disque de sauvegarde branché (fichier {TEMOIN} à la racine, tutoriel 16).")
        return 10
    print(f"Sauvegarde vers {disque}{DOSSIER} (quelques minutes, plus la première fois).")
    e = sauvegarder(disque)
    print("Sauvegarde faite." if e["reussie"] else "Sauvegarde en erreur : " + "; ".join(e["erreurs"][:5]))
    return 0 if e["reussie"] else 20


if __name__ == "__main__":
    sys.exit(main())
