// Moteur de l'atlas, module « structures » (propre à l'atlas). Structures de soins sur la carte, niveau de confirmation,
// encadré « Structures de soins de ce territoire », plan du territoire et fond Plan IGN.
// Dépend du noyau, de la carte et de la page de l'atlas (drawMap, render).
// ---------- structures de soins (FINESS et ROR réunis sans double compte), points posés sur la carte sans en changer les
// couleurs. Un clic repère le lieu et affiche sa fiche sous la carte, sans zoom (règle du 5 octobre 2026).
const LX=D.lieux||null;
let LIEU_CHOISI=null;
// niveau de confirmation de chaque structure (pipeline/confirmation.py), point creux pour une structure inscrite dans
// FINESS ou le ROR que rien d'autre ne confirme encore, point plein sinon (décision de Lucas du 15 octobre 2026)
const CONF=LX?.confirmations||[],CONF_BASES=CONF.findIndex(c=>c.id==="bases");
// trois classes montrées au lecteur (décision de Lucas du 21 octobre 2026), confirmée (point plein), recoupée par la SAE
// (point à demi rempli, le nombre ou l'activité du site est confirmé, pas l'adresse), à vérifier (point creux)
const classeDe=d=>d[11]!=null?(CONF[d[11]]?.classe||null):null;
const creux=d=>classeDe(d)==="a_verifier",recoupe=d=>classeDe(d)==="recoupee",confirme=d=>classeDe(d)==="confirmee";
const typeConfirme=id=>(LX?.types_confirmes||[]).includes(id);
const rayonLieu=d=>d===LIEU_CHOISI?5:creux(d)?2.7:2.4,traitLieu=d=>creux(d)?1.2:.6;
const lieuDep=c=>c&&c.startsWith("97")?c.slice(0,3):(c||"").slice(0,2);
function lieuxOptions(){const sel=document.getElementById("lieuxType"),bar=document.getElementById("lieuxBar");
  if(!LX){bar.hidden=true;return}bar.hidden=false;
  const types=LX.types.map((t,k)=>({...t,k})).filter(t=>LX.pts.some(p=>p[0]===t.k)&&(S.fam==="*"||t.famille===S.fam));
  const grp=[...new Set(types.map(t=>t.groupe))];
  sel.innerHTML='<option value="">Aucune</option>'+grp.map(g=>'<optgroup label="'+esc(g)+'">'+types.filter(t=>t.groupe===g)
    .map(t=>'<option value="'+t.id+'"'+(S.lieux===t.id?" selected":"")+'>'+esc(t.lib)+(t.complet?"":" (recensement incomplet)")+'</option>').join("")+'</optgroup>').join("");
  if(S.lieux&&!types.some(t=>t.id===S.lieux))S.lieux="";sel.value=S.lieux||""}
function projLieu(pt){const d=lieuDep(pt[4]),ll=[pt[2]/1e4,pt[1]/1e4];return DOMS.includes(d)?(P[d]?P[d].projection()(ll):null):CORSE.includes(d)?metro([ll[0]-DLON_CORSE,ll[1]]):metro(ll)}
function dessinerLieux(Mx){Mx.zoomable.selectAll("g.lieux").remove();Mx.svg.selectAll("g.lieuxdom").remove();
  if(!LX||!S.lieux||Mx.tuiles){document.getElementById("lieuInfo").hidden=true;return ""}
  const k=LX.types.findIndex(t=>t.id===S.lieux),t=LX.types[k],pts=LX.pts.filter(p=>p[0]===k);
  const z=d3.zoomTransform(Mx.svg.node()).k;
  const dessin=(g,data)=>g.selectAll("circle").data(data).join("circle").attr("class","lieu")
    .attr("cx",d=>projLieu(d)[0]).attr("cy",d=>projLieu(d)[1]).attr("r",d=>rayonLieu(d)/(g.node().parentNode===Mx.zoomable.node()?z:1))
    .attr("class",d=>"lieu"+(creux(d)?" creux":"")).attr("pointer-events","all")
    .attr("fill",d=>d===LIEU_CHOISI?css("--accent"):creux(d)?"none":css("--ink")).attr("fill-opacity",d=>recoupe(d)&&d!==LIEU_CHOISI?.4:.85)
    .attr("stroke",d=>creux(d)?(d===LIEU_CHOISI?css("--accent"):css("--ink")):css("--panel")).attr("stroke-width",d=>traitLieu(d)/(g.node().parentNode===Mx.zoomable.node()?z:1))
    .attr("tabindex",0).attr("role","button").attr("aria-label",d=>LX.noms[d[3]]+", "+(LX.communes[d[4]]||"")+(d[11]!=null?", "+CONF[d[11]].lib:""))
    .on("mousemove",(ev,d)=>showTip(ev,'<div class="tt">'+esc(LX.noms[d[3]])+'</div><div class="tl">'+esc(t.lib)+", "+esc(LX.communes[d[4]]||d[4])+'</div>'+(d[11]!=null?'<div class="tl">'+symboleConf(d)+' '+esc(CONF[d[11]].lib)+'</div>':'')))
    .on("mouseleave",hideTip)
    .on("click",(ev,d)=>{ev.stopPropagation();LIEU_CHOISI=LIEU_CHOISI===d?null:d;ficheLieu();drawMap()})
    .on("keydown",(ev,d)=>{if(ev.key==="Enter"||ev.key===" "){ev.preventDefault();LIEU_CHOISI=LIEU_CHOISI===d?null:d;ficheLieu();drawMap()}});
  const ok=pts.filter(d=>projLieu(d));
  dessin(Mx.zoomable.append("g").attr("class","lieux"),ok.filter(d=>!DOMS.includes(lieuDep(d[4]))));
  dessin(Mx.svg.append("g").attr("class","lieuxdom"),ok.filter(d=>DOMS.includes(lieuDep(d[4]))));
  if(LIEU_CHOISI&&LIEU_CHOISI[0]!==k)LIEU_CHOISI=null;
  visibiliteLieux(Mx);
  ficheLieu();
  // légende, nombre de structures confirmées et à vérifier (France entière, ou territoire choisi)
  const champ={epci:8,dep:9,reg:10}[S.sel?.lv],ici=S.sel&&S.sel.lv===S.level&&champ!=null?pts.filter(d=>d[champ]===S.sel.c):null;
  const vus=ici||pts,nc=vus.filter(confirme).length,nr=vus.filter(recoupe).length,nb=vus.filter(creux).length;
  const conf=typeConfirme(t.id)?legendeClasses(nc,nr,nb)+'<span>'+(ici?"dans le territoire choisi":"en France")+', voir « Comment lire »</span>':"";
  return '<div class="legende-lieux">'+(conf?conf+'</div><div class="legende-lieux">':'<svg width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="4" fill="'+css("--ink")+'"/></svg> ')
    +fmt.format(pts.length)+' structures, '+esc(minLib(t.lib))+', recensées par FINESS et le ROR, réunies sans double compte'+(t.complet?"":", recensement incomplet")
    +'. Les points s’affichent en zoomant sur la carte (deux fois au moins), le plan du territoire choisi est dans l’encadré « Structures de soins de ce territoire »'+(t.complet&&D.niveaux[S.level].lieux_dist?.[S.lieux]?", la mesure « Distance aux structures » en donne la vue d’ensemble":"")+'.</div>'}
