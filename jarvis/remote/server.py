import asyncio
import sys
import threading
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import biometrics, config, control
from ..brain import llm
from ..skills import call_tool, confirm, get_tool, get_tool_schemas
from . import auth, broadcaster

_server: Optional[uvicorn.Server] = None


def _webapp_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "jarvis" / "webapp" / "static"
    return Path(__file__).resolve().parent.parent / "webapp" / "static"


class CommandRequest(BaseModel):
    text: str
    session_id: Optional[str] = "remote"


class SkillInvokeRequest(BaseModel):
    args: dict = {}


def create_app() -> FastAPI:
    app = FastAPI(title="Jarvis Remote")

    @app.on_event("startup")
    async def _on_startup():
        broadcaster.set_loop(asyncio.get_running_loop())

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/biometrics/status", dependencies=[Depends(auth.require_token)])
    def biometric_status():
        return {
            "enabled": config.GNANI_BIOMETRICS_ENABLED,
            "configured": config.biometrics_configured(),
            "speaker": config.GNANI_BIOMETRIC_SPEAKER,
        }

    @app.post("/api/biometrics/enroll", dependencies=[Depends(auth.require_token)])
    def enroll_voice():
        """Records eight consented seconds on Jarvis's local microphone."""
        result = biometrics.enroll_from_microphone()
        broadcaster.publish({"type": "log", "line": f"Voice enrollment: {result.message}"})
        return {"ok": result.verified, "message": result.message}

    @app.delete("/api/biometrics/enrollment", dependencies=[Depends(auth.require_token)])
    def delete_voice_enrollment():
        result = biometrics.delete_enrollment()
        broadcaster.publish({"type": "log", "line": f"Voice enrollment deletion: {result.message}"})
        return {"ok": result.verified, "message": result.message}

    @app.get("/api/skills", dependencies=[Depends(auth.require_token)])
    def list_skills():
        return {"skills": [schema["function"] for schema in get_tool_schemas()]}

    @app.post(
        "/api/skills/{name}/invoke", dependencies=[Depends(auth.require_token)]
    )
    def invoke_skill(name: str, body: SkillInvokeRequest):
        entry = get_tool(name)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"Unknown skill: {name}")

        allowed = set(entry["schema"]["function"]["parameters"].get("properties", {}))
        unknown = set(body.args) - allowed
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown argument(s): {', '.join(sorted(unknown))}",
            )

        confirm.begin_turn("remote-ui")
        result = call_tool(name, body.args)
        broadcaster.publish({"type": "log", "line": f"Skill: {name} -> {result}"})
        return {"result": result}

    @app.post("/api/command", dependencies=[Depends(auth.require_token)])
    def command(body: CommandRequest):
        broadcaster.publish({"type": "log", "line": f"You: {body.text}"})
        reply = llm.process(body.text, session_id=body.session_id or "remote")
        broadcaster.publish({"type": "log", "line": f"Jarvis: {reply}"})
        return {"reply": reply}

    @app.get("/api/status", dependencies=[Depends(auth.require_token)])
    def status():
        return {"status": broadcaster.last_status, "history": broadcaster.recent(50)}

    @app.get("/api/history", dependencies=[Depends(auth.require_token)])
    def history(limit: int = 100):
        return {"events": broadcaster.recent(limit)}

    @app.post("/api/control/stop", dependencies=[Depends(auth.require_token)])
    def stop():
        control.cancel_event.set()
        broadcaster.publish({"type": "log", "line": "Stopped from remote"})
        return {"ok": True}

    @app.post("/api/control/quit", dependencies=[Depends(auth.require_token)])
    def quit_app():
        control.request_shutdown()
        return {"ok": True}

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        if not await auth.require_token_ws(websocket):
            return
        await websocket.accept()
        for event in broadcaster.recent(50):
            await websocket.send_json(event)

        queue = broadcaster.subscribe()
        try:
            while True:
                event = await queue.get()
                await websocket.send_json(event)
        except WebSocketDisconnect:
            pass
        finally:
            broadcaster.unsubscribe(queue)

    webapp_dir = _webapp_dir()
    if webapp_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(webapp_dir), html=True), name="webapp")

    return app


def run_server_in_thread():
    """Starts the remote-control server on a background daemon thread.
    Never raises - a failure here (e.g. port already in use) is logged but
    must not take down the voice assistant."""
    global _server

    def _run():
        global _server
        try:
            cfg = uvicorn.Config(
                create_app(),
                host="0.0.0.0",
                port=config.REMOTE_PORT,
                log_level="warning",
            )
            _server = uvicorn.Server(cfg)
            _server.install_signal_handlers = False
            _server.run()
        except Exception as exc:
            print(f"[remote] failed to start remote-control server: {exc}")

    threading.Thread(target=_run, daemon=True).start()


def stop_server():
    if _server is not None:
        _server.should_exit = True
