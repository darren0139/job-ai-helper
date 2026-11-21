"""Optional focused Chromium smoke for Capture's actual DOM and PNG drawing.

Uses local screenshots as the frame source. WebExtension activeTab permission
is exercised separately when the extension is loaded into a browser.
"""
from __future__ import annotations

import base64
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
            f'<aside>{panel}</aside><main data-testid="stMain">{colors}</main>'
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(timeout=10_000)
            try:
                page = browser.new_page(viewport={'width': 800, 'height': 400})
                page.set_content(html)

                page.evaluate("""() => {
                    window.pendingFixtureFrames = [];
                    window.browser = {runtime:{sendMessage:() => new Promise(resolve =>
                        window.pendingFixtureFrames.push(resolve))}};
                }""")
                page.add_script_tag(path=str(ROOT / 'browser_extension' / 'app_capture.js'))
                page.locator('summary').click()
                main = page.locator('main')
                main.evaluate('(el) => { el.scrollTop = 521; }')
                button = page.get_by_role('button', name='Capture', exact=True)
                for mode, size in [('visible', (580, 400)), ('full', (800, 1155))]:
                    with self.subTest(mode=mode):
                        page.select_option('#job-ai-capture-area', mode)
                        if mode == 'full':
                            page.get_by_label('Include visible sidebar').check()
                        button.click()
                        for _ in range(1 if mode == 'visible' else 3):
                            page.wait_for_function('window.pendingFixtureFrames.length > 0', timeout=5000)
                            pixels = base64.b64encode(page.screenshot(timeout=5000)).decode('ascii')
                            page.evaluate("(image) => window.pendingFixtureFrames.shift()({image})",
                                          'data:image/png;base64,' + pixels)
                        link = page.get_by_role('link', name='Download PNG', exact=True)
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
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main()
