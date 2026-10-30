"""Bases complémentaires. Chaque base est décrite par un fichier JSON versionné dans complements/
(à la racine du projet). Le programme la télécharge, la lit, l'agrège aux niveaux supérieurs et
l'ajoute aux indicateurs de contexte. Elle entre alors automatiquement dans tous les croisements,
le rapport et l'atlas. Les fichiers téléchargés sont rangés dans donnees/complements/.

Tout doit être automatisable (tâche planifiée sur serveur). Une base est donc résolue soit par
data.gouv (« datagouv », slug ou identifiant du jeu, et « ressource », motif sur le titre ou le nom
du fichier), soit par une adresse stable (« url »), soit, en version 2, par un portail Opendatasoft
(« portail » et « jeu »). Un fichier sans l'un ni l'autre est refusé.

Exemple de descripteur (version 1)
{
  "nom": "Allocataires de l'AAH",
  "source": "CAF, data.caf.fr",
  "licence": "Licence Ouverte 2.0",
  "famille": "",                               "" pour tous, ou « Santé mentale », « Santé »
  "actif": true,
  "datagouv": "slug-du-jeu",                   ou "url": "https://...csv"
  "ressource": "motif",                        motif sur le titre de la ressource data.gouv
  "fichier": "caf_aah_com.csv",                nom local du fichier
  "separateur": ";",                          facultatif, détecté sinon
  "encodage": "utf-8",                        facultatif
  "niveau": "dep",                            com, epci, dep ou reg
  "colonne_code": "dept",
  "filtre": {"patho_niv1": "Maladies psychiatriques"},   facultatif, lignes à garder
  "indicateurs": [
    {"colonne": "Ntop", "id": "patients_psy", "libelle": "Patients suivis pour maladie psychiatrique",
     "unite": "pour 10 000 hab.", "agregation": "somme", "pour_10000_habitants": true,
     "explication": "Nombre de personnes prises en charge par l'Assurance Maladie pour une maladie psychiatrique, rapporté à la population."}
  ]
}
agregation vaut "somme" (effectifs, additionnés en remontant) ou "moyenne" (taux, moyenne
pondérée par la population en remontant).

Version 2, voie légère (note docs/veille/conception_voie_legere.md, validée le 30 octobre 2026). Un descripteur qui
porte « etat » (« brouillon » ou « actif ») suit la liste à cocher du projet pour toute nouvelle base et il est refusé s'il est incomplet
(verifier_descripteur). En plus de la version 1, il nomme sa ligne du registre des bases (« id »), lit un portail
Opendatasoft (« portail », « jeu »), trouve ses colonnes par motifs (« colonnes »), garde la série des années
(« annee », « serie »), lit les valeurs sous le secret statistique comme absentes (« secret »), porte pour chaque
indicateur son domaine, son sens, sa comparabilité, son dénominateur, son incertitude, son agrégation et sa limite
avec ses sources, le paragraphe de la page méthode (« methode »), et peut proposer des indicateurs dérivés
(« derives », rapport de deux indicateurs seulement) et des questions préparées (« questions », sur le modèle de
config.CROISEMENTS). Le niveau « fra » donne un repère national, jamais en carte ni en croisement. Un descripteur
« brouillon » n'est lu que par les tests et par une exécution locale de contrôle (brouillons=True, ou variable
d'environnement OFFRE_SOINS_BROUILLONS=1), jamais pour une version publiée."""
from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd

from .. import config, libelles, licences
from ..util import (JOURNAL, choisir_ressource, detecter_separateur, get_json, lire_meta, log, norm, premiere_ligne,
                    ressources_datagouv, telecharger, trouver_colonne)

# descripteurs versionnés à côté du code (comme le registre), le cache des données suit config.DONNEES
DESCRIPTEURS = Path(__file__).resolve().parents[2] / "complements"
DOSSIER = config.DONNEES / "complements"
# registre des bases, à côté du code (il ne part pas avec le code public, la vérification est alors sautée)
REGISTRE = Path(__file__).resolve().parents[2] / "docs" / "veille" / "registre_bases.csv"
# portails Opendatasoft, adresses déjà vérifiées dans la configuration
PORTAILS = {"odisse": config.ODISSE_API, "drees": config.DREES_API, "caf": config.CAF_API,
            "ameli": config.AMELI_API.rsplit("/", 1)[0] + "/"}
