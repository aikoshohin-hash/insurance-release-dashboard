"""Google Sheets アップロードモジュール v3 - スコアリング対応

認証方法（優先順位）:
  1. サービスアカウント: credentials.json をプロジェクトルートに配置
  2. OAuth認証: 初回実行時にブラウザが開き、認証を求められます
     → authorized_user.json が自動生成され、以降は自動認証

セットアップ手順:
  1. Google Cloud Console → APIとサービス → 認証情報
  2. 「サービスアカウント」を作成し、JSONキーをダウンロード
  3. credentials.json としてプロジェクトルートに配置
  4. 対象スプレッドシートをサービスアカウントのメールアドレスと共有
"""

import os
import logging
from datetime import date

import gspread

from config import SPREADSHEET_ID, GSHEET_CREDENTIALS, CATEGORY_LABELS, PROJECT_DIR

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

OAUTH_CREDENTIALS = os.path.join(PROJECT_DIR, "oauth_credentials.json")
AUTHORIZED_USER = os.path.join(PROJECT_DIR, "authorized_user.json")


def _stars_text(n: int) -> str:
    """★を文字列で表現"""
    return "★" * n + "☆" * (5 - n)


def get_client() -> gspread.Client:
    """認証済み gspread クライアントを返す（サービスアカウント or OAuth）"""

    # 方法1: サービスアカウント
    if os.path.exists(GSHEET_CREDENTIALS):
        from google.oauth2.service_account import Credentials
        creds = Credentials.from_service_account_file(GSHEET_CREDENTIALS, scopes=SCOPES)
        logger.info("サービスアカウント認証を使用")
        return gspread.authorize(creds)

    # 方法2: OAuth (authorized_user.json が既にある場合)
    if os.path.exists(AUTHORIZED_USER):
        client = gspread.oauth(
            credentials_filename=OAUTH_CREDENTIALS if os.path.exists(OAUTH_CREDENTIALS) else None,
            authorized_user_filename=AUTHORIZED_USER,
        )
        logger.info("OAuth認証（保存済み）を使用")
        return client

    # 方法3: OAuth 初回認証（ブラウザが開く）
    if os.path.exists(OAUTH_CREDENTIALS):
        client = gspread.oauth(
            credentials_filename=OAUTH_CREDENTIALS,
            authorized_user_filename=AUTHORIZED_USER,
        )
        logger.info("OAuth認証（初回）を使用")
        return client

    raise FileNotFoundError(
        "Google Sheets認証ファイルが見つかりません。\n"
        "以下のいずれかをプロジェクトルートに配置してください:\n"
        "  ・credentials.json (サービスアカウント)\n"
        "  ・oauth_credentials.json (OAuth認証)"
    )


