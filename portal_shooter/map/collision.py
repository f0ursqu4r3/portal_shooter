from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pyglm import glm

from portal_shooter.map.spatial_grid import WallGrid
from portal_shooter.map.types import Wall
from portal_shooter.util import ray_segment_intersect

if TYPE_CHECKING:
    from portal_shooter.entities.bullet import Bullet
    from portal_shooter.entities.entity import Entity
    from portal_shooter.entities.grenade import Grenade
    from portal_shooter.entities.rocket import Rocket
    from portal_shooter.entities.shell import Shell


# ---------------------------------------------------------------------------
# Inlined raw-float helpers (no glm.vec2 allocations)
# ---------------------------------------------------------------------------

def _segments_intersect(
    ax: float, ay: float, bx: float, by: float,
    cx: float, cy: float, dx: float, dy: float,
) -> bool:
    """Test if segment (a,b) intersects segment (c,d).  All raw floats."""
    # direction(c,d,a) = cross(a-c, d-c)
    d1 = (ax - cx) * (dy - cy) - (ay - cy) * (dx - cx)
    d2 = (bx - cx) * (dy - cy) - (by - cy) * (dx - cx)
    d3 = (cx - ax) * (by - ay) - (cy - ay) * (bx - ax)
    d4 = (dx - ax) * (by - ay) - (dy - ay) * (bx - ax)
    return ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
        (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)
    )


def _point_dist_to_seg_sq(
    px: float, py: float,
    x1: float, y1: float, x2: float, y2: float,
) -> float:
    """Squared distance from point (px,py) to segment (x1,y1)-(x2,y2)."""
    vx = x2 - x1
    vy = y2 - y1
    dot_vv = vx * vx + vy * vy
    if dot_vv < 1e-20:
        dx = px - x1
        dy = py - y1
        return dx * dx + dy * dy
    t = ((px - x1) * vx + (py - y1) * vy) / dot_vv
    if t < 0:
        dx = px - x1
        dy = py - y1
    elif t > 1:
        dx = px - x2
        dy = py - y2
    else:
        cx = x1 + vx * t
        cy = y1 + vy * t
        dx = px - cx
        dy = py - cy
    return dx * dx + dy * dy


# ---------------------------------------------------------------------------
# Public collision functions
# ---------------------------------------------------------------------------

def collide_player(
    player: Entity, old_pos: glm.vec2, wall_grid: WallGrid,
    radius: float = 3.0, push_iters: int = 3,
) -> None:
    """Push entity out of walls using swept + push-out collision.

    All inner math uses raw floats — no glm.vec2 allocations in the hot loop.
    push_iters controls the number of push-out iterations (3 for player, 1 for enemies).
    """
    ppx: float = player.pos.x
    ppy: float = player.pos.y
    opx: float = old_pos.x
    opy: float = old_pos.y

    nearby = wall_grid.query(ppx, ppy, 20.0)

    # First pass: swept collision — snap back if crossed a wall
    for x1, y1, x2, y2 in nearby:
        if _segments_intersect(opx, opy, ppx, ppy, x1, y1, x2, y2):
            ppx = opx
            ppy = opy
            break

    # Second pass: proximity push-out
    radius_sq = radius * radius
    for _ in range(push_iters):
        for x1, y1, x2, y2 in nearby:
            dist_sq = _point_dist_to_seg_sq(ppx, ppy, x1, y1, x2, y2)
            if dist_sq < radius_sq:
                dist = math.sqrt(dist_sq)
                # Wall normal
                ex = x2 - x1
                ey = y2 - y1
                nx = -ey
                ny = ex
                ln = math.sqrt(nx * nx + ny * ny)
                if ln < 1e-10:
                    continue
                inv_ln = 1.0 / ln
                nx *= inv_ln
                ny *= inv_ln
                # Orient normal toward player
                if nx * (ppx - x1) + ny * (ppy - y1) < 0:
                    nx = -nx
                    ny = -ny
                push = radius - dist
                ppx += nx * push
                ppy += ny * push

    player.pos.x = ppx
    player.pos.y = ppy