ETATS = ("brouillon", "actif")
NIVEAUX = ("com", "epci", "dep", "reg", "fra")
NOMS_NIVEAUX = {"com": "communes", "epci": "intercommunalités", "dep": "départements", "reg": "régions"}
AGREGATIONS = ("somme", "moyenne", "non_agregeable")
DOMAINES = ("Santé mentale", "Santé", "Social", "Sécurité et victimes", "Cadre de vie")
SENS = ("manque si plus bas", "manque si plus haut", "aucun")
COMPARABILITE = ("comparable", "outre-mer à part", "non comparable")
SOURCE_LIBELLES = "Complément"


def brouillons_demandes() -> bool:
    return os.environ.get("OFFRE_SOINS_BROUILLONS") == "1"


def _recuperer(d, chemin, hors_ligne, rafraichir):
    """Télécharge la base décrite par d, par data.gouv, par un portail ou par adresse. Renvoie l'adresse utilisée."""
    if hors_ligne:
        if not chemin.exists():
            raise FileNotFoundError(f"mode hors ligne et fichier {chemin.name} absent")
        return lire_meta(chemin).get("url", "")
    if d.get("portail"):
        return _recuperer_portail(d, chemin, rafraichir)
    if d.get("datagouv"):
        res = ressources_datagouv(d["datagouv"])
        r = choisir_ressource(res, d.get("ressource", "."), set(d["formats"]) if d.get("formats") else None)
        if r is None:
            raise RuntimeError(f"aucune ressource ne correspond à « {d.get('ressource')} » dans {d['datagouv']}")
        telecharger(r["url"], chemin, "complements", rafraichir, taille_min=100,
                    extra_meta={"titre": r["titre"], "maj_source": r["maj"], "jeu_datagouv": d["datagouv"]})
        return r["url"]
    if d.get("url"):
        telecharger(d["url"], chemin, "complements", rafraichir, taille_min=100)
        return d["url"]
    raise RuntimeError("ni « datagouv » ni « url » dans le descripteur, la base ne serait pas automatisable")


def _clause(champ: str, valeurs) -> str:
    vals = valeurs if isinstance(valeurs, list) else [valeurs]
    parts = [f'{champ}="{str(v).replace(chr(34), chr(92) + chr(34))}"' for v in vals]
    return parts[0] if len(parts) == 1 else "(" + " or ".join(parts) + ")"


def _recuperer_portail(d, chemin, rafraichir):
    """Export CSV d'un jeu Opendatasoft, filtré sur le portail quand le descripteur le demande, avec la date de
    modification du jeu (maj_source)."""
    base = PORTAILS[d["portail"]] + d["jeu"]
    meta = get_json(base)
    maj = ((meta.get("metas") or {}).get("default") or {}).get("modified", "")
    champs = [f["name"] for f in meta.get("fields", [])]
    where = " and ".join(_clause(_colonne(champs, motif, motif), v) for motif, v in (d.get("filtre") or {}).items())
    url = base + "/exports/csv?delimiter=%3B" + ("&where=" + quote(where) if where else "")
    ancien = lire_meta(chemin).get("maj_source")
    telecharger(url, chemin, "complements", rafraichir or (bool(ancien) and ancien != maj), taille_min=50,
                extra_meta={"maj_source": maj, "jeu": f"{d['portail']}:{d['jeu']}"})
    return url


def _colonne(colonnes, motif, nom=""):
    """Colonne trouvée par son nom exact, puis par motif sur le nom brut, puis par motif sur le nom normalisé
    (util.trouver_colonne), jamais par position."""
    colonnes = list(colonnes)
    motifs = motif if isinstance(motif, list) else [motif]
    for m in motifs:
        if m in colonnes:
            return m
    for m in motifs:
        for c in colonnes:
            if re.search(m, str(c).lower()):
                return c
    return trouver_colonne(colonnes, motifs, nom=nom or motifs[0])


def _normaliser_code(s: pd.Series, niveau: str) -> pd.Series:
    s = s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.upper()
    if niveau == "com":
        return s.str.zfill(5)
    if niveau == "dep":   # « 005 » devient « 05 », « 971 » et « 2A » restent tels quels
        s = s.where(~(s.str.len().eq(3) & s.str.startswith("0")), s.str[1:])
        return s.where(s.str.len() != 1, s.str.zfill(2))
    if niveau == "reg":
        return s.str.zfill(2)
    return s


