import re


GROUP_TYPES = {"group", "supergroup"}
JOINED_STATUSES = {"member", "administrator", "creator", "restricted"}
GROUP_ADMIN_STATUSES = {"administrator", "creator"}
CHANNEL_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")

