import os
import sys
import time
import json
import psutil

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) == "scripts" else CURRENT_DIR
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

from google import genai
from agents import DirectorAgent, ReviewerAgent, resolve_gemini_api_key
from broll_engine import BRollEngine

api_key = resolve_gemini_api_key()
if not api_key:
    print("❌ Chave de API Gemini não encontrada em gemini-api.txt, .env ou ambiente.")
    sys.exit(1)
os.environ["GEMINI_API_KEY"] = api_key

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Conjunto de cenas padronizadas para testes de estresse
BENCHMARK_TOPIC = "Camp Century: A Cidade Nuclear Secreta Sob o Gelo da Groenlândia"
BENCHMARK_SCENES = [
    {
        "scene_id": 1,
        "fala": "Em plena Guerra Fria, o exército americano construiu uma base subterrânea ultrassecreta sob a calota de gelo.",
        "youtube_query": "Camp Century Greenland nuclear ice documentary 4k",
        "duracao_estimada": 3.5
    },
    {
        "scene_id": 2,
        "fala": "A instalação inteira era energizada pelo primeiro reator nuclear militar móvel do mundo.",
        "youtube_query": "Camp Century nuclear reactor US Army real footage",
        "duracao_estimada": 3.5
    },
    {
        "scene_id": 3,
        "fala": "Quilômetros de túneis abrigavam centenas de militares e cientistas a dezenas de metros sob a neve.",
        "youtube_query": "Camp Century ice tunnels underground military 4k",
        "duracao_estimada": 3.5
    },
    {
        "scene_id": 4,
        "fala": "Mas o movimento lento das geleiras começou a esmagar as estruturas, forçando o abandono repentino da base.",
        "youtube_query": "Camp Century Greenland glacier abandoned mystery",
        "duracao_estimada": 3.5
    }
]

def run_benchmark_for_workers(worker_count: int, run_id: int) -> dict:
    print("\n" + "=" * 70)
    print(f"🧪 INICIANDO TESTE EMPÍRICO: max_workers = {worker_count} (Rodada {run_id})")
    print("=" * 70)

    test_dir = os.path.join(PROJECT_ROOT, "data", f"benchmark_run_w{worker_count}_r{run_id}")
    os.makedirs(test_dir, exist_ok=True)

    broll_engine = BRollEngine(max_search_results=4)
    reviewer = ReviewerAgent()

    cpu_start = psutil.cpu_percent(interval=0.5)
    mem_start = psutil.virtual_memory().percent
    start_time = time.time()

    status_events = []
    def on_status(msg):
        t_rel = round(time.time() - start_time, 2)
        status_events.append({"time": t_rel, "msg": msg})
        print(f"  [{t_rel:05.1f}s] {msg}")

    progress_events = []
    def on_progress(done, total):
        t_rel = round(time.time() - start_time, 2)
        progress_events.append({"time": t_rel, "done": done, "total": total})

    try:
        scene_clips, scene_audits = broll_engine.process_all_scenes_parallel(
            cenas=BENCHMARK_SCENES,
            global_topic=BENCHMARK_TOPIC,
            reviewer_agent=reviewer,
            project_dir=test_dir,
            total_audio_duration=14.0,
            max_workers=worker_count,
            status_callback=on_status,
            progress_callback=on_progress
        )
        elapsed = round(time.time() - start_time, 2)
        cpu_end = psutil.cpu_percent(interval=0.5)
        mem_end = psutil.virtual_memory().percent

        success_count = len(scene_clips)
        expected_count = len(BENCHMARK_SCENES)

        avg_score = 0.0
        if scene_audits:
            avg_score = round(sum(a.get("score", 0) for a in scene_audits) / len(scene_audits), 2)

        result_data = {
            "worker_count": worker_count,
            "run_id": run_id,
            "success": success_count == expected_count,
            "scenes_delivered": success_count,
            "scenes_expected": expected_count,
            "total_elapsed_seconds": elapsed,
            "throughput_scenes_per_minute": round((success_count / elapsed) * 60, 2) if elapsed > 0 else 0,
            "avg_reviewer_score": avg_score,
            "cpu_percent_peak": max(cpu_start, cpu_end),
            "mem_percent_peak": max(mem_start, mem_end),
            "status_events_count": len(status_events)
        }

        print("\n📊 RESULTADO DA RODADA:")
        print(json.dumps(result_data, indent=2, ensure_ascii=False))
        return result_data

    except Exception as e:
        elapsed = round(time.time() - start_time, 2)
        err_data = {
            "worker_count": worker_count,
            "run_id": run_id,
            "success": False,
            "error": str(e),
            "total_elapsed_seconds": elapsed
        }
        print(f"❌ ERRO NA RODADA max_workers={worker_count}: {str(e)}")
        return err_data

def main():
    print("=" * 80)
    print("🔬 BATERIA DE TESTES EXPERIMENTAIS DE ESCALABILIDADE E CONCORRÊNCIA")
    print("=" * 80)

    worker_configs = [1, 2, 3, 4, 5, 6]
    all_results = []

    for w in worker_configs:
        res = run_benchmark_for_workers(worker_count=w, run_id=1)
        all_results.append(res)
        print("\n⏳ Cooldown de 10 segundos entre testes para estabilização de rede e CPU...")
        time.sleep(10)

    log_dir = os.path.join(PROJECT_ROOT, "logs")
    os.makedirs(log_dir, exist_ok=True)
    report_file = os.path.join(log_dir, "benchmark_concurrency_report.json")

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print(f"🏆 RELATÓRIO FINAL DE BENCHMARK GRAVADO EM: {report_file}")
    print("=" * 80)

    print("\n| Workers | Tempo Total (s) | Cenas/min | Taxa Sucesso | CPU (%) | Score Médio |")
    print("|:---:|:---:|:---:|:---:|:---:|:---:|")
    for r in all_results:
        w = r.get("worker_count")
        t = r.get("total_elapsed_seconds")
        tp = r.get("throughput_scenes_per_minute", 0)
        s = "100%" if r.get("success") else "FALHOU"
        cpu = r.get("cpu_percent_peak", 0)
        score = r.get("avg_reviewer_score", 0)
        print(f"| **{w}** | {t:.1f}s | {tp:.1f} | {s} | {cpu:.1f}% | {score}/10 |")

if __name__ == "__main__":
    main()
