#!/usr/bin/env python3
"""
HateFileless v1.1 — Fileless Detection Suite
Splash animado | Header con wave | Contadores animados | Dark UI
"""

import os, sys, re, queue, ctypes, winreg, time as _t
import subprocess, threading, tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime as dt

VERSION = "1.1"

# ═══════════════════════════════════════════════════════════════════
#  FIRMAS — PS / LOLBin / Fileless
# ═══════════════════════════════════════════════════════════════════

PS_SIGNATURES = {
    'AMSI Bypass': {
        'sev': 'CRITICAL',
        'kw': [
            'amsiInitFailed', 'AmsiUtils', 'amsiContext', 'AmsiScanBuffer',
            'amsiSession', 'amsi.dll', 'amsiEnable', 'HookAMSI', 'PatchAMSI',
            'amsiResult', 'AMSI_RESULT_CLEAN',
        ]
    },
    'Assembly Load (Fileless)': {
        'sev': 'CRITICAL',
        'kw': [
            'Reflection.Assembly', '::Load(', 'LoadWithPartialName',
            'Assembly]::Load', 'loadfrom(', 'loadfile(',
            'AssemblyLoadContext', 'UnsafeLoadFrom',
        ]
    },
    'Download GitHub': {
        'sev': 'HIGH',
        'kw': ['raw.githubusercontent.com', 'github.com/', 'gist.github.com']
    },
    'Download Web': {
        'sev': 'HIGH',
        'kw': [
            'DownloadData', 'DownloadString', 'DownloadFile',
            'Net.WebClient', 'Invoke-WebRequest', 'iwr ',
            'WebRequest', 'pastebin.com', 'hastebin.com',
            'ghostbin', 'paste.ee', 'transfer.sh', 'https', 'http', '.py'
        ]
    },
    'Fileless Execution': {
        'sev': 'CRITICAL',
        'kw': [
            'EntryPoint.Invoke', '.Invoke($null', 'GetMethod(',
            'SetApartmentState', '.Invoke(', 'DynamicInvoke',
            'InvokeMethod', 'MethodInfo',
        ]
    },
    'Base64 Payload': {
        'sev': 'MEDIUM',
        'kw': [
            'FromBase64String', 'EncodedCommand', '-enc ',
            'ToBase64String', '-EncodedCommand', '-e ',
        ]
    },
    'LOLBin Abuse': {
        'sev': 'MEDIUM',
        'kw': [
            'mshta', 'rundll32', 'regsvr32', 'certutil',
            'bitsadmin', 'wscript', 'cscript', 'msiexec',
            'InstallUtil', 'regasm', 'odbcconf', 'xwizard',
            'syncappvpublishingserver', 'forfiles', 'pcalua',
        ]
    },
    'Compression / Encoding': {
        'sev': 'MEDIUM',
        'kw': [
            'GZipStream', 'DeflateStream', 'IO.Compression',
            'BinaryFormatter', 'MemoryStream', 'BinaryReader',
        ]
    },
    'Credential Access': {
        'sev': 'HIGH',
        'kw': [
            'ConvertTo-SecureString', 'Get-Credential',
            'sekurlsa', 'mimikatz', 'lsass',
            'Invoke-Mimikatz', 'Get-GPPPassword', 'DumpCreds',
        ]
    },
    'Shellcode / Injection': {
        'sev': 'CRITICAL',
        'kw': [
            'VirtualAlloc', 'WriteProcessMemory', 'CreateRemoteThread',
            'NtCreateThreadEx', 'RtlCreateUserThread', 'QueueUserAPC',
            'shellcode', 'meterpreter', 'cobaltstrike', 'cobalt strike',
            'Process Ghosting', 'Process Hollowing', 'Transacted Hollowing',
            'Process Doppelganging', 'Module Overloading', 'NtCreateSection',
            'NtMapViewOfSection', 'indirect syscall', 'SharpGhosting',
            '[#] Injector fork', '[#] Injection completed',
            'Obligatory PE Injection', 'DLL sideloading',
            'payload injection successful', 'VirtualAllocEx',
        ]
    },
    'Network C2': {
        'sev': 'HIGH',
        'kw': [
            'ngrok', 'serveo.net', 'localhost.run',
            'cloudflared', 'burpcollaborator',
            '/payload', '/shell', '/beacon', '/stager',
        ]
    },
}

