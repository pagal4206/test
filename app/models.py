from dataclasses import dataclass
from typing import Optional


@dataclass
class ForceSubConfig:
    enabled: bool = False
    channel_ref: Optional[str] = None
    join_link: Optional[str] = None


@dataclass
class BroadcastSummary:
    total_targets: int
    sent_users: int
    failed_users: int
    sent_groups: int
    failed_groups: int


@dataclass
class BroadcastPayload:
    kind: str
    text: Optional[str] = None
    source_chat_id: Optional[int] = None
    source_message_id: Optional[int] = None
