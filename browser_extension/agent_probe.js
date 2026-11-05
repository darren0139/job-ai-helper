(() => {
  "use strict";

  const CONTENT_VERSION = "browser-content-v4.2";
  // Identical load order to popup.js ensureInjected() as of the pinned baseline.
  const SCRIPT_FILES = Object.freeze([
    "mapping.js",
    "jd_cleaning.js",
    "adapters/registry.js",
    "adapters/job_posting_jsonld.js",
    "adapters/generic.js",
    "adapters/careers_gov.js",
    "adapters/greenhouse.js",
    "adapters/workday.js",
    "adapters/phenom.js",
    "adapters/successfactors.js",
    "adapters/mycareersfuture.js",
    "adapters/smartrecruiters.js",
    "adapters/linkedin.js",
    "adapters/structured_job.js",
    "content.js",
  ]);
  const label = document.getElementById("targetOrigin");
  const button = document.getElementById("grantSiteAccess");
  const status = document.getElementById("status");
  let allowedPattern = "";

  function permissionPattern(targetUrl) {
    const url = new URL(String(targetUrl));
    if (url.username || url.password || url.hash) throw new Error("URL credentials/fragments are unsupported.");
    if (url.protocol !== "https:" &&
      !(url.protocol === "http:" && ["127.0.0.1", "localhost"].includes(url.hostname))) {
      throw new Error("Only HTTPS or localhost fixture pages are supported.");
    }
    return `${url.protocol}//${url.hostname}/*`;
  }

  function selectTarget(targetUrl) {
    allowedPattern = permissionPattern(targetUrl);
    label.textContent = allowedPattern;
    button.disabled = false;
    status.textContent = "Target selected. Site access may be required.";
    return allowedPattern;
  }

  button.addEventListener("click", async () => {
    if (!allowedPattern) return;
    try {
      const granted = await chrome.permissions.request({ origins: [allowedPattern] });
      status.textContent = granted ? "Site access granted." : "Site access declined.";
    } catch (error) {
      status.textContent = `Site access error: ${String(error?.message || error)}`;
    }
  });

  async function hasAccess() {
    return Boolean(allowedPattern && await chrome.permissions.contains({ origins: [allowedPattern] }));
  }

  async function ping(tabId) {
    try {
      return await chrome.tabs.sendMessage(tabId, { type: "JOB_AI_PING" });
    } catch (_error) {
      return null;
    }
  }

  async function inspect(targetUrl) {
    const expectedPattern = permissionPattern(targetUrl);
    if (!allowedPattern || expectedPattern !== allowedPattern) {
      throw new Error("Target URL does not match the selected site.");
    }
    if (!(await hasAccess())) {
      throw new Error("SITE_ACCESS_REQUIRED: approve this site's permission in the probe tab.");
    }

    const requested = new URL(targetUrl).href;
    const tabs = await chrome.tabs.query({});
    const matches = tabs.filter((tab) => tab.id && tab.url === requested);
    if (matches.length !== 1) {
      throw new Error(`EXPECTED_ONE_JOB_TAB: found ${matches.length} tabs for requested URL.`);
    }
    const tabId = matches[0].id;
    let response = await ping(tabId);
    if (!response?.ok || response.content_version !== CONTENT_VERSION) {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: SCRIPT_FILES,
      });
      response = await ping(tabId);
    }
    if (!response?.ok || response.content_version !== CONTENT_VERSION) {
      throw new Error("The existing Job AI Helper content script did not respond correctly.");
    }

    // Do NOT call JOB_AI_AUTOFILL or mutate the application form.
    const extraction = await chrome.tabs.sendMessage(tabId, { type: "JOB_AI_EXTRACT_PAGE" });
    const scan = await chrome.tabs.sendMessage(tabId, { type: "JOB_AI_SCAN_FIELDS" });
    if (!extraction?.ok || !scan?.ok) {
      throw new Error(`Extension extraction/scan failed: ${String(extraction?.error || scan?.error || "unknown")}`);
    }
    return {
      ok: true,
      content_version: response.content_version,
      extraction: extraction.data,
      scan: scan.data,
    };
  }

  window.JobAIStage1Probe = Object.freeze({ selectTarget, hasAccess, inspect });
})();
