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
    '[class*="jobDescription"]',
    '[class*="job_description"]',
    '[class*="description"]',
    "article",
    "main",
  ];
  const COMPANY_SELECTORS = [
    '[class*="company-name"]',
    '[class*="companyName"]',
    '[class*="employer"]',
  ];
  const LOCATION_SELECTORS = [
    '[class*="job-location"]',
    '[class*="location"]',
  ];
  const STOP_LINES = [
    /^similar jobs$/i,
    /^related jobs$/i,
    /^recommended jobs$/i,
    /^apply now$/i,
    /^apply for this job$/i,
    /^share this job$/i,
    /^report job$/i,
  ];
  const DROP_LINES = [
    /^just a moment/i,
    /^checking your browser/i,
    /^enable javascript and cookies/i,
    /^fastjobs$/i,
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

  function fastJobsHost(host) {
    const value = String(host || "").toLowerCase();
    return value === "fastjobs.sg" || value.endsWith(".fastjobs.sg");
  }

  function jobUrl(url) {
    try {
      const parsed = new URL(String(url || ""));
      return (
        fastJobsHost(parsed.hostname) &&
        /\/singapore-job-ad\/\d+(?:\/|$)/i.test(parsed.pathname)
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
    if (/\bfull[\s-]?time\b/.test(text)) return "Full-time";
    if (/\btemporary\b|\btemp\b/.test(text)) return "Temporary";
    if (/\bcontract\b/.test(text)) return "Contract";
    if (/\bintern(?:ship)?\b/.test(text)) return "Internship";
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
        strategy: "fastjobs_job_posting_jsonld_v1",
      },
    };
  }

  function extractJob(context) {
    const structured = fromStructured(context);
    if (structured) return structured;

    const title =
      clean(context.headings?.[0]) ||
      clean(context.documentTitle).replace(/\s*[-|]\s*FastJobs.*$/i, "");
    const company = clean(queryText(context, COMPANY_SELECTORS));
    const location = clean(queryText(context, LOCATION_SELECTORS));
    const domDescription = queryText(context, DESCRIPTION_SELECTORS);
    const jdText = cleanBody(domDescription || context.rawText);

    if (!title || jdText.length < 120) {
      return {
        notReady: true,
        reason:
          "FastJobs job details are not ready for a reliable browser capture yet.",
      };
    }

    return {
      identity: { title, company, location },
      isolated: {
        jdText,
        postingNotes: [],
        discardedTrackingTags: [],
        strategy: "fastjobs_visible_job_v1",
        confidence: domDescription ? "high" : "medium",
      },
      metadata: {
        employmentType: detectEmploymentType(
          `${title}\n${context.rawText || ""}`
        ),
      },
    };
  }

  return {
    id: "fastjobs",
    version: "fastjobs-browser-adapter-v1",
    priority: 96,
    dynamic: true,
    captureOnly: true,
    matches(context) { return jobUrl(context.url); },
    extractJob,
    fieldHints() { return []; },
    getControls() { return null; },
    diagnostics(context) {
      return {
        mode: "fastjobs_browser_assisted",
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