# ═══════════════════════════════════════════════════════════════════
#  FIRMAS — Ofuscación
# ═══════════════════════════════════════════════════════════════════
CREATE_NO_WINDOW = 0x08000000
OBFUSCATION = {
    'Tick Escaping':            {'sev': 'HIGH',    're': [r'(?:[a-zA-Z]`){3,}', r'`[iI]`[eE]`[xX]', r'i`[eE][xX]', r'po`wer']},
    'String Concat Obf':        {'sev': 'HIGH',    're': [r"'[a-zA-Z]{1,6}'\s*\+\s*'[a-zA-Z]{1,6}'", r'"[a-zA-Z]{1,6}"\s*\+\s*"[a-zA-Z]{1,6}"']},
    'Char Obfuscation':         {'sev': 'HIGH',    're': [r'\[char\]\s*0x[0-9a-fA-F]{2}', r'\[char\]\s*\d{2,3}', r'String\.fromCharCode\(']},
    'Caret Escaping (CMD)':     {'sev': 'HIGH',    're': [r'[a-zA-Z]\^[a-zA-Z]\^[a-zA-Z]', r'cmd\s*/v.*%\w+:~', r'SET\s+\w+=.*&&.*%\w+:~\d+,\d+%']},
    'Env Variable Abuse':       {'sev': 'MEDIUM',  're': [r'\$env:comspec', r'\$\{env:', r'%comspec%', r'%SystemRoot%\\system32\\cmd']},
    'Reverse String':           {'sev': 'MEDIUM',  're': [r'\-join\s*\(.*\[\s*-1\s*\]\s*\)', r'\[Array\]::Reverse']},
    'SecureString Obf':         {'sev': 'MEDIUM',  're': [r'ConvertTo-SecureString.*-AsPlainText', r'Marshal::SecureStringToBSTR']},
    'Replace Obfuscation':      {'sev': 'HIGH',    're': [r"['\"][A-Za-z0-9+/=_\-]{6,}['\"]\.replace\(", r'\-replace\s+["\'][^"\']+["\'],\s*["\'][^"\']*["\']']},
    'Invoke-Obf Markers':       {'sev': 'CRITICAL','re': [r'cmd\.exe.*\/v:on.*\/c', r'for.*%\w+.*in.*do.*set', r'%\w+:~-?\d+,\d+%']},
    'Suspicious Long Base64':   {'sev': 'MEDIUM',  're': [r'[A-Za-z0-9+/=]{200,}']},
}

OBF_COMPILED: dict = {}
for _n, _c in OBFUSCATION.items():
    OBF_COMPILED[_n] = {
        'sev': _c['sev'],
        'patterns': [re.compile(p, re.IGNORECASE) for p in _c.get('re', [])]
    }

# ═══════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════

SEV_ORDER = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}

def run_ps(cmd: str, timeout: int = 90) -> str:
    try:
        r = subprocess.run(
            ['powershell', '-NonInteractive', '-NoProfile', '-Command', cmd],
            capture_output=True, text=True, timeout=timeout,
            encoding='utf-8', errors='replace', creationflags=CREATE_NO_WINDOW)
        return r.stdout
    except Exception:
        return ''

def check_sigs(text: str) -> list:
    hits, tl = [], text.lower()
    for name, cfg in PS_SIGNATURES.items():
        if any(k.lower() in tl for k in cfg['kw']):
            hits.append((name, cfg['sev']))
    return hits

def check_obf(text: str) -> list:
    hits = []
    for name, cfg in OBF_COMPILED.items():
        if any(rx.search(text) for rx in cfg['patterns']):
            hits.append((name, cfg['sev']))
    return hits

def max_sev(hits: list) -> str:
    return min((h[1] for h in hits), key=lambda s: SEV_ORDER.get(s, 9)) if hits else 'LOW'

def make_finding(source, time_val, hits, content, path='', fileless=False) -> dict:
    return {
        'source': source, 'time': time_val if time_val and time_val.strip() else '(sin timestamp)',
        'severity': max_sev(hits), 'hits': hits, 'fileless': fileless,
        'path': path or source, 'content': content,
        'summary': content[:150].replace('\n', ' '),
    }

# ═══════════════════════════════════════════════════════════════════
#  SCANNERS
# ═══════════════════════════════════════════════════════════════════

