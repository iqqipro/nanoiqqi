"""Image generation tool via OpenRouter (modalities image)."""

import base64
import re
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from nanoiqqi.agent.tools.base import Tool
from nanoiqqi.utils.helpers import ensure_dir


OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_IMAGE_MODEL = "black-forest-labs/flux-2-pro"


class GenerateImageTool(Tool):
    """
    Generate images from a text prompt using OpenRouter image-capable models
    (e.g. Flux, Sourceful). Saves images to workspace and returns their paths.
    """

    name = "generate_image"
    description = (
        "Generate an image from a text prompt. Use when the user asks for a photo, "
        "illustration, drawing, or picture. Returns the path to the saved image file. "
        "The 'prompt' must describe the image only; use the optional 'model' parameter to try a different image model, not the prompt."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Description of the image to generate (e.g. 'a cute fluffy orange cat'). Do NOT put a model name here.",
            },
            "model": {
                "type": "string",
                "description": "Optional. Image model id (e.g. black-forest-labs/flux-2-pro). Only use to try another model; leave empty to use default.",
            },
        },
        "required": ["prompt"],
    }

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str = DEFAULT_IMAGE_MODEL,
        workspace: Path | None = None,
    ):
        self.api_key = api_key or ""
        self.default_model = default_model
        self.workspace = workspace or Path.cwd()

    async def execute(
        self,
        prompt: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not self.api_key:
            return "Error: OpenRouter API key not configured for image generation. Set providers.openrouter.api_key in config."

        # OpenRouter API expects model id without "openrouter/" prefix (e.g. bytedance-seed/seedream-4.5)
        model_id = (model or self.default_model).strip()
        if model_id.startswith("openrouter/"):
            model_id = model_id[len("openrouter/") :]

        out_dir = ensure_dir(self.workspace / ".nanoiqqi" / "generated")
        safe_name = "".join(c for c in prompt[:40] if c.isalnum() or c in (" ", "-", "_"))[:40].strip() or "image"
        safe_name = safe_name.replace(" ", "_")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(
                    OPENROUTER_CHAT_URL,
                    json={
                        "model": model_id,
                        "messages": [{"role": "user", "content": prompt}],
                        "modalities": ["image"],
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/nanoiqqi",
                    },
                )
                r.raise_for_status()
                data = r.json()

            choice = (data.get("choices") or [None])[0]
            if not choice:
                return "Error: No response from image model."

            message = choice.get("message") or {}
            images = message.get("images") or []
            content = message.get("content") or ""

            saved_paths: list[str] = []
            for i, img in enumerate(images):
                url = _get_image_url(img)
                if not url:
                    continue
                b64 = _extract_base64_from_data_url(url)
                if not b64:
                    continue
                ext = ".png"
                path = out_dir / f"{safe_name}_{i}{ext}"
                path.write_bytes(base64.b64decode(b64))
                saved_paths.append(str(path))

            if not saved_paths:
                logger.warning(
                    "Image model returned no images. message keys: {}, content: {}",
                    list(message.keys()),
                    (content or "")[:200],
                )
                return (
                    f"Error: Model did not return an image. Response: {content[:200] if content else 'empty'}"
                )

            result = f"Image(s) saved: {', '.join(saved_paths)}"
            result += f"\nUse this exact path in the message tool when sending to the user: {saved_paths[0]}"
            if len(saved_paths) > 1:
                result += f" (and {saved_paths[1:]})"
            result += ". Do not invent or change the path."
            if content:
                result += f"\nCaption: {content[:300]}"
            return result

        except httpx.HTTPStatusError as e:
            body = (e.response.text or "")[:500]
            logger.warning("Image API error {}: {}", e.response.status_code, body)
            return f"Error: Image API returned {e.response.status_code}: {body}"
        except Exception as e:
            logger.exception("Image generation failed")
            return f"Error: {e}"


def _get_image_url(img: Any) -> str | None:
    """Extract image URL from OpenRouter response (supports image_url and imageUrl)."""
    if isinstance(img, str):
        return img
    if not isinstance(img, dict):
        return None
    # OpenRouter may return image_url (snake_case) or imageUrl (camelCase)
    for key in ("image_url", "imageUrl"):
        obj = img.get(key)
        if isinstance(obj, dict) and obj.get("url"):
            return obj["url"]
    return img.get("url")


def _extract_base64_from_data_url(url: str) -> str | None:
    """Extract base64 payload from a data URL (e.g. data:image/png;base64,...)."""
    if not url:
        return None
    m = re.match(r"data:image/[^;]+;base64,(.+)", url.strip())
    if m:
        return m.group(1).strip()
    if url.startswith("data:"):
        parts = url.split(",", 1)
        if len(parts) == 2:
            return parts[1].strip()
    return None
