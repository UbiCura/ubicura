// Page « Explorer les données » (décision de Lucas du 26 octobre 2026), outils réglés par le lecteur. Données préparées
// par pipeline/explorer.py (mêmes comptes que les rapports), réglages gardés dans l'adresse de la page.
const fr = d3.formatLocale({decimal: ",", thousands: " ", grouping: [3], currency: ["", " €"]});
const f1 = fr.format(",.1f"), f0 = fr.format(",.0f"), fp = v => (v >= 0 ? "+" : "−") + fr.format(",.1f")(Math.abs(v)) + " %";
const fd = v => v == null ? "" : (Math.abs(v) < 10 ? fr.format(",.2f")(v) : f1(v));
const pc = v => v < .001 && v > 0 ? "moins de 0,1 %" : fr.format(",.1f")(v * 100) + " %";
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
const court = s => s.replace(/ \(.*\)/, "").replace(/,.*/, "");
const bulle = document.getElementById("bulle");
function montrer(ev, html) { bulle.innerHTML = html; bulle.style.display = "block"; bulle.style.left = Math.min(ev.clientX + 14, innerWidth - 270) + "px"; bulle.style.top = ev.clientY + 14 + "px"; }
const cacher = () => bulle.style.display = "none";
function choix(id, items, actif, clic, apres) {
  const el = document.getElementById(id); el.innerHTML = "";
  for (const [val, lib, off] of items) {
    const b = document.createElement("button"); b.type = "button"; b.textContent = lib; b.disabled = !!off;
    b.setAttribute("aria-pressed", actif(val)); b.onclick = () => { clic(val); apres(); }; el.appendChild(b);
  }
}
// données de la figure pour « Citer et exporter » (CSV), comme les figures des rapports
function donneesFigure(id, nom, lignes) {
  const csv = "﻿" + lignes.map(l => l.map(v => typeof v === "number" ? String(Math.round(v * 1000) / 1000).replace(".", ",") : v).join(";")).join("\n");
  const f = document.getElementById(id), ancien = f.dataset.donnees;
  if (ancien && ancien.startsWith("blob:")) URL.revokeObjectURL(ancien);
  f.dataset.donnees = URL.createObjectURL(new Blob([csv], {type: "text/csv"})); f.dataset.donneesNom = nom;
}
// styles écrits dans la figure elle-même, avec les valeurs du fond clair en repli, pour qu'un SVG ou un PNG exporté
// garde ses couleurs et ses traits hors de la page (exports sur fond blanc, décision de Lucas du 22 octobre 2026)
function figer(svg) {
  const s = d3.select(svg), police = "Work Sans, Segoe UI, sans-serif";
  s.attr("font-family", police);
  s.selectAll(".grillage line").attr("stroke", "var(--line, #E2E3E6)").attr("stroke-width", 1);
  s.selectAll(".axe text").attr("fill", "var(--muted, #5D6371)").attr("font-size", 12).attr("font-family", police);
  s.selectAll(".courbe").attr("fill", "none").attr("stroke-width", 2).attr("stroke-linejoin", "round").attr("stroke-linecap", "round");
  s.selectAll(".repere").attr("fill", "none").attr("stroke", "var(--ink, #1C2028)").attr("stroke-width", 1.5).attr("stroke-dasharray", "4 3");
  s.selectAll(".etiq").attr("fill", "var(--muted, #5D6371)").attr("font-size", 12).attr("font-family", police);
  s.selectAll(".etiq.forte").attr("fill", "var(--ink, #1C2028)");
  s.selectAll(".territoire").attr("stroke", "var(--contour, #FFFFFF)").attr("stroke-width", .3);
  s.selectAll(".curseur").attr("stroke", "var(--muted, #5D6371)");
}

// ---------------------------------------------------------------- famille et état dans l'adresse de la page
// familles tirées des professions du catalogue (santé mentale, santé), plus toute l'offre ; la clé courte sert à l'adresse
const CLES_FAMILLE = {"Santé mentale": "sm", "Santé": "sante"};
const FAMILLES = [...new Set(Object.values(DC.profs).map(p => p.famille))].filter(f => CLES_FAMILLE[f])
  .sort((a, b) => (a === "Santé mentale" ? -1 : 1) - (b === "Santé mentale" ? -1 : 1)).map(f => [CLES_FAMILLE[f], f, f])
  .concat([["tout", "Toute l'offre de soins", null]]);
const DEFAUTS = {sm: {pA: "psychologue", pB: "psychiatre", tProfs: ["psychiatre", "psychologue"]},
                 sante: {pA: "medecin_generaliste", pB: "pediatre", tProfs: ["medecin_generaliste", "pediatre"]},
                 tout: {pA: "psychologue", pB: "psychiatre", tProfs: ["psychiatre", "medecin_generaliste"]}};
