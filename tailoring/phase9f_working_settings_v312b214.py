"""Application-local editing preferences, separate from immutable generation inputs."""
from copy import deepcopy
from pathlib import Path
from hashlib import sha256

# A distinct namespace in the existing non-authoritative preference store.
# Never passed to a generation lookup, native scorer or approval gate.
_PREF_GENERATION = "__application_working_settings__"
_PREF_VIEW = "phase9f-working-controls-v1"

LABELS = {
    "adaptive_project_fit_mode": ("adaptive_projects_mode", {
        "balanced": "Balanced (up to 5)", "preserve_generated": "Preserve all generated projects",
        "jd_focused": "JD-focused", "portfolio_quality": "Portfolio Quality Optimization (preview)",
        "manual": "Manual", "legacy": "Keep generated selection (legacy)"}),
    "adaptive_skills_mode": ("adaptive_skills_mode", {
        "balanced": "Balanced (recommended)", "preserve_supported": "Preserve all supported",
        "jd_focused": "JD-focused", "manual": "Manual", "legacy": "Keep generated selection (legacy)"}),
    "bullet_allocation_mode": ("bullet_allocation_mode", {
        "adaptive": "Adaptive", "prefer_available_evidence": "Prefer available evidence",
        "all_canonical_before_fitting": "Fit from all eligible evidence"}),
    "project_header_layout": ("project_header_layout", {"auto": "Auto", "stacked": "Stacked", "inline": "Inline"}),
    "project_metadata_style": ("project_metadata_style", {"pipes": "Pipes", "parentheses": "Parentheses (legacy)"}),
    "page_density_mode": ("page_density_mode", {"none": "Fit only", "balanced": "Balanced", "maximize": "Maximize relevant content"}),
    "spacing_mode": ("spacing_mode", {"source_template": "Preserve original template spacing", "paragraph_spacing": "Paragraph spacing", "blank_line": "Blank line"}),
}
DIRECT = {
    "max_projects": "max_projects", "max_bullets": "max_bullets",
    "use_compact_before_delete": "use_compact_before_delete", "allow_bullet_fusion": "allow_bullet_fusion",
    "prefer_balanced_bullets": "prefer_balanced_bullets", "allow_skills_compaction": "allow_skills_compaction",
    "allow_margin_compaction": "allow_margin_compaction", "spacing_before_first_project": "add_spacing_before_first_project",
    "project_spacing_pt": "project_spacing_pt", "after_projects_spacing_pt": "after_projects_spacing_pt",
    "blank_lines_between_projects": "blank_lines_between_projects", "blank_lines_after_projects": "blank_lines_after_projects",
    "adaptive_project_fit_manual": "adaptive_project_keys", "adaptive_skills_manual": "adaptive_skill_keys",
    "phase9f_bestof_next_mode": "optimizer_mode",
}
CONTROLS = set(LABELS) | set(DIRECT) | {"adaptive_project_count_mode"}


def saved_settings(generation):
    """Return recorded input settings only; no inference from final bullet counts."""
    generation = generation if isinstance(generation, dict) else {}
    stored = generation.get("generation_settings") or {}
    if not isinstance(stored, dict):
        stored = {}
    lifecycle = stored.get("phase9f_f_normal_lifecycle") or {}
    if not isinstance(lifecycle, dict):
        lifecycle = {}
    stage = lifecycle.get("settings") if isinstance(lifecycle.get("settings"), dict) else {}
    fit = lifecycle.get("fit") or {}
    fit_values = fit.get("settings") if isinstance(fit, dict) and isinstance(fit.get("settings"), dict) else {}
    fields = set(DIRECT.values()) | {field for field, _ in LABELS.values()}
    # Old flat settings were used by the ordinary and legacy fitting paths.
    flat = {key: deepcopy(value) for key, value in stored.items() if key in fields and key != "optimizer_mode"}
    generation_fields = {"max_projects", "max_bullets", "bullet_allocation_mode"}
    generation_values = {key: value for key, value in flat.items() if key in generation_fields}
    generation_values.update({key: deepcopy(value) for key, value in stage.items() if key in generation_fields})
    if lifecycle:
        # Do not pretend an unfitted normal generation has used fit defaults.
        fitting_values = {key: deepcopy(value) for key, value in fit_values.items() if key in fields and key not in generation_fields and key != "optimizer_mode"}
    else:
        fitting_values = {key: value for key, value in flat.items() if key not in generation_fields} if generation.get("fit_result") or generation.get("docx_path") else {}
    snapshot = (generation.get("fit_result") or {}).get("fitting_input_snapshot") or {}
    invoked = snapshot.get("fitter_invocation") or {}
    effective = {k: deepcopy(v) for k, v in invoked.items() if k in (
        "max_projects", "max_bullets_per_project", "requested_max_projects",
        "requested_max_bullets_per_project", "project_header_layout", "requested_project_header_layout",
        "page_density_max_fill", "minimum_total_skills")}
    return {"generation_id": str(generation.get("generation_id") or ""),
            "model": lifecycle.get("model") or stored.get("model") or "",
            "generation": generation_values, "fitting": fitting_values, "effective_fitting": effective,
            "fit_status": fit.get("status", "") if isinstance(fit, dict) else ""}


