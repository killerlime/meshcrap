(() => {
 const openCards=new Set();
 document.addEventListener('keydown',event=>{if(event.key==='Escape')for(const close of [...openCards])close();},true);
 window.installMapNodeHover=(marker,map,html,name)=>{
  let timer=null,tip=null;
  const close=()=>{clearTimeout(timer);if(tip){map.removeLayer(tip);tip=null;}marker.getElement()?.removeAttribute('aria-describedby');openCards.delete(close);mapNodeHoverOpen=openCards.size>0;};
  const later=()=>{clearTimeout(timer);timer=setTimeout(close,180);};
  const show=()=>{
   clearTimeout(timer);if(tip||marker.isPopupOpen())return;
   for(const dismiss of [...openCards])dismiss();
   tip=L.tooltip({direction:'auto',offset:[10,0],opacity:1,interactive:true,className:'node-hover-card'}).setLatLng(marker.getLatLng()).setContent(html).addTo(map);
   openCards.add(close);mapNodeHoverOpen=true;
   const box=tip.getElement();if(box.id)marker.getElement()?.setAttribute('aria-describedby',box.id);box.addEventListener('mouseenter',()=>clearTimeout(timer));box.addEventListener('mouseleave',later);
  };
  marker.on('mouseover',event=>{if(window.matchMedia('(any-hover: hover)').matches&&!event.originalEvent?.sourceCapabilities?.firesTouchEvents)show();});
  marker.on('mouseout',later);marker.on('click',close);marker.on('remove',()=>{close();map.off('movestart',close);});
  map.on('movestart',close);
  const path=marker.getElement();if(!path)return;
  path.setAttribute('tabindex','0');path.setAttribute('role','button');path.setAttribute('aria-label',name+' · show node details');
  path.addEventListener('focus',show);path.addEventListener('blur',later);
  path.addEventListener('keydown',event=>{
   if(event.key==='Enter'||event.key===' '){event.preventDefault();close();marker.fire('click',{originalEvent:event});}
  });
 };
})();
