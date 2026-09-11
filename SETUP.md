# 保険会社リリース自動取得ツール v4 — セットアップと運用

公開URL: https://aikoshohin-hash.github.io/insurance-release-dashboard/
リポジトリ: `aikoshohin-hash/insurance-release-dashboard`（PUBLIC）

---

## 1. 全体の仕組み

### 毎朝の流れ（GitHub Actions）

```
23:17 UTC（= 08:17 JST）に cron 起動 ※GitHub の都合で数十分遅れることがある
  │
  ├─ 15社のニュース一覧をスクレイプ
  ├─ 関連性ゲート（relevance.py）…… 本線 / 周辺 / 除外 の3値に分類
  ├─ 本文エンリッチ（enricher.py）… 本線・周辺のリリース本文/PDFを読み、
  │                                   商品名・通貨・利率・チャネル・取扱金融機関を抽出
  ├─ スコアリング（scorer.py）…… アクション40 + 関心軸25 + 裏取り15 + 鮮度12 + ブランド8
  ├─ 分析（analyzer.py）………… 事実 / 含意 / 利率の横比較 を組み立てる
  ├─ 新規検知（notifier.py）…… data/seen.json と突き合わせ、未知のものだけ Gmail で通知
  │
  ├─ data/ を main ブランチに書き戻し（本文キャッシュ・検知台帳）
  └─ index.html を gh-pages ブランチへ → GitHub Pages が配信
```

### ブランチの役割

| ブランチ | 中身 | 更新者 |
|---|---|---|
| `main` | ソースコード、ワークフロー、`data/`（本文キャッシュ・検知台帳） | 人 ＋ Actions（data/ のみ） |
| `gh-pages` | 配信物だけ（index.html / latest.xlsx / robots.txt / .nojekyll） | Actions のみ。毎回履歴を捨てて上書き |

### GitHub Pages について押さえておくこと

- Pages の設定は `gh-pages` ブランチのルートを配信（Settings > Pages）
- **サイトは URL を知っていれば誰でも閲覧可能**。robots.txt と noindex で検索エンジンを避けているだけ
  （Pages は私有リポジトリでも公開される。完全非公開は Enterprise Cloud 組織のみ）
- 公開リポジトリのため、他社サイトの**本文全文は保存しない**。保存するのは抽出後の構造化項目と
  根拠用の短い抜粋（120字×最大3本）だけ

### 認証

