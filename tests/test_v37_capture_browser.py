"""Optional focused Chromium smoke for Capture's actual DOM and PNG drawing.

Uses local screenshots as the frame source. WebExtension activeTab permission
is exercised separately when the extension is loaded into a browser.
"""
from __future__ import annotations

import base64
import json
from hashlib import sha256
from zipfile import ZipFile
from io import BytesIO
from pathlib import Path
import unittest

from PIL import Image

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(sync_playwright is None, 'Optional Playwright smoke dependency is unavailable.')
class CaptureBrowserSmoke(unittest.TestCase):
    def test_visible_and_full_png_use_original_browser_document_and_restore_scroll(self):
        panel = (ROOT / 'assets' / 'streamlit_capture.html').read_text(encoding='utf-8')
        colors = ''.join(f'<div style="height:385px;background:{color}"></div>'
                         for color in ('red', 'blue', 'yellow'))
        html = (
            '<style>body{margin:0}aside{position:absolute;width:220px;height:400px;background:green}'
            'main{margin-left:220px;height:400px;overflow:auto;scrollbar-width:none}</style>'
            f'<aside data-testid="stSidebarContent" style="overflow:auto">{panel}</aside><main data-testid="stMain">{colors}</main>'
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(timeout=10_000)
            try:
                page = browser.new_page(viewport={'width': 800, 'height': 400})
                page.route('http://localhost:18501/',lambda route:route.fulfill(body=html,content_type='text/html; charset=utf-8'))
                page.goto('http://localhost:18501/')

                page.evaluate("""() => {
                    window.pendingFixtureFrames = [];
                    window.browser = {runtime:{sendMessage:() => new Promise(resolve =>
                        window.pendingFixtureFrames.push(resolve))}};
                }""")
                page.add_script_tag(path=str(ROOT / 'browser_extension' / 'app_capture.js'))

                main = page.locator('main')
                main.evaluate('(el) => { el.scrollTop = 521; }')
                button = page.get_by_role('button', name='Capture This Tab — Full Page', exact=True)
                page.get_by_label('Include sidebar',exact=True).uncheck()
                for mode, size in [('visible', (580, 400)), ('full', (800, 1155))]:
                    with self.subTest(mode=mode):
                        page.select_option('#job-ai-capture-area', mode)
                        if mode == 'full':
                            page.get_by_label('Include sidebar',exact=True).check()
                        button.click()
                        for _ in range(10):
                            page.wait_for_function('window.pendingFixtureFrames.length > 0 || !document.querySelector("#job-ai-capture-start").disabled', timeout=5000)
                            if not page.evaluate('window.pendingFixtureFrames.length'):break
                            pixels = base64.b64encode(page.screenshot(timeout=5000)).decode('ascii')
                            page.evaluate("(image) => window.pendingFixtureFrames.shift()({image})", 'data:image/png;base64,' + pixels)
                        self.assertTrue(page.locator('#job-ai-capture-status').inner_text().startswith('Captured '),page.locator('#job-ai-capture-status').inner_text())
                        link = page.get_by_role('link', name=f'{1 if mode=="visible" else 2}. Application view · full PNG', exact=True)
                        link.wait_for(timeout=10_000)
                        data = link.evaluate("""async (a) => {
                            const bytes = await (await fetch(a.href)).arrayBuffer();
                            const reader = new FileReader();
                            return await new Promise(resolve => {
                                reader.onload = () => resolve(reader.result.split(',')[1]);
                                reader.readAsDataURL(new Blob([bytes], {type: 'image/png'}));
                            });
                        }""")
                        with Image.open(BytesIO(base64.b64decode(data))) as image:
                            self.assertEqual(image.size, size)
                            if mode == 'full':
                                self.assertEqual(image.getpixel((10, 20))[:3], (0, 128, 0))
                                self.assertEqual(image.getpixel((240, 20))[:3], (255, 0, 0))
                                self.assertEqual(image.getpixel((240, 420))[:3], (0, 0, 255))
                                self.assertEqual(image.getpixel((240, 1040))[:3], (255, 255, 0))
                        self.assertEqual(main.evaluate('(el) => el.scrollTop'), 521)
                page.get_by_role('button',name='Export This Tab Review ZIP',exact=True).click()
                link=page.get_by_role('link',name='Download This Tab Review ZIP',exact=True)
                link.wait_for(timeout=10000)
                data=link.evaluate("async a=>Array.from(new Uint8Array(await (await fetch(a.href)).arrayBuffer()))")
                with ZipFile(BytesIO(bytes(data))) as z:
                    self.assertIsNone(z.testzip());manifest=json.loads(z.read('JobAIHelper_UI_Review/manifest.json'))
                    self.assertEqual(manifest['mode'],'extension-current-tab');self.assertEqual(len(manifest['captures']),2)
                    for entry in manifest['captures']:
                        full=z.read('JobAIHelper_UI_Review/'+entry['directory']+'/full.png')
                        self.assertEqual(sha256(full).hexdigest(),entry['sha256']);end=0
                        with Image.open(BytesIO(full)) as original:
                            for section in entry['sections']:
                                raw=z.read('JobAIHelper_UI_Review/'+entry['directory']+'/'+section['name'])
                                self.assertEqual(sha256(raw).hexdigest(),section['sha256'])
                                x,a,w,b=section['coordinates'];self.assertLessEqual(a,end);end=b
                                with Image.open(BytesIO(raw)) as crop:self.assertEqual(crop.tobytes(),original.crop((x,a,w,b)).tobytes())
                            self.assertEqual(end,original.height)
                        self.assertTrue(entry['scroll_restored'])

            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main()
