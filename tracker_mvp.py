from __future__ import annotations
import copy, ctypes, json, math, os, re, sys, threading, time, urllib.request, urllib.parse, webbrowser, socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
WEB = BUNDLE_ROOT / "web"
CONFIG = ROOT / "config.json"
MAPS = ROOT / "maps.json" if (ROOT / "maps.json").exists() else BUNDLE_ROOT / "maps.json"
RICH_CACHE = ROOT / "rich_map_cache.json"
QUEST_CACHE = ROOT / "quests_cache.json"
PIN_REPORTS = ROOT / "pin_reports.json"
PIDFILE = ROOT / "tracker.pid"
RECORDINGS = ROOT / "recordings"
RECORDINGS.mkdir(exist_ok=True)
if not CONFIG.exists() and (BUNDLE_ROOT / "config.json").exists():
    CONFIG.write_text((BUNDLE_ROOT / "config.json").read_text(encoding="utf-8"), encoding="utf-8")
if not RICH_CACHE.exists():
    RICH_CACHE.write_text(json.dumps({"updated":None,"maps":{}}, ensure_ascii=False), encoding="utf-8")
if not QUEST_CACHE.exists():
    QUEST_CACHE.write_text(json.dumps({"updated":None,"source":None,"quests":[]}, ensure_ascii=False), encoding="utf-8")
if not PIN_REPORTS.exists():
    PIN_REPORTS.write_text("[]", encoding="utf-8")

cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
maps_meta = json.loads(MAPS.read_text(encoding="utf-8"))

NUM = r"-?\d+(?:\.\d+)?"
POSE_RE = re.compile(rf"_\s*({NUM})\s*,\s*({NUM})\s*,\s*({NUM})\s*_\s*({NUM})\s*,\s*({NUM})\s*,\s*({NUM})\s*,\s*({NUM})")
XYZ_RE = re.compile(rf"_\s*({NUM})\s*,\s*({NUM})\s*,\s*({NUM})\s*_")

state_lock = threading.Lock()
state: dict[str, Any] = {
    "position": None, "bearing": None, "quaternion": None,
    "last_update": None, "last_file": None, "last_trigger": None, "last_success": None,
    "game_foreground": False, "status": "Wachten op Tarkov...",
    "map": cfg.get("default_map", "customs"),
    "interval": float(cfg.get("interval_seconds", 0.5)),
    "screenshot_key": str(cfg.get("screenshot_key", "F9")).upper(),
    "screenshot_folder": None, "folder_reason": "Nog niet gedetecteerd", "files_seen": 0,
    "data_status": "lokale cache laden", "data_updated": None,
    "auto_map_detect": bool(cfg.get("auto_map_detect", True)),
    "map_detection": {"status":"wachten","candidates":[]},
    "smoothed_position": None, "velocity": {"x":0.0,"y":0.0,"z":0.0},
    "speed_mps": 0.0, "accepted_count": 0, "rejected_count": 0,
    "recording_id": None,
    "capture_enabled": bool(cfg.get("capture_enabled", True)),
    "app_name": str(cfg.get("app_name", "Tarkov Compass")), "app_version": str(cfg.get("app_version", "24.6-progression-planner")), "started_at": time.time(), "server_port": None,
    "quest_status": "questcache laden", "quest_count": 0, "quest_updated": None, "quest_source": None,
    "quest_spot_count": 0, "quest_mapped_objectives": 0, "quest_mapped_quests": 0,
    "quest_story_count": 0, "quest_position_corrections": {"moved":0,"floors":0,"hidden":0},
}
rich_maps: dict[str, dict[str, Any]] = {}
quest_catalog: list[dict[str, Any]] = []
quest_index: dict[str, dict[str, Any]] = {}
quest_lock = threading.Lock()
quest_ready = threading.Event()
trigger_times: list[float] = []
last_valid_pose: dict[str, Any] | None = None
last_valid_time: float | None = None
smooth_pos: dict[str, float] | None = None
smooth_vel = {"x":0.0,"y":0.0,"z":0.0}
recording_lock = threading.Lock()
recording_id = time.strftime("raid_%Y%m%d_%H%M%S") + ".jsonl"
recording_path = RECORDINGS / recording_id
with state_lock:
    state["recording_id"] = recording_id

KEYS = {**{chr(ord('A')+i):0x41+i for i in range(26)}, **{str(i):0x30+i for i in range(10)},
        **{f"F{i}":0x70+i-1 for i in range(1,13)}, "INSERT":0x2D,"HOME":0x24,"END":0x23,
        "PAGEUP":0x21,"PAGEDOWN":0x22,"PAUSE":0x13,
        **{f"NUMPAD{i}":0x60+i for i in range(10)}}
ALIASES = {
    "factory":"factory","night-factory":"factory","customs":"customs","woods":"woods",
    "shoreline":"shoreline","interchange":"interchange","the-lab":"lab","lab":"lab",
    "reserve":"reserve","lighthouse":"lighthouse","streets-of-tarkov":"streetsoftarkov",
    "streetsoftarkov":"streetsoftarkov","ground-zero":"groundzero","groundzero":"groundzero",
    "ground-zero-21":"groundzero","ground-zero-tutorial":"groundzero",
    "terminal":"terminal","icebreaker":"icebreaker","the-labyrinth":"labyrinth","labyrinth":"labyrinth","transit":"transit","transits":"transit",
}

def norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")

def map_key(obj: Any) -> str | None:
    if isinstance(obj, str): return ALIASES.get(norm_name(obj))
    if isinstance(obj, dict):
        return ALIASES.get(norm_name(obj.get("normalizedName") or obj.get("name") or ""))
    return None

def save_pid(): PIDFILE.write_text(str(os.getpid()), encoding="ascii")

_single_mutex = None
def acquire_single_instance():
    """Prevent old/new tracker builds from running at the same time on Windows."""
    global _single_mutex
    if os.name != "nt":
        return True
    try:
        k32=ctypes.windll.kernel32
        _single_mutex=k32.CreateMutexW(None, False, "Local\\TarkovCompassSingleInstance")
        return int(k32.GetLastError()) != 183
    except Exception:
        return True

def save_runtime_config():
    try: cur = json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception: cur = {}
    with state_lock:
        cur["interval_seconds"] = float(state["interval"])
        cur["screenshot_key"] = state["screenshot_key"]
        cur["auto_map_detect"] = bool(state.get("auto_map_detect", True))
        cur["capture_enabled"] = bool(state.get("capture_enabled", True))
    CONFIG.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")

def parse_pose(name: str):
    m = POSE_RE.search(name)
    if m:
        x,y,z,qx,qy,qz,qw = map(float, m.groups())
        # Quaternion yaw around Unity's vertical Y axis. Browser can add a calibration offset.
        siny = 2.0 * (qw*qy + qx*qz)
        cosy = 1.0 - 2.0 * (qy*qy + qz*qz)
        bearing = math.degrees(math.atan2(siny, cosy)) % 360.0
        return {"x":x,"y":y,"z":z,"bearing":bearing,"quaternion":[qx,qy,qz,qw]}
    m = XYZ_RE.search(name)
    if not m: return None
    x,y,z = map(float, m.groups())
    return {"x":x,"y":y,"z":z,"bearing":None,"quaternion":None}


def map_norm_for(meta: dict[str, Any], x: float, z: float):
    try:
        rot=float(meta.get("coordinateRotation") or 0.0)
        a=math.radians(rot); c=math.cos(a); sn=math.sin(a)
        def rp(px,pz): return (px*c-pz*sn, px*sn+pz*c)
        p=rp(x,z); c0=meta.get("corners",[[0,0],[1,1]])[0]; c1=meta.get("corners",[[0,0],[1,1]])[1]
        a0=rp(float(c0[0]),float(c0[1])); a1=rp(float(c1[0]),float(c1[1]))
        minx,maxx=sorted((a0[0],a1[0])); minz,maxz=sorted((a0[1],a1[1]))
        nx=(p[0]-minx)/max(1e-6,maxx-minx); ny=1.0-(p[1]-minz)/max(1e-6,maxz-minz)
        return nx,ny
    except Exception:
        return None

def maybe_auto_detect_map(pose: dict[str, Any]):
    with state_lock:
        enabled=bool(state.get("auto_map_detect", True)); current=state.get("map")
    if not enabled: return current
    x,z=float(pose["x"]),float(pose["z"])
    scored=[]
    for key,meta in maps_meta.items():
        if meta.get("liveTracking") is False: continue
        n=map_norm_for(meta,x,z)
        if not n: continue
        nx,ny=n
        # Conservative: only consider positions plausibly inside the map.
        if -0.06 <= nx <= 1.06 and -0.06 <= ny <= 1.06:
            outside=max(0,-nx,nx-1,-ny,ny-1)
            center=math.hypot(nx-.5,ny-.5)
            score=outside*4.0+center
            scored.append((score,key,nx,ny))
    scored.sort()
    candidates=[{"map":k,"score":round(sc,3),"nx":round(nx,3),"ny":round(ny,3)} for sc,k,nx,ny in scored[:5]]
    chosen=current; status="huidige map behouden"
    cur=next((r for r in scored if r[1]==current),None)
    if cur and -0.04 <= cur[2] <= 1.04 and -0.04 <= cur[3] <= 1.04:
        pass
    elif scored:
        best=scored[0]
        gap=(scored[1][0]-best[0]) if len(scored)>1 else 9.0
        if gap>=0.10 or len(scored)==1:
            chosen=best[1]; status=f"automatisch herkend: {maps_meta.get(chosen,{}).get('name',chosen)}"
            with state_lock: state["map"]=chosen
        else:
            status="meerdere maps passen; handmatige map behouden"
    else:
        status="positie past niet binnen bekende mapbounds"
    with state_lock: state["map_detection"]={"status":status,"candidates":candidates}
    return chosen

def accept_and_filter_pose(pose: dict[str, Any], now: float):
    global last_valid_pose,last_valid_time,smooth_pos,smooth_vel
    p={"x":float(pose["x"]),"y":float(pose["y"]),"z":float(pose["z"])}
    reject_reason=None
    if last_valid_pose is not None and last_valid_time is not None:
        dt=max(1e-3,now-last_valid_time)
        d=math.sqrt(sum((p[k]-float(last_valid_pose[k]))**2 for k in ("x","y","z")))
        speed=d/dt
        # Avoid one-off parser/corrupt screenshot jumps. Long gaps are allowed.
        if dt < 8.0 and d > 65.0 and speed > 25.0:
            reject_reason=f"onrealistische sprong {d:.0f}m/{dt:.1f}s genegeerd"
    if reject_reason:
        with state_lock:
            state["rejected_count"]+=1; state["status"]=reject_reason
        return None

    prev_smooth=dict(smooth_pos) if smooth_pos else None
    prev_time=last_valid_time
    alpha=.58
    if smooth_pos is None: smooth_pos=dict(p)
    else:
        for k in ("x","y","z"): smooth_pos[k]=alpha*p[k]+(1-alpha)*smooth_pos[k]
    if prev_smooth is not None and prev_time is not None:
        dt=max(.05,now-prev_time)
        inst={k:(smooth_pos[k]-prev_smooth[k])/dt for k in ("x","y","z")}
        va=.45
        for k in ("x","y","z"): smooth_vel[k]=va*inst[k]+(1-va)*smooth_vel[k]
    speed=math.sqrt(smooth_vel["x"]**2+smooth_vel["z"]**2)
    last_valid_pose=dict(p); last_valid_time=now
    maybe_auto_detect_map(p)
    with state_lock:
        state["smoothed_position"]=dict(smooth_pos); state["velocity"]=dict(smooth_vel); state["speed_mps"]=speed; state["accepted_count"]+=1
    return p

