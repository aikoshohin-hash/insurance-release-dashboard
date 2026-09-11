"""エンリッチャの効きを実データで確認する検証スクリプト（開発用）"""
import json
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(level=logging.WARNING)

from relevance import classify, TIER_PRODUCT
from enricher import enrich_entries, format_enrich_report

entries = json.load(open(sys.argv[1], encoding="utf-8"))
prod = [e for e in entries if classify(e["title"])["tier"] == TIER_PRODUCT]

n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
target = sorted(prod, key=lambda x: x["date"], reverse=True)[:n]
print(f"本線 {len(prod)}件 のうち直近 {len(target)}件を取得します\n")

target, stats = enrich_entries(target, use_cache=True)
print(format_enrich_report(stats))
print()

for e in target:
    f = e["facts"]
    print("-" * 96)
    print(f"{e['date']} {e['company']}  [{e.get('body_status')}]")
    print(f"  {e['title'][:78]}")
    print(f"  URL: {e.get('url','')[:96]}")
    bits = []
    if f["product_names"]:  bits.append("商品名=" + "/".join(f["product_names"][:2]))
    if f["product_kind"]:   bits.append("種別=" + f["product_kind"])
    if f["payment"]:        bits.append("払方=" + f["payment"])
    if f["currencies"]:     bits.append("通貨=" + ",".join(f["currencies"]))
    if f["rates"]:          bits.append("利率=" + ",".join(f"{r['kind']}{r['value']}%" for r in f["rates"][:3]))
    if f["sale_start"]:     bits.append("販売開始=" + f["sale_start"])
    if f["channels"]:       bits.append("チャネル=" + ",".join(f["channels"]))
    if f["banks"]:          bits.append("金融機関=" + ",".join(f["banks"][:4]))
    print("  " + (" | ".join(bits) if bits else "(抽出ゼロ)"))
    for ex in f["excerpts"][:1]:
        print(f"    根拠: {ex}")
