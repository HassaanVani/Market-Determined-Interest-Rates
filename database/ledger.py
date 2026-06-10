import sqlite3
import math


class BalanceSheetMismatch(Exception):
    pass


class Ledger:
    def __init__(self, db_path=":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS balance_sheets (
                agent_id TEXT PRIMARY KEY,
                agent_type TEXT,
                assets REAL DEFAULT 0.0,
                liabilities REAL DEFAULT 0.0,
                equity REAL DEFAULT 0.0
            )
        """)
        self.conn.commit()

    def update_balance_sheet(
        self,
        agent_id: str,
        agent_type: str,
        assets: float,
        liabilities: float,
        equity: float,
    ):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO balance_sheets (agent_id, agent_type, assets, liabilities, equity)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                assets=excluded.assets,
                liabilities=excluded.liabilities,
                equity=excluded.equity
        """,
            (
                str(agent_id),
                agent_type,
                float(assets),
                float(liabilities),
                float(equity),
            ),
        )
        self.conn.commit()

    def get_balance_sheet(self, agent_id: str):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM balance_sheets WHERE agent_id = ?", (str(agent_id),)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {
            "agent_id": str(agent_id),
            "assets": 0.0,
            "liabilities": 0.0,
            "equity": 0.0,
        }

    def validate_balance_sheets(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM balance_sheets")
        rows = cursor.fetchall()

        for row in rows:
            assets = float(row["assets"])
            liabilities = float(row["liabilities"])
            equity = float(row["equity"])

            # Use math.isclose to handle floating point inaccuracies
            if not math.isclose(assets, liabilities + equity, abs_tol=1e-5):
                raise BalanceSheetMismatch(
                    f"Agent {row['agent_id']} ({row['agent_type']}) balance sheet mismatch: "
                    f"Assets ({assets}) != Liabilities ({liabilities}) + Equity ({equity})"
                )

        # Also validate global macro constraint if necessary, but checking all agents is sufficient
        # as long as each agent obeys it, the system obeys it.
        return True
