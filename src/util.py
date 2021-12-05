from typing import Any
from typing import List
from typing import Tuple

from pygame import Vector2


def direction(p1: Vector2, p2: Vector2, p3: Vector2) -> Vector2:
    return (p3 - p1).cross(p2 - p1)


def intersect(p1: Vector2, p2: Vector2, p3: Vector2, p4: Vector2) -> bool:
    d1 = direction(p3, p4, p1)
    d2 = direction(p3, p4, p2)
    d3 = direction(p1, p2, p3)
    d4 = direction(p1, p2, p4)

    return (
        ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and
        ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0))
    )


def point_dist_to_line(point: Vector2, segment: Tuple[Vector2, Vector2]) -> float:
    p1, p2 = segment
    v1 = p2 - p1
    v2 = point - p1
    t = v2.dot(v1) / v1.dot(v1)
    if t < 0:
        return (p1 - point).length()
    if t > 1:
        return (p2 - point).length()
    return (p1 + v1 * t - point).length()


def get_collisions(entity: Any, others: List[Any]):
    if not hasattr(entity, 'rect'):
        raise AttributeError('Entity must have a rect attribute')
    return [o for o in others if hasattr(o, 'rect') and o.rect.colliderect(entity.rect)]


def remap(val, min_in, max_in, min_out, max_out, clamp=True):
    if clamp:
        return min(max(min_out, (val - min_in) * (max_out - min_out) / (max_in - min_in) + min_out), max_out)
    return (val - min_in) / (max_in - min_in) * (max_out - min_out) + min_out


def lerp(a, b, t):
    return a + (b - a) * t
