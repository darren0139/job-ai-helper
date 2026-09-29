"use strict";

const assert = require("node:assert/strict");
const cleaning = require("../jd_cleaning.js");

const sample = `
Singapore Government Agency Website
What the role is
Example agency introduction.
What you will be working on
• Build and operate infrastructure.
What we are looking for
• Skilled in Linux and Python.
• Preferably 1-5 years of relevant working experience.
All new hires are appointed on a two-year contract in the first instance.
As part of the shortlisting process for this role, you may be required to complete a medical declaration and/or undergo further assessment.
All applicants will be updated on the status of their applications within 4 weeks upon closing of the advertisement.
#LI-HL1
About your application process
Apply
Save
`;

const result = cleaning.cleanCareersGovText(sample);

assert.equal(result.strategy, "careers_gov_sections_v2");
assert.equal(result.confidence, "high");

assert.match(result.jdText, /What the role is/);
assert.match(result.jdText, /Skilled in Linux and Python/);
assert.match(result.jdText, /1-5 years/);

assert.doesNotMatch(result.jdText, /two-year contract/);
assert.doesNotMatch(result.jdText, /medical declaration/);
assert.doesNotMatch(result.jdText, /updated on the status/);
assert.doesNotMatch(result.jdText, /#LI-HL1/);

assert.deepEqual(result.postingNotes, [
  "All new hires are appointed on a two-year contract in the first instance.",
  "As part of the shortlisting process for this role, you may be required to complete a medical declaration and/or undergo further assessment.",
  "All applicants will be updated on the status of their applications within 4 weeks upon closing of the advertisement.",
]);

assert.deepEqual(result.discardedTrackingTags, ["#LI-HL1"]);

console.log("jd_cleaning_self_test_v31: passed");