def scan_ps4104() -> list:
    cmd = r"""
$evs = Get-WinEvent -LogName 'Microsoft-Windows-PowerShell/Operational' `
    -MaxEvents 1000 -ErrorAction SilentlyContinue | Where-Object { $_.Id -eq 4104 }
foreach ($e in $evs) {
    $x=$[xml]$e.ToXml();$d=$x.Event.EventData.Data
    $txt=($d|Where-Object{$_.Name -eq 'ScriptBlockText'}).'#text'
    $path=($d|Where-Object{$_.Name -eq 'Path'}).'#text'
    $t=$e.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')
    Write-Output "^T:$t^P:$path^B:$txt^END"
}
""".replace('$[xml]', '[xml]')
    raw, findings = run_ps(cmd, 90), []
    for block in raw.split('^END'):
        if '^T:' not in block: continue
        try:
            tv = block.split('^T:')[1].split('^P:')[0].strip()
            pv = block.split('^P:')[1].split('^B:')[0].strip()
            bv = block.split('^B:')[1].strip() if '^B:' in block else ''
        except IndexError: continue
        if not bv: continue
        hits = check_sigs(bv) + check_obf(bv)
        if hits:
            findings.append(make_finding(
                'PS Event 4104', tv, hits, bv,
                path=pv or '<fileless>', fileless=not pv.strip()))
    return findings

def scan_clipboard() -> list:
    CF_UNICODE = 13
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    text = ''
    try:
        if u32.OpenClipboard(0):
            h = u32.GetClipboardData(CF_UNICODE)
            if h:
                p = k32.GlobalLock(h)
                if p:
                    try:    text = ctypes.wstring_at(p)
                    finally: k32.GlobalUnlock(h)
            u32.CloseClipboard()
    except Exception: pass
    if not text or len(text.strip()) < 5: return []
    hits = check_sigs(text) + check_obf(text)
    if not hits: return []
    scan_time = f"Escaneado: {dt.now().strftime('%Y-%m-%d %H:%M:%S')}"
    return [make_finding('Clipboard', scan_time,
                        hits, text, path='<clipboard>', fileless=True)]

def scan_cmd_history() -> list:
    findings = []
    cmd4688 = r"""
$evs=Get-WinEvent -LogName 'Security' -MaxEvents 2000 -ErrorAction SilentlyContinue|
    Where-Object{$_.Id -eq 4688}
foreach($e in $evs){
    $x=[xml]$e.ToXml();$d=@{}
    foreach($i in $x.Event.EventData.Data){$d[$i.Name]=$i.'#text'}
    $proc=$d['NewProcessName'];$cl=$d['CommandLine']
    $t=$e.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')
    if($proc -match 'cmd\.exe|powershell|wscript|cscript|mshta|wmic|regsvr32|rundll32'){
        Write-Output "^T:$t^P:$proc^C:$cl^END"
    }
}
"""
    raw = run_ps(cmd4688, 60)
    for block in raw.split('^END'):
        if '^T:' not in block: continue
        try:
            tv = block.split('^T:')[1].split('^P:')[0].strip()
            pv = block.split('^P:')[1].split('^C:')[0].strip()
            cv = block.split('^C:')[1].strip() if '^C:' in block else ''
        except IndexError: continue
        if not cv: continue
        hits = check_sigs(cv) + check_obf(cv)
        if hits:
            findings.append(make_finding(
                f'Event 4688 ({Path(pv).name})', tv, hits, cv, path=pv))

    ps_hist = (Path(os.environ.get('APPDATA', '')) /
               'Microsoft/Windows/PowerShell/PSReadLine/ConsoleHost_history.txt')
    if ps_hist.exists():
        try:
            for line in ps_hist.read_text(encoding='utf-8', errors='replace').splitlines():
                if not line.strip(): continue
                hits = check_sigs(line) + check_obf(line)
                if hits:
                    findings.append(make_finding(
                        'PS ReadLine History', '', hits, line, path=str(ps_hist)))
        except Exception: pass

    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU')
        idx = 0
        while True:
            try:
                name, val, _ = winreg.EnumValue(k, idx); idx += 1
                if name == 'MRUList': continue
                val = str(val).rstrip('\x01').strip()
                hits = check_sigs(val) + check_obf(val)
                if hits:
                    findings.append(make_finding(
                        'Run MRU (Win+R)', '', hits, val, path='<registry>'))
            except OSError: break
        winreg.CloseKey(k)
    except Exception: pass
    return findings

