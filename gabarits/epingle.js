// « Ton territoire partout » (plan de reprise de la présentation, étape 2, idée 2, 30 octobre 2026). Le lecteur épingle
// un territoire depuis sa fiche, ou deux pour les comparer. Ils restent dans l'en-tête de chaque page, sont cernés sur
// chaque carte qui porte leurs contours (<use href="#gE200090561"> des fiches, data-t="epci:200090561" des autres cartes)
// et marqués dans les figures qui portent data-t. L'état est gardé dans le navigateur du lecteur, sans compte, ou donné
// par l'adresse (?epingle=epci:200090561,dep:18), si bien qu'un lien partagé ouvre la même lecture.
(function(){
  var CLE="territoires-epingles",LETTRE={epci:"E",dep:"D",reg:"R"},racine=document.documentElement.getAttribute("data-racine")||"";
  function lire(){try{var v=JSON.parse(localStorage.getItem(CLE)||"[]");return Array.isArray(v)?v.filter(function(x){return x&&/^(epci|dep|reg):\w+$/.test(x.t)}).slice(0,2):[]}catch(e){return []}}
  function ecrire(v){try{localStorage.setItem(CLE,JSON.stringify(v.slice(0,2)))}catch(e){}}
  function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
  function fiche(t){var p=t.split(":");return racine+"territoire/"+p[0]+"/"+p[1]+".html"}
  var ep=lire();
  // adresse partagée : elle remplace les territoires épinglés, les noms viennent de l'index de recherche du site
  var m=/[?&]epingle=([^&#]+)/.exec(location.search);
  if(m){var ts=decodeURIComponent(m[1]).split(",").filter(function(x){return /^(epci|dep|reg):\w+$/.test(x)}).slice(0,2);
    if(ts.length){var connus={};ep.forEach(function(x){connus[x.t]=x.nm});ep=ts.map(function(t){return {t:t,nm:connus[t]||t}});ecrire(ep);
      if(ep.some(function(x){return x.nm===x.t}))fetch(racine+"presentation/recherche.json").then(function(r){return r.json()}).then(function(R){
        ep.forEach(function(x){var p=x.t.split(":"),l=(R.territoires||{})[p[0]]||[];for(var i=0;i<l.length;i++)if(l[i][0]===p[1]){x.nm=l[i][1];break}});ecrire(ep);maj()}).catch(function(){})}}
  function marquer(){
    document.querySelectorAll(".epingle,.epingle-2").forEach(function(e){e.classList.remove("epingle","epingle-2")});
    ep.forEach(function(x,i){var p=x.t.split(":"),cl=i?"epingle-2":"epingle";
      document.querySelectorAll('svg use[href="#g'+LETTRE[p[0]]+p[1]+'"]:not(.choisi),[data-t="'+x.t+'"]').forEach(function(e){e.classList.add(cl)})})}
  function nav(){
    var n=document.getElementById("epingle-nav");if(!n)return;n.hidden=!ep.length;if(!ep.length){n.innerHTML="";return}
    var h=(ep.length>1?"Mes territoires":"Mon territoire")+" "+ep.map(function(x,i){return '<a href="'+fiche(x.t)+'">'+esc(x.nm)+'</a><button type="button" data-retirer="'+i+'" aria-label="Ne plus épingler '+esc(x.nm)+'">×</button>'}).join(" ");
    if(ep.length>1)h+=' <a href="'+racine+"comparer.html#t="+ep.map(function(x){return x.t}).join(",")+'">Comparer</a>';
    n.innerHTML=h;
    n.querySelectorAll("[data-retirer]").forEach(function(b){b.onclick=function(){ep.splice(+b.dataset.retirer,1);ecrire(ep);maj()}})}
  function boutons(){
    document.querySelectorAll("[data-epingle]").forEach(function(b){
      var t=b.dataset.epingle,oui=ep.some(function(x){return x.t===t});
      b.setAttribute("aria-pressed",String(oui));b.textContent=oui?"Territoire épinglé":"Épingler ce territoire";
      b.onclick=function(){var i=ep.findIndex(function(x){return x.t===t});
        if(i>=0)ep.splice(i,1);else{ep.unshift({t:t,nm:b.dataset.nom});ep=ep.slice(0,2)}ecrire(ep);maj()}});
    // sur une fiche, un autre territoire épinglé propose la comparaison des deux
    var c=document.querySelector(".epingle-comparer"),moi=document.querySelector("[data-epingle]");
    if(c&&moi){var autre=ep.filter(function(x){return x.t!==moi.dataset.epingle})[0];c.hidden=!autre;
      if(autre)c.innerHTML='Vous avez aussi épinglé <a href="'+fiche(autre.t)+'">'+esc(autre.nm)+'</a>, <a href="'+racine+"comparer.html#t="+moi.dataset.epingle+","+autre.t+'">comparer les deux territoires</a>.'}}
  function maj(){nav();boutons();marquer()}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",maj);else maj();
  addEventListener("storage",function(e){if(e.key===CLE){ep=lire();maj()}});
  window.epingle={territoires:function(){return ep.slice()},marquer:marquer};
})();
