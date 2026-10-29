"""Réutilisation « Ubi Cura » sur data.gouv.fr, reliée à chaque jeu de données utilisé (feuille de route de la
communication, phase 1, accord de Lucas du 29 octobre 2026, déclaration par l'API demandée le même jour).

Les jeux sont tirés du code lui-même (identifiants passés à util.ressources_datagouv et adresses data.gouv.fr citées
dans pipeline/config.py), puis lus sur l'API de data.gouv pour leur identifiant, leur titre et leur producteur.
La réutilisation est créée **privée** (invisible du public) avec la clé d'API de Lucas, rangée dans le gestionnaire
d'identifiants de Windows et jamais affichée. C'est Lucas qui la rend publique, d'un clic sur data.gouv.fr (tutoriel 12).
Champs et adresses d'après la description de l'API, https://www.data.gouv.fr/api/1/swagger.json (lue le 29 octobre
2026), clé dans l'en-tête X-API-KEY, champs obligatoires title, description, topic, type, url.

    python outils/jeux_datagouv.py                 écrit docs/referencement/jeux_datagouv.csv
    python outils/jeux_datagouv.py cle             saisit la clé d'API, la teste et la range dans Windows
    python outils/jeux_datagouv.py reutilisation   crée la réutilisation privée, ou ajoute à la réutilisation
                                                   existante les jeux qui lui manquent, et dépose l'image d'aperçu
    python outils/jeux_datagouv.py verifier        dit si la réutilisation existe, si elle est publique et
                                                   quels jeux lui manquent
"""
from __future__ import annotations

import argparse
import csv
import getpass
import json
import re
import sys
from pathlib import Path

import requests

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
from pipeline import config  # noqa: E402
from pipeline.util import get_json  # noqa: E402
from outils import identifiants as coffre  # noqa: E402

SORTIE = RACINE / "docs" / "referencement" / "jeux_datagouv.csv"
API = "https://www.data.gouv.fr/api/1"
CIBLE_CLE = "Ubi Cura, data.gouv.fr"      # nom de la clé dans le gestionnaire d'identifiants de Windows
ETAT = config.DONNEES / "datagouv.json"   # identifiant de la réutilisation créée, jamais publié
IMAGE = RACINE / "site" / "apercu.png"

# texte de la réutilisation, ton neutre et titre qui décrit l'usage des données (guide de data.gouv.fr, « Publier une
# réutilisation », lu le 29 octobre 2026), relu par Lucas avant qu'il la rende publique
REUTILISATION = {
    "title": "Atlas de l'offre de soins et de santé mentale en France, par territoire",
    "url": config.ADRESSE_SITE.rstrip("/") + "/",
    "type": "visualization",
    "topic": "health",
    "tags": ["offre-de-soins", "sante-mentale", "demographie-medicale", "professionnels-de-sante",
             "geographie-de-la-sante", "structures-de-soins", "rpps", "finess"],
    "description": (
        "Carte et rapports de l'offre de soins en France, par région, département, intercommunalité et commune. Les "
        "effectifs et densités des professionnels de santé et de santé mentale proviennent du répertoire RPPS, les "
        "structures de soins de FINESS et du Répertoire opérationnel des ressources, confirmées par les évaluations de "
        "la HAS, la base Sirene et la statistique annuelle des établissements de santé. Le profil des habitants vient "
        "de l'INSEE, de la DREES, de l'Assurance Maladie, de Santé publique France et de la CAF.\n\n"
        "Chaque chiffre renvoie à sa source et à sa date, les limites connues des données sont signalées là où elles "
        "sont montrées, et les effectifs sont comparés à chaque version aux séries publiées par la DREES. Les données "
        f"agrégées sont téléchargeables en CSV et archivées sur Zenodo (https://doi.org/{config.DOI_DONNEES}).\n\n"
        "Projet de recherche personnel, sans affiliation, code ouvert sous licence EUPL 1.2."),
}


class Arret(Exception):
    """Arrêt propre, avec un message pour Lucas."""


