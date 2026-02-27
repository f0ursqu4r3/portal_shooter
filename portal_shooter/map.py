from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import pygame
from pyglm import glm

from portal_shooter.util import intersect, point_dist_to_line, ray_segment_intersect

if TYPE_CHECKING:
    from portal_shooter.entities.bullet import Bullet
    from portal_shooter.entities.player import Player
    from portal_shooter.entities.shell import Shell

Wall = tuple[glm.vec2, glm.vec2]

VOID_COLOR = (10, 8, 12)
FLOOR_COLOR = (40, 35, 42)
WALL_COLOR = (100, 90, 100)


def compute_visibility(
    origin: glm.vec2,
    walls: list[Wall],
    max_dist: float = 200,
) -> list[glm.vec2]:
    """Compute a visibility polygon from origin by raycasting to wall vertices."""
    # Collect unique angles to all wall vertices within range
    angles: list[float] = []
    for wall in walls:
        for pt in wall:
            d = pt - origin
            if glm.length(d) > max_dist * 1.5:
                continue
            angle = math.atan2(d.y, d.x)
            angles.append(angle)

    # Also add rays at small offsets for edge cases
    base_angles = list(angles)
    for a in base_angles:
        angles.append(a - 0.001)
        angles.append(a + 0.001)

    angles.sort()

    points: list[glm.vec2] = []
    for angle in angles:
        ray_dir = glm.vec2(math.cos(angle), math.sin(angle))
        ray_end = origin + ray_dir * max_dist

        closest: glm.vec2 | None = None
        closest_dist = max_dist

        for wall in walls:
            hit = ray_segment_intersect(origin, ray_end, wall[0], wall[1])
            if hit is not None:
                d = glm.distance(origin, hit)
                if d < closest_dist:
                    closest_dist = d
                    closest = hit

        if closest is not None:
            points.append(closest)
        else:
            points.append(ray_end)

    return points


class Room:
    __slots__ = ["vertices", "walls", "center", "bounds"]

    def __init__(self, vertices: list[glm.vec2]) -> None:
        self.vertices: list[glm.vec2] = vertices
        self.walls: list[Wall] = []
        for i in range(len(vertices)):
            self.walls.append((vertices[i], vertices[(i + 1) % len(vertices)]))
        xs = [v.x for v in vertices]
        ys = [v.y for v in vertices]
        self.bounds: pygame.Rect = pygame.Rect(
            min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
        )
        self.center: glm.vec2 = glm.vec2(
            self.bounds.centerx, self.bounds.centery
        )


class BSPNode:
    __slots__ = ["rect", "left", "right", "room"]

    def __init__(self, rect: pygame.Rect) -> None:
        self.rect: pygame.Rect = rect
        self.left: BSPNode | None = None
        self.right: BSPNode | None = None
        self.room: Room | None = None


