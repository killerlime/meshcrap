/* Explicit user request only; endpoints are never inferred from private nodes. */
(() => {
 const host=document.getElementById('dashboard-panel-whatif');if(!host)return;
 const el=(tag,text)=>{const e=document.createElement(tag);if(text)e.textContent=text;return e;};
 const box=el('details');box.append(el('summary','Real terrain profile · HeyWhatsThat'));
 box.append(el('p','Enter two locations to see the terrain between them. Generate sends these coordinates and antenna heights to HeyWhatsThat. No node names, messages or radio data are included. On secured installations, unlock dashboard controls before generating a profile.'));
 const form=el('form'),fields=el('div');fields.style.cssText='display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px';form.append(fields);const inputs={};
 for(const [key,label,min,max,value] of [['lat1','Start latitude',-54,60,''],['lon1','Start longitude',-180,180,''],['lat2','End latitude',-54,60,''],['lon2','End longitude',-180,180,''],['height1','Start antenna height above ground (m)',0,1000,10],['height2','End antenna height above ground (m)',0,1000,10]]){
  const wrap=el('label',label),input=el('input');input.type='number';input.min=min;input.max=max;input.step='any';input.required=true;input.value=value;input.setAttribute('aria-label',label);input.style.width='100%';wrap.append(input);fields.append(wrap);inputs[key]=input;
 }
 const button=el('button','Generate terrain profile');button.type='submit';form.append(button);box.append(form);
 const status=el('p');status.setAttribute('role','status');const result=el('div');box.append(status,result);
 box.append(el('p','Terrain reference only: Earth curvature is included, but this image does not apply the simulator’s k factor, Fresnel zone, vegetation, buildings or live weather. It does not change the RF calculations.'));
 const credit=el('p','Profile image © Michael Kosowsky. All rights reserved. Used under the published low-volume noncommercial API permission. '),link=el('a','HeyWhatsThat API / terms');link.href='https://www.heywhatsthat.com/techfaq.html';link.target='_blank';link.rel='noopener noreferrer';credit.append(link);box.append(credit);
 const usage=el('p');box.append(usage);host.insertBefore(box,host.querySelector('iframe'));let objectUrl=null;
 async function counts(){try{const r=await fetch('/api/heywhatsthat/usage',{cache:'no-store'});if(!r.ok)throw Error();const c=await r.json();usage.textContent=c.enabled?`Last 7 UTC days: ${c.windows['7'].attempts} upstream attempts, ${c.windows['7'].successes} successful profiles, ${c.windows['7'].cache_hits} cache hits. Last 30 UTC days: ${c.windows['30'].attempts} attempts. Local experiment cap: 20/day; not a provider quota. Contact HeyWhatsThat before regular production use.`:'HeyWhatsThat is disabled in this installation.';}catch{usage.textContent='Usage counts unavailable.';}}
 box.addEventListener('toggle',()=>{if(box.open)counts();});
 form.addEventListener('submit',async event=>{event.preventDefault();if(!form.reportValidity())return;button.disabled=true;status.textContent='Requesting terrain…';result.replaceChildren();if(objectUrl){URL.revokeObjectURL(objectUrl);objectUrl=null;}
 try{const body=Object.fromEntries(Object.entries(inputs).map(([k,v])=>[k,v.valueAsNumber]));const response=await fetch('/api/heywhatsthat/profile',{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'meshcrap-terrain'},body:JSON.stringify(body)});
 if(!response.ok){const problem=await response.json();throw Error(problem.error||'Profile unavailable.');}
 objectUrl=URL.createObjectURL(await response.blob());const image=el('img');image.alt='HeyWhatsThat terrain cross-section between the entered endpoints, with antenna sightline and Earth curvature';image.style.cssText='width:100%;height:auto;background:white';image.src=objectUrl;result.append(image);status.textContent=response.headers.get('X-Terrain-Cache')==='hit'?'Loaded saved profile; no provider call.':'Terrain profile received. Red line joins the antenna endpoints.';
 }catch(error){status.textContent=error.message||'Profile unavailable.';}finally{button.disabled=false;counts();}});
})();