def collide_entity(
    entity: Bullet | Shell, old_pos: glm.vec2, wall_grid: WallGrid,
) -> tuple[float, float, float, float] | None:
    """Check entity movement against walls.

    Returns the hit wall as (x1, y1, x2, y2) if a collision occurred, None otherwise.
    """
    epx: float = entity.pos.x
    epy: float = entity.pos.y
    opx: float = old_pos.x
    opy: float = old_pos.y

    cx = (opx + epx) * 0.5
    cy = (opy + epy) * 0.5
    dx = epx - opx
    dy = epy - opy
    reach = math.sqrt(dx * dx + dy * dy) * 0.5 + 5.0

    nearby = wall_grid.query(cx, cy, reach)

    for flat in nearby:
        x1, y1, x2, y2 = flat
        if not _segments_intersect(opx, opy, epx, epy, x1, y1, x2, y2):
            continue

        # Wall normal
        ex = x2 - x1
        ey = y2 - y1
        nx = -ey
        ny = ex
        ln = math.sqrt(nx * nx + ny * ny)
        if ln < 1e-10:
            continue
        inv_ln = 1.0 / ln
        nx *= inv_ln
        ny *= inv_ln
        # Orient normal toward incoming velocity
        vx: float = entity.vel.x
        vy: float = entity.vel.y
        if nx * vx + ny * vy > 0:
            nx = -nx
            ny = -ny

        from portal_shooter.entities.bullet import Bullet

        if isinstance(entity, Bullet):
            if entity.piercing:
                entity.piercing = False
                entity.pos.x = opx
                entity.pos.y = opy
                return None

            # Grazing angle → ricochet
            vmag = math.sqrt(vx * vx + vy * vy)
            if vmag > 1e-10:
                incidence = abs((vx * nx + vy * ny) / vmag)
            else:
                incidence = 1.0

            if incidence < 0.5:
                dot_vn = vx * nx + vy * ny
                entity.vel.x = vx - nx * 2 * dot_vn
                entity.vel.y = vy - ny * 2 * dot_vn
                entity.pos.x = opx
                entity.pos.y = opy
            else:
                entity.life = 0
                entity.pos.x = opx
                entity.pos.y = opy
        else:
            entity.vel = glm.vec2()
            entity.speed = 0.0
            entity.pos.x = opx
            entity.pos.y = opy
        return flat
    return None


def collide_grenade(
    grenade: Grenade | Rocket, old_pos: glm.vec2, wall_grid: WallGrid,
) -> bool:
    """Bounce grenade off walls. Returns True if a wall was hit."""
    epx: float = grenade.pos.x
    epy: float = grenade.pos.y
    opx: float = old_pos.x
    opy: float = old_pos.y

    dx = epx - opx
    dy = epy - opy
    cx = (opx + epx) * 0.5
    cy = (opy + epy) * 0.5
    reach = math.sqrt(dx * dx + dy * dy) * 0.5 + 5.0

    nearby = wall_grid.query(cx, cy, reach)

    for x1, y1, x2, y2 in nearby:
        if not _segments_intersect(opx, opy, epx, epy, x1, y1, x2, y2):
            continue

        ex = x2 - x1
        ey = y2 - y1
        nx = -ey
        ny = ex
        ln = math.sqrt(nx * nx + ny * ny)
        if ln < 1e-10:
            continue
        inv_ln = 1.0 / ln
        nx *= inv_ln
        ny *= inv_ln
        vx: float = grenade.vel.x
        vy: float = grenade.vel.y
        if nx * vx + ny * vy > 0:
            nx = -nx
            ny = -ny
        dot_vn = vx * nx + vy * ny
        grenade.vel.x = vx - nx * 2 * dot_vn
        grenade.vel.y = vy - ny * 2 * dot_vn
        grenade.speed *= grenade.bounce
        grenade.pos.x = opx
        grenade.pos.y = opy
        return True
    return False


def find_nearest_wall_hit(
    origin: glm.vec2,
    direction: glm.vec2,
    walls: list[Wall],
    max_range: float = 500,
) -> tuple[glm.vec2, glm.vec2] | None:
    """Cast a ray from origin along direction, returning (hit_point, wall_normal)."""
    if glm.length(direction) < 1e-10:
        return None
    ray_dir = glm.normalize(direction)
    ray_end = origin + ray_dir * max_range

    best_dist_sq = float("inf")
    best_hit: glm.vec2 | None = None
    best_normal: glm.vec2 | None = None

    for wall in walls:
        hit = ray_segment_intersect(origin, ray_end, wall[0], wall[1])
        if hit is None:
            continue
        dist_sq = glm.dot(hit - origin, hit - origin)
        if dist_sq < best_dist_sq:
            best_dist_sq = dist_sq
            best_hit = hit
            edge = wall[1] - wall[0]
            n = glm.vec2(-edge.y, edge.x)
            if glm.length(n) < 1e-10:
                continue
            n = glm.normalize(n)
            if glm.dot(n, origin - hit) < 0:
                n = -n
            best_normal = n

    if best_hit is not None and best_normal is not None:
        return (best_hit, best_normal)
    return None


def get_wall_vertices(walls: list[Wall]) -> list[glm.vec2]:
    """Get unique vertices from all walls for visibility raycasting."""
    seen: set[tuple[float, float]] = set()
    verts: list[glm.vec2] = []
    for w in walls:
        for p in w:
            key = (round(p.x, 1), round(p.y, 1))
            if key not in seen:
                seen.add(key)
                verts.append(p)
    return verts
