"use strict";

const assert = require("node:assert/strict");

globalThis.JobAIJobPostingJsonLd = require("../adapters/job_posting_jsonld.js");
const registry = require("../adapters/registry.js");

registry.register(require("../adapters/generic.js"));
registry.register(require("../adapters/structured_job.js"));
registry.register(require("../adapters/linkedin.js"));

function element(text) {
  return {
    innerText: text,
    textContent: text,
    getAttribute() {
      return "";
    },
  };
}

function mockDocument(selectors = {}) {
  return {
    querySelector(selector) {
      return selectors[selector] || null;
    },
    querySelectorAll() {
      return [];
    },
  };
}

const description = [
  "About the job",
  "We are looking for a Software Engineer to build reliable digital products.",
  "",
  "What you will do",
  "Design, develop, test, and operate production software.",
  "Work with APIs, cloud infrastructure, CI/CD, and Kubernetes.",
  "",
  "Requirements",
  "Strong software engineering fundamentals and experience with Python or Java.",
  "Experience with automated testing and version control.",
  "#LI-Hybrid",
  "",
  "Seniority level",
  "Associate",
  "Employment type",
  "Full-time",
  "Job function",
  "Engineering and Information Technology",
  "Similar jobs",
  "Another Software Engineer",
].join("\n");

const documentObject = mockDocument({
  ".job-details-jobs-unified-top-card__job-title h1":
    element("Software Engineer"),
  ".job-details-jobs-unified-top-card__company-name a":
    element("The Digital Company"),
  ".job-details-jobs-unified-top-card__primary-description-container .t-black--light":
    element("Singapore"),
  ".jobs-description__content .jobs-box__html-content":
    element(description),
});

const context = {
  host: "sg.linkedin.com",
  url:
    "https://sg.linkedin.com/jobs/view/" +
    "software-engineer-at-the-digital-company-4460000000",
  document: documentObject,
  documentTitle:
    "Software Engineer at The Digital Company — Singapore | LinkedIn",
  headings: ["Software Engineer"],
  rawText: description,
  textOf(target) {
    return target?.innerText || "";
  },
};

const adapter = registry.resolve(context);
assert.equal(adapter.id, "linkedin");
assert.equal(adapter.version, "linkedin-adapter-v5");
assert.equal(adapter.captureOnly, true);

