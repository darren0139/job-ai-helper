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

  const NON_TITLE_PATTERNS = [
    /^sorry,?\s+internet explorer/i,
    /internet explorer 11 is no longer supported/i,
    /^please update to one of the following browsers/i,
    /^company description$/i,
    /^job description$/i,
    /^qualifications$/i,
    /^additional information$/i,
    /^job location$/i,
    /^share this job$/i,
    /^i'?m interested$/i,
  ];

  function clean(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function query(documentObject, selector) {
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
      const value = text(context, query(context.document, selector));
      if (value) return value;
    }
    return "";
  }

  function smartRecruitersHost(host) {
    const value = String(host || "").toLowerCase();
    return (
      value === "jobs.smartrecruiters.com" ||
      value === "careers.smartrecruiters.com" ||
      value === "www.smartrecruiters.com"
    );
  }

  function companySlugFromUrl(url) {
    try {
      return clean(
        new URL(String(url || "")).pathname.split("/").filter(Boolean)[0]
      );
    } catch (_error) {
      return "";
    }
  }

  function documentTitleCore(documentTitle) {
    return clean(documentTitle)
      .replace(/\s*\|\s*SmartRecruiters\s*$/i, "")
      .trim();
  }

  function plausibleTitle(value) {
    const candidate = clean(value);
    if (!candidate || candidate.length < 3 || candidate.length > 220) {
      return false;
    }
    return !NON_TITLE_PATTERNS.some((pattern) => pattern.test(candidate));
  }

  function titleFromPage(context, structured) {
    const structuredTitle = clean(structured?.identity?.title);
    if (plausibleTitle(structuredTitle)) return structuredTitle;

    const core = documentTitleCore(context.documentTitle);
    const candidates = [];

    for (const heading of context.headings || []) {
      if (plausibleTitle(heading)) candidates.push(clean(heading));
    }

    const h1 = firstText(context, ["h1", '[itemprop="title"]']);
    if (plausibleTitle(h1)) candidates.push(clean(h1));

    const unique = [...new Set(candidates)];

    const titleMatch = unique
      .filter((candidate) =>
        core.toLowerCase().includes(candidate.toLowerCase())
      )
      .sort((left, right) => right.length - left.length)[0];

    if (titleMatch) return titleMatch;
    if (unique.length) return unique[0];

    return "";
  }

  function companyFromTitle(documentTitle, jobTitle) {
    let core = documentTitleCore(documentTitle);
    const job = clean(jobTitle);
    if (
      job &&
      core.toLowerCase().endsWith(job.toLowerCase())
    ) {
      core = core.slice(0, core.length - job.length).trim();
    }

    return core
      .replace(/[\s|–—-]+$/g, "")
      .trim();
  }

  function companyFromStructured(structured) {
    const company = clean(structured?.identity?.company);
    if (!company) return "";
    if (/internet explorer|smartrecruiters/i.test(company)) return "";
    return company;
  }

  function locationFromRawText(rawText) {
    const lines = String(rawText || "")
      .replace(/\r/g, "")
      .split("\n")
      .map(clean)
      .filter(Boolean);

    for (let index = 0; index < lines.length - 1; index += 1) {
      if (/^job location$/i.test(lines[index])) {
        const candidate = lines[index + 1];
        if (
          candidate &&
          candidate.length <= 160 &&
          !NON_TITLE_PATTERNS.some((pattern) => pattern.test(candidate))
        ) {
          return candidate;
        }
      }
    }
    return "";
  }

  function cleanSectionFormatting(value) {
    return String(value || "")
      .replace(/\*\*([^*\n]+)\*\*/g, "$1")
      .replace(/\u00a0/g, " ")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function sectionText(rawText) {
    const raw = String(rawText || "").replace(/\r/g, "");
    const lower = raw.toLowerCase();

    const markers = [
      "\njob description\n",
      "job description\n",
    ];

    let start = -1;
    let markerLength = 0;
    for (const marker of markers) {
      const index = lower.indexOf(marker);
      if (index >= 0 && (start < 0 || index < start)) {
        start = index;
        markerLength = marker.length;
      }
    }
    if (start < 0) return "";

    const after = start + markerLength;
    let end = raw.length;
    for (const marker of [
      "\nadditional information\n",
      "\njob location\n",
      "\nshare this job\n",
    ]) {
      const index = lower.indexOf(marker, after);
      if (index >= 0 && index < end) end = index;
    }

    return cleanSectionFormatting(raw.slice(after, end));
  }

  function identityFromPage(context, structured) {
    const title = titleFromPage(context, structured);

    const company =
      companyFromStructured(structured) ||
      firstText(context, [
        '[itemprop="hiringOrganization"]',
        '[data-testid="company-name"]',
      ]) ||
      companyFromTitle(context.documentTitle, title) ||
      companySlugFromUrl(context.url);

    const location =
      clean(structured?.identity?.location) ||
      firstText(context, [
        '[itemprop="jobLocation"]',
        '[data-testid="job-location"]',
        ".job-location",
      ]) ||
      locationFromRawText(context.rawText);

    return { title, company, location };
  }

  function extractJob(context) {
    const structured = jsonLd?.extract?.(context.document);
    const visibleSection = sectionText(context.rawText);
    const identity = identityFromPage(context, structured);

    if (visibleSection.length >= 160) {
      return {
        identity,
        isolated: {
          jdText: visibleSection,
          postingNotes: [],
          discardedTrackingTags: [],
          strategy: "smartrecruiters_sections_v4",
          confidence: "high",
        },
      };
    }

    if (structured?.isolated?.jdText) {
      structured.identity = identity;
      structured.isolated.strategy =
        "smartrecruiters_job_posting_jsonld_v4";
      return structured;
    }

    const description = firstText(context, [
      '[data-testid="job-description"]',
      '[itemprop="description"]',
      ".job-description",
    ]);
    if (description.length < 160) return null;

    return {
      identity,
      isolated: {
        jdText: description,
        postingNotes: [],
        discardedTrackingTags: [],
        strategy: "smartrecruiters_job_description_dom_v4",
        confidence: "medium",
      },
    };
  }

  return {
    id: "smartrecruiters",
    version: "smartrecruiters-adapter-v4",
    priority: 89,
    dynamic: false,

    matches(context) {
      return smartRecruitersHost(context.host);
    },

    extractJob,

    fieldHints(element) {
      return [
        element?.getAttribute?.("name"),
        element?.getAttribute?.("id"),
        element?.getAttribute?.("aria-label"),
      ].filter(Boolean);
    },

    getControls() { return null; },

    diagnostics(context) {
      return {
        framework: "smartrecruiters",
        company_slug: companySlugFromUrl(context.url),
        title_hint: titleFromPage(context, null),
        section_extraction: sectionText(context.rawText).length >= 160,
      };
    },
  };
});
