(() => {
 async function init(){
  const panel=document.getElementById('dashboard-panel-control'),tab=document.getElementById('dashboard-tab-control');if(!panel||!tab)return;
  let settings;try{const response=await fetch('/api/receiver-comparison/integration',{cache:'no-store',signal:AbortSignal.timeout(5000)});if(!response.ok)return;settings=await response.json();}catch{return;}
  if(!settings.enabled||!settings.controls_enabled)return;
  const choices=document.createElement('div');choices.className='console-toolbar';choices.setAttribute('role','group');choices.setAttribute('aria-label','Choose node to control');
  let selected='receiver',secondary;const buttons=[];
  function show(id){selected=id;if(id==='secondary'&&!secondary){secondary=document.createElement('iframe');secondary.title='Secondary radio control';secondary.src='/secondary-control?embedded=1';secondary.style.cssText='width:100%;height:calc(100vh - 280px);min-height:600px;border:0;border-radius:12px';panel.append(secondary);}panel.querySelectorAll('iframe').forEach(f=>{const active=(f===secondary)===(id==='secondary');f.hidden=!active;f.style.display=active?'block':'none';});buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.node===id)));}
  for(const [id,label] of [['receiver','Receiver'],['secondary',settings.secondary_label||'Secondary radio']]){const b=document.createElement('button');b.type='button';b.textContent=label;b.dataset.node=id;b.setAttribute('aria-pressed',String(id===selected));b.onclick=()=>show(id);buttons.push(b);choices.append(b);}
  panel.prepend(choices);tab.addEventListener('click',()=>show(selected));
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
