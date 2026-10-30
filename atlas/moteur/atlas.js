// Moteur de l'atlas, module « atlas » (la page elle-même). Onglets et sommaires, carte principale (drawMap), fiche d'un
// territoire, tableau par profession, sources et « Comprendre », réglages et barre de rappel, orchestration (render,
// syncBar) et branchement des événements, lecture des réglages dans l'adresse, premier rendu.

// ---------- sommaire en tête d'un onglet, une ligne par encadré avec son titre et ce qu'il permet (RESUMES),
// tenu à jour à chaque nouveau choix. Un clic mène à l'encadré, qui reste entier (chantier d'organisation, 22 octobre 2026)
// ce que permet chaque analyse, sans en citer un résultat particulier, chaque encadré étant un outil à régler
// (remarque de Lucas du 22 octobre 2026, la phrase de résultat n'était qu'un exemple parmi les croisements possibles)
const RESUMES={
  "Corrélations par groupe d’indicateurs":"Voir d’un coup d’œil quels indicateurs vont avec la présence de chaque profession, groupe par groupe.",
  "Besoins, recours et conditions de vie, croisés entre eux":"Comparer entre eux, par département, les indicateurs de besoin, de recours aux soins et de conditions de vie.",
  "À autres indicateurs égaux":"Mesurer ce qui reste du lien entre deux indicateurs quand les autres sont tenus égaux (régression multiple).",
  "Addictologie":"L’offre en addictologie, le recours aux soins et les consommations d’alcool et de tabac, réunis au même endroit.",
  "Offre et indicateur sur une même carte":"Situer sur la carte les départements où l’offre et un indicateur sont ensemble hauts, bas ou opposés.",
  "Le lien avec le niveau de vie, d’une région à l’autre":"Voir comment le lien entre le niveau de vie et la densité d’une profession change d’une région à l’autre.",
  "L’effet ville retiré":"Séparer les liens qui tiennent à la taille des villes de ceux qui demeurent à densité de population égale.",
  "Accès aux structures de soins":"Connaître, pour chaque type de structure, à quelle distance les habitants vivent de la plus proche."};
// la page d'un onglet rangée une fois par question, pour que chaque question réunisse des analyses voisines ; un bloc
// suit la question de son premier encadré, les cadres des corrélations suivent le bloc qui les précède
function rangerOnglet(onglet,sec){if(sec.dataset.range||!QUESTIONS[onglet])return;sec.dataset.range="1";
  const grp=QUESTIONS[onglet],grpDe=t=>{const k=grp.findIndex(([q,ts])=>ts.includes(t));return k<0?grp.length:k};
  const blocs=[...sec.children].filter(c=>!c.classList.contains("sommaire-onglet"));let prec=0;
  const cles=blocs.map(b=>{const p=b.matches(".panel")?b:b.querySelector(".panel");const k=b.id==="hmCadres"||!p?prec:grpDe(titreEncadre(p));prec=k;return k});
  blocs.map((b,i)=>[b,cles[i],i]).sort((a,b)=>a[1]-b[1]||a[2]-b[2]).forEach(([b])=>sec.appendChild(b))}
function sommaireOnglet(onglet){
  const sec=document.querySelector('section[data-p="'+onglet+'"]');if(!sec)return;rangerOnglet(onglet,sec);
  let som=sec.querySelector(":scope > .sommaire-onglet");
  if(!som){som=document.createElement("nav");som.className="sommaire-onglet";som.setAttribute("aria-label","Analyses de cet onglet");sec.prepend(som);
    som.addEventListener("click",e=>{const a=e.target.closest("a[data-cible]");if(!a)return;e.preventDefault();const p=document.getElementById(a.dataset.cible);if(!p)return;
      if(p.classList.contains("replie"))p.querySelector("button.repli")?.click();
      const haut=(document.querySelector("nav.site")?.offsetHeight||0)+(document.getElementById("rappelReglages")?.offsetHeight||0)+24;window.scrollTo({top:p.getBoundingClientRect().top+scrollY-haut,behavior:"smooth"});const h=p.querySelector("h2 button, h2");h?.focus?.({preventScroll:true})})}
  const pans=[...sec.querySelectorAll(".panel")].filter(p=>!p.parentElement.closest(".panel")&&!p.closest("[hidden]")&&titreEncadre(p));
  const items=[];
  pans.forEach((p,i)=>{if(!p.id)p.id="enc-"+onglet+"-"+i;
    // les cadres d'un même groupe (corrélations par groupe d'indicateurs) deviennent des liens de l'entrée qui les précède
    if(p.parentElement.id==="hmCadres"&&items.length){items[items.length-1].sous.push(p);return}
    items.push({p,sous:[]})});
  // marge de lecture (choix de Lucas du 23 octobre 2026) : les analyses rangées par question, titres seuls, la phrase
  // de RESUMES en infobulle ; la marge reste visible pendant la lecture et marque l'analyse en cours
  const lien=p=>{const t=titreEncadre(p),r=RESUMES[t];return '<li><a href="#'+p.id+'" data-cible="'+p.id+'"'+(r?' title="'+esc(r)+'"':'')+'>'+esc(t)+'</a></li>'};
  // la marge suit l'ordre de la page (demande de Lucas du 23 octobre 2026) : les questions dans l'ordre où leur
  // première analyse paraît, les analyses dans l'ordre de la page ; la page a été rangée par question (rangerOnglet)
  const grp=QUESTIONS[onglet]||[],grpDe=p=>{const k=grp.findIndex(([q,ts])=>ts.includes(titreEncadre(p)));return k<0?grp.length:k},groupes=[];
  items.forEach(({p})=>{const k=grpDe(p);let g=groupes.find(x=>x.k===k);if(!g){g={k,ps:[]};groupes.push(g)}g.ps.push(p)});
  let h=groupes.map(g=>'<div class="som-groupe">'+(grp.length?'<p class="som-question">'+esc(g.k<grp.length?grp[g.k][0]:"Autres analyses")+'</p>':'')+'<ul>'+g.ps.map(lien).join("")+'</ul></div>').join("");
  som.innerHTML=h;sec.classList.add("a-marge");suivreMarge()}
// questions de chaque onglet, dans l'ordre de lecture ; un encadré absent de la liste va sous « Autres analyses »
const QUESTIONS={
  croisements:[["La densité et le profil des habitants",["Corrélations par groupe d’indicateurs","L’effet ville retiré"]],
    ["Cartes croisées, par territoire",["Offre et indicateur sur une même carte","Le lien avec le niveau de vie, d’une région à l’autre"]],
    ["Les indicateurs entre eux",["Besoins, recours et conditions de vie, croisés entre eux","À autres indicateurs égaux"]],
    ["Offre, recours et consommations",["Addictologie"]]],
};
// l'analyse en cours est celle dont le haut a passé la barre des réglages ; la marge se place sous cette barre
let MARGE_ECOUTE=false;
function suivreMarge(){
  const maj=()=>{const sec=document.querySelector("section.a-marge:not(.hidden)");if(!sec)return;
    const haut=hautFixe();sec.style.setProperty("--haut-marge",Math.max(0,haut)+16+"px");
    // l'analyse en cours est la plus basse de la page dont le haut a passé la barre, quel que soit son rang dans la
    // marge (rangée par question, pas dans l'ordre de la page)
    const liens=[...sec.querySelectorAll(".sommaire-onglet a[data-cible]")],pos=liens.map(a=>{const p=document.getElementById(a.dataset.cible);return p&&p.offsetParent?p.getBoundingClientRect().top:Infinity});
    const fin=innerHeight+scrollY>=document.documentElement.scrollHeight-4;let cur=null,best=-Infinity,premier=null,haut0=Infinity;
    pos.forEach((t,k)=>{if(t<haut0){haut0=t;premier=liens[k]}if((fin||t<=haut+80)&&t>best&&t!==Infinity){best=t;cur=liens[k]}});cur=cur||premier;
    liens.forEach(a=>{if(a===cur)a.setAttribute("aria-current","location");else a.removeAttribute("aria-current")})};
  maj();if(MARGE_ECOUTE)return;MARGE_ECOUTE=true;let f=0;
  const planifier=()=>{if(!f)f=requestAnimationFrame(()=>{f=0;maj()})};addEventListener("scroll",planifier,{passive:true});addEventListener("resize",planifier)}
let M=null,TM=null;

