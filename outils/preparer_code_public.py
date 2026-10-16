"""Prépare le code public dans un dépôt Git séparé et le vérifie. N'envoie rien.

Le dépôt de travail garde son historique et ses notes internes. Le dépôt public n'en reçoit qu'une copie filtrée, en
commits signés de la seule adresse anonyme GitHub de Lucas (git config offresoins.adresseautorisee).

Deux modes.
- Par défaut, un dépôt neuf d'un seul commit, refait à chaque fois (pour vérifier).
- Avec --suivi, un dépôt public permanent (donnees/code_public, hors de Git), mis à jour à chaque publication. Un commit
  n'est ajouté que si le code a changé, l'historique public reste ainsi lisible d'une version à l'autre.

Exclus : notes de travail, tutoriels personnels, prototypes, fichiers de données et résultats (déjà hors de Git).
Contrôles bloquants : aucune mention d'un assistant, aucune adresse personnelle, aucun identifiant RPPS, aucun
fichier de données, identité unique dans tout le dépôt public, puis contrôle avant envoi (.githooks/pre-push).

    python outils/preparer_code_public.py [dossier]          (par défaut %TEMP%/ubicura_code_public)
    python outils/preparer_code_public.py --suivi [dossier]  (par défaut donnees/code_public)
Codes de sortie, 0 prêt, 20 problème bloquant. En cas de problème, le dépôt suivi revient à son dernier commit.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from pipeline import config  # noqa: E402

# notes de méthode utiles aux lecteurs, publiées avec le code (les autres notes de docs/ restent internes)
DOCS_PUBLICS = {"docs/verification_2026-10-05.md", "docs/verification_2026-10-08.md",
                "docs/note_secteurs_hors_soins.md", "docs/note_suicide_ile_de_france_2026-10-05.md"}
# le nom de l'assistant est assemblé ici, pour que ce fichier ne contienne pas lui-même ce qu'il recherche
ASSISTANT = "cla" + "ude"
EXCLUS = re.compile(rf"^({ASSISTANT.upper()}\.md|\.{ASSISTANT}/|prototypes/|docs/)")
INTERDITS_CHEMIN = re.compile(r"^(donnees|resultats|site)/|\.(parquet|log)$|(^|/)rpps[^/]*\.(txt|csv)$", re.I)
INTERDITS_TEXTE = [
    # noms propres écartés (Camille-Claudel, rue Claude-Monet, Jean-Claude), toute autre forme reste bloquante
    (re.compile(r"(?i:(?<![\w-])" + ASSISTANT + r"(?!l))(?!-[A-ZÀ-Ý][a-zà-ÿ])|(?i:anthr" + "opic)"),
     "mention d'un assistant"),
    (re.compile(r"@gmail\.|a-remplacer\.invalid|univ-[a-z]+\.fr", re.I), "adresse personnelle"),
    (re.compile(r"(?<![\d.,])(10\d{9}|810\d{8})(?![\d.,])"), "identifiant RPPS possible"),
]


def motifs_prives() -> list:
    """Motifs privés en plus (adresse personnelle, nom d'utilisateur Windows...), gardés dans la configuration locale
    du dépôt et jamais publiés, git config --add offresoins.motifprive <texte>."""
    r = subprocess.run(["git", "config", "--get-all", "offresoins.motifprive"], cwd=RACINE, capture_output=True, text=True)
    return [(re.compile(re.escape(m), re.I), "donnée personnelle") for m in r.stdout.split("\n") if m.strip()]


def fichiers_publics() -> list[str]:
    """Fichiers du dernier commit seulement, jamais des modifications non enregistrées."""
    suivis = subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD"], cwd=RACINE, capture_output=True, text=True,
                            check=True).stdout.split("\n")
    return sorted(f for f in suivis if f and (f in DOCS_PUBLICS or not EXCLUS.match(f)))


def citation_cff(version: str) -> str:
    prenom, nom = config.AUTEUR.split(" ", 1)
    lignes = ["cff-version: 1.2.0",
              "message: \"Pour citer ce travail, merci d'utiliser les références ci-dessous.\"",
              f"title: \"{config.NOM_PROJET}, {config.SOUS_TITRE[0].lower() + config.SOUS_TITRE[1:]}\"",
              "type: software",
              "authors:",
              f"  - family-names: \"{nom}\"",
              f"    given-names: \"{prenom}\"",
              f"    orcid: \"https://orcid.org/{config.ORCID}\"",
              "license: EUPL-1.2",
              f"date-released: \"{version}\""]
    if config.ADRESSE_SITE:
        lignes.append(f"url: \"{config.ADRESSE_SITE}\"")
    if config.DOI_DONNEES:
        lignes += ["references:", "  - type: dataset", f"    title: \"{config.TITRES_DEPOTS['donnees']}\"",
                   "    authors:", f"      - family-names: \"{nom}\"", f"        given-names: \"{prenom}\"",
                   f"    doi: \"{config.DOI_DONNEES}\""]
    return "\n".join(lignes) + "\n"


def _supprimer(chemin: Path) -> None:
    if chemin.is_dir():
        shutil.rmtree(chemin, onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))
    else:
        os.chmod(chemin, 0o700)
        chemin.unlink()


def main() -> int:
    ap = argparse.ArgumentParser(description="Prépare et vérifie le code public, sans rien envoyer.")
    ap.add_argument("dossier", nargs="?")
    ap.add_argument("--suivi", action="store_true", help="dépôt public permanent, un commit par version qui change")
    a = ap.parse_args()
    if a.dossier:
        dest = Path(a.dossier)
    else:
        dest = RACINE / "donnees" / "code_public" if a.suivi else Path(tempfile.gettempdir()) / "ubicura_code_public"
    adresse = subprocess.run(["git", "config", "--get", "offresoins.adresseautorisee"], cwd=RACINE,
                             capture_output=True, text=True).stdout.strip()
    nom = subprocess.run(["git", "config", "--get", "offresoins.nomautorise"], cwd=RACINE,
                         capture_output=True, text=True).stdout.strip()
    if not re.fullmatch(r"\d+\+[A-Za-z0-9-]+@users\.noreply\.github\.com", adresse) or not nom:
        print("Adresse anonyme GitHub ou nom autorisé absents de la configuration du dépôt, rien n'est préparé.")
        return 20
    versions = sorted(p.name for p in (RACINE / "resultats").glob("20*") if p.is_dir())
    version = versions[-1] if versions else "inconnue"

    def git(*args):
        return subprocess.run(["git", *args], cwd=dest, capture_output=True, text=True)

    # dossier de travail, neuf, ou dépôt suivi vidé de tout sauf son historique
    suivi_existant = a.suivi and (dest / ".git").exists()
    if suivi_existant:
        for p in dest.iterdir():
            if p.name != ".git":
                _supprimer(p)
    else:
        if dest.exists():
            _supprimer(dest)
        dest.mkdir(parents=True)

    fichiers = fichiers_publics()
    prives = motifs_prives()
    if subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=RACINE, capture_output=True,
                      text=True).stdout.strip():
        print("À savoir, des modifications ne sont pas encore enregistrées dans le dépôt de travail. Seul le dernier "
              "commit est publié.")
    problemes = []
    for f in fichiers:
        if INTERDITS_CHEMIN.search(f):
            problemes.append(f"{f}, fichier de données")
            continue
        cible = dest / f
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(subprocess.run(["git", "show", f"HEAD:{f}"], cwd=RACINE, capture_output=True,
                                         check=True).stdout)
        if f.startswith("atlas/vendor/"):
            continue   # bibliothèques tierces minifiées, publiées telles quelles
        try:
            texte = cible.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        for motif, raison in INTERDITS_TEXTE + prives:
            for m in motif.finditer(texte):
                ligne = texte.count("\n", 0, m.start()) + 1
                problemes.append(f"{f}, ligne {ligne}, {raison} ({m.group(0)})")
    (dest / "CITATION.cff").write_text(citation_cff(version), encoding="utf-8")
    fichiers.append("CITATION.cff")

    # renvois vers des fichiers qui ne sont pas publiés (simple avertissement)
    absents = set()
    for f in fichiers:
        p = dest / f
        if p.suffix in {".md", ".py", ".ps1", ".html"} and p.exists():
            for m in re.finditer(r"(docs[\\/][\w./\\-]+\.md|prototypes[\\/]|" + ASSISTANT.upper() + r"\.md)",
                                 p.read_text(encoding="utf-8-sig")):
                cible = m.group(1).replace("\\", "/")
                if cible not in fichiers:
                    absents.add(f"{f} renvoie à {cible}")

    if not suivi_existant:
        git("init", "--quiet", "--initial-branch=main")
    for cle, val in (("core.autocrlf", "false"), ("user.name", nom), ("user.email", adresse),
                     ("offresoins.nomautorise", nom), ("offresoins.adresseautorisee", adresse),
                     ("core.hooksPath", ".githooks")):
        git("config", cle, val)

    nouveau_commit = False
    if problemes:
        if suivi_existant:
            git("reset", "--hard", "--quiet")   # le dépôt suivi revient à son dernier commit
            git("clean", "-fdq")
    else:
        git("add", "--all")
        if git("status", "--porcelain").stdout.strip():
            git("commit", "--quiet", "-m", f"{config.NOM_PROJET}, version du {version}")
            nouveau_commit = True
        identites = set(git("log", "--all", "--format=%an <%ae>%n%cn <%ce>").stdout.split("\n")) - {""}
        if identites != {f"{nom} <{adresse}>"}:
            problemes.append(f"identités inattendues dans le dépôt public, {sorted(identites)}")
        # lancé par git, qui fournit son propre interpréteur (sh n'existe pas dans le PowerShell de Windows)
        crochet = subprocess.run(["git", "hook", "run", "pre-push"], cwd=dest, capture_output=True, text=True,
                                 stdin=subprocess.DEVNULL)
        if crochet.returncode != 0:
            problemes.append("contrôle avant envoi refusé, " + " ".join(crochet.stdout.split()))

    dossiers: dict[str, int] = {}
    for f in fichiers:
        cle = f.split("/")[0] + ("/" if "/" in f else "")
        dossiers[cle] = dossiers.get(cle, 0) + 1
    nb_commits = git("rev-list", "--count", "HEAD").stdout.strip() or "0"
    etat = ("nouveau commit" if nouveau_commit else "aucun changement depuis le dernier commit")
    print(f"Code public préparé dans {dest}, version du {version}, {len(fichiers)} fichiers, {etat}, "
          f"{nb_commits} commit(s) au total.")
    for d, n in sorted(dossiers.items()):
        print(f"  {d:28} {n}")
    print("Notes de docs/ publiées : " + ", ".join(sorted(DOCS_PUBLICS)))
    for x in sorted(absents):
        print("  à savoir, " + x + " (fichier non publié)")
    if problemes:
        print("PROBLÈMES BLOQUANTS :")
        for p in problemes:
            print("  " + p)
        return 20
    print("Aucun problème bloquant. Rien n'a été envoyé.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
