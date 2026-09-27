(() => {
 function init(){
  const nav=document.getElementById('dashboardTabs'),main=document.querySelector('main');
  if(!nav||!main||document.getElementById('dashboard-tab-heardby'))return;
  const tab=document.createElement('button');tab.type='button';tab.id='dashboard-tab-heardby';tab.textContent='Heard by';tab.setAttribute('role','tab');tab.setAttribute('aria-selected','false');tab.setAttribute('aria-controls','dashboard-panel-heardby');tab.tabIndex=-1;
  const panel=document.createElement('section');panel.id='dashboard-panel-heardby';panel.className='dashboard-panel';panel.hidden=true;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tab.id);
  panel.innerHTML=`<div class="card"><h2>Heard by MSP ingestors</h2><p>Which ingestors submitted public reports for each node.</p><div style="display:flex;gap:14px;flex-wrap:wrap;align-items:center"><button id="refreshHeardBy" type="button">Refresh heard-by reports</button><button id="exportHeardByCsv" type="button" disabled>Export CSV</button><label>Find node or ingestor <input id="heardBySearch" type="search" placeholder="Name or node ID"></label></div><p id="heardByStatus" role="status">Press Refresh to load public reports. No automatic refresh.</p><p class="muted">Snapshot of up to 200 latest messages, 200 positions, and 200 telemetry records. This shows the submitting ingestor, not proof of a direct RF link or a complete list of receivers. Local/self reports are labeled. Receiver’s local RF measurements remain separate.</p><div id="heardBySummary" class="console-summary" aria-label="Filtered public-report summary"></div><p id="heardByCount" class="muted"></p><div class="node-table-scroll"><table><thead><tr><th>Node</th><th>Reported by ingestor</th><th>Reports in snapshot</th><th>Report types</th><th>Latest report</th></tr></thead><tbody id="heardByRows"><tr><td colspan="5">No reports loaded yet.</td></tr></tbody></table></div><p class="muted">External directory lookup is unavailable in this portable distribution.</p></div>`;
  nav.append(tab);main.append(panel);
  const refresh=panel.querySelector('#refreshHeardBy'),status=panel.querySelector('#heardByStatus'),body=panel.querySelector('#heardByRows'),search=panel.querySelector('#heardBySearch'),count=panel.querySelector('#heardByCount');
  let rows=[],checked=null,checkedUtc=null,visibleRows=[];
  const exportButton=panel.querySelector("#exportHeardByCsv");
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
    const response=await fetch('/api/msp-heard-by',{cache:'no-store'});const data=await response.json();if(!response.ok||!Array.isArray(data.rows))throw Error();
    rows=data.rows;checkedUtc=data.checked_at;checked=new Date(data.checked_at).toLocaleString();render();
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
