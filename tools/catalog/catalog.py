#!/usr/bin/env python3
"""
Portal1 Media Catalog — simple SQLite index for all captured media.

Storage layout:
  {MEDIA_ROOT}/
  ├── YYYY/MM/DD/              date-organized originals
  │   ├── 20260131_221826_snap.jpg
  │   ├── 20260131_221900_clip.mp4
  │   └── 20260131_222000_stream.mp4
  ├── thumbs/                  auto-generated thumbnails
  └── catalog.db               SQLite database

Every ingest: hash → dedup → move to date folder → extract metadata → index.
"""

import sqlite3
import os
import hashlib
import json
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

# Catalog DB always lives on the SD card (indexes ALL devices)
CATALOG_HOME = "/home/clawd/media"
DB_PATH = os.path.join(CATALOG_HOME, "catalog.db")

def _db_path():
    return DB_PATH

MOUNT_BASE = "/mnt"  # Where external drives get mounted

def _get_block_info(dev_path):
    """Get UUID, model, fstype for a block device."""
    uuid = None
    for cmd in [["sudo", "blkid", "-s", "UUID", "-o", "value", dev_path],
                ["blkid", "-s", "UUID", "-o", "value", dev_path],
                ["lsblk", "-n", "-o", "UUID", dev_path]]:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if r.stdout.strip():
                uuid = r.stdout.strip()
                break
        except:
            continue

    dev_name = os.path.basename(dev_path).rstrip("0123456789")
    model_path = f"/sys/block/{dev_name}/device/model"
    model = open(model_path).read().strip() if os.path.exists(model_path) else None

    fstype = None
    try:
        r = subprocess.run(["lsblk", "-n", "-o", "FSTYPE", dev_path],
                          capture_output=True, text=True, timeout=5)
        fstype = r.stdout.strip() or None
    except:
        pass

    size_bytes = None
    try:
        r = subprocess.run(["lsblk", "-n", "-o", "SIZE", "-b", dev_path],
                          capture_output=True, text=True, timeout=5)
        size_bytes = int(r.stdout.strip()) if r.stdout.strip() else None
    except:
        pass

    return {"uuid": uuid, "model": model, "fs_type": fstype, "size_bytes": size_bytes}

def register_device(uuid, label=None, mount_point=None, device_path=None, fs_type=None, size_bytes=None):
    """Register or update a device in the catalog."""
    db = get_db()
    dev_id = f"usb:{uuid}"
    existing = db.execute("SELECT * FROM devices WHERE id = ?", (dev_id,)).fetchone()
    
    if existing:
        # Update
        db.execute("""UPDATE devices SET label=COALESCE(?,label), mount_point=?,
                      device_path=COALESCE(?,device_path), fs_type=COALESCE(?,fs_type),
                      total_bytes=COALESCE(?,total_bytes)
                      WHERE id=?""",
                   (label, mount_point, device_path, fs_type, size_bytes, dev_id))
    else:
        db.execute("""INSERT INTO devices (id, label, mount_point, device_path, fs_type,
                      total_bytes, added_at) VALUES (?,?,?,?,?,?,?)""",
                   (dev_id, label or "Unknown Drive", mount_point, device_path,
                    fs_type, size_bytes, datetime.now().isoformat()))
    db.commit()
    db.close()
    return dev_id

def get_registered_devices():
    """Get all registered devices from catalog."""
    db = get_db()
    rows = db.execute("SELECT * FROM devices").fetchall()
    db.close()
    return [dict(r) for r in rows]

