(() => {
 let box,status,select,detail,table,canvas,chart,busy=false,pending=false,data;
 const el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
 const num=(x,d=1)=>Number.isFinite(x)?x.toFixed(d):'—';
 const date=x=>x?new Date(x*1000).toLocaleString():'No reply yet';
 function age(x){if(!x)return 'no sample';const m=Math.max(0,Math.round((Date.now()/1000-x)/60));return m<60?`${m}m ago`:m<1440?`${Math.floor(m/60)}h ${m%60}m ago`:`${Math.floor(m/1440)}d ago`;}
 const label=s=>({waiting:'Waiting for reply',acknowledged:'Acknowledged; waiting for data',timeout:'Slow/no reply · retry scheduled',rejected:'Request declined · retry scheduled',send_error:'Could not send · retry scheduled',response:'Reply received',empty_response:'Setting unavailable'}[s]||'Queued');
 function render(){
  if(!data)return;
  const node=data.nodes.find(n=>n.id===select.value)||data.nodes[0];if(!node)return;
  select.value=node.id;try{localStorage.setItem('lnaRemoteNode',node.id);}catch{}
  detail.replaceChildren();
  const request=node.last_request;
  detail.append(el('p',`${label(request?.status)}${request?.error?` (${request.error})`:''}. Last data reply: ${age(node.last_success)}. ${node.next_attempt_at?`Next eligible read: ${date(node.next_attempt_at)}; radio availability and other queued nodes may delay it.`:'Waiting for the initial check.'}`));
  const latest=node.latest,valid=node.latest_in_window;
  const values=el('div',null,'pki-values');
  for(const [name,value] of [['Remote noise floor',valid&&latest?.noise_floor<0?`${num(latest.noise_floor)} dBm`:'—'],['Received since reboot',valid?num(latest?.num_packets_rx,0):'—'],['Relayed since reboot',valid?num(latest?.num_tx_relay,0):'—'],['Latest remote sample',valid?age(node.latest_at):'None in this window']]){
   const card=el('div');card.append(el('span',name),el('strong',value));if(name==='Latest remote sample')card.title=date(node.latest_at);values.append(card);
  }
  detail.append(values);
  if(node.stale)detail.append(el('p','Remote readings are stale or still pending. A missed admin reply does not prove this node is offline.','pki-note'));
  const points=[];
  for(const p of node.points){const old=points.at(-1);if(old&&p.timestamp-old.timestamp>2700)points.push({time:new Date((old.timestamp+1)*1000).toISOString(),timestamp:old.timestamp+1});points.push(p);}
  const labels=points.map(p=>new Date(p.time).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}));
  const datasets=[{label:'Remote noise (dBm)',data:points.map(p=>p.warmup?null:p.noise_dbm??null),borderColor:'#68c9ff',backgroundColor:'#68c9ff',yAxisID:'noise',pointRadius:2,borderWidth:2,spanGaps:false},
   {label:'Remote receives / hour',data:points.map(p=>p.rx_per_hour??null),borderColor:'#91d7a4',backgroundColor:'#91d7a4',yAxisID:'rate',pointRadius:2,borderWidth:2,spanGaps:false},
   {label:'Remote relays / hour',data:points.map(p=>p.relay_per_hour??null),borderColor:'#e7c875',backgroundColor:'#e7c875',yAxisID:'rate',pointRadius:2,borderWidth:2,spanGaps:false}];
  const opts={responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{labels:{color:'#b8c9bf'}},lnaSwitches:{timestamps:points.map(p=>p.time)}},scales:{x:{ticks:{color:'#b8c9bf',maxTicksLimit:5}},noise:{position:'left',title:{display:true,text:'Noise · dBm',color:'#b8c9bf'},ticks:{color:'#b8c9bf'}},rate:{position:'right',beginAtZero:true,title:{display:true,text:'Packets / hour',color:'#b8c9bf'},ticks:{color:'#b8c9bf'},grid:{drawOnChartArea:false}}}};
  if(chart){chart.data={labels,datasets};chart.options=opts;chart.update('none');}else chart=new Chart(canvas,{type:'line',data:{labels,datasets},options:opts});
  canvas.setAttribute('aria-label',`${node.name}: remote noise floor, receive and relay rates over the selected ${data.hours} hours. ${node.points.length} samples. LNA markers refer to Receiver only.`);
  const rows=node.points.filter(p=>p.rx_per_hour!=null);const last=rows.at(-1);
  detail.append(el('p',last?`${node.name} reported about ${num(last.rx_per_hour,0)} receives and ${num(last.relay_per_hour,0)} relays per hour over its latest comparable interval. These counters include duplicates and diagnostic traffic.`:'Waiting for two fresh samples from the same boot to calculate receive and relay rates.'));
  const config=el('details');config.append(el('summary','Latest radio and channel checks'));
  const dl=el('dl');const cfg=node.configs,lora=cfg.lora?.data,dev=cfg.device?.data;
  for(const [key,value] of [['Radio',lora?`${lora.modem_preset} · ${lora.region} · channel ${lora.channel_num}${lora.override_frequency?` · ${lora.override_frequency} MHz override`:''}`:'Waiting'],['Forwarding',dev?`${dev.role} · ${dev.rebroadcast_mode}`:'Waiting'],...['channel_0','channel_1'].map((k,i)=>{const c=cfg[k]?.data;return [`Slot ${i}`,c?`${c.settings?.name||'(preset default)'} · ${c.role}${c.key_matches_receiver_named_channel===true?' · key matches Receiver':c.key_matches_receiver_named_channel===false?' · KEY MISMATCH':''}`:'Waiting'];})]){dl.append(el('dt',key),el('dd',value));}
  config.append(dl,el('p','Settings are the last successful snapshots and may be older than the selected graph window. PKI keys and channel secrets are omitted.','pki-note'));detail.append(config);
  table.replaceChildren();
  const head=el('thead'),tr=el('tr');for(const title of ['local node','Remote sample','Read status'])tr.append(el('th',title));head.append(tr);table.append(head);const body=el('tbody');
  for(const n of data.nodes){const tr=el('tr'),name=el('td'),button=el('button',n.name);button.type='button';button.addEventListener('click',()=>{select.value=n.id;render();});name.append(button);const sample=el('td',n.latest_in_window?age(n.latest_at):'None in window');sample.title=date(n.latest_at);tr.append(name,sample,el('td',label(n.last_request?.status)));body.append(tr);}table.append(body);
 }
 async function refresh(){
  if(busy){pending=true;return;}if(document.hidden||!box?.getClientRects().length)return;
  busy=true;pending=false;const hours=window.getDashboardHours?.()||24;
  try{const r=await fetch(`/api/lna-remote?hours=${hours}`,{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error('Remote receiver data unavailable');const d=await r.json();if(hours!==(window.getDashboardHours?.()||24)){pending=true;return;}data=d;
   let saved=select.value;try{saved=saved||localStorage.getItem('lnaRemoteNode');}catch{}
   select.replaceChildren();for(const n of d.nodes){const o=el('option',n.name);o.value=n.id;select.append(o);}select.value=d.nodes.some(n=>n.id===saved)?saved:(d.nodes.find(n=>n.id==='!00000000')?.id||d.nodes[0]?.id||'');
   status.textContent=`${d.responses} saved replies · ${d.requests} requests in the selected ${hours}h window · ${d.pending} waiting. Reads are paced and retries back off automatically.`;render();
  }catch(e){status.textContent=`${e.message}. Displayed data may be stale.`;}finally{busy=false;if(pending)refresh();}
 }
 window.addEventListener('load',()=>{
  const panel=document.getElementById('dashboard-panel-filter');if(!panel)return;
  box=el('section',null,'lna-controls pki-panel');box.id='lnaRemotePanel';box.append(el('h3','What the other local receivers hear'));
  box.append(el('p','Remote receivers provide context: if their reception falls too, the wider mesh may be quieter. If they remain busy while Receiver drops, look closer to Receiver. Neither pattern proves the LNA caused the change.','pki-note'));
  status=el('p','Loading remote receiver observations…');status.setAttribute('role','status');box.append(status);
  const label=el('label','Receiver ');select=el('select');select.id='lnaRemoteSelect';label.htmlFor=select.id;label.append(select);select.addEventListener('change',render);box.append(label);
  detail=el('div');box.append(detail);const wrap=el('div',null,'pki-chart');canvas=el('canvas');canvas.setAttribute('role','img');wrap.append(canvas);box.append(wrap);
  box.append(el('p','LNA switch markers describe Receiver only. Remote noise is measured at the selected node, not at Receiver. Startup samples, counter resets and gaps over 45 minutes are excluded from rates. Known poll replies are excluded from the main LNA reception graph; hardware counters still include polling traffic.','pki-note'));
  const all=el('details');all.append(el('summary','All local CLIENT receivers'));const scroller=el('div',null,'pki-table-wrap');table=el('table');table.setAttribute('aria-label','Remote receiver collection status');scroller.append(table);all.append(scroller);box.append(all);
  const noise=document.getElementById('lnaNoisePanel');if(noise)noise.after(box);else panel.append(box);
  refresh();setInterval(refresh,60000);document.addEventListener('visibilitychange',refresh);document.getElementById('dashboardTabs')?.addEventListener('click',()=>setTimeout(refresh,80));window.addEventListener('dashboard:time-window',refresh);
 });
})();
