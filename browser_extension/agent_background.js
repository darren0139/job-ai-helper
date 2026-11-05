"use strict";
// Stage 1 only: make the unpacked MV3 extension discoverable by Playwright.
// No browser action, messaging endpoint, network request or persisted state.
chrome.runtime.onInstalled.addListener(() => {});
chrome.runtime.onStartup.addListener(() => {});
