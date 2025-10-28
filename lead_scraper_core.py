
import os, re, time, random, logging
import urllib.parse as urlparse
from urllib.parse import urljoin
from urllib import robotparser
import requests
from bs4 import BeautifulSoup
import tldextract

UA = "Mozilla/5.0 (compatible; YachtLeadsBot/1.0; +https://example.com/bot)"
EMAIL_REGEX = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_REGEX = re.compile(r"(\+?\d[\d\-\s().]{6,}\d)")
ADDRESS_HINTS = ["address", "location", "head office", "headquarters", "hq"]
DEFAULT_CONTACT_PATHS = ["/contact", "/contact-us", "/about", "/about-us", "/en/contact", "/en/about"]

def allowed_by_robots(root_url, path):
    try:
        rp = robotparser.RobotFileParser()
        robots_url = urljoin(root_url, "/robots.txt")
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(UA, urljoin(root_url, path))
    except Exception:
        return True

def polite_get(session, url, timeout=12, max_retries=2):
    for attempt in range(max_retries+1):
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True)
            if 200 <= r.status_code < 300:
                return r
            elif r.status_code in (403, 429):
                time.sleep(2 * (attempt+1))
            else:
                time.sleep(0.6)
        except requests.RequestException:
            time.sleep(0.6 + attempt)
    return None

def norm_domain(url):
    parts = tldextract.extract(url)
    if not parts.domain:
        return None
    return f"{parts.domain}.{parts.suffix}" if parts.suffix else parts.domain

def clean_text(s):
    import re as _re
    return _re.sub(r"\s+", " ", s or "").strip()

def guess_company_name(soup, domain):
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    if title:
        import re as _re
        title = _re.sub(r"\|.*$| - .*|—.*|–.*", "", title).strip()
    meta = soup.find("meta", attrs={"property": "og:site_name"})
    site = meta["content"].strip() if meta and meta.get("content") else ""
    fallback = domain.split(".")[0].replace("-", " ").title() if domain else ""
    for cand in [title, site, fallback]:
        if cand and len(cand) >= 2:
            return cand
    return fallback or domain

def extract_contacts(html):
    emails = set(m.group(0).lower() for m in EMAIL_REGEX.finditer(html))
    phones = set(clean_text(m.group(0)) for m in PHONE_REGEX.finditer(html))

    locations = set()
    lowered = html.lower()
    for hint in ADDRESS_HINTS:
        idx = lowered.find(hint)
        if idx != -1:
            snippet = clean_text(html[max(0, idx-120): idx+240])
            if 10 <= len(snippet) <= 400:
                locations.add(snippet)
    return emails, phones, locations

def find_contact_pages(root):
    pages = []
    for path in DEFAULT_CONTACT_PATHS:
        full = urljoin(root, path)
        pages.append(full)
    return pages

def iter_links(soup, base, limit=20):
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("#"):
            continue
        u = urljoin(base, href)
        if norm_domain(u) != norm_domain(base):
            continue
        if u not in seen:
            seen.add(u)
            yield u
        if len(seen) >= limit:
            break

def discover_with_search(keywords, regions, max_results=120, serp_key=None, bing_key=None):
    results = set()
    if not serp_key and not bing_key:
        return results
    queries = []
    for kw in keywords or []:
        for r in regions or []:
            queries.append(f"{kw} {r}")
        queries.append(kw)
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    for q in queries:
        if serp_key:
            try:
                params = {"engine": "google", "q": q, "api_key": serp_key, "num": "10"}
                r = session.get("https://serpapi.com/search", params=params, timeout=15)
                if r.ok:
                    data = r.json()
                    for item in (data.get("organic_results") or []):
                        link = item.get("link")
                        if link and norm_domain(link):
                            results.add(link)
                time.sleep(0.8)
            except Exception:
                pass
        elif bing_key:
            try:
                headers = {"Ocp-Apim-Subscription-Key": bing_key}
                params = {"q": q, "count": 10, "mkt": "en-US"}
                r = session.get("https://api.bing.microsoft.com/v7.0/search", headers=headers, params=params, timeout=15)
                if r.ok:
                    data = r.json()
                    for item in (data.get("webPages", {}).get("value", []) or []):
                        link = item.get("url")
                        if link and norm_domain(link):
                            results.add(link)
                time.sleep(0.8)
            except Exception:
                pass
        if len(results) >= max_results:
            break
    return results

