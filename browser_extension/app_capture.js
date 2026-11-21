/* Capture runs in the existing tab. Frames and object URLs stay in this browser. */
(() => {
  const PANEL = '#job-ai-helper-capture';
  const MAX_SCROLL_HEIGHT = 30000;
  const MAX_CHUNK_PIXELS = 16_000_000;
  const MAX_TOTAL_PIXELS = 80_000_000;
  const MIN_FRAME_INTERVAL_MS = 575;

  function nextSlice(scrollTop, viewportHeight, total, captured) {
    const from = Math.max(scrollTop, captured);
    const to = Math.min(scrollTop + viewportHeight, total);
    if (scrollTop > captured || to <= from) throw new Error('The main panel changed while scrolling.');
    return { offset: from - scrollTop, height: to - from, end: to };
  }

  async function restoreAfterCapture(main, header, panel, work) {
    const top = main.scrollTop;
    const left = main.scrollLeft;
    const behavior = main.style.scrollBehavior;
    const panelVisibility = panel.style.visibility;
    const headerVisibility = header?.style.visibility;
    try {
      main.style.scrollBehavior = 'auto';
      panel.style.visibility = 'hidden';
      if (header) header.style.visibility = 'hidden';
      return await work();
    } finally {
      main.scrollTop = top;
      main.scrollLeft = left;
      main.style.scrollBehavior = behavior;
      panel.style.visibility = panelVisibility;
      if (header) header.style.visibility = headerVisibility;
    }
  }

  function viewport(main) {
    const rect = main.getBoundingClientRect();
    return {
      x: Math.max(0, Math.round(rect.left)),
      y: Math.max(0, Math.round(rect.top)),
      right: Math.min(innerWidth, Math.round(rect.left + main.clientWidth)),
      bottom: Math.min(innerHeight, Math.round(rect.top + main.clientHeight)),
      windowWidth: innerWidth, windowHeight: innerHeight,
    };
  }

  function canvasFor(width, height) {
    if (width <= 0 || height <= 0 || width * height > MAX_CHUNK_PIXELS) {
      throw new Error('Capture area exceeded the PNG size limit. Reduce the browser zoom or window size.');
    }
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    return canvas;
  }

  function png(canvas) {
    return new Promise((resolve, reject) => canvas.toBlob((blob) => {
      canvas.width = 0;
      canvas.height = 0;
      if (blob) resolve(blob);
      else reject(new Error('The browser could not encode this PNG.'));
    }, 'image/png'));
  }

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error('The browser returned an unreadable image.'));
      image.src = url;
    });
  }

  function createFrameReader(runtime, panel) {
    let requestedAt = 0;
    return async () => {
      const delay = Math.max(80, MIN_FRAME_INTERVAL_MS - (performance.now() - requestedAt));
      await new Promise((resolve) => setTimeout(resolve, delay));
      if (!panel.isConnected || document.visibilityState !== 'visible') {
        throw new Error('Keep this Job AI Helper tab active during Capture.');
      }
      requestedAt = performance.now();
      const response = await runtime.sendMessage({ type: 'job-ai-helper:app-capture-frame' });
      if (!response?.image) {
        const reason = response?.error || 'Capture helper is unavailable.';
        throw new Error(reason + ' Open the Job AI Helper toolbar extension on this tab and try again.');
      }
      const image = await loadImage(response.image);
      return {
        image,
        scaleX: image.naturalWidth / innerWidth,
        scaleY: image.naturalHeight / innerHeight,
      };
    };
  }

  async function visiblePng(main, readFrame, includeSidebar) {
    const bounds = viewport(main);
    const { image, scaleX, scaleY } = await readFrame();
    if (innerWidth !== bounds.windowWidth || innerHeight !== bounds.windowHeight) {
      throw new Error('The viewport changed during Capture.');
    }
    const x = includeSidebar ? 0 : Math.round(bounds.x * scaleX);
    const y = includeSidebar ? 0 : Math.round(bounds.y * scaleY);
    const right = includeSidebar ? image.naturalWidth : Math.round(bounds.right * scaleX);
    const bottom = includeSidebar ? image.naturalHeight : Math.round(bounds.bottom * scaleY);
    const canvas = canvasFor(right - x, bottom - y);
    canvas.getContext('2d').drawImage(image, x, y, canvas.width, canvas.height,
      0, 0, canvas.width, canvas.height);
    return [await png(canvas)];
  }

  async function fullPngs(main, readFrame, includeSidebar) {
    const bounds = viewport(main);
    const height = bounds.bottom - bounds.y;
    const total = main.scrollHeight;
    if (height <= 0 || total > MAX_SCROLL_HEIGHT || height !== main.clientHeight) {
      throw new Error('The full main panel exceeds the capture limit or is partially offscreen. Try visible area.');
    }
    if (main.scrollLeft !== 0 || main.scrollWidth > main.clientWidth + 1) {
      throw new Error('Full capture requires the main panel to fit horizontally in the browser.');
    }
    let captured = 0;
    let scale;
    let chunk;
    let used = 0;
    let chunkHeight;
    let part = 0;
    const images = [];
    while (captured < total) {
      main.scrollTop = Math.min(captured, total - height);
      const top = Math.round(main.scrollTop);
      const slice = nextSlice(top, height, total, captured);
      const frame = await readFrame();
      const next = viewport(main);
      if (main.scrollHeight !== total || Math.round(main.scrollTop) !== top ||
          Object.keys(bounds).some((key) => bounds[key] !== next[key])) {
        throw new Error('The page layout changed during Capture. Try again after the page settles.');
      }
      scale ??= [frame.scaleX, frame.scaleY];
      if (frame.scaleX !== scale[0] || frame.scaleY !== scale[1]) {
        throw new Error('Browser zoom changed during Capture.');
      }
      const [sx, sy] = scale;
      const left = Math.round(bounds.x * sx);
      const right = Math.round(bounds.right * sx);
      const width = includeSidebar ? right : right - left;
      const totalPixels = Math.round(total * sy);
      if (width * totalPixels > MAX_TOTAL_PIXELS) {
        throw new Error('This page exceeds the full Capture pixel limit.');
      }
      chunkHeight ??= Math.min(8192, Math.floor(MAX_CHUNK_PIXELS / width));
      let sourceY = Math.round((bounds.y + slice.offset) * sy);
      let remaining = Math.round(slice.end * sy) - Math.round(captured * sy);
      while (remaining > 0) {
        if (!chunk) {
          chunk = canvasFor(width, Math.min(chunkHeight, totalPixels - part * chunkHeight));
          const context = chunk.getContext('2d');
          if (includeSidebar && left > 0) {
            context.fillStyle = getComputedStyle(main).backgroundColor;
            context.fillRect(0, 0, left, chunk.height);
          }
          used = 0;
        }
        const size = Math.min(remaining, chunk.height - used);
        const context = chunk.getContext('2d');
        // The visible sidebar appears once, beside the opening viewport.
        if (includeSidebar && captured === 0 && part === 0 && left > 0) {
          context.drawImage(frame.image, 0, sourceY, left, size, 0, used, left, size);
        }
        context.drawImage(frame.image, left, sourceY, right - left, size,
          includeSidebar ? left : 0, used, right - left, size);
        used += size;
        remaining -= size;
        sourceY += size;
        if (used === chunk.height) {
          images.push(await png(chunk));
          chunk = null;
          part += 1;
        }
      }
      captured = slice.end;
    }
    if (chunk || !images.length) throw new Error('Capture did not cover the complete visible panel.');
    return images;
  }

  async function runCapture(runtime, panel, button) {
    const status = panel.querySelector('#job-ai-capture-status');
    const downloads = panel.querySelector('#job-ai-capture-downloads');
    const main = document.querySelector('[data-testid="stMain"]');
    const area = panel.querySelector('#job-ai-capture-area').value;
    const includeSidebar = panel.querySelector('#job-ai-capture-sidebar').checked;
    const header = area === 'full' ? document.querySelector('[data-testid="stHeader"]') : null;
    const readFrame = createFrameReader(runtime, panel);
    if (!main) {
      status.textContent = 'The Streamlit main panel could not be found.';
      return;
    }
    for (const link of downloads.querySelectorAll('a')) URL.revokeObjectURL(link.href);
    downloads.replaceChildren();
    button.disabled = true;
    try {
      const images = await restoreAfterCapture(main, header, panel,
        () => area === 'full' ? fullPngs(main, readFrame, includeSidebar)
          : visiblePng(main, readFrame, includeSidebar));
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      for (const [index, blob] of images.entries()) {
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        const url = link.href;
        setTimeout(() => URL.revokeObjectURL(url), 30 * 60 * 1000);
        link.download = `job-ai-helper-${timestamp}-${index + 1}.png`;
        link.textContent = images.length === 1 ? 'Download PNG' : `Download PNG part ${index + 1}`;
        const li = document.createElement('li');
        li.append(link);
        downloads.append(li);
      }
      status.textContent = images.length === 1 ? 'PNG ready to download.' : `${images.length} PNG parts ready to download in order.`;
    } catch (error) {
      status.textContent = error.message || 'Capture failed.';
    } finally {
      button.disabled = false;
    }
  }

  if (typeof module !== 'undefined') {
    module.exports = { nextSlice, restoreAfterCapture, fullPngs, visiblePng };
    return;
  }
  const runtime = (globalThis.browser || globalThis.chrome).runtime;
  const ready = () => {
    const panel = document.querySelector(PANEL);
    const button = panel?.querySelector('#job-ai-capture-start');
    if (!button || button.dataset.captureReady) return;
    button.dataset.captureReady = 'true';
    button.disabled = false;
    panel.querySelector('#job-ai-capture-status').textContent =
      'Open the Job AI Helper toolbar extension once on this tab to grant capture access. Then return here.';
    button.addEventListener('click', (event) => {
      if (event.isTrusted) void runCapture(runtime, panel, button);
    });
  };
  ready();
  new MutationObserver(ready).observe(document.body, { childList: true, subtree: true });
})();
