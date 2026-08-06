import logging
import os
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request
# app.py와 같은 폴더의 .env 파일 로드
load_dotenv(
    Path(__file__).resolve().parent / ".env",
    override=True
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("geef-worker")

app = Flask(__name__)


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class SupabaseClient:
    def __init__(self) -> None:
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self.timeout = int(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))

    def configured(self) -> bool:
        return bool(self.url and self.key)

    def rpc(self, function_name: str, payload: dict[str, Any]) -> Any:
        if not self.configured():
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        response = requests.post(
            f"{self.url}/rest/v1/rpc/{function_name}",
            headers={
                "apikey": self.key,
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        if not response.ok:
            raise RuntimeError(
                f"RPC {function_name} failed ({response.status_code}): {response.text[:1000]}"
            )
        if response.status_code == 204 or not response.text.strip():
            return None
        return response.json()


supabase = SupabaseClient()


def build_context(job: dict[str, Any]) -> dict[str, Any]:
    source = job.get("context") or job.get("input_payload") or {}
    return {
        "language": source.get("language", "ko"),
        "genre": source.get("genre", "Korean Ballad"),
        "theme": source.get("theme", source.get("title", "새로운 시작과 따뜻한 위로")),
        "mood": source.get("mood", ["따뜻함", "희망", "위로"]),
        "target_audience": source.get("target_audience", "한국어 성인 청취자"),
        "vocal_style": source.get("vocal_style", "warm and emotional"),
        "target_duration_seconds": int(source.get("target_duration_seconds", 210)),
        "tempo_bpm": int(source.get("tempo_bpm", 76)),
        "instrument_style": source.get("instrument_style", "acoustic guitar, piano, soft strings"),
        "arrangement_style": source.get("arrangement_style", "verse-pre-chorus-bridge-final"),
        "mix_style": source.get("mix_style", "warm, clear vocal, natural dynamics"),
        "master_style": source.get("master_style", "streaming-ready balanced master"),
        "musical_key": source.get("musical_key", "G Major"),
        "time_signature": source.get("time_signature", "4/4"),
        "video_style": source.get("video_style", "cinematic Korean daily-life storytelling"),
        "aspect_ratio": source.get("aspect_ratio", "16:9"),
        "context_status": "READY",
    }


def run_ef01(job: dict[str, Any]) -> dict[str, Any]:
    required = ["content_uuid", "workflow_run_id", "module_run_id"]
    missing = [field for field in required if not job.get(field)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    context = build_context(job)
    if env_bool("DRY_RUN", True):
        return {"dry_run": True, "module_code": "EF-01", "context": context}

    saved = supabase.rpc(
        os.getenv("RPC_SAVE_CONTEXT", "geef_save_project_context"),
        {
            "p_content_uuid": job["content_uuid"],
            "p_workflow_run_id": job["workflow_run_id"],
            "p_module_run_id": job["module_run_id"],
            "p_context": context,
        },
    )
    return {"dry_run": False, "module_code": "EF-01", "saved_context": saved}


def get_next_module(workflow_run_id: str) -> dict[str, Any]:
    result = supabase.rpc(
        os.getenv("RPC_GET_NEXT_MODULE", "geef_get_next_queued_module"),
        {"p_workflow_run_id": workflow_run_id},
    )
    if isinstance(result, list):
        return result[0] if result else {"found": False}
    return result or {"found": False}


@app.get("/")
@app.get("/health")
def health():
    return jsonify(
        {
            "ok": True,
            "service": "geef-cloud-run-worker",
            "dry_run": env_bool("DRY_RUN", True),
            "supabase_configured": supabase.configured(),
            "supported_modules": ["EF-00", "EF-01"],
        }
    )


@app.post("/next-module")
def next_module():
    body = request.get_json(silent=True) or {}
    workflow_run_id = body.get("workflow_run_id")
    if not workflow_run_id:
        return jsonify({"ok": False, "error": "workflow_run_id is required"}), 400
    try:
        return jsonify({"ok": True, "next_module": get_next_module(workflow_run_id)})
    except Exception as exc:
        logger.exception("next-module failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/execute")
def execute():
    started = time.perf_counter()
    body = request.get_json(silent=True) or {}
    module_code = body.get("module_code", "EF-01")
    try:
        if module_code == "EF-00":
            result = {
                "dry_run": env_bool("DRY_RUN", True),
                "module_code": "EF-00",
                "message": "Project Control accepted",
            }
        elif module_code == "EF-01":
            result = run_ef01(body)
        else:
            return jsonify({"ok": False, "error": f"Unsupported module: {module_code}"}), 400
        result["duration_ms"] = round((time.perf_counter() - started) * 1000)
        return jsonify({"ok": True, "result": result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.exception("execution failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
