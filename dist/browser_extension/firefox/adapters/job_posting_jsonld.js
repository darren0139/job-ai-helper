(function (root, factory) {
  "use strict";
  const api = factory();
  root.JobAIJobPostingJsonLd = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";

  function clean(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function decodeEntities(value) {
    return String(value || "")
      .replace(/&nbsp;/gi, " ")
      .replace(/&amp;/gi, "&")
      .replace(/&lt;/gi, "<")
      .replace(/&gt;/gi, ">")
      .replace(/&quot;/gi, '"')
      .replace(/&#39;|&apos;/gi, "'");
  }

  function htmlToText(value) {
    return decodeEntities(String(value || ""))
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/(?:p|div|li|ul|ol|h[1-6]|section|article)>/gi, "\n")
      .replace(/<li\b[^>]*>/gi, "• ")
      .replace(/<[^>]+>/g, " ")
      .split(/\r?\n/)
      .map((line) => line.replace(/[ \t]+/g, " ").trim())
      .filter(Boolean)
      .join("\n")
      .trim();
  }

  function flattenJsonLd(value, output = []) {
    if (Array.isArray(value)) {
      for (const item of value) flattenJsonLd(item, output);
      return output;
    }
    if (!value || typeof value !== "object") return output;

    output.push(value);
    if (Array.isArray(value["@graph"])) {
      for (const item of value["@graph"]) flattenJsonLd(item, output);
    }
    return output;
  }

  function jsonLdObjects(documentObject) {
    const scripts = [
      ...(documentObject?.querySelectorAll?.('script[type="application/ld+json"]') || []),
    ];

    const objects = [];
    for (const script of scripts) {
      const raw = String(script?.textContent || script?.innerText || "").trim();
      if (!raw) continue;
      try {
        flattenJsonLd(JSON.parse(raw), objects);
      } catch (_error) {
        // Invalid third-party structured data must never break extraction.
      }
    }
    return objects;
  }

  function hasType(value, expected) {
    const type = value?.["@type"];
    if (Array.isArray(type)) return type.includes(expected);
    return type === expected;
  }

  function findJobPosting(documentObject) {
    return (
      jsonLdObjects(documentObject).find((item) => hasType(item, "JobPosting")) ||
      null
    );
  }

  function addressText(address) {
    if (!address || typeof address !== "object") return "";
    return [
      address.addressLocality,
      address.addressRegion,
      address.addressCountry?.name || address.addressCountry,
    ]
      .map(clean)
      .filter(Boolean)
      .join(", ");
  }

  function locationText(jobLocation) {
    const locations = Array.isArray(jobLocation) ? jobLocation : [jobLocation];
    return [
      ...new Set(
        locations
          .map((item) => {
            if (!item || typeof item !== "object") return "";
            return addressText(item.address || item);
          })
          .filter(Boolean)
      ),
    ].join(" / ");
  }

  function companyText(posting) {
    const organization = posting?.hiringOrganization;
    if (typeof organization === "string") return clean(organization);
    return clean(organization?.name);
  }

  function extract(documentObject) {
    const posting = findJobPosting(documentObject);
    if (!posting) return null;

    const title = clean(posting.title || posting.name);
    const company = companyText(posting);
    const location = locationText(posting.jobLocation);
    const description = htmlToText(posting.description);

    if (!title && description.length < 120) return null;

    return {
      identity: {
        title,
        company,
        location,
      },
      isolated: {
        jdText: description,
        postingNotes: [],
        discardedTrackingTags: [],
        strategy: "job_posting_jsonld_v1",
        confidence: description.length >= 300 ? "high" : "medium",
      },
      structured: posting,
    };
  }

  return {
    clean,
    htmlToText,
    jsonLdObjects,
    findJobPosting,
    locationText,
    companyText,
    extract,
  };
});
