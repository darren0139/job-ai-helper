(function (root, factory) {
  "use strict";

  let jsonLd = root.JobAIJobPostingJsonLd;
  if (!jsonLd && typeof module !== "undefined" && module.exports) {
    jsonLd = require("./job_posting_jsonld.js");
  }

  const adapter = factory(jsonLd);
  if (root.JobAISiteAdapters) root.JobAISiteAdapters.register(adapter);
  if (typeof module !== "undefined" && module.exports) module.exports = adapter;
})(typeof self !== "undefined" ? self : globalThis, function (jsonLd) {
  "use strict";

  const DESCRIPTION_SELECTORS = [
    '[data-automation-id="jobPostingDescription"]',
    '[data-automation-id="jobPostingDescriptionText"]',
    'div[data-automation-id="jobPostingDescription"]',
  ];

  const TITLE_SELECTORS = [
    '[data-automation-id="jobPostingHeader"] h1',
    '[data-automation-id="jobPostingHeader"] h2',
    'h1[data-automation-id="jobPostingHeader"]',
    'h2[data-automation-id="jobPostingHeader"]',
    '[data-automation-id="jobPostingHeader"]',
  ];

  const LOCATION_SELECTORS = [
    '[data-automation-id="locations"]',
    '[data-automation-id="location"]',
  ];

  function clean(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function querySelectorSafe(documentObject, selector) {
    try {
      return documentObject?.querySelector?.(selector) || null;
    } catch (_error) {
      return null;
    }
  }

  function text(context, element) {
    if (!element) return "";
    if (typeof context.textOf === "function") {
      return String(context.textOf(element) || "").trim();
    }
    return String(element.innerText || element.textContent || "").trim();
  }

  function firstText(context, selectors) {
    for (const selector of selectors) {
      const value = text(context, querySelectorSafe(context.document, selector));
      if (value) return value;
    }
    return "";
  }

  function normaliseDescriptionText(value) {
    return String(value || "")
      .replace(/\u00a0/g, " ")
      .replace(/\r\n?/g, "\n")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function cleanWorkdayDescription(value, host) {
    const original = normaliseDescriptionText(value);
    if (!original) return "";

    let result = original;
    const hostValue = String(host || "").toLowerCase();

    if (hostValue.includes("razer.")) {
      const startMatch = result.match(/\bJob Responsibilities\s*:\s*/i);
      if (startMatch?.index != null && startMatch.index < 1500) {
        result = result.slice(startMatch.index);
      }

      const prerequisiteMatch = result.match(/\bPre-Requisites\s*:\s*/i);
      if (prerequisiteMatch?.index != null) {
        const tail = result.slice(
          prerequisiteMatch.index,
          prerequisiteMatch.index + 700
        );
        if (/Equal Opportunity Employer|Razer is proud/i.test(tail)) {
          result = result.slice(0, prerequisiteMatch.index);
        }
      }

      result = result
        .replace(/^Job Responsibilities\s*:\s*/i, "Job Responsibilities\n")
        .replace(/\s+Job Scope\s+/i, "\n\nJob Scope\n")
        .replace(/\s+Candidate Requirements\s+/i, "\n\nCandidate Requirements\n");
    }

    result = result
      .split("\n")
      .filter((line) => !/^\s*#LI-[A-Za-z0-9_-]+\s*$/i.test(line))
      .join("\n");

    result = normaliseDescriptionText(result);
    return result.length >= 120 ? result : original;
  }

  function workdayHost(host) {
    const value = String(host || "").toLowerCase();
    return value === "myworkdayjobs.com" || value.endsWith(".myworkdayjobs.com");
  }

  function companyFromMeta(documentObject) {
    const meta =
      querySelectorSafe(documentObject, 'meta[property="og:site_name"]') ||
      querySelectorSafe(documentObject, 'meta[name="application-name"]');
    return clean(meta?.getAttribute?.("content"))
      .replace(/\s+(careers?|jobs?)$/i, "")
      .trim();
  }

  function parsedDocumentTitle(documentTitle, title) {
    let value = clean(documentTitle);
    if (!value) return "";
    if (title && value.toLowerCase().startsWith(title.toLowerCase())) {
      value = value.slice(title.length).replace(/^[\s|–—-]+/, "").trim();
    }
    return value.replace(/\s+(careers?|jobs?)$/i, "").trim();
  }

  function domExtraction(context) {
    const description = cleanWorkdayDescription(
      firstText(context, DESCRIPTION_SELECTORS),
      context.host
    );
    if (description.length < 120) return null;

    const title =
      firstText(context, TITLE_SELECTORS) ||
      clean((context.headings || [])[0]);
    const location = firstText(context, LOCATION_SELECTORS);
    const company =
      companyFromMeta(context.document) ||
      parsedDocumentTitle(context.documentTitle, title);

    return {
      identity: { title, company, location },
      isolated: {
        jdText: description,
        postingNotes: [],
        discardedTrackingTags: [],
        strategy: "workday_job_description_dom_v2",
        confidence: description.length >= 300 ? "high" : "medium",
      },
    };
  }

  return {
    id: "workday",
    version: "workday-adapter-v2",
    priority: 95,
    dynamic: true,

    matches(context) {
      return workdayHost(context.host);
    },

    extractJob(context) {
      const structured = jsonLd?.extract?.(context.document);
      if (structured?.isolated?.jdText) {
        structured.isolated.jdText = cleanWorkdayDescription(
          structured.isolated.jdText,
          context.host
        );
        structured.isolated.strategy = "workday_job_posting_jsonld_v2";
        return structured;
      }
      return domExtraction(context);
    },

    fieldHints() { return []; },
    getControls() { return null; },

    diagnostics() {
      return {
        framework: "workday_dynamic_job_page",
        waits_for_stable_capture: true,
      };
    },
  };
});
