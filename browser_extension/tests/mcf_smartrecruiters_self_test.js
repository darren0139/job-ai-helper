"use strict";

const assert = require("node:assert/strict");
globalThis.JobAIJobPostingJsonLd = require("../adapters/job_posting_jsonld.js");
const registry = require("../adapters/registry.js");
registry.register(require("../adapters/generic.js"));
registry.register(require("../adapters/structured_job.js"));
registry.register(require("../adapters/mycareersfuture.js"));
registry.register(require("../adapters/smartrecruiters.js"));

function element(text, attrs = {}) {
  return {
    innerText: text,
    textContent: text,
    getAttribute(name) { return attrs[name] || ""; },
  };
}

function mockDocument(selectors = {}, selectorLists = {}) {
  return {
    querySelector(selector) { return selectors[selector] || null; },
    querySelectorAll(selector) { return selectorLists[selector] || []; },
  };
}

// MCF DOM fallback: company is present in visible text, but not in the
// selector fixture. This reproduces the A-IT page behavior seen live.
const mcfDescription =
  "Provide technical support for enterprise software. ".repeat(15) +
  "Troubleshoot incidents, maintain systems and support users.";

const nuisanceCompanyLink = element(
  "More jobs from this company",
  { href: "/company/a-it-investment" }
);

const mcfDomDocument = mockDocument(
  {
    '[data-testid="job-title"]': element("Software Engineer (Technical Support)"),
    '[data-testid="job-description"]': element(mcfDescription),
    'a[href*="/company/"]': nuisanceCompanyLink,
  },
  {
    'a[href*="/company/"], a[href*="/companies/"]': [nuisanceCompanyLink],
  }
);

const mcf = registry.resolve({
  host: "www.mycareersfuture.gov.sg",
  url:
    "https://www.mycareersfuture.gov.sg/job/information-technology/" +
    "software-engineer-a-it-investment-a51a64a40dd448041248b3703484c6e1",
  document: mcfDomDocument,
});
assert.equal(mcf.id, "mycareersfuture");

const mcfRaw = [
  "Software Engineer (Technical Support)",
  "A-IT INVESTMENT PTE. LTD.",
  "Singapore",
  "Job Description",
  mcfDescription,
].join("\n");

const mcfExtracted = mcf.extractJob({
  host: "www.mycareersfuture.gov.sg",
  url:
    "https://www.mycareersfuture.gov.sg/job/information-technology/" +
    "software-engineer-a-it-investment-a51a64a40dd448041248b3703484c6e1",
  document: mcfDomDocument,
  documentTitle:
    "Software Engineer (Technical Support) | MyCareersFuture",
  headings: ["Software Engineer (Technical Support)"],
  rawText: mcfRaw,
  textOf(target) { return target?.innerText || ""; },
});

assert.equal(
  mcfExtracted.identity.title,
  "Software Engineer (Technical Support)"
);
assert.equal(
  mcfExtracted.identity.company,
  "A-IT INVESTMENT PTE. LTD."
);
assert.equal(
  mcfExtracted.isolated.strategy,
  "mycareersfuture_job_description_dom_v3"
);

// SmartRecruiters fixture reproduces the live nuisance H1 followed by the
// actual NCS role heading.
const smartRaw = [
  "Sorry, Internet Explorer 11 is no longer supported by SmartRecruiters",
  "Please update to one of the following browsers:",
  "Software Engineer [Java Core]",
  "Full-time",
  "Company Description",
  "NCS is a leading AI Tech Services company.",
  "Job Description",
  "We are seeking a Software Engineer in Singapore.",
  "Develop, test and maintain high-quality Java applications.",
  "Build reliable backend services and collaborate across teams.",
  "Qualifications",
  "Degree in Computer Science or related field.",
  "Strong Java fundamentals and software engineering practices.",
  "Additional Information",
  "We are committed to equal opportunities.",
  "Job Location",
  "Singapore",
].join("\n");

const smartDocument = mockDocument({
  "h1": element(
    "Sorry, Internet Explorer 11 is no longer supported by SmartRecruiters"
  ),
});

const smart = registry.resolve({
  host: "jobs.smartrecruiters.com",
  url:
    "https://jobs.smartrecruiters.com/NCS3/" +
    "6000000001045727-software-engineer-java-core-",
  document: smartDocument,
});
assert.equal(smart.id, "smartrecruiters");

const smartExtracted = smart.extractJob({
  host: "jobs.smartrecruiters.com",
  url:
    "https://jobs.smartrecruiters.com/NCS3/" +
    "6000000001045727-software-engineer-java-core-",
  document: smartDocument,
  documentTitle: "NCS Software Engineer [Java Core] | SmartRecruiters",
  headings: [
    "Sorry, Internet Explorer 11 is no longer supported by SmartRecruiters",
    "Software Engineer [Java Core]",
    "Company Description",
    "Job Description",
    "Qualifications",
    "Additional Information",
    "Job Location",
  ],
  rawText: smartRaw,
  textOf(target) { return target?.innerText || ""; },
});

assert.equal(
  smartExtracted.identity.title,
  "Software Engineer [Java Core]"
);
assert.equal(smartExtracted.identity.company, "NCS");
assert.equal(
  smartExtracted.isolated.strategy,
  "smartrecruiters_sections_v4"
);
assert.ok(
  smartExtracted.isolated.jdText.startsWith(
    "We are seeking a Software Engineer in Singapore."
  )
);
assert.doesNotMatch(
  smartExtracted.isolated.jdText,
  /^n\s*$/m
);
assert.doesNotMatch(
  smartExtracted.isolated.jdText,
  /Internet Explorer/
);
assert.doesNotMatch(
  smartExtracted.isolated.jdText,
  /Company Description/
);
assert.match(
  smartExtracted.isolated.jdText,
  /Qualifications/
);
assert.doesNotMatch(
  smartExtracted.isolated.jdText,
  /Additional Information/
);

console.log("mcf_smartrecruiters_self_test_v443: passed");
