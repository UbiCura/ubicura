// Recherche d'un territoire, d'une commune ou d'un indicateur (présentation du 30 octobre 2026, deux audits externes).
// Une commune mène à la fiche de son intercommunalité, avec la commune rappelée en tête ; le code postal fonctionne ;
// une recherche sans résultat le dit avec une piste. Les données (recherche.json) se chargent à la première frappe.
// Usage : Recherche.brancher(champ, liste, message, racine[, choisir]), racine étant le chemin vers la racine du site.
// Avec choisir, un résultat n'ouvre pas de page : choisir({t, c, nm, commune}, entrée) est appelé (comparateur, zone), les
// indicateurs sont alors écartés et une commune vaut son intercommunalité.
var Recherche = (function () {
  function norm(s) { return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[-'’]/g, " ").replace(/\s+/g, " ").trim(); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  var NIV = { reg: "région", dep: "département", epci: "intercommunalité" };
  var donnees = null, index = null, epci = {}, enCours = null;
  function charger(racine) {
    if (!enCours) enCours = fetch(racine + "presentation/recherche.json").then(function (r) { return r.json(); }).then(function (d) {
      donnees = d; index = [];
      ["reg", "dep", "epci"].forEach(function (lv) {
        d.territoires[lv].forEach(function (u) { index.push({ t: lv, c: u[0], nm: u[1], n: norm(u[1]), pop: u[2], p: u[3] }); if (lv === "epci") epci[u[0]] = u; });
      });
      d.communes.forEach(function (k) { index.push({ t: "com", c: k[0], nm: k[1], n: norm(k[1]), cp: k[2], pop: k[3], epci: k[4] }); });
      d.indicateurs.forEach(function (i) { index.push({ t: "ind", c: i[0], nm: i[1], n: norm(i[1]), d: norm(i[2]), dom: i[3], domNom: i[2], fiche: i[4] || "" }); });
    });
    return enCours;
  }
  function chercher(q) {
    var n = norm(q); if (!n || !index) return [];
    var estCp = /^\d{2,5}$/.test(n), mots = n.split(" "), res = [];
    index.forEach(function (e) {
      var s = -1;
      if (e.t === "ind") {
        if (!estCp && n.length > 2) {
          if (mots.every(function (m) { return e.n.indexOf(m) >= 0; })) s = e.n.indexOf(n) === 0 ? 1.5 : 1;
          else if (mots.every(function (m) { return (e.n + " " + e.d).indexOf(m) >= 0; })) s = 0.5;
        }
      } else if (estCp && e.t === "com") { if (e.cp.split(" ").some(function (x) { return x.indexOf(n) === 0; })) s = 2; else if (e.c.indexOf(n) === 0) s = 1; }
      else if (estCp && e.t === "dep" && e.c === n) s = 3;
      else if (!estCp) { if (e.n === n) s = 4; else if (e.n.indexOf(n) === 0) s = 3; else if (e.n.indexOf(" " + n) >= 0) s = 2; }
      if (s >= 0) res.push({ e: e, s: s });
    });
    res.sort(function (a, b) { return b.s - a.s || (b.e.pop || 0) - (a.e.pop || 0); });
    var terr = res.filter(function (r) { return r.e.t !== "ind"; }).slice(0, 6), ind = res.filter(function (r) { return r.e.t === "ind"; }).slice(0, terr.length ? 3 : 8);
    return terr.concat(ind).map(function (r) { return r.e; });
  }
  function libelle(e) {
    if (e.t === "ind") return esc(e.nm) + " <span>indicateur, " + esc(e.domNom.toLowerCase()) + "</span>";
    if (e.t === "com") { var ep = epci[e.epci]; return esc(e.nm) + " <span>commune, " + esc(e.cp.split(" ")[0]) + (ep ? ", dans " + esc(ep[1]) : "") + "</span>"; }
    return esc(e.nm) + " <span>" + NIV[e.t] + (e.p ? ", " + esc(e.p) : "") + "</span>";
  }
  // Adresse de la page qu'ouvre un résultat.
  function adresse(e, racine) {
    if (e.t === "com") { var ep = epci[e.epci]; return ep ? racine + "territoire/epci/" + ep[0] + ".html?commune=" + e.c + "&nom=" + encodeURIComponent(e.nm) : null; }
    if (e.t === "ind") return e.fiche ? racine + "indicateur/" + e.fiche + ".html" : racine + "domaines.html#" + e.dom;
    return racine + "territoire/" + e.t + "/" + e.c + ".html";
  }
  function cible(e) {
    if (e.t === "com") { var ep = epci[e.epci]; return ep ? { t: "epci", c: ep[0], nm: ep[1], commune: { c: e.c, nm: e.nm } } : null; }
    return { t: e.t, c: e.c, nm: e.nm };
  }
  function brancher(champ, liste, msg, racine, choisir) {
    var courant = [];
    function montrer() {
      if (!index) { charger(racine).then(montrer); return; }
      courant = chercher(champ.value).filter(function (e) { return !choisir || e.t !== "ind"; }); msg.textContent = "";
      if (!champ.value.trim()) { liste.innerHTML = ""; liste.hidden = true; champ.setAttribute("aria-expanded", "false"); return; }
      if (!courant.length) {
        liste.innerHTML = ""; liste.hidden = true; champ.setAttribute("aria-expanded", "false");
        msg.textContent = "Aucun territoire ni aucun indicateur ne porte ce nom. Essayez le code postal, le début du nom, ou un autre mot comme « revenu » ou « CMP ».";
        return;
      }
      liste.innerHTML = courant.map(function (e, k) { return '<li role="option" id="' + liste.id + "-" + k + '" data-k="' + k + '"><a href="' + esc(adresse(e, racine) || "#") + '">' + libelle(e) + "</a></li>"; }).join("");
      liste.hidden = false; champ.setAttribute("aria-expanded", "true");
    }
    champ.addEventListener("focus", function () { charger(racine); });
    champ.addEventListener("input", montrer);
    champ.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") { ev.preventDefault(); if (!index) return; montrer(); if (courant.length) { if (choisir) { liste.hidden = true; choisir(cible(courant[0]), courant[0]); return; } var a = adresse(courant[0], racine); if (a) location.href = a; else msg.textContent = "Cette commune n'a pas d'intercommunalité dans le référentiel."; } }
      if (ev.key === "Escape") { liste.hidden = true; champ.setAttribute("aria-expanded", "false"); }
    });
    if (choisir) liste.addEventListener("click", function (ev) {
      var li = ev.target.closest("li"); if (!li) return; ev.preventDefault();
      liste.hidden = true; champ.setAttribute("aria-expanded", "false"); var e = courant[+li.getAttribute("data-k")]; choisir(cible(e), e);
    });
  }
  return { brancher: brancher, norm: norm };
})();