def discover_devices():
    """Discover all storage devices — registered and live."""
    devices = []
    
    # SD card (always present, always online)
    devices.append({
        "id": "sd:mmcblk0p2",
        "label": "SD Card",
        "mount_point": "/",
        "media_path": "/home/clawd/media",
        "device_path": "/dev/mmcblk0p2",
        "online": True,
        "registered": True,
    })

    # Get all registered external devices from DB
    registered = {d["id"]: d for d in get_registered_devices()}
    
    # Scan mounted external drives using JSON output for reliable parsing
    online_ids = set()
    try:
        r = subprocess.run(["lsblk", "-J", "-o", "NAME,MOUNTPOINT,UUID,MODEL,TYPE,PATH"],
                          capture_output=True, text=True, timeout=5)
        data = json.loads(r.stdout)
        
        def scan_devices(entries, parent_model=None):
            for entry in entries:
                dev_path = entry.get("path", "")
                mount = entry.get("mountpoint") or None
                uuid = entry.get("uuid") or None
                model = entry.get("model") or parent_model
                dtype = entry.get("type", "")
                
                if dtype == "part" and uuid:
                    if "mmcblk" not in dev_path and "loop" not in dev_path and "zram" not in dev_path:
                        dev_id = f"usb:{uuid}"
                        online_ids.add(dev_id)
                        
                        if not model:
                            parent = dev_path.rstrip("0123456789")
                            mp = f"/sys/block/{os.path.basename(parent)}/device/model"
                            model = open(mp).read().strip() if os.path.exists(mp) else "External Drive"
                        
                        is_registered = dev_id in registered
                        devices.append({
                            "id": dev_id,
                            "label": model,
                            "mount_point": mount,
                            "media_path": mount,
                            "device_path": dev_path,
                            "online": True,
                            "registered": is_registered,
                            "uuid": uuid,
                        })
                
                # Recurse into children (partitions under disks)
                if "children" in entry:
                    scan_devices(entry["children"], parent_model=entry.get("model") or parent_model)
        
        scan_devices(data.get("blockdevices", []))
    except:
        pass
    
    # Add offline registered devices (not currently mounted)
    for dev_id, dev in registered.items():
        if dev_id not in online_ids and dev_id != "sd:mmcblk0p2":
            # Count items on this device
            db = get_db()
            count = db.execute("SELECT COUNT(*) FROM media WHERE device_id=?", (dev_id,)).fetchone()[0]
            db.close()
            devices.append({
                "id": dev_id,
                "label": dev.get("label", "Unknown Drive"),
                "mount_point": None,
                "media_path": None,
                "device_path": dev.get("device_path"),
                "online": False,
                "registered": True,
                "items_offline": count,
            })
    
    return devices

def handshake(dev_path=None):
    """
    Handshake with a drive. Detect, identify, register if new, reconcile if known.
    Returns status dict.
    """
    # Find the drive
    if dev_path is None:
        # Auto-detect: look for non-SD block devices
        try:
            r = subprocess.run(["lsblk", "-n", "-o", "NAME,UUID,SIZE,MODEL", "-p", "--list"],
                              capture_output=True, text=True, timeout=5)
            for line in r.stdout.strip().split("\n"):
                parts = line.split(None, 3)
                if len(parts) < 2:
                    continue
                if "mmcblk" not in parts[0] and "loop" not in parts[0] and "zram" not in parts[0]:
                    if parts[1] and parts[1] != "":
                        dev_path = parts[0]
                        break
        except:
            pass
    
    if not dev_path:
        return {"status": "no_drive", "message": "No external drive detected."}
    
    info = _get_block_info(dev_path)
    uuid = info.get("uuid")
    if not uuid:
        return {"status": "error", "message": f"Could not read UUID from {dev_path}"}
    
    dev_id = f"usb:{uuid}"
    model = info.get("model") or "External Drive"
    
    # Check if mounted
    mount_point = None
    try:
        r = subprocess.run(["findmnt", "-n", "-o", "TARGET", dev_path],
                          capture_output=True, text=True, timeout=5)
        mount_point = r.stdout.strip() or None
    except:
        pass
    
    # Mount if not mounted
    if not mount_point:
        mount_point = f"{MOUNT_BASE}/media"
        os.makedirs(mount_point, exist_ok=True)
        try:
            uid = os.getuid()
            gid = os.getgid()
            subprocess.run(
                ["sudo", "mount", "-o", f"uid={uid},gid={gid}", dev_path, mount_point],
                capture_output=True, timeout=10
            )
        except:
            # Try without uid/gid (ext4 etc)
            try:
                subprocess.run(["sudo", "mount", dev_path, mount_point],
                              capture_output=True, timeout=10)
            except:
                return {"status": "error", "message": f"Failed to mount {dev_path}"}
    
    # Check if known
    db = get_db()
    existing = db.execute("SELECT * FROM devices WHERE id = ?", (dev_id,)).fetchone()
    item_count = db.execute("SELECT COUNT(*) FROM media WHERE device_id=?", (dev_id,)).fetchone()[0]
    db.close()
    
    # Register/update
    register_device(uuid, label=model, mount_point=mount_point,
                   device_path=dev_path, fs_type=info.get("fs_type"),
                   size_bytes=info.get("size_bytes"))
    
    if existing:
        # Known drive — verify files
        db = get_db()
        items = db.execute("SELECT id, path FROM media WHERE device_id=?", (dev_id,)).fetchall()
        db.close()
        
        missing = 0
        for item in items:
            if not os.path.exists(item["path"]):
                missing += 1
        
        return {
            "status": "welcome_back",
            "device_id": dev_id,
            "label": model,
            "uuid": uuid,
            "mount_point": mount_point,
            "items": item_count,
            "missing": missing,
            "message": f"Welcome back, {model}. {item_count} items cataloged{f', {missing} missing' if missing else ', all verified'}."
        }
    else:
        # New drive — check if it has existing media to scan
        existing_files = 0
        for root, dirs, files in os.walk(mount_point):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in ('.jpg', '.jpeg', '.png', '.mp4', '.mkv', '.mov', '.wav', '.mp3', '.ogg', '.flac'):
                    existing_files += 1
        
        return {
            "status": "new_drive",
            "device_id": dev_id,
            "label": model,
            "uuid": uuid,
            "mount_point": mount_point,
            "existing_media_files": existing_files,
            "message": f"New drive: {model} ({uuid}). Registered.{f' Found {existing_files} existing media files — ingest with /catalog scan.' if existing_files else ''}"
        }

