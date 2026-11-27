// Fiche de territoire, étape 2 des portes d'entrée (maquettes validées le 14 novembre 2026,
// prototypes/entrees/v2_fiche/ et v2_domaines/) :
// 1. « Tous les indicateurs de ce territoire », sous les tuiles de chiffres clés : un champ qui cherche dans la fiche et
//    les domaines en raccourcis vers le tableau complet ;
// 2. le tableau complet, à la fin de « Confiance et citation » : chaque indicateur du catalogue que le site publie pour
//    ce territoire (et, sur la fiche d'un département, ceux publiés seulement par région, avec la valeur de sa région),
//    rangé par domaine puis par sous-thème, avec un filtre par sous-thème et deux fichiers CSV, un par licence ;
// 3. les infobulles « ensemble » et « médiane » des réglettes, au survol, au toucher et au clavier.
// Les valeurs, repères, positions et limites sont lus dans les fichiers publiés du territoire (territoire/<niveau>/<code>.json,
// écrits par pipeline/reponses.py avec la règle d'affichage unique) et dans le catalogue (presentation/catalogue.json) :
// rien n'est recalculé ici.
(function () {
  var P = document.getElementById("porte"); if (!P) return;
  var lv = P.dataset.niv, code = P.dataset.code, rc = P.dataset.reg || "", racine = P.dataset.racine || "../../";
  var NIV = { dep: ["département", "départements", "du département", "le département médian"],
              reg: ["région", "régions", "de la région", "la région médiane"],
              epci: ["intercommunalité", "intercommunalités", "de l’intercommunalité", "l’intercommunalité médiane"] };
  var REPERE = { dep: "Ensemble des départements", reg: "Ensemble des régions", epci: "Ensemble des intercommunalités" };
  function sa(s) { return String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
  function e(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function cle(i) { return i.indexOf("prof:") === 0 ? i.split(":").slice(0, 2).join(":") : i; }
  function idTt(i) { return "tt-" + i.replace(/[:_]/g, "-"); }
  // le nom seul est souligné ; la flèche est du texte ordinaire, tenue au dernier mot par un caractère de liaison et
  // une espace insécable : elle ne passe jamais seule à la ligne, et le nom peut se couper à son trait d'union
  function fleche(nom, f, aide) { return '<span class="u">' + e(nom) + '</span>\u2060<span class="fl" aria-hidden="true">\u00a0' + f + '</span><span class="lecteur">, ' + aide + "</span>"; }
  function nomLien(nom, page) { return '<a class="vers-ind avec-fl" href="' + racine + e(page) + '">' + fleche(nom, "→", "page de l’indicateur") + "</a>"; }
  function publie(l) { return !!l.val || l.eff === "aucun"; }
  function zero(v) { return /^0([,.]0+)?$/.test((v || "").trim()); }
  function lire(u) { return fetch(u).then(function (r) { if (!r.ok) throw new Error(u); return r.json(); }); }

  // le territoire qui le contient, pour les indicateurs publiés seulement à son niveau : la région d'un département
  // (indicateurs publiés seulement par région), le département d'une intercommunalité (lignes « donnée du département »
  // de la fiche)
  var HAUT = { dep: { niv: "reg", mot: "de sa région", val: "valeur de la région", dit: "région",
                      si: function (n) { return n.length === 1 && n[0] === "région"; } },
               epci: { niv: "dep", mot: "de son département", val: "valeur du département", dit: "département",
                       si: function (n) { return n.indexOf("intercommunalité") < 0 && n.indexOf("département") >= 0; } } }[lv] || null;
  var lignes = null, T = null, R = null;
  Promise.all([lire(racine + "presentation/catalogue.json"), lire(code + ".json")])
    .then(function (x) { T = x[1]; var c = HAUT && (HAUT.niv === "reg" ? rc : T.dep);
      return (c ? lire("../" + HAUT.niv + "/" + c + ".json").catch(function () { return null; }) : Promise.resolve(null)).then(function (h) { R = h; return x[0]; }); })
    .then(function (cat) { preparer(cat); montrer(); })
    .catch(function () { P.querySelector(".p-attente").textContent = "Le tableau complet n’a pas pu être chargé. Recharger la page."; });

  // rang de chaque indicateur sur la fiche (ordre des lignes), pour garder cet ordre dans un sous-thème
  function rangs() { var r = {}, a = {}, k = 0;
    document.querySelectorAll(".fiche tr[data-ind][id]").forEach(function (tr) { if (tr.closest("#tout-terr")) return;
      var c = cle(tr.dataset.ind); if (!(c in r)) { r[c] = k++; a[c] = tr; } });
    return { r: r, a: a }; }

  function preparer(cat) {
    var ordreDom = [], ordreSous = {}, rf = rangs();
    lignes = [];
    cat.forEach(function (x, ci) {
      if (ordreDom.indexOf(x.domaine) < 0) ordreDom.push(x.domaine);
      var os = ordreSous[x.domaine] = ordreSous[x.domaine] || []; if (os.indexOf(x.sous) < 0) os.push(x.sous);
      var v = T.ind[x.id], ech = lv;
      if (!v && R && HAUT.si(x.niveaux)) { v = R.ind[x.id]; ech = HAUT.niv; }
      if (!v) return;
      var pos = v[2] || "", rlib = v[4] || "", rval = v[5] || "";
      if (!rlib && !rval) { var m = /l.ensemble \(([\d\s \u00a0,]+)\)/.exec(pos);
        if (m) { rlib = REPERE[ech]; rval = m[1]; pos = pos.replace(" (" + m[1] + ")", ""); } }
      lignes.push({ x: x, ci: ci, ech: ech, eff: v[0] || "", val: v[1] || "", pos: pos, lim: v[3] || "", rlib: rlib, rval: rval,
                    note: v[6] || "", kind: v[7] || "", couleur: v[8] || "", rang: x.id in rf.r ? rf.r[x.id] : 1e6 + ci, tr: rf.a[x.id] || null });
      // la fourchette (intervalle de confiance) que la fiche montre sous la valeur d'une enquête, reprise telle quelle
      var L = lignes[lignes.length - 1], ic = L.tr && L.tr.querySelector("td.v .note.ic");
      L.ic = ic ? ic.textContent.replace(/\s+/g, " ").trim() : "";
    });
    lignes.sort(function (a, b) {
      return (ordreDom.indexOf(a.x.domaine) - ordreDom.indexOf(b.x.domaine)) ||
             (ordreSous[a.x.domaine].indexOf(a.x.sous) - ordreSous[b.x.domaine].indexOf(b.x.sous)) || (a.rang - b.rang); });
  }

  function valeur(l) {
    // sans valeur et sans aucun professionnel, la note (« aucun inscrit ») tient lieu de valeur, jamais « aucun aucun inscrit »
    var seulNote = !l.val && l.eff === "aucun" && l.note;
    var val = l.val || (l.eff === "aucun" ? (l.note || "aucun") : ""), t = "<b>" + (val ? e(val) : "non publié") + "</b>", s = [];
    if (l.ic) s.push(e(l.ic));
    if (l.ech !== lv) s.push(HAUT.val + ' <span class="sc">' + e(R.nom) + "</span>");
    if (l.kind === "prof" && l.eff && l.eff !== "aucun") s.push("effectif " + e(l.eff));
    if (l.kind === "lieux" && l.eff && l.eff !== "aucun") s.push(e(l.eff) + (l.eff === "0" || l.eff === "1" ? " lieu" : " lieux"));
    if (l.note) { if (!seulNote) s.push(e(l.note)); }
    else if (zero(l.val)) s.push(l.kind === "prof" ? "aucun inscrit" : l.kind === "lieux" ? "aucune structure recensée" : "valeur nulle");   // jamais un 0 seul
    return t + s.map(function (x) { return '<span class="tt-n">' + x + "</span>"; }).join("");
  }
  function position(l) {
    var m = /^(\d[\d \u00a0\s]* ?% (?:au-dessus de|sous) l.ensemble)(.*)$/.exec(l.pos);
    if (!m) return e(l.pos);
    // la couleur de la fiche, seulement pour une valeur du territoire lui-même (pas pour celle de sa région)
    return '<span class="ec ' + (l.ech === lv && (l.couleur === "haut" || l.couleur === "bas") ? l.couleur : "neutre") + '">' + e(m[1]) + "</span>" + e(m[2]);
  }
  function domId(d) { return "tt-" + sa(d).split(/[\s,]+/)[0]; }

  function tableau() {
    var nb = {}, nbs = {}, h = [], dom = null, sous = null;
    lignes.forEach(function (l) { var d = l.x.domaine; nb[d] = (nb[d] || 0) + 1; nbs[d] = nbs[d] || {}; nbs[d][l.x.sous] = (nbs[d][l.x.sous] || 0) + 1; });
    var tete = '<div class="tt-cadre"><table class="tt"><colgroup><col class="c1"><col class="c2"><col class="c3"><col class="c4"></colgroup><thead><tr>' +
      '<th scope="col">Indicateur</th><th scope="col" class="v">Valeur</th><th scope="col" class="rep">Repère, ' + e(REPERE[lv].toLowerCase()) +
      ' sauf mention</th><th scope="col">Position</th></tr></thead><tbody>';
    lignes.forEach(function (l) {
      var d = l.x.domaine;
      if (d !== dom) {
        if (dom !== null) h.push("</tbody></table></div></details>");
        dom = d; sous = null;
        var ss = Object.keys(nbs[d]), f = "";
        if (ss.length >= 3) f = '<p class="tt-filtre" role="group" aria-label="Sous-thèmes de ' + e(d) + '"><button type="button" data-sous="" aria-pressed="true">Tous <span>' + nb[d] + "</span></button>" +
          ss.map(function (s) { return '<button type="button" data-sous="' + e(s) + '" aria-pressed="false">' + e(s) + " <span>" + nbs[d][s] + "</span></button>"; }).join("") + "</p>";
        h.push('<details class="tt-domd" id="' + domId(d) + '" data-titre="Tous les indicateurs, ' + e(d) + '"><summary><h3 class="tt-dom">' + e(d) + "<span>" + nb[d] + " indicateur" + (nb[d] > 1 ? "s" : "") + "</span></h3></summary>" + f +
               '<div class="encadre-outils seul-ecran tt-outils"><button type="button" class="citer-encadre" aria-expanded="false">Citer et exporter</button></div>' + tete);
      }
      if (l.x.sous !== sous) { sous = l.x.sous; h.push('<tr class="tt-sous" data-sous="' + e(sous) + '"><th colspan="4" scope="colgroup">' + e(sous) + "</th></tr>"); }
      var sm = l.x.themes.indexOf("Santé mentale") >= 0 && !l.x.sensible && l.x.sous !== "Santé mentale" ? ' <span class="tt-eti">santé mentale</span>' : "";
      var lim = l.lim ? '<span class="tt-lim"><b aria-hidden="true">!</b>' + e(l.lim) + "</span>" : "";
      var rlib = l.rlib || REPERE[l.ech], autre = !!l.rlib && l.rlib !== REPERE[lv];
      var rep = l.rval ? '<span class="tt-rd">' + e(rlib) + " : </span>" + e(l.rval) + (autre ? '<span class="tt-rl">' + e(l.rlib.toLowerCase()) + "</span>" : "") : "";
      h.push("<tr" + (l.ech !== lv ? ' class="tt-reg"' : "") + ' id="' + idTt(l.x.id) + '" data-sous="' + e(l.x.sous) + '"><th scope="row">' + nomLien(l.x.nom, l.x.page) + sm + lim +
             '</th><td class="v">' + valeur(l) + '</td><td class="rep">' + rep + '</td><td class="pos">' + position(l) + "</td></tr>");
    });
    if (dom !== null) h.push("</tbody></table></div></details>");
    return { html: h.join(""), nb: nb };
  }

  // où se trouve la ligne de la fiche : « 01 Santé mentale », et si elle est dans un repli
  function ou(tr, l) {
    var s = tr.closest("section.bande"), t = s && s.querySelector("h2.titre-bande"), n = t && t.querySelector(".num-partie");
    var nom = t ? (n ? n.textContent + " " + t.textContent.slice(n.textContent.length) : t.textContent).trim() : "";
    return nom + (l.ech !== lv ? ", " + HAUT.val : "") + (tr.closest("details.autres") ? ", parmi les autres indicateurs de la partie" : "");
  }

  var index = [];
  function montrer() {
    var t = tableau(), ODBL = /ODbL/;
    var corps = document.querySelector("#tout-terr .tt-corps"); if (corps) corps.innerHTML = t.html;
    // une mesure sans valeur publiée reste dans le tableau (« non publié ») et se compte à part : « 107 du
    // département, 132 non publiés » pour Mayotte
    var nTerr = 0, nReg = 0, nNp = 0, parDom = {};
    lignes.forEach(function (l) { var k = parDom[l.x.domaine] = parDom[l.x.domaine] || [0, 0, 0]; k[0]++;
      if (!publie(l)) nNp++; else if (l.ech !== lv) { nReg++; k[1]++; } else nTerr++; });
    var compte = nTerr + " " + NIV[lv][2] + (nReg ? " et " + nReg + " " + HAUT.mot : "") + (nNp ? ", " + nNp + " non publié" + (nNp > 1 ? "s" : "") : "");
    document.querySelectorAll("[data-compte-tout]").forEach(function (x) { x.textContent = compte; });
    var ul = P.querySelector(".p-doms");
    if (ul) ul.insertAdjacentHTML("beforeend", Object.keys(t.nb).map(function (d) { var k = parDom[d];
      return '<li><a class="vers-ind avec-fl" href="#' + domId(d) + '" data-aller="' + domId(d) + '">' + fleche(d, "↓", "plus bas dans le tableau complet") + '</a><span>' +
        k[0] + (k[1] ? ", dont " + k[1] + " " + (HAUT.niv === "reg" ? "de la région" : "du département") : "") + "</span></li>"; }).join(""));
    var lo = lignes.filter(function (l) { return !ODBL.test(l.x.licence); }), od = lignes.filter(function (l) { return ODBL.test(l.x.licence); });
    var b = document.querySelector("#tout-terr .tt-csv");
    if (b) b.innerHTML = '<button type="button" data-csv="lo">Licence Ouverte, CSV</button><span>' + lo.length + " indicateur" + (lo.length > 1 ? "s" : "") + "</span>" +
      (od.length ? '<button type="button" data-csv="odbl">ODbL, CSV</button><span>' + od.length + " indicateur" + (od.length > 1 ? "s" : "") + "</span>" : "");
    var pc = P.querySelector(".p-csv"); if (pc) pc.textContent = od.length ? "Le tableau complet se télécharge en deux fichiers CSV, un par licence." : "Le tableau complet se télécharge en un fichier CSV.";
    FICHIERS = { lo: lo, odbl: od };
    index = lignes.map(function (l) {
      var a, o, tr = l.ech === "reg" && lv === "dep" ? document.querySelector('.fiche tr[data-ind="' + l.x.id + '"][id^="l-reg-"]') : l.tr;
      if (tr) { a = tr.id; o = ou(tr, l); } else { a = idTt(l.x.id); o = "Tableau complet, " + l.x.domaine + ", " + l.x.sous.toLowerCase(); }
      var v = l.val || (l.eff === "aucun" ? (l.note || "aucun") : "non publié");
      return { n: l.x.nom, k: sa(l.x.nom + " " + l.x.sous), a: a, o: o, v: v, p: l.x.page };
    });
    // une ligne de la fiche que le catalogue ne tient pas (« CMP, tous publics ») se trouve aussi : la recherche porte sur
    // toute la fiche (relecture indépendante du 15 novembre 2026)
    var dejaVu = {}; lignes.forEach(function (l) { dejaVu[cle(l.x.id)] = 1; });
    document.querySelectorAll(".fiche tr[data-ind][id]").forEach(function (tr) {
      if (tr.closest("#tout-terr")) return; var c = cle(tr.dataset.ind); if (dejaVu[c]) return; dejaVu[c] = 1;
      var nom = tr.dataset.titre || ((tr.querySelector("th .u") || tr.querySelector("th") || {}).textContent || "").trim();
      var b = tr.querySelector("td.v b") || tr.querySelector("td.v .statut"), g = tr.closest(".groupe"), gt = g && g.querySelector("h3, h4");
      // le titre de son tableau distingue deux lignes de même nom (« CMP, tous publics » : structures, distance)
      var o = ou(tr, { ech: lv }) + (gt ? ", " + gt.textContent.trim().charAt(0).toLowerCase() + gt.textContent.trim().slice(1) : "");
      if (nom) index.push({ n: nom, k: sa(nom), a: tr.id, o: o, v: b ? b.textContent.trim() : "", p: null });
    });
    // le repli des domaines, au téléphone, dit combien il en tient (maquette validée)
    var sm = P.querySelector(".p-doms-d > summary"), nd = Object.keys(t.nb).length;
    if (sm) sm.textContent = "Le tableau complet, par domaine, " + nd + " domaine" + (nd > 1 ? "s" : "");
    // « Citer et exporter » de chaque domaine du tableau, comme tout encadré de la fiche (figures.js)
    if (window.citerEncadres) window.citerEncadres();
    P.classList.add("pret"); var at = P.querySelector(".p-attente"); if (at) at.remove();
    if (q.value) chercher();
    if (/^#tt-/.test(location.hash)) aller(location.hash.slice(1));
  }

  // fichiers CSV, séparateur « ; », encodage UTF-8 avec BOM, un par licence (frontière validée le 30 octobre 2026)
  var FICHIERS = null;
  function champ(x) { x = String(x == null ? "" : x); return /[;"\n\r]/.test(x) ? '"' + x.replace(/"/g, '""') + '"' : x; }
  function csv(ls) {
    var t = [["domaine", "sous_theme", "indicateur", "id", "territoire_de_la_valeur", "valeur", "intervalle_de_confiance", "effectif", "repere", "repere_valeur", "position", "note", "limite", "source", "date", "licence", "page"]];
    ls.forEach(function (l) { t.push([l.x.domaine, l.x.sous, l.x.nom, l.x.id, l.ech !== lv ? R.nom + " (" + HAUT.dit + ")" : T.nom, l.val, l.ic, l.eff, l.rlib, l.rval, l.pos, l.note, l.lim,
      l.x.source_longue, l.x.date, l.x.licence, "https://ubicura.fr/" + l.x.page]); });
    return "﻿" + t.map(function (r) { return r.map(champ).join(";"); }).join("\n") + "\n";
  }
  function telecharger(k) {
    var u = URL.createObjectURL(new Blob([csv(FICHIERS[k])], { type: "text/csv;charset=utf-8" })), a = document.createElement("a");
    a.href = u; a.download = "ubicura_" + lv + "_" + code + "_toutes_valeurs" + (k === "odbl" ? "_odbl" : "") + ".csv";
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(function () { URL.revokeObjectURL(u); }, 1000);
  }

  function filtrer(d, s) {
    d.querySelectorAll(".tt-filtre button").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.sous === s ? "true" : "false"); });
    d.querySelectorAll("tr[data-sous]").forEach(function (t) { t.hidden = !!s && t.dataset.sous !== s; });
  }
  function ouvrir(el) { for (var p = el.parentElement; p; p = p.parentElement) if (p.tagName === "DETAILS") p.open = true; }
  function aller(id) {
    var el = document.getElementById(id); if (!el) return;
    if (id === "tout-terr") { el.open = true; el.scrollIntoView({ block: "start" }); return; }
    if (id.indexOf("tt-") === 0) { var dd = el.tagName === "DETAILS" ? el : el.closest("details.tt-domd"); if (dd) { dd.open = true; if (el.hidden) filtrer(dd, ""); } }
    ouvrir(el); el.scrollIntoView({ block: "center" });
    if (el.tagName === "TR") { el.classList.add("vu"); setTimeout(function () { el.classList.remove("vu"); }, 2500); }
  }

  var q = document.getElementById("q-fiche"), r = document.getElementById("r-fiche"), et = document.getElementById("e-fiche");
  function chercher() {
    var t = sa(q.value.trim()); if (t.length < 2 || !index.length) { r.innerHTML = ""; et.textContent = ""; return; }
    var mots = t.split(/\s+/), res = index.filter(function (x) { return mots.every(function (m) { return x.k.indexOf(m) >= 0; }); });
    // dans l'ordre de la fiche, de haut en bas (maquette validée), puis le tableau complet
    res.forEach(function (x) { x.el = document.getElementById(x.a); });
    res.sort(function (a, b) { return !a.el || !b.el ? 0 : a.el.compareDocumentPosition(b.el) & 4 ? -1 : 1; });
    // le nom mène à sa ligne, plus bas : il porte « ↓ », comme tout lien qui reste dans la fiche
    var h = res.slice(0, 6).map(function (x) {
      return '<li><a class="vers-ind avec-fl" href="#' + x.a + '" data-aller="' + x.a + '">' + fleche(x.n, "↓", "plus bas dans la fiche") + '</a><span class="p-v">' + e(x.v) +
        '</span><span class="p-ou">' + e(x.o) + "</span></li>"; }).join("");
    if (res.length > 6) h += '<li class="p-plus">Et ' + (res.length - 6) + " autres, dans le tableau complet.</li>";
    if (!res.length) h = '<li class="p-plus">Aucun indicateur de ce nom dans la fiche. La recherche du site, en haut de page, cherche aussi les lieux et les pages.</li>';
    r.innerHTML = h;
    et.textContent = res.length ? res.length + (res.length > 1 ? " indicateurs trouvés" : " indicateur trouvé") : "Aucun indicateur trouvé";
  }
  if (q) q.addEventListener("input", chercher);
  var pd = P.querySelector(".p-doms-d"); if (pd && matchMedia("(max-width:760px)").matches) pd.open = false;
  document.addEventListener("click", function (ev) {
    var a = ev.target.closest("[data-aller]"); if (a) { ev.preventDefault(); aller(a.dataset.aller); history.replaceState(null, "", "#" + a.dataset.aller); return; }
    var t = ev.target.closest('a[href="#tout-terr"]'); if (t) { ev.preventDefault(); aller("tout-terr"); return; }
    var b = ev.target.closest(".tt-filtre button"); if (b) { filtrer(b.closest("details.tt-domd"), b.dataset.sous); return; }
    var c = ev.target.closest("[data-csv]"); if (c && FICHIERS) telecharger(c.dataset.csv);
  });
})();

// Réglettes : « ensemble » et « médiane » expliqués au survol, avec les mots de la légende des réglettes (maquette
// validée le 22 novembre 2026), au toucher et au clavier, dans le fil de la page, sans
// rien recouvrir (maquette validée le 14 novembre 2026, prototypes/entrees/v2_domaines/, captures r1 à r7).
(function () {
  var MOTS = { dep: { reunis2: "réunis", unseul: "s’ils n’en faisaient qu’un", un: "département", peuples: "peuplés", le: "le département", pl: "départements", ce: "ce département", tous: "tous les", reunis: "réunis, calculés comme" },
               reg: { reunis2: "réunies", unseul: "si elles n’en faisaient qu’une", un: "région", peuples: "peuplées", le: "la région", pl: "régions", ce: "cette région", tous: "toutes les", reunis: "réunies, calculées comme" },
               epci: { reunis2: "réunies", unseul: "si elles n’en faisaient qu’une", un: "intercommunalité", peuples: "peuplées", le: "l’intercommunalité", pl: "intercommunalités", ce: "cette intercommunalité", tous: "toutes les", reunis: "réunies, calculées comme" } };
  var porte = document.getElementById("porte"), defaut = (porte && porte.dataset.niv) || "dep";
  function mots(l) { var tr = l.closest("tr[data-niv]"), n = tr ? tr.getAttribute("data-niv").split(":")[0] : defaut; return MOTS[n] || MOTS[defaut] || MOTS.dep; }
  var b = document.createElement("div"); b.id = "rg-bulle"; b.setAttribute("role", "tooltip"); b.hidden = true; document.body.appendChild(b);
  var mode = null, ouvert = null, tempo = null;
  // l'unité de la ligne : sous la valeur, ou dans le nom pour « En bref » ; jamais la fourchette de la valeur (« entre
  // 15,2 et 18,3 », qui n'est pas celle de la médiane) ni une note qui n'est pas une unité (relecture du 15 novembre 2026)
  function unite(l) { var tr = l.closest("tr"); if (!tr) return "";
    var ns = tr.querySelectorAll(tr.closest("table.matrice") ? "th .note" : "td.v .note:not(.ic)");
    for (var i = 0; i < ns.length; i++) { var t = ns[i].textContent.replace(/\s+/g, " ").trim().replace(/, médiane des habitants$/, "");
      if (/^(pour |km$|%$|€$|hab\.)/.test(t)) return " " + t; }
    return ""; }
  function ligne(l) {
    var t = l.textContent.trim(), m = t.match(/^(ensemble|médiane)\s+(.*)$/); if (!m) return null;
    var v = m[2].replace(/\s*\(aucun : .*\)$/, ""), u = /^[\d\s\u00a0 ,]+$/.test(v) ? unite(l) : "", M = mots(l);
    if (m[1] === "ensemble") return "<b>Ensemble des " + M.pl + ", " + v + u + "</b> : " + M.tous + " " + M.pl + " " + M.reunis2 + " comme " + M.unseul + ", la mesure calculée comme pour " + M.ce + ". " + (/km²/.test(u) ? "Pour la densité de population, chaque km² y compte autant." : "Chaque habitant y compte autant, donc les " + M.pl + " " + M.peuples + " pèsent plus.");
    return "<b>Médiane, " + v + u + "</b> : la moitié des " + M.pl + " est au-dessus, l’autre moitié en dessous. Chaque " + M.un + " compte autant, quelle que soit sa population.";
  }
  // « ensemble » et « médiane » reçoivent le pointillé du glossaire : il annonce une explication
  document.querySelectorAll(".fiche .rg-lab").forEach(function (l) { var t = l.firstChild; if (!t || t.nodeType !== 3) return;
    var m = t.nodeValue.match(/^(ensemble|médiane)(\s[\s\S]*)$/); if (!m) return; var s = document.createElement("span"); s.className = "rg-mot"; s.textContent = m[1];
    l.replaceChild(document.createTextNode(m[2]), t); l.insertBefore(s, l.firstChild); });
  document.querySelectorAll(".fiche .rg[tabindex]").forEach(function (rg) { if (rg.querySelector(".rg-lab .rg-mot")) rg.setAttribute("aria-describedby", "rg-bulle"); });
  function retirerLigne() { var x = document.querySelector("tr.rg-expl"); if (x) { document.body.appendChild(b); x.remove(); } }
  // toujours dans le fil de la page, sous la ligne ou sous la réglette : la bulle ne recouvre jamais rien
  function dansFlux(rg) {
    retirerLigne(); b.className = "dans-flux"; var tr = rg.closest("tr");
    if (tr && innerWidth >= 640 && !rg.closest("table.matrice")) { var n = document.createElement("tr"); n.className = "rg-expl"; var td = document.createElement("td");
      td.colSpan = tr.cells.length; td.style.paddingLeft = (rg.getBoundingClientRect().left - tr.getBoundingClientRect().left) + "px";
      n.appendChild(td); td.appendChild(b); tr.insertAdjacentElement("afterend", n); }
    // sous la ligne de la réglette et de sa valeur (« En bref ») : placée entre les deux, la bulle prenait la place de la
    // réglette, réduite à 32 px (22 novembre 2026)
    else (rg.closest(".m-ligne") || rg).insertAdjacentElement("afterend", b);
  }
  // la bulle ajoutée ou retirée dans le fil d'un tableau peut changer la largeur des colonnes : les étiquettes des
  // réglettes sont replacées aussitôt (figures.js), sinon elles se chevauchent (contrôle de mise en page du 15 novembre 2026)
  function replacer() { if (window.etiquettesReglettes) requestAnimationFrame(window.etiquettesReglettes); }
  function ouvrir(l, m) { var t = ligne(l); if (!t) return; clearTimeout(tempo); b.innerHTML = t; b.hidden = false; mode = m; ouvert = l; dansFlux(l.closest(".rg")); replacer(); }
  function cacher() { clearTimeout(tempo); b.hidden = true; mode = null; ouvert = null; retirerLigne(); replacer(); }
  document.addEventListener("pointerover", function (ev) { if (ev.pointerType !== "mouse" || mode === "fixe" || mode === "clavier") return;
    var l = ev.target.closest && ev.target.closest(".fiche .rg-lab"); if (l) { if (ouvert !== l) ouvrir(l, "survol"); else clearTimeout(tempo); }
    else if (b.contains(ev.target)) clearTimeout(tempo); });
  document.addEventListener("pointerout", function (ev) { if (ev.pointerType !== "mouse" || mode !== "survol") return;
    if ((ev.target.closest && ev.target.closest(".fiche .rg-lab")) || b.contains(ev.target)) { clearTimeout(tempo); tempo = setTimeout(function () { if (mode === "survol") cacher(); }, 300); } });
  // un toucher (ou un clic) ouvre, un second toucher sur le même mot ou un toucher ailleurs ferme
  document.addEventListener("click", function (ev) { var l = ev.target.closest && ev.target.closest(".fiche .rg-lab");
    if (l) { if (mode === "fixe" && ouvert === l) cacher(); else ouvrir(l, "fixe"); return; }
    if (b.contains(ev.target)) return; if (mode === "fixe") cacher(); });
  // au clavier : Tab mène à la réglette, ses deux lignes s'ouvrent dans le fil ; Échap ou Tab suivant ferme
  document.addEventListener("focusin", function (ev) { var rg = ev.target.matches && ev.target.matches(".fiche .rg[tabindex]:focus-visible") ? ev.target : null; if (!rg) return;
    var x = [].slice.call(rg.querySelectorAll(".rg-lab")).map(ligne).filter(Boolean); if (!x.length) return;
    clearTimeout(tempo); b.innerHTML = x.map(function (s) { return '<span class="l">' + s + "</span>"; }).join(""); b.hidden = false; mode = "clavier"; ouvert = rg; dansFlux(rg); replacer(); });
  document.addEventListener("focusout", function (ev) { if (mode === "clavier" && ev.target === ouvert) cacher(); });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape" && mode) cacher(); });
  var larg = innerWidth; addEventListener("resize", function () { if (innerWidth !== larg) { larg = innerWidth; cacher(); } });
})();
