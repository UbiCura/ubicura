// Explorer, outils de l'onglet Inégalités de l'atlas déplacés ici (lot 2, note docs/note_explorer_atlas_2026-10-28.md).
// Même calcul et mêmes phrases que l'atlas, données prises telles quelles dans site_data.json (pipeline/explorer.py,
// donnees_inegalites), figures en pleine largeur dans des fenêtres séparées, onglets seulement entre des vues d'un même
// résultat. Chargé après explorer.js, dont il reprend les outils communs (formats, listes, réglages dans l'adresse).

// pluriel et qualification du Gini, repris de l'atlas mot pour mot (à réunir dans un fichier commun au lot 5)
const LIAISON_I = new Set(["de", "du", "des", "d", "en", "pour", "a", "au", "aux", "l", "la", "le", "et"]);
function plurielI(lib) { let fige = false; return String(lib).toLowerCase().split(" ").map(mot => { const m = mot.match(/^(.*?)([,.;]*)$/), corps = m[1], ponct = m[2];
  if (fige || !corps || LIAISON_I.has(corps.split("'")[0]) || corps.startsWith("(")) { fige = true; return mot; }
  return corps.split("-").map(p => !p || /[sx]$/.test(p) ? p : (/al$/.test(p) ? p.slice(0, -2) + "aux" : p + "s")).join("-") + ponct; }).join(" "); }
const phraseGini = g => g < .2 ? "assez homogène sur le territoire" : g < .35 ? "modérément inégale" : g < .5 ? "nettement inégale" : "très concentrée dans certains territoires";
const f2 = fr.format(",.2f");
const borneIC = v => Math.abs(v) < .005 ? fr.format(",.3f")(v) : f2(v);
const MI = {lib: 0, sal: 1, all: 2};
const MODES = [["all", "tous modes d'exercice"], ["lib", "libéral"], ["sal", "salarié"]];
const NIV_I = {dep: ["Départements", "départements", "un département", "des départements"], epci: ["Intercommunalités", "intercommunalités", "une intercommunalité", "des intercommunalités"]};
const libI = p => DI.profs[p].lib;
const SM_DEF = {sm: "psychologue", sante: "medecin_generaliste", tout: "psychologue"};
Object.keys(DEFAUTS).forEach(f => DEFAUTS[f].iProf = SM_DEF[f]);
Object.assign(ETAT, {iProf: DEFAUTS[ETAT.fam].iProf, iNiv: "epci", iMode: "all", iType: null});

// densités, toujours comparées à l'ensemble des territoires du même niveau, calculé de la même façon (refD de l'atlas)
const MOY_I = {};
// unité de chaque profession (10 000 ou 100 000 habitants, pipeline/explorer.py « unites ») et écriture des densités
// comme sur les autres pages (affichage.nombre : 0 seul, deux décimales sous 1) ; les séries calculées d'avance par le
// programme (escalier, limites de l'entonnoir) sont enregistrées pour 10 000 et ramenées à l'unité par kI
const FAC_I = p => (DI.unites && DI.unites[p]) || 1e4, kI = p => FAC_I(p) / 1e4;
const uniteI = (p, court) => (FAC_I(p) === 1e5 ? "pour 100 000 " : "pour 10 000 ") + (court ? "hab." : "habitants");
const fI2 = new Intl.NumberFormat("fr-FR", {minimumFractionDigits: 2, maximumFractionDigits: 2}), fI1 = new Intl.NumberFormat("fr-FR", {minimumFractionDigits: 1, maximumFractionDigits: 1}), fI0 = new Intl.NumberFormat("fr-FR", {maximumFractionDigits: 0});
const nbI = s => +s.replace(/[\s\u202f\u00a0]/g, "").replace(",", ".").replace("\u2212", "-");
function fDI(v) { if (v == null || !isFinite(v)) return ""; const s2 = fI2.format(v); if (nbI(s2) === 0) return "0"; if (Math.abs(nbI(s2)) < 1) return s2; const s1 = fI1.format(v); return Math.abs(nbI(s1)) >= 1000 ? fI0.format(v) : s1; }
function refI(lv, p, m = "all") { const k = lv + "|" + p + "|" + m; if (!(k in MOY_I)) { const L = DI.niv[lv], a = L.n[p];
  let n = 0, P = 0; L.units.forEach((u, i) => { P += u[2]; if (a) n += a[m][i]; }); MOY_I[k] = P ? n / P * FAC_I(p) : 0; } return MOY_I[k]; }
const nI = (lv, p, i, m = "all") => DI.niv[lv].n[p] ? DI.niv[lv].n[p][m][i] : 0;
const dI = (lv, p, i, m = "all") => { const pop = DI.niv[lv].units[i][2]; return pop ? nI(lv, p, i, m) / pop * FAC_I(p) : 0; };
const natNI = (p, m) => (DI.france.n[p] || [0, 0, 0])[MI[m]];
const natDI = (p, m) => natNI(p, m) / DI.france.pop * FAC_I(p);

