import os
import re
import sys
import time
import json
import random
import signal
import threading
from typing import Dict, Any, List, Optional, Tuple

# Força UTF-8 nos terminais Windows para exibição de emojis e logs limpos
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

import atexit
try:
    from .logger import app_logger, LogSpan, record_throttling
    from .checkpoint_manager import CheckpointManager, VIDEOS_PER_BATCH
    from .agents import (
        ProposerAgent,
        EvaluatorAgent,
        DissertationAgent,
        DirectorAgent,
        ReviewerAgent,
        SemanticAuditorAgent,
        DEFAULT_FALLBACK_MODELS,
        resolve_gemini_api_key,
        resolve_gemini_api_keys,
        validate_gemini_api_connection,
        save_video_metadata_file
    )
    from .pronunciation import PronunciationEngine, DEFAULT_PRONUNCIATION_ENGINE
    from .algorithm_memory import AlgorithmMemorySystem, DEFAULT_ALGORITHM_MEMORY
    from .audio import AudioEngine, FALLBACK_VOICES, VOICE_PROSODY_PRESETS
    from .broll_engine import BRollEngine, find_ffmpeg_binary
    from .subtitles import convert_words_to_ass
    from .render import assemble_multi_scene_video
    from .bgm_engine import BGMEngine, DEFAULT_BGM_ENGINE
    from .sfx_engine import SFXEngine, DEFAULT_SFX_ENGINE
    from .video_enhancer import VideoResolutionEnhancer, DEFAULT_VIDEO_ENHANCER
except ImportError:
    from logger import app_logger, LogSpan, record_throttling
    from checkpoint_manager import CheckpointManager, VIDEOS_PER_BATCH
    from agents import (
        ProposerAgent,
        EvaluatorAgent,
        DissertationAgent,
        DirectorAgent,
        ReviewerAgent,
        SemanticAuditorAgent,
        DEFAULT_FALLBACK_MODELS,
        resolve_gemini_api_key,
        resolve_gemini_api_keys,
        validate_gemini_api_connection,
        save_video_metadata_file
    )
    from pronunciation import PronunciationEngine, DEFAULT_PRONUNCIATION_ENGINE
    from algorithm_memory import AlgorithmMemorySystem, DEFAULT_ALGORITHM_MEMORY
    from audio import AudioEngine, FALLBACK_VOICES, VOICE_PROSODY_PRESETS
    from broll_engine import BRollEngine, find_ffmpeg_binary
    from subtitles import convert_words_to_ass
    from render import assemble_multi_scene_video
    from bgm_engine import BGMEngine, DEFAULT_BGM_ENGINE
    from sfx_engine import SFXEngine, DEFAULT_SFX_ENGINE
    from video_enhancer import VideoResolutionEnhancer, DEFAULT_VIDEO_ENHANCER



# Lock do SO e sincronização com Watchdog
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK_FILE = os.path.join(PROJECT_ROOT, "checkpoint", ".pipeline.lock")
PIPELINE_LOCK_HANDLE = None

