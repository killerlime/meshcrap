(() => {
  function init(){
    const nav=document.getElementById('dashboardTabs'),main=document.querySelector('main');
    if(!nav||!main||document.getElementById('dashboard-tab-debug'))return;
    const button=document.createElement('button');button.type='button';button.textContent='Debug Logs';button.id='dashboard-tab-debug';button.setAttribute('role','tab');button.setAttribute('aria-selected','false');button.setAttribute('aria-controls','dashboard-panel-debug');button.tabIndex=-1;
    const panel=document.createElement('section');panel.id='debugLogPanel';panel.className='utility-debug';
    panel.innerHTML=`<div class="card"><h2>Debug Logs</h2><p class="muted">Application and Receiver radio logs. Open this section or press Load logs. Automatic updates start paused to preserve your place.</p><form id="debugLogForm" style="display:flex;gap:12px;flex-wrap:wrap;align-items:end"><label>Service<br><select name="service"><option value="receiver">Receiver radio · meshtasticd</option><option value="collector">Collector</option><option value="dashboard">Web dashboard</option><option value="feed">Potato feed</option><option value="gateway">Mobile gateway</option><option value="all">All app services</option></select></label><label>Time range<br><select name="window"><option value="hour">Last hour</option><option value="day" selected>Last 24 hours</option><option value="week">Last 7 days</option></select></label><label>Level<br><select name="level"><option value="all">All levels</option><option value="warning">Warnings and errors</option></select></label><label>Lines<br><select name="limit"><option>100</option><option selected>200</option><option>500</option></select></label><button type="submit">Load logs</button></form><p id="debugLogStatus" class="muted" role="status">Ready.</p><label>Filter loaded logs <input id="debugLogSearch" type="search" placeholder="Search these lines…"></label><button type="button" id="debugLogOlder" hidden>Load older receiver logs</button><p id="debugLogCount" class="muted"></p><pre id="debugLogOutput" tabindex="0" aria-label="Debug log output" style="background:#101820;color:#d8e3ee;padding:16px;border-radius:8px;max-height:65vh;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 monospace">No logs loaded.</pre></div>`;

    const form=panel.querySelector('form'),status=panel.querySelector('#debugLogStatus'),output=panel.querySelector('pre'),search=panel.querySelector('input');
    let lines=[],busy=false,loaded=false,nextCursor=null; const older=panel.querySelector("#debugLogOlder"); let activeSelection="";
    const levels=['EMERGENCY','ALERT','CRITICAL','ERROR','WARNING','NOTICE','INFO','DEBUG'];
    function render(){const term=search.value.toLowerCase();const visible=lines.filter(line=>line.toLowerCase().includes(term));document.getElementById('debugLogCount').textContent=`${visible.length} of ${lines.length} loaded entries`;output.textContent=visible.join('\n')||(lines.length?'No lines match this filter.':'No log entries in this selection.');}
    async function load(before=null){
      if(busy)return;busy=true;form.querySelector('button').disabled=true;status.textContent='Loading logs…';
      try{
        const params=new URLSearchParams(new FormData(form)); const selection=params.toString(); if(before && selection!==activeSelection)before=null; if(before)params.set('before',before); const response=await fetch('/api/debug-logs?'+params,{cache:'no-store',signal:AbortSignal.timeout(22000)});
        const data=await response.json();if(!response.ok)throw Error(data.error||'Unable to load logs.');
        const page=data.entries.map(e=>`${new Date(e.time).toLocaleString()}  ${e.service.replace('.service','')}  ${levels[Number(e.priority)]||'INFO'}\n${e.message}${e.truncated?'\n[Long entry truncated]':''}`); lines=before?[...page,...lines]:page; nextCursor=data.next_cursor||null; activeSelection=selection; older.hidden=!nextCursor;
        loaded=true;render();status.textContent=`${lines.length} recent entries · Loaded ${new Date(data.generated).toLocaleTimeString()} · Oldest first${data.source==='receiver'?' · Older entries available in pages; warning filter scans each page':''}`;
      }catch(error){status.textContent=(/401/.test(error.message)?'Unlock settings in Node Control to read logs.':error.name==='TimeoutError'?'Request timed out. Try again.':error.message)+' Previously loaded logs are retained.';}
      finally{busy=false;form.querySelector('button').disabled=false;}
    }
    older.addEventListener('click',()=>load(nextCursor)); form.addEventListener('change',()=>{nextCursor=null;older.hidden=true;});
    form.addEventListener('submit',e=>{e.preventDefault();load();});search.addEventListener('input',render);
    function mount(){
      const utilities=document.getElementById('dashboard-panel-utilities');if(!utilities)return;
      const detail=document.createElement('details');detail.className='card';detail.id='utility-debug-logs';const heading=document.createElement('summary');heading.textContent='Debug logs';detail.append(heading,panel);utilities.append(detail);
      detail.addEventListener('toggle',()=>{if(detail.open&&!loaded)load();});
      window.openRFDebugLogs=()=>{document.getElementById('dashboard-tab-utilities')?.click();detail.open=true;requestAnimationFrame(()=>detail.scrollIntoView({block:'start'}));};
      RFRefresh.every('debug',()=>load(),30000,{host:'#debugLogPanel',label:'Debug logs',defaultPaused:true,guard:()=>!search.value.trim()&&output.scrollTop===0,waiting:'Holding your log search or reading position'});
    }
    window.addEventListener('load',mount);

  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