def _codes_par_nom(s: pd.Series, table: pd.DataFrame) -> pd.Series:
    """Code d'un département ou d'une région retrouvé par son nom (« Ile-de-France » pour « Île-de-France »)."""
    noms = {norm(n): c for c, n in zip(table["code"], table["nom"])}
    return s.map(lambda x: noms.get(norm(x), ""))


# ---------------------------------------------------------------- conditions d'entrée (version 2)
def lire_registre(f: Path | None = None) -> dict | None:
    f = f or REGISTRE
    if not f.exists():
        return None
    with f.open(encoding="utf-8", newline="") as h:
        return {x["id"]: x for x in csv.DictReader(h, delimiter=";")}


def verifier_descripteur(d: dict, registre: dict | None = None) -> list[str]:
    """Ce qui manque à un descripteur de la version 2 pour entrer (liste à cocher du projet pour toute nouvelle base, conditions du
    30 octobre 2026). Une liste vide veut dire qu'il peut entrer."""
    e = []
    if d.get("etat") not in ETATS:
        e.append(f"état {d.get('etat')!r}, attendu parmi {ETATS}")
    for k in ("id", "nom", "source", "licence", "verifie_le", "niveau", "methode"):
        if not str(d.get(k) or "").strip():
            e.append(f"« {k} » manquant")
    if d.get("verifie_le") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d["verifie_le"])):
        e.append("« verifie_le » en AAAA-MM-JJ")
    if len(str(d.get("methode") or "")) < 80:
        e.append("paragraphe « methode » trop court pour la page méthode")
    lic = licences.identifiant(d.get("licence"), d.get("source"))
    if lic is None:
        e.append(f"licence {d.get('licence')!r} absente du registre des licences")
    if d.get("portail"):
        if d["portail"] not in PORTAILS or not d.get("jeu"):
            e.append(f"portail {d.get('portail')!r} inconnu ou « jeu » manquant")
    elif not (d.get("datagouv") or d.get("url")):
        e.append("ni portail, ni datagouv, ni url")
    if d.get("niveau") not in NIVEAUX:
        e.append(f"niveau {d.get('niveau')!r}")
    if d.get("niveau") != "fra" and not ((d.get("colonnes") or {}).get("code") or d.get("colonne_code")):
        e.append("colonne du code du territoire manquante")
    if not d.get("indicateurs"):
        e.append("aucun indicateur")
    ids = []
    for ind in d.get("indicateurs") or []:
        i = ind.get("id", "?")
        ids.append(i)
        if not re.fullmatch(r"[a-z0-9_]+", str(i)):
            e.append(f"identifiant d'indicateur {i!r}")
        for k in ("colonne", "libelle", "unite", "explication", "groupe"):
            if not str(ind.get(k) or "").strip():
                e.append(f"{i}, « {k} » manquant")
        for k, permis in (("agregation", AGREGATIONS), ("domaine", DOMAINES), ("sens", SENS),
                          ("comparabilite", COMPARABILITE)):
            if ind.get(k) not in permis:
                e.append(f"{i}, {k} {ind.get(k)!r}, attendu parmi {permis}")
        if not str(ind.get("denominateur") or "").strip():
            e.append(f"{i}, dénominateur manquant (« aucun » pour un effectif)")
        lim = ind.get("limite") or {}
        if not (lim.get("texte") and lim.get("court") and lim.get("risque")):
            e.append(f"{i}, limite incomplète (risque, court, texte)")
        srcs = lim.get("sources") or []
        if not srcs or not all(s.get("titre") and str(s.get("url", "")).startswith("https://") and s.get("date")
                               for s in srcs):
            e.append(f"{i}, chaque limite cite au moins une source datée avec son adresse")
        for texte in (ind.get("libelle"), ind.get("explication"), lim.get("court"), lim.get("texte")):
            for t in libelles.termes_proscrits(texte or ""):
                e.append(f"{i}, terme à proscrire ({t})")
        relu = next((r for r in libelles.table() if r["source"] == SOURCE_LIBELLES and r["code"] == i), None)
        if relu is None:
            e.append(f"{i}, libellé absent de pipeline/libelles.csv (source « {SOURCE_LIBELLES} »)")
        elif d.get("etat") == "actif" and relu["statut"] != "validé":
            e.append(f"{i}, libellé pas encore validé, la base ne peut pas passer à « actif »")
    for x in d.get("derives") or []:
        i = x.get("id", "?")
        if x.get("operation") != "rapport":
            e.append(f"dérivé {i}, seul le rapport de deux indicateurs est permis (jamais de somme de professions)")
        for k in ("numerateur", "denominateur", "libelle", "unite", "explication"):
            if not str(x.get(k) or "").strip():
                e.append(f"dérivé {i}, « {k} » manquant")
        if x.get("numerateur") == x.get("denominateur"):
            e.append(f"dérivé {i}, numérateur et dénominateur identiques")
        if any(str(x.get(k, "")).startswith(("dens", "n_")) for k in ("numerateur", "denominateur")):
            e.append(f"dérivé {i}, pas de rapport sur des effectifs de professions dans un descripteur")
    themes = [q.get("theme") for q in d.get("questions") or []]
    if len(themes) != len(set(themes)):
        e.append("deux questions préparées partagent un thème, chaque question a le sien (son texte est lu par thème)")
    for q in d.get("questions") or []:
        if not all(str(q.get(k) or "").strip() for k in ("x", "y", "theme", "question")):
            e.append(f"question préparée incomplète {q}")
        if d.get("niveau") == "fra":
            e.append("un repère national n'entre dans aucune question")
    if registre is not None:
        x = registre.get(d.get("id"))
        if x is None:
            e.append(f"ligne {d.get('id')!r} absente du registre des bases")
        else:
            if x["statut"] not in ("à intégrer", "intégrée"):
                e.append(f"ligne du registre au statut « {x['statut']} », la base n'a pas été tranchée")
            if "lot" not in x["sources"].lower():
                e.append("la ligne du registre ne cite pas le lot qui a tranché la base")
            if licences.identifiant(x["licence"], d.get("source")) != lic:
                e.append(f"licence différente de celle du registre ({x['licence']})")
    return e


