"""Contrôle de finition des pages du site (direction visuelle du 30 octobre 2026, docs/direction_visuelle.md).

Pour chaque page, à 1 280, 1 024, 883 et 375 px de large, dans Edge ou Chrome sans fenêtre :
- au plus cinq tailles de texte par page ;
- aucun texte qui en chevauche ou en touche un autre, aucun texte coupé, aucune page qui défile en largeur ;
- aucun paragraphe justifié de moins de 560 px de large, mesuré sur le paragraphe lui-même ;
- les colonnes côte à côte d'un tableau de bord (.bord) finissent ensemble, à 40 px près ;
- sur ordinateur, aucun conteneur qui défile en largeur (le texte y serait coupé par son cadre) ;
- des réglettes lisibles : histogramme d'au moins 3:1 sur son fond, barres visibles, point entier et au-dessus des
  autres marques, étiquettes d'au moins 14 px qui ne se touchent pas et restent dans leur cellule ;
- aucune classe de couleur des données égale au fond, sur le fond sombre et sur le fond clair (contraste d'au moins
  2:1 entre chaque teinte des palettes, chaque aplat de carte et le fond).
Sans navigateur, seul le contrôle des palettes de style.css est fait (palettes()).
Avec --papier, chaque page est aussi contrôlée telle qu'elle s'imprime : règles d'impression appliquées à l'écran, à la
largeur utile d'une page A4 (182 mm, 688 px), chevauchements et textes coupés seulement (l'impression a sa propre
échelle en points).

Lancer, sur le site construit :
    .\\.venv\\Scripts\\python.exe outils\\controle_finition.py _planche.html index.html territoire\\epci\\200090561.html
    .\\.venv\\Scripts\\python.exe outils\\controle_finition.py _planche.html --captures docs\\captures_presentation\\planche
Code de retour 1 si un défaut est trouvé.
"""
import argparse
import functools
import http.server
import json
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

# 1 024 et 883 px : un petit ordinateur et une tablette ou une fenêtre réduite, où la matrice de la fiche se
# chevauchait sans que rien ne le voie (relecture esthétique du 31 octobre 2026)
LARGEURS = {"ordinateur": (1280, 900), "ordinateur_etroit": (1024, 900), "tablette": (883, 900), "telephone": (375, 812)}
PAPIER = (688, 1000)
TAILLES_MAX = 5
SEUIL_DONNEES = 2.0    # contraste minimal d'une classe de couleur des données avec le fond
SEUIL_TEXTE = 4.5      # contraste minimal du texte (registre, 12)


def _lum(h: str) -> float:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contraste(a: str, b: str) -> float:
    x, y = sorted((_lum(a), _lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def jetons(css: str, selecteur: str) -> dict[str, str]:
    """Variables de couleur d'un bloc de style.css (premier bloc dont le sélecteur commence par selecteur)."""
    m = re.search(re.escape(selecteur) + r"[^{]*\{([^}]*)\}", css)
    return dict(re.findall(r"(--[\w-]+):(#[0-9A-Fa-f]{3,6})\b", m.group(1))) if m else {}


def palettes(css: str | None = None) -> list[str]:
    """Défauts des palettes de style.css sur les deux fonds : une classe des données (--r, --d, --c) sous 2:1 du
    fond, un texte (--ink, --muted) sous 4,5:1, une teinte identique au fond."""
    css = css if css is not None else (RACINE / "gabarits" / "style.css").read_text(encoding="utf-8")
    defauts = []
    for nom, sel in (("clair", ':root[data-theme="light"]'), ("sombre", ':root[data-theme="dark"]')):
        t = jetons(css, sel)
        if "--bg" not in t:
            defauts.append(f"fond {nom} : bloc {sel} introuvable ou sans --bg")
            continue
        for v, c in t.items():
            if re.fullmatch(r"--(r\d|d\d|c\d)", v):
                r = contraste(c, t["--bg"])
                if r < SEUIL_DONNEES:
                    defauts.append(f"fond {nom} : {v} {c} à {r:.2f}:1 du fond {t['--bg']}")
            elif v in ("--ink", "--muted"):
                r = contraste(c, t["--bg"])
                if r < SEUIL_TEXTE:
                    defauts.append(f"fond {nom} : texte {v} {c} à {r:.2f}:1 du fond")
    return defauts


def liseres(html: str) -> list[str]:
    """Défauts des cartes : un contour de territoire choisi (class="choisi") sans le liseré de la couleur du fond posé
    dessous (class="choisi-lisere", cartes_presentation.lisere), qui le garde lisible sur les classes foncées
    (contre-vérification esthétique du 31 octobre 2026)."""
    defauts = []
    for svg in re.findall(r'<svg[^>]*class="carte-svg[^"]*"[^>]*>.*?</svg>', html, re.S):
        for m in re.finditer(r'<use href="#([^"]+)"[^>]*class="choisi"', svg):
            if not re.search(r'<use href="#' + re.escape(m.group(1)) + r'"[^>]*class="choisi-lisere"', svg[:m.start()]):
                defauts.append(f"contour choisi sans liseré ({m.group(1)})")
    return defauts


def _serveur(dossier: Path):
    class Muet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    gestion = functools.partial(Muet, directory=str(dossier))
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), gestion)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def _navigateur() -> str:
    from pipeline.site import navigateur
    exe = navigateur()
    if not exe:
        raise RuntimeError("aucun navigateur Edge, Chrome ou Chromium trouvé")
    return exe


