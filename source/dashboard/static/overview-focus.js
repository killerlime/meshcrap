/* Presentation-only refinement. Existing tab handlers and RF calculations stay authoritative. */
(() => {
  'use strict';
  const el = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  const byId = id => document.getElementById(id);
  const count = value => Number.isFinite(value) ? value.toLocaleString() : '—';
  const selectedHours = () => window.getDashboardHours?.() || 24;
  const windowLabel = h => h < 24 ? `${h}h` : h % 24 === 0 ? `${h / 24}d` : `${h}h`;
  const windowWords = h => h <= 24 ? `${h} hour${h===1?'':'s'}` : h % 24 === 0 ? `${h/24} days` : `${h} hours`;
  function init() {
    const nav = byId('dashboardTabs'), overview = byId('dashboard-panel-overview');
    if (!nav || !overview || byId('rfBriefing')) return;
    document.documentElement.classList.add('rf-focus');
    const go = id => byId('dashboard-tab-' + id)?.click();

    const pages = [
      ['overview','Overview'], ['map','Map & coverage'], ['survey','Survey'], ['nodes','Nodes'],
      ['messages','Messages'], ['insights','Insights'], ['control','Node control'],
      ['filter','LNA test'], ['heardby','Heard by'], ['role','HQ role comparison'], ['whatif','What-if'],
      ['tropo','Tropo'], ['ask','Ask questions'], ['ingestors','MSP ingestors'],
      ['system','System & events'], ['utilities','Utilities']
    ];
    const read = key => {try{return localStorage.getItem(key);}catch{return null;}};
    const save = (key,value) => {try{localStorage.setItem(key,value);}catch{}};
    const storedPage=read('rf-current-page');
    let intendedPage=new URLSearchParams(location.hash.slice(1)).get('view') || storedPage || 'overview';
    if(intendedPage==='debug')intendedPage='utilities';
    let activePage=null, restoring=true;
    const sidebar=el('aside',null,'rf-sidebar');sidebar.id='rfSidebar';sidebar.setAttribute('aria-label','Dashboard navigation');
    const sideHead=el('div',null,'rf-sidebar-heading');sideHead.append(el('strong','Meshcrap'));
    const closeSide=el('button','×','rf-close-sidebar');closeSide.type='button';closeSide.setAttribute('aria-label','Close navigation');sideHead.append(closeSide);
    const sideNav=el('nav',null,'rf-sidebar-links');sideNav.setAttribute('aria-label','Main navigation');
    const sideFooter=el('p','RF Console','rf-sidebar-footer');sidebar.append(sideHead,sideNav,sideFooter);document.body.append(sidebar);
    const opener=el('button','☰','rf-open-sidebar');opener.type='button';opener.setAttribute('aria-label','Open navigation');opener.setAttribute('aria-controls','rfSidebar');
    document.querySelector('header')?.prepend(opener);
    const shade=el('div',null,'rf-sidebar-shade');shade.hidden=true;document.body.append(shade);
    const pageButtons=new Map(),pageRows=new Map();
    const arrange=el('button','Arrange menu','rf-arrange-menu');arrange.type='button';arrange.setAttribute('aria-pressed','false');sidebar.append(arrange);
    const reset=el('button','Reset order','rf-reset-menu');reset.type='button';reset.hidden=true;sidebar.append(reset);
    const reorderStatus=el('span','','rf-reorder-status');reorderStatus.setAttribute('role','status');reorderStatus.setAttribute('aria-live','polite');sidebar.append(reorderStatus);
    let arranging=false,drag=null;
    const menuOrder=()=>[...sideNav.children].map(row=>row.dataset.page);
    const saveOrder=()=>save('rf-menu-order',JSON.stringify(menuOrder()));
    const savedOrder=()=>{try{const value=JSON.parse(read('rf-menu-order'));return Array.isArray(value)?[...new Set(value.filter(id=>typeof id==='string'))]:[];}catch{return [];}};
    function updateMoveButtons(){
      const rows=[...sideNav.children];
      rows.forEach((row,i)=>{row.querySelector('[data-move=up]').disabled=i===0;row.querySelector('[data-move=down]').disabled=i===rows.length-1;});
    }
    function announceMove(row){reorderStatus.textContent=`${row.querySelector('.rf-nav-page').textContent} moved to position ${[...sideNav.children].indexOf(row)+1} of ${sideNav.children.length}.`;}
    function moveRow(row,delta){
      const rows=[...sideNav.children],i=rows.indexOf(row),target=rows[i+delta];if(!target)return;
      if(delta<0)target.before(row);else target.after(row);
      updateMoveButtons();saveOrder();announceMove(row);
    }
    function finishDrag(cancel=false){
      if(!drag)return;
      const current=drag;drag=null;
      current.row.classList.remove('rf-dragging');
      if(cancel)sideNav.append(...current.before.map(id=>pageRows.get(id)).filter(Boolean));else {saveOrder();announceMove(current.row);}
      try{sidebar.releasePointerCapture(current.pointerId);}catch{}
      updateMoveButtons();
    }
    arrange.addEventListener('click',()=>{
      finishDrag();arranging=!arranging;sidebar.classList.toggle('rf-arranging',arranging);
      document.documentElement.classList.toggle('rf-arranging',arranging);
      arrange.textContent=arranging?'Done arranging':'Arrange menu';arrange.setAttribute('aria-pressed',String(arranging));reset.hidden=!arranging;
      reorderStatus.textContent=arranging?'Drag the handles or use the arrow buttons to reorder. Changes are saved in this browser.':'';
      window.dispatchEvent(new Event('resize'));
    });
    reset.addEventListener('click',()=>{save('rf-menu-order','[]');buildLinks();reorderStatus.textContent='Default menu order restored.';});
    document.addEventListener('pointermove',e=>{
      if(!drag||e.pointerId!==drag.pointerId)return;
      e.preventDefault();
      const bounds=sidebar.getBoundingClientRect();
      if(e.clientY<bounds.top+50)sidebar.scrollTop-=12;else if(e.clientY>bounds.bottom-50)sidebar.scrollTop+=12;
      if(e.clientX<bounds.left||e.clientX>bounds.right)return;
      const other=[...sideNav.children].find(row=>{const r=row.getBoundingClientRect();return row!==drag.row&&e.clientY>=r.top&&e.clientY<=r.bottom;});
      if(other){const r=other.getBoundingClientRect();if(e.clientY<r.top+r.height/2)other.before(drag.row);else other.after(drag.row);}
    },{passive:false});
    document.addEventListener('pointerup',e=>{if(drag&&e.pointerId===drag.pointerId)finishDrag();});
    document.addEventListener('pointercancel',()=>finishDrag(true));
    let sidebarOpen=read('rf-sidebar-open')===null?!matchMedia('(max-width:700px)').matches:read('rf-sidebar-open')==='true';
    function setSidebar(open,persist=true){
      if(!open)finishDrag();
      sidebarOpen=open;sidebar.hidden=!open;opener.hidden=open;
      document.documentElement.classList.toggle('rf-sidebar-open',open);
      opener.setAttribute('aria-expanded',String(open));
      shade.hidden=!(open&&matchMedia('(max-width:700px)').matches);
      if(persist)save('rf-sidebar-open',String(open));
      requestAnimationFrame(()=>window.dispatchEvent(new Event('resize')));
    }
    closeSide.addEventListener('click',()=>{setSidebar(false);opener.focus();});
    opener.addEventListener('click',()=>{setSidebar(true);closeSide.focus();});
    shade.addEventListener('click',()=>setSidebar(false));
    matchMedia('(max-width:700px)').addEventListener('change',()=>setSidebar(sidebarOpen,false));
    function normalize(id,historyMode='push'){
      const target=byId('dashboard-panel-'+id);if(!target)return;
      document.querySelectorAll('.dashboard-panel').forEach(p=>{if(p.hidden!==(p!==target))p.hidden=p!==target;});
      nav.querySelectorAll('[role=tab]').forEach(t=>{
        const active=t.id==='dashboard-tab-'+id;
        if(t.getAttribute('aria-selected')!==String(active))t.setAttribute('aria-selected',String(active));
        t.tabIndex=active?0:-1;
      });
      pageButtons.forEach((b,key)=>{if(key===id)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
      const changed=activePage!==id;activePage=id;intendedPage=id;
      const title=byId('dashboard-tab-'+id)?.textContent.trim()||'Overview';sideFooter.textContent='Viewing '+title;
      save('rf-current-page',id);
      try{sessionStorage.setItem('console-active-tab',id);sessionStorage.setItem('mesh-dashboard-tab',id);}catch{}
      const hash='#view='+encodeURIComponent(id);
      if(location.hash!==hash&&historyMode!=='none')history[historyMode==='replace'?'replaceState':'pushState'](null,'',hash);
      if(changed)requestAnimationFrame(()=>{window.dispatchEvent(new Event('resize'));if(id==='overview')loadBriefing();});
    }
    function visit(id,historyMode='push'){
      if(id==='debug')id='utilities';
      const tab=byId('dashboard-tab-'+id);if(!tab)return false;
      tab.click();normalize(id,historyMode);return true;
    }
    function buildLinks(){
      const known=new Set(pages.map(p=>p[0]));
      const extras=[...nav.querySelectorAll('[role=tab]')].map(t=>[t.id.replace('dashboard-tab-',''),t.textContent.trim()]).filter(p=>!known.has(p[0]));
      for(const [id,label] of [...pages,...extras]){
        if(!byId('dashboard-tab-'+id)||pageButtons.has(id))continue;
        const row=el('div',null,'rf-nav-row');row.dataset.page=id;
        const button=el('button',label,'rf-nav-page');button.type='button';button.dataset.page=id;
        button.addEventListener('click',()=>{
          visit(id);
          if(matchMedia('(max-width:700px)').matches){setSidebar(false);opener.focus();}
        });
        const handle=el('button','⠿','rf-move-handle');handle.type='button';handle.setAttribute('aria-label','Drag to move '+label);handle.title='Drag to move; arrow keys also work';
        handle.addEventListener('pointerdown',e=>{
          if(!arranging||e.button!==0)return;e.preventDefault();
          drag={row,pointerId:e.pointerId,before:menuOrder()};row.classList.add('rf-dragging');handle.focus();
          sidebar.setPointerCapture(e.pointerId);
        });
        handle.addEventListener('keydown',e=>{if(e.key==='ArrowUp'||e.key==='ArrowDown'){e.preventDefault();e.stopPropagation();moveRow(row,e.key==='ArrowUp'?-1:1);}});
        const up=el('button','↑','rf-move-arrow');up.type='button';up.dataset.move='up';up.setAttribute('aria-label','Move '+label+' up');up.addEventListener('click',()=>moveRow(row,-1));
        const down=el('button','↓','rf-move-arrow');down.type='button';down.dataset.move='down';down.setAttribute('aria-label','Move '+label+' down');down.addEventListener('click',()=>moveRow(row,1));
        row.append(button,handle,up,down);pageRows.set(id,row);pageButtons.set(id,button);
      }
      const defaultIds=[...pages,...extras].map(([id])=>id);
      const ids=[...new Set([...savedOrder().filter(id=>defaultIds.includes(id)),...defaultIds])];
      const ordered=ids.map(id=>pageRows.get(id)).filter(Boolean);
      if(ordered.some((row,i)=>sideNav.children[i]!==row))sideNav.append(...ordered);
      updateMoveButtons();
      pageButtons.forEach((b,id)=>{if(id===activePage)b.setAttribute('aria-current','page');});
    }
    buildLinks();nav.hidden=true;nav.setAttribute('aria-hidden','true');
    // Let each legacy handler initialize its screen, then reconcile selection.
    nav.addEventListener('click',e=>{
      const tab=e.target.closest('[role=tab]');if(!tab)return;
      const id=tab.id.replace('dashboard-tab-','');
      queueMicrotask(()=>{if(!restoring||id===intendedPage)normalize(id,restoring?'replace':'push');});
    });
    let restoreQueued=false;
    function restore(){
      if(!restoring||restoreQueued)return;restoreQueued=true;
      requestAnimationFrame(()=>{restoreQueued=false;if(visit(intendedPage,'replace'))restoring=false;});
    }
    new MutationObserver(()=>{buildLinks();restore();}).observe(nav,{childList:true});
    setTimeout(restore,0);
    window.addEventListener('hashchange',()=>{
      const id=new URLSearchParams(location.hash.slice(1)).get('view');if(id&&id!==activePage)visit(id,'none');
    });
    // Some internal links select a panel without clicking its tab.
    const panelObserver=new MutationObserver(records=>{
      const opened=records.filter(r=>r.type==='attributes'&&!r.target.hidden).map(r=>r.target);
      const panel=opened.at(-1);if(panel&&!restoring){const id=panel.id.replace('dashboard-panel-','');if(id!==activePage)normalize(id);}
    });
    const observePanels=()=>document.querySelectorAll('.dashboard-panel').forEach(p=>panelObserver.observe(p,{attributes:true,attributeFilter:['hidden']}));
    observePanels();new MutationObserver(observePanels).observe(document.querySelector('main'),{childList:true});
    document.addEventListener('keydown',e=>{
      if(e.key==='Escape'&&drag){e.preventDefault();finishDrag(true);return;}
      if(e.key==='Escape'&&sidebarOpen&&sidebar.contains(document.activeElement)){setSidebar(false);opener.focus();return;}
      if(!sideNav.contains(e.target)||!['ArrowDown','ArrowUp','Home','End'].includes(e.key))return;
      const buttons=[...sideNav.querySelectorAll('.rf-nav-page')];const i=buttons.indexOf(document.activeElement);if(i<0)return;
      e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?buttons.length-1:(i+(e.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length;buttons[next].focus();
    });
    setSidebar(sidebarOpen,false);

    const appearance = document.querySelector('header .appearance-picker');
    if (appearance) {
      const settings = el('details', null, 'rf-appearance'); settings.append(el('summary', 'Appearance'));
      appearance.before(settings); settings.append(appearance);
    }
    const heading = overview.querySelector('.console-panel-heading');
    if (heading) {
      heading.querySelector('h2').textContent = 'Reception at Receiver';
      heading.querySelector('p').textContent = 'Current activity and changes in the selected window';
    }

    const briefing = el('section', null, 'rf-briefing'); briefing.id = 'rfBriefing';
    briefing.setAttribute('aria-label', 'RF reception summary');
    const metricGrid = el('div', null, 'rf-metrics');
    const metrics = [
      ['Packets heard', 'insights'], ['Originating nodes', 'nodes'],
      ['Known direct packets', 'insights'], ['Observed minutes', 'insights']
    ].map(([name,target]) => {
      const button = el('button', null, 'rf-metric'); button.type = 'button';
      const label = el('span', name, 'rf-metric-label'), value = el('strong', '—'), note = el('small', 'Loading…');
      button.append(label,value,note); button.addEventListener('click', () => go(target));
      metricGrid.append(button); return {button,label,value,note};
    });
    const trend = el('div', null, 'rf-trend');
    const trendTitle = el('strong', 'Reading recent reception…'); const trendText = el('p', '');
    const insights = el('button', 'Explore insights →', 'rf-insight-link'); insights.type='button'; insights.addEventListener('click', () => go('insights'));
    const trendCopy = el('div'); trendCopy.append(trendTitle, trendText); trend.append(trendCopy, insights);
    const stamp = el('p', 'Updates every 2 minutes while Overview is visible.', 'rf-briefing-stamp');
    stamp.setAttribute('role','status');
    briefing.append(metricGrid,trend,stamp); heading ? heading.after(briefing) : overview.prepend(briefing);

    // Keep secondary information and all existing controls, lower on Overview.
    const liveGrid = overview.querySelector('.live-grid');
    const recentCard = byId('recentHeard')?.closest('.card');
    const systemCard = byId('systemDetail')?.closest('.card');
    if (recentCard) { briefing.after(recentCard); recentCard.classList.add('rf-recent-card'); }
    const secondary = el('div', null, 'rf-secondary-sections'); overview.append(secondary);
    function disclosure(label, contents) {
      const items = contents.filter(Boolean); if (!items.length) return;
      const details = el('details', null, 'rf-secondary-details'); details.append(el('summary',label));
      const body = el('div', null, 'rf-secondary-body'); body.append(...items); details.append(body); secondary.append(details);
    }
    disclosure('Receiver & station', [systemCard, byId('hqWeather')]);
    const records = byId('nocRecords')?.closest('.card');
    const insightsPanel=byId('dashboard-panel-insights');
    if(records&&insightsPanel){records.id='insight-records';insightsPanel.querySelector('#insight-mesh')?.after(records);const link=el('a','Records & achievements');link.href='#insight-records';insightsPanel.querySelector('.insight-jumps')?.append(link);}
    const storedStats = document.querySelector('main > .topstats');
    if (storedStats) {
      const history = el('section', null, 'rf-stored-history');
      history.setAttribute('aria-labelledby', 'rfStoredHistoryTitle');
      const title = el('h2', 'Stored History'); title.id = 'rfStoredHistoryTitle';
      const description = el('p', 'Saved collector records and known nodes, separate from the reception window above.');
      history.append(title, description, storedStats);
      briefing.after(history);
    }
    RFRefresh.every('insights',()=>loadNoc(),30000);
    if (liveGrid && !liveGrid.children.length) liveGrid.remove();

    const recentBox=byId('recentHeard');
    recentBox.classList.add('rf-mini-nodes');
    const toolbar=el('div',null,'rf-recent-toolbar');
    const searchLabel=el('label','Find node '),search=el('input');search.type='search';search.placeholder='Name, ID, hardware or role';search.setAttribute('aria-label','Find recently heard node');searchLabel.append(search);
    const limitLabel=el('label','Rows '),limit=el('select');limit.setAttribute('aria-label','Recently heard rows');
    for(const n of [8,20,50,0]){const option=el('option',n?String(n):'All');option.value=String(n);limit.append(option);}
    limit.value=['8','20','50','0'].includes(read('rf-recent-limit'))?read('rf-recent-limit'):'8';limitLabel.append(limit);
    const allNodes=el('button','Open Nodes →');allNodes.type='button';allNodes.addEventListener('click',()=>go('nodes'));
    toolbar.append(searchLabel,limitLabel,allNodes);
    const recentNote=el('p','Loading recent nodes…','rf-recent-note');recentNote.setAttribute('role','status');
    const wrap=el('div',null,'rf-recent-table-wrap');wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','Sortable recently heard nodes');
    const table=el('table',null,'rf-recent-table'),caption=el('caption','Recently heard nodes');caption.className='rf-sr-only';table.append(caption);
    const thead=el('thead'),headrow=el('tr'),tbody=el('tbody');thead.append(headrow);table.append(thead,tbody);wrap.append(table);
    const help=el('p','Sort any column by its heading. Signal describes the last radio hop; it is not an end-to-end reading. Power is the latest report found in the recent packet sample.','rf-recent-help');
    recentBox.replaceChildren(toolbar,recentNote,wrap,help);
    const numeric=value=>typeof value==='number'&&Number.isFinite(value)?value:null;
    const timestamp=value=>Number.isFinite(Date.parse(value))?Date.parse(value):null;
    const packetLabel=p=>({TELEMETRY_APP:'Telemetry',POSITION_APP:'Position',NODEINFO_APP:'Node info',TEXT_MESSAGE_APP:'Message',TRACEROUTE_APP:'Traceroute',ROUTING_APP:'Routing',NEIGHBORINFO_APP:'Neighbors'}[p]||p||'Update');
    const columns=[
      ['name','Node','asc'],['heard','Last heard','desc'],['snr','SNR (dB)','desc'],['rssi','RSSI (dBm)','desc'],
      ['hops','Hops','asc'],['updates','Updates','desc'],['direct','Direct %','desc'],['battery','Battery','desc'],
      ['voltage','Volts','desc'],['hardware','Hardware','asc'],['role','Role','asc'],['types','Packet types','asc']
    ];
    let sortKey=read('rf-recent-sort')||'heard',sortDir=read('rf-recent-direction')||'desc';
    if(!columns.some(c=>c[0]===sortKey))sortKey='heard';if(!['asc','desc'].includes(sortDir))sortDir='desc';
    let recentData=null,rows=[];
    const headers=new Map();
    for(const [key,label,initial] of columns){
      const th=el('th');th.scope='col';const button=el('button',label);button.type='button';button.dataset.sort=key;
      button.addEventListener('click',()=>{sortDir=sortKey===key?(sortDir==='asc'?'desc':'asc'):initial;sortKey=key;save('rf-recent-sort',sortKey);save('rf-recent-direction',sortDir);renderRecentTable();});
      th.append(button);headrow.append(th);headers.set(key,{th,button,label});
    }
    function renderRecentTable(){
      const query=search.value.trim().toLocaleLowerCase();
      const filtered=rows.filter(row=>!query||[row.name,row.id,row.short,row.hardware,row.role].some(v=>String(v||'').toLocaleLowerCase().includes(query)));
      const collator=new Intl.Collator(undefined,{numeric:true,sensitivity:'base'});
      filtered.sort((a,b)=>{
        const x=a[sortKey],y=b[sortKey],missing=v=>v==null||v==='';
        if(missing(x)||missing(y))return missing(x)===missing(y)?collator.compare(a.id,b.id):missing(x)?1:-1;
        const cmp=typeof x==='number'&&typeof y==='number'?x-y:collator.compare(String(x),String(y));
        return (sortDir==='asc'?cmp:-cmp)||(b.heard||0)-(a.heard||0)||collator.compare(a.id,b.id);
      });
      const shown=Number(limit.value)?filtered.slice(0,Number(limit.value)):filtered;
      headers.forEach(({th,button,label},key)=>{th.setAttribute('aria-sort',key===sortKey?(sortDir==='asc'?'ascending':'descending'):'none');button.textContent=label+(key===sortKey?(sortDir==='asc'?' ↑':' ↓'):' ↕');});
      const activeNode=tbody.contains(document.activeElement)?document.activeElement.dataset.node:null;
      const fragment=document.createDocumentFragment();
      for(const row of shown){
        const tr=el('tr');tr.dataset.node=row.id;
        for(const [key,label] of columns){
          const td=el('td');td.dataset.column=key;td.dataset.label=label;
          if(key==='name'){
            const button=el('button',row.name,'rf-recent-node');button.type='button';button.dataset.node=row.id;button.addEventListener('click',()=>window.openTelemetry(row.id));
            td.append(button,el('small',[row.short,row.id].filter(Boolean).join(' · ')));
          }else{
            let text=row[key]==null||row[key]===''?'—':String(row[key]);
            if(key==='heard'){text=row.heard==null?'—':age(new Date(row.heard).toISOString())+' ago';if(row.heard!=null)td.title=new Date(row.heard).toLocaleString();}
            if(key==='snr'&&row.snr!=null)text=row.snr.toFixed(1);
            if(key==='hops'&&row.hops===0)text='Direct';
            if(key==='direct'&&row.direct!=null)text=row.direct.toFixed(1)+'%';
            if(key==='battery'&&row.battery!=null)text=row.battery===101?'External':row.battery+'%';
            if(key==='voltage'&&row.voltage!=null)text=row.voltage.toFixed(2);
            td.textContent=text;
            if(['battery','voltage'].includes(key))td.title=row.powerTime?'Reported '+new Date(row.powerTime).toLocaleString():'No power report in the recent packet sample';
            if(['snr','rssi'].includes(key))td.title='Latest received packet: final radio hop, including relayed packets';
            if(key==='direct')td.title='Direct updates divided by all updates in the selected window, including unknown hops';
          }
          tr.append(td);
        }
        fragment.append(tr);
      }
      if(!shown.length){const tr=el('tr'),td=el('td',recentData?'No matching recently heard nodes.':'Loading recent nodes…');td.colSpan=columns.length;tr.append(td);fragment.append(tr);}
      tbody.replaceChildren(fragment);
      if(activeNode)[...tbody.querySelectorAll('button[data-node]')].find(b=>b.dataset.node===activeNode)?.focus({preventScroll:true});
      recentNote.textContent=recentData?`Showing ${shown.length} of ${filtered.length}${query?' matching':''} nodes · ${rows.length} nodes in the latest ${recentData.recent.length} remote updates · activity totals cover ${windowLabel(Number(recentData.hours))}. Missing values sort last.`:'Loading recent nodes…';
    }
    window.renderRecentNodePanel=function(data){
      if(Number(data.hours)!==selectedHours())return;
      recentData=data;const groups=new Map();
      for(const p of [...(data.recent||[])].sort((a,b)=>(timestamp(b.collector_time)||0)-(timestamp(a.collector_time)||0))){
        const id=p.node_id||p.node;if(!id)continue;
        if(!groups.has(id))groups.set(id,{p,types:new Set(),power:null});const g=groups.get(id);g.types.add(packetLabel(p.portnum));
        if(!g.power&&(numeric(p.battery_level)!=null||numeric(p.voltage)!=null))g.power=p;
      }
      rows=[...groups].map(([id,{p,types,power}])=>({id,name:p.node||id,short:p.short_name||'',heard:timestamp(p.collector_time),snr:numeric(p.rx_snr),rssi:numeric(p.rx_rssi),hops:numeric(p.hops_used),updates:numeric(p.window_packets),direct:numeric(p.window_direct_pct),battery:power&&numeric(power.battery_level)!=null&&power.battery_level>=0&&power.battery_level<=101?power.battery_level:null,voltage:power?numeric(power.voltage):null,powerTime:power?.collector_time,hardware:p.hw_model||'',role:p.role||'',types:[...types].sort().join(', ')}));
      renderRecentTable();
    };
    search.addEventListener('input',renderRecentTable);limit.addEventListener('change',()=>{save('rf-recent-limit',limit.value);renderRecentTable();});
    window.addEventListener('dashboard:time-window',()=>{recentData=null;rows=[];renderRecentTable();});
    renderRecentTable();

    let busy = false, pending = false, lastHours = null, loadedAt = 0;
    async function loadBriefing(force = false) {
      if (overview.hidden || document.hidden) return;
      const h = selectedHours();
      if (busy) { if (h !== lastHours) pending = true; return; }
      if (!force && h === lastHours && Date.now()-loadedAt < 120000) return;
      busy=true; pending=false;
      if (h !== lastHours) {
        metrics.forEach(m => {m.value.textContent='—';m.note.textContent='Loading…';m.button.removeAttribute('aria-label');});
        trendTitle.textContent='Reading recent reception…';trendText.textContent='';
      }
      briefing.setAttribute('aria-busy','true'); stamp.textContent='Refreshing reception summary…';
      try {
        const r=await fetch(`/api/insights?hours=${h}`, {cache:'no-store',signal:AbortSignal.timeout(25000)});
        if (!r.ok) throw new Error('Briefing unavailable');
        const d=await r.json();
        await RFRefresh.ready();
        if (h !== selectedHours()) {pending=true;return;}
        const a=d.current,b=d.previous;
        metrics[0].value.textContent=count(a.packets); metrics[0].note.textContent=`${count(b.packets)} in previous ${windowLabel(h)}`;
        metrics[1].value.textContent=count(a.nodes); metrics[1].note.textContent=`${count(b.nodes)} in previous ${windowLabel(h)}`;
        metrics[2].value.textContent=count(a.direct); metrics[2].note.textContent=`${count(a.unknown_hops)} packets have unknown hops`;
        metrics[3].value.textContent=Number.isFinite(a.observed_pct)?`${a.observed_pct.toLocaleString(undefined,{maximumFractionDigits:1})}%`:'—';
        metrics[3].note.textContent='Based on HQ self updates';
        metrics.forEach(m => m.button.setAttribute('aria-label', `${m.label.textContent}: ${m.value.textContent}. ${m.note.textContent}. Open details.`));
        const comparable=a.observed_pct>=90&&b.observed_pct>=90;
        trend.classList.toggle('rf-trend-caution', !comparable);
        if (!comparable) {
          trendTitle.textContent='Collection gaps limit the comparison';
          trendText.textContent=`HQ self updates cover ${count(a.observed_pct)}% of this window and ${count(b.observed_pct)}% of the previous one. A lower count may reflect gaps in collection.`;
        } else if (b.packets>=10) {
          const pct=100*(a.packets-b.packets)/b.packets;
          trendTitle.textContent=`${Math.round(Math.abs(pct))}% ${pct>=0?'more':'fewer'} packets than the previous ${windowWords(h)}`;
          trendText.textContent=`${count(d.newly_heard_count)} nodes heard only in this window; ${count(d.quiet_count)} previously active nodes not heard here. Reception at HQ does not measure total mesh traffic.`;
        } else {
          trendTitle.textContent='More history is needed for a meaningful trend';
          trendText.textContent=`The previous window has ${count(b.packets)} qualifying packets. Current counts describe reception at HQ.`;
        }
        lastHours=h;loadedAt=Date.now();
        stamp.textContent=`Last ${windowLabel(h)} · updated ${new Date(loadedAt).toLocaleTimeString([], {hour:'numeric',minute:'2-digit'})} · ordinary remote packets; self-traffic and diagnostic traffic excluded`;
      } catch(error) {
        stamp.textContent=lastHours===h?'Summary could not refresh. Previous readings remain visible; retrying automatically.':'Reception summary unavailable. Retrying automatically; live node details remain below.';
        if (lastHours!==h) {metrics.forEach(m=>m.note.textContent='Unavailable');trendTitle.textContent='Waiting for reception summary';}
      } finally {
        busy=false;briefing.setAttribute('aria-busy','false');
        if(pending)loadBriefing(true);
      }
    }
    window.addEventListener('dashboard:time-window', () => {save('rf-time-window',String(selectedHours()));loadBriefing(true);});
    
    
    RFRefresh.every('overview',()=>loadBriefing(true),120000);
    const restoreHours=()=>{
      const savedHours=Number(read('rf-time-window'));
      if([...byId('dashboardTimeWindow').options].some(o=>Number(o.value)===savedHours)&&savedHours!==selectedHours()){
        byId('dashboardTimeWindow').value=String(savedHours);window.setHours(savedHours);
      }else loadBriefing();
    };
    // LNA controls subscribe early but initialize on load; restore afterwards.
    if(document.readyState==='complete')restoreHours();else window.addEventListener('load',restoreHours,{once:true});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
