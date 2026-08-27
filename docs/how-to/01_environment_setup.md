# Guia Prático: Configuração do Ambiente e Dependências (Python 3.11+)

Este guia orienta a instalação e configuração de todos os binários, interpretadores e bibliotecas necessários para reconstruir e executar a plataforma de geração autônoma em qualquer ambiente Windows.

---

## 1. Instalação do Interpretador Python 3.11+

Recomenda-se utilizar Python 3.11 (64-bit) para compatibilidade plena com os tipos modernos e a nova SDK do Google GenAI.

### Instalação via WinGet no Windows

```powershell
winget install --id Python.Python.3.11
```

Verifique a instalação:

```powershell
py -3.11 --version
```

---

## 2. Instalação do FFmpeg e FFprobe com Suporte a Libass

O FFmpeg e o FFprobe são obrigatórios para:
- Extração de frames para auditoria visual multimodal (`ReviewerAgent`).
- Validação empírica da duração real dos arquivos antes do corte (`get_video_duration`).
- Recorte proporcional 9:16 (*Pan & Scan*) com interpolação Lanczos e CRF 18.
- Composição e queima de legendas `.ass` na trilha de vídeo final.

### Instalação via WinGet

Execute no terminal do PowerShell:

```powershell
winget install Gyan.FFmpeg
```

O pipeline detecta automaticamente o executável do FFmpeg instalado pelo WinGet em `~\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\*\bin\ffmpeg.exe`.

---

## 3. Instalação dos Pacotes Python

Atualize o instalador de pacotes e instale as dependências listadas em `requirements.txt`:

```powershell
py -3.11 -m pip install --upgrade pip setuptools wheel
py -3.11 -m pip install -r requirements.txt
```

As dependências principais incluem:
- `google-genai>=2.20.0`: Nova SDK oficial do Gemini com suporte a streaming, multimodal e controle de timeout HTTP.
- `streamlit>=1.62.0`: Interface web interativa com gestão de sessões.
- `edge-tts>=6.1.12`: Síntese de voz neural multilíngue com timestamps por palavra.
- `yt-dlp>=2025.1.26`: Motor de busca e download de transmissões de vídeo em alta definição.
- `pillow>=10.4.0`: Processamento e extração de imagens de quadros.
- `psutil>=5.9.0`: Monitoramento de processos e telemetria de recursos.
- `python-dotenv`: Carregamento automático de credenciais de ambiente.

---

## 4. Configuração das Variáveis de Ambiente (`.env`)

Crie ou edite o arquivo `.env` na raiz do projeto contendo sua chave de acesso à API do Google Gemini:

```env
GEMINI_API_KEY=sua_chave_gemini_aqui
```

---

## 5. Validação da Instalação

Execute o script de verificação unitária com Python 3.11:

```powershell
py -3.11 test_backend.py
```

Se todos os 6 estágios emitirem `✅ PASSOU`, o ambiente está validado e pronto para produção.
