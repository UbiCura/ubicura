"""Outils communs. Téléchargement robuste, résolution des ressources data.gouv,
normalisation de texte, détection tolérante des colonnes, journal des sources."""
from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path

from . import config

log = logging.getLogger("offre_soins")


# ---------------------------------------------------------------- journal des sources
@dataclass
class Entree:
    source: str
    statut: str          # "ok", "absent", "erreur", "ignoré"
    detail: str = ""
    url: str = ""
    date_donnees: str = ""
    lignes: int | None = None
    producteur: str = ""
    licence: str = ""
    page: str = ""          # page de présentation du jeu de données chez le producteur


@dataclass
class Journal:
    entrees: list[Entree] = field(default_factory=list)
    controles: list[tuple[str, str]] = field(default_factory=list)

    def note(self, source, statut, detail="", **kw):
        detail = format_fr(str(detail)) if statut == "ok" else str(detail)
        e = Entree(source, statut, detail, **kw)
        for motif, producteur, licence, page in config.SOURCES_INFO:
            if re.search(motif, source):
                e.producteur = e.producteur or producteur
                e.licence = e.licence or licence
                m = re.search(r"^(https://[^/]+)/api/explore/v2\.1/catalog/datasets/([^/?]+)", e.url or "")
                e.page = e.page or page or (f"{m.group(1)}/explore/dataset/{m.group(2)}/" if m else
                                            e.url if "/explore/dataset/" in (e.url or "") else "")
                break
        self.entrees.append(e)
        niveau = logging.INFO if statut == "ok" else logging.WARNING
        log.log(niveau, "[%s] %s %s", source, statut, detail)

    def controle(self, nom, resultat):
        """Contrôle de cohérence consigné dans le rapport (nombres mis au format français)."""
        resultat = format_fr(str(resultat))
        self.controles.append((nom, resultat))
        log.info("contrôle | %s | %s", nom, resultat)

    def to_dict(self):
        return {"sources": [asdict(e) for e in self.entrees], "controles": self.controles}


JOURNAL = Journal()


# ---------------------------------------------------------------- texte
def format_fr(texte: str) -> str:
    """« 90.9% » devient « 90,9 % », « 348021 » devient « 348 021 », « 9666 » devient « 9 666 ». Les nombres de
    quatre chiffres compris entre 1900 et 2099 sont laissés tels quels (années), un effectif de cet ordre doit donc
    être mis en forme avant l'appel (entier_fr)."""
    texte = re.sub(r"(\d)\.(\d+)\s?%", r"\1,\2 %", texte)
    texte = re.sub(r"(?<![\d,.])(\d+)\s?%", r"\1 %", texte)
    texte = re.sub(r"(?<![\w.])(\d+)\.(\d+)(?![\w.])", r"\1,\2", texte)
    texte = re.sub(r"(?<![\d,.])\d{5,}(?![\d,.])", lambda m: entier_fr(int(m.group())), texte)
    return re.sub(r"(?<![\d,.\-–/])\d{4}(?![\d,.%\-–/])",
                  lambda m: m.group() if 1900 <= int(m.group()) <= 2099 else entier_fr(int(m.group())), texte)


def entier_fr(n) -> str:
    """Entier avec espace des milliers, « 2013 » devient « 2 013 »."""
    return f"{int(n):,}".replace(",", " ")


