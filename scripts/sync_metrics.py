"""
Script de Sincronização de Métricas do YouTube & Memória Algorítmica.
Lê o arquivo METRICAS_VIDEOS.csv (ou METRICAS_VIDEOS.md) na raiz do projeto,
ingere as visualizações e retenções informadas pelo criador de conteúdo,
e recalibra a convergência algorítmica da IA.

Uso:
    python scripts/sync_metrics.py
    python scripts/sync_metrics.py --export-only
    python scripts/sync_metrics.py --scan-checkpoints
"""

import os
import sys
import csv
import re
import argparse

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) in ("src", "scripts") else CURRENT_DIR
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

from algorithm_memory import AlgorithmMemorySystem, DEFAULT_ALGORITHM_MEMORY

def sync_from_csv(csv_path: str, memory_sys: AlgorithmMemorySystem) -> int:
    """Lê linhas de METRICAS_VIDEOS.csv e sincroniza com a memória algorítmica."""
    if not os.path.exists(csv_path):
        print(f"⚠️ Arquivo CSV '{csv_path}' não encontrado.")
        return 0

    count = 0
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            batch = row.get("batch", "").strip()
            video = row.get("video", "").strip()
            vid_id = f"{batch}/{video}" if (batch and video) else row.get("video_id", "").strip()
            titulo = row.get("titulo", "").strip()
            
            try:
                views = int(re.sub(r"[^\d]", "", row.get("visualizacoes", "0")) or 0)
                ret_str = row.get("retencao_3s_pct", "0").replace(",", ".")
                ret_3s = float(re.search(r"\d+(\.\d+)?", ret_str).group(0)) if re.search(r"\d+(\.\d+)?", ret_str) else 0.0
                
                apv_str = row.get("apv_pct", "0").replace(",", ".")
                apv = float(re.search(r"\d+(\.\d+)?", apv_str).group(0)) if re.search(r"\d+(\.\d+)?", apv_str) else 0.0
                
                ctr_str = row.get("ctr_pct", "0").replace(",", ".")
                ctr = float(re.search(r"\d+(\.\d+)?", ctr_str).group(0)) if re.search(r"\d+(\.\d+)?", ctr_str) else 0.0
                
                likes = int(re.sub(r"[^\d]", "", row.get("likes", "0")) or 0)
                comments = int(re.sub(r"[^\d]", "", row.get("comentarios", "0")) or 0)
                notes = row.get("observacoes", "").strip()

                if vid_id or titulo:
                    memory_sys.record_video_metrics(
                        video_id=vid_id or titulo,
                        title=titulo,
                        views=views,
                        retention_3s=ret_3s,
                        apv=apv,
                        ctr=ctr,
                        likes=likes,
                        comments=comments,
                        notes=notes
                    )
                    count += 1
            except Exception as e:
                print(f"⚠️ Erro ao processar linha do CSV ({row}): {str(e)}")

    return count

def main():
    parser = argparse.ArgumentParser(description="Sincronizador de Métricas do YouTube & Memória Algorítmica")
    parser.add_argument("--csv", default=os.path.join(PROJECT_ROOT, "METRICAS_VIDEOS.csv"), help="Caminho do CSV de métricas")
    args = parser.parse_args()

    print("=" * 70)
    print("📈 MINUTO INEXPLICÁVEL — SINCRONIZAÇÃO DE MÉTRICAS & FEEDBACK DA IA")
    print("=" * 70)
    
    synced = sync_from_csv(args.csv, DEFAULT_ALGORITHM_MEMORY)
    print(f"\n✅ Total de {synced} registros sincronizados com a Memória Algorítmica.")
    print(f"📄 Resumo analítico atualizado em: {DEFAULT_ALGORITHM_MEMORY.memory_md_file}")
    
    weights = DEFAULT_ALGORITHM_MEMORY.load_weights()
    print("\n⚖️ Pesos Auxiliares Dinâmicos Atuais:")
    for k, v in weights.items():
        print(f"   • {k}: {v:.2f}")

if __name__ == "__main__":
    main()
