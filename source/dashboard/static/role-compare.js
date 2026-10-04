(() => {
 'use strict';
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
 const fmt=(n,d=0)=>Number(n||0).toLocaleString(undefined,{maximumFractionDigits:d});
 const signed=(n,d=0)=>(n>0?'+':'')+fmt(n,d);
 const read=()=>{try{return JSON.parse(localStorage.getItem('rf-role-scenario'))||{};}catch{return {};}};
 function init(){
  const nav=document.getElementById('dashboardTabs'),main=document.querySelector('main');if(!nav||!main)return;
  const tab=el('button','HQ role comparison');tab.id='dashboard-tab-role';tab.type='button';tab.setAttribute('role','tab');tab.setAttribute('aria-controls','dashboard-panel-role');tab.setAttribute('aria-selected','false');tab.tabIndex=-1;
  const panel=el('section',null,'dashboard-panel');panel.id='dashboard-panel-role';panel.hidden=true;panel.tabIndex=0;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tab.id);
  const heading=el('div',null,'console-panel-heading');heading.append(el('h2','HQ role comparison'),el('p','Explore any device role using saved HQ observations'));panel.append(heading);nav.append(tab);main.append(panel);
  const section=el('section',null,'card role-compare');section.id='hq-role-scenarios';panel.append(section);
  const title=el('h3','What if HQ used a different role?');section.append(title,el('p','Choose a scenario below. These are saved-traffic estimates; HQ’s actual role stays unchanged.','muted'));
  const model=window.RFRoleModel,settings=read(),tools=el('div',null,'role-tools');section.append(tools);
  const field=(text,input)=>{const label=el('label',text);label.append(input);tools.append(label);return label;};
  const role=el('select');role.id='role-target';for(const [id,spec] of Object.entries(model.roles)){const o=el('option',id+(spec.kind==='legacy'?' · deprecated':''));o.value=id;role.append(o);}role.value=model.roles[settings.role]?settings.role:'ROUTER_LATE';field('Scenario role',role);
  const rate=el('select');rate.id='role-cancel';for(const n of [0,10,25,50,75,100]){const o=el('option',n+'%');o.value=n;rate.append(o);}rate.value=[0,10,25,50,75,100].includes(Number(settings.cancel))?String(settings.cancel):'50';field('Assumed CLIENT cancellation',rate);
  const number=(id,value,min,max,step)=>{const n=el('input');n.id=id;n.type='number';n.value=value;n.min=min;n.max=max;n.step=step;return n;};
  const air=number('role-airtime',settings.seconds??.4,.05,5,.05);field('Assumed airtime per relay (seconds)',air);
  const awake=number('role-awake',settings.awake??100,0,100,5),awakeLabel=field('Assumed awake share (%)',awake);
  const local=number('role-local',settings.local??100,0,100,5),localLabel=field('Assumed local-channel share (%)',local);
  const refresh=el('button','Refresh comparison');refresh.type='button';refresh.hidden=true;tools.append(refresh);
  const behavior=el('p',null,'role-notice'),status=el('p','Open this page to calculate.');status.setAttribute('role','status');section.append(behavior,status);
  const body=el('div');section.append(body);
  const details=el('details');details.append(el('summary','Scope, assumptions, and role definitions'));
  for(const text of [
   'This replays the same decoded, unique, confirmed RF broadcasts with remaining hops. HQ-origin traffic, unicast routing, diagnostics, startup records and undecoded traffic are excluded. A modeled relay is an attempt, not a successful delivery.',
   'Baseline = favorite candidates + non-favorite candidates × (1 − assumed cancellation). CLIENT uses all candidates × (1 − cancellation); CLIENT_MUTE uses zero; ROUTER and ROUTER_LATE use all candidates. CLIENT_BASE keeps the baseline. The same cancellation assumption applies to each comparison.',
   'Specialized roles use a conditional CLIENT forwarding estimate. TRACKER, SENSOR and TAK_TRACKER multiply by the assumed awake share; CLIENT_HIDDEN multiplies by the assumed local-channel share. These shares are assumptions, not measurements. Sleep is assumed independent of traffic timing. All other forwarding settings are held constant.',
   'Role-specific originating traffic, power consumption, exact delay, radio sensitivity, delivery, topology changes and additional packets heard after changing role are not modeled. ROUTER and ROUTER_LATE therefore share this count estimate, while their timing differs.',
   'Numerical comparisons require the existing verified CLIENT_BASE / ALL baseline on the supported 2.8 firmware family. Current favorites are replayed across the selected history. A cached profile is labeled. Legacy roles remain selectable for explanation; no unsupported numerical forecast is shown.'
  ])details.append(el('p',text));
  const source=el('a','Official Meshtastic device roles');source.href='https://meshtastic.org/docs/configuration/radio/device/';source.target='_blank';source.rel='noopener';details.append(source);section.append(details);
  let data=null,chart=null,sequence=0,loadedHours=null;
  const options=()=>({cancel:Number(rate.value),seconds:air.value===''?NaN:Number(air.value),awake:awake.value===''?NaN:Number(awake.value),local:local.value===''?NaN:Number(local.value)});
  function table(title,heads,rows,parent=body){const wrap=el('div',null,'role-table'),t=el('table');t.append(el('caption',title));const head=el('tr');heads.forEach(h=>{const th=el('th',h);th.scope='col';head.append(th);});const thead=el('thead');thead.append(head);t.append(thead);const tb=el('tbody');rows.forEach(r=>{const tr=el('tr');r.forEach(v=>tr.append(el('td',String(v))));tb.append(tr);});t.append(tb);wrap.append(t);parent.append(wrap);}
  function render(){
   const spec=model.roles[role.value];title.textContent=`What if HQ used ${role.value}?`;awakeLabel.hidden=!spec.awake;localLabel.hidden=!spec.local;behavior.textContent=spec.description;
   const o=options();try{localStorage.setItem('rf-role-scenario',JSON.stringify({role:role.value,...o}));}catch{}
   if(!data)return;if(chart){chart.destroy();chart=null;}const opened=!!body.querySelector('details[open]');body.replaceChildren();
   const t=data.totals,p=data.profile;
   body.append(el('p',p?`Current HQ: ${p.role||'unknown'} · firmware ${p.firmware||'unknown'} · ${p.favorites.length} favorites · ${data.profile_fresh?'profile read':'CACHED profile from'} ${new Date(p.captured_at*1000).toLocaleString()}`:'HQ profile unavailable.','role-profile'));
   body.append(el('p',`Observed period: ${new Date(data.start).toLocaleString()} – ${new Date(data.generated).toLocaleString()}`,'muted'));
   table('Measured candidate traffic',['Unique confirmed RF packets','Broadcast candidates with hops','Favorite candidates','Other candidates'],[[fmt(t.unique_rf),fmt(t.candidates),p?fmt(t.favorites):'Unknown',p?fmt(t.affected):'Unknown']]);
   if(spec.kind==='legacy'){body.append(el('p','Legacy scenario: behavior is documented above, but HQ’s current firmware is not a validated baseline for this deprecated role.','role-notice'));return;}
   if(!data.model_ready){body.append(el('p','Forwarding estimate unavailable: HQ must have a verified CLIENT_BASE / ALL profile on supported 2.8 firmware. Measured traffic and role descriptions remain available.','role-notice'));return;}
   const result=model.estimate(role.value,t,o);
   if(!result){body.append(el('p','Use airtime from 0.05 to 5 seconds and percentage assumptions from 0 to 100.','role-notice'));return;}
   body.append(el('p',`For this observed subset: about ${fmt(result.target,1)} modeled relay attempts in ${role.value}, versus ${fmt(result.baseline,1)} in the CLIENT_BASE baseline. Difference: ${signed(result.delta,1)} attempts and ${signed(result.minutes,2)} transmit minutes. These are assumptions, not measured transmissions.`, 'role-verdict'));
   if(spec.awake||spec.local)body.append(el('p',`Conditional estimate using ${spec.awake?o.awake+'% awake':o.local+'% local-channel'} share. Role-specific originating packets and any traffic missed while asleep are outside this replay.`,'role-notice'));
   table('Sensitivity to cancellation assumption',['CLIENT cancellations','Baseline attempts','Scenario attempts','Change in attempts','Change in TX minutes'],[0,25,50,75,100].map(cancel=>{const v=model.estimate(role.value,t,{...o,cancel});return [cancel+'%',fmt(v.baseline,1),fmt(v.target,1),signed(v.delta,1),signed(v.minutes,2)];}));
   const chartWrap=el('div',null,'role-chart'),canvas=el('canvas');canvas.setAttribute('role','img');canvas.setAttribute('aria-label','Measured channel and HQ transmit utilization, with separate modeled change in transmit airtime');chartWrap.append(canvas);body.append(chartWrap);
   const modeled=b=>model.estimate(role.value,b,o).delta*o.seconds/(data.bin_hours*3600)*100;
   if(window.Chart)chart=new Chart(canvas,{type:'line',data:{labels:data.bins.map(b=>new Date(b.time).toLocaleString()),datasets:[{label:'Measured channel utilization · peak %',data:data.bins.map(b=>b.channel_max),borderColor:'#68c9ff'},{label:'Measured HQ TX utilization · peak %',data:data.bins.map(b=>b.tx_max),borderColor:'#67ea94'},{label:'Modeled TX change · bucket average %',data:data.bins.map(b=>b.hq_samples||b.candidates?modeled(b):null),borderColor:'#f2c94c',borderDash:[6,4]}]},options:{responsive:true,maintainAspectRatio:false,animation:false,spanGaps:false,plugins:{legend:{labels:{color:'#cdd8e3'}}},scales:{y:{title:{display:true,text:'Percent of time / signed change'}},x:{ticks:{maxTicksLimit:6}}},elements:{point:{radius:1}}}});
   body.append(el('p',`${data.bins.filter(b=>!b.hq_samples).length} of ${data.bins.length} buckets have no HQ airtime telemetry. Measured peaks and modeled average changes are separate; do not add them as a forecast. Negative modeled changes mean fewer relay attempts, not negative radio usage.`,'muted'));
   const buckets=el('details');buckets.open=opened;buckets.append(el('summary','Exact time-bucket values'));body.append(buckets);
   table('Time buckets',['Bucket starts','Candidates','Baseline attempts','Scenario attempts','TX change %','HQ samples'],data.bins.map(b=>{const v=model.estimate(role.value,b,o);return [new Date(b.time).toLocaleString(),fmt(b.candidates),fmt(v.baseline,1),fmt(v.target,1),signed(modeled(b),3),b.hq_samples];}),buckets);
  }
  async function load(){
   if(panel.hidden)return;const id=++sequence,hours=window.getDashboardHours?.()||24;
   refresh.disabled=true;status.textContent='Reading saved HQ observations…';
   try{const response=await fetch(`/api/role-comparison?hours=${hours}`,{signal:AbortSignal.timeout(30000)});const d=await response.json();await RFRefresh.ready();if(id!==sequence||hours!==(window.getDashboardHours?.()||24))return;if(!response.ok)throw Error(d.error||'Comparison unavailable');data=d;loadedHours=hours;render();status.textContent='Calculated '+new Date(d.generated).toLocaleString();}
   catch(e){if(id===sequence)status.textContent=(e.message||'Unable to load comparison')+' · previous results retained.';}
   finally{if(id===sequence)refresh.disabled=false;}
  }
  for(const input of [role,rate])input.addEventListener('change',render);for(const input of [air,awake,local])input.addEventListener('input',render);refresh.addEventListener('click',load);
  tab.addEventListener('click',()=>{main.querySelectorAll('.dashboard-panel').forEach(p=>p.hidden=p!==panel);nav.querySelectorAll('[role=tab]').forEach(b=>{b.setAttribute('aria-selected',String(b===tab));b.tabIndex=b===tab?0:-1;});if(loadedHours!==(window.getDashboardHours?.()||24))load();});
  nav.addEventListener('click',e=>{if(e.target.closest('[role=tab]')!==tab)panel.hidden=true;});
  window.addEventListener('dashboard:time-window',()=>{loadedHours=null;load();});
  RFRefresh.every('role',load,120000,{label:'HQ role comparison'});render();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
