// Explorer, question « L'addictologie, de l'offre aux consommations » (choix de Lucas du 29 octobre 2026, option C de
// la note docs/note_atlas_2026-10-29.md), reprise de l'encadré « Addictologie » de l'onglet Croisements de l'atlas.
// Même calcul que la partie du rapport santé mentale (pipeline/export.py, _addicto_atlas), données DA écrites par
// pipeline/explorer.py. Régions rangées par ordre alphabétique et non par valeur (pas de palmarès). Les panneaux sont
// côte à côte sur un écran large et s'empilent sur un écran étroit. Chargé après explorer.js et explorer_inegalites.js,
// dont il reprend les outils (formats, dessin à la largeur de la fenêtre, données de la figure).

const AUCUNE_A = "-";
const nomRegA = c => DA.regions[c] || c;
// région à la française dans une phrase (« en Bretagne », « dans les Hauts-de-France », « à La Réunion »)
function enRegionA(c) { const n = nomRegA(c);
  if (/^(La Réunion|Mayotte)$/.test(n)) return "à " + n;
  if (/^(Hauts|Pays)/.test(n)) return "dans les " + n;
  if (/^(Grand Est|Centre)/.test(n)) return "dans le " + n;
  return "en " + n; }
// régions qui ont au moins une mesure, rangées par nom
const regionsA = () => [...new Set(DA.ind.flatMap(i => Object.keys(i.v)))].filter(c => DA.regions[c])
  .sort((a, b) => nomRegA(a).localeCompare(nomRegA(b), "fr"));
// titre coupé en lignes d'au plus n signes
function coupeA(s, n) { const l = []; let cur = "";
  for (const m of String(s).split(" ")) { if (cur && (cur + " " + m).length > n) { l.push(cur); cur = m; } else cur = cur ? cur + " " + m : m; }
  if (cur) l.push(cur); return l; }
const valA = (r, k = 0) => r == null || r[k] == null ? null : r[k];

function reglagesAddicto() {
  const infos = {[AUCUNE_A]: {lib: "Aucune région repérée", groupe: "Région repérée", entier: true}};
  for (const c of regionsA()) infos[c] = {lib: nomRegA(c), groupe: "Région repérée", entier: true};
  if (ETAT.adReg && !infos[ETAT.adReg]) ETAT.adReg = null;
  liste("adReg", infos, [ETAT.adReg || AUCUNE_A], v => { ETAT.adReg = v === AUCUNE_A ? null : v; }, [], () => { addictoE(); ecrireAdresse("qAddicto"); });
}

function addictoE() {
  if (typeof DA === "undefined" || !DA) return;
  const sec = document.getElementById("qAddicto");
  if (!DA.ind.length && !DA.offre.length) { if (sec) sec.hidden = true; return; }
  reglagesAddicto();
  consommationsA();
  offreA();
}

