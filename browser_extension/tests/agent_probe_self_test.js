"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

async function run() {
  const files = [];
  const messages = [];
  const listeners = {};
  const controls = Object.create(null);
  for (const id of ["targetOrigin", "grantSiteAccess", "status"]) {
    controls[id] = { textContent: "", disabled: true, addEventListener(event, handler) { listeners[`${id}.${event}`] = handler; } };
  }
  let injected = false;
  const chrome = {
    permissions: {
      contains: async () => true,
      request: async () => true,
    },
    tabs: {
      query: async () => [{ id: 42, url: "https://boards.greenhouse.io/demo/jobs/123" }],
      async sendMessage(id, message) {
        assert.equal(id, 42);
        messages.push(message.type);
        if (message.type === "JOB_AI_PING") {
          return injected ? { ok: true, content_version: "browser-content-v4.2" } : null;
        }
        if (message.type === "JOB_AI_EXTRACT_PAGE") {
          return { ok: true, data: { source: { site_adapter: "greenhouse" }, job: { job_title: "Engineer" } } };
        }
        if (message.type === "JOB_AI_SCAN_FIELDS") {
          return { ok: true, data: { site_adapter: "greenhouse", fields: [] } };
        }
        throw new Error("Unexpected action: " + message.type);
      },
    },
    scripting: {
      async executeScript(options) {
        assert.equal(options.target.tabId, 42);
        files.push(...options.files);
        injected = true;
      },
    },
  };
  const context = { window: {}, chrome, document: { getElementById: id => controls[id] }, URL };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "agent_probe.js"), "utf8"), context);
  const probe = context.window.JobAIStage1Probe;
  assert.equal(probe.selectTarget("https://boards.greenhouse.io/demo/jobs/123"), "https://boards.greenhouse.io/*");
  assert.equal(controls.targetOrigin.textContent, "https://boards.greenhouse.io/*");
  const result = await probe.inspect("https://boards.greenhouse.io/demo/jobs/123");
  assert.equal(result.ok, true);
  assert.equal(result.extraction.job.job_title, "Engineer");
  assert.deepEqual(messages, ["JOB_AI_PING", "JOB_AI_PING", "JOB_AI_EXTRACT_PAGE", "JOB_AI_SCAN_FIELDS"]);
  assert.equal(files[0], "mapping.js");
  assert.equal(files[files.length - 1], "content.js");
  assert.ok(!messages.includes("JOB_AI_AUTOFILL"));
  await assert.rejects(() => probe.inspect("https://boards.greenhouse.io.evil.test/jobs/123"));
  assert.ok(listeners["grantSiteAccess.click"]);
  console.log("agent_probe_self_test: PASS (read-only actions, exact tab, current content script)");
}

run().catch(error => { console.error(error); process.exitCode = 1; });
