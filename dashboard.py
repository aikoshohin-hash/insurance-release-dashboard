"""保険リリース ダッシュボード（Streamlit）

使い方:
  streamlit run dashboard.py

機能:
  - カテゴリ別リリース一覧（スコア順）
  - スコアリング・ランキング表示
  - 商品分析コメンタリー
  - 人気度（★）表示
  - フィルタ・検索機能
  - チャート可視化
"""

import sys
import os
import json
import logging
from datetime import date, datetime
from pathlib import Path

import streamlit as st
import pandas as pd

# パスを通す
sys.path.insert(0, os.path.dirname(__file__))

from config import COMPANIES, CATEGORY_LABELS, DATE_FROM, DATE_TO
from scrapers import SCRAPER_MAP
from filter import filter_releases
from scorer import score_and_rank, compute_score, score_categorized
from analyzer import analyze_categorized, analyze_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Streamlit 設定 ──
st.set_page_config(
    page_title="保険リリース ダッシュボード",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── キャッシュ付きデータ取得 ──
CACHE_FILE = os.path.join(os.path.dirname(__file__), "output", "cache_dashboard.json")


def _save_cache(data: dict):
    """キャッシュを保存"""
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    serializable = {}
    for cat, entries in data.items():
        serializable[cat] = []
        for e in entries:
            entry_copy = e.copy()
            # tags リストを文字列に変換（JSON互換）
            if "tags" in entry_copy and isinstance(entry_copy["tags"], list):
                entry_copy["tags"] = entry_copy["tags"]
            if "score_detail" in entry_copy and isinstance(entry_copy["score_detail"], dict):
                entry_copy["score_detail"] = entry_copy["score_detail"]
            serializable[cat].append(entry_copy)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "data": serializable,
        }, f, ensure_ascii=False, indent=2)


def _load_cache() -> dict | None:
    """キャッシュを読み込み"""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return cache.get("data")
    except Exception:
        return None


def _get_cache_timestamp() -> str | None:
    """キャッシュのタイムスタンプ取得"""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return cache.get("timestamp", "")
    except Exception:
        return None


@st.cache_data(ttl=3600)
def fetch_all_data(companies_list: tuple) -> dict[str, list[dict]]:
    """全社のデータを取得・フィルタ・スコアリング・分析"""
    raw_by_cat = {"A": [], "B": [], "C": []}

    companies = list(companies_list) if companies_list else list(SCRAPER_MAP.keys())

    progress = st.progress(0, text="データ取得中...")
    total_companies = len(companies)

    for idx, key in enumerate(companies):
        if key not in SCRAPER_MAP:
            continue

        scraper = SCRAPER_MAP[key]()
        company_cfg = COMPANIES.get(key, {})
        available_cats = company_cfg.get("pages", {}).keys()

        for cat in ("A", "B", "C"):
            if cat not in available_cats:
                continue
            try:
                entries = scraper.fetch_releases(category=cat)
                for e in entries:
                    e["category"] = cat
                raw_by_cat[cat].extend(entries)
            except Exception as e:
                logger.error(f"[{scraper.company_name}] カテゴリ{cat} エラー: {e}")

        progress.progress((idx + 1) / total_companies, text=f"{scraper.company_name} 完了...")

    progress.empty()

    # フィルタリング
    result = {}
    for cat in ("A", "B", "C"):
        result[cat] = filter_releases(raw_by_cat[cat])

    # スコアリング
    result = score_categorized(result)

    # 商品分析
    result = analyze_categorized(result)

    # キャッシュ保存
    _save_cache(result)

    return result


def render_stars(n: int) -> str:
    """★表示"""
    return "★" * n + "☆" * (5 - n)


def rank_badge(rank: str) -> str:
    """ランクバッジHTML"""
    colors = {
        "S": "#FF4444",
        "A": "#FF8800",
        "B": "#44AA44",
        "C": "#4488CC",
        "D": "#888888",
    }
    color = colors.get(rank, "#888888")
    return f":{color}[**{rank}**]"


def render_score_bar(score: float) -> str:
    """スコアバー"""
    filled = int(score / 5)
    return "█" * filled + "░" * (20 - filled)


# ══════════════════════════════════════════════════════════
#  メイン画面
# ══════════════════════════════════════════════════════════

