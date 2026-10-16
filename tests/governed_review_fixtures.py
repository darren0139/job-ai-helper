"""Portable, test-owned native knowledge; never derive a baseline from live JSON."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from tailoring import capability_taxonomy as taxonomy
from tailoring.requirement_scope import API_RECOGNITION_FALLBACK

PRE_PUBLICATION=Path(__file__).with_name('fixtures')/'governed_requirement_taxonomy_v1_5.json'


def write_taxonomy(path, *, published=False):
    raw=json.loads(PRE_PUBLICATION.read_text(encoding='utf-8'))
    assert raw['taxonomy_version']=='phase6d-capability-taxonomy-v1.5'
    target=next(c for c in raw['capabilities'] if c['capability_id']=='backend.api_development')
    assert not target['requirement'].get('recognition_fallback_rules')
    if published:
        raw['taxonomy_version']='phase6d-capability-taxonomy-v1.6'
        target['requirement']['recognition_fallback_rules']=[deepcopy(API_RECOGNITION_FALLBACK)]
    Path(path).write_bytes((json.dumps(raw,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))


@contextmanager
def isolated_taxonomy(*, published=False):
    # A/B identity imports the artifact path by value. Import before patching,
    # then scope that alias too so lazy imports cannot retain a deleted path.
    from tailoring import job_match_ab_analysis as ab
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'taxonomy.json';write_taxonomy(path,published=published)
        with patch.object(taxonomy,'TAXONOMY_PATH',path), patch.object(ab,'TAXONOMY_PATH',path):
            taxonomy.get_default_taxonomy.cache_clear()
            try:yield path
            finally:taxonomy.get_default_taxonomy.cache_clear()