def scan_ps_events() -> list:
    findings = []
    cmd = r"""
$evs=Get-WinEvent -LogName 'Windows PowerShell' -MaxEvents 1000 `
    -ErrorAction SilentlyContinue|Where-Object{$_.Id -in @(400,600,800)}
foreach($e in $evs){
    $x=[xml]$e.ToXml();$d=@{}
    foreach($i in $x.Event.EventData.Data){$d[$i.Name]=$i.'#text'}
    $t=$e.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss');$id=$e.Id
    $info=switch($id){
        400{"HostApp="+$d['HostApplication']+" | Engine="+$d['EngineVersion']}
        600{"Provider="+$d['ProviderName']+" | State="+$d['NewState']}
        800{"SeqName="+$d['SequencePointName']+" | Cmd="+$d['CommandLine']}
    }
    Write-Output "^ID:$id^T:$t^I:$info^END"
}
"""
    raw = run_ps(cmd, 60)
    labels = {'400': 'PS Engine Start', '600': 'PS Provider', '800': 'PS Pipeline'}
    for block in raw.split('^END'):
        if '^ID:' not in block: continue
        try:
            eid = block.split('^ID:')[1].split('^T:')[0].strip()
            tv  = block.split('^T:')[1].split('^I:')[0].strip()
            iv  = block.split('^I:')[1].strip() if '^I:' in block else ''
        except IndexError: continue
        if not iv: continue
        hits = check_sigs(iv) + check_obf(iv)
        if eid == '400' and ('-enc' in iv.lower() or 'encodedcommand' in iv.lower()):
            hits.append(('Encoded PS Launch (E400)', 'HIGH'))
        if hits:
            findings.append(make_finding(
                f'PS Event {eid} ({labels.get(eid, eid)})', tv, hits, iv,
                path='<Windows PowerShell log>'))

    cmd_ti = r"""
$evs=Get-WinEvent -LogName 'Microsoft-Windows-TextInput/Operational' `
    -MaxEvents 200 -ErrorAction SilentlyContinue
foreach($e in $evs){
    $t=$e.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')
    Write-Output "^T:$t^M:$($e.Message)^END"
}
"""
    raw_ti = run_ps(cmd_ti, 30)
    for block in raw_ti.split('^END'):
        if '^T:' not in block: continue
        try:
            tv = block.split('^T:')[1].split('^M:')[0].strip()
            mv = block.split('^M:')[1].strip() if '^M:' in block else ''
        except IndexError: continue
        if not mv: continue
        hits = check_sigs(mv) + check_obf(mv)
        if hits:
            findings.append(make_finding(
                'TextInputHost', tv, hits, mv,
                path='<TextInput log>', fileless=True))
    return findings

SCANNERS = [
    ('PS ScriptBlock',     scan_ps4104),
    ('Clipboard',                  scan_clipboard),
    ('Historial',    scan_cmd_history),
    ('Procesando Resultados...', scan_ps_events),
]

# ═══════════════════════════════════════════════════════════════════
#  COLORES
# ═══════════════════════════════════════════════════════════════════

BG  = '#0d0d12'
BG2 = '#12121a'
BG3 = '#1a1a26'
BG4 = '#222233'
FG  = '#e0e0f0'
FGD = '#505070'
ACC = '#0088ff'
AC2 = '#00ccff'
RED = '#ff3355'
ORA = '#ff8c00'
YEL = '#ffcc00'
GRN = '#00e676'
BRD = '#2a2a40'

SEV_COL = {'CRITICAL': RED, 'HIGH': ORA, 'MEDIUM': YEL, 'LOW': GRN}

# ═══════════════════════════════════════════════════════════════════
#  SPLASH SCREEN
# ═══════════════════════════════════════════════════════════════════

