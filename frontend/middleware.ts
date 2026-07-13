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

  const isStudentRoute = pathname.startsWith("/student/dashboard");
  const isTeacherRoute = pathname.startsWith("/teacher/dashboard");

  if (isStudentRoute && (!token || role !== "student")) {
    return NextResponse.redirect(new URL("/student/login", request.url));
  }

  if (isTeacherRoute && (!token || role !== "teacher")) {
    return NextResponse.redirect(new URL("/teacher/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/student/dashboard/:path*", "/teacher/dashboard/:path*"],
};
