from __future__ import annotations

import math

from portal_shooter.map.spatial_grid import WallGrid


def _count_wall_hits(
    ox: float,
    oy: float,
    tx: float,
    ty: float,
    walls: list[tuple[float, float, float, float]],
) -> int:
    """Count ray-segment intersections between origin and target."""
    rdx = tx - ox
    rdy = ty - oy
    count = 0
    for sx1, sy1, sx2, sy2 in walls:
        ssx = sx2 - sx1
        ssy = sy2 - sy1
        denom = rdx * ssy - rdy * ssx
        if -1e-10 < denom < 1e-10:
            continue
        qpx = sx1 - ox
        qpy = sy1 - oy
        t = (qpx * ssy - qpy * ssx) / denom
        if t < 0.0 or t > 1.0:
            continue
        u = (qpx * rdy - qpy * rdx) / denom
        if 0.0 <= u <= 1.0:
            count += 1
    return count


def _attenuation(dist: float, max_range: float) -> float:
    """Quadratic distance rolloff."""
    if dist >= max_range:
        return 0.0
    t = 1.0 - dist / max_range
    return t * t


def _occlusion(wall_count: int) -> float:
    """Exponential decay per wall: 0.4^wall_count, floored at 0.05."""
    if wall_count == 0:
        return 1.0
    return max(0.05, 0.4**wall_count)


def _compute_pan(
    arrival_dx: float,
    arrival_dy: float,
    facing_x: float,
    facing_y: float,
) -> float:
    """Dot product of normalized arrival direction with player's right vector."""
    mag = math.sqrt(arrival_dx * arrival_dx + arrival_dy * arrival_dy)
    if mag < 1e-10:
        return 0.0
    ndx = arrival_dx / mag
    ndy = arrival_dy / mag
    # Right vector: (-facing_y, facing_x) for screen coords where +Y is down
    return ndx * (-facing_y) + ndy * facing_x


def compute_sound(
    listener_x: float,
    listener_y: float,
    facing_x: float,
    facing_y: float,
    source_x: float,
    source_y: float,
    wall_grid: WallGrid,
    max_range: float = 400.0,
) -> tuple[float, float]:
    """Compute (volume, pan) for a sound source using raytraced propagation."""
    # Query walls around the midpoint between listener and source
    mid_x = (listener_x + source_x) * 0.5
    mid_y = (listener_y + source_y) * 0.5
    dx = source_x - listener_x
    dy = source_y - listener_y
    direct_dist = math.sqrt(dx * dx + dy * dy)
    query_radius = direct_dist * 0.5 + 32.0
    walls = wall_grid.query(mid_x, mid_y, query_radius)

    # Direct path
    direct_hits = _count_wall_hits(listener_x, listener_y, source_x, source_y, walls)
    direct_vol = _attenuation(direct_dist, max_range) * _occlusion(direct_hits)
    direct_pan = _compute_pan(dx, dy, facing_x, facing_y)

    return (direct_vol, direct_pan)
