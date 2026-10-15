"""Dependency-free local web editor for controller profiles."""

from __future__ import annotations

import base64
import binascii
import json
import secrets
import threading
import webbrowser
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .boot_logo import (
    BootLogoError,
    boot_logo_path,
    prepare_boot_logo,
    save_boot_logo,
)
from .profile_overrides import (
    load_profiles,
    profiles_document,
    profiles_path,
    reset_profiles,
    save_profiles,
)
from .profiles import ALL_PROFILES
from .settings import SettingsError


EDITOR_HTML = r"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SOOMFON Profil-Editor</title><style>
:root{color-scheme:dark;font-family:Segoe UI,Arial,sans-serif;background:#10151c;color:#eef4f7}*{box-sizing:border-box}
body{max-width:1120px;margin:auto;padding:24px}h1{margin:0 0 6px}.sub{color:#93a3ae;margin:0 0 22px}
.bar,.meta,.actions{display:flex;gap:12px;align-items:end;flex-wrap:wrap;margin:14px 0}.bar select{min-width:220px}
label{display:grid;gap:5px;color:#b9c7cf;font-size:13px}input,select,button{border:1px solid #344452;border-radius:7px;background:#19232d;color:#fff;padding:9px 11px}
button{cursor:pointer;background:#263745}button.primary{background:#27a967;border-color:#38cb80}button.danger{background:#74303a}.grow{flex:1;min-width:230px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.card{border:1px solid #30404c;border-radius:12px;background:#171f28;padding:14px}
.preview{height:74px;border-radius:9px;display:grid;place-items:center;font-weight:700;font-size:18px;text-shadow:0 1px 2px #000;margin-bottom:12px}
.card label{margin-top:9px}.card input,.card select{width:100%}.status{min-height:22px;color:#6fe09d}.error{color:#ff8d91}
.boot{margin-top:24px;border:1px solid #30404c;border-radius:12px;background:#171f28;padding:16px}.boot h2{margin:0 0 5px}.bootrow{display:flex;gap:18px;align-items:center;flex-wrap:wrap}
.bootpreview{width:320px;max-width:100%;aspect-ratio:4/3;object-fit:cover;background:#090d11;border:1px solid #344452;border-radius:9px}.bootcontrols{display:grid;gap:11px;min-width:260px;flex:1}.hint{color:#93a3ae;font-size:13px;margin:0}
@media(max-width:760px){.grid{grid-template-columns:1fr}}
</style></head><body>
<h1>SOOMFON Profil-Editor</h1><p class="sub">Profile und die sechs LCD-Tasten bearbeiten. Speichern aktualisiert den laufenden Controller.</p>
<div class="bar"><label>Profil<select id="profiles"></select></label><button id="add">Neues Profil</button><button id="remove" class="danger">Profil löschen</button></div>
<div class="meta"><label class="grow">Profilname<input id="profileName" maxlength="40"></label><label class="grow">Prozesse, mit Komma getrennt<input id="processes" placeholder="app.exe, app2.exe"></label><label>Reihenfolge<input id="order" type="number" min="0" max="9999"></label></div>
<div id="buttons" class="grid"></div>
<section class="boot"><h2>Bootlogo</h2><p class="hint">Wird direkt nach dem Einschalten angezeigt und dauerhaft im Controller gespeichert.</p><div class="bootrow"><img id="bootPreview" class="bootpreview" alt="Bootlogo-Vorschau"><div class="bootcontrols"><label>Bild auswÃ¤hlen<input id="bootFile" type="file" accept="image/png,image/jpeg,image/webp,image/bmp"></label><p class="hint">Das Bild wird mittig auf 320 Ã— 240 zugeschnitten. Metadaten werden entfernt.</p><button id="writeBoot" class="danger" disabled>Dauerhaft auf Controller schreiben</button><span id="bootStatus" class="status"></span></div></div></section>
<div class="actions"><button id="save" class="primary">Speichern & anwenden</button><button id="reset">Werkseinstellungen wiederherstellen</button><span id="status" class="status"></span></div>
<script>
const token=new URLSearchParams(location.search).get('token');let doc,current=0,bootData=null,bootPending=false;
const types=['none','key','hotkey','open','launch','internal'];
function actionValue(a){if(!a)return '';if(a.type==='key')return a.key||'';if(a.type==='hotkey')return (a.keys||[]).join('+');if(a.type==='open')return a.target||'';if(a.type==='launch')return Array.isArray(a.command)?a.command.join(' | '):a.command||'';return a.name||''}
function makeAction(type,value){value=value.trim();if(type==='none')return null;if(type==='key')return {type,key:value};if(type==='hotkey')return {type,keys:value.split('+').map(x=>x.trim()).filter(Boolean)};if(type==='open')return {type,target:value};if(type==='launch')return {type,command:value.split('|').map(x=>x.trim()).filter(Boolean)};return {type,name:value}}
function store(){if(!doc)return;const p=doc.profiles[current];p.name=profileName.value.trim();p.processes=processes.value.split(',').map(x=>x.trim()).filter(Boolean);p.order=Number(order.value);document.querySelectorAll('.card').forEach((card,i)=>{p.buttons[i]={label:card.querySelector('.label').value.trim(),color:card.querySelector('.color').value,action:makeAction(card.querySelector('.type').value,card.querySelector('.value').value)}})}
function render(){const p=doc.profiles[current];profiles.innerHTML=doc.profiles.map((x,i)=>`<option value="${i}" ${i===current?'selected':''}>${escapeHtml(x.name)}</option>`).join('');profileName.value=p.name;processes.value=p.processes.join(', ');order.value=p.order;buttons.innerHTML=p.buttons.map((b,i)=>`<section class="card"><div class="preview" style="background:${b.color}">${escapeHtml(b.label)}</div><label>Beschriftung<input class="label" maxlength="12" value="${escapeAttr(b.label)}"></label><label>Farbe<input class="color" type="color" value="${b.color}"></label><label>Aktion<select class="type">${types.map(t=>`<option ${t===(b.action?.type||'none')?'selected':''}>${t}</option>`).join('')}</select></label><label>Wert<input class="value" value="${escapeAttr(actionValue(b.action))}" placeholder="z.B. ctrl+shift+p"></label></section>`).join('');document.querySelectorAll('.card').forEach(c=>{const update=()=>{c.querySelector('.preview').textContent=c.querySelector('.label').value;c.querySelector('.preview').style.background=c.querySelector('.color').value};c.querySelector('.label').oninput=update;c.querySelector('.color').oninput=update})}
function escapeHtml(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML}function escapeAttr(s){return escapeHtml(String(s)).replaceAll('"','&quot;')}
profiles.onchange=()=>{store();current=Number(profiles.value);render()};add.onclick=()=>{store();doc.profiles.push({name:'Neues Profil',processes:['programm.exe'],order:100,buttons:Array.from({length:6},(_,i)=>({label:`KEY${i+1}`,color:'#345A78',action:null}))});current=doc.profiles.length-1;render()};remove.onclick=()=>{if(doc.profiles.length<=1)return;doc.profiles.splice(current,1);current=Math.max(0,current-1);render()};
save.onclick=async()=>{store();await send('/api/profiles',doc,'Gespeichert und angewendet.')};reset.onclick=async()=>{if(!confirm('Alle Editor-Anpassungen verwerfen?'))return;const r=await fetch('/api/reset?token='+encodeURIComponent(token),{method:'POST'});const x=await r.json();if(!r.ok)return show(x.error,true);doc=x;current=0;render();show('Werkseinstellungen wiederhergestellt.')};
async function send(url,data,msg){const r=await fetch(url+'?token='+encodeURIComponent(token),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const x=await r.json();if(!r.ok)return show(x.error||'Fehler',true);doc=x;current=Math.min(current,doc.profiles.length-1);render();show(msg)}function show(text,error=false){status.textContent=text;status.className=error?'status error':'status'}
bootFile.onchange=()=>{const file=bootFile.files[0];if(!file)return;if(file.size>8*1024*1024){showBoot('Das Bild darf hÃ¶chstens 8 MB groÃŸ sein.',true);return}const reader=new FileReader();reader.onload=()=>{bootData=reader.result;bootPreview.src=bootData;writeBoot.disabled=false;showBoot('Vorschau bereit â€“ noch nicht auf das GerÃ¤t geschrieben.')};reader.onerror=()=>showBoot('Bild konnte nicht gelesen werden.',true);reader.readAsDataURL(file)};
writeBoot.onclick=async()=>{if(!bootData||bootPending)return;if(!confirm('Das vorhandene Startbild im Controller dauerhaft Ã¼berschreiben?'))return;bootPending=true;writeBoot.disabled=true;showBoot('Bild wird vorbereitet ...');try{const r=await fetch('/api/boot-logo?token='+encodeURIComponent(token),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:bootData})});const x=await r.json();if(!r.ok)throw new Error(x.error||'Fehler');bootPreview.src=x.image;bootData=null;showBoot(x.status||'Schreibauftrag gesendet.');pollBootStatus()}catch(e){showBoot(e.message||String(e),true)}finally{bootPending=false;writeBoot.disabled=!bootData}};
function showBoot(text,error=false){bootStatus.textContent=text||'';bootStatus.className=error?'status error':'status'}
async function loadBootLogo(){try{const r=await fetch('/api/boot-logo?token='+encodeURIComponent(token));const x=await r.json();if(x.image)bootPreview.src=x.image;showBoot(x.status||'Noch kein eigenes Bootlogo gespeichert.')}catch(e){showBoot(e.message||String(e),true)}}
async function pollBootStatus(){let previous='';for(let i=0;i<20;i++){await new Promise(resolve=>setTimeout(resolve,500));try{const r=await fetch('/api/boot-logo?token='+encodeURIComponent(token));const x=await r.json();if(x.status){showBoot(x.status,x.status.includes('Fehler'));if(x.status!==previous&&(/gespeichert|Fehler/.test(x.status)))return;previous=x.status}}catch{return}}}
fetch('/api/profiles?token='+encodeURIComponent(token)).then(r=>r.json()).then(x=>{doc=x;render()}).catch(e=>show(e,true));
loadBootLogo();
</script></body></html>"""


class ProfileEditorServer:
    def __init__(
        self,
        config_path: Path,
        on_save: Callable[[], None],
        *,
        on_boot_logo: Callable[[bytes], None] | None = None,
        status_provider: Callable[[], str | None] | None = None,
    ) -> None:
        self.config_path = config_path
        self.on_save = on_save
        self.on_boot_logo = on_boot_logo
        self.status_provider = status_provider or (lambda: None)
        self.token = secrets.token_urlsafe(24)
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> str:
        if self.server is None:
            editor = self

            class Handler(BaseHTTPRequestHandler):
                def log_message(self, _format: str, *_args: object) -> None:
                    return

                def _authorized(self) -> bool:
                    return parse_qs(urlparse(self.path).query).get("token", [""])[0] == editor.token

                def _json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
                    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(body)

                def do_GET(self) -> None:  # noqa: N802
                    parsed = urlparse(self.path)
                    if not self._authorized():
                        self._json({"error": "Nicht autorisiert"}, HTTPStatus.FORBIDDEN)
                        return
                    if parsed.path == "/api/profiles":
                        profiles = load_profiles(editor.config_path, ALL_PROFILES)
                        self._json(profiles_document(profiles))
                        return
                    if parsed.path == "/api/boot-logo":
                        path = boot_logo_path(editor.config_path)
                        image = None
                        if path.is_file():
                            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
                            image = f"data:image/jpeg;base64,{encoded}"
                        self._json(
                            {"image": image, "status": editor.status_provider()}
                        )
                        return
                    if parsed.path != "/":
                        self.send_error(HTTPStatus.NOT_FOUND)
                        return
                    body = EDITOR_HTML.encode("utf-8")
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header(
                        "Content-Security-Policy",
                        "default-src 'self'; img-src 'self' data:; "
                        "style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'",
                    )
                    self.end_headers()
                    self.wfile.write(body)

                def do_POST(self) -> None:  # noqa: N802
                    parsed = urlparse(self.path)
                    if not self._authorized():
                        self._json({"error": "Nicht autorisiert"}, HTTPStatus.FORBIDDEN)
                        return
                    try:
                        if parsed.path == "/api/reset":
                            reset_profiles(editor.config_path)
                            profiles = ALL_PROFILES
                        elif parsed.path == "/api/profiles":
                            length = int(self.headers.get("Content-Length", "0"))
                            if length <= 0 or length > 1_000_000:
                                raise SettingsError("Ungueltige Datengroesse")
                            document = json.loads(self.rfile.read(length).decode("utf-8"))
                            profiles = save_profiles(editor.config_path, document, ALL_PROFILES)
                        elif parsed.path == "/api/boot-logo":
                            if editor.on_boot_logo is None:
                                raise SettingsError("Bootlogo-Funktion ist nicht verfuegbar")
                            length = int(self.headers.get("Content-Length", "0"))
                            if length <= 0 or length > 12_000_000:
                                raise SettingsError("Ungueltige Datengroesse")
                            document = json.loads(self.rfile.read(length).decode("utf-8"))
                            image_value = document.get("image") if isinstance(document, dict) else None
                            if not isinstance(image_value, str) or "," not in image_value:
                                raise SettingsError("Bilddaten fehlen")
                            header, encoded = image_value.split(",", 1)
                            if not header.startswith("data:image/") or ";base64" not in header:
                                raise SettingsError("Ungueltiges Bildformat")
                            try:
                                source = base64.b64decode(encoded, validate=True)
                            except (ValueError, binascii.Error) as exc:
                                raise SettingsError("Ungueltige Bilddaten") from exc
                            preview, transport = prepare_boot_logo(source)
                            save_boot_logo(editor.config_path, preview)
                            editor.on_boot_logo(transport)
                            image = "data:image/jpeg;base64," + base64.b64encode(preview).decode("ascii")
                            self._json({"image": image, "status": "Schreibauftrag an Controller gesendet."})
                            return
                        else:
                            self.send_error(HTTPStatus.NOT_FOUND)
                            return
                        editor.on_save()
                        self._json(profiles_document(profiles))
                    except (BootLogoError, json.JSONDecodeError, UnicodeDecodeError, OSError, SettingsError, ValueError) as exc:
                        self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

            self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            self.server.daemon_threads = True
            self.thread = threading.Thread(target=self.server.serve_forever, name="profile-editor", daemon=True)
            self.thread.start()
        assert self.server is not None
        return f"http://127.0.0.1:{self.server.server_port}/?token={self.token}"

    def open(self) -> str:
        url = self.start()
        webbrowser.open(url)
        return url

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread is not None:
            self.thread.join(timeout=1.0)
            self.thread = None
