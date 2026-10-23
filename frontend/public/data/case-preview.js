// ADR-0001: only the visible board refreshes; a failed refresh keeps the last image.
export function previewUrl(value, demo=false) {
  if (typeof value !== 'string' || /[\\\x00-\x20]/.test(value)) return null;
  if (/^\/api\/case-finding\/images\/[A-Za-z0-9_-]+(?:\?[A-Za-z0-9_%=&.-]+)?$/.test(value)) return value;
  if (demo && /^\/demo\/case-board-v[12]\.svg$/.test(value)) return value;
  return null;
}

export function preloadPreview(url, signal) {
  return new Promise((resolve,reject)=>{
    const image=new Image();
    const cleanup=()=>{ image.onload=null; image.onerror=null; signal?.removeEventListener('abort',abort); };
    const abort=()=>{ cleanup(); image.src=''; reject(new DOMException('Cancelled','AbortError')); };
    image.onload=()=>{ cleanup(); image.naturalWidth && image.naturalHeight ? resolve({width:image.naturalWidth,height:image.naturalHeight}) : reject(new Error('图片无效')); };
    image.onerror=()=>{ cleanup(); reject(new Error('图片暂时无法显示')); };
    if(signal?.aborted) return abort();
    signal?.addEventListener('abort',abort,{once:true}); image.src=url;
  });
}

export function createPreviewController({fetchPreview,loadImage=preloadPreview,onState,demo=false,
  interval=60000,setTimer=setTimeout,clearTimer=clearTimeout}) {
  let selected=null,visible=true,disposed=false,generation=0,timer=null,pending=null,failures=0,blocked=false;
  const cache=new Map();
  const notify=extra=>onState({record:selected,snapshot:cache.get(selected?.id)||null,...extra});
  const cancel=()=>{ generation++; clearTimer(timer);timer=null;pending?.abort();pending=null; };
  const schedule=()=>{
    if(!disposed && visible && selected && fetchPreview && !blocked) timer=setTimer(()=>run(),Math.min(interval*2**failures,300000));
  };
  async function run() {
    if(disposed || !visible || !selected || pending) return;
    clearTimer(timer); timer=null;
    const record=selected,token=generation,abort=new AbortController(); pending=abort;
    const timeout=setTimer(()=>abort.abort(),30000);
    notify({phase:'loading'});
    try {
      // A cached service snapshot can be painted before remote fetching finishes.
      if(!cache.has(record.id) && record.preview) {
        const url=previewUrl(record.preview.image_url,demo);
        if(url) {
          try {
            const dimensions=await loadImage(url,abort.signal);
            if(token!==generation || disposed) return;
            cache.set(record.id,{...record.preview,...dimensions,image_url:url});notify({phase:'loading'});
          } catch(error) { if(abort.signal.aborted) throw error; }
        }
      }
      if(!fetchPreview) { notify({phase:'unavailable'});return; }
      const result=await fetchPreview(record,abort.signal);
      const url=previewUrl(result.image_url,demo);
      if(result.version_id!==record.id || !url || !Number.isFinite(Date.parse(result.fetched_at))) throw new Error('画板预览响应无效');
      const dimensions=await loadImage(url,abort.signal);
      if(token!==generation || disposed || !visible) return;
      cache.set(record.id,{...result,...dimensions,image_url:url});failures=0;blocked=false;notify({phase:'ready'});
    } catch(error) {
      if(token!==generation || disposed || !visible) return;
      failures++;blocked=['AUTH_REQUIRED','FORBIDDEN'].includes(error.code);
      if(error.code==='BOARD_NOT_READY') blocked=true;
      notify({phase:error.code==='BOARD_NOT_READY'?'unbound':blocked?'blocked':'error',message:blocked?'飞书登录或访问权限需要处理，自动刷新已暂停。':'暂时无法刷新，稍后自动重试。',code:error.code});
    } finally {
      clearTimer(timeout);
      if(token===generation) { pending=null;schedule(); }
    }
  }
  return {
    select(record){ cancel();selected=record;failures=0;blocked=false;notify({phase:record?'loading':'empty'});run(); },
    refresh(){ if(pending || disposed) return;blocked=false;failures=0;return run(); },
    setVisible(value){ if(value===visible) return;visible=value;cancel();if(value && !blocked) run(); },
    destroy(){ disposed=true;cancel();cache.clear(); }
  };
}

// Read-only local service contract. Enabled only when the service advertises it.
export function previewTransport(data, projectId, fetcher=fetch) {
  if(data.meta?.demo) return async(record,signal)=>{
    if(signal.aborted) throw new DOMException('Cancelled','AbortError');
    return {...record.preview,version_id:record.id,fetched_at:new Date().toISOString()};
  };
  if(data.meta?.case_finding_preview !== true) return null;
  return async(record,signal)=>{
    if(!record.board_token) throw Object.assign(new Error('画板尚未关联'),{code:'BOARD_NOT_READY'});
    const query=new URLSearchParams({project:projectId,version:record.id});
    const response=await fetcher('/api/case-finding/preview?'+query,{signal,cache:'no-store'});
    if(!response.ok) {
      const error=new Error('画板预览不可用');
      error.code=response.status===401?'AUTH_REQUIRED':response.status===403?'FORBIDDEN':'UNAVAILABLE';throw error;
    }
    return response.json();
  };
}
