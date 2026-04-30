# Concordance Engine — site

Static HTML for the Concordance Engine landing site. Hand-written HTML + CSS, no build step, no JavaScript framework, no npm dependencies.

## Preview locally

Just open `index.html` in a browser. That's it. Or run a tiny local server if you want clean URLs:

```bash
cd site/
python -m http.server 8000
# open http://localhost:8000
```

## Deploy to Cloudflare Pages

This is the recommended path. Free, fast, automatic HTTPS, deploys on every push.

### One-time setup

1. **Buy a domain.** Cloudflare Registrar is the cheapest because they don't mark up — and it pairs naturally with Pages. ~$10-15/yr. Suggested names: `concordance.dev`, `concordancengine.com`, `lighthouseengine.com`.

2. **Decide repo structure.** Two options:
   - **Co-located (default):** keep this `site/` directory inside the main `Lighthouse` repo. Simplest. The downside is `git clone Lighthouse` pulls the site too.
   - **Separate repo:** create a new `lighthouse-site` repo on GitHub, copy this directory into its root, and connect Cloudflare Pages to it. Cleaner separation between code and marketing.

3. **Connect Cloudflare Pages.**
   - Log into the Cloudflare dashboard → Workers & Pages → Create → Pages → Connect to Git.
   - Authorize GitHub, pick the repo (Lighthouse or lighthouse-site).
   - **Build settings:**
     - Framework preset: `None`
     - Build command: *(leave blank)*
     - Build output directory: `site` (if using the co-located layout) or `/` (if using a separate repo)
   - Click "Save and Deploy."
   - Cloudflare gives you a `*.pages.dev` URL within ~30 seconds.

4. **Connect your custom domain.**
   - In the Pages project → Custom domains → Set up a custom domain.
   - Enter `concordance.dev` (or whatever).
   - If the domain is registered with Cloudflare, the DNS is auto-configured. If it's elsewhere, follow Cloudflare's instructions to add a CNAME.
   - HTTPS is provisioned automatically within a couple of minutes.

5. **Done.** Future pushes to the connected branch redeploy automatically. No build, no CI, no maintenance.

## Deploy to GitHub Pages (alternative)

If you'd rather stay in the GitHub ecosystem:

1. In the Lighthouse repo settings → Pages.
2. Source: Deploy from a branch.
3. Branch: `main`, folder: `/site`.
4. Save. URL is `https://matharrismma.github.io/Lighthouse/`.
5. Custom domain field if you want `concordance.dev` instead.

GitHub Pages doesn't honor `_headers` or `_redirects` (those are Cloudflare-specific). The site still works — you just won't get the cache hints or the `/repo` shortlinks.

## Files

```
site/
├── index.html             Hero + product framing
├── how-it-works.html      Four Gates explainer
├── verifiers.html         Verifier reference (the 14 tools)
├── install.html           Setup guide
├── benchmark.html         Head-to-head benchmark page (numbers TBD)
├── theory.html            O(1) vs O(n²) formalization
├── use-cases/
│   ├── science.html       For researchers
│   ├── governance.html    For boards / councils
│   └── faith.html         For elders / households / churches
├── styles.css             All custom styles. ~250 lines.
├── _headers               Cloudflare cache + security headers
├── _redirects             /repo, /code, /docs shortlinks
├── robots.txt             Search engine directives
└── sitemap.xml            URL list for crawlers
```

## Editing

Each page is a single self-contained HTML file. The header and footer are inlined (no shared template), so a change to the nav touches every file. That's the trade-off for "no build step" — readable. Use find-and-replace.

When you add a new page:
1. Copy an existing one as a starting template.
2. Update the nav links at the top if it should appear in the main menu.
3. Add the URL to `sitemap.xml`.
4. Update the footer links on every page (~9 files) — find/replace works.

## What's deliberately not here

- **No JavaScript framework.** Plain HTML loads instantly, ranks well in search, and degrades gracefully. Add JS only when interactive content actually needs it.
- **No analytics.** Cloudflare Web Analytics is free, privacy-respecting, and one toggle in the Pages dashboard. Add when you want it.
- **No live demo widget.** The "see Claude use the engine" experience requires either a video (you record once) or an in-browser Pyodide build of the verifier (substantial work). Both are reasonable v2 projects; not in v1.
- **No newsletter signup, no chatbot, no popups.** Aggressively avoided. The page should respect the reader's time.

## v2 wishlist

When you're ready to invest more in the site, in priority order:

1. **Demo video / animated GIF** showing Claude Desktop catching a wrong p-value via the engine. Embed on the homepage.
2. **Benchmark numbers** filled in once the head-to-head runs.
3. **Logo / wordmark.** The current "brand-mark" is a CSS square. A real logo (even a simple wordmark) lifts perceived quality.
4. **Open Graph image.** Right now `og:image` is unset. A 1200×630 social card image makes Twitter/LinkedIn previews look intentional.
5. **Case studies.** When real organizations adopt the engine, write them up. One paragraph per case is enough.
6. **In-browser interactive demo.** Use Pyodide to ship the chemistry verifier client-side. Visitors paste an equation, see the engine balance it, no API key needed.

## License

Same as the engine: MIT. Reuse the HTML/CSS for related projects freely.
