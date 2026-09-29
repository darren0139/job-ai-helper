"use strict";

const assert = require("node:assert/strict");

globalThis.JobAIJobPostingJsonLd = require("../adapters/job_posting_jsonld.js");
const registry = require("../adapters/registry.js");
registry.register(require("../adapters/generic.js"));
registry.register(require("../adapters/structured_job.js"));
registry.register(require("../adapters/workday.js"));
registry.register(require("../adapters/phenom.js"));

function element(text, attrs = {}) {
  return {
    innerText: text,
    textContent: text,
    getAttribute(name) {
      return attrs[name] || "";
    },
  };
}

function mockDocument({ selectors = {}, selectorLists = {} } = {}) {
  return {
    querySelector(selector) {
      return selectors[selector] || null;
    },
    querySelectorAll(selector) {
      return selectorLists[selector] || [];
    },
  };
}

const workdayPosting = {
  "@context": "https://schema.org",
  "@type": "JobPosting",
  title: "Applied AI Intern",
  hiringOrganization: {
    "@type": "Organization",
    name: "Razer",
  },
  jobLocation: {
    "@type": "Place",
    address: {
      "@type": "PostalAddress",
      addressLocality: "Singapore",
      addressCountry: "SG",
    },
  },
  description:
    "<p>Join the applied AI team.</p><h2>Responsibilities</h2>" +
    "<p>" + "Build and evaluate AI systems. ".repeat(20) + "</p>",
};

const workdayDocument = mockDocument({
  selectorLists: {
    'script[type="application/ld+json"]': [
      element(JSON.stringify(workdayPosting)),
    ],
  },
});

const workday = registry.resolve({
  host: "razer.wd3.myworkdayjobs.com",
  url: "https://razer.wd3.myworkdayjobs.com/en-US/Careers/job/Singapore/Applied-AI-Intern_JR2026007785",
  document: workdayDocument,
});

assert.equal(workday.id, "workday");
const workdayExtracted = workday.extractJob({
  host: "razer.wd3.myworkdayjobs.com",
  document: workdayDocument,
  documentTitle: "Applied AI Intern | Razer Careers",
  headings: ["Applied AI Intern"],
  rawText: "CAREERS\nApplied AI Intern\nResponsibilities",
  textOf(target) {
    return target?.innerText || "";
  },
});
assert.equal(workdayExtracted.identity.title, "Applied AI Intern");
assert.equal(workdayExtracted.identity.company, "Razer");
assert.equal(workdayExtracted.identity.location, "Singapore, SG");
assert.equal(
  workdayExtracted.isolated.strategy,
  "workday_job_posting_jsonld_v2"
);
assert.match(workdayExtracted.isolated.jdText, /Responsibilities/);

const phenomMarker = element("", { src: "https://cdn.phenompeople.com/app.js" });
const phenomDocument = mockDocument({
  selectors: {
    'script[src*="phenompeople.com"], script[src*="phenompeople"], [data-ph-at-id]':
      phenomMarker,
  },
});

const phenom = registry.resolve({
  host: "careers.thalesgroup.com",
  url: "https://careers.thalesgroup.com/global/en/job/R0321445/Software-DevOps-Engineer-IFE-DCC",
  document: phenomDocument,
});
assert.equal(phenom.id, "phenom");

const expired = phenom.extractJob({
  host: "careers.thalesgroup.com",
  document: phenomDocument,
  documentTitle: "Software DevOps Engineer (IFE DCC) | Thales Group",
  headings: [],
  rawText:
    "We're sorry… the job you are trying to apply for is no longer available.",
  textOf(target) {
    return target?.innerText || "";
  },
});
assert.equal(expired.availability, "unavailable");
assert.equal(expired.isolated.strategy, "phenom_unavailable_v1");
assert.equal(expired.isolated.jdText, "");

const genericStructuredDocument = mockDocument({
  selectorLists: {
    'script[type="application/ld+json"]': [
      element(
        JSON.stringify({
          "@type": "JobPosting",
          title: "Platform Engineer",
          hiringOrganization: { name: "Example Co" },
          description: "Operate production systems. ".repeat(20),
        })
      ),
    ],
  },
});
const structured = registry.resolve({
  host: "jobs.example.com",
  url: "https://jobs.example.com/123",
  document: genericStructuredDocument,
});
assert.equal(structured.id, "structured_job");

console.log("workday_phenom_self_test_v42: passed");
