# CS2 饰品行情日报

每天一份的 CS2 饰品市场快照 —— **看趋势，不看实时报价。**

👉 https://faust-cloud.github.io/cs2-market/

---

## 为什么是「每天一次」

SteamDT 的接口有 IP 级频控，连续请求几次就会返回 `errorCode 108 当前环境异常`。
所以这个项目刻意做得极慢：**每天只发两个请求**，抓一次就停。

代价是数据不是实时的，好处是稳定 —— 用来观察一周、一个月的走势足够了，
而且不会给对方服务器添麻烦。

## 页面里有什么

**大盘指数** —— 当前点位、较昨日涨跌、连续记录的分时曲线拼成的走势图。

**当日变动** —— 跌幅前十 / 涨幅前十，含现价、涨跌幅、卖单数、求购价。
点任意一行即可加入关注。

**我的关注** —— 你点过的饰品，会显示「首次记录价 → 最新价」的变化和已记录天数。
关注列表存在浏览器 localStorage 里，不上传任何地方。

## 数据从哪来

SteamDT 网页端的公开接口：

| 接口 | 用途 |
|---|---|
| `GET /api/index/statistics/v1/summary` | 大盘指数与分时历史 |
| `POST /api/index/item/change/v1/list` | 当日涨跌榜（前 50 条） |

⚠️ **这是逆向出来的内部接口**，没有公开文档，也不是提供给第三方调用的。
它随时可能改、可能加验证、可能失效。这个项目按「随时会坏」的前提设计：
数据全部落盘成 JSON，接口哪天挂了，已经记录的日期依然能看。

## 为什么定时任务在本机跑，不在 GitHub Actions

一开始是挂在 Actions 上的，实测失败：

```
RuntimeError: /api/index/statistics/v1/summary 重试 3 次仍失败：
网络错误 <urlopen error _ssl.c:999: The handshake operation timed out>
```

GitHub 的 runner 在境外，到 `www.steamdt.com` 的 TLS 握手直接超时 —— 是地域限制，不是代码问题。
所以 `.github/workflows/daily.yml` 只保留了手动触发，定时抓取改在本机做。

### 本机定时（macOS launchd）

```bash
# 每天 08:10 抓一次并推送（把 TOKEN 换成自己的）
cat > ~/Library/LaunchAgents/com.faust.cs2market.plist <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.faust.cs2market</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string><string>REPO_PATH/fetch.py</string>
  </array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>10</integer></dict>
  <key>RunAtLoad</key><false/>
</dict></plist>
PLIST
launchctl load ~/Library/LaunchAgents/com.faust.cs2market.plist
```

抓完还需要把 `data/` 推上去（`publish.py` 里的推送部分可以复用）。

## 本地跑

```bash
# 抓一次（会写入 data/）
python3 fetch.py

# 只看结果不写文件
python3 fetch.py --dry
```

本地直接打开 `index.html` 会因为 `fetch` 读不了本地文件而空白，
起个静态服务器即可：

```bash
python3 -m http.server 8000
# http://localhost:8000
```

## 数据结构

```
data/
  2026-10-24.json   # 当天快照：大盘 + 50 条榜单
  index.json        # 有哪些天
```

单日文件：

```json
{
  "date": "2026-10-24",
  "fetchedAt": "2026-10-24T00:54:41+08:00",
  "index": { "value": 715.27, "diff": 0.24, "ratio": 0.0336, "points": [[ts, 715.09], ...] },
  "items": [
    { "id": "553489656", "name": "AK-47 | 幻影破坏者 (久经沙场)",
      "price": 32.9, "prev": 33.0, "ratio": -0.3, "sell": 904, "buy": 33.0 }
  ]
}
```

## License

MIT
