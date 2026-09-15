"""
Módulo de Automação de Publicação de Shorts no YouTube Studio via Playwright / Chrome.

Responsável por:
1. Gerenciar sessão autenticada persistente no YouTube Studio (perfil isolado em checkpoint/youtube_profile).
2. Carregar e parsear cookies locais (cookies.txt) e dados de autenticação.
3. Fazer upload de vídeos renderizados (final_output.mp4) de cada lote.
4. Preencher Título, Descrição, Tags e selecionar 'Não é conteúdo para crianças'.
5. Alocar automaticamente slots fixos diários (11:00, 13:00, 15:00, 17:00 GMT) e agendar Shorts no YouTube Studio.
6. Executar limpeza imediata dos arquivos pesados de mídia (final_output.mp4, broll/) logo após o upload bem-sucedido.
7. Disparar alertas por e-mail para o destinatário configurado em caso de falha de upload.
8. Sincronizar em lote todo o backlog de vídeos não postados nos lotes existentes.
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from .logger import app_logger
except ImportError:
    try:
        from logger import app_logger
    except ImportError:
        import logging
        app_logger = logging.getLogger("youtube_uploader")
        if not app_logger.handlers:
            logging.basicConfig(level=logging.INFO)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CHECKPOINT_DIR = os.environ.get("CHECKPOINT_DIR") or os.path.join(PROJECT_ROOT, "checkpoint")
DEFAULT_PROFILE_DIR = os.path.join(DEFAULT_CHECKPOINT_DIR, "youtube_profile")
DEFAULT_COOKIES_TXT = os.path.join(PROJECT_ROOT, "cookies.txt")

# Slots de horários diários fixos em GMT (11h, 13h, 15h, 17h GMT = 08h, 10h, 12h, 14h Brasília)
DEFAULT_GMT_SLOTS = [11, 13, 15, 17]

# Caminhos padrão do Google Chrome no Windows
CHROME_CANDIDATE_PATHS = [
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def find_system_browser() -> Optional[str]:
    """Localiza o executável do Google Chrome ou Edge no sistema Windows."""
    for path in CHROME_CANDIDATE_PATHS:
        if os.path.exists(path):
            return path
    return None


def parse_netscape_cookies(cookie_file_path: str) -> List[Dict[str, Any]]:
    """
    Converte cookies no formato Netscape (cookies.txt) para o formato aceito pelo Playwright.
    """
    if not os.path.exists(cookie_file_path):
        return []

    cookies = []
    now = time.time()
    try:
        with open(cookie_file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                parts = line.split("\t")
                if len(parts) >= 7:
                    domain = parts[0]
                    path = parts[2]
                    secure = parts[3].lower() == "true"
                    try:
                        expires = float(parts[4])
                    except (ValueError, IndexError):
                        expires = -1

                    name = parts[5]
                    value = parts[6]

                    if "youtube.com" not in domain and "google.com" not in domain:
                        continue

                    if expires > 0 and expires < now:
                        continue

                    cookie_dict: Dict[str, Any] = {
                        "name": name,
                        "value": value,
                        "domain": domain if domain.startswith(".") else f".{domain}",
                        "path": path,
                        "secure": secure,
                        "sameSite": "Lax",
                    }
                    if expires > 0:
                        if expires > 1e11:
                            expires = expires / 1000.0
                        cookie_dict["expires"] = int(expires)

                    cookies.append(cookie_dict)
    except Exception as e:
        app_logger.warning(f"[YouTubeUploader] Erro ao ler cookies de {cookie_file_path}: {e}")

    return cookies


def parse_video_metadata(video_dir: str) -> Dict[str, Any]:
    """
    Extrai título, descrição e tags de um vídeo a partir de metadata.txt ou checkpoint.json.
    """
    meta_path = os.path.join(video_dir, "metadata.txt")
    ckpt_path = os.path.join(video_dir, "checkpoint.json")

    title = ""
    description = ""
    tags = []

    # 1. Tenta ler checkpoint.json primeiro
    if os.path.exists(ckpt_path):
        try:
            with open(ckpt_path, "r", encoding="utf-8") as f:
                cdata = json.load(f)
                topic = cdata.get("topic", {})
                title = topic.get("tema", "")
                description = topic.get("descricao", "")
                tags = topic.get("tags", [])
        except Exception:
            pass

    # 2. Complementa com metadata.txt
    if (not title or not description) and os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            current_section = None
            desc_lines = []
            for line in lines:
                sline = line.strip()
                if sline.startswith("TÍTULO:") or sline.startswith("TITULO:"):
                    current_section = "title"
                    t_val = sline.split(":", 1)[1].strip()
                    if t_val:
                        title = t_val
                    continue
                elif sline.startswith("DESCRIÇÃO:") or sline.startswith("DESCRICAO:"):
                    current_section = "desc"
                    continue
                elif sline.startswith("HASHTAGS:") or sline.startswith("TAGS:"):
                    current_section = "tags"
                    continue

                if current_section == "title" and sline and not title:
                    title = sline
                elif current_section == "desc" and sline:
                    desc_lines.append(sline)
                elif current_section == "tags" and sline:
                    found_tags = [t.strip() for t in sline.split() if t.startswith("#")]
                    if found_tags:
                        tags.extend(found_tags)

            if desc_lines and not description:
                description = "\n".join(desc_lines)
        except Exception:
            pass

    # Garante hashtag #Shorts no título se ainda não estiver presente
    if title and "#Shorts" not in title and "#shorts" not in title:
        if len(title) + len(" #Shorts") <= 100:
            title = f"{title} #Shorts"
        else:
            title = f"{title[:90]}... #Shorts"

    return {
        "title": title or "Mistério Inexplicável #Shorts",
        "description": description or "Mais um mistério factual e documental investigado pelo Minuto Inexplicável.",
        "tags": tags or ["#Shorts", "#MinutoInexplicavel", "#Misterio", "#Documentario"],
    }


def load_scheduled_slots(checkpoint_dir: Optional[str] = None) -> Dict[str, Any]:
    """Carrega registro global de horários já reservados."""
    base_dir = os.path.abspath(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)
    slots_path = os.path.join(base_dir, "youtube_scheduled_slots.json")
    if os.path.exists(slots_path):
        try:
            with open(slots_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_scheduled_slots(slots_data: Dict[str, Any], checkpoint_dir: Optional[str] = None):
    """Grava registro global de horários reservados."""
    base_dir = os.path.abspath(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)
    os.makedirs(base_dir, exist_ok=True)
    slots_path = os.path.join(base_dir, "youtube_scheduled_slots.json")
    with open(slots_path, "w", encoding="utf-8") as f:
        json.dump(slots_data, f, indent=2, ensure_ascii=False)


def get_next_available_gmt_slot(
    safety_buffer_minutes: int = 30,
    checkpoint_dir: Optional[str] = None
) -> datetime:
    """
    Calcula o próximo horário livre dentre os slots fixos diários (11:00, 13:00, 15:00, 17:00 GMT).
    Garante que o slot esteja livre no registro global e no mínimo 30 min no futuro em relação ao horário UTC atual.
    """
    now_utc = datetime.now(timezone.utc)
    min_time_utc = now_utc + timedelta(minutes=safety_buffer_minutes)
    
    reserved_slots = load_scheduled_slots(checkpoint_dir)
    current_date = now_utc.date()

    for day_offset in range(180):  # Varre até 180 dias
        day = current_date + timedelta(days=day_offset)
        for hour in DEFAULT_GMT_SLOTS:
            candidate = datetime(day.year, day.month, day.day, hour, 0, 0, tzinfo=timezone.utc)
            if candidate < min_time_utc:
                continue

            slot_key = candidate.strftime("%Y-%m-%dT%H:%M:%SZ")
            if slot_key not in reserved_slots:
                return candidate

    return min_time_utc + timedelta(hours=2)


def reserve_gmt_slot(
    slot_dt: datetime,
    video_info: Dict[str, Any],
    checkpoint_dir: Optional[str] = None
):
    """Marca um slot GMT como ocupado para evitar conflito de publicações simultâneas."""
    reserved_slots = load_scheduled_slots(checkpoint_dir)
    slot_key = slot_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    local_str = slot_dt.astimezone().strftime("%Y-%m-%d %H:%M:%S Local")

    reserved_slots[slot_key] = {
        "slot_gmt": slot_key,
        "slot_local": local_str,
        "batch_index": video_info.get("batch_index"),
        "video_index": video_info.get("video_index"),
        "video_key": video_info.get("video_key"),
        "title": video_info.get("title"),
        "url": video_info.get("url", ""),
        "reserved_at": datetime.now(timezone.utc).isoformat()
    }
    save_scheduled_slots(reserved_slots, checkpoint_dir)


def get_batch_videos_to_upload(
    batch_index: int,
    checkpoint_dir: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Varre o batch e retorna a lista de vídeos que possuem arquivo MP4 em disco e ainda não foram postados.
    """
    base_dir = os.path.abspath(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)
    batch_dir = os.path.join(base_dir, f"batch_{batch_index}")
    if not os.path.exists(batch_dir):
        return []

    history_file = os.path.join(batch_dir, "youtube_uploads.json")
    uploaded_history: Dict[str, Any] = {}
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as hf:
                uploaded_history = json.load(hf)
        except Exception:
            uploaded_history = {}

    targets = []
    for item in sorted(os.listdir(batch_dir)):
        item_path = os.path.join(batch_dir, item)
        if not os.path.isdir(item_path) or not item.startswith("video_"):
            continue

        try:
            v_idx = int(item.split("_")[1])
        except (IndexError, ValueError):
            continue

        v_key = f"video_{v_idx}"
        if v_key in uploaded_history and uploaded_history[v_key].get("success"):
            continue

        # Checa se no checkpoint.json já consta youtube_url
        ckpt_path = os.path.join(item_path, "checkpoint.json")
        if os.path.exists(ckpt_path):
            try:
                with open(ckpt_path, "r", encoding="utf-8") as cf:
                    cdata = json.load(cf)
                    if cdata.get("youtube_url") or cdata.get("cleaned"):
                        continue
            except Exception:
                pass

        final_mp4 = os.path.join(item_path, "final_output.mp4")
        if not os.path.exists(final_mp4):
            alt_mp4 = os.path.join(item_path, "final_video.mp4")
            if os.path.exists(alt_mp4):
                final_mp4 = alt_mp4

        if not os.path.exists(final_mp4) or os.path.getsize(final_mp4) < 10_000:
            continue

        meta = parse_video_metadata(item_path)
        targets.append({
            "batch_index": batch_index,
            "video_index": v_idx,
            "video_key": v_key,
            "video_dir": item_path,
            "video_file": final_mp4,
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
        })

    return targets


