import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const body = await req.text();
  const res = await fetch(
    `${process.env.API_BASE_URL}/generate`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": process.env.API_KEY!,
      },
      body,
    }
  );

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
