// Explorer, typologie des intercommunalités et analyse en composantes principales, reprises de l'onglet Typologie de
// l'atlas (lot 3, note docs/note_explorer_atlas_2026-10-28.md). Même calcul, mêmes noms de groupes et mêmes phrases
// que l'atlas, données de site_data.json (pipeline/explorer.py, DI.typo). Chargé après explorer.js et
// explorer_inegalites.js, dont il reprend les outils (formats, pluriel, tableaux, dessin à la largeur de la fenêtre).

const PAL_T = d3.schemeTableau10;              // couleurs des groupes, les mêmes que dans l'atlas et les rapports
const couleurT_ = c => PAL_T[(c - 1) % 10];
const famT = () => ETAT.fam === "sante" ? "sante" : ETAT.fam === "tout" ? "tout" : "sm";
const libT = p => (DI.typo.libelles[p] || [p])[0];
const groupeT = p => (DI.typo.libelles[p] || [p, "Autres médecins"])[1];
const listeT = ps => { ps = ps.slice(0, 3).map(plurielI); return ps.length === 1 ? ps[0] : ps.slice(0, -1).join(", ") + " et " + ps[ps.length - 1]; };
const habitantsT = n => n >= 1e6 ? f1(n / 1e6) + " million" + (n >= 2e6 ? "s" : "") + " d'habitants" : f0(Math.round(n / 1e3) * 1e3) + " habitants";
// nom d'un groupe, celui calculé par le programme (meta.noms_classes), sinon le même calcul que l'atlas
function nomClasseT(ind) { const ks = Object.keys(ind); if (!ks.length) return ""; const n = ks.length;
  const bas = ks.filter(p => ind[p] < 80).sort((a, b) => ind[a] - ind[b]), haut = ks.filter(p => ind[p] > 120).sort((a, b) => ind[b] - ind[a]);
  if (bas.length >= .8 * n) { const s = ks.filter(p => ind[p] >= 100); return "Territoires moins dotés pour presque toutes les professions" + (s.length ? ", sauf pour les " + listeT(s) : ""); }
  if (haut.length >= .8 * n) { const s = ks.filter(p => ind[p] <= 100); return "Territoires mieux dotés pour presque toutes les professions" + (s.length ? ", sauf pour les " + listeT(s) : ""); }
  if (bas.length >= .5 * n) return "Territoires plutôt moins dotés, surtout pour les " + listeT(bas);
  if (haut.length >= .5 * n) return "Territoires plutôt mieux dotés, surtout pour les " + listeT(haut);
  if (!bas.length && !haut.length) return "Territoires proches de la moyenne";
  const m = []; if (bas.length) m.push("moins dotés pour les " + listeT(bas)); if (haut.length) m.push("mieux dotés pour les " + listeT(haut));
  return "Territoires proches de la moyenne, " + m.join(", "); }