def transfer(from_device, to_device, media_type=None, limit=None):
    """Transfer media items from one device to another."""
    db = get_db()
    
    conditions = ["device_id = ?"]
    params = [from_device]
    if media_type:
        conditions.append("type = ?")
        params.append(media_type)
    
    where = " AND ".join(conditions)
    if limit:
        items = db.execute(f"SELECT * FROM media WHERE {where} LIMIT ?", params + [limit]).fetchall()
    else:
        items = db.execute(f"SELECT * FROM media WHERE {where}", params).fetchall()
    
    if not items:
        db.close()
        return {"status": "nothing", "message": f"No items on {from_device} to transfer."}
    
    # Find target mount point
    devices = discover_devices()
    target = None
    for d in devices:
        if d["id"] == to_device and d["online"]:
            target = d
            break
    
    if not target or not target.get("media_path"):
        db.close()
        return {"status": "error", "message": f"Target device {to_device} not online or not mounted."}
    
    transferred = 0
    errors = 0
    bytes_moved = 0
    
    for item in items:
        src = item["path"]
        if not os.path.exists(src):
            errors += 1
            continue
        
        # Preserve date folder structure
        filename = item["filename"]
        # Parse date from created_at
        try:
            dt = datetime.fromisoformat(item["created_at"])
            date_dir = dt.strftime("%Y/%m/%d")
        except:
            date_dir = "unsorted"
        
        dest_dir = os.path.join(target["media_path"], date_dir)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, filename)
        
        try:
            shutil.copy2(src, dest)
            if os.path.exists(dest) and os.path.getsize(dest) == item["size_bytes"]:
                # Update catalog
                db.execute("UPDATE media SET path=?, device_id=? WHERE id=?",
                          (dest, to_device, item["id"]))
                os.remove(src)  # Remove from source
                transferred += 1
                bytes_moved += item["size_bytes"]
            else:
                errors += 1
        except Exception as e:
            errors += 1
    
    db.commit()
    db.close()
    
    return {
        "status": "done",
        "transferred": transferred,
        "errors": errors,
        "bytes_moved": bytes_moved,
        "mb_moved": round(bytes_moved / 1_000_000, 1),
        "message": f"Transferred {transferred} items ({round(bytes_moved/1_000_000,1)}MB) to {to_device}. {f'{errors} errors.' if errors else ''}"
    }

