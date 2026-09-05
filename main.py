"""
Middleware entre un GPT personalizado (ChatGPT) y la API de Kling AI.

Expone dos endpoints pensados para usarse como "Action" de un GPT:

  POST /animate         -> crea una tarea de image-to-video en Kling y devuelve un task_id
  GET  /status/{task_id} -> consulta el estado de la tarea y, cuando termina, la URL del video

Por qué dos endpoints y no uno solo que "espere":
  Kling tarda entre ~1 y 5 minutos en generar un video. Las Actions de un GPT
  personalizado tienen un timeout corto (unos 45s), así que no podemos
  bloquear la respuesta esperando el video. El GPT primero llama a /animate,
  y luego (el propio modelo, siguiendo las instrucciones del GPT) vuelve a
  llamar a /status/{task_id} cada cierto tiempo hasta que el estado sea
  "succeed" o "failed".

Variables de entorno requeridas:
  KLING_API_KEY      -> la API Key que generaste en kling.ai/dev/api-key
  BRIDGE_API_KEY     -> una clave que TÚ inventas, para proteger este middleware
                         (el GPT la manda en el header "X-API-Key"). Sin esto,
                         cualquiera que encuentre la URL podría gastar tu saldo de Kling.

Variables opcionales:
  KLING_BASE_URL     -> por defecto https://api.klingai.com/v1
                         (revisa en tu panel de KlingAI cuál es tu base URL real,
                         algunas cuentas usan un dominio regional distinto)
"""

import os
from typing import Optional

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

KLING_API_KEY = os.environ.get("KLING_API_KEY", "")
BRIDGE_API_KEY = os.environ.get("BRIDGE_API_KEY", "")
KLING_BASE_URL = os.environ.get("KLING_BASE_URL", "https://api.klingai.com/v1")

app = FastAPI(
    title="Kling Bridge para ChatGPT",
    description="Middleware que permite a un GPT personalizado animar imágenes con Kling AI.",
    version="1.0.0",
)


def check_bridge_key(x_api_key: Optional[str]) -> None:
    """Verifica que quien llama a este middleware tenga la clave que definiste tú."""
    if not BRIDGE_API_KEY:
        # Si no configuraste ninguna clave propia, no bloqueamos (útil solo para pruebas locales).
        return
    if x_api_key != BRIDGE_API_KEY:
        raise HTTPException(status_code=401, detail="X-API-Key inválida o ausente.")


def kling_headers() -> dict:
    if not KLING_API_KEY:
        raise HTTPException(status_code=500, detail="Falta KLING_API_KEY en el servidor.")
    return {"Authorization": f"Bearer {KLING_API_KEY}"}


class AnimateRequest(BaseModel):
    image_url: str = Field(..., description="URL pública de la imagen ya editada por ChatGPT.")
    prompt: str = Field(..., description="Descripción del movimiento/animación deseado.")
    negative_prompt: Optional[str] = Field(None, description="Qué evitar en la animación.")
    duration: str = Field("5", description="Duración del video en segundos: '5' o '10'.")
    mode: str = Field("std", description="'std' (estándar) o 'pro' (más calidad, más costo).")
    model_name: Optional[str] = Field(None, description="Modelo de Kling a usar, ej. 'kling-v2-6'. Si se omite, Kling usa su default.")


class AnimateResponse(BaseModel):
    task_id: str
    task_status: str


class StatusResponse(BaseModel):
    task_id: str
    task_status: str
    video_url: Optional[str] = None
    message: Optional[str] = None


@app.post("/animate", response_model=AnimateResponse)
def animate(body: AnimateRequest, x_api_key: Optional[str] = Header(None)):
    check_bridge_key(x_api_key)

    kling_payload = {
        "image": body.image_url,
        "prompt": body.prompt,
        "duration": body.duration,
        "mode": body.mode,
    }
    if body.negative_prompt:
        kling_payload["negative_prompt"] = body.negative_prompt
    if body.model_name:
        kling_payload["model_name"] = body.model_name

    headers = kling_headers()
    headers["Content-Type"] = "application/json"

    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{KLING_BASE_URL}/videos/image2video", json=kling_payload, headers=headers)

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=f"Error de Kling: {resp.text}")

    data = resp.json()
    task_data = data.get("data", {})
    task_id = task_data.get("task_id")
    task_status = task_data.get("task_status", "submitted")

    if not task_id:
        raise HTTPException(status_code=502, detail=f"Respuesta inesperada de Kling: {data}")

    return AnimateResponse(task_id=task_id, task_status=task_status)


@app.get("/status/{task_id}", response_model=StatusResponse)
def status(task_id: str, x_api_key: Optional[str] = Header(None)):
    check_bridge_key(x_api_key)

    headers = kling_headers()

    with httpx.Client(timeout=30) as client:
        resp = client.get(f"{KLING_BASE_URL}/videos/image2video/{task_id}", headers=headers)

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=f"Error de Kling: {resp.text}")

    data = resp.json()
    task_data = data.get("data", {})
    task_status = task_data.get("task_status", "unknown")

    video_url = None
    videos = (task_data.get("task_result") or {}).get("videos") or []
    if videos:
        video_url = videos[0].get("url")

    return StatusResponse(
        task_id=task_id,
        task_status=task_status,
        video_url=video_url,
        message=task_data.get("task_status_msg"),
    )


@app.get("/health")
def health():
    return {"ok": True}
