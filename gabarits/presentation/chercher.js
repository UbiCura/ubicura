// Recherche de l'en-tête (navigation, étape 2, validée par Lucas le 8 novembre 2026, prototypes/nav_etape2/) : un bouton
// « Chercher » sur toutes les pages ouvre un champ qui trouve territoires, communes, indicateurs, questions, thèmes et
// outils, sans tenir compte des accents, des pluriels, de quelques sigles d'usage et d'une faute de frappe. « indicateur +
// lieu » (« psychiatres rodez ») reçoit une réponse directe : les chiffres de la fiche du territoire (règle d'affichage
// unique, territoire/<niveau>/<code>.json écrit par pipeline/reponses.py), une commune répondant par son intercommunalité.
(function () {
  var bouton = document.getElementById("bouton-chercher"), panneau = document.getElementById("panneau-chercher");
  if (!bouton || !panneau) return;
  var champ = document.getElementById("q-tete"), sortie = document.getElementById("res-tete"), etat = document.getElementById("etat-tete");
  var racine = document.documentElement.getAttribute("data-racine") || "";
  var D = null, idx = null, epci = {}, comNom = {}, comPop = {}, enCours = null, minuterie = null, demande = 0, META = null;
  var NIV = { reg: "région", dep: "département", epci: "intercommunalité" };
  // mots d'usage ramenés au vocabulaire du site : des variantes séparées par « | », chacune de un ou plusieurs mots, tous
  // exigés (« hlm » vaut « logement social », jamais « logement » seul)
  var SYN = { psy: "psychiatre|psychologue", pedopsy: "pedopsychiatre", hlm: "logement social", kine: "kinesitherapeute",
    dentiste: "dentiste", toubib: "medecin generaliste", infirmiere: "infirmier", sagefemme: "sage femme",
    pauvre: "pauvrete", riche: "niveau vie", revenu: "revenu|niveau vie", chomeur: "chomage", vieux: "80 ans", agee: "80 ans",
    age: "80 ans|65 79", addiction: "addictologie|addictif", drogue: "addictologie|csapa|caarud", cigarette: "tabac", zone: "autour lieu|rayon", rayon: "autour lieu", perimetre: "autour lieu", cpts: "autour lieu" };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[c]; }); }
  function base(s) { return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[’'\-]/g, " "); }
  function mot(m) { return m.length > 3 ? m.replace(/(s|x)$/, "") : m; }
  // mots vides retirés de la recherche : « psychiatres à Rodez » cherchait « a » au début de « ans » ou « adolescent »
  // (audit indépendant du 8 novembre 2026)
  var VIDES = { a: 1, au: 1, aux: 1, en: 1, de: 1, du: 1, des: 1, d: 1, l: 1, le: 1, la: 1, les: 1, dans: 1, pour: 1, et: 1, ou: 1, sur: 1, par: 1, un: 1, une: 1 };
  function mots(s) { return base(s).split(/[^a-z0-9]+/).filter(Boolean).map(mot); }
  // les mots vides sont retirés avant la coupe du pluriel : « dans » devenait « dan » et n'était plus reconnu (contrôle du
  // 8 novembre 2026, « psychologues dans l'Aveyron »)
  function motsCherches(s) { return base(s).split(/[^a-z0-9]+/).filter(function (m) { return m && !VIDES[m]; }).map(mot); }
  function proche(a, b) {   // une faute de frappe au plus sur un mot d'au moins cinq lettres
    if (a.length < 5 || Math.abs(a.length - b.length) > 1) return false;
    var i = 0, j = 0, e = 0;
    while (i < a.length && j < b.length) { if (a[i] === b[j]) { i++; j++; continue; } if (++e > 1) return false;
      if (a.length > b.length) i++; else if (b.length > a.length) j++; else { i++; j++; } }
    return e + (a.length - i) + (b.length - j) <= 1;
  }
  function charger() {
    if (!enCours) enCours = fetch(racine + "presentation/recherche.json").then(function (r) { return r.json(); }).then(function (d) {
      D = d; idx = [];
      ["reg", "dep", "epci"].forEach(function (lv) { d.territoires[lv].forEach(function (u) {
        idx.push({ g: "terr", t: lv, c: u[0], nm: u[1], m: mots(u[1]), pop: u[2], p: u[3] }); if (lv === "epci") epci[u[0]] = u; }); });
      d.communes.forEach(function (k) { idx.push({ g: "terr", t: "com", c: k[0], nm: k[1], m: mots(k[1]), cp: k[2], pop: k[3], epci: k[4] }); comNom[k[0]] = k[1]; comPop[k[0]] = k[3]; });
      // les arrondissements de Paris, Lyon et Marseille, trouvés comme une commune (« Paris 15e », « Lyon 3 »,
      // « Marseille 8ème »), qui mènent à la fiche de leur commune (contre-audit du 8 novembre 2026) ; « arrondissement »
      // en minuscule, comme on l'écrit (« Paris 15e arrondissement »)
      (d.arrondissements || []).forEach(function (k) { var nm = k[1].replace(/ Arrondissement$/, " arrondissement");
        idx.push({ g: "terr", t: "com", c: k[0], nm: nm, m: mots(nm + " " + rangs(nm).join(" ")), cp: k[2], pop: k[3], epci: k[4], pc: k[5] }); });
      d.indicateurs.forEach(function (i, k) { idx.push({ g: "ind", c: i[0], nm: i[1], m: mots(i[1] + " " + i[2]), mn: motsCherches(i[1].split(", pour ")[0].replace("à la structure la plus proche,", "")), rang: k, dom: i[2], fiche: i[4] || "" }); });
      (d.pages || []).forEach(function (p) { idx.push({ g: p[2] === "question" ? "q" : "page", nm: p[0], url: p[1], genre: p[2], prec: p[3], m: mots(p[0] + " " + p[3]) }); });
    });
    return enCours;
  }
  function etendre(q) {
    // pour chaque mot cherché, ses variantes ; chaque variante est une liste de mots tous exigés
    return motsCherches(q).map(function (m) { return SYN[m] ? SYN[m].split("|").map(mots) : [[m]]; });
  }
  // score d'une entrée : chaque mot cherché doit s'y retrouver (début de mot, ou une faute) ; les mots d'un nom de lieu
  // comptent à part pour reconnaître « indicateur + lieu »
  function present(v, e) { return e.m.some(function (w) { return v.length < 3 ? w === v : (w.indexOf(v) === 0 || proche(v, w)); }); }
  function couvre(e, groupes) {
    return groupes.every(function (vs) { return vs.some(function (alt) { return alt.every(function (v) { return present(v, e); }); }); });
  }
  // pour la réponse directe, plus strict que la liste : un mot court (sigle) se retrouve en entier (« cmp » n'est pas
  // « cmpp »), seul le nom de l'indicateur compte (pas son domaine), et l'indicateur retenu est celui dont la recherche
  // couvre la plus grande part du nom, sans faute de frappe, au moins 40 % ; à égalité, le premier du catalogue.
  // « logement Rennes » ou « emploi Lyon » ne répondent plus par un indicateur pris au hasard (contre-audit du 8 novembre
  // 2026) : la liste les propose.
  function exact(v, w) { return v.length < 4 ? w === v : w.indexOf(v) === 0; }
  function part(e, groupes) {
    var vus = {};
    groupes.forEach(function (vs) { vs.forEach(function (alt) { alt.forEach(function (v) {
      e.mn.forEach(function (w, k) { if (exact(v, w)) vus[k] = 1; }); }); }); });
    return e.mn.length ? Object.keys(vus).length / e.mn.length : 0;
  }
  function indicateurs(q) {
    var V = etendre(q);
    if (!V.length || !idx) return [];
    return idx.filter(function (e) { return e.g === "ind" && couvre(e, V); })
      .map(function (e) { return { e: e, p: part(e, V) }; })
      .filter(function (x) { return x.p >= 0.4; })
      .sort(function (a, b) { return b.p - a.p || a.e.rang - b.e.rang; })
      .map(function (x) { return x.e; });
  }
  // un nom de lieu et ses formes d'usage : sans son article (« Réunion », « Havre »), sans le sigle d'une
  // intercommunalité (« Rodez Agglomération », « Grand Paris »)
  function formes(nm) {
    var n = base(nm).replace(/\s+/g, " ").trim(), s = n.replace(/^(la|le|les|l) /, "");
    var r = rangs(nm), v = /^(.+) \d+(er|e) arrondissement$/.exec(n);
    // un arrondissement : « paris 15 », « paris 15e », « paris 15eme », avec ou sans « arrondissement »
    var arr = v ? r.reduce(function (a, x) { return a.concat([v[1] + " " + x, v[1] + " " + x + " arrondissement"]); }, []) : [];
    return [n, s, s.replace(/^(ca|cc|cu|ct|ept|cte|cs|metropole|communaute (de communes|d agglomeration|urbaine))( (du|de la|de|des|d))? /, "")].concat(arr);
  }
  // le rang d'un arrondissement sous ses formes d'usage : « 15 », « 15e », « 15eme », et « 1er », « 1ere » pour le premier
  function rangs(nm) {
    var v = /(\d+)(er|e) [Aa]rrondissement$/.exec(nm); if (!v) return [];
    return [v[1], v[1] + "e", v[1] + "eme"].concat(v[1] === "1" ? ["1er", "1ere"] : []);
  }
  function trouver(q) {
    var V = etendre(q), res = { terr: [], ind: [], q: [], page: [] };
    if (!V.length || !idx) return res;
    var cp = /^\d{5}$/.test(q.trim());
    idx.forEach(function (e) {
      if (cp) { if (e.t === "com" && e.cp.split(" ").indexOf(q.trim()) >= 0) res.terr.push(e); return; }
      if (couvre(e, V)) res[e.g].push(e);
    });
    var RANG = { dep: 0, reg: 1, epci: 2, com: 3 };
    res.terr.sort(function (a, b) { return (b.pop || 0) - (a.pop || 0) || RANG[a.t] - RANG[b.t]; });
    // « 75015 » : l'arrondissement dont c'est le code postal avant la commune de Paris (relecture du 9 novembre 2026)
    if (cp) res.terr.sort(function (a, b) { return (b.pc ? 1 : 0) - (a.pc ? 1 : 0); });
    // l'indicateur dont le nom commence par la recherche d'abord, puis le plus court (« Psychiatre » avant « Psychiatre,
    // en établissement psychiatrique »)
    var qb = motsCherches(q).join(" ");
    res.ind.sort(function (a, b) { var x = mots(a.nm).join(" ").indexOf(qb) === 0 ? 0 : 1, y = mots(b.nm).join(" ").indexOf(qb) === 0 ? 0 : 1;
      return x - y || a.nm.length - b.nm.length; });
    return res;
  }
  // « indicateur + lieu » : le plus long découpage dont la fin est un lieu et le début un indicateur
  function analyser(q) {
    var ms = q.trim().split(/\s+/);
    for (var k = 1; k < ms.length; k++) {
      var a = ms.slice(0, k).join(" "), b = ms.slice(k).join(" ");
      var essais = [[a, b], [b, a]];
      for (var i = 0; i < 2; i++) {
        var ri = indicateurs(essais[i][0]); if (!ri.length) continue;
        var rt = trouver(essais[i][1]).terr;
        // un lieu n'est reconnu que si son nom correspond en entier, avec ou sans article ou sigle (« Lille » pour
        // « Lille », jamais « de vie » pour « Croix-de-Vie »)
        var lieu = base(essais[i][1]).trim().replace(/\s+/g, " ").replace(/^(a|au|aux|en|dans|de|du|des|d|pour|sur) /, "");
        var lieux = [lieu, lieu.replace(/^(la|le|les|l) /, "")];
        // le nom entier d'abord, puis sans article, puis sans sigle : « Lyon » est la commune, pas la Métropole de Lyon ;
        // -1 quand aucune forme ne va (un arrondissement a plus de neuf formes, « lyon 1er » est la dixième)
        function niveau(e) { var f = formes(e.nm); for (var z = 0; z < f.length; z++) if (lieux.indexOf(f[z]) >= 0) return z; return -1; }
        var ok = lieu.length < 3 ? [] : rt.map(function (e, z) { return { e: e, n: /^\d{5}$/.test(lieu) ? 0 : niveau(e), z: z }; })
          .filter(function (x) { return x.n >= 0; }).sort(function (x, y) { return x.n - y.n || x.z - y.z; }).map(function (x) { return x.e; });
        var t = ok[0];
        if (!t) continue;
        // Paris par son code postal répond comme « Paris » : le département, dont la commune porte le nom et le code ;
        // un arrondissement de Paris aussi, et la réponse le nomme (« à Paris, dont Paris 15e arrondissement fait partie »)
        if (t.t === "com") { var nc = t.pc ? comNom[t.pc] || t.nm : t.nm, cc = t.pc || t.c;
          var dp = idx.filter(function (e) { return e.t === "dep" && cc.indexOf(e.c) === 0 && base(e.nm) === base(nc); })[0];
          // la commune reste connue (com), pour le lien « Autour de Paris » de la réponse
          if (dp) t = { g: dp.g, t: dp.t, c: dp.c, nm: dp.nm, m: dp.m, pop: dp.pop, p: dp.p, via: t.pc ? t.nm : null, com: t }; }
        return { ind: ri, terr: t, homonymes: ok.filter(function (e) { return e !== t && e.nm === t.nm && e.pop !== t.pop; }) };
      }
    }
    return null;
  }
  // sans réponse directe, l'indicateur et le lieu reconnus chacun de leur côté (« psychiatres auvergne »)
  function separer(q) {
    var ms = q.trim().split(/\s+/), best = null;
    for (var k = 1; k < ms.length; k++) {
      var a = ms.slice(0, k).join(" "), b = ms.slice(k).join(" ");
      [[a, b], [b, a]].forEach(function (x) {
        var ri = trouver(x[0]).ind, rt = trouver(x[1]).terr;
        if (ri.length && rt.length && (!best || ri.length + rt.length < best.ind.length + best.terr.length)) best = { ind: ri, terr: rt };
      });
    }
    return best;
  }
  // « Autour d'Avignon », « Autour du Havre », « Autour des Abymes », « Autour de Rodez »
  function autour(nm) {
    if (/^Le /.test(nm)) return "Autour du " + nm.slice(3);
    if (/^Les /.test(nm)) return "Autour des " + nm.slice(4);
    return /^[AEIOUYÉÈÊÎÔÂH]/i.test(nm) ? "Autour d'" + nm : "Autour de " + nm;
  }
  // une commune hors intercommunalité (code en C : Ouessant, Sein, Bréhat, Yeu) a sa propre fiche, qu'elle ne « fait
  // pas partie » d'elle-même (contre-audit du 8 novembre 2026, « à Ouessant, dont Ouessant fait partie »)
  function seule(e) { return e.t === "com" && /^C/.test(e.epci || ""); }
  // une commune ou un arrondissement (relecture indépendante du 9 novembre 2026) : Paris, commune et département à la
  // fois, mène à la fiche du département comme la réponse directe ; un arrondissement de Lyon ou de Marseille, à
  // l'intercommunalité avec sa commune et son nom (« Lyon 3e arrondissement est dans la commune de Lyon ») ; une
  // commune de plus de 100 000 habitants n'y est pas dite « trop petite »
  function lienCommune(e) {
    var cc = e.pc || e.c, ep = epci[e.epci];
    if (cc === "75056") return racine + "territoire/dep/75.html";
    if (!ep) return null;
    if (seule(e)) return racine + "territoire/epci/" + ep[0] + ".html";
    return racine + "territoire/epci/" + ep[0] + ".html?commune=" + cc + "&nom=" + encodeURIComponent(e.pc ? comNom[e.pc] || e.nm : e.nm) +
      (e.pc ? "&arr=" + encodeURIComponent(e.nm) : "") + ((comPop[cc] || e.pop || 0) > 100000 ? "&grande=1" : "");
  }
  function adresse(e) {
    if (e.t === "com") return lienCommune(e);
    if (e.g === "terr") return racine + "territoire/" + e.t + "/" + e.c + ".html";
    if (e.g === "ind") return e.fiche ? racine + "indicateur/" + e.fiche + ".html" : racine + "indicateurs.html";
    return racine + e.url;
  }
  function ligne(e) {
    var s = "";
    // « 75015, à Paris » pour un arrondissement ; « commune sans intercommunalité » pour Ouessant ou l'Île-d'Yeu
    if (e.t === "com" && e.pc) s = e.cp.split(" ")[0] + ", à " + (comNom[e.pc] || "");
    else if (e.t === "com") { var ep = epci[e.epci]; s = seule(e) ? "commune sans intercommunalité" : "commune" + (ep ? ", dans " + ep[1] : ""); }
    else if (e.g === "terr") s = (e.t === "epci" && /^C/.test(e.c) ? "commune sans intercommunalité" : NIV[e.t]) + (e.p ? ", " + e.p : "");
    else if (e.g === "ind") s = "indicateur, " + e.dom.toLowerCase();
    else s = e.prec;
    var a = adresse(e);
    return "<li>" + (a ? '<a href="' + esc(a) + '">' + esc(e.nm) + "</a>" : esc(e.nm)) + "<span>" + esc(s) + "</span></li>";
  }
  function groupe(titre, l, n) { return l.length ? "<div><h3>" + titre + "</h3><ul>" + l.slice(0, n).map(ligne).join("") + "</ul></div>" : ""; }
  function lire(lv, code) { return fetch(racine + "territoire/" + lv + "/" + code + ".json").then(function (r) { return r.ok ? r.json() : null; }); }
  function reponse(a, numero) {
    var t = a.terr, lv = t.t === "com" ? "epci" : t.t, code = t.t === "com" ? t.epci : t.c, ind = a.ind[0];
    if (!code || !ind) return;
    var meta = META ? Promise.resolve(META) : fetch(racine + "presentation/reponses.json").then(function (r) { return r.json(); }).then(function (m) { META = m; return m; });
    Promise.all([lire(lv, code), meta]).then(function (x) {
      var j = x[0];
      // un indicateur publié seulement au département répond au département de rattachement, comme la fiche ; publié
      // seulement par région, à la région de ce département (contre-audit du 8 novembre 2026)
      function region(d) { return d && d.reg ? lire("reg", d.reg).then(function (r) { return r && r.ind[ind.c] ? [r, "reg", d.reg] : null; }) : Promise.resolve(null); }
      if (!j || j.ind[ind.c]) return [j, x[1], null];
      if (j.dep) return lire("dep", j.dep).then(function (d) {
        if (d && d.ind[ind.c]) return [j, x[1], [d, "dep", j.dep]];
        return region(d).then(function (r) { return [j, x[1], r]; });
      });
      if (lv === "dep") return region(j).then(function (r) { return [j, x[1], r]; });
      return [j, x[1], null];
    }).then(function (x) {
      var j = x[0], M = x[1][ind.c] || [ind.nm.toLowerCase(), ""], R = x[2], jd = R ? R[0] : null;
      if (numero !== demande || !j) return;
      var lieu = (j.dans || "dans " + j.nom) + (t.t === "com" && !seule(t) ? ", dont " + t.nm + " fait partie" : t.via ? ", dont " + t.via + " fait partie" : "");
      var src = jd || j, v = src.ind[ind.c];
      var bloc = document.createElement("div"); bloc.className = "reponse";
      var ou = !jd ? lieu : (jd.dans || "dans " + jd.nom) + (R[1] === "dep" ? ", département de rattachement " : ", région ") +
        (j.de || "de " + j.nom) + (R[1] === "dep" ? " (indicateur publié par département)" : " (indicateur publié par région)");
      // sans valeur, ce que la fiche écrit (« non diffusé », « non publié »), jamais une unité seule (contre-audit)
      if (!v || (v[0] !== "aucun" && !v[1])) {
        bloc.innerHTML = '<span class="n">–</span><span class="t">' + esc(ind.nm.split(", pour ")[0]) + " : " + esc(v && v[6] ? v[6] : "pas de valeur publiée") + " " + esc(ou) + ".</span>" +
          (v && v[3] ? '<span class="r"><b class="sig">!</b> ' + esc(v[3]) + "</span>" : "");
      }
      else {
        var prof = v[7] === "prof" || v[7] === "lieux", gros, phrase;
        // « Pédopsychiatre : aucun inscrit dans … », « CAARUD : aucune structure dans … », jamais un 0 seul
        if (v[0] === "aucun") { gros = v[7] === "lieux" ? "aucune" : "aucun"; phrase = esc(ind.nm.split(", pour ")[0]) + " : " + esc(v[6] || "aucun") + " " + esc(ou); }
        else {
          gros = prof && v[0] ? v[0] : (v[1] || "–");
          // la phrase de la tuile de la fiche : « psychiatres dans la CA Rodez Agglomération, soit 4,8 pour 10 000 habitants »
          // au singulier pour un seul inscrit (M[2]) ; un type de lieu s'écrit comme la ligne de la fiche, « Maternités : 1 dans … »
          // un nom qui porte une virgule se referme par une autre : « psychiatres, en établissement psychiatrique, dans … »
          var nomP = v[0] === "1" && M[2] ? M[2] : M[0]; if (nomP.indexOf(", ") > 0) nomP += ",";
          phrase = v[7] === "prof" && v[0] ? esc(nomP) + " " + esc(ou) + ", soit " + esc(v[1]) + " " + esc(M[1])
            : v[7] === "lieux" && v[0] ? esc(M[0]) + " : " + esc(v[0]) + " " + esc(ou) + ", soit " + esc(v[1]) + " " + esc(M[1])
            : esc(ind.nm) + " : " + esc(v[1]) + (M[1] && M[1] !== "%" ? " " + esc(M[1]) : (M[1] === "%" ? "\u202f%" : "")) + " " + esc(ou);
          if (v[6]) phrase += " (" + esc(v[6]) + ")";
        }
        // le repère d'une distance ou d'un temps avec son unité, comme la fiche (« 6,3 km »)
        var uRef = M[1] === "km" || M[1] === "min" ? " " + M[1] : "";
        bloc.innerHTML = '<span class="n">' + esc(gros) + "</span>" + '<span class="t">' + phrase + "</span>" +
          // la limite dans la même ligne de notes, à la ligne : la grille de la réponse garde quatre lignes
          '<span class="r">' + esc(v[2]) + (v[4] ? (v[2] ? ". " : "") + esc(v[4]) + " : " + esc(v[5]) + esc(uRef) : "") +
          (v[3] ? '<br><b class="sig">!</b> ' + esc(v[3]) : "") + "</span>" +
          '<span class="s">Chiffres calculés comme ceux des fiches, ' + esc(((jd || j).pop || 0).toLocaleString("fr-FR")) + " habitants.</span>";
      }
      var fl = jd ? R[1] : lv, fc = jd ? R[2] : code, fj = jd || j;
      var tc = t.t === "com" ? t : t.com || null;
      var l = document.createElement("span"); l.className = "l";
      l.innerHTML = '<a href="' + esc(racine + "territoire/" + fl + "/" + fc + ".html") + '">Fiche ' + esc(fj.de || "de " + fj.nom) + "</a>" +
        '<a href="' + esc(adresse(ind)) + '">' + esc(ind.nm) + " : carte et définition</a>" +
        // autour d'un arrondissement : autour de sa commune, la seule que connaît la page « Autour d'un lieu »
        (tc ? '<a href="' + esc(racine + "zone.html#lieu=" + (tc.pc || tc.c) + "&rayon=10") + '">' + esc(autour(tc.pc ? comNom[tc.pc] || tc.nm : tc.nm)) + "</a>" : "");
      bloc.appendChild(l);
      // une seule apostrophe dans la réponse et ses liens, la droite, comme le reste du texte des fiches
      bloc.innerHTML = bloc.innerHTML.replace(/’/g, "'");
      sortie.insertBefore(bloc, sortie.firstChild);
      // les autres lieux du même nom, proposés sous la réponse (« Saint-Denis » : La Réunion et la Seine-Saint-Denis)
      if (a.homonymes && a.homonymes.length) {
        var g = document.createElement("div"); g.className = "groupes";
        g.innerHTML = groupe("Autres lieux de ce nom", a.homonymes, 8).replace(/’/g, "'");
        bloc.parentNode.insertBefore(g, bloc.nextSibling);
      }
      annoncer();
    }).catch(function () {});
  }
  function montrer() {
    var q = champ.value, numero = ++demande;
    if (!q.trim()) { sortie.innerHTML = ""; return; }
    if (!idx) { charger().then(montrer); return; }
    var r = trouver(q), a = analyser(q), s = (a || r.terr.length || r.ind.length || r.q.length || r.page.length) ? null : separer(q);
    var h = groupe("Territoires", r.terr, 5) + groupe("Indicateurs", r.ind, 5) + groupe("Questions", r.q, 4) + groupe("Pages et outils", r.page, 4);
    // sans réponse directe ni résultat pour toute la phrase, l'indicateur et le lieu proposés chacun de leur côté
    var avant = s ? '<p class="vide">Pas de réponse directe pour cette recherche : choisissez l\'indicateur, puis le territoire.</p>' : "";
    if (s) h = groupe("Indicateurs", s.ind, 5) + groupe("Territoires", s.terr, 5);
    // une seule apostrophe dans tout le panneau, la droite (contre-audit du 8 novembre 2026)
    sortie.innerHTML = h ? avant + '<div class="groupes">' + h.replace(/’/g, "'") + "</div>" : (a ? "" :'<p class="vide">Rien ne porte ce nom. Essayez le début d\'un nom de commune, un code postal, ou un mot comme « CMP », « revenu » ou « logement ».</p>');
    annoncer();
    if (a) reponse(a, numero);
  }
  // le compte des résultats lu par les lecteurs d'écran, plutôt que toute la liste à chaque frappe
  function annoncer() {
    var n = sortie.querySelectorAll(".groupes li").length, r = sortie.querySelector(".reponse");
    if (etat) etat.textContent = !champ.value.trim() ? "" : r ? "Une réponse directe" + (n ? ", puis " + n + " résultat" + (n > 1 ? "s" : "") : "") + "."
      : (n ? n + " résultat" + (n > 1 ? "s" : "") : "Aucun résultat") + ".";
  }
  function ouvrir(o) {
    panneau.hidden = !o; bouton.setAttribute("aria-expanded", String(o));
    if (o) { charger(); champ.focus(); } else bouton.focus();
  }
  bouton.addEventListener("click", function () { ouvrir(panneau.hidden); });
  champ.addEventListener("input", function () { clearTimeout(minuterie); minuterie = setTimeout(montrer, 120); });
  // Échap ferme le panneau d'où que soit le focus ; les flèches passent d'un lien à l'autre ; Entrée dans le champ suit
  // la fiche de la réponse directe quand elle est là, sinon le premier résultat
  panneau.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") { ev.preventDefault(); ouvrir(false); return; }
    if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp") return;
    var liens = [].slice.call(sortie.querySelectorAll("a")); if (!liens.length) return;
    var k = liens.indexOf(document.activeElement);
    ev.preventDefault();
    if (ev.key === "ArrowDown") (k < 0 ? liens[0] : liens[Math.min(liens.length - 1, k + 1)]).focus();
    else if (k <= 0) champ.focus(); else liens[k - 1].focus();
  });
  champ.addEventListener("keydown", function (ev) {
    if (ev.key === "Enter") { var a = sortie.querySelector(".reponse .l a") || sortie.querySelector("a"); if (a) location.href = a.href; }
  });
  // fonctions reprises par le contrôle de la recherche (outils/controle_recherche.py), qui l'essaie dans le navigateur
  window.UbiChercher = { charger: charger, analyser: analyser, chercher: function (q) { champ.value = q; montrer(); } };
})();
