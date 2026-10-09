(() => {
 'use strict';
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
 const fmt=(v,d=1)=>v==null?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:d});
 const stamp=t=>new Date(t).toLocaleString();
 const windowName=h=>h<24?`${h} hour${h===1?'':'s'}`:h===24?'24 hours':`${h/24} days`;
 const colors=['#67ea94','#68c9ff','#f2c94c','#b39aff','#ed91ad','#ffac75'];
 function init(){
  const nav=document.getElementById('dashboardTabs'),main=document.querySelector('main');if(!nav||!main)return;
  const tab=el('button','Insights');tab.type='button';tab.id='dashboard-tab-insights';tab.setAttribute('role','tab');tab.setAttribute('aria-selected','false');tab.setAttribute('aria-controls','dashboard-panel-insights');tab.tabIndex=-1;
  const panel=el('section',null,'dashboard-panel insights');panel.id='dashboard-panel-insights';panel.hidden=true;panel.tabIndex=0;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tab.id);
  nav.append(tab);main.append(panel);
  const head=el('div',null,'insight-heading');head.append(el('h2','Your mesh, with a little perspective'),el('p','Changes, active nodes and mesh records.'));
  const toolbar=el('div',null,'insight-toolbar');const refresh=el('button','Refresh insights');refresh.type='button';refresh.hidden=true;const status=el('span','Open to load insights.');status.setAttribute('role','status');toolbar.append(refresh,status);
  const jumps=el('nav',null,'insight-jumps');jumps.setAttribute('aria-label','Insights sections');
  for(const [id,title] of [['mesh','Mesh briefing'],['improve','Improve the mesh'],['reduce','Reduce traffic'],['voices','The regulars'],['coverage','Coverage quest'],['diary','Receiver diary']]){const a=el('a',title);a.href='#insight-'+id;jumps.append(a);}
  panel.append(head,toolbar,jumps);
  // A separate, lazy-loaded workspace preserves scenario inputs between tab visits.
  const whatifTab=el('button','What-if');whatifTab.type='button';whatifTab.id='dashboard-tab-whatif';whatifTab.setAttribute('role','tab');whatifTab.setAttribute('aria-controls','dashboard-panel-whatif');whatifTab.setAttribute('aria-selected','false');whatifTab.tabIndex=-1;
  const whatifPanel=el('section',null,'dashboard-panel');whatifPanel.id='dashboard-panel-whatif';whatifPanel.hidden=true;whatifPanel.tabIndex=0;whatifPanel.setAttribute('role','tabpanel');whatifPanel.setAttribute('aria-labelledby',whatifTab.id);
  const whatifHeading=el('h2','What-if'),standalone=el('a','Open radio planner full page');standalone.href='/static/mesh-simulator.html';const radioPlanning=el('details',null,'card whatif-radio-planning');radioPlanning.append(el('summary','Radio settings, terrain & node builder'),standalone);whatifPanel.append(whatifHeading,radioPlanning);
  nav.append(whatifTab);main.append(whatifPanel);let simulatorFrame=null;
  new MutationObserver(()=>{for(const child of [...whatifPanel.children])if(child.tagName==='DETAILS'&&child!==radioPlanning&&child.id!=='trafficReductionSimulator'&&/terrain/i.test(child.querySelector('summary')?.textContent||''))radioPlanning.append(child);}).observe(whatifPanel,{childList:true});
  whatifTab.addEventListener('click',()=>{
   main.querySelectorAll('.dashboard-panel').forEach(p=>p.hidden=p!==whatifPanel);
   nav.querySelectorAll('[role=tab]').forEach(b=>{b.setAttribute('aria-selected',String(b===whatifTab));b.tabIndex=b===whatifTab?0:-1;});
   if(!simulatorFrame){simulatorFrame=el('iframe');simulatorFrame.title='What-if simulator and virtual node builder';simulatorFrame.src='/static/mesh-simulator.html?embedded=1';simulatorFrame.setAttribute('sandbox','allow-scripts');simulatorFrame.style.cssText='display:block;width:100%;height:80vh;min-height:520px;border:0;margin-top:12px;border-radius:12px';radioPlanning.append(simulatorFrame);}
  });
  nav.addEventListener('click',e=>{const other=e.target.closest('[role=tab]');if(other&&other!==whatifTab){whatifPanel.hidden=true;whatifTab.setAttribute('aria-selected','false');whatifTab.tabIndex=-1;}});
  setTimeout(()=>{tab.after(whatifTab);try{if(sessionStorage.getItem('console-active-tab')==='whatif')whatifTab.click();}catch{}},0);
  const blocks={};
  const trafficScript=el('script');trafficScript.src='/static/traffic-simulator.js';document.body.append(trafficScript);
  const terrainScript=el('script');terrainScript.src='/static/heywhatsthat.js';document.body.append(terrainScript);
  const tropoScript=el('script');tropoScript.src='/static/tropo-view.js';document.body.append(tropoScript);
  function block(id,title,sub){const section=el('section',null,'card insight-section');section.id='insight-'+id;section.append(el('h3',title),el('p',sub,'insight-sub'));const content=el('div');section.append(content);panel.append(section);blocks[id]=content;return content;}
  block('mesh','The mesh briefing','This window versus the previous window.');
  block('improve','What can improve the mesh?','Based on HQ reception. Change one thing, then compare equal windows.');
  block('reduce','How to reduce unnecessary data','Find traffic worth reviewing without treating useful reports or acknowledgments as waste.');
  block('voices','Meet the regulars','Originating nodes heard by Receiver. A relayed packet’s signal belongs to the last radio hop, so direct-link comparisons stand on their own.');
  block('coverage','The coverage quest','A separate, cumulative coverage survey—not limited by the time-window buttons.');
  block('diary','Receiver diary','Connection events within the selected window. A gap in collection is not evidence that the mesh went quiet.');
  const methodology=el('details',null,'card insight-method');methodology.append(el('summary','How this briefing thinks'));
  methodology.append(el('p','These statements are calculated on the Pi from saved observations. No external AI call, radio query, or new data collection is triggered. General activity includes LIVE decoded packets from other nodes, excluding routing acknowledgments, admin traffic and traceroutes. Imported metadata and startup snapshots are not counted as receptions. Position and telemetry replies may still contribute.'));
  methodology.append(el('p','“Observed minutes” means minutes containing Receiver’s regular self updates; it is a continuity indicator, not an uptime guarantee. Side-by-side windows may differ in traffic, time of day and weather. Quiet nodes are not necessarily offline. New-to-window nodes are not necessarily new to the mesh. LNA comparisons reuse the test’s matched healthy-hour rules. RF signal comparisons use direct packets only.'));
  panel.append(methodology);
  const charts=new Map();let busy=false,pending=false,loadedHours=null;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  function chart(canvas,type,labels,datasets,extra={}){
   const opts={responsive:true,maintainAspectRatio:false,animation:reduced.matches?false:{duration:350},plugins:{legend:{labels:{color:'#b8c9bf'}},tooltip:{callbacks:{}}},scales:type==='doughnut'?{}:{x:{ticks:{maxTicksLimit:7,maxRotation:0,color:'#b8c9bf'},grid:{display:false}},y:{beginAtZero:true,ticks:{color:'#b8c9bf'},grid:{color:'#ffffff12'}}},...extra};
   if(type!=='doughnut'){opts.scales.x.ticks.maxTicksLimit=Math.max(2,Math.min(7,Math.floor((canvas.parentElement.clientWidth||300)/140)));opts.onResize=(c,size)=>{c.options.scales.x.ticks.maxTicksLimit=Math.max(2,Math.min(7,Math.floor(size.width/140)));};}
   const c=new Chart(canvas,{type,data:{labels,datasets},options:opts});charts.set(canvas,c);return c;
  }
  function clear(id){const box=blocks[id];box.querySelectorAll('canvas').forEach(c=>{charts.get(c)?.destroy();charts.delete(c);});box.replaceChildren();return box;}
  function graph(box,label,height=250){const fig=el('figure',null,'insight-figure');const caption=el('figcaption',label);const wrap=el('div');wrap.style.height=height+'px';const c=el('canvas');c.setAttribute('role','img');c.setAttribute('aria-label',label);wrap.append(c);fig.append(caption,wrap);box.append(fig);return c;}
  function metric(label,value,note){const d=el('div',null,'insight-metric');d.append(el('div',label,'insight-label'),el('strong',value),el('small',note));return d;}
  function note(box,title,text,kind='neutral'){const n=el('article',null,'insight-observation '+kind);n.append(el('h4',title),el('p',text));box.append(n);}
  function table(box,title,headers,rows){const details=el('details');details.append(el('summary',title));const wrap=el('div',null,'insight-table');const t=el('table');const head=el('tr');headers.forEach(h=>{const th=el('th',h);th.scope='col';head.append(th);});const thead=el('thead');thead.append(head);t.append(thead);const body=el('tbody');rows.forEach(row=>{const tr=el('tr');row.forEach(v=>tr.append(el('td',String(v))));body.append(tr);});t.append(body);wrap.append(t);details.append(wrap);box.append(details);}
  function renderMesh(d){
   const box=clear('mesh'),a=d.current,b=d.previous;
   const rangeLabel=[...document.getElementById('dashboardTimeWindow').options].find(o=>Number(o.value)===Number(d.hours))?.textContent.trim()||windowName(d.hours);
   const currentPeriod=`the last ${rangeLabel}`,previousPeriod=`the previous ${rangeLabel}`;
   const counts=el('div',null,'insight-metrics');counts.append(metric('Packets heard',fmt(a.packets,0),`${fmt(b.packets,0)} · ${previousPeriod}`),metric('Distinct voices',fmt(a.nodes,0),`${fmt(b.nodes,0)} · ${previousPeriod}`),metric('Known direct packets',fmt(a.direct,0),`${fmt(a.unknown_hops,0)} packets have unknown hop count`),metric('Observed minutes',fmt(a.observed_pct)+'%',`${fmt(b.observed_pct)}% · ${previousPeriod}`));box.append(counts);
   const observations=el('div',null,'insight-observations');box.append(observations);
   const enough=a.observed_pct>=90&&b.observed_pct>=90;
   if(!enough)note(observations,'The logbook has some blank pages',`Self updates cover ${fmt(a.observed_pct)}% during ${currentPeriod} and ${fmt(b.observed_pct)}% during ${previousPeriod}. Packet totals are real, but a fair activity trend needs more continuous collection.`,'caution');
   else if(b.packets>=10){const pct=100*(a.packets-b.packets)/b.packets;note(observations,pct>=20?'The mesh got chattier':pct<=-20?'A quieter stretch':'A familiar rhythm',`${fmt(a.packets,0)} ordinary remote packets during ${currentPeriod}, ${fmt(Math.abs(pct),0)}% ${pct>=0?'more':'fewer'} than during ${previousPeriod}. This describes reception at Receiver, not total mesh traffic.`,pct<=-20?'caution':'good');}
   else note(observations,'Too little history for a trend',`During ${previousPeriod}, there were ${b.packets} ordinary remote packets. A percentage change would make a small sample look more impressive than it is.`);
   note(observations,'Who joined the conversation?',`${d.newly_heard_count} node${d.newly_heard_count===1?' was':'s were'} heard during ${currentPeriod} but not during ${previousPeriod}. ${d.quiet_count} previously active node${d.quiet_count===1?' has':'s have'} gone quiet in this view. That does not mean they are offline.`);
   const row=el('div',null,'insight-two');box.append(row);const label=d.bins.map(b=>new Date(b.time).toLocaleString([],{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}));
   chart(graph(row,'Traffic rhythm · packets per time bucket'),'bar',label,[{label:'Remote packets',data:d.bins.map(b=>b.packets),backgroundColor:d.bins.map(b=>b.observed_pct<90?'#f2c94c88':'#67ea9499'),borderRadius:3},{label:'Direct subset',data:d.bins.map(b=>b.direct),backgroundColor:'#68c9ff99',borderRadius:3}]);
   const entries=Object.entries(a.mix).sort((x,y)=>y[1]-x[1]);if(entries.length)chart(graph(row,'What the mesh was saying'),'doughnut',entries.map(([k])=>k.replace('_APP','').replaceAll('_',' ').toLowerCase()),[{data:entries.map(x=>x[1]),backgroundColor:colors,borderWidth:0}],{cutout:'65%'});else note(row,'A quiet page','No qualifying remote packets in this window.');
   box.append(el('p','Amber traffic bars mark buckets with fewer than 90% observed minutes. Direct packets are included in the total, not additional to it.','insight-sub'));
   table(box,'Read the packet mix as a table',['Packet type','Count'],Object.entries(a.mix).sort((x,y)=>y[1]-x[1]));
   table(box,'Read the traffic chart as a table',['Bucket begins','Packets','Direct','Nodes','Observed'],d.bins.map(x=>[stamp(x.time),x.packets,x.direct,x.nodes,fmt(x.observed_pct)+'%']));
  }
  function renderAdvice(d,coverage){
   const improve=clear('improve'),reduce=clear('reduce'),a=d.current,b=d.previous,x=d.improvement;
   const label=[...document.getElementById('dashboardTimeWindow').options].find(o=>Number(o.value)===Number(d.hours))?.textContent.trim()||windowName(d.hours);
   const packetName=k=>({POSITION_APP:'Position',TELEMETRY_APP:'Telemetry',NODEINFO_APP:'Node info',TRACEROUTE_APP:'Traceroute',ADMIN_APP:'Admin',ROUTING_APP:'Routing / ACK'}[k]||k.replace('_APP','').replaceAll('_',' '));
   const sources={tips:'https://meshtastic.org/docs/configuration/tips/',position:'https://meshtastic.org/docs/configuration/radio/position/',telemetry:'https://meshtastic.org/docs/configuration/module/telemetry/'};
   function card(parent,title,evidence,action,tradeoff,state='neutral',source=null){
    const c=el('article',null,'insight-advice '+state);c.append(el('span',state==='good'?'● Good evidence':state==='caution'?'● Review suggested':'○ Worth checking','advice-state'),el('h4',title),el('p',evidence),el('p',action));
    const detail=el('details');detail.append(el('summary','Tradeoff & validation'),el('p',tradeoff));if(source){const link=el('a','Meshtastic guidance ↗');link.href=source;link.target='_blank';link.rel='noopener noreferrer';detail.append(link);}c.append(detail);parent.append(c);return c;
   }
   function jump(parent,text,id){const button=el('button',text);button.type='button';button.addEventListener('click',()=>document.getElementById('dashboard-tab-'+id)?.click());parent.append(button);}
   const metrics=el('div',null,'insight-metrics insight-advice-metrics');
   metrics.append(metric('Collection observed',fmt(a.observed_pct)+'%',`Last ${label}`),metric('Known direct share',a.packets?fmt(100*a.direct/a.packets)+'%':'—',`${fmt(a.direct,0)} direct · ${fmt(a.unknown_hops,0)} unknown-hop receipts`),metric('Regulars gone quiet',fmt(d.quiet_count,0),'Missing at HQ does not mean offline'));improve.append(metrics);
   const grid=el('div',null,'insight-advice-grid');improve.append(grid);
   if(a.observed_pct<90||b.observed_pct<90)card(grid,'First, make the comparison trustworthy',`HQ self updates cover ${fmt(a.observed_pct)}% of this range and ${fmt(b.observed_pct)}% of the previous range.`, 'Check collector connectivity and power before attributing lower traffic to mesh performance. The 90% threshold is this dashboard’s comparison rule.','Repeat the same time range after collection stabilizes. More received packets alone does not prove better message delivery.','caution');
   else card(grid,'Collection is steady enough for a comparison',`Observed minutes are ${fmt(a.observed_pct)}% now versus ${fmt(b.observed_pct)}% before.`, 'Use this range as a baseline. Change one setting or one physical factor, then compare direct reception and actual message delivery.','Self updates measure logging continuity, not RF uptime. Time of day, mobility and weather can still change the result.','good');
   const declines=d.signals.filter(n=>n.delta<=-3).sort((a,b)=>a.delta-b.delta);
   if(declines.length){const n=declines[0];card(grid,'Check the strongest observed link decline',`${n.name}: direct median SNR changed ${fmt(n.previous)} → ${fmt(n.current)} dB (${fmt(n.delta)} dB), from ${n.previous_samples} to ${n.samples} samples.`, 'Check placement, antenna connections and obstructions on this link before adding relay traffic. Compare it again under similar conditions.','A 3 dB decline is a review cue, not a failure threshold. Different senders, settings or conditions can explain a shift; SNR alone is not a delivery test.','caution');}
   else card(grid,'Build stronger direct paths',`${fmt(a.direct,0)} known direct receipts out of ${fmt(a.packets,0)} ordinary remote receipts; ${fmt(a.unknown_hops,0)} have unknown hops. No ≥3 dB decline appears among the sampled comparison nodes.`, 'Use a repeatable route or fixed test location to compare antenna placement and a clearer path. Use LNA Test for matched receiver experiments.','This direct share depends on who transmits and what HQ hears. It cannot diagnose a coverage hole or justify an amplifier by itself. Only the busiest sampled nodes are compared.');
   if(coverage?.counts)card(grid,'Measure the coverage gaps before adding infrastructure',`${fmt(coverage.demonstrated_pct)}% demonstrated coverage; ${fmt(coverage.counts.UNTESTED||0,0)} untested cells in the cumulative survey.`, 'Survey the missing areas you actually need to use. Repeat message tests in both directions before deciding where a relay would help.','Coverage data is cumulative and is not restricted to the time dropdown. An untested cell is not a dead zone, and receiving one packet does not guarantee reliable service.');
   else card(grid,'Collect coverage evidence', 'Coverage survey data is unavailable for this refresh.', 'Open Map & coverage and plan tests along the routes you need. Avoid choosing relay sites from received node count alone.','Confirm both directions and repeat tests at relevant times before treating a route as reliable.');
   card(grid,'Review roles and hop limits against the routes you need',`${fmt(a.relayed,0)} receipts have known relayed hops; ${fmt(d.quiet_count,0)} previously active nodes were not heard in this range.`, 'Use HQ role comparison before changing HQ’s role. Favor ordinary client roles for ordinary nodes; coordinate infrastructure roles and test the lowest hop limit that still reaches your intended destinations.','Missing nodes and relayed counts do not establish congestion. Fewer hops or less relaying can reduce reach and redundancy. Role simulation estimates are not measured savings.', 'neutral',sources.tips);
   const actions=el('div',null,'insight-advice-actions');jump(actions,'Map & coverage','map');jump(actions,'HQ role comparison','role');jump(actions,'LNA test','filter');improve.append(actions);
   if(!x){reduce.append(el('p','Traffic review is unavailable until the analysis service updates.'));return;}
   const total=x.remote_receipts,periodic=x.periodic_receipts;
   const rm=el('div',null,'insight-metrics insight-advice-metrics');rm.append(metric('Decoded remote receipts',fmt(total,0),`Last ${label} · includes diagnostics`),metric('Report-type receipts',fmt(periodic,0),total?`${fmt(100*periodic/total)}% position, telemetry and node info`:'No receipts in this range'),metric('Illustrative 50% reduction',periodic?fmt(periodic/2):'—','Report receipts only · not an airtime forecast'));reduce.append(rm);
   reduce.append(el('p','These are receipts at HQ, not unique mesh transmissions or measured airtime. Report types may include replies. A hypothetical 50% reduction assumes all counted reports are reducible and reception stays comparable; it is a planning bound, not a recommended blanket cut.','insight-sub'));
   const rg=el('div',null,'insight-advice-grid');reduce.append(rg);
   const choices=[
    ['POSITION_APP','Match position reporting to movement','For fixed nodes you own, review the broadcast interval and fields you need. For moving nodes, review Smart Broadcast and its distance and time thresholds.','Slower reporting makes locations less current. Keep timely positions for tracking and safety uses; GPS sampling and radio broadcasts are separate settings.',sources.position],
    ['TELEMETRY_APP','Keep telemetry that supports a decision','Review device and sensor report intervals on nodes you manage. Lengthen intervals only where battery, environment or power changes do not need rapid updates.','Fewer reports can hide developing faults or weaken LNA and reception comparisons. This count combines telemetry types and does not prove repeated identical values.',sources.telemetry],
    ['NODEINFO_APP','Review routine identity announcements','Check node-info broadcast intervals and unexpected reconnects or restarts on managed nodes. Avoid repeatedly requesting information already available.','Node information helps discovery. Some receipts may be requested replies; the observed spacing does not reveal the configured interval.',sources.tips]
   ].sort((a,b)=>(x.mix[b[0]]||0)-(x.mix[a[0]]||0));
   for(const [kind,title,action,tradeoff,source] of choices){const n=x.mix[kind]||0;card(rg,title,`${fmt(n,0)} ${packetName(kind).toLowerCase()} receipts · ${total?fmt(100*n/total):'0'}% of decoded remote receipts.`,n?action:'None observed in this range. Revisit this category if traffic appears; there is no measured reduction opportunity here.',tradeoff,'neutral',source);}
   const diag=(x.mix.TRACEROUTE_APP||0)+(x.mix.ADMIN_APP||0);
   card(rg,'Keep radio diagnostics deliberate',`${fmt(diag,0)} traceroute/admin receipts and ${fmt(x.mix.ROUTING_APP||0,0)} routing/ACK receipts were observed.`, 'Avoid repeated radio traceroutes and manual telemetry requests when stored readings answer the question. Dashboard refresh reads stored data; pausing it reduces web requests, not mesh RF traffic.','Routine acknowledgments support delivery and are not classified as waste. These are received diagnostics, not a count of actions initiated by HQ. No payload-level duplicate analysis is available.');
   table(reduce,'Report senders to review · top 12 by received count',['Node','Report type','Receipts','Median arrival gap'],x.cadence.map(n=>[n.name,packetName(n.kind),n.count,n.median_gap_minutes==null?'Too few intervals':`${fmt(n.median_gap_minutes)} min`]));
   reduce.append(el('p','Arrival gaps require at least four distinct reception times and can be distorted by missed packets, rebroadcasts, requests and collection gaps. High volume alone is not evidence of abuse. Review only settings on nodes you manage, and coordinate with other owners.','insight-sub'));
   const tryScenario=el('button','Try these reductions on the simulation map');tryScenario.type='button';tryScenario.addEventListener('click',()=>{document.getElementById('dashboard-tab-whatif')?.click();const section=document.getElementById('trafficReductionSimulator');if(section){section.open=true;section.scrollIntoView({block:'start',behavior:'smooth'});}});reduce.append(tryScenario);
   table(reduce,'All decoded remote traffic · evidence',['Packet type','Receipts','Share'],Object.entries(x.mix).sort((a,b)=>b[1]-a[1]).map(([kind,n])=>[packetName(kind),n,total?fmt(100*n/total)+'%':'—']));
  }

  function renderVoices(d){const box=clear('voices'),row=el('div',null,'insight-two');box.append(row);
   const leaders=el('div');row.append(leaders);leaders.append(el('h4','The most talkative origins'));
   const max=Math.max(1,...d.leaders.map(n=>n.packets));for(const n of d.leaders.slice(0,7)){const item=el('div',null,'insight-ranking');const line=el('div');line.append(el('span',n.name),el('strong',`${n.packets} packets`));item.append(line);const track=el('div',null,'insight-track');const fill=el('div');fill.style.width=(100*n.packets/max)+'%';track.append(fill);item.append(track);leaders.append(item);}if(!d.leaders.length)leaders.append(el('p','No qualifying packets yet.'));
   const side=el('div');row.append(side);const strongest=d.leaders.filter(n=>n.direct_samples>=3).sort((a,b)=>b.median_snr-a.median_snr)[0];
   if(strongest)note(side,'A strong direct voice',`${strongest.name} has a median direct SNR of ${fmt(strongest.median_snr)} dB across ${strongest.direct_samples} samples. This is the strongest qualifying direct median among the 12 busiest nodes shown.`,'good');else note(side,'Direct-link spotlight is warming up','At least three direct SNR readings from a listed node are needed before naming a standout.');
   if(d.signals.length){const n=d.signals[0];note(side,'The biggest measured signal shift',`${n.name}: ${fmt(n.previous)} → ${fmt(n.current)} dB median direct SNR (${n.delta>=0?'+':''}${fmt(n.delta)} dB). Based on ${n.previous_samples} previous and ${n.samples} current readings; movement and conditions may explain the change.`);}else note(side,'No apples-to-apples signal shift yet','No node has at least three direct SNR readings in both windows. Relayed readings are deliberately excluded.');
   table(box,'Busiest nodes · full evidence',['Node','Packets','Direct SNR samples','Median direct SNR','Last heard'],d.leaders.map(n=>[n.name,n.packets,n.direct_samples,fmt(n.median_snr)+' dB',stamp(n.last_seen)]));
   table(box,`Regulars gone quiet (${d.quiet_count}) · top 12`,['Node','Previous packets','Last recorded in previous window'],d.quiet.map(n=>[n.name,n.previous_packets,stamp(n.last_seen)]));
   table(box,`New to this window (${d.newly_heard_count}) · top 12`,['Node','Packets'],d.newly_heard.map(n=>[n.name,n.packets]));
   table(box,'Same-node direct signal changes · top 12',['Node','Previous median','Current median','Change','Samples before / now'],d.signals.map(n=>[n.name,fmt(n.previous)+' dB',fmt(n.current)+' dB',fmt(n.delta)+' dB',`${n.previous_samples} / ${n.samples}`]));
  }
  function renderCoverage(d){const box=clear('coverage');const pct=Number(d.demonstrated_pct||0);const track=el('div',null,'insight-coverage');track.setAttribute('role','progressbar');track.setAttribute('aria-label','Demonstrated coverage toward 90 percent target');track.setAttribute('aria-valuemin','0');track.setAttribute('aria-valuemax','100');track.setAttribute('aria-valuenow',String(pct));const fill=el('div');fill.style.width=Math.min(100,pct)+'%';track.append(fill);box.append(track);
   const metrics=el('div',null,'insight-metrics');metrics.append(metric('Demonstrated',fmt(pct)+'%','Target: 90%'),metric('Proven cells',fmt(d.counts?.PROVEN||0,0),`${d.cell_miles}-mile grid`),metric('Untested territory',fmt(d.counts?.UNTESTED||0,0),'Untested is not failed'),metric('Evidence packets',fmt(d.evidence_packets||0,0),'Fixed and mobile nodes both count'));box.append(metrics);
   note(box,pct>=90?'Target reached!':'Room for the next field trip',pct>=90?'90% coverage target reached. Untested cells remain.':`${fmt(Math.max(0,90-pct))} percentage points remain to the survey target. An empty cell means no qualifying evidence here—not proof that a radio cannot work there.`);
   const button=el('button','Explore the coverage map');button.type='button';button.addEventListener('click',()=>document.getElementById('dashboard-tab-map')?.click());box.append(button);
  }
  function renderDiary(d){const box=clear('diary');if(!d.events.length){note(box,'No recorded connection events','No connection or configuration events recorded in this window. Unrecorded changes are still possible.');return;}
   const list=el('ol',null,'insight-diary');for(const ev of d.events){const item=el('li');const time=el('time',stamp(ev.event_time));time.dateTime=ev.event_time;item.append(time,el('strong',({CONNECTED:'Receiver connection established',CONNECTION_ERROR:'Radio connection interrupted',START:'Collector started',STOP:'Collector stopped',WEB_CONFIG_SUBMITTED:'Radio settings submitted',CHANNEL_ORDER_CHANGED:'Channel order changed'})[ev.event_type]||ev.event_type),el('p',ev.message));list.append(item);}box.append(list);
  }
  async function get(url){const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(25000)});if(!r.ok)throw Error(`Data unavailable (${r.status})`);return r.json();}
  async function load(){if(panel.hidden||document.hidden)return;if(busy){pending=true;return;}busy=true;pending=false;refresh.disabled=true;const openDetails=new Set([...panel.querySelectorAll('details[open]')].map(d=>d.querySelector('summary')?.textContent));const hours=window.getDashboardHours?.()||24;status.textContent='Reading the logbook…';panel.setAttribute('aria-busy','true');
   if(loadedHours!==hours){for(const id of Object.keys(blocks)){clear(id).append(el('p','Gathering observations…','insight-loading'));}}
   try{const results=await Promise.allSettled([get(`/api/insights?hours=${hours}`),get('/api/coverage')]);
    await RFRefresh.ready();
    if(hours!==(window.getDashboardHours?.()||24)){pending=true;return;}
    let failed=0;const good=i=>results[i].status==='fulfilled';
    if(good(0)){renderMesh(results[0].value);renderAdvice(results[0].value,good(1)?results[1].value:null);renderVoices(results[0].value);renderDiary(results[0].value);}else{failed++;for(const id of ['mesh','improve','reduce','voices','diary'])clear(id).append(el('p','The logbook could not be read. Use Refresh insights to try again.'));}
    if(good(1))renderCoverage(results[1].value);else{failed++;clear('coverage').append(el('p','Coverage data is unavailable right now.'));}
    panel.querySelectorAll('details').forEach(d=>{if(openDetails.has(d.querySelector('summary')?.textContent))d.open=true;});loadedHours=hours;status.textContent=`Last ${windowName(hours)} · ${failed?'Some sections unavailable':'Updated'} ${new Date().toLocaleTimeString()}`;panel.classList.add('insight-loaded');
   }catch(e){status.textContent='Refresh failed. Try again.';console.error('Insights',e);}finally{busy=false;refresh.disabled=false;panel.setAttribute('aria-busy','false');if(pending)load();}}
  refresh.addEventListener('click',load);
  function activate(){main.querySelectorAll('.dashboard-panel').forEach(p=>p.hidden=p!==panel);nav.querySelectorAll('[role=tab]').forEach(b=>{b.setAttribute('aria-selected',String(b===tab));b.tabIndex=b===tab?0:-1;});load();}
  tab.addEventListener('click',activate);
  nav.addEventListener('click',e=>{const target=e.target.closest('[role=tab]');if(target&&target!==tab){panel.hidden=true;tab.setAttribute('aria-selected','false');tab.tabIndex=-1;}});
  // One keyboard path for all existing and added tabs; click handlers retain ownership.
  nav.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;const tabs=[...nav.querySelectorAll('[role=tab]')],idx=tabs.indexOf(document.activeElement);if(idx<0)return;e.preventDefault();e.stopImmediatePropagation();const next=e.key==='Home'?0:e.key==='End'?tabs.length-1:(idx+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;tabs[next].click();tabs[next].focus();},true);
  window.addEventListener('dashboard:time-window',load);RFRefresh.every('insights',load,120000);
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