// case d'indice colorée sur l'échelle encre et cuivre de l'atlas, texte de contraste au moins 4,5
const DIV_T = () => ["--d0", "--d1", "--d2", "--d3", "--d4", "--d5", "--d6"].map(v => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || "#888");
function lumT(f) { const c = d3.rgb(f), l = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * l(c.r) + .7152 * l(c.g) + .0722 * l(c.b); }
const contrT = (a, b) => { const x = lumT(a), y = lumT(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
const texteT = f => contrT(f, "#14161B") >= contrT(f, "#F4F4F7") ? "#14161B" : "#F4F4F7";
function caseT(fond) { let f = fond; for (let k = 0; k < 14; k++) { const t = texteT(f); if (contrT(f, t) >= 4.5) break; f = d3.interpolateRgb(f, t === "#14161B" ? "#fff" : "#000")(.12); } return `background:${f};color:${texteT(f)}`; }

const METRO_T = new Set(GEO.map(f => f.properties.epci));
const DEP_T = (() => { const g = TOPO.objects.dep; const geoms = g.geometries.filter(x => { const f = topojson.feature(TOPO, x); const [a, b] = d3.geoCentroid(f); return a > -6 && a < 10 && b > 41 && b < 52; });
  return topojson.mesh(TOPO, {type: "GeometryCollection", geometries: geoms}, (a, b) => a !== b); })();
const IDX_T = Object.fromEntries(DI.niv.epci.units.map((u, i) => [u[0], i]));

function typologieE() {
  const fam = famT(), T = DI.typo, L = DI.niv.epci, cl = T.classe?.[fam], A = T.acp?.[fam];
  const profils = (T.profils || []).filter(r => !r.famille || r.famille === fam), forme = r => r.dans_typologie !== false;
  const classes = [...new Set(profils.map(r => r.classe))].sort((a, b) => a - b), profs = [...new Set(profils.filter(forme).map(r => r.prof))];
  const decrites = [...new Set(profils.filter(r => !forme(r)).map(r => r.prof))], get = new Map(profils.map(r => [r.classe + "|" + r.prof, r]));
  if (!classes.length) { document.getElementById("tyResultat").textContent = "Typologie absente de ce fichier de données."; return; }
  const nomC = c => T.noms[fam + "|" + c] || T.noms[c] || nomClasseT(Object.fromEntries(profs.map(p => [libT(p), get.get(c + "|" + p).indice_vs_national])));
  const r0 = c => get.get(c + "|" + profs[0]);
  const gros = classes.slice().sort((a, b) => r0(b).population - r0(a).population)[0];
  document.getElementById("tyResultat").textContent = `On distingue ${classes.length} groupes d'intercommunalités. Le plus peuplé, « ${nomC(gros)} », réunit ${f0(r0(gros).population)} habitants.` + (A && A.silhouette < .25 ? " Les groupes sont peu séparés, ils découpent un continuum plutôt que des types bien distincts." : "");
  document.getElementById("tyNote").textContent = `Groupes construits à partir des densités ${fam === "sm" ? "de l'offre de santé mentale" : fam === "sante" ? "des principales professions de santé" : "des principales professions, santé et santé mentale ensemble"} (${profs.map(libT).join(", ").toLowerCase()}). Indice 100 pour la moyenne des intercommunalités.`;
  document.getElementById("tyMethode").textContent = A ? `Analyse en composantes principales sur le logarithme des densités, centrées et réduites, puis classification ascendante hiérarchique (méthode de Ward) sur les mêmes données. Nombre de groupes choisi par la silhouette moyenne entre 3 et 6 (${A.classes} groupes, silhouette ${f2(A.silhouette)}). Les groupes réunissent ${Math.round(A.inertie_classes * 100)} % des différences entre intercommunalités. Une silhouette inférieure à 0,25 signale des groupes peu séparés.` : "";
  // carte, une couleur par groupe, frontières des départements
  document.getElementById("tyTitre").textContent = `Groupes d'intercommunalités de l'Hexagone et de la Corse selon le profil de leur offre (${fam === "sm" ? "santé mentale" : fam === "sante" ? "santé" : "toute l'offre"})`;
  const div = document.getElementById("tyCarte"), w = Math.min(640, largeur(div)), h = Math.round(w * 1.02);
  const proj = d3.geoConicConformal().parallels([44, 49]).rotate([-3, 0]).fitSize([w, h], {type: "FeatureCollection", features: GEO}), path = d3.geoPath(proj);
  const svg = svgI(div, w, h, document.getElementById("tyTitre").textContent);
  svg.selectAll("path.territoire").data(GEO).join("path").attr("class", "territoire").attr("d", path)
    .attr("fill", f => { const i = IDX_T[f.properties.epci], c = cl && i != null ? cl[i] : null; return c ? couleurT_(c) : "var(--nodata, #ECECEF)"; })
    .append("title").text(f => { const i = IDX_T[f.properties.epci]; if (i == null) return ""; const u = L.units[i], c = cl?.[i];
      return `${u[1]}, ${T.deps[T.parent[i]] || T.parent[i] || ""}, ${f0(u[2])} habitants${c ? `, groupe « ${nomC(c)} »` : ""}`; });
  svg.append("path").datum(DEP_T).attr("fill", "none").attr("stroke", "var(--ink, #1C2028)").attr("stroke-opacity", .45).attr("stroke-width", .6).attr("d", path);
  figer(svg.node());
  document.getElementById("tyLegende").innerHTML = classes.map(c => `<li><i style="background:${couleurT_(c)}"></i><span>${nomC(c)}</span><span class="n">${f0(r0(c).territoires)} intercommunalités, ${habitantsT(r0(c).population)}</span></li>`).join("");
  donneesFigure("figTy", `typologie_${fam}.csv`, [["code", "intercommunalite", "habitants", "groupe", "nom_du_groupe"],
    ...L.units.map((u, i) => [u[0], u[1], u[2], cl?.[i] ?? "", cl?.[i] ? nomC(cl[i]) : ""])]);
  // profil de chaque groupe, indice 100 pour la moyenne des intercommunalités
  const dv = DIV_T(), sc = d3.scaleThreshold().domain([50, 70, 90, 110, 140, 200]).range(dv);
  let hT = `<table><caption>Densité de chaque profession dans chaque groupe, indice 100 pour la moyenne des intercommunalités</caption><thead><tr><th>Profession</th>${classes.map(c => `<th class="ty-col"><i class="pastille" style="background:${couleurT_(c)}"></i>${nomC(c)}</th>`).join("")}</tr></thead><tbody>`;
  hT += `<tr><td class="muted small">Intercommunalités</td>${classes.map(c => `<td class="muted small">${f0(r0(c).territoires)}</td>`).join("")}</tr>`;
  hT += `<tr><td class="muted small">Habitants</td>${classes.map(c => `<td class="muted small">${f0(Math.round(r0(c).population / 1e3))} k</td>`).join("")}</tr>`;
  const ligne = p => `<tr><td>${libT(p)}</td>${classes.map(c => { const v = get.get(c + "|" + p)?.indice_vs_national; return v == null ? "<td></td>" : `<td style="${caseT(sc(v))}">${f0(Math.round(v))}</td>`; }).join("")}</tr>`;
  profs.forEach(p => hT += ligne(p));
  for (const g of [...new Set(decrites.map(groupeT))]) { hT += `<tr class="ty-sous"><th colspan="${classes.length + 1}">${g}, à titre descriptif, sans servir à former les groupes</th></tr>`; decrites.filter(x => groupeT(x) === g).forEach(p => hT += ligne(p)); }
  const TL = (T.lieux || []).filter(r => r.famille === fam);
  if (TL.length) { const libL = id => ((DI.lieux.types || []).find(x => x.id === id) || {}).lib || id, tl = new Map(TL.map(r => [r.classe + "|" + r.type, r])), tys = [...new Set(TL.map(r => r.type))];
    hT += `<tr class="ty-sous"><th colspan="${classes.length + 1}">Structures de soins pour 100 000 habitants, indice 100 pour la France (FINESS et ROR), à titre descriptif</th></tr>`;
    tys.forEach(ty => hT += `<tr><td>${libL(ty)}</td>${classes.map(c => { const v = tl.get(c + "|" + ty)?.indice_vs_national; return v == null ? "<td></td>" : `<td style="${caseT(sc(v))}">${f0(Math.round(v))}</td>`; }).join("")}</tr>`);
    hT += `<tr class="ty-sous"><th colspan="${classes.length + 1}">Distance médiane des habitants à la structure la plus proche, en km, à titre descriptif</th></tr>`;
    tys.forEach(ty => hT += `<tr><td>${libL(ty)}</td>${classes.map(c => { const v = tl.get(c + "|" + ty)?.distance_mediane_km; return `<td>${v == null ? "" : f1(v)}</td>`; }).join("")}</tr>`); }
  document.getElementById("tyTable").innerHTML = hT + "</tbody></table>";
  acpE(fam, A, cl, nomC);
}

function acpE(fam, A, cl, nomC) {
  const pts = (DI.typo.acp_pts?.[fam] || []).map((v, i) => v && {x: v[0], y: v[1], c: cl?.[i], u: DI.niv.epci.units[i]}).filter(Boolean);
  if (!A || !pts.length) { document.getElementById("acpResultat").textContent = "Analyse absente de ce fichier de données."; return; }
  const ax = A.inertie, ch = Object.entries(A.charges).map(([p, v]) => ({p, a: v[0], b: v[1]})).sort((a, b) => b.a - a.a);
  document.getElementById("acpTitre").textContent = `Intercommunalités placées selon les deux premiers axes de l'analyse en composantes principales, couleur de leur groupe`;
  const div = document.getElementById("acpPlan"), w = largeur(div), h = haut(w, 520), m = {l: 52, r: 16, t: 14, b: 44}, svg = svgI(div, w, h, document.getElementById("acpTitre").textContent);
  const x = d3.scaleLinear().domain(d3.extent(pts, d => d.x)).nice().range([m.l, w - m.r]), y = d3.scaleLinear().domain(d3.extent(pts, d => d.y)).nice().range([h - m.b, m.t]);
  grilleY(svg, y, m, w, 6); axeY(svg, y, m, 6, f1); axeX(svg, x, h, m, s => d3.axisBottom(s).ticks(6).tickFormat(f1));
  svg.append("line").attr("class", "repere").attr("x1", x(0)).attr("x2", x(0)).attr("y1", m.t).attr("y2", h - m.b);
  svg.append("line").attr("class", "repere").attr("x1", m.l).attr("x2", w - m.r).attr("y1", y(0)).attr("y2", y(0));
  svg.append("g").selectAll("circle").data(pts).join("circle").attr("cx", d => x(d.x)).attr("cy", d => y(d.y)).attr("r", 2.6)
    .attr("fill", d => d.c ? couleurT_(d.c) : "var(--muted, #5D6371)").attr("fill-opacity", .8).append("title").text(d => d.u[1] + (d.c ? ", " + nomC(d.c) : ""));
  svg.append("text").attr("class", "etiq").attr("x", w - m.r).attr("y", h - 6).attr("text-anchor", "end").text(`axe 1, ${Math.round(ax[0] * 100)} % des différences`);
  svg.append("text").attr("class", "etiq").attr("x", m.l + 6).attr("y", m.t + 12).text(`axe 2, ${Math.round(ax[1] * 100)} %`);
  figer(svg.node());
  const pos = ch.filter(r => r.b >= .3).sort((a, b) => b.b - a.b).map(r => libT(r.p)), neg = ch.filter(r => r.b <= -.3).sort((a, b) => a.b - b.b).map(r => libT(r.p));
  const memeSens = ch.every(r => r.a > 0);
  let ph = `Le premier axe résume ${Math.round(ax[0] * 100)} % des différences entre intercommunalités. ` + (memeSens ? `Toutes les professions y vont dans le même sens (corrélations de ${f2(d3.min(ch, r => r.a))} à ${f2(d3.max(ch, r => r.a))}). Il distingue les intercommunalités où l'offre est élevée dans l'ensemble de celles où elle est faible.` : "Les professions ne vont pas toutes dans le même sens.");
  if (pos.length && neg.length) ph += ` Le deuxième axe (${Math.round(ax[1] * 100)} %) oppose surtout les territoires relativement mieux dotés en ${listeT(pos)} à ceux relativement mieux dotés en ${listeT(neg)}, à niveau d'offre égal.`;
  document.getElementById("acpResultat").textContent = ph;
  donneesFigure("figAcp", `acp_${fam}.csv`, [["intercommunalite", "axe_1", "axe_2", "groupe"], ...pts.map(d => [d.u[1], d.x, d.y, d.c ?? ""])]);
  // poids de chaque profession dans les deux axes, barres de -1 à +1 autour de zéro
  const barre = v => { const l = v < 0 ? 50 - Math.abs(v) * 50 : 50; return `<svg viewBox="0 0 100 12" preserveAspectRatio="none" aria-hidden="true"><line x1="50" x2="50" y1="0" y2="12" stroke="var(--muted)" stroke-width=".6"/><rect x="${l}" width="${Math.abs(v) * 50}" y="2" height="8" fill="${v < 0 ? "var(--d1, #BC6B3B)" : "var(--d5, #4A77B0)"}"/></svg>`; };
  document.getElementById("acpCharges").innerHTML = `<table><caption>Corrélation de chaque profession avec les deux premiers axes, de −1 à +1</caption><thead><tr><th>Profession</th><th>Axe 1</th><th></th><th>Axe 2</th><th></th></tr></thead><tbody>`
    + ch.map(r => `<tr><td>${libT(r.p)}</td><td>${f2(r.a)}</td><td class="barre-acp">${barre(r.a)}</td><td>${f2(r.b)}</td><td class="barre-acp">${barre(r.b)}</td></tr>`).join("") + "</tbody></table>";
  document.getElementById("acpAxes").innerHTML = `<table><caption>Part des différences entre intercommunalités résumée par chaque axe</caption><thead><tr><th>Axe</th><th>Part des différences</th></tr></thead><tbody>`
    + ax.slice(0, Math.min(4, ax.length)).map((v, i) => `<tr><td>Axe ${i + 1}</td><td>${f1(v * 100)} %</td></tr>`).join("") + "</tbody></table>";
  document.getElementById("acpMethode").textContent = `Les axes sont calculés sur le logarithme des densités centrées et réduites, ils décrivent des territoires et ne disent rien d'une cause.`;
}

let ATTENTE_T = null;
addEventListener("fenetre", () => { clearTimeout(ATTENTE_T); ATTENTE_T = setTimeout(typologieE, 140); });
addEventListener("resize", () => { clearTimeout(ATTENTE_T); ATTENTE_T = setTimeout(typologieE, 140); });
