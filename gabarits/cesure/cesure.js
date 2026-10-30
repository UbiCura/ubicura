// Césure française du texte justifié (refonte du 23 octobre 2026, demande de Lucas). Le navigateur ne coupe pas les
// mots français sous Windows, si bien qu'un texte justifié laisse de grands blancs entre les mots. Les règles de césure
// de TeX (module hyphen, licence ISC, texte joint) placent des césures possibles invisibles, dont on écarte les coupures
// ridicules : mots de moins de sept lettres, moins de trois lettres d'un côté de la coupure, noms propres, sigles,
// nombres. Seul le texte justifié est traité ; tableaux, titres, légendes et boutons ne le sont jamais.
(function(){
  if(!window.createHyphenator||!window.hyphenationPatternsFr)return;
  var SH="­",couperBrut=createHyphenator(hyphenationPatternsFr,{hyphenChar:SH,minWordLength:7});
  var MOT=/[A-Za-zÀ-ÖØ-öø-ÿŒœÆæ]+(?:['’][A-Za-zÀ-ÖØ-öø-ÿŒœÆæ]+)?/g,MAJ=/^[A-ZÀ-ÖØ-ÞŒÆ]/;
  var EXCLUS="table,nav.site,code,pre,svg,figcaption,button,select,h1,h2,h3,h4,h5,h6,.legende,.tip,#bulle,.sommaire";
  function couper(w){
    if(w.length<7||MAJ.test(w))return w;
    var parts=couperBrut(w).split(SH);if(parts.length<2)return w;
    var out=parts[0],avant=parts[0].length;
    for(var i=1;i<parts.length;i++){if(avant>=3&&w.length-avant>=3)out+=SH;out+=parts[i];avant+=parts[i].length}
    return out}
  function traiter(racine){
    if(!racine)return;
    var parents=new Map(),tw=document.createTreeWalker(racine,NodeFilter.SHOW_TEXT),n,noeuds=[];
    while((n=tw.nextNode())){var p=n.parentElement;if(!p||n.nodeValue.length<7||n.nodeValue.indexOf(SH)>=0)continue;
      var ok=parents.get(p);if(ok===undefined){ok=!p.closest(EXCLUS)&&getComputedStyle(p).textAlign==="justify";parents.set(p,ok)}
      if(ok)noeuds.push(n)}
    noeuds.forEach(function(t){var v=t.nodeValue.replace(MOT,couper);if(v!==t.nodeValue)t.nodeValue=v})}
  window.cesure=traiter;
  function lancer(){traiter(document.querySelector("main")||document.body)}
  // les césures invisibles ne partent ni dans un copier-coller ni dans une impression (le PDF les garderait dans son
  // texte, qui se copierait abîmé, audit externe du 30 octobre 2026) ; elles reviennent après l'impression
  function retirer(){var tw=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),n;
    while((n=tw.nextNode()))if(n.nodeValue.indexOf(SH)>=0)n.nodeValue=n.nodeValue.split(SH).join("")}
  document.addEventListener("copy",function(e){var s=window.getSelection(),t=s?String(s):"";
    if(t.indexOf(SH)<0||!e.clipboardData)return;e.clipboardData.setData("text/plain",t.split(SH).join(""));e.preventDefault()});
  window.addEventListener("beforeprint",retirer);
  window.addEventListener("afterprint",lancer);
  if("requestIdleCallback" in window)requestIdleCallback(lancer,{timeout:1200});else setTimeout(lancer,150);
})();
