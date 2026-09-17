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


## v4 adapter framework

Browser behavior is now selected through a small adapter registry rather than
adding every site-specific rule to `content.js`.

Current adapters:

- `careers_gov`: dedicated Careers@Gov extraction plus SAP/UI5 field hints.
- `greenhouse`: Greenhouse-hosted job extraction, application-form scoping, and
  deterministic hints for common contact/profile fields.
- `generic`: conservative fallback for unknown sites.

Greenhouse can be recognized on `*.greenhouse.io`, on custom pages carrying a
`gh_jid` parameter, and when a Greenhouse iframe is detected. Cross-origin
embedded Greenhouse iframes are detected and reported, but v4 intentionally does
not inject into those frames yet.

The extension still uses `activeTab`; v4 adds no broad website permissions,
mass-tab access, submission, resume upload, or custom-answer generation.

## Application Profile v2

All adapters consume one platform-neutral profile. New repeat facts are middle
name, explicit phone country code, and structured postal address fields. Adapters
translate those canonical facts into site controls.

The profile deliberately does not add government IDs, citizenship/residency,
demographic answers, employer-specific screening answers, or a context-free
work-authorization yes/no flag.


## v4.1 batch prepare

The adapter framework remains authoritative for site-specific extraction and
field hints. Batch prepare adds orchestration around those adapters without
changing their extraction/mapping contracts.

The extension can discover normal web tabs in the current Chrome window and run
two explicit, review-only batch actions over the user's selected tabs:

1. **Capture selected JDs to Job AI Helper**
   - processes selected tabs sequentially;
   - uses the same adapter stack as single-tab capture;
   - posts each capture to the existing localhost `/api/v1/jd-captures` endpoint;
   - creates pending browser-source artifacts only;
   - makes zero model/OpenAI calls.

2. **Autofill safe fields in selected tabs**
   - reuses Application Profile v2 and the existing deterministic whitelist;
   - processes tabs sequentially;
   - does not navigate, upload resumes, generate free-text answers, accept
     declarations, or click submit;
   - makes zero model/OpenAI calls.

### Permission model

The extension keeps localhost access as its only always-on host permission.
Batch mode uses Chrome optional permissions:

- `tabs` is requested only when the user clicks **Discover open tabs**;
- HTTP(S) host access is requested only for sites represented by the user's
  selected tabs.

The manifest declares HTTP(S) patterns only as `optional_host_permissions`;
they are not automatically granted.

### Job AI Helper queue

Multiple captures are stored independently in the existing browser capture
table. Exact duplicate handling and same-URL supersession remain unchanged.
The Streamlit Browser JD Queue shows current pending captures, while Tailor
Resume continues to analyze one explicitly selected JD at a time.


## v4.2 dynamic ATS extraction and batch latency

v4.2 adds platform-level extraction rather than company-specific rules:

- **Workday** for `*.myworkdayjobs.com` career sites.
- **Phenom** for career sites exposing Phenom markers/scripts.
- **Schema.org `JobPosting` JSON-LD** as a reusable structured fallback for
  otherwise unknown sites.
- Existing Careers@Gov and Greenhouse adapters remain unchanged.

Dynamic Workday/Phenom pages are allowed a short readiness window before the
extension captures them. The capture stops early as soon as the extracted job is
stable. The result includes `source.extraction_wait_ms` for diagnostics.

The generic fallback now marks obvious shell captures such as `CAREERS` with no
company as `needs_review` instead of silently saving them as valid JDs. Expired
Phenom jobs are marked `unavailable` and are not sent to the Browser JD Queue.

Batch work is bounded to three tabs at a time rather than being fully serial.
Already-injected current content scripts are reused via a local ping, reducing
repeat script injection. Per-tab results include `elapsed_ms`.

The Streamlit Browser JD Queue includes an explicit refresh button because an
extension write to the local SQLite database does not itself trigger a Streamlit
rerun.

All browser-side extraction, readiness checks, queue writes, and deterministic
autofill remain zero-model-call operations. v4.2 still does not navigate
application flows, upload resumes, generate screening answers, accept
declarations, or submit applications.

## v4.3 SAP SuccessFactors

v4.3 adds a dedicated SAP SuccessFactors Recruiting adapter for direct
SuccessFactors candidate pages such as `career5.successfactors.eu`,
`career10.successfactors.com`, `/sfcareer/jobreqcareer?...`, and URLs carrying
`career_job_req_id`.

Extraction order is schema.org `JobPosting` JSON-LD first, then SuccessFactors
job-description DOM containers such as `.jobdescription`. SuccessFactors is
treated as dynamic, so the v4.2 readiness/stability wait applies automatically.

Company-branded Career Site Builder pages may already be handled by the generic
`JobPosting` structured-data adapter. This adapter intentionally claims strong
SuccessFactors URL signatures only.

No login/account automation, declarations, resume upload, navigation, or submit
behavior is added. Browser capture remains zero-model.

## v4.3.1 Branded SuccessFactors career sites

