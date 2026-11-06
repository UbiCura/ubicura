// Glossaire en infobulle (deux audits externes du 30 octobre 2026). Chaque sigle et chaque notion du glossaire publié
// est expliqué à sa première apparition dans la page, au survol, au clavier et d'un toucher. Définitions tirées de
// contenus/sigles.csv et du glossaire des résultats (site_data, meta.glossaire), réunies dans glossaire.json.
(function () {
  var racine = document.documentElement.getAttribute("data-racine") || "";
  var zone = document.querySelector("main");
  if (!zone) return;
  fetch(racine + "presentation/glossaire.json").then(function (r) { return r.json(); }).then(function (G) {
    var cles = Object.keys(G).sort(function (a, b) { return b.length - a.length; });
    if (!cles.length) return;
    var re = new RegExp("(^|[^\\wÀ-ÿ])(" + cles.map(function (k) { return k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).join("|") + ")(?![\\wÀ-ÿ])");
    var vus = {}, SAUTER = { SCRIPT: 1, STYLE: 1, A: 1, BUTTON: 1, CODE: 1, H1: 1, SUMMARY: 1, LABEL: 1, CAPTION: 1, TH: 1, OPTION: 1, SELECT: 1, TEXTAREA: 1, INPUT: 1 };
    function parcourir(n) {
      if (n.nodeType === 3) {
        var texte = n.nodeValue, decal = 0, m;
        while ((m = re.exec(texte.slice(decal))) && vus[m[2]]) decal += m.index + m[0].length;
        if (!m) return;
        vus[m[2]] = 1;
        var debut = decal + m.index + m[1].length, apres = n.splitText(debut); apres.splitText(m[2].length);
        var s = document.createElement("span"); s.className = "glo"; s.tabIndex = 0; s.setAttribute("data-def", G[m[2]]);
        s.setAttribute("aria-label", m[2] + ", " + G[m[2]]); s.textContent = m[2];
        apres.parentNode.replaceChild(s, apres);
        return;
      }
      if (n.nodeType !== 1 || SAUTER[n.nodeName] || n.closest("svg,nav,.glo,[data-sans-glossaire]")) return;
      [].slice.call(n.childNodes).forEach(parcourir);
    }
    parcourir(zone);
    var bulle = document.createElement("div"); bulle.id = "glo-bulle"; bulle.setAttribute("role", "tooltip"); bulle.hidden = true; document.body.appendChild(bulle);
    function montrer(s) {
      bulle.textContent = s.getAttribute("data-def"); bulle.hidden = false;
      var r = s.getBoundingClientRect(), l = Math.min(Math.max(8, r.left + scrollX), scrollX + innerWidth - Math.min(360, innerWidth - 16) - 8);
      bulle.style.left = l + "px"; bulle.style.top = (r.bottom + scrollY + 6) + "px";
    }
    function cacher() { bulle.hidden = true; }
    document.addEventListener("mouseover", function (e) { var s = e.target.closest && e.target.closest(".glo"); if (s) montrer(s); });
    document.addEventListener("mouseout", function (e) { if (e.target.closest && e.target.closest(".glo")) cacher(); });
    document.addEventListener("focusin", function (e) { if (e.target.classList && e.target.classList.contains("glo")) montrer(e.target); });
    document.addEventListener("focusout", function (e) { if (e.target.classList && e.target.classList.contains("glo")) cacher(); });
    document.addEventListener("click", function (e) { var s = e.target.closest && e.target.closest(".glo"); if (s) { if (bulle.hidden) montrer(s); else cacher(); } else cacher(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") cacher(); });
  }).catch(function () {});
})();