def crawl_domain(session, start_url, max_pages=10, timeout=12):
    root = "{uri.scheme}://{uri.netloc}/".format(uri=urlparse.urlparse(start_url))
    seen = set()
    queue = [start_url] + find_contact_pages(root)
    contacts = {"emails": set(), "phones": set(), "locations": set(), "pages": set()}
    company_name = None

    while queue and len(seen) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)

        path = urlparse.urlparse(url).path or "/"
        if not allowed_by_robots(root, path):
            continue

        r = polite_get(session, url, timeout=timeout)
        if not r:
            continue

        html = r.text
        soup = BeautifulSoup(html, "html.parser")

        if not company_name:
            company_name = guess_company_name(soup, norm_domain(root))

        emails, phones, locs = extract_contacts(html)
        if emails or phones or locs:
            contacts["emails"].update(emails)
            contacts["phones"].update(phones)
            contacts["locations"].update(locs)
            contacts["pages"].add(url)

        if len(contacts["emails"]) < 2 and len(seen) < max_pages:
            for u in iter_links(soup, url, limit=10):
                if u not in seen and len(queue) < max_pages:
                    queue.append(u)

        time.sleep(0.3 + random.random()*0.5)

    domain = norm_domain(root)
    if domain and not contacts["emails"]:
        for local in ("info", "contact", "hello", "sales", "office"):
            contacts["emails"].add(f"{local}@{domain}")

    def normalize_phone(p):
        import re as _re
        return _re.sub(r"[^\d+]", "", p)

    phones_sorted = sorted(contacts["phones"], key=lambda p: len(normalize_phone(p)))
    emails_sorted = sorted(contacts["emails"])
    loc_txt = next(iter(contacts["locations"])) if contacts["locations"] else ""

    return {
        "name": company_name or (domain.split(".")[0].title() if domain else ""),
        "website": root.rstrip("/"),
        "phone": phones_sorted[0] if phones_sorted else "",
        "email": emails_sorted[0] if emails_sorted else "",
        "location": clean_text(loc_txt),
        "source_page": next(iter(contacts["pages"])) if contacts["pages"] else start_url,
    }

def scrape_leads(keywords, regions, seed_urls=None, target=100, timeout=12, max_pages=10, region_regex=None, serp_key=None, bing_key=None, progress_cb=None):
    seed_urls = seed_urls or []
    discovered = set()

    found = discover_with_search(keywords, regions, max_results=200, serp_key=serp_key, bing_key=bing_key)
    discovered.update(found)
    for u in seed_urls:
        discovered.add(u)

    roots = set()
    for u in discovered:
        try:
            parsed = urlparse.urlparse(u)
            root = f"{parsed.scheme}://{parsed.netloc}/"
            if norm_domain(root):
                roots.add(root)
        except Exception:
            continue

    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    seen_domains = set()
    leads = []
    written = 0
    total = len(roots)

    for i, root in enumerate(sorted(roots)):
        if written >= target:
            break
        d = norm_domain(root)
        if not d or d in seen_domains:
            if progress_cb: progress_cb(i+1, total, None)
            continue
        try:
            lead = crawl_domain(session, root, max_pages=max_pages, timeout=timeout)
            if region_regex:
                try:
                    import re as _re
                    if not _re.search(region_regex, lead.get("location",""), _re.I):
                        if progress_cb: progress_cb(i+1, total, None)
                        continue
                except re.error:
                    pass
            if lead.get("name") and lead.get("website"):
                leads.append(lead)
                seen_domains.add(d)
                written += 1
        except Exception as e:
            # ignore domain errors to keep flow
            pass
        if progress_cb: progress_cb(i+1, total, lead if 'lead' in locals() else None)
        time.sleep(0.6 + random.random()*0.6)
    return leads