def acquire_pipeline_lock() -> bool:
    global PIPELINE_LOCK_HANDLE
    lock_dir = os.path.dirname(LOCK_FILE)
    os.makedirs(lock_dir, exist_ok=True)
    my_pid = os.getpid()

    try:
        PIPELINE_LOCK_HANDLE = open(LOCK_FILE, "a+", encoding="utf-8")
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(PIPELINE_LOCK_HANDLE.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(PIPELINE_LOCK_HANDLE.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        
        PIPELINE_LOCK_HANDLE.seek(0)
        PIPELINE_LOCK_HANDLE.truncate()
        PIPELINE_LOCK_HANDLE.write(str(my_pid))
        PIPELINE_LOCK_HANDLE.flush()
        return True
    except (IOError, OSError, PermissionError) as e:
        app_logger.warning(f"[AutoPipeline] Outra instância ativa já detém o lock exclusivo: {e}")
        if PIPELINE_LOCK_HANDLE:
            try:
                PIPELINE_LOCK_HANDLE.close()
            except Exception:
                pass
            PIPELINE_LOCK_HANDLE = None
        return False


def release_pipeline_lock():
    global PIPELINE_LOCK_HANDLE
    if PIPELINE_LOCK_HANDLE:
        try:
            if sys.platform == "win32":
                import msvcrt
                try:
                    PIPELINE_LOCK_HANDLE.seek(0)
                    msvcrt.locking(PIPELINE_LOCK_HANDLE.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
            else:
                import fcntl
                try:
                    fcntl.flock(PIPELINE_LOCK_HANDLE.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
            PIPELINE_LOCK_HANDLE.close()
        except Exception:
            pass
        PIPELINE_LOCK_HANDLE = None
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except Exception:
            pass

# Flag de encerramento gracioso (Ctrl+C / SIGINT)
RUNNING = True

def handle_sigint(signum, frame):
    global RUNNING
    if RUNNING:
        print("\n\n⚠️ SINAL DE INTERRUPÇÃO DETECTADO (Ctrl+C)!")
        print("💾 Finalizando a operação atômica atual e persistindo o checkpoint no disco...")
        RUNNING = False
    else:
        print("\nForçando encerramento imediato...")
        release_pipeline_lock()
        sys.exit(1)

signal.signal(signal.SIGINT, handle_sigint)
try:
    signal.signal(signal.SIGTERM, handle_sigint)
except Exception:
    pass

class AutoPipelineRunner:

    """
    Orquestrador Autônomo e Resiliente de Produção de Vídeos em Lote (9:16 Vertical).
    Garante:
    1. Geração e verificação semântica profunda de temas (sem duplicatas em essência).
    2. Pesquisa factual densa via DissertationAgent (Fase 1).
    3. Destilação em roteiro investigativo hipnótico via DirectorAgent (Fase 2).
    4. Narração com pronúncia fonética precisa para termos estrangeiros via Edge-TTS pt-BR.
    5. Recuperação imediata de checkpoints em caso de interrupção ou queda de energia.
    """

    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        voice: str = "pt-BR-AntonioNeural",
        rate: str = "+25%",
        pitch: str = "+0Hz",
        volume: str = "+0%",
        model_name: str = "gemini-flash-lite-latest",
        auto_fallback: bool = True,
        auto_cooldown: bool = True,
        videos_per_batch: int = VIDEOS_PER_BATCH,
        fast_mode: bool = False,
        enable_bgm: bool = True,
        bgm_volume: float = 0.12,
        enable_sfx: bool = True,
        sfx_volume: float = 0.35
    ):
        self.checkpoint_mgr = CheckpointManager(root_dir=checkpoint_dir, videos_per_batch=videos_per_batch)
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.videos_per_batch = videos_per_batch
        self.fast_mode = fast_mode
        self.enable_bgm = enable_bgm
        self.bgm_volume = bgm_volume
        self.enable_sfx = enable_sfx
        self.sfx_volume = sfx_volume

        # Garante a chave do Gemini
        api_key = resolve_gemini_api_key()
        if api_key:
            os.environ["GEMINI_API_KEY"] = api_key

        # Instanciação dos motores reutilizáveis com ritmo acelerado 1.25x, pronúncia, BGM, SFX e HD Enhancer
        self.pronunciation_engine = DEFAULT_PRONUNCIATION_ENGINE
        self.bgm_engine = DEFAULT_BGM_ENGINE or BGMEngine()
        self.sfx_engine = DEFAULT_SFX_ENGINE or SFXEngine()
        self.video_enhancer = DEFAULT_VIDEO_ENHANCER or VideoResolutionEnhancer()
        self.audio_engine = AudioEngine(
            voice=self.voice,
            rate=self.rate,
            pitch=self.pitch,
            volume=self.volume,
            pronunciation_engine=self.pronunciation_engine
        )


        self.broll_engine = BRollEngine(max_search_results=6)
        self.reviewer_agent = ReviewerAgent(
            model_name=self.model_name,
            auto_fallback=self.auto_fallback,
            auto_cooldown=self.auto_cooldown
        )
        self.proposer_agent = ProposerAgent(
            model_name=self.model_name,
            auto_fallback=self.auto_fallback,
            auto_cooldown=self.auto_cooldown
        )
        self.dissertation_agent = DissertationAgent(
            model_name=self.model_name,
            auto_fallback=self.auto_fallback,
            auto_cooldown=self.auto_cooldown
        )
        self.director_agent = DirectorAgent(
            model_name=self.model_name,
            auto_fallback=self.auto_fallback,
            auto_cooldown=self.auto_cooldown
        )
        self.semantic_auditor = SemanticAuditorAgent(
            model_name=self.model_name,
            auto_fallback=self.auto_fallback,
            auto_cooldown=self.auto_cooldown
        )

    def print_banner(self):
        print("=" * 75)
        print("🔮 MINUTO INEXPLICÁVEL - GERAÇÃO E RECUPERAÇÃO AUTOMÁTICA (BATCHES 9:16)")
        print("=" * 75)
        print(f"📁 Pasta de Checkpoints : {self.checkpoint_mgr.root_dir}")
        print(f"📦 Vídeos por Batch    : {self.videos_per_batch}")
        print(f"🎙️ Voz Neural TTS      : {self.voice} ({self.rate})")
        print(f"🧠 Modelo de IA Primário: {self.model_name}")
        keys_pool = resolve_gemini_api_keys()
        print(f"🔑 Pool de Chaves Gemini : {len(keys_pool)} chave(s) detectada(s)")
        print("=" * 75)

    def process_single_video(self, batch_idx: int, video_idx: int) -> bool:
        """
        Executa ou retoma todas as 6 etapas atômicas de produção de um único vídeo.
        Salva o checkpoint imediatamente após a conclusão de cada etapa.
        """
        b_name = f"batch_{batch_idx}"
        v_name = f"video_{video_idx}"
        v_dir = self.checkpoint_mgr.get_video_dir(batch_idx, video_idx)
        ckpt = self.checkpoint_mgr.load_video_checkpoint(batch_idx, video_idx)

        print(f"\n🎬 Processando [{b_name}/{v_name}] em: {v_dir}")

        with LogSpan(f"process_single_video_{b_name}_{v_name}"):
            res_stage, ckpt = self.checkpoint_mgr.determine_video_resume_stage(batch_idx, video_idx)
            stage = ckpt.get("status", res_stage)

            if stage in ("COMPLETED", "RENDER_COMPLETED"):
                final_v = os.path.join(v_dir, ckpt.get("final_video", "final_output.mp4"))
                if not os.path.exists(final_v):
                    final_v = os.path.join(v_dir, ckpt.get("final_video_file", "final_video.mp4"))
                if os.path.exists(final_v) and os.path.getsize(final_v) > 1000:
                    print(f"  ✨ Vídeo já concluído e renderizado anteriormente: {final_v}")
                    return True
                else:
                    print("  ⚠️ Checkpoint indicava RENDER_COMPLETED, mas o arquivo de vídeo não existe. Re-executando render...")
                    stage = "RENDER_FINAL"

            # ETAPA 1: GERAÇÃO E ESCOLHA DE TEMA INÉDITO (PROPOSER AGENT + BLACKLIST SEMÂNTICA)
            if stage in ("NOT_STARTED", "PENDING", "TOPIC_PENDING", "GENERATE_TOPIC") or not ckpt.get("topic") or not ckpt.get("topic", {}).get("tema"):
                print("  🔍 [1/6] Gerando e auditando tema inédito em essência...")

                blacklist_titles = self.checkpoint_mgr.get_blacklist_titles()
                
                max_topic_attempts = 4
                selected_topic = None

                for attempt in range(max_topic_attempts):
                    try:
                        proposed_topics = self.proposer_agent.generate_topics(
                            count=5,
                            blacklist=blacklist_titles,
                            status_callback=lambda m: print(f"    📡 {m}")
                        )
                        
                        if isinstance(proposed_topics, list) and proposed_topics:
                            for candidate in proposed_topics:
                                t_name = candidate.get("tema", "")
                                is_blk, blk_reason = self.checkpoint_mgr.is_in_blacklist(
                                    candidate,
                                    threshold=0.60,
                                    ai_auditor=self.semantic_auditor
                                )
                                if not is_blk:
                                    selected_topic = candidate
                                    break
                                else:
                                    print(f"    ⚠️ Tema descartado pela Blacklist (Essência Repetida): '{t_name}' ({blk_reason})")
                            
                            if selected_topic:
                                break
                    except Exception as e:
                        app_logger.warning(f"[AutoPipeline] Erro ao propor tema (tentativa {attempt+1}/{max_topic_attempts}): {str(e)}")
                        print(f"    ⚠️ Tentativa {attempt+1}/{max_topic_attempts} de gerar tema falhou: {str(e)}")
                        time.sleep(3)

                if not selected_topic:
                    err_msg = "Não foi possível gerar um tema inédito via IA após múltiplas tentativas. Pausando sem gerar conteúdo genérico."
                    print(f"  ❌ {err_msg}")
                    app_logger.error(f"[AutoPipeline] {err_msg}")
                    ckpt["error"] = err_msg
                    self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                    return False

                print(f"  🎯 TEMA APROVADO: \"{selected_topic.get('tema')}\"")
                ckpt["topic"] = selected_topic
                ckpt["status"] = "TOPIC_READY"
                save_video_metadata_file(v_dir, selected_topic)
                ckpt["metadata_file"] = "metadata.txt"
                self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                
                # Registra IMEDIATAMENTE na Blacklist com perfil semântico
                self.checkpoint_mgr.add_to_blacklist(selected_topic, b_name, v_name)
                stage = "GENERATE_DISSERTATION"

            if not RUNNING:
                return False

            # ETAPA 1.5: DISSERTAÇÃO FACTUAL PROFUNDA (DISSERTATION AGENT)
            if stage in ("GENERATE_DISSERTATION", "TOPIC_READY") or (stage in ("GENERATE_STORYBOARD", "STORYBOARD_PENDING") and "dissertation" not in ckpt):
                print("  🔬 [1.5/6] Construindo dissertação documental profunda e factual (DissertationAgent)...")
                topic = ckpt.get("topic", {})
                try:
                    dissertacao_data = self.dissertation_agent.generate_dissertation(
                        topic,
                        status_callback=lambda m: print(f"    🔬 {m}")
                    )
                    ckpt["dissertation"] = dissertacao_data
                    ckpt["status"] = "DISSERTATION_READY"
                    
                    dissertacao_file = os.path.join(v_dir, "dissertacao.txt")
                    with open(dissertacao_file, "w", encoding="utf-8") as df:
                        df.write(f"ENTIDADE: {dissertacao_data.get('entidade_principal')}\n\n")
                        df.write(f"DADOS QUANTITATIVOS:\n{json.dumps(dissertacao_data.get('dados_quantitativos', {}), ensure_ascii=False, indent=2)}\n\n")
                        df.write(f"ANOMALIA / ENIGMA CENTRAL:\n{dissertacao_data.get('anomalia_ou_enigma_central')}\n\n")
                        df.write(f"TEORIAS E EVIDÊNCIAS:\n{dissertacao_data.get('teorias_e_evidencias')}\n\n")
                        df.write(f"DISSERTAÇÃO COMPLETA:\n{dissertacao_data.get('dissertacao_completa')}\n")
                    print(f"  📄 Dissertação factual gravada em: {dissertacao_file}")
                    self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                    stage = "GENERATE_STORYBOARD"
                except Exception as e:
                    app_logger.warning(f"[AutoPipeline] Falha na dissertação ({str(e)}). Prosseguindo com síntese direta.")
                    ckpt["dissertation"] = {"dissertacao_completa": f"{topic.get('hook', '')} {topic.get('explicacao_tecnica', '')}"}
                    stage = "GENERATE_STORYBOARD"

            if not RUNNING:
                return False

            # ETAPA 2: ROTEIRIZAÇÃO E STORYBOARD (DIRECTOR AGENT)
            if stage in ("GENERATE_STORYBOARD", "DISSERTATION_READY", "STORYBOARD_PENDING"):
                print("  ✍️ [2/6] Gerando roteiro investigativo e plano de cortes (DirectorAgent)...")
                topic = ckpt.get("topic", {})
                dissertacao_info = ckpt.get("dissertation")
                try:
                    cenas = self.director_agent.generate_storyboard(
                        topic,
                        dissertacao_data=dissertacao_info,
                        status_callback=lambda m: print(f"    ✍️ {m}")
                    )
                    if not cenas or len(cenas) < 3:
                        raise Exception("Storyboard retornado com menos de 3 cenas.")
                    
                    ckpt["storyboard"] = cenas
                    ckpt["status"] = "STORYBOARD_READY"
                    self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                    print(f"  ✅ Storyboard concluído com {len(cenas)} cenas planejadas!")
                    stage = "GENERATE_AUDIO"
                except Exception as e:
                    app_logger.error(f"[AutoPipeline] Falha no Storyboard: {str(e)}")
                    ckpt["error"] = f"Falha no Storyboard: {str(e)}"
                    self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                    return False

            if not RUNNING:
                return False

            # ETAPA 3: SÍNTESE DE VOZ NEURAL (EDGE-TTS COM ADAPTAÇÃO FONÉTICA)
            if stage in ("GENERATE_AUDIO", "STORYBOARD_READY", "AUDIO_PENDING"):
                print(f"  🎙️ [3/6] Sintetizando narração neural ({self.voice} - {self.rate})...")
                cenas = ckpt.get("storyboard", [])
                full_script = " ".join([c.get("fala", "").strip() for c in cenas if c.get("fala")])
                if not full_script:
                    topic = ckpt.get("topic", {})
                    full_script = f"{topic.get('hook', '')} {topic.get('explicacao_tecnica', '')}"

                audio_path = os.path.join(v_dir, "audio.mp3")
                success_audio, words_timing = self.audio_engine.generate_audio(full_script, audio_path)
                
                if not success_audio:
                    err_msg = f"Falha no áudio: {words_timing}"
                    app_logger.error(f"[AutoPipeline] {err_msg}")
                    ckpt["error"] = err_msg
                    self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                    return False

                total_audio_dur = words_timing[-1].get("end", 60.0) if words_timing else 60.0
                ckpt["audio_file"] = "audio.mp3"
                ckpt["audio_duration"] = total_audio_dur
                ckpt["words_timing"] = words_timing
                ckpt["status"] = "AUDIO_READY"
                self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                print(f"  ✅ Áudio neural sintetizado ({total_audio_dur:.1f}s)!")
                stage = "PROCESS_SUBTITLES"

            if not RUNNING:
                return False

            # ETAPA 4: GERAÇÃO DE LEGENDAS DINÂMICAS ASS (ESTILO SHORT VIRAL)
            if stage in ("PROCESS_SUBTITLES", "GENERATE_SUBTITLES", "AUDIO_READY", "SUBTITLES_PENDING"):
                print("  📝 [4/6] Gerando legendas dinâmicas animadas (ASS)...")
                words_timing = ckpt.get("words_timing", [])
                ass_path = os.path.join(v_dir, "subtitles.ass")
                
                try:
                    convert_words_to_ass(words_timing, ass_path)
                    ckpt["ass_file"] = "subtitles.ass"
                    ckpt["status"] = "SUBTITLES_READY"
                    self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                    print("  ✅ Legendas ASS formatadas e salvas!")
                    stage = "FETCH_BROLL"
                except Exception as e:
                    app_logger.error(f"[AutoPipeline] Falha nas legendas ASS: {str(e)}")
                    ckpt["error"] = f"Falha nas legendas: {str(e)}"
                    self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                    return False

            if not RUNNING:
                return False

            # ETAPA 5: DOWNLOAD E AUDITORIA DE B-ROLL DO YOUTUBE
            if stage in ("FETCH_BROLL", "PROCESS_SCENES", "SUBTITLES_READY", "BROLL_PENDING"):
                print("  🎥 [5/6] Baixando e auditando B-Roll histórico do YouTube...")
                cenas = ckpt.get("storyboard", [])
                broll_dir = os.path.join(v_dir, "broll")
                os.makedirs(broll_dir, exist_ok=True)
                
                scenes_media = ckpt.get("scenes_media", {})
                
                for idx, c in enumerate(cenas):
                    if not RUNNING:
                        return False

                    sc_id = str(c.get("scene_id", idx + 1))
                    
                    if sc_id in scenes_media and os.path.exists(scenes_media[sc_id].get("file", "")):
                        continue

                    query = c.get("youtube_query") or c.get("fala", "")
                    dur_est = float(c.get("duracao_estimada", 5.0))
                    
                    print(f"    🔍 Cena {sc_id}/{len(cenas)}: Buscando '{query}'...")
                    
                    # 1. Busca e baixa segmento do YouTube
                    broll_res = self.broll_engine.fetch_scene_broll(
                        query=query,
                        output_dir=broll_dir,
                        scene_idx=int(sc_id) if sc_id.isdigit() else idx,
                        target_duration=dur_est
                    )
                    
                    video_file = broll_res.get("video_file")
                    preview_frame = broll_res.get("preview_frame")
                    
                    # 2. Auditoria visual com ReviewerAgent
                    if video_file and preview_frame and os.path.exists(preview_frame):
                        review_result = self.reviewer_agent.review_frame(
                            image_path=preview_frame,
                            context_text=c.get("fala", query)
                        )
                        broll_res["review"] = review_result
                        if not review_result.get("aprovado", True):
                            print(f"    ⚠️ Frame reprovado pelo Revisor: {review_result.get('motivo')}")

                    scenes_media[sc_id] = broll_res
                    ckpt["scenes_media"] = scenes_media
                    self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)

                ckpt["status"] = "BROLL_READY"
                self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                print(f"  ✅ Todas as {len(cenas)} cenas de B-Roll foram preparadas!")
                stage = "RENDER_FINAL"

            if not RUNNING:
                return False

            # ETAPA 6: RENDERIZAÇÃO FINAL MULTI-CENA COM FFMPEG
            if stage in ("RENDER_FINAL", "BROLL_READY", "SCENES_READY", "RENDER_PENDING"):

                print("  🎞️ [6/6] Renderizando vídeo final 9:16 com áudio, B-Roll e legendas ASS...")
                
                audio_path = os.path.join(v_dir, ckpt.get("audio_file", "audio.mp3"))
                ass_path = os.path.join(v_dir, ckpt.get("ass_file", "subtitles.ass"))
                final_video_path = os.path.join(v_dir, "final_output.mp4")
                
                cenas = ckpt.get("storyboard", [])
                scenes_media = ckpt.get("scenes_media", {})
                
                # Monta a lista ordenada de segmentos de vídeo para cada cena (100% vídeos reais baixados)
                media_list = []
                available_video_files = []
                for idx, c in enumerate(cenas):
                    sc_id = str(c.get("scene_id", idx + 1))
                    m_data = scenes_media.get(sc_id, {})
                    v_file = m_data.get("video_file")
                    if v_file and os.path.exists(v_file) and os.path.getsize(v_file) > 0:
                        available_video_files.append(v_file)

                for idx, c in enumerate(cenas):
                    sc_id = str(c.get("scene_id", idx + 1))
                    m_data = scenes_media.get(sc_id, {})
                    v_file = m_data.get("video_file")
                    dur = float(c.get("duracao_estimada", 5.0))
                    if v_file and os.path.exists(v_file) and os.path.getsize(v_file) > 0:
                        media_list.append({
                            "type": "video",
                            "file": v_file,
                            "duration": dur,
                            "is_fallback": m_data.get("is_fallback", False)
                        })
                    elif available_video_files:
                        # Reutiliza vídeo real baixado existente para garantir que nenhum frame sintético seja gerado
                        fallback_file = available_video_files[idx % len(available_video_files)]
                        media_list.append({
                            "type": "video",
                            "file": fallback_file,
                            "duration": dur,
                            "is_fallback": True
                        })
                    else:
                        raise Exception(f"Nenhum clipe de vídeo real baixado disponível para a cena {sc_id}")

                try:
                    bgm_track = self.bgm_engine.get_bgm_for_topic(
                        topic_title=ckpt.get("topic", {}).get("tema", ""),
                        topic_context=ckpt.get("topic", {}).get("hook", "")
                    ) if self.enable_bgm else None

                    # Geração da trilha de Sound FX (SFX: Whooshes, Sinos e Clicks sincronizados)
                    sfx_track_path = None
                    if self.enable_sfx:
                        try:
                            sfx_cues = self.sfx_engine.detect_sfx_cues(
                                storyboard=cenas,
                                words_timing=ckpt.get("words_timing", []),
                                total_duration=ckpt.get("audio_duration", 60.0)
                            )
                            sfx_output_file = os.path.join(v_dir, "sfx_track.wav")
                            self.sfx_engine.build_sfx_audio_track(
                                sfx_cues=sfx_cues,
                                output_wav=sfx_output_file,
                                total_duration=ckpt.get("audio_duration", 60.0),
                                master_sfx_volume=self.sfx_volume
                            )
                            if os.path.exists(sfx_output_file) and os.path.getsize(sfx_output_file) > 1000:
                                sfx_track_path = sfx_output_file
                                ckpt["sfx_file"] = "sfx_track.wav"
                                print(f"  🔔 Trilha de Sound FX montada com {len(sfx_cues)} efeitos sonoros sincronizados!")
                        except Exception as e_sfx:
                            app_logger.warning(f"[AutoPipeline] Falha na montagem de SFX ({str(e_sfx)}). Renderizando sem SFX.")

                    success_res = assemble_multi_scene_video(
                        media_scenes=media_list,
                        audio_path=audio_path,
                        subtitles_path=ass_path if os.path.exists(ass_path) else None,
                        output_path=final_video_path,
                        bgm_path=bgm_track,
                        bgm_volume=self.bgm_volume,
                        sfx_path=sfx_track_path,
                        sfx_volume=self.sfx_volume,
                        topic_context=ckpt.get("topic", {})
                    )

                    success_render = success_res[0] if isinstance(success_res, tuple) else bool(success_res)
                    render_msg = success_res[1] if isinstance(success_res, tuple) and len(success_res) > 1 else ""
                    
                    if not success_render or not os.path.exists(final_video_path):
                        raise Exception(f"Falha no FFmpeg ao montar o vídeo final: {render_msg}")

                    file_size = os.path.getsize(final_video_path)
                    print(f"  🎉 VÍDEO CONCLUÍDO COM SUCESSO! ({file_size / (1024*1024):.2f} MB)")
                    print(f"  🎬 Arquivo: {final_video_path}")

                    
                    ckpt["final_video"] = "final_output.mp4"
                    ckpt["final_video_size"] = file_size
                    ckpt["status"] = "RENDER_COMPLETED"
                    ckpt["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                    self.checkpoint_mgr.mark_video_completed(batch_idx, video_idx, final_video_path)
                    return True

                except Exception as e:
                    app_logger.error(f"[AutoPipeline] Erro na renderização final: {str(e)}")
                    ckpt["error"] = f"Erro no render: {str(e)}"
                    self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                    return False

        return ckpt.get("status") in ("RENDER_COMPLETED", "COMPLETED")


    def run_batch(self, batch_idx: int) -> bool:
        """Executa sequencialmente todos os vídeos de um batch."""
        b_name = f"batch_{batch_idx}"
        print(f"\n{'#' * 75}")
        print(f"🚀 INICIANDO EXECUÇÃO DO {b_name.upper()} ({self.videos_per_batch} VÍDEOS)")
        print(f"{'#' * 75}")

        completed_count = 0
        for v_idx in range(self.videos_per_batch):
            if not RUNNING:
                print("\n🛑 Pipeline pausado pelo usuário. Retomada preservada nos checkpoints.")
                return False

            success = self.process_single_video(batch_idx, v_idx)
            if success:
                completed_count += 1
            else:
                if not RUNNING:
                    return False
                print(f"  ⚠️ Aviso: video_{v_idx} do {b_name} não pôde ser completado. Continuando...")

        print(f"\n📊 RESUMO DO {b_name.upper()}: {completed_count}/{self.videos_per_batch} vídeos concluídos.")
        return completed_count == self.videos_per_batch

    def run_loop(self, start_batch: Optional[int] = None, max_batches: int = 20):
        """Loop contínuo autônomo de geração de batches."""
        self.print_banner()

        # Validação obrigatória de pré-voo da API Gemini
        print("🔍 Executando teste de pré-voo e conectividade da API Gemini...")
        api_valid, api_msg = validate_gemini_api_connection()
        if not api_valid:
            print(f"\n❌ ERRO CRÍTICO NO PRÉ-VOO: {api_msg}")
            print("🛑 O pipeline foi interrompido para evitar a geração de arquivos genéricos sem chave de IA.")
            print("👉 Configure sua chave GEMINI_API_KEY no arquivo '.env' ou em 'gemini-api.txt' na raiz do projeto e execute novamente.")
            return

        print(f"✅ Pré-voo concluído: {api_msg}\n")

        current_batch, current_video = self.checkpoint_mgr.get_next_pending_target()
        if start_batch is not None:
            current_batch = start_batch

        print(f"🎯 Ponto de início determinado: batch_{current_batch} (vídeo pendente: video_{current_video})")

        batch_count = 0
        while RUNNING and batch_count < max_batches:
            success = self.run_batch(current_batch)
            if not RUNNING:
                break

            current_batch += 1
            batch_count += 1
            print(f"\n⏳ Pausa de 5 segundos antes de iniciar o próximo batch...")
            time.sleep(5)

        print("\n🏁 Execução do AutoPipeline finalizada.")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="AutoPipeline Minuto Inexplicável 9:16")
    parser.add_argument("--batch", type=int, default=None, help="Batch específico para executar")
    parser.add_argument("--voice", type=str, default="pt-BR-AntonioNeural", help="Voz Neural do Edge-TTS")
    parser.add_argument("--rate", type=str, default="+25%", help="Taxa de velocidade do áudio (ex: +25%%)")
    parser.add_argument("--pitch", type=str, default="+0Hz", help="Tom vocal (ex: +0Hz)")

    parser.add_argument("--model", type=str, default="gemini-flash-lite-latest", help="Modelo LLM")
    parser.add_argument("--max-batches", type=int, default=10, help="Máximo de batches a processar")
    args = parser.parse_args()

    if not acquire_pipeline_lock():
        print("\n⚠️ AVISO: Uma instância do gerador (auto_pipeline.py) já está ativa neste computador!")
        print("🔒 Esta janela será encerrada para evitar duplicações e concorrência no pipeline.\n")
        sys.exit(0)

    atexit.register(release_pipeline_lock)

    try:
        runner = AutoPipelineRunner(
            voice=args.voice,
            rate=args.rate,
            pitch=args.pitch,
            model_name=args.model
        )
        runner.run_loop(start_batch=args.batch, max_batches=args.max_batches)
    finally:
        release_pipeline_lock()

if __name__ == "__main__":
    main()

