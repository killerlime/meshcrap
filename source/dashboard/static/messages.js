(() => {
  const list=document.getElementById('messages'),status=document.getElementById('status');
  const older=document.getElementById('older'),latest=document.getElementById('latest');
  const channelSelect=document.getElementById('channel');
  let cursor=null,next=null,busy=false,loaded=null;
  const exportButton=document.getElementById("exportMessagesCsv");
  const element=(tag,text,cls)=>{const el=document.createElement(tag);el.textContent=text;if(cls)el.className=cls;return el;};
  const search=document.getElementById('messageSearch');let visible=[];
  function render(){
    if(!loaded)return;
    const term=search.value.trim().toLowerCase();
    visible=loaded.messages.filter(m=>[m.sender,m.sender_id,m.text].some(v=>String(v||'').toLowerCase().includes(term)));
    const content=document.createDocumentFragment();let day=null;
    for(const msg of visible){
      const date=new Date(msg.received_at),key=date.toLocaleDateString();
      if(day!==key){content.append(element('h2',date.toLocaleDateString(undefined,{weekday:'long',month:'short',day:'numeric',year:'numeric'}),'console-day'));day=key;}
      const article=element('article',''),meta=element('div','','meta'),stamp=element('time',date.toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit',second:'2-digit'}),'muted');stamp.dateTime=msg.received_at;stamp.title=date.toLocaleString();
      meta.append(element('span',msg.sender,'sender'),stamp);article.append(meta,element('p',msg.text,'message'));
      const detail=[msg.sender_id];if(msg.direction==='sent')detail.push('Submitted to Receiver · delivery not confirmed');if(msg.snr!=null)detail.push('SNR '+msg.snr+' dB');if(msg.hops!=null)detail.push(msg.hops===0?'Direct':msg.hops+' hops');
      article.append(element('div',detail.join(' · '),'muted details'));content.append(article);
    }
    if(!visible.length&&loaded.messages.length)content.append(element('p','No messages match this search.','muted'));
    list.replaceChildren(content);exportButton.disabled=!visible.length;
    document.getElementById('messageMatchCount').textContent=`${visible.length} of ${loaded.messages.length} loaded messages`;
    const known=visible.filter(m=>m.hops!=null);
    window.ConsoleUI?.summary('messageSummary',[
      ['Messages',visible.length,cursor?'History page':'Latest loaded page'],
      ['Senders',new Set(visible.map(m=>m.sender_id)).size,'Unique on this page'],
      ['Direct',known.filter(m=>m.hops===0).length,`${known.length} with known hops`]]);
  }
  search.addEventListener('input',render);
  async function load(target=cursor){
    if(busy)return;
    busy=true;document.getElementById('refresh').disabled=true;older.disabled=true;latest.disabled=true;channelSelect.disabled=true;
    try{
      const params=new URLSearchParams({channel:channelSelect.value});
      if(target)params.set('before',target);
      const response=await fetch('/api/channel-messages?'+params,{cache:'no-store',signal:AbortSignal.timeout(10000)});
      if(!response.ok)throw new Error('Request failed');
      const data=await response.json();
      if(data.channel!==Number(channelSelect.value))throw new Error('Channel change is not active yet');
      data.messages=[...data.messages,...(data.sent_messages||[])].sort((a,b)=>Date.parse(b.received_at)-Date.parse(a.received_at));
      loaded=data;exportButton.disabled=data.messages.length===0;
      cursor=target;next=data.next_before;render();
      document.querySelector('h1').textContent=data.channel_name+' messages';
      document.getElementById('empty').hidden=data.messages.length>0;
      older.hidden=!next;latest.hidden=!cursor;
      status.textContent=(cursor?'History':'Updated '+new Date().toLocaleTimeString())+' · '+data.messages.length+' messages';
    }catch(error){status.textContent='Unable to refresh. Showing the last loaded messages; retry shortly.';}
    finally{busy=false;document.getElementById('refresh').disabled=false;older.disabled=false;latest.disabled=false;channelSelect.disabled=false;}
  }
  channelSelect.addEventListener('change',()=>{
    loaded=null;visible=[];exportButton.disabled=true;document.getElementById("messageSummary").replaceChildren();document.getElementById("messageMatchCount").textContent="";
    cursor=null;next=null;list.replaceChildren();older.hidden=true;latest.hidden=true;
    document.getElementById('empty').hidden=true;
    document.querySelector('h1').textContent=channelSelect.selectedOptions[0].textContent+' messages';
    status.textContent='Loading messages…';load(null);
  });
  exportButton.addEventListener('click',()=>{
    if(!loaded)return;
    ConsoleCSV.download('messages-'+loaded.channel_name,
      ['Time UTC','Channel','Channel index','Sender','Sender ID','Message','SNR dB','Hops','Direction'],
      visible.map(m=>[m.received_at,loaded.channel_name,loaded.channel,m.sender,m.sender_id,m.text,m.snr,m.hops,m.direction||'received']));
  });
  document.getElementById('refresh').addEventListener('click',()=>load());
  older.addEventListener('click',()=>load(next));latest.addEventListener('click',()=>load(null));
  setInterval(()=>{if(!cursor&&!document.hidden&&(!window.frameElement||window.frameElement.getClientRects().length))load(null);},10000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!cursor)load(null);});load();
})();