function drawMap(){
  if(!M)M=mapInit("map");
  const lv=S.level,p=S.prof,feats=geom[lv];
  const vals=D.niveaux[lv].units.map((u,i)=>u.pop?val(lv,p,i):null);
  let color,legend;
  if(S.metric==="zones"){
    const Z=D.niveaux[lv].zones?.[p]||[],cz={desert:css("--d0"),concentration:css("--r5"),isole_haut:css("--r2"),isole_bas:css("--d2"),non_significatif:css("--d3")};
    for(let i=0;i<vals.length;i++)vals[i]=Z[i]??null;
    color=v=>v==null?css("--nodata"):cz[v];
    legend='<span>Zones</span>'+[["desert","Zone peu dotée"],["concentration","Zone de concentration"],["isole_bas","Peu doté entouré de mieux dotés"],["isole_haut","Bien doté entouré de moins dotés"],["non_significatif","Pas de zone marquée"]].map(([k,l])=>'<span style="display:inline-flex;align-items:center;gap:4px"><span style="width:12px;height:12px;background:'+cz[k]+'"></span>'+l+'</span>').join("");
  }else if(S.metric==="ecart"){
    const dv=DIV(),dom=[.5,.7,.9,1.1,1.4,2];
    const sc=d3.scaleThreshold().domain(dom).range(dv);color=v=>v==null?css("--nodata"):sc(v);
    legend='<span>Effectif observé rapporté à l’attendu</span><div><div class="sw">'+dv.map(c=>'<span style="background:'+c+'"></span>').join("")+'</div><div class="ticks"><span></span>'+dom.map(b=>'<span>'+f1.format(b)+'</span>').join("")+'</div></div>';
  }else if(S.metric==="evol"){
    // cuivre pour une baisse, bleu pour une hausse, gris autour de zéro
    const dv=DIV(),dom=[-.2,-.1,-.03,.03,.1,.2],e=evolInfo(p);
    const sc=d3.scaleThreshold().domain(dom).range(dv);color=v=>v==null?css("--nodata"):sc(v);
    legend='<span>Évolution de la densité de '+e.debut+' à '+e.fin+' (France '+signe(e.fr[2])+')</span><div><div class="sw">'+dv.map(c=>'<span style="background:'+c+'"></span>').join("")+'</div><div class="ticks"><span></span>'+dom.map(b=>'<span>'+(b>0?"+":"")+Math.round(b*100)+'</span>').join("")+'</div></div><span>En %, cuivre en baisse, bleu en hausse.</span>';
  }else if(S.metric==="lieux"){
    // distance médiane des habitants à la structure la plus proche du type choisi, couleur forte pour une structure proche
    const pos=vals.filter(v=>v!=null).sort(d3.ascending),r=RAMP().slice().reverse(),t=LX.types.find(x=>x.id===S.lieux);
    const br=[...new Set(d3.range(1,6).map(i=>d3.quantile(pos,i/6)).filter(x=>x!=null).map(b=>Math.round(b*10)/10))];
    const sc=d3.scaleThreshold().domain(br).range(r.slice(0,br.length+1));
    color=v=>v==null?css("--nodata"):sc(v);
    legend='<span>Distance médiane des habitants à la structure la plus proche, '+esc(minLib(t.lib))+', en km à vol d’oiseau</span><div><div class="sw">'+sc.range().map(c=>'<span style="background:'+c+'"></span>').join("")+'</div><div class="ticks"><span></span>'+br.map(b=>'<span>'+f1.format(b)+'</span>').join("")+'</div></div>';
  }else if(S.metric==="trajet"){
    // couleur forte pour un trajet court, comme pour une offre abondante sur les autres cartes
    const pos=vals.filter(v=>v!=null).sort(d3.ascending),r=RAMP().slice().reverse(),e=routeEq(p);
    const br=[...new Set(d3.range(1,6).map(i=>d3.quantile(pos,i/6)).filter(x=>x!=null).map(b=>Math.round(b)))];
    const sc=d3.scaleThreshold().domain(br).range(r.slice(0,br.length+1));
    color=v=>v==null?css("--nodata"):sc(v);
    legend='<span>Durée médiane en voiture jusqu’au '+esc((e?.lib||"").toLowerCase())+' le plus proche, en minutes</span><div><div class="sw">'+sc.range().map(c=>'<span style="background:'+c+'"></span>').join("")+'</div><div class="ticks"><span></span>'+br.map(b=>'<span>'+fmt.format(b)+'</span>').join("")+'</div></div><span>Couleur forte, trajet court.</span>';
  }else{
    const pos=vals.filter(v=>v>0).sort(d3.ascending),r=RAMP();
    const dec=S.metric==="dens"||S.metric==="acces";
    let br=[...new Set(d3.range(1,6).map(i=>d3.quantile(pos,i/6)).filter(x=>x!=null).map(b=>dec?Math.round(b*10)/10:Math.round(b)))];
    const sc=d3.scaleThreshold().domain(br).range(r.slice(6-br.length-1));
    color=v=>v==null?css("--nodata"):(v===0?r[0]:sc(v));
    legend=pos.length?'<span>'+(S.metric==="dens"?"Pour 10 000 habitants":S.metric==="acces"?"Accessibilité, pour 10 000 habitants":"Effectif")+'</span><div><div class="sw">'+sc.range().map(c=>'<span style="background:'+c+'"></span>').join("")+'</div><div class="ticks"><span></span>'+br.map(b=>'<span>'+(dec?f1.format(b):fmt.format(b))+'</span>').join("")+'</div></div>':'<span>Aucun professionnel pour ces filtres.</span>';
  }
  const ix=IDX[lv],box=document.getElementById("mapbox");
  const tuiles=S.vue==="tuiles"&&lv==="dep"&&D.tuiles;
  document.querySelector('#mapbox .zoombar').hidden=!!tuiles;
  M.gi.style("display",tuiles?"none":null);
  if(tuiles){
    // un carré de même taille par département, placé au plus près de sa position réelle (comme dans les rapports)
    M.tuiles=true;[M.g,M.gd,M.gdom,M.gddom].forEach(g=>g.selectAll("path").remove());M.zoomable.attr("transform",null);M.svg.call(M.zoom.transform,d3.zoomIdentity);
    const pos=Object.entries(D.tuiles),nc=d3.max(pos,d=>d[1][0])+1,nl=d3.max(pos,d=>d[1][1])+1,c=Math.min((W-40)/nc,(H-40)/nl),x0=(W-nc*c)/2,y0=(H-nl*c)/2;
    const lum=h=>{const m=d3.color(h);if(!m)return 1;const {r,g,b}=m.rgb();return(.299*r+.587*g+.114*b)/255};
    const gs=M.gt.selectAll("g.t").data(pos.filter(([k])=>ix.has(k)),d=>d[0]).join(en=>{const g=en.append("g").attr("class","t");g.append("rect").attr("class","t");g.append("text").attr("class","tc").attr("text-anchor","middle");return g});
    gs.attr("transform",([k,[x,y]])=>"translate("+(x0+x*c)+","+(y0+y*c)+")");
    gs.select("rect").attr("width",c-4).attr("height",c-4).attr("rx",4)
      .attr("fill",([k])=>color(vals[ix.get(k)]))
      .classed("sel",([k])=>S.sel&&S.sel.lv==="dep"&&S.sel.c===k)
      .attr("tabindex",0).attr("role","button").attr("aria-label",([k])=>D.niveaux.dep.units[ix.get(k)].nm)
      .on("mousemove",(ev,[k])=>showTip(ev,bulle(lv,ix.get(k),p))).on("mouseleave",hideTip)
      .on("click",(ev,[k])=>{S.sel=S.sel&&S.sel.lv==="dep"&&S.sel.c===k?null:{lv:"dep",c:k};render()})
      .on("keydown",(ev,[k])=>{if(ev.key==="Enter"||ev.key===" "){ev.preventDefault();S.sel=S.sel&&S.sel.c===k?null:{lv:"dep",c:k};render()}});
    gs.select("text").attr("x",(c-4)/2).attr("y",(c-4)/2+5).text(([k])=>k).attr("fill",([k])=>lum(color(vals[ix.get(k)]))>.55?"#1F2430":"#FFFFFF");
    gs.selectAll("g.fragile").remove();gs.filter(([k])=>fragile("dep",k)).each(function([k]){symboleFragile(d3.select(this),c-11,7,fragile("dep",k),4.5)});
    if(gs.filter(([k])=>fragile("dep",k)).size())legend+='<div class="legende-signaux">'+legendeSignaux(["mayotte"])+'</div>';
    legend+=legendeHospitaliere(p,"dep");
    M.gt.selectAll("text.om").data([0]).join("text").attr("class","om").attr("x",x0).attr("y",y0+(nl-1)*c-8).text("Outre-mer");
    document.getElementById("legend").innerHTML=legend;
    document.getElementById("mapLimite").innerHTML=(S.metric==="trajet"?limiteHtml(["route"]):S.metric==="evol"?limiteHtml(["evol:"]):limiteHtml(["prof:"+p]))+limiteHtml(["mayotte"]);
    return;
  }
  M.gt.selectAll("*").remove();M.tuiles=false;
  joinUnites(M,lv,feats)
    .attr("fill",f=>{const i=ix.get(keyOf(lv,f));return i==null?css("--nodata"):color(vals[i])})
    .classed("sel",f=>S.sel&&S.sel.lv===lv&&S.sel.c===keyOf(lv,f))
    .on("mouseenter",function(){const h=this.parentNode===M.g.node()?M.survol:M.survolDom;h.attr("d",this.getAttribute("d")).style("display",null)})
    .on("mousemove",(ev,f)=>{const i=ix.get(keyOf(lv,f));if(i==null)return;showTip(ev,bulle(lv,i,p))})
    .on("mouseleave",()=>{M.survol.style("display","none");M.survolDom.style("display","none");hideTip()})
    .on("click",(ev,f)=>{const c=keyOf(lv,f);S.sel=S.sel&&S.sel.lv===lv&&S.sel.c===c?null:{lv,c};render()});
  M.g.selectAll("path.sel").raise();M.gdom.selectAll("path.sel").raise();
  bordures(M,lv==="epci"?geom.dep:[]);
  // territoires sans psychiatre déclaré qui accueillent un CMP de FINESS, signalés dans l'infobulle et la fiche (plus
  // de ronds sur la carte, trop nombreux, décision de Lucas du 10 octobre 2026), compte gardé pour la limite écrite
  M.svg.selectAll("circle.cmp").remove();
  const psyBulle=S.fam!==SANTE?PSY_CMP.filter(x=>IDX.prof.has(x)):[];
  const sigs=signauxCarte(M,lv,false);
  if(sigs.length)legend+='<div class="legende-signaux">'+legendeSignaux(sigs)+'</div>';
  legend+=legendeHospitaliere(p,lv);
  legend+=dessinerLieux(M);
  document.getElementById("legend").innerHTML=legend;
  document.getElementById("mapLimite").innerHTML=(S.metric==="trajet"?limiteHtml(["route"]):S.metric==="evol"?limiteHtml(["evol:"]):limiteHtml(["prof:"+p,...psyBulle.map(x=>"prof:"+x)]))+(sigs.length?limiteHtml(sigs):"")+(S.lieux?limiteHtml(["lieux","dist_"+S.lieux]):"");
}
document.getElementById("lieuxType").addEventListener("change",e=>{S.lieux=e.target.value;LIEU_CHOISI=null;if(!S.lieux&&S.metric==="lieux")S.metric="dens";render()});

// infobulle de la carte, le territoire et toutes les professions principales de la famille affichée
const BULLE_SM=["psychiatre","pedopsychiatre","psychologue","psychotherapeute"],BULLE_SANTE=["medecin_generaliste","infirmier","masseur_kinesitherapeute","pediatre","orthophoniste","sage_femme","chirurgien_dentiste","pharmacien"];
function bulle(lv,i,p){const u=D.niveaux[lv].units[i];
  let ids=(S.fam===SM?BULLE_SM:S.fam===SANTE?BULLE_SANTE:[...BULLE_SM,...BULLE_SANTE.slice(0,4)]).filter(x=>IDX.prof.has(x));
  if(!ids.includes(p))ids=[p,...ids];
  const par=lv==="epci"?(IDX.depName.get(u.p)||u.p):lv==="dep"?u.p:"Région";
  let h='<strong>'+esc(u.nm)+'</strong><div class="tl">'+esc(par)+', '+fmt.format(u.pop)+' habitants. Écart à la moyenne '+MOYLAB[lv]+'.</div>'+ligneSignal(lv,u.c)+'<table><tr><th></th><th>Effectif</th><th style="white-space:nowrap">Pour 10&nbsp;000</th><th>Écart à la moyenne</th></tr>';
  for(const q of ids){const n=unitN(lv,q,i),d=unitD(lv,q,i),r=refD(lv,q);h+='<tr'+(q===p?' class="on"':'')+'><td>'+esc(profLab(q))+'</td><td>'+fmt.format(n)+'</td><td>'+f1.format(d)+'</td><td>'+(n===0?'aucun':Math.abs(d/r-1)<.05?'autant':esc(fois(d,r)))+'</td></tr>'}
  h+='</table>';
  // un 0 n'est jamais laissé seul. Pour la profession choisie, et pour les psychiatres et les pédopsychiatres dès
  // qu'ils figurent dans l'infobulle, une précision dit ce que ce 0 peut cacher (CMP de FINESS où des psychiatres
  // peuvent consulter, psychiatres qualifiés pour l'enfant, professionnel le plus proche dans un territoire voisin)
  const cmI=D.niveaux[lv].cmp?.[i]||0,limZero=[],zeros=[];
  for(const q of [...new Set([p,...ids.filter(x=>PSY_CMP.includes(x))])]){if(unitN(lv,q,i)!==0)continue;
    const morceaux=[];
    if(q==="pedopsychiatre"&&IDX.prof.has("q_psychiatrie_enfant")){const k=unitN(lv,"q_psychiatrie_enfant",i);
      if(k>0)morceaux.push(fmt.format(k)+' psychiatre'+(k>1?'s':'')+' qualifié'+(k>1?'s':'')+' pour l’enfant et l’adolescent')}
    if(q==="psychiatre"&&cmI&&unitN(lv,q,i,"all")===0)morceaux.push(cmI+' centre'+(cmI>1?'s':'')+' médico-psychologique'+(cmI>1?'s':'')+' (CMP) recensé'+(cmI>1?'s':'')+' par FINESS et le ROR, où des psychiatres peuvent consulter');
    if(q==="pedopsychiatre"&&unitN(lv,q,i,"all")===0){const e=lieuxEnfants(lv,i);if(e)morceaux.push(e)}
    zeros.push({q,morceaux});if(cleLimite("prof:"+q))limZero.push(q)}
  // professions à 0 pour la même raison réunies en une phrase (« aucun psychiatre ni pédopsychiatre »)
  for(const cle of [...new Set(zeros.map(z=>z.morceaux.join("|")))]){const g=zeros.filter(z=>z.morceaux.join("|")===cle),q0=g[0].q,m=g[0].morceaux;
    const labs=g.map(z=>esc(profLab(z.q).toLowerCase())).join(" ni "),fem=g.every(z=>FEM.has(z.q));
    h+='<div class="tl">'+(fem?"Aucune ":"Aucun ")+labs+' déclaré'+(fem?"e":"")+(m.length
      ?(g.length===1&&q0==="pedopsychiatre"?' comme tel':'')+', mais '+m.join(', et ')+'.'
      :' ici. Cela ne veut pas dire que les habitants n’y ont pas accès, le plus proche peut exercer dans un territoire voisin.')+'</div>'}
  if(limZero.length)h+='<div class="tl"><em>Voir « À savoir » sous la carte, sur ce que '+(limZero.length>1?'ces chiffres peuvent':'ce chiffre peut')+' cacher.</em></div>';
  const a=att(lv,p,i);if(a&&S.mode==="all")h+='<div class="tl">'+esc(profLab(p))+', d’après le profil de la population on en attendrait '+f1.format(a)+' pour 10 000 hab.</div>';
  // distance vide, aucune structure de ce type sur le territoire (la Corse et chaque département d'outre-mer comptés à
  // part, jamais par-dessus la mer, note du 28 octobre 2026)
  if(S.metric==="lieux"&&S.lieux){const dl=D.niveaux[lv].lieux_dist?.[S.lieux]?.[i],tl=LX?.types.find(t=>t.id===S.lieux);
    // distance retirée là où les bases inscrivent moins de la moitié des structures que la SAE déclare (audit du 30
    // octobre 2026), la précision du territoire le dit
    const km=cleLimite("dist_"+S.lieux),manque=km&&D.limites[km].territoires?.[lv==="reg"?"reg:"+u.c:u.c];
    h+='<div class="tl">'+esc(tl?tl.lib:"Structure")+', '+(manque?'distance non publiée. '+esc(manque):dl==null?'aucune structure de ce type sur ce territoire, la distance n’est pas cherchée par-dessus la mer.':'la moitié des habitants à moins de '+f1.format(dl)+' km à vol d’oiseau.')+'</div>'}
  if(S.metric==="acces"&&D.niveaux[lv].distance?.[p]?.[i]==null&&D.niveaux[lv].distance?.[p])h+='<div class="tl">Aucun de ces professionnels sur ce territoire, la distance n’est pas cherchée par-dessus la mer.</div>';
  if(S.metric==="acces"&&D.niveaux[lv].distance?.[p]?.[i]!=null)h+='<div class="tl">Distance moyenne au plus proche '+f1.format(D.niveaux[lv].distance[p][i])+' km, accessibilité '+f1.format(D.niveaux[lv].acces[p][i])+' pour 10 000 hab.</div>';
  const ev=evol(lv,p,i),ei=evolInfo(p);if(ev)h+='<div class="tl">'+esc(ei.lib)+', évolution de la densité de '+ei.debut+' à '+ei.fin+' selon la DREES, '+signe(ev[2])+' (France '+signe(ei.fr[2])+').</div>';
  const t=trajet(lv,p,i),e=routeEq(p);if(t)h+='<div class="tl">'+esc(e.lib)+' le plus proche, '+(t[1]!=null?f1.format(t[1])+' min en voiture pour la moitié des habitants, ':'')+(t[0]>0&&t[0]<.005?'moins de 1':fmt.format(Math.round(t[0]*100)))+' % des habitants à plus de 20 minutes.</div>';
  return h}
