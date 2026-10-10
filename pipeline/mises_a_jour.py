"""Journal des mises à jour. À chaque exécution, l'état de chaque jeu de données (date côté producteur, date de
récupération) est comparé à celui de l'exécution précédente. Le journal dit quels jeux ont changé, comment les
effectifs nationaux ont bougé et quelles évolutions du site ont été faites depuis (lignes « Journal: » des messages
de commit). Il est conservé dans resultats/historique/ et publié sur la page « Journal des mises à jour » du site."""
from __future__ import annotations

import json
import re
import subprocess
from email.utils import parsedate_to_datetime

import pandas as pd

from . import config
from .util import JOURNAL, log

FICHIER = config.RESULTATS / "historique" / "journal_mises_a_jour.json"


def date_iso(texte) -> str:
    """Date AAAA-MM-JJ à partir d'une date ISO ou d'un en-tête HTTP (« Tue, 21 Jul 2026 16:11:45 GMT »)."""
    if not texte:
        return ""
    texte = str(texte)
    if re.match(r"^[A-Z][a-z]{2}, ", texte):
        try:
            return parsedate_to_datetime(texte).date().isoformat()
        except (TypeError, ValueError):
            return ""
    d = pd.to_datetime(texte[:19], errors="coerce")
    return "" if pd.isna(d) else d.date().isoformat()


def _groupe(chemin: str):
    for motif, nom, producteur, *_ in config.SOURCES_SUIVIES:
        if re.search(motif, chemin):
            return nom, producteur
    return None, None


def jeu_de_source(nom_source: str):
    """Jeu de données suivi auquel se rattache un nom de source (entrée du journal, source d'un indicateur)."""
    for _m, nom, _p, motif, *_ in config.SOURCES_SUIVIES:
        if re.search(motif, nom_source or ""):
            return nom
    return None


def ancre(nom_jeu: str) -> str:
    """Ancre de la fiche d'un jeu sur la page « Données sources »."""
    from .util import slug
    return slug(nom_jeu)[:40].strip("-_")


def etat_sources(brut=None) -> dict:
    """État de chaque jeu suivi, d'après les fichiers .meta.json de donnees/brut."""
    brut = brut or config.BRUT
    jeux = {}
    for p in sorted(brut.rglob("*.meta.json")):
        chemin = p.relative_to(brut).as_posix()[:-len(".meta.json")]
        nom, producteur = _groupe(chemin)
        if nom is None:
            continue
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        maj = m.get("maj_source") or m.get("last_modified") or ""
        # ce qui identifie la version d'un fichier, date côté producteur sinon étiquette HTTP sinon taille
        signature = str(maj or m.get("etag") or m.get("octets") or "")
        j = jeux.setdefault(nom, {"producteur": producteur, "fichiers": {}})
        j["fichiers"][chemin] = {"maj": date_iso(maj), "signature": signature,
                                 "recupere": date_iso(m.get("telecharge_le"))}
    for j in jeux.values():
        f = j["fichiers"].values()
        j["maj"] = max((x["maj"] for x in f if x["maj"]), default="")
        j["recupere"] = max((x["recupere"] for x in f if x["recupere"]), default="")
    return jeux


def comparer(avant: dict | None, apres: dict) -> list[dict]:
    """Jeux nouveaux, modifiés ou disparus entre deux états."""
    avant = avant or {}
    out = []
    for nom, j in apres.items():
        a = avant.get(nom)
        if a is None:
            out.append({"jeu": nom, "producteur": j["producteur"], "nature": "nouveau", "maj": j["maj"]})
            continue
        fa, fb = a["fichiers"], j["fichiers"]
        changes = sorted(k for k in fb if k in fa and fa[k]["signature"] != fb[k]["signature"])
        ajoutes, retires = sorted(set(fb) - set(fa)), sorted(set(fa) - set(fb))
        if changes or ajoutes or retires:
            out.append({"jeu": nom, "producteur": j["producteur"], "nature": "modifié", "maj": j["maj"],
                        "maj_avant": a.get("maj", ""), "fichiers": len(changes) + len(ajoutes),
                        "total": len(fb)})
    for nom, a in avant.items():
        if nom not in apres:
            out.append({"jeu": nom, "producteur": a["producteur"], "nature": "retiré", "maj": a.get("maj", "")})
    return out


