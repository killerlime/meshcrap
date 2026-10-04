(() => {
  'use strict';
  const model=globalThis.MeshSimulator,host=document.getElementById('node-builder');if(!host)return;
  const el=(tag,value)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;return e;};
  host.append(el('h2','Node builder'),el('p','Build a hypothetical RF chain. All values are editable assumptions; consult the exact device revision and frequency-specific datasheet. Coordinates stay in this page and are never sent or saved.'));
  host.append(el('p','* Required for the calculation. Optional sections identify their own required inputs; enter 0 for components that are absent.'));
  const form=el('form'),fields=el('div');fields.className='fields';form.append(fields);host.append(form);
  const controls={};
  function select(key,label,choices){const wrap=el('label',label+' *'),input=el('select');input.setAttribute('aria-label',label);input.required=true;for(const [value,text] of choices){const option=el('option',text);option.value=value;input.append(option);}wrap.append(input);fields.append(wrap);controls[key]=input;return input;}
  select('hardware','Hardware preset',Object.entries(globalThis.RadioHardware).map(([key,p])=>[key,p.name]));
  const hardwareNote=el('section');hardwareNote.className='builder-hardware-info';fields.append(hardwareNote);
  select('modem','Builder modem preset',Object.keys(model.presets).map(p=>[p,p]));controls.modem.value='Medium Fast';
  select('antenna','Antenna pattern reference',[['omni','Omnidirectional'],['directional','Directional (assumes aimed at remote node)'],['custom','Custom / measured pattern']]);
  select('cable','Coax type',[['custom','Custom / other coax: enter loss rate'],['LMR-400','Times Microwave standard LMR-400'],['LMR-240','Times Microwave standard LMR-240']]);
  for(const [key,label,value,min,max,step] of [
    ['frequency','Frequency (MHz)',915,100,2500,.001],['power','Actual radio connector TX power (dBm)',20,-30,40,.1],['gain','Antenna gain toward remote node (dBi)',3,-20,40,.1],
    ['length','Coax length (m)',5,0,1000,.1],['rate','Custom coax loss at this frequency (dB / 100 m)',20,0,200,.1],['connectors','Total connector / adapter loss (dB)',.5,0,30,.1],
    ['filter','Cavity filter insertion loss (dB; 0 = absent)',0,0,30,.1],['other','Arrestor, switch, pigtail and other loss (dB)',0,0,30,.1],
    ['sensitivity','Local receiver sensitivity (dBm, assumed)',-130,-160,-40,.1],['remotePower','Remote radio TX power (dBm)',20,-30,40,.1],['remoteGain','Remote antenna gain toward local node (dBi)',3,-20,40,.1],
    ['remoteLoss','Remote total feedline / component loss (dB)',1,0,60,.1],['remoteSensitivity','Remote receiver sensitivity (dBm, assumed)',-130,-160,-40,.1],
    ['distance','Path distance (km)',10,.001,20000,.001],['extraLoss','Additional path loss beyond free space (dB, assumed)',20,0,150,.1]
  ]){const wrap=el('label',label+' *'),input=el('input');input.type='number';input.setAttribute('aria-label',label);input.value=value;input.min=min;input.max=max;input.step=step;input.required=true;wrap.append(input);fields.append(wrap);controls[key]=input;}
  const coords=el('details');coords.append(el('summary','Optional: calculate distance from coordinates'));const grid=el('div');grid.className='fields';coords.append(el('p','All four coordinates are required only when using this distance helper.'),grid);
  for(const [key,label,min,max] of [['lat1','Local latitude',-90,90],['lon1','Local longitude',-180,180],['lat2','Remote latitude',-90,90],['lon2','Remote longitude',-180,180]]){const wrap=el('label',label),input=el('input');input.type='number';input.setAttribute('aria-label',label);input.min=min;input.max=max;input.step='any';wrap.append(input);grid.append(wrap);controls[key]=input;}
  const use=el('button','Calculate distance from coordinates');use.type='button';coords.append(use,el('p','Distance only: coordinates do not provide terrain, obstructions, antenna heights or measured coverage. The two ends must also share compatible radio settings.'));form.append(coords);
  const lna=el('details');lna.append(el('summary','Optional LNA / external amplifier planning'),el('p','This builder calculates a passive bidirectional chain. An LNA needs a receive-only path or a suitable transmit bypass; its gain must not be added to transmit power. A cavity filter can reduce unwanted signals but also attenuates the wanted signal. Noise figure, filter placement, overload and measured selectivity determine the actual receive benefit. These are not estimated from gain alone. For an external TX amplifier, enter its actual final output at the radio connector and include downstream losses; do not add its gain twice.'));host.append(lna);
  const error=el('p');error.setAttribute('role','alert');const output=el('div');output.setAttribute('role','status');output.setAttribute('aria-live','polite');host.append(error,output);
  function applyHardware(resetPower=true){const p=globalThis.RadioHardware[controls.hardware.value];hardwareNote.replaceChildren(el('h3',p.name));
    const specs=el('dl');specs.className='builder-hardware-specs';
    for(const [label,value] of [['Radio',p.radio||'Confirm exact model'],['Processor',p.processor||'See exact model datasheet'],['Documented band',p.band?p.band.join('–')+' MHz':'Variant-specific; confirm hardware'],['Published TX capability',p.power===null?'Not provided':p.power+' dBm · not a measured setting'],['Connections',p.connectivity||'See model documentation'],['Positioning',p.position||'Model / accessory dependent'],['Power inputs',p.supply||'See model documentation'],['Antenna connector',p.antennaConnector||'Confirm the installed board revision']]){const item=el('div');item.append(el('dt',label),el('dd',value));specs.append(item);}hardwareNote.append(specs,el('p',p.note));const link=el('a','Published specification');link.href=p.source;link.target='_blank';link.rel='noopener';hardwareNote.append(link);if(p.extraSource){const extra=el('a',' · Radio module specification');extra.href=p.extraSource;extra.target='_blank';extra.rel='noopener';hardwareNote.append(extra);}
    if(resetPower&&p.power!==null)controls.power.value=p.power;
    if(resetPower&&p.gain!==undefined)controls.gain.value=p.gain;
    if(p.sensitivity!==undefined){const [sf,bw]=model.presets[controls.modem.value];controls.sensitivity.value=(p.sensitivity-2.5*(sf-p.sf)+10*Math.log10(bw/p.bw)).toFixed(1);hardwareNote.append(el('p',`Sensitivity derived from the published SF${p.sf} / ${p.bw} kHz point using an approximate SF/bandwidth adjustment. Editable; not a measured sensitivity curve.`));}
    else hardwareNote.append(el('p','Receiver sensitivity is not supplied by this profile: the existing value remains an explicit user assumption.'));
  }
  controls.hardware.addEventListener('change',()=>{applyHardware();update();});
  controls.modem.addEventListener('change',()=>{const p=globalThis.RadioHardware[controls.hardware.value];if(p.sensitivity!==undefined)applyHardware(false);update();});
  function requirements(){
    const custom=controls.cable.value==='custom';controls.rate.required=custom;controls.rate.disabled=!custom;controls.rate.parentElement.firstChild.textContent='Custom coax loss at this frequency (dB / 100 m)'+(custom?' *':' · calculated from cable type');
    const keys=['lat1','lon1','lat2','lon2'],using=keys.some(k=>controls[k].value!=='');for(const key of keys){const input=controls[key];input.required=using;input.parentElement.firstChild.textContent=input.getAttribute('aria-label')+(using?' *':' (optional)');}
  }
  function update(){requirements();if(!form.checkValidity()){error.textContent='Check required fields and input limits: '+[...form.querySelectorAll('input,select')].filter(i=>!i.checkValidity()).map(i=>i.getAttribute('aria-label')).join(', ')+'.';output.replaceChildren();return;}const c={};for(const [key,input] of Object.entries(controls))c[key]=input.type==='number'?(input.disabled?0:input.valueAsNumber):input.value;
    try{const r=model.build(c);error.textContent='';output.replaceChildren();
      document.dispatchEvent(new CustomEvent('mesh:builder',{detail:{distance:c.distance,frequency:c.frequency}}));
      output.append(el('strong',r.margin>=0&&r.returnMargin>=0?'Both directions exceed the assumed receiver thresholds.':r.margin<0&&r.returnMargin<0?'Neither direction exceeds the assumed receiver thresholds.':'One-way risk: only one direction exceeds its assumed receiver threshold.'));
      const profile=globalThis.RadioHardware[c.hardware];
      if(profile.band&&(c.frequency<profile.band[0]||c.frequency>profile.band[1]))output.append(el('strong','Outside this profile’s documented band. RF results below are mathematical only.'));
      if(profile.power!==null&&c.power>profile.power)output.append(el('p','TX input exceeds the profile’s published nominal capability.'));
      const packet=model.airtime(...model.presets[c.modem],40,16);output.append(el('p',`Builder modem: ${c.modem}; illustrative 40-byte packet: ${(packet.seconds*1000).toFixed(1)} ms, 16-symbol preamble / CRC / explicit header.`));
      for(const [label,value] of [['Cable loss',`${r.cableLoss.toFixed(2)} dB (${r.rate.toFixed(2)} dB / 100 m)`],['All local passive losses',`${r.loss.toFixed(2)} dB`],['Power arriving at antenna',`${r.antennaPower.toFixed(2)} dBm / ${r.watts.toPrecision(3)} W`],['EIRP in modeled direction',`${r.eirp.toFixed(2)} dBm`],['Outgoing link',`${r.received.toFixed(1)} dBm at remote receiver; ${r.margin.toFixed(1)} dB margin`],['Return link',`${r.returned.toFixed(1)} dBm at local receiver; ${r.returnMargin.toFixed(1)} dB margin`],['Midpoint first Fresnel radius',`${r.fresnel.toFixed(1)} m (geometry only; no clearance assessment)`]])output.append(el('p',`${label}: ${value}`));
      output.append(el('p','These are calculations, not measured RF output or guaranteed range. Receiver sensitivity must match the chosen modem settings. This builder is independent of the preset comparison above. EIRP is directional equivalent radiated power, not extra watts from the antenna. No compliance or hardware compatibility certification is implied.'));
    }catch(e){error.textContent='Check the builder inputs.';output.replaceChildren();}}
  use.onclick=()=>{try{for(const key of ['lat1','lon1','lat2','lon2'])if(controls[key].value==='')throw new Error();const km=model.distance(...['lat1','lon1','lat2','lon2'].map(k=>controls[k].valueAsNumber));if(km<.001)throw new Error();controls.distance.value=km.toFixed(3);update();}catch(e){error.textContent='Enter four valid coordinates for two locations at least one metre apart.';}};
  form.addEventListener('input',update);form.addEventListener('change',update);form.addEventListener('submit',e=>e.preventDefault());
  const rxFields=el('div');rxFields.className='fields';const rxInputs=[];
  for(const [label,value,max] of [['Loss before LNA (dB)',1,60],['LNA gain (dB)',15,60],['LNA noise figure (dB)',2,30],['Loss after LNA (dB)',1,60],['Receiver noise figure (dB)',6,30]]){const wrap=el('label',label+' *'),input=el('input');input.type='number';input.setAttribute('aria-label',label);input.min=0;input.max=max;input.step=.1;input.value=value;input.required=true;wrap.append(input);rxFields.append(wrap);rxInputs.push(input);}
  const rxResult=el('p');rxResult.setAttribute('role','status');lna.append(rxFields,rxResult,el('p','Separate receive-only thermal-noise model at 290 K. Enter each passive component once, before or after the LNA. Does not predict overload, blocking, intermodulation or a sensitivity improvement in external noise. It does not modify the link-budget results.'));
  function rxUpdate(){try{if(rxInputs.some(i=>!i.checkValidity()))throw new Error();const r=model.receiveChain(...rxInputs.map(i=>i.valueAsNumber));rxResult.textContent=`Estimated cascade noise figure: ${r.noiseFigure.toFixed(2)} dB. Net receive gain before receiver: ${r.gain.toFixed(2)} dB.`;}catch(e){rxResult.textContent='Enter valid receive-chain values.';}}
  lna.append(el('p','* Required within this optional receive-chain model. These values do not change the main link budget.'));
  rxFields.addEventListener('input',rxUpdate);rxUpdate();
  const source=el('a','Cable formulas: Times Microwave datasheets');source.href='https://timesmicrowave.com/cable-families/lmr/standard/';host.append(source);applyHardware();update();
})();
