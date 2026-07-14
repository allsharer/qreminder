#!/usr/bin/env python3
"""Local web server providing a browser UI for qremind."""

import os
import sys
import json
import signal
import time
import http.server
import threading
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

# ── Config (mirrors qremind) ──────────────────────────────────────────────────

CONFIG_DIR  = Path.home() / ".config" / "qreminder"
CONFIG_FILE = CONFIG_DIR / "config.json"
DATA_DIR    = Path.home() / ".local" / "share" / "qreminder"

DEFAULT_CONFIG = {
    "data_file":        str(DATA_DIR / "reminders.dat"),
    "hidden_file":      str(DATA_DIR / "hidden.txt"),
    "snooze_file":      str(DATA_DIR / "snoozed.json"),
    "snooze_intervals": "30m,1h,2h,3h,6h,12h,24h",
}

def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text()))
        except Exception:
            pass
    return cfg

# ── Data helpers ──────────────────────────────────────────────────────────────

def load_reminders(data_file):
    path = Path(data_file)
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            parts = line.split(";", 3)
            if len(parts) == 4:
                out.append(parts)
    return out

def save_reminders(data_file, reminders):
    content = "\n".join(";".join(r) for r in reminders)
    Path(data_file).write_text(content + "\n" if content else "")

def load_hidden(hidden_file):
    path = Path(hidden_file)
    if not path.exists():
        return set()
    return {l.strip() for l in path.read_text().splitlines() if l.strip()}

def save_hidden(hidden_file, hidden):
    Path(hidden_file).parent.mkdir(parents=True, exist_ok=True)
    ids = sorted(hidden, key=lambda x: int(x) if x.isdigit() else 0)
    Path(hidden_file).write_text("\n".join(ids) + "\n" if ids else "")

def load_snoozed(snooze_file):
    path = Path(snooze_file)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def save_snoozed(snooze_file, snoozed):
    Path(snooze_file).parent.mkdir(parents=True, exist_ok=True)
    Path(snooze_file).write_text(json.dumps(snoozed, indent=2) + "\n")

def next_refno(reminders):
    return "1" if not reminders else str(max(int(r[0]) for r in reminders) + 1)

def fmt_date(dt_str):
    dt = datetime.strptime(dt_str, "%Y%m%d%H%M")
    if dt_str[8:] == "0000":
        return dt.strftime("%b %d, %Y")
    return dt.strftime("%b %d, %Y %-I:%M %p")

def parse_snooze_intervals(s):
    out = []
    for part in s.split(","):
        part = part.strip()
        if part.endswith("h"):
            h = int(part[:-1])
            out.append({"label": f"{h} hour{'s' if h != 1 else ''}", "minutes": h * 60})
        elif part.endswith("m"):
            m = int(part[:-1])
            out.append({"label": f"{m} minute{'s' if m != 1 else ''}", "minutes": m})
    return out

# ── HTML ──────────────────────────────────────────────────────────────────────

