// One screenshot per section, for looking at the page piece by piece.
//   node scripts/sections.mjs <outDir> [light|dark] [desktop|phone]
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const out = process.argv[2] ?? path.join(process.cwd(), "screenshots", "sections");
const scheme = process.argv[3] ?? "light";
const device = process.argv[4] ?? "desktop";
const base = process.env.BASE_URL ?? "http://localhost:3060";
const viewport = device === "phone" ? { width: 390, height: 844 } : { width: 1440, height: 900 };
fs.mkdirSync(out, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport, colorScheme: scheme, reducedMotion: "reduce" });
const page = await ctx.newPage();
await page.goto(base, { waitUntil: "networkidle" });
await page.waitForTimeout(500);
const targets = [["top", "header.mast"], ["ledger", "dl.ledger"], ...["market", "growth", "sellers", "generics", "protection", "states", "outlook", "quality"].map((id) => [id, `#${id}`]), ["footer", "footer.foot"]];
for (const [name, sel] of targets) {
  const el = page.locator(sel).first();
  await el.scrollIntoViewIfNeeded();
  await el.screenshot({ path: path.join(out, `${device}-${scheme}-${name}.png`) });
}
await browser.close();
console.log("wrote", targets.length, "section screenshots to", out);
