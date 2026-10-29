// Moteur de l'atlas, module « croisements » (propre à l'atlas). Corrélations par groupe d'indicateurs, effet ville,
// offre et indicateur sur une même carte, lien local avec le niveau de vie, indicateurs entre eux, régressions,
// addictologie. « Croiser deux indicateurs » est dans le module « nuage », chargé par Explorer (lot 2 du 29 octobre 2026).
// Dépend du noyau et de la carte. La page qui le charge fournit render() (tout redessiner après un changement de
// niveau ou de profession), syncBar() (remettre les réglages affichés d'accord avec S) et ouvrirNuage() (ouvrir un
// croisement dans « Croiser deux indicateurs », dans Explorer), et les éléments de la page que les fonctions remplissent.
// encadré « Addictologie » (22 octobre 2026), même calcul que la partie du rapport santé mentale, régions rangées par
// ordre alphabétique et non par valeur (pas de palmarès)
function addictologie(){const A=D.addicto,P=document.getElementById("adPanel");if(!P)return;
  const vis=!!(A&&(A.ind.length||A.offre.length))&&S.fam!=="Santé";P.hidden=!vis;if(!vis)return;
  const f1=new Intl.NumberFormat("fr-FR",{maximumFractionDigits:1});
  document.getElementById("adTable").innerHTML='<thead><tr><th scope="col">Offre</th><th scope="col">Nombre</th><th scope="col">Précision</th></tr></thead><tbody>'
    +A.offre.map(r=>'<tr><td>'+esc(r.objet)+'</td><td>'+fmt.format(r.n)+'</td><td class="small muted">'+esc(r.note||"")+'</td></tr>').join("")+'</tbody>';
  document.getElementById("adPhrase").textContent=A.ind.length?"Selon les régions, "+A.ind.filter(i=>i.phrase).map(i=>{const v=Object.values(i.v).map(x=>x[0]);
    return i.phrase.replace("{min}",f1.format(d3.min(v))).replace("{max}",f1.format(d3.max(v))).replace("{annee}",i.annee)}).join(", ")+".":"";
  document.getElementById("adLimite").innerHTML=limiteHtml(["addictions"]);
  const svg=d3.select("#adPlot");svg.selectAll("*").remove();if(!A.ind.length)return;
  const codes=[...new Set(A.ind.flatMap(i=>Object.keys(i.v)))].filter(c=>A.regions[c]).sort((a,b)=>A.regions[a].localeCompare(A.regions[b],"fr"));
  const nomsR=cs=>cs.map(c=>A.regions[c]).sort((a,b)=>a.localeCompare(b,"fr")).join(", "),
    manques=A.ind.map(i=>Object.keys(A.regions).filter(c=>!(c in i.v))),commun=manques[0].filter(c=>manques.every(m=>m.includes(c))),
    notes=(commun.length?["Aucune mesure publiée pour "+nomsR(commun)+"."]:[]).concat(A.ind.map((i,j)=>[i,manques[j].filter(c=>!commun.includes(c))])
      .filter(([,m])=>m.length).map(([i,m])=>"« "+i.lib+" », pas de mesure publiée pour "+nomsR(m)+"."));
  // titres et unités coupés selon la place de chaque colonne à leur taille d'écran (normaliserTextes), la hauteur de
  // l'en-tête suit le plus long
  const W=900,pas=21,ecran=svg.node().getBoundingClientRect().width||W,k=W/Math.max(ecran,W*.9);
  const g0=Math.max(150,largeurLignes(svg,codes.map(c=>A.regions[c]))*k+14),larg=(W-g0-12)/A.ind.length;
  const fT=TYPO.texte*k,fP=TYPO.petit*k,ent=A.ind.map(i=>({t:coupeLib(i.lib,Math.floor((larg-20)/(fT*.58))),u:coupeLib(i.unite+", "+i.annee,Math.floor((larg-20)/(fP*.56)))}));
  const haut=d3.max(ent,e=>e.t.length*fT*1.3+e.u.length*fP*1.3)+14,bas=haut+pas*codes.length+34,h=bas+14*notes.length;svg.attr("viewBox","0 0 "+W+" "+h);
  codes.forEach((c,k)=>{const y=haut+pas*k+pas/2;
    if(k%2===0)svg.append("rect").attr("x",g0).attr("y",y-pas/2).attr("width",W-g0-12).attr("height",pas).attr("fill",css("--line")).attr("opacity",.25);
    svg.append("text").attr("x",g0-8).attr("y",y+4).attr("text-anchor","end").attr("font-size",11).attr("fill",css("--ink")).text(A.regions[c])});
  A.ind.forEach((ind,j)=>{const x0=g0+j*larg+10,x1=x0+larg-24,vals=Object.values(ind.v);
    const vmax=d3.max(vals,x=>Math.max(x[0],x[2]??x[0]))*1.05,X=d3.scaleLinear().domain([0,vmax]).nice(4).range([x0,x1]);
    const e=ent[j];
    e.t.forEach((t,l)=>svg.append("text").attr("x",(x0+x1)/2).attr("y",fT*1.1+fT*1.3*l).attr("text-anchor","middle").attr("font-size",11).attr("font-weight",600).attr("fill",css("--ink")).text(t));
    e.u.forEach((t,l)=>svg.append("text").attr("x",(x0+x1)/2).attr("y",fT*1.1+fT*1.3*e.t.length+fP*1.3*l).attr("text-anchor","middle").attr("font-size",10).attr("fill",css("--muted")).text(t));
    X.ticks(4).forEach(v=>{svg.append("line").attr("x1",X(v)).attr("x2",X(v)).attr("y1",haut).attr("y2",bas-34).attr("stroke",css("--line"));
      svg.append("text").attr("x",X(v)).attr("y",bas-18).attr("text-anchor","middle").attr("font-size",10).attr("fill",css("--muted")).text(f1.format(v))});
    const med=d3.median(vals,x=>x[0]);svg.append("line").attr("x1",X(med)).attr("x2",X(med)).attr("y1",haut).attr("y2",bas-34).attr("stroke",css("--muted")).attr("stroke-dasharray","3 3");
    codes.forEach((c,k)=>{const r=ind.v[c];if(!r)return;const y=haut+pas*k+pas/2;
      if(r[1]!=null&&r[2]!=null)svg.append("line").attr("x1",X(r[1])).attr("x2",X(r[2])).attr("y1",y).attr("y2",y).attr("stroke",css("--r3")).attr("stroke-width",2);
      svg.append("circle").attr("cx",X(r[0])).attr("cy",y).attr("r",4).attr("fill",css("--r5")).append("title").text(A.regions[c]+", "+f1.format(r[0])+(r[1]!=null?" (de "+f1.format(r[1])+" à "+f1.format(r[2])+")":""))})});
  ["Point, valeur de la région. Trait, fourchette (intervalle de confiance à 95 %). Pointillé, médiane des régions."].concat(notes)
    .forEach((t,k)=>svg.append("text").attr("x",12).attr("y",bas-3+14*k).attr("font-size",10).attr("fill",css("--muted")).text(t))}
