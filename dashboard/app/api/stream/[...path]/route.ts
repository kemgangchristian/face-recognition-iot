// app/api/stream/[...path]/route.ts
//
// Proxifie le flux MJPEG vers l'API du Pi en transmettant le cookie de
// session. Le navigateur ne peut pas envoyer ce cookie directement au Pi
// (origine différente) : le flux passe donc par /api/stream/*, même origine
// que le login.

import { NextRequest, NextResponse } from "next/server";

const PI_URL = process.env.PI_URL || "http://192.168.1.191:8000";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const streamPath = path.join("/");
  const cookie = req.headers.get("cookie") ?? "";
  const search = req.nextUrl.search;

  const upstream = await fetch(`${PI_URL}/stream/${streamPath}${search}`, {
    method: "GET",
    headers: { cookie },
    cache: "no-store",
  });

  if (!upstream.ok || !upstream.body) {
    return new NextResponse(null, { status: upstream.status });
  }

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type":
        upstream.headers.get("Content-Type") ??
        "multipart/x-mixed-replace; boundary=frame",
      "Cache-Control": "no-cache, no-store, must-revalidate",
      Pragma: "no-cache",
      Expires: "0",
    },
  });
}
