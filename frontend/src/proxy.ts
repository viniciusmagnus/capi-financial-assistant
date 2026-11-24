import { getSessionCookie } from "better-auth/cookies";
import { type NextRequest, NextResponse } from "next/server";

import { paginaDeEntrada } from "@/lib/destino";

export function proxy(request: NextRequest) {
  if (getSessionCookie(request, { cookiePrefix: "capi" })) return NextResponse.next();
  const { pathname, search } = request.nextUrl;
  return NextResponse.redirect(new URL(paginaDeEntrada(`${pathname}${search}`), request.url));
}

export const config = {
  matcher: ["/", "/chat/:path*", "/busca/:path*", "/regras/:path*", "/conta/:path*"],
};
