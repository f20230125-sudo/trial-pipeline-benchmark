// Lists the elements that stick out past the right edge of the viewport (used when a page scrolls sideways).
//   node scripts/overflow.mjs [width] [tables]     "tables" switches every figure to its table view first
import { chromium } from "@playwright/test";

const width = Number(process.argv[2] ?? 390);
const withTables = process.argv[3] === "tables";
const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width, height: 844 } })).newPage();
await page.goto(process.env.BASE_URL ?? "http://localhost:3060", { waitUntil: "networkidle" });
if (withTables) for (const b of await page.getByRole("button", { name: "Table" }).all()) await b.click();
const rows = await page.evaluate(() => {
  const out = [];
  for (const el of document.querySelectorAll("body *")) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.right > window.innerWidth + 1 && !el.closest(".tbl-wrap")) {
      out.push([el.tagName.toLowerCase() + (el.className && typeof el.className === "string" ? "." + el.className.split(" ").join(".") : ""), Math.round(r.right), Math.round(r.width), (el.textContent || "").trim().slice(0, 40)]);
    }
  }
  return out.slice(0, 25);
});
console.log("viewport", width, "scrollWidth", await page.evaluate(() => document.documentElement.scrollWidth));
for (const r of rows) console.log(r.join("  |  "));
await browser.close();
