"""ニュース価値スコアリング & ランキング v4

【v3 の何が問題だったか】
    score = keyword + recency + category + brand + ichiji  （全て加点）

    加点しか無いため、中身の無いリリースでも
      ブランド14 + カテゴリ15 + 鮮度13 = 42点
    の下駄を履き、「創作四字熟語 募集開始」が B ランクに並んでいた。
    S ランクは113件中1件しか出ず、ランクが選別として機能していなかった。

【v4 の考え方】
    1. 採点の前に relevance.py の 3値ゲートを通す。
       EXCLUDE は採点対象にすらしない（除外ログに落とす）。
    2. 点数の主軸は「商品に何が起きたか」(action) に置く。
       ブランドと鮮度は **補助** に降格させ、合計でも20点に届かないようにする。
    3. 「一時払い・銀行窓販」という関心軸を独立した focus_score として持つ。
       銀行窓販の商品ウォッチという用途では、これが実質的な選別軸になる。
    4. 本文を読めたか（利率の数値を掴めたか）を evidence として加点する。
       裏の取れたニュースを上に出すため。

    配点:
        action    0-40   商品アクション（新商品発売40 / 販売開始38 / 利率改定36 …）
        focus     0-25   一時払10 + 銀行窓販8 + 外貨4 + 変額3
        evidence  0-15   本文取得5 + 利率数値6 + 商品名2 + 販売開始日2
        recency   0-12   鮮度
        brand     0- 8   会社ブランド
        ─────────────
        合計      0-100
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

from companies import get_brand_scores
from relevance import classify, TIER_PRODUCT, TIER_PERIPHERAL, TIER_EXCLUDE

logger = logging.getLogger(__name__)

COMPANY_BRAND_SCORES = get_brand_scores()

# 周辺(PERIPHERAL)は商品そのものではないため、Bランクの上限で頭を押さえる。
# これをしないと大手の事務サービス告知が本線の商品リリースを押しのける。
PERIPHERAL_CAP = 44

# ランク閾値
RANK_THRESHOLDS = [(75, "S"), (60, "A"), (45, "B"), (30, "C")]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  各軸
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _parse_date(date_str: str) -> date | None:
    if not date_str:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", date_str)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def score_recency(date_str: str) -> float:
    """鮮度スコア（0〜12）。v3の15点から降格させ、古い商品ニュースが
    新しい広報ニュースに負けないようにする。"""
    d = _parse_date(date_str)
    if d is None:
        return 3.0
    delta = (date.today() - d).days
    if delta <= 7:
        return 12.0
    if delta <= 14:
        return 10.0
    if delta <= 30:
        return 8.0
    if delta <= 60:
        return 5.0
    if delta <= 90:
        return 3.0
    return 1.0


def score_brand(company: str) -> float:
    """ブランドスコア（0〜8）。v3の15点から降格。"""
    raw = COMPANY_BRAND_SCORES.get(company, 7)
    return round(raw / 15.0 * 8.0, 1)


def score_focus(facts: dict) -> tuple[float, list[str]]:
    """関心軸スコア（0〜25）— 一時払い・銀行窓販の商品ウォッチとしての重み。

    Returns:
        (点数, 効いた軸のラベル)
    """
    if not facts:
        return 0.0, []
    total = 0.0
    labels: list[str] = []
    if facts.get("is_single_premium"):
        total += 10.0
        labels.append("一時払")
    if facts.get("is_bank_channel"):
        total += 8.0
        labels.append("銀行窓販")
    if facts.get("is_fx"):
        total += 4.0
        labels.append("外貨建")
    if facts.get("is_variable"):
        total += 3.0
        labels.append("変額")
    return min(25.0, total), labels


def score_evidence(entry: dict, facts: dict) -> tuple[float, list[str]]:
    """裏取りスコア（0〜15）— 本文まで読めているものを上に出す。"""
    if not facts:
        return 0.0, []
    total = 0.0
    labels: list[str] = []
    if entry.get("body_status") in ("html", "pdf"):
        total += 5.0
        labels.append("本文取得")
    if facts.get("rate_change"):
        total += 6.0
        labels.append("改定幅")
    elif facts.get("rates"):
        total += 6.0
        labels.append("利率数値")
    if facts.get("product_names"):
        total += 2.0
        labels.append("商品名")
    if facts.get("sale_start"):
        total += 2.0
        labels.append("販売開始日")
    return min(15.0, total), labels


def estimate_popularity(entry: dict, focus: float, action: float) -> int:
    """注目度（★1〜5）。v3 のような独自ロジックを持たず、
    本体スコアの構成要素から素直に導く（二重基準を作らないため）。"""
    raw = action / 40.0 * 3.0 + focus / 25.0 * 2.0
    return min(5, max(1, round(raw)))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  総合
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def compute_score(entry: dict) -> dict:
    """エントリに総合スコアとランクを付与する。

    entry には事前に以下が入っている前提:
        entry["relevance"] : relevance.classify() の結果（無ければここで算出）
        entry["facts"]     : enricher.extract_facts() の結果（無ければ空扱い）
    """
    rel   = entry.get("relevance") or classify(entry.get("title", ""))
    facts = entry.get("facts") or {}

    s_action           = float(rel.get("action_score", 0))
    s_focus, f_labels  = score_focus(facts)
    s_evid,  e_labels  = score_evidence(entry, facts)
    s_recency          = score_recency(entry.get("date", ""))
    s_brand            = score_brand(entry.get("company", ""))

    total = s_action + s_focus + s_evid + s_recency + s_brand

    # 周辺は頭を押さえる
    if rel.get("tier") == TIER_PERIPHERAL:
        total = min(total, PERIPHERAL_CAP)

    total = round(min(100.0, total), 1)

    rank = "D"
    for threshold, label in RANK_THRESHOLDS:
        if total >= threshold:
            rank = label
            break

    entry["score"] = total
    entry["score_detail"] = {
        "action":   round(s_action, 1),
        "focus":    round(s_focus, 1),
        "evidence": round(s_evid, 1),
        "recency":  round(s_recency, 1),
        "brand":    s_brand,
    }
    entry["rank_label"]  = rank
    entry["tier"]        = rel.get("tier", TIER_PRODUCT)
    entry["action_type"] = rel.get("action", "")
    entry["focus_labels"]    = f_labels
    entry["evidence_labels"] = e_labels
    entry["popularity"]  = estimate_popularity(entry, s_focus, s_action)
    return entry


def score_and_rank(entries: list[dict]) -> list[dict]:
    """スコア付与 → 本線優先・スコア降順で並べる。"""
    scored = [compute_score(e) for e in entries]
    # 本線(PRODUCT)を常に周辺(PERIPHERAL)より上に置く
    tier_key = {TIER_PRODUCT: 0, TIER_PERIPHERAL: 1, TIER_EXCLUDE: 2}
    scored.sort(key=lambda x: (tier_key.get(x.get("tier"), 2), -x.get("score", 0)))
    for i, e in enumerate(scored, 1):
        e["rank"] = i
    return scored


def score_categorized(categorized: dict[str, list[dict]]) -> dict[str, list[dict]]:
    return {cat: score_and_rank(entries) for cat, entries in categorized.items()}
