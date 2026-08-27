"""
Módulo de Inteligência Algorítmica, Big Data e Memória de Feedback (.md) para o Minuto Inexplicável.
Rastreia a anatomia completa de todos os conteúdos produzidos, processa métricas de analytics
(visualizações, retenção aos 3s, APV %, CTR %, engajamento), realiza atribuição causal de sucesso
e atualiza pesos auxiliares dinâmicos para convergir na fórmula viral sem repetir temas.
"""

import os
import json
import time
import math
from typing import Dict, List, Any, Optional, Tuple

try:
    from .logger import app_logger, LogSpan
    from .deduplication import sanitize_and_cap_title, extract_canonical_entity
    from .analytics_parser import DEFAULT_ANALYTICS_PARSER, YouTubeAnalyticsZipParser, ANALYTICS_DIR
except ImportError:
    from logger import app_logger, LogSpan
    from deduplication import sanitize_and_cap_title, extract_canonical_entity
    from analytics_parser import DEFAULT_ANALYTICS_PARSER, YouTubeAnalyticsZipParser, ANALYTICS_DIR

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR = os.path.join(PROJECT_ROOT, "data", "algorithm_memory")

# Pesos auxiliares padrão calibrados para retenção máxima em Shorts de 60s a 120s
DEFAULT_AUXILIARY_WEIGHTS: Dict[str, float] = {
    "hook_curiosity_gap_weight": 0.95,      # Intensidade do gancho nos primeiros 3s (paradoxo/dado chocante)
    "technical_depth_weight": 0.92,         # Nível de profundidade e exatidão documental (vs termos genéricos)
    "anti_hype_precision_weight": 0.90,     # Penalização severa de palavras de efeito vazias e buzzwords
    "atmosphere_sound_weight": 0.88,        # Foco em termos sonoros e busca de B-roll autêntico
    "telemetry_density_weight": 0.85,       # Presença de dados concretos (anos, coordenadas, profundidade, frequências)
    "pacing_cadence_wpm": 185.0,            # Palavras por minuto ideais (ritmo 1.25x acelerado)
    "broll_cut_frequency_sec": 3.0,         # Tempo médio entre tomadas de corte (em segundos)
    "conflict_and_triumph_weight": 0.80,    # Presença do enigma e investigação científica
    "comment_trigger_weight": 0.85          # Eficácia da pergunta final para provocar debate nos comentários
}

