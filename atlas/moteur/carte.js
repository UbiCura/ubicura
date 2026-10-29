// Moteur de l'atlas, module « carte ». Fond de carte (Hexagone, Corse rapprochée, médaillons de l'outre-mer), projection,
// dessin des territoires d'un niveau, limites, zoom à la demande et signaux « ! » posés sur une carte.
// Dépend du noyau seulement. Un autre module ajoute ce qu'il veut au zoom par SUR_ZOOM, sans que la carte le connaisse.

// ---------- geometry
const W=960,H=800,DOMS=["971","972","973","974","976"];
const geom={epci:topojson.feature(topo,topo.objects.epci).features,dep:topojson.feature(topo,topo.objects.dep).features,reg:topo.objects.reg?topojson.feature(topo,topo.objects.reg).features:[]};
// régions d'outre-mer, un seul département chacune
const REG_DOM={"01":"971","02":"972","03":"973","04":"974","06":"976"};
const depOfFeat=(lv,f)=>lv==="dep"?f.properties.dep:lv==="reg"?(REG_DOM[f.properties.reg]||""):(IDX.epciDep?.get(f.properties.epci)||"");
// Sur la carte nationale seulement, la Corse est rapprochée du continent de 1,3 degré de longitude, à la même échelle
// (pratique courante des cartes de France). À sa place exacte, elle tenait le coin sud-est du cadre, collée au bord, et
// repoussait la France vers la gauche (remarque de Lucas du 28 octobre 2026). Les plans des territoires, les distances
// et les exports de données gardent les coordonnées réelles.
const CORSE=["2A","2B"],DLON_CORSE=1.3;
const estCorse=(lv,f)=>lv==="reg"?f.properties.reg==="94":CORSE.includes(depOfFeat(lv,f));
const decaler=g=>{const m=c=>typeof c[0]==="number"?[c[0]-DLON_CORSE,c[1]]:c.map(m);return {...g,coordinates:m(g.coordinates)}};
const metro=d3.geoConicConformal().parallels([44,49]).rotate([-3,0]).fitExtent([[180,14],[W-14,H-14]],{type:"FeatureCollection",
  features:geom.dep.filter(f=>f.properties.dep.length===2).map(f=>CORSE.includes(f.properties.dep)?{...f,geometry:decaler(f.geometry)}:f)});
// projection de la Corse, la même que le continent après le décalage (flux d3, rien n'est recopié)
const corseProj={stream:s=>{const t=metro.stream(s);return {point:(x,y)=>t.point(x-DLON_CORSE,y),sphere:()=>t.sphere(),
  lineStart:()=>t.lineStart(),lineEnd:()=>t.lineEnd(),polygonStart:()=>t.polygonStart(),polygonEnd:()=>t.polygonEnd()}}};
const boxes=DOMS.map((d,i)=>{const y=14+i*154;return{d,b:[[14,y+16],[164,y+142]]}});
const P={metro:d3.geoPath(metro),corse:d3.geoPath(corseProj)};
for(const b of boxes)P[b.d]=d3.geoPath(d3.geoMercator().fitExtent(b.b,{type:"FeatureCollection",features:geom.dep.filter(f=>f.properties.dep===b.d)}));
const pathOf=(lv,f)=>{const d=depOfFeat(lv,f);return(DOMS.includes(d)?P[d]:estCorse(lv,f)?P.corse:P.metro)(f)};
const keyOf=(lv,f)=>f.properties[lv];

