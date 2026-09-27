(()=>{
 const $=id=>document.getElementById(id);let map,layer,nodes=[],home=null,loading=false,library;
 const text=(tag,value)=>{const e=document.createElement(tag);e.textContent=value;return e;};
 function loadLibrary(){if(window.L)return Promise.resolve();if(library)return library;library=new Promise((resolve,reject)=>{const css=document.createElement('link');css.rel='stylesheet';css.href='/static/lcd-leaflet.css';document.head.append(css);const script=document.createElement('script');script.src='/static/lcd-leaflet.js';script.onload=resolve;script.onerror=()=>{script.remove();library=null;reject(Error('Map library unavailable.'));};document.head.append(script);});return library;}
 const located=n=>n.latitude!=null&&n.longitude!=null&&Number.isFinite(Number(n.latitude))&&Number.isFinite(Number(n.longitude))&&Math.abs(Number(n.latitude))<=90&&Math.abs(Number(n.longitude))<=180;
 const jk=n=>(n.short_name||'').trim().toUpperCase().startsWith('@@NODE_PREFIX@@');
 function visible(){return nodes.filter(n=>!$('mapJk').checked||jk(n)||n.node_id==='@@RECEIVER_ID@@');}
 function render(){layer.clearLayers();for(const n of visible().sort((a,b)=>Number(a.node_id==='@@RECEIVER_ID@@')-Number(b.node_id==='@@RECEIVER_ID@@'))){
  const own=n.node_id==='@@RECEIVER_ID@@',color=own?'#00d8ff':jk(n)?'#39d98a':['ROUTER','ROUTER_LATE','REPEATER'].includes(n.role)?'#f2c94c':'#939d98';
  const marker=L.circleMarker([Number(n.latitude),Number(n.longitude)],{radius:own?10:7,weight:own?3:2,color:own?'#fff':color,fillColor:color,fillOpacity:.95});
  const popup=document.createElement('div');popup.append(text('strong',n.site_name||n.long_name||n.short_name||n.node_id||'Unnamed node'),text('div',(n.short_name||'—')+' · '+(n.node_id||'—')),text('div',n.location_source==='installed'?'Installed site location':'Last advertised location · may be out of date'));
  if(n.role)popup.append(text('div',n.role));marker.bindPopup(popup,{maxWidth:230,autoPanPadding:[12,12]});marker.addTo(layer);
 }
 $('mapCount').textContent=visible().length+' nodes · cyan Receiver · green JK';}
 function center(){if(home)map.setView(home,11);else fit();}
 function fit(){const points=visible().map(n=>[Number(n.latitude),Number(n.longitude)]);if(points.length)map.fitBounds(points,{padding:[25,25],maxZoom:13});}
 async function refresh(first=false){if(loading)return;loading=true;$('mapRefresh').disabled=true;$('mapStatus').textContent='Loading locations…';try{
  const r=await fetch('/api/map',{cache:'no-store',signal:AbortSignal.timeout(12000)});if(!r.ok)throw Error('HTTP '+r.status);const d=await r.json();if(!Array.isArray(d))throw Error('Invalid map response');nodes=d.filter(located);const own=nodes.find(n=>n.node_id==='@@RECEIVER_ID@@');home=own?[Number(own.latitude),Number(own.longitude)]:null;render();if(first)center();$('mapStatus').textContent='Updated '+new Date().toLocaleTimeString();
 }catch(e){$('mapStatus').textContent='Unable to refresh. '+(nodes.length?'Showing previous locations.':'Tap Refresh to retry.');}finally{loading=false;$('mapRefresh').disabled=false;}}
 $('mapOpen').onclick=async()=>{window.lcdMapOpen=true;$('mapPanel').hidden=false;try{await loadLibrary();if(!map){map=L.map('lcdMap',{zoomControl:false,inertia:false,zoomAnimation:false,fadeAnimation:false,markerZoomAnimation:false,attributionControl:true,preferCanvas:true}).setView([@@HOME_LAT@@,@@HOME_LON@@],10);layer=L.layerGroup().addTo(map);const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,referrerPolicy:'strict-origin-when-cross-origin',attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'});tiles.on('tileerror',()=>{$('mapStatus').textContent='Base map unavailable; node markers remain available.';});tiles.addTo(map);}map.invalidateSize();await refresh(true);}catch(e){$('mapStatus').textContent=e.message;}};
 $('mapClose').onclick=()=>{$('mapPanel').hidden=true;window.lcdMapOpen=false;$('mapOpen').focus();};$('mapHome').onclick=()=>map&&center();$('mapAll').onclick=()=>map&&fit();$('mapRefresh').onclick=()=>{if(map)refresh();else $('mapOpen').click();};$('mapPlus').onclick=()=>map?.zoomIn();$('mapMinus').onclick=()=>map?.zoomOut();$('mapJk').onchange=()=>{if(map)render();};
})();
