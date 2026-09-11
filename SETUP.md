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
  ├─ 新規検知（notifier.py）…… data/seen.json と突き合わせ、未知の商品リリースだけを抽出
  │
  ├─ data/ を main ブランチに書き戻し（本文キャッシュ・検知台帳）
  ├─ 新規があれば Issue を起票 → GitHub が通知メールを送る
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

**秘密情報（Secrets）は1つも使っていません。**

### GitHub の設定画面が 404 になるとき

ブラウザで `aikoshohin-hash` としてログインしていません。GitHub は権限の無い人が設定ページを開くと
「存在しない」として 404 を返します。画面上部に「Platform / Solutions / Pricing」が並んでいたら未ログインの表示です。
右上の「Sign in」→「Continue with Google」でログインしてください。

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

> **注意**: ローカル実行でも `data/seen.json`（検知台帳）が作られます。
> 手元の台帳を push すると CI の台帳を上書きするので、**data/ を手元からコミットしない**こと。
> CI が唯一の書き手です。手元で走らせたら data/ は消してから `git pull` してください。

---

## 3. 新規検知の通知（GitHub Issue → 通知メール）

新規の商品リリースを検知した朝だけ、`new-release` ラベルの Issue が1件立ちます。
GitHub はリポジトリを Watch しているアカウントの登録メールへ、その Issue を通知メールとして送ります。
Issue の本文（事実・含意・原文リンク）はメール本文にそのまま入ります。何もない日は何も起きません。

### 当初案（Gmail + アプリパスワード）を採らなかった理由

アプリパスワードは送信専用ではなく、Gmail のメール受信（IMAP）にも使えます。
漏れたときにメールボックスを読まれうるうえ、2段階認証も通らずに使えるため、
「自分に通知を送る」という用途に対して被害範囲が大きすぎると判断しました（2026-09-11）。
この方式は秘密情報を一切使いません。

### メールが届くための条件（最初に一度だけ確認）

1. **このリポジトリを Watch している**
   リポジトリのページ右上「Watch」が「All Activity」（または「Custom」で Issues にチェック）になっていること。
   自分で作ったリポジトリは既定で Watch 済みです。
2. **Watch の通知がメールで届く設定になっている**
   https://github.com/settings/notifications → 「Subscriptions」の **Watching** で「Email」にチェック。
3. **送り先のメールアドレス**
   同じ画面の「Default notifications email」に表示されているアドレスに届きます。

同じアカウントの `product-scout` が毎朝立てている「[scout] … 商品の棚に変化」の Issue のメールが
届いていれば、1〜3 はすでに満たされています。

### テスト通知で動作確認

台帳に全件が既知として載っているため、普通に手動実行しても新規0件で Issue は立ちません。
疎通確認は **テスト通知** で行います（台帳は変わりません）:

Actions タブ → 「Fetch & Deploy Report」→「Run workflow」→ **`test_notify` にチェック** → Run。
またはコマンドで:

```powershell
& "C:\Users\DFLDXPT\Claude code\test\gh_cli_tmp\bin\gh.exe" workflow run fetch_and_deploy.yml --repo aikoshohin-hash/insurance-release-dashboard -f test_notify=true
```

件名に「【テスト】【保険リリース】…」を含むメールが届けば成功です。確認したらその Issue は Close してください。

### 運用

- 読んだ Issue は **Close** してください。未読管理の代わりになります
- 起票に失敗した日はワークフローが失敗扱いになり、GitHub の「Run failed」メールで気づけます
- 公開リポジトリの Issue なので、中身は公開ダッシュボードと同じ範囲（見出し・抽出した事実・原文URL）に留めています。
  見出しに `@` があると実在ユーザーへのメンションになるため、全角 `＠` に置き換えています

### 通知の判定ルール（notifier.py）

| ケース | 扱い |
|---|---|
| 台帳が無い初回 | 全件を既知として登録するだけ。通知しない |
| 台帳に1件も無い会社の初出 | 登録のみ（スクレイパーを直した社の過去記事が一斉に届くのを防ぐ） |
| リリース日付が14日より古い | 登録のみ（サイトがアーカイブを再掲した日の大量通知を防ぐ） |
| 周辺（事務サービス等）・除外 | 登録のみ。通知は商品リリースだけ |
| URL が変わっても会社名＋見出しが同じ | 既知扱い |
| 1日に30件を超えた | 上位30件だけ載せ、構造変更を疑う旨を注記 |

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
  notifier.py        新規検知と Issue 本文の生成
  html_report.py     ダッシュボード HTML 生成
  health_checker.py  取得ヘルスチェック
  exporter.py        Excel 出力
  scrapers/          各社スクレイパー
  data/
    enrichment.json  本文から抽出した事実のキャッシュ（Actions が書き戻す）
    seen.json        新規検知の台帳（Actions が書き戻す。消すと次回は初回ベースラインに戻る）
  .github/workflows/fetch_and_deploy.yml
```
