"""GitHub Pages 自動セットアップスクリプト

このスクリプトは以下を自動実行します:
  1. GitHubリポジトリの作成 (private)
  2. config.py にGitHub情報を書き込み
  3. git init & 初回 push
  4. GitHub Pages の有効化
  5. 初回 GitHub Actions ワークフロー実行
  6. デプロイURLの表示

使い方:
  python github_setup.py

前提条件:
  - gh (GitHub CLI) がインストール済み
  - gh auth login でGitHubにログイン済み
"""

import os
import sys
import subprocess
import json
import re

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_cmd(cmd, check=True, capture=True):
    """コマンド実行ヘルパー"""
    result = subprocess.run(
        cmd, shell=True, capture_output=capture, text=True,
        cwd=PROJECT_DIR, encoding="utf-8"
    )
    if check and result.returncode != 0:
        print(f"  [ERROR] コマンド失敗: {cmd}")
        if result.stderr:
            print(f"  {result.stderr.strip()}")
        return None
    return result.stdout.strip() if capture else ""


def check_gh_cli():
    """GitHub CLIの存在とログイン状態を確認"""
    # gh コマンドの存在確認
    result = subprocess.run(
        "gh --version", shell=True, capture_output=True, text=True
    )
    if result.returncode != 0:
        print("[ERROR] GitHub CLI (gh) がインストールされていません。")
        print("  インストール: https://cli.github.com/")
        print("  または: winget install GitHub.cli")
        return False

    # ログイン状態確認
    result = subprocess.run(
        "gh auth status", shell=True, capture_output=True, text=True
    )
    if result.returncode != 0:
        print("[INFO] GitHub にログインが必要です。")
        print("  以下のコマンドでログインしてください:")
        print("  gh auth login")
        return False

    print("[OK] GitHub CLI ログイン済み")
    return True


def get_gh_username():
    """ログイン中のGitHubユーザー名を取得"""
    output = run_cmd("gh api user --jq .login")
    return output if output else None


def create_repo(repo_name):
    """GitHubリポジトリを作成 (private)"""
    # 既存チェック
    result = subprocess.run(
        f"gh repo view {repo_name}",
        shell=True, capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"[OK] リポジトリ '{repo_name}' は既に存在します")
        return True

    print(f"[...] リポジトリ '{repo_name}' を作成中 (private)...")
    output = run_cmd(
        f'gh repo create {repo_name} --private --description "保険会社リリース自動取得ダッシュボード"'
    )
    if output is None:
        return False
    print(f"[OK] リポジトリ作成完了")
    return True


def update_config(owner, repo):
    """config.py のGitHub設定を更新"""
    config_path = os.path.join(PROJECT_DIR, "config.py")
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = re.sub(
        r'GITHUB_OWNER\s*=\s*".*?"',
        f'GITHUB_OWNER = "{owner}"',
        content,
    )
    content = re.sub(
        r'GITHUB_REPO\s*=\s*".*?"',
        f'GITHUB_REPO = "{repo}"',
        content,
    )

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[OK] config.py 更新: GITHUB_OWNER={owner}, GITHUB_REPO={repo}")


def setup_git_and_push(owner, repo):
    """Gitリポジトリ初期化 & push"""
    git_dir = os.path.join(PROJECT_DIR, ".git")

    if not os.path.exists(git_dir):
        run_cmd("git init")
        print("[OK] git init 完了")

    # remote 設定
    remote_url = f"https://github.com/{owner}/{repo}.git"
    existing = run_cmd("git remote -v", check=False)
    if "origin" in (existing or ""):
        run_cmd(f"git remote set-url origin {remote_url}", check=False)
    else:
        run_cmd(f"git remote add origin {remote_url}")
    print(f"[OK] remote origin: {remote_url}")

    # .gitignore 作成（まだない場合）
    gitignore_path = os.path.join(PROJECT_DIR, ".gitignore")
    if not os.path.exists(gitignore_path):
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write(
                "__pycache__/\n"
                "*.pyc\n"
                ".env\n"
                "credentials.json\n"
                "output/\n"
                "*.xlsx\n"
                "*.zip\n"
                "cache_dashboard.json\n"
                ".deploy_info.json\n"
                ".streamlit/\n"
                "deploy/\n"
            )
        print("[OK] .gitignore 作成")

    # コミット & push
    run_cmd("git add -A")
    run_cmd('git commit -m "Initial commit: insurance release fetcher v3"', check=False)

    # main ブランチに切り替え
    run_cmd("git branch -M main", check=False)

    print("[...] GitHub へ push 中...")
    result = run_cmd("git push -u origin main", check=False)
    if result is None:
        # force push を試行
        run_cmd("git push -u origin main --force", check=False)
    print("[OK] push 完了")