// petits outils de dessin, mêmes classes que les autres figures d'Explorer (styles figés par figer() pour l'export)
// figures dessinées à la largeur réelle de leur fenêtre, pour que les textes gardent leur taille sur un téléphone
const largeur = div => Math.max(320, Math.min(1400, Math.round(div.getBoundingClientRect().width) || 1000));
const haut = (w, h) => Math.round(w < 640 ? h * .82 : h);
function svgI(div, w, h, aria) { div._ancien = div.querySelector(":scope > svg"); div.innerHTML = ""; return d3.select(div).append("svg").attr("xmlns", "http://www.w3.org/2000/svg").attr("viewBox", `0 0 ${w} ${h}`).attr("role", "img").attr("aria-label", aria); }
function grilleY(svg, y, m, w, n) { svg.append("g").attr("class", "grillage").selectAll("line").data(y.ticks(n)).join("line").attr("x1", m.l).attr("x2", w - m.r).attr("y1", y).attr("y2", y); }
function axeY(svg, y, m, n, fmt) { svg.append("g").attr("class", "axe").attr("transform", `translate(${m.l - 6},0)`).call(d3.axisLeft(y).ticks(n).tickFormat(fmt).tickSize(0).tickPadding(6)).call(s => s.select(".domain").remove()); }
function axeX(svg, x, h, m, gen) { svg.append("g").attr("class", "axe").attr("transform", `translate(0,${h - m.b + 4})`).call(gen(x).tickSize(0).tickPadding(8)).call(s => s.select(".domain").remove()); }
// valeur écrite sur une barre, avec un liseré de la couleur du fond pour ne jamais se mêler à une ligne de référence
const halo = s => s.attr("paint-order", "stroke").attr("stroke", "var(--fen-corps, #FFFFFF)").attr("stroke-width", 4).attr("stroke-linejoin", "round");
// une courbe se lit dans la légende par un bout de son tracé (couleur et tireté), une barre par un carré
function legende(id, items) { document.getElementById(id).innerHTML = items.map(([c, t, tiret, trace]) => trace !== undefined
  ? `<span><svg class="trace" width="26" height="10" aria-hidden="true"><line x1="1" y1="5" x2="25" y2="5" stroke="${c}" stroke-width="2.5"${trace ? ` stroke-dasharray="${trace}"` : ""}/></svg>${t}</span>`
  : `<span><i class="${tiret ? "tiret" : "carre"}"${tiret ? "" : ` style="background:${c}"`}></i>${t}</span>`).join(""); }
const tableau = (cap, tete, lignes) => `<table><caption>${cap}</caption><thead><tr>${tete.map(t => `<th>${t}</th>`).join("")}</tr></thead><tbody>` + lignes.map(l => `<tr>${l.map(v => `<td>${v}</td>`).join("")}</tr>`).join("") + "</tbody></table>";

// ---------------------------------------------------------------- réglages de la question
function reglagesInegalites(apres) {
  if (!DI.profs[ETAT.iProf] || !dansFamille(DI.profs[ETAT.iProf])) ETAT.iProf = DEFAUTS[ETAT.fam].iProf;
  if (!NIV_I[ETAT.iNiv]) ETAT.iNiv = "epci";
  liste("iProf", DI.profs, [ETAT.iProf], p => ETAT.iProf = p, [], apres);
  choix("iNiv", Object.entries(NIV_I).map(([k, v]) => [k, v[0]]), v => v === ETAT.iNiv, v => ETAT.iNiv = v, apres);
  // retour vers la carte de l'atlas, même profession, même niveau, même famille (l'atlas lit ces réglages dans l'adresse)
  const a = document.getElementById("iVersAtlas");
  if (a) a.href = a.getAttribute("href").split("#")[0] + `#?fam=${ETAT.fam}&prof=${encodeURIComponent(ETAT.iProf)}&niv=${ETAT.iNiv}`;
}

