(() => {
 'use strict';
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
 const fmt=(n,d=0)=>Number(n||0).toLocaleString(undefined,{maximumFractionDigits:d});
 function init(){
  const panel=document.getElementById('dashboard-panel-insights');if(!panel)return;
  const section=el('section',null,'card role-compare');section.id='insight-role';
  section.append(el('h3','What if receiver were ROUTER_LATE?'),el('p','Replay observed traffic under different forwarding assumptions. receiver stays in its current role; this panel sends no radio requests.','muted'));
  panel.querySelector('#insight-mesh')?.after(section);
  const jump=el('a','receiver role comparison');jump.href='#insight-role';panel.querySelector('.insight-jumps')?.append(jump);
  const tools=el('div',null,'role-tools');
  const rateLabel=el('label','Assumed CLIENT cancellation rate '),rate=el('select');rate.id='role-cancel';
  for(const n of [0,10,25,50,75,100]){const o=el('option',n+'%');o.value=n;rate.append(o);}rate.value='50';rateLabel.append(rate);
  const airLabel=el('label','Assumed airtime per rebroadcast (seconds) '),air=el('input');air.type='number';air.min='.05';air.max='5';air.step='.05';air.value='.4';air.id='role-airtime';airLabel.append(air);
  const refresh=el('button','Refresh comparison');refresh.type='button';
  tools.append(rateLabel,airLabel,refresh);section.append(tools);
  section.append(el('p','These are adjustable assumptions, not measured cancellation rates or packet durations. Extra rebroadcasts = affected packets × cancellation rate; extra airtime = extra rebroadcasts × assumed duration.','muted'));
  const status=el('p','Open Insights to calculate.');status.setAttribute('role','status');const body=el('div');section.append(status,body);
  const methodology=el('details'),summary=el('summary','Scope, exclusions, and confidence');methodology.append(summary);
  for(const text of [
   'Measured: LIVE RF broadcast packets received by receiver, with an identifiable packet ID and remaining hops. Startup snapshots, other receivers, receiver-origin traffic, MQTT, unconfirmed RF, diagnostics, and unicast traffic are excluded. Repeated sender/packet IDs are counted once within 24 hours.',
   'Modeled: how many non-favorite broadcast packets might gain a rebroadcast if CLIENT cancellation were replaced with late forwarding. Current favorites and configuration are applied across the selected history. This is not proof of past configuration.',
   'The newer CLIENT_BASE behavior already gives favorite traffic late forwarding. ROUTER_LATE extends that treatment to other eligible traffic. A 100% case is only a ceiling for this observed broadcast subset, not all radio traffic.',
   'Missing: internal duplicate/cancellation decisions, full transmit queue state, undecoded traffic, neighbor reception, and what traffic would change after switching. The simulator assumes candidate packets pass all remaining firmware checks and have queue capacity. It cannot predict successful delivery, improved coverage, battery life, or exact delays.',
   'Measured airtime telemetry is a rolling radio metric. Modeled extra airtime is averaged across each chart bucket; they are shown separately and must not be added as an exact prediction. Periods without receiver telemetry are flagged, not treated as confirmed quiet time.',
   'Estimates require a verified CLIENT_BASE / ALL profile on the supported 2.8 firmware family. A stale cached profile is labeled; when unavailable, numerical scenarios are withheld.'
  ])methodology.append(el('p',text));
  const source=el('a','Meshtastic role behavior and firmware change');source.href='https://github.com/meshtastic/firmware/pull/8567';source.target='_blank';source.rel='noopener';methodology.append(source);section.append(methodology);
  let data=null,chart=null,sequence=0,loadedHours=null;
  function table(title,heads,rows){const wrap=el('div',null,'role-table');const t=el('table');t.append(el('caption',title));const thead=el('thead'),tr=el('tr');for(const h of heads){const th=el('th',h);th.scope='col';tr.append(th);}thead.append(tr);t.append(thead);const tb=el('tbody');for(const r of rows){const row=el('tr');r.forEach(v=>row.append(el('td',String(v))));tb.append(row);}t.append(tb);wrap.append(t);body.append(wrap);}
  function render(){
   if(!data)return;
   if(chart){chart.destroy();chart=null;}body.replaceChildren();
   const t=data.totals,p=data.profile,affected=t.affected||0;
   const profile=p?`${p.role||'Unknown role'} · firmware ${p.firmware||'unknown'} · ${p.use_preset?p.modem:'custom modem'} · ${p.favorites.length} favorites · read ${new Date(p.captured_at*1000).toLocaleString()}${data.profile_fresh?'':' · CACHED: collector currently unavailable'}`:'receiver configuration unavailable. It may be in use by the phone.';
   body.append(el('p',profile,'role-profile'));
   table('Measured traffic in the selected window',['Unique confirmed RF packets','Broadcast candidates with hops','Favorite candidates','Non-favorite candidates'],[[fmt(t.unique_rf),fmt(t.candidates),p?fmt(t.favorites):'Unknown',p?fmt(affected):'Unknown']]);
   const missing=data.bins.filter(b=>!b.hq_samples).length;
   body.append(el('p',`${missing} of ${data.bins.length} time buckets have no receiver airtime telemetry. Collection gaps and time before receiver was installed are not extrapolated.`,missing?'role-notice':'muted'));
   if(!data.model_ready){body.append(el('p','Scenario withheld: the current profile must confirm CLIENT_BASE, rebroadcast ALL, and supported 2.8 firmware. Measured traffic is still shown.','role-notice'));return;}
   const seconds=Number(air.value),fraction=Number(rate.value)/100;
   if(!Number.isFinite(seconds)||seconds<.05||seconds>5){body.append(el('p','Enter an assumed packet airtime between 0.05 and 5 seconds.','role-notice'));return;}
   if(!affected)body.append(el('p','No non-favorite broadcast candidates in this window. That provides no evidence of extra forwarding opportunities; it does not prove the two roles would behave identically.'));
   else body.append(el('p',`Under your ${rate.value}% cancellation assumption, receiver would attempt about ${fmt(affected*fraction)} additional rebroadcasts for this observed subset, consuming about ${fmt(affected*fraction*seconds/60,1)} extra transmit minutes. Whether anybody benefits remains unknown.`,'role-verdict'));
   table('Scenario estimates — not observed outcomes',['Assumed cancellations','Additional rebroadcasts','Extra TX minutes','Extra TX % of selected window'],[25,50,75,100].map(n=>[`${n}%${n===100?' · subset ceiling':''}`,fmt(affected*n/100),fmt(affected*n/100*seconds/60,2),fmt(affected*n/100*seconds/(data.hours*3600)*100,3)+'%']));
   body.append(el('p','The favorite candidates already receive special forwarding under CLIENT_BASE. The additional workload shown here comes from other nodes; it does not make receiver more sensitive or increase its transmit power.','muted'));
   const chartWrap=el('div',null,'role-chart'),canvas=el('canvas');canvas.setAttribute('role','img');canvas.setAttribute('aria-label','Measured channel and receiver transmit utilization with separate modeled extra transmit airtime. Exact values are in the table below.');chartWrap.append(canvas);body.append(chartWrap);
   const modeled=b=>b.affected*fraction*seconds/(data.bin_hours*3600)*100;
   if(window.Chart)chart=new Chart(canvas,{type:'line',data:{labels:data.bins.map(b=>new Date(b.time).toLocaleString()),datasets:[{label:'Measured channel utilization · peak sample %',data:data.bins.map(b=>b.channel_max),borderColor:'#68c9ff'},{label:'Measured receiver TX utilization · peak sample %',data:data.bins.map(b=>b.tx_max),borderColor:'#67ea94'},{label:'Modeled extra TX airtime · bucket average %',data:data.bins.map(b=>b.hq_samples||b.candidates?modeled(b):null),borderColor:'#f2c94c',borderDash:[6,4]}]},options:{responsive:true,maintainAspectRatio:false,animation:false,spanGaps:false,plugins:{legend:{labels:{color:'#cdd8e3'}}},scales:{y:{beginAtZero:true,title:{display:true,text:'Percent of time'}},x:{ticks:{maxTicksLimit:6}}},elements:{point:{radius:1}}}});
   else chartWrap.remove();
   const busiest=[...data.bins].sort((a,b)=>b.affected-a.affected)[0];
   if(busiest?.affected)body.append(el('p',`Largest candidate bucket: ${new Date(busiest.time).toLocaleString()} — ${fmt(busiest.affected)} non-favorite packets; measured channel peak ${busiest.channel_max==null?'unavailable':fmt(busiest.channel_max,2)+'%'}. This is a workload comparison, not a congestion forecast.`));
   // Tables provide accessible chart data without requiring hover.
   const detail=el('details');detail.append(el('summary','Exact time-bucket values'));body.append(detail);
   table('Time buckets',['Bucket starts','Affected packets','Channel peak %','receiver TX peak %','Modeled extra TX %','receiver samples'],data.bins.map(b=>[new Date(b.time).toLocaleString(),fmt(b.affected),b.channel_max==null?'No sample':fmt(b.channel_max,3),b.tx_max==null?'No sample':fmt(b.tx_max,3),fmt(modeled(b),3),b.hq_samples]));detail.append(body.lastElementChild);
   table('Nodes whose broadcast traffic could gain forwarding · top 12',['Originating node','ID','Candidates'],data.origins.map(n=>[n.name,n.id,fmt(n.packets)]));
   body.append(el('p',`Excluded from modeling: ${fmt(t.own)} receiver-origin records; ${fmt(t.other_receiver)} other-receiver records; ${fmt(t.non_rf)} non-RF; ${fmt(t.unconfirmed_rf)} without RF evidence; ${fmt(t.duplicates)} duplicates; ${fmt(t.non_broadcast)} non-broadcast; ${fmt(t.exhausted)} exhausted hops; ${fmt(t.unknown_hops)} unknown hops; ${fmt(t.diagnostic)} diagnostic broadcasts; ${fmt(t.missing_identity)} missing IDs. Startup records were removed before analysis.`,'muted'));
  }
  async function load(){
   if(panel.hidden)return;const id=++sequence,hours=window.getDashboardHours?.()||24;
   refresh.disabled=true;status.textContent='Reading saved receiver observations…';section.setAttribute('aria-busy','true');
   try{const response=await fetch(`/api/role-comparison?hours=${hours}`,{signal:AbortSignal.timeout(30000)});const d=await response.json();if(id!==sequence)return;if(!response.ok)throw Error(d.error||'Comparison unavailable');data=d;loadedHours=hours;render();status.textContent=`Last ${hours<24?hours+(hours===1?' hour':' hours'):fmt(hours/24,2)+(hours===24?' day':' days')} · calculated ${new Date(d.generated).toLocaleString()} · refresh on demand`;
   }catch(e){if(id!==sequence)return;data=null;if(chart){chart.destroy();chart=null;}body.replaceChildren();status.textContent=e.message||'Unable to load comparison. Try Refresh comparison.';}finally{if(id===sequence){refresh.disabled=false;section.removeAttribute('aria-busy');}}
  }
  rate.addEventListener('change',render);air.addEventListener('input',render);refresh.addEventListener('click',load);
  document.getElementById('dashboard-tab-insights').addEventListener('click',()=>{if(loadedHours!==(window.getDashboardHours?.()||24))load();});
  window.addEventListener('dashboard:time-window',()=>{loadedHours=null;load();});
  if(!panel.hidden)load();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
