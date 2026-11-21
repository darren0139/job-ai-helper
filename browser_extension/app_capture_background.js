/* The content script owns scrolling and PNGs. Only this worker can request tab pixels. */
const captureRuntime = globalThis.browser || globalThis.chrome;

function isCaptureSender(sender) {
  if (sender.frameId !== 0 || !Number.isInteger(sender.tab?.id)) return false;
  try {
    const url = new URL(sender.url);
    return url.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(url.hostname);
  } catch {
    return false;
  }
}

async function captureActiveFrame(tabs, sender) {
  const { id, windowId } = sender.tab;
  let switched = false;
  const onActivated = (info) => {
    if (info.windowId === windowId && info.tabId !== id) switched = true;
  };
  tabs.onActivated.addListener(onActivated);
  try {
    const before = await tabs.get(id);
    if (!before.active || before.url !== sender.url || before.windowId !== windowId) {
      throw new Error('Keep this Job AI Helper tab active during Capture.');
    }
    const image = await tabs.captureVisibleTab(windowId, { format: 'png' });
    const after = await tabs.get(id);
    if (switched || !after.active || after.url !== sender.url || after.windowId !== windowId) {
      throw new Error('The active tab changed during Capture. No image was kept.');
    }
    return image;
  } finally {
    tabs.onActivated.removeListener(onActivated);
  }
}

if (captureRuntime?.runtime) {
  captureRuntime.runtime.onMessage.addListener((message, sender, respond) => {
    if (message?.type !== 'job-ai-helper:app-capture-frame' || !isCaptureSender(sender)) return false;
    captureActiveFrame(captureRuntime.tabs, sender).then(
      (image) => respond({ image }),
      (error) => respond({ error: String(error.message || error) }),
    );
    return true;
  });
}

if (typeof module !== 'undefined') module.exports = { captureActiveFrame, isCaptureSender };