function natCard(){
  const p=S.prof,ineg=(D.inegalites||[]).find(r=>r.niv===S.level&&r.mode===S.mode&&r.prof===p);
  const sp=(D.spatial||[]).find(r=>r.niveau===S.level&&r.prof===p);
  const pr=IDX.prof.get(p)||{},lab=profLab(p),niv=NIVLAB[S.level];
  let ph="";
  if(natOf(pr)==="perimetre_elargi")ph=fmt.format(natN(p))+" "+pluriel(lab)+" en France, salariés d’un établissement psychiatrique ou médico-psychologique. Ce chiffre se lit à côté de celui de la profession et ne s’y ajoute pas.";
  else if(natD(p)>0){ph=cap(un(p))+" "+lab.toLowerCase()+" pour "+unPour(natD(p))+" habitants en France.";
    if(ineg)ph+=" Répartition "+phraseGini(ineg.gini)+" entre "+niv+". "+cap(f1.format(ineg.zero*100))+" % de la population vit dans "+UNLAB[S.level]+" sans "+lab.toLowerCase()+".";
    if(natOf(pr)==="qualification")ph+=" Ces médecins sont aussi comptés dans leur spécialité, les chiffres ne s’additionnent pas.";
    if(natOf(pr)==="ensemble")ph+=" Chaque médecin spécialiste y est compté une fois, hors généralistes. Ce chiffre réunit les spécialités et ne s’y ajoute pas."}
  let h='<h2>'+esc(lab)+' <button class="how" data-how="densite,gini,sans_pro'+(natOf(pr)==="qualification"?",qualification":natOf(pr)==="perimetre_elargi"?",elargi":"")+'">Comment lire</button></h2><div class="howtxt hidden"></div><div class="muted small">France entière, '+modeLab[S.mode]+'</div><div class="big">'+f1.format(natD(p))+'</div><div class="muted small">pour 10 000 habitants, soit '+fmt.format(natN(p))+' professionnels</div><p class="phrase">'+esc(ph)+'</p><dl class="f">';
  if(ineg)h+='<dt>Concentration (Gini, '+NIVLAB[S.level]+')</dt><dd>'+f2.format(ineg.gini)+'</dd><dt>Population sans aucun professionnel</dt><dd>'+f1.format(ineg.zero*100)+' %</dd>';
  if(sp&&sp.moran_I!=null)h+='<dt>Ressemblance entre voisins (Moran)</dt><dd>'+f2.format(sp.moran_I)+'</dd>';
  const L=D.niveaux[S.level],ds=L.units.map((u,i)=>({u,d:unitD(S.level,p,i)})).filter(x=>x.u.pop>20000||S.level!=="epci").sort((a,b)=>a.d-b.d);
  h+='</dl><details class="plus" style="margin-top:12px"><summary>Les territoires les moins et les mieux dotés</summary><h3>Les moins dotés'+(S.level==="epci"?" (plus de 20 000 hab.)":"")+'</h3><dl class="f">'+ds.slice(0,4).map(x=>'<dt>'+esc(x.u.nm)+'</dt><dd>'+f1.format(x.d)+'</dd>').join("")+'</dl><h3>Les mieux dotés</h3><dl class="f">'+ds.slice(-4).reverse().map(x=>'<dt>'+esc(x.u.nm)+'</dt><dd>'+f1.format(x.d)+'</dd>').join("")+'</dl><p class="small" style="margin:6px 0 0">Les petits territoires fluctuent beaucoup d’une année à l’autre.</p></details>';
  h+=limiteHtml(["prof:"+p]);
  document.getElementById("natCard").innerHTML=h;
}
function selCard(){
  const el=document.getElementById("selCard"),br=document.getElementById("selBrief");
  br.classList.toggle("choisi",!!(S.sel&&S.sel.lv===S.level));
  if(!S.sel||S.sel.lv!==S.level){el.classList.add("hidden");el.innerHTML="";br.innerHTML='<h2>Profil d’un territoire</h2><p class="muted small" style="margin:0">Cliquez sur un territoire de la carte. Son profil s’affiche sous la carte, comparé à la moyenne des territoires du même niveau. Un second clic le désélectionne.</p>';return}
  el.classList.remove("hidden");
  const lv=S.sel.lv,i=IDX[lv].get(S.sel.c),u=D.niveaux[lv].units[i];
  const parent=lv==="epci"?(IDX.depName.get(u.p)||u.p):lv==="reg"?"Région":u.p;
  let h='<div class="selhead"><div class="sel-titre"><h2>'+esc(u.nm)+' <button class="how" data-how="indice100,attendu,entonnoir">Comment lire</button></h2><div class="howtxt hidden"></div><div class="sel-sous"><span class="muted">'+esc(parent)+', '+fmt.format(u.pop)+' habitants</span>'+[["sante-mentale","Rapport santé mentale"],["sante","Rapport santé"]].filter(([k])=>(D.rapports_territoires||[]).includes(lv+"-"+S.sel.c+"-"+k)).map(([k,l])=>'<a class="lien-rapport" href="'+(D.rapports_dossier||"territoires")+'/'+lv+'-'+S.sel.c+'-'+k+'.html">'+l+'</a>').join("")+'</div></div><div class="pastilles"><button id="selReplier" type="button" aria-controls="selCorps" aria-expanded="'+!S.selReplie+'" aria-label="'+(S.selReplie?"Déplier":"Replier")+' la fiche « '+esc(u.nm)+' »">'+(S.selReplie?ICONE_FEN.plus:ICONE_FEN.moins)+'</button></div></div>';
  const finTete=h.length;
  let court="",precision="";
  // phrase sur la profession affichée
  const p0=S.prof,lab=profLab(p0),d=unitD(lv,p0,i),nd=refD(lv,p0),n0=unitN(lv,p0,i);
  if(natOf(IDX.prof.get(p0)||{})!=="perimetre_elargi"){
    let ph=n0===0?(FEM.has(p0)?"Aucune ":"Aucun ")+lab.toLowerCase()+" ne déclare exercer dans ce territoire.":f1.format(d)+" "+(d>=2?pluriel(lab):lab.toLowerCase())+" pour 10 000 habitants, "+(Math.abs(d/nd-1)<.05?"autant que la moyenne "+MOYLAB[lv]:fois(d,nd)+" que la moyenne "+MOYLAB[lv])+".";
    const a=att(lv,p0,i);
    if(a&&S.mode==="all"){const e=a*u.pop/1e4,diff=e-unitN(lv,p0,i,"all");
      ph+=" Compte tenu du profil de sa population, l’effectif attendu est d’environ "+fmt.format(Math.round(e))+(Math.abs(diff)<1?", l’effectif observé y correspond.":diff>0?", on en compte environ "+fmt.format(Math.round(diff))+" de moins.":", on en compte environ "+fmt.format(Math.round(-diff))+" de plus.")+" C’est une comparaison avec des territoires semblables, pas une mesure du besoin."}
    const st=D.niveaux[lv].entonnoir?.[p0]?.[i];
    if(st!=null)ph+=" Compte tenu de sa taille, ce territoire est "+STATUT[String(st)]+".";
    // aucun psychiatre déclaré, mais des CMP où des psychiatres peuvent consulter (FINESS)
    const ncmp=D.niveaux[lv].cmp?.[i]||0;
    if(n0===0&&p0==="pedopsychiatre"&&IDX.prof.has("q_psychiatrie_enfant")){const q=unitN(lv,"q_psychiatrie_enfant",i);
      if(q>0){precision="On y compte toutefois "+q+" psychiatre"+(q>1?"s":"")+" qualifié"+(q>1?"s":"")+" pour l’enfant et l’adolescent.";
        ph+=" Aucun pédopsychiatre n’y est déclaré comme tel, mais "+q+" psychiatre"+(q>1?"s":"")+" qualifié"+(q>1?"s":"")+" pour l’enfant et l’adolescent y exerce"+(q>1?"nt":"")+"."}}
    if(n0===0&&ncmp&&p0==="psychiatre")ph+=" D’après FINESS et le ROR réunis, il accueille pourtant "+ncmp+" centre"+(ncmp>1?"s":"")+" médico-psychologique"+(ncmp>1?"s":"")+" (CMP), où des psychiatres peuvent consulter sans y être déclarés.";
    if(n0===0&&p0==="pedopsychiatre"){const e=lieuxEnfants(lv,i);if(e)ph+=" Il accueille "+e+" sans y être déclarés."}
    const ev=evol(lv,p0,i),ei=evolInfo(p0);
    // téléconsultation et activités sans soins à la population déclarées dans ce territoire, non comptées
    const td=D.niveaux[lv].a_distance?.[p0]?.[S.sel.c],hs=D.niveaux[lv].hors_soins?.[p0]?.[S.sel.c];
    const nb=k=>fmt.format(k)+" "+(k>1?pluriel(lab):lab.toLowerCase())+" "+(k>1?"déclarent":"déclare");
    if(td)ph+=" Par ailleurs, "+nb(td)+" ici une activité de téléconsultation, des soins à distance déclarés au siège de la société et non rattachés au territoire des patients, non comptée dans la densité.";
    if(hs)ph+=(td?" De plus, ":" Par ailleurs, ")+nb(hs)+" ici une activité sans soins à la population (siège d’organisme, contrôle médical…), non comptée dans la densité.";
    if(ev)ph+=" D’après les séries de la DREES, qui comptent chaque professionnel dans un seul département, la densité "+deMot(ei.lib.split(",")[0].toLowerCase())+" a évolué de "+signe(ev[2])+" de "+ei.debut+" à "+ei.fin+", contre "+signe(ei.fr[2])+" en France.";
    h+='<p class="phrase">'+esc(ph)+'</p>';court=ph;
    // combinaison des trois professions dans l'intercommunalité (carte des combinaisons, 23 octobre 2026), présence
    // ou absence seulement, jamais d'addition
    if(lv==="epci"&&S.fam!==SANTE){const g=unitN(lv,"medecin_generaliste",i,"all")>0,ps=unitN(lv,"psychologue",i,"all")>0,pt=unitN(lv,"psychiatre",i,"all")>0;
      const cb=g&&ps&&pt?"Des médecins généralistes, des psychologues et des psychiatres y déclarent exercer."
        :g&&ps?"Des médecins généralistes et des psychologues y déclarent exercer, mais aucun psychiatre."
        :g&&!pt?"Des médecins généralistes y déclarent exercer, mais ni psychologue ni psychiatre."
        :g?"Des médecins généralistes et des psychiatres y déclarent exercer, mais aucun psychologue.":"";
      const nc=D.niveaux[lv].cmp?.[i]||0,cmpTxt=g&&!pt&&nc&&p0!=="psychiatre"?" L’intercommunalité accueille toutefois "+nc+" centre"+(nc>1?"s":"")+" médico-psychologique"+(nc>1?"s":"")+" (CMP), où des psychiatres peuvent consulter sans y être déclarés.":"";
      if(cb)h+='<p class="phrase">'+esc(cb+cmpTxt)+'</p>'}
  }
  // légende en couleur (registre, point 10), l'explication de l'indice est dans « Comment lire »
  const dv=DIV(),barreL=c=>'<svg viewBox="0 0 26 10" aria-hidden="true"><rect x="1" y="2" width="24" height="6" fill="'+c+'"/></svg>';
  h+='<div class="fiche-legende"><span>'+barreL(dv[1])+'moins dense</span><span><svg viewBox="0 0 26 10" aria-hidden="true"><line x1="13" x2="13" y1="0" y2="10" stroke="'+css("--muted")+'" stroke-width="1.5"/></svg>moyenne '+MOYLAB[lv]+' = 100</span><span>'+barreL(dv[5])+'plus dense</span><span>50 = deux fois moins, 200 = deux fois plus, '+modeLab[S.mode]+'</span></div>';
  // dans le groupe « Salariés des établissements psychiatriques », le titre dit déjà où ils exercent : le libellé court
  // évite des lignes de quatre lignes qui décalaient barres et valeurs (remarque de Lucas du 30 octobre 2026), le
  // libellé entier reste dans l'infobulle
  const nomCourt=p=>natOf(p)==="perimetre_elargi"?p.libelle.replace(/, en établissement psychiatrique$/,""):p.libelle;
  const ligne=p=>{const ind=unitD(lv,p.id,i)/refD(lv,p.id)*100,l=Math.max(-2,Math.min(2,Math.log2(Math.max(ind,1)/100)));
      const w=Math.abs(l)/2*50,left=l<0?50-w:50,c=l<0?dv[1]:dv[5];
      const nP=unitN(lv,p.id,i),dP=unitD(lv,p.id,i),bulleP=p.libelle+", "+fmt.format(nP)+" professionnel"+(nP>1?"s":"")+", "+f1.format(dP)+" pour 10 000 habitants, indice "+fmt.format(Math.round(ind))+" (moyenne "+MOYLAB[lv]+" = 100)";
      if(nP===0){let prec="";
        if(p.id==="pedopsychiatre"&&IDX.prof.has("q_psychiatrie_enfant")){const q=unitN(lv,"q_psychiatrie_enfant",i);if(q>0)prec=fmt.format(q)+" psychiatre"+(q>1?"s":"")+" qualifié"+(q>1?"s":"")+" pour l’enfant et l’adolescent y exerce"+(q>1?"nt":"")+"."}
        if(p.id==="psychiatre"){const nc=D.niveaux[lv].cmp?.[i]||0;if(nc)prec=fmt.format(nc)+" CMP, où des psychiatres peuvent consulter sans y être déclarés."}
        return'<div class="prow zero'+(p.id===S.prof?' on':'')+'" data-p="'+p.id+'" title="'+esc(p.libelle+", aucun professionnel déclaré dans ce territoire, la densité n’est pas comparée"+(prec?". "+prec:"."))+'"><span class="lbl">'+esc(nomCourt(p))+'</span><span class="aucun">aucun déclaré</span><span class="v"></span>'+(prec?'<span class="prec">'+esc(prec)+'</span>':'')+'</div>'}
      return'<div class="prow'+(p.id===S.prof?' on':'')+'" data-p="'+p.id+'" title="'+esc(bulleP)+'"><span class="lbl">'+esc(nomCourt(p))+'</span><svg viewBox="0 0 100 10" preserveAspectRatio="none" style="height:10px"><line x1="50" x2="50" y1="0" y2="10" stroke="'+css("--muted")+'" stroke-width=".6"/><rect x="'+left+'" width="'+w+'" y="2" height="6" fill="'+c+'"/></svg><span class="v">'+fmt.format(Math.round(ind))+'</span></div>'};
  const blocs={};
  // deux blocs séparés, santé mentale puis santé
  for(const fam of [SM,SANTE]){
    if(S.fam!=="*"&&S.fam!==fam)continue;
    const ps=D.professions.filter(p=>famOf(p)===fam&&natN(p.id)>0);if(!ps.length)continue;
    const h0=h;h='<h3 class="fiche-bt">'+(fam===SM?"Santé mentale":"Santé")+'</h3>';
    for(const g of [...new Set(ps.map(p=>p.groupe))].sort((a,b)=>ordreGroupe(a)-ordreGroupe(b))){
      const pg=ps.filter(p=>p.groupe===g),annexe=pg.some(p=>natOf(p)!=="profession");
      if(annexe){h+='<details class="groupe gr"'+(pg.some(p=>p.id===S.prof)?' open':'')+'><summary>'+esc(g)+'<span class="mention">ne s’additionne pas</span></summary>';for(const p of pg)h+=ligne(p);h+='</details>'}
      // spécialités médicales repliées par groupe, ouvertes quand la profession affichée en fait partie (version 2)
      else if((D.meta.groupes_specialites||[]).includes(g)){h+='<details class="groupe gr"'+(pg.some(p=>p.id===S.prof)?' open':'')+'><summary>'+esc(g)+'<span class="mention">'+pg.length+' spécialités</span></summary>';for(const p of pg)h+=ligne(p);h+='</details>'}
      else{h+='<div class="gr"><div class="gh">'+esc(g)+'</div>';for(const p of pg)h+=ligne(p);h+='</div>'}
    }
    blocs[fam]=h;h=h0;
  }
  if(u.x){blocs.pop='';const h0=h;h='';const grp=[...new Set(ctxVisibles().filter(c=>u.x[c.i]!=null).map(c=>c.groupe||"Profil de la population"))];const ligneCtx=c=>u.x[c.i]==null?'':'<div><dt title="'+esc((c.explication||"")+(c.source?" Source, "+c.source+".":""))+'">'+esc(c.label)+'</dt><dd>'+(c.unite==="€"?fmt.format(Math.round(u.x[c.i]))+'\u202f€':(u.x[c.i]===0?"0":f1.format(u.x[c.i]))+(c.unite==="%"?"\u202f%":c.unite==="km"?"\u202fkm":c.unite==="minutes"?"\u202fmin":""))+'</dd></div>';
  h+='<h3 class="fiche-bt">Profil de la population</h3>'+grp.map(g=>'<div class="gr pop">'+(g==="Profil de la population"?'':'<div class="gh">'+esc(g)+'</div>')+'<dl class="kv">'+ctxVisibles().filter(c=>(c.groupe||"Profil de la population")===g).map(ligneCtx).join("")+'</dl></div>').join("");blocs.pop=h;h=h0}
  // offre de la famille choisie (santé mentale puis santé), puis profil de la population, chacun en colonnes équilibrées
  h+='<div class="fiche-colonnes">'+[blocs[SM],blocs[SANTE],blocs.pop].filter(Boolean).join("")+'</div>';
  if(LX&&D.niveaux[lv].lieux)h+='<p class="small" style="margin:14px 0 0"><button type="button" class="lien" id="selVersLieux">Structures de soins de ce territoire, niveau de confirmation et liste</button></p>';
  // addictologie de la région du territoire, dans Explorer (choix de Lucas du 29 octobre 2026), consommations publiées
  // par région seulement
  const rg=regionDe(lv,S.sel.c);
  if(S.fam!==SANTE&&rg)h+='<p class="small" style="margin:6px 0 0"><a href="explorer.html#qAddicto?fam='+famCle()+'&adReg='+rg+'">L’addictologie '+esc(enRegion(rg))+', de l’offre aux consommations, dans Explorer</a></p>';
  // limites propres à ce territoire (par exemple les suicides en Île-de-France)
  // une région se désigne « reg: » suivi de son code dans les territoires d'une limite, pour ne pas se confondre avec
  // un département de même code (Guyane 03 et Allier 03), seule la limite des manques de la SAE l'utilise
  const codes=[S.sel.c,lv==="epci"?u.p:null,lv==="reg"?"reg:"+S.sel.c:null],lims=Object.keys(D.limites||{}).filter(k=>codes.some(c=>c&&D.limites[k].territoires?.[c]));
  if(fragile(lv,S.sel.c))lims.unshift(fragile(lv,S.sel.c));
  h+=limiteHtml(["prof:"+p0,...lims],codes);
  // le détail se masque ou s'affiche par la flèche, l'en-tête reste visible (le choix est gardé d'un territoire à l'autre)
  el.innerHTML=h.slice(0,finTete)+'<div id="selCorps" data-export="fiche"'+(S.selReplie?' hidden':'')+'>'+h.slice(finTete)+'</div>';el.classList.toggle("repliee",!!S.selReplie);
  // valeurs de la fiche, exportées par « Citer et exporter »
  EXPORT_CSV.fiche=()=>{const lignes=[["Profession","Effectif","Pour 10 000 habitants","Indice (moyenne "+MOYLAB[lv]+" = 100)"]];
    for(const pr of D.professions.filter(x=>(S.fam==="*"||famOf(x)===S.fam)&&!x.id.startsWith("esm_")&&natN(x.id)>0)){const n=unitN(lv,pr.id,i),d=unitD(lv,pr.id,i),r=refD(lv,pr.id);
      lignes.push([pr.libelle,fmt.format(n),f1.format(d),r?fmt.format(Math.round(d/r*100)):""])}
    if(u.x){lignes.push([]);lignes.push(["Indicateur","Valeur"]);for(const cx of ctxVisibles())if(u.x[cx.i]!=null)lignes.push([cx.label+(cx.unite?" ("+cx.unite+")":""),f1.format(u.x[cx.i])])}
    return {titre:"Profil de "+u.nm+", offre de soins comparée à la moyenne "+MOYLAB[lv],nom:nomFichier("profil_"+u.nm,"profil"),texte:lignes.map(l=>l.map(qCsv).join(";")).join("\r\n")}};
  br.innerHTML='<h2>'+esc(u.nm)+'</h2><div class="muted small">'+esc(parent)+', '+fmt.format(u.pop)+' habitants</div>'+(court?'<p class="phrase">'+esc(court.split(". ")[0].replace(/\.$/,""))+'.'+(precision?' '+esc(precision):'')+'</p>':'')+'<button class="lien" id="selVoir">Voir son profil complet sous la carte</button>';
  document.getElementById("selVoir").onclick=()=>el.scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"});
  document.getElementById("selReplier").onclick=()=>{S.selReplie=!S.selReplie;const b=document.getElementById("selReplier");
    document.getElementById("selCorps").hidden=S.selReplie;b.setAttribute("aria-expanded",String(!S.selReplie));b.innerHTML=S.selReplie?ICONE_FEN.plus:ICONE_FEN.moins;
    b.setAttribute("aria-label",(S.selReplie?"Déplier":"Replier")+" la fiche « "+u.nm+" »");el.classList.toggle("repliee",S.selReplie)};
  el.querySelectorAll(".prow").forEach(r=>r.onclick=()=>{S.prof=r.dataset.p;document.getElementById("prof").value=S.prof;render()});
  const vl=document.getElementById("selVersLieux");if(vl)vl.onclick=versStructures;
}
function hbars(id,rows,total){
  const max=d3.max(rows,r=>r[1])||1;
  document.getElementById(id).innerHTML=rows.map(([l,n])=>'<div class="r"><span>'+esc(l)+'</span><span class="muted">'+fmt.format(n)+(total?' ('+Math.round(n/total*100)+' %)':'')+'</span><div class="t"><span style="width:'+(n/max*100)+'%"></span></div></div>').join("")||'<p class="small muted">Pas de données pour cette profession.</p>';
}
function lowerPanels(){
  const p=S.prof;const dep=S.sel?(S.sel.lv==="dep"?S.sel.c:S.sel.lv==="epci"?IDX.epciDep.get(S.sel.c):null):null;const key=dep&&D.secteurs?.v?.[p]?.[dep]?dep:"FR";
  const where=key==="FR"?"France entière":IDX.depName.get(key);
  const sec=(D.secteurs?.v?.[p]?.[key]||[]).map(([i,n])=>[D.secteurs.lib[i],n]);const tot=d3.sum(sec,r=>r[1]);
  document.getElementById("secNote").textContent=profLab(p)+", "+where+". Secteur attribué par le RPPS à la structure d’exercice, une personne peut relever de plusieurs secteurs.";
  hbars("secBars",sec,tot);
  // structures de santé mentale à numéro FINESS propre (21 octobre 2026), même territoire que les secteurs
  const ex=(D.exercice?.v?.[p]?.[key]||[]).map(([i,n])=>[D.exercice.lib[i],n]);
  document.getElementById("exBloc").hidden=!ex.length;
  if(ex.length){document.getElementById("exNote").textContent=pluriel(profLab(p))+" qui déclarent exercer dans une structure de santé mentale enregistrée sous son propre numéro FINESS, "+where+", en personnes distinctes. Beaucoup déclarent leur hôpital de rattachement plutôt que la structure, ces nombres sont des minimums. Hôpitaux de jour et hospitalisation non comptés, ils partagent le numéro de leur hôpital.";
    hbars("exBars",ex,0)}
  const cat=(D.categories?.v?.[p]?.[key]||[]).map(([i,n])=>[D.categories.lib[i],n]);
  const base=(D.site_dossier&&D.site_dossier!==".")?D.site_dossier+"/":"",choisi=S.sel&&S.sel.lv===S.level&&LX&&D.niveaux[S.level].lieux;
  document.getElementById("catNote").innerHTML=esc("Catégorie FINESS des établissements d’exercice, "+where+". Les professionnels sont classés selon la catégorie sous laquelle FINESS inscrit le lieu d’exercice qu’ils déclarent au répertoire. Le personnel des structures qui dépendent d’un hôpital (CMP, CATTP, hôpitaux de jour) déclare en général l’hôpital lui-même, il est alors compté sous « Centre hospitalier » ou « CHS, EPSM » et non sous la structure ; l’encadré « Où ils exercent » recompte les professionnels par structure de santé mentale. Un établissement inscrit sous une catégorie, CMP par exemple, peut être d’un autre type d’après son nom (hôpital de jour, CATTP, équipe mobile). Les structures de soins, elles, sont rangées dans le type que désigne leur nom, ")
    +'<a href="'+esc(base)+'methode-structures.html#lieux">voir la page méthode</a>.'
    +(choisi?'<br><button type="button" class="lien" id="catVersLieux">Voir les structures de soins de ce territoire ('+esc(D.niveaux[S.level].units[IDX[S.level].get(S.sel.c)].nm)+')</button>':'');
  const cv=document.getElementById("catVersLieux");if(cv)cv.onclick=versStructures;
  // les dix premières catégories, puis toutes les autres derrière un bouton, pour chaque profession
  const totCat=d3.sum(cat,r=>r[1]);hbars("catBars",cat.slice(0,10),totCat);
  let ca=document.getElementById("catAutres");if(!ca){ca=document.createElement("div");ca.id="catAutres";document.getElementById("catBars").after(ca)}
  const reste=cat.slice(10);ca.innerHTML=reste.length?'<button type="button" class="lien" aria-expanded="false">Autres catégories ('+reste.length+')</button><div class="hbars" id="catBarsReste" hidden></div>':"";
  if(reste.length){hbars("catBarsReste",reste,totCat);const bt=ca.querySelector("button"),zone=ca.querySelector("#catBarsReste");
    bt.onclick=()=>{const o=zone.hidden;zone.hidden=!o;bt.setAttribute("aria-expanded",String(o));bt.textContent=(o?"Masquer les autres catégories":"Autres catégories ("+reste.length+")")}}
  const st=D.structures?.[p]?.[key]||[];
  document.getElementById("structs").innerHTML=st.map(([rs,c,n])=>'<li>'+esc(rs)+' <span class="muted">'+esc(c)+', '+fmt.format(n)+'</span></li>').join("")||'<li class="muted">Disponible pour les principales professions salariées.</li>';
}