# ---------------------------------------------------------------- chargement
def charger(ref, ctx: dict | None, hors_ligne=False, rafraichir=False, descripteurs=None, brouillons=None,
            extras: dict | None = None):
    """Renvoie (ctx enrichi, liste des définitions d'indicateurs ajoutés). Avec « extras » (dictionnaire), y range
    les séries, les repères nationaux, les dérivés et les questions préparées des descripteurs de la version 2, et
    les descripteurs refusés avec leur raison."""
    ctx = {k: v.copy() for k, v in (ctx or {}).items()}
    for niv, base in {"com": ref.communes, "epci": ref.epci, "dep": ref.deps, "reg": ref.regs}.items():
        ctx.setdefault(niv, pd.DataFrame(index=base["code"]))
    defs = []
    extras = extras if extras is not None else {}
    for k in ("series", "reperes", "derives", "questions", "refuses"):
        extras.setdefault(k, [])
    descripteurs = descripteurs or DESCRIPTEURS
    brouillons = brouillons_demandes() if brouillons is None else brouillons
    if not descripteurs.exists():
        return ctx, defs
    pops = {"com": ref.communes.set_index("code")["pop"], "epci": ref.epci.set_index("code")["pop"],
            "dep": ref.deps.set_index("code")["pop"], "reg": ref.regs.set_index("code")["pop"]}
    registre = None
    for desc_path in sorted(descripteurs.glob("*.json")):
        try:
            d = json.loads(desc_path.read_text(encoding="utf-8"))
            if "etat" in d:
                if d["etat"] == "brouillon" and not brouillons:
                    log.info("complément %s en brouillon, non lu", desc_path.name)
                    continue
                registre = registre if registre is not None else (lire_registre() or {})
                erreurs = verifier_descripteur(d, registre if REGISTRE.exists() else None)
                if desc_path.stem != d.get("id"):
                    erreurs.append(f"fichier {desc_path.name} et identifiant {d.get('id')!r} différents")
                if erreurs:
                    extras["refuses"].append({"descripteur": desc_path.name, "erreurs": erreurs})
                    JOURNAL.note(f"Complément, {d.get('nom', desc_path.stem)}", "erreur",
                                 "refusé, " + " ; ".join(erreurs)[:280])
                    continue
                d2, nouveaux = _charger_v2(d, ref, ctx, pops, hors_ligne, rafraichir, extras)
                defs += nouveaux
                continue
            if d.get("actif") is False:
                continue
            chemin = (descripteurs if d.get("local") else DOSSIER) / d["fichier"]
            if not d.get("local"):   # « local » ne sert qu'aux tests unitaires
                d["url"] = _recuperer(d, chemin, hors_ligne, rafraichir) or d.get("url", "")
            enc = d.get("encodage", "utf-8-sig")
            sep = d.get("separateur") or detecter_separateur(premiere_ligne(chemin, enc))
            df = pd.read_csv(chemin, sep=sep, dtype=str, encoding=enc, encoding_errors="replace", keep_default_na=False)
            for col, valeur in (d.get("filtre") or {}).items():
                valeurs = valeur if isinstance(valeur, list) else [valeur]
                df = df[df[col].isin([str(v) for v in valeurs])]
            niv = d["niveau"]
            df["_code"] = _normaliser_code(df[d["colonne_code"]], niv)
            if niv == "com":
                actuels = set(ref.communes["code"])
                df["_code"] = df["_code"].where(df["_code"].isin(actuels), df["_code"].map(ref.anciens))
            df = df[df["_code"].notna() & (df["_code"] != "")]
            for ind in d["indicateurs"]:
                v = pd.to_numeric(df[ind["colonne"]].str.replace(",", ".").str.replace(" ", ""), errors="coerce")
                s = v.groupby(df["_code"]).sum(min_count=1) if ind.get("agregation", "somme") == "somme" \
                    else v.groupby(df["_code"]).mean()
                niveaux = _niveaux(s, niv, ind.get("agregation", "somme"), ref, pops)
                for n2, serie in niveaux.items():
                    if ind.get("pour_10000_habitants"):
                        serie = serie / pops[n2].reindex(serie.index) * 1e4
                    ctx[n2][ind["id"]] = serie.reindex(ctx[n2].index)
                defs.append({"id": ind["id"], "libelle": ind["libelle"], "unite": ind.get("unite", ""),
                             "explication": ind.get("explication", ""), "source": d.get("source", d.get("nom", "")),
                             "famille": ind.get("famille", d.get("famille", "")), "licence": d.get("licence", ""),
                             "niveau_origine": niv})
            JOURNAL.note(f"Complément, {d.get('nom', desc_path.stem)}", "ok",
                         f"{len(df)} lignes, {len(d['indicateurs'])} indicateur(s) au niveau {niv}",
                         url=d.get("url", ""), lignes=len(df))
        except Exception as e:  # noqa: BLE001
            JOURNAL.note(f"Complément, {desc_path.stem}", "erreur", str(e)[:300])
            log.exception("complément %s", desc_path.name)
    return ctx, defs


