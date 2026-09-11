"""商品分析コメンタリー v4 — 事実を書く層

【v3 の何が問題だったか】
    タイトルにキーワードが当たると、あらかじめ書いておいた教科書的な解説文を
    そのまま貼っていた。例:
      「外貨建保険 - 為替リスクがあるが円建より高い利回りが期待できる。」
    どのリリースにも同じ文が付くため、読んでも **そのリリース固有の情報が
    ひとつも増えない**。分析ではなく飾りだった。

【v4 の考え方】
    enricher が本文/PDF から取った事実だけを書く。書くことが無ければ書かない。
    コメンタリーは3行構成:

      事実:   米ドル・豪ドル建 / 一時払終身 / 積立利率 2.85% /
              銀行窓販（みずほ銀行）/ 2026/07/01 販売開始
      含意:   （その事実から言えることがある場合のみ）
      比較:   （同種商品の中での利率の位置。データが2件以上ある場合のみ）

    一般論しか書けないときは沈黙する。それが v3 との一番の違い。
"""

from __future__ import annotations

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  含意 — 「事実の組み合わせ」に対してのみ発火する
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  条件を満たしたときだけ1文返す。汎用の解説文は置かない。

def _implications(entry: dict, facts: dict) -> list[str]:
    out: list[str] = []
    action = entry.get("action_type", "")

    single = facts.get("is_single_premium")
    bank   = facts.get("is_bank_channel")
    banks  = facts.get("banks") or []

    if single and bank and action in ("新商品発売", "販売開始", "取扱開始"):
        out.append("一時払×銀行窓販の本丸。銀行の棚の入れ替えに直結する。")
    elif bank and action in ("販売開始", "取扱開始") and banks:
        out.append(f"チャネル拡大（{len(banks)}機関）。商品自体は既存で、棚を広げる動き。")

    if action == "利率改定":
        out.append("予定利率は貯蓄性商品の競争力を直接動かす。他社の同時期改定と並べて見る。")
    elif action == "料率改定":
        out.append("料率改定は保障性商品の価格改定。標準生命表・金利環境の反映を確認。")

    if action == "販売停止":
        out.append("駆け込み需要と代替商品の有無を確認する必要がある。")

    if facts.get("is_variable"):
        out.append("投資性商品。特別勘定のラインナップが実質的な競争軸。")

    return out


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  事実行の組み立て
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _fact_line(facts: dict) -> str:
    if not facts:
        return ""
    bits: list[str] = []

    if facts.get("product_names"):
        bits.append("／".join(facts["product_names"][:2]))
    if facts.get("product_kind"):
        bits.append(facts["product_kind"])
    if facts.get("currencies"):
        bits.append("・".join(facts["currencies"]) + "建")
    # 改定は「いくらから いくらへ」が本体。単発の数値より先に出す。
    rc = facts.get("rate_change")
    if rc:
        bits.append(f"{rc['from']}% → {rc['to']}%（{rc['direction']}）")
    elif facts.get("rates"):
        r = facts["rates"][0]
        extra = f"ほか{len(facts['rates']) - 1}件" if len(facts["rates"]) > 1 else ""
        bits.append(f"{r['kind']}{r['value']}%{extra}")
    if facts.get("channels"):
        ch = "・".join(facts["channels"])
        banks = facts.get("banks") or []
        if banks:
            shown = "、".join(banks[:3])
            more  = f"ほか{len(banks) - 3}機関" if len(banks) > 3 else ""
            ch += f"（{shown}{more}）"
        bits.append(ch)
    if facts.get("sale_start"):
        bits.append(f"{facts['sale_start']}販売開始")

    return " ｜ ".join(bits)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  利率の横比較
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _build_rate_index(all_entries: list[dict]) -> dict:
    """(商品種別, 利率種別) ごとに [(値, 会社名)] を集める。"""
    idx: dict[tuple[str, str], list[tuple[float, str]]] = defaultdict(list)
    for e in all_entries:
        facts = e.get("facts") or {}
        kind  = facts.get("product_kind") or ""
        if not kind:
            continue
        for r in facts.get("rates") or []:
            idx[(kind, r["kind"])].append((r["value"], e.get("company", "")))
    return idx


def _comparison(entry: dict, facts: dict, idx: dict) -> str:
    """同種商品の中でのこの利率の位置を1文で返す。比較対象が無ければ空。"""
    kind = facts.get("product_kind") or ""
    if not kind or not facts.get("rates"):
        return ""

    r      = facts["rates"][0]
    peers  = idx.get((kind, r["kind"]), [])
    others = [v for v, c in peers if c != entry.get("company", "")]
    if not others:
        return ""

    hi, lo = max(others), min(others)
    if r["value"] > hi:
        return f"{kind}の{r['kind']}としては収集分で最も高い（他社最高 {hi}%）。"
    if r["value"] < lo:
        return f"{kind}の{r['kind']}としては収集分で最も低い（他社最低 {lo}%）。"
    return f"{kind}の{r['kind']}の他社レンジ {lo}〜{hi}% の中。"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  公開API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def analyze_entry(entry: dict, rate_index: dict | None = None) -> dict:
    """エントリに事実ベースのコメンタリーを付与する。

    付与するキー:
        fact_line    事実の要約行（本文から取れたものだけ）
        implication  含意（言えることがある場合のみ）
        comparison   利率の横比較（比較対象がある場合のみ）
        commentary   上記を連結した表示用文字列
        product_type 商品種別（v3互換のキー名）
    """
    facts = entry.get("facts") or {}

    fact_line  = _fact_line(facts)
    implies    = _implications(entry, facts)
    comparison = _comparison(entry, facts, rate_index or {})

    entry["fact_line"]   = fact_line
    entry["implication"] = " ".join(implies)
    entry["comparison"]  = comparison
    entry["product_type"] = facts.get("product_kind", "")
    entry["tags"] = list(entry.get("focus_labels") or [])

    parts = [p for p in (fact_line, entry["implication"], comparison) if p]
    if not parts:
        # 何も取れなかったことを取り繕わない。取れなかったと書く。
        status = entry.get("body_status", "")
        if status in ("html", "pdf"):
            entry["commentary"] = "本文は取得したが、商品情報の抽出に至らず。"
        elif status:
            entry["commentary"] = f"本文を取得できず（{status}）。タイトルのみで判定。"
        else:
            entry["commentary"] = "本文未取得。タイトルのみで判定。"
    else:
        entry["commentary"] = " / ".join(parts)

    return entry


def analyze_all(entries: list[dict], rate_index: dict | None = None) -> list[dict]:
    idx = rate_index if rate_index is not None else _build_rate_index(entries)
    return [analyze_entry(e, idx) for e in entries]


def analyze_categorized(categorized: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """カテゴリ別データ全体に分析を適用する。

    利率の横比較のため、まず全カテゴリを串刺しで見て利率インデックスを作る。
    """
    all_entries = [e for entries in categorized.values() for e in entries]
    idx = _build_rate_index(all_entries)
    return {cat: analyze_all(entries, idx) for cat, entries in categorized.items()}
