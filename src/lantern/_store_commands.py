from __future__ import annotations

from ._store_record_commands import RecordCommandsMixin
from ._store_source_commands import SourceCommandsMixin
from ._store_status_queries import StatusQueriesMixin
from ._store_trace_queries import TraceQueriesMixin


class CommandsMixin(
    SourceCommandsMixin, RecordCommandsMixin, StatusQueriesMixin, TraceQueriesMixin
):
    pass
