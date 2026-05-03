"""Application settings.

Settings are loaded from environment variables (and ``.env`` for local dev).
We use pydantic-settings v2 so that types are validated at startup — config
errors should crash loudly, not silently degrade the agent loop.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed view of the runtime environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Anthropic ---
    ANTHROPIC_API_KEY: str = Field(default="", description="Anthropic API key.")
    RESEARCHER_MODEL: str = "claude-opus-4-7"
    STRUCTURAL_MODEL: str = "claude-opus-4-7"
    LITERATURE_MODEL: str = "claude-sonnet-4-6"
    CLINICAL_MODEL: str = "claude-sonnet-4-6"
    COMMUNICATOR_MODEL: str = "claude-sonnet-4-6"

    # --- Structure prediction provider ---
    # "biolm" (default) — managed Boltz-2 / Chai-1 via biolm.ai
    # "replicate" — legacy fallback (kept for emergencies; not currently used)
    STRUCTURE_PROVIDER: str = "biolm"

    # --- BioLM (https://biolm.ai) ---
    BIOLMAI_TOKEN: str = ""
    BIOLM_BASE_URL: str = "https://biolm.ai/api/v3"
    BIOLM_BOLTZ2_PATH: str = "/boltz2/predict/"
    BIOLM_CHAI1_PATH: str = "/chai1/predict/"
    BIOLM_TIMEOUT_SECONDS: int = 600

    # --- Replicate (legacy fallback) ---
    REPLICATE_API_TOKEN: str = ""
    BOLTZ2_MODEL_ID: str = ""
    CHAI1_MODEL_ID: str = ""

    # --- Database ---
    DATABASE_URL: str = (
        "postgresql+asyncpg://alembic:alembic@localhost:5432/alembic_labs"
    )

    # --- App ---
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    # Default cycle cadence — bumped from 45→60 to bring the lab into the
    # ~$500/mo budget once Chai-1 cross-validation is gated adaptively.
    DISTILLATION_INTERVAL_MINUTES: int = 60
    # Legacy always-on toggle. Kept for emergency overrides (set true to
    # force Chai-1 on every fold regardless of the adaptive gate).
    ENABLE_CHAI1: bool = False
    # Adaptive cross-validation: only run Chai-1 when Boltz-2 pLDDT lands
    # in the borderline band where ensemble disagreement is informative.
    # Above the high gate Boltz-2 is confident enough on its own; below the
    # low gate the structure is already too noisy for cross-val to clarify.
    ENABLE_CHAI1_ADAPTIVE: bool = True
    CHAI1_GATE_PLDDT_LOW: float = 0.5
    CHAI1_GATE_PLDDT_HIGH: float = 0.7
    ENABLE_SCHEDULER: bool = True
    PDB_STORAGE_DIR: Path = Path("./pdb_storage")
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,https://alembic.bio"

    # --- Twitter (placeholder, later) ---
    TWITTER_BEARER_TOKEN: str = ""
    TWITTER_API_KEY: str = ""
    TWITTER_API_SECRET: str = ""
    TWITTER_ACCESS_TOKEN: str = ""
    TWITTER_ACCESS_SECRET: str = ""

    # --- Solana on-chain logging ---
    # Master switch. When ON, every REFINED/DISCARDED fold gets a SHA-256
    # hash of its core data committed to Solana via the SPL Memo program.
    # Disabled by default so a missing keypair never blocks the cycle.
    SOLANA_ONCHAIN_ENABLED: bool = False
    SOLANA_RPC_URL: str = "https://api.mainnet-beta.solana.com"
    # Base58 (Phantom-export style) encoded 64-byte secret key. Generate
    # locally with ``solana-keygen new`` + ``solders.keypair.Keypair`` or
    # via Phantom "Show Private Key" → base58 string.
    SOLANA_KEYPAIR_BASE58: str = ""
    # ``mainnet`` | ``devnet`` — drives the Solscan explorer URL suffix.
    SOLANA_NETWORK: str = "mainnet"
    # Treat any RPC / signing error as a non-fatal event so the cycle still
    # publishes the fold even if Solana is down. Flip to false in tests.
    SOLANA_FAILURE_NON_FATAL: bool = True
    # Legacy var kept for backwards compatibility with older .env files —
    # not currently used (we sign in-process from SOLANA_KEYPAIR_BASE58).
    SOLANA_KEYPAIR_PATH: str = ""

    @field_validator("PDB_STORAGE_DIR", mode="after")
    @classmethod
    def _ensure_pdb_dir(cls, value: Path) -> Path:
        # Ensure the directory exists at boot — folders that don't exist at
        # write time are a common source of mysterious 500s in production.
        value.mkdir(parents=True, exist_ok=True)
        return value

    @property
    def cors_origins(self) -> list[str]:
        """Parsed CORS origins list."""
        return [
            origin.strip()
            for origin in self.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() in {"production", "prod"}

    @property
    def chai1_credentials_available(self) -> bool:
        """Whether the active provider can call Chai-1 at all (creds present)."""
        if self.STRUCTURE_PROVIDER == "biolm":
            return bool(self.BIOLMAI_TOKEN)
        return bool(self.CHAI1_MODEL_ID and self.REPLICATE_API_TOKEN)

    @property
    def chai1_enabled(self) -> bool:
        """Legacy always-on flag. True ⇒ run Chai-1 on every fold (forced)."""
        return self.ENABLE_CHAI1 and self.chai1_credentials_available

    @property
    def chai1_adaptive_enabled(self) -> bool:
        """Adaptive flag — run Chai-1 only inside the borderline pLDDT band."""
        return self.ENABLE_CHAI1_ADAPTIVE and self.chai1_credentials_available

    @property
    def solana_explorer_base(self) -> str:
        """Base Solscan URL for the active network. Drives explorer links."""
        if self.SOLANA_NETWORK.lower() == "devnet":
            return "https://solscan.io/tx/{sig}?cluster=devnet"
        return "https://solscan.io/tx/{sig}"

    @property
    def solana_ready(self) -> bool:
        """True when on-chain logging is enabled AND a keypair is configured."""
        return self.SOLANA_ONCHAIN_ENABLED and bool(self.SOLANA_KEYPAIR_BASE58)

    @property
    def structure_provider_normalised(self) -> str:
        return (self.STRUCTURE_PROVIDER or "biolm").strip().lower()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton accessor — instantiate once per process."""
    return Settings()


settings = get_settings()
