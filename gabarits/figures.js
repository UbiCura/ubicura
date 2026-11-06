// Graphiques interactifs, communs aux rapports et à l'atlas (demande de Lucas du 9 octobre 2026).
// Infobulle au survol de chaque point ou zone qui porte un titre, clic pour la garder, zoom à la molette et par
// boutons, déplacement à la souris quand le graphique est zoomé. La page n'est pas bloquée, une molette qui
// arrive pendant le défilement de la page continue de faire défiler la page.
// Réglage, window.FIGURES = {zoom: "sélecteur des svg zoomables", bulle: "sélecteur des svg à infobulles"}.
(function(){
  var R=window.FIGURES||{zoom:"figure.zoomable svg",bulle:"figure.graphique svg"};
  var bulle=document.createElement("div");bulle.className="bulle-fig";bulle.setAttribute("role","status");
  document.addEventListener("DOMContentLoaded",function(){document.body.appendChild(bulle)});
  if(document.body)document.body.appendChild(bulle);
  var epingle=null,dernierDefil=0;
  addEventListener("scroll",function(){dernierDefil=Date.now();if(!epingle)cacher()},{passive:true});
  function svgDe(el,sel){var s=el&&el.closest&&el.closest("svg");while(s&&s.ownerSVGElement)s=s.ownerSVGElement;return s&&s.matches(sel)?s:null}
  // texte de l'élément survolé, pris dans son titre (déplacé dans data-info pour éviter la bulle du navigateur)
  function info(el,s){
    for(var e=el;e&&e!==s;e=e.parentNode){
      if(e.dataset&&e.dataset.info)return [e,e.dataset.info];
      var t=e.querySelector&&e.querySelector(":scope > title");
      if(t&&e!==s){e.dataset.info=t.textContent;t.remove();return [e,e.dataset.info]}}
    return null}
  function montrer(x,y,txt){bulle.textContent=txt;bulle.style.opacity=1;var w=bulle.offsetWidth,h=bulle.offsetHeight;
    bulle.style.left=Math.max(8,Math.min(x+14,innerWidth-w-8))+"px";bulle.style.top=Math.max(8,y-h-12<8?y+16:y-h-12)+"px"}
  function cacher(){bulle.style.opacity=0}
  document.addEventListener("pointermove",function(ev){
    if(epingle)return;var s=svgDe(ev.target,R.bulle);if(!s){cacher();return}
    var i=info(ev.target,s);if(i)montrer(ev.clientX,ev.clientY,i[1]);else cacher()});
  document.addEventListener("click",function(ev){
    var s=svgDe(ev.target,R.bulle);
    if(epingle){epingle.removeAttribute("data-choisi");epingle=null}
    if(!s){cacher();return}
    var i=info(ev.target,s);if(!i){cacher();return}
    epingle=i[0];epingle.setAttribute("data-choisi","");montrer(ev.clientX,ev.clientY,i[1])});
  document.addEventListener("keydown",function(ev){if(ev.key==="Escape"&&epingle){epingle.removeAttribute("data-choisi");epingle=null;cacher()}});

  // zoom, le cadrage d'origine est repris chaque fois que la page redessine le graphique
  function cadre(s){var v=s.getAttribute("viewBox");if(!v)return null;if(s.dataset.vbz!==v)s.dataset.vb0=v;return v.split(/[ ,]+/).map(Number)}
  function zoomer(s,k,cx,cy){var b=cadre(s);if(!b)return;var o=s.dataset.vb0.split(/[ ,]+/).map(Number);
    var w=Math.min(o[2],b[2]*k),h=Math.min(o[3],b[3]*k);if(w<o[2]/12)return;
    if(cx==null){cx=b[0]+b[2]/2;cy=b[1]+b[3]/2}
    var x=cx-(cx-b[0])*w/b[2],y=cy-(cy-b[1])*h/b[3];
    x=Math.max(o[0],Math.min(x,o[0]+o[2]-w));y=Math.max(o[1],Math.min(y,o[1]+o[3]-h));
    var v=[x,y,w,h].map(function(n){return +n.toFixed(2)}).join(" ");s.setAttribute("viewBox",v);s.dataset.vbz=v;boutons(s)}
  function entier(s){return !s.dataset.vb0||s.getAttribute("viewBox")===s.dataset.vb0}
  function boutons(s){
    var hote=s.closest(".fig-corps")||s.closest("figure");
    if(!hote){
      // hors d'une figure (atlas), les boutons vont sur une ligne à eux juste au-dessus du graphique, sans recouvrir le
      // titre du panneau ni le bouton Citer
      hote=s.parentNode;
      if(hote&&!hote.classList.contains("fig-zoom")){var enveloppe=document.createElement("div");enveloppe.className="fig-zoom";
        hote.insertBefore(enveloppe,s);enveloppe.appendChild(s);hote=enveloppe}
    }
    if(!hote||hote.querySelector(":scope > .zoom-boutons"))return;
    var bz=document.createElement("div");bz.className="zoom-boutons";
    bz.innerHTML='<button type="button" aria-label="Zoomer">+</button><button type="button" aria-label="Dézoomer">−</button><button type="button" aria-label="Revenir à la vue entière">⟲</button>';
    if(getComputedStyle(hote).position==="static")hote.style.position="relative";
    hote.insertBefore(bz,hote.firstChild);
    var cible=function(){var v=hote.querySelector(".variante:not([hidden]) svg");return v||s};
    var b=bz.querySelectorAll("button");
    b[0].onclick=function(){zoomer(cible(),.6)};b[1].onclick=function(){zoomer(cible(),1/.6)};
    b[2].onclick=function(){var c=cible();cadre(c);if(c.dataset.vb0){c.setAttribute("viewBox",c.dataset.vb0);c.dataset.vbz=c.dataset.vb0}}}
  document.querySelectorAll(R.zoom).forEach(boutons);
  document.addEventListener("pointerover",function(ev){var s=svgDe(ev.target,R.zoom);if(s)boutons(s)});
  // la molette seule fait toujours défiler la page ; le zoom à la molette demande Ctrl (ou ⌘), sinon le curseur restait
  // pris dans la figure (remarque de Lucas du 23 octobre 2026) ; les boutons + et − restent le moyen ordinaire
  document.addEventListener("wheel",function(ev){
    if(!(ev.ctrlKey||ev.metaKey))return;
    var s=svgDe(ev.target,R.zoom);if(!s)return;
    if(Date.now()-dernierDefil<450)return;                       // la page défile, on la laisse défiler
    if(ev.deltaY>0&&entier(s))return;                           // vue entière, molette vers le bas, la page défile
    ev.preventDefault();var p=s.createSVGPoint();p.x=ev.clientX;p.y=ev.clientY;
    var q=p.matrixTransform(s.getScreenCTM().inverse());zoomer(s,ev.deltaY<0?.8:1.25,q.x,q.y)},{passive:false});
  var dep=null;
  document.addEventListener("pointerdown",function(ev){var s=svgDe(ev.target,R.zoom);if(!s||entier(s))return;
    var b=cadre(s);dep={x:ev.clientX,y:ev.clientY,b:b,s:s,k:b[2]/s.getBoundingClientRect().width,bouge:false}});
  addEventListener("pointermove",function(ev){if(!dep)return;var o=dep.s.dataset.vb0.split(/[ ,]+/).map(Number),b=dep.b;
    if(Math.abs(ev.clientX-dep.x)+Math.abs(ev.clientY-dep.y)>3)dep.bouge=true;if(!dep.bouge)return;
    var x=Math.max(o[0],Math.min(b[0]-(ev.clientX-dep.x)*dep.k,o[0]+o[2]-b[2])),y=Math.max(o[1],Math.min(b[1]-(ev.clientY-dep.y)*dep.k,o[1]+o[3]-b[3]));
    var v=[x,y,b[2],b[3]].map(function(n){return +n.toFixed(2)}).join(" ");dep.s.setAttribute("viewBox",v);dep.s.dataset.vbz=v});
  addEventListener("pointerup",function(){dep=null});

  // figures des rapports, même modèle que l'atlas (10 octobre 2026). Sous le titre de la figure, une ligne
  // « Citer et exporter » ouvre la citation du rapport suivie de la légende, l'image (copie, PNG, SVG, avec
  // la citation dessous) et les données de la figure. La citation du rapport est donnée par la page (data-citation).
  function citerFigures(){
    var porte=document.querySelector("[data-citation]");if(!porte)return;var base=porte.dataset.citation;
    document.querySelectorAll("figure.graphique").forEach(function(f){
      if(f.dataset.cite)return;f.dataset.cite="1";
      var cap=f.querySelector("figcaption");
      var ligne=document.createElement("div");ligne.className="outils-figure";
      var bc=document.createElement("button");bc.type="button";bc.className="citer-fig";bc.textContent="Citer et exporter";bc.setAttribute("aria-expanded","false");ligne.appendChild(bc);
      if(cap)cap.after(ligne);else f.insertBefore(ligne,f.firstChild);
      var boite=document.createElement("div");boite.className="citation-fig";boite.hidden=true;ligne.after(boite);
      bc.onclick=function(){var ouvert=boite.hidden;bc.setAttribute("aria-expanded",String(ouvert));boite.hidden=!ouvert;if(!ouvert)return;
        // la légende suit la profession choisie, la citation est donc refaite à chaque ouverture
        // figures titrées sans numéro (1er novembre 2026) : la citation reprend la légende seule
        var leg=cap&&cap.querySelector(".leg");
        var ref=leg?leg.textContent.trim():"Figure";
        var texte=base.replace(/\s*$/,"")+(/[.]$/.test(base.trim())?" ":". ")+ref+".";
        var nom=(ref.normalize("NFD").replace(/[̀-ͯ]/g,"").replace(/[^A-Za-z0-9]+/g,"_").replace(/^_|_$/g,"").slice(0,80)||"figure").toLowerCase();
        boite.innerHTML='<p></p><div class="citation-actions"><button type="button" data-a="cit">Copier la citation</button></div>'
          +'<ul class="exports"><li><span class="nom"><span class="genre">Image</span> de la figure</span><span class="citation-actions"><button type="button" data-a="img">Copier l&#39;image</button><button type="button" data-a="png">PNG</button><button type="button" data-a="svg">SVG</button></span></li>'
          +(f.dataset.donnees?'<li><span class="nom"><span class="genre">Données</span> de la figure, '+f.dataset.donneesNom+'</span><span class="citation-actions"><a class="bouton" download href="'+f.dataset.donnees+'">CSV</a></span></li>':'')
          +'</ul><p class="small muted">Chaque fichier porte la citation du rapport, merci de la joindre à toute reprise.</p>';
        boite.querySelector("p").textContent=texte;
        boite.querySelectorAll("button").forEach(function(b){b.onclick=function(){var a=b.dataset.a;
          if(a==="cit"){navigator.clipboard.writeText(texte).then(function(){b.textContent="Citation copiée"},function(){b.textContent="Copie impossible ici"});return}
          var src=f.querySelector(".variante:not([hidden]) svg")||f.querySelector("svg");if(!src)return;
          var svg=imageCitee(src,texte);
          if(a==="svg"){enregistrer(new Blob([svg],{type:"image/svg+xml"}),nom+".svg");b.textContent="Enregistré";return}
          var img=new Image(),url=URL.createObjectURL(new Blob([svg],{type:"image/svg+xml"}));
          img.onload=function(){var c=document.createElement("canvas");c.width=img.width;c.height=img.height;c.getContext("2d").drawImage(img,0,0);URL.revokeObjectURL(url);
            c.toBlob(function(png){if(!png)return;
              if(a==="png"){enregistrer(png,nom+".png");b.textContent="Enregistré";return}
              navigator.clipboard.write([new ClipboardItem({"image/png":png})]).then(function(){b.textContent="Image copiée"},function(){b.textContent="Copie impossible ici, utilisez PNG"})})};img.src=url}})}})}
  // cartes des fiches : les contours sont écrits une fois par page et repris par <use> ; l'export les remet en place,
  // avec les couleurs du fond clair des classes de même effectif et le motif des territoires sans valeur
  var COUL={q0:"#579891",q1:"#3B7E78",q2:"#2A6B66",q3:"#1C5652",q4:"#0D3D3B"};
  function deplier(c){
    var ns="http://www.w3.org/2000/svg";
    c.querySelectorAll("use").forEach(function(u){
      var o=document.getElementById((u.getAttribute("href")||u.getAttribute("xlink:href")||"").slice(1));if(!o){u.remove();return}
      var p=o.cloneNode(true);p.removeAttribute("id");
      [].forEach.call(u.attributes,function(a){if(a.name!=="href"&&a.name!=="xlink:href")p.setAttribute(a.name,a.value)});
      var k=(u.getAttribute("class")||"").split(" ").filter(function(x){return COUL[x]||x==="nd"})[0];
      if(k)p.setAttribute("fill",k==="nd"?"url(#hachure)":COUL[k]);
      if(u.parentNode)u.parentNode.replaceChild(p,u)});
    if(c.querySelector('[fill="url(#hachure)"]')&&!c.querySelector("#hachure")){var h=document.getElementById("hachure");
      if(h){var d=document.createElementNS(ns,"defs");d.appendChild(h.cloneNode(true));c.insertBefore(d,c.firstChild)}}}
  window.deplierCarte=deplier;
  function imageCitee(src,texte){
    var ns="http://www.w3.org/2000/svg",c=src.cloneNode(true),vb=(src.dataset.vb0||src.getAttribute("viewBox")||"0 0 600 400").split(/[ ,]+/).map(Number);
    deplier(c);
    // taille commune des exports (harmonisation, 22 octobre 2026), dessin rapporté à 800 pixels, image à 1 600, citation
    // au petit corps de l'échelle typographique (11,5 pixels à cette largeur), couleurs du fond clair (valeurs de repli
    // des variables, seules lues dans un fichier SVG isolé)
    var fs=11.5*vb[2]/800,par=Math.max(40,Math.floor((vb[2]-16)/(fs*.55))),lignes=[];
    texte.split(" ").forEach(function(m){var l=lignes.length?lignes[lignes.length-1]:null;if(l!=null&&(l+" "+m).length<=par)lignes[lignes.length-1]=l+" "+m;else lignes.push(m)});
    var hc=fs*1.4*lignes.length+fs;c.setAttribute("xmlns",ns);c.setAttribute("viewBox",[vb[0],vb[1],vb[2],vb[3]+hc].join(" "));
    c.setAttribute("width",1600);c.setAttribute("height",Math.round((vb[3]+hc)*1600/vb[2]));
    var fond=document.createElementNS(ns,"rect");fond.setAttribute("x",vb[0]);fond.setAttribute("y",vb[1]);fond.setAttribute("width",vb[2]);fond.setAttribute("height",vb[3]+hc);fond.setAttribute("fill","#FFFFFF");c.insertBefore(fond,c.firstChild);
    lignes.forEach(function(l,i){var t=document.createElementNS(ns,"text");t.setAttribute("x",vb[0]+8);t.setAttribute("y",vb[1]+vb[3]+fs*1.4*(i+1));t.setAttribute("font-size",fs);t.setAttribute("fill","#5F6675");t.setAttribute("font-family","Work Sans, Segoe UI, sans-serif");t.textContent=l;c.appendChild(t)});
    return new XMLSerializer().serializeToString(c)}
  function enregistrer(blob,nom){var a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=nom;document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(a.href)},1000)}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",citerFigures);else citerFigures();

  // tableaux des rapports et des pages, citables et exportables comme les figures (version 2, point 1, 22 octobre 2026).
  // La citation est celle du rapport (data-citation) ou de la page (data-citation-page et son adresse), suivie du titre
  // du tableau, tiré de sa légende ou de l'intertitre qui le précède (décision de Lucas, titre sans numéro). Le CSV
  // reprend les lignes affichées, au format des fichiers du site (point-virgule, virgule décimale, nombres sans
  // séparateur de milliers), avec la citation en dernière ligne.
  // adresse citée, la même que celle affichée en tête des pages (sans « .html », que GitHub Pages sert aussi)
  function adressePage(){return location.pathname.replace(/\/index\.html$/,"/").replace(/\.html$/,"")}
  function titreTableau(t){
    // titre seul, puis l'unité après une virgule (« Professionnels de santé mentale, pour 10 000 habitants »), jamais
    // collés (audit de contrôle du 30 octobre 2026, point B5)
    if(t.caption&&t.caption.textContent.trim()){var cap=t.caption.cloneNode(true),u=cap.querySelector(".unite-tel");[].forEach.call(cap.querySelectorAll(".outils-figure"),function(o){o.remove()});
      var ut=u?u.textContent.replace(/\s+/g," ").trim():"";if(u)u.remove();var ti=cap.textContent.replace(/\s+/g," ").trim();
      return ut?ti+", "+ut.charAt(0).toLowerCase()+ut.slice(1):ti}
    for(var e=t.closest(".defile")||t;e&&e.tagName!=="MAIN";e=e.parentElement){
      for(var p=e.previousElementSibling;p;p=p.previousElementSibling){
        if(/^H[2-5]$/.test(p.tagName))return p.textContent.replace(/\s+/g," ").trim();
        var h=p.querySelectorAll&&p.querySelectorAll("h2,h3,h4,h5");if(h&&h.length)return h[h.length-1].textContent.replace(/\s+/g," ").trim()}
      if(e.tagName==="DETAILS"){var s=e.querySelector("summary");if(s)return s.textContent.trim()}}
    return "Tableau"}
  function celluleCsv(c){
    // une adresse raccourcie à l'écran est écrite en entier dans le fichier
    if(c.querySelectorAll){var lien=[].filter.call(c.querySelectorAll("a[href^='http']"),function(a){return /…$/.test(a.textContent.trim())});
      if(lien.length){c=c.cloneNode(true);[].forEach.call(c.querySelectorAll("a[href^='http']"),function(a){if(/…$/.test(a.textContent.trim()))a.textContent=a.href})}}
    var v=c.textContent.replace(/[\s  ]+/g," ").trim();
    if(/^[−-]?\d{1,3}( \d{3})+(,\d+)?$/.test(v))v=v.replace(/ /g,"");
    v=v.replace(/^−(?=\d)/,"-");
    return /[;"\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v}
  function tableauCsv(t){
    return "﻿"+[].filter.call(t.querySelectorAll("tr"),function(tr){return !tr.hidden&&tr.style.display!=="none"})
      .map(function(tr){return [].map.call(tr.children,celluleCsv).join(";")}).join("\r\n")}
  function citerTableaux(){
    var main=document.querySelector("main");if(!main)return;
    var porte=document.querySelector("[data-citation]"),base;
    if(porte)base=porte.dataset.citation.replace(/\s*$/,"");
    else{base=(main.dataset.citationPage||"").replace(/\s*$/,"");if(!base)return;
      var adr=main.dataset.adresse;base+=(adr?", "+adr+adressePage():"")+"."}
    main.querySelectorAll("table").forEach(function(t){
      if(t.dataset.cite||t.closest(".citation-fig,.sommaire,details.versions,nav,figure,.encadre"))return;t.dataset.cite="1";
      var bloc=t.closest(".defile")||t;
      var ligne=document.createElement("div");ligne.className="outils-figure outils-tableau";
      var bc=document.createElement("button");bc.type="button";bc.className="citer-fig";bc.textContent="Citer et exporter";bc.setAttribute("aria-expanded","false");ligne.appendChild(bc);
      // dans les fiches, le bouton se place à droite du titre du tableau, comme dans Croiser (audit de contrôle du
      // 30 octobre 2026, point I8)
      var dansTitre=!!(t.caption&&t.closest("main.fiche"));
      if(dansTitre){ligne.classList.add("dans-titre");t.caption.appendChild(ligne)}else bloc.before(ligne);
      var boite=document.createElement("div");boite.className="citation-fig";boite.hidden=true;if(dansTitre)bloc.before(boite);else ligne.after(boite);
      bc.onclick=function(){var ouvert=boite.hidden;bc.setAttribute("aria-expanded",String(ouvert));boite.hidden=!ouvert;if(!ouvert)return;
        var titre=titreTableau(t),texte=base+(/[.]$/.test(base)?" ":". ")+"Tableau, « "+titre+" ».";
        var nom=(titre.normalize("NFD").replace(/[̀-ͯ]/g,"").replace(/[^A-Za-z0-9]+/g,"_").replace(/^_|_$/g,"").slice(0,80)||"tableau").toLowerCase();
        boite.innerHTML='<p></p><div class="citation-actions"><button type="button" data-a="cit">Copier la citation</button></div>'
          +'<ul class="exports"><li><span class="nom"><span class="genre">Données</span> du tableau, telles qu&#39;affichées</span><span class="citation-actions"><button type="button" data-a="csv">CSV</button></span></li></ul>'
          +'<p class="small muted">Le fichier porte la citation de la page, merci de la joindre à toute reprise.</p>';
        boite.querySelector("p").textContent=texte;
        boite.querySelectorAll("button").forEach(function(b){b.onclick=function(){
          if(b.dataset.a==="cit"){navigator.clipboard.writeText(texte).then(function(){b.textContent="Citation copiée"},function(){b.textContent="Copie impossible ici"});return}
          enregistrer(new Blob([tableauCsv(t)+"\r\n\r\n"+celluleCsv({textContent:texte})],{type:"text/csv;charset=utf-8"}),nom+".csv");b.textContent="Enregistré"}})}})}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",citerTableaux);else citerTableaux();

  // « Citer et exporter » de l'encadré type (fiche d'un territoire, plan de reprise, étape 2, 30 octobre 2026). Le bouton
  // .citer-encadre ouvre, sous le titre de son bloc [data-titre] : la citation en texte, en RIS et en BibTeX, l'image de
  // sa carte (PNG, SVG), les données de son tableau (CSV), le code d'intégration et l'adresse de la version (DOI des
  // données de la version quand Zenodo l'a archivée). Les éléments de la citation sont donnés par la page (#cite).
  function citerEncadres(){
    var C=document.getElementById("cite");if(!C)return;var d=C.dataset;
    var auteurBib=d.auteur.replace(/^(\S+)\s+(.+)$/,"$1, $2"),jour=new Date().toISOString().slice(0,10);
    document.querySelectorAll(".citer-encadre").forEach(function(b){
      if(b.dataset.pret)return;b.dataset.pret="1";
      var bloc=b.hasAttribute("data-tout")?null:b.closest("[data-titre]");
      var tete=bloc?(bloc.querySelector(".encadre-tete")||b.parentNode):b.parentNode;
      var boite=document.createElement("div");boite.className="citation-fig";boite.hidden=true;tete.after(boite);
      b.onclick=function(){var ouvert=boite.hidden;b.setAttribute("aria-expanded",String(ouvert));boite.hidden=!ouvert;if(!ouvert)return;
        var h=bloc&&(bloc.id?bloc:bloc.querySelector("[id]")),ancre=h?h.id:"";
        var titre=d.titre+(bloc?", « "+bloc.dataset.titre+" »":""),url=d.adresse+(ancre?"#"+ancre:"");
        var texte=d.auteur+" ("+d.annee+"). "+titre+". "+d.projet+", version du "+d.version+", "+url.replace(/^https:\/\//,"")+(d.doi?", doi:"+d.doi:d.doiGeneral?", toutes les versions doi:"+d.doiGeneral:"")+".";
        var ris=["TY  - DATA","AU  - "+auteurBib,"PY  - "+d.annee,"TI  - "+titre,"PB  - "+d.projet,"ET  - version du "+d.version,"UR  - "+url]
          .concat(d.doi?["DO  - "+d.doi]:[]).concat(["Y2  - "+jour,"LA  - fr","ER  - "]).join("\r\n");
        var cle=("ubicura_"+d.cle+"_"+d.iso).replace(/[^A-Za-z0-9_]+/g,"_");
        var bib="@misc{"+cle+",\n  author = {"+auteurBib+"},\n  title = {"+titre+"},\n  year = {"+d.annee+"},\n  publisher = {"+d.projet+"},\n  version = {version du "+d.version+"},\n  url = {"+url+"},\n"+(d.doi?"  doi = {"+d.doi+"},\n":"")+"  urldate = {"+jour+"},\n  language = {french}\n}";
        var integ='<iframe src="'+url+'" title="'+titre.replace(/"/g,"&quot;")+'" width="100%" height="560" loading="lazy" style="border:0"></iframe>\n<p>'+texte.replace(/</g,"&lt;")+"</p>";
        // la carte exportée est celle qui est montrée (carte de bloc de la fiche : une carte par indicateur choisi)
        var svgs=bloc?[].slice.call(bloc.querySelectorAll("svg.carte-svg")):[],svg=svgs.filter(function(x){return x.getBoundingClientRect().width>0})[0]||svgs[0],tab=bloc&&bloc.querySelector("table");
        var nom=(titre.normalize("NFD").replace(/[̀-ͯ]/g,"").replace(/[^A-Za-z0-9]+/g,"_").replace(/^_|_$/g,"").slice(0,80)||"ubicura").toLowerCase();
        boite.innerHTML='<p class="cit"></p><div class="citation-actions"><button type="button" data-a="cit">Copier la citation</button><button type="button" data-a="ris">RIS</button><button type="button" data-a="bib">BibTeX</button></div>'
          +'<ul class="exports">'
          +(svg?'<li><span class="nom"><span class="genre">Image</span> de la carte</span><span class="citation-actions"><button type="button" data-a="png">PNG</button><button type="button" data-a="svg">SVG</button></span></li>':"")
          +(tab?'<li><span class="nom"><span class="genre">Données</span> du tableau, telles qu&#39;affichées</span><span class="citation-actions"><button type="button" data-a="csv">CSV</button></span></li>':"")
          +'<li><span class="nom"><span class="genre">Intégrer</span> dans une page, ouverte sur ce bloc</span><span class="citation-actions"><button type="button" data-a="int">Copier le code</button></span></li>'
          +'<li><span class="nom"><span class="genre">Adresse</span> <a href="'+url+'">'+url.replace(/^https:\/\//,"")+"</a>"+(d.doi?', version archivée <a href="https://doi.org/'+d.doi+'">doi:'+d.doi+"</a>":"")+(d.doiGeneral?(d.doi?', voir aussi toutes les versions':', toutes les versions')+' <a href="https://doi.org/'+d.doiGeneral+'">doi:'+d.doiGeneral+"</a>":"")+"</span></li>"
          +'</ul><p class="small muted">Chaque fichier porte la citation, merci de la joindre à toute reprise.</p>';
        boite.querySelector("p.cit").textContent=texte;
        if(!bloc){var pre=document.createElement("pre");pre.textContent=ris+"\n\n"+bib;boite.querySelector(".citation-actions").after(pre)}
        boite.querySelectorAll("button").forEach(function(x){x.onclick=function(){var a=x.dataset.a;
          var copier=function(s,ok){navigator.clipboard.writeText(s).then(function(){x.textContent=ok},function(){x.textContent="Copie impossible ici"})};
          if(a==="cit")return copier(texte,"Citation copiée");
          if(a==="int")return copier(integ,"Code copié");
          if(a==="ris"){enregistrer(new Blob([ris],{type:"application/x-research-info-systems"}),nom+".ris");x.textContent="Enregistré";return}
          if(a==="bib"){enregistrer(new Blob([bib],{type:"application/x-bibtex"}),nom+".bib");x.textContent="Enregistré";return}
          if(a==="csv"){enregistrer(new Blob([tableauCsv(tab)+"\r\n\r\n"+celluleCsv({textContent:texte})],{type:"text/csv;charset=utf-8"}),nom+".csv");x.textContent="Enregistré";return}
          var image=imageCitee(svg,texte);
          if(a==="svg"){enregistrer(new Blob([image],{type:"image/svg+xml"}),nom+".svg");x.textContent="Enregistré";return}
          var img=new Image(),u=URL.createObjectURL(new Blob([image],{type:"image/svg+xml"}));
          img.onload=function(){var cv=document.createElement("canvas");cv.width=img.width;cv.height=img.height;cv.getContext("2d").drawImage(img,0,0);URL.revokeObjectURL(u);
            cv.toBlob(function(png){if(png){enregistrer(png,nom+".png");x.textContent="Enregistré"}})};img.src=u}})}})
    // « Citer cette fiche », en fin de page : tous les formats montrés d'emblée
    document.querySelectorAll(".citer-encadre[data-ouvert]").forEach(function(b){if(b.getAttribute("aria-expanded")!=="true")b.click()})}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",citerEncadres);else citerEncadres();

  // Réglettes : chaque étiquette (ensemble, médiane) reste dans sa réglette ; près d'un bord, elle glisse vers
  // l'intérieur au lieu de sortir de sa cellule (« médiane : aucune structure » au téléphone ; reprise de lisibilité
  // du 31 octobre 2026). Refait quand la largeur change ou qu'un repli s'ouvre.
  function etiquettesReglettes(){
    // la part des territoires sans inscrit : sur sa barre, ou dans l'étiquette de la médiane si celle de l'ensemble la touche
    document.querySelectorAll(".rg").forEach(function(rg){var z=rg.querySelector(".rg-aucun"),p=rg.querySelector(".rg-part");
      if(!z||!p||!rg.getBoundingClientRect().width)return;z.hidden=false;p.hidden=true;rg.classList.remove("deux");
      var a=z.getBoundingClientRect(),e=rg.querySelector(".rg-lab.haut:not(.rg-aucun)"),b=e&&e.getBoundingClientRect();
      if(b&&Math.min(a.right,b.right)-Math.max(a.left,b.left)>-6){z.hidden=true;p.hidden=false;rg.classList.add("deux")}});
    document.querySelectorAll(".rg").forEach(function(rg){var R=rg.getBoundingClientRect();if(!R.width)return;
      rg.querySelectorAll(".rg-lab").forEach(function(l){l.style.marginLeft="";var a=l.getBoundingClientRect(),d=0;
        if(a.left<R.left)d=R.left-a.left;else if(a.right>R.right)d=R.right-a.right;
        if(d)l.style.marginLeft=d.toFixed(1)+"px"})})}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",etiquettesReglettes);else etiquettesReglettes();
  addEventListener("load",etiquettesReglettes);addEventListener("resize",etiquettesReglettes);
  document.addEventListener("toggle",function(){requestAnimationFrame(etiquettesReglettes)},true);
  if(document.fonts)document.fonts.ready.then(etiquettesReglettes);

  // « Comment lire » des encadrés : toujours entier, jamais replié derrière « Lire la suite » (règles du projet, partie 6 : ce
  // qui explique reste visible ; défaut P1 relevé par le prototype de la fiche resserrée, 1er novembre 2026)

  // « Comment lire » des rapports et des pages de domaine : toujours affiché sous sa figure ou son tableau, sans bouton
  // (décision de Lucas du 5 novembre 2026 ; le repli au clic du 22 octobre est retiré, audit du 6 novembre 2026)

  // longs tableaux de consultation (pages de la méthode), un champ filtre les lignes à mesure qu'on tape
  function filtres(){
    document.querySelectorAll("table.filtrable").forEach(function(t){
      if(t.dataset.filtre)return;t.dataset.filtre="1";var bloc=t.closest(".defile")||t;
      var l=document.createElement("label");l.className="filtre-tableau";l.innerHTML='<span>Filtrer le tableau</span><input type="search" autocomplete="off">';
      var ligne=bloc.previousElementSibling&&bloc.previousElementSibling.classList.contains("citation-fig")?bloc.previousElementSibling:bloc;ligne.before(l);
      var n=document.createElement("span");n.className="small muted";l.appendChild(n);
      var champ=l.querySelector("input"),lignes=[].slice.call(t.tBodies[0]?t.tBodies[0].rows:[]);
      var norm=function(x){return x.normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase()};
      champ.addEventListener("input",function(){var q=norm(champ.value.trim()),k=0;
        lignes.forEach(function(r){var ok=!q||norm(r.textContent).indexOf(q)>=0;r.hidden=!ok;if(ok)k++});
        n.textContent=q?k+" ligne"+(k>1?"s":"")+" sur "+lignes.length:""})})}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",filtres);else filtres();
})();

// Figures qui apparaissent en douceur quand on arrive dessus (refonte du 23 octobre 2026). La classe posée sur la racine
// n'existe qu'avec le script, si bien qu'une figure reste visible quand il ne tourne pas ; impression exclue.
(function(){
  if(!("IntersectionObserver" in window)||matchMedia("print").matches)return;
  const cibles=document.querySelectorAll("figure.graphique,.une-carte");if(!cibles.length)return;
  document.documentElement.classList.add("revele");
  const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add("vu");io.unobserve(e.target)}}),{rootMargin:"0px 0px -8% 0px"});
  cibles.forEach(c=>io.observe(c));
  addEventListener("beforeprint",()=>cibles.forEach(c=>c.classList.add("vu")));
})();
// en-tête qui se resserre en barre flottante dès qu'on descend (essai du 23 octobre 2026, d'après reactbits.dev)
// classe « resserree » et non « defile », que .defile{overflow-x:auto} des tableaux rognait (liste « Le projet » cachée)
(function(){var n=document.querySelector("nav.site");if(!n)return;
  var f=function(){n.classList.toggle("resserree",(window.scrollY||0)>12)};f();addEventListener("scroll",f,{passive:true})})();
