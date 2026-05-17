
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
syncthing_reporter_py — V2.1 | Build 2026-05-17 | Copyright Roman Glos 2026
- DE/EN in one script via REPORT_LANG=de|en
- Shows failed folder items from /rest/folder/errors
- Fixes missing HTML output for collected API/status errors
- Improves light/dark mail styling (best effort for Outlook and other clients)
- Adds color-scheme meta tags for clients that honor them
- TABLE_BYTES_METRIC is now used
"""
import os, sys, json, time, socket, pathlib, traceback, html, datetime as dt, re
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET
import requests

# ------------------------ Konfiguration ------------------------
SYNCTHING_URL = os.getenv("SYNCTHING_URL", "http://syncthing:8384").rstrip("/")
ST_CONFIG = os.getenv("ST_CONFIG", "/st-config/config.xml")
ST_API_KEY = os.getenv("ST_API_KEY", "").strip()
WINDOW_HOURS = int(os.getenv("WINDOW_HOURS", "24"))
REPORT_HOSTNAME = os.getenv("REPORT_HOSTNAME") or socket.gethostname()
REPORT_LANG = os.getenv("REPORT_LANG", "de").strip().lower()
if REPORT_LANG not in ("de", "en"):
    REPORT_LANG = "de"
REPORT_TITLE_PREFIX = os.getenv("REPORT_TITLE_PREFIX", "").strip()
REPORTER_VERSION = os.getenv("REPORTER_VERSION", "V2.1").strip() or "V2.1"
REPORTER_BUILD_DATE = os.getenv("REPORTER_BUILD_DATE", "2026-05-17").strip() or "2026-05-17"
REPORTER_COPYRIGHT = "Roman Glos 2026"
STATE_DIR = pathlib.Path(os.getenv("STATE_DIR", "/state"))
ATTACH_DIR = STATE_DIR / "attach"
ATTACH_DIR.mkdir(parents=True, exist_ok=True)

LOOKUP_FILE_SIZES = os.getenv("LOOKUP_FILE_SIZES", "1") in ("1","true","True","yes","YES")
CLASSIFY_BY_FIRST_SEEN = os.getenv("CLASSIFY_BY_FIRST_SEEN", "1") in ("1","true","True","yes","YES")
MERGE_ADD_CHANGE = os.getenv("MERGE_ADD_CHANGE", "1") in ("1","true","True","yes","YES")  # default on
HIDE_DIR_SIZES = os.getenv("HIDE_DIR_SIZES", "1") in ("1","true","True","yes","YES")
ZERO_SIZE_AS_DASH = os.getenv("ZERO_SIZE_AS_DASH", "1") in ("1","true","True","yes","YES")
TABLE_BYTES_METRIC = os.getenv("TABLE_BYTES_METRIC", "binary").strip().lower()
if TABLE_BYTES_METRIC not in ("binary", "decimal"):
    TABLE_BYTES_METRIC = "binary"
FOLDER_ERRORS_LIMIT = int(os.getenv("FOLDER_ERRORS_LIMIT", "250"))
FAILED_ITEMS_LIMIT = int(os.getenv("FAILED_ITEMS_LIMIT", "250"))

# Persistenter Cache
SIZE_CACHE_ENABLED = os.getenv("SIZE_CACHE_ENABLED", "1") in ("1","true","True","yes","YES")
SIZE_CACHE_FILE = pathlib.Path(os.getenv("SIZE_CACHE_FILE", str(STATE_DIR / "size_cache.json")))
SIZE_CACHE_TTL_DAYS = int(os.getenv("SIZE_CACHE_TTL_DAYS", "90"))
SIZE_CACHE_MAX_ENTRIES = int(os.getenv("SIZE_CACHE_MAX_ENTRIES", "200000"))

# Apprise / Mail (optional)
APPRISE_URL    = os.getenv("APPRISE_URL", "").strip()
APPRISE_TAG    = os.getenv("APPRISE_TAG", "all").strip()
APPRISE_URLS   = os.getenv("APPRISE_URLS", "").strip()
APPRISE_ENABLE = os.getenv("APPRISE_ENABLED", os.getenv("APPRISE_ENABLE", "1")).strip()

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_FROM = os.getenv("SMTP_FROM", "").strip()
SMTP_TO   = os.getenv("SMTP_TO", "").strip()
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").strip()
SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "1") in ("1","true","True","yes","YES")
SMTP_SSL      = os.getenv("SMTP_SSL", "0") in ("1","true","True","yes","YES")

FOLDER_NAME_MODE = os.getenv("FOLDER_NAME_MODE", "label-then-path").strip().lower()

# Local timezone (respects TZ env; falls back to system local tz)
_tz_name = os.getenv("TZ") or ""
try:
    LOCAL_TZ = ZoneInfo(_tz_name) if _tz_name else dt.datetime.now().astimezone().tzinfo
except Exception:
    LOCAL_TZ = dt.datetime.now().astimezone().tzinfo

session = requests.Session()
if ST_API_KEY:
    session.headers.update({"X-API-Key": ST_API_KEY})

I18N = {
    "de": {
        "title_prefix": "Syncthing Bericht",
        "section_status": "Ordnerstatus",
        "section_api_errors": "Status- und API-Fehler",
        "section_failed_summary": "Fehlgeschlagene Elemente",
        "section_failed_details": "Fehlerdetails",
        "section_changes": "Änderungen (letzte {hours}h)",
        "added_changed": "Hinzugefügt / Geändert",
        "added": "Hinzugefügt",
        "changed": "Geändert",
        "deleted": "Gelöscht",
        "folder": "Ordner",
        "files": "Dateien",
        "dirs": "Verzeichnisse",
        "total_size": "Gesamtgröße",
        "status": "Status",
        "pending": "Ausstehend",
        "failed_items": "Fehlgeschlagene Elemente",
        "date": "Datum",
        "time": "Uhrzeit",
        "path": "Pfad",
        "size": "Größe",
        "error": "Fehler",
        "errors": "Fehler",
        "count": "Anzahl",
        "permission_denied": "Zugriff verweigert",
        "example": "Beispiel",
        "period_badge": "Zeitraum: letzte {hours}h",
        "folders_badge": "Ordner: {count}",
        "errors_badge": "API-Fehler: {count}",
        "changes_badge": "Änderungen: {count}",
        "failed_badge": "Fehlgeschlagene Elemente: {count}",
        "permdenied_badge": "Zugriff verweigert: {count}",
        "generated_by": "Erstellt von syncthing_reporter_py",
        "none": "-",
        "cache": "Cache",
        "state_idle": "idle",
        "state_scanning": "scanning",
        "state_syncing": "syncing",
        "state_unknown": "unbekannt",
        "state_paused": "pausiert",
        "details_first_n": "erste {count} Einträge",
        "live_recording": "laufende Aufnahme",
        "updated_n": "{count} Aktualisierungen",
        "path_empty": "Keine Einträge",
    },
    "en": {
        "title_prefix": "Syncthing Report",
        "section_status": "Folder status",
        "section_api_errors": "Status and API errors",
        "section_failed_summary": "Failed items",
        "section_failed_details": "Error details",
        "section_changes": "Changes (last {hours}h)",
        "added_changed": "Added / Changed",
        "added": "Added",
        "changed": "Changed",
        "deleted": "Deleted",
        "folder": "Folder",
        "files": "Files",
        "dirs": "Directories",
        "total_size": "Total size",
        "status": "Status",
        "pending": "Pending",
        "failed_items": "Failed items",
        "date": "Date",
        "time": "Time",
        "path": "Path",
        "size": "Size",
        "error": "Error",
        "errors": "Errors",
        "count": "Count",
        "permission_denied": "Permission denied",
        "example": "Example",
        "period_badge": "Period: last {hours}h",
        "folders_badge": "Folders: {count}",
        "errors_badge": "API errors: {count}",
        "changes_badge": "Changes: {count}",
        "failed_badge": "Failed items: {count}",
        "permdenied_badge": "Permission denied: {count}",
        "generated_by": "Generated by syncthing_reporter_py",
        "none": "-",
        "cache": "Cache",
        "state_idle": "idle",
        "state_scanning": "scanning",
        "state_syncing": "syncing",
        "state_unknown": "unknown",
        "state_paused": "paused",
        "details_first_n": "first {count} entries",
        "live_recording": "live recording",
        "updated_n": "{count} updates",
        "path_empty": "No entries",
    }
}

def tr(key, **kwargs):
    txt = I18N.get(REPORT_LANG, I18N["de"]).get(key, key)
    return txt.format(**kwargs) if kwargs else txt


def reporter_meta_suffix(sep=" · "):
    parts = []
    if REPORTER_VERSION:
        parts.append(REPORTER_VERSION)
    if REPORTER_BUILD_DATE:
        parts.append(f"Build {REPORTER_BUILD_DATE}")
    return sep.join(parts)


def reporter_footer_line(hostname):
    parts = [tr("generated_by"), hostname]
    meta = reporter_meta_suffix()
    if meta:
        parts.append(meta)
    if REPORTER_COPYRIGHT:
        parts.append(f"Copyright {REPORTER_COPYRIGHT}")
    return " - ".join(parts[:2]) + (" · " + " · ".join(parts[2:]) if len(parts) > 2 else "")

if not REPORT_TITLE_PREFIX:
    REPORT_TITLE_PREFIX = tr("title_prefix")


def log(msg):
    ts = dt.datetime.now(LOCAL_TZ).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def human_bytes(n):
    try:
        n = int(n)
    except Exception:
        return str(n)
    if TABLE_BYTES_METRIC == "decimal":
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        base = 1000.0
    else:
        units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
        base = 1024.0
    s = float(n)
    for u in units:
        if abs(s) < base:
            return f"{s:,.2f} {u}".replace(",", " ")
        s /= base
    return f"{s*base:,.2f} {units[-1]}".replace(",", " ")

def parse_rfc3339(ts):
    try:
        if isinstance(ts, str) and ts.endswith('Z'):
            ts = ts[:-1] + '+00:00'
        return dt.datetime.fromisoformat(ts)
    except Exception:
        return None

def to_local_dt(value):
    if isinstance(value, str):
        d = parse_rfc3339(value)
    else:
        d = value
    if not isinstance(d, dt.datetime):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(LOCAL_TZ)

def fmt_date(value):
    d = to_local_dt(value)
    return d.strftime("%d.%m.%Y") if d else str(value)

def fmt_time(value):
    d = to_local_dt(value)
    return d.strftime("%H:%M:%S") if d else ""

# ------------------------ Cache ------------------------
_SIZE_CACHE = {}
def _cache_key(fid, item):
    return f"{fid}:::{item}"

def _utc_now_iso_seconds():
    # tz-aware UTC (Python 3.12+ Empfehlung)
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def cache_load():
    global _SIZE_CACHE
    if not SIZE_CACHE_ENABLED:
        _SIZE_CACHE = {}
        return
    try:
        if SIZE_CACHE_FILE.exists():
            raw = json.loads(SIZE_CACHE_FILE.read_text(encoding="utf-8"))
            # optional TTL prune
            cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=SIZE_CACHE_TTL_DAYS)
            if isinstance(raw, dict):
                if SIZE_CACHE_TTL_DAYS > 0:
                    pruned = {}
                    for k, v in raw.items():
                        ts = v.get("ts")
                        try:
                            dv = dt.datetime.fromisoformat(str(ts))
                        except Exception:
                            dv = None
                        if dv is None or dv.tzinfo is None:
                            # behandle alte Einträge ohne TZ als UTC
                            try:
                                dv = dt.datetime.fromisoformat(str(ts)).replace(tzinfo=dt.timezone.utc)
                            except Exception:
                                dv = None
                        if dv and dv >= cutoff:
                            pruned[k] = v
                    _SIZE_CACHE = pruned
                else:
                    _SIZE_CACHE = raw
            else:
                _SIZE_CACHE = {}
        else:
            _SIZE_CACHE = {}
    except Exception as e:
        log(f"[warn] cache load failed: {e}")
        _SIZE_CACHE = {}

def cache_save():
    if not SIZE_CACHE_ENABLED:
        return
    try:
        data = _SIZE_CACHE
        # hard cap entries
        if len(data) > SIZE_CACHE_MAX_ENTRIES:
            # prune oldest
            items = sorted(data.items(), key=lambda kv: kv[1].get("ts",""))
            keep = dict(items[-SIZE_CACHE_MAX_ENTRIES:])
            data = keep
        tmp = SIZE_CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(SIZE_CACHE_FILE)
    except Exception as e:
        log(f"[warn] cache save failed: {e}")

def cache_put(fid, item, size, is_dir=False):
    if not SIZE_CACHE_ENABLED:
        return
    try:
        key = _cache_key(fid, item)
        _SIZE_CACHE[key] = {
            "size": int(size or 0),
            "is_dir": bool(is_dir),
            "ts": _utc_now_iso_seconds(),
        }
    except Exception:
        pass

def cache_get(fid, item):
    if not SIZE_CACHE_ENABLED:
        return 0, False, False
    key = _cache_key(fid, item)
    v = _SIZE_CACHE.get(key)
    if not v:
        return 0, False, False
    try:
        return int(v.get("size", 0)), bool(v.get("is_dir", False)), True
    except Exception:
        return 0, False, True

# ------------------------ Syncthing ------------------------
def get_api_key_from_config():
    if ST_API_KEY:
        return ST_API_KEY
    try:
        text = pathlib.Path(ST_CONFIG).read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"<apikey>(.*?)</apikey>", text, re.S | re.I)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return ""

def read_folders_from_config():
    folders = []
    try:
        tree = ET.parse(ST_CONFIG)
        root = tree.getroot()
        for f in root.findall(".//folder"):
            fid = (f.get("id") or "").strip()
            if not fid:
                continue
            label = (f.get("label") or "").strip()
            if not label:
                labnode = f.find("label")
                if labnode is not None and labnode.text:
                    label = labnode.text.strip()
            path_attr = (f.get("path") or "").strip()
            display = label or (pathlib.Path(path_attr).name if path_attr else fid)
            if FOLDER_NAME_MODE == "path" and path_attr:
                display = pathlib.Path(path_attr).name
            elif FOLDER_NAME_MODE == "id":
                display = fid
            folders.append({"id": fid, "label": label, "path": path_attr, "display": display})
    except Exception as e:
        log(f"[error] failed to read config: {e}")
    uniq, seen = [], set()
    for x in folders:
        if x["id"] not in seen:
            uniq.append(x); seen.add(x["id"])
    return uniq

def st_get(path, **params):
    url = f"{SYNCTHING_URL.rstrip('/')}{path}"
    resp = session.get(url, params=params, timeout=60)
    resp.raise_for_status()
    try:
        return resp.json()
    except Exception:
        return resp.text

def collect_status(folders):
    rows, errors = [], []
    for f in folders:
        fid = f["id"].strip()
        if not fid:
            continue
        try:
            js = st_get("/rest/db/status", folder=fid)
            rows.append({
                "display": f["display"],
                "id": fid,
                "globalFiles": js.get("globalFiles", 0),
                "globalDirectories": js.get("globalDirectories", 0),
                "globalBytes": js.get("globalBytes", 0),
                "needBytes": js.get("needBytes", 0),
                "inSyncBytes": js.get("inSyncBytes", 0),
                "state": js.get("state", ""),
            })
        except requests.HTTPError as he:
            errors.append({"folder": f["display"], "id": fid, "error": str(he)})
        except Exception as e:
            errors.append({"folder": f["display"], "id": fid, "error": str(e)})
    return rows, errors

def collect_folder_errors(folders):
    per_folder = {}
    api_errors = []
    for f in folders:
        fid = f["id"].strip()
        if not fid:
            continue
        try:
            js = st_get("/rest/folder/errors", folder=fid, page=1, perpage=FOLDER_ERRORS_LIMIT)
            errs = []
            if isinstance(js, dict):
                errs = js.get("errors", []) or []
            cleaned = []
            for e in errs[:FOLDER_ERRORS_LIMIT]:
                if not isinstance(e, dict):
                    cleaned.append({"path": "", "error": str(e)})
                    continue
                cleaned.append({
                    "path": (e.get("path") or e.get("file") or e.get("item") or ""),
                    "error": (e.get("error") or "").strip() or str(e),
                })
            per_folder[fid] = {
                "folder": f["display"],
                "id": fid,
                "errors": cleaned,
            }
        except requests.HTTPError as he:
            api_errors.append({"folder": f["display"], "id": fid, "error": str(he)})
        except Exception as e:
            api_errors.append({"folder": f["display"], "id": fid, "error": str(e)})
    return per_folder, api_errors

def _raw_action_to_kind(action):
    a = (action or "").lower()
    if a in ("delete", "deleted", "rm", "remove", "trash"):
        return "deleted"
    return "touched"

def _fetch_window_events(hours):
    try:
        evs = st_get("/rest/events", since=0, limit=100000)
        if isinstance(evs, dict) and "events" in evs:
            evs = evs.get("events", [])
        if not isinstance(evs, list):
            return []
        return evs
    except Exception as e:
        log(f"[warn] events read failed: {e}")
        return []

def _extract_size_from_event(data):
    for k in ("size","bytes","length","filesize","totalBytes","bytesTotal","numBytes","itemSize"):
        v = data.get(k)
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str):
            try:
                return int(float(v))
            except Exception:
                continue
    return 0

def _looks_like_live_recording(item):
    item_l = (item or "").lower()
    return item_l.endswith('.ts') or item_l.endswith('.m2ts')

def _merge_item_event(prev, rec, *, keep_latest=True):
    if not prev:
        base = dict(rec)
        base['updates'] = 1
        base['growing'] = False
        return base
    merged = dict(prev)
    prev_size = int(prev.get('size', 0) or 0)
    rec_size = int(rec.get('size', 0) or 0)
    merged['updates'] = int(prev.get('updates', 1)) + 1
    merged['growing'] = bool(prev.get('growing', False) or (rec_size >= prev_size and rec_size > 0 and prev_size > 0))
    if keep_latest:
        merged.update(rec)
        merged['updates'] = int(prev.get('updates', 1)) + 1
        merged['growing'] = bool(prev.get('growing', False) or (rec_size >= prev_size and rec_size > 0 and prev_size > 0))
    return merged

def collect_event_lists(hours):
    evs = _fetch_window_events(hours)
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    flat = []
    for ev in evs:
        ts = ev.get("time")
        dtobj = parse_rfc3339(ts) if isinstance(ts, str) else None
        if dtobj is not None:
            if dtobj.tzinfo is None:
                dtobj = dtobj.replace(tzinfo=dt.timezone.utc)
            if dtobj < since:
                continue
        t = ev.get("type")
        if t not in ("ItemFinished", "RemoteItemFinished", "LocalItemFinished"):
            continue
        data = ev.get("data", {}) or {}
        fid = data.get("folder", "") or data.get("folderID", "")
        if not fid:
            continue
        item = data.get("item") or data.get("path") or data.get("file") or data.get("name") or ""
        if not item:
            continue
        size = _extract_size_from_event(data)
        kind = _raw_action_to_kind(data.get("action") or data.get("event") or data.get("type"))
        flat.append({"time": dtobj, "fid": fid, "item": item, "size": int(size), "kind": kind})

    flat.sort(key=lambda r: (r["fid"], r["item"], r["time"] or dt.datetime.now(dt.timezone.utc)))
    result = {}
    seen_first = {}
    bucket_maps = {}

    for rec in flat:
        fid = rec["fid"]
        bucket = result.setdefault(fid, {"added": [], "changed": [], "deleted": []})
        maps = bucket_maps.setdefault(fid, {"added": {}, "changed": {}, "deleted": {}})
        key = (fid, rec["item"])

        if rec["kind"] == "deleted":
            csize, cisdir, from_cache = cache_get(fid, rec["item"])
            item_rec = {
                "time": rec["time"],
                "item": rec["item"],
                "size": csize,
                "is_dir": cisdir,
                "from_cache": from_cache,
                "updates": 1,
                "growing": False,
            }
            maps["deleted"][rec["item"]] = _merge_item_event(maps["deleted"].get(rec["item"]), item_rec, keep_latest=True)
            seen_first[key] = "deleted"
            continue

        if CLASSIFY_BY_FIRST_SEEN:
            if key not in seen_first:
                item_rec = {"time": rec["time"], "item": rec["item"], "size": rec["size"], "is_dir": False}
                maps["added"][rec["item"]] = _merge_item_event(maps["added"].get(rec["item"]), item_rec, keep_latest=False)
                seen_first[key] = "added"
            else:
                item_rec = {"time": rec["time"], "item": rec["item"], "size": rec["size"], "is_dir": False}
                maps["changed"][rec["item"]] = _merge_item_event(maps["changed"].get(rec["item"]), item_rec, keep_latest=True)
        else:
            item_rec = {"time": rec["time"], "item": rec["item"], "size": rec["size"], "is_dir": False}
            maps["changed"][rec["item"]] = _merge_item_event(maps["changed"].get(rec["item"]), item_rec, keep_latest=True)

        if rec["size"] and rec["size"] > 0:
            cache_put(fid, rec["item"], rec["size"], is_dir=False)

    for fid, maps in bucket_maps.items():
        result[fid]["added"] = sorted(maps["added"].values(), key=lambda x: x.get("time") or dt.datetime.min.replace(tzinfo=dt.timezone.utc))
        result[fid]["changed"] = sorted(maps["changed"].values(), key=lambda x: x.get("time") or dt.datetime.min.replace(tzinfo=dt.timezone.utc))
        result[fid]["deleted"] = sorted(maps["deleted"].values(), key=lambda x: x.get("time") or dt.datetime.min.replace(tzinfo=dt.timezone.utc))

    return result

def fetch_size_via_db_file(fid, item):
    csize, cisdir, from_cache = cache_get(fid, item)
    if from_cache and csize > 0:
        return {"size": csize, "is_dir": cisdir, "from_cache": True}
    if not LOOKUP_FILE_SIZES:
        return {"size": csize, "is_dir": cisdir, "from_cache": from_cache}
    url = f"{SYNCTHING_URL.rstrip('/')}/rest/db/file"
    try:
        r = session.get(url, params={"folder": fid, "file": item}, timeout=30)
        if r.status_code != 200:
            return {"size": csize, "is_dir": cisdir, "from_cache": from_cache}
        js = r.json()
        type_val = (js.get("type") or js.get("filetype") or "").lower()
        if not type_val and isinstance(js.get("global"), dict):
            type_val = (js["global"].get("type") or js["global"].get("filetype") or "").lower()
        if not type_val and isinstance(js.get("local"), dict):
            type_val = (js["local"].get("type") or js["local"].get("filetype") or "").lower()
        is_dir = type_val in ("dir", "directory", "folder")
        size_candidates = []
        raw_size = js.get("size")
        if raw_size is not None:
            size_candidates.append(raw_size)
        for k in ("global", "local", "file", "summary"):
            if isinstance(js.get(k), dict):
                cand = js[k].get("size")
                if cand is not None:
                    size_candidates.append(cand)
        size = 0
        for v in size_candidates:
            if isinstance(v, (int, float)):
                size = int(v); break
            if isinstance(v, str):
                try: size = int(float(v)); break
                except Exception: pass
        if size > 0 or is_dir:
            cache_put(fid, item, size, is_dir=is_dir)
        return {"size": int(size or 0), "is_dir": is_dir, "from_cache": False}
    except Exception:
        return {"size": csize, "is_dir": cisdir, "from_cache": from_cache}

# ------------------------ HTML & Versand ------------------------
LINES_CSS = [
    "body { font-family: Segoe UI, Calibri, Arial, sans-serif; margin:0; padding:0; background:#0b1220; color:#eef3ff; }",
    ".container { max-width: 980px; margin: 0 auto; padding: 24px; }",
    ".card { background:#121a2b; border:1px solid #23314d; border-radius:12px; padding:18px; margin-bottom:16px; }",
    "h1 { margin:0 0 8px 0; font-size:22px; }",
    ".muted { color:#9cb3d8; }",
    ".badges { display:flex; gap:10px; flex-wrap:wrap; margin:8px 0 0 0;}",
    ".badge { background:#263040; border-radius:999px; padding:6px 10px; font-size:12px; }",
    "table { width:100%; border-collapse:collapse; }",
    "th, td { padding:10px 8px; border-bottom:1px solid #23314d; text-align:left; }",
    "th { font-size:12px; color:#9cb3d8; font-weight:600; text-transform:uppercase; letter-spacing:0.04em; }",
    ".ok { color:#a2f5a2; }",
    ".warn { color:#ffcd7a; }",
    ".err { color:#ff8a8a; }",
    ".footer { color:#9cb3d8; font-size:12px; margin-top:12px; }",
    ".subtle { color:#cdd8f0; font-weight:600; margin: 2px 0 6px 0; }",
    ".grid { border:1px solid #23314d; border-radius:10px; overflow:hidden; }",
    ".grid thead th { background:#0f1729; }",
    ".grid tbody tr:nth-child(odd) { background:#0e1627; }",
    ".grid tbody tr:nth-child(even) { background:#101a2c; }",
    ".num { text-align:right; font-variant-numeric: tabular-nums; }",
    ".nowrap { white-space:nowrap; }",
    ".tag { color:#9cb3d8; font-size:11px; margin-left:6px; }",
]


def render_html(hostname, rows, status_errors, folder_errors, changes_detail, window_hours):
    """Rendert eine Outlook-freundliche HTML-Mail im Stil des Nextcloud-Reports.

    Wichtig für Outlook Dark Mode: Der HTML-Code ist bewusst als schlanker
    Mail-Body ohne erzwungenen dunklen Seitenhintergrund aufgebaut. Genau wie
    beim Nextcloud-entrypoint kann Outlook die hellen Tabellen-/Rahmenfarben
    dadurch sauber in den Dark Mode umsetzen.
    """
    now = dt.datetime.now(LOCAL_TZ).strftime("%d.%m.%Y %H:%M:%S")
    report_date = dt.datetime.now(LOCAL_TZ).strftime("%d.%m.%Y")
    meta_suffix = reporter_meta_suffix()
    header_meta = f"{now} · {meta_suffix}" if meta_suffix else now

    rows = rows or []
    status_errors = status_errors or []
    folder_errors = folder_errors or {}
    changes_detail = changes_detail or {}

    total_folders = len(rows)
    total_status_errors = len(status_errors)
    total_failed_items = sum(len(v.get("errors", [])) for v in folder_errors.values())
    total_permission_denied = sum(
        1
        for v in folder_errors.values()
        for e in v.get("errors", [])
        if "permission denied" in (e.get("error", "").lower())
    )
    total_changes = sum(
        len(dd.get("added", [])) + len(dd.get("changed", [])) + len(dd.get("deleted", []))
        for dd in changes_detail.values()
    )
    total_pending_bytes = sum(int(r.get("needBytes", 0) or 0) for r in rows)
    has_errors = bool(total_status_errors or total_failed_items or total_permission_denied)

    # Palette absichtlich wie im nc_inotify_sync-entrypoint: helle Mailfarben,
    # damit Outlook Desktop sie im Dark Mode selbst invertieren kann.
    C = {
        "text": "#111827",
        "muted": "#6b7280",
        "line": "#e5e7eb",
        "head": "#f9fafb",
        "soft": "#f3f4f6",
        "ok": "#008000",
        "warn": "#b45309",
        "err": "#e11d48",
        "blue": "#2563eb",
    }

    def esc(v):
        return html.escape("" if v is None else str(v))

    def count_fmt(v):
        try:
            return f"{int(v):,}".replace(",", " ")
        except Exception:
            return str(v)

    def state_label(state):
        s = (state or "").strip().lower()
        return {
            "idle": tr("state_idle"),
            "scanning": tr("state_scanning"),
            "syncing": tr("state_syncing"),
            "paused": tr("state_paused"),
            "": tr("state_unknown"),
        }.get(s, state or tr("state_unknown"))

    def state_color(state, need_bytes=0, failed_items=0):
        s = (state or "").strip().lower()
        need = int(need_bytes or 0)
        failed = int(failed_items or 0)
        if failed > 0 or need > 0:
            return C["err"]
        if s in ("idle", "scanning"):
            return C["ok"]
        if s in ("syncing", "paused"):
            return C["warn"]
        return C["warn"]

    def td(value, *, align="left", color=None, weight="400", width=None, nowrap=False, extra=""):
        w = f"width:{width};" if width else ""
        ws = "white-space:nowrap;" if nowrap else ""
        return (
            f'<td style="padding:7px 8px; border-bottom:1px solid {C["line"]}; '
            f'color:{color or C["text"]}; text-align:{align}; vertical-align:top; '
            f'font-size:14px; line-height:1.35; font-weight:{weight}; {w}{ws}{extra}">{value}</td>'
        )

    def th(value, *, align="left", width=None, nowrap=False):
        w = f"width:{width};" if width else ""
        ws = "white-space:nowrap;" if nowrap else ""
        return (
            f'<th align="{align}" style="padding:8px; background:{C["head"]}; '
            f'border-bottom:1px solid {C["line"]}; color:{C["text"]}; text-align:{align}; '
            f'font-size:13px; line-height:1.35; font-weight:700; {w}{ws}">{value}</th>'
        )

    def section_title(icon, title):
        return f'<h3 style="margin:16px 0 8px 0; font-size:18px; line-height:1.3; color:{C["text"]};">{icon} {title}</h3>'

    def summary_cell(label, value, icon="", color=None, right_border=True):
        border = f"border-right:1px solid {C['line']};" if right_border else ""
        return (
            f'<td style="padding:4px 12px; {border} white-space:nowrap; color:{C["text"]}; '
            f'font-size:14px; line-height:1.35;">'
            f'<strong style="color:{color or C["text"]};">{icon} {esc(label)}:</strong> '
            f'<strong>{esc(value)}</strong></td>'
        )

    def summary_box():
        status_title = "Mit Fehlern" if has_errors else "OK"
        status_emoji = "⚠️" if has_errors else "✅"
        status_color = C["err"] if has_errors else C["ok"]
        return f"""
        <div style="padding:12px; border:1px solid {C['line']}; border-radius:10px; margin:10px 0 14px 0;">
          <div style="font-weight:700; margin-bottom:8px; color:{status_color};">{status_emoji} Status: {esc(status_title)}</div>
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse; width:auto;">
            <tr>
              {summary_cell(tr('folders_badge', count=total_folders).split(': ', 1)[0], count_fmt(total_folders), '📁')}
              {summary_cell(tr('changes_badge', count=total_changes).split(': ', 1)[0], count_fmt(total_changes), '🔄')}
              {summary_cell(tr('pending'), human_bytes(total_pending_bytes), '⏳', C['err'] if total_pending_bytes else C['text'])}
              {summary_cell(tr('errors_badge', count=total_status_errors).split(': ', 1)[0], count_fmt(total_status_errors), '❗', C['err'] if total_status_errors else C['text'])}
              {summary_cell(tr('failed_badge', count=total_failed_items).split(': ', 1)[0], count_fmt(total_failed_items), '🚫', C['err'] if total_failed_items else C['text'])}
              {summary_cell(tr('permdenied_badge', count=total_permission_denied).split(': ', 1)[0], count_fmt(total_permission_denied), '🔒', C['err'] if total_permission_denied else C['text'], False)}
            </tr>
          </table>
        </div>
        """

    def status_table():
        if not rows:
            return f"{section_title('📁', esc(tr('section_status')))}<div style='color:{C['muted']};'>{esc(tr('path_empty'))}</div>"
        header = (
            "<tr>"
            + th(esc(tr("folder")), width="26%")
            + th(esc(tr("files")), align="right", nowrap=True)
            + th(esc(tr("dirs")), align="right", nowrap=True)
            + th(esc(tr("total_size")), align="right", nowrap=True)
            + th(esc(tr("status")), nowrap=True)
            + th(esc(tr("pending")), align="right", nowrap=True)
            + th(esc(tr("failed_items")), align="right", nowrap=True)
            + "</tr>"
        )
        body_rows = []
        for r in sorted(rows, key=lambda x: x.get("display", "").lower()):
            fid = r.get("id", "")
            need = int(r.get("needBytes", 0) or 0)
            failed = len(folder_errors.get(fid, {}).get("errors", []))
            scolor = state_color(r.get("state", ""), need, failed)
            body_rows.append(
                "<tr>"
                + td(f"<strong>{esc(r.get('display', ''))}</strong><br><span style='color:{C['muted']}; font-size:12px;'>{esc(fid)}</span>", extra="word-break:break-word;")
                + td(esc(count_fmt(r.get("globalFiles", 0))), align="right", nowrap=True)
                + td(esc(count_fmt(r.get("globalDirectories", 0))), align="right", nowrap=True)
                + td(esc(human_bytes(r.get("globalBytes", 0))), align="right", nowrap=True)
                + td(esc(state_label(r.get("state", ""))), color=scolor, weight="700", nowrap=True)
                + td(esc(human_bytes(need)), align="right", color=C["ok"] if need == 0 else C["err"], weight="700", nowrap=True)
                + td(esc(count_fmt(failed)), align="right", color=C["ok"] if failed == 0 else C["err"], weight="700", nowrap=True)
                + "</tr>"
            )
        return f"""
        {section_title('📁', esc(tr('section_status')))}
        <table cellpadding="0" cellspacing="0" border="0" style="width:100%; border-collapse:collapse; border:1px solid {C['line']};">
          <thead>{header}</thead>
          <tbody>{''.join(body_rows)}</tbody>
        </table>
        """

    def api_errors_table():
        if not status_errors:
            return ""
        rows_html = []
        for e in status_errors:
            rows_html.append(
                "<tr>"
                + td(esc(e.get("folder", "")))
                + td(esc(e.get("id", "")))
                + td(esc(e.get("error", "")), color=C["err"], weight="700", extra="word-break:break-word;")
                + "</tr>"
            )
        header = "<tr>" + th(esc(tr("folder")), width="22%") + th("ID", width="16%") + th(esc(tr("error"))) + "</tr>"
        return f"""
        {section_title('❗', esc(tr('section_api_errors')))}
        <table cellpadding="0" cellspacing="0" border="0" style="width:100%; border-collapse:collapse; border:1px solid {C['line']};">
          <thead>{header}</thead><tbody>{''.join(rows_html)}</tbody>
        </table>
        """

    def failed_summary_table():
        folders_with_failed = [
            {
                "folder": v.get("folder", ""),
                "id": v.get("id", ""),
                "failed": len(v.get("errors", [])),
                "permission_denied": sum(1 for e in v.get("errors", []) if "permission denied" in (e.get("error", "").lower())),
                "example": next((e.get("path") or tr("none") for e in v.get("errors", []) if (e.get("path") or "").strip()), tr("none")),
                "errors": v.get("errors", []),
            }
            for _, v in sorted(folder_errors.items(), key=lambda kv: kv[1].get("folder", "").lower())
            if v.get("errors")
        ]
        if not folders_with_failed:
            return ""
        summary_rows = []
        detail_rows = []
        for x in folders_with_failed:
            summary_rows.append(
                "<tr>"
                + td(f"<strong>{esc(x['folder'])}</strong><br><span style='color:{C['muted']}; font-size:12px;'>{esc(x['id'])}</span>", extra="word-break:break-word;")
                + td(esc(count_fmt(x["failed"])), align="right", color=C["err"], weight="700", nowrap=True)
                + td(esc(count_fmt(x["permission_denied"])), align="right", color=C["err"] if x["permission_denied"] else C["ok"], weight="700", nowrap=True)
                + td(esc(x["example"]), extra="word-break:break-word;")
                + "</tr>"
            )
            for e in x["errors"][:FAILED_ITEMS_LIMIT]:
                detail_rows.append(
                    "<tr>"
                    + td(f"<strong>{esc(x['folder'])}</strong><br><span style='color:{C['muted']}; font-size:12px;'>{esc(x['id'])}</span>", width="24%", extra="word-break:break-word;")
                    + td(esc(e.get("path", "")), extra="word-break:break-word;")
                    + td(esc(e.get("error", "")), color=C["err"], weight="700", extra="word-break:break-word;")
                    + "</tr>"
                )
        summary_header = "<tr>" + th(esc(tr("folder")), width="24%") + th(esc(tr("failed_items")), align="right", nowrap=True) + th(esc(tr("permission_denied")), align="right", nowrap=True) + th(esc(tr("example"))) + "</tr>"
        detail_html = ""
        if detail_rows:
            detail_header = "<tr>" + th(esc(tr("folder")), width="24%") + th(esc(tr("path"))) + th(esc(tr("error"))) + "</tr>"
            detail_html = f"""
            <h3 style="margin:16px 0 8px 0; font-size:17px; color:{C['text']};">{esc(tr('section_failed_details'))}</h3>
            <table cellpadding="0" cellspacing="0" border="0" style="width:100%; border-collapse:collapse; border:1px solid {C['line']};">
              <thead>{detail_header}</thead><tbody>{''.join(detail_rows)}</tbody>
            </table>
            """
        return f"""
        {section_title('🚫', esc(tr('section_failed_summary')))}
        <table cellpadding="0" cellspacing="0" border="0" style="width:100%; border-collapse:collapse; border:1px solid {C['line']};">
          <thead>{summary_header}</thead><tbody>{''.join(summary_rows)}</tbody>
        </table>
        {detail_html}
        """

    def detail_item_row(fid, it, action_label, action_color, deleted=False):
        when = it.get("time", "")
        size_val = int(it.get("size", 0) or 0)
        is_dir = bool(it.get("is_dir", False))
        info_used_cache = False
        if (size_val == 0) and (not deleted):
            info = fetch_size_via_db_file(fid, it.get("item", ""))
            if info["size"] > 0 or info["is_dir"]:
                size_val = info["size"]
                is_dir = info["is_dir"]
                info_used_cache = info["from_cache"]
        if is_dir and HIDE_DIR_SIZES:
            size_txt = tr("none")
        elif size_val > 0:
            size_txt = human_bytes(size_val)
        elif ZERO_SIZE_AS_DASH:
            size_txt = tr("none")
        else:
            size_txt = "0.00 B"
        tags = []
        if deleted and size_val > 0:
            tags.append(tr("cache"))
        elif info_used_cache:
            tags.append(tr("cache"))
        updates = int(it.get("updates", 1) or 1)
        if updates > 1:
            tags.append(tr("updated_n", count=updates))
        if it.get("growing") and _looks_like_live_recording(it.get("item", "")):
            tags.append(tr("live_recording"))
        tag_html = f"<br><span style='color:{C['muted']}; font-size:12px;'>{esc(' · '.join(tags))}</span>" if tags else ""
        when_txt = f"{fmt_date(when)} {fmt_time(when)}".strip() or tr("none")
        return (
            "<tr>"
            + td(esc(when_txt), nowrap=True, color=C["muted"])
            + td(esc(action_label), color=action_color, weight="700", nowrap=True)
            + td(esc(it.get("item", "")) + tag_html, extra="word-break:break-word;")
            + td(esc(size_txt), align="right", nowrap=True)
            + "</tr>"
        )

    def changes_table_for_folder(fid, dd):
        rows_html = []
        if MERGE_ADD_CHANGE:
            merged = dd.get("added", []) + dd.get("changed", [])
            merged.sort(key=lambda it: (to_local_dt(it.get("time")) or dt.datetime.min.replace(tzinfo=LOCAL_TZ)))
            for it in merged[:200]:
                rows_html.append(detail_item_row(fid, it, tr("added_changed"), C["blue"], deleted=False))
        else:
            for it in dd.get("added", [])[:200]:
                rows_html.append(detail_item_row(fid, it, tr("added"), C["blue"], deleted=False))
            for it in dd.get("changed", [])[:200]:
                rows_html.append(detail_item_row(fid, it, tr("changed"), C["warn"], deleted=False))
        for it in dd.get("deleted", [])[:200]:
            rows_html.append(detail_item_row(fid, it, tr("deleted"), C["err"], deleted=True))
        if not rows_html:
            rows_html.append("<tr>" + td(esc(tr("path_empty")), color=C["muted"], extra="font-style:italic;") + td("") + td("") + td("") + "</tr>")
        action_header = "Aktion" if REPORT_LANG == "de" else "Action"
        header = "<tr>" + th(esc(tr("time")), width="145px", nowrap=True) + th(esc(action_header), width="150px", nowrap=True) + th(esc(tr("path"))) + th(esc(tr("size")), align="right", width="120px", nowrap=True) + "</tr>"
        return f"""
        <table cellpadding="0" cellspacing="0" border="0" style="width:100%; border-collapse:collapse; border:1px solid {C['line']};">
          <thead>{header}</thead><tbody>{''.join(rows_html)}</tbody>
        </table>
        """

    def changes_panel():
        if not changes_detail:
            return ""
        row_by_id = {r.get("id", ""): r for r in rows}
        out = section_title("📋", esc(tr("section_changes", hours=window_hours)))
        for fid, dd in sorted(changes_detail.items(), key=lambda kv: row_by_id.get(kv[0], {}).get("display", kv[0]).lower()):
            r = row_by_id.get(fid, {"display": fid, "id": fid})
            cnt = len(dd.get("added", [])) + len(dd.get("changed", [])) + len(dd.get("deleted", []))
            out += f"<h3 style='margin:14px 0 6px 0; font-size:16px; color:{C['text']};'>🔄 {esc(r.get('display', fid))} <span style='font-weight:400; color:{C['muted']};'>— {esc(count_fmt(cnt))} {esc(tr('count'))}</span></h3>"
            out += changes_table_for_folder(fid, dd)
        return out

    title = f"{REPORT_TITLE_PREFIX} {report_date} | Host: {hostname}"
    footer_text = reporter_footer_line(hostname)
    return f"""
