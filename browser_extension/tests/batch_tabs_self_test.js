"use strict";

const assert = require("node:assert/strict");
const batch = require("../batch_tabs.js");

const tabs = [
  {
    id: 1,
    active: false,
    title: "DevOps Engineer | Careers@Gov",
    url: "https://jobs.careers.gov.sg/jobs/hrp/123",
  },
  {
    id: 2,
    active: false,
    title: "Software Engineer",
    url: "https://company.example/careers/456",
  },
  {
    id: 3,
    active: true,
    title: "Random article",
    url: "https://news.example/article",
  },
  {
    id: 4,
    active: false,
    title: "Job AI Helper",
    url: "http://127.0.0.1:8501/",
  },
  {
    id: 5,
    active: false,
    title: "Extensions",
    url: "chrome://extensions/",
  },
];

assert.equal(batch.isHttpUrl(tabs[0].url), true);
assert.equal(batch.isHttpUrl(tabs[4].url), false);
assert.equal(batch.isLocalAppUrl(tabs[3].url), true);

assert.deepEqual(
  batch.capturableTabs(tabs).map((tab) => tab.id),
  [1, 2, 3]
);

assert.deepEqual(batch.permissionPatterns(tabs), [
  "https://jobs.careers.gov.sg/*",
  "https://company.example/*",
  "https://news.example/*",
]);

assert.equal(batch.looksLikeJobTab(tabs[0]), true);
assert.equal(batch.looksLikeJobTab(tabs[1]), true);
assert.equal(batch.defaultSelected(tabs[2]), true);
assert.match(batch.displayLabel(tabs[0]), /jobs\.careers\.gov\.sg/);

console.log("batch_tabs_self_test_v4: passed");
