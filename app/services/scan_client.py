"""
Wraps Thorn Safer (https://safer.io) for image/video CSAM hash-matching +
classifier scanning. Requires a real account and API key before launch —
this stub returns a "no hit" result so the rest of the pipeline is
testable end-to-end without live credentials, but MUST be replaced with
a real integration before any real user content flows through it.
"""

from dataclasses import dataclass

from app.config import settings


@dataclass
class ScanResult:
    hit: bool
    classifier_score: float = 0.0
    raw: dict | None = None


async def scan(media_bytes: bytes, media_type: str) -> ScanResult:
    if not settings.safer_api_key:
        # No key configured — fail loud in logs so this can't be missed,
        # but don't block local development entirely.
        print("[WARNING] SAFER_API_KEY not set — media_pipeline is running "
              "with a stubbed scanner. DO NOT use this in production.")
        return ScanResult(hit=False)

    # TODO: real integration, e.g.:
    # response = await httpx.post(
    #     "https://api.safer.io/v2/scan",
    #     headers={"Authorization": f"Bearer {settings.safer_api_key}"},
    #     files={"file": media_bytes},
    # )
    # data = response.json()
    # return ScanResult(hit=data["match_found"], classifier_score=data.get("score", 0), raw=data)
    return ScanResult(hit=False)
