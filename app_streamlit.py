
import os, io
import pandas as pd
import streamlit as st
from lead_scraper_core import scrape_leads

st.set_page_config(page_title="Yacht Leads Scraper", page_icon="⛵", layout="wide")

st.title("⛵ Yacht Management Leads — Web Scraper")
st.caption("Find 75–100 yacht managers/management companies: name, website, phone, email, location.")

with st.expander("Search & Crawl Settings", expanded=True):
    colA, colB, colC = st.columns(3)
    with colA:
        serp = st.text_input("SerpAPI Key (optional)", type="password")
    with colB:
        bing = st.text_input("Bing Web Search API Key (optional)", type="password")
    with colC:
        target = st.number_input("Target leads", min_value=10, max_value=500, value=100, step=10)

    keywords = st.text_area("Keywords (one per line)", value="\n".join([
        "yacht management company",
        "yacht manager",
        "superyacht management",
        "vessel management services",
        "yacht operations management",
        "yacht crew management"
    ]))
    regions = st.text_area("Regions (one per line)", value="\n".join([
        "Fort Lauderdale",
        "Miami",
        "West Palm Beach",
        "Newport Rhode Island",
        "Seattle",
        "San Diego",
        "Los Angeles",
        "Monaco",
        "Antibes",
        "Nice",
        "Cannes",
        "Barcelona",
        "Palma de Mallorca",
        "Viareggio",
        "Genoa",
        "Dubai",
        "Abu Dhabi",
        "Doha",
        "Singapore",
        "Sydney",
        "Auckland"
    ]))

    seed_urls = st.text_area("Seed URLs (optional, one per line)", value="\n".join([
        "https://www.iyba.org/",
        "https://www.myba-association.com/",
        "https://www.superyachtservicesguide.com/"
    ]))

    colD, colE, colF = st.columns(3)
    with colD:
        timeout = st.slider("Per-request timeout (sec)", 5, 30, 12)
    with colE:
        max_pages = st.slider("Max pages per domain", 5, 30, 10)
    with colF:
        region_regex = st.text_input("Region filter (optional regex)", value="")

run = st.button("Run Scraper", type="primary")

progress = st.empty()
status = st.empty()
results_ph = st.empty()
download_ph = st.empty()

if run:
    kw_list = [k.strip() for k in keywords.splitlines() if k.strip()]
    reg_list = [r.strip() for r in regions.splitlines() if r.strip()]
    seed_list = [s.strip() for s in seed_urls.splitlines() if s.strip()]

    pbar = st.progress(0, text="Discovering and crawling…")
    last_total = 1

    def on_progress(done, total, last_lead):
        nonlocal last_total
        last_total = max(last_total, total or 1)
        p = min(1.0, done / last_total) if last_total else 0
        pbar.progress(int(p*100), text=f"Crawling {done}/{last_total} domains…")
        if last_lead:
            status.info(f"Last saved: {last_lead.get('website','')}")

    leads = scrape_leads(
        keywords=kw_list,
        regions=reg_list,
        seed_urls=seed_list,
        target=int(target),
        timeout=int(timeout),
        max_pages=int(max_pages),
        region_regex=region_regex or None,
        serp_key=serp or None,
        bing_key=bing or None,
        progress_cb=on_progress
    )
    pbar.progress(100, text="Done")

    if not leads:
        st.warning("No leads found. Try adding an API key, more regions, or seed URLs.")
    else:
        df = pd.DataFrame(leads, columns=["name","website","phone","email","location","source_page"])
        st.success(f"Found {len(df)} leads.")
        results_ph.dataframe(df, use_container_width=True)

        csv_bytes = df.to_csv(index=False).encode("utf-8")
        download_ph.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name="yacht_leads.csv",
            mime="text/csv"
        )

st.markdown("---")
st.caption("Respect robots.txt & site terms. Throttled, minimal crawling for contact details.")
