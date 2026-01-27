export async function analyzeJob(url: string) {
  const res = await fetch("/api/analyze", {
    method: "POST",
    body: JSON.stringify({ url }),
  });

  if (!res.ok) throw new Error("Failed");

  return res.json();
}

export async function parseJob(url: string) {
  const res = await fetch("/api/parse", {
    method: "POST",
    body: JSON.stringify({ url }),
  });

  if (!res.ok) throw new Error("Failed");

  return res.json();
}

export async function submitProfile(jsonBody: string) {
  const res = await fetch("/api/profile", {
    method: "POST",
    body: jsonBody,
  });

  if (!res.ok) throw new Error("Failed");

  return res.json();
}

export async function submitJob(jsonBody: string) {
  const res = await fetch("/api/job", {
    method: "POST",
    body: jsonBody,
  });

  if (!res.ok) throw new Error("Failed");

  return res.json();
}

export async function generateMatch(jsonBody: string) {
  const res = await fetch("/api/generate", {
    method: "POST",
    body: jsonBody,
  });

  if (!res.ok) throw new Error("Failed");

  return res.json();
}
