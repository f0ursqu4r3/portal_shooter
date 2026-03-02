from __future__ import annotations

import math
from typing import NamedTuple

from portal_shooter.map.spatial_grid import WallGrid


class PortalData(NamedTuple):
    pos_x: float
    pos_y: float
    normal_x: float
    normal_y: float
    exit_x: float
    exit_y: float
    line_ax: float
    line_ay: float
    line_bx: float
    line_by: float


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
    portals: tuple[PortalData, PortalData] | None,
    max_range: float = 400.0,
) -> tuple[float, float]:
    """Compute (volume, pan) for a sound source using raytraced propagation.

    Tries direct path and portal paths, returns the best result.
    """
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

    best_vol = direct_vol
    best_pan = direct_pan

    # Short-circuit: clear line of sight and close — skip portal evaluation
    if direct_hits == 0 and direct_dist < max_range * 0.5:
        return (best_vol, best_pan)

    # Portal paths (try both orderings: A→B and B→A)
    if portals is not None:
        for entry, exit_ in (portals, (portals[1], portals[0])):
            # Check source is on front side of entry portal
            to_source_x = source_x - entry.pos_x
            to_source_y = source_y - entry.pos_y
            if to_source_x * entry.normal_x + to_source_y * entry.normal_y <= 0:
                continue

            # Leg 1: source → entry exit point
            leg1_dx = entry.exit_x - source_x
            leg1_dy = entry.exit_y - source_y
            leg1_dist = math.sqrt(leg1_dx * leg1_dx + leg1_dy * leg1_dy)

            leg1_mid_x = (source_x + entry.exit_x) * 0.5
            leg1_mid_y = (source_y + entry.exit_y) * 0.5
            leg1_walls = wall_grid.query(
                leg1_mid_x, leg1_mid_y, leg1_dist * 0.5 + 32.0
            )
            leg1_hits = _count_wall_hits(
                source_x, source_y, entry.exit_x, entry.exit_y, leg1_walls
            )

            # Leg 2: exit portal exit point → listener
            leg2_dx = listener_x - exit_.exit_x
            leg2_dy = listener_y - exit_.exit_y
            leg2_dist = math.sqrt(leg2_dx * leg2_dx + leg2_dy * leg2_dy)

            leg2_mid_x = (exit_.exit_x + listener_x) * 0.5
            leg2_mid_y = (exit_.exit_y + listener_y) * 0.5
            leg2_walls = wall_grid.query(
                leg2_mid_x, leg2_mid_y, leg2_dist * 0.5 + 32.0
            )
            leg2_hits = _count_wall_hits(
                exit_.exit_x, exit_.exit_y, listener_x, listener_y, leg2_walls
            )

            total_dist = leg1_dist + leg2_dist
            total_hits = leg1_hits + leg2_hits
            portal_vol = _attenuation(total_dist, max_range) * _occlusion(total_hits)

            if portal_vol > best_vol:
                # Arrival direction is from exit portal toward listener
                arrival_dx = exit_.exit_x - listener_x
                arrival_dy = exit_.exit_y - listener_y
                best_vol = portal_vol
                best_pan = _compute_pan(arrival_dx, arrival_dy, facing_x, facing_y)

    return (best_vol, best_pan)
