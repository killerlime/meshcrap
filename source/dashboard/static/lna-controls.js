(() => {
  let state=null, busy=false, polling=false, healthBusy=false, lastHealth=null;
  const el=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;};
  const fmt=(v,n=1)=>v==null?'—':Number(v).toFixed(n);
  const get=async(url,options={})=>{
    const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(15000),...options});
    const d=await r.json();if(!r.ok)throw new Error(d.error||`Request failed (${r.status})`);return d;
  };
  let box,status,note,confirm,on,off,unlock,key,analysis,banner;
  function renderState(d){
    state=d;const current=d.transitions.at(-1);
    if(window.LnaSwitches)window.LnaSwitches.update(d.transitions);
    status.textContent=`Recorded LNA: ${current.state==='ON'?'enabled':current.state==='OFF'?'disabled':'unknown'} · ${new Date(current.time_utc).toLocaleString()}`;
    on.disabled=busy||!d.unlocked||!confirm.checked||current.state==='ON';
    off.disabled=busy||!d.unlocked||!confirm.checked||current.state==='OFF';
    unlock.hidden=d.unlocked;
    const list=box.querySelector('[data-history]');list.replaceChildren();
    d.transitions.slice(-12).reverse().forEach(t=>list.append(el('li',`${new Date(t.time_utc).toLocaleString()} — LNA ${t.state==='ON'?'enabled':t.state==='OFF'?'disabled':'unknown'}`)));
  }
  let pending=false;
  window.addEventListener('dashboard:time-window',()=>{pending=true;refresh();});
  async function refresh(){
    if(polling||busy||document.hidden)return;polling=true;pending=false;
    const hours=window.getDashboardHours?.()||24;
    try{
      renderState(await get('/api/lna-experiment'));
      const d=await get(`/api/lna-analysis?hours=${hours}`);if(hours===(window.getDashboardHours?.()||24))renderAnalysis(d);
    }catch(e){note.textContent=e.message+' Previously shown values may be stale.';}
    finally{polling=false;if(pending)refresh();}
  }
  async function mark(value){
    if(busy||!state||!confirm.checked)return;
    busy=true;renderState(state);note.textContent='Recording physical state…';
    try{
      const d=await get('/api/lna-experiment/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({state:value,physical_change_confirmed:true,revision:state.revision})});
      confirm.checked=false;
      note.textContent=d.changed?'Recorded. The transition hour is excluded from comparisons.':'That state was already recorded; no new transition was added.';
      renderState({...d.experiment,revision:d.revision,unlocked:true});
      if(window.loadRfHealthHourly)window.loadRfHealthHourly();
    }catch(e){note.textContent=e.message;}
    finally{busy=false;if(state)renderState(state);await refresh();}
  }
  function renderAnalysis(d){
    analysis.replaceChildren(el('h3','Matched comparisons'));
    analysis.append(el('p',`${d.paired_hours} matched hour pair${d.paired_hours===1?'':'s'} · OFF → ON · same local clock hour, each hour used once`));
    if(d.paired_hours){
      const table=el('table');const head=el('tr');['Measurement','LNA OFF','LNA ON'].forEach(x=>head.append(el('th',x)));table.append(head);
      [['Packets / observed hour','packets_per_hour'],['Direct packets / observed hour','direct_per_hour'],['Average hourly RX bad share (%)','rx_bad_share_pct']].forEach(([title,k])=>{const r=el('tr');[title,fmt(d.off[k]),fmt(d.on[k])].forEach(x=>r.append(el('td',x)));table.append(r);});analysis.append(table);
    }else analysis.append(el('p','Waiting for complete, healthy OFF and ON hours at matching times of day.'));
    analysis.append(el('h4','Same direct nodes'));
    if(d.nodes.length){
      analysis.append(el('p',`Equal-weight node average SNR change: ${fmt(d.node_balanced_delta_snr,2)} dB (ON minus OFF).`));
      const table=el('table');const head=el('tr');['Node','Hour pairs','Packets OFF / ON','SNR OFF / ON','Change'].forEach(x=>head.append(el('th',x)));table.append(head);
      d.nodes.forEach(n=>{const r=el('tr');[n.node,n.matched_hours,`${n.off_packets} / ${n.on_packets}`,`${fmt(n.off_snr)} / ${fmt(n.on_snr)} dB`,`${fmt(n.delta_snr)} dB`].forEach(x=>r.append(el('td',String(x))));table.append(r);});analysis.append(table);
    }else analysis.append(el('p','Waiting for the same direct node with at least 3 SNR readings in each matched hour. Relayed packets are excluded from this signal comparison.'));
    const details=el('details');details.append(el('summary','Method and limitations'),el('p',d.method),el('p',d.limitations));analysis.append(details);
  }
  async function health(){
    if(healthBusy||document.hidden)return;healthBusy=true;
    try{
      const d=await get('/api/self-test');const c=d.checks;let message,level;
      const failed=['collector_service','dashboard_service','gateway_service','database_live','receiver_socket'].filter(k=>!c[k]?.ok);
      if(failed.length){level='fault';message='Collection warning: '+failed.map(k=>({collector_service:'collector stopped',dashboard_service:'dashboard stopped',gateway_service:'gateway stopped',database_live:'no recent collector data',receiver_socket:'Receiver disconnected'}[k])).join('; ')+'. Gaps must not be interpreted as LNA performance.';}
      else if(!c.recent_rf?.ok){level='warning';message='Mesh traffic is quiet. The collector is connected, but no recent RF packet was heard; this alone does not prove a collection fault.';}
      else {level='healthy';message='Collection healthy · Receiver connected · latest saved packet '+new Date(c.database_live.last_packet).toLocaleTimeString();}
      if(lastHealth&&lastHealth!=='healthy'&&level==='healthy')message='Collection recovered. '+message;
      banner.dataset.level=level;banner.textContent=message;lastHealth=level;
    }catch(e){banner.dataset.level='fault';banner.textContent='Cannot check collection health. Dashboard connection may be unavailable; displayed data may be stale.';lastHealth='unreachable';}
    finally{healthBusy=false;}
  }
  function init(){
    const heading=[...document.querySelectorAll('h2')].find(h=>h.textContent.trim()==='LNA Enabled / Disabled Test');if(!heading)return;
    const style=el('style');style.textContent='.lna-controls{padding:16px;border:1px solid var(--border);border-radius:10px;margin:12px 0}.lna-controls button{margin:8px 8px 8px 0}.lna-controls label{display:block;margin:10px 0}.lna-controls table{width:100%;text-align:left;margin:12px 0}.lna-controls th,.lna-controls td{padding:8px;border-bottom:1px solid var(--border)}.lna-health{padding:12px 16px;border:1px solid var(--border);border-left:5px solid #22a06b;border-radius:8px;margin:12px 0}.lna-health[data-level="fault"]{border-left-color:#e34949;background:#8b202022}.lna-health[data-level="warning"]{border-left-color:#dca12a;background:#a26c1022}.lna-controls button:disabled{opacity:.45;cursor:not-allowed}.lna-match{overflow-x:auto}';document.head.append(style);
    banner=el('div','Checking collection health…');banner.className='lna-health';banner.setAttribute('role','status');banner.setAttribute('aria-live','polite');
    const nav=document.getElementById('dashboardTabs');if(nav)nav.before(banner);else document.querySelector('main').prepend(banner);
    box=el('div');box.className='lna-controls';heading.after(box);
    status=el('strong','Loading recorded LNA state…');box.append(status,el('p','These buttons record a physical change; they do not switch the radio hardware. Leave the cavity filter and 30-foot LMR400 run unchanged. Record the state immediately after changing the LNA.'));
    unlock=el('form');const label=el('label','Dashboard control key ');key=el('input');key.type='password';key.autocomplete='off';key.required=true;label.append(key);const ub=el('button','Unlock controls');ub.type='submit';unlock.append(label,ub);box.append(unlock);
    unlock.addEventListener('submit',async e=>{e.preventDefault();ub.disabled=true;try{await get('/api/node-control/unlock',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:key.value})});key.value='';note.textContent='Controls unlocked.';await refresh();}catch(err){note.textContent=err.message;}finally{ub.disabled=false;}});
    const ack=el('label');confirm=el('input');confirm.type='checkbox';ack.append(confirm,document.createTextNode(' I have physically changed the LNA and am ready to record its current state.'));box.append(ack);
    on=el('button','Mark enabled');off=el('button','Mark disabled');on.type=off.type='button';on.disabled=off.disabled=true;on.addEventListener('click',()=>mark('ON'));off.addEventListener('click',()=>mark('OFF'));confirm.addEventListener('change',()=>state&&renderState(state));box.append(on,off);
    note=el('p');note.setAttribute('role','status');box.append(note);
    const history=el('details');history.append(el('summary','Recent state changes'));const list=el('ul');list.dataset.history='';history.append(list);box.append(history);
    analysis=el('section');analysis.className='lna-match';box.append(analysis);
    refresh();health();setInterval(refresh,60000);setInterval(health,30000);document.addEventListener('visibilitychange',()=>{if(!document.hidden){refresh();health();}});
  }
  window.addEventListener('load',init);
})();
