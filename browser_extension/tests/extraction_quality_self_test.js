"use strict";

const assert = require("node:assert/strict");
globalThis.JobAIJobPostingJsonLd = require("../adapters/job_posting_jsonld.js");

const workday = require("../adapters/workday.js");
const phenom = require("../adapters/phenom.js");
const successfactors = require("../adapters/successfactors.js");
const smartrecruiters = require("../adapters/smartrecruiters.js");
const greenhouse = require("../adapters/greenhouse.js");

function element(text, attrs = {}) {
  return {
    innerText: text,
    textContent: text,
    getAttribute(name) { return attrs[name] || ""; },
  };
}

function mockDocument({ selectors = {}, selectorLists = {} } = {}) {
  return {
    querySelector(selector) { return selectors[selector] || null; },
    querySelectorAll(selector) { return selectorLists[selector] || []; },
  };
}

function jsonLdDocument(posting, selectors = {}) {
  return mockDocument({
    selectors,
    selectorLists: {
      'script[type="application/ld+json"]': [
        element(JSON.stringify(posting)),
      ],
    },
  });
}

function ctx({
  host,
  url,
  document,
  documentTitle = "",
  headings = [],
  rawText = "",
}) {
  return {
    host,
    url,
    document,
    documentTitle,
    headings,
    rawText,
    textOf(target) {
      return target?.innerText || target?.textContent || "";
    },
  };
}

// Razer / Workday
const razerPosting = {
  "@context": "https://schema.org",
  "@type": "JobPosting",
  title: "Applied AI Intern",
  hiringOrganization: { name: "Razer (Asia-Pacific) Pte. Ltd" },
  jobLocation: {
    address: { addressLocality: "Singapore", addressCountry: "SG" },
  },
  description:
    "<p>Joining Razer will place you on a global mission to revolutionize gaming.</p>" +
    "<p>Job Responsibilities : Applied AI Intern to support multimodal and agentic AI features. " +
    "Job Scope Support evaluation and benchmarking of models and agent workflows. " +
    "Candidate Requirements Strong Python and SQL skills with analytical problem solving. " +
    "Pre-Requisites : Razer is proud to be an Equal Opportunity Employer. Are you game?</p>",
};
const razer = workday.extractJob(ctx({
  host: "razer.wd3.myworkdayjobs.com",
  url: "https://razer.wd3.myworkdayjobs.com/en-US/Careers/job/Singapore/Test",
  document: jsonLdDocument(razerPosting),
  documentTitle: "Applied AI Intern",
  headings: ["Applied AI Intern"],
  rawText: "Applied AI Intern",
}));
assert.equal(razer.isolated.strategy, "workday_job_posting_jsonld_v2");
assert.match(razer.isolated.jdText, /^Job Responsibilities/);
assert.match(razer.isolated.jdText, /Candidate Requirements/);
assert.doesNotMatch(razer.isolated.jdText, /Joining Razer/);
assert.doesNotMatch(razer.isolated.jdText, /Pre-Requisites/);
assert.doesNotMatch(razer.isolated.jdText, /Equal Opportunity Employer/);

// Thales / Phenom
const thalesPosting = {
  "@context": "https://schema.org",
  "@type": "JobPosting",
  title: "Software DevOps Engineer",
  hiringOrganization: { name: "Thales" },
  jobLocation: {
    address: { addressLocality: "Singapore", addressCountry: "SG" },
  },
  description:
    "<p>Location: Singapore</p>" +
    "<p>Thales is a global technology leader trusted by governments and enterprises.</p>" +
    "<p>In Singapore, Thales has been a trusted partner since 1973.</p>" +
    "<h2>In-Flyt Experience (IFE)</h2>" +
    "<p>This business line is digitalising its platform.</p>" +
    "<h2>Responsibilities:</h2><p>Build CI/CD pipelines and cloud services.</p>" +
    "<h2>Requirements:</h2><p>Kubernetes, Terraform and Python.</p>" +
    "<h2>Other Information:</h2><p>Working Location: Suntec City</p>" +
    "<p>At Thales, we’re committed to fostering a workplace where respect and trust matter.</p>",
};
const thales = phenom.extractJob(ctx({
  host: "careers.thalesgroup.com",
  url: "https://careers.thalesgroup.com/global/en/job/TEST/Software-DevOps-Engineer",
  document: jsonLdDocument(thalesPosting),
  documentTitle: "Software DevOps Engineer | Thales Group",
  headings: ["Software DevOps Engineer"],
  rawText: "Software DevOps Engineer",
}));
assert.equal(thales.isolated.strategy, "phenom_job_posting_jsonld_v2");
assert.match(thales.isolated.jdText, /^In-Flyt Experience/);
assert.doesNotMatch(thales.isolated.jdText, /global technology leader/);
assert.doesNotMatch(thales.isolated.jdText, /^At Thales,/m);
assert.match(thales.isolated.jdText, /Requirements:/);

// SAP / SuccessFactors
const sapText = [
  "We help the world run better",
  "At SAP, we keep it simple and help customers around the world.",
  "Location: Singapore",
  "Duration: 5-6 months",
  "Start Date: January 2027",
  "SAP's Autonomous Enterprise is an AI-native operating model.",
  "Through the internship, you will get to:",
  "Build mobile and agentic AI features.",
  "Skills Required:",
  "JavaScript, Swift, Java, Python and SQL.",
  "#SAPAICareers",
  "#SAPNextGen",
  "Bring out your best",
  "SAP innovations help more than four hundred thousand customers.",
  "We win with inclusion",
  "AI Usage in the Recruitment Process",
  "Requisition ID: 458752 | Work Area: Software-Design and Development",
].join("\n");

