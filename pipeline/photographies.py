"""Suivi dans le temps des comptes (demande de Lucas du 26 octobre 2026, point 7 de la version 2).

Deux traces, pour pouvoir dire plus tard si une figure « bouge » et pourquoi.

1. Une photographie des comptes à chaque exécution, une par extraction du RPPS (la date annoncée par le producteur, pas
   le jour de l'exécution), dans resultats/historique/photographies/, avec la version du programme qui l'a calculée.
   Des agrégats seulement, aucun nom ni identifiant. Une nouvelle exécution sur la même extraction remplace la
   photographie et le dit dans l'index.
2. Une archive mensuelle de l'extraction brute du RPPS, sur le PC seulement (donnees/archives/rpps/, hors de Git),
   pour pouvoir recalculer une date passée avec les règles du moment. Sans elle, un changement de règle se confondrait
   avec un vrai changement. Les noms, prénoms et coordonnées de contact n'y sont pas gardés, ils ne servent à aucun
   calcul (Lucas, 31 octobre 2026). Elle garde l'identifiant, nécessaire pour compter chaque professionnel une fois, et
   ne doit jamais être publiée.
"""
from __future__ import annotations

import json
import re
import subprocess
import zipfile
from datetime import datetime

import pandas as pd

from . import config
from .util import JOURNAL, date_version, detecter_separateur, lire_meta, log, norm

DOSSIER = config.RESULTATS / "historique" / "photographies"
ARCHIVES_RPPS = config.DONNEES / "archives" / "rpps"
NIVEAUX = ("reg", "dep", "epci")
# colonnes retirées de l'archive (noms normalisés) ; la civilité reste, seule approximation du sexe
COLONNES_HORS_ARCHIVE = (r"^nom d exercice$", r"^prenom d exercice$", r"^telephone", r"^telecopie", r"^adresse e mail")


def version_programme() -> str | None:
    """Commit du programme qui a calculé la photographie, suivi de « +modifs » si le code n'est pas commité."""
    try:
        h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=config.RACINE, capture_output=True, text=True,
                           timeout=20).stdout.strip()
        sale = subprocess.run(["git", "status", "--porcelain", "--", "pipeline", "run.py"], cwd=config.RACINE,
                              capture_output=True, text=True, timeout=20).stdout.strip()
        return (h + ("+modifs" if sale else "")) or None
    except (OSError, subprocess.SubprocessError):
        return None


def table(effectifs: dict) -> pd.DataFrame:
    """Comptes longs (niveau, code, prof, mode, n) des niveaux suivis, lignes à zéro retirées."""
    parts = []
    for niv in NIVEAUX:
        e = effectifs.get(niv)
        if isinstance(e, pd.DataFrame) and len(e):
            parts.append(e.loc[e["n"] > 0, ["code", "prof", "mode", "n"]].assign(niveau=niv))
    if not parts:
        return pd.DataFrame(columns=["niveau", "code", "prof", "mode", "n"])
    t = pd.concat(parts, ignore_index=True)[["niveau", "code", "prof", "mode", "n"]]
    t["n"] = t["n"].astype(int)
    return t.sort_values(["niveau", "code", "prof", "mode"]).reset_index(drop=True)


def ecrire(agg, jour: str) -> dict | None:
    """Photographie des comptes de cette exécution, nommée par la date de l'extraction du RPPS."""
    from .sources import rpps
    meta = rpps.META_LUE or lire_meta(config.BRUT / "rpps_activite.txt")
    date_rpps = date_version(meta) if meta else None
    if not date_rpps:
        JOURNAL.controle("Photographie des comptes", "non écrite, date de l'extraction du RPPS inconnue")
        return None
    DOSSIER.mkdir(parents=True, exist_ok=True)
    t = table(getattr(agg, "effectifs", {}) or {})
    f = DOSSIER / f"effectifs_{date_rpps}.csv.gz"
    remplace = f.exists()
    t.to_csv(f, sep=";", index=False, encoding="utf-8", compression="gzip")
    index_f = DOSSIER / "index.json"
    index = json.loads(index_f.read_text(encoding="utf-8")) if index_f.exists() else []
    index = [i for i in index if i.get("date_rpps") != date_rpps]
    entree = {"date_rpps": date_rpps, "execution": jour, "calcule_le": datetime.now().isoformat(timespec="seconds"),
              "version_programme": version_programme(), "lignes": int(len(t)), "fichier": f.name}
    index = sorted(index + [entree], key=lambda i: i["date_rpps"])
    index_f.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    JOURNAL.controle("Photographie des comptes", f"extraction RPPS du {date_rpps}, {len(t)} lignes"
                     + (", remplace la photographie précédente de la même extraction" if remplace else "")
                     + f", {len(index)} photographie{'s' if len(index) > 1 else ''} gardée{'s' if len(index) > 1 else ''}")
    return entree


