import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import { ThemeProvider } from "@/components/theme-provider";

import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "SnapAttend",
  description: "Fast, reliable attendance tracking for classrooms.",
};

// Milestone 7B: Next.js's App Router does not inject a viewport meta tag
// automatically — without one, mobile browsers fall back to a ~980px
// virtual viewport and scale the whole page down to fit, which is what
// caused every page to "require zooming out" even though layouts already
// use fluid/relative units. Pinch-zoom is intentionally left enabled
// (maximumScale: 5) for accessibility — only the broken initial scale is
// being fixed here.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  viewportFit: "cover",
};

// Runs before React hydrates so the correct theme class is present on
// <html> for the very first paint (no light-mode flash in dark mode).
const themeInitScript = `
(function () {
  try {
    var stored = window.localStorage.getItem("snapattend-theme");
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    var theme = stored || (prefersDark ? "dark" : "light");
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    }
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className={`${inter.variable} min-h-dvh font-sans antialiased`}>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
