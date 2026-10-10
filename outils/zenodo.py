"""Nouvelles versions des trois dépôts Zenodo (données, rapport santé mentale, rapport santé), par l'API de Zenodo et la
clé d'accès personnelle de Lucas (tutoriel 07).

    python outils\\zenodo.py cle          saisit la clé d'accès, la teste et la range dans le gestionnaire
                                         d'identifiants de Windows (jamais dans un fichier ni dans le dépôt)
    python outils\\zenodo.py verifier     connexion et état des trois dépôts, sans rien modifier
    python outils\\zenodo.py preparer     prépare un brouillon de nouvelle version de chaque dépôt avec les fichiers
                                         de la dernière version (option --version AAAA-MM-JJ), sans le publier
    python outils\\zenodo.py publier      publie les trois brouillons après confirmation (une publication est
                                         définitive)
    python outils\\zenodo.py abandonner   supprime les brouillons préparés, rien n'est publié
    python outils\\zenodo.py constater    lit la dernière version publiée de chaque dépôt et met à jour la version
                                         archivée citée par le site (codes de sortie 0 rien de nouveau, 10 nouvelle
                                         version archivée, 20 vérification impossible)
    python outils\\zenodo.py rappel       rappel trimestriel pour la tâche planifiée (code 10 quand il est temps
                                         d'archiver une version, au plus une fois par semaine)

API dite « héritée » de Zenodo (https://developers.zenodo.org/, relue le 10 octobre 2026), points d'entrée
/api/deposit/depositions, action newversion, envoi des fichiers dans le « bucket » du brouillon, action publish. Zenodo
annonce qu'elle sera remplacée un jour sans date ni point d'entrée de remplacement. Si elle change, le script s'arrête
avec la réponse de Zenodo et rien n'est publié. Droits de la clé, deposit:write et deposit:actions.

Le dossier donnees\\zenodo\\AAAA-MM-JJ\\ garde les fichiers déposés. L'état est dans donnees\\zenodo.json, dont la
version archivée est lue par config.VERSION_ZENODO.
"""
from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import getpass
import hashlib
import json
import sys
import time
from ctypes import wintypes
from pathlib import Path

import requests

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from pipeline import config  # noqa: E402

API = "https://zenodo.org/api"
CIBLE_CLE = "Ubi Cura, Zenodo"            # nom de la clé dans le gestionnaire d'identifiants de Windows
ETAT = config.DONNEES / "zenodo.json"
DOSSIER = config.DONNEES / "zenodo"
DEPOTS = {"donnees": config.DOI_DONNEES, **config.DOI_RAPPORTS}
JOURS_RAPPEL = 91                         # une version archivée par trimestre (choix de Lucas du 10 octobre 2026)
NOMS = {"donnees": "données", "sante-mentale": "rapport santé mentale", "sante": "rapport santé"}


class Arret(Exception):
    """Arrêt propre, avec un message pour Lucas."""


# ---------------------------------------------------------------- gestionnaire d'identifiants de Windows
class _CREDENTIAL(ctypes.Structure):
    _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR), ("LastWritten", wintypes.FILETIME),
                ("CredentialBlobSize", wintypes.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]


_GENERIQUE, _PERSISTANT = 1, 2   # CRED_TYPE_GENERIC, CRED_PERSIST_LOCAL_MACHINE


def lire_cle() -> str | None:
    if sys.platform != "win32":
        return None
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    p = ctypes.POINTER(_CREDENTIAL)()
    if not adv.CredReadW(CIBLE_CLE, _GENERIQUE, 0, ctypes.byref(p)):
        return None
    try:
        brut = ctypes.string_at(p.contents.CredentialBlob, p.contents.CredentialBlobSize)
        return brut.decode("utf-16-le").strip() or None
    finally:
        adv.CredFree(p)


