import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SECTIONS = ["overview", "pipeline", "concentration", "revenue", "readouts", "starts", "gulf", "method"];
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const ladder = (page: Page) => page.locator("#overview .ladder");
const running = (page: Page) => page.evaluate(() => document.getAnimations().filter((a) => a.playState === "running").length);
const violations = async (page: Page) =>
  (await new AxeBuilder({ page }).withTags(TAGS).analyze()).violations.map(
    (v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`,
  );

test.describe("the report", () => {
  test("loads with its title, one h1 and the eight sections", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto("/");
    await expect(page).toHaveTitle(/Trial Pipeline Benchmark/);
    await expect(page.locator("h1")).toHaveCount(1);
    for (const id of SECTIONS) await expect(page.locator(`#${id}`)).toHaveCount(1);
    await expect(page.locator("main")).toHaveCount(1);
    await expect(page.getByRole("navigation", { name: "Sections" })).toBeVisible();
    expect(errors).toEqual([]);
  });

  test("the first screen draws 238 marks in five phase columns, 71 of them berry", async ({ page }) => {
    await page.goto("/");
    await expect(ladder(page).locator("a")).toHaveCount(238);
    await expect(ladder(page).locator(".mk.b")).toHaveCount(71);
    expect(await ladder(page).locator(".col-n").allTextContents()).toEqual(["37", "37", "58", "7", "99"]);
  });

  test("each mark opens its registry record, safely", async ({ page }) => {
    await page.goto("/");
    const first = ladder(page).locator("a").first();
    await expect(first).toHaveAttribute("href", /^https:\/\/clinicaltrials\.gov\/study\/NCT\d{8}$/);
    await expect(first).toHaveAttribute("rel", "noopener noreferrer");
    await expect(first).toHaveAttribute("target", "_blank");
  });

  test("the ladder is one tab stop and the arrow keys move between studies", async ({ page }) => {
    await page.goto("/");
    await expect(ladder(page).locator('a[tabindex="0"]')).toHaveCount(1);
    await ladder(page).locator('a[data-order="0"]').focus();
    await expect(page.locator("#overview .detail")).toContainText("NCT");
    await page.keyboard.press("ArrowRight");
    await expect(ladder(page).locator('a[data-order="1"]')).toBeFocused();
    await page.keyboard.press("ArrowUp");
    const moved = await page.evaluate(() => document.activeElement?.getAttribute("data-order"));
    expect(Number(moved)).toBeGreaterThan(1);
    await page.keyboard.press("End");
    await expect(ladder(page).locator('a[data-order="237"]')).toBeFocused();
    await page.keyboard.press("Home");
    await expect(ladder(page).locator('a[data-order="0"]')).toBeFocused();
  });

  test("every Chart and Table switch works", async ({ page }) => {
    await page.goto("/");
    const figures = page.locator("figure.fig:has(.seg)");
    const n = await figures.count();
    expect(n).toBeGreaterThanOrEqual(8);
    for (let i = 0; i < n; i++) {
      const fig = figures.nth(i);
      await fig.scrollIntoViewIfNeeded();
      await fig.getByRole("button", { name: "Table" }).click();
      await expect(fig.locator("table.tbl").first()).toBeVisible();
      await fig.getByRole("button", { name: "Chart" }).click();
      await expect(fig.locator("table.tbl")).toHaveCount(0);
    }
  });

  test("the table behind the ladder lists all 238 studies", async ({ page }) => {
    await page.goto("/");
    const fig = page.locator("#overview figure.fig");
    await fig.getByRole("button", { name: "Table" }).click();
    await expect(fig.locator("tbody tr")).toHaveCount(238);
    await expect(fig.locator("tr.hl")).toHaveCount(71);
  });

  test("the Excel model downloads", async ({ request, page }) => {
    await page.goto("/");
    await expect(page.locator('a[download][href$=".xlsx"]').first()).toBeVisible();
    const res = await request.get("/downloads/Pipeline-Benchmark-Model.xlsx");
    expect(res.status()).toBe(200);
    expect((await res.body()).length).toBeGreaterThan(1_000_000);
  });

  test("theme choice is applied and remembered", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Switch between light and dark theme/ }).click();
    const first = await page.locator("html").getAttribute("data-theme");
    expect(["light", "dark"]).toContain(first);
    expect(await page.evaluate(() => localStorage.getItem("tp-theme"))).toBe(first);
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", first!);
  });

  test("the share image and icon exist", async ({ request }) => {
    expect((await request.get("/opengraph-image.png")).status()).toBe(200);
    expect((await request.get("/icon.svg")).status()).toBe(200);
  });

  test("an unknown address shows the not-found page", async ({ page }) => {
    const res = await page.goto("/nothing-here");
    expect(res?.status()).toBe(404);
    await expect(page.getByRole("heading", { name: "That page does not exist" })).toBeVisible();
  });
});

