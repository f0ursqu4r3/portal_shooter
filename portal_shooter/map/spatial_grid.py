from __future__ import annotations

from portal_shooter.map.types import Wall


class WallGrid:
    """Spatial hash grid for fast wall lookups by region.

    Uses index-based generation-counter dedup instead of id() + set
    for faster query performance.
    """

    __slots__ = ["cell_size", "inv_cell", "grid", "_walls", "_last_gen", "_gen"]

    def __init__(self, walls: list[Wall], cell_size: int = 64) -> None:
        self.cell_size: int = cell_size
        self.inv_cell: float = 1.0 / cell_size
        self.grid: dict[tuple[int, int], list[int]] = {}
        # Store flat tuples indexed by int for fast dedup
        self._walls: list[tuple[float, float, float, float]] = []
        self._last_gen: list[int] = []
        self._gen: int = 0

        for i, w in enumerate(walls):
            x1, y1, x2, y2 = w[0].x, w[0].y, w[1].x, w[1].y
            flat = (x1, y1, x2, y2)
            self._walls.append(flat)
            self._last_gen.append(0)

            min_cx = int(min(x1, x2) * self.inv_cell)
            max_cx = int(max(x1, x2) * self.inv_cell)
            min_cy = int(min(y1, y2) * self.inv_cell)
            max_cy = int(max(y1, y2) * self.inv_cell)
            for cx in range(min_cx, max_cx + 1):
                for cy in range(min_cy, max_cy + 1):
                    key = (cx, cy)
                    try:
                        self.grid[key].append(i)
                    except KeyError:
                        self.grid[key] = [i]

    def query(self, x: float, y: float, radius: float) -> list[tuple[float, float, float, float]]:
        """Return flat wall tuples in cells overlapping the AABB around (x, y, radius)."""
        self._gen += 1
        gen = self._gen
        inv = self.inv_cell
        min_cx = int((x - radius) * inv)
        max_cx = int((x + radius) * inv)
        min_cy = int((y - radius) * inv)
        max_cy = int((y + radius) * inv)
        walls = self._walls
        last_gen = self._last_gen
        grid = self.grid
        result: list[tuple[float, float, float, float]] = []
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                bucket = grid.get((cx, cy))
                if bucket is None:
                    continue
                for wi in bucket:
                    if last_gen[wi] != gen:
                        last_gen[wi] = gen
                        result.append(walls[wi])
        return result