class AlgorithmMemorySystem:
    """
    Sistema Central de Memória Algorítmica e Inteligência de Conteúdo.
    Persiste dados analíticos em JSON e compila a memória analítica em ALGORITHM_MEMORY.md.
    """

    def __init__(self, memory_dir: Optional[str] = None, data_dir: Optional[str] = None, root_dir: Optional[str] = None):
        target_dir = memory_dir or data_dir or root_dir or MEMORY_DIR
        self.memory_dir = os.path.abspath(target_dir)
        os.makedirs(self.memory_dir, exist_ok=True)
        
        self.weights_file = os.path.join(self.memory_dir, "auxiliary_weights.json")
        self.history_file = os.path.join(self.memory_dir, "analytics_history.json")
        self.memory_md_file = os.path.join(self.memory_dir, "ALGORITHM_MEMORY.md")
        
        self._init_files_if_needed()

    def _init_files_if_needed(self):
        """Inicializa os arquivos de persistência caso ainda não existam."""
        if not os.path.exists(self.weights_file):
            self.save_weights(DEFAULT_AUXILIARY_WEIGHTS)

        if not os.path.exists(self.history_file):
            initial_history = {
                "version": 1,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "total_records": 0,
                "records": []
            }
            self._save_json_atomic(self.history_file, initial_history)

        if not os.path.exists(self.memory_md_file):
            self._regenerate_markdown_memory()

    def _save_json_atomic(self, file_path: str, data: Any):
        """Salva arquivo JSON atomicamente com arquivo temporário."""
        tmp = f"{file_path}.tmp.{time.time()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, file_path)

    def load_weights(self) -> Dict[str, float]:
        """Carrega os pesos auxiliares ativos."""
        try:
            if os.path.exists(self.weights_file):
                with open(self.weights_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {k: float(v) for k, v in data.items()}
        except Exception as e:
            app_logger.warning(f"[AlgorithmMemory] Erro ao ler auxiliary_weights.json: {str(e)}")
        return dict(DEFAULT_AUXILIARY_WEIGHTS)

    def save_weights(self, weights: Dict[str, float]):
        """Salva os pesos auxiliares atualizados."""
        self._save_json_atomic(self.weights_file, weights)
        app_logger.info(f"[AlgorithmMemory] Pesos auxiliares salvos: {self.weights_file}")

    def load_history(self) -> List[Dict[str, Any]]:
        """Carrega o histórico completo de vídeos e métricas."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("records", [])
        except Exception as e:
            app_logger.warning(f"[AlgorithmMemory] Erro ao ler analytics_history.json: {str(e)}")
        return []

    def record_video_generation(self, video_payload: Dict[str, Any]) -> str:
        """
        Registra a anatomia completa de um novo vídeo gerado para futuro acompanhamento analítico.
        """
        history_data = self.load_history()
        video_id = video_payload.get("video_id") or f"vid_{int(time.time()*1000)}"
        
        existing_idx = next((i for i, r in enumerate(history_data) if r.get("video_id") == video_id), None)
        
        raw_tema = video_payload.get("tema", "")
        clean_tema = sanitize_and_cap_title(raw_tema, max_length=100)
        
        entry = {
            "video_id": video_id,
            "batch": video_payload.get("batch", "batch_0"),
            "video_index": video_payload.get("video_index", 0),
            "tema": clean_tema,
            "core_entity": video_payload.get("core_entity") or extract_canonical_entity(clean_tema),
            "hook": video_payload.get("hook", ""),
            "dissertacao_resumo": video_payload.get("dissertacao_resumo", ""),
            "duracao_segundos": video_payload.get("duracao_segundos", 0.0),
            "palavras_totais": video_payload.get("palavras_totais", 0),
            "total_cenas": video_payload.get("total_cenas", 0),
            "estilo_voz": video_payload.get("estilo_voz", "pt-BR-AntonioNeural"),
            "criado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "analytics": video_payload.get("analytics", {
                "views": 0,
                "retention_3s_pct": None,
                "apv_pct": None,
                "ctr_pct": None,
                "likes": 0,
                "comments": 0,
                "shares": 0,
                "performance_tier": "PENDING",
                "feedback_notes": ""
            })
        }

        if existing_idx is not None:
            history_data[existing_idx] = entry
        else:
            history_data.append(entry)

        payload = {
            "version": 1,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_records": len(history_data),
            "records": history_data
        }
        self._save_json_atomic(self.history_file, payload)
        self._regenerate_markdown_memory()
        app_logger.info(f"[AlgorithmMemory] Vídeo '{entry['tema']}' registrado na memória de analytics.")
        return video_id

    @staticmethod
    def _calculate_exposure_aware_tier(
        views: int,
        exposure_days: float,
        views_per_day: float,
        projected_28d_views: int,
        apv_pct: Optional[float],
        ctr_pct: Optional[float],
        retention_3s_pct: Optional[float],
        likes: int = 0
    ) -> str:
        """Classificação MECE imune ao viés de tempo de exposição."""
        if exposure_days <= 1.0 and views < 10 and (apv_pct is None or apv_pct < 50.0):
            return "INCUBATING"

        if (retention_3s_pct is not None and retention_3s_pct < 30.0) or (apv_pct is not None and apv_pct < 20.0):
            return "D"

        if (views_per_day >= 250.0 or projected_28d_views >= 3000 or views >= 5000):
            if apv_pct is None or apv_pct >= 20.0:
                return "S"

        if (views_per_day >= 75.0 or projected_28d_views >= 1000 or views >= 1500 or (apv_pct and apv_pct >= 65.0 and views >= 40)):
            return "A"

        if (views_per_day >= 15.0 or projected_28d_views >= 200 or views >= 100 or (apv_pct and apv_pct >= 40.0 and views >= 5)):
            return "B"

        if exposure_days >= 3.0 and views_per_day < 15.0 and views >= 15:
            if apv_pct and apv_pct >= 30.0:
                return "C"
            return "D"

        if views >= 1:
            return "B"
        return "PENDING"

    def ingest_analytics_feedback(
        self,
        identifier: str,
        views: int = 0,
        retention_3s_pct: Optional[float] = None,
        apv_pct: Optional[float] = None,
        ctr_pct: Optional[float] = None,
        likes: int = 0,
        comments: int = 0,
        shares: int = 0,
        publish_date: Optional[str] = None,
        exposure_days: Optional[float] = None,
        views_per_day: Optional[float] = None,
        projected_28d_views: Optional[int] = None,
        growth_trajectory: Optional[str] = None,
        watch_time_hours: Optional[float] = None,
        impressions: Optional[int] = None,
        subscribers: Optional[int] = None,
        feedback_notes: str = "",
        ai_analyzer_callback = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        history = self.load_history()
        target_record = None
        target_idx = -1

        for i, r in enumerate(history):
            bv_tag = f"{r.get('batch')}/{r.get('video_index')}"
            bv_tag_v = f"{r.get('batch')}/video_{r.get('video_index')}"
            if r.get("video_id") == identifier or identifier in (bv_tag, bv_tag_v) or identifier.lower() in r.get("tema", "").lower():
                target_record = r
                target_idx = i
                break

        if target_idx == -1 or not target_record:
            return False, f"Nenhum vídeo encontrado para o identificador '{identifier}'.", {}

        exp_days = exposure_days or 1.0
        vpd = views_per_day if views_per_day is not None else round(views / max(1.0, exp_days), 2)
        proj_28d = projected_28d_views if projected_28d_views is not None else views

        tier = self._calculate_exposure_aware_tier(
            views=views,
            exposure_days=exp_days,
            views_per_day=vpd,
            projected_28d_views=proj_28d,
            apv_pct=apv_pct,
            ctr_pct=ctr_pct,
            retention_3s_pct=retention_3s_pct,
            likes=likes
        )

        target_record["analytics"] = {
            "views": views,
            "publish_date": publish_date,
            "exposure_days": exp_days,
            "views_per_day": vpd,
            "projected_28d_views": proj_28d,
            "growth_trajectory": growth_trajectory or "STEADY_GROWTH",
            "watch_time_hours": watch_time_hours,
            "impressions": impressions,
            "subscribers": subscribers,
            "retention_3s_pct": retention_3s_pct,
            "apv_pct": apv_pct,
            "ctr_pct": ctr_pct,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "performance_tier": tier,
            "feedback_notes": feedback_notes,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")
        }

        history[target_idx] = target_record
        payload = {
            "version": 1,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_records": len(history),
            "records": history
        }
        self._save_json_atomic(self.history_file, payload)
        self._recalibrate_weights_based_on_analytics(history)
        self._regenerate_markdown_memory()

        return True, f"Feedback do vídeo '{target_record.get('tema')}' atualizado com sucesso (Tier: {tier}).", target_record

    def record_video_metrics(
        self,
        video_id: str,
        title: str = "",
        views: int = 0,
        retention_3s: float = 0.0,
        apv: float = 0.0,
        ctr: float = 0.0,
        likes: int = 0,
        comments: int = 0,
        shares: int = 0,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Registra métricas reais de vídeo e calcula o composite_score."""
        history = self.load_history()
        composite_score = round(
            (min(views, 100000) / 1000.0) * 0.35 +
            (retention_3s * 0.25) +
            (apv * 0.30) +
            (ctr * 1.5) +
            (min(likes, 5000) / 100.0) * 0.10,
            2
        )
        rec = {
            "video_id": video_id,
            "title": title,
            "tema": title,
            "views": views,
            "retention_3s": retention_3s,
            "apv": apv,
            "ctr": ctr,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "composite_score": composite_score,
            "notes": notes,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S")
        }

        # Atualiza histórico
        existing_idx = next((i for i, r in enumerate(history) if r.get("video_id") == video_id), None)
        if existing_idx is not None:
            history[existing_idx].update(rec)
        else:
            history.append(rec)

        payload = {
            "version": 1,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_records": len(history),
            "records": history
        }
        self._save_json_atomic(self.history_file, payload)
        self._regenerate_markdown_memory()
        return rec

    def _recalibrate_weights_based_on_analytics(self, history: List[Dict[str, Any]]):

        """Recalibra os pesos auxiliares ativos com base no desempenho dos Tiers."""
        s_and_a_vids = [r for r in history if r.get("analytics", {}).get("performance_tier") in ("S", "A")]
        if not s_and_a_vids:
            return

        weights = self.load_weights()
        weights["hook_curiosity_gap_weight"] = round(min(1.0, weights.get("hook_curiosity_gap_weight", 0.95) + 0.01), 3)
        weights["technical_depth_weight"] = round(min(1.0, weights.get("technical_depth_weight", 0.92) + 0.01), 3)
        weights["anti_hype_precision_weight"] = round(min(1.0, weights.get("anti_hype_precision_weight", 0.90) + 0.01), 3)
        self.save_weights(weights)

    def _regenerate_markdown_memory(self):
        """Regenera o arquivo ALGORITHM_MEMORY.md formatado."""
        history = self.load_history()
        weights = self.load_weights()

        total_vids = len(history)
        total_views = sum(r.get("analytics", {}).get("views", 0) for r in history)
        s_tier = [r for r in history if r.get("analytics", {}).get("performance_tier") == "S"]
        a_tier = [r for r in history if r.get("analytics", {}).get("performance_tier") == "A"]
        
        md = f"""# 🧠 Memória Algorítmica e Inteligência de Conteúdo - Minuto Inexplicável

*Atualizado em: {time.strftime('%Y-%m-%d %H:%M:%S')}*

## 📊 1. Resumo Executivo da Base de Vídeos
- **Total de Vídeos Gerados:** `{total_vids}`
- **Visualizações Totais Acumuladas:** `{total_views:,}`
- **Vídeos Tier S (Super Virais):** `{len(s_tier)}`
- **Vídeos Tier A (Alta Retenção):** `{len(a_tier)}`

---

## 🎯 2. Pesos Auxiliares Ativos (Vetor de Convergência Viral)
- **`hook_curiosity_gap_weight`:** `{weights.get('hook_curiosity_gap_weight', 0.95):.2f}`
- **`technical_depth_weight`:** `{weights.get('technical_depth_weight', 0.92):.2f}`
- **`anti_hype_precision_weight`:** `{weights.get('anti_hype_precision_weight', 0.90):.2f}`
- **`pacing_cadence_wpm`:** `{weights.get('pacing_cadence_wpm', 185.0):.0f} WPM`
- **`broll_cut_frequency_sec`:** `{weights.get('broll_cut_frequency_sec', 3.0):.1f}s`

---

## 🏆 3. Top Conteúdos por Performance
"""
        for r in (s_tier + a_tier)[:8]:
            an = r.get("analytics", {})
            md += f"- **{r.get('tema')}** (Tier {an.get('performance_tier')}) — {an.get('views', 0):,} views | {an.get('views_per_day', 0.0):.1f} v/d\n"

        with open(self.memory_md_file, "w", encoding="utf-8") as f:
            f.write(md)

    def get_prompt_context_for_generation(self) -> str:
        """Gera o bloco de instruções e diretrizes ativas para injeção nos agentes."""
        weights = self.load_weights()
        return (
            f"\n[DIRETRIZES DA MEMÓRIA ALGORÍTMICA (.MD) & PESOS AUXILIARES ATIVOS]:\n"
            f"- Intensidade do Hook Inicial (0-3s): {weights.get('hook_curiosity_gap_weight', 0.95):.2f}/1.0 (Mistério chocante, data ou documento desclassificado imediato nos primeiros 3s).\n"
            f"- Profundidade Documental & Factual: {weights.get('technical_depth_weight', 0.92):.2f}/1.0 (Fatos históricos, coordenadas exatas, nomes de projetos, frequências e evidências reais).\n"
            f"- Tolerância Zero a Buzzwords Vazias (Anti-Hype): {weights.get('anti_hype_precision_weight', 0.90):.2f}/1.0 (PROIBIDO usar enrolação ou adjetivos vazios no meio do vídeo. Preencha com fatos e evidências documentadas).\n"
            f"- Cadência de Pacing: ~{weights.get('pacing_cadence_wpm', 185.0):.0f} WPM a 1.25x (Frases concisas, diretas e com ritmo contínuo de revelação).\n"
            f"- Frequência Média de Tomadas: 1 corte a cada {weights.get('broll_cut_frequency_sec', 3.0):.1f}s (Cenas curtas com termos de busca em inglês focados em radar, arquivo histórico e filmagem documental 4K)."
        )

    get_prompt_guidance = get_prompt_context_for_generation

DEFAULT_ALGORITHM_MEMORY = AlgorithmMemorySystem()

