"""
Módulo de Inteligência Algorítmica, Big Data e Memória de Feedback (.md).
Rastreia a anatomia completa de todos os conteúdos produzidos para o Minuto Inexplicável,
processa métricas de analytics (visualizações, retenção aos 3s, APV %, CTR %, engajamento),
realiza atribuição causal de sucesso e atualiza pesos auxiliares dinâmicos para convergir
na fórmula viral documental sem alucinações e sem repetição de temas.
"""

import os
import json
import time
import math
from typing import Dict, List, Any, Optional, Tuple

try:
    from .logger import app_logger, LogSpan
except ImportError:
    from logger import app_logger, LogSpan

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR = os.path.join(PROJECT_ROOT, "data", "algorithm_memory")

# Pesos auxiliares padrão calibrados para retenção máxima em Shorts documentais de 60s a 90s
DEFAULT_AUXILIARY_WEIGHTS: Dict[str, float] = {
    "hook_curiosity_gap_weight": 0.95,      # Intensidade do gancho nos primeiros 3s (paradoxo/dado chocante)
    "technical_depth_weight": 0.92,         # Nível de profundidade factual (vs termos genéricos)
    "anti_hype_precision_weight": 0.90,     # Penalização severa de clichês e sensacionalismo vazio
    "historical_accuracy_weight": 0.88,     # Presença de documentos desclassificados, datas e arquivos reais
    "telemetry_density_weight": 0.85,       # Presença de dados concretos (profundidade, km, datas, Hz, radiação)
    "pacing_cadence_wpm": 180.0,            # Palavras por minuto ideais (ritmo 1.25x acelerado)
    "broll_cut_frequency_sec": 2.8,         # Tempo médio entre tomadas de corte (em segundos)
    "conflict_and_mystery_weight": 0.82,    # Presença da anomalia inexplicável e teorias científicas
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
        tmp = f"{file_path}.tmp.{time.time()}_{os.getpid()}"
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

    def load_history(self) -> List[Dict[str, Any]]:
        """Carrega o histórico de analytics gravado."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("records", [])
        except Exception as e:
            app_logger.warning(f"[AlgorithmMemory] Erro ao ler analytics_history.json: {str(e)}")
        return []

    def record_video_metrics(
        self,
        video_id: str,
        title: str,
        views: int,
        retention_3s: float,
        apv: float,
        ctr: float = 0.0,
        likes: int = 0,
        comments: int = 0,
        notes: str = "",
        generation_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Registra métricas reais de um vídeo publicado e aciona a recalibração de pesos."""
        records = self.load_history()
        
        # Procura se já existe registro prévio deste vídeo para atualizar
        existing_idx = -1
        for idx, rec in enumerate(records):
            if rec.get("video_id") == video_id or (rec.get("title") == title and title):
                existing_idx = idx
                break

        # Cálculo do Score de Performance Composto (0 a 100)
        # APV (Average Percentage Viewed) tem peso 40%, Retenção aos 3s tem peso 35%, CTR tem peso 15%, Engajamento 10%
        apv_norm = min(100.0, max(0.0, float(apv)))
        ret_norm = min(100.0, max(0.0, float(retention_3s)))
        ctr_norm = min(100.0, max(0.0, float(ctr))) * 5.0 # 10% CTR -> 50 pts
        eng_score = min(100.0, (likes * 2.0 + comments * 5.0) / max(1.0, float(views) / 1000.0))
        composite_score = (apv_norm * 0.40) + (ret_norm * 0.35) + (min(100.0, ctr_norm) * 0.15) + (eng_score * 0.10)

        record_entry = {
            "video_id": video_id,
            "title": title,
            "views": int(views),
            "retention_3s": float(retention_3s),
            "apv": float(apv),
            "ctr": float(ctr),
            "likes": int(likes),
            "comments": int(comments),
            "composite_score": round(composite_score, 2),
            "notes": notes,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "generation_metadata": generation_metadata or {}
        }

        if existing_idx >= 0:
            records[existing_idx] = record_entry
        else:
            records.append(record_entry)

        payload = {
            "version": 1,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_records": len(records),
            "records": records
        }
        self._save_json_atomic(self.history_file, payload)

        # Recalibra os pesos auxiliares com base nos novos dados
        self._recalibrate_weights(records)
        self._regenerate_markdown_memory()
        return record_entry

    def _recalibrate_weights(self, records: List[Dict[str, Any]]):
        """Ajusta sutilmente os pesos auxiliares na direção dos vídeos com melhor score composto."""
        if not records:
            return

        current_weights = self.load_weights()
        top_tier = [r for r in records if r.get("composite_score", 0) >= 70.0]
        low_tier = [r for r in records if r.get("composite_score", 0) < 50.0]

        # Se temos dados suficientes de alto rendimento, reforça atributos vencedores
        if top_tier:
            avg_high_apv = sum(r.get("apv", 0) for r in top_tier) / len(top_tier)
            avg_high_ret = sum(r.get("retention_3s", 0) for r in top_tier) / len(top_tier)

            if avg_high_ret >= 75.0:
                current_weights["hook_curiosity_gap_weight"] = min(0.99, current_weights.get("hook_curiosity_gap_weight", 0.95) + 0.01)
            if avg_high_apv >= 80.0:
                current_weights["technical_depth_weight"] = min(0.98, current_weights.get("technical_depth_weight", 0.92) + 0.01)
                current_weights["anti_hype_precision_weight"] = min(0.98, current_weights.get("anti_hype_precision_weight", 0.90) + 0.01)

        self.save_weights(current_weights)

    def _regenerate_markdown_memory(self):
        """Gera o arquivo executivo ALGORITHM_MEMORY.md com os aprendizados do canal."""
        records = self.load_history()
        weights = self.load_weights()

        total_videos = len(records)
        total_views = sum(r.get("views", 0) for r in records)
        avg_ret = sum(r.get("retention_3s", 0) for r in records) / max(1, total_videos)
        avg_apv = sum(r.get("apv", 0) for r in records) / max(1, total_videos)

        top_videos = sorted(records, key=lambda x: x.get("composite_score", 0), reverse=True)[:5]

        lines = [
            "# 🧠 Memória Algorítmica e Inteligência de Conteúdo — Minuto Inexplicável",
            "",
            f"> **Última Atualização:** {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
            f"> **Base de Vídeos Analisados:** {total_videos} | **Total de Views:** {total_views:,}  ",
            f"> **Retenção Média aos 3s:** {avg_ret:.1f}% | **APV Médio (% Visto):** {avg_apv:.1f}%",
            "",
            "---",
            "",
            "## ⚖️ Pesos Auxiliares Dinâmicos em Operação",
            "",
            "| Parâmetro Algorítmico | Peso Ativo | Função Estratégica na Retenção |",
            "| :--- | :---: | :--- |",
            f"| `hook_curiosity_gap_weight` | **{weights.get('hook_curiosity_gap_weight', 0.95):.2f}** | Impacto e quebra de padrão nos 3 primeiros segundos |",
            f"| `technical_depth_weight` | **{weights.get('technical_depth_weight', 0.92):.2f}** | Densidade documental, dados exatos e profundidade histórica |",
            f"| `anti_hype_precision_weight` | **{weights.get('anti_hype_precision_weight', 0.90):.2f}** | Eliminação implacável de adjetivos vazios e clickbait fraco |",
            f"| `historical_accuracy_weight` | **{weights.get('historical_accuracy_weight', 0.88):.2f}** | Menção a documentos desclassificados, datas e arquivos reais |",
            f"| `telemetry_density_weight` | **{weights.get('telemetry_density_weight', 0.85):.2f}** | Presença de medidas concretas (metros, Hz, km, graus, datas) |",
            f"| `pacing_cadence_wpm` | **{weights.get('pacing_cadence_wpm', 180.0):.1f}** | Velocidade de fala acelerada 1.25x para evitar dispersão |",
            f"| `broll_cut_frequency_sec` | **{weights.get('broll_cut_frequency_sec', 2.8):.1f}s** | Ritmo visual acelerado entre tomadas de corte no YouTube |",
            f"| `comment_trigger_weight` | **{weights.get('comment_trigger_weight', 0.85):.2f}** | Pergunta final polarizadora para forçar engajamento nos comentários |",
            "",
            "---",
            "",
            "## 🏆 Top Vídeos com Maior Retenção e Score Composto",
            ""
        ]

        if top_videos:
            lines.append("| Vídeo / Mistério | Views | Ret. 3s | APV % | Score |")
            lines.append("| :--- | :---: | :---: | :---: | :---: |")
            for tv in top_videos:
                lines.append(f"| {tv.get('title', 'Sem Título')} | {tv.get('views', 0):,} | {tv.get('retention_3s', 0):.1f}% | {tv.get('apv', 0):.1f}% | **{tv.get('composite_score', 0):.1f}** |")
        else:
            lines.append("_Nenhum vídeo registrado com métricas completas ainda. Use `scripts/sync_metrics.py` ou `scripts/feedback_cli.py` para sincronizar._")

        lines.append("")
        content = "\n".join(lines)
        with open(self.memory_md_file, "w", encoding="utf-8") as f:
            f.write(content)

    def get_prompt_context_for_generation(self) -> str:
        """Formata um bloco de diretrizes algorítmicas dinâmicas para ser injetado nos prompts dos Agentes."""
        weights = self.load_weights()
        return (
            f"[DIRETRIZES DA MEMÓRIA ALGORÍTMICA (CONVERGÊNCIA DE RETENÇÃO)]:\n"
            f"- Intensidade do Hook (0 a 1): {weights.get('hook_curiosity_gap_weight', 0.95):.2f} (Iniciar imediatamente com dado intrigante nos primeiros 3s).\n"
            f"- Densidade Documental (0 a 1): {weights.get('technical_depth_weight', 0.92):.2f} (Foco estrito em dados reais, datas, documentos e evidências).\n"
            f"- Tolerância Zero a Sensacionalismo Vazio: {weights.get('anti_hype_precision_weight', 0.90):.2f} (Evite frases genéricas e adjetivos sem fato).\n"
            f"- Ritmo Vocal Recomendado: ~{int(weights.get('pacing_cadence_wpm', 180))} palavras/minuto.\n"
            f"- Cadência de Corte Visual: Trocas de cena a cada ~{weights.get('broll_cut_frequency_sec', 2.8):.1f} segundos."
        )

# Instância padrão global
DEFAULT_ALGORITHM_MEMORY = AlgorithmMemorySystem()
