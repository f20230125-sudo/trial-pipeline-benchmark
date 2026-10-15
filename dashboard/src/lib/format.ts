const MINUS = "−";

function trim(n: number, digits: number): string {
  return n.toFixed(digits).replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1");
}

/** Compact dollars: 116891569123 -> "$116.9B", 892e6 -> "$892M", 4.2e6 -> "$4.2M". */
export function usd(n: number | null | undefined, digits = 1): string {
  if (n == null || Number.isNaN(n)) return "n/a";
  const sign = n < 0 ? MINUS : "";
  const a = Math.abs(n);
  if (a >= 1e12) return `${sign}$${trim(a / 1e12, digits)}T`;
  if (a >= 1e9) return `${sign}$${trim(a / 1e9, digits)}B`;
  if (a >= 1e6) return `${sign}$${trim(a / 1e6, a >= 1e8 ? 0 : digits)}M`;
  if (a >= 1e3) return `${sign}$${trim(a / 1e3, 0)}K`;
  return `${sign}$${Math.round(a)}`;
}

/** Whole dollars with separators: 1092.4 -> "$1,092". For per-person figures, where "$1K" would hide the answer. */
export function dollars(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "n/a";
  return `${n < 0 ? MINUS : ""}$${Math.round(Math.abs(n)).toLocaleString("en-US")}`;
}

/** Compact counts: 724600000 -> "724.6M". */
export function count(n: number | null | undefined, digits = 1): string {
  if (n == null || Number.isNaN(n)) return "n/a";
  const sign = n < 0 ? MINUS : "";
  const a = Math.abs(n);
  if (a >= 1e9) return `${sign}${trim(a / 1e9, digits)}B`;
  if (a >= 1e6) return `${sign}${trim(a / 1e6, digits)}M`;
  if (a >= 1e3) return `${sign}${trim(a / 1e3, digits)}K`;
  return `${sign}${Math.round(a)}`;
}

/** A fraction as a percent: 0.886 -> "88.6%". */
export function pct(fraction: number | null | undefined, digits = 0): string {
  if (fraction == null || Number.isNaN(fraction)) return "n/a";
  return `${(fraction * 100).toFixed(digits).replace("-", MINUS)}%`;
}

/** Signed change: 0.6 -> "+60%", -0.0055 -> "−0.6%". */
export function signedPct(fraction: number | null | undefined, digits = 0): string {
  if (fraction == null || Number.isNaN(fraction)) return "n/a";
  const v = fraction * 100;
  const body = Math.abs(v).toFixed(digits);
  return `${v < 0 ? MINUS : "+"}${body}%`;
}

/** Signed compact dollars: +$11.9B / −$6.2B. */
export function signedUsd(n: number, digits = 1): string {
  return `${n < 0 ? MINUS : "+"}${usd(Math.abs(n), digits)}`;
}

export function dateLabel(iso: string | null | undefined): string {
  if (!iso) return "n/a";
  const [y, m] = iso.split("-");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${months[Number(m) - 1]} ${y}`;
}

export function titleCase(s: string): string {
  return s
    .toLowerCase()
    .replace(/\b([a-z])/g, (c) => c.toUpperCase())
    .replace(/\bOf\b/g, "of");
}

const FULL_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

/** 1363 -> "1,363". */
export function int(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "n/a";
  return `${n < 0 ? MINUS : ""}${Math.round(Math.abs(n)).toLocaleString("en-US")}`;
}

/** A number that is already a percent: 35.3 -> "35.3%". */
export function pct1(n: number | null | undefined, digits = 1): string {
  if (n == null || Number.isNaN(n)) return "n/a";
  return `${n.toFixed(digits)}%`;
}

/** "JANUVIA (Nov 2026), JANUMET (Nov 2026)" -> "Januvia (Nov 2026), Janumet (Nov 2026)": product names are upper case in the data. */
export function productCase(s: string): string {
  return s.replace(/\b([A-Z])([A-Z]{4,})\b/g, (_m, first: string, rest: string) => first + rest.toLowerCase());
}

/** "2026-10-14" -> "14 October 2026". */
export function longDate(iso: string | null | undefined): string {
  if (!iso) return "n/a";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${d} ${FULL_MONTHS[m - 1]} ${y}`;
}

/** "2028-09-30" -> "September 2028". */
export function monthYear(iso: string | null | undefined): string {
  if (!iso) return "n/a";
  const [y, m] = iso.slice(0, 7).split("-").map(Number);
  return `${FULL_MONTHS[m - 1]} ${y}`;
}
