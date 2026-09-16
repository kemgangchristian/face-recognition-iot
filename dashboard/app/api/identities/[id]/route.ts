// app/api/identities/[id]/route.ts
//
// Proxifie la suppression d'une identité (droit à l'effacement RGPD)
// vers l'API du Pi. Route dynamique : le segment [id] capture
// l'identifiant numérique de l'identité à supprimer.

import { NextRequest, NextResponse } from "next/server";

const PI_URL = process.env.PI_URL || "http://192.168.1.191:8000";

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const cookie = req.headers.get("cookie") ?? "";

  const upstream = await fetch(`${PI_URL}/identities/${id}`, {
    method: "DELETE",
    headers: { cookie },
  });

  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}
