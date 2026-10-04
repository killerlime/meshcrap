(() => {
 function ingestorReport(rows,directory){
  const reporters=new Map(),nodeReporters=new Map();
  const ensure=(id,name)=>{if(!reporters.has(id))reporters.set(id,{id,name:name||id,reports:0,external:0,nodes:new Set(),kinds:new Set(),lastSeen:null});return reporters.get(id);};
  for(const d of directory){const r=ensure(d.node_id,d.name);r.lastSeen=d.last_seen;}
  for(const row of rows){const r=ensure(row.ingestor_id,row.ingestor_name);r.reports+=row.reports;for(const k of row.kinds)r.kinds.add(k);
   if(!row.self_report){r.external+=row.reports;r.nodes.add(row.node_id);if(!nodeReporters.has(row.node_id))nodeReporters.set(row.node_id,new Set());nodeReporters.get(row.node_id).add(row.ingestor_id);}}
  return [...reporters.values()].map(r=>({...r,exclusive:[...r.nodes].filter(n=>nodeReporters.get(n).size===1).length,yield:r.external?100*r.nodes.size/r.external:null})).sort((a,b)=>b.reports-a.reports||a.name.localeCompare(b.name));
 }
 function init(){
  const nav=document.getElementById('dashboardTabs'),main=document.querySelector('main');
  if(!nav||!main||document.getElementById('dashboard-tab-heardby'))return;
  const tab=document.createElement('button');tab.type='button';tab.id='dashboard-tab-heardby';tab.textContent='Heard by';tab.setAttribute('role','tab');tab.setAttribute('aria-selected','false');tab.setAttribute('aria-controls','dashboard-panel-heardby');tab.tabIndex=-1;
  const panel=document.createElement('section');panel.id='dashboard-panel-heardby';panel.className='dashboard-panel';panel.hidden=true;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tab.id);
  panel.innerHTML=`<div class="card"><h2>Heard by MSP ingestors</h2><p>Which ingestors submitted public reports for each node.</p><div style="display:flex;gap:14px;flex-wrap:wrap;align-items:center"><button id="refreshHeardBy" type="button">Refresh heard-by reports</button><button id="exportHeardByCsv" type="button" disabled>Export CSV</button><label>Find node or ingestor <input id="heardBySearch" type="search" placeholder="Name or node ID"></label></div><p id="heardByStatus" role="status">Press Refresh to load public reports. No automatic refresh.</p><p class="muted">Snapshot of up to 200 latest messages, 200 positions, and 200 telemetry records. This shows the submitting ingestor, not proof of a direct RF link or a complete list of receivers. Local/self reports are labeled. Receiver’s local RF measurements remain separate.</p><section aria-labelledby="ingestorReportTitle"><h3 id="ingestorReportTitle">Ingestor report card</h3><p>Contribution and efficiency in the current snapshot, ranked by report count.</p><label>Find ingestor <input id="ingestorReportSearch" type="search" placeholder="Ingestor name or ID"></label><p id="ingestorReportStatus" role="status">Refresh heard-by reports to load the report card.</p><div class="node-table-scroll" style="max-width:100%;overflow-x:auto" tabindex="0" role="region" aria-label="Ingestor report card table"><table><thead><tr><th>Ingestor</th><th>Reports</th><th>External reports</th><th>External nodes</th><th>Exclusive nodes</th><th>Shared nodes</th><th>Nodes per 100 external reports</th><th>Directory last seen</th><th>Report types</th></tr></thead><tbody id="ingestorReportRows"><tr><td colspan="9">No snapshot loaded yet.</td></tr></tbody></table></div><p class="muted">Exclusive means attributed only to that ingestor in this sample. Shared nodes do not prove duplicate packets. Nodes per 100 external reports measures diversity, not packet delivery or RF efficiency; repeated observations can be useful. Self reports are excluded from external metrics. These capped feeds cover different time spans, and last seen does not measure uptime.</p></section><h3>Node-by-node reports</h3><div id="heardBySummary" class="console-summary" aria-label="Filtered public-report summary"></div><p id="heardByCount" class="muted"></p><div class="node-table-scroll"><table><thead><tr><th>Node</th><th>Reported by ingestor</th><th>Reports in snapshot</th><th>Report types</th><th>Latest report</th></tr></thead><tbody id="heardByRows"><tr><td colspan="5">No reports loaded yet.</td></tr></tbody></table></div><p class="muted">External directory lookup is unavailable in this portable distribution.</p></div>`;
  nav.append(tab);main.append(panel);
  const refresh=panel.querySelector('#refreshHeardBy'),status=panel.querySelector('#heardByStatus'),body=panel.querySelector('#heardByRows'),search=panel.querySelector('#heardBySearch'),count=panel.querySelector('#heardByCount');
  let rows=[],checked=null,checkedUtc=null,visibleRows=[],directory=[];
  let directoryAvailable=false;
  const exportButton=panel.querySelector("#exportHeardByCsv");
  function renderReport(){
   const term=panel.querySelector('#ingestorReportSearch').value.trim().toLowerCase(),all=ingestorReport(rows,directory);
   const items=all.filter(r=>(r.name+' '+r.id).toLowerCase().includes(term)),body=panel.querySelector('#ingestorReportRows');body.replaceChildren();
   for(const r of items){const tr=document.createElement('tr');for(const value of [r.name+' ('+r.id+')',r.reports,r.external,r.nodes.size,r.exclusive,r.nodes.size-r.exclusive,r.yield===null?'—':r.yield.toFixed(1),r.lastSeen?new Date(r.lastSeen).toLocaleString():'Unavailable',[...r.kinds].sort().join(', ')||'None in snapshot']){const td=document.createElement('td');td.textContent=String(value);tr.append(td);}body.append(tr);}
   if(!items.length){const td=body.insertRow().insertCell();td.colSpan=9;td.textContent=checked?'No matching ingestors.':'No snapshot loaded yet.';}
   panel.querySelector('#ingestorReportStatus').textContent=checked?`${items.length} of ${all.length} ingestors · ${all.filter(r=>r.reports>0).length} represented in reports · Snapshot ${checked}. `+(directoryAvailable?'Directory-only ingestors show zero sampled reports, not proven downtime.':'Directory unavailable; showing only ingestors represented in reports.'): 'Refresh heard-by reports to load the report card.';
  }
  panel.querySelector('#ingestorReportSearch').addEventListener('input',renderReport);
  function render(){
   const term=search.value.trim().toLowerCase();const visible=rows.filter(r=>[r.node_name,r.node_id,r.ingestor_name,r.ingestor_id].some(v=>v.toLowerCase().includes(term)));
   window.ConsoleUI?.summary('heardBySummary',[['Nodes',new Set(visible.map(r=>r.node_id)).size,'In matching reports'],['Ingestors',new Set(visible.map(r=>r.ingestor_id)).size,'Submitting receivers'],['Reports',visible.reduce((n,r)=>n+r.reports,0),'In this snapshot'],['Local/self pairs',visible.filter(r=>r.self_report).length,'Not evidence of an RF link']]);
   visibleRows=visible;exportButton.disabled=!checked||visible.length===0;
   const fragment=document.createDocumentFragment();
   for(const item of visible){
    const tr=document.createElement('tr');
    for(const [name,id] of [[item.node_name,item.node_id],[item.ingestor_name+(item.self_report?' · Local/self report':''),item.ingestor_id]]){
     const cell=document.createElement('td'),label=document.createElement('strong'),sub=document.createElement('div');label.textContent=name;sub.textContent=id;sub.className='muted';cell.append(label,sub);tr.append(cell);
    }
    for(const value of [item.reports,item.kinds.join(', '),new Date(item.last_report).toLocaleString()]){const td=document.createElement('td');td.textContent=value;tr.append(td);}
    fragment.append(tr);
   }
   body.replaceChildren(fragment);if(!visible.length){const td=body.insertRow().insertCell();td.colSpan=5;td.textContent=checked?'No matching reports in this snapshot.':'No reports loaded yet.';}
   count.textContent=checked?`${visible.length} of ${rows.length} node–ingestor pairs · ${new Set(visible.map(r=>r.node_id)).size} nodes · ${new Set(visible.map(r=>r.ingestor_id)).size} ingestors`:'';
  }
  refresh.addEventListener('click',async()=>{
   refresh.disabled=true;status.textContent='Loading public reports…';
   try{
    const get=async(path,key)=>{const response=await fetch(path,{cache:'no-store'});const data=await response.json();if(!response.ok||!Array.isArray(data[key]))throw Error();return data;};
    const [heard,ingestors]=await Promise.allSettled([get('/api/msp-heard-by','rows'),get('/api/msp-ingestors','ingestors')]);
    if(heard.status!=='fulfilled')throw Error();const data=heard.value;
    directoryAvailable=ingestors.status==='fulfilled';directory=directoryAvailable?ingestors.value.ingestors:[];
    rows=data.rows;checkedUtc=data.checked_at;checked=new Date(data.checked_at).toLocaleString();render();renderReport();
    status.textContent=`Snapshot refreshed ${checked}. No automatic refresh.`+(data.unavailable.length?` Partial results: ${data.unavailable.join(', ')} unavailable.`:'')+(data.omitted?` ${data.omitted} records omitted because attribution or time was missing/invalid.`:'');
   }catch(_){status.textContent='Unable to refresh public reports. '+(checked?`Keeping the snapshot from ${checked}. `:'')+'Press Refresh to try again.';}
   finally{refresh.disabled=false;}
  });
  exportButton.addEventListener('click',()=>{
   ConsoleCSV.download('msp-heard-by',['Node','Node ID','Reporting ingestor','Ingestor ID','Local self report','Reports in snapshot','Report types','Latest report UTC','Snapshot refreshed UTC'],
     visibleRows.map(r=>[r.node_name,r.node_id,r.ingestor_name,r.ingestor_id,r.self_report,r.reports,r.kinds.join('; '),r.last_report,checkedUtc]));
  });
  search.addEventListener('input',render);
  tab.addEventListener('click',()=>{main.querySelectorAll('.dashboard-panel').forEach(p=>p.hidden=p!==panel);nav.querySelectorAll('[role="tab"]').forEach(b=>{b.setAttribute('aria-selected',String(b===tab));b.tabIndex=b===tab?0:-1;});});
  nav.addEventListener('click',e=>{if(e.target.closest('[role="tab"]')!==tab){panel.hidden=true;tab.setAttribute('aria-selected','false');tab.tabIndex=-1;}});
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
