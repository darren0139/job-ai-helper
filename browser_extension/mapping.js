(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.JobAIFieldMapping = api;
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const FIELD_RULES = [
    {
      key: "full_name",
      section: "derived",
      aliases: ["full name", "legal name", "name as in identification"],
    },
    {
      key: "first_name",
      section: "personal",
      aliases: ["first name", "given name", "forename", "given names"],
    },
    {
      key: "last_name",
      section: "personal",
      aliases: ["last name", "surname", "family name"],
    },
    {
      key: "preferred_name",
      section: "personal",
      aliases: ["preferred name", "name you prefer", "preferred first name"],
    },
    {
      key: "email",
      section: "personal",
      aliases: ["email", "email address", "e-mail", "e-mail address"],
    },
    {
      key: "phone",
      section: "personal",
      aliases: [
        "phone",
        "phone number",
        "mobile",
        "mobile number",
        "contact number",
        "telephone",
        "telephone number",
      ],
    },
    {
      key: "current_location",
      section: "personal",
      aliases: [
        "current location",
        "current country",
        "country of residence",
        "current country of residence",
      ],
    },
    {
      key: "linkedin_url",
      section: "personal",
      aliases: [
        "linkedin",
        "linkedin url",
        "linkedin profile",
        "linkedin profile url",
      ],
    },
    {
      key: "github_url",
      section: "personal",
      aliases: [
        "github",
        "github url",
        "github profile",
        "github profile url",
      ],
    },
    {
      key: "notice_period",
      section: "availability",
      aliases: ["notice period", "notice period required", "availability notice period"],
    },
    {
      key: "requires_sponsorship",
      section: "work_eligibility",
      exactOnly: true,
      aliases: [
        "do you require sponsorship",
        "do you require visa sponsorship",
        "will you require sponsorship",
        "will you require visa sponsorship",
        "will you now or in the future require sponsorship",
        "will you now or in the future require visa sponsorship",
        "do you need sponsorship",
        "do you need visa sponsorship",
        "requires sponsorship",
        "require sponsorship",
      ],
    },
  ];

  function normalizeText(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[\u2018\u2019'"]/g, "")
      .replace(/[^a-z0-9]+/g, " ")
      .trim()
      .replace(/\s+/g, " ");
  }

  function compactText(value) {
    return normalizeText(value).replace(/\s+/g, "");
  }

  function scoreAlias(label, alias, exactOnly) {
    const normalizedLabel = normalizeText(label);
    const normalizedAlias = normalizeText(alias);

    if (!normalizedLabel || !normalizedAlias) return 0;
    if (normalizedLabel === normalizedAlias) return 100;
    if (exactOnly) return 0;

    const labelCompact = compactText(normalizedLabel);
    const aliasCompact = compactText(normalizedAlias);

    if (labelCompact === aliasCompact) return 95;
    if (
      normalizedLabel.startsWith(normalizedAlias + " ") ||
      normalizedLabel.endsWith(" " + normalizedAlias)
    ) {
      return 85;
    }
    if (normalizedLabel.includes(normalizedAlias)) return 70;
    return 0;
  }

  function classifyField(labelText) {
    let best = null;

    for (const rule of FIELD_RULES) {
      for (const alias of rule.aliases) {
        const score = scoreAlias(labelText, alias, Boolean(rule.exactOnly));
        if (!score) continue;

        if (!best || score > best.score) {
          best = {
            key: rule.key,
            section: rule.section,
            score,
            alias,
          };
        }
      }
    }

    return best;
  }

  function applicationProfile(profilePayload) {
    return profilePayload?.application_profile || profilePayload || {};
  }

  function profileValue(profilePayload, match) {
    if (!profilePayload || !match) return "";

    const profile = applicationProfile(profilePayload);

    if (match.section === "derived" && match.key === "full_name") {
      const personal = profile.personal || {};
      return [personal.first_name, personal.last_name]
        .map((value) => String(value || "").trim())
        .filter(Boolean)
        .join(" ");
    }

    const section = profile[match.section] || {};
    return String(section[match.key] || "").trim();
  }

  function isSupportedProfilePayload(payload) {
    if (!payload || typeof payload !== "object") return false;
    const profile = applicationProfile(payload);
    return Boolean(
      profile &&
      typeof profile === "object" &&
      profile.personal &&
      typeof profile.personal === "object"
    );
  }

  return {
    FIELD_RULES,
    normalizeText,
    classifyField,
    profileValue,
    isSupportedProfilePayload,
  };
});