def append_recording(pose: dict[str, Any], now: float):
    with state_lock:
        row={"t":now,"map":state.get("map"),"x":pose["x"],"y":pose["y"],"z":pose["z"],"bearing":state.get("bearing")}
    try:
        with recording_lock, recording_path.open("a",encoding="utf-8") as f:
            f.write(json.dumps(row,ensure_ascii=False)+"\n")
    except Exception:
        pass

def recording_files():
    out=[]
    for p in sorted(RECORDINGS.glob("raid_*.jsonl"),reverse=True):
        first=last=None; count=0; maps=set()
        try:
            with p.open("r",encoding="utf-8") as f:
                for line in f:
                    try: r=json.loads(line)
                    except Exception: continue
                    if first is None:first=r
                    last=r; count+=1
                    if r.get("map"): maps.add(r["map"])
            if count:
                
                distance=0.0; prev=None
                try:
                    for rr in read_recording(p.name,limit=12000):
                        if prev and rr.get("map")==prev.get("map"):
                            distance += math.hypot(float(rr.get("x",0))-float(prev.get("x",0)), float(rr.get("z",0))-float(prev.get("z",0)))
                        prev=rr
                except Exception: pass
                out.append({"id":p.name,"start":first.get("t"),"end":last.get("t"),"duration":max(0,float(last.get("t") or 0)-float(first.get("t") or 0)),"distance":round(distance,1),"points":count,"maps":sorted(maps)})
        except Exception: pass
    return out[:40]

def safe_recording(name: str):
    if not re.fullmatch(r"raid_\d{8}_\d{6}\.jsonl",name or ""): return None
    p=(RECORDINGS/name).resolve()
    if p.parent!=RECORDINGS.resolve() or not p.exists(): return None
    return p

def read_recording(name: str, limit=8000):
    p=safe_recording(name)
    if not p:return []
    rows=[]
    try:
        with p.open("r",encoding="utf-8") as f:
            for line in f:
                try: rows.append(json.loads(line))
                except Exception: pass
                if len(rows)>=limit: break
    except Exception: pass
    return rows

def heatmap_for(map_name: str):
    bins={}
    for rec in recording_files():
        for r in read_recording(rec["id"],limit=12000):
            if r.get("map")!=map_name: continue
            try:
                x=float(r["x"]); z=float(r["z"])
            except Exception: continue
            # 18m cells keep payload small while still useful.
            k=(round(x/18)*18,round(z/18)*18)
            bins[k]=bins.get(k,0)+1
    return [{"x":x,"z":z,"count":c} for (x,z),c in sorted(bins.items(),key=lambda kv:kv[1],reverse=True)[:700]]

def newest_image_mtime(folder: Path) -> float:
    latest=0.0
    try:
        for pat in ("*.png","*.jpg","*.jpeg","*.bmp"):
            for f in folder.glob(pat):
                try: latest=max(latest,f.stat().st_mtime)
                except OSError: pass
    except OSError: pass
    return latest

def candidate_screenshot_dirs():
    out=[]; explicit=str(cfg.get("screenshot_folder","")).strip()
    if explicit and explicit.lower()!="auto": out.append(("config.json",Path(os.path.expandvars(os.path.expanduser(explicit)))))
    home=Path.home(); user=Path(os.environ.get("USERPROFILE",str(home)))
    for p in [user/"Documents"/"Escape from Tarkov"/"Screenshots",
              user/"OneDrive"/"Documents"/"Escape from Tarkov"/"Screenshots",
              user/"OneDrive"/"Documenten"/"Escape from Tarkov"/"Screenshots",
              user/"OneDrive"/"Dokumente"/"Escape from Tarkov"/"Screenshots"]:
        out.append(("standaard/OneDrive",p))
    for base in (user/"OneDrive", user):
        if not base.exists(): continue
        try:
            for child in base.iterdir():
                if child.is_dir(): out.append(("automatische scan",child/"Escape from Tarkov"/"Screenshots"))
        except OSError: pass
    result=[]; seen=set()
    for reason,p in out:
        try: p=p.resolve()
        except Exception: pass
        k=str(p).lower()
        if k not in seen: result.append((reason,p)); seen.add(k)
    return result

def detect_screenshot_dir():
    candidates=[]
    for reason,p in candidate_screenshot_dirs():
        if p.exists() and p.is_dir(): candidates.append((newest_image_mtime(p),reason,p))
    if candidates:
        candidates.sort(key=lambda x:(x[0],x[1]=="config.json"),reverse=True); mt,reason,p=candidates[0]
        with state_lock:
            state["screenshot_folder"]=str(p); state["folder_reason"]=reason+(" (nieuwste screenshots)" if mt else "")
        return p
    p=Path.home()/"Documents"/"Escape from Tarkov"/"Screenshots"
    with state_lock: state["screenshot_folder"]=str(p); state["folder_reason"]="fallback; map bestond nog niet"
    return p

shot_dir = detect_screenshot_dir()

def foreground_title():
    if os.name!="nt": return ""
    u=ctypes.windll.user32; hwnd=u.GetForegroundWindow(); n=u.GetWindowTextLengthW(hwnd); buf=ctypes.create_unicode_buffer(n+1); u.GetWindowTextW(hwnd,buf,n+1); return buf.value or ""

def tarkov_foreground():
    t=foreground_title().lower(); return "escape from tarkov" in t or "escapefromtarkov" in t

def tap_key():
    if os.name!="nt": raise RuntimeError("Windows-only")
    with state_lock: name=state["screenshot_key"]
    vk=KEYS.get(name)
    if vk is None: raise RuntimeError(f"Onbekende screenshot_key {name}")
    u=ctypes.windll.user32; UP=0x0002; u.keybd_event(vk,0,0,0); time.sleep(.012); u.keybd_event(vk,0,UP,0)

def pos(o):
    if not isinstance(o,dict): return None
    if all(isinstance(o.get(k),(int,float)) for k in ("x","y","z")): return {"x":float(o["x"]),"y":float(o["y"]),"z":float(o["z"])}
    p=o.get("position")
    if isinstance(p,dict) and all(isinstance(p.get(k),(int,float)) for k in ("x","y","z")): return {"x":float(p["x"]),"y":float(p["y"]),"z":float(p["z"])}
    return None

def poi(cat,name,p,floor=None,extra=None):
    if not p: return None
    d={"category":cat,"name":str(name or cat).strip(),**p}
    if floor: d["floor"]=floor
    if extra: d.update(extra)
    return d

def dedupe(items):
    out=[]; seen=set()
    for p in items:
        key=(p.get("category"),p.get("name"),round(p.get("x",0),1),round(p.get("z",0),1))
        if key not in seen: seen.add(key); out.append(p)
    return out

def categorize_loot_name(name:str):
    n=(name or "").lower()
    if "key" in n or "keycard" in n: return "key"
    if any(x in n for x in ("salewa","ifak","afak","med","bandage","morphine","stim","cms","surv12")): return "medical"
    if any(x in n for x in ("ammo","round","cartridge","bullet","shell")): return "ammo"
    return "loot"

def parse_maps_document(raw):
    node=raw.get("data",raw) if isinstance(raw,dict) else raw
    if isinstance(node,dict): mlist=node.get("maps") or node.get("data") or []
    else: mlist=node if isinstance(node,list) else []
    result={}
    for m in mlist:
        if not isinstance(m,dict): continue
        key=map_key(m)
        if key not in maps_meta: continue
        ps=[]; ex=[]; zone_positions={}
        for e in m.get("extracts") or []:
            q=poi("extract",e.get("name"),pos(e),extra={"faction":e.get("faction")})
            if q: ps.append(q); ex.append(q)
        for s in m.get("spawns") or []:
            p=pos(s)
            if not p: continue
            sides="/".join(s.get("sides") or s.get("categories") or [])
            name=s.get("zoneName") or sides or "Spawn"
            q=poi("spawn",name,p,extra={"sides":sides})
            if q: ps.append(q); zone_positions.setdefault(str(s.get("zoneName") or ""),[]).append(p)
        for e in m.get("transits") or []:
            q=poi("transit",e.get("description") or (e.get("map") or {}).get("name") or "Transit",pos(e));
            if q: ps.append(q)
        for e in m.get("hazards") or []:
            q=poi("hazard",e.get("name") or e.get("hazardType") or "Hazard",pos(e));
            if q: ps.append(q)
        for e in m.get("switches") or []:
            q=poi("switch",e.get("name") or "Switch",pos(e));
            if q: ps.append(q)
        for e in m.get("stationaryWeapons") or []:
            q=poi("landmark",(e.get("stationaryWeapon") or {}).get("name") or e.get("name") or "Stationary weapon",pos(e));
            if q: ps.append(q)
        for e in m.get("btrStops") or []:
            q=poi("service",e.get("name") or "BTR stop",pos(e));
            if q: ps.append(q)
        for e in m.get("locks") or []:
            keyitem=e.get("key") or e.get("item") or {}
            name=(keyitem.get("name") if isinstance(keyitem,dict) else None) or e.get("name") or "Locked door / key"
            q=poi("key",name,pos(e));
            if q: ps.append(q)
        for e in m.get("lootContainers") or []:
            q=poi("container",e.get("name") or e.get("type") or "Loot container",pos(e))
            if q: ps.append(q)
        loot_count=0
        for e in m.get("lootLoose") or []:
            p=pos(e)
            if not p: continue
            for item in e.get("items") or []:
                name=item.get("name") if isinstance(item,dict) else str(item)
                cat=categorize_loot_name(name)
                if cat:
                    q=poi(cat,name,p)
                    if q: ps.append(q); loot_count+=1
                    if loot_count>250: break
            if loot_count>250: break
        # Boss locations map through spawn zone names where possible.
        for b in m.get("bosses") or []:
            boss=b.get("boss") or {}; bname=boss.get("name") if isinstance(boss,dict) else b.get("name")
            for loc in b.get("spawnLocations") or []:
                lk=str(loc.get("spawnKey") or loc.get("name") or "")
                matches=zone_positions.get(lk,[])
                if not matches:
                    nl=norm_name(lk)
                    for zk,zps in zone_positions.items():
                        if nl and (nl in norm_name(zk) or norm_name(zk) in nl): matches.extend(zps)
                for bp in matches:
                    q=poi("boss",bname or "Boss",bp,extra={"chance":loc.get("chance") or b.get("spawnChance")})
                    if q: ps.append(q)
        result[key]={"pois":dedupe(ps),"extracts":dedupe(ex),"source_name":m.get("name")}
    return result

