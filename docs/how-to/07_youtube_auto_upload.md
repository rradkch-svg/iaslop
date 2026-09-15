# Como Autenticar e Postar Vídeos no YouTube Studio Automaticamente

Este guia ensina como configurar e utilizar o módulo de upload e agendamento automático via navegador web (Playwright / Chrome) para publicar os Shorts concluídos do Minuto Inexplicável Studio nos horários fixos diários (11:00, 13:00, 15:00 e 17:00 GMT), com limpeza imediata de mídia e alertas por e-mail.

---

## 1. Visão Geral da Automação

O módulo [`src/youtube_uploader.py`](file:///C:/Users/Aluno/Documents/RRA_NRM/src/youtube_uploader.py) opera de forma integrada com o pipeline de geração contínua:

1. **Reaproveitamento de Sessão Persistente:** Utiliza um perfil isolado do navegador em `checkpoint/youtube_profile/` (ou importa cookies de `cookies.txt`), mantendo você autenticado de forma contínua sem necessidade de 2FA diário.
2. **Slots Diários Fixos (GMT):** O agendador aloca automaticamente cada novo vídeo nos 4 horários diários estratégicos:
   - **11:00 GMT** (08:00 horário de Brasília)
   - **13:00 GMT** (10:00 horário de Brasília)
   - **15:00 GMT** (12:00 horário de Brasília)
   - **17:00 GMT** (14:00 horário de Brasília)
3. **Limpeza Granular Imediata:** Assim que o upload e agendamento do vídeo é confirmado com sucesso, os arquivos de mídia pesados locais (`final_output.mp4`, pasta `broll/`, áudios temporários) são imediatamente excluídos do disco, liberando espaço sem perder os metadados (`metadata.txt`, `checkpoint.json`, `dissertacao.txt`) que registram o link `https://youtu.be/...`.
4. **Resiliência e Alertas por E-mail:** Se a conexão de internet oscilar ou a sessão do YouTube expirar, o arquivo do vídeo é preservado intacto em disco, a esteira não para e um e-mail de alerta é disparado para `rra.dkch@gmail.com`.

---

## 2. Autenticação Inicial (Login Único)

Antes do primeiro envio, é necessário autenticar a conta do seu canal uma única vez no perfil local do robô:

```bash
scripts\postar_youtube.bat --login
```
*(ou pelo Python diretamente)*:
```bash
py -3.11 -m src.youtube_uploader --login
```

1. Uma janela visível do Google Chrome será aberta apontando para `studio.youtube.com`.
2. Faça login normalmente com o e-mail e senha do canal do YouTube.
3. Assim que o painel principal do YouTube Studio carregar, volte ao terminal e pressione **ENTER**.
4. A sessão será gravada de forma segura no perfil local em `checkpoint/youtube_profile/`.

---

## 3. Publicação e Sincronização de Vídeos (CLI)

### Sincronizar Todo o Backlog de Vídeos Existentes (Recomendado)
Para escanear todos os lotes (Batches 2 a 5) com vídeos prontos acumulados em disco e agendá-los em sequência nos slots GMT liberando espaço de cada um:

```bash
scripts\postar_youtube.bat --sync-backlog
```
*(Adicione `--headless` para executar em segundo plano sem abrir janela)*:
```bash
scripts\postar_youtube.bat --sync-backlog --headless
```

### Agendar Lote Específico
Para agendar todos os vídeos pendentes do Batch 2 nos próximos slots livres:

```bash
scripts\postar_youtube.bat --batch 2
```

### Agendar um Único Vídeo Específico
Para agendar pontualmente o vídeo 0 do lote 2:

```bash
scripts\postar_youtube.bat --video 2 0
```

---

## 4. Operação pelo Streamlit WebUI

No painel web do Minuto Inexplicável (`run.py` ou `iniciar_estudio.bat`):

1. Acesse a aba **📦 Batches & Checkpoints**.
2. Na seção **🚀 Postagem de Shorts no YouTube Studio (Playwright)**:
   - Clique em **🔄 Sincronizar Todo o Backlog (Slots GMT)** para agendar e limpar todo o acervo pendente.
   - Ou selecione um lote individual e clique em **🚀 Agendar Lote Selecionado no YouTube**.

---

## 5. Histórico e Registros de Agendamento

- **Slots Reservados Globais:** O arquivo `checkpoint/youtube_scheduled_slots.json` registra todos os horários GMT alocados e os links correspondentes, evitando colisões de publicação.
- **Histórico do Lote:** Cada lote mantém o registro em `checkpoint/batch_X/youtube_uploads.json`.
- **Diagnóstico Visual:** Em caso de erro de interface, uma captura de tela é gravada automaticamente em `checkpoint/youtube_profile/upload_error_diagnostic.png`.
