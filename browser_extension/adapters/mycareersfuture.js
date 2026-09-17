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
    /this job may have expired/i,
    /you may have entered an incorrect url/i,
    /job (?:is|has been) no longer available/i,
  ];

  const TITLE_SELECTORS = [
    '[data-testid="job-title"]',
    '[data-cy="job-title"]',
    '[itemprop="title"]',
    "main h1",
    "h1",
  ];
  const COMPANY_SELECTORS = [
    '[data-testid="company-name"]',
    '[data-cy="company-name"]',
    '[itemprop="hiringOrganization"]',
  ];
  const LOCATION_SELECTORS = [
    '[data-testid="job-location"]',
    '[data-cy="job-location"]',
    '[itemprop="jobLocation"]',
  ];
  const DESCRIPTION_SELECTORS = [
    '[data-testid="job-description"]',
    '[data-cy="job-description"]',
    '[itemprop="description"]',
  ];

  const COMPANY_SUFFIX_RE =
    /\b(?:PTE\.?\s*LTD\.?|PRIVATE\s+LIMITED|LTD\.?|LIMITED|LLP|LLC|INC\.?|CORP\.?|CORPORATION)\b/i;

  function clean(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function text(context, element) {
    if (!element) return "";
    if (typeof context.textOf === "function") {
      return String(context.textOf(element) || "").trim();
    }
    return String(element.innerText || element.textContent || "").trim();
  }

  function query(documentObject, selector) {
    try {
      return documentObject?.querySelector?.(selector) || null;
    } catch (_error) {
      return null;
    }
  }

  function queryAll(documentObject, selector) {
    try {
      return [...(documentObject?.querySelectorAll?.(selector) || [])];
    } catch (_error) {
      return [];
    }
  }

  function firstText(context, selectors) {
    for (const selector of selectors) {
      const value = text(context, query(context.document, selector));
      if (value) return value;
    }
    return "";
  }

  function htmlToText(value) {
    if (jsonLd?.htmlToText) return jsonLd.htmlToText(value);
    return String(value || "")
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/(?:p|div|li|ul|ol|h[1-6]|section)>/gi, "\n")
      .replace(/<li\b[^>]*>/gi, "• ")
      .replace(/<[^>]+>/g, " ")
      .split(/\r?\n/)
      .map((line) => line.replace(/[ \t]+/g, " ").trim())
      .filter(Boolean)
      .join("\n")
      .trim();
  }

  function unavailable(rawText) {
    return UNAVAILABLE_PATTERNS.some((pattern) =>
      pattern.test(String(rawText || ""))
    );
  }

  function invalidCompanyLabel(value) {
    const candidate = clean(value).toLowerCase();
    return (
      !candidate ||
      candidate.length > 160 ||
      /^(view|learn|more|company)$/i.test(candidate) ||
      candidate.includes("more jobs from this company") ||
      candidate.includes("view jobs from this company") ||
      candidate.includes("view all jobs") ||
      candidate.includes("company profile") ||
      candidate.includes("about this company")
    );
  }

  function companyFromAnchors(context) {
    for (const anchor of queryAll(
      context.document,
      'a[href*="/company/"], a[href*="/companies/"]'
    )) {
      const candidate = clean(text(context, anchor));
      if (!invalidCompanyLabel(candidate)) return candidate;
    }
    return "";
  }

  function companyFromRawText(rawText, jobTitle) {
    const title = clean(jobTitle).toLowerCase();
    const lines = String(rawText || "")
      .split(/\r?\n/)
      .map(clean)
      .filter(Boolean);

    for (const line of lines.slice(0, 80)) {
      if (
        line.length >= 3 &&
        line.length <= 160 &&
        line.toLowerCase() !== title &&
        COMPANY_SUFFIX_RE.test(line)
      ) {
        return line;
      }
    }
    return "";
  }

  function companyFromPage(context, title) {
    return (
      firstText(context, COMPANY_SELECTORS) ||
      companyFromRawText(context.rawText, title) ||
      companyFromAnchors(context)
    );
  }

  function valueFromObject(object, keys) {
    for (const key of keys) {
      const value = object?.[key];
      if (typeof value === "string" && value.trim()) return value.trim();
    }
    return "";
  }

  function descriptionFromObject(object) {
    return htmlToText(valueFromObject(object, [
      "descriptionText",
      "jobDescription",
      "description",
      "descriptionHtml",
      "jobDescriptionHtml",
    ]));
  }

  function companyFromObject(object) {
    const direct = valueFromObject(object, [
      "companyName",
      "employerName",
      "hiringCompanyName",
    ]);
    if (direct) return direct;
    for (const key of ["company", "employer", "hiringOrganization"]) {
      const value = object?.[key];
      if (typeof value === "string" && value.trim()) return value.trim();
      if (value && typeof value === "object") {
        const nested = valueFromObject(value, ["name", "companyName"]);
        if (nested) return nested;
      }
    }
    return "";
  }

  function locationFromObject(object) {
    const direct = valueFromObject(object, [
      "address",
      "location",
      "workplaceAddress",
    ]);
    if (direct) return direct;
    return [
      valueFromObject(object, ["district"]),
      valueFromObject(object, ["region"]),
    ].filter(Boolean).join(", ");
  }

  function postingNotesFromObject(object) {
    const notes = [];
    const salaryMin = object?.salaryMin ?? object?.minimumSalary;
    const salaryMax = object?.salaryMax ?? object?.maximumSalary;
    const salaryType = clean(object?.salaryType || object?.salaryPeriod);
    if (salaryMin || salaryMax) {
      notes.push(
        `Salary: ${salaryMin || "?"} - ${salaryMax || "?"}` +
        (salaryType ? ` (${salaryType})` : "")
      );
    }

    const employment = object?.employmentTypes || object?.employmentType || [];
    const employmentText = Array.isArray(employment)
      ? employment.map(clean).filter(Boolean).join(", ")
      : clean(employment);
    if (employmentText) notes.push(`Employment type: ${employmentText}`);

    const levels = object?.positionLevels || object?.positionLevel || [];
    const levelText = Array.isArray(levels)
      ? levels.map(clean).filter(Boolean).join(", ")
      : clean(levels);
    if (levelText) notes.push(`Position level: ${levelText}`);

    const expiry = clean(object?.expiryDate || object?.expiry);
    if (expiry) notes.push(`Expiry date: ${expiry}`);
    return notes;
  }

  function walk(value, visit, depth = 0) {
    if (depth > 10 || value == null) return;
    if (Array.isArray(value)) {
      for (const item of value) walk(item, visit, depth + 1);
      return;
    }
    if (typeof value !== "object") return;
    visit(value);
    for (const child of Object.values(value)) {
      if (child && typeof child === "object") walk(child, visit, depth + 1);
    }
  }

  function nextDataCandidates(documentObject) {
    const script = query(documentObject, "script#__NEXT_DATA__");
    const raw = String(script?.textContent || script?.innerText || "").trim();
    if (!raw) return [];
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (_error) {
      return [];
    }

    const candidates = [];
    walk(parsed, (object) => {
      const description = descriptionFromObject(object);
      const title = valueFromObject(object, ["title", "jobTitle", "name"]);
      if (description.length >= 160 && title) {
        candidates.push({
          title,
          description,
          company: companyFromObject(object),
          location: locationFromObject(object),
          notes: postingNotesFromObject(object),
        });
      }
    });

    return candidates.sort(
      (left, right) => right.description.length - left.description.length
    );
  }

  function sectionFromRawText(rawText) {
    const raw = String(rawText || "").replace(/\r/g, "");
    const lower = raw.toLowerCase();
    const starts = ["\njob description\n", "\njob description", "\ndescription\n"];
    let start = -1;
    let markerLength = 0;

    for (const marker of starts) {
      const index = lower.indexOf(marker);
      if (index >= 0 && (start < 0 || index < start)) {
        start = index;
        markerLength = marker.length;
      }
    }
    if (start < 0) return "";

    const after = start + markerLength;
    const ends = [
      "\nskills\n",
      "\nabout the company\n",
      "\ncompany information\n",
      "\nother information\n",
      "\njob details\n",
      "\napply now\n",
    ];
    let end = raw.length;
    for (const marker of ends) {
      const index = lower.indexOf(marker, after);
      if (index >= 0 && index < end) end = index;
    }
    return raw.slice(after, end).trim();
  }

  function unavailableResult(context) {
    const title =
      firstText(context, TITLE_SELECTORS) ||
      clean((context.headings || [])[0]);
    return {
      availability: "unavailable",
      identity: {
        title,
        company: companyFromPage(context, title),
        location: firstText(context, LOCATION_SELECTORS),
      },
      isolated: {
        jdText: "",
        postingNotes: [
          "MyCareersFuture reports that this job may have expired or is unavailable.",
        ],
        discardedTrackingTags: [],
        strategy: "mycareersfuture_unavailable_v3",
        confidence: "high",
      },
    };
  }

  function extractJob(context) {
    if (unavailable(context.rawText)) return unavailableResult(context);

    const structured = jsonLd?.extract?.(context.document);
    if (structured?.isolated?.jdText) {
      if (!clean(structured.identity?.company)) {
        structured.identity.company = companyFromPage(
          context,
          structured.identity?.title
        );
      }
      structured.isolated.strategy = "mycareersfuture_job_posting_jsonld_v3";
      return structured;
    }

    const nextCandidate = nextDataCandidates(context.document)[0];
    if (nextCandidate) {
      const title = nextCandidate.title;
      return {
        identity: {
          title,
          company:
            nextCandidate.company || companyFromPage(context, title),
          location: nextCandidate.location,
        },
        isolated: {
          jdText: nextCandidate.description,
          postingNotes: nextCandidate.notes,
          discardedTrackingTags: [],
          strategy: "mycareersfuture_next_data_v3",
          confidence: "high",
        },
      };
    }

    const domDescription = firstText(context, DESCRIPTION_SELECTORS);
    const rawSection = sectionFromRawText(context.rawText);
    const description = domDescription.length >= 160
      ? domDescription
      : rawSection;
    if (description.length < 160) return null;

    const title =
      firstText(context, TITLE_SELECTORS) ||
      clean((context.headings || [])[0]);

    return {
      identity: {
        title,
        company: companyFromPage(context, title),
        location: firstText(context, LOCATION_SELECTORS),
      },
      isolated: {
        jdText: description,
        postingNotes: [],
        discardedTrackingTags: [],
        strategy: domDescription.length >= 160
          ? "mycareersfuture_job_description_dom_v3"
          : "mycareersfuture_visible_section_v3",
        confidence: domDescription.length >= 160 ? "high" : "medium",
      },
    };
  }

  return {
    id: "mycareersfuture",
    version: "mycareersfuture-adapter-v3",
    priority: 94,
    dynamic: true,

    matches(context) {
      const host = String(context.host || "").toLowerCase();
      const url = String(context.url || "").toLowerCase();
      return (
        (host === "mycareersfuture.gov.sg" ||
         host === "www.mycareersfuture.gov.sg") &&
        url.includes("/job/")
      );
    },

    extractJob,
    fieldHints() { return []; },
    getControls() { return null; },

    diagnostics(context) {
      const title =
        firstText(context, TITLE_SELECTORS) ||
        clean((context.headings || [])[0]);
      return {
        framework: "mycareersfuture",
        has_next_data: Boolean(query(context.document, "script#__NEXT_DATA__")),
        next_data_candidates: nextDataCandidates(context.document).length,
        company_hint: companyFromPage(context, title),
        waits_for_stable_capture: true,
        application_automation: false,
      };
    },
  };
});