def recursive_positions(o):
    found=[]
    if isinstance(o,dict):
        p=pos(o)
        if p: found.append(p)
        for k,v in o.items():
            if k in ("item","items","properties","rewards"): continue
            found.extend(recursive_positions(v))
    elif isinstance(o,list):
        for v in o: found.extend(recursive_positions(v))
    return found

def merge_task_document(raw, base):
    node=raw.get("data",raw) if isinstance(raw,dict) else raw
    tasks=node.get("tasks") if isinstance(node,dict) else node if isinstance(node,list) else []
    if not isinstance(tasks,list): return
    for t in tasks:
        if not isinstance(t,dict): continue
        tname=t.get("name") or t.get("title") or "Quest"
        task_map=map_key(t.get("map"))
        for obj in t.get("objectives") or []:
            mk=map_key(obj.get("map")) if isinstance(obj,dict) else None
            mk=mk or task_map
            if mk not in maps_meta: continue
            for p in recursive_positions(obj):
                base.setdefault(mk,{"pois":[],"extracts":[]})["pois"].append(poi("quest",tname,p,extra={"objective":obj.get("description") or obj.get("type") if isinstance(obj,dict) else None}))
    for v in base.values(): v["pois"]=dedupe([p for p in v.get("pois",[]) if p])


# ---------------------------------------------------------------------------
# Quest catalog: current json.tarkov.dev data + positional TarkovLab fallback.
# The browser only reads our local cache/API. Internet is used by this backend
# to refresh the cache, never by the HTML page directly.
# ---------------------------------------------------------------------------

def _http_json(url: str, timeout: float = 12.0):
    req = urllib.request.Request(url, headers={
        "User-Agent": "TarkovCompass/24.6",
        "Accept": "application/json,text/plain;q=0.9,*/*;q=0.8",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _data_node(raw: Any):
    return raw.get("data", raw) if isinstance(raw, dict) else raw


def _entities(raw: Any, key: str):
    node = _data_node(raw)
    if isinstance(node, dict) and key in node:
        node = node[key]
    if isinstance(node, list):
        return [x for x in node if isinstance(x, dict)]
    if isinstance(node, dict):
        out = []
        for k, v in node.items():
            if not isinstance(v, dict):
                continue
            q = dict(v)
            q.setdefault("id", k)
            out.append(q)
        return out
    return []


def _translations(raw: Any):
    node = _data_node(raw)
    if isinstance(node, dict):
        # Locale endpoints are normally a simple id->string table.
        if all(isinstance(v, str) for v in node.values()):
            return node
        for k in ("translations", "locale", "strings"):
            v = node.get(k)
            if isinstance(v, dict):
                return v
    return {}


def _tr(value: Any, table: dict[str, str]):
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("name") or value.get("shortName") or value.get("id")
    if not isinstance(value, str):
        return str(value)
    return table.get(value, value)


def _ref_id(value: Any):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("id") or value.get("_id") or value.get("item") or value.get("task")
    return None


def _humanize_slug(s: str | None):
    if not s:
        return "Onbekend"
    return re.sub(r"[-_]+", " ", str(s)).strip().title()


def _index_entities(rows: list[dict[str, Any]], translations: dict[str, str], kind: str):
    idx = {}
    for row in rows:
        rid = str(row.get("id") or "")
        if not rid:
            continue
        name = _tr(row.get("name") or row.get("shortName"), translations)
        if not name or name == row.get("name") and isinstance(name, str) and name.endswith(" name"):
            name = row.get("normalizedName") or name or rid
        normalized = row.get("normalizedName") or norm_name(name or rid)
        idx[rid] = {**row, "id": rid, "name": name or _humanize_slug(normalized), "normalizedName": normalized}
    return idx


def _map_ref(value: Any, map_idx: dict[str, dict[str, Any]]):
    if value is None:
        return None
    if isinstance(value, list):
        for x in value:
            mk = _map_ref(x, map_idx)
            if mk:
                return mk
        return None
    if isinstance(value, dict):
        rid = value.get("id") or value.get("_id")
        if rid and str(rid) in map_idx:
            return map_key(map_idx[str(rid)])
        return map_key(value)
    s = str(value)
    if s in map_idx:
        return map_key(map_idx[s])
    return ALIASES.get(norm_name(s))


def _infer_map_from_text(text: str | None):
    t = (text or "").lower()
    tests = [
        ("ground zero", "groundzero"), ("streets of tarkov", "streetsoftarkov"),
        ("streets", "streetsoftarkov"), ("the lab", "lab"), ("laboratory", "lab"),
        ("factory", "factory"), ("customs", "customs"), ("woods", "woods"),
        ("shoreline", "shoreline"), ("interchange", "interchange"), ("reserve", "reserve"),
        ("lighthouse", "lighthouse"), ("terminal", "terminal"), ("icebreaker", "icebreaker"),
        ("the labyrinth", "labyrinth"), ("labyrinth", "labyrinth"),
    ]
    for needle, key in tests:
        if needle in t:
            return key
    return None


def _resolve_item(value: Any, item_idx: dict[str, dict[str, Any]], item_tr: dict[str, str]):
    if value is None:
        return None
    if isinstance(value, dict):
        rid = str(value.get("id") or value.get("_id") or value.get("item") or "")
        name = _tr(value.get("name") or value.get("shortName"), item_tr)
        if rid in item_idx:
            name = item_idx[rid].get("name") or name
        return {"id": rid or norm_name(name or "item"), "name": name or _humanize_slug(rid)}
    rid = str(value)
    row = item_idx.get(rid)
    if row:
        return {"id": rid, "name": row.get("name") or _humanize_slug(row.get("normalizedName") or rid)}
    # TarkovLab fallback uses normalized item slugs, which are still readable.
    return {"id": rid, "name": _humanize_slug(rid)}


def _location_entry(mk: str | None, p: dict[str, Any], node: dict[str, Any] | None = None):
    if not isinstance(p, dict) or "x" not in p or "z" not in p:
        return None
    try:
        x, z = float(p["x"]), float(p["z"])
        y = float(p.get("y") or 0.0)
    except Exception:
        return None
    if not mk:
        return None
    node = node or {}
    level = None
    for field in ("level", "floor", "levelName"):
        if field in node and node.get(field) is not None:
            level = node.get(field)
            break
    name = node.get("name") or node.get("zoneName") or node.get("zoneId") or node.get("id")
    outline = node.get("outline") if isinstance(node.get("outline"), list) else None
    return {"map": mk, "x": x, "y": y, "z": z, "level": level, "name": name, "outline": outline, "supported": mk in maps_meta}


def _collect_locations(obj: Any, map_idx: dict[str, dict[str, Any]], default_map: str | None = None):
    found: list[dict[str, Any]] = []
    seen = set()
    def add(loc):
        if not loc:
            return
        key = (loc["map"], round(loc["x"], 2), round(loc["y"], 2), round(loc["z"], 2), str(loc.get("level")))
        if key not in seen:
            seen.add(key); found.append(loc)
    def walk(node: Any, inherited: str | None):
        if isinstance(node, list):
            for v in node:
                walk(v, inherited)
            return
        if not isinstance(node, dict):
            return
        mk = _map_ref(node.get("map") or node.get("maps") or node.get("location"), map_idx) or inherited
        # Direct TarkovLab projection format.
        if isinstance(node.get("world"), dict):
            add(_location_entry(mk or _map_ref(node.get("map"), map_idx), node["world"], node))
        # Tarkov.dev TaskZone/MapWithPosition format.
        if isinstance(node.get("position"), dict):
            add(_location_entry(mk, node["position"], node))
        # possibleLocations uses {map, positions:[{x,y,z}, ...]}.  Add the
        # coordinate rows explicitly rather than treating every nested x/z pair
        # as a spot (outline polygons also contain x/z points).
        if isinstance(node.get("positions"), list):
            for point in node.get("positions") or []:
                if isinstance(point, dict) and "x" in point and "z" in point:
                    add(_location_entry(mk, point, node))
        # Occasionally a location object is itself the position.
        if "x" in node and "z" in node and any(k in node for k in ("zoneId", "outline", "level", "floor", "top", "bottom")):
            add(_location_entry(mk, node, node))
        for k, v in node.items():
            if k in ("item", "items", "rewards", "properties", "trader", "task", "questItem", "requiredKeys", "usingWeapon", "usingWeaponMods", "wearing", "notWearing"):
                continue
            if k in ("zones", "possibleLocations", "locations", "positions", "position", "world", "map", "maps") or isinstance(v, (dict, list)):
                if k not in ("position", "world", "map", "maps"):
                    walk(v, mk)
    walk(obj, default_map)
    return found


def _req_append(out: list[dict[str, Any]], kind: str, item: dict[str, str] | None, count: Any = 1, found_in_raid: Any = None, note: str | None = None):
    if not item:
        return
    try:
        cnt = float(count if count is not None else 1)
        cnt = int(cnt) if cnt.is_integer() else cnt
    except Exception:
        cnt = 1
    rec = {"kind": kind, "id": item.get("id"), "name": item.get("name") or "Item", "count": cnt}
    if found_in_raid is not None:
        rec["foundInRaid"] = bool(found_in_raid)
    if note:
        rec["note"] = note
    key = (rec["kind"], rec["id"], str(rec.get("foundInRaid")), rec.get("note"))
    for old in out:
        oldkey = (old.get("kind"), old.get("id"), str(old.get("foundInRaid")), old.get("note"))
        if oldkey == key:
            old["count"] = max(float(old.get("count") or 1), float(rec["count"] or 1))
            return
    out.append(rec)


def _objective_requirements(obj: dict[str, Any], item_idx: dict[str, dict[str, Any]], item_tr: dict[str, str]):
    reqs: list[dict[str, Any]] = []
    typ = str(obj.get("type") or "").lower()
    count = obj.get("count") or obj.get("number") or 1
    fir = obj.get("foundInRaid")
    item = obj.get("item")
    qitem = obj.get("questItem")
    if item is not None:
        _req_append(reqs, "item", _resolve_item(item, item_idx, item_tr), count, fir)
    if qitem is not None:
        _req_append(reqs, "questItem", _resolve_item(qitem, item_idx, item_tr), count, fir, "Quest item")
    items = obj.get("items")
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict):
                _req_append(reqs, "item", _resolve_item(it.get("item") or it.get("id") or it, item_idx, item_tr), it.get("count") or count, it.get("foundInRaid", fir))
            else:
                _req_append(reqs, "item", _resolve_item(it, item_idx, item_tr), count, fir)
    for key in ("requiredKeys", "keys"):
        vals = obj.get(key) or []
        if not isinstance(vals, list):
            vals = [vals]
        for group in vals:
            # JSON API may encode key alternatives as [[Item, Item], [Item]].
            alternatives = group if isinstance(group, list) else [group]
            names = []
            resolved = []
            for it in alternatives:
                item_value = it.get("item") if isinstance(it, dict) and "item" in it else it
                ri = _resolve_item(item_value, item_idx, item_tr)
                if ri:
                    resolved.append(ri); names.append(ri.get("name") or "Key")
            if len(resolved) == 1:
                _req_append(reqs, "key", resolved[0], 1, None, "Key / keycard")
            elif resolved:
                # One of the alternatives is sufficient. Keep it as a single requirement row.
                _req_append(reqs, "keyAlternative", {"id":"or:" + "|".join(str(x.get("id")) for x in resolved), "name":" OF ".join(names)}, 1, None, "Eén van deze keys/keycards")
    for field, kind, note in (("usingWeapon","gear","Weapon"),("usingWeaponMods","gear","Weapon mod"),("wearing","gear","Wear"),("notWearing","restriction","Do not wear")):
        vals = obj.get(field) or []
        if not isinstance(vals, list): vals = [vals]
        for it in vals:
            _req_append(reqs, kind, _resolve_item(it.get("item") if isinstance(it,dict) and "item" in it else it, item_idx, item_tr), 1, None, note)
    # A few universally useful fallbacks when a legacy source only has text.
    desc = str(obj.get("description") or "")
    if not reqs and "MS2000 Marker" in desc:
        _req_append(reqs, "item", {"id":"ms2000-marker","name":"MS2000 Marker"}, 1, None, "Marker")
    if not reqs and "Wi-Fi Camera" in desc:
        _req_append(reqs, "item", {"id":"wi-fi-camera","name":"Wi-Fi Camera"}, 1, None, "Place item")
    # Legacy/fallback quest feeds may only expose human objective text. Preserve a
    # useful checklist instead of showing nothing at all. This is intentionally
    # conservative and never overrides structured API requirements.
    if not reqs and typ in ("giveitem", "finditem", "collect", "handover", "givequestitem", "findquestitem"):
        m = re.search(r"(?:hand over|find|obtain|locate and obtain|collect)\s+(?:the\s+)?(?:(found in raid|found-in-raid)\s+)?(?:(\d+(?:\.\d+)?)\s*[x×]?\s*)?(.+?)(?:\s+on\s+[A-Z][A-Za-z ]+)?$", desc, re.I)
        if m:
            item_name = re.sub(r"^(?:item|items)[:\s-]+", "", (m.group(3) or "").strip(), flags=re.I).strip(" .")
            # Avoid treating whole generic quest sentences as item names.
            if item_name and len(item_name) < 110 and not item_name.lower().startswith(("the location", "the area", "the quest")):
                try: txt_count=float(m.group(2) or count or 1); txt_count=int(txt_count) if txt_count.is_integer() else txt_count
                except Exception: txt_count=count or 1
                _req_append(reqs, "questItem" if "questitem" in typ else "item", {"id":"text:"+norm_name(item_name),"name":item_name}, txt_count, bool(m.group(1)) if m.group(1) else fir, "Uit questdoel afgeleid")
    return reqs


def _normalize_objective(obj: dict[str, Any], task_map: str | None, task_tr: dict[str, str], item_idx: dict[str, dict[str, Any]], item_tr: dict[str, str], map_idx: dict[str, dict[str, Any]]):
    desc = _tr(obj.get("description") or obj.get("name") or obj.get("type") or "Objective", task_tr) or "Objective"
    omap = _map_ref(obj.get("map") or obj.get("maps"), map_idx) or task_map or _infer_map_from_text(desc)
    locs = _collect_locations(obj, map_idx, omap)
    return {
        "id": str(obj.get("id") or norm_name(desc)),
        "type": str(obj.get("type") or "objective"),
        "description": desc,
        "optional": bool(obj.get("optional", False)),
        "count": obj.get("count") or obj.get("number"),
        "maps": sorted({x["map"] for x in locs} | ({omap} if omap else set())),
        "locations": locs,
        "requirements": _objective_requirements(obj, item_idx, item_tr),
        "rawHints": {k: obj.get(k) for k in ("targetNames","bodyParts","distance","exitName","exitStatus","zoneNames","timeFromHour","timeUntilHour") if obj.get(k) not in (None,[],"")},
    }


def _aggregate_requirements(objectives: list[dict[str, Any]]):
    out: list[dict[str, Any]] = []
    for obj in objectives:
        for r in obj.get("requirements") or []:
            # For paired find/give objectives, maximum required count is more useful than sum.
            key = (r.get("kind"), r.get("id"), bool(r.get("foundInRaid")), r.get("note"))
            hit = next((x for x in out if (x.get("kind"),x.get("id"),bool(x.get("foundInRaid")),x.get("note")) == key), None)
            if hit:
                # Placement consumables (markers/cameras) are spent per objective; find+handover
                # pairs should not be double-counted, hence max for ordinary item requirements.
                if r.get("note") in ("Marker", "Place item"):
                    hit["count"] = float(hit.get("count") or 1) + float(r.get("count") or 1)
                else:
                    hit["count"] = max(float(hit.get("count") or 1), float(r.get("count") or 1))
                if float(hit.get("count") or 0).is_integer():
                    hit["count"] = int(hit["count"])
            else:
                out.append(dict(r))
    return out


def _objective_patch_map(value: Any):
    """Return objective patches keyed by objective id for overlay-compatible shapes."""
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items() if isinstance(v, dict)}
    if isinstance(value, list):
        out = {}
        for row in value:
            if isinstance(row, dict) and row.get("id"):
                out[str(row["id"])] = row
        return out
    return {}


