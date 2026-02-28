from __future__ import annotations

from portal_shooter.map.types import Wall


class WallGrid:
    """Spatial hash grid for fast wall lookups by region."""

    __slots__ = ["cell_size", "inv_cell", "grid"]

    def __init__(self, walls: list[Wall], cell_size: int = 64) -> None:
        self.cell_size: int = cell_size
        self.inv_cell: float = 1.0 / cell_size
        self.grid: dict[tuple[int, int], list[tuple[float, float, float, float]]] = {}
        for w in walls:
            x1, y1, x2, y2 = w[0].x, w[0].y, w[1].x, w[1].y
            flat = (x1, y1, x2, y2)
            min_cx = int(min(x1, x2) * self.inv_cell)
            max_cx = int(max(x1, x2) * self.inv_cell)
            min_cy = int(min(y1, y2) * self.inv_cell)
            max_cy = int(max(y1, y2) * self.inv_cell)
            for cx in range(min_cx, max_cx + 1):
                for cy in range(min_cy, max_cy + 1):
                    key = (cx, cy)
                    try:
                        self.grid[key].append(flat)
                    except KeyError:
                        self.grid[key] = [flat]

    def query(self, x: float, y: float, radius: float) -> list[tuple[float, float, float, float]]:
        """Return flat wall tuples in cells overlapping the AABB around (x, y, radius)."""
        min_cx = int((x - radius) * self.inv_cell)
        max_cx = int((x + radius) * self.inv_cell)
        min_cy = int((y - radius) * self.inv_cell)
        max_cy = int((y + radius) * self.inv_cell)
        seen: set[int] = set()
        result: list[tuple[float, float, float, float]] = []
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                bucket = self.grid.get((cx, cy))
                if bucket is None:
                    continue
                for w in bucket:
                    wid = id(w)
                    if wid not in seen:
                        seen.add(wid)
                        result.append(w)
        return result
