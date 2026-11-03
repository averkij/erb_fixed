"""Isolated local Chromium QA for the offline control report (Playwright required)."""
import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, default=Path("control_report/report.html"))
    p.add_argument("--output-dir", type=Path, default=Path("test-artifacts/report-visual"))
    args = p.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    result = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for label, width, height in [("desktop", 1440, 1000), ("mobile", 390, 900)]:
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()
            errors, external = [], []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("request", lambda r: external.append(r.url) if r.url.startswith(("http:", "https:")) else None)
            page.goto(args.report.resolve().as_uri())
            page.locator("h1").wait_for()
            assert page.locator("#repos tbody tr").count() == 50
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), label
            page.screenshot(path=str(args.output_dir / (label + ".png")))
            page.locator("#repo-filter").fill("Chronyk")
            assert page.locator("#repos tbody tr:visible").count() == 1
            assert "1 / 50" in page.locator("#shown").inner_text()
            page.locator("#repo-filter").fill("")
            assert page.locator("#repos tbody tr:visible").count() == 50
            page.locator("#repo-filter").focus()
            page.keyboard.press("End")
            assert page.locator("#repo-filter").evaluate("el=>getComputedStyle(el).outlineStyle") != "none"
            scroll = page.locator("#repos").evaluate("el=>({scroll:el.parentElement.scrollWidth,client:el.parentElement.clientWidth})")
            if label == "mobile":
                assert scroll["scroll"] > scroll["client"]
                page.locator("#repos").evaluate("el=>el.parentElement.scrollLeft=300")
                assert page.locator("#repos").evaluate("el=>el.parentElement.scrollLeft") > 0
            if page.locator("details").count():
                detail = page.locator("details").first
                detail.locator("summary").click()
                assert detail.get_attribute("open") is not None
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
                page.screenshot(path=str(args.output_dir / (label + "-diagnostic.png")))
                detail.locator("summary").click()
                assert detail.get_attribute("open") is None
            assert not errors, errors
            assert not external, external
            result.append(dict(viewport=label, width=width, overflow=False, filter=True, focus=True, errors=errors, external_requests=external))
            context.close()
        context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 900})
        page = context.new_page()
        page.goto(args.report.resolve().as_uri())
        assert page.locator("#repos tbody tr").count() == 50
        assert page.locator("#result h2").inner_text()
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        context.close()
        browser.close()
    (args.output_dir / "checks.json").write_text(json.dumps(dict(results=result, no_javascript=True), indent=2), encoding="utf-8")
    print("PASS: desktop/mobile, filter, focus, contained table scrolling, no-JS, no external requests/errors")


if __name__ == "__main__":
    main()
