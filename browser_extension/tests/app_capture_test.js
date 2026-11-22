const assert = require('node:assert/strict');
const test = require('node:test');
const { captureActiveFrame, isCaptureSender } = require('../app_capture_background.js');
const { nextSlice, restoreAfterCapture, fullPngs, visiblePng } = require('../app_capture.js');

const sender = { frameId: 0, url: 'http://localhost:8501/', tab: { id: 7, windowId: 23 } };

function fakeTabs({ active = true, switchTab = false, reject = false } = {}) {
  const listeners = new Set();
  const windows = [];
  return {
    listeners, windows,
    onActivated: { addListener: (fn) => listeners.add(fn), removeListener: (fn) => listeners.delete(fn) },
    get: async () => ({ ...sender.tab, active, url: sender.url }),
    captureVisibleTab: async (windowId) => {
      windows.push(windowId);
      if (switchTab) {
        for (const fn of listeners) {
          fn({ tabId: 8, windowId });
          fn({ tabId: 7, windowId });
        }
      }
      if (reject) throw new Error('permission withheld');
      return 'data:image/png;base64,fixture';
    },
  };
}

test('restrict screenshot messages to local top-frame tab senders', () => {
  assert.equal(isCaptureSender(sender), true);
  for (const overrides of [
    { frameId: 1 }, { url: 'https://example.com' }, { url: 'http://localhost.example.com' }, { tab: null },
  ]) {
    assert.equal(isCaptureSender({ ...sender, ...overrides }), false);
  }
});

test('capture targets the sender window and checks tab identity', async () => {
  const tabs = fakeTabs();
  assert.equal(await captureActiveFrame(tabs, sender), 'data:image/png;base64,fixture');
  assert.deepEqual(tabs.windows, [23]);
  assert.equal(tabs.listeners.size, 0);
  const inactive = fakeTabs({ active: false });
  await assert.rejects(captureActiveFrame(inactive, sender), /active/);
  assert.equal(inactive.windows.length, 0);
});

test('active-tab switches and permission errors discard frames and remove listeners', async () => {
  for (const [config, message] of [[{ switchTab: true }, /changed/], [{ reject: true }, /permission withheld/]]) {
    const tabs = fakeTabs(config);
    await assert.rejects(captureActiveFrame(tabs, sender), message);
    assert.equal(tabs.listeners.size, 0);
  }
});

test('stitching crops the overlapping part of a clamped final viewport', () => {
  assert.deepEqual(nextSlice(0, 500, 1150, 0), { offset: 0, height: 500, end: 500 });
  assert.deepEqual(nextSlice(500, 500, 1150, 500), { offset: 0, height: 500, end: 1000 });
  assert.deepEqual(nextSlice(650, 500, 1150, 1000), { offset: 350, height: 150, end: 1150 });
  assert.throws(() => nextSlice(525, 500, 1150, 500), /changed/);
  assert.throws(() => nextSlice(0, 500, 1150, 500), /changed/);
});

test('capture restores scroll and styles on success and failure', async () => {
  for (const fail of [false, true]) {
    const main = { scrollTop: 283, scrollLeft: 5, style: { scrollBehavior: 'smooth' } };
    const panel = { style: { visibility: '' } };
    const header = { style: { visibility: 'visible' } };
    const capture = restoreAfterCapture(main, header, panel, async () => {
      assert.equal(panel.style.visibility, 'hidden');
      assert.equal(header.style.visibility, 'hidden');
      main.scrollTop = 500;
      main.scrollLeft = 0;
      if (fail) throw new Error('interrupted');
      return 'png';
    });
    if (fail) await assert.rejects(capture, /interrupted/);
    else assert.equal(await capture, 'png');
    assert.deepEqual(main, { scrollTop: 283, scrollLeft: 5, style: { scrollBehavior: 'smooth' } });
    assert.equal(panel.style.visibility, '');
    assert.equal(header.style.visibility, 'visible');
  }
});

