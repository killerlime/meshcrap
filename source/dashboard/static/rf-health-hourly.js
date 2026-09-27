(() => {
  let charts = [];
  const fmt = (x, n=1) => x == null ? '--' : Number(x).toFixed(n);
  const reliable = r => r.comparison_eligible === true;
  const label = h => new Date(h).toLocaleString([], {month:'short', day:'numeric', hour:'numeric'});
  function render(data) {
    const summary = document.getElementById('rfHealthHourlySummary');
    const note = document.getElementById('rfHealthHourlyNote');
    if (data.comparison !== 'lna') {
      summary.textContent = 'LNA comparison is waiting for the dashboard service update.';
      return;
    }
    const rows = data.timeline.filter(reliable);
    const off = rows.filter(r => r.lna_state === 'OFF');
    const on = rows.filter(r => r.lna_state === 'ON');
    const avg = (rr, key) => {
      const v = rr.map(r => r[key]).filter(x => x != null);
      return v.length ? v.reduce((a,b) => a+b,0)/v.length : null;
    };
    const rate = (rr, key) => {
      const m = rr.reduce((a,r) => a+r.observed_minutes,0);
      return m ? 60*rr.reduce((a,r) => a+r[key],0)/m : null;
    };
    const card = (title, value, detail) => `<div class="noc-record"><div class="muted">${title}</div><div class="value">${value}</div><div class="muted">${detail}</div></div>`;
    summary.innerHTML = card('Eligible hours', `${off.length} / ${on.length}`, 'LNA OFF / ON')
      + card('Packets / observed hr', `${fmt(rate(off,'packets'))} → ${fmt(rate(on,'packets'))}`, 'LNA OFF → ON')
      + card('Direct / observed hr', `${fmt(rate(off,'direct_packets'))} → ${fmt(rate(on,'direct_packets'))}`, 'LNA OFF → ON')
      + card('P10 SNR', `${fmt(avg(off,'p10_snr'))} → ${fmt(avg(on,'p10_snr'))} dB`, 'Hourly average · OFF → ON')
      + card('RX bad share', `${fmt(avg(off,'rx_bad_share_pct'))} → ${fmt(avg(on,'rx_bad_share_pct'))}%`, 'Hourly average · OFF → ON');
    note.textContent = `Selected window: ${data.hours<24?data.hours+'h':data.hours/24+'d'}. Fresh test started ` + new Date(data.experiment_start).toLocaleString()
      + '. Current LNA: ' + data.current_lna_state + '. Cavity filter attached; 30-foot LMR400 run to Receiver stays fixed. '
      + 'Only completed hours with at least 45 observed minutes qualify. Start, transition, restart hours and collection gaps longer than 3 minutes are excluded.'
      + (!on.length || !off.length ? ' Waiting for eligible data in both LNA states; no conclusion yet.' : ' Traffic and time-of-day differences can affect this comparison.');
    const points = data.timeline.filter(r => r.lna_state !== 'EXCLUDED');
    // A null endpoint exposes switches in the current hour without inventing data.
    if (points.length && Date.parse(data.generated) > Date.parse(points.at(-1).hour)) {
      points.push({hour:data.generated,lna_state:data.current_lna_state,comparison_eligible:false,observed_minutes:0});
    }

    charts.forEach(c => c.destroy());
    charts = [];
    const groups = [
      ['rfHealthReceptionChart', [['packets_per_observed_hour','Packets / observed hr'],['direct_per_observed_hour','Direct / observed hr'],['unique_nodes','Unique nodes']]],
      ['rfHealthSignalChart', [['median_snr','Median SNR'],['p10_snr','P10 SNR']]],
      ['rfHealthEnvironmentChart', [['rx_bad_share_pct','RX bad share %'],['channel_utilization','Channel utilization %'],['air_util_tx','Air utilization TX %']]]
    ];
    for (const [id, fields] of groups) {
      charts.push(new Chart(document.getElementById(id), {
        type:'line',
        data:{labels:points.map(r => label(r.hour)), datasets:fields.map(([key,title]) => ({label:title, data:points.map(r => reliable(r) ? r[key] : null), spanGaps:false}))},
        options:{responsive:true, maintainAspectRatio:false, interaction:{mode:'index',intersect:false}, scales:{x:{ticks:{maxTicksLimit:6,maxRotation:0,color:'#b8c9bf'}},y:{ticks:{color:'#b8c9bf'}}},plugins:{legend:{labels:{color:'#b8c9bf'}},lnaSwitches:{timestamps:points.map(r=>r.hour)},tooltip:{callbacks:{afterBody(items){
          if (!items.length) return '';
          const r = points[items[0].dataIndex];
          return [`LNA: ${r.lna_state}`, `Observed: ${r.observed_minutes} min`];
        }}}}}
      }));
    }
  }
  let loading=false, pending=false;
  window.addEventListener('dashboard:time-window',()=>{pending=true;load();});
  async function load() {
    if(loading||document.hidden||(typeof dashboardPanelVisible==='function'&&!dashboardPanelVisible('filter')))return;
    loading=true;pending=false;
    const hours=window.getDashboardHours?.()||24;
    try {
      const r = await fetch(`/api/rf-health-hourly?hours=${hours}`,{cache:'no-store',signal:AbortSignal.timeout(15000)});
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data=await r.json();
      if(hours===(window.getDashboardHours?.()||24))render(data);
    } catch(e) {
      console.error('LNA comparison',e);
      document.getElementById('rfHealthHourlyNote').textContent = 'Unable to refresh LNA comparison. Previously displayed data may be stale.';
    } finally {loading=false;if(pending)load();}
  }
  window.loadRfHealthHourly = load;
  window.addEventListener('load',() => {load(); setInterval(load,60000);});
})();


