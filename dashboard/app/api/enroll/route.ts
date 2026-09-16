// app/api/enroll/route.ts
//
// Proxifie l'enrôlement vers l'API du Pi. Le corps est un formulaire
// multipart (nom + fichier image capturé depuis le flux caméra) : on le
// lit puis on le retransmet tel quel, sans le reconstruire manuellement,
// pour préserver l'encodage binaire exact de l'image.

import { NextRequest, NextResponse } from "next/server";

const PI_URL = process.env.PI_URL || "http://192.168.1.191:8000";

export async function POST(req: NextRequest) {
  const cookie = req.headers.get("cookie") ?? "";
  const formData = await req.formData();

  const upstream = await fetch(`${PI_URL}/enroll`, {
    method: "POST",
    headers: { cookie },
    body: formData,
  });

  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}