class GameMap:
    __slots__ = [
        "width",
        "height",
        "rooms",
        "corridors",
        "walls",
        "bounds",
        "spawn_pos",
        "_floor_surface",
    ]

    def __init__(self, width: int = 600, height: int = 600) -> None:
        self.width: int = width
        self.height: int = height
        self.rooms: list[Room] = []
        self.corridors: list[list[glm.vec2]] = []
        self.walls: list[Wall] = []
        self.bounds: glm.vec2 = glm.vec2(width, height)
        self.spawn_pos: glm.vec2 = glm.vec2(width / 2, height / 2)
        self._floor_surface: pygame.Surface | None = None

        self._generate()

    def _generate(self) -> None:
        root = BSPNode(pygame.Rect(0, 0, self.width, self.height))
        self._split(root, 0)
        self._create_rooms(root)
        self._connect(root)
        self._collect_walls()
        self._add_boundary_walls()
        if self.rooms:
            self.spawn_pos = glm.vec2(self.rooms[0].center)
        self._bake_floor_surface()

    def _split(self, node: BSPNode, depth: int) -> None:
        min_size = 80
        if node.rect.width < min_size * 2 and node.rect.height < min_size * 2:
            return
        if depth > 6:
            return

        # Choose split axis — prefer splitting the longer dimension
        if node.rect.width > node.rect.height * 1.3:
            horizontal = False
        elif node.rect.height > node.rect.width * 1.3:
            horizontal = True
        else:
            horizontal = random.random() < 0.5

        if horizontal:
            if node.rect.height < min_size * 2:
                return
            split = random.randint(
                node.rect.top + min_size, node.rect.bottom - min_size
            )
            node.left = BSPNode(
                pygame.Rect(
                    node.rect.left, node.rect.top,
                    node.rect.width, split - node.rect.top,
                )
            )
            node.right = BSPNode(
                pygame.Rect(
                    node.rect.left, split,
                    node.rect.width, node.rect.bottom - split,
                )
            )
        else:
            if node.rect.width < min_size * 2:
                return
            split = random.randint(
                node.rect.left + min_size, node.rect.right - min_size
            )
            node.left = BSPNode(
                pygame.Rect(
                    node.rect.left, node.rect.top,
                    split - node.rect.left, node.rect.height,
                )
            )
            node.right = BSPNode(
                pygame.Rect(
                    split, node.rect.top,
                    node.rect.right - split, node.rect.height,
                )
            )

        self._split(node.left, depth + 1)
        self._split(node.right, depth + 1)

    def _create_rooms(self, node: BSPNode) -> None:
        if node.left and node.right:
            self._create_rooms(node.left)
            self._create_rooms(node.right)
            return

        # Leaf node — carve an irregular room
        r = node.rect
        margin_min = 8
        margin_max = min(20, r.width // 4, r.height // 4)
        margin_max = max(margin_min + 1, margin_max)

        left = r.left + random.randint(margin_min, margin_max)
        right = r.right - random.randint(margin_min, margin_max)
        top = r.top + random.randint(margin_min, margin_max)
        bottom = r.bottom - random.randint(margin_min, margin_max)

        if right - left < 20 or bottom - top < 20:
            # Too small, use minimal margins
            left = r.left + margin_min
            right = r.right - margin_min
            top = r.top + margin_min
            bottom = r.bottom - margin_min

        corners = [
            glm.vec2(left, top),
            glm.vec2(right, top),
            glm.vec2(right, bottom),
            glm.vec2(left, bottom),
        ]

        # Perturb corners
        for i, c in enumerate(corners):
            corners[i] = glm.vec2(
                c.x + random.uniform(-6, 6),
                c.y + random.uniform(-6, 6),
            )

        # Optionally add midpoints on long edges for more irregular shapes
        vertices: list[glm.vec2] = []
        for i in range(len(corners)):
            vertices.append(corners[i])
            nxt = corners[(i + 1) % len(corners)]
            edge_len = glm.distance(corners[i], nxt)
            if edge_len > 40 and random.random() < 0.6:
                mid = (corners[i] + nxt) / 2
                mid = glm.vec2(
                    mid.x + random.uniform(-5, 5),
                    mid.y + random.uniform(-5, 5),
                )
                vertices.append(mid)

        room = Room(vertices)
        node.room = room
        self.rooms.append(room)

    def _get_rooms(self, node: BSPNode) -> list[Room]:
        if node.room:
            return [node.room]
        rooms: list[Room] = []
        if node.left:
            rooms.extend(self._get_rooms(node.left))
        if node.right:
            rooms.extend(self._get_rooms(node.right))
        return rooms

    def _connect(self, node: BSPNode) -> None:
        if not node.left or not node.right:
            return
        self._connect(node.left)
        self._connect(node.right)

        left_rooms = self._get_rooms(node.left)
        right_rooms = self._get_rooms(node.right)

        # Find closest room pair
        best_dist = float("inf")
        best_pair: tuple[Room, Room] | None = None
        for lr in left_rooms:
            for rr in right_rooms:
                d = glm.distance(lr.center, rr.center)
                if d < best_dist:
                    best_dist = d
                    best_pair = (lr, rr)

        if best_pair:
            self._make_corridor(best_pair[0], best_pair[1])

    def _make_corridor(self, room_a: Room, room_b: Room) -> None:
        a = room_a.center
        b = room_b.center
        half_w = random.randint(4, 6)

        # L-shaped corridor
        if random.random() < 0.5:
            mid = glm.vec2(a.x, b.y)
        else:
            mid = glm.vec2(b.x, a.y)

        self._add_corridor_segment(a, mid, half_w)
        self._add_corridor_segment(mid, b, half_w)

    def _add_corridor_segment(
        self, start: glm.vec2, end: glm.vec2, half_w: int
    ) -> None:
        if glm.distance(start, end) < 1:
            return

        d = end - start
        if abs(d.x) > abs(d.y):
            # Horizontal corridor
            x1 = min(start.x, end.x)
            x2 = max(start.x, end.x)
            cy = (start.y + end.y) / 2
            verts = [
                glm.vec2(x1, cy - half_w),
                glm.vec2(x2, cy - half_w),
                glm.vec2(x2, cy + half_w),
                glm.vec2(x1, cy + half_w),
            ]
        else:
            # Vertical corridor
            y1 = min(start.y, end.y)
            y2 = max(start.y, end.y)
            cx = (start.x + end.x) / 2
            verts = [
                glm.vec2(cx - half_w, y1),
                glm.vec2(cx + half_w, y1),
                glm.vec2(cx + half_w, y2),
                glm.vec2(cx - half_w, y2),
            ]

        self.corridors.append(verts)

    def _collect_walls(self) -> None:
        """Collect walls from rooms and corridors, cutting openings where corridors
        intersect room walls."""
        # Build corridor rects for fast overlap checks
        corridor_rects: list[pygame.Rect] = []
        for cverts in self.corridors:
            xs = [v.x for v in cverts]
            ys = [v.y for v in cverts]
            corridor_rects.append(
                pygame.Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
            )

        # Room walls — split around corridor openings
        for room in self.rooms:
            for wall in room.walls:
                segments = self._cut_wall_by_corridors(wall, corridor_rects)
                self.walls.extend(segments)

        # Corridor walls — clip to only keep parts outside rooms
        for cverts in self.corridors:
            for i in range(len(cverts)):
                seg = (cverts[i], cverts[(i + 1) % len(cverts)])
                self.walls.extend(self._clip_segment_outside_rooms(seg))

    def _cut_wall_by_corridors(
        self, wall: Wall, corridor_rects: list[pygame.Rect]
    ) -> list[Wall]:
        """Cut a wall segment where corridors cross it, leaving openings."""
        p1, p2 = wall
        d = p2 - p1
        length = glm.length(d)
        if length < 0.1:
            return [wall]

        # Collect cut intervals as (t_start, t_end) along the wall
        cuts: list[tuple[float, float]] = []
        for crect in corridor_rects:
            # Inflate the corridor rect slightly to ensure clean cuts
            inflated = crect.inflate(2, 2)
            # Find parametric intersection of wall with corridor rect
            t_values: list[float] = []
            for t_check in range(int(length) + 1):
                t = t_check / length if length > 0 else 0
                pt = p1 + d * t
                if inflated.collidepoint(pt.x, pt.y):
                    t_values.append(t)

            # Also check endpoints
            for t in [0.0, 1.0]:
                pt = p1 + d * t
                if inflated.collidepoint(pt.x, pt.y):
                    t_values.append(t)

            if t_values:
                cuts.append((min(t_values), max(t_values)))

        if not cuts:
            return [wall]

        # Merge overlapping cuts
        cuts.sort()
        merged: list[tuple[float, float]] = [cuts[0]]
        for start, end in cuts[1:]:
            if start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        # Build remaining segments
        result: list[Wall] = []
        prev_t = 0.0
        for cut_start, cut_end in merged:
            if cut_start - prev_t > 0.02:
                result.append((p1 + d * prev_t, p1 + d * cut_start))
            prev_t = cut_end
        if 1.0 - prev_t > 0.02:
            result.append((p1 + d * prev_t, p2))

        return result

    def _clip_segment_outside_rooms(self, seg: Wall) -> list[Wall]:
        """Split a corridor wall segment at room boundaries, keeping only
        the sub-segments whose midpoints are outside all rooms."""
        p1, p2 = seg
        d = p2 - p1
        length_sq = glm.dot(d, d)
        if length_sq < 0.01:
            return []

        # Find all t-values where this segment crosses a room edge
        t_values: set[float] = {0.0, 1.0}
        for room in self.rooms:
            for rwall in room.walls:
                hit = ray_segment_intersect(p1, p2, rwall[0], rwall[1])
                if hit is not None:
                    t = glm.dot(hit - p1, d) / length_sq
                    if 0 < t < 1:
                        t_values.add(round(t, 6))

        sorted_t = sorted(t_values)

        result: list[Wall] = []
        for i in range(len(sorted_t) - 1):
            t_start = sorted_t[i]
            t_end = sorted_t[i + 1]
            mid_pt = p1 + d * ((t_start + t_end) / 2)
            # Keep only sub-segments outside all rooms
            inside = False
            for room in self.rooms:
                if self._point_in_polygon(mid_pt, room.vertices):
                    inside = True
                    break
            if not inside:
                sp = p1 + d * t_start
                ep = p1 + d * t_end
                if glm.distance(sp, ep) > 0.5:
                    result.append((sp, ep))
        return result

    @staticmethod
    def _point_in_polygon(point: glm.vec2, polygon: list[glm.vec2]) -> bool:
        """Ray-casting point-in-polygon test."""
        n = len(polygon)
        inside = False
        j = n - 1
        for i in range(n):
            pi = polygon[i]
            pj = polygon[j]
            if (pi.y > point.y) != (pj.y > point.y) and (
                point.x < (pj.x - pi.x) * (point.y - pi.y) / (pj.y - pi.y) + pi.x
            ):
                inside = not inside
            j = i
        return inside

    def _add_boundary_walls(self) -> None:
        w, h = float(self.width), float(self.height)
        corners = [
            glm.vec2(0, 0),
            glm.vec2(w, 0),
            glm.vec2(w, h),
            glm.vec2(0, h),
        ]
        for i in range(4):
            self.walls.append((corners[i], corners[(i + 1) % 4]))

    def _bake_floor_surface(self) -> None:
        """Pre-render the floor polygons onto a surface for fast drawing."""
        self._floor_surface = pygame.Surface(
            (self.width, self.height), pygame.SRCALPHA
        )
        self._floor_surface.fill(VOID_COLOR)
        for room in self.rooms:
            pts = [(int(v.x), int(v.y)) for v in room.vertices]
            if len(pts) >= 3:
                pygame.draw.polygon(self._floor_surface, FLOOR_COLOR, pts)
        for cverts in self.corridors:
            pts = [(int(v.x), int(v.y)) for v in cverts]
            if len(pts) >= 3:
                pygame.draw.polygon(self._floor_surface, FLOOR_COLOR, pts)

    def draw(self, surface: pygame.Surface, cam_offset: glm.vec2) -> None:
        if self._floor_surface is None:
            return

        screen_rect = pygame.Rect(
            int(cam_offset.x), int(cam_offset.y),
            surface.get_width(), surface.get_height(),
        )

        # Blit the visible portion of the floor surface
        surface.blit(self._floor_surface, (0, 0), screen_rect)

        # Draw wall lines (only those near viewport)
        inflated = screen_rect.inflate(20, 20)
        for wall in self.walls:
            p1, p2 = wall
            # Quick AABB check
            wx1 = min(p1.x, p2.x)
            wy1 = min(p1.y, p2.y)
            wx2 = max(p1.x, p2.x)
            wy2 = max(p1.y, p2.y)
            if wx2 < inflated.left or wx1 > inflated.right:
                continue
            if wy2 < inflated.top or wy1 > inflated.bottom:
                continue

            sp1 = p1 - cam_offset
            sp2 = p2 - cam_offset
            pygame.draw.line(surface, WALL_COLOR, sp1, sp2, 1)

    def collide_player(self, player: Player, old_pos: glm.vec2) -> None:
        """Push player out of walls using swept + push-out collision."""
        radius = 3.0
        # First pass: swept collision — snap back if player crossed a wall
        for wall in self.walls:
            if intersect(old_pos, player.pos, wall[0], wall[1]):
                player.pos = glm.vec2(old_pos)
                break
        # Second pass: proximity push-out for wall sliding
        for _ in range(3):
            for wall in self.walls:
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

    def collide_entity(self, entity: Bullet | Shell, old_pos: glm.vec2) -> bool:
        """Check entity movement against walls. Returns True if a wall was hit."""
        for wall in self.walls:
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
                    # Reflect velocity
                    entity.vel = entity.vel - n * 2 * glm.dot(entity.vel, n)
                    entity.pos = glm.vec2(old_pos)
                else:
                    # Shell: stop
                    entity.vel = glm.vec2()
                    entity.speed = 0.0
                    entity.pos = glm.vec2(old_pos)
                return True
        return False

    def get_wall_vertices(self) -> list[glm.vec2]:
        """Get unique vertices from all walls for visibility raycasting."""
        seen: set[tuple[float, float]] = set()
        verts: list[glm.vec2] = []
        for w in self.walls:
            for p in w:
                key = (round(p.x, 1), round(p.y, 1))
                if key not in seen:
                    seen.add(key)
                    verts.append(p)
        return verts