def _objective_additions(value: Any):
    if isinstance(value, list):
        return [copy.deepcopy(x) for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        out = []
        for oid, row in value.items():
            if not isinstance(row, dict):
                continue
            q = copy.deepcopy(row); q.setdefault("id", oid); out.append(q)
        return out
    return []


def _apply_task_patch(task: dict[str, Any], patch: Any):
    """Apply tarkov-data-overlay task patch semantics, including objective patches/additions."""
    if not isinstance(patch, dict):
        return copy.deepcopy(task)
    result = copy.deepcopy(task)
    for key, value in patch.items():
        if key in ("objectives", "objectivesAdd"):
            continue
        result[key] = copy.deepcopy(value)

    base_objectives = [copy.deepcopy(x) for x in (result.get("objectives") or []) if isinstance(x, dict)]
    patches = _objective_patch_map(patch.get("objectives"))
    if patches:
        for i, obj in enumerate(base_objectives):
            oid = str(obj.get("id") or "")
            opatch = patches.get(oid)
            if opatch:
                merged = dict(obj)
                merged.update(copy.deepcopy(opatch))
                merged.setdefault("id", oid)
                base_objectives[i] = merged

    additions = _objective_additions(patch.get("objectivesAdd"))
    if additions:
        by_id = {str(x.get("id")): i for i, x in enumerate(base_objectives) if x.get("id")}
        for obj in additions:
            oid = str(obj.get("id") or "")
            if oid and oid in by_id:
                merged = dict(base_objectives[by_id[oid]])
                merged.update(obj)
                base_objectives[by_id[oid]] = merged
            else:
                if oid:
                    by_id[oid] = len(base_objectives)
                base_objectives.append(obj)
    result["objectives"] = base_objectives
    return result


def _overlay_task_rows(tasks: list[dict[str, Any]], overlay: Any, game_mode: str = "regular", locale: str = "en"):
    """Apply shared -> mode -> locale overlay data and append tasksAdd entries by id."""
    rows = [copy.deepcopy(x) for x in tasks if isinstance(x, dict)]
    if not isinstance(overlay, dict):
        return rows

    shared_patches = overlay.get("tasks") if isinstance(overlay.get("tasks"), dict) else {}
    modes = overlay.get("modes") if isinstance(overlay.get("modes"), dict) else {}
    mode = modes.get(game_mode) if isinstance(modes.get(game_mode), dict) else {}
    mode_patches = mode.get("tasks") if isinstance(mode.get("tasks"), dict) else {}
    locales = overlay.get("locales") if isinstance(overlay.get("locales"), dict) else {}
    locale_node = locales.get(locale) if isinstance(locales.get(locale), dict) else {}
    locale_patches = locale_node.get("tasks") if isinstance(locale_node.get("tasks"), dict) else {}

    additions: dict[str, dict[str, Any]] = {}
    for node in (overlay.get("tasksAdd"), mode.get("tasksAdd") if isinstance(mode, dict) else None):
        if not isinstance(node, dict):
            continue
        for tid, row in node.items():
            if not isinstance(row, dict):
                continue
            q = copy.deepcopy(row); q.setdefault("id", tid)
            if str(tid) in additions:
                q = _apply_task_patch(additions[str(tid)], q)
            additions[str(tid)] = q

    by_id = {str(x.get("id")): i for i, x in enumerate(rows) if x.get("id")}
    for tid, add in additions.items():
        if tid in by_id:
            rows[by_id[tid]] = _apply_task_patch(rows[by_id[tid]], add)
        else:
            by_id[tid] = len(rows)
            rows.append(add)

    out = []
    for task in rows:
        tid = str(task.get("id") or "")
        cur = task
        if tid and tid in shared_patches:
            cur = _apply_task_patch(cur, shared_patches[tid])
        if tid and tid in mode_patches:
            cur = _apply_task_patch(cur, mode_patches[tid])
        if tid and tid in locale_patches:
            cur = _apply_task_patch(cur, locale_patches[tid])
        if cur.get("disabled") is True:
            continue
        out.append(cur)
    return out


def _merge_location_lists(existing: Any, extra: Any):
    """Union quest spots without losing richer metadata from either source."""
    out: list[dict[str, Any]] = []
    for group in (existing or [], extra or []):
        if not isinstance(group, list):
            continue
        for source in group:
            if not isinstance(source, dict):
                continue
            try:
                base = (
                    source.get("map"), round(float(source.get("x")), 2),
                    round(float(source.get("y") or 0.0), 2), round(float(source.get("z")), 2)
                )
            except Exception:
                continue
            level = source.get("level")
            match = None
            for i, current in enumerate(out):
                try:
                    cur_base = (
                        current.get("map"), round(float(current.get("x")), 2),
                        round(float(current.get("y") or 0.0), 2), round(float(current.get("z")), 2)
                    )
                except Exception:
                    continue
                cur_level = current.get("level")
                # The same physical spot often arrives once without floor metadata
                # and once with it.  Merge those rows, but keep genuinely distinct
                # floor-specific locations separate.
                if cur_base == base and (cur_level == level or cur_level is None or level is None):
                    match = i
                    break
            if match is None:
                out.append(copy.deepcopy(source)); continue
            current = out[match]
            for field in ("name", "level", "outline", "supported"):
                if current.get(field) in (None, "", []) and source.get(field) not in (None, "", []):
                    current[field] = copy.deepcopy(source.get(field))
    return out


def _quest_spot_stats(quests: list[dict[str, Any]]):
    mapped_quests = 0; mapped_objectives = 0; spots = 0; unsupported = 0
    for q in quests:
        q_has = False
        for obj in q.get("objectives") or []:
            locs = [x for x in (obj.get("locations") or []) if isinstance(x, dict)]
            if locs:
                q_has = True; mapped_objectives += 1; spots += len(locs)
                unsupported += sum(1 for x in locs if x.get("supported") is False)
        if q_has:
            mapped_quests += 1
    return {"quests": len(quests), "mappedQuests": mapped_quests, "mappedObjectives": mapped_objectives, "spots": spots, "unsupportedSpots": unsupported}


def _normalize_tasks_current(tasks_raw: Any, tasks_en: Any, items_raw: Any, items_en: Any, maps_raw: Any, maps_en: Any, traders_raw: Any, traders_en: Any, overlay: Any = None):
    task_tr = _translations(tasks_en); item_tr = _translations(items_en); map_tr = _translations(maps_en); trader_tr = _translations(traders_en)
    item_idx = _index_entities(_entities(items_raw,"items"), item_tr, "item")
    map_idx = _index_entities(_entities(maps_raw,"maps"), map_tr, "map")
    trader_idx = _index_entities(_entities(traders_raw,"traders"), trader_tr, "trader")
    if isinstance(overlay, dict) and isinstance(overlay.get("itemsAdd"), dict):
        for iid, row in overlay["itemsAdd"].items():
            if not isinstance(row, dict): continue
            q=dict(row); q.setdefault("id", iid)
            item_idx[str(iid)] = {**q, "name": q.get("name") or q.get("shortName") or _humanize_slug(str(iid)), "normalizedName": q.get("normalizedName") or norm_name(q.get("name") or str(iid))}
    tasks = _overlay_task_rows(_entities(tasks_raw,"tasks"), overlay, "regular", "en")
    out=[]
    for t in tasks:
        tid=str(t.get("id") or "")
        if not tid: continue
        name=_tr(t.get("name") or t.get("title"), task_tr) or t.get("normalizedName") or tid
        normalized=t.get("normalizedName") or norm_name(name)
        task_map=_map_ref(t.get("map"),map_idx) or _infer_map_from_text(name)
        trader_ref=_ref_id(t.get("trader")); trader_name=None
        if trader_ref and trader_ref in trader_idx: trader_name=trader_idx[trader_ref].get("name")
        if not trader_name: trader_name=_tr(t.get("trader"),trader_tr) if not isinstance(t.get("trader"),dict) else _tr(t.get("trader"),trader_tr)
        objectives=[_normalize_objective(o,task_map,task_tr,item_idx,item_tr,map_idx) for o in (t.get("objectives") or []) if isinstance(o,dict)]
        maps_set={task_map} if task_map else set()
        for o in objectives: maps_set.update(o.get("maps") or [])
        prereqs=[]
        for req in t.get("taskRequirements") or t.get("requirements") or []:
            if not isinstance(req,dict): continue
            rr=_ref_id(req.get("task") or req.get("quest")); rname=None
            if rr:
                # Name might itself be embedded in object.
                tv=req.get("task") or req.get("quest")
                if isinstance(tv,dict): rname=_tr(tv.get("name"),task_tr)
            prereqs.append({"id":rr,"name":rname or rr or "Quest","status":req.get("status") or req.get("statuses") or []})
        quest={
            "id":tid,"gameId":tid,"name":name,"normalizedName":normalized,"trader":trader_name or "Unknown",
            "map":task_map,"maps":sorted(m for m in maps_set if m),
            "minPlayerLevel":t.get("minPlayerLevel") or 0,"experience":t.get("experience"),
            "kappa":bool(t.get("kappaRequired") or t.get("kappa")),"lightkeeper":bool(t.get("lightkeeperRequired") or t.get("lightkeeper")),
            "faction":t.get("factionName") or t.get("faction"),"wiki":t.get("wikiLink") or t.get("wiki"),
            "imageLink":t.get("taskImageLink") or t.get("imageLink"),"objectives":objectives,
            "requirements":_aggregate_requirements(objectives),"prerequisites":prereqs,
            "startRewards":t.get("startRewards") or {},"finishRewards":t.get("finishRewards") or {},
            "source":"json.tarkov.dev",
        }
        quest["hasLocations"]=any(o.get("locations") for o in objectives)
        out.append(quest)
    # Name prerequisite tasks after all tasks are known.
    names={q["id"]:q["name"] for q in out}
    for q in out:
        for r in q["prerequisites"]:
            if r.get("id") in names: r["name"]=names[r["id"]]
    return out


def _normalize_objective_snapshot(raw: Any):
    """Normalize the current structured objective slice into a positional supplement.

    The snapshot deliberately contains no quest metadata such as trader/name; it is
    joined onto the canonical task catalog by quest/objective id.
    """
    node = raw.get("quests", []) if isinstance(raw, dict) else []
    out = []
    for t in node:
        if not isinstance(t, dict):
            continue
        tid = str(t.get("id") or "")
        if not tid:
            continue
        task_map = _map_ref(t.get("objectiveMaps"), {})
        objs = []
        for o in t.get("objectives") or []:
            if not isinstance(o, dict):
                continue
            desc = o.get("description") or o.get("type") or "Objective"
            omap = _map_ref(o.get("maps") or o.get("map"), {}) or task_map or _infer_map_from_text(desc)
            locs = _collect_locations(o, {}, omap)
            objs.append({
                "id": str(o.get("id") or norm_name(desc)),
                "type": str(o.get("type") or "objective"),
                "description": desc,
                "optional": bool(o.get("optional", False)),
                "count": o.get("count") or o.get("number"),
                "maps": sorted({x["map"] for x in locs} | ({omap} if omap else set())),
                "locations": locs,
                "requirements": [],
                "rawHints": {},
            })
        maps_set = {task_map} if task_map else set()
        for o in objs:
            maps_set.update(o.get("maps") or [])
        out.append({
            "id": tid, "gameId": tid, "name": tid, "normalizedName": tid,
            "trader": "Unknown", "map": task_map,
            "maps": sorted(m for m in maps_set if m),
            "objectives": objs, "requirements": [], "prerequisites": [],
            "source": "current objective snapshot",
            "hasLocations": any(o.get("locations") for o in objs),
        })
    return out


def _story_point_locations(obj: dict[str, Any]):
    locs: list[dict[str, Any]] = []
    for group in obj.get("points") or []:
        if not isinstance(group, dict):
            continue
        mk = _map_ref(group.get("map"), {})
        floor = group.get("floor")
        pts = [p for p in (group.get("pts") or []) if isinstance(p, dict) and "x" in p and "z" in p]
        if str(group.get("kind") or "").lower() == "area" and len(pts) >= 3:
            # Story data distinguishes search/visit areas from exact pins.  Keep
            # the polygon as one interactive zone rather than turning every
            # polygon vertex into a fake quest spot.  The marker lives at the
            # polygon centroid while the outline remains available to the map UI.
            ring = []
            for p in pts:
                try:
                    ring.append({"x": float(p["x"]), "z": float(p["z"])})
                except Exception:
                    pass
            if len(ring) >= 3:
                # Ignore a repeated closing vertex when calculating the centroid.
                core = ring[:-1] if len(ring) > 3 and ring[0] == ring[-1] else ring
                area2 = 0.0; cx_num = 0.0; cz_num = 0.0
                for i, p in enumerate(core):
                    nxt = core[(i + 1) % len(core)]
                    cross = p["x"] * nxt["z"] - nxt["x"] * p["z"]
                    area2 += cross
                    cx_num += (p["x"] + nxt["x"]) * cross
                    cz_num += (p["z"] + nxt["z"]) * cross
                if abs(area2) > 1e-9:
                    cx = cx_num / (3.0 * area2)
                    cz = cz_num / (3.0 * area2)
                else:
                    # Degenerate polygon fallback: keep a usable marker even if a
                    # source accidentally publishes collinear points.
                    cx = sum(p["x"] for p in core) / len(core)
                    cz = sum(p["z"] for p in core) / len(core)
                node = {"floor": floor, "name": obj.get("description"), "outline": ring}
                q = _location_entry(mk, {"x": cx, "y": 0, "z": cz}, node)
                if q:
                    locs.append(q)
            continue
        for point in pts:
            if not isinstance(point, dict):
                continue
            node = {"floor": floor, "name": obj.get("description")}
            q = _location_entry(mk, point, node)
            if q:
                locs.append(q)
    return _merge_location_lists([], locs)


def _normalize_story_chapters(raw: Any):
    """Turn storyline chapters into normal interactive quest records."""
    story = raw.get("story") if isinstance(raw, dict) else None
    chapters = story.get("chapters") if isinstance(story, dict) else []
    if not isinstance(chapters, list):
        return []
    out = []
    slug_to_id = {}
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        slug = str(ch.get("id") or norm_name(ch.get("name") or "story"))
        qid = "story:" + str(ch.get("questId") or slug)
        slug_to_id[slug] = qid
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        slug = str(ch.get("id") or norm_name(ch.get("name") or "story"))
        qid = slug_to_id.get(slug) or ("story:" + slug)
        objs = []
        for o in ch.get("objectives") or []:
            if not isinstance(o, dict):
                continue
            desc = str(o.get("description") or o.get("type") or "Story objective")
            omap = _map_ref(o.get("maps") or o.get("map"), {}) or _infer_map_from_text(desc)
            locs = _merge_location_lists(_collect_locations(o, {}, omap), _story_point_locations(o))
            maps_set = {x.get("map") for x in locs if x.get("map")}
            for name in o.get("maps") or []:
                mk = _map_ref(name, {})
                if mk:
                    maps_set.add(mk)
            obj_reqs = []
            needs = o.get("needs")
            if needs:
                need_rows = needs if isinstance(needs, list) else [needs]
                for need in need_rows:
                    if isinstance(need, dict):
                        label = str(need.get("name") or need.get("id") or "Required item")
                    else:
                        label = str(need)
                    if label.strip():
                        _req_append(
                            obj_reqs, "storyNeed",
                            {"id": "story:" + norm_name(label), "name": label.strip()},
                            1, note="Nodig voor dit storyline-objective"
                        )
            objs.append({
                "id": str(o.get("id") or norm_name(desc)),
                "type": str(o.get("type") or "story"),
                "description": desc,
                "optional": str(o.get("type") or "").lower() == "optional",
                "count": o.get("count"),
                "maps": sorted(maps_set),
                "locations": locs,
                "requirements": obj_reqs,
                "rawHints": {"sourceQuestId": o.get("sourceQuestId")} if o.get("sourceQuestId") else {},
            })
        maps_set = set()
        for o in objs:
            maps_set.update(o.get("maps") or [])
        prereqs = []
        for req in ch.get("requires") or []:
            rid = slug_to_id.get(str(req), "story:" + str(req))
            prereqs.append({"id": rid, "name": str(req).replace("-", " ").title(), "status": ["complete"]})
        q = {
            "id": qid,
            "gameId": str(ch.get("questId") or qid),
            "publicId": slug,
            "name": str(ch.get("name") or _humanize_slug(slug)),
            "normalizedName": slug,
            "trader": "Story",
            "map": next(iter(maps_set)) if len(maps_set) == 1 else None,
            "maps": sorted(maps_set),
            "minPlayerLevel": 0, "experience": None,
            "kappa": False, "lightkeeper": False, "faction": None,
            "wiki": ch.get("wikiLink"), "imageLink": None,
            "objectives": objs, "requirements": _aggregate_requirements(objs), "prerequisites": prereqs,
            "startRewards": {}, "finishRewards": {},
            "source": "story campaign / hand-placed map data",
            "hasLocations": any(o.get("locations") for o in objs),
            "story": True, "storyOrder": ch.get("order"), "wip": bool(ch.get("wip")),
        }
        out.append(q)
    names = {q.get("id"): q.get("name") for q in out}
    for q in out:
        for req in q.get("prerequisites") or []:
            if req.get("id") in names:
                req["name"] = names[req["id"]]
    return out


def _parse_map_objective_key(key: str):
    """Parse map|objectiveId|x|z keys; labels may contain pipes, ids do not."""
    try:
        left, xs, zs = str(key).rsplit("|", 2)
        map_name, objective_id = left.split("|", 1)
        return _map_ref(map_name, {}), objective_id, float(xs), float(zs)
    except Exception:
        return None


def _apply_map_objective_corrections(quests: list[dict[str, Any]], raw: Any):
    """Apply hand-checked coordinate/floor corrections and remove known false pins."""
    corrections = raw.get("corrections") if isinstance(raw, dict) else None
    if not isinstance(corrections, dict):
        return {"moved": 0, "floors": 0, "hidden": 0}
    moved: dict[tuple[str, str], list[tuple[float, float, float, float]]] = {}
    for key, value in (corrections.get("objectives") or {}).items():
        parsed = _parse_map_objective_key(key)
        if not parsed or not isinstance(value, dict):
            continue
        mk, oid, ox, oz = parsed
        try:
            nx, nz = float(value["x"]), float(value["z"])
        except Exception:
            continue
        moved.setdefault((mk, str(oid)), []).append((ox, oz, nx, nz))
    floors: dict[tuple[str, str], list[tuple[float, float, Any]]] = {}
    for key, floor in (corrections.get("objectiveFloors") or {}).items():
        parsed = _parse_map_objective_key(key)
        if not parsed:
            continue
        mk, oid, ox, oz = parsed
        floors.setdefault((mk, str(oid)), []).append((ox, oz, floor))
    hidden: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for key, flag in (corrections.get("hidden") or {}).items():
        if not flag or not str(key).startswith("api|"):
            continue
        parsed = _parse_map_objective_key(str(key)[4:])
        if not parsed:
            continue
        mk, oid, ox, oz = parsed
        hidden.setdefault((mk, str(oid)), []).append((ox, oz))

    counts = {"moved": 0, "floors": 0, "hidden": 0}
    for q in quests:
        for obj in q.get("objectives") or []:
            oid = str(obj.get("id") or "")
            kept = []
            for loc in obj.get("locations") or []:
                if not isinstance(loc, dict) or not loc.get("map"):
                    continue
                mk = loc.get("map")
                try:
                    x, z = float(loc.get("x")), float(loc.get("z"))
                except Exception:
                    kept.append(loc); continue
                is_hidden = any(abs(x-ox) <= 1.25 and abs(z-oz) <= 1.25 for ox, oz in hidden.get((mk, oid), []))
                if is_hidden:
                    counts["hidden"] += 1
                    continue
                for ox, oz, nx, nz in moved.get((mk, oid), []):
                    if abs(x-ox) <= 1.25 and abs(z-oz) <= 1.25:
                        loc["x"], loc["z"] = nx, nz
                        x, z = nx, nz
                        counts["moved"] += 1
                        break
                for ox, oz, floor in floors.get((mk, oid), []):
                    # Floor keys are based on the original source coordinate, while
                    # positional corrections may already have moved the marker.
                    rawx = float(loc.get("x")); rawz = float(loc.get("z"))
                    if abs(rawx-ox) <= 1.25 and abs(rawz-oz) <= 1.25 or any(
                        abs(ox-mox) <= 0.01 and abs(oz-moz) <= 0.01 and abs(rawx-nx) <= 1.25 and abs(rawz-nz) <= 1.25
                        for mox, moz, nx, nz in moved.get((mk, oid), [])
                    ):
                        loc["level"] = floor
                        counts["floors"] += 1
                        break
                kept.append(loc)
            obj["locations"] = _merge_location_lists([], kept)
            obj["maps"] = sorted(set(obj.get("maps") or []) | {x.get("map") for x in obj["locations"] if x.get("map")})
        q["maps"] = sorted(set(q.get("maps") or []) | {m for o in q.get("objectives") or [] for m in (o.get("maps") or []) if m})
        q["hasLocations"] = any(o.get("locations") for o in q.get("objectives") or [])
    return counts


def _merge_positional_quests(primary: list[dict[str, Any]], supplement: list[dict[str, Any]], only_when_empty: bool = False):
    """Merge positional data by quest/objective id while preserving canonical metadata."""
    if not primary:
        return supplement
    fb = {str(q.get("gameId") or q.get("id")): q for q in supplement if q.get("gameId") or q.get("id")}
    fbslug = {q.get("normalizedName"): q for q in supplement if q.get("normalizedName")}
    for q in primary:
        f = fb.get(str(q.get("gameId") or q.get("id"))) or fbslug.get(q.get("normalizedName"))
        if not f:
            continue
        if not q.get("name") or str(q["name"]).endswith(" name"):
            q["name"] = f.get("name") or q["name"]
        if q.get("trader") in (None, "Unknown") and f.get("trader"):
            q["trader"] = f["trader"]
        current = q.get("objectives") or []
        by_id = {str(o.get("id")): o for o in current if o.get("id")}
        for extra_obj in f.get("objectives") or []:
            if not isinstance(extra_obj, dict):
                continue
            match = by_id.get(str(extra_obj.get("id") or ""))
            if not match:
                match = next((o for o in current if norm_name(o.get("description")) == norm_name(extra_obj.get("description"))), None)
            if match:
                if extra_obj.get("locations") and (not only_when_empty or not match.get("locations")):
                    match["locations"] = _merge_location_lists(match.get("locations") or [], extra_obj.get("locations") or [])
                    match["maps"] = sorted(set(match.get("maps") or []) | set(extra_obj.get("maps") or []) | {loc.get("map") for loc in match["locations"] if loc.get("map")})
            elif extra_obj.get("locations"):
                added = copy.deepcopy(extra_obj)
                current.append(added)
                if added.get("id"):
                    by_id[str(added["id"])] = added
        q["objectives"] = current
        q["maps"] = sorted(set(q.get("maps") or []) | set(f.get("maps") or []) | {m for o in current for m in (o.get("maps") or []) if m})
        q["hasLocations"] = any(o.get("locations") for o in current)
        if not q.get("wiki"):
            q["wiki"] = f.get("wiki")
    return primary


def _normalize_tarkovlab(raw: Any):
    node=raw.get("quests",[]) if isinstance(raw,dict) else []
    out=[]
    for t in node:
        if not isinstance(t,dict): continue
        tid=str(t.get("gameId") or t.get("id") or "")
        if not tid: continue
        task_map=ALIASES.get(norm_name(t.get("map") or ""))
        objs=[]
        for o in t.get("objectives") or []:
            if not isinstance(o,dict): continue
            desc=o.get("description") or o.get("type") or "Objective"
            locs=[]
            for l in o.get("locations") or []:
                if not isinstance(l,dict): continue
                mk=ALIASES.get(norm_name(l.get("map") or "")) or task_map or _infer_map_from_text(desc)
                world=l.get("world") or {}
                q=_location_entry(mk,world,l)
                if q: locs.append(q)
            fake=dict(o); fake["description"]=desc
            reqs=_objective_requirements(fake,{}, {})
            objs.append({"id":str(o.get("id") or norm_name(desc)),"type":str(o.get("type") or "objective"),"description":desc,"optional":bool(o.get("optional",False)),"count":o.get("count"),"maps":sorted({x["map"] for x in locs} | ({task_map} if task_map else set())),"locations":locs,"requirements":reqs,"rawHints":{}})
        maps_set={task_map} if task_map else set()
        for o in objs: maps_set.update(o.get("maps") or [])
        q={"id":tid,"gameId":tid,"publicId":t.get("id"),"name":t.get("name") or _humanize_slug(t.get("normalizedName")),"normalizedName":t.get("normalizedName") or t.get("id"),"trader":t.get("trader") or "Unknown","map":task_map,"maps":sorted(m for m in maps_set if m),"minPlayerLevel":t.get("minPlayerLevel") or 0,"experience":t.get("experience"),"kappa":bool(t.get("kappa")),"lightkeeper":bool(t.get("lightkeeper")),"faction":t.get("faction"),"wiki":t.get("wiki"),"imageLink":t.get("imageLink"),"objectives":objs,"requirements":_aggregate_requirements(objs),"prerequisites":[],"startRewards":t.get("startRewards") or {},"finishRewards":t.get("finishRewards") or {},"source":"TarkovLab positional snapshot","hasLocations":any(o.get("locations") for o in objs)}
        out.append(q)
    return out


def _merge_tarkovlab(primary: list[dict[str,Any]], fallback: list[dict[str,Any]]):
    # Backward-compatible name used by older tests/callers; legacy snapshots are
    # intentionally only used to fill objectives that are still empty.
    return _merge_positional_quests(primary, fallback, only_when_empty=True)


def _quest_summary(q: dict[str,Any]):
    search_bits=[q.get("name") or "", q.get("trader") or ""]
    search_bits += [o.get("description") or "" for o in (q.get("objectives") or [])]
    search_bits += [r.get("name") or "" for r in (q.get("requirements") or [])]
    # Keep the catalog lightweight, but expose the dependency + raid-kit data
    # needed by the local account progression planner. Full objective/location
    # payloads remain behind /api/quest.
    reqs=[]
    for r in (q.get("requirements") or []):
        if not isinstance(r,dict): continue
        reqs.append({k:r.get(k) for k in ("kind","id","name","count","foundInRaid","note") if r.get(k) is not None})
    prereqs=[]
    for r in (q.get("prerequisites") or []):
        if not isinstance(r,dict): continue
        prereqs.append({"id":r.get("id"),"name":r.get("name") or r.get("id") or "Quest","status":r.get("status") or []})
    return {
        "id":q.get("id"),"name":q.get("name"),"trader":q.get("trader"),"map":q.get("map"),"maps":q.get("maps") or [],
        "minPlayerLevel":q.get("minPlayerLevel") or 0,"experience":q.get("experience"),
        "kappa":bool(q.get("kappa")),"lightkeeper":bool(q.get("lightkeeper")),"story":bool(q.get("story")),"faction":q.get("faction"),
        "objectiveCount":len(q.get("objectives") or []),"requirementCount":len(reqs),"requirements":reqs,"prerequisites":prereqs,
        "hasLocations":bool(q.get("hasLocations")),"source":q.get("source"),"searchText":" ".join(search_bits)
    }


def load_quest_cache():
    global quest_catalog, quest_index
    try:
        raw=json.loads(QUEST_CACHE.read_text(encoding="utf-8"))
        qs=raw.get("quests") if isinstance(raw,dict) else []
        if not isinstance(qs,list): qs=[]
        with quest_lock:
            quest_catalog=qs; quest_index={str(q.get("id")):q for q in qs if q.get("id")}
        stats=_quest_spot_stats(qs)
        with state_lock:
            state["quest_count"]=len(qs); state["quest_updated"]=raw.get("updated") if isinstance(raw,dict) else None; state["quest_source"]=raw.get("source") if isinstance(raw,dict) else None; state["quest_status"]="lokale questcache geladen" if qs else "questcache leeg"
            state["quest_spot_count"]=stats["spots"]; state["quest_mapped_objectives"]=stats["mappedObjectives"]; state["quest_mapped_quests"]=stats["mappedQuests"]
            state["quest_story_count"]=int(raw.get("storyCount") or sum(1 for q in qs if q.get("story"))) if isinstance(raw,dict) else 0
            state["quest_position_corrections"]=(raw.get("positionCorrections") or {"moved":0,"floors":0,"hidden":0}) if isinstance(raw,dict) else {"moved":0,"floors":0,"hidden":0}
        if qs: quest_ready.set()
    except Exception as exc:
        with state_lock: state["quest_status"]=f"questcache fout: {exc}"


def refresh_quest_data():
    global quest_catalog, quest_index
    with state_lock:
        state["quest_status"] = "actuele questdata en quest-spots laden..."
    primary = []
    positional = []
    legacy = []
    story = []
    map_side = {}
    primary_error = None
    positional_error = None
    fallback_error = None
    urls = {
        "tasks": ("https://json.tarkov.dev/regular/tasks", 14.0),
        "tasks_en": ("https://json.tarkov.dev/regular/tasks_en", 14.0),
        "items": ("https://json.tarkov.dev/regular/items", 14.0),
        "items_en": ("https://json.tarkov.dev/regular/items_en", 14.0),
        "maps": ("https://json.tarkov.dev/regular/maps", 14.0),
        "maps_en": ("https://json.tarkov.dev/regular/maps_en", 14.0),
        "traders": ("https://json.tarkov.dev/regular/traders", 14.0),
        "traders_en": ("https://json.tarkov.dev/regular/traders_en", 14.0),
        "overlay": ("https://cdn.jsdelivr.net/gh/tarkovtracker-org/tarkov-data-overlay@main/dist/overlay.json", 16.0),
        # Current structured objectives: includes zones and possibleLocations with
        # multiple positions, joined by stable quest/objective ids.
        "objective_snapshot": ("https://szepiz.github.io/tarkov-quest-data/api/quests/objectives.json", 20.0),
        # Hand-checked quest-pin corrections plus storyline chapter coordinates.
        "map_side": ("https://szepiz.github.io/tarkov-quest-data/api/maps.json", 20.0),
    }
    docs = {}
    try:
        with ThreadPoolExecutor(max_workers=len(urls)) as ex:
            fut = {ex.submit(_http_json, url, timeout): key for key, (url, timeout) in urls.items()}
            for f in as_completed(fut):
                key = fut[f]
                try:
                    docs[key] = f.result()
                except Exception:
                    docs[key] = None
        if docs.get("tasks"):
            primary = _normalize_tasks_current(
                docs.get("tasks"), docs.get("tasks_en") or {},
                docs.get("items") or {}, docs.get("items_en") or {},
                docs.get("maps") or {}, docs.get("maps_en") or {},
                docs.get("traders") or {}, docs.get("traders_en") or {},
                docs.get("overlay") or {},
            )
        if len(primary) < 100:
            raise RuntimeError(f"json.tarkov.dev leverde maar {len(primary)} bruikbare quests")
    except Exception as exc:
        primary_error = str(exc)
        primary = []

    try:
        if docs.get("objective_snapshot"):
            positional = _normalize_objective_snapshot(docs["objective_snapshot"])
        if len(positional) < 100:
            raise RuntimeError(f"current objective snapshot leverde maar {len(positional)} quests")
    except Exception as exc:
        positional_error = str(exc)
        positional = []

    if isinstance(docs.get("map_side"), dict):
        map_side = docs["map_side"]
        story = _normalize_story_chapters(map_side)

    # Use the archived TarkovLab catalog only as a disaster/coverage fallback.
    # We never let it overwrite a current position; it only fills an objective
    # that still has no coordinates when the current positional slice failed.
    if not primary or not positional:
        try:
            raw = _http_json("https://raw.githubusercontent.com/TarkovLab/TarkovData/refs/heads/master/data/quests.json", 18.0)
            legacy = _normalize_tarkovlab(raw)
        except Exception as exc:
            fallback_error = str(exc)
            legacy = []

    if primary:
        merged = _merge_positional_quests(primary, positional, only_when_empty=False) if positional else primary
        if legacy:
            merged = _merge_positional_quests(merged, legacy, only_when_empty=True)
    else:
        merged = legacy

    correction_counts = {"moved": 0, "floors": 0, "hidden": 0}
    if merged and map_side:
        correction_counts = _apply_map_objective_corrections(merged, map_side)

    # Story chapters are separate campaign records, intentionally namespaced so
    # their progress does not collide with trader-task ids in localStorage.
    if story:
        existing_ids = {str(q.get("id")) for q in merged}
        merged.extend(q for q in story if str(q.get("id")) not in existing_ids)

    if not merged:
        with state_lock:
            detail = primary_error or positional_error or fallback_error or "onbekend"
            state["quest_status"] = "offline questcache gebruikt" if quest_catalog else f"questdata niet beschikbaar: {detail}"
        quest_ready.set()
        return

    merged.sort(key=lambda q: ((q.get("trader") or "").lower(), (q.get("name") or "").lower()))
    sources = []
    if primary:
        sources.append("json.tarkov.dev + tarkov-data-overlay")
    elif legacy:
        sources.append("TarkovLab archived fallback")
    if positional:
        sources.append("current objective positions")
    if map_side:
        sources.append("hand-checked map corrections")
    if story:
        sources.append("story campaign pins")
    source = " + ".join(sources) or "local fallback"
    now = time.time()
    stats = _quest_spot_stats(merged)
    payload = {
        "updated": now,
        "source": source,
        "stats": stats,
        "storyCount": len(story),
        "positionCorrections": correction_counts,
        "quests": merged,
    }
    try:
        QUEST_CACHE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    with quest_lock:
        quest_catalog = merged
        quest_index = {str(q.get("id")): q for q in merged if q.get("id")}
    with state_lock:
        state["quest_count"] = len(merged)
        state["quest_updated"] = now
        state["quest_source"] = source
        state["quest_status"] = f"{len(merged)} quests / {stats['spots']} quest-spots geladen"
        state["quest_spot_count"] = stats["spots"]
        state["quest_mapped_objectives"] = stats["mappedObjectives"]
        state["quest_mapped_quests"] = stats["mappedQuests"]
        state["quest_story_count"] = len(story)
        state["quest_position_corrections"] = correction_counts
    quest_ready.set()


def quest_refresh_loop():
    while True:
        time.sleep(6*3600); refresh_quest_data()

def load_rich_cache():
    global rich_maps
    try:
        raw=json.loads(RICH_CACHE.read_text(encoding="utf-8")); rich_maps=raw.get("maps",{}) if isinstance(raw,dict) else {}
        with state_lock:
            state["data_updated"]=raw.get("updated") if isinstance(raw,dict) else None; state["data_status"]="lokale POI-cache geladen" if rich_maps else "POI-cache leeg"
    except Exception: rich_maps={}

def refresh_rich_data():
    global rich_maps
    with state_lock: state["data_status"]="POI-data verversen..."
    try:
        def get(url):
            req=urllib.request.Request(url,headers={"User-Agent":"EFTOfflineTracker/14","Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=15) as r: return json.loads(r.read().decode("utf-8"))
        maps_raw=get("https://json.tarkov.dev/regular/maps")
        fresh=parse_maps_document(maps_raw)
        try: merge_task_document(get("https://json.tarkov.dev/regular/tasks"),fresh)
        except Exception: pass
        if fresh:
            rich_maps=fresh; now=time.time(); RICH_CACHE.write_text(json.dumps({"updated":now,"maps":fresh},ensure_ascii=False),encoding="utf-8")
            with state_lock: state["data_updated"]=now; state["data_status"]="POI-data bijgewerkt"
        else: raise RuntimeError("geen maps in data")
    except Exception as exc:
        with state_lock: state["data_status"]="offline cache gebruikt" if rich_maps else f"POI-data niet beschikbaar: {exc}"

def data_refresh_loop():
    while True:
        refresh_rich_data(); time.sleep(6*3600)

def input_loop():
    global trigger_times
    while True:
        fg=tarkov_foreground()
        with state_lock:
            state["game_foreground"]=fg
            interval=max(.5,float(state["interval"]))
            enabled=bool(state.get("capture_enabled", True))
        if fg and enabled:
            now=time.time()
            try:
                tap_key(); trigger_times.append(now); trigger_times=[t for t in trigger_times if now-t<5]
                with state_lock:
                    state["last_trigger"]=now; ok=state.get("last_success"); state["status"]="LIVE" if ok and now-ok<4 else f"{state['screenshot_key']} gestuurd — wacht op screenshot..."
            except Exception as e:
                with state_lock: state["status"]=f"Inputfout: {e}"
            time.sleep(interval)
        else:
            with state_lock: state["status"]="Capture gepauzeerd" if not enabled else "Gepauzeerd — Tarkov niet actief"
            time.sleep(.15)

def was_ours(mt): return any(0<=mt-t<=2.5 for t in trigger_times)

def latest_image(folder):
    files=[]
    try:
        for pat in ("*.png","*.jpg","*.jpeg","*.bmp"): files.extend(folder.glob(pat))
    except OSError: return None
    return max(files,key=lambda p:p.stat().st_mtime) if files else None

def watch_loop():
    global shot_dir
    seen=None; redetect=0
    while True:
        try:
            if time.time()>=redetect:
                with state_lock: ok=state.get("last_success")
                if not ok: shot_dir=detect_screenshot_dir()
                redetect=time.time()+3
            shot_dir.mkdir(parents=True,exist_ok=True); latest=latest_image(shot_dir)
            with state_lock:
                try: state["files_seen"]=sum(1 for p in shot_dir.iterdir() if p.is_file())
                except Exception: state["files_seen"]=0
            if latest:
                st=latest.stat(); key=(str(latest),st.st_mtime_ns,st.st_size)
                if key!=seen:
                    pose=parse_pose(latest.name)
                    if pose:
                        now=time.time()
                        accepted=accept_and_filter_pose(pose,now)
                        if accepted:
                            with state_lock:
                                state["position"]=accepted; state["bearing"]=pose["bearing"]; state["quaternion"]=pose["quaternion"]
                                state["last_update"]=now; state["last_success"]=now; state["last_file"]=latest.name; state["status"]="LIVE — positie ontvangen"
                            append_recording(accepted,now)
                        if cfg.get("delete_auto_screenshots",True) and was_ours(st.st_mtime):
                            time.sleep(.05)
                            for _ in range(8):
                                try: latest.unlink(missing_ok=True); break
                                except PermissionError: time.sleep(.05)
                                except Exception: break
                    else:
                        with state_lock: state["last_file"]=latest.name; state["status"]="Screenshot gezien, maar geen XYZ in bestandsnaam"
                    seen=key
            with state_lock:
                trig=state.get("last_trigger"); ok=state.get("last_success"); fg=state["game_foreground"]
                if fg and trig and time.time()-trig>2.5 and (not ok or ok<trig-.2): state["status"]=f"Geen XYZ ontvangen. Controleer Screenshot={state['screenshot_key']} en screenshotmap."
        except Exception as e:
            with state_lock: state["status"]=f"Watcherfout: {e}"
        time.sleep(.08)

def public_state():
    with state_lock: s=dict(state)
    data=rich_maps.get(s["map"],{})
    s["map_meta"]=maps_meta.get(s["map"],{}); s["pois"]=data.get("pois",[]); s["extracts"]=data.get("extracts",[])
    sp=s.get("smoothed_position")
    if sp and s.get("last_update"):
        age=max(0.0,min(float(s.get("interval",1.0))*1.35,time.time()-float(s["last_update"])))
        v=s.get("velocity") or {"x":0,"y":0,"z":0}
        s["predicted_position"]={k:float(sp[k])+float(v.get(k,0))*age for k in ("x","y","z")}
        s["prediction_age"]=age
    else:
        s["predicted_position"]=sp or s.get("position"); s["prediction_age"]=0
    
    s["health"]={
        "tracker": True,
        "capture": bool(s.get("capture_enabled")),
        "folder": bool(s.get("screenshot_folder")) and Path(str(s.get("screenshot_folder"))).exists(),
        "xyz": bool(s.get("position")),
        "questData": int(s.get("quest_count") or 0)>0,
        "poiData": bool(data.get("pois") or data.get("extracts")),
        "age": (time.time()-float(s["last_update"])) if s.get("last_update") else None,
    }
    return s

def diagnostics_payload():
    with state_lock: st=dict(state)
    folder=Path(str(st.get("screenshot_folder") or "")) if st.get("screenshot_folder") else None
    return {
        "appName": st.get("app_name"), "version": st.get("app_version"), "pid": os.getpid(), "python": sys.version.split()[0],
        "startedAt": st.get("started_at"), "uptime": time.time()-float(st.get("started_at") or time.time()),
        "serverPort": st.get("server_port"), "captureEnabled": st.get("capture_enabled"),
        "interval": st.get("interval"), "screenshotKey": st.get("screenshot_key"),
        "gameForeground": st.get("game_foreground"), "map": st.get("map"),
        "mapDetection": st.get("map_detection"), "position": st.get("position"),
        "smoothedPosition": st.get("smoothed_position"), "bearing": st.get("bearing"),
        "lastUpdate": st.get("last_update"), "lastFile": st.get("last_file"),
        "screenshotFolder": str(folder) if folder else None, "folderExists": bool(folder and folder.exists()),
        "filesSeen": st.get("files_seen"), "accepted": st.get("accepted_count"), "rejected": st.get("rejected_count"),
        "questCount": st.get("quest_count"), "questStatus": st.get("quest_status"), "questSource": st.get("quest_source"),
        "questSpotCount": st.get("quest_spot_count"), "questMappedQuests": st.get("quest_mapped_quests"),
        "questStoryCount": st.get("quest_story_count"), "questPositionCorrections": st.get("quest_position_corrections"),
        "poiMaps": len(rich_maps), "recording": st.get("recording_id"), "status": st.get("status"),
    }

class H(BaseHTTPRequestHandler):
    def log_message(self,*_): pass
    def json(self,obj,code=200):
        b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Cache-Control","no-store"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def body(self):
        try: return json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))) or b"{}")
        except Exception: return {}
    def do_GET(self):
        parsed=urllib.parse.urlparse(self.path); path_only=parsed.path; q=urllib.parse.parse_qs(parsed.query)
        if path_only=="/api/state": return self.json(public_state())
        if path_only=="/api/diagnostics": return self.json(diagnostics_payload())
        if path_only=="/api/maps": return self.json({"maps":maps_meta})
        if path_only=="/api/poi-index":
            rows=[]
            for mk,data in rich_maps.items():
                seen=set()
                for kind in ("pois","extracts"):
                    for item in (data.get(kind) or []):
                        name=str(item.get("name") or "").strip()
                        try: x=float(item.get("x")); z=float(item.get("z"))
                        except (TypeError,ValueError): continue
                        if not name: continue
                        key=(name.lower(),round(x,2),round(z,2))
                        if key in seen: continue
                        seen.add(key)
                        rows.append({
                            "map":mk,"name":name,"category":item.get("category") or ("extract" if kind=="extracts" else "landmark"),
                            "x":x,"y":item.get("y"),"z":z,"id":item.get("id") or f"{mk}:{kind}:{len(rows)}"
                        })
            return self.json({"pois":rows,"count":len(rows)})
        if path_only=="/api/quests":
            with quest_lock: qs=[_quest_summary(q) for q in quest_catalog]
            with state_lock: meta={"status":state.get("quest_status"),"updated":state.get("quest_updated"),"source":state.get("quest_source"),"count":state.get("quest_count",len(qs)),"spotCount":state.get("quest_spot_count",0),"mappedObjectives":state.get("quest_mapped_objectives",0),"mappedQuests":state.get("quest_mapped_quests",0),"storyCount":state.get("quest_story_count",0),"positionCorrections":state.get("quest_position_corrections",{})}
            return self.json({**meta,"quests":qs})
        if path_only=="/api/quest":
            qid=(q.get("id") or [""])[0]
            with quest_lock: item=quest_index.get(qid)
            return self.json({"quest":item}) if item else self.json({"error":"quest niet gevonden"},404)
        if path_only=="/api/recordings": return self.json({"recordings":recording_files(),"current":recording_id})
        if path_only=="/api/recording":
            rid=(q.get("id") or [""])[0]; rows=read_recording(rid)
            return self.json({"id":rid,"points":rows}) if rows else self.json({"error":"recording niet gevonden"},404)
        if path_only=="/api/heatmap":
            mk=(q.get("map") or [state.get("map")])[0]
            if mk not in maps_meta:return self.json({"error":"onbekende map"},400)
            return self.json({"map":mk,"cells":heatmap_for(mk)})
        if path_only=="/api/pin-reports":
            try:
                rows=json.loads(PIN_REPORTS.read_text(encoding="utf-8") or "[]")
            except Exception:
                rows=[]
            return self.json({"count":len(rows),"reports":rows[-100:]})
        path=path_only
        if path=="/": path="/index.html"
        f=(WEB/path.lstrip("/")).resolve()
        if not str(f).startswith(str(WEB.resolve())) or not f.exists(): self.send_error(404); return
        b=f.read_bytes(); ext=f.suffix.lower(); c={".html":"text/html; charset=utf-8",".js":"application/javascript; charset=utf-8",".css":"text/css; charset=utf-8",".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg",".webp":"image/webp",".json":"application/json; charset=utf-8"}.get(ext,"application/octet-stream")
        self.send_response(200); self.send_header("Content-Type",c); self.send_header("Content-Length",str(len(b))); self.send_header("Cache-Control","public, max-age=3600"); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        global shot_dir
        b=self.body()
        if self.path=="/api/map":
            k=b.get("map")
            if k not in maps_meta: return self.json({"ok":False},400)
            with state_lock: state["map"]=k
            return self.json({"ok":True})
        if self.path=="/api/settings":
            try: iv=max(.5,min(30,float(b.get("interval_seconds",state["interval"]))))
            except Exception: return self.json({"ok":False,"error":"ongeldige interval"},400)
            with state_lock:
                state["interval"]=iv
                if "auto_map_detect" in b: state["auto_map_detect"]=bool(b.get("auto_map_detect"))
                if "capture_enabled" in b: state["capture_enabled"]=bool(b.get("capture_enabled"))
            save_runtime_config(); return self.json({"ok":True,"interval_seconds":iv,"auto_map_detect":state.get("auto_map_detect"),"capture_enabled":state.get("capture_enabled")})
        if self.path=="/api/pin-report":
            # Reports are local-first: save feedback/correction candidates beside the app.
            if not isinstance(b,dict): return self.json({"ok":False,"error":"ongeldige payload"},400)
            def short(v,n=300): return str(v or "").strip()[:n]
            rec={
                "ts":time.time(),"map":short(b.get("map"),80),"pinKey":short(b.get("pinKey"),260),
                "name":short(b.get("name"),220),"category":short(b.get("category"),60),
                "note":short(b.get("note"),1000),"reason":short(b.get("reason"),120),
                "original":b.get("original") if isinstance(b.get("original"),dict) else None,
                "suggested":b.get("suggested") if isinstance(b.get("suggested"),dict) else None,
                "player":b.get("player") if isinstance(b.get("player"),dict) else None,
            }
            try:
                try: rows=json.loads(PIN_REPORTS.read_text(encoding="utf-8") or "[]")
                except Exception: rows=[]
                if not isinstance(rows,list): rows=[]
                rows.append(rec)
                # Keep the local file bounded while retaining enough history for review.
                PIN_REPORTS.write_text(json.dumps(rows[-2000:],ensure_ascii=False,indent=2),encoding="utf-8")
                return self.json({"ok":True,"stored":len(rows[-2000:])})
            except Exception as e:
                return self.json({"ok":False,"error":str(e)},500)
        if self.path=="/api/redetect-folder": shot_dir=detect_screenshot_dir(); return self.json({"ok":True,"folder":str(shot_dir)})
        if self.path=="/api/refresh-data": threading.Thread(target=refresh_rich_data,daemon=True).start(); return self.json({"ok":True})
        if self.path=="/api/refresh-quests": threading.Thread(target=refresh_quest_data,daemon=True).start(); return self.json({"ok":True})
        if self.path=="/api/update-all":
            threading.Thread(target=refresh_rich_data,daemon=True).start(); threading.Thread(target=refresh_quest_data,daemon=True).start(); return self.json({"ok":True})
        self.send_error(404)

