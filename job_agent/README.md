# Job AI Helper — Autonomous Job Agent, Stage 0

This is a **read-only, deterministic dry-run planner**. It produces *review candidates*
from existing Job Finder records and Job Match snapshots. It is not an autonomous
browser controller and never prepares, files, or submits an application.

From the repository root:

```cmd
python -m unittest discover -s tests -p test_autonomous_job_agent_stage0.py -v
python -m job_agent.dry_run --db data/applications.db --max-jobs 50 --max-candidates 20
python -m job_agent.dry_run --db data/applications.db --max-jobs 50 --json
```

The database must already exist. All SQLite connections used by this CLI are
`mode=ro` with `PRAGMA query_only=ON`; no schema initialization, migrations,
matching runs, model calls, or browser actions occur.

## Review candidate conditions

- A real discovered-job identity, active lifecycle, usable JD and no recorded expiration.
- Not hidden by the existing Job Finder hide rules.
- A syntactically safe HTTPS review destination in the conservative ATS host allowlist.
  If an external application URL is unapproved but the source page is approved,
  it uses the source as a **review link only**, with a warning reason.
- A **current** persisted match snapshot with matching JD content hash, current
  evidence fingerprint, match/scoring/taxonomy versions, and ranking version.
- `ranking_eligible is True`, using the existing Job Finder ranking contract.

A candidate is **not** proof of applicant suitability; the deterministic
alignment score and important gap count are displayed for human assessment.
The planner does not invent a job-fit cutoff or ignore unmatched requirements.

Rows are `review_candidate`, `hold`, `reject`, or `skip`. Candidates use the
existing Job Finder `best_match_sort_key` and a deterministic queue-size cap.
The planner never executes queued actions or persists the queue. Its JSON is
printed to stdout only, with no full JD, résumé, or evidence library included.

## Known boundaries before Stage 1

- No web crawling, Playwright, extension messaging or navigation.
- No persistent task queue, retry/resume, document uploads, autofill, or submissions.
- No reconciliation with previously **submitted** applications in the application tracker.
- The allowlist is a **review-link filter**, not authority to automate that website.
- A real browser-action policy must separately check website terms, navigational
  permissions, explicit user approvals, and domain-specific safety constraints.

Only the package and focused tests are added in Stage 0. Existing scoring,
taxonomy, database schema, extension, bridge and Streamlit modules remain unchanged.
