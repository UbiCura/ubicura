// Page d'indicateur, étape 3 des portes d'entrée (maquette P3 validée le 14 novembre 2026, prototypes/entrees/p2_p3/) :
// 1. « Votre territoire » : une commune, un code postal, une intercommunalité, un département ou une région, lus dans
//    l'index de recherche du site (presentation/recherche.json) ; une commune est lue dans son intercommunalité, ou au
//    niveau le plus fin où l'indicateur est publié. La valeur, la position, le repère et la limite viennent du fichier
//    publié du territoire (territoire/<niveau>/<code>.json, écrit par pipeline/reponses.py avec la règle d'affichage
//    unique), la réglette de celle de sa fiche (indicateur/reglettes/<page>.json) : rien n'est recalculé ici.
// 2. La carte cliquable : un clic sur un département le cerne et affiche sa valeur à côté, sans zoom.
// Le territoire épinglé du lecteur (epingle.js) remplit le champ à l'ouverture.
(function () {
  var V = document.getElementById("votre"); if (!V) return;
  var id = V.dataset.ind, niv = (V.dataset.niv || "").split(/\s+/), slug = V.dataset.slug, unite = V.dataset.unite || "", racine = "../";
  var NOM = { reg: "région", dep: "département", epci: "intercommunalité", com: "commune" };
  var SON = { reg: "sa région", dep: "son département", epci: "son intercommunalité" };
  var REPERE = { dep: "Ensemble des départements", reg: "Ensemble des régions", epci: "Ensemble des intercommunalités" };
  function e(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function sa(s) { return String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[-'’]/g, " ").replace(/\s+/g, " ").trim(); }
  function zero(v) { return /^0([,.]0+)?$/.test((v || "").trim()); }
  var cache = {};
  function lire(u) { return cache[u] = cache[u] || fetch(u).then(function (r) { if (!r.ok) throw new Error(u); return r.json(); }); }
  function terr(lv, c) { return lire(racine + "territoire/" + lv + "/" + c + ".json"); }

  // l'index des territoires, chargé à la première frappe
  var IDX = null, depNom = {}, regNom = {}, regDeDep = {}, depDeEpci = {};
  function charger() {
    return IDX ? Promise.resolve(IDX) : lire(racine + "presentation/recherche.json").then(function (d) {
      IDX = [];
      (d.territoires.reg || []).forEach(function (u) { regNom[u[1]] = u[0]; IDX.push({ t: "reg", c: u[0], nm: u[1], k: sa(u[1]), pop: u[2] }); });
      (d.territoires.dep || []).forEach(function (u) { depNom[u[1]] = u[0]; regDeDep[u[0]] = regNom[u[3]]; IDX.push({ t: "dep", c: u[0], nm: u[1], k: sa(u[1] + " " + u[0]), pop: u[2] }); });
      (d.territoires.epci || []).forEach(function (u) { depDeEpci[u[0]] = depNom[u[3]]; IDX.push({ t: "epci", c: u[0], nm: u[1], k: sa(u[1]), pop: u[2] }); });
      (d.communes || []).forEach(function (k) { IDX.push({ t: "com", c: k[0], nm: k[1], k: sa(k[1]), cp: k[2], pop: k[3], epci: k[4] }); });
      // les arrondissements de Paris, Lyon et Marseille, lus dans leur commune (« Lyon 3e arrondissement », 69003)
      (d.arrondissements || []).forEach(function (k) { var nm = k[1].replace(/ Arrondissement$/, " arrondissement");
        IDX.push({ t: "com", arr: true, c: k[5] || k[0], nm: nm, k: sa(nm), cp: k[2], pop: k[3], epci: k[4] }); });
      return IDX;
    });
  }
  function depDeCommune(c) { return /^97/.test(c) ? c.slice(0, 3) : c.slice(0, 2); }
  // le territoire où se lit la valeur : le niveau choisi s'il est publié, sinon le plus fin des niveaux au-dessus
  function cible(x) {
    var a = niv.indexOf.bind(niv);
    if (x.t === "com") {
      if (a("epci") >= 0 && x.epci) return { lv: "epci", c: x.epci };
      var dp = depDeCommune(x.c); if (a("dep") >= 0) return { lv: "dep", c: dp };
      return regDeDep[dp] && a("reg") >= 0 ? { lv: "reg", c: regDeDep[dp] } : null;
    }
    if (a(x.t) >= 0) return { lv: x.t, c: x.c };
    if (x.t === "epci") { var d = depDeEpci[x.c]; if (d && a("dep") >= 0) return { lv: "dep", c: d }; x = { t: "dep", c: d }; }
    if (x.t === "dep" && regDeDep[x.c] && a("reg") >= 0) return { lv: "reg", c: regDeDep[x.c] };
    return null;
  }

  // ce que la fiche écrit : la valeur (jamais un 0 seul), l'unité, l'effectif, la position avec l'écart en couleur
  // seulement quand la fiche le colore, le repère, la limite
  function lecture(v, lv) {
    var eff = v[0] || "", val = v[1] || "", pos = v[2] || "", lim = v[3] || "", rlib = v[4] || "", rval = v[5] || "", note = v[6] || "", kind = v[7] || "", coul = v[8] || "";
    var aucun = eff === "aucun";
    if (!rlib && !rval) { var m = /l.ensemble \(([\d\s   ,]+(?: km)?)\)/.exec(pos); if (m) { rlib = REPERE[lv]; rval = m[1]; pos = pos.replace(" (" + m[1] + ")", ""); } }
    // une distance garde son unité dans le repère, comme dans la réglette (« 2,6 km »)
    if (kind === "dist" && rval && !/km/.test(rval)) rval += " km";
    var plus = [];
    if (val && unite) plus.push(unite);
    if (kind === "prof" && eff && !aucun) plus.push("effectif " + eff);
    if (kind === "lieux" && eff && !aucun) plus.push(eff + (eff === "0" || eff === "1" ? " lieu" : " lieux"));
    if (note && !aucun) plus.push(note);
    else if (!note && zero(val)) plus.push(kind === "prof" ? "aucun inscrit" : kind === "lieux" ? "aucune structure recensée" : "valeur nulle");
    var p = /^(\d[\d   \s]* ?% (?:au-dessus de|sous) l.ensemble)(.*)$/.exec(pos);
    var posH = p ? '<span class="ec ' + (coul === "haut" || coul === "bas" ? coul : "neutre") + '">' + e(p[1]) + "</span>" + e(p[2]) : e(pos);
    return { val: val || (aucun ? (note || "aucun") : "non publié"), plus: plus.join(", "), pos: posH, posT: pos,
             rep: rval ? (rlib || REPERE[lv]).toLowerCase() + " : " + rval : "", lim: lim };
  }
  function limite(t) { return t ? '<p class="limite"><b aria-hidden="true">!</b><span>' + e(t) + "</span></p>" : ""; }
  function posRep(L) { return '<p class="vt-pos">' + L.pos + (L.rep ? (L.pos ? " ; " : "") + "repère, " + e(L.rep) : "") + "</p>"; }

  // la réglette de la fiche du territoire
  function reglette(G, lv, c, L) {
    var g = G && G[lv]; if (!g) return "";
    if (g.x[c]) return g.x[c];
    var d = g.d[c]; if (!d) return "";
    var h = g.t.replace("§C§", d[1] || "").replace("§A§", e(L.val + (L.val && /\d/.test(L.val) && unite ? " " + unite : "") + (L.posT ? ", " + L.posT : "") + g.a));
    return d[0] == null ? h.replace(/<span class="rg-pt" style="left:§V§%"><\/span>/, "") : h.replace("§V§", d[0]);
  }

  var q = document.getElementById("q-votre"), s = document.getElementById("s-votre"), r = document.getElementById("r-votre"), choix = [], actif = -1, demande = 0;
  function montrer(x) {
    var n = ++demande, t = cible(x);
    if (!t) { r.innerHTML = '<div><p class="vt-pos">Cet indicateur n’est pas publié pour ' + e(x.nm) + ".</p></div>"; return; }
    Promise.all([terr(t.lv, t.c), lire(racine + "indicateur/reglettes/" + slug + ".json").catch(function () { return null; })]).then(function (y) {
      if (n !== demande) return;
      var T = y[0], v = T.ind[id], via = "";
      // le nom de la commune en tête, sans préposition : « de Ajaccio », « de Le Havre » ou « d’Hazebrouck » seraient faux
      if (x.t === "com") via = x.nm + (x.arr ? " : valeur de " : ", commune : valeur de ") + SON[t.lv] + ".";
      else if (x.t !== t.lv) via = x.nm + " : valeur de " + SON[t.lv] + ", cet indicateur n’est pas publié par " + NOM[x.t] + ".";
      var fiche = '<p class="vt-lien"><a href="' + racine + "territoire/" + t.lv + "/" + t.c + '.html">Fiche du territoire : ' + e(T.nom) + "</a></p>";
      if (!v) { r.innerHTML = '<div class="vt-a"><p class="vt-l1"><span class="vt-nom">' + e(T.nom) + '</span></p>' + (via ? '<p class="vt-pos">' + e(via) + "</p>" : "") +
        '<p class="vt-pos">Pas de valeur publiée pour ce territoire.</p></div><div class="vt-b">' + fiche + "</div>"; return; }
      var L = lecture(v, t.lv);
      r.innerHTML = '<div class="vt-a"><p class="vt-l1"><span class="vt-nom">' + e(T.nom) + '</span><span class="vt-v">' + e(L.val) + "</span>" +
        (L.plus ? '<span class="vt-u">' + e(L.plus) + "</span>" : "") + "</p>" + (via ? '<p class="vt-pos">' + e(via) + "</p>" : "") +
        // une valeur non publiée n'a pas de réglette (un territoire sans inscrit garde la sienne, sans point)
        '<div class="fiche">' + (v[1] || v[0] === "aucun" ? reglette(y[1], t.lv, t.c, L) : "") + "</div></div>" +
        '<div class="vt-b">' + posRep(L) + limite(L.lim) + fiche + "</div>";
      if (window.etiquettesReglettes) requestAnimationFrame(window.etiquettesReglettes);
    }).catch(function () { if (n === demande) r.innerHTML = '<div><p class="vt-pos">La valeur n’a pas pu être chargée. Recharger la page.</p></div>'; });
  }
  function suggerer() {
    var t = sa(q.value); actif = -1;
    if (t.length < 2) { fermer(); s.innerHTML = ""; return; }
    charger().then(function (I) {
      if (sa(q.value) !== t) return;
      var cp = /^\d{2,5}$/.test(t), mots = t.split(" "), RANG = { dep: 0, reg: 1, epci: 2, com: 3 };
      choix = I.filter(function (x) { return cp ? (x.t === "com" && x.cp && x.cp.split(" ").some(function (c) { return c.indexOf(t) === 0; })) || (x.t === "dep" && x.c === t) : mots.every(function (m) { return x.k.indexOf(m) >= 0; }); })
        .sort(function (a, b) { var da = a.k.indexOf(t) === 0 ? 0 : 1, db = b.k.indexOf(t) === 0 ? 0 : 1; return (da - db) || (RANG[a.t] - RANG[b.t]) || ((b.pop || 0) - (a.pop || 0)); }).slice(0, 6);
      s.innerHTML = choix.length ? choix.map(function (x, i) {
        // un seul code postal : celui qui répond, sinon le premier (Lyon en a neuf)
        var c = x.cp ? (cp ? x.cp.split(" ").filter(function (k) { return k.indexOf(t) === 0; })[0] : x.cp.split(" ")[0]) : "";
        return '<li><button type="button" role="option" id="sv-' + i + '" aria-selected="false" data-i="' + i + '">' + e(x.nm) + "<span>" + (x.arr ? "arrondissement" : NOM[x.t]) + (c ? ", " + e(c) : "") + "</span></button></li>"; }).join("")
        : '<li><p class="aide" style="margin:8px 0">Aucun territoire de ce nom.</p></li>';
      s.hidden = false; q.setAttribute("aria-expanded", "true");
    });
  }
  function fermer() { s.hidden = true; actif = -1; q.setAttribute("aria-expanded", "false"); q.removeAttribute("aria-activedescendant"); }
  function prendre(i) { var x = choix[i]; if (!x) return; q.value = x.nm; fermer(); montrer(x); }
  function marquer() { s.querySelectorAll("button").forEach(function (b, i) { b.setAttribute("aria-selected", i === actif ? "true" : "false"); });
    if (actif >= 0) q.setAttribute("aria-activedescendant", "sv-" + actif); else q.removeAttribute("aria-activedescendant"); }
  if (q) {
    q.addEventListener("input", suggerer);
    q.addEventListener("keydown", function (ev) {
      if (ev.key === "ArrowDown" && choix.length) { actif = Math.min(choix.length - 1, actif + 1); marquer(); ev.preventDefault(); }
      else if (ev.key === "ArrowUp" && choix.length) { actif = Math.max(0, actif - 1); marquer(); ev.preventDefault(); }
      else if (ev.key === "Enter" && !s.hidden && choix.length) { prendre(actif >= 0 ? actif : 0); ev.preventDefault(); }
      else if (ev.key === "Escape") fermer();
    });
    s.addEventListener("click", function (ev) { var b = ev.target.closest("button[data-i]"); if (b) prendre(+b.dataset.i); });
    // le territoire épinglé du lecteur, s'il en a un
    try { var ep = JSON.parse(localStorage.getItem("territoires-epingles") || "[]")[0];
      if (ep && /^(epci|dep|reg):\w+$/.test(ep.t)) { var p = ep.t.split(":"); q.value = ep.nm || ""; charger().then(function () { montrer({ t: p[0], c: p[1], nm: ep.nm || p[1] }); }); } } catch (x) {}
  }

  // la carte : un clic cerne le département et affiche sa valeur à côté ; la carte ne bouge pas
  var svg = document.querySelector(".carte-cote svg"), b = document.getElementById("clic");
  function reperer(t) {
    var path = svg.querySelector('path[data-t="' + t + '"]'); if (!path || !b) return;
    var c = t.split(":"); svg.querySelectorAll("path.repere").forEach(function (x) { x.classList.remove("repere"); });
    path.classList.add("repere"); var g = svg.querySelector("g.leg-svg"); if (g) svg.insertBefore(path, g);
    terr(c[0], c[1]).then(function (T) {
      var v = T.ind[id], tete = '<p class="ck-nom">' + e(T.nom) + "</p>", lien = '<a class="ck-bouton" href="' + racine + "territoire/" + c[0] + "/" + c[1] + '.html">Ouvrir la fiche</a>';
      if (!v) { b.innerHTML = tete + '<p>Pas de valeur publiée pour ce territoire.</p>' + lien; return; }
      var L = lecture(v, c[0]);
      b.innerHTML = tete + '<p class="ck-v">' + e(L.val) + (L.plus ? "<span>" + e(L.plus) + "</span>" : "") + "</p>" + posRep(L) + limite(L.lim) + lien;
    }).catch(function () { b.innerHTML = "<p>La valeur n’a pas pu être chargée.</p>"; });
  }
  if (svg) svg.addEventListener("click", function (ev) { var p = ev.target.closest("path[data-t]"); if (p) reperer(p.dataset.t); });
})();
