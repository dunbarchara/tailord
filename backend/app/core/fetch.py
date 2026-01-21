import httpx

def fetch_html(url: str) -> str:
    headers = {"User-Agent": "Tailord/1.0"}
    with httpx.Client(timeout=10, follow_redirects=True) as client:
        r = client.get(url, headers=headers)
        r.raise_for_status()
        return r.text