def norm(s) -> str:
    """Minuscules, sans accents, ponctuation réduite à des espaces."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def slug(s) -> str:
    return norm(s).replace(" ", "_")


def trouver_colonne(colonnes, motifs, obligatoire=True, nom=""):
    """Renvoie la première colonne dont le nom normalisé correspond à un des motifs (regex)."""
    normes = {c: norm(c) for c in colonnes}
    for m in motifs:
        for c, n in normes.items():
            if re.search(m, n):
                return c
    if obligatoire:
        raise KeyError(
            f"Colonne introuvable pour « {nom or motifs[0]} ». Colonnes disponibles :\n  - "
            + "\n  - ".join(colonnes))
    return None


# ---------------------------------------------------------------- réseau
def _session():
    import requests
    s = requests.Session()
    s.headers["User-Agent"] = config.USER_AGENT
    return s


def get_json(url, essais=4):
    s = _session()
    for i in range(essais):
        try:
            r = s.get(url, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            if i == essais - 1:
                raise
            log.warning("échec %s (%s), nouvel essai", url, e)
            time.sleep(2 ** i)


def get_texte(url, essais=4):
    s = _session()
    for i in range(essais):
        try:
            r = s.get(url, timeout=60)
            r.raise_for_status()
            return r.text
        except Exception as e:  # noqa: BLE001
            if i == essais - 1:
                raise
            log.warning("échec %s (%s), nouvel essai", url, e)
            time.sleep(2 ** i)


def meta_path(dest: Path) -> Path:
    return dest.with_suffix(dest.suffix + ".meta.json")


def lire_meta(dest: Path) -> dict:
    p = meta_path(dest)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def date_version(meta: dict) -> str:
    """Date de la version des données (AAAA-MM-JJ), celle annoncée par le producteur, à défaut le jour du
    téléchargement. Sert à dater chaque source dans le journal et sur le site."""
    from email.utils import parsedate_to_datetime
    m = str(meta.get("maj_source") or "")
    if re.match(r"^[A-Z][a-z]{2}, ", m):
        try:
            return parsedate_to_datetime(m).date().isoformat()
        except (TypeError, ValueError):
            pass
    elif re.match(r"^\d{4}-\d{2}-\d{2}", m):
        return m[:10]
    return str(meta.get("telecharge_le") or "")[:10]


def fichier_complet(chemin: Path) -> bool:
    """Vérifie qu'un fichier binaire n'est pas tronqué (signature de fin du parquet, index du zip,
    fin du flux gzip). Certains serveurs n'annoncent pas la taille, une coupure passe sinon inaperçue."""
    nom = chemin.name.lower()
    try:
        if nom.endswith(".parquet"):
            with open(chemin, "rb") as f:
                f.seek(-4, 2)
                return f.read(4) == b"PAR1"
        if nom.endswith(".zip"):
            import zipfile
            with zipfile.ZipFile(chemin) as z:
                return len(z.namelist()) > 0
        if nom.endswith(".gz"):
            import gzip
            with gzip.open(chemin, "rb") as f:
                while f.read(1 << 24):
                    pass
            return True
    except Exception:  # noqa: BLE001
        return False
    return True


