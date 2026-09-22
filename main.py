import json, os, re, hashlib
from datetime import datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

CONFIG = json.load(open("config.json", encoding="utf-8"))
SEEN_FILE = "seen.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; KamuIlanTakip/1.0; +https://github.com/)"
}

def norm(s):
    return re.sub(r"\s+", " ", (s or "").lower()).strip()

def load_seen():
    try:
        return set(json.load(open(SEEN_FILE, encoding="utf-8")))
    except Exception:
        return set()

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen)[-5000:], f, ensure_ascii=False, indent=2)

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    return r.text

def make_id(title, url):
    return hashlib.sha256((title.strip() + "|" + url).encode("utf-8")).hexdigest()[:20]

def classify(text):
    t = norm(text)

    # KPSS'siz olduğu açıkça belirtilmiyorsa yanlış bildirimleri azaltmak için dışarıda bırak.
    no_kpss = any(x in t for x in CONFIG["no_kpss_terms"])
    if not no_kpss:
        return None

    education = any(x in t for x in CONFIG["education_terms"])
    if not education:
        return None

    permanent = any(x in t for x in CONFIG["permanent_terms"])
    contract = any(x in t for x in CONFIG["contract_terms"])

    if permanent:
        status = "Kadrolu/daimi"
    elif contract:
        status = "Sözleşmeli"
    else:
        status = "Belirtilmemiş"

    return status

def extract_links(source):
    html = fetch(source["url"])
    soup = BeautifulSoup(html, "lxml")
    out = []

    # Genel amaçlı bağlantı taraması. JS ile oluşturulan içerikler bu aşamada görülemeyebilir.
    for a in soup.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        href = urljoin(source["url"], a["href"])
        if len(title) < 8:
            continue
        if href.startswith("javascript:") or href.startswith("mailto:"):
            continue
        out.append((title, href))

    # Sayfanın kendisini de aday olarak tut.
    if soup.get_text(" ", strip=True):
        out.append((source["name"], source["url"]))

    # Aynı bağlantıları kaldır.
    seen = set()
    unique = []
    for x in out:
        if x[1] not in seen:
            seen.add(x[1])
            unique.append(x)
    return unique

def inspect_candidate(title, url):
    try:
        html = fetch(url)
    except Exception:
        return None

    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)
    status = classify(title + " " + text)
    if not status:
        return None

    # KPSS zorunluluğu açıkça belirtilmiş ilanlarda yanlış eşleşmeyi azalt.
    t = norm(text)
    if not any(x in t for x in CONFIG["no_kpss_terms"]):
        return None

    return {
        "title": title.strip(),
        "url": url,
        "status": status,
        "text": text[:6000],
    }

def city_from(text):
    t = norm(text)
    if "ankara" in t:
        return "Ankara"
    cities = [
        "adana","adıyaman","afyonkarahisar","ağrı","amasya","antalya","artvin",
        "aydın","balıkesir","bilecik","bingöl","bitlis","bolu","burdur","bursa",
        "çanakkale","çankırı","çorum","denizli","diyarbakır","edirne","elazığ",
        "erzincan","erzurum","eskişehir","gaziantep","giresun","gümüşhane",
        "hakkari","hatay","ısparta","mersin","istanbul","izmir","kars","kastamonu",
        "kayseri","kırklareli","kırşehir","kocaeli","konya","kütahya","malatya",
        "manisa","mardin","muğla","muş","nevşehir","niğde","ordu","rize","sakarya",
        "samsun","siirt","sinop","sivas","şanlıurfa","şırnak","tekirdağ","tokat",
        "trabzon","tunceli","uşak","van","yalova","yozgat","zonguldak","aksaray",
        "bayburt","karaman","kırıkkale","batman","bartın","ardahan","ığdır",
        "osmaniye","düzce"
    ]
    for c in cities:
        if c in t:
            return c.title()
    return "Türkiye geneli / belirtilmemiş"

def send_telegram(items):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Telegram secret'ları eksik.")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for item in items:
        city = city_from(item["text"])
        prefix = "⭐ " if item["status"] == "Kadrolu/daimi" else ""
        msg = (
            f"{prefix}<b>Yeni kamu ilanı</b>\n\n"
            f"<b>İlan:</b> {item['title']}\n"
            f"<b>Yer:</b> {city}\n"
            f"<b>Statü:</b> {item['status']}\n"
            f"<b>Filtre:</b> KPSS şartı açıkça aranmayacak + önlisans/lisans\n\n"
            f"<a href=\"{item['url']}\">İlana git</a>"
        )
        r = requests.post(url, data={
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }, timeout=20)
        r.raise_for_status()

def main():
    seen = load_seen()
    found = []

    for source in CONFIG["sources"]:
        try:
            links = extract_links(source)
        except Exception as e:
            print(f"[KAYNAK HATASI] {source['name']}: {e}")
            continue

        # Kaynak sayfalarında çok fazla link olabilir; ilk aşamada ilan/personel/kadro başlıklı
        # bağlantıları öne alıyoruz.
        priority = []
        normal = []
        for title, url in links:
            if re.search(r"personel|memur|ilan|kadro|alım|işçi|sözleşmeli|uzman|büro|mühendis|tekniker|teknisyen", norm(title)):
                priority.append((title, url))
            else:
                normal.append((title, url))

        candidates = priority + normal[:30]
        for title, url in candidates[:80]:
            item = inspect_candidate(title, url)
            if item:
                item["id"] = make_id(item["title"], item["url"])
                if item["id"] not in seen:
                    found.append(item)

    # Ankara önce, sonra kadrolu, sonra başlık.
    found.sort(key=lambda x: (
        0 if city_from(x["text"]) == "Ankara" else 1,
        0 if x["status"] == "Kadrolu/daimi" else 1,
        norm(x["title"])
    ))

    if found:
        send_telegram(found)
        seen.update(x["id"] for x in found)
        save_seen(seen)
        print(f"{len(found)} yeni ilan Telegram'a gönderildi.")
    else:
        save_seen(seen)
        print("Yeni uygun ilan bulunamadı.")

if __name__ == "__main__":
    main()
