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

  const UNAVAILABLE_PATTERNS = [
    /the job you are trying to apply for is no longer available/i,
    /\bthis job is no longer available\b/i,
    /\bthis position is no longer available\b/i,
  ];

  const DESCRIPTION_SELECTORS = [
    '[data-ph-at-id="job-description"]',
    '[data-ph-at-id="job-description-text"]',
    ".job-description",
    ".job-description-text",
  ];

  const TITLE_SELECTORS = [
    '[data-ph-at-id="job-title"]',
    '[data-ph-at-id="job-title-text"]',
    ".job-title",
    "h1",
  ];

  const LOCATION_SELECTORS = [
    '[data-ph-at-id="job-location"]',
    '[data-ph-at-id="job-location-text"]',
    ".job-location",
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

  function companyFromMeta(documentObject) {
    const meta =
      querySelectorSafe(documentObject, 'meta[property="og:site_name"]') ||
      querySelectorSafe(documentObject, 'meta[name="application-name"]');
    return clean(meta?.getAttribute?.("content"))
      .replace(/\s+(careers?|jobs?)$/i, "")
      .trim();
  }

  function cleanPhenomDescription(value, host) {
    const original = normaliseDescriptionText(value);
    if (!original) return "";

    let result = original;
    const hostValue = String(host || "").toLowerCase();

    if (hostValue.includes("thalesgroup.com")) {
      const starts = [
        /^Whom We Are Looking For\s*$/im,
        /^In-Flyt Experience\b.*$/im,
        /^Digital Competence Center\b.*$/im,
      ];

      const startIndexes = starts
        .map((pattern) => result.search(pattern))
        .filter((index) => index >= 0 && index < 2500);
      if (startIndexes.length) {
        result = result.slice(Math.min(...startIndexes));
      }

      const closing = result.search(
        /^At Thales, we[’']re committed to fostering a workplace/im
      );
      if (closing >= 0) result = result.slice(0, closing);
    }

    result = normaliseDescriptionText(result);
    return result.length >= 120 ? result : original;
  }

  function pageUnavailable(rawText) {
    const value = String(rawText || "");
    return UNAVAILABLE_PATTERNS.some((pattern) => pattern.test(value));
  }

  function phenomMarker(documentObject) {
    return Boolean(
      querySelectorSafe(
        documentObject,
        'script[src*="phenompeople.com"], script[src*="phenompeople"], [data-ph-at-id]'
      )
    );
  }

  function phenomHost(host) {
    const value = String(host || "").toLowerCase();
    return value === "phenompeople.com" || value.endsWith(".phenompeople.com");
  }

  function unavailableResult(context) {
    const title = clean(context.documentTitle)
      .replace(/\s+\|\s+.*$/, "")
      .trim();

    return {
      availability: "unavailable",
      identity: {
        title,
        company: "",
        location: "",
      },
      isolated: {
        jdText: "",
        postingNotes: [
          "The source career site reports that this job is no longer available.",
        ],
        discardedTrackingTags: [],
        strategy: "phenom_unavailable_v1",
        confidence: "high",
      },
    };
  }

  function domExtraction(context) {
    const description = cleanPhenomDescription(
      firstText(context, DESCRIPTION_SELECTORS),
      context.host
    );
    if (description.length < 120) return null;

    const title =
      firstText(context, TITLE_SELECTORS) ||
      clean((context.headings || [])[0]);
    const location = firstText(context, LOCATION_SELECTORS);

    return {
      identity: {
        title,
        company: companyFromMeta(context.document),
        location,
      },
      isolated: {
        jdText: description,
        postingNotes: [],
        discardedTrackingTags: [],
        strategy: "phenom_job_description_dom_v2",
        confidence: description.length >= 300 ? "high" : "medium",
      },
    };
  }

  return {
    id: "phenom",
    version: "phenom-adapter-v2",
    priority: 90,
    dynamic: true,

    matches(context) {
      return phenomHost(context.host) || phenomMarker(context.document);
    },

    extractJob(context) {
      if (pageUnavailable(context.rawText)) {
        return unavailableResult(context);
      }

      const structured = jsonLd?.extract?.(context.document);
      if (structured?.isolated?.jdText) {
        if (!clean(structured.identity?.company)) {
          structured.identity.company = companyFromMeta(context.document);
        }
        structured.isolated.jdText = cleanPhenomDescription(
          structured.isolated.jdText,
          context.host
        );
        structured.isolated.strategy = "phenom_job_posting_jsonld_v2";
        return structured;
      }
      return domExtraction(context);
    },

    fieldHints() { return []; },
    getControls() { return null; },

    diagnostics() {
      return {
        framework: "phenom_dynamic_career_site",
        waits_for_stable_capture: true,
      };
    },
  };
});
