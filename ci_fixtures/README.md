# Sanitized fixtures for manual paid stability tests

The paid workflow does not use files from your Windows computer. GitHub Actions
can access only files committed to the selected Git branch plus configured
Actions secrets.

Create these files before running the paid workflow:

```text
ci_fixtures/phase6a/resume_fixture.docx
ci_fixtures/phase6a/job_description.txt
ci_fixtures/phase6b/debug_bundle.json
```

## Privacy warning

This repository is public. Do not commit:

- your real résumé;
- personal contact information;
- private employer or internship data;
- API keys;
- a full debug bundle containing information you do not want public.

Use a synthetic or thoroughly anonymized résumé and debug bundle. Keep the
fixture structure representative, but replace names, email addresses, phone
numbers, URLs, company-confidential text, and identifying project details.

## Phase 6A fixture

`resume_fixture.docx` should be a valid DOCX that the existing parser accepts.
`job_description.txt` should be UTF-8 plain text.

## Phase 6B fixture

Generate Projects and Skills once from a synthetic/anonymized application, then
use **Download Full Debug Bundle JSON**. Review and sanitize every field before
saving it as:

```text
ci_fixtures/phase6b/debug_bundle.json
```

The bundle must retain:

```text
analysis_report.stable_analysis
project_tailoring_inputs.evidence_items
```

## API secrets

Create the GitHub Environment:

```text
paid-api-tests
```

Add only the provider secret needed by the selected model:

```text
OPENAI_API_KEY
ANTHROPIC_API_KEY
GEMINI_API_KEY
```

Add yourself as a required reviewer so each paid job pauses before receiving
the environment secret.

A workflow run uses the API credential stored in that environment. The provider
account/project that owns that credential is charged for the calls.