// ---------------------------------------------------------------- selon le niveau de vie (escalier)
function escalierI() {
  const lv = ETAT.iNiv, p = ETAT.iProf, lab = libI(p), R = DI.revenu, v0 = R.escalier?.[lv]?.[p], v = v0 ? v0.map(x => x == null ? x : x * kI(p)) : v0, b = R.bornes?.[lv];
  const c = (R.concentration || []).find(r => r.niv === lv && r.prof === p), nd = refI(lv, p, "all");
  const div = document.getElementById("iEscalier");
  document.getElementById("iEsTitre").textContent = `${cap(plurielI(lab))} ${uniteI(p)} selon le niveau de vie médian des ${NIV_I[lv][1]}, dix tranches de population égale, tous modes d'exercice`;
  if (!v) { div.innerHTML = `<p class="small muted">Pas de données de niveau de vie pour cette profession.</p>`; document.getElementById("iEsResultat").textContent = ""; document.getElementById("iEsLegende").innerHTML = ""; return; }
  // couleur d'écart seulement hors de 0,8 à 1,25 fois l'ensemble (décision de Lucas du 30 octobre 2026) ; chaque tranche
  // réunit un dixième de la population, le hasard n'y joue presque pas
  const coulEs = d => d < .8 * nd ? "var(--d1, #BC6B3B)" : d > 1.25 * nd ? "var(--r3, #1C5652)" : "var(--d3, #ABAEB4)";
  legende("iEsLegende", [["var(--d1, #BC6B3B)", `moins de 0,8 fois l'ensemble ${NIV_I[lv][3]}`], ["var(--d3, #ABAEB4)", "proche de l'ensemble"], ["var(--r3, #1C5652)", "plus de 1,25 fois"], [null, `ensemble ${NIV_I[lv][3]}, ${fDI(nd)}`, true]]);
  const w = largeur(div), h = haut(w, 380), m = {l: 52, r: 16, t: 22, b: 48}, svg = svgI(div, w, h, document.getElementById("iEsTitre").textContent);
  const x = d3.scaleBand().domain(d3.range(1, 11)).range([m.l, w - m.r]).padding(.22), y = d3.scaleLinear().domain([0, d3.max(v) * 1.12 || 1]).nice().range([h - m.b, m.t]);
  grilleY(svg, y, m, w, 5); axeY(svg, y, m, 5, f1); axeX(svg, x, h, m, d3.axisBottom);
  svg.selectAll("rect.b").data(v).join("rect").attr("x", (d, i) => x(i + 1)).attr("width", x.bandwidth()).attr("y", d => y(d)).attr("height", d => y(0) - y(d)).attr("rx", 2)
    .attr("fill", coulEs)
    .append("title").text((d, i) => `Tranche ${i + 1}${b ? `, niveau de vie de ${f0(b[i][0])} à ${f0(b[i][1])} €` : ""}, ${fDI(d)} ${uniteI(p, true)}`);
  svg.append("line").attr("class", "repere").attr("x1", m.l).attr("x2", w - m.r).attr("y1", y(nd)).attr("y2", y(nd));
  halo(svg.selectAll("text.v").data(v).join("text").attr("class", "etiq forte").attr("x", (d, i) => x(i + 1) + x.bandwidth() / 2).attr("y", d => y(d) - 6).attr("text-anchor", "middle").text(d => fDI(d)));
  svg.append("text").attr("class", "etiq").attr("x", m.l).attr("y", h - 6).text("Plus modestes");
  svg.append("text").attr("class", "etiq").attr("x", w - m.r).attr("y", h - 6).attr("text-anchor", "end").text("Plus aisés");
  figer(svg.node());
  let ph = "";
  if (c) { const lp = plurielI(lab); ph = (c.lo <= 0 && c.hi >= 0) ? `Les ${lp} ne sont ni plus ni moins présents dans les territoires aisés que dans les territoires modestes`
    : `Les ${lp} sont ${Math.abs(c.c) < .05 ? "à peine" : Math.abs(c.c) < .15 ? "un peu" : "nettement"} plus présents dans les territoires ${c.c > 0 ? "aisés que dans les territoires modestes" : "modestes que dans les territoires aisés"}`;
    ph += ` (indice de concentration ${f2(c.c)}).`; }
  const hi = v.indexOf(d3.max(v)), lo = v.indexOf(d3.min(v));
  ph += ` La tranche la mieux dotée est la ${hi === 0 ? "première" : (hi + 1) + "ᵉ"}, la moins dotée la ${lo === 0 ? "première" : (lo + 1) + "ᵉ"}.`;
  document.getElementById("iEsResultat").textContent = ph.trim();
  document.getElementById("iEsNote").textContent = c ? `Indice de concentration ${f2(c.c)}, intervalle de confiance à 95 % par bootstrap de ${f2(c.lo)} à ${f2(c.hi)}. Tranches pondérées par la population, territoires dont le niveau de vie médian est publié. Tous modes d'exercice.` : "";
  const lignes = v.map((d, i) => [i + 1, b ? b[i][0] : "", b ? b[i][1] : "", d, d / nd * 100 - 100]);
  document.getElementById("iEsTable").innerHTML = tableau(`${cap(plurielI(lab))} ${uniteI(p)} par tranche de niveau de vie, ${NIV_I[lv][1]}`,
    ["Tranche", "Niveau de vie médian, de", "à", cap(uniteI(p, true)), `Écart à l'ensemble ${NIV_I[lv][3]}`],
    lignes.map(l => [`${l[0]}${l[0] === 1 ? ", la plus modeste" : l[0] === 10 ? ", la plus aisée" : ""}`, l[1] === "" ? "" : f0(l[1]) + " €", l[2] === "" ? "" : f0(l[2]) + " €", fDI(l[3]), fp(l[4])]));
  donneesFigure("figIEs", `selon_niveau_de_vie_${p}_${lv}.csv`, [["tranche", "niveau_de_vie_min", "niveau_de_vie_max", `densite_pour_${FAC_I(p)}`, "ensemble_des_territoires"], ...lignes.map(l => [l[0], l[1], l[2], l[3], nd])]);
}

