// Moteur de l'atlas, module « noyau » (découpage du 29 octobre 2026, docs/note_atlas_2026-10-29.md).
// Commun à l'atlas et à Explorer. État des réglages (S) et données (D), formats et graduations, phrases de lecture
// (mêmes règles que pipeline/lecture.py), limites des données et signaux « ! », grille des figures, citation, signature
// et exports (PNG, SVG, CSV), encadrés et « Citer et exporter », « Comment lire », familles et moyenne des territoires
// (refD), infobulle, listes de choix et menu en deux temps.
// Les modules sont réunis dans une seule fonction au moment de la construction (atlas/construire_atlas.py, moteur()) et
// partagent ses noms. Celui-ci ne dépend d'aucun autre.
const topo=window.TOPO;
let D=window.DONNEES;
const S={lieux:"",vue:"carte",tab:"carte",fam:"Santé mentale",prof:"psychologue",level:"epci",mode:"all",metric:"dens",sel:null,grp:"*",sort:null,asc:false,xvar:"revenu_median",ylog:"1",bvMode:"tiers",bvVar:"suicides",gwProf:"psychologue"};
const SM="Santé mentale",SANTE="Santé";
const MI={lib:0,sal:1,all:2};
// graduations des axes, nombres en français (jamais « 16k » ni « 20% ») et libellés jamais serrés. En échelle
// logarithmique, les valeurs rondes (1, 2, 5 de chaque puissance de 10) passent d'abord, les autres seulement s'il reste
// la place (au moins minPx pixels entre deux libellés).
const nbAxe=v=>(+v).toLocaleString("fr-FR",{maximumSignificantDigits:3});
const pctAxe=v=>(+v*100).toLocaleString("fr-FR",{maximumFractionDigits:0})+" %";
function graduations(sc,n,minPx){const cand=sc.base?sc.ticks(n*3):sc.ticks(n);if(!sc.base)return cand;
  const mant=v=>+(v/10**Math.floor(Math.log10(v))).toFixed(6),rang=v=>{const k=mant(v);return k===1?0:k===2||k===5?1:k===1.5||k===3||k===4?2:3};
  const pris=[];for(const v of cand.slice().sort((a,b)=>rang(a)-rang(b)))if(pris.every(u=>Math.abs(sc(u)-sc(v))>=minPx))pris.push(v);
  return pris.sort((a,b)=>a-b)}
const fmt=new Intl.NumberFormat("fr-FR"),f1=new Intl.NumberFormat("fr-FR",{minimumFractionDigits:1,maximumFractionDigits:1}),f2=new Intl.NumberFormat("fr-FR",{minimumFractionDigits:2,maximumFractionDigits:2});
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const RAMP=()=>["--r0","--r1","--r2","--r3","--r4","--r5"].map(css);
const DIV=()=>["--d0","--d1","--d2","--d3","--d4","--d5","--d6"].map(css);
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const cap=s=>s?s[0].toUpperCase()+s.slice(1):s;

// ---------- phrases (mêmes règles et mêmes seuils que pipeline/lecture.py)
const LIAISON=new Set(["de","du","des","d","en","pour","a","au","aux","l","la","le","et"]);
function pluriel(lib){let fige=false;return String(lib).toLowerCase().split(" ").map(mot=>{const m=mot.match(/^(.*?)([,.;]*)$/),corps=m[1],ponct=m[2];if(fige||!corps||LIAISON.has(corps.split("'")[0])||corps.startsWith("(")){fige=true;return mot}return corps.split("-").map(p=>!p||/[sx]$/.test(p)?p:(/al$/.test(p)?p.slice(0,-2)+"aux":p+"s")).join("-")+ponct}).join(" ")}
const deMot=m=>(/^[aeiouyéèêàâîôûh]/i.test(m)?"d’":"de ")+m;
const FEM=new Set(["sage_femme"]);
const un=p=>FEM.has(p)?"une":"un";
function unPour(d){if(!d||d<=0||!isFinite(d))return"";const n=1e4/d;const a=n>=1000?Math.round(n/100)*100:n>=100?Math.round(n/10)*10:Math.round(n);return fmt.format(a)}
const forceLien=r=>{const a=Math.abs(r);return a<.1?"négligeable":a<.3?"faible":a<.5?"modéré":"fort"};
const phraseGini=g=>g<.2?"assez homogène sur le territoire":g<.35?"modérément inégale":g<.5?"nettement inégale":"très concentrée dans certains territoires";
function fois(a,b){if(!b||!isFinite(a/b))return"";const r=a/b;if(r>=1.5)return f1.format(r)+" fois plus";if(r>=1)return Math.round((r-1)*100)+" % de plus";if(r>.67)return Math.round((1-r)*100)+" % de moins";return r>0?f1.format(1/r)+" fois moins":"aucun"}
const minuscule=s=>!s||(s.length>1&&s[1]===s[1].toUpperCase()&&s[1]!==s[1].toLowerCase())?s:s[0].toLowerCase()+s.slice(1);
function phraseCorrelation(rho,indic,lab,ic){if(rho==null||!isFinite(rho))return"";const f=forceLien(rho);
  if(ic&&ic[0]!=null&&ic[1]!=null&&ic[0]<0&&ic[1]>0&&f!=="négligeable")return"Aucun lien net n’apparaît entre l’indicateur « "+minuscule(indic)+" » et la présence "+deMot(pluriel(lab))+". La corrélation mesurée ("+f2.format(rho)+") est trop incertaine pour conclure, elle pourrait aussi bien être nulle (fourchette plausible de "+f2.format(ic[0])+" à "+f2.format(ic[1])+").";if(f==="négligeable")return"Aucun lien notable entre l’indicateur « "+minuscule(indic)+" » et la présence "+deMot(pluriel(lab))+".";return"Les territoires où l’indicateur « "+minuscule(indic)+" » est élevé comptent plutôt "+(rho>0?"plus":"moins")+" "+deMot(pluriel(lab))+". Le lien est "+f+" (rho = "+f2.format(rho)+"). Ce lien décrit des territoires et ne dit rien d’une cause."}
function valeursReg(xs){return(xs.length>1?"les valeurs de ":"la valeur de ")+(xs.length<2?xs.join(""):xs.slice(0,-1).join(", ")+" et "+xs[xs.length-1])+(xs.length>1?" sont plus hautes":" est plus haute")}
function phraseDeux(rho,ic,xl,yl,lv){if(rho==null||!isFinite(rho))return"";const f=forceLien(rho),qui=lv==="dep"?"Les départements":lv==="reg"?"Les régions":"Les intercommunalités";
  if(ic&&ic[0]!=null&&ic[0]<0&&ic[1]>0&&f!=="négligeable")return"Aucun lien net n’apparaît entre « "+minuscule(xl)+" » et « "+minuscule(yl)+" ». La corrélation mesurée ("+f2.format(rho)+") est trop incertaine pour conclure, elle pourrait aussi bien être nulle (fourchette plausible de "+f2.format(ic[0])+" à "+f2.format(ic[1])+").";
  if(f==="négligeable")return"Aucun lien notable entre « "+minuscule(xl)+" » et « "+minuscule(yl)+" ».";
  return qui+" où « "+minuscule(xl)+" » est élevé ont plutôt une valeur "+(rho>0?"plus élevée":"plus basse")+" de « "+minuscule(yl)+" ». Le lien est "+f+" (rho = "+f2.format(rho)+(ic&&ic[0]!=null?", fourchette plausible de "+f2.format(ic[0])+" à "+f2.format(ic[1]):"")+"). Il décrit des territoires et ne dit rien d’une cause."}
function liste(ps){ps=ps.slice(0,3).map(pluriel);return ps.length===1?ps[0]:ps.slice(0,-1).join(", ")+" et "+ps[ps.length-1]}

// ---------- limites connues des données, avec leurs sources (config.LIMITES)
function cleLimite(id){const L=D.limites||{};if(L[id])return id;for(const [debut,k] of Object.entries(D.limites_alias||{}))if(id.startsWith(debut))return k;return null}
// Chaque limite tient en une ligne sous la figure (sa phrase courte, ou la première phrase de son texte), la précision
// propre au territoire reste visible, le texte entier et ses sources s'ouvrent au clic (chantier d'organisation de
// l'atlas, 22 octobre 2026). Rien n'est retiré, seul l'étagement change.
function limiteCourte(L){if(L.court)return L.court;const m=L.texte.match(/^(.+?[.])(\s|$)/);return m?m[1]:L.texte}
function limiteHtml(ids,codes){const vues=new Set();let h="";
  for(const id of ids){const k=cleLimite(id);if(!k||vues.has(k))continue;vues.add(k);const L=D.limites[k];let terr="";
    for(const c of (codes||[]))if(c&&L.territoires?.[c]){terr=L.territoires[c];break}
    // structures déclarées à la SAE et absentes des bases (audit du 30 octobre 2026), la phrase du territoire, qui
    // nomme chaque type et ses nombres, tient lieu de résumé, l'explication reste dans le texte qui s'ouvre au clic
    const seul=terr&&k==="manque_sae";
    h+='<details class="asavoir"><summary><strong>À savoir.</strong> '+(seul?esc(terr):esc(limiteCourte(L))+(terr?' <span class="asavoir-terr">'+esc(terr)+'</span>':''))+'</summary>'+
       '<p>'+esc(L.texte)+' Source, '+L.sources.map(([ti,u])=>'<a href="'+esc(u)+'" target="_blank" rel="noopener">'+esc(ti)+'</a>').join(", ")+'.</p></details>'}
  return h}

