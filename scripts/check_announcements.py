"""ÖSYM duyurular sayfasını okuyup mevcut duyuru listesini bir webhook'a gönderir.

Kaynak: https://www.osym.gov.tr/duyurular/index
Her çalıştırmada (zamanlanmış ya da manuel) sayfadaki duyuru listesi çekilir ve
JSON olarak WEBHOOK_URL'e POST edilir. Herhangi bir state/fark takibi yapılmaz;
her tetiklemede sayfada o an görünen tüm duyurular gönderilir.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://www.osym.gov.tr/duyurular/index"
DEFAULT_WEBHOOK_URL = "https://webhook.site/7c90a1ec-1890-402c-9a16-823bf3852200"
# GitHub Actions secret'ı tanımlı değilse veya boşsa varsayılana düşer.
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") or DEFAULT_WEBHOOK_URL
REQUEST_TIMEOUT = 30
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch_announcements() -> list[dict]:
    response = requests.get(SOURCE_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    items = soup.select("a.duyuru-list-item")

    announcements = []
    for item in items:
        href = item.get("href", "").strip()
        if not href:
            continue

        title_span = item.select_one(".duyuru-list-title")
        title = (title_span.get_text(strip=True) if title_span else item.get("title", "")).strip()

        day_span = item.select_one(".duyuru-list-day")
        my_span = item.select_one(".duyuru-list-my")
        day = day_span.get_text(strip=True) if day_span else ""
        month_year = my_span.get_text(strip=True) if my_span else ""
        date_text = f"{day} {month_year}".strip()

        announcements.append(
            {
                "id": href,
                "title": title,
                "date": date_text,
                "url": urljoin(SOURCE_URL, href),
            }
        )

    return announcements


def send_webhook(announcements: list[dict]) -> None:
    payload = {
        "source": SOURCE_URL,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "count": len(announcements),
        "announcements": announcements,
    }
    response = requests.post(WEBHOOK_URL, json=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    print(f"Webhook'a gönderildi: {len(announcements)} duyuru (HTTP {response.status_code}).")


def main() -> int:
    announcements = fetch_announcements()
    if not announcements:
        print("Hiç duyuru bulunamadı; sayfa yapısı değişmiş olabilir.", file=sys.stderr)
        return 1

    send_webhook(announcements)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