# ---------------------------------------------------------------- jeux utilisés
def jeux_cites() -> list[tuple[str, str]]:
    """(identifiant ou slug, d'où il vient dans le code), sans doublon."""
    vus, out = set(), []

    def ajouter(ident, origine):
        if ident and ident not in vus:
            vus.add(ident)
            out.append((ident, origine))

    for nom in ("RPPS_DATASET", "FINESS_NOUVEAU", "FINESS_HISTORIQUE", "ACCES_ROUTE_DATAGOUV", "ALD_DATAGOUV",
                "SIRENE_JEU", "HAS_ESSMS_JEU", "ROR_JEU"):
        ajouter(getattr(config, nom, None), f"config.{nom}")
    for slug, *_ in getattr(config, "HAS_CERTIFICATION", []):
        ajouter(slug, "config.HAS_CERTIFICATION")

    # adresses data.gouv.fr citées dans les valeurs de config (pages des sources, fiches), lues sur les valeurs et non sur
    # le texte du fichier, où une adresse longue est coupée en deux chaînes
    def chaines(v):
        if isinstance(v, str):
            yield v
        elif isinstance(v, dict):
            for x in v.values():
                yield from chaines(x)
        elif isinstance(v, (list, tuple, set)):
            for x in v:
                yield from chaines(x)

    for nom, v in vars(config).items():
        if nom.startswith("_"):
            continue
        for s in chaines(v):
            for m in re.finditer(r"data\.gouv\.fr/(?:fr/)?datasets/([A-Za-z0-9-]+)", s):
                ajouter(m.group(1), f"config.{nom}")
    return out


def lire_jeu(ident: str) -> dict | None:
    try:
        d = get_json(config.DATAGOUV_API.format(ident))
    except Exception as e:  # noqa: BLE001
        print(f"  {ident} introuvable sur l'API ({e})", file=sys.stderr)
        return None
    org = (d.get("organization") or {}).get("name") or (d.get("owner") or {}).get("last_name") or ""
    return {"id": d.get("id", ""), "slug": d.get("slug", ""), "titre": d.get("title", ""), "producteur": org,
            "licence": d.get("license", ""), "page": d.get("page", ""), "archive": d.get("archived") or ""}


def jeux() -> list[dict]:
    lignes, ids = [], set()
    for ident, origine in jeux_cites():
        j = lire_jeu(ident)
        if j is None or j["id"] in ids:
            continue
        ids.add(j["id"])
        lignes.append(dict(j, origine=origine))
    return lignes


def cmd_liste(_args) -> int:
    lignes = jeux()
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    with open(SORTIE, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "slug", "titre", "producteur", "licence", "page", "archive", "origine"],
                           delimiter=";")
        w.writeheader()
        w.writerows(lignes)
    print(f"{len(lignes)} jeux écrits dans {SORTIE.relative_to(RACINE)}")
    return 0


# ---------------------------------------------------------------- API de data.gouv, avec la clé de Lucas
class DataGouv:
    def __init__(self, cle: str):
        self.s = requests.Session()
        self.s.headers["X-API-KEY"] = cle

    def appel(self, methode: str, chemin: str, attendu=(200, 201, 204), **kw) -> requests.Response:
        try:
            r = self.s.request(methode, API + chemin, timeout=60, **kw)
        except requests.RequestException as e:
            raise Arret(f"data.gouv.fr ne répond pas ({e.__class__.__name__}). Réessayer plus tard.") from e
        if r.status_code in (401, 403):
            raise Arret("data.gouv.fr refuse la clé d'API (code %d). En créer une nouvelle sur ton profil (tutoriel 12, "
                        "partie B) puis lancer python outils\\jeux_datagouv.py cle." % r.status_code)
        if r.status_code not in attendu:
            raise Arret(f"réponse inattendue de data.gouv.fr à {methode} {chemin} (code {r.status_code}), {r.text[:400]}")
        return r

    def moi(self) -> dict:
        return self.appel("GET", "/me/").json()


def client() -> DataGouv:
    cle = coffre.lire(CIBLE_CLE)
    if not cle:
        raise Arret("aucune clé d'API data.gouv.fr dans le gestionnaire d'identifiants de Windows. Suivre le tutoriel 12, "
                    "partie B.")
    return DataGouv(cle)