// symbole du niveau de confirmation, plein ou creux comme sur la carte
function symboleConf(d,k){const c=d?classeDe(d):(k===true?"a_verifier":k===false?"confirmee":k);
  const f=c==="a_verifier"?'fill="none" stroke="currentColor" stroke-width="1.6"':c==="recoupee"?'fill="currentColor" fill-opacity=".4" stroke="currentColor" stroke-width="1.2"':'fill="currentColor"';
  return '<svg class="sym-conf" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="4" '+f+'/></svg>'}
// légende des trois classes avec leur nombre (la classe recoupée n'apparaît que si elle compte des structures)
function legendeClasses(nc,nr,nb){return '<span class="lx-leg">'+symboleConf(null,"confirmee")+' '+fmt.format(nc)+' confirmée'+(nc>1?"s":"")+'</span>'
  +(nr?'<span class="lx-leg">'+symboleConf(null,"recoupee")+' '+fmt.format(nr)+' recoupée'+(nr>1?"s":"")+' par la statistique des hôpitaux</span>':'')
  +'<span class="lx-leg">'+symboleConf(null,"a_verifier")+' '+fmt.format(nb)+' à vérifier</span>'}
// à l'échelle de la France les points chargent trop la carte, ils ne paraissent qu'en zoomant (au moins 2 fois)
// (remarques de Lucas du 12 et du 16 octobre 2026). Le territoire choisi a son propre plan dans l'encadré « Structures
// de soins de ce territoire », sans que la grande carte change de cadrage.
function visibiliteLieux(Mx){if(!Mx)return;const k=d3.zoomTransform(Mx.svg.node()).k;
  Mx.zoomable.selectAll("circle.lieu").style("display",d=>k>=2||d===LIEU_CHOISI?null:"none");
  Mx.svg.selectAll("g.lieuxdom circle.lieu").style("display",d=>d===LIEU_CHOISI?null:"none")}
// points des structures à la taille de l'écran quel que soit le zoom, et seulement à partir d'un certain zoom
SUR_ZOOM.push((Mx,ev)=>{Mx.zoomable.selectAll("circle.lieu").attr("r",d=>rayonLieu(d)/ev.transform.k).attr("stroke-width",d=>traitLieu(d)/ev.transform.k);
  visibiliteLieux(Mx)});
function ficheLieu(){const el=document.getElementById("lieuInfo");const d=LIEU_CHOISI;
  if(!d){el.hidden=true;el.innerHTML="";return}
  el.innerHTML='<p style="margin:6px 16px">'+texteLieu(d)+' <button type="button" class="lien" id="lieuFermer">Fermer</button></p>';el.hidden=false;
  document.getElementById("lieuFermer").onclick=()=>{LIEU_CHOISI=null;ficheLieu();drawMap()}}
function texteLieu(d){const t=LX.types[d[0]],dec=d[7],npart=d[14]||0;
  let h='<strong>'+esc(LX.noms[d[3]])+'</strong>, '+esc(minLib(t.lib))+', '+esc(LX.communes[d[4]]||d[4])+'. ';
  const pv=LX.provenances[d[5]];
  h+=(pv.includes("ne distingue")?"Décrit par le ROR seulement, FINESS ne distinguant pas ce type de structure":pv.includes("seul")?(pv.startsWith("ROR")?"Recensé comme tel par le ROR seulement, FINESS l’enregistrant sous une autre catégorie ou pas du tout":"Recensé par FINESS seulement"):"Recensé par FINESS et le ROR")+'. Emplacement, '+esc(LX.precisions[d[6]])+'.';
  if(dec===0)h+=' Aucun de ces professionnels (psychiatres, psychologues, infirmiers...) n’y est déclaré au répertoire, ce qui n’exclut pas des consultations de professionnels déclarés à leur établissement de rattachement.';
  else if(dec){const parts=LX.professions.map((p,k)=>dec[k]?fmt.format(dec[k])+" "+(dec[k]>1?pluriel(profLab(p)):profLab(p).toLowerCase()):null).filter(Boolean);
    // numéro FINESS partagé par plusieurs structures de la commune, l'effectif est celui de l'établissement, jamais
    // attribué à la structure (règle des trois temps, 29 octobre 2026)
    h+=' '+(!parts.length?"Aucun de ces professionnels n’y est déclaré au répertoire, ce qui n’exclut pas des consultations de professionnels déclarés à leur établissement de rattachement."
      :npart>1?"Déclarés à l’établissement, dont le numéro FINESS est partagé par "+npart+" structures de la commune, "+parts.join(", ")+", sans qu’on sache combien exercent dans celle-ci."
      :"Déclarés sur place au répertoire, "+parts.join(", ")+".")}
  else h+=' Sans numéro FINESS propre, les professionnels déclarés sur place ne sont pas connus.';
  if(d[11]!=null)h+=' Niveau de confirmation, '+esc(CONF[d[11]].lib)+'.';
  if(d[13]&2)h+=' Ce CATTP est au même lieu qu’un CMP, il est compté à part comme lieu d’activité déclaré.';
  if(d[13]&1)h+=' C’est une antenne ou une permanence.';
  return h}
