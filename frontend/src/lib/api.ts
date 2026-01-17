export async function analyzeJob(url: string) {
  const res = await fetch("/api/analyze", {
    method: "POST",
    body: JSON.stringify({ url }),
  });

  if (!res.ok) throw new Error("Failed");

  return res.json();
}
