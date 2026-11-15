---
status: accepted
---

# Server-rendered UI with Bootstrap and HTMX

The management screens are Django templates styled with Bootstrap 5, with
HTMX for partial page updates. Both libraries are stored in
`static/vendor/` at pinned versions (Bootstrap 5.3.3, HTMX 2.0.4), so the
project has no Node.js build step and works offline. This keeps one
language and one codebase for a solo developer, and every screen keeps
Django's permission checks.

## Considered Options

- **React or Vue front end with a Django REST API**: rejected. It needs two
  codebases, an API layer and a JavaScript build, which costs too much time
  for management screens that are mostly forms and lists.
- **Loading the libraries from a CDN**: rejected. Churches may have poor
  connections, and local files keep demos and tests independent of the
  network.

## Consequences

- The later music features (playback, chord sheet viewer) may need richer
  JavaScript. They can add a focused script for their own pages without
  changing this decision for the management side.
- Upgrading Bootstrap or HTMX means replacing the folder under
  `static/vendor/` and updating the paths in `templates/base.html`.
