import json
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
from backend.app.config import STORAGE_DIR
from backend.app.models.schemas import ProjectState

def get_project_dir(project_id: str) -> Path:
    project_dir = STORAGE_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "images").mkdir(exist_ok=True)
    (project_dir / "audio").mkdir(exist_ok=True)
    (project_dir / "video").mkdir(exist_ok=True)
    (project_dir / "subtitles").mkdir(exist_ok=True)
    (project_dir / "thumbnail").mkdir(exist_ok=True)
    return project_dir

def save_project_state(project: ProjectState) -> None:
    project_dir = get_project_dir(project.id)
    state_file = project_dir / "project.json"
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(project.model_dump(), f, indent=2, ensure_ascii=False)

def load_project_state(project_id: str) -> Optional[ProjectState]:
    project_dir = get_project_dir(project_id)
    state_file = project_dir / "project.json"
    if not state_file.exists():
        return None
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return ProjectState(**data)
    except Exception as e:
        print(f"Error loading project {project_id}: {e}")
        return None

def list_all_projects() -> list[Dict[str, Any]]:
    projects = []
    if not STORAGE_DIR.exists():
        return projects
    for p_dir in STORAGE_DIR.iterdir():
        if p_dir.is_dir():
            state_file = p_dir / "project.json"
            if state_file.exists():
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        projects.append({
                            "id": data.get("id"),
                            "title": data.get("title", "Untitled Project"),
                            "topic": data.get("topic", ""),
                            "video_format": data.get("video_format", "shorts_9_16"),
                            "status": data.get("status", "idle"),
                            "current_step": data.get("current_step", 1),
                            "has_video": bool(data.get("final_video_path"))
                        })
                except Exception:
                    continue
    return sorted(projects, key=lambda x: x["id"], reverse=True)
