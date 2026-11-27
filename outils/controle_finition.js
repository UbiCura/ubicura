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
  // le texte d'aide d'un champ tient dans le champ, sans être coupé (« Commune, code postal, indicateu » de l'accueil
  // au téléphone, 26 novembre 2026) : mesuré dans la police du champ, contre sa largeur utile
  const aideTronquee = el => {
    if (el.tagName !== "INPUT" || !el.placeholder || el.value || !el.clientWidth) return;
    const s = getComputedStyle(el), c = (window.__mesureAide = window.__mesureAide || document.createElement("canvas")).getContext("2d");
    c.font = `${s.fontStyle} ${s.fontWeight} ${s.fontSize} ${s.fontFamily}`;
    const utile = el.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight) - (parseFloat(s.textIndent) || 0);
    const l = c.measureText(el.placeholder).width;
    if (l > utile + .5) sortie.defauts.push(`texte d'aide tronqué « ${el.placeholder} » (${Math.round(l)} px pour ${Math.round(utile)})`);
  };
  // étiquettes d'une même réglette qui se touchent, telles que la page les montre au lecteur. Mesuré d'abord au
  // chargement, avant tout clic : les contrôles qui suivent ouvrent des infobulles et replacent les étiquettes
  // (etiquettesReglettes), ce qui masquait « aucun : 40 % » sur « ensemble 2,4 » des fiches (audit du 25 novembre 2026)
  const etiquettesQuiSeTouchent = quand => {
    const vus = [];
    document.querySelectorAll(".rg").forEach(rg => {
      if (!vis(rg) || cache(rg)) return;
      const labs = [...rg.querySelectorAll(".rg-lab")].filter(vis);
      labs.forEach((l, i) => labs.slice(i + 1).forEach(m => {
        const a = l.getBoundingClientRect(), b = m.getBoundingClientRect();
        if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > -4 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 0) {
          const qui = ((rg.closest("tr") && rg.closest("tr").querySelector("th") || {}).textContent || rg.closest("figure") && "réglette type" || "").replace(/­/g, "").trim().slice(0, 30);
          vus.push(`réglette « ${qui} » : étiquettes « ${l.textContent.trim()} » et « ${m.textContent.trim()} » qui se touchent ${quand}`);
        }
      }));
    });
    return vus;
  };
  // une image dessinée, pour que les observateurs de taille de la page aient replacé ce qu'ils suivent (sans fenêtre,
  // une image peut ne jamais venir : 200 ms au plus)
  await new Promise(r => { requestAnimationFrame(() => requestAnimationFrame(r)); setTimeout(r, 200); });
  const reglettesAuChargement = etiquettesQuiSeTouchent("au chargement");
  // la page suit d'elle-même un changement de largeur des étiquettes, sans attendre un événement : la police arrivée
  // après la première mesure les élargissait et rien ne les replaçait (audit du 25 novembre 2026). Les étiquettes sont
  // élargies un instant, comme par une autre police, puis rendues ; elles ne doivent se toucher à aucun des deux moments.
  if (document.querySelector(".rg .rg-aucun")) {
    // la page a deux secondes pour replacer ses étiquettes (sans fenêtre, sous la charge de plusieurs navigateurs, une
    // image peut tarder) : seul compte ce qui se touche encore au bout de ce délai
    const stable = async quand => { let d = []; for (let i = 0; i < 20; i++) { await new Promise(r => setTimeout(r, 100)); d = etiquettesQuiSeTouchent(quand); if (!d.length) break; } return d; };
    const st = document.createElement("style");
    st.textContent = ".rg-lab{letter-spacing:.25em}";
    document.head.appendChild(st);
    reglettesAuChargement.push(...await stable("quand leur police s'élargit"));
    st.remove();
    reglettesAuChargement.push(...await stable("quand leur police revient"));
  }
  // 0. fiche, « Tous les indicateurs de ce territoire » et tableau complet (étape 2 des portes d'entrée, 15 novembre
  //    2026) : chargés, le compte de la porte égal aux lignes du tableau, chaque raccourci de domaine égal à son domaine,
  //    chaque lien vers une page d'indicateur porte « → », chaque lien vers une ligne de la fiche porte « ↓ », chaque
  //    résultat de la recherche mène à un élément qui existe. Le tableau est ensuite ouvert en entier, pour que les
  //    contrôles qui suivent le lisent aussi.
  const porte = document.getElementById("porte");
  if (porte) {
    for (let i = 0; i < 100 && !porte.classList.contains("pret") && !porte.querySelector(".p-attente")?.textContent; i++) await new Promise(r => setTimeout(r, 100));
    if (!porte.classList.contains("pret")) sortie.defauts.push("tableau complet de la fiche non chargé : " + (porte.querySelector(".p-attente")?.textContent || "délai dépassé"));
    else {
      const lignes = document.querySelectorAll("#tout-terr table.tt tr[id]").length;
      const nb = ((document.querySelector("[data-compte-tout]") || {}).textContent || "").match(/\d+/g) || [];
      const somme = nb.reduce((s, x) => s + (+x), 0);
      if (!lignes || somme !== lignes) sortie.defauts.push(`compte de « Tous les indicateurs » (${somme}) différent des lignes du tableau complet (${lignes})`);
      porte.querySelectorAll(".p-doms a[data-aller]").forEach(a => {
        const d = document.getElementById(a.dataset.aller), n = d && d.querySelectorAll("tr[id]").length;
        const k = +(((a.parentElement.querySelector(":scope > span") || {}).textContent || "").match(/^\d+/) || [NaN])[0];
        if (!d || n !== k) sortie.defauts.push(`raccourci « ${a.textContent.replace(/[↓,].*$/, "").trim()} » : ${k} annoncés, ${n} lignes dans le tableau`);
      });
      const q = document.getElementById("q-fiche");
      for (const m of ["pour", "psy", "taux"]) {
        q.value = m; q.dispatchEvent(new Event("input"));
        document.querySelectorAll("#r-fiche a[data-aller]").forEach(a => { if (!document.getElementById(a.dataset.aller)) sortie.defauts.push(`résultat de la recherche dans la fiche sans cible : « ${a.textContent.trim().slice(0, 40)} »`); });
      }
      q.value = ""; q.dispatchEvent(new Event("input"));
      // l'écart du tableau complet a la couleur de la réglette de la même ligne de la fiche (haut, bas ou neutre)
      const coul = el => el.classList.contains("haut") ? "haut" : el.classList.contains("bas") ? "bas" : "neutre";
      const vus = new Set();
      document.querySelectorAll(".fiche tr[data-ind][id] .rg").forEach(rg => {
        const tr = rg.closest("tr"); if (tr.closest("#tout-terr")) return;
        const i = tr.dataset.ind, c = i.indexOf("prof:") === 0 ? i.split(":").slice(0, 2).join(":") : i;
        if (vus.has(c)) return; vus.add(c);
        const ec = document.querySelector("#tt-" + c.replace(/[:_]/g, "-") + " .ec"); if (!ec) return;
        if (coul(ec) !== coul(rg)) sortie.defauts.push(`écart de « ${tr.dataset.titre || c} » : ${coul(ec)} dans le tableau complet, ${coul(rg)} sur la fiche`);
      });
      // relecture indépendante du 15 novembre 2026 : la fourchette de la fiche reprise sous la valeur du tableau ; chaque
      // ligne de la fiche absente du tableau se trouve par la recherche ; le repli du téléphone dit le nombre de domaines ;
      // chaque domaine du tableau a son « Citer et exporter »
      document.querySelectorAll(".fiche tr[data-ind][id] td.v .note.ic").forEach(n => {
        const tr = n.closest("tr"); if (tr.closest("#tout-terr")) return;
        const td = document.querySelector("#tt-" + tr.dataset.ind.replace(/[:_]/g, "-") + " td.v"), ic = n.textContent.replace(/\s+/g, " ").trim();
        if (td && !td.textContent.replace(/\s+/g, " ").includes(ic)) sortie.defauts.push(`fourchette « ${ic} » de « ${tr.dataset.titre || tr.dataset.ind} » absente du tableau complet`);
      });
      const cle = i => i.indexOf("prof:") === 0 ? i.split(":").slice(0, 2).join(":") : i;
      document.querySelectorAll(".fiche tr[data-ind][id]").forEach(tr => {
        if (tr.closest("#tout-terr") || document.getElementById("tt-" + cle(tr.dataset.ind).replace(/[:_]/g, "-"))) return;
        const nm = tr.dataset.titre || ""; if (!nm) return;
        q.value = nm; q.dispatchEvent(new Event("input"));
        if (![...document.querySelectorAll("#r-fiche a[data-aller]")].some(a => a.dataset.aller === tr.id)) sortie.defauts.push(`ligne « ${nm} » de la fiche introuvable par la recherche dans la fiche`);
      });
      q.value = ""; q.dispatchEvent(new Event("input"));
      const sm = document.querySelector("#porte .p-doms-d > summary");
      if (sm && !/\d+\s+domaines?$/.test(sm.textContent.replace(/­/g, "").trim())) sortie.defauts.push("repli des domaines sans leur nombre : « " + sm.textContent.trim() + " »");
      document.querySelectorAll("#tout-terr details.tt-domd").forEach(d => { if (!d.querySelector(".citer-encadre")) sortie.defauts.push("domaine du tableau complet sans « Citer et exporter » : " + d.id); });
      // jamais un mot répété dans la valeur d'une ligne (défaut vu le 15 novembre 2026, « aucun aucun inscrit »)
      document.querySelectorAll("#tout-terr table.tt td.v, #r-fiche .p-v").forEach(td => {
        const m = /(^|\s)([\p{L}]+)\s+\2(\s|$)/u.exec(td.textContent.replace(/\s+/g, " "));
        if (m) sortie.defauts.push(`mot répété dans une valeur du tableau complet : « ${td.textContent.trim().slice(0, 50)} »`);
      });
      // l'infobulle « ensemble » ou « médiane » ne reprend jamais la fourchette de la valeur (défaut du 15 novembre 2026,
      // « Médiane, 15,5 entre 15,2 et 18,3 ») et porte l'unité quand la ligne en a une
      const bulle = document.getElementById("rg-bulle");
      if (bulle) document.querySelectorAll(".fiche .rg-lab").forEach(l => {
        l.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        const t = bulle.hidden ? "" : bulle.textContent;
        if (/\bentre\b/.test(t)) sortie.defauts.push("infobulle de réglette avec une fourchette : « " + t.slice(0, 60) + " »");
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
      });
      // la page replace les étiquettes des réglettes à l'image suivante (fiche_tout.js) ; le navigateur sans fenêtre
      // n'en dessine pas entre deux clics : on le fait ici, comme le navigateur du lecteur
      if (window.etiquettesReglettes) window.etiquettesReglettes();
      document.querySelectorAll("#tout-terr, #tout-terr details.tt-domd").forEach(d => { d.open = true; });
    }
    document.querySelectorAll('main a[href*="indicateur/"]').forEach(a => { if (!a.textContent.includes("→")) sortie.defauts.push("lien vers une page d'indicateur sans « → » : " + nom(a)); });
    document.querySelectorAll('main a[href^="#l-"], main a[href^="#t-sm-reg"]').forEach(a => { if (!a.textContent.includes("↓")) sortie.defauts.push("lien vers une ligne de la fiche sans « ↓ » : " + nom(a)); });
    await new Promise(r => setTimeout(r, 100));
  }
  // 0 bis. page d'indicateur, étape 3 des portes d'entrée (15 novembre 2026) : « Votre territoire » trouve le Rhône (ou
  //    la première région) et écrit la valeur de son fichier publié, avec sa réglette quand le niveau en a une ; un clic
  //    sur un département de la carte affiche sa valeur à côté. Les contrôles qui suivent lisent la page ainsi remplie.
  const votre = document.getElementById("votre");
  if (votre && /\b(dep|reg)\b/.test(votre.dataset.niv)) {
    const attendre = async (f, n = 80) => { for (let i = 0; i < n && !f(); i++) await new Promise(r => setTimeout(r, 100)); return f(); };
    const q = document.getElementById("q-votre"), niv = votre.dataset.niv.split(" "), lv = niv.includes("dep") ? "dep" : "reg";
    const code = lv === "dep" ? "69" : "84", nomT = lv === "dep" ? "Rhône" : "Auvergne";
    q.value = nomT; q.dispatchEvent(new Event("input"));
    const b = await attendre(() => document.querySelector("#s-votre:not([hidden]) button[data-i]"));
    if (!b) sortie.defauts.push("« Votre territoire » : aucune proposition pour « " + nomT + " »");
    else {
      b.click();
      const ok = await attendre(() => document.querySelector("#r-votre .vt-v, #r-votre .vt-pos"));
      let T = null; try { T = await (await fetch("../territoire/" + lv + "/" + code + ".json")).json(); } catch (e) {}
      const v = T && T.ind[votre.dataset.ind], aff = (document.querySelector("#r-votre .vt-v") || {}).textContent || "";
      if (!ok) sortie.defauts.push("« Votre territoire » : rien n'est affiché pour " + nomT);
      else if (v && v[1] && aff !== v[1]) sortie.defauts.push(`« Votre territoire » : ${aff} affiché, ${v[1]} dans le fichier du territoire`);
      else if (v && v[1] && !document.querySelector("#r-votre .rg") && votre.dataset.niv) sortie.defauts.push("« Votre territoire » : réglette absente pour " + nomT);
    }
    const p = document.querySelector('.carte-cote svg path[data-t="dep:69"]');
    if (p) {
      p.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      if (!await attendre(() => document.querySelector("#clic .ck-nom"))) sortie.defauts.push("carte : un clic sur le Rhône n'affiche pas sa valeur");
    }
    if (window.etiquettesReglettes) window.etiquettesReglettes();
    await new Promise(r => setTimeout(r, 200));
  }
  // la flèche « → » ou « ↓ » d'un lien ne passe jamais seule à la ligne : elle est sur la ligne où finit le nom (défaut vu
  // le 15 novembre 2026, « Masseurs-kinésithérapeutes » puis « → » seule)
  document.querySelectorAll("main a.avec-fl").forEach(a => {
    const u = a.querySelector(".u"), f = a.querySelector(".fl"); if (!u || !f || !vis(a) || cache(a)) return;
    const ru = u.getClientRects(), rf = f.getBoundingClientRect(); if (!ru.length || !rf.width) return;
    if (Math.abs(ru[ru.length - 1].top - rf.top) > 4) sortie.defauts.push("flèche seule en début de ligne : " + nom(a));
  });

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
    // un bouton plus étroit que son plus long mot : le texte en sort, un mot par ligne (« Voir la carte » de l'atlas à
    // 4 px au téléphone, réduit par un conteneur de requête, 25 novembre 2026). Au-delà de 4 px : la flèche « ▾ » des
    // replis de l'atlas dépasse de 3 px sans rien couper.
    if (el.tagName === "BUTTON" && el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 4 && s.overflowX === "visible" && el.textContent.trim()) sortie.defauts.push("texte qui sort de son bouton " + nom(el));
    aideTronquee(el);
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
      const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left), oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (ox > 0 && oy > 1)
        sortie.defauts.push("figure, chevauchement « " + ts[i].t.textContent.trim().slice(0, 25) + " » / « " + ts[j].t.textContent.trim().slice(0, 25) + " »");
      // deux étiquettes d'une même ligne à moins de 4 px l'une de l'autre se lisent comme une seule (« 13,9 » et « 13,6 »
      // de l'escalier d'Explorer au téléphone, audit du 25 novembre 2026)
      // (le signal « ! » se pose contre la donnée qu'il signale, à dessein : il n'est pas une étiquette)
      else if (ox > -4 && oy > Math.min(a.height, b.height) / 2 && ![ts[i], ts[j]].some(o => o.t.textContent.trim() === "!"))
        sortie.defauts.push("figure, étiquettes à moins de 4 px « " + ts[i].t.textContent.trim().slice(0, 25) + " » / « " + ts[j].t.textContent.trim().slice(0, 25) + " » (" + (-ox).toFixed(1) + " px)");
    }
    // une étiquette n'est jamais traversée par un trait (repère, diagonale d'égalité) : ni par un trait dessiné par-dessus, ni
    // par un trait dessous quand elle n'a pas de liseré qui le masque ; et une étiquette détourée ne se pose pas sur une
    // barre d'une autre couleur que son liseré, qui y ferait une pastille barrée (« 12,2 » et « 11,5 » de l'escalier du
    // niveau de vie, audit du 25 novembre 2026)
    const detouree = t => { const s = getComputedStyle(t); return s.stroke !== "none" && parseFloat(s.strokeWidth) > 0 && /stroke/.test(s.paintOrder || ""); };
    // le quadrillage, pâle et dessous, n'est pas un trait de lecture : classe « grillage », ou trait à moins de 1,5:1 du fond
    const rgbT = c => { const d = document.createElement("i"); d.style.color = c; document.body.appendChild(d); const v = getComputedStyle(d).color; d.remove(); return (v.match(/[\d.]+/g) || []).slice(0, 3).map(Number); };
    const lumT = c => c.map(x => { x /= 255; return x <= .03928 ? x / 12.92 : Math.pow((x + .055) / 1.055, 2.4); }).reduce((s, x, i) => s + x * [.2126, .7152, .0722][i], 0);
    const fondT = rgbT(getComputedStyle(document.documentElement).getPropertyValue("--bg").trim() || getComputedStyle(document.body).backgroundColor);
    const pale = l => { const a = lumT(rgbT(getComputedStyle(l).stroke)), b = lumT(fondT); return (Math.max(a, b) + .05) / (Math.min(a, b) + .05) < 1.5; };
    const traits = [...svg.querySelectorAll("line")].filter(l => vis(l) || l.getBoundingClientRect().width > 1 || l.getBoundingClientRect().height > 1)
      .filter(l => getComputedStyle(l).stroke !== "none" && !l.closest(".axe,.grillage") && !pale(l));
    // une forme pleine peinte entre le trait et l'étiquette (cadre d'un domaine, pastille « ! ») masque le trait
    const formes = [...svg.querySelectorAll("rect,circle,ellipse,path,polygon")].filter(f => { const c = getComputedStyle(f), a = (c.fill.match(/[\d.]+/g) || [])[3];
      return c.fill !== "none" && c.fill !== "transparent" && (a === undefined || +a > .9) && +c.fillOpacity > .9 && +c.opacity > .9; });
    const masque = (l, t, r) => { const cx = (r.left + r.right) / 2, cy = (r.top + r.bottom) / 2;
      return formes.some(f => (l.compareDocumentPosition(f) & Node.DOCUMENT_POSITION_FOLLOWING) && !(t.compareDocumentPosition(f) & Node.DOCUMENT_POSITION_FOLLOWING)
        && (() => { const b = f.getBoundingClientRect(); return cx > b.left && cx < b.right && cy > b.top && cy < b.bottom; })()); };
    const points = l => { const m = l.getScreenCTM(); if (!m) return null; const p = (x, y) => new DOMPoint(x, y).matrixTransform(m);
      return [p(l.x1.baseVal.value, l.y1.baseVal.value), p(l.x2.baseVal.value, l.y2.baseVal.value)]; };
    const coupe = (s, r) => { // le segment s traverse-t-il le rectangle r (resserré d'un pixel) ?
      const [a, b] = s, x0 = r.left + 1, x1 = r.right - 1, y0 = r.top + 1, y1 = r.bottom - 1; if (x1 <= x0 || y1 <= y0) return false;
      let t0 = 0, t1 = 1; const dx = b.x - a.x, dy = b.y - a.y;
      for (const [p, q] of [[-dx, a.x - x0], [dx, x1 - a.x], [-dy, a.y - y0], [dy, y1 - a.y]]) {
        if (p === 0) { if (q < 0) return false; continue; }
        const u = q / p; if (p < 0) { if (u > t1) return false; if (u > t0) t0 = u; } else { if (u < t0) return false; if (u < t1) t1 = u; }
      }
      return true;
    };
    ts.forEach(o => {
      const halo = detouree(o.t);
      traits.forEach(l => {
        const dessus = !!(o.t.compareDocumentPosition(l) & Node.DOCUMENT_POSITION_FOLLOWING);
        if (!dessus && (halo || masque(l, o.t, o.r))) return;
        // boîte resserrée sur les chiffres, dont le haut et le bas sont vides (comme au 11 sexies)
        const s = points(l), r = { left: o.r.left, right: o.r.right, top: o.r.top + o.r.height * .25, bottom: o.r.bottom - o.r.height * .2 };
        if (s && coupe(s, r)) sortie.defauts.push("figure, étiquette « " + o.t.textContent.trim().slice(0, 25) + " » traversée par un trait");
      });
      if (halo) {
        // la page peut être plus haute que la fenêtre : la barre se cherche par sa géométrie, pas par le point visé
        const cx = (o.r.left + o.r.right) / 2, cy = (o.r.top + o.r.bottom) / 2, couleur = c => { const d = document.createElement("i"); d.style.color = c; document.body.appendChild(d); const v = getComputedStyle(d).color; d.remove(); return v; };
        const opaque = e => { const f = getComputedStyle(e).fill, a = (f.match(/[\d.]+/g) || [])[3]; return f !== "none" && f !== "transparent" && (a === undefined || +a > 0) && +getComputedStyle(e).fillOpacity > 0; };
        const sous = [...svg.querySelectorAll("rect")].filter(e => !(o.t.compareDocumentPosition(e) & Node.DOCUMENT_POSITION_FOLLOWING) && vis(e) && opaque(e))
          .filter(e => { const b = e.getBoundingClientRect(); return cx > b.left && cx < b.right && cy > b.top && cy < b.bottom; }).pop();
        if (sous) {
          const f = getComputedStyle(sous).fill, k = getComputedStyle(o.t).stroke;
          const alpha = (f.match(/[\d.]+/g) || [])[3];   // rectangle transparent de survol : pas une barre
          if (f !== "none" && f !== "transparent" && (alpha === undefined || +alpha > 0) && +getComputedStyle(sous).fillOpacity > 0 && couleur(f) !== couleur(k)) sortie.defauts.push("figure, étiquette détourée posée sur une barre « " + o.t.textContent.trim().slice(0, 25) + " »");
        }
      }
    });
    // une étiquette reste dans le cadre de sa figure (« 10 000 000 » de l'entonnoir au téléphone, audit du 13 novembre 2026)
    const cadre = svg.getBoundingClientRect();
    ts.forEach(o => { if (cadre.width > 0 && (o.r.right > cadre.right + 1 || o.r.left < cadre.left - 1)) sortie.defauts.push("figure, étiquette hors du cadre « " + o.t.textContent.trim().slice(0, 25) + " »"); });
    // entonnoir d'Explorer : le statut publié de chaque territoire suit la bande dessinée (audit du 13 novembre 2026, K1)
    if (svg.hasAttribute("data-ecarts") && svg.getAttribute("data-ecarts") !== "0") sortie.defauts.push("entonnoir, " + svg.getAttribute("data-ecarts") + " territoire(s) dont la couleur contredit la bande");
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
  sortie.reglettes = [...reglettesAuChargement];
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
        // le point ne touche ni ne recouvre jamais une barre, la barre détachée « aucun » ni le chevron : il se pose sous
        // l'axe, sur lequel reposent toutes les barres (audit du 27 novembre 2026 : psychologues à 98 % contre la
        // dernière barre et le chevron, distance au CMP sur la première barre, CMP pour adultes sur « aucun »)
        const axeP = rg.querySelector(".rg-axe"), chev = rg.querySelector(".rg-chev");
        if (axeP && hist && p.top < axeP.getBoundingClientRect().bottom + .5) dire("point qui touche ou recouvre les barres");
        if (chev && vis(chev)) {
          const c = chev.getBoundingClientRect(), cx = (p.left + p.right) / 2, cy = (p.top + p.bottom) / 2;
          const dx = Math.max(c.left - cx, 0, cx - c.right), dy = Math.max(c.top - cy, 0, cy - c.bottom);
          // le cadre du chevron tourné est plus grand que son trait : mesuré contre ce cadre, sans marge
          if (Math.hypot(dx, dy) < p.width / 2) dire("point qui touche le chevron");
        }
      }
    }
    // la part des territoires sans inscrit, reportée dans l'étiquette de la médiane, ne se coupe jamais à l'intérieur de
    // sa parenthèse (« (aucun : » puis « 69 %) », Repères de la fiche courte à 1 440 px, audit du 27 novembre 2026)
    rg.querySelectorAll(".rg-part").forEach(x => { if (vis(x) && x.getClientRects().length > 1) dire("parenthèse « " + x.textContent.trim() + " » coupée"); });
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
  // 5 bis. explication de « ensemble » et « médiane » ouverte d'un clic (fiche) : la réglette garde sa largeur et sa
  //    place, l'explication vient dessous et ne fait pas défiler la page. Ouverte dans « Lire une réglette », elle
  //    élargissait la réglette au-delà de sa colonne, et dans « En bref » elle prenait sa place (22 novembre 2026).
  //    Une réglette de chaque sorte : « En bref », tableau.
  const bulle = document.getElementById("rg-bulle");
  if (bulle) {
    // la légende des réglettes a remplacé l'encadré qui portait une réglette (22 novembre 2026) : restent « En bref »
    // et les tableaux ; une fiche où aucune explication ne peut s'ouvrir est signalée
    const sortes = ["table.matrice .rg-lab", "table:not(.matrice) .rg-lab"];
    if (document.querySelector(".fiche .rg-lab .rg-mot") && !sortes.some(s => [...document.querySelectorAll(s)].some(x => x.querySelector(".rg-mot") && vis(x) && !cache(x))))
      sortes.length = 0, sortie.reglettes.push("aucune explication de réglette visible à ouvrir");
    for (const sel of sortes) {
      const l = [...document.querySelectorAll(sel)].find(x => x.querySelector(".rg-mot") && vis(x) && !cache(x));
      if (!l) continue;
      const rg = l.closest(".rg"), a = rg.getBoundingClientRect(), qui = sel.split(" ")[0];
      l.click(); await new Promise(r => setTimeout(r, 120));
      const b = rg.getBoundingClientRect(), bb = bulle.getBoundingClientRect();
      if (bulle.hidden) sortie.reglettes.push("explication de « " + l.textContent.trim() + " » qui ne s'ouvre pas (" + qui + ")");
      else {
        if (Math.abs(b.width - a.width) > 1.5 || Math.abs(b.left - a.left) > 1.5) sortie.reglettes.push(`réglette qui change de taille quand son explication s'ouvre (${qui}, ${Math.round(a.width)} puis ${Math.round(b.width)} px)`);
        if (bb.top < b.bottom - 1) sortie.reglettes.push("explication de réglette qui n'est pas sous la réglette (" + qui + ")");
        if (document.documentElement.scrollWidth > innerWidth + 1) sortie.reglettes.push("explication de réglette qui fait défiler la page en largeur (" + qui + ")");
      }
      l.click(); await new Promise(r => setTimeout(r, 80));
    }
  }
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
  // 7 bis. fiche courte (structure validée le 26 novembre 2026) : dans les Repères et les domaines, les valeurs d'une même
  //    colonne finissent au même bord droit, à 1 px près ; sous une tuile, la réglette tient dans la tuile
  document.querySelectorAll(".fiche-courte table.matrice tbody").forEach(tb => {
    const col = {};
    tb.querySelectorAll(":scope > tr").forEach(tr => {
      const v = tr.querySelector(".m-v");
      if (!v || !vis(v)) return;
      const k = Math.round(tr.getBoundingClientRect().left);
      (col[k] = col[k] || []).push(v.getBoundingClientRect().right);
    });
    Object.values(col).forEach(r => {
      if (r.length > 1 && Math.max(...r) - Math.min(...r) > 1)
        sortie.defauts.push(`valeurs non alignées dans une colonne de la fiche courte : ${Math.round(Math.max(...r) - Math.min(...r))} px d'écart`);
    });
  });
  // 7 ter. fiche courte, au téléphone et sur tablette : pas de vide entre la réglette d'une ligne et sa valeur (exigence
  //    9 ; au plus 24 px du chevron, ou du bout de l'axe, au texte de la valeur ; audit du 27 novembre 2026)
  if (innerWidth <= 860) document.querySelectorAll(".fiche-courte .m-ligne").forEach(ml => {
    const rg = ml.querySelector(".rg"), v = ml.querySelector(".m-v b, .m-v .statut");
    if (!rg || !v || !vis(rg) || !vis(v) || cache(ml)) return;
    const ch = rg.querySelector(".rg-chev"), fin = Math.max(rg.getBoundingClientRect().right, ch && vis(ch) ? ch.getBoundingClientRect().right : 0);
    const e = v.getBoundingClientRect().left - fin;
    if (e > 24) sortie.defauts.push(`vide de ${Math.round(e)} px entre la réglette et la valeur, fiche courte « ${(ml.closest("tr") && ml.closest("tr").dataset.titre || "").slice(0, 40)} »`);
  });
  document.querySelectorAll(".fiche-courte .cles-fiche li.cle-tuile").forEach(li => {
    const rg = li.querySelector(".sous-tuile .rg"), b = li.getBoundingClientRect();
    if (rg && vis(rg) && rg.getBoundingClientRect().right > b.right + 1)
      sortie.defauts.push("réglette qui sort de sa tuile, fiche courte « " + (li.querySelector(".tuile-t") || li).textContent.trim().slice(0, 40) + " »");
  });
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
      // une mesure non publiée n'a pas de position : sa cellule dit pourquoi elle manque (indicateurs connus seulement
      // pour la région, fiche de département, 14 novembre 2026), et doit le dire
      if (c.closest("tr.non-pub")) {
        if (!/ne donne pas cette mesure/.test(t)) sortie.defauts.push("mesure non publiée sans sa raison « " + t.slice(0, 50) + " »");
        return;
      }
      if (t && !/ des (intercommunalités|départements|régions)| (tous|toutes) les autres /.test(t + " "))
        sortie.defauts.push("position sans son ensemble au téléphone « " + t.slice(0, 50) + " »");
      const ec = [...c.closest("tr").querySelectorAll(".ec")].filter(vis);
      if (ec.some(x => !c.contains(x))) sortie.defauts.push("écart et position sur deux lignes « " + t.slice(0, 50) + " »");
    });
    // 9 bis. le nom de la ligne prend la largeur que lui laissent la valeur et le menu : la réglette, étendue sur les
    //        deux colonnes, élargissait la seconde et le nom tenait sur 127 px sur 343 (relecture du 9 novembre 2026)
    tb.querySelectorAll("tbody tr").forEach(tr => {
      const n = tr.querySelector("th"), v = tr.querySelector("td.v"), o = tr.querySelector("td.outil");
      if (!n || !vis(n) || !v) return;
      const rg = document.createRange(); rg.selectNodeContents(v);   // largeur du contenu de la valeur, pas de sa cellule
      const libre = tr.getBoundingClientRect().width - Math.max(rg.getBoundingClientRect().width, o ? o.getBoundingClientRect().width : 0);
      if (n.getBoundingClientRect().width < libre - 60)
        sortie.defauts.push("nom de ligne serré sur " + Math.round(n.getBoundingClientRect().width) + " px au téléphone « " + n.innerText.trim().slice(0, 40) + " »");
      // le menu « … » reste au-dessus du nom qui s'étend sous lui, donc cliquable (même relecture) ; ouvert, son panneau
      // passe au premier plan (il glissait sous la réglette et les lignes suivantes, contrôle 9 ter plus bas)
      const b = o && vis(o) ? o.getBoundingClientRect() : null;
      if (b && b.top >= 0 && b.bottom <= innerHeight) {
        const x = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
        if (x && !o.contains(x)) sortie.defauts.push("menu de ligne caché sous « " + n.innerText.trim().slice(0, 40) + " »");
      }
    });
  });
  // 9 ter. menus « … » des lignes ouverts un à un (douze au plus) : tout leur panneau est au premier plan, rien ne le
  //        raye ni ne le recouvre (régression du 9 novembre 2026, relevée par la relecture indépendante)
  for (const d of [...document.querySelectorAll("table.ligne-type details.menu-ligne")].filter(vis).slice(0, 12)) {
    d.scrollIntoView({ block: "center" });
    d.open = true;
    await new Promise(r => setTimeout(r, 60));
    const c = d.querySelector(".menu-corps");
    if (c && vis(c)) {
      const b = c.getBoundingClientRect();
      const pts = [[.1, .2], [.5, .5], [.9, .8], [.3, .9]].map(([fx, fy]) => [b.left + fx * b.width, b.top + fy * b.height])
        .filter(([x, y]) => y > 0 && y < innerHeight && x > 0 && x < innerWidth);
      if (pts.some(([x, y]) => { const e = document.elementFromPoint(x, y); return e && !c.contains(e); }))
        sortie.defauts.push("menu de ligne ouvert recouvert « " + (d.closest("tr").querySelector("th") || d).innerText.trim().slice(0, 40) + " »");
    }
    d.open = false;
  }
  // 6. justifié étroit : un bloc justifié de moins de 560 px, mesuré sur lui-même et non sur sa colonne (rivières dans
  //    les « Comment lire » bornés par la mesure, relecture esthétique du 31 octobre 2026). Tout bloc de texte de la
  //    page, pas seulement les p, li et dd de main, et l'alignement que lui donne la feuille de style : le script de
  //    césure remet à gauche, après coup, un paragraphe étroit qu'elle justifie, si bien que le contrôle, lancé une fois
  //    le script passé, ne voyait pas les huit blocs justifiés de 282 à 402 px de l'accueil, justifiés tant que le
  //    script n'a pas tourné et sans lui (audit du 25 novembre 2026). À l'impression, le script règle l'alignement
  //    au moment d'imprimer (cesure.js, papier) : c'est l'alignement final qui est mesuré.
  {
    const papier = !!document.querySelector('link[href*="_papier"]');
    let n = 0, ex = "";
    document.querySelectorAll("body *").forEach(b => {
      if (b.closest("svg,script,style,template,noscript,pre#controle-finition") || !vis(b) || cache(b)) return;
      const s = getComputedStyle(b);
      if (s.display.startsWith("inline") || s.display === "contents") return;
      // un bloc qui porte lui-même du texte (un texte nu ou un élément en ligne), sur deux lignes au moins
      const texte = [...b.childNodes].some(x => (x.nodeType === 3 && x.nodeValue.trim()) || (x.nodeType === 1 && x.textContent.trim() && getComputedStyle(x).display.startsWith("inline")));
      if (!texte) return;
      let al = s.textAlign;
      if (!papier && b.dataset.aligne !== undefined && b.style.textAlign) {
        const avant = b.style.textAlign; b.style.textAlign = ""; al = getComputedStyle(b).textAlign; b.style.textAlign = avant;
      }
      if (al !== "justify") return;
      const r = b.getBoundingClientRect();
      if (r.width >= 559 || r.height < 1.8 * (parseFloat(s.lineHeight) || 1.5 * parseFloat(s.fontSize))) return;
      n++; ex = ex || Math.round(r.width) + " px « " + b.textContent.replace(/­/g, "").trim().slice(0, 40) + " »";
    });
    if (n) sortie.defauts.push(`justifié sur moins de 560 px : ${n} bloc(s), dont ${ex}`);
  }
  // 6 bis. une valeur chiffrée n'est jamais suivie, sur la même ligne, d'un élément en ligne qui commence par un chiffre
  //    (règle 17 : « 0509 territoires à 0 » se lisait dans le tableau des pages d'indicateur, la note collée à sa
  //    valeur, audit du 25 novembre 2026). Le texte qui précède est cherché dans le même bloc.
  {
    let n = 0, ex = "";
    const bloc = e => { let a = e; while (a && a.parentElement && getComputedStyle(a).display.startsWith("inline")) a = a.parentElement; return a; };
    document.querySelectorAll("body *").forEach(el => {
      if (el.closest("svg,script,style,template,noscript,pre#controle-finition,input,select,textarea") || !getComputedStyle(el).display.startsWith("inline")) return;
      if (!/^\s*\d/.test(el.textContent) || !vis(el) || cache(el)) return;
      const blk = bloc(el.parentElement || el), tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      tw.currentNode = el;
      let t = tw.previousNode();
      while (t && !t.nodeValue.trim() && blk.contains(t)) t = tw.previousNode();
      if (!t || !blk.contains(t) || !/\d[\s  ]*$/.test(t.nodeValue) || !t.parentElement || !vis(t.parentElement)) return;
      const rg = document.createRange(), v = t.nodeValue.replace(/[\s  ]+$/, "");
      rg.setStart(t, v.length - 1); rg.setEnd(t, v.length);
      const a = rg.getClientRects()[0], b = el.getClientRects()[0];
      if (!a || !b || Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) < Math.min(a.height, b.height) / 2) return;
      n++; ex = ex || "« " + (v.slice(-12) + el.textContent.trim().slice(0, 28)).trim() + " »";
    });
    if (n) sortie.defauts.push(`valeur collée à sa note : ${n} (${ex})`);
  }
  // même règle sur ce qui est replié ou caché (panneaux « Citer et exporter », fenêtres fermées), mesurée par le style
  // calculé : une citation n'est jamais justifiée, et rien ne l'est au téléphone (signalé le 25 novembre 2026)
  let citJ = 0, telJ = 0, exJ = "";
  document.querySelectorAll("main p,main li,main dd").forEach(b => {
    if (b.closest("script,template") || getComputedStyle(b).textAlign !== "justify") return;
    if (b.closest(".citation-fig")) { citJ++; exJ = exJ || b.textContent.trim().slice(0, 40); }
    else if (innerWidth < 560) { telJ++; exJ = exJ || b.textContent.trim().slice(0, 40); }
  });
  if (citJ) sortie.defauts.push(`citation justifiée : ${citJ} (« ${exJ} »)`);
  if (telJ) sortie.defauts.push(`texte justifié au téléphone, même replié : ${telJ} (« ${exJ} »)`);
  // 6 ter. aucune césure dans un sigle, même élidé : « l'INSEE » se coupait en « l'IN-/SEE » dans
  //    les blocs « Sources » de la fiche (audit du 25 novembre 2026). Toutes les césures posées dans la page sont lues.
  {
    let n = 0, ex = "";
    const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let x;
    while ((x = tw.nextNode())) {
      if (x.nodeValue.indexOf("­") < 0) continue;
      for (const m of x.nodeValue.split(/[^\p{L}­'’]+/u)) {
        if (m.indexOf("­") < 0) continue;
        const w = m.replace(/^(?:[ldjmnstc]|qu|jusqu|lorsqu|puisqu|quoiqu)['’]/i, "").replace(/­/g, "");
        // un sigle (deux capitales au moins) ; un nom d'en-tête de tableau coupé exprès à sa jointure (« Psycho-logue »,
        // site.CESURES) n'en est pas un
        if ((w.match(/\p{Lu}/gu) || []).length >= 2) { n++; ex = ex || m.replace(/­/g, "-"); }
      }
    }
    if (n) sortie.defauts.push(`césure dans un sigle : ${n} (« ${ex} »)`);
  }
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
  // 11. bord droit (règle 8, 6 novembre 2026) : un paragraphe large s'arrête au même bord droit que la figure,
  //     le tableau ou l'encadré de sa colonne, à 8 px près. Un seul défaut par page, avec le compte et un exemple.
  {
    const blocs = "figure,table,.encadre,.defile,.graphique";
    let n = 0, ex = "", ecart = 0;
    const parents = new Set([...document.querySelectorAll("main " + blocs.split(",").join(",main "))].filter(vis).map(f => f.parentElement));
    parents.forEach(par => {
      const figs = [...par.children].filter(e => e.matches(blocs) && vis(e) && !cache(e));
      if (!figs.length) return;
      const bord = Math.max(...figs.map(f => f.getBoundingClientRect().right));
      // le sous-titre des pages est sur les sept colonnes de la grille (7 novembre 2026, proposition 1)
      [...par.children].filter(e => e.matches("p,ul,ol,.comment-lire,.source,.note") && !e.matches(".chapeau:not(.version),.reponse-d") && vis(e) && !cache(e)).forEach(p => {
        const r = p.getBoundingClientRect();
        if (r.width < 300) return;                       // une phrase courte ou une colonne étroite n'est pas mesurée
        const d = bord - r.right;
        if (d > 8) { n++; if (d > ecart) { ecart = d; ex = nom(p); } }
      });
    });
    if (n) sortie.defauts.push(`bord droit : ${n} paragraphe(s) qui s'arrêtent avant la figure de leur colonne, jusqu'à ${Math.round(ecart)} px (${ex})`);
  }
  // 11 bis. pas de colonne de lecture étroite (7 novembre 2026, capture A) : un texte courant d'une colonne large
  //     n'est pas bridé par une largeur maximale qui l'arrête avant le bord de sa colonne, même sans figure à côté
  //     (7 novembre 2026, chapeaux des pages de domaine bridés à 64 caractères, vus)
  {
    let n = 0, ex = "", ecart = 0;
    document.querySelectorAll("main p,main ul,main ol,main .comment-lire,main .source,main .note").forEach(p => {
      // le sous-titre des pages est sur les sept colonnes de la grille (7 novembre 2026, proposition 1), et la
      // phrase qui le suit sur les pages de domaine aussi (10 novembre 2026, sur captures)
      // ; un chapeau posé dans la colonne de texte, à côté du sommaire, n'est pas le sous-titre de la page et va au bord
      // de sa colonne comme ses voisins (Territoires, 690 px dans une colonne de 800, audit du 27 novembre 2026)
      if (!vis(p) || cache(p) || (p.matches(".chapeau,.reponse-d") && !p.matches(".colonne .corps .chapeau:not(.version)"))
          || getComputedStyle(p).maxWidth === "none") return;
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
  // 11 bis a. pas de vide sous le sommaire replié (exigence 9) : quand le sommaire passe au-dessus du texte (téléphone,
  //     tablette), le premier texte ou champ qui le suit commence à 40 px au plus de son filet (audit du 27 novembre
  //     2026 : 84 px entre « Sommaire » et le champ de recherche de Territoires, 60 px sur Télécharger et les rapports)
  document.querySelectorAll(".rapport > .sommaire").forEach(s => {
    const suite = s.nextElementSibling;
    if (!suite || !vis(s) || !vis(suite)) return;
    const rs = s.getBoundingClientRect();
    if (suite.getBoundingClientRect().top < rs.bottom - 1) return;     // côte à côte, sur ordinateur
    const w = document.createTreeWalker(suite, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    let haut = null;
    for (let x = w.nextNode(); x && haut === null; x = w.nextNode()) {
      if (x.nodeType === 3) {
        if (!x.nodeValue.trim() || !vis(x.parentElement) || cache(x.parentElement)) continue;
        const rg = document.createRange(); rg.selectNodeContents(x);
        const r = rg.getBoundingClientRect(); if (r.height) haut = r.top;
      } else if (x.matches("input,select,textarea,img,svg,canvas,table") && vis(x) && !cache(x)) haut = x.getBoundingClientRect().top;
      // un filet est déjà du contenu : les chiffres clés de « Citer et réutiliser » commencent par le leur, 28 px sous le
      // sommaire (contrôle du 27 novembre 2026)
      else if (vis(x) && !cache(x) && parseFloat(getComputedStyle(x).borderTopWidth) > 0 && getComputedStyle(x).borderTopStyle !== "none")
        haut = x.getBoundingClientRect().top;
    }
    if (haut !== null && haut - rs.bottom > 40)
      sortie.defauts.push(`vide de ${Math.round(haut - rs.bottom)} px sous le sommaire replié, avant « ${(suite.textContent || "").replace(/\s+/g, " ").trim().slice(0, 30)} »`);
  });
  // 11 bis b. l'en-tête du site tient sur une seule ligne, menu déplié ou replié derrière « Menu » (10 novembre 2026 :
  //     avec Explorer, « Fond sombre » passait à la ligne entre 1 000 et 1 100 px)
  {
    const nav = document.querySelector("nav.site .in");
    if (nav && !document.querySelector("nav.site.ouvert")) {
      const items = [...nav.querySelectorAll(":scope > *, :scope > .liens > *")]
        .filter(e => getComputedStyle(e).display !== "contents" && vis(e) && e.getBoundingClientRect().width > 0);
      const milieux = items.map(e => { const r = e.getBoundingClientRect(); return r.top + r.height / 2; });
      if (milieux.length > 1 && Math.max(...milieux) - Math.min(...milieux) > 12)
        sortie.defauts.push("en-tête du site sur plusieurs lignes (" + items.map(e => (e.textContent || "").trim().slice(0, 14)).filter(Boolean).slice(-2).join(", ") + ")");
    }
  }
  // 11 bis c. relecture indépendante du 11 novembre 2026 : texte écrit par les scripts sans espace insécable (2.4) ;
  //     nom de commune posé sur un point d'« Autour d'un lieu » (2.5) ; texte de figure illisible au téléphone (2.7)
  {
    if (document.readyState !== "complete") await new Promise(r => addEventListener("load", r, { once: true }));
    await new Promise(r => setTimeout(r, 400));
    // la fenêtre « Croiser deux indicateurs » d'Explorer ne se charge qu'à l'approche de l'écran
    const fen = document.getElementById("cxFenNuage");
    if (fen) { fen.scrollIntoView({block: "center"}); await new Promise(r => setTimeout(r, 2500)); }
    const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n = 0, ex = "", x, abs = "";
    while ((x = tw.nextNode())) {
      const p = x.parentElement;
      if (!p || p.closest("script,style,code,pre,textarea,svg,input,select,option,#controle-finition") || !vis(p)) continue;
      // message de repli d'une donnée ou d'une explication absente (« Explication absente de ce fichier de données »
      // sous le nuage de points d'Explorer, vu le 11 novembre 2026)
      if (/absentes? de ce fichier/.test(x.nodeValue)) abs = abs || x.nodeValue.trim().slice(0, 60);
      const m = x.nodeValue.match(/\d \d{3}(?!\d)|« |[^\s] »|\d (?:%|€)/);
      if (m) { n++; ex = ex || "« " + x.nodeValue.trim().slice(0, 50) + " »"; }
    }
    if (n) sortie.defauts.push(`espace ordinaire là où il faut une insécable : ${n} texte(s) (${ex})`);
    if (abs) sortie.defauts.push(`message de donnée absente affiché : « ${abs} »`);
    // audit du 12 novembre 2026 : une colonne de tableau réduite à quelques lettres (« publi / que / Franc / e »), et, dans
    // Comparer au téléphone, la valeur du premier territoire hors de l'écran
    let etroites = 0, ex3 = "";
    document.querySelectorAll("main td").forEach(td => {
      if (!vis(td) || td.closest(".encadre-outils,.outils-figure")) return;
      // innerText, le texte visible : un menu de ligne fermé (« Plus sur cette ligne ») n'est pas une colonne écrasée
      const w = td.getBoundingClientRect().width, t = td.innerText.replace(/\s+/g, " ").trim();
      if (w > 0 && w < 56 && t.length > 15 && /[a-zà-ÿ]{6,}/i.test(t)) { etroites++; ex3 = ex3 || "« " + t.slice(0, 40) + " »"; }
    });
    if (etroites) sortie.defauts.push(`colonne de tableau de moins de 56 px pour un texte long : ${etroites} cellule(s) (${ex3})`);
    // un « 0 » écrit par le script dans une cellule, sans infobulle ni signal (règle 6 ; « CAARUD : 0 » dans Autour
    // d'un lieu, audit du 12 novembre 2026, point 18)
    let zeros = 0, ex5 = "";
    document.querySelectorAll("main td").forEach(td => {
      if (!vis(td) || td.innerText.trim() !== "0") return;
      const ligne = td.closest("tr");
      if (td.querySelector("[title],abbr,.sig") || td.hasAttribute("title") || (ligne && ligne.querySelector(".sig,[title]"))) return;
      zeros++; ex5 = ex5 || ((ligne && ligne.cells[0]) ? ligne.cells[0].innerText.trim().slice(0, 40) : "");
    });
    if (zeros) sortie.defauts.push(`« 0 » laissé seul dans un tableau : ${zeros} cellule(s) (« ${ex5} »)`);
    // une étiquette de valeur traversée par la ligne de repère horizontale (exigence 17, audit du 12 novembre 2026, 21)
    let barrees = 0, ex6 = "";
    document.querySelectorAll("main svg line.repere").forEach(l => {
      const b = l.getBoundingClientRect();
      if (!vis(l) || b.height > 1.5 || b.width < 20) return;
      const yl = b.top + b.height / 2;
      l.ownerSVGElement.querySelectorAll("text.etiq").forEach(t => {
        const r = t.getBoundingClientRect();
        if (!t.textContent.trim() || r.width === 0) return;
        if (r.top + 2 < yl && yl < r.bottom - 2 && r.right > b.left && r.left < b.right) { barrees++; ex6 = ex6 || t.textContent.trim().slice(0, 20); }
      });
    });
    if (barrees) sortie.defauts.push(`étiquette traversée par la ligne de repère : ${barrees} (« ${ex6} »)`);
    document.querySelectorAll("table.comp tbody tr").forEach((tr, i) => {
      if (i > 12) return;
      const td = tr.querySelector("td"); if (!td || !vis(td)) return;
      const tw2 = document.createTreeWalker(td, NodeFilter.SHOW_TEXT); let x2;
      while ((x2 = tw2.nextNode()) && !x2.nodeValue.trim()) {}
      if (!x2) return;
      const rg = document.createRange(); rg.selectNodeContents(x2); const b = rg.getBoundingClientRect();
      if (b.width && b.left > innerWidth - 8) sortie.defauts.push("Comparer : valeur du premier territoire hors de l'écran « " + x2.nodeValue.trim().slice(0, 20) + " »");
    });
    let larges = 0;
    const tw3 = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let x3;
    while ((x3 = tw3.nextNode())) {
      const p = x3.parentElement;
      if (!p || p.closest("script,style,code,pre,textarea,svg,input,select,option") || !vis(p)) continue;
      if (/\d\u00a0\d{3}(?!\d)/.test(x3.nodeValue)) larges++;
    }
    if (larges) sortie.defauts.push(`séparateur des milliers large au lieu de l'espace fine : ${larges} texte(s)`);
    // une seule barre de zoom par figure : celle des figures du site et celle du nuage d'Explorer se superposaient, signes
    // doublés (signalé le 25 novembre 2026)
    const barres = [...document.querySelectorAll(".zoom-boutons, .zoombar")].filter(vis).map(z => z.getBoundingClientRect());
    let doubles = 0;
    barres.forEach((a, i) => barres.slice(i + 1).forEach(b => {
      if (a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom) doubles++;
    }));
    if (doubles) sortie.defauts.push(`barres de zoom superposées : ${doubles}`);
    // figures lisibles au téléphone (12 novembre 2026) : une figure dont le texte tombe sous 9 px a son bouton
    // « Agrandir la figure », et la figure agrandie se lit à 9 px au moins
    if (innerWidth <= 640) {
      await new Promise(r => setTimeout(r, 900));
      const petit = s => { let m = Infinity; s.querySelectorAll("text").forEach(t => { if (!t.textContent.trim()) return; const h = t.getBoundingClientRect().height; if (h > 0 && h < m) m = h; }); return m; };
      let sans = 0, ex4 = "", premier = null;
      document.querySelectorAll("main svg, .panel svg").forEach(s => {
        if (s.ownerSVGElement || s.closest(".fig-plein,nav,button,.leg-classes") || !vis(s) || s.getBoundingClientRect().width < 200) return;
        if (petit(s) >= 9) return;
        const h = s.closest("figure") || s.parentElement, b = h.querySelector(":scope > .fig-agrandir");
        if (!b) { sans++; ex4 = ex4 || (s.getAttribute("aria-label") || (h.querySelector("figcaption") || {}).textContent || "").trim().slice(0, 50); }
        else if (!premier) premier = b;
      });
      if (sans) sortie.defauts.push(`figure illisible au téléphone sans bouton « Agrandir » : ${sans} (« ${ex4} »)`);
      if (premier) {
        premier.click(); await new Promise(r => setTimeout(r, 200));
        const o = document.querySelector(".fig-plein svg");
        if (!o) sortie.defauts.push("le bouton « Agrandir la figure » n'ouvre rien");
        else if (petit(o) < 9) sortie.defauts.push(`figure agrandie encore illisible : texte de ${Math.round(petit(o) * 10) / 10} px`);
        const f = document.querySelector(".fig-plein-fermer"); if (f) f.click();
      }
    }
    const noms = [...document.querySelectorAll("#zc text.nom-com")], pts = [...document.querySelectorAll("#zc .st")];
    noms.forEach(t => {
      const a = t.getBoundingClientRect();
      const k = pts.filter(q => { const b = q.getBoundingClientRect(); return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom; }).length;
      if (k) sortie.defauts.push(`nom « ${t.textContent} » posé sur ${k} point(s) de la carte`);
    });
    // le lieu choisi garde son nom sur sa carte (revérification de l'audit, 11 novembre 2026 : Rodez n'était plus nommé)
    const lieu = document.querySelector("#zc circle.lieu title");
    if (lieu && !noms.some(t => t.textContent.trim() === lieu.textContent.trim()))
      sortie.defauts.push(`lieu choisi « ${lieu.textContent.trim()} » sans son nom sur la carte`);
    // la case « non publié » de la légende en texte garde sa hachure (un fond url(#motif) restait vide)
    document.querySelectorAll(".leg-classes i").forEach(i => {
      if (vis(i) && getComputedStyle(i).backgroundImage === "none" && getComputedStyle(i).backgroundColor === "rgba(0, 0, 0, 0)")
        sortie.defauts.push("case de légende sans couleur ni hachure");
    });
    if (innerWidth <= 640) {
      let m2 = 0, ex2 = "";
      document.querySelectorAll('main figure svg[aria-label*="en cinq classes"] text').forEach(t => {
        if (!vis(t) || !t.textContent.trim()) return;
        const h = t.getBoundingClientRect().height;
        if (h > 0 && h < 9) { m2++; ex2 = ex2 || "« " + t.textContent.trim().slice(0, 30) + " »"; }
      });
      if (m2) sortie.defauts.push(`légende de carte de moins de 9 px au téléphone : ${m2} (${ex2})`);
    }
  }
  // 11 ter. sur les pages de domaine, le sous-titre, la phrase qui le suit et la colonne de la carte finissent au même bord
  //     droit, celui des sept colonnes de la grille (10 novembre 2026, sur captures : 13 px d'écart avant)
  if (innerWidth > 900) {
    const els = ["main.domaine header.tete .chapeau", "main.domaine .reponse-d", "main.domaine .phares > :first-child"]
      .map(s => document.querySelector(s)).filter(e => e && vis(e));
    if (els.length === 3) {
      const bords = els.map(e => e.getBoundingClientRect().right);
      const e = Math.max(...bords) - Math.min(...bords);
      if (e > 2) sortie.defauts.push("sous-titre, phrase et carte de la page de domaine qui finissent à " + Math.round(e) + " px l'un de l'autre");
    }
  }
  // 11 ter b. accueil (structure du site validée le 26 novembre 2026, planche_2_accueil) : les tuiles des chiffres de la
  //     France sont de même hauteur, à 2 px près, sur ordinateur ; la légende de page de la carte est visible (à droite
  //     sur ordinateur, sous le dessin au téléphone), son texte d'au moins 12 px, et le dessin n'a plus de légende en
  //     texte de 8 unités ; la page Offre de soins garde chaque réglage sur sa propre ligne, sous sa question.
  {
    const tuiles = [...document.querySelectorAll(".accueil .tete-chiffres > div")].filter(vis);
    if (innerWidth > 860 && tuiles.length > 1) {
      const hs = tuiles.map(t => t.getBoundingClientRect().height);
      if (Math.max(...hs) - Math.min(...hs) > 2) sortie.defauts.push("tuiles des chiffres de la France de hauteurs différentes : " + hs.map(Math.round).join(", ") + " px");
    }
    const carte = document.querySelector(".accueil .carte-accueil");
    if (carte) {
      const legs = [...carte.querySelectorAll(".leg-carte")].filter(vis);
      if (legs.length !== 1) sortie.defauts.push(`légende de la carte de l'accueil visible ${legs.length} fois, attendue une`);
      legs.forEach(l => l.querySelectorAll("li").forEach(li => {
        if (parseFloat(getComputedStyle(li).fontSize) < 12) sortie.defauts.push("légende de la carte de l'accueil sous 12 px : « " + li.textContent.trim().slice(0, 30) + " »");
      }));
      const svg = carte.querySelector("figure svg");
      if (svg) {
        const cadre = svg.viewBox.baseVal;
        [...svg.querySelectorAll('rect[x="8"][width="14"]')].forEach(r => {
          if (+r.getAttribute("y") < cadre.y + cadre.height) sortie.defauts.push("légende dessinée visible dans la carte de l'accueil");
        });
      }
    }
    document.querySelectorAll("main.domaine .famille-q li").forEach(li => {
      const q = li.querySelector(":scope > a:not(.reg-q)"), r = li.querySelector(":scope > .reg-q");
      if (!q || !r || !vis(r)) return;
      const bq = q.getClientRects(), br = r.getBoundingClientRect();
      const dernier = bq[bq.length - 1];
      if (dernier && br.top < dernier.bottom - 1) sortie.defauts.push("« la régler dans » sur la ligne de sa question : « " + q.textContent.trim().slice(0, 40) + " »");
    });
  }
  // 11 quater. un texte ne touche pas le bord gauche ou droit du cadre qui le contient (7 novembre 2026, « Comment
  //     lire » de la carte d'« Autour d'un lieu », collé au filet de son encadré, vu) : 4 px au moins entre
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
  // 11 quinquies. l'atlas mène à la fiche du territoire choisi (promesse de l'accueil, demande du 2 novembre
  //     2026 ; l'encadré ne menait qu'aux rapports, relevé par l'audit de la navigation du 8 novembre)
  if (/atlas\.html$/.test(location.pathname.replace(/_finition_atlas[^/]*\.html$/, "atlas.html")) && document.getElementById("tip")) {
    // un territoire de la carte elle-même, amenée à l'écran : à 883 px, la carte commence sous le premier écran et le
    // contrôle cliquait une case de légende (10 novembre 2026)
    const carte = document.querySelector("svg#map");
    if (carte) { carte.scrollIntoView({block: "center"}); await new Promise(r => setTimeout(r, 200)); }
    const t = [...document.querySelectorAll(carte ? "svg#map path" : "svg path")].find(e => { const r = e.getBoundingClientRect(); return r.width > 8 && r.height > 8 && r.top >= 0 && r.bottom <= innerHeight; });
    if (t) {
      const b = t.getBoundingClientRect();
      t.dispatchEvent(new MouseEvent("click", {bubbles: true, clientX: b.x + b.width / 2, clientY: b.y + b.height / 2}));
      if (!document.querySelector('a.lien-fiche[href*="territoire/"]')) sortie.defauts.push("atlas : l'encadré du territoire choisi ne mène pas à sa fiche complète");
    }
  }
  // 11 quinquies b. l'atlas ouvert avec une mesure dans son adresse (#?…&mesure=evol) l'affiche, la garde dans l'adresse
  //     une fois la page dessinée, et son panneau de la France entière la suit : après le choix « Évolution », un lien
  //     partagé rouvrait la densité et le panneau la montrait encore (audit du 25 novembre 2026)
  if (document.getElementById("metricSeg")) {
    const q = new URLSearchParams((location.hash.split("?")[1]) || ""), m = q.get("mesure");
    if (m) {
      const b = document.querySelector('#metricSeg button[aria-pressed="true"]');
      if (!b || b.dataset.v !== m) sortie.defauts.push(`atlas : mesure « ${m} » de l'adresse non affichée (« ${b ? b.dataset.v : "aucune"} »)`);
      if (new URLSearchParams((location.hash.split("?")[1]) || "").get("mesure") !== m) sortie.defauts.push(`atlas : mesure « ${m} » perdue de l'adresse une fois la carte dessinée`);
      const nat = document.getElementById("natCard");
      if (m === "evol" && nat && !/évolution de la densité/.test(nat.textContent)) sortie.defauts.push("atlas : panneau de la France entière qui ne suit pas la mesure « Évolution »");
    }
  }
  // 11 quinquies bis. le « Comment lire » de la carte de l'atlas suit la mesure choisie : pour chaque mesure proposée,
  //     la définition de cette mesure, et aucune de celles des autres (la mesure « Évolution » expliquait la densité et
  //     l'écart à l'attendu, audit du 25 novembre 2026)
  {
    const seg = document.getElementById("metricSeg");
    if (seg && document.getElementById("mapbox")) {
      // au téléphone, la carte s'ouvre d'abord par « Voir la carte » ; le texte est cherché à chaque mesure, et il doit
      // être visible (posé dans un bloc que la carte récrit, il disparaissait au premier dessin)
      const voir = document.querySelector(".voir-carte");
      if (voir && vis(voir) && voir.getAttribute("aria-expanded") !== "true") { voir.click(); await new Promise(r => setTimeout(r, 300)); }
      const TERMES = { dens: "Densité pour 10 000 ou 100 000 habitants", n: "Effectif", ecart: "Écart à l'attendu", acces: "Accessibilité",
        trajet: "Temps de trajet", lieux: "Structures de soins", evol: "Évolution de la densité", zones: "Zones peu dotées et zones de concentration" };
      const net = s => s.replace(/­/g, "").replace(/[\s  ]+/g, " ").replace(/[’]/g, "'").replace(/\.$/, "").trim();
      const avant = seg.querySelector('button[aria-pressed="true"]');
      for (const b of seg.querySelectorAll("button[data-v]")) {
        if (b.disabled || !vis(b)) continue;
        const v = b.dataset.v, t = TERMES[v];
        b.click(); await new Promise(r => setTimeout(r, 300));
        const how = document.getElementById("mapHow");
        if (!how || !vis(how)) { sortie.defauts.push(`atlas : « Comment lire » de la carte absent ou caché, mesure « ${v} »`); continue; }
        const lus = [...how.querySelectorAll("p > strong")].map(s => net(s.textContent)).filter(x => x !== "Comment lire");
        if (!t) sortie.defauts.push(`atlas : mesure « ${v} » dont le contrôle ignore la définition attendue`);
        else if (!lus.includes(net(t))) sortie.defauts.push(`atlas : « Comment lire » de la carte sans la définition de la mesure « ${v} » (${lus.join(", ") || "vide"})`);
        const autres = Object.entries(TERMES).filter(([k, x]) => k !== v && lus.includes(net(x))).map(([, x]) => x);
        if (autres.length) sortie.defauts.push(`atlas : « Comment lire » de la carte, mesure « ${v} », qui explique aussi ${autres.join(", ")}`);
      }
      if (avant) { avant.click(); await new Promise(r => setTimeout(r, 300)); }
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
  // 11 septies b. Comparer et Croiser (structure validée le 26 novembre 2026) : sur la réglette de Comparer, chaque
  //     territoire sur sa rangée sous l'axe, aucune marque ne touche une autre marque, les barres, l'axe, le trait du repère
  //     ni le triangle de la médiane ; dans Croiser, les légendes des repères au-dessus du nuage ne se touchent pas
  {
    const touche = (a, b) => a.left < b.right - .5 && b.left < a.right - .5 && a.top < b.bottom - .5 && b.top < a.bottom - .5;
    let n = 0, ex = "";
    document.querySelectorAll(".rg.cmp").forEach(rg => {
      if (!vis(rg)) return;
      const pts = [...rg.querySelectorAll(".rg-pt")].map(e => e.getBoundingClientRect());
      const autres = [...rg.querySelectorAll(".rg-ens,.rg-med,.rg-hist,.rg-axe")].map(e => e.getBoundingClientRect());
      pts.forEach((a, i) => { if (pts.some((b, j) => j !== i && touche(a, b)) || autres.some(b => touche(a, b))) { n++; ex = ex || (rg.getAttribute("aria-label") || "").slice(0, 70); } });
    });
    if (n) sortie.defauts.push(`réglette de Comparer : ${n} marque(s) qui touchent une autre marque, les barres, le repère ou la médiane (${ex})`);
    const lr = document.getElementById("leg-reperes");
    if (lr && vis(lr)) {
      const s = [...lr.children].map(e => e.getBoundingClientRect());
      if (s.some((a, i) => s.some((b, j) => j > i && touche(a, b)))) sortie.defauts.push("légendes des repères du nuage de Croiser qui se touchent");
    }
  }
  // 11 ter. l'infobulle d'une carte tient entière à l'écran, son tableau compris (7 novembre 2026, atlas, médecins
  //     spécialistes : la colonne « Écart » débordait de l'infobulle et sortait de l'écran, vu). Survol de
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
  // 11 octies. le champ de la recherche de l'en-tête, caché jusqu'au clic : ouvert, son texte d'aide tient aussi
  {
    const bt = document.getElementById("bouton-chercher"), q = document.getElementById("q-tete");
    if (bt && q && vis(bt) && !vis(q)) {
      bt.click(); await new Promise(r => setTimeout(r, 200));
      if (vis(q)) aideTronquee(q);
      bt.click(); await new Promise(r => setTimeout(r, 100));
    }
  }
  // 11 nonies. une seule grille (exigence 19) : le contenu d'une page n'est jamais plus large que la grille de
  //     l'en-tête (Croiser s'étendait de 43 à 1 379 px à 1 440 px de large, au lieu de 111 à 1 311 px comme les autres
  //     pages, audit du 27 novembre 2026 ; à 1 280 px l’écart ne se voit pas, d’où la comparaison des largeurs maximales,
  //     jugée quand la fenêtre est plus large que la grille : au téléphone, la marge de 16 px réduit la grille, pas main)
  {
    const nav = document.querySelector("nav.site .in"), mains = [...document.querySelectorAll("main")].filter(vis);
    const px = v => (/^[\d.]+px$/.test(v) ? parseFloat(v) : Infinity);
    if (nav && vis(nav)) {
      const lg = px(getComputedStyle(nav).maxWidth);
      mains.forEach(m => {
        const lm = px(getComputedStyle(m).maxWidth);
        if (lg < Infinity && innerWidth > lg && lm > lg + 0.5) sortie.defauts.push(`contenu plus large que la grille commune : ${nom(m).slice(0, 40)} jusqu'à ${lm === Infinity ? "toute la largeur" : Math.round(lm) + " px"}, en-tête ${Math.round(lg)} px`);
      });
    }
  }
  // 11 decies. renvois « Résultat publié et méthode » d'Explorer au téléphone : un par ligne, tous au même bord, cible
  //     d'au moins 44 px (audit du 27 novembre 2026 : deux seuls sur leur ligne, puis deux par ligne)
  if (innerWidth <= 700) {
    document.querySelectorAll(".renvois-q").forEach(p => {
      if (!vis(p) || cache(p)) return;
      const r = [...p.querySelectorAll("a")].filter(vis).map(a => a.getBoundingClientRect());
      if (!r.length) return;
      const g = Math.min(...r.map(b => b.left)), d = Math.max(...r.map(b => b.left)), haut = r.map(b => b.top);
      if (d - g > 1 || new Set(haut.map(Math.round)).size < r.length) sortie.defauts.push(`renvois mal répartis au téléphone : ${nom(p).slice(0, 60)}`);
      if (r.some(b => b.height < 43.5)) sortie.defauts.push(`renvoi de moins de 44 px au téléphone : ${nom(p).slice(0, 60)}`);
    });
  }
  // 12. tailles du texte courant, par rôle (texte, tableaux et notes), lues par outils/controle_finition.py en papier :
  //     deux tailles au plus dans les rapports imprimés (6 novembre 2026)
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
