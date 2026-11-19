# Board templates

Real DOM skeletons and chrome captured from live public postings on 2026-11-18, scrubbed of
company names, ids and logos, with posting content replaced by slots (regenerate with
`uv run python -m evals.capture_templates <raw_dir>`; raw pages are not committed).

Slots: `{{TITLE}} {{COMPANY}} {{COMPANY_SLUG}} {{LOCATION}} {{JOB_ID}} {{JOB_URL}} {{JOB_SLUG}}
{{BODY_HTML}}`. Stylesheets and scripts are stripped; JSON-LD is kept (the production
extractor reads it).

| Template | Source board | Notes |
|---|---|---|
| `greenhouse.html` | job-boards.greenhouse.io | Includes the full application form and EEO/demographic questions as chrome. Body: `<h2><strong>` headings, `<p>`, `<ul>`. |
| `lever.html` | jobs.lever.co | Server-rendered; body is a series of titled `div.section.page-centered` blocks with `<h3>` and `<ul><li>`. |
| `ashby.html` | jobs.ashbyhq.com | Captured from the JS-rendered DOM (raw HTML is an empty SPA shell). Body in `.ashby-job-posting-description`, usually `<h1>`/`<h2>` + `<p>`/`<ul>`. |
| `workday.html` | *.myworkdayjobs.com | Head metadata and JSON-LD as captured. The headless render never hydrated, so the body is hand-written from Workday's `data-automation-id` structure. |
| `amazon_careers.html` | amazon.jobs (big-tech company site) | Body often uses `<br/>` runs as pseudo-lists, with no `<ul>`: a deliberately messy real pattern. |
| `weworkremotely.html` | weworkremotely.com (aggregator) | Intro block plus description inside heavy site chrome. |
| `remoteok.html` | remoteok.com (aggregator) | Description inside an expanded table row; headings often run into text. |
| `startup_site.html` | hand-written | Generic small-company careers page (hero, cookie banner, article body, share box, other roles). Not captured from a live page. |

Known: the production extractor returns an empty string for the raw Workday shell, a real
failure mode that the hand-hydrated template does not exercise.