def recorded_optimizer(application_id, generation):
    """Historical display only, not a current verification or approval receipt."""
    if not isinstance(generation, dict) or not generation.get("generation_id"):
        return {}
    if str(generation.get("application_id") or application_id) != str(application_id):
        return {}
    try:
        path = Path(generation.get("docx_path") or (generation.get("fit_result") or {}).get("docx_path") or "")
        if not path.is_file() or path.suffix.lower() != ".docx":
            return {}
        from database.phase9f_bestof_review_state import load_historical_optimizer_settings
        return load_historical_optimizer_settings(int(application_id), str(generation["generation_id"]), sha256(path.read_bytes()).hexdigest())
    except Exception:
        return {}


def widget_values(receipt):
    source = {**receipt.get("generation", {}), **receipt.get("fitting", {})}
    values = {control: deepcopy(source[field]) for control, field in DIRECT.items() if field in source}
    for control, (field, labels) in LABELS.items():
        if source.get(field) in labels:
            values[control] = labels[source[field]]
    return values


def _key(application_id):
    return f"v312b214_working_controls_{int(application_id)}"


def working_values(st, application_id):
    key = _key(application_id)
    if key not in st.session_state:
        try:
            from database.phase9f_bestof_review_state import load_existing_working_preferences
            loaded = load_existing_working_preferences(int(application_id), _PREF_GENERATION, _PREF_VIEW)
        except Exception:
            loaded = {}
        st.session_state[key] = {k: deepcopy(v) for k, v in loaded.items() if k in CONTROLS} if isinstance(loaded, dict) else {}
        st.session_state[key + "_saved"] = deepcopy(st.session_state[key])
    return st.session_state[key]


def persist_working(st, application_id):
    values = working_values(st, application_id)
    marker = _key(application_id) + "_saved"
    if not values or st.session_state.get(marker) == values:
        return
    try:
        from database.phase9f_bestof_review_state import save_bestof_view_preferences
        if save_bestof_view_preferences(int(application_id), _PREF_GENERATION, _PREF_VIEW, values):
            st.session_state[marker] = deepcopy(values)
    except Exception:
        # Preferences never block generation. Current-session controls survive.
        pass


def queue_saved_settings(st, application_id, generation):
    """Explicit user action only. Apply before each affected widget is next rendered."""
    values = widget_values(saved_settings(generation))
    optimizer = recorded_optimizer(application_id, generation)
    if optimizer.get("mode") in ("v35-relevance", "v37-same-work", "v26-fixed") and not optimizer.get("manual"):
        values["phase9f_bestof_next_mode"] = optimizer["mode"]
    if not values:
        return False
    working_values(st, application_id).update(deepcopy(values))
    key = _key(application_id) + "_restore"
    st.session_state[key] = dict(values)
    persist_working(st, application_id)
    return True


def _valid(value, method, options, kwargs):
    if method == "radio":
        return value in options
    if method == "multiselect":
        return isinstance(value, list) and all(v in options for v in value)
    if method == "checkbox":
        return isinstance(value, bool)
    if method in ("slider", "number_input"):
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and kwargs.get("min_value", value) <= value <= kwargs.get("max_value", value))
    return False