const ETAT = {fam: "sm", ...DEFAUTS.sm, pV: "revenu_median", tV: "revenu_median", tK: 5, tM: "base", tPar: "groupes", tG: "tous", tDep: null};
const nomFamille = () => FAMILLES.find(f => f[0] === ETAT.fam)[2];
const dansFamille = info => !nomFamille() || !info.famille || info.famille === nomFamille();
function lireAdresse() {
  const q = new URLSearchParams(location.hash.split("?")[1] || "");
  if (q.has("fam") && DEFAUTS[q.get("fam")]) Object.assign(ETAT, {fam: q.get("fam")}, DEFAUTS[q.get("fam")]);
  for (const [k, v] of q) { if (!(k in ETAT) || k === "fam") continue; ETAT[k] = k === "tProfs" ? v.split(",").filter(p => DT.profs[p]) : k === "tK" ? +v : v; }
  ETAT.pV = {revenu: "revenu_median", densite: "densite_pop"}[ETAT.pV] || ETAT.pV;
}
function ecrireAdresse(ancre) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(ETAT)) if (v != null) q.set(k, Array.isArray(v) ? v.join(",") : v);
  history.replaceState(null, "", "#" + ancre + "?" + q.toString());
}
function famille() {
  choix("fam", FAMILLES.map(f => [f[0], f[1]]), f => f === ETAT.fam, f => { Object.assign(ETAT, {fam: f}, DEFAUTS[f]); Object.keys(OUVERTS).forEach(k => OUVERTS[k] = false); }, () => { tout(); ecrireAdresse(""); });
}

// ordre des groupes, santé mentale puis premier recours, comme dans l'atlas (réglage de présentation) ; un groupe nouveau
// du catalogue suit, dans l'ordre de la table des professions, et un thème d'indicateurs dans l'ordre du catalogue
const ORDRE_GROUPES = ["Psychiatrie", "Psychologie et psychothérapie", "Qualifications complémentaires", "Premier recours",
  "Médecins spécialistes, ensemble", "Spécialités médicales", "Spécialités chirurgicales", "Spécialités médico-techniques",
  "Rééducation", "Médico-technique", "Appareillage", "Prévention et santé publique", "Autres médecins", "Autres"];
const rangGroupe = g => { const i = ORDRE_GROUPES.indexOf(g); if (i >= 0) return i; const j = (DC.groupes || []).indexOf(g); return j < 0 ? 999 : 100 + j; };
// liste de professions, même composant que le choix de la profession dans l'atlas (nom souligné et flèche, professions
// rangées par groupe, recherche au-delà de quinze noms), plusieurs choix possibles pour les trajectoires
const OUVERTS = {};
function liste(id, infos, choisies, clic, interdites, apres, multi = false, max = 1) {
  const el = document.getElementById(id);
  const ids = Object.keys(infos).filter(p => dansFamille(infos[p]));
  const groupes = [...new Set(ids.map(p => infos[p].groupe))].sort((a, b) => rangGroupe(a) - rangGroupe(b));
  // libellé entier quand la forme courte confondrait deux choix (structures pour adultes et pour enfants)
  const nom = p => infos[p].entier ? infos[p].lib : court(infos[p].lib || infos[p].libelle);
  const filtre = el.querySelector(".filtre-liste")?.value || "";
  el.className = "prof-choix"; el.innerHTML = "";
  const b = document.createElement("button"); b.type = "button"; b.setAttribute("aria-haspopup", "true");
  b.innerHTML = `<span>${choisies.map(nom).join(", ")}</span><svg width="11" height="7" viewBox="0 0 11 7" aria-hidden="true"><path d="M1 1l4.5 4.5L10 1" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>`;
  const l = document.createElement("div"); l.className = "prof-liste" + (ids.length > 15 ? " large" : ""); l.hidden = true;
  l.innerHTML = (ids.length > 15 ? `<input type="search" class="filtre-liste" placeholder="Rechercher une profession" aria-label="Rechercher une profession">` : "")
    + (multi ? `<p class="consigne">Jusqu'à ${max} professions, un clic ajoute ou retire.</p>` : "")
    + `<div class="colonnes">` + groupes.map(g => `<div class="grp"><p>${g}</p>` + ids.filter(p => infos[p].groupe === g).map(p =>
      `<button type="button" data-v="${p}"${multi ? ` aria-pressed="${choisies.includes(p)}"` : ` aria-current="${choisies.includes(p)}"`}${interdites.includes(p) ? " disabled" : ""}>${nom(p)}</button>`).join("") + `</div>`).join("") + `</div>`;
  el.append(b, l);
  const ouvrir = o => { l.hidden = !o; b.setAttribute("aria-expanded", String(o)); OUVERTS[id] = o;
    if (o) document.querySelectorAll(".prof-liste").forEach(x => { if (x !== l) { x.hidden = true; x.parentElement.querySelector(":scope > button")?.setAttribute("aria-expanded", "false"); } }); };
  const f = l.querySelector(".filtre-liste");
  const filtrer = () => { const q = f.value.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().trim();
    l.querySelectorAll(".grp").forEach(g => { let k = 0; g.querySelectorAll("button").forEach(x => { const ok = !q || x.textContent.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().includes(q); x.hidden = !ok; if (ok) k++; }); g.hidden = !k; }); };
  if (f) { f.value = filtre; f.addEventListener("input", filtrer); if (filtre) filtrer(); }
  b.onclick = () => { ouvrir(l.hidden); if (!l.hidden) (f || l.querySelector('[aria-current="true"],[aria-pressed="true"]') || l.querySelector("button"))?.focus(); };
  l.onclick = e => { const x = e.target.closest("[data-v]"); if (!x || x.disabled) return; clic(x.dataset.v); if (!multi) OUVERTS[id] = false; apres();
    if (multi) document.querySelector(`#${id} [data-v="${x.dataset.v}"]`)?.focus(); };
  if (OUVERTS[id]) ouvrir(true);
  if (!el.dataset.ecoute) { el.dataset.ecoute = "1";
    document.addEventListener("keydown", e => { if (e.key === "Escape" && OUVERTS[id]) { const lb = document.querySelector(`#${id} .prof-liste`); if (lb) lb.hidden = true; OUVERTS[id] = false; document.querySelector(`#${id} > button`)?.focus(); } });
    document.addEventListener("pointerdown", e => { if (OUVERTS[id] && !e.target.closest("#" + id)) { const lb = document.querySelector(`#${id} .prof-liste`); if (lb) lb.hidden = true; OUVERTS[id] = false; document.querySelector(`#${id} > button`)?.setAttribute("aria-expanded", "false"); } }, true); }
}

