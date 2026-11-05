# Stage 1 — read-only browser agent

This runs the **real Job AI Helper extension's** content-script actions inside a fresh Playwright Chromium profile. The dedicated `agent_probe.html` page is an extension-owned controller. It injects the same files as `popup.js`, then requests only `JOB_AI_EXTRACT_PAGE` and `JOB_AI_SCAN_FIELDS` from `content.js`.

Stage 1 **does not** call `JOB_AI_AUTOFILL`, click application buttons, upload files, use the localhost bridge, call models, or write into the application database. The report omits raw job descriptions, nearby field text, form values and full URLs. It does not yet support cross-origin embedded Greenhouse forms or autonomous pagination.

## Setup (Windows CMD, from project root)

```cmd
python -m pip install playwright
python -m playwright install chromium
python -m unittest tests.test_autonomous_job_agent_stage1 -v
```

## Run the local smoke test

```cmd
python -m job_agent.browser_stage1 --fixture --json
```

The agent starts a local fixture server, launches a **separate Chromium profile**, loads your existing unpacked extension, opens the fixture automatically, invokes the existing extraction and scan actions and exits. No Streamlit process, SQLite database or Ollama is needed. The fixture's fields must remain unchanged.

If running on a host without a display, use `--headless` **for the fixture only**.

## Inspect one live HTTPS job page (manual permission gate)

```cmd
python -m job_agent.browser_stage1 --url "https://boards.greenhouse.io/EXAMPLE/jobs/123" --allow-host boards.greenhouse.io --json
```

Supply a real job URL with the exact hostname in `--allow-host`. A Chromium window opens with the probe page. If the extension has no permission yet, **click “Grant access to this site”** and approve the Chromium permission prompt. The probe waits up to 90 seconds. Only the approved hostname is navigable as the primary page; redirected destinations are refused. Permission is temporary because the browser profile is deleted after the run.

No site login is imported from your personal Chrome profile. Sites needing authentication will require a separate approved capability later. Never use this to bypass access controls, CAPTCHA or site restrictions. LinkedIn remains capture-only and should not be targeted for automated interactions.

## Limitations

- One page at a time. No automated page-to-page application navigation yet.
- The existing extension sees the top-level DOM, not inaccessible cross-origin iframes.
- Headed Chromium required for live-site permission consent.
- First live run requires manual host approval; no broad permanent site access is requested.
- A green synthetic smoke test is not proof of compatibility with a real job board.
