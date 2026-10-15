import json, time, urllib.request

API = "https://api-eapp.emart.com/promotion/api/v1/sfmarket/event/detail?eventId={}"
H = {"accept": "application/json", "origin": "https://www.starfieldmarket.com",
     "referer": "https://www.starfieldmarket.com/", "user-agent": "Mozilla/5.0"}

for i in range(1, 1001):
    try:
        req = urllib.request.Request(API.format(i), headers=H)
        with urllib.request.urlopen(req, timeout=10) as r:
            d = (json.loads(r.read().decode("utf-8")).get("data") or {}).get("eventDetail")
    except Exception:
        d = None
    time.sleep(0.2)
    if d and d.get("branchNm") == "스타필드마켓 동탄점":
        print(i, d.get("eventTitle"), "| 노출:", d.get("eventDispYn"), "| 종료:", d.get("eventDispEdate"))