class Splash(tk.Toplevel):
    W, H = 420, 290

    def __init__(self, parent):
        super().__init__(parent)
        self.overrideredirect(True)
        self.configure(bg=BG)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f'{self.W}x{self.H}+{(sw-self.W)//2}+{(sh-self.H)//2}')

        # Borde ACC
        bd = tk.Frame(self, bg=ACC, padx=1, pady=1)
        bd.pack(fill='both', expand=True)
        inner = tk.Frame(bd, bg=BG)
        inner.pack(fill='both', expand=True)

        self.cv = tk.Canvas(inner, width=130, height=130,
            bg=BG, highlightthickness=0)
        self.cv.pack(pady=(22, 6))

        tk.Label(inner, text='HateFileless',
            font=('Segoe UI', 16, 'bold'), bg=BG, fg=FG).pack()
        tk.Label(inner, text='Fileless Detection Tool',
            font=('Segoe UI', 9), bg=BG, fg=FGD).pack(pady=(2, 8))

        self.lbl = tk.Label(inner, text='Initializing…',
            font=('Consolas', 8), bg=BG, fg=ACC)
        self.lbl.pack()

        # Mini barra de carga
        self.bar = tk.Canvas(inner, width=220, height=3,
            bg=BG4, highlightthickness=0)
        self.bar.pack(pady=8)

        self._a1, self._a2 = 0, 180
        self._bp = 0
        self._alive = True
        self._spin()
        self._bar_anim()

    def _spin(self):
        if not self._alive: return
        c, cx, cy = self.cv, 65, 65
        c.delete('all')

        # Anillo exterior
        r1 = 52
        c.create_arc(cx-r1, cy-r1, cx+r1, cy+r1,
            start=self._a1, extent=260,
            style='arc', outline=ACC, width=3)
        # Punta brillante
        import math
        a_rad = math.radians(self._a1)
        px = cx + r1 * math.cos(a_rad)
        py = cy - r1 * math.sin(a_rad)
        c.create_oval(px-4, py-4, px+4, py+4, fill=AC2, outline='')

        # Anillo interior (counter)
        r2 = 36
        c.create_arc(cx-r2, cy-r2, cx+r2, cy+r2,
            start=self._a2, extent=110,
            style='arc', outline=AC2, width=2)

        # Centro
        c.create_oval(cx-5, cy-5, cx+5, cy+5, fill=ACC, outline='')
        c.create_text(cx, cy, text='FT',
            font=('Segoe UI', 8, 'bold'), fill=BG3)

        self._a1 = (self._a1 + 5) % 360
        self._a2 = (self._a2 - 3) % 360
        self.after(14, self._spin)

    def _bar_anim(self):
        if not self._alive: return
        w = 220
        self.bar.delete('all')
        p = (self._bp % (w + 80)) - 40
        x1, x2 = max(0, p), min(w, p + 80)
        if x1 < x2:
            self.bar.create_rectangle(x1, 0, x2, 3, fill=ACC, outline='')
        self._bp += 4
        self.after(14, self._bar_anim)

    def set_status(self, text: str):
        self.lbl.config(text=text)
        self.update()

    def close(self):
        self._alive = False
        self.destroy()