// ---------- grille très légère, la même sur tous les graphiques
function grille(svg,y,m,w,n){svg.append("g").attr("class","grille").attr("transform","translate("+m.l+",0)")
  .call(d3.axisLeft(y).tickValues(graduations(y,n,24)).tickSize(-(w-m.l-m.r)).tickFormat(""))
  .call(g=>{g.select(".domain").remove();g.selectAll("line").attr("stroke",css("--line")).attr("stroke-opacity",.45)})}

// ---------- citation et signature des graphiques
// Une capture d'écran ne peut pas être empêchée, chaque graphique porte donc sa source, et un bouton donne la citation.
function dateDonnees(){const g=D.meta.genere_le||"";return g?new Date(g+"T12:00").toLocaleDateString("fr-FR",{day:"numeric",month:"long",year:"numeric"}):""}
function citationTexte(titre){const c=D.citation||{},a=(D.meta.genere_le||"").slice(0,4);
  // avec un DOI, citation formelle sur le titre du dépôt Zenodo des données, sans le nom du site
  if(c.doi&&c.titre_donnees&&(!c.version_zenodo||c.version_zenodo===D.meta.genere_le||!c.adresse))return (c.auteur_court||"Pithon L.")+" ("+a+"). "+titre+". D’après « "+c.titre_donnees+" », version du "+dateDonnees()+". Zenodo. https://doi.org/"+c.doi;
  // version plus récente que la dernière archivée sur Zenodo, citée par l'adresse du site
  if(c.doi&&c.titre_donnees)return (c.auteur_court||"Pithon L.")+" ("+a+"). "+titre+". D’après « "+c.titre_donnees+" », version du "+dateDonnees()+", "+c.adresse+". Dernière version archivée, Zenodo, https://doi.org/"+c.doi;
  return (c.auteur_court||"Pithon L.")+" ("+a+"). "+titre+". "+(c.projet||"Ubi Cura")+", données du "+dateDonnees()+"."+(c.adresse?" "+c.adresse:"")}
// zone de la page que le moteur gère, toute la page dans l'atlas, la seule question qui le charge dans Explorer
// (attribut data-moteur), pour ne toucher ni aux textes ni à la signature des autres figures de la page
const ZONE_MOTEUR=document.querySelector("[data-moteur]")||document.body;
const GRAPHES=[...ZONE_MOTEUR.querySelectorAll('svg[role="img"][id]')].map(x=>x.id);
function titreGraphe(id){
  if(id==="map"){const mb=document.querySelector('#metricSeg [aria-pressed="true"]');return "Carte, "+pluriel(profLab(S.prof))+", "+(mb?mb.textContent.toLowerCase():"")+", par "+({reg:"région",dep:"département",epci:"intercommunalité"}[S.level])}
  if(id==="scatter"){const cx=IDX.ctx.find(c=>c.id===S.xvar),cy=S.yvar?IDX.ctx.find(c=>c.id===S.yvar):null;return "Nuage de points, "+(cy?minuscule(cy.label):pluriel(profLab(S.prof)))+" et "+(cx?minuscule(cx.label):"")+", par "+(S.level==="dep"?"département":"intercommunalité")}
  if(id==="lxCarte"){const u=S.sel&&D.niveaux[S.sel.lv].units[IDX[S.sel.lv].get(S.sel.c)],o=document.getElementById("lxType")?.selectedOptions[0];
    return "Plan des structures de soins, "+(o?minLib(o.textContent.replace(/\s*\(\d[\d\s\u202f]*\)$/,"")):"")+(u?", "+u.nm:"")+", FINESS et ROR réunis"}
  if(id==="tmap")return "Carte des groupes de territoires, "+({sm:"santé mentale",sante:"santé",tout:"toute l’offre"}[famCle()]||"")+", par intercommunalité";
  if(id==="regPlot"){const r=document.getElementById("regRes");return "Régression multiple, "+(r&&r.selectedOptions[0]?minuscule(r.selectedOptions[0].textContent):"")+", par département"}
  // titre du panneau, puis la profession quand la figure en dépend, puis le choix fait dans le menu du panneau
  const pan=document.getElementById(id).closest(".panel"),h=pan&&pan.querySelector("h2"),sel=pan&&pan.querySelector("select");
  let t=h?texteTitre(h):(document.getElementById(id).getAttribute("aria-label")||id);
  if(["escalier","funnel","effetVille","pcPlot"].includes(id))t+=", "+pluriel(profLab(S.prof))+(id==="pcPlot"?"":", par "+({dep:"département",epci:"intercommunalité",reg:"région"}[S.level]||""));
  if(sel&&sel.selectedOptions[0])t+=", "+minuscule(sel.selectedOptions[0].textContent.trim());
  return t}
// repère les tableaux qui défilent de côté (fondu sur le bord, phrase d'indication sous le tableau)
const DEFIL=new ResizeObserver(es=>es.forEach(e=>majDefil(e.target.parentElement)));
function majDefil(b){if(!b)return;
  // tableaux des corrélations, défilement de côté dès que le tableau dépasse son cadre, mesuré quand l'onglet s'affiche
  // ou que la largeur change (mesuré au dessin seulement, l'onglet caché laissait le tableau élargir la page du
  // téléphone, 657 pixels pour 375, relevé du 29 octobre 2026)
  if(b.classList.contains("hmbox")&&b.closest("#hmCadres")){const t=b.querySelector("table");b.classList.toggle("defile-x",!!t&&t.offsetWidth>b.clientWidth+1)}
  const d=b.scrollWidth>b.clientWidth+2;b.classList.toggle("deborde-d",d&&b.scrollLeft+b.clientWidth<b.scrollWidth-2);b.classList.toggle("deborde-g",d&&b.scrollLeft>2);
  let n=b.nextElementSibling;if(!(n&&n.classList.contains("indice-defil"))){if(!d)return;n=document.createElement("p");n.className="indice-defil";n.textContent="Faites défiler le tableau vers la droite pour voir les autres colonnes.";b.after(n)}n.hidden=!d}
document.querySelectorAll(".scroll,.hmbox,.tabdonnees").forEach(b=>{b.addEventListener("scroll",()=>majDefil(b),{passive:true});new MutationObserver(()=>{const t=b.querySelector("table");if(t&&!t.dataset.observe){t.dataset.observe=1;DEFIL.observe(t)}majDefil(b)}).observe(b,{childList:true,subtree:true});const t=b.querySelector("table");if(t){t.dataset.observe=1;DEFIL.observe(t)}});
addEventListener("resize",()=>document.querySelectorAll(".scroll,.hmbox,.tabdonnees").forEach(majDefil));
function signer(){
  for(const id of GRAPHES){const el=document.getElementById(id);if(!el||!el.closest("section")||el.closest("section").classList.contains("hidden"))continue;
    // une bande de 16 unités ajoutée sous le graphique reçoit la signature, elle ne recouvre jamais un libellé
    const cur=el.getAttribute("viewBox");if(el.dataset.vbSigne!==cur){const [x0,y0,w0,h0]=cur.split(/[ ,]+/).map(Number);const nv=[x0,y0,w0,h0+16].join(" ");el.setAttribute("viewBox",nv);el.dataset.vbSigne=nv}
    const sv=d3.select(el),vb=el.viewBox.baseVal;sv.selectAll("text.signature").remove();
    sv.append("text").attr("class","signature").attr("x",vb.x+vb.width-6).attr("y",vb.y+vb.height-4).attr("text-anchor","end")
      .text((D.citation?.projet||"Ubi Cura")+", données du "+dateDonnees()+(D.citation?.doi?", doi:"+D.citation.doi:""))}}
