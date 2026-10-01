(() => {
 const card=document.getElementById('hqWeather');if(!card)return;
 const place=()=>{const panel=document.getElementById('dashboard-panel-overview');if(panel){const heading=panel.querySelector('.console-panel-heading');if(heading)heading.after(card);else panel.prepend(card);}};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',place);else place();
 const status=card.querySelector('[data-weather-status]'),time=card.querySelector('time');
 const text=(name,value)=>{card.querySelector('[data-weather-'+name+']').textContent=value;};
 async function update(){
  if(document.hidden)return;
  try{
   const r=await fetch('/api/hq-weather',{cache:'no-store',signal:AbortSignal.timeout(8000)});if(!r.ok)throw Error();
   const w=await r.json();
   if(!w.available){status.textContent='Waiting for the first station reading';return;}
   const v=w.values,fmt=(x,d=1)=>x==null?'—':Number(x).toFixed(d);
   text('temp',v.temperature==null?'—':fmt(v.temperature*9/5+32)+' °F');
   text('temp-c',fmt(v.temperature)+' °C');text('humidity',fmt(v.relativeHumidity,0)+' %');
   text('pressure',v.barometricPressure==null?'—':fmt(v.barometricPressure/33.8638866667,2)+' inHg');
   text('pressure-hpa',fmt(v.barometricPressure,1)+' hPa');
   const age=Math.floor(w.age_seconds/60);
   time.dateTime=w.observed_at;time.title=new Date(w.observed_at).toLocaleString();time.textContent=age<1?'Observed just now':'Observed '+age+' min ago';
   status.textContent=w.stale?'Stale reading · awaiting a fresh station update':w.error?'Last reading · weather service temporarily unavailable':'Fresh station reading';
   card.dataset.stale=String(w.stale);
  }catch(e){status.textContent='Weather feed unavailable · displayed values may be out of date';card.dataset.stale='true';}
 }
 MeshcrapPoll.watch('hqWeather',update,60000);
})();
