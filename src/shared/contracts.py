from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class RenderSpec:
    aspect: str = "9:16"
    width: int = 1080
    height: int = 1920
    scene_seconds: int = 3
    fps: int = 30


@dataclass
class AudioSpec:
    music_style: str = "funk_carioca_instrumental"
    music_volume: float = 0.6
    voice: str = "optional"


@dataclass
class PricingSpec:
    currency: str = "USD"
    estimated_cogs: float = 0.0
    suggested_price: float = 0.0
    margin_target: float = 0.5


@dataclass
class SceneSpec:
    id: int
    hook: str
    prompt: str
    motion: str = "zoom_in"


@dataclass
class JobSpec:
    job_id: str
    product_name: str
    market: str
    mode: str
    scenes: List[SceneSpec]
    render_spec: RenderSpec = field(default_factory=RenderSpec)
    audio_spec: AudioSpec = field(default_factory=AudioSpec)
    pricing: PricingSpec = field(default_factory=PricingSpec)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class JobResult:
    job_id: str
    status: str
    final_video_uri: Optional[str] = None
    artifacts: Dict[str, str] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
