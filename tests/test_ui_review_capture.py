import json
from io import BytesIO
import unittest
from zipfile import ZipFile
from PIL import Image
from browser_integration.ui_review_capture import section_ranges,image_files,CaptureSession
from streamlit.testing.v1 import AppTest


class ReviewCapture(unittest.TestCase):
    def test_full_width_sections_cover_long_image(self):
        out=BytesIO();Image.new('RGB',(800,11000),'white').save(out,format='PNG')
        files,meta=image_files(out.getvalue());self.assertEqual(meta['dimensions'],[800,11000])
        end=0
        for section in meta['sections']:
            x,a,w,b=section['coordinates'];self.assertLessEqual(a,end);end=b
            with Image.open(BytesIO(files[section['name']])) as im:self.assertEqual(im.size,(800,b-a))
        self.assertEqual(end,11000);self.assertEqual(files['full.png'],out.getvalue())

    def test_stitch_clamped_frames_preserve_every_source_row(self):
        import tempfile
        from pathlib import Path
        from browser_integration.ui_review_scroll import _capture, SEL_JS
        class Page:
            viewport_size={'width':1200,'height':600}
            top=0
            def evaluate(self,code,*args):
                if code==SEL_JS:return {'mode':'container','total':3500,'rect':{'x':200,'y':0,'width':1000,'height':600},'selector':'main'}
                self.top=min(2900,args[0]);return {'top':self.top,'total':3500,'visible':600}
            def wait_for_timeout(self,*_):pass
            def screenshot(self,**_):
                image=Image.new('RGB',(1200,600));pixels=image.load()
                for y in range(600):
                    color=((self.top+y)%251,(self.top+y)//251,73)
                    for x in range(200,1200):pixels[x,y]=color
                b=BytesIO();image.save(b,format='PNG');return b.getvalue()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'full.png';result=_capture(Page(),path)
            with Image.open(path) as im:
                self.assertEqual(im.size,(1000,3500))
                for y in range(3500):self.assertEqual(im.getpixel((50,y)),(y%251,y//251,73),y)
            self.assertGreater(result['frames'],5)

    def test_zip_remove_and_order(self):
        s=CaptureSession();out=BytesIO();Image.new('RGB',(800,500)).save(out,format='PNG');files,meta=image_files(out.getvalue())
        for n in [1,2,3]:s.views.append(dict(id=str(n),sequence=n,name='View',notes='',files=files,status='success',**meta))
        s.remove('2')
        with ZipFile(BytesIO(s.export())) as z:
            self.assertIsNone(z.testzip());m=json.loads(z.read('JobAIHelper_UI_Review/manifest.json'));self.assertEqual([v['sequence'] for v in m['captures']],[1,3])
            self.assertTrue(all('JobAIHelper_UI_Review/'+v['directory']+'/full.png' in z.namelist() for v in m['captures']))
        s.pool.shutdown()

    def test_not_started_and_external_urls_fail_closed(self):
        s=CaptureSession()
        with self.assertRaises(RuntimeError):s.capture('Missing')
        for url in ['https://example.com','http://localhost.evil/','http://user:secret@localhost:8501']:
            with self.assertRaises(ValueError):s.start(url)
        s.pool.shutdown()

    def test_capture_controls_render_without_starting_browser(self):
        a=AppTest.from_string('from tailoring.ui_review_capture_ui import render_ui_review_capture\nrender_ui_review_capture()').run()
        self.assertFalse(a.exception);self.assertTrue(any(x.label=='Start Capture Session' for x in a.button))

    def test_unit_testing_without_pair_has_substantive_explanation(self):
        a=AppTest.from_string('''import streamlit as st
from tailoring.phase9f_wording_explanation_ui import render_source_wordings
row={'bullet':'Added automated unit tests and GitHub Actions CI across Ubuntu and Windows.', 'project':'Job AI Helper','sources':['Evidence Library'],'source_label':'Library bullet','in_actual_a':True,'in_proposed_b':True,'words':15,'jd_links':[]}
render_source_wordings(st,scope=[row],catalog={'t':{'id':'t','text':'Execute unit, integration, system and user acceptance testing','importance':'core'}},recorded=True,proposal={},key='unit')
''').run()
        self.assertFalse(a.exception,list(a.exception));text=' '.join(x.value for x in a.markdown)
        self.assertIn('Execute unit, integration, system',text);self.assertIn('Explicit testing terminology: unit testing',text)
        self.assertIn('integration testing, system testing, user acceptance testing',text)
        self.assertIn('Individual selection cause not recorded',' '.join(x.value for x in a.caption))


if __name__=='__main__':unittest.main()
