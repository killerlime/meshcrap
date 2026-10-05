/* Explicit scheduling for data refreshes. Never schedules radio operations. */
(() => {
 'use strict';
 if(window.RFRefresh)return;
 const jobs=[],groups=new Map();let touched=0,pressed=false,manualRuns=0;
 const read=k=>{try{return JSON.parse(localStorage.getItem('rf-refresh:'+k))||{};}catch{return {};}};
 const save=g=>{try{localStorage.setItem('rf-refresh:'+g.id,JSON.stringify({paused:g.paused}));}catch{}};
 const node=(tag,text)=>{const n=document.createElement(tag);if(text)n.textContent=text;return n;};
 const labels={overview:'Overview',nodes:'Nodes',map:'Map & coverage',system:'System',filter:'LNA analysis',insights:'Insights',messages:'Messages',control:'Operation status',secondary:'Secondary radio operation status',health:'Collection health',weather:'Weather',mobile:'Receiver access',lcd:'LCD status',feed:'Feed status'};
 function visible(id){
  if(document.hidden||!navigator.onLine)return false;
  if(window.frameElement&&!window.frameElement.getClientRects().length)return false;
  const panel=document.getElementById('dashboard-panel-'+id);
  if(panel)return !panel.hidden&&!!panel.getClientRects().length;
  const g=groups.get(id),host=g?.host&&document.querySelector(g.host);
  return !g?.host||!!host?.getClientRects().length;
 }
 function interacting(){
  if(pressed||Date.now()-touched<2500)return true;
  const active=document.activeElement;
  if(active?.matches('input:not([type=checkbox]):not([type=radio]):not([type=button]):not([type=submit]):not([type=range]),textarea,[contenteditable="true"]')&&!active.closest('.rf-refresh-controls'))return true;
  if(document.querySelector('dialog[open]'))return true;
  return !!window.getSelection()?.toString();
 }
 function touch(e){if(!e.target?.closest?.('.rf-refresh-controls'))touched=Date.now();}
 for(const event of ['keydown','input','wheel','touchmove','scroll'])document.addEventListener(event,touch,{capture:true,passive:true});
 document.addEventListener('pointerdown',e=>{pressed=true;touch(e);},true);
 for(const event of ['pointerup','pointercancel'])document.addEventListener(event,()=>{pressed=false;},true);
 window.addEventListener('blur',()=>{pressed=false;});
 function group(id,options={}){
  if(groups.has(id))return groups.get(id);
  const old=read(id),g={id,paused:typeof old.paused==='boolean'?old.paused:!!options.defaultPaused,label:options.label||labels[id]||id,host:options.host,before:options.before,controls:options.controls!==false,last:0,running:0,failed:false};groups.set(id,g);return g;
 }
 function every(scope,fn,ms,options={}){
  const aliases={weather:'overview',lcd:'overview',mobile:'system',feed:'messages'};if(aliases[scope]){options={...options,visibleHost:options.host};delete options.host;delete options.before;scope=aliases[scope];}
  if(Array.isArray(scope)){scope.forEach(id=>every(id,fn,ms,options));return;}
  const g=group(scope,options);jobs.push({g,fn,ms,due:Date.now()+ms,running:false,guard:options.guard,waiting:options.waiting,visibleHost:options.visibleHost});
 }
 function request(id){for(const j of jobs)if(j.g.id===id)j.due=0;}
 async function run(j,manual=false){
  if(j.running)return;
  const g=j.g;j.running=true;g.running++;if(manual)manualRuns++;paint(g);
  const target=host(g),open=new Set([...target?.querySelectorAll('details[open]')||[]].map(d=>d.id||d.querySelector('summary')?.textContent));
  try{await j.fn();for(const d of target?.querySelectorAll('details')||[])if(open.has(d.id||d.querySelector('summary')?.textContent))d.open=true;g.last=Date.now();g.failed=false;}catch(e){g.failed=true;console.error('Refresh '+g.id,e);}
  finally{if(manual)manualRuns--;j.running=false;g.running--;j.due=Date.now()+j.ms;paint(g);}
 }
 function host(g){return g.host?document.querySelector(g.host):document.getElementById('dashboard-panel-'+g.id)||document.querySelector('main');}
 function mount(g){
  if(!g.controls||g.bar?.isConnected)return;const target=host(g);if(!target)return;
  const bar=node('div');bar.className='rf-refresh-controls';bar.dataset.refreshArea=g.id;bar.setAttribute('role','group');bar.setAttribute('aria-label',g.label+' refresh controls');
  const label=node('label'),toggle=node('input');toggle.type='checkbox';toggle.setAttribute('aria-label',g.label+' auto-refresh');label.append(toggle,node('span','Auto-refresh'));
  const status=node('span');status.className='rf-refresh-state';
  toggle.addEventListener('change',()=>{g.paused=!toggle.checked;save(g);if(!g.paused)request(g.id);paint(g);});
  const now=node('button','Refresh');now.type='button';now.setAttribute('aria-label','Refresh '+g.label);now.addEventListener('click',()=>{jobs.filter(j=>j.g===g||j.g.id==='health'&&visible(j.g.id)).forEach(j=>{if(!j.visibleHost||document.querySelector(j.visibleHost)?.getClientRects().length)run(j,true);});});
  bar.append(label,status,now);if(g.before)target.before(bar);else target.prepend(bar);Object.assign(g,{bar,status,toggle,now});paint(g);
 }
 function paint(g){
  if(!g.bar)return;const list=jobs.filter(j=>j.g===g);
  const held=list.find(j=>j.guard&&!j.guard());
  const state=!navigator.onLine?'Offline':g.running?'Refreshing…':g.failed?'Update failed':g.paused?'Paused':interacting()?'Waiting for editing to finish':held?'Idle':g.last?'Updated '+new Date(g.last).toLocaleTimeString([], {hour:'numeric',minute:'2-digit'}):'Automatic';
  const level=!navigator.onLine||g.failed?'red':g.paused||interacting()?'yellow':held?'gray':'green';
  const paintKey=JSON.stringify([state,level,g.last,g.paused,!!g.running]);
  if(g.paintKey===paintKey)return;g.paintKey=paintKey;
  g.bar.dataset.state=level;g.status.textContent=state;g.status.title=g.last?'Last refresh cycle: '+new Date(g.last).toLocaleString():'';
  g.toggle.checked=!g.paused;g.now.disabled=!!g.running||!navigator.onLine;
 }
 async function ready(){while(document.hidden||(!manualRuns&&interacting()))await new Promise(resolve=>setTimeout(resolve,250));}
 window.RFRefresh={every,request,ready,allowed:id=>!groups.get(id)?.paused&&visible(id)&&!interacting()};
 setInterval(()=>{
  for(const g of groups.values()){mount(g);paint(g);}
  const active=document.querySelector('.dashboard-panel:not([hidden])')?.id.replace('dashboard-panel-',''),activeGroup=groups.get(active);
  for(const j of jobs)if(!j.g.paused&&!(j.g.id==='health'&&activeGroup?.paused)&&!j.running&&visible(j.g.id)&&(!j.visibleHost||document.querySelector(j.visibleHost)?.getClientRects().length)&&!interacting()&&(!j.guard||j.guard())&&Date.now()>=j.due)run(j);
 },1000);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)for(const g of groups.values())request(g.id);});
 window.addEventListener('online',()=>{for(const g of groups.values())request(g.id);});
})();