def _lancer(exe: str, url: str, largeur: int, hauteur: int, *options) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as profil:
        return subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                               f"--user-data-dir={profil}", f"--window-size={largeur},{hauteur}",
                               "--virtual-time-budget=15000", *options, url],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)


def _cadre(tmp: Path, largeur: int, hauteur: int, recopier: str) -> Path:
    """Page qui porte la page à contrôler dans un cadre de la largeur voulue : le navigateur sans fenêtre ne descend
    pas sous 500 px environ, un cadre de 375 px donne la largeur d'un téléphone. Le bloc pre d'identifiant recopier,
    écrit dans le cadre, est recopié dans la page qui le porte, seule lue par --dump-dom."""
    c = tmp.with_name(f"_cadre{tmp.stem}.html")
    c.write_text(
        '<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#fff}'
        'iframe{border:0;display:block}</style></head><body>'
        f'<iframe id="f" src="{tmp.name}" width="{largeur}" height="{hauteur}" scrolling="no"></iframe><script>'
        'var f=document.getElementById("f");(function attendre(){try{var e=f.contentDocument&&'
        f'f.contentDocument.getElementById("{recopier}");if(e){{var p=document.createElement("pre");p.id="{recopier}";'
        'p.hidden=true;p.textContent=e.textContent;document.body.appendChild(p);return}}catch(x){}'
        'setTimeout(attendre,100)})();</script></body></html>', encoding="utf-8")
    return c


def controler(site: Path, page: str, exe: str, serveur, largeur: int, hauteur: int, theme: str | None = None) -> dict:
    """Résultat du contrôle d'une page à une largeur, lu dans la page elle-même (outils/controle_finition.js)."""
    src = site / page
    tmp = src.with_name(f"_finition_{src.stem}.html")
    html = src.read_text(encoding="utf-8")
    script = (RACINE / "outils" / "controle_finition.js").read_text(encoding="utf-8")
    if theme == "papier":
        # la page telle qu'elle s'imprime : feuille de style dont les règles d'impression valent à l'écran, détails
        # ouverts comme à l'impression
        css = (site / "style.css").read_text(encoding="utf-8").replace("@media print{", "@media all{").replace("@media screen and", "@media print and")
        (site / "_papier.css").write_text(css, encoding="utf-8")
        html = re.sub(r'href="([./]*)style\.css[^"]*"', r'href="\1_papier.css"', html, count=1)
        html = html.replace("</body>", "<script>document.querySelectorAll('details').forEach(function(d){d.open=true});"
                            "window.dispatchEvent(new Event('beforeprint'))</script></body>", 1)
    elif theme:
        html = html.replace("<head>", f"<head><script>try{{localStorage.setItem('theme','{theme}')}}catch(e){{}}</script>", 1)
    tmp.write_text(html.replace("</body>", f"<script>{script}</script></body>", 1), encoding="utf-8")
    cadre = _cadre(tmp, largeur, hauteur, "controle-finition")
    try:
        url = f"http://127.0.0.1:{serveur.server_address[1]}/{cadre.relative_to(site).as_posix()}"
        p = _lancer(exe, url, max(largeur, 600), hauteur, "--dump-dom")
        m = re.findall(r'<pre id="controle-finition" hidden="">(.*?)</pre>', p.stdout, re.S)
        if not m:
            return {"erreur": "résultat introuvable (page trop lente ou script en erreur)"}
        import html as h
        return json.loads(h.unescape(m[-1]))
    finally:
        tmp.unlink(missing_ok=True)
        cadre.unlink(missing_ok=True)
        if theme == "papier":
            (site / "_papier.css").unlink(missing_ok=True)


