/* Original educational model. References and limitations: docs/MESH-SIMULATOR.md. */
(function(root) {
  'use strict';
  const presets = {
    'Short Turbo': [7,500,5], 'Short Fast': [7,250,5], 'Short Slow': [8,250,5],
    'Medium Fast': [9,250,5], 'Medium Slow': [10,250,5], 'Long Turbo': [11,500,8],
    'Long Fast': [11,250,5], 'Long Moderate': [11,125,8], 'Long Slow (deprecated)': [12,125,8]
  };
  function number(value,min,max,name,integer=false) {
    if(typeof value!=='number'||!Number.isFinite(value)||value<min||value>max||(integer&&!Number.isInteger(value))) throw new RangeError(name);
    return value;
  }
  function airtime(sf,bw,cr,bytes,preamble=16) {
    number(sf,7,12,'SF',true); number(bw,125,500,'bandwidth'); number(cr,5,8,'coding rate',true);
    number(bytes,1,255,'PHY payload',true); number(preamble,6,65535,'preamble',true);
    const symbol=2**sf/(bw*1000), de=symbol>=0.016?1:0;
    // Explicit header, payload CRC enabled, classic SF7–12 LoRa packet formula.
    const payload=8+Math.max(Math.ceil((8*bytes-4*sf+28+16)/(4*(sf-2*de)))*cr,0);
    return {seconds:(preamble+4.25+payload)*symbol,symbolMs:symbol*1000,de};
  }
  function simulate(c) {
    if(!Object.hasOwn(presets,c.before)||!Object.hasOwn(presets,c.after))throw new RangeError('preset');
    for(const [key,min,max,int] of [['frequencyBefore',100,2500],['frequencyAfter',100,2500],['margin',-30,40],['nodes',2,200,true],['messages',0,60],['copies',1,8,true],['bytes',1,255,true],['preamble',6,65535,true]])number(c[key],min,max,key,int);
    if(!['one','local','all'].includes(c.scope))throw new RangeError('scope');
    const a=presets[c.before],b=presets[c.after],oldAir=airtime(...a,c.bytes,c.preamble),newAir=airtime(...b,c.bytes,c.preamble);
    // Approximate thermal-noise / typical SF threshold delta, not board sensitivity.
    const sensitivityGain=2.5*(b[0]-a[0])+10*Math.log10(a[1]/b[1]);
    const frequencyLoss=20*Math.log10(c.frequencyAfter/c.frequencyBefore);
    const changed=c.before!==c.after||c.frequencyBefore!==c.frequencyAfter;
    const split=changed&&c.scope!=='all';
    const load=t=>100*c.nodes*c.messages*c.copies*t/60;
    return {oldAir,newAir,sensitivityGain,frequencyLoss,margin:c.margin+sensitivityGain-frequencyLoss,
      oldLoad:load(oldAir.seconds),newLoad:load(newAir.seconds),split,
      localCompatible:!changed||c.scope!=='one',regionalCompatible:!split};
  }
  function build(c) {
    for(const [key,min,max] of [['frequency',100,2500],['power',-30,40],['gain',-20,40],['length',0,1000],['rate',0,200],['connectors',0,30],['filter',0,30],['other',0,30],['remoteGain',-20,40],['remoteLoss',0,60],['remotePower',-30,40],['sensitivity',-160,-40],['remoteSensitivity',-160,-40],['extraLoss',0,150],['distance',0.001,20000]])number(c[key],min,max,key);
    if(!['custom','LMR-400','LMR-240'].includes(c.cable))throw new RangeError('cable');
    const rate=c.cable==='custom'?c.rate:((c.cable==='LMR-400'?0.122290:0.242080)*Math.sqrt(c.frequency)+(c.cable==='LMR-400'?0.000260:0.000330)*c.frequency)/30.48*100;
    const cableLoss=rate*c.length/100,loss=cableLoss+c.connectors+c.filter+c.other;
    const antennaPower=c.power-loss,eirp=antennaPower+c.gain;
    const pathLoss=32.44+20*Math.log10(c.frequency)+20*Math.log10(c.distance)+c.extraLoss;
    const received=eirp-pathLoss+c.remoteGain-c.remoteLoss;
    const returned=c.remotePower-c.remoteLoss+c.remoteGain-pathLoss+c.gain-loss;
    return {rate,cableLoss,loss,antennaPower,eirp,watts:10**((antennaPower-30)/10),pathLoss,received,returned,margin:received-c.remoteSensitivity,returnMargin:returned-c.sensitivity,
      fresnel:Math.sqrt((299792458/(c.frequency*1e6))*c.distance*1000/4)};
  }
  function distance(lat1,lon1,lat2,lon2) {
    number(lat1,-90,90,'latitude');number(lat2,-90,90,'latitude');number(lon1,-180,180,'longitude');number(lon2,-180,180,'longitude');
    const rad=Math.PI/180,a=Math.sin((lat2-lat1)*rad/2)**2+Math.cos(lat1*rad)*Math.cos(lat2*rad)*Math.sin((lon2-lon1)*rad/2)**2;
    return 6371*2*Math.atan2(Math.sqrt(Math.min(1,a)),Math.sqrt(Math.max(0,1-a)));
  }
  function receiveChain(lossBefore,gain,noiseFigure,lossAfter,receiverNF) {
    for(const [v,min,max] of [[lossBefore,0,60],[gain,0,60],[noiseFigure,0,30],[lossAfter,0,60],[receiverNF,0,30]])number(v,min,max,'receive chain');
    const lb=10**(lossBefore/10),g=10**(gain/10),f=10**(noiseFigure/10),la=10**(lossAfter/10),fr=10**(receiverNF/10);
    // Friis cascade: passive loss -> LNA -> passive loss -> receiver, 290 K.
    const factor=lb+(f-1)*lb+(la-1)*lb/g+(fr-1)*lb*la/g;
    return {noiseFigure:10*Math.log10(factor),gain:gain-lossBefore-lossAfter};
  }
  function pathProfile(km,frequency,startHeight,endHeight,k=4/3,terrain=[[0,0],[1,0]]) {
    number(km,.001,500,'profile distance');number(frequency,100,2500,'frequency');
    number(startHeight,0,1000,'antenna height');number(endHeight,0,1000,'antenna height');number(k,.5,5,'effective Earth factor');
    if(!Array.isArray(terrain)||terrain.length<2||terrain.length>501)throw new RangeError('terrain');
    terrain.forEach((p,i)=>{if(!Array.isArray(p)||p.length!==2)throw new RangeError('terrain');number(p[0],0,1,'path fraction');number(p[1],-500,9000,'terrain elevation');if(i&&p[0]<=terrain[i-1][0])throw new RangeError('terrain order');});
    if(terrain[0][0]!==0||terrain.at(-1)[0]!==1)throw new RangeError('terrain endpoints');
    const distance=km*1000,lambda=299792458/(frequency*1e6),a=terrain[0][1]+startHeight,b=terrain.at(-1)[1]+endHeight;
    const points=[];let segment=0;
    for(let i=0;i<=100;i++){
      const f=i/100;while(segment<terrain.length-2&&terrain[segment+1][0]<f)segment++;
      const [f0,z0]=terrain[segment],[f1,z1]=terrain[segment+1];
      const ground=z0+(z1-z0)*(f-f0)/(f1-f0)+distance**2*f*(1-f)/(2*k*6371000);
      const ray=a+(b-a)*f,radius=Math.sqrt(lambda*distance*f*(1-f));
      points.push({fraction:f,ground,ray,radius,clearance:ray-ground-.6*radius});
    }
    return {points,minimumClearance:Math.min(...points.map(p=>p.clearance)),k};
  }
  const api={presets,airtime,simulate,build,distance,receiveChain,pathProfile};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.MeshSimulator=api;
})(globalThis);
