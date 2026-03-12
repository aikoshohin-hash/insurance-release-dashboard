# 保険会社リリース自動取得ツール v3 - セットアップ手順

## 動作環境
- Python 3.10 以上
- Windows / Mac / Linux

## インストール手順

### 1. Python の確認
```bash
python --version
```
Python 3.10以上が必要です。

### 2. 依存パッケージのインストール
```bash
cd insurance_release_fetcher
pip install -r requirements.txt
```

### 3. 動作確認
```bash
python main.py --list
```
対象13社の一覧が表示されれば成功です。

## 使い方

### 基本実行（全社取得 + スコアリング + Excel出力）
```bash
python main.py --no-gsheet
```

### 特定会社のみ
```bash
python main.py --company sumitomo meiji-yasuda --no-gsheet
```

### v2互換モード（スコアリングなし）
```bash
python main.py --simple --no-gsheet
```

### ダッシュボード起動
```bash
python main.py --dashboard
```
または
```bash
streamlit run dashboard.py
```
ブラウザで http://localhost:8501 を開く。

### スケジュール実行（毎日9時）
```bash
python main.py --schedule 09:00
```

## Google Sheets連携（任意）

1. Google Cloud Console でサービスアカウントを作成
2. JSONキーをダウンロードし `credentials.json` としてプロジェクトルートに配置
3. 対象スプレッドシートをサービスアカウントのメールと共有
4. `--no-gsheet` オプションを外して実行

## 出力ファイル
- `output/releases_YYYYMMDD_HHMMSS.xlsx` - Excel (3シート構成)
  - カテゴリ別一覧（ランク・スコア・コメンタリー付き）
  - 総合ランキング
  - サマリー

## Windows での注意事項
- コンソールの文字化け対策: 環境変数 `PYTHONIOENCODING=utf-8` を設定
  ```bash
  set PYTHONIOENCODING=utf-8
  python main.py --no-gsheet
  ```

## ファイル構成
```
insurance_release_fetcher/
  main.py              - メインエントリポイント (CLI)
  config.py            - 設定（対象会社・キーワード・期間）
  filter.py            - キーワードフィルタリング
  scorer.py            - スコアリング & ランキング
  analyzer.py          - 商品分析コメンタリー
  exporter.py          - Excel/CSV出力
  gsheet_uploader.py   - Google Sheets連携
  dashboard.py         - Streamlit WEBダッシュボード
  scheduler.py         - スケジュール実行
  requirements.txt     - 依存パッケージ
  scrapers/
    __init__.py        - スクレイパー登録
    base.py            - 基底クラス
    sumitomo.py        - 住友生命
    nissay.py          - 日本生命
    nissay_wealth.py   - ニッセイ・ウェルス生命
    taiju.py           - 大樹生命
    meiji_yasuda.py    - 明治安田生命
    ms_primary.py      - 三井住友海上プライマリー生命
    metlife.py         - メットライフ生命
    taiyo.py           - 太陽生命
    pgf.py             - PGF生命
    sonylife.py        - ソニー生命
    orix.py            - オリックス生命
    td_financial.py    - T&Dフィナンシャル生命
    manulife.py        - マニュライフ生命
  output/              - 出力先（自動作成）
```