| 用途 | 仕組み |
|---|---|
| 手元の git / gh | `gh` CLI の OAuth トークン（Windows キーリング保存）。`gh.exe` は `test\gh_cli_tmp\bin\` にあり PATH 未登録 |
| Actions の push / Pages デプロイ / Issue 起票 | 実行ごとに GitHub が自動発行する `GITHUB_TOKEN`。登録作業なし |
| 通知メール | GitHub Secrets に登録した Gmail アプリパスワード（下記 §3） |

---

## 2. ローカルでの実行

```bash
cd insurance_release_fetcher
pip install -r requirements.txt
python main.py --no-gsheet
```

| オプション | 用途 |
|---|---|
| `--company sumitomo meiji-yasuda` | 特定の会社だけ |
| `--no-enrich-cache` | 本文キャッシュを使わず取り直す（抽出ルールを変えたとき） |
| `--list` | 対象会社一覧 |

Windows でコンソールが文字化けする場合は `set PYTHONIOENCODING=utf-8`。

> **注意**: ローカル実行でも `data/seen.json`（検知台帳）が更新されます。
> 手元の台帳を push すると CI の台帳を上書きするので、**data/ を手元からコミットしない**こと。
> CI が唯一の書き手です。

---

## 3. 新規検知メール（Gmail）の設定

新規の商品リリースを検知した朝だけ、Gmail から通知メールが届きます。
何もない日は送りません。設定しなければ送信はスキップされ、ダッシュボードの更新は通常どおり続きます。

### 手順（パスワードを扱うため、ご自身で行ってください）

**① 送信元の Gmail で 2段階認証を有効にする**
https://myaccount.google.com/security → 「2段階認証プロセス」

**② アプリパスワードを発行する**
https://myaccount.google.com/apppasswords → アプリ名に `insurance-release` など → 作成
表示された **16文字**を控える（この画面を閉じると二度と表示されない）。

**③ GitHub にシークレットを3つ登録する**
https://github.com/aikoshohin-hash/insurance-release-dashboard/settings/secrets/actions
→ 「New repository secret」

> **このページが 404 になる場合** — ブラウザで `aikoshohin-hash` としてログインしていません。
> GitHub は権限の無い人が設定ページを開くと「存在しない」として 404 を返します。
> 画面上部に「Platform / Solutions / Pricing」が並んでいたら未ログインの表示です。
> 右上の「Sign in」→「Continue with Google」でログインしてから開き直すか、下のコマンドで登録してください。

| Name | Secret に入れる値 |
|---|---|
| `SMTP_USER` | 送信元の Gmail アドレス |
| `SMTP_PASSWORD` | ②の16文字（スペースは詰める） |
| `MAIL_TO` | 宛先。複数ならカンマ区切り（`a@example.com,b@example.com`） |

コマンドで登録する場合（この PC の gh はログイン済みなので、ブラウザのログインは不要）。
1行ずつ実行すると `? Paste your secret` と聞かれるので値を貼り付けて Enter。値は画面にも履歴にも残りません。
gh は PATH に入っていないためフルパスで呼びます（PowerShell の場合）:

```powershell
& "C:\Users\DFLDXPT\Claude code\test\gh_cli_tmp\bin\gh.exe" secret set SMTP_USER     --repo aikoshohin-hash/insurance-release-dashboard
& "C:\Users\DFLDXPT\Claude code\test\gh_cli_tmp\bin\gh.exe" secret set SMTP_PASSWORD --repo aikoshohin-hash/insurance-release-dashboard
& "C:\Users\DFLDXPT\Claude code\test\gh_cli_tmp\bin\gh.exe" secret set MAIL_TO       --repo aikoshohin-hash/insurance-release-dashboard
```

**④ テストメールで動作確認**
台帳に全件が既知として載っているため、普通に手動実行しても新規0件でメールは来ません。
疎通確認は **テスト送信** で行います（台帳は変わりません）:

Actions タブ → 「Fetch & Deploy Report」→「Run workflow」→ **`test_mail` にチェック** → Run。
またはコマンドで:

```powershell
& "C:\Users\DFLDXPT\Claude code\test\gh_cli_tmp\bin\gh.exe" workflow run fetch_and_deploy.yml --repo aikoshohin-hash/insurance-release-dashboard -f test_mail=true
```

件名が「【テスト送信】【保険リリース】…」のメールが、現在の上位3件の内容で届けば成功です。

### 安全性

- シークレットは Actions の実行時にだけ環境変数として渡され、ログには `***` と伏せ字で出る
- このワークフローには `pull_request` トリガーが無く、またフォークからの PR にはシークレットが渡らない。
  PUBLIC リポジトリでも外部から読まれない
- アプリパスワードは Gmail 送信にしか使えず、Google アカウントのパスワードとは別物。
  不要になったら②の画面から個別に削除できる

### 送信に失敗したら

`notify-failure` ラベルの Issue が自動で立ちます（本文に、送るはずだった内容が入っています）。
Google アカウントのパスワードを変えるとアプリパスワードは失効するので、②③をやり直してください。

### 通知の判定ルール（notifier.py）

| ケース | 扱い |
|---|---|
| 台帳が無い初回 | 全件を既知として登録するだけ。通知しない |
| 台帳に1件も無い会社の初出 | 登録のみ（スクレイパーを直した社の過去記事が一斉に届くのを防ぐ） |
| リリース日付が14日より古い | 登録のみ（サイトがアーカイブを再掲した日の大量通知を防ぐ） |
| 周辺（事務サービス等）・除外 | 登録のみ。通知は商品リリースだけ |
| URL が変わっても会社名＋見出しが同じ | 既知扱い |

調整用の環境変数: `NOTIFY_TIERS`（既定 `PRODUCT`）、`NOTIFY_FRESH_DAYS`（既定 `14`）。

---

## 4. 関連性ゲートの調整

ダッシュボードの **「除外ログ」タブ**に、本線から外した見出しと理由が並びます。
拾うべきものが落ちていたら `relevance.py` の辞書を直してください。

```bash
python tools_eval_gate.py <エントリのJSON>   # 辞書変更の効きを実データで確認
python tools_test_notifier.py                # 通知ロジックの不変条件テスト
```

---

## 5. ファイル構成

```
insurance_release_fetcher/
  main.py            エントリポイント
  config.py          設定（抽出期間=直近12か月のローリング窓、ブラウザ一式ヘッダ）
  companies.py       対象会社マスタ（15社）
  relevance.py       関連性ゲート（本線/周辺/除外）
  filter.py          期間・重複の絞り込み（除外分も理由付きで返す）
  enricher.py        本文/PDF 取得と構造化抽出
  scorer.py          スコアリング
  analyzer.py        事実ベースのコメンタリー
  notifier.py        新規検知と Gmail 通知
  html_report.py     ダッシュボード HTML 生成
  health_checker.py  取得ヘルスチェック
  exporter.py        Excel 出力
  scrapers/          各社スクレイパー
  data/
    enrichment.json  本文から抽出した事実のキャッシュ（Actions が書き戻す）
    seen.json        新規検知の台帳（Actions が書き戻す。消すと翌日全件が新規扱い→初回ベースラインに戻る）
  .github/workflows/fetch_and_deploy.yml
```