// ce que d'autres modules ajoutent au zoom d'une carte (points des structures dans l'atlas), appelé avec la carte et
// l'événement
const SUR_ZOOM=[];
function mapInit(svgId){
  const svg=d3.select("#"+svgId);svg.selectAll("*").remove();
  const gi=svg.append("g");
  gi.selectAll("rect").data(boxes).join("rect").attr("class","inset").attr("x",d=>d.b[0][0]-6).attr("y",d=>d.b[0][1]-16).attr("width",162).attr("height",146).attr("rx",3);
  gi.selectAll("text").data(boxes).join("text").attr("x",d=>d.b[0][0]-1).attr("y",d=>d.b[0][1]-4).text(d=>IDX.depName?.get(d.d)||d.d);
  // l'Hexagone zoomé reste dans sa zone, à droite des médaillons d'outre-mer
  svg.append("defs").append("clipPath").attr("id",svgId+"-zone").append("rect").attr("x",174).attr("y",0).attr("width",W-174).attr("height",H);
  const zoomable=svg.append("g").attr("clip-path","url(#"+svgId+"-zone)").append("g"),fixe=svg.append("g");
  const Mx={svg,gi,zoomable,g:zoomable.append("g"),gd:zoomable.append("g"),gdom:fixe.append("g"),gddom:fixe.append("g"),gt:svg.append("g"),tuiles:false};
  // contour du territoire survolé, tracé par-dessus sans déplacer le territoire lui-même (déplacer l'élément sous la souris
  // fait perdre le survol et le clic au navigateur)
  Mx.survol=zoomable.append("path").attr("class","survol").style("display","none");Mx.survolDom=fixe.append("path").attr("class","survol").style("display","none");
  // zoom seulement à la demande (molette, boutons), jamais déclenché tout seul, un clic ne le change pas
  Mx.zoom=d3.zoom().scaleExtent([1,6]).translateExtent([[0,0],[W,H]]).clickDistance(4)
    .filter(ev=>!Mx.tuiles&&(ev.type==="wheel"?(ev.ctrlKey||ev.metaKey):(!ev.button&&ev.type!=="dblclick")))
    .on("zoom",ev=>{zoomable.attr("transform",ev.transform);svg.classed("zoome",ev.transform.k>1);hideTip();
      zoomable.selectAll("g.fragile").attr("transform",function(){return "translate("+this.dataset.x+","+this.dataset.y+") scale("+1/ev.transform.k+")"});
      SUR_ZOOM.forEach(f=>f(Mx,ev))});
  svg.call(Mx.zoom).on("dblclick.zoom",null);
  return Mx;
}
// dessine les territoires, l'Hexagone dans le groupe zoomable, l'outre-mer dans ses médaillons fixes
function joinUnites(Mx,lv,feats){const dom=f=>DOMS.includes(depOfFeat(lv,f)),cle=f=>lv+keyOf(lv,f);
  const a=Mx.g.selectAll("path.u").data(feats.filter(f=>!dom(f)),cle).join("path").attr("class","u").attr("d",f=>pathOf(lv,f));
  const b=Mx.gdom.selectAll("path.u").data(feats.filter(dom),cle).join("path").attr("class","u").attr("d",f=>pathOf(lv,f));
  return d3.selectAll([...a.nodes(),...b.nodes()])}
function bordures(Mx,feats){const dom=f=>DOMS.includes(f.properties.dep);
  Mx.gd.selectAll("path").data(feats.filter(f=>!dom(f))).join("path").attr("class","dep").attr("d",f=>pathOf("dep",f));
  Mx.gddom.selectAll("path").data(feats.filter(dom)).join("path").attr("class","dep").attr("d",f=>pathOf("dep",f))}
function zoomer(Mx,quoi){if(!Mx)return;const t=Mx.svg.transition().duration(matchMedia("(prefers-reduced-motion: reduce)").matches?0:250);
  if(quoi==="in")t.call(Mx.zoom.scaleBy,1.6);else if(quoi==="out")t.call(Mx.zoom.scaleBy,1/1.6);else t.call(Mx.zoom.transform,d3.zoomIdentity)}
// pose les symboles sur une carte, renvoie les signaux présents (pour la légende et les limites)
// contour ocre des territoires concernés et un seul symbole au centre du groupe, la couleur des territoires ne change pas
function signauxCarte(Mx,lv,suicide){Mx.svg.selectAll("g.fragile,path.fragile-contour").remove();const vus=new Set(),k0=d3.zoomTransform(Mx.svg.node()).k;
  [Mx.g,Mx.gdom].forEach(g=>{const cadres={};
    g.selectAll("path.u").each(function(f){if(!f)return;const k=fragile(lv,keyOf(lv,f),suicide);if(!k)return;
      g.append("path").attr("class","fragile-contour").attr("d",this.getAttribute("d")).attr("fill","none").attr("stroke",css("--signal"))
        .attr("stroke-width",1.6).attr("vector-effect","non-scaling-stroke").style("pointer-events","none");
      const b=this.getBBox(),c=cadres[k];cadres[k]=c?[Math.min(c[0],b.x),Math.min(c[1],b.y),Math.max(c[2],b.x+b.width),Math.max(c[3],b.y+b.height)]:[b.x,b.y,b.x+b.width,b.y+b.height]});
    for(const [k,[x0,y0,x1,y1]] of Object.entries(cadres)){vus.add(k);const x=(x0+x1)/2,y=(y0+y1)/2,s=symboleFragile(g,x,y,k,5.5);
      if(g===Mx.g&&k0>1)s.attr("transform","translate("+x+","+y+") scale("+1/k0+")")}});
  return [...vus]}