def main():
    # ── ヘッダー ──
    st.title("📊 保険リリース ダッシュボード")
    st.caption(f"対象期間: {DATE_FROM} ～ {DATE_TO}")

    # ── サイドバー ──
    with st.sidebar:
        st.header("🔧 設定")

        # 会社フィルター
        all_companies = list(SCRAPER_MAP.keys())
        company_names = {k: COMPANIES[k]["name"] for k in all_companies}

        selected_companies = st.multiselect(
            "対象会社",
            options=all_companies,
            default=all_companies,
            format_func=lambda x: company_names.get(x, x),
        )

        # データ取得ボタン
        st.divider()
        fetch_button = st.button("🔄 データ取得（最新）", use_container_width=True, type="primary")

        # キャッシュ使用
        use_cache = st.checkbox("キャッシュを使用", value=True)
        cache_ts = _get_cache_timestamp()
        if cache_ts:
            st.caption(f"最終取得: {cache_ts[:19]}")

        st.divider()

        # 表示フィルター
        st.subheader("📋 表示フィルター")
        min_score = st.slider("最低スコア", 0, 100, 0)
        min_stars = st.slider("最低人気度（★）", 1, 5, 1)
        search_text = st.text_input("🔍 キーワード検索")

        # ランクフィルター
        rank_filter = st.multiselect(
            "ランクフィルター",
            options=["S", "A", "B", "C", "D"],
            default=["S", "A", "B", "C", "D"],
        )

    # ── データ取得 ──
    data = None

    if fetch_button:
        st.cache_data.clear()
        data = fetch_all_data(tuple(selected_companies))
    elif use_cache:
        data = _load_cache()
        if data is None:
            st.info("キャッシュがありません。「データ取得」ボタンを押してください。")
            return
    else:
        data = fetch_all_data(tuple(selected_companies))

    if data is None:
        st.info("データがありません。サイドバーから「データ取得」を実行してください。")
        return

    # ── サマリーメトリクス ──
    total_all = sum(len(v) for v in data.values())

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📰 総リリース数", f"{total_all}件")
    with col2:
        s_rank_count = sum(
            1 for cat in data.values()
            for e in cat if e.get("rank_label") == "S"
        )
        st.metric("🏆 Sランク", f"{s_rank_count}件")
    with col3:
        avg_score = 0
        if total_all > 0:
            avg_score = sum(
                e.get("score", 0) for cat in data.values() for e in cat
            ) / total_all
        st.metric("📈 平均スコア", f"{avg_score:.1f}")
    with col4:
        company_count = len(set(
            e.get("company", "") for cat in data.values() for e in cat
        ))
        st.metric("🏢 取得会社数", f"{company_count}社")

    st.divider()

    # ── タブ表示 ──
    tab_overview, tab_a, tab_b, tab_c, tab_charts = st.tabs([
        "📊 総合ランキング",
        f"📋 カテゴリA ({CATEGORY_LABELS['A']})",
        f"📋 カテゴリB ({CATEGORY_LABELS['B']})",
        f"📋 カテゴリC ({CATEGORY_LABELS['C']})",
        "📈 分析チャート",
    ])

    # ── 総合ランキングタブ ──
    with tab_overview:
        st.subheader("🏆 総合ランキング（全カテゴリ統合・スコア順）")

        # 全エントリを統合してスコア順
        all_entries = []
        for cat, entries in data.items():
            for e in entries:
                e_copy = e.copy()
                e_copy["cat_label"] = f"{cat}: {CATEGORY_LABELS.get(cat, cat)}"
                all_entries.append(e_copy)
        all_entries.sort(key=lambda x: x.get("score", 0), reverse=True)

        # フィルター適用
        filtered = _apply_filters(all_entries, min_score, min_stars, search_text, rank_filter)

        if not filtered:
            st.info("条件に合致するリリースがありません。")
        else:
            _render_release_cards(filtered)

    # ── カテゴリ別タブ ──
    for tab, cat_key in [(tab_a, "A"), (tab_b, "B"), (tab_c, "C")]:
        with tab:
            cat_label = CATEGORY_LABELS.get(cat_key, cat_key)
            st.subheader(f"カテゴリ{cat_key}: {cat_label}")

            entries = data.get(cat_key, [])
            filtered = _apply_filters(entries, min_score, min_stars, search_text, rank_filter)

            if not filtered:
                st.info(f"カテゴリ{cat_key}には条件に合致するリリースがありません。")
            else:
                _render_release_cards(filtered)

    # ── チャートタブ ──
    with tab_charts:
        _render_charts(data)


def _apply_filters(
    entries: list[dict],
    min_score: int,
    min_stars: int,
    search_text: str,
    rank_filter: list[str],
) -> list[dict]:
    """表示フィルター適用"""
    result = []
    for e in entries:
        if e.get("score", 0) < min_score:
            continue
        if e.get("popularity", 1) < min_stars:
            continue
        if e.get("rank_label", "D") not in rank_filter:
            continue
        if search_text:
            combined = f"{e.get('title', '')} {e.get('company', '')} {e.get('commentary', '')}"
            if search_text.lower() not in combined.lower():
                continue
        result.append(e)
    return result


