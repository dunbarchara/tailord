import requests

def fetch_repos(username: str):
    url = f"https://api.github.com/users/{username}/repos"
    resp = requests.get(url)
    if resp.status_code != 200:
        return []

    repos = resp.json()
    return [
        {
            "name": r["name"],
            "description": r["description"],
            "language": r["language"]
        }
        for r in repos[:5]
    ]
