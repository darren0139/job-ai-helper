(function (root, factory) {
  "use strict";

  let cleaning = root.JobAIJDCleaning;
  if (!cleaning && typeof module !== "undefined" && module.exports) {
    cleaning = require("../jd_cleaning.js");
  }

  const adapter = factory(cleaning);
  if (root.JobAISiteAdapters) root.JobAISiteAdapters.register(adapter);
  if (typeof module !== "undefined" && module.exports) module.exports = adapter;
})(typeof self !== "undefined" ? self : globalThis, function (cleaning) {
  "use strict";

  const HOSTS = new Set([
    "jobs.careers.gov.sg",
    "www.careers.hrp.gov.sg",
    "careers.hrp.gov.sg",
  ]);

  function clean(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function identity(context) {
    const headings = Array.isArray(context.headings) ? context.headings : [];
    const rawText = String(context.rawText || "");
    const documentTitle = clean(context.documentTitle);

    const title =
      headings.find((heading) =>
        ![
          "What the role is",
          "What you will be working on",
          "What we are looking for",
          "About your application process",
        ].includes(clean(heading))
      ) ||
      documentTitle.replace(/\s*\|\s*Careers@Gov\s*$/i, "").trim();

    let company = "";
    const aboutHeading = headings.find(
      (heading) =>
        /^About\s+/i.test(clean(heading)) &&
        !/^About your application process$/i.test(clean(heading))
    );
    if (aboutHeading) {
      company = clean(aboutHeading).replace(/^About\s+/i, "").trim();
    }

    if (!company && cleaning?.normalizeLines) {
      const lines = cleaning.normalizeLines(rawText);
      const titleIndex = lines.findIndex((line) => line === title);
      if (titleIndex > 0) {
        const before = lines
          .slice(Math.max(0, titleIndex - 4), titleIndex)
          .filter((line) => line !== "/" && line !== line.toUpperCase());
        company = before.at(-1) || "";
      }
    }

    return { title, company, location: "" };
  }

  return {
    id: "careers_gov",
    version: "careers-gov-adapter-v1",
    priority: 100,

    matches(context) {
      return HOSTS.has(String(context.host || "").toLowerCase());
    },

    extractJob(context) {
      if (!cleaning?.cleanCareersGovText) return null;
      return {
        identity: identity(context),
        isolated: cleaning.cleanCareersGovText(context.rawText),
      };
    },

    fieldHints(element) {
      const identityText = [
        element?.id,
        element?.getAttribute?.("name"),
        element?.getAttribute?.("data-sap-ui"),
      ]
        .map(clean)
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      const hints = [];
      if (/ipname|fullname|full_name/.test(identityText)) hints.push("full name");
      if (/noticeperiod|notice_period/.test(identityText)) hints.push("notice period");
      return hints;
    },

    getControls() { return null; },

    diagnostics() {
      return { framework: "sap_ui5_plus_standard_controls" };
    },
  };
});
