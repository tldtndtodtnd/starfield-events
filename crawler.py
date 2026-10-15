import json
import re
import time
import html
import urllib.request
import http.cookiejar
from datetime import datetime

NOW = datetime.now()


def get_json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read().decode("utf-8"))


def parse_dt(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def clean(t):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", t or "")).split())


# ---------------------------------------------------------------
# 1) 스타필드 마켓 동탄점
# ---------------------------------------------------------------
DT_API = "https://api-eapp.emart.com/promotion/api/v1/sfmarket/event/detail?eventId={}"
DT_HEADERS = {
    "accept": "application/json",
    "origin": "https://www.starfieldmarket.com",
    "referer": "https://www.starfieldmarket.com/",
    "user-agent": "Mozilla/5.0",
}
DT_BRANCH_ID = "1085"
DT_MAX_ID = 1000
DT_STOP_AFTER_MISSES = 150


def dt_fetch(event_id):
    try:
        body = get_json(DT_API.format(event_id), DT_HEADERS)
        return (body.get("data") or {}).get("eventDetail")
    except Exception:
        return None


def dt_parse_shows(conts):
    shows = []
    for chunk in (conts or "").split('<b class="font-red">')[1:]:
        category = clean(chunk.split("</b>")[0])

        title = ""
        for m in re.finditer(r'<b style="font-size: x-large;">(.*?)</b>', chunk, re.S):
            if clean(m.group(1)):
                title = clean(m.group(1))
                break

        d = re.search(r"공연일자</b>\s*:\s*([^<]+)", chunk)
        t = re.search(r"공연시간</b>\s*:\s*([^<]+)", chunk)
        img = re.search(r'<img[^>]+src="([^"]+)"', chunk)
        if not (title and d):
            continue

        date_text = html.unescape(d.group(1)).strip()
        days = []
        for mo, da in re.findall(r"(\d{1,2})/(\d{1,2})", date_text):
            try:
                days.append(datetime(NOW.year, int(mo), int(da), 23, 59, 59))
            except ValueError:
                pass
        if not days:
            continue

        shows.append({
            "category": category,
            "title": title,
            "date": date_text,
            "time": html.unescape(t.group(1)).strip() if t else "",
            "image": img.group(1) if img else None,
            "end": max(days),
        })
    return shows


def crawl_dongtan():
    cards = []
    misses = 0
    for i in range(1, DT_MAX_ID + 1):
        d = dt_fetch(i)
        time.sleep(0.3)
        if not d:
            misses += 1
            if misses >= DT_STOP_AFTER_MISSES:
                break
            continue
        misses = 0

        if d.get("branchId") != DT_BRANCH_ID:
            continue

        end = parse_dt(d.get("eventDispEdate"))
        if d.get("eventDispYn") != "Y" or (end and end < NOW):
            continue

        url = f"https://www.starfieldmarket.com/event/detail/{d['eventId']}?isApp=false&branch={d.get('branchId')}"
        shows = dt_parse_shows(d.get("eventConts"))

        if shows:
            for n, s in enumerate(shows):
                if s["end"] < NOW:
                    continue
                term = " · ".join(x for x in [s["date"], s["time"], s["category"]] if x)
                cards.append({
                    "id": f"dongtan-{d['eventId']}-{n}",
                    "branchId": DT_BRANCH_ID,
                    "branch": "동탄점",
                    "title": s["title"],
                    "image": s["image"] or d.get("eventFileUrl"),
                    "term": term,
                    "endDate": s["end"].strftime("%Y-%m-%d %H:%M:%S"),
                    "url": url,
                })
                print("[동탄]", s["title"], "|", term)
        else:
            cards.append({
                "id": f"dongtan-{d['eventId']}",
                "branchId": DT_BRANCH_ID,
                "branch": "동탄점",
                "title": d.get("eventTitle"),
                "image": d.get("eventFileUrl"),
                "term": d.get("eventTerm"),
                "endDate": d.get("eventDispEdate"),
                "url": url,
            })
            print("[동탄]", d.get("eventTitle"), "(본문 파싱 실패, 게시물 단위)")
    return cards


# ---------------------------------------------------------------
# 2) 스타필드 수원
# ---------------------------------------------------------------
SW_API = "https://www.starfield.co.kr/api/suwon/event/eventList.do?evt_gbn=event&lang=ko&pageIndex={}"
SW_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "referer": "https://www.starfield.co.kr/suwon/eventBenefit/events",
    "user-agent": "Mozilla/5.0",
}


