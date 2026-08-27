"""
Script CLI para Tratamento de Resolução HD, Upscaling e Nitidez (Unsharp Masking)
Processa arquivos de vídeo individuais ou pastas inteiras, garantindo 1080x1920 Full HD (9:16 Vertical).
"""

import os
import sys
import argparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from video_enhancer import DEFAULT_VIDEO_ENHANCER, VideoResolutionEnhancer

def process_file(input_file: str, output_file: str, sharpen: float, denoise: bool, contrast: float):
    print(f"🎬 Processando arquivo: {input_file} ➔ {output_file}")
    ok, msg = DEFAULT_VIDEO_ENHANCER.enhance_clip(
        input_path=input_file,
        output_path=output_file,
        sharpen_strength=sharpen,
        denoise=denoise,
        contrast_boost=contrast,
        status_callback=lambda m: print(f"  {m}")
    )
    if ok:
        print(f"✅ Concluído com sucesso! Tamanho final: {os.path.getsize(output_file) // 1024} KB")
    else:
        print(f"❌ Falha: {msg}")

def process_directory(input_dir: str, output_dir: str, sharpen: float, denoise: bool, contrast: float):
    os.makedirs(output_dir, exist_ok=True)
    video_exts = (".mp4", ".mov", ".mkv", ".webm", ".avi")
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(video_exts)]
    print(f"📂 Encontrados {len(files)} vídeos para tratamento HD em: {input_dir}")

    for idx, f in enumerate(files, 1):
        in_p = os.path.join(input_dir, f)
        out_p = os.path.join(output_dir, f"hd_{f}")
        print(f"\n[{idx}/{len(files)}] {f}")
        process_file(in_p, out_p, sharpen, denoise, contrast)

def main():
    parser = argparse.ArgumentParser(description="Tratamento e Upscaling de Resolução HD para Shorts 9:16")
    parser.add_argument("--input", "-i", type=str, required=True, help="Arquivo de vídeo ou pasta de entrada")
    parser.add_argument("--output", "-o", type=str, default="", help="Arquivo de vídeo ou pasta de saída")
    parser.add_argument("--sharpen", type=float, default=0.8, help="Força da máscara de nitidez (0.0 a 1.5, padrão 0.8)")
    parser.add_argument("--no-denoise", action="store_true", help="Desativa redução de ruído de compressão")
    parser.add_argument("--contrast", type=float, default=1.05, help="Equalização de contraste (padrão 1.05)")

    args = parser.parse_args()

    if os.path.isfile(args.input):
        out = args.output or os.path.splitext(args.input)[0] + "_hd.mp4"
        process_file(args.input, out, args.sharpen, not args.no_denoise, args.contrast)
    elif os.path.isdir(args.input):
        out = args.output or os.path.join(args.input, "hd_output")
        process_directory(args.input, out, args.sharpen, not args.no_denoise, args.contrast)
    else:
        print(f"❌ Caminho de entrada inválido: {args.input}")
        sys.exit(1)

if __name__ == "__main__":
    main()
