(() => {
  const $=id=>document.getElementById(id), element=(tag,text)=>{const e=document.createElement(tag);e.textContent=text;return e;};
  let state=null, groups=[], readers=[], pending=null, busy=false;
  const sendStatus=element('p','');sendStatus.id='sendStatus';sendStatus.setAttribute('role','status');sendStatus.setAttribute('aria-live','polite');$('send').append(sendStatus);
  const status=text=>{$('status').textContent=text;sendStatus.textContent=text;};
  const uuid=()=>{const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);return [...bytes].map(x=>x.toString(16).padStart(2,'0')).join('');};

  const replyLabel=element('label','Reply to (optional)');replyLabel.className='field';
  const replySelect=element('select','');replySelect.id='replyMessage';replyLabel.append(replySelect);$('message').closest('p').before(replyLabel);
  const resetReplies=()=>{const o=element('option','New message');o.value='';replySelect.replaceChildren(o);};resetReplies();
  let replyGeneration=0;
  async function loadReplies(){
    const generation=++replyGeneration;resetReplies();replySelect.disabled=true;
    if($('recipient').value!=='^all')return;
    const channel=$('sendChannel').value;
    try{const response=await fetch('/api/channel-messages?channel='+encodeURIComponent(channel),{cache:'no-store',signal:AbortSignal.timeout(10000)});if(!response.ok)throw new Error();const data=await response.json();if(generation!==replyGeneration)return;
      for(const msg of data.messages){const o=element('option',msg.sender+': '+msg.text.replace(/\s+/g,' ').slice(0,100));o.value=String(msg.id);replySelect.append(o);}replySelect.disabled=false;
    }catch(error){if(generation===replyGeneration){const o=element('option','Reply history unavailable — refresh to retry');o.value='';replySelect.append(o);}}
  }
  $('sendChannel').addEventListener('change',loadReplies);$('recipient').addEventListener('change',loadReplies);

  const actionsCard=element('section','');actionsCard.className='card';
  actionsCard.innerHTML=`<h2>Node actions</h2><p class="muted">Request information from a node, manage Receiver’s node list, or maintain Receiver. Replies depend on the target’s firmware, permissions and reachability.</p><form id="radioAction"><div class="grid"><label class="field">Action<select id="operation"></select></label><label class="field">Destination<select id="operationNode"></select></label><label class="field">Channel<select id="operationChannel"></select></label><label class="field">Hop limit<input id="operationHops" type="number" min="0" max="7" value="3" required></label></div><p id="operationNote" class="muted"></p><button class="primary">Review action</button></form><h3>Action results</h3><p class="muted">Recent actions from this collector session. Pending replies refresh while this panel is visible.</p><button id="refreshOperations" type="button">Refresh results</button><div id="operationResults" aria-live="polite"></div>`;
  $('controls').insertBefore(actionsCard,$('send').closest('section'));
  const confirmLabel=element('label','Type the destination node ID to confirm');confirmLabel.className='field';confirmLabel.hidden=true;
  const confirmInput=element('input','');confirmInput.autocomplete='off';confirmLabel.append(confirmInput);$('review').after(confirmLabel);
  let resultBusy=false,hasPending=false;
  function resultText(job){
    const r=job.result;
    if(job.operation!=='traceroute')return JSON.stringify(r,null,2);
    const name=id=>id===job.source?'Receiver':state.nodes.find(n=>n.id===id)?.name||id;
    const path=(start,middle,end,snr)=>[start,...middle,end].map((id,i)=>name(id)+(i&&snr?.length===middle.length+1?' ('+(snr[i-1]===-128?'unknown':snr[i-1]/4+' dB')+')':'')).join(' → ');
    return 'Forward route\n'+path(job.source,r.route||[],job.destination,r.snrTowards)+'\n\nReturn route\n'+(r.returnRouteAvailable?path(job.destination,r.routeBack||[],job.source,r.snrBack):'Not reported by the responding firmware.');
  }
  function operationChanged(){const spec=state?.actions?.find(a=>a.id===$('operation').value);$('operationNode').disabled=!!spec?.local;if(spec?.local)$('operationNode').value=state.node_id;
    const warnings={shutdown:'Receiver shuts down in 10 seconds and may need physical power to resume.',reboot:'Receiver reboots in 10 seconds, briefly interrupting collection.',reset_nodes:'Clears Receiver’s radio node list. Stored dashboard history is retained.',reset_config:'Resets Receiver configuration. Network access may be lost; local setup may be required.',factory_reset:'Erases Receiver configuration and node list. Local setup may be required to reconnect.',remove_node:'Removes this node from Receiver’s radio list. Dashboard history is retained; future traffic may rediscover it.',ignore:'Tells Receiver to ignore this node; this can change mesh reception.'};
    $('operationNote').textContent=warnings[$('operation').value]||(spec?.local?'This action applies to Receiver itself.':'Requests are directed to the selected node. No automatic retries.');}
  async function refreshOperations(){if(resultBusy||$('controls').hidden)return;resultBusy=true;try{const data=await request('action',{action:'operations'});hasPending=data.operations.some(j=>['waiting','acknowledged'].includes(j.status));$('operationResults').replaceChildren();for(const job of data.operations){const box=element('details','');box.open=['waiting','acknowledged'].includes(job.status);box.append(element('summary',`${job.operation.replaceAll('_',' ')} → ${job.destination} · ${job.status}`),element('p',job.message));if(job.result){const pre=element('pre',resultText(job));pre.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere';box.append(pre);}$('operationResults').append(box);}if(!data.operations.length)$('operationResults').textContent='No actions yet.';}catch(error){status(error.message);}finally{resultBusy=false;}}
  async function request(path,body){
    const response=await fetch('/api/node-control/'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,cache:'no-store',signal:AbortSignal.timeout(15000)});
    const result=await response.json();
    if(response.status===401){$('unlock').hidden=false;$('controls').hidden=true;}
    if(!response.ok||result.ok===false)throw new Error(result.error||'Unable to complete the action');
    return result.data||result;
  }
  function setBusy(value){busy=value;document.querySelectorAll('button').forEach(b=>b.disabled=value);}
  async function refresh(){
    setBusy(true);status('Reading settings from the collector…');
    try{
      state=await request('action',{action:'state'});$('unlock').hidden=true;$('controls').hidden=false;
      const preset=state.groups.find(g=>g.kind==='config'&&g.name==='lora')?.fields.find(f=>f.name==='modem_preset')?.value;
      for(const channel of state.channels){
        const name=channel.fields.find(f=>f.name==='settings')?.fields.find(f=>f.name==='name')?.value;
        if(channel.enabled&&!name&&preset)channel.name=preset.toLowerCase().split('_').map(s=>s[0].toUpperCase()+s.slice(1)).join('');
      }
      $('identity').textContent=state.node_id+' · '+(state.metadata.firmwareVersion||'Connected');
      groups=[...state.groups,...state.channels.map(c=>({...c,kind:'channel',name:String(c.index),label:'Channel '+c.index+' · '+c.name}))];
      const old=$('group').value;$('group').replaceChildren();
      groups.forEach((g,i)=>{const option=element('option',g.label||((g.kind==='module'?'Module · ':'')+g.name.replaceAll('_',' ')));option.value=String(i);$('group').append(option);});
      if(old&&Number(old)<groups.length)$('group').value=old;
      $('sendChannel').replaceChildren();state.channels.filter(c=>c.enabled).forEach(c=>{const o=element('option',c.index+' · '+c.name);o.value=c.index;$('sendChannel').append(o);});
      $('recipient').replaceChildren(element('option','Everyone on channel'));$('recipient').firstElementChild.value='^all';$('nodes').replaceChildren();
      state.nodes.forEach(n=>{const option=element('option',n.name+' · '+n.id);option.value=n.id;$('recipient').append(option);const row=element('tr','');row.append(element('td',n.name),element('td',n.id),element('td',n.battery==null?'—':n.battery+'%'));$('nodes').append(row);});
      $('operation').replaceChildren();(state.actions||[]).forEach(a=>{const o=element('option',a.label);o.value=a.id;$('operation').append(o);});
      $('operationNode').replaceChildren();const actionNodes=[{id:state.node_id,name:'Receiver (this radio)'},...state.nodes.filter(n=>n.id!==state.node_id)];actionNodes.forEach(n=>{const o=element('option',n.name+' · '+n.id);o.value=n.id;$('operationNode').append(o);});if(actionNodes.length>1)$('operationNode').value=actionNodes[1].id;
      $('operationChannel').replaceChildren();state.channels.filter(c=>c.enabled).forEach(c=>{const o=element('option',c.index+' · '+c.name);o.value=c.index;$('operationChannel').append(o);});if(state.channels.some(c=>c.index===1&&c.enabled))$('operationChannel').value='1';
      $('operationHops').value=state.groups.find(g=>g.name==='lora')?.fields.find(f=>f.name==='hop_limit')?.value??3;operationChanged();
      loadReplies();renderGroup();refreshOperations();status('Connected. No radio settings have been changed.');
    }catch(error){status(error.message);}finally{setBusy(false);}
  }
  function renderGroup(){
    readers=[];$('fields').replaceChildren();const group=groups[Number($('group').value)];if(!group)return;
    buildFields(group.fields,$('fields'),[],readers);
  }
  function buildFields(fields,parent,path,collect){
    const grid=element('div','');grid.className='grid';parent.append(grid);
    for(const field of fields){
      const full=[...path,field.name];
      if(field.type==='message'){
        const box=element('fieldset','');box.append(element('legend',field.label));parent.append(box);
        if(field.repeated){
          const entries=[];
          const addEntry=spec=>{const item=element('fieldset',''),local=[];buildFields(spec,item,[],local);const remove=element('button','Remove');remove.type='button';remove.onclick=()=>{item.remove();entries.splice(entries.indexOf(local),1);};item.append(remove);box.insertBefore(item,add);entries.push(local);};
          const add=element('button','Add entry');add.type='button';box.append(add);(field.items||[]).forEach(addEntry);add.onclick=()=>addEntry(field.prototype);
          const initial=JSON.stringify(entries.map(rs=>collectValues(rs,true)));
          collect.push(()=>{const value=entries.map(rs=>collectValues(rs,true));return JSON.stringify(value)===initial?null:{path:full,value,label:field.label,secret:field.secret};});
        }else buildFields(field.fields,box,full,collect);
        continue;
      }
      const label=element('label',field.label);label.className='field';const input=element(field.repeated?'textarea':field.type==='enum'?'select':'input','');label.append(input);grid.append(label);let clear=null;
      if(field.repeated){input.value=field.secret?'':(field.value||[]).join('\n');input.rows=3;label.append(element('small','One value per line'));}
      else if(field.type==='enum'){field.options.forEach(v=>{const o=element('option',v);o.value=v;input.append(o);});input.value=field.value||field.options[0];}
      else if(field.type==='boolean'){input.type='checkbox';input.checked=!!field.value;}
      else {input.type=field.secret?'password':field.type==='number'?'number':'text';if(field.type==='number')input.step='any';input.value=field.secret?'':(field.value??'');}
      if(field.name==='index'&&path.length===0){input.disabled=true;}
      if(field.secret){input.autocomplete='off';input.placeholder=field.configured?'Configured — leave blank to keep':'Leave blank to keep';label.append(element('small','Existing value stays hidden. Enter a replacement only to change it.'));const clearLabel=element('label','Clear stored '+field.label.toLowerCase());clear=element('input','');clear.type='checkbox';clearLabel.prepend(clear);grid.append(clearLabel);}
      if(field.type==='bytes')label.append(element('small','Base64-encoded key or bytes'));
      const value=()=>field.repeated?input.value.split('\n').filter(x=>x.trim()).map(x=>field.type==='number'?Number(x):x):field.type==='boolean'?input.checked:field.type==='number'?Number(input.value):input.value;
      const initial=JSON.stringify(value());
      collect.push(all=>{const v=clear?.checked?(field.repeated?[]:''):value();if(!all&&!clear?.checked&&(JSON.stringify(v)===initial||(field.secret&&!input.value)))return null;return {path:full,value:v,label:full.join(' › '),secret:field.secret};});
    }
  }
  function readAll(fields){const value={};for(const f of fields)value[f.name]=f.type==='message'?(f.repeated?(f.items||[]).map(readAll):readAll(f.fields)):f.value;return value;}
  function collectValues(rs,all=false){const result={};for(const read of rs){const change=read(all);if(!change)continue;let at=result;for(const p of change.path.slice(0,-1))at=at[p]||(at[p]={});at[change.path.at(-1)]=change.value;}return result;}
  function review(title,text,body){pending=body;confirmInput.value='';confirmLabel.hidden=!(body.action==='operation'&&state.actions.find(a=>a.id===body.operation)?.confirm);$('confirmTitle').textContent=title;$('review').textContent=text;$('confirm').showModal();}
  $('operation').onchange=operationChanged;
  $('radioAction').onsubmit=event=>{event.preventDefault();const spec=state.actions.find(a=>a.id===$('operation').value);const destination=$('operationNode').value;review(spec.label+'?',$('operationNode').selectedOptions[0].textContent+'\n'+$('operationNote').textContent+(spec.confirm?'\n\nConfirm by typing '+destination:''),{action:'operation',operation:spec.id,destination,channel:Number($('operationChannel').value),hops:Number($('operationHops').value),request_id:uuid()});};
  $('refreshOperations').onclick=refreshOperations;
  setInterval(()=>{if(hasPending&&!document.hidden&&(!window.frameElement||window.frameElement.getClientRects().length))refreshOperations();},3000);
  $('unlock').onsubmit=async event=>{event.preventDefault();setBusy(true);try{await request('unlock',{key:$('key').value,remember:$('rememberDevice').checked});$('key').value='';await refresh();}catch(error){status(error.message);}finally{setBusy(false);}};
  $('group').onchange=renderGroup;
  $('settings').onsubmit=event=>{event.preventDefault();const changes=collectValues(readers);if(!Object.keys(changes).length){status('No changes to apply.');return;}const group=groups[Number($('group').value)];const lines=readers.map(r=>r()).filter(Boolean).map(c=>c.label+': '+(c.secret?'[new hidden value]':JSON.stringify(c.value)));
    review('Apply '+(group.label||group.name)+' changes?',lines.join('\n')+'\n\nReceiver may reboot or disconnect. These changes affect your live radio and RF measurements.',{action:'save',kind:group.kind,name:group.name,revision:group.revision,changes,request_id:uuid()});};
  $('send').onsubmit=event=>{event.preventDefault();const text=$('message').value;const size=new TextEncoder().encode(text).length;if(!text.trim()||size>228){status('Messages must contain 1–228 UTF-8 bytes.');return;}review('Send message?',$('sendChannel').selectedOptions[0].textContent+' → '+$('recipient').selectedOptions[0].textContent+(replySelect.value?'\nReply to: '+replySelect.selectedOptions[0].textContent:'')+'\n\n'+text,{action:'send',text,channel:Number($('sendChannel').value),destination:$('recipient').value,reply_row_id:replySelect.value?Number(replySelect.value):null,request_id:uuid()});};
  $('message').oninput=()=>$('messageSize').textContent=new TextEncoder().encode($('message').value).length+' / 228 bytes';
  $('cancel').onclick=()=>{$('confirm').close();pending=null;};
  $('apply').onclick=async()=>{if(busy||!pending)return;if(!confirmLabel.hidden&&confirmInput.value!==pending.destination){confirmInput.setCustomValidity('Enter the exact destination node ID');confirmInput.reportValidity();return;}confirmInput.setCustomValidity('');const body=pending;if(!confirmLabel.hidden)body.confirm_node=confirmInput.value;pending=null;$('confirm').close();setBusy(true);try{const result=await request('action',body);status(result.message);if(body.action==='operation'){hasPending=true;refreshOperations();}if(body.action==='send'){$('message').value='';$('message').oninput();replySelect.value='';}}catch(error){status(error.message+' If the request timed out, verify the radio before retrying.');}finally{setBusy(false);}};
  $('refresh').onclick=refresh;$('lock').onclick=async()=>{try{await request('action',{action:'lock'});$('controls').hidden=true;$('unlock').hidden=false;state=null;groups=[];$('fields').replaceChildren();status('Controls locked.');}catch(error){status(error.message);}};
  $('unlockSettings').onclick=()=>{$('unlock').hidden=false;$('key').focus();};
  $('revokeDevices').onclick=async()=>{if(!window.confirm('Revoke remembered access for all browsers? Existing one-hour settings sessions will expire normally.'))return;try{const result=await request('action',{action:'revoke_devices'});status(result.message);}catch(e){status(e.message);}};
  request('session').then(s=>{$('rememberLabel').hidden=!s.secure;$('httpsHint').hidden=s.secure;if(s.unlocked)refresh();else{$('unlock').hidden=false;status('Unlock to view and change radio settings.');}}).catch(e=>status(e.message));
})();
