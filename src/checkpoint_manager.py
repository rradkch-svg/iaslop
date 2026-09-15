import os
import re
import json
import time
import shutil
import difflib
from typing import Dict, Any, List, Optional, Tuple, Union, Set, Callable

try:
    from .logger import app_logger, LogSpan
except ImportError:
    from logger import app_logger, LogSpan

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CHECKPOINT_ROOT = os.environ.get("CHECKPOINT_DIR") or os.path.join(PROJECT_ROOT, "checkpoint")
VIDEOS_PER_BATCH = 10

KNOWN_MYSTERY_ANCHORS = {
    "dyatlov", "kola", "derinkuyu", "marianas", "challenger", "bloop", "century",
    "duga", "wow", "tunguska", "voynich", "mkultra", "gobekli", "tepe", "nazca",
    "yonaguni", "roanoke", "flannan", "bouvet", "sargaco", "sargasso", "antarctica",
    "antartida", "groenlandia", "catatumbo", "marfa", "hessdalen",
    "habbakuk", "montauk", "filadelfia", "nan madol", "anticitera", "antikythera",
    "bagda", "baghdad", "mary celeste", "kic 8462852", "oumuamua", "proxima centauri",
    "movile", "bermudas", "cicada 3301", "shugborough", "taos hum", "varginha",
    "colares", "skinwalker", "rendlesham", "area 51", "dulce", "cheyenne", "diefenbunker",
    "balaklava", "riese", "erebus", "terror", "wilkes", "mirny"
}


