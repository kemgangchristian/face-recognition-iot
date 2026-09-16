// app/api/identities/route.ts
//
// Proxifie la liste des identités enrôlées vers l'API du Pi.
// La suppression (DELETE /identities/{id}) est gérée dans la route
// dynamique voisine : app/api/identities/[id]/route.ts

import { NextRequest, NextResponse } from "next/server";

const PI_URL = process.env.PI_URL || "http://192.168.1.191:8000";

export async function GET(req: NextRequest) {
  const cookie = req.headers.get("cookie") ?? "";

  const upstream = await fetch(`${PI_URL}/identities`, {
    method: "GET",
    headers: { cookie },
    cache: "no-store",
  });

  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}
