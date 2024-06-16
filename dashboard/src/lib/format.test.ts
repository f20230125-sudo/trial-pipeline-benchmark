import { describe, expect, it } from "vitest";
import { count, dateLabel, pct, signedPct, signedUsd, usd } from "./format";

describe("usd", () => {
  it("compacts to the right unit", () => {
    expect(usd(116_891_569_123)).toBe("$116.9B");
    expect(usd(892_000_000)).toBe("$892M");
    expect(usd(42_300_000)).toBe("$42.3M");
    expect(usd(4_200_000)).toBe("$4.2M");
    expect(usd(850_000)).toBe("$850K");
    expect(usd(12)).toBe("$12");
  });
  it("uses a true minus and handles missing values", () => {
    expect(usd(-6_190_000_000)).toBe("−$6.2B");
    expect(usd(null)).toBe("n/a");
    expect(usd(Number.NaN)).toBe("n/a");
  });
  it("drops a trailing .0", () => {
    expect(usd(8_000_000_000)).toBe("$8B");
  });
});

describe("count / pct / signed", () => {
  it("formats counts", () => {
    expect(count(724_600_000)).toBe("724.6M");
    expect(count(12_300)).toBe("12.3K");
  });
  it("formats percentages", () => {
    expect(pct(0.886, 1)).toBe("88.6%");
    expect(pct(0.14)).toBe("14%");
    expect(signedPct(0.6)).toBe("+60%");
    expect(signedPct(-0.0062, 1)).toBe("−0.6%");
    expect(signedUsd(11_930_000_000)).toBe("+$11.9B");
    expect(signedUsd(-6_190_000_000)).toBe("−$6.2B");
  });
});

describe("dateLabel", () => {
  it("shows month and year", () => {
    expect(dateLabel("2026-11-24")).toBe("Nov 2026");
    expect(dateLabel(null)).toBe("n/a");
  });
});

import { productCase } from "./format";
describe("productCase", () => {
  it("lower-cases the upper-case product names but keeps months and short words", () => {
    expect(productCase("JANUVIA (Nov 2026), JANUMET (Nov 2026)")).toBe("Januvia (Nov 2026), Janumet (Nov 2026)");
    expect(productCase("BRIDION (Jun 2028)")).toBe("Bridion (Jun 2028)");
    expect(productCase("MSD and HIV")).toBe("MSD and HIV");
  });
});
