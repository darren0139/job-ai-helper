"use strict";
// Firefox Stage 1 temporary add-on only. Open its OWN read-only probe tab when installed.
// Never navigate a job tab, fill fields, click an application form, or submit.
browser.runtime.onInstalled.addListener(() => {
  browser.tabs.create({ url: browser.runtime.getURL("agent_probe.html") }).catch(() => {});
});
