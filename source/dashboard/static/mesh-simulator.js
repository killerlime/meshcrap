(() => {
  'use strict';
  if(new URLSearchParams(location.search).get('embedded')==='1')document.querySelector('main > a')?.remove();
  const $=id=>document.getElementById(id),model=globalThis.MeshSimulator,form=$('controls');
  for(const id of ['before','after'])for(const name of Object.keys(model.presets)){
    const option=document.createElement('option');option.textContent=name;option.value=name;
    option.defaultSelected=name===(id==='before'?'Medium Fast':'Long Fast');$(id).append(option);
  }
  const text=(tag,value)=>{const el=document.createElement(tag);el.textContent=value;return el;};
  function update(){
    if(!form.checkValidity()){$('error').textContent='Enter values within the limits shown by each field.';return;}
    const c={};for(const id of ['before','after','scope'])c[id]=$(id).value;
    for(const id of ['frequencyBefore','frequencyAfter','margin','nodes','messages','copies','bytes','preamble'])c[id]=$(id).valueAsNumber;
    let r;try{r=model.simulate(c);}catch(e){$('error').textContent='Check the scenario values.';return;}
    $('error').textContent='';
    $('summary').textContent=r.split?'The mesh splits unless the other radios change too.': 'Radio compatibility is preserved in this scenario. Actual reach remains unknown.';
    $('metrics').replaceChildren();
    for(const [label,value,note] of [
      ['Packet airtime',`${(r.oldAir.seconds*1000).toFixed(1)} → ${(r.newAir.seconds*1000).toFixed(1)} ms`,`${(r.newAir.seconds/r.oldAir.seconds).toFixed(2)}× the airtime per transmission`],
      ['Estimated margin on a matching link',`${c.margin.toFixed(1)} → ${r.margin.toFixed(1)} dB`,r.margin<0?'Below the assumed decoding threshold; not a measured outage.':'Above the assumed threshold; not a delivery guarantee.'],
      ['Frequency-only loss change',`${r.frequencyLoss.toFixed(2)} dB`,'Positive means more free-space loss, with equal antenna gains.'],
      ['Modem sensitivity allowance',`${r.sensitivityGain.toFixed(1)} dB`,'Approximate SF/bandwidth difference, not measured hardware sensitivity.']]){
      const card=text('div','');card.className='metric';card.append(text('span',label),text('strong',value),text('small',note));$('metrics').append(card);
    }
    $('local-link').classList.toggle('broken',!r.localCompatible);$('regional-link').classList.toggle('broken',!r.regionalCompatible);
    $('links').textContent=`My node ↔ local group: ${r.localCompatible?'matching radio settings':'mismatched radio settings'}. Local group ↔ regional mesh: ${r.regionalCompatible?'matching radio settings':c.scope==='one'?'unchanged; only my node is isolated':'mismatched radio settings'}. Dashed amber means a settings mismatch, not weak signal.`;
    // When only one node changes, the rest of the mesh still shares its original settings.
    $('regional-link').classList.toggle('broken',r.split&&c.scope==='local');
    $('airtime-bars').replaceChildren();for(const [name,value] of [['Before',r.oldLoad],['If this whole neighborhood used the proposal',r.newLoad]]){
      const bar=text('div','');bar.className='bar';const fill=text('span','');fill.style.width=Math.min(100,value)+'%';bar.append(fill);
      $('airtime-bars').append(text('p',`${name}: ${value.toFixed(1)}% offered airtime`),bar);
    }
    $('symbol').textContent=`One symbol: ${r.oldAir.symbolMs.toFixed(3)} ms before → ${r.newAir.symbolMs.toFixed(3)} ms after. Packet overhead and coding are included in the airtime estimate above.`;
  }
  form.addEventListener('input',update);form.addEventListener('change',update);form.addEventListener('submit',e=>e.preventDefault());form.addEventListener('reset',()=>setTimeout(update,0));update();
})();
