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

  return {
    id: "structured_job",
    version: "structured-job-adapter-v1",
    priority: 30,
    dynamic: false,

    matches(context) {
      return Boolean(jsonLd?.findJobPosting?.(context.document));
    },

    extractJob(context) {
      return jsonLd?.extract?.(context.document) || null;
    },

    fieldHints() { return []; },
    getControls() { return null; },

    diagnostics() {
      return { mode: "schema_org_job_posting" };
    },
  };
});
