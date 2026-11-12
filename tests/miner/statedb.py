"""A real Hermes session store built through hermes_state.SessionDB, for the miner tests."""
import json
import sqlite3
from pathlib import Path
from hermes_state import SessionDB   # imported at collection time, before other tests stub hermes_cli modules


class Store:
    def __init__(self, path):
        self.path = str(path); self.db = SessionDB(db_path=Path(path))

    def session(self, sid, started_at):
        self.db.create_session(sid, 'cli')
        con = sqlite3.connect(self.path)   # test fixture only: back-date the session
        con.execute('UPDATE sessions SET started_at = ? WHERE id = ?', (started_at, sid)); con.commit(); con.close()

    def msg(self, sid, role, content=None, tool_calls=None, tool_name=None, call_id=None):
        if isinstance(tool_calls, str): tool_calls = json.loads(tool_calls)
        self.db.append_message(sid, role, content=content, tool_name=tool_name, tool_calls=tool_calls, tool_call_id=call_id)

    def close(self): self.db.close()