// échelle typographique commune des figures (harmonisation, 22 octobre 2026), les mêmes tailles que dans les rapports
// (graphiques.TYPO), telles qu'on les voit à l'écran quelle que soit la largeur de la figure. Chaque texte garde sa
// taille d'origine (data-fs0), qui dit son rôle, titre, texte ou petit, et reçoit la taille qui donne ce rôle à
// l'écran. Recalculé quand une figure est redessinée ou change de largeur. Un texte marqué data-typo-libre (le « ! »
// des signaux, posé dans son cercle) garde sa taille.
const TYPO={titre:14,texte:12.5,petit:11.5};
const roleTexte=fs=>fs>=12.75?"titre":fs>=10.75?"texte":"petit";
function normaliserTextes(svg){
  const vb=svg.viewBox&&svg.viewBox.baseVal,w=svg.getBoundingClientRect().width;
  if(!vb||!vb.width||w<40)return;
  // la carte, plus réduite que les autres figures, garde des libellés lisibles (encarts d'outre-mer)
  const k=vb.width/Math.max(w,vb.width*(svg.classList.contains("map")?.5:.9));
  svg.querySelectorAll("text").forEach(t=>{
    if(t.hasAttribute("data-typo-libre"))return;
    if(!t.dataset.fs0){const f=parseFloat(getComputedStyle(t).fontSize);if(!f)return;t.dataset.fs0=f}
    t.style.fontSize=(TYPO[roleTexte(+t.dataset.fs0)]*k).toFixed(2)+"px"});
  const b=svg.getBoundingClientRect(),ticks=[...svg.querySelectorAll(".tick text")];
  ticks.forEach(t=>{t.style.visibility="";const r=t.getBoundingClientRect();if(!r.width)return;
    if(r.right>b.right+.5)t.setAttribute("text-anchor","end");else if(r.left<b.left-.5)t.setAttribute("text-anchor","start")});
  // une graduation qui toucherait un autre texte est masquée, jamais un libellé
  const touche=(a,c)=>Math.min(a.right,c.right)-Math.max(a.left,c.left)>1&&Math.min(a.bottom,c.bottom)-Math.max(a.top,c.top)>2;
  const fixes=[...svg.querySelectorAll("text")].filter(t=>!t.closest(".tick")&&t.textContent.trim()).map(t=>t.getBoundingClientRect()).filter(r=>r.width);
  const gardes=[];
  ticks.forEach(t=>{const r=t.getBoundingClientRect();if(!r.width||!t.textContent.trim())return;
    if(fixes.some(c=>touche(r,c))||gardes.some(c=>touche(r,c)))t.style.visibility="hidden";else gardes.push(r)})}
const TYPO_VUS=new WeakSet(),TYPO_A_FAIRE=new Set();let typoPrevu=0;
// minuteur plutôt que requestAnimationFrame, qui ne part pas tant que l'onglet est en arrière-plan
function typoPlanifier(){if(typoPrevu)return;typoPrevu=setTimeout(()=>{typoPrevu=0;TYPO_A_FAIRE.forEach(normaliserTextes);TYPO_A_FAIRE.clear()},30)}
const TYPO_RO=new ResizeObserver(es=>{es.forEach(e=>TYPO_A_FAIRE.add(e.target));typoPlanifier()});
new MutationObserver(ms=>{ms.forEach(m=>{let s=m.target.closest?m.target.closest("svg"):null;while(s&&s.ownerSVGElement)s=s.ownerSVGElement;
  if(!s)return;if(!TYPO_VUS.has(s)){TYPO_VUS.add(s);TYPO_RO.observe(s)}TYPO_A_FAIRE.add(s)});typoPlanifier()})
  .observe(ZONE_MOTEUR,{childList:true,subtree:true});
// export d'un graphique (harmonisation, lot 5, 22 octobre 2026), toujours sur fond blanc avec les couleurs du fond clair
// quel que soit le fond affiché (décision de Lucas), toujours en vue entière même si la carte est zoomée, à une taille
// commune (dessin rapporté à 800 pixels, image à 1 600), texte à l'échelle typographique commune, légende puis citation
// à la largeur de la figure. Les couleurs du fond clair sont lues en basculant le thème le temps d'un calcul, sans dessin.
const VARS_COULEUR=["--bg","--panel","--ink","--muted","--line","--nodata","--accent","--signal","--focus","--contour","--r0","--r1","--r2","--r3","--r4","--r5","--d0","--d1","--d2","--d3","--d4","--d5","--d6"];
const LARGEUR_EXPORT=800;
function enRgb(c){const e=document.createElement("span");e.style.color=c;document.body.appendChild(e);const v=getComputedStyle(e).color;e.remove();return v}
function couleursClaires(){const r=document.documentElement,t=r.getAttribute("data-theme"),cur=VARS_COULEUR.map(v=>enRgb(css(v)));
  r.setAttribute("data-theme","light");const cl=VARS_COULEUR.map(v=>enRgb(css(v)));if(t)r.setAttribute("data-theme",t);else r.removeAttribute("data-theme");
  // une même couleur peut servir à deux variables (fond et contour en fond sombre), un trait prend d'abord le contour
  const m=new Map(),mt=new Map(),ordreTrait=["--contour","--line",...VARS_COULEUR];cur.forEach((c,i)=>{if(!m.has(c))m.set(c,cl[i])});
  ordreTrait.forEach(v=>{const i=VARS_COULEUR.indexOf(v);if(!mt.has(cur[i]))mt.set(cur[i],cl[i])});
  return {vers:(c,trait)=>{if(!c||c==="none")return c;const k=enRgb(c);return (trait?mt:m).get(k)||c},clair:Object.fromEntries(VARS_COULEUR.map((v,i)=>[v,cl[i]]))}}
