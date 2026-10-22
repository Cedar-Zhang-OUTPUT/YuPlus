"""Parse Feishu message times consistently at read and storage boundaries."""
from datetime import datetime, timedelta, timezone
import re

_LOCAL_TIME = re.compile(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?', re.ASCII)


def message_time(value):
    """Return UTC; naive CLI display times use the subprocess's local timezone.

    lark-cli common.FormatTime formats time.Unix(...).Local() without an offset.
    astimezone() on a naive datetime uses local rules at that historical date,
    rather than today's UTC offset. Never attach UTC to a local display time.
    Keep the original provider value in the stored message payload.
    """
    if ((type(value) is int and value >= 0) or
            (isinstance(value, str) and value.isascii() and value.isdigit())):
        return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=int(value))
    if not isinstance(value, str):
        raise ValueError('Invalid message time')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None and not _LOCAL_TIME.fullmatch(value):
        raise ValueError('Unrecognized local message time')
    return parsed.astimezone(timezone.utc)
