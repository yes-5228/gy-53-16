from flask import Blueprint, request

from ..database import get_connection, rows_to_dicts

anomalies_bp = Blueprint("anomalies", __name__)


@anomalies_bp.get("/", strict_slashes=False)
def list_anomalies():
    status_filter = request.args.get("status")
    with get_connection() as conn:
        if status_filter:
            rows = conn.execute(
                "SELECT * FROM anomalies WHERE status = ? ORDER BY created_at DESC",
                (status_filter,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM anomalies ORDER BY created_at DESC").fetchall()
        pending_count = conn.execute(
            "SELECT COUNT(*) AS count FROM anomalies WHERE status = 'pending'"
        ).fetchone()["count"]
    return {"items": rows_to_dicts(rows), "pending_count": pending_count}


@anomalies_bp.post("/", strict_slashes=False)
def create_anomaly():
    data = request.get_json() or {}
    space_code = data.get("space_code")
    plate_number = data.get("plate_number")
    description = data.get("description")

    if not space_code or not description:
        return {"message": "车位编号和说明为必填项"}, 400

    with get_connection() as conn:
        space = conn.execute(
            "SELECT * FROM spaces WHERE code = ?", (space_code,)
        ).fetchone()
        if not space:
            return {"message": "车位不存在"}, 404

        previous_status = space["status"] if space["status"] != "abnormal" else None
        cursor = conn.execute(
            """
            INSERT INTO anomalies (space_code, plate_number, description, status, previous_status, created_at)
            VALUES (?, ?, ?, 'pending', ?, datetime('now', 'localtime'))
            """,
            (space_code, plate_number or None, description, previous_status),
        )

        conn.execute(
            """
            UPDATE spaces
            SET status = 'abnormal', plate_number = ?, updated_at = datetime('now', 'localtime')
            WHERE code = ?
            """,
            (plate_number or space["plate_number"], space_code),
        )

        row = conn.execute("SELECT * FROM anomalies WHERE id = ?", (cursor.lastrowid,)).fetchone()

    return dict(row), 201


@anomalies_bp.patch("/<int:anomaly_id>")
def resolve_anomaly(anomaly_id):
    data = request.get_json() or {}
    result = data.get("result")
    status = data.get("status", "resolved")

    if status not in ("resolved", "dismissed"):
        return {"message": "处理状态不合法"}, 400

    with get_connection() as conn:
        anomaly = conn.execute("SELECT * FROM anomalies WHERE id = ?", (anomaly_id,)).fetchone()
        if not anomaly:
            return {"message": "异常记录不存在"}, 404

        conn.execute(
            """
            UPDATE anomalies
            SET status = ?, result = ?, resolved_at = datetime('now', 'localtime')
            WHERE id = ?
            """,
            (status, result, anomaly_id),
        )

        remaining_pending = conn.execute(
            "SELECT COUNT(*) AS count FROM anomalies WHERE space_code = ? AND status = 'pending'",
            (anomaly["space_code"],),
        ).fetchone()["count"]

        if remaining_pending == 0:
            earliest = conn.execute(
                """
                SELECT previous_status FROM anomalies
                WHERE space_code = ? ORDER BY created_at ASC LIMIT 1
                """,
                (anomaly["space_code"],),
            ).fetchone()
            restore_status = (earliest and earliest["previous_status"]) or "free"
            conn.execute(
                """
                UPDATE spaces
                SET status = ?, updated_at = datetime('now', 'localtime')
                WHERE code = ? AND status = 'abnormal'
                """,
                (restore_status, anomaly["space_code"]),
            )

        row = conn.execute("SELECT * FROM anomalies WHERE id = ?", (anomaly_id,)).fetchone()

    return dict(row)
