"""取得ヘルスチェックモジュール

各社のスクレイピング結果を検査し、問題があればアラートを生成する。

アラートレベル:
  ERROR  : 取得件数が0件（スクレイパー破損・サイト変更の可能性）
  WARNING: フィルタ後0件（キーワード不一致 or 日付範囲外のみ）
  INFO   : 正常取得

使い方:
  from health_checker import check_health, format_health_report
  alerts = check_health(raw_results, filtered_results)
  print(format_health_report(alerts))
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime

from config import OUTPUT_DIR

logger = logging.getLogger(__name__)

HEALTH_JSON = os.path.join(OUTPUT_DIR, "health_report.json")

ALERT_ERROR   = "ERROR"
ALERT_WARNING = "WARNING"
ALERT_OK      = "OK"


@dataclass
class CompanyHealth:
    key:          str
    name:         str
    level:        str           # OK / WARNING / ERROR
    raw_count:    int = 0       # スクレイパーが返した件数
    filter_count: int = 0       # フィルタ後件数
    errors:       list[str] = field(default_factory=list)   # エラーメッセージ
    message:      str = ""      # 表示用メッセージ

    def to_dict(self) -> dict:
        return asdict(self)


def check_health(
    raw_by_company:      dict[str, int],
    filtered_by_company: dict[str, int],
    errors_by_company:   dict[str, list[str]] | None = None,
) -> list[CompanyHealth]:
    """会社ごとの取得状況を検査してヘルスリストを返す。

    Args:
        raw_by_company:      {company_name: 取得件数}
        filtered_by_company: {company_name: フィルタ後件数}
        errors_by_company:   {company_name: [エラーメッセージ, ...]}

    Returns:
        CompanyHealth のリスト（ERRORが先頭）
    """
    errors_by_company = errors_by_company or {}
    results: list[CompanyHealth] = []

    all_names = set(raw_by_company) | set(filtered_by_company)
    for name in sorted(all_names):
        raw     = raw_by_company.get(name, 0)
        filtered = filtered_by_company.get(name, 0)
        errors  = errors_by_company.get(name, [])

        if raw == 0:
            level   = ALERT_ERROR
            message = "スクレイピング0件 - サイト構造変更・WAFブロックの可能性"
        elif filtered == 0:
            level   = ALERT_WARNING
            message = f"取得{raw}件 / フィルタ後0件 - 対象期間内にキーワード一致なし"
        else:
            level   = ALERT_OK
            message = f"正常: {filtered}件取得"

        results.append(CompanyHealth(
            key=name, name=name,
            level=level,
            raw_count=raw, filter_count=filtered,
            errors=errors, message=message,
        ))

    # ERROR → WARNING → OK の順にソート
    order = {ALERT_ERROR: 0, ALERT_WARNING: 1, ALERT_OK: 2}
    results.sort(key=lambda h: order[h.level])
    return results


def format_health_report(health_list: list[CompanyHealth]) -> str:
    """コンソール用のヘルスレポート文字列を生成する。"""
    lines = [
        "",
        "=" * 60,
        "  取得ヘルスチェック結果",
        "=" * 60,
    ]

    errors   = [h for h in health_list if h.level == ALERT_ERROR]
    warnings = [h for h in health_list if h.level == ALERT_WARNING]
    oks      = [h for h in health_list if h.level == ALERT_OK]

    if errors:
        lines.append(f"\n[ERROR] ({len(errors)}sha) - 至急確認が必要")
        for h in errors:
            lines.append(f"  {h.name}: {h.message}")
            for e in h.errors:
                lines.append(f"    -> {e}")

    if warnings:
        lines.append(f"\n[WARNING] ({len(warnings)}sha) - データなし")
        for h in warnings:
            lines.append(f"  {h.name}: {h.message}")

    if oks:
        lines.append(f"\n[OK] ({len(oks)}sha)")
        for h in oks:
            lines.append(f"  {h.name}: {h.message}")

    total  = len(health_list)
    ok_cnt = len(oks)
    lines += [
        "",
        f"  結果サマリー: {ok_cnt}/{total}社 正常 | ERROR {len(errors)}社 | WARNING {len(warnings)}社",
        "=" * 60,
        "",
    ]
    return "\n".join(lines)


def save_health_json(health_list: list[CompanyHealth]) -> str:
    """ヘルス結果を JSON ファイルに保存する（HTML レポート埋め込み用）。"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    payload = {
        "generated_at": datetime.now().strftime("%Y/%m/%d %H:%M"),
        "summary": {
            "total":   len(health_list),
            "ok":      sum(1 for h in health_list if h.level == ALERT_OK),
            "warning": sum(1 for h in health_list if h.level == ALERT_WARNING),
            "error":   sum(1 for h in health_list if h.level == ALERT_ERROR),
        },
        "companies": [h.to_dict() for h in health_list],
    }
    with open(HEALTH_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"ヘルスレポート保存: {HEALTH_JSON}")
    return HEALTH_JSON
