import type { Metadata, Viewport } from "next";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-serif/500.css";
import "@fontsource/ibm-plex-serif/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "./globals.css";

export const metadata: Metadata = {
  // Share-image addresses are built from this; set NEXT_PUBLIC_SITE_URL to the real address when the site is published.
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "https://trial-pipeline-benchmark.vercel.app"),
  title: "Trial Pipeline Benchmark: MSD against 11 peers on clinical-trial pipelines",
  description:
    "MSD and 11 peer companies compared on clinical-trial pipelines, from the public ClinicalTrials.gov registry: pipeline size, concentration on one molecule, expiring revenue, readouts due, starts and stops, and Gulf presence. Every count traces to a registry record.",
  authors: [{ name: "Mohammad Uzair Khan" }],
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#faf8f3" },
    { media: "(prefers-color-scheme: dark)", color: "#111817" },
  ],
  width: "device-width",
  initialScale: 1,
};

// Sets the saved theme before first paint so there is no flash of the wrong one.
const themeScript = `try{var t=localStorage.getItem("tp-theme");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