def _niveaux(s: pd.Series, niv: str, agregation: str, ref, pops) -> dict:
    """Valeurs au niveau d'origine et remontées aux niveaux supérieurs (somme, ou moyenne pondérée par la
    population). Un indicateur non agrégeable reste à son niveau."""
    niveaux = {niv: s}
    if agregation == "non_agregeable":
        return niveaux
    if niv == "com":
        rat = ref.communes.set_index("code")[["epci", "dep", "reg"]]
        t = pd.DataFrame({"v": s}).join(rat, how="inner")
        t["pop"] = t.index.map(pops["com"])
        for sup in ["epci", "dep", "reg"]:
            niveaux[sup] = _remonter(t, sup, agregation)
    elif niv == "dep":
        t = pd.DataFrame({"v": s}).join(ref.deps.set_index("code")[["reg", "pop"]], how="inner")
        niveaux["reg"] = _remonter(t, "reg", agregation)
    return niveaux


def _incomplets(s: pd.Series, niv: str, sup: str, ref) -> set:
    """Territoires du niveau sup dont au moins un territoire du niveau niv n'a pas de valeur (secret, absent)."""
    table = ref.communes if niv == "com" else ref.deps
    rat = table.set_index("code")[sup]
    manque = rat[~rat.index.isin(s.dropna().index)]
    return set(manque.dropna())


