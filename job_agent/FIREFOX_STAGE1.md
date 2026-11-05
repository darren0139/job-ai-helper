# Firefox Stage 1 — optional read-only browser agent

This is a separate, opt-in Firefox runner. It reuses the existing Job AI Helper
`mapping.js`, adapters, `content.js`, `agent_probe.html`, and `agent_probe.js`.
The Chromium runner and production extension manifest are unchanged.

## Setup

Install ordinary Firefox on Windows, then in the repo virtualenv:

```cmd
python -m pip install -U selenium
```

Selenium Manager normally provisions GeckoDriver automatically. Unlike Chromium
Stage 1, **Playwright Firefox is not used to side-load extensions**. Selenium
creates an isolated temporary Firefox session, installs an unsigned temporary
Firefox version of the extension, and quits/removes it after inspecting one URL.
The Firefox bundle exists only in a temporary folder.

## Tests and smoke

```cmd
python -m unittest tests.test_autonomous_job_agent_firefox_stage1 -v
python -m job_agent.browser_firefox_stage1 --fixture --json
```

If Firefox displays the Job AI Helper **Stage 1 Read-only Probe**, approve any
site permission by clicking **Grant access to this site**. This is the sole
permission action; the script does not click it on your behalf.

To test a user-approved live Greenhouse application page (read-only):

```cmd
python -m job_agent.browser_firefox_stage1 --url "https://job-boards.greenhouse.io/okx/jobs/8045415003" --allow-host job-boards.greenhouse.io --json
```

Run the existing Chromium command for comparison:

```cmd
python -m job_agent.browser_stage1 --url "https://job-boards.greenhouse.io/okx/jobs/8045415003" --allow-host job-boards.greenhouse.io --json
```

### Limitations

- **No autofill, attachments, submission, multi-page navigation, database writes, or model calls.**
- Does not apply to user's normal Firefox profile, and does not install a permanent extension.
- Requires a visible browser window for site-permission approval.
- Firefox WebDriver follows HTTP redirects before the runner validates the final
  URL. If the final URL has a different host, the runner stops without scanning.
  This is not a network isolation boundary for a malicious site.
- Only the top-level page's form state is integrity-hashed; embedded iframes
  need separate tests in later stages.
- Test live sites only when appropriate and permitted, and never click Submit.
- This runner still requires a live Windows/Firefox smoke test: unit tests
  cannot establish GeckoDriver + extension + real form interoperability.
