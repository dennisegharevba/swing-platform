import sys
sys.path.insert(0, "/mount/src/swing-platform")


import sqlite3
from datetime import date

from src.core.config import DATA_DIR

DB_PATH = DATA_DIR / "signal_tracker.db"


def _get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS signal_history (
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            first_seen_date TEXT NOT NULL,
            last_seen_date TEXT NOT NULL,
            PRIMARY KEY (symbol, direction)
        )
        """
    )
    return conn


def sync_signal_history(signals):
    """
    For each active signal, look up (or create) its first-seen date in the
    local tracker DB, and stamp `signal.first_seen_date` accordingly.

    Signals that are no longer active get dropped from the tracker, so if
    the same symbol/direction reappears later after disappearing, it's
    treated as a brand new signal rather than continuing an old countdown.

    This uses the stdlib sqlite3 module, which is blocking. Callers in async
    code should run it via asyncio.to_thread() -- the same pattern already
    used for the blocking yfinance call in market_data.py.
    """
    today = date.today().isoformat()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        current_keys = {(s.symbol, s.direction.value) for s in signals}

        for sig in signals:
            cur.execute(
                "SELECT first_seen_date FROM signal_history WHERE symbol = ? AND direction = ?",
                (sig.symbol, sig.direction.value),
            )
            row = cur.fetchone()
            if row:
                first_seen = row[0]
                cur.execute(
                    "UPDATE signal_history SET last_seen_date = ? WHERE symbol = ? AND direction = ?",
                    (today, sig.symbol, sig.direction.value),
                )
            else:
                first_seen = today
                cur.execute(
                    "INSERT INTO signal_history (symbol, direction, first_seen_date, last_seen_date) "
                    "VALUES (?, ?, ?, ?)",
                    (sig.symbol, sig.direction.value, today, today),
                )
            sig.first_seen_date = date.fromisoformat(first_seen)

        cur.execute("SELECT symbol, direction FROM signal_history")
        stale = [(sym, dirn) for sym, dirn in cur.fetchall() if (sym, dirn) not in current_keys]
        for sym, dirn in stale:
            cur.execute(
                "DELETE FROM signal_history WHERE symbol = ? AND direction = ?",
                (sym, dirn),
            )

        conn.commit()
    finally:
        conn.close()

    return signals
commit directly to main