// ---------- tableau
function table(){
  const lv=S.level,L=D.niveaux[lv];
  const profs=D.professions.filter(p=>inFam(p)&&natOf(p)!=="perimetre_elargi"&&(S.grp==="*"||p.groupe===S.grp)&&natN(p.id)>0);
  const q=document.getElementById("q").value.trim().toLowerCase();
  let rows=L.units.map((u,i)=>({u,i})).filter(r=>r.u.pop>0&&(!q||r.u.nm.toLowerCase().includes(q)));
  const k=S.sort;
  if(k==="nm")rows.sort((a,b)=>a.u.nm.localeCompare(b.u.nm,"fr")*(S.asc?1:-1));
  else if(k==="pop")rows.sort((a,b)=>(a.u.pop-b.u.pop)*(S.asc?1:-1));
  else if(k)rows.sort((a,b)=>(unitD(lv,k,a.i)-unitD(lv,k,b.i))*(S.asc?1:-1));
  const dv=DIV(),sc=d3.scaleThreshold().domain([.5,.7,.9,1.1,1.4,2]).range(dv);
  const t=document.getElementById("tbl");
  t.querySelector("thead").innerHTML='<tr><th><button data-s="nm" class="'+(k==="nm"?"on":"")+'">Territoire</button></th><th><button data-s="pop" class="'+(k==="pop"?"on":"")+'">Habitants</button></th>'+profs.map(p=>'<th><button data-s="'+p.id+'" class="'+(k===p.id?"on":"")+'">'+esc(p.libelle)+'</button></th>').join("")+'</tr><tr><td class="muted small">Moyenne '+MOYLAB[lv]+'</td><td class="muted small">'+fmt.format(D.france.pop)+'</td>'+profs.map(p=>'<td class="muted small">'+f1.format(refD(lv,p.id))+'</td>').join("")+'</tr>';
  const dark=matchMedia("(prefers-color-scheme: dark)").matches;
  t.querySelector("tbody").innerHTML=rows.slice(0,1500).map(r=>'<tr data-c="'+r.u.c+'"><td>'+esc(r.u.nm)+'</td><td>'+fmt.format(r.u.pop)+'</td>'+profs.map(p=>{const d=unitD(lv,p.id,r.i),ratio=d/refD(lv,p.id),bg=sc(ratio),strong=ratio<.5||ratio>2;return'<td style="'+styleCase(bg,false)+'">'+f1.format(d)+'</td>'}).join("")+'</tr>').join("");
}
// du répertoire aux densités, personnes à chaque étape pour la profession choisie (France entière)
const ETAPES=[[0,"Inscrits au répertoire",""],[1,"Avec une activité déclarée","sans activité déclarée"],
  [3,"Avec un lieu d’exercice","sans lieu fixe (remplacements, exercice sans site)"],[6,"Comptés dans les densités","seulement des activités non rattachées à un territoire"]];
