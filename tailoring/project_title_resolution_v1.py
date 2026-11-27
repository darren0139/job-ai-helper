"""Conservative title aliases shared by source joining and read-only inspection.

No fuzzy matching, cross-user lookup, persistence or score authority. Distinct
nonempty project IDs conflict. A bare title may match one descriptive variant
only when the complete candidate group makes the relation unambiguous.
"""
from __future__ import annotations
import re
import unicodedata

GENERIC = {'project', 'game', 'app', 'application', 'final year project',
           'personal project', 'team project', 'capstone', 'capstone project',
           'school project', 'untitled project', 'website', 'portfolio'}


def clean(value):
    return ' '.join(str(value or '').split())


def title_key(value):
    text = unicodedata.normalize('NFKC', clean(value)).casefold()
    return ' '.join(re.sub(r'[^\w+#.]+', ' ', text).split())


def full_title(row):
    display = clean(row.get('display_title'))
    title = clean(row.get('title') or row.get('name') or row.get('project'))
    subtitle = clean(row.get('subtitle'))
    return display or (title + ' — ' + subtitle if title and subtitle else title)


def parts(value):
    text = clean(value)
    # At least one adjacent space for ASCII hyphens: Job-AI-Helper is a name.
    # A trailing parenthesis may be legacy header metadata, not a new project.
    m = re.match(r'^(.+?)(?:\s+[-–—]\s*|\s*[-–—]\s+|:\s*)(.+)$', text)
    if not m:
        m = re.match(r'^(.+?)\s*[([]([^()\[\]]+)[)\]]$', text)
    if m:
        left, right = (title_key(x) for x in m.groups())
        if left and right:
            return left, right
    return title_key(text), ''


def _compatible_ids(left, right):
    a, b = clean(left.get('project_id')), clean(right.get('project_id'))
    return not (a and b and a != b)


def _base_equal(a, b):
    return bool(a and b and (a == b or a.replace(' ', '') == b.replace(' ', '')))


def _distinctive(key):
    return bool(key and key not in GENERIC and len(key.replace(' ', '')) >= 4)


def _same_family(left, right):
    a, _ = parts(full_title(left)); b, _ = parts(full_title(right))
    return _base_equal(a, b)


def _alias(left, right):
    a, ax = parts(full_title(left)); b, bx = parts(full_title(right))
    if not (_base_equal(a, b) and _distinctive(a) and _distinctive(b)):
        return False
    # Never equate two different nonempty subtitles. Bare-versus-extended or
    # a spacing-only variation is allowed; exact full matches were tried first.
    if ax and bx:
        return ax == bx
    return True


def resolve_project(row, candidates):
    """Return (unique original record, method) or (None, diagnostic)."""
    rows = [r for r in candidates if isinstance(r, dict)]
    ident = clean(row.get('project_id'))
    if ident:
        matched = [r for r in rows if clean(r.get('project_id')) == ident]
        if matched:
            return (matched[0], 'project_id') if len(matched) == 1 else (None, 'ambiguous_project_id')
    key = title_key(full_title(row))
    exact = [r for r in rows if key and title_key(full_title(r)) == key]
    if exact:
        if len(exact) == 1 and _compatible_ids(row, exact[0]):
            return exact[0], 'exact_title'
        return None, 'ambiguous_or_conflicting_exact_title'
    family = [r for r in rows if _same_family(row, r)]
    if len(family) != 1:
        return None, 'ambiguous_title_family' if family else 'no_title_match'
    other = family[0]
    if _compatible_ids(row, other) and _alias(row, other):
        return other, 'unique_subtitle_alias'
    return None, 'conflicting_project_identity'


def mutually_resolve_project(row, own_rows, other_rows):
    """Require one-to-one ownership, not just uniqueness in one direction."""
    match, method = resolve_project(row, other_rows)
    if match is None:
        return None, method
    reverse, _ = resolve_project(match, own_rows)
    return (match, method) if reverse is row else (None, 'ambiguous_reverse_identity')


def registry_scope(master, blueprints):
    """Read-only revision identity; no source analysis, DB or file writes."""
    m = master or {}
    master_key = tuple(clean(m.get(k)) for k in (
        'master_version_id', 'master_version_fingerprint',
        'master_content_fingerprint', 'artifact_sha256'))
    bp = tuple(sorted(tuple(clean(row.get(k)) for k in (
        'blueprint_id', 'blueprint_fingerprint', 'status', 'variant_id'))
        for row in blueprints if isinstance(row, dict)))
    return master_key, bp
