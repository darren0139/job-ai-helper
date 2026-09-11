(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.JobAIBatchTabs = api;
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const JOB_HINTS = [
    "career",
    "careers",
    "job",
    "jobs",
    "workday",
    "myworkdayjobs",
    "greenhouse",
    "lever",
    "successfactors",
    "smartrecruiters",
    "oraclecloud",
    "careers.gov.sg",
  ];

  function isHttpUrl(value) {
    try {
      const url = new URL(String(value || ""));
      return url.protocol === "http:" || url.protocol === "https:";
    } catch (_error) {
      return false;
    }
  }

  function isLocalAppUrl(value) {
    try {
      const url = new URL(String(value || ""));
      return url.hostname === "127.0.0.1" || url.hostname === "localhost";
    } catch (_error) {
      return false;
    }
  }

  function permissionPattern(value) {
    if (!isHttpUrl(value)) return null;
    const url = new URL(String(value));
    return `${url.protocol}//${url.host}/*`;
  }

  function capturableTabs(tabs) {
    return (Array.isArray(tabs) ? tabs : []).filter(
      (tab) =>
        Number.isInteger(tab?.id) &&
        isHttpUrl(tab?.url) &&
        !isLocalAppUrl(tab?.url)
    );
  }

  function permissionPatterns(tabs) {
    return [
      ...new Set(
        capturableTabs(tabs)
          .map((tab) => permissionPattern(tab.url))
          .filter(Boolean)
      ),
    ];
  }

  function looksLikeJobTab(tab) {
    const haystack = `${String(tab?.title || "")} ${String(tab?.url || "")}`
      .toLowerCase();
    return JOB_HINTS.some((hint) => haystack.includes(hint));
  }

  function defaultSelected(tab) {
    return Boolean(tab?.active) || looksLikeJobTab(tab);
  }

  function displayLabel(tab) {
    const title = String(tab?.title || "Untitled tab").trim();
    let host = "";
    try {
      host = new URL(String(tab?.url || "")).host;
    } catch (_error) {
      host = "";
    }
    return host ? `${title} — ${host}` : title;
  }

  return {
    isHttpUrl,
    isLocalAppUrl,
    permissionPattern,
    capturableTabs,
    permissionPatterns,
    looksLikeJobTab,
    defaultSelected,
    displayLabel,
  };
});
