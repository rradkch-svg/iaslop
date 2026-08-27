"""
Script CLI para Ingestão de Feedback Analítico e Inspeção da Memória Algorítmica (.md).
Permite ao criador de conteúdo inserir as métricas reais retornadas pelo YouTube Shorts
(Visualizações, Retenção aos 3s %, APV %, CTR %, Likes, Comentários) para calibrar os pesos
auxiliares e orientar a IA na geração de novos conteúdos de alta retenção sem repetir temas.

Uso:
    python scripts/feedback_cli.py --list
    python scripts/feedback_cli.py --input batch_1/video_0 --views 45000 --retention 78.5 --apv 88.0 --ctr 11.2 --notes "Excelente engajamento no mistério do reator"
    python scripts/feedback_cli.py --memory
    python scripts/feedback_cli.py --weights
"""

import os
import sys
import argparse
import time

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

def main():
    parser = argparse.ArgumentParser(description="CLI de Feedback Analítico e Memória Algorítmica")
    parser.add_argument("--list", action="store_true", help="Lista todos os vídeos registrados com métricas")
    parser.add_argument("--weights", action="store_true", help="Exibe os pesos auxiliares ativos da IA")
    parser.add_argument("--memory", action="store_true", help="Exibe o conteúdo completo do ALGORITHM_MEMORY.md")
    parser.add_argument("--input", type=str, help="ID do vídeo (ex: batch_0/video_1)")
    parser.add_argument("--title", type=str, default="", help="Título do vídeo")
    parser.add_argument("--views", type=int, default=0, help="Total de visualizações")
    parser.add_argument("--retention", type=float, default=0.0, help="Retenção nos primeiros 3s (%)")
    parser.add_argument("--apv", type=float, default=0.0, help="Porcentagem média visualizada (%)")
    parser.add_argument("--ctr", type=float, default=0.0, help="Taxa de cliques / CTR (%)")
    parser.add_argument("--likes", type=int, default=0, help="Total de curtidas")
    parser.add_argument("--comments", type=int, default=0, help="Total de comentários")
    parser.add_argument("--notes", type=str, default="", help="Observações qualitativas")

    args = parser.parse_args()

    if args.weights:
        weights = DEFAULT_ALGORITHM_MEMORY.load_weights()
        print("\n⚖️ PESOS AUXILIARES ATIVOS:")
        for k, v in weights.items():
            print(f"   • {k}: {v:.2f}")
        return

    if args.memory:
        if os.path.exists(DEFAULT_ALGORITHM_MEMORY.memory_md_file):
            with open(DEFAULT_ALGORITHM_MEMORY.memory_md_file, "r", encoding="utf-8") as f:
                print(f.read())
        else:
            print("Memória algorítmica ainda não gerada.")
        return

    if args.list:
        records = DEFAULT_ALGORITHM_MEMORY.load_history()
        print(f"\n📋 TOTAL DE VÍDEOS REGISTRADOS: {len(records)}")
        for r in records:
            print(f"   • [{r.get('video_id')}] {r.get('title')} | Views: {r.get('views'):,} | Ret. 3s: {r.get('retention_3s')}% | APV: {r.get('apv')}% | Score: {r.get('composite_score')}")
        return

    if args.input:
        entry = DEFAULT_ALGORITHM_MEMORY.record_video_metrics(
            video_id=args.input,
            title=args.title or args.input,
            views=args.views,
            retention_3s=args.retention,
            apv=args.apv,
            ctr=args.ctr,
            likes=args.likes,
            comments=args.comments,
            notes=args.notes
        )
        print("\n✅ FEEDBACK REGISTRADO COM SUCESSO:")
        print(f"   • Vídeo: {entry.get('video_id')}")
        print(f"   • Score Composto: {entry.get('composite_score')}/100")
        print(f"   • Memória atualizada em: {DEFAULT_ALGORITHM_MEMORY.memory_md_file}")
        return

    parser.print_help()

if __name__ == "__main__":
    main()