def build_html(snooze_opts_js):
    return """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>qremind</title>
<style>
:root{
  --bg:#f0f2f5;--sf:#fff;--bd:#e0e3e8;
  --tx:#1a1a2e;--mt:#6b7280;
  --due:#ef4444;--up:#3b82f6;--hd:#9ca3af;--snz:#f59e0b;
  --pr:#3b82f6;--prh:#2563eb;--dr:#ef4444;--drh:#dc2626;
  --rd:8px;--sh:0 1px 3px rgba(0,0,0,.1);
}
@media(prefers-color-scheme:dark){:root{
  --bg:#0f0f13;--sf:#1a1a24;--bd:#2d2d3d;
  --tx:#e2e8f0;--mt:#9ca3af;--sh:0 1px 3px rgba(0,0,0,.4);
}}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--tx);min-height:100vh}
header{background:var(--sf);border-bottom:1px solid var(--bd);padding:0 24px;height:56px;
  display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:10;box-shadow:var(--sh)}
.logo{font-size:1.2rem;font-weight:700;letter-spacing:-.5px}
.logo em{color:var(--pr);font-style:normal}
.filters{display:flex;gap:8px;padding:16px 24px 0;flex-wrap:wrap}
.fb{padding:6px 14px;border-radius:20px;border:1px solid var(--bd);background:var(--sf);
  color:var(--mt);cursor:pointer;font-size:.875rem;transition:all .15s}
.fb:hover{border-color:var(--pr);color:var(--pr)}
.fb.on{background:var(--pr);color:#fff;border-color:var(--pr)}
.bdg{display:inline-block;border-radius:10px;padding:0 6px;font-size:.75rem;
  margin-left:4px;background:var(--bd);color:var(--mt)}
.fb.on .bdg{background:rgba(255,255,255,.25);color:#fff}
main{padding:16px 24px 40px;max-width:800px;margin:0 auto}
.card{background:var(--sf);border:1px solid var(--bd);border-radius:var(--rd);
  padding:16px;margin-bottom:12px;box-shadow:var(--sh)}
.ch{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px}
.cdate{font-size:.85rem;color:var(--mt)}
.sb{font-size:.72rem;font-weight:600;padding:2px 8px;border-radius:12px;
  text-transform:uppercase;letter-spacing:.5px;white-space:nowrap}
.s-due{background:#fee2e2;color:var(--due)}
.s-upcoming{background:#dbeafe;color:#1d4ed8}
.s-hidden{background:#f3f4f6;color:var(--hd)}
.s-snoozed{background:#fef3c7;color:#92400e}
@media(prefers-color-scheme:dark){
  .s-due{background:#450a0a;color:#fca5a5}
  .s-upcoming{background:#1e3a5f;color:#93c5fd}
  .s-hidden{background:#1f2937;color:#9ca3af}
  .s-snoozed{background:#451a03;color:#fcd34d}
}
.ctopic{font-size:1rem;font-weight:600;margin-bottom:4px}
.cdesc{font-size:.875rem;color:var(--mt);margin-bottom:10px;white-space:pre-wrap}
.cdesc:empty{display:none}
.csnz{font-size:.8rem;color:var(--snz);margin-bottom:8px}
.cacts{display:flex;gap:6px;justify-content:flex-end;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;padding:5px 12px;border-radius:6px;
  border:1px solid var(--bd);background:var(--sf);color:var(--tx);
  cursor:pointer;font-size:.8rem;font-weight:500;transition:all .15s}
.btn:hover{background:var(--bd)}
.btn-p{background:var(--pr);color:#fff;border-color:var(--pr)}
.btn-p:hover{background:var(--prh);border-color:var(--prh)}
.btn-d{color:var(--dr);border-color:var(--dr)}
.btn-d:hover{background:var(--dr);color:#fff}
.empty{text-align:center;padding:48px 0;color:var(--mt)}
.ei{font-size:2.5rem;margin-bottom:12px}
.ov{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);
  z-index:100;align-items:center;justify-content:center}
.ov.open{display:flex}
.modal{background:var(--sf);border-radius:var(--rd);padding:24px;width:100%;
  max-width:520px;max-height:90vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,.3)}
.modal h2{margin-bottom:18px;font-size:1.1rem}
.fld{margin-bottom:14px}
.fld label{display:block;font-size:.85rem;font-weight:500;margin-bottom:5px;color:var(--mt)}
.fld input,.fld textarea{width:100%;padding:8px 12px;border:1px solid var(--bd);
  border-radius:6px;background:var(--bg);color:var(--tx);font-size:.9rem;font-family:inherit}
.fld textarea{min-height:72px;resize:vertical}
.fld input:focus,.fld textarea:focus{outline:none;border-color:var(--pr);
  box-shadow:0 0 0 3px rgba(59,130,246,.15)}
.prow{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:7px}
.pb{padding:3px 9px;border-radius:14px;border:1px solid var(--bd);background:var(--bg);
  color:var(--mt);cursor:pointer;font-size:.78rem;transition:all .15s}
.pb:hover,.pb.on{background:var(--pr);color:#fff;border-color:var(--pr)}
.trow{display:flex;gap:8px;align-items:center}
.trow input{flex:1}
.macts{display:flex;gap:10px;justify-content:flex-end;margin-top:18px}
</style>
</head>
<body>
<header>
  <div class="logo">q<em>remind</em></div>
  <button class="btn btn-p" onclick="openAdd()">+ Add Reminder</button>
</header>
<div class="filters" id="fbar"></div>
<main id="main"></main>

<div class="ov" id="editOv">
<div class="modal">
  <h2 id="mttl">Add Reminder</h2>
  <div class="fld">
    <label>Date</label>
    <div class="prow" id="dpreset"></div>
    <input type="date" id="din" required>
  </div>
  <div class="fld">
    <label>Time <span style="font-weight:400;font-size:.78rem">(optional)</span></label>
    <div class="prow" id="tpreset"></div>
    <div class="trow">
      <input type="time" id="tin">
      <button class="btn" type="button" onclick="clearT()">Clear</button>
    </div>
  </div>
  <div class="fld">
    <label>Topic *</label>
    <input type="text" id="topin" placeholder="Required">
  </div>
  <div class="fld">
    <label>Description</label>
    <textarea id="descin" placeholder="Optional"></textarea>
  </div>
  <div class="macts">
    <button class="btn" onclick="closeEdit()">Cancel</button>
    <button class="btn btn-p" onclick="saveR()">Save</button>
  </div>
</div>
</div>

<div class="ov" id="snzOv">
<div class="modal" style="max-width:400px">
  <h2>Snooze</h2>
  <p style="font-size:.875rem;color:var(--mt);margin-bottom:14px" id="snztopic"></p>
  <div id="snzopts"></div>
  <div class="macts"><button class="btn" onclick="closeSnz()">Cancel</button></div>
</div>
</div>

<script>
const SNZ="""  + snooze_opts_js + """;
let all=[],cur='all',eref=null,sref=null;

async function load(){
  all=await fetch('/api/reminders').then(r=>r.json());
  renderF();renderL();
}

function cnt(){
  const n=new Date(),m=n.getMonth(),y=n.getFullYear();
  return{
    all:all.length,
    due:all.filter(r=>r.status==='due').length,
    month:all.filter(r=>{if(r.status==='hidden')return false;const d=pdt(r.dt_str);return d.getFullYear()===y&&d.getMonth()===m;}).length,
    upcoming:all.filter(r=>r.status==='upcoming').length,
    hidden:all.filter(r=>r.status==='hidden').length,
  };
}

function renderF(){
  const c=cnt();
  const fs=[{k:'all',l:'All'},{k:'due',l:'Due'},{k:'month',l:'This Month'},{k:'upcoming',l:'Upcoming'},{k:'hidden',l:'Hidden'}];
  document.getElementById('fbar').innerHTML=fs.map(f=>`<button class="fb${f.k===cur?' on':''}" onclick="sf('${f.k}')">${f.l}<span class="bdg">${c[f.k]}</span></button>`).join('');
}

function filt(){
  const n=new Date(),m=n.getMonth(),y=n.getFullYear();
  return all.filter(r=>{
    if(cur==='all')return true;
    if(cur==='due')return r.status==='due';
    if(cur==='upcoming')return r.status==='upcoming';
    if(cur==='hidden')return r.status==='hidden';
    if(cur==='month'){if(r.status==='hidden')return false;const d=pdt(r.dt_str);return d.getFullYear()===y&&d.getMonth()===m;}
  });
}

function renderL(){
  const lst=filt(),el=document.getElementById('main');
  if(!lst.length){el.innerHTML='<div class="empty"><div class="ei">🔔</div>No reminders here.</div>';return;}
  el.innerHTML=lst.map(r=>{
    const snzR=r.snooze_until?`<div class="csnz">⏰ Snoozed until ${r.snooze_until}</div>`:'';
    const hideB=r.status==='hidden'
      ?`<button class="btn" onclick="unhide('${r.refno}')">Unhide</button>`
      :`<button class="btn" onclick="hide('${r.refno}')">Hide</button>`;
    const snzB=r.status!=='hidden'?`<button class="btn" onclick="openSnz('${r.refno}','${xe(r.topic)}')">Snooze</button>`:'';
    const unsnzB=r.snooze_until?`<button class="btn" onclick="unsnz('${r.refno}')">Unsnooze</button>`:'';
    return`<div class="card"><div class="ch"><span class="cdate">${r.formatted_date}</span><span class="sb s-${r.status}">${r.status}</span></div><div class="ctopic">${xe(r.topic)}</div><div class="cdesc">${xe(r.desc)}</div>${snzR}<div class="cacts"><button class="btn" onclick="openEdit('${r.refno}')">Edit</button>${hideB}${snzB}${unsnzB}<button class="btn btn-d" onclick="del('${r.refno}')">Delete</button></div></div>`;
  }).join('');
}

function sf(f){cur=f;renderF();renderL();}
function xe(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function pdt(s){return new Date(s.slice(0,4),+s.slice(4,6)-1,s.slice(6,8),s.slice(8,10),s.slice(10,12));}
function todt(d,t){return d.replace(/-/g,'')+(t?t.replace(':',''):'0000');}
function frdt(s){return{d:s.slice(0,4)+'-'+s.slice(4,6)+'-'+s.slice(6,8),t:s.slice(8)==='0000'?'':s.slice(8,10)+':'+s.slice(10,12)};}
function addD(n){const d=new Date();d.setDate(d.getDate()+n);return d.toISOString().slice(0,10);}
function addM(n){const d=new Date();d.setMonth(d.getMonth()+n);return d.toISOString().slice(0,10);}
function addY(n){const d=new Date();d.setFullYear(d.getFullYear()+n);return d.toISOString().slice(0,10);}

const DP=[{l:'Today',f:()=>addD(0)},{l:'+1 day',f:()=>addD(1)},{l:'+3 days',f:()=>addD(3)},{l:'+1 week',f:()=>addD(7)},{l:'+2 weeks',f:()=>addD(14)},{l:'+1 month',f:()=>addM(1)},{l:'+3 months',f:()=>addM(3)},{l:'+6 months',f:()=>addM(6)},{l:'+1 year',f:()=>addY(1)}];
const TP=[{l:'Morning',t:'09:00'},{l:'Noon',t:'12:00'},{l:'Afternoon',t:'14:00'},{l:'Evening',t:'18:00'},{l:'Night',t:'21:00'}];

function buildP(){
  document.getElementById('dpreset').innerHTML=DP.map((p,i)=>`<button class="pb" type="button" onclick="sdp(${i},this)">${p.l}</button>`).join('');
  document.getElementById('tpreset').innerHTML=TP.map(p=>`<button class="pb" type="button" onclick="stp('${p.t}',this)">${p.l}</button>`).join('');
}
function sdp(i,b){document.getElementById('din').value=DP[i].f();document.querySelectorAll('#dpreset .pb').forEach(x=>x.classList.remove('on'));b.classList.add('on');}
function stp(t,b){document.getElementById('tin').value=t;document.querySelectorAll('#tpreset .pb').forEach(x=>x.classList.remove('on'));b.classList.add('on');}
function clearT(){document.getElementById('tin').value='';document.querySelectorAll('#tpreset .pb').forEach(x=>x.classList.remove('on'));}

function openAdd(){
  eref=null;
  document.getElementById('mttl').textContent='Add Reminder';
  ['din','tin','topin','descin'].forEach(id=>document.getElementById(id).value='');
  document.querySelectorAll('.pb').forEach(b=>b.classList.remove('on'));
  document.getElementById('editOv').classList.add('open');
  setTimeout(()=>document.getElementById('topin').focus(),50);
}
function openEdit(ref){
  const r=all.find(x=>x.refno===ref);if(!r)return;
  eref=ref;
  document.getElementById('mttl').textContent='Edit Reminder';
  const{d,t}=frdt(r.dt_str);
  document.getElementById('din').value=d;
  document.getElementById('tin').value=t;
  document.getElementById('topin').value=r.topic;
  document.getElementById('descin').value=r.desc;
  document.querySelectorAll('.pb').forEach(b=>b.classList.remove('on'));
  document.getElementById('editOv').classList.add('open');
}
function closeEdit(){document.getElementById('editOv').classList.remove('open');}

async function saveR(){
  const topic=document.getElementById('topin').value.trim();
  if(!topic){document.getElementById('topin').focus();return;}
  const dv=document.getElementById('din').value;
  if(!dv){document.getElementById('din').focus();return;}
  const dt_str=todt(dv,document.getElementById('tin').value);
  const desc=document.getElementById('descin').value.trim();
  const body=JSON.stringify({dt_str,topic,desc});
  const hdrs={'Content-Type':'application/json'};
  if(eref){await fetch('/api/reminders/'+eref,{method:'PUT',headers:hdrs,body});}
  else{await fetch('/api/reminders',{method:'POST',headers:hdrs,body});}
  closeEdit();await load();
}

async function hide(ref){await fetch('/api/reminders/'+ref+'/hide',{method:'POST'});await load();}
async function unhide(ref){await fetch('/api/reminders/'+ref+'/unhide',{method:'POST'});await load();}
async function del(ref){if(!confirm('Delete this reminder?'))return;await fetch('/api/reminders/'+ref,{method:'DELETE'});await load();}
async function unsnz(ref){await fetch('/api/reminders/'+ref+'/snooze',{method:'DELETE'});await load();}

function openSnz(ref,topic){
  sref=ref;
  document.getElementById('snztopic').textContent=decodeURIComponent(topic);
  document.getElementById('snzopts').innerHTML=SNZ.map(o=>`<button class="btn" style="margin-bottom:8px;width:100%;justify-content:center" onclick="applySnz(${o.minutes})">${o.label}</button>`).join('');
  document.getElementById('snzOv').classList.add('open');
}
function closeSnz(){document.getElementById('snzOv').classList.remove('open');}
async function applySnz(mins){
  await fetch('/api/reminders/'+sref+'/snooze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({minutes:mins})});
  closeSnz();await load();
}

document.getElementById('editOv').addEventListener('click',e=>{if(e.target===e.currentTarget)closeEdit();});
document.getElementById('snzOv').addEventListener('click',e=>{if(e.target===e.currentTarget)closeSnz();});
buildP();load();
</script>
<script>setInterval(()=>fetch('/ping',{method:'POST'}),3000);</script>
</body>
</html>"""

