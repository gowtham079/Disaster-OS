"""Generate PNG diagram images from Mermaid source files (requires: pip install playwright && playwright install chromium)."""

import asyncio
import sys
from pathlib import Path

DIAGRAMS = Path(__file__).parent
HTML = DIAGRAMS / "PROJECT_DIAGRAMS.html"
OUT = DIAGRAMS / "images"
OUT.mkdir(exist_ok=True)


async def main() -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Install: pip install playwright && playwright install chromium")
        print(f"Or open in browser: {HTML}")
        sys.exit(1)

    names = [
        "01_er_diagram",
        "02_system_architecture",
        "03_use_case_operator",
        "04_use_case_admin",
        "05_sequence_diagram",
        "07_ml_pipeline",
        "08_message_bus_communication",
        "06_data_flow_diagram",
        "10_overall_workflow",
        "11_activity_diagram",
        "12_dfd_level1",
        "13_database_interaction",
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        await page.goto(HTML.resolve().as_uri())
        await page.wait_for_timeout(3000)

        slides = await page.query_selector_all(".slide")
        for i, slide in enumerate(slides):
            if i < len(names):
                await slide.screenshot(path=str(OUT / f"{names[i]}.png"))
                print(f"Saved: {OUT / names[i]}.png")

        await browser.close()

    print("Done. Images in docs/diagrams/images/")


if __name__ == "__main__":
    asyncio.run(main())
