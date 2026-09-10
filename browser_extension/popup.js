"use strict";

const PROFILE_STORAGE_KEY = "jobAiHelperProfilePayload";
const BRIDGE_URL_KEY = "jobAiHelperBridgeUrl";
const BRIDGE_TOKEN_KEY = "jobAiHelperBridgeToken";

const profileFile = document.getElementById("profileFile");
const profileStatus = document.getElementById("profileStatus");
const bridgeUrl = document.getElementById("bridgeUrl");
const bridgeToken = document.getElementById("bridgeToken");
const bridgeStatus = document.getElementById("bridgeStatus");
const connectButton = document.getElementById("connectButton");
const extractButton = document.getElementById("extractButton");
const saveCaptureButton = document.getElementById("saveCaptureButton");
const scanButton = document.getElementById("scanButton");
const autofillButton = document.getElementById("autofillButton");
const result = document.getElementById("result");
const copyButton = document.getElementById("copyButton");
const downloadButton = document.getElementById("downloadButton");

let latestResult = null;
let latestJobCapture = null;

function showResult(value) {
  latestResult = value;
  result.textContent = JSON.stringify(value, null, 2);
  copyButton.disabled = false;
  downloadButton.disabled = false;
}

function cleanedBridgeUrl() {
  return String(bridgeUrl.value || "").trim().replace(/\/+$/, "");
}

async function bridgeFetch(path, options = {}) {
  const base = cleanedBridgeUrl();
  const token = String(bridgeToken.value || "").trim();
  if (!base) throw new Error("Bridge URL is required.");
  if (!token) throw new Error("Bridge token is required.");

  const headers = {
    "X-Job-AI-Bridge-Token": token,
    ...(options.headers || {}),
  };

  const response = await fetch(`${base}${path}`, {
    ...options,
    headers,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `Bridge request failed (${response.status}).`);
  }
  return payload;
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  const tab = tabs[0];

  if (!tab?.id) throw new Error("No active browser tab found.");
  if (
    !tab.url ||
    tab.url.startsWith("chrome://") ||
    tab.url.startsWith("edge://") ||
    tab.url.startsWith("about:")
  ) {
    throw new Error("Open a normal job webpage before using the POC.");
  }
  return tab;
}

async function ensureInjected(tabId) {
  await chrome.scripting.executeScript({
    target: { tabId },
    files: ["mapping.js", "jd_cleaning.js", "content.js"],
  });
}

async function sendToActiveTab(message) {
  const tab = await getActiveTab();
  await ensureInjected(tab.id);
  return await chrome.tabs.sendMessage(tab.id, message);
}

async function loadStoredProfileStatus() {
  const stored = await chrome.storage.local.get(PROFILE_STORAGE_KEY);
  const payload = stored[PROFILE_STORAGE_KEY];

  if (!payload) {
    profileStatus.textContent = "No profile loaded.";
    return;
  }

  const profile = payload.application_profile || payload;
  const personal = profile.personal || {};
  const name = [personal.first_name, personal.last_name].filter(Boolean).join(" ");
  profileStatus.textContent = name ? `Loaded profile: ${name}` : "Profile loaded.";
}

async function restoreBridgeSettings() {
  const stored = await chrome.storage.local.get([
    BRIDGE_URL_KEY,
    BRIDGE_TOKEN_KEY,
  ]);

  bridgeUrl.value = stored[BRIDGE_URL_KEY] || "http://127.0.0.1:8765";
  bridgeToken.value = stored[BRIDGE_TOKEN_KEY] || "";
}

async function connectAndLoadProfile({ showConnectionResult = true } = {}) {
  await chrome.storage.local.set({
    [BRIDGE_URL_KEY]: cleanedBridgeUrl(),
    [BRIDGE_TOKEN_KEY]: String(bridgeToken.value || "").trim(),
  });

  const health = await bridgeFetch("/health");
  const profileResponse = await bridgeFetch("/api/v1/application-profile");
  const payload = {
    application_profile: profileResponse.application_profile,
  };

  await chrome.storage.local.set({ [PROFILE_STORAGE_KEY]: payload });
  await loadStoredProfileStatus();

  bridgeStatus.textContent = `Connected to ${health.service || "Job AI Helper bridge"}.`;
  if (showConnectionResult) {
    showResult({
      ok: true,
      action: "bridge_connect",
      bridge: health,
      profile_loaded: true,
    });
  }
  return health;
}

