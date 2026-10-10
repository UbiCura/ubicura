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
    var hote=s.closest("figure");
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
})();
