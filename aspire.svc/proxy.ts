import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const LEGACY_MAIN_PREFIX = "/main";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname === LEGACY_MAIN_PREFIX || pathname === `${LEGACY_MAIN_PREFIX}/`) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  if (pathname.startsWith(`${LEGACY_MAIN_PREFIX}/`)) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/main", "/main/:path*"],
};
