"""QA for the website in docs/: every sitemap page in headless Chrome at phone and desktop widths.

Checks: no horizontal scroll, no console errors, no broken internal links or images, valid JSON-LD, one <h1>, and that the
web app (explore/) loads its data, searches and opens a place.

Usage: .venv/bin/python scripts/qa-site.py      (serves docs/ itself on a free localhost port; exits 1 on any problem)
"""
import functools
import http.server
import json
import os
import sys
import threading
import urllib.parse
import xml.etree.ElementTree as ET

from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(__file__), "..")
DOCS = os.path.join(ROOT, "docs")
DOMAIN = open(os.path.join(DOCS, "CNAME")).read().strip()


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=DOCS))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}"


def local_exists(path):
    path = urllib.parse.unquote(path.split("#")[0].split("?")[0])
    f = os.path.join(DOCS, path.lstrip("/"))
    return os.path.isfile(f) or os.path.isfile(os.path.join(f, "index.html"))


def main():
    base = serve()
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [e.text for e in ET.parse(os.path.join(DOCS, "sitemap.xml")).getroot().findall("s:url/s:loc", ns)]
    pages = [base + urllib.parse.urlparse(u).path for u in urls]
    problems = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        for width in (375, 1280):
            ctx = browser.new_context(viewport={"width": width, "height": 900})
            page = ctx.new_page()
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            for url in pages:
                errors.clear()
                page.goto(url, wait_until="networkidle")
                where = f"{urllib.parse.urlparse(url).path} @{width}"
                over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                if over > 1:
                    problems.append(f"{where}: scrolls sideways by {over}px")
                if page.locator("h1").count() != 1:
                    problems.append(f"{where}: {page.locator('h1').count()} <h1>")
                for raw in page.locator('script[type="application/ld+json"]').all_text_contents():
                    try:
                        json.loads(raw)
                    except ValueError as e:
                        problems.append(f"{where}: bad JSON-LD ({e})")
                if width == 1280:   # links are the same at both widths
                    refs = page.evaluate("""[...document.querySelectorAll('a[href],img[src],link[href],script[src]')]
                        .map(e => e.getAttribute('href') || e.getAttribute('src'))""")
                    for ref in refs:
                        full = urllib.parse.urljoin(url, ref)
                        p = urllib.parse.urlparse(full)
                        if p.scheme in ("mailto", "tel", "data"):
                            continue
                        if p.netloc in (urllib.parse.urlparse(base).netloc, DOMAIN) and not local_exists(p.path):
                            problems.append(f"{where}: broken link {ref}")
                    imgs = page.evaluate("[...document.images].filter(i => i.complete && i.naturalWidth === 0).map(i => i.src)")
                    problems += [f"{where}: image didn't load {s}" for s in imgs]
                problems += [f"{where}: console error: {e}" for e in errors]
            # the web app: data loads, a search finds places, a place opens
            errors.clear()
            page.goto(base + "/explore/", wait_until="networkidle")
            page.wait_for_function("document.querySelectorAll('.ex-row').length > 0", timeout=15000)
            search = page.locator('#ex-q').first
            search.fill("perch green bay")
            page.wait_for_timeout(400)
            hits = page.locator(".ex-row").count()
            if not hits:
                problems.append(f"explore @{width}: search 'perch green bay' found nothing")
            else:
                page.locator(".ex-row").first.click()
                page.wait_for_timeout(600)
                panel = page.locator("#ex-panel")
                if not panel.is_visible() or not panel.locator("a", has_text="Directions").count():
                    problems.append(f"explore @{width}: opening a place showed no details")
                else:
                    page.locator("#ex-close").click()
            search.fill("🍕")
            page.wait_for_timeout(400)
            if page.locator(".ex-row").count():
                problems.append(f"explore @{width}: an emoji search listed places")
            problems += [f"explore @{width}: console error: {e}" for e in errors]
            ctx.close()
        browser.close()
    print(f"{len(pages)} pages × 2 widths + the web app")
    for p in problems:
        print("  ✗", p)
    print("OK" if not problems else f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