// redessin quand la largeur de la figure change (encadré déplié, fenêtre redimensionnée), les titres en dépendent
const AD_RO=new ResizeObserver(es=>{const w=Math.round(es[0].contentRect.width);if(w&&w!==AD_RO.w){AD_RO.w=w;addictologie()}});
{const e=document.getElementById("adPlot");if(e)AD_RO.observe(e)}
// ---------- indicateurs entre eux (départements), liens d'un indicateur avec les autres, et régressions multiples
function indicateursEntreEux(){
  const T=D.croisements_indicateurs||[],ids=[...new Set(T.flatMap(r=>[r.a,r.b]))],lab=v=>(IDX.ctx.find(c=>c.id===v)||{label:v}).label;
  const sel=document.getElementById("indRef");
  if(!T.length){document.getElementById("indPhrase").textContent="Croisements absents de ce fichier de données.";return}
  if(!sel.options.length)sel.innerHTML=ids.map(v=>'<option value="'+v+'">'+esc(lab(v))+'</option>').join("");
  if(!S.indRef||!ids.includes(S.indRef))S.indRef=ids.includes("suicides")?"suicides":ids[0];sel.value=S.indRef;
  const ref=S.indRef,rows=T.filter(r=>r.a===ref||r.b===ref).map(r=>({v:r.a===ref?r.b:r.a,rho:r.rho,lo:r.lo,hi:r.hi,net:r.lo>0||r.hi<0})).sort((a,b)=>b.rho-a.rho);
  const svg=d3.select("#indPlot");svg.selectAll("*").remove();
  rows.forEach(r=>r.lignes=coupeLib(lab(r.v),40));
  const larg=largeurLignes(svg,rows.flatMap(r=>r.lignes)),hr=r=>Math.max(20,r.lignes.length*15+6);let cum=0;rows.forEach(r=>{r.y0=cum;r.hr=hr(r);cum+=r.hr});
  const ml=margeLibelles(svg,larg,560,330),m={l:ml.l,r:16,t:8,b:28},w=ml.w,h=m.t+m.b+cum;svg.attr("viewBox","0 0 "+w+" "+h);delete document.getElementById("indPlot").dataset.vbSigne;
  const x=d3.scaleLinear().domain([-1,1]).range([m.l,w-m.r]);
  grilleX(svg,x,m,h,5);
  svg.append("g").attr("transform","translate(0,"+(h-m.b)+")").call(d3.axisBottom(x).ticks(5).tickFormat(f1.format)).call(g=>g.selectAll("line,path").attr("stroke",css("--line")));
  svg.append("line").attr("x1",x(0)).attr("x2",x(0)).attr("y1",m.t).attr("y2",h-m.b).attr("stroke",css("--muted"));
  rows.forEach(r=>{const y0=m.t+r.y0,bh=r.hr,g=svg.append("g").style("cursor","pointer").on("click",()=>ouvrirNuage({x:ref,y:r.v,niveau:"dep"}));
    libelleMulti(g,m.l-8,y0+bh/2,r.lignes);
    g.append("rect").attr("x",Math.min(x(0),x(r.rho))).attr("width",Math.abs(x(r.rho)-x(0))).attr("y",y0+bh/2-6).attr("height",12).attr("fill",css(r.rho<0?"--d1":"--r4")).attr("opacity",r.net?1:.35);
    if(r.lo!=null)g.append("line").attr("x1",x(r.lo)).attr("x2",x(r.hi)).attr("y1",y0+bh/2).attr("y2",y0+bh/2).attr("stroke",css("--ink")).attr("stroke-opacity",.6);
    g.append("title").text(lab(ref)+" et "+lab(r.v)+", corrélation "+f2.format(r.rho)+(r.lo!=null?", fourchette plausible de "+f2.format(r.lo)+" à "+f2.format(r.hi):"")+(r.net?"":", lien incertain"))});
  const plus=rows.filter(r=>r.net&&r.rho>=.3).slice(0,3),moins=rows.filter(r=>r.net&&r.rho<=-.3).sort((a,b)=>a.rho-b.rho).slice(0,3);
  let ph="Entre départements, « "+minuscule(lab(ref))+" » a un lien net avec "+rows.filter(r=>r.net).length+" des "+rows.length+" autres indicateurs.";
  if(plus.length)ph+=" Il va surtout avec "+plus.map(r=>"« "+minuscule(lab(r.v))+" »").join(", ").replace(/, ([^,]*)$/," et $1")+".";
  if(moins.length)ph+=" Il va en sens inverse de "+moins.map(r=>"« "+minuscule(lab(r.v))+" »").join(", ").replace(/, ([^,]*)$/," et $1")+".";
  document.getElementById("indPhrase").textContent=ph+" Ces liens décrivent des départements et ne disent pas que l’un cause l’autre.";
  regressions();
}
// offre et indicateur sur une même carte (audit 4.2) et Moran local bivarié (2.5), par département
let BV=null,GW=null,GW_SUIVI=null;
const ZONES_BV={HL:["Indicateur élevé, offre faible alentour","--d1"],HH:["Indicateur élevé, offre élevée alentour","--r5"],
  LL:["Indicateur bas, offre faible alentour","--d3"],LH:["Indicateur bas, offre élevée alentour","--r2"]};