def telecharger(url: str, dest: Path, famille: str, rafraichir=False, hors_ligne=False,
                taille_min=1000, extra_meta=None) -> Path:
    """Télécharge url vers dest, avec cache, reprise d'erreur et fichier temporaire.
    En mode hors ligne, exige que le fichier soit déjà présent."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    # quand le producteur annonce la date de sa version (maj_source), c'est elle qui décide, pas l'âge du cache
    version = (extra_meta or {}).get("maj_source") or ""
    version_locale = lire_meta(dest).get("maj_source") or "" if dest.exists() else ""
    if dest.exists() and not rafraichir and not hors_ligne and version and version_locale and fichier_complet(dest):
        if version == version_locale:
            log.info("cache %s, version du producteur inchangée (%s)", dest.name, version)
            return dest
        log.info("%s, nouvelle version du producteur (%s, précédente %s)", dest.name, version, version_locale)
        rafraichir = True
    if dest.exists() and not rafraichir:
        age = datetime.now() - datetime.fromtimestamp(dest.stat().st_mtime)
        if not fichier_complet(dest):
            log.warning("fichier en cache incomplet, nouveau téléchargement : %s", dest.name)
            if hors_ligne:
                raise IOError(f"Mode hors ligne et fichier incomplet : {dest}")
        elif hors_ligne or age < timedelta(days=config.CACHE_JOURS.get(famille, 30)):
            log.info("cache %s (%.1f Mo, %d j)", dest.name, dest.stat().st_size / 1e6, age.days)
            return dest
    if hors_ligne:
        raise FileNotFoundError(f"Mode hors ligne et fichier absent : {dest}")
    s = _session()
    tmp = dest.with_suffix(dest.suffix + ".part")
    for essai in range(4):
        try:
            with s.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length") or 0)
                entetes = {k: r.headers[k] for k in ("Last-Modified", "ETag") if r.headers.get(k)}
                lu, dernier = 0, time.time()
                with open(tmp, "wb") as f:
                    for bloc in r.iter_content(1 << 20):
                        f.write(bloc)
                        lu += len(bloc)
                        if time.time() - dernier > 5:
                            pct = f" ({lu / total:.0%})" if total else ""
                            log.info("  %s : %.0f Mo%s", dest.name, lu / 1e6, pct)
                            dernier = time.time()
            if tmp.stat().st_size < taille_min:
                raise IOError(f"fichier trop petit ({tmp.stat().st_size} octets)")
            if total and tmp.stat().st_size != total:
                raise IOError(f"fichier tronqué ({tmp.stat().st_size} octets sur {total})")
            # le contrôle de signature porte sur le nom final (l'extension .part masque le type)
            tmp_type = dest.with_name(dest.stem + ".verif" + dest.suffix)
            tmp.replace(tmp_type)
            if not fichier_complet(tmp_type):
                tmp_type.replace(tmp)
                raise IOError("fichier incomplet (signature de fin absente)")
            tmp = tmp_type
            tmp.replace(dest)
            # Last-Modified et ETag permettront à une tâche planifiée de savoir si la source a changé
            meta = {"url": url, "telecharge_le": datetime.now().isoformat(timespec="seconds"),
                    "octets": dest.stat().st_size, **{k.lower().replace("-", "_"): v for k, v in entetes.items()}}
            meta.update(extra_meta or {})
            meta_path(dest).write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            log.info("téléchargé %s (%.1f Mo)", dest.name, dest.stat().st_size / 1e6)
            return dest
        except Exception as e:  # noqa: BLE001
            log.warning("échec du téléchargement %s (essai %d) : %s", url, essai + 1, e)
            time.sleep(3 * (essai + 1))
    raise IOError(f"Impossible de télécharger {url}")


def ressources_datagouv(dataset: str) -> list[dict]:
    """Liste des ressources d'un jeu data.gouv (slug ou identifiant)."""
    d = get_json(config.DATAGOUV_API.format(dataset))
    out = []
    for r in d.get("resources", []):
        out.append({
            "titre": r.get("title") or "",
            "url": r.get("latest") or r.get("url") or "",
            "url_directe": r.get("url") or "",
            "format": (r.get("format") or "").lower(),
            "taille": r.get("filesize") or 0,
            "maj": r.get("last_modified") or r.get("created_at") or "",
        })
    return out


def choisir_ressource(ressources, motif, formats=None):
    """Ressource dont le titre, l'URL ou le nom de fichier correspond au motif."""
    cand = []
    for r in ressources:
        if formats and r["format"] and r["format"] not in formats:
            continue
        texte = norm(r["titre"]) + " " + norm(r["url_directe"].rsplit("/", 1)[-1])
        if re.search(motif, texte):
            cand.append(r)
    return max(cand, key=lambda r: r["taille"] or 0) if cand else None


def detecter_separateur(ligne: str) -> str:
    comptes = {s: ligne.count(s) for s in ["|", ";", "\t", ","]}
    return max(comptes, key=comptes.get)


def premiere_ligne(chemin: Path, encodage="utf-8-sig") -> str:
    with open(chemin, encoding=encodage, errors="replace") as f:
        return f.readline().rstrip("\r\n")