// ---------------------------------------------------------------- une profession sans l'autre
const NOMP = p => court(DC.profs[p].lib);
const min = p => NOMP(p).toLowerCase();
const IDX = Object.fromEntries(DC.ordre.map((p, i) => [p, i + 2]));
const GEO = topojson.feature(TOPO, TOPO.objects.epci).features.filter(f => {
  const [x, y] = d3.geoCentroid(f); return x > -6 && x < 10 && y > 41 && y < 52; });
const classeP = (c, a, b) => { const r = DC.epci[c]; if (!r) return null; const ha = r[IDX[a]] > 0, hb = r[IDX[b]] > 0;
  return ha && hb ? "deux" : ha ? "a" : hb ? "b" : "aucun"; };
const minusc = s => /^[A-ZÉ]{2}/.test(s) ? s : s.charAt(0).toLowerCase() + s.slice(1);
const VARS_P = Object.fromEntries(Object.entries(DC.vars).map(([k, v]) => [k, [v.article || minusc(v.lib), v.sens, v.valeurs]]));
const INFOS_VP = Object.fromEntries(Object.entries(DC.vars).map(([k, v]) => [k, {lib: v.lib, groupe: v.groupe, famille: v.famille, entier: true}]));
const SEUIL_VISIBLE = .01;   // une situation qui réunit moins de 1 % des habitants ne se voit pas sur les barres
function paires() {
  const apres = () => { paires(); ecrireAdresse("paires"); };
  if (!DC.profs[ETAT.pA] || !dansFamille(DC.profs[ETAT.pA])) ETAT.pA = DEFAUTS[ETAT.fam].pA;
  if (!DC.profs[ETAT.pB] || !dansFamille(DC.profs[ETAT.pB])) ETAT.pB = DEFAUTS[ETAT.fam].pB;
  liste("pA", DC.profs, [ETAT.pA], p => ETAT.pA = p, [ETAT.pB], apres);
  liste("pB", DC.profs, [ETAT.pB], p => ETAT.pB = p, [ETAT.pA], apres);
  if (!VARS_P[ETAT.pV]) ETAT.pV = VARS_P.revenu_median ? "revenu_median" : Object.keys(VARS_P)[0];
  liste("pV", INFOS_VP, [ETAT.pV], v => ETAT.pV = v, [], apres);
  const A = ETAT.pA, B = ETAT.pB;
  const CL = [["a", `${min(A)} mais aucun ${min(B)}`, "var(--d1, #BC6B3B)"],
              ["b", `${min(B)} mais aucun ${min(A)}`, "var(--r3, #3167A9)"],
              ["aucun", "ni l'un ni l'autre", "var(--d0, #83451E)"],
              ["deux", "les deux professions", "var(--d3, #DFE1E5)"]];
  const coul = Object.fromEntries(CL.map(c => [c[0], c[2]])), lib = Object.fromEntries(CL.map(c => [c[0], c[1]]));
  // totaux, toutes les intercommunalités, outre-mer compris
  const tot = {deux: [0, 0], a: [0, 0], b: [0, 0], aucun: [0, 0]}; let P = 0;
  for (const c of Object.keys(DC.epci)) { const k = classeP(c, A, B); tot[k][0]++; tot[k][1] += DC.epci[c][1]; P += DC.epci[c][1]; }
  const part = k => tot[k][1] / P;
  const nInter = k => `${f0(tot[k][0])} intercommunalité${tot[k][0] > 1 ? "s" : ""}`;
  document.getElementById("pLecture").textContent = `${cap(pc(part("a")))} des habitants vivent dans une intercommunalité qui compte au moins un ${min(A)} mais aucun ${min(B)} déclaré (${nInter("a")}), `
    + (tot.b[0] ? `et ${pc(part("b"))} dans la situation inverse (${nInter("b")}).` : `et aucune intercommunalité ne compte un ${min(B)} sans ${min(A)}.`);
  // limite propre aux psychiatres, écrite seulement quand l'un d'eux est choisi
  const psy = [A, B].some(p => /psychiatr/.test(p));
  document.getElementById("pSavoir").innerHTML = `<strong>À savoir.</strong> Le répertoire situe chaque professionnel à l'adresse de la structure où il déclare exercer.`
    + (psy ? ` Un psychiatre peut consulter dans un centre médico-psychologique (CMP) sans y être déclaré, une intercommunalité sans psychiatre déclaré peut donc accueillir des consultations de psychiatrie.` : "")
    + ` Sources, Annuaire santé, extractions en libre accès du RPPS (data.gouv), INSEE, population et niveau de vie (Filosofi).`;
  const presentes = CL.filter(c => tot[c[0]][0] > 0);
  document.getElementById("pLegende").innerHTML = presentes.map(c => `<span${part(c[0]) < SEUIL_VISIBLE ? ' class="rare"' : ""}><i class="carre" style="background:${c[2]}"></i>${c[1]}, ${nInter(c[0])}</span>`).join("");
  document.getElementById("pTitreCarte").textContent = `Intercommunalités de l'Hexagone et de Corse selon la présence d'au moins un ${min(A)} et d'au moins un ${min(B)} déclarés`;
  const W = 520, H = 540, proj = d3.geoConicConformal().parallels([44, 49]).rotate([-3, 0]).fitSize([W, H], {type: "FeatureCollection", features: GEO});
  const path = d3.geoPath(proj), div = document.getElementById("pCarte"); div.innerHTML = "";
  const svg = d3.select(div).append("svg").attr("xmlns", "http://www.w3.org/2000/svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img")
    .attr("aria-label", document.getElementById("pTitreCarte").textContent);
  svg.selectAll("path").data(GEO).join("path").attr("class", "territoire").attr("d", path)
    .attr("fill", f => coul[classeP(f.properties.epci, A, B)] || "var(--nodata, #ECECEF)")
    .on("mousemove", (ev, f) => { const r = DC.epci[f.properties.epci]; if (!r) return;
      montrer(ev, `<b>${r[0]}</b><div class="l"><span>Habitants</span><span>${f0(r[1])}</span></div><div class="l"><span>${NOMP(A)}, déclarés</span><span>${f0(r[IDX[A]])}</span></div><div class="l"><span>${NOMP(B)}, déclarés</span><span>${f0(r[IDX[B]])}</span></div>`); })
    .on("mouseleave", cacher);
  const [vlib, vsens, vals] = VARS_P[ETAT.pV];
  document.getElementById("pTitreBarres").textContent = `Part des habitants à qui il manque au moins l'une des deux professions dans leur intercommunalité, par dixième des intercommunalités selon ${vlib}`;
  const ordre = ["a", "b", "aucun"].filter(k => tot[k][0] > 0);
  document.getElementById("pLegende2").innerHTML = ordre.map(k => `<span${part(k) < SEUIL_VISIBLE ? ' class="rare"' : ""}><i class="carre" style="background:${coul[k]}"></i>${lib[k]}, ${pc(part(k))} des habitants</span>`).join("");
  const codes = Object.keys(DC.epci).filter(c => vals[c] != null).sort((x, y) => vals[x] - vals[y]);
  const dec = d3.range(10).map(i => { const g = codes.filter((c, j) => Math.floor(j * 10 / codes.length) === i); const t = {deux: 0, a: 0, b: 0, aucun: 0}; let p = 0;
    g.forEach(c => { t[classeP(c, A, B)] += DC.epci[c][1]; p += DC.epci[c][1]; }); return {i, n: g.length, p, parts: Object.fromEntries(Object.entries(t).map(([k, v]) => [k, v / p]))}; });
  const bw = 520, bh = 520, m = {t: 10, r: 8, b: 44, l: 46}, x = d3.scaleBand().domain(d3.range(10)).range([m.l, bw - m.r]).padding(.22);
  const ymax = Math.max(.05, d3.max(dec, d => ordre.reduce((s, k) => s + d.parts[k], 0)) * 1.12);
  const y = d3.scaleLinear().domain([0, ymax]).nice().range([bh - m.b, m.t]);
  const db = document.getElementById("pBarres"); db.innerHTML = "";
  const sb = d3.select(db).append("svg").attr("xmlns", "http://www.w3.org/2000/svg").attr("viewBox", `0 0 ${bw} ${bh}`).attr("role", "img").attr("aria-label", document.getElementById("pTitreBarres").textContent);
  sb.append("g").attr("class", "grillage").selectAll("line").data(y.ticks(4)).join("line").attr("x1", m.l).attr("x2", bw - m.r).attr("y1", y).attr("y2", y);
  sb.append("g").attr("class", "axe").attr("transform", `translate(${m.l - 6},0)`).call(d3.axisLeft(y).ticks(4).tickFormat(v => fr.format(",.0f")(v * 100) + " %").tickSize(0).tickPadding(6)).call(s => s.select(".domain").remove());
  sb.append("g").attr("class", "axe").attr("transform", `translate(0,${bh - m.b + 4})`).call(d3.axisBottom(x).tickFormat(i => i + 1).tickSize(0).tickPadding(8)).call(s => s.select(".domain").remove());
  sb.append("text").attr("class", "etiq").attr("x", (m.l + bw - m.r) / 2).attr("y", bh - 4).attr("text-anchor", "middle").text(`dixièmes des intercommunalités, ${vsens}`);
  for (const d of dec) { let y0 = 0;
    const g = sb.append("g").on("mousemove", ev => montrer(ev, `<b>${d.i + 1}<sup>e</sup> dixième, ${f0(d.n)} intercommunalités</b>` + ordre.map(q => `<div class="l"><span><i style="background:${coul[q]}"></i>${lib[q]}</span><span>${pc(d.parts[q])}</span></div>`).join(""))).on("mouseleave", cacher);
    g.append("rect").attr("x", x(d.i)).attr("width", x.bandwidth()).attr("y", m.t).attr("height", bh - m.b - m.t).attr("fill", "transparent");
    for (const k of ordre) { const v = d.parts[k]; if (!v) continue;
      g.append("rect").attr("x", x(d.i)).attr("width", x.bandwidth()).attr("y", y(y0 + v)).attr("height", Math.max(0, y(y0) - y(y0 + v) - (y0 ? 2 : 0))).attr("rx", 2).attr("fill", coul[k]);
      y0 += v; }
    sb.append("text").attr("class", "etiq").attr("x", x(d.i) + x.bandwidth() / 2).attr("y", y(y0) - 5).attr("text-anchor", "middle").text(fr.format(",.0f")(y0 * 100) + " %"); }
  figer(svg.node()); figer(sb.node());
  const rares = ordre.filter(k => part(k) < SEUIL_VISIBLE);
  document.getElementById("pLire").innerHTML = `<strong>Comment lire.</strong> Sur la carte, chaque intercommunalité reçoit une couleur selon que les deux professions y comptent au moins un professionnel déclaré dans le répertoire RPPS, ou non. Elle montre l'Hexagone et la Corse, l'outre-mer est compté dans les barres et le tableau. Une profession absente ne veut pas dire que les habitants n'y ont pas accès, le professionnel le plus proche peut exercer dans l'intercommunalité voisine. Les barres réunissent les intercommunalités par dixième, rangées selon ${vlib}, 10 % des intercommunalités chacune, et donnent la part de leurs habitants à qui il manque au moins l'une des deux professions. Le reste de chaque barre, jusqu'à 100 %, correspond aux habitants qui ont les deux.`
    + (rares.length ? ` ${rares.length > 1 ? "Les situations" : "La situation"} ${rares.map(k => `« ${lib[k]} »`).join(" et ")} ${rares.length > 1 ? "concernent" : "concerne"} moins de 1 % des habitants, trop peu pour se voir sur les barres, ${rares.length > 1 ? "ces situations restent" : "cette situation reste"} dans la légende et le tableau.` : "")
    + ` Les deux professions ne sont jamais additionnées.`;
  const lignes = CL.map(c => [c[0], c[1], tot[c[0]][0], tot[c[0]][1], part(c[0])]);
  document.getElementById("pTable").innerHTML = `<table><caption>Intercommunalités et habitants dans chaque situation, France entière</caption><thead><tr><th>Dans l'intercommunalité</th><th>Intercommunalités</th><th>Habitants</th><th>Part des habitants</th></tr></thead><tbody>`
    + lignes.map(l => `<tr><td><i class="pastille" style="background:${coul[l[0]]}"></i>${cap(l[1])}</td><td>${f0(l[2])}</td><td>${f0(l[3])}</td><td>${pc(l[4])}</td></tr>`).join("") + "</tbody></table>";
  donneesFigure("figCarte", `une_sans_l_autre_${A}_${B}.csv`, [["code", "intercommunalite", "habitants", A, B, "situation"],
    ...Object.entries(DC.epci).map(([c, r]) => [c, r[0], r[1], r[IDX[A]], r[IDX[B]], lib[classeP(c, A, B)]])]);
  donneesFigure("figBarres", `une_sans_l_autre_${A}_${B}_${ETAT.pV}.csv`, [["dixieme", "intercommunalites", "habitants", ...ordre.map(k => lib[k])],
    ...dec.map(d => [d.i + 1, d.n, d.p, ...ordre.map(k => d.parts[k])])]);
}

