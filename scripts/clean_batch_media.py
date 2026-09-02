#!/usr/bin/env python3
"""
scripts/clean_batch_media.py
Utilitário para limpeza de arquivos pesados de mídia (mp4, mp3, wav, ass, b-roll)
em batches de checkpoints, preservando rigorosamente os metadados (metadata.txt),
dissertação e checkpoint.json para liberar espaço em disco no PC.
"""

import os
import sys
import argparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.checkpoint_manager import CheckpointManager

def main():
    parser = argparse.ArgumentParser(
        description="Limpa arquivos de mídia de batches mantendo metadados (metadata.txt)"
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=None,
        help="Índice específico do batch para processar (ex: 0, 15, 20)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Processa todos os batches existentes em checkpoint/"
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Apenas gera o arquivo 'limpar_conteudo.bat' no batch sem apagar arquivos"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Executa a limpeza física dos arquivos de mídia para liberar espaço"
    )

    args = parser.parse_args()
    ckpt_mgr = CheckpointManager()

    # Descobre todos os batches existentes
    existing_batches = []
    if os.path.exists(ckpt_mgr.root_dir):
        for entry in os.listdir(ckpt_mgr.root_dir):
            full_p = os.path.join(ckpt_mgr.root_dir, entry)
            if os.path.isdir(full_p) and entry.startswith("batch_"):
                try:
                    b_num = int(entry.split("_")[1])
                    existing_batches.append(b_num)
                except ValueError:
                    pass
    existing_batches.sort()

    if not existing_batches:
        print("ℹ️ Nenhum diretório de batch encontrado em:", ckpt_mgr.root_dir)
        return

    # Determina batches alvo
    targets = []
    if args.batch is not None:
        targets = [args.batch]
    elif args.all or not sys.argv[1:]:
        targets = existing_batches
    else:
        targets = existing_batches

    print("=" * 65)
    print("🧹 MINUTO INEXPLICÁVEL - LIMPEZA DE MÍDIA DE BATCHES")
    print("   Preserva 100% dos metadados (metadata.txt) e checkpoints")
    print("=" * 65)
    print(f"Batches alvo: {targets}")
    print(f"Modo: {'Apenas gerar scripts' if args.generate_only else ('Limpar mídia física' if args.clean else 'Gerar scripts nos batches')}\n")

    total_freed_bytes = 0
    total_removed_files = 0

    for b_idx in targets:
        # 1. Gera sempre o script limpar_conteudo.bat
        script_file = ckpt_mgr.generate_batch_cleanup_script(b_idx)
        print(f"📄 [batch_{b_idx}] Script pronto: {script_file}")

        # 2. Se modo clean for solicitado, realiza a limpeza física
        if args.clean and not args.generate_only:
            res = ckpt_mgr.clean_batch_media(b_idx)
            total_freed_bytes += res["freed_bytes"]
            total_removed_files += res["removed_files"]
            print(f"   ✨ Limpeza: {res['removed_files']} arquivos removidos | {res['freed_mb']:.2f} MB liberados")

    print("\n" + "=" * 65)
    if args.clean and not args.generate_only:
        total_freed_mb = total_freed_bytes / (1024 * 1024)
        total_freed_gb = total_freed_mb / 1024
        print(f"✅ Concluído! Total liberado: {total_freed_mb:.2f} MB ({total_freed_gb:.2f} GB)")
        print(f"🗑️ Total de arquivos de vídeo/áudio removidos: {total_removed_files}")
    else:
        print(f"✅ Scripts 'limpar_conteudo.bat' implantados com sucesso em {len(targets)} batches!")
        print("💡 Para executar a limpeza manualmente, dê duplo clique em 'limpar_conteudo.bat' no batch")
        print("   ou execute: python scripts/clean_batch_media.py --clean --all")
    print("=" * 65)

if __name__ == "__main__":
    main()
