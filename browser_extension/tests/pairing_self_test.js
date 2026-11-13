"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

async function scenario(failAt) {
  const elements = new Map();
  const storage = { jobAiHelperProfilePayload: { personal: { first_name: "Saved" } } };
  const calls = [];
  const writes = [];
  const context = vm.createContext({
    document: {
      getElementById(id) {
        if (!elements.has(id)) elements.set(id, {
          value: "", type: "password", textContent: "", listeners: {},
          addEventListener(event, handler) { this.listeners[event] = handler; },
        });
        return elements.get(id);
      },
    },
    chrome: { storage: { local: {
      async get() { return { ...storage }; },
      async set(values) { writes.push(values); Object.assign(storage, values); },
      async remove(key) { delete storage[key]; },
    } } },
    async fetch(url, options) {
      calls.push(url);
      assert.equal(options.headers["X-Job-AI-Bridge-Token"], "entered-token");
      assert.equal(writes.length, 0, "No writes before both responses succeed");
      if (!failAt && calls.length === 1) {
        elements.get("bridgeUrl").value = "http://localhost:9999";
        elements.get("bridgeToken").value = "edited-during-validation";
      }
      const failed = calls.length === failAt;
      return {
        ok: !failed, status: failed ? 401 : 200,
        async json() { return failed ? { ok: false } : {
          ok: true, application_profile: { personal: { first_name: "Validated" } },
        }; },
      };
    },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../popup.js"), "utf8"), context);
  // Let the popup's normal asynchronous restore finish before simulating input.
  await new Promise(setImmediate);
  storage.jobAiHelperBridgeToken = "previous-valid-token";
  storage.jobAiHelperBridgeUrl = "http://localhost:8765";
  const original = JSON.stringify(storage);
  elements.get("bridgeUrl").value = "http://127.0.0.1:8765/";
  elements.get("bridgeToken").value = "entered-token";
  assert.equal(elements.get("bridgeToken").type, "password");
  if (failAt) {
    await assert.rejects(vm.runInContext("connectAndLoadProfile()", context), /Pairing token was rejected/);
    assert.equal(JSON.stringify(storage), original);
    assert.equal(writes.length, 0);
  } else {
    await vm.runInContext("connectAndLoadProfile()", context);
    assert.deepEqual(calls, ["http://127.0.0.1:8765/health", "http://127.0.0.1:8765/api/v1/application-profile"]);
    assert.equal(writes.length, 1);
    assert.equal(storage.jobAiHelperBridgeToken, "entered-token");
    const profile = storage.jobAiHelperProfilePayload;
    await elements.get("showBridgeTokenButton").listeners.click();
    assert.equal(elements.get("bridgeToken").type, "text");
    await elements.get("showBridgeTokenButton").listeners.click();
    assert.equal(elements.get("bridgeToken").type, "password");
    await elements.get("clearPairingButton").listeners.click();
    assert.equal(storage.jobAiHelperBridgeToken, undefined);
    assert.equal(storage.jobAiHelperBridgeUrl, "http://127.0.0.1:8765");
    assert.equal(storage.jobAiHelperProfilePayload, profile);
    assert.equal(elements.get("bridgeToken").type, "password");
    await assert.rejects(vm.runInContext('bridgeFetch("/health")', context), /Bridge token is required/);
  }
}

(async () => {
  await scenario(1);
  await scenario(2);
  await scenario(0);
  console.log("Pairing runtime contracts passed (health 401, profile 401, success, visibility, token-only clear).");
})().catch((error) => { console.error(error); process.exitCode = 1; });
