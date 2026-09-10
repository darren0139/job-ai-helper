(() => {
  "use strict";

  if (self.__JOB_AI_HELPER_CONTENT_V2__) return;
  self.__JOB_AI_HELPER_CONTENT_V2__ = true;

  const mapping = self.JobAIFieldMapping;
  const jdCleaning = self.JobAIJDCleaning;
  if (!mapping) throw new Error("JobAIFieldMapping is not loaded.");
  if (!jdCleaning) throw new Error("JobAIJDCleaning is not loaded.");

  const BASIC_TYPES = new Set(["text", "email", "tel", "url", "search", "number"]);

  function visibleElement(element) {
    if (!(element instanceof Element)) return false;
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return (
      style.display !== "none" &&
      style.visibility !== "hidden" &&
      rect.width > 0 &&
      rect.height > 0
    );
  }

  function textOf(element) {
    return String(element?.innerText || element?.textContent || "").trim();
  }

  function uniquePieces(pieces) {
    return [...new Set(pieces.map((value) => String(value || "").trim()).filter(Boolean))];
  }

  function associatedLabelElements(element) {
    const labels = [];
    if (element.labels) labels.push(...element.labels);

    const ariaLabelledBy = element.getAttribute("aria-labelledby");
    if (ariaLabelledBy) {
      for (const id of ariaLabelledBy.split(/\s+/)) {
        const labelled = document.getElementById(id);
        if (labelled) labels.push(labelled);
      }
    }

    const closestLabel = element.closest("label");
    if (closestLabel) labels.push(closestLabel);

    return [...new Set(labels)];
  }

  function nearbyDiagnosticText(element) {
    const candidates = [];
    let current = element.parentElement;

    for (let depth = 0; current && depth < 4; depth += 1) {
      const value = textOf(current).replace(/\s+/g, " ").trim();
      if (value && value.length <= 500) candidates.push(value);
      current = current.parentElement;
    }

    return uniquePieces(candidates).slice(0, 3).join(" | ").slice(0, 900);
  }

  function associatedLabelText(element) {
    const pieces = associatedLabelElements(element).map(textOf);

    const ariaLabel = element.getAttribute("aria-label");
    if (ariaLabel) pieces.push(ariaLabel);

    const placeholder = element.getAttribute("placeholder");
    if (placeholder) pieces.push(placeholder);

    const name = element.getAttribute("name");
    if (name) pieces.push(name);

    const id = element.getAttribute("id");
    if (id) pieces.push(id);

    const parent = element.parentElement;
    if (parent) {
      for (const candidate of [parent.previousElementSibling, element.previousElementSibling]) {
        const value = textOf(candidate);
        if (value && value.length <= 180) pieces.push(value);
      }
    }

    return uniquePieces(pieces).join(" | ").slice(0, 500);
  }

  function fieldKind(element) {
    const tag = element.tagName.toLowerCase();
    if (tag === "select") return "select";
    if (tag === "textarea") return "textarea";
    if (tag === "input") {
      const type = String(element.type || "text").toLowerCase();
      if (type === "radio") return "radio";
      if (type === "checkbox") return "checkbox";
      return type;
    }
    return tag;
  }

  function isRequiredControl(element) {
    if (Boolean(element.required)) return true;
    if (String(element.getAttribute("aria-required") || "").toLowerCase() === "true") {
      return true;
    }

    for (const label of associatedLabelElements(element)) {
      if (
        label.classList.contains("sapMLabelRequired") ||
        label.classList.contains("sapMLabelRequiredIndicator")
      ) {
        return true;
      }
      const ariaRequired = String(label.getAttribute("aria-required") || "").toLowerCase();
      if (ariaRequired === "true") return true;
    }

    return false;
  }

  function getStandardControls() {
    return [...document.querySelectorAll("input, select, textarea")]
      .filter((element) => !element.disabled)
      .filter((element) => element.type !== "hidden");
  }

  function scanFields() {
    const fields = getStandardControls().map((element, index) => {
      const label = associatedLabelText(element);
      const match = mapping.classifyField(label);

      return {
        index,
        tag: element.tagName.toLowerCase(),
        kind: fieldKind(element),
        id: element.id || "",
        name: element.getAttribute("name") || "",
        classes: String(element.className || "").slice(0, 300),
        label,
        nearby_text: match ? "" : nearbyDiagnosticText(element),
        matched_key: match?.key || null,
        matched_section: match?.section || null,
        match_score: match?.score || 0,
        required: isRequiredControl(element),
        visible: visibleElement(element),
        aria_required: element.getAttribute("aria-required") || "",
        aria_label: element.getAttribute("aria-label") || "",
        aria_labelledby: element.getAttribute("aria-labelledby") || "",
      };
    });

    return {
      schema_version: 2,
      url: location.href,
      title: document.title,
      site_adapter: detectSiteAdapter(),
      standard_control_count: fields.length,
      visible_standard_control_count: fields.filter((field) => field.visible).length,
      mapped_field_count: fields.filter((field) => field.matched_key).length,
      unmatched_visible_count: fields.filter(
        (field) => field.visible && !field.matched_key
      ).length,
      fields,
    };
  }

  function findMainTextRoot() {
    const candidates = [
      document.querySelector("main"),
      document.querySelector("article"),
      document.querySelector('[role="main"]'),
      document.querySelector("#content"),
      document.querySelector(".content"),
      document.body,
    ].filter(Boolean);

    for (const candidate of candidates) {
      const value = textOf(candidate);
      if (value.length >= 300) return candidate;
    }
    return document.body;
  }

  function detectSiteAdapter() {
    const host = location.hostname.toLowerCase();
    if (
      host === "jobs.careers.gov.sg" ||
      host === "www.careers.hrp.gov.sg" ||
      host === "careers.hrp.gov.sg"
    ) {
      return "careers_gov";
    }
    return "generic";
  }

  function careersGovIdentity(headings, rawText) {
    const title =
      headings.find((heading) =>
        ![
          "What the role is",
          "What you will be working on",
          "What we are looking for",
          "About your application process",
        ].includes(heading)
      ) ||
      document.title.replace(/\s*\|\s*Careers@Gov\s*$/i, "").trim();

    let company = "";
    const aboutHeading = headings.find(
      (heading) =>
        /^About\s+/i.test(heading) &&
        !/^About your application process$/i.test(heading)
    );
    if (aboutHeading) company = aboutHeading.replace(/^About\s+/i, "").trim();

    if (!company) {
      const lines = jdCleaning.normalizeLines(rawText);
      const titleIndex = lines.findIndex((line) => line === title);
      if (titleIndex > 0) {
        const before = lines
          .slice(Math.max(0, titleIndex - 4), titleIndex)
          .filter((line) => line !== "/" && line !== line.toUpperCase());
        company = before.at(-1) || "";
      }
    }

    return { title, company };
  }

  function genericJobIdentity(headings) {
    const title = headings[0] || document.title || "";
    return { title, company: "" };
  }

  function extractJobPage() {
    const root = findMainTextRoot();
    const rawText = textOf(root).replace(/\n{3,}/g, "\n\n").trim();
    const headings = [...document.querySelectorAll("h1, h2, h3, [role='heading']")]
      .filter(visibleElement)
      .map(textOf)
      .filter(Boolean)
      .slice(0, 80);

    const siteAdapter = detectSiteAdapter();
    let identity;
    let isolated;

    if (siteAdapter === "careers_gov") {
      identity = careersGovIdentity(headings, rawText);
      isolated = jdCleaning.cleanCareersGovText(rawText);
    } else {
      identity = genericJobIdentity(headings);
      isolated = {
        jdText: rawText,
        strategy: "generic_visible_main_text",
        confidence: "medium",
      };
    }

    const capturedAt = new Date().toISOString();

    return {
      schema_version: 2,
      source: {
        captured_at: capturedAt,
        url: location.href,
        host: location.hostname,
        document_title: document.title,
        source_type: "browser_extension",
        site_adapter: siteAdapter,
      },
      capture: {
        headings,
        raw_visible_text: rawText,
        character_count: rawText.length,
      },
      job: {
        job_title: identity.title || "",
        company: identity.company || "",
        location: "",
        jd_text: isolated.jdText || "",
        jd_character_count: String(isolated.jdText || "").length,
        posting_notes: Array.isArray(isolated.postingNotes)
          ? isolated.postingNotes
          : [],
        discarded_tracking_tags: Array.isArray(isolated.discardedTrackingTags)
          ? isolated.discardedTrackingTags
          : [],
        cleaning_strategy: isolated.strategy,
        cleaning_confidence: isolated.confidence,
      },
    };
  }

  function nativeSetValue(element, value) {
    const prototype =
      element instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype;

    const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
    if (descriptor?.set) descriptor.set.call(element, value);
    else element.value = value;

    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    element.dispatchEvent(new Event("blur", { bubbles: true }));
  }

  function setSelectValue(select, value) {
    const target = mapping.normalizeText(value);
    const option = [...select.options].find((candidate) => {
      return (
        mapping.normalizeText(candidate.value) === target ||
        mapping.normalizeText(candidate.textContent) === target
      );
    });

    if (!option) return false;
    select.value = option.value;
    select.dispatchEvent(new Event("input", { bubbles: true }));
    select.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function groupQuestionText(radio) {
    const fieldset = radio.closest("fieldset");
    if (fieldset) {
      const legend = fieldset.querySelector("legend");
      const value = textOf(legend);
      if (value) return value;
    }
    return associatedLabelText(radio);
  }

  function radioOptionText(radio) {
    const pieces = [];
    if (radio.labels) {
      for (const label of radio.labels) pieces.push(textOf(label));
    }
    if (radio.value) pieces.push(radio.value);
    const closestLabel = radio.closest("label");
    if (closestLabel) pieces.push(textOf(closestLabel));
    return uniquePieces(pieces).join(" | ");
  }

  function fillRadioGroup(radio, value) {
    const name = radio.getAttribute("name");
    if (!name) return false;

    const target = mapping.normalizeText(value);
    const radios = [
      ...document.querySelectorAll(
        `input[type="radio"][name="${CSS.escape(name)}"]`
      ),
    ];

    const candidate = radios.find((item) => {
      const optionText = mapping.normalizeText(radioOptionText(item));
      return (
        optionText === target ||
        optionText.startsWith(target + " ") ||
        optionText.includes(" " + target + " ")
      );
    });

    if (!candidate) return false;
    candidate.click();
    candidate.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function autofill(profilePayload) {
    if (!mapping.isSupportedProfilePayload(profilePayload)) {
      return { ok: false, error: "Unsupported Job AI Helper profile payload." };
    }

    const controls = getStandardControls();
    const processedRadioNames = new Set();
    const results = [];

    for (const element of controls) {
      const kind = fieldKind(element);
      let label = associatedLabelText(element);

      if (kind === "radio") {
        const name = element.getAttribute("name") || "";
        if (!name || processedRadioNames.has(name)) continue;
        processedRadioNames.add(name);
        label = groupQuestionText(element);
      }

      const match = mapping.classifyField(label);
      if (!match) continue;

      const value = mapping.profileValue(profilePayload, match);
      if (!value) {
        results.push({
          status: "skipped_unknown",
          key: match.key,
          label,
          kind,
        });
        continue;
      }

      let filled = false;
      let reason = "";

      try {
        if (element instanceof HTMLInputElement && BASIC_TYPES.has(kind)) {
          nativeSetValue(element, value);
          filled = true;
        } else if (element instanceof HTMLTextAreaElement) {
          nativeSetValue(element, value);
          filled = true;
        } else if (element instanceof HTMLSelectElement) {
          filled = setSelectValue(element, value);
          if (!filled) reason = "matching select option not found";
        } else if (kind === "radio") {
          filled = fillRadioGroup(element, value);
          if (!filled) reason = "matching radio option not found";
        } else {
          reason = "unsupported standard control type";
        }
      } catch (error) {
        reason = String(error?.message || error);
      }

      results.push({
        status: filled ? "filled" : "not_filled",
        key: match.key,
        label,
        kind,
        reason,
      });
    }

    return {
      ok: true,
      schema_version: 2,
      url: location.href,
      filled_count: results.filter((item) => item.status === "filled").length,
      skipped_unknown_count: results.filter(
        (item) => item.status === "skipped_unknown"
      ).length,
      not_filled_count: results.filter(
        (item) => item.status === "not_filled"
      ).length,
      results,
      note:
        "This POC never clicks submit/navigation buttons. Review the page manually.",
    };
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    try {
      if (message?.type === "JOB_AI_EXTRACT_PAGE") {
        sendResponse({ ok: true, data: extractJobPage() });
        return;
      }
      if (message?.type === "JOB_AI_SCAN_FIELDS") {
        sendResponse({ ok: true, data: scanFields() });
        return;
      }
      if (message?.type === "JOB_AI_AUTOFILL") {
        sendResponse(autofill(message.profilePayload));
        return;
      }
      sendResponse({ ok: false, error: "Unknown Job AI Helper action." });
    } catch (error) {
      sendResponse({ ok: false, error: String(error?.message || error) });
    }
  });
})();
