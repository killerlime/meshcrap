/* Supplied terrain only. No coordinate disclosure or automatic elevation query. */
(() => {
 'use strict';
 const host=document.getElementById('node-builder'),el=(tag,text)=>{const e=document.createElement(tag);if(text)e.textContent=text;return e;};
 const box=el('details'),title=el('summary','Antenna height and path clearance');box.append(title);host.append(box);
 const fields=el('div');fields.className='fields';box.append(fields);const inputs=[];
 for(const [name,value,min,max] of [['Local antenna height above ground (m)',10,0,1000],['Remote antenna height above ground (m)',10,0,1000],['Effective Earth radius factor (k)',1.333333,.5,5]]){
  const wrap=el('label',name),input=el('input');input.type='number';input.min=min;input.max=max;input.step='any';input.value=value;input.required=true;input.setAttribute('aria-label',name);wrap.append(input);fields.append(wrap);inputs.push(input);
 }
 const label=el('label','Optional terrain: path fraction, elevation metres (one point per line)');const terrain=el('textarea');terrain.rows=4;terrain.placeholder='0, 200\n0.5, 230\n1, 210';label.append(terrain);box.append(label);
 box.append(el('p','Blank means an illustrative level surface, not real terrain. Enter endpoints 0 and 1 plus intermediate elevations in increasing path order, using one consistent vertical datum. Coordinates provide distance only. Buildings, vegetation and fine terrain may be missing.'));
 const status=el('p');status.setAttribute('role','status');box.append(status);
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 640 240');svg.setAttribute('role','img');svg.setAttribute('aria-label','Supplied terrain and Earth curvature versus radio path and 60 percent Fresnel clearance');box.append(svg);
 box.append(el('p','Solid green: straight radio path. Dashed amber: lower 60% Fresnel boundary. Grey: supplied ground plus effective Earth curvature. Clearance is a screening estimate, not predicted delivery or a ducting forecast. k = 4/3 is an assumed reference atmosphere; no current weather is inferred. Profiles are sampled at 101 points; narrow obstructions can be missed.'));
 let current=null;
 function render(){if(!current)return;svg.replaceChildren();try{
  if(inputs.some(i=>!i.checkValidity()))throw new Error('Enter valid antenna heights and k.');
  if(terrain.value.length>30000)throw new Error('Terrain profile is too large.');
  const supplied=terrain.value.trim(),rows=supplied?supplied.split(/\r?\n/).map(line=>line.split(',').map(v=>v.trim()===''?NaN:Number(v))):[[0,0],[1,0]];
  const r=globalThis.MeshSimulator.pathProfile(current.distance,current.frequency,...inputs.map(i=>i.valueAsNumber),rows);
  const values=r.points.flatMap(p=>[p.ground,p.ray,p.ray-.6*p.radius]),low=Math.min(...values)-5,high=Math.max(...values)+5;
  const y=v=>220-(v-low)/(high-low)*200;
  for(const [key,color,dashed] of [['ground','#a5b5b4',false],['ray','#86dcaa',false],['fresnel','#ffbd80',true]]){
   const path=document.createElementNS(ns,'path');path.setAttribute('d',r.points.map((p,i)=>`${i?'L':'M'}${20+p.fraction*600},${y(key==='fresnel'?p.ray-.6*p.radius:p[key])}`).join(' '));path.setAttribute('fill','none');path.style.stroke=color;path.style.strokeWidth='3';if(dashed)path.style.strokeDasharray='7 6';svg.append(path);
  }
  status.textContent=`${supplied?'User-supplied terrain':'Illustrative level surface'} · ${current.distance.toFixed(3)} km. Minimum sampled 60% Fresnel clearance: ${r.minimumClearance.toFixed(1)} m. ${r.minimumClearance<0?'An obstruction enters this modeled clearance zone.':'Sampled points clear this modeled zone.'}`;
 }catch(e){status.textContent='Profile unavailable: check distance (up to 500 km), heights, k, and ordered fraction/elevation pairs.';}}
 document.addEventListener('mesh:builder',event=>{if(!current)host.append(box);current=event.detail;render();});box.addEventListener('input',render);
})();
