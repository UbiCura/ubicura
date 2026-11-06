"""Inventaire du contenu du site, page par page, pour ne rien perdre à la refonte de la présentation.

Demande de Lucas du 30 octobre 2026 : la nouvelle présentation reprend tout ce que montre le site actuel (figures,
tableaux, cartes, encadrés). Ce script compte, dans chaque page HTML construite, les figures (SVG), les cartes (SVG
d'au moins 30 tracés), les tableaux, les images, et relève les titres (h2, h3, légendes de tableau). Il relève aussi
les limites connues des données (config.LIMITES) que chaque page écrit en texte, par leur phrase courte ou la première
phrase de leur texte (inventaire des limites du 31 octobre 2026) : une limite écrite avant la refonte doit l'être encore
après, sur une page au moins. Les pages dessinées
dans le navigateur (atlas, Explorer) sont relevées à part par outils/inventaire_navigateur.js, dont le résultat
s'ajoute au même fichier.

Usage :
  python outils/inventaire_site.py <dossier du site> <sortie.json>
  python outils/inventaire_site.py --comparer <avant.json> <apres.json> [correspondances.csv]
La comparaison sort en code 1 si un titre de l'inventaire d'avant ne se retrouve nulle part après (au besoin sous le
nom donné par le fichier de correspondances, ancien;nouveau) ou si un total baisse.
"""
import csv
import json
import re
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

DOSSIERS_EXCLUS = ("prototype", "prototype2", "prototype3", "prototype4", "maquettes", "_maquettes", "cesure", "polices")
MIN_TRACES_CARTE = 30


MOIS = "janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre"


