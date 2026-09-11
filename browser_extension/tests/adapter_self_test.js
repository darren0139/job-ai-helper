"use strict";

const assert = require("node:assert/strict");

globalThis.JobAIJDCleaning = require("../jd_cleaning.js");
const registry = require("../adapters/registry.js");
registry.register(require("../adapters/generic.js"));
registry.register(require("../adapters/careers_gov.js"));
registry.register(require("../adapters/greenhouse.js"));

function mockDocument(selectors = {}) {
  return {
    querySelector(selector) {
      return selectors[selector] || null;
    },
  };
}

assert.equal(
  registry.resolve({
    host: "jobs.careers.gov.sg",
    url: "https://jobs.careers.gov.sg/jobs/example",
    document: mockDocument(),
  }).id,
  "careers_gov"
);

assert.equal(
  registry.resolve({
    host: "boards.greenhouse.io",
    url: "https://boards.greenhouse.io/example/jobs/123",
    document: mockDocument(),
  }).id,
  "greenhouse"
);

assert.equal(
  registry.resolve({
    host: "careers.example.com",
    url: "https://careers.example.com/jobs?gh_jid=123",
    document: mockDocument(),
  }).id,
  "greenhouse"
);

assert.equal(
  registry.resolve({
    host: "careers.example.com",
    url: "https://careers.example.com/jobs/123",
    document: mockDocument(),
  }).id,
  "generic"
);

const fakeDescription = {
  innerText:
    "What the role is\n" +
    "Build reliable systems. ".repeat(20) +
    "\nWhat we are looking for\nPython and Linux.",
};
const fakeTitle = { innerText: "Platform Engineer" };
const fakeLocation = { innerText: "Singapore" };

const greenhouse = registry.resolve({
  host: "boards.greenhouse.io",
  url: "https://boards.greenhouse.io/example/jobs/123",
  document: mockDocument(),
});

const extracted = greenhouse.extractJob({
  host: "boards.greenhouse.io",
  url: "https://boards.greenhouse.io/example/jobs/123",
  documentTitle: "Job Application for Platform Engineer at Example Co",
  headings: ["Platform Engineer"],
  rawText: fakeDescription.innerText + "\nApply for this job\nFirst Name",
  textOf(element) {
    return element?.innerText || "";
  },
  document: mockDocument({
    '[data-testid="job-description"]': fakeDescription,
    "h1": fakeTitle,
    ".location": fakeLocation,
  }),
});

assert.equal(extracted.identity.title, "Platform Engineer");
assert.equal(extracted.identity.company, "Example Co");
assert.equal(extracted.identity.location, "Singapore");
assert.equal(
  extracted.isolated.strategy,
  "greenhouse_job_description_dom_v1"
);
assert.doesNotMatch(extracted.isolated.jdText, /First Name/);

console.log("adapter_self_test_v4: passed");
