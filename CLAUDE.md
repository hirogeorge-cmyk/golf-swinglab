# SwingLab 作業メモ

## 必ず守ること
- ユーザーへの返答・説明・報告は、**すべて日本語**で書く（英語で書いた場合は日本語に直してから伝える）。
- コミットメッセージやコード内のコメントは英語でもよい。

## 構成
- `src/app.html` … アプリ本体（編集するのはここ）
- `build.py` … `public/index.html` を生成（PWA 用の head、CDN を自前ファイルに置き換え）
- `public/` … GitHub Pages で配信する一式（`.github/workflows/pages.yml` が main への push で自動公開）
- 公開URL: https://hirogeorge-cmyk.github.io/golf-swinglab/

## 更新手順
1. `src/app.html` を編集
2. `public/sw.js` の `CACHE` 名（swinglab-vNN）を1つ上げる
3. `python3 build.py`
4. commit して `main` に push（1〜2分で公開サイトに反映）

## 方針メモ
- 動画は端末の外に送らない（解析・履歴はすべて端末内 / IndexedDB）
- 履歴の動画は ArrayBuffer で保存（iPhone のアプリ内ブラウザで Blob が読み戻せないため）
- 履歴の動画は「スイング部分だけ切り出し・画質は元のまま（長辺1920pxまで、高ビットレート）」で保存。小さくならない場合は元の動画のまま
- スイングプレーン・クラブヘッド追跡は一度試したが精度不足で取り下げ（2026-11）。再挑戦するならクラブ専用の学習モデルが必要
- 課金は「履歴10件まで無料、それ以上は月額」の方向（未実装）