const extracted = adapter.extractJob(context);
assert.equal(extracted.identity.title, "Software Engineer");
assert.equal(extracted.identity.company, "The Digital Company");
assert.equal(extracted.identity.location, "Singapore");
assert.equal(
  extracted.isolated.strategy,
  "linkedin_job_description_dom_v1"
);
assert.match(extracted.isolated.jdText, /What you will do/);
assert.match(extracted.isolated.jdText, /Requirements/);
assert.doesNotMatch(extracted.isolated.jdText, /About the job/);
assert.doesNotMatch(extracted.isolated.jdText, /Seniority level/);
assert.doesNotMatch(extracted.isolated.jdText, /Employment type/);
assert.doesNotMatch(extracted.isolated.jdText, /Similar jobs/);
assert.doesNotMatch(extracted.isolated.jdText, /#LI-Hybrid/);
assert.deepEqual(
  extracted.isolated.discardedTrackingTags,
  ["#LI-Hybrid"]
);

assert.equal(
  registry.resolve({
    ...context,
    url:
      "https://www.linkedin.com/jobs/search/?" +
      "currentJobId=4460000000&keywords=software",
  }).id,
  "linkedin"
);

const splitPaneReady = {
  ...context,
  url:
    "https://www.linkedin.com/jobs/search/?" +
    "currentJobId=4460000000&keywords=software",
};
const splitPaneExtracted = adapter.extractJob(splitPaneReady);
assert.equal(
  splitPaneExtracted.isolated.strategy,
  "linkedin_job_description_dom_v1"
);
assert.equal(splitPaneExtracted.identity.company, "The Digital Company");

const loggedInDescription = element(description);
const loggedInContext = {
  ...context,
  document: mockDocument({
    "#job-details": loggedInDescription,
  }),
  documentTitle:
    "Software Engineer | The Digital and Intelligence Service (DIS) | LinkedIn",
  headings: ["0 notifications", "About the job"],
  url:
    "https://www.linkedin.com/jobs/view/" +
    "software-engineer-at-the-digital-and-intelligence-service-dis-4177168405/",
};
const loggedInExtracted = adapter.extractJob(loggedInContext);
assert.equal(loggedInExtracted.identity.title, "Software Engineer");
assert.equal(
  loggedInExtracted.identity.company,
  "The Digital and Intelligence Service (DIS)"
);
assert.equal(
  loggedInExtracted.isolated.strategy,
  "linkedin_job_description_dom_v1"
);
const loggedInDiagnostics = adapter.diagnostics(loggedInContext);
assert.equal(
  loggedInDiagnostics.document_title_parse.strategy,
  "document_title_pipe"
);
assert.ok(
  loggedInDiagnostics.description_selectors_found.includes("#job-details")
);

const loggedInRawFallbackContext = {
  ...context,
  document: mockDocument({}),
  documentTitle:
    "Software Engineer | The Digital and Intelligence Service (DIS) | LinkedIn",
  headings: ["0 notifications", "About the job"],
  url:
    "https://www.linkedin.com/jobs/view/" +
    "software-engineer-at-the-digital-and-intelligence-service-dis-4177168405/",
  rawText: [
    "0 notifications",
    "About the job",
    "This is a DXO position and only open to Singaporean citizens",
    "",
    "Who we are looking for:",
    "Build and maintain useful software applications across the stack.",
    "Adhere to software engineering best practices.",
    "… more",
    "",
    "This job alert is on",
    "Software Engineer, Singapore, Singapore",
    "Unlock hiring insights on The Digital and Intelligence Service (DIS)",
    "More jobs",
    "Recommended unrelated job",
  ].join("\n"),
};
const loggedInRawFallback = adapter.extractJob(loggedInRawFallbackContext);
assert.equal(
  loggedInRawFallback.isolated.strategy,
  "linkedin_visible_job_section_v1"
);
assert.equal(loggedInRawFallback.identity.title, "Software Engineer");
assert.equal(
  loggedInRawFallback.identity.company,
  "The Digital and Intelligence Service (DIS)"
);
assert.match(
  loggedInRawFallback.isolated.jdText,
  /only open to Singaporean citizens/
);
assert.doesNotMatch(
  loggedInRawFallback.isolated.jdText,
  /This job alert is on/i
);
assert.doesNotMatch(
  loggedInRawFallback.isolated.jdText,
  /Unlock hiring insights/i
);
assert.doesNotMatch(
  loggedInRawFallback.isolated.jdText,
  /… more/
);

const shellOnlyDocument = mockDocument({});
const shellOnlyContext = {
  ...context,
  url:
    "https://www.linkedin.com/jobs/search/?" +
    "currentJobId=4460000000&keywords=software",
  document: shellOnlyDocument,
  documentTitle: "0 notifications | LinkedIn",
  headings: ["0 notifications", "About the job"],
  rawText: [
    "0 notifications",
    "About the job",
    "This text is long enough to look like a job description but the",
    "selected LinkedIn job panel identity has not rendered yet. ".repeat(8),
  ].join("\n"),
};
const shellOnlyExtracted = adapter.extractJob(shellOnlyContext);
assert.equal(shellOnlyExtracted.notReady, true);
assert.match(shellOnlyExtracted.reason, /not ready/i);
assert.doesNotMatch(
  JSON.stringify(shellOnlyExtracted),
  /linkedin_visible_job_section_v1/
);

assert.equal(
  registry.resolve({
    ...context,
    url:
      "https://www.linkedin.com/jobs/collections/recommended/?" +
      "currentJobId=4460000000",
  }).id,
  "linkedin"
);

assert.equal(
  registry.resolve({
    ...context,
    url: "https://sg.linkedin.com/jobs/search/?keywords=software",
  }).id,
  "generic"
);

console.log("linkedin_self_test_v462: passed");
