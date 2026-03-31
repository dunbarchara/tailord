import requests


def fetch_repos(username: str) -> list[dict]:
    url = f"https://api.github.com/users/{username}/repos"
    resp = requests.get(url, params={"per_page": 100, "sort": "pushed"})
    if resp.status_code == 404:
        raise ValueError(f"GitHub user '{username}' not found")
    if resp.status_code != 200:
        return []

    repos = resp.json()

    filtered = [
        r for r in repos
        if not r.get("fork")
        and not r.get("archived")
        # Drop repos with no stars AND no description — pure noise
        and not (r.get("stargazers_count", 0) == 0 and not r.get("description"))
    ]

    # API returns repos sorted by pushed_at (sort=pushed) — preserve that order.

    return [
        {
            "name": r["name"],
            "description": r["description"],
            "language": r["language"],
            "star_count": r.get("stargazers_count", 0),
            "pushed_at": r.get("pushed_at"),
        }
        for r in filtered[:10]
    ]