// ---------------------------------------------------------------- écarts qui dépassent le hasard (entonnoir)
const STATUT_I = {"-2": "nettement en dessous de l'ensemble des territoires, au-delà de ce que le hasard expliquerait", "-1": "en dessous de l'ensemble des territoires, un écart que le hasard expliquerait rarement",
  "0": "proche de l'ensemble des territoires, l'écart peut tenir au hasard", "1": "au-dessus de l'ensemble des territoires, un écart que le hasard expliquerait rarement", "2": "nettement au-dessus de l'ensemble des territoires, au-delà de ce que le hasard expliquerait"};
const COUL_STATUT = s => s <= -2 ? "var(--d0, #83451E)" : s === -1 ? "var(--d1, #BC6B3B)" : s >= 2 ? "var(--d6, #0E5A5A)" : s === 1 ? "var(--d5, #2A6B66)" : "var(--muted, #5D6371)";
function entonnoirI() {
  const lv = ETAT.iNiv, p = ETAT.iProf, lab = libI(p), lim0 = DI.entonnoir?.limites?.[lv]?.[p], lim = lim0 ? lim0.map(r => [r[0], ...r.slice(1).map(x => x * kI(p))]) : lim0, st = DI.niv[lv].statut?.[p];
  const div = document.getElementById("iEntonnoir");
  document.getElementById("iEnTitre").textContent = `${cap(plurielI(lab))} ${uniteI(p)} selon la population des ${NIV_I[lv][1]}, avec les limites de ce que le hasard pourrait produire, tous modes d'exercice`;
  if (!lim) { div.innerHTML = `<p class="small muted">Profession trop peu nombreuse pour ce diagramme.</p>`; document.getElementById("iEnResultat").textContent = ""; document.getElementById("iEnLegende").innerHTML = ""; return; }
  const L = DI.niv[lv], pts = L.units.map((u, i) => ({u, i, x: u[2], y: dI(lv, p, i), s: st ? st[i] : null})).filter(d => d.x > 0), nd = refI(lv, p, "all");
  legende("iEnLegende", [["var(--d0, #83451E)", "nettement en dessous"], ["var(--d1, #BC6B3B)", "en dessous"], ["var(--muted, #5D6371)", "proche de l'ensemble"], ["var(--d5, #2A6B66)", "au-dessus"], ["var(--d6, #0E5A5A)", "nettement au-dessus"], [null, `ensemble ${NIV_I[lv][3]}, ${fDI(nd)}`, true]]);
  const w = largeur(div), h = haut(w, 460), m = {l: 52, r: 16, t: 14, b: 44}, svg = svgI(div, w, h, document.getElementById("iEnTitre").textContent);
  const x = d3.scaleLog().domain(d3.extent(pts, d => d.x)).nice().range([m.l, w - m.r]);
  const ymax = Math.max(d3.quantile(pts.map(d => d.y).sort(d3.ascending), .98) || 1, d3.max(lim, r => r[2]) * .5 || 1) * 1.1;
  const y = d3.scaleLinear().domain([0, ymax]).range([h - m.b, m.t]).clamp(true);
  grilleY(svg, y, m, w, 5); axeY(svg, y, m, 5, f1);
  // graduations aux puissances de dix seulement, l'échelle logarithmique se lit ainsi sans chevauchement
  axeX(svg, x, h, m, s => d3.axisBottom(s).tickValues(s.ticks().filter(v => /^10*$/.test(String(Math.round(v))))).tickFormat(f0));
  const lp = lim.filter(r => r[0] >= x.domain()[0] && r[0] <= x.domain()[1]);
  svg.append("path").datum(lp).attr("fill", "var(--r1, #3B7E78)").attr("opacity", .35).attr("d", d3.area().x(r => x(r[0])).y0(r => y(r[1])).y1(r => y(r[2])));
  [3, 4].forEach(k => svg.append("path").datum(lp).attr("fill", "none").attr("stroke", "var(--muted, #5D6371)").attr("stroke-dasharray", "3 3").attr("d", d3.line().x(r => x(r[0])).y(r => y(r[k]))));
  svg.append("line").attr("class", "repere").attr("x1", m.l).attr("x2", w - m.r).attr("y1", y(nd)).attr("y2", y(nd));
  svg.append("g").selectAll("circle").data(pts).join("circle").attr("cx", d => x(d.x)).attr("cy", d => y(d.y)).attr("r", 2.6)
    .attr("fill", d => COUL_STATUT(d.s)).attr("fill-opacity", .8).append("title").text(d => `${d.u[1]}, ${f0(d.x)} hab., ${fDI(d.y)} ${uniteI(p, true)}, ${STATUT_I[String(d.s)] || "statut non calculé"}`);
  svg.append("text").attr("class", "etiq").attr("x", w - m.r).attr("y", h - 6).attr("text-anchor", "end").text("habitants, échelle logarithmique");
  figer(svg.node());
  const rs = DI.entonnoir?.resume?.[lv]?.[p];
  document.getElementById("iEnResultat").textContent = rs ? `${cap(pc(rs.pop_sous998))} des habitants vivent dans ${NIV_I[lv][2]} nettement en dessous de l'ensemble ${NIV_I[lv][3]} pour les ${plurielI(lab)}, au-delà de ce que le hasard pourrait expliquer.` : "";
  document.getElementById("iEnNote").textContent = rs ? `Limites de Poisson à 95 % et 99,8 % autour de l'ensemble ${NIV_I[lv][3]}, tous modes d'exercice. ${f1(rs.hors95 * 100)} % des territoires sont hors des limites à 95 %, contre 5 % si seul le hasard jouait. Cette surdispersion montre que les écarts ne sont pas aléatoires. Les limites ne sont pas élargies pour en tenir compte.` : "";
  const tri = [...pts].sort((a, b) => (a.s ?? 0) - (b.s ?? 0) || a.y - b.y);
  document.getElementById("iEnTable").innerHTML = tableau(`${cap(NIV_I[lv][1])}, densité de ${plurielI(lab)} et situation au regard du hasard`, [cap(NIV_I[lv][1].replace(/s$/, "")), "Habitants", cap(uniteI(p, true)), "Situation"],
    tri.map(d => [d.u[1], f0(d.x), fDI(d.y), STATUT_I[String(d.s)] || "non calculée"]));
  donneesFigure("figIEn", `ecarts_hasard_${p}_${lv}.csv`, [["code", "territoire", "habitants", `densite_pour_${FAC_I(p)}`, "statut"], ...pts.map(d => [d.u[0], d.u[1], d.x, d.y, d.s])]);
}

