"""Sectorisation psychiatrique, arrêtés des agences régionales de santé (ARS).

Chaque région est décrite par un fichier de contenus/sectorisation/ (code de région, document, émetteur, date, courriel
qui l'a transmis et celui qui confirme qu'il est à jour, lecteur du tableau, établissements porteurs avec leur numéro
FINESS d'entité juridique, limites signalées par l'ARS). Le document lui-même est rangé dans donnees/brut/sectorisation
tel que reçu. Ajouter une région, c'est déposer son document et écrire sa description, sans toucher au code, sauf si son
tableau demande un nouveau lecteur.

Les arrêtés arrivent par courriel en réponse à une demande d'accès aux documents administratifs. Ils ne se téléchargent
pas d'eux-mêmes, c'est l'exception à la règle « tout est automatisable », signalée à Lucas et acceptée le 29 octobre 2026.
Licence, document administratif communiqué, réutilisable sans altération avec sa source et sa date (CRPA, articles
L321-1 et L322-1, registre pipeline/licences.py).

Sortie, une ligne par commune, type de secteur et secteur : région, département, commune (code actuel du référentiel),
code et nom lus dans l'arrêté, partie de commune quand une ville est découpée entre secteurs (« LILLE NORD »), type
(G psychiatrie générale, I psychiatrie infanto-juvénile), secteur (« 59G22 »), établissement porteur et son numéro
FINESS d'entité juridique."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

from .. import config
from ..util import JOURNAL

DESCRIPTIONS = config.RACINE / "contenus" / "sectorisation"
DOSSIER = config.BRUT / "sectorisation"
SOURCE = "Agences régionales de santé, arrêtés de sectorisation psychiatrique"
COLONNES = ["region", "dep", "commune", "rattachement", "code_arrete", "nom_arrete", "partie", "type", "secteur",
            "etablissement", "ej", "document", "date_document"]

# une ligne du tableau, établissement porteur, code commune, nom de la commune, secteur (« 02 G 01 », « 59G22 »)
_LIGNE = re.compile(r"^(?P<etab>.+?)\s+(?P<code>\d[\dAB]\d{3})\s+(?P<nom>.+?)\s+(?P<dep>\d[\dAB])\s*(?P<type>[GIP])\s*"
                    r"(?P<num>\d{1,3})\s*$")
_ENTETE = re.compile(r"^Etablissement de sant", re.I)


def cle(s: str) -> str:
    """Clé de comparaison d'un nom, sans accents, espaces ni ponctuation (l'arrêté écrit « CH Douai » et « CH DOUAI »)."""
    s = unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def _nom_propre(s: str) -> str:
    """Nom lu dans le PDF, sans l'espace que l'extraction place parfois devant une lettre accentuée (« R ésigny »)."""
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"(?<=\w) (?=[À-ÖØ-öø-ÿ])", "", s)


def lire_tableau_lignes(pdf: Path) -> tuple[pd.DataFrame, int]:
    """Lecteur des tableaux d'une ligne par commune (arrêté des Hauts-de-France). Une ligne coupée par un nom de commune
    trop long est recollée aux suivantes (trois au plus). Renvoie les lignes lues et le nombre de fragments non lus."""
    import pypdf
    lignes, tampon, perdus = [], [], 0
    for page in pypdf.PdfReader(str(pdf)).pages:
        for l in (page.extract_text() or "").splitlines():
            l = l.strip()
            if not l or l.isdigit() or _ENTETE.match(l):
                continue
            m = _LIGNE.match(l)
            if m:
                perdus += len(tampon)
                tampon = []
                lignes.append(m.groupdict())
                continue
            if tampon:
                joint = tampon[0]
                for t in tampon[1:] + [l]:
                    joint = joint + t if joint.endswith("-") else joint + " " + t
                m = _LIGNE.match(joint)
                if m:
                    tampon = []
                    lignes.append(m.groupdict())
                    continue
            tampon.append(l)
            if len(tampon) > 3:
                perdus += 1
                tampon.pop(0)
    perdus += len(tampon)
    t = pd.DataFrame(lignes)
    if t.empty:
        return t, perdus
    t["etab"] = t["etab"].map(lambda s: re.sub(r"\s+", " ", s).strip())
    t["nom"] = t["nom"].map(_nom_propre)
    t["secteur"] = t["dep"] + t["type"] + t["num"].astype(int).map("{:02d}".format)
    return t, perdus


LECTEURS = {"tableau_lignes": lire_tableau_lignes}


def descriptions() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DESCRIPTIONS.glob("*.json"))]


def charger(ref) -> pd.DataFrame | None:
    """Secteurs de toutes les régions décrites dont le document est présent, None si aucune."""
    parts = []
    for d in descriptions():
        pdf = DOSSIER / d["fichier"]
        nom = f"Sectorisation psychiatrique, {d['nom']}"
        if not pdf.exists():
            JOURNAL.note(nom, "absente", f"document {d['fichier']} absent de donnees/brut/sectorisation")
            continue
        try:
            t, perdus = LECTEURS[d["lecteur"]](pdf)
        except Exception as e:  # noqa: BLE001
            JOURNAL.note(nom, "erreur", f"{type(e).__name__} {e}"[:300])
            continue
        etabs = {cle(k): v for k, v in d["etablissements"].items() if not k.startswith("_")}
        out = pd.DataFrame({"region": d["region"], "dep": t["dep"], "code_arrete": t["code"], "nom_arrete": t["nom"],
                            "type": t["type"], "secteur": t["secteur"], "etablissement": t["etab"],
                            "ej": t["etab"].map(lambda s: etabs.get(cle(s))), "document": d["document"],
                            "date_document": d["date_document"]})
        out = rattacher(out, ref)
        controler(out, ref, d, perdus)
        JOURNAL.note(nom, "ok", f"{d['document']}, {d['emetteur']}, {len(out)} lignes, {out['secteur'].nunique()} "
                                f"secteurs, {out['etablissement'].nunique()} libellés d'établissement",
                     date_donnees=d["date_document"], producteur=d["emetteur"], licence=d["licence"])
        parts.append(out)
    return pd.concat(parts, ignore_index=True)[COLONNES] if parts else None


def _mots(s: str) -> list[str]:
    s = (s or "").replace("œ", "oe").replace("Œ", "Oe").replace("æ", "ae").replace("Æ", "Ae")
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return re.findall(r"[a-z0-9]+", s)


def rattacher(t: pd.DataFrame, ref) -> pd.DataFrame:
    """Commune actuelle de chaque ligne de l'arrêté (colonne commune) et manière de l'établir (colonne rattachement) :
    « code », le code de l'arrêté est celui d'une commune actuelle de même nom ; « commune fusionnée », ancien code
    rattaché par le référentiel ; « nom », commune actuelle du même département qui porte le nom de l'arrêté, quand le
    code a changé depuis l'arrêté (communes nouvelles ou rétablies, « Les Hauts Talican » sous le code 60054, aujourd'hui
    Beaumont-les-Nonains) ou n'est plus connu du référentiel (Filain, 02311, aujourd'hui dans Pargny-et-Filain). Une
    ville découpée entre secteurs garde le nom de son quartier (colonne partie, « LILLE NORD »)."""
    com = ref.communes
    nom_de = com.set_index("code")["nom"]
    par_dep = {dep: [(c, _mots(n)) for c, n in zip(g["code"], g["nom"])] for dep, g in com.groupby("dep")}

    def par_nom(dep, nom):
        m = _mots(nom)
        exact = [c for c, mc in par_dep.get(dep, []) if mc == m]
        if exact:
            return exact[0]
        # nom de l'arrêté contenu dans un seul nom actuel du département (« Filain » dans « Pargny-et-Filain »)
        cont = [c for c, mc in par_dep.get(dep, []) if len(m) and any(mc[i:i + len(m)] == m for i in range(len(mc)))]
        return cont[0] if len(cont) == 1 else None

    lignes = []
    for r in t.to_dict("records"):
        code, nom, dep = r["code_arrete"], r["nom_arrete"], r["dep"]
        base = _mots(nom_de.get(code, "")) if code in nom_de.index else []
        mots = _mots(nom)
        if base and mots[:len(base)] == base:
            # même commune, ou ville découpée quand l'arrêté ajoute un quartier au nom
            lignes.append({**r, "commune": code, "rattachement": "code", "partie": nom if len(mots) > len(base) else None})
            continue
        if code not in nom_de.index and code in ref.anciens:
            lignes.append({**r, "commune": ref.anciens[code], "rattachement": "commune fusionnée", "partie": None})
            continue
        autre = par_nom(dep, nom)
        if code in nom_de.index and (autre is None or autre == code):
            # même code, la commune a changé de nom ou en a pris un plus long (Guignicourt, aujourd'hui
            # Villeneuve-sur-Aisne ; Templeuve, aujourd'hui Templeuve-en-Pévèle)
            lignes.append({**r, "commune": code, "rattachement": "code, nom changé", "partie": None})
            continue
        if autre:
            lignes.append({**r, "commune": autre, "rattachement": "nom", "partie": None})
        if code in nom_de.index:
            # code d'une commune actuelle sous un autre nom, le territoire de l'arrêté la comprenait
            lignes.append({**r, "commune": code, "rattachement": "code, autre commune", "partie": None})
        elif not autre:
            lignes.append({**r, "commune": None, "rattachement": "inconnu", "partie": None})
    return pd.DataFrame(lignes)


def controler(t: pd.DataFrame, ref, d: dict, perdus: int) -> dict:
    """Contrôles d'une région : toute commune de la région couverte une fois par type de secteur, communes fusionnées
    rattachées par le référentiel, aucune ligne perdue à la lecture, chaque établissement porteur relié à FINESS.
    Renvoie les comptes, écrits aussi dans le journal."""
    com = ref.communes[ref.communes["reg"] == d["region"]]
    r = {"lignes": len(t), "fragments_non_lus": perdus, "codes_inconnus": int(t["commune"].isna().sum()),
         "codes_anciens": int((t["rattachement"] == "commune fusionnée").sum()),
         "par_le_nom": sorted(set(t.loc[t["rattachement"].isin(["nom", "code, autre commune"]), "commune"].dropna())),
         "nom_change": int((t["rattachement"] == "code, nom changé").sum()),
         "etablissements_sans_finess": sorted(set(t.loc[t["ej"].isna(), "etablissement"]))}
    for ty in d["types"]:
        x = t[t["type"] == ty].dropna(subset=["commune"])
        n = x.groupby("commune")["secteur"].nunique()
        couvertes = set(n.index)
        r[f"{ty}_sans_secteur"] = sorted(set(com["code"]) - couvertes)
        r[f"{ty}_hors_region"] = sorted(couvertes - set(com["code"]))
        # plusieurs secteurs d'un type pour une commune, ville découpée (partie nommée) ou communes fusionnées
        plusieurs = n[n > 1].index
        decoupees = set(x.loc[x["partie"].notna() & x["commune"].isin(plusieurs), "commune"])
        fusion = set(x.loc[(x["commune"] != x["code_arrete"]) & x["commune"].isin(plusieurs), "commune"])
        r[f"{ty}_plusieurs_secteurs"] = sorted(set(plusieurs))
        r[f"{ty}_plusieurs_inexpliques"] = sorted(set(plusieurs) - decoupees - fusion)
        JOURNAL.controle(f"Sectorisation, {d['nom']}, {d['types'][ty]}, communes couvertes (attendu, toutes)",
                         f"{len(couvertes & set(com['code']))} sur {len(com)} ; sans secteur {len(r[f'{ty}_sans_secteur'])} ; "
                         f"hors de la région {len(r[f'{ty}_hors_region'])} ; dans plusieurs secteurs "
                         f"{len(r[f'{ty}_plusieurs_secteurs'])} (ville découpée {len(decoupees)}, communes fusionnées "
                         f"{len(fusion)}, inexpliqué {len(r[f'{ty}_plusieurs_inexpliques'])})")
    JOURNAL.controle(f"Sectorisation, {d['nom']}, lecture du document (attendu, aucune perte)",
                     f"{r['lignes']} lignes, {perdus} fragments non lus, {r['codes_inconnus']} codes inconnus du "
                     f"référentiel, {r['codes_anciens']} codes de communes fusionnées rattachés, {len(r['par_le_nom'])} communes "
                     f"rattachées par le nom (code changé depuis l'arrêté), établissements sans "
                     f"numéro FINESS {len(r['etablissements_sans_finess'])}")
    return r
