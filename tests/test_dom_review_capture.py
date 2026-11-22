"""Focused DOM reconstruction controls. No private inputs or model calls."""
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from hashlib import sha256
import unittest
from zipfile import ZipFile

from PIL import Image
from streamlit.testing.v1 import AppTest


class ComponentContract(unittest.TestCase):
    def test_sidebar_mounts_v2_without_starting_another_browser(self):
        app=AppTest.from_string('from tailoring.ui_review_capture_ui import render_ui_review_capture\nrender_ui_review_capture()').run(timeout=30)
        self.assertFalse(app.exception,list(app.exception))
        self.assertTrue(any(b.label=='Start Capture Session' for b in app.button))
        from browser_integration.dom_review_capture import javascript
        js=javascript()
        self.assertIn('export default function(component)',js)
        self.assertIn('captureFiles.sectionRanges',js)
        self.assertIn('captureFiles.zipFiles',js)
        self.assertIn('captureFiles.crc32',js)
        capture_handler=js[js.index('capture.onclick='):js.index('exportButton.onclick=')]
        self.assertNotIn('setTriggerValue(',capture_handler)
        self.assertNotIn('setStateValue(',js)


    def test_app_export_rejects_private_paths_and_bad_archives(self):
        from browser_integration.dom_review_capture import validate_export
        from zipfile import BadZipFile
        def packet(name):
            b=BytesIO()
            with ZipFile(b,'w') as z:z.writestr(name,b'fixture')
            return b.getvalue()
        valid=packet('JobAIHelper_UI_Review/view/manifest.json')
        self.assertEqual(validate_export(valid),valid)
        for name in ['database/private.db','JobAIHelper_UI_Review/../private.json','JobAIHelper_UI_Review/view/secret.env']:
            with self.assertRaises(ValueError):validate_export(packet(name))
        with self.assertRaises((ValueError,BadZipFile)):validate_export(b'broken')


    def test_app_sections_are_exact_crops_of_original(self):
        from browser_integration.dom_review_capture import canonical_export
        from browser_integration.ui_review_capture import image_files
        b=BytesIO();Image.new('RGB',(240,2400),'blue').save(b,format='PNG');original=b.getvalue()
        _,meta=image_files(original)
        metadata={'captures':[{'directory':'01_View','panels':[{'name':'main',**meta}]}]}
        raw=BytesIO()
        with ZipFile(raw,'w') as z:
            z.writestr('JobAIHelper_UI_Review/manifest.json',json.dumps(metadata))
            z.writestr('JobAIHelper_UI_Review/README.md','Synthetic original')
            z.writestr('JobAIHelper_UI_Review/01_View/main/full.png',original)
        with ZipFile(BytesIO(canonical_export(raw.getvalue()))) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(z.read('JobAIHelper_UI_Review/01_View/main/full.png'),original)
            data=json.loads(z.read('JobAIHelper_UI_Review/manifest.json'))
            for section in data['captures'][0]['panels'][0]['sections']:
                raw_section=z.read('JobAIHelper_UI_Review/01_View/main/'+section['name'])
                self.assertEqual(sha256(raw_section).hexdigest(),section['sha256'])
                with Image.open(BytesIO(raw_section)) as crop,Image.open(BytesIO(original)) as full:
                    self.assertEqual(crop.tobytes(),full.crop(section['coordinates']).tobytes())


