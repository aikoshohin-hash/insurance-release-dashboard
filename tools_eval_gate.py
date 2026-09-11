"""関連性ゲートの効きを実データで確認する検証スクリプト（開発用）"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from relevance import classify, TIER_PRODUCT, TIER_PERIPHERAL, TIER_EXCLUDE

path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\DFLDXPT\AppData\Local\Temp\entries.json"
entries = json.load(open(path, encoding="utf-8"))

buckets = {TIER_PRODUCT: [], TIER_PERIPHERAL: [], TIER_EXCLUDE: []}
for e in entries:
    r = classify(e["title"])
    e["_rel"] = r
    buckets[r["tier"]].append(e)

print(f"入力 {len(entries)}件")
for tier in (TIER_PRODUCT, TIER_PERIPHERAL, TIER_EXCLUDE):
    print(f"  {tier:11s} {len(buckets[tier]):3d}件")
print()

for tier in (TIER_PRODUCT, TIER_PERIPHERAL, TIER_EXCLUDE):
    print("=" * 100)
    print(f" {tier}  ({len(buckets[tier])}件)")
    print("=" * 100)
    for e in sorted(buckets[tier], key=lambda x: x["date"]):
        r = e["_rel"]
        tag = r.get("action") or r.get("peri_kind") or r.get("noise_kind")
        print(f"{e['date']} [{tag:14s}] {e['company'][:7]:8s} {e['title'][:62]}")
    print()
