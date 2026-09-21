"""Check that the external tools yt-dlp relies on are installed."""

import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class Tool:
    name: str
    required: bool
    purpose: str


TOOLS = (
    Tool("ffmpeg", required=True, purpose="merging video and audio streams"),
    Tool("ffprobe", required=True, purpose="inspecting downloaded media"),
    Tool("deno", required=False, purpose="solving YouTube's JavaScript challenges"),
)

INSTALL_HINT = "Install with: brew install ffmpeg deno"


@dataclass(frozen=True)
class PreflightResult:
    missing_required: list[Tool]
    missing_optional: list[Tool]

    @property
    def ok(self) -> bool:
        return not self.missing_required


def check_tools() -> PreflightResult:
    missing = [tool for tool in TOOLS if shutil.which(tool.name) is None]
    return PreflightResult(
        missing_required=[t for t in missing if t.required],
        missing_optional=[t for t in missing if not t.required],
    )
