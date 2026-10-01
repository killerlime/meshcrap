/* Shared local-only CSV downloads. Preserve numeric readings and quote text safely. */
(() => {
 function cell(value){
  if(value===null||value===undefined)return '';
  let text=String(value);
  // Node names and messages are untrusted spreadsheet text, not formulas.
  if(typeof value==='string' && /^[\s\uFEFF]*[=+@-]/u.test(text))text="'"+text;
  if(typeof value==='string' && /^[\t\r\n]/u.test(text))text="'"+text;
  return '"'+text.replace(/"/g,'""')+'"';
 }
 function serialize(headers,rows){return '\uFEFF'+[headers,...rows].map(row=>row.map(cell).join(',')).join('\r\n')+'\r\n';}
 function download(name,headers,rows){
  const blob=new Blob([serialize(headers,rows)],{type:'text/csv;charset=utf-8;'});
  const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name.replace(/[^a-zA-Z0-9_.-]/g,'_')+'-'+new Date().toISOString().replace(/[:.]/g,'-')+'.csv';
  document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }
 window.ConsoleCSV={serialize,download};
})();
