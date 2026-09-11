(function (root, factory) {
  "use strict";
  const adapter = factory();
  if (root.JobAISiteAdapters) root.JobAISiteAdapters.register(adapter);
  if (typeof module !== "undefined" && module.exports) module.exports = adapter;
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";
  return {
    id: "generic",
    version: "generic-adapter-v1",
    priority: -1000,
    matches() { return true; },
    extractJob() { return null; },
    fieldHints() { return []; },
    getControls() { return null; },
    diagnostics() { return { mode: "generic_fallback" }; },
  };
});