// consommations et décès attribuables, une colonne par indicateur, point et fourchette par région, médiane en pointillé
function consommationsA() {
  const codes = regionsA(), rep = ETAT.adReg, inds = DA.ind;
  const res = document.getElementById("adResultat"), div = document.getElementById("adFigure");
  if (!inds.length) { res.textContent = "Aucune mesure régionale des consommations dans ce fichier de données."; div.innerHTML = ""; return; }
  let ph = "Selon les régions, " + inds.filter(i => i.phrase).map(i => { const v = Object.values(i.v).map(x => x[0]);
    return i.phrase.replace("{min}", f1(d3.min(v))).replace("{max}", f1(d3.max(v))).replace("{annee}", i.annee); }).join(", ") + ".";
  // unité courte, « % » ou « pour 100 000 hab. », jusqu'à la première virgule de l'unité publiée
  const unite = i => /^%/.test(i.unite) ? " %" : i.unite ? " " + i.unite.split(",")[0] : "";
  if (rep) { const parts = inds.map(i => { const r = i.v[rep]; return r ? `${i.lib.toLowerCase()}, ${f1(r[0])}${unite(i)}${r[1] != null ? ` (de ${f1(r[1])} à ${f1(r[2])})` : ""}` : null; }).filter(Boolean);
    ph += parts.length ? ` ${cap(enRegionA(rep))}, ${parts.join(" ; ")}.` : ` Aucune mesure publiée ${enRegionA(rep)}.`; }
  res.textContent = ph;
  document.querySelector("#adFenConso .fen-resume").textContent = ph;
  const titre = "Consommations d'alcool et de tabac et décès attribuables au tabac, par région, avec leur fourchette";
  document.getElementById("adTitre").textContent = titre;
  // régions sans mesure, dites sous la figure
  const manques = inds.map(i => Object.keys(DA.regions).filter(c => !(c in i.v))), commun = manques[0].filter(c => manques.every(m => m.includes(c)));
  const noms = cs => cs.map(nomRegA).sort((a, b) => a.localeCompare(b, "fr")).join(", ");
  const notes = (commun.length ? [`Aucune mesure publiée pour ${noms(commun)}.`] : [])
    .concat(inds.map((i, j) => [i, manques[j].filter(c => !commun.includes(c))]).filter(([, m]) => m.length).map(([i, m]) => `« ${i.lib} », pas de mesure publiée pour ${noms(m)}.`));
  document.getElementById("adNotes").innerHTML = ["Point, valeur de la région. Trait, fourchette (intervalle de confiance à 95 %). Pointillé, médiane des régions. Un clic sur une région la repère dans les trois panneaux."]
    .concat(notes).map(t => `<span>${t}</span>`).join(" ");
  // côte à côte sur un écran large, empilés sur un écran étroit (moins de 300 pixels par panneau)
  const w = largeur(div), pas = 22, fs = 12, sig = fs * .56;
  const g0 = Math.min(Math.round(w * .42), Math.ceil(d3.max(codes, c => nomRegA(c).length) * sig) + 14);
  const empile = (w - g0 - 12) / inds.length < 230;
  const largP = empile ? w - g0 - 16 : (w - g0 - 12) / inds.length;
  const ent = inds.map(i => ({t: coupeA(i.lib, Math.max(12, Math.floor((largP - 16) / (fs * .58)))), u: coupeA(`${i.unite}, ${i.annee}`, Math.max(14, Math.floor((largP - 16) / (11 * .56))))}));
  const hTete = e => e.t.length * 16 + e.u.length * 14 + 8;
  const hCorps = pas * codes.length + 26;
  const tetes = empile ? ent.map(hTete) : [d3.max(ent, hTete)];
  const h = empile ? d3.sum(tetes) + inds.length * (hCorps + 18) : tetes[0] + hCorps + 4;
  const svg = svgI(div, w, h, titre);
  inds.forEach((ind, j) => {
    const y0 = empile ? d3.sum(tetes.slice(0, j)) + j * (hCorps + 18) : 0, ht = empile ? tetes[j] : tetes[0];
    // marge entre deux panneaux, pour que leurs graduations ne se touchent pas
    const x0 = empile ? g0 + 8 : g0 + j * largP + 16, x1 = empile ? w - 16 : x0 + largP - 40, e = ent[j];
    const vals = Object.values(ind.v), vmax = d3.max(vals, x => Math.max(x[0], x[2] ?? x[0])) * 1.05;
    const X = d3.scaleLinear().domain([0, vmax]).nice(4).range([x0, x1]), haut0 = y0 + ht, bas0 = haut0 + pas * codes.length;
    const cx = empile ? x0 : (x0 + x1) / 2, ancre = empile ? "start" : "middle";
    e.t.forEach((t, l) => svg.append("text").attr("x", cx).attr("y", y0 + 14 + 16 * l).attr("text-anchor", ancre).attr("font-size", fs).attr("font-weight", 600).attr("fill", "var(--ink)").text(t));
    e.u.forEach((t, l) => svg.append("text").attr("x", cx).attr("y", y0 + 14 + 16 * e.t.length + 14 * l).attr("text-anchor", ancre).attr("font-size", 11).attr("fill", "var(--muted)").text(t));
    // lignes des régions, une bande sur deux, la région repérée soulignée
    codes.forEach((c, k) => { const y = haut0 + pas * k;
      if (c === rep) { if (empile || j === 0) svg.append("rect").attr("x", 4).attr("y", y).attr("width", w - 8).attr("height", pas).attr("fill", "var(--ink)").attr("opacity", .1); }
      else if (k % 2 === 0) svg.append("rect").attr("x", x0 - 10).attr("y", y).attr("width", x1 - x0 + 20).attr("height", pas).attr("fill", "var(--line)").attr("opacity", .25);
      if (empile || j === 0) svg.append("text").attr("x", g0 - 8).attr("y", y + pas / 2 + 4).attr("text-anchor", "end").attr("font-size", fs)
        .attr("font-weight", c === rep ? 600 : 400).attr("fill", "var(--ink)").text(nomRegA(c)); });
    const ticks = X.ticks(4), ft = ticks.every(Number.isInteger) ? f0 : f1;
    ticks.forEach(v => { svg.append("line").attr("x1", X(v)).attr("x2", X(v)).attr("y1", haut0).attr("y2", bas0).attr("stroke", "var(--line)");
      svg.append("text").attr("x", X(v)).attr("y", bas0 + 16).attr("text-anchor", "middle").attr("font-size", 11).attr("fill", "var(--muted)").text(ft(v)); });
    const med = d3.median(vals, x => x[0]);
    svg.append("line").attr("x1", X(med)).attr("x2", X(med)).attr("y1", haut0).attr("y2", bas0).attr("stroke", "var(--muted)").attr("stroke-dasharray", "3 3");
    codes.forEach((c, k) => { const r = ind.v[c]; if (!r) return; const y = haut0 + pas * k + pas / 2;
      const bulleTxt = `${nomRegA(c)}, ${ind.lib.toLowerCase()} ${f1(r[0])}${r[1] != null ? ` (de ${f1(r[1])} à ${f1(r[2])})` : ""}, ${ind.unite}, ${ind.annee}`;
      if (r[1] != null && r[2] != null) svg.append("line").attr("x1", X(r[1])).attr("x2", X(r[2])).attr("y1", y).attr("y2", y).attr("stroke", "var(--r3, #3167A9)").attr("stroke-width", 2);
      svg.append("circle").attr("cx", X(r[0])).attr("cy", y).attr("r", c === rep ? 5.5 : 4).attr("fill", "var(--r5, #0F3562)")
        .attr("stroke", c === rep ? "var(--ink)" : "none").attr("stroke-width", 1.5).append("title").text(bulleTxt); });
  });
  // un clic sur une ligne repère la région, un second clic l'enlève
  svg.append("g").selectAll("rect").data(empile ? inds.flatMap((_, j) => codes.map((c, k) => [c, d3.sum(tetes.slice(0, j)) + j * (hCorps + 18) + tetes[j] + pas * k])) : codes.map((c, k) => [c, tetes[0] + pas * k]))
    .join("rect").attr("x", 0).attr("y", d => d[1]).attr("width", w).attr("height", pas).attr("fill", "transparent").style("cursor", "pointer")
    .on("click", (ev, d) => { ETAT.adReg = ETAT.adReg === d[0] ? null : d[0]; addictoE(); ecrireAdresse("qAddicto"); })
    .append("title").text(d => nomRegA(d[0]));
  figer(svg.node());
  const tete = ["code_region", "region"].concat(inds.flatMap(i => [`${i.id}_valeur`, `${i.id}_ic_bas`, `${i.id}_ic_haut`]));
  donneesFigure("figAddicto", "addictologie_regions.csv", [tete, ...codes.map(c => [c, nomRegA(c)].concat(inds.flatMap(i => [valA(i.v[c]), valA(i.v[c], 1), valA(i.v[c], 2)].map(v => v == null ? "" : v))))]);
}

