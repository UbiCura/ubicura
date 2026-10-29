// « Croiser deux indicateurs » dans Explorer (lot 2 du 29 octobre 2026, point 11 bis de la version 2). Ce fichier n'est
// jamais chargé seul : pipeline/explorer.py le réunit au noyau, à la carte et au nuage du moteur de l'atlas
// (atlas/moteur/) dans une seule fonction, d'où il lit leurs noms (S, D, scatter...). Il fournit ce que le nuage attend
// de sa page, render() et syncBar(), règle S d'après les réglages d'Explorer (ETAT, inscrits dans l'adresse) et range
// les réglages de la question dans la barre gardée en haut. Les figures, phrases et chiffres sont ceux de l'atlas, le
// même code les calcule.
const FAM_CX = {sm: SM, sante: SANTE, tout: "*"};
const NIV_CX = [["dep", "Départements"], ["epci", "Intercommunalités"]];
const MODES_CX = [["all", "Tous modes d'exercice"], ["lib", "Libéral"], ["sal", "Salarié"]];
const ECHELLES_CX = [["1", "Logarithmique"], ["0", "Linéaire"]];
const ANCRE_CX = "cxFenNuage";

function depuisEtat() {
  S.fam = FAM_CX[ETAT.fam] || SM;
  if (ETAT.cxProf) S.prof = ETAT.cxProf;
  S.level = ETAT.cxNiv === "dep" ? "dep" : "epci";
  S.mode = ETAT.cxMode in MI ? ETAT.cxMode : "all";
  if (ETAT.cxX) S.xvar = ETAT.cxX;
  S.yvar = ETAT.cxY || "";
  S.ylog = ETAT.cxLog === "0" ? "0" : "1";
}
function versEtat() {
  Object.assign(ETAT, {cxProf: S.prof, cxNiv: S.level, cxMode: S.mode, cxX: S.xvar, cxY: S.yvar || "", cxLog: S.ylog});
}
const apresCx = () => { render(); ecrireAdresse(ANCRE_CX); };

// réglages de la question (profession, niveau, exercice) et de la fenêtre (indicateurs, échelle), listes de l'atlas
function syncBar() {
  const prof = document.getElementById("prof");
  prof.value = S.prof;
  choixListe(prof, "cxProf", document.getElementById("cxProfAncre"));
  choix("cxNiv", NIV_CX, v => v === S.level, v => { S.level = v; S.sel = null; S.niveauAuto = false; }, apresCx);
  choix("cxMode", MODES_CX, v => v === S.mode, v => { S.mode = v; }, apresCx);
  choix("cxLog", ECHELLES_CX, v => v === S.ylog, v => { S.ylog = v; }, apresCx);
  for (const id of ["xvar", "yvar"]) {
    const sel = document.getElementById(id);
    sel.value = id === "xvar" ? S.xvar : (S.yvar || "");
    if (!sel.classList.contains("natif")) { sel.classList.add("natif"); sel.tabIndex = -1; }
    const b = choixListe(sel, id, sel);
    if (b) b.querySelector("button").setAttribute("aria-label", (sel.getAttribute("aria-label") || "Choix") + ", " + (sel.selectedOptions[0]?.textContent || ""));
  }
}

// tout redessiner après un changement de réglage (le nuage glisse d'une position à l'autre au même niveau)
function render() {
  hideTip();
  syncBar();
  scatter();
  croisementsBases();
  finitions();
}
// titre et phrase de la fenêtre, données à exporter, adresse, après chaque dessin du nuage (le nuage redessine seul
// quand on change d'indicateur, nuage.js)
function finitions() {
  signer();
  versEtat();
  document.getElementById("cxTitre").textContent = titreGraphe("scatter");
  document.getElementById("cxResume").textContent = (document.getElementById("scPhrase").hidden
    ? document.getElementById("scPrepare") : document.getElementById("scPhrase")).textContent;
  const e = EXPORT_CSV.scTable && EXPORT_CSV.scTable();
  if (e) donneesFigure("figCxNuage", e.nom + ".csv", e.texte.split("\r\n").map(l => l.split(";")));
  const a = document.getElementById("cxVersAtlas");
  if (a) a.href = a.getAttribute("href").split("#")[0] + "#?fam=" + ETAT.fam + "&prof=" + encodeURIComponent(S.prof) + "&niv=" + S.level;
  if (window.cesure) window.cesure(document.getElementById("qCroisements"));
}

document.getElementById("prof").addEventListener("change", e => { S.prof = e.target.value; apresCx(); });
// le nuage écoute déjà ses deux listes (nuage.js), l'adresse suit le choix
for (const id of ["xvar", "yvar"]) document.getElementById(id).addEventListener("change", () => setTimeout(() => { finitions(); ecrireAdresse(ANCRE_CX); }, 0));
document.querySelector("#" + ANCRE_CX + " .fen-lire").innerHTML = '<div class="comment-lire">' + howHtml("correlation,force,effet_ville,ecologique") + "</div>";

depuisEtat();
prep();
// une famille choisie en haut de la page (explorer.js, tout()) refait les listes et le nuage
window.croisementsE = () => { depuisEtat(); buildSelects(); render(); };
render();
// un lien qui vise la fenêtre (depuis l'atlas, une case des corrélations) la montre une fois dessinée
if (/^#(cxFenNuage|qCroisements)/.test(location.hash)) requestAnimationFrame(() => document.getElementById("qCroisementsT").scrollIntoView({block: "start"}));
