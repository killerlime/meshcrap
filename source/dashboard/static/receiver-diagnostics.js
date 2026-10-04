(() => {
  function init() {
    const rf=document.getElementById('rfHealthHourlySummary');
    const system=document.getElementById('systemDetail');
    const nodes=document.getElementById('nodeSummary');
    if(!rf||!system||!nodes)return;
    const section=document.createElement('section');section.className='card';section.id='receiverDiagnostics';
    section.innerHTML='<h2>Receiver log insights</h2><p class="muted">Last 48 hours of retained receiver logs. These counts explain receiver behavior; they are not a packet-loss percentage or an LNA verdict.</p><button type="button" class="receiver-refresh">Refresh diagnostics</button> <button type="button" class="receiver-open-logs">View receiver logs</button><p class="muted receiver-status" role="status">Not loaded.</p><div class="noc-grid receiver-counts"></div><details><summary>Hourly log counts</summary><div style="overflow:auto;max-height:320px"><table><thead><tr><th>Hour</th><th>CRC failures</th><th>Decode errors</th><th>Node evictions</th></tr></thead><tbody></tbody></table></div></details>';
    const style=document.createElement('style');style.textContent='#receiverDiagnostics .muted,#receiverConnectionContext,#receiverCapacityContext{text-transform:none;letter-spacing:normal;font-size:13px;line-height:1.5}';section.prepend(style);
    rf.closest('.card').after(section);
    const sys=document.createElement('p');sys.className='muted';sys.id='receiverConnectionContext';system.after(sys);
    const node=document.createElement('p');node.className='muted';node.id='receiverCapacityContext';nodes.after(node);
    const fmt=n=>n==null?'Unavailable':Number(n).toLocaleString();
    const date=s=>s?new Date(s).toLocaleString():'Unavailable';
    let busy=false,last=0;
    function card(title,count,explanation){const box=document.createElement('div');box.className='noc-record';for(const [tag,cls,text] of [['div','muted',title],['div','value',fmt(count)],['p','muted',explanation]]){const e=document.createElement(tag);e.className=cls;e.textContent=text;box.append(e);}return box;}
    async function load(){
      if(busy)return;busy=true;section.querySelector('.receiver-refresh').disabled=true;
      const status=section.querySelector('.receiver-status');status.textContent='Reading saved diagnostics…';
      try{
        const r=await fetch('/api/receiver-diagnostics',{cache:'no-store',signal:AbortSignal.timeout(25000)});if(!r.ok)throw Error('Diagnostics unavailable.');const d=await r.json();last=Date.now();
        const c=d.connection;
        sys.textContent=c?`Connection history · ${fmt(c.errors_48h)} failed attempts in 48h (${fmt(c.no_route_48h)} network-unreachable). Last recorded ${c.last_event?.type==='CONNECTED'?'connection':'failure'}: ${date(c.last_event?.time)}. This is saved history; use live system status above for current health.`:'Connection history unavailable.';
        const radio=d.radio;
        status.textContent=radio?`${d.stale?'STALE · ':''}Captured ${date(radio.generated)} · Earliest retained entry ${date(radio.first_record)}${radio.truncated?' · Scan limit reached; counts are partial':''}. ${d.radio_error||'Cached for up to five minutes. Logs may cover less than the requested 48h.'}`:(d.radio_error||'Receiver logs unavailable; counts are unknown.');
        const counts=radio?.counts||{};
        const box=section.querySelector('.receiver-counts');box.replaceChildren(
          card('CRC failures',counts.crc_errors,'Received packets failed their checksum. Weak reception, collisions and interference are possibilities; logs do not establish the cause.'),
          card('Decode errors',counts.decode_errors,'Payloads could not be interpreted. Channel mismatches or hash collisions are possible; this alone does not prove an app defect.'),
          card('Node evictions',counts.node_evictions,'The receiver replaced older entries in its own node list. The dashboard’s saved reception history is separate.'),
          card('Client disconnects',counts.client_disconnects,'Recorded API disconnect events, not a count of lost RF packets. Configuration requests may also occur during normal setup.')
        );
        node.textContent=radio?`${d.stale?'Stale receiver snapshot · ':''}Receiver node-list capacity${radio.capacity_at_last_eviction?' at last eviction: '+fmt(radio.capacity_at_last_eviction):' not observed in retained logs'} · ${fmt(counts.node_evictions)} eviction events in the scanned 48h window. A node disappearing from the receiver’s list does not mean it went offline or its saved history was deleted.`:'Receiver node-list capacity diagnostics unavailable; no capacity is assumed.';
        const body=section.querySelector('tbody');body.replaceChildren();for(const h of (radio?.hourly||[]).slice().reverse()){const tr=document.createElement('tr');for(const v of [date(h.hour),fmt(h.crc_errors||0),fmt(h.decode_errors||0),fmt(h.node_evictions||0)]){const td=document.createElement('td');td.textContent=v;tr.append(td);}body.append(tr);}
      }catch(e){status.textContent='Diagnostics unavailable. Previously displayed readings are stale.';sys.textContent='Connection history unavailable. Previously loaded diagnostics may be stale.';node.textContent='Receiver capacity diagnostics unavailable; refresh to verify.';}
      finally{busy=false;section.querySelector('.receiver-refresh').disabled=false;}
    }
    section.querySelector('.receiver-refresh').addEventListener('click',load);
    section.querySelector('.receiver-open-logs').addEventListener('click',()=>{const form=document.getElementById('debugLogForm');if(form)form.elements.service.value='receiver';window.openRFDebugLogs?.();form?.requestSubmit();});
    const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)&&Date.now()-last>300000)load();});[section,sys,node].forEach(e=>observer.observe(e));
  }
  if(document.readyState!=='complete')window.addEventListener('load',init);else init();
})();