The v4.3 direct SuccessFactors matcher did not claim branded Career Site Builder
hosts such as `jobs.sap.com` and `careers.gi-de.com`, so those pages could fall
through to `generic_visible_main_text` and lose company identity.

v4.3.1 adds strong branded-site detection using either:

- an outgoing SuccessFactors apply/form URL, or
- a `/job/.../<numeric id>/` career URL together with a known SuccessFactors
  job-description DOM marker.

Company identity is resolved from the page company field, `og:site_name`,
`application-name`, the branded document-title suffix, then the direct
SuccessFactors URL query parameter.

This remains platform-level detection rather than hard-coding SAP or
Giesecke+Devrient as companies. No login, apply, navigation, resume upload,
declaration, or submission automation is added.

## v4.3.2 SuccessFactors title validation

Some branded SuccessFactors Career Site Builder pages reuse broad CSS class
names around their Apply CTA. On Giesecke+Devrient, the v4.3.1 selector order
could therefore capture `Apply now »` as the job title even though the real job
title is the page H1.

v4.3.2 validates title candidates and rejects navigation/CTA labels such as
`Apply now`, `Login/View Profile`, `All Jobs`, `Search Jobs`, `Careers`, and
`Jobs`. It prefers the explicit Career Site Builder title property and H1 before
legacy `.jobTitle` classes, then falls back to filtered visible headings and the
document title.

This change affects title extraction only. Company extraction, JD isolation,
zero-model capture, and the no-submit safety boundary remain unchanged.

## v4.4 MyCareersFuture and SmartRecruiters

v4.4 adds two platform-level JD capture adapters.

MyCareersFuture is capture-only: JSON-LD first, then embedded `__NEXT_DATA__`,
then DOM/visible-section fallback. Salary, employment type, position level and
expiry metadata are kept as posting notes rather than JD scoring text. Expired
jobs are marked unavailable. No Singpass/login/apply automation is added.

SmartRecruiters isolates `Job Description` plus `Qualifications` while excluding
`Company Description`, `Additional Information`, sharing UI and location
widgets from scoring text. JSON-LD and DOM extraction remain fallbacks.

Both adapters preserve zero-model browser capture and the review-only/no-submit
safety boundary.

## v4.4.1 MCF company and SmartRecruiters identity

MyCareersFuture v2 adds company-identity fallbacks for employer links and
Singapore legal-entity names visible near the top of the job page. This fixes
valid MCF DOM captures whose JD was correct but whose company was blank.

SmartRecruiters v2 rejects the global `Sorry, Internet Explorer 11 is no longer
supported by SmartRecruiters` banner as a job title. It selects a plausible
visible heading that matches the document title, then derives the company from
the remaining document-title prefix. This keeps the browser-support banner and
Company Description outside JD identity/scoring.

No application automation, Singpass/login behavior, navigation, or submit
behavior is added.

## v4.4.2 MyCareersFuture company CTA filtering

MyCareersFuture can expose a `/company/` link whose visible label is
`More jobs from this company`. v4.4.1 could mistake that CTA for the employer.

v4.4.2 removes generic company links from direct company selectors, rejects
company-navigation CTA labels, and prefers visible Singapore legal-entity text
before a company-link fallback.

JD extraction, metadata separation, capture-only behavior, and the no-Singpass /
no-submit boundary remain unchanged.

## v4.4.3 SmartRecruiters section boundary

The SmartRecruiters visible-section cleaner searched for the marker
`
job description
` but advanced by only the length of `job description`.
Because the start index pointed at the leading newline, extraction began on the
final `n` of `description`, producing a stray `n` before the first real JD
sentence.

v4.4.3 advances by the full matched marker length and adds a regression test
that the extracted NCS JD starts directly with the first job-description
sentence.

This changes JD section slicing only. SmartRecruiters title/company identity,
MyCareersFuture behavior, zero-model capture, and the no-submit boundary remain
unchanged.

## v4.5 extraction quality pass

v4.5 is based on an audit of the current Browser JD Queue rather than on one
site in isolation.

The pass keeps job requirements/responsibilities intact while reducing text
that can distort JD requirement extraction and scoring:

- **Workday / Razer:** starts at the role-specific `Job Responsibilities`
  content and removes the duplicated employer/EEO tail when the Razer page
  exposes it after `Pre-Requisites`.
- **Phenom / Thales:** removes the generic global-company preamble and generic
  closing while retaining business-line context, responsibilities,
  requirements, and role-specific working information.
- **SuccessFactors / SAP:** removes the generic SAP employer, inclusion,
  recruiting-policy, requisition/footer, and campaign-tag tail while retaining
  internship metadata, role context, responsibilities, and skills.
- **SuccessFactors / G+D:** removes the EEO/template `$$`/application-link tail.
- **SmartRecruiters:** fixes the full `Job Description` marker boundary,
  rejects the browser-warning heading, normalizes emphasis markers, and reads
  `Job Location` separately from the scoring text.
- **Greenhouse:** when a `The Firm` prelude is followed by an explicit
  `The Role`, scoring text starts at `The Role`.

