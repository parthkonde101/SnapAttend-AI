/**
 * Centralized runtime configuration for the frontend.
 *
 * Everything here is sourced from environment variables so the same build
 * can point at different backends without code changes:
 *  - Development:   NEXT_PUBLIC_API_URL=http://localhost:8000
 *  - LAN testing:    NEXT_PUBLIC_API_URL=http://192.168.x.x:8000 (your machine's LAN IP,
 *                     so a phone on the same Wi-Fi can reach the backend)
 *  - Production:     NEXT_PUBLIC_API_URL=https://api.your-domain.com
 *
 * `NEXT_PUBLIC_*` vars are inlined at build time by Next.js, so this must
 * be set before `next build` / `next dev` — see `.env.local.example`.
 */

const DEFAULT_DEV_API_URL = "http://localhost:8000";

function resolveApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL;

  if (!configured) {
    if (process.env.NODE_ENV === "production") {
      // eslint-disable-next-line no-console
      console.warn(
        "NEXT_PUBLIC_API_URL is not set — falling back to the local development API. " +
          "Set it in your environment before building for LAN testing or production."
      );
    }
    return DEFAULT_DEV_API_URL;
  }

  // Trim a trailing slash so callers can safely do `${API_BASE_URL}${path}`.
  return configured.replace(/\/+$/, "");
}

export const API_BASE_URL = resolveApiBaseUrl();
