(() => {
 function init(){
  const panel=document.getElementById('dashboard-panel-control'),tab=document.getElementById('dashboard-tab-control');if(!panel||!tab)return;
  const choices=document.createElement('div');choices.className='console-toolbar';choices.setAttribute('role','group');choices.setAttribute('aria-label','Choose node to control');
  let selected='gunit',kmkt;const buttons=[];
  function show(id){selected=id;if(id==='kmkt'&&!kmkt){kmkt=document.createElement('iframe');kmkt.title='Secondary radio control';kmkt.src='/kmkt-control?embedded=1';kmkt.style.cssText='width:100%;height:calc(100vh - 280px);min-height:600px;border:0;border-radius:12px';panel.append(kmkt);}panel.querySelectorAll('iframe').forEach(f=>{const active=(f===kmkt)===(id==='kmkt');f.hidden=!active;f.style.display=active?'block':'none';});buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.node===id)));}
  for(const [id,label] of [['gunit','Receiver'],['kmkt','Secondary radio']]){const b=document.createElement('button');b.type='button';b.textContent=label;b.dataset.node=id;b.setAttribute('aria-pressed',String(id===selected));b.onclick=()=>show(id);buttons.push(b);choices.append(b);}
  panel.prepend(choices);tab.addEventListener('click',()=>show(selected));
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