def copier_sans_noms(source, flux) -> list[str]:
    """Copie un fichier du RPPS dans un flux binaire sans les colonnes de COLONNES_HORS_ARCHIVE, renvoie celles retirées.
    Le reste de chaque ligne est gardé tel quel (séparateur, fin de ligne, octets illisibles)."""
    with open(source, encoding="utf-8-sig", errors="surrogateescape", newline="") as f:
        entete = f.readline()
        fin = entete[len(entete.rstrip("\r\n")):]
        sep = detecter_separateur(entete.rstrip("\r\n"))
        cols = entete.rstrip("\r\n").split(sep)
        retirees = {i for i, c in enumerate(cols) if any(re.search(m, norm(c)) for m in COLONNES_HORS_ARCHIVE)}

        def garder(ligne: str) -> bytes:
            corps = ligne.rstrip("\r\n")
            champs = corps.split(sep)
            return (sep.join(v for i, v in enumerate(champs) if i not in retirees)
                    + ligne[len(corps):]).encode("utf-8", "surrogateescape")

        flux.write(garder(entete if fin else entete + "\n"))
        for ligne in f:
            flux.write(garder(ligne))
    return [cols[i] for i in sorted(retirees)]


def archiver_rpps(fichiers: dict) -> str | None:
    """Archive mensuelle de l'extraction brute du RPPS (une par mois, la première vue), sans les noms ni les
    coordonnées de contact, sur le PC seulement."""
    meta = lire_meta(fichiers.get("activite")) if fichiers.get("activite") else {}
    date_rpps = date_version(meta) if meta else None
    if not date_rpps:
        return None
    ARCHIVES_RPPS.mkdir(parents=True, exist_ok=True)
    mois = date_rpps[:7]
    deja = sorted(ARCHIVES_RPPS.glob(f"rpps_{mois}-*.zip"))
    if deja:
        JOURNAL.controle("Archive mensuelle du RPPS", f"{deja[0].name} déjà gardée pour {mois}")
        return deja[0].name
    cible = ARCHIVES_RPPS / f"rpps_{date_rpps}.zip"
    tmp = cible.with_suffix(".part")
    log.info("archive de l'extraction du RPPS du %s (une fois par mois, sans les noms, sur le PC seulement)", date_rpps)
    retirees = {}
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for chemin in fichiers.values():
            with z.open(chemin.name, "w", force_zip64=True) as flux:
                retirees[chemin.name] = copier_sans_noms(chemin, flux)
            m = chemin.with_name(chemin.name + ".meta.json")
            if m.exists():
                z.write(m, m.name)
    noms = [n for n, r in retirees.items() if not any(re.search(r"^nom d exercice$", norm(c)) for c in r)]
    if noms:
        tmp.unlink()
        raise RuntimeError("colonne des noms introuvable dans " + ", ".join(noms) + ", archive non écrite")
    tmp.replace(cible)
    JOURNAL.controle("Archive mensuelle du RPPS", f"{cible.name}, {cible.stat().st_size / 1e6:.0f} Mo, gardée sur le PC "
                     f"seulement, {sum(map(len, retirees.values()))} colonnes de noms et de coordonnées retirées "
                     "(identifiants gardés, jamais publiée)")
    return cible.name