def ecrire_cle(cle: str) -> None:
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    blob = cle.encode("utf-16-le")
    tampon = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    c = _CREDENTIAL(Type=_GENERIQUE, TargetName=CIBLE_CLE, UserName="zenodo.org",
                    Comment="Clé d'accès personnelle à l'API de Zenodo, tutoriel 07",
                    CredentialBlobSize=len(blob), CredentialBlob=tampon, Persist=_PERSISTANT)
    if not adv.CredWriteW(ctypes.byref(c), 0):
        raise Arret(f"la clé n'a pas pu être rangée dans le gestionnaire d'identifiants (erreur Windows "
                    f"{ctypes.get_last_error()})")


# ---------------------------------------------------------------- appels à l'API
class Zenodo:
    def __init__(self, cle: str):
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {cle}"

    def appel(self, methode: str, url: str, attendu=(200, 201, 202, 204), **kw) -> requests.Response:
        url = url if url.startswith("http") else API + url
        for essai in range(4):
            try:
                r = self.s.request(methode, url, timeout=kw.pop("timeout", 120), **kw)
            except requests.RequestException as e:
                if essai == 3:
                    raise Arret(f"Zenodo ne répond pas ({e.__class__.__name__}). Réessayer plus tard.") from e
                time.sleep(15)
                continue
            if r.status_code in (429, 500, 502, 503, 504) and essai < 3:
                time.sleep(30 if r.status_code == 429 else 15)
                continue
            if r.status_code in (401, 403):
                raise Arret("Zenodo refuse la clé d'accès (code %d). Elle est peut-être expirée ou révoquée, ou il lui "
                            "manque les droits deposit:write et deposit:actions. En créer une nouvelle (tutoriel 07, "
                            "partie A) puis lancer python outils\\zenodo.py cle." % r.status_code)
            if r.status_code not in attendu:
                raise Arret(f"réponse inattendue de Zenodo à {methode} {url.replace(API, '')} (code {r.status_code}), "
                            f"{r.text[:400]}")
            return r
        raise Arret("Zenodo ne répond pas. Réessayer plus tard.")

    def depots(self) -> list[dict]:
        """Toutes les versions de tous les dépôts du compte, publiées ou en brouillon."""
        tout, page = [], 1
        while True:
            lot = self.appel("GET", "/deposit/depositions",
                             params={"all_versions": "true", "size": 25, "page": page}).json()
            tout += lot
            if len(lot) < 25:
                return tout
            page += 1


def concept(doi: str) -> str:
    """Identifiant Zenodo du DOI général (10.5281/zenodo.23264933 donne 23264933)."""
    return doi.rsplit(".", 1)[1]


def etat_depots(z: Zenodo) -> dict:
    """Pour chaque dépôt, sa dernière version publiée et son brouillon de nouvelle version s'il en a un."""
    tous = z.depots()
    sortie = {}
    for cle, doi in DEPOTS.items():
        lies = [d for d in tous if str(d.get("conceptrecid")) == concept(doi)]
        publiees = sorted((d for d in lies if d.get("submitted")), key=lambda d: d["id"])
        brouillons = [d for d in lies if not d.get("submitted")]
        if not publiees:
            raise Arret(f"aucune version publiée trouvée pour le dépôt {NOMS[cle]} (DOI {doi}) sur ce compte Zenodo")
        sortie[cle] = {"derniere": publiees[-1], "brouillon": brouillons[0] if brouillons else None}
    return sortie


def lire_etat() -> dict:
    return json.loads(ETAT.read_text(encoding="utf-8")) if ETAT.exists() else {}


def ecrire_etat(etat: dict) -> None:
    ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")


def md5(f: Path) -> str:
    h = hashlib.md5()
    with open(f, "rb") as fh:
        for bloc in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def connexion() -> Zenodo:
    cle = lire_cle()
    if not cle:
        raise Arret("aucune clé d'accès Zenodo dans le gestionnaire d'identifiants de Windows. Suivre le tutoriel 07, "
                    "parties A et B.")
    return Zenodo(cle)


def version_du_depot(d: dict) -> str:
    """Champ Version du dépôt, sinon sa date de publication (champ Version laissé vide sur les premières versions du
    9 octobre 2026)."""
    m = d.get("metadata") or {}
    return m.get("version") or m.get("publication_date") or "sans numéro"


