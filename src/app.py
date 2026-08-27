import streamlit as st
import os
import sys
import time
import json
import tempfile
from google import genai

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) == "src" else CURRENT_DIR
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Carregar variáveis de ambiente
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

try:
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
        save_video_metadata_file
    )
    from .audio import AudioEngine, FALLBACK_VOICES, VOICE_PROSODY_PRESETS
    from .broll_engine import BRollEngine
    from .visual_engine import VisualEngine
    from .subtitles import convert_words_to_ass
    from .render import assemble_multi_scene_video
    from .checkpoint_manager import CheckpointManager
    from .pronunciation import PronunciationEngine, DEFAULT_PRONUNCIATION_ENGINE
    from .algorithm_memory import AlgorithmMemorySystem, DEFAULT_ALGORITHM_MEMORY
    from .bgm_engine import BGMEngine, DEFAULT_BGM_ENGINE, BGM_THEME_PROFILES
    from .sfx_engine import SFXEngine, DEFAULT_SFX_ENGINE
    from .video_enhancer import VideoResolutionEnhancer, DEFAULT_VIDEO_ENHANCER
    from .logger import (
        app_logger,
        get_recent_ui_logs,
        analyze_logs,
        LOGS_DIR,
        get_active_throttling_alerts,
        get_throttling_summary
    )
except ImportError:
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
        save_video_metadata_file
    )
    from audio import AudioEngine, FALLBACK_VOICES, VOICE_PROSODY_PRESETS
    from broll_engine import BRollEngine
    from visual_engine import VisualEngine
    from subtitles import convert_words_to_ass
    from render import assemble_multi_scene_video
    from checkpoint_manager import CheckpointManager
    from pronunciation import PronunciationEngine, DEFAULT_PRONUNCIATION_ENGINE
    from algorithm_memory import AlgorithmMemorySystem, DEFAULT_ALGORITHM_MEMORY
    from bgm_engine import BGMEngine, DEFAULT_BGM_ENGINE, BGM_THEME_PROFILES
    from sfx_engine import SFXEngine, DEFAULT_SFX_ENGINE
    from video_enhancer import VideoResolutionEnhancer, DEFAULT_VIDEO_ENHANCER
    from logger import (
        app_logger,
        get_recent_ui_logs,
        analyze_logs,
        LOGS_DIR,
        get_active_throttling_alerts,
        get_throttling_summary
    )

