(() => {
 'use strict';
 document.documentElement.classList.toggle('embedded',new URLSearchParams(location.search).get('embedded')==='1');
 const $=id=>document.getElementById(id);
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=String(text);if(cls)n.className=cls;return n;};
 const number=value=>value==null?'—':Number(value).toLocaleString();
 const when=value=>value?new Date(value).toLocaleString(undefined,{timeZoneName:'short'}):'Waiting for observations';
 const offset=(value,samples,unit)=>value==null?'No paired samples':`${value>0?'+':''}${value} ${unit} · ${number(samples)} samples`;
 let busy=false;
 function profile(label,p){const box=el('div',null,'profile');box.append(el('strong',label));if(!p){box.append(el('span','Profile unavailable'));return box;}const l=p.lora||{};box.append(el('span',`${l.region||'Unknown region'} · ${l.modem_preset?.replaceAll('_',' ')||'Custom modem'} · frequency slot ${l.channel_num??'unknown'}`));box.append(el('span',`Channels: ${(p.channels||[]).filter(c=>c.enabled).map(c=>`${c.index} ${c.name}`).join(', ')||'Unknown'}`));return box;}
 function render(d){
  const status=d.status||{},coverage=d.coverage||{},label=d.labels?.secondary||'Secondary';
  $('secondaryLegend').textContent=label;
  $('status').textContent=!d.enabled?'Optional · off':status.connected?`${label} connected`:`${label} offline`;$('status').className=`badge ${d.enabled&&status.connected?'online':'offline'}`;
  $('connection').textContent=status.connected?`${label} is collecting independently. Last RF observation: ${when(status.last_packet)}.`:(status.error||'Waiting for the Secondary collector.');
  $('profiles').replaceChildren(profile('Primary',d.primary_profile),profile(label,status.profile));
  $('compatibility').textContent=d.compatibility.message;
  const duration=coverage.overlap_seconds||0;
  $('coverage').textContent=`${(duration/3600).toFixed(2)} hours of simultaneous collection in this window. ${label} history began ${when(coverage.first_collection)}.`;
  $('limits').replaceChildren(...d.limits.map(x=>el('li',x)));
  const c=d.comparison;$('results').hidden=!c;$('empty').hidden=!!c;
  if(!d.enabled)$('connection').textContent='Optional receiver comparison is off. Run the receiver setup wizard to add an independent radio.';
  if(!c)return;
  const metrics=[['Heard by both',c.packets.both,'Same sender, packet ID and payload'],['Primary only',c.packets.primary_only,'Not observed at Secondary'],['Secondary only',c.packets.secondary_only,'Not observed at Primary']];
  $('metrics').replaceChildren(...metrics.map(([label,value,note])=>{const box=el('div',null,'metric');box.append(el('p',label),el('strong',number(value)),el('small',note));return box;}));
  $('telemetry').replaceChildren(...[['primary','Primary'],['secondary',label]].map(([key,label])=>{const samples=d.local_telemetry?.[key]||[],t=samples[samples.length-1]||{},row=el('tr');row.append(el('td',label),el('td',when(t.collector_time)),el('td',t.battery_level==null?'—':t.battery_level>100?'External power':`${number(t.battery_level)}%`),el('td',t.voltage==null?'—':`${number(t.voltage)} V`),el('td',t.channel_utilization==null?'—':`${number(t.channel_utilization)}%`),el('td',t.air_util_tx==null?'—':`${number(t.air_util_tx)}%`));return row;}));
  if(d.truncated)$('coverage').textContent+=' History limit reached: results are partial.';
  $('coverage').textContent+=` ${number(c.unmatchable_observations)} observations lacked a usable payload identity.`;
  $('signals').replaceChildren(...[['direct_both','Direct at both'],['relayed_both','Relayed at both'],['mixed','Different path types'],['unknown','Unknown hops']].map(([key,label])=>{const s=c.signal[key],row=el('tr');row.append(el('td',label),el('td',number(s.packets)),el('td',offset(s.snr_median_secondary_minus_primary,s.snr_samples,'dB')),el('td',offset(s.rssi_median_secondary_minus_primary,s.rssi_samples,'dB')));return row;}));
  $('nodes').replaceChildren(...c.nodes.map(n=>{const row=el('tr'),name=el('td',n.name);name.append(el('small',n.node_id));row.append(name,el('td',number(n.both)),el('td',number(n.primary_only)),el('td',number(n.secondary_only)),el('td',offset(n.direct.snr_median_secondary_minus_primary,n.direct.snr_samples,'dB')));return row;}));
  if(!c.nodes.length){const row=el('tr'),cell=el('td','No comparable RF packets yet.');cell.colSpan=5;row.append(cell);$('nodes').append(row);}
  const t=c.timing;
  $('correlation').textContent=d.truncated?'Correlation withheld because this window reached the history limit. Select a shorter window.':t.packet_count_pearson==null?`Waiting for at least 12 complete ${t.bin_minutes}-minute intervals with varying reception counts. ${t.complete_bins} complete intervals available.`:`Reception-count correlation: ${t.packet_count_pearson} across ${t.complete_bins} complete ${t.bin_minutes}-minute intervals. A shared rise or fall does not establish a cause.`;
  const top=Math.max(1,...t.timeline.map(b=>Math.max(b.primary,b.secondary)));
  $('timeline').replaceChildren(...t.timeline.map(b=>{const bin=el('div',null,'bin');bin.title=`${when(b.at)} · Primary ${b.primary} · Secondary ${b.secondary}`;for(const key of ['primary','secondary']){const bar=el('div',null,`bar ${key}`);bar.style.height=`${100*b[key]/top}%`;bin.append(bar);}return bin;}));
  $('intervals').replaceChildren(...t.timeline.map(b=>{const row=el('tr');row.append(el('td',when(b.at)),el('td',number(b.primary)),el('td',number(b.secondary)));return row;}));
  $('hops').replaceChildren(...Object.entries(c.hop_pairs).map(([path,count])=>el('span',`${path} · ${number(count)} packets`)));
 }
 async function load(){if(busy||document.hidden||window.frameElement&&!window.frameElement.getClientRects().length)return;busy=true;try{const response=await fetch(`/api/receiver-comparison?hours=${encodeURIComponent($('hours').value)}`,{cache:'no-store',signal:AbortSignal.timeout(12000)});const data=await response.json();if(!response.ok)throw new Error(data.error||'Receiver data unavailable');render(data);$('updated').textContent=`Updated ${new Date(data.generated_at).toLocaleTimeString()}`;}catch(e){$('updated').textContent=`${e.message}. Saved data remains visible. Use Refresh to retry.`;}finally{busy=false;}}
 $('hours').addEventListener('change',load);document.addEventListener('visibilitychange',load);
 RFRefresh.every('comparison',load,30000,{host:'main',label:'Receiver comparison'});load();
})();