def _charger_v2(d, ref, ctx, pops, hors_ligne, rafraichir, extras):
    """Lecture d'un descripteur de la version 2 déjà vérifié. Renvoie (d, définitions)."""
    chemin = DOSSIER / (d.get("fichier") or f"{d['id']}.csv")
    url = _recuperer(d, chemin, hors_ligne, rafraichir) or d.get("url", "")
    meta = lire_meta(chemin)
    enc = d.get("encodage", "utf-8-sig")
    sep = d.get("separateur") or detecter_separateur(premiere_ligne(chemin, enc))
    df = pd.read_csv(chemin, sep=sep, dtype=str, encoding=enc, encoding_errors="replace", keep_default_na=False)
    lignes_lues = len(df)
    for motif, valeur in (d.get("filtre") or {}).items():
        valeurs = valeur if isinstance(valeur, list) else [valeur]
        df = df[df[_colonne(df.columns, motif, motif)].isin([str(v) for v in valeurs])]
    cols = d.get("colonnes") or {}
    niv = d["niveau"]
    df["_annee"] = df[_colonne(df.columns, cols["annee"], "année")].str[:4] if cols.get("annee") else ""
    connus = {"com": ref.communes, "epci": ref.epci, "dep": ref.deps, "reg": ref.regs}
    hors_referentiel = 0
    if niv != "fra":
        brut = df[_colonne(df.columns, cols.get("code") or d.get("colonne_code"), "code du territoire")]
        df["_code"] = (_codes_par_nom(brut, connus[niv]) if d.get("code_par_nom") else _normaliser_code(brut, niv))
        if niv == "com":
            actuels = set(ref.communes["code"])
            df["_code"] = df["_code"].where(df["_code"].isin(actuels), df["_code"].map(ref.anciens))
        garde = df["_code"].isin(set(connus[niv]["code"]))
        hors_referentiel = int((~garde).sum())
        df = df[garde]
    else:
        df["_code"] = "FR"
    secret = {str(x) for x in d.get("secret") or []}
    defs = []
    for ind in d["indicateurs"]:
        brut = df[_colonne(df.columns, ind["colonne"], ind["id"])].astype(str).str.strip()
        v = pd.to_numeric(brut.where(~brut.isin(secret)).str.replace(",", ".").str.replace(" ", ""), errors="coerce")
        x = pd.DataFrame({"code": df["_code"], "annee": df["_annee"], "v": v,
                          "marque": brut.where(brut.isin(secret), "")})
        if d.get("serie") and cols.get("annee"):
            s_ = x.dropna(subset=["v"]).groupby(["code", "annee"])["v"].first().reset_index()
            extras["series"].append(s_.assign(niveau=niv, indicateur=ind["id"])
                                    .rename(columns={"v": "valeur"})[["niveau", "code", "indicateur", "annee", "valeur"]])
        annee = d.get("annee", "derniere")
        if cols.get("annee"):
            annee = x.dropna(subset=["v"])["annee"].max() if annee == "derniere" else str(annee)
            x = x[x["annee"] == annee]
        agr = ind["agregation"]
        if agr == "non_agregeable" and x["code"].duplicated().any():
            raise ValueError(f"{ind['id']}, plusieurs lignes par territoire pour un indicateur non agrégeable")
        s = (x.groupby("code")["v"].sum(min_count=1) if agr == "somme" else x.groupby("code")["v"].mean())
        # territoires sous le secret statistique, valeur vide et raison écrite (champ non_publies du catalogue)
        marques = x[x["marque"] != ""].groupby("code")["marque"].first()
        marques = marques[s.reindex(marques.index).isna()]
        n_secret = len(marques)
        non_publies = {niv: {c: f"non publié par le producteur, secret statistique (« {m} »)"
                             for c, m in marques.items()}} if n_secret else {}
        limite = ind["limite"]
        definition = {"id": ind["id"], "libelle": ind["libelle"], "unite": ind["unite"],
                      "explication": ind["explication"] + (f" Année {annee}." if annee else ""),
                      "source": d["source"], "famille": ind.get("famille", d.get("famille", "")),
                      "licence": d["licence"], "groupe": ind["groupe"], "niveau_origine": niv, "annee": annee,
                      "domaine": ind["domaine"], "sens": ind["sens"], "comparabilite": ind["comparabilite"],
                      "denominateur": ind["denominateur"], "incertitude": ind.get("incertitude") or {},
                      "agregation_explicite": agr, "limite": limite, "page_source": d.get("adresse", ""),
                      "registre": d["id"], "etat": d["etat"], "methode": d["methode"],
                      "date_source": (meta.get("maj_source") or "")[:10], "url": url}
        if niv == "fra":
            valeur = s.get("FR", np.nan)
            extras["reperes"].append(definition | {"valeur": None if pd.isna(valeur) else float(valeur)})
            JOURNAL.controle(f"Complément, {ind['libelle']}, repère national", f"{valeur} ({annee})")
            continue
        for n2, serie in _niveaux(s, niv, agr, ref, pops).items():
            if n2 != niv:   # un territoire dont une partie manque n'a pas de valeur, jamais une somme incomplète
                incomplets = _incomplets(s, niv, n2, ref)
                serie = serie.where(~serie.index.isin(incomplets))
                if incomplets:
                    non_publies[n2] = {c: "non calculé, au moins un territoire qui le compose est sans valeur"
                                       for c in sorted(incomplets)}
            if ind.get("pour_10000_habitants"):
                serie = serie / pops[n2].reindex(serie.index) * 1e4
            ctx[n2][ind["id"]] = serie.reindex(ctx[n2].index)
        if non_publies:
            definition["non_publies"] = non_publies
        defs.append(definition)
        _controler(d, ind, s, niv, connus, n_secret, annee)
    for x in d.get("derives") or []:
        extras["derives"].append(x | {"source": d["source"], "licence": d["licence"], "registre": d["id"], "etat": d["etat"],
                                      "famille": x.get("famille") or d["indicateurs"][0].get("famille", ""),
                                      "domaine": x.get("domaine") or d["indicateurs"][0]["domaine"],
                                      "groupe": x.get("groupe") or d["indicateurs"][0]["groupe"]})
    for q in d.get("questions") or []:
        extras["questions"].append((q["x"], q["y"], q["theme"], q["question"]))
    JOURNAL.note(f"Complément, {d['nom']}", "ok",
                 f"{lignes_lues} lignes lues, {len(df)} gardées, {hors_referentiel} hors du référentiel, "
                 f"{len(d['indicateurs'])} indicateur(s) au niveau {niv}" + (", brouillon" if d["etat"] == "brouillon" else ""),
                 url=str(url)[:200], date_donnees=(meta.get("maj_source") or "")[:10], lignes=lignes_lues)
    return d, defs


