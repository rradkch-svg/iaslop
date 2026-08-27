import os
import subprocess
import tempfile
import time
import sys
from typing import Tuple, Optional
from agents import CoderAgent
from logger import app_logger, LogSpan

def get_failsafe_manim_template(topic_text: str) -> str:
    """
    Template Manim garantido (100% puro e sem dependências externas)
    para caso o LLM esgote todas as tentativas de compilação.
    """
    clean_title = topic_text.replace('"', '').replace("'", "")[:50]
    return f"""from manim import *

class EngineScene(Scene):
    def construct(self):
        # Configuração vertical 9:16
        self.camera.frame_width = 9
        self.camera.frame_height = 16

        # Fundo e Estilo
        background = Rectangle(width=9, height=16, color="#121216", fill_opacity=1.0)
        self.add(background)

        # Título Esquemático
        title = Text("{clean_title}", font_size=32, color=YELLOW, weight=BOLD)
        title.to_edge(UP, buff=1.2)
        
        # Desenho Esquemático do Mecanismo (Pistão / Engrenagem / Fluxo)
        cylinder = Rectangle(width=3.5, height=6.0, color=WHITE, stroke_width=4)
        cylinder.move_to(ORIGIN + UP*0.5)

        piston = Rectangle(width=3.2, height=1.5, color=BLUE_D, fill_color=BLUE_E, fill_opacity=0.8)
        piston.move_to(cylinder.get_bottom() + UP*1.0)

        rod = Line(piston.get_bottom(), cylinder.get_bottom() + DOWN*1.5, stroke_width=6, color=LIGHT_GRAY)
        crank = Circle(radius=1.2, color=RED, stroke_width=4).move_to(cylinder.get_bottom() + DOWN*1.5)

        # Rótulos Técnicos
        t_label = Text("CÂMARA DE COMBUSTÃO", font_size=20, color=RED_A).next_to(cylinder, UP, buff=0.2)
        p_label = Text("FOLGA MICROMÉTRICA", font_size=18, color=YELLOW).next_to(piston, RIGHT, buff=0.3)

        self.play(FadeIn(title), FadeIn(cylinder), FadeIn(crank), run_time=1.0)
        self.play(FadeIn(piston), Create(rod), Write(t_label), Write(p_label), run_time=1.0)

        # Animação Cinemática Periódica
        for _ in range(3):
            self.play(
                piston.animate.shift(UP * 2.8),
                rod.animate.shift(UP * 1.4),
                run_time=0.8,
                rate_func=linear
            )
            self.play(
                piston.animate.shift(DOWN * 2.8),
                rod.animate.shift(DOWN * 1.4),
                run_time=0.8,
                rate_func=linear
            )

        self.wait(1.0)
"""

