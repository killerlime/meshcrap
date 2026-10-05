(() => {
 'use strict';
 const validId=id=>Number.isSafeInteger(id)&&id>=0;
 const mark=(seen,channel,id)=>/^\d+$/.test(channel)&&validId(id)?{...seen,[channel]:Math.max(validId(seen[channel])?seen[channel]:0,id)}:seen;
 const unread=(heads,seen)=>Object.entries(heads).some(([channel,id])=>validId(id)&&id>(validId(seen[channel])?seen[channel]:0));
 window.RFMessageRead={mark,unread};
 function init(){
  const key='rf.messagesSeen.v1';let seen={},heads=null,busy=false;
  const restore=()=>{try{const value=JSON.parse(localStorage.getItem(key)||'{}');seen=value&&typeof value==='object'&&!Array.isArray(value)?value:{};}catch(_){seen={};}};
  restore();
  function paint(){
   const button=document.querySelector('.rf-nav-page[data-page="messages"]');if(!button)return;
   let dot=button.querySelector('.rf-message-dot');if(!dot){dot=document.createElement('span');dot.className='rf-message-dot';dot.setAttribute('aria-hidden','true');dot.style.cssText='display:inline-block;flex:0 0 8px;width:8px;height:8px;border-radius:50%;margin-left:auto;box-shadow:0 0 0 1px #ffffff40';button.append(dot);}
   const pending=heads&&unread(heads,seen),label=heads?(pending?'Unread messages':'All messages read'):'Checking messages';
   dot.style.background=heads?(pending?'#ff5353':'#40c980'):'#999';dot.title=label;button.setAttribute('aria-label','Messages — '+label);
  }
  async function check(){
   if(document.hidden||busy)return;busy=true;
   try{const response=await fetch('/api/message-heads',{cache:'no-store',signal:AbortSignal.timeout(10000)});if(!response.ok)throw Error('Message status unavailable');const data=await response.json();heads=data.heads;paint();}
   catch(_){const button=document.querySelector('.rf-nav-page[data-page="messages"]');if(button)button.title='Message status could not refresh';}
   finally{busy=false;}
  }
  window.addEventListener('message',event=>{
   const panel=document.getElementById('dashboard-panel-messages'),frame=panel?.querySelector('iframe');
   if(event.origin!==location.origin||event.source!==frame?.contentWindow||panel.hidden||document.hidden||event.data?.type!=='rf:messages-read')return;
   seen=mark(seen,String(event.data.channel),event.data.id);try{localStorage.setItem(key,JSON.stringify(seen));}catch(_){}paint();
  });
  window.addEventListener('storage',event=>{if(event.key===key){restore();paint();}});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)check();});
  const sidebar=document.getElementById('rfSidebar');if(sidebar)new MutationObserver(paint).observe(sidebar,{childList:true});
  paint();check();setInterval(check,30000);
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
