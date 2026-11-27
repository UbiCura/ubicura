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
  // territoires semblables, par la définition unique du site (pipeline/semblables.py, publiée dans A.semb) : sept
  // mesures de l'INSEE, les cinq plus proches du même niveau, hors outre-mer ; leur critère en clair dans A.sembCrit
  function semblables(lv, k) {
    var u = A.units[lv][k], l = (A.semb && A.semb[lv] && u && A.semb[lv][u.c]) || [];
    return l.map(function (c) { var j = unite(lv, c); return j >= 0 ? { t: lv, c: c, nm: A.units[lv][j].nm } : null; }).filter(Boolean);
  }
  function etat() { return "t=" + S.t.map(function (x) { return x.t + ":" + x.c; }).join(","); }
  function lire() {
    var h = location.hash.slice(1), m = /(?:^|&)t=([^&]*)/.exec(h);
    if (m) S.t = m[1].split(",").map(function (s) { var p = s.split(":"), k = unite(p[0], p[1]); return k >= 0 ? { t: p[0], c: p[1], nm: A.units[p[0]][k].nm } : null; }).filter(Boolean).slice(0, 4);
  }
  // réglette du site (gabarits/reglette.html, même histogramme, même repère et même médiane, publiés par
  // pipeline/atelier.py dans A.rg) où les territoires comparés sont placés sous l'axe, chacun sur sa rangée, dans l'ordre
  // de la légende (rond plein, losange, carré, rond creux), au-dessus du triangle de la médiane : deux valeurs égales
  // restent visibles et aucune marque ne touche les barres, le trait du repère, arrêté à l'axe, ni le triangle.
  // avecRep, le repère écrit sur la réglette (téléphone, niveaux différents) ; sinon il est dans sa colonne.
  var NB = " ", RANGEE = 18;
  function cote(x) { return x < 14 ? "g" : x > 86 ? "d" : "c"; }
  function reglette(id, lv, pts, avecRep) {
    var R = A.rg && A.rg[lv] && A.rg[lv][id]; if (!R) return "";
    var X = function (v) { return +Math.max(0, Math.min(100, (v - R.b) / (R.h - R.b || 1) * 100)).toFixed(2); };
    var marques = pts.filter(function (p) { return p.v != null; }), n = Math.max(1, marques.length);
    var med = 50 + RANGEE * n - 2, lab = med + 10, mots = [];
    var s = '<span class="rg-piste" aria-hidden="true"><svg class="rg-hist" viewBox="0 0 ' + R.nb + ' 18" preserveAspectRatio="none" aria-hidden="true"><path d="' + R.c + '"/></svg><span class="rg-axe"></span>' + (R.k ? '<span class="rg-chev"></span>' : "");
    if (R.r != null) {
      s += '<span class="rg-ens" style="left:' + R.r + '%"></span>' + (avecRep ? '<span class="rg-lab haut lab-' + cote(R.r) + '" style="left:' + R.r + '%">ensemble ' + R.rt + "</span>" : "");
      mots.push(A.aff.ensemble[lv].toLowerCase() + " " + R.rt);
    }
    // la part des territoires sans inscrit, sur sa propre ligne sous l'étiquette de la médiane : elle ne touche jamais
    // l'étiquette du repère, quelle que soit la largeur (contrôle de mise en page du 26 novembre 2026)
    var bas = R.al ? 17 : 0;
    if (R.m != null) {
      s += '<span class="rg-med" style="left:' + R.m + "%;top:" + med + 'px"></span><span class="rg-lab bas lab-' + cote(R.m) + '" style="left:' + R.m + "%;top:" + lab + 'px">médiane ' + R.mt + "</span>" +
        (R.al ? '<span class="rg-lab bas lab-g rg-sans" style="left:0%;top:' + (lab + bas) + 'px">' + R.al + "</span>" : "");
      mots.push("médiane " + R.mt.replace(/^: /, ""));
    }
    marques.forEach(function (p, r) { s += '<span class="rg-pt t' + p.j + '" style="left:' + X(p.v) + "%;top:" + (50 + RANGEE * r) + 'px"></span>'; mots.push(p.nm + " " + p.txt); });
    return '<div class="fiche"><div class="rg petite cmp" style="height:' + (lab + 12 + (bas || 0)) + 'px" role="img" tabindex="0" aria-label="Répartition des ' + NIVPL[lv] + " ; " + esc(mots.join(" ; ")) + " ; " + esc(R.ax) + '">' + s + "</span></div></div>";
  }
  function marque(j) { return '<i class="m t' + j + '" aria-hidden="true"></i>'; }
  // contenu d'une cellule : valeur (« aucun inscrit » plutôt que 0), effectif, statut, position ; court, sans le niveau
  function contenu(id, x, c, i, notes, court) {
    var k = unite(x.t, x.c), u = A.units[x.t][k], lim = limTerr(i, x.t, u, id);
    if (!c) return '<span class="np">non publié à ce niveau</span>';
    var n = compte(id, c.lv, c.k), np = i && i.np && i.np[c.lv] && i.np[c.lv][A.units[c.lv][c.k].c];
    if (lim) notes[x.nm + "|" + lim] = [x.nm, lim];
    var sig = lim ? '<b class="sig" title="' + esc(lim) + '" aria-label="Limite, ' + esc(lim) + '">!</b>' : "";
    var txt = c.txt, coul = c.couleur, st = c.statut || (c.txt ? "" : np || "sans donnée");
    // un 0 n'est jamais laissé seul : « aucun inscrit », « aucune structure », comme la fiche (relecture indépendante
    // du 5 novembre 2026, CMPP de l'Ain ; structure validée le 26 novembre 2026)
    var mot = id.indexOf("prof:") === 0 ? "aucun inscrit" : "aucune structure";
    if (c.code === "a" || (n === 0 && c.lv === x.t && /^0([,.]0+)?$/.test(String(txt || "").trim()))) { txt = mot; coul = null; n = null; if (st === mot || c.code === "a") st = ""; }
    var pos = c.pos_txt && !/[aprn]/.test(c.code) ? c.pos_txt : "";
    if (court) pos = pos.replace(/ des (intercommunalités|départements|régions)$/, "");
    return (txt ? '<span class="v' + (coul ? " ecart-" + coul : "") + '">' + txt + "</span>" + sig : "") +
      (n != null && c.lv === x.t ? '<span class="eff">' + fr0.format(n) + (id.indexOf("prof:") === 0 ? " professionnel" + (n > 1 ? "s" : "") : " structure" + (n > 1 ? "s" : "")) + "</span>" : "") +
      (st ? '<span class="np">' + esc(st) + (txt ? "" : sig) + "</span>" : "") + (pos ? '<span class="rep">' + esc(pos) + "</span>" : "");
  }
  function rendre() {
    history.replaceState(null, "", "#" + etat());
    $("puces").innerHTML = S.t.map(function (x, j) { return '<span class="puce">' + marque(j + 1) + esc(x.nm) + ' <button type="button" data-retirer="' + j + '" aria-label="Retirer ' + esc(x.nm) + '">×</button></span>'; }).join("");
    var p = S.t[0], sb = p ? semblables(p.t, unite(p.t, p.c)) : [];
    $("semblables").innerHTML = sb.length && S.t.length < 4 ? "Territoires semblables à " + esc(p.nm) + NB + ": " + sb.map(function (x) { return '<button type="button" data-ajout="' + x.t + ":" + x.c + '">' + esc(x.nm) + "</button>"; }).join("") +
      '<span class="critere">' + esc((A.sembCrit || {})[p.t] || "") + "</span>" : "";
    // outils cachés tant que le tableau est vide (F11)
    document.querySelector(".outils-c").hidden = !S.t.length;
    if (!S.t.length) { $("defile").innerHTML = '<p class="vide-comp">Ajoutez un premier territoire avec le champ ci-dessus, par exemple votre commune.</p>'; $("leg-comp").textContent = ""; $("notes").innerHTML = ""; return; }
    var notes = {}, T = S.t.map(function (x, j) { var k = unite(x.t, x.c); return { t: x.t, c: x.c, nm: x.nm, k: k, j: j + 1, pop: A.units[x.t][k].pop }; });
    var lv = T[0].t, meme = T.every(function (x) { return x.t === lv; }), ENS = A.aff.ensemble[lv];
    $("leg-comp").innerHTML = "Comparaison de " + T.length + " territoire" + (T.length > 1 ? "s" : "") + ", version du " + A.version +
      '<span class="leg-pts">' + T.map(function (x) { return "<span>" + marque(x.j) + esc(x.nm) + "</span>"; }).join("") + "</span>" +
      '<span class="leg-rg">' + (meme ? "Sur chaque réglette, la répartition des " + NIVPL[lv] + ", le trait de l’" + ENS.charAt(0).toLowerCase() + ENS.slice(1) + " et le triangle de la médiane" + NB + "; sous l’axe, chaque territoire sur sa rangée, dans l’ordre de la légende. La position se lit parmi les " + NIVPL[lv] + "."
        : "Les territoires ne sont pas tous du même niveau" + NB + ": chacun est placé sur la réglette de son niveau, avec le repère de ce niveau, et sa position se lit parmi les territoires de ce niveau.") + "</span>";
    var ncol = T.length + 1 + (meme ? 2 : 0);
    var h = '<table class="comp cmp2' + (meme ? "" : " mixte") + " n" + T.length + '" aria-labelledby="leg-comp"><thead><tr><th scope="col">Indicateur</th>' +
      T.map(function (x) { return '<th scope="col" class="terr"><span class="nm">' + marque(x.j) + '<a href="territoire/' + x.t + "/" + encodeURIComponent(x.c) + '.html">' + esc(x.nm) + '</a></span><span class="niv">' + NIV1[x.t] + ", " + fr0.format(x.pop) + " habitants</span></th>"; }).join("") +
      (meme ? '<th scope="col" class="rep-col">Repère<span class="niv">' + esc(ENS) + '</span></th><th scope="col" class="rg-col">Répartition des ' + NIVPL[lv] + "</th>" : "") + "</tr></thead><tbody>";
    var cartes = "";
    LIGNES.forEach(function (g) {
      h += '<tr class="groupe"><th scope="row" colspan="' + ncol + '"><span class="g">' + g[0] + "</span></th></tr>";
      cartes += '<h3 class="carte-g">' + g[0] + "</h3>";
      g[1].forEach(function (l) {
        var id = l[0], i = IND[id], cs = T.map(function (x) { return cel(id, x.t, x.k); });
        var tete = '<th scope="row">' + esc(l[1]) + '<span class="u">' + esc(l[2]) + "</span></th>", titre = '<p class="ci-t">' + esc(l[1]) + ' <span class="u">' + esc(l[2]) + "</span></p>";
        // une réglette commune quand les valeurs se lisent toutes au même niveau (donnée du département comprise)
        var niv = cs.filter(Boolean).map(function (c) { return c.lv; }), lvR = niv.length && niv.every(function (v) { return v === niv[0]; }) ? niv[0] : null;
        var pts = function (js) { return js.map(function (j) { var c = cs[j]; return { v: c ? c.v : null, j: T[j].j, nm: T[j].nm, txt: c ? (c.code === "a" ? "aucun" : c.txt) : "" }; }); };
        if (meme) {
          var c0 = cs.filter(Boolean)[0], tous = T.map(function (x, j) { return j; });
          var rep = c0 && c0.ref_txt ? '<span class="v rep-v">' + c0.ref_txt + "</span>" + (c0.ref_lib !== ENS ? '<span class="rep">' + esc(c0.ref_lib) + "</span>" : "") : "";
          var rg = lvR ? reglette(id, lvR, pts(tous), false) : "";
          h += "<tr>" + tete + cs.map(function (c, j) { return "<td>" + contenu(id, T[j], c, i, notes) + "</td>"; }).join("") + '<td class="rep-col">' + rep + '</td><td class="rg-col">' + rg + "</td></tr>";
          cartes += '<div class="carte-i">' + titre + (lvR ? reglette(id, lvR, pts(tous), true) : "") + (c0 && c0.ref_txt && (!lvR || !(A.rg[lvR] && A.rg[lvR][id] && A.rg[lvR][id].r != null)) ? '<p class="ci-rep">Repère' + NB + ": " + esc(c0.ref_lib.toLowerCase()) + ", " + c0.ref_txt + "</p>" : "") +
            '<div class="ci-v">' + cs.map(function (c, j) { return "<div>" + marque(T[j].j) + contenu(id, T[j], c, i, notes, true) + "</div>"; }).join("") + "</div></div>";
        } else {
          var une = function (c, j) { return c ? reglette(id, c.lv, pts([j]), true) : ""; };
          h += "<tr>" + tete + cs.map(function (c, j) { return "<td>" + contenu(id, T[j], c, i, notes) + une(c, j) + "</td>"; }).join("") + "</tr>";
          cartes += '<div class="carte-i">' + titre + cs.map(function (c, j) { return '<div class="ci-m"><div class="ci-v1">' + marque(T[j].j) + contenu(id, T[j], c, i, notes) + "</div>" + une(c, j) + "</div>"; }).join("") + "</div>";
        }
      });
    });
    $("defile").innerHTML = h + '</tbody></table><div class="cartes-tel">' + cartes + "</div>";
    var ks = Object.keys(notes);
    $("notes").innerHTML = ks.map(function (k) { return '<p class="limite"><b aria-hidden="true">!</b><span><strong>' + esc(notes[k][0]) + "</strong>, " + esc(notes[k][1]) + "</span></p>"; }).join("");
    // étiquettes gardées dans leur réglette, part des territoires sans inscrit placée comme sur la fiche (figures.js)
    if (window.etiquettesReglettes) requestAnimationFrame(window.etiquettesReglettes);
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
    if (cible.commune) $("msg").textContent = cible.commune.nm + " fait partie de " + cible.nm + ", ajoutée à la comparaison" +
      ((cible.commune.pop || 0) > 100000 ? ", les chiffres étant publiés pour l'intercommunalité." : ", la commune seule étant trop petite pour la plupart des professions.");
    rendre();
  });
  lire(); rendre();
})();

