# Referência da API: Áudio, Legendas e Renderização (`audio.py`, `subtitles.py`, `render.py`)

Especificação técnica dos módulos de síntese de voz neural, geração de legendas dinâmicas sincronizadas com caixa de realce (*Pill Box*) e renderização final no FFmpeg.

---

## 1. Módulo `audio.py`

### `AudioEngine`

Gerencia a síntese de voz neural multilíngue e a extração de carimbos de tempo em nível de palavra (*Word Boundaries*).

#### Construtor

```python
AudioEngine(voice: str = "pt-BR-AntonioNeural", rate: str = "+25%")
```

- **`voice` (`str`):** Identificador da voz neural do Edge-TTS (padrão: `"pt-BR-AntonioNeural"`).
- **`rate` (`str`):** Taxa de velocidade da narração (padrão: `"+25%"` para dinamismo 1.25x acelerado).

#### Métodos

- **`generate_audio(text: str, output_path: str, output_vtt: str = "", rate: Optional[str] = None) -> Tuple[bool, List[Dict[str, Any]]]`:**
  - Retorna `(sucesso: bool, words_timing: List[Dict])`.
  - Cada item de `words_timing` possui:
    - `'word'` (`str`): A palavra pronunciada.
    - `'start'` (`float`): Instante de início em segundos.
    - `'end'` (`float`): Instante de conclusão em segundos.

---

## 2. Módulo `subtitles.py`

### `convert_words_to_ass`

Converte a lista de palavras temporizadas em um arquivo de legenda `.ass` estilizado com destaque de palavra ativa e caixa envolvente de fundo (*Pill Box*).

```python
convert_words_to_ass(
    words_timing: List[Dict[str, Any]],
    output_ass_path: str,
    primary_color: str = "FFFFFF",
    highlight_color: str = "FFE500"
) -> bool
```

- **`words_timing` (`List[Dict]`):** Lista de eventos de limite de palavra com timestamps.
- **`output_ass_path` (`str`):** Caminho onde o arquivo `.ass` será gravado.
- **`primary_color` (`str`):** Cor hexadecimal do texto base (ex: `"FFFFFF"`).
- **`highlight_color` (`str`):** Cor hexadecimal da palavra em foco no momento da pronúncia (ex: `"FFE500"`).

---

## 3. Módulo `render.py`

### `assemble_multi_scene_video`

Concatena os múltiplos clipes de vídeo 9:16 previamente auditados, combina com a trilha de áudio da narração e queima as legendas dinâmicas no vídeo através do filtro `ass` do FFmpeg.

```python
assemble_multi_scene_video(
    clip_paths: List[str],
    audio_path: str,
    ass_path: str,
    output_path: str,
    status_callback = None
) -> Tuple[bool, str]
```

#### Pipeline de Filtros no FFmpeg:
1. **Concatenação de Cenas:**
   ```bash
   ffmpeg -f concat -safe 0 -i scenes_concat.txt -vf "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,setsar=1" -c:v libx264 -crf 18 -preset fast combined.mp4
   ```
2. **Mixagem de Áudio e Queima de Legendas:**
   ```bash
   ffmpeg -i combined.mp4 -i audio.mp3 -vf "ass='subtitles.ass'" -c:v libx264 -crf 18 -preset fast -c:a aac -b:a 192k -shortest output.mp4
   ```
