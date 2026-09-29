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

  const TITLE_SELECTORS = [
    ".job-details-jobs-unified-top-card__job-title h1",
    ".job-details-jobs-unified-top-card__job-title",
    ".jobs-unified-top-card__job-title h1",
    ".jobs-unified-top-card__job-title",
    "h1.top-card-layout__title",
    "h1.topcard__title",
    "main h1",
    "h1",
  ];

  const COMPANY_SELECTORS = [
    ".job-details-jobs-unified-top-card__company-name a",
    ".job-details-jobs-unified-top-card__company-name",
    ".jobs-unified-top-card__company-name a",
    ".jobs-unified-top-card__company-name",
    ".job-details-jobs-unified-top-card__primary-description-container a[href*='/company/']",
    ".jobs-unified-top-card__primary-description-container a[href*='/company/']",
    "a.topcard__org-name-link",
    ".topcard__org-name-link",
    ".top-card-layout__card a[data-tracking-control-name*='public_jobs_topcard-org-name']",
  ];

  const LOCATION_SELECTORS = [
    ".job-details-jobs-unified-top-card__primary-description-container .t-black--light",
    ".jobs-unified-top-card__primary-description-container .t-black--light",
    ".job-details-jobs-unified-top-card__primary-description-container .tvm__text",
    ".jobs-unified-top-card__primary-description-container .tvm__text",
    ".top-card-layout__second-subline .topcard__flavor--bullet",
    ".topcard__flavor--bullet",
  ];

  const DESCRIPTION_SELECTORS = [
    ".jobs-description__content .jobs-box__html-content",
    ".jobs-description-content__text",
    ".description__text .show-more-less-html__markup",
    ".show-more-less-html__markup",
    ".jobs-description__container",
    ".jobs-description__content",
    ".jobs-description",
    "#job-details",
  ];

  const PLATFORM_BOUNDARIES = [
    /^seniority level$/i,
    /^employment type$/i,
    /^job function$/i,
    /^industries$/i,
    /^referrals increase your chances/i,
    /^see who you know$/i,
    /^get notified about new/i,
    /^similar jobs$/i,
    /^people also viewed$/i,
    /^explore collaborative articles$/i,
    /^this job alert is (?:on|off)$/i,
  ];

  const PLATFORM_LINES = [
    /^about the job$/i,
    /^show more$/i,
    /^show less$/i,
    /^report this job$/i,
    /^(?:…|\.\.\.)\s*more$/i,
  ];

  const TRACKING_TAG_RE = /^#LI-[A-Za-z0-9_-]+$/i;

  function clean(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function multiline(value) {
    return String(value || "")
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n")
      .replace(/\u00a0/g, " ")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n[ \t]+/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
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

  function selectorDiagnostics(context, selectors, maxLength = 160) {
    const matches = [];
    for (const selector of selectors) {
      const value = clean(text(context, query(context.document, selector)));
      if (!value) continue;
      matches.push({
        selector,
        text: value.slice(0, maxLength),
      });
    }
    return matches.slice(0, 8);
  }

  function linkedInHost(host) {
    const value = String(host || "").toLowerCase();
    return value === "linkedin.com" || value.endsWith(".linkedin.com");
  }

  function directJobUrl(url) {
    try {
      const parsed = new URL(String(url || ""));
      return linkedInHost(parsed.hostname) && /\/jobs\/view\//i.test(parsed.pathname);
    } catch (_error) {
      return false;
    }
  }

  function splitPaneJobUrl(url) {
    try {
      const parsed = new URL(String(url || ""));
      if (!linkedInHost(parsed.hostname)) return false;
      if (!/^\/jobs\//i.test(parsed.pathname)) return false;
      const currentJobId = String(parsed.searchParams.get("currentJobId") || "").trim();
      return /^\d{5,}$/.test(currentJobId);
    } catch (_error) {
      return false;
    }
  }

  function jobContextUrl(url) {
    return directJobUrl(url) || splitPaneJobUrl(url);
  }

  function plausibleIdentity(value) {
    const candidate = clean(value);
    if (!candidate || candidate.length > 220) return "";

    const shellLabels = [
      /^(sign in|join now|jobs|job search|linkedin)$/i,
      /^(home|my network|messaging|notifications?|me|for business|post)$/i,
      /^\d+\s+notifications?$/i,
      /^see who .* has hired for this role$/i,
    ];

    if (shellLabels.some((pattern) => pattern.test(candidate))) {
      return "";
    }
    return candidate;
  }

  function hasReliableIdentity(identity) {
    return Boolean(
      plausibleIdentity(identity?.title) &&
      plausibleIdentity(identity?.company)
    );
  }

  function notReady(reason) {
    return {
      notReady: true,
      reason:
        String(reason || "").trim() ||
        "LinkedIn job panel is not ready for capture yet.",
    };
  }

  function parseDocumentTitle(documentTitle) {
    const original = clean(documentTitle);
    const title = original
      .replace(/\s*\|\s*LinkedIn(?:\s+Jobs)?\s*$/i, "")
      .trim();

    const atMatch = title.match(
      /^(.+?)\s+at\s+(.+?)(?:\s+[—–|-]\s+.+)?$/i
    );
    if (atMatch) {
      return {
        title: plausibleIdentity(atMatch[1]),
        company: plausibleIdentity(atMatch[2]),
        strategy: "document_title_at",
      };
    }

    const pipeParts = title
      .split("|")
      .map(clean)
      .filter(Boolean);
    if (pipeParts.length >= 2) {
      const parsedTitle = plausibleIdentity(pipeParts[0]);
      const parsedCompany = plausibleIdentity(pipeParts[1]);
      if (parsedTitle && parsedCompany) {
        return {
          title: parsedTitle,
          company: parsedCompany,
          strategy: "document_title_pipe",
        };
      }
    }

    return { title: "", company: "", strategy: "" };
  }

  function identity(context, structured) {
    const parsed = parseDocumentTitle(context.documentTitle);

    const structuredTitle = plausibleIdentity(structured?.identity?.title);
    const structuredCompany = plausibleIdentity(structured?.identity?.company);
    const structuredLocation = clean(structured?.identity?.location);

    const title =
      structuredTitle ||
      plausibleIdentity(firstText(context, TITLE_SELECTORS)) ||
      parsed.title ||
      (context.headings || []).map(plausibleIdentity).find(Boolean) ||
      "";

    const company =
      structuredCompany ||
      plausibleIdentity(firstText(context, COMPANY_SELECTORS)) ||
      parsed.company;

    const location =
      structuredLocation ||
      clean(firstText(context, LOCATION_SELECTORS));

    return { title, company, location };
  }

  function cleanDescription(value) {
    const discardedTrackingTags = [];
    const sourceLines = multiline(value).split("\n");
    const kept = [];

    for (const sourceLine of sourceLines) {
      const line = sourceLine.trim();
      if (!line) {
        if (kept.length && kept[kept.length - 1] !== "") kept.push("");
        continue;
      }

      if (PLATFORM_BOUNDARIES.some((pattern) => pattern.test(line))) break;
      if (PLATFORM_LINES.some((pattern) => pattern.test(line))) continue;

      if (TRACKING_TAG_RE.test(line)) {
        discardedTrackingTags.push(line);
        continue;
      }

      kept.push(line);
    }

    const jdText = kept.join("\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();

    return {
      jdText,
      discardedTrackingTags: [...new Set(discardedTrackingTags)],
    };
  }

  function rawSection(rawText) {
    const raw = multiline(rawText);
    if (!raw) return "";

    const lines = raw.split("\n");
    let start = lines.findIndex((line) => /^about the job$/i.test(line.trim()));
    if (start >= 0) {
      start += 1;
      return lines.slice(start).join("\n");
    }

    // Logged-out/public LinkedIn pages often omit an explicit "About the job"
    // heading. If the platform rendered a clear description container, the DOM
    // path is preferred. Do not guess a full-page raw boundary here.
    return "";
  }

  function extractJob(context) {
    const structured = jsonLd?.extract?.(context.document) || null;
    const pageIdentity = identity(context, structured);
    const isSplitPane =
      splitPaneJobUrl(context.url) && !directJobUrl(context.url);

    if (structured?.isolated?.jdText) {
      const cleaned = cleanDescription(structured.isolated.jdText);
      if (
        cleaned.jdText.length >= 160 &&
        (!isSplitPane || hasReliableIdentity(pageIdentity))
      ) {
        return {
          identity: pageIdentity,
          isolated: {
            jdText: cleaned.jdText,
            postingNotes: Array.isArray(structured.isolated.postingNotes)
              ? structured.isolated.postingNotes
              : [],
            discardedTrackingTags: [
              ...new Set([
                ...(Array.isArray(structured.isolated.discardedTrackingTags)
                  ? structured.isolated.discardedTrackingTags
                  : []),
                ...cleaned.discardedTrackingTags,
              ]),
            ],
            strategy: "linkedin_job_posting_jsonld_v1",
            confidence: "high",
          },
        };
      }
    }

    const domDescription = firstText(context, DESCRIPTION_SELECTORS);
    if (domDescription) {
      const cleaned = cleanDescription(domDescription);
      if (
        cleaned.jdText.length >= 160 &&
        (!isSplitPane || hasReliableIdentity(pageIdentity))
      ) {
        return {
          identity: pageIdentity,
          isolated: {
            jdText: cleaned.jdText,
            postingNotes: [],
            discardedTrackingTags: cleaned.discardedTrackingTags,
            strategy: "linkedin_job_description_dom_v1",
            confidence: "high",
          },
        };
      }
    }

    if (isSplitPane) {
      if (!hasReliableIdentity(pageIdentity)) {
        return notReady(
          "LinkedIn selected-job panel is not ready: a reliable job title " +
          "and company were not both available yet."
        );
      }
      return notReady(
        "LinkedIn selected-job panel is not ready: the dedicated job " +
        "description container has not rendered yet."
      );
    }

    const raw = rawSection(context.rawText);
    if (raw && hasReliableIdentity(pageIdentity)) {
      const cleaned = cleanDescription(raw);
      if (cleaned.jdText.length >= 160) {
        return {
          identity: pageIdentity,
          isolated: {
            jdText: cleaned.jdText,
            postingNotes: [],
            discardedTrackingTags: cleaned.discardedTrackingTags,
            strategy: "linkedin_visible_job_section_v1",
            confidence: "medium",
          },
        };
      }
    }

    return notReady(
      "LinkedIn job details are not ready for a reliable capture yet."
    );
  }
  return {
    id: "linkedin",
    version: "linkedin-adapter-v5",
    priority: 92,
    dynamic: true,
    captureOnly: true,

    matches(context) {
      return jobContextUrl(context.url);
    },

    extractJob,

    fieldHints() {
      return [];
    },

    getControls() {
      return null;
    },

    diagnostics(context) {
      const parsedTitle = parseDocumentTitle(context.documentTitle);
      return {
        framework: "linkedin",
        direct_job_page: directJobUrl(context.url),
        split_pane_job_page: splitPaneJobUrl(context.url),
        current_job_context: jobContextUrl(context.url),
        reliable_identity: hasReliableIdentity(identity(context, null)),
        document_title_parse: parsedTitle,
        title_candidates: selectorDiagnostics(
          context,
          TITLE_SELECTORS
        ),
        company_candidates: selectorDiagnostics(
          context,
          COMPANY_SELECTORS
        ),
        location_candidates: selectorDiagnostics(
          context,
          LOCATION_SELECTORS
        ),
        description_selectors_found: DESCRIPTION_SELECTORS.filter(
          (selector) => Boolean(query(context.document, selector))
        ).slice(0, 12),
        capture_only: true,
        has_description_dom: Boolean(
          DESCRIPTION_SELECTORS.some((selector) =>
            query(context.document, selector)
          )
        ),
        waits_for_stable_capture: true,
      };
    },
  };
});