// « , dont 4 226 en téléconsultation (soins à distance) et 120 sans soins à la population »
function detailNonRattaches(dist,sans){const p=[];if(dist)p.push(fmt.format(dist)+" en téléconsultation (soins à distance)");
  if(sans)p.push(fmt.format(sans)+" sans soins à la population");return p.length?", dont "+p.join(" et "):""}
function parcoursAtlas(){
  const svg=d3.select("#pcPlot");svg.selectAll("*").remove();const p=S.prof,v=(D.parcours||{})[p],ph=document.getElementById("pcPhrase");
  if(!v){ph.textContent="Pas de décompte par étape pour cette sélection (qualification ou périmètre élargi), seulement pour les professions du répertoire.";svg.attr("viewBox","0 0 640 20");delete document.getElementById("pcPlot").dataset.vbSigne;return}
  // barres fines, libellé au-dessus et valeur à droite, comme « Où ils exercent » ; dessin à 640 de large, jamais agrandi
  const et=ETAPES.filter(e=>v[e[0]]),tot=v[et[0][0]],w=640,bh=7;
  // détail de chaque étape, coupé à la largeur du dessin (petit texte, environ 11,5 × 0,56 unités par caractère)
  let pr=null;const det=et.map(([i,_t,raison])=>{const n=v[i],d=pr!=null&&pr>n?coupeLib("− "+fmt.format(pr-n)+" "+raison+(i===6?detailNonRattaches(v[5],v[4]):""),Math.floor(w/(TYPO.petit*.56))):[];pr=n;return d});
  const ys=[];let cum=0;det.forEach(d=>{ys.push(cum);cum+=36+16*Math.max(1,d.length)});const h=cum+4;
  svg.attr("viewBox","0 0 "+w+" "+h);delete document.getElementById("pcPlot").dataset.vbSigne;
  const x=d3.scaleLinear().domain([0,tot]).range([0,w]);let prec=null;
  et.forEach(([i,titre,raison],k)=>{const y=ys[k],n=v[i],der=i===6;
    svg.append("text").attr("x",0).attr("y",y+13).attr("fill",css("--ink")).attr("font-size",12).attr("font-weight",der?600:400).text(titre);
    svg.append("text").attr("x",w).attr("y",y+13).attr("text-anchor","end").attr("fill",css("--ink")).attr("font-size",12)
      .attr("font-weight",der?600:400).text(fmt.format(n));
    svg.append("rect").attr("x",0).attr("y",y+19).attr("width",w).attr("height",bh).attr("rx",1.5).attr("fill",css("--nodata"));
    svg.append("rect").attr("x",0).attr("y",y+19).attr("width",Math.max(1,x(n))).attr("height",bh).attr("rx",1.5)
      .attr("fill",css(der?"--r4":"--r3")).append("title").text(titre+", "+fmt.format(n));
    if(prec!=null&&prec>n){svg.append("rect").attr("x",x(n)).attr("y",y+19).attr("width",x(prec)-x(n)).attr("height",bh)
        .attr("fill","none").attr("stroke",css("--d1")).attr("stroke-width",1).attr("stroke-dasharray","3 2");
      const t=svg.append("text").attr("x",0).attr("y",y+42).attr("fill",css("--muted")).attr("font-size",10);
      det[k].forEach((l,j)=>t.append("tspan").attr("x",0).attr("dy",j?16:0).text(l))}
    prec=n});
  const pl=pluriel(profLab(p));
  ph.textContent=(v[0]?"Sur "+fmt.format(v[0])+" "+pl+" inscrits au répertoire, "+fmt.format(v[1])+" déclarent une activité":"Sur "+fmt.format(v[1])+" "+pl+" qui déclarent une activité")
    +", "+fmt.format(v[3])+" ont au moins un lieu d’exercice et "+fmt.format(v[6])+" sont comptés dans les densités des territoires."
    +(v[5]?" "+fmt.format(v[5])+" n’exercent, avec un lieu déclaré, qu’en téléconsultation, des soins à distance déclarés au siège de la société et non rattachés au territoire des patients.":"")
    +(v[4]?" "+fmt.format(v[4])+" n’exercent qu’à des activités sans soins à la population.":"");
}
// liste des territoires du niveau affiché, pour choisir un territoire sans souris
let CHERCHE_NIV=null;
function listeCherche(){if(CHERCHE_NIV===S.level)return;CHERCHE_NIV=S.level;const L=D.niveaux[S.level];
  document.getElementById("cherche-liste").innerHTML=L.units.map(u=>'<option value="'+esc(u.nm+(u.p&&S.level!=="reg"?" ("+u.p+")":""))+'"></option>').join("")}
