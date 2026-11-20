#!/usr/bin/env python3
"""Cut a long practice video (many swings in a row) into one clip per swing, with keypoints.

usage:
  python3 tools/split_swings.py VIDEO_OR_FOLDER [...] [--slow 1] [--no-rtm] [--force]

For each video it makes a folder "<name>_切り出し" next to the video:
  swing_01.mp4 / swing_01.json   one clip per swing (JSON uses the same layout as the monitor uploads)
  一覧.jpg                        the top of every swing side by side, to spot and delete bad cuts
A folder argument processes every video in it that has not been processed yet.

Needs: pip install mediapipe opencv-python onnxruntime rtmlib numpy
Models come from this repository (public/model). ffmpeg is used for the clips when installed.
"""
import argparse, glob, json, math, os, shutil, subprocess, sys
import numpy as np, cv2
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(HERE, "..", "public", "model")
POSE_TASK = os.path.join(MODEL_DIR, "pose_landmarker.wasm")  # MediaPipe pose model (renamed for GitHub Pages)
COCO2MP = [0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
VIDEO_EXT = (".mov", ".mp4", ".m4v", ".webm", ".avi", ".mkv")
BONES = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24), (23, 25), (25, 27), (24, 26), (26, 28)]


def rtm_model():
    """Rebuild the RTMPose ONNX file from the chunks the web app downloads."""
    parts = sorted(glob.glob(os.path.join(MODEL_DIR, "rtm.*.wasm")), key=lambda p: int(p.split(".")[-2]))
    if not parts:
        return None
    cache = os.path.join(HERE, ".cache")
    os.makedirs(cache, exist_ok=True)
    out = os.path.join(cache, "rtmpose_l256.onnx")
    if not os.path.exists(out):
        with open(out + ".tmp", "wb") as f:
            for p in parts:
                f.write(open(p, "rb").read())
        os.replace(out + ".tmp", out)
    return out


def landmarker():
    opts = vision.PoseLandmarkerOptions(base_options=BaseOptions(model_asset_path=POSE_TASK),
                                        running_mode=vision.RunningMode.VIDEO, num_poses=1,
                                        min_pose_detection_confidence=0.5, min_tracking_confidence=0.5)
    return vision.PoseLandmarker.create_from_options(opts)


def detect(lm, img, ms):
    H, W = img.shape[:2]
    r = lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)), ms)
    if not r.pose_landmarks:
        return None
    return np.array([[q.x * W, q.y * H, q.visibility] for q in r.pose_landmarks[0]], dtype=np.float32)


