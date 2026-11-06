// Relevé des pages dessinées dans le navigateur (atlas, Explorer, et plus tard les pages de la nouvelle présentation),
// pour l'inventaire « ne rien perdre » d'outils/inventaire_site.py. À coller dans la console de la page une fois
// chargée (ou à lancer par l'outil de navigation). Ouvre chaque onglet, déplie chaque bloc, puis compte les figures
// (SVG de premier niveau d'au moins 5 éléments), les cartes (SVG d'au moins 30 tracés), les tableaux, et relève les titres
// (h2, h3, légendes de tableau, titres de fenêtre). Rend un objet { titres, figures, cartes, tableaux }.
(async () => {
  const pause = ms => new Promise(r => setTimeout(r, ms));
  const vu = { titres: new Set(), figures: new Set(), cartes: new Set(), tableaux: new Set() };
  function releve() {
    document.querySelectorAll("details").forEach(d => { d.open = true; });
    document.querySelectorAll("svg").forEach(s => {
      if (s.parentElement && s.parentElement.closest("svg")) return;
      if (s.querySelectorAll("*").length < 5) return;   // pictogrammes écartés (la taille vaut 0 quand la fenêtre est masquée)
      const cle = (s.id || "") + "|" + (s.getAttribute("aria-label") || "") + "|" + (s.closest("[id]") ? s.closest("[id]").id : "") + "|" + s.querySelectorAll("*").length;
      vu.figures.add(cle);
      if (s.querySelectorAll("path,polygon").length >= 30) vu.cartes.add(cle);
    });
    document.querySelectorAll("table").forEach(t => { const c = t.querySelector("caption"); vu.tableaux.add((t.id || "") + "|" + (c ? c.textContent.trim() : "") + "|" + (t.closest("[id]") ? t.closest("[id]").id : "")); });
    document.querySelectorAll("h2,h3,caption,.barre strong,.fenetre-titre").forEach(h => { const t = h.textContent.replace(/\s+/g, " ").trim(); if (t && !h.closest("svg")) vu.titres.add(t); });
  }
  releve();
  for (const b of document.querySelectorAll('[role="tab"]')) { b.click(); await pause(1500); releve(); }
  return { titres: [...vu.titres], figures: vu.figures.size, cartes: vu.cartes.size, tableaux: vu.tableaux.size };
})();
