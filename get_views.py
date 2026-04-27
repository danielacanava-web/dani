#!/usr/bin/env python3
"""
Twitter/X View Count Scraper
Setup: pip install playwright && playwright install chromium

How to get your auth_token:
  1. Open x.com in Chrome (logged in)
  2. DevTools (F12) → Application → Cookies → https://x.com
  3. Copy the value of 'auth_token'
"""
import asyncio
import re
from playwright.async_api import async_playwright

# ── PASTE YOUR auth_token VALUE HERE ─────────────────────────────────────────
AUTH_TOKEN = "PASTE_HERE"
# ─────────────────────────────────────────────────────────────────────────────

URLS = [
    "https://x.com/cgtwts/status/2045212979294249322",
    "https://x.com/svpino/status/2045195162343600585",
    "https://x.com/shiri_shh/status/2045225784793813284",
    "https://x.com/ecommartinez/status/2045175779068424388",
    "https://x.com/the_p_god/status/2045248877595398481",
    "https://x.com/hewarsaber/status/2045158289567080464",
    "https://x.com/ecomchasedimond/status/2045157493039632654",
    "https://x.com/drewvento/status/2045235352382648327",
    "https://x.com/kritarthmittal/status/2045254256186568991",
    "https://x.com/BacardiCapital/status/2045243295190675474",
    "https://x.com/brkguzel/status/2045544533388124515",
    "https://x.com/_guillecasaus/status/2045159713281646947",
    "https://x.com/arceyul/status/2045236052147748963",
    "https://x.com/shashpicious_/status/2045160434207252568",
    "https://x.com/i/status/2045160459607675231",
    "https://x.com/coleHardik/status/2045157954182340810",
    "https://x.com/BenjaminUIX/status/2045158312044593201",
    "https://x.com/chizorommaduba/status/2045209732156194855",
    "https://x.com/i/status/2045167501550727438",
    "https://x.com/hasantoxr/status/2045586668153922044",
    "https://x.com/MatiasSchrank/status/2045355919693709377",
    "https://x.com/HeyToha/status/2045161129979326715",
    "https://x.com/TechByMarkandey/status/2045159365443981688",
    "https://x.com/socialwithaayan/status/2045322839641993448",
    "https://x.com/thetripathi58/status/2045163802107502603",
    "https://x.com/i/status/2045222061707329786",
    "https://x.com/vermaaakash3/status/2045221297714803144",
    "https://x.com/alex_inspira/status/2045160190702408140",
    "https://x.com/viipin8/status/2045158265080906227",
    "https://x.com/ginacostag_/status/2045254379758911774",
    "https://x.com/TextoCriativo/status/2045169527156064652",
    "https://x.com/HeyNayeem/status/2045526758959849963",
    "https://x.com/IA_Quijote/status/2045772431994827045",
    "https://x.com/Krishnasagrawal/status/2045159887307735184",
    "https://x.com/Rana_kamran43/status/2045161909591445733",
    "https://x.com/aiwithghotai/status/2045164634420715975",
    "https://x.com/Marco_Exito/status/2045164826251444553",
    "https://x.com/TheoBuildsAI/status/2045157694181392687",
    "https://x.com/NovaIAHQ/status/2045158193043567055",
    "https://x.com/Parul_Gautam7/status/2045158910634709462",
    "https://x.com/Lupin_Ai_Coder/status/2045162749257523560",
    "https://x.com/future_coded/status/2045163852304912843",
    "https://x.com/heysajib/status/2045160303181398030",
    "https://x.com/hey_abusiddik/status/2045164432423280936",
    "https://x.com/EnzoSanchezIA/status/2045157879666114710",
    "https://x.com/techwithakansha/status/2045184030283329969",
    "https://x.com/HeyAmit_/status/2045158925386015137",
    "https://x.com/tec_aryan/status/2045178855569408337",
    "https://x.com/manishkumar_dev/status/2045164263778771131",
    "https://x.com/iam_chonchol/status/2045160210357231828",
    "https://x.com/hey_mujeebahmed/status/2045165092464119822",
    "https://x.com/Ronycoder/status/2045158511274008877",
    "https://x.com/saidul_dev/status/2045161792532558063",
    "https://x.com/Polanco_IA/status/2045162013467283775",
    "https://x.com/Kawsar_Ai/status/2045171908216590379",
    "https://x.com/i/status/2045158505678782490",
    "https://x.com/Shruti_0810/status/2045171858841178534",
    "https://x.com/aaliya_va/status/2045409040667189579",
    "https://x.com/i/status/2045354351762551271",
    "https://x.com/GrowAIHub/status/2045400523684347983",
    "https://x.com/copyelpadrino/status/2045588758049796140",
    "https://x.com/azed_ai/status/2045159720210813113",
    "https://x.com/s_mohinii/status/2045177078895800631",
    "https://x.com/Code_SantrexAI/status/2045171300382265389",
    "https://x.com/archygupta22/status/2045185572906623192",
    "https://x.com/anjum_ai/status/2045165190283694222",
    "https://x.com/BharukaShraddha/status/2045162258624635154",
    "https://x.com/pushkersoni72/status/2045162401109324280",
    "https://x.com/jihad_sameul/status/2045159181192487309",
    "https://x.com/KhusbooT14835/status/2045162676675133924",
    "https://x.com/tech_crafters/status/2045174369400635613",
    "https://x.com/aiscout22/status/2045391951885914326",
    "https://x.com/i/status/2045194036546302021",
    "https://x.com/Nijol71/status/2045158998291398899",
    "https://x.com/Rixhabh__/status/2045158121543533032",
    "https://x.com/iamfakhrealam/status/2045158323520237835",
    "https://x.com/Diptish09/status/2045158369703694381",
    "https://x.com/soni_jyoti_/status/2045158198521594078",
    "https://x.com/ai_explorer25/status/2045158964892201149",
]


