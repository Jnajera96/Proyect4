"""Real-browser profile-mode smoke test. Uses only local backend and fake STT."""

from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import verify_frontend as browser

PROBE = r"""
const requests=[], failures=[];
let authenticated=false;
const originalFetch=window.fetch;
window.fetch=async function(url,init) {
  requests.push({url:String(url),authenticated});
  return originalFetch.call(this,url,init);
};
window.addEventListener('error', e=>failures.push(e.message));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const button=text=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===text);
async function wait(fn) {
  for(let i=0;i<500;i++){if(fn())return;await sleep(50);}throw Error('Timeout');
}
function fill(name,value) {
  const input=document.querySelector(`[name="${name}"]`);
  const proto=input.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto,'value').set.call(input,value);
  input.dispatchEvent(new Event('input',{bubbles:true}));
}
function check(value,label) {if(!value)throw Error(label);}
(async()=>{
  let passed=[];
  try {
    await wait(()=>button('Crear un perfil nuevo'));
    check(!requests.some(r=>/^\/(runs|projects|transcriptions)/.test(r.url)),
      'private fetch before login');
    passed.push('private data gated');
    button('Crear un perfil nuevo').click();
    await wait(()=>button('Crear perfil y entrar'));
    fill('name','alice');fill('password','browser-test-password');
    authenticated=true;
    button('Crear perfil y entrar').click();
    await wait(()=>button('Configurar bóveda') && document.querySelector('#btn-crear'));
    passed.push('registration and workspace');
    document.querySelector('#btn-crear').click();
    await wait(()=>window.__AISWE__?.runId);
    const aliceRun=window.__AISWE__.runId;
    await wait(()=>window.__AISWE__?.tipos?.length || window.__AISWE__?.eventos?.length);
    passed.push('profile run and cookie SSE');
    check(!document.cookie.includes('aiswe_session'),'cookie readable');
    button('Configurar bóveda').click();
    await wait(()=>document.querySelector('[name="hf_token"]'));
    fill('hf_token','hf_browser-only-secret');fill('budget_limit','3');
    button('Guardar bóveda').click();
    await wait(()=>[...document.querySelectorAll('[role="status"]')]
      .some(e=>e.textContent.includes('guardada')));
    button('Configurar bóveda').click();
    await wait(()=>document.querySelector('[name="hf_token"]'));
    check(document.querySelector('[name="hf_token"]').value==='','token reflected');
    check(document.body.textContent.includes('Token: guardado'),'token not saved');
    check(!document.body.textContent.includes('hf_browser-only-secret'),'token in DOM');
    passed.push('vault saved without token echo');
    button('Cerrar sesión').click();
    await wait(()=>button('Entrar'));
    authenticated=false;
    check((await originalFetch('/runs')).status===401,'logout failed');
    passed.push('logout revocation');
    button('Crear un perfil nuevo').click();await wait(()=>button('Crear perfil y entrar'));
    fill('name','bob');fill('password','browser-test-password');authenticated=true;
    button('Crear perfil y entrar').click();await wait(()=>button('Configurar bóveda'));
    button('Configurar bóveda').click();await wait(()=>document.querySelector('[name="hf_token"]'));
    check(document.body.textContent.includes('Token: sin configurar'),'cross-user token');
    check((await (await originalFetch('/runs')).json()).length===0,'cross-user runs');
    check((await originalFetch('/runs/'+aliceRun)).status===404,'cross-user direct run');
    passed.push('second user isolation');
    button('Cerrar sesión').click();await wait(()=>button('Entrar'));
    fill('name','alice');fill('password','browser-test-password');button('Entrar').click();
    await wait(()=>button('Configurar bóveda'));
    check(document.body.textContent.includes('Perfil: alice'),'login identity');
    check(!JSON.stringify([localStorage,sessionStorage]).includes('hf_browser-only-secret'),
      'secret persisted');
    passed.push('login restores profile');
    check(failures.length===0,failures.join(';'));
    const report=document.createElement('pre');report.id='profile-report';
    report.textContent=JSON.stringify({passed});document.body.appendChild(report);
  }catch(e){const report=document.createElement('pre');report.id='profile-report';
    report.textContent=JSON.stringify({passed,error:String(e),failures});document.body.appendChild(report);}
})();
"""


def main():
    executable = browser.encontrar_navegador()
    if not executable:
        raise SystemExit("Chromium unavailable: profile browser verification not run")
    browser._reconstruir()
    (browser.DIST / "_profiles_probe.js").write_text(PROBE, encoding="utf-8")
    page = (
        (browser.DIST / "index.html")
        .read_text(encoding="utf-8")
        .replace(
            '<script type="module"',
            '<script src="_profiles_probe.js"></script><script type="module"',
            1,
        )
    )
    (browser.DIST / "_profiles.html").write_text(page, encoding="utf-8")
    # Retain isolated test artifacts; no deletion outside the workspace is necessary.
    root = Path(tempfile.mkdtemp(prefix="aiswe-profiles-browser-"))
    port = browser.puerto_libre()
    env = {
        **os.environ,
        "PYTHONPATH": "src",
        "AI_SWE_PROFILE_MODE": "true",
        "AI_SWE_PROFILES_ROOT": str(root / "users"),
        "AI_SWE_STT_PROVIDER": "fake",
        "AI_SWE_REMOTE_MODEL_ROLES": "[]",
    }
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "ai_swe.api.app:crear_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=browser.RAIZ,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        if not browser.esperar_servidor(base + "/health"):
            raise RuntimeError("Profile server did not start")
        dom, completed = browser._lanzar_navegador(
            [
                str(executable),
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--dump-dom",
                "--hide-scrollbars",
                "--virtual-time-budget=40000",
                f"--user-data-dir={root / 'browser'}",
                base + "/app/_profiles.html",
            ],
            limite=60,
        )
        match = re.search(r'<pre id="profile-report">(.*?)</pre>', dom, re.S)
        if not completed or not match:
            print(dom[-3000:])
            raise RuntimeError("Browser did not return a profile report")
        report = json.loads(html.unescape(match.group(1)))
        print(json.dumps(report, indent=2))
        return 1 if report.get("error") else 0
    finally:
        server.terminate()
        server.wait(timeout=15)


if __name__ == "__main__":
    raise SystemExit(main())