// ---------------------------------------------------------------- trajectoires
const ARTICLE = new Proxy({}, {get: (o, k) => (DT.vars[k] || {}).article || "la variable choisie"});   // forme du nom dans une phrase, d'après le catalogue
const nomT = p => court(DT.profs[p].libelle);
const K_REPLI = {1: "#83451E", 2: "#C0703F", 3: "#A7ACB5", 4: "#3F74C0", 5: "#163F75"};
const couleurT = i => { const n = ETAT.tK === 3 ? [1, 3, 5][i] : i + 1; return `var(--k${n}, ${K_REPLI[n]})`; };
// une couleur par profession dans le mode « une courbe par profession », toujours dans le même ordre, jamais recyclée
const C_REPLI = ["#2a78d6", "#eb6834", "#1baf7a", "#6250d6", "#e87ba4", "#008300"];
const couleurP = j => `var(--c${j + 1}, ${C_REPLI[j]})`;
const SOURCES = {ADELI: "série tirée du répertoire ADELI, qui s'arrête en 2024 et compte les actifs occupés de moins de 62 ans, avec des effectifs plus élevés que le RPPS pour la même profession",
                 SNDS: "infirmiers libéraux ayant eu une activité remboursée dans l'année (SNDS), jusqu'en 2023",
                 "INSEE, base Tous salariés": "infirmiers salariés en poste principal au 31 décembre (base Tous salariés de l'INSEE), jusqu'en 2023"};
