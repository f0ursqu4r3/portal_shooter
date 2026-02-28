from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import pygame
from pyglm import glm
from shapely import unary_union
from shapely.geometry import MultiPolygon, Polygon

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
        "_wall_grid",
    ]

    def __init__(self, width: int = 1000, height: int = 1000) -> None:
        self.width: int = width
        self.height: int = height
        self.rooms: list[Room] = []
        self.corridors: list[list[glm.vec2]] = []
        self.walls: list[Wall] = []
        self.bounds: glm.vec2 = glm.vec2(width, height)
        self.spawn_pos: glm.vec2 = glm.vec2(width / 2, height / 2)
        self._floor_surface: pygame.Surface | None = None
        self._wall_grid: WallGrid | None = None

        self._generate()

    def _generate(self) -> None:
        root = BSPNode(pygame.Rect(0, 0, self.width, self.height))
        self._split(root, 0)
        self._create_rooms(root)
        self._connect(root)
        self._collect_walls()
        self._add_pillars()
        self._add_boundary_walls()
        self._wall_grid = WallGrid(self.walls)
        if self.rooms:
            self.spawn_pos = glm.vec2(self.rooms[0].center)
        self._bake_floor_surface()

    def _split(self, node: BSPNode, depth: int) -> None:
        min_size = 100
        if node.rect.width < min_size * 2 and node.rect.height < min_size * 2:
            return
        if depth > 5:
            return
        # 40% early-stop at depth 3+ — preserves large leaves
        if depth >= 3 and random.random() < 0.4:
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

        # Leaf node — carve a rectilinear room (rectangle, possibly L-shaped)
        r = node.rect

        # Pick archetype for sizing: Large 70%, Medium 20%, Small 10%
        roll = random.random()
        if roll < 0.7:
            margin_frac_min, margin_frac_max = 0.03, 0.08
        elif roll < 0.9:
            margin_frac_min, margin_frac_max = 0.08, 0.18
        else:
            margin_frac_min, margin_frac_max = 0.18, 0.35

        # Derive rectangle bounds within the BSP cell
        mx = random.uniform(margin_frac_min, margin_frac_max) * r.width
        my = random.uniform(margin_frac_min, margin_frac_max) * r.height
        x0 = r.left + mx
        y0 = r.top + my
        x1 = r.right - mx
        y1 = r.bottom - my

        if x1 - x0 < 20:
            x0, x1 = r.left + 5, r.right - 5
        if y1 - y0 < 20:
            y0, y1 = r.top + 5, r.bottom - 5

        # Base rectangle corners (CCW)
        corners: list[tuple[float, float]] = [
            (x0, y0), (x1, y0), (x1, y1), (x0, y1),
        ]

        # 40% chance to cut a rectangular notch from one corner — L-shape
        if random.random() < 0.4:
            w = x1 - x0
            h = y1 - y0
            # Notch size: 25-45% of each dimension
            nw = w * random.uniform(0.25, 0.45)
            nh = h * random.uniform(0.25, 0.45)
            # Pick which corner to notch (0=TL, 1=TR, 2=BR, 3=BL)
            corner_idx = random.randint(0, 3)
            if corner_idx == 0:  # top-left
                corners = [
                    (x0 + nw, y0), (x1, y0), (x1, y1),
                    (x0, y1), (x0, y0 + nh), (x0 + nw, y0 + nh),
                ]
            elif corner_idx == 1:  # top-right
                corners = [
                    (x0, y0), (x1 - nw, y0), (x1 - nw, y0 + nh),
                    (x1, y0 + nh), (x1, y1), (x0, y1),
                ]
            elif corner_idx == 2:  # bottom-right
                corners = [
                    (x0, y0), (x1, y0), (x1, y1 - nh),
                    (x1 - nw, y1 - nh), (x1 - nw, y1), (x0, y1),
                ]
            else:  # bottom-left
                corners = [
                    (x0, y0), (x1, y0), (x1, y1),
                    (x0 + nw, y1), (x0 + nw, y1 - nh), (x0, y1 - nh),
                ]

        # Minimal edge perturbation on long edges for rough-wall feel
        vertices: list[glm.vec2] = []
        for i in range(len(corners)):
            cx, cy = corners[i]
            nx, ny = corners[(i + 1) % len(corners)]
            vertices.append(glm.vec2(cx, cy))
            edge_len = math.hypot(nx - cx, ny - cy)
            if edge_len > 80:
                # Add 1-2 midpoints with small perpendicular jitter (2-4px)
                n_mids = 1 if edge_len < 150 else 2
                dx, dy = nx - cx, ny - cy
                perp_x, perp_y = -dy / edge_len, dx / edge_len
                for j in range(n_mids):
                    t = (j + 1) / (n_mids + 1)
                    px = cx + dx * t + perp_x * random.uniform(-4, 4)
                    py = cy + dy * t + perp_y * random.uniform(-4, 4)
                    vertices.append(glm.vec2(px, py))

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
        """Connect two rooms with a single wide doorway (direct line)."""
        a = room_a.center
        b = room_b.center
        half_w = random.randint(12, 20)
        self._add_corridor_segment(a, b, half_w)

    def _add_corridor_segment(
        self, start: glm.vec2, end: glm.vec2, half_w: int
    ) -> None:
        if glm.distance(start, end) < 1:
            return

        d = end - start
        length = glm.length(d)
        fwd = d / length
        perp = glm.vec2(-fwd.y, fwd.x)

        # Build quad along the segment direction (works for any angle)
        hw = float(half_w)
        verts = [
            start - perp * hw,
            end - perp * hw,
            end + perp * hw,
            start + perp * hw,
        ]

        self.corridors.append(verts)

    def _add_pillars(self) -> None:
        """Scatter small square pillars inside large rooms as internal obstacles."""
        margin = 20
        for room in self.rooms:
            area = room.bounds.width * room.bounds.height
            if area < 15000:
                continue
            n_pillars = random.randint(1, 4)
            b = room.bounds
            for _ in range(n_pillars):
                size = random.randint(10, 18)
                hs = size / 2.0
                # Random position inside room bounds with margin
                px = random.uniform(b.left + margin + hs, b.right - margin - hs)
                py = random.uniform(b.top + margin + hs, b.bottom - margin - hs)
                # Skip if bounds are too tight
                if b.right - b.left < 2 * (margin + hs) + 1:
                    continue
                if b.bottom - b.top < 2 * (margin + hs) + 1:
                    continue
                # Add 4 walls forming a square pillar
                tl = glm.vec2(px - hs, py - hs)
                tr = glm.vec2(px + hs, py - hs)
                br = glm.vec2(px + hs, py + hs)
                bl = glm.vec2(px - hs, py + hs)
                self.walls.append((tl, tr))
                self.walls.append((tr, br))
                self.walls.append((br, bl))
                self.walls.append((bl, tl))

    def _collect_walls(self) -> None:
        """Union all room and corridor polygons with Shapely, then extract
        the boundary edges as wall segments."""
        polys: list[Polygon] = []
        for room in self.rooms:
            coords = [(v.x, v.y) for v in room.vertices]
            p = Polygon(coords)
            if p.is_valid and p.area > 1:
                polys.append(p)
        for cverts in self.corridors:
            coords = [(v.x, v.y) for v in cverts]
            if len(coords) >= 3:
                p = Polygon(coords)
                if p.is_valid and p.area > 1:
                    polys.append(p)

        if not polys:
            return

        union = unary_union(polys)

        # Extract boundary line segments from the union
        def _extract_walls(geom: Polygon | MultiPolygon) -> None:
            if isinstance(geom, MultiPolygon):
                for poly in geom.geoms:
                    _extract_walls(poly)
                return
            # Exterior ring
            coords = list(geom.exterior.coords)
            for i in range(len(coords) - 1):
                a, b = coords[i], coords[i + 1]
                self.walls.append((glm.vec2(a[0], a[1]), glm.vec2(b[0], b[1])))
            # Interior rings (holes)
            for interior in geom.interiors:
                coords = list(interior.coords)
                for i in range(len(coords) - 1):
                    a, b = coords[i], coords[i + 1]
                    self.walls.append(
                        (glm.vec2(a[0], a[1]), glm.vec2(b[0], b[1]))
                    )

        _extract_walls(union)

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

    def _get_nearby_walls(self, x: float, y: float, radius: float) -> list[Wall]:
        """Return Wall tuples near a point using the spatial grid."""
        assert self._wall_grid is not None
        flat = self._wall_grid.query(x, y, radius)
        return [(glm.vec2(x1, y1), glm.vec2(x2, y2)) for x1, y1, x2, y2 in flat]

    def collide_player(self, player: Player, old_pos: glm.vec2) -> None:
        """Push player out of walls using swept + push-out collision."""
        radius = 3.0
        nearby = self._get_nearby_walls(player.pos.x, player.pos.y, 20.0)
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

    def collide_entity(self, entity: Bullet | Shell, old_pos: glm.vec2) -> bool:
        """Check entity movement against walls. Returns True if a wall was hit."""
        cx = (old_pos.x + entity.pos.x) * 0.5
        cy = (old_pos.y + entity.pos.y) * 0.5
        reach = glm.distance(old_pos, entity.pos) * 0.5 + 5.0
        nearby = self._get_nearby_walls(cx, cy, reach)
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

    def find_nearest_wall_hit(
        self,
        origin: glm.vec2,
        direction: glm.vec2,
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

        for wall in self.walls:
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
