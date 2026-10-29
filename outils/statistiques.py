"""Écho du projet, une photographie par jour des mesures publiées par Bluesky, data.gouv.fr, Zenodo et GoatCounter,
montrée dans l'onglet « Statistiques » de la fenêtre du courrier (demande de Lucas du 29 octobre 2026). Lecture seule,
rien n'est publié, sources officielles seulement. Les photographies restent sur le PC dans donnees\\statistiques\\
(hors de Git), une par jour, AAAA-MM-JJ.json.

    python outils\\statistiques.py photographier [--forcer]   photographie du jour (une seule par jour sans --forcer)
    python outils\\statistiques.py jeton-goatcounter          jeton de lecture de GoatCounter, testé puis rangé dans le
                                                              gestionnaire d'identifiants de Windows (tutoriel 13)
    python outils\\statistiques.py resume                     état du jour en quelques lignes

La photographie du jour est aussi prise par messagerie.py relever et envoyer-programmes (relève et mise à jour
quotidiennes), une fois par jour.

Sources, lues le 29 octobre 2026.
- Bluesky, API publique (public.api.bsky.app), app.bsky.actor.getProfile (followersCount, followsCount, postsCount) et
  app.bsky.feed.getAuthorFeed sur le DID du compte (likeCount, repostCount, replyCount, quoteCount de chaque message,
  republications d'autres comptes écartées).
- data.gouv.fr, GET /api/1/reuses/{id}/, champ metrics (views, followers, discussions), identifiant de la réutilisation
  dans donnees\\datagouv.json.
- Zenodo, GET /api/records/{id} sur le DID général de chaque dépôt (redirigé vers la dernière version), champ stats.
  unique_views et unique_downloads sont les « Views » et « Downloads » de la colonne « All versions » de la page du dépôt
  (vérifié sur zenodo.org/records/23760494 le 29 octobre 2026).
- GoatCounter, API v0 (www.goatcounter.com/help/api et /api.json), GET /api/v0/stats/total (visiteurs par jour, champ
  stats[].daily) et GET /api/v0/stats/hits (visiteurs par page, champ hits[].count), jeton envoyé dans l'en-tête
  Authorization. Sans jeton rangé, la source est notée « sans jeton », rien d'autre ne change.
"""
from __future__ import annotations

import argparse
import datetime as dt
import getpass
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from pipeline import config  # noqa: E402
from outils import identifiants  # noqa: E402

DOSSIER = config.DONNEES / "statistiques"
DATAGOUV = config.DONNEES / "datagouv.json"
CIBLE_GOATCOUNTER = "Ubi Cura, GoatCounter"   # nom du jeton dans le gestionnaire d'identifiants de Windows
BLUESKY_PUBLIC = "https://public.api.bsky.app/xrpc"
DATAGOUV_API = "https://www.data.gouv.fr/api/1"
ZENODO_API = "https://zenodo.org/api/records"
GOATCOUNTER_API = f"https://{config.GOATCOUNTER}.goatcounter.com/api/v0"
GOATCOUNTER_DEBUT = dt.date(2026, 10, 23)     # compteur posé sur le site le 23 octobre 2026
DEPOTS = {"donnees": ("Données", config.DOI_DONNEES),
          "sante-mentale": ("Rapport santé mentale", config.DOI_RAPPORTS["sante-mentale"]),
          "sante": ("Rapport santé", config.DOI_RAPPORTS["sante"])}
ENTETES = {"User-Agent": f"{config.NOM_PROJET}, statistiques ({config.ADRESSE_SITE})"}
BLUESKY_PAGES = 5                             # 100 messages par page, 500 messages au plus


def maintenant() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _get(url: str, **kw) -> dict:
    import requests
    r = requests.get(url, headers=ENTETES | kw.pop("entetes", {}), timeout=60, **kw)
    if r.status_code != 200:
        # le message du service dit la cause (jeton inconnu, permission manquante, paramètre refusé), sans le jeton
        raise RuntimeError(f"code {r.status_code}, {r.text.strip()[:200]}")
    return r.json()


