(function (root, factory) {
  "use strict";

  if (root.JobAISiteAdapters?.frameworkVersion === "adapter-framework-v1") {
    if (typeof module !== "undefined" && module.exports) {
      module.exports = root.JobAISiteAdapters;
    }
    return;
  }

  const api = factory();
  root.JobAISiteAdapters = api;

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";

  const adapters = new Map();

  function register(adapter) {
    if (!adapter || typeof adapter !== "object") {
      throw new Error("Adapter must be an object.");
    }
    const id = String(adapter.id || "").trim();
    if (!id) throw new Error("Adapter id is required.");
    if (typeof adapter.matches !== "function") {
      throw new Error(`Adapter ${id} must provide matches(context).`);
    }
    adapters.set(id, Object.freeze({ ...adapter, id }));
    return adapters.get(id);
  }

  function list() {
    return [...adapters.values()].sort(
      (left, right) =>
        Number(right.priority || 0) - Number(left.priority || 0)
    );
  }

  function resolve(context) {
    for (const adapter of list()) {
      try {
        if (adapter.matches(context || {})) return adapter;
      } catch (_error) {
        // A broken site detector must not block the generic fallback.
      }
    }
    return null;
  }

  return {
    frameworkVersion: "adapter-framework-v1",
    register,
    list,
    resolve,
  };
});
