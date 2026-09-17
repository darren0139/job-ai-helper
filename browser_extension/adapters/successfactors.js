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
    ".jobdescription",
    ".jobDescription",
    ".job-description",
    '[itemprop="description"]',
    '[data-careersite-propertyid="description"]',
  ];

  const TITLE_SELECTORS = [
    '[data-careersite-propertyid="title"]',
    "h1",
    ".jobTitle",
    ".jobtitle",
    ".job-title",
  ];

  const NON_JOB_TITLE_PATTERNS = [
    /^apply(?:\s+now)?\b/i,
    /^apply\b.*[»›>]\s*$/i,
    /^login(?:\/view profile)?$/i,
    /^view profile$/i,
    /^all jobs$/i,
    /^search jobs?$/i,
    /^careers?$/i,
    /^jobs?$/i,
  ];

  const LOCATION_SELECTORS = [
    ".jobLocation",
    ".joblocation",
    ".job-location",
    '[data-careersite-propertyid="location"]',
  ];

  const COMPANY_SELECTORS = [
    '[data-careersite-propertyid="company"]',
    ".jobCompany",
    ".jobcompany",
    ".company-name",
  ];

  const BRANDED_JOB_PATH_RE =
    /\/job\/[^?#]+\/\d{6,}(?:\/)?(?:[?#]|$)/i;

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
      const value = text(
        context,
        querySelectorSafe(context.document, selector)
      );
      if (value) return value;
    }
    return "";
  }

  function isPlausibleJobTitle(value) {
    const title = clean(value);
    if (!title || title.length < 3 || title.length > 220) return false;
    return !NON_JOB_TITLE_PATTERNS.some((pattern) => pattern.test(title));
  }

  function jobTitleFromPage(context) {
    for (const selector of TITLE_SELECTORS) {
      const candidate = text(
        context,
        querySelectorSafe(context.document, selector)
      );
      if (isPlausibleJobTitle(candidate)) return clean(candidate);
    }

    for (const heading of context.headings || []) {
      if (isPlausibleJobTitle(heading)) return clean(heading);
    }

    const documentTitle = clean(context.documentTitle)
      .replace(/\s+Job Details?\s*\|.*$/i, "")
      .replace(/\s+[|–—-]\s+(careers?|jobs?).*$/i, "")
      .trim();

    return isPlausibleJobTitle(documentTitle) ? documentTitle : "";
  }

  function successFactorsHost(host) {
    const value = String(host || "").toLowerCase();
    return (
      value === "successfactors.com" ||
      value.endsWith(".successfactors.com") ||
      value === "successfactors.eu" ||
      value.endsWith(".successfactors.eu")
    );
  }

  function successFactorsPath(url) {
    const value = String(url || "").toLowerCase();
    return (
      value.includes("/sfcareer/") ||
      value.includes("jobreqcareer") ||
      value.includes("career_job_req_id=") ||
      value.includes("career_ns=job_application")
    );
  }

  function companyFromUrl(url) {
    try {
      const parsed = new URL(String(url || ""));
      return clean(
        parsed.searchParams.get("company") ||
        parsed.searchParams.get("career_company")
      );
    } catch (_error) {
      return "";
    }
  }

  function metaContent(documentObject, selector) {
    const meta = querySelectorSafe(documentObject, selector);
    return clean(meta?.getAttribute?.("content"));
  }

  function companyFromDocumentTitle(documentTitle) {
    const value = clean(documentTitle);
    if (!value.includes("|")) return "";

    let candidate = clean(value.split("|").pop());
    candidate = candidate
      .replace(/\b(job details?|careers?|jobs?)\b/gi, " ")
      .replace(/\s+/g, " ")
      .trim();

    if (
      !candidate ||
      /^(career|careers|job|jobs|job details?)$/i.test(candidate)
    ) {
      return "";
    }

    return candidate;
  }

  function companyFromPage(context) {
    const direct = firstText(context, COMPANY_SELECTORS);
    if (direct) return direct;

    const siteName =
      metaContent(context.document, 'meta[property="og:site_name"]') ||
      metaContent(context.document, 'meta[name="application-name"]');

    if (
      siteName &&
      !/^(career|careers|job|jobs)$/i.test(siteName)
    ) {
      return siteName
        .replace(/\s+(careers?|jobs?)$/i, "")
        .trim();
    }

    return (
      companyFromDocumentTitle(context.documentTitle) ||
      companyFromUrl(context.url)
    );
  }


  function normaliseDescriptionText(value) {
    return String(value || "")
      .replace(/\u00a0/g, " ")
      .replace(/\r\n?/g, "\n")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function cleanSuccessFactorsDescription(value, host) {
    const original = normaliseDescriptionText(value);
    if (!original) return "";

    let result = original;
    const hostValue = String(host || "").toLowerCase();

    if (hostValue === "jobs.sap.com") {
      if (/^We help the world run better\b/im.test(result)) {
        const locationStart = result.search(/^Location:\s*/im);
        if (locationStart >= 0 && locationStart < 1600) {
          result = result.slice(locationStart);
        }
      }

      const boilerplateStart = result.search(/^Bring out your best\s*$/im);
      if (boilerplateStart >= 0) {
        result = result.slice(0, boilerplateStart);
      }

      result = result
        .split("\n")
        .filter(
          (line) =>
            !/^\s*#(?:SAPAICareers|SAPNextGen|LI-[A-Za-z0-9_-]+)\s*$/i.test(
              line
            )
        )
        .join("\n");
    }

    if (hostValue === "careers.gi-de.com") {
      const eeoStart = result.search(
        /^\s*\$*\s*We are an equal opportunity employer!/im
      );
      if (eeoStart >= 0) {
        result = result.slice(0, eeoStart);
      }
    }

    result = result
      .replace(
        /https?:\/\/career\d+\.successfactors\.(?:com|eu)\/\S+/gi,
        ""
      )
      .split("\n")
      .filter((line) => !/^\s*\$+(?:\s+\$+)*\s*$/.test(line))
      .join("\n")
      .replace(/\${2,}/g, " ");

    result = normaliseDescriptionText(result);
    return result.length >= 120 ? result : original;
  }

  function hasDescriptionMarker(documentObject) {
    return DESCRIPTION_SELECTORS.some((selector) =>
      Boolean(querySelectorSafe(documentObject, selector))
    );
  }

  function hasSuccessFactorsApplyLink(documentObject) {
    return Boolean(
      querySelectorSafe(
        documentObject,
        [
          'a[href*=".successfactors.com/"]',
          'a[href*=".successfactors.eu/"]',
          'form[action*=".successfactors.com/"]',
          'form[action*=".successfactors.eu/"]',
        ].join(", ")
      )
    );
  }

  function rawTextHasSuccessFactorsUrl(rawText) {
    return /https?:\/\/[^\s<>"']+\.successfactors\.(?:com|eu)\//i.test(
      String(rawText || "")
    );
  }

  function looksLikeBrandedCareerSite(context) {
    const url = String(context.url || "");
    const strongApplyMarker =
      hasSuccessFactorsApplyLink(context.document) ||
      rawTextHasSuccessFactorsUrl(context.rawText);

    if (strongApplyMarker) return true;

    return (
      BRANDED_JOB_PATH_RE.test(url) &&
      hasDescriptionMarker(context.document)
    );
  }

  function domExtraction(context) {
    const description = cleanSuccessFactorsDescription(
      firstText(context, DESCRIPTION_SELECTORS),
      context.host
    );
    if (description.length < 120) return null;

    const title = jobTitleFromPage(context);
    const location = firstText(context, LOCATION_SELECTORS);
    const company = companyFromPage(context);

    return {
      identity: {
        title,
        company,
        location,
      },
      isolated: {
        jdText: description,
        postingNotes: [],
        discardedTrackingTags: [],
        strategy: "successfactors_job_description_dom_v4",
        confidence: description.length >= 300 ? "high" : "medium",
      },
    };
  }

  return {
    id: "successfactors",
    version: "successfactors-adapter-v4",
    priority: 88,
    dynamic: true,

    matches(context) {
      return (
        successFactorsHost(context.host) ||
        successFactorsPath(context.url) ||
        looksLikeBrandedCareerSite(context)
      );
    },

    extractJob(context) {
      const structured = jsonLd?.extract?.(context.document);
      if (structured?.isolated?.jdText) {
        if (!structured.identity.company) {
          structured.identity.company = companyFromPage(context);
        }
        structured.isolated.jdText = cleanSuccessFactorsDescription(
          structured.isolated.jdText,
          context.host
        );
        structured.isolated.strategy =
          "successfactors_job_posting_jsonld_v4";
        return structured;
      }

      return domExtraction(context);
    },

    fieldHints(element) {
      return [
        element?.getAttribute?.("name"),
        element?.getAttribute?.("id"),
        element?.getAttribute?.("aria-label"),
      ].filter(Boolean);
    },

    getControls() {
      return null;
    },

    diagnostics(context) {
      return {
        framework: "sap_successfactors_recruiting",
        direct_successfactors_host: successFactorsHost(context.host),
        successfactors_path: successFactorsPath(context.url),
        branded_career_site: looksLikeBrandedCareerSite(context),
        company_hint: companyFromPage(context),
        title_hint: jobTitleFromPage(context),
        waits_for_stable_capture: true,
      };
    },
  };
});