st.set_page_config(
    page_title="Minuto Inexplicável Studio - Shorts 9:16",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #9C27B0, #E040FB, #FFD700);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #9E9E9E;
        margin-bottom: 1.5rem;
    }
    .badge-approved {
        background-color: #1B5E20;
        color: #81C784;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85rem;
    }
    .badge-rejected {
        background-color: #B71C1C;
        color: #EF9A9A;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85rem;
    }
    .stProgress > div > div > div > div {
        background-color: #E040FB;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/isometric/100/secret.png", width=70)
    st.markdown("## ⚙️ Configurações do Estúdio")
    
    api_key_env = resolve_gemini_api_key()
    api_key = st.text_input("🔑 Gemini API Key:", value=api_key_env, type="password")
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key
        
    st.markdown("---")
    st.markdown("### 🤖 Modelo & Gestão de Quota")
    
    model_choice = st.selectbox(
        "Modelo Principal Gemini:",
        options=DEFAULT_FALLBACK_MODELS,
        index=0,
        help="Modelos ultrarrápidos e testados com cota gratuita abundante."
    )
    
    auto_fallback = st.checkbox(
        "🔄 Fallback Automático de Modelo",
        value=True,
        help="Se o modelo atingir cota ou timeout (>60s), tenta automaticamente o próximo modelo disponível."
    )
    
    auto_cooldown = st.checkbox(
        "⏳ Cooldown com Contador Regressivo",
        value=True,
        help="Se todos os modelos baterem cota, aguarda com contagem regressiva na tela."
    )
    
    st.markdown("---")
    st.markdown("### 🎙️ Voz e Prosódia Vocal")
    voice_choice = st.selectbox(
        "Voz Neural (Edge-TTS):",
        options=FALLBACK_VOICES,
        index=0
    )
    
    preset_choice = st.selectbox(
        "🎭 Preset de Prosódia:",
        options=list(VOICE_PROSODY_PRESETS.keys()),
        index=0,
        help="Ajusta taxa, tom e volume para suspense ou alta energia."
    )
    selected_preset = VOICE_PROSODY_PRESETS[preset_choice]
    st.caption(f"ℹ️ {selected_preset['description']} (`rate`: {selected_preset['rate']}, `pitch`: {selected_preset['pitch']})")
    
    rate_choice = selected_preset['rate']
    pitch_choice = selected_preset['pitch']
    volume_choice = selected_preset['volume']

    st.markdown("---")
    st.markdown("### 🎵 Áudio, BGM & Sound FX")
    enable_bgm_ui = st.checkbox("🔊 Ativar Trilha Sonora (BGM Suspense)", value=True, help="Adiciona música de fundo dark ambient com ducking de volume.")
    bgm_volume_ui = st.slider("🎚️ Volume da Música (Ducking):", min_value=0.02, max_value=0.30, value=0.12, step=0.01, format="%.2f")

    enable_sfx_ui = st.checkbox("🔔 Ativar Sound FX (Whooshes, Sinos e Clicks)", value=True, help="Dispara whooshes em transições, sinos em mistérios e clicks em documentos.")
    sfx_volume_ui = st.slider("🎚️ Volume dos Efeitos (SFX):", min_value=0.10, max_value=0.80, value=0.35, step=0.05, format="%.2f")

    st.markdown("---")
    st.markdown("### ✨ Resolução & Pós-Processamento")
    enable_hd_ui = st.checkbox("📺 Forçar Full HD 1080x1920 + Unsharp", value=True, help="Garante upscaling HD com nitidez e equalização de contraste.")

# Header Principal
st.markdown('<div class="main-header">🔮 MINUTO INEXPLICÁVEL STUDIO</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Fábrica Autônoma Multi-Agente de Vídeos Curtos (9:16 Vertical) para Shorts/Reels/TikTok</div>', unsafe_allow_html=True)

def render_throttling_alerts_ui():
    alerts = get_active_throttling_alerts()
    if alerts:
        for al in alerts:
            if al["source"] == "GEMINI_API":
                st.warning(
                    f"⚠️ **Alerta de Quota no Gemini [{al['time_str']}]:** {al['message']} "
                    f"(Aguardando liberação em {al['retry_after']}s)."
                )
            elif al["source"] == "YOUTUBE_DOWNLOAD":
                st.warning(
                    f"⚠️ **Alerta de Throttling no Download de Vídeo [{al['time_str']}]:** {al['message']} "
                    f"(Cooldown aplicado: {al['retry_after']}s)."
                )

# Tabs Principais
tab_prod, tab_batches, tab_audio_sfx, tab_memory, tab_phonetics, tab_diag = st.tabs([
    "🎬 Estúdio de Produção",
    "📦 Batches & Checkpoints",
    "🔔 Sound FX & Trilha Sonora",
    "📈 Memória Algorítmica & Métricas",
    "🗣️ Dicionário Fonético",
    "📊 Central de Logs & Diagnóstico"
])

with tab_prod:
    render_throttling_alerts_ui()
    if "temas" not in st.session_state:
        st.session_state.temas = []
    if "avaliacoes" not in st.session_state:
        st.session_state.avaliacoes = {}
    if "dissertacoes" not in st.session_state:
        st.session_state.dissertacoes = {}
    if "storyboards" not in st.session_state:
        st.session_state.storyboards = {}
    if "last_generated_video" not in st.session_state:
        st.session_state.last_generated_video = None

    def create_ui_cooldown_handler(container):
        def cooldown_callback(remaining, total, model_name):
            if remaining > 0:
                pct = 1.0 - (remaining / total)
                container.warning(
                    f"⏳ **Limite de Requisições Atingido no Modelo `{model_name}`!**\n\n"
                    f"Aguardando liberação de cota: **{remaining} segundos restantes**..."
                )
                container.progress(pct)
            else:
                container.empty()
        return cooldown_callback

    # Área de Controle de Temas
    col_ctrl1, col_ctrl2 = st.columns([1.5, 3.5])
    with col_ctrl1:
        btn_gerar = st.button("💡 Propor 10 Novos Mistérios (60-90s)", type="primary", use_container_width=True)

    cooldown_box_top = st.empty()

    if btn_gerar:
        with st.status("🧠 **ProposerAgent** minerando mistérios e documentos desclassificados...", expanded=True) as status:
            live_status = st.empty()
            
            def on_proposer_status(msg):
                live_status.markdown(f"📡 {msg}")
                
            proposer = ProposerAgent(
                model_name=model_choice,
                auto_fallback=auto_fallback,
                auto_cooldown=auto_cooldown,
                api_key=api_key
            )
            cooldown_fn = create_ui_cooldown_handler(cooldown_box_top)
            
            try:
                ckpt_mgr = CheckpointManager()
                blacklist_titles = ckpt_mgr.get_blacklist_titles()
                temas = proposer.generate_topics(
                    count=10,
                    blacklist=blacklist_titles,
                    cooldown_callback=cooldown_fn,
                    status_callback=on_proposer_status
                )
                if isinstance(temas, list) and len(temas) > 0:
                    st.session_state.temas = temas
                    st.session_state.avaliacoes = {}
                    st.session_state.dissertacoes = {}
                    st.session_state.storyboards = {}
                    status.update(label="✅ 10 Novos Mistérios Gerados!", state="complete", expanded=False)
                    st.rerun()
                else:
                    status.update(label="❌ Erro ao estruturar temas", state="error")
                    st.error(f"Resposta inesperada do Gemini: {temas}")
            except Exception as e:
                status.update(label="❌ Falha na geração de temas", state="error")
                st.error(f"Erro: {str(e)}")

    # Exibição dos Temas Propostos
    if st.session_state.temas:
        st.markdown("---")
        st.markdown("### 📋 Mistérios em Pauta")
        
        for idx, tema in enumerate(st.session_state.temas):
            with st.container():
                st.markdown(f"#### 🎯 #{idx+1}: {tema.get('tema', 'Mistério Desclassificado')}")
                
                c_hook, c_tech = st.columns([1, 1])
                with c_hook:
                    st.info(f"🎣 **Hook (Primeiros 3 segundos):**\n\n\"{tema.get('hook', '')}\"")
                with c_tech:
                    st.markdown(f"🔬 **Contexto Factual:**\n\n{tema.get('explicacao_tecnica', '')}")
                
                # Ações de Pesquisa (Dissertação) e Roteirização (Diretor)
                c_b1, c_b2, c_b3 = st.columns([1.5, 1.5, 2])
                with c_b1:
                    btn_dissertar = st.button(f"🔬 Pesquisar e Dissertar #{idx+1}", key=f"btn_diss_{idx}", use_container_width=True)
                with c_b2:
                    btn_roteirizar = st.button(f"✍️ Gerar Storyboard #{idx+1}", key=f"btn_rot_{idx}", use_container_width=True)

                if btn_dissertar:
                    with st.status(f"🔬 **DissertationAgent** construindo monografia factual para #{idx+1}...", expanded=True) as d_status:
                        d_agent = DissertationAgent(model_name=model_choice, auto_fallback=auto_fallback, auto_cooldown=auto_cooldown, api_key=api_key)
                        res_diss = d_agent.generate_dissertation(tema)
                        st.session_state.dissertacoes[idx] = res_diss
                        d_status.update(label=f"✅ Monografia factual concluída!", state="complete")
                        st.rerun()

                if btn_roteirizar:
                    with st.status(f"✍️ **DirectorAgent** destilando roteiro de 60-90s para #{idx+1}...", expanded=True) as r_status:
                        dir_agent = DirectorAgent(model_name=model_choice, auto_fallback=auto_fallback, auto_cooldown=auto_cooldown, api_key=api_key)
                        diss_data = st.session_state.dissertacoes.get(idx)
                        res_story = dir_agent.generate_storyboard(tema, dissertacao_data=diss_data)
                        st.session_state.storyboards[idx] = res_story
                        r_status.update(label=f"✅ Storyboard com {len(res_story)} cenas gerado!", state="complete")
                        st.rerun()

                # Exibição da Dissertação se gerada
                if idx in st.session_state.dissertacoes:
                    diss = st.session_state.dissertacoes[idx]
                    with st.expander(f"📄 Monografia Documental Factual (Fase 1) — #{idx+1}", expanded=True):
                        st.markdown(f"**Entidade Central:** `{diss.get('entidade_principal')}`")
                        st.markdown(f"**Dados Quantitativos:** `{json.dumps(diss.get('dados_quantitativos', {}), ensure_ascii=False)}`")
                        st.markdown(f"**Enigma Central:** {diss.get('anomalia_ou_enigma_central')}")
                        st.markdown(f"**Dissertação Completa:**\n\n{diss.get('dissertacao_completa')}")

                # Exibição do Storyboard se gerado
                if idx in st.session_state.storyboards:
                    story = st.session_state.storyboards[idx]
                    with st.expander(f"🎬 Storyboard Destilado (Fase 2 - {len(story)} Cenas) — #{idx+1}", expanded=True):
                        for sc in story:
                            st.markdown(f"**Cena {sc.get('scene_id')}:** *\"{sc.get('fala')}\"*  \n🔍 *Query B-Roll YouTube:* `{sc.get('youtube_query')}` ({sc.get('duracao_estimada', 5.0)}s)")

                st.markdown("---")

with tab_batches:
    st.markdown("### 📦 Gerenciador de Batches & Checkpoints")
    ckpt_mgr = CheckpointManager()
    state = ckpt_mgr.load_global_state()
    
    c_m1, c_m2, c_m3 = st.columns(3)
    c_m1.metric("Batches Concluídos", state.get("completed_batches_count", 0))
    c_m2.metric("Vídeos Concluídos", state.get("total_completed_videos", 0))
    next_b, next_v = ckpt_mgr.get_next_pending_target()
    c_m3.metric("Próximo Alvo", f"batch_{next_b} / video_{next_v}")

    st.markdown("#### 📋 Histórico da Blacklist (Semântica)")
    bl_items = ckpt_mgr.load_blacklist()
    if bl_items:
        st.dataframe(bl_items[-30:], use_container_width=True)
    else:
        st.info("Blacklist vazia.")

with tab_audio_sfx:
    st.markdown("### 🔔 Sound FX & 🎵 Trilha Sonora de Suspense")
    
    c_sfx_info1, c_sfx_info2 = st.columns(2)
    with c_sfx_info1:
        st.markdown("#### 🔔 Sound FX (Transições, Sinos & Clicks)")
        st.caption("Efeitos sonoros sincronizados nos milissegundos exatos de cortes de cena e palavras de revelação.")
        sfx_eng = DEFAULT_SFX_ENGINE or SFXEngine()
        sfx_list = sfx_eng.list_available_sfx()
        for s_item in sfx_list:
            st.markdown(f"**{s_item['filename']}** ({s_item['size_kb']} KB)")
            if os.path.exists(s_item["path"]):
                st.audio(s_item["path"])
    
    with c_sfx_info2:
        st.markdown("#### 🎵 Trilha Sonora BGM (Dark Ambient)")
        st.caption("Ambiências de suspense com ducking de volume em -20dB para destacar a voz neural.")
        bgm_eng = DEFAULT_BGM_ENGINE or BGMEngine()
        bgm_list = bgm_eng.list_available_tracks()
        for b_item in bgm_list:
            st.markdown(f"**{b_item['filename']}** ({b_item['size_kb']} KB)")
            if os.path.exists(b_item["path"]):
                st.audio(b_item["path"])

    with st.expander("🌐 Baixar Nova Trilha de Suspense Sem Copyright (YouTube Audio Library)"):
        with st.form("form_download_bgm"):
            query_bgm = st.text_input("Termo de Busca Royalty-Free:", value="dark ambient suspense investigation background music no copyright")
            btn_dl_bgm = st.form_submit_button("🔍 Baixar e Adicionar ao Banco")
            if btn_dl_bgm and query_bgm:
                with st.spinner("Baixando e convertendo trilha sem copyright..."):
                    res = bgm_eng.fetch_online_royalty_free_bgm(query_bgm)
                    if res:
                        st.success(f"Trilha adicionada com sucesso: `{os.path.basename(res)}`")
                        st.rerun()

with tab_memory:
    st.markdown("### 📈 Inteligência Algorítmica e Sincronização de Métricas")
    st.markdown("Acompanhe o aprendizado contínuo da IA com base nas métricas reais de visualizações e retenção do **YouTube Shorts**.")

    col_s1, col_s2 = st.columns([2, 2])
    with col_s1:
        if st.button("🔄 Sincronizar METRICAS_VIDEOS.csv com a Memória", type="primary", use_container_width=True):
            from scripts.sync_metrics import sync_from_csv
            csv_path = os.path.join(PROJECT_ROOT, "METRICAS_VIDEOS.csv")
            n = sync_from_csv(csv_path, DEFAULT_ALGORITHM_MEMORY)
            st.success(f"✅ {n} registros de analytics sincronizados com sucesso!")
            st.rerun()

    weights = DEFAULT_ALGORITHM_MEMORY.load_weights()
    st.markdown("#### ⚖️ Pesos Auxiliares Dinâmicos Ativos")
    
    cols_w = st.columns(3)
    idx_w = 0
    for k, v in weights.items():
        with cols_w[idx_w % 3]:
            st.metric(k, f"{v:.2f}")
        idx_w += 1

    st.markdown("#### 📋 Histórico Analítico dos Vídeos")
    records = DEFAULT_ALGORITHM_MEMORY.load_history()
    if records:
        st.dataframe(records, use_container_width=True)
    else:
        st.info("Nenhum vídeo registrado com métricas ainda. Edite `METRICAS_VIDEOS.csv` e clique em sincronizar.")

    if os.path.exists(DEFAULT_ALGORITHM_MEMORY.memory_md_file):
        with st.expander("📄 Ver Documento Completo ALGORITHM_MEMORY.md", expanded=False):
            with open(DEFAULT_ALGORITHM_MEMORY.memory_md_file, "r", encoding="utf-8") as mf:
                st.markdown(mf.read())

with tab_phonetics:
    st.markdown("### 🗣️ Dicionário Fonético & Adaptação para Edge-TTS")
    st.markdown("Garante que termos estrangeiros, nomes de expedições e mistérios sejam pronunciados perfeitamente pelo Edge-TTS (pt-BR), preservando a escrita correta nas legendas ASS.")

    lexicon = DEFAULT_PRONUNCIATION_ENGINE.get_lexicon()
    search_term = st.text_input("🔍 Buscar termo no léxico fonético:", "")

    filtered_lex = {k: v for k, v in lexicon.items() if search_term.lower() in k.lower()} if search_term else lexicon

    st.markdown(f"**Total de Regras Ativas:** {len(lexicon)}")
    st.dataframe([{"Termo Original (Legenda)": k, "Grafia Fonética (Edge-TTS)": v} for k, v in list(filtered_lex.items())[:50]], use_container_width=True)

    with st.expander("➕ Adicionar Nova Regra Fonética Personalizada"):
        with st.form("form_fonetica"):
            novo_termo = st.text_input("Termo Original (ex: 'Camp Century'):")
            nova_pronuncia = st.text_input("Grafia Fonética (ex: 'Kemp Sênturi'):")
            submit_regra = st.form_submit_button("Salvar Regra")
            if submit_regra and novo_termo and nova_pronuncia:
                DEFAULT_PRONUNCIATION_ENGINE.add_custom_rule(novo_termo, nova_pronuncia)
                st.success(f"Regra adicionada: '{novo_termo}' ➔ '{nova_pronuncia}'")
                st.rerun()

with tab_diag:
    st.markdown("### 📊 Central de Logs & Diagnóstico")
    summary = get_throttling_summary()
    st.json(summary)
    
    recent_logs = get_recent_ui_logs(max_lines=100)
    st.code(recent_logs or "Nenhum log registrado na sessão atual.", language="log")