def _render_release_cards(entries: list[dict]):
    """リリースカードをレンダリング"""
    for i, entry in enumerate(entries):
        rank_label = entry.get("rank_label", "D")
        score = entry.get("score", 0)
        popularity = entry.get("popularity", 1)
        commentary = entry.get("commentary", "")
        product_type = entry.get("product_type", "")
        action_type = entry.get("action_type", "")
        tags = entry.get("tags", [])

        # ランクに応じた色付け
        rank_colors = {"S": "🔴", "A": "🟠", "B": "🟢", "C": "🔵", "D": "⚪"}
        rank_icon = rank_colors.get(rank_label, "⚪")

        # カード表示
        with st.container():
            # ヘッダー行
            hcol1, hcol2, hcol3, hcol4, hcol5 = st.columns([1, 2, 6, 2, 2])
            with hcol1:
                st.markdown(f"### {rank_icon} {rank_label}")
            with hcol2:
                st.markdown(f"**{entry.get('company', '')}**")
            with hcol3:
                title = entry.get("title", "")
                url = entry.get("url", "")
                if url:
                    st.markdown(f"[{title}]({url})")
                else:
                    st.markdown(title)
            with hcol4:
                st.markdown(f"📅 {entry.get('date', '')}")
            with hcol5:
                st.markdown(f"Score: **{score}** {render_stars(popularity)}")

            # 詳細展開
            with st.expander("💡 詳細分析", expanded=(rank_label in ("S", "A"))):
                dcol1, dcol2 = st.columns([3, 2])
                with dcol1:
                    st.markdown(f"**📝 コメンタリー:** {commentary}")
                    if product_type:
                        st.markdown(f"**📦 商品タイプ:** {product_type}")
                    if action_type:
                        st.markdown(f"**🎯 アクション:** {action_type}")
                    if tags:
                        st.markdown(f"**🏷️ タグ:** {', '.join(tags)}")

                with dcol2:
                    # スコア内訳
                    detail = entry.get("score_detail", {})
                    if detail:
                        st.markdown("**スコア内訳:**")
                        score_data = pd.DataFrame([
                            {"項目": "キーワード", "スコア": detail.get("keyword", 0)},
                            {"項目": "鮮度", "スコア": detail.get("recency", 0)},
                            {"項目": "一時払い関連", "スコア": detail.get("ichiji", 0)},
                            {"項目": "カテゴリ", "スコア": detail.get("category", 0)},
                            {"項目": "ブランド", "スコア": detail.get("brand", 0)},
                        ])
                        st.dataframe(score_data, hide_index=True, use_container_width=True)

                    reason = entry.get("reason", "")
                    if reason:
                        st.markdown(f"**抽出理由:** {reason}")

            st.divider()


def _render_charts(data: dict):
    """分析チャートを描画"""
    st.subheader("📈 分析チャート")

    # 全エントリ統合
    all_entries = []
    for cat, entries in data.items():
        for e in entries:
            e_copy = e.copy()
            e_copy["category_label"] = CATEGORY_LABELS.get(cat, cat)
            all_entries.append(e_copy)

    if not all_entries:
        st.info("データがありません。")
        return

    df = pd.DataFrame(all_entries)

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        # 会社別リリース数
        st.markdown("### 🏢 会社別リリース数")
        company_counts = df["company"].value_counts()
        st.bar_chart(company_counts)

    with chart_col2:
        # カテゴリ別リリース数
        st.markdown("### 📋 カテゴリ別リリース数")
        cat_counts = df["category_label"].value_counts()
        st.bar_chart(cat_counts)

    chart_col3, chart_col4 = st.columns(2)

    with chart_col3:
        # ランク分布
        st.markdown("### 🏆 ランク分布")
        if "rank_label" in df.columns:
            rank_counts = df["rank_label"].value_counts().reindex(["S", "A", "B", "C", "D"], fill_value=0)
            st.bar_chart(rank_counts)

    with chart_col4:
        # スコア分布
        st.markdown("### 📊 スコア分布")
        if "score" in df.columns:
            st.bar_chart(df["score"].value_counts().sort_index())

    # 会社別平均スコア
    st.markdown("### 📈 会社別平均スコア")
    if "score" in df.columns:
        avg_by_company = df.groupby("company")["score"].mean().sort_values(ascending=False)
        st.bar_chart(avg_by_company)

    # 商品タイプ分布
    st.markdown("### 📦 商品タイプ分布")
    if "product_type" in df.columns:
        pt = df[df["product_type"] != ""]["product_type"].value_counts()
        if not pt.empty:
            st.bar_chart(pt)
        else:
            st.info("商品タイプが推定されたリリースはありません。")

    # データテーブル（全件）
    st.markdown("### 📋 全データテーブル")
    display_cols = ["company", "date", "title", "score", "rank_label", "popularity",
                    "product_type", "action_type", "commentary"]
    available_cols = [c for c in display_cols if c in df.columns]
    col_labels = {
        "company": "会社名", "date": "日付", "title": "見出し",
        "score": "スコア", "rank_label": "ランク", "popularity": "人気度",
        "product_type": "商品タイプ", "action_type": "アクション",
        "commentary": "コメンタリー",
    }
    display_df = df[available_cols].rename(columns=col_labels)
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=600,
    )


if __name__ == "__main__":
    main()