function tiersDe(v){const s=v.filter(x=>x!=null&&isFinite(x)).sort(d3.ascending),a=d3.quantile(s,1/3),b=d3.quantile(s,2/3);return x=>x==null||!isFinite(x)?null:x>b?2:x>a?1:0}
function offreBesoin(){
  const OB=D.offre_besoin,sel=document.getElementById("bvVar"),L=D.niveaux.dep,p=S.prof;
  if(!OB||!L){document.getElementById("bvPhrase").textContent="Données absentes de ce fichier.";return}
  const vars=OB.variables.filter(v=>IDX.ctx.find(c=>c.id===v));
  if(!sel.options.length){sel.innerHTML=vars.map(v=>'<option value="'+v+'">'+esc(IDX.ctx.find(c=>c.id===v).label)+'</option>').join("");sel.onchange=e=>{S.bvVar=e.target.value;offreBesoin();signer()}}
  if(!vars.includes(S.bvVar))S.bvVar=vars[0];sel.value=S.bvVar;
  const cx=IDX.ctx.find(c=>c.id===S.bvVar),exclus=new Set(["976"]);
  const dens=L.units.map((u,i)=>u.pop&&!exclus.has(u.c)?unitD("dep",p,i):null),ind=L.units.map(u=>exclus.has(u.c)||!u.x?null:u.x[cx.i]);
  const to=tiersDe(dens),tb=tiersDe(ind),zones=OB.zones&&OB.zones[p]?OB.zones[p][S.bvVar]:null,zb=document.querySelector('.seg[data-k="bvMode"] [data-v="zones"]');
  zb.disabled=!zones;if(!zones&&S.bvMode==="zones"){S.bvMode="tiers";syncBar()}
  const classe=i=>{const a=to(dens[i]),b=tb(ind[i]);return a==null||b==null?null:a*3+b};
  const couleur=i=>{if(S.bvMode==="zones"){const z=zones[L.units[i].c];return z&&ZONES_BV[z[0]]?css(ZONES_BV[z[0]][1]):css("--nodata")}const k=classe(i);return k==null?css("--nodata"):OB.palette[k]};
  if(!BV)BV=mapInit("bvmap");const ix=IDX.dep;
  joinUnites(BV,"dep",geom.dep).attr("fill",f=>{const i=ix.get(keyOf("dep",f));return i==null?css("--nodata"):couleur(i)})
    .on("mouseenter",function(){const h=this.parentNode===BV.g.node()?BV.survol:BV.survolDom;h.attr("d",this.getAttribute("d")).style("display",null)})
    .on("mousemove",(ev,f)=>{const i=ix.get(keyOf("dep",f));if(i==null)return;const u=L.units[i],z=zones?zones[u.c]:null;
      showTip(ev,'<strong>'+esc(u.nm)+'</strong><div class="tl">'+esc(profLab(p))+', '+(dens[i]==null?"non calculé":f2.format(dens[i])+' pour 10 000 hab.')+'</div><div class="tl">'+esc(cx.label)+', '+(ind[i]==null?"non disponible":f1.format(ind[i]))+'</div>'+(z&&ZONES_BV[z[0]]?'<div class="tl">'+ZONES_BV[z[0]][0]+'</div>':""))})
    .on("mouseleave",()=>{BV.survol.style("display","none");BV.survolDom.style("display","none");hideTip()}).on("click",null);
  const n=k=>L.units.filter((u,i)=>classe(i)===k).length,pl=pluriel(profLab(p));
  let ph;
  if(S.bvMode==="zones"){const cpt=t=>Object.values(zones||{}).filter(z=>z[0]===t).length,hl=cpt("HL");
    const nz=Object.values(zones||{}).filter(z=>z[0]!=="non_significatif").length;
    ph=!nz?"Aucun département ne forme, au-delà du hasard, une zone où cet indicateur et l’offre des départements voisins s’écartent ensemble de la moyenne.":
      (hl?"Au-delà du hasard, "+hl+" département"+(hl>1?"s ont":" a")+" un indicateur élevé entouré de départements où l’offre est faible. ":"Aucun département n’a, au-delà du hasard, un indicateur élevé entouré d’une offre faible. ")+nz+" zone"+(nz>1?"s":"")+" en tout se distingue"+(nz>1?"nt":"")+" du hasard.";
    document.getElementById("bvLegende").innerHTML=Object.entries(ZONES_BV).map(([k,[t,c]])=>'<span><i style="display:inline-block;width:12px;height:12px;background:'+css(c)+';margin-right:6px"></i>'+t+'</span>').join("")+'<span><i style="display:inline-block;width:12px;height:12px;background:'+css("--nodata")+';margin-right:6px"></i>Pas de zone nette</span>'}
  else{ph=n(2)+" départements ont à la fois un indicateur « "+minuscule(cx.label)+" » dans le tiers le plus haut et une densité de "+pl+" dans le tiers le plus bas (en rouge). "+n(6)+" sont dans la situation inverse (en bleu).";
    document.getElementById("bvLegende").innerHTML='<div class="grille" aria-hidden="true">'+[2,1,0].map(b=>[0,1,2].map(o=>'<i style="background:'+OB.palette[o*3+b]+'"></i>').join("")).join("")+'</div><span>Vers la droite, plus de '+esc(pl)+'. Vers le haut, « '+esc(minuscule(cx.label))+' » plus élevé.</span>'}
  document.getElementById("bvPhrase").textContent=ph+" Ces cartes décrivent des départements et ne disent rien d’une cause.";
  const sigBv=signauxCarte(BV,"dep",S.bvVar==="suicides");
  if(sigBv.length)document.getElementById("bvLegende").innerHTML+='<div class="legende-signaux">'+legendeSignaux(sigBv)+'</div>';
  document.getElementById("bvLimite").innerHTML=limiteHtml([S.bvVar,"prof:"+p,...sigBv],[]);
  document.getElementById("bvNote").textContent="Tiers calculés sur les départements, Mayotte écartée (population de référence incertaine). Zones, Moran local bivarié, indicateur du département rapproché de la densité moyenne de ses voisins (densité en logarithme), 999 permutations, correction de Benjamini-Hochberg au seuil de 5 %. Les zones ne sont calculées que pour les psychiatres, les psychologues, les psychiatres qualifiés pour l’enfant et les généralistes. Détail dans offre_besoin_lisa.csv.";
}
// lien local entre niveau de vie et densité, régression géographiquement pondérée (audit 2.6)
function gwrCarte(){
  const G=D.gwr,sel=document.getElementById("gwProf"),L=D.niveaux.epci;
  if(!G){document.getElementById("gwPhrase").textContent="Données absentes de ce fichier.";return}
  if(!sel.options.length){sel.innerHTML=Object.keys(G).map(p=>'<option value="'+p+'">'+esc(cap(pluriel(profLab(p))))+'</option>').join("");sel.onchange=e=>{S.gwProf=e.target.value;gwrCarte();signer()}}
  // la carte suit la profession choisie en haut de la page quand le calcul existe pour elle, et garde sinon le choix
  // fait dans l'encadré (remarque de Lucas du 23 octobre 2026, la carte ne changeait pas avec la profession)
  if(G[S.prof]&&S.prof!==GW_SUIVI)S.gwProf=S.prof;GW_SUIVI=S.prof;
  if(!G[S.gwProf])S.gwProf=Object.keys(G)[0];sel.value=S.gwProf;
  const liste=Object.keys(G).map(p=>pluriel(profLab(p))),dispo=document.getElementById("gwDispo");
  dispo.textContent=G[S.prof]?"":"Ce calcul est fait pour les professions présentes dans au moins une intercommunalité sur deux, pas pour les "+pluriel(profLab(S.prof))+", trop rares pour un lien local. Profession montrée ici :";
  dispo.hidden=!!G[S.prof];choixListe(sel,"gwProf",sel).hidden=!!G[S.prof];
  const g=G[S.gwProf],r=g.resume,dv=DIV(),cls=v=>v==null?null:!v[1]?2:v[0]>0?(v[0]>=.3?4:3):(v[0]<=-.3?0:1);
  const cols=[dv[0],dv[1],css("--d3"),dv[dv.length-2],dv[dv.length-1]],labs=["négatif net, fort","négatif net","pas de lien net","positif net","positif net, fort"];
  if(!GW)GW=mapInit("gwrmap");const ix=IDX.epci;
  joinUnites(GW,"epci",geom.epci).attr("fill",f=>{const i=ix.get(keyOf("epci",f)),k=i==null?null:cls(g.coef[i]);return k==null?css("--nodata"):cols[k]})
    .on("mouseenter",function(){const h=this.parentNode===GW.g.node()?GW.survol:GW.survolDom;h.attr("d",this.getAttribute("d")).style("display",null)})
    .on("mousemove",(ev,f)=>{const i=ix.get(keyOf("epci",f));if(i==null)return;const u=L.units[i],v=g.coef[i];
      showTip(ev,'<strong>'+esc(u.nm)+'</strong><div class="tl">'+(v==null?"Hors du calcul (outre-mer ou donnée manquante)":"Lien local "+(v[1]?(v[0]>0?"positif":"négatif")+" et net":"sans lien net")+", coefficient "+f2.format(v[0]))+'</div>')})
    .on("mouseleave",()=>{GW.survol.style("display","none");GW.survolDom.style("display","none");hideTip()}).on("click",null);
  bordures(GW,geom.dep);
  document.getElementById("gwLegende").innerHTML=labs.map((t,k)=>'<span style="display:inline-flex;align-items:center;gap:4px"><span style="width:12px;height:12px;background:'+cols[k]+'"></span>'+t+'</span>').join("");
  const pl=pluriel(profLab(S.gwProf)),varie=r.p_variation_niveau_de_vie<.05;
  document.getElementById("gwPhrase").textContent="À densité de population égale, le lien entre le niveau de vie et la densité de "+pl+(varie?" change nettement d’une région à l’autre. ":" ne change pas nettement d’une région à l’autre. ")
    +"Il est positif et net dans "+Math.round(r.part_positif_net*100)+" % des intercommunalités, négatif et net dans "+Math.round(r.part_negatif_net*100)+" %, sans lien net ailleurs. Il décrit des territoires et ne dit rien d’une cause.";
  document.getElementById("gwNote").textContent="Régression géographiquement pondérée du logarithme de la densité sur le niveau de vie médian et le logarithme de la densité de population, variables centrées et réduites, "+fmt.format(r.intercommunalites)+" intercommunalités. Noyau bicarré adaptatif à "+r.voisines+" voisines, choisi par le critère AICc ("+fmt.format(Math.round(r.aicc_gwr))+" contre "+fmt.format(Math.round(r.aicc_ols))+" pour la régression ordinaire, plus bas est meilleur). Coefficient global "+f2.format(r.coef_global_niveau_de_vie)+", coefficients locaux de "+f2.format(r.coef_local_q1)+" à "+f2.format(r.coef_local_q3)+" pour la moitié centrale. Tests locaux au seuil ajusté de da Silva et Fotheringham (2016). Test de variation spatiale par 49 permutations des positions, p = "+f2.format(r.p_variation_niveau_de_vie)+". Détail dans gwr_coefficients.csv et gwr_resume.csv.";
}
const NOMS_RES={suicides:"le taux de décès par suicide",hospit_gestes_auto_infliges:"le taux d’hospitalisation pour geste auto-infligé",ald_23:"la part de personnes en ALD psychiatrique"};
function regressions(){
  const T=D.regressions||[],res=[...new Set(T.map(r=>r.res))],lab=v=>(IDX.ctx.find(c=>c.id===v)||{label:v}).label,sel=document.getElementById("regRes");
  if(!T.length){document.getElementById("regPhrase").textContent="Régressions absentes de ce fichier de données.";return}
  if(!sel.options.length)sel.innerHTML=res.map(v=>'<option value="'+v+'">'+esc(cap(NOMS_RES[v]||lab(v)))+'</option>').join("");
  if(!S.regRes||!res.includes(S.regRes))S.regRes=res[0];sel.value=S.regRes;
  const g=T.filter(r=>r.res===S.regRes&&r.champ==="hexagone"),sans=new Map(T.filter(r=>r.res===S.regRes&&r.champ!=="hexagone").map(r=>[r.var,r]));
  const svg=d3.select("#regPlot");svg.selectAll("*").remove();
  g.forEach(r=>r.lignes=coupeLib(lab(r.var),36));
  const larg=largeurLignes(svg,g.flatMap(r=>r.lignes)),bh=Math.max(36,d3.max(g,r=>r.lignes.length)*15+10);
  const ml=margeLibelles(svg,larg,520,300),m={l:ml.l,r:16,t:8,b:28},w=ml.w,h=m.t+m.b+g.length*bh;svg.attr("viewBox","0 0 "+w+" "+h);delete document.getElementById("regPlot").dataset.vbSigne;
  const lim=Math.max(.8,d3.max(g,r=>Math.max(Math.abs(r.lo),Math.abs(r.hi)))*1.1),x=d3.scaleLinear().domain([-lim,lim]).range([m.l,w-m.r]);
  grilleX(svg,x,m,h,6);
  svg.append("g").attr("transform","translate(0,"+(h-m.b)+")").call(d3.axisBottom(x).ticks(6).tickFormat(f1.format)).call(gg=>gg.selectAll("line,path").attr("stroke",css("--line")));
  svg.append("line").attr("x1",x(0)).attr("x2",x(0)).attr("y1",m.t).attr("y2",h-m.b).attr("stroke",css("--muted"));
  g.forEach((r,k)=>{const y0=m.t+k*bh+bh/2,net=r.lo>0||r.hi<0,c=css(r.b<0?"--d1":"--r4");
    libelleMulti(svg,m.l-8,y0,r.lignes);
    svg.append("line").attr("x1",x(r.lo)).attr("x2",x(r.hi)).attr("y1",y0-4).attr("y2",y0-4).attr("stroke",c).attr("stroke-width",2).attr("opacity",net?1:.45);
    svg.append("circle").attr("cx",x(r.b)).attr("cy",y0-4).attr("r",5).attr("fill",c).attr("opacity",net?1:.45).append("title").text(lab(r.var)+", "+f2.format(r.b)+", fourchette de "+f2.format(r.lo)+" à "+f2.format(r.hi));
    const s=sans.get(r.var);if(s){svg.append("line").attr("x1",x(s.lo)).attr("x2",x(s.hi)).attr("y1",y0+6).attr("y2",y0+6).attr("stroke",css("--muted")).attr("stroke-width",1.2);
      svg.append("path").attr("d",d3.symbol(d3.symbolDiamond,40)()).attr("transform","translate("+x(s.b)+","+(y0+6)+")").attr("fill",css("--muted")).append("title").text("Sans l’Île-de-France, "+f2.format(s.b))}});
  const nom=NOMS_RES[S.regRes]||lab(S.regRes),plus=g.filter(r=>r.lo>0).map(r=>"« "+minuscule(lab(r.var))+" »"),moins=g.filter(r=>r.hi<0).map(r=>"« "+minuscule(lab(r.var))+" »");
  const et=l=>l.length<2?l.join(""):l.slice(0,-1).join(", ")+" et "+l[l.length-1];
  let ph="À autres indicateurs égaux, "+nom+" est "+[plus.length?"plus élevé dans les départements où "+valeursReg(plus):"",moins.length?"plus bas dans ceux où "+valeursReg(moins):""].filter(Boolean).join(", et ")+".";
  if(!plus.length&&!moins.length)ph="À autres indicateurs égaux, aucun de ces indicateurs n’est nettement lié à "+nom+".";
  ph+=" Ensemble, ils résument "+Math.round((g[0]?.r2||0)*100)+" % des écarts entre départements. Un coefficient peut différer du lien simple, car il retire ce que les autres indicateurs expliquent déjà.";
  document.getElementById("regPhrase").textContent=ph;
  // lien qui n'existe qu'à autres indicateurs égaux, effet de compensation entre deux indicateurs liés (même règle que le rapport)
  const fl=new Map(g.filter(r=>(r.lo>0||r.hi<0)&&r.dep&&r.rho!=null&&r.bsans!=null&&(Math.abs(r.rho)<.2||Math.sign(r.rho)!==Math.sign(r.b))&&Math.abs(r.bsans)<Math.abs(r.b)/2).map(r=>[r.var,r]));
  const comp=[],vus=new Set();
  fl.forEach((r,v)=>{if(vus.has(v))return;const nv=minuscule(lab(v)),nw=minuscule(lab(r.dep)),o=fl.get(r.dep);
    if(o&&o.dep===v){vus.add(v);vus.add(r.dep);comp.push("Les liens avec « "+nv+" » et « "+nw+" » n’apparaissent qu’ensemble. Pris seuls, ils sont faibles (rho = "+f2.format(r.rho)+" et "+f2.format(o.rho)+"). Ces deux indicateurs vont souvent de pair, et le modèle compare des départements où l’un est plus élevé que ne le laisserait attendre l’autre. Aucun des deux ne doit être lu comme un effet propre.")}
    else{vus.add(v);comp.push("Le lien avec « "+nv+" » n’apparaît qu’à autres indicateurs égaux. Pris seul, il est faible"+(Math.sign(r.rho)!==Math.sign(r.b)?" et de sens contraire":"")+" (rho = "+f2.format(r.rho)+"). Cet indicateur va souvent de pair avec « "+nw+" », et sans ce dernier le coefficient tombe à "+f2.format(r.bsans)+". Le modèle compare donc des départements où « "+nv+" » est plus élevé ou plus bas que ne le laisserait attendre « "+nw+" ». Ce lien ne doit pas être lu comme un effet propre de « "+nv+" ».")}});
  document.getElementById("regCompense").textContent=comp.join(" ");
  document.getElementById("regLimite").innerHTML=limiteHtml([S.regRes],[]);
}
const HM_PRINC={[SM]:["psychologue","psychiatre","pedopsychiatre","q_psychiatrie_enfant","psychotherapeute"],[SANTE]:["medecin_generaliste","infirmier","masseur_kinesitherapeute","orthophoniste","pediatre","sage_femme","chirurgien_dentiste","pharmacien"]};
// un cadre par groupe d'indicateurs (demande de Lucas du 12 octobre 2026), chacun avec son titre, « Comment lire »,
// « Citer et exporter » et son tableau, professions en colonnes, indicateurs du groupe en lignes
function heatmap(){
  const lv=S.level,toutes=D.professions.filter(p=>inFam(p)&&natOf(p)!=="perimetre_elargi"&&natN(p.id,"all")>=30);
  const princ=new Set([...(S.fam!==SANTE?HM_PRINC[SM]:[]),...(S.fam!==SM?HM_PRINC[SANTE]:[])]);
  const profs=S.hmTout?toutes:toutes.filter(p=>princ.has(p.id));
  let corr=(D.correlations||[]).filter(r=>r.niv===lv&&r.mode===S.mode);
  const get=new Map(corr.map(r=>[r.prof+"|"+r.var,r]));
  const L=D.niveaux[lv];
  const dv=DIV(),sc=d3.scaleLinear().domain([-.6,-.3,-.1,0,.1,.3,.6]).range(dv).clamp(true);
  const cols=ctxVisibles().filter(c=>ctxDispo(lv,c));
  const groupes=[...new Set(cols.map(c=>c.groupe||"Profil de la population"))];
  const nivLab={reg:"régions",dep:"départements",epci:"intercommunalités"}[lv]||lv;
  const tete='<thead><tr><th>Indicateur</th>'+profs.map(p=>'<th>'+coupureMots(esc(p.libelle))+'</th>').join("")+'</tr></thead>';
  const cadres=document.getElementById("hmCadres"),liens=[];
  cadres.innerHTML="";
  groupes.forEach((g,gi)=>{
    const cg=cols.filter(c=>(c.groupe||"Profil de la population")===g);
    let h=tete+'<tbody>',fort=null;
    for(const c of cg){
      h+='<tr><td class="ind" title="'+esc((c.explication||"")+(c.source?" Source, "+c.source+".":""))+'">'+esc(c.label)+'</td>';
      for(const p of profs){
        let r=get.get(p.id+"|"+c.id),rho,q;
        if(r){rho=r.rho;q=r.q}else if(L.units[0].x){const s=spearman(L.units.map(u=>u.x[c.i]),L.units.map((u,i)=>unitD(lv,p.id,i)));rho=s.rho;q=null}
        const incertain=(q!=null&&q>=.05)||(r&&r.lo!=null&&r.lo<0&&r.hi>0);
        if(rho!=null&&!isNaN(rho)&&!incertain&&(!fort||Math.abs(rho)>Math.abs(fort.rho)))fort={rho,p:p.libelle,c:c.label};
        const tt=rho==null||isNaN(rho)?"":p.libelle+" et "+c.label+", rho "+f2.format(rho)+(r&&r.lo!=null?", fourchette plausible de "+f2.format(r.lo)+" à "+f2.format(r.hi):"")+(incertain?", lien incertain":"");
        h+='<td data-p="'+p.id+'" data-x="'+c.id+'" title="'+esc(tt)+'" style="'+styleCase(rho==null||isNaN(rho)?null:sc(rho),incertain)+'">'+(rho==null||isNaN(rho)?"":f2.format(rho))+'</td>';
      }
      h+='</tr>';
    }
    h+='</tbody>';
    const id="hm"+gi,pan=document.createElement("div");pan.className="panel pad";pan.id="cadre-"+id;
    TABLEAUX[id]=()=>"Liens entre l’offre de soins et les indicateurs, "+g+", "+famLab[S.fam]+", "+nivLab;
    pan.innerHTML='<h2>Corrélations, '+esc(g)+' <button class="how" data-how="correlation,force,q">Comment lire</button></h2><div class="howtxt hidden"></div>'
      +'<p class="note" style="margin:0 0 8px">'+cg.length+' indicateur'+(cg.length>1?"s":"")+', '+nivLab+', '+(S.mode==="all"?"tous modes d’exercice":S.mode==="lib"?"exercice libéral":"exercice salarié")+'.'
      +(fort?' Lien le plus net du groupe, '+esc(fort.p.toLowerCase())+' et '+esc(minLib(fort.c))+' ('+f2.format(fort.rho)+').':' Aucun lien net dans ce groupe.')+'</p>'
      +(toutes.length>profs.length||S.hmTout?'<div class="hmbar"><button class="btn ghost hmtout" type="button">'+(S.hmTout?"Professions principales seulement":"Afficher toutes les professions de la famille ("+toutes.length+")")+'</button></div>':'')
      +'<div class="hmbox"><table class="hm" id="'+id+'" style="table-layout:fixed;min-width:'+(210+profs.length*80)+'px"><colgroup><col style="width:210px"></colgroup>'+h+'</table></div>';
    cadres.appendChild(pan);
    liens.push('<li><button type="button" data-cadre="cadre-'+id+'">'+esc(g)+'</button> <span>'+cg.length+' indicateur'+(cg.length>1?"s":"")+'</span></li>');
    const b=pan.querySelector(".hmbox");b.addEventListener("scroll",()=>majDefil(b),{passive:true});
    // défilement horizontal seulement si le tableau dépasse la fenêtre, sinon aucun défilement interne
    requestAnimationFrame(()=>b.classList.toggle("defile-x",b.scrollWidth>b.clientWidth+1));const tb=b.querySelector("table");tb.dataset.observe=1;DEFIL.observe(tb);
  });
  document.getElementById("hmLiens").innerHTML=liens.join("");
  document.querySelectorAll("#hmLiens button").forEach(b=>b.onclick=()=>document.getElementById(b.dataset.cadre).scrollIntoView({behavior:"smooth",block:"start"}));
  cadres.querySelectorAll("button.hmtout").forEach(b=>b.onclick=()=>{const y=b.closest(".panel").getBoundingClientRect().top;const id=b.closest(".panel").id;S.hmTout=!S.hmTout;heatmap();normaliserEncadres();signer();
    // le cadre cliqué reste sous les yeux après le changement
    const n=document.getElementById(id);if(n)window.scrollBy(0,n.getBoundingClientRect().top-y)});
  // une case ouvre son croisement dans « Croiser deux indicateurs » (profession, indicateur, niveau gardé) ; la case
  // se signale au survol et au clavier (remarque de Lucas du 23 octobre 2026, partir de ce qui ressort)
  const ouvrirCase=td=>ouvrirNuage({prof:td.dataset.p,x:td.dataset.x,y:""});
  cadres.querySelectorAll("td[data-p]").forEach(td=>{if(!td.textContent)return;td.tabIndex=0;td.classList.add("ouvrable");
    td.title=(td.title?td.title+". ":"")+"Cliquer pour voir ce croisement dans le nuage";
    td.onclick=()=>ouvrirCase(td);td.onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();ouvrirCase(td)}}});
}