def defilements_ordinateur(r: dict, largeur: str) -> list[str]:
    """Sur ordinateur, aucun conteneur ne défile en largeur : un texte y serait coupé par son cadre sans que la page
    déborde (onglet « anté mentale » de la barre des domaines, relecture du prototype de fiche resserrée, 31 octobre
    2026, M4). Au téléphone, une barre ou un tableau peut défiler."""
    return [f"défile en largeur sur ordinateur : {d}" for d in r.get("defilements", [])] if largeur == "ordinateur" else []


def _rogner_png(f: Path, largeur: int) -> None:
    """Rogne une capture PNG à sa largeur utile, sans bibliothèque d'image : lecture des lignes, retrait des filtres,
    réécriture sans filtre."""
    import struct
    import zlib
    b = f.read_bytes()
    pos, idat, ihdr = 8, b"", None
    while pos < len(b):
        n, t = struct.unpack(">I4s", b[pos:pos + 8])
        if t == b"IHDR":
            ihdr = b[pos + 8:pos + 8 + n]
        elif t == b"IDAT":
            idat += b[pos + 8:pos + 8 + n]
        pos += 12 + n
    w, h, prof, typ = struct.unpack(">IIBB", ihdr[:10])
    if w <= largeur or prof != 8 or typ not in (2, 6) or ihdr[12] != 0:
        return
    bpp = 3 if typ == 2 else 4
    brut, pas, prec, sortie = zlib.decompress(idat), w * bpp, bytearray(w * bpp), bytearray()
    for y in range(h):
        filtre, cur = brut[y * (pas + 1)], bytearray(brut[y * (pas + 1) + 1:(y + 1) * (pas + 1)])
        for x in range(pas):
            a = cur[x - bpp] if x >= bpp else 0
            c = prec[x - bpp] if x >= bpp else 0
            if filtre == 1:
                cur[x] = (cur[x] + a) & 255
            elif filtre == 2:
                cur[x] = (cur[x] + prec[x]) & 255
            elif filtre == 3:
                cur[x] = (cur[x] + ((a + prec[x]) >> 1)) & 255
            elif filtre == 4:
                p = a + prec[x] - c
                pa, pb, pc = abs(p - a), abs(p - prec[x]), abs(p - c)
                cur[x] = (cur[x] + (a if pa <= pb and pa <= pc else prec[x] if pb <= pc else c)) & 255
        sortie += b"\0" + cur[:largeur * bpp]
        prec = cur
    morceau = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + morceau(b"IHDR", struct.pack(">IIBBBBB", largeur, h, 8, typ, 0, 0, 0))
                  + morceau(b"IDAT", zlib.compress(bytes(sortie), 9)) + morceau(b"IEND", b""))


