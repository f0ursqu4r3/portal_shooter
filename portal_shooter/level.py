from __future__ import annotations

from pyglm import glm

from portal_shooter.map.types import Room


class LevelState:
    __slots__ = ["floor", "has_key", "key_room", "exit_room", "key_pos", "exit_pos"]

    def __init__(self) -> None:
        self.floor: int = 1
        self.has_key: bool = False
        self.key_room: int = 0
        self.exit_room: int = 0
        self.key_pos: glm.vec2 = glm.vec2()
        self.exit_pos: glm.vec2 = glm.vec2()

    def setup_floor(self, rooms: list[Room], spawn_room_idx: int = 0) -> None:
        """Pick key and exit rooms based on distance from spawn."""
        self.has_key = False
        if len(rooms) < 3:
            # Fallback for tiny maps
            self.key_room = min(1, len(rooms) - 1)
            self.exit_room = min(2, len(rooms) - 1)
            self.key_pos = glm.vec2(rooms[self.key_room].center)
            self.exit_pos = glm.vec2(rooms[self.exit_room].center)
            return

        spawn_center = rooms[spawn_room_idx].center
        # Sort rooms by distance from spawn, descending
        dists = [
            (glm.distance(spawn_center, r.center), i)
            for i, r in enumerate(rooms)
            if i != spawn_room_idx
        ]
        dists.sort(reverse=True)

        # Key in farthest room, exit in second-farthest
        self.key_room = dists[0][1]
        self.exit_room = dists[1][1]
        self.key_pos = glm.vec2(rooms[self.key_room].center)
        self.exit_pos = glm.vec2(rooms[self.exit_room].center)

    def advance_floor(self) -> None:
        self.floor += 1
        self.has_key = False


def get_difficulty_params(floor: int) -> dict[str, float]:
    """Linear scaling of enemy stats per floor."""
    return {
        "enemy_count_mul": 1.0 + (floor - 1) * 0.2,
        "enemy_health_mul": 1.0 + (floor - 1) * 0.15,
        "enemy_speed_mul": 1.0 + (floor - 1) * 0.1,
    }
