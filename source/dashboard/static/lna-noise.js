(() => {
 let chart,busy=false,box,status,summary,canvas,title,pending=false;
 window.addEventListener('dashboard:time-window',()=>{pending=true;refresh();});
 const el=(tag,text)=>{const e=document.createElement(tag);if(text)e.textContent=text;return e;};
 const fmt=v=>v==null?'—':Number(v).toFixed(1);
 async function refresh(){
  if(busy||document.hidden||!box?.getClientRects().length)return;busy=true;pending=false;
  const hours=window.getDashboardHours?.()||24;
  try{
   const r=await fetch(`/api/lna-noise?hours=${hours}`,{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error('Noise-floor data unavailable');const d=await r.json();
   if(hours!==(window.getDashboardHours?.()||24))return;
   const range=hours<24?`${hours} hour${hours===1?'':'s'}`:`${hours/24} day${hours===24?'':'s'}`;
   title.textContent=`Receiver receiver noise floor · last ${range}`;
   canvas.setAttribute('aria-label',`Receiver noise floor over the last ${range} with recorded LNA switch markers`);
   const p=d.latest;
   status.textContent=p?`Latest: ${fmt(p.noise_dbm)} dBm · ${new Date(p.time).toLocaleString()}${d.stale?' · STALE':''}${p.warmup?' · radio startup':''}. Sampling: every 15 minutes; recent median spacing: ${fmt(d.median_interval_seconds/60)} minutes.`:'Waiting for Receiver noise-floor telemetry.';
   const m=d.matched;
   summary.textContent=m.paired_hours?`${m.paired_hours} matched hour pairs · OFF ${fmt(m.off_dbm)} dBm → ON ${fmt(m.on_dbm)} dBm · change ${fmt(m.delta_db)} dB (ON minus OFF).`:'Matched comparison is waiting for complete, healthy ON/OFF hours at the same local time.';
   const points=[];
   for(const p of d.points){
    const prev=points.at(-1);if(prev&&Date.parse(p.time)-Date.parse(prev.time)>1200000)points.push({time:new Date(Date.parse(prev.time)+1).toISOString(),noise_dbm:null,warmup:false});points.push(p);
   }
   const labels=points.map(p=>new Date(p.time).toLocaleString([],hours>24?{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}:{hour:'2-digit',minute:'2-digit'}));
   const datasets=[{label:'Noise floor (dBm)',data:points.map(p=>p.warmup?null:p.noise_dbm),borderColor:'#68c9ff',backgroundColor:'#68c9ff',pointRadius:1,borderWidth:2,spanGaps:false},{label:'Startup · excluded',data:points.map(p=>p.warmup?p.noise_dbm:null),borderColor:'#f2c94c',backgroundColor:'#f2c94c',showLine:false,pointRadius:3}];
   if(chart){chart.data={labels,datasets};chart.options.plugins.lnaSwitches.timestamps=points.map(p=>p.time);chart.options.plugins.tooltip.callbacks.title=items=>points[items[0]?.dataIndex]?new Date(points[items[0].dataIndex].time).toLocaleString():'';chart.update('none');}
   else chart=new Chart(canvas,{type:'line',data:{labels,datasets},options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{labels:{color:'#b8c9bf'}},lnaSwitches:{timestamps:points.map(p=>p.time)},tooltip:{callbacks:{title:items=>points[items[0]?.dataIndex]?new Date(points[items[0].dataIndex].time).toLocaleString():''}}},scales:{x:{ticks:{maxTicksLimit:8,color:'#b8c9bf'}},y:{ticks:{color:'#b8c9bf'},title:{display:true,color:'#b8c9bf',text:'Receiver noise floor (dBm)'}}}}});
  }catch(e){status.textContent=e.message+'; displayed readings may be stale.';}finally{busy=false;if(pending)refresh();}
 }
 window.addEventListener('load',()=>{
  const heading=[...document.querySelectorAll('h2')].find(h=>h.textContent.trim()==='LNA Enabled / Disabled Test');if(!heading)return;
  box=el('section');box.className='lna-controls';box.id='lnaNoisePanel';heading.after(box);
  title=el('h3','Receiver receiver noise floor');box.append(title);
  status=el('p','Loading noise-floor readings…');status.setAttribute('role','status');summary=el('p');box.append(status,summary);
  box.append(el('p','More-negative values mean a lower receiver noise estimate. An LNA can raise both signal and noise: judge this alongside same-node SNR, reception rate and bad-packet share. This is a smoothed radio estimate, not a calibrated measurement of antenna noise or LNA noise figure.'));
  const wrap=el('div');wrap.style.cssText='height:280px;min-width:0';canvas=el('canvas');canvas.setAttribute('role','img');canvas.setAttribute('aria-label','Receiver noise floor over the last 24 hours with recorded LNA switch markers');wrap.append(canvas);box.append(wrap);
  box.append(el('p','Comparison uses equal-weight hourly medians across the existing matched healthy ON/OFF hours. Each hour needs at least 3 readings spanning 30 minutes. The first 15 minutes after radio startup are excluded; transition hours are excluded. The existing 15-minute sampling interval is unchanged.'));
  refresh();setInterval(refresh,60000);document.addEventListener('visibilitychange',refresh);document.getElementById('dashboardTabs')?.addEventListener('click',()=>setTimeout(refresh,50));
 });
})();