# ---------------------------------------------------------------- commandes
def cmd_cle(_args) -> int:
    print("Colle la clé d'accès créée sur Zenodo, puis appuie sur Entrée. Rien ne s'affiche pendant la saisie, c'est "
          "normal.")
    cle = getpass.getpass("Clé d'accès Zenodo : ").strip()
    if len(cle) < 20:
        raise Arret("la clé saisie est trop courte. Recommencer en collant la clé entière (clic droit dans la fenêtre "
                    "PowerShell pour coller).")
    etat_depots(Zenodo(cle))   # teste la clé et la présence des trois dépôts avant de la ranger
    ecrire_cle(cle)
    print(f"Clé acceptée par Zenodo et rangée dans le gestionnaire d'identifiants de Windows, sous « {CIBLE_CLE} ».")
    return 0


def cmd_verifier(_args) -> int:
    e = etat_depots(connexion())
    print("Connexion à Zenodo réussie.")
    for cle, x in e.items():
        ligne = f"- {NOMS[cle]}, dernière version publiée {version_du_depot(x['derniere'])}"
        if x["brouillon"]:
            ligne += f", brouillon en cours ({x['brouillon']['links'].get('html') or 'https://zenodo.org/deposit/' + str(x['brouillon']['id'])})"
        print(ligne)
    print(f"Version archivée citée par le site, {config.VERSION_ZENODO}.")
    return 0


def derniere_version() -> str:
    dates = sorted(p.name for p in config.RESULTATS.glob("20*") if (p / "rapport_sante_mentale.md").exists())
    if not dates:
        raise Arret("aucun résultat complet dans le dossier resultats")
    return dates[-1]


def cmd_preparer(args) -> int:
    version = args.version or derniere_version()
    z = connexion()
    e = etat_depots(z)
    if all(version_du_depot(x["derniere"]) == version for x in e.values()):
        print(f"La version {version} est déjà publiée sur Zenodo pour les trois dépôts, rien à préparer.")
        return 0
    print(f"Fichiers de la version {version}, archive des données et rapports en PDF (quelques minutes).")
    from pipeline import site
    fichiers = site.fichiers_zenodo(version, DOSSIER / version)
    etat = lire_etat()
    etat.update({"en_preparation": version, "brouillons": {}, "date_preparation": dt.datetime.now().isoformat("T", "seconds")})
    for cle, x in e.items():
        if version_du_depot(x["derniere"]) == version:
            print(f"- {NOMS[cle]}, version {version} déjà publiée, laissé tel quel.")
            continue
        # le brouillon de nouvelle version, repris s'il existe déjà, sinon créé à partir de la dernière version publiée
        if x["brouillon"]:
            brouillon = z.appel("GET", f"/deposit/depositions/{x['brouillon']['id']}").json()
        else:
            r = z.appel("POST", f"/deposit/depositions/{x['derniere']['id']}/actions/newversion").json()
            brouillon = z.appel("GET", r["links"]["latest_draft"]).json()
        if brouillon.get("submitted"):
            raise Arret(f"Zenodo n'a pas créé de brouillon pour le dépôt {NOMS[cle]}, rien n'a été modifié")
        bid = brouillon["id"]
        # les fichiers repris de la version précédente sont retirés, puis les nouveaux sont envoyés
        for f in z.appel("GET", f"/deposit/depositions/{bid}/files").json():
            z.appel("DELETE", f"/deposit/depositions/{bid}/files/{f['id']}")
        for f in fichiers[cle]:
            with open(f, "rb") as fh:
                rep = z.appel("PUT", f"{brouillon['links']['bucket']}/{f.name}", data=fh, timeout=1800).json()
            if rep.get("checksum", "").removeprefix("md5:") != md5(f):
                raise Arret(f"le fichier {f.name} reçu par Zenodo ne correspond pas au fichier envoyé. Lancer "
                            "python outils\\zenodo.py abandonner, puis recommencer.")
        meta = brouillon["metadata"]
        meta.update({"version": version, "publication_date": version})
        z.appel("PUT", f"/deposit/depositions/{bid}", json={"metadata": meta})
        # adresse donnée par Zenodo lui-même (le brouillon n'est visible que du titulaire du compte, connecté)
        lien = brouillon["links"].get("latest_draft_html") or brouillon["links"].get("html") or f"https://zenodo.org/deposit/{bid}"
        etat["brouillons"][cle] = {"id": bid, "lien": lien, "fichiers": sorted(f.name for f in fichiers[cle]),
                                   "md5": {f.name: md5(f) for f in fichiers[cle]}}
        print(f"- {NOMS[cle]}, brouillon prêt, " + ", ".join(f"{f.name} ({f.stat().st_size / 1e6:.1f} Mo)"
                                                               for f in fichiers[cle]) + f", {lien}")
    ecrire_etat(etat)
    print("\nRien n'est publié. Relire chaque brouillon sur Zenodo (bouton Preview), puis publier, soit sur Zenodo "
          "(bouton Publish), soit par python outils\\zenodo.py publier.")
    return 0


