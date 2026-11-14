# SwingLab — ゴルフスイング動作解析

スイング動画を選ぶと、ブラウザ内（MediaPipe Pose）で骨格を検出し、
テンポ・トップの間・肩と腰の回転・頭の移動・体重移動などを P1/P4/P7/P10 ごとに診断します。

- **解析**: 動画に骨格・手の軌道を重ね、数値と診断を表示
- **元動画と並べる**: 元の動画と解析動画を同じ瞬間で左右に表示（`#check`）
- **お手本と比較**: 上手な人の動画と自分の動画を、アドレス・トップ・インパクト・フィニッシュで同期して並べ、数値の差を表示（`#compare`）
動画は端末の外へ送信されません。ホーム画面に追加すればアプリとして使え、2回目以降はオフラインでも動きます。

## 構成
- `src/app.html` … アプリ本体（編集するのはここ）
- `build.py` … `public/index.html` を生成（PWA 用の head と Service Worker 登録を付与）
- `public/` … 公開するフォルダ一式（静的ファイルのみ・サーバー不要）

## 更新手順
```
python3 build.py
```

## 公開方法（どれか一つ）
- **GitHub Pages**: このリポジトリを GitHub に置き、Pages の公開元を `public/` にする（Actions で配信）
- **Netlify Drop**: https://app.netlify.com/drop に `public` フォルダをドラッグ＆ドロップ
- **Cloudflare Pages / Vercel**: 出力ディレクトリに `public` を指定

HTTPS で配信されていれば、iPhone は Safari の「共有 → ホーム画面に追加」、Android は Chrome の「アプリをインストール」でアプリとして追加できます。

## 注意
- iPhone の HEVC（.mov）動画は Safari では解析できますが、一部の Android / PC の Chrome では再生できない場合があります。
- 数値は単眼カメラの2D映像からの推定です。回転角は低めに出る傾向があります。
