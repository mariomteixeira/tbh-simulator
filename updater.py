#!/usr/bin/env python3
"""
Auto-update do TBH Copilot a partir do GitHub.

So fica ativo quando existe um update_config.json ao lado deste arquivo:

    {"repo": "usuario/tbh-simulator", "branch": "main"}
    (opcional: "token": "ghp_..." para repositorio privado)

O update baixa o zip do branch e sobrescreve o app, PRESERVANDO:
  - data/        (store.json: calibracoes, teto, historico)
  - python/      (runtime embutido do pacote portatil)
  - .version     (atualizado ao final com o sha novo)

Uso pelo launcher (tbh_painel) ou na mao:
    python updater.py --check    # ha versao nova?
    python updater.py --apply    # baixa e aplica
"""

import io
import json
import ssl
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "update_config.json"
VERSION_FILE = ROOT / ".version"
CACERT = ROOT / "cacert.pem"        # bundle de CAs (certifi) p/ Python sem certs
# nunca sobrescrever (dados do jogador e runtime); .git so existe no dev
PRESERVE = {"data", "python", ".git", ".version", "node_modules",
            "dist-portable", "reference"}
UA = {"User-Agent": "TBH-Copilot-updater"}


def _cfg():
    if not CONFIG.exists():
        return None
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        return cfg if cfg.get("repo") else None
    except (OSError, ValueError):
        return None


def _headers(cfg):
    h = dict(UA)
    if cfg.get("token"):
        h["Authorization"] = f"Bearer {cfg['token']}"
    return h


def _ssl_ctx(cfg):
    """Contexto SSL tolerante a Python sem CA certs (caso comum no runtime
    portatil do Windows). Adiciona o bundle do certifi + o store do Windows.
    Com "insecure": true no update_config.json, pula a verificacao (ultimo
    recurso, ex.: antivirus interceptando HTTPS)."""
    if cfg.get("insecure"):
        sys.stderr.write("[updater] AVISO: SSL sem verificacao (insecure)\n")
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    ctx = ssl.create_default_context()
    if CACERT.exists():
        try:
            ctx.load_verify_locations(cafile=str(CACERT))   # roots do certifi
        except OSError:
            pass
    try:
        ctx.load_default_certs()        # + store do Windows (pega AV/corporativo)
    except Exception:
        pass
    return ctx


def _err_hint(e):
    s = str(e)
    if "CERTIFICATE_VERIFY_FAILED" in s or "SSL" in s.upper():
        return (f"{e} -> erro de certificado SSL. Tente, nesta ordem: "
                "(1) corrigir a DATA/HORA do PC; "
                "(2) desligar a 'verificacao HTTPS/SSL' do antivirus; "
                '(3) adicionar "insecure": true ao update_config.json.')
    return s


def local_sha() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def remote_sha(cfg) -> str:
    url = (f"https://api.github.com/repos/{cfg['repo']}/commits/"
           f"{cfg.get('branch', 'main')}")
    req = urllib.request.Request(
        url, headers={**_headers(cfg), "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx(cfg)) as r:
        return json.loads(r.read())["sha"]


def check():
    """None = sem config/sem rede; senao {'update': bool, 'remote': sha, 'local': sha}."""
    cfg = _cfg()
    if not cfg:
        return None
    try:
        rs = remote_sha(cfg)
    except Exception:
        return None
    return {"update": rs != local_sha(), "remote": rs, "local": local_sha()}


def _download_zip(cfg) -> bytes:
    if cfg.get("token"):
        # repo privado: zipball autenticado via API
        url = (f"https://api.github.com/repos/{cfg['repo']}/zipball/"
               f"{cfg.get('branch', 'main')}")
    else:
        url = (f"https://codeload.github.com/{cfg['repo']}/zip/refs/heads/"
               f"{cfg.get('branch', 'main')}")
    req = urllib.request.Request(url, headers=_headers(cfg))
    with urllib.request.urlopen(req, timeout=180, context=_ssl_ctx(cfg)) as r:
        return r.read()


def extract_over(zf: zipfile.ZipFile, root: Path):
    """Extrai o zip (que tem um diretorio-prefixo) por cima de root,
    pulando os diretorios PRESERVE."""
    names = zf.namelist()
    prefix = names[0].split("/")[0]
    for n in names:
        rel = Path(n[len(prefix) + 1:]) if n.startswith(prefix + "/") else None
        if not rel or not rel.parts:
            continue
        if rel.parts[0] in PRESERVE:
            continue
        dest = root / rel
        if n.endswith("/"):
            dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(n))


def apply_update():
    """(ok, mensagem). Baixa o branch e aplica por cima, preservando dados."""
    cfg = _cfg()
    if not cfg:
        return False, "sem update_config.json (instalacao de desenvolvimento)"
    try:
        rs = remote_sha(cfg)
    except Exception as e:
        return False, f"sem acesso ao GitHub: {_err_hint(e)}"
    if rs == local_sha():
        return True, "ja esta na ultima versao"
    try:
        blob = _download_zip(cfg)
        extract_over(zipfile.ZipFile(io.BytesIO(blob)), ROOT)
        VERSION_FILE.write_text(rs, encoding="utf-8")
        return True, f"atualizado para {rs[:10]}"
    except Exception as e:
        return False, f"update falhou: {e}"


if __name__ == "__main__":
    if "--apply" in sys.argv:
        ok, msg = apply_update()
        print(("[ok] " if ok else "[erro] ") + msg)
        sys.exit(0 if ok else 1)
    info = check()
    if info is None:
        print("sem config de update (ou sem rede)")
    else:
        print("nova versao disponivel" if info["update"] else "atualizado",
              "| local:", info["local"][:10] or "(nenhuma)",
              "| remoto:", info["remote"][:10])
