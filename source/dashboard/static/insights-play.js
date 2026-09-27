/* Private message comics. No radio actions, uploads, or external assets. */
(() => {
 'use strict';
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
 function init(){
  const panel=document.getElementById('dashboard-panel-insights');if(!panel)return;
  const comicActors=['👽','🤖','🐱'];
  const comic=el('section',null,'card insight-comics');comic.id='insight-comics';comic.append(el('h3','The mesh funny pages'),el('p','Real broadcast words. Imaginary costumes. Panels follow recorded time within one channel; they may be unrelated messages, not replies. Comics stay on this private page.','insight-sub'));
  const comicTools=el('div',null,'insight-toolbar'),channelLabel=el('label','Channel '),channel=el('select'),refresh=el('button','Make a comic'),older=el('button','Older strip'),newer=el('button','Newer strip'),comicStatus=el('p','Choose a channel and make a comic. No messages are sent.');refresh.type=older.type=newer.type='button';comicStatus.setAttribute('role','status');channel.setAttribute('aria-label','Comic channel');channelLabel.append(channel);
  // Channel options are populated from the dashboard's configuration by the read-only endpoint.
  const strips=el('div',null,'insight-comic-grid');comicTools.append(channelLabel,refresh,newer,older);comic.append(comicTools,comicStatus,strips);older.disabled=newer.disabled=true;
  let messages=[],history=[],offset=0,cursor=null,loading=false,comicChannel='';
  function renderComics(){strips.replaceChildren();for(const m of messages.slice(offset,offset+6).reverse()){const p=el('article',null,'insight-comic-panel'),caption=el('div',null,'comic-caption'),time=el('time',new Date(m.received_at).toLocaleString());time.dateTime=m.received_at;caption.append(el('strong',m.sender),time);const bubble=el('blockquote',m.text,'comic-bubble'),actor=el('div',null,'comic-actor');let hash=0;for(const c of m.sender_id)hash=(hash*31+c.charCodeAt(0))>>>0;actor.textContent=comicActors[hash%comicActors.length];actor.setAttribute('aria-hidden','true');p.append(caption,bubble,actor);strips.append(p);}older.disabled=loading||!(offset+6<messages.length||cursor);newer.disabled=loading||offset===0;}
  async function readComic(append=false){if(loading)return;loading=true;refresh.disabled=channel.disabled=true;older.disabled=newer.disabled=true;comicStatus.textContent='Opening the funny pages…';try{const url='/api/channel-messages?channel='+encodeURIComponent(channel.value)+(append&&cursor?'&before='+cursor:'');const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error();const d=await r.json();const incoming=d.messages.filter(m=>typeof m.text==='string'&&typeof m.sender_id==='string');if(append){history.push(offset);offset=messages.length;messages.push(...incoming);}else{messages=incoming;history=[];offset=0;}cursor=d.next_before;comicChannel=d.channel_name;comicStatus.textContent=messages.length?`${comicChannel} · original wording, decorative characters · received times shown`:'No saved broadcast messages on this channel yet.';}catch{comicStatus.textContent='Could not load messages. Try Make a comic again.';}finally{loading=false;refresh.disabled=channel.disabled=false;renderComics();}}
  refresh.addEventListener('click',()=>readComic());channel.addEventListener('change',()=>{messages=[];history=[];offset=0;cursor=null;renderComics();comicStatus.textContent='Choose Make a comic to read this channel.';});
  older.addEventListener('click',()=>{if(offset+6<messages.length){history.push(offset);offset+=6;renderComics();}else if(cursor)readComic(true);});newer.addEventListener('click',()=>{offset=history.pop()||0;renderComics();});
  // Configuration only; no messages loaded until requested.
  let channelsLoaded=false;async function loadChannels(){if(channelsLoaded)return;try{const r=await fetch('/api/insights/channels',{signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error();const d=await r.json();for(const [id,name] of Object.entries(d.channels)){const o=el('option',name);o.value=id;channel.append(o);}channel.value=String(d.channel);channelsLoaded=true;refresh.disabled=false;}catch{comicStatus.textContent='Channel list unavailable. Reopen Insights to try again.';refresh.disabled=true;}}
  panel.querySelector('.insight-jumps').after(comic);
  for(const [id,text] of [['comics','Funny pages']]){const a=el('a',text);a.href='#insight-'+id;panel.querySelector('.insight-jumps').append(a);}
  document.getElementById('dashboard-tab-insights').addEventListener('click',loadChannels);refresh.disabled=true;
  if(!panel.hidden)loadChannels();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