def _controler(d, ind, s: pd.Series, niv: str, connus: dict, n_secret: int, annee: str) -> None:
    """Contrôle écrit dans JOURNAL.controle, couverture du niveau, valeurs sous le secret, valeurs hors des bornes, et
    écart au repère publié quand le descripteur en cite un."""
    c = d.get("controle") or {}
    attendus = len(connus[niv])
    n = int(s.notna().sum())
    bornes = ind.get("bornes") or c.get("bornes")
    hors = int(((s < bornes[0]) | (s > bornes[1])).sum()) if bornes else 0
    texte = (f"{n} {NOMS_NIVEAUX[niv]} sur {attendus} ({n / attendus:.0%}), {n_secret} valeur(s) sous le secret, "
             f"{hors} hors des bornes, année {annee or 'unique'}")
    JOURNAL.controle(f"Complément, {ind['libelle']}", texte)
    if n / attendus < c.get("couverture_min", 0.9) or hors:
        JOURNAL.note(f"Complément, {ind['libelle']}", "attention", texte)
    rep = c.get("repere") or {}
    if rep.get("valeur") is not None:
        calc = float(s.sum()) if ind["agregation"] == "somme" else float(s.mean())
        ecart = abs(calc - rep["valeur"]) / abs(rep["valeur"]) if rep["valeur"] else float("inf")
        JOURNAL.controle(f"Complément, {ind['libelle']}, repère publié",
                         f"{calc:.4g} calculé contre {rep['valeur']} publié ({rep.get('source', '')}), écart {ecart:.1%}")
        if ecart > rep.get("tolerance", 0.02):
            JOURNAL.note(f"Complément, {ind['libelle']}", "attention", f"écart de {ecart:.1%} au repère publié")


