"""Courrier de contact@ubicura.fr, relevé chaque matin, brouillons relus dans une fenêtre et envoyés seulement par un
clic de Lucas sur « Envoyer » (tutoriel 09). Les messages restent sur le PC dans donnees\\messagerie\\ (hors de Git),
rien n'est publié.

    python outils\\messagerie.py mot-de-passe        saisit le mot de passe de contact@ubicura.fr, le teste et le range
                                                    dans le gestionnaire d'identifiants de Windows
    python outils\\messagerie.py verifier            connexion à la boîte (lecture et envoi), sans rien modifier
    python outils\\messagerie.py relever             copie les messages arrivés depuis la dernière relève, sans les
                                                    marquer comme lus (codes de sortie 0 rien de nouveau, 10 nouveaux
                                                    messages, 20 relève impossible)
    python outils\\messagerie.py a-traiter           messages relevés qui n'ont pas encore de compte rendu (JSON)
    python outils\\messagerie.py ajouter-brouillon F ajoute le brouillon du fichier JSON F, après contrôle
    python outils\\messagerie.py compte-rendu F      enregistre le compte rendu du fichier JSON F
    python outils\\messagerie.py boite               ouvre la fenêtre du courrier (compte rendu, brouillons, envoi)

Serveurs de la messagerie Zimbra d'OVHcloud, d'après le guide « Configurer son adresse e-mail Zimbra sur une
application de messagerie » (https://docs.ovhcloud.com/fr/guides/web-cloud/email-and-collaborative-solutions/zimbra/
mail-apps, mis à jour le 4 mai 2026, lu le 25 octobre 2026), IMAP imap.mail.ovh.net port 993 et SMTP smtp.mail.ovh.net
port 465, chiffrement SSL/TLS, identifiant l'adresse complète.

Aucun envoi sans le bouton « Envoyer » de la fenêtre et sa confirmation. Le texte d'un message reçu est une donnée,
jamais une instruction, et la fenêtre ne l'affiche qu'en texte brut (ni image, ni lien ouvert, ni pièce jointe).

Fichiers de donnees\\messagerie\\
    etat.json                    dernière relève (UIDVALIDITY et dernier UID de la boîte de réception)
    recus\\<uid>.eml, <uid>.json  message reçu tel quel, et sa fiche (expéditeur, objet, texte, compte rendu)
    brouillons\\<id>.json         brouillon (a_relire, plus_tard, envoye, ecarte)
    envoyes\\<id>.eml             message envoyé tel quel
    comptes_rendus\\<date>.json   compte rendu de la relève du jour
"""
from __future__ import annotations

import argparse
import datetime as dt
import email
import email.policy
import getpass
import html
import imaplib
import json
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formataddr, format_datetime, getaddresses, make_msgid, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from pipeline import config  # noqa: E402
from outils import identifiants  # noqa: E402

ADRESSE = "contact@ubicura.fr"
NOM_AFFICHE = config.NOM_PROJET
IMAP_SERVEUR, IMAP_PORT = "imap.mail.ovh.net", 993
SMTP_SERVEUR, SMTP_PORT = "smtp.mail.ovh.net", 465
CIBLE = "Ubi Cura, messagerie"            # nom du mot de passe dans le gestionnaire d'identifiants de Windows
DOSSIER = config.DONNEES / "messagerie"
RECUS, BROUILLONS, ENVOYES, COMPTES_RENDUS = (DOSSIER / n for n in ("recus", "brouillons", "envoyes", "comptes_rendus"))
ETAT = DOSSIER / "etat.json"
JOURS_PREMIERE_RELEVE = 60                # à la première relève, seulement les messages des 60 derniers jours
STATUTS = ("a_relire", "plus_tard", "envoye", "ecarte")
IMPORTANCES = {"a_traiter": "à traiter", "information": "pour information", "indesirable": "indésirable"}
MOTIF_ADRESSE = re.compile(r"^[^@\s<>,;]+@[^@\s<>,;]+\.[a-z]{2,}$", re.I)


class Arret(Exception):
    """Arrêt propre, avec un message pour Lucas."""


# ---------------------------------------------------------------- connexion
def mot_de_passe() -> str:
    mdp = identifiants.lire(CIBLE)
    if not mdp:
        raise Arret("aucun mot de passe de contact@ubicura.fr dans le gestionnaire d'identifiants de Windows. Suivre "
                    "le tutoriel 09, partie A.")
    return mdp