class DOMPixels(unittest.TestCase):
    def test_long_current_document_two_states_pixels_zip_and_restore(self):
        from playwright.sync_api import sync_playwright
        from browser_integration.dom_review_capture import javascript
        source=javascript().replace('export default function(component)', 'window.mountReview=function(component)')
        html='''<!doctype html><meta charset=utf-8><style>
        body{margin:0;font-family:Arial;background:white}aside{position:absolute;width:220px;height:600px;overflow:auto;background:#ededed}
        main{margin-left:220px;height:600px;overflow:auto;background:white}.row{height:1000px;box-sizing:border-box;padding:10px}
        #sticky{position:sticky;top:0;height:25px;background:purple}#controls{position:fixed;left:0;top:0;width:210px}
        </style><aside data-testid=stSidebarContent><div style="height:2000px">Sidebar starts<br>Complete sidebar</div></aside>
        <main data-testid=stMain><div id=sticky>Sticky header once</div><div data-testid=stSelectbox>App156 · Testing wording</div>
        <canvas width=100 height=60></canvas>'''+''.join('<div class=row style="background:'+('rgb(255,0,0)' if n%2==0 else 'rgb(0,0,255)')+'">Long page row '+str(n)+'</div>' for n in range(13))+'''<p>END OF MAIN CONTENT</p><details><summary>Collapsed receipt</summary><div id=hidden-receipt></div></details></main>
        <div id=controls><input id=review-name value="State one"><button id=review-capture>Capture Entire Current Page</button><p id=review-status></p><ol id=review-views></ol><button id=review-export>Export</button><div id=review-download></div></div>
        <script>document.querySelector('canvas').getContext('2d').fillStyle='green';document.querySelector('canvas').getContext('2d').fillRect(0,0,100,60);</script>'''
        with sync_playwright() as p:
            for engine in ('chromium','firefox'):
                with self.subTest(engine=engine):
                    browser=getattr(p,engine).launch()
                    try:
                        page=browser.new_page(viewport={'width':800,'height':600},device_scale_factor=1)
                        page.route('http://localhost:18502/',lambda route:route.fulfill(body=html,content_type='text/html; charset=utf-8'))
                        page.goto('http://localhost:18502/')
                        page.locator('#hidden-receipt').evaluate("el=>{for(let i=0;i<26000;i++)el.append(document.createElement('span'));}")
                        page.add_script_tag(content=source)
                        page.evaluate("mountReview({parentElement:document.querySelector('#controls'),key:'test',setTriggerValue:()=>{}})")
                        main=page.locator('main');main.evaluate('el=>el.scrollTop=3210')
                        page.locator('aside').evaluate('el=>el.scrollTop=300')
                        for n in range(2):
                            if n:page.locator('[data-testid=stSelectbox]').evaluate("el=>el.innerText='App156 · Different wording'")
                            page.locator('#review-name').fill('State '+str(n+1))
                            page.locator('#review-capture').click()
                            page.wait_for_function("!document.querySelector('#review-capture').disabled",timeout=60000)
                            self.assertTrue(page.locator('#review-status').inner_text().startswith('Captured'),page.locator('#review-status').inner_text())
                            self.assertEqual(main.evaluate('el=>el.scrollTop'),3210)
                            self.assertEqual(page.locator('aside').evaluate('el=>el.scrollTop'),300)
                            self.assertEqual(page.locator('#sticky').evaluate('el=>getComputedStyle(el).position'),'sticky')
                        page.locator('#review-export').click()
                        page.get_by_role('link',name='Download current-page review ZIP').wait_for(timeout=10000)
                        data=page.get_by_role('link',name='Download current-page review ZIP').evaluate('async e=>Array.from(new Uint8Array(await (await fetch(e.href)).arrayBuffer()))')
                        with ZipFile(BytesIO(bytes(data))) as z:
                            self.assertIsNone(z.testzip());m=json.loads(z.read('JobAIHelper_UI_Review/manifest.json'))
                            self.assertEqual(len(m['captures']),2)
                            self.assertNotEqual(m['captures'][0]['state']['controls'],m['captures'][1]['state']['controls'])
                            for c in m['captures']:
                                self.assertEqual([e['name'] for e in c['panels']],['main','sidebar'])
                                panel=c['panels'][0];self.assertGreater(panel['dimensions'][1],10000);self.assertEqual(panel['dimensions'][0],580)
                                with Image.open(BytesIO(z.read('JobAIHelper_UI_Review/'+c['directory']+'/main/full.png'))) as im:
                                    self.assertEqual(im.getpixel((50,50))[:3],(0,128,0))
                                    self.assertEqual(sum(im.getpixel((400,y))[:3]==(128,0,128) for y in range(im.height)),25)
                                    self.assertEqual(im.getpixel((400,500))[:3],(255,0,0))
                                    self.assertEqual(im.getpixel((400,1500))[:3],(0,0,255))
                                    full=z.read('JobAIHelper_UI_Review/'+c['directory']+'/main/full.png')
                                    self.assertEqual(sha256(full).hexdigest(),panel['sha256'])
                                    end=0
                                    for section in panel['sections']:
                                        x,a,w,b=section['coordinates'];self.assertLessEqual(a,end);end=b
                                        raw=z.read('JobAIHelper_UI_Review/'+c['directory']+'/main/'+section['name']);self.assertEqual(sha256(raw).hexdigest(),section['sha256'])
                                        with Image.open(BytesIO(raw)) as crop:
                                            self.assertEqual(crop.tobytes(),im.crop((x,a,w,b)).tobytes())
                                    self.assertEqual(end,im.height)
                        # Visible embedded content must fail, never disappear silently.
                        main.evaluate("el=>{const f=document.createElement('iframe');f.srcdoc='<p>embedded</p>';el.prepend(f);el.scrollTop=0;}")
                        page.locator('#review-capture').click()
                        page.wait_for_function("!document.querySelector('#review-capture').disabled",timeout=60000)
                        self.assertIn('Embedded iframe',page.locator('#review-status').inner_text())
                        main.evaluate("el=>{el.querySelector('iframe').remove();el.firstElementChild.style.backdropFilter='blur(2px)';}")
                        page.locator('#review-capture').click()
                        page.wait_for_function("!document.querySelector('#review-capture').disabled",timeout=10000)
                        self.assertIn('Backdrop filtering',page.locator('#review-status').inner_text())
                        main.evaluate("el=>{el.firstElementChild.style.backdropFilter='none';el.style.height='600px';el.firstElementChild.style.height='200000px';}")
                        page.locator('#review-capture').click()
                        page.wait_for_function("!document.querySelector('#review-capture').disabled",timeout=10000)
                        self.assertIn('pixel bound',page.locator('#review-status').inner_text())
                    finally:browser.close()


if __name__=='__main__':unittest.main()
