"""スタンドアロン HTML レポート生成モジュール v3

Streamlit風の洗練されたデザインでレスポンシブ対応。
サーバー不要、1ファイル完結（CSS/JS内蔵）。

v3 新機能:
  - データ更新ボタン (GitHub Actions 連携)
  - 更新ステータス表示
  - Excel ダウンロードリンク
  - GitHub Pages 対応メタデータ
"""

import os
import json
import logging
from datetime import datetime

from config import OUTPUT_DIR, CATEGORY_LABELS, DATE_FROM, DATE_TO

logger = logging.getLogger(__name__)

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>保険リリース ダッシュボード</title>
<style>
:root {
  --primary: #2F5496;
  --primary-light: #4472C4;
  --primary-bg: #f0f2f6;
  --card-bg: #ffffff;
  --text: #31333F;
  --text-light: #808495;
  --border: #e6e9ef;
  --shadow: 0 1px 3px rgba(0,0,0,0.08);
  --radius: 8px;
  --rank-s: #ff4b4b;
  --rank-a: #ffa62b;
  --rank-b: #21c354;
  --rank-c: #1c83e1;
  --rank-d: #808495;
}
*, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }
html { font-size: 15px; -webkit-text-size-adjust: 100%; }
body {
  font-family: "Source Sans Pro", -apple-system, BlinkMacSystemFont,
    "Segoe UI", "Hiragino Kaku Gothic ProN", "Noto Sans JP", sans-serif;
  background: var(--primary-bg);
  color: var(--text);
  line-height: 1.6;
  min-height: 100vh;
}

/* === レイアウト === */
.app { display: flex; min-height: 100vh; }
.sidebar {
  width: 260px;
  background: white;
  border-right: 1px solid var(--border);
  padding: 24px 20px;
  position: fixed;
  top: 0; left: 0; bottom: 0;
  overflow-y: auto;
  z-index: 100;
  transition: transform 0.3s ease;
}
.main {
  flex: 1;
  margin-left: 260px;
  padding: 24px 32px;
  max-width: 1100px;
}

/* サイドバー */
.sidebar .logo {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--primary);
  margin-bottom: 6px;
}
.sidebar .period {
  font-size: 0.75rem;
  color: var(--text-light);
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}
.sidebar h3 {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-light);
  margin: 16px 0 8px;
}
.sidebar select, .sidebar input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.87rem;
  color: var(--text);
  background: white;
  margin-bottom: 8px;
  outline: none;
  transition: border-color 0.2s;
}
.sidebar select:focus, .sidebar input:focus { border-color: var(--primary-light); }
.nav-item {
  display: block;
  width: 100%;
  padding: 9px 12px;
  border: none;
  background: transparent;
  text-align: left;
  font-size: 0.9rem;
  color: var(--text);
  cursor: pointer;
  border-radius: 6px;
  margin-bottom: 2px;
  transition: background 0.15s;
}
.nav-item:hover { background: var(--primary-bg); }
.nav-item.active { background: var(--primary-bg); color: var(--primary); font-weight: 600; }
.nav-count {
  float: right;
  background: var(--primary-bg);
  color: var(--text-light);
  font-size: 0.72rem;
  padding: 1px 7px;
  border-radius: 10px;
}
.nav-item.active .nav-count { background: white; color: var(--primary); }

/* モバイルメニュー */
.mobile-header {
  display: none;
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 52px;
  background: white;
  border-bottom: 1px solid var(--border);
  z-index: 200;
  padding: 0 16px;
  align-items: center;
}
.mobile-header .logo { font-weight: 700; color: var(--primary); }
.hamburger {
  width: 36px; height: 36px;
  border: none; background: transparent; cursor: pointer;
  display: flex; flex-direction: column; justify-content: center; gap: 5px;
}
.hamburger span { display:block; height:2px; width:20px; background:var(--text); border-radius:1px; }
.overlay {
  display: none;
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.3);
  z-index: 99;
}
.overlay.show { display: block; }