def _git(*args) -> str:
    try:
        r = subprocess.run(["git", "-C", str(config.RACINE), *args], capture_output=True, text=True,
                           encoding="utf-8", timeout=20)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def evolutions_site(depuis: str | None) -> list[str]:
    """Lignes « Journal: » des commits faits depuis le commit consigné à l'exécution précédente."""
    if not depuis:
        return []
    brut = _git("log", f"{depuis}..HEAD", "--reverse", "--format=%B%x1e")
    motif = re.compile(config.JOURNAL_MOTIF_COMMIT, re.M)
    return [m.group(1).strip() for bloc in brut.split("\x1e") for m in motif.finditer(bloc)]


def effectifs_nationaux(national: pd.DataFrame) -> dict:
    t = national[national["mode"] == "all"] if "mode" in national else national
    n = dict(zip(t["prof"].astype(str), t["n"]))
    return {p: int(n[p]) for p in config.JOURNAL_PROFESSIONS if p in n}


def consigner(jour: str, national: pd.DataFrame, libelles: dict) -> dict:
    """Ajoute l'entrée du jour dans le journal. Une exécution refaite le même jour complète l'entrée du jour, les
    changements constatés depuis l'exécution précédente s'ajoutent à ceux déjà notés ce jour-là."""
    entrees = lire()
    precedentes = [e for e in entrees if e["date"] < jour]
    prec = precedentes[-1] if precedentes else None
    du_jour = next((e for e in entrees if e["date"] == jour), None)
    etat = etat_sources()
    eff = effectifs_nationaux(national)
    # sources, comparaison avec l'état laissé par l'exécution précédente, même si elle a eu lieu le même jour
    reference = du_jour["etat"] if du_jour else prec["etat"] if prec else None
    sources = {s["jeu"]: s for s in (du_jour or {}).get("sources", [])}
    if reference is not None:
        for c in comparer(reference, etat):
            avant = sources.get(c["jeu"])
            if avant:   # déjà changé plus tôt dans la journée, on garde la version de départ et la nature d'origine
                c = dict(c, maj_avant=avant.get("maj_avant", c.get("maj_avant", "")),
                         nature="nouveau" if avant["nature"] == "nouveau" else c["nature"])
            sources[c["jeu"]] = c
    # effectifs et nouveautés du site, comparés à la mise à jour d'un jour antérieur, à défaut au début de la journée
    ref_eff = prec["effectifs"] if prec else (du_jour or {}).get("effectifs_reference") or (du_jour or {}).get("effectifs") or eff
    ref_commit = prec["commit"] if prec else (du_jour or {}).get("commit_reference") or (du_jour or {}).get("commit")
    variations = [{"prof": p, "libelle": libelles.get(p, p), "avant": ref_eff[p], "apres": n}
                  for p, n in eff.items() if p in ref_eff and ref_eff[p] != n]
    indisponibles = sorted({e.source for e in JOURNAL.entrees if e.statut == "erreur"})
    entree = {"date": jour, "commit": _git("rev-parse", "HEAD"), "premiere": prec is None,
              "sources": list(sources.values()), "effectifs": eff, "effectifs_reference": ref_eff,
              "commit_reference": ref_commit, "variations": variations, "indisponibles": indisponibles,
              "site": evolutions_site(ref_commit), "etat": etat}
    entrees = precedentes + [entree] + [e for e in entrees if e["date"] > jour]
    FICHIER.parent.mkdir(parents=True, exist_ok=True)
    FICHIER.write_text(json.dumps(entrees, ensure_ascii=False, indent=1), encoding="utf-8")
    modifies = [s for s in entree["sources"] if s["nature"] != "retiré"]
    JOURNAL.controle("Jeux de données modifiés depuis l'exécution précédente",
                     "première exécution consignée" if reference is None else
                     f"{len(modifies)} sur {len(etat)}" + (f" ({', '.join(s['jeu'] for s in modifies)})" if modifies else ""))
    log.info("journal des mises à jour, %s", FICHIER)
    return entree


def lire() -> list[dict]:
    return json.loads(FICHIER.read_text(encoding="utf-8")) if FICHIER.exists() else []
