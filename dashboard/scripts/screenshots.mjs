// Full-page screenshots of the built site in light and dark, desktop and phone width.
//   npm run build && npm run start   (in another terminal)   then   node scripts/screenshots.mjs [outDir]
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const out = process.argv[2] ?? path.join(process.cwd(), "screenshots");
const base = process.env.BASE_URL ?? "http://localhost:3060";
fs.mkdirSync(out, { recursive: true });

const browser = await chromium.launch();
for (const [name, viewport] of [["desktop", { width: 1440, height: 900 }], ["phone", { width: 390, height: 844 }]]) {
  for (const scheme of ["light", "dark"]) {
    const ctx = await browser.newContext({ viewport, colorScheme: scheme, reducedMotion: "reduce" });
    const page = await ctx.newPage();
    const errors = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto(base, { waitUntil: "networkidle" });
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(out, `${name}-${scheme}.png`), fullPage: true });
    if (errors.length) console.log(`${name}-${scheme}: console errors`, errors);
    await ctx.close();
  }
}
await browser.close();
console.log("wrote screenshots to", out);
