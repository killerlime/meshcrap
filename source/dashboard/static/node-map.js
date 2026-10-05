/* A separate, lazy node map. No coverage grids or survey layers. */
(() => {
 'use strict';
 function init(){
  const nav=document.getElementById('dashboardTabs'),main=document.querySelector('main');if(!nav||!main)return;
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
  const tab=el('button','Node map');tab.id='dashboard-tab-nodemap';tab.type='button';tab.setAttribute('role','tab');tab.setAttribute('aria-controls','dashboard-panel-nodemap');tab.setAttribute('aria-selected','false');tab.tabIndex=-1;
  const panel=el('section',null,'dashboard-panel');panel.id='dashboard-panel-nodemap';panel.hidden=true;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tab.id);
  const title=el('h2','Node map'),tools=el('div',null,'console-toolbar'),fit=el('button','Fit all nodes'),status=el('span','Open to load nodes.');fit.type='button';status.setAttribute('role','status');const home=el('button','Focus receiver'),focus=el('button','Zoom to selected');home.type=focus.type='button';focus.disabled=true;tools.append(fit,home,focus,status);
  const canvas=el('div');canvas.id='allNodeMap';canvas.style.cssText='height:65vh;min-height:340px;max-height:850px;border-radius:12px;overflow:hidden';canvas.setAttribute('aria-label','Map of all nodes with known locations');
  const card=el('section',null,'card'),heading=el('h3','Selected node'),hint=el('p','Click a node for details.'),table=el('table'),body=el('tbody');table.append(body);card.append(heading,hint,table);panel.append(title,tools,canvas,card);main.append(panel);nav.append(tab);
  let map=null,layer=null,rows=[],selected=null,busy=false,first=true;const markers=new Map();
  function show(n){
   selected=n.node_id||String(n.node_num);focus.disabled=false;heading.textContent=n.site_name||n.long_name||n.short_name||selected;
   hint.textContent='Latest stored details · signal is the last radio hop.';body.replaceChildren();
   const fields=[['Node ID',n.node_id],['Short name',n.short_name],['Hardware',n.site_hardware||n.hw_model],['Role',n.role],['Location',Number(n.latitude).toFixed(5)+', '+Number(n.longitude).toFixed(5)],['Position source',n.location_source],['Last heard',n.last_observed?new Date(n.last_observed).toLocaleString():null],['SNR',n.last_snr==null?null:n.last_snr+' dB'],['RSSI',n.last_rssi==null?null:n.last_rssi+' dBm'],['Hops',n.last_hops],['Antenna',n.antenna],['Antenna gain',n.antenna_gain_dbi==null?null:n.antenna_gain_dbi+' dBi'],['Height above ground',n.agl_ft==null?null:n.agl_ft+' ft'],['Notes',n.notes]];
   for(const [label,value] of fields){const tr=el('tr'),th=el('th',label),td=el('td',value==null||value===''?'—':String(value));th.scope='row';td.style.overflowWrap='anywhere';tr.append(th,td);body.append(tr);}
   for(const [id,item] of markers)item.marker.setStyle({radius:id===selected?10:6,weight:id===selected?4:2});
  }
  async function load(){
   if(panel.hidden||document.hidden||busy)return;busy=true;status.textContent='Loading nodes…';
   try{
    if(!map){map=L.map(canvas,{scrollWheelZoom:true,renderer:L.svg()});L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,referrerPolicy:'strict-origin-when-cross-origin',attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}).addTo(map);layer=L.layerGroup().addTo(map);map.setView([0,0],2);}
    const response=await fetch('/api/map',{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!response.ok)throw Error('HTTP '+response.status);const data=await response.json();if(panel.hidden)return;
    rows=data.filter(n=>typeof n.latitude==='number'&&typeof n.longitude==='number'&&Math.abs(n.latitude)<=90&&Math.abs(n.longitude)<=180&&(n.latitude!==0||n.longitude!==0));const present=new Set();
    for(const n of rows){const id=n.node_id||String(n.node_num),signature=JSON.stringify(n);present.add(id);const previous=markers.get(id);if(previous?.signature===signature)continue;if(previous)layer.removeLayer(previous.marker);
     const color=typeof mapNodeStyle==='function'?mapNodeStyle(n).color:'#67ea94',name=n.site_name||n.long_name||n.short_name||id;
     const marker=L.circleMarker([n.latitude,n.longitude],{radius:id===selected?10:6,weight:id===selected?4:2,color,fillColor:color,fillOpacity:.85}).addTo(layer);marker.bindTooltip(el('span',name));marker.on('click',()=>show(n));markers.set(id,{marker,signature});
     const path=marker.getElement();if(path){path.setAttribute('role','button');path.setAttribute('tabindex','0');path.setAttribute('aria-label',name+' · show map details');path.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show(n);}});}
    }
    for(const [id,item] of markers)if(!present.has(id)){layer.removeLayer(item.marker);markers.delete(id);}
    if(selected){const n=rows.find(n=>(n.node_id||String(n.node_num))===selected);if(n)show(n);else{selected=null;focus.disabled=true;heading.textContent='Selected node';body.replaceChildren();hint.textContent='This node no longer has a mapped location.';}}
    map.invalidateSize();if(first){fitNodes();first=false;}for(const n of rows){const item=markers.get(n.node_id||String(n.node_num)),path=item?.marker.getElement();if(path&&!path.hasAttribute("role")){path.setAttribute("role","button");path.setAttribute("tabindex","0");path.setAttribute("aria-label",(n.site_name||n.long_name||n.short_name||n.node_id)+" · show map details");path.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();show(n);}});}}status.textContent=rows.length+' located nodes · updated '+new Date().toLocaleTimeString();
   }catch(e){status.textContent='Could not refresh. Previous nodes remain visible.';console.error('Node map',e);}finally{busy=false;}
  }
  function fitNodes(){if(!map)return;if(rows.length)map.fitBounds(rows.map(n=>[n.latitude,n.longitude]),{padding:[30,30],maxZoom:12});else map.setView([@@HOME_LAT@@,@@HOME_LON@@],10);}
  fit.addEventListener('click',fitNodes);home.addEventListener('click',()=>{if(map)map.setView([@@HOME_LAT@@,@@HOME_LON@@],12);});focus.addEventListener('click',()=>{const n=rows.find(n=>(n.node_id||String(n.node_num))===selected);if(map&&n)map.setView([n.latitude,n.longitude],13);});
  tab.addEventListener('click',()=>{main.querySelectorAll('.dashboard-panel').forEach(p=>p.hidden=p!==panel);nav.querySelectorAll('[role=tab]').forEach(b=>{b.setAttribute('aria-selected',String(b===tab));b.tabIndex=b===tab?0:-1;});requestAnimationFrame(()=>{map?.invalidateSize();load();});});
  nav.addEventListener('click',e=>{if(e.target.closest('[role=tab]')!==tab){panel.hidden=true;tab.setAttribute('aria-selected','false');tab.tabIndex=-1;}});
  window.RFRefresh?.every('nodemap',load,30000,{label:'Node map'});
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