# ---------------------------------------------------------------- sources
def bluesky(did: str | None = None) -> dict:
    did = did or config.BLUESKY_DID
    p = _get(f"{BLUESKY_PUBLIC}/app.bsky.actor.getProfile", params={"actor": did})
    messages, curseur = [], None
    for _ in range(BLUESKY_PAGES):
        params = {"actor": did, "limit": 100, "filter": "posts_and_author_threads"}
        if curseur:
            params["cursor"] = curseur
        f = _get(f"{BLUESKY_PUBLIC}/app.bsky.feed.getAuthorFeed", params=params)
        for x in f.get("feed", []):
            m = x["post"]
            if "reason" in x or m["author"]["did"] != did:   # republication d'un autre compte
                continue
            messages.append({"uri": m["uri"], "adresse": f"https://bsky.app/profile/{did}/post/{m['uri'].rsplit('/', 1)[-1]}",
                             "date": m["record"].get("createdAt", ""), "texte": m["record"].get("text", "")[:140],
                             "jaime": m.get("likeCount", 0), "republications": m.get("repostCount", 0),
                             "reponses": m.get("replyCount", 0), "citations": m.get("quoteCount", 0)})
        curseur = f.get("cursor")
        if not curseur:
            break
    return {"compte": p.get("handle"), "abonnes": p.get("followersCount", 0), "abonnements": p.get("followsCount", 0),
            "messages": p.get("postsCount", 0), "jaime": sum(m["jaime"] for m in messages),
            "republications": sum(m["republications"] for m in messages),
            "reponses": sum(m["reponses"] for m in messages), "publications": messages}


def datagouv() -> dict:
    ident = json.loads(DATAGOUV.read_text(encoding="utf-8"))["id"]
    d = _get(f"{DATAGOUV_API}/reuses/{ident}/")
    m = d.get("metrics") or {}
    return {"titre": d.get("title"), "page": d.get("page"), "vues": m.get("views", 0), "abonnes": m.get("followers", 0),
            "discussions": m.get("discussions", 0), "modifiee_le": d.get("last_modified")}


def zenodo() -> dict:
    sortie = {}
    for cle, (nom, doi) in DEPOTS.items():
        d = _get(f"{ZENODO_API}/{doi.rsplit('.', 1)[-1]}")
        s = d.get("stats") or {}
        sortie[cle] = {"nom": nom, "doi_general": doi, "doi_version": d.get("doi"),
                       "version": (d.get("metadata") or {}).get("version"),
                       "publiee_le": (d.get("metadata") or {}).get("publication_date"),
                       "vues": s.get("unique_views", 0), "telechargements": s.get("unique_downloads", 0),
                       "vues_version": s.get("version_unique_views", 0),
                       "telechargements_version": s.get("version_unique_downloads", 0)}
    return sortie


def jeton_goatcounter() -> str | None:
    return identifiants.lire_compte(CIBLE_GOATCOUNTER)[1]


def goatcounter(jeton: str | None = None, aujourdhui: dt.date | None = None) -> dict:
    jeton = jeton or jeton_goatcounter()
    if not jeton:
        return {"sans_jeton": True}
    aujourdhui = aujourdhui or dt.date.today()
    e = {"entetes": {"Authorization": f"Bearer {jeton}", "Content-Type": "application/json"}}
    fin = f"{aujourdhui + dt.timedelta(days=1)}T00:00:00Z"
    t = _get(f"{GOATCOUNTER_API}/stats/total", params={"start": f"{GOATCOUNTER_DEBUT}T00:00:00Z", "end": fin}, **e)
    jours = {s["day"][:10]: s.get("daily", 0) for s in t.get("stats", [])}
    debut_30 = aujourdhui - dt.timedelta(days=29)
    h = _get(f"{GOATCOUNTER_API}/stats/hits", params={"start": f"{debut_30}T00:00:00Z", "end": fin, "limit": 10}, **e)
    pages = [{"chemin": x.get("path"), "visiteurs": x.get("count", 0)} for x in h.get("hits", []) if not x.get("event")]
    return {"sans_jeton": False, "jours": jours, "total": t.get("total", 0), "pages_30_jours": pages,
            "pages_depuis": str(debut_30)}