test('visible crop and full stitching produce bounded PNG parts with continuous main rows', async (t) => {
  globalThis.innerWidth = 800;
  globalThis.innerHeight = 1000;
  globalThis.getComputedStyle = () => ({ backgroundColor: 'white' });
  globalThis.document = {
    createElement() {
      const draws = [];
      return {
        width: 0, height: 0,
        getContext: () => ({ fillRect() {}, drawImage: (...args) => draws.push(args) }),
        toBlob(callback) { callback({ width: this.width, height: this.height, draws }); },
      };
    },
  };
  t.after(() => {
    for (const key of ['innerWidth', 'innerHeight', 'getComputedStyle', 'document']) delete globalThis[key];
  });
  const main = {
    clientWidth: 600, scrollWidth: 600, clientHeight: 1000, scrollHeight: 9500,
    scrollTop: 320, scrollLeft: 0, getBoundingClientRect: () => ({ top: 0, left: 200 }),
  };
  const read = async () => ({
    image: { naturalWidth: 800, naturalHeight: 1000, top: main.scrollTop }, scaleX: 1, scaleY: 1,
  });
  const [visible] = await visiblePng(main, read, false);
  assert.equal(visible.width, 600);
  assert.equal(visible.height, 1000);
  assert.equal(visible.draws[0][1], 200);
  assert.equal(main.scrollTop, 320);
  const chunks = await fullPngs(main, read, true);
  assert.deepEqual(chunks.map(({ width, height }) => [width, height]), [[800, 8192], [800, 1308]]);
  let nextRow = 0;
  for (const chunk of chunks) {
    for (const [image, left, y, , height] of chunk.draws) {
      if (left === 0) continue;
      assert.equal(image.top + y, nextRow);
      nextRow += height;
    }
  }
  assert.equal(nextRow, 9500);
  assert.equal(chunks.flatMap(({ draws }) => draws).filter((draw) => draw[1] === 0).length, 1);
});

test('both manifests use local content scripts and the existing activeTab grant', () => {
  for (const name of ['manifest.json', 'manifest.firefox.json']) {
    const manifest = require('../' + name);
    const background = manifest.background.service_worker || manifest.background.scripts[0];
    assert.equal(background, 'app_capture_background.js');
    assert.deepEqual(manifest.permissions, ['activeTab', 'scripting', 'storage']);
    assert.deepEqual(manifest.content_scripts[0].matches, ['http://127.0.0.1/*', 'http://localhost/*']);
    assert.deepEqual(manifest.content_scripts[0].js, ['app_capture.js']);
  }
});


test('readable section ranges preserve full vertical coverage without resizing', () => {
  const {sectionRanges} = require('../app_capture.js');
  for (const height of [500,1800,1801,31148,45000]) {
    let end=0;
    for (const [top,bottom] of sectionRanges(height)) {
      assert.ok(top<=end);assert.ok(bottom>top);assert.ok(bottom-top<=1800);end=bottom;
    }
    assert.equal(end,height);
  }
  assert.throws(()=>sectionRanges(0),/geometry/);
});

test('ZIP contains UTF8 names, CRCs, original bytes and readable-section files', async () => {
  const {zipFiles,crc32} = require('../app_capture.js');
  const items=[['review/full.png',new Blob([new Uint8Array([137,80,78,71])])],['review/sections/001.png',new Blob(['crop'])],['review/manifest.json',new Blob(['{"captures":2}'])]];
  const bytes=new Uint8Array(await (await zipFiles(items)).arrayBuffer());let offset=0;
  for (const [name,blob] of items) {
    const h=new DataView(bytes.buffer,offset);assert.equal(h.getUint32(0,true),0x04034b50);
    const size=h.getUint32(18,true),n=h.getUint16(26,true),start=offset+30+n;
    assert.equal(new TextDecoder().decode(bytes.slice(offset+30,start)),name);
    const content=bytes.slice(start,start+size);assert.deepEqual(content,new Uint8Array(await blob.arrayBuffer()));
    assert.equal(h.getUint32(14,true),crc32(content));offset=start+size;
  }
  assert.equal(new DataView(bytes.buffer,offset).getUint32(0,true),0x02014b50);
  const end=new DataView(bytes.buffer,bytes.length-22);assert.equal(end.getUint32(0,true),0x06054b50);assert.equal(end.getUint16(10,true),items.length);
});


test('sticky capture layout restores exact original inline styles', () => {
  const {unpin} = require('../app_capture.js');
  const node={value:'color:red',computed:'sticky',getAttribute(){return this.value;},style:{setProperty(){node.value='position:static!important';}},setAttribute(_name,value){this.value=value;},removeAttribute(){this.value=null;}};
  globalThis.getComputedStyle = element => ({position:element.computed});
  try {const restore=unpin([node]);assert.equal(node.value,'position:static!important');restore();assert.equal(node.value,'color:red');}
  finally {delete globalThis.getComputedStyle;}
});
