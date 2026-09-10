# Job AI Helper — Browser Integration POC v2

This extension is the second browser-integration POC.

It keeps the browser-side work deterministic and local:

1. Capture the current job page.
2. Preserve the complete visible page for debugging.
3. Produce a cleaner Job AI Helper-ready JD text payload.
4. Scan standard form controls.
5. Fill only a conservative whitelist of saved candidate facts.
6. Optionally connect to the local Job AI Helper bridge.

It does **not** call OpenAI, ChatGPT Work, Codex, or any external API.

## Why raw page capture and Clean JD text are separate

`capture.raw_visible_text` is diagnostic evidence of what the browser saw.

`job.jd_text` is the text intended to move toward Job AI Helper's existing
JD-analysis pipeline. For Careers@Gov, v2 isolates the role sections and excludes
the application-process/site footer material where possible.

The extension does not create the final structured JD profile. Job AI Helper's
existing analyzer remains responsible for fields such as required skills,
preferred skills, technologies, responsibilities, soft skills, buzzwords, and
deal breakers.

## Local bridge

Start the bridge from the repository root:

```bat
python -m browser_integration.bridge_server
```

It binds to `127.0.0.1` only and prints a random token.

Paste that token into the extension and click **Connect + load profile**.

The bridge exposes only:

- health
- the saved Application Profile
- pending browser JD capture save/read operations

Browser requests require the random bridge token. CORS responses are provided
only to Chrome-extension origins, not ordinary webpages.

## Careers@Gov improvements

v2 adds:

- Careers@Gov-specific JD section isolation
- company/title extraction
- composite `Full name = first_name + last_name`
- Notice period mapping
- richer unmatched SAP UI5 diagnostics
- additional required-state hints

Identity numbers, citizenship, permanent residency, salary, work authorization,
demographics, declarations, and submission remain deliberately unmapped.

## Load/reload the extension

After applying v2, open:

- Chrome: `chrome://extensions`
- Edge: `edge://extensions`

Find Job AI Helper and click **Reload**.

## Test order

1. Start the local bridge.
2. Paste the bridge token and connect.
3. Open the Careers@Gov job page.
4. Click **Extract clean JD**.
5. Confirm:
   - `capture.raw_visible_text` is the whole visible capture.
   - `job.jd_text` contains the JD sections without the site footer.
6. Click **Save JD to Job AI Helper**.
7. In Streamlit, open Profile & Evidence and inspect **Browser JD Capture Inbox**.
8. On the application form, click **Scan form fields**.
9. Review mappings/diagnostics.
10. Click **Autofill basic details** and manually inspect every filled field.

The capture inbox is intentionally pending-only in v2. It does not automatically
run the LLM analyzer or create a canonical JD row yet.


## v3 workflow

When Job AI Helper is started with:

```bat
streamlit run app.py
```

Streamlit now owns the localhost bridge lifecycle. A separate bridge terminal is
normally unnecessary.

After pairing the extension once, the stored localhost URL/token are reused and
the extension attempts to reconnect when its popup opens.

Browser captures can be handed into the existing Tailor Resume JD pipeline:

```text
Browser JD Capture Inbox
  -> Use in Tailor Resume
  -> Choose browser capture
  -> Analyse Job Description
  -> existing exact-JD reuse / structured extraction / JD Library workflow
```

The browser source does not bypass the existing JD analyzer, canonical identity,
versioning, ranking, or application-session lifecycle.


## v3.1 Careers@Gov JD cleaning

The Careers@Gov adapter now keeps three distinct outputs:

- `job.jd_text`: role/responsibility/qualification text that may enter the JD analyzer.
- `job.posting_notes`: contract and application-process notices preserved for review,
  but excluded from candidate-fit scoring.
- `job.discarded_tracking_tags`: recruiting tags such as `#LI-HL1`.

The complete page remains available under `capture.raw_visible_text`.

When corrected JD text is saved for the same source URL, older pending captures
for that URL are marked `superseded`. Streamlit and Tailor Resume show only the
current pending capture.
