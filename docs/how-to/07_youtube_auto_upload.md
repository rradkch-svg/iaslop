# Como Autenticar e Postar Vídeos no YouTube Studio Automaticamente

Este guia ensina como configurar e utilizar o módulo de upload automático via navegador web (Playwright / Chrome) para publicar ou agendar os Shorts concluídos do Minuto Inexplicável Studio.

---

## 1. Visão Geral da Automação

O módulo [`src/youtube_uploader.py`](file:///C:/Users/Aluno/Documents/RRA_NRM/src/youtube_uploader.py) executa os seguintes passos diretamente no YouTube Studio:

1. **Reaproveitamento de Sessão Persistente:** Utiliza um perfil isolado do navegador em `checkpoint/youtube_profile/` (ou importa cookies de `cookies.txt`), mantendo você autenticado de forma contínua sem necessidade de 2FA diário.
2. **Carregamento Automático de Metadados:** Lê o arquivo `metadata.txt` e o `checkpoint.json` de cada vídeo do lote para preencher:
   - Título otimizado para Shorts (com teto de 100 caracteres e tag `#Shorts`).
   - Descrição factual com créditos e hashtags virais.
   - Tags de indexação e descoberta.
   - Restrição de audiência (marcação obrigatória de *Não é conteúdo para crianças*).
3. **Prevenção de Duplicidade:** Mantém o histórico em `checkpoint/batch_X/youtube_uploads.json`. Se um vídeo já foi postado com sucesso, ele é ignorado em execuções subsequentes.
4. **Agendamento Escalonado:** Permite definir um intervalo em horas entre cada publicação para evitar cansar o algoritmo do YouTube Shorts.

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
4. A sessão será gravada de forma criptografada e segura no perfil isolado local.

---

## 3. Publicação de Lotes (CLI)

### Publicar Todos os Vídeos Concluídos de um Lote

Para postar imediatamente como público todos os vídeos pendentes do Batch 1:

```bash
scripts\postar_youtube.bat --batch 1
```

### Agendar Publicações com Espaçamento Programado

Para agendar 1 vídeo a cada 3 horas (ideal para manter consistência no feed dos Shorts):

```bash
scripts\postar_youtube.bat --batch 1 --schedule-hours 3.0
```

### Postar em Modo Não-Listado ou Privado (Para Revisão Prévia)

```bash
scripts\postar_youtube.bat --batch 1 --visibility UNLISTED
```

---

## 4. Execução em Segundo Plano (Headless)

Após realizar o login inicial, a automação pode rodar silenciosamente sem abrir janelas na tela:

```bash
scripts\postar_youtube.bat --batch 1 --headless
```

---

## 5. Histórico e Logs de Envio

Cada lote mantém um arquivo de auditoria em `checkpoint/batch_X/youtube_uploads.json`:

```json
{
  "video_0": {
    "success": true,
    "title": "A Cidade Fantasma de Centralia e os Incêndios Subterrâneos Perpétuos #Shorts",
    "url": "https://youtu.be/exemplo123",
    "published_at": "2026-09-15T10:30:00",
    "visibility": "PUBLIC"
  }
}
```

Caso ocorra algum erro durante o preenchimento, uma captura de tela de diagnóstico é salva automaticamente em `checkpoint/youtube_profile/upload_error_diagnostic.png` para inspeção visual imediata.
