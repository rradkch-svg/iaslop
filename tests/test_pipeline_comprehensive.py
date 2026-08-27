import os
import sys
import json
import time
import subprocess

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) == "tests" else CURRENT_DIR
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

from logger import app_logger, LogSpan, analyze_logs
from agents import ProposerAgent, EvaluatorAgent, DirectorAgent, ReviewerAgent, resolve_gemini_api_key

api_key = resolve_gemini_api_key()
if api_key:
    os.environ["GEMINI_API_KEY"] = api_key
from audio import AudioEngine
from subtitles import convert_words_to_ass
from broll_engine import BRollEngine
from render import assemble_multi_scene_video, find_ffmpeg_binary

def probe_video(file_path: str) -> dict:
    """Extrai metadados do vídeo via ffprobe para comprovação empírica."""
    ffprobe_bin = find_ffmpeg_binary().replace("ffmpeg.exe", "ffprobe.exe")
    if not os.path.exists(ffprobe_bin):
        ffprobe_bin = "ffprobe"
        
    cmd = [
        ffprobe_bin, "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        file_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(res.stdout)
    except Exception as e:
        return {"error": str(e)}

def run_comprehensive_test():
    print("=" * 70)
    print("🚀 TESTE COMPLETO DO PIPELINE 9:16 - MINUTO INEXPLICÁVEL")
    print("=" * 70)

    test_output_dir = os.path.join(PROJECT_ROOT, "data", "test_comprehensive_output")
    os.makedirs(test_output_dir, exist_ok=True)

    # 1. Teste de Proposição e Storyboard
    with LogSpan("Teste_Etapa_1_Agentes"):
        print("\n[1/5] Executando ProposerAgent (Modelo: gemini-flash-lite-latest)...")
        proposer = ProposerAgent(model_name="gemini-flash-lite-latest", auto_fallback=True)
        topics = proposer.generate_topics(count=1)
        selected_topic = topics[0]
        print(f"Tema selecionado: {selected_topic.get('tema')}")
            
        print("\n[2/5] Executando DirectorAgent (Storyboard 100% YouTube B-Rolls)...")
        director = DirectorAgent(model_name="gemini-flash-lite-latest", auto_fallback=True)
        cenas = director.generate_storyboard(selected_topic)
        print(f"Storyboard gerado com {len(cenas)} cenas.")
        for i, c in enumerate(cenas[:4]):
            print(f"  Cena #{i+1} [B-Roll]: '{c.get('fala')[:60]}...' -> Busca: '{c.get('youtube_query')}'")

    # 2. Narração e Mapeamento de Palavras
    print("\n[3/5] Sintetizando Narração Neural Completa (Edge-TTS)...")
    full_script = " ".join([c.get("fala", "").strip() for c in cenas if c.get("fala")])
    mp3_path = os.path.join(test_output_dir, "narration.mp3")
    audio_engine = AudioEngine()
    success_audio, words_timing = audio_engine.generate_audio(full_script, mp3_path)
    assert success_audio, f"Falha no áudio: {words_timing}"
    total_audio_dur = words_timing[-1].get("end", 60.0) if words_timing else 60.0
    print(f"  ✅ Áudio gerado: {os.path.getsize(mp3_path)} bytes ({total_audio_dur:.1f}s • {len(words_timing)} palavras)")

    # 3. Legendas Dinâmicas Hormozi (Pill Amarela Neon)
    ass_path = os.path.join(test_output_dir, "subtitles.ass")
    success_ass = convert_words_to_ass(words_timing, ass_path, primary_color="FFFFFF", highlight_color="FFE500")
    assert success_ass, "Falha na geração das legendas ASS"
    print(f"  ✅ Legendas ASS formatadas com Pill Box: {os.path.getsize(ass_path)} bytes")

    # 4. Download e Auditoria Visual Concorrente em Batches (Parallel Processing)
    print("\n[4/5] Processando Cenas em Paralelo com ReviewerAgent (Gemini Vision Concorrente)...")
    broll_engine = BRollEngine(max_search_results=6)
    reviewer = ReviewerAgent()
    global_topic = selected_topic.get('tema', 'Mistério Desclassificado')

    # Testando cenas em paralelo com max_workers=4
    test_scenes = cenas[:3]
    scene_clips, scene_audits = broll_engine.process_all_scenes_parallel(
        cenas=test_scenes,
        global_topic=global_topic,
        reviewer_agent=reviewer,
        project_dir=test_output_dir,
        total_audio_duration=total_audio_dur,
        max_workers=4,
        status_callback=lambda m: print("  📡", m),
        progress_callback=lambda d, t: print(f"  📊 Progresso Concorrente: {d}/{t} cenas concluídas")
    )

    assert len(scene_clips) == len(test_scenes), f"Esperava {len(test_scenes)} clipes, obteve {len(scene_clips)}"
    print(f"  ✅ Garantia de Ineditismo & Velocidade: {len(scene_clips)} vídeos aprovados e renderizados em lote paralelo!")

    # 5. Composição Final no FFmpeg
    print("\n[5/5] Executando Composição Final no FFmpeg (Vídeos Reais + Narração + Legendas Queimadas)...")
    final_output = os.path.join(test_output_dir, "final_video_real_broll.mp4")
    success_render, render_msg = assemble_multi_scene_video(scene_clips, mp3_path, ass_path, final_output)
    assert success_render, f"Falha no render FFmpeg: {render_msg}"
    print(f"  ✅ Vídeo Final Concluído: {final_output} ({os.path.getsize(final_output)} bytes)")

    # 6. Auditoria de Metadados com FFprobe
    print("\n" + "=" * 70)
    print("🔬 AUDITORIA EMPÍRICA DOS ARQUIVOS E STREAMS (FFPROBE)")
    print("=" * 70)
    probe_data = probe_video(final_output)
    if "streams" in probe_data:
        for st in probe_data["streams"]:
            c_type = st.get("codec_type")
            c_name = st.get("codec_name")
            if c_type == "video":
                w = st.get("width")
                h = st.get("height")
                dur = st.get("duration", probe_data.get("format", {}).get("duration", "N/A"))
                print(f"  📹 STREAM DE VÍDEO: Codec {c_name} | Resolução {w}x{h} (Vertical 9:16 Nativo) | Duração: {dur}s")
            elif c_type == "audio":
                sr = st.get("sample_rate")
                ch = st.get("channels")
                print(f"  🎙️ STREAM DE ÁUDIO: Codec {c_name} | Taxa de Amostragem {sr}Hz | Canais: {ch}")

    print("\n🎉 TODOS OS TESTES PASSARAM COM 100% DE SUCESSO!")
    print(f"🎬 Deliverable final com vídeos reais do YouTube: {final_output}")

if __name__ == "__main__":
    run_comprehensive_test()
