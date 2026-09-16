// app/api/logout/route.ts
//
// Proxifie la déconnexion vers le Pi. Transmet le cookie de session
// courant pour que le Pi sache quelle session invalider, puis retransmet
// le Set-Cookie de suppression au navigateur.

import { NextRequest, NextResponse } from "next/server";

const PI_URL = process.env.PI_URL || "http://192.168.1.191:8000";

export async function POST(req: NextRequest) {
  const cookie = req.headers.get("cookie") ?? "";

  const upstream = await fetch(`${PI_URL}/logout`, {
    method: "POST",
    headers: { cookie },
  });

  const data = await upstream.json();
  const response = NextResponse.json(data, { status: upstream.status });

  const setCookie = upstream.headers.get("set-cookie");
  if (setCookie) {
    response.headers.set("set-cookie", setCookie);
  }

  return response;
}
