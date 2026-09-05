# Kling Bridge para ChatGPT

Middleware que permite a un GPT personalizado (ChatGPT) animar una imagen usando la API de Kling AI.

## Cómo funciona

1. Dentro de ChatGPT editas una imagen (esto ya lo hace ChatGPT de forma nativa).
2. Tu GPT personalizado, mediante una Action, llama a `POST /animate` de este servicio con la URL de la imagen y el prompt de animación.
3. Este servicio llama a la API de Kling y devuelve un `task_id` de inmediato (Kling tarda minutos en generar el video).
4. El GPT vuelve a llamar a `GET /status/{task_id}` cada cierto tiempo hasta que el estado sea `succeed`, momento en el que la respuesta incluye la URL del video final.

## Variables de entorno (se configuran en el panel de Render, nunca en el código)

| Variable | Obligatoria | Descripción |
|---|---|---|
| `KLING_ACCESS_KEY` | Sí | Access Key generada en kling.ai/dev/api-key |
| `KLING_SECRET_KEY` | Sí | Secret Key generada en kling.ai/dev/api-key |
| `BRIDGE_API_KEY` | Recomendada | Una clave que tú inventas para proteger este servicio. El GPT debe enviarla en el header `X-API-Key`. Sin esto, cualquiera que descubra la URL pública podría gastar tu saldo de Kling. |
| `KLING_BASE_URL` | No | Por defecto `https://api.klingai.com/v1`. Revisa en tu cuenta cuál es tu base URL real. |

## Despliegue en Render

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Conectarlo a un GPT personalizado

1. Ve a ChatGPT → "Explore GPTs" → "Create" → pestaña "Configure".
2. En "Actions", clic en "Create new action".
3. Pega el contenido de `openapi.yaml` (cambiando `TU-SERVICIO.onrender.com` por la URL real que te da Render).
4. En autenticación, elige "API Key", header `X-API-Key`, y pega el mismo valor que pusiste en `BRIDGE_API_KEY`.
5. En las instrucciones del GPT, indícale que primero llame a `animateImage`, guarde el `task_id`, y luego llame a `getAnimationStatus` cada 20-30 segundos hasta recibir `video_url`.