def norm(t: str) -> str:
    """Titre comparable d'un inventaire à l'autre : sans accents ni ponctuation, et sans la date de la version (« totaux
    dans les fichiers du 30 octobre 2026 » devenait un titre perdu à chaque nouvelle version, 4 novembre 2026)."""
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(rf"\b(1er|\d{{1,2}}) ({MOIS}) \d{{4}}\b", "date", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


class _Releve(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.figures = self.cartes = self.tableaux = self.images = 0
        self.titres: list[str] = []
        self._svg = 0          # profondeur dans un SVG
        self._traces = 0       # tracés du SVG de plus haut niveau
        self._titre = None     # balise de titre en cours (h2, h3, caption)
        self._texte = []
        self._ignorer = 0      # script, style
        self.lu: list[str] = []   # texte lu de la page (jamais les attributs, donc jamais une infobulle title)

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._ignorer += 1
        if tag == "svg":
            if self._svg == 0:
                self._traces = 0
            self._svg += 1
        elif self._svg and tag in ("path", "polygon"):
            self._traces += 1
        if tag == "table":
            self.tableaux += 1
        if tag == "img":
            self.images += 1
        if tag in ("h2", "h3", "caption") and not self._svg:
            self._titre, self._texte = tag, []

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._ignorer = max(0, self._ignorer - 1)
        if tag == "svg" and self._svg:
            self._svg -= 1
            if self._svg == 0:
                self.figures += 1
                if self._traces >= MIN_TRACES_CARTE:
                    self.cartes += 1
        if tag == self._titre:
            t = re.sub(r"\s+", " ", "".join(self._texte)).strip()
            if t:
                self.titres.append(t)
            self._titre = None

    def handle_data(self, data):
        if self._titre and not self._ignorer:
            self._texte.append(data)
        if not self._ignorer:
            self.lu.append(data)


def _reperes_limites() -> dict[str, list[str]]:
    """Pour chaque limite de config.LIMITES, les phrases qui la reconnaissent dans une page : sa phrase courte et la
    première phrase de son texte, normalisées."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from pipeline import config
    out = {}
    for k, L in config.LIMITES.items():
        ph = [config.LIMITES_COURT.get(k, ""), (L.get("texte") or "").split(". ")[0]]
        out[k] = [n for n in (norm(p) for p in ph) if len(n) > 30]
    return out


_LIMITES = None


def limites_lues(texte: str) -> list[str]:
    """Clés des limites dont une phrase figure dans le texte lu d'une page."""
    global _LIMITES
    if _LIMITES is None:
        _LIMITES = _reperes_limites()
    t = norm(texte)
    return sorted(k for k, ph in _LIMITES.items() if any(p in t for p in ph))


def releve_page(chemin: Path) -> dict:
    r = _Releve()
    r.feed(chemin.read_text(encoding="utf-8", errors="ignore"))
    return {"figures": r.figures, "cartes": r.cartes, "tableaux": r.tableaux, "images": r.images, "titres": r.titres,
            "limites": limites_lues(" ".join(r.lu))}


def inventaire(site: Path) -> dict:
    pages = {}
    for f in sorted(site.rglob("*.html")):
        rel = f.relative_to(site)
        if any(p in DOSSIERS_EXCLUS for p in rel.parts[:-1]) or f.name.endswith(".impression.html"):
            continue
        pages[rel.as_posix()] = releve_page(f)
    total = {k: sum(p[k] for p in pages.values()) for k in ("figures", "cartes", "tableaux", "images")}
    return {"site": str(site), "pages": pages, "total": total}


def _tous_titres(inv: dict) -> set[str]:
    s = set()
    for p in inv["pages"].values():
        s.update(norm(t) for t in p["titres"])
    for p in inv.get("navigateur", {}).values():
        s.update(norm(t) for t in p.get("titres", []))
    return s


def comparer(avant: dict, apres: dict, correspondances: dict[str, str] | None = None,
             baisses: dict[str, int] | None = None) -> list[str]:
    """Écarts entre deux inventaires : titres disparus et totaux en baisse. Liste vide si rien n'est perdu.
    Une correspondance dont l'ancien titre finit par « * » vaut pour tout titre qui commence ainsi, et un nouveau titre
    qui finit par « * » est trouvé dès qu'un titre d'après commence ainsi : un titre propre à chaque territoire
    (« Évolution depuis 2016, Cher ») se range sous un seul motif. baisses donne, par total, la baisse décidée (fiche
    resserrée validée par Lucas le 31 octobre 2026 : les tableaux d'évolution devenus une colonne)."""
    exacts, motifs = {}, []
    for a, b in (correspondances or {}).items():
        cible = (norm(b.rstrip("*")), b.endswith("*"))
        if a.endswith("*"):
            motifs.append((norm(a.rstrip("*")), cible))
        else:
            exacts[norm(a)] = cible
    apres_titres = _tous_titres(apres)
    manques = []
    for t in sorted(_tous_titres(avant)):
        cible, debut = exacts.get(t) or next((c for m, c in motifs if t.startswith(m)), (t, False))
        trouve = any(x.startswith(cible) for x in apres_titres) if debut else cible in apres_titres
        if cible and not trouve:
            manques.append(f"titre absent après la refonte : {t}")
    # limites : comparées quand les deux inventaires les relèvent (ceux d'avant le 31 octobre 2026 ne le font pas)
    if all("limites" in p for p in avant["pages"].values()) and all("limites" in p for p in apres["pages"].values()):
        ecrites = {k for p in apres["pages"].values() for k in p["limites"]}
        for k in sorted({k for p in avant["pages"].values() for k in p["limites"]} - ecrites):
            manques.append(f"limite absente après la refonte : {k}")
    for k in ("figures", "cartes", "tableaux"):
        a = avant["total"][k] + sum(p.get(k, 0) for p in avant.get("navigateur", {}).values())
        b = apres["total"][k] + sum(p.get(k, 0) for p in apres.get("navigateur", {}).values())
        if b < a - (baisses or {}).get(k, 0):
            manques.append(f"{k} en baisse : {a} avant, {b} après")
    return manques


def lire_correspondances(chemin: Path) -> dict[str, str]:
    if not chemin.exists():
        return {}
    with chemin.open(encoding="utf-8") as f:
        return {l["ancien"]: l["nouveau"] for l in csv.DictReader(f, delimiter=";")}


if __name__ == "__main__":
    if sys.argv[1] == "--comparer":
        av = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        ap = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
        corr = lire_correspondances(Path(sys.argv[4])) if len(sys.argv) > 4 else {}
        m = comparer(av, ap, corr)
        print("\n".join(m) if m else "Rien de perdu.")
        sys.exit(1 if m else 0)
    site, sortie = Path(sys.argv[1]), Path(sys.argv[2])
    inv = inventaire(site)
    ancien = json.loads(sortie.read_text(encoding="utf-8")) if sortie.exists() else {}
    if "navigateur" in ancien:   # relevé du navigateur gardé d'une exécution à l'autre
        inv["navigateur"] = ancien["navigateur"]
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(inv, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(inv["pages"]), "pages", inv["total"])