const STYLES_EXPORT=["fill","fill-opacity","stroke","stroke-width","stroke-opacity","stroke-dasharray","opacity","font-family","font-size","font-weight","text-anchor","dominant-baseline","display"];
function svgExport(id,citation){
  const src=document.getElementById(id),clone=src.cloneNode(true),a=[src,...src.querySelectorAll("*")],b=[clone,...clone.querySelectorAll("*")];
  const {vers,clair}=couleursClaires();
  a.forEach((el,i)=>{const cs=getComputedStyle(el);STYLES_EXPORT.forEach(pr=>{let v=cs.getPropertyValue(pr);if(v&&(pr==="fill"||pr==="stroke"))v=vers(v,pr==="stroke");if(v)b[i].style.setProperty(pr,v)});b[i].removeAttribute("class")});
  const vb=src.viewBox.baseVal,ns="http://www.w3.org/2000/svg",ech=vb.width/LARGEUR_EXPORT,fs=TYPO.petit*ech;
  // texte à l'échelle commune, comme si la figure faisait 800 pixels de large
  clone.querySelectorAll("text[data-fs0]").forEach(t=>t.style.setProperty("font-size",(TYPO[roleTexte(+t.dataset.fs0)]*ech).toFixed(2)+"px"));
  // vue entière, le zoom de la carte est retiré, les symboles qu'il réduisait retrouvent leur taille
  const zg=clone.querySelector("g[clip-path] > g[transform]");
  if(zg){const k=+((zg.getAttribute("transform").match(/scale\(([\d.]+)/)||[0,1])[1]);zg.removeAttribute("transform");
    zg.querySelectorAll("g.fragile,[data-x]").forEach(f=>{if(f.dataset.x!=null)f.setAttribute("transform","translate("+f.dataset.x+","+f.dataset.y+")")});
    zg.querySelectorAll("circle").forEach(c=>{const r=+c.getAttribute("r");if(r&&k>1){c.setAttribute("r",r*k);const sw=parseFloat(c.style.strokeWidth);if(sw)c.style.strokeWidth=sw*k}})}
  // légende des cartes, recopiée depuis la légende affichée sous la carte (HTML)
  const leg=[],lg=id==="map"?document.getElementById("legend"):id==="tmap"?document.getElementById("tyLegende"):null;
  if(id==="lxCarte")leg.push({cle:css("--ink"),t:"Point plein, structure confirmée par une source indépendante de FINESS et du ROR"},{t:"Point creux, structure inscrite dans FINESS ou le ROR seulement, à vérifier"});
  if(id==="regPlot")leg.push({cle:css("--r4"),t:"Lien positif"},{cle:css("--d1"),t:"Lien négatif"},{t:"Point et trait, départements de l’Hexagone avec leur fourchette plausible à 95 %, couleur pâle si la fourchette englobe zéro."},{cle:css("--muted"),t:"Losange gris, sans l’Île-de-France"});
  if(lg&&id==="tmap")lg.querySelectorAll("li").forEach(li=>leg.push({cle:getComputedStyle(li.querySelector("i")).backgroundColor,t:li.querySelector("span").textContent}));
  else if(lg)[...lg.children].forEach(el=>{
    if(el.querySelector(".sw"))leg.push({rampe:[...el.querySelectorAll(".sw span")].map(s=>s.style.background),ticks:[...el.querySelectorAll(".ticks span")].map(s=>s.textContent)});
    else if(el.children.length&&el.firstElementChild.style.background)leg.push({cle:el.firstElementChild.style.background,t:el.textContent.trim()});
    else if(el.textContent.trim())leg.push({t:el.textContent.trim()})});
  const g=document.createElementNS(ns,"g"),larg=vb.width-16;let x=0,y=0;
  const texte=(t,tx,ty,anc)=>{const e=document.createElementNS(ns,"text");e.setAttribute("x",tx);e.setAttribute("y",ty);e.setAttribute("fill",clair["--muted"]);e.setAttribute("font-size",fs);e.setAttribute("font-family","Work Sans, Segoe UI, sans-serif");if(anc)e.setAttribute("text-anchor",anc);e.textContent=t;g.appendChild(e)};
  const rect=(rx,ry,w,h,c)=>{const e=document.createElementNS(ns,"rect");e.setAttribute("x",rx);e.setAttribute("y",ry);e.setAttribute("width",w);e.setAttribute("height",h);e.setAttribute("fill",vers(c));g.appendChild(e)};
  const place=w=>{if(x>0&&x+w>larg){x=0;y+=fs*2.6}};
  leg.forEach(it=>{
    if(it.rampe){const cw=fs*3.2,w=cw*it.rampe.length;place(w);it.rampe.forEach((c,i)=>rect(x+i*cw,y,cw,fs*.9,c));it.ticks.forEach((t,i)=>{if(t)texte(t,x+i*cw,y+fs*2.1,"middle")});x+=w+fs*1.5}
    else if(it.cle){const w=fs*1.6+it.t.length*fs*.55;place(w);rect(x,y,fs*.9,fs*.9,it.cle);texte(it.t,x+fs*1.3,y+fs*.85);x+=w+fs}
    else{const w=it.t.length*fs*.55;place(w);texte(it.t,x,y+fs*.85);x+=w+fs}});
  // citation coupée en lignes selon la largeur du graphique
  const fc=TYPO.petit*ech,parLigne=Math.max(40,Math.floor((vb.width-16)/(fc*.55))),lignes=[];
  citation.split(" ").forEach(m=>{const l=lignes.length?lignes[lignes.length-1]:null;if(l!=null&&(l+" "+m).length<=parLigne)lignes[lignes.length-1]=l+" "+m;else lignes.push(m)});
  const hl=leg.length?y+fs*3.4:0,hc=14+fc*1.35*lignes.length+hl;
  g.setAttribute("transform","translate("+(vb.x+8)+","+(vb.y+vb.height+fs*.6)+")");if(leg.length)clone.appendChild(g);
  clone.setAttribute("xmlns",ns);clone.setAttribute("viewBox",[vb.x,vb.y,vb.width,vb.height+hc].join(" "));
  clone.setAttribute("width",LARGEUR_EXPORT*2);clone.setAttribute("height",Math.round((vb.height+hc)/ech*2));
  const fond=document.createElementNS(ns,"rect");fond.setAttribute("x",vb.x);fond.setAttribute("y",vb.y);fond.setAttribute("width",vb.width);fond.setAttribute("height",vb.height+hc);fond.setAttribute("fill","#FFFFFF");clone.insertBefore(fond,clone.firstChild);
  lignes.forEach((l,i)=>{const txt=document.createElementNS(ns,"text");txt.setAttribute("x",vb.x+8);txt.setAttribute("y",vb.y+vb.height+hl+fc*1.35*(i+1));txt.setAttribute("fill",clair["--muted"]);txt.setAttribute("font-family","Work Sans, Segoe UI, sans-serif");txt.setAttribute("font-size",fc);txt.textContent=l;clone.appendChild(txt)});
  return new XMLSerializer().serializeToString(clone)}
function pngExport(id,citation){return new Promise((ok,ko)=>{const img=new Image(),url=URL.createObjectURL(new Blob([svgExport(id,citation)],{type:"image/svg+xml"}));
  img.onload=()=>{const c=document.createElement("canvas");c.width=img.width;c.height=img.height;c.getContext("2d").drawImage(img,0,0);URL.revokeObjectURL(url);c.toBlob(b=>b?ok(b):ko(new Error("png")),"image/png")};
  img.onerror=ko;img.src=url})}
function telecharger(blob,nom){const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=nom;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
// tableaux citables et exportables, la citation et le fichier reprennent ce qui est affiché (famille, niveau, mode, filtre)
const TABLEAUX={tbl:()=>"Professionnels de santé par territoire, "+famLab[S.fam]+", "+({reg:"régions",dep:"départements",epci:"intercommunalités"}[S.level]||S.level),
  hm:()=>"Liens entre l’offre de soins et le profil des habitants, "+famLab[S.fam],
  cbTable:()=>"Croisements entre bases, par département"};
function tableauCsv(t){const lignes=[...t.querySelectorAll("tr")].filter(tr=>!tr.hidden&&tr.style.display!=="none");
  const cell=c=>{const v=c.textContent.replace(/\s+/g," ").trim();return /[;"\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v};
  return "\ufeff"+lignes.map(tr=>[...tr.children].map(cell).join(";")).join("\r\n")}
// figures en barres HTML (pas en image), citables avec leurs valeurs en CSV, boutons dans le titre du panneau
const FIG_HTML={secBars:()=>"Où exercent les "+pluriel(profLab(S.prof))+", par mode d’exercice et secteur",
  catBars:()=>"Établissements où exercent les "+pluriel(profLab(S.prof)),
  acpCharges:()=>"Poids de chaque profession dans les axes de la typologie, "+famLab[S.fam],
  acpAxes:()=>"Part des différences entre intercommunalités résumée par chaque axe, "+famLab[S.fam]};
function lignesHtml(el){
  if(el.querySelector("div.r"))return [["Libellé","Valeur"],...[...el.querySelectorAll("div.r")].map(r=>[...r.querySelectorAll(":scope > span")].map(x=>x.textContent.trim()))];
  const cases=[...el.children].map(x=>x.textContent.trim()),n=3,out=[];for(let k=0;k<cases.length;k+=n)out.push(cases.slice(k,k+n));if(out.length)out[0][0]=out[0][0]||"Profession";return out}
// ---------- encadrés, même tête partout et un seul « Citer et exporter » (version 2, point 1, 10 octobre 2026)
// Chaque encadré a son titre, puis une ligne avec « Comment lire » et « Citer et exporter ». La boîte de citation liste
// ce que contient l'encadré, repéré de lui-même (graphique ou carte, tableau, figure en barres, données sur mesure), avec
// les exports de chaque élément, chacun avec sa propre citation. Une nouvelle figure reçoit ses exports sans rien ajouter.
const EXPORT_CSV={};  // exports de données sur mesure, id de l'élément -> ()=>({titre,nom,texte})
const texteTitre=h=>{if(!h)return "";const c=h.cloneNode(true);c.querySelectorAll('[aria-hidden="true"],button.how,button.citer').forEach(x=>x.remove());return c.textContent.replace(/\s+/g," ").trim()};
function titreEncadre(row){const pan=row.closest(".panel");return texteTitre(pan&&pan.querySelector("h2"))}
const CANDIDATS='svg[role="img"][id],table[id],.hbars[id],.acpbar[id],[data-export]';
function elementsEncadre(row){
  let els;
  if(row.dataset.elements)els=row.dataset.elements.split(",").map(id=>document.getElementById(id)).filter(Boolean);
  else{const pan=row.closest(".panel");if(!pan)return [];els=[...pan.querySelectorAll(CANDIDATS)];
    const avec=(row.closest("[data-avec]")||pan).dataset.avec;if(avec)els.push(...avec.split(",").map(id=>document.getElementById(id)).filter(Boolean))}
  return els}
function genreElement(el){return el.dataset.export?"donnees":el.tagName==="svg"?(el.classList.contains("map")?"carte":"graphique"):el.tagName==="TABLE"?"tableau":"barres"}
function titreElement(el){const id=el.id,g=genreElement(el);
  if(g==="donnees"&&EXPORT_CSV[el.dataset.export])return EXPORT_CSV[el.dataset.export]().titre;
  if(g==="carte"||g==="graphique")return titreGraphe(id);
  if(g==="tableau")return TABLEAUX[id]?TABLEAUX[id]():(el.getAttribute("aria-label")||texteTitre(el.closest(".panel")?.querySelector("h2")));
  return FIG_HTML[id]?FIG_HTML[id]():texteTitre(el.closest(".panel")?.querySelector("h2"))}
const nomFichier=(t,id)=>(t.normalize("NFD").replace(/[̀-ͯ]/g,"").replace(/[^A-Za-z0-9]+/g,"_").replace(/^_|_$/g,"").slice(0,80)||id).toLowerCase();
const qCsv=v=>{v=String(v);return /[;"\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v};
function exporterCsv(el,titre,c){
  const sur=el.dataset.export?EXPORT_CSV[el.dataset.export]:EXPORT_CSV[el.id];
  if(sur){const x=sur();telecharger(new Blob(["﻿"+x.texte+"\r\n\r\n"+c],{type:"text/csv;charset=utf-8"}),(x.nom||nomFichier(titre,el.id))+".csv");return}
  const corps=el.tagName==="TABLE"?tableauCsv(el):"﻿"+lignesHtml(el).map(l=>l.map(qCsv).join(";")).join("\r\n");
  telecharger(new Blob([corps+"\r\n\r\n"+c],{type:"text/csv;charset=utf-8"}),nomFichier(titre,el.id)+".csv")}
function remplirCitation(row,boite){
  const els=elementsEncadre(row).filter(el=>el.childElementCount>0&&!el.closest(".hidden"));
  const titreE=els.length===1?titreElement(els[0]):titreEncadre(row),c0=citationTexte(titreE);
  const LIB={carte:"Carte",graphique:"Graphique",tableau:"Tableau",barres:"Figure",donnees:"Données"};
  let h='<p>'+esc(c0)+'</p><div class="hmbar"><button class="btn ghost" type="button" data-a="cit">Copier la citation</button></div>';
  if(els.length){h+='<ul class="exports">'+els.map((el,k)=>{const g=genreElement(el),img=g==="carte"||g==="graphique";
    return '<li><span class="nom"><span class="genre">'+LIB[g]+'</span> '+esc(titreElement(el))+'</span><span class="acts">'
      +(img?'<button class="btn ghost" type="button" data-a="img" data-k="'+k+'">Copier l’image</button><button class="btn ghost" type="button" data-a="png" data-k="'+k+'">PNG</button><button class="btn ghost" type="button" data-a="svg" data-k="'+k+'">SVG</button>'
        :'<button class="btn ghost" type="button" data-a="csv" data-k="'+k+'">CSV</button>')+'</span></li>'}).join("")+'</ul>';
    h+='<p class="small muted" style="margin:6px 0 0">Chaque fichier porte sa propre citation, avec la version des données. Merci de la joindre à toute reprise.</p>'}
  boite.innerHTML=h;
  boite.querySelector('[data-a="cit"]').onclick=async e=>{try{await navigator.clipboard.writeText(c0);e.target.textContent="Citation copiée"}catch(_){e.target.textContent="Copie impossible ici"}};
  boite.querySelectorAll("button[data-k]").forEach(bt=>bt.onclick=async()=>{const el=els[+bt.dataset.k],a=bt.dataset.a,t=titreElement(el),c=citationTexte(t),ok=m=>{bt.textContent=m};
    try{if(a==="csv"){exporterCsv(el,t,c);ok("Enregistré")}
      else if(a==="svg"){telecharger(new Blob([svgExport(el.id,c)],{type:"image/svg+xml"}),nomFichier(t,el.id)+".svg");ok("Enregistré")}
      else{const png=await pngExport(el.id,c);if(a==="png"){telecharger(png,nomFichier(t,el.id)+".png");ok("Enregistré")}
        else{await navigator.clipboard.write([new ClipboardItem({"image/png":png})]);ok("Image copiée")}}}
    catch(e){ok(a==="img"?"Copie impossible ici, utilisez PNG":"Opération impossible")}})}
function normaliserEncadres(){
  // tête de chaque encadré, les boutons « Comment lire » quittent le titre pour la ligne d'en dessous
  document.querySelectorAll(".panel").forEach(pan=>{const h=pan.querySelector("h2");if(!h||h.closest(".panel")!==pan||pan.querySelector(".outils-encadre"))return;
    const hows=[...h.querySelectorAll("button.how")],row=document.createElement("div");row.className="outils-encadre";
    hows.forEach(b=>row.appendChild(b));if(h.lastChild&&h.lastChild.nodeType===3)h.lastChild.textContent=h.lastChild.textContent.replace(/\s+$/,"");
    if(hows.length||pan.querySelector(CANDIDATS)||((pan.dataset.avec||pan.querySelector("[data-avec]"))))h.after(row)});
  // un seul « Citer et exporter » par ligne, quand l'encadré contient de quoi citer
  document.querySelectorAll(".outils-encadre").forEach(row=>{if(row.querySelector("button.citer")||!elementsEncadre(row).length)return;
    const b=document.createElement("button");b.type="button";b.className="citer";b.textContent="Citer et exporter";b.setAttribute("aria-expanded","false");
    const boite=document.createElement("div");boite.className="citation hidden";row.appendChild(b);row.after(boite);
    b.onclick=()=>{const ouvert=boite.classList.contains("hidden");b.setAttribute("aria-expanded",String(ouvert));if(ouvert)remplirCitation(row,boite);boite.classList.toggle("hidden",!ouvert)}})}
// ---------- « Comment lire »
let GL=new Map();
function howHtml(keys){return keys.split(",").map(k=>GL.get(k)).filter(Boolean).map(g=>'<p><strong>'+esc(g.terme)+'.</strong> '+esc(g.definition)+'</p>').join("")||'<p>Explication absente de ce fichier de données.</p>'}
document.addEventListener("click",e=>{const b=e.target.closest("button.how");if(!b)return;
  // texte juste après le bouton, sinon après son titre, en sautant le bloc de citation ajouté par « Citer »
  let t=b.nextElementSibling;
  if(!t||!t.classList.contains("howtxt")){t=b.parentElement.nextElementSibling;while(t&&t.classList.contains("citation"))t=t.nextElementSibling}
  if(!t||!t.classList.contains("howtxt"))return;
  const open=t.classList.contains("hidden");if(open)t.innerHTML=howHtml(b.dataset.how);t.classList.toggle("hidden",!open);b.setAttribute("aria-expanded",String(open))});

// ---------- familles
const famOf=p=>p.famille||(p.groupe==="Santé mentale"?SM:SANTE);
const natOf=p=>p.nature||"profession";
const inFam=p=>S.fam==="*"||famOf(p)===S.fam;
const ctxVisibles=()=>IDX.ctx.filter(c=>!c.famille||S.fam==="*"||c.famille===S.fam);
// taux d'un type de structure montré avec son nombre (décision de Lucas du 30 octobre 2026, « 2 EHPAD, soit 268 pour
// 100 000 personnes de 80 ans et plus »), le nombre venant des comptes de l'encadré des structures (niveaux.*.lieux)
function nombreStructures(c,lv,i){if(!c||!String(c.id).startsWith("lieux_"))return null;const v=D.niveaux[lv]?.lieux?.[c.id.slice(6)];return v&&v[i]!=null?v[i]:null}
const motStructures=n=>n?fmt.format(n)+"\u00a0structure"+(n>1?"s":""):"aucune structure";
function texteTaux(c,lv,i,txt){const n=nombreStructures(c,lv,i);return n==null?txt:motStructures(n)+", soit "+txt}
// même chose en HTML pour la fiche, le nombre sur sa ligne au-dessus du taux, pour ne pas serrer le libellé sur téléphone
function htmlTaux(c,lv,i,txt){const n=nombreStructures(c,lv,i);return n==null?esc(txt):'<span class="nb-struct">'+esc(motStructures(n))+'</span>'+esc("soit "+txt)}
// les nombres d'un libellé ne se coupent pas en fin de ligne (« pour 100 000 personnes »)
const insecables=t=>String(t).replace(/(\d) (\d{3})/g,"$1\u00a0$2");
// libellé d'un indicateur suivi de son unité, sauf quand le libellé la dit déjà (« EHPAD, pour 100 000 personnes de 80 ans
// et plus » ne se répète pas entre parenthèses)
const libUnite=c=>c.label+(c.unite&&!c.label.includes(c.unite)?" ("+c.unite+")":"");
const ctxDispo=(lv,c)=>D.niveaux[lv].units.some(u=>u.x&&u.x[c.i]!=null);
const famLab={[SM]:"santé mentale",[SANTE]:"santé","*":"toute l’offre de soins"};

// ---------- data helpers
let IDX={};
function prep(){
  IDX={};
  for(const lv of ["reg","dep","epci"]){const L=D.niveaux[lv];if(L)IDX[lv]=new Map(L.units.map((u,i)=>[u.c,i]))}
  IDX.prof=new Map(D.professions.map(p=>[p.id,p]));
  IDX.ctx=D.contexte.map((c,i)=>({...c,i}));
  // temps médian par la route de chaque équipement (INSEE), ajouté aux indicateurs du nuage, par territoire
  (D.route||[]).forEach(e=>{const i=IDX.ctx.length;let vu=false;
    for(const lv of ["reg","dep","epci"]){const L=D.niveaux[lv],r=L&&L.route&&L.route[e.id];if(!L)continue;
      L.units.forEach((u,k)=>{if(!u.x)u.x=[];const v=r&&r[k]?r[k][1]:null;u.x[i]=v;if(v!=null)vu=true})}
    if(vu)IDX.ctx.push({id:"route:"+e.id,label:"Temps médian par la route, "+e.lib.charAt(0).toLowerCase()+e.lib.slice(1),unite:"minutes",
      groupe:"Temps de trajet par la route",famille:e.fam||null,source:"",explication:"Durée en voiture, aux heures creuses, jusqu’à l’équipement le plus proche, médiane des habitants du territoire (INSEE).",i})});
  // part de l'exercice libéral par territoire (demande de Lucas du 23 octobre 2026), ajoutée aux indicateurs du nuage
  // avec la règle de analyses.part_liberal : pas de part sous l'effectif minimal de la profession dans le territoire
  const PL=D.meta.part_liberal;
  if(PL)PL.professions.forEach(p=>{const pr=IDX.prof.get(p);if(!pr)return;const i=IDX.ctx.length;
    for(const lv of ["reg","dep","epci"]){const L=D.niveaux[lv],a=L&&L.n[p];if(!L)continue;
      L.units.forEach((u,k)=>{if(!u.x)u.x=[];const t=a?a.all[k]:0;u.x[i]=a&&t>=PL.minimum?Math.round(a.lib[k]/t*1000)/10:null})}
    IDX.ctx.push({id:"lib_part:"+p,label:"Part de l’exercice libéral, "+pluriel(pr.libelle).toLowerCase(),unite:"%",
      groupe:"Exercice libéral",famille:famOf(pr),source:"",i,
      explication:"Part des "+pluriel(pr.libelle).toLowerCase()+" du territoire qui déclarent une activité libérale, parmi tous ceux qui y exercent (répertoire RPPS). Une personne qui exerce aussi en salariée compte comme libérale. Non calculée quand le territoire compte moins de "+PL.minimum+" professionnels de la profession."})});
  IDX.epciDep=new Map(D.niveaux.epci.units.map(u=>[u.c,u.p]));
  IDX.depName=new Map(D.niveaux.dep.units.map(u=>[u.c,u.nm]));
  GL=new Map((D.meta.glossaire||[]).map(g=>[g.id,g]));
  if(D.meta.libelles)GL.set("libelles",{terme:"Noms des établissements",definition:D.meta.libelles});
  const gl=D.meta.genere_le||"";document.getElementById("maj").textContent=gl?"Données du "+new Date(gl+"T12:00").toLocaleDateString("fr-FR",{day:"numeric",month:"long",year:"numeric"})+", répertoire RPPS, FINESS et INSEE.":"";
  buildSelects();
}
// ordre des groupes de professions, premier recours, médecins spécialistes, spécialités par groupe, puis le reste dans
// l'ordre des données (version 2, 11 octobre 2026)
function ordreGroupe(g){const sp=D.meta.groupes_specialites||[];
  return g==="Premier recours"?0:g==="Médecins spécialistes, ensemble"?1:sp.includes(g)?2+sp.indexOf(g):50}
function buildSelects(){
  const visibles=D.professions.filter(p=>inFam(p)&&natN(p.id,"all")>0);
  const g=[...new Set(visibles.map(p=>p.groupe))].sort((a,b)=>ordreGroupe(a)-ordreGroupe(b));
  const ps=document.getElementById("prof");ps.innerHTML="";
  for(const gr of g){const og=document.createElement("optgroup");og.label=gr;for(const p of visibles.filter(p=>p.groupe===gr)){const o=document.createElement("option");o.value=p.id;o.textContent=p.libelle;og.appendChild(o)}ps.appendChild(og)}
  if(!visibles.find(p=>p.id===S.prof)){const pref=S.fam===SANTE?"medecin_generaliste":"psychologue";S.prof=(visibles.find(p=>p.id===pref)||visibles[0]||D.professions[0]).id}
  const gt=[...new Set(visibles.filter(p=>natOf(p)!=="perimetre_elargi").map(p=>p.groupe))];
  document.getElementById("grp").innerHTML='<option value="*">Toutes les professions affichées</option>'+gt.map(x=>'<option>'+esc(x)+'</option>').join("");
  if(S.grp!=="*"&&!gt.includes(S.grp))S.grp="*";
  // indicateurs de contexte, ceux de l'INSEE pour tous, les autres selon leur famille
  const cx=ctxVisibles().filter(c=>ctxDispo("dep",c)||ctxDispo("epci",c));
  const grp=[...new Set(cx.map(c=>c.groupe||"Profil de la population"))].map(g=>[g+(cx.some(c=>(c.groupe||"")===g&&!ctxDispo("epci",c))?" (par département)":""),cx.filter(c=>(c.groupe||"Profil de la population")===g)]);
  // listes du nuage, présentes dans Explorer seulement depuis le lot 2 du 29 octobre 2026
  const yv=document.getElementById("yvar"),xv=document.getElementById("xvar");
  if(S.yvar&&!cx.find(c=>c.id===S.yvar))S.yvar="";
  if(yv){yv.innerHTML='<option value="">Axe vertical, densité de la profession choisie</option>'+grp.filter(g=>g[1].length).map(([l,cs])=>'<optgroup label="Axe vertical, '+esc(l)+'">'+cs.map(c=>'<option value="'+c.id+'">'+esc(c.label)+'</option>').join("")+'</optgroup>').join("");
    yv.value=S.yvar||""}
  if(xv)xv.innerHTML=grp.filter(g=>g[1].length).map(([l,cs])=>'<optgroup label="'+esc(l)+'">'+cs.map(c=>'<option value="'+c.id+'">'+esc(c.label)+'</option>').join("")+'</optgroup>').join("");
  if(!cx.find(c=>c.id===S.xvar))S.xvar=cx[0]?.id;
  const nb=visibles.filter(p=>natOf(p)==="profession").length;
  document.getElementById("famNote").textContent=S.fam===SM?"Psychologues, psychothérapeutes, psychiatres et pédopsychiatres, avec les qualifications complémentaires et le périmètre élargi.":S.fam===SANTE?nb+" professions de l’offre de soins générale.":"Toutes les professions, santé mentale et santé.";
}
const natN=(p,m)=>(D.france.n[p]||[0,0,0])[MI[m||S.mode]];
const natD=(p,m)=>natN(p,m)/D.france.pop*1e4;
// Moyenne des territoires d'un niveau, calculée comme eux (somme de leurs effectifs rapportée à leur population).
// C'est la référence de toutes les comparaisons de territoires (décision de Lucas du 5 octobre 2026). natD reste le
// chiffre de la France entière, où chaque personne compte une fois, y compris les activités sans lieu.
const MOY={},MOYLAB={com:"des communes",epci:"des intercommunalités",dep:"des départements",reg:"des régions"};
const NIVLAB={epci:"intercommunalités",dep:"départements",reg:"régions"},UNLAB={epci:"une intercommunalité",dep:"un département",reg:"une région"};
function refD(lv,p,m){m=m||S.mode;const k=lv+"|"+p+"|"+m;if(!(k in MOY)){const L=D.niveaux[lv],a=L.n[p];let n=0,P=0;
  L.units.forEach((u,i)=>{P+=u.pop;if(a)n+=a[m][i]});MOY[k]=P?n/P*1e4:0}return MOY[k]}
function unitN(lv,p,i,m){const a=D.niveaux[lv].n[p];return a?a[m||S.mode][i]:0}
function unitD(lv,p,i,m){const u=D.niveaux[lv].units[i];return u.pop?unitN(lv,p,i,m)/u.pop*1e4:0}
const routeEq=p=>(D.route||[]).find(r=>r.prof===p);
function trajet(lv,p,i){const e=routeEq(p),a=e&&D.niveaux[lv].route?.[e.id];return a&&a[i]?a[i]:null}
// évolution de la densité sur dix ans (séries de la DREES), régions et départements
const evolInfo=p=>(D.evolution||[]).find(e=>e.prof===p);
function evol(lv,p,i){const a=D.niveaux[lv].evolution?.[p];return a&&a[i]?a[i]:null}
const signe=v=>(v>0?"+":"")+f1.format(v*100)+" %";
function att(lv,p,i){const A=D.niveaux[lv].attendu;return A&&A[p]?A[p][i]:null}
function val(lv,p,i){
  if(S.metric==="n")return unitN(lv,p,i);
  if(S.metric==="acces"){const a=D.niveaux[lv].acces?.[p];return a?a[i]:null}
  if(S.metric==="trajet"){const t=trajet(lv,p,i);return t?t[1]:null}
  if(S.metric==="lieux"){const d=D.niveaux[lv].lieux_dist?.[S.lieux];return d?d[i]:null}
  if(S.metric==="evol"){const e=evol(lv,p,i);return e?e[2]:null}
  if(S.metric==="ecart"){const a=att(lv,p,i);return a?unitD(lv,p,i,"all")/a:null}
  return unitD(lv,p,i);
}
const profLab=p=>IDX.prof.get(p)?.libelle||p;
const modeLab={all:"tous modes",lib:"en libéral",sal:"salariés"};
const tip=document.getElementById("tip");
function showTip(ev,html){if(tip.parentNode!==document.body)document.body.appendChild(tip);tip.innerHTML=html;tip.style.opacity=1;
  const w=tip.offsetWidth,h=tip.offsetHeight,W=document.documentElement.clientWidth,H=innerHeight;let x=ev.clientX+14,y=ev.clientY+14;
  if(x+w>W-8)x=ev.clientX-w-14;if(x<8)x=8;if(y+h>H-8)y=ev.clientY-h-14;if(y<8)y=8;tip.style.left=x+"px";tip.style.top=y+"px"}
function hideTip(){document.querySelectorAll(".tip").forEach(t=>t.style.opacity=0)}
// libellé en minuscule sauf les sigles (« CMP pour adultes » reste tel quel)
const minLib=s=>/^[A-ZÉ]{2}/.test(s)?s:s.charAt(0).toLowerCase()+s.slice(1);
// signaux « donnée fragile ici » (9 octobre 2026), symbole ocre marqué « ! » posé sur le territoire, sa couleur ne change
// pas et la limite est écrite sous la figure. Mayotte partout, l'Île-de-France sur les figures du suicide.
const IDF=["75","77","78","91","92","93","94","95"];
const SIG={mayotte:"Mayotte, données incomplètes, densités surestimées d’environ un quart (population de 2017)",suicides:"Île-de-France, décès par suicide nettement sous-déclarés"};
function fragile(lv,c,suicide){if(lv==="reg")return c==="06"?"mayotte":suicide&&c==="11"?"suicides":null;
  let d=c;if(lv==="epci"){const i=IDX.epci.get(c);d=i==null?null:D.niveaux.epci.units[i].p}
  return d==="976"?"mayotte":suicide&&IDF.includes(d)?"suicides":null}
function symboleFragile(g,x,y,k,r){r=r||5;const s=g.append("g").attr("class","fragile").attr("data-x",x).attr("data-y",y)
    .attr("transform","translate("+x+","+y+")").style("cursor","pointer").attr("tabindex",0).attr("role","button").attr("aria-label",SIG[k]);
  // survol ou clic, infobulle avec la limite et sa source, sans sélectionner le territoire dessous
  const bulleSig=ev=>{const L=(D.limites||{})[k];showTip(ev,'<strong>'+esc(SIG[k])+'</strong>'+(L?'<div class="tl">'+esc(L.texte)+'</div><div class="tl">Source, '+esc(L.sources.map(x=>x[0]).join(", "))+'.</div>':""))};
  s.on("mousemove",bulleSig).on("mouseleave",hideTip).on("click",ev=>{ev.stopPropagation();bulleSig(ev)})
   .on("keydown",ev=>{if(ev.key==="Enter"||ev.key===" "){ev.preventDefault();const b=ev.currentTarget.getBoundingClientRect();bulleSig({clientX:b.x+b.width/2,clientY:b.y,pageX:b.x+b.width/2+scrollX,pageY:b.y+scrollY})}});
  s.append("circle").attr("r",r).attr("fill",css("--signal")).attr("stroke",css("--panel")).attr("stroke-width",1).attr("vector-effect","non-scaling-stroke");
  s.append("text").attr("data-typo-libre","").attr("text-anchor","middle").attr("y",r*.55).attr("font-size",r*1.5).attr("font-weight",700).attr("fill",css("--panel")).text("!");return s}
function legendeSignaux(ks){return ks.map(k=>'<span class="sig-leg"><svg width="13" height="13" aria-hidden="true"><circle cx="6.5" cy="6.5" r="6" fill="'+css("--signal")+'"/><text x="6.5" y="10" text-anchor="middle" font-size="9" font-weight="700" fill="'+css("--panel")+'">!</text></svg>'+esc(SIG[k])+'</span>').join("")}
function ligneSignal(lv,c,suicide){const k=fragile(lv,c,suicide);return k?'<div class="tl" style="color:'+css("--signal")+'"><strong>!</strong> '+esc(SIG[k])+'</div>':""}
// symboles au trait des fenêtres d'Explorer (gabarits/figures.js), replier et déplier
const ICONE_FEN=(()=>{const s=d=>'<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="'+d+'" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';return {moins:s("M3 7h8"),plus:s("M3 7h8M7 3v8")}})();
// libellés longs sur plusieurs lignes, jamais coupés, la marge gauche suit la ligne la plus longue
// césures possibles dans les noms de professions longs (trait d'union discret, visible seulement si le mot est coupé)
const coupureMots=t=>t.replace(/(Psycho|psycho|Pédo|pédo|Kinési|kinési|Ortho|ortho|Gynéco|gynéco|Ophtalmo)(?=\p{L})/gu,"$1\u00AD");
// population en clair, « 15,2 millions d'habitants », « 850 000 habitants »
const habitantsTxt=n=>n>=1e6?f1.format(n/1e6)+" million"+(n>=2e6?"s":"")+" d’habitants":fmt.format(Math.round(n/1e3)*1e3)+" habitants";
// source d'un indicateur, liée à la fiche de son jeu de données sur la page « Données sources » du site
function lienFiche(c){if(!c.fiche)return esc(c.source||"");const base=(D.site_dossier&&D.site_dossier!==".")?D.site_dossier+"/":"";
  return'<a href="'+base+'donnees-sources.html#'+c.fiche+'">'+esc(c.source)+'</a>'}
// fond d'une case colorée et couleur du texte qui garde un contraste d'au moins 4,5 (RGAA, critère 3.2)
function luminance(fond){const c=d3.rgb(fond),l=v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)};return .2126*l(c.r)+.7152*l(c.g)+.0722*l(c.b)}
const TEXTE_FONCE="#14161B",TEXTE_CLAIR="#F4F4F7";
function contrasteTexte(fond,texte){const a=luminance(fond),b=luminance(texte);return(Math.max(a,b)+.05)/(Math.min(a,b)+.05)}
function texteSur(fond){return contrasteTexte(fond,TEXTE_FONCE)>=contrasteTexte(fond,TEXTE_CLAIR)?TEXTE_FONCE:TEXTE_CLAIR}
function styleCase(fond,pale){if(!fond)return"background:transparent";let f=pale?d3.interpolateRgb(css("--panel"),fond)(.4):fond;
  // teinte moyenne, le fond est un peu éclairci ou assombri jusqu'à un contraste de 4,5 avec le texte
  for(let k=0;k<14;k++){const t=texteSur(f);if(contrasteTexte(f,t)>=4.5)break;f=d3.interpolateRgb(f,t===TEXTE_FONCE?"#fff":"#000")(.12)}
  return"background:"+f+";color:"+texteSur(f)}
function coupeLib(t,max){const l=[];let c="";for(const mot of String(t).split(" ")){if(c&&(c+" "+mot).length>max){l.push(c);c=mot}else c=c?c+" "+mot:mot}if(c)l.push(c);return l}
// marge gauche pour des libellés de largeur larg (mesurée à leur taille d'écran) dans une figure d'au moins wMin unités dont
// le tracé prend corps unités : le texte est converti selon le rapport entre le dessin et l'écran (normaliserTextes),
// la marge l'est donc aussi
function margeLibelles(svg,larg,wMin,corps){const ecran=svg.node().getBoundingClientRect().width||wMin;let l=Math.max(larg+16,140),w=Math.max(wMin,l+corps);
  for(let i=0;i<3;i++){const k=w/Math.max(ecran,w*.9);l=Math.max(larg*k+16,140);w=Math.max(wMin,l+corps)}return {l,w}}
function largeurLignes(svg,lignes){const t=svg.append("text").attr("x",0).attr("y",-100);t.style("font-size",TYPO[roleTexte(parseFloat(getComputedStyle(t.node()).fontSize)||11)]+"px");let w=0;for(const l of lignes){t.text(l);w=Math.max(w,t.node().getComputedTextLength()||l.length*6.6)}t.remove();return w}
function libelleMulti(sel,x,yc,lignes,dl=15){const t=sel.append("text").attr("x",x).attr("y",yc+4-(lignes.length-1)*dl/2).attr("text-anchor","end");lignes.forEach((l,i)=>t.append("tspan").attr("x",x).attr("dy",i?dl:0).text(l));return t}
function grilleX(svg,x,m,h,n){svg.append("g").attr("class","grille").attr("transform","translate(0,"+(h-m.b)+")").call(d3.axisBottom(x).ticks(n).tickSize(-(h-m.t-m.b)).tickFormat("")).call(g=>{g.select(".domain").remove();g.selectAll("line").attr("stroke",css("--line")).attr("stroke-opacity",.45)})}

// ---------- typologie, une par famille (santé mentale, santé, ensemble), et ACP
const famCle=()=>S.fam===SM?"sm":S.fam===SANTE?"sante":"tout";
// liste de choix soignée, reprise d'une liste du navigateur qui reste la source de l'état (un choix y écrit la valeur
// et déclenche son « change »). Au-delà de quinze options, une recherche en tête et les groupes répartis en colonnes,
// pour ne jamais présenter un mur d'options (remarque de Lucas du 23 octobre 2026, liste des professions de la santé)
function choixListe(sel,cle,apres){if(!sel)return null;
  let box=document.querySelector('.prof-choix[data-pour="'+cle+'"]');
  if(!box){box=document.createElement("div");box.className="prof-choix";box.dataset.pour=cle;
    box.innerHTML='<button type="button" aria-expanded="false" aria-haspopup="true"><span></span><svg width="11" height="7" viewBox="0 0 11 7" aria-hidden="true"><path d="M1 1l4.5 4.5L10 1" fill="none" stroke="currentColor" stroke-width="1.5"/></svg></button><div class="prof-liste" hidden></div>';
    apres.after(box);const b=box.querySelector("button"),l=box.querySelector(".prof-liste");
    const fermer=()=>{l.hidden=true;b.setAttribute("aria-expanded","false")};
    const option=o=>'<button type="button" data-v="'+esc(o.value)+'" aria-current="'+(o.value===sel.value)+'">'+esc(o.textContent)+'</button>';
    b.onclick=()=>{const o=l.hidden;
      // une seule liste ouverte à la fois (remarque de Lucas du 23 octobre 2026, deux listes ouvertes se superposaient)
      if(o)document.querySelectorAll(".prof-liste:not([hidden])").forEach(x=>{if(x!==l){x.hidden=true;x.parentElement.querySelector(":scope > button")?.setAttribute("aria-expanded","false")}});
      if(o){const n=sel.querySelectorAll("option").length,grand=n>15,og=[...sel.children].filter(g=>g.tagName==="OPTGROUP"),deux=grand&&og.length>=4;
        l.classList.toggle("large",grand&&!deux);l.classList.toggle("deux",deux);
        if(deux){menuDeux(sel,l,og,option)}else{
        const groupes=[...sel.children].map(g=>g.tagName==="OPTGROUP"?'<div class="grp"><p>'+esc(g.label)+'</p>'+[...g.children].map(option).join("")+'</div>':'<div class="grp">'+option(g)+'</div>').join("");
        l.innerHTML=(grand?'<input type="search" class="filtre-liste" placeholder="Rechercher" aria-label="Rechercher dans la liste">':'')+'<div class="colonnes">'+groupes+'</div>';
        const f=l.querySelector(".filtre-liste");
        if(f)f.addEventListener("input",()=>{const q=f.value.normalize("NFD").replace(/\p{M}/gu,"").toLowerCase().trim();
          l.querySelectorAll(".grp").forEach(g=>{let k=0;g.querySelectorAll("button").forEach(x=>{const ok=!q||x.textContent.normalize("NFD").replace(/\p{M}/gu,"").toLowerCase().includes(q);x.hidden=!ok;if(ok)k++});g.hidden=!k})})}}
      l.hidden=!o;b.setAttribute("aria-expanded",String(o));
      if(o)(l.querySelector(".filtre-liste")||l.querySelector('[aria-current="true"]')||l.querySelector("button"))?.focus()};
    l.onclick=e=>{const t=e.target.closest(".theme");if(t){montrerTheme(l,t.dataset.g);return}
      const x=e.target.closest("[data-v]");if(!x)return;sel.value=x.dataset.v;b.querySelector("span").textContent=sel.selectedOptions[0]?.textContent||"";sel.dispatchEvent(new Event("change"));fermer();b.focus()};
    document.addEventListener("keydown",e=>{if(e.key==="Escape"&&!l.hidden){fermer();b.focus()}});
    // fermeture au clic hors de la liste, en phase de capture pour qu'aucun autre élément ne l'arrête
    document.addEventListener("pointerdown",e=>{if(!l.hidden&&!e.target.closest('.prof-choix[data-pour="'+cle+'"]'))fermer()},true)}
  box.querySelector("button span").textContent=sel.selectedOptions[0]?.textContent||"";
  return box}
// menu en deux temps (remarque de Lucas du 23 octobre 2026, cent dix-sept indicateurs dans une seule liste étaient
// difficiles à parcourir ; Impeccable, peu de choix à la fois, le reste à la demande) : une douzaine de thèmes avec
// leur nombre d'indicateurs, les indicateurs du thème montré, une recherche qui parcourt tous les thèmes
const sansAccent=t=>t.normalize("NFD").replace(/\p{M}/gu,"").toLowerCase();
function montrerTheme(l,g){l.querySelectorAll(".theme").forEach(t=>t.setAttribute("aria-pressed",String(t.dataset.g===String(g))));
  l.querySelectorAll(".volet-choix .grp").forEach(x=>{x.hidden=x.dataset.g!==String(g);x.querySelectorAll("button").forEach(b=>b.hidden=false)});
  const f=l.querySelector(".filtre-liste");if(f)f.value="";l.classList.remove("cherche")}
function menuDeux(sel,l,og,option){
  const nett=t=>t.replace(/^Axe vertical, /,""),seuls=[...sel.children].filter(g=>g.tagName==="OPTION");
  const cur=sel.selectedOptions[0],actif=Math.max(0,og.indexOf(cur&&cur.parentElement));
  l.innerHTML='<input type="search" class="filtre-liste" placeholder="Rechercher un indicateur" aria-label="Rechercher dans tous les thèmes">'
    +'<div class="volet-themes">'+(seuls.length?'<div class="seuls">'+seuls.map(option).join("")+'</div>':'')
    +og.map((g,i)=>'<button type="button" class="theme" data-g="'+i+'" aria-pressed="'+(i===actif)+'"><span>'+esc(nett(g.label))+'</span><span class="nb">'+g.children.length+'</span></button>').join("")+'</div>'
    +'<div class="volet-choix">'+og.map((g,i)=>'<div class="grp" data-g="'+i+'"'+(i===actif?'':' hidden')+'><p>'+esc(nett(g.label))+'</p>'+[...g.children].map(option).join("")+'</div>').join("")+'</div>';
  // survoler un thème le montre, comme un menu ; le clic fait de même au clavier et au toucher
  l.querySelectorAll(".theme").forEach(t=>t.addEventListener("mouseenter",()=>{if(!l.classList.contains("cherche"))montrerTheme(l,t.dataset.g)}));
  const f=l.querySelector(".filtre-liste");
  f.addEventListener("input",()=>{const q=sansAccent(f.value.trim());
    if(!q){const a=l.querySelector('.theme[aria-pressed="true"]');montrerTheme(l,a?a.dataset.g:0);return}
    l.classList.add("cherche");
    l.querySelectorAll(".volet-choix .grp").forEach(g=>{let k=0;g.querySelectorAll("button").forEach(x=>{const ok=sansAccent(x.textContent).includes(q);x.hidden=!ok;if(ok)k++});g.hidden=!k});
    l.querySelectorAll(".theme").forEach(t=>{const g=l.querySelector('.volet-choix .grp[data-g="'+t.dataset.g+'"]');t.classList.toggle("vide",!g||g.hidden)})})}
addEventListener("scroll",hideTip,{passive:true});
// barre de rappel des réglages (remarque de Lucas du 23 octobre 2026 : utile que les réglages suivent la lecture, mais
// la barre entière prenait de la place, et la replier en cours de défilement faisait sauter la page). Les réglages
// restent en tête de page ; une fois dépassés, une fine barre flottante apparaît sous l'en-tête, par un fondu, sans rien
// déplacer dans la page : la profession (même liste), le rappel des autres choix et « Réglages », qui ouvre tous les
// réglages dans une fenêtre posée au-dessus de la lecture
function hautFixe(){const n=document.querySelector("nav.site"),r=document.getElementById("rappelReglages");
  return (n?n.getBoundingClientRect().bottom:0)+(r&&r.classList.contains("vu")?r.offsetHeight+8:0)}
// ---------- corrélation de rang de Spearman (nuage d'Explorer, corrélations par groupe de l'atlas)
function spearman(x,y){
  const idx=x.map((v,i)=>i).filter(i=>x[i]!=null&&y[i]!=null&&isFinite(x[i])&&isFinite(y[i]));
  const rk=a=>{const o=idx.map(i=>a[i]).map((v,j)=>[v,j]).sort((p,q)=>p[0]-q[0]);const r=new Array(o.length);let j=0;while(j<o.length){let k=j;while(k+1<o.length&&o[k+1][0]===o[j][0])k++;const m=(j+k)/2+1;for(let t=j;t<=k;t++)r[o[t][1]]=m;j=k+1}return r};
  const rx=rk(x),ry=rk(y),n=rx.length;if(n<5)return{rho:NaN,n};
  const mx=d3.mean(rx),my=d3.mean(ry);let a=0,b=0,c=0;for(let i=0;i<n;i++){a+=(rx[i]-mx)*(ry[i]-my);b+=(rx[i]-mx)**2;c+=(ry[i]-my)**2}
  return{rho:a/Math.sqrt(b*c),n};
}
