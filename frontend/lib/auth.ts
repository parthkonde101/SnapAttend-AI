"use client";

import type { UserRole } from "@/lib/types";

const TOKEN_COOKIE = "sa_token";
const ROLE_COOKIE = "sa_role";
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24; // 1 day, mirrors the backend's default token lifetime

function setCookie(name: string, value: string, maxAgeSeconds: number) {
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${maxAgeSeconds}; SameSite=Lax`;
}

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

function deleteCookie(name: string) {
  document.cookie = `${name}=; path=/; max-age=0`;
}

/** Persist the access token and role after a successful login/registration. */
export function storeSession(token: string, role: UserRole) {
  setCookie(TOKEN_COOKIE, token, COOKIE_MAX_AGE_SECONDS);
  setCookie(ROLE_COOKIE, role, COOKIE_MAX_AGE_SECONDS);
}

/** Read the currently stored access token, if any. */
export function getToken(): string | null {
  return getCookie(TOKEN_COOKIE);
}

/** Read the currently stored user role, if any. */
export function getRole(): UserRole | null {
  const role = getCookie(ROLE_COOKIE);
  return role === "student" || role === "teacher" ? role : null;
}

/** Clear the stored session, logging the user out. */
export function clearSession() {
  deleteCookie(TOKEN_COOKIE);
  deleteCookie(ROLE_COOKIE);
}
