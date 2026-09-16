// app/api/stats/route.ts
//
// Proxifie /stats vers l'API du Pi, en transmettant le cookie de session
// du navigateur au Pi (server-to-server), puis en renvoyant la réponse
// telle quelle au client. Le navigateur n'a jamais connaissance de
// l'adresse réelle du Pi ni d'un quelconque secret.

import { NextRequest, NextResponse } from "next/server";

const PI_URL = process.env.PI_URL || "http://192.168.1.191:8000";

export async function GET(req: NextRequest) {
  const cookie = req.headers.get("cookie") ?? "";

  const upstream = await fetch(`${PI_URL}/stats`, {
    method: "GET",
    headers: { cookie },
    cache: "no-store",
  });

  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}
