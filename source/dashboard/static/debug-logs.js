(() => {
  function init(){
    const nav=document.getElementById('dashboardTabs'),main=document.querySelector('main');
    if(!nav||!main||document.getElementById('dashboard-tab-debug'))return;
    const button=document.createElement('button');button.type='button';button.textContent='Debug Logs';button.id='dashboard-tab-debug';button.setAttribute('role','tab');button.setAttribute('aria-selected','false');button.setAttribute('aria-controls','dashboard-panel-debug');button.tabIndex=-1;
    const panel=document.createElement('section');panel.id='dashboard-panel-debug';panel.className='dashboard-panel';panel.hidden=true;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',button.id);
    panel.innerHTML=`<div class="card"><h2>Debug Logs</h2><p class="muted">Recent application logs. Loaded only when you open this tab or press Load logs.</p><form id="debugLogForm" style="display:flex;gap:12px;flex-wrap:wrap;align-items:end"><label>Service<br><select name="service"><option value="collector">Collector</option><option value="dashboard">Web dashboard</option><option value="feed">Potato feed</option><option value="gateway">Mobile gateway</option><option value="all">All app services</option></select></label><label>Time range<br><select name="window"><option value="hour">Last hour</option><option value="day" selected>Last 24 hours</option><option value="week">Last 7 days</option></select></label><label>Level<br><select name="level"><option value="all">All levels</option><option value="warning">Warnings and errors</option></select></label><label>Lines<br><select name="limit"><option>100</option><option selected>200</option><option>500</option></select></label><button type="submit">Load logs</button></form><p id="debugLogStatus" class="muted" role="status">Ready.</p><label>Filter loaded logs <input id="debugLogSearch" type="search" placeholder="Search these lines…"></label><p id="debugLogCount" class="muted"></p><pre id="debugLogOutput" tabindex="0" aria-label="Debug log output" style="background:#101820;color:#d8e3ee;padding:16px;border-radius:8px;max-height:65vh;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 monospace">No logs loaded.</pre></div>`;
    nav.append(button);main.append(panel);
    const form=panel.querySelector('form'),status=panel.querySelector('#debugLogStatus'),output=panel.querySelector('pre'),search=panel.querySelector('input');
    let lines=[],busy=false,loaded=false;
    const levels=['EMERGENCY','ALERT','CRITICAL','ERROR','WARNING','NOTICE','INFO','DEBUG'];
    function render(){const term=search.value.toLowerCase();const visible=lines.filter(line=>line.toLowerCase().includes(term));document.getElementById('debugLogCount').textContent=`${visible.length} of ${lines.length} loaded entries`;output.textContent=visible.join('\n')||(lines.length?'No lines match this filter.':'No log entries in this selection.');}
    async function load(){
      if(busy)return;busy=true;form.querySelector('button').disabled=true;status.textContent='Loading logs…';
      try{
        const response=await fetch('/api/debug-logs?'+new URLSearchParams(new FormData(form)),{cache:'no-store',signal:AbortSignal.timeout(10000)});
        const data=await response.json();if(!response.ok)throw Error(data.error||'Unable to load logs.');
        lines=data.entries.map(e=>`${new Date(e.time).toLocaleString()}  ${e.service.replace('.service','')}  ${levels[Number(e.priority)]||'INFO'}\n${e.message}`);
        loaded=true;render();status.textContent=`${lines.length} recent entries · Loaded ${new Date(data.generated).toLocaleTimeString()} · Oldest first · No automatic refresh`;
      }catch(error){status.textContent=(error.name==='TimeoutError'?'Request timed out. Try again.':error.message)+' Previously loaded logs are retained.';}
      finally{busy=false;form.querySelector('button').disabled=false;}
    }
    form.addEventListener('submit',e=>{e.preventDefault();load();});search.addEventListener('input',render);
    button.addEventListener('click',()=>{
      main.querySelectorAll('.dashboard-panel').forEach(p=>p.hidden=p!==panel);
      nav.querySelectorAll('[role="tab"]').forEach(b=>{b.setAttribute('aria-selected',String(b===button));b.tabIndex=b===button?0:-1;});
      if(!loaded)load();
    });
    nav.addEventListener('click',e=>{if(e.target.closest('[role="tab"]')!==button){panel.hidden=true;button.setAttribute('aria-selected','false');button.tabIndex=-1;}});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