document.getElementById("cherche").addEventListener("change",e=>{const v=e.target.value.trim(),L=D.niveaux[S.level];
  const u=L.units.find(u=>(u.nm+(u.p&&S.level!=="reg"?" ("+u.p+")":""))===v)||L.units.find(u=>u.nm.toLowerCase()===v.toLowerCase());
  if(!u)return;S.sel={lv:S.level,c:u.c};render();const el=document.getElementById("selCard");if(!el.classList.contains("hidden"))el.scrollIntoView({block:"start"})});


// ---------- entonnoir
const STATUT={"-2":"nettement en dessous de la moyenne des territoires, au-delà de ce que le hasard expliquerait","-1":"en dessous de la moyenne des territoires, un écart que le hasard expliquerait rarement","0":"proche de la moyenne des territoires, l’écart peut tenir au hasard","1":"au-dessus de la moyenne des territoires, un écart que le hasard expliquerait rarement","2":"nettement au-dessus de la moyenne des territoires, au-delà de ce que le hasard expliquerait"};

// lien vers les fenêtres d'Explorer qui ont repris les onglets Inégalités et Typologie (lots 2 et 3, 28 octobre
// 2026), réglé sur la profession, le niveau et la famille choisis ici ; les régions, sans escalier ni entonnoir,
// passent aux intercommunalités
function liensExplorerOnglets(){const n=document.getElementById("lienNuage");if(n)n.href=lienNuage({});
  const a=document.getElementById("lienExplorerOnglets");if(!a)return;
  a.href="explorer.html#qInegalites?fam="+famCle()+"&iProf="+encodeURIComponent(S.prof)+"&iNiv="+(S.level==="dep"?"dep":"epci")}
// code de la région d'un territoire, par le nom de région que porte chaque département (u.p)
function regionDe(lv,c){const R=D.niveaux.reg;if(!R)return null;if(lv==="reg")return c;
  const dep=lv==="dep"?c:(D.niveaux.epci.units[IDX.epci.get(c)]||{}).p,u=D.niveaux.dep&&D.niveaux.dep.units[IDX.dep.get(dep)];
  const r=u&&R.units.find(x=>x.nm===u.p);return r?r.c:null}
// région à la française dans une phrase (« en Bretagne », « dans les Hauts-de-France », « à La Réunion »)
function enRegion(c){const u=D.niveaux.reg.units[IDX.reg.get(c)],n=u?u.nm:c;
  return /^(La Réunion|Mayotte)$/.test(n)?"à "+n:/^(Hauts|Pays)/.test(n)?"dans les "+n:/^(Grand Est|Centre)/.test(n)?"dans le "+n:"en "+n}
// « Croiser deux indicateurs » vit dans Explorer (lot 2 du 29 octobre 2026). Une case des corrélations ou une barre des
// indicateurs entre eux y ouvre le nuage réglé sur la même profession, le même indicateur et le même niveau.
function lienNuage(o){return "explorer.html#cxFenNuage?fam="+famCle()+"&cxProf="+encodeURIComponent(o.prof||S.prof)
  +"&cxNiv="+(o.niveau||(S.level==="dep"?"dep":"epci"))+"&cxMode="+S.mode+"&cxX="+encodeURIComponent(o.x||S.xvar||"")+"&cxY="+encodeURIComponent(o.y||"")}
function ouvrirNuage(o){location.href=lienNuage(o)}
// accès aux structures de soins par territoire, temps par la route de l'INSEE et distance à la structure la plus proche
function accesLieux(){const tab=document.getElementById("alTable"),lv=S.level==="reg"?"dep":S.level,N=D.niveaux[lv];
  const route=(D.route||[]).filter(r=>S.fam==="*"||r.fam===S.fam),RT=N.route||{};
  const types=LX?LX.types.filter(t=>t.complet&&N.lieux_dist?.[t.id]&&(S.fam==="*"||t.famille===S.fam)):[];
  if(!route.length&&!types.length){tab.innerHTML="";document.getElementById("alPhrase").textContent="Pas de données d’accès pour cette sélection.";return}
  const court=s=>{s=s.replace(/^Structures? de psychiatrie ambulatoire, dont les centres médico-psychologiques \(CMP\)/,"Psychiatrie ambulatoire, dont CMP").split(", ")[0];return s};
  const cols=[...route.filter(r=>RT[r.id]).map(r=>({id:"r:"+r.id,g:"r",lib:court(r.lib),plein:r.lib,v:i=>RT[r.id][i]?.[1]})),
    ...types.map(t=>({id:"l:"+t.id,g:"l",lib:court(t.lib),plein:t.lib,v:i=>N.lieux_dist[t.id][i]}))];
  const tri=S.alTri||{c:cols[0]?.id,asc:false};
  const lignes=N.units.map((u,i)=>({u,i})).filter(x=>x.u.pop>0);
  const col=cols.find(c=>c.id===tri.c)||cols[0];
  lignes.sort((a,b)=>{const x=col.v(a.i),y=col.v(b.i);if(x==null)return 1;if(y==null)return -1;return tri.asc?x-y:y-x});
  const nr=cols.filter(c=>c.g==="r").length,nl=cols.filter(c=>c.g==="l").length;
  tab.innerHTML='<thead><tr><th rowspan="2">'+(lv==="dep"?"Département":"Intercommunalité")+'</th><th rowspan="2">Habitants</th>'
    +(nr?'<th colspan="'+nr+'" class="groupe-col">Temps médian par la route, en minutes</th>':'')+(nl?'<th colspan="'+nl+'" class="groupe-col">Distance médiane à la structure la plus proche, en km à vol d’oiseau</th>':'')+'</tr><tr>'
    +cols.map(c=>'<th title="'+esc(c.plein)+'"><button type="button" class="tri" data-c="'+c.id+'" aria-sort="'+(c.id===col.id?(tri.asc?"ascending":"descending"):"none")+'">'+esc(c.lib)+'</button></th>').join("")+'</tr></thead><tbody>'
    +lignes.map(({u,i})=>'<tr><td>'+esc(u.nm)+'</td><td>'+fmt.format(u.pop)+'</td>'+cols.map(c=>{const v=c.v(i);return'<td>'+(v==null?(c.g==="l"?"aucune sur le territoire":"non disponible"):f1.format(v))+'</td>'}).join("")+'</tr>').join("")+'</tbody>';
  tab.querySelectorAll("button.tri").forEach(b=>b.onclick=()=>{S.alTri={c:b.dataset.c,asc:S.alTri?.c===b.dataset.c?!S.alTri.asc:false};accesLieux();normaliserEncadres()});
  const t0=types.find(t=>t.id==="lieu_cmp_adultes")||types[0],fr=t0&&LX.fr?.[t0.id];
  document.getElementById("alPhrase").textContent=fr?"En France, la moitié des habitants vit à moins de "+f1.format(fr[0])+" km à vol d’oiseau de la structure la plus proche de type « "+t0.lib+" », et "+f1.format(fr[2]*100)+" % à plus de 30 km.":"";
  document.getElementById("alNote").textContent="Un clic sur l’en-tête d’une colonne trie le tableau. Temps de trajet de l’INSEE, en voiture aux heures creuses, vers l’équipement le plus proche. Distances à vol d’oiseau depuis le centre de chaque commune, médiane des habitants du territoire, vers les structures recensées par FINESS et le ROR réunis sans double compte."+(S.level==="reg"?" Présenté par département.":"");
  document.getElementById("alLimite").innerHTML=limiteHtml(["route",...(route.some(r=>r.id==="psychiatrie_ambulatoire"&&RT[r.id])?["route:psychiatrie_ambulatoire"]:[]),"lieux"])}

// ---------- sources
function sources(){
  const j=D.meta.journal||{sources:[],controles:[]};
  document.getElementById("srcList").innerHTML=j.sources.map(s=>'<li><strong>'+esc(s.source)+'</strong>, '+esc(s.statut)+(s.date_donnees?' ('+esc(s.date_donnees)+')':'')+'. <span class="muted">'+esc(s.detail)+'</span></li>').join("");
  document.getElementById("ctlList").innerHTML=j.controles.map(([a,b])=>'<li>'+esc(a)+', <span class="muted">'+esc(b)+'</span></li>').join("");
}

function comprendre(){
  const g=(D.meta.glossaire||[]).filter(x=>!x.famille||S.fam==="*"||x.famille===S.fam);
  document.getElementById("glNote").textContent="Notions utiles pour "+famLab[S.fam]+".";
  document.getElementById("glList").innerHTML=g.map(x=>'<dt>'+esc(x.terme)+'</dt><dd>'+esc(x.definition)+'</dd>').join("")||'<dd>Glossaire absent de ce fichier de données.</dd>';
  document.getElementById("ctxList").innerHTML=ctxVisibles().map(c=>'<dt>'+esc(c.label)+(c.unite?' <span class="tag">'+esc(c.unite)+'</span>':'')+'</dt><dd>'+esc(c.explication||"")+(c.source?' <span class="muted">Source, '+esc(c.source)+'.</span>':'')+'</dd>').join("");
  document.getElementById("libNote").textContent=(D.meta.libelles||"")+" "+(D.meta.licences||"");
}

