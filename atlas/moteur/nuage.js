// Moteur de l'atlas, module « nuage » (lot 2 du 29 octobre 2026). « Croiser deux indicateurs », nuage des territoires,
// données par territoire et questions préparées entre bases (config.CROISEMENTS). Chargé par Explorer seulement,
// qui le réunit au noyau et à la carte (pipeline/explorer.py) avec son adaptateur gabarits/explorer_croisements.js.
// Dépend du noyau et de la carte. La page fournit render(), syncBar() et les éléments que les fonctions remplissent.
// croisements entre bases par département (config.CROISEMENTS), mêmes règles de lecture que les rapports
function phraseCroisement(r){
  const net=r.lo>0||r.hi<0,netp=r.rp!=null&&(r.lop>0||r.hip<0);
  const brut=net?"le lien est "+forceLien(r.rho)+" (rho = "+f2.format(r.rho)+")":"aucun lien net n’apparaît (rho = "+f2.format(r.rho)+", fourchette de "+f2.format(r.lo)+" à "+f2.format(r.hi)+")";
  const dens=r.rp==null?"":net&&netp?", et "+forceLien(r.rp)+" à densité de population égale (rho = "+f2.format(r.rp)+")":net?", mais il disparaît à densité de population égale (rho = "+f2.format(r.rp)+")":netp?", mais un lien "+forceLien(r.rp)+" apparaît à densité de population égale (rho = "+f2.format(r.rp)+")":", ni à densité de population égale (rho = "+f2.format(r.rp)+")";
  return "Entre « "+minuscule(r.x)+" » et « "+minuscule(r.y)+" », "+brut+dens+"."}
// questions préparées entre bases (config.CROISEMENTS), chargées d'un clic dans « Croiser deux indicateurs » (demande
// de Lucas du 23 octobre 2026 : la fenêtre à part enfermait la lecture dans ces questions, l'outil permet d'en croiser
// d'autres) ; la question en cours est soulignée et sa phrase reprend fourchette et lien à densité égale
let CB_T=[];
const cleCb=k=>String(k||"").replace(/^ctx:/,"");
function croisementCourant(){if(S.level!=="dep")return null;
  const x=S.xvar,y=S.yvar?S.yvar:(S.mode==="lib"?"dens_lib:":S.mode==="all"?"dens:":"?:")+S.prof;
  return CB_T.find(r=>{const a=cleCb(r.xk),b=cleCb(r.yk);return (a===x&&b===y)||(a===y&&b===x)})||null}