# ── HTTP server ───────────────────────────────────────────────────────────────

def run(cfg, port=8765):
    intervals  = parse_snooze_intervals(cfg.get("snooze_intervals", DEFAULT_CONFIG["snooze_intervals"]))
    snooze_js  = json.dumps(intervals)
    html_bytes = build_html(snooze_js).encode()

    # ── Browser watchdog ──────────────────────────────────────────────────────
    _state = {"last_ping": time.time()}
    _PING_TIMEOUT = 10

    def _watchdog():
        time.sleep(5)  # grace period for the browser to load the first page
        while True:
            time.sleep(3)
            if time.time() - _state["last_ping"] > _PING_TIMEOUT:
                print("\nNo browser activity detected — shutting down.", flush=True)
                os.kill(os.getpid(), signal.SIGINT)
                break

    threading.Thread(target=_watchdog, daemon=True).start()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_): pass

        def send_json(self, data, code=200):
            body = json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def read_body(self):
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n)) if n else {}

        def parts(self):
            return [p for p in self.path.rstrip("/").split("/") if p]

        # ── GET ──────────────────────────────────────────────────────────────

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html_bytes)))
                self.end_headers()
                self.wfile.write(html_bytes)
            elif self.path == "/api/reminders":
                reminders = load_reminders(cfg["data_file"])
                hidden    = load_hidden(cfg["hidden_file"])
                snoozed   = load_snoozed(cfg["snooze_file"])
                now       = datetime.now()
                result    = []
                for refno, dt_str, topic, desc in reminders:
                    dt        = datetime.strptime(dt_str, "%Y%m%d%H%M")
                    snz_str   = snoozed.get(refno)
                    snz_dt    = datetime.strptime(snz_str, "%Y%m%d%H%M") if snz_str else None
                    if refno in hidden:
                        status = "hidden"
                    elif snz_dt and snz_dt > now:
                        status = "snoozed"
                    elif dt <= now:
                        status = "due"
                    else:
                        status = "upcoming"
                    result.append({
                        "refno":          refno,
                        "dt_str":         dt_str,
                        "formatted_date": fmt_date(dt_str),
                        "topic":          topic,
                        "desc":           desc,
                        "status":         status,
                        "snooze_until":   fmt_date(snz_str) if snz_str else None,
                    })
                self.send_json(result)
            else:
                self.send_error(404)

        # ── POST ─────────────────────────────────────────────────────────────

        def do_POST(self):
            ps = self.parts()
            if ps == ["ping"]:
                _state["last_ping"] = time.time()
                self.send_response(204)
                self.end_headers()
            elif ps == ["api", "reminders"]:
                data      = self.read_body()
                reminders = load_reminders(cfg["data_file"])
                refno     = next_refno(reminders)
                reminders.append([refno, data["dt_str"], data["topic"], data.get("desc", "")])
                Path(cfg["data_file"]).parent.mkdir(parents=True, exist_ok=True)
                save_reminders(cfg["data_file"], reminders)
                self.send_json({"ok": True, "refno": refno})
            elif len(ps) == 4 and ps[:2] == ["api", "reminders"]:
                refno, action = ps[2], ps[3]
                if action == "hide":
                    h = load_hidden(cfg["hidden_file"]); h.add(refno)
                    save_hidden(cfg["hidden_file"], h); self.send_json({"ok": True})
                elif action == "unhide":
                    h = load_hidden(cfg["hidden_file"]); h.discard(refno)
                    save_hidden(cfg["hidden_file"], h); self.send_json({"ok": True})
                elif action == "snooze":
                    body    = self.read_body()
                    snoozed = load_snoozed(cfg["snooze_file"])
                    until   = datetime.now() + timedelta(minutes=int(body["minutes"]))
                    snoozed[refno] = until.strftime("%Y%m%d%H%M")
                    save_snoozed(cfg["snooze_file"], snoozed)
                    self.send_json({"ok": True})
                else:
                    self.send_error(404)
            else:
                self.send_error(404)

        # ── PUT ──────────────────────────────────────────────────────────────

        def do_PUT(self):
            ps = self.parts()
            if len(ps) == 3 and ps[:2] == ["api", "reminders"]:
                refno     = ps[2]
                data      = self.read_body()
                reminders = load_reminders(cfg["data_file"])
                updated   = [
                    [refno, data.get("dt_str", r[1]), data.get("topic", r[2]), data.get("desc", r[3])]
                    if r[0] == refno else r
                    for r in reminders
                ]
                save_reminders(cfg["data_file"], updated)
                self.send_json({"ok": True})
            else:
                self.send_error(404)

        # ── DELETE ───────────────────────────────────────────────────────────

        def do_DELETE(self):
            ps = self.parts()
            if len(ps) == 3 and ps[:2] == ["api", "reminders"]:
                refno     = ps[2]
                reminders = [r for r in load_reminders(cfg["data_file"]) if r[0] != refno]
                save_reminders(cfg["data_file"], reminders)
                h = load_hidden(cfg["hidden_file"]); h.discard(refno)
                save_hidden(cfg["hidden_file"], h)
                s = load_snoozed(cfg["snooze_file"]); s.pop(refno, None)
                save_snoozed(cfg["snooze_file"], s)
                self.send_json({"ok": True})
            elif len(ps) == 4 and ps[:2] == ["api", "reminders"] and ps[3] == "snooze":
                refno   = ps[2]
                snoozed = load_snoozed(cfg["snooze_file"])
                snoozed.pop(refno, None)
                save_snoozed(cfg["snooze_file"], snoozed)
                self.send_json({"ok": True})
            else:
                self.send_error(404)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url    = f"http://localhost:{port}"
    print(f"qremind web UI → {url}")
    print("Press Ctrl+C to stop.")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    run(load_config(), port)