// ---------------------------------------------------------------- concentration de l'offre (Lorenz et professions classées)
function lorenzI(lv, p, m) {
  const L = DI.niv[lv], a = L.units.map((u, i) => ({pop: u[2], n: nI(lv, p, i, m)})).filter(d => d.pop > 0).sort((x, y) => x.n / x.pop - y.n / y.pop);
  const P = d3.sum(a, d => d.pop), N = d3.sum(a, d => d.n) || 1; let cx = 0, cy = 0, g = 0; const pts = [[0, 0]];
  for (const d of a) { const nx = cx + d.pop / P, ny = cy + d.n / N; g += (nx - cx) * (ny + cy); cx = nx; cy = ny; pts.push([cx, cy]); }
  return {pts, gini: 1 - g};
}
function concentrationI(apres) {
  const lv = ETAT.iNiv, md = ETAT.iMode, p = ETAT.iProf;
  choix("iMode", MODES, v => v === md, v => ETAT.iMode = v, apres);
  const ref = ETAT.fam === "sm" ? ["psychologue", "psychiatre", "pedopsychiatre"] : ETAT.fam === "sante" ? ["medecin_generaliste", "infirmier", "masseur_kinesitherapeute"] : ["medecin_generaliste", "psychologue", "psychiatre"];
  const comp = [p, ...ref].filter((q, i, a) => DI.profs[q] && DI.niv[lv].n[q] && a.indexOf(q) === i).slice(0, 4);
  // la profession choisie en canard et plus épaisse, les professions de comparaison en catégories du site, chacune avec
  // son tracé (trois tons de canard proches se confondaient, remarque de Lucas du 31 octobre 2026 ; l'ocre est réservé
  // au signal « ! »)
  const cols = ["var(--action, #0E5A5A)", "var(--c1, #B473A4)", "var(--c2, #2E672F)", "var(--c3, #998E3B)"], tirets = [null, "7 3", "2 3", "9 3 2 3"];
  document.getElementById("iLoTitre").textContent = `Part cumulée des professionnels selon la part cumulée de la population, ${NIV_I[lv][1]} classées de la moins à la mieux dotée, ${MODES.find(x => x[0] === md)[1]}`;
  const courbes = comp.map(q => ({q, l: lorenzI(lv, q, md)}));
  legende("iLoLegende", courbes.map((c, k) => [cols[k], `${libI(c.q)}, Gini ${f2(c.l.gini)}`, false, tirets[k]]).concat([[null, "répartition parfaitement égale", true]]));
  const w = largeur(document.getElementById("iLorenz")), h = haut(w, 520), m = {l: 52, r: 16, t: 14, b: 44}, svg = svgI(document.getElementById("iLorenz"), w, h, document.getElementById("iLoTitre").textContent);
  const x = d3.scaleLinear().range([m.l, w - m.r]), y = d3.scaleLinear().range([h - m.b, m.t]), pct = v => fr.format(",.0f")(v * 100) + " %";
  grilleY(svg, y, m, w, 5); axeY(svg, y, m, 5, pct); axeX(svg, x, h, m, s => d3.axisBottom(s).ticks(5).tickFormat(pct));
  svg.append("line").attr("class", "repere").attr("x1", x(0)).attr("y1", y(0)).attr("x2", x(1)).attr("y2", y(1));
  courbes.forEach((c, k) => svg.append("path").datum(c.l.pts).attr("class", "courbe").attr("stroke", cols[k]).attr("stroke-dasharray", tirets[k]).attr("stroke-width", k === 0 ? 2.75 : 1.75).attr("d", d3.line().x(d => x(d[0])).y(d => y(d[1]))));
  svg.append("text").attr("class", "etiq").attr("x", w - m.r).attr("y", h - 6).attr("text-anchor", "end").text("part cumulée de la population");
  // titre de l'axe vertical, dans le coin haut gauche que les courbes laissent vide (relecture du 5 novembre 2026)
  svg.append("text").attr("class", "etiq").attr("x", m.l + 8).attr("y", m.t + 12).text("part cumulée des professionnels");
  figer(svg.node());
  const l0 = courbes[0].l, pts = l0.pts; let y20 = 0;
  for (let k = 1; k < pts.length; k++) if (pts[k][0] >= .2) { const [a0, b0] = pts[k - 1], [a1, b1] = pts[k]; y20 = a1 > a0 ? b0 + (b1 - b0) * (.2 - a0) / (a1 - a0) : b1; break; }
  document.getElementById("iCoResultat").textContent = `Les 20 % d'habitants les moins bien dotés disposent de ${f1(y20 * 100)} % des ${plurielI(libI(p))}. Avec une répartition parfaitement égale, ils en auraient 20 %. La répartition est ${phraseGini(l0.gini)} (indice de Gini ${f2(l0.gini)}).`;
  const rows = Object.keys(DI.profs).filter(q => dansFamille(DI.profs[q]) && DI.niv[lv].n[q] && natNI(q, md) > 0).map(q => {
    const l = lorenzI(lv, q, md), L = DI.niv[lv]; let z = 0, P = 0; L.units.forEach((u, i) => { P += u[2]; if (nI(lv, q, i, md) === 0) z += u[2]; });
    return {q, g: l.gini, z: z / P, d: natDI(q, md)}; }).sort((a, b) => b.g - a.g);
  document.getElementById("iCoTable").innerHTML = tableau(`Professions classées par concentration entre ${NIV_I[lv][1]}, ${MODES.find(x => x[0] === md)[1]}`, ["Profession", "Indice de Gini", "Habitants sans aucun professionnel dans leur territoire", "Densité, France"],
    rows.map(r => [`<button type="button" class="lien-prof" data-p="${r.q}"${r.q === p ? ' aria-current="true"' : ""}>${libI(r.q)}</button>`, f2(r.g), pc(r.z), `${fDI(r.d)} ${uniteI(r.q, true)}`]));
  document.querySelectorAll("#iCoTable .lien-prof").forEach(b => b.onclick = () => { ETAT.iProf = b.dataset.p; apres(); });
  donneesFigure("figILo", `concentration_${lv}_${md}.csv`, [["profession", "gini", "part_habitants_sans_professionnel", "densite_france", "pour_habitants"], ...rows.map(r => [libI(r.q), r.g, r.z, r.d, FAC_I(r.q)])]);
}