function appliquerCroisement(r){let a=cleCb(r.xk),b=cleCb(r.yk);const dens=k=>/^dens(_lib)?:/.test(k);if(dens(a))[a,b]=[b,a];
  if(!IDX.ctx.find(c=>c.id===a))return;
  S.level="dep";S.xvar=a;
  if(dens(b)){S.yvar="";S.prof=b.split(":")[1];S.mode=b.startsWith("dens_lib:")?"lib":"all"}else S.yvar=b;
  ["xvar","yvar","prof"].forEach(id=>{const e=document.getElementById(id);if(e)e.value=id==="xvar"?S.xvar:id==="yvar"?(S.yvar||""):S.prof});
  render();signer();
  requestAnimationFrame(()=>{const p=document.getElementById("scatter").closest(".panel,.fenetre");
    window.scrollTo({top:p.getBoundingClientRect().top+scrollY-hautFixe()-16,behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth"})})}
function croisementsBases(){
  const T=(D.croisements_bases||[]).filter(r=>S.fam==="*"||r.famille===S.fam),boite=document.getElementById("scSuggestions");CB_T=T;
  if(!boite)return;
  if(!T.length){boite.innerHTML="";document.getElementById("cbTable").innerHTML="";return}
  const qs=[...new Set(T.map(r=>r.theme))],cur=croisementCourant();
  {const X=v=>66+v*60,mini=x=>{const net=x.lo>0||x.hi<0,c=net?css("--r4"):css("--muted");
      return '<svg viewBox="0 0 132 16" aria-hidden="true"><line x1="6" x2="126" y1="8" y2="8" stroke="'+css("--line")+'"/><line x1="66" x2="66" y1="2" y2="14" stroke="'+css("--muted")+'" stroke-width="1"/>'
        +'<line x1="'+X(Math.max(-1,x.lo))+'" x2="'+X(Math.min(1,x.hi))+'" y1="8" y2="8" stroke="'+c+'" stroke-width="2" stroke-linecap="round"/>'
        +'<circle cx="'+X(x.rho)+'" cy="8" r="4.5" fill="'+(net?c:css("--panel"))+'" stroke="'+c+'" stroke-width="1.6"/></svg>'};
    boite.innerHTML='<h3>Questions préparées</h3><p class="note">Un clic charge la question dans le nuage, par département. Pour ces questions, chaque lien porte sa fourchette plausible, sa valeur à densité de population égale et la correction pour tests multiples. Un croisement choisi librement donne un coefficient descriptif quand il n’a pas été calculé à l’avance.</p>'
      +'<div class="cb-axe"><span></span><span><span>−1</span><span>0</span><span>+1</span></span><span style="text-align:right">rho</span></div>'
      +qs.map(t=>{const g=T.filter(x=>x.theme===t),q=(g.find(x=>x.question)||{}).question||"";
        return '<div class="cb-q">'+esc(q)+'</div>'+g.map(x=>{const k=T.indexOf(x);
          return '<button type="button" class="cb-ligne'+(x===cur?' on':'')+'" data-cb="'+k+'" aria-label="'+esc(phraseCroisement(x))+'"><span>'+esc(x.x+" et "+minuscule(x.y))+'</span>'+mini(x)+'<span class="rho">'+f2.format(x.rho)+'</span></button>'}).join("")}).join("")}
  // une ligne de titre par question, puis un croisement par ligne, le lien écrit en mots avec sa valeur
  const motLien=(v,lo,hi)=>lo!=null&&lo<=0&&hi>=0?"incertain":forceLien(v);
  document.getElementById("cbTable").innerHTML='<thead><tr><th>Croisement</th><th>Lien entre départements</th><th>Fourchette plausible</th><th>À densité de population égale</th><th class="num">Départements</th></tr></thead><tbody>'
    +qs.map(t=>{const g=T.filter(x=>x.theme===t),q=(g.find(x=>x.question)||{}).question||"";
      return '<tr class="cb-titre"><th colspan="5">'+esc(q)+'</th></tr>'+g.map(x=>'<tr><td>'+esc(x.x)+'<br><span class="muted">et '+esc(minuscule(x.y))+'</span></td>'
        +'<td>'+motLien(x.rho,x.lo,x.hi)+' ('+f2.format(x.rho)+')</td><td>de '+f2.format(x.lo)+' à '+f2.format(x.hi)+'</td>'
        +'<td>'+(x.rp==null?"non calculé":motLien(x.rp,x.lop,x.hip)+' ('+f2.format(x.rp)+')')+'</td><td class="num">'+x.n+'</td></tr>').join("")}).join("")+'</tbody>';
}
// données du nuage, par territoire, triables, filtrables et téléchargeables
const SC={tri:"nm",asc:true};
let SC_NIVEAU=null;
function tableNuage(lv,cx,p,pts,cy){
  const lab=profLab(p),q=(document.getElementById("scFiltre").value||"").trim().toLowerCase();
  const val=d=>SC.tri==="nm"?d.u.nm:SC.tri==="pop"?d.u.pop:SC.tri==="x"?d.x:d.y;
  let rows=pts.filter(d=>!q||d.u.nm.toLowerCase().includes(q)).sort((a,b)=>{const A=val(a),B=val(b);return(typeof A==="string"?A.localeCompare(B,"fr"):A-B)*(SC.asc?1:-1)});
  const th=(k,t)=>'<th><button data-s="'+k+'" class="'+(SC.tri===k?"on":"")+'">'+esc(t)+(SC.tri===k?(SC.asc?" ▲":" ▼"):"")+'</button></th>';
  const fx=v=>cx.unite==="€"?fmt.format(Math.round(v)):f1.format(v);
  document.getElementById("scTable").innerHTML='<thead><tr>'+th("nm",lv==="dep"?"Département":"Intercommunalité")+th("pop","Habitants")+th("x",cx.label+(cx.unite?" ("+cx.unite+")":""))+th("y",cy?cy.label+(cy.unite?" ("+cy.unite+")":""):cap(pluriel(lab))+", pour 10 000 hab.")+'</tr></thead><tbody>'
    +rows.map(d=>'<tr><td>'+esc(d.u.nm)+'</td><td>'+fmt.format(d.u.pop)+'</td><td>'+fx(d.x)+'</td><td>'+(cy?(cy.unite==="€"?fmt.format(Math.round(d.y)):f1.format(d.y)):f2.format(d.y))+'</td></tr>').join("")+'</tbody>';
  document.querySelectorAll("#scTable th button").forEach(b=>b.onclick=()=>{const k=b.dataset.s;if(SC.tri===k)SC.asc=!SC.asc;else{SC.tri=k;SC.asc=k==="nm"}tableNuage(lv,cx,p,pts,cy)});
  // données complètes du nuage (codes, valeurs non arrondies), exportées par « Citer et exporter »
  EXPORT_CSV.scTable=()=>({titre:"Données du nuage, "+cx.label+" et "+(cy?minuscule(cy.label):pluriel(lab))+", par "+(lv==="dep"?"département":"intercommunalité"),nom:cx.id+"_"+(cy?cy.id:p)+"_"+lv,
    texte:[["code","territoire","habitants",cx.id,cy?cy.id:"densite_"+p].join(";")].concat(pts.slice().sort((a,b)=>a.u.nm.localeCompare(b.u.nm,"fr")).map(d=>[d.u.c,'"'+d.u.nm.replace(/"/g,'""')+'"',d.u.pop,String(d.x).replace(".",","),String(Math.round(d.y*1e4)/1e4).replace(".",",")].join(";"))).join("\r\n")});
}
function scatter(){
  const lv=S.level,L=D.niveaux[lv],p=S.prof,cx=IDX.ctx.find(c=>c.id===S.xvar),cy=S.yvar?IDX.ctx.find(c=>c.id===S.yvar):null;
  const svg=d3.select("#scatter");
  // positions d'avant, pour que les points glissent vers leur nouvelle place quand on change d'indicateur, de profession
  // ou d'échelle (comme dans le prototype validé par Lucas le 23 octobre 2026), au même niveau seulement
  const avant=new Map();if(SC_NIVEAU===S.level)svg.selectAll("g.points circle").each(function(d){if(d&&d.u)avant.set(d.u.c,[+this.getAttribute("cx"),+this.getAttribute("cy")])});
  SC_NIVEAU=S.level;svg.selectAll("*").remove();
  document.querySelector('.seg[data-k="ylog"]').hidden=!!cy;
  if(!cx||!L.units[0].x){svg.append("text").attr("x",20).attr("y",40).text("Indicateurs de contexte absents du fichier.");return}
  if(!ctxDispo(lv,cx)){svg.append("text").attr("x",20).attr("y",40).text("Cet indicateur n’existe qu’au niveau des départements. Choisissez « Départements » en haut de la page.");document.getElementById("scPhrase").textContent="";document.getElementById("scLimite").innerHTML="";document.getElementById("xvarNote").textContent=cx.explication||"";document.getElementById("scNote").textContent="";return}
  const pts=L.units.map((u,i)=>({u,i,x:u.x[cx.i],y:cy?u.x[cy.i]:unitD(lv,p,i)})).filter(d=>d.x!=null&&d.y!=null&&d.u.pop>0);
  if(cy&&!pts.length){svg.append("text").attr("x",20).attr("y",40).text("Ces deux indicateurs n’existent pas ensemble à ce niveau. Choisissez « Départements ».");document.getElementById("scPhrase").textContent="";document.getElementById("scLimite").innerHTML="";return}
  const m={l:52,r:14,t:30,b:44},w=560,h=420;
  const xs=(cx.id==="densite_pop"?d3.scaleLog().domain(d3.extent(pts.filter(d=>d.x>0),d=>d.x)):d3.scaleLinear().domain(d3.extent(pts,d=>d.x))).nice().range([m.l,w-m.r]);
  const yl=!cy&&S.ylog==="1",ypos=pts.map(d=>d.y).filter(v=>v>0);
  // en logarithmique, l'axe suit les valeurs observées (un peu de marge) au lieu d'être arrondi aux puissances de 10,
  // sinon les points se tassent au milieu et le graphique ressemble à l'échelle linéaire
  const logSerre=(a,b)=>d3.scaleLog().domain([(a||.01)/1.15,(b||1)*1.15]);
  const ys=(yl?logSerre(d3.min(ypos),d3.max(ypos)):cy?(cy.id==="densite_pop"?d3.scaleLog().domain(d3.extent(pts.filter(d=>d.y>0),d=>d.y)).nice():d3.scaleLinear().domain(d3.extent(pts,d=>d.y)).nice()):d3.scaleLinear().domain([0,d3.max(pts,d=>d.y)||1]).nice()).range([h-m.b,m.t]);
  const rs=d3.scaleSqrt().domain([0,d3.max(pts,d=>d.u.pop)]).range([1.5,lv==="dep"?14:9]);
  const gx=svg.append("g").attr("transform","translate(0,"+(h-m.b)+")").call(d3.axisBottom(xs).tickValues(graduations(xs,6,46)).tickFormat(nbAxe)).call(g=>g.selectAll("line,path").attr("stroke",css("--line")));
  const gG=svg.append("g");grille(gG,ys,m,w,6);
  const gy=svg.append("g").attr("transform","translate("+m.l+",0)").call(d3.axisLeft(ys).tickValues(graduations(ys,6,24)).tickFormat(nbAxe)).call(g=>g.selectAll("line,path").attr("stroke",css("--line")));
  svg.append("clipPath").attr("id","scClip").append("rect").attr("x",m.l).attr("y",m.t-6).attr("width",w-m.l-m.r).attr("height",h-m.t-m.b+6);
  svg.append("text").attr("x",w-m.r).attr("y",h-6).attr("text-anchor","end").text(cx.label+(cx.unite?" ("+cx.unite+")":""));
  const ylab=cy?cy.label+(cy.unite?" ("+cy.unite+")":""):profLab(p)+", pour 10 000 hab."+(yl?" (log)":"");
  svg.append("text").attr("x",m.l).attr("y",12).text(ylab);
  const box=document.getElementById("scatter");
  const ptsC=svg.append("g").attr("class","points").attr("clip-path","url(#scClip)").selectAll("circle").data(pts.filter(d=>!yl||d.y>0)).join("circle")
    .attr("cx",d=>(avant.get(d.u.c)||[xs(Math.max(d.x,xs.domain()[0]))])[0]).attr("cy",d=>(avant.get(d.u.c)||[0,ys(d.y)])[1]).attr("r",d=>rs(d.u.pop))
    .attr("fill",d=>S.sel&&S.sel.c===d.u.c?css("--accent"):css("--r4")).attr("fill-opacity",.55).attr("stroke",css("--panel")).attr("stroke-width",.4);
  ptsC.append("title").text(d=>d.u.nm+"\n"+cx.label+" "+f1.format(d.x)+"\n"+(cy?cy.label:profLab(p))+" "+f1.format(d.y));
  // le glissement part après le dessin des autres figures de l'onglet, sinon le temps de ce dessin mange l'animation
  // (changement de profession, toutes les figures sont refaites d'un bloc)
  if(avant.size)requestAnimationFrame(()=>ptsC.transition().duration(480).ease(d3.easeCubicOut).attr("cx",d=>xs(Math.max(d.x,xs.domain()[0]))).attr("cy",d=>ys(d.y)));
  // signaux « donnée fragile », posés sur le point sans en changer la couleur
  const suiSc=[cx.id,cy&&cy.id].includes("suicides"),gSc=svg.append("g").attr("clip-path","url(#scClip)");
  pts.filter(d=>(!yl||d.y>0)&&fragile(lv,d.u.c,suiSc)).forEach(d=>symboleFragile(gSc,xs(Math.max(d.x,xs.domain()[0])),ys(d.y),fragile(lv,d.u.c,suiSc),4.5));
  const sigSc=[...new Set(pts.map(d=>fragile(lv,d.u.c,suiSc)).filter(Boolean))],legSc=sigSc.length?'<p class="legende-signaux">'+legendeSignaux(sigSc)+'</p>'+limiteHtml(sigSc):"";
  // le territoire choisi sur la carte est nommé dans le nuage
  const choisi=S.sel&&pts.find(d=>d.u.c===S.sel.c&&(!yl||d.y>0));
  let etiq=null;
  if(choisi){const cx0=xs(Math.max(choisi.x,xs.domain()[0])),cy0=ys(choisi.y),adroite=cx0<w-160;
    etiq=svg.append("text").attr("x",cx0+(adroite?9:-9)).attr("y",cy0-8).attr("text-anchor",adroite?"start":"end").attr("font-weight",600).attr("fill",css("--ink")).text(choisi.u.nm)}
  // quadrants offre et besoin, pour un indicateur de santé mentale au niveau départemental
  let quad="",quadListe="",medX=null,medY=null;
  if(lv==="dep"&&cx.famille&&!cy){
    // Mayotte écartée des croisements entre départements, comme dans les rapports
    const pq=pts.filter(d=>!(D.meta.exclus_croisements||["976"]).includes(d.u.c));
    const mx=d3.median(pq,d=>d.x),my=d3.median(pq,d=>d.y);medX=mx;medY=Math.max(my,yl?ys.domain()[0]:0);
    svg.append("line").attr("class","med-x").attr("x1",xs(mx)).attr("x2",xs(mx)).attr("y1",m.t).attr("y2",h-m.b).attr("stroke",css("--accent")).attr("stroke-dasharray","4 3");
    svg.append("line").attr("class","med-y").attr("x1",m.l).attr("x2",w-m.r).attr("y1",ys(Math.max(my,yl?ys.domain()[0]:0))).attr("y2",ys(Math.max(my,yl?ys.domain()[0]:0))).attr("stroke",css("--accent")).attr("stroke-dasharray","4 3");
    const crit=pq.filter(d=>d.x>mx&&d.y<=my);
    quad=" Lignes pointillées, médianes des départements, en bas à droite un indicateur élevé et une offre faible. "+crit.length+" départements ont un indicateur au-dessus de la médiane et une densité "+deMot(pluriel(profLab(p)))+" au-dessous. Cette position par rapport aux médianes ne mesure pas une insuffisance au sens d’une norme.";
    quadListe='<details class="plus"><summary>Liste de ces '+crit.length+' départements, par ordre alphabétique</summary><div class="scroll"><table><tr><th>Département</th><th>'+esc(cx.label)+'</th><th>'+esc(profLab(p))+', pour 10 000 hab.</th></tr>'+crit.slice().sort((a,b)=>a.u.nm.localeCompare(b.u.nm,"fr")).map(d=>'<tr><td>'+esc(d.u.nm)+'</td><td>'+f1.format(d.x)+'</td><td>'+f2.format(d.y)+'</td></tr>').join("")+'</table></div></details>';
  }
  // zoom du nuage (remarque de Lucas du 23 octobre 2026, l'échelle se dérèglait) : les axes et la grille se
  // recalculent au lieu d'agrandir l'image ; boutons + et −, Ctrl et molette, glisser pour se déplacer une fois zoomé
  {const fx=d=>Math.max(d.x,xs.domain()[0]),dedans=v=>v>=m.l-1&&v<=w-m.r+1;
    const zoomer=t=>{const X=t.rescaleX(xs),Y=t.rescaleY(ys),trait=g=>g.selectAll("line,path").attr("stroke",css("--line"));
      gx.call(d3.axisBottom(X).tickValues(graduations(X,6,46)).tickFormat(nbAxe)).call(trait);
      gy.call(d3.axisLeft(Y).tickValues(graduations(Y,6,24)).tickFormat(nbAxe)).call(trait);
      gG.selectAll("*").remove();grille(gG,Y,m,w,6);
      ptsC.interrupt().attr("cx",d=>X(fx(d))).attr("cy",d=>Y(d.y));
      gSc.selectAll("*").remove();pts.filter(d=>(!yl||d.y>0)&&fragile(lv,d.u.c,suiSc)).forEach(d=>symboleFragile(gSc,X(fx(d)),Y(d.y),fragile(lv,d.u.c,suiSc),4.5));
      if(etiq&&choisi){const a=X(fx(choisi)),b=Y(choisi.y);etiq.attr("x",a+(a<w-160?9:-9)).attr("y",b-8).attr("text-anchor",a<w-160?"start":"end").style("display",dedans(a)&&b>=m.t&&b<=h-m.b?null:"none")}
      if(medX!=null){const a=X(medX),b=Y(medY);svg.select("line.med-x").attr("x1",a).attr("x2",a).style("display",dedans(a)?null:"none");svg.select("line.med-y").attr("y1",b).attr("y2",b).style("display",b>=m.t&&b<=h-m.b?null:"none")}};
    const zm=d3.zoom().scaleExtent([1,12]).extent([[m.l,m.t],[w-m.r,h-m.b]]).translateExtent([[m.l,m.t],[w-m.r,h-m.b]])
      .filter(ev=>ev.type==="wheel"?(ev.ctrlKey||ev.metaKey):(!ev.button&&ev.type!=="dblclick")).on("zoom",ev=>zoomer(ev.transform));
    svg.property("__zoom",d3.zoomIdentity).call(zm).on("dblclick.zoom",null);
    // les boutons de zoom vont dans un cadre autour de la figure, jamais en tête de la fenêtre (le titre doit rester
    // le premier élément pour former la barre de titre, remarque de Lucas du 23 octobre 2026)
    let hote=box.parentElement;if(!hote.classList.contains("sc-hote")){const w=document.createElement("div");w.className="sc-hote";box.before(w);w.appendChild(box);hote=w;
      const vieux=w.parentElement.querySelector(":scope > .sc-zoom");if(vieux)vieux.remove()}
    let zb=hote.querySelector(":scope > .sc-zoom");
    if(!zb){zb=document.createElement("div");zb.className="zoombar sc-zoom";zb.setAttribute("role","group");zb.setAttribute("aria-label","Zoom du nuage");
      zb.innerHTML='<button type="button" data-z="in" aria-label="Zoomer">+</button><button type="button" data-z="out" aria-label="Dézoomer">−</button><button type="button" data-z="reset" aria-label="Revenir à la vue entière">⟲</button>';
      if(getComputedStyle(hote).position==="static")hote.style.position="relative";hote.prepend(zb)}
    zb.onclick=e=>{const b=e.target.closest("button");if(!b)return;e.stopPropagation();const t=svg.transition().duration(250);
      if(b.dataset.z==="reset")t.call(zm.transform,d3.zoomIdentity);else t.call(zm.scaleBy,b.dataset.z==="in"?1.6:1/1.6)}}
  const s=spearman(pts.map(d=>d.x),pts.map(d=>d.y));
  const pre=(D.correlations||[]).find(r=>r.niv===lv&&r.mode===S.mode&&r.prof===p&&r.var===cx.id);
  const zeros=pts.filter(d=>d.y===0).length;
  const rho=pre&&pre.rho!=null?pre.rho:s.rho;
  let sens="";const se=lv==="dep"&&(D.sensibilite||[]).find(r=>r.prof===p&&r.var===cx.id);
  if(se&&se.sans!=null){const incertain=pre&&pre.lo!=null&&pre.lo<0&&pre.hi>0;
    sens=" Sans les départements d’Île-de-France, où les suicides sont sous-déclarés, la corrélation vaut "+f2.format(se.sans)+(incertain&&Math.abs(se.sans)<=Math.abs(se.rho)?", ce qui ne change pas ce constat.":Math.sign(se.sans)===Math.sign(se.rho)&&forceLien(se.sans)===forceLien(se.rho)?", le constat reste le même.":", le lien est alors "+forceLien(se.sans)+".")}
  if(cy){
    // deux indicateurs entre eux, corrélation publiée (départements) ou calculée ici
    const pc=lv==="dep"&&(D.croisements_indicateurs||[]).find(r=>(r.a===cx.id&&r.b===cy.id)||(r.a===cy.id&&r.b===cx.id));
    document.getElementById("scPhrase").textContent=phraseDeux(pc?pc.rho:s.rho,pc?[pc.lo,pc.hi]:null,cx.label,cy.label,lv)
      +(pc&&pc.sans!=null&&[cx.id,cy.id].some(v=>/suicide|geste/.test(v))?" Sans les départements d’Île-de-France, où les suicides sont sous-déclarés, la corrélation vaut "+f2.format(pc.sans)+".":"");
    document.getElementById("scLimite").innerHTML=limiteHtml([cx.id,cy.id],[])+legSc;
  }else{
  document.getElementById("scPhrase").textContent=phraseCorrelation(rho,cx.label,profLab(p),pre&&pre.rho!=null?[pre.lo,pre.hi]:null)+sens+quad;
  document.getElementById("scLimite").innerHTML=limiteHtml([cx.id,"prof:"+p])+legSc+quadListe;}
  document.getElementById("xvarNote").innerHTML=(S.niveauAuto&&lv==="dep"?"<strong>Nuage affiché par département</strong>, seul niveau où cet indicateur est publié. ":"")+esc(cx.explication?cx.label+". "+cx.explication+" ":"")+(cx.source?"Source, "+lienFiche(cx)+". ":"")+esc("Chaque point est un territoire, sa taille est proportionnelle à la population."+(yl&&zeros?" "+fmt.format(zeros)+" territoires sans professionnel ne figurent pas en échelle logarithmique.":""));
  tableNuage(lv,cx,p,pts,cy);signer();
  {const cr=croisementCourant();document.getElementById("scPhrase").hidden=!!cr;document.getElementById("scPrepare").textContent=cr?"Question préparée, « "+cr.question.replace(/\s*\?$/," ?")+" » "+phraseCroisement(cr):"";
    document.querySelectorAll("#scSuggestions [data-cb]").forEach(b=>b.classList.toggle("on",CB_T[+b.dataset.cb]===cr))}
  document.getElementById("scNote").textContent="Corrélation de rang de Spearman rho = "+f2.format(s.rho)+" sur "+fmt.format(s.n)+" territoires"+(pre&&pre.lo!=null?", intervalle de confiance à 95 % par bootstrap de "+f2.format(pre.lo)+" à "+f2.format(pre.hi):"")+(pre&&pre.q!=null?", q de Benjamini-Hochberg "+(pre.q<.001?"inférieure à 0,001":"égale à "+f2.format(pre.q)):"")+". Le lien peut tenir pour une large part à l’effet ville, qu’une corrélation à densité de population égale permettra de corriger.";
}
// un indicateur publié seulement par département fait passer le nuage à ce niveau, sans autre action
function niveauPourNuage(){
  const cs=[S.xvar,S.yvar].filter(Boolean).map(id=>IDX.ctx.find(c=>c.id===id)).filter(Boolean);
  if(S.level!=="dep"&&cs.some(c=>!ctxDispo(S.level,c)&&ctxDispo("dep",c))){S.level="dep";S.sel=null;S.niveauAuto=true;render()}
  else scatter();
  signer()}
document.getElementById("xvar").addEventListener("change",e=>{S.xvar=e.target.value;niveauPourNuage()});
document.getElementById("yvar").addEventListener("change",e=>{S.yvar=e.target.value;niveauPourNuage()});
document.getElementById("scSuggestions")?.addEventListener("click",e=>{const b=e.target.closest("[data-cb]");if(b&&CB_T[+b.dataset.cb])appliquerCroisement(CB_T[+b.dataset.cb])});
document.getElementById("scFiltre").addEventListener("input",()=>scatter());

