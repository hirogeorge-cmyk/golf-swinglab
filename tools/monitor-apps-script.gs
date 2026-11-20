/**
 * SwingLab monitor receiver (Google Apps Script web app).
 * Receives swings that monitor participants agreed to provide and stores them in the owner's Google Drive:
 *   マイドライブ / SwingLab_モニター / <participant name> / <date>_<id>.mp4 + .json
 * Deploy: Deploy > New deployment > Web app, Execute as: Me, Who has access: Anyone.
 * It only ever creates files inside SwingLab_モニター; it cannot list, read or delete anything.
 * To stop receiving: Deploy > Manage deployments > Archive.
 */
const ROOT_NAME = 'SwingLab_モニター';
const MAX_VIDEO_BYTES = 300 * 1024 * 1024;
const MAX_JSON_CHARS = 20 * 1024 * 1024;

function doGet() { return out_({ ok: true, app: 'swinglab-monitor' }); }

function doPost(e) {
  try {
    const q = JSON.parse(e.postData.contents);
    if (q.op === 'json') return out_(saveJson_(q));
    if (q.op === 'start') return out_(start_(q));
    if (q.op === 'chunk') return out_(chunk_(q));
    return out_({ ok: false, error: 'bad op' });
  } catch (err) {
    return out_({ ok: false, error: String(err) });
  }
}

function out_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

function clean_(s, n) {
  return String(s || '').replace(/[\\/:*?"<>|\u0000-\u001f]/g, '_').trim().slice(0, n || 60) || 'noname';
}

function folderFor_(person) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    let it = DriveApp.getFoldersByName(ROOT_NAME);
    const root = it.hasNext() ? it.next() : DriveApp.createFolder(ROOT_NAME);
    const name = clean_(person, 40);
    it = root.getFoldersByName(name);
    return it.hasNext() ? it.next() : root.createFolder(name);
  } finally {
    lock.releaseLock();
  }
}

function saveJson_(q) {
  const text = String(q.content || '');
  if (text.length > MAX_JSON_CHARS) return { ok: false, error: 'size' };
  const file = folderFor_(q.person).createFile(clean_(q.name, 100), text, 'application/json');
  return { ok: true, id: file.getId() };
}

// Opens a resumable Drive upload; the browser then sends the video in base64 chunks through chunk_().
function start_(q) {
  const size = Number(q.size);
  if (!(size > 0 && size <= MAX_VIDEO_BYTES)) return { ok: false, error: 'size' };
  const mime = /^video\/(mp4|quicktime|webm)$/.test(q.mime) ? q.mime : 'video/mp4';
  const folder = folderFor_(q.person);
  const res = UrlFetchApp.fetch('https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable', {
    method: 'post',
    contentType: 'application/json; charset=UTF-8',
    headers: {
      Authorization: 'Bearer ' + ScriptApp.getOAuthToken(),
      'X-Upload-Content-Type': mime,
      'X-Upload-Content-Length': String(size),
    },
    payload: JSON.stringify({ name: clean_(q.name, 100), parents: [folder.getId()] }),
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() !== 200) return { ok: false, error: 'start ' + res.getResponseCode() };
  const h = res.getHeaders();
  const url = h.Location || h.location;
  const key = Utilities.getUuid();
  CacheService.getScriptCache().put(key, JSON.stringify({ url: url, size: size }), 21600);
  return { ok: true, key: key };
}

function chunk_(q) {
  const cache = CacheService.getScriptCache();
  const c = cache.get(q.key);
  if (!c) return { ok: false, error: 'expired' };
  const s = JSON.parse(c);
  const bytes = Utilities.base64Decode(q.data);
  const from = Number(q.from), to = from + bytes.length - 1;
  if (!(from >= 0) || to >= s.size) return { ok: false, error: 'range' };
  const res = UrlFetchApp.fetch(s.url, {
    method: 'put',
    contentType: 'application/octet-stream',
    headers: { 'Content-Range': 'bytes ' + from + '-' + to + '/' + s.size },
    payload: bytes,
    muteHttpExceptions: true,
  });
  const code = res.getResponseCode();
  if (code === 308) return { ok: true, done: false };
  if (code === 200 || code === 201) {
    cache.remove(q.key);
    return { ok: true, done: true, id: JSON.parse(res.getContentText()).id };
  }
  return { ok: false, error: 'chunk ' + code };
}
