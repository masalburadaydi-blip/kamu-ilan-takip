import json
import os
import re
import hashlib
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


CONFIG = json.load(open("config.json", encoding="utf-8"))

SEEN_FILE = "seen.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )
}


def norm(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def load_seen():
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(
            sorted(seen)[-5000:],
            f,
            ensure_ascii=False,
            indent=2
        )


def fetch(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()
    return response.text


def make_id(title, url):
    value = title.strip() + "|" + url
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()[:20]


def has_any(text, terms):
    text = norm(text)
    return any(term in text for term in terms)


def classify(text):
    t = norm(text)

    # Önce açıkça KPSS aranmayacağını kontrol et.
    no_kpss = has_any(
        t,
        CONFIG.get("no_kpss_terms", [])
    )

    if not no_kpss:
        return None

    # Önlisans/lisans veya coğrafya ile ilgili eğitim şartı aranıyor mu?
    education = has_any(
        t,
        CONFIG.get("education_terms", [])
    )

    if not education:
        return None

    permanent = has_any(
        t,
        CONFIG.get("permanent_terms", [])
    )

    contract = has_any(
        t,
        CONFIG.get("contract_terms", [])
    )

    if permanent:
        return "Kadrolu/daimi"
    elif contract:
        return "Sözleşmeli"
    else:
        return "Belirtilmemiş"


def extract_links(source):
    html = fetch(source["url"])

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    links = []

    for a in soup.find_all("a", href=True):
        title = a.get_text(
            " ",
            strip=True
        )

        href = urljoin(
            source["url"],
            a["href"]
        )

        if len(title) < 8:
            continue

        if href.startswith("javascript:"):
            continue

        if href.startswith("mailto:"):
            continue

        links.append(
            (title, href)
        )

    # Aynı URL'leri kaldır.
    unique = []
    seen_urls = set()

    for title, url in links:
        if url not in seen_urls:
            seen_urls.add(url)
            unique.append(
                (title, url)
            )

    return unique


def inspect_candidate(title, url):
    try:
        html = fetch(url)
    except Exception as e:
        print(
            f"[DETAY HATASI] {title[:80]} | {e}"
        )
        return None

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    text = soup.get_text(
        " ",
        strip=True
    )

    combined = title + " " + text

    status = classify(combined)

    if not status:
        return None

    # Açık KPSS'siz ifadesini ilan metninde
    # gerçekten görmüş olduğumuzdan emin ol.
    if not has_any(
        text,
        CONFIG.get("no_kpss_terms", [])
    ):
        return None

    return {
        "title": title.strip(),
        "url": url,
        "status": status,
        "text": text[:10000]
    }


def city_from(text):
    t = norm(text)

    if "ankara" in t:
        return "Ankara"

    cities = [
        "adana",
        "adıyaman",
        "afyonkarahisar",
        "ağrı",
        "amasya",
        "antalya",
        "artvin",
        "aydın",
        "balıkesir",
        "bilecik",
        "bingöl",
        "bitlis",
        "bolu",
        "burdur",
        "bursa",
        "çanakkale",
        "çankırı",
        "çorum",
        "denizli",
        "diyarbakır",
        "edirne",
        "elazığ",
        "erzincan",
        "erzurum",
        "eskişehir",
        "gaziantep",
        "giresun",
        "gümüşhane",
        "hakkari",
        "hatay",
        "ısparta",
        "mersin",
        "istanbul",
        "izmir",
        "kars",
        "kastamonu",
        "kayseri",
        "kırklareli",
        "kırşehir",
        "kocaeli",
        "konya",
        "kütahya",
        "malatya",
        "manisa",
        "mardin",
        "muğla",
        "muş",
        "nevşehir",
        "niğde",
        "ordu",
        "rize",
        "sakarya",
        "samsun",
        "siirt",
        "sinop",
        "sivas",
        "şanlıurfa",
        "şırnak",
        "tekirdağ",
        "tokat",
        "trabzon",
        "tunceli",
        "uşak",
        "van",
        "yalova",
        "yozgat",
        "zonguldak",
        "aksaray",
        "bayburt",
        "karaman",
        "kırıkkale",
        "batman",
        "bartın",
        "ardahan",
        "ığdır",
        "osmaniye",
        "düzce"
    ]

    for city in cities:
        if city in t:
            return city.title()

    return "Türkiye geneli / belirtilmemiş"


def send_telegram(items):
    token = os.environ.get(
        "TELEGRAM_BOT_TOKEN"
    )

    chat_id = os.environ.get(
        "TELEGRAM_CHAT_ID"
    )

    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN secret bulunamadı."
        )

    if not chat_id:
        raise RuntimeError(
            "TELEGRAM_CHAT_ID secret bulunamadı."
        )

    telegram_url = (
        f"https://api.telegram.org/"
        f"bot{token}/sendMessage"
    )

    sent = 0

    for item in items:
        city = city_from(
            item["text"]
        )

        prefix = (
            "⭐ "
            if item["status"] == "Kadrolu/daimi"
            else ""
        )

        message = (
            f"{prefix}<b>Yeni kamu ilanı</b>\n\n"
            f"<b>İlan:</b> {item['title']}\n"
            f"<b>Yer:</b> {city}\n"
            f"<b>Statü:</b> {item['status']}\n"
            f"<b>Filtre:</b> KPSS şartı açıkça aranmayacak + önlisans/lisans\n\n"
            f'<a href="{item["url"]}">İlana git</a>'
        )

        response = requests.post(
            telegram_url,
            data={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            },
            timeout=20
        )

        if not response.ok:
            print(
                "[TELEGRAM HATASI]",
                response.text
            )
            response.raise_for_status()

        sent += 1

    return sent


def main():
    print("=" * 60)
    print("KAMU İLAN TAKİP BAŞLADI")
    print("=" * 60)

    seen = load_seen()
    found = []

    total_links = 0
    total_checked = 0

    for source in CONFIG["sources"]:
        name = source["name"]

        print()
        print(
            f"[KAYNAK] {name}"
        )
        print(
            f"[URL] {source['url']}"
        )

        try:
            links = extract_links(
                source
            )

            print(
                f"[BAĞLANTI] {len(links)} bağlantı bulundu."
            )

            total_links += len(links)

        except Exception as e:
            print(
                f"[KAYNAK HATASI] {name}: {e}"
            )
            continue

        priority = []
        normal = []

        for title, url in links:
            title_norm = norm(title)

            if re.search(
                r"personel|memur|ilan|kadro|"
                r"alım|işçi|sözleşmeli|uzman|"
                r"büro|mühendis|tekniker|teknisyen",
                title_norm
            ):
                priority.append(
                    (title, url)
                )
            else:
                normal.append(
                    (title, url)
                )

        candidates = (
            priority +
            normal[:30]
        )

        # Aynı URL tekrarlarını kaldır.
        unique_candidates = []
        candidate_urls = set()

        for title, url in candidates:
            if url not in candidate_urls:
                candidate_urls.add(url)
                unique_candidates.append(
                    (title, url)
                )

        print(
            f"[ADAY] {len(unique_candidates)} bağlantı incelenecek."
        )

        for title, url in unique_candidates[:80]:
            total_checked += 1

            item = inspect_candidate(
                title,
                url
            )

            if item:
                item["id"] = make_id(
                    item["title"],
                    item["url"]
                )

                if item["id"] not in seen:
                    found.append(item)

                    print(
                        f"[EŞLEŞME] {item['title'][:100]}"
                    )

    found.sort(
        key=lambda x: (
            0
            if city_from(x["text"]) == "Ankara"
            else 1,

            0
            if x["status"] == "Kadrolu/daimi"
            else 1,

            norm(x["title"])
        )
    )

    print()
    print("=" * 60)
    print(
        f"TOPLAM BAĞLANTI: {total_links}"
    )
    print(
        f"TOPLAM İNCELENEN: {total_checked}"
    )
    print(
        f"YENİ UYGUN İLAN: {len(found)}"
    )
    print("=" * 60)

    if found:
        try:
            sent = send_telegram(
                found
            )

            seen.update(
                item["id"]
                for item in found
            )

            save_seen(seen)

            print(
                f"{sent} yeni ilan Telegram'a gönderildi."
            )

        except Exception as e:
            print(
                f"[TELEGRAM GÖNDERİM HATASI] {e}"
            )
            raise

    else:
        save_seen(seen)

        print(
            "Yeni uygun ilan bulunamadı."
        )


if __name__ == "__main__":
    main()
