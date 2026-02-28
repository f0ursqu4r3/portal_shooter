from __future__ import annotations

from typing import TYPE_CHECKING

from pyglm import glm

from portal_shooter.map.spatial_grid import WallGrid
from portal_shooter.map.types import Wall
from portal_shooter.util import intersect, point_dist_to_line, ray_segment_intersect

if TYPE_CHECKING:
    from portal_shooter.entities.bullet import Bullet
    from portal_shooter.entities.player import Player
    from portal_shooter.entities.shell import Shell


def get_nearby_walls(wall_grid: WallGrid, x: float, y: float, radius: float) -> list[Wall]:
    """Return Wall tuples near a point using the spatial grid."""
    flat = wall_grid.query(x, y, radius)
    return [(glm.vec2(x1, y1), glm.vec2(x2, y2)) for x1, y1, x2, y2 in flat]


def collide_player(player: Player, old_pos: glm.vec2, wall_grid: WallGrid) -> None:
    """Push player out of walls using swept + push-out collision."""
    radius = 3.0
    nearby = get_nearby_walls(wall_grid, player.pos.x, player.pos.y, 20.0)
    # First pass: swept collision — snap back if player crossed a wall
    for wall in nearby:
        if intersect(old_pos, player.pos, wall[0], wall[1]):
            player.pos = glm.vec2(old_pos)
            break
    # Second pass: proximity push-out for wall sliding
    for _ in range(3):
        for wall in nearby:
            dist = point_dist_to_line(player.pos, wall)
            if dist < radius:
                p1, p2 = wall
                edge = p2 - p1
                n = glm.vec2(-edge.y, edge.x)
                if glm.length(n) < 1e-10:
                    continue
                n = glm.normalize(n)
                if glm.dot(n, player.pos - p1) < 0:
                    n = -n
                player.pos += n * (radius - dist)


def collide_entity(entity: Bullet | Shell, old_pos: glm.vec2, wall_grid: WallGrid) -> bool:
    """Check entity movement against walls. Returns True if a wall was hit."""
    cx = (old_pos.x + entity.pos.x) * 0.5
    cy = (old_pos.y + entity.pos.y) * 0.5
    reach = glm.distance(old_pos, entity.pos) * 0.5 + 5.0
    nearby = get_nearby_walls(wall_grid, cx, cy, reach)
    for wall in nearby:
        if intersect(old_pos, entity.pos, wall[0], wall[1]):
            # Compute wall normal
            edge = wall[1] - wall[0]
            n = glm.vec2(-edge.y, edge.x)
            if glm.length(n) < 1e-10:
                continue
            n = glm.normalize(n)
            if glm.dot(n, entity.vel) > 0:
                n = -n

            from portal_shooter.entities.bullet import Bullet

            if isinstance(entity, Bullet):
                # Piercing bullets pass through the first wall hit
                if entity.piercing:
                    entity.piercing = False
                    entity.pos = glm.vec2(old_pos)
                    return False

                # Only ricochet at grazing angles (< ~30° from wall surface)
                incidence = abs(glm.dot(glm.normalize(entity.vel), n))
                if incidence < 0.5:
                    entity.vel = entity.vel - n * 2 * glm.dot(entity.vel, n)
                    entity.pos = glm.vec2(old_pos)
                else:
                    entity.life = 0
                    entity.pos = glm.vec2(old_pos)
            else:
                # Shell: stop
                entity.vel = glm.vec2()
                entity.speed = 0.0
                entity.pos = glm.vec2(old_pos)
            return True
    return False


def find_nearest_wall_hit(
    origin: glm.vec2,
    direction: glm.vec2,
    walls: list[Wall],
    max_range: float = 500,
) -> tuple[glm.vec2, glm.vec2] | None:
    """Cast a ray from origin along direction, returning (hit_point, wall_normal).

    The wall normal is oriented toward the origin side.
    Returns None if no wall is hit within max_range.
    """
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
            # Compute wall normal oriented toward origin
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
