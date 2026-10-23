#!/usr/bin/env python3
"""抓取一次 SteamDT 公开行情快照，写入 data/YYYY-MM-DD.json

只用两个请求：
  1. GET  /api/index/statistics/v1/summary   —— 大盘指数 + 分时历史
  2. POST /api/index/item/change/v1/list     —— 当日涨跌榜（前 100）

设计原则：极低频、只读。对方有 IP 级频控（连续多次会返回 errorCode 108），
所以每天只跑一次、只发两个请求。

用法：
  python3 fetch.py            # 抓取并写入 data/
  python3 fetch.py --dry      # 只抓取并打印摘要，不写文件
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

BASE = "https://www.steamdt.com"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Referer": BASE + "/",
    "Accept": "application/json, text/plain, */*",
}
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
TZ = timezone(timedelta(hours=8))          # 北京时间


def call(path, body=None, method="GET", retries=3):
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(HEADERS)
    if data:
        headers["Content-Type"] = "application/json"
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                payload = json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = f"网络错误 {e}"
            time.sleep(3 * (attempt + 1))
            continue
        if payload.get("success"):
            return payload["data"]
        # errorCode 108 = 频控/环境异常，退避后重试
        last = f"{payload.get('errorCode')} {payload.get('errorMsg')}"
        if payload.get("errorCode") == 108:
            time.sleep(10 * (attempt + 1))
            continue
        raise RuntimeError(f"{path} 失败：{last}")
    raise RuntimeError(f"{path} 重试 {retries} 次仍失败：{last}")


def main():
    dry = "--dry" in sys.argv
    now = datetime.now(TZ)
    day = now.strftime("%Y-%m-%d")

    summary = call("/api/index/statistics/v1/summary")
    trend = summary.get("historyMarketIndexList") or []
    index = {
        "value": summary.get("broadMarketIndex"),
        "diff": summary.get("diffYesterday"),
        "ratio": summary.get("diffYesterdayRatio"),
        # [时间戳, 指数] → 只留最近 24 小时，控制文件体积
        "points": [[int(t), round(float(v), 2)] for t, v in trend][-72:],
    }

    time.sleep(2)   # 两个请求之间稍作停顿，别让对方觉得被扫
    rank = call("/api/index/item/change/v1/list", body={"pageNum": 1, "pageSize": 100}, method="POST")
    rows = rank.get("list") or []

    items = []
    for r in rows:
        price, prev = r.get("sellPrice"), r.get("beforeSellPrice")
        if price is None:
            continue
        ratio = None
        if prev:
            ratio = round((price - prev) / prev * 100, 2)
        items.append({
            "id": r.get("itemId"),
            "name": r.get("name"),
            "img": r.get("imageUrl"),
            "link": r.get("link"),
            "price": price,
            "prev": prev,
            "ratio": ratio,
            "sell": r.get("sellCount"),
            "sellPrev": r.get("beforeSellCount"),
            "buy": r.get("purchasePrice"),
            "buyCount": r.get("purchaseCount"),
        })

    snapshot = {
        "date": day,
        "fetchedAt": now.isoformat(timespec="seconds"),
        "index": index,
        "items": items,
    }

    print(f"日期 {day}  指数 {index['value']}  ({index['ratio']}%)  榜单 {len(items)} 条")
    if items:
        items_sorted = sorted(items, key=lambda x: x["ratio"] if x["ratio"] is not None else 0)
        print("  跌最多：", items_sorted[0]["name"], items_sorted[0]["ratio"], "%")
        print("  涨最多：", items_sorted[-1]["name"], items_sorted[-1]["ratio"], "%")

    if dry:
        print("（dry-run，未写文件）")
        return 0

    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, day + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=0)

    # 维护清单：页面靠它知道有哪些天
    manifest_path = os.path.join(DATA, "index.json")
    manifest = {"days": []}
    if os.path.exists(manifest_path):
        try:
            manifest = json.load(open(manifest_path, encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    days = set(manifest.get("days") or [])
    days.add(day)
    manifest = {"days": sorted(days), "updated": now.isoformat(timespec="seconds")}
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=0)

    print(f"已写入 {path} 与 index.json（累计 {len(days)} 天）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
