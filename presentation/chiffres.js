// Écriture des chiffres dans les pages en JavaScript (comparateur, Croiser), la même que pipeline/affichage.py : les
// valeurs, repères, médianes, positions, couleurs et statuts sont calculés une fois en Python et publiés dans les
// données de l'atelier (A.aff) ; ce fichier ne fait que les écrire, avec les mêmes décimales et les mêmes mots.
// Arrondi au plus proche, une demie vers le haut, comme Intl.NumberFormat (halfExpand) et decimal.ROUND_HALF_UP.
var Chiffres = (function () {
  var F = {};
  function nf(d) { return F[d] || (F[d] = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d })); }
  function num(s) { return Number(s.replace(/\s/g, "").replace(/ /g, "").replace(",", ".").replace("−", "-")); }
  // décimales d'une valeur selon son genre (taux, part, distance, euros, entier), décidées sur la valeur arrondie
  function decimales(v, g) {
    if (g === "entier" || g === "euros" || g === "minutes") return 0;
    if (g === "distance" || g === "part") return 1;
    if (Math.abs(num(nf(2).format(v))) < 1) return 2;
    return Math.abs(num(nf(1).format(v))) >= 1000 ? 0 : 1;
  }
  function ar(v, g) {
    if (v == null) return null;
    if (g === "euros") { var x = Math.abs(v) / 10; return (v < 0 ? -1 : 1) * num(nf(0).format(x)) * 10; }
    var r = num(nf(decimales(v, g)).format(v)); return r === 0 ? 0 : r;
  }
  function fmt(v, g) {
    var r = ar(v, g); if (r == null) return "";
    var d = r === 0 ? 0 : decimales(r, g);
    return (r < 0 ? "−" : "") + nf(d).format(Math.abs(r)).replace(/[\u00a0 ]/g, "\u202f");
  }
  function ecart(va, ra) {
    if (va == null || !ra) return null; var e = va / ra - 1, p = e * 100, q = (p < 0 ? -1 : 1) * Math.round(Math.abs(p));
    return { e: e, t: (q > 0 ? "+" : q < 0 ? "−" : "") + Math.abs(q) + "\u202f%" };
  }
  // A.aff[lv][id] : r repère, t sa nature, m médiane, c une lettre par territoire (statut ou couleur), p positions,
  // x valeurs dont l'arrondi des données de l'atelier différerait de celui de la page
  function cellule(A, id, lv, k, v) {
    var a = A.aff && A.aff.lv[lv] && A.aff.lv[lv][id], i = A.aff.ind[id] || {}, g = i.g || "taux";
    if (!a) return null;
    var code = a.c.charAt(k), st = A.aff.statuts[code] || "", coul = code === "h" ? "haut" : code === "b" ? "bas" : "";
    if (code === "a" && i.k === "lieux") st = A.aff.aucune;
    var x = code === "r" ? null : a.x && a.x[k] != null ? a.x[k] : v, va = ar(x, g), sansEcart = /[aprn]/.test(code) || i.k === "dist";
    var e = sansEcart ? null : ecart(x, a.r);   // valeurs pleines, comme pipeline/affichage.py
    if (va === 0 && !st && A.aff.zero[i.k]) st = A.aff.zero[i.k];
    return { v: va, txt: fmt(x, g), statut: st, code: code, couleur: coul, ref: a.r, ref_txt: fmt(a.r, g),
      ref_lib: (a.t === "mediane_territoires" ? A.aff.mediane : A.aff.ensemble)[lv], med_txt: fmt(a.m, g),
      pos: a.p[k], pos_txt: posTxt(a.q ? a.q[k] : a.p[k], i.k, lv, A), ecart: e };
  }
  // position \u00e9crite comme pipeline/affichage.position_txt, \u00e0 partir du nombre publi\u00e9 (position_code) : n \u00ab plus haut que
  // n % \u00bb, \u2212n \u00ab plus bas que n % \u00bb, \u00b1100 \u00ab tous les autres \u00bb ; \u00ab plus loin \u00bb, \u00ab plus pr\u00e8s \u00bb pour une distance
  function posTxt(q, kind, lv, A) {
    if (q == null) return "";
    var bas = q < 0, mot = kind === "dist" ? (bas ? "plus pr\u00e8s que " : "plus loin que ") : (bas ? "plus bas que " : "plus haut que ");
    if (Math.abs(q) === 100) return mot + (lv === "dep" ? "tous les autres " : "toutes les autres ") + A.aff.pluriel[lv];
    return mot + Math.abs(q) + "\u202f% des " + A.aff.pluriel[lv];
  }
  return { decimales: decimales, ar: ar, fmt: fmt, ecart: ecart, cellule: cellule };
})();
