"""Adapted from owner Downloads capture_streamlit_scroll_stitched_v2.py; frame overlap/clamping algorithm preserved."""
from pathlib import Path
from io import BytesIO
SEL_JS = r"""() => {
  const preferred = ['[data-testid="stMain"]', '[data-testid="stAppViewContainer"]',
                     'section.main', '.main', '[data-testid="stApp"]'];
  const seen = new Set(), options=[];
  for (const selector of preferred) {
    document.querySelectorAll(selector).forEach(el => {
      if (seen.has(el)) return; seen.add(el);
      const r=el.getBoundingClientRect();
      if (r.width < 300 || r.height < 150) return;
      const excess=el.scrollHeight-el.clientHeight;
      options.push({el,selector,excess,rect:r,visibleWidth:r.width});
    });
  }
  const scrollers=options.filter(x=>x.excess>50)
                         .sort((a,b)=> b.excess-a.excess || a.visibleWidth-b.visibleWidth);
  const chosen=scrollers[0];
  if (!chosen) return {mode:'document', docHeight:Math.max(document.body.scrollHeight,document.documentElement.scrollHeight)};
  // A transient reference is deliberately held in this page only.
  window.__jobScreenshotScrollEl=chosen.el;
  return {mode:'container',selector:chosen.selector,total:chosen.el.scrollHeight,
          visible:chosen.el.clientHeight,rect:{x:chosen.rect.x,y:chosen.rect.y,
          width:chosen.rect.width,height:chosen.rect.height},count:scrollers.length};
}"""

SET_SCROLL_JS = r"""target => {
  const el=window.__jobScreenshotScrollEl;
  if (!el) throw new Error('Streamlit scroll element no longer exists');
  el.scrollTop=target;
  return {top:el.scrollTop,total:el.scrollHeight,visible:el.clientHeight};
}"""


def _capture(page, output: Path, *, max_height: int = 45000, settle_ms: int = 150):
    from PIL import Image
    info=page.evaluate(SEL_JS)
    output.parent.mkdir(parents=True, exist_ok=True)
    if info['mode']=='document':
        if info['docHeight']>max_height:
            raise RuntimeError(f'Document is {info["docHeight"]} px tall (limit {max_height}); collapse panels or raise --max-height')
        page.screenshot(path=str(output), full_page=True, animations='disabled',timeout=120000)
        with Image.open(output) as im: size=im.size
        return {'mode':'document','pixels':size,'frames':1}

    total=int(info['total']); rect=info['rect']; clip=page.viewport_size
    if not clip: raise RuntimeError('Missing browser viewport')
    if total>max_height:
        raise RuntimeError(f'Streamlit main pane is {total:,} px tall (limit {max_height:,}). Collapse panels or raise --max-height.')
    x=max(0,int(round(rect['x']))); y=max(0,int(round(rect['y'])))
    right=min(clip['width'],int(round(rect['x']+rect['width'])))
    bottom=min(clip['height'],int(round(rect['y']+rect['height'])))
    width=right-x; height=bottom-y
    if width<250 or height<100:
        raise RuntimeError(f'Main pane clip is too small: {width} x {height}; close DevTools or enlarge browser.')
    # Avoid recording sidebar, Firefox Developer Tools, or screen overlays.
    stitched=Image.new('RGB',(width,total),(255,255,255))
    # Move by one pane at a time; clip top of each *later* screenshot if the
    # browser scrollTop is not a multiple of viewport height.
    target=0; visited=set(); frames=0
    while True:
        sc=page.evaluate(SET_SCROLL_JS,target)
        page.wait_for_timeout(settle_ms)
        actual=int(round(sc['top']))
        if actual in visited: break
        visited.add(actual)
        raw=page.screenshot(full_page=False,animations='disabled',timeout=120000)
        with Image.open(BytesIO(raw)) as screen:
            crop=screen.convert('RGB').crop((x,y,x+width,y+height))
            # Paste only the previously unseen scroll region. This prevents
            # row duplication at a clamped final scroll position.
            new_start=max(0, actual)
            if frames:
                new_start=max(new_start, last_end)
            offset=new_start-actual
            length=min(height-offset,total-new_start)
            if length>0:
                stitched.paste(crop.crop((0,offset,width,offset+length)),(0,new_start))
                last_end=new_start+length
            frames+=1
        if last_end>=total or actual>=total-height: break
        target=min(total-height,last_end)
    # May be on a stale page in a reactive UI; do not call a partial capture a success.
    if last_end < total-2:
        raise RuntimeError(f'Only {last_end:,} of {total:,} rows captured; the page may have rerendered. Try again.')
    stitched.save(output,optimize=True)
    return {'mode':'stitched','pixels':stitched.size,'frames':frames,'selector':info['selector']}

