"""Bases complémentaires. Chaque base est décrite par un fichier JSON versionné dans complements/
(à la racine du projet). Le programme la télécharge, la lit, l'agrège aux niveaux supérieurs et
l'ajoute aux indicateurs de contexte. Elle entre alors automatiquement dans tous les croisements,
le rapport et l'atlas. Les fichiers téléchargés sont rangés dans donnees/complements/.

Tout doit être automatisable (tâche planifiée sur serveur). Une base est donc résolue soit par
data.gouv (« datagouv », slug ou identifiant du jeu, et « ressource », motif sur le titre ou le nom
du fichier), soit par une adresse stable (« url »). Un fichier sans l'un ni l'autre est refusé.

Exemple de descripteur
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
pondérée par la population en remontant)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import config
from ..util import (JOURNAL, choisir_ressource, detecter_separateur, log, premiere_ligne, ressources_datagouv,
                    telecharger)

DESCRIPTEURS = config.RACINE / "complements"
DOSSIER = config.DONNEES / "complements"


def _recuperer(d, chemin, hors_ligne, rafraichir):
    """Télécharge la base décrite par d, par data.gouv ou par adresse. Renvoie l'adresse utilisée."""
    if hors_ligne:
        if not chemin.exists():
            raise FileNotFoundError(f"mode hors ligne et fichier {chemin.name} absent")
        return ""
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


def _normaliser_code(s: pd.Series, niveau: str) -> pd.Series:
    s = s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.upper()
    if niveau == "com":
        return s.str.zfill(5)
    if niveau == "dep":
        return s.where(s.str.len() != 1, s.str.zfill(2))
    if niveau == "reg":
        return s.str.zfill(2)
    return s


def charger(ref, ctx: dict | None, hors_ligne=False, rafraichir=False, descripteurs=None):
    """Renvoie (ctx enrichi, liste des définitions d'indicateurs ajoutés)."""
    ctx = {k: v.copy() for k, v in (ctx or {}).items()}
    for niv, base in {"com": ref.communes, "epci": ref.epci, "dep": ref.deps, "reg": ref.regs}.items():
        ctx.setdefault(niv, pd.DataFrame(index=base["code"]))
    defs = []
    descripteurs = descripteurs or DESCRIPTEURS
    if not descripteurs.exists():
        return ctx, defs
    pops = {"com": ref.communes.set_index("code")["pop"], "epci": ref.epci.set_index("code")["pop"],
            "dep": ref.deps.set_index("code")["pop"], "reg": ref.regs.set_index("code")["pop"]}
    for desc_path in sorted(descripteurs.glob("*.json")):
        try:
            d = json.loads(desc_path.read_text(encoding="utf-8"))
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
                niveaux = {niv: s}
                if niv == "com":
                    rat = ref.communes.set_index("code")[["epci", "dep", "reg"]]
                    t = pd.DataFrame({"v": s}).join(rat, how="inner")
                    t["pop"] = t.index.map(pops["com"])
                    for sup in ["epci", "dep", "reg"]:
                        niveaux[sup] = _remonter(t, sup, ind.get("agregation", "somme"))
                elif niv == "dep":
                    t = pd.DataFrame({"v": s}).join(ref.deps.set_index("code")[["reg", "pop"]], how="inner")
                    niveaux["reg"] = _remonter(t, "reg", ind.get("agregation", "somme"))
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


def _remonter(t: pd.DataFrame, niveau: str, agregation: str) -> pd.Series:
    if agregation == "somme":
        return t.groupby(niveau)["v"].sum(min_count=1)
    u = t.dropna(subset=["v"])
    return (u["v"] * u["pop"]).groupby(u[niveau]).sum() / u["pop"].groupby(u[niveau]).sum().replace(0, np.nan)
