import requests
from bs4 import BeautifulSoup

def scrape_job_text(url: str) -> str:
    html = requests.get(url).text
    soup = BeautifulSoup(html, "html.parser")
    return " ".join(p.get_text() for p in soup.find_all("p"))
