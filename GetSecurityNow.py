import os
import re
import requests
from bs4 import BeautifulSoup


def get_latest_security_now_episode() -> int:
    """Fetch the latest Security Now episode number from https://twit.tv/sn.

    Strategy:
    - Load the page (which redirects to /shows/security-now).
    - Extract all links that match /shows/security-now/episodes/<number>.
    - Return the maximum episode number found.
    If anything fails, fall back to a safe default so the script still works.
    """
    url = "https://twit.tv/sn"
    try:
        headers = {
            "User-Agent": "clubtwitshows/0.1 (+https://twit.tv/)"
        }
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        html = resp.text

        # First, try BeautifulSoup to find anchors
        soup = BeautifulSoup(html, "lxml")
        candidates = set()
        for a in soup.find_all("a", href=True):
            m = re.search(r"/shows/security-now/episodes/(\d+)", a["href"])  # noqa: W605
            if m:
                candidates.add(int(m.group(1)))

        # Fallback: regex over the whole page
        if not candidates:
            for m in re.finditer(r"/shows/security-now/episodes/(\d+)", html):  # noqa: W605
                candidates.add(int(m.group(1)))

        if candidates:
            return max(candidates)
    except Exception:
        # Swallow and use fallback below
        pass

    # Fallback to a conservative recent value if scraping fails
    return 1052


if __name__ == "__main__":
    latest_episode = get_latest_security_now_episode()
    speed = input("Speed in Kbps(blank = no limit): ")
    speed = speed if speed else "0"

    # Change to your desired download directory
    os.chdir('/media/mainmeister/2TBB/security_now')

    for episode in range(1, latest_episode + 1):
        if int(speed) > 0:
            os.system(
                f"yt-dlp --limit-rate {speed}K --download-archive archive.txt "
                f"https://twit.tv/shows/security-now/episodes/{episode}"
            )
        else:
            os.system(
                f"yt-dlp --download-archive archive.txt "
                f"https://twit.tv/shows/security-now/episodes/{episode}"
            )
    print("All done!")
