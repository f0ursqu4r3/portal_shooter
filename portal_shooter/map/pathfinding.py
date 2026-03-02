from __future__ import annotations

import math
from collections import deque

from pyglm import glm

from portal_shooter.map.spatial_grid import WallGrid
from portal_shooter.map.types import Room
from portal_shooter.util import intersect


class RoomGraph:
    """Room-level navigation graph for enemy pathfinding.

    Uses room AABB overlap + corridor connectivity for adjacency,
    and BFS for inter-room pathfinding.
    """

    __slots__ = ["adjacency", "rooms"]

    def __init__(self, rooms: list[Room], corridors: list[list[glm.vec2]]) -> None:
        self.rooms: list[Room] = rooms
        n = len(rooms)
        self.adjacency: list[list[int]] = [[] for _ in range(n)]

        # Build adjacency: two rooms are neighbours if a corridor midpoint
        # is close to both room centers (same heuristic used in generation).
        for corr in corridors:
            if len(corr) < 3:
                continue
            mid = (corr[0] + corr[2]) * 0.5
            dists = [(glm.distance(mid, r.center), idx) for idx, r in enumerate(rooms)]
            dists.sort()
            if len(dists) >= 2:
                a, b = dists[0][1], dists[1][1]
                if b not in self.adjacency[a]:
                    self.adjacency[a].append(b)
                if a not in self.adjacency[b]:
                    self.adjacency[b].append(a)

    def find_room(self, pos: glm.vec2) -> int | None:
        """Find which room contains pos (point-in-AABB test)."""
        best_idx: int | None = None
        best_dist = float("inf")
        for i, room in enumerate(self.rooms):
            b = room.bounds
            if b.left <= pos.x <= b.right and b.top <= pos.y <= b.bottom:
                return i
            # Fallback: closest room center
            d = glm.distance(pos, room.center)
            if d < best_dist:
                best_dist = d
                best_idx = i
        return best_idx

    def find_path(self, from_room: int, to_room: int) -> list[int]:
        """BFS shortest path between rooms. Returns list of room indices."""
        if from_room == to_room:
            return [from_room]
        visited: set[int] = {from_room}
        parent: dict[int, int] = {}
        queue: deque[int] = deque([from_room])
        while queue:
            cur = queue.popleft()
            for nb in self.adjacency[cur]:
                if nb in visited:
                    continue
                visited.add(nb)
                parent[nb] = cur
                if nb == to_room:
                    # Reconstruct
                    path: list[int] = []
                    node = to_room
                    while node != from_room:
                        path.append(node)
                        node = parent[node]
                    path.append(from_room)
                    path.reverse()
                    return path
                queue.append(nb)
        return [from_room]


def has_line_of_sight(a: glm.vec2, b: glm.vec2, wall_grid: WallGrid) -> bool:
    """Check if there is a clear line between a and b (no wall intersections)."""
    cx = (a.x + b.x) * 0.5
    cy = (a.y + b.y) * 0.5
    reach = glm.distance(a, b) * 0.5 + 5.0
    nearby = wall_grid.query(cx, cy, reach)
    for x1, y1, x2, y2 in nearby:
        if intersect(a, b, glm.vec2(x1, y1), glm.vec2(x2, y2)):
            return False
    return True


def steer_toward(
    pos: glm.vec2, target: glm.vec2, speed: float, wall_grid: WallGrid
) -> glm.vec2:
    """Compute velocity toward target with simple wall avoidance feeler rays."""
    diff = target - pos
    dist = glm.length(diff)
    if dist < 1.0:
        return glm.vec2()

    desired = glm.normalize(diff) * speed

    # Cast 3 feeler rays to avoid walls
    feeler_len = 15.0
    angles = [0.0, math.radians(30), math.radians(-30)]
    avoidance = glm.vec2()
    d_norm = glm.normalize(diff)

    for angle in angles:
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        feeler_dir = glm.vec2(
            d_norm.x * cos_a - d_norm.y * sin_a,
            d_norm.x * sin_a + d_norm.y * cos_a,
        )
        feeler_end = pos + feeler_dir * feeler_len
        nearby = wall_grid.query(pos.x, pos.y, feeler_len)
        for x1, y1, x2, y2 in nearby:
            if intersect(pos, feeler_end, glm.vec2(x1, y1), glm.vec2(x2, y2)):
                # Push away from this wall direction
                avoidance -= feeler_dir * speed * 0.5
                break

    result = desired + avoidance
    length = glm.length(result)
    if length > speed:
        result = glm.normalize(result) * speed
    return result
