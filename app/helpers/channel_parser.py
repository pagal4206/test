from typing import Optional
from urllib.parse import urlparse

from app.constants import CHANNEL_USERNAME_RE


def _is_valid_channel_username(value: str) -> bool:
    return bool(CHANNEL_USERNAME_RE.fullmatch(value))


def _parse_channel_token(token: str) -> dict[str, Optional[str] | bool]:
    result: dict[str, Optional[str] | bool] = {
        "channel_ref": None,
        "join_link": None,
        "invite_only_link": False,
        "error": None,
    }

    raw = token.strip()
    if not raw:
        result["error"] = "invalid channel value"
        return result

    if raw.lstrip("-").isdigit():
        result["channel_ref"] = raw
        return result

    if raw.startswith("@"):
        username = raw[1:]
        if not _is_valid_channel_username(username):
            result["error"] = "invalid username format"
            return result
        result["channel_ref"] = f"@{username}"
        result["join_link"] = f"https://t.me/{username}"
        return result

    if _is_valid_channel_username(raw):
        result["channel_ref"] = f"@{raw}"
        result["join_link"] = f"https://t.me/{raw}"
        return result

    parsed = urlparse(raw)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    if host not in {"t.me", "telegram.me"}:
        result["error"] = "unsupported format"
        return result

    path = parsed.path.strip("/")
    if not path:
        result["error"] = "empty telegram link"
        return result

    if path.startswith("+"):
        result["join_link"] = raw
        result["invite_only_link"] = True
        return result

    first_part = path.split("/")[0]
    if first_part.lower() == "joinchat":
        result["join_link"] = raw
        result["invite_only_link"] = True
        return result

    username = first_part.lstrip("@")
    if not _is_valid_channel_username(username):
        result["error"] = "invalid telegram link"
        return result

    result["channel_ref"] = f"@{username}"
    result["join_link"] = f"https://t.me/{username}"
    return result


def resolve_fsub_inputs(args: list[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    parsed_tokens = [_parse_channel_token(item) for item in args[:2]]
    for parsed in parsed_tokens:
        if parsed["error"]:
            return None, None, (
                "Invalid value. Use a channel id, @username, or a t.me username link."
            )

    channel_ref = next(
        (str(p["channel_ref"]) for p in parsed_tokens if p["channel_ref"]),
        None,
    )
    join_link = next(
        (str(p["join_link"]) for p in reversed(parsed_tokens) if p["join_link"]),
        None,
    )
    invite_only = any(bool(p["invite_only_link"]) for p in parsed_tokens)

    if not channel_ref and not join_link:
        return None, None, "Usage: /fsub <channel_id/@username/link> [optional_join_link]"

    warning = None
    if invite_only and not channel_ref:
        warning = (
            "Invite link is saved, but membership checks require a channel id or @username."
        )
    return channel_ref, join_link, warning
