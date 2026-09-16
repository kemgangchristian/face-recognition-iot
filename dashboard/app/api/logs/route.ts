// app/api/logs/route.ts
//
// Proxifie /logs vers l'API du Pi, en transmettant le paramètre `limit`
// et le cookie de session du navigateur.

import { NextRequest, NextResponse } from "next/server";

const PI_URL = process.env.PI_URL || "http://192.168.1.191:8000";

export async function GET(req: NextRequest) {
  const cookie = req.headers.get("cookie") ?? "";
  const limit = req.nextUrl.searchParams.get("limit") ?? "100";

  const upstream = await fetch(`${PI_URL}/logs?limit=${limit}`, {
    method: "GET",
    headers: { cookie },
    cache: "no-store",
  });

  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}
