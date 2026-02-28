from __future__ import annotations

import math
import random

import pygame
from pyglm import glm
from shapely import unary_union
from shapely.geometry import MultiPolygon, Polygon

from portal_shooter.map.types import BSPNode, Room, Wall


def split(node: BSPNode, depth: int) -> None:
    """Recursively split a BSP node into left/right children."""
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
        split_pos = random.randint(
            node.rect.top + min_size, node.rect.bottom - min_size
        )
        node.left = BSPNode(
            pygame.Rect(
                node.rect.left, node.rect.top,
                node.rect.width, split_pos - node.rect.top,
            )
        )
        node.right = BSPNode(
            pygame.Rect(
                node.rect.left, split_pos,
                node.rect.width, node.rect.bottom - split_pos,
            )
        )
    else:
        if node.rect.width < min_size * 2:
            return
        split_pos = random.randint(
            node.rect.left + min_size, node.rect.right - min_size
        )
        node.left = BSPNode(
            pygame.Rect(
                node.rect.left, node.rect.top,
                split_pos - node.rect.left, node.rect.height,
            )
        )
        node.right = BSPNode(
            pygame.Rect(
                split_pos, node.rect.top,
                node.rect.right - split_pos, node.rect.height,
            )
        )

    split(node.left, depth + 1)
    split(node.right, depth + 1)


def create_rooms(node: BSPNode) -> list[Room]:
    """Recursively create rooms in BSP leaf nodes. Returns all created rooms."""
    if node.left and node.right:
        rooms = create_rooms(node.left)
        rooms.extend(create_rooms(node.right))
        return rooms

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
    return [room]


def get_rooms(node: BSPNode) -> list[Room]:
    """Collect all rooms from a BSP subtree."""
    if node.room:
        return [node.room]
    rooms: list[Room] = []
    if node.left:
        rooms.extend(get_rooms(node.left))
    if node.right:
        rooms.extend(get_rooms(node.right))
    return rooms


def connect(node: BSPNode) -> list[list[glm.vec2]]:
    """Recursively connect BSP siblings with corridors. Returns corridor vertex lists."""
    if not node.left or not node.right:
        return []

    corridors: list[list[glm.vec2]] = []
    corridors.extend(connect(node.left))
    corridors.extend(connect(node.right))

    left_rooms = get_rooms(node.left)
    right_rooms = get_rooms(node.right)

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
        corridor = make_corridor(best_pair[0], best_pair[1])
        if corridor is not None:
            corridors.append(corridor)

    return corridors


def make_corridor(room_a: Room, room_b: Room) -> list[glm.vec2] | None:
    """Connect two rooms with a single wide doorway (direct line)."""
    a = room_a.center
    b = room_b.center
    half_w = random.randint(12, 20)
    return add_corridor_segment(a, b, half_w)


def add_corridor_segment(
    start: glm.vec2, end: glm.vec2, half_w: int
) -> list[glm.vec2] | None:
    """Build a corridor quad between two points. Returns vertices or None if too short."""
    if glm.distance(start, end) < 1:
        return None

    d = end - start
    length = glm.length(d)
    fwd = d / length
    perp = glm.vec2(-fwd.y, fwd.x)

    # Build quad along the segment direction (works for any angle)
    hw = float(half_w)
    return [
        start - perp * hw,
        end - perp * hw,
        end + perp * hw,
        start + perp * hw,
    ]


def collect_walls(rooms: list[Room], corridors: list[list[glm.vec2]]) -> list[Wall]:
    """Union all room and corridor polygons with Shapely, then extract
    the boundary edges as wall segments."""
    polys: list[Polygon] = []
    for room in rooms:
        coords = [(v.x, v.y) for v in room.vertices]
        p = Polygon(coords)
        if p.is_valid and p.area > 1:
            polys.append(p)
    for cverts in corridors:
        coords = [(v.x, v.y) for v in cverts]
        if len(coords) >= 3:
            p = Polygon(coords)
            if p.is_valid and p.area > 1:
                polys.append(p)

    if not polys:
        return []

    union = unary_union(polys)

    walls: list[Wall] = []

    def _extract_walls(geom: Polygon | MultiPolygon) -> None:
        if isinstance(geom, MultiPolygon):
            for poly in geom.geoms:
                _extract_walls(poly)
            return
        # Exterior ring
        coords = list(geom.exterior.coords)
        for i in range(len(coords) - 1):
            a, b = coords[i], coords[i + 1]
            walls.append((glm.vec2(a[0], a[1]), glm.vec2(b[0], b[1])))
        # Interior rings (holes)
        for interior in geom.interiors:
            coords = list(interior.coords)
            for i in range(len(coords) - 1):
                a, b = coords[i], coords[i + 1]
                walls.append((glm.vec2(a[0], a[1]), glm.vec2(b[0], b[1])))

    if isinstance(union, (Polygon, MultiPolygon)):
        _extract_walls(union)
    return walls


def add_pillars(rooms: list[Room]) -> list[Wall]:
    """Scatter small square pillars inside large rooms as internal obstacles."""
    walls: list[Wall] = []
    margin = 20
    for room in rooms:
        area = room.bounds.width * room.bounds.height
        if area < 15000:
            continue
        n_pillars = random.randint(1, 4)
        b = room.bounds
        for _ in range(n_pillars):
            size = random.randint(10, 18)
            hs = size / 2.0
            # Skip if bounds are too tight
            if b.right - b.left < 2 * (margin + hs) + 1:
                continue
            if b.bottom - b.top < 2 * (margin + hs) + 1:
                continue
            # Random position inside room bounds with margin
            px = random.uniform(b.left + margin + hs, b.right - margin - hs)
            py = random.uniform(b.top + margin + hs, b.bottom - margin - hs)
            # Add 4 walls forming a square pillar
            tl = glm.vec2(px - hs, py - hs)
            tr = glm.vec2(px + hs, py - hs)
            br = glm.vec2(px + hs, py + hs)
            bl = glm.vec2(px - hs, py + hs)
            walls.append((tl, tr))
            walls.append((tr, br))
            walls.append((br, bl))
            walls.append((bl, tl))
    return walls


def add_boundary_walls(width: int, height: int) -> list[Wall]:
    """Create perimeter walls around the map."""
    w, h = float(width), float(height)
    corners = [
        glm.vec2(0, 0),
        glm.vec2(w, 0),
        glm.vec2(w, h),
        glm.vec2(0, h),
    ]
    return [(corners[i], corners[(i + 1) % 4]) for i in range(4)]


def generate_pickup_positions(rooms: list[Room]) -> list[tuple[glm.vec2, str]]:
    """Generate pickup positions, one per qualifying room (skipping room 0).

    Returns list of (position, kind_str) tuples where kind_str is "health" or "speed".
    """
    positions: list[tuple[glm.vec2, str]] = []
    for room in rooms[1:]:
        if room.bounds.width * room.bounds.height < 5000:
            continue
        offset = glm.vec2(random.uniform(-10, 10), random.uniform(-10, 10))
        pos = room.center + offset
        kind = "health" if random.random() < 0.7 else "speed"
        positions.append((pos, kind))
    return positions
