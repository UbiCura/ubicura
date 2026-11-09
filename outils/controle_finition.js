// Contrôle de finition d'une page du site (direction visuelle du 30 octobre 2026), lancé par outils/controle_finition.py
// dans un navigateur sans fenêtre, à 1 280 et à 375 px. Il écrit son résultat en JSON dans un bloc pre caché.
// 1. Tailles de texte : au plus cinq tailles par page (texte HTML visible, hors figures SVG).
// 2. Chevauchements : deux textes qui se chevauchent ou se touchent, un texte coupé par son cadre, une page qui défile
//    en largeur. Les tableaux qui défilent dans leur cadre sont notés à part, ils sont voulus.
// 3. Couleurs : aucune classe de couleur des données égale au fond, sur le fond sombre et sur le fond clair. Chaque
//    variable des palettes (--r, --d, --c) et chaque aplat de carte (hors « aucune donnée ») doit avoir un contraste
//    d'au moins 2:1 avec le fond.
// 4. Lignes lâches : une ligne justifiée dont les mots s'écartent de plus d'une fois et demie l'espace ordinaire,
//    notée par le script de césure (cesure/cesure.js, data-lache) ; elle se corrige dans le texte ou la mise en page.
(async () => {
  const sortie = { tailles: [], defauts: [], defilements: [], couleurs: [] };
  try { if (document.fonts) await document.fonts.ready; } catch (e) {}
  await new Promise(r => setTimeout(r, 400));
  for (let i = 0; i < 300 && window.cesure && document.documentElement.dataset.cesure !== "prete"; i++) await new Promise(r => setTimeout(r, 100));
  const vis = el => {
    if (el.checkVisibility && !el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) return false;
    const s = getComputedStyle(el); if (s.visibility === "hidden" || s.display === "none" || +s.opacity === 0) return false;
    const r = el.getBoundingClientRect(); return r.width > 1 && r.height > 1;
  };
  const cache = el => el.closest(".cache,[hidden],.seul-papier,template,noscript");
  const nom = el => (el.id ? "#" + el.id : el.tagName.toLowerCase() + (typeof el.className === "string" && el.className.trim() ? "." + el.className.trim().split(/\s+/).join(".") : "")) + " « " + (el.textContent || "").replace(/­/g, "").trim().slice(0, 40) + " »";

  // 1. tailles de texte
  const tailles = new Map();
  const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const feuilles = [];
  while (tw.nextNode()) {
    const n = tw.currentNode; if (!n.textContent.trim()) continue;
    const p = n.parentElement; if (!p || p.closest("svg,script,style,pre#controle-finition") || cache(p) || !vis(p)) continue;
    const t = Math.round(parseFloat(getComputedStyle(p).fontSize));
    if (!tailles.has(t)) tailles.set(t, nom(p));
    const rg = document.createRange(); rg.selectNodeContents(n);
    // le texte qu'un cadre cache (résumé coupé à deux lignes, overflow hidden) n'est pas lu : seules les lignes visibles
    // comptent (7 novembre 2026, résumés repliés de l'atlas)
    let clip = null;
    for (let e = p; e && e !== document.body; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (/hidden|clip/.test(s.overflowY) || (s.webkitLineClamp && s.webkitLineClamp !== "none")) { clip = e.getBoundingClientRect(); break; }
    }
    for (const r of rg.getClientRects()) {
      if (r.width <= 2 || r.height <= 2) continue;
      if (clip && (r.top >= clip.bottom - 1 || r.bottom <= clip.top + 1)) continue;
      feuilles.push({ r, p, t: n.textContent.replace(/­/g, "").trim().slice(0, 30) });
    }
  }
  sortie.tailles = [...tailles.entries()].sort((a, b) => a[0] - b[0]).map(([t, ex]) => ({ px: t, exemple: ex }));

  // 2. chevauchements, contacts, coupures
  document.querySelectorAll("body *").forEach(el => {
    if (!vis(el) || el.closest("svg") || cache(el)) return;
    const s = getComputedStyle(el);
    if (el.scrollWidth > el.clientWidth + 1 && /hidden|clip/.test(s.overflowX) && s.textOverflow !== "ellipsis") sortie.defauts.push("coupé en largeur " + nom(el));
    // un résumé coupé à dessein (line-clamp, points de suspension) n'est pas un texte coupé
    if (el.scrollHeight > el.clientHeight + 1 && /hidden|clip/.test(s.overflowY) && el.clientHeight > 0 && !(s.webkitLineClamp && s.webkitLineClamp !== "none")) sortie.defauts.push("coupé en hauteur " + nom(el));
    if (el.scrollWidth > el.clientWidth + 1 && /auto|scroll/.test(s.overflowX) && el.tagName !== "BODY" && el.tagName !== "HTML") sortie.defilements.push(nom(el));
  });
  if (document.documentElement.scrollWidth > innerWidth + 1) sortie.defauts.push("la page défile en largeur : " + document.documentElement.scrollWidth + " px pour " + innerWidth);
  const inl = el => getComputedStyle(el).display.startsWith("inline");
  feuilles.sort((a, b) => a.r.top - b.r.top);
  for (let i = 0; i < feuilles.length; i++) for (let j = i + 1; j < feuilles.length; j++) {
    const a = feuilles[i], b = feuilles[j];
    if (b.r.top > a.r.bottom + 2) break;   // triées par le haut : plus rien ne peut toucher a
    if (a.p === b.p) continue;
    const ox = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left);
    const oy = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
    if (ox > 1 && oy > 3) sortie.defauts.push("chevauchement « " + a.t + " » / « " + b.t + " »");
    else if (oy > 3 && ox > -2 && ox <= 1 && !a.p.contains(b.p) && !b.p.contains(a.p) && !(inl(a.p) && inl(b.p) && a.p.parentElement === b.p.parentElement))
      sortie.defauts.push("se touchent « " + a.t + " » / « " + b.t + " » (" + ox.toFixed(1) + " px)");
  }
  document.querySelectorAll("svg").forEach(svg => {
    if (!vis(svg) || cache(svg)) return;
    const ts = [...svg.querySelectorAll("text")].filter(t => t.textContent.trim()).map(t => ({ t, r: t.getBoundingClientRect() })).filter(o => o.r.width > 0);
    for (let i = 0; i < ts.length; i++) for (let j = i + 1; j < ts.length; j++) {
      const a = ts[i].r, b = ts[j].r;
      if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 0 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1)
        sortie.defauts.push("figure, chevauchement « " + ts[i].t.textContent.trim().slice(0, 25) + " » / « " + ts[j].t.textContent.trim().slice(0, 25) + " »");
    }
  });

  // 3. couleurs des données contre le fond, sur les deux fonds
  const rgb = c => { const d = document.createElement("i"); d.style.color = c; document.body.appendChild(d); const v = getComputedStyle(d).color; d.remove(); return (v.match(/[\d.]+/g) || []).slice(0, 3).map(Number); };
  const lum = c => c.map(x => { x /= 255; return x <= .03928 ? x / 12.92 : Math.pow((x + .055) / 1.055, 2.4); }).reduce((s, x, i) => s + x * [.2126, .7152, .0722][i], 0);
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
  const VARS = ["--r0", "--r1", "--r2", "--r3", "--r4", "--r5", "--d0", "--d1", "--d2", "--d3", "--d4", "--d5", "--d6", "--c1", "--c2", "--c3", "--c4", "--c5", "--c6"];
  const racine = document.documentElement, avant = racine.getAttribute("data-theme");
  for (const theme of ["dark", "light"]) {
    racine.setAttribute("data-theme", theme);
    const st = getComputedStyle(racine), fond = rgb(st.getPropertyValue("--bg").trim() || getComputedStyle(document.body).backgroundColor);
    for (const v of VARS) {
      const c = st.getPropertyValue(v).trim(); if (!c) continue;
      const r = ratio(rgb(c), fond);
      if (r < 2) sortie.couleurs.push(`fond ${theme === "dark" ? "sombre" : "clair"} : ${v} (${c}) à ${r.toFixed(2)}:1 du fond`);
    }
    // aplats des cartes : fond du bloc qui porte la carte
    const vide = rgb(st.getPropertyValue("--nodata").trim()).join();
    let mauvais = 0, exemple = "";
    document.querySelectorAll("svg path.aplat, svg path[data-code]").forEach(p => {
      if (!vis(p)) return;
      const f = getComputedStyle(p).fill; if (!f || f === "none" || f.startsWith("url") || rgb(f).join() === vide) return;
      let b = p.closest(".fond-clair,.fond-sombre") || document.body;
      const fb = rgb(getComputedStyle(b).getPropertyValue("--bg").trim());
      const r = ratio(rgb(f), fb);
      if (r < 2) { mauvais++; exemple = exemple || `${f} à ${r.toFixed(2)}:1`; }
    });
    if (mauvais) sortie.couleurs.push(`fond ${theme === "dark" ? "sombre" : "clair"} : ${mauvais} aplats de carte presque de la couleur du fond (${exemple})`);
  }
  if (avant === null) racine.removeAttribute("data-theme"); else racine.setAttribute("data-theme", avant);
  // 5. lisibilité des réglettes (relecture du 31 octobre 2026) : histogramme d'au moins 3:1 sur son fond, assez haut,
  //    barres visibles ; point présent, entier, au-dessus des autres marques et pas collé au bord de l'axe ; étiquettes
  //    d'au moins 14 px, qui ne se touchent pas et ne sortent pas de leur cellule
  sortie.reglettes = [];
  const fondDe = el => {
    for (let e = el; e; e = e.parentElement) {
      const m = (getComputedStyle(e).backgroundColor.match(/[\d.]+/g) || []).map(Number);
      if (m.length === 3 || (m.length === 4 && m[3] > .5)) return m.slice(0, 3);
    }
    return rgb(getComputedStyle(racine).getPropertyValue("--bg").trim());
  };
  const z = el => +getComputedStyle(el).zIndex || 0;
  document.querySelectorAll(".rg").forEach(rg => {
    if (!vis(rg) || cache(rg)) return;
    const qui = ((rg.closest("tr") && rg.closest("tr").querySelector("th") || {}).textContent || rg.closest("figure") && "réglette type" || "").replace(/­/g, "").trim().slice(0, 30);
    const dire = m => sortie.reglettes.push("réglette « " + qui + " » : " + m);
    const R = rg.getBoundingClientRect(), hist = rg.querySelector(".rg-hist"), chemin = hist && hist.querySelector("path");
    if (chemin) {
      const H = hist.getBoundingClientRect(), c = ratio(rgb(getComputedStyle(chemin).fill), fondDe(rg));
      if (c < 3) dire("histogramme à " + c.toFixed(2) + ":1 du fond");
      if (H.height < 14) dire("histogramme de " + H.height.toFixed(0) + " px de haut");
      const hs = [...(chemin.getAttribute("d") || "").matchAll(/v-([\d.]+)/g)].map(m => +m[1] / 18 * H.height);
      if (hs.length && Math.min(...hs) < .9) dire("barre de " + Math.min(...hs).toFixed(1) + " px de haut, invisible");
      const axe = rg.querySelector(".rg-axe");
      if (!axe || ratio(rgb(getComputedStyle(axe).backgroundColor), fondDe(rg)) < 3) dire("axe absent ou trop pâle sous les barres");
      const nb = (hist.viewBox && hist.viewBox.baseVal && hist.viewBox.baseVal.width) || 30;
      if (H.width / nb * .76 < 1.5) dire("barres de " + (H.width / nb * .76).toFixed(1) + " px de large");
    }
    const pt = rg.querySelector(".rg-pt");
    if (!rg.classList.contains("sans")) {
      if (!pt) dire("point absent");
      else {
        const p = pt.getBoundingClientRect();
        if (p.width < 10) dire("point de " + p.width.toFixed(0) + " px");
        if (p.left < R.left - .5 || p.right > R.right + .5) dire("point qui dépasse de l'axe");
        [...rg.querySelectorAll(".rg-ens,.rg-med,.rg-chev")].forEach(m => { if (z(m) >= z(pt)) dire("point sous une autre marque"); });
        for (let e = rg.parentElement; e && e !== document.body; e = e.parentElement) {
          const s = getComputedStyle(e);
          if (/hidden|clip|auto|scroll/.test(s.overflowX + s.overflowY)) {
            const c = e.getBoundingClientRect();
            if (p.left < c.left - .5 || p.right > c.right + .5 || p.top < c.top - .5 || p.bottom > c.bottom + .5) dire("point coupé par son cadre");
            break;
          }
        }
      }
    }
    const labs = [...rg.querySelectorAll(".rg-lab")].filter(vis), cel = rg.closest("td,figure") || rg.parentElement, C = cel.getBoundingClientRect();
    labs.forEach((l, i) => {
      const t = parseFloat(getComputedStyle(l).fontSize), a = l.getBoundingClientRect();
      if (t < 14) dire("étiquette « " + l.textContent + " » de " + t + " px");
      if (a.left < C.left - .5 || a.right > C.right + .5) dire("étiquette « " + l.textContent + " » hors de sa cellule");
      if (pt) { const p = pt.getBoundingClientRect(); if (Math.min(a.right, p.right) - Math.max(a.left, p.left) > 0 && Math.min(a.bottom, p.bottom) - Math.max(a.top, p.top) > 0) dire("étiquette « " + l.textContent + " » sur le point"); }
      labs.slice(i + 1).forEach(m => {
        const b = m.getBoundingClientRect();
        if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > -4 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 0) dire("étiquettes qui se touchent");
      });
    });
  });
  sortie.reglettes = [...new Set(sortie.reglettes)].slice(0, 60);
  // 7. colonnes du tableau de bord d'une fiche : côte à côte, elles finissent ensemble, à 40 px près (relecture
  //    esthétique du 31 octobre 2026, M5 : 236 px de vide sous la colonne de gauche)
  //    Mesurées après le chargement complet et le placement (data-bord-place), sur chaque couche de la carte. La carte
  //    ne rétrécit jamais, et la colonne de droite n'est jamais vide : à 40 px près dans les deux sens (relectures des
  //    fiches construites du 1er novembre 2026).
  if (document.querySelector(".bord")) {
    if (document.readyState !== "complete") await new Promise(r => addEventListener("load", r, { once: true }));
    await new Promise(r => setTimeout(r, 300));
  }
  const colonnes = quoi => document.querySelectorAll(".bord").forEach(b => {
    if (!vis(b) || getComputedStyle(b).gridTemplateColumns.trim().split(/\s+/).length < 2) return;
    const g = b.querySelector(".bord-carte"), d = b.querySelector(".en-bref");
    if (!g || !d || !vis(g) || !vis(d)) return;
    const e = d.getBoundingClientRect().bottom - g.getBoundingClientRect().bottom;
    if (Math.abs(e) > 40)
      sortie.defauts.push("colonnes du tableau de bord qui finissent à " + Math.round(Math.abs(e)) + " px l'une de l'autre" + quoi);
  });
  colonnes("");
  // 8. couche des secteurs : chaque code dans le cadre de la carte, aucun qui en touche un autre (défaut M7)
  for (const bt of document.querySelectorAll('.carte-terr button[data-couche="secteurs"]')) {
    if (!vis(bt)) continue;
    const avant = bt.parentElement.querySelector('button[aria-pressed="true"]');
    bt.click(); await new Promise(r => setTimeout(r, 250));
    const svg = bt.closest(".carte-terr").querySelector(".carte-fig svg.carte-svg");
    if (svg) {
      const cadre = svg.getBoundingClientRect(), ts = [...svg.querySelectorAll("g.etiquettes text")].map(t => [t, t.getBoundingClientRect()]);
      ts.forEach(([t, r]) => {
        if (r.width && (r.left < cadre.left - 1 || r.right > cadre.right + 1 || r.top < cadre.top - 1 || r.bottom > cadre.bottom + 1))
          sortie.defauts.push("code de secteur hors du cadre « " + t.textContent + " »");
      });
      for (let i = 0; i < ts.length; i++) for (let j = i + 1; j < ts.length; j++) {
        const a = ts[i][1], c = ts[j][1];
        if (a.width && c.width && a.left < c.right && c.left < a.right && a.top < c.bottom && c.top < a.bottom)
          sortie.defauts.push("codes de secteur qui se chevauchent « " + ts[i][0].textContent + " » / « " + ts[j][0].textContent + " »");
      }
    }
    colonnes(", couche des secteurs");
    if (avant) { avant.click(); await new Promise(r => setTimeout(r, 150)); }
  }
  // 9. tableaux de la fiche : là où leur en-tête est masqué (téléphone), la cellule de la position dit son ensemble,
  //    et l'écart écrit est sur la même ligne qu'elle (relecture des fiches construites, 1er novembre 2026, P0)
  document.querySelectorAll("table.ligne-type").forEach(tb => {
    const th = tb.querySelector("thead");
    if (!vis(tb) || (th && vis(th))) return;
    tb.querySelectorAll("tbody td.pos").forEach(c => {
      if (!vis(c)) return;
      const t = c.innerText.replace(/\s+/g, " ").trim();
      if (t && !/ des (intercommunalités|départements|régions)| (tous|toutes) les autres /.test(t + " "))
        sortie.defauts.push("position sans son ensemble au téléphone « " + t.slice(0, 50) + " »");
      const ec = [...c.closest("tr").querySelectorAll(".ec")].filter(vis);
      if (ec.some(x => !c.contains(x))) sortie.defauts.push("écart et position sur deux lignes « " + t.slice(0, 50) + " »");
    });
  });
  // 6. justifié étroit : un paragraphe justifié de moins de 560 px, mesuré sur lui-même et non sur sa colonne
  //    (rivières dans les « Comment lire » bornés par la mesure, relecture esthétique du 31 octobre 2026)
  document.querySelectorAll("main p,main li,main dd").forEach(b => {
    if (!vis(b) || cache(b) || getComputedStyle(b).textAlign !== "justify") return;
    const w = b.getBoundingClientRect().width;
    if (w < 559) sortie.defauts.push("justifié sur " + Math.round(w) + " px « " + b.textContent.replace(/­/g, "").trim().slice(0, 40) + " »");
  });
  document.querySelectorAll("[data-lache]").forEach(b => {
    if (cache(b) || !vis(b)) return;
    JSON.parse(b.dataset.lache).forEach(([x, t]) => sortie.defauts.push("ligne lâche (" + String(x).replace(".", ",") + " fois l'espace) « " + t + " »"));
  });
  // 10. « mais » ne commence jamais une cellule ni une ligne de position : ce à quoi il s'oppose, l'écart ou l'ensemble,
  //     est écrit devant (relecture v2 des fiches construites, 1er novembre 2026 : 1 814 cellules)
  document.querySelectorAll("table.ligne-type td.pos, table.matrice .m-pos").forEach(c => {
    if (!vis(c)) return;
    const t = c.innerText.replace(/\s+/g, " ").trim();
    if (/^mais /i.test(t)) sortie.defauts.push("cellule qui commence par « mais » « " + t.slice(0, 50) + " »");
  });
  // 11. bord droit (règle 8, Lucas, 6 novembre 2026) : un paragraphe large s'arrête au même bord droit que la figure,
  //     le tableau ou l'encadré de sa colonne, à 8 px près. Un seul défaut par page, avec le compte et un exemple.
  {
    const blocs = "figure,table,.encadre,.defile,.graphique";
    let n = 0, ex = "", ecart = 0;
    const parents = new Set([...document.querySelectorAll("main " + blocs.split(",").join(",main "))].filter(vis).map(f => f.parentElement));
    parents.forEach(par => {
      const figs = [...par.children].filter(e => e.matches(blocs) && vis(e) && !cache(e));
      if (!figs.length) return;
      const bord = Math.max(...figs.map(f => f.getBoundingClientRect().right));
      // le sous-titre des pages est sur les sept colonnes de la grille (Lucas, 7 novembre 2026, proposition 1)
      [...par.children].filter(e => e.matches("p,ul,ol,.comment-lire,.source,.note") && !e.matches(".chapeau:not(.version)") && vis(e) && !cache(e)).forEach(p => {
        const r = p.getBoundingClientRect();
        if (r.width < 300) return;                       // une phrase courte ou une colonne étroite n'est pas mesurée
        const d = bord - r.right;
        if (d > 8) { n++; if (d > ecart) { ecart = d; ex = nom(p); } }
      });
    });
    if (n) sortie.defauts.push(`bord droit : ${n} paragraphe(s) qui s'arrêtent avant la figure de leur colonne, jusqu'à ${Math.round(ecart)} px (${ex})`);
  }
  // 11 bis. pas de colonne de lecture étroite (Lucas, 7 novembre 2026, capture A) : un texte courant d'une colonne large
  //     n'est pas bridé par une largeur maximale qui l'arrête avant le bord de sa colonne, même sans figure à côté
  //     (7 novembre 2026, chapeaux des pages de domaine bridés à 64 caractères, vus par Lucas)
  {
    let n = 0, ex = "", ecart = 0;
    document.querySelectorAll("main p,main ul,main ol,main .comment-lire,main .source,main .note").forEach(p => {
      // le sous-titre des pages est sur les sept colonnes de la grille (Lucas, 7 novembre 2026, proposition 1)
      if (!vis(p) || cache(p) || p.matches(".chapeau") || getComputedStyle(p).maxWidth === "none") return;
      const par = p.parentElement, sp = getComputedStyle(par), rp = par.getBoundingClientRect();
      const droite = rp.right - parseFloat(sp.paddingRight) - parseFloat(sp.borderRightWidth);
      const largeur = droite - rp.left - parseFloat(sp.paddingLeft) - parseFloat(sp.borderLeftWidth);
      const r = p.getBoundingClientRect();
      if (largeur < 560 || r.width < 300) return;     // colonne étroite ou phrase courte, laissée à sa mise en page
      // une phrase d'une seule ligne (ligne de version d'un rapport) ne bute pas sur sa largeur maximale
      if (r.height < 1.8 * (parseFloat(getComputedStyle(p).lineHeight) || 24)) return;
      const d = droite - r.right;
      if (d > 8) { n++; if (d > ecart) { ecart = d; ex = nom(p); } }
    });
    if (n) sortie.defauts.push(`colonne étroite : ${n} texte(s) bridés avant le bord de leur colonne, jusqu'à ${Math.round(ecart)} px (${ex})`);
  }
  // 11 quater. un texte ne touche pas le bord gauche ou droit du cadre qui le contient (7 novembre 2026, « Comment
  //     lire » de la carte d'« Autour d'un lieu », collé au filet de son encadré, vu par Lucas) : 4 px au moins entre
  //     le texte et un bord tracé de l'un des trois éléments qui l'entourent
  {
    let n = 0, ex = "";
    const trace = (st, cote) => parseFloat(st[`border${cote}Width`]) > 0 && st[`border${cote}Style`] !== "none" && !/rgba\(0, 0, 0, 0\)|transparent/.test(st[`border${cote}Color`]);
    document.querySelectorAll("main p, main li, main .comment-lire").forEach(p => {
      if (!vis(p) || cache(p) || !p.textContent.trim() || p.closest("table,svg,nav,.tip")) return;
      // bords du texte lui-même, retrait intérieur compris
      const b = p.getBoundingClientRect(), sp = getComputedStyle(p);
      const r = {left: b.left + parseFloat(sp.paddingLeft) + parseFloat(sp.borderLeftWidth),
                 right: b.right - parseFloat(sp.paddingRight) - parseFloat(sp.borderRightWidth)};
      let a = p.parentElement;
      for (let k = 0; k < 3 && a && a !== document.body; k++, a = a.parentElement) {
        const st = getComputedStyle(a), ra = a.getBoundingClientRect();
        const g = trace(st, "Left") ? r.left - (ra.left + parseFloat(st.borderLeftWidth)) : 99;
        const d = trace(st, "Right") ? (ra.right - parseFloat(st.borderRightWidth)) - r.right : 99;
        if (g < 4 || d < 4) { n++; ex = ex || nom(p); break; }
      }
    });
    if (n) sortie.defauts.push(`texte collé au bord de son cadre : ${n} bloc(s) (${ex})`);
  }
  // 11 quinquies. l'atlas mène à la fiche du territoire choisi (promesse de l'accueil, demande de Lucas du 2 novembre
  //     2026 ; l'encadré ne menait qu'aux rapports, relevé par l'audit de la navigation du 8 novembre)
  if (/atlas\.html$/.test(location.pathname.replace(/_finition_atlas[^/]*\.html$/, "atlas.html")) && document.getElementById("tip")) {
    const t = [...document.querySelectorAll("svg path")].find(e => { const r = e.getBoundingClientRect(); return r.width > 8 && r.height > 8 && r.top >= 0 && r.bottom <= innerHeight; });
    if (t) {
      const b = t.getBoundingClientRect();
      t.dispatchEvent(new MouseEvent("click", {bubbles: true, clientX: b.x + b.width / 2, clientY: b.y + b.height / 2}));
      if (!document.querySelector('a.lien-fiche[href*="territoire/"]')) sortie.defauts.push("atlas : l'encadré du territoire choisi ne mène pas à sa fiche complète");
    }
  }
  // 11 sexies. une valeur n'est jamais barrée par un trait de repère en pointillé (règle 17 ; 17 valeurs des figures en
  //     escalier l'étaient, relevé le 8 novembre 2026)
  {
    let n = 0, ex = "";
    document.querySelectorAll("main svg").forEach(svg => {
      if (!vis(svg)) return;
      const traits = [...svg.querySelectorAll("line[stroke-dasharray], path[stroke-dasharray]")].map(l => l.getBoundingClientRect())
        .filter(r => r.height <= 2 && r.width > 20);
      if (!traits.length) return;
      svg.querySelectorAll("text").forEach(t => {
        if (!t.textContent.trim() || getComputedStyle(t).display === "none") return;
        const r = t.getBoundingClientRect();
        if (!r.width) return;
        // boîte du texte resserrée sur les chiffres (le haut et le bas de la boîte sont vides)
        const h = r.top + r.height * .25, b = r.bottom - r.height * .2;
        if (traits.some(l => l.top >= h && l.top <= b && l.left < r.right - 1 && l.right > r.left + 1)) { n++; ex = ex || `« ${t.textContent.trim()} »`; }
      });
    });
    if (n) sortie.defauts.push(`valeur barrée par un trait de repère : ${n} texte(s) (${ex})`);
  }
  // 11 ter. l'infobulle d'une carte tient entière à l'écran, son tableau compris (7 novembre 2026, atlas, médecins
  //     spécialistes : la colonne « Écart » débordait de l'infobulle et sortait de l'écran, vu par Lucas). Survol de
  //     douze territoires répartis sur la carte, aux deux bords compris.
  {
    const tip = document.getElementById("tip");
    if (tip) {
      const terr = [...document.querySelectorAll("svg path")].filter(e => { const r = e.getBoundingClientRect(); return r.width > 3 && r.height > 3 && r.top >= 0 && r.bottom <= innerHeight; });
      const W = document.documentElement.clientWidth, H = innerHeight, pb = [];
      const choix = terr.length ? Array.from({length: Math.min(12, terr.length)}, (_, k) => terr[Math.floor(k * (terr.length - 1) / Math.max(1, Math.min(12, terr.length) - 1))]) : [];
      choix.forEach(p => {
        const b = p.getBoundingClientRect(), o = {bubbles: true, clientX: b.x + b.width / 2, clientY: b.y + b.height / 2};
        ["mouseover", "mouseenter", "mousemove"].forEach(t => p.dispatchEvent(new MouseEvent(t, o)));
        if (getComputedStyle(tip).opacity === "0" || !tip.textContent.trim()) return;
        const r = tip.getBoundingClientRect();
        if (r.left < 0 || r.right > W + 1 || r.top < 0 || r.bottom > H + 1 || tip.scrollWidth > tip.clientWidth + 1)
          pb.push(`${Math.round(r.left)}-${Math.round(r.right)} sur ${W} px, ${Math.round(r.top)}-${Math.round(r.bottom)} sur ${H} px`);
        ["mouseout", "mouseleave"].forEach(t => p.dispatchEvent(new MouseEvent(t, o)));
      });
      if (pb.length) sortie.defauts.push(`infobulle coupée par le bord de l'écran ou par sa propre largeur : ${pb.length} survol(s), ${pb[0]}`);
    }
  }
  // 12. tailles du texte courant, par rôle (texte, tableaux et notes), lues par outils/controle_finition.py en papier :
  //     deux tailles au plus dans les rapports imprimés (Lucas, 6 novembre 2026)
  {
    const role = {};
    document.querySelectorAll("main p, main li, main dd, main td, main th, main figcaption, main .source, main .note").forEach(e => {
      if (!vis(e) || cache(e) || e.closest("svg,nav,header,footer,.sommaire,.couverture") || !e.textContent.trim()) return;
      const t = Math.round(parseFloat(getComputedStyle(e).fontSize) * 10) / 10;
      role[t] = role[t] || nom(e);
    });
    sortie.tailles_texte = Object.entries(role).map(([px, exemple]) => ({ px: +px, exemple })).sort((a, b) => a.px - b.px);
  }
  sortie.defauts = [...new Set(sortie.defauts)].slice(0, 60);
  sortie.defilements = [...new Set(sortie.defilements)].slice(0, 20);
  const pre = document.createElement("pre"); pre.id = "controle-finition"; pre.hidden = true;
  pre.textContent = JSON.stringify(sortie); document.body.appendChild(pre);
})();
