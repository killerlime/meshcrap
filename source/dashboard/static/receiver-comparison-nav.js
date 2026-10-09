/* Optional independent receiver view; loading this panel never starts a collector. */
(() => {
 'use strict';
 async function init(){
  const nav=document.getElementById('dashboardTabs'),main=document.querySelector('main');
  if(!nav||!main)return;
  let settings;
  try{const response=await fetch('/api/receiver-comparison/integration',{cache:'no-store',signal:AbortSignal.timeout(5000)});if(!response.ok)return;settings=await response.json();}catch{return;}
  if(settings.enabled!==true)return;
  const tab=document.createElement('button');tab.type='button';tab.id='dashboard-tab-comparison';tab.textContent='Receiver comparison';tab.setAttribute('role','tab');tab.setAttribute('aria-controls','dashboard-panel-comparison');tab.setAttribute('aria-selected','false');tab.tabIndex=-1;
  const panel=document.createElement('section');panel.className='dashboard-panel';panel.id='dashboard-panel-comparison';panel.hidden=true;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tab.id);
  const head=document.createElement('div');head.className='console-panel-heading';const title=document.createElement('h2');title.textContent='Receiver comparison';head.append(title);panel.append(head);
  let frame;
  tab.addEventListener('click',()=>{
   main.querySelectorAll('.dashboard-panel').forEach(p=>p.hidden=p!==panel);
   nav.querySelectorAll('[role=tab]').forEach(t=>{const active=t===tab;t.setAttribute('aria-selected',String(active));t.tabIndex=active?0:-1;});
   document.querySelector('main>.controls')?.setAttribute('hidden','');
   if(!frame){frame=document.createElement('iframe');frame.title='Primary and secondary receiver comparison';frame.loading='lazy';frame.src='/receiver-comparison?embedded=1';frame.style.cssText='width:100%;height:calc(100vh - 200px);min-height:600px;border:0;border-radius:12px';panel.append(frame);}
  });
  nav.addEventListener('click',e=>{if(e.target.closest('[role=tab]')!==tab){panel.hidden=true;tab.setAttribute('aria-selected','false');tab.tabIndex=-1;}});
  nav.append(tab);main.append(panel);
  if(location.hash==='#view=comparison')tab.click();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
