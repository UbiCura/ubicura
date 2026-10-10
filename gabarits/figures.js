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
  document.addEventListener("wheel",function(ev){
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

  // figures des rapports, même modèle que l'atlas (10 octobre 2026). Sous le titre « Figure N. légende », une ligne
  // « Citer et exporter » ouvre la citation du rapport suivie du numéro et de la légende, l'image (copie, PNG, SVG, avec
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
        var num=cap&&cap.querySelector("strong"),leg=cap&&cap.querySelector(".leg");
        var ref=(num?num.textContent.replace(/\.$/,""):"Figure")+(leg?", "+leg.textContent.trim():"");
        var texte=base.replace(/\s*$/,"")+(/[.]$/.test(base.trim())?" ":". ")+ref+".";
        var nom=(ref.normalize("NFD").replace(/[̀-ͯ]/g,"").replace(/[^A-Za-z0-9]+/g,"_").replace(/^_|_$/g,"").slice(0,80)||"figure").toLowerCase();
        boite.innerHTML='<p></p><div class="citation-actions"><button type="button" data-a="cit">Copier la citation</button></div>'
          +'<ul class="exports"><li><span class="nom"><span class="genre">Image</span> de la figure</span><span class="citation-actions"><button type="button" data-a="img">Copier l’image</button><button type="button" data-a="png">PNG</button><button type="button" data-a="svg">SVG</button></span></li>'
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
  function imageCitee(src,texte){
    var ns="http://www.w3.org/2000/svg",c=src.cloneNode(true),vb=(src.dataset.vb0||src.getAttribute("viewBox")||"0 0 600 400").split(/[ ,]+/).map(Number);
    var fs=Math.max(10,vb[2]/70),par=Math.max(40,Math.floor((vb[2]-16)/(fs*.52))),lignes=[];
    texte.split(" ").forEach(function(m){var l=lignes.length?lignes[lignes.length-1]:null;if(l!=null&&(l+" "+m).length<=par)lignes[lignes.length-1]=l+" "+m;else lignes.push(m)});
    var hc=fs*1.4*lignes.length+fs;c.setAttribute("xmlns",ns);c.setAttribute("viewBox",[vb[0],vb[1],vb[2],vb[3]+hc].join(" "));
    c.setAttribute("width",vb[2]*2);c.setAttribute("height",(vb[3]+hc)*2);
    var fond=document.createElementNS(ns,"rect");fond.setAttribute("x",vb[0]);fond.setAttribute("y",vb[1]);fond.setAttribute("width",vb[2]);fond.setAttribute("height",vb[3]+hc);fond.setAttribute("fill","#FFFFFF");c.insertBefore(fond,c.firstChild);
    lignes.forEach(function(l,i){var t=document.createElementNS(ns,"text");t.setAttribute("x",vb[0]+8);t.setAttribute("y",vb[1]+vb[3]+fs*1.4*(i+1));t.setAttribute("font-size",fs);t.setAttribute("fill","#555555");t.setAttribute("font-family","Work Sans, Segoe UI, sans-serif");t.textContent=l;c.appendChild(t)});
    return new XMLSerializer().serializeToString(c)}
  function enregistrer(blob,nom){var a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=nom;document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(a.href)},1000)}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",citerFigures);else citerFigures();
})();