SW_PAGE = "https://www.starfield.co.kr/suwon/eventBenefit/events"
SW_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"


def sw_open_session():
    """목록 페이지를 먼저 열어서 쿠키를 받아 둔다."""
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.open(urllib.request.Request(
        SW_PAGE, headers={"user-agent": SW_UA, "accept-language": "ko-KR,ko;q=0.9"}
    ), timeout=10).read()
    return opener


def sw_get(opener, page):
    req = urllib.request.Request(SW_API.format(page), headers={
        "user-agent": SW_UA,
        "accept": "application/json, text/plain, */*",
        "accept-language": "ko-KR,ko;q=0.9",
        "referer": SW_PAGE,
        "x-requested-with": "XMLHttpRequest",
    })
    return json.loads(opener.open(req, timeout=10).read().decode("utf-8"))


def crawl_suwon():
    cards = []
    opener = sw_open_session()
    page = 1
    while True:
        body = sw_get(opener, page)

        for e in body.get("data") or []:
            if e.get("evt_open_yn") != "Y":
                continue

            post_end = parse_dt(e.get("evt_post_end_dt"))
            if post_end and post_end < NOW:
                continue

            title = clean(re.sub(r"<br\s*/?>", " ", e.get("evt_titl") or ""))

            image = e.get("web_list_open_img_uri")
            if not image and e.get("img_uri"):
                image = "https://www.starfield.co.kr" + e["img_uri"]

            # "10.3(토), 10.10(토), ..." 에서 날짜를 뽑아 남은 일정만 남긴다
            date_text = e.get("evtStrtDtTxt") or ""
            found = re.findall(r"(\d{1,2})\.(\d{1,2})\(([^)]*)\)", date_text)
            upcoming = []
            for mo, da, wd in found:
                try:
                    dt = datetime(NOW.year, int(mo), int(da), 23, 59, 59)
                except ValueError:
                    continue
                if dt >= NOW:
                    upcoming.append((dt, f"{int(mo)}/{int(da)}({wd})"))

            if found and not upcoming:
                continue  # 날짜가 전부 지났으면 제외

            if upcoming:
                upcoming.sort()
                term = "남은 일정 " + " · ".join(label for _, label in upcoming)
                end_date = upcoming[0][0].strftime("%Y-%m-%d %H:%M:%S")  # 가장 가까운 날짜
            else:
                term = date_text
                end_date = e.get("evt_post_end_dt") or "2099-12-31 23:59:59"

            cards.append({
                "id": f"suwon-{e['evt_seq']}",
                "branchId": "suwon",
                "branch": "스타필드 수원",
                "title": title,
                "image": image,
                "term": term,
                "endDate": end_date,
                "url": f"https://www.starfield.co.kr/suwon/eventBenefit/events/{e['evt_seq']}",
            })
            print("[수원]", title, "|", term)

        total = (body.get("paginationInfo") or {}).get("totalPageCount") or 1
        if page >= total:
            break
        page += 1
        time.sleep(0.3)
    return cards


# ---------------------------------------------------------------
# 실행
# ---------------------------------------------------------------
all_cards = []

try:
    all_cards += crawl_dongtan()
except Exception as ex:
    print("동탄 수집 실패:", ex)

try:
    all_cards += crawl_suwon()
except Exception as ex:
    print("수원 수집 실패:", ex)

with open("events.json", "w", encoding="utf-8") as f:
    json.dump(all_cards, f, ensure_ascii=False, indent=2)

print(f"\n총 {len(all_cards)}개 저장 완료 -> events.json")