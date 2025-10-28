# Yacht Leads Scraper — Web App (Streamlit)
A one-file web UI to discover and crawl **yacht management** companies and export a CSV of **name, website, phone, email, location**.

## Run locally
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app_streamlit.py
```
Open the URL Streamlit prints (usually http://localhost:8501).

## Deploy to Streamlit Cloud (free/easy)
1. Push this folder to a public GitHub repo.
2. Go to streamlit.io → **Deploy an app** → point to your repo → select `app_streamlit.py`.
3. (Optional) Set environment variables for API keys in the Streamlit dashboard:
   - `SERPAPI_API_KEY` (not required; you can paste it in the UI instead)
   - `BING_API_KEY` (not required; you can paste it in the UI instead)

## Using the app
- Enter an **API key** (SerpAPI or Bing) to enable discovery. Without a key, add **Seed URLs** so the crawler has places to start.
- Add **keywords** and **regions** (pre-filled with yachting hotspots).
- Optionally add a **region filter** (regex) to limit results by address text.
- Click **Run Scraper**, preview results, and **Download CSV**.

## Notes
- The crawler respects `robots.txt`, limits to same-domain links, and scans a few obvious contact pages.
- Data quality varies by site. You’ll still want to eyeball the CSV and enrich where needed.
- For larger runs, keep **target <= 150** per session to be polite. Increase only if necessary.
