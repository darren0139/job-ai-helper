(function (root, factory) {
  "use strict";
  const adapter = factory();
  if (root.JobAISiteAdapters) root.JobAISiteAdapters.register(adapter);
  if (typeof module !== "undefined" && module.exports) module.exports = adapter;
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";

  const DESCRIPTION_SELECTORS = [
    '[data-testid="job-description"]',
    ".job__description",
    ".job-description",
    ".job-post__description",
    '[class*="jobDescription"]',
    "#content",
  ];

  const APPLICATION_ROOT_SELECTORS = [
    '[data-testid="application-form"]',
    "#application_form",
    'form[action*="greenhouse.io"]',
    "#application",
  ];

  function clean(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function greenhouseHost(host) {
    const value = String(host || "").toLowerCase();
    return value === "greenhouse.io" || value.endsWith(".greenhouse.io");
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

  function findDescription(context) {
    for (const selector of DESCRIPTION_SELECTORS) {
      const element = querySelectorSafe(context.document, selector);
      const value = text(context, element);
      if (value.length >= 200) return { value, selector };
    }
    return null;
  }

  function cutBeforeApplicationForm(rawText) {
    const lines = String(rawText || "")
      .split(/\r?\n/)
      .map((line) => clean(line))
      .filter(Boolean);

    const boundary = lines.findIndex((line) =>
      /^(apply for this job|apply now)$/i.test(line)
    );
    if (boundary > 0) return lines.slice(0, boundary).join("\n");
    return "";
  }

  function parsedDocumentTitle(context) {
    const match = clean(context.documentTitle).match(
      /^Job Application for\s+(.+?)\s+at\s+(.+)$/i
    );
    if (!match) return { title: "", company: "" };
    return { title: clean(match[1]), company: clean(match[2]) };
  }

  function identity(context) {
    const parsed = parsedDocumentTitle(context);
    const doc = context.document;

    const titleElement =
      querySelectorSafe(doc, '[data-testid="job-title"]') ||
      querySelectorSafe(doc, "h1.app-title") ||
      querySelectorSafe(doc, "h1");

    const locationElement =
      querySelectorSafe(doc, '[data-testid="job-location"]') ||
      querySelectorSafe(doc, ".location");

    return {
      title:
        clean(text(context, titleElement)) ||
        parsed.title ||
        clean((context.headings || [])[0]),
      company: parsed.company,
      location: clean(text(context, locationElement)),
    };
  }

  function formRoot(documentObject) {
    for (const selector of APPLICATION_ROOT_SELECTORS) {
      const root = querySelectorSafe(documentObject, selector);
      if (root) return root;
    }
    return null;
  }

  const EXACT_FIELD_HINTS = new Map([
    ["first_name", "first name"],
    ["firstname", "first name"],
    ["last_name", "last name"],
    ["lastname", "last name"],
    ["email", "email address"],
    ["phone", "phone number"],
    ["phone_number", "phone number"],
    ["linkedin", "linkedin profile url"],
    ["linkedin_url", "linkedin profile url"],
    ["website", "website"],
    ["portfolio", "portfolio"],
  ]);

  return {
    id: "greenhouse",
    version: "greenhouse-adapter-v1",
    priority: 80,

    matches(context) {
      if (greenhouseHost(context.host)) return true;

      try {
        if (new URL(String(context.url || "")).searchParams.has("gh_jid")) {
          return true;
        }
      } catch (_error) {
        // Continue with DOM detection.
      }

      return Boolean(
        querySelectorSafe(
          context.document,
          'iframe[src*="greenhouse.io"], iframe[src*="job-boards.greenhouse"]'
        )
      );
    },

    extractJob(context) {
      const found = findDescription(context);
      let jdText = found?.value || "";
      let strategy = "greenhouse_job_description_dom_v1";
      let confidence = "high";

      if (!jdText) {
        jdText = cutBeforeApplicationForm(context.rawText);
        strategy = "greenhouse_pre_application_boundary_v1";
        confidence = jdText ? "medium" : "low";
      }
      if (!jdText) return null;

      return {
        identity: identity(context),
        isolated: {
          jdText,
          postingNotes: [],
          discardedTrackingTags: [],
          strategy,
          confidence,
        },
      };
    },

    getControls(documentObject) {
      const root = formRoot(documentObject);
      if (!root?.querySelectorAll) return null;
      return [...root.querySelectorAll("input, select, textarea")];
    },

    fieldHints(element) {
      const values = [
        element?.getAttribute?.("name"),
        element?.id,
        element?.getAttribute?.("data-mapped-name"),
      ]
        .map((value) => String(value || "").trim().toLowerCase())
        .filter(Boolean);

      const hints = [];
      for (const value of values) {
        if (EXACT_FIELD_HINTS.has(value)) {
          hints.push(EXACT_FIELD_HINTS.get(value));
        }
        const tail = value.split(/\[|\]|\./).filter(Boolean).at(-1);
        if (EXACT_FIELD_HINTS.has(tail)) {
          hints.push(EXACT_FIELD_HINTS.get(tail));
        }
      }
      return [...new Set(hints)];
    },

    diagnostics(context) {
      const embeddedIframe = Boolean(
        querySelectorSafe(
          context.document,
          'iframe[src*="greenhouse.io"], iframe[src*="job-boards.greenhouse"]'
        )
      );
      return {
        hosted_greenhouse: greenhouseHost(context.host),
        embedded_application_iframe: embeddedIframe,
        embedded_iframe_note: embeddedIframe
          ? "Cross-origin embedded Greenhouse frames are detected but not autofilled by v4."
          : "",
      };
    },
  };
});