def save_upload_record(
    batch_index: int,
    video_key: str,
    record_data: Dict[str, Any],
    checkpoint_dir: Optional[str] = None
):
    """Registra o status e URL do vídeo postado no arquivo youtube_uploads.json do batch."""
    base_dir = os.path.abspath(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)
    batch_dir = os.path.join(base_dir, f"batch_{batch_index}")
    os.makedirs(batch_dir, exist_ok=True)
    history_file = os.path.join(batch_dir, "youtube_uploads.json")

    current = {}
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                current = json.load(f)
        except Exception:
            current = {}

    current[video_key] = record_data
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)


class YouTubeStudioUploader:
    """
    Robô de automação do YouTube Studio utilizando Playwright e perfil persistente do Chrome.
    """

    def __init__(
        self,
        profile_dir: Optional[str] = None,
        cookies_txt_path: Optional[str] = None,
        headless: bool = False
    ):
        self.profile_dir = os.path.abspath(profile_dir or DEFAULT_PROFILE_DIR)
        os.makedirs(self.profile_dir, exist_ok=True)
        self.cookies_path = cookies_txt_path or DEFAULT_COOKIES_TXT
        self.headless = headless
        self.browser_exe = find_system_browser()

    def launch_browser(self, p):
        """Inicializa o contexto persistente do navegador com perfil dedicado."""
        app_logger.info(f"[YouTubeUploader] 🌐 Inicializando navegador (Headless={self.headless})...")
        if self.browser_exe:
            app_logger.info(f"[YouTubeUploader] 🚀 Executável do navegador detectado: {self.browser_exe}")

        context = p.chromium.launch_persistent_context(
            user_data_dir=self.profile_dir,
            executable_path=self.browser_exe,
            headless=self.headless,
            viewport={"width": 1280, "height": 800},
            ignore_default_args=["--enable-automation"],
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )

        if not context.cookies() and os.path.exists(self.cookies_path):
            netscape_cookies = parse_netscape_cookies(self.cookies_path)
            if netscape_cookies:
                added = 0
                for c in netscape_cookies:
                    try:
                        context.add_cookies([c])
                        added += 1
                    except Exception:
                        pass
                app_logger.info(f"[YouTubeUploader] 🍪 {added}/{len(netscape_cookies)} cookies importados de '{self.cookies_path}'.")

        return context

    def open_interactive_login(self):
        """
        Abre uma janela visível do navegador para o usuário fazer login no YouTube Studio.
        A sessão fica salva de forma definitiva no perfil local isolado.
        """
        from playwright.sync_api import sync_playwright

        print("\n" + "=" * 75)
        print("🔑 MODO DE AUTENTICAÇÃO INTERATIVA DO YOUTUBE STUDIO")
        print("Uma janela do Google Chrome será aberta.")
        print("1. Faça login na sua conta do YouTube associada ao canal.")
        print("2. Quando a tela do YouTube Studio (studio.youtube.com) carregar com sucesso,")
        print("   volte a este terminal e pressione ENTER para salvar a sessão.")
        print("=" * 75 + "\n")

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=self.profile_dir,
                executable_path=self.browser_exe,
                headless=False,
                viewport={"width": 1280, "height": 850},
                ignore_default_args=["--enable-automation"],
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
            )
            context.clear_cookies()
            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://studio.youtube.com", timeout=60000)

            input("👉 Pressione ENTER assim que estiver autenticado e vendo o painel do YouTube Studio...")

            storage_path = os.path.join(self.profile_dir, "storage_state.json")
            context.storage_state(path=storage_path)
            print(f"✅ Sessão persistente salva com sucesso em: {self.profile_dir}")
            context.close()

    def upload_video(
        self,
        video_data: Dict[str, Any],
        visibility: str = "SCHEDULE",
        schedule_time: Optional[datetime] = None,
        status_callback=None
    ) -> Dict[str, Any]:
        """
        Executa o fluxo completo de upload de um vídeo individual no YouTube Studio.
        """
        from playwright.sync_api import sync_playwright

        def log(msg: str):
            if status_callback:
                status_callback(msg)
            app_logger.info(f"[YouTubeUploader] {msg}")
            print(f"  {msg}")

        video_path = video_data["video_file"]
        title = video_data["title"]
        description = video_data["description"]
        tags = video_data.get("tags", [])

        if not os.path.exists(video_path):
            return {"success": False, "error": f"Arquivo de vídeo não encontrado: {video_path}"}

        log(f"🎬 Iniciando envio de: '{title}' ({os.path.getsize(video_path) / (1024*1024):.2f} MB)")

        with sync_playwright() as p:
            context = self.launch_browser(p)
            page = context.pages[0] if context.pages else context.new_page()

            try:
                log("📡 Navegando para o YouTube Studio...")
                page.goto("https://studio.youtube.com", timeout=60000, wait_until="domcontentloaded")
                time.sleep(3)

                if "accounts.google.com" in page.url or "signin" in page.url:
                    context.close()
                    return {
                        "success": False,
                        "error": "Sessão não autenticada no YouTube Studio. Execute 'scripts\\postar_youtube.bat --login' para autenticar sua conta."
                    }

                log("🖱️ Abrindo menu de envio de vídeos...")
                create_btn = page.locator("#create-icon, button[aria-label*='Criar'], button[aria-label*='Create'], ytcp-button#create-icon").first
                create_btn.wait_for(state="visible", timeout=30000)
                create_btn.click()
                time.sleep(1.5)

                upload_option = page.locator(
                    "tp-yt-paper-item#text-item-0, "
                    "#text-item-0, "
                    "ytcp-text-menu tp-yt-paper-item:has-text('Enviar vídeos'), "
                    "ytcp-text-menu tp-yt-paper-item:has-text('Upload videos'), "
                    "ytcp-text-menu :text('Enviar vídeos'), "
                    "ytcp-text-menu :text('Upload videos'), "
                    "[test-id='upload-video']"
                ).first
                upload_option.wait_for(state="visible", timeout=15000)
                upload_option.click(force=True)
                time.sleep(2)

                log(f"📤 Fazendo upload do arquivo: {os.path.basename(video_path)}...")
                file_input = page.locator("input[type='file']").first
                file_input.wait_for(state="attached", timeout=20000)
                file_input.set_input_files(video_path)
                time.sleep(4)

                dialog = page.locator("ytcp-uploads-dialog, ytcp-video-metadata-editor").first
                dialog.wait_for(state="attached", timeout=45000)
                log("✍️ Preenchendo metadados do vídeo...")

                title_box = page.locator("#textbox[aria-label*='título'], #textbox[aria-label*='Title'], div#title-textarea #textbox, #title-textarea #textbox").first
                title_box.wait_for(state="visible", timeout=45000)
                title_box.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                title_box.fill(title[:100])
                time.sleep(1)

                desc_box = page.locator("div#description-textarea #textbox, #textbox[aria-label*='descrição'], #textbox[aria-label*='Description']").first
                if desc_box.is_visible():
                    desc_box.click()
                    full_desc = f"{description}\n\n{' '.join(tags)}"
                    desc_box.fill(full_desc[:4900])
                    time.sleep(1)

                log("👶 Definindo restrição de audiência (Não é para crianças)...")
                not_for_kids_radio = page.locator("tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']").first
                not_for_kids_radio.scroll_into_view_if_needed()
                time.sleep(0.5)
                radio_target = not_for_kids_radio.locator("#radioContainer, div#offRadio").first
                if radio_target.is_visible():
                    radio_target.click()
                else:
                    not_for_kids_radio.click()
                time.sleep(1)

                try:
                    show_more = page.locator("#toggle-button, button:has-text('Mostrar mais'), button:has-text('Show more')").first
                    if show_more.is_visible():
                        show_more.click()
                        time.sleep(1)
                        tags_input = page.locator("input[aria-label*='Tags'], #tags-container input").first
                        if tags_input.is_visible() and tags:
                            raw_tags = ", ".join([t.replace("#", "") for t in tags])
                            tags_input.fill(raw_tags[:450])
                            page.keyboard.press("Enter")
                except Exception as e_tags:
                    app_logger.warning(f"[YouTubeUploader] Erro ao preencher tags: {e_tags}")

                log("⏭️ Avançando etapas de elementos e direitos autorais...")
                for _ in range(3):
                    next_btn = page.locator("#next-button, button:has-text('Avançar'), button:has-text('Próximo'), button:has-text('Next')").first
                    next_btn.wait_for(state="visible", timeout=15000)
                    next_btn.click()
                    time.sleep(2)

                log(f"🔒 Configurando visibilidade/agendamento: {visibility}...")
                if visibility == "SCHEDULE" and schedule_time:
                    sched_tab = page.locator("#second-container-expand-button, button:has-text('Programar'), button:has-text('Schedule'), tp-yt-paper-radio-button[name='SCHEDULE']").first
                    sched_tab.click()
                    time.sleep(1.5)

                    # Converte para horário local da máquina/canal
                    target_local = schedule_time.astimezone() if schedule_time.tzinfo else schedule_time
                    log(f"📅 Definindo data/hora: {schedule_time.strftime('%H:%M GMT')} ({target_local.strftime('%d/%m/%Y %H:%M Local')})")

                    dp_trigger = page.locator("#datepicker-trigger").first
                    if dp_trigger.is_visible():
                        dp_trigger.click()
                        time.sleep(1)

                    date_input = page.locator("ytcp-date-picker input").first
                    if date_input.is_visible():
                        curr_val = date_input.input_value()
                        is_pt = any(m in curr_val.lower() for m in [" de ", "fev", "abr", "mai", "ago", "set", "out", "dez"])
                        if is_pt:
                            pt_months = ["", "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
                            formatted_date = f"{target_local.day} de {pt_months[target_local.month]}. de {target_local.year}"
                        else:
                            formatted_date = target_local.strftime("%b %d, %Y")

                        date_input.click(force=True)
                        page.keyboard.press("Control+A")
                        page.keyboard.press("Backspace")
                        date_input.fill(formatted_date)
                        page.keyboard.press("Enter")
                        time.sleep(0.8)

                    time_input = page.locator("#time-of-day-container input, input[aria-label*='Horário'], input[aria-label*='Time']").first
                    if time_input.is_visible():
                        time_input.click(force=True)
                        page.keyboard.press("Control+A")
                        page.keyboard.press("Backspace")
                        time_input.fill(target_local.strftime("%H:%M"))
                        page.keyboard.press("Enter")
                        time.sleep(0.8)

                elif visibility == "PUBLIC":
                    pub_radio = page.locator("tp-yt-paper-radio-button[name='PUBLIC']").first
                    pub_radio.scroll_into_view_if_needed()
                    pub_radio.click()
                elif visibility == "UNLISTED":
                    unlisted_radio = page.locator("tp-yt-paper-radio-button[name='UNLISTED']").first
                    unlisted_radio.scroll_into_view_if_needed()
                    unlisted_radio.click()
                elif visibility == "PRIVATE":
                    priv_radio = page.locator("tp-yt-paper-radio-button[name='PRIVATE']").first
                    priv_radio.scroll_into_view_if_needed()
                    priv_radio.click()

                time.sleep(2)

                video_url = ""
                try:
                    url_elem = page.locator("a.ytcp-video-info, a[href*='youtu.be']").first
                    if url_elem.is_visible():
                        video_url = url_elem.get_attribute("href") or ""
                except Exception:
                    pass

                log("💾 Finalizando e publicando no YouTube...")
                done_btn = page.locator("#done-button, button:has-text('Salvar'), button:has-text('Publicar'), button:has-text('Programar'), button:has-text('Save'), button:has-text('Publish'), button:has-text('Schedule'), ytcp-button#done-button").first
                done_btn.wait_for(state="visible", timeout=20000)
                done_btn.click()

                time.sleep(4)
                try:
                    url_elem = page.locator("a.ytcp-video-info, a[href*='youtu.be']").first
                    if url_elem.is_visible():
                        video_url = url_elem.get_attribute("href") or video_url
                except Exception:
                    pass

                try:
                    close_btn = page.locator("#close-button, ytcp-button#close-button, button:has-text('Fechar'), button:has-text('Close')").first
                    if close_btn.is_visible():
                        close_btn.click()
                        time.sleep(2)
                except Exception:
                    pass

                log(f"🎉 Vídeo agendado/publicado com sucesso! {video_url}")

                context.close()
                return {
                    "success": True,
                    "title": title,
                    "url": video_url,
                    "published_at": datetime.now().isoformat(),
                    "visibility": visibility,
                    "schedule_gmt": schedule_time.strftime("%Y-%m-%dT%H:%M:%SZ") if schedule_time else None
                }

            except Exception as e:
                err_msg = f"Falha durante o upload no YouTube Studio: {str(e)}"
                app_logger.error(f"[YouTubeUploader] {err_msg}")
                try:
                    diag_shot = os.path.join(self.profile_dir, "upload_error_diagnostic.png")
                    page.screenshot(path=diag_shot)
                    app_logger.info(f"[YouTubeUploader] Screenshot do erro salva em: {diag_shot}")
                except Exception:
                    pass
                context.close()
                return {"success": False, "error": err_msg}


def upload_and_clean_single_video(
    batch_index: int,
    video_index: int,
    checkpoint_dir: Optional[str] = None,
    headless: bool = True
) -> Dict[str, Any]:
    """
    Faz o upload do vídeo recém-concluído, programa para o próximo slot GMT livre (11h, 13h, 15h ou 17h GMT)
    e, mediante confirmação de sucesso, exclui a mídia física local liberando espaço em disco.
    Em caso de falha, mantém a mídia para retentativa e envia alerta por e-mail para o destinatário configurado.
    """
    base_dir = os.path.abspath(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)
    b_dir = os.path.join(base_dir, f"batch_{batch_index}")
    v_dir = os.path.join(b_dir, f"video_{video_index}")

    if not os.path.exists(v_dir):
        return {"success": False, "error": f"Diretório não encontrado: {v_dir}"}

    final_mp4 = os.path.join(v_dir, "final_output.mp4")
    if not os.path.exists(final_mp4):
        alt_mp4 = os.path.join(v_dir, "final_video.mp4")
        if os.path.exists(alt_mp4):
            final_mp4 = alt_mp4

    if not os.path.exists(final_mp4) or os.path.getsize(final_mp4) < 10_000:
        return {"success": False, "error": f"Vídeo final MP4 não existe ou está corrompido em {v_dir}"}

    meta = parse_video_metadata(v_dir)
    video_key = f"video_{video_index}"
    target_data = {
        "batch_index": batch_index,
        "video_index": video_index,
        "video_key": video_key,
        "video_dir": v_dir,
        "video_file": final_mp4,
        "title": meta["title"],
        "description": meta["description"],
        "tags": meta["tags"]
    }

    # 1. Aloca o próximo slot GMT disponível
    slot_dt = get_next_available_gmt_slot(safety_buffer_minutes=30, checkpoint_dir=base_dir)
    local_dt = slot_dt.astimezone()
    app_logger.info(
        f"[YouTubeUploader] 🎯 Próximo slot alocado para batch_{batch_index}/{video_key}: "
        f"{slot_dt.strftime('%H:%M GMT')} ({local_dt.strftime('%d/%m/%Y %H:%M Local')})"
    )

    # 2. Executa o upload e agendamento via Playwright
    uploader = YouTubeStudioUploader(headless=headless)
    res = uploader.upload_video(
        video_data=target_data,
        visibility="SCHEDULE",
        schedule_time=slot_dt
    )

    if res.get("success"):
        # 3. Sucesso: grava reserva e histórico
        target_data["url"] = res.get("url", "")
        reserve_gmt_slot(slot_dt, target_data, checkpoint_dir=base_dir)
        save_upload_record(batch_index, video_key, res, checkpoint_dir=base_dir)

        # 4. Limpeza imediata do arquivo de mídia
        try:
            from .checkpoint_manager import CheckpointManager
        except Exception:
            try:
                from checkpoint_manager import CheckpointManager
            except Exception:
                from src.checkpoint_manager import CheckpointManager
        ckpt_mgr = CheckpointManager(root_dir=base_dir)
        clean_res = ckpt_mgr.clean_single_video_media(
            batch_index=batch_index,
            video_index=video_index,
            youtube_url=res.get("url"),
            scheduled_time=slot_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        res["cleaned"] = True
        res["freed_mb"] = clean_res.get("freed_mb", 0.0)
        res["scheduled_gmt"] = slot_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        app_logger.info(
            f"[YouTubeUploader] ✅ batch_{batch_index}/{video_key} agendado para {slot_dt.strftime('%H:%M GMT')} "
            f"e mídia local limpa ({res['freed_mb']} MB liberados)."
        )
        return res
    else:
        # 5. Falha: notifica por e-mail e preserva mídia
        err_msg = res.get("error", "Erro desconhecido")
        app_logger.error(f"[YouTubeUploader] ❌ Falha no agendamento de batch_{batch_index}/{video_key}: {err_msg}")
        try:
            from .email_service import send_upload_alert_email
        except Exception:
            try:
                from email_service import send_upload_alert_email
            except Exception:
                from src.email_service import send_upload_alert_email

        try:
            send_upload_alert_email(
                subject=f"Falha ao postar {video_key} do Batch {batch_index}",
                message=f"Não foi possível agendar o vídeo '{meta['title']}' no YouTube Studio.\n\n"
                        f"Erro retornado: {err_msg}\n\n"
                        f"O arquivo de vídeo foi PRESERVADO no disco para retentativa futura sem perda de conteúdo."
            )
        except Exception as e_alert:
            app_logger.warning(f"[YouTubeUploader] Não foi possível disparar e-mail de alerta: {e_alert}")

        return res


def sync_all_unposted_videos(
    checkpoint_dir: Optional[str] = None,
    headless: bool = True
) -> Dict[str, Any]:
    """
    Varre todos os lotes existentes em busca de vídeos que possuam arquivos de vídeo em disco
    e que ainda não foram postados/agendados no YouTube, agendando-os em sequência nos slots GMT.
    """
    base_dir = os.path.abspath(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)
    if not os.path.exists(base_dir):
        return {"success": False, "error": f"Pasta de checkpoints não encontrada: {base_dir}"}

    batches = []
    for entry in sorted(os.listdir(base_dir)):
        if entry.startswith("batch_") and os.path.isdir(os.path.join(base_dir, entry)):
            try:
                b_num = int(entry.split("_")[1])
                batches.append(b_num)
            except (ValueError, IndexError):
                pass

    total_synced = 0
    total_freed_mb = 0.0
    results = []

    print(f"\n{'=' * 75}")
    print(f"🔄 SINCRONIZAÇÃO DE BACKLOG: POSTAGEM NOS SLOTS 11h, 13h, 15h, 17h GMT")
    print(f"{'=' * 75}\n")

    for b_idx in batches:
        targets = get_batch_videos_to_upload(b_idx, checkpoint_dir=base_dir)
        if not targets:
            continue

        print(f"\n📦 Processando Batch {b_idx} ({len(targets)} vídeos pendentes)...")
        for t in targets:
            v_idx = t["video_index"]
            print(f"  🚀 Agendando batch_{b_idx}/video_{v_idx}...")
            res = upload_and_clean_single_video(b_idx, v_idx, checkpoint_dir=base_dir, headless=headless)
            if res.get("success"):
                total_synced += 1
                total_freed_mb += res.get("freed_mb", 0.0)
                results.append(res)
            else:
                print(f"  ❌ Erro ao postar batch_{b_idx}/video_{v_idx}: {res.get('error')}")
                if "não autenticada" in res.get("error", "").lower():
                    print("\n🛑 Sessão do YouTube Studio não autenticada. Interrompendo sincronização.")
                    print("👉 Execute 'scripts\\postar_youtube.bat --login' para autenticar sua conta.\n")
                    return {
                        "success": False,
                        "error": "Sessão não autenticada",
                        "total_synced": total_synced,
                        "total_freed_mb": total_freed_mb,
                        "results": results
                    }

    return {
        "success": True,
        "total_synced": total_synced,
        "total_freed_mb": round(total_freed_mb, 2),
        "results": results
    }


def upload_batch_to_youtube(
    batch_index: int,
    visibility: str = "SCHEDULE",
    schedule_interval_hours: float = 0.0,
    headless: bool = False,
    checkpoint_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Coordena o envio de todos os vídeos pendentes de um lote específico.
    Se visibility='SCHEDULE' e schedule_interval_hours=0, utiliza a alocação de slots fixos GMT.
    """
    targets = get_batch_videos_to_upload(batch_index, checkpoint_dir=checkpoint_dir)
    if not targets:
        return {
            "success": True,
            "message": f"Nenhum vídeo pendente para envio no batch_{batch_index}.",
            "batch_index": batch_index,
            "uploaded_count": 0
        }

    uploaded_count = 0
    results = []

    print(f"\n{'=' * 75}")
    print(f"🚀 INICIANDO POSTAGEM NO YOUTUBE: BATCH {batch_index} ({len(targets)} vídeos pendentes)")
    print(f"{'=' * 75}\n")

    for t in targets:
        v_idx = t["video_index"]
        res = upload_and_clean_single_video(batch_index, v_idx, checkpoint_dir=checkpoint_dir, headless=headless)
        if res.get("success"):
            uploaded_count += 1
            results.append(res)
        else:
            if "não autenticada" in res.get("error", "").lower():
                break

    return {
        "success": uploaded_count == len(targets),
        "batch_index": batch_index,
        "total_targets": len(targets),
        "uploaded_count": uploaded_count,
        "results": results
    }


def main():
    parser = argparse.ArgumentParser(description="Automação de Upload e Agendamento de Shorts no YouTube Studio (Slots 11h, 13h, 15h, 17h GMT)")
    parser.add_argument("--batch", type=int, default=None, help="Índice do batch para postar (ex: 1, 2, 3)")
    parser.add_argument("--video", nargs=2, type=int, metavar=("BATCH", "VIDEO"), help="Posta um único vídeo específico (ex: --video 2 0)")
    parser.add_argument("--sync-backlog", "--sync-all", action="store_true", help="Processa e agenda todo o backlog de vídeos não postados em todos os batches")
    parser.add_argument("--login", action="store_true", help="Abre o navegador visível para login interativo e salva a sessão")
    parser.add_argument("--headless", action="store_true", help="Executa o navegador em modo oculto (headless)")
    parser.add_argument("--visibility", type=str, default="SCHEDULE", choices=["SCHEDULE", "PUBLIC", "UNLISTED", "PRIVATE"], help="Visibilidade padrão")
    args = parser.parse_args()

    if args.login:
        uploader = YouTubeStudioUploader(headless=False)
        uploader.open_interactive_login()
        return

    if args.sync_backlog:
        res = sync_all_unposted_videos(headless=args.headless)
        print("\nResultado da Sincronização do Backlog:", res)
        return

    if args.video:
        b_num, v_num = args.video
        res = upload_and_clean_single_video(b_num, v_num, headless=args.headless)
        print("\nResultado do Upload do Vídeo:", res)
        return

    if args.batch is not None:
        res = upload_batch_to_youtube(
            batch_index=args.batch,
            visibility=args.visibility,
            headless=args.headless
        )
        print("\nResultado da Operação:", res)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
