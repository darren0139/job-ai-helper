"""Regression for native/custom DOCX project bullet readback."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from tailoring.phase9f_final_evidence_comparison_v2_4 import _read_exact_docx_bullets


def _num(p):
    ppr = p._p.get_or_add_pPr()
    num = OxmlElement('w:numPr')
    level = OxmlElement('w:ilvl'); level.set(qn('w:val'), '0')
    n = OxmlElement('w:numId'); n.set(qn('w:val'), '1')
    num.append(level); num.append(n); ppr.append(num)


class NativeDocxAuditTests(unittest.TestCase):
    def test_keith_style_native_word_bullets_are_detected(self):
        d = Document()
        for style in ['Resume Entry', 'Resume Subentry', 'Resume Bullet']:
            d.styles.add_style(style, WD_STYLE_TYPE.PARAGRAPH)
        d.add_paragraph('PROJECTS')
        d.add_paragraph('RequestFlow — IT Service Request Tracker\tJune 2026 – Aug 2026', 'Resume Entry')
        d.add_paragraph('Python, TypeScript, React | Individual Project', 'Resume Subentry')
        p=d.add_paragraph('Built a full-stack tracker.', 'Resume Bullet'); _num(p)
        p=d.add_paragraph('Automated CI and security checks.', 'Resume Bullet'); _num(p)
        d.add_paragraph('High Verdant — 3D Platformer Game\tSep 2024 – Apr 2025', 'Resume Entry')
        d.add_paragraph('C++, Lua | Team of 8', 'Resume Subentry')
        p=d.add_paragraph('Implemented Lua gameplay.', 'Normal'); _num(p)
        d.add_paragraph('SKILLS')
        d.add_paragraph('Programming: C++, Python', 'Normal')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'keith_style.docx'; d.save(p)
            titles=['RequestFlow — IT Service Request Tracker','High Verdant — 3D Platformer Game']
            actual, error = _read_exact_docx_bullets(p, titles)
            self.assertEqual(error, '')
            self.assertEqual(actual[titles[0]], ['Built a full-stack tracker.','Automated CI and security checks.'])
            self.assertEqual(actual[titles[1]], ['Implemented Lua gameplay.'])

    def test_custom_bullet_style_without_numbering_and_legacy_bullet_still_work(self):
        d = Document(); d.styles.add_style('Resume Bullet', WD_STYLE_TYPE.PARAGRAPH)
        d.add_paragraph('PROJECTS'); d.add_paragraph('My Project')
        d.add_paragraph('Custom styled text', 'Resume Bullet')
        d.add_paragraph('Legacy list styled text', 'List Bullet')
        d.add_paragraph('• Literal bullet text')
        d.add_paragraph('SKILLS'); d.add_paragraph('Python')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'styles.docx'; d.save(p)
            actual, error = _read_exact_docx_bullets(p, ['My Project'])
            self.assertEqual(error, '')
            self.assertEqual(actual['My Project'], ['Custom styled text','Legacy list styled text','Literal bullet text'])

    def test_metadata_is_not_a_bullet_and_genuine_mismatch_remains_visible(self):
        d=Document(); d.styles.add_style('Resume Subentry', WD_STYLE_TYPE.PARAGRAPH)
        d.add_paragraph('PROJECTS'); d.add_paragraph('My Project')
        d.add_paragraph('Team of 6 | Python', 'Resume Subentry')
        d.add_paragraph('• One confirmed bullet')
        d.add_paragraph('SKILLS')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'not_an_extra_bullet.docx'; d.save(p)
            actual, error=_read_exact_docx_bullets(p,['My Project'])
            self.assertEqual(error, '')
            self.assertEqual(len(actual['My Project']), 1)
            self.assertNotEqual(len(actual['My Project']), 2)  # Fail-closed count gate still needed.


if __name__=='__main__': unittest.main()
