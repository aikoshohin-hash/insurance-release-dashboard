"""HTMLレポート公開デプロイモジュール

生成されたHTMLレポートをインターネットに公開し、
スマホや他PCからどこでもアクセスできるURLを発行する。

デプロイ先（優先順位）:
  1. 0x0.st  (アカウント不要・パスワード不要・約30日保持)
  2. surge.sh (npx経由)

使い方:
  python deploy.py                         # 最新のレポートを公開
  python deploy.py report_xxx.html         # 指定ファイルを公開
  python deploy.py --info                  # 前回のデプロイ情報を表示
"""

import os
import sys
import glob
import json
import shutil
import logging
import argparse
import subprocess
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from config import OUTPUT_DIR

logger = logging.getLogger(__name__)

DEPLOY_INFO_FILE = os.path.join(os.path.dirname(__file__), ".deploy_info.json")


def _save_deploy_info(info: dict):
    info["deployed_at"] = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    with open(DEPLOY_INFO_FILE, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)


def _load_deploy_info() -> dict | None:
    if os.path.exists(DEPLOY_INFO_FILE):
        with open(DEPLOY_INFO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def find_latest_report() -> str | None:
    """最新のHTMLレポートを検索"""
    pattern = os.path.join(OUTPUT_DIR, "report_*.html")
    files = sorted(glob.glob(pattern), reverse=True)
    return files[0] if files else None


def deploy_0x0(html_path: str) -> str | None:
    """0x0.st にアップロード（アカウント不要・パスワード不要）

    - 無料ホスティング
    - HTMLはブラウザでそのまま表示される
    - 約30日間保持
    - ファイルサイズ上限: 512MB
    """
    print("0x0.st にアップロード中...")

    curl = shutil.which("curl")
    if curl:
        # curl が使える場合（高速）
        try:
            result = subprocess.run(
                [curl, "-s", "-F", f"file=@{html_path}", "https://0x0.st"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 and result.stdout.strip().startswith("http"):
                url = result.stdout.strip()
                print(f"  アップロード成功!")
                _save_deploy_info({
                    "method": "0x0.st",
                    "url": url,
                    "source": html_path,
                })
                return url
        except Exception as e:
            logger.debug(f"curl失敗: {e}")

    # curl が無い場合は Python の urllib で
    try:
        import urllib.request
        import urllib.error

        boundary = "----PythonFormBoundary"
        filename = os.path.basename(html_path)

        with open(html_path, "rb") as f:
            file_data = f.read()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: text/html\r\n\r\n"
        ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

        req = urllib.request.Request(
            "https://0x0.st",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            url = resp.read().decode("utf-8").strip()
            if url.startswith("http"):
                print(f"  アップロード成功!")
                _save_deploy_info({
                    "method": "0x0.st",
                    "url": url,
                    "source": html_path,
                })
                return url
    except Exception as e:
        logger.warning(f"0x0.st アップロード失敗: {e}")

    return None


def deploy(html_path: str | None = None) -> str | None:
    """HTMLレポートをインターネットに公開

    Args:
        html_path: 公開するHTMLファイル。Noneの場合は最新を自動検出。

    Returns:
        公開URL (失敗時は None)
    """
    if html_path is None:
        html_path = find_latest_report()
        if html_path is None:
            print("HTMLレポートが見つかりません。先に main.py を実行してください。")
            return None

    if not os.path.exists(html_path):
        print(f"ファイルが見つかりません: {html_path}")
        return None

    size_kb = os.path.getsize(html_path) / 1024
    print(f"\n公開対象: {os.path.basename(html_path)}")
    print(f"サイズ: {size_kb:.1f} KB\n")

    # 0x0.st にデプロイ
    url = deploy_0x0(html_path)

    if url:
        print(f"\n{'='*50}")
        print(f"  公開URL: {url}")
        print(f"  スマホ・他PCからアクセス可能です")
        print(f"  (アカウント/パスワード不要)")
        print(f"  保持期間: 約30日")
        print(f"{'='*50}\n")
    else:
        print("\nデプロイに失敗しました。手動でアップロードしてください:")
        print(f"  ファイル: {html_path}")
        print("  方法: https://0x0.st にアクセスしファイルを選択")

    return url


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="HTMLレポートをインターネットに公開",
    )
    parser.add_argument(
        "file", nargs="?", default=None,
        help="公開するHTMLファイル（省略時は最新を自動検出）",
    )
    parser.add_argument(
        "--info", action="store_true",
        help="前回のデプロイ情報を表示",
    )

    args = parser.parse_args()

    if args.info:
        info = _load_deploy_info()
        if info:
            print("\n前回のデプロイ情報:")
            print(f"  方法: {info.get('method', '不明')}")
            print(f"  URL: {info.get('url', '不明')}")
            print(f"  日時: {info.get('deployed_at', '不明')}")
            print(f"  ソース: {info.get('source', '不明')}")
        else:
            print("デプロイ情報がありません。")
        return

    html_path = args.file
    if html_path and not os.path.isabs(html_path):
        candidate = os.path.join(OUTPUT_DIR, html_path)
        if os.path.exists(candidate):
            html_path = candidate

    deploy(html_path)


if __name__ == "__main__":
    main()