const sapDocument = mockDocument({
  selectors: {
    ".jobdescription": element(sapText),
    "h1": element("SAP Intern - Full Stack Developer"),
    ".jobLocation": element("Singapore, SG, 117440"),
    'meta[property="og:site_name"]': element("", { content: "SAP Jobs" }),
  },
});
const sap = successfactors.extractJob(ctx({
  host: "jobs.sap.com",
  url: "https://jobs.sap.com/job/Singapore-Test/123456789/",
  document: sapDocument,
  documentTitle: "SAP Intern - Full Stack Developer Job Details | SAP",
  headings: ["SAP Intern - Full Stack Developer"],
  rawText: sapText,
}));
assert.equal(sap.isolated.strategy, "successfactors_job_description_dom_v4");
assert.match(sap.isolated.jdText, /^Location: Singapore/);
assert.match(sap.isolated.jdText, /Skills Required:/);
assert.doesNotMatch(sap.isolated.jdText, /We help the world run better/);
assert.doesNotMatch(sap.isolated.jdText, /Bring out your best/);
assert.doesNotMatch(sap.isolated.jdText, /#SAPNextGen/);
assert.doesNotMatch(sap.isolated.jdText, /Requisition ID:/);

// G+D / SuccessFactors
const gdText = [
  "Job Summary:",
  "Support the end-to-end hardware supply chain.",
  "Responsibilities:",
  "Coordinate suppliers and logistics.",
  "Job Requirements:",
  "Experience with SAP systems preferred.",
  "$$ We are an equal opportunity employer! We promote diversity.",
  "$$ $$ $$",
  "https://career5.successfactors.eu/career?company=gieseckede&career_job_req_id=27372",
].join("\n");
const gdDocument = mockDocument({
  selectors: {
    ".jobdescription": element(gdText),
    "h1": element("Supply Chain Analyst"),
    ".jobLocation": element("Singapore, SG"),
  },
});
const gd = successfactors.extractJob(ctx({
  host: "careers.gi-de.com",
  url: "https://careers.gi-de.com/GieseckeDevrientMS/job/Test/1408155433/",
  document: gdDocument,
  documentTitle: "Supply Chain Analyst Job Details | Giesecke+Devrient",
  headings: ["Supply Chain Analyst"],
  rawText: gdText,
}));
assert.equal(gd.isolated.strategy, "successfactors_job_description_dom_v4");
assert.doesNotMatch(gd.isolated.jdText, /equal opportunity employer/i);
assert.doesNotMatch(gd.isolated.jdText, /\$\$/);
assert.doesNotMatch(gd.isolated.jdText, /successfactors\.eu\/career/);

// SmartRecruiters / NCS
const smartRaw = [
  "Sorry, Internet Explorer 11 is no longer supported by SmartRecruiters",
  "Please update to one of the following browsers:",
  "Software Engineer [Java Core]",
  "Full-time",
  "Company Description",
  "NCS is a leading AI Tech Services company.",
  "Job Description",
  "We are seeking a Software Engineer in Singapore.",
  "Build reliable Java services and collaborate across teams.",
  "Qualifications",
  "Strong Java fundamentals and data structures.",
  "**Preferred Skills and Experience:**",
  "Spring Boot and Kubernetes.",
  "Additional Information",
  "Equal opportunity information.",
  "Job Location",
  "Singapore",
].join("\n");
const smartDocument = mockDocument({
  selectors: {
    "h1": element(
      "Sorry, Internet Explorer 11 is no longer supported by SmartRecruiters"
    ),
  },
});
const smart = smartrecruiters.extractJob(ctx({
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
}));
assert.equal(smart.identity.title, "Software Engineer [Java Core]");
assert.equal(smart.identity.company, "NCS");
assert.equal(smart.identity.location, "Singapore");
assert.equal(smart.isolated.strategy, "smartrecruiters_sections_v4");
assert.match(
  smart.isolated.jdText,
  /^We are seeking a Software Engineer in Singapore\./
);
assert.doesNotMatch(smart.isolated.jdText, /^n\s*$/m);
assert.doesNotMatch(smart.isolated.jdText, /Company Description/);
assert.doesNotMatch(smart.isolated.jdText, /Additional Information/);
assert.match(smart.isolated.jdText, /Preferred Skills and Experience:/);
assert.doesNotMatch(smart.isolated.jdText, /\*\*/);

// Greenhouse / XTX
const greenhouseText = [
  "The Firm",
  "",
  "XTX Markets is a leading algorithmic trading firm using machine learning.",
  "The firm operates globally with substantial compute infrastructure.",
  "",
  "The Role",
  "",
  "We are hiring a software engineer to join the exchange trading team.",
  "Most of our work is done using C++ and Python.",
  "",
  "Essential Attributes",
  "",
  "Strong knowledge of modern C++ and algorithms is required.",
].join("\n");
const greenhouseDocument = mockDocument({
  selectors: {
    ".job__description": element(greenhouseText),
  },
});
const greenhouseResult = greenhouse.extractJob(ctx({
  host: "job-boards.greenhouse.io",
  url: "https://job-boards.greenhouse.io/xtx/jobs/123",
  document: greenhouseDocument,
  documentTitle: "Job Application for C++ Software Engineer at XTX Markets",
  headings: ["C++ Software Engineer"],
  rawText: greenhouseText,
}));
assert.equal(
  greenhouseResult.isolated.strategy,
  "greenhouse_job_description_dom_v2"
);
assert.match(greenhouseResult.isolated.jdText, /^The Role/);
assert.doesNotMatch(greenhouseResult.isolated.jdText, /^The Firm/m);

console.log("extraction_quality_self_test_v45: passed");
