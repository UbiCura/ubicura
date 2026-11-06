// Matrice des liens entre l'offre et les autres domaines (avis de l'auditeur externe du 30 octobre 2026). Données L de
// liens_donnees.js (pipeline/liens.py), règle unique Lien (lien.js). Case [rho, bas, haut, q, rho partiel, bas, haut,
// q partiel, territoires]. Adresse de la vue : #niv=epci&mode=p&fam=sm&vue=matrice&prof=psychologue.
(function () {
  var $ = function (i) { return document.getElementById(i); };
  var fr2 = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }), fr0 = new Intl.NumberFormat("fr-FR");
  function r2(v) { return fr2.format(v).replace("-", "−"); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  var TEL = matchMedia("(max-width: 640px)");
  var S = { niv: "epci", mode: "p", fam: "sm", vue: "matrice", prof: null, tout: false, dist: false };
  var DOMNOM = {}; L.domaines.forEach(function (d) { DOMNOM[d.id] = d.nom; });
  var LIGNE = {}; L.lignes.forEach(function (l) { LIGNE[l.id] = l; });

  function lire() {
    location.hash.slice(1).split("&").forEach(function (kv) {
      var p = kv.split("="), v = decodeURIComponent(p[1] || "");
      if (p[0] === "niv" && L.cases[v]) S.niv = v;
      if (p[0] === "mode" && (v === "p" || v === "b")) S.mode = v;
      if (p[0] === "fam" && L.colonnes[v]) S.fam = v;
      if (p[0] === "vue" && /^(matrice|liste|etoile)$/.test(v)) S.vue = v;
      if (p[0] === "prof") S.prof = v;
    });
  }
  function ecrire() { history.replaceState(null, "", "#niv=" + S.niv + "&mode=" + S.mode + "&fam=" + S.fam + "&vue=" + S.vue + (S.prof ? "&prof=" + S.prof : "")); }
  // valeurs de la case selon la comparaison choisie : rho, bas, haut, q, territoires
  function val(p, v) {
    var c = L.cases[S.niv][p + "|" + v]; if (!c) return null;
    if (S.mode === "p") { if (v === "densite_pop") return { tenue: true }; return { r: c[4], lo: c[5], hi: c[6], q: c[7], n: c[8] }; }
    return { r: c[0], lo: c[1], hi: c[2], q: c[3], n: c[8] };
  }
  function couleur(r) {
    var a = Math.min(1, Math.abs(r)), pct = Math.round(38 + 62 * Math.min(1, (a - L.seuil) / (0.7 - L.seuil)));
    return "color-mix(in srgb," + (r > 0 ? "var(--d5)" : "var(--d1)") + " " + pct + "%,var(--panel))";
  }
  function nuage(p, v) { return "croiser.html#x=" + v + "&y=prof:" + p + ":all&lv=" + S.niv + (S.mode === "p" ? "&z=densite_pop&zm=p" : "&z=&zm=t"); }
  function bulle(p, v, x) {
    var col = colonnes().filter(function (c) { return c.id === p; })[0];
    if (!x) return LIGNE[v].lab + ", indicateur absent à ce niveau";
    if (x.tenue) return "Densité de population, tenue égale dans cette comparaison";
    var t = col.lab + " et " + LIGNE[v].lab.charAt(0).toLowerCase() + LIGNE[v].lab.slice(1) + ", corrélation de rang " + (S.mode === "p" ? "à densité égale " : "") + r2(x.r);
    if (x.lo != null && x.hi != null) t += " (intervalle de " + r2(x.lo) + " à " + r2(x.hi) + ")";
    if (x.n) t += ", " + fr0.format(x.n) + " " + (S.niv === "epci" ? "intercommunalités" : "départements");
    return t + (Lien.est(x.r, x.q) ? "" : ", sous le seuil du lien");
  }
  function colonnes() { return L.colonnes[S.fam]; }
  function liensDe(p) {
    var out = [];
    L.lignes.forEach(function (l) { if (l.dom === "distances" && !S.dist) return; var x = val(p, l.id); if (x && !x.tenue && Lien.est(x.r, x.q)) out.push({ l: l, x: x }); });
    return out.sort(function (a, b) { return Math.abs(b.x.r) - Math.abs(a.x.r); });
  }

  function matrice() {
    var cols = colonnes(), h = '<div class="defile-m"><table class="mat" data-cite="1"><caption class="discret" style="text-align:left;padding-bottom:6px">Liens entre les ' + (S.fam === "sm" ? "professions de santé mentale" : "principales professions de santé") + " et les indicateurs des autres domaines, par " + (S.niv === "epci" ? "intercommunalité" : "département") + (S.mode === "p" ? ", à densité de population égale" : ", corrélation brute") + '</caption><thead><tr><th scope="col">Indicateur</th>';
    cols.forEach(function (c) { h += '<th scope="col" title="' + esc(c.lab) + '">' + (c.fiche ? '<a href="indicateur/' + c.fiche + '.html">' + esc(c.court || c.lab) + "</a>" : esc(c.court || c.lab)) + "</th>"; });
    h += "</tr></thead><tbody>";
    var caches = 0, dom = "";
    L.lignes.forEach(function (l) {
      if (l.dom === "distances" && !S.dist) return;
      var cells = cols.map(function (c) { return val(c.id, l.id); });
      var present = cells.some(function (x) { return x; }), lien = cells.some(function (x) { return x && !x.tenue && Lien.est(x.r, x.q); });
      if (!present) return;
      if (!lien && !S.tout) { caches++; return; }
      if (l.dom !== dom) { dom = l.dom; h += '<tr class="dom"><th colspan="' + (cols.length + 1) + '"><span>' + esc(DOMNOM[dom]) + "</span></th></tr>"; }
      h += '<tr><th scope="row" title="' + esc(l.long || l.lab) + '">' + (l.fiche ? '<a href="indicateur/' + l.fiche + '.html">' + esc(l.lab) + "</a>" : esc(l.lab)) + "</th>";
      cells.forEach(function (x, k) {
        var t = esc(bulle(cols[k].id, l.id, x));
        if (!x) h += '<td class="abs" title="' + t + '"></td>';
        else if (x.tenue) h += '<td class="vide" title="' + t + '">·</td>';
        else if (Lien.est(x.r, x.q)) h += '<td style="background:' + couleur(x.r) + '"><a href="' + nuage(cols[k].id, l.id) + '" title="' + t + '" aria-label="' + t + '">' + r2(x.r) + "</a></td>";
        else h += '<td class="vide"><a href="' + nuage(cols[k].id, l.id) + '" title="' + t + '" aria-label="' + t + '"></a></td>';
      });
      h += "</tr>";
    });
    h += "</tbody></table></div>";
    h += '<p class="plus-l">Les distances aux structures de soins, qui comparent l’offre à l’offre, sont rangées à part. <button type="button" id="b-dist">' + (S.dist ? "Les masquer" : "Les montrer") + "</button></p>";
    if (caches || S.tout) h += '<p class="plus-l">' + (S.tout ? '<button type="button" id="b-tout">Masquer les indicateurs sans lien</button>' : fr0.format(caches) + " indicateur" + (caches > 1 ? "s" : "") + " sans aucun lien au-delà du seuil à ce niveau. " + '<button type="button" id="b-tout">Les montrer</button>') + "</p>";
    return h;
  }
  // phrase de lecture au-dessus de la matrice, tirée du lien le plus fort hors distances (point I5)
  function lecture() {
    var best = null;
    colonnes().forEach(function (c) { L.lignes.forEach(function (l) { if (l.dom === "distances") return; var x = val(c.id, l.id); if (x && !x.tenue && Lien.est(x.r, x.q) && (!best || Math.abs(x.r) > Math.abs(best.x.r))) best = { c: c, l: l, x: x }; }); });
    var niv = S.niv === "epci" ? "intercommunalités" : "départements", eg = S.mode === "p" ? "À densité de population égale, " : "";
    if (!best) return "<p class=\"lecture\">" + eg + "aucun indicateur des autres domaines n’est lié à ces professions au-delà du seuil, entre " + niv + ".</p>";
    var v = best.l.lab.charAt(0).toLowerCase() + best.l.lab.slice(1);
    return '<p class="lecture">' + eg + "le lien le plus fort relie les " + esc(best.c.lab.toLowerCase()) + " et l’indicateur « " + esc(v) + " » (" + r2(best.x.r) + "). Les " + niv + " où cet indicateur est plus élevé comptent plutôt " + (best.x.r > 0 ? "plus" : "moins") + " de " + esc(best.c.lab.toLowerCase()) + ".</p>";
  }
  function choixProf() {
    var cols = colonnes(); if (!S.prof || !cols.some(function (c) { return c.id === S.prof; })) S.prof = cols[0].id;
    return '<div class="choix-p" role="group" aria-label="Profession">' + cols.map(function (c) { return '<button type="button" data-prof="' + c.id + '" aria-pressed="' + (c.id === S.prof) + '">' + esc(c.lab) + "</button>"; }).join("") + "</div>";
  }
  function liste() {
    var choix = choixProf(), ls = liensDe(S.prof), col = colonnes().filter(function (c) { return c.id === S.prof; })[0];
    var h = choix + '<h2 style="font-size:1.125rem;margin:0 0 6px;border:0;padding:0">Les liens les plus forts avec les ' + esc(col.lab.toLowerCase()) + (S.mode === "p" ? ", à densité de population égale" : "") + "</h2>";
    if (!ls.length) return h + '<p class="discret">Aucun indicateur n’est lié aux ' + esc(col.lab.toLowerCase()) + " au-delà du seuil à ce niveau.</p>";
    h += '<ol class="liste">';
    ls.slice(0, 15).forEach(function (o) {
      var x = o.x, l = o.l;
      h += '<li><a class="q" href="' + nuage(S.prof, l.id) + '">' + esc(l.lab) + '</a><span class="d">' + esc(DOMNOM[l.dom]) + ", " + (x.r > 0 ? "plus élevé là où les " + esc(col.lab.toLowerCase()) + " sont plus nombreux" : "plus bas là où les " + esc(col.lab.toLowerCase()) + " sont plus nombreux") + ', <span class="v">' + r2(x.r) + "</span>" + (x.lo != null ? " (" + r2(x.lo) + " à " + r2(x.hi) + ")" : "") + '</span><span class="barre-l" style="width:' + Math.round(Math.abs(x.r) * 100) + "%;background:" + couleur(x.r) + '" aria-hidden="true"></span></li>';
    });
    return h + "</ol>" + (ls.length > 15 ? '<p class="discret">' + (ls.length - 15) + " autres liens dans la matrice.</p>" : "");
  }
  function etoile() {
    var choix = choixProf(), ls = liensDe(S.prof).slice(0, 8), col = colonnes().filter(function (c) { return c.id === S.prof; })[0];
    var ordre = L.domaines.map(function (d) { return d.id; });
    ls.sort(function (a, b) { return ordre.indexOf(a.l.dom) - ordre.indexOf(b.l.dom) || Math.abs(b.x.r) - Math.abs(a.x.r); });
    var W = 880, H = 520, cx = W / 2, cy = H / 2, R = 190, s = '<svg id="etoile" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Les ' + ls.length + " liens les plus forts autour des " + esc(col.lab.toLowerCase()) + '">';
    s += '<text x="' + cx + '" y="24" text-anchor="middle" font-size="15" fill="var(--muted, #5D6371)" font-family="Newsreader, Georgia, serif">Ces territoires se ressemblent sur ces deux points, cela ne dit pas pourquoi.</text>';
    ls.forEach(function (o, k) {
      var a = -Math.PI / 2 + (k + 0.5) * 2 * Math.PI / Math.max(ls.length, 1), x = cx + R * Math.cos(a), y = cy + 14 + R * Math.sin(a) * 0.82;
      var w = (1.5 + 9 * (Math.abs(o.x.r) - L.seuil) / (1 - L.seuil)).toFixed(1), c = o.x.r > 0 ? "var(--d5, #2A6B66)" : "var(--d1, #BC6B3B)";
      s += '<a href="' + nuage(S.prof, o.l.id) + '"><line x1="' + cx + '" y1="' + (cy + 14) + '" x2="' + x.toFixed(1) + '" y2="' + y.toFixed(1) + '" stroke="' + c + '" stroke-width="' + w + '" stroke-linecap="round"><title>' + esc(bulle(S.prof, o.l.id, o.x)) + "</title></line>";
      s += '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="6" fill="' + c + '"/>';
      var droite = Math.cos(a) >= 0, tx = x + (droite ? 12 : -12), mots = o.l.lab.split(" "), l1 = "", l2 = "";
      mots.forEach(function (m) { if ((l1 + " " + m).length <= 30 && !l2) l1 = (l1 + " " + m).trim(); else l2 = (l2 + " " + m).trim(); });
      if (l2.length > 32) l2 = l2.slice(0, 31) + "…";
      s += '<text x="' + tx.toFixed(1) + '" y="' + (y - (l2 ? 4 : -4)).toFixed(1) + '" text-anchor="' + (droite ? "start" : "end") + '" font-size="13" fill="var(--ink, #1C2028)" font-family="Work Sans, sans-serif">' + esc(l1) + (l2 ? '<tspan x="' + tx.toFixed(1) + '" dy="15">' + esc(l2) + "</tspan>" : "") + '<tspan x="' + tx.toFixed(1) + '" dy="15" fill="var(--muted, #5D6371)" font-size="12">' + esc(DOMNOM[o.l.dom]) + ", " + r2(o.x.r) + "</tspan></text></a>";
    });
    s += '<circle cx="' + cx + '" cy="' + (cy + 14) + '" r="44" fill="var(--panel, #FFFFFF)" stroke="var(--r4, #0E5A5A)" stroke-width="2"/><text x="' + cx + '" y="' + (cy + 19) + '" text-anchor="middle" font-size="14" font-weight="600" fill="var(--ink, #1C2028)" font-family="Work Sans, sans-serif">' + esc(col.lab) + "</text></svg>";
    return choix + (ls.length ? s : '<p class="discret">Aucun indicateur n’est lié aux ' + esc(col.lab.toLowerCase()) + " au-delà du seuil à ce niveau.</p>") + '<p class="discret">Les huit liens les plus forts au plus, rangés par domaine. Un clic sur un trait ouvre le nuage de points.</p>';
  }

  function rendre() {
    if (TEL.matches && S.vue !== "liste") S.vue = "liste";
    document.querySelectorAll("[data-niv]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-niv") === S.niv)); });
    document.querySelectorAll("[data-mode]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-mode") === S.mode)); });
    document.querySelectorAll("[data-fam]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-fam") === S.fam)); });
    document.querySelectorAll("[data-vue]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-vue") === S.vue)); });
    $("t-vue").textContent = { matrice: "Matrice des liens", liste: "Liste des liens les plus forts", etoile: "Les liens autour d’une profession" }[S.vue];
    document.querySelectorAll(".pour-etoile").forEach(function (b) { b.hidden = S.vue !== "etoile"; });
    $("corps-v").innerHTML = S.vue === "matrice" ? lecture() + matrice() : S.vue === "liste" ? liste() : etoile();
    ecrire();
    $("cit-l").textContent = "Pithon L., Ubi Cura, « " + $("t-vue").textContent + " », version du " + L.version + (L.doi ? ", doi:" + L.doi : "") + ", " + location.href;
  }
  function exporter(k) {
    if (k === "lien") { try { navigator.clipboard.writeText(location.href); } catch (e) {} $("lien-l").textContent = "Lien copié."; return; }
    if (k === "csv") {
      var l = ["profession;indicateur;domaine;niveau;comparaison;rho;ic95_bas;ic95_haut;q_bh;territoires;lien"];
      colonnes().forEach(function (c) { L.lignes.forEach(function (li) { var x = val(c.id, li.id); if (!x || x.tenue) return; l.push([c.id, li.id, li.dom, S.niv, S.mode === "p" ? "densite_egale" : "brute", x.r, x.lo, x.hi, x.q, x.n, Lien.est(x.r, x.q) ? "oui" : "non"].map(function (v) { return v == null ? "" : String(v).replace(".", ","); }).join(";")); }); });
      l.push("# Source, Pithon L., Ubi Cura, version du " + L.version + (L.doi ? ", doi:" + L.doi : "") + ", correlations_contexte.csv, lien si |rho| >= " + String(L.seuil).replace(".", ",") + " et q < " + String(L.alpha).replace(".", ","));
      telecharger(new Blob(["﻿" + l.join("\n") + "\n"], { type: "text/csv" }), "liens_ubicura.csv"); return;
    }
    var svg = document.getElementById("etoile"); if (!svg) return;
    var racine = document.documentElement, avant = racine.getAttribute("data-theme"); racine.setAttribute("data-theme", "light");
    var copie = svg.cloneNode(true), o = svg.querySelectorAll("*"), d = copie.querySelectorAll("*");
    for (var i = 0; i < o.length; i++) { var cs = getComputedStyle(o[i]); ["fill", "stroke"].forEach(function (p) { d[i].style.setProperty(p, cs.getPropertyValue(p)); }); }
    racine.setAttribute("data-theme", avant);
    var fond = document.createElementNS("http://www.w3.org/2000/svg", "rect"); fond.setAttribute("width", "880"); fond.setAttribute("height", "520"); fond.setAttribute("fill", "#fff"); copie.insertBefore(fond, copie.firstChild);
    copie.setAttribute("xmlns", "http://www.w3.org/2000/svg"); copie.setAttribute("width", 880); copie.setAttribute("height", 520);
    var txt = new XMLSerializer().serializeToString(copie);
    if (k === "svg") { telecharger(new Blob([txt], { type: "image/svg+xml" }), "liens_ubicura.svg"); return; }
    var img = new Image(), url = URL.createObjectURL(new Blob([txt], { type: "image/svg+xml" }));
    img.onload = function () { var c = document.createElement("canvas"); c.width = 1760; c.height = 1040; var x = c.getContext("2d"); x.fillStyle = "#fff"; x.fillRect(0, 0, c.width, c.height); x.drawImage(img, 0, 0, c.width, c.height); URL.revokeObjectURL(url); c.toBlob(function (b) { telecharger(b, "liens_ubicura.png"); }); };
    img.src = url;
  }
  function telecharger(b, n) { var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = n; a.click(); }

  document.addEventListener("click", function (ev) {
    var o = ev.target.closest("[data-panneau]");
    if (o) { var p = $(o.getAttribute("data-panneau")), ouvert = o.getAttribute("aria-expanded") === "true";
      o.parentNode.querySelectorAll("[data-panneau]").forEach(function (x) { x.setAttribute("aria-expanded", "false"); var q = $(x.getAttribute("data-panneau")); if (q) q.hidden = true; });
      if (!ouvert && p) { o.setAttribute("aria-expanded", "true"); p.hidden = false; } return; }
    var x = ev.target.closest("[data-export]"); if (x) { exporter(x.getAttribute("data-export")); return; }
    var b = ev.target.closest("[data-niv],[data-mode],[data-fam],[data-vue],[data-prof],#b-tout,#b-dist"); if (!b) return;
    if (b.id === "b-tout") S.tout = !S.tout;
    if (b.id === "b-dist") S.dist = !S.dist;
    ["niv", "mode", "fam", "vue", "prof"].forEach(function (k) { if (b.hasAttribute("data-" + k)) S[k] = b.getAttribute("data-" + k); });
    rendre();
  });
  // échelle de la légende, du seuil au lien le plus fort
  [["ech-neg", -1], ["ech-pos", 1]].forEach(function (e) { $(e[0]).innerHTML = [0.3, 0.45, 0.6, 0.75].map(function (a) { return '<i style="background:' + couleur(e[1] * a) + '"></i>'; }).join(""); });
  var s = L.seuil.toFixed(1).replace(".", ",");
  $("regle").textContent = "Sur tout le site, deux indicateurs sont dits liés quand leur corrélation de rang entre territoires atteint au moins " + s + " en valeur absolue et passe la correction de Benjamini-Hochberg des tests multiples. La même règle vaut dans l’atelier et dans les rapports.";
  TEL.addEventListener("change", rendre);
  lire(); rendre();
})();