/* === メトリクス === */
.metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}
.metric {
  background: var(--card-bg);
  border-radius: var(--radius);
  padding: 18px 16px;
  box-shadow: var(--shadow);
}
.metric .label { font-size: 0.78rem; color: var(--text-light); margin-bottom: 4px; }
.metric .value { font-size: 1.7rem; font-weight: 700; color: var(--primary); }
.metric .sub { font-size: 0.72rem; color: var(--text-light); margin-top: 2px; }

/* === テーブルビュー === */
.table-wrap {
  background: var(--card-bg);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
  margin-bottom: 16px;
}
.table-wrap .section-title {
  padding: 14px 18px 10px;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text);
  border-bottom: 1px solid var(--border);
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
thead th {
  text-align: left;
  padding: 10px 14px;
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  color: var(--text-light);
  border-bottom: 2px solid var(--border);
  white-space: nowrap;
  position: sticky;
  top: 0;
  background: white;
}
tbody tr {
  border-bottom: 1px solid var(--border);
  transition: background 0.1s;
  cursor: pointer;
}
tbody tr:hover { background: #fafbfe; }
tbody td { padding: 11px 14px; vertical-align: top; }
.rank-cell {
  font-weight: 800;
  font-size: 0.9rem;
  width: 40px;
  text-align: center;
}
.rank-S { color: var(--rank-s); }
.rank-A { color: var(--rank-a); }
.rank-B { color: var(--rank-b); }
.rank-C { color: var(--rank-c); }
.rank-D { color: var(--rank-d); }
.score-cell { font-weight: 600; width: 50px; }
.stars-cell { color: #ffa62b; font-size: 0.8rem; white-space: nowrap; width: 80px; }
.company-cell { font-weight: 500; white-space: nowrap; width: 130px; }
.date-cell { color: var(--text-light); white-space: nowrap; width: 85px; font-size: 0.82rem; }
.title-cell { min-width: 200px; }
.title-cell a { color: var(--primary); text-decoration: none; }
.title-cell a:hover { text-decoration: underline; }
.tag {
  display: inline-block;
  background: #eef2f9;
  color: var(--primary);
  font-size: 0.7rem;
  padding: 1px 7px;
  border-radius: 3px;
  margin: 2px 2px 0 0;
}

/* 詳細行 */
.detail-tr td {
  padding: 0;
  border-bottom: 2px solid var(--primary-bg);
}
.detail-content {
  display: none;
  padding: 14px 18px 14px 54px;
  background: #fafbfe;
  font-size: 0.83rem;
  color: #555;
}
.detail-content.open { display: block; }
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 220px;
  gap: 16px;
}
.detail-grid .commentary {
  line-height: 1.7;
}
.detail-grid .commentary strong { color: var(--text); }
.score-breakdown { display: flex; flex-direction: column; gap: 5px; }
.sb-row {
  display: grid;
  grid-template-columns: 80px 1fr 30px;
  gap: 6px;
  align-items: center;
  font-size: 0.75rem;
}
.sb-label { color: var(--text-light); }
.sb-track { height: 6px; background: #e8ebf0; border-radius: 3px; overflow: hidden; }
.sb-fill { height: 100%; background: var(--primary-light); border-radius: 3px; }
.sb-val { color: var(--text); text-align: right; font-weight: 500; }

/* === チャート === */
.charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.chart-card {
  background: var(--card-bg);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 18px;
}
.chart-card h3 { font-size: 0.88rem; color: var(--text); margin-bottom: 14px; }
.hbar { display: flex; flex-direction: column; gap: 8px; }
.hbar-row { display: grid; grid-template-columns: 100px 1fr 40px; gap: 8px; align-items: center; font-size: 0.8rem; }
.hbar-label { text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text); }
.hbar-track { height: 18px; background: var(--primary-bg); border-radius: 4px; overflow: hidden; }
.hbar-fill { height: 100%; border-radius: 4px; }
.hbar-val { font-weight: 600; color: var(--text); }

/* === 新着ハイライト === */
.row-new {
  background: linear-gradient(90deg, #fff8e1 0%, #fffdf5 100%) !important;
  border-left: 3px solid #ffa62b;
}
.row-new:hover { background: #fff3cd !important; }
.badge-new {
  display: inline-block;
  background: #ff4b4b;
  color: white;
  font-size: 0.6rem;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  margin-left: 6px;
  letter-spacing: 0.5px;
  vertical-align: middle;
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%,100% { opacity: 1; }
  50% { opacity: 0.6; }
}
.new-divider {
  padding: 8px 18px;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--rank-a);
  background: #fff8e1;
  border-bottom: 1px solid #ffe0b2;
}
.metric-new .value { color: #ff4b4b !important; }

/* === 更新ボタン === */
.refresh-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}
.btn-refresh {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 10px 14px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s, transform 0.1s;
}
.btn-refresh:hover { background: var(--primary-light); }
.btn-refresh:active { transform: scale(0.98); }
.btn-refresh.loading {
  background: #999;
  pointer-events: none;
}
.btn-refresh .icon { font-size: 1rem; }
.btn-refresh.loading .icon { animation: spin 1s linear infinite; }
@keyframes spin { from{transform:rotate(0)} to{transform:rotate(360deg)} }
.refresh-status {
  margin-top: 8px;
  font-size: 0.72rem;
  color: var(--text-light);
  text-align: center;
  min-height: 18px;
}
.refresh-status.success { color: var(--rank-b); }
.refresh-status.error { color: var(--rank-s); }
.refresh-status.running { color: var(--rank-a); }
.btn-download {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 8px 14px;
  background: white;
  color: var(--primary);
  border: 1px solid var(--primary);
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  margin-top: 8px;
  transition: background 0.2s;
  text-decoration: none;
}
.btn-download:hover { background: var(--primary-bg); }
.gh-link {
  display: block;
  text-align: center;
  font-size: 0.7rem;
  color: var(--text-light);
  margin-top: 8px;
  text-decoration: none;
}
.gh-link:hover { color: var(--primary); }

/* === フッター === */
.footer { text-align: center; padding: 28px 0 20px; font-size: 0.72rem; color: var(--text-light); }

/* === レスポンシブ === */
@media (max-width: 900px) {
  .charts-grid { grid-template-columns: 1fr; }
  .detail-grid { grid-template-columns: 1fr; }
  .metrics { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 768px) {
  .sidebar { transform: translateX(-100%); }
  .sidebar.open { transform: translateX(0); box-shadow: 4px 0 20px rgba(0,0,0,0.15); }
  .mobile-header { display: flex; justify-content: space-between; }
  .main { margin-left: 0; padding: 68px 14px 14px; }
  .metrics { grid-template-columns: repeat(2, 1fr); gap: 8px; }
  .metric { padding: 12px; }
  .metric .value { font-size: 1.3rem; }
  table { font-size: 0.8rem; }
  thead th, tbody td { padding: 8px 10px; }
  .company-cell { width: auto; }
  .hbar-row { grid-template-columns: 70px 1fr 35px; font-size: 0.75rem; }
  .detail-content { padding-left: 18px; }
}
@media (max-width: 480px) {
  .metrics { grid-template-columns: repeat(2, 1fr); }
  .score-cell, .date-cell { display: none; }
  .table-wrap { overflow-x: auto; }
}
</style>
</head>
<body>
<div class="app">

  <!-- モバイルヘッダー -->
  <div class="mobile-header">
    <span class="logo">保険リリース</span>
    <button class="hamburger" onclick="toggleSidebar()">
      <span></span><span></span><span></span>
    </button>
  </div>
  <div class="overlay" id="overlay" onclick="toggleSidebar()"></div>

  <!-- サイドバー -->
  <div class="sidebar" id="sidebar">
    <div class="logo">保険リリース ダッシュボード</div>
    <div class="period">期間: <!--PERIOD--></div>

    <h3>ナビゲーション</h3>
    <button class="nav-item active" onclick="go('ranking')">
      総合ランキング <span class="nav-count" id="nc-all">0</span>
    </button>
    <button class="nav-item" onclick="go('catA')">
      お知らせ (A) <span class="nav-count" id="nc-A">0</span>
    </button>
    <button class="nav-item" onclick="go('catB')">
      ニュースリリース (B) <span class="nav-count" id="nc-B">0</span>
    </button>
    <button class="nav-item" onclick="go('catC')">
      プレスリリース (C) <span class="nav-count" id="nc-C">0</span>
    </button>
    <button class="nav-item" onclick="go('charts')">
      分析チャート
    </button>

    <h3>フィルター</h3>
    <input type="text" id="search" placeholder="キーワード検索..." oninput="refresh()">
    <select id="fRank" onchange="refresh()">
      <option value="">全ランク</option>
      <option value="S">S ランク</option>
      <option value="A">A ランク</option>
      <option value="B">B ランク</option>
      <option value="C">C ランク</option>
      <option value="D">D ランク</option>
    </select>
    <select id="fCompany" onchange="refresh()"></select>
    <label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;margin:6px 0;cursor:pointer">
      <input type="checkbox" id="fNewOnly" onchange="refresh()" style="accent-color:var(--rank-s)"> 新着のみ表示
    </label>

    <!-- データ更新セクション -->
    <div class="refresh-section">
      <button class="btn-refresh" id="btnRefresh" onclick="triggerRefresh()">
        <span class="icon">&#x21bb;</span> データ更新
      </button>
      <div class="refresh-status" id="refreshStatus"></div>

      <a class="btn-download" href="latest.xlsx" download id="btnDownload" style="display:none">
        &#x1F4E5; Excel ダウンロード
      </a>

      <a class="gh-link" id="ghLink" href="#" target="_blank" rel="noopener" style="display:none">
        GitHub Actions &rarr;
      </a>
    </div>

    <div style="margin-top:20px;padding-top:16px;border-top:1px solid var(--border);font-size:0.7rem;color:var(--text-light)">
      作成: <!--GENERATED-->
    </div>
  </div>

  <!-- メインコンテンツ -->
  <div class="main">

    <!-- メトリクス -->
    <div class="metrics">
      <div class="metric">
        <div class="label">総リリース数</div>
        <div class="value" id="m-total">0</div>
      </div>
      <div class="metric">
        <div class="label">S ランク</div>
        <div class="value" style="color:var(--rank-s)" id="m-srank">0</div>
      </div>
      <div class="metric">
        <div class="label">平均スコア</div>
        <div class="value" id="m-avg">0</div>
      </div>
      <div class="metric metric-new">
        <div class="label">新着 (3日以内)</div>
        <div class="value" id="m-new">0</div>
        <div class="sub" id="m-new-sub"></div>
      </div>
    </div>

    <!-- ページ -->
    <div id="page-ranking"></div>
    <div id="page-catA" style="display:none"></div>
    <div id="page-catB" style="display:none"></div>
    <div id="page-catC" style="display:none"></div>
    <div id="page-charts" style="display:none"></div>

    <div class="footer">保険リリース自動取得ツール v3</div>
  </div>
</div>

<script>
var DATA = /*DATA_JSON*/[];
var currentPage = 'ranking';
var GH_CONFIG = /*GH_CONFIG_JSON*/{"owner":"","repo":"","enabled":false};
var NEW_DAYS = 3; // 新着とみなす日数

// 日付パース
function parseDate(s){
  if(!s) return null;
  var m = s.match(/(\d{4})\D+(\d{1,2})\D+(\d{1,2})/);
  if(m) return new Date(parseInt(m[1]),parseInt(m[2])-1,parseInt(m[3]));
  return null;
}

// 新着判定
function isNew(e){
  var d = parseDate(e.date);
  if(!d) return false;
  var now = new Date();
  now.setHours(0,0,0,0);
  var diff = (now - d) / (1000*60*60*24);
  return diff <= NEW_DAYS;
}

// DATA各エントリに _isNew フラグを付与
DATA.forEach(function(e){ e._isNew = isNew(e); });

// 初期化
(function init(){
  var cs = {};
  DATA.forEach(function(e){ cs[e.company]=1; });
  var sel = document.getElementById('fCompany');
  sel.innerHTML = '<option value="">全会社</option>';
  Object.keys(cs).sort().forEach(function(c){
    var o = document.createElement('option');
    o.value=c; o.textContent=c; sel.appendChild(o);
  });
  updateMetrics();
  refresh();
})();

function updateMetrics(){
  document.getElementById('m-total').textContent = DATA.length;
  var s=0; DATA.forEach(function(e){ if(e.rank_label==='S') s++; });
  document.getElementById('m-srank').textContent = s;
  var sum=0; DATA.forEach(function(e){ sum+=e.score||0; });
  document.getElementById('m-avg').textContent = DATA.length? (sum/DATA.length).toFixed(1) : '0';
  // 新着カウント
  var nw=0; DATA.forEach(function(e){ if(e._isNew) nw++; });
  document.getElementById('m-new').textContent = nw;
  document.getElementById('m-new-sub').textContent = nw>0 ? 'NEW!' : '-';
  document.getElementById('nc-all').textContent = DATA.length;
  ['A','B','C'].forEach(function(c){
    var n=0; DATA.forEach(function(e){ if(e.cat_key===c) n++; });
    document.getElementById('nc-'+c).textContent = n;
  });
}

function getFiltered(catKey){
  var q = document.getElementById('search').value.toLowerCase();
  var r = document.getElementById('fRank').value;
  var c = document.getElementById('fCompany').value;
  var nOnly = document.getElementById('fNewOnly').checked;
  var result = DATA.filter(function(e){
    if(catKey && e.cat_key !== catKey) return false;
    if(r && e.rank_label !== r) return false;
    if(c && e.company !== c) return false;
    if(nOnly && !e._isNew) return false;
    if(q){
      var t = (e.title||'')+(e.company||'')+(e.commentary||'')+(e.product_type||'');
      if(t.toLowerCase().indexOf(q)===-1) return false;
    }
    return true;
  });
  // 新着を上に、その中でスコア降順
  result.sort(function(a,b){
    if(a._isNew !== b._isNew) return a._isNew ? -1 : 1;
    return (b.score||0) - (a.score||0);
  });
  return result;
}

function esc(s){ var d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }
function stars(n){ return '\u2605'.repeat(n)+'\u2606'.repeat(5-n); }
function rc(r){ return {S:'var(--rank-s)',A:'var(--rank-a)',B:'var(--rank-b)',C:'var(--rank-c)',D:'var(--rank-d)'}[r]||'var(--rank-d)'; }

function buildTable(entries, title){
  if(!entries.length) return '<div class="table-wrap"><div class="section-title">'+esc(title)+'</div><div style="padding:40px;text-align:center;color:var(--text-light)">該当データなし</div></div>';
  var newCount = entries.filter(function(e){return e._isNew;}).length;
  var titleSuffix = newCount>0 ? ' ('+entries.length+'件 / 新着'+newCount+'件)' : ' ('+entries.length+'件)';
  var h = '<div class="table-wrap"><div class="section-title">'+esc(title)+titleSuffix+'</div>';
  h += '<div style="overflow-x:auto"><table><thead><tr>';
  h += '<th>ランク</th><th>スコア</th><th>人気度</th><th>会社名</th><th>日付</th><th>見出し</th>';
  h += '</tr></thead><tbody>';
  var shownDivider = false;
  entries.forEach(function(e,i){
    // 新着と既存の区切り線
    if(!shownDivider && !e._isNew && newCount>0){
      h += '<tr><td colspan="6" class="new-divider">&#9660; 以前のニュース</td></tr>';
      shownDivider = true;
    }
    var id = currentPage+'_'+i;
    var url = e.url||'';
    var tHtml = url ? '<a href="'+url+'" target="_blank" rel="noopener">'+esc(e.title)+'</a>' : esc(e.title);
    var newBadge = e._isNew ? '<span class="badge-new">NEW</span>' : '';
    var tags = '';
    if(e.product_type) tags += '<span class="tag">'+esc(e.product_type)+'</span>';
    if(e.action_type) tags += '<span class="tag">'+esc(e.action_type)+'</span>';
    if(e.cat_label) tags += '<span class="tag">'+esc(e.cat_label)+'</span>';
    h += '<tr onclick="toggle(\''+id+'\')" class="'+(e._isNew?'row-new':'')+'">';
    h += '<td class="rank-cell rank-'+e.rank_label+'">'+e.rank_label+'</td>';
    h += '<td class="score-cell">'+e.score+'</td>';
    h += '<td class="stars-cell">'+stars(e.popularity||1)+'</td>';
    h += '<td class="company-cell">'+esc(e.company)+'</td>';
    h += '<td class="date-cell">'+esc(e.date)+'</td>';
    h += '<td class="title-cell">'+tHtml+newBadge+(tags?' <br>'+tags:'')+'</td>';
    h += '</tr>';
    // detail row
    var d = e.score_detail||{};
    h += '<tr class="detail-tr"><td colspan="6"><div class="detail-content" id="d-'+id+'">';
    h += '<div class="detail-grid"><div class="commentary">';
    if(e.commentary) h += '<strong>コメンタリー:</strong> '+esc(e.commentary)+'<br>';
    if(e.reason) h += '<strong>抽出理由:</strong> '+esc(e.reason);
    h += '</div><div class="score-breakdown">';
    h += '<div style="font-weight:600;font-size:0.78rem;margin-bottom:4px">スコア内訳</div>';
    h += sbRow('キーワード',d.keyword||0,30);
    h += sbRow('鮮度',d.recency||0,15);
    h += sbRow('一時払い',d.ichiji||0,15);
    h += sbRow('カテゴリ',d.category||0,15);
    h += sbRow('ブランド',d.brand||0,15);
    h += '</div></div></div></td></tr>';
  });
  h += '</tbody></table></div></div>';
  return h;
}

function sbRow(label,val,max){
  var pct = Math.min(100,(val/max)*100);
  return '<div class="sb-row"><div class="sb-label">'+label+'</div><div class="sb-track"><div class="sb-fill" style="width:'+pct+'%"></div></div><div class="sb-val">'+val+'</div></div>';
}

function toggle(id){
  var el = document.getElementById('d-'+id);
  if(el) el.classList.toggle('open');
}

function refresh(){
  document.getElementById('page-ranking').innerHTML = buildTable(getFiltered(null), '総合ランキング');
  document.getElementById('page-catA').innerHTML = buildTable(getFiltered('A'), 'カテゴリA: お知らせ');
  document.getElementById('page-catB').innerHTML = buildTable(getFiltered('B'), 'カテゴリB: ニュースリリース');
  document.getElementById('page-catC').innerHTML = buildTable(getFiltered('C'), 'カテゴリC: プレスリリース');
  renderCharts();
}

function go(page){
  currentPage = page;
  ['ranking','catA','catB','catC','charts'].forEach(function(p){
    document.getElementById('page-'+p).style.display = p===page?'block':'none';
  });
  document.querySelectorAll('.nav-item').forEach(function(el,i){
    el.classList.remove('active');
  });
  if(event && event.target) event.target.classList.add('active');
  if(page==='charts') renderCharts();
  // モバイル: サイドバー閉じる
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('overlay').classList.remove('show');
  window.scrollTo(0,0);
}

function toggleSidebar(){
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('overlay').classList.toggle('show');
}

function renderCharts(){
  var el = document.getElementById('page-charts');
  // ランク分布
  var rd={}; ['S','A','B','C','D'].forEach(function(r){rd[r]=0;});
  DATA.forEach(function(e){rd[e.rank_label]=(rd[e.rank_label]||0)+1;});
  var mxR=Math.max.apply(null,Object.values(rd).concat([1]));
  var colors = {S:'var(--rank-s)',A:'var(--rank-a)',B:'var(--rank-b)',C:'var(--rank-c)',D:'var(--rank-d)'};

  // 会社別
  var cd={}; DATA.forEach(function(e){cd[e.company]=(cd[e.company]||0)+1;});
  var cs=Object.entries(cd).sort(function(a,b){return b[1]-a[1];});
  var mxC=Math.max.apply(null,cs.map(function(x){return x[1];}).concat([1]));

  // 会社別平均
  var ca={}; DATA.forEach(function(e){if(!ca[e.company])ca[e.company]=[];ca[e.company].push(e.score||0);});
  var av=Object.entries(ca).map(function(x){return[x[0],x[1].reduce(function(a,b){return a+b;},0)/x[1].length];}).sort(function(a,b){return b[1]-a[1];});
  var mxA=Math.max.apply(null,av.map(function(x){return x[1];}).concat([1]));

  // 商品タイプ
  var pd={}; DATA.forEach(function(e){if(e.product_type)pd[e.product_type]=(pd[e.product_type]||0)+1;});
  var ps=Object.entries(pd).sort(function(a,b){return b[1]-a[1];});
  var mxP=Math.max.apply(null,ps.map(function(x){return x[1];}).concat([1]));

  var h = '<div class="charts-grid">';
  h += '<div class="chart-card"><h3>ランク分布</h3><div class="hbar">';
  ['S','A','B','C','D'].forEach(function(r){
    h += hbar(r+' ランク',rd[r],mxR,colors[r]);
  });
  h += '</div></div>';

  h += '<div class="chart-card"><h3>会社別リリース数</h3><div class="hbar">';
  cs.forEach(function(x){ h += hbar(x[0],x[1],mxC,'var(--primary-light)'); });
  h += '</div></div>';

  h += '<div class="chart-card"><h3>会社別 平均スコア</h3><div class="hbar">';
  av.forEach(function(x){ h += hbar(x[0],x[1].toFixed(1),mxA,'var(--rank-b)'); });
  h += '</div></div>';

  h += '<div class="chart-card"><h3>商品タイプ分布</h3><div class="hbar">';
  if(ps.length){ ps.forEach(function(x){ h += hbar(x[0],x[1],mxP,'var(--rank-a)'); }); }
  else { h += '<div style="color:var(--text-light);text-align:center;padding:20px">該当データなし</div>'; }
  h += '</div></div></div>';

  el.innerHTML = h;
}

function hbar(label,val,max,color){
  var pct=Math.min(100,(parseFloat(val)/max)*100);
  return '<div class="hbar-row"><div class="hbar-label">'+esc(label)+'</div><div class="hbar-track"><div class="hbar-fill" style="width:'+pct+'%;background:'+color+'"></div></div><div class="hbar-val">'+val+'</div></div>';
}

// === GitHub Actions データ更新 ===
(function initGH(){
  if(!GH_CONFIG.enabled) return;
  // Excelダウンロードリンク表示
  var dl = document.getElementById('btnDownload');
  if(dl) dl.style.display = 'flex';
  // GitHub Actionsリンク
  var gh = document.getElementById('ghLink');
  if(gh){
    gh.href = 'https://github.com/'+GH_CONFIG.owner+'/'+GH_CONFIG.repo+'/actions';
    gh.style.display = 'block';
  }
})();

function triggerRefresh(){
  var btn = document.getElementById('btnRefresh');
  var st = document.getElementById('refreshStatus');

  if(!GH_CONFIG.enabled || !GH_CONFIG.pat){
    // PATがない場合: GitHub Actionsページへ誘導
    if(GH_CONFIG.enabled){
      window.open('https://github.com/'+GH_CONFIG.owner+'/'+GH_CONFIG.repo+'/actions/workflows/fetch_and_deploy.yml','_blank');
      st.textContent = 'GitHub Actions ページで "Run workflow" をクリックしてください';
      st.className = 'refresh-status running';
    } else {
      st.textContent = 'GitHub連携未設定 - ローカルで python main.py を実行してください';
      st.className = 'refresh-status error';
    }
    return;
  }

  // PAT設定済みの場合: API経由でワークフロー実行
  btn.classList.add('loading');
  st.textContent = 'データ更新を開始しています...';
  st.className = 'refresh-status running';

  fetch('https://api.github.com/repos/'+GH_CONFIG.owner+'/'+GH_CONFIG.repo+'/actions/workflows/fetch_and_deploy.yml/dispatches',{
    method:'POST',
    headers:{
      'Accept':'application/vnd.github.v3+json',
      'Authorization':'token '+GH_CONFIG.pat,
      'Content-Type':'application/json'
    },
    body:JSON.stringify({ref:'main'})
  }).then(function(r){
    if(r.status===204){
      st.textContent = 'データ更新開始! 約5分後にページを再読込してください';
      st.className = 'refresh-status success';
      // 5分後に自動リロード
      setTimeout(function(){ location.reload(); }, 300000);
    } else {
      st.textContent = 'エラー('+r.status+') - GitHub Actionsページで手動実行してください';
      st.className = 'refresh-status error';
    }
    btn.classList.remove('loading');
  }).catch(function(e){
    st.textContent = 'ネットワークエラー - GitHub Actionsページで手動実行してください';
    st.className = 'refresh-status error';
    btn.classList.remove('loading');
  });
}
</script>
</body>
</html>"""


def generate_html_report(
    categorized: dict[str, list[dict]],
    filename: str | None = None,
    gh_owner: str = "",
    gh_repo: str = "",
) -> str:
    """スコアリング済みデータからスタンドアロンHTMLレポートを生成

    Args:
        categorized: カテゴリ別エントリデータ
        filename: 出力ファイル名 (省略時は自動生成)
        gh_owner: GitHubユーザー名 (GitHub Pages連携用)
        gh_repo: GitHubリポジトリ名 (GitHub Pages連携用)
    """

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if filename is None:
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    filepath = os.path.join(OUTPUT_DIR, filename)

    # 全エントリ統合
    all_entries = []
    for cat, entries in categorized.items():
        for e in entries:
            ec = {
                "title": e.get("title", ""),
                "company": e.get("company", ""),
                "date": e.get("date", ""),
                "url": e.get("url", ""),
                "category": e.get("category", ""),
                "cat_key": cat,
                "cat_label": CATEGORY_LABELS.get(cat, cat),
                "score": e.get("score", 0),
                "score_detail": e.get("score_detail", {}),
                "rank_label": e.get("rank_label", "D"),
                "popularity": e.get("popularity", 1),
                "product_type": e.get("product_type", ""),
                "action_type": e.get("action_type", ""),
                "commentary": e.get("commentary", ""),
                "reason": e.get("reason", ""),
            }
            all_entries.append(ec)
    all_entries.sort(key=lambda x: x.get("score", 0), reverse=True)

    json_data = json.dumps(all_entries, ensure_ascii=False)
    now = datetime.now().strftime("%Y/%m/%d %H:%M")
    period = f"{DATE_FROM} - {DATE_TO}"

    # GitHub連携設定
    gh_config = {
        "owner": gh_owner,
        "repo": gh_repo,
        "enabled": bool(gh_owner and gh_repo),
    }
    gh_config_json = json.dumps(gh_config, ensure_ascii=False)

    html = HTML_TEMPLATE
    html = html.replace("/*DATA_JSON*/[]", json_data)
    html = html.replace('/*GH_CONFIG_JSON*/{"owner":"","repo":"","enabled":false}', gh_config_json)
    html = html.replace("<!--PERIOD-->", period)
    html = html.replace("<!--GENERATED-->", now)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"HTMLレポート生成: {filepath}")
    return filepath
