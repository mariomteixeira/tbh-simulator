#!/usr/bin/env python3
"""
TBH Copilot - painelzinho de controle
=====================================

Mini-janela pra LIGAR/DESLIGAR o servidor (server.py) e ver que esta vivo,
sem precisar de terminal. Sobe o servidor como subprocesso usando o MESMO
Python que roda esta janela (sys.executable) -- entao basta o atalho da Area
de Trabalho apontar pro pythonw 3.12 (que tem fastapi/uvicorn) e funciona.

Uso:  pythonw tbh_painel.pyw     (ou duplo-clique no atalho "TBH Copilot")

Nao escreve nada no save; so controla o processo do servidor e le a API local.
A entrada de dados (calibracao de tempo etc.) fica toda no painel web.
"""

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

# No pacote portatil (Python embutido) o Tcl/Tk fica em python/tcl/ e o tkinter
# nao o acha sozinho — aponta antes de importar. Em instalacao normal nao faz mal.
_pyroot = os.path.dirname(os.path.abspath(sys.executable))
for _env, _sub in (("TCL_LIBRARY", "tcl8.6"), ("TK_LIBRARY", "tk8.6")):
    _p = os.path.join(_pyroot, "tcl", _sub)
    if os.path.isdir(_p):
        os.environ.setdefault(_env, _p)

import tkinter as tk
from tkinter import ttk

try:
    import updater  # auto-update via GitHub (ativo so com update_config.json)
except Exception:
    updater = None

ROOT = Path(__file__).resolve().parent
SERVER = ROOT / "server.py"
LOG = ROOT / "data" / "server.log"
PORT = 8423
URL = f"http://127.0.0.1:{PORT}"
SNAPSHOT_URL = f"{URL}/api/snapshot"
POLL_MS = 2000

# CREATE_NO_WINDOW: evita piscar um console preto caso o atalho aponte pro
# python.exe (com console) em vez do pythonw.exe.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ---------------------------------------------------------------------------
# Logica pura (testavel sem Tk)
# ---------------------------------------------------------------------------
def fmt(n):
    if n is None:
        return "—"
    n = round(n)
    if abs(n) >= 1_000_000:
        return f"{n / 1e6:.2f}M"
    if abs(n) >= 1_000:
        return f"{n / 1e3:.1f}k"
    return str(n)


def _age(ts, now):
    # mesmos limiares/arredondamento do painel web (timeAgo) p/ nao divergir
    if not ts:
        return "—"
    d = max(0, int(now - ts))
    if d < 5:
        return "agora"
    if d < 60:
        return f"há {d}s"
    if d < 3600:
        return f"há {d // 60}min"
    return f"há {d / 3600:.1f}h"


def render_info(snap, now):
    """Transforma um /api/snapshot nas linhas (rotulo, valor, cor) do painel.

    cor: None = normal, "erro" = vermelho, "ok" = verde. Defensivo: chave
    faltando vira "—" em vez de estourar.
    """
    snap = snap or {}
    st = snap.get("status") or {}
    state = snap.get("state") or {}
    sim = snap.get("sim") or {}
    sess = snap.get("sessionRates") or snap.get("rates") or {}

    rows = []

    found = st.get("saveFound")
    rows.append(("Save", "✓ encontrado" if found else "✗ não encontrado",
                 "ok" if found else "erro"))

    gd_ok = st.get("gamedataLoaded")
    rows.append(("Gamedata", "✓ ok" if gd_ok else "✗ faltando",
                 "ok" if gd_ok else "erro"))

    rows.append(("Última leitura", _age(st.get("lastRead"), now), None))

    # estagio atual: prefere o rotulo bonito do farm; cai pra chave crua
    label = None
    for r in (sim.get("farm") or {}).get("rows") or []:
        if r.get("current"):
            label = r.get("label")
            break
    rows.append(("Estágio atual", label or state.get("currentStage") or "—", None))

    dps = (sim.get("party") or {}).get("dps")
    rows.append(("DPS do time", fmt(dps), None))

    gph = sess.get("gold_per_hour")
    rows.append(("Gold/h (sessão)", fmt(gph), None))

    exp_by = sess.get("exp_per_hour") or {}
    eph = sum(v for v in exp_by.values() if v) if exp_by else None
    rows.append(("Exp/h (sessão)", fmt(eph), None))

    rows.append(("Calibrações", str(len(snap.get("manualSamples") or [])), None))

    err = st.get("error") or st.get("simError")
    if err:
        rows.append(("Erro", str(err), "erro"))

    return rows