// Dashboard tabs: move existing sections without replacing their live elements.
(() => {
  const init = () => {
    const main = document.querySelector('main');
    if (!main || document.getElementById('dashboardTabs')) return;
    const card = title => [...main.querySelectorAll('h2')].find(h => h.textContent.trim() === title)?.closest('.card');
    const groups = [
      ['overview','Overview',[main.querySelector('.live-grid'),card('Mesh Records & Achievements')]],
      ['nodes','Nodes',[card('Nodes'),document.getElementById('detailcard'),document.getElementById('snrchart')?.closest('.graph-grid')]],
      ['map','Map & Coverage',[card('Mesh Map'),card('Home area Coverage')]],
      ['filter','LNA Test',[card('LNA Enabled / Disabled Test'),card('RF Environment')]],
      ['system','System & Events',[card('Receiver Connection'),card('System Self-Test'),card('Record RF / Configuration Event'),card('Recent Events')]]
    ];
    if (groups.some(([, ,items]) => items.some(x => !x))) {
      console.error('Dashboard sections changed; keeping the full-page layout.');
      return;
    }
    const style = document.createElement('style');
    style.textContent = `
      .dashboard-tabs{display:flex;gap:6px;overflow-x:auto;position:sticky;top:0;z-index:900;background:var(--bg);padding:12px 0;margin:0 0 16px;border-bottom:1px solid var(--border);scrollbar-width:thin}
      .dashboard-tabs button{flex:0 0 auto;min-height:44px;margin:0;padding:10px 17px;border:1px solid transparent;border-radius:9px;color:var(--muted);background:transparent;font-weight:600;white-space:nowrap}
      .dashboard-tabs button[aria-selected="true"]{color:var(--mesh);background:var(--mesh-soft);border-color:var(--mesh-border)}
      .dashboard-tabs button:focus-visible{outline:2px solid var(--mesh);outline-offset:2px}
      .dashboard-panel[hidden]{display:none!important}
      .dashboard-panel{display:grid;gap:18px;min-width:0;scroll-margin-top:75px}
      .dashboard-panel>*{min-width:0}
      .dashboard-panel .node-table-scroll{max-height:52vh}
      main>.topstats{margin-bottom:12px}
      main>.controls{margin:12px 0}
      #dashboard-panel-nodes #detailcard{scroll-margin-top:85px}
      @media(max-width:650px){.dashboard-tabs{gap:3px}.dashboard-tabs button{padding:9px 12px;font-size:13px}.dashboard-panel{gap:12px}main>.topstats{grid-template-columns:repeat(2,minmax(0,1fr))}}
    `;
    document.head.append(style);
    const nav=document.createElement('div');
    nav.id='dashboardTabs';nav.className='dashboard-tabs';
    nav.setAttribute('role','tablist');nav.setAttribute('aria-label','Dashboard sections');
    const panels={},buttons={};
    for (const [id,title,items] of groups) {
      const button=document.createElement('button');
      button.type='button';button.id='dashboard-tab-'+id;button.textContent=title;
      button.setAttribute('role','tab');button.setAttribute('aria-controls','dashboard-panel-'+id);
      const panel=document.createElement('section');
      panel.id='dashboard-panel-'+id;panel.className='dashboard-panel';
      panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',button.id);panel.tabIndex=0;
      items.forEach(item=>panel.append(item));
      panels[id]=panel;buttons[id]=button;nav.append(button);
      button.addEventListener('click',()=>activate(id,true));
      button.addEventListener('keydown',e=>{
        const ids=groups.map(g=>g[0]);let idx=ids.indexOf(id);
        if(e.key==='ArrowRight')idx=(idx+1)%ids.length;
        else if(e.key==='ArrowLeft')idx=(idx+ids.length-1)%ids.length;
        else if(e.key==='Home')idx=0;
        else if(e.key==='End')idx=ids.length-1;
        else return;
        e.preventDefault();activate(ids[idx],true);buttons[ids[idx]].focus();
      });
    }
    main.querySelectorAll(':scope > .space').forEach(x=>x.remove());
    const controls=main.querySelector(':scope > .controls');
    if(controls)controls.after(nav);else main.prepend(nav);
    groups.forEach(([id])=>main.append(panels[id]));
    function activate(id,scroll=false) {
      if(!panels[id])id='overview';
      for(const [key,panel] of Object.entries(panels)) {
        panel.hidden=key!==id;
        buttons[key].setAttribute('aria-selected',String(key===id));
        buttons[key].tabIndex=key===id?0:-1;
      }
      try{sessionStorage.setItem('mesh-dashboard-tab',id);}catch{}
      requestAnimationFrame(()=>{
        if(id==='map' && typeof meshMap!=='undefined' && meshMap){
          meshMap.invalidateSize();
          // The central tab refresh loads map data once.
        }
        if(typeof Chart!=='undefined' && Chart.getChart)panels[id].querySelectorAll('canvas').forEach(c=>Chart.getChart(c)?.resize());
        if(scroll && nav.getBoundingClientRect().top<0)nav.scrollIntoView({block:'start'});
      });
    }
    let initial='overview';try{initial=sessionStorage.getItem('mesh-dashboard-tab')||initial;}catch{}
    activate(initial);
    if(typeof selectNode==='function'){
      const original=selectNode;
      selectNode=function(node){
        if(typeof selectedNode==='undefined' || node!==selectedNode)activate('nodes',true);
        return original.apply(this,arguments);
      };
    }
    window.showDashboardTab=activate;
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
