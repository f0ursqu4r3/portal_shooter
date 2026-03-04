from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
from pyglm import glm

from portal_shooter.map.collision import (
    collide_entity as _collide_entity,
    collide_grenade as _collide_grenade,
    collide_player as _collide_player,
    find_nearest_wall_hit as _find_nearest_wall_hit,
    get_wall_vertices as _get_wall_vertices,
)
from portal_shooter.map.generation import (
    add_boundary_walls,
    add_extra_connections,
    add_pillars,
    collect_walls,
    connect,
    create_rooms,
    generate_crate_positions,
    generate_door_positions,
    generate_pickup_positions,
    split,
)
from portal_shooter.map.pathfinding import RoomGraph
from portal_shooter.map.spatial_grid import WallGrid
from portal_shooter.map.types import FLOOR_COLOR, VOID_COLOR, WALL_COLOR, BSPNode, Room, Wall

if TYPE_CHECKING:
    from portal_shooter.entities.bullet import Bullet
    from portal_shooter.entities.entity import Entity
    from portal_shooter.entities.grenade import Grenade
    from portal_shooter.entities.rocket import Rocket
    from portal_shooter.entities.shell import Shell


class GameMap:
    __slots__ = [
        "width",
        "height",
        "rooms",
        "corridors",
        "walls",
        "bounds",
        "spawn_pos",
        "pickup_positions",
        "crate_positions",
        "door_positions",
        "room_graph",
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
        self.pickup_positions: list[tuple[glm.vec2, str, str | None]] = []
        self.crate_positions: list[glm.vec2] = []
        self.door_positions: list[tuple[glm.vec2, glm.vec2, glm.vec2]] = []
        self._floor_surface: pygame.Surface | None = None
        self._wall_grid: WallGrid | None = None
        self.room_graph: RoomGraph | None = None

        self._generate()

    def _generate(self) -> None:
        root = BSPNode(pygame.Rect(0, 0, self.width, self.height))
        split(root, 0)
        self.rooms = create_rooms(root)
        self.corridors = connect(root)
        self.corridors.extend(add_extra_connections(self.rooms, self.corridors))
        self.walls = collect_walls(self.rooms, self.corridors)
        self.walls.extend(add_pillars(self.rooms))
        self.walls.extend(add_boundary_walls(self.width, self.height))
        self._wall_grid = WallGrid(self.walls)
        if self.rooms:
            self.spawn_pos = glm.vec2(self.rooms[0].center)
            self.pickup_positions = generate_pickup_positions(self.rooms)
            self.crate_positions = generate_crate_positions(self.rooms)
            self.door_positions = generate_door_positions(self.rooms, self.corridors)
        self.room_graph = RoomGraph(self.rooms, self.corridors)
        self._bake_floor_surface()

    def _bake_floor_surface(self) -> None:
        """Pre-render the floor polygons + wall lines onto a surface."""
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
        # Bake wall lines onto the surface
        for wall in self.walls:
            p1, p2 = wall
            pygame.draw.line(
                self._floor_surface, WALL_COLOR,
                (int(p1.x), int(p1.y)), (int(p2.x), int(p2.y)), 1,
            )

    def draw(self, surface: pygame.Surface, cam_offset: glm.vec2) -> None:
        if self._floor_surface is None:
            return

        screen_rect = pygame.Rect(
            int(cam_offset.x), int(cam_offset.y),
            surface.get_width(), surface.get_height(),
        )

        # Blit the visible portion of the pre-baked floor + walls surface
        surface.blit(self._floor_surface, (0, 0), screen_rect)

    def collide_player(
        self, entity: Entity, old_pos: glm.vec2,
        radius: float = 3.0, push_iters: int = 3,
    ) -> None:
        assert self._wall_grid is not None
        _collide_player(entity, old_pos, self._wall_grid, radius, push_iters)

    def collide_entity(
        self, entity: Bullet | Shell, old_pos: glm.vec2
    ) -> tuple[float, float, float, float] | None:
        assert self._wall_grid is not None
        return _collide_entity(entity, old_pos, self._wall_grid)

    def collide_grenade(self, grenade: Grenade | Rocket, old_pos: glm.vec2) -> bool:
        assert self._wall_grid is not None
        return _collide_grenade(grenade, old_pos, self._wall_grid)

    def remove_walls(self, to_remove: list[Wall]) -> None:
        """Remove walls from the map and rebuild the spatial grid + surface."""
        remove_set = {(w[0].x, w[0].y, w[1].x, w[1].y) for w in to_remove}
        self.walls = [
            w for w in self.walls
            if (w[0].x, w[0].y, w[1].x, w[1].y) not in remove_set
        ]
        self._wall_grid = WallGrid(self.walls)
        self._bake_floor_surface()

    def add_walls(self, new_walls: list[Wall]) -> None:
        """Add walls to the map and rebuild the spatial grid + surface."""
        self.walls.extend(new_walls)
        self._wall_grid = WallGrid(self.walls)
        self._bake_floor_surface()

    def find_nearest_wall_hit(
        self,
        origin: glm.vec2,
        direction: glm.vec2,
        max_range: float = 500,
    ) -> tuple[glm.vec2, glm.vec2] | None:
        return _find_nearest_wall_hit(origin, direction, self.walls, max_range)

    def get_wall_vertices(self) -> list[glm.vec2]:
        return _get_wall_vertices(self.walls)
