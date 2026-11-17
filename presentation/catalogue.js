// Page « Indicateurs » (navigation, étape 2, 8 novembre 2026) : catalogue des indicateurs, recherche sans accents ni
// pluriels (« psychiatres » trouve « Psychiatre »), filtres par domaine, thème et niveau, réglages gardés dans l'adresse.
(function () {
  var corps = document.getElementById("cat-corps"), n = document.getElementById("cat-n"), q = document.getElementById("qcat");
  if (!corps) return;
  var f = { dom: "", th: "", niv: "" }, C = [];
  function norm(s) {
    return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[’']/g, " ")
      .split(/[^a-z0-9]+/).filter(Boolean).map(function (m) { return m.length > 3 ? m.replace(/(s|x)$/, "") : m; }).join(" ");
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[c]; }); }
  var tete = '<table class="cat-t"><colgroup><col class="c-nom"><col class="c-def"><col class="c-src"><col class="c-niv"></colgroup>' +
    '<thead><tr><th scope="col">Indicateur</th><th scope="col">Définition</th><th scope="col">Source</th><th scope="col">Niveaux</th></tr></thead><tbody>';
  function ecrireAdresse() {
    var p = []; if (q.value.trim()) p.push("q=" + encodeURIComponent(q.value.trim()));
    ["dom", "th", "niv"].forEach(function (g) { if (f[g]) p.push(g + "=" + encodeURIComponent(f[g])); });
    history.replaceState(null, "", p.length ? "#" + p.join("&") : location.pathname);
  }
  function rendre() {
    var mots = norm(q.value).split(" ").filter(Boolean), dom = null, grp = null, h = "", k = 0;
    C.forEach(function (e) {
      if (f.dom && e.domaine !== f.dom) return;
      if (f.th && e.themes.indexOf(f.th) < 0) return;
      if (f.niv && e.niveaux.indexOf(f.niv) < 0) return;
      var t = " " + norm([e.nom, e.definition, e.source, e.sous, e.themes.join(" ")].join(" ")) + " ";
      if (mots.some(function (m) { return t.indexOf(" " + m) < 0; })) return;
      k++;
      if (e.domaine !== dom) { h += (dom === null ? "" : "</tbody></table></div>") + '<h2 class="cat-dom">' + esc(e.domaine) + '</h2><div class="defile">' + tete; dom = e.domaine; grp = null; }
      if (e.commune && e.sous !== grp) { grp = e.sous; h += '<tr class="groupe"><td colspan="4">' + esc(e.sous) + ' <span>' + esc(e.definition) + '</span></td></tr>'; }
      if (!e.commune) grp = null;
      h += '<tr><td class="nom"><a href="' + esc(e.page) + '">' + esc(e.nom) + '</a>' +
        (e.themes.length ? '<span class="eti">' + esc(e.themes.join(", ").toLowerCase()) + '</span>' : "") + '</td>' +
        '<td class="def">' + (e.commune ? "" : esc(e.definition)) + '</td>' +
        '<td>' + esc(e.source) + (e.date ? ", " + esc(e.date) : "") + '</td><td>' + esc(e.niveaux.join(", ")) + '</td></tr>';
    });
    corps.innerHTML = k ? h + "</tbody></table></div>" : '<p>Aucun indicateur ne répond à cette recherche. Essayez un autre mot, ou retirez un filtre.</p>';
    n.textContent = k === C.length ? k + " indicateurs" : k + " indicateur" + (k > 1 ? "s" : "") + " sur " + C.length;
    ecrireAdresse();
  }
  document.querySelectorAll(".filtres button:not([disabled])").forEach(function (b) {
    b.addEventListener("click", function () {
      var g = b.dataset.g; f[g] = b.dataset.v;
      document.querySelectorAll('.filtres button[data-g="' + g + '"]').forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      rendre();
    });
  });
  q.addEventListener("input", rendre);
  var a = new URLSearchParams(location.hash.slice(1));
  if (a.get("q")) q.value = a.get("q");
  ["dom", "th", "niv"].forEach(function (g) {
    var v = a.get(g); if (!v) return; f[g] = v;
    document.querySelectorAll('.filtres button[data-g="' + g + '"]').forEach(function (x) { x.setAttribute("aria-pressed", String(x.dataset.v === v)); });
  });
  fetch("presentation/catalogue.json").then(function (r) { return r.json(); }).then(function (d) { C = d; rendre(); })
    .catch(function () { corps.innerHTML = '<p>Le catalogue n’a pas pu être chargé. Les indicateurs sont aussi listés sur la page <a href="domaines.html">Domaines</a>.</p>'; });
})();
