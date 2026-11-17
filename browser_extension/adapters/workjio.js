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
    '[class*="job-description"]',
    '[class*="description"]',
    '[class*="job-details"]',
    "article",
    "main",
  ];
  const COMPANY_SELECTORS = [
    '[class*="company-name"]',
    '[class*="company"]',
    '[class*="employer"]',
  ];
  const LOCATION_SELECTORS = [
    '[class*="location"]',
    '[class*="address"]',
  ];
  const STOP_LINES = [
    /^more jobs like this$/i,
    /^browse more jobs/i,
    /^similar jobs$/i,
    /^apply now$/i,
    /^apply for this job$/i,
    /^share$/i,
  ];
  const DROP_LINES = [
    /^workjio$/i,
    /^log ?in$/i,
    /^sign ?up$/i,
    /^save job$/i,
  ];

  function clean(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function multiline(value) {
    return String(value || "")
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n")
      .replace(/\u00a0/g, " ")
      .split("\n")
      .map((line) => line.replace(/[ \t]+/g, " ").trim())
      .filter(Boolean)
      .join("\n")
      .trim();
  }

  function workJioHost(host) {
    const value = String(host || "").toLowerCase();
    return value === "workjio.com" || value.endsWith(".workjio.com");
  }

  function jobUrl(url) {
    try {
      const parsed = new URL(String(url || ""));
      return (
        workJioHost(parsed.hostname) &&
        /^\/jobs\/[^/]+\/?$/i.test(parsed.pathname)
      );
    } catch (_error) {
      return false;
    }
  }

  function queryText(context, selectors) {
    for (const selector of selectors) {
      try {
        const node = context.document?.querySelector?.(selector);
        const value = String(
          context.textOf?.(node) || node?.innerText || node?.textContent || ""
        ).trim();
        if (value) return value;
      } catch (_error) {}
    }
    return "";
  }

  function cleanBody(value) {
    const kept = [];
    for (const raw of multiline(value).split("\n")) {
      const line = raw.trim();
      if (!line) continue;
      if (STOP_LINES.some((pattern) => pattern.test(line))) break;
      if (DROP_LINES.some((pattern) => pattern.test(line))) continue;
      kept.push(line);
    }
    return kept.join("\n").trim();
  }

  function detectEmploymentType(value) {
    const text = String(value || "").toLowerCase();
    if (/\bpart[\s-]?time\b/.test(text)) return "Part-time";
    if (/\bgig\b|\bshift\b/.test(text)) return "Gig / shift";
    if (/\bfull[\s-]?time\b/.test(text)) return "Full-time";
    if (/\btemporary\b|\btemp\b/.test(text)) return "Temporary";
    if (/\bcontract\b/.test(text)) return "Contract";
    return "";
  }

  function fromStructured(context) {
    const structured = jsonLd?.extract?.(context.document) || null;
    if (!structured?.isolated?.jdText) return null;
    const posting = structured.structured || {};
    const raw = posting.employmentType;
    const employmentType = Array.isArray(raw)
      ? raw.map(clean).filter(Boolean).join(", ")
      : clean(raw);
    return {
      ...structured,
      metadata: {
        employmentType:
          employmentType ||
          detectEmploymentType(
            `${structured.identity?.title || ""}\n${structured.isolated.jdText || ""}`
          ),
      },
      isolated: {
        ...structured.isolated,
        strategy: "workjio_job_posting_jsonld_v1",
      },
    };
  }

  function extractJob(context) {
    const structured = fromStructured(context);
    if (structured) return structured;

    const title =
      clean(context.headings?.[0]) ||
      clean(context.documentTitle).replace(/\s*[-|]\s*WorkJio.*$/i, "");
    const company = clean(queryText(context, COMPANY_SELECTORS));
    const location = clean(queryText(context, LOCATION_SELECTORS));
    const domDescription = queryText(context, DESCRIPTION_SELECTORS);
    const jdText = cleanBody(domDescription || context.rawText);

    if (!title || jdText.length < 120) {
      return {
        notReady: true,
        reason:
          "WorkJio job details are not ready for a reliable browser capture yet.",
      };
    }

    return {
      identity: { title, company, location },
      isolated: {
        jdText,
        postingNotes: [],
        discardedTrackingTags: [],
        strategy: "workjio_visible_job_v1",
        confidence: domDescription ? "high" : "medium",
      },
      metadata: {
        employmentType:
          detectEmploymentType(`${title}\n${context.rawText || ""}`) ||
          "Part-time",
      },
    };
  }

  return {
    id: "workjio",
    version: "workjio-browser-adapter-v1",
    priority: 96,
    dynamic: true,
    captureOnly: true,
    matches(context) { return jobUrl(context.url); },
    extractJob,
    fieldHints() { return []; },
    getControls() { return null; },
    diagnostics(context) {
      return {
        mode: "workjio_browser_assisted",
        job_url: jobUrl(context.url),
        structured_job_posting: Boolean(
          jsonLd?.findJobPosting?.(context.document)
        ),
        direct_http_expected_to_be_blocked: true,
        capture_only: true,
      };
    },
  };
});