const PSY_CMP=["psychiatre","pedopsychiatre"];
// lieux pour enfants d'un territoire (FINESS et ROR réunis), pour préciser « aucun pédopsychiatre déclaré »
// ---------- encadré « Structures de soins de ce territoire » (16 octobre 2026, remplace le volet replié de la fiche).
// Nombre par type et par groupe, niveau de confirmation de chaque structure, liste par type ouverte d'un bouton, un clic
// sur une structure la repère sur la carte sans zoom. Les CMP pour adultes et pour enfants sont des CMP comptés aussi
// dans le total des CMP, un CMP accueillant les deux publics figure dans les deux lignes et y est signalé.
const LX_GROUPES=[["Santé mentale, adultes",["lieu_cmp_adultes","lieu_hdj_psy_adultes","lieu_hc_psy_adultes"]],
  ["Santé mentale, enfants et adolescents",["lieu_cmp_enfants","lieu_hdj_psy_enfants","lieu_hc_psy_enfants","lieu_cmpp","lieu_camsp"]],
  ["Santé mentale, tous âges",["cmp_non_precise","lieu_cattp"]],
  ["Addictologie",["lieu_csapa","lieu_caarud","lieu_addicto_hosp"]]];
const LX_OUVERTS=new Set();  // listes ouvertes, gardées d'un territoire à l'autre
const PUBLIC_CMP={a:"pour adultes",e:"pour enfants et adolescents",d:"pour adultes et pour enfants",n:"au public non précisé"};
function lignesStructures(lv,code){
  const champ={epci:8,dep:9,reg:10}[lv],L=D.niveaux[lv].lieux||{},ici=LX.pts.filter(p=>p[champ]===code);
  const kOf=id=>LX.types.findIndex(t=>t.id===id),cmpK=kOf("lieu_cmp");
  // public de chaque CMP, retrouvé pour les points des types enfants par le nom et l'emplacement
  const cle=p=>p[3]+","+p[1]+","+p[2],pub=new Map(ici.filter(p=>p[0]===cmpK).map(p=>[cle(p),p[12]]));
  const visibles=LX.types.filter(t=>t.complet&&L[t.id]&&(S.fam==="*"||t.famille===S.fam));
  const ligne=(id,lib,pts,tid)=>({id,lib,pts,tid:tid||id,conf:typeConfirme(tid||id)});
  const groupes=[],pris=new Set(["lieu_cmp"]);
  for(const [g,ids] of LX_GROUPES){const lignes=[];
    for(const id of ids){
      if(id==="cmp_non_precise"){if(!visibles.some(t=>t.id==="lieu_cmp"))continue;const pts=ici.filter(p=>p[0]===cmpK&&p[12]==="n");
        if(pts.length)lignes.push(ligne(id,"CMP au public non précisé",pts,"lieu_cmp"));continue}
      const t=visibles.find(x=>x.id===id);if(!t)continue;pris.add(id);const k=kOf(id);
      lignes.push(ligne(id,t.lib,ici.filter(p=>p[0]===k).map(p=>{if(id.startsWith("lieu_cmp_"))p._pub=pub.get(cle(p));return p})))}
    if(lignes.length)groupes.push([g,lignes])}
  // les autres types, dans l'ordre des données, sous leur groupe
  for(const g of [...new Set(visibles.filter(t=>!pris.has(t.id)).map(t=>t.groupe))]){
    const lignes=visibles.filter(t=>!pris.has(t.id)&&t.groupe===g).map(t=>{const k=kOf(t.id);return ligne(t.id,t.lib,ici.filter(p=>p[0]===k))});
    groupes.push([g,lignes])}
  return {groupes,ici,cmpK}}
function precisionLieu(p,id){const tags=[];
  if(id.startsWith("lieu_cmp_")&&p._pub==="d")tags.push(id==="lieu_cmp_adultes"?"accueille aussi les enfants":"accueille aussi les adultes");
  if(p[13]&1)tags.push("antenne ou permanence");
  if(p[13]&2)tags.push("au même lieu qu’un CMP");
  return tags}
function confLigne(l,c,r,b){if(!l.conf)return '<span class="muted">niveau non établi</span>';
  const rec=(LX.types_recoupes||[]).includes(l.id),N=n=>fmt.format(n),s=(k,cl)=>'<span>'+symboleConf(null,cl)+N(k)+'</span>';
  return '<span class="lx-conf"><span aria-hidden="true">'+s(c,"confirmee")+(rec?s(r,"recoupee"):'')+s(b,"a_verifier")+'</span><span class="sr">'
    +N(c)+' confirmée'+(c>1?'s':'')+(rec?', '+N(r)+' recoupée'+(r>1?'s':''):'')+', '+N(b)+' à vérifier</span></span>'}