def main():
    if not acquire_single_instance():
        print("Tarkov Compass draait al. Sluit de bestaande instantie eerst.")
        return
    save_pid(); load_rich_cache(); load_quest_cache()
    threading.Thread(target=input_loop,daemon=True).start(); threading.Thread(target=watch_loop,daemon=True).start(); threading.Thread(target=data_refresh_loop,daemon=True).start()
    with quest_lock: have_quests=bool(quest_catalog)
    threading.Thread(target=refresh_quest_data,daemon=True).start()
    threading.Thread(target=quest_refresh_loop,daemon=True).start()
    host=cfg.get("host","127.0.0.1"); preferred=int(cfg.get("port",8765)); srv=None; port=None
    for candidate in range(preferred, preferred+20):
        try:
            srv=ThreadingHTTPServer((host,candidate),H); port=candidate; break
        except OSError:
            continue
    if srv is None:
        raise RuntimeError("Geen vrije lokale poort gevonden (8765-8784)")
    with state_lock: state["server_port"]=port
    url=f"http://{host}:{port}/"
    if cfg.get("open_browser",True): threading.Timer(.35,lambda:webbrowser.open(url)).start()
    try: srv.serve_forever()
    finally:
        try: PIDFILE.unlink(missing_ok=True)
        except Exception: pass

if __name__=="__main__": main()