def smooth(x, n):
    if n <= 1:
        return x
    k = np.ones(n) / n
    pad = np.pad(x, (n // 2, n - 1 - n // 2), mode="edge")
    return np.convolve(pad, k, mode="valid")


def find_swings(path, slow):
    """Quick pass (~15 fps): returns the video info and a list of impact times."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError("動画を開けませんでした")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, round(fps / 15))
    ts, hand, sh, scale = [], [], [], []
    with landmarker() as lm:
        k = 0
        while True:
            if k % step:
                if not cap.grab():
                    break
                k += 1
                continue
            ok, img = cap.read()
            if not ok:
                break
            t = k / fps
            p = detect(lm, img, int(t * 1000))
            if p is not None:
                ts.append(t)
                hand.append((p[15, :2] + p[16, :2]) / 2)
                sm, hm = (p[11, :2] + p[12, :2]) / 2, (p[23, :2] + p[24, :2]) / 2
                sh.append(sm[1])
                scale.append(np.linalg.norm(sm - hm))
            k += 1
            if n and k % (step * 150) == 0:
                print(f"  スイングを探しています… {min(100, round(k / n * 100))}%", flush=True)
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    dur = (n / fps) if n else (ts[-1] if ts else 0)
    cap.release()
    info = {"fps": fps, "W": W, "H": H, "dur": dur}
    if len(ts) < 10:
        return info, []
    ts, hand, sh = np.array(ts), np.array(hand), np.array(sh)
    L = float(np.median(scale)) or 1.0
    dt = np.diff(ts)
    v = np.r_[0, np.linalg.norm(np.diff(hand, axis=0), axis=1) / np.maximum(dt, 1e-3) / L]
    v[np.r_[False, dt > 0.5]] = 0  # no speed across gaps where nobody was detected
    v = smooth(v, 3) * slow  # body-lengths per second, in real time
    up = (sh - hand[:, 1]) / L  # > 0: hands above the shoulders
    cands = []
    for i in range(1, len(v) - 1):
        if v[i] < 6 or v[i] < v[i - 1] or v[i] < v[i + 1]:
            continue
        t = ts[i]
        before = (ts >= t - 1.8 * slow) & (ts < t)
        after = (ts > t) & (ts <= t + 1.8 * slow)
        if up[before].max(initial=-9) > 0.15 and up[after].max(initial=-9) > 0.15:
            cands.append((t, v[i]))
    swings = []  # keep the fastest peak within each 2.5 s window
    for t, s in sorted(cands, key=lambda c: -c[1]):
        if all(abs(t - u) > 2.5 * slow for u, _ in swings):
            swings.append((t, s))
    return info, sorted(t for t, _ in swings)


def windows(impacts, dur, slow):
    out = []
    for i, t in enumerate(impacts):
        a, b = t - 2.4 * slow, t + 1.8 * slow
        if i:
            a = max(a, (impacts[i - 1] + t) / 2)
        if i < len(impacts) - 1:
            b = min(b, (t + impacts[i + 1]) / 2)
        out.append((max(0.0, a), min(dur, b), t))
    return out


def write_clip(src, a, b, dst, W, H):
    k = min(1.0, 1920 / max(W, H))
    if shutil.which("ffmpeg"):
        vf = ["-vf", f"scale={round(W * k / 2) * 2}:{round(H * k / 2) * 2}"] if k < 1 else []
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", src, "-t", f"{b - a:.3f}", "-an", *vf,
               "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst]
        if subprocess.run(cmd).returncode == 0:
            return True
    return False


def clip_keypoints(src, a, b, fps, rtm, writer_path=None, W=0, H=0):
    """Full-rate pose for one clip. Writes the clip with OpenCV when writer_path is given (no ffmpeg)."""
    cap = cv2.VideoCapture(src)
    cap.set(cv2.CAP_PROP_POS_MSEC, a * 1000)
    wr = None
    if writer_path:
        k = min(1.0, 1920 / max(W, H))
        size = (round(W * k / 2) * 2, round(H * k / 2) * 2)
        for cc in ("avc1", "mp4v"):
            wr = cv2.VideoWriter(writer_path, cv2.VideoWriter_fourcc(*cc), fps, size)
            if wr.isOpened():
                break
    frames, imgs = [], {}
    with landmarker() as lm:
        k = 0
        while True:
            ok, img = cap.read()
            if not ok:
                break
            t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if t > b + 1e-3:
                break
            if t < a - 1e-3:
                continue
            if wr is not None:
                wr.write(cv2.resize(img, size) if size != (img.shape[1], img.shape[0]) else img)
            p = detect(lm, img, int(t * 1000) + k)  # +k keeps timestamps strictly increasing
            k += 1
            if p is not None and rtm is not None:
                x1, y1 = p[:, :2].min(0)
                x2, y2 = p[:, :2].max(0)
                h = y2 - y1
                try:
                    kp, sc = rtm(img, bboxes=[[x1 - 0.05 * h, y1 - 0.12 * h, x2 + 0.05 * h, y2 + 0.03 * h]])
                    for ci, mi in enumerate(COCO2MP):
                        if sc[0][ci] > 0.3:
                            p[mi] = [kp[0][ci][0], kp[0][ci][1], 1.0]
                except Exception as e:  # keep the MediaPipe result
                    print("  RTMPose:", e)
            frames.append({"t": round(t - a, 4), "p": None if p is None else [[round(float(x), 1), round(float(y), 1), round(float(c), 2)] for x, y, c in p]})
            imgs[len(frames) - 1] = img
            if len(imgs) > 600:  # keep memory bounded; only needed for the top-frame thumbnail
                imgs.pop(min(imgs))
    cap.release()
    if wr is not None:
        wr.release()
    return frames, imgs


def top_index(frames, impact_rel, slow):
    best, bi = 1e9, None
    for i, f in enumerate(frames):
        if f["p"] is None or not (impact_rel - 1.5 * slow <= f["t"] <= impact_rel):
            continue
        y = (f["p"][15][1] + f["p"][16][1]) / 2
        if y < best:
            best, bi = y, i
    return bi


def draw(img, p):
    img = img.copy()
    s = max(2, round(max(img.shape[:2]) / 400))
    for a, b in BONES:
        cv2.line(img, (int(p[a][0]), int(p[a][1])), (int(p[b][0]), int(p[b][1])), (106, 168, 201), s, cv2.LINE_AA)
    for j in (11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28):
        cv2.circle(img, (int(p[j][0]), int(p[j][1])), s * 2, (255, 255, 255), -1, cv2.LINE_AA)
    return img


def contact_sheet(tiles, path):
    if not tiles:
        return
    th = 360
    cells = []
    for label, img in tiles:
        h, w = img.shape[:2]
        im = cv2.resize(img, (max(1, round(w * th / h)), th))
        cv2.rectangle(im, (0, 0), (im.shape[1], 40), (20, 20, 20), -1)
        cv2.putText(im, label, (10, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
        cells.append(im)
    cw = max(c.shape[1] for c in cells)
    cols = min(5, len(cells))
    rows = math.ceil(len(cells) / cols)
    sheet = np.full((rows * (th + 8), cols * (cw + 8), 3), 30, np.uint8)
    for i, c in enumerate(cells):
        r, q = divmod(i, cols)
        sheet[r * (th + 8):r * (th + 8) + th, q * (cw + 8):q * (cw + 8) + c.shape[1]] = c
    ok, buf = cv2.imencode(".jpg", sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if ok:
        open(path, "wb").write(buf.tobytes())  # imwrite cannot handle non-ASCII paths on every platform


def process(path, slow, rtm, force):
    stem = os.path.splitext(os.path.basename(path))[0]
    out = os.path.join(os.path.dirname(os.path.abspath(path)), f"{stem}_切り出し")
    if os.path.isdir(out) and not force:
        print(f"{os.path.basename(path)}: 処理済みなのでスキップ（やり直すときは --force）")
        return
    print(f"{os.path.basename(path)}: スイングを探しています…", flush=True)
    info, impacts = find_swings(path, slow)
    print(f"  {len(impacts)} 回のスイングが見つかりました（動画 {info['dur']:.0f} 秒）", flush=True)
    if not impacts:
        return
    os.makedirs(out, exist_ok=True)
    tiles = []
    for n, (a, b, imp) in enumerate(windows(impacts, info["dur"], slow), 1):
        name = f"swing_{n:02d}"
        mp4 = os.path.join(out, name + ".mp4")
        ok = write_clip(path, a, b, mp4, info["W"], info["H"])
        frames, imgs = clip_keypoints(path, a, b, info["fps"], rtm, None if ok else mp4, info["W"], info["H"])
        meta = {"app": "SwingLab", "kind": "swing", "source": "split_swings", "video": os.path.basename(path),
                "clip": name + ".mp4", "start": round(a, 3), "end": round(b, 3), "impact": round(imp - a, 3),
                "fps": info["fps"], "slow": slow, "W": info["W"], "H": info["H"], "rtm": rtm is not None,
                "keypoints": "MediaPipe 33-point order, [x_px, y_px, visibility] in the original video's pixels",
                "frames": frames}
        with open(os.path.join(out, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
        ti = top_index(frames, imp - a, slow)
        if ti is not None and ti in imgs:
            tiles.append((f"{n:02d}  {int(imp // 60)}:{imp % 60:04.1f}", draw(imgs[ti], frames[ti]["p"])))
        print(f"  {name}  {a:.1f}〜{b:.1f} 秒", flush=True)
    contact_sheet(tiles, os.path.join(out, "一覧.jpg"))
    print(f"  → {out}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--slow", type=float, default=1, help="スロー撮影の倍率（1/4 スローなら 4）")
    ap.add_argument("--no-rtm", action="store_true", help="高精度モデル（RTMPose）を使わない")
    ap.add_argument("--force", action="store_true", help="処理済みの動画もやり直す")
    a = ap.parse_args()
    rtm = None
    if not a.no_rtm:
        try:
            from rtmlib import RTMPose
            m = rtm_model()
            if m:
                rtm = RTMPose(m, model_input_size=(192, 256), backend="onnxruntime", device="cpu")
        except Exception as e:
            print("RTMPose を使えないので MediaPipe だけで続けます:", e)
    vids = []
    for p in a.paths:
        if os.path.isdir(p):
            vids += sorted(os.path.join(p, f) for f in os.listdir(p) if f.lower().endswith(VIDEO_EXT) and not f.startswith("."))
        else:
            vids.append(p)
    if not vids:
        sys.exit("動画が見つかりませんでした")
    for v in vids:
        try:
            process(v, a.slow, rtm, a.force)
        except Exception as e:
            print(f"{os.path.basename(v)}: 失敗しました（{e}）")


if __name__ == "__main__":
    main()
