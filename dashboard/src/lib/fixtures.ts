// Test helper: loads the same JSON the site is built from, validated by the same schemas, without the server-only guard.
import fs from "node:fs";
import path from "node:path";
import { Concentration, Gulf, Headline, Meta, MsdActive, Overview, Quality, Readouts, Revenue, Starts, type Dataset } from "./schema";

const DIR = path.join(process.cwd(), "public", "data");
const read = <T,>(file: string, schema: { parse: (v: unknown) => T }): T => schema.parse(JSON.parse(fs.readFileSync(path.join(DIR, file), "utf-8")));

export function dataset(): Dataset {
  return {
    meta: read("meta.json", Meta),
    overview: read("overview.json", Overview),
    concentration: read("concentration.json", Concentration),
    revenue: read("revenue.json", Revenue),
    readouts: read("readouts.json", Readouts),
    starts: read("starts.json", Starts),
    gulf: read("gulf.json", Gulf),
    quality: read("quality.json", Quality),
    msdActive: read("msd_active.json", MsdActive),
    headline: read("headline.json", Headline),
  };
}