SOURCES = {"bluesky": bluesky, "datagouv": datagouv, "zenodo": zenodo, "goatcounter": goatcounter}
NOMS = {"bluesky": "Bluesky", "datagouv": "data.gouv.fr", "zenodo": "Zenodo", "goatcounter": "GoatCounter"}


# ---------------------------------------------------------------- photographies
def fichier(jour: dt.date) -> Path:
    return DOSSIER / f"{jour.isoformat()}.json"


def photographier(forcer: bool = False, sources: dict | None = None) -> dict | None:
    """Photographie du jour, une source en échec n'empêche pas les autres. None si elle existe déjà (sans forcer)."""
    f = fichier(dt.date.today())
    if f.exists() and not forcer:
        return None
    photo = {"prise_le": maintenant(), "sources": {}}
    for nom, lire in (sources or SOURCES).items():
        try:
            photo["sources"][nom] = {"ok": True, "lu_le": maintenant(), **lire()}
        except Exception as e:   # noqa: BLE001, une source cassée est notée et n'arrête pas les autres
            photo["sources"][nom] = {"ok": False, "lu_le": maintenant(), "erreur": f"{e.__class__.__name__}, {e}"[:200]}
    DOSSIER.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(photo, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(f)
    return photo


def bilan(photo: dict) -> str:
    s = photo["sources"]
    ok = [NOMS[k] for k, v in s.items() if v.get("ok") and not v.get("sans_jeton")]
    sans = [NOMS[k] for k, v in s.items() if v.get("sans_jeton")]
    ko = [NOMS[k] for k, v in s.items() if not v.get("ok")]
    return ("Statistiques, photographie du jour prise, " + (", ".join(ok) or "aucune source lue")
            + (f", {', '.join(sans)} sans jeton" if sans else "") + (f", échec {', '.join(ko)}" if ko else "") + ".")


def photographier_du_jour() -> int:
    """Pour la relève et la mise à jour quotidiennes, n'écrit qu'une ligne et seulement quand la photographie est prise.
    Ne renvoie jamais d'échec, la relève du courrier n'en dépend pas."""
    try:
        photo = photographier()
    except OSError as e:
        print(f"Statistiques, photographie impossible ({e}).")
        return 0
    if photo:
        print(bilan(photo))
    return 0


def photographies() -> list[tuple[dt.date, dict]]:
    sortie = []
    for f in sorted(DOSSIER.glob("????-??-??.json")):
        try:
            sortie.append((dt.date.fromisoformat(f.stem), json.loads(f.read_text(encoding="utf-8"))))
        except (ValueError, OSError):
            continue
    return sortie


def serie(photos: list[tuple[dt.date, dict]], source: str, *cles: str) -> list[tuple[dt.date, float]]:
    """Valeurs d'une mesure d'une photographie à l'autre, jours sans lecture réussie omis."""
    sortie = []
    for jour, p in photos:
        v = p["sources"].get(source) or {}
        if not v.get("ok"):
            continue
        for c in cles:
            v = v.get(c) if isinstance(v, dict) else None
        if isinstance(v, (int, float)):
            sortie.append((jour, v))
    return sortie


def visiteurs_par_semaine(photos: list[tuple[dt.date, dict]]) -> list[tuple[dt.date, int, bool]]:
    """Visiteurs GoatCounter par semaine (lundi), d'après les jours de la photographie la plus récente qui les donne,
    complétés par les plus anciennes. Le booléen dit si la semaine est complète."""
    jours = {}
    for _, p in photos:
        g = p["sources"].get("goatcounter") or {}
        if g.get("ok") and not g.get("sans_jeton"):
            jours.update(g.get("jours") or {})
    semaines = {}
    for j, n in jours.items():
        d = dt.date.fromisoformat(j)
        lundi = d - dt.timedelta(days=d.weekday())
        semaines[lundi] = semaines.get(lundi, 0) + n
    aujourdhui = dt.date.today()
    return [(l, n, l + dt.timedelta(days=7) <= aujourdhui) for l, n in sorted(semaines.items())]


# ---------------------------------------------------------------- commandes
def cmd_photographier(args) -> int:
    photo = photographier(forcer=args.forcer)
    if photo is None:
        print("Photographie du jour déjà prise. Ajouter --forcer pour la refaire.")
        return 0
    print(bilan(photo))
    for nom, v in photo["sources"].items():
        if not v.get("ok"):
            print(f"  {NOMS[nom]}, {v['erreur']}")
    return 0


def cmd_jeton_goatcounter(_args) -> int:
    print("Jeton de l'interface de GoatCounter (tutoriel 13), avec la seule permission de lire les statistiques. Il ne "
          "s'affiche pas pendant la frappe.")
    brut = getpass.getpass("Jeton : ")
    # Ctrl+V dans une fenêtre PowerShell colle parfois un caractère de contrôle au lieu du texte, seuls les caractères
    # visibles sont gardés et l'écart est signalé
    jeton = "".join(c for c in brut if c.isprintable()).strip()
    if len(jeton) != len(brut.strip()):
        print("Des caractères invisibles ont été retirés de la saisie. Si le jeton est refusé, recolle-le avec un clic "
              "droit dans la fenêtre plutôt qu'avec Ctrl+V.")
    if not jeton:
        print("Jeton vide, rien n'a changé.")
        return 20
    try:
        g = goatcounter(jeton)   # essai réel avec la seule permission « Read statistics »
    except Exception as e:   # noqa: BLE001
        print(f"GoatCounter refuse ce jeton ou ne répond pas ({e}). Vérifier la permission « Read statistics » "
              "(tutoriel 13). Rien n'a changé.")
        return 20
    erreur = identifiants.ecrire(CIBLE_GOATCOUNTER, jeton, config.GOATCOUNTER, "Lecture des statistiques, tutoriel 13")
    if erreur:
        print(f"Le jeton n'a pas pu être rangé (erreur Windows {erreur}).")
        return 20
    print(f"Jeton accepté par GoatCounter ({g['total']} visiteurs depuis le {GOATCOUNTER_DEBUT:%d/%m/%Y}) et rangé dans "
          f"le gestionnaire d'identifiants de Windows, sous « {CIBLE_GOATCOUNTER} ».")
    return 0


def cmd_resume(_args) -> int:
    photos = photographies()
    if not photos:
        print("Aucune photographie encore.")
        return 0
    jour, p = photos[-1]
    print(f"Photographie du {jour:%d/%m/%Y}.")
    s = p["sources"]
    if s.get("bluesky", {}).get("ok"):
        b = s["bluesky"]
        print(f"  Bluesky @{b['compte']}, {b['abonnes']} abonnés, {b['abonnements']} abonnements, {b['messages']} "
              f"messages, {b['jaime']} « j'aime », {b['republications']} republications, {b['reponses']} réponses.")
    if s.get("datagouv", {}).get("ok"):
        d = s["datagouv"]
        print(f"  data.gouv.fr, {d['vues']} vues, {d['abonnes']} abonnés, {d['discussions']} discussions.")
    if s.get("zenodo", {}).get("ok"):
        for z in s["zenodo"].values():
            if isinstance(z, dict) and "vues" in z:
                print(f"  Zenodo, {z['nom']}, {z['vues']} vues et {z['telechargements']} téléchargements, toutes versions.")
    g = s.get("goatcounter", {})
    if g.get("sans_jeton"):
        print("  GoatCounter, pas de jeton rangé (tutoriel 13).")
    elif g.get("ok"):
        print(f"  GoatCounter, {g['total']} visiteurs depuis le {GOATCOUNTER_DEBUT:%d/%m/%Y}.")
    for nom, v in s.items():
        if not v.get("ok"):
            print(f"  {NOMS[nom]}, lecture impossible ({v['erreur']}).")
    return 0


# ---------------------------------------------------------------- onglet de la fenêtre du courrier
def nombre(v) -> str:
    return f"{int(v):,}".replace(",", " ") if isinstance(v, (int, float)) else "–"


def onglet(onglets, racine, c: dict, police, petite) -> dict:
    """Onglet « Statistiques », état du jour et une courbe simple par mesure (une seule couleur, la valeur du jour
    en bleu, les précédentes en gris, infobulle date et valeur au survol). Renvoie {page, rafraichir}."""
    import tkinter as tk
    import webbrowser
    from tkinter import ttk

    page = ttk.Frame(onglets, padding=0)
    onglets.add(page, text="Statistiques")
    toile = tk.Canvas(page, bg=c["fond"], highlightthickness=0)
    barre = ttk.Scrollbar(page, orient="vertical", command=toile.yview)
    toile.configure(yscrollcommand=barre.set)
    barre.pack(side="right", fill="y")
    toile.pack(side="left", fill="both", expand=True)
    corps = tk.Frame(toile, bg=c["fond"], padx=16, pady=12)
    fen = toile.create_window(0, 0, window=corps, anchor="nw")
    corps.bind("<Configure>", lambda e: toile.configure(scrollregion=toile.bbox("all")))
    toile.bind("<Configure>", lambda e: toile.itemconfigure(fen, width=e.width))
    toile.bind("<Enter>", lambda e: toile.bind_all("<MouseWheel>", lambda ev: toile.yview_scroll(
        -1 * (ev.delta // 120), "units")))
    toile.bind("<Leave>", lambda e: toile.unbind_all("<MouseWheel>"))
    info = {"bulle": None}

    def bulle(w, x, y, texte):
        cacher_bulle()
        b = tk.Toplevel(w)
        b.wm_overrideredirect(True)
        b.wm_geometry(f"+{x + 12}+{y + 12}")
        tk.Label(b, text=texte, bg=c["encre"], fg="#FFFFFF", font=petite, padx=6, pady=2).pack()
        info["bulle"] = b

    def cacher_bulle(_e=None):
        if info["bulle"] is not None:
            info["bulle"].destroy()
            info["bulle"] = None

    def courbe(parent, points, largeur=140, hauteur=40, etiquette=lambda d: f"{d:%d/%m}"):
        """Courbe d'une mesure, ligne de 2 px grise, dernier point en bleu, aucun axe (la valeur est écrite à côté)."""
        cv = tk.Canvas(parent, width=largeur, height=hauteur, bg=c["panneau"], highlightthickness=0)
        if not points:
            cv.create_text(largeur / 2, hauteur / 2, text="pas encore de relevé", fill=c["discret"], font=petite)
            return cv
        vals = [v for _, v in points]
        bas, haut = min(vals), max(vals)
        etendue = (haut - bas) or 1
        m = 7
        xs = [m + (largeur - 2 * m) * (i / (len(points) - 1) if len(points) > 1 else 1) for i in range(len(points))]
        ys = [hauteur - m - (hauteur - 2 * m) * ((v - bas) / etendue if haut > bas else 0.5) for v in vals]
        if len(points) > 1:
            cv.create_line(*[a for xy in zip(xs, ys) for a in xy], fill=c["discret"], width=2, capstyle="round",
                           joinstyle="round")
        cv.create_oval(xs[-1] - 5, ys[-1] - 5, xs[-1] + 5, ys[-1] + 5, fill=c["bleu"], outline=c["panneau"], width=1)

        def survol(e):
            i = min(range(len(xs)), key=lambda k: abs(xs[k] - e.x))
            bulle(cv, e.x_root, e.y_root, f"{etiquette(points[i][0])}, {nombre(points[i][1])}")
        cv.bind("<Motion>", survol)
        cv.bind("<Leave>", cacher_bulle)
        return cv

    def tuile(parent, libelle, points, colonne, ligne=0):
        """Tuile d'une mesure, libellé, valeur du jour, écart sur sept jours, courbe."""
        t = tk.Frame(parent, bg=c["panneau"], highlightbackground=c["ligne"], highlightthickness=1, padx=10, pady=8)
        t.grid(row=ligne, column=colonne, sticky="nsew", padx=(0, 8), pady=(0, 8))
        parent.grid_columnconfigure(colonne, uniform="tuiles")
        tk.Label(t, text=libelle, bg=c["panneau"], fg=c["discret"], font=petite, anchor="nw", justify="left",
                 wraplength=140, height=2).pack(fill="x")
        tk.Label(t, text=nombre(points[-1][1]) if points else "–", bg=c["panneau"], fg=c["encre"],
                 font=("Segoe UI Semibold", 18), anchor="w").pack(fill="x")
        ecart = ""
        if points:
            avant = [v for d, v in points if d <= points[-1][0] - dt.timedelta(days=7)]
            if avant:
                n = points[-1][1] - avant[-1]
                ecart = f"{'+' if n > 0 else ''}{nombre(n) if n >= 0 else '−' + nombre(-n)} en 7 jours"
            elif len(points) == 1:
                ecart = "premier relevé"
            else:
                ecart = f"depuis le {points[0][0]:%d/%m}"
        tk.Label(t, text=ecart, bg=c["panneau"], fg=c["discret"], font=petite, anchor="w").pack(fill="x")
        courbe(t, points).pack(anchor="w", pady=(4, 0))

    def section(titre, date_texte):
        tete = tk.Frame(corps, bg=c["fond"])
        tete.pack(fill="x", pady=(14, 6))
        tk.Label(tete, text=titre, bg=c["fond"], fg=c["encre"], font=("Segoe UI Semibold", 12)).pack(side="left")
        tk.Label(tete, text=date_texte, bg=c["fond"], fg=c["discret"], font=petite).pack(side="left", padx=(12, 0))
        g = tk.Frame(corps, bg=c["fond"])
        g.pack(fill="x", anchor="w")
        return g

    def quand(v):
        try:
            return dt.datetime.fromisoformat(v["lu_le"]).strftime("lu le %d/%m à %H h %M")
        except (KeyError, ValueError):
            return ""

    def message_source(parent, v, nom):
        if v.get("sans_jeton"):
            texte = (f"{nom}, pas de jeton rangé, ces mesures ne sont pas lues. Voir le tutoriel 13 pour en ranger un, "
                     "en lecture seule.")
        elif not v.get("ok"):
            texte = f"{nom}, lecture impossible à la dernière photographie ({v.get('erreur', 'source absente')})."
        else:
            return False
        tk.Label(parent, text=texte, bg=c["fond"], fg=c["ocre"], font=petite, anchor="w", justify="left").grid(
            row=0, column=0, columnspan=6, sticky="w")
        return True

    def rafraichir():
        for w in corps.winfo_children():
            w.destroy()
        photos = photographies()
        tete = tk.Frame(corps, bg=c["fond"])
        tete.pack(fill="x")
        if photos:
            jour, dernier = photos[-1]
            prise = dt.datetime.fromisoformat(dernier["prise_le"])
            texte = (f"Photographie du {prise:%d/%m/%Y à %H h %M}, {len(photos)} photographie(s) depuis le "
                     f"{photos[0][0]:%d/%m/%Y}. Une par jour, avec la relève du courrier ou la mise à jour, gardée "
                     "sur ce PC et jamais publiée.")
        else:
            dernier = {"sources": {}}
            texte = "Aucune photographie encore. Elle est prise chaque jour avec la relève du courrier."
        tk.Label(tete, text=texte, bg=c["fond"], fg=c["discret"], font=petite, anchor="w", justify="left",
                 wraplength=760).pack(side="left", fill="x", expand=True)
        ttk.Button(tete, text="Photographier maintenant", command=photographier_maintenant).pack(side="right")
        s = dernier["sources"]

        # Bluesky
        b = s.get("bluesky", {"ok": False, "erreur": "pas encore lu"})
        g = section("Bluesky", (f"@{b.get('compte')}, " if b.get("ok") else "") + quand(b)
                    + ", API publique de Bluesky")
        if not message_source(g, b, "Bluesky"):
            for i, (lib, cle) in enumerate((("Abonnés", "abonnes"), ("Abonnements", "abonnements"),
                                            ("Messages", "messages"), ("« J'aime » reçus", "jaime"),
                                            ("Republications", "republications"), ("Réponses", "reponses"))):
                tuile(g, lib, serie(photos, "bluesky", cle), i)
            pubs = b.get("publications") or []
            cadre = tk.Frame(corps, bg=c["fond"])
            cadre.pack(fill="x", anchor="w")
            if pubs:
                arbre = ttk.Treeview(cadre, columns=("date", "texte", "jaime", "repo", "rep", "cit"), show="headings",
                                     height=min(8, len(pubs)), selectmode="browse")
                for col, lib, larg, anc in (("date", "Date", 90, "w"), ("texte", "Message", 520, "w"),
                                            ("jaime", "« J'aime »", 80, "e"), ("repo", "Republications", 110, "e"),
                                            ("rep", "Réponses", 80, "e"), ("cit", "Citations", 80, "e")):
                    arbre.heading(col, text=lib, anchor=anc)
                    arbre.column(col, width=larg, anchor=anc, stretch=col == "texte")
                for i, m in enumerate(sorted(pubs, key=lambda x: x["date"], reverse=True)):
                    arbre.insert("", "end", iid=str(i), values=(m["date"][8:10] + "/" + m["date"][5:7] + "/"
                                                                + m["date"][:4], m["texte"].replace("\n", " "),
                                                                m["jaime"], m["republications"], m["reponses"],
                                                                m["citations"]))
                ordre = sorted(pubs, key=lambda x: x["date"], reverse=True)
                arbre.bind("<Double-1>", lambda e: arbre.selection() and webbrowser.open(
                    ordre[int(arbre.selection()[0])]["adresse"]))
                arbre.pack(fill="x", anchor="w")
                tk.Label(cadre, text="Double clic pour ouvrir le message.", bg=c["fond"], fg=c["discret"],
                         font=petite).pack(anchor="w")
            else:
                tk.Label(cadre, text="Aucun message publié pour l'instant.", bg=c["fond"], fg=c["discret"],
                         font=petite).pack(anchor="w")

        # data.gouv.fr
        d = s.get("datagouv", {"ok": False, "erreur": "pas encore lu"})
        g = section("data.gouv.fr", "réutilisation « " + str(d.get("titre") or "") + " », " + quand(d)
                    if d.get("ok") else quand(d))
        if not message_source(g, d, "data.gouv.fr"):
            for i, (lib, cle) in enumerate((("Vues de la page", "vues"), ("Abonnés", "abonnes"),
                                            ("Discussions", "discussions"))):
                tuile(g, lib, serie(photos, "datagouv", cle), i)

        # Zenodo
        z = s.get("zenodo", {"ok": False, "erreur": "pas encore lu"})
        versions = sorted({v.get("publiee_le") for v in z.values() if isinstance(v, dict) and v.get("publiee_le")})
        g = section("Zenodo", quand(z) + (", toutes versions, dernière version publiée le "
                                          + ", ".join(f"{dt.date.fromisoformat(x):%d/%m/%Y}" for x in versions)
                                          if versions else ""))
        if not message_source(g, z, "Zenodo"):
            for i, (cle, (nom, _)) in enumerate(DEPOTS.items()):
                tuile(g, f"{nom}, vues", serie(photos, "zenodo", cle, "vues"), 2 * i)
                tuile(g, f"{nom}, téléchargements", serie(photos, "zenodo", cle, "telechargements"), 2 * i + 1)

        # GoatCounter
        gc = s.get("goatcounter", {"ok": False, "erreur": "pas encore lu"})
        g = section("Visites du site", (quand(gc) + ", GoatCounter, visiteurs comptés sans cookie")
                    if gc.get("ok") and not gc.get("sans_jeton") else "GoatCounter")
        if not message_source(g, gc, "GoatCounter"):
            semaines = visiteurs_par_semaine(photos)
            t = tk.Frame(g, bg=c["panneau"], highlightbackground=c["ligne"], highlightthickness=1, padx=12, pady=8)
            t.grid(row=0, column=0, sticky="nw", padx=(0, 10))
            tk.Label(t, text="Visiteurs par semaine (du lundi au dimanche)", bg=c["panneau"], fg=c["discret"],
                     font=petite, anchor="w").pack(fill="x")
            der = semaines[-1] if semaines else None
            tk.Label(t, text=nombre(der[1]) if der else "–", bg=c["panneau"], fg=c["encre"],
                     font=("Segoe UI Semibold", 18), anchor="w").pack(fill="x")
            tk.Label(t, text=(f"semaine du {der[0]:%d/%m}" + ("" if der[2] else ", en cours")) if der else "",
                     bg=c["panneau"], fg=c["discret"], font=petite, anchor="w").pack(fill="x")
            courbe(t, [(l, n) for l, n, _ in semaines], largeur=360, hauteur=70,
                   etiquette=lambda d: f"semaine du {d:%d/%m}").pack(anchor="w", pady=(4, 0))
            p = tk.Frame(g, bg=c["panneau"], highlightbackground=c["ligne"], highlightthickness=1, padx=12, pady=8)
            p.grid(row=0, column=1, sticky="nw")
            tk.Label(p, text=f"Pages les plus vues depuis le {dt.date.fromisoformat(gc['pages_depuis']):%d/%m}",
                     bg=c["panneau"], fg=c["discret"], font=petite, anchor="w").grid(row=0, column=0, columnspan=2,
                                                                                      sticky="w")
            for i, x in enumerate(gc.get("pages_30_jours") or [], start=1):
                tk.Label(p, text=x["chemin"], bg=c["panneau"], fg=c["encre"], font=petite, anchor="w").grid(
                    row=i, column=0, sticky="w", padx=(0, 24))
                tk.Label(p, text=nombre(x["visiteurs"]), bg=c["panneau"], fg=c["encre"], font=petite,
                         anchor="e").grid(row=i, column=1, sticky="e")
        tk.Label(corps, text="Lecture seule. Les mesures viennent des sources nommées, telles qu'elles les publient "
                             "(Zenodo compte les vues et téléchargements uniques de toutes les versions d'un dépôt).",
                 bg=c["fond"], fg=c["discret"], font=petite, anchor="w", justify="left", wraplength=900).pack(
            fill="x", pady=(16, 0))

    def photographier_maintenant():
        racine.config(cursor="watch")
        racine.update()
        try:
            photographier(forcer=True)
        except OSError:
            pass
        finally:
            racine.config(cursor="")
        rafraichir()

    rafraichir()
    return {"page": page, "rafraichir": rafraichir}


def main() -> int:
    ap = argparse.ArgumentParser(description="Écho du projet, photographie quotidienne des statistiques publiques.")
    sous = ap.add_subparsers(dest="commande", required=True)
    p = sous.add_parser("photographier")
    p.add_argument("--forcer", action="store_true", help="refait la photographie du jour")
    p.set_defaults(f=cmd_photographier)
    sous.add_parser("jeton-goatcounter").set_defaults(f=cmd_jeton_goatcounter)
    sous.add_parser("resume").set_defaults(f=cmd_resume)
    args = ap.parse_args()
    return args.f(args)


if __name__ == "__main__":
    sys.exit(main())
