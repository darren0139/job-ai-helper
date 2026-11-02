"""Regression tests for independent, on-demand Job Finder match panels.

The control tests execute the actual extracted production AST in a tiny fake
Streamlit harness. No database, network, scorer, or app imports are used.
"""
import ast
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'job_discovery' / 'ui.py'


class FakeStreamlit:
    def __init__(self, state=None, clicks=()):
        self.session_state = dict(state or {})
        self.clicks = set(clicks)
        self.empties = 0
        self.reruns = 0
    def button(self, label, *, key, **kwargs):
        return key in self.clicks
    def checkbox(self, label, *, key, **kwargs):
        return bool(self.session_state.get(key, False))
    def caption(self, value):
        pass
    def empty(self):
        self.empties += 1
        return f'placeholder-{self.empties}'
    def rerun(self):
        self.reruns += 1


def _card_control_function(tree):
    """Compile real per-card UI control statements, not a reimplemented policy."""
    candidate = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        if not isinstance(node.target, ast.Tuple):
            continue
        if [e.id for e in node.target.elts if isinstance(e, ast.Name)] == ['card_offset', 'card_job']:
            candidate = node
            break
    if candidate is None:
        raise AssertionError('missing card loop')
    with_node = next(n for n in candidate.body if isinstance(n, ast.With)
                     and any(isinstance(i.context_expr, ast.Call)
                             and isinstance(i.context_expr.func, ast.Attribute)
                             and i.context_expr.func.attr == 'container'
                             for i in n.items))
    controls = with_node.body
    start = next(i for i, n in enumerate(controls) if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'open_key' for t in n.targets))
    extracted = controls[start:]
    args = ['st', 'card_id', 'card_offset', 'page_start_index',
            'card_state', 'inline_match_detail_slots']
    fn = ast.FunctionDef(
        name='card_controls',
        args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=x) for x in args],
                           vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
        body=extracted + [ast.Return(value=ast.Constant(None))],
        decorator_list=[], returns=None, type_comment=None,
    )
    mod = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    env = {}
    exec(compile(mod, '<real-card-controls>', 'exec'), env)
    return env['card_controls']


def _collapse_function(tree):
    node = next(x for x in ast.walk(tree) if isinstance(x, ast.If)
                and isinstance(x.test, ast.Call)
                and isinstance(x.test.func, ast.Attribute)
                and x.test.func.attr == 'button'
                and x.test.args and isinstance(x.test.args[0], ast.Constant)
                and x.test.args[0].value == 'Collapse all Full Match Analysis panels')
    fn = ast.FunctionDef(
        name='collapse',
        args=ast.arguments(posonlyargs=[], args=[ast.arg(arg='st'), ast.arg(arg='page_job_ids')],
                           vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
        body=[node, ast.Return(value=ast.Constant(None))], decorator_list=[],
        returns=None, type_comment=None,
    )
    env = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 '<real-collapse-control>', 'exec'), env)
    return env['collapse']


class MultiExpandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = SOURCE.read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.src)
        cls.controls = staticmethod(_card_control_function(cls.tree))
        cls.collapse = staticmethod(_collapse_function(cls.tree))

    def test_two_expanded_cards_get_independent_detail_placeholders(self):
        st = FakeStreamlit({'job_finder_inline_full_match_v1_314': True,
                            'job_finder_inline_full_match_v1_319': True})
        slots=[]
        for idx, job_id in enumerate([314, 319, 321], 1):
            self.controls(st, job_id, idx, 0, {'status': 'current'}, slots)
        self.assertEqual([job_id for job_id, _ in slots], [314, 319])
        self.assertEqual(st.empties, 2)
        self.assertEqual(st.reruns, 0)

    def test_opening_third_card_does_not_collapse_other_cards(self):
        st = FakeStreamlit({'job_finder_inline_full_match_v1_314': True,
                            'job_finder_inline_full_match_v1_319': True},
                           clicks=['job_finder_select_card_v17_321'])
        slots=[]
        for idx, job_id in enumerate([314,319,321], 1):
            self.controls(st, job_id, idx, 0, {'status': 'none'}, slots)
        self.assertEqual([job_id for job_id, _ in slots], [314,319,321])
        self.assertTrue(st.session_state['job_finder_inline_full_match_v1_314'])
        self.assertTrue(st.session_state['job_finder_inline_full_match_v1_319'])
        self.assertTrue(st.session_state['job_finder_inline_full_match_v1_321'])
        self.assertEqual(st.reruns, 1)

    def test_collapsing_one_card_does_not_affect_other(self):
        st=FakeStreamlit({'job_finder_inline_full_match_v1_314': False,
                          'job_finder_inline_full_match_v1_319': True})
        slots=[]
        self.controls(st, 314, 1, 0, {'status': 'stale'}, slots)
        self.controls(st, 319, 2, 0, {'status': 'stale'}, slots)
        self.assertEqual([j for j, _ in slots],[319])

    def test_collapse_all_clears_only_visible_jobs(self):
        st=FakeStreamlit({'job_finder_inline_full_match_v1_314': True,
                          'job_finder_inline_full_match_v1_319': True,
                          'job_finder_inline_full_match_v1_999': True},
                         clicks=['job_finder_collapse_all_full_match_v11'])
        self.collapse(st,[314,319])
        self.assertEqual(st.session_state['job_finder_inline_full_match_v1_314'],False)
        self.assertEqual(st.session_state['job_finder_inline_full_match_v1_319'],False)
        self.assertTrue(st.session_state['job_finder_inline_full_match_v1_999'])
        self.assertEqual(st.reruns,1)

    def test_no_eager_per_card_receipt_loads(self):
        # Only the detail loop may invoke scoring or the receipt renderer.
        card_loop=next(x for x in ast.walk(self.tree) if isinstance(x, ast.For)
                       and isinstance(x.target, ast.Tuple)
                       and [n.id for n in x.target.elts if isinstance(n, ast.Name)]
                       == ['card_offset','card_job'])
        seg=ast.get_source_segment(self.src,card_loop)
        self.assertNotIn('analyze_job_match(',seg)
        self.assertNotIn('render_job_finder_explainer(',seg)
        self.assertNotIn('_connect_read_only(',seg)
        self.assertEqual(seg.count('st.empty()'),1)

    def test_existing_match_actions_and_historical_isolation(self):
        self.assertIn('for selected_job_id, inline_match_detail_slot in inline_match_detail_slots:',self.src)
        self.assertIn('HISTORICAL MATCH — NOT CURRENT',self.src)
        self.assertIn('if match_state.get("status") == "current"',self.src)
        self.assertIn('snapshot = (',self.src)
        self.assertIn('if isinstance(snapshot, dict):',self.src)
        self.assertIn('analyze_job_match(',self.src)
        self.assertIn('Use in new Application Session',self.src)
        self.assertIn('"Batch candidate matching"',self.src)
        self.assertNotIn('selected_job_key',self.src)

    def test_no_duplicate_score_explainer_controls(self):
        self.assertNotIn('"Show full saved score calculation for this card"',self.src)
        self.assertNotIn('"Score details · #',self.src)
        self.assertIn('Export saved card summary (CSV)',self.src)
        self.assertEqual(self.src.count('with st.expander("How this match was analyzed")'),1)


if __name__ == '__main__': unittest.main()
