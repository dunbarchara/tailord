import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const res = await fetch(
    `${process.env.API_BASE_URL}/generate`,
    {
      method: "POST",
      headers: {
        "X-API-Key": process.env.API_KEY!,
      },
    }
  );

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