def get_active_media_root():
    """Get the preferred media root (external drive if available, else SD)."""
    # Prefer registered + online external drives
    devices = discover_devices()
    for d in devices:
        if d["id"] != "sd:mmcblk0p2" and d.get("online") and d.get("media_path"):
            return d["media_path"]
    return "/home/clawd/media"

def device_for_path(path):
    """Determine which device a path belongs to."""
    devices = discover_devices()
    # Find the most specific mount point match
    best = None
    for d in devices:
        mp = d.get("media_path") or d.get("mount_point")
        if mp and path.startswith(mp) and (best is None or len(mp) > len(best[1])):
            best = (d["id"], mp)
    return best[0] if best else "sd:mmcblk0p2"

def get_db():
    db = sqlite3.connect(_db_path())
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db

def init_db():
    """Create tables if they don't exist."""
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY,           -- e.g. "usb:697E-ABB0", "sd:mmcblk0p2"
            label TEXT,                    -- friendly name
            mount_point TEXT,
            device_path TEXT,              -- /dev/sda1
            fs_type TEXT,
            total_bytes INTEGER,
            added_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hash TEXT UNIQUE NOT NULL,
            path TEXT NOT NULL,
            filename TEXT NOT NULL,
            device_id TEXT,               -- which device this lives on
            type TEXT NOT NULL,           -- snap, clip, stream, listen, import
            mime TEXT,
            size_bytes INTEGER,
            duration_secs REAL,
            width INTEGER,
            height INTEGER,
            created_at TEXT NOT NULL,      -- ISO 8601
            ingested_at TEXT NOT NULL,
            tags TEXT DEFAULT '',          -- space-separated tags
            notes TEXT DEFAULT '',
            metadata TEXT DEFAULT '{}'     -- JSON blob for extras
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
            tag TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_media_type ON media(type);
        CREATE INDEX IF NOT EXISTS idx_media_created ON media(created_at);
        CREATE INDEX IF NOT EXISTS idx_media_hash ON media(hash);
        CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
        CREATE INDEX IF NOT EXISTS idx_tags_media ON tags(media_id);

        CREATE VIRTUAL TABLE IF NOT EXISTS media_fts USING fts5(
            filename, type, tags, notes,
            content=media, content_rowid=id
        );

        -- Triggers to keep FTS in sync
        CREATE TRIGGER IF NOT EXISTS media_ai AFTER INSERT ON media BEGIN
            INSERT INTO media_fts(rowid, filename, type, tags, notes)
            VALUES (new.id, new.filename, new.type, new.tags, new.notes);
        END;

        CREATE TRIGGER IF NOT EXISTS media_au AFTER UPDATE ON media BEGIN
            INSERT INTO media_fts(media_fts, rowid, filename, type, tags, notes)
            VALUES ('delete', old.id, old.filename, old.type, old.tags, old.notes);
            INSERT INTO media_fts(rowid, filename, type, tags, notes)
            VALUES (new.id, new.filename, new.type, new.tags, new.notes);
        END;

        CREATE TRIGGER IF NOT EXISTS media_ad AFTER DELETE ON media BEGIN
            INSERT INTO media_fts(media_fts, rowid, filename, type, tags, notes)
            VALUES ('delete', old.id, old.filename, old.type, old.tags, old.notes);
        END;
    """)
    db.commit()
    db.close()

def file_hash(path, chunk_size=65536):
    """SHA-256 hash of file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def probe_media(path):
    """Extract metadata via ffprobe."""
    try:
        result = subprocess.run([
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", path
        ], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except:
        pass
    return {}

def make_thumbnail(src_path, thumb_path, size="320x240"):
    """Generate thumbnail for image or video."""
    os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
    ext = os.path.splitext(src_path)[1].lower()
    try:
        if ext in ('.jpg', '.jpeg', '.png', '.webp'):
            subprocess.run([
                "ffmpeg", "-y", "-i", src_path,
                "-vf", f"scale={size}:force_original_aspect_ratio=decrease",
                thumb_path
            ], capture_output=True, timeout=10)
        elif ext in ('.mp4', '.mkv', '.avi', '.mov', '.ts'):
            subprocess.run([
                "ffmpeg", "-y", "-i", src_path,
                "-ss", "00:00:01", "-frames:v", "1",
                "-vf", f"scale={size}:force_original_aspect_ratio=decrease",
                thumb_path
            ], capture_output=True, timeout=10)
        return os.path.exists(thumb_path)
    except:
        return False

def detect_type(filename):
    """Guess media type from filename pattern."""
    name = filename.lower()
    if "snap" in name:
        return "snap"
    if "clip" in name:
        return "clip"
    if "stream" in name:
        return "stream"
    if "listen" in name or "recording" in name:
        return "listen"
    return "import"

def detect_mime(path):
    """Guess MIME type."""
    ext = os.path.splitext(path)[1].lower()
    return {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
        '.webp': 'image/webp', '.gif': 'image/gif',
        '.mp4': 'video/mp4', '.mkv': 'video/x-matroska', '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime', '.ts': 'video/mp2t',
        '.wav': 'audio/wav', '.ogg': 'audio/ogg', '.mp3': 'audio/mpeg',
        '.flac': 'audio/flac',
    }.get(ext, 'application/octet-stream')

def ingest(src_path, media_type=None, tags=None, notes="", move=True, target_root=None):
    """
    Ingest a file into the catalog.
    
    - Hashes file for dedup
    - Moves/copies to date-organized folder on target device
    - Extracts metadata
    - Generates thumbnail
    - Indexes in SQLite
    
    Returns: dict with media record, or None if duplicate.
    """
    if not os.path.exists(src_path):
        return {"error": f"File not found: {src_path}"}

    fhash = file_hash(src_path)
    
    # Check for duplicate
    db = get_db()
    existing = db.execute("SELECT * FROM media WHERE hash = ?", (fhash,)).fetchone()
    if existing:
        db.close()
        return {"duplicate": True, "existing": dict(existing)}

    filename = os.path.basename(src_path)
    if media_type is None:
        media_type = detect_type(filename)
    
    mime = detect_mime(src_path)
    size = os.path.getsize(src_path)
    
    # Use target root or auto-detect best device
    media_root = target_root or get_active_media_root()
    dev_id = device_for_path(media_root)
    
    # Extract creation time from filename or file mtime
    now = datetime.now()
    created_at = now.isoformat()
    
    # Probe for duration/dimensions
    probe = probe_media(src_path)
    duration = None
    width = None
    height = None
    if probe.get("format"):
        duration = float(probe["format"].get("duration", 0)) or None
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            width = stream.get("width")
            height = stream.get("height")
            break

    # Date folder: YYYY/MM/DD
    date_dir = now.strftime("%Y/%m/%d")
    dest_dir = os.path.join(media_root, date_dir)
    os.makedirs(dest_dir, exist_ok=True)
    
    # Rename with timestamp + type
    ext = os.path.splitext(filename)[1]
    new_name = f"{now.strftime('%Y%m%d_%H%M%S')}_{media_type}{ext}"
    dest_path = os.path.join(dest_dir, new_name)
    
    # Avoid collision
    counter = 1
    while os.path.exists(dest_path):
        new_name = f"{now.strftime('%Y%m%d_%H%M%S')}_{media_type}_{counter}{ext}"
        dest_path = os.path.join(dest_dir, new_name)
        counter += 1

    # Move or copy
    if move:
        shutil.move(src_path, dest_path)
    else:
        shutil.copy2(src_path, dest_path)

    # Store absolute path (works across devices)
    rel_path = dest_path

    # Generate thumbnail
    thumb_name = f"{os.path.splitext(new_name)[0]}.jpg"
    thumb_path = os.path.join(media_root, "thumbs", date_dir, thumb_name)
    make_thumbnail(dest_path, thumb_path)

    # Tags
    tag_list = tags or []
    tag_str = " ".join(tag_list)

    # Insert
    cursor = db.execute("""
        INSERT INTO media (hash, path, filename, device_id, type, mime, size_bytes,
                          duration_secs, width, height, created_at, ingested_at,
                          tags, notes, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (fhash, rel_path, new_name, dev_id, media_type, mime, size,
          duration, width, height, created_at, now.isoformat(),
          tag_str, notes, json.dumps({"probe": probe.get("format", {})})))
    
    media_id = cursor.lastrowid
    
    # Insert individual tags
    for tag in tag_list:
        db.execute("INSERT INTO tags (media_id, tag) VALUES (?, ?)", (media_id, tag))
    
    db.commit()
    
    record = dict(db.execute("SELECT * FROM media WHERE id = ?", (media_id,)).fetchone())
    db.close()
    
    return {"ingested": True, "record": record}

def search(query=None, media_type=None, date_from=None, date_to=None, 
           tags=None, limit=20, offset=0):
    """Search the catalog."""
    db = get_db()
    
    if query:
        # Full-text search
        rows = db.execute("""
            SELECT m.* FROM media m
            JOIN media_fts fts ON m.id = fts.rowid
            WHERE media_fts MATCH ?
            ORDER BY m.created_at DESC
            LIMIT ? OFFSET ?
        """, (query, limit, offset)).fetchall()
    else:
        conditions = []
        params = []
        
        if media_type:
            conditions.append("type = ?")
            params.append(media_type)
        if date_from:
            conditions.append("created_at >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("created_at <= ?")
            params.append(date_to)
        if tags:
            for tag in tags:
                conditions.append("id IN (SELECT media_id FROM tags WHERE tag = ?)")
                params.append(tag)
        
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])
        
        rows = db.execute(f"""
            SELECT * FROM media {where}
            ORDER BY created_at DESC LIMIT ? OFFSET ?
        """, params).fetchall()
    
    results = [dict(r) for r in rows]
    db.close()
    return results

def stats():
    """Get catalog statistics."""
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    by_type = {r[0]: r[1] for r in db.execute(
        "SELECT type, COUNT(*) FROM media GROUP BY type").fetchall()}
    total_size = db.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM media").fetchone()[0]
    total_duration = db.execute(
        "SELECT COALESCE(SUM(duration_secs), 0) FROM media WHERE duration_secs IS NOT NULL"
    ).fetchone()[0]
    top_tags = db.execute(
        "SELECT tag, COUNT(*) as cnt FROM tags GROUP BY tag ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    
    # Per-device stats
    by_device = {}
    for r in db.execute(
        "SELECT device_id, COUNT(*), COALESCE(SUM(size_bytes),0) FROM media GROUP BY device_id"
    ).fetchall():
        by_device[r[0] or "unknown"] = {"count": r[1], "size_mb": round(r[2] / 1_000_000, 1)}
    
    db.close()
    
    # Enrich with live device info
    devices = discover_devices()
    device_info = []
    for dev in devices:
        info = {"id": dev["id"], "label": dev["label"], "online": dev["online"],
                "device_path": dev["device_path"]}
        # Get disk usage
        try:
            mp = dev.get("media_path") or dev["mount_point"]
            stat = os.statvfs(mp)
            info["total_gb"] = round(stat.f_blocks * stat.f_frsize / 1e9, 1)
            info["free_gb"] = round(stat.f_bavail * stat.f_frsize / 1e9, 1)
        except:
            pass
        # Merge catalog counts
        if dev["id"] in by_device:
            info["items"] = by_device[dev["id"]]["count"]
            info["catalog_mb"] = by_device[dev["id"]]["size_mb"]
        else:
            info["items"] = 0
            info["catalog_mb"] = 0
        device_info.append(info)
    
    return {
        "total_items": total,
        "by_type": by_type,
        "total_size_mb": round(total_size / 1_000_000, 1),
        "total_duration_mins": round(total_duration / 60, 1),
        "top_tags": [{"tag": r[0], "count": r[1]} for r in top_tags],
        "devices": device_info,
    }

def recent(n=10):
    """Get n most recent items."""
    return search(limit=n)

def get(media_id):
    """Get a single media item by ID."""
    db = get_db()
    row = db.execute("SELECT * FROM media WHERE id = ?", (media_id,)).fetchone()
    db.close()
    return dict(row) if row else None

def tag(media_id, new_tags):
    """Add tags to a media item."""
    db = get_db()
    item = db.execute("SELECT * FROM media WHERE id = ?", (media_id,)).fetchone()
    if not item:
        db.close()
        return {"error": "Not found"}
    
    existing = set(item["tags"].split()) if item["tags"] else set()
    for t in new_tags:
        if t not in existing:
            db.execute("INSERT INTO tags (media_id, tag) VALUES (?, ?)", (media_id, t))
            existing.add(t)
    
    db.execute("UPDATE media SET tags = ? WHERE id = ?", (" ".join(existing), media_id))
    db.commit()
    db.close()
    return {"ok": True, "tags": list(existing)}

def abs_path(record):
    """Get absolute path for a media record."""
    return os.path.join(MEDIA_ROOT, record["path"])


# CLI
if __name__ == "__main__":
    import sys
    init_db()
    
    if len(sys.argv) < 2:
        print("Usage: catalog.py <command> [args]")
        print("  init              Initialize database")
        print("  ingest <file>     Ingest a file")
        print("  search [query]    Search catalog")
        print("  recent [n]        Show recent items")
        print("  stats             Show statistics")
        print("  get <id>          Get item by ID")
        print("  tag <id> <tags>   Add tags")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "init":
        print(f"Database initialized at {_db_path()}")
    
    elif cmd == "ingest":
        if len(sys.argv) < 3:
            print("Usage: catalog.py ingest <file> [type] [tags...]")
            sys.exit(1)
        path = sys.argv[2]
        mtype = sys.argv[3] if len(sys.argv) > 3 else None
        tags = sys.argv[4:] if len(sys.argv) > 4 else []
        result = ingest(path, media_type=mtype, tags=tags)
        print(json.dumps(result, indent=2, default=str))
    
    elif cmd == "search":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
        results = search(query=query)
        for r in results:
            dur = f" ({r['duration_secs']:.0f}s)" if r.get('duration_secs') else ""
            size = f" {r['size_bytes']/1_000_000:.1f}MB" if r.get('size_bytes') else ""
            tags = f" [{r['tags']}]" if r.get('tags') else ""
            print(f"#{r['id']} {r['type']:8s} {r['filename']}{dur}{size}{tags}")
    
    elif cmd == "recent":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        results = recent(n)
        for r in results:
            dur = f" ({r['duration_secs']:.0f}s)" if r.get('duration_secs') else ""
            size = f" {r['size_bytes']/1_000_000:.1f}MB" if r.get('size_bytes') else ""
            print(f"#{r['id']} {r['type']:8s} {r['created_at'][:16]} {r['filename']}{dur}{size}")
    
    elif cmd == "stats":
        print(json.dumps(stats(), indent=2))
    
    elif cmd == "get":
        if len(sys.argv) < 3:
            print("Usage: catalog.py get <id>")
            sys.exit(1)
        item = get(int(sys.argv[2]))
        print(json.dumps(item, indent=2, default=str) if item else "Not found")
    
    elif cmd == "tag":
        if len(sys.argv) < 4:
            print("Usage: catalog.py tag <id> <tag1> [tag2 ...]")
            sys.exit(1)
        result = tag(int(sys.argv[2]), sys.argv[3:])
        print(json.dumps(result))
    
    elif cmd == "handshake":
        dev = sys.argv[2] if len(sys.argv) > 2 else None
        result = handshake(dev)
        print(json.dumps(result, indent=2, default=str))
    
    elif cmd == "transfer":
        if len(sys.argv) < 4:
            print("Usage: catalog.py transfer <from_device_id> <to_device_id> [type] [limit]")
            sys.exit(1)
        from_dev = sys.argv[2]
        to_dev = sys.argv[3]
        mtype = sys.argv[4] if len(sys.argv) > 4 else None
        limit = int(sys.argv[5]) if len(sys.argv) > 5 else None
        result = transfer(from_dev, to_dev, media_type=mtype, limit=limit)
        print(json.dumps(result, indent=2, default=str))
    
    elif cmd == "devices":
        devices = discover_devices()
        for d in devices:
            status = "🟢" if d["online"] else "🔴"
            reg = "✓" if d.get("registered") else "?"
            print(f"{status} [{reg}] {d['label']:20s} {d['id']:20s} {d.get('device_path',''):12s} {d.get('mount_point') or 'unmounted'}")
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