def deriver(ctx: dict, derives: list[dict], defs: list[dict]) -> list[dict]:
    """Indicateurs dérivés des descripteurs, rapport de deux indicateurs du catalogue au même niveau, calculés une fois
    toutes les sources réunies. Un dérivé dont un terme manque est noté et sauté. Renvoie les définitions ajoutées,
    chacune avec les sources et les limites de ses deux termes."""
    par_id = {x["id"]: x for x in defs}
    ajoutes = []
    for x in derives:
        if x.get("operation") != "rapport":
            JOURNAL.note(f"Complément, dérivé {x.get('id')}", "erreur", "seul le rapport est permis")
            continue
        annees = {str(par_id.get(k, {}).get("annee") or "") for k in (x["numerateur"], x["denominateur"])} - {""}
        if len(annees) > 1:
            JOURNAL.note(f"Complément, dérivé {x['id']}", "erreur",
                         f"années différentes ({', '.join(sorted(annees))}), rapport non calculé")
            continue
        niveaux = []
        for niv, t in ctx.items():
            if not isinstance(t, pd.DataFrame) or x["numerateur"] not in t or x["denominateur"] not in t:
                continue
            den = t[x["denominateur"]].where(t[x["denominateur"]] != 0)
            t[x["id"]] = t[x["numerateur"]] / den * float(x.get("facteur", 1))
            niveaux.append(niv)
        if not niveaux:
            JOURNAL.note(f"Complément, dérivé {x['id']}", "erreur",
                         f"{x['numerateur']} ou {x['denominateur']} absent du contexte")
            continue
        termes = [par_id.get(x["numerateur"], {}), par_id.get(x["denominateur"], {})]
        sources = list(dict.fromkeys(s for s in (t.get("source") for t in termes) if s)) or [x["source"]]
        ajoutes.append({"id": x["id"], "libelle": x["libelle"], "unite": x["unite"], "explication": x["explication"],
                        "source": " ; ".join(sources), "famille": x.get("famille", ""), "licence": x["licence"],
                        "groupe": x["groupe"], "domaine": x["domaine"], "sens": x.get("sens", "aucun"),
                        "comparabilite": x.get("comparabilite", "comparable"), "agregation_explicite": "non_agregeable",
                        "denominateur": x["denominateur"], "derive_de": [x["numerateur"], x["denominateur"]],
                        "limites_heritees": [x["numerateur"], x["denominateur"]], "registre": x["registre"],
                        "etat": x.get("etat", ""),
                        "annee": next(iter(annees), ""),
                        "niveau_origine": niveaux[0]})
        JOURNAL.controle(f"Complément, {x['libelle']}",
                         ", ".join(f"{int(ctx[n][x['id']].notna().sum())} {NOMS_NIVEAUX.get(n, n)}" for n in niveaux))
    return ajoutes


def limites(defs: list[dict]) -> tuple[dict, dict]:
    """Limites des indicateurs des descripteurs, au format de config.LIMITES (pour limites.completer) et des lignes
    courtes de config.LIMITES_COURT. Un dérivé reprend les limites de ses deux termes."""
    longues, courtes = {}, {}
    for d in defs:
        L = d.get("limite")
        if not L:
            continue
        longues[d["id"]] = {"risque": L["risque"], "texte": L["texte"], "nom": d["libelle"],
                            "sources": [(s["titre"] + (f" ({s['date']})" if s.get("date") else ""), s["url"])
                                        for s in L["sources"]]}
        courtes[d["id"]] = L["court"]
    for d in defs:
        termes = [t for t in d.get("limites_heritees") or [] if t in longues or t in config.LIMITES]
        if not termes:
            continue
        sources = [config.LIMITES.get(t, longues.get(t)) for t in termes]
        longues[d["id"]] = {"risque": sources[0]["risque"], "nom": d["libelle"],
                            "texte": " ".join(dict.fromkeys(s["texte"] for s in sources)),
                            "sources": list(dict.fromkeys(tuple(x) for s in sources for x in s["sources"]))}
        courtes[d["id"]] = " ".join(dict.fromkeys(c for c in (courtes.get(t) or config.LIMITES_COURT.get(t, "")
                                                               for t in termes) if c))
    return longues, courtes


def _remonter(t: pd.DataFrame, niveau: str, agregation: str) -> pd.Series:
    if agregation == "somme":
        return t.groupby(niveau)["v"].sum(min_count=1)
    u = t.dropna(subset=["v"])
    return (u["v"] * u["pop"]).groupby(u[niveau]).sum() / u["pop"].groupby(u[niveau]).sum().replace(0, np.nan)
