// app/api/login/route.ts
//
// Proxifie l'authentification vers le Pi. Le Set-Cookie renvoyé par le Pi
// est retransmis tel quel au navigateur : celui-ci le stocke pour
// l'origine du dashboard (même origine que cette route), et l'enverra
// automatiquement à chaque appel suivant vers /api/*.

import { NextRequest, NextResponse } from "next/server";

const PI_URL = process.env.PI_URL || "http://192.168.1.191:8000";

export async function POST(req: NextRequest) {
  const body = await req.formData();

  const upstream = await fetch(`${PI_URL}/login`, {
    method: "POST",
    body,
  });

  const data = await upstream.json();
  const response = NextResponse.json(data, { status: upstream.status });

  const setCookie = upstream.headers.get("set-cookie");
  if (setCookie) {
    response.headers.set("set-cookie", setCookie);
  }

  return response;
}
