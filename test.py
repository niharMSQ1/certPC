import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

RAW_JSON_PATH = "raw_cert_links.json"
OUTPUT_DIR = Path("sections_output")
OUTPUT_DIR.mkdir(exist_ok=True)

def load_existing_jsons():
    existing_data = []
    for json_file in OUTPUT_DIR.glob("sections_*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing_data.append(data)
        except Exception as e:
            print(f"⚠️ Failed to read {json_file}: {e}")
    return existing_data

async def get_cert_links(page):
    await page.goto("https://trust.trustcloud.ai/certifications")
    await page.wait_for_selector('a[href^="/certifications/"]')
    cert_links = await page.eval_on_selector_all(
        'a[href^="/certifications/"]',
        'elements => elements.map(el => el.href)'
    )
    cert_links = list(set(cert_links))
    raw_data = [{"title": "TrustShare", "url": link, "items": []} for link in cert_links]
    with open(RAW_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, indent=2)
    print(f"✅ Found and saved {len(cert_links)} certification links.")
    return raw_data

async def capture_sections_for_all_links():
    existing_jsons = load_existing_jsons()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        links = await get_cert_links(page)

        for idx, entry in enumerate(links, 1):
            url = entry["url"]
            print(f"\n🔗 ({idx}/{len(links)}) Visiting: {url}")
            sub_page = await context.new_page()
            found = False

            async def handle_response(response):
                nonlocal found
                try:
                    if "sections" in response.url:
                        found = True
                        print(f"✅ Found 'sections' API: {response.url}")
                        json_data = await response.json()
                        if json_data in existing_jsons:
                            print("⛔ Duplicate data found. Skipping save.")
                            return
                        output_path = OUTPUT_DIR / f"sections_{idx:02d}.json"
                        with open(output_path, "w", encoding="utf-8") as f:
                            json.dump(json_data, f, ensure_ascii=False, indent=2)
                        print(f"📁 Saved JSON to {output_path}")
                        existing_jsons.append(json_data)
                except Exception as e:
                    print(f"⚠️ Error processing response: {e}")

            sub_page.on("response", handle_response)

            try:
                await sub_page.goto(url, timeout=30000)
                await sub_page.wait_for_timeout(8000)
            except Exception as e:
                print(f"⚠️ Failed to load {url}: {e}")
            finally:
                if not found:
                    print("❌ No 'sections' API found for this URL.")
                await sub_page.close()

        await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_sections_for_all_links())