// ---------------------------------------------------------------- distances aux structures de soins
function distancesI(apres) {
  const LX = DI.lieux, types = (LX.types || []).filter(t => t.complet && (LX.escalier || []).some(r => r.type === t.id) && (ETAT.fam === "tout" || t.famille === nomFamille()));
  const bloc = document.getElementById("qDistances"); bloc.hidden = !types.length; if (!types.length) return;
  if (!ETAT.iType || !types.some(t => t.id === ETAT.iType)) ETAT.iType = (types.find(t => t.id === (ETAT.fam === "sante" ? "lieu_urgences" : "lieu_cmp_adultes")) || types[0]).id;
  const infos = Object.fromEntries(types.map(t => [t.id, {lib: t.lib, groupe: t.groupe || "Structures", famille: t.famille, entier: true}]));
  liste("iType", infos, [ETAT.iType], v => ETAT.iType = v, [], apres);
  const ty = types.find(t => t.id === ETAT.iType), lib = /^[A-ZÉ]{2}/.test(ty.lib) ? ty.lib : ty.lib.charAt(0).toLowerCase() + ty.lib.slice(1), frm = LX.fr?.[ty.id]?.[0];
  // selon le niveau de vie
  const es = LX.escalier.filter(r => r.type === ty.id).sort((a, b) => a.decile - b.decile), v = es.map(r => r.distance_mediane_km);
  document.getElementById("iDnTitre").textContent = `Distance médiane à la structure la plus proche (${lib}) selon le niveau de vie médian des intercommunalités, dix tranches de population égale, en km`;
  // distances en barres neutres, comme sur la fiche d'un territoire où seule l'offre prend la couleur de l'écart
  // (relecture de l'étape 4, 5 novembre 2026 : « plus loin » en cuivre contredisait le sens des couleurs du site)
  legende("iDnLegende", [["var(--hist, #858B96)", "distance médiane des habitants de la tranche"]].concat(frm != null ? [[null, `distance médiane de tous les habitants, ${f1(frm)} km`, true]] : []));
  const w = largeur(document.getElementById("iDistNv")), h = haut(w, 380), m = {l: 52, r: 16, t: 22, b: 48}, svg = svgI(document.getElementById("iDistNv"), w, h, document.getElementById("iDnTitre").textContent);
  const x = d3.scaleBand().domain(d3.range(1, 11)).range([m.l, w - m.r]).padding(.22), y = d3.scaleLinear().domain([0, Math.max(d3.max(v), frm || 0) * 1.15 || 1]).nice().range([h - m.b, m.t]);
  grilleY(svg, y, m, w, 5); axeY(svg, y, m, 5, f1); axeX(svg, x, h, m, d3.axisBottom);
  svg.selectAll("rect.b").data(es).join("rect").attr("x", d => x(d.decile)).attr("width", x.bandwidth()).attr("y", d => y(d.distance_mediane_km)).attr("height", d => y(0) - y(d.distance_mediane_km)).attr("rx", 2)
    .attr("fill", "var(--hist, #858B96)")
    .append("title").text(d => `Tranche ${d.decile}, niveau de vie de ${f0(d.niveau_de_vie_min)} à ${f0(d.niveau_de_vie_max)} €, distance médiane ${f1(d.distance_mediane_km)} km, ${f1(d.part_plus_20_km * 100)} % des habitants à plus de 20 km`);
  if (frm != null) svg.append("line").attr("class", "repere").attr("x1", m.l).attr("x2", w - m.r).attr("y1", y(frm)).attr("y2", y(frm));
  halo(svg.selectAll("text.v").data(es).join("text").attr("class", "etiq forte").attr("x", d => x(d.decile) + x.bandwidth() / 2).attr("y", d => y(d.distance_mediane_km) - 6).attr("text-anchor", "middle").text(d => f1(d.distance_mediane_km)));
  svg.append("text").attr("class", "etiq").attr("x", m.l).attr("y", h - 6).text("Plus modestes");
  svg.append("text").attr("class", "etiq").attr("x", w - m.r).attr("y", h - 6).attr("text-anchor", "end").text("Plus aisés");
  figer(svg.node());
  const c = (LX.concentration || []).find(r => r.type === ty.id);
  let ph = `La moitié des habitants de la tranche la plus modeste vit à moins de ${f1(v[0])} km de la structure la plus proche (${lib}), contre ${f1(v[9])} km pour la tranche la plus aisée.`;
  if (c) ph += (c.ic95_bas <= 0 && c.ic95_haut >= 0) ? " L'éloignement n'a pas de lien net avec le niveau de vie." : ` L'éloignement pèse ${Math.abs(c.indice_concentration) < .15 ? "un peu " : ""}davantage sur les territoires ${c.indice_concentration < 0 ? "modestes" : "aisés"}.`;
  document.getElementById("iDnResultat").textContent = ph;
  document.getElementById("iDnNote").textContent = c ? `Indice de concentration des habitants-kilomètres selon le niveau de vie ${f2(c.indice_concentration)}, fourchette plausible à 95 % de ${borneIC(c.ic95_bas)} à ${borneIC(c.ic95_haut)} (tirages des intercommunalités). Il vaut 0 quand l'éloignement suit la population, il est négatif quand il pèse surtout sur les territoires modestes. Les intercommunalités sans niveau de vie publié (Guadeloupe, Martinique, Guyane, Mayotte) sont écartées. Une intercommunalité très peuplée peut remplir presque seule une tranche, d'où des ruptures dans l'escalier.` : "";
  document.getElementById("iDnTable").innerHTML = tableau(`Distance médiane à la structure la plus proche (${lib}) par tranche de niveau de vie`, ["Tranche", "Niveau de vie médian, de", "à", "Distance médiane, km", "Habitants à plus de 20 km"],
    es.map(d => [d.decile, f0(d.niveau_de_vie_min) + " €", f0(d.niveau_de_vie_max) + " €", f1(d.distance_mediane_km), pc(d.part_plus_20_km)]));
  donneesFigure("figIDn", `distance_niveau_de_vie_${ty.id}.csv`, [["tranche", "niveau_de_vie_min", "niveau_de_vie_max", "distance_mediane_km", "part_plus_20_km"], ...es.map(d => [d.decile, d.niveau_de_vie_min, d.niveau_de_vie_max, d.distance_mediane_km, d.part_plus_20_km])]);
  // selon le type de territoire
  const cl = (LX.classes || []).filter(r => r.type === ty.id), dm = cl.map(r => r.distance_mediane_km);
  document.getElementById("iDtTitre").textContent = `Distance médiane à la structure la plus proche (${lib}) selon la densité de population des intercommunalités, en km`;
  const etroit = w < 640, nomC = c => etroit ? c.split(" (")[0] : c;
  const h2 = 60 + cl.length * 54, m2 = {l: etroit ? 130 : 300, r: 70, t: 8, b: 40}, s2 = svgI(document.getElementById("iDistType"), w, h2, document.getElementById("iDtTitre").textContent);
  const y2 = d3.scaleBand().domain(cl.map(r => r.classe)).range([m2.t, h2 - m2.b]).padding(.3), x2 = d3.scaleLinear().domain([0, d3.max(dm) * 1.1 || 1]).nice().range([m2.l, w - m2.r]);
  s2.append("g").attr("class", "grillage").selectAll("line").data(x2.ticks(5)).join("line").attr("x1", x2).attr("x2", x2).attr("y1", m2.t).attr("y2", h2 - m2.b);
  axeX(s2, x2, h2, m2, s => d3.axisBottom(s).ticks(5).tickFormat(f1));
  s2.selectAll("text.c").data(cl).join("text").attr("class", "etiq forte").attr("x", m2.l - 14).attr("y", d => y2(d.classe) + y2.bandwidth() / 2 + 4).attr("text-anchor", "end").text(d => nomC(d.classe));
  s2.selectAll("rect").data(cl).join("rect").attr("x", m2.l).attr("y", d => y2(d.classe)).attr("height", y2.bandwidth()).attr("width", d => x2(d.distance_mediane_km) - m2.l).attr("rx", 2)
    .attr("fill", "var(--hist, #858B96)")
    .append("title").text(d => `${d.classe}, ${f0(d.population)} habitants, distance médiane ${f1(d.distance_mediane_km)} km, ${f1(d.part_plus_20_km * 100)} % à plus de 20 km`);
  s2.selectAll("text.v").data(cl).join("text").attr("class", "etiq forte").attr("x", d => x2(d.distance_mediane_km) + 8).attr("y", d => y2(d.classe) + y2.bandwidth() / 2 + 4).text(d => `${f1(d.distance_mediane_km)} km`);
  s2.append("text").attr("class", "etiq").attr("x", w - m2.r).attr("y", h2 - 4).attr("text-anchor", "end").text("distance médiane, en km");
  figer(s2.node());
  const proche = cl[dm.indexOf(d3.min(dm))], loin = cl[dm.indexOf(d3.max(dm))];
  document.getElementById("iDtResultat").textContent = cl.length ? `Selon le type de territoire, la distance médiane à la structure la plus proche (${lib}) va de ${f1(d3.min(dm))} km (${proche.classe.split(" (")[0].toLowerCase()}) à ${f1(d3.max(dm))} km (${loin.classe.split(" (")[0].toLowerCase()}).` : "";
  const te = (LX.tests || []).find(r => r.type === ty.id);
  document.getElementById("iDtNote").textContent = te ? `Test de Kruskal-Wallis sur les distances médianes des intercommunalités, epsilon carré ${f2(te.epsilon2)} (part des écarts entre intercommunalités qui tient au type de territoire), q-valeur de Benjamini-Hochberg ${te.q_bh < .001 ? "inférieure à 0,001" : f2(te.q_bh)}. Classes de densité de population des intercommunalités, les mêmes que pour les professions. Ce n'est pas un temps de trajet, et une structure n'est pas une capacité.` : "";
  document.getElementById("iDtTable").innerHTML = tableau(`Distance médiane à la structure la plus proche (${lib}) selon la densité de population`, ["Type de territoire", "Habitants", "Distance médiane, km", "Habitants à plus de 20 km"],
    cl.map(d => [d.classe, f0(d.population), f1(d.distance_mediane_km), pc(d.part_plus_20_km)]));
  donneesFigure("figIDt", `distance_type_territoire_${ty.id}.csv`, [["classe", "habitants", "distance_mediane_km", "part_plus_20_km"], ...cl.map(d => [d.classe, d.population, d.distance_mediane_km, d.part_plus_20_km])]);
}

// redessin quand une fenêtre change de largeur (agrandie, rendue, écran tourné)
let ATTENTE_I = null;
const redessinerI = () => { clearTimeout(ATTENTE_I); ATTENTE_I = setTimeout(() => { escalierI(); entonnoirI(); concentrationI(() => { inegalites(); ecrireAdresse("qInegalites"); }); distancesI(() => { inegalites(); ecrireAdresse("qDistances"); }); }, 120); };
addEventListener("fenetre", redessinerI); addEventListener("resize", redessinerI);
function inegalites() {
  const apres = () => { inegalites(); ecrireAdresse("qInegalites"); };
  const apresD = () => { inegalites(); ecrireAdresse("qDistances"); };
  reglagesInegalites(apres);
  escalierI(); entonnoirI(); concentrationI(apres); distancesI(apresD);
  if (window.cesure) { window.cesure(document.getElementById("qInegalites")); window.cesure(document.getElementById("qDistances")); }
}