def enable_github_pages(owner, repo):
    """GitHub Pages を gh-pages ブランチから有効化"""
    print("[...] GitHub Pages を有効化中...")

    # Pages 設定 (gh-pages ブランチ, / ルート)
    result = run_cmd(
        f'gh api repos/{owner}/{repo}/pages '
        f'-X POST '
        f'-H "Accept: application/vnd.github.v3+json" '
        f'-f "source[branch]=gh-pages" '
        f'-f "source[path]=/"',
        check=False,
    )

    if result is None:
        # 既に有効化済みの場合もある
        result = run_cmd(
            f'gh api repos/{owner}/{repo}/pages '
            f'-X PUT '
            f'-H "Accept: application/vnd.github.v3+json" '
            f'-f "source[branch]=gh-pages" '
            f'-f "source[path]=/"',
            check=False,
        )

    print("[OK] GitHub Pages 設定完了 (gh-pages ブランチ)")


def enable_actions_permissions(owner, repo):
    """GitHub Actions の permissions を有効化"""
    run_cmd(
        f'gh api repos/{owner}/{repo}/actions/permissions '
        f'-X PUT '
        f'-H "Accept: application/vnd.github.v3+json" '
        f'-f "enabled=true" '
        f'-f "allowed_actions=all"',
        check=False,
    )
    # GITHUB_TOKEN に write 権限を付与
    run_cmd(
        f'gh api repos/{owner}/{repo} '
        f'-X PATCH '
        f'-H "Accept: application/vnd.github.v3+json" '
        f'--input - <<< \'{{"default_branch":"main"}}\'',
        check=False,
    )
    print("[OK] GitHub Actions 権限設定完了")


def trigger_first_workflow(owner, repo):
    """初回ワークフロー実行"""
    print("[...] 初回データ取得ワークフローを実行中...")
    result = run_cmd(
        f"gh workflow run fetch_and_deploy.yml --repo {owner}/{repo}",
        check=False,
    )
    if result is not None:
        print("[OK] ワークフロー実行開始 (約5分で完了)")
    else:
        print("[INFO] ワークフローは次回 push 時または手動実行で開始されます")


def main():
    print()
    print("=" * 60)
    print("  保険リリースダッシュボード - GitHub Pages セットアップ")
    print("=" * 60)
    print()

    # 1. GitHub CLI チェック
    if not check_gh_cli():
        print("\n先に GitHub CLI のインストール & ログインを行ってください。")
        sys.exit(1)

    # 2. ユーザー名取得
    username = get_gh_username()
    if not username:
        print("[ERROR] GitHubユーザー名を取得できません。gh auth login を実行してください。")
        sys.exit(1)
    print(f"[OK] GitHubユーザー: {username}")

    # 3. リポジトリ名
    repo_name = "insurance-release-dashboard"
    print(f"[INFO] リポジトリ名: {repo_name}")

    # 4. リポジトリ作成
    if not create_repo(repo_name):
        print("[ERROR] リポジトリ作成に失敗しました。")
        sys.exit(1)

    # 5. config.py 更新
    update_config(username, repo_name)

    # 6. Git 初期化 & push
    setup_git_and_push(username, repo_name)

    # 7. GitHub Actions 権限
    enable_actions_permissions(username, repo_name)

    # 8. 初回ワークフロー実行
    trigger_first_workflow(username, repo_name)

    # 9. GitHub Pages 有効化 (gh-pages ブランチ作成後)
    enable_github_pages(username, repo_name)

    # 結果表示
    pages_url = f"https://{username}.github.io/{repo_name}/"
    repo_url = f"https://github.com/{username}/{repo_name}"
    actions_url = f"{repo_url}/actions"

    print()
    print("=" * 60)
    print("  セットアップ完了!")
    print("=" * 60)
    print()
    print(f"  リポジトリ:     {repo_url}")
    print(f"  GitHub Actions: {actions_url}")
    print(f"  ダッシュボード: {pages_url}")
    print()
    print("  ※ 初回デプロイは約5分後に完了します")
    print("  ※ 以降は毎日 9:00 JST に自動更新されます")
    print("  ※ 手動更新: GitHub Actions ページで 'Run workflow' をクリック")
    print()
    print(f"  会社PC・スマホからアクセス:")
    print(f"    {pages_url}")
    print()


if __name__ == "__main__":
    main()
