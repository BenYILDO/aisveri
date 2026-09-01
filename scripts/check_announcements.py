"""ÖSYM duyurular sayfasını okuyup yeni duyuruları bir webhook'a gönderir.

Kaynak: https://www.osym.gov.tr/duyurular/index
Her çalıştırmada sayfadaki duyuru listesi çekilir, data/seen_announcements.json
içindeki daha önce görülen duyurularla karşılaştırılır. Yeni bulunan duyurular
varsa WEBHOOK_URL'e tek bir POST isteğiyle gönderilir ve state dosyası güncellenir.

İlk çalıştırmada (state dosyası yoksa) mevcut duyurular sadece kaydedilir,
webhook'a gönderilmez; amaç geçmiş duyuru arşivini tek seferde webhook'a
boşaltmak değil, bundan sonraki YENİ duyuruları takip etmektir.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://www.osym.gov.tr/duyurular/index"
DEFAULT_WEBHOOK_URL = "https://webhook.site/7c90a1ec-1890-402c-9a16-823bf3852200"
# GitHub Actions secret'ı tanımlı değilse veya boşsa varsayılana düşer.
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") or DEFAULT_WEBHOOK_URL
STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "seen_announcements.json"
MAX_STATE_ITEMS = 300
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


def load_seen_ids() -> set[str] | None:
    if not STATE_FILE.exists():
        return None
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data.get("seen_ids", []))
    except (json.JSONDecodeError, OSError):
        return None


def save_seen_ids(ids: list[str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "seen_ids": ids[:MAX_STATE_ITEMS],
    }
    STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def send_webhook(new_announcements: list[dict]) -> None:
    payload = {
        "source": SOURCE_URL,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "count": len(new_announcements),
        "new_announcements": new_announcements,
    }
    response = requests.post(WEBHOOK_URL, json=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    print(f"Webhook'a gönderildi: {len(new_announcements)} yeni duyuru (HTTP {response.status_code}).")


def main() -> int:
    announcements = fetch_announcements()
    if not announcements:
        print("Hiç duyuru bulunamadı; sayfa yapısı değişmiş olabilir.", file=sys.stderr)
        return 1

    current_ids = [a["id"] for a in announcements]
    seen_ids = load_seen_ids()

    if seen_ids is None:
        print("İlk çalıştırma: state dosyası yok, mevcut duyurular sadece kaydediliyor (webhook'a gönderilmiyor).")
        save_seen_ids(current_ids)
        return 0

    new_announcements = [a for a in announcements if a["id"] not in seen_ids]

    if new_announcements:
        send_webhook(new_announcements)
    else:
        print("Yeni duyuru yok.")

    # sırayı koru: en yeni duyurular listenin başında geliyor
    merged_ids = current_ids + [i for i in seen_ids if i not in current_ids]
    save_seen_ids(merged_ids)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
