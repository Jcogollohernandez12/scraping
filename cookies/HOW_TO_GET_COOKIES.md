# How to Get Your LinkedIn Cookies

LinkedIn requires authentication to access search results.
You need the `li_at` cookie from your logged-in browser session.

## Option 1 — Environment variable (fastest)

1. Open Chrome/Firefox and log in to LinkedIn
2. Open DevTools → Application tab → Cookies → `https://www.linkedin.com`
3. Find the cookie named `li_at` and copy its value
4. Add to your `.env` file:
   ```
   LINKEDIN_LI_AT=AQEDAxxxxxxxxxxxxxxxxxxxxxxx
   ```

## Option 2 — Export full cookies file (recommended)

Install the "Cookie Editor" browser extension:
- Chrome: https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm
- Firefox: https://addons.mozilla.org/en-US/firefox/addon/cookie-editor/

Steps:
1. Log in to LinkedIn in your browser
2. Click the Cookie Editor extension icon
3. Click "Export" → "Export as JSON"
4. Save the file as `cookies/linkedin.json` in this project

The scraper will automatically load these cookies.

## Option 3 — Proxycurl (no cookies needed)

Use `python main.py linkedin-proxycurl` commands instead.
These use the Proxycurl API which handles authentication for you.
Requires a Proxycurl API key (set `PROXYCURL_API_KEY` in `.env`).

## Important Notes

- Your `li_at` cookie is valid for ~1 year
- Never commit `linkedin.json` to git (it's in `.gitignore`)
- Using someone else's account violates LinkedIn ToS
- Each account can safely do ~100-200 profile views/day
- For large-scale data, use Proxycurl (Option 3)

## Verify your cookies work

```bash
python main.py linkedin-companies "digital health" --no-headless
```

If the browser opens and shows LinkedIn logged in, your cookies are working.
