# Job AI Helper Browser Integration — Privacy Notice

Last updated: November 13, 2026

This notice applies to the privately distributed / unlisted Firefox build of
Job AI Helper Browser Integration.

## Summary

The extension is designed to work with the Job AI Helper application running
on the same computer. It does not include advertising, analytics, telemetry,
or developer-controlled cloud collection.

The extension does not automatically submit job applications.

## Authentication information

The extension stores the Job AI Helper localhost bridge pairing token entered
by the user. The token is used only to authenticate requests to the local
Job AI Helper bridge.

## Browsing activity

When the user explicitly captures a job page, discovers/selects tabs for batch
capture, or runs supported actions, the extension handles the URL/domain of
the selected page or tab.

## Website content

When the user explicitly chooses to extract or save a job, the extension reads
job-page content such as visible page text, job title, company, location, job
description, and related page metadata. A saved capture is transmitted to the
Job AI Helper bridge on localhost / 127.0.0.1.

## Personally identifying information

The extension can load the user's Job AI Helper application profile from the
local bridge or from a JSON file selected by the user. The profile can contain
contact information such as name, email address, phone number, and postal
address fields.

The profile is stored in Firefox extension-local storage and is used only when
the user explicitly clicks an autofill action. Autofill writes only the
extension's deterministic allow-listed fields into the selected webpage. The
extension does not click a submit button, accept declarations, upload a resume,
or automatically complete an application.

A website may process form-field values through its own page scripts after the
extension fills them, just as it may process values typed manually by the user.

## Where data goes

Job-page captures are sent only to the Job AI Helper bridge URL configured in
the extension. The normal supported configuration is localhost or 127.0.0.1 on
the user's own computer.

The extension itself does not directly send captured job-page data or the
candidate profile to developer-operated analytics services, advertising
services, or third-party AI APIs.

Job AI Helper is a separate local application. If the user later invokes a
feature in that application that uses an external provider, that later action
is outside the browser extension's capture/autofill operation and is controlled
by the application's own configuration and user action.

## Browser permissions

Always-on host access is limited to:

- `http://127.0.0.1/*`
- `http://localhost/*`

Access to normal HTTP(S) job/application sites is requested at runtime only
when the user invokes a feature that needs it, such as selected-tab batch
capture or autofill.

## Local storage and control

The extension may store the local bridge URL, local bridge pairing token, and
locally loaded application profile.

The popup provides a control to clear the saved pairing token. The user can
also remove the extension or clear its extension storage to remove
browser-stored extension data.

Job captures saved to the Job AI Helper local application are managed by that
application's local storage and queue/history controls.

## No automatic application submission

The extension does not automatically submit job applications. It does not
automatically click submit/navigation buttons, accept declarations, or send
applications without the user's review and action.

## Private distribution

This Firefox build is intended for self-distribution / unlisted distribution.
For privacy or support questions, use the private channel through which the
extension was provided.
