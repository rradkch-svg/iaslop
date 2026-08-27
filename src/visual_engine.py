import os
import subprocess
import glob
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont

try:
    from .logger import app_logger, LogSpan
except ImportError:
    from logger import app_logger, LogSpan

def find_ffmpeg_binary() -> str:
    """Busca o executável do FFmpeg no Windows/PATH."""
    winget_pattern = os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\*\bin\ffmpeg.exe")
    winget_matches = glob.glob(winget_pattern)
    if winget_matches and os.path.exists(winget_matches[0]):
        return winget_matches[0]
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    return "ffmpeg"

def get_best_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Tenta carregar uma fonte moderna do sistema Windows com fallback gracioso."""
    candidates = []
    if bold:
        candidates = [
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\impact.ttf",
            r"C:\Windows\Fonts\calibrib.ttf",
            r"C:\Windows\Fonts\tahomabd.ttf"
        ]
    else:
        candidates = [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\calibri.ttf",
            r"C:\Windows\Fonts\tahoma.ttf"
        ]
    
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except:
                pass
    return ImageFont.load_default()

class VisualEngine:
    """
    Motor de geração de cards visuais e infográficos da IA (Estilo Dossiê Confidencial / Top Secret).
    Gera infográficos táticos e misteriosos em 1080x1920 com estética de documentos desclassificados.
    """
    def __init__(self):
        self.ffmpeg_bin = find_ffmpeg_binary()

    def render_card_image(self, card_data: Dict[str, Any], output_png: str) -> bool:
        """
        Desenha um card infográfico vertical 1080x1920 no estilo Dossiê Confidencial / Arquivo Secreto.
        """
        width, height = 1080, 1920
        # Imagem base com gradiente escuro militar/investigativo
        img = Image.new("RGB", (width, height), color="#080A10")
        draw = ImageDraw.Draw(img)

        # 1. Fundo com gradiente sutil e linhas de grade tática
        for y in range(0, height, 4):
            alpha = int(10 + (y / height) * 18)
            r = int(8 + alpha * 0.4)
            g = int(10 + alpha * 0.5)
            b = int(16 + alpha * 0.8)
            draw.line([(0, y), (width, y)], fill=(r, g, b), width=4)

        # Grade tática sutil
        grid_color = (20, 25, 38)
        for gx in range(60, width, 120):
            draw.line([(gx, 100), (gx, height - 100)], fill=grid_color, width=1)
        for gy in range(100, height, 120):
            draw.line([(60, gy), (width - 60, gy)], fill=grid_color, width=1)

        # 2. Moldura e Card Central
        card_box = [60, 140, width - 60, height - 240]
        draw.rounded_rectangle(card_box, radius=24, fill=(12, 15, 24), outline=(40, 50, 75), width=3)

        # 3. Cabeçalho / Badge Superior (Estilo Carimbo TOP SECRET / DESCLASSIFICADO)
        category = card_data.get("categoria", "ARQUIVO DESCLASSIFICADO").upper()
        font_badge = get_best_font(30, bold=True)
        badge_w = draw.textlength(category, font=font_badge) + 40
        badge_box = [100, 180, 100 + badge_w, 240]
        draw.rounded_rectangle(badge_box, radius=10, fill=(220, 38, 38))
        draw.text((120, 194), category, font=font_badge, fill=(255, 255, 255))

        # Indicador de Registro / Selo
        font_ai = get_best_font(24, bold=False)
        draw.text((width - 340, 196), "📂 MINUTO INEXPLICÁVEL", font=font_ai, fill=(140, 155, 190))

        # 4. Título Principal da Evidência / Fato
        title = card_data.get("titulo", "Dossiê Confidencial").upper()
        font_title = get_best_font(58, bold=True)
        
        words = title.split()
        title_lines = []
        current_line = []
        for w in words:
            test_line = " ".join(current_line + [w])
            if draw.textlength(test_line, font=font_title) < (width - 240):
                current_line.append(w)
            else:
                if current_line:
                    title_lines.append(" ".join(current_line))
                current_line = [w]
        if current_line:
            title_lines.append(" ".join(current_line))

        y_offset = 290
        for t_line in title_lines[:3]:
            draw.text((100, y_offset), t_line, font=font_title, fill=(255, 255, 255))
            y_offset += 75

        # Linha divisória tática amarela
        y_offset += 10
        draw.line([(100, y_offset), (width - 100, y_offset)], fill=(255, 229, 0), width=4)
        y_offset += 40

        # 5. Destaques do Dossiê / Bullet Points
        pontos = card_data.get("pontos", [])
        if not pontos:
            pontos = [
                {"rotulo": "EVIDÊNCIA", "descricao": card_data.get("descricao", "Registro documental desclassificado.")},
                {"rotulo": "MISTÉRIO", "descricao": "Anomalia sem explicação conclusiva pelas autoridades da época."}
            ]

        font_label = get_best_font(32, bold=True)
        font_desc = get_best_font(36, bold=False)

        for p_idx, p in enumerate(pontos[:3]):
            p_box = [100, y_offset, width - 100, y_offset + 220]
            draw.rounded_rectangle(p_box, radius=16, fill=(18, 22, 34), outline=(48, 58, 88), width=2)
            
            p_label = str(p.get("rotulo", f"REGISTRO #{p_idx+1}")).upper()
            draw.text((130, y_offset + 25), f"🔍 {p_label}", font=font_label, fill=(255, 215, 0))
            
            p_desc = str(p.get("descricao", ""))
            desc_words = p_desc.split()
            d_lines = []
            d_curr = []
            for dw in desc_words:
                test_d = " ".join(d_curr + [dw])
                if draw.textlength(test_d, font=font_desc) < (width - 300):
                    d_curr.append(dw)
                else:
                    if d_curr:
                        d_lines.append(" ".join(d_curr))
                    d_curr = [dw]
            if d_curr:
                d_lines.append(" ".join(d_curr))

            d_y = y_offset + 75
            for dl in d_lines[:3]:
                draw.text((130, d_y), dl, font=font_desc, fill=(225, 230, 245))
                d_y += 45

            y_offset += 250

        # 6. Caixa de Coordenada / Data / Métrica de Destaque (se houver)
        metrica = card_data.get("metrica", "")
        valor_metrica = card_data.get("valor_metrica", "")
        if metrica and valor_metrica:
            stat_box = [100, y_offset + 10, width - 100, y_offset + 190]
            draw.rounded_rectangle(stat_box, radius=18, fill=(28, 18, 24), outline=(220, 38, 38), width=2)
            
            font_stat_val = get_best_font(52, bold=True)
            font_stat_lbl = get_best_font(30, bold=False)
            
            draw.text((140, y_offset + 35), str(valor_metrica), font=font_stat_val, fill=(255, 229, 0))
            draw.text((140, y_offset + 110), str(metrica).upper(), font=font_stat_lbl, fill=(240, 240, 255))

        # 7. Rodapé do Card
        font_foot = get_best_font(24, bold=False)
        draw.text((120, height - 200), "Minuto Inexplicável • Dossiê de Mistérios e Fatos Reais", font=font_foot, fill=(110, 125, 155))

        img.save(output_png, quality=95)
        return True

    def create_clip(self, card_data: Dict[str, Any], duration: float, output_clip_path: str, status_callback=None) -> bool:
        """
        Gera o card PNG e converte para clipe MP4 1080x1920 (30fps) com movimento sutil.
        """
        with LogSpan("VisualEngine.create_clip", extra={"duration": duration, "output": output_clip_path}):
            png_path = output_clip_path.replace(".mp4", "_card.png")
            if status_callback:
                status_callback(f"🎨 Desenhando Dossiê Confidencial: **{card_data.get('titulo', 'Dossiê')}**...")
            
            self.render_card_image(card_data, png_path)

            if status_callback:
                status_callback(f"⚡ Renderizando Clipe 1080x1920...")

            cmd = [
                self.ffmpeg_bin, "-y",
                "-loop", "1",
                "-i", png_path,
                "-t", str(duration),
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1",
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-r", "30",
                "-an",
                output_clip_path
            ]
            
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
                app_logger.info(f"[VisualEngine] Clipe visual gerado com sucesso: {output_clip_path}")
                return True
            except Exception as e:
                app_logger.error(f"[VisualEngine] Erro ao renderizar vídeo do card: {str(e)}")
                return False