// ---------- orchestration
function syncBar(){
  document.querySelectorAll(".seg[data-k]").forEach(sg=>sg.querySelectorAll("button").forEach(b=>b.setAttribute("aria-pressed",String(S[sg.dataset.k]===b.dataset.v))));
  const hasAtt=!!(D.niveaux[S.level].attendu&&D.niveaux[S.level].attendu[S.prof]);
  const ab=document.querySelector('#metricSeg [data-v="acces"]');ab.disabled=!(D.niveaux[S.level].acces&&D.niveaux[S.level].acces[S.prof])||S.mode!=="all";
  if(ab.disabled&&S.metric==="acces")S.metric="dens";
  const zb=document.querySelector('#metricSeg [data-v="zones"]');zb.disabled=!(D.niveaux[S.level].zones&&D.niveaux[S.level].zones[S.prof])||S.mode!=="all";
  if(zb.disabled&&S.metric==="zones")S.metric="dens";
  const eb=document.querySelector('#metricSeg [data-v="ecart"]');eb.disabled=!hasAtt||S.mode!=="all";
  if(eb.disabled&&S.metric==="ecart")S.metric="dens";
  const evb=document.querySelector('#metricSeg [data-v="evol"]');evb.disabled=!(D.niveaux[S.level].evolution?.[S.prof])||S.mode!=="all";
  evb.title=evb.disabled?"Disponible pour les régions et les départements, pour les professions suivies par la DREES depuis 2016":"";
  if(evb.disabled&&S.metric==="evol")S.metric="dens";
  // distance aux structures, cliquable dès qu'un type a des distances à ce niveau ; sans type choisi sous la carte, le
  // premier type disponible de la liste est retenu (remarque de Lucas du 23 octobre 2026, la mesure semblait inactive)
  const ld=D.niveaux[S.level].lieux_dist||{},lb=document.querySelector('#metricSeg [data-v="lieux"]');lb.disabled=!Object.keys(ld).length;
  if(S.metric==="lieux"&&!(S.lieux&&ld[S.lieux])){const v=[...document.querySelectorAll("#lieuxType option")].map(o=>o.value).find(x=>x&&ld[x]);
    if(v){S.lieux=v;document.getElementById("lieuxType").value=v}else S.metric="dens"}
  if(lb.disabled&&S.metric==="lieux")S.metric="dens";
  const tb=document.querySelector('#metricSeg [data-v="trajet"]');tb.disabled=!(routeEq(S.prof)&&D.niveaux[S.level].route);
  if(tb.disabled&&S.metric==="trajet")S.metric="dens";
  document.querySelectorAll('.seg[data-k="metric"] button').forEach(b=>b.setAttribute("aria-pressed",String(S.metric===b.dataset.v)));
  raisonsMesures();
  document.getElementById("prof").value=S.prof;
  document.getElementById("grp").value=S.grp;
  const typo=S.tab==="sources"||S.tab==="comprendre";
  document.getElementById("libNote2").textContent=D.meta.libelles||"";
  document.getElementById("bar").classList.toggle("hidden",typo);
  document.getElementById("metricSeg").classList.toggle("hidden",S.tab!=="carte");
  document.querySelector('.seg[data-k="level"] [data-v="dep"]').disabled=false;
  // les régions sont trop peu nombreuses pour les corrélations et les indices, elles servent à la carte et au tableau
  const tub=document.querySelector('.seg[data-k="vue"] [data-v="tuiles"]');tub.disabled=!D.tuiles;
  tub.title="Un carré de même taille par département";
  if(S.vue==="tuiles"&&(tub.disabled||S.level!=="dep"))S.vue="carte";
  document.querySelectorAll('.seg[data-k="vue"] button').forEach(b=>b.setAttribute("aria-pressed",String(S.vue===b.dataset.v)));
  const rb=document.querySelector('.seg[data-k="level"] [data-v="reg"]');rb.disabled=!D.niveaux.reg||!["carte","tableau"].includes(S.tab);
}
// encadrés étroits repérés à chaque rendu (les cadres créés en cours de route compris), voir [data-etroit] (attribut, car certains encadrés réécrivent leur classe)
const ETROIT_RO=new ResizeObserver(es=>es.forEach(e=>{const w=e.contentRect.width;if(w)e.target.toggleAttribute("data-etroit",w<300)}));  // largeur du contenu, sans les marges intérieures
// note de méthode longue posée avant une figure, réduite à sa première phrase, la suite s'ouvre au clic (chantier
// d'organisation, 22 octobre 2026). Seules les notes en texte simple sont repliées, une note réécrite au rendu suivant
// l'est de nouveau.
function replierNotes(){document.querySelectorAll(".panel p.note").forEach(p=>{
  if(p.children.length||p.closest(".howtxt"))return;const t=p.textContent.trim();if(t.length<260)return;
  const m=t.match(/^(.+?[.!?])\s+(?=[A-ZÀ-Ý«])/);if(!m||t.length-m[1].length<80)return;
  p.innerHTML=esc(m[1])+'<span class="note-reste" hidden> '+esc(t.slice(m[1].length).trim())+'</span> <button type="button" class="note-suite" aria-expanded="false">Lire la suite</button>';
  const b=p.querySelector(".note-suite"),r=p.querySelector(".note-reste");
  b.onclick=()=>{r.hidden=!r.hidden;b.textContent=r.hidden?"Lire la suite":"Replier";b.setAttribute("aria-expanded",String(!r.hidden))}})}
// la typologie garde sa mise en page propre (liste défilante à hauteur de la carte)
function equilibrerPanneaux(){document.querySelectorAll(".two:not(.typo)").forEach(t=>{if(!t.offsetParent)return;
  t.classList.remove("empile");t.style.alignItems="start";
  const h=[...t.children].filter(c=>c.offsetParent).map(c=>c.getBoundingClientRect().height);t.style.alignItems="";
  if(h.length===2&&Math.min(...h)>0&&Math.max(...h)/Math.min(...h)>1.15)t.classList.add("empile")})}

// profession choisie dans une liste rangée par groupe, sous son nom souligné (refonte du 23 octobre 2026). La liste du
// navigateur reste la source de l'état : un choix y écrit la valeur et déclenche son événement « change ».
// une mesure grisée dit pourquoi, sur une ligne sous la barre, au lieu d'une infobulle que personne ne voit (Impeccable,
// un état indisponible s'explique là où on le voit)
const RAISONS_MESURE={ecart:"par intercommunalité, tous modes d’exercice",zones:"par intercommunalité, tous modes d’exercice",
  evol:"pour les professions suivies par la DREES depuis 2016, par région ou département, tous modes d’exercice",
  trajet:"pour les professions dont le temps de trajet par la route est publié",lieux:"aucune distance calculée à ce niveau"};
function raisonsMesures(){const seg=document.getElementById("metricSeg");if(!seg)return;
  let r=document.getElementById("raisonsMesure");if(!r){r=document.createElement("p");r.id="raisonsMesure";r.className="raisons-mesure";(seg.closest(".groupe-reg")||seg).after(r)}
  const par=new Map();seg.querySelectorAll("button:disabled").forEach(b=>{const t=RAISONS_MESURE[b.dataset.v];if(!t)return;par.set(t,(par.get(t)||[]).concat(b.textContent.trim()))});
  const ph=[...par].map(([t,ls])=>(ls.length>1?ls.slice(0,-1).join(", ")+" et "+ls.at(-1).toLowerCase():ls[0])+", "+t+".");
  r.textContent=ph.length?"Non disponible pour ce choix. "+ph.join(" "):"";r.hidden=!ph.length||seg.classList.contains("hidden")}
function intitulesReglages(){const lib={level:"Niveau",mode:"Exercice",metric:"Mesure"};
  // l'intitulé et son groupe sont réunis dans un même bloc, pour ne jamais être séparés par un retour à la ligne
  document.querySelectorAll('#bar .seg[data-k]').forEach(g=>{const t=lib[g.dataset.k];if(!t||g.parentElement.classList.contains("groupe-reg"))return;
    const w=document.createElement("span");w.className="groupe-reg";const sp=document.createElement("span");sp.className="lbl-reg";sp.textContent=t;sp.id="lbl-"+g.dataset.k;
    g.setAttribute("aria-labelledby",sp.id);g.before(w);w.append(sp,g)});
  document.querySelectorAll("#bar .groupe-reg").forEach(w=>{const g=w.querySelector(".seg");w.hidden=!g||g.classList.contains("hidden")})}
function choixProfession(){intitulesReglages();const sel=document.getElementById("prof");choixListe(sel,"prof",sel);choixStructures();listesEncadres();rappelReglages()}
// les listes des encadrés prennent la même forme que le choix de la profession, au lieu de la liste blanche du système
// (remarque de Lucas du 23 octobre 2026) ; la liste du navigateur reste cachée et garde l'état, si bien qu'un choix
// redessine la figure par le même chemin, points qui glissent compris
function listesEncadres(){document.querySelectorAll("section[data-p] select:not(#lieuxType)").forEach(sel=>{if(!sel.id||!sel.options.length)return;
  if(!sel.classList.contains("natif")){sel.classList.add("natif");sel.tabIndex=-1}
  const b=choixListe(sel,sel.id,sel);b.classList.add("dans-encadre");b.querySelector("button").setAttribute("aria-label",(sel.getAttribute("aria-label")||"Choix")+", "+(sel.selectedOptions[0]?.textContent||""))})}
// structures de soins, choisies dans la barre à côté des mesures et non plus sous la carte : elles servent aux points de
// la carte et à la mesure « Distance aux structures »
function choixStructures(){const sel=document.getElementById("lieuxType"),bar=document.getElementById("lieuxBar"),seg=document.getElementById("metricSeg");if(!sel||!seg)return;
  let g=document.getElementById("groupeStructures");
  if(!g){g=document.createElement("span");g.className="groupe-reg";g.id="groupeStructures";g.innerHTML='<span class="lbl-reg">Structures</span><span class="ancre"></span>';
    (seg.closest(".groupe-reg")||seg).after(g)}
  choixListe(sel,"lieux",g.querySelector(".ancre"));
  g.hidden=!bar||bar.hidden||seg.classList.contains("hidden");
  const r=document.getElementById("raisonsMesure");if(r&&g.nextElementSibling!==r)g.after(r)}
// figures qui apparaissent en douceur quand on arrive dessus ; la classe n'existe qu'avec le script
const REVELE=("IntersectionObserver" in window)?new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add("vu");REVELE.unobserve(e.target)}}),{rootMargin:"0px 0px -6% 0px"}):null;
if(REVELE)document.documentElement.classList.add("revele");
function revelerFigures(){if(!REVELE)return;document.querySelectorAll('.panel svg[role="img"]:not(.vu)').forEach(x=>REVELE.observe(x))}
// césure du texte justifié de l'onglet affiché, refaite après chaque rendu (le texte réécrit perd ses césures)
let CESURE_T=0;function cesureOnglet(){clearTimeout(CESURE_T);CESURE_T=setTimeout(()=>{if(window.cesure)window.cesure(document.querySelector('section[data-p]:not(.hidden)'))},120)}
function observerEtroits(){replierNotes();equilibrerPanneaux();choixProfession();revelerFigures();cesureOnglet();const ps=[...document.querySelectorAll(".panel")];ps.forEach(x=>ETROIT_RO.observe(x));
  // mesures d'abord, écritures ensuite, pour un seul calcul de mise en page
  const m=ps.map(x=>x.clientWidth);ps.forEach((x,i)=>{if(m[i])x.toggleAttribute("data-etroit",m[i]<340)});
  // paragraphe très étroit (moins de 22 cadratins par ligne) ; au-delà, la césure française permet le justifié
  const es=[...document.querySelectorAll("p,li,dd")].filter(e=>e.offsetParent),w=es.map(e=>e.clientWidth/parseFloat(getComputedStyle(e).fontSize));
  es.forEach((e,i)=>{if(w[i])e.toggleAttribute("data-etroit",w[i]<22)})}
