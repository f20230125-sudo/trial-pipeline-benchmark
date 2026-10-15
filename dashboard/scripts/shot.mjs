// One screenshot of a part of the built page, for looking at it piece by piece.
//   node scripts/shot.mjs <out.png> [light|dark] [desktop|phone] [selector | top | full]
// "top" is the first screen (the viewport); a selector screenshots that element; "full" is the whole page.
import { chromium } from "@playwright/test";

const [out, scheme = "light", device = "desktop", target = "top"] = process.argv.slice(2);
const base = process.env.BASE_URL ?? "http://localhost:3060";
const viewport = device === "phone" ? { width: 390, height: 844 } : { width: 1440, height: 900 };
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport, colorScheme: scheme, reducedMotion: "reduce" });
const page = await ctx.newPage();
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(String(e)));
await page.goto(base, { waitUntil: "networkidle" });
await page.waitForTimeout(400);
if (target === "full") await page.screenshot({ path: out, fullPage: true });
else if (target === "top") await page.screenshot({ path: out });
else {
  const el = page.locator(target).first();
  await el.scrollIntoViewIfNeeded();
  await el.screenshot({ path: out });
}
if (errors.length) console.log("console errors:", errors);
await browser.close();
console.log("wrote", out);
