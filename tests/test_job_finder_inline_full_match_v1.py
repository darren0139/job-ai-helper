"""Job Finder inline match analysis: render placement and historical isolation.

Independent static+behavior checks; no DB, scorer, model or network calls.
"""
import ast
import re
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "job_discovery" / "ui.py"

def _detail_node(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.With) and any(
            isinstance(item.context_expr, ast.Call)
            and isinstance(item.context_expr.func, ast.Attribute)
            and item.context_expr.func.attr == "container"
            and isinstance(item.context_expr.func.value, ast.Name)
            and item.context_expr.func.value.id == "inline_match_detail_slot"
            for item in node.items
        ):
            return node
    raise AssertionError("Missing selected-card detail container")

def _history_renderer(detail):
    """Compile just the real stale branch from production source into a pure harness."""
    nodes = [x for x in ast.walk(detail) if isinstance(x, ast.If)
             and isinstance(x.test, ast.Compare)
             and any(isinstance(y, ast.Constant) and y.value == "stale" for y in x.test.comparators)
             and any(isinstance(y, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "historic" for t in y.targets) for y in x.body)]
    assert len(nodes) == 1, len(nodes)
    fn = ast.FunctionDef(name="render", args=ast.arguments(posonlyargs=[], args=[ast.arg(arg="st"), ast.arg(arg="match_state")], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]), body=[nodes[0], ast.Return(value=ast.Constant(value=None))], decorator_list=[])
    fn.returns = None
    module=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]))
    ns={}
    exec(compile(module,"<historical_branch>","exec"),ns)
    return ns["render"]

class UI:
    def __init__(self): self.messages=[]
    def warning(self,x): self.messages.append(("warning",x))
    def caption(self,x): self.messages.append(("caption",x))
    def metric(self,k,v): self.messages.append(("metric",k,v))
    def columns(self,n): return [self for _ in range(n)]
    def json(self,v): self.messages.append(("json",v))
    def expander(self,*a,**kw):
        class Ctx:
            def __enter__(inner):return self
            def __exit__(inner,*_):return False
        return Ctx()

class JobFinderInlineMatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src=SRC.read_text(encoding="utf-8")
        cls.tree=ast.parse(cls.src)
        cls.detail=_detail_node(cls.tree)

    def test_card_has_independently_lazy_detail_slots(self):
        self.assertEqual(self.src.count('inline_match_detail_slots.append((card_id, st.empty()))'),1)
        self.assertEqual(self.src.count('with inline_match_detail_slot.container():'),1)
        self.assertIn('f"Full Match Analysis · #{page_start_index + card_offset}"',self.src)
        self.assertIn('for selected_job_id, inline_match_detail_slot in inline_match_detail_slots:',self.src)
        self.assertLess(self.src.index('inline_match_detail_slots.append((card_id, st.empty()))'),self.src.index('with inline_match_detail_slot.container():'))
        self.assertEqual(self.src.count('with st.expander("How this match was analyzed")'),1)
        self.assertNotIn('job_finder_selected_job_v16',self.src)

    def test_existing_matching_and_batch_actions_remain(self):
        segment=ast.get_source_segment(self.src,self.detail)
        self.assertIn("analyze_job_match(",segment)
        self.assertIn("render_job_finder_explainer",segment)
        self.assertIn("Refresh Match",segment)
        self.assertIn("Use in new Application Session",segment)
        self.assertIn("job_finder_hide_job_v16_",segment)
        self.assertNotIn('"Batch candidate matching"',segment)
        self.assertEqual(self.src.count('"Batch candidate matching"'),1)

    def test_historical_score_is_separate_from_current_snapshot(self):
        segment=ast.get_source_segment(self.src,self.detail)
        self.assertIn('if match_state.get("status") == "current"',segment)
        self.assertIn('if match_state.get("status") == "stale":',segment)
        self.assertIn("HISTORICAL MATCH — NOT CURRENT",segment)
        self.assertIn('if isinstance(snapshot, dict):',segment)
        self.assertNotIn('snapshot = match_state.get("snapshot")',segment)

    def test_stale_saved_score_is_labeled_and_read_only(self):
        render=_history_renderer(self.detail)
        st=UI()
        render(st,{"status":"stale","snapshot":{"id":29,"created_at":"2026-10-02","summary":{"deterministic_alignment_score":26,"required_core_coverage_score":19,"preferred_coverage_score":0,"evidence_strength_score":71}},"stale_reasons":["scorer changed"]})
        self.assertTrue(any(x[0]=="warning" and "NOT CURRENT" in x[1] for x in st.messages))
        self.assertIn(("metric","Historical Job Match","26/100"),st.messages)
        self.assertTrue(any(x[0]=="json" and x[1]["historical_only"] for x in st.messages))

    def test_none_and_current_never_present_historical_score(self):
        render=_history_renderer(self.detail)
        for status in ["none","current"]:
            st=UI()
            render(st,{"status":status,"snapshot":{"summary":{"deterministic_alignment_score":100}}})
            self.assertEqual(st.messages,[])

    def test_stale_without_summary_does_not_fabricate_score(self):
        st=UI()
        _history_renderer(self.detail)(st,{"status":"stale","snapshot":{"summary":{}}})
        self.assertFalse(any(v[0]=="metric" for v in st.messages))

if __name__ == "__main__":unittest.main()
