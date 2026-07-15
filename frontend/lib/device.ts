const DEVICE_ID_STORAGE_KEY = "sa_device_id";

/**
 * Milestone 6C, Part 1 — Temporary Device Lock. Reuses the existing device
 * identifier from localStorage if one already exists; otherwise generates
 * a fresh random UUID and persists it locally. Never asks the student for
 * any input, and this id is never permanently tied to a student account —
 * the backend only ever associates it with a student for the lifetime of
 * a single active attendance session (see
 * `app/services/device_lock_service.py`), clearing that association the
 * moment the session ends.
 *
 * Returns null during server-side rendering (no `window`) or if
 * localStorage is unavailable — callers treat null the same as "no device
 * id available" and simply omit it from the request, exactly like a
 * client that predates this feature.
 */
export function getOrCreateDeviceId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const existing = window.localStorage.getItem(DEVICE_ID_STORAGE_KEY);
    if (existing) return existing;

    const generated =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `dev-${Date.now()}-${Math.random().toString(16).slice(2)}`;

    window.localStorage.setItem(DEVICE_ID_STORAGE_KEY, generated);
    return generated;
  } catch {
    return null;
  }
}