// offre en addictologie en France, trois comptes des CSAPA qui ne s'additionnent pas
function offreA() {
  const rows = DA.offre;
  document.getElementById("adOffre").innerHTML = rows.length ? `<table class="ad-offre"><thead><tr><th>Offre</th><th>Nombre</th><th>Précision</th></tr></thead><tbody>`
    + rows.map(r => `<tr><td>${r.objet}</td><td>${f0(r.n)}</td><td class="small muted">${r.note || ""}</td></tr>`).join("") + "</tbody></table>"
    : "<p>Offre en addictologie absente de ce fichier de données.</p>";
  const csapa = rows.filter(r => /CSAPA/.test(r.objet)), n = re => rows.find(r => re.test(r.objet));
  const caarud = n(/CAARUD/), hop = n(/hôpital/);
  const resume = csapa.length ? `Les CSAPA se comptent à trois niveaux, ${csapa.map(r => `${f0(r.n)} ${r.objet.replace(/^CSAPA,?\s*/, "") || "principaux"}`).join(", ")}, qui ne s'additionnent pas.`
    + (caarud ? ` On compte ${f0(caarud.n)} CAARUD` + (hop ? ` et ${f0(hop.n)} unités d'addictologie à l'hôpital.` : ".") : "") : "";
  document.getElementById("adOffreResultat").textContent = resume;
  document.querySelector("#adFenOffre .fen-resume").textContent = csapa.length ? `CSAPA comptés à trois niveaux, ${csapa.map(r => f0(r.n)).join(", ")}, qui ne s'additionnent pas.` : "";
  donneesFigure("figAdOffre", "addictologie_offre.csv", [["offre", "nombre", "precision"], ...rows.map(r => [r.objet, r.n, r.note || ""])]);
  const L = DA.limite;
  document.getElementById("adSavoir").innerHTML = L ? `<strong>À savoir.</strong> ${L.texte} Sources, ${L.sources.map(([t, u]) => `<a href="${u}" target="_blank" rel="noopener">${t}</a>`).join(", ")}.` : "";
}

let ATTENTE_A = null;
addEventListener("fenetre", () => { clearTimeout(ATTENTE_A); ATTENTE_A = setTimeout(addictoE, 140); });
addEventListener("resize", () => { clearTimeout(ATTENTE_A); ATTENTE_A = setTimeout(addictoE, 140); });
// un lien qui vise la question (depuis la fiche d'un territoire de l'atlas) la montre une fois dessinée
if (/^#(qAddicto|adFen)/.test(location.hash)) addEventListener("load", () => requestAnimationFrame(() => document.getElementById("qAddictoT")?.scrollIntoView({block: "start"})));
