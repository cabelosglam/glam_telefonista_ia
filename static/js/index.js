(() => {
  const $form = document.getElementById('callForm');
  const $btn  = document.getElementById('callBtn');
  const $to   = document.getElementById('to');
  const $log  = document.getElementById('log');
  const $status = document.getElementById('status');
  const $name    = document.getElementById('name');   // <-- NOVO

  const E164 = /^\+\d{8,15}$/; // simples e direto
  const LS_NM = 'dial_last_name';     // <-- NOVO

  // Restaura último número usado
  const LS_KEY = 'dial_last_to';
  const last = localStorage.getItem(LS_KEY);
  const lastNm = localStorage.getItem(LS_NM);  
  
  if (last && !$to.value) $to.value = last;
  if (lastNm && !$name.value) $name.value = lastNm;   // <-- NOVO

  function log(msg, cls = "") {
    const line = document.createElement('div');
    if (cls) line.className = cls;
    line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    $log.prepend(line);
  }

  function setStatus(text, tone = 'muted') {
    $status.textContent = text || '';
    $status.className = `status ${tone}`;
  }

  async function startCall(ev) {
    ev?.preventDefault();
    const to = ($to.value || '').trim();
    const name = ($name.value || '').trim(); 

    if (!E164.test(to)) {
      setStatus('Número inválido. Use E.164, ex.: +5562...', 'err');
      log('Número inválido. Use E.164, ex.: +5562...', 'err');
      $to.focus();
      return;
    }

    localStorage.setItem(LS_KEY, to);
    if (name) localStorage.setItem(LS_NM, name);      // <-- NOVO

    setStatus(`Chamando ${to}...`, 'ok');

    $btn.disabled = true;
    $btn.classList.add('loading');

    try {
      const res = await fetch('/api/call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ to, name })
      });

      // Pode dar erro 4xx/5xx sem JSON válido
      let data = {};
      try { data = await res.json(); } catch { /* ignore */ }

      if (!res.ok || !data.ok) {
        const msg = (data && data.error) ? data.error : res.statusText || 'Erro desconhecido';
        setStatus('Falha ao iniciar a ligação.', 'err');
        log(`Falha ao iniciar: ${msg}`, 'err');
        return;
      }

      setStatus('Ligação criada. Atenda e converse com a IA. 😄', 'ok');
      log(`Ligação criada. SID: ${data.sid}`, 'ok');
    } catch (err) {
      setStatus('Erro de rede ao iniciar a ligação.', 'err');
      log(`Erro de rede: ${err.message}`, 'err');
    } finally {
      $btn.disabled = false;
      $btn.classList.remove('loading');
    }
  }

  // Eventos
  $form.addEventListener('submit', startCall);
  $to.addEventListener('keydown', e => {
    if (e.key === 'Enter') startCall(e);
  });

  // Dica extra ao focar
  $to.addEventListener('focus', () => {
    setStatus('Formato E.164: +[código do país][DDD][número]. Ex.: +5562...', 'muted');
  });
})();
