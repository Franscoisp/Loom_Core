"""Multi-LLM provider configuration (spec §9).

Model-agnostic design. Providers (DeepSeek, OpenAI, Anthropic, Groq, Ollama,
etc.) are registered with API keys, base URLs, and default model names. The
active provider and model are stored per-project in a ``models.json`` profile
under ``~/.loom/`` — no secrets are ever written to memory or committed.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from loom_core.locking import FileLock

LOOM_HOME = Path.home() / ".loom"
LOOM_HOME.mkdir(parents=True, exist_ok=True)
MODELS_PATH = LOOM_HOME / "models.json"
ACTIVE_MODEL_PATH = LOOM_HOME / "active-model"


@dataclass
class ProviderConfig:
    name: str  # e.g. "deepseek", "openai", "groq"
    base_url: str = ""
    api_key_env: str = ""  # env-var name, never the value itself
    default_model: str = ""


@dataclass
class ModelsConfig:
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    active: str = ""  # provider name currently in use
    default_model: str = ""  # model override for the active provider


class ModelStore:
    """Persist multi-LLM provider config (spec §9)."""

    def __init__(self) -> None:
        self.path = MODELS_PATH

    def _load(self) -> ModelsConfig:
        if not self.path.exists():
            return ModelsConfig()
        with FileLock(self.path):
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        providers = {}
        provs_raw = raw.get("providers", {})
        if isinstance(provs_raw, dict):
            for name, data in provs_raw.items():
                providers[name] = ProviderConfig(
                    name=data.get("name", name),
                    base_url=data.get("base_url", ""),
                    api_key_env=data.get("api_key_env", ""),
                    default_model=data.get("default_model", ""),
                )
        return ModelsConfig(
            providers=providers,
            active=raw.get("active", ""),
            default_model=raw.get("default_model", ""),
        )

    def _save(self, cfg: ModelsConfig) -> None:
        data: dict[str, object] = {
            "providers": {k: asdict(v) for k, v in cfg.providers.items()},
            "active": cfg.active,
            "default_model": cfg.default_model,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(data, fh, indent=2, sort_keys=True)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    def add_provider(
        self,
        name: str,
        base_url: str = "",
        api_key_env: str = "",
        default_model: str = "",
    ) -> ProviderConfig:
        cfg = self._load()
        prov = ProviderConfig(
            name=name,
            base_url=base_url,
            api_key_env=api_key_env,
            default_model=default_model,
        )
        cfg.providers[name] = prov
        self._save(cfg)
        return prov

    def list_providers(self) -> list[ProviderConfig]:
        cfg = self._load()
        result: list[ProviderConfig] = []
        for _name, prov in cfg.providers.items():
            result.append(prov)
        return sorted(result, key=lambda p: p.name)

    def get_provider(self, name: str) -> ProviderConfig | None:
        return self._load().providers.get(name)

    def active_provider_name(self) -> str | None:
        cfg = self._load()
        name = cfg.active or None
        if name is None and ACTIVE_MODEL_PATH.exists():
            name = ACTIVE_MODEL_PATH.read_text(encoding="utf-8").strip() or None
        return name

    def set_active(self, name: str) -> None:
        cfg = self._load()
        if name not in cfg.providers:
            raise ValueError(
                f"provider {name!r} is not configured; use 'loom models add' first"
            )
        cfg.active = name
        self._save(cfg)
        ACTIVE_MODEL_PATH.write_text(name + "\n", encoding="utf-8", newline="\n")

    def set_active_model(self, model: str) -> None:
        cfg = self._load()
        cfg.default_model = model
        self._save(cfg)

    def active_model(self) -> str | None:
        cfg = self._load()
        return cfg.default_model or None

    def active_provider(self) -> ProviderConfig | None:
        name = self.active_provider_name()
        if name is None:
            return None
        return self.get_provider(name)

    def remove_provider(self, name: str) -> bool:
        cfg = self._load()
        if name not in cfg.providers:
            return False
        del cfg.providers[name]
        if cfg.active == name:
            cfg.active = next(iter(cfg.providers), "")
        self._save(cfg)
        return True

    def is_configured(self) -> bool:
        cfg = self._load()
        prov = cfg.active or None
        if prov is None:
            return False
        pcfg = cfg.providers.get(prov)
        if pcfg is None:
            return False
        return os.environ.get(pcfg.api_key_env.strip(), "").strip() != ""


# built-in defaults for known providers (spec §9)
DEFAULT_PROVIDERS: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "api_key_env": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-20250514",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "api_key_env": "",
        "default_model": "llama3",
    },
}
