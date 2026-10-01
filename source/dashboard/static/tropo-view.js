/* Official provider embed. No protected API, scraping, key or RF data upload. */
(() => {
 'use strict';
 const nav=document.getElementById('dashboardTabs'),main=document.querySelector('main');if(!nav||!main||document.getElementById('dashboard-tab-tropo'))return;
 const el=(tag,text)=>{const e=document.createElement(tag);if(text)e.textContent=text;return e;};
 const tab=el('button','Tropo');tab.type='button';tab.id='dashboard-tab-tropo';tab.setAttribute('role','tab');tab.setAttribute('aria-controls','dashboard-panel-tropo');tab.setAttribute('aria-selected','false');tab.tabIndex=-1;
 const panel=el('section');panel.className='dashboard-panel';panel.id='dashboard-panel-tropo';panel.hidden=true;panel.tabIndex=0;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tab.id);
 panel.append(el('h2','Regional tropo forecast'),el('p','Explore forecast propagation potential, then compare the valid time with your RF observations. This is external weather-model context, not measured 915 MHz coverage or proof of ducting.'));
 const source=el('a','Open Tropocast map full screen');source.target='_blank';source.rel='noopener noreferrer';source.href='https://tropocast.eu/map';panel.append(source);
 const status=el('p','Map loads when this tab is opened.');status.setAttribute('role','status');panel.append(status);
 const wrap=el('div');panel.append(wrap);
 panel.append(el('p','Source: Tropocast / Artur SQ3A, using the global ECCC GDPS model. Forecast date, timeline and propagation scale are supplied by the provider inside the map. Blank or unavailable layers are not evidence of normal conditions. Animation starts only when you choose Play.'));
 panel.append(el('p','The map connects your browser to Tropocast and its map services. No local nodes, messages or radio measurements are sent. Closing this tab unloads the external map. API-based measurements and automated correlations are not enabled.'));
 main.append(panel);(document.getElementById('dashboard-tab-whatif')||nav.lastElementChild).after(tab);
 let frame=null,generation=0;
 async function open(){
  main.querySelectorAll('.dashboard-panel').forEach(p=>p.hidden=p!==panel);nav.querySelectorAll('[role=tab]').forEach(b=>{b.setAttribute('aria-selected',String(b===tab));b.tabIndex=b===tab?0:-1;});
  if(frame)return;const current=++generation;
  const url=new URL('https://tropocast.eu/map');url.search=new URLSearchParams({lang:'en',model:'full',source:'gdps',renderer:'standard',tz:'browser',opacity:'70',date_position:'top',timeline:'1',legend:'1',data_border:'1',autoplay:'0',speed:'1300',location:'default',zoom:'5',embed:'1',embed_view:'simple',locked:'0','auto-hide':'0'}).toString();
  // Optional deployment-local, coarse regional centre. Not part of public source.
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),5000);
  try{const response=await fetch('/static/tropo-map-config.json',{cache:'no-store',signal:controller.signal});if(response.ok){const c=await response.json();if(Number.isFinite(c.latitude)&&Math.abs(c.latitude)<=85&&Number.isFinite(c.longitude)&&Math.abs(c.longitude)<=180){url.searchParams.set('location','fixed');url.searchParams.set('lat',String(c.latitude));url.searchParams.set('lon',String(c.longitude));}}}catch{}finally{clearTimeout(timeout);}
  if(current!==generation||panel.hidden)return;
  source.href=url.toString();frame=el('iframe');frame.title='Tropocast regional propagation forecast and time controls';frame.referrerPolicy='no-referrer';frame.setAttribute('sandbox','allow-scripts allow-same-origin');frame.style.cssText='display:block;width:100%;height:70vh;min-height:440px;border:0;border-radius:12px';frame.src=url.toString();wrap.append(frame);
  status.textContent='Use the map’s forecast time and color scale. If the provider is unavailable here, use the full-screen source link above.';
 }
 tab.addEventListener('click',open);
 nav.addEventListener('click',event=>{const other=event.target.closest('[role=tab]');if(other&&other!==tab){generation++;frame?.remove();frame=null;panel.hidden=true;tab.setAttribute('aria-selected','false');tab.tabIndex=-1;}});
 try{if(sessionStorage.getItem('console-active-tab')==='tropo')tab.click();}catch{}
})();