function render(){
  hideTip();setTimeout(observerEtroits,0);setTimeout(observerEtroits,450);
  if(S.level==="reg"&&(!D.niveaux.reg||!["carte","tableau"].includes(S.tab))){S.level="dep";S.sel=null}
  syncBar();
  document.querySelectorAll("section[data-p]").forEach(s=>s.classList.toggle("hidden",s.dataset.p!==S.tab));
  if(S.tab==="carte"){lieuxOptions();drawMap();natCard();selCard();structuresTerritoire();lowerPanels();parcoursAtlas();listeCherche()}
  if(S.tab==="tableau"){table();accesLieux()}
  liensExplorerOnglets();
  if(S.tab==="croisements"){heatmap();effetVille();indicateursEntreEux();offreBesoin();gwrCarte();sommaireOnglet("croisements");setTimeout(()=>sommaireOnglet("croisements"),400)}
  if(S.tab==="sources")sources();
  if(S.tab==="comprendre")comprendre();
  normaliserEncadres();signer();
}
document.getElementById("tabs").addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;S.tab=b.dataset.t;document.querySelectorAll("#tabs button").forEach(x=>x.setAttribute("aria-selected",String(x===b)));render()});
document.querySelectorAll(".seg[data-k]").forEach(sg=>sg.addEventListener("click",e=>{const b=e.target.closest("button");if(!b||b.disabled)return;S[sg.dataset.k]=b.dataset.v;if(sg.dataset.k==="level"){S.sel=null;S.niveauAuto=false}if(sg.dataset.k==="vue"&&S.vue==="tuiles"&&S.level!=="dep"){S.level="dep";S.sel=null}if(sg.dataset.k==="fam"){S.sort=null;buildSelects()}render()}));
document.getElementById("prof").addEventListener("change",e=>{S.prof=e.target.value;render()});
document.getElementById("grp").addEventListener("change",e=>{S.grp=e.target.value;S.sort=null;table()});
document.getElementById("q").addEventListener("input",table);
// téléphone, bouton « Réglages » et rappel des choix en cours (niveau, mode, mesure)
{const bar=document.getElementById("bar"),bt=bar&&bar.querySelector(".reglages"),res=document.getElementById("reglagesResume");
  if(bt){bt.addEventListener("click",()=>{const o=!bar.classList.contains("ouvert");bar.classList.toggle("ouvert",o);bt.setAttribute("aria-expanded",String(o))});
    const maj=()=>{res.textContent=[...bar.querySelectorAll('.seg button[aria-pressed="true"]')].map(b=>b.textContent.trim()).join(" · ")};
    new MutationObserver(maj).observe(bar,{subtree:true,attributes:true,attributeFilter:["aria-pressed"]});maj()}}
const hautNav=()=>{const n=document.querySelector("nav.site"),c=document.querySelector(".collant"),h=n?n.offsetHeight:0;
  document.documentElement.style.setProperty("--haut-nav",h+"px");document.documentElement.style.setProperty("--haut-collant",(h+(c?c.offsetHeight:0))+"px")};hautNav();addEventListener("resize",hautNav);
{const c=document.querySelector(".collant");
  if(c){const r=document.createElement("div");r.id="rappelReglages";r.className="rappel-reglages";r.setAttribute("aria-label","Rappel des réglages");
    r.innerHTML='<span class="rr-prof"></span><span class="rr-texte"></span><button type="button" class="rr-ouvrir" aria-expanded="false">Réglages</button>';
    const place=document.createElement("div");place.className="place-collant";place.hidden=true;c.before(place);document.body.appendChild(r);
    const btn=r.querySelector(".rr-ouvrir");
    const fermer=()=>{if(!c.classList.contains("flotte"))return;c.classList.remove("flotte");place.hidden=true;btn.setAttribute("aria-expanded","false")};
    const ouvrir=()=>{place.style.height=c.offsetHeight+"px";place.hidden=false;c.classList.add("flotte");btn.setAttribute("aria-expanded","true")};
    btn.onclick=e=>{e.stopPropagation();c.classList.contains("flotte")?fermer():ouvrir()};
    document.addEventListener("keydown",e=>{if(e.key==="Escape"&&c.classList.contains("flotte")){fermer();btn.focus()}});
    document.addEventListener("click",e=>{if(c.classList.contains("flotte")&&!e.target.closest(".collant,.rappel-reglages,.prof-liste"))fermer()});
    // un onglet choisi depuis la fenêtre des réglages la referme et mène au haut de cet onglet
    document.getElementById("tabs")?.addEventListener("click",e=>{if(!e.target.closest("button")||!c.classList.contains("flotte"))return;
      setTimeout(()=>{fermer();window.scrollTo({top:c.getBoundingClientRect().top+scrollY-(document.querySelector("nav.site")?.offsetHeight||0),behavior:"instant"})},0)});
    let f=0;const maj=()=>{f=0;const n=document.querySelector("nav.site"),bas=n?n.getBoundingClientRect().bottom:0,ref=c.classList.contains("flotte")?place:c;
      const passe=ref.getBoundingClientRect().bottom<bas;r.classList.toggle("vu",passe);if(!passe)fermer()};
    addEventListener("scroll",()=>{if(!f)f=requestAnimationFrame(maj)},{passive:true});addEventListener("resize",maj);maj()}}
// texte du rappel, refait à chaque rendu
// une rangée n'est étirée jusqu'à la marge droite que si elle tient sur une ligne, sinon elle reste serrée à gauche
function ajusterRangees(){const bar=document.getElementById("bar");if(!bar)return;
  bar.classList.remove("plein");bar.querySelectorAll(".groupe-reg.plein").forEach(g=>g.classList.remove("plein"));
  const tete=[...bar.children].filter(c=>c.offsetParent&&!c.matches(".raisons-mesure,select,.reglages")&&getComputedStyle(c).position!=="absolute")
    .filter(c=>!c.querySelector("#metricSeg")&&c.id!=="groupeStructures");
  const hauts=tete.map(c=>Math.round(c.getBoundingClientRect().top));if(tete.length>1&&Math.max(...hauts)-Math.min(...hauts)<6)bar.classList.add("plein");
  const m=bar.querySelector(".groupe-reg:has(#metricSeg)");
  if(m&&m.offsetParent){const bs=[...m.querySelectorAll("#metricSeg button")].filter(b=>b.offsetParent).map(b=>Math.round(b.getBoundingClientRect().top));
    if(bs.length&&Math.max(...bs)-Math.min(...bs)<6){m.classList.add("plein");
      const apres=[...m.querySelectorAll("#metricSeg button")].filter(b=>b.offsetParent).map(b=>Math.round(b.getBoundingClientRect().top));
      if(Math.max(...apres)-Math.min(...apres)>=6)m.classList.remove("plein")}}}
addEventListener("resize",()=>requestAnimationFrame(ajusterRangees));
function rappelReglages(){ajusterRangees();const mt=document.getElementById("mapTitre"),mp=document.getElementById("map");if(mt&&mp)mt.textContent=titreElement(mp);
  const r=document.getElementById("rappelReglages");if(!r)return;
  const sel=document.getElementById("prof");if(sel)choixListe(sel,"prof-rappel",r.querySelector(".rr-prof"));
  const onglet=document.querySelector('#tabs [aria-selected="true"]')?.textContent.trim()||"";
  const choix=[...document.querySelectorAll('.collant .seg:not([data-k="vue"]):not(.hidden) button[aria-pressed="true"]')].filter(b=>b.offsetParent!==null||document.querySelector(".collant.flotte")).map(b=>b.textContent.trim());
  r.querySelector(".rr-texte").textContent=[onglet,...choix].filter(Boolean).join(" · ")}
document.addEventListener("click",e=>{const b=e.target.closest(".zoombar button");if(!b)return;zoomer(b.parentNode.dataset.carte==="tmap"?TM:M,b.dataset.z)});
document.querySelector("#tbl thead").addEventListener("click",e=>{const b=e.target.closest("button[data-s]");if(!b)return;if(S.sort===b.dataset.s)S.asc=!S.asc;else{S.sort=b.dataset.s;S.asc=b.dataset.s==="nm"}table()});
document.querySelector("#tbl tbody").addEventListener("click",e=>{const tr=e.target.closest("tr[data-c]");if(!tr)return;S.sel={lv:S.level,c:tr.dataset.c};S.tab="carte";document.querySelectorAll("#tabs button").forEach(x=>x.setAttribute("aria-selected",String(x.dataset.t==="carte")));render();window.scrollTo({top:0,behavior:"smooth"})});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change",render);
window.addEventListener("theme",()=>{M=null;TM=null;render()});
document.addEventListener("keydown",e=>{if(e.key==="Escape"&&S.sel&&S.tab==="carte"){S.sel=null;render()}});
normaliserEncadres();
// panneaux repliables sous la carte, ouverts sur grand écran et repliés sur téléphone, choix gardé par le navigateur
document.querySelectorAll("[data-repli]").forEach(p=>{const h=p.querySelector("h2"),cle="atlas-repli-"+p.dataset.repli,corps=document.createElement("div");
  let n=h.nextElementSibling;if(n&&n.classList.contains("howtxt"))n=n.nextElementSibling;
  while(n){const suivant=n.nextElementSibling;corps.appendChild(n);n=suivant}p.appendChild(corps);
  const b=document.createElement("button");b.type="button";b.className="repli";b.innerHTML='<span class="chevron" aria-hidden="true">▾</span>';
  b.appendChild(document.createTextNode(h.firstChild.textContent.trim()));h.replaceChild(b,h.firstChild);h.insertBefore(document.createTextNode(" "),b.nextSibling);
  let ouvert=innerWidth>760;try{const v=localStorage.getItem(cle);if(v!==null)ouvert=v==="1"}catch(e){}
  // encadré replié, sa phrase de lecture (résultat principal) reste visible sous le titre (audit du 22 octobre 2026)
  const res=document.createElement("p");res.className="resume-repli";h.after(res);
  const majRes=()=>{const ph=[...corps.querySelectorAll("p.phrase,p.note")].find(x=>x.textContent.trim());res.textContent=ph?ph.textContent.trim():"";res.hidden=ouvert||!res.textContent};
  let tRes=0;new MutationObserver(()=>{clearTimeout(tRes);tRes=setTimeout(majRes,60)}).observe(corps,{subtree:true,childList:true,characterData:true});
  const maj=()=>{b.setAttribute("aria-expanded",String(ouvert));corps.hidden=!ouvert;p.classList.toggle("replie",!ouvert);majRes()};maj();
  b.addEventListener("click",()=>{ouvert=!ouvert;try{localStorage.setItem(cle,ouvert?"1":"0")}catch(e){}maj()})});
// réglages lus dans l'adresse (#?fam=sm&prof=psychiatre&niv=dep), pour qu'un lien d'Explorer ouvre la carte de la
// même profession (lot 5, 28 octobre 2026) ; une valeur inconnue est ignorée
{const q=new URLSearchParams((location.hash.split("?")[1])||""),fam={sm:SM,sante:SANTE,tout:"*"}[q.get("fam")];
  if(fam)S.fam=fam;if(q.get("niv")&&["reg","dep","epci"].includes(q.get("niv")))S.level=q.get("niv");
  if(q.get("prof")&&(D.professions||[]).some(p=>p.id===q.get("prof")))S.prof=q.get("prof")}
prep();render();
