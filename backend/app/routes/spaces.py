from flask import Blueprint, request

from ..database import get_connection, rows_to_dicts

spaces_bp = Blueprint("spaces", __name__)


@spaces_bp.get("/", strict_slashes=False)
def list_spaces():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM spaces ORDER BY area, code").fetchall()
        stats = conn.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM spaces
            GROUP BY status
            """
        ).fetchall()
    return {"items": rows_to_dicts(rows), "stats": {row["status"]: row["count"] for row in stats}}


@spaces_bp.patch("/<int:space_id>")
def update_space(space_id):
    data = request.get_json() or {}
    status = data.get("status")
    plate_number = data.get("plate_number")
    allowed = {"free", "occupied", "reserved", "maintenance", "abnormal"}

    if status not in allowed:
        return {"message": "车位状态不合法"}, 400

    with get_connection() as conn:
        current = conn.execute("SELECT * FROM spaces WHERE id = ?", (space_id,)).fetchone()
        if not current:
            return {"message": "车位不存在"}, 404

        if current["status"] == "abnormal" and status != "abnormal":
            conn.execute(
                """
                UPDATE anomalies
                SET status = 'dismissed',
                    result = '手动修改车位状态，自动关闭待处理异常',
                    resolved_at = datetime('now', 'localtime')
                WHERE space_code = ? AND status = 'pending'
                """,
                (current["code"],),
            )

        conn.execute(
            """
            UPDATE spaces
            SET status = ?, plate_number = ?, updated_at = datetime('now', 'localtime')
            WHERE id = ?
            """,
            (status, plate_number if status in ("occupied", "abnormal") else None, space_id),
        )
        row = conn.execute("SELECT * FROM spaces WHERE id = ?", (space_id,)).fetchone()

    return dict(row)