<div style="font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif; font-size:14px; line-height:1.4; color:{C['text']};">
  <h2 style="margin:0 0 6px 0; font-size:24px; line-height:1.3; color:{C['text']};">{esc(title)}</h2>
  <div style="margin:0 0 12px 0; color:{C['muted']}; font-size:13px;">Erstellt: {esc(header_meta)} · Zeitraum: letzte {esc(window_hours)}h</div>
  {summary_box()}
  {status_table()}
  {api_errors_table()}
  {failed_summary_table()}
  {changes_panel()}
  <div style="color:{C['muted']}; margin-top:12px; font-size:12px; line-height:1.5;">{esc(footer_text)}</div>
</div>"""

def apprise_send(title, body_html):
    if APPRISE_ENABLE in ("0","false","False","no","NO") or not APPRISE_URL:
        return False, "Apprise disabled"
    try:
        import re
        candidates = [APPRISE_URL]
        if "?tag=" not in APPRISE_URL and "/tag/" not in APPRISE_URL:
            sep = "&" if "?" in APPRISE_URL else "?"
            candidates.append(f"{APPRISE_URL}{sep}tag={APPRISE_TAG}")
        base = APPRISE_URL.rstrip("/")
        if not base.endswith(f"/tag/{APPRISE_TAG}"):
            candidates.append(f"{base}/tag/{APPRISE_TAG}")
        urls_list = [u.strip() for u in re.split(r"[ ,]+", APPRISE_URLS) if u.strip()] if APPRISE_URLS else []
        json_payload = {"title": title, "body": body_html, "message": body_html, "type": "html", "format": "html"}
        if urls_list: json_payload["urls"] = urls_list
        form_data  = {"title": title, "body": body_html, "message": body_html, "type": "html", "format": "html"}
        if urls_list: form_data["urls"] = " ".join(urls_list)
        for target in candidates:
            r = session.post(target, json=json_payload, timeout=30)
            if r.status_code == 200: return True, f"APPRISE OK (json @ {target})"
            r2 = session.post(target, data=form_data, timeout=30)
            if r2.status_code == 200: return True, f"APPRISE OK (form @ {target})"
            form_min = {"title": title, "message": body_html, "type": "html", "format": "html"}
            if urls_list: form_min["urls"] = " ".join(urls_list)
            r3 = session.post(target, data=form_min, timeout=30)
            if r3.status_code == 200: return True, f"APPRISE OK (form-min @ {target})"
        return False, "APPRISE 400/failed on all endpoints"
    except Exception as e:
        return False, f"APPRISE error: {e}"

def smtp_send(title, body_html):
    missing = []
    if not SMTP_HOST: missing.append("SMTP_HOST")
    if not SMTP_FROM: missing.append("SMTP_FROM")
    if not SMTP_TO:   missing.append("SMTP_TO")
    if missing:
        return False, "SMTP not configured (missing: " + ", ".join(missing) + ")"
    try:
        import smtplib, ssl
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        msg = MIMEMultipart("alternative"); msg["Subject"]=title; msg["From"]=SMTP_FROM; msg["To"]=SMTP_TO
        msg.attach(MIMEText(body_html, "html", "utf-8"))
        if SMTP_SSL:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as s:
                if SMTP_USER: s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
                if SMTP_STARTTLS: s.starttls(context=ssl.create_default_context())
                if SMTP_USER: s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        return True, "SMTP OK"
    except Exception as e:
        return False, f"SMTP error: {e}"

def main():
    cache_load()
    print(f"[build] syncthing_reporter_py | version={REPORTER_VERSION} | build={REPORTER_BUILD_DATE} | copyright={REPORTER_COPYRIGHT}")
    key = get_api_key_from_config()
    if key and not session.headers.get("X-API-Key"):
        session.headers["X-API-Key"] = key

    folders = read_folders_from_config()
    rows, status_errors = collect_status(folders)
    folder_errors, folder_error_api_errors = collect_folder_errors(folders)
    if folder_error_api_errors:
        status_errors.extend(folder_error_api_errors)
    details = collect_event_lists(WINDOW_HOURS)

    html_doc = render_html(REPORT_HOSTNAME, rows, status_errors, folder_errors, details, WINDOW_HOURS)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = ATTACH_DIR / f"syncthing_report_{ts}.html"
    out_path.write_text(html_doc, encoding="utf-8")
    print(f"[{dt.datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M:%S')}] Wrote HTML: {out_path}")

    cache_save()

    title = f"{REPORT_TITLE_PREFIX} - {REPORT_HOSTNAME}"
    ok, msg = apprise_send(title, html_doc); print(f"[apprise] {msg}")
    ok2, msg2 = smtp_send(title, html_doc); print(f"[smtp] {msg2}")
    print("Done.")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
