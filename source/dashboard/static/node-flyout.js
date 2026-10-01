(() => {
 const el=(tag,text)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;return e;};
 const requestId=()=>{const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);return Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');};
 let generation=0,timer=null,detailMap=null;
 window.stopFlyoutRequests=()=>{generation++;clearTimeout(timer);if(detailMap){detailMap.remove();detailMap=null;}};
 async function api(path,body,route='node-control'){
  const r=await fetch('/api/'+route+'/'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,cache:'no-store',signal:AbortSignal.timeout(12000)});
  const d=await r.json();if(!r.ok||d.ok===false)throw Error(d.error||'Request failed');return d.data||d;
 }
 const label=k=>k.replace(/([a-z])([A-Z])/g,'$1 $2').replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());
 const units={temperature:'°C',relativeHumidity:'%',barometricPressure:'hPa',gasResistance:'Ω',voltage:'V',current:'mA',iaq:'index',lux:'lx',whiteLux:'lx'};
 function fields(parent,values){for(const [key,value] of Object.entries(values||{})){if(value==null||key==='raw')continue;const row=el('div');row.className='telemetry-row';row.append(el('span',label(key)),el('strong',(typeof value==='object'?JSON.stringify(value):String(value))+(units[key]?' '+units[key]:'')));parent.append(row);}}
 window.enhanceNodeFlyout=d=>{
  window.stopFlyoutRequests();const gen=generation,n=d.node||{},node=n.node_id,body=document.getElementById('telemetryBody');
  const section=title=>{const e=el('section');e.className='telemetry-section';const h=el('h3',title);h.className='telemetry-section-title';e.append(h);return e;};
  const info=section('Node identity');fields(info,{'Node ID':node||telemetryNode,'Short name':n.short_name,'Long name':n.long_name,'Reported hardware':n.hw_model,'Role':n.role,'Node record updated':n.node_updated_at});body.prepend(info);
  for(const [key,title] of [['position','Last reported location'],['environment','Environmental metrics'],['environment_radio','Radio-reported environmental metrics']]){
   const card=section(title),item=d.details?.[key];if(key==='environment_radio'&&!item)continue;
   if(item){const values={...item.values};if(key==='position'){if(values.latitudeI!=null){values.latitude=values.latitudeI/1e7;delete values.latitudeI;}if(values.longitudeI!=null){values.longitude=values.longitudeI/1e7;delete values.longitudeI;}if(values.altitude!=null){values['Altitude (m)']=values.altitude;delete values.altitude;}if(values.time){values['Node position time']=new Date(values.time*1000).toLocaleString();delete values.time;}if(values.groundTrack!=null){values['Ground track (raw)']=values.groundTrack;delete values.groundTrack;}if(values.groundSpeed!=null){values['Ground speed (raw)']=values.groundSpeed;delete values.groundSpeed;}}
    card.append(el('p',item.source ? item.source+' · '+item.station_id+' · '+(item.stale?'STALE · ':'')+'Observed '+new Date(item.observed_at).toLocaleString() : 'Received '+new Date(item.received_at).toLocaleString()+' · stored report'));fields(card,values);if(item.pressure_basis)card.append(el('p',item.pressure_basis));
   }else card.append(el('p','No '+(key==='position'?'position':'environmental telemetry')+' report stored for this node.'));
   info.after(card);
  }
  const location=d.details?.position,position=location?.values||{};
  const latitude=position.latitudeI!=null?Number(position.latitudeI)/1e7:(position.latitude==null?NaN:Number(position.latitude));
  const longitude=position.longitudeI!=null?Number(position.longitudeI)/1e7:(position.longitude==null?NaN:Number(position.longitude));
  const mapCard=section('Around this node · 10-mile radius');info.after(mapCard);
  if(!window.L||!Number.isFinite(latitude)||!Number.isFinite(longitude)||Math.abs(latitude)>90||Math.abs(longitude)>180||(latitude===0&&longitude===0)){
   mapCard.append(el('p','No valid reported location is available for this node.'));
  }else{
   const canvas=el('div');canvas.style.cssText='height:280px;width:100%;border-radius:10px;overflow:hidden';canvas.setAttribute('aria-label','Map showing a ten-mile radius around the last reported node location');mapCard.append(canvas);
   mapCard.append(el('p','Centered on the last reported position. The circle shows distance, not proven radio coverage.'));
   const stamp=position.time?Number(position.time)*1000:NaN;
   mapCard.append(el('p',Number.isFinite(stamp)?'Position reported '+new Date(stamp).toLocaleString():'Position time unknown; this may be an old location.'));
   requestAnimationFrame(()=>{if(gen!==generation||!canvas.isConnected)return;
    detailMap=L.map(canvas,{scrollWheelZoom:false}).setView([latitude,longitude],10);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}).addTo(detailMap);
    const radius=L.circle([latitude,longitude],{radius:16093.44,color:'#45d68c',weight:2,fillOpacity:.08}).addTo(detailMap);
    L.circleMarker([latitude,longitude],{radius:7,color:'#fff',fillColor:'#45d68c',fillOpacity:1}).addTo(detailMap).bindTooltip(el('span',n.long_name||n.short_name||node));
    detailMap.fitBounds(radius.getBounds(),{padding:[12,12]});detailMap.invalidateSize();
   });
  }
  const actions=section('Request from this node'),status=el('p','Checking control session…');status.setAttribute('role','status');
  const note=el('p','RF requests use Receiver; Secondary radio node info is read directly through the configured secondary connection. Replies depend on radio reachability and sensor support. Waits stop after 30 seconds; no automatic resend.');note.className='muted';actions.append(note);
  const unlock=el('form'),key=el('input');key.type='password';key.placeholder='Dashboard control key';key.autocomplete='off';key.setAttribute('aria-label','Flyout control key');const unlockButton=el('button','Unlock controls');unlock.append(key,unlockButton);unlock.hidden=true;actions.append(unlock);
  const settings=el('div');settings.style.cssText='display:flex;gap:12px;flex-wrap:wrap';const channel=el('select'),hops=el('input');hops.type='number';hops.min=0;hops.max=7;hops.value=3;
  for(const [title,input] of [['Request channel',channel],['Request hop limit',hops]]){const l=el('label',title+' ');input.setAttribute('aria-label',title);l.append(input);settings.append(l);}actions.append(settings);
  const buttons=el('div');buttons.style.cssText='display:flex;flex-wrap:wrap;gap:8px;margin:12px 0';actions.append(buttons,status);const results=el('div');results.setAttribute('aria-live','polite');actions.append(results);info.after(actions);
  let state=null,busy=false,jobId=null,deadline=0,requestName='',lastResult=null,jobRoute='node-control';
  const specs=[['traceroute','Traceroute'],['position','Request location'],['node_info','Request node info'],['device_metrics','Request device metrics'],['environment_metrics','Request environmental metrics']];
  const controls=[];
  function disabled(){controls.forEach(([b,op])=>b.disabled=busy||!state||!node||(op==='traceroute'&&node===state.node_id));channel.disabled=busy||!state;hops.disabled=busy||!state;}
  function renderJob(job){
   results.replaceChildren();results.append(el('h4',requestName+' · '+job.status),el('p',job.message));
   if(job.result){
    if(job.operation==='traceroute'){
     const r=job.result,name=id=>state.nodes.find(n=>n.id===id)?.name||id;
     const route=(a,m,b)=>[a,...(m||[]),b].map(name).join(' → ');
     results.append(el('p','Forward: '+route(job.source,r.route,job.destination)),el('p','Return: '+(r.returnRouteAvailable?route(job.destination,r.routeBack,job.source):'Not reported')));
    }
    const details=el('details');details.append(el('summary','Response details'));const pre=el('pre',JSON.stringify(job.result,null,2));pre.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere';details.append(pre);results.append(details);
    if(lastResult!==job.id){lastResult=job.id;const refresh=el('button','Reload stored node details');refresh.onclick=()=>{const notes=document.getElementById('nodeNotesText');if(notes&&notes.value!==(d.note?.note||'')){status.textContent='Save your edited note before reloading details.';return;}openTelemetry(node);};results.append(refresh);}
   }
  }
  async function poll(){
   if(gen!==generation)return;
   try{const data=await api('action',{action:'operations'},jobRoute);if(gen!==generation)return;const job=data.operations.find(j=>j.id===jobId);
    if(job){renderJob(job);if(!['waiting','acknowledged'].includes(job.status)){busy=false;disabled();status.textContent=job.message;return;}}
    if(Date.now()>=deadline){busy=false;disabled();status.textContent='No completed reply within 30 seconds. A late response can still be received. Use Check for late reply; the request will not be resent.';return;}
    timer=setTimeout(poll,Math.min(2000,deadline-Date.now()));
   }catch(e){if(gen!==generation)return;busy=false;disabled();status.textContent=e.message;}
  }
  for(const [op,title] of specs){const b=el('button',op==='node_info'&&node==='!00000000'?'Read node info · direct':title);b.type='button';controls.push([b,op]);buttons.append(b);b.onclick=async()=>{
   if(busy||gen!==generation)return;const h=Number(hops.value);if(!Number.isInteger(h)||h<0||h>7){status.textContent='Choose a hop limit from 0 to 7.';return;}
   clearTimeout(timer);busy=true;disabled();requestName=title;results.replaceChildren();status.textContent='Submitting '+title.toLowerCase()+'…';
   try{jobRoute='node-control';const r=await api('action',{action:'operation',operation:op,destination:node,channel:Number(channel.value),hops:h,request_id:requestId()},jobRoute);if(gen!==generation)return;jobId=r.operation_id;deadline=Date.now()+30000;status.textContent=jobRoute==='secondary-control'?'Secondary integration is unavailable.':'Submitted. Waiting up to 30 seconds for a reply.';poll();}
   catch(e){if(gen!==generation)return;busy=false;disabled();status.textContent=e.message+' No automatic retry was made.';}
  };}
  const late=el('button','Check for late reply');late.type='button';late.onclick=()=>{if(!jobId||busy)return;deadline=0;poll();};actions.append(late);
  async function loadState(){state=await api('action',{action:'state'});if(gen!==generation)return;channel.replaceChildren();for(const c of state.channels.filter(c=>c.enabled)){const o=el('option',c.index+' · '+((c.index===0&&c.name==='Primary'?'MediumFast':c.name)||(c.index===0?'MediumFast':'Unnamed')));o.value=c.index;channel.append(o);}channel.value=String(state.channels.find(c=>c.enabled&&c.index===0)?.index??state.channels.find(c=>c.enabled)?.index);hops.value=state.groups.find(g=>g.name==='lora')?.fields.find(f=>f.name==='hop_limit')?.value??3;unlock.hidden=true;status.textContent=node===state.node_id?'Receiver selected. Traceroute requires another node.':'Choose a request. Delivery acknowledgment alone is not a data reply.';disabled();}
  unlock.onsubmit=async e=>{e.preventDefault();unlockButton.disabled=true;try{await api('unlock',{key:key.value});key.value='';await loadState();}catch(e){status.textContent=e.message;}finally{unlockButton.disabled=false;}};
  disabled();api('session').then(s=>{if(gen!==generation)return;if(s.unlocked)return loadState();unlock.hidden=false;status.textContent='Unlock controls to send requests.';}).catch(e=>{if(gen===generation)status.textContent=e.message;});
 };
})();