test.describe("accessibility", () => {
  for (const scheme of ["light", "dark"] as const) {
    test(`axe finds no violations on the desktop page (${scheme})`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      if (scheme === "dark") await page.addInitScript(() => localStorage.setItem("tp-theme", "dark"));
      await page.goto("/");
      expect(await violations(page)).toEqual([]);
    });
    test(`axe finds no violations on a phone (${scheme})`, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.emulateMedia({ colorScheme: scheme });
      if (scheme === "dark") await page.addInitScript(() => localStorage.setItem("tp-theme", "dark"));
      await page.goto("/");
      expect(await violations(page)).toEqual([]);
    });
  }

  test("with every table open there are still no violations", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    for (const group of await page.locator(".seg").all()) await group.getByRole("button", { name: "Table" }).click();
    expect(await violations(page)).toEqual([]);
  });
});

test.describe("phone", () => {
  test.use({ viewport: { width: 390, height: 844 } });
  test("no sideways scroll, with the charts and then with every table open", async ({ page }) => {
    await page.goto("/");
    const wide = () => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(await wide()).toBeLessThanOrEqual(1);
    for (const group of await page.locator(".seg").all()) await group.getByRole("button", { name: "Table" }).click();
    expect(await wide()).toBeLessThanOrEqual(1);
  });
  test("the section menu opens and goes to a section", async ({ page }) => {
    await page.goto("/");
    await page.locator(".sections-menu summary").click();
    await page.locator(".sections-menu .menu a", { hasText: "Gulf" }).click();
    await expect(page).toHaveURL(/#gulf$/);
  });
  test("a tap selects a study so its detail can be read", async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
    const page = await ctx.newPage();
    await page.goto("/");
    await ladder(page).locator('a[data-order="5"]').tap();
    await expect(page.locator("#overview .detail")).toContainText("NCT");
    await ctx.close();
  });
});

test.describe("motion", () => {
  test("with reduced motion nothing is animating and the marks are in their final colours", async ({ page }) => {
    await page.goto("/");
    await page.waitForTimeout(300);
    expect(await running(page)).toBe(0);
    const fill = await ladder(page).locator(".mk.b").first().evaluate((el) => getComputedStyle(el).fill);
    expect(fill).toBe("rgb(175, 29, 78)");
  });
  test.describe("with motion allowed", () => {
    test.use({ reducedMotion: "no-preference" });
    test("the ladder fills, then the berry marks change colour last", async ({ page }) => {
      await page.goto("/");
      const berry = ladder(page).locator(".mk.b").first();
      expect(await berry.evaluate((el) => getComputedStyle(el).fill)).not.toBe("rgb(175, 29, 78)"); // still grey while the marks land
      await page.waitForTimeout(2200);
      expect(await berry.evaluate((el) => getComputedStyle(el).fill)).toBe("rgb(175, 29, 78)");
      expect(await running(page)).toBe(0);
    });
  });
});

test("opens in light mode even when the system prefers dark", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});
