"""Build the standalone, installable (PWA) site into ./public from src/app.html."""
import re, pathlib
root = pathlib.Path(__file__).parent
app = (root / "src/app.html").read_text(encoding="utf-8")
# use self-hosted MediaPipe files instead of the CDN
app = app.replace("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs", "./vendor/vision_bundle.mjs")
app = app.replace("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm/vision_wasm_internal.js", "./vendor/vision_wasm_internal.js")
app = app.replace("https://cdn.jsdelivr.net/npm/mp4-muxer@5.2.1/build/mp4-muxer.js", "./vendor/mp4-muxer.js")
app = app.replace("https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/ort.webgpu.min.js", "./vendor/ort.webgpu.min.js")
app = app.replace("https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/ort-wasm-simd-threaded.jsep.mjs", "./vendor/ort-wasm-simd-threaded.jsep.mjs")
app = app.replace("await loadScript(ORT_JS);", "await loadScript(new URL(ORT_JS,location.href).href);")
app = app.replace("ort.env.wasm.wasmPaths={mjs:ORT_MJS};", "ort.env.wasm.wasmPaths={mjs:new URL(ORT_MJS,location.href).href};")
app = app.replace("const {PoseLandmarker}=await import(VISION_URL);", "const {PoseLandmarker}=await import(new URL(VISION_URL,location.href).href);")
app = app.replace("wasmLoaderPath:WASM_LOADER", "wasmLoaderPath:new URL(WASM_LOADER,location.href).href")
head = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="スイング動画から骨格を検出し、テンポ・回転・頭の移動を診断するゴルフ動作解析アプリ。動画は端末の外に送信されません。">
<meta name="theme-color" content="#2F7A4D">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="SwingLab">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icon-192.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>
"""
tail = """<script>if('serviceWorker' in navigator)addEventListener('load',()=>navigator.serviceWorker.register('sw.js').catch(()=>{}));</script>
</body>
</html>
"""
# move <title>/<meta>/<link>/<style> block into head, rest into body
idx = app.index("</style>") + len("</style>")
html = head + app[:idx] + "\n</head>\n<body>\n" + app[idx:] + tail
(root / "public/index.html").write_text(html, encoding="utf-8")
print("built public/index.html", len(html))
