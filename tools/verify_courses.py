# -*- coding: utf-8 -*-
"""
课程链接验证脚本（一次性）
- 每门 B 站课调官方 API：取标题 / 播放量 / 视频数 / 发布时间，判断有效性与热度
- LeetCode studyplan 用 HTTP 检查
用法：在项目根目录  .venv\Scripts\python.exe tools\verify_courses.py
"""
import json
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "backend" / "data" / "agent_study.db"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36"}
TIMEOUT = 15

BILI_API = "https://api.bilibili.com/x/web-interface/view?bvid="


def http_get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", "replace")


def check_bilibili(url):
    m = re.search(r"(BV[0-9A-Za-z]{10})", url)
    if not m:
        return {"ok": False, "note": "URL 里没找到 BV 号"}
    bvid = m.group(1)
    try:
        data = json.loads(http_get(BILI_API + bvid))
    except Exception as e:
        return {"ok": False, "note": f"API 请求失败: {e.__class__.__name__}"}
    if data.get("code") != 0:
        return {"ok": False, "note": f"API code={data.get('code')} {data.get('message', '')}"}
    d = data["data"]
    stat = d.get("stat", {})
    return {
        "ok": True,
        "bvid": bvid,
        "title": d.get("title", ""),
        "views": stat.get("view", 0),
        "videos": stat.get("video", 1),
        "pubdate": d.get("pubdate", 0),
    }


def check_http(url):
    try:
        req = urllib.request.Request(url, headers=UA, method="GET")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return {"ok": resp.status < 400, "status": resp.status}
    except Exception as e:
        return {"ok": False, "note": f"HTTP 失败: {e.__class__.__name__}"}


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id,name,platform,url,teacher FROM courses ORDER BY id").fetchall()
    print(f"{'ID':<4}{'课程':<38}{'平台':<9}{'状态':<6}{'数据'}")
    print("-" * 100)
    for r in rows:
        name = r["name"] or "(无名称)"
        platform = r["platform"] or "?"
        if "bilibili.com" in (r["url"] or ""):
            res = check_bilibili(r["url"])
            if res.get("ok"):
                views = res["views"]
                if views >= 500_000:
                    hot = "✅ 热度高"
                elif views >= 100_000:
                    hot = "⚠️ 热度一般"
                else:
                    hot = "🔻 热度低"
                detail = f"「{res['title'][:30]}」 播放 {views/10000:.1f}万 / {res['videos']}P"
                print(f"{r['id']:<4}{name[:36]:<38}{platform:<9}{hot:<6}{detail}")
            else:
                print(f"{r['id']:<4}{name[:36]:<38}{platform:<9}{'❌ 失效':<6}{res['note']}")
        else:
            res = check_http(r["url"])
            if res.get("ok"):
                print(f"{r['id']:<4}{name[:36]:<38}{platform:<9}{'✅ HTTP '+str(res.get('status')):<6}{r['url'][:60]}")
            else:
                print(f"{r['id']:<4}{name[:36]:<38}{platform:<9}{'❌ 失效':<6}{res['note']}")
    conn.close()
    print("-" * 100)
    print("完成。")

if __name__ == "__main__":
    main()