def settings_widget(st, application_id, method, *args, **kwargs):
    """Pin defaults independently of restored generation; mirror widget values
    under non-widget keys so navigation/conditional widgets cannot discard them.
    Locked controls remain authoritative and never overwrite working preferences.
    """
    key = kwargs.get("key", "")
    suffix = f"_{int(application_id)}"
    name = key[:-len(suffix)] if key.endswith(suffix) else ""
    render = getattr(st, method)
    if name not in CONTROLS:
        return render(*args, **kwargs)
    if kwargs.get("disabled"):
        # The lock owns the displayed value. Retain the editable preference
        # and force its rehydration when this control becomes editable again.
        st.session_state.setdefault(_key(application_id) + "_disabled", set()).add(name)
        return render(*args, **kwargs)
    values = working_values(st, application_id)
    defaults = st.session_state.setdefault(_key(application_id) + "_defaults", {})
    pending = st.session_state.get(_key(application_id) + "_restore", {})
    options = list(kwargs.get("options", args[1] if len(args) > 1 and method in ("radio", "multiselect") else []))
    disabled = st.session_state.setdefault(_key(application_id) + "_disabled", set())
    if name in pending or name in disabled:
        st.session_state.pop(key, None)
        defaults.pop(name, None)
        pending.pop(name, None)
        disabled.discard(name)
    if key not in st.session_state:
        defaults.pop(name, None)
    if method == "multiselect":
        option_key = _key(application_id) + "_options"
        prior_options = st.session_state.setdefault(option_key, {})
        if name in prior_options and prior_options[name] != options:
            # Preserve still-valid exact keys rather than silently selecting all.
            st.session_state.pop(key, None)
            defaults.pop(name, None)
        prior_options[name] = list(options)
    if name not in defaults:
        candidate = values.get(name, st.session_state.get(key))
        if method == "multiselect" and isinstance(candidate, list):
            # A different generation may not contain the same manual choices.
            candidate = [v for v in candidate if v in options]
        if not _valid(candidate, method, options, kwargs):
            if method == "radio":
                candidate = options[kwargs.get("index", 0)]
            elif method == "multiselect":
                candidate = list(kwargs.get("default") or [])
            else:
                candidate = kwargs.get("value")
        defaults[name] = deepcopy(candidate)
    default = defaults[name]
    if method in ("slider", "number_input") and isinstance(default, (int, float)):
        if isinstance(kwargs.get("value"), float):
            default = float(default)
        elif isinstance(kwargs.get("value"), int):
            default = int(default)
    if not _valid(default, method, options, kwargs):
        if method == "multiselect":
            default = [v for v in default if v in options] if isinstance(default, list) else []
        elif method == "radio":
            default = options[kwargs.get("index", 0)]
        else:
            default = kwargs.get("value")
        defaults[name] = deepcopy(default)
    # Do not set widget state and a conflicting default. Existing Streamlit
    # values are authoritative while the widget survives; missing keys use the mirror.
    if method == "radio":
        kwargs["index"] = options.index(default)
    elif method == "multiselect":
        kwargs["default"] = default
    else:
        kwargs["value"] = default
    result = render(*args, **kwargs)
    if _valid(result, method, options, kwargs):
        values[name] = deepcopy(result)
    return result


def render_saved_settings(st, application_id, generation, *, key_prefix, allow_copy=False):
    receipt = saved_settings(generation)
    recorded = widget_values(receipt)
    optimizer = recorded_optimizer(application_id, generation)
    if optimizer.get("mode") and not optimizer.get("manual"):
        recorded["phase9f_bestof_next_mode"] = optimizer["mode"]
    working = working_values(st, application_id)
    with st.expander("Settings used for this résumé", expanded=False):
        st.caption("Recorded settings are historical inputs, not the number of projects or bullets retained after fitting. Missing settings were not recorded.")
        if receipt["model"]:
            st.caption("Generation model: " + str(receipt["model"]))
        rows = []
        for name in sorted(CONTROLS):
            def display(value):
                if isinstance(value, bool):
                    return "On" if value else "Off"
                if isinstance(value, list):
                    return ", ".join(map(str, value)) or "None selected"
                return str(value)
            rows.append({"Setting": name.replace("_", " "),
                         "Selected draft": display(recorded[name]) if name in recorded else "Not recorded",
                         "Working": display(working[name]) if name in working else "Not set"})
        if rows:
            st.dataframe(rows, hide_index=True, width="stretch")
        else:
            st.caption("No generation settings were recorded for this draft.")
        if receipt["effective_fitting"]:
            st.caption("Effective fitter inputs (separate from generation controls)")
            st.dataframe([{"Setting": k.replace("_", " "), "Value": str(v)} for k, v in receipt["effective_fitting"].items()], hide_index=True, width="stretch")
        if optimizer:
            st.caption("Latest recorded optimizer comparison: " + optimizer["mode"] + " · " + optimizer["status"] + (" · manual trial" if optimizer["manual"] else " · Build and Fit request") + " · " + optimizer["updated_at"])
            st.caption("Historical receipt for these exact DOCX bytes; not a current scoring or approval decision.")
        else:
            st.caption("Historical optimizer mode: Not recorded or matching document unavailable.")
        if allow_copy and recorded and st.button("Copy recorded settings to working controls", key=key_prefix + "_copy_settings"):
            queue_saved_settings(st, application_id, generation)
            st.rerun()