def lire_etat() -> dict:
    return json.loads(ETAT.read_text(encoding="utf-8")) if ETAT.exists() else {}


def cmd_cle(_args) -> int:
    print("Colle la clé d'API créée sur data.gouv.fr, puis appuie sur Entrée. Rien ne s'affiche pendant la saisie, "
          "c'est normal.")
    cle = getpass.getpass("Clé d'API data.gouv.fr : ").strip()
    if len(cle) < 20:
        raise Arret("la clé saisie est trop courte. Recommencer en collant la clé entière (clic droit dans la fenêtre "
                    "PowerShell pour coller).")
    moi = DataGouv(cle).moi()   # teste la clé avant de la ranger
    erreur = coffre.ecrire(CIBLE_CLE, cle, "data.gouv.fr", "Clé d'API de data.gouv.fr, tutoriel 12")
    if erreur:
        raise Arret(f"la clé n'a pas pu être rangée dans le gestionnaire d'identifiants (erreur Windows {erreur})")
    print(f"Clé acceptée par data.gouv.fr (compte de {moi.get('first_name', '')} {moi.get('last_name', '')}) et rangée "
          f"dans le gestionnaire d'identifiants de Windows, sous « {CIBLE_CLE} ».")
    return 0


def _manquants(dg: DataGouv, rid: str, attendus: list[dict]) -> tuple[dict, list[dict]]:
    r = dg.appel("GET", f"/reuses/{rid}/").json()
    presents = {(d.get("id") if isinstance(d, dict) else d) for d in r.get("datasets") or []}
    return r, [j for j in attendus if j["id"] not in presents]


def cmd_reutilisation(_args) -> int:
    dg, attendus, etat = client(), jeux(), lire_etat()
    if not etat.get("id"):
        corps = dict(REUTILISATION, private=True, datasets=[{"id": j["id"], "class": "Dataset"} for j in attendus])
        r = dg.appel("POST", "/reuses/", json=corps).json()
        etat = {"id": r["id"], "page": r.get("page", ""), "cree_le": r.get("created_at", "")}
        ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Réutilisation créée, privée, avec {len(attendus)} jeux de données.")
    else:
        _, manque = _manquants(dg, etat["id"], attendus)
        for j in manque:
            dg.appel("POST", f"/reuses/{etat['id']}/datasets/", json={"id": j["id"], "class": "Dataset"})
        print(f"Réutilisation existante, {len(manque)} jeu(x) ajouté(s)." if manque else
              "Réutilisation existante, aucun jeu ne manque.")
    if IMAGE.exists() and not etat.get("image"):
        with open(IMAGE, "rb") as fh:
            dg.appel("POST", f"/reuses/{etat['id']}/image/", files={"file": (IMAGE.name, fh, "image/png")})
        etat["image"] = IMAGE.name
        ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Image d'aperçu déposée.")
    print(f"Page de la réutilisation : {etat.get('page')}. Elle reste privée tant que tu ne l'as pas rendue publique "
          "sur data.gouv.fr (tutoriel 12, partie D).")
    return 0


def cmd_verifier(_args) -> int:
    etat = lire_etat()
    if not etat.get("id"):
        print("Aucune réutilisation créée pour l'instant (lancer la commande reutilisation).")
        return 0
    r, manque = _manquants(client(), etat["id"], jeux())
    print(f"Réutilisation « {r.get('title')} », {'privée' if r.get('private') else 'publique'}, "
          f"{len(r.get('datasets') or [])} jeux reliés, page {r.get('page')}.")
    for j in manque:
        print(f"  jeu à relier, {j['titre']} ({j['page']})")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("commande", nargs="?", default="liste", choices=["liste", "cle", "reutilisation", "verifier"])
    a = p.parse_args()
    try:
        return {"liste": cmd_liste, "cle": cmd_cle, "reutilisation": cmd_reutilisation,
                "verifier": cmd_verifier}[a.commande](a)
    except Arret as e:
        print(f"Arrêt, {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