# ═══════════════════════════════════════════════════════════════════
#  MAIN APP
# ═══════════════════════════════════════════════════════════════════

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.findings: list[dict] = []
        self.q: queue.Queue = queue.Queue()
        self.tabs: dict[str, tuple] = {}
        self._scanning  = False
        self._wave_x    = 0
        self._spin_t    = 0
        self._stat_cur  = {s: 0 for s in SEV_COL}
        self._stat_tgt  = {s: 0 for s in SEV_COL}

        root.title(f'HateFileless v{VERSION} — Fileless Detection Suite')
        root.geometry('1200x760')
        root.minsize(960, 620)
        root.configure(bg=BG)

        self._style()
        self._build()
        root.bind('<Configure>', lambda e: self._draw_hdr())
        self._poll()

    # ── Estilos ──────────────────────────────────────────────────

    def _style(self):
        s = ttk.Style(self.root)
        s.theme_use('clam')
        s.configure('.', background=BG, foreground=FG,
                    fieldbackground=BG2, bordercolor=BRD,
                    troughcolor=BG3, selectbackground=ACC,
                    selectforeground='white')
        s.configure('TFrame', background=BG)
        s.configure('TLabel', background=BG, foreground=FG)
        s.configure('TNotebook', background=BG2, tabposition='nw')
        s.configure('TNotebook.Tab', background=BG3, foreground=FGD,
                    padding=(14, 6))
        s.map('TNotebook.Tab',
              background=[('selected', BG2)],
              foreground=[('selected', FG)])
        s.configure('Treeview', background=BG2, foreground=FG,
                    fieldbackground=BG2, rowheight=26, borderwidth=0)
        s.configure('Treeview.Heading', background=BG4,
                    foreground=FGD, relief='flat', padding=(6, 4))
        s.map('Treeview',
              background=[('selected', ACC)],
              foreground=[('selected', 'white')])
        s.configure('TScrollbar', background=BG3, troughcolor=BG,
                    arrowcolor=FGD, bordercolor=BG)
        s.configure('Run.TButton', background=ACC, foreground='white',
                    borderwidth=0, padding=(16, 8),
                    font=('Segoe UI', 10, 'bold'))
        s.map('Run.TButton',
              background=[('active', '#005fcc'), ('disabled', BG4)])
        s.configure('TButton', background=BG3, foreground=FGD,
                    borderwidth=1, bordercolor=BRD, padding=(8, 5))
        s.map('TButton', background=[('active', BG4)])
        s.configure('Status.TLabel', background=BG2,
                    foreground=FGD, padding=(10, 4),
                    font=('Consolas', 8))

    # ── Build ─────────────────────────────────────────────────────

    def _build(self):
        # Header canvas
        self.hdr = tk.Canvas(self.root, height=80,
            bg=BG2, highlightthickness=0)
        self.hdr.pack(fill='x')

        # Botones flotando sobre el header
        bf = tk.Frame(self.hdr, bg=BG2)
        bf.place(relx=1.0, rely=0.5, anchor='e', x=-12)
        ttk.Button(bf, text='Clear', command=self.clear).pack(side='right', padx=(4,0))
        self.btn = ttk.Button(bf, text='▶  Run Analysis',
            style='Run.TButton', command=self.run)
        self.btn.pack(side='right', padx=4)

        tk.Frame(self.root, height=1, bg=BRD).pack(fill='x')

        # PanedWindow vertical
        pane = tk.PanedWindow(self.root, orient='vertical',
            bg=BG, sashwidth=6, sashrelief='flat', sashpad=2)
        pane.pack(fill='both', expand=True, padx=6, pady=6)

        # Panel superior: Notebook
        top = tk.Frame(pane, bg=BG)
        pane.add(top, minsize=240)
        self.nb = ttk.Notebook(top)
        self.nb.pack(fill='both', expand=True)
        self._make_tab('All')

        # Panel inferior: Detalle
        bot = tk.Frame(pane, bg=BG)
        pane.add(bot, minsize=140)

        det_hdr = tk.Frame(bot, bg=BG3, height=30)
        det_hdr.pack(fill='x')
        det_hdr.pack_propagate(False)

        self.lbl_sev = tk.Label(det_hdr, text=' ● ',
            font=('Segoe UI', 11, 'bold'), bg=BG3, fg=FGD)
        self.lbl_sev.pack(side='left', padx=(8, 0))
        self.lbl_title = tk.Label(det_hdr, text='Detail — click a row',
            font=('Segoe UI', 9, 'bold'), bg=BG3, fg=FGD)
        self.lbl_title.pack(side='left')
        self.lbl_meta = tk.Label(det_hdr, text='',
            font=('Consolas', 8), bg=BG3, fg=FGD)
        self.lbl_meta.pack(side='left', padx=10)

        det_body = tk.Frame(bot, bg=BG)
        det_body.pack(fill='both', expand=True)

        self.txt = tk.Text(det_body, bg=BG2, fg=FG,
            insertbackground=FG, font=('Consolas', 9),
            wrap='word', relief='flat', borderwidth=0,
            state='disabled', padx=10, pady=8)
        vsb_d = ttk.Scrollbar(det_body, orient='vertical',
            command=self.txt.yview)
        self.txt.configure(yscrollcommand=vsb_d.set)
        vsb_d.pack(side='right', fill='y')
        self.txt.pack(fill='both', expand=True)

        self.txt.tag_configure('section',
            foreground=ACC, font=('Consolas', 9, 'bold'))
        self.txt.tag_configure('fileless',
            foreground=RED, font=('Consolas', 9, 'bold'))
        for sev, col in SEV_COL.items():
            self.txt.tag_configure(f'sev_{sev}', foreground=col)

        # Scan bar (2px animada al fondo)
        self.scan_bar = tk.Canvas(self.root, height=2,
            bg=BG, highlightthickness=0)
        self.scan_bar.pack(fill='x', side='bottom')

        self.status_var = tk.StringVar(value='Ready — press ▶ Run Analysis')
        ttk.Label(self.root, textvariable=self.status_var,
            style='Status.TLabel').pack(fill='x', side='bottom')

        self._draw_hdr()

    # ── Header ───────────────────────────────────────────────────

    def _draw_hdr(self):
        c = self.hdr
        c.delete('all')
        w = max(c.winfo_width(), 1)

        # Fondo degradado vertical simulado
        for i in range(80):
            v = int(0x12 + (0x1a - 0x12) * i / 79)
            c.create_line(0, i, w, i, fill=f'#0d0d{v:02x}')

        # Acento izquierdo
        c.create_rectangle(0, 0, 3, 80, fill=ACC, outline='')

        # Título
        c.create_text(22, 22, text='◈  HateFileless',
            font=('Segoe UI', 14, 'bold'), fill=FG, anchor='w')
        c.create_text(24, 44, text=f'v{VERSION}  —  Fileless Detection Suite',
            font=('Segoe UI', 8), fill=FGD, anchor='w')

        # Badges de severidad
        sevcols = [('CRITICAL', RED), ('HIGH', ORA),
                   ('MEDIUM', YEL), ('LOW', GRN)]
        x = 240
        for sev, col in sevcols:
            n = self._stat_cur.get(sev, 0)
            c.create_rectangle(x, 18, x+90, 62,
                fill=BG3, outline=col, width=1)
            c.create_text(x+45, 34,
                text=str(n),
                font=('Segoe UI', 13, 'bold'), fill=col)
            c.create_text(x+45, 52,
                text=sev,
                font=('Segoe UI', 7), fill=col)
            x += 98

        # Wave scan (solo si está escaneando)
        if self._scanning:
            wp = self._wave_x % (w + 220)
            for i, alpha in enumerate([1.0, 0.5, 0.2]):
                xi = wp - i * 50
                xf = xi + 150
                col_w = ACC if i == 0 else (AC2 if i == 1 else BG4)
                if xf > 0 and xi < w:
                    c.create_rectangle(max(0,xi), 74,
                        min(w,xf), 80, fill=col_w, outline='')

        # Borde inferior
        c.create_line(0, 79, w, 79, fill=BRD, width=1)

    def _anim_wave(self):
        if not self._scanning: return
        self._wave_x += 5
        self._draw_hdr()
        # Barra inferior
        c, w = self.scan_bar, max(self.scan_bar.winfo_width(), 1)
        c.delete('all')
        p = (self._spin_t * 4) % (w + 160)
        x1, x2 = p - 80, p + 80
        if x1 < w and x2 > 0:
            c.create_rectangle(max(0,x1), 0, min(w,x2), 2,
                fill=ACC, outline='')
        self._spin_t += 1
        self.root.after(14, self._anim_wave)

    def _count_up(self):
        done = True
        for sev in SEV_COL:
            cur, tgt = self._stat_cur[sev], self._stat_tgt[sev]
            if cur < tgt:
                self._stat_cur[sev] = min(cur + max(1, (tgt-cur)//3+1), tgt)
                done = False
        self._draw_hdr()
        if not done:
            self.root.after(28, self._count_up)

    # ── Pestaña ──────────────────────────────────────────────────

    def _make_tab(self, name: str):
        fr = tk.Frame(self.nb, bg=BG)
        self.nb.add(fr, text=f'  {name}  ')

        cols = ('time', 'sev', 'source', 'hits', 'summary')
        tree = ttk.Treeview(fr, columns=cols,
            show='headings', selectmode='browse')
        tree.heading('time',    text='Tiempo')
        tree.heading('sev',     text='Severidad')
        tree.heading('source',  text='Fuente')
        tree.heading('hits',    text='Detecciones')
        tree.heading('summary', text='Preview')
        tree.column('time',    width=148, minwidth=120, stretch=False)
        tree.column('sev',     width=82,  minwidth=70,  stretch=False)
        tree.column('source',  width=205, minwidth=140, stretch=False)
        tree.column('hits',    width=195, minwidth=130, stretch=False)
        tree.column('summary', width=500, minwidth=200)

        for sev, col in SEV_COL.items():
            tree.tag_configure(sev, foreground=col)

        vsb = ttk.Scrollbar(fr, orient='vertical',   command=tree.yview)
        hsb = ttk.Scrollbar(fr, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side='bottom', fill='x')
        vsb.pack(side='right',  fill='y')
        tree.pack(fill='both', expand=True)

        tree.bind('<<TreeviewSelect>>',
                  lambda e, t=tree: self._on_select(t))
        self.tabs[name] = (fr, tree)
        return tree

    # ── Click fila ────────────────────────────────────────────────

    def _on_select(self, tree):
        sel = tree.selection()
        if not sel: return
        try:
            idx = int(sel[0].split('_')[1])
            f   = self.findings[idx]
        except Exception: return

        sev = f['severity']
        col = SEV_COL.get(sev, FGD)
        fl  = '  ⚡ FILELESS' if f.get('fileless') else ''

        self.lbl_sev.config(fg=col)
        self.lbl_title.config(text=f'[{sev}]  {f["source"]}{fl}', fg=col)
        self.lbl_meta.config(text=f'  {f["time"]}   |   {f["path"]}')

        self.txt.config(state='normal')
        self.txt.delete('1.0', 'end')
        self.txt.insert('end', '━━ DETECCIONES ━━\n', 'section')
        for hn, hs in f['hits']:
            self.txt.insert('end', f'  [{hs}] {hn}\n', f'sev_{hs}')
        if f.get('fileless'):
            self.txt.insert('end',
                '\n  ⚡ FILELESS — ejecutado en memoria, sin archivo en disco\n',
                'fileless')
        self.txt.insert('end', '\n━━ CONTENIDO ━━\n', 'section')
        self.txt.insert('end', f['content'])
        self.txt.config(state='disabled')

    # ── Agregar finding ──────────────────────────────────────────

    def _add_finding(self, f: dict, idx: int):
        iid      = f'f_{idx}'
        hits_str = ', '.join(dict.fromkeys(h[0] for h in f['hits']))[:72]
        vals     = (f['time'], f['severity'], f['source'],
                    hits_str, f['summary'])
        sev      = f['severity']

        self.tabs['All'][1].insert('', 'end', iid=iid,
            values=vals, tags=(sev,))

        src = f['source'].split('(')[0].strip()[:30]
        if src not in self.tabs:
            self._make_tab(src)
        self.tabs[src][1].insert('', 'end', iid=iid,
            values=vals, tags=(sev,))

    # ── Run ──────────────────────────────────────────────────────

    def run(self):
        self.btn.config(state='disabled', text='⏳  Scanning…')
        self.clear(keep_btn=True)
        self._scanning = True
        self._wave_x   = 0
        self._spin_t   = 0
        self.status_var.set('Iniciando análisis…')
        self._anim_wave()

        def worker():
            all_f = []
            for name, fn in SCANNERS:
                self.q.put(('status', f'Estado: {name}…'))
                try:
                    res = fn()
                    all_f.extend(res)
                except Exception as e:
                    self.q.put(('status', f'  ✗ {name}: {e}'))
            all_f.sort(key=lambda x: (
                SEV_ORDER.get(x['severity'], 9), x['time']))
            self.q.put(('done', all_f))

        threading.Thread(target=worker, daemon=True).start()

    # ── Poll ──────────────────────────────────────────────────────

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == 'status':
                    self.status_var.set(msg[1])
                elif msg[0] == 'done':
                    self.findings = msg[1]
                    for sev in self._stat_tgt:
                        self._stat_tgt[sev] = sum(
                            1 for f in self.findings
                            if f['severity'] == sev)
                    delay = 0
                    for i, f in enumerate(self.findings):
                        self.root.after(delay,
                            lambda fi=f, ii=i: self._add_finding(fi, ii))
                        delay += 22
                    self.root.after(delay + 200, self._done)
        except queue.Empty:
            pass
        self.root.after(80, self._poll)

    def _done(self):
        self._scanning = False
        self.scan_bar.delete('all')
        n = len(self.findings)
        c = self._stat_tgt.get('CRITICAL', 0)
        h = self._stat_tgt.get('HIGH', 0)
        self.status_var.set(
            f'✓ Completado — {n} findings  |  {c} CRITICAL  '
            f'{h} HIGH  |  {len(self.tabs)-1} fuentes')
        self.btn.config(state='normal', text='▶  Run Analysis')
        self._count_up()

    # ── Clear ─────────────────────────────────────────────────────

    def clear(self, keep_btn=False):
        self.findings = []
        self._stat_cur = {s: 0 for s in SEV_COL}
        self._stat_tgt = {s: 0 for s in SEV_COL}
        self.txt.config(state='normal')
        self.txt.delete('1.0', 'end')
        self.txt.config(state='disabled')
        self.lbl_title.config(text='Detail — click a row', fg=FGD)
        self.lbl_meta.config(text='')
        self.lbl_sev.config(fg=FGD)
        if not keep_btn:
            self.status_var.set('Ready — press ▶ Run Analysis')
        for name in list(self.tabs):
            _, tree = self.tabs[name]
            tree.delete(*tree.get_children())
            if name != 'All':
                self.nb.forget(self.tabs[name][0])
                del self.tabs[name]
        self._draw_hdr()

# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    if sys.platform != 'win32':
        print('Solo Windows.'); sys.exit(1)

    try:    admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except: admin = False

    root = tk.Tk()
    root.withdraw()

    splash = Splash(root)
    steps = [
        ('Cargando firmas PS…',    0.3),
        ('Compilando regex…',      0.3),
        ('Preparando escáneres…',  0.3),
        ('Listo.',                 0.15),
    ]
    for msg, delay in steps:
        splash.set_status(msg)
        _t.sleep(delay)

    splash.close()

    if not admin:
        messagebox.showwarning('HateFileless — Sin Admin',
            'Sin privilegios de administrador.\n'
            'Pueden devolver resultados limitados.\n\n'
            'Recomendado: ejecutar como Administrador.')

    root.deiconify()
    App(root)
    root.mainloop()

if __name__ == '__main__':
    main()
