(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.JobAIJDCleaning = api;
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const CAREERS_GOV_POSTING_NOTE_PATTERNS = [
    /^all new hires are appointed on a two-year contract\b/i,
    /^as part of the shortlisting process for this role\b/i,
    /^all applicants will be updated on the status of their applications\b/i,
  ];

  const TRACKING_TAG_PATTERN = /^#LI[-_A-Z0-9]+$/i;

  function normalizeLines(text) {
    return String(text || "")
      .split(/\r?\n/)
      .map((line) => line.replace(/\s+/g, " ").trim())
      .filter(Boolean);
  }

  function isTrackingTag(line) {
    return TRACKING_TAG_PATTERN.test(String(line || "").trim());
  }

  function isCareersGovPostingNoteStart(line) {
    return CAREERS_GOV_POSTING_NOTE_PATTERNS.some((pattern) =>
      pattern.test(String(line || "").trim())
    );
  }

  function trimTrailingActions(lines) {
    const result = [...lines];
    while (
      result.length &&
      ["apply", "save"].includes(String(result.at(-1) || "").toLowerCase())
    ) {
      result.pop();
    }
    return result;
  }

  function cleanCareersGovText(rawText) {
    const lines = normalizeLines(rawText);
    const start = lines.findIndex((line) => line === "What the role is");

    if (start < 0) {
      return {
        jdText: String(rawText || "").trim(),
        postingNotes: [],
        discardedTrackingTags: [],
        strategy: "careers_gov_whole_page_fallback_v2",
        confidence: "low",
      };
    }

    let pageEnd = lines.findIndex(
      (line, index) =>
        index > start && line === "About your application process"
    );
    if (pageEnd < 0) pageEnd = lines.length;

    let candidateLines = trimTrailingActions(lines.slice(start, pageEnd));

    const discardedTrackingTags = candidateLines.filter(isTrackingTag);
    candidateLines = candidateLines.filter((line) => !isTrackingTag(line));

    const noteStart = candidateLines.findIndex(isCareersGovPostingNoteStart);
    const jdLines =
      noteStart >= 0
        ? candidateLines.slice(0, noteStart)
        : candidateLines;
    const postingNotes =
      noteStart >= 0
        ? candidateLines.slice(noteStart)
        : [];

    return {
      jdText: trimTrailingActions(jdLines).join("\n"),
      postingNotes,
      discardedTrackingTags,
      strategy: "careers_gov_sections_v2",
      confidence: "high",
    };
  }

  return {
    normalizeLines,
    isTrackingTag,
    isCareersGovPostingNoteStart,
    cleanCareersGovText,
  };
});