# ---------------------------------------------------------------------------
# Janela
# ---------------------------------------------------------------------------
class Painel:
    def __init__(self, root):
        self.root = root
        self.proc = None
        self.browser_opened = False

        root.title("TBH Copilot")
        root.geometry("380x320")
        root.minsize(340, 300)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        pad = {"padx": 12, "pady": 6}
        top = ttk.Frame(root)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="TBH Copilot", font=("Segoe UI", 13, "bold")).pack(side="left")
        self.dot = ttk.Label(top, text="● Parado", foreground="#b00")
        self.dot.pack(side="right")

        btns = ttk.Frame(root)
        btns.pack(fill="x", **pad)
        self.b_start = ttk.Button(btns, text="▶ Iniciar", command=self.start)
        self.b_start.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.b_stop = ttk.Button(btns, text="■ Parar", command=self.stop, state="disabled")
        self.b_stop.pack(side="left", expand=True, fill="x", padx=(4, 0))
        self.b_open = ttk.Button(root, text="Abrir painel no navegador",
                                 command=lambda: webbrowser.open(URL), state="disabled")
        self.b_open.pack(fill="x", padx=12, pady=(0, 6))

        # auto-update (so em instalacao portatil, com update_config.json)
        self._update_msg = None
        if updater is not None and updater._cfg():
            self.b_update = ttk.Button(root, text="Atualizar",
                                       command=self.update_app)
            self.b_update.pack(fill="x", padx=12, pady=(0, 6))
            threading.Thread(target=self._check_update, daemon=True).start()
        else:
            self.b_update = None

        ttk.Separator(root).pack(fill="x", padx=12, pady=2)

        self.info = ttk.Frame(root)
        self.info.pack(fill="both", expand=True, padx=12, pady=6)
        self.rows = {}  # rotulo -> (label_valor)
        self._set_info([("status", "Parado — clique em Iniciar", None)])

        self.poll()

    # -- controle do processo ----------------------------------------------
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self):
        if self.running():
            return
        LOG.parent.mkdir(parents=True, exist_ok=True)
        self.browser_opened = False
        logf = open(LOG, "a", encoding="utf-8", errors="replace")
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            cwd=str(ROOT), stdout=logf, stderr=subprocess.STDOUT,
            creationflags=_NO_WINDOW)
        self.dot.config(text="● Iniciando…", foreground="#c80")
        self.b_start.config(state="disabled")
        self.b_stop.config(state="normal")
        self.b_open.config(state="normal")

    def stop(self):
        if self.proc is not None:
            try:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            except Exception:
                pass
        self.proc = None
        self.dot.config(text="● Parado", foreground="#b00")
        self.b_start.config(state="normal")
        self.b_stop.config(state="disabled")
        self.b_open.config(state="disabled")
        self._set_info([("status", "Parado — clique em Iniciar", None)])

    def on_close(self):
        # fechar a janela derruba o servidor junto (sem processo orfao)
        self.stop()
        self.root.destroy()

    # -- auto-update ---------------------------------------------------------
    def _check_update(self):
        info = updater.check()
        if info and info["update"]:
            self.root.after(0, lambda: self.b_update.config(
                text="Atualizar — nova versão disponível!"))

    def update_app(self):
        if self.b_update is None:
            return
        self.b_update.config(state="disabled", text="Atualizando…")
        was_running = self.running()
        self.stop()

        def work():
            ok, msg = updater.apply_update()
            self._update_msg = (ok, msg, was_running)

        threading.Thread(target=work, daemon=True).start()
        self._wait_update()

    def _wait_update(self):
        if self._update_msg is None:
            self.root.after(300, self._wait_update)
            return
        ok, msg, was_running = self._update_msg
        self._update_msg = None
        self.b_update.config(state="normal", text="Atualizar")
        self._set_info([("update", msg, "ok" if ok else "erro")])
        if ok and was_running:
            self.start()  # sobe o servidor ja com o codigo novo

    # -- polling da API -----------------------------------------------------
    def poll(self):
        if self.running():
            snap = self._fetch()
            if snap is not None:
                if not self.browser_opened:
                    self.browser_opened = True
                    webbrowser.open(URL)
                self.dot.config(text="● Rodando", foreground="#0a0")
                self._set_info(render_info(snap, time.time()))
            else:
                self.dot.config(text="● Iniciando…", foreground="#c80")
                self._set_info([("status", "Subindo o servidor…", None)])
        elif self.proc is not None:
            # processo morreu sozinho
            self.stop()
            self._set_info([("status", f"Servidor caiu — veja {LOG.name}", "erro")])
        self.root.after(POLL_MS, self.poll)

    def _fetch(self):
        try:
            with urllib.request.urlopen(SNAPSHOT_URL, timeout=1.5) as r:
                return json.loads(r.read())
        except Exception:
            return None

    # -- render das linhas --------------------------------------------------
    def _set_info(self, rows):
        for w in self.info.winfo_children():
            w.destroy()
        colors = {"erro": "#b00", "ok": "#0a0", None: ""}
        for i, (label, value, color) in enumerate(rows):
            ttk.Label(self.info, text=label + ":", foreground="#666").grid(
                row=i, column=0, sticky="w", pady=1)
            ttk.Label(self.info, text=str(value),
                      foreground=colors.get(color, "")).grid(
                row=i, column=1, sticky="w", padx=(8, 0), pady=1)


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")  # tema nativo do Windows quando existe
    except tk.TclError:
        pass
    Painel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
