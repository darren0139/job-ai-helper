"use strict";

const assert = require("node:assert/strict");

globalThis.JobAIJobPostingJsonLd = require("../adapters/job_posting_jsonld.js");
const registry = require("../adapters/registry.js");

registry.register(require("../adapters/generic.js"));
registry.register(require("../adapters/structured_job.js"));
registry.register(require("../adapters/successfactors.js"));

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

const directDocument = mockDocument({
  selectors: {
    ".jobdescription": element(
      "Responsibilities\n" +
      "Build and operate enterprise systems. ".repeat(18) +
      "\nRequirements\nPython, Linux and CI/CD."
    ),
    ".jobTitle": element("Platform Engineer"),
    ".jobLocation": element("Singapore"),
  },
});

const directAdapter = registry.resolve({
  host: "career5.successfactors.eu",
  url:
    "https://career5.successfactors.eu/sfcareer/" +
    "jobreqcareer?jobId=27372&company=gieseckede",
  document: directDocument,
});
assert.equal(directAdapter.id, "successfactors");

const directExtracted = directAdapter.extractJob({
  host: "career5.successfactors.eu",
  url:
    "https://career5.successfactors.eu/sfcareer/" +
    "jobreqcareer?jobId=27372&company=gieseckede",
  documentTitle: "Platform Engineer | Careers",
  headings: ["Platform Engineer"],
  document: directDocument,
  rawText: directDocument.querySelector(".jobdescription").innerText,
  textOf(target) {
    return target?.innerText || "";
  },
});
assert.equal(directExtracted.identity.title, "Platform Engineer");
assert.equal(directExtracted.identity.company, "gieseckede");
assert.equal(directExtracted.identity.location, "Singapore");
assert.equal(
  directExtracted.isolated.strategy,
  "successfactors_job_description_dom_v4"
);

// Branded SAP Career Site Builder-style page:
// branded host + /job/.../<numeric id> + SuccessFactors job-description DOM.
const sapDocument = mockDocument({
  selectors: {
    ".jobdescription": element(
      "We help the world run better.\n" +
      "Develop enterprise mobile and AI features. ".repeat(18)
    ),
    ".jobTitle": element(
      "SAP Intern - Full Stack Developer - SAP Build Mobile and Agentic Qualities"
    ),
    ".jobLocation": element("Singapore, SG, 117440"),
    'meta[property="og:site_name"]': element("", {
      content: "SAP Jobs",
    }),
  },
});

const sapAdapter = registry.resolve({
  host: "jobs.sap.com",
  url:
    "https://jobs.sap.com/job/" +
    "Singapore-SAP-Intern-Full-Stack-Developer-117440/1434449133/",
  document: sapDocument,
});
assert.equal(sapAdapter.id, "successfactors");

const sapExtracted = sapAdapter.extractJob({
  host: "jobs.sap.com",
  url:
    "https://jobs.sap.com/job/" +
    "Singapore-SAP-Intern-Full-Stack-Developer-117440/1434449133/",
  documentTitle:
    "SAP Intern - Full Stack Developer - SAP Build Mobile and Agentic Qualities Job Details | SAP",
  headings: ["SAP Intern - Full Stack Developer - SAP Build Mobile and Agentic Qualities"],
  document: sapDocument,
  rawText: sapDocument.querySelector(".jobdescription").innerText,
  textOf(target) {
    return target?.innerText || "";
  },
});
assert.equal(sapExtracted.identity.company, "SAP");
assert.equal(
  sapExtracted.isolated.strategy,
  "successfactors_job_description_dom_v4"
);

// G+D branded page exposes a direct SuccessFactors apply URL in the page.
const gdApplyLink = element("", {
  href:
    "https://career5.successfactors.eu/career" +
    "?company=gieseckede&career_job_req_id=27372" +
    "&career_ns=job_application",
});
const gdDocument = mockDocument({
  selectors: {
    ".jobdescription": element(
      "Job Summary\n" +
      "Support the end-to-end supply chain operations. ".repeat(18)
    ),
    ".jobTitle": element("Apply now »"),
    "h1": element("Supply Chain Analyst"),
    ".jobLocation": element("Singapore, SG"),
    [
      'a[href*=".successfactors.com/"], ' +
      'a[href*=".successfactors.eu/"], ' +
      'form[action*=".successfactors.com/"], ' +
      'form[action*=".successfactors.eu/"]'
    ]: gdApplyLink,
  },
});

const gdAdapter = registry.resolve({
  host: "careers.gi-de.com",
  url:
    "https://careers.gi-de.com/GieseckeDevrientMS/job/" +
    "Singapore-Supply-Chain-Analyst/1408155433/",
  document: gdDocument,
});
assert.equal(gdAdapter.id, "successfactors");

const gdExtracted = gdAdapter.extractJob({
  host: "careers.gi-de.com",
  url:
    "https://careers.gi-de.com/GieseckeDevrientMS/job/" +
    "Singapore-Supply-Chain-Analyst/1408155433/",
  documentTitle:
    "Supply Chain Analyst Job Details | Giesecke+Devrient",
  headings: ["Supply Chain Analyst"],
  document: gdDocument,
  rawText:
    gdDocument.querySelector(".jobdescription").innerText +
    "\nhttps://career5.successfactors.eu/career" +
    "?company=gieseckede&career_job_req_id=27372",
  textOf(target) {
    return target?.innerText || "";
  },
});
assert.equal(gdExtracted.identity.title, "Supply Chain Analyst");
assert.equal(gdExtracted.identity.company, "Giesecke+Devrient");
assert.equal(
  gdExtracted.isolated.strategy,
  "successfactors_job_description_dom_v4"
);

console.log("successfactors_self_test_v432: passed");
