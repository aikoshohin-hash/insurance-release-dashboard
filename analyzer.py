"""商品分析コメンタリーモジュール

リリースのタイトル・URLから商品の特徴を推定し、
コメントを自動付与する。
"""

import re
import logging

logger = logging.getLogger(__name__)


# ── 商品タイプ推定ルール ──

PRODUCT_TYPE_RULES = [
    # (キーワードリスト, 商品タイプ名, 解説コメント)
    (
        ["一時払終身", "一時払い終身"],
        "一時払終身保険",
        "相続対策・資産移転に活用される商品。死亡保険金の非課税枠を活用でき、"
        "銀行窓販の主力商品のひとつ。",
    ),
    (
        ["外貨建", "ドル建", "豪ドル建", "米ドル建"],
        "外貨建保険",
        "為替リスクがあるが円建より高い利回りが期待できる。"
        "銀行窓販では根強い人気がある一方、為替変動リスクの説明義務が重要。",
    ),
    (
        ["変額年金", "変額保険"],
        "変額保険/年金",
        "運用実績により保険金額が変動する投資性の高い商品。"
        "市場リスクを顧客が負うため、適合性確認が特に重要。",
    ),
    (
        ["定額年金", "一時払年金", "一時払い年金"],
        "定額年金保険",
        "元本保証型で安定志向の顧客に人気。"
        "予定利率の動向が商品性に大きく影響する。",
    ),
    (
        ["個人年金"],
        "個人年金保険",
        "老後資金準備の定番商品。個人年金保険料控除の対象となり税制メリットがある。",
    ),
    (
        ["養老保険"],
        "養老保険",
        "満期保険金と死亡保険金が同額の貯蓄型保険。"
        "法人向け福利厚生としても活用される。",
    ),
    (
        ["据置", "据え置き"],
        "据置型商品",
        "一定期間据え置くことで運用益を期待する商品。"
        "据置期間の選択が運用成果に影響する。",
    ),
    (
        ["ターゲット"],
        "ターゲット型商品",
        "目標値に到達すると自動的に円建に移行する機能付き商品。"
        "為替リスクを一定程度コントロールできる設計。",
    ),
    (
        ["定期支払", "定期払"],
        "定期支払型",
        "運用成果を定期的に受け取れる商品。"
        "年金受取前でも定期的なキャッシュフローが得られる。",
    ),
    (
        ["介護", "認知症"],
        "介護・認知症関連商品",
        "高齢化社会で需要増加中の保障商品。"
        "要介護認定で保険金が支払われ、介護費用に充当可能。",
    ),
    (
        ["がん", "三大疾病", "生活習慣病"],
        "疾病保障型商品",
        "特定疾病に対する保障を提供する商品。医療費の自己負担に備える。",
    ),
]

# ── アクション分類ルール ──

ACTION_RULES = [
    (["新発売", "新商品", "販売開始", "発売開始", "取扱開始"], "新商品発売",
     "新たに市場投入される商品。販売チャネルの動向やターゲット顧客層に注目。"),
    (["改定", "商品改定", "仕様変更"], "商品改定",
     "既存商品の仕様変更。改定内容（利率変更、保障内容変更等）を確認すること。"),
    (["予定利率"], "予定利率変更",
     "予定利率は貯蓄型保険の魅力を大きく左右する重要指標。市場金利動向との連動に注目。"),
    (["リニューアル", "バージョンアップ"], "商品リニューアル",
     "既存商品の大幅な刷新。競合他社の類似商品と比較して優位性を確認。"),
    (["提供停止", "販売停止", "取扱停止"], "販売停止",
     "商品の販売終了。駆け込み需要の可能性と代替商品の確認が必要。"),
    (["届出"], "届出・認可",
     "監督官庁への届出事項。今後の商品変更や販売開始の先行指標となる場合がある。"),
]

# ── 注目タグ ──

ATTENTION_TAGS = {
    "金融庁": "規制動向",
    "業務改善": "コンプライアンス",
    "行政処分": "規制対応",
    "協会": "業界動向",
    "提携": "アライアンス",
    "DX": "デジタル化",
    "AI": "テクノロジー",
    "アプリ": "デジタルサービス",
    "オンライン": "デジタル化",
    "ESG": "サステナビリティ",
    "SDGs": "サステナビリティ",
    "サステナ": "サステナビリティ",
}


def analyze_product_type(title: str) -> dict | None:
    """タイトルから商品タイプを推定

    Returns:
        {"type": "商品タイプ", "comment": "解説"} or None
    """
    for keywords, ptype, comment in PRODUCT_TYPE_RULES:
        if any(kw in title for kw in keywords):
            return {"type": ptype, "comment": comment}
    return None


def analyze_action(title: str) -> dict | None:
    """タイトルからアクション（新発売/改定等）を分類

    Returns:
        {"action": "アクション", "comment": "解説"} or None
    """
    for keywords, action, comment in ACTION_RULES:
        if any(kw in title for kw in keywords):
            return {"action": action, "comment": comment}
    return None


def detect_tags(title: str) -> list[str]:
    """注目タグを検出"""
    tags = []
    for keyword, tag in ATTENTION_TAGS.items():
        if keyword in title and tag not in tags:
            tags.append(tag)
    return tags


def generate_commentary(entry: dict) -> str:
    """リリースエントリに対する総合コメントを生成

    タイトルから商品タイプ・アクション・タグを推定し、
    読みやすいコメントを構築する。
    """
    title = entry.get("title", "")
    parts = []

    # アクション分類
    action_info = analyze_action(title)
    if action_info:
        parts.append(f"[{action_info['action']}] {action_info['comment']}")

    # 商品タイプ推定
    product_info = analyze_product_type(title)
    if product_info:
        parts.append(f"商品タイプ: {product_info['type']} -{product_info['comment']}")

    # 注目タグ
    tags = detect_tags(title)
    if tags:
        parts.append(f"注目: {', '.join(tags)}")

    # コメントなしの場合のデフォルト
    if not parts:
        # カテゴリに基づく一般コメント
        cat = entry.get("category", "")
        if cat == "A":
            parts.append("一般的なお知らせ。内容を確認の上、必要に応じて対応。")
        elif cat == "B":
            parts.append("ニュースリリース。事業活動に関する公式発表。")
        elif cat == "C":
            parts.append("プレスリリース。メディア向けの公式発表で注目度が高い。")
        else:
            parts.append("詳細はリンク先を確認してください。")

    return " / ".join(parts)


def analyze_entry(entry: dict) -> dict:
    """エントリに商品分析コメンタリーを付与

    以下のキーを追加:
      - commentary: 総合コメント
      - product_type: 商品タイプ（推定できた場合）
      - action_type: アクション分類
      - tags: 注目タグリスト
    """
    title = entry.get("title", "")

    # 各分析
    product_info = analyze_product_type(title)
    action_info = analyze_action(title)
    tags = detect_tags(title)
    commentary = generate_commentary(entry)

    entry["commentary"] = commentary
    entry["product_type"] = product_info["type"] if product_info else ""
    entry["action_type"] = action_info["action"] if action_info else ""
    entry["tags"] = tags

    return entry


def analyze_all(entries: list[dict]) -> list[dict]:
    """エントリリスト全体に商品分析を適用"""
    return [analyze_entry(e) for e in entries]


def analyze_categorized(categorized: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """カテゴリ別データ全体に商品分析を適用"""
    result = {}
    for cat, entries in categorized.items():
        result[cat] = analyze_all(entries)
    return result
