/* Passive relay evidence; shares the dashboard time window and refresh controls. */
(() => {
 'use strict';
 function init(){
  const nav=document.getElementById('dashboardTabs'),main=document.querySelector('main');if(!nav||!main)return;
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
  const tab=el('button','Relays');tab.type='button';tab.id='dashboard-tab-relays';tab.setAttribute('role','tab');tab.setAttribute('aria-controls','dashboard-panel-relays');tab.setAttribute('aria-selected','false');tab.tabIndex=-1;
  const panel=el('section',null,'dashboard-panel');panel.id='dashboard-panel-relays';panel.hidden=true;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tab.id);
  const card=el('section',null,'card'),heading=el('h2','Relayed nodes'),note=el('p','Relayed traffic received here. This does not confirm HQ retransmitted it.');
  const toolbar=el('div',null,'rf-recent-toolbar'),label=el('label','Find node '),search=el('input');search.type='search';search.placeholder='Name or ID';search.setAttribute('aria-label','Find relayed node');label.append(search);toolbar.append(label);
  const status=el('p','Open to load relay activity.','rf-recent-note');status.setAttribute('role','status');
  const wrap=el('div',null,'rf-recent-table-wrap');wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','Sortable relay activity');
  const table=el('table',null,'rf-recent-table relay-table'),caption=el('caption','Relayed nodes');caption.className='rf-sr-only';const head=el('thead'),hr=el('tr'),body=el('tbody');head.append(hr);table.append(caption,head,body);wrap.append(table);
  const help=el('p','Unique originating packets · signal is the final hop. Relay IDs show only the last byte; multiple matches stay ambiguous.','rf-recent-help');
  card.append(heading,note,toolbar,status,wrap,help);panel.append(card);main.append(panel);nav.append(tab);
  const css=el('style');css.textContent='.relay-table{min-width:1050px}.relay-table td[data-column=relay]{min-width:210px;max-width:300px;white-space:normal}.relay-table td[data-column=relay] small{white-space:normal}.relay-table th:first-child,.relay-table td:first-child{min-width:180px}.relay-table td[data-column=relay] span{display:block;margin-bottom:5px}#dashboard-panel-relays{min-width:0}';document.head.append(css);
  const columns=[['name','Node'],['packets','Relayed packets'],['nodeinfo','Node info'],['relay','Observed relays'],['last_heard','Last heard'],['snr','SNR (dB)'],['rssi','RSSI (dBm)'],['hops','Hops'],['role','Role']];
  let rows=[],key='packets',direction=-1,busy=false,sequence=0,lastData=null;const headers=new Map();
  function render(){
   const query=search.value.trim().toLowerCase(),filtered=rows.filter(n=>[n.name,n.node_id,n.short_name].some(s=>String(s||'').toLowerCase().includes(query)));
   const text=n=>n.relays.map(r=>r.candidates.length===1?r.candidates[0].name:'0x'+r.byte).join(', ');
   const value=n=>key==='relay'?text(n):key==='last_heard'?Date.parse(n.last_heard):n[key];
   filtered.sort((a,b)=>{const x=value(a),y=value(b);if(x==null||y==null)return x==null?(y==null?0:1):-1;return direction*(typeof x==='number'&&typeof y==='number'?x-y:String(x).localeCompare(String(y),undefined,{numeric:true}))||a.node_id.localeCompare(b.node_id);});
   headers.forEach(({th,button,label},k)=>{th.setAttribute('aria-sort',key===k?(direction===1?'ascending':'descending'):'none');button.textContent=label+(key===k?(direction===1?' ↑':' ↓'):' ↕');});
   const fragment=document.createDocumentFragment();
   for(const n of filtered){const tr=el('tr');for(const [k,label] of columns){const td=el('td');td.dataset.column=k;td.dataset.label=label;
    if(k==='name'){const b=el('button',n.name,'rf-recent-node');b.type='button';b.addEventListener('click',()=>window.openTelemetry?.(n.node_id));td.append(b,el('small',[n.short_name,n.node_id].filter(Boolean).join(' · ')));}
    else if(k==='relay'){for(const r of n.relays){const name=r.candidates.length===1?r.candidates[0].name:r.candidates.length?'Ambiguous · 0x'+r.byte:'Unknown · 0x'+r.byte;const s=el('span',name+' · '+r.packets);s.title=r.candidates.map(c=>c.name+' '+c.node_id).join('\n')||'No matching known node';td.append(s);}if(n.unidentified_relay)td.append(el('small',n.unidentified_relay+' without relay ID'));}
    else if(k==='last_heard'){const date=new Date(n.last_heard),age=Math.max(0,Math.floor((Date.now()-date)/60000));td.textContent=age<1?'Just now':age<60?age+' min ago':age<1440?Math.floor(age/60)+' hr ago':Math.floor(age/1440)+' d ago';td.title=date.toLocaleString(undefined,{timeZoneName:'short'});}
    else td.textContent=n[k]==null?'—':k==='snr'?Number(n[k]).toFixed(1):String(n[k]);tr.append(td);}fragment.append(tr);}
   if(!filtered.length){const tr=el('tr'),td=el('td',query?'No matching nodes.':'No relayed packets recorded in this window.');td.colSpan=columns.length;tr.append(td);fragment.append(tr);}body.replaceChildren(fragment);
   if(lastData)status.textContent=filtered.length+' nodes · '+lastData.relayed_packets.toLocaleString()+' relayed packets · '+lastData.hours+'h · '+lastData.unknown_packets+' packets with unknown relay status';
  }
  for(const [k,label] of columns){const th=el('th'),button=el('button',label);th.scope='col';button.type='button';button.addEventListener('click',()=>{direction=key===k?-direction:['packets','nodeinfo','last_heard'].includes(k)?-1:1;key=k;render();});th.append(button);hr.append(th);headers.set(k,{th,button,label});}
  async function load(){if(panel.hidden||document.hidden)return;const hours=window.getDashboardHours?.()||24;if(busy){sequence++;return;}busy=true;const id=++sequence;status.textContent='Loading relay activity…';try{const r=await fetch('/api/relay-activity?hours='+hours,{signal:AbortSignal.timeout(20000)});if(!r.ok)throw Error('HTTP '+r.status);const data=await r.json();if(id!==sequence||hours!==(window.getDashboardHours?.()||24))return;rows=data.nodes;lastData=data;render();}catch(e){status.textContent='Could not refresh. Previous data remains visible.';console.error('Relay activity',e);}finally{busy=false;if(id!==sequence&&!panel.hidden)load();}}
  search.addEventListener('input',render);
  tab.addEventListener('click',()=>{main.querySelectorAll('.dashboard-panel').forEach(p=>p.hidden=p!==panel);nav.querySelectorAll('[role=tab]').forEach(b=>{b.setAttribute('aria-selected',String(b===tab));b.tabIndex=b===tab?0:-1;});load();});
  nav.addEventListener('click',e=>{if(e.target.closest('[role=tab]')!==tab){panel.hidden=true;tab.setAttribute('aria-selected','false');tab.tabIndex=-1;}});
  window.addEventListener('dashboard:time-window',load);window.RFRefresh?.every('relays',load,60000,{label:'Relays'});render();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
