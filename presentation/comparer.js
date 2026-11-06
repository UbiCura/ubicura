// Comparateur de deux à quatre territoires (présentation du 30 octobre 2026), tiré de la maquette validée. Données de
// l'atelier (const A), recherche du site. Valeur, repère, position, couleur et statut lus dans A.aff (pipeline/affichage.py).
(function () {
  var $ = function (i) { return document.getElementById(i); };
  // nombres écrits par presentation/chiffres.js, comme sur les fiches (pipeline/affichage.py)
  var fr0 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  var IND = {}; A.ind.forEach(function (i) { IND[i.id] = i; });
  var NIVPL = { reg: "régions", dep: "départements", epci: "intercommunalités" }, NIV1 = { reg: "Région", dep: "Département", epci: "Intercommunalité" };
  var LIGNES = [
    ["Santé mentale", [["prof:psychologue:all", "Psychologues", "pour 10 000 habitants"], ["prof:psychiatre:all", "Psychiatres", "pour 10 000 habitants"], ["prof:q_psychiatrie_enfant:all", "Psychiatres qualifiés pour l'enfant", "pour 10 000 habitants"],
      ["lieux_lieu_cmp_adultes", "CMP pour adultes", "pour 100 000 habitants"], ["lieux_lieu_cmp_enfants", "CMP pour enfants", "pour 100 000 moins de 15 ans"], ["lieux_lieu_cattp", "CATTP", "pour 100 000 habitants"], ["lieux_lieu_cmpp", "CMPP", "pour 100 000 moins de 15 ans"], ["lieux_lieu_csapa", "CSAPA", "pour 100 000 habitants"],
      ["dist_lieu_cmp_adultes", "Distance au CMP pour adultes", "km, médiane des habitants"]]],
    ["Offre de soins en santé", [["prof:medecin_generaliste:all", "Médecins généralistes", "pour 10 000 habitants"], ["prof:infirmier:all", "Infirmiers", "pour 10 000 habitants"], ["prof:masseur_kinesitherapeute:all", "Masseurs-kinésithérapeutes", "pour 10 000 habitants"], ["prof:sage_femme:all", "Sages-femmes", "pour 10 000 habitants"], ["dist_lieu_urgences", "Distance au service d'urgences", "km, médiane des habitants"]]],
    ["Revenus, emploi et pauvreté", [["revenu_median", "Niveau de vie médian", "euros par an"], ["taux_pauvrete", "Taux de pauvreté", "%"], ["taux_chomage", "Taux de chômage des 15-64 ans", "%"]]],
    ["Enfance, éducation et familles", [["part_monoparentales", "Familles monoparentales", "%"]]],
    ["Population et logement", [["densite_pop", "Densité de population", "habitants par km²"], ["part_0_14", "Moins de 15 ans", "%"], ["part_80p", "80 ans et plus", "%"], ["part_80p_seuls", "80 ans et plus vivant seuls", "%"]]]
  ];
  // libellés et unités du catalogue pour les indicateurs du profil, les mêmes que sur toutes les pages (audit de
  // contrôle du 30 octobre 2026, point I3)
  LIGNES.forEach(function (g) { g[1].forEach(function (l) { var i = IND[l[0]]; if (i && i.type === "ctx" && !/^(lieux_|dist_)/.test(l[0])) { l[1] = i.lab; if (i.u) l[2] = i.u; } else if (i && i.type === "prof" && i.u) l[2] = i.u; }); });
  var S = { t: [] };
  function unite(lv, c) { var us = A.units[lv]; for (var k = 0; k < us.length; k++) if (us[k].c === c) return k; return -1; }
  function valeur(id, lv, k) { var a = A.val[lv][id]; return a ? a[k] : undefined; }
  function compte(id, lv, k) { var cle = id.indexOf("prof:") === 0 ? id.replace(/:all$/, "") : id.replace(/^lieux_/, ""); var a = A.n && A.n[lv] && A.n[lv][cle]; return a ? a[k] : null; }
  // valeur, repère, position, couleur et statut lus dans les données publiées par pipeline/affichage.py (A.aff), écrits
  // par presentation/chiffres.js ; pour une intercommunalité, l'indicateur publié seulement au département se lit sur
  // son département comparé aux départements, avec le statut « donnée du département »
  function cel(id, lv, k) {
    var v = valeur(id, lv, k), lv2 = lv, k2 = k;
    if (v === undefined && lv === "epci" && A.units.epci[k].p) { lv2 = "dep"; k2 = unite("dep", A.units.epci[k].p); v = k2 >= 0 ? valeur(id, "dep", k2) : undefined; }
    if (v === undefined) return null;
    var c = Chiffres.cellule(A, id, lv2, k2, v); if (!c) return null;
    if (lv2 !== lv && !/[aprnd]/.test(c.code)) c.statut = A.aff.statuts.D + (c.statut ? ", " + c.statut : "");
    c.lv = lv2; c.k = k2; return c;
  }
  var MOT_TYPE = { "lieu_cmp_adultes": "CMP pour adultes", "lieu_cmp_enfants": "CMP pour enfants", "lieu_cattp": "CATTP", "lieu_hdj_psy_enfants": "jour en psychiatrie pour enfants", "lieu_hdj_psy_adultes": "jour en psychiatrie pour adultes" };
  function concerne(id, t) { var m = /(?:lieux_|dist_)(lieu_\w+)/.exec(id); if (!m || !MOT_TYPE[m[1]] || !t) return true; return t.indexOf(MOT_TYPE[m[1]]) >= 0; }
  function limTerr(i, lv, u, id) { if (!i || !i.limT) return null; var t = lv === "reg" ? i.limT["reg:" + u.c] : (i.limT[u.c] || (lv === "epci" && u.p ? i.limT[u.p] : null)); return t && concerne(id, t) ? t : null; }
  function semblables(lv, k) {
    var crit = ["densite_pop", "revenu_median", "part_80p"], us = A.units[lv];
    var st = crit.map(function (id) { var a = A.val[lv][id].filter(function (v) { return v != null; }), mu = a.reduce(function (x, y) { return x + y; }, 0) / a.length, sd = Math.sqrt(a.reduce(function (x, y) { return x + (y - mu) * (y - mu); }, 0) / a.length); return { id: id, mu: mu, sd: sd || 1 }; });
    function vec(j) { return st.map(function (s) { var v = A.val[lv][s.id][j]; return v == null ? null : (s.id === "densite_pop" ? Math.log(v + 1) : v); }); }
    var stl = st.map(function (s) { if (s.id !== "densite_pop") return s; var a = A.val[lv][s.id].filter(function (v) { return v != null; }).map(function (v) { return Math.log(v + 1); }), mu = a.reduce(function (x, y) { return x + y; }, 0) / a.length; return { id: s.id, mu: mu, sd: Math.sqrt(a.reduce(function (x, y) { return x + (y - mu) * (y - mu); }, 0) / a.length) }; });
    var v0 = vec(k); if (v0.some(function (x) { return x == null; })) return [];
    var d = []; us.forEach(function (u, j) { if (j === k) return; var v = vec(j); if (v.some(function (x) { return x == null; })) return; var s = 0; v.forEach(function (x, q) { var z = (x - v0[q]) / stl[q].sd; s += z * z; }); d.push([s, j]); });
    d.sort(function (a, b) { return a[0] - b[0]; });
    return d.slice(0, 3).map(function (x) { return { t: lv, c: us[x[1]].c, nm: us[x[1]].nm }; });
  }
  function etat() { return "t=" + S.t.map(function (x) { return x.t + ":" + x.c; }).join(","); }
  function lire() {
    var h = location.hash.slice(1), m = /(?:^|&)t=([^&]*)/.exec(h);
    if (m) S.t = m[1].split(",").map(function (s) { var p = s.split(":"), k = unite(p[0], p[1]); return k >= 0 ? { t: p[0], c: p[1], nm: A.units[p[0]][k].nm } : null; }).filter(Boolean).slice(0, 4);
  }
  function rendre() {
    history.replaceState(null, "", "#" + etat());
    $("puces").innerHTML = S.t.map(function (x, j) { return '<span class="puce">' + esc(x.nm) + ' <button type="button" data-retirer="' + j + '" aria-label="Retirer ' + esc(x.nm) + '">×</button></span>'; }).join("");
    var p = S.t[0], sb = p ? semblables(p.t, unite(p.t, p.c)) : [];
    $("semblables").innerHTML = sb.length && S.t.length < 4 ? "Territoires semblables à " + esc(p.nm) + ", " + sb.map(function (x) { return '<button type="button" data-ajout="' + x.t + ":" + x.c + '">' + esc(x.nm) + "</button>"; }).join("") : "";
    // outils cachés tant que le tableau est vide (F11)
    document.querySelector(".outils-c").hidden = !S.t.length;
    if (!S.t.length) { $("defile").innerHTML = '<p class="vide-comp">Ajoutez un premier territoire avec le champ ci-dessus, par exemple votre commune.</p>'; $("leg-comp").textContent = ""; $("notes").innerHTML = ""; return; }
    var notes = {};
    $("leg-comp").textContent = "Comparaison de " + S.t.length + " territoire" + (S.t.length > 1 ? "s" : "") + ", version du " + A.version;
    var h = '<table class="comp" aria-labelledby="leg-comp"><thead><tr><th scope="col">Indicateur</th>' +
      S.t.map(function (x) { var k = unite(x.t, x.c), u = A.units[x.t][k]; return '<th scope="col"><a href="territoire/' + x.t + "/" + encodeURIComponent(x.c) + '.html">' + esc(x.nm) + '</a><span class="niv">' + NIV1[x.t] + ", " + fr0.format(u.pop) + " habitants</span></th>"; }).join("") + "</tr></thead><tbody>";
    LIGNES.forEach(function (g) {
      h += '<tr class="groupe"><th scope="row" colspan="' + (S.t.length + 1) + '"><span class="g">' + g[0] + "</span></th></tr>";
      g[1].forEach(function (l) {
        var id = l[0], i = IND[id];
        h += '<tr><th scope="row">' + esc(l[1]) + '<span class="u">' + esc(l[2]) + "</span></th>";
        S.t.forEach(function (x) {
          var k = unite(x.t, x.c), u = A.units[x.t][k], lim = limTerr(i, x.t, u, id), c = cel(id, x.t, k);
          if (!c) { h += '<td><span class="np">non publié à ce niveau</span></td>'; return; }
          var n = compte(id, c.lv, c.k), np = i && i.np && i.np[c.lv] && i.np[c.lv][A.units[c.lv][c.k].c];
          if (lim) notes[x.nm + "|" + lim] = [x.nm, lim];
          var sig = lim ? '<b class="sig" title="' + esc(lim) + '" aria-label="Limite, ' + esc(lim) + '">!</b>' : "";
          var st = c.statut || (c.txt ? "" : np || "sans donnée");
          // un 0 n'est jamais laissé seul : sans structure ni professionnel, « aucune » ou « aucun », comme la fiche
          // (relecture indépendante du 5 novembre 2026, CMPP de l'Ain)
          var zero = n === 0 && c.lv === x.t && /^0([,.]0+)?$/.test(String(c.txt || "").trim());
          if (zero) { c = Object.assign({}, c, {txt: id.indexOf("prof:") === 0 ? "aucun" : "aucune", couleur: null}); n = null; }
          h += "<td>" + (c.txt ? '<span class="v' + (c.couleur ? " ecart-" + c.couleur : "") + '">' + c.txt + "</span>" : "") + (c.txt ? sig : "") +
            (n != null && c.lv === x.t ? '<span class="eff">' + fr0.format(n) + (id.indexOf("prof:") === 0 ? " professionnel" + (n > 1 ? "s" : "") : " structure" + (n > 1 ? "s" : "")) + "</span>" : "") +
            (st ? '<span class="np">' + esc(st) + (c.txt ? "" : sig) + "</span>" : "") +
            (c.ref_txt ? '<span class="rep">' + esc(c.ref_lib) + ", " + c.ref_txt + "</span>" : "") +
            (c.pos_txt && !/[aprn]/.test(c.code) ? '<span class="rep">' + esc(c.pos_txt) + "</span>" : "") + "</td>";
        });
        h += "</tr>";
      });
    });
    $("defile").innerHTML = h + "</tbody></table>";
    var ks = Object.keys(notes);
    $("notes").innerHTML = ks.map(function (k) { return '<p class="limite"><b aria-hidden="true">!</b><span><strong>' + esc(notes[k][0]) + "</strong>, " + esc(notes[k][1]) + "</span></p>"; }).join("");
  }
  document.addEventListener("click", function (e) {
    var t = e.target;
    if (t.matches("[data-retirer]")) { S.t.splice(+t.getAttribute("data-retirer"), 1); rendre(); }
    if (t.matches("[data-ajout]")) { var p = t.getAttribute("data-ajout").split(":"), k = unite(p[0], p[1]); if (S.t.length < 4) S.t.push({ t: p[0], c: p[1], nm: A.units[p[0]][k].nm }); rendre(); }
  });
  $("copier").addEventListener("click", function () { var u = location.href; try { navigator.clipboard.writeText(u); } catch (e) {} $("lien").textContent = "Lien copié, " + u; });
  $("csv").addEventListener("click", function () {
    var lignes = [["indicateur", "unite"].concat([].concat.apply([], S.t.map(function (x) { return [x.nm, x.nm + ", statut", x.nm + ", repère"]; }))).join(";")];
    LIGNES.forEach(function (g) { g[1].forEach(function (l) { lignes.push([l[1], l[2]].concat([].concat.apply([], S.t.map(function (x) { var c = cel(l[0], x.t, unite(x.t, x.c)); return c ? [c.txt.replace(/ /g, ""), c.statut, c.ref_txt ? c.ref_lib + " " + c.ref_txt.replace(/ /g, "") : ""] : ["", "non publié à ce niveau", ""]; }))).join(";")); }); });
    var b = new Blob(["\ufeff" + lignes.join("\n") + "\n# Source, " + A.citation + ", Ubi Cura, version du " + A.version + (A.doi ? ", doi:" + A.doi : "") + "\n"], { type: "text/csv" });
    var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "comparaison_ubicura.csv"; a.click();
  });
  Recherche.brancher($("q"), $("sugg"), $("msg"), "", function (cible) {
    if (!cible) { $("msg").textContent = "Cette commune n'a pas d'intercommunalité dans le référentiel."; return; }
    $("q").value = "";
    if (S.t.some(function (x) { return x.t === cible.t && x.c === cible.c; })) { $("msg").textContent = cible.nm + " est déjà dans la comparaison."; return; }
    if (unite(cible.t, cible.c) < 0) { $("msg").textContent = "Les comparaisons entre territoires écartent " + cible.nm + ", faute de données comparables. Sa fiche reste ouverte."; return; }
    if (S.t.length >= 4) { $("msg").textContent = "Quatre territoires au plus. Retirez-en un pour en ajouter un autre."; return; }
    S.t.push({ t: cible.t, c: cible.c, nm: cible.nm });
    if (cible.commune) $("msg").textContent = cible.commune.nm + " fait partie de " + cible.nm + ", ajoutée à la comparaison, la commune seule étant trop petite pour la plupart des professions.";
    rendre();
  });
  lire(); rendre();
})();