def cmd_publier(args) -> int:
    etat = lire_etat()
    brouillons = etat.get("brouillons") or {}
    if not brouillons:
        raise Arret("aucun brouillon préparé. Lancer d'abord python outils\\zenodo.py preparer.")
    z = connexion()
    a_publier = []
    for cle, b in brouillons.items():
        d = z.appel("GET", f"/deposit/depositions/{b['id']}").json()
        if d.get("submitted"):
            print(f"- {NOMS[cle]}, déjà publié.")
            continue
        noms = sorted(f["filename"] for f in z.appel("GET", f"/deposit/depositions/{b['id']}/files").json())
        attendus = b.get("fichiers") or [b["fichier"]]
        if noms != attendus:
            raise Arret(f"le brouillon du dépôt {NOMS[cle]} ne contient pas exactement les fichiers attendus "
                        f"({', '.join(attendus)}), mais {', '.join(noms) or 'aucun fichier'}. Rien n'a été publié.")
        a_publier.append((cle, b))
    if a_publier:
        print(f"Publication de la version {etat['en_preparation']} pour "
              + ", ".join(NOMS[c] for c, _ in a_publier) + ". Une version publiée ne peut plus être retirée.")
        if not args.oui and input("Écris oui puis Entrée pour publier : ").strip().lower() != "oui":
            print("Rien n'a été publié.")
            return 0
        for cle, b in a_publier:
            z.appel("POST", f"/deposit/depositions/{b['id']}/actions/publish")
            print(f"- {NOMS[cle]}, publié.")
    return cmd_constater(args)


def cmd_abandonner(_args) -> int:
    etat = lire_etat()
    z = connexion()
    for cle, x in etat_depots(z).items():
        if x["brouillon"]:
            z.appel("DELETE", f"/deposit/depositions/{x['brouillon']['id']}", attendu=(201, 204))
            print(f"- {NOMS[cle]}, brouillon supprimé.")
    etat.pop("brouillons", None)
    etat.pop("en_preparation", None)
    ecrire_etat(etat)
    print("Aucun brouillon ne reste, rien n'a été publié.")
    return 0


