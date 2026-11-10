# Dhago showcase site

A one-page, static walkthrough of the pipeline: pick one of four invented applicants and follow the application through Income, Rules, Risk and Recommendation, then tamper with the hash-chained audit log and watch the browser catch it.

- No build step and no third-party requests: plain HTML, CSS and JavaScript, with the fonts (Anek, SIL Open Font License) served from `fonts/`.
- Every number comes from the real pipeline. `examples.json` is written by `python scripts/make_showcase_examples.py`, which builds a tiny dataset of invented applicants in the Track A file layout (no Track A records), runs the LangGraph pipeline on each and keeps the raw audit lines. The page re-checks those SHA-256 hashes with the Web Crypto API.

## Run it locally

```bash
cd showcase
python -m http.server 8000      # then open http://localhost:8000
```

Opening `index.html` straight from disk does not work, because browsers block `fetch()` of local files.

## Deploy on Vercel

1. Push the repository to GitHub.
2. On vercel.com choose **Add New → Project** and import the repository.
3. Set **Root Directory** to `showcase` and **Framework Preset** to **Other**. Leave the build and output settings empty.
4. Deploy. Every push to the main branch redeploys the site.

`vercel.json` adds a strict content security policy and long caching for the fonts.

## Update the examples

Change the invented applicants in `scripts/make_showcase_examples.py`, or change the policy or model, then rerun the script from the repository root:

```bash
python scripts/make_showcase_examples.py
```
