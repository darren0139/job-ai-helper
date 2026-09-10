"use strict";

const assert = require("node:assert/strict");
const mapping = require("../mapping.js");

function expectKey(label, key) {
  const match = mapping.classifyField(label);
  assert.ok(match, `Expected a match for ${JSON.stringify(label)}`);
  assert.equal(match.key, key);
}

expectKey("Full name | Enter full name | __xmlview0--ipName-inner", "full_name");
expectKey("First Name", "first_name");
expectKey("Given name *", "first_name");
expectKey("Surname", "last_name");
expectKey("Email Address", "email");
expectKey("Mobile Number", "phone");
expectKey("LinkedIn Profile URL", "linkedin_url");
expectKey("GitHub", "github_url");
expectKey(
  "Notice period | e.g. immediately, within one month",
  "notice_period"
);
expectKey("Do you require sponsorship", "requires_sponsorship");

assert.equal(
  mapping.classifyField("Tell us about sponsorship arrangements"),
  null,
  "Sponsorship mapping must stay strict."
);

assert.equal(
  mapping.classifyField("NRIC / Passport / FIN number"),
  null,
  "Government identity numbers must never be generically mapped."
);

assert.equal(
  mapping.profileValue(
    {
      application_profile: {
        personal: { first_name: "Keith", last_name: "Lua" },
      },
    },
    { section: "derived", key: "full_name" }
  ),
  "Keith Lua"
);

assert.equal(
  mapping.profileValue(
    {
      application_profile: {
        availability: { notice_period: "Immediate" },
      },
    },
    { section: "availability", key: "notice_period" }
  ),
  "Immediate"
);

assert.equal(
  mapping.isSupportedProfilePayload({
    application_profile: { personal: {} },
  }),
  true
);

console.log("mapping_self_test_v2: passed");
