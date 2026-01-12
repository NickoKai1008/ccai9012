"""ccai9012.token_utils

Centralized secret/token loading for the toolkit.

Contract
- Looks for tokens in `ccai9012/token.yaml` (configurable via env var `CCAI9012_TOKEN_YAML`).
- If missing/invalid, falls back to environment variables.
- If still missing, optionally prompts the user via `getpass.getpass`.
- On success, sets the corresponding environment variable for the current session.

Notes
- This module is intentionally lightweight and avoids network calls.
- It never validates whether a token works remotely; "invalid" here means empty/placeholder.
"""

from __future__ import annotations

import os
import getpass
from pathlib import Path
from typing import Any, Optional


_DEFAULT_TOKEN_YAML_REL = Path(__file__).with_name("token.yaml")


def _is_invalid_secret(value: Optional[str]) -> bool:
    if value is None:
        return True
    v = value.strip()
    if not v:
        return True
    # common placeholder values
    placeholders = {
        "changeme",
        "change_me",
        "your_key_here",
        "your_token_here",
        "your_api_key_here",
        "xxx",
        "<token>",
        "<api_key>",
        "<key>",
    }
    return v.lower() in placeholders


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}

    try:
        import yaml  # type: ignore
    except Exception as e:  # pragma: no cover
        raise ImportError(
            "PyYAML is required to load token.yaml. Install with `pip install pyyaml`."
        ) from e

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Token YAML must be a mapping/dict. Got: {type(data).__name__}")
    return data


def _get_by_dotted_path(data: dict[str, Any], dotted: str) -> Optional[str]:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur if isinstance(cur, str) else None


def get_token(
    *,
    env_var: str,
    yaml_key: Optional[str] = None,
    prompt: Optional[str] = None,
    allow_prompt: bool = True,
    token_yaml_path: Optional[str | os.PathLike[str]] = None,
) -> str:
    """Resolve a secret token with precedence: YAML -> env -> prompt.

    Args:
        env_var: Environment variable name to read/set.
        yaml_key: Dotted key inside token.yaml. If None, defaults to `env.<env_var>`.
        prompt: Prompt text for manual entry. Defaults to "Enter your {env_var}: ".
        allow_prompt: If False, never prompts and raises ValueError if token is missing.
        token_yaml_path: Optional override path. If None, uses env var
            `CCAI9012_TOKEN_YAML` then defaults to `ccai9012/token.yaml`.

    Returns:
        Token string.

    Raises:
        ValueError: if token cannot be resolved and prompting is disabled.
    """

    yaml_key = yaml_key or f"env.{env_var}"
    prompt = prompt or f"Enter your {env_var}: "

    # 1) YAML
    path = Path(
        token_yaml_path
        or os.getenv("CCAI9012_TOKEN_YAML")
        or str(_DEFAULT_TOKEN_YAML_REL)
    )
    token: Optional[str] = None
    try:
        data = _load_yaml(path)
        token = _get_by_dotted_path(data, yaml_key)
    except FileNotFoundError:
        token = None

    if not _is_invalid_secret(token):
        os.environ[env_var] = token.strip()  # keep session compatibility
        return token.strip()

    # 2) Env var
    token = os.getenv(env_var)
    if not _is_invalid_secret(token):
        os.environ[env_var] = token.strip()
        return token.strip()

    # 3) Prompt
    if allow_prompt:
        token = getpass.getpass(prompt)
        if _is_invalid_secret(token):
            raise ValueError(f"A valid value for {env_var} was not provided.")
        os.environ[env_var] = token.strip()
        return token.strip()

    raise ValueError(
        f"Missing {env_var}. Set it in environment or in token.yaml key '{yaml_key}'."
    )