def capture(site: Path, page: str, exe: str, serveur, largeur: int, cible: Path, theme: str = "dark") -> Path:
    """Capture de la page entière à une largeur, sur le fond choisi (hauteur mesurée dans la page)."""
    src = site / page
    tmp = src.with_name(f"_capture_{src.stem}.html")
    html = src.read_text(encoding="utf-8").replace(
        "<head>", f"<head><script>try{{localStorage.setItem('theme','{theme}')}}catch(e){{}}</script>", 1)
    mesure = ('<script>addEventListener("load",function(){setTimeout(function(){var p=document.createElement("pre");'
              'p.id="hauteur-page";p.hidden=true;p.textContent=document.documentElement.scrollHeight;document.body.appendChild(p)},800)})</script>')
    tmp.write_text(html.replace("</body>", mesure + "</body>", 1), encoding="utf-8")
    cadre = _cadre(tmp, largeur, 900, "hauteur-page")
    base = f"http://127.0.0.1:{serveur.server_address[1]}/"
    try:
        p = _lancer(exe, base + cadre.relative_to(site).as_posix(), max(largeur, 600), 900, "--dump-dom")
        m = re.findall(r'<pre id="hauteur-page" hidden="">(\d+)</pre>', p.stdout)
        hauteur = min(int(m[-1]) if m else 6000, 16000)
        cadre.unlink(missing_ok=True)
        cadre = _cadre(tmp, largeur, hauteur, "rien")
        cible.parent.mkdir(parents=True, exist_ok=True)
        _lancer(exe, base + cadre.relative_to(site).as_posix(), max(largeur, 600), hauteur, f"--screenshot={cible.resolve()}")
        _rogner_png(cible, largeur)
        return cible
    finally:
        tmp.unlink(missing_ok=True)
        cadre.unlink(missing_ok=True)


def main(argv=None) -> int:
    from pipeline.site import SITE
    a = argparse.ArgumentParser(description="Contrôle de finition des pages du site construit")
    a.add_argument("pages", nargs="*", default=["_planche.html"], help="pages, relatives au dossier du site")
    a.add_argument("--site", default=str(SITE))
    a.add_argument("--captures", help="dossier où écrire une capture de chaque page, ordinateur et téléphone")
    a.add_argument("--papier", action="store_true", help="contrôler aussi chaque page telle qu'elle s'imprime")
    args = a.parse_args(argv)
    site = Path(args.site)
    defauts = [f"style.css : {d}" for d in palettes()]
    exe = _navigateur()
    serveur = _serveur(site)
    try:
        for page in args.pages:
            for nom, (l, h) in LARGEURS.items():
                r = controler(site, page, exe, serveur, l, h)
                if "erreur" in r:
                    defauts.append(f"{page}, {nom} : {r['erreur']}")
                    continue
                tailles = [t["px"] for t in r["tailles"]]
                print(f"{page}, {nom} ({l} px) : tailles {tailles}, {len(r['defauts'])} défauts, "
                      f"{len(r['defilements'])} cadres qui défilent")
                if len(tailles) > TAILLES_MAX:
                    defauts.append(f"{page}, {nom} : {len(tailles)} tailles de texte " +
                                   ", ".join(f"{t['px']} px ({t['exemple']})" for t in r["tailles"]))
                defauts += [f"{page}, {nom} : {d}" for d in r["defauts"] + r["couleurs"] + defilements_ordinateur(r, nom)
                            + r.get("reglettes", [])]
                if args.captures:
                    c = capture(site, page, exe, serveur, l, Path(args.captures) / f"{Path(page).stem.strip('_')}_{nom}.png")
                    print("capture", c)
            if args.papier:
                r = controler(site, page, exe, serveur, *PAPIER, theme="papier")
                if "erreur" in r:
                    defauts.append(f"{page}, papier : {r['erreur']}")
                else:
                    print(f"{page}, papier ({PAPIER[0]} px) : {len(r['defauts'])} défauts")
                    defauts += [f"{page}, papier : {d}" for d in r["defauts"]]
    finally:
        serveur.shutdown()
    for page in args.pages:
        defauts += [f"{page} : {d}" for d in liseres((site / page).read_text(encoding="utf-8"))]
    for d in dict.fromkeys(defauts):
        print("DÉFAUT", d)
    print("contrôle de finition :", "aucun défaut" if not defauts else f"{len(defauts)} défauts")
    return 1 if defauts else 0


if __name__ == "__main__":
    sys.exit(main())