def imap(mdp: str | None = None) -> imaplib.IMAP4_SSL:
    try:
        m = imaplib.IMAP4_SSL(IMAP_SERVEUR, IMAP_PORT, ssl_context=ssl.create_default_context(), timeout=60)
    except OSError as e:
        raise Arret(f"le serveur de messagerie ne répond pas ({e.__class__.__name__}). Réessayer plus tard.") from e
    try:
        m.login(ADRESSE, mdp or mot_de_passe())
    except imaplib.IMAP4.error as e:
        raise Arret("le serveur refuse le mot de passe de contact@ubicura.fr. S'il a changé, le ranger de nouveau "
                    "(tutoriel 09, partie A).") from e
    return m


def smtp(mdp: str | None = None) -> smtplib.SMTP_SSL:
    try:
        s = smtplib.SMTP_SSL(SMTP_SERVEUR, SMTP_PORT, context=ssl.create_default_context(), timeout=60)
        s.login(ADRESSE, mdp or mot_de_passe())
    except smtplib.SMTPAuthenticationError as e:
        raise Arret("le serveur d'envoi refuse le mot de passe de contact@ubicura.fr (tutoriel 09, partie A).") from e
    except (OSError, smtplib.SMTPException) as e:
        raise Arret(f"le serveur d'envoi ne répond pas ({e.__class__.__name__}). Réessayer plus tard.") from e
    return s


def dossier_envoyes(m: imaplib.IMAP4_SSL) -> str | None:
    """Dossier des messages envoyés de la boîte (attribut \\Sent, sinon un nom usuel)."""
    _, lignes = m.list()
    noms = []
    for brut in lignes or []:
        ligne = brut.decode("utf-8", "replace")
        nom = ligne.rsplit(' "/" ', 1)[-1].strip().strip('"')
        if "\\Sent" in ligne:
            return nom
        noms.append(nom)
    return next((n for n in ("Sent", "Envoyés", "Sent Items", "Éléments envoyés") if n in noms), None)


# ---------------------------------------------------------------- fichiers
def lire_json(f: Path, defaut=None):
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else defaut