Careers@Gov and MyCareersFuture are intentionally unchanged by this pass because
the audited current captures already isolate their role content well.

No model calls, login automation, navigation, resume upload, declarations, or
application submission are added.

## v4.6 LinkedIn capture adapter

v4.6 adds a capture-only adapter for direct LinkedIn job-detail pages
(`/jobs/view/...`).

Extraction order:

1. schema.org `JobPosting` JSON-LD when present;
2. LinkedIn job-description DOM containers;
3. a conservative `About the job` visible-section fallback.

The adapter captures title, company, location, and the employer-provided job
description while cutting LinkedIn platform metadata such as Seniority level,
Employment type, Job function, Industries, referrals, recommendations, and
Similar jobs. `#LI-*` tags are moved to discarded tracking tags.

LinkedIn search-result pages are intentionally not matched in v1 because their
split-pane URL is not a stable job-posting source and the page contains multiple
job cards.

The adapter is capture-only. It does not automate LinkedIn login, search,
connections, messages, Easy Apply, external Apply, resume upload, declarations,
navigation, or submission.

## v4.6.2 LinkedIn split-pane capture

LinkedIn v2 keeps direct `/jobs/view/...` capture and also recognizes a
specific selected job in LinkedIn's split-pane jobs UI when the URL contains a
numeric `currentJobId`.

Examples that are now eligible for the LinkedIn adapter:

- `/jobs/view/...`
- `/jobs/search/?currentJobId=...`
- `/jobs/collections/.../?currentJobId=...`

A generic `/jobs/search/?keywords=...` page without `currentJobId` is still not
matched, because it does not identify one unambiguous selected job.

The adapter remains capture-only: no login, search crawling, messaging,
connections, Easy Apply, external Apply, resume upload, declarations,
navigation, or submission automation.

## v4.6.4 LinkedIn readiness guard

LinkedIn's split-pane jobs UI can update `currentJobId` before the selected
job title, company, and description panel have finished rendering. v4.6.2
correctly recognized the URL as a LinkedIn job context, but a capture during
that intermediate state could fall through to visible page text and treat
LinkedIn shell UI such as `0 notifications` as job identity.

v4.6.4 hardens this path:

- rejects shell/navigation labels such as `0 notifications`;
- split-pane captures require a plausible title and company;
- split-pane capture accepts JSON-LD or dedicated LinkedIn description DOM;
- disables raw `About the job` fallback on split-pane pages;
- reports `notReady` when the selected job panel has not rendered;
- content.js converts `notReady` into a capture error rather than saving shell
  text;
- direct `/jobs/view/...` pages retain conservative fallback with reliable
  identity.

## v4.6.5 LinkedIn logged-in DOM support

LinkedIn can serve a richer authenticated `www.linkedin.com` job page whose
document title uses `Job title | Company | LinkedIn` rather than the public
`Job title at Company — Location | LinkedIn Jobs` shape.

v4.6.5 adds deterministic support for that variant:

- parses both documented LinkedIn title shapes;
- adds logged-in top-card selector variants for title/company/location;
- keeps the v4.6.4 readiness guard and does not restore unsafe shell fallback;
- adds diagnostics for matched title/company/location selectors;
- records the document-title parse strategy;
- records which description selectors were present.

The known bad pattern from capture 229 (`0 notifications`, blank company,
full LinkedIn shell text) remains rejected. A direct logged-in job whose
document title is `Software Engineer | The Digital and Intelligence Service
(DIS) | LinkedIn` can recover the title/company even when LinkedIn's top-card
class names differ.

## v4.6.6 LinkedIn authenticated raw boundary

The authenticated `www.linkedin.com/jobs/view/...` page can expose a reliable
job title/company through the document title while withholding the dedicated
description DOM. In that case the direct-page raw fallback remains useful, but
LinkedIn appends personalized platform UI after the role description.

The observed boundary is:

`This job alert is on`

v4.6.6 treats `This job alert is on/off` as a hard LinkedIn platform boundary
and removes the collapsed `… more` / `... more` presentation line. This keeps
the actual employer job description while excluding hiring insights, Premium
prompts, company cards, recommended jobs, footer navigation, and language
selectors.

The v4.6.4 readiness guard remains intact. Split-pane pages still do not use
the raw fallback.

## v4.6.7 Batch action responsiveness

Batch capture and batch autofill now acknowledge the first click immediately
before any optional-host permission check or tab work begins.

While either batch action is running:

- the popup shows `Preparing ...` immediately;
- both batch action buttons are disabled;
- Discover Open Tabs and the current tab checkboxes are temporarily disabled;
- repeated clicks are ignored instead of starting overlapping batch runs;
- button text changes to `Capturing…` or `Autofilling…`;
- controls are restored in a `finally` block on success or failure.

The capture pipeline itself is unchanged: batch capture still sends
`JOB_AI_EXTRACT_PAGE` to each selected tab and then POSTs the resulting clean
capture to `/api/v1/jd-captures`.