connectButton.addEventListener("click", async () => {
  try {
    await connectAndLoadProfile({ showConnectionResult: true });
  } catch (error) {
    bridgeStatus.textContent = `Connection failed: ${String(error?.message || error)}`;
    showResult({ ok: false, error: String(error?.message || error) });
  }
});

profileFile.addEventListener("change", async () => {
  try {
    const file = profileFile.files?.[0];
    if (!file) return;

    const payload = JSON.parse(await file.text());
    const profile = payload.application_profile || payload;

    if (
      !profile ||
      typeof profile !== "object" ||
      !profile.personal ||
      typeof profile.personal !== "object"
    ) {
      throw new Error(
        "This does not look like a Job AI Helper work-profile JSON export."
      );
    }

    await chrome.storage.local.set({ [PROFILE_STORAGE_KEY]: payload });
    await loadStoredProfileStatus();

    showResult({
      ok: true,
      action: "profile_import",
      file_name: file.name,
      note: "Fallback profile stored locally in the extension.",
    });
  } catch (error) {
    showResult({ ok: false, error: String(error?.message || error) });
  }
});

extractButton.addEventListener("click", async () => {
  try {
    const response = await sendToActiveTab({ type: "JOB_AI_EXTRACT_PAGE" });
    latestJobCapture = response?.data || null;
    saveCaptureButton.disabled = !latestJobCapture?.job?.jd_text;
    showResult(response);
  } catch (error) {
    showResult({ ok: false, error: String(error?.message || error) });
  }
});

saveCaptureButton.addEventListener("click", async () => {
  try {
    if (!latestJobCapture?.job?.jd_text) {
      throw new Error("Extract the current job page before saving it.");
    }

    const response = await bridgeFetch("/api/v1/jd-captures", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(latestJobCapture),
    });

    showResult(response);
  } catch (error) {
    showResult({ ok: false, error: String(error?.message || error) });
  }
});

scanButton.addEventListener("click", async () => {
  try {
    showResult(await sendToActiveTab({ type: "JOB_AI_SCAN_FIELDS" }));
  } catch (error) {
    showResult({ ok: false, error: String(error?.message || error) });
  }
});

autofillButton.addEventListener("click", async () => {
  try {
    const stored = await chrome.storage.local.get(PROFILE_STORAGE_KEY);
    const payload = stored[PROFILE_STORAGE_KEY];

    if (!payload) {
      throw new Error(
        "Connect to Job AI Helper or import job_ai_helper_work_profile.json first."
      );
    }

    showResult(
      await sendToActiveTab({
        type: "JOB_AI_AUTOFILL",
        profilePayload: payload,
      })
    );
  } catch (error) {
    showResult({ ok: false, error: String(error?.message || error) });
  }
});

copyButton.addEventListener("click", async () => {
  if (!latestResult) return;
  await navigator.clipboard.writeText(JSON.stringify(latestResult, null, 2));
  copyButton.textContent = "Copied";
  setTimeout(() => {
    copyButton.textContent = "Copy result JSON";
  }, 1200);
});

downloadButton.addEventListener("click", () => {
  if (!latestResult) return;

  const blob = new Blob([JSON.stringify(latestResult, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "job_ai_helper_browser_poc_result.json";
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

async function initialisePopup() {
  await loadStoredProfileStatus();
  await restoreBridgeSettings();

  if (String(bridgeToken.value || "").trim()) {
    try {
      await connectAndLoadProfile({ showConnectionResult: false });
    } catch (error) {
      bridgeStatus.textContent =
        `Stored pairing could not reconnect: ${String(error?.message || error)}`;
    }
  }
}

initialisePopup().catch((error) => {
  profileStatus.textContent = String(error?.message || error);
});