def ecrire_json(f: Path, contenu) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(contenu, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(f)


def maintenant() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def recus() -> list[dict]:
    return sorted((lire_json(f) for f in RECUS.glob("*.json")), key=lambda r: r.get("date") or "", reverse=True)


def brouillons() -> list[dict]:
    return sorted((lire_json(f) for f in BROUILLONS.glob("*.json")), key=lambda b: b.get("cree_le") or "")


# ---------------------------------------------------------------- lecture d'un message
class _Texte(HTMLParser):
    """Texte d'un message HTML, sans balise, sans image ni script."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.morceaux, self._ignore = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self._ignore += 1
        elif tag in ("br", "p", "div", "tr", "li", "h1", "h2", "h3"):
            self.morceaux.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head") and self._ignore:
            self._ignore -= 1

    def handle_data(self, data):
        if not self._ignore:
            self.morceaux.append(data)


def texte_du_message(msg: email.message.EmailMessage) -> str:
    corps = msg.get_body(preferencelist=("plain", "html"))
    if corps is None:
        return ""
    try:
        contenu = corps.get_content()
    except (LookupError, KeyError):
        contenu = corps.get_payload(decode=True).decode("utf-8", "replace")
    if corps.get_content_type() == "text/html":
        p = _Texte()
        p.feed(contenu)
        contenu = html.unescape("".join(p.morceaux))
    contenu = re.sub(r"[ \t\r\f\v]+\n", "\n", contenu)
    return re.sub(r"\n{3,}", "\n\n", contenu).strip()


def fiche(uid: int, brut: bytes) -> dict:
    msg = email.message_from_bytes(brut, policy=email.policy.default)
    try:
        date = parsedate_to_datetime(msg["Date"]).astimezone().isoformat(timespec="seconds") if msg["Date"] else None
    except (TypeError, ValueError):
        date = None
    pj = [p.get_filename() or p.get_content_type() for p in msg.iter_attachments()]
    return {"uid": uid, "date": date, "de": str(msg["From"] or ""), "a": str(msg["To"] or ""),
            "cc": str(msg["Cc"] or ""), "objet": str(msg["Subject"] or ""), "message_id": msg["Message-ID"],
            "references": str(msg["References"] or ""), "repondre_a": str(msg["Reply-To"] or ""),
            "pieces_jointes": pj, "texte": texte_du_message(msg), "releve_le": maintenant(), "compte_rendu": None}


# ---------------------------------------------------------------- commandes
def cmd_mot_de_passe(_args) -> int:
    print("Mot de passe de contact@ubicura.fr (il ne s'affiche pas pendant la frappe, puis Entrée).")
    mdp = getpass.getpass("Mot de passe : ").strip()
    if not mdp:
        raise Arret("aucun mot de passe saisi, rien n'a changé.")
    imap(mdp).logout()
    smtp(mdp).quit()
    erreur = identifiants.ecrire(CIBLE, mdp, ADRESSE, "Mot de passe de la boîte contact@ubicura.fr, tutoriel 09")
    if erreur:
        raise Arret(f"le mot de passe n'a pas pu être rangé (erreur Windows {erreur}).")
    print(f"Mot de passe accepté par le serveur et rangé dans le gestionnaire d'identifiants de Windows, sous « {CIBLE} ».")
    return 0


def cmd_verifier(_args) -> int:
    m = imap()
    _, donnees = m.select("INBOX", readonly=True)
    nb = int(donnees[0])
    envoyes = dossier_envoyes(m)
    m.logout()
    smtp().quit()
    print(f"Connexion réussie. Boîte de réception, {nb} messages. Dossier des envoyés, {envoyes or 'introuvable'}.")
    return 0


def cmd_relever(_args) -> int:
    try:
        m = imap()
    except Arret as e:
        print(f"Relève impossible, {e}")
        return 20
    etat = lire_json(ETAT, {})
    typ, donnees = m.select("INBOX", readonly=True)          # lecture seule, les messages restent « non lus »
    if typ != "OK":
        print("Relève impossible, la boîte de réception n'a pas pu être ouverte.")
        return 20
    validite = int(m.untagged_responses.get("UIDVALIDITY", [b"0"])[0])
    dernier = etat.get("dernier_uid", 0) if etat.get("uidvalidite") == validite else 0
    if dernier:
        _, res = m.uid("search", None, f"UID {dernier + 1}:*")
    else:
        depuis = (dt.date.today() - dt.timedelta(days=JOURS_PREMIERE_RELEVE)).strftime("%d-%b-%Y")
        _, res = m.uid("search", None, f"SINCE {depuis}")
    uids = sorted(u for u in (int(x) for x in (res[0] or b"").split()) if u > dernier)
    RECUS.mkdir(parents=True, exist_ok=True)
    nouveaux = []
    for uid in uids:
        if (RECUS / f"{uid}.json").exists():
            continue
        _, morceaux = m.uid("fetch", str(uid), "(BODY.PEEK[])")
        brut = next((p[1] for p in morceaux if isinstance(p, tuple)), None)
        if brut is None:
            continue
        (RECUS / f"{uid}.eml").write_bytes(brut)
        f = fiche(uid, brut)
        ecrire_json(RECUS / f"{uid}.json", f)
        nouveaux.append(f)
    m.logout()
    ecrire_json(ETAT, {"uidvalidite": validite, "dernier_uid": max([dernier, *uids]), "derniere_releve": maintenant()})
    if not nouveaux:
        print("Aucun nouveau message.")
        return 0
    print(f"{len(nouveaux)} nouveau(x) message(s).")
    for f in nouveaux:
        print(f"  {f['uid']}  {(f['date'] or '')[:16]}  {f['de']}  {f['objet']}")
    return 10


def cmd_a_traiter(_args) -> int:
    attente = [{k: r[k] for k in ("uid", "date", "de", "a", "cc", "objet", "pieces_jointes", "texte")}
               for r in recus() if not r.get("compte_rendu")]
    print(json.dumps(attente, ensure_ascii=False, indent=2))
    return 0


def controler_brouillon(b: dict) -> list[str]:
    erreurs = []
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,80}", str(b.get("id", ""))):
        erreurs.append("id en minuscules, chiffres et tirets")
    for champ in ("a", "cc"):
        if not isinstance(b.get(champ, []), list):
            erreurs.append(f"{champ} doit être une liste d'adresses")
    if not b.get("a"):
        erreurs.append("au moins un destinataire")
    for adr in b.get("a", []) + b.get("cc", []):
        if not MOTIF_ADRESSE.match(adr):
            erreurs.append(f"adresse invalide {adr!r}")
    for champ in ("objet", "corps", "motif"):
        if not str(b.get(champ, "")).strip():
            erreurs.append(f"{champ} manquant")
    if b.get("en_reponse_a") is not None and not (RECUS / f"{b['en_reponse_a']}.json").exists():
        erreurs.append(f"message d'origine {b['en_reponse_a']} introuvable")
    inconnus = set(b) - {"id", "a", "cc", "objet", "corps", "motif", "sources", "en_reponse_a"}
    if inconnus:
        erreurs.append(f"champs inconnus {sorted(inconnus)}")
    return erreurs


def cmd_ajouter_brouillon(args) -> int:
    b = json.loads(Path(args.fichier).read_text(encoding="utf-8"))
    erreurs = controler_brouillon(b)
    if (BROUILLONS / f"{b.get('id')}.json").exists():
        erreurs.append(f"un brouillon {b.get('id')} existe déjà")
    if erreurs:
        raise Arret("brouillon refusé, " + " ; ".join(erreurs))
    b = {"cc": [], "sources": [], "en_reponse_a": None, **b, "statut": "a_relire", "cree_le": maintenant(),
         "modifie_le": None, "envoye_le": None, "message_id": None}
    ecrire_json(BROUILLONS / f"{b['id']}.json", b)
    print(f"Brouillon {b['id']} ajouté, à relire dans la fenêtre du courrier.")
    return 0


def cmd_compte_rendu(args) -> int:
    cr = json.loads(Path(args.fichier).read_text(encoding="utf-8"))
    erreurs = [] if str(cr.get("resume", "")).strip() else ["resume manquant"]
    for e in cr.get("messages", []):
        if not (RECUS / f"{e.get('uid')}.json").exists():
            erreurs.append(f"message {e.get('uid')} introuvable")
        if e.get("importance") not in IMPORTANCES:
            erreurs.append(f"importance de {e.get('uid')} parmi {sorted(IMPORTANCES)}")
        if not str(e.get("resume", "")).strip():
            erreurs.append(f"résumé de {e.get('uid')} manquant")
    if erreurs:
        raise Arret("compte rendu refusé, " + " ; ".join(erreurs))
    jour = dt.date.today().isoformat()
    cr = {"date": jour, "cree_le": maintenant(), **cr}
    ecrire_json(COMPTES_RENDUS / f"{jour}.json", cr)
    for e in cr.get("messages", []):
        f = RECUS / f"{e['uid']}.json"
        r = lire_json(f)
        r["compte_rendu"] = {k: e.get(k) for k in ("importance", "resume", "suite")} | {"date": jour}
        ecrire_json(f, r)
    print(f"Compte rendu du {jour} enregistré ({len(cr.get('messages', []))} message(s)).")
    return 0


# ---------------------------------------------------------------- envoi (seulement depuis la fenêtre)
def composer(b: dict) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((NOM_AFFICHE, ADRESSE))
    msg["To"] = ", ".join(b["a"])
    if b.get("cc"):
        msg["Cc"] = ", ".join(b["cc"])
    msg["Subject"] = b["objet"]
    msg["Date"] = format_datetime(dt.datetime.now().astimezone())
    msg["Message-ID"] = make_msgid(domain="ubicura.fr")
    if b.get("en_reponse_a") is not None:
        origine = lire_json(RECUS / f"{b['en_reponse_a']}.json")
        if origine.get("message_id"):
            msg["In-Reply-To"] = origine["message_id"]
            msg["References"] = (origine.get("references", "") + " " + origine["message_id"]).strip()
    msg.set_content(b["corps"])
    return msg


def envoyer(b: dict) -> str:
    """Envoie le brouillon, en garde une copie dans le dossier des envoyés de la boîte et sur le PC."""
    erreurs = controler_brouillon({k: v for k, v in b.items() if k in
                                   {"id", "a", "cc", "objet", "corps", "motif", "sources", "en_reponse_a"}})
    if erreurs:
        raise Arret("envoi refusé, " + " ; ".join(erreurs))
    msg = composer(b)
    s = smtp()
    try:
        s.send_message(msg)
    finally:
        s.quit()
    brut = msg.as_bytes()
    ENVOYES.mkdir(parents=True, exist_ok=True)
    (ENVOYES / f"{b['id']}.eml").write_bytes(brut)
    remarque = ""
    try:
        m = imap()
        dossier = dossier_envoyes(m)
        if dossier:
            m.append(f'"{dossier}"', "\\Seen", imaplib.Time2Internaldate(dt.datetime.now().astimezone()), brut)
        if b.get("en_reponse_a") is not None:
            m.select("INBOX")
            m.uid("store", str(b["en_reponse_a"]), "+FLAGS", "(\\Answered)")
        m.logout()
    except (Arret, imaplib.IMAP4.error, OSError):
        remarque = " (copie dans le dossier des envoyés de la boîte impossible, la copie sur le PC est gardée)"
    b.update(statut="envoye", envoye_le=maintenant(), message_id=msg["Message-ID"])
    ecrire_json(BROUILLONS / f"{b['id']}.json", b)
    return f"Message envoyé à {', '.join(b['a'])}{remarque}."


# ---------------------------------------------------------------- fenêtre
COULEURS = {"fond": "#F4F4F1", "panneau": "#FFFFFF", "encre": "#1C2028", "discret": "#5D6371", "ligne": "#E2E3E6",
            "bleu": "#1D4D87", "cuivre": "#83451E", "ocre": "#8A5A0E"}


def cmd_boite(args) -> int:
    import tkinter as tk
    from tkinter import messagebox, ttk

    c = COULEURS
    racine = tk.Tk()
    racine.title(f"{NOM_AFFICHE}, courrier de {ADRESSE}")
    racine.geometry("1180x760")
    racine.minsize(900, 560)
    racine.configure(bg=c["fond"])
    style = ttk.Style(racine)
    style.theme_use("clam")
    police, petite, titre = ("Segoe UI", 10), ("Segoe UI", 9), ("Segoe UI Semibold", 15)
    style.configure(".", background=c["fond"], foreground=c["encre"], font=police)
    style.configure("TNotebook", background=c["fond"], borderwidth=0)
    style.configure("TNotebook.Tab", padding=(16, 6), background=c["fond"], foreground=c["discret"])
    style.map("TNotebook.Tab", background=[("selected", c["panneau"])], foreground=[("selected", c["bleu"])])
    style.configure("Treeview", background=c["panneau"], fieldbackground=c["panneau"], rowheight=26, borderwidth=0)
    style.configure("Treeview.Heading", background=c["fond"], foreground=c["discret"], font=petite, relief="flat")
    style.map("Treeview", background=[("selected", "#DCE6F2")], foreground=[("selected", c["encre"])])
    style.configure("Envoyer.TButton", background=c["cuivre"], foreground="#FFFFFF", padding=(18, 7),
                    font=("Segoe UI Semibold", 10), borderwidth=0)
    style.map("Envoyer.TButton", background=[("active", "#6A3716"), ("disabled", "#C9B8AC")])
    style.configure("TButton", padding=(14, 7), background=c["panneau"], borderwidth=1)
    style.configure("Discret.TLabel", foreground=c["discret"], font=petite)
    style.configure("Titre.TLabel", font=titre, foreground=c["encre"])
    style.configure("TEntry", fieldbackground=c["panneau"])

    entete = ttk.Frame(racine, padding=(20, 16, 20, 8))
    entete.pack(fill="x")
    ttk.Label(entete, text=f"Courrier du {dt.date.today().strftime('%d/%m/%Y')}", style="Titre.TLabel").pack(anchor="w")
    bilan = ttk.Label(entete, style="Discret.TLabel")
    bilan.pack(anchor="w", pady=(2, 0))
    cr = lire_json(COMPTES_RENDUS / f"{dt.date.today().isoformat()}.json")
    resume = tk.Label(entete, text=(cr or {}).get("resume") or "Pas encore de compte rendu ce matin.", justify="left",
                      wraplength=1100, bg=c["fond"], fg=c["encre"], font=police, anchor="w")
    resume.pack(anchor="w", fill="x", pady=(8, 0))

    onglets = ttk.Notebook(racine)
    onglets.pack(fill="both", expand=True, padx=20, pady=(8, 16))

    def zone_texte(parent, lecture_seule):
        cadre = tk.Frame(parent, bg=c["ligne"], padx=1, pady=1)
        t = tk.Text(cadre, wrap="word", font=("Segoe UI", 10), bg=c["panneau"], fg=c["encre"], relief="flat",
                    padx=12, pady=10, undo=True, insertbackground=c["encre"], spacing1=1, spacing3=3)
        barre = ttk.Scrollbar(cadre, command=t.yview)
        t.configure(yscrollcommand=barre.set)
        barre.pack(side="right", fill="y")
        t.pack(fill="both", expand=True)
        t.lecture_seule = lecture_seule
        return cadre, t

    def remplir(t, texte):
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("1.0", texte)
        t.edit_reset()
        if t.lecture_seule:
            t.configure(state="disabled")

    # -- onglet des brouillons
    page_b = ttk.Frame(onglets, padding=12)
    onglets.add(page_b, text="À envoyer")
    gauche = ttk.Frame(page_b)
    gauche.pack(side="left", fill="y")
    liste_b = ttk.Treeview(gauche, columns=("objet",), show="headings", selectmode="browse", height=18)
    liste_b.heading("objet", text="Brouillons à relire")
    liste_b.column("objet", width=330)
    liste_b.pack(fill="y", expand=True)
    droite = ttk.Frame(page_b, padding=(16, 0, 0, 0))
    droite.pack(side="left", fill="both", expand=True)
    champs = {}
    for i, (cle, lib) in enumerate((("a", "À"), ("cc", "Copie"), ("objet", "Objet"))):
        ttk.Label(droite, text=lib, style="Discret.TLabel", width=8).grid(row=i, column=0, sticky="w", pady=3)
        champs[cle] = ttk.Entry(droite, font=police)
        champs[cle].grid(row=i, column=1, sticky="ew", pady=3)
    motif = tk.Label(droite, justify="left", anchor="w", wraplength=700, bg=c["fond"], fg=c["ocre"], font=petite)
    motif.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 6))
    cadre_corps, corps = zone_texte(droite, False)
    cadre_corps.grid(row=4, column=0, columnspan=2, sticky="nsew")
    sources = tk.Label(droite, justify="left", anchor="w", wraplength=700, bg=c["fond"], fg=c["discret"], font=petite)
    sources.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(6, 0))
    boutons = ttk.Frame(droite)
    boutons.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))
    droite.columnconfigure(1, weight=1)
    droite.rowconfigure(4, weight=1)
    droite.bind("<Configure>", lambda e: [w.configure(wraplength=max(300, e.width - 24)) for w in (motif, sources)])
    entete.bind("<Configure>", lambda e: resume.configure(wraplength=max(400, e.width - 220)))

    etat = {"courant": None}

    def a_relire():
        return [b for b in brouillons() if b.get("statut") in ("a_relire", "plus_tard")]

    def garder_modifications():
        b = etat["courant"]
        if not b:
            return
        nouveau = {"a": [x.strip() for x in re.split(r"[,;]", champs["a"].get()) if x.strip()],
                   "cc": [x.strip() for x in re.split(r"[,;]", champs["cc"].get()) if x.strip()],
                   "objet": champs["objet"].get().strip(), "corps": corps.get("1.0", "end").rstrip() + "\n"}
        avant = {k: b.get(k, []) for k in ("a", "cc")} | {"objet": b["objet"], "corps": b["corps"].rstrip() + "\n"}
        if nouveau != avant:
            b.update(nouveau, modifie_le=maintenant())
            ecrire_json(BROUILLONS / f"{b['id']}.json", b)

    def afficher_brouillon(_evt=None):
        garder_modifications()
        sel = liste_b.selection()
        b = lire_json(BROUILLONS / f"{sel[0]}.json") if sel else None
        etat["courant"] = b
        for cle in champs:
            champs[cle].delete(0, "end")
        remplir(corps, "")
        motif.configure(text="")
        sources.configure(text="")
        if not b:
            return
        champs["a"].insert(0, ", ".join(b["a"]))
        champs["cc"].insert(0, ", ".join(b.get("cc", [])))
        champs["objet"].insert(0, b["objet"])
        remplir(corps, b["corps"])
        texte = f"Pourquoi ce message. {b['motif']}"
        if b.get("en_reponse_a") is not None:
            o = lire_json(RECUS / f"{b['en_reponse_a']}.json") or {}
            texte += f"\nEn réponse au message de {o.get('de', '?')} du {(o.get('date') or '')[:10]}, « {o.get('objet', '')} »."
        if b.get("statut") == "plus_tard":
            texte += "\nGardé pour plus tard."
        motif.configure(text=texte)
        if b.get("sources"):
            sources.configure(text="Adresse et faits vérifiés sur " + " ; ".join(b["sources"]))

    def rafraichir_brouillons(choix=None):
        liste_b.delete(*liste_b.get_children())
        for b in a_relire():
            liste_b.insert("", "end", iid=b["id"], values=(("◷ " if b["statut"] == "plus_tard" else "") + b["objet"],))
        enfants = liste_b.get_children()
        if enfants:
            liste_b.selection_set(choix if choix in enfants else enfants[0])
        else:
            etat["courant"] = None
            afficher_brouillon()
        mettre_a_jour_bilan()

    def changer_statut(statut):
        b = etat["courant"]
        if not b:
            return
        garder_modifications()
        b = lire_json(BROUILLONS / f"{b['id']}.json")
        b.update(statut=statut, modifie_le=maintenant())
        ecrire_json(BROUILLONS / f"{b['id']}.json", b)
        etat["courant"] = None
        rafraichir_brouillons(b["id"] if statut == "plus_tard" else None)

    def cliquer_envoyer():
        if not etat["courant"]:
            return
        garder_modifications()
        b = lire_json(BROUILLONS / f"{etat['courant']['id']}.json")
        dest = ", ".join(b["a"] + b.get("cc", []))
        if not messagebox.askyesno("Envoyer ce message ?", f"Envoyer « {b['objet']} »\nà {dest}\n\ndepuis {ADRESSE} ?",
                                   icon="question", default="no", parent=racine):
            return
        racine.config(cursor="watch")
        racine.update()
        try:
            texte = envoyer(b)
        except Arret as e:
            messagebox.showerror("Message non envoyé", str(e), parent=racine)
            return
        finally:
            racine.config(cursor="")
        etat["courant"] = None
        rafraichir_brouillons()
        messagebox.showinfo("Message envoyé", texte, parent=racine)

    ttk.Button(boutons, text="Envoyer", style="Envoyer.TButton", command=cliquer_envoyer).pack(side="left")
    ttk.Button(boutons, text="Garder pour plus tard", command=lambda: changer_statut("plus_tard")).pack(
        side="left", padx=(10, 0))
    ttk.Button(boutons, text="Écarter", command=lambda: changer_statut("ecarte")).pack(side="left", padx=(10, 0))
    ttk.Label(boutons, text="Les modifications du texte sont gardées.", style="Discret.TLabel").pack(side="right")
    liste_b.bind("<<TreeviewSelect>>", afficher_brouillon)

    # -- onglet des messages reçus
    page_r = ttk.Frame(onglets, padding=12)
    onglets.add(page_r, text="Reçus")
    liste_r = ttk.Treeview(page_r, columns=("date", "de", "objet", "importance"), show="headings",
                           selectmode="browse", height=9)
    for col, lib, larg in (("date", "Date", 120), ("de", "Expéditeur", 300), ("objet", "Objet", 470),
                           ("importance", "Compte rendu", 150)):
        liste_r.heading(col, text=lib, anchor="w")
        liste_r.column(col, width=larg, anchor="w", stretch=col == "objet")
    liste_r.pack(fill="x")
    cadre_r, texte_r = zone_texte(page_r, True)
    cadre_r.pack(fill="both", expand=True, pady=(10, 0))
    texte_r.tag_configure("cr", foreground=c["bleu"], font=("Segoe UI Semibold", 10))
    texte_r.tag_configure("meta", foreground=c["discret"], font=petite)

    def afficher_recu(_evt=None):
        sel = liste_r.selection()
        r = lire_json(RECUS / f"{sel[0]}.json") if sel else None
        texte_r.configure(state="normal")
        texte_r.delete("1.0", "end")
        if r:
            if r.get("compte_rendu"):
                e = r["compte_rendu"]
                texte_r.insert("end", f"{IMPORTANCES.get(e['importance'], '')}. {e['resume']}", "cr")
                if e.get("suite"):
                    texte_r.insert("end", f"\nSuite proposée. {e['suite']}", "cr")
                texte_r.insert("end", "\n\n")
            meta = f"De {r['de']}\nÀ {r['a']}" + (f"\nCopie {r['cc']}" if r.get("cc") else "")
            meta += f"\nObjet {r['objet']}\nDate {(r.get('date') or '')[:16].replace('T', ' ')}"
            if r.get("pieces_jointes"):
                meta += "\nPièces jointes (non ouvertes) " + ", ".join(r["pieces_jointes"])
            texte_r.insert("end", meta + "\n\n", "meta")
            texte_r.insert("end", r.get("texte") or "(message sans texte)")
        texte_r.configure(state="disabled")

    def rafraichir_recus():
        liste_r.delete(*liste_r.get_children())
        for r in recus():
            imp = IMPORTANCES.get((r.get("compte_rendu") or {}).get("importance"), "pas encore lu")
            liste_r.insert("", "end", iid=str(r["uid"]), values=((r.get("date") or "")[:16].replace("T", " "),
                                                                r["de"], r["objet"], imp))
        mettre_a_jour_bilan()

    liste_r.bind("<<TreeviewSelect>>", afficher_recu)

    def mettre_a_jour_bilan():
        e = lire_json(ETAT, {})
        nb_b = len(a_relire())
        nb_r = sum(1 for r in recus() if not r.get("compte_rendu"))
        der = (e.get("derniere_releve") or "")[:16].replace("T", " à ")
        bilan.configure(text=f"{nb_b} brouillon(s) à relire, {nb_r} message(s) sans compte rendu"
                             + (f", dernière relève le {der}" if der else ", aucune relève encore"))

    def relever_maintenant():
        racine.config(cursor="watch")
        racine.update()
        code = cmd_relever(None)
        racine.config(cursor="")
        rafraichir_recus()
        if code == 20:
            messagebox.showerror("Relève impossible", "La boîte n'a pas pu être relevée. Voir le tutoriel 09.",
                                 parent=racine)

    ttk.Button(entete, text="Relever maintenant", command=relever_maintenant).place(relx=1.0, y=4, anchor="ne")

    def fermer():
        garder_modifications()
        racine.destroy()

    racine.protocol("WM_DELETE_WINDOW", fermer)
    rafraichir_brouillons()
    rafraichir_recus()
    if not a_relire():
        onglets.select(page_r)
    racine.lift()
    racine.attributes("-topmost", True)
    racine.after(800, lambda: racine.attributes("-topmost", False))
    racine.focus_force()
    if args and getattr(args, "capture", None):
        racine.after(1500, lambda: (capturer(racine, Path(args.capture)), racine.destroy()))
    racine.mainloop()
    return 0


def capturer(fenetre, chemin: Path) -> None:
    """Image PNG de la fenêtre (pour le tutoriel), par l'interface graphique de Windows."""
    import ctypes
    import struct
    import zlib
    from ctypes import wintypes
    fenetre.update()
    hwnd = ctypes.windll.user32.GetParent(fenetre.winfo_id()) or fenetre.winfo_id()
    r = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
    l, h = r.right - r.left, r.bottom - r.top
    gdi, u32 = ctypes.windll.gdi32, ctypes.windll.user32
    dc = u32.GetWindowDC(hwnd)
    mem = gdi.CreateCompatibleDC(dc)
    bmp = gdi.CreateCompatibleBitmap(dc, l, h)
    gdi.SelectObject(mem, bmp)
    u32.PrintWindow(hwnd, mem, 2)
    entete = struct.pack("<IiiHHIIiiII", 40, l, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    tampon = ctypes.create_string_buffer(l * h * 4)
    gdi.GetDIBits(mem, bmp, 0, h, tampon, entete, 0)
    gdi.DeleteObject(bmp), gdi.DeleteDC(mem), u32.ReleaseDC(hwnd, dc)
    brut = tampon.raw
    lignes = b"".join(b"\x00" + bytes(x for i in range(0, l * 4, 4) for x in (brut[y * l * 4 + i + 2],
                      brut[y * l * 4 + i + 1], brut[y * l * 4 + i])) for y in range(h))

    def bloc(typ, donnees):
        return struct.pack(">I", len(donnees)) + typ + donnees + struct.pack(">I", zlib.crc32(typ + donnees))
    chemin.write_bytes(b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", struct.pack(">IIBBBBB", l, h, 8, 2, 0, 0, 0))
                       + bloc(b"IDAT", zlib.compress(lignes, 6)) + bloc(b"IEND", b""))


def main() -> int:
    ap = argparse.ArgumentParser(description="Courrier de contact@ubicura.fr (tutoriel 09).")
    sous = ap.add_subparsers(dest="commande", required=True)
    sous.add_parser("mot-de-passe").set_defaults(f=cmd_mot_de_passe)
    sous.add_parser("verifier").set_defaults(f=cmd_verifier)
    sous.add_parser("relever").set_defaults(f=cmd_relever)
    sous.add_parser("a-traiter").set_defaults(f=cmd_a_traiter)
    p = sous.add_parser("ajouter-brouillon")
    p.add_argument("fichier")
    p.set_defaults(f=cmd_ajouter_brouillon)
    p = sous.add_parser("compte-rendu")
    p.add_argument("fichier")
    p.set_defaults(f=cmd_compte_rendu)
    p = sous.add_parser("boite")
    p.add_argument("--capture", help=argparse.SUPPRESS)
    p.set_defaults(f=cmd_boite)
    args = ap.parse_args()
    try:
        return args.f(args)
    except Arret as e:
        print(f"Arrêt, {e}")
        return 20


if __name__ == "__main__":
    sys.exit(main())
