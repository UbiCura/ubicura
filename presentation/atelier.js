// Atelier « Croiser » (présentation du 30 octobre 2026). Lit presentation/atelier_donnees.js (const A, préparé par
// pipeline/atelier.py), dessine le nuage et la carte en SVG,
// calcule la corrélation de rang, son intervalle, la corrélation partielle et la correction de Benjamini-Hochberg
// sur les croisements essayés pendant la visite.
(function () {
  "use strict";
  var fr = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 });
  var fr1 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
  var fr0 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
  // Domaines du modèle (pipeline/domaines.py), rangement, drapeau santé mentale et année déjà portés par les données.
  // La santé mentale est une entrée qui traverse les domaines, en tête du menu.
  var Domaines = { liste: A.domaines, par: {} }; A.domaines.forEach(function (d) { Domaines.par[d.id] = d; });
  var DOMS = Domaines.liste.map(function (d) { return [d.id, d.nom]; });
  var NOMDOM = {}; DOMS.forEach(function (d) { NOMDOM[d[0]] = d[1]; });
  var NIV_SING = { reg: "région", dep: "département", epci: "intercommunalité" };
  var NIV_UN = { reg: "D'une région", dep: "D'un département", epci: "D'une intercommunalité" };
  var NIV_PL = { reg: "régions", dep: "départements", epci: "intercommunalités" };
  var IND = {}; A.ind.forEach(function (i) { IND[i.id] = i; });
  var REGNOM = {}; A.units.reg.forEach(function (u) { REGNOM[u.c] = u.nm; });
  // région de chaque département, le fichier des unités donne son nom comme parent (p)
  var REGCODE = {}; A.units.reg.forEach(function (u) { REGCODE[u.nm] = u.c; });
  var DEPREG = {}; A.units.dep.forEach(function (u) { DEPREG[u.c] = REGCODE[u.p]; });

  var S = { x: "taux_pauvrete", y: "prof:psychiatre:all", z: "", zm: "t", lv: "dep", m: "all", r: "", traj: false, v: "b", sel: null };
  var HISTO = [];

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function norm(s) { return String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, ""); }
  function f(v, i) { if (v == null) return "sans donnée"; if (Math.abs(v) < 1e-9) v = 0; var a = Math.abs(v); return (a >= 1000 ? fr0 : a >= 10 ? fr1 : fr).format(v).replace("-", "−"); }
  function unite(i) { return i.u ? " " + i.u : ""; }

  // identifiant effectif d'un indicateur selon le mode d'exercice choisi
  function eff(id) {
    var i = IND[id]; if (!i || i.type !== "prof") return id;
    var j = "prof:" + i.prof + ":" + S.m; return IND[j] ? j : id;
  }
  function dispo(id, lv) { var i = IND[eff(id)]; return !!(i && i.niv && i.niv.indexOf(lv) >= 0 && A.val[lv][i.id]); }
  function valeurs(id, lv) {
    var i = IND[eff(id)];
    if (S.traj && i.type === "prof" && IND["evol:" + i.prof] && IND["evol:" + i.prof].d1[lv]) return IND["evol:" + i.prof].d1[lv];
    return A.val[lv][i.id];
  }
  function trajSerie(id, lv) { var i = IND[eff(id)]; var e = i && IND["evol:" + i.prof]; return e && e.d0[lv] ? e : null; }
  function region(u, lv) { if (lv === "reg") return u.c; if (lv === "dep") return DEPREG[u.c]; return DEPREG[u.p]; }

  // repère du niveau, le même que la fiche et le comparateur (pipeline/affichage.py, publié dans A.aff), nommé
  // « Ensemble des ... » ou « ... médiane » ; pour une série de la trajectoire, la médiane des territoires de la série
  function reference(id, lv, vals) {
    var i = IND[eff(id)], a = A.aff && A.aff.lv[lv] && A.aff.lv[lv][i.id];
    if (a && a.r != null && !(S.traj && trajSerie(id, lv))) return { v: a.r, t: (a.t === "mediane_territoires" ? A.aff.mediane : A.aff.ensemble)[lv], g: (A.aff.ind[i.id] || {}).g };
    var b = vals.filter(function (x) { return x != null; }).sort(function (p, q) { return p - q; });
    if (!b.length) return null;
    var m = b.length % 2 ? b[(b.length - 1) / 2] : (b[b.length / 2 - 1] + b[b.length / 2]) / 2;
    return { v: m, t: "médiane des " + NIV_PL[lv] };
  }
  // valeur d'un territoire telle que les fiches l'écrivent (presentation/chiffres.js), statut compris
  function fv(id, lv, k, v) {
    var i = IND[eff(id)];
    if (S.traj && trajSerie(id, lv)) return f(v, i);
    var c = Chiffres.cellule(A, i.id, lv, k, v);
    return c ? (c.txt || c.statut || "sans donnée") + (c.txt && c.statut ? ", " + c.statut : "") : f(v, i);
  }

  // statistiques
  function rangs(a) {
    var o = a.map(function (v, k) { return [v, k]; }).sort(function (p, q) { return p[0] - q[0]; }), r = new Array(a.length), k = 0;
    while (k < o.length) { var j = k; while (j + 1 < o.length && o[j + 1][0] === o[k][0]) j++; var m = (k + j) / 2 + 1; for (var t = k; t <= j; t++) r[o[t][1]] = m; k = j + 1; }
    return r;
  }
  function pearson(a, b) {
    var n = a.length, ma = 0, mb = 0; for (var k = 0; k < n; k++) { ma += a[k]; mb += b[k]; } ma /= n; mb /= n;
    var sab = 0, saa = 0, sbb = 0; for (k = 0; k < n; k++) { var da = a[k] - ma, db = b[k] - mb; sab += da * db; saa += da * da; sbb += db * db; }
    return saa && sbb ? sab / Math.sqrt(saa * sbb) : 0;
  }
  function betacf(a, b, x) {
    var qab = a + b, qap = a + 1, qam = a - 1, c = 1, d = 1 - qab * x / qap; if (Math.abs(d) < 1e-30) d = 1e-30; d = 1 / d; var h = d;
    for (var m = 1; m <= 200; m++) {
      var m2 = 2 * m, aa = m * (b - m) * x / ((qam + m2) * (a + m2));
      d = 1 + aa * d; if (Math.abs(d) < 1e-30) d = 1e-30; c = 1 + aa / c; if (Math.abs(c) < 1e-30) c = 1e-30; d = 1 / d; h *= d * c;
      aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
      d = 1 + aa * d; if (Math.abs(d) < 1e-30) d = 1e-30; c = 1 + aa / c; if (Math.abs(c) < 1e-30) c = 1e-30; d = 1 / d;
      var del = d * c; h *= del; if (Math.abs(del - 1) < 3e-12) break;
    }
    return h;
  }
  function lgamma(z) {
    var g = [76.18009172947146, -86.50532032941677, 24.01409824083091, -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5];
    var x = z, y = z, t = x + 5.5; t -= (x + 0.5) * Math.log(t); var s = 1.000000000190015; for (var j = 0; j < 6; j++) s += g[j] / ++y;
    return -t + Math.log(2.5066282746310005 * s / x);
  }
  function ibeta(x, a, b) {
    if (x <= 0) return 0; if (x >= 1) return 1;
    var bt = Math.exp(lgamma(a + b) - lgamma(a) - lgamma(b) + a * Math.log(x) + b * Math.log(1 - x));
    return x < (a + 1) / (a + b + 2) ? bt * betacf(a, b, x) / a : 1 - bt * betacf(b, a, 1 - x) / b;
  }
  function pCorr(r, df) { if (Math.abs(r) >= 1) return 0; var t2 = r * r * df / (1 - r * r); return ibeta(df / (df + t2), df / 2, 0.5); }
  function ic(r, n, k) { // intervalle à 95 %, transformation de Fisher, erreur type de Fieller pour le rang
    var se = Math.sqrt(1.06 / (n - 3 - k)), z = Math.atanh(Math.max(-0.9999, Math.min(0.9999, r)));
    return [Math.tanh(z - 1.96 * se), Math.tanh(z + 1.96 * se)];
  }
  function force(r) { var a = Math.abs(r); return a < 0.1 ? "négligeable" : a < 0.3 ? "faible" : a < 0.5 ? "modéré" : "fort"; }
  function bh(ps) { // p ajustées de Benjamini-Hochberg, dans l'ordre d'origine
    var n = ps.length, o = ps.map(function (p, k) { return [p, k]; }).sort(function (a, b) { return a[0] - b[0]; }), out = new Array(n), m = 1;
    for (var j = n - 1; j >= 0; j--) { m = Math.min(m, o[j][0] * n / (j + 1)); out[o[j][1]] = m; }
    return out;
  }
  function r2(v) { var x = Math.round(v * 100) / 100; return fr.format(x === 0 ? 0 : x).replace("-", "−"); }
  function fp(p) { return p < 0.001 ? "moins de 0,001" : fr.format(Math.round(p * 1000) / 1000); }

  // jeu de points du croisement courant
  function points() {
    var lv = S.lv, U = A.units[lv], X = valeurs(S.x, lv), Y = valeurs(S.y, lv), Z = S.z && dispo(S.z, lv) ? valeurs(S.z, lv) : null;
    var tx = S.traj ? trajSerie(S.x, lv) : null, ty = S.traj ? trajSerie(S.y, lv) : null, pts = [];
    U.forEach(function (u, k) {
      if (X[k] == null || Y[k] == null) return;
      pts.push({ k: k, u: u, x: X[k], y: Y[k], z: Z ? Z[k] : null, x0: tx ? tx.d0[lv][k] : null, y0: ty ? ty.d0[lv][k] : null,
        dedans: !S.r || region(u, lv) === S.r });
    });
    return pts;
  }

  function stats(pts) {
    var p = pts.filter(function (q) { return q.dedans && (S.zm !== "p" || !S.z || q.z != null); }), n = p.length;
    if (n < 10) return { n: n, trop: true };
    var rx = rangs(p.map(function (q) { return q.x; })), ry = rangs(p.map(function (q) { return q.y; })), r = pearson(rx, ry), k = 0;
    if (S.zm === "p" && S.z && dispo(S.z, S.lv)) {
      var rz = rangs(p.map(function (q) { return q.z; })), rxz = pearson(rx, rz), ryz = pearson(ry, rz);
      r = (r - rxz * ryz) / Math.sqrt((1 - rxz * rxz) * (1 - ryz * ryz)); k = 1;
    }
    return { n: n, r: r, ic: ic(r, n, k), p: pCorr(r, n - 2 - k), partiel: !!k };
  }

  function cle() { return [eff(S.x), eff(S.y), S.lv, S.r, S.zm === "p" ? S.z : "", S.traj ? 1 : 0].join("|"); }
  function noter(st) {
    if (st.trop) return;
    var c = cle(), h = HISTO.filter(function (e) { return e.c === c; })[0];
    if (!h) { h = { c: c, s: JSON.parse(JSON.stringify(S)) }; HISTO.push(h); }
    h.r = st.r; h.p = st.p; h.n = st.n;
    var adj = bh(HISTO.map(function (e) { return e.p; }));
    HISTO.forEach(function (e, j) { e.padj = adj[j]; });
    return h;
  }

  // couleurs, lues sur les jetons de la page pour suivre le thème
  function jeton(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
  function hex(c) { c = c.replace("#", ""); return [0, 2, 4].map(function (k) { return parseInt(c.substr(k, 2), 16) / 255; }); }
  function tohex(a) { return "#" + a.map(function (v) { var s = Math.round(Math.max(0, Math.min(1, v)) * 255).toString(16); return s.length < 2 ? "0" + s : s; }).join(""); }
  // fond sombre : luminance du fond sous la moitié (la page comparait au fond sombre d'avant, plus clair que l'actuel, et dessinait
  // les classes du fond clair sur le fond sombre, relecture de l'étape 4 du 5 novembre 2026)
  function sombre() { var c = hex(jeton("--bg") || "#F4F4F1"); return .2126 * c[0] + .7152 * c[1] + .0722 * c[2] < .5; }
  // case de la carte à deux indicateurs, jetons --bv0 à --bv8 de la feuille du site (les mêmes que l'atlas et les
  // rapports) : i tiers de l'axe horizontal (canard), j tiers de l'axe vertical (cuivre)
  function bivar(i, j) { return jeton("--bv" + (i * 3 + j)); }
  function seq(k) { return jeton(["--r0", "--r1", "--r2", "--r3", "--r4"][k]); }
  function quantiles(vals, q) {
    var a = vals.filter(function (v) { return v != null; }).sort(function (p, r) { return p - r; });
    var b = []; for (var k = 1; k < q; k++) b.push(a[Math.floor(k * a.length / q)]); return b;
  }
  function classe(v, b) { var k = 0; while (k < b.length && v >= b[k]) k++; return k; }

  function graduations(lo, hi, n) {
    var pas = Math.pow(10, Math.floor(Math.log10((hi - lo) / n || 1))), e = (hi - lo) / n / pas;
    pas *= e > 5 ? 10 : e > 2 ? 5 : e > 1 ? 2 : 1;
    var out = []; for (var v = Math.ceil(lo / pas) * pas; v <= hi + 1e-9; v += pas) out.push(Math.round(v / pas) * pas || 0); return out;
  }

  // Titre d'axe passé à la ligne mot à mot, trois lignes au plus, au-delà de la place disponible
  // (environ 6,6 pixels par caractère à la taille des titres d'axe).
  function lignesAxe(t, place) {
    var max = Math.max(12, Math.floor(place / 6.6)), l = [""];
    t.split(" ").forEach(function (m) {
      var c = l[l.length - 1];
      if (c && (c + " " + m).length > max) l.push(m); else l[l.length - 1] = c ? c + " " + m : m;
    });
    if (l.length > 3) { l = l.slice(0, 3); l[2] = l[2].slice(0, max - 1) + "…"; }
    return l;
  }

  // dessin du nuage
  function dessinerNuage(pts, refx, refy) {
    var svg = $("nuage"), W = Math.round(Math.max(320, Math.min(700, svg.parentNode.clientWidth - 24 || 560))), H = Math.round(W < 500 ? W * 0.95 : Math.min(460, W * 0.68)), ml = 52, mr = 14, mt = 40, mb = 52;
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    var dd = pts.filter(function (p) { return p.dedans; });
    var xs = dd.map(function (p) { return p.x; }).concat(dd.map(function (p) { return p.x0; }).filter(function (v) { return v != null; }));
    var ys = dd.map(function (p) { return p.y; }).concat(dd.map(function (p) { return p.y0; }).filter(function (v) { return v != null; }));
    if (refx) xs.push(refx.v); if (refy) ys.push(refy.v);
    var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs), y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
    var px = (x1 - x0) * 0.05 || 1, py = (y1 - y0) * 0.06 || 1; x0 -= px; x1 += px; y0 -= py; y1 += py;
    // Marge gauche à la mesure des graduations, pour que « 25 000 » ne touche jamais le titre de l'axe.
    var gy = graduations(y0, y1, W < 500 ? 5 : 6);
    ml = Math.max(52, 32 + Math.max.apply(null, gy.map(function (v) { return f(v).length; })) * 6.4) +
      15 * (lignesAxe(court(IND[eff(S.y)]), H - mt - mb).length - 1);
    mb = 52 + 15 * (lignesAxe(court(IND[eff(S.x)]), W - ml - mr).length - 1);
    var sx = function (v) { return ml + (v - x0) / (x1 - x0) * (W - ml - mr); }, sy = function (v) { return H - mb - (v - y0) / (y1 - y0) * (H - mt - mb); };
    var Z = S.z && dispo(S.z, S.lv) ? IND[eff(S.z)] : null, zv = pts.map(function (p) { return p.z; }), zb = Z && S.zm === "c" ? quantiles(zv, 5) : null;
    var zmax = Math.max.apply(null, (Z && S.zm === "t" ? zv : pts.map(function (p) { return p.u.pop; })).filter(function (v) { return v != null && v > 0; }));
    var rmax = S.lv === "epci" ? 11 : S.lv === "dep" ? 15 : 22;
    var s = "";
    s += '<g class="axe">';
    graduations(x0, x1, W < 500 ? 4 : 6).forEach(function (v) { var X = sx(v); s += '<line x1="' + X + '" x2="' + X + '" y1="' + mt + '" y2="' + (H - mb) + '" opacity=".35"/><text x="' + X + '" y="' + (H - mb + 16) + '" text-anchor="middle">' + f(v) + "</text>"; });
    gy.forEach(function (v) { var Y = sy(v); s += '<line x1="' + ml + '" x2="' + (W - mr) + '" y1="' + Y + '" y2="' + Y + '" opacity=".35"/><text x="' + (ml - 6) + '" y="' + (Y + 4) + '" text-anchor="end">' + f(v) + "</text>"; });
    s += "</g>";
    var ix = IND[eff(S.x)], iy = IND[eff(S.y)];
    // Titres d'axe sur deux lignes au plus quand ils dépassent la place, jamais coupés au bord du cadre.
    var lx = lignesAxe(court(ix), W - ml - mr), ly = lignesAxe(court(iy), H - mt - mb);
    s += '<text class="lab" x="' + (ml + (W - ml - mr) / 2) + '" y="' + (H - 12 - 15 * (lx.length - 1)) + '" text-anchor="middle">' +
      lx.map(function (t, k) { return '<tspan x="' + (ml + (W - ml - mr) / 2) + '" dy="' + (k ? 15 : 0) + '">' + esc(t) + "</tspan>"; }).join("") + "</text>";
    s += '<text class="lab" transform="translate(14,' + (mt + (H - mt - mb) / 2) + ') rotate(-90)" text-anchor="middle">' +
      ly.map(function (t, k) { return '<tspan x="0" dy="' + (k ? 15 : 0) + '">' + esc(t) + "</tspan>"; }).join("") + "</text>";
    if (refx) s += '<line class="ref" x1="' + sx(refx.v) + '" x2="' + sx(refx.v) + '" y1="' + mt + '" y2="' + (H - mb) + '"/>';
    // étiquettes des repères hors du cadre des points, dans la bande du haut (audit de contrôle du 30 octobre 2026, F5) :
    // la verticale au-dessus de son trait, l'horizontale à droite, précédée d'un petit trait qui la désigne
    // largeur de l'étiquette estimée (12 px, environ 6,4 px par signe) : elle se pose à droite du trait si elle tient,
    // sinon à gauche, sinon au bord gauche du cadre ; elle ne sort jamais de la figure (relecture de l'étape 4, téléphone)
    // la précision « trait vertical » ou « horizontal » se raccourcit si la place manque, jamais au point de rendre
    // les deux étiquettes identiques tant qu'un mot tient (relecture indépendante du 5 novembre 2026, téléphone)
    function suffixe(t, long, court, x0) { return x0 + (t.length + long.length) * 5.9 <= W - mr ? long : x0 + (t.length + court.length) * 5.9 <= W - mr ? court : ""; }
    var xl = 4;   // légende des repères au bord gauche de la figure, au-dessus des graduations, dont elle prend la place
    var ax = refx ? sx(refx.v) : 0, lw = refx ? (refx.t.length + 16) * 6.4 : 0;
    var ancre = refx && ax + 4 + lw > W - mr ? (ax - 4 - lw >= ml ? "end" : "bord") : "start";
    // au bord gauche, loin de son trait, l'étiquette de la verticale est précédée d'un court trait vertical en tirets
    var etiq = refx ? (ancre === "bord" ? '<line class="ref" x1="' + (xl + 10) + '" x2="' + (xl + 10) + '" y1="' + (mt - 32) + '" y2="' + (mt - 20) + '"/>' : "") +
      '<text class="reftxt" x="' + (ancre === "end" ? ax - 4 : ancre === "bord" ? xl + 26 : ax + 4) + '" y="' + (mt - 22) + '" text-anchor="' + (ancre === "bord" ? "start" : ancre) + '">' + esc(refx.t) + (ancre === "bord" ? suffixe(refx.t, ", trait vertical", ", vertical", xl + 26) : ", trait vertical") + "</text>" : "";
    if (refy) s += '<line class="ref" x1="' + ml + '" x2="' + (W - mr) + '" y1="' + sy(refy.v) + '" y2="' + sy(refy.v) + '"/>';
    // l'étiquette de l'horizontale, loin de son trait, est précédée d'un court trait en tirets, le même que sa ligne,
    // qui la relie à elle comme dans une légende, au bord gauche du cadre, à 6 px du texte (relecture du 5 novembre 2026)
    if (refy) etiq += '<line class="ref" x1="' + xl + '" x2="' + (xl + 20) + '" y1="' + (mt - 10) + '" y2="' + (mt - 10) + '"/>' +
      '<text class="reftxt" x="' + (xl + 26) + '" y="' + (mt - 6) + '" text-anchor="start">' + esc(refy.t) + suffixe(refy.t, ", trait horizontal", ", horizontal", xl + 26) + "</text>";
    var tri = pts.slice().sort(function (a, b) { return (b.z != null && S.zm === "t" ? b.z : b.u.pop) - (a.z != null && S.zm === "t" ? a.z : a.u.pop); });
    tri.forEach(function (p) {
      if (S.traj && (p.x0 != null || p.y0 != null)) s += '<line class="traj" x1="' + sx(p.x0 != null ? p.x0 : p.x) + '" y1="' + sy(p.y0 != null ? p.y0 : p.y) + '" x2="' + sx(p.x) + '" y2="' + sy(p.y) + '"' + (p.dedans ? "" : ' opacity=".08"') + "/>";
    });
    var sig = [];
    tri.forEach(function (p) {
      var t = Z && S.zm === "t" ? p.z : p.u.pop, r = t != null && t > 0 ? Math.max(2.2, Math.sqrt(t / zmax) * rmax) : 2.2;
      var col = zb ? (p.z == null ? jeton("--nodata") : seq(classe(p.z, zb))) : jeton("--r3");
      s += '<circle class="pt' + (p.dedans ? "" : " hors") + (S.sel === p.u.c ? " sel" : "") + '" data-c="' + p.u.c + '" cx="' + sx(p.x).toFixed(1) + '" cy="' + sy(p.y).toFixed(1) + '" r="' + r.toFixed(1) + '" fill="' + col + '" fill-opacity="' + (zb ? 0.95 : 0.7) + '"/>';
      if (signalT(p.u)) sig.push({ x: sx(p.x), y: sy(p.y), r: r });
    });
    // Signal « ! » posé à côté du point, à la première place libre, pour que deux signaux ne se recouvrent jamais.
    var pris = [];
    sig.forEach(function (q) {
      var places = [[q.r + 2, -q.r + 2], [-q.r - 6, -q.r + 2], [q.r + 2, q.r + 8], [-q.r - 6, q.r + 8], [-2, -q.r - 4], [-2, q.r + 13], [q.r + 9, 4], [-q.r - 13, 4]];
      var c = places[0];
      for (var k = 0; k < places.length; k++) {
        var x = q.x + places[k][0], y = q.y + places[k][1];
        if (!pris.some(function (b) { return Math.abs(b[0] - x) < 8 && Math.abs(b[1] - y) < 15; })) { c = places[k]; break; }
      }
      pris.push([q.x + c[0], q.y + c[1]]);
      s += '<text class="signal" x="' + (q.x + c[0]).toFixed(1) + '" y="' + (q.y + c[1]).toFixed(1) + '">!</text>';
    });
    // Étiquettes des repères posées après les points, pour qu'aucune bulle ne les couvre.
    s += etiq;
    svg.innerHTML = s;
    var leg = "";
    if (zb) leg = '<span>' + esc(court(Z)) + '</span><span class="seq">' + [0, 1, 2, 3, 4].map(function (k) { return '<i style="background:' + seq(k) + '"></i>'; }).join("") + "</span><span>du cinquième le plus bas au plus haut, de " + f(Math.min.apply(null, zv.filter(function (v) { return v != null; }))) + " à " + f(Math.max.apply(null, zv.filter(function (v) { return v != null; }))) + "</span>";
    else leg = "<span>Taille des points selon " + (Z && S.zm === "t" ? esc(court(Z)) : "la population") + "</span>";
    if (S.traj && (trajSerie(S.x, S.lv) || trajSerie(S.y, S.lv))) leg += '<span>Trait gris, chemin depuis le début de la série</span>';
    $("leg-nuage").innerHTML = leg;
  }

  // dessin de la carte
  function dessinerCarte(pts) {
    var lv = S.lv, svg = $("carte"), G = A.geo[lv];
    svg.setAttribute("viewBox", "0 0 " + A.W + " " + A.H);
    var parC = {}; pts.forEach(function (p) { parC[p.u.c] = p; });
    var dd = pts.filter(function (p) { return p.dedans; });
    var bx = quantiles(dd.map(function (p) { return p.x; }), 3), by = quantiles(dd.map(function (p) { return p.y; }), 3);
    var b1 = S.v === "x" ? quantiles(dd.map(function (p) { return p.x; }), 5) : S.v === "y" ? quantiles(dd.map(function (p) { return p.y; }), 5) : null;
    var s = "";
    Object.keys(G).forEach(function (c) {
      var p = parC[c], col = null, cls = "terr";
      if (!p) cls += " vide";
      else {
        col = S.v === "b" ? bivar(classe(p.x, bx), classe(p.y, by)) : seq(classe(S.v === "x" ? p.x : p.y, b1));
        if (!p.dedans) cls += " hors";
      }
      if (S.sel === c) cls += " sel";
      s += '<path class="' + cls + '" data-c="' + c + '" d="' + G[c] + '"' + (col ? ' fill="' + col + '"' : "") + "/>";
    });
    // le territoire repéré passe au premier plan pour que son contour ne soit pas recouvert
    svg.innerHTML = s;
    var sel = S.sel && svg.querySelector('path[data-c="' + S.sel + '"]'); if (sel) svg.appendChild(sel);
    var leg;
    if (S.v === "b") {
      // légende de 120 pixels, les deux axes écrits le long de la grille (point I12)
      var cases = ""; for (var j = 2; j >= 0; j--) for (var i = 0; i < 3; i++) cases += '<i style="background:' + bivar(i, j) + '"></i>';
      leg = '<span class="bivar-cadre"><span class="bivar-y">' + esc(court(IND[eff(S.y)])) + ', valeur plus élevée&nbsp;→</span><span class="bivar" aria-hidden="true">' + cases + '</span><span class="bivar-x">' + esc(court(IND[eff(S.x)])) + ", valeur plus élevée&nbsp;→</span></span><span>Chaque indicateur en trois tiers de territoires</span>";
    } else {
      leg = '<span class="seq">' + [0, 1, 2, 3, 4].map(function (k) { return '<i style="background:' + seq(k) + '"></i>'; }).join("") + "</span><span>" + esc(court(IND[eff(S.v === "x" ? S.x : S.y)])) + ", en cinq parts égales de territoires</span>";
    }
    leg += '<span>Gris, sans donnée ou écarté' + (lv !== "reg" ? ", Mayotte comprise" : "") + "</span>";
    $("leg-carte").innerHTML = leg;
  }

  function court(i) { return i.lab.replace(/, pour 100 000 .*$/, "").replace(/^Distance à la structure la plus proche, /, "Distance, "); }
  // Phrase de limite d'un territoire. Les régions sont rangées sous « reg: » (une région et un département
  // peuvent porter le même code), une intercommunalité hérite d'une limite posée sur son département.
  var MOT_TYPE = { "lieu_cmp_adultes": "CMP pour adultes", "lieu_cmp_enfants": "CMP pour enfants", "lieu_cattp": "CATTP", "lieu_hdj_psy_enfants": "jour en psychiatrie pour enfants", "lieu_hdj_psy_adultes": "jour en psychiatrie pour adultes" };
  function concerne(id, t) { var m = /(?:lieux_|dist_)(lieu_\w+)/.exec(id); if (!m || !MOT_TYPE[m[1]] || !t) return true; return t.indexOf(MOT_TYPE[m[1]]) >= 0; }
  function limTerr(i, u) {
    if (!i.limT) return null;
    var t = S.lv === "reg" ? i.limT["reg:" + u.c] : (i.limT[u.c] || (S.lv === "epci" && u.p ? i.limT[u.p] : null));
    return t && concerne(i.id, t) ? t : null;
  }
  function signalT(u) {
    var r = false;
    [S.x, S.y].forEach(function (id) { var t = limTerr(IND[eff(id)], u); if (t) r = t; });
    return r;
  }
  // Raison d'une valeur absente, écrite à côté du vide : nombre sous le seuil de publication ou limite.
  function raisonVide(u) {
    var k = A.units[S.lv].indexOf(u), out = [];
    [S.x, S.y].forEach(function (id) {
      var i = IND[eff(id)], v = valeurs(id, S.lv)[k];
      if (v != null) return;
      var np = i.np && i.np[S.lv] && i.np[S.lv][u.c];
      var t = np || limTerr(i, u);
      if (t) out.push(court(i) + ", " + t);
    });
    return out.join(". ");
  }

  // règle unique du lien (presentation/lien.js, pipeline/regle_lien.py) : |rho| d'au moins 0,3 et probabilité
  // corrigée par Benjamini-Hochberg sous 0,05, la même que les rapports et l'escalier
  function phrase(st, h) {
    var ix = IND[eff(S.x)], iy = IND[eff(S.y)], niv = NIV_PL[S.lv];
    if (st.trop) return "Trop peu de " + niv + " ont les deux indicateurs pour mesurer un lien (" + st.n + ").";
    var sens = st.r > 0 ? "plus élevé aussi" : "plus bas", t = force(st.r), eg = st.partiel ? ", en tenant égal l’indicateur « " + low(court(IND[eff(S.z)])) + " »" : "";
    if (S.lv === "reg") return "Entre régions, trop peu de territoires pour dire un lien. La corrélation de rang vaut " + r2(st.r) + eg + ", à lire avec son intervalle.";
    if (!Lien.est(st.r, h ? h.padj : st.p)) return "Les indicateurs « " + low(court(ix)) + " » et « " + low(court(iy)) + " » ne sont pas liés au-delà du seuil retenu sur tout le site" + eg + " (corrélation de rang " + r2(st.r) + ", lien dit à partir de 0,3 et après correction des tests multiples).";
    return "Dans les " + niv + " où l'indicateur « " + low(court(ix)) + " » est plus élevé, l'indicateur « " + low(court(iy)) + " » tend à être " + sens + eg + ". Le lien est " + t + ".";
  }
  function low(s) { return /^[A-Z]{2}/.test(s) ? s : s.charAt(0).toLowerCase() + s.slice(1); }

  function mesures(st, h) {
    if (st.trop) { $("mesures").innerHTML = ""; return; }
    var adj = h ? h.padj : st.p;
    $("mesures").innerHTML =
      '<div><span class="n">' + r2(st.r) + '</span><span class="l">corrélation de rang' + (st.partiel ? " partielle" : "") + ", " + (S.lv !== "reg" && Lien.est(st.r, adj) ? "lien " + force(st.r) : "sous le seuil du lien") + "</span></div>" +
      '<div><span class="n">' + r2(st.ic[0]) + " à " + r2(st.ic[1]) + '</span><span class="l">intervalle de confiance à 95 %</span></div>' +
      '<div><span class="n">' + fp(adj) + '</span><span class="l">probabilité corrigée sur ' + HISTO.length + " croisement" + (HISTO.length > 1 ? "s" : "") + " de la visite</span></div>" +
      '<div><span class="n">' + fr0.format(st.n) + '</span><span class="l">' + NIV_PL[S.lv] + " dans le calcul" + (S.r ? ", dans " + esc(REGNOM[S.r]) : "") + "</span></div>";
  }

  function limites() {
    var out = "", vus = {};
    [S.x, S.y, S.z].forEach(function (id) {
      if (!id) return; var i = IND[eff(id)]; if (!i || vus[i.id]) return; vus[i.id] = 1;
      var lim = i.lim ? i.lim.split(/(?<=\.)\s/)[0] : "";
      out += '<p class="limite">' + (lim ? "<b>!</b>" : '<b style="visibility:hidden">!</b>') + "<span><strong>" + esc(court(i)) + "</strong>, " + esc(i.src) + ", " + esc(i.lic) + (lim ? ". " + esc(lim) : ".") + (i.fi ? ' <a href="indicateur/' + i.fi + '.html">Fiche de l’indicateur</a>' : "") + "</span></p>";
    });
    $("limites").innerHTML = out;
  }

  function carteTerr(pts, rx, ry) {
    var p = pts.filter(function (q) { return q.u.c === S.sel; })[0];
    if (!p) { $("terr").innerHTML = '<h3>Territoire repéré</h3><p class="vide-txt">Cliquez un point ou un territoire de la carte.</p>'; return; }
    function ligne(id, v, ref) {
      var i = IND[eff(id)], c = !(S.traj && trajSerie(id, S.lv)) ? Chiffres.cellule(A, i.id, S.lv, p.k, v) : null;
      // statut sous le nom de l'indicateur, la colonne des valeurs ne passant pas à la ligne (il touchait le repère au
      // téléphone) ; sans valeur, le statut tient lieu de valeur
      var txt = c ? c.txt || c.statut : f(v), st = c && c.txt && c.statut ? "<br><small>" + esc(c.statut) + "</small>" : "", rt = c ? c.ref_txt : ref ? f(ref.v) : "";
      var e = c ? c.ecart : ref && ref.v ? Chiffres.ecart(v, ref.v) : null;
      return '<tr><th scope="row">' + esc(court(i)) + st + '</th><td class="v">' + txt + '</td><td class="v m">' + rt + '</td><td class="v">' + (e ? e.t : "") + "</td></tr>";
    }
    var rows = ligne(S.x, p.x, rx) + ligne(S.y, p.y, ry);
    if (S.z && p.z != null) { var zz = valeurs(S.z, S.lv); rows += ligne(S.z, p.z, reference(S.z, S.lv, zz)); }
    var sig = signalT(p.u);
    var fiche = '<a href="territoire/' + S.lv + "/" + encodeURIComponent(p.u.c) + '.html">Ouvrir la fiche du territoire</a>';
    $("terr").innerHTML = "<h3>" + esc(p.u.nm) + "</h3><table><thead><tr><th scope=\"col\">Indicateur</th><th scope=\"col\" class=\"v\">Ici</th><th scope=\"col\" class=\"v\">Repère</th><th scope=\"col\" class=\"v\">Écart</th></tr></thead><tbody>" + rows + "</tbody></table>" +
      (sig ? '<p class="limite"><b>!</b><span>' + esc(sig) + "</span></p>" : "") + '<p class="discret" style="margin-top:8px">Repère, ' + esc(low(rx ? rx.t : "médiane des " + NIV_PL[S.lv])) + ". " + fiche + "</p>";
  }

  function histo() {
    var c = cle();
    $("histo").innerHTML = HISTO.slice().reverse().map(function (e) {
      var j = HISTO.indexOf(e), s = e.s, ix = IND[eff2(s.x, s.m)], iy = IND[eff2(s.y, s.m)];
      return '<li' + (e.c === c ? ' aria-current="true"' : "") + '><button type="button" data-h="' + j + '"><span class="q">' + esc(court(ix)) + " et " + esc(low(court(iy))) + ", " + NIV_PL[s.lv] + (s.r ? ", " + esc(REGNOM[s.r]) : "") + (s.zm === "p" && s.z ? ", en tenant égal « " + esc(low(court(IND[eff2(s.z, s.m)]))) + " »" : "") + '</span><span class="r">' + r2(e.r) + "<br>p corr. " + fp(e.padj) + "</span></button></li>";
    }).join("");
  }
  // la rangée n'a de largeur qu'une fois la fenêtre ouverte : mesurée après showModal (relecture du 5 novembre 2026)
  function domaineEnVue() {
    var choisi = document.querySelector('#menu-doms [aria-pressed="true"]'), rang = $("menu-doms");
    if (choisi && rang.scrollWidth > rang.clientWidth) rang.scrollLeft += choisi.getBoundingClientRect().left - rang.getBoundingClientRect().left - 10;
  }
  function eff2(id, m) { var i = IND[id]; if (!i || i.type !== "prof") return id; var j = "prof:" + i.prof + ":" + m; return IND[j] ? j : id; }

  function citer() {
    var ix = IND[eff(S.x)], iy = IND[eff(S.y)], lien = location.href.split("#")[0] + "#" + etat();
    // même forme que les figures du site (figures.js) : la citation et « Copier la citation », puis une ligne par
    // fichier (image, données), puis le lien permanent cliquable (H3 et relecture de l'étape 4, 5 novembre 2026)
    function texte(quoi) { return A.citation + ", Ubi Cura, " + quoi + " de « " + ix.lab + " » et de « " + iy.lab + " » par " + NIV_SING[S.lv] + ", version du " + A.version + (A.doi ? ", doi:" + A.doi : "") + "."; }
    function boite(quoi, nom, png, svg) {
      var t = texte(quoi);
      return '<p class="cit">' + esc(t).replace(/doi:(\S+?)\.$/, function (m, d) { return 'doi:<a href="https://doi.org/' + d + '">' + d + "</a>."; }) + "</p>" +
        '<div class="citation-actions"><button type="button" data-copier="' + esc(t) + '">Copier la citation</button></div>' +
        '<ul class="exports"><li><span class="nom"><span class="genre">Image</span> ' + nom + '</span><span class="citation-actions"><button type="button" data-export="' + png + '">PNG</button><button type="button" data-export="' + svg + '">SVG</button></span></li>' +
        '<li><span class="nom"><span class="genre">Données</span> du croisement</span><span class="citation-actions"><button type="button" data-export="csv">CSV</button></span></li></ul>' +
        '<p class="small muted lien-permanent">Lien permanent vers ce réglage, <a href="' + esc(lien) + '">' + esc(lien) + "</a></p>";
    }
    if ($("citer-carte")) { $("citer-carte").classList.add("citation-fig"); $("citer-carte").innerHTML = boite("carte du croisement", "de la carte", "carte-png", "carte-svg"); }
    $("citer").classList.add("citation-fig"); $("citer").innerHTML = boite("croisement", "du nuage", "png", "svg");
  }

  // état dans l'adresse, pour le lien permanent
  function etat() { return ["x=" + S.x, "y=" + S.y, "z=" + S.z, "zm=" + S.zm, "lv=" + S.lv, "m=" + S.m, "r=" + S.r, "t=" + (S.traj ? 1 : 0), "v=" + S.v, "s=" + (S.sel || "")].join("&"); }
  function lireEtat() {
    var h = location.hash.slice(1); if (!h) return;
    h.split("&").forEach(function (kv) { var p = kv.split("="), k = p[0], v = decodeURIComponent(p[1] || "");
      if (k === "x" || k === "y") { if (IND[v]) S[k] = v; } else if (k === "z") S.z = IND[v] ? v : ""; else if (k === "zm" || k === "m" || k === "r" || k === "v") S[k] = v; else if (k === "lv" && A.units[v]) S.lv = v; else if (k === "t") S.traj = v === "1"; else if (k === "s") S.sel = v || null; });
  }

  function reglages() {
    ["x", "y", "z"].forEach(function (a) {
      var b = document.querySelector('[data-axe="' + a + '"]'), i = S[a] ? IND[eff(S[a])] : null;
      b.innerHTML = i ? esc(i.lab) + '<span class="dom">' + NOMDOM[i.domb] + ", " + esc(i.u || "") + (i.an ? ", " + esc(i.an) : "") + "</span>" : "Aucun<span class=\"dom\">la taille suit alors la population</span>";
    });
    document.querySelectorAll("#zmode button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-zm") === S.zm)); b.disabled = !S.z; });
    var nv = ""; ["reg", "dep", "epci"].forEach(function (lv) {
      var ok = dispo(S.x, lv) && dispo(S.y, lv);
      nv += '<button type="button" data-lv="' + lv + '" aria-pressed="' + (lv === S.lv) + '"' + (ok ? "" : " disabled") + ">" + A.niveaux[lv] + "</button>";
    });
    $("niveaux").innerHTML = nv;
    var manque = ["reg", "dep", "epci"].filter(function (lv) { return !(dispo(S.x, lv) && dispo(S.y, lv)); }).map(function (lv) { return NIV_PL[lv]; });
    $("note-niv").textContent = manque.length ? "Pas de croisement par " + manque.join(" ni par ") + ", l'un des deux indicateurs n'y est pas publié." : "";
    document.querySelectorAll("#modes button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-m") === S.m)); });
    var aProf = [S.x, S.y, S.z].some(function (id) { return id && IND[id] && IND[id].type === "prof"; });
    document.querySelectorAll("#modes button").forEach(function (b) { b.disabled = !aProf; });
    var sel = $("region"), opts = '<option value="">Toute la France</option>';
    if (S.lv !== "reg") A.units.reg.slice().sort(function (a, b) { return a.nm.localeCompare(b.nm, "fr"); }).forEach(function (u) { opts += '<option value="' + u.c + '"' + (u.c === S.r ? " selected" : "") + ">" + esc(u.nm) + "</option>"; });
    sel.innerHTML = opts; sel.disabled = S.lv === "reg";
    var tx = trajSerie(S.x, S.lv) || trajSerie(S.y, S.lv);
    $("traj").disabled = !tx; $("traj").checked = S.traj && !!tx;
    $("note-temps").textContent = tx ? "Les densités passent alors à la série annuelle du répertoire, la même aux deux dates." : "Possible quand un axe porte une profession suivie depuis 2016 (généralistes, psychiatres, pédiatres, sages-femmes...) ou une évolution.";
    $("traj-lib").textContent = "Montrer le chemin depuis " + (tx ? tx.debut : 2016);
    document.querySelectorAll("#vue-carte button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-v") === S.v)); });
    $("resume-tel").textContent = court(IND[eff(S.x)]) + " et " + low(court(IND[eff(S.y)])) + ", " + NIV_PL[S.lv];
  }

  function rendre() {
    if (!(dispo(S.x, S.lv) && dispo(S.y, S.lv))) { var lv = ["dep", "reg", "epci"].filter(function (l) { return dispo(S.x, l) && dispo(S.y, l); })[0]; if (lv) S.lv = lv; }
    if (S.lv === "reg") S.r = "";
    if (S.traj && !(trajSerie(S.x, S.lv) || trajSerie(S.y, S.lv))) S.traj = false;
    reglages();
    var pts = points(), st = stats(pts), h = noter(st);
    var rx = reference(S.x, S.lv, valeurs(S.x, S.lv)), ry = reference(S.y, S.lv, valeurs(S.y, S.lv));
    $("titre").textContent = court(IND[eff(S.x)]) + " et " + low(court(IND[eff(S.y)])) + ", par " + NIV_SING[S.lv];
    $("phrase").textContent = phrase(st, h);
    // quand l'escalier d'Explorer répond à la même question, une ligne dit ce qui les distingue (audit de contrôle du
    // 30 octobre 2026, point I6)
    var esc1 = /^prof:([a-z_]+):all$/.exec(S.y) || /^prof:([a-z_]+):all$/.exec(S.x), autre = esc1 && (S.x === "revenu_median" || S.y === "revenu_median");
    var pe = $("escalier-note");
    if (!pe) { pe = document.createElement("p"); pe.id = "escalier-note"; pe.className = "note-escalier"; $("phrase").after(pe); }
    pe.hidden = !(autre && !st.trop);
    if (autre && !st.trop) pe.innerHTML = "La corrélation dit si l’offre monte régulièrement avec le niveau de vie, d’un territoire à l’autre. L’escalier d’Explorer range les habitants en dix tranches de niveau de vie et compare les tranches entre elles, il peut montrer un écart entre les extrêmes sans lien régulier. <a href=\"explorer.html#iFenEscalier?fam=" + (IND[eff("prof:" + esc1[1] + ":all")] && IND[eff("prof:" + esc1[1] + ":all")].sm ? "sm" : "sante") + "&iProf=" + esc1[1] + "\">Voir l’escalier dans Explorer</a>.";
    mesures(st, h); limites(); dessinerNuage(pts, rx, ry); dessinerCarte(pts); carteTerr(pts, rx, ry); histo(); citer();
    $("t-carte").textContent = S.v === "b" ? "Carte des deux indicateurs" : "Carte, " + low(court(IND[eff(S.v === "x" ? S.x : S.y)]));
    try { history.replaceState(null, "", "#" + etat()); } catch (e) {}
    PTS = pts;
  }
  var PTS = [];

  // sélecteur d'indicateur
  // Sélecteur d'indicateur, pensé pour plusieurs centaines d'indicateurs (partie 6 du second audit externe).
  // Recherche dans tout le catalogue, entrée « Santé mentale » qui traverse les domaines, filtre par niveau
  // géographique, et pour chaque indicateur son unité, son niveau le plus fin et son année quand elle est connue.
  var axeOuvert = null, domOuvert = "sm", nivF = "", voirVenir = true;
  var FIN = { epci: "intercommunalité", dep: "département", reg: "région" };
  // niveau annoncé par le producteur pour une base à venir, lu dans le texte du registre
  var NIV_TXT = { epci: /commune|iris|intercommun|arr[êe]t|points?\b|adresse|[ée]tablissement|logement|b[âa]timent|bassin|carreau|p[ée]rim[èe]tre|qpv|universit/i,
    dep: /d[ée]partement/i, reg: /r[ée]gion|zones proches/i };
  function auNiveau(i, lv) {
    if (!lv) return true;
    if (i.type !== "venir") return i.niv.indexOf(lv) >= 0;
    var t = i.niveau || "", ordre = ["epci", "dep", "reg"];
    return ordre.slice(0, ordre.indexOf(lv) + 1).some(function (l) { return NIV_TXT[l].test(t); });
  }
  function plusFin(i) { var l = ["epci", "dep", "reg"].filter(function (x) { return i.niv.indexOf(x) >= 0; })[0]; return l ? "le plus fin par " + FIN[l] : ""; }
  function ouvrirMenu(a) {
    axeOuvert = a; var i = S[a] ? IND[S[a]] : null; domOuvert = i ? (i.sm ? "sm" : i.domb) : "sm";
    $("menu-q").value = ""; listeMenu(); $("menu").showModal(); $("menu-q").focus(); domaineEnVue();
  }
  function listeMenu() {
    var q = norm($("menu-q").value.trim()), mots = q.split(/\s+/).filter(Boolean);
    var tout = A.ind.filter(function (i) { return (i.type !== "prof" || i.mode === "all") && (voirVenir || i.type !== "venir"); });
    var base = tout.filter(function (i) { return auNiveau(i, nivF); });
    var dans = function (d) { return function (i) { return d === "sm" ? i.sm : i.domb === d; }; };
    // les évolutions dans le temps d'une profession sont des variantes de celle-ci, comme ses modes d'exercice : elles
    // restent proposées mais ne s'ajoutent pas au nombre d'indicateurs, le même que sur Domaines et l'accueil
    var compte = function (i) { return i.type !== "venir" && i.type !== "evol"; };
    function nb(l) { var p = l.filter(compte).length, v = l.filter(function (i) { return i.type === "venir"; }).length; return p + (v ? '<small> + ' + v + "</small>" : ""); }
    $("menu-doms").innerHTML = (axeOuvert === "z" ? '<button type="button" data-dom="">Aucun<span class="nb"></span></button>' : "") +
      '<button type="button" class="dom-sm" data-dom="sm" aria-pressed="' + (!mots.length && domOuvert === "sm") + '">Santé mentale<span class="nb">' + nb(base.filter(dans("sm"))) + "</span></button>" +
      DOMS.map(function (d) {
        return '<button type="button" data-dom="' + d[0] + '" aria-pressed="' + (!mots.length && d[0] === domOuvert) + '">' + d[1] + '<span class="nb">' + nb(base.filter(dans(d[0]))) + "</span></button>";
      }).join("");
    var publies = base.filter(compte).length;
    $("menu-compte").textContent = publies + " indicateurs publiés" + (voirVenir ? ", " + base.filter(function (i) { return i.type === "venir"; }).length + " bases à venir" : "") + (nivF ? ", disponibles par " + FIN[nivF] : "") + ". À côté de chaque domaine, ses indicateurs publiés" + (voirVenir ? " + ses bases à venir" : "") + ".";
    document.querySelectorAll("#menu-niv button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-nivf") === nivF)); });
    // sur téléphone, les domaines défilent sur une rangée : le domaine choisi reste en vue
    domaineEnVue();
    // le nom du domaine n'est cherché qu'en second recours, sinon « logement » ramènerait tout le domaine
    var trouve = function (avecDom) { return base.filter(function (i) { var t = norm(i.lab + " " + i.grp + " " + i.sous + " " + (avecDom ? Domaines.par[i.domb].nom + " " : "") + (i.exp || "") + " " + (i.src || "")); return mots.every(function (m) { return t.indexOf(m) >= 0; }); }); };
    var liste = mots.length ? trouve(false) : base.filter(dans(domOuvert));
    if (mots.length && !liste.length) liste = trouve(true);
    // sous-thèmes dans l'ordre du modèle, les bases à venir en dernier
    var grp = {}, ordre = [], avecDom = mots.length || domOuvert === "sm";
    liste.forEach(function (i) {
      var g = (avecDom ? NOMDOM[i.domb] + ", " : "") + i.sous, d = Domaines.par[i.domb];
      if (!grp[g]) { grp[g] = { l: [], k: Domaines.liste.indexOf(d) * 100 + (i.sous === "À venir" ? 99 : d.sous.indexOf(i.sous)) }; ordre.push(g); }
      grp[g].l.push(i);
    });
    ordre.sort(function (a, b) { return grp[a].k - grp[b].k; });
    $("menu-liste").innerHTML = ordre.length ? ordre.map(function (g) {
      return "<h3>" + esc(g) + " <span>" + grp[g].l.length + "</span></h3>" + grp[g].l.map(function (i) {
        var venir = i.type === "venir";
        return '<button type="button" data-ind="' + i.id + '"' + (venir ? " disabled" : "") + ">" + esc(i.lab) + '<span class="niv">' +
          (venir ? ["base à venir", esc(i.src || ""), esc(i.niveau || "")].filter(Boolean).join(", ")
                 : [esc(i.u), plusFin(i), esc(i.an)].filter(Boolean).join(", ")) + "</span></button>";
      }).join("");
    }).join("") : '<p class="vide-txt">' + (mots.length ? "Aucun indicateur ne contient tous ces mots" : "Aucun indicateur de ce domaine") + (nivF ? " à ce niveau. Essayez « Tous les niveaux »." : ".") + "</p>";
  }

  // recherche de la page, qui propose des indicateurs et, quand deux mots trouvent deux indicateurs, la paire
  function chercher() {
    var q = norm($("q").value.trim()), out = $("trouves");
    if (q.length < 3) { out.innerHTML = ""; return; }
    var mots = q.split(/\s+/).filter(function (m) { return m.length > 2; });
    var base = A.ind.filter(function (i) { return i.type !== "venir" && (i.type !== "prof" || i.mode === "all"); });
    function score(i, ms) { var t = norm(i.lab), u = norm(i.grp + " " + (i.exp || "")); return ms.reduce(function (s, m) { return s + (t.indexOf(m) >= 0 ? 3 : u.indexOf(m) >= 0 ? 1 : 0); }, 0) - i.lab.length / 400; }
    var parMot = mots.map(function (m) { return base.map(function (i) { return [score(i, [m]), i]; }).filter(function (p) { return p[0] >= 2.5; }).sort(function (a, b) { return b[0] - a[0]; }); });
    var tous = base.map(function (i) { return [score(i, mots), i]; }).filter(function (p) { return p[0] >= 1; }).sort(function (a, b) { return b[0] - a[0]; }).slice(0, 6);
    var html = "<ul>";
    if (mots.length >= 2 && parMot[0].length && parMot[parMot.length - 1].length && parMot[0][0][1] !== parMot[parMot.length - 1][0][1]) {
      var a = parMot[0][0][1], b = parMot[parMot.length - 1][0][1];
      html += '<li><span class="paire-prop">' + esc(a.lab) + " et " + esc(low(b.lab)) + '</span><span class="act"><button class="mini" type="button" data-paire="' + a.id + "|" + b.id + '">Croiser</button></span></li>';
    }
    tous.forEach(function (p) { var i = p[1]; html += "<li><span>" + esc(i.lab) + ' <span class="discret">' + NOMDOM[i.domb] + '</span></span><span class="act"><button class="mini" type="button" data-mettre="x|' + i.id + '">En horizontal</button><button class="mini" type="button" data-mettre="y|' + i.id + '">En vertical</button></span></li>'; });
    out.innerHTML = tous.length ? html + "</ul>" : '<p class="discret">Aucun indicateur ne correspond. Essayez un autre mot, par exemple « revenu » ou « CMP ».</p>';
  }

  var QUESTIONS = [
    ["Les psychologues selon le niveau de vie", "revenu_median", "prof:psychologue:all", "epci"],
    ["Les généralistes là où vivent les plus âgés", "part_80p", "prof:medecin_generaliste:all", "epci"],
    ["Les psychiatres et les décès par suicide", "prof:psychiatre:all", "suicides", "dep"],
    ["Distance au CMP pour enfants et familles monoparentales", "part_monoparentales", "dist_lieu_cmp_enfants", "epci"]
  ];
  var INATTENDUS = [
    ["Logements suroccupés et orthophonistes", "part_logements_suroccupes", "prof:orthophoniste:all", "epci"],
    ["Mesures d'aide sociale à l'enfance et psychiatres de l'enfant", "ase_mesures", "prof:q_psychiatrie_enfant:all", "dep"],
    ["80 ans et plus vivant seuls et anxiolytiques", "part_80p_seuls", "anxiolytiques", "dep"],
    ["Élèves en situation de handicap et psychomotriciens", "eleves_handicap", "prof:psychomotricien:all", "dep"]
  ];
  function pistes(id, L) { $(id).innerHTML += L.map(function (q, k) { return '<button type="button" data-q="' + id + ":" + k + '">' + esc(q[0]) + "</button>"; }).join(""); }

  // événements
  document.addEventListener("click", function (ev) {
    var t = ev.target.closest("button,path.terr,circle.pt"); if (!t) return;
    if (t.matches("[data-axe]")) return ouvrirMenu(t.getAttribute("data-axe"));
    if (t.matches("[data-dom]")) { domOuvert = t.getAttribute("data-dom"); if (!domOuvert && axeOuvert === "z") { S.z = ""; $("menu").close(); rendre(); return; } $("menu-q").value = ""; listeMenu(); return; }
    if (t.matches("[data-nivf]")) { nivF = t.getAttribute("data-nivf"); listeMenu(); return; }
    if (t.matches("[data-ind]")) { S[axeOuvert] = t.getAttribute("data-ind"); if (axeOuvert === "z" && S.zm === "t" && !S.z) S.zm = "t"; $("menu").close(); rendre(); return; }
    if (t.id === "menu-fermer") return $("menu").close();
    if (t.matches("[data-zm]")) { S.zm = t.getAttribute("data-zm"); return rendre(); }
    if (t.matches("[data-lv]")) { S.lv = t.getAttribute("data-lv"); S.sel = null; return rendre(); }
    if (t.matches("[data-m]")) { S.m = t.getAttribute("data-m"); return rendre(); }
    if (t.matches("[data-v]")) { S.v = t.getAttribute("data-v"); return rendre(); }
    if (t.matches("[data-h]")) { var e = HISTO[+t.getAttribute("data-h")]; var sel = S.sel; Object.assign(S, JSON.parse(JSON.stringify(e.s))); S.sel = sel; return rendre(); }
    if (t.matches("[data-q]")) { var p = t.getAttribute("data-q").split(":"), q = (p[0] === "pistes" ? QUESTIONS : INATTENDUS)[+p[1]]; S.x = q[1]; S.y = q[2]; S.lv = q[3]; S.z = ""; S.zm = "t"; S.m = "all"; S.v = "b"; S.r = ""; S.traj = false; S.sel = null; rendre(); $("titre").scrollIntoView({ block: "start" }); return; }
    if (t.matches("[data-paire]")) { var pr = t.getAttribute("data-paire").split("|"); S.x = pr[0]; S.y = pr[1]; S.sel = null; $("trouves").innerHTML = ""; rendre(); $("titre").scrollIntoView({ block: "start" }); return; }
    if (t.matches("[data-mettre]")) { var mm = t.getAttribute("data-mettre").split("|"); S[mm[0]] = mm[1]; S.sel = null; rendre(); return; }
    if (t.matches("[data-export]")) { exporter(t.getAttribute("data-export")); return; }
    if (t.matches("[data-copier]")) { navigator.clipboard.writeText(t.getAttribute("data-copier")).then(function () { t.textContent = "Citation copiée"; }, function () { t.textContent = "Copie impossible ici"; }); return; }
    if (t.id === "ouvrir-reglages") { var r = $("reglages"), o = r.classList.toggle("ouvert"); t.setAttribute("aria-expanded", String(o)); return; }
    if (t.matches("path.terr,circle.pt")) { var c = t.getAttribute("data-c"); S.sel = S.sel === c ? null : c; rendre(); return; }
  });
  $("region").addEventListener("change", function (e) { S.r = e.target.value; rendre(); });
  $("traj").addEventListener("change", function (e) { S.traj = e.target.checked; rendre(); });
  $("menu-q").addEventListener("input", listeMenu);
  $("menu-venir").addEventListener("change", function (e) { voirVenir = e.target.checked; listeMenu(); });
  $("q").addEventListener("input", chercher);
  // Sur téléphone, une invite courte, l'exemple ne tiendrait pas dans le champ.
  if (matchMedia("(max-width: 700px)").matches) $("q").placeholder = "Indicateur ou question";
  $("cherche").addEventListener("submit", function (e) { e.preventDefault(); chercher(); });

  // bulle au survol
  var bulle = $("bulle");
  document.addEventListener("mousemove", function (ev) {
    var t = ev.target.closest && ev.target.closest("path.terr,circle.pt");
    if (!t) { bulle.hidden = true; return; }
    var c = t.getAttribute("data-c"), p = PTS.filter(function (q) { return q.u.c === c; })[0];
    var u = p ? p.u : A.units[S.lv].filter(function (q) { return q.c === c; })[0];
    if (!u) { bulle.hidden = false; bulle.innerHTML = "<b>Mayotte</b>Écartée des croisements, faute de données comparables."; }
    else {
      var s = "<b>" + esc(u.nm) + "</b>";
      if (p) { s += esc(court(IND[eff(S.x)])) + ", " + fv(S.x, S.lv, p.k, p.x) + "<br>" + esc(court(IND[eff(S.y)])) + ", " + fv(S.y, S.lv, p.k, p.y); if (S.z && p.z != null) s += "<br>" + esc(court(IND[eff(S.z)])) + ", " + fv(S.z, S.lv, p.k, p.z); var sg = signalT(u); if (sg) s += '<br><span class="sig">!</span> ' + esc(sg); }
      else { var rv = raisonVide(u); s += rv ? esc(rv) : "Sans donnée pour l'un des deux indicateurs."; }
      bulle.hidden = false; bulle.innerHTML = s;
    }
    var x = ev.clientX + 14, y = ev.clientY + 14; if (x + 310 > innerWidth) x = ev.clientX - 314; bulle.style.left = x + "px"; bulle.style.top = y + "px";
  });

  function exporter(k) {
    var ix = IND[eff(S.x)], iy = IND[eff(S.y)];
    if (k === "csv") {
      var l = ["code;territoire;" + ix.lab + ";" + iy.lab];
      PTS.filter(function (p) { return p.dedans; }).forEach(function (p) { l.push(p.u.c + ";" + p.u.nm + ";" + String(p.x).replace(".", ",") + ";" + String(p.y).replace(".", ",")); });
      telecharger(new Blob(["﻿" + l.join("\n")], { type: "text/csv" }), "croisement.csv");
    } else if (k === "svg") telecharger(new Blob([$("nuage").outerHTML], { type: "image/svg+xml" }), "croisement.svg");
    else if (k === "carte-svg" || k === "carte-png") {
      var racine = document.documentElement, avant = racine.getAttribute("data-theme"); racine.setAttribute("data-theme", "light"); rendre();
      var c = $("carte"), copie = c.cloneNode(true), o = c.querySelectorAll("*"), dd = copie.querySelectorAll("*");
      for (var q = 0; q < o.length; q++) { var cs = getComputedStyle(o[q]); ["fill", "stroke", "stroke-width", "opacity"].forEach(function (p) { dd[q].style.setProperty(p, cs.getPropertyValue(p)); }); }
      racine.setAttribute("data-theme", avant); rendre();
      copie.setAttribute("xmlns", "http://www.w3.org/2000/svg"); copie.setAttribute("width", A.W); copie.setAttribute("height", A.H);
      var fond = document.createElementNS("http://www.w3.org/2000/svg", "rect"); fond.setAttribute("width", A.W); fond.setAttribute("height", A.H); fond.setAttribute("fill", "#fff"); copie.insertBefore(fond, copie.firstChild);
      var txt = new XMLSerializer().serializeToString(copie);
      if (k === "carte-svg") { telecharger(new Blob([txt], { type: "image/svg+xml" }), "carte_croisement.svg"); return; }
      var img = new Image(), url = URL.createObjectURL(new Blob([txt], { type: "image/svg+xml" }));
      img.onload = function () { var cv = document.createElement("canvas"); cv.width = A.W * 2; cv.height = A.H * 2; var x = cv.getContext("2d"); x.fillStyle = "#fff"; x.fillRect(0, 0, cv.width, cv.height); x.drawImage(img, 0, 0, cv.width, cv.height); URL.revokeObjectURL(url); cv.toBlob(function (b) { telecharger(b, "carte_croisement.png"); }); };
      img.src = url;
    }
    else pngFondBlanc($("nuage"), "croisement.png");
  }
  // Export PNG sur fond blanc (règle 16 du registre) : la figure est relue avec les couleurs du fond clair, chaque
  // style calculé est écrit dans la copie, puis dessinée deux fois plus grande sur un fond blanc.
  function pngFondBlanc(svg, nom) {
    var racine = document.documentElement, avant = racine.getAttribute("data-theme");
    racine.setAttribute("data-theme", "light");
    var copie = svg.cloneNode(true), orig = svg.querySelectorAll("*"), dest = copie.querySelectorAll("*");
    for (var k = 0; k < orig.length; k++) { var cs = getComputedStyle(orig[k]); ["fill", "stroke", "stroke-width", "stroke-dasharray", "opacity", "font-size", "font-family", "font-weight"].forEach(function (p) { dest[k].style.setProperty(p, cs.getPropertyValue(p)); }); }
    racine.setAttribute("data-theme", avant);
    var vb = svg.viewBox.baseVal, w = vb && vb.width ? vb.width : svg.clientWidth, h = vb && vb.height ? vb.height : svg.clientHeight;
    copie.setAttribute("width", w); copie.setAttribute("height", h); copie.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    var img = new Image(), url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(copie)], { type: "image/svg+xml" }));
    img.onload = function () { var c = document.createElement("canvas"); c.width = w * 2; c.height = h * 2; var x = c.getContext("2d"); x.fillStyle = "#fff"; x.fillRect(0, 0, c.width, c.height); x.drawImage(img, 0, 0, c.width, c.height); URL.revokeObjectURL(url); c.toBlob(function (b) { telecharger(b, nom); }); };
    img.src = url;
  }
  function telecharger(b, n) { var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = n; a.click(); }

  // panneaux « Comment lire » et « Citer et exporter », un seul ouvert à la fois dans une même barre
  document.addEventListener("click", function (ev) {
    var o = ev.target.closest("[data-panneau]"); if (!o) return;
    var p = $(o.getAttribute("data-panneau")), ouvert = o.getAttribute("aria-expanded") === "true";
    o.parentNode.querySelectorAll("[data-panneau]").forEach(function (x) { x.setAttribute("aria-expanded", "false"); var q = $(x.getAttribute("data-panneau")); if (q) q.hidden = true; });
    if (!ouvert && p) { o.setAttribute("aria-expanded", "true"); p.hidden = false; }
  });
  pistes("pistes", QUESTIONS); pistes("pistes2", INATTENDUS);
  lireEtat(); rendre();
  var tempo; addEventListener("resize", function () { clearTimeout(tempo); tempo = setTimeout(rendre, 200); });
  new MutationObserver(function () { rendre(); }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  // hauteur réelle de l'en-tête, pour que la barre des réglages s'y colle sans jour (relecture du 5 novembre 2026,
  // comme explorer.js et l'atlas)
  var navS = document.querySelector("nav.site");
  function hautNav() { if (navS) document.documentElement.style.setProperty("--haut-nav", navS.offsetHeight + "px"); }
  hautNav(); addEventListener("resize", hautNav);
  if (navS && window.ResizeObserver) new ResizeObserver(hautNav).observe(navS);
})();