def cmd_constater(args) -> int:
    """Version archivée = dernière version publiée, quand elle est la même pour les trois dépôts."""
    try:
        e = etat_depots(connexion())
    except Arret as x:
        if getattr(args, "discret", False):
            print(f"Zenodo non vérifié, {x}")
            return 20
        raise
    versions = {cle: version_du_depot(x["derniere"]) for cle, x in e.items()}
    etat = lire_etat()
    if len(set(versions.values())) != 1:
        print("Les trois dépôts n'ont pas la même dernière version publiée ("
              + ", ".join(f"{NOMS[c]} {v}" for c, v in versions.items()) + "). La version citée par le site reste "
              f"{config.VERSION_ZENODO}.")
        return 0
    v = versions["donnees"]
    if not (config.RESULTATS / v).is_dir():
        print(f"La dernière version publiée sur Zenodo ({v}) ne correspond à aucun dossier de résultats, rien n'est "
              "changé.")
        return 0
    if v == etat.get("version_archivee", config.VERSION_ZENODO):
        if not getattr(args, "discret", False):
            print(f"Version archivée citée par le site, {v}, déjà à jour.")
        return 0
    etat.update({"version_archivee": v, "date_constat": dt.datetime.now().isoformat("T", "seconds")})
    if etat.get("en_preparation") == v:
        etat.pop("en_preparation", None)
        etat.pop("brouillons", None)
    ecrire_etat(etat)
    print(f"La version {v} est archivée sur Zenodo pour les trois dépôts. Le site la citera par son DOI après sa "
          "prochaine reconstruction (python -m pipeline.site, puis publication).")
    return 10


def cmd_rappel(args) -> int:
    """Rappel trimestriel d'archivage (choix de Lucas du 10 octobre 2026, une version par trimestre). Code 10 quand la
    dernière version archivée a au moins JOURS_RAPPEL jours, qu'une version plus récente existe, et que le dernier
    rappel date d'au moins une semaine. La tâche planifiée affiche alors une fenêtre (mise_a_jour.ps1)."""
    etat = lire_etat()
    archivee = dt.date.fromisoformat(etat.get("version_archivee", config.VERSION_ZENODO))
    recente = derniere_version()
    age = (dt.date.today() - archivee).days
    if recente <= archivee.isoformat() or age < args.jours:
        return 0
    if etat.get("en_preparation"):
        texte = (f"Les brouillons de la version {etat['en_preparation']} attendent sur Zenodo. Il reste à les relire et "
                 "à les publier (tutoriel 07, partie C, étapes 2 à 6).")
    else:
        texte = (f"La dernière version archivée sur Zenodo date du {archivee:%d/%m/%Y}, il y a {age} jour{'s' if age > 1 else ''}. "
                 f"Il est temps d'archiver la version du {dt.date.fromisoformat(recente):%d/%m/%Y} (tutoriel 07, "
                 "partie C, une dizaine de minutes).")
    dernier = etat.get("dernier_rappel")
    if dernier and (dt.date.today() - dt.date.fromisoformat(dernier)).days < 7 and not args.forcer:
        return 0
    etat["dernier_rappel"] = dt.date.today().isoformat()
    ecrire_etat(etat)
    print(texte + " Ce rappel reviendra dans une semaine tant que ce n'est pas fait.")
    return 10


def main() -> int:
    ap = argparse.ArgumentParser(description="Nouvelles versions des dépôts Zenodo (tutoriel 07).")
    sous = ap.add_subparsers(dest="commande", required=True)
    sous.add_parser("cle")
    sous.add_parser("verifier")
    p = sous.add_parser("preparer")
    p.add_argument("--version", help="date de la version à archiver (par défaut la plus récente)")
    p = sous.add_parser("publier")
    p.add_argument("--oui", action="store_true", help="ne pas demander de confirmation")
    sous.add_parser("abandonner")
    p = sous.add_parser("constater")
    p.add_argument("--discret", action="store_true", help="pour la tâche planifiée, code 20 sans erreur si Zenodo "
                                                          "n'est pas joignable ou si aucune clé n'est rangée")
    p = sous.add_parser("rappel")
    p.add_argument("--jours", type=int, default=JOURS_RAPPEL, help="âge de la dernière version archivée qui déclenche "
                                                                    "le rappel")
    p.add_argument("--forcer", action="store_true", help="ignorer le délai d'une semaine entre deux rappels")
    args = ap.parse_args()
    try:
        return {"cle": cmd_cle, "verifier": cmd_verifier, "preparer": cmd_preparer, "publier": cmd_publier,
                "abandonner": cmd_abandonner, "constater": cmd_constater,
                "rappel": cmd_rappel}[args.commande](args)
    except Arret as e:
        print(f"Arrêt, {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
