"""Capture real screenshots of the running app (python -m streamlit run app.py --server.port 8503).

Needs: pip install playwright && python -m playwright install chromium
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "assets"
URL = "http://localhost:8503"


def settle(page, ms=1800):
    page.wait_for_timeout(500)
    try:
        page.wait_for_selector("[data-testid='stStatusWidget']", state="detached", timeout=20000)
    except Exception:
        pass
    page.wait_for_timeout(ms)


def nav(page, label):
    page.get_by_text(label, exact=True).first.click()
    settle(page)


with sync_playwright() as pw:
    b = pw.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.goto(URL)
    settle(page, 3500)
    page.screenshot(path=str(OUT / "01_kalkulator.png"))
    nav(page, "📋 Dokumen Pinjaman")
    page.screenshot(path=str(OUT / "02_dokumen.png"))
    nav(page, "💬 Pembantu Pertanyaan")
    page.locator("[data-testid='stSelectbox']").nth(1).click()
    page.get_by_role("option").nth(1).click()
    settle(page, 2500)
    page.mouse.wheel(0, 250)
    settle(page, 600)
    page.screenshot(path=str(OUT / "03_pertanyaan.png"))
    nav(page, "📊 Papan Pemuka Prospek")
    page.screenshot(path=str(OUT / "04_papan_pemuka.png"))
    for label in ["ℹ️ Tentang Projek Ini"]:
        nav(page, label)
    errors = page.locator("[data-testid='stException']").count()
    print("exceptions on last page:", errors)
    b.close()
print("saved to", OUT)
