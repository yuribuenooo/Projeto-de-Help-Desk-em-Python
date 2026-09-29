# Help Desk – Python/Django

Sistema de chamados com **login individual**, anexos, setores, prazos (SLA) e dashboard.
Django + templates + SQLite, API REST (JSON), JavaScript, acessibilidade, testes, Git e Docker/Render.

## Rodar (Windows/PowerShell, dentro da pasta com `manage.py`)
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    python manage.py migrate
    python manage.py criar_demo      # usuários e chamados de exemplo (só em DEBUG)
    python manage.py runserver       # http://127.0.0.1:8000
    python manage.py test            # testes

Usuários de demonstração: `tecnico` (técnico) e `cliente` (solicitante), ambos com a senha `Senha@12345`.
Para criar um técnico real: `python manage.py createsuperuser` e acesse `/admin/` (marque "Membro da equipe" nos técnicos).

## Perfis
- **Solicitante**: cria conta em *Criar conta*, abre chamados (categoria, setor, prioridade, anexo), acompanha o status, responde, confirma a solução (fecha) ou reabre. Só vê os próprios chamados.
- **Técnico** (`is_staff`): vê todos, assume, altera status (aberto/em andamento/pendente) e prioridade, encaminha para outro setor, comenta e finaliza (resolve) com a solução aplicada.

## Regras
- Status: Aberto → Em andamento ⇄ Pendente (aguardando solicitante) → Resolvido → Fechado (ou reaberto).
- Se o solicitante responde a um chamado Pendente, ele volta para Em andamento.
- Prazo (SLA) por prioridade: urgente 4 h · alta 8 h · média 24 h · baixa 72 h (contado desde a abertura).
- Todas as mudanças ficam registradas no histórico do chamado.
- Anexos: até 5 MB (pdf, imagens, txt, log, csv, doc/docx, xls/xlsx), baixados apenas por view autenticada.

## Dashboard
Abertos, em andamento, pendentes, resolvidos, atrasados, tempo médio de atendimento, % resolvido no prazo; gráficos por status, prioridade, setor, categoria e mês, e produtividade por técnico. Cada gráfico tem tabela com os números (acessível).

## MVC no Django (MVT)
- **Model** `chamados/models.py` – regras de negócio, SLA e análise (`Chamado.resumo`)
- **View (apresentação)** = **Templates** em `chamados/templates`
- **Controller** = **views** em `chamados/views.py` (HTML) e `chamados/api.py` (JSON)

## API (exige sessão autenticada)
`GET/POST /api/chamados` · `GET /api/setores` · `GET /api/relatorio`

## Acessibilidade
`lang`, link "pular para conteúdo", labels ligados aos campos, `aria-live`, foco visível, tabelas com `caption`/`scope`, gráficos com tabela equivalente, modo escuro.

## Segurança
Senhas com hash e validadores do Django, CSRF nos formulários, cada usuário só acessa seus chamados/anexos, ações de técnico exigem `is_staff`.

## Git
    git init -b main && git add . && git commit -m "feat: versão inicial"

## Nuvem (Render)
Suba no GitHub → Render → New → Blueprint. Anexos e SQLite ficam em disco efêmero no plano gratuito: em produção use PostgreSQL e um Disk/armazenamento (S3) para `MEDIA_ROOT`.