// ---------- effet ville (corrélation brute et à densité de population égale)
function effetVille(){
  const lv=S.level,p=S.prof,lab=profLab(p),svg=d3.select("#effetVille");svg.selectAll("*").remove();
  document.getElementById("evReglages").textContent="La figure suit les choix faits en haut de la page, ici les "+pluriel(lab)+", "
    +({dep:"par département",epci:"par intercommunalité"}[lv]||"")+", "+modeLab[S.mode]+". Chaque ligne met en regard un indicateur du profil des habitants et la densité de ces professionnels. "
    +"La barre foncée tient égale une seule chose, la densité de population (habitants au kilomètre carré), pour comparer des territoires aussi urbains les uns que les autres. Les autres indicateurs ne sont pas tenus égaux entre eux, chacun est regardé seul, et le lien ne dit rien d’une cause.";
  const rows=(D.correlations||[]).filter(r=>r.niv===lv&&r.mode===S.mode&&r.prof===p&&r.var!=="densite_pop"&&r.rho!=null)
    .map(r=>({...r,lab:(IDX.ctx.find(c=>c.id===r.var)||{}).label||r.var})).sort((a,b)=>Math.abs(b.rho)-Math.abs(a.rho));
  if(!rows.length||rows.every(r=>r.rp==null)){svg.append("text").attr("x",10).attr("y",30).text("Ces liens ne sont pas calculés pour ce choix. Essayez un autre mode d’exercice ou une autre profession en haut de la page.");document.getElementById("evPhrase").textContent="";document.getElementById("evSynthese").textContent="";return}
  // les 15 indicateurs les plus liés d'abord, les autres sur demande
  const total=rows.length,EV_MAX=15,bEv=document.getElementById("evTout");
  bEv.hidden=total<=EV_MAX;bEv.textContent=S.evTout?"Afficher les "+EV_MAX+" indicateurs les plus liés":"Afficher les "+total+" indicateurs";
  const tous=rows.slice();if(!S.evTout)rows.splice(EV_MAX);
  // libellés longs sur plusieurs lignes, marge gauche calculée d'après la ligne la plus longue, rien n'est coupé
  const coupe=(t,max)=>{const l=[];let c="";for(const mot of t.split(" ")){if(c&&(c+" "+mot).length>max){l.push(c);c=mot}else c=c?c+" "+mot:mot}if(c)l.push(c);return l};
  rows.forEach(r=>r.lignes=coupe(r.lab,46));
  // marge mesurée à la taille d'écran des libellés et convertie comme eux (margeLibelles)
  const larg=largeurLignes(svg,rows.flatMap(r=>r.lignes))||200;
  const bh=13,haut=r=>Math.max(2*bh+8,r.lignes.length*15+10);let cum=0;rows.forEach(r=>{r.y0=cum;cum+=haut(r)});
  const ml=margeLibelles(svg,larg,900,520),m={l:Math.max(ml.l,160),r:20,t:10,b:30},w=Math.max(ml.w,m.l+520),h=m.t+m.b+cum;svg.attr("viewBox","0 0 "+w+" "+h);
  const x=d3.scaleLinear().domain([-.8,.8]).range([m.l,w-m.r]).clamp(true);
  svg.append("g").attr("transform","translate(0,"+(h-m.b)+")").call(d3.axisBottom(x).ticks(8).tickFormat(f1.format)).call(g=>g.selectAll("line,path").attr("stroke",css("--line")));
  svg.append("line").attr("x1",x(0)).attr("x2",x(0)).attr("y1",m.t).attr("y2",h-m.b).attr("stroke",css("--muted"));
  [-.3,.3].forEach(v=>svg.append("line").attr("x1",x(v)).attr("x2",x(v)).attr("y1",m.t).attr("y2",h-m.b).attr("stroke",css("--line")).attr("stroke-dasharray","3 3"));
  rows.forEach(r=>{const y0=m.t+r.y0,n=r.lignes.length,t=svg.append("text").attr("x",m.l-8).attr("y",y0+bh+4-(n-1)*7.5).attr("text-anchor","end");
    r.lignes.forEach((l,i)=>t.append("tspan").attr("x",m.l-8).attr("dy",i?15:0).text(l));
    [[r.rho,css("--r2")],[r.rp,css("--r5")]].forEach(([v,c],j)=>{if(v==null)return;svg.append("rect").attr("x",Math.min(x(0),x(v))).attr("width",Math.abs(x(v)-x(0))).attr("y",y0+j*bh).attr("height",bh-2).attr("fill",c).append("title").text((j?"À densité de population égale ":"Tous territoires ")+f2.format(v))})});
  const avant=tous.filter(r=>Math.abs(r.rho)>=.3),apres=tous.filter(r=>r.rp!=null&&Math.abs(r.rp)>=.3);
  const plus=tous.filter(r=>r.rp!=null).sort((a,b)=>(Math.abs(b.rho)-Math.abs(b.rp))-(Math.abs(a.rho)-Math.abs(a.rp)))[0];
  let ph=avant.length?"Pour les "+pluriel(lab)+", "+avant.length+" indicateur"+(avant.length>1?"s sont liés":" est lié")+" au moins modérément à leur densité. Entre territoires de même densité de population, "+(apres.length>avant.length?"il y en a "+apres.length+", car retirer l’effet ville fait aussi apparaître des liens qu’il masquait.":"il en reste "+apres.length+"."):"Aucun indicateur n’est lié au moins modérément à la densité "+deMot(pluriel(lab))+".";
  if(plus&&Math.abs(plus.rho)-Math.abs(plus.rp)>.1)ph+=" Le lien le plus touché par l’effet ville est « "+plus.lab.toLowerCase()+" », qui passe de "+f2.format(plus.rho)+" à "+f2.format(plus.rp)+".";
  document.getElementById("evPhrase").textContent=ph;
  // synthèse en langage simple, sous le graphique, sans interprétation causale
  const nom=r=>"« "+minuscule(r.lab.replace(/ \(ALD \d+\)$/,""))+" »";
  const nets=tous.filter(r=>r.rp!=null&&Math.abs(r.rp)>=.3&&!(r.lp!=null&&r.lp<0&&r.hp>0)).sort((a,b)=>Math.abs(b.rp)-Math.abs(a.rp));
  const effaces=tous.filter(r=>r.rp!=null&&Math.abs(r.rho)>=.3&&Math.abs(r.rp)<.15).sort((a,b)=>Math.abs(b.rho)-Math.abs(a.rho));
  let sy="Ce que cela veut dire. Les villes réunissent à la fois beaucoup de professionnels et des habitants au profil différent (âge, diplôme, revenus, façon de se loger). Une partie des liens du graphique vient seulement de là.";
  const et=l=>l.length<2?l.join(""):l.slice(0,-1).join(", ")+" et "+l[l.length-1];
  if(nets.length){const hauts=nets.slice(0,4).filter(r=>r.rp>0).map(nom),bas=nets.slice(0,4).filter(r=>r.rp<0).map(nom),morceaux=[];
    if(hauts.length)morceaux.push("plutôt plus "+deMot(pluriel(lab))+" là où "+et(hauts)+(hauts.length>1?" sont élevés":" est élevé"));
    if(bas.length)morceaux.push((hauts.length?"et plutôt moins":"plutôt moins "+deMot(pluriel(lab)))+" là où "+et(bas)+(bas.length>1?" sont élevés":" est élevé"));
    sy+=" Une fois cet effet retiré, on compte encore "+morceaux.join(", ")+". Ce constat ne tient donc pas seulement à la taille des villes."}
  else sy+=" Une fois cet effet retiré, aucun lien ne reste au moins modéré, les écarts tenaient donc pour l’essentiel à la taille des villes.";
  if(effaces.length)sy+=" À l’inverse, "+(effaces.length===1?"le lien avec "+nom(effaces[0])+" s’efface presque, il tenait":"les liens avec "+effaces.slice(0,3).map(nom).join(", ").replace(/, ([^,]*)$/," et $1")+" s’effacent presque, ils tenaient")+" surtout à l’effet ville.";
  sy+=" Dans tous les cas, ces liens décrivent des territoires et ne disent pas que l’un cause l’autre.";
  document.getElementById("evSynthese").textContent=sy;
  document.getElementById("evNote").textContent="Corrélation partielle de rang, les rangs de l’indicateur et de la densité de professionnels sont corrigés de leur relation linéaire avec le rang de la densité de population. Intervalles à 95 % par bootstrap pour les principales professions, correction de Benjamini-Hochberg propre aux corrélations partielles. "+tous.filter(r=>r.rp!=null).map(r=>r.lab+" "+f2.format(r.rp)+(r.lp!=null?" (de "+f2.format(r.lp)+" à "+f2.format(r.hp)+")":"")).join(", ")+".";
}
document.getElementById("indRef").addEventListener("change",e=>{S.indRef=e.target.value;indicateursEntreEux();signer()});
document.getElementById("regRes").addEventListener("change",e=>{S.regRes=e.target.value;regressions();signer()});

document.getElementById("evTout").addEventListener("click",()=>{S.evTout=!S.evTout;effetVille();signer()});
