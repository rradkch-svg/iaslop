# Como Configurar e Enviar Batches Compactados (.zip) por E-mail

Este guia ensina como configurar e utilizar o sistema automático de empacotamento em formato ZIP e transmissão por e-mail para cada lote de vídeos concluído no Minuto Inexplicável Studio.

---

## 1. Visão Geral do Fluxo de Envio

A cada batch de 10 vídeos concluído com sucesso pelo `AutoPipeline`, o sistema executa automaticamente os seguintes passos:

1. **Varredura e Auditoria do Batch:** Coleta métricas de duração, tamanho de arquivo em disco, títulos, ganchos narrativos (*hooks*), tags do YouTube e status dos 10 vídeos.
2. **Compactação Inteligente em ZIP:** Cria o pacote `batch_X.zip` na pasta do lote contendo todos os vídeos Full HD (`final_output.mp4`), metadados (`metadata.txt`), dissertações completas (`dissertacao.txt`), marcações temporais (`checkpoint.json`), legendas estritas (`subtitles.ass`) e narrações neurais (`audio.mp3`), omitindo mídias temporárias e b-roll bruto.
3. **Gerenciamento do Limite de Anexos (25 MB do Gmail):**
   - Se o arquivo ZIP estiver dentro do teto seguro ($\le 24\text{ MB}$), ele é anexado diretamente ao e-mail.
   - Caso o pacote de vídeos ultrapasse o limite de anexo de provedores SMTP (lotes com 10 vídeos Full HD costumam somar centenas de megabytes), o sistema salva o arquivo `batch_X.zip` completo no computador e cria automaticamente um pacote leve de metadados (`batch_X_metadata.zip`, $\lt 2\text{ MB}$) para anexar ao e-mail, registrando no corpo da mensagem o caminho absoluto da gravação em disco.
4. **Envio Seguro via SMTPS (Porta 465):** Estabelece conexão direta criptografada com `smtp.gmail.com:465` (SSL nativo, compatível com redes restritas) e despacha a mensagem formatada em HTML moderno e texto puro.

---

## 2. Configuração de Credenciais no `.env`

Para que o envio automático via Gmail funcione sem intervenção manual, obtenha uma **Senha de App** do Google:

### Passo a Passo para Gerar a Senha de App do Gmail

1. Acesse sua conta Google e certifique-se de que a **Verificação em duas etapas** está ativada.
2. Acesse: [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
3. No campo "Nome do app", digite `Minuto Inexplicavel` e clique em **Criar**.
4. Copie a senha de 16 caracteres gerada (exemplo: `abcd efgh ijkl mnop`).

### Variáveis no `.env`

No arquivo `.env` na raiz do projeto, adicione ou configure as seguintes variáveis:

```ini
# Destinatário padrão das notificações e pacotes ZIP
EMAIL_RECIPIENT=rra.dkch@gmail.com

# Servidor e Porta SMTP (Porta 465 SSL recomendada para redes corporativas/acadêmicas)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465

# Credenciais de Envio do Gmail
SMTP_USER=seu_email@gmail.com
SMTP_PASSWORD=sua_senha_de_app_16_caracteres

# Teto máximo de anexo direto (em MB)
EMAIL_MAX_ATTACHMENT_MB=24.0
```

> [!NOTE]
> Se `SMTP_USER` ou `SMTP_PASSWORD` não estiverem configurados, o pipeline continuará gerando e salvando os arquivos ZIP normalmente no disco, exibindo no terminal o caminho local do arquivo sem travar o processamento.

---

## 3. Teste Rápido de Conectividade SMTP

Você pode verificar a conectividade com o servidor SMTP executando:

```bash
python -m src.email_service --test
```

Saída esperada em conexões saudáveis:

```text
🔍 Testando conexão com smtp.gmail.com:465...
✅ Conexão SSL com smtp.gmail.com:465 estabelecida com sucesso!
```

---

## 4. Compactação e Envio Sob Demanda (CLI)

Para compactar e disparar o e-mail de um lote específico já finalizado (por exemplo, `batch_1` ou `batch_2`):

```bash
# Compactar e enviar por e-mail para o destinatário padrão:
python -m src.email_service --batch 1

# Apenas gerar o arquivo ZIP localmente sem disparar o e-mail:
python -m src.email_service --batch 1 --zip-only

# Enviar para um e-mail alternativo:
python -m src.email_service --batch 1 --recipient outro_email@gmail.com
```

---

## 5. Operação pelo Streamlit WebUI

No painel web do Minuto Inexplicável (`run.py` ou `start_studio.bat`):

1. Acesse a aba **📦 Batches & Checkpoints**.
2. Na seção **📧 Envio Automático de Batches (ZIP por E-mail)**:
   - Verifique o endereço de destino configurado e o status das credenciais SMTP.
   - Selecione o índice do lote desejado e clique em **📦 Compactar & Enviar Batch**.