// fenêtres repliables façon macOS (demandes de Lucas des 23 et 28 octobre 2026), pour tout élément .fenetre.repliable
// qui porte une barre .fen-tete et un corps .fen-corps. Deux boutons sobres à droite de la barre, comme sous Windows
// (choix de Lucas du 28 octobre 2026, les trois pastilles en couleur à gauche faisaient trop), replier ou déplier, et
// agrandir à la largeur de l'écran (Échap pour revenir). Double clic sur la barre, replier. Une fenêtre
// repliée garde son titre et sa phrase de résultat (copie de son .resultat). État gardé dans le navigateur du lecteur,
// commodité seulement, jamais dans l'adresse, pour qu'un lien partagé ouvre toujours la fenêtre qu'il vise.
(function(){
  var fens=[].slice.call(document.querySelectorAll(".fenetre.repliable"));if(!fens.length)return;
  var CLE="fenetres-repliees:"+location.pathname,etat={};
  try{etat=JSON.parse(localStorage.getItem(CLE)||"{}")}catch(e){}
  function garder(){try{localStorage.setItem(CLE,JSON.stringify(etat))}catch(e){}}
  function titre(f){var h=f.querySelector(".fen-tete h2,.fen-tete h3");return h?h.textContent.trim():"cette fenêtre"}
  // symboles dessinés au trait, de la couleur du texte, nets à toutes les tailles
  var svg=function(d){return '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="'+d+'" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'};
  var ICONE={moins:svg("M3 7h8"),plus:svg("M3 7h8M7 3v8"),agrandir:svg("M8.5 2.5h3v3M11.5 2.5L8 6M5.5 11.5h-3v-3M2.5 11.5L6 8"),
    reduire:svg("M11.5 2.5L8 6M8 3v3h3M2.5 11.5L6 8M6 11V8H3")};
  function poser(f,replie,memo){
    f.classList.toggle("repliee",replie);var b=f.querySelector(".p-replier");
    b.setAttribute("aria-expanded",String(!replie));b.innerHTML=replie?ICONE.plus:ICONE.moins;
    b.setAttribute("aria-label",(replie?"Déplier":"Replier")+" la fenêtre « "+titre(f)+" »");
    if(replie&&f.classList.contains("agrandie"))agrandir(f,false);
    if(memo!==false){if(replie)etat[f.id]=1;else delete etat[f.id];garder()}
    document.querySelectorAll('a[href^="#'+f.id+'"]').forEach(function(a){a.classList.toggle("vers-repliee",replie)});
    if(!replie)dispatchEvent(new CustomEvent("fenetre",{detail:f}))}
  function agrandir(f,oui){
    f.classList.remove("agrandie");f.style.removeProperty("--deborde-g");f.style.removeProperty("--deborde-d");
    if(oui){var r=f.getBoundingClientRect(),w=document.documentElement.clientWidth;
      f.style.setProperty("--deborde-g",Math.max(0,r.left-16)+"px");f.style.setProperty("--deborde-d",Math.max(0,w-r.right-16)+"px");
      f.classList.add("agrandie")}
    var b=f.querySelector(".p-agrandir");b.setAttribute("aria-pressed",String(oui));b.innerHTML=oui?ICONE.reduire:ICONE.agrandir;
    b.setAttribute("aria-label",(oui?"Rendre à la fenêtre « ":"Agrandir la fenêtre « ")+titre(f)+(oui?" » sa largeur":" » à la largeur de l'écran"));
    dispatchEvent(new CustomEvent("fenetre",{detail:f}))}
  function resume(f){var r=f.querySelector(".fen-corps .resultat"),c=f.querySelector(".fen-resume");if(r&&c)c.textContent=r.textContent.replace(/­/g,"")}
  fens.forEach(function(f){
    var corps=f.querySelector(".fen-corps"),tete=f.querySelector(".fen-tete"),p=tete&&tete.querySelector(".pastilles");if(!corps||!p)return;
    corps.id=corps.id||f.id+"-corps";var t=titre(f);
    p.innerHTML='<button type="button" class="p-agrandir" aria-pressed="false" aria-label="Agrandir la fenêtre « '+t+' » à la largeur de l&#39;écran">'+ICONE.agrandir+'</button>'
      +'<button type="button" class="p-replier" aria-controls="'+corps.id+'"></button>';
    p.querySelector(".p-replier").onclick=function(){poser(f,!f.classList.contains("repliee"))};
    p.querySelector(".p-agrandir").onclick=function(){if(f.classList.contains("repliee"))poser(f,false);agrandir(f,!f.classList.contains("agrandie"))};
    tete.addEventListener("dblclick",function(e){if(!e.target.closest("button,a,input,select"))poser(f,!f.classList.contains("repliee"))});
    var r=corps.querySelector(".resultat");if(r){resume(f);new MutationObserver(function(){resume(f)}).observe(r,{childList:true,characterData:true,subtree:true})}
    // « Comment lire » de la barre, ouvre la note de lecture rangée en tête du corps
    var bl=tete.querySelector(".fen-lire-bouton"),nl=f.querySelector(".fen-lire");
    // toujours visible, comme sur la fiche (règles du projet, partie 6 ; décision de Lucas du 5 novembre 2026) : la note
    // est montrée et le bouton qui la dépliait disparaît
    if(nl){nl.hidden=false;var figs=corps.querySelectorAll("figure");if(figs.length)figs[figs.length-1].after(nl)}if(bl)bl.remove();   // sous la dernière figure, le résultat d'abord
    poser(f,!!etat[f.id],false)});
  // un lien vers une fenêtre repliée la déplie, l'adresse d'une vue partagée aussi (#paires?pA=…)
  function viser(){var id=decodeURIComponent((location.hash||"").slice(1).split("?")[0]);if(!id)return;
    var f=document.getElementById(id);if(f&&f.classList.contains("repliee"))poser(f,false)}
  viser();addEventListener("hashchange",viser);
  // le navigateur ne trouve pas l'ancre d'une vue partagée (#iFenEntonnoir?iProf=…), la page y descend donc elle-même,
  // une fois les figures dessinées pour que la position soit juste
  // (sans quoi le navigateur remet la page à la position qu'il avait gardée)
  if((location.hash||"").indexOf("?")>=0&&"scrollRestoration" in history)history.scrollRestoration="manual";
  addEventListener("load",function(){var h=location.hash||"";if(h.indexOf("?")<0)return;
    var el=document.getElementById(decodeURIComponent(h.slice(1).split("?")[0]));
    if(el)setTimeout(function(){el.scrollIntoView({block:"start"})},0)});
  document.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest('a[href^="#"]');if(!a)return;
    var f=document.getElementById(a.getAttribute("href").slice(1).split("?")[0]);if(f&&f.classList.contains("repliee"))poser(f,false)});
  document.addEventListener("keydown",function(e){if(e.key==="Escape")fens.forEach(function(f){if(f.classList.contains("agrandie"))agrandir(f,false)})});
  addEventListener("resize",function(){fens.forEach(function(f){if(f.classList.contains("agrandie"))agrandir(f,true)})});
  window.fenetres={toutes:function(replie){fens.forEach(function(f){poser(f,replie)})}};
  document.querySelectorAll("[data-fenetres]").forEach(function(b){b.onclick=function(){window.fenetres.toutes(b.dataset.fenetres==="replier")}});
})();
