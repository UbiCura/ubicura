// Atelier « Croiser » (présentation du 30 octobre 2026). Lit presentation/atelier_donnees.js (const A, préparé par
// pipeline/atelier.py), dessine le nuage et la carte en SVG,
// calcule la corrélation de rang, son intervalle et la corrélation partielle. Pour un couple d'une famille de tests
// publiée (presentation/atelier_familles.js, const FAM, pipeline/atelier.familles), la corrélation, l'intervalle de
// confiance, le nombre de territoires et la probabilité corrigée sont ceux du fichier publié, jamais recalculés (un
// chiffre publié est calculé en un seul endroit, audit du 27 novembre 2026) ; le verdict « lien » ne dépend plus des
// croisements essayés pendant la visite (option B de la structure validée le 26 novembre 2026). Hors de ces familles,
// la corrélation et son intervalle, calculé par la méthode du pipeline (bootstrap des centiles), sans verdict.
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

  var S = { x: "taux_pauvrete", y: "prof:psychiatre:all", z: "", zm: "t", lv: "dep", m: "all", r: "", traj: false, v: "b", sel: null, e: "log" };
  // croisements vus pendant la visite, pour y revenir ; ils ne changent aucune probabilité
  var VUS = [];
  var MODE_TXT = { all: "tous modes d’exercice réunis", lib: "exercice libéral", sal: "exercice salarié" };

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
  // Intervalle de confiance à 95 % d'un croisement que le fichier publié ne donne pas, par la méthode du pipeline
  // (analyses.spearman_bootstrap et spearman_partiel_bootstrap) : FAM.B tirages avec remise des territoires
  // (config.BOOTSTRAP), corrélation de rang de chaque tirage (partielle : rangs corrigés de leur relation linéaire avec
  // ceux de l'indicateur tenu égal), centiles 2,5 et 97,5 interpolés comme numpy. Tirages semés par la clé du croisement,
  // le même intervalle à chaque visite ; gardé en mémoire pendant la visite.
  var IC_VUS = {};
  function alea(cle) {
    var h = 2166136261; for (var k = 0; k < cle.length; k++) { h ^= cle.charCodeAt(k); h = Math.imul(h, 16777619); }
    var a = h >>> 0;
    return function () { a = (a + 0x6D2B79F5) | 0; var x = Math.imul(a ^ (a >>> 15), 1 | a); x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x; return ((x ^ (x >>> 14)) >>> 0) / 4294967296; };
  }
  function centre(r) { var n = r.length, m = 0, k; for (k = 0; k < n; k++) m += r[k]; m /= n; var o = new Array(n); for (k = 0; k < n; k++) o[k] = r[k] - m; return o; }
  function residus(r, rz) { var a = centre(r), b = centre(rz), sab = 0, sbb = 0, k; for (k = 0; k < a.length; k++) { sab += a[k] * b[k]; sbb += b[k] * b[k]; } var pe = sbb ? sab / sbb : 0; return a.map(function (v, j) { return v - pe * b[j]; }); }
  function corrC(a, b) { var s = 0, aa = 0, bb = 0; for (var k = 0; k < a.length; k++) { s += a[k] * b[k]; aa += a[k] * a[k]; bb += b[k] * b[k]; } return aa > 0 && bb > 0 ? s / Math.sqrt(aa * bb) : NaN; }
  function centile(a, q) { var h = (a.length - 1) * q, b = Math.floor(h); return b + 1 < a.length ? a[b] + (a[b + 1] - a[b]) * (h - b) : a[b]; }
  function icBoot(xs, ys, zs, cle) {
    if (IC_VUS[cle]) return IC_VUS[cle];
    var n = xs.length, B = (typeof FAM !== "undefined" && FAM.B) || 500, tire = alea(cle), bs = [];
    for (var b = 0; b < B; b++) {
      var ix = new Array(n); for (var k = 0; k < n; k++) ix[k] = Math.floor(tire() * n);
      var rx = rangs(ix.map(function (j) { return xs[j]; })), ry = rangs(ix.map(function (j) { return ys[j]; })), v;
      if (zs) { var rz = rangs(ix.map(function (j) { return zs[j]; })); v = corrC(residus(rx, rz), residus(ry, rz)); }
      else v = corrC(centre(rx), centre(ry));
      if (!isNaN(v)) bs.push(v);
    }
    bs.sort(function (p, q) { return p - q; });
    return (IC_VUS[cle] = bs.length ? [centile(bs, 0.025), centile(bs, 0.975)] : [NaN, NaN]);
  }
  function force(r) { var a = Math.abs(r); return a < 0.1 ? "négligeable" : a < 0.3 ? "faible" : a < 0.5 ? "modéré" : "fort"; }
  function r2(v) { var x = Math.round(v * 100) / 100; return fr.format(x === 0 ? 0 : x).replace("-", "−"); }
  // probabilité au millième : le format commun (deux décimales) écrivait « 0 » de 0,001 à 0,005
  var fr3 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 3 });
  function fp(p) { return p < 0.001 ? "moins de 0,001" : fr3.format(Math.round(p * 1000) / 1000); }

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
    var xs = p.map(function (q) { return q.x; }), ys = p.map(function (q) { return q.y; }), zs = null;
    var rx = rangs(xs), ry = rangs(ys), r = pearson(rx, ry), k = 0;
    if (S.zm === "p" && S.z && dispo(S.z, S.lv)) {
      zs = p.map(function (q) { return q.z; });
      var rz = rangs(zs), rxz = pearson(rx, rz), ryz = pearson(ry, rz);
      r = (r - rxz * ryz) / Math.sqrt((1 - rxz * rxz) * (1 - ryz * ryz)); k = 1;
    }
    // l'intervalle n'est calculé qu'à la demande (icDe), un couple publié prend celui du fichier
    return { n: n, r: r, xs: xs, ys: ys, zs: zs, p: pCorr(r, n - 2 - k), partiel: !!k };
  }
  function icDe(st) { return icBoot(st.xs, st.ys, st.zs, cle()); }

  // Famille de tests publiée du croisement affiché (option B, 26 novembre 2026) : les questions préparées entre
  // départements (croisements.csv), puis chaque profession face au profil des habitants, par niveau et mode d'exercice
  // (correlations_contexte.csv). Seulement pour le calcul publié : toute la France, sans indicateur tenu égal ni série
  // annuelle, hors régions. Rend la corrélation et la probabilité corrigée publiées, et le nom de la famille.
  var publie = { ic: function (fa) { return fa && fa.lo != null && fa.hi != null ? [fa.lo, fa.hi] : null; } };
  function famille() {
    if (typeof FAM === "undefined" || S.lv === "reg" || S.r || S.traj || (S.zm === "p" && S.z)) return null;
    var a = eff(S.x), b = eff(S.y), k = [a, b].sort(), p;
    // [rho, q, bas et haut de l'intervalle publié (null s'il n'est pas publié), territoires du calcul publié]
    if (S.lv === "dep" && FAM.q[k[0]] && (p = FAM.q[k[0]][k[1]])) return { rho: p[0], q: p[1], lo: p[2], hi: p[3], nt: p[4], n: FAM.n.questions, nom: "questions préparées entre départements" };
    p = FAM.c[S.lv] && FAM.c[S.lv][k[0]] && FAM.c[S.lv][k[0]][k[1]];
    if (!p) return null;
    var pr = IND[a] && IND[a].type === "prof" ? IND[a] : IND[b];
    return { rho: p[0], q: p[1], lo: p[2], hi: p[3], nt: p[4], n: FAM.n["contexte:" + S.lv + ":" + pr.mode], nom: "famille des professions face au profil des habitants, " + NIV_PL[S.lv] + ", " + MODE_TXT[pr.mode] };
  }
  function cle() { return [eff(S.x), eff(S.y), S.lv, S.r, S.zm === "p" ? S.z : "", S.traj ? 1 : 0].join("|"); }
  function noter(st, fa) {
    if (st.trop) return;
    var c = cle(), h = VUS.filter(function (e) { return e.c === c; })[0];
    if (!h) { h = { c: c, s: JSON.parse(JSON.stringify(S)) }; VUS.push(h); }
    h.r = st.r; h.q = fa ? fa.q : null;
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

  // échelle logarithmique de l'axe vertical, celle de départ comme dans Explorer : possible quand aucune valeur montrée
  // n'est négative ; les territoires à 0 sortent alors du dessin (comme dans Explorer), la légende dit combien
  function logPossible(pts) { var d = pts.filter(function (p) { return p.dedans; }); return d.some(function (p) { return p.y > 0; }) && !d.some(function (p) { return p.y < 0 || (p.y0 != null && p.y0 < 0); }); }
  function gradLog(lo, hi) {
    function serie(m) { var o = []; for (var k = Math.floor(Math.log10(lo)) - 1; k <= Math.ceil(Math.log10(hi)); k++) m.forEach(function (x) { var v = x * Math.pow(10, k); if (v >= lo * 0.999 && v <= hi * 1.001) o.push(+v.toPrecision(3)); }); return o; }
    var o = serie([1, 2, 5]); if (o.length > 7) o = serie([1]); if (o.length < 3) o = serie([1, 1.5, 2, 3, 5, 7]); return o;
  }

  // dessin du nuage
  function dessinerNuage(pts, refx, refy) {
    var svg = $("nuage"), W = Math.round(Math.max(320, Math.min(700, svg.parentNode.clientWidth - 24 || 560))), H = Math.round(W < 500 ? W * 0.95 : Math.min(460, W * 0.68)), ml = 52, mr = 14, mt = 14, mb = 52;
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    var lg = S.e === "log" && logPossible(pts);
    var dd = pts.filter(function (p) { return p.dedans; });
    var xs = dd.map(function (p) { return p.x; }).concat(dd.map(function (p) { return p.x0; }).filter(function (v) { return v != null; }));
    var ys = dd.map(function (p) { return p.y; }).concat(dd.map(function (p) { return p.y0; }).filter(function (v) { return v != null; }));
    if (lg) ys = ys.filter(function (v) { return v > 0; });
    if (refx) xs.push(refx.v); if (refy && (!lg || refy.v > 0)) ys.push(refy.v);
    var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs), y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
    var px = (x1 - x0) * 0.05 || 1, py = (y1 - y0) * 0.06 || 1; x0 -= px; x1 += px;
    if (lg) { y0 /= 1.15; y1 *= 1.15; } else { y0 -= py; y1 += py; }
    // Marge gauche à la mesure des graduations, pour que « 25 000 » ne touche jamais le titre de l'axe.
    var gy = lg ? gradLog(y0, y1) : graduations(y0, y1, W < 500 ? 5 : 6);
    ml = Math.max(52, 32 + Math.max.apply(null, gy.map(function (v) { return f(v).length; })) * 6.4) +
      15 * (lignesAxe(court(IND[eff(S.y)]), H - mt - mb).length - 1);
    mb = 52 + 15 * (lignesAxe(court(IND[eff(S.x)]), W - ml - mr).length - 1);
    var l0 = Math.log(y0), l1 = Math.log(y1);
    var sx = function (v) { return ml + (v - x0) / (x1 - x0) * (W - ml - mr); };
    var sy = lg ? function (v) { return H - mb - (Math.log(v) - l0) / (l1 - l0) * (H - mt - mb); } : function (v) { return H - mb - (v - y0) / (y1 - y0) * (H - mt - mb); };
    var vu = function (v) { return v != null && (!lg || v > 0); };
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
    if (refy && vu(refy.v)) s += '<line class="ref" x1="' + ml + '" x2="' + (W - mr) + '" y1="' + sy(refy.v) + '" y2="' + sy(refy.v) + '"/>';
    var tri = pts.slice().sort(function (a, b) { return (b.z != null && S.zm === "t" ? b.z : b.u.pop) - (a.z != null && S.zm === "t" ? a.z : a.u.pop); });
    tri.forEach(function (p) {
      if (S.traj && (p.x0 != null || p.y0 != null) && vu(p.y) && vu(p.y0 != null ? p.y0 : p.y)) s += '<line class="traj" x1="' + sx(p.x0 != null ? p.x0 : p.x) + '" y1="' + sy(p.y0 != null ? p.y0 : p.y) + '" x2="' + sx(p.x) + '" y2="' + sy(p.y) + '"' + (p.dedans ? "" : ' opacity=".08"') + "/>";
    });
    var sig = [], horsLog = 0;
    tri.forEach(function (p) {
      if (!vu(p.y)) { if (p.dedans) horsLog++; return; }
      var t = Z && S.zm === "t" ? p.z : p.u.pop, r = t != null && t > 0 ? Math.max(2.2, Math.sqrt(t / zmax) * rmax) : 2.2;
      var col = zb ? (p.z == null ? jeton("--nodata") : seq(classe(p.z, zb))) : jeton("--r3");
      s += '<circle class="pt' + (p.dedans ? "" : " hors") + (S.sel === p.u.c ? " sel" : "") + '" data-c="' + p.u.c + '" cx="' + sx(p.x).toFixed(1) + '" cy="' + sy(p.y).toFixed(1) + '" r="' + r.toFixed(1) + '" fill="' + col + '" fill-opacity="' + (zb ? 0.95 : 0.7) + '"/>';
      if (signalT(p.u)) sig.push({ x: sx(p.x), y: sy(p.y), r: r });
    });
    // Signal « ! » posé à côté du point, à la première place libre, pour que deux signaux ne se recouvrent jamais.
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
    svg.innerHTML = s;
    // légendes des deux repères en texte de page, au-dessus du dessin, le même libellé sur ordinateur et au téléphone
    // (structure validée le 26 novembre 2026, planche 6) : un court trait en tirets, horizontal ou vertical, puis le nom
    $("leg-reperes").innerHTML = (refy && vu(refy.v) ? '<span><i class="ech-h" aria-hidden="true"></i><span>' + esc(refy.t) + ", trait horizontal</span></span>" : "") +
      (refx ? '<span><i class="ech-v" aria-hidden="true"></i><span>' + esc(refx.t) + ", trait vertical</span></span>" : "");
    var leg = "";
    if (zb) leg = '<span>' + esc(court(Z)) + '</span><span class="seq">' + [0, 1, 2, 3, 4].map(function (k) { return '<i style="background:' + seq(k) + '"></i>'; }).join("") + "</span><span>du cinquième le plus bas au plus haut, de " + f(Math.min.apply(null, zv.filter(function (v) { return v != null; }))) + " à " + f(Math.max.apply(null, zv.filter(function (v) { return v != null; }))) + "</span>";
    else leg = "<span>Taille des points selon " + (Z && S.zm === "t" ? esc(court(Z)) : "la population") + "</span>";
    if (S.traj && (trajSerie(S.x, S.lv) || trajSerie(S.y, S.lv))) leg += '<span>Trait gris, chemin depuis le début de la série</span>';
    if (lg) leg += "<span>Axe vertical en échelle logarithmique" + (horsLog ? ", " + fr0.format(horsLog) + " " + (horsLog > 1 ? NIV_PL[S.lv] : NIV_SING[S.lv]) + " à 0 hors du dessin, compté" + (horsLog > 1 ? "s" : "") + " dans le calcul" : "") + "</span>";
    else if (S.e === "log") leg += "<span>Échelle linéaire : l’axe vertical a des valeurs négatives</span>";
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
  function phrase(st, fa) {
    var ix = IND[eff(S.x)], iy = IND[eff(S.y)], niv = NIV_PL[S.lv];
    if (st.trop) return "Trop peu de " + niv + " ont les deux indicateurs pour mesurer un lien (" + st.n + ").";
    var sens = st.r > 0 ? "plus élevé aussi" : "plus bas", t = force(st.r), eg = st.partiel ? ", en tenant égal l’indicateur « " + low(court(IND[eff(S.z)])) + " »" : "";
    if (S.lv === "reg") return "Entre régions, trop peu de territoires pour dire un lien. La corrélation de rang vaut " + r2(st.r) + eg + ", à lire avec son intervalle.";
    // hors des familles de tests publiées : la corrélation et son intervalle, sans dire s'il y a un lien
    if (!fa) {
      var cond = S.r ? "restreint à " + REGNOM[S.r] : st.partiel ? "en tenant égal l’indicateur « " + low(court(IND[eff(S.z)])) + " »" : S.traj ? "sur la série annuelle du répertoire" : "";
      var suite = " : la corrélation de rang" + (st.partiel ? " partielle" : "") + " (" + r2(st.r) + ") et son intervalle de confiance à 95 % (" + r2(st.ic[0]) + " à " + r2(st.ic[1]) + ") sont donnés, sans dire s’il y a un lien.";
      return cond ? "Ce croisement, " + cond + ", n’appartient à aucune famille de tests publiée" + suite
        : "Les indicateurs « " + low(court(ix)) + " » et « " + low(court(iy)) + " » n’appartiennent à aucune famille de tests publiée" + suite;
    }
    if (!Lien.est(fa.rho, fa.q)) return "Les indicateurs « " + low(court(ix)) + " » et « " + low(court(iy)) + " » ne sont pas liés au-delà du seuil retenu sur tout le site (corrélation de rang " + r2(st.r) + ", lien dit à partir de 0,3 et après correction des tests multiples).";
    return "Dans les " + niv + " où l'indicateur « " + low(court(ix)) + " » est plus élevé, l'indicateur « " + low(court(iy)) + " » tend à être " + sens + ". Le lien est " + t + ".";
  }
  function low(s) { return /^[A-Z]{2}/.test(s) ? s : s.charAt(0).toLowerCase() + s.slice(1); }

  function mesures(st, fa) {
    if (st.trop) { $("mesures").innerHTML = ""; return; }
    var lien = fa ? (Lien.est(fa.rho, fa.q) ? ", lien " + force(fa.rho) : ", sous le seuil du lien") : "";
    $("mesures").innerHTML =
      '<div><span class="n">' + r2(st.r) + '</span><span class="l">corrélation de rang' + (st.partiel ? " partielle" : "") + lien + "</span></div>" +
      '<div><span class="n">' + r2(st.ic[0]) + " à " + r2(st.ic[1]) + '</span><span class="l">intervalle de confiance à 95 %</span></div>' +
      (fa ? '<div><span class="n">' + fp(fa.q) + '</span><span class="l">probabilité corrigée publiée, ' + esc(fa.nom) + " (" + fr0.format(fa.n) + " couples)</span></div>"
          : '<div><span class="n">sans verdict</span><span class="l">' + (S.lv === "reg" ? "entre régions, aucun lien n’est dit" : "ce couple n’appartient à aucune famille de tests publiée") + "</span></div>") +
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
    $("histo").innerHTML = VUS.slice().reverse().map(function (e) {
      var j = VUS.indexOf(e), s = e.s, ix = IND[eff2(s.x, s.m)], iy = IND[eff2(s.y, s.m)];
      return '<li' + (e.c === c ? ' aria-current="true"' : "") + '><button type="button" data-h="' + j + '"><span class="q">' + esc(court(ix)) + " et " + esc(low(court(iy))) + ", " + NIV_PL[s.lv] + (s.r ? ", " + esc(REGNOM[s.r]) : "") + (s.zm === "p" && s.z ? ", en tenant égal « " + esc(low(court(IND[eff2(s.z, s.m)]))) + " »" : "") + '</span><span class="r">' + r2(e.r) + "<br>" + (e.q != null ? "q publiée " + fp(e.q) : "sans verdict") + "</span></button></li>";
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
    function boiteDonnees(t, exp, quoi) {
      return '<p class="cit">' + esc(t).replace(/doi:(\S+?)\.$/, function (m, d) { return 'doi:<a href="https://doi.org/' + d + '">' + d + "</a>."; }) + "</p>" +
        '<div class="citation-actions"><button type="button" data-copier="' + esc(t) + '">Copier la citation</button></div>' +
        '<ul class="exports"><li><span class="nom"><span class="genre">Données</span> ' + quoi + '</span><span class="citation-actions"><button type="button" data-export="' + exp + '">CSV</button></span></li></ul>';
    }
    $("citer-donnees").classList.add("citation-fig"); $("citer-donnees").innerHTML = boiteDonnees(texte("données par territoire"), "csv", "par territoire");
    $("citer-prep").classList.add("citation-fig"); $("citer-prep").innerHTML = boiteDonnees(A.citation + ", Ubi Cura, questions préparées entre départements, version du " + A.version + (A.doi ? ", doi:" + A.doi : "") + ".", "prep-csv", "des questions préparées");
  }

  // état dans l'adresse, pour le lien permanent
  function etat() { return ["x=" + S.x, "y=" + S.y, "z=" + S.z, "zm=" + S.zm, "lv=" + S.lv, "m=" + S.m, "r=" + S.r, "t=" + (S.traj ? 1 : 0), "v=" + S.v, "e=" + S.e, "s=" + (S.sel || "")].join("&"); }
  function lireEtat() {
    var h = location.hash.slice(1); if (!h) return;
    h.split("&").forEach(function (kv) { var p = kv.split("="), k = p[0], v = decodeURIComponent(p[1] || "");
      if (k === "x" || k === "y") { if (IND[v]) S[k] = v; } else if (k === "z") S.z = IND[v] ? v : ""; else if (k === "zm" || k === "m" || k === "r" || k === "v") S[k] = v; else if (k === "e") S.e = v === "lin" ? "lin" : "log"; else if (k === "lv" && A.units[v]) S.lv = v; else if (k === "t") S.traj = v === "1"; else if (k === "s") S.sel = v || null; });
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
    document.querySelectorAll("#echelle button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-ech") === S.e)); });
    document.querySelectorAll("#vue-carte button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-v") === S.v)); });
    $("resume-tel").textContent = court(IND[eff(S.x)]) + " et " + low(court(IND[eff(S.y)])) + ", " + NIV_PL[S.lv];
  }

  function rendre() {
    if (!(dispo(S.x, S.lv) && dispo(S.y, S.lv))) { var lv = ["dep", "reg", "epci"].filter(function (l) { return dispo(S.x, l) && dispo(S.y, l); })[0]; if (lv) S.lv = lv; }
    if (S.lv === "reg") S.r = "";
    if (S.traj && !(trajSerie(S.x, S.lv) || trajSerie(S.y, S.lv))) S.traj = false;
    reglages();
    var pts = points(), st = stats(pts), fa = st.trop ? null : famille();
    // dans une famille publiée, la corrélation, l'intervalle et le nombre de territoires du fichier publié, avec lesquels
    // la règle du lien a été appliquée (publié.ic) ; sinon l'intervalle par la méthode du pipeline (icDe)
    if (fa && fa.rho != null) st.r = fa.rho;
    if (fa && fa.nt != null) st.n = fa.nt;
    if (!st.trop) st.ic = publie.ic(fa) || icDe(st);
    noter(st, fa);
    var rx = reference(S.x, S.lv, valeurs(S.x, S.lv)), ry = reference(S.y, S.lv, valeurs(S.y, S.lv));
    $("titre").textContent = court(IND[eff(S.x)]) + " et " + low(court(IND[eff(S.y)])) + ", par " + NIV_SING[S.lv];
    $("phrase").textContent = phrase(st, fa);
    // quand l'escalier d'Explorer répond à la même question, une ligne dit ce qui les distingue (audit de contrôle du
    // 30 octobre 2026, point I6)
    var esc1 = /^prof:([a-z_]+):all$/.exec(S.y) || /^prof:([a-z_]+):all$/.exec(S.x), autre = esc1 && (S.x === "revenu_median" || S.y === "revenu_median");
    var pe = $("escalier-note");
    if (!pe) { pe = document.createElement("p"); pe.id = "escalier-note"; pe.className = "note-escalier"; $("phrase").after(pe); }
    pe.hidden = !(autre && !st.trop);
    if (autre && !st.trop) pe.innerHTML = "La corrélation dit si l’offre monte régulièrement avec le niveau de vie, d’un territoire à l’autre. L’escalier d’Explorer range les habitants en dix tranches de niveau de vie et compare les tranches entre elles, il peut montrer un écart entre les extrêmes sans lien régulier. <a href=\"explorer.html#iFenEscalier?fam=" + (IND[eff("prof:" + esc1[1] + ":all")] && IND[eff("prof:" + esc1[1] + ":all")].sm ? "sm" : "sante") + "&iProf=" + esc1[1] + "\">Voir l’escalier dans Explorer</a>.";
    PTS = pts;
    mesures(st, fa); limites(); dessinerNuage(pts, rx, ry); dessinerCarte(pts); carteTerr(pts, rx, ry); histo(); tableTerr(); citer();
    $("t-carte").textContent = S.v === "b" ? "Carte des deux indicateurs" : "Carte, " + low(court(IND[eff(S.v === "x" ? S.x : S.y)]));
    try { history.replaceState(null, "", "#" + etat()); } catch (e) {}
    PTS = pts;
  }
  var PTS = [];

  // Données par territoire (repris de la fenêtre « Croiser deux indicateurs » d'Explorer) : une ligne par territoire du
  // croisement, valeurs écrites comme sur les fiches, triables, filtrables, et le tout en CSV par « Citer et exporter »
  // les dix premières lignes dans l'ordre choisi (comme la maquette validée), toutes sur demande ou quand un filtre est
  // écrit : jamais de tableau qui défile dans la page
  var TRI = { k: "nm", asc: true }, TOUT = false, PREMIERES = 10;
  function tableTerr() {
    var ix = IND[eff(S.x)], iy = IND[eff(S.y)], q = norm(($("filtre-terr").value || "").trim());
    var d = PTS.filter(function (p) { return p.dedans; }), n = d.length;
    var val = function (p) { return TRI.k === "nm" ? p.u.nm : TRI.k === "pop" ? p.u.pop : TRI.k === "x" ? p.x : p.y; };
    var rows = d.filter(function (p) { return !q || norm(p.u.nm).indexOf(q) >= 0; }).sort(function (a, b) {
      var u = val(a), v = val(b); return (typeof u === "string" ? u.localeCompare(v, "fr") : u - v) * (TRI.asc ? 1 : -1); });
    var th = function (k, t, u, num) { return '<th scope="col"' + (num ? ' class="num"' : "") + '><button type="button" data-tri="' + k + '" aria-label="Trier par ' + esc(t) + '">' + esc(t) + (TRI.k === k ? (TRI.asc ? " ▲" : " ▼") : "") + (u ? '<span class="u">' + esc(u) + "</span>" : "") + "</button></th>"; };
    $("table-terr").innerHTML = "<thead><tr>" + th("nm", NIV_SING[S.lv].charAt(0).toUpperCase() + NIV_SING[S.lv].slice(1)) + th("pop", "Habitants", "", true) + th("x", court(ix), ix.u, true) + th("y", court(iy), iy.u, true) + "</tr></thead><tbody>" +
      rows.slice(0, TOUT || q ? rows.length : PREMIERES).map(function (p) { return "<tr><td>" + esc(p.u.nm) + '<span class="pop-tel">' + fr0.format(p.u.pop) + " habitants</span>" + '</td><td class="num">' + fr0.format(p.u.pop) + '</td><td class="num">' + esc(fv(S.x, S.lv, p.k, p.x)) + '</td><td class="num">' + esc(fv(S.y, S.lv, p.k, p.y)) + "</td></tr>"; }).join("") + "</tbody>";
    var vus = TOUT || q ? rows.length : Math.min(PREMIERES, rows.length);
    $("note-terr").textContent = (vus < n ? (q ? fr0.format(vus) + " sur " : "Les " + fr0.format(vus) + " premières lignes des ") : "") + fr0.format(n) + " " + (n > 1 ? NIV_PL[S.lv] : NIV_SING[S.lv]) + " du croisement" + (S.r ? ", dans " + REGNOM[S.r] : "") + ". Un clic sur l’en-tête d’une colonne la trie ; le tableau complet se filtre, se montre en entier et se télécharge en CSV par « Citer et exporter ».";
    var b = $("tout-terr"); b.hidden = !!q || rows.length <= PREMIERES; b.textContent = TOUT ? "Montrer les " + PREMIERES + " premières lignes" : "Montrer les " + fr0.format(rows.length) + " lignes";
    b.setAttribute("aria-expanded", String(TOUT));
  }

  // Questions préparées entre départements (croisements.csv, A.cb), le tableau d'Explorer : lien, intervalle de confiance
  // à 95 %, valeur à densité de population égale, nombre de départements. Un nombre négatif porte le signe « − » et les
  // bornes ne se séparent pas (espaces insécables).
  // deux décimales toujours, comme le tableau d'Explorer (« de 0,30 à 0,64 »), signe « − » des nombres négatifs
  var fr2f = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  function nb2(v) { var x = Math.round(v * 100) / 100; return fr2f.format(x === 0 ? 0 : x).replace("-", "−"); }
  function motLien(v, lo, hi) { return lo != null && lo <= 0 && hi >= 0 ? "incertain" : force(v); }
  function chargeable(cb) {
    var ix = IND[cb.x], iy = IND[cb.y]; if (!ix || !iy || ix.type === "venir" || iy.type === "venir") return null;
    var m = ix.type === "prof" ? ix.mode : iy.type === "prof" ? iy.mode : "all";
    if (ix.type === "prof" && iy.type === "prof" && ix.mode !== iy.mode) return null;
    var x = ix.type === "prof" ? "prof:" + ix.prof + ":all" : cb.x, y = iy.type === "prof" ? "prof:" + iy.prof + ":all" : cb.y;
    if (!(IND[x] && IND[y])) return null;
    var lv0 = S.lv, m0 = S.m; S.lv = "dep"; S.m = m; var ok = dispo(x, "dep") && dispo(y, "dep"); S.lv = lv0; S.m = m0;
    return ok ? { x: x, y: y, m: m } : null;
  }
  function questions() {
    var qs = [], h = "";
    A.cb.forEach(function (r) { if (qs.indexOf(r.q) < 0) qs.push(r.q); });
    qs.forEach(function (q) {
      h += '<tr class="cb-titre"><th scope="rowgroup" colspan="5">' + esc(q) + "</th></tr>";
      A.cb.forEach(function (r, k) {
        if (r.q !== q) return;
        var nom = esc(r.lx) + '<span class="et">et ' + esc(low(r.ly)) + "</span>";
        h += "<tr><td>" + (chargeable(r) ? '<button type="button" class="charger" data-cb="' + k + '" aria-label="Charger dans le nuage : ' + esc(r.lx) + " et " + esc(low(r.ly)) + '">' + nom + "</button>" : nom) + "</td>" +
          "<td>" + motLien(r.rho, r.lo, r.hi) + " (" + nb2(r.rho) + ")</td><td>de\u00a0" + nb2(r.lo) + "\u00a0à\u00a0" + nb2(r.hi) + "</td>" +
          "<td>" + (r.rp == null ? "non calculé" : motLien(r.rp, r.lop, r.hip) + " (" + nb2(r.rp) + ")") + '</td><td class="num">' + r.n + "</td></tr>";
      });
    });
    $("table-prep").innerHTML = '<thead><tr><th scope="col">Croisement</th><th scope="col">Lien entre départements</th><th scope="col">Intervalle de confiance à 95\u00a0%</th><th scope="col">À densité de population égale</th><th scope="col" class="num">Départements</th></tr></thead><tbody>' + h + "</tbody>";
  }

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
    if (t.matches("[data-ech]")) { S.e = t.getAttribute("data-ech"); return rendre(); }
    if (t.id === "tout-terr") { TOUT = !TOUT; tableTerr(); return; }
    if (t.matches("[data-tri]")) { var k2 = t.getAttribute("data-tri"); if (TRI.k === k2) TRI.asc = !TRI.asc; else { TRI.k = k2; TRI.asc = k2 === "nm"; } tableTerr(); return; }
    if (t.matches("[data-cb]")) { var cb = A.cb[+t.getAttribute("data-cb")], ch = chargeable(cb); if (!ch) return; S.x = ch.x; S.y = ch.y; S.m = ch.m; S.lv = "dep"; S.z = ""; S.zm = "t"; S.r = ""; S.traj = false; S.sel = null; rendre(); $("titre").scrollIntoView({ block: "start" }); return; }
    if (t.matches("[data-h]")) { var e = VUS[+t.getAttribute("data-h")]; var sel = S.sel; Object.assign(S, JSON.parse(JSON.stringify(e.s))); S.sel = sel; return rendre(); }
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
  $("filtre-terr").addEventListener("input", tableTerr);
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
      var l = ["code;territoire;habitants;" + ix.lab + ";" + iy.lab];
      PTS.filter(function (p) { return p.dedans; }).forEach(function (p) { l.push(p.u.c + ";" + p.u.nm + ";" + p.u.pop + ";" + String(p.x).replace(".", ",") + ";" + String(p.y).replace(".", ",")); });
      telecharger(new Blob(["﻿" + l.join("\n")], { type: "text/csv" }), "croisement.csv");
    } else if (k === "prep-csv") {
      var lq = ["question;indicateur_1;indicateur_2;rho;ic95_bas;ic95_haut;rho_a_densite_egale;ic95_bas_a_densite_egale;ic95_haut_a_densite_egale;departements"];
      var c = function (v) { return v == null ? "" : String(v).replace(".", ","); }, g = function (s) { return '"' + String(s).replace(/"/g, '""') + '"'; };
      A.cb.forEach(function (r) { lq.push([g(r.q), g(r.lx), g(r.ly), c(r.rho), c(r.lo), c(r.hi), c(r.rp), c(r.lop), c(r.hip), r.n].join(";")); });
      telecharger(new Blob(["\ufeff" + lq.join("\n") + "\n# Source, " + A.citation + ", Ubi Cura, version du " + A.version + (A.doi ? ", doi:" + A.doi : "") + "\n"], { type: "text/csv" }), "questions_preparees.csv");
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
  pistes("pistes", QUESTIONS); pistes("pistes2", INATTENDUS); questions();
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
