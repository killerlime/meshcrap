/* Bound read requests. Never retry or replay a message, setting, or radio action. */
(() => {
 const originalFetch=window.fetch.bind(window);
 window.fetch=async function(input, options={}){
   const url=new URL(input instanceof Request ? input.url : input, location.href);
   const method=String(options.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
   if(url.origin!==location.origin || !url.pathname.startsWith('/api/') || method!=='GET')return originalFetch(input,options);
   const controller=new AbortController();
   const callerSignal=options.signal || (input instanceof Request ? input.signal : null);
   const cancel=()=>controller.abort();
   if(callerSignal?.aborted)cancel();else callerSignal?.addEventListener('abort',cancel,{once:true});
   const timer=setTimeout(cancel,15000);
   try{
     const response=await originalFetch(input,{...options,signal:controller.signal,cache:'no-store'});
     if(!response.ok)throw new Error(`Dashboard read unavailable (${response.status})`);
     return response;
   }finally{clearTimeout(timer);callerSignal?.removeEventListener('abort',cancel);}
 };
})();