class ManimEngine:
    def __init__(self, coder_agent: CoderAgent, max_retries: int = 3):
        self.coder = coder_agent
        self.max_retries = max_retries

    def run_manim_code(self, code: str, output_dir: str, log_callback=None) -> Tuple[bool, str]:
        """
        Salva o código num arquivo .py temporário e executa o Manim via subprocess com streaming de logs ao vivo.
        Retorna (sucesso_booleano, caminho_do_video_ou_mensagem_de_erro).
        """
        temp_py = os.path.join(output_dir, "temp_scene.py")
        with open(temp_py, "w", encoding="utf-8") as f:
            f.write(code)

        command = [
            sys.executable, "-m", "manim",
            temp_py,
            "-a",
            "-qm",
            "--media_dir", output_dir,
            "-o", "manim_output.mp4"
        ]

        app_logger.info(f"[ManimEngine] Executando comando Manim: {' '.join(command)}")
        if log_callback:
            log_callback(f"[ManimEngine] Iniciando renderização...")

        full_output = []
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1
            )

            for line in iter(process.stdout.readline, ""):
                line_str = line.strip()
                if line_str:
                    full_output.append(line_str)
                    app_logger.debug(f"[Manim stdout] {line_str}")
                    if log_callback:
                        log_callback(f"🎬 {line_str}")

            process.stdout.close()
            return_code = process.wait()

            if return_code == 0:
                found_mp4s = []
                for root, dirs, files in os.walk(output_dir):
                    if "partial_movie_files" in root:
                        continue
                    for f in files:
                        if f.endswith(".mp4"):
                            full_path = os.path.join(root, f)
                            found_mp4s.append((os.path.getmtime(full_path), full_path))
                
                if found_mp4s:
                    # Seleciona o mp4 mais recente
                    found_mp4s.sort(reverse=True)
                    expected_mp4_path = found_mp4s[0][1]
                    app_logger.info(f"[ManimEngine] Renderização bem-sucedida: {expected_mp4_path} ({os.path.getsize(expected_mp4_path)} bytes)")
                    return True, expected_mp4_path
                else:
                    return False, "Processo finalizou com código 0, mas nenhum arquivo .mp4 final foi encontrado."
            else:
                out_joined = "\n".join(full_output)
                app_logger.warning(f"[ManimEngine] Erro de execução Manim (código {return_code}):\n{out_joined[-500:]}")
                return False, out_joined

        except Exception as e:
            out_joined = f"Exceção ao executar o Manim: {str(e)}\n" + "\n".join(full_output)
            app_logger.error(out_joined)
            return False, out_joined

    def generate_and_render(
        self, 
        script: str, 
        output_dir: str, 
        status_callback=None, 
        code_callback=None, 
        log_callback=None, 
        cooldown_callback=None
    ) -> str:
        """
        Gera o código Manim, tenta renderizar com logs linha a linha, 
        e possui failsafe template redundante caso todas as tentativas falhem.
        """
        with LogSpan("ManimEngine.generate_and_render", extra={"script_preview": script[:60]}):
            feedback = ""
            current_code = ""
            
            for attempt in range(1, self.max_retries + 1):
                msg_step = f"Tentativa {attempt}/{self.max_retries} - CoderAgent escrevendo Manim..."
                app_logger.info(f"[ManimEngine] {msg_step}")
                if status_callback:
                    status_callback(msg_step)
                
                current_code = self.coder.generate_manim_code(
                    script, 
                    feedback=feedback, 
                    cooldown_callback=cooldown_callback, 
                    status_callback=status_callback
                )
                if code_callback:
                    code_callback(current_code)
                
                msg_render = f"Tentativa {attempt}/{self.max_retries} - Renderizando cena Manim (streaming de frames)..."
                app_logger.info(f"[ManimEngine] {msg_render}")
                if status_callback:
                    status_callback(msg_render)
                    
                success, result = self.run_manim_code(current_code, output_dir, log_callback=log_callback)
                
                if success:
                    if status_callback:
                        status_callback(f"✅ Renderização Manim concluída com sucesso!")
                    if log_callback:
                        log_callback(f"[ManimEngine] Sucesso na tentativa {attempt}! Arquivo: {result}")
                    return result
                else:
                    if log_callback:
                        log_callback(f"[ManimEngine] ❌ Falha na tentativa {attempt}:\n{result}")
                    feedback = f"Ocorreu o seguinte erro ao rodar o Manim:\n\n{result}\n\nPor favor, retorne apenas o código Python corrigido."
                    if status_callback:
                        status_callback(f"⚠️ Tentativa {attempt} falhou. Auto-correção acionada...")

            # REDUNDÂNCIA MÁXIMA: Failsafe Template
            app_logger.warning("[ManimEngine] Todas as tentativas do LLM falharam. Acionando Failsafe Template Cinemático Redundante...")
            if status_callback:
                status_callback("⚠️ Acionando Failsafe Template Cinemático Redundante...")
            if log_callback:
                log_callback("[ManimEngine] Acionando Failsafe Template Redundante de Alta Confiabilidade...")
                
            failsafe_code = get_failsafe_manim_template(script)
            if code_callback:
                code_callback(failsafe_code)
                
            success_fs, result_fs = self.run_manim_code(failsafe_code, output_dir, log_callback=log_callback)
            if success_fs:
                app_logger.info("[ManimEngine] Failsafe Template renderizado com sucesso!")
                return result_fs
            
            raise Exception(f"Falha crítica inclusive no Failsafe Template: {result_fs}")
