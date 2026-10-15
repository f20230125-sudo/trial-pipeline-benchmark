import "server-only";
import fs from "node:fs";
import path from "node:path";
import {
  Concentration,
  Gulf,
  Headline,
  Meta,
  MsdActive,
  Overview,
  Quality,
  Readouts,
  Revenue,
  Starts,
  type Dataset,
} from "./schema";

const DIR = path.join(process.cwd(), "public", "data");

function read<T>(file: string, schema: { parse: (v: unknown) => T }): T {
  const raw = JSON.parse(fs.readFileSync(path.join(DIR, file), "utf-8"));
  try {
    return schema.parse(raw);
  } catch (e) {
    throw new Error(`${file} does not match its schema: ${e instanceof Error ? e.message : String(e)}`);
  }
}

/** Reads and validates every data file. Runs at build time on the server; the page ships the result. */
export function loadDataset(): Dataset {
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