def parse_views(text):
    text = text.strip().replace(",", "")
    m = re.match(r"^([\d.]+)([KMB]?)$", text.upper())
    if not m:
        return "N/A"
    num = float(m.group(1))
    mult = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "": 1}[m.group(2)]
    return int(num * mult)


JS_EXTRACT = """
() => {
    // Strategy 1: analytics link text (e.g. "137.3K Views")
    const links = document.querySelectorAll('a[href*="/analytics"]');
    for (const link of links) {
        const txt = (link.innerText || link.textContent || "").trim();
        const m = txt.match(/([\\d,\\.]+[KMB]?)\\s*Views/i);
        if (m) return m[1].replace(/,/g, "");
    }
    // Strategy 2: find "Views" span and grab the preceding number span
    const spans = [...document.querySelectorAll('span')];
    for (let i = 1; i < spans.length; i++) {
        if (/^views$/i.test(spans[i].textContent.trim())) {
            const prev = spans[i - 1].textContent.trim().replace(/,/g, "");
            if (/^[\\d\\.]+[KMB]?$/i.test(prev)) return prev;
        }
    }
    return null;
}
"""


async def fetch_views(sem, context, url, idx, total):
    async with sem:
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector("article", timeout=15000)
            await page.wait_for_timeout(2500)
            raw = await page.evaluate(JS_EXTRACT)
            result = parse_views(raw) if raw else "N/A"
        except Exception:
            result = "N/A"
        finally:
            await page.close()
        print(f"  [{idx}/{total}] {url.split('/')[-1]} → {result}", flush=True)
        return result


async def main():
    if AUTH_TOKEN == "PASTE_HERE":
        print("ERROR: Set AUTH_TOKEN at the top of the script first.")
        return

    total = len(URLS)
    sem = asyncio.Semaphore(4)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        await context.add_cookies([
            {"name": "auth_token", "value": AUTH_TOKEN, "domain": ".x.com", "path": "/"}
        ])

        print(f"Fetching {total} tweets (4 at a time)...\n")
        tasks = [fetch_views(sem, context, url, i + 1, total) for i, url in enumerate(URLS)]
        results = await asyncio.gather(*tasks)
        await browser.close()

    print("\n" + "=" * 40)
    print("PASTE INTO AIRTABLE:")
    print("=" * 40)
    for r in results:
        print(r)


asyncio.run(main())
