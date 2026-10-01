(() => {
 'use strict';
 function init(){
  const nav=document.getElementById('dashboardTabs'),main=document.querySelector('main');if(!nav||!main)return;
  const make=(tag,text)=>{const e=document.createElement(tag);if(text)e.textContent=text;return e;};
  const tab=make('button','Ask questions');tab.type='button';tab.id='dashboard-tab-ask';tab.setAttribute('role','tab');tab.setAttribute('aria-selected','false');tab.setAttribute('aria-controls','dashboard-panel-ask');tab.tabIndex=-1;
  const panel=make('section');panel.id='dashboard-panel-ask';panel.className='dashboard-panel';panel.hidden=true;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tab.id);
  const card=make('div');card.className='card';card.style.maxWidth='960px';
  const form=make('form'),label=make('label','Your question'),input=make('textarea');input.id='askQuestion';label.htmlFor=input.id;input.rows=3;input.maxLength=2000;input.required=true;input.placeholder='How long has Receiver been online? How many direct receives did I get today?';input.style.cssText='display:block;box-sizing:border-box;width:100%;resize:vertical;margin:10px 0 14px;padding:14px;font:inherit';
  const submit=make('button','Ask');submit.type='submit';submit.className='primary';
  const hint=make('p','Answers use saved console data. Relevant records are sent to OpenAI when you ask.');hint.className='muted';hint.style.fontSize='12px';
  const status=make('p');status.setAttribute('role','status');status.style.whiteSpace='pre-wrap';
  const answer=make('div');answer.setAttribute('aria-live','polite');answer.style.cssText='white-space:pre-wrap;line-height:1.65;margin-top:20px';
  const sources=make('details');sources.hidden=true;sources.append(make('summary','Sources and evidence'));const evidence=make('div');sources.append(evidence);
  form.append(label,input,submit);card.append(form,hint,status,answer,sources);panel.append(card);nav.append(tab);main.append(panel);
  let busy=false,job=null;
  function setBusy(value){busy=value;submit.disabled=value;submit.textContent=value?'Looking into it…':'Ask';input.readOnly=value;}
  async function json(url,options={}){const r=await fetch(url,{cache:'no-store',...options});let data;try{data=await r.json();}catch{throw Error('The console connection was interrupted. Try again when it reconnects.');}if(!r.ok)throw Error(data.error||'Unable to answer right now.');return data;}
  async function readiness(){if(busy)return;try{const s=await json('/api/ask/status');status.textContent=!s.configured?'One-time setup: in your Pi terminal, run:\npython3 @@DATA_DIR@@/configure_ask.py\nEnter your OpenAI API key there; it stays on the Pi.':!s.unlocked?'Unlock Receiver controls once, or open the console in your trusted HTTPS browser, to ask questions.':'';}catch(e){status.textContent=e.message;}}
  function show(result){answer.textContent=result.answer;status.textContent='Answered '+new Date(result.answered_at).toLocaleString()+' · Default window: '+result.hours+'h unless your question specified another period';evidence.replaceChildren();sources.hidden=!result.sources?.length;for(const source of result.sources||[]){const box=make('details');box.append(make('summary','['+source.number+'] '+source.name));const pre=make('pre',JSON.stringify(source.evidence,null,2));pre.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px';box.append(pre);if(source.query){const query=make('pre',source.query);query.style.cssText=pre.style.cssText;box.append(query);}evidence.append(box);}}
  async function poll(){
   if(!job)return;
   try{const data=await json('/api/ask/'+job);if(data.state==='working'){setTimeout(poll,1500);return;}job=null;setBusy(false);if(data.state==='error')throw Error(data.error);show(data.result);}catch(e){job=null;setBusy(false);status.textContent=e.message;}
  }
  form.addEventListener('submit',async event=>{event.preventDefault();if(busy||!input.value.trim())return;setBusy(true);answer.textContent='';sources.hidden=true;sources.open=false;status.textContent='Reading the relevant console data…';try{const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);const id=Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');const data=await json('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:input.value.trim(),hours:typeof hours==='number'?hours:24,request_id:id})});job=data.job_id;poll();}catch(e){setBusy(false);status.textContent=e.message;}});
  input.addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();form.requestSubmit();}});
  tab.addEventListener('click',()=>{main.querySelectorAll('.dashboard-panel').forEach(p=>p.hidden=p!==panel);nav.querySelectorAll('[role=tab]').forEach(b=>{b.setAttribute('aria-selected',String(b===tab));b.tabIndex=b===tab?0:-1;});readiness();});
  nav.addEventListener('click',e=>{if(e.target.closest('[role=tab]')!==tab){panel.hidden=true;tab.setAttribute('aria-selected','false');tab.tabIndex=-1;}});
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
