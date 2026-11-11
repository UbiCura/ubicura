// Césure française du texte justifié (refonte du 23 octobre 2026, demande de Lucas ; le texte est justifié partout depuis
// la décision du 30 octobre 2026). Le navigateur ne coupe pas les mots français sous Windows, si bien qu'un texte
// justifié laisse de grands blancs entre les mots. Les règles de césure de TeX (module hyphen, licence ISC, texte
// joint) placent des césures possibles invisibles, dont on écarte les coupures ridicules : mots de moins de sept
// lettres, moins de trois lettres d'un côté de la coupure, noms propres, sigles, nombres. Seul le texte justifié est
// traité ; tableaux, titres, légendes, sommaires, infobulles et boutons ne le sont jamais. Au plus trois lignes coupées
// de suite (hyphenate-limit-lines, que les navigateurs n'appliquent pas à une césure posée par script) : une fois la
// page composée, la quatrième coupure d'affilée est retirée.
// Une adresse ou un DOI n'est jamais coupé (« 10.5281/zeno-do » dans l'en-tête de la fiche, 1er novembre 2026).
// Espaces insécables du français dans le texte écrit par les scripts après le chargement (Indicateurs, Explorer,
// atlas, Croiser, Comparer, Chercher), mêmes règles que pipeline/typographie.py pour les pages : « pour 10 / 000 » et
// un guillemet seul se coupaient en fin de ligne au téléphone (relecture indépendante du 11 novembre 2026, 2.4). Ni les
// figures (svg), ni les scripts, ni les champs de saisie ne sont touchés.
(function(){
  var NB="\u00a0",FI="\u202f",HORS="script,style,code,pre,textarea,svg,input,select,option";
  var R=[[/«[ \u00a0\u202f]+/g,"«"+NB],[/[ \u00a0\u202f]+»/g,NB+"»"],
    [/(\S) +(?=[;!?](?:\s|$))/g,"$1"+FI],[/([\w\)»%]) +(?=:(?:\s|$))/g,"$1"+FI],
    [/(\d) +(?=(?:%|‰|€|km|px|h|min|ans?|pour)\b|%|‰|€)/g,"$1"+NB],[/(\d) (?=\d{3}\b)/g,"$1"+FI],
    [/(\d) (?=[a-zàâçéèêëîïôûùüÿœæ]{1,8}(?![a-zàâçéèêëîïôûùüÿœæ]))/g,"$1"+NB],[/([a-zéû]) (?=(?:19|20)\d\d\b)/g,"$1"+NB]];
  function fixer(t){var v=t.nodeValue;if(!v||v.indexOf(" ")<0)return;var p=t.parentElement;if(!p||p.closest(HORS))return;
    var w=v;for(var i=0;i<R.length;i++)w=w.replace(R[i][0],R[i][1]);if(w!==v)t.nodeValue=w}
  function traiter(n){if(!n)return;if(n.nodeType===3){fixer(n);return}if(n.nodeType!==1||n.closest&&n.closest(HORS))return;
    var tw=document.createTreeWalker(n,NodeFilter.SHOW_TEXT),x,l=[];while((x=tw.nextNode()))l.push(x);l.forEach(fixer)}
  window.insecables=traiter;
  function lancer(){traiter(document.body);
    new MutationObserver(function(ms){ms.forEach(function(m){if(m.type==="characterData")fixer(m.target);
      else m.addedNodes.forEach(traiter)})}).observe(document.body,{childList:true,subtree:true,characterData:true})}
  if(document.body)lancer();else document.addEventListener("DOMContentLoaded",lancer);
})();
(function(){
  if(!window.createHyphenator||!window.hyphenationPatternsFr)return;
  var SH="­",couperBrut=createHyphenator(hyphenationPatternsFr,{hyphenChar:SH,minWordLength:6});
  var MOT=/[A-Za-zÀ-ÖØ-öø-ÿŒœÆæ]+(?:['’][A-Za-zÀ-ÖØ-öø-ÿŒœÆæ]+)?/g,MAJ=/^[A-ZÀ-ÖØ-ÞŒÆ]/;
  var EXCLUS="table,nav.site,code,pre,svg,figcaption,button,select,h1,h2,h3,h4,h5,h6,.legende,.legende-cat,.legende-barre,.tip,#bulle,#glo-bulle,.bulle-fig,.sommaire,.titres-constats,.citation-fig,a[href^='http']";
  function couper(w){
    if(w.length<6||MAJ.test(w))return w;
    var parts=couperBrut(w).split(SH);if(parts.length<2)return w;
    var out=parts[0],avant=parts[0].length;
    for(var i=1;i<parts.length;i++){if(avant>=3&&w.length-avant>=2)out+=SH;out+=parts[i];avant+=parts[i].length}
    return out}
  function traiter(racine){
    if(!racine)return;
    var parents=new Map(),tw=document.createTreeWalker(racine,NodeFilter.SHOW_TEXT),n,noeuds=[];
    while((n=tw.nextNode())){var p=n.parentElement;if(!p||n.nodeValue.length<7||n.nodeValue.indexOf(SH)>=0)continue;
      var ok=parents.get(p);if(ok===undefined){ok=!p.closest(EXCLUS)&&getComputedStyle(p).textAlign==="justify";parents.set(p,ok)}
      if(ok)noeuds.push(n)}
    noeuds.forEach(function(t){var v=t.nodeValue.replace(MOT,couper);if(v!==t.nodeValue)t.nodeValue=v});
    var blocs=new Set();noeuds.forEach(function(t){var b=t.parentElement.closest("p,li,dd,blockquote,summary");if(b)blocs.add(b)});
    blocs.forEach(finale);blocs.forEach(limiter);blocs.forEach(espacer)}
  // le dernier mot d'un paragraphe ne se coupe pas en laissant moins de six lettres sur la dernière ligne :
  // « intercommunali- / tés. » laissait quatre lettres seules (relecture des fiches du 1er novembre 2026, mineur 9). Une
  // coupure plus haute reste permise (« psy- / chiatre. »), sans quoi une ligne de deux qui finit sur un mot long ne
  // trouve aucune coupure et reste lâche (contrôle de mise en page du 7 novembre 2026, page santé mentale)
  function finale(b){var tw=document.createTreeWalker(b,NodeFilter.SHOW_TEXT),n,d=null;while((n=tw.nextNode()))if(n.nodeValue.trim())d=n;
    if(!d)return;var v=d.nodeValue,m=v.match(/[^\s ]+[\s ]*$/);if(!m||m[0].indexOf(SH)<0)return;
    var p=m[0].split(SH),out=p[0];
    for(var i=1;i<p.length;i++){var reste=p.slice(i).join("").replace(/[^A-Za-zÀ-ÖØ-öø-ÿŒœÆæ]/g,"");out+=(reste.length>=6?SH:"")+p[i]}
    d.nodeValue=v.slice(0,m.index)+out}
  // à l'impression seulement (le choix du papier reste à trancher) : les paragraphes d'une même famille (les constats,
  // les phrases des encadrés, de même classe et de même parent) ont un seul alignement, à gauche si la moitié au moins
  // sont trop lâches ou courts, justifiés sinon
  function familles(blocs,cle){
    cle=cle||"aligne";
    var fam={};blocs.forEach(function(b){if(b.dataset[cle]===undefined)return;var k=b.className+"|"+(b.parentElement?b.parentElement.className:"");(fam[k]=fam[k]||[]).push(b)});
    Object.keys(fam).forEach(function(k){var l=fam[k];if(l.length<2)return;var g=l.filter(function(b){return b.dataset[cle]==="1"}).length;
      var gauche=g*2>=l.length;l.forEach(function(b){b.style.textAlign=gauche?"left":""})})}
  // à l'écran, seul un paragraphe de moins de trois lignes passe à gauche (avec les colonnes de moins de 560 px, réglées
  // par la feuille de style) ; une ligne justifiée dont les mots s'écartent de plus d'une fois et demie l'espace
  // ordinaire ne change pas l'alignement : elle est notée (data-lache) pour le contrôle de finition, et corrigée dans le
  // texte ou la mise en page (décision du 31 octobre 2026). Avant de la noter, le script essaie un léger réglage de
  // l'espace entre les mots du paragraphe (REGLAGES, en em, du plus petit au plus grand), qui déplace les coupures,
  // comme le fait un compositeur : le premier qui ne laisse aucune ligne lâche est gardé. Mesuré une fois la page
  // composée, refait quand la largeur change.
  var COLONNE_MIN=560,mesureur=document.createElement("canvas").getContext("2d"),LACHE=1.5,REGLAGES=[-.01,.01,-.02,.02,-.03,.03,-.04,-.05,-.06,-.08,-.1,-.12,-.15],APPROCHES=[-.005,.005,-.01,.01,-.015],BLANC=/[ \u00a0\t\n\r]+/;
  // une ligne lâche : dans un paragraphe dont l'espace moyen dépasse LACHE, chaque ligne au-delà ; partout, une ligne
  // au-delà de 2 fois l'espace ordinaire (la règle écrite le 31 octobre 2026)
  function laches(ls){var c=ls.slice(0,-1),moy=c.reduce(function(s,x){return s+x.x},0)/(c.length||1);
    return c.filter(function(x){return x.x>2||(moy>LACHE&&x.x>LACHE)})}
  function pire(ls){var l=laches(ls);return l.length?l.length*10+l.reduce(function(m,x){return Math.max(m,x.x)},0):0}
  function espacer(b){
    b.style.textAlign="";b.style.wordSpacing="";b.style.letterSpacing="";delete b.dataset.lache;
    var st=getComputedStyle(b);if(st.textAlign!=="justify"){b.dataset.aligne="";return}
    // la colonne réelle décide (H4 de l'étape 4, 5 novembre 2026) : un paragraphe de moins de 560 px de large passe à
    // gauche, même quand le conteneur interrogé par la feuille de style est plus large (une colonne de grille, une
    // marge de 5 colonnes, une carte d'indicateur)
    if(b.getBoundingClientRect().width<COLONNE_MIN){b.dataset.aligne="1";b.style.textAlign="left";return}
    var ls=mesurer(b,st),gauche=ls.length<3;
    if(!gauche&&pire(ls)){var mieux={ws:"",w:0,lt:"",p:pire(ls),ls:ls},essai=function(w,a){
        b.style.wordSpacing=w?w+"em":"";b.style.letterSpacing=a?a+"em":"";var l2=mesurer(b,st);
        if(l2.length>=3&&pire(l2)<mieux.p)mieux={ws:b.style.wordSpacing,w:w,lt:b.style.letterSpacing,p:pire(l2),ls:l2}};
      // espace entre les mots d'abord ; s'il reste une ligne lâche, l'approche des lettres d'un demi à un et demi pour
      // cent autour du meilleur espacement trouvé, comme le fait un compositeur (7 novembre 2026). Au plus 26 mesures
      // par paragraphe, pour que la page soit composée en moins d'une seconde ou deux.
      for(var k=0;k<REGLAGES.length&&mieux.p;k++)essai(REGLAGES[k],0);
      var w0=mieux.w;
      for(var j=0;j<APPROCHES.length&&mieux.p;j++)for(var d=-.01;d<=.0101&&mieux.p;d+=.01)essai(Math.round((w0+d)*1000)/1000,APPROCHES[j]);
      b.style.wordSpacing=mieux.ws;b.style.letterSpacing=mieux.lt;ls=mieux.ls}
    b.dataset.aligne=gauche?"1":"";b.style.textAlign=gauche?"left":"";
    if(gauche)return;
    var l=laches(ls);
    if(l.length)b.dataset.lache=JSON.stringify(l.map(function(x){return [Math.round(x.x*100)/100,x.mots.join(" ")]}))}
  // lignes du paragraphe b, chacune avec ses mots et l'espace entre eux une fois justifiée, en fois l'espace ordinaire
  // (x) : mesuré mot par mot sur le paragraphe aligné à gauche, qui le reste
  // largeur d'une espace ordinaire du paragraphe, lue dans la page (la première espace de son texte, alignée à gauche)
  function espace(b,st){
    var tw=document.createTreeWalker(b,NodeFilter.SHOW_TEXT),n,r=document.createRange();
    while((n=tw.nextNode())){var i=n.nodeValue.indexOf(" ",1);
      while(i>0&&i<n.nodeValue.length-1){r.setStart(n,i);r.setEnd(n,i+1);var q=r.getClientRects();if(q.length===1&&q[0].width>.5)return q[0].width;i=n.nodeValue.indexOf(" ",i+1)}}
    mesureur.font=st.fontWeight+" "+st.fontSize+" "+st.fontFamily;return mesureur.measureText(" ").width||parseFloat(st.fontSize)*.28}
  function mesurer(b,st){
    b.style.textAlign="left";
    var ws=parseFloat(st.wordSpacing)||0,esp=espace(b,st)-ws,lh=parseFloat(st.lineHeight)||parseFloat(st.fontSize)*1.5;
    var bord=b.getBoundingClientRect(),large=bord.width-parseFloat(st.paddingLeft)-parseFloat(st.paddingRight)-parseFloat(st.borderLeftWidth)-parseFloat(st.borderRightWidth);
    var ls=[],r=document.createRange(),tw=document.createTreeWalker(b,NodeFilter.SHOW_TEXT),n;
    function ligne(t){for(var i=0;i<ls.length;i++)if(Math.abs(ls[i].t-t)<lh/2)return ls[i];var l={t:t,g:1e9,d:-1e9,f:0,mots:[]};ls.push(l);return l}
    while((n=tw.nextNode())){var v=n.nodeValue,i=0;
      while(i<v.length){var m=BLANC.exec(v.slice(i)),j=m?i+m.index:v.length;
        if(j>i){r.setStart(n,i);r.setEnd(n,j);var q=[].slice.call(r.getClientRects()).filter(function(x){return x.width>.5});
          q.forEach(function(x,k){var l=ligne(x.top);l.g=Math.min(l.g,x.left);l.d=Math.max(l.d,x.right);l.f++;if(!k)l.mots.push(v.slice(i,j).split(SH).join(""))})}
        i=m?j+m[0].length:v.length}}
    ls.sort(function(a,c){return a.t-c.t});
    ls.forEach(function(l){l.x=l.f>1?((large-(l.d-l.g))/(l.f-1)+esp+ws)/esp:1});
    return ls}
  // vrai si le paragraphe justifié b (de style calculé st) doit passer à gauche sur papier ; le laisse aligné à gauche
  function lache(b,st){
    b.style.textAlign="left";
    var r=document.createRange();r.selectNodeContents(b);var q=[].slice.call(r.getClientRects()),lignes={};
    q.forEach(function(x){if(x.width<1)return;var k=Math.round(x.top);var l=lignes[k]||(lignes[k]={g:x.left,d:x.right});l.g=Math.min(l.g,x.left);l.d=Math.max(l.d,x.right)});
    var tops=Object.keys(lignes).map(Number).sort(function(a,c){return a-c});
    // lignes distinctes, à une demi-ligne près
    var ls=[];tops.forEach(function(t){var p=ls[ls.length-1];if(p&&t-p.t<parseFloat(st.lineHeight)/2){p.g=Math.min(p.g,lignes[t].g);p.d=Math.max(p.d,lignes[t].d)}else ls.push({t:t,g:lignes[t].g,d:lignes[t].d})});
    var gauche=ls.length<3;
    if(!gauche){mesureur.font=st.fontWeight+" "+st.fontSize+" "+st.fontFamily;var esp=mesureur.measureText(" ").width||parseFloat(st.fontSize)*.28;
      var bord=b.getBoundingClientRect(),large=bord.width-parseFloat(st.paddingLeft)-parseFloat(st.paddingRight),txt=b.textContent.replace(/\s+/g," ").trim(),mots=txt.split(" ").length,tot=ls.reduce(function(s,l){return s+(l.d-l.g)},0);
      // espace entre les mots de chaque ligne une fois justifiée, en fois l'espace ordinaire : à gauche si la moyenne du
      // paragraphe dépasse 1,5 ou si une ligne dépasse 2
      var somme=0,pire=0;for(var i=0;i<ls.length-1;i++){var w=ls[i].d-ls[i].g,n=Math.max(1,Math.round(mots*w/tot)-1),x=(large-w)/n/esp+1;somme+=x;pire=Math.max(pire,x)}
      gauche=somme/(ls.length-1)>1.5||pire>2}
    return gauche}
  // la même règle sur la page imprimée : les règles d'impression de la feuille de style s'appliquent un instant à
  // l'écran, à la largeur d'une page A4 entre ses marges (182 mm), chaque paragraphe justifié y est mesuré, puis tout
  // revient ; seul l'alignement choisi reste, jusqu'à la fin de l'impression
  function papier(){
    var css="";[].forEach.call(document.styleSheets,function(f){var rs;try{rs=f.cssRules}catch(e){return}
      [].forEach.call(rs||[],function(r){var m=r.media&&r.media.mediaText;if(m&&/print/.test(m)&&!/screen/.test(m))[].forEach.call(r.cssRules,function(x){css+=x.cssText+"\n"})})});
    if(!css)return;
    var s=document.createElement("style");s.textContent=css+"html{width:182mm!important}";document.head.appendChild(s);
    var bs=[].slice.call(document.querySelectorAll("main p,main li,main dd,main summary")).filter(function(b){return !b.closest(EXCLUS)&&b.textContent.trim()});
    bs.forEach(function(b){b.dataset.papierAvant=b.style.textAlign;b.dataset.papierMots=b.style.wordSpacing;b.style.textAlign="";b.style.wordSpacing=""});
    var mes=[];bs.forEach(function(b){var st=getComputedStyle(b);if(st.textAlign==="justify")mes.push([b,st])});
    mes.forEach(function(x){x[0].dataset.papier=lache(x[0],x[1])?"1":""});
    mes.forEach(function(x){x[0].style.textAlign=x[0].dataset.papier?"left":""});
    familles(mes.map(function(x){return x[0]}),"papier");
    s.remove()}
  function defaire(){
    document.querySelectorAll("[data-papier-avant]").forEach(function(b){b.style.textAlign=b.dataset.papierAvant;b.style.wordSpacing=b.dataset.papierMots||"";delete b.dataset.papierAvant;delete b.dataset.papierMots;delete b.dataset.papier})}
  var attente;addEventListener("resize",function(){clearTimeout(attente);attente=setTimeout(function(){
    var bs=[].slice.call(document.querySelectorAll("main p,main li,main dd,main summary")).filter(function(b){return b.dataset.aligne!==undefined});
    bs.forEach(espacer)},250)});
  // coupures employées d'un bloc : une césure qui coupe la ligne se dessine (largeur non nulle) ; on note sa ligne
  function employees(b){
    var out=[],tw=document.createTreeWalker(b,NodeFilter.SHOW_TEXT),n,r=document.createRange();
    while((n=tw.nextNode())){var v=n.nodeValue,i=v.indexOf(SH);
      while(i>=0){r.setStart(n,i);r.setEnd(n,i+1);var q=r.getClientRects()[0];if(q&&q.width>.5)out.push({n:n,i:i,y:q.top});i=v.indexOf(SH,i+1)}}
    return out}
  function limiter(b){
    var lh=parseFloat(getComputedStyle(b).lineHeight)||24;
    for(var essai=0;essai<6;essai++){
      var c=employees(b),fait=false;
      for(var k=3;k<c.length;k++){
        if(Math.abs(c[k].y-c[k-1].y-lh)<lh/2&&Math.abs(c[k-1].y-c[k-2].y-lh)<lh/2&&Math.abs(c[k-2].y-c[k-3].y-lh)<lh/2){
          // le mot de la quatrième coupure perd toutes ses césures
          var v=c[k].n.nodeValue,a=c[k].i,z=c[k].i;
          while(a>0&&/[^\s]/.test(v[a-1]))a--;while(z<v.length&&/[^\s]/.test(v[z]))z++;
          c[k].n.nodeValue=v.slice(0,a)+v.slice(a,z).split(SH).join("")+v.slice(z);fait=true;break}}
      if(!fait)return}}
  window.cesure=traiter;
  function lancer(){traiter(document.querySelector("main")||document.body);document.documentElement.dataset.cesure="prete"}
  // les césures invisibles ne partent ni dans un copier-coller ni dans une impression : Edge écrit chacune comme une
  // coupure du texte du PDF (« inter com mu na li tés » au copier, vérifié le 30 octobre 2026), si bien que le PDF est
  // justifié sans césure, et le texte qu'on en copie reste exact ; elles reviennent après l'impression
  function retirer(){var tw=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),n;
    while((n=tw.nextNode()))if(n.nodeValue.indexOf(SH)>=0)n.nodeValue=n.nodeValue.split(SH).join("")}
  document.addEventListener("copy",function(e){var s=window.getSelection(),t=s?String(s):"";
    if(t.indexOf(SH)<0||!e.clipboardData)return;e.clipboardData.setData("text/plain",t.split(SH).join(""));e.preventDefault()});
  window.addEventListener("beforeprint",function(){retirer();papier()});
  window.addEventListener("afterprint",function(){defaire();lancer()});
  if("requestIdleCallback" in window)requestIdleCallback(lancer,{timeout:1200});else setTimeout(lancer,150);
})();