function structuresTerritoire(){const el=document.getElementById("lieuxCard");
  const vider=()=>{el.classList.add("hidden");el.innerHTML="";delete EXPORT_CSV.structures};
  if(!LX||!S.sel||S.sel.lv!==S.level)return vider();
  const lv=S.sel.lv,i=IDX[lv].get(S.sel.c),u=D.niveaux[lv].units[i],code=S.sel.c;
  const {groupes,ici,cmpK}=lignesStructures(lv,code);
  if(!groupes.length)return vider();
  el.classList.remove("hidden");
  const N=n=>fmt.format(n);
  // structures distinctes au niveau de confirmation établi, chaque CMP une fois (pas les lignes adultes et enfants)
  const toutes=groupes.flatMap(([,ls])=>ls);
  const autres=toutes.filter(l=>l.conf&&l.tid!=="lieu_cmp"&&!l.id.startsWith("lieu_cmp_")).flatMap(l=>l.pts);
  const cmpTous=toutes.some(l=>l.tid==="lieu_cmp"||l.id.startsWith("lieu_cmp_"))?ici.filter(p=>p[0]===cmpK):[];
  const base=[...autres,...(typeConfirme("lieu_cmp")?cmpTous:[])],nc=base.filter(confirme).length,nr=base.filter(recoupe).length,nb=base.filter(creux).length;
  let h='<h2 tabindex="-1">Structures de soins de ce territoire <button class="how" data-how="lieux,confirmation">Comment lire</button></h2><div class="howtxt hidden"></div>';
  h+='<div data-export="structures">';
  // l'encadré repensé (demande de Lucas du 28 octobre 2026) : le résultat d'abord, en une phrase et une légende en
  // couleur, puis le plan sur toute la largeur, puis la liste par type, le détail de chaque type à un clic
  const accord=(k,s,p)=>N(k)+' '+(k>1?p:s);
  h+='<p class="phrase">'+(base.length>1?'Sur les '+N(base.length)+' structures de ce territoire dont le niveau de confirmation est établi, '
      +accord(nc,"est confirmée","sont confirmées")+' par une source indépendante de FINESS et du Répertoire opérationnel des ressources (ROR)'
      +(nr?', '+accord(nr,"est recoupée","sont recoupées")+' par la statistique annuelle des établissements de santé (SAE), qui confirme le nombre et non l’adresse,':'')
      +' et '+accord(nb,"reste","restent")+' à vérifier.'
    :base.length?'La structure de ce territoire dont le niveau de confirmation est établi '+(nc?'est confirmée par une source indépendante de FINESS et du Répertoire opérationnel des ressources (ROR).':nr?'est recoupée par la statistique annuelle des établissements de santé (SAE).':'reste à vérifier.')
    :'FINESS et le Répertoire opérationnel des ressources (ROR), réunis sans double compte, recensent ici les structures suivantes.')+'</p>';
  if(base.length)h+='<div class="lx-legende lx-resultat">'+legendeClasses(nc,nr,nb)+'</div>';
  const lignesPlan=groupes.flatMap(([,ls])=>ls).filter(l=>l.pts.length);
  if(!lignesPlan.some(l=>l.id===LX_TYPE_LOCAL))LX_TYPE_LOCAL=(lignesPlan.find(l=>l.id==="lieu_cmp_adultes")||lignesPlan[0]||{}).id;
  if(LX_CHOISI_LOCAL&&!ici.includes(LX_CHOISI_LOCAL))LX_CHOISI_LOCAL=null;
  h+='<div class="lx-corps">'+(lignesPlan.length?carteTerritoireHtml(lignesPlan):'')+'<div class="lx-gauche"><div class="scroll"><table class="lx-table"><thead><tr><th scope="col">Type de structure</th><th scope="col">Structures</th><th scope="col">Niveau de confirmation</th></tr></thead><tbody>';
  const cp=D.niveaux[lv].cmp_public,cs=D.niveaux[lv].cmp_sae?.[i];
  for(const [g,ls] of groupes){h+='<tr class="lx-groupe"><th colspan="3" scope="colgroup">'+esc(g)+'</th></tr>';
    for(const l of ls){const n=l.pts.length,c=l.pts.filter(confirme).length,r=l.pts.filter(recoupe).length,b=l.pts.filter(creux).length,ouv=LX_OUVERTS.has(l.id);
      h+='<tr><td>'+esc(l.lib)+(n?'<br><button type="button" class="lien lx-ouvrir" data-l="'+l.id+'" aria-expanded="'+ouv+'" aria-controls="lx-'+l.id+'">'+(ouv?"Masquer la liste":"Voir la liste")+'</button>':'')+'</td>'
        +'<td>'+N(n)+'</td><td>'+confLigne(l,c,r,b)+'</td></tr>';
      const notes=[];
      if(l.id==="lieu_cattp"){const m=l.pts.filter(p=>p[13]&2).length;
        if(m)notes.push(N(m)+(m>1?" sont au même lieu qu’un CMP, comptés à part comme lieux d’activité déclarés":" est au même lieu qu’un CMP, compté à part comme lieu d’activité déclaré"));
        const s=l.pts.filter(p=>p[11]!=null&&CONF[p[11]].id==="sae").length;
        if(s)notes.push(N(s)+" "+(s>1?"sont recoupés":"est recoupé")+" par la statistique des hôpitaux, leur établissement y déclarant autant de CATTP, ce qui confirme le nombre et non l’adresse")}
      if(l.id==="lieu_cmp_adultes"||l.id==="lieu_cmp_enfants"){const d=l.pts.filter(p=>p._pub==="d").length;
        if(d)notes.push(N(d)+" accueille"+(d>1?"nt":"")+" aussi "+(l.id==="lieu_cmp_adultes"?"les enfants":"les adultes")+", compté"+(d>1?"s":"")+" dans les deux lignes")}
      if(notes.length)h+='<tr class="lx-note"><td colspan="3">'+esc(notes.join(", "))+'.</td></tr>';
      if(n)h+='<tr class="lx-liste"'+(ouv?'':' hidden')+' id="lx-'+l.id+'"><td colspan="3"><ul>'+l.pts.slice().sort((a,b)=>(LX.communes[a[4]]||"").localeCompare(LX.communes[b[4]]||"","fr")||LX.noms[a[3]].localeCompare(LX.noms[b[3]],"fr"))
        .map(p=>{const tags=precisionLieu(p,l.id);return '<li><button type="button" class="lx-item" data-j="'+LX.pts.indexOf(p)+'" data-l="'+l.id+'">'+(p[11]!=null?symboleConf(p):'')+'<span class="nom">'+esc(LX.noms[p[3]])+'</span><span class="muted">, '+esc(LX.communes[p[4]]||p[4])+(p[11]!=null?', '+esc(CONF[p[11]].lib):'')+(tags.length?', '+esc(tags.join(", ")):'')+'</span></button></li>'}).join("")+'</ul></td></tr>'}}
  h+='</tbody></table></div></div></div>';
  // CMP en tout, par public, et concordance avec la SAE
  if(cmpTous.length&&cp){const v=k=>cp[k][i]||0;
    h+='<p class="note">'+N(cmpTous.length)+' CMP en tout, dont '+N(v("adultes"))+' pour adultes et '+N(v("enfants"))+' pour enfants et adolescents'
      +(v("les_deux")?', '+N(v("les_deux"))+' accueillant les deux':'')+(v("non_precise")?', '+N(v("non_precise"))+' au public non précisé (connu'+(v("non_precise")>1?"s":"")+' de FINESS seul)':'')
      +(v("antennes")?'. '+(v("antennes")>1?N(v("antennes"))+' sont des antennes ou des permanences':'L’un d’eux est une antenne ou une permanence')+' (en mairie, en CCAS ou en maison de santé, par exemple)':'')+'.'
      +(cs?' '+esc(cs[1].charAt(0).toUpperCase()+cs[1].slice(1))+' ('+N(cs[0])+' CMP déclarés à la SAE par les établissements dont le siège est ici).':'')+'</p>'}
  h+='<p class="note">Une structure n’est pas une capacité. Les types recensés de façon incomplète (équipes mobiles, centres de crise...) restent sur la carte et ne sont pas comptés ici.</p>';
  h+='</div>';
  // constats vérifiés sur d'autres sources (sites des établissements, ARS, listes ouvertes), pour le département
  const depV=lv==="dep"?code:lv==="epci"?u.p:null;
  const ver=(D.verifications_lieux||[]).filter(v=>v.code===depV);
  if(ver.length)h+='<div class="note" style="margin-top:8px"><strong>Vérifié sur d’autres sources.</strong> '+ver.map(v=>esc(v.constat)+' Source, <a href="'+esc(v.adresse)+'" target="_blank" rel="noopener">'+esc(v.source)+'</a>, consultée le '+esc(v.date.split("-").reverse().join("/"))+(v.a_refaire?", vérification à refaire":"")+'.').join(" ")+'</div>';
  h+=limiteHtml(["lieux"]);
  el.innerHTML=h;
  // liste affichée, exportée par « Citer et exporter »
  EXPORT_CSV.structures=()=>{const lignes=[["Groupe","Type de structure","Nom","Commune","Code commune","Public des CMP","Niveau de confirmation","Précisions","Provenance"]];
    for(const [g,ls] of groupes)for(const l of ls)for(const p of l.pts)lignes.push([g,l.lib,LX.noms[p[3]],LX.communes[p[4]]||"",p[4],
      l.tid==="lieu_cmp"||l.id.startsWith("lieu_cmp_")?(PUBLIC_CMP[p._pub||p[12]]||""):"",p[11]!=null?CONF[p[11]].lib:"niveau non établi pour ce type",
      precisionLieu(p,l.id).join(", "),LX.provenances[p[5]]]);
    return {titre:"Structures de soins, "+u.nm+", FINESS et ROR réunis sans double compte",nom:nomFichier("structures_de_soins_"+u.nm,"structures"),texte:lignes.map(l=>l.map(qCsv).join(";")).join("\r\n")}};
  el.querySelectorAll(".lx-ouvrir").forEach(b=>b.onclick=()=>{const id=b.dataset.l,tr=document.getElementById("lx-"+id),ouv=tr.hidden;
    tr.hidden=!ouv;b.setAttribute("aria-expanded",String(ouv));b.textContent=ouv?"Masquer la liste":"Voir la liste";if(ouv)LX_OUVERTS.add(id);else LX_OUVERTS.delete(id)});
  const plan=()=>dessinerCarteTerritoire(lv,code,lignesPlan);
  plan();
  const se=document.getElementById("lxSecteurs");
  // type de secteur suivi tant que le lecteur ne l'a pas choisi lui-même
  // une valeur posée par le code est reportée sur la liste soignée qui double la liste du navigateur (choixListe)
  const miroir=sel=>{const b=sel&&document.querySelector('.prof-choix[data-pour="'+sel.id+'"] button');if(!b)return;const t=sel.selectedOptions[0]?.textContent||"";
    b.querySelector("span").textContent=t;b.setAttribute("aria-label",(sel.getAttribute("aria-label")||"Choix")+", "+t)};
  const reglerSecteurs=()=>{if(!LX_SECTEURS_CHOISI)LX_SECTEURS_TYPE=typeSecteurPour(LX_TYPE_LOCAL);if(se){se.value=LX_SECTEURS_TYPE||"";miroir(se)}};
  if(se){reglerSecteurs();se.onchange=()=>{LX_SECTEURS_TYPE=se.value;LX_SECTEURS_CHOISI=true;dessinerSecteurs(lv,code)};dessinerSecteurs(lv,code)}
  const st=document.getElementById("lxType");if(st)st.onchange=()=>{LX_TYPE_LOCAL=st.value;LX_CHOISI_LOCAL=null;if(se)reglerSecteurs();plan()};
  el.querySelectorAll(".lx-item").forEach(b=>b.onclick=()=>{const p=LX.pts[+b.dataset.j];LX_TYPE_LOCAL=b.dataset.l;
    LX_CHOISI_LOCAL=LX_CHOISI_LOCAL===p?null:p;if(st){st.value=LX_TYPE_LOCAL;miroir(st)}if(se)reglerSecteurs();plan();
    // plan hors de l'écran (petits écrans), on le fait venir sans changer son cadrage
    const r=(document.getElementById("lxPlan")||document.getElementById("lxCarte")).getBoundingClientRect(),haut=document.querySelector(".collant")?.getBoundingClientRect().bottom||0;
    if(r.top<haut||r.bottom>innerHeight)scrollTo({top:scrollY+r.top-haut-60,behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth"})})}
// ---------- carte du territoire choisi, dans l'encadré des structures (décision de Lucas du 16 octobre 2026). Sur la
// grande carte les points ne paraissent qu'en zoomant, ici le plan est cadré sur le territoire, avec ses limites
// internes (intercommunalités d'un département, départements d'une région), et montre les structures d'un type, point
// plein confirmée, point creux à vérifier. Un clic dans la liste repère la structure sur ce plan, la grande carte ne bouge
// pas. Les points ne sont pas dans l'ordre de tabulation, la liste en est l'équivalent au clavier.
let LX_TYPE_LOCAL="lieu_cmp_adultes",LX_CHOISI_LOCAL=null;
// Plan IGN sous les structures (demande de Lucas du 28 octobre 2026), fond de la Géoplateforme (couche
// GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2, grille PM_0_19, PNG), adresse et couche relevées le 28 octobre 2026 dans les
// capacités du service WMTS, conditions sur https://cartes.gouv.fr/cgu. Le plan en SVG reste dessiné hors de l'écran,
// c'est lui que « Citer et exporter » enregistre (les images du fond viennent d'un autre serveur). Sans Leaflet, ou si
// le fond ne se charge pas, les points et le contour restent lisibles.
// mention demandée par l'IGN, « © IGN » suivi du nom du produit (réponse du 29 octobre 2026 à la question du 28 octobre,
// dossier DRG CRM:0072209), Plan IGN sous Licence Ouverte 2.0, usage commercial compris (pipeline/licences.py, ign-lo-2.0)
const IGN_PLAN="https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&TILEMATRIXSET=PM_0_19&FORMAT=image/png&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}";
const IGN_MENTION='© IGN – <a href="https://cartes.gouv.fr/" target="_blank" rel="noopener">Plan IGN</a>';
// points posés sur le fond clair du plan, mêmes couleurs dans les deux thèmes (bleu d'encre, choisi en cuivre)
const PLAN_POINT="#1D4D87",PLAN_CHOISI="#8A5A0E";
const planIgn=()=>!!(window.L&&window.L.map);
let LX_PLAN=null;
// ---------- secteurs de psychiatrie sur le plan (demande de Lucas du 29 octobre 2026), d'après les arrêtés des ARS reçus
// (pipeline/sectorisation.py, secteurs_psychiatrie.geojson à côté de la page, chargé à la première demande). Une couche
// par type, générale ou infanto-juvénile, en aplats clairs sous les structures, deux secteurs voisins jamais de la même
// teinte, une ville partagée entre secteurs en pointillé. Ailleurs, la sectorisation est dite non disponible.
let LX_SECTEURS=null,LX_SECTEURS_ETAT="",LX_SECTEURS_TYPE=null,LX_SECTEURS_CHOISI=false;
function chargerSecteurs(fin){if(LX_SECTEURS||LX_SECTEURS_ETAT==="erreur")return fin();
  if(LX_SECTEURS_ETAT==="charge")return;LX_SECTEURS_ETAT="charge";
  fetch("secteurs_psychiatrie.geojson").then(r=>{if(!r.ok)throw new Error(r.status);return r.json()})
    .then(j=>{LX_SECTEURS=j;LX_SECTEURS_ETAT="";fin()}).catch(()=>{LX_SECTEURS_ETAT="erreur";fin()})}
const regionDuTerritoire=(lv,code)=>typeof regionDe==="function"?regionDe(lv,code):null;
// type de secteur proposé d'abord, celui du public des CMP montrés, aucun pour les autres types
const typeSecteurPour=id=>/_enfants$/.test(id)?"I":/^lieu_cmp/.test(id)?"G":"";
function bulleSecteur(pr){const lim=(pr.limites||[]).map(t=>'<div class="tl">'+esc(t)+'</div>').join("");
  return '<div class="tt">'+(pr.secteur?'Secteur '+esc(pr.secteur):'Commune partagée entre les secteurs '+esc((pr.partagee||[]).join(", ")))+'</div>'
    +'<div class="tl">'+esc(pr.type_lib||"")+'</div><div class="tl">Établissement responsable, '+esc(pr.etablissement||"")+'</div>'
    +'<div class="tl muted">Source, '+esc(pr.source||"")+'</div>'+lim}
function dessinerSecteurs(lv,code){const P=LX_PLAN,LF=window.L;if(!P||!LF)return;
  if(P.secteurs)P.secteurs.clearLayers();else{P.secteurs=LF.layerGroup().addTo(P.carte);P.points.remove();P.points.addTo(P.carte)}
  const ty=LX_SECTEURS_TYPE,leg=document.getElementById("lxSecteursNote");if(!ty){if(leg)leg.textContent="";return}
  if(!LX_SECTEURS){if(leg)leg.textContent=LX_SECTEURS_ETAT==="erreur"?"Secteurs indisponibles dans cette version de l'atlas.":"Chargement des secteurs…";
    chargerSecteurs(()=>dessinerSecteurs(lv,code));return}
  const reg=regionDuTerritoire(lv,code);
  if(!reg||!(LX_SECTEURS.regions||[]).includes(reg)){if(leg)leg.textContent="Sectorisation non disponible pour cette région.";return}
  const t=LX_SECTEURS.teintes||[];
  const fs=LX_SECTEURS.features.filter(f=>f.properties.region===reg&&f.properties.type===ty);
  LF.geoJSON({type:"FeatureCollection",features:fs},{style:f=>f.properties.secteur
    ?{color:"#1C2028",weight:1.2,opacity:.75,fillColor:t[f.properties.teinte]||"#E3E2DC",fillOpacity:.5}
    :{color:"#1C2028",weight:1,opacity:.75,dashArray:"4 3",fillColor:"#FFFFFF",fillOpacity:.55},
    onEachFeature:(f,lay)=>{lay.on("mousemove",ev=>showTip(ev.originalEvent,bulleSecteur(f.properties)));lay.on("mouseout",hideTip)}}).addTo(P.secteurs);
  if(leg){const d=fs.find(f=>f.properties.secteur);leg.textContent=d?"Secteurs de "+d.properties.type_lib+", d'après l'arrêté de l'ARS du "
    +new Date(d.properties.date+"T00:00").toLocaleDateString("fr-FR",{day:"numeric",month:"long",year:"numeric"})+", établissement responsable dans l'infobulle.":""}}
function dessinerPlanIgn(lv,code,lignes,l){
  const LF=window.L,el=document.getElementById("lxPlan");if(!el)return;
  const cle=lv+"|"+code,f=formeTerritoire(lv,code);
  if(!LX_PLAN||LX_PLAN.el!==el){
    // encadré refait (autre réglage), même territoire, le cadrage choisi est gardé
    const vue=LX_PLAN&&LX_PLAN.cle===cle?[LX_PLAN.carte.getCenter(),LX_PLAN.carte.getZoom()]:null;
    if(LX_PLAN)LX_PLAN.carte.remove();
    // molette réservée au défilement de la page (zoom avec Ctrl, comme la grande carte), un doigt fait défiler la page
    // sur téléphone, deux doigts rapprochent le plan
    const carte=LF.map(el,{scrollWheelZoom:false,dragging:!LF.Browser.mobile,tap:false,zoomSnap:.5,minZoom:5,maxZoom:18});
    LF.tileLayer(IGN_PLAN,{maxZoom:18,attribution:IGN_MENTION}).addTo(carte);
    carte.attributionControl.setPrefix(false);
    el.addEventListener("wheel",ev=>{if(!ev.ctrlKey)return;ev.preventDefault();carte.setZoom(carte.getZoom()+(ev.deltaY<0?.5:-.5))},{passive:false});
    LX_PLAN={el,carte,cle,cadre:vue?cle:null,points:LF.layerGroup()};
    if(f){LF.geoJSON(f,{interactive:false,style:{color:"#FFFFFF",weight:5,opacity:.8,fill:false}}).addTo(carte);
      LX_PLAN.contour=LF.geoJSON(f,{interactive:false,style:{color:"#1C2028",weight:2,opacity:.9,fill:false}}).addTo(carte)}
    LX_PLAN.points.addTo(carte);
    if(vue)carte.setView(vue[0],vue[1],{animate:false})}
  const P=LX_PLAN;
  // cadrage sur le territoire une seule fois, ensuite seul le lecteur le change
  if(P.cadre!==cle){if(P.contour)P.carte.fitBounds(P.contour.getBounds(),{padding:[14,14],animate:false});else P.carte.setView([46.6,2.45],5);P.cadre=cle}
  P.points.clearLayers();
  const pts=l.pts.filter(p=>isFinite(p[1])&&isFinite(p[2])&&p[1]&&p[2]).sort((a,b)=>(a===LX_CHOISI_LOCAL)-(b===LX_CHOISI_LOCAL));
  for(const p of pts){const ch=p===LX_CHOISI_LOCAL,c=ch?PLAN_CHOISI:PLAN_POINT,vide=creux(p),demi=recoupe(p);
    // point plein confirmée (cerné de blanc), à demi rempli recoupée, creux à vérifier (centre blanc)
    const m=LF.circleMarker([p[1]/1e4,p[2]/1e4],{radius:ch?8:5.5,color:vide||demi?c:"#FFFFFF",weight:vide?2.2:1.5,
      fillColor:vide?"#FFFFFF":c,fillOpacity:vide?.9:demi?.45:1,bubblingMouseEvents:false});
    m.on("mousemove",ev=>showTip(ev.originalEvent,'<div class="tt">'+esc(LX.noms[p[3]])+'</div><div class="tl">'+esc(LX.communes[p[4]]||p[4])+'</div>'+(p[11]!=null?'<div class="tl">'+symboleConf(p)+' '+esc(CONF[p[11]].lib)+'</div>':'')));
    m.on("mouseout",hideTip);
    m.on("click",()=>{LX_CHOISI_LOCAL=LX_CHOISI_LOCAL===p?null:p;dessinerCarteTerritoire(lv,code,lignes)});
    P.points.addLayer(m)}
  // structure choisie dans la liste hors du cadre, le plan se déplace jusqu'à elle sans changer d'échelle
  if(LX_CHOISI_LOCAL&&pts.includes(LX_CHOISI_LOCAL)){const ll=[LX_CHOISI_LOCAL[1]/1e4,LX_CHOISI_LOCAL[2]/1e4];if(!P.carte.getBounds().contains(ll))P.carte.panTo(ll,{animate:false})}
  dessinerSecteurs(lv,code);
  const u=D.niveaux[lv].units[IDX[lv].get(code)];
  el.setAttribute("aria-label","Plan IGN de "+u.nm+", "+minLib(l.lib)+", "+fmt.format(l.pts.length)+" structures, point plein confirmée, point creux à vérifier")}
const LX_MAILLES={};
// contours de tous les territoires d'un niveau (le fond ne partage pas les arcs entre voisins, d'où le maillage complet)
// filtre, territoires retenus (par leurs propriétés), pour ne tracer que les limites utiles au plan
function mailleLx(niv,filtre,cle){const k=niv+"|"+(cle||"");if(!(k in LX_MAILLES)){const o=topo.objects[niv];
  LX_MAILLES[k]=o?topojson.mesh(topo,filtre?{type:"GeometryCollection",geometries:o.geometries.filter(g=>filtre(g.properties||{}))}:o):null}
  return LX_MAILLES[k]}
function formeTerritoire(lv,code){const f=(geom[lv]||[]).find(x=>x.properties[lv]===code);return f||null}
function carteTerritoireHtml(lignes){
  const opts=lignes.map(l=>'<option value="'+l.id+'"'+(l.id===LX_TYPE_LOCAL?" selected":"")+'>'+esc(l.lib)+' ('+fmt.format(l.pts.length)+')</option>').join("");
  return '<div class="lx-droite"><div class="lx-plan-tete"><span class="lx-choix"><label class="small muted" for="lxType">Sur le plan</label><select id="lxType">'+opts+'</select></span>'+(planIgn()?'<span class="lx-choix"><label class="small muted" for="lxSecteurs">Secteurs</label><select id="lxSecteurs"><option value="">aucun</option><option value="G">psychiatrie générale</option><option value="I">psychiatrie infanto-juvénile</option></select></span>':'')+'<div class="lx-legende small" id="lxLegende"></div></div>'+(planIgn()?'<p class="small muted lx-secteurs-note" id="lxSecteursNote"></p>':'')
    +(planIgn()?'<div id="lxPlan" class="lx-plan" role="img" aria-label="Plan IGN du territoire et de ses structures de soins"></div>':'')
    +'<svg id="lxCarte"'+(planIgn()?' class="lx-export" aria-hidden="true"':'')+' viewBox="0 0 400 340" role="img" aria-label="Plan du territoire et de ses structures de soins"></svg>'
    +'<div class="lieuinfo small" id="lxFiche" hidden aria-live="polite"></div></div>'}
function dessinerCarteTerritoire(lv,code,lignes){
  const svg=d3.select("#lxCarte");if(svg.empty())return;svg.selectAll("*").remove();
  const l=lignes.find(x=>x.id===LX_TYPE_LOCAL)||lignes[0];if(!l)return;
  dessinerPlanIgn(lv,code,lignes,l);
  const f=formeTerritoire(lv,code);if(!f){svg.append("text").attr("x",200).attr("y",170).attr("text-anchor","middle").attr("fill",css("--muted")).text("Contour du territoire indisponible");return}
  const dep=depOfFeat(lv,f),dom=DOMS.includes(dep);
  const proj=(dom?d3.geoMercator():d3.geoConicConformal().parallels([44,49]).rotate([-3,0])).fitExtent([[14,14],[386,326]],f),path=d3.geoPath(proj);
  const u=D.niveaux[lv].units[IDX[lv].get(code)];
  svg.attr("aria-label","Plan de "+u.nm+", "+minLib(l.lib)+", "+fmt.format(l.pts.length)+" structures, point plein confirmée, point creux à vérifier");
  svg.append("rect").attr("width",400).attr("height",340).attr("fill",css("--nodata"));
  // territoires voisins en fond, limites des départements (et des intercommunalités pour une intercommunalité)
  const memeDep=pr=>IDX.epciDep.get(pr.epci)===dep;
  if(lv==="epci"&&mailleLx("epci",memeDep,"dep"+dep))svg.append("path").datum(mailleLx("epci",memeDep,"dep"+dep)).attr("d",path).attr("fill","none").attr("stroke",css("--muted")).attr("stroke-width",.6).attr("stroke-opacity",.45);
  svg.append("path").datum(f).attr("d",path).attr("fill",css("--r1"));
  const clip="lxClip";svg.append("clipPath").attr("id",clip).append("path").datum(f).attr("d",path);
  const depsReg=lv==="reg"?new Set(D.niveaux.dep.units.filter(x=>x.p===u.nm).map(x=>x.c)):null;
  const interne=lv==="dep"?mailleLx("epci",memeDep,"dep"+dep):lv==="reg"?mailleLx("dep",pr=>depsReg.has(pr.dep),"reg"+code):null;
  if(interne)svg.append("path").datum(interne).attr("d",path).attr("clip-path","url(#"+clip+")").attr("fill","none").attr("stroke",css("--muted")).attr("stroke-width",.7).attr("stroke-opacity",.7);
  // départements voisins seulement (emprise du territoire élargie de moitié)
  const [[x0,y0],[x1,y1]]=d3.geoBounds(f),mx=(x1-x0)/2+.2,my=(y1-y0)/2+.2;
  const voisins=new Set(geom.dep.filter(g=>{const [[a,b],[c,e]]=d3.geoBounds(g);return c>=x0-mx&&a<=x1+mx&&e>=y0-my&&b<=y1+my}).map(g=>g.properties.dep));
  const mdep=mailleLx("dep",pr=>voisins.has(pr.dep),"autour"+lv+code);
  if(mdep)svg.append("path").datum(mdep).attr("d",path).attr("fill","none").attr("stroke",css("--muted")).attr("stroke-width",.8).attr("stroke-opacity",.6);
  svg.append("path").datum(f).attr("d",path).attr("fill","none").attr("stroke",css("--ink")).attr("stroke-width",1.4);
  // points, le choisi par-dessus
  const pts=l.pts.map(p=>({p,xy:proj([p[2]/1e4,p[1]/1e4])})).filter(d=>d.xy&&isFinite(d.xy[0]));
  pts.sort((a,b)=>(a.p===LX_CHOISI_LOCAL)-(b.p===LX_CHOISI_LOCAL));
  svg.append("g").attr("aria-hidden","true").selectAll("circle").data(pts).join("circle")
    .attr("cx",d=>d.xy[0]).attr("cy",d=>d.xy[1]).attr("r",d=>d.p===LX_CHOISI_LOCAL?6.5:creux(d.p)?4.2:4)
    .attr("fill",d=>d.p===LX_CHOISI_LOCAL?(creux(d.p)?"none":css("--accent")):creux(d.p)?"none":css("--ink"))
    .attr("stroke",d=>d.p===LX_CHOISI_LOCAL?css("--accent"):creux(d.p)?css("--ink"):css("--panel"))
    .attr("stroke-width",d=>creux(d.p)?(d.p===LX_CHOISI_LOCAL?2.4:1.6):1).attr("pointer-events","all").style("cursor","pointer")
    .on("mousemove",(ev,d)=>showTip(ev,'<div class="tt">'+esc(LX.noms[d.p[3]])+'</div><div class="tl">'+esc(LX.communes[d.p[4]]||d.p[4])+'</div>'+(d.p[11]!=null?'<div class="tl">'+symboleConf(d.p)+' '+esc(CONF[d.p[11]].lib)+'</div>':'')))
    .on("mouseleave",hideTip)
    .on("click",(ev,d)=>{LX_CHOISI_LOCAL=LX_CHOISI_LOCAL===d.p?null:d.p;dessinerCarteTerritoire(lv,code,lignes)});
  // légende en couleur, nombres du type montré, emplacements approchés signalés
  const nc=l.pts.filter(confirme).length,nr=l.pts.filter(recoupe).length,nb=l.pts.filter(creux).length,kc=new Set(LX.precisions.map((x,i)=>/^centre de la commune/.test(x)?i:-1).filter(i=>i>=0));
  // positions approchées, contour, chef-lieu ou adresse du gestionnaire reprise (29 octobre 2026)
  const approx=l.pts.filter(p=>kc.has(p[6])).length,horsCadre=l.pts.length-pts.length;
  // structures au même emplacement (même immeuble, ou centre de la même commune), un seul point visible pour plusieurs
  const nEmpl=d3.rollup(l.pts,v=>v.length,p=>p[1]+","+p[2]),superposes=d3.sum([...nEmpl.values()].filter(v=>v>1));
  document.getElementById("lxLegende").innerHTML=(l.conf?legendeClasses(nc,nr,nb):'<span>Niveau de confirmation non établi pour ce type.</span>')
    +(approx?'<span>'+fmt.format(approx)+(approx>1?' placées au centre de leur commune':' placée au centre de sa commune')+', adresse exacte inconnue.</span>':'')
    +(superposes?'<span>'+fmt.format(superposes)+' partagent leur emplacement avec une autre, un seul point les montre.</span>':'')
    +(horsCadre?'<span>'+fmt.format(horsCadre)+' sans emplacement connu.</span>':'');
  const fi=document.getElementById("lxFiche");
  if(LX_CHOISI_LOCAL&&l.pts.includes(LX_CHOISI_LOCAL)){fi.innerHTML='<p style="margin:4px 0">'+texteLieu(LX_CHOISI_LOCAL)+'</p>';fi.hidden=false}else{fi.hidden=true;fi.innerHTML=""}}
function versStructures(){const c=document.getElementById("lieuxCard");if(c.classList.contains("hidden"))return;
  c.scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"});c.querySelector("h2")?.focus({preventScroll:true})}
function lieuxEnfants(lv,i){const L=D.niveaux[lv].lieux||{},n=k=>L[k]?.[i]||0;
  const parts=[[n("lieu_cmp_enfants"),"CMP pour enfants et adolescents","CMP pour enfants et adolescents"],[n("lieu_cmpp"),"CMPP","CMPP"],
    [n("lieu_camsp"),"CAMSP","CAMSP"],[n("lieu_hdj_psy_enfants"),"hôpital de jour pour enfants","hôpitaux de jour pour enfants"]].filter(x=>x[0]>0);
  if(!parts.length)return "";
  const txt=parts.map(([k,s,pl])=>fmt.format(k)+" "+(k>1?pl:s));
  return(txt.length>1?txt.slice(0,-1).join(", ")+" et "+txt.at(-1):txt[0])+" recensés par FINESS et le ROR, où des pédopsychiatres peuvent consulter"}
// spécialité exercée surtout à l'hôpital (précision calculée à chaque mise à jour), signalée dans la légende de la carte,
// sans changer les couleurs, avec le conseil de la lire par département (demande de Lucas du 11 octobre 2026)
function legendeHospitaliere(p,lv){const k=cleLimite("prof:"+p);
  if(!k||D.limites[k]?.risque!=="exercice surtout salarié"||["trajet","evol","lieux"].includes(S.metric))return "";
  SIG.hospitalier="Exercice surtout hospitalier"+(lv==="epci"?", à lire de préférence par département":"")+", voir « À savoir » sous la carte";
  return '<div class="legende-signaux">'+legendeSignaux(["hospitalier"])+'</div>'}
