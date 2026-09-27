(() => {
 function init(){
  const nav=document.getElementById('dashboardTabs'),main=document.querySelector('main');
  if(!nav||!main||document.getElementById('dashboard-tab-ingestors'))return;
  const tab=document.createElement('button');tab.type='button';tab.id='dashboard-tab-ingestors';tab.textContent='MSP Ingestors';tab.setAttribute('role','tab');tab.setAttribute('aria-selected','false');tab.setAttribute('aria-controls','dashboard-panel-ingestors');tab.tabIndex=-1;
  const panel=document.createElement('section');panel.id='dashboard-panel-ingestors';panel.className='dashboard-panel';panel.hidden=true;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tab.id);
  panel.innerHTML=`<div class="card"><h2>MSP Mesh Ingestors</h2><p>Nodes reporting to the public MSP Mesh monitor.</p><div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap"><button id="refreshIngestors" type="button">Refresh ingestors</button><span class="muted">On demand only · no automatic refresh</span></div><div id="ingestorSummary" class="console-summary" aria-label="Ingestor summary"></div><p id="ingestorStatus" role="status">Press Refresh ingestors to load the directory.</p><p class="muted">Recent means a check-in within one hour of refresh, not proof the node is online. Times use this browser’s timezone.</p><div class="node-table-scroll"><table><thead><tr><th>Node</th><th>Shortname</th><th>Check-in status</th><th>Last check-in</th><th>Preset</th><th>Feed version</th></tr></thead><tbody id="ingestorRows"><tr><td colspan="6">No directory loaded yet.</td></tr></tbody></table></div><p class="muted">External directory lookup is unavailable in this portable distribution.</p></div>`;
  nav.append(tab);main.append(panel);
  const refresh=panel.querySelector('#refreshIngestors'),status=panel.querySelector('#ingestorStatus'),body=panel.querySelector('#ingestorRows');
  let checked=null;
  refresh.addEventListener('click',async()=>{
   refresh.disabled=true;status.textContent='Loading MSP Mesh directory…';
   try{
    const response=await fetch('/api/msp-ingestors',{cache:'no-store'});const data=await response.json();
    if(!response.ok||!Array.isArray(data.ingestors))throw Error('MSP Mesh is unavailable.');
    const fragment=document.createDocumentFragment();
    for(const item of data.ingestors){
     const row=document.createElement('tr');
     const name=document.createElement('td'),strong=document.createElement('strong'),id=document.createElement('div');
     strong.textContent=item.name+(item.is_gunit?' · Your Receiver':'');id.className='muted';id.textContent=item.node_id;name.append(strong,id);row.append(name);
     for(const value of [item.short_name||'—',item.recent?'Recent (within 1h)':item.last_seen?'Older check-in':'Unknown',item.last_seen?new Date(item.last_seen).toLocaleString():'Not reported',item.preset,item.version]){
      const cell=document.createElement('td');cell.textContent=value;row.append(cell);
     }
     fragment.append(row);
    }
    body.replaceChildren(fragment);
    if(!data.ingestors.length){const row=body.insertRow();const cell=row.insertCell();cell.colSpan=6;cell.textContent='The monitor lists no ingestors.';}
    checked=new Date(data.checked_at).toLocaleString();
    const recent=data.ingestors.filter(n=>n.recent).length;
    window.ConsoleUI?.summary('ingestorSummary',[['Ingestors',data.ingestors.length,'Public directory'],['Recent',recent,'Check-in within 1 hour'],['Older or unknown',data.ingestors.length-recent,'Not an online/offline test']]);
    status.textContent=`${data.ingestors.length} ingestors · ${recent} recent · ${data.ingestors.length-recent} older/unknown · Refreshed ${checked}`;
   }catch(_){status.textContent='Unable to refresh MSP Mesh. '+(checked?`Keeping the directory from ${checked}. `:'')+'Press Refresh to try again.';}
   finally{refresh.disabled=false;}
  });
  tab.addEventListener('click',()=>{
   main.querySelectorAll('.dashboard-panel').forEach(p=>p.hidden=p!==panel);
   nav.querySelectorAll('[role="tab"]').forEach(b=>{b.setAttribute('aria-selected',String(b===tab));b.tabIndex=b===tab?0:-1;});
  });
  nav.addEventListener('click',event=>{if(event.target.closest('[role="tab"]')!==tab){panel.hidden=true;tab.setAttribute('aria-selected','false');tab.tabIndex=-1;}});
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
