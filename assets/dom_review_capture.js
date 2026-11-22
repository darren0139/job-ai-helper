// DOM reconstruction, explicitly distinct from browser-pixel capture.
const DOM_CAPTURE_VERSION = 'dom-review-v1';
const LIMITS = {pixels: 70000000, height: 100000, nodes: 25000, views: 12, bytes: 180000000};
const collections = new Map();
const pause = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
function visible(element) {return element.getClientRects().length && getComputedStyle(element).display !== 'none';}
function localResource(value) {
  const url = new URL(value, location.href);
  return ['data:','blob:'].includes(url.protocol) || url.origin === location.origin;
}
function visibleNodes(node, exclude=()=>false) {
  const nodes=[];
  const walker=document.createTreeWalker(node,NodeFilter.SHOW_ELEMENT,{acceptNode(el){
    if(exclude(el))return NodeFilter.FILTER_REJECT;
    const closed=el.closest('details:not([open])');
    if(closed && el!==closed && !closed.querySelector('summary')?.contains(el))return NodeFilter.FILTER_REJECT;
    if(el!==node && !el.closest('svg') && !el.getClientRects().length && getComputedStyle(el).display!=='contents')return NodeFilter.FILTER_REJECT;
    return NodeFilter.FILTER_ACCEPT;
  }});
  if(!exclude(node))nodes.push(node);
  let next;while((next=walker.nextNode())){nodes.push(next);if(nodes.length>LIMITS.nodes)throw new Error('Rendered DOM node limit exceeded.');}
  return nodes;
}
function inspectPanel(node, nodes) {
  const issues=[], warnings=[], nested=[];
  if (nodes.length>LIMITS.nodes) issues.push('DOM node limit exceeded.');
  for (const el of nodes) {
    if (!visible(el)) continue;
    if (['IFRAME','OBJECT','EMBED','VIDEO'].includes(el.tagName)) issues.push('Embedded '+el.tagName.toLowerCase()+' cannot be faithfully reconstructed.');
    if (el.tagName === 'CANVAS') {
      try {el.toDataURL();} catch {issues.push('A canvas is tainted or unreadable.');}
      warnings.push('Canvas pixels represent its currently rendered rows/content, not hidden virtualized rows.');
    }
    if (el.tagName === 'IMG' && (!el.complete || !el.naturalWidth)) issues.push('An image has not loaded.');
    if (el.tagName === 'IMG' && !localResource(el.currentSrc || el.src)) issues.push('Cross-origin image is not captured.');
    const css=getComputedStyle(el);
    if (css.backdropFilter && css.backdropFilter !== 'none') issues.push('Backdrop filtering depends on pixels outside this DOM subtree.');
    for (const match of (css.backgroundImage || '').matchAll(/url\(["']?([^"')]+)["']?\)/g)) {
      if (!localResource(match[1])) issues.push('Cross-origin background image is not captured.');
    }
    if (el!==node && el.scrollHeight>el.clientHeight+3 && ['auto','scroll'].includes(css.overflowY)) nested.push({tag:el.tagName,height:el.scrollHeight,viewport:el.clientHeight});
  }
  return {issues:[...new Set(issues)],warnings:[...new Set(warnings)],nested};
}
function stateOf(doc) {
  return JSON.stringify({url:location.origin+location.pathname, width:innerWidth,
    headings:[...doc.querySelectorAll('[data-testid=stMain] h1,[data-testid=stMain] h2,[data-testid=stMain] h3')].map(e=>e.innerText).slice(0,50),
    expanded:[...doc.querySelectorAll('details')].map(e=>e.open),
    controls:[...doc.querySelectorAll('[data-testid=stSelectbox],[role=tab][aria-selected=true]')].map(e=>e.innerText),
    inputs:[...doc.querySelectorAll('[data-testid=stMain] input')].map(e=>[e.type,e.type==='password'?'':e.value,e.checked])});
}
function aborted(signal){if(signal?.aborted)throw new Error(String(signal.reason||'Capture cancelled.'));}
function cancellable(promise,signal){return new Promise((resolve,reject)=>{const stop=()=>reject(new Error(String(signal.reason||'Capture cancelled.')));signal.addEventListener('abort',stop,{once:true});promise.then(resolve,reject).finally(()=>signal.removeEventListener('abort',stop));});}
async function prepareScroll(node,signal) {
  let frames=0;
  for (let y=0;y<node.scrollHeight;y+=Math.max(1,node.clientHeight-40)) {
    aborted(signal);node.scrollTop=y;await pause();frames++;
  }
  node.scrollTop=0;await pause();return frames;
}
function background(node) {
  for (let el=node;el;el=el.parentElement) {
    const value=getComputedStyle(el).backgroundColor;
    if (value && value !== 'rgba(0, 0, 0, 0)' && value !== 'transparent') return value;
  }
  return getComputedStyle(document.documentElement).getPropertyValue('--st-background-color').trim() || '#ffffff';
}
async function digest(blob) {
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256',await blob.arrayBuffer()))].map(v=>v.toString(16).padStart(2,'0')).join('');
}
function pngChunk(type,bytes) {
  const name=new TextEncoder().encode(type),chunk=new Uint8Array(12+bytes.length),view=new DataView(chunk.buffer);
  view.setUint32(0,bytes.length);chunk.set(name,4);chunk.set(bytes,8);
  view.setUint32(8+bytes.length,captureFiles.crc32(chunk.subarray(4,8+bytes.length)));return chunk;
}
async function renderPanel(node, exclude, signal) {
  const width=node.clientWidth, height=node.scrollHeight, ratio=devicePixelRatio || 1;
  const pixelWidth=Math.ceil(width*ratio),pixelHeight=Math.ceil(height*ratio);
  if (!width || !height || pixelHeight>LIMITS.height || pixelWidth*pixelHeight>LIMITS.pixels) throw new Error('Full-resolution panel exceeds the safe pixel bound; no image was resized or accepted.');
  if(typeof CompressionStream==='undefined')throw new Error('This browser lacks the streaming PNG compressor. No reduced image was substituted.');
  const nodes=visibleNodes(node,exclude),eligible=new Set(nodes);
  const inspection=inspectPanel(node,nodes);inspection.rendered_elements=nodes.length;
  if (inspection.issues.length) throw new Error(inspection.issues.join(' '));
  const svg=await cancellable(domImage.toSvg(node,{width,height,skipAutoScale:true,fetchRequestInit:{signal},
    backgroundColor:background(node),filter:el=>el.nodeType===1?eligible.has(el):eligible.has(el.parentElement),
    style:{width:width+'px',height:height+'px',maxHeight:'none',overflow:'visible',position:'relative',top:'0',left:'0',margin:'0',transform:'none'}}),signal);aborted(signal);
  const xml=new DOMParser().parseFromString(decodeURIComponent(svg.slice(svg.indexOf(',')+1)),'image/svg+xml');
  const svgRoot=xml.documentElement,foreign=svgRoot.querySelector('foreignObject');
  if(!foreign)throw new Error('DOM snapshot has no renderable content.');
  foreign.setAttribute('width',width);foreign.setAttribute('height',height);
  // Repeated Streamlit rows inherit thousands of identical theme declarations.
  // Share byte-identical computed styles, without omitting any CSS property.
  const styleClasses=new Map(),rules=[],prefix='jobai-dom-'+crypto.randomUUID().replaceAll('-','');
  for(const el of xml.querySelectorAll('[style]')) {
    const css=el.getAttribute('style');if(!css)continue;
    let name=styleClasses.get(css);
    if(!name){name=prefix+'-'+styleClasses.size;styleClasses.set(css,name);rules.push('.'+name+'{'+css+'}');}
    el.setAttribute('class',((el.getAttribute('class')||'')+' '+name).trim());el.removeAttribute('style');
  }
  const sheet=xml.createElementNS('http://www.w3.org/1999/xhtml','style');sheet.textContent=rules.join('\n');foreign.prepend(sheet);
  inspection.unique_computed_styles=styleClasses.size;
  inspection.snapshot_characters=svg.length;
  inspection.raster_snapshot_characters=new XMLSerializer().serializeToString(xml).length;
  if(inspection.raster_snapshot_characters>32000000)throw new Error('DOM snapshot exceeds the safe serialization bound; no resized substitute was produced.');

  const sections=[],files=[];
  // Stream one raster section at a time into PNG scanlines. No tall canvas,
  // automatic scaling, or full uncompressed page buffer is required.
  async function* rows() {
    let consumed=0;
    for(const [index,[top,bottom]] of captureFiles.sectionRanges(pixelHeight).entries()) {
      aborted(signal);
      svgRoot.setAttribute('width',pixelWidth);svgRoot.setAttribute('height',bottom-top);
      svgRoot.setAttribute('viewBox',`0 ${top/ratio} ${pixelWidth/ratio} ${(bottom-top)/ratio}`);
      const image=new Image();image.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(new XMLSerializer().serializeToString(xml));await cancellable(image.decode(),signal);
      const canvas=document.createElement('canvas');canvas.width=pixelWidth;canvas.height=bottom-top;
      const context=canvas.getContext('2d');if(!context)throw new Error('Section canvas allocation failed.');
      context.drawImage(image,0,0);
      const blob=await new Promise((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('Section encoding failed.')),'image/png'));
      const name=`sections/${String(index+1).padStart(3,'0')}.png`;
      files.push([name,blob]);sections.push({name,coordinates:[0,top,pixelWidth,bottom],sha256:await digest(blob)});
      const start=Math.max(0,consumed-top),pixels=context.getImageData(0,start,pixelWidth,bottom-top-start).data;
      const stride=pixelWidth*4;
      for(let y=0;y<bottom-top-start;y+=16) {
        const count=Math.min(16,bottom-top-start-y),raw=new Uint8Array(count*(stride+1));
        for(let j=0;j<count;j++)raw.set(pixels.subarray((y+j)*stride,(y+j+1)*stride),j*(stride+1)+1);
        yield raw;
      }
      consumed=bottom;canvas.width=canvas.height=0;
    }
    if(consumed!==pixelHeight)throw new Error('Incomplete vertical coverage.');
  }
  const iterator=rows(),raw=new ReadableStream({async pull(controller){try{const next=await iterator.next();if(next.done)controller.close();else controller.enqueue(next.value);}catch(error){controller.error(error);}}});
  const compressed=new Uint8Array(await new Response(raw.pipeThrough(new CompressionStream('deflate'))).arrayBuffer());
  const header=new Uint8Array(13),view=new DataView(header.buffer);view.setUint32(0,pixelWidth);view.setUint32(4,pixelHeight);header[8]=8;header[9]=6;
  const full=new Blob([new Uint8Array([137,80,78,71,13,10,26,10]),pngChunk('IHDR',header),pngChunk('IDAT',compressed),pngChunk('IEND',new Uint8Array())],{type:'image/png'});
  return {files:[['full.png',full],...files],dimensions:[pixelWidth,pixelHeight],sha256:await digest(full),sections,css_dimensions:[width,height],pixel_ratio:ratio,inspection};
}
async function captureCurrent(doc, host, signal) {
  const main=doc.querySelector('[data-testid=stMain]');
  const sidebar=doc.querySelector('[data-testid=stSidebarContent]');
  if (!main) throw new Error('Streamlit main panel not found in this document.');
  if (doc.querySelector('[data-testid=stStatusWidget] button[title=Stop]')) throw new Error('Wait for the Streamlit rerun to finish.');
  const panels=[['main',main],...sidebar && visible(sidebar)?[['sidebar',sidebar]]:[]];
  const before=stateOf(doc), positions=panels.map(([,node])=>[node,node.scrollTop,node.scrollLeft,node.style.scrollBehavior]);
  const restorePinned=captureFiles.unpin(panels.flatMap(([,node])=>visibleNodes(node)));
  const exclude=el=>el===host || el.matches?.('script,input[type=password]') ||
    (el.matches?.('[data-testid=stExpander]') && /extension pairing|api key|session secret/i.test(el.querySelector('summary')?.innerText||''));
  try {
    await doc.fonts.ready;
    const rendered=[];
    for (const [name,node] of panels) {
      const ratio=devicePixelRatio||1;
      if(node.scrollHeight>45000 || Math.ceil(node.clientWidth*ratio)*Math.ceil(node.scrollHeight*ratio)>LIMITS.pixels)throw new Error('Full-resolution panel exceeds the safe pixel bound; no resized substitute was produced.');
      node.style.scrollBehavior='auto';const frames=await prepareScroll(node,signal);
      const height=node.scrollHeight;const output=await renderPanel(node,exclude,signal);
      if(node.scrollHeight!==height) throw new Error('Page geometry changed during capture; no partial view was accepted.');
      rendered.push({name,scroll_steps:frames,...output});
    }
    if (before!==stateOf(doc) || !host.isConnected) throw new Error('Application state changed during capture; no view was accepted.');
    return {panels:rendered,scroll_positions:positions.map(([node,top,left])=>({panel:node===main?'main':'sidebar',top,left})),scroll_restored:true,state:JSON.parse(before),engine:DOM_CAPTURE_VERSION,mode:'DOM reconstruction — not browser screenshot pixels'};
  } finally {
    restorePinned();
    for(const [node,top,left,behavior] of positions) {node.style.scrollBehavior='auto';node.scrollTop=top;node.scrollLeft=left;node.style.scrollBehavior=behavior;if(node.scrollTop!==top||node.scrollLeft!==left)throw new Error('Original scroll position could not be restored; view rejected.');}
  }
}
async function reviewZip(session) {
  const files=[],captures=[];
  for (const [index,view] of session.views.entries()) {
    const directory=String(index+1).padStart(2,'0')+'_'+view.name.replace(/[^a-z0-9_-]+/gi,'_').slice(0,60);
    const panels=[];
    for (const panel of view.panels) {
      const {files:images,...meta}=panel;panels.push(meta);
      for (const [name,blob] of images) files.push(['JobAIHelper_UI_Review/'+directory+'/'+panel.name+'/'+name,blob]);
    }
    captures.push({id:view.id,name:view.name,sequence:index+1,directory,panels,state:view.state,engine:view.engine,mode:view.mode,scroll_positions:view.scroll_positions,scroll_restored:view.scroll_restored});
  }
  files.push(['JobAIHelper_UI_Review/manifest.json',new Blob([JSON.stringify({schema_version:1,captures,errors:session.errors},null,2)])]);
  files.push(['JobAIHelper_UI_Review/README.md',new Blob(['Current-page DOM reconstruction, not exact browser pixels. Main and sidebar are separate full-resolution originals with numbered full-width sections. No downsampling. Expanded content stays expanded; virtualized and internally clipped tables contain only their rendered content. Manifest lists geometry, limitations and hashes. Canvas, embedded content, unsupported CSS and page/memory changes may cause a visible failure. Images stay browser-local. Review private text before sharing. No database or résumé document files are included.'])]);
  return captureFiles.zipFiles(files);
}
export default function(component) {
  const root=component.parentElement,doc=root.ownerDocument,host=root.host || root;
  const session=collections.get(component.key)||{views:[],errors:[],busy:false};collections.set(component.key,session);
  const status=root.querySelector('#review-status'),capture=root.querySelector('#review-capture'),exportButton=root.querySelector('#review-export');
  const list=root.querySelector('#review-views'),download=root.querySelector('#review-download');
  const display=()=>{list.replaceChildren();for (const v of session.views) {const li=doc.createElement('li');li.textContent=v.name+' · '+v.panels.map(p=>p.name+' '+p.dimensions.join(' × ')).join(' / ');list.append(li);}exportButton.disabled=!session.views.length||session.busy;};display();
  capture.onclick=async()=>{
    if(session.busy)return;session.busy=true;capture.disabled=true;status.textContent='Capturing this page automatically…';
    const name=root.querySelector('#review-name').value.trim().slice(0,120)||'Current page';
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort('Capture exceeded 120 seconds; no partial view accepted.'),120000);
    const cancel=root.querySelector('#review-cancel');if(cancel){cancel.disabled=false;cancel.onclick=()=>controller.abort('Capture cancelled; no partial view accepted.');}
    try {
      if(session.views.length>=LIMITS.views)throw new Error('Collection full; export before refreshing.');
      const view=await captureCurrent(doc,host,controller.signal);
      const cost=v=>v.panels.reduce((n,p)=>n+p.files.reduce((s,f)=>s+f[1].size,0),0);
      if(session.views.reduce((n,v)=>n+cost(v),0)+cost(view)>LIMITS.bytes)throw new Error('Collection byte limit exceeded.');
      session.views.push({...view,id:crypto.randomUUID(),name});
      status.textContent='Captured this page. Original scroll positions restored. DOM-rendered images: review their fidelity before sharing.';
    }catch(e){session.errors.push({name,error:String(e.message)});status.textContent='Capture failed: '+e.message;}
    finally{clearTimeout(timer);if(cancel)cancel.disabled=true;session.busy=false;capture.disabled=false;display();}
  };
  exportButton.onclick=async()=>{try{exportButton.disabled=true;const zip=await reviewZip(session);const link=doc.createElement('a');link.href=URL.createObjectURL(zip);link.download='JobAIHelper_Current_Page_DOM_Review.zip';link.textContent='Download current-page review ZIP';download.replaceChildren(link);
    const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(zip);});
    if(zip.size>64000000)throw new Error('ZIP exceeds the local-app transfer bound; use the browser-local download link.');
    component.setTriggerValue('export_zip',encoded);}catch(e){status.textContent='ZIP export failed: '+e.message;}finally{display();}};
}