def upload_to_gsheet(
    categorized: dict[str, list[dict]],
    sheet_name: str | None = None,
) -> str:
    """カテゴリ分類済みデータを Google Sheets にアップロード（v3: スコアリング対応）"""
    if sheet_name is None:
        sheet_name = date.today().strftime("%Y/%m/%d")

    # スコアリング列の有無を判定
    has_scoring = any(
        "score" in e
        for entries in categorized.values()
        for e in entries
    )

    client = get_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    # 既存シートがあれば削除して再作成
    try:
        existing = spreadsheet.worksheet(sheet_name)
        spreadsheet.del_worksheet(existing)
        logger.info(f"既存シート「{sheet_name}」を削除しました")
    except gspread.exceptions.WorksheetNotFound:
        pass

    num_cols = 10 if has_scoring else 5
    worksheet = spreadsheet.add_worksheet(
        title=sheet_name, rows=2000, cols=num_cols
    )
    logger.info(f"シート「{sheet_name}」を作成しました")

    # データ構築
    rows = []
    for cat_key in ("A", "B", "C"):
        cat_label = CATEGORY_LABELS.get(cat_key, cat_key)
        entries = categorized.get(cat_key, [])

        if has_scoring:
            rows.append([
                f"【カテゴリ{cat_key}】{cat_label}（{len(entries)}件）",
                "", "", "", "", "", "", "", "", "",
            ])
            rows.append([
                "ランク", "スコア", "人気度", "会社名", "日付",
                "見出し", "URL", "商品タイプ", "コメンタリー", "抽出理由",
            ])
        else:
            rows.append([
                f"【カテゴリ{cat_key}】{cat_label}（{len(entries)}件）",
                "", "", "", "",
            ])
            rows.append(["会社名", "日付", "見出し", "URL", "抽出理由"])

        if entries:
            for e in entries:
                if has_scoring:
                    rows.append([
                        e.get("rank_label", ""),
                        e.get("score", 0),
                        _stars_text(e.get("popularity", 1)),
                        e.get("company", ""),
                        e.get("date", ""),
                        e.get("title", ""),
                        e.get("url", ""),
                        e.get("product_type", ""),
                        e.get("commentary", ""),
                        e.get("reason", ""),
                    ])
                else:
                    rows.append([
                        e.get("company", ""),
                        e.get("date", ""),
                        e.get("title", ""),
                        e.get("url", ""),
                        e.get("reason", ""),
                    ])
        else:
            filler = [""] * num_cols
            filler[0] = "（該当なし）"
            rows.append(filler)

        rows.append([""] * num_cols)

    # 一括書き込み
    worksheet.update(rows, value_input_option="USER_ENTERED")

    # 書式設定（ベストエフォート）
    try:
        fmt_requests = []
        r = 0
        for cat_key in ("A", "B", "C"):
            entries = categorized.get(cat_key, [])
            # カテゴリタイトル行: 背景色 + 太字
            fmt_requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": r,
                        "endRowIndex": r + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": num_cols,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.18, "green": 0.33, "blue": 0.59},
                            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            })
            # カラムヘッダー行
            fmt_requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": r + 1,
                        "endRowIndex": r + 2,
                        "startColumnIndex": 0,
                        "endColumnIndex": num_cols,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.27, "green": 0.45, "blue": 0.77},
                            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            })

            # ランク別の行色付け（Sランク＝赤背景、Aランク＝オレンジ背景）
            if has_scoring:
                data_start = r + 2
                for idx, e in enumerate(entries):
                    rank = e.get("rank_label", "D")
                    bg_colors = {
                        "S": {"red": 1.0, "green": 0.88, "blue": 0.88},
                        "A": {"red": 1.0, "green": 0.94, "blue": 0.82},
                        "B": {"red": 0.88, "green": 1.0, "blue": 0.88},
                    }
                    if rank in bg_colors:
                        fmt_requests.append({
                            "repeatCell": {
                                "range": {
                                    "sheetId": worksheet.id,
                                    "startRowIndex": data_start + idx,
                                    "endRowIndex": data_start + idx + 1,
                                    "startColumnIndex": 0,
                                    "endColumnIndex": num_cols,
                                },
                                "cell": {
                                    "userEnteredFormat": {
                                        "backgroundColor": bg_colors[rank],
                                    }
                                },
                                "fields": "userEnteredFormat(backgroundColor)",
                            }
                        })

            r += 2 + max(len(entries), 1) + 1

        # 列幅設定
        if has_scoring:
            col_widths = [60, 60, 100, 120, 90, 400, 350, 120, 350, 200]
        else:
            col_widths = [120, 90, 400, 350, 200]
        for i, w in enumerate(col_widths):
            fmt_requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": worksheet.id,
                        "dimension": "COLUMNS",
                        "startIndex": i,
                        "endIndex": i + 1,
                    },
                    "properties": {"pixelSize": w},
                    "fields": "pixelSize",
                }
            })

        spreadsheet.batch_update({"requests": fmt_requests})
    except Exception as e:
        logger.debug(f"書式設定スキップ: {e}")

    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid={worksheet.id}"
    logger.info(f"Google Sheets アップロード完了: {url}")
    return url
