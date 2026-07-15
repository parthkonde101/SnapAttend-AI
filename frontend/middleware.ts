import { NextRequest, NextResponse } from "next/server";

/**
 * Edge middleware guarding the dashboard routes. Real authorization still
 * happens against the backend (the JWT is verified server-side on every
 * API call); this only prevents an obviously logged-out browser from
 * rendering a dashboard shell before redirecting to the right login page.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get("sa_token")?.value;
  const role = request.cookies.get("sa_role")?.value;

  const isStudentRoute = pathname.startsWith("/student/dashboard") || pathname.startsWith("/student/attendance");
  const isTeacherRoute = pathname.startsWith("/teacher/dashboard") || pathname.startsWith("/teacher/session");
  const isAdminRoute = pathname.startsWith("/admin/dashboard");

  if (isStudentRoute && (!token || role !== "student")) {
    return NextResponse.redirect(new URL("/student/login", request.url));
  }

  if (isTeacherRoute && (!token || role !== "teacher")) {
    return NextResponse.redirect(new URL("/teacher/login", request.url));
  }

  // Milestone 7A: an Administrator is not a Teacher — a teacher's own
  // token (role="teacher") must bounce off /admin/dashboard exactly like
  // an unauthenticated browser would, not be treated as "close enough".
  if (isAdminRoute && (!token || role !== "admin")) {
    return NextResponse.redirect(new URL("/admin/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/student/dashboard/:path*",
    "/student/attendance/:path*",
    "/teacher/dashboard/:path*",
    "/teacher/session/:path*",
    "/admin/dashboard/:path*",
  ],
};