function groupesT() { const vals = DT.vars[ETAT.tV].valeurs; const codes = Object.keys(vals).filter(c => vals[c] != null).sort((a, b) => vals[a] - vals[b]);
  const g = {}; codes.forEach((c, i) => g[c] = Math.floor(i * ETAT.tK / codes.length)); return g; }
function nomGroupe(i) { const v = DT.vars[ETAT.tV]; if (i === 0) return v.bas; if (i === ETAT.tK - 1) return v.haut;
  return ETAT.tK === 3 ? "groupe du milieu" : ["", "deuxième groupe", "groupe du milieu", "quatrième groupe"][i]; }
const nomGroupeLong = i => i === "tous" ? "l'ensemble des départements" : (+i === 0 || +i === ETAT.tK - 1 ? "les départements " + nomGroupe(+i) : "le " + nomGroupe(+i));
const ANNEES = (() => { const s = new Set(); Object.values(DT.profs).forEach(p => Object.values(p.deps).forEach(d => Object.keys(d).forEach(a => s.add(+a)))); return [...s].sort(); })();
function densite(p, g, i, a) {
  let e = 0, pop = 0; for (const [c, d] of Object.entries(DT.profs[p].deps)) if ((i === "tous" ? g[c] != null : g[c] === +i) && d[a]) { e += d[a][0]; pop += d[a][1]; }
  return pop ? e / pop * 1e4 : null;
}
function enBase(pts, base) { const b = pts.find(q => q.d != null); pts.forEach(q => q.v = q.d == null || !b ? null : (base ? q.d / b.d * 100 : q.d)); return pts; }
function dessinerPanneau(div, A, series, base, titreAria, large) {
  const W = large ? 1000 : 520, H = large ? 380 : 270, m = {t: 8, r: 190, b: 24, l: 40};
  const svg = d3.select(div).append("svg").attr("xmlns", "http://www.w3.org/2000/svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img").attr("aria-label", titreAria);
  const tous = series.flatMap(s => s.pts.map(q => q.v)).filter(v => v != null && isFinite(v));
  const x = d3.scaleLinear().domain(d3.extent(A)).range([m.l, W - m.r]);
  const ext = d3.extent(tous), pad = (ext[1] - ext[0]) * .08 || 1;
  const y = d3.scaleLinear().domain(base ? [Math.min(ext[0] - pad, 98), Math.max(ext[1] + pad, 102)] : [0, ext[1] + pad]).nice().range([H - m.b, m.t]);
  svg.append("g").attr("class", "grillage").selectAll("line").data(y.ticks(4)).join("line").attr("x1", m.l).attr("x2", W - m.r).attr("y1", y).attr("y2", y);
  svg.append("g").attr("class", "axe").attr("transform", `translate(0,${H - m.b + 4})`).call(d3.axisBottom(x).ticks(large ? 11 : 6).tickFormat(d3.format("d")).tickSize(0).tickPadding(8)).call(s => s.select(".domain").remove());
  svg.append("g").attr("class", "axe").attr("transform", `translate(${m.l - 6},0)`).call(d3.axisLeft(y).ticks(4).tickFormat(base ? f0 : (y.domain()[1] < 5 ? fr.format(",.1f") : f0)).tickSize(0).tickPadding(6)).call(s => s.select(".domain").remove());
  const ligne = d3.line().defined(q => q.v != null).x(q => x(q.a)).y(q => y(q.v));
  series.forEach(s => svg.append("path").attr("class", s.repere ? "repere" : "courbe").attr("stroke", s.couleur).attr("d", ligne(s.pts)));
  const fins = series.filter(s => !s.repere && s.pts.some(q => q.v != null)).map(s => { const q = [...s.pts].reverse().find(q => q.v != null); return {s, y: y(q.v), v: q.v, a: q.a}; }).sort((a, b) => a.y - b.y);
  for (let j = 1; j < fins.length; j++) if (fins[j].y - fins[j - 1].y < 15) fins[j].y = fins[j - 1].y + 15;
  fins.forEach(f => svg.append("text").attr("class", "etiq" + (f.s.fort ? " forte" : "")).attr("x", W - m.r + 8).attr("y", f.y + 4)
    .text(`${base ? f1(f.v) : fd(f.v)}${f.a < A.at(-1) ? ` (${f.a})` : ""}  ${f.s.etiquette || ""}`));
  const cur = svg.append("line").attr("class", "curseur").attr("y1", m.t).attr("y2", H - m.b).style("display", "none");
  svg.append("rect").attr("x", m.l).attr("y", 0).attr("width", W - m.r - m.l).attr("height", H).attr("fill", "transparent")
    .on("mousemove", ev => { const [mx] = d3.pointer(ev), a = A[d3.minIndex(A, a => Math.abs(x(a) - mx))], k = A.indexOf(a);
      cur.style("display", null).attr("x1", x(a)).attr("x2", x(a));
      montrer(ev, `<b>${a}</b>` + [...series].reverse().map(s => `<div class="l"><span><i style="background:${s.couleur};height:2px"></i>${s.nom}</span><span>${s.pts[k].v == null ? "non connu" : (base ? f1(s.pts[k].v) : fd(s.pts[k].v))}${s.pts[k].e != null ? ` (${f0(s.pts[k].e)} en tout)` : ""}</span></div>`).join("")); })
    .on("mouseleave", () => { cur.style("display", "none"); cacher(); });
  figer(svg.node());
}
function trajectoires() {
  const apres = () => { trajectoires(); ecrireAdresse("trajectoires"); };
  const max = ETAT.tPar === "professions" ? 6 : 4;
  ETAT.tProfs = ETAT.tProfs.filter(p => DT.profs[p] && dansFamille(DT.profs[p])).slice(0, max);
  if (!ETAT.tProfs.length) ETAT.tProfs = DEFAUTS[ETAT.fam].tProfs.filter(p => DT.profs[p]);
  liste("tProfs", DT.profs, ETAT.tProfs, p => { if (ETAT.tProfs.includes(p)) { if (ETAT.tProfs.length > 1) ETAT.tProfs = ETAT.tProfs.filter(x => x !== p); } else ETAT.tProfs = [...ETAT.tProfs, p].slice(-max); }, [], apres, true, max);
  choix("tPar", [["groupes", "groupe de départements"], ["professions", "profession"]], v => v === ETAT.tPar, v => ETAT.tPar = v, apres);
  if (!DT.vars[ETAT.tV]) ETAT.tV = DT.vars.revenu_median ? "revenu_median" : Object.keys(DT.vars)[0];
  liste("tVar", Object.fromEntries(Object.entries(DT.vars).map(([k, v]) => [k, {lib: v.libelle, groupe: v.groupe, famille: v.famille, entier: true}])), [ETAT.tV], v => ETAT.tV = v, [], apres);
  choix("tK", [[3, "trois"], [5, "cinq"]], k => k === ETAT.tK, k => { ETAT.tK = k; if (ETAT.tG !== "tous" && +ETAT.tG >= k) ETAT.tG = "tous"; }, apres);
  const parProf = ETAT.tPar === "professions";
  document.getElementById("tLigneG").hidden = !parProf; document.getElementById("tLibG").hidden = !parProf;
  document.getElementById("tLigneM").hidden = parProf; document.getElementById("tLibM").hidden = parProf;
  choix("tG", [["tous", "tous les départements"], ...d3.range(ETAT.tK).map(i => [String(i), i === 0 || i === ETAT.tK - 1 ? "départements " + nomGroupe(i) : nomGroupe(i)])], v => v === ETAT.tG, v => ETAT.tG = v, apres);
  choix("tMode", [["base", "base 100 la première année"], ["densite", "densité"]], m => m === ETAT.tM, m => ETAT.tM = m, apres);
  const g = groupesT(), v = DT.vars[ETAT.tV], base = parProf || ETAT.tM === "base", A = ANNEES;
  const grille = document.getElementById("tGrille"); grille.innerHTML = "";
  const lect = document.getElementById("tLectures"); lect.innerHTML = "";
  const export_ = [];
  const l = ETAT.tProfs.map(p => nomT(p).toLowerCase());
  const listeNoms = l.length > 1 ? l.slice(0, -1).join(", des ") + " et des " + l.at(-1) : l[0];
  if (!parProf) {
    document.getElementById("tTitre").textContent = `Densité des ${listeNoms} depuis 2016, par groupe de départements selon ${ARTICLE[ETAT.tV]}`;
    document.getElementById("tLegende").innerHTML = d3.range(ETAT.tK).map(i => `<span><i style="background:${couleurT(i)}"></i>${i === 0 || i === ETAT.tK - 1 ? "départements " + nomGroupe(i) : nomGroupe(i)}</span>`).join("") + (ETAT.tDep ? `<span><i class="tiret"></i>${NOMS[ETAT.tDep]}</span>` : "");
    grille.style.gridTemplateColumns = ETAT.tProfs.length > 1 ? "1fr 1fr" : "1fr";
    ETAT.tProfs.forEach((p, j) => {
      const series = d3.range(ETAT.tK).map(i => ({nom: nomGroupe(i), couleur: couleurT(i), fort: i === 0 || i === ETAT.tK - 1,
        etiquette: i === 0 || i === ETAT.tK - 1 ? nomGroupe(i) : "", pts: enBase(A.map(a => ({a, d: densite(p, g, String(i), a)})), base)}));
      const dp = ETAT.tDep && DT.profs[p].deps[ETAT.tDep];
      if (dp) series.push({nom: NOMS[ETAT.tDep], couleur: "var(--ink, #1C2028)", repere: true, pts: enBase(A.map(a => ({a, e: dp[a] ? dp[a][0] : null, d: dp[a] ? dp[a][0] / dp[a][1] * 1e4 : null})), base)});
      const div = document.createElement("div"); grille.appendChild(div);
      div.innerHTML = `<h3>${nomT(p)}</h3><p class="unite">${base ? `base 100 en ${series[0].pts.find(q => q.d != null).a}` : "pour 10 000 habitants"}</p>`;
      dessinerPanneau(div, A, series, base, `Évolution de la densité de ${nomT(p).toLowerCase()} par groupe de départements`, ETAT.tProfs.length === 1);
      const b = series[0].pts.filter(q => q.d != null), h = series[ETAT.tK - 1].pts.filter(q => q.d != null);
      const txt = `de ${b[0].a} à ${b.at(-1).a}, la densité est passée de ${fd(b[0].d)} à ${fd(b.at(-1).d)} pour 10 000 habitants dans les départements ${v.bas} (${fp((b.at(-1).d / b[0].d - 1) * 100)}), et de ${fd(h[0].d)} à ${fd(h.at(-1).d)} dans les départements ${v.haut} (${fp((h.at(-1).d / h[0].d - 1) * 100)}). L'écart entre ces deux groupes est passé de ${fd(h[0].d - b[0].d)} à ${fd(h.at(-1).d - b.at(-1).d)} pour 10 000 habitants.`;
      if (j === 0) document.getElementById("tResultat").textContent = `${nomT(p)}, ${txt}`;
      else { const pl = document.createElement("p"); pl.textContent = `${nomT(p)}, ${txt}`; lect.appendChild(pl); }
      series.filter(s => !s.repere).forEach(s => export_.push([nomT(p), s.nom, ...s.pts.map(q => q.d)]));
    });
  } else {
    document.getElementById("tTitre").textContent = `Densité des ${listeNoms} depuis 2016 dans ${nomGroupeLong(ETAT.tG)}, en base 100 la première année de chaque série`;
    const series = ETAT.tProfs.map((p, j) => ({nom: nomT(p), couleur: couleurP(j), fort: true, etiquette: nomT(p), pts: enBase(A.map(a => ({a, d: densite(p, g, ETAT.tG, a)})), true)}));
    document.getElementById("tLegende").innerHTML = series.map(s => `<span><i style="background:${s.couleur}"></i>${s.nom}</span>`).join("");
    grille.style.gridTemplateColumns = "1fr";
    const div = document.createElement("div"); grille.appendChild(div);
    div.innerHTML = `<p class="unite">base 100 la première année de chaque série</p>`;
    dessinerPanneau(div, A, series, true, `Évolution de la densité de plusieurs professions dans ${nomGroupeLong(ETAT.tG)}`, true);
    const morceaux = series.map(s => { const q = s.pts.filter(q => q.d != null); return `${s.nom.toLowerCase()} ${fp((q.at(-1).d / q[0].d - 1) * 100)} (${q[0].a} à ${q.at(-1).a})`; });
    document.getElementById("tResultat").textContent = `Dans ${nomGroupeLong(ETAT.tG)}, la densité a varié ainsi, ${morceaux.join(", ")}. Les professions sont comparées par leur variation, jamais additionnées.`;
    series.forEach(s => export_.push([s.nom, nomGroupeLong(ETAT.tG), ...s.pts.map(q => q.d)]));
  }
  // limites des sources, écrites seulement pour les professions choisies
  const srcs = [...new Set(ETAT.tProfs.map(p => DT.profs[p].source))].filter(s => SOURCES[s]);
  document.getElementById("tSavoir").innerHTML = `<strong>À savoir.</strong> ` + srcs.map(s => `${cap(ETAT.tProfs.filter(p => DT.profs[p].source === s).map(p => nomT(p).toLowerCase()).join(", "))}, ${SOURCES[s]}.`).join(" ")
    + (srcs.length ? " " : "") + `La DREES compte chaque professionnel une fois, dans le département de son activité principale, ce qui diffère des comptages par lieu d'exercice du reste du site. Mayotte est exclue. Sources, DREES, démographie des professionnels de santé, INSEE, estimations de population et Filosofi.`;
  donneesFigure("figTraj", "trajectoires.csv", [["profession", "groupe", ...A], ...export_]);
  document.getElementById("tTable").innerHTML = `<table><caption>Densité pour 10 000 habitants${parProf ? ", " + nomGroupeLong(ETAT.tG) : ", par groupe de départements selon " + ARTICLE[ETAT.tV]}</caption><thead><tr><th>Profession</th><th>Groupe</th>${A.map(a => `<th>${a}</th>`).join("")}</tr></thead><tbody>`
    + export_.map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td>${r.slice(2).map(x => `<td>${fd(x)}</td>`).join("")}</tr>`).join("") + "</tbody></table>";
  if (window.cesure) window.cesure(document.getElementById("trajectoires"));
}
const dl = document.getElementById("deps");
Object.entries(NOMS).forEach(([c, n]) => { const o = document.createElement("option"); o.value = `${n} (${c})`; dl.appendChild(o); });
document.getElementById("tDep").oninput = e => { const m = e.target.value.match(/\(([0-9AB]{2,3})\)$/) || e.target.value.trim().match(/^([0-9AB]{2,3})$/);
  const c = m ? m[1] : null; if (c && NOMS[c]) { ETAT.tDep = c; trajectoires(); ecrireAdresse("trajectoires"); } else if (!e.target.value) { ETAT.tDep = null; trajectoires(); } };
document.querySelectorAll(".outil .onglets").forEach(barre => {
  const bs = [...barre.querySelectorAll("button")];
  const choisir = b0 => bs.forEach(b => { const on = b === b0; b.setAttribute("aria-selected", String(on)); b.tabIndex = on ? 0 : -1;
    document.getElementById(b.dataset.vue).hidden = !on; });
  // une vue qui reparaît se redessine à sa largeur (figures d'explorer_inegalites.js)
  bs.forEach((b, i) => { b.onclick = () => { choisir(b); dispatchEvent(new CustomEvent("fenetre", {detail: barre.closest(".fenetre")})); };
    b.onkeydown = e => { if (e.key === "ArrowRight" || e.key === "ArrowLeft") { const n = bs[(i + (e.key === "ArrowRight" ? 1 : bs.length - 1)) % bs.length]; choisir(n); n.focus(); } }; });
  choisir(bs[0]);
});
// outils des autres fichiers (explorer_inegalites.js, explorer_typologie.js, lots 2 et 3), appelés s'ils sont chargés ; le premier dessin attend que
// tous les fichiers de la page soient lus
function tout() { famille(); if (typeof inegalites === "function") inegalites(); if (typeof typologieE === "function") typologieE(); paires(); trajectoires(); if (window.cesure) window.cesure(document.querySelector(".explorer")); }
document.addEventListener("DOMContentLoaded", () => { lireAdresse(); tout(); });
