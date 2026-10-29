"""Messages pour LinkedIn (profil de Lucas) et Bluesky (compte du projet, @ubicura.fr), relus dans l'onglet « Réseaux »
de la fenêtre du courrier et publiés seulement par un clic de Lucas sur « Publier » (tutoriels 10 et 11, feuille de
route de la communication, phase 2, décisions de Lucas du 29 octobre 2026). Les messages restent sur le PC dans
donnees\\messagerie\\reseaux\\ (hors de Git).

    python outils\\reseaux.py bluesky-mot-de-passe   identifiant du compte et mot de passe d'application de Bluesky,
                                                    testés puis rangés dans le gestionnaire d'identifiants de Windows
    python outils\\reseaux.py linkedin-application   identifiant et secret de l'application de développeur de LinkedIn
    python outils\\reseaux.py linkedin-autoriser     autorisation de publier au nom de Lucas, valable 60 jours
    python outils\\reseaux.py verifier               état de chaque compte, sans rien publier
    python outils\\reseaux.py ajouter F              ajoute le message du fichier JSON F, après contrôle
    python outils\\reseaux.py apercu ID              ce qui serait envoyé à chaque réseau, sans rien envoyer
    python outils\\reseaux.py publier-programmes     publie les messages programmés par Lucas dont l'heure est passée
    python outils\\reseaux.py suivre [--essai]       abonne le compte Bluesky du projet aux comptes cochés par Lucas
                                                    dans docs\\reseaux\\comptes_a_suivre.csv, cinq par jour au plus
                                                    (aussi lancé par messagerie.py envoyer-programmes)

Interfaces officielles seulement, jamais d'automate qui pilote un compte, jamais le mot de passe principal d'un compte.
Les identifiants sont saisis par Lucas et rangés dans le gestionnaire d'identifiants de Windows (outils/identifiants.py),
jamais écrits dans un fichier ni affichés.

Bluesky, lexiques du dépôt bluesky-social/bsky lus le 29 octobre 2026 (lexicons/app/bsky/feed/post.json, texte de
300 graphèmes et 3 000 octets au plus, text et createdAt obligatoires ; embed/images.json, 4 images au plus de
2 000 000 octets chacune, texte de remplacement obligatoire ; richtext/facet.json, positions en octets UTF-8, début
compris, fin exclue, lien par #link et son uri), et dépôt bluesky-social/atproto (com.atproto.server.createSession,
com.atproto.repo.uploadBlob, com.atproto.repo.createRecord). Ouverture de session sur bsky.social, puis appels au
serveur du compte indiqué par son document DID.

LinkedIn, documentation officielle lue le 29 octobre 2026 (learn.microsoft.com/en-us/linkedin), flux d'autorisation à
trois parties (jeton de 60 jours, sans renouvellement programmatique hors partenaires), produits « Share on LinkedIn »
(portée w_member_social) et « Sign in with LinkedIn using OpenID Connect » (openid, profile, identifiant par
GET /v2/userinfo), Posts API (POST /rest/posts, en-têtes Linkedin-Version et X-Restli-Protocol-Version 2.0.0, identifiant
du message dans l'en-tête x-restli-id), Images API (initializeUpload puis envoi du fichier par PUT), texte au format
« little text » (caractères réservés précédés d'une barre oblique inverse). La publication avec une personne comme
auteur n'a pas d'exemple dans la documentation, à confirmer au premier essai (tutoriel 10, partie E).

Fichiers de donnees\\messagerie\\reseaux\\
    messages\\<id>.json          message (a_relire, plus_tard, programme, publie, ecarte), une version par réseau
    figures\\<id>.png            figure du message, copiée à l'ajout ; une figure changée annule la validation
    journal_publications.csv    date, réseau, message, adresse publique et texte de chaque publication
    journal_abonnements.csv     date, état (suivi, deja_suivi) et compte de chaque abonnement sur Bluesky
    etat.json                   autorisation LinkedIn (date d'expiration), sans aucun secret
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import getpass
import hashlib
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from pipeline import config  # noqa: E402
from outils import identifiants  # noqa: E402

DOSSIER = config.DONNEES / "messagerie" / "reseaux"
MESSAGES, FIGURES = DOSSIER / "messages", DOSSIER / "figures"
JOURNAL_PUBLICATIONS = DOSSIER / "journal_publications.csv"
ETAT = DOSSIER / "etat.json"
RESEAUX = {"linkedin": "LinkedIn", "bluesky": "Bluesky"}
STATUTS = ("a_relire", "plus_tard", "programme", "publie", "ecarte")
CHAMPS = {"id", "titre", "motif", "linkedin", "bluesky", "lien", "figure", "alt", "sources", "reseaux", "envoi_prevu",
          "donnees"}

# noms des secrets dans le gestionnaire d'identifiants de Windows
CIBLE_BLUESKY = "Ubi Cura, Bluesky"                       # identifiant du compte, mot de passe d'application
CIBLE_LINKEDIN_APPLI = "Ubi Cura, LinkedIn application"   # identifiant (client id) et secret de l'application
CIBLE_LINKEDIN_JETON = "Ubi Cura, LinkedIn jeton"         # auteur (urn:li:person:…) et jeton d'accès

BLUESKY_ENTREE = "https://bsky.social"
BLUESKY_GRAPHEMES, BLUESKY_OCTETS, BLUESKY_IMAGE_OCTETS = 300, 3000, 2_000_000
LINKEDIN_API = "https://api.linkedin.com"
LINKEDIN_VERSION = config.LINKEDIN_VERSION
LINKEDIN_CARACTERES = 3000          # longueur gardée pour la version LinkedIn (limite la plus citée par LinkedIn)
LINKEDIN_REDIRECTION = "http://localhost:8765/linkedin"
LINKEDIN_PORTEES = "openid profile w_member_social"
ALT_CARACTERES = 2000
MOTIF_APP_BLUESKY = re.compile(r"^[a-z0-9]{4}(-[a-z0-9]{4}){3}$")   # forme des mots de passe d'application
# liens rendus cliquables sur Bluesky, adresse complète ou adresse du site sans « https:// » (plus courte)
LIEN = re.compile(r"https?://[^\s<>«»\"]+|(?<![\w@/.-])(?:www\.)?ubicura\.fr(?:/[^\s<>«»\"]*)?")
FIN_DE_LIEN = ".,;:!?)»'’\""
RESERVES_LINKEDIN = set("|{}@[]()<>#\\*_~")

# abonnements du compte Bluesky du projet (demande de Lucas du 29 octobre 2026), seulement aux comptes de la liste
# vérifiée qu'il a cochés, une poignée par jour, jamais deux fois le même, ni message ni « j'aime ». Lexique
# app.bsky.graph.follow (dépôt bluesky-social/bsky, lexicons/app/bsky/graph/follow.json, subject en DID et createdAt
# obligatoires), relations lues par app.bsky.graph.getRelationships sur l'API publique.
COMPTES_A_SUIVRE = RACINE / "docs" / "reseaux" / "comptes_a_suivre.csv"
COLONNES_COMPTES = ["reseau", "identifiant", "did", "nom", "categorie", "pourquoi", "verification", "verifie_le",
                    "valide"]
JOURNAL_ABONNEMENTS = DOSSIER / "journal_abonnements.csv"
BLUESKY_PUBLIC = "https://public.api.bsky.app"
COLLECTION_SUIVI = "app.bsky.graph.follow"   # seule collection écrite par la commande suivre
SUIVIS_PAR_JOUR, PAUSE_SUIVI = 5, 30         # cinq comptes par jour au plus, 30 secondes entre deux abonnements
MOTIF_DID = re.compile(r"did:plc:[a-z2-7]{24}")


class Arret(Exception):
    """Arrêt propre, avec un message pour Lucas."""


# ---------------------------------------------------------------- fichiers
def lire_json(f: Path, defaut=None):
    return json.loads(f.read_text(encoding="utf-8-sig")) if f.exists() else defaut


def ecrire_json(f: Path, contenu) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(contenu, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(f)


def maintenant() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def messages() -> list[dict]:
    return sorted((lire_json(f) for f in MESSAGES.glob("*.json")), key=lambda m: m.get("cree_le") or "")


def enregistrer(m: dict) -> None:
    ecrire_json(MESSAGES / f"{m['id']}.json", m)


def chemin_figure(m: dict) -> Path:
    """Figure du message, dans figures\\ une fois ajouté, ou chemin du fichier source (relatif au projet)."""
    p = Path(str(m.get("figure") or ""))
    if p.is_absolute():
        return p
    for base in (FIGURES, RACINE):
        if (base / p).is_file():
            return base / p
    return FIGURES / p


def taille_png(brut: bytes) -> tuple[int, int] | None:
    """Largeur et hauteur d'une image PNG, lues dans son en-tête, ou None si ce n'est pas un PNG."""
    if brut[:8] != b"\x89PNG\r\n\x1a\n" or brut[12:16] != b"IHDR":
        return None
    return int.from_bytes(brut[16:20], "big"), int.from_bytes(brut[20:24], "big")


# ---------------------------------------------------------------- textes
def graphemes(texte: str) -> int:
    """Nombre de graphèmes (caractères perçus), comme Bluesky les compte, sans bibliothèque extérieure. Les signes qui
    se combinent au précédent (accents séparés, sélecteurs de variante, modificateurs de couleur de peau, éléments
    joints par U+200D, seconde lettre d'un drapeau) ne comptent pas. En cas de doute, le compte est au plus haut, jamais
    au plus bas."""
    n, joint, drapeau, avant = 0, False, False, ""
    for ch in texte:
        o, precedent, avant = ord(ch), avant, ch
        if joint:
            joint = False
            continue
        if o == 0x200D:
            joint = True
            continue
        if unicodedata.combining(ch) or 0xFE00 <= o <= 0xFE0F or 0x1F3FB <= o <= 0x1F3FF or 0xE0020 <= o <= 0xE007F:
            continue
        if 0x1F1E6 <= o <= 0x1F1FF:
            drapeau = not drapeau
            if not drapeau:
                continue
        else:
            drapeau = False
        if ch == "\n" and precedent == "\r":
            continue
        n += 1
    return n


def liens(texte: str) -> list[tuple[int, int, str]]:
    """Liens du texte, (début, fin en caractères, adresse complète)."""
    sortie = []
    for m in LIEN.finditer(texte):
        brut = m.group(0).rstrip(FIN_DE_LIEN)
        if not brut:
            continue
        uri = brut if brut.startswith(("http://", "https://")) else "https://" + brut
        sortie.append((m.start(), m.start() + len(brut), uri))
    return sortie


def facettes(texte: str) -> list[dict]:
    """Facettes de lien de Bluesky (app.bsky.richtext.facet#link), positions en octets UTF-8, fin exclue."""
    sortie = []
    for debut, fin, uri in liens(texte):
        a = len(texte[:debut].encode("utf-8"))
        b = a + len(texte[debut:fin].encode("utf-8"))
        sortie.append({"index": {"byteStart": a, "byteEnd": b},
                       "features": [{"$type": "app.bsky.richtext.facet#link", "uri": uri}]})
    return sortie


def echapper_linkedin(texte: str) -> str:
    """Texte au format « little text » de LinkedIn, chaque caractère réservé précédé d'une barre oblique inverse
    (sinon LinkedIn y lit une mention, un mot-dièse ou coupe le message)."""
    return "".join("\\" + ch if ch in RESERVES_LINKEDIN else ch for ch in texte)


def _prose(texte: str) -> str:
    """Texte sans ses liens, pour les contrôles de style."""
    for debut, fin, _ in reversed(liens(texte)):
        texte = texte[:debut] + " " + texte[fin:]
    return texte


def controler_message(m: dict) -> list[str]:
    """Erreurs qui empêchent l'ajout ou la publication d'un message."""
    from pipeline import libelles
    erreurs = []
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,80}", str(m.get("id", ""))):
        erreurs.append("id en minuscules, chiffres et tirets")
    inconnus = set(m) - CHAMPS - {"statut", "cree_le", "modifie_le", "programme_le", "empreinte_validee",
                                  "publications", "valide_le"}
    if inconnus:
        erreurs.append(f"champs inconnus {sorted(inconnus)}")
    for champ in ("titre", "motif", "lien", "alt"):
        if not str(m.get(champ, "")).strip():
            erreurs.append(f"{champ} manquant")
    reseaux = m.get("reseaux") or []
    if not reseaux or not set(reseaux) <= set(RESEAUX):
        erreurs.append(f"reseaux parmi {sorted(RESEAUX)}, au moins un")
    if not str(m.get("lien", "")).startswith(config.ADRESSE_SITE.rstrip("/") + "/"):
        erreurs.append(f"le lien mène au site ({config.ADRESSE_SITE})")
    for r in RESEAUX:
        texte = str(m.get(r) or "")
        if r in reseaux and not texte.strip():
            erreurs.append(f"version {RESEAUX[r]} manquante")
        if not texte:
            continue
        prose = _prose(texte)
        if "—" in prose or " – " in prose:
            erreurs.append(f"{RESEAUX[r]}, tiret long dans le texte")
        if re.search(r"\s:|:\s|:$", prose):
            erreurs.append(f"{RESEAUX[r]}, deux-points dans le texte")
        erreurs += [f"{RESEAUX[r]}, {x}" for x in libelles.termes_proscrits(texte)]
        if not liens(texte):
            erreurs.append(f"{RESEAUX[r]}, aucun lien vers le site")
    b = str(m.get("bluesky") or "")
    if graphemes(b) > BLUESKY_GRAPHEMES:
        erreurs.append(f"Bluesky, {graphemes(b)} caractères pour {BLUESKY_GRAPHEMES} au plus")
    if len(b.encode("utf-8")) > BLUESKY_OCTETS:
        erreurs.append(f"Bluesky, {len(b.encode('utf-8'))} octets pour {BLUESKY_OCTETS} au plus")
    if len(str(m.get("linkedin") or "")) > LINKEDIN_CARACTERES:
        erreurs.append(f"LinkedIn, {len(m['linkedin'])} caractères pour {LINKEDIN_CARACTERES} au plus")
    if len(str(m.get("alt") or "")) > ALT_CARACTERES:
        erreurs.append(f"texte de remplacement de {len(m['alt'])} caractères pour {ALT_CARACTERES} au plus")
    f = chemin_figure(m)
    if not m.get("figure") or not f.is_file():
        erreurs.append("figure introuvable")
    else:
        brut = f.read_bytes()
        if taille_png(brut) is None:
            erreurs.append("figure au format PNG")
        if len(brut) > BLUESKY_IMAGE_OCTETS:
            erreurs.append(f"figure de {len(brut)} octets, {BLUESKY_IMAGE_OCTETS} au plus pour Bluesky")
    if m.get("envoi_prevu") is not None and lire_date(m["envoi_prevu"]) is None:
        erreurs.append("envoi_prevu au format AAAA-MM-JJTHH:MM (heure de Paris)")
    return erreurs


def lire_date(texte) -> dt.datetime | None:
    from outils.messagerie import lire_date as lire
    return lire(texte)


def empreinte(m: dict) -> str:
    """Empreinte de ce que Lucas a validé au clic, textes, réseaux choisis, texte de remplacement et figure."""
    f = chemin_figure(m)
    image = hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else None
    return hashlib.sha256(json.dumps([m.get("linkedin"), m.get("bluesky"), m.get("alt"), m.get("lien"),
                                      sorted(m.get("reseaux") or []), image], ensure_ascii=False)
                          .encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- Bluesky
def _http():
    import requests
    return requests


def _erreur_http(reseau: str, r) -> Arret:
    try:
        detail = r.json()
        detail = detail.get("message") or detail.get("error") or ""
    except ValueError:
        detail = ""
    return Arret(f"{reseau} a refusé la demande (code {r.status_code}{', ' + str(detail)[:200] if detail else ''}).")


def _handle_actuel(did: str) -> str | None:
    """Identifiant actuel du compte, lu sur l'interface publique de Bluesky (app.bsky.actor.getProfile), sans secret."""
    if not did:
        return None
    try:
        r = _http().get("https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile", params={"actor": did}, timeout=30)
        return r.json().get("handle") if r.status_code == 200 else None
    except Exception:  # noqa: BLE001
        return None


def session_bluesky(identifiant: str | None = None, mdp: str | None = None) -> dict:
    """Session ouverte avec le mot de passe d'application, {jeton, did, handle, serveur}."""
    candidats = [identifiant]
    if not (identifiant and mdp):
        identifiant, mdp = identifiants.lire_compte(CIBLE_BLUESKY)
        # l'identifiant rangé est celui du jour de la saisie (ubicura.bsky.social le 29 octobre 2026), il change quand le
        # compte passe à @ubicura.fr ; le DID du compte (config.BLUESKY_DID) ne change jamais, puis l'identifiant actuel
        # lu sur l'interface publique, puis celui qui est rangé
        candidats = [config.BLUESKY_DID, _handle_actuel(config.BLUESKY_DID), identifiant]
    candidats = [c for c in dict.fromkeys(candidats) if c]
    if not (candidats and mdp):
        raise Arret("aucun compte Bluesky dans le gestionnaire d'identifiants de Windows (tutoriel 11, partie D).")
    requests = _http()
    for c in candidats:
        try:
            r = requests.post(f"{BLUESKY_ENTREE}/xrpc/com.atproto.server.createSession",
                              json={"identifier": c, "password": mdp}, timeout=60)
        except requests.RequestException as e:
            raise Arret(f"Bluesky ne répond pas ({e.__class__.__name__}). Réessayer plus tard.") from e
        if r.status_code not in (400, 401):
            break
    if r.status_code == 401:
        raise Arret("Bluesky refuse l'identifiant ou le mot de passe d'application (tutoriel 11, partie D).")
    if r.status_code != 200:
        raise _erreur_http("Bluesky", r)
    s = r.json()
    serveur = next((x.get("serviceEndpoint") for x in (s.get("didDoc") or {}).get("service", [])
                    if str(x.get("id", "")).endswith("#atproto_pds")), None) or BLUESKY_ENTREE
    return {"jeton": s["accessJwt"], "did": s["did"], "handle": s["handle"], "serveur": serveur.rstrip("/")}


def enregistrement_bluesky(m: dict, image: dict | None, largeur: int, hauteur: int, quand: dt.datetime) -> dict:
    """Message app.bsky.feed.post, texte, facettes de lien, langue, figure et son texte de remplacement."""
    texte = m["bluesky"].strip()
    rec = {"$type": "app.bsky.feed.post", "text": texte,
           "createdAt": quand.astimezone(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
           "langs": ["fr"]}
    f = facettes(texte)
    if f:
        rec["facets"] = f
    if image is not None:
        rec["embed"] = {"$type": "app.bsky.embed.images",
                        "images": [{"alt": m["alt"].strip(), "image": image,
                                    "aspectRatio": {"width": largeur, "height": hauteur}}]}
    return rec


def publier_bluesky(m: dict) -> dict:
    requests = _http()
    s = session_bluesky()
    entetes = {"Authorization": f"Bearer {s['jeton']}"}
    brut = chemin_figure(m).read_bytes()
    largeur, hauteur = taille_png(brut)
    try:
        r = requests.post(f"{s['serveur']}/xrpc/com.atproto.repo.uploadBlob", data=brut,
                          headers=entetes | {"Content-Type": "image/png"}, timeout=120)
        if r.status_code != 200:
            raise _erreur_http("Bluesky", r)
        rec = enregistrement_bluesky(m, r.json()["blob"], largeur, hauteur, dt.datetime.now())
        r = requests.post(f"{s['serveur']}/xrpc/com.atproto.repo.createRecord", headers=entetes, timeout=60,
                          json={"repo": s["did"], "collection": "app.bsky.feed.post", "record": rec})
    except requests.RequestException as e:
        raise Arret(f"Bluesky ne répond pas ({e.__class__.__name__}). Réessayer plus tard.") from e
    if r.status_code != 200:
        raise _erreur_http("Bluesky", r)
    uri = r.json()["uri"]
    return {"le": maintenant(), "identifiant": uri,
            "adresse": f"https://bsky.app/profile/{s['handle']}/post/{uri.rsplit('/', 1)[-1]}"}


# ---------------------------------------------------------------- LinkedIn
def jeton_linkedin() -> tuple[str, str]:
    """Auteur (urn:li:person:…) et jeton d'accès, refusés s'ils ont expiré."""
    auteur, jeton = identifiants.lire_compte(CIBLE_LINKEDIN_JETON)
    if not (auteur and jeton):
        raise Arret("LinkedIn n'est pas encore autorisé à publier (tutoriel 10, partie D).")
    fin = (lire_json(ETAT, {}).get("linkedin") or {}).get("expire_le")
    if fin and dt.datetime.fromisoformat(fin) <= dt.datetime.now().astimezone():
        raise Arret(f"l'autorisation de LinkedIn a expiré le {dt.datetime.fromisoformat(fin):%d/%m/%Y}. La "
                    "renouveler (tutoriel 10, partie D).")
    return auteur, jeton


def entetes_linkedin(jeton: str) -> dict:
    return {"Authorization": f"Bearer {jeton}", "Linkedin-Version": LINKEDIN_VERSION,
            "X-Restli-Protocol-Version": "2.0.0"}


def corps_linkedin(m: dict, auteur: str, image: str | None) -> dict:
    """Corps de POST /rest/posts, message public d'une personne, avec la figure et son texte de remplacement."""
    corps = {"author": auteur, "commentary": echapper_linkedin(m["linkedin"].strip()), "visibility": "PUBLIC",
             "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                              "thirdPartyDistributionChannels": []},
             "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False}
    if image:
        corps["content"] = {"media": {"id": image, "altText": m["alt"].strip()}}
    return corps


def publier_linkedin(m: dict) -> dict:
    import time
    requests = _http()
    auteur, jeton = jeton_linkedin()
    e = entetes_linkedin(jeton)
    try:
        r = requests.post(f"{LINKEDIN_API}/rest/images?action=initializeUpload", headers=e, timeout=60,
                          json={"initializeUploadRequest": {"owner": auteur}})
        if r.status_code not in (200, 201):
            raise _erreur_http("LinkedIn", r)
        v = r.json()["value"]
        r = requests.put(v["uploadUrl"], data=chemin_figure(m).read_bytes(),
                         headers={"Authorization": f"Bearer {jeton}"}, timeout=120)
        if r.status_code not in (200, 201):
            raise _erreur_http("LinkedIn", r)
        time.sleep(5)   # l'image est traitée par LinkedIn avant d'être utilisable (lecture d'état non permise ici)
        r = requests.post(f"{LINKEDIN_API}/rest/posts", headers=e | {"Content-Type": "application/json"},
                          json=corps_linkedin(m, auteur, v["image"]), timeout=60)
    except requests.RequestException as ex:
        raise Arret(f"LinkedIn ne répond pas ({ex.__class__.__name__}). Réessayer plus tard.") from ex
    if r.status_code != 201:
        raise _erreur_http("LinkedIn", r)
    urn = r.headers.get("x-restli-id") or r.headers.get("X-RestLi-Id") or ""
    return {"le": maintenant(), "identifiant": urn,
            "adresse": f"https://www.linkedin.com/feed/update/{urn}/" if urn else "https://www.linkedin.com/feed/"}


PUBLIEURS = {"linkedin": publier_linkedin, "bluesky": publier_bluesky}


# ---------------------------------------------------------------- publication (seulement depuis la fenêtre)
def journaliser(m: dict, reseau: str, p: dict) -> None:
    neuf = not JOURNAL_PUBLICATIONS.exists()
    JOURNAL_PUBLICATIONS.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL_PUBLICATIONS.open("a", encoding="utf-8-sig" if neuf else "utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        if neuf:
            w.writerow(["date", "reseau", "message", "titre", "adresse", "lien", "texte"])
        w.writerow([p["le"], reseau, m["id"], m["titre"], p["adresse"], m["lien"], m[reseau].strip()])


def journal() -> list[dict]:
    if not JOURNAL_PUBLICATIONS.exists():
        return []
    with JOURNAL_PUBLICATIONS.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def publier(m: dict, publieurs=None) -> str:
    """Publie le message sur chaque réseau choisi qui ne l'a pas encore reçu. Un réseau déjà servi n'est jamais
    servi deux fois. Renvoie le compte rendu, lève Arret au premier échec (les réseaux déjà servis restent notés)."""
    publieurs = publieurs or PUBLIEURS
    erreurs = controler_message(m)
    if erreurs:
        raise Arret("publication refusée, " + " ; ".join(erreurs))
    m.setdefault("publications", {})
    faits = []
    for r in [x for x in RESEAUX if x in m["reseaux"]]:   # LinkedIn d'abord, un échec arrête avant Bluesky
        if r in m["publications"]:
            continue
        p = publieurs[r](m)
        m["publications"][r] = p
        enregistrer(m)
        journaliser(m, r, p)
        faits.append(f"{RESEAUX[r]}, {p['adresse']}")
    if all(r in m["publications"] for r in m["reseaux"]):
        m["statut"] = "publie"
        enregistrer(m)
    return "Publié. " + " ; ".join(faits) if faits else "Rien à publier, chaque réseau a déjà reçu ce message."


def valider(m: dict) -> None:
    m.update(valide_le=maintenant(), empreinte_validee=empreinte(m))


def programmer(m: dict, quand: dt.datetime) -> str:
    """Programme la publication, seulement depuis le bouton « Publier » de la fenêtre et sa confirmation."""
    valider(m)
    m.update(statut="programme", envoi_prevu=quand.strftime("%Y-%m-%dT%H:%M"), programme_le=maintenant())
    enregistrer(m)
    return f"Publication programmée le {quand.strftime('%d/%m/%Y à %H:%M')}."


def publier_programmes(publieurs=None) -> int:
    """Publie les messages programmés dont l'heure est passée. Un message changé depuis le clic (texte, réseaux,
    texte de remplacement, figure) n'est jamais publié, il revient à relire. Codes 0 rien à faire ou tout publié,
    20 au moins un échec (le message reste programmé et sera retenté)."""
    code = 0
    for m in messages():
        if m.get("statut") != "programme":
            continue
        quand = lire_date(m.get("envoi_prevu"))
        if quand is None or quand > dt.datetime.now():
            continue
        if m.get("empreinte_validee") != empreinte(m):
            m.update(statut="a_relire", modifie_le=maintenant())
            enregistrer(m)
            print(f"{m['id']} modifié depuis la programmation, remis à relire sans publication.")
            continue
        try:
            print(publier(m, publieurs))
        except Arret as e:
            print(f"{m['id']} non publié, nouvel essai au prochain passage ({e}).")
            code = 20
    return code


# ---------------------------------------------------------------- comptes à suivre (Bluesky seulement)
def lire_comptes(f: Path | None = None) -> list[dict]:
    f = f or COMPTES_A_SUIVRE
    with f.open(encoding="utf-8-sig", newline="") as h:
        lecteur = csv.DictReader(h, delimiter=";")
        if lecteur.fieldnames != COLONNES_COMPTES:
            raise Arret(f"colonnes de {f.name} inattendues ({lecteur.fieldnames}), attendu {COLONNES_COMPTES}.")
        return [{k: (v or "").strip() for k, v in ligne.items()} for ligne in lecteur]


def ecrire_comptes(lignes: list[dict], f: Path | None = None) -> None:
    f = f or COMPTES_A_SUIVRE
    tmp = f.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=COLONNES_COMPTES, delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows(lignes)
    tmp.replace(f)


def controler_comptes(lignes: list[dict]) -> list[str]:
    """Erreurs de la liste des comptes à suivre, qui empêchent tout abonnement."""
    erreurs, vus = [], set()
    for i, c in enumerate(lignes, start=2):
        if c["reseau"] != "bluesky":
            erreurs.append(f"ligne {i}, réseau {c['reseau']!r}, seul bluesky est suivi par la commande")
        if not MOTIF_DID.fullmatch(c["did"]):
            erreurs.append(f"ligne {i}, DID illisible ({c['did']!r})")
        for cle in ("identifiant", "did"):
            if c[cle] in vus:
                erreurs.append(f"ligne {i}, {c[cle]} en double")
            vus.add(c[cle])
        for cle in ("identifiant", "nom", "pourquoi", "verification"):
            if not c[cle]:
                erreurs.append(f"ligne {i}, {cle} manquant")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", c["verifie_le"]):
            erreurs.append(f"ligne {i}, date de vérification au format AAAA-MM-JJ")
        if c["valide"] and not re.fullmatch(r"oui|\d{4}-\d{2}-\d{2}", c["valide"]):
            erreurs.append(f"ligne {i}, colonne valide vide, « oui » ou date du choix")
    return erreurs


def journal_abonnements() -> list[dict]:
    if not JOURNAL_ABONNEMENTS.exists():
        return []
    with JOURNAL_ABONNEMENTS.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def journaliser_abonnement(c: dict, etat: str, uri: str = "") -> None:
    neuf = not JOURNAL_ABONNEMENTS.exists()
    JOURNAL_ABONNEMENTS.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL_ABONNEMENTS.open("a", encoding="utf-8-sig" if neuf else "utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        if neuf:
            w.writerow(["date", "etat", "identifiant", "did", "nom", "enregistrement"])
        w.writerow([maintenant(), etat, c["identifiant"], c["did"], c["nom"], uri])


def did_public(identifiant: str) -> str | None:
    """DID auquel mène aujourd'hui l'identifiant, lu sur l'API publique, ou None (compte supprimé, suspendu)."""
    requests = _http()
    try:
        r = requests.get(f"{BLUESKY_PUBLIC}/xrpc/app.bsky.actor.getProfile", params={"actor": identifiant},
                         timeout=30)
    except requests.RequestException as e:
        raise Arret(f"Bluesky ne répond pas ({e.__class__.__name__}). Réessayer plus tard.") from e
    return r.json().get("did") if r.status_code == 200 else None


def suit_deja(moi: str, did: str) -> bool:
    """Vrai si le compte du projet suit déjà ce compte (abonnement fait à la main dans Bluesky compris)."""
    requests = _http()
    try:
        r = requests.get(f"{BLUESKY_PUBLIC}/xrpc/app.bsky.graph.getRelationships",
                         params={"actor": moi, "others": [did]}, timeout=30)
    except requests.RequestException as e:
        raise Arret(f"Bluesky ne répond pas ({e.__class__.__name__}). Réessayer plus tard.") from e
    if r.status_code != 200:
        raise _erreur_http("Bluesky", r)
    return any(x.get("did") == did and x.get("following") for x in r.json().get("relationships", []))


def enregistrement_suivi(did: str, quand: dt.datetime) -> dict:
    return {"$type": COLLECTION_SUIVI, "subject": did,
            "createdAt": quand.astimezone(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")}


def suivre_bluesky(s: dict, did: str) -> str:
    """Un abonnement, et rien d'autre (ni message, ni « j'aime »). Renvoie l'adresse at:// de l'enregistrement."""
    requests = _http()
    try:
        r = requests.post(f"{s['serveur']}/xrpc/com.atproto.repo.createRecord", timeout=60,
                          headers={"Authorization": f"Bearer {s['jeton']}"},
                          json={"repo": s["did"], "collection": COLLECTION_SUIVI,
                                "record": enregistrement_suivi(did, dt.datetime.now())})
    except requests.RequestException as e:
        raise Arret(f"Bluesky ne répond pas ({e.__class__.__name__}). Réessayer plus tard.") from e
    if r.status_code != 200:
        raise _erreur_http("Bluesky", r)
    return r.json()["uri"]


def suivre(essai: bool = False, discret: bool = False, resoudre=None, deja=None, suiveur=None,
           pause: float = PAUSE_SUIVI) -> int:
    """Abonne le compte du projet aux comptes cochés par Lucas, cinq par jour au plus, dans l'ordre de la liste.
    Un compte déjà dans le journal n'est jamais repris. Un identifiant qui mène à un autre DID que celui vérifié est
    refusé (compte à revérifier). Codes 0 rien à faire ou fait, 20 au moins un échec. Avec essai, rien n'est envoyé."""
    import time
    resoudre, deja, suiveur = resoudre or did_public, deja or suit_deja, suiveur or suivre_bluesky
    lignes = lire_comptes()
    erreurs = controler_comptes(lignes)
    if erreurs:
        raise Arret("liste des comptes à suivre à corriger, aucun abonnement. " + " ; ".join(erreurs))
    journal = journal_abonnements()
    traites = {j["did"] for j in journal}
    aujourdhui = dt.date.today().isoformat()
    reste = SUIVIS_PAR_JOUR - sum(1 for j in journal if j["etat"] == "suivi" and j["date"][:10] == aujourdhui)
    a_faire = [c for c in lignes if c["valide"] and c["did"] not in traites]
    if not a_faire:
        if not discret:
            print("Aucun compte coché en attente d'abonnement.")
        return 0
    if reste <= 0:
        if not discret:
            print(f"Déjà {SUIVIS_PAR_JOUR} abonnements aujourd'hui, la suite demain ({len(a_faire)} en attente).")
        return 0
    s = None if essai else session_bluesky()
    moi = s["did"] if s else config.BLUESKY_DID
    faits, code = 0, 0
    for c in a_faire:
        if faits >= reste:
            break
        try:
            actuel = resoudre(c["identifiant"])
            if actuel != c["did"]:
                print(f"{c['nom']} (@{c['identifiant']}) non suivi, l'identifiant mène à "
                      f"{actuel or 'aucun compte'} au lieu du compte vérifié, à revérifier dans la liste.")
                continue
            if deja(moi, c["did"]):
                if not essai:
                    journaliser_abonnement(c, "deja_suivi")
                print(f"{c['nom']} (@{c['identifiant']}) déjà suivi, noté au journal.")
                continue
            if essai:
                print(f"{c['nom']} (@{c['identifiant']}) serait suivi (essai, rien n'est envoyé).")
                faits += 1
                continue
            if faits:
                time.sleep(pause)
            uri = suiveur(s, c["did"])
            journaliser_abonnement(c, "suivi", uri)
            faits += 1
            print(f"Bluesky, abonnement à {c['nom']} (@{c['identifiant']}).")
        except Arret as e:
            print(f"{c['nom']} non suivi, nouvel essai au prochain passage ({e}).")
            code = 20
            break
    restants = len(a_faire) - faits
    if faits and restants > 0 and not discret:
        print(f"{restants} compte(s) coché(s) encore en attente, {SUIVIS_PAR_JOUR} par jour au plus.")
    return code


def etat_suivis() -> dict:
    """Pour la fenêtre, {did: texte de l'état} des comptes déjà traités."""
    return {j["did"]: ("suivi le " if j["etat"] == "suivi" else "déjà suivi, constaté le ") +
            f"{j['date'][8:10]}/{j['date'][5:7]}" for j in journal_abonnements()}


def etat_comptes() -> dict:
    """État de chaque compte pour la fenêtre, sans connexion ni secret affiché, {réseau: (relié, texte)}."""
    ident, mdp = identifiants.lire_compte(CIBLE_BLUESKY)
    ident = _handle_actuel(config.BLUESKY_DID) or ident   # identifiant du jour, il a pu changer depuis la saisie
    sortie = {"bluesky": (bool(ident and mdp), f"Bluesky, compte {ident} relié" if ident and mdp
                          else "Bluesky, compte pas encore relié (tutoriel 11)")}
    auteur, jeton = identifiants.lire_compte(CIBLE_LINKEDIN_JETON)
    fin = (lire_json(ETAT, {}).get("linkedin") or {}).get("expire_le")
    if not (auteur and jeton):
        sortie["linkedin"] = (False, "LinkedIn, pas encore autorisé (tutoriel 10)")
    elif fin and dt.datetime.fromisoformat(fin) <= dt.datetime.now().astimezone():
        sortie["linkedin"] = (False, f"LinkedIn, autorisation expirée le {dt.datetime.fromisoformat(fin):%d/%m}, "
                                     "à renouveler (tutoriel 10, partie D)")
    elif not fin:
        sortie["linkedin"] = (True, "LinkedIn, autorisé")
    else:
        jours = (dt.datetime.fromisoformat(fin) - dt.datetime.now().astimezone()).days
        sortie["linkedin"] = (True, f"LinkedIn, autorisé jusqu'au {dt.datetime.fromisoformat(fin):%d/%m}"
                              + (", à renouveler bientôt (tutoriel 10, partie D)" if jours < 7 else ""))
    return sortie


# ---------------------------------------------------------------- commandes
def cmd_bluesky_mot_de_passe(_args) -> int:
    print("Identifiant du compte Bluesky du projet (par exemple ubicura.bsky.social, ou ubicura.fr une fois "
          "l'identifiant changé), puis Entrée.")
    ident = input("Identifiant : ").strip().lstrip("@")
    print("Mot de passe d'application créé dans Bluesky (forme xxxx-xxxx-xxxx-xxxx). Il ne s'affiche pas pendant la "
          "frappe. Jamais le mot de passe principal du compte.")
    mdp = getpass.getpass("Mot de passe d'application : ").strip()
    if not (ident and mdp):
        raise Arret("identifiant ou mot de passe vide, rien n'a changé.")
    if not MOTIF_APP_BLUESKY.match(mdp):
        raise Arret("ce n'est pas un mot de passe d'application (forme xxxx-xxxx-xxxx-xxxx). Le mot de passe principal "
                    "du compte n'est jamais rangé ici (tutoriel 11, partie D).")
    s = session_bluesky(ident, mdp)
    erreur = identifiants.ecrire(CIBLE_BLUESKY, mdp, s["handle"], "Mot de passe d'application Bluesky, tutoriel 11")
    if erreur:
        raise Arret(f"le mot de passe n'a pas pu être rangé (erreur Windows {erreur}).")
    print(f"Mot de passe d'application accepté par Bluesky pour @{s['handle']} et rangé dans le gestionnaire "
          f"d'identifiants de Windows, sous « {CIBLE_BLUESKY} ».")
    return 0


def cmd_linkedin_application(_args) -> int:
    print("Identifiant de l'application (Client ID), copié depuis l'onglet « Auth » du portail des développeurs de "
          "LinkedIn, puis Entrée.")
    client = input("Client ID : ").strip()
    print("Secret de l'application (Primary Client Secret). Il ne s'affiche pas pendant la frappe.")
    secret = getpass.getpass("Client Secret : ").strip()
    if not re.fullmatch(r"[A-Za-z0-9]{8,40}", client) or not secret:
        raise Arret("identifiant ou secret de l'application illisible, rien n'a changé.")
    erreur = identifiants.ecrire(CIBLE_LINKEDIN_APPLI, secret, client, "Application LinkedIn d'Ubi Cura, tutoriel 10")
    if erreur:
        raise Arret(f"le secret n'a pas pu être rangé (erreur Windows {erreur}).")
    print(f"Application rangée dans le gestionnaire d'identifiants de Windows, sous « {CIBLE_LINKEDIN_APPLI} ». "
          "Lancer maintenant linkedin-autoriser.")
    return 0


def cmd_linkedin_autoriser(_args) -> int:
    """Flux d'autorisation à trois parties. Le navigateur ouvre la page de LinkedIn, Lucas accepte, LinkedIn renvoie
    vers ce PC (adresse locale, rien ne passe par le site), le code est échangé contre un jeton de 60 jours."""
    import http.server
    import secrets
    import urllib.parse
    import webbrowser
    client, secret = identifiants.lire_compte(CIBLE_LINKEDIN_APPLI)
    if not (client and secret):
        raise Arret("aucune application LinkedIn rangée. Lancer d'abord linkedin-application (tutoriel 10, partie C).")
    etat = secrets.token_urlsafe(24)
    adresse = "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode(
        {"response_type": "code", "client_id": client, "redirect_uri": LINKEDIN_REDIRECTION, "state": etat,
         "scope": LINKEDIN_PORTEES})
    recu = {}

    class Retour(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if urllib.parse.urlparse(self.path).path != "/linkedin":
                self.send_response(404)
                self.end_headers()
                return
            recu.update({k: v[0] for k, v in q.items()})
            ok = "code" in recu and recu.get("state") == etat
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(("<p style='font:16px Segoe UI'>" + ("Autorisation reçue. Tu peux fermer cet onglet et "
                              "revenir à PowerShell." if ok else "Autorisation refusée ou interrompue. Revenir à "
                              "PowerShell.") + "</p>").encode("utf-8"))

        def log_message(self, *a):
            pass

    serveur = http.server.HTTPServer(("127.0.0.1", 8765), Retour)
    serveur.timeout = 5
    print("Le navigateur s'ouvre sur LinkedIn. Connecte-toi si besoin, puis clique sur « Allow » (Autoriser).")
    webbrowser.open(adresse)
    fin = dt.datetime.now() + dt.timedelta(minutes=5)
    while not recu and dt.datetime.now() < fin:
        serveur.handle_request()
    serveur.server_close()
    if not recu:
        raise Arret("aucune réponse de LinkedIn en cinq minutes. Relancer la commande.")
    if recu.get("state") != etat:
        raise Arret("réponse de LinkedIn qui ne correspond pas à cette demande, ignorée. Relancer la commande.")
    if "code" not in recu:
        raise Arret(f"LinkedIn n'a pas donné l'autorisation ({recu.get('error_description') or recu.get('error')}).")
    requests = _http()
    r = requests.post("https://www.linkedin.com/oauth/v2/accessToken", timeout=60,
                      data={"grant_type": "authorization_code", "code": recu["code"], "client_id": client,
                            "client_secret": secret, "redirect_uri": LINKEDIN_REDIRECTION})
    if r.status_code != 200:
        raise _erreur_http("LinkedIn", r)
    j = r.json()
    jeton, duree = j["access_token"], int(j.get("expires_in") or 0)
    u = requests.get(f"{LINKEDIN_API}/v2/userinfo", headers={"Authorization": f"Bearer {jeton}"}, timeout=60)
    if u.status_code != 200:
        raise _erreur_http("LinkedIn", u)
    auteur = f"urn:li:person:{u.json()['sub']}"
    erreur = identifiants.ecrire(CIBLE_LINKEDIN_JETON, jeton, auteur, "Autorisation de publier sur LinkedIn, tutoriel 10")
    if erreur:
        raise Arret(f"l'autorisation n'a pas pu être rangée (erreur Windows {erreur}).")
    expire = (dt.datetime.now().astimezone() + dt.timedelta(seconds=duree)).isoformat(timespec="seconds")
    etat_f = lire_json(ETAT, {})
    etat_f["linkedin"] = {"autorise_le": maintenant(), "expire_le": expire, "portees": j.get("scope")}
    ecrire_json(ETAT, etat_f)
    print(f"Autorisation de LinkedIn rangée dans le gestionnaire d'identifiants de Windows, valable jusqu'au "
          f"{dt.datetime.fromisoformat(expire):%d/%m/%Y}.")
    return 0


def cmd_verifier(_args) -> int:
    code = 0
    try:
        s = session_bluesky()
        print(f"Bluesky, connexion réussie pour @{s['handle']}.")
    except Arret as e:
        print(f"Bluesky, {e}")
        code = 20
    try:
        auteur, jeton = jeton_linkedin()
        r = _http().get(f"{LINKEDIN_API}/v2/userinfo", headers={"Authorization": f"Bearer {jeton}"}, timeout=60)
        if r.status_code != 200:
            raise _erreur_http("LinkedIn", r)
        print(f"LinkedIn, connexion réussie. {etat_comptes()['linkedin'][1]}.")
    except Arret as e:
        print(f"LinkedIn, {e}")
        code = 20
    return code


def cmd_ajouter(args) -> int:
    m = json.loads(Path(args.fichier).read_text(encoding="utf-8"))
    erreurs = controler_message(m)
    if (MESSAGES / f"{m.get('id')}.json").exists():
        erreurs.append(f"un message {m.get('id')} existe déjà")
    if erreurs:
        raise Arret("message refusé, " + " ; ".join(erreurs))
    FIGURES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(chemin_figure(m), FIGURES / f"{m['id']}.png")
    # cree_le à la microseconde, les messages ajoutés à la suite gardent leur ordre dans la liste
    m = {"sources": [], **m, "figure": f"{m['id']}.png", "statut": "a_relire",
         "cree_le": dt.datetime.now().astimezone().isoformat(timespec="microseconds"),
         "modifie_le": None, "publications": {}}
    enregistrer(m)
    print(f"Message {m['id']} ajouté, à relire dans l'onglet « Réseaux » de la fenêtre du courrier.")
    return 0


def cmd_apercu(args) -> int:
    m = lire_json(MESSAGES / f"{args.id}.json") or lire_json(Path(args.id))
    if not m:
        raise Arret(f"message {args.id} introuvable.")
    erreurs = controler_message(m)
    largeur, hauteur = taille_png(chemin_figure(m).read_bytes()) or (0, 0)
    sortie = {"controle": erreurs or "aucune erreur",
              "bluesky": {"graphemes": graphemes(m.get("bluesky") or ""),
                          "record": enregistrement_bluesky(m, {"$type": "blob", "ref": "(figure envoyée au moment de "
                                                               "la publication)"}, largeur, hauteur, dt.datetime.now())},
              "linkedin": {"caracteres": len(m.get("linkedin") or ""),
                           "corps": corps_linkedin(m, "urn:li:person:(auteur)", "urn:li:image:(figure)")}}
    print(json.dumps(sortie, ensure_ascii=False, indent=2))
    return 1 if erreurs else 0


def cmd_publier_programmes(_args) -> int:
    return publier_programmes()


def cmd_suivre(args) -> int:
    return suivre(essai=args.essai)


def suivre_discret() -> int:
    """Pour envoyer-programmes (tâche planifiée), n'écrit que ce qui a été fait ou a échoué."""
    try:
        return suivre(discret=True)
    except Arret as e:
        print(f"Abonnements Bluesky, {e}")
        return 20


# ---------------------------------------------------------------- choix des comptes à suivre
def fenetre_comptes(racine, c: dict, petite) -> None:
    """Fenêtre où Lucas coche les comptes que Bluesky suivra. Le choix est écrit dans la colonne valide de
    docs\\reseaux\\comptes_a_suivre.csv (date du choix). Un compte déjà suivi reste coché, il n'est jamais repris."""
    import tkinter as tk
    from tkinter import messagebox, ttk

    try:
        lignes = lire_comptes()
    except (Arret, OSError) as e:
        messagebox.showerror("Liste illisible", str(e), parent=racine)
        return
    faits = etat_suivis()
    coche = {x["did"]: bool(x["valide"]) for x in lignes}
    f = tk.Toplevel(racine)
    f.title("Comptes à suivre sur Bluesky")
    f.configure(bg=c["fond"])
    f.geometry("1080x720")
    f.transient(racine)
    cadre = ttk.Frame(f, padding=12)
    cadre.pack(fill="both", expand=True)
    tk.Label(cadre, justify="left", anchor="w", bg=c["fond"], fg=c["discret"], font=petite, wraplength=1040,
             text="Coche les comptes que le compte du projet suivra. Chaque compte a été vu sur Bluesky et rattaché à "
                  "son organisme ou à sa personne (colonne Vérification). Les abonnements partent "
                  f"{SUIVIS_PAR_JOUR} par jour au plus, avec la mise à jour quotidienne, sans message ni « j'aime ». "
                  "Double clic ou barre d'espace pour cocher ou décocher.").pack(fill="x", pady=(0, 8))
    tableau = ttk.Frame(cadre)
    tableau.pack(fill="both", expand=True)
    arbre = ttk.Treeview(tableau, columns=("case", "nom", "identifiant", "categorie", "etat"), show="headings",
                         selectmode="browse", height=18)
    for col, lib, larg in (("case", "Suivre", 60), ("nom", "Nom", 300), ("identifiant", "Identifiant", 260),
                           ("categorie", "Catégorie", 190), ("etat", "État", 150)):
        arbre.heading(col, text=lib, anchor="w")
        arbre.column(col, width=larg, anchor="w", stretch=col == "nom")
    defil = ttk.Scrollbar(tableau, orient="vertical", command=arbre.yview)
    arbre.configure(yscrollcommand=defil.set)
    defil.pack(side="right", fill="y")
    arbre.pack(side="left", fill="both", expand=True)
    detail = tk.Label(cadre, justify="left", anchor="w", bg=c["fond"], fg=c["encre"], font=petite, wraplength=1040,
                      height=3)
    detail.pack(fill="x", pady=(8, 0))
    par_did = {x["did"]: x for x in lignes}

    def remplir_arbre(choisi=None):
        arbre.delete(*arbre.get_children())
        for x in lignes:
            arbre.insert("", "end", iid=x["did"], values=(
                "☑" if coche[x["did"]] or x["did"] in faits else "☐", x["nom"], "@" + x["identifiant"], x["categorie"],
                faits.get(x["did"], "en attente" if coche[x["did"]] else "")))
        if choisi:
            arbre.selection_set(choisi)
            arbre.see(choisi)

    def montrer(_e=None):
        sel = arbre.selection()
        if sel:
            x = par_did[sel[0]]
            detail.configure(text=f"Pourquoi. {x['pourquoi']}\nVérification ({x['verifie_le']}). {x['verification']}")

    def basculer(_e=None):
        sel = arbre.selection()
        if not sel:
            return
        if sel[0] in faits:
            detail.configure(text="Ce compte est déjà suivi. Pour ne plus le suivre, se désabonner dans Bluesky.")
            return
        coche[sel[0]] = not coche[sel[0]]
        remplir_arbre(sel[0])
        montrer()

    def tout(valeur):
        for d in coche:
            if d not in faits:
                coche[d] = valeur
        remplir_arbre(arbre.selection()[0] if arbre.selection() else None)

    def enregistrer_choix():
        nouveaux = [x for x in lignes if coche[x["did"]] and not x["valide"]]
        retires = [x for x in lignes if not coche[x["did"]] and x["valide"]]
        if not (nouveaux or retires):
            f.destroy()
            return
        texte = (f"{len(nouveaux)} compte(s) ajouté(s) au choix, {len(retires)} retiré(s).\n\nLes abonnements partiront "
                 f"{SUIVIS_PAR_JOUR} par jour au plus, avec la mise à jour quotidienne. Enregistrer ce choix ?")
        if not messagebox.askyesno("Enregistrer le choix ?", texte, icon="question", default="yes", parent=f):
            return
        try:
            a_jour = lire_comptes()   # relue, la liste a pu changer depuis l'ouverture de la fenêtre
            jour = dt.date.today().isoformat()
            for x in a_jour:
                if x["did"] in coche:
                    x["valide"] = (x["valide"] or jour) if coche[x["did"]] else ""
            ecrire_comptes(a_jour)
        except (Arret, OSError) as e:
            messagebox.showerror("Choix non enregistré", str(e), parent=f)
            return
        f.destroy()

    boutons = ttk.Frame(cadre)
    boutons.pack(fill="x", pady=(8, 0))
    ttk.Button(boutons, text="Enregistrer le choix", style="Envoyer.TButton", command=enregistrer_choix).pack(
        side="left")
    ttk.Button(boutons, text="Tout cocher", command=lambda: tout(True)).pack(side="left", padx=(10, 0))
    ttk.Button(boutons, text="Tout décocher", command=lambda: tout(False)).pack(side="left", padx=(10, 0))
    ttk.Button(boutons, text="Fermer sans enregistrer", command=f.destroy).pack(side="right")
    arbre.bind("<<TreeviewSelect>>", montrer)
    arbre.bind("<Double-1>", basculer)
    arbre.bind("<space>", basculer)
    remplir_arbre(lignes[0]["did"] if lignes else None)
    montrer()
    f.grab_set()
    f.wait_window()


# ---------------------------------------------------------------- onglet de la fenêtre du courrier
def onglet(onglets, racine, c: dict, police, petite, zone_texte, remplir) -> dict:
    """Onglet « Réseaux » de la fenêtre du courrier. Renvoie {garder, rafraichir} pour la fenêtre."""
    import tkinter as tk
    from tkinter import messagebox, ttk

    page = ttk.Frame(onglets, padding=12)
    onglets.add(page, text="Réseaux")
    gauche = ttk.Frame(page)
    gauche.pack(side="left", fill="y")
    liste = ttk.Treeview(gauche, columns=("titre",), show="headings", selectmode="browse", height=9)
    liste.heading("titre", text="Messages à relire")
    liste.column("titre", width=330)
    liste.pack(fill="x")
    ttk.Label(gauche, text="Journal des publications", style="Discret.TLabel").pack(anchor="w", pady=(12, 2))
    pub = ttk.Treeview(gauche, columns=("date", "reseau", "titre"), show="headings", selectmode="browse", height=6)
    for col, lib, larg in (("date", "Date", 92), ("reseau", "Réseau", 70), ("titre", "Message", 168)):
        pub.heading(col, text=lib, anchor="w")
        pub.column(col, width=larg, anchor="w")
    pub.pack(fill="both", expand=True)
    ttk.Label(gauche, text="Comptes à suivre sur Bluesky", style="Discret.TLabel").pack(anchor="w", pady=(12, 2))
    resume_suivis = tk.Label(gauche, justify="left", anchor="w", wraplength=330, bg=c["fond"], fg=c["discret"],
                             font=petite)
    resume_suivis.pack(fill="x")

    def resumer_suivis():
        try:
            lignes = lire_comptes()
        except (Arret, OSError) as e:
            resume_suivis.configure(text=f"Liste illisible ({e}).")
            return
        faits = etat_suivis()
        coches = [x for x in lignes if x["valide"]]
        resume_suivis.configure(text=f"{len(lignes)} comptes vérifiés, {len(coches)} cochés, "
                                     f"{sum(1 for x in lignes if x['did'] in faits)} déjà suivis. "
                                     f"{SUIVIS_PAR_JOUR} abonnements par jour au plus.")

    def choisir_comptes():
        fenetre_comptes(racine, c, petite)
        resumer_suivis()

    ttk.Button(gauche, text="Choisir les comptes à suivre", command=choisir_comptes).pack(anchor="w", pady=(4, 0))
    resumer_suivis()

    droite = ttk.Frame(page, padding=(16, 0, 0, 0))
    droite.pack(side="left", fill="both", expand=True)
    droite.columnconfigure(0, weight=1)
    tete_msg = ttk.Frame(droite)
    tete_msg.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
    motif = tk.Label(tete_msg, justify="left", anchor="w", wraplength=700, bg=c["fond"], fg=c["ocre"], font=petite)
    motif.pack(fill="x")
    sources = tk.Label(tete_msg, justify="left", anchor="w", wraplength=700, bg=c["fond"], fg=c["discret"],
                       font=petite)
    sources.pack(fill="x", pady=(2, 0))
    compteurs, zones = {}, {}
    for i, (r, haut) in enumerate((("linkedin", 9), ("bluesky", 4))):
        tete = ttk.Frame(droite)
        tete.grid(row=1 + 2 * i, column=0, columnspan=2, sticky="ew", pady=(4 if i else 0, 2))
        ttk.Label(tete, text=RESEAUX[r] + (", version longue" if r == "linkedin" else ", version courte"),
                  font=("Segoe UI Semibold", 10)).pack(side="left")
        compteurs[r] = tk.Label(tete, bg=c["fond"], fg=c["discret"], font=petite)
        compteurs[r].pack(side="right")
        cadre, t = zone_texte(droite, False)
        t.configure(height=haut)
        cadre.grid(row=2 + 2 * i, column=0, columnspan=2, sticky="nsew")
        zones[r] = t
    droite.rowconfigure(2, weight=2)
    droite.rowconfigure(4, weight=1)
    bas = ttk.Frame(droite)
    bas.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
    apercu = tk.Label(bas, bg=c["panneau"], relief="flat", width=36, height=9)
    apercu.pack(side="left", anchor="n")
    cote = ttk.Frame(bas, padding=(12, 0, 0, 0))
    cote.pack(side="left", fill="both", expand=True)
    tete_alt = ttk.Frame(cote)
    tete_alt.pack(fill="x")
    ttk.Label(tete_alt, text="Texte de remplacement de la figure, lu aux personnes aveugles (obligatoire)",
              style="Discret.TLabel").pack(side="left")
    compteurs["alt"] = tk.Label(tete_alt, bg=c["fond"], fg=c["discret"], font=petite)
    compteurs["alt"].pack(side="right")
    cadre_alt, alt = zone_texte(cote, False)
    alt.configure(height=5)
    cadre_alt.pack(fill="both", expand=True)
    ligne_reseaux = ttk.Frame(droite)
    ligne_reseaux.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))
    ttk.Label(ligne_reseaux, text="Publier sur", style="Discret.TLabel").pack(side="left", padx=(0, 8))
    choix = {r: tk.BooleanVar(value=True) for r in RESEAUX}
    for r in RESEAUX:
        ttk.Checkbutton(ligne_reseaux, text=RESEAUX[r], variable=choix[r]).pack(side="left", padx=(0, 8))
    comptes = tk.Label(ligne_reseaux, justify="left", anchor="w", bg=c["fond"], fg=c["discret"], font=petite)
    comptes.pack(side="left", padx=(16, 0))
    boutons = ttk.Frame(droite)
    boutons.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(8, 0))
    ttk.Label(boutons, text="Publier le", style="Discret.TLabel").pack(side="left")
    champ_date = ttk.Entry(boutons, font=police, width=17)
    champ_date.pack(side="left", padx=(6, 10))
    droite.bind("<Configure>", lambda e: [motif.configure(wraplength=max(300, e.width - 24)),
                                          comptes.configure(wraplength=max(200, e.width - 300)),
                                          sources.configure(wraplength=max(300, e.width - 24))])
    etat = {"courant": None, "image": None}

    def compter(_e=None):
        b = zones["bluesky"].get("1.0", "end").rstrip("\n")
        n = graphemes(b)
        compteurs["bluesky"].configure(text=f"{n} caractères sur {BLUESKY_GRAPHEMES}",
                                       fg=c["cuivre"] if n > BLUESKY_GRAPHEMES else c["discret"])
        n = len(zones["linkedin"].get("1.0", "end").rstrip("\n"))
        compteurs["linkedin"].configure(text=f"{n} caractères sur {LINKEDIN_CARACTERES}",
                                        fg=c["cuivre"] if n > LINKEDIN_CARACTERES else c["discret"])
        n = len(alt.get("1.0", "end").strip())
        compteurs["alt"].configure(text=f"{n} caractères" if n else "à écrire",
                                   fg=c["cuivre"] if not n or n > ALT_CARACTERES else c["discret"])

    for t in (*zones.values(), alt):
        t.bind("<KeyRelease>", compter)

    def date_affichee(m):
        q = lire_date(m.get("envoi_prevu"))
        return q.strftime("%d/%m/%Y %H:%M") if q else ""

    def a_relire():
        return [m for m in messages() if m.get("statut") in ("a_relire", "plus_tard", "programme")]

    def garder():
        m = etat["courant"]
        if not m:
            return
        m = lire_json(MESSAGES / f"{m['id']}.json") or m
        nouveau = {r: zones[r].get("1.0", "end").rstrip() for r in RESEAUX} | {
            "alt": alt.get("1.0", "end").strip(), "reseaux": [r for r in RESEAUX if choix[r].get()]}
        avant = {r: (m.get(r) or "").rstrip() for r in RESEAUX} | {"alt": (m.get("alt") or "").strip(),
                                                                   "reseaux": [r for r in RESEAUX if r in m["reseaux"]]}
        quand = lire_date(champ_date.get())
        prevu = quand.strftime("%Y-%m-%dT%H:%M") if quand else None
        vide = not champ_date.get().strip()
        if nouveau != avant or (prevu and prevu != m.get("envoi_prevu")) or (vide and m.get("envoi_prevu")):
            m.update(nouveau, modifie_le=maintenant())
            if prevu:
                m["envoi_prevu"] = prevu
            elif vide:
                m.pop("envoi_prevu", None)
            if m.get("statut") == "programme":   # un message changé après le clic doit être validé de nouveau
                m["statut"] = "a_relire"
            enregistrer(m)
        etat["courant"] = m

    def afficher(_evt=None):
        garder()
        sel = liste.selection()
        m = lire_json(MESSAGES / f"{sel[0]}.json") if sel else None
        etat["courant"] = m
        for t in (*zones.values(), alt):
            remplir(t, "")
        champ_date.delete(0, "end")
        motif.configure(text="")
        sources.configure(text="")
        apercu.configure(image="", text="")
        if not m:
            compter()
            return
        for r in RESEAUX:
            remplir(zones[r], m.get(r) or "")
            choix[r].set(r in m["reseaux"])
        remplir(alt, m.get("alt") or "")
        champ_date.insert(0, date_affichee(m))
        texte = f"Pourquoi ce message. {m['motif']}"
        deja = [RESEAUX[r] for r in (m.get("publications") or {})]
        if deja:
            texte += f"\nDéjà publié sur {', '.join(deja)}, ce réseau ne le recevra pas une seconde fois."
        if m.get("statut") == "plus_tard":
            texte += "\nGardé pour plus tard."
        if m.get("statut") == "programme":
            texte += f"\nPublication programmée le {date_affichee(m).replace(' ', ' à ')}, validée par ton clic."
        elif m.get("envoi_prevu"):
            texte += f"\nDate de publication proposée, le {date_affichee(m).replace(' ', ' à ')}."
        motif.configure(text=texte)
        src = "Lien " + m["lien"] + (". Sources " + " ; ".join(m["sources"]) if m.get("sources") else "")
        sources.configure(text=src)
        f = chemin_figure(m)
        if f.is_file():
            try:
                img = tk.PhotoImage(file=str(f))
                k = max(1, -(-img.width() // 260), -(-img.height() // 170))
                etat["image"] = img.subsample(k, k)
                apercu.configure(image=etat["image"], width=0, height=0)
            except tk.TclError:
                apercu.configure(text="Figure illisible")
        compter()

    def rafraichir(choisi=None):
        liste.delete(*liste.get_children())
        for m in a_relire():
            tete = ("◷ " if m["statut"] == "plus_tard" else
                    f"⏲ {date_affichee(m)} " if m["statut"] == "programme" else "")
            liste.insert("", "end", iid=m["id"], values=(tete + m["titre"],))
        enfants = liste.get_children()
        if enfants:
            liste.selection_set(choisi if choisi in enfants else enfants[0])
        else:
            etat["courant"] = None
            afficher()
        pub.delete(*pub.get_children())
        for i, j in enumerate(reversed(journal())):
            pub.insert("", "end", iid=str(i), values=(j["date"][:10], RESEAUX.get(j["reseau"], j["reseau"]),
                                                      j["titre"]))
        e = etat_comptes()
        comptes.configure(text="   ·   ".join(t for _, t in e.values()))
        resumer_suivis()

    def changer_statut(statut):
        m = etat["courant"]
        if not m:
            return
        garder()
        m = lire_json(MESSAGES / f"{m['id']}.json")
        m.update(statut=statut, modifie_le=maintenant())
        enregistrer(m)
        etat["courant"] = None
        rafraichir(m["id"] if statut == "plus_tard" else None)

    def cliquer_publier():
        if not etat["courant"]:
            return
        garder()
        m = lire_json(MESSAGES / f"{etat['courant']['id']}.json")
        erreurs = controler_message(m)
        if erreurs:
            messagebox.showerror("Message à corriger", "Rien n'est publié.\n\n" + "\n".join(erreurs), parent=racine)
            return
        restants = [r for r in m["reseaux"] if r not in (m.get("publications") or {})]
        relies = etat_comptes()
        absents = [relies[r][1] for r in restants if not relies[r][0]]
        if absents:
            messagebox.showerror("Compte non relié", "Rien n'est publié.\n\n" + "\n".join(absents), parent=racine)
            return
        noms = " et ".join(RESEAUX[r] for r in restants)
        saisie = champ_date.get().strip()
        quand = lire_date(saisie) if saisie else None
        if saisie and quand is None:
            messagebox.showerror("Date illisible", "Écrire la date sous la forme 03/11/2026 09:30, ou laisser le "
                                 "champ vide pour publier tout de suite.", parent=racine)
            return
        if quand and quand > dt.datetime.now():
            if not messagebox.askyesno("Programmer ce message ?",
                                       f"Publier « {m['titre']} »\nsur {noms}\nle "
                                       f"{quand.strftime('%d/%m/%Y à %H:%M')} ?\n\nUn changement du texte, de la "
                                       "figure, de son texte de remplacement ou des réseaux avant cette heure annule "
                                       "la programmation.", icon="question", default="no", parent=racine):
                return
            texte = programmer(m, quand)
            etat["courant"] = None
            rafraichir(m["id"])
            messagebox.showinfo("Publication programmée", texte, parent=racine)
            return
        if not messagebox.askyesno("Publier ce message ?", f"Publier « {m['titre']} »\nsur {noms}, tout de suite ?\n\n"
                                   "Le message sera public.", icon="question", default="no", parent=racine):
            return
        racine.config(cursor="watch")
        racine.update()
        try:
            valider(m)
            enregistrer(m)
            texte = publier(m)
        except Arret as e:
            messagebox.showerror("Message non publié", str(e), parent=racine)
            rafraichir(m["id"])
            return
        finally:
            racine.config(cursor="")
        etat["courant"] = None
        rafraichir()
        messagebox.showinfo("Message publié", texte, parent=racine)

    ttk.Button(boutons, text="Publier", style="Envoyer.TButton", command=cliquer_publier).pack(side="left")
    ttk.Button(boutons, text="Garder pour plus tard", command=lambda: changer_statut("plus_tard")).pack(
        side="left", padx=(10, 0))
    ttk.Button(boutons, text="Écarter", command=lambda: changer_statut("ecarte")).pack(side="left", padx=(10, 0))
    ttk.Button(boutons, text="Annuler la programmation", command=lambda: changer_statut("a_relire")).pack(
        side="left", padx=(10, 0))

    def ouvrir_publication(_e=None):
        import webbrowser
        sel = pub.selection()
        if sel:
            j = list(reversed(journal()))[int(sel[0])]
            if j.get("adresse", "").startswith("https://"):
                webbrowser.open(j["adresse"])

    liste.bind("<<TreeviewSelect>>", afficher)
    pub.bind("<Double-1>", ouvrir_publication)
    rafraichir()
    return {"page": page, "garder": garder, "rafraichir": lambda: rafraichir(liste.selection()[0]
                                                                           if liste.selection() else None),
            "a_relire": a_relire}


def main() -> int:
    ap = argparse.ArgumentParser(description="Messages pour LinkedIn et Bluesky (tutoriels 10 et 11).")
    sous = ap.add_subparsers(dest="commande", required=True)
    sous.add_parser("bluesky-mot-de-passe").set_defaults(f=cmd_bluesky_mot_de_passe)
    sous.add_parser("linkedin-application").set_defaults(f=cmd_linkedin_application)
    sous.add_parser("linkedin-autoriser").set_defaults(f=cmd_linkedin_autoriser)
    sous.add_parser("verifier").set_defaults(f=cmd_verifier)
    p = sous.add_parser("ajouter")
    p.add_argument("fichier")
    p.set_defaults(f=cmd_ajouter)
    p = sous.add_parser("apercu")
    p.add_argument("id")
    p.set_defaults(f=cmd_apercu)
    sous.add_parser("publier-programmes").set_defaults(f=cmd_publier_programmes)
    p = sous.add_parser("suivre")
    p.add_argument("--essai", action="store_true", help="dit ce qui serait fait, sans rien envoyer")
    p.set_defaults(f=cmd_suivre)
    args = ap.parse_args()
    try:
        return args.f(args)
    except Arret as e:
        print(f"Arrêt, {e}")
        return 20


if __name__ == "__main__":
    sys.exit(main())
