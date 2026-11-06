// Autour d'un lieu, ou sur un périmètre (présentation du 30 octobre 2026, maquette d-zone). Données Z de
// zone_donnees.js (pipeline/zone.py) : communes [code, nom, codes postaux, habitants, epci, département, lon, lat],
// structures [type, nom, lon, lat, confirmation c/v/r ou vide, commune, placée au centre de sa commune], masques par
// département (types dont la distance est retirée par la limite des manques de la SAE).
// Adresse de la zone : #lieu=CODE&rayon=10&fam=sm, #perimetre=CODE,CODE&fam=sm, ou #epci=SIREN (périmètre de
// l'intercommunalité, lien des fiches).
// Temps de route : Z.trajets (pipeline/zone.py, depuis pipeline/trajets.py) {seuils: [10, 15, 20, 30, 45], rapport,
// calcules: [rang des types calculés], communes: {code: [tranche par type calculé, null si au-delà]}}, à l'échelle du
// distancier de l'INSEE (décision de Lucas du 31 octobre 2026) ; le bouton « En temps de route » s'active et la colonne
// « La plus proche » donne la tranche de temps depuis le centre de la commune choisie, la distance pour les autres types.
(function () {
  var $ = function (i) { return document.getElementById(i); };
  var fr0 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });   // distances écrites par presentation/chiffres.js
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function pl(n, s) { return n > 1 ? s + "s" : s; }
  var PARCODE = {}, PAREPCI = {};
  Z.communes.forEach(function (x) { PARCODE[x[0]] = x; if (x[4]) (PAREPCI[x[4]] = PAREPCI[x[4]] || []).push(x[0]); });
  var AVEC_CONF = Z.types.map(function () { return false; });
  Z.structures.forEach(function (s) { if (s[4]) AVEC_CONF[s[0]] = true; });
  var INCOMPLET = {}; (Z.incomplets || []).forEach(function (k) { INCOMPLET[k] = 1; });
  var S = { mode: "z", com: null, r: 10, coms: [], fam: "sm", mesure: "vol" }, DERNIER = null, VOIR = false;

  function lireAdresse() {
    location.hash.slice(1).split("&").forEach(function (kv) {
      var p = kv.split("="), v = decodeURIComponent(p[1] || "");
      if (p[0] === "lieu" && PARCODE[v]) { S.mode = "z"; S.com = v; }
      if (p[0] === "rayon" && [5, 10, 20, 30].indexOf(+v) >= 0) S.r = +v;
      if (p[0] === "perimetre" && v) { S.mode = "p"; S.coms = v.split(",").filter(function (c) { return PARCODE[c]; }); }
      if (p[0] === "epci" && PAREPCI[v]) { S.mode = "p"; S.coms = PAREPCI[v].slice(); }
      if (p[0] === "fam" && (v === "sm" || v === "sante")) S.fam = v;
    });
  }
  function ecrireAdresse() {
    var h = S.mode === "p" ? (S.coms.length ? "perimetre=" + S.coms.join(",") : "") : (S.com ? "lieu=" + S.com + "&rayon=" + S.r : "");
    if (h) h += "&fam=" + S.fam;
    history.replaceState(null, "", h ? "#" + h : location.pathname + location.search);
  }
  var FOND = {};
  function charger(dep) {
    FOND[dep] = 1;
    fetch("presentation/zone_fond/" + dep + ".json").then(function (r) { return r.ok ? r.json() : null; }).then(function (f) { if (f) { FOND[dep] = f; rendre(); } }).catch(function () {});
  }
  function dist(a, b, c, d) { var R = 6371, t = Math.PI / 180, x = (c - a) * t * Math.cos((b + d) / 2 * t), y = (d - b) * t; return R * Math.sqrt(x * x + y * y); }
  function typesFam() { var o = []; for (var k = 0; k < Z.types.length; k++) if ((k < Z.sm) === (S.fam === "sm")) o.push(k); return o; }

  function rendre() {
    var P = S.mode === "p";
    document.querySelectorAll("[data-mode]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-mode") === S.mode)); });
    document.querySelectorAll("[data-fam]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-fam") === S.fam)); });
    document.querySelectorAll("[data-mesure]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-mesure") === S.mesure)); });
    $("b-route").disabled = !Z.trajets;
    if (Z.trajets) { $("b-route").textContent = "En temps de route"; $("b-route").title = "Temps de route en voiture depuis le centre de la population de la commune, à l’échelle du distancier de l’INSEE"; }
    $("rlim").hidden = !(S.mesure === "route" && Z.trajets && !P);
    $("perim").hidden = !P; $("reg-zone").hidden = P; $("plim").hidden = !P; $("leg-lieu").hidden = P; $("leg-com").hidden = !P;
    $("q-lab").textContent = P ? "Ajouter une commune ou toute une intercommunalité au périmètre" : "Le lieu, une commune ou un code postal";
    $("t-zr").textContent = P ? "Dans le périmètre" : "Dans la zone";
    $("th-dans").textContent = P ? "Dans le périmètre" : "Dans la zone";
    $("th-proche").textContent = P ? "La plus proche du centre" : "La plus proche";
    $("t-zc").textContent = P ? "Structures du périmètre et alentour" : "Structures de la zone";
    $("cap-zt").textContent = S.fam === "sm" ? "Structures de soins en santé mentale" : "Structures de soins en santé, proximité et urgences";
    ecrireAdresse();
    var com, lon, lat, R, dedans;
    if (P) {
      dedans = S.coms.map(function (c) { return PARCODE[c]; });
      $("perim-n").textContent = dedans.length ? fr0.format(dedans.length) + " " + pl(dedans.length, "commune") + " dans le périmètre." : "Le périmètre est vide. Ajoutez une première commune avec le champ ci-dessus.";
      var long = dedans.length > 8; $("p-voir").hidden = !long; $("perim-liste").hidden = long && !VOIR;
      $("p-voir").textContent = VOIR ? "Masquer la liste" : "Voir la liste et retirer des communes"; $("p-voir").setAttribute("aria-expanded", String(VOIR));
      $("perim-liste").innerHTML = dedans.map(function (x) { return "<li>" + esc(x[1]) + ' <button type="button" data-retirer="' + x[0] + '" aria-label="Retirer ' + esc(x[1]) + ' du périmètre">×</button></li>'; }).join("");
      $("p-epci").disabled = !dedans.length; $("p-vider").disabled = !dedans.length;
      var pc = dedans.filter(function (x) { return x[6] != null; }), pw = pc.reduce(function (s, x) { return s + (x[3] || 1); }, 0);
      if (!pc.length) { $("grille").hidden = true; $("vide").hidden = false; DERNIER = null; return; }
      lon = pc.reduce(function (s, x) { return s + x[6] * (x[3] || 1); }, 0) / pw; lat = pc.reduce(function (s, x) { return s + x[7] * (x[3] || 1); }, 0) / pw;
      R = Math.max(5, pc.reduce(function (m, x) { return Math.max(m, dist(lon, lat, x[6], x[7])); }, 0) + 3);
      com = [null, "ce périmètre"];
    } else {
      com = PARCODE[S.com];
      if (!com || com[6] == null) { $("grille").hidden = true; $("vide").hidden = false; DERNIER = null; return; }
      lon = com[6]; lat = com[7]; R = S.r;
      document.querySelectorAll("[data-r]").forEach(function (b) { b.setAttribute("aria-pressed", String(+b.getAttribute("data-r") === R)); });
      dedans = Z.communes.filter(function (x) { return x[6] != null && dist(lon, lat, x[6], x[7]) <= R; });
    }
    $("grille").hidden = false; $("vide").hidden = true;
    var dans = {}; dedans.forEach(function (x) { dans[x[0]] = 1; });
    var pop = dedans.reduce(function (s, x) { return s + x[3]; }, 0), deps = {};
    dedans.forEach(function (x) { deps[x[5]] = 1; });
    var ks = typesFam(), garde = {}; ks.forEach(function (k) { garde[k] = 1; });
    var parType = Z.types.map(function () { return { n: 0, conf: 0, proche: null, nomProche: "" }; }), pts = [], auCentre = 0;
    Z.structures.forEach(function (s) {
      if (!garde[s[0]]) return;
      var d = dist(lon, lat, s[2], s[3]), t = parType[s[0]];
      if (t.proche == null || d < t.proche) { t.proche = d; t.nomProche = s[1]; }
      if (P ? dans[s[5]] : d <= R) { t.n++; if (s[4] === "c") t.conf++; if (s[6]) auCentre++; }
      if (d <= R * 1.3) pts.push([s, d]);
    });
    var total = ks.reduce(function (s, k) { return s + parType[k].n; }, 0);
    var lieuTxt = P ? " du périmètre" : " dont le centre de la population est à moins de " + R + "&nbsp;km de celui de " + esc(com[1]);
    $("chz").innerHTML = '<div><span class="n">' + fr0.format(pop) + "</span><p>habitants dans " + fr0.format(dedans.length) + " " + pl(dedans.length, "commune") + lieuTxt + "</p></div>" +
      '<div><span class="n">' + fr0.format(total) + "</span><p>" + pl(total, "structure") + " de soins " + (S.fam === "sm" ? "en santé mentale" : "en santé, de proximité et d’urgence") + (P ? " dans le périmètre" : " dans la zone") + ", tous types confondus, chacune comptée une fois</p></div>";
    var masque = {}; Object.keys(deps).forEach(function (d) { (Z.masques[d] || []).forEach(function (k) { if (garde[k]) (masque[k] = masque[k] || []).push(d); }); });
    var route = S.mesure === "route" && Z.trajets && !P ? (Z.trajets.communes[S.com] || null) : null;
    // types bien recensés dans le tableau, types mal recensés dans un bloc à part, sans « 0 » ni distance (audit de
    // contrôle du 30 octobre 2026, point I11 et règle 6)
    $("zt").innerHTML = ks.filter(function (k) { return !INCOMPLET[k]; }).map(function (k) {
      var t = parType[k], sig = masque[k] ? ' <b class="sig" title="Moins de la moitié des structures déclarées à la SAE sont inscrites dans les bases, ' + masque[k].map(function (d) { return esc(Z.departements[d] || d); }).join(", ") + '">!</b>' : "";
      var inc = INCOMPLET[k], sigI = inc ? ' <b class="sig" title="Type recensé dans moins de 90&nbsp;% des départements, la structure existe souvent sans être inscrite sous ce type">!</b>' : "";
      var conf = t.n && AVEC_CONF[k] ? '<span class="c">' + (t.conf ? fr0.format(t.conf) + " " + pl(t.conf, "confirmée") : "aucune confirmée") + "</span>" : "";
      var proche = inc ? '<span class="c">non donnée</span>' : t.proche == null ? "aucune en France" : Chiffres.fmt(t.proche, "distance") + "&nbsp;km";
      var kr = route ? Z.trajets.calcules.indexOf(k) : -1;
      if (route && kr >= 0 && !inc) { var tr = route[kr]; proche = tr == null ? "plus de " + Z.trajets.seuils[Z.trajets.seuils.length - 1] + "&nbsp;min" : "moins de " + Z.trajets.seuils[tr] + "&nbsp;min"; }
      return "<tr><td>" + esc(Z.types[k]) + sig + sigI + '</td><td class="v">' + (inc && t.n ? "au moins " : "") + fr0.format(t.n) + conf + '</td><td class="v"' + (inc ? "" : ' title="' + esc(t.nomProche) + '"') + ">" + proche + "</td></tr>";
    }).join("");
    var zl = $("zlim"), mk = Object.keys(masque), dm = Object.keys(deps).filter(function (d) { return (Z.masques[d] || []).some(function (k) { return garde[k]; }); });
    zl.hidden = !mk.length;
    if (mk.length) zl.querySelector("span").textContent = "Pour " + mk.map(function (k) { return Z.types[k]; }).join(", ") + ", les bases inscrivent moins de la moitié des structures que les hôpitaux déclarent à la statistique annuelle des établissements de santé (SAE) " + (dm.length > 1 ? "dans ces départements, " : "dans ce département, ") + dm.map(function (d) { return Z.departements[d] || d; }).join(", ") + ". Ces structures peuvent manquer dans la zone.";
    var ik = ks.filter(function (k) { return INCOMPLET[k]; });
    $("mal").hidden = !ik.length;
    $("mal-liste").innerHTML = ik.map(function (k) { var t = parType[k]; return "<li><span>" + esc(Z.types[k]) + '</span><span class="v">' + (t.n ? "au moins " + fr0.format(t.n) : (Z.statuts && Z.statuts.r) || "non recensé") + "</span></li>"; }).join("");
    var cl = $("clim"); cl.hidden = !auCentre;
    if (auCentre) cl.querySelector("span").textContent = fr0.format(auCentre) + " " + pl(auCentre, "structure") + " de la zone " + (auCentre > 1 ? "sont placées" : "est placée") + " au centre de " + (auCentre > 1 ? "leur" : "sa") + " commune, faute d’adresse précise, " + (auCentre > 1 ? "leur distance est approchée" : "sa distance est approchée") + ".";
    // carte, projection locale équirectangulaire centrée sur le lieu
    var W = 520, H = 420, kx = Math.cos(lat * Math.PI / 180) * 111.32, ky = 110.57, e = R * 1.3, sc = Math.min(W, H) / (2 * e);
    function px(x) { return W / 2 + (x - lon) * kx * sc; } function py(y) { return H / 2 - (y - lat) * ky * sc; }
    // fond, contours des communes (ADMIN EXPRESS de l'IGN, simplifiés, un fichier par département chargé à la
    // demande), aplat des communes de la zone ou du périmètre, noms des principales communes, structures en symboles
    // distincts selon leur confirmation (audit de contrôle du 30 octobre 2026, point I2)
    var s = "", vue = [], depsVue = {};
    Z.communes.forEach(function (x) {
      if (x[6] == null) return; var X = px(x[6]), Y = py(x[7]);
      if (X < -60 || X > W + 60 || Y < -60 || Y > H + 60) return;
      depsVue[x[5]] = 1; if (X >= 0 && X <= W && Y >= 0 && Y <= H) vue.push(x);
    });
    var manque = Object.keys(depsVue).filter(function (d) { return !FOND[d]; });
    manque.forEach(charger);
    Object.keys(depsVue).forEach(function (d) {
      var f = FOND[d]; if (!f || f === 1) return;
      Object.keys(f.c).forEach(function (code) {
        var d2 = "";
        f.c[code].forEach(function (r) {
          var ix = r[0], iy = r[1], out = [];
          for (var k = 0; k < r.length; k += 2) { if (k) { ix += r[k]; iy += r[k + 1]; } out.push(px(f.o[0] + ix / 1e4).toFixed(1) + "," + py(f.o[1] + iy / 1e4).toFixed(1)); }
          d2 += "M" + out.join("L") + "Z";
        });
        var cl = dans[code] ? (P ? "fc sel" : "fc dans") : "fc";
        s += '<path class="' + cl + '" d="' + d2 + '"><title>' + esc((PARCODE[code] || [0, code])[1]) + "</title></path>";
      });
    });
    if (!P) s += '<circle class="cercle" cx="' + W / 2 + '" cy="' + H / 2 + '" r="' + (R * sc).toFixed(1) + '"/>';
    pts.forEach(function (p) {
      var st = p[0], X = px(st[2]), Y = py(st[3]); if (X < 0 || X > W || Y < 0 || Y > H) return;
      var hors = P && !dans[st[5]] ? " hors" : "", t = "<title>" + esc(Z.types[st[0]]) + ", " + esc(st[1]) + ", " + Chiffres.fmt(p[1], "distance") + " km" + (st[6] ? ", placée au centre de sa commune" : "") + "</title>";
      if (st[4] === "c") s += '<circle class="st c' + hors + '" cx="' + X.toFixed(1) + '" cy="' + Y.toFixed(1) + '" r="5">' + t + "</circle>";
      else if (st[4] === "v") s += '<circle class="st v' + hors + '" cx="' + X.toFixed(1) + '" cy="' + Y.toFixed(1) + '" r="4.5">' + t + "</circle>";
      else s += '<rect class="st o' + hors + '" x="' + (X - 4).toFixed(1) + '" y="' + (Y - 4).toFixed(1) + '" width="8" height="8" transform="rotate(45 ' + X.toFixed(1) + " " + Y.toFixed(1) + ')">' + t + "</rect>";
    });
    // noms des six communes les plus peuplées de la vue, et du lieu choisi
    vue.sort(function (a, b) { return b[3] - a[3]; });
    var noms = vue.slice(0, 6); if (!P && noms.indexOf(com) < 0) noms.push(com);
    noms.forEach(function (x) {
      var X = px(x[6]), Y = Math.max(14, py(x[7]) - 9), a = X < 90 ? "start" : X > W - 90 ? "end" : "middle";
      if (a === "start") X = Math.max(X, 6); if (a === "end") X = Math.min(X, W - 6);
      s += '<text class="nom-com" x="' + X.toFixed(1) + '" y="' + Y.toFixed(1) + '" text-anchor="' + a + '">' + esc(x[1]) + "</text>";
    });
    if (!P) {
      s += '<circle class="lieu" cx="' + W / 2 + '" cy="' + H / 2 + '" r="6"><title>' + esc(com[1]) + "</title></circle>";
      s += '<text class="echelle" x="' + (W / 2 + R * sc - 4) + '" y="' + (H / 2 - 8) + '" text-anchor="end">' + R + " km</text>";
    }
    $("zc").innerHTML = s;
    $("zc").setAttribute("aria-label", (P ? "Carte du périmètre de " : "Carte de la zone de " + R + " km autour de " + com[1] + ", ") + fr0.format(dedans.length) + " communes et " + fr0.format(total) + " structures");
    $("q").placeholder = P ? "Commune, code postal ou intercommunalité" : com[1] + " (" + (com[2].split(" ")[0] || com[0]) + ")";
    var ep = P ? null : com[4];
    $("vers-fiche").innerHTML = ep ? 'Les professionnels, le profil des habitants et les repères de son intercommunalité dans <a href="territoire/epci/' + ep + '.html?commune=' + com[0] + "&nom=" + encodeURIComponent(com[1]) + '">sa fiche</a>.' : "";
    var titre = P ? "Périmètre de " + fr0.format(dedans.length) + " " + pl(dedans.length, "commune") : "Zone de " + R + " km autour de " + com[1];
    $("cit-z").textContent = Z.citation + ", Ubi Cura, « " + titre + " », version du " + Z.version + (Z.doi ? ", doi:" + Z.doi : "") + ", " + location.href;
    DERNIER = { titre: titre, ks: ks, parType: parType, P: P };
  }

  function telecharger(b, n) { var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = n; a.click(); }
  // figure exportée sur fond blanc avec les couleurs du fond clair, comme dans l'atelier
  function svgFondBlanc() {
    var racine = document.documentElement, avant = racine.getAttribute("data-theme"), svg = $("zc");
    racine.setAttribute("data-theme", "light");
    var copie = svg.cloneNode(true), orig = svg.querySelectorAll("*"), dest = copie.querySelectorAll("*");
    for (var k = 0; k < orig.length; k++) { var cs = getComputedStyle(orig[k]); ["fill", "stroke", "stroke-width", "stroke-dasharray", "opacity", "font-size", "font-family", "font-weight", "paint-order"].forEach(function (p) { dest[k].style.setProperty(p, cs.getPropertyValue(p)); }); }
    racine.setAttribute("data-theme", avant);
    var fond = document.createElementNS("http://www.w3.org/2000/svg", "rect"); fond.setAttribute("width", "520"); fond.setAttribute("height", "420"); fond.setAttribute("fill", "#fff");
    copie.insertBefore(fond, copie.firstChild);
    copie.setAttribute("width", 520); copie.setAttribute("height", 420); copie.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    return new XMLSerializer().serializeToString(copie);
  }
  function exporter(k) {
    if (!DERNIER) return;
    if (k === "lien") { try { navigator.clipboard.writeText(location.href); } catch (e) {} $("lien-z").textContent = "Lien copié."; return; }
    if (k === "svg") { telecharger(new Blob([svgFondBlanc()], { type: "image/svg+xml" }), "zone_ubicura.svg"); return; }
    if (k === "png") {
      var img = new Image(), url = URL.createObjectURL(new Blob([svgFondBlanc()], { type: "image/svg+xml" }));
      img.onload = function () { var c = document.createElement("canvas"); c.width = 1040; c.height = 840; var x = c.getContext("2d"); x.fillStyle = "#fff"; x.fillRect(0, 0, c.width, c.height); x.drawImage(img, 0, 0, c.width, c.height); URL.revokeObjectURL(url); c.toBlob(function (b) { telecharger(b, "zone_ubicura.png"); }); };
      img.src = url; return;
    }
    var l = ["# " + DERNIER.titre, "type;" + (DERNIER.P ? "dans_le_perimetre" : "dans_la_zone") + ";dont_confirmees;plus_proche_km;recensement_complet"];
    DERNIER.ks.forEach(function (k) { var t = DERNIER.parType[k]; l.push('"' + Z.types[k].replace(/"/g, '""') + '";' + t.n + ";" + (AVEC_CONF[k] ? t.conf : "") + ";" + (t.proche == null || INCOMPLET[k] ? "" : String(Math.round(t.proche * 10) / 10).replace(".", ",")) + ";" + (INCOMPLET[k] ? "non" : "oui")); });
    l.push("# Source, " + Z.citation + ", Ubi Cura, version du " + Z.version + (Z.doi ? ", doi:" + Z.doi : "") + ", distances à vol d'oiseau depuis le centre de la population");
    telecharger(new Blob(["﻿" + l.join("\n") + "\n"], { type: "text/csv" }), "zone_ubicura.csv");
  }

  document.addEventListener("click", function (ev) {
    var o = ev.target.closest("[data-panneau]");
    if (o) {
      var p = $(o.getAttribute("data-panneau")), ouvert = o.getAttribute("aria-expanded") === "true";
      o.parentNode.querySelectorAll("[data-panneau]").forEach(function (x) { x.setAttribute("aria-expanded", "false"); var q = $(x.getAttribute("data-panneau")); if (q) q.hidden = true; });
      if (!ouvert && p) { o.setAttribute("aria-expanded", "true"); p.hidden = false; }
      return;
    }
    var x = ev.target.closest("[data-export]"); if (x) { exporter(x.getAttribute("data-export")); return; }
    var b = ev.target.closest("[data-r],[data-mode],[data-fam],[data-mesure],[data-retirer],#p-epci,#p-vider,#p-voir"); if (!b || b.disabled) return;
    if (b.hasAttribute("data-r")) S.r = +b.getAttribute("data-r");
    else if (b.hasAttribute("data-mode")) { S.mode = b.getAttribute("data-mode"); if (S.mode === "p" && !S.coms.length && S.com) S.coms = [S.com]; if (S.mode === "z" && !S.com && S.coms.length) S.com = S.coms.reduce(function (m, c) { return PARCODE[c][3] > PARCODE[m][3] ? c : m; }); }
    else if (b.hasAttribute("data-fam")) S.fam = b.getAttribute("data-fam");
    else if (b.hasAttribute("data-mesure")) S.mesure = b.getAttribute("data-mesure");
    else if (b.hasAttribute("data-retirer")) { var c = b.getAttribute("data-retirer"); S.coms = S.coms.filter(function (y) { return y !== c; }); }
    else if (b.id === "p-vider") S.coms = [];
    else if (b.id === "p-voir") VOIR = !VOIR;
    else if (b.id === "p-epci") { var ep = PARCODE[S.coms[S.coms.length - 1]][4]; (PAREPCI[ep] || []).forEach(function (y) { if (S.coms.indexOf(y) < 0) S.coms.push(y); }); }
    rendre();
  });
  Recherche.brancher($("q"), $("sugg"), $("msg"), "", function (cible, e) {
    if (e.t === "epci" && S.mode === "p") { (PAREPCI[e.c] || []).forEach(function (y) { if (S.coms.indexOf(y) < 0) S.coms.push(y); }); }
    else if (e.t !== "com") { $("msg").textContent = S.mode === "p" ? "Choisissez une commune ou une intercommunalité, le périmètre se compose à partir d’elles." : "Choisissez une commune, la zone se trace autour d’elle."; return; }
    else if (S.mode === "p") { if (S.coms.indexOf(e.c) < 0) S.coms.push(e.c); }
    else S.com = e.c;
    $("q").value = ""; rendre();
  });
  lireAdresse(); rendre();
})();
