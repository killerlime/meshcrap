/* Correlation is exploratory, not evidence of causation or radio reachability. */
(() => {
 const pearson=(pairs,min=12)=>{
  const good=pairs.filter(p=>p.length===2&&p.every(v=>typeof v==='number'&&Number.isFinite(v)));
  const n=good.length;if(n<min)return {n,r:null};
  const mx=good.reduce((s,p)=>s+p[0],0)/n,my=good.reduce((s,p)=>s+p[1],0)/n;
  let xy=0,xx=0,yy=0;for(const [x,y] of good){const a=x-mx,b=y-my;xy+=a*b;xx+=a*a;yy+=b*b;}
  return {n,r:xx>0&&yy>0?Math.max(-1,Math.min(1,xy/Math.sqrt(xx*yy))):null};
 };
 const nodeIntensity=row=>{
  const rate=row.packets_per_observed_hour,nodes=row.unique_nodes;
  return typeof rate==='number'&&Number.isFinite(rate)&&rate>=0&&typeof nodes==='number'&&Number.isFinite(nodes)&&nodes>0?rate/nodes:null;
 };
 window.RFGraphMath={pearson,nodeIntensity};
})();
