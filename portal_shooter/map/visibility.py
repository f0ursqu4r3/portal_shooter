from __future__ import annotations

import math

from pyglm import glm

from portal_shooter.map.spatial_grid import WallGrid


def compute_visibility(
    origin: glm.vec2,
    wall_grid: WallGrid,
    max_dist: float = 200,
) -> list[tuple[float, float]]:
    """Compute a visibility polygon from origin by raycasting to wall vertices.

    Returns screen-ready (float, float) tuples for direct use in pygame.draw.polygon.
    Uses raw floats throughout to avoid glm.vec2 overhead in the hot loop.
    """
    ox, oy = origin.x, origin.y
    radius = max_dist * 1.05
    range_sq = radius * radius

    # Use spatial grid to get only nearby walls
    nearby = wall_grid.query(ox, oy, radius)

    angle_set: set[float] = set()
    for x1, y1, x2, y2 in nearby:
        for px, py in ((x1, y1), (x2, y2)):
            dx, dy = px - ox, py - oy
            if dx * dx + dy * dy <= range_sq:
                angle_set.add(math.atan2(dy, dx))

    # Build sorted angle list with ±epsilon for edge cases
    angles: list[float] = []
    for a in angle_set:
        angles.append(a - 0.001)
        angles.append(a)
        angles.append(a + 0.001)
    angles.sort()

    # Cast rays — all math in raw floats, no glm.vec2 in inner loop
    points: list[tuple[float, float]] = []
    cos = math.cos
    sin = math.sin
    for angle in angles:
        rdx = cos(angle) * max_dist
        rdy = sin(angle) * max_dist

        closest_t = 1.0
        for sx1, sy1, sx2, sy2 in nearby:
            # Inlined ray-segment intersection
            ssx = sx2 - sx1
            ssy = sy2 - sy1
            denom = rdx * ssy - rdy * ssx
            if -1e-10 < denom < 1e-10:
                continue
            qpx = sx1 - ox
            qpy = sy1 - oy
            t = (qpx * ssy - qpy * ssx) / denom
            if t < 0 or t >= closest_t:
                continue
            u = (qpx * rdy - qpy * rdx) / denom
            if 0 <= u <= 1:
                closest_t = t

        points.append((ox + rdx * closest_t, oy + rdy * closest_t))

    return points
