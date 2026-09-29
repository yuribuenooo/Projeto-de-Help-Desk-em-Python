// Painel: atualiza indicadores pela API REST (usa a sessão do usuário logado)
const btn = document.getElementById('atualizar');
if (btn) {
  btn.addEventListener('click', async () => {
    const info = document.getElementById('status-atualizacao');
    const r = await fetch('/api/relatorio', { headers: { Accept: 'application/json' } });
    if (!r.ok) { info.textContent = 'Não foi possível atualizar. Faça login novamente.'; return; }
    const d = await r.json();
    for (const k of ['total', 'abertos', 'em_andamento', 'pendentes', 'resolvidos', 'atrasados', 'media_horas', 'pct_no_prazo']) {
      const el = document.querySelector(`[data-k=${k}]`);
      if (el) el.textContent = (d[k] ?? '—') + (d[k] != null && el.dataset.suf ? el.dataset.suf : '');
    }
    info.textContent = 'Dados atualizados.';
  });
}