class CheckpointManager:
    """
    Gerenciador centralizado de Checkpoints, Batches (batch_0 .. batch_N),
    Vídeos Individuais (video_0 .. video_9) e Blacklist de temas não-repetíveis.
    Garante persistência atômica e auto-recuperação resiliente contra quedas de energia.
    """

    def __init__(self, root_dir: Optional[str] = None, videos_per_batch: int = VIDEOS_PER_BATCH):
        self.root_dir = os.path.abspath(root_dir or DEFAULT_CHECKPOINT_ROOT)
        self.videos_per_batch = videos_per_batch
        self.blacklist_file = os.path.join(self.root_dir, "blacklist.json")
        self.blacklist_txt = os.path.join(self.root_dir, "blacklist.txt")
        self.global_state_file = os.path.join(self.root_dir, "global_state.json")
        
        # Garante a criação da pasta raiz de checkpoints
        os.makedirs(self.root_dir, exist_ok=True)
        self._init_blacklist_if_needed()
        self._init_global_state_if_needed()

    # =========================================================================
    # 1. GESTÃO DE BLACKLIST (TEMAS JÁ UTILIZADOS - EVITAR REPETIÇÃO)
    # =========================================================================

    def _init_blacklist_if_needed(self):
        """Inicializa arquivos de blacklist caso não existam."""
        if not os.path.exists(self.blacklist_file):
            initial_data = {
                "version": 1,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "total_items": 0,
                "items": []
            }
            self._save_json_atomic(self.blacklist_file, initial_data)

        if not os.path.exists(self.blacklist_txt):
            try:
                with open(self.blacklist_txt, "w", encoding="utf-8") as f:
                    f.write("# Blacklist de Temas Já Gravados - Minuto Inexplicável\n")
                    f.write(f"# Criado em: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            except Exception:
                pass

    def load_blacklist(self) -> List[Dict[str, Any]]:
        """Carrega a lista de itens da blacklist."""
        try:
            if os.path.exists(self.blacklist_file):
                with open(self.blacklist_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("items", [])
        except Exception as e:
            app_logger.warning(f"[CheckpointManager] Erro ao carregar blacklist.json: {str(e)}")
        return []

    def get_blacklist_titles(self) -> List[str]:
        """Retorna apenas os títulos e entidades principais da blacklist."""
        items = self.load_blacklist()
        titles = []
        for it in items:
            t = it.get("tema") or it.get("core_entity")
            if t and t not in titles:
                titles.append(t)
        return titles

    def _extract_semantic_fingerprint(self, item: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extrai a impressão digital semântica profunda de um tema ou candidato.
        Analisa título, hook, explicação técnica, tags e termos-chave.
        """
        if isinstance(item, dict):
            tema = item.get("tema", "")
            hook = item.get("hook", "")
            tech = item.get("explicacao_tecnica", "")
            tags = item.get("tags", [])
            raw_entity = item.get("core_entity", "")
        else:
            tema = str(item)
            hook = ""
            tech = ""
            tags = []
            raw_entity = ""

        clean_title = self._normalize_topic_string(tema)
        core_entity = (raw_entity or self._extract_core_entity(tema)).strip()
        clean_entity = self._normalize_topic_string(core_entity)

        # Concatenação de todo o contexto semântico disponível
        tags_text = " ".join(tags) if isinstance(tags, list) else str(tags)
        full_text = f"{tema} {hook} {tech} {tags_text}".lower()
        clean_full = self._normalize_topic_string(full_text)

        # Tokens únicos sem stopwords
        keywords = set(clean_full.split())
        title_tokens = set(clean_title.split())
        entity_tokens = set(clean_entity.split())

        # Marcadores numéricos e anos específicos (ex: 1959, 1977, 1908, 12262, 12km, 18, 150)
        numeric_markers = set(re.findall(r"\b\d+(?:[km|m|mil|graus|minutos|segundos|anos])?\b", full_text))

        # Detecção de âncoras históricas / locais conhecidos com garantia de limite de palavra
        words_in_full = set(clean_full.split())
        words_in_title = set(clean_title.split())
        detected_anchors = set()
        for anchor in KNOWN_MYSTERY_ANCHORS:
            if " " in anchor:
                if anchor in clean_full or anchor in clean_title:
                    detected_anchors.add(anchor)
            else:
                if anchor in words_in_full or anchor in words_in_title:
                    detected_anchors.add(anchor)

        return {
            "tema": tema,
            "hook": hook,
            "tech": tech,
            "clean_title": clean_title,
            "core_entity": core_entity,
            "clean_entity": clean_entity,
            "title_tokens": title_tokens,
            "entity_tokens": entity_tokens,
            "keywords": keywords,
            "numeric_markers": numeric_markers,
            "detected_anchors": detected_anchors,
            "full_text": clean_full
        }

    def _compute_semantic_similarity(self, cand_fp: Dict[str, Any], exist_fp: Dict[str, Any]) -> Tuple[float, str]:
        """
        Calcula o grau de sobreposição semântica em essência entre dois temas.
        Retorna (score: float entre 0.0 e 1.0, reason: str).
        """
        # 1. Correspondência exata de título normalizado
        if cand_fp["clean_title"] and cand_fp["clean_title"] == exist_fp["clean_title"]:
            return 1.0, f"Título idêntico a '{exist_fp['tema']}'"

        # 2. Correspondência exata ou embutida de entidade principal
        cand_ent = cand_fp["clean_entity"]
        exist_ent = exist_fp["clean_entity"]
        if cand_ent and exist_ent:
            if cand_ent == exist_ent:
                return 0.95, f"Mesma entidade principal ('{exist_fp['core_entity']}') em '{exist_fp['tema']}'"
            if len(cand_ent) >= 4 and len(exist_ent) >= 4:
                if cand_ent in exist_ent or exist_ent in cand_ent:
                    return 0.90, f"Entidade central coincidente ('{exist_fp['core_entity']}') em '{exist_fp['tema']}'"

        # 3. Sobreposição de Âncoras Históricas/Locais do Mistério
        common_anchors = cand_fp["detected_anchors"].intersection(exist_fp["detected_anchors"])
        if common_anchors:
            anchor_name = list(common_anchors)[0]
            # Se compartilha a mesma âncora de mistério, verifica sobreposição de palavras-chave
            kw_overlap = cand_fp["keywords"].intersection(exist_fp["keywords"])
            if len(kw_overlap) >= 2 or len(cand_fp["title_tokens"].intersection(exist_fp["title_tokens"])) >= 1:
                return 0.90, f"Mesmo mistério/local âncora ('{anchor_name.upper()}') abordado em '{exist_fp['tema']}'"

        # 4. Sobreposição de tokens da entidade
        if cand_fp["entity_tokens"] and exist_fp["entity_tokens"]:
            ent_overlap = cand_fp["entity_tokens"].intersection(exist_fp["entity_tokens"])
            if len(ent_overlap) >= 2:
                overlap_words = " ".join(ent_overlap)
                return 0.85, f"Sobreposição de termos centrais da entidade ('{overlap_words}') com '{exist_fp['tema']}'"

        # 5. Marcadores numéricos e anos específicos (ex: 1959, 1977, 12km) com contexto
        num_overlap = cand_fp["numeric_markers"].intersection(exist_fp["numeric_markers"])
        specific_nums = {
            n for n in num_overlap 
            if (len(n) == 4 and n.isdigit() and (n.startswith("18") or n.startswith("19") or n.startswith("20"))) 
            or any(unit in n for unit in ["km", "hz", "mil", "graus", "kwh", "atm"])
        }
        if specific_nums:
            kw_overlap = cand_fp["keywords"].intersection(exist_fp["keywords"])
            title_overlap = cand_fp["title_tokens"].intersection(exist_fp["title_tokens"])
            if len(kw_overlap) >= 5 and len(title_overlap) >= 1:
                num_str = list(specific_nums)[0]
                return 0.82, f"Mesmos dados históricos/quantitativos ('{num_str}') e termos em '{exist_fp['tema']}'"

        # 6. Índice de Jaccard no vocabulário semântico total (título + hook + explicação)
        union_kw = cand_fp["keywords"].union(exist_fp["keywords"])
        if union_kw:
            intersection_kw = cand_fp["keywords"].intersection(exist_fp["keywords"])
            jaccard = len(intersection_kw) / len(union_kw)
            if jaccard >= 0.40 or len(intersection_kw) >= 5:
                top_words = list(intersection_kw)[:4]
                return min(0.95, 0.50 + jaccard), f"Alta sobreposição de contexto ({len(intersection_kw)} termos em comum: {top_words}) com '{exist_fp['tema']}'"

        # 7. Similaridade difflib / Levenshtein de título e entidade
        seq_title = difflib.SequenceMatcher(None, cand_fp["clean_title"], exist_fp["clean_title"]).ratio()
        if seq_title >= 0.65:
            return seq_title, f"Similaridade textual alta ({seq_title:.0%}) com '{exist_fp['tema']}'"

        return 0.0, ""

    def is_in_blacklist(
        self,
        candidate_topic: Union[str, Dict[str, Any]],
        threshold: float = 0.60,
        ai_auditor: Optional[Any] = None
    ) -> Tuple[bool, str]:
        """
        Verifica se um tema proposto é idêntico ou semanticamente equivalente em essência
        a um tema já gravado na blacklist, utilizando análise multi-camada (entidades,
        âncoras, n-grams, contexto factual e auditoria por IA).
        """
        if not candidate_topic:
            return False, ""

        cand_fp = self._extract_semantic_fingerprint(candidate_topic)
        if not cand_fp["clean_title"] and not cand_fp["keywords"]:
            return False, ""

        items = self.load_blacklist()
        if not items:
            return False, ""

        highest_sim = 0.0
        best_reason = ""
        suspicious_matches = []

        for it in items:
            exist_fp = self._extract_semantic_fingerprint(it)
            sim, reason = self._compute_semantic_similarity(cand_fp, exist_fp)
            if sim > highest_sim:
                highest_sim = sim
                best_reason = reason
            if sim >= 0.40:
                suspicious_matches.append(it)

        # 1. Bloqueio determinístico local por alta similaridade de essência
        if highest_sim >= threshold:
            return True, f"Repetição temática em essência ({highest_sim:.0%}): {best_reason}"

        # 2. Arbitragem por IA para casos suspeitos/fronteiriços
        if suspicious_matches and ai_auditor is not None and hasattr(ai_auditor, "check_duplicate_essence"):
            candidate_dict = candidate_topic if isinstance(candidate_topic, dict) else {"tema": str(candidate_topic)}
            is_dup, ai_reason = ai_auditor.check_duplicate_essence(
                candidate_topic=candidate_dict,
                blacklist_items=suspicious_matches[:15]
            )
            if is_dup:
                return True, f"Auditor de IA identificou repetição de essência: {ai_reason}"

        return False, ""

    def add_to_blacklist(self, topic_data: Dict[str, Any], batch_name: str, video_name: str) -> bool:
        """
        Registra imediatamente um tema na Blacklist para garantir que nunca mais se repita.
        Grava o perfil semântico completo tanto em JSON estruturado quanto em TXT legível.
        """
        tema_title = topic_data.get("tema", "").strip()
        if not tema_title:
            return False

        core_entity = self._extract_core_entity(tema_title)
        fp = self._extract_semantic_fingerprint(topic_data)

        items = self.load_blacklist()
        
        # Evita duplicar no próprio arquivo se já estiver presente
        for it in items:
            if it.get("tema") == tema_title:
                return True

        new_entry = {
            "tema": tema_title,
            "core_entity": core_entity,
            "hook": topic_data.get("hook", ""),
            "explicacao_tecnica": topic_data.get("explicacao_tecnica", ""),
            "tags": topic_data.get("tags", []),
            "keywords": sorted(list(fp["keywords"]))[:25],
            "batch": batch_name,
            "video": video_name,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
        }
        items.append(new_entry)

        payload = {
            "version": 2,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_items": len(items),
            "items": items
        }

        self._save_json_atomic(self.blacklist_file, payload)

        # Atualiza blacklist.txt de forma legível
        try:
            with open(self.blacklist_txt, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{batch_name}/{video_name}] {tema_title}\n")
        except Exception as e:
            app_logger.warning(f"[CheckpointManager] Erro ao gravar blacklist.txt: {str(e)}")

        app_logger.info(f"[CheckpointManager] Blacklist atualizada com perfil semântico: '{tema_title}' ({batch_name}/{video_name})")
        return True


    # =========================================================================
    # 2. GESTÃO DE ESTADO GLOBAL E RECUPERAÇÃO DE BATCHES
    # =========================================================================

    def _init_global_state_if_needed(self):
        """Inicializa ou reconstrói o arquivo global_state.json."""
        if not os.path.exists(self.global_state_file):
            self.rebuild_global_state_from_disk()

    def load_global_state(self) -> Dict[str, Any]:
        """Lê o estado global com fallback para reconstrução a partir do disco."""
        try:
            if os.path.exists(self.global_state_file):
                with open(self.global_state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            app_logger.warning(f"[CheckpointManager] Erro ao ler global_state.json: {str(e)}. Reconstruindo...")
        return self.rebuild_global_state_from_disk()

    def save_global_state(self, state: Dict[str, Any]):
        """Salva o estado global de forma atômica."""
        state["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._save_json_atomic(self.global_state_file, state)

    def rebuild_global_state_from_disk(self) -> Dict[str, Any]:
        """
        Escaneia fisicamente a pasta checkpoint/ no disco e reconstrói o estado global exato.
        Mecanismo crucial para recuperação de pane ou falta de luz.
        """
        app_logger.info("[CheckpointManager] Escaneando disco para reconstruir estado global...")
        
        batch_dirs = []
        if os.path.exists(self.root_dir):
            for name in os.listdir(self.root_dir):
                if os.path.isdir(os.path.join(self.root_dir, name)) and name.startswith("batch_"):
                    try:
                        num = int(name.split("_")[1])
                        batch_dirs.append((num, name))
                    except (ValueError, IndexError):
                        pass

        batch_dirs.sort(key=lambda x: x[0])
        
        batches_dict = {}
        total_completed_videos = 0
        current_active_batch_idx = 0

        for num, b_name in batch_dirs:
            b_dir = os.path.join(self.root_dir, b_name)
            
            # Checa vídeos dentro deste batch
            videos_status = {}
            completed_in_batch = 0

            for v_idx in range(self.videos_per_batch):
                v_name = f"video_{v_idx}"
                v_dir = os.path.join(b_dir, v_name)
                v_ckpt_path = os.path.join(v_dir, "checkpoint.json")
                
                v_status = "PENDING"
                if os.path.exists(v_ckpt_path):
                    try:
                        with open(v_ckpt_path, "r", encoding="utf-8") as f:
                            v_data = json.load(f)
                            v_status = v_data.get("status", "PENDING")
                    except:
                        pass
                
                # Validação física de integridade
                final_video_file1 = os.path.join(v_dir, "final_video.mp4")
                final_video_file2 = os.path.join(v_dir, "final_output.mp4")
                if (os.path.exists(final_video_file1) and os.path.getsize(final_video_file1) > 100_000) or (os.path.exists(final_video_file2) and os.path.getsize(final_video_file2) > 100_000):
                    v_status = "COMPLETED"

                videos_status[v_name] = v_status
                if v_status == "COMPLETED":
                    completed_in_batch += 1
                    total_completed_videos += 1

            batch_status = "COMPLETED" if completed_in_batch >= self.videos_per_batch else "IN_PROGRESS"
            batches_dict[b_name] = {
                "batch_index": num,
                "status": batch_status,
                "completed_videos_count": completed_in_batch,
                "total_videos": self.videos_per_batch,
                "videos": videos_status
            }

            if batch_status == "IN_PROGRESS" and current_active_batch_idx == 0:
                current_active_batch_idx = num

        # Se todos os batches existentes estiverem completos, o ativo é o próximo
        if batch_dirs:
            last_num = batch_dirs[-1][0]
            if batches_dict[batch_dirs[-1][1]]["status"] == "COMPLETED":
                current_active_batch_idx = last_num + 1

        state = {
            "version": 1,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "current_batch_index": current_active_batch_idx,
            "total_videos_completed": total_completed_videos,
            "batches": batches_dict
        }

        self._save_json_atomic(self.global_state_file, state)
        return state

    # =========================================================================
    # 3. GESTÃO DE CHECKPOINT POR VÍDEO (RESTAURAÇÃO DE ETAPAS)
    # =========================================================================

    def get_batch_dir(self, batch_index: int) -> str:
        """Retorna o caminho da pasta do batch (ex: checkpoint/batch_0)."""
        b_dir = os.path.join(self.root_dir, f"batch_{batch_index}")
        os.makedirs(b_dir, exist_ok=True)
        return b_dir

    def get_video_dir(self, batch_index: int, video_index: int) -> str:
        """Retorna o caminho da pasta do vídeo (ex: checkpoint/batch_0/video_3)."""
        b_dir = self.get_batch_dir(batch_index)
        v_dir = os.path.join(b_dir, f"video_{video_index}")
        os.makedirs(v_dir, exist_ok=True)
        return v_dir

    def get_video_checkpoint_path(self, batch_index: int, video_index: int) -> str:
        """Retorna o caminho do arquivo checkpoint.json do vídeo."""
        v_dir = self.get_video_dir(batch_index, video_index)
        return os.path.join(v_dir, "checkpoint.json")

    def generate_batch_cleanup_script(self, batch_index: int) -> str:
        """
        Gera o script 'limpar_conteudo.bat' no diretório do batch especificado.
        Remove todos os arquivos pesados de mídia (vídeos, áudios, b-roll, legendas)
        de cada pasta de vídeo do lote, preservando rigorosamente os metadados (metadata.txt).
        """
        b_dir = self.get_batch_dir(batch_index)
        script_path = os.path.join(b_dir, "limpar_conteudo.bat")

        script_content = (
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            "setlocal enabledelayedexpansion\r\n"
            "\r\n"
            "echo ========================================================\r\n"
            "echo   Minuto Inexplicavel - Limpeza de Conteudo do Batch\r\n"
            "echo   Preservando exclusivamente os metadados (metadata.txt)\r\n"
            "echo ========================================================\r\n"
            "echo.\r\n"
            "set \"BATCH_DIR=%~dp0\"\r\n"
            "echo Diretorio do Batch: %BATCH_DIR%\r\n"
            "echo.\r\n"
            "set /a PROCESSED_COUNT=0\r\n"
            "\r\n"
            "for /d %%D in (\"%BATCH_DIR%video_*\") do (\r\n"
            "    if exist \"%%D\" (\r\n"
            "        echo [Limpando] %%~nxD...\r\n"
            "        del /q /f \"%%D\\*.mp4\" 2>nul\r\n"
            "        del /q /f \"%%D\\*.mp3\" 2>nul\r\n"
            "        del /q /f \"%%D\\*.wav\" 2>nul\r\n"
            "        del /q /f \"%%D\\*.ass\" 2>nul\r\n"
            "        del /q /f \"%%D\\*.jpg\" 2>nul\r\n"
            "        del /q /f \"%%D\\*.jpeg\" 2>nul\r\n"
            "        del /q /f \"%%D\\*.png\" 2>nul\r\n"
            "        del /q /f \"%%D\\scenes_concat.txt\" 2>nul\r\n"
            "        if exist \"%%D\\broll\" (\r\n"
            "            rmdir /s /q \"%%D\\broll\" 2>nul\r\n"
            "        )\r\n"
            "        set /a PROCESSED_COUNT+=1\r\n"
            "    )\r\n"
            ")\r\n"
            "\r\n"
            "echo.\r\n"
            "echo ========================================================\r\n"
            "echo   Limpeza concluida! !PROCESSED_COUNT! videos processados.\r\n"
            "echo   Espaco pesado liberado com sucesso no PC.\r\n"
            "echo   Metadados (metadata.txt) mantidos intactos.\r\n"
            "echo ========================================================\r\n"
            "echo.\r\n"
            "if \"%1\"==\"--silent\" goto end_script\r\n"
            "if \"%1\"==\"-y\" goto end_script\r\n"
            "pause\r\n"
            ":end_script\r\n"
        )
        with open(script_path, "w", encoding="utf-8", newline="") as f:
            f.write(script_content)
        return script_path

    def clean_single_video_media(
        self,
        batch_index: int,
        video_index: int,
        youtube_url: Optional[str] = None,
        scheduled_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executa limpeza física dos arquivos de mídia pesados de um único vídeo recém-postado/agendado,
        preservando estritamente metadata.txt, checkpoint.json e dissertacao.txt.
        Registra no checkpoint o link do YouTube e o horário de agendamento.
        """
        v_dir = self.get_video_dir(batch_index, video_index)
        removed_files = 0
        freed_bytes = 0

        if not os.path.exists(v_dir):
            return {"success": False, "error": f"Diretório não encontrado: {v_dir}", "freed_mb": 0.0}

        media_extensions = {".mp4", ".mp3", ".wav", ".ass", ".jpg", ".jpeg", ".png"}
        keep_filenames = {"metadata.txt", "checkpoint.json", "dissertacao.txt", "limpar_conteudo.bat"}

        # 1. Remove pasta broll se existir
        broll_dir = os.path.join(v_dir, "broll")
        if os.path.exists(broll_dir):
            try:
                for root, _, files in os.walk(broll_dir):
                    for file in files:
                        fp = os.path.join(root, file)
                        freed_bytes += os.path.getsize(fp)
                        removed_files += 1
                shutil.rmtree(broll_dir, ignore_errors=True)
            except Exception as e:
                app_logger.warning(f"[CheckpointManager] Erro ao remover broll em {v_dir}: {e}")

        # 2. Remove arquivos pesados na pasta do vídeo
        for item in os.listdir(v_dir):
            item_path = os.path.join(v_dir, item)
            if not os.path.isfile(item_path):
                continue
            if item in keep_filenames:
                continue

            _, ext = os.path.splitext(item)
            if ext.lower() in media_extensions or item == "scenes_concat.txt":
                try:
                    sz = os.path.getsize(item_path)
                    os.remove(item_path)
                    freed_bytes += sz
                    removed_files += 1
                except Exception as e:
                    app_logger.warning(f"[CheckpointManager] Erro ao deletar {item_path}: {e}")

        # 3. Atualiza checkpoint do vídeo indicando que foi limpo
        ckpt = self.load_video_checkpoint(batch_index, video_index)
        ckpt["cleaned"] = True
        ckpt["cleaned_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        if youtube_url:
            ckpt["youtube_url"] = youtube_url
        if scheduled_time:
            ckpt["youtube_scheduled_time"] = scheduled_time
        self.save_video_checkpoint(batch_index, video_index, ckpt)

        freed_mb = round(freed_bytes / (1024 * 1024), 2)
        app_logger.info(f"[CheckpointManager] 🧹 Limpeza individual de batch_{batch_index}/video_{video_index}: {removed_files} arquivos removidos ({freed_mb} MB liberados).")

        return {
            "success": True,
            "batch_index": batch_index,
            "video_index": video_index,
            "removed_files": removed_files,
            "freed_bytes": freed_bytes,
            "freed_mb": freed_mb,
            "youtube_url": youtube_url,
            "youtube_scheduled_time": scheduled_time
        }

    def clean_batch_media(self, batch_index: int) -> Dict[str, Any]:
        """
        Executa limpeza física dos arquivos de mídia de todos os vídeos de um batch,
        preservando estritamente os arquivos de metadados (metadata.txt, checkpoint.json, dissertacao.txt).
        """
        total_removed = 0
        total_freed = 0

        for v_idx in range(self.videos_per_batch):
            res = self.clean_single_video_media(batch_index, v_idx)
            total_removed += res.get("removed_files", 0)
            total_freed += res.get("freed_bytes", 0)

        # Garante que o script limpar_conteudo.bat permaneça no batch
        self.generate_batch_cleanup_script(batch_index)

        return {
            "batch_index": batch_index,
            "removed_files": total_removed,
            "freed_bytes": total_freed,
            "freed_mb": round(total_freed / (1024 * 1024), 2)
        }

    def load_video_checkpoint(self, batch_index: int, video_index: int) -> Dict[str, Any]:
        """Carrega os dados de checkpoint de um vídeo específico."""
        ckpt_path = self.get_video_checkpoint_path(batch_index, video_index)
        if os.path.exists(ckpt_path):
            try:
                with open(ckpt_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                app_logger.warning(f"[CheckpointManager] Erro ao ler checkpoint ({batch_index}/{video_index}): {str(e)}")
        
        # Checkpoint novo padrão
        return {
            "batch_index": batch_index,
            "video_index": video_index,
            "batch_name": f"batch_{batch_index}",
            "video_name": f"video_{video_index}",
            "status": "PENDING", # PENDING, TOPIC_READY, STORYBOARD_READY, AUDIO_READY, SUBTITLES_READY, SCENES_READY, COMPLETED, FAILED
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "topic": {},
            "storyboard": [],
            "audio_file": "audio.mp3",
            "audio_duration": 0.0,
            "words_timing": [],
            "subtitles_file": "subtitles.ass",
            "scene_clips": [],
            "scene_audits": [],
            "final_video_file": "final_video.mp4",
            "final_video_size_bytes": 0,
            "error": None,
            "retry_count": 0
        }

    def save_video_checkpoint(self, batch_index: int, video_index: int, data: Dict[str, Any]):
        """Salva atomicamente o checkpoint do vídeo."""
        data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        ckpt_path = self.get_video_checkpoint_path(batch_index, video_index)
        self._save_json_atomic(ckpt_path, data)

    def determine_video_resume_stage(self, batch_index: int, video_index: int) -> Tuple[str, Dict[str, Any]]:
        """
        Analisa o checkpoint gravado e os arquivos físicos no disco para determinar
        exatamente de qual etapa retomar a geração deste vídeo.
        
        Retorna (stage_name, checkpoint_data):
        - 'COMPLETED': Vídeo final renderizado e íntegro no disco.
        - 'RENDER_FINAL': Todas as cenas, áudio e legendas prontos, falta apenas o render do FFmpeg.
        - 'PROCESS_SCENES': Áudio e storyboard prontos, faltam baixar/auditar clipes.
        - 'GENERATE_SUBTITLES': Áudio pronto, falta compilar legendas ASS.
        - 'GENERATE_AUDIO': Storyboard pronto, falta gerar narração Edge-TTS.
        - 'GENERATE_STORYBOARD': Tema pronto, falta roteirizar cenas.
        - 'GENERATE_TOPIC': Vídeo em branco, necessita propor novo tema com IA.
        """
        ckpt = self.load_video_checkpoint(batch_index, video_index)
        v_dir = self.get_video_dir(batch_index, video_index)
        
        final_mp4 = os.path.join(v_dir, ckpt.get("final_video_file", "final_video.mp4"))
        audio_mp3 = os.path.join(v_dir, ckpt.get("audio_file", "audio.mp3"))
        subtitles_ass = os.path.join(v_dir, ckpt.get("subtitles_file", "subtitles.ass"))
        storyboard = ckpt.get("storyboard", [])
        topic = ckpt.get("topic", {})

        # 1. Verifica se vídeo final já está 100% concluído e íntegro no disco
        final_candidates = [
            os.path.join(v_dir, ckpt.get("final_video", "final_output.mp4")),
            os.path.join(v_dir, ckpt.get("final_video_file", "final_video.mp4")),
            os.path.join(v_dir, "final_output.mp4"),
            os.path.join(v_dir, "final_video.mp4")
        ]
        for f_cand in final_candidates:
            if os.path.exists(f_cand) and os.path.getsize(f_cand) > 100_000:
                ckpt["status"] = "COMPLETED"
                ckpt["final_video_size_bytes"] = os.path.getsize(f_cand)
                ckpt["final_video_path"] = f_cand
                self.save_video_checkpoint(batch_index, video_index, ckpt)
                return "COMPLETED", ckpt

        # Se o vídeo já foi concluído e seu conteúdo pesado foi limpo para liberar espaço
        if ckpt.get("status") == "COMPLETED" and (ckpt.get("completed_at") or ckpt.get("cleaned") or ckpt.get("final_video_size_bytes")):
            return "COMPLETED", ckpt

        # 2. Verifica se o tema foi definido
        if not topic or not topic.get("tema"):
            return "GENERATE_TOPIC", ckpt

        # 3. Verifica se storyboard foi gerado
        if not storyboard or not isinstance(storyboard, list) or len(storyboard) < 3:
            return "GENERATE_STORYBOARD", ckpt

        # 4. Verifica se áudio foi sintetizado
        if not os.path.exists(audio_mp3) or os.path.getsize(audio_mp3) < 5_000 or not ckpt.get("words_timing"):
            return "GENERATE_AUDIO", ckpt

        # 5. Verifica se legendas ASS existem
        if not os.path.exists(subtitles_ass) or os.path.getsize(subtitles_ass) < 10:
            return "GENERATE_SUBTITLES", ckpt

        # 6. Verifica se clipes de cenas existem no disco e foram devidamente auditados/aprovados
        if ckpt.get("status") == "PROCESS_SCENES":
            return "PROCESS_SCENES", ckpt

        scenes_media = ckpt.get("scenes_media", {})
        scene_clips = ckpt.get("scene_clips", [])
        has_valid_scenes = False

        if scenes_media and isinstance(scenes_media, dict):
            has_valid_scenes = any(
                os.path.exists(m.get("video_file", "") or m.get("file", "")) and
                os.path.getsize(m.get("video_file", "") or m.get("file", "")) > 10_000 and
                m.get("success", False) and
                m.get("review", {}).get("aprovado", True) and
                float(m.get("review", {}).get("nota_relevancia", 10.0)) >= 6.0
                for m in scenes_media.values() if isinstance(m, dict)
            )
        elif scene_clips and isinstance(scene_clips, list):
            has_valid_scenes = any(
                os.path.exists(cp) and os.path.getsize(cp) > 10_000
                for cp in scene_clips
            )

        if not has_valid_scenes:
            return "PROCESS_SCENES", ckpt

        # 7. Todas as partes estão prontas, falta renderizar
        return "RENDER_FINAL", ckpt

    def get_next_work_target(self) -> Tuple[int, int, str, str]:
        """
        Determina o próximo batch e vídeo que precisa de trabalho.
        Garante transição automática sem pular nenhum vídeo ou batch incompleto.
        """
        state = self.load_global_state()

        # Coleta todos os números de batches existentes no disco
        batch_nums = []
        if os.path.exists(self.root_dir):
            for name in os.listdir(self.root_dir):
                if os.path.isdir(os.path.join(self.root_dir, name)) and name.startswith("batch_"):
                    try:
                        batch_nums.append(int(name.split("_")[1]))
                    except (ValueError, IndexError):
                        pass
        batch_nums = sorted(list(set(batch_nums)))
        max_batch = max(batch_nums, default=0)
        search_range = batch_nums + list(range(max_batch + 1, max_batch + 100))

        for b_idx in search_range:
            completed_in_this_batch = 0
            first_pending_v = None

            for v_idx in range(self.videos_per_batch):
                stage, ckpt = self.determine_video_resume_stage(b_idx, v_idx)
                if stage == "COMPLETED":
                    completed_in_this_batch += 1
                elif first_pending_v is None:
                    first_pending_v = v_idx

            if completed_in_this_batch < self.videos_per_batch and first_pending_v is not None:
                state["current_batch_index"] = b_idx
                self.save_global_state(state)
                return b_idx, first_pending_v, f"batch_{b_idx}", f"video_{first_pending_v}"

        # Se todos estiverem completos, avança para o próximo novo batch
        next_new_batch = max_batch + 1
        state["current_batch_index"] = next_new_batch
        self.save_global_state(state)
        return next_new_batch, 0, f"batch_{next_new_batch}", "video_0"

    def get_next_pending_target(self) -> Tuple[int, int]:
        """
        Retorna uma tupla (batch_index, video_index) do próximo vídeo pendente de produção.
        """
        b_idx, v_idx, _, _ = self.get_next_work_target()
        return b_idx, v_idx

    def mark_video_completed(self, batch_index: int, video_index: int, final_video_path: str):

        """Marca o vídeo como COMPLETED e atualiza estado global e batch."""
        ckpt = self.load_video_checkpoint(batch_index, video_index)
        ckpt["status"] = "COMPLETED"
        ckpt["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        if os.path.exists(final_video_path):
            ckpt["final_video_size_bytes"] = os.path.getsize(final_video_path)
            ckpt["final_video_path"] = final_video_path
        self.save_video_checkpoint(batch_index, video_index, ckpt)

        # Atualiza o estado global
        state = self.load_global_state()
        batches = state.setdefault("batches", {})
        b_name = f"batch_{batch_index}"
        b_info = batches.setdefault(b_name, {
            "batch_index": batch_index,
            "status": "IN_PROGRESS",
            "completed_videos_count": 0,
            "total_videos": self.videos_per_batch,
            "videos": {}
        })

        b_info.setdefault("videos", {})[f"video_{video_index}"] = "COMPLETED"
        
        # Conta vídeos concluídos neste batch
        completed_cnt = sum(1 for st in b_info["videos"].values() if st == "COMPLETED")
        b_info["completed_videos_count"] = completed_cnt
        if completed_cnt >= self.videos_per_batch:
            b_info["status"] = "COMPLETED"
            b_info["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            state["current_batch_index"] = max(state.get("current_batch_index", 0), batch_index + 1)

        # Recalcula total de vídeos concluídos
        total_comp = 0
        for b in batches.values():
            for v_st in b.get("videos", {}).values():
                if v_st == "COMPLETED":
                    total_comp += 1
        state["total_videos_completed"] = total_comp
        self.save_global_state(state)

    # =========================================================================
    # HELPERS INTERNOS
    # =========================================================================

    def _normalize_topic_string(self, text: str) -> str:
        """Normaliza uma string de tema para comparação robusta."""
        t = text.lower()
        t = re.sub(r"[^\w\s]", " ", t)
        words = [w.strip() for w in t.split() if w.strip() and len(w.strip()) > 1]
        # Remove stopwords comuns
        stopwords = {"o", "a", "os", "as", "de", "da", "do", "dos", "das", "em", "no", "na", "nos", "nas",
                     "por", "que", "com", "como", "funciona", "segredo", "fisica", "engenharia", "tudo", "sobre"}
        filtered = [w for w in words if w not in stopwords]
        return " ".join(filtered)

    def _extract_core_entity(self, text: str) -> str:
        """Extrai o mistério/local/projeto principal do tema."""
        parts = text.split(":")
        main_part = parts[0] if len(parts) > 1 else text
        cleaned = re.sub(r"^(O Segredo d[oa]|Como funciona o|Por que o|A física d[oa]|A engenharia d[oa]|Tudo sobre o|O Mistério d[oa]|A Base Secreta d[oa]|O Incidente d[oa]|A Verdade sobre|O que há no fundo d[oa]|O Projeto Secreto|A História d[oa]|O Caso d[oa]|A Anomalia d[oa])\s*", "", main_part, flags=re.IGNORECASE)
        cleaned = re.sub(r"[^\w\s\-\.]", " ", cleaned)
        cleaned = re.sub(r"\b(e seu|e sua|no|na|com|de|da|do|dos|das|para|sobre|o|a|os|as|sob o gelo|enterrada|secreta|misteriosa)\b", " ", cleaned, flags=re.IGNORECASE)
        words = [w.strip() for w in cleaned.split() if w.strip()]
        return " ".join(words[:6]) if words else text.strip()

    def _save_json_atomic(self, file_path: str, data: Dict[str, Any]):
        """Grava JSON de forma atômica para evitar corrupção em caso de queda de energia."""
        temp_file = f"{file_path}.tmp_{os.getpid()}_{int(time.time()*1000)}"
        parent_dir = os.path.dirname(file_path)
        os.makedirs(parent_dir, exist_ok=True)
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            # Replace atômico
            if os.path.exists(file_path):
                os.replace(temp_file, file_path)
            else:
                os.rename(temp_file, file_path)
        except Exception as e:
            app_logger.error(f"[CheckpointManager] Erro na gravação atômica de '{file_path}': {str(e)}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            raise e
