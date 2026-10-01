(() => {
  'use strict';
  const key='meshcrap-console-appearance';
  const allowed=new Set(['mesh','neon','midnight']);
  let current='mesh';
  try {const saved=localStorage.getItem(key);if(allowed.has(saved))current=saved;}catch(_){}
  document.documentElement.dataset.appearance=current;
  function styleFrame(frame){
    try {
      const doc=frame.contentDocument;
      if(!doc || frame.contentWindow.location.origin!==location.origin)return;
      if(!doc.getElementById('console-appearance')){
        const css=doc.createElement('link');css.id='console-appearance';css.rel='stylesheet';css.href='/static/appearance.css?v=hq-1';doc.head.append(css);
      }
      doc.documentElement.dataset.appearance=current;
    }catch(_){}
  }
  function apply(value,persist){
    current=allowed.has(value)?value:'mesh';
    document.documentElement.dataset.appearance=current;
    const select=document.getElementById('appearanceSelect');if(select)select.value=current;
    if(persist){try{localStorage.setItem(key,current);}catch(_){}}
    document.querySelectorAll('iframe').forEach(styleFrame);
  }
  function init(){
    const select=document.getElementById('appearanceSelect');
    if(select){select.value=current;select.addEventListener('change',()=>apply(select.value,true));}
    const watchFrame=frame=>{if(frame.dataset.appearanceWatched)return;frame.dataset.appearanceWatched='1';frame.addEventListener('load',()=>styleFrame(frame));styleFrame(frame);};
    document.querySelectorAll('iframe').forEach(watchFrame);
    new MutationObserver(changes=>changes.forEach(change=>change.addedNodes.forEach(node=>{
      if(node.nodeType!==1)return;
      if(node.tagName==='IFRAME')watchFrame(node);
      node.querySelectorAll('iframe').forEach(watchFrame);
    }))).observe(document.body,{childList:true,subtree:true});
    window.addEventListener('storage',event=>{if(event.key===key)apply(event.newValue,false);});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
