from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from portal_shooter.game import Game


class HUD:
    __slots__ = [
        "_font_sm",
        "_font_md",
        "_label_hp",
        "_label_spd",
        "_label_q",
        "_label_e",
        "_cached_hp_text",
        "_cached_hp_val",
        "_cached_fps_text",
        "_cached_fps_val",
        "_minimap_bg",
        "_minimap_size",
        "_timer",
    ]

    def __init__(self) -> None:
        self._font_sm: pygame.font.Font = pygame.font.Font("assets/fonts/homespun.ttf", 16)
        self._font_md: pygame.font.Font = pygame.font.Font("assets/fonts/homespun.ttf", 20)

        # Pre-render static labels (antialias=False for pixel font)
        self._label_hp: pygame.Surface = self._font_sm.render(
            "HP", False, (180, 40, 40)
        )
        self._label_spd: pygame.Surface = self._font_sm.render(
            "SPD", False, (220, 200, 40)
        )
        self._label_q: pygame.Surface = self._font_sm.render(
            "Q:", False, (200, 200, 200)
        )
        self._label_e: pygame.Surface = self._font_sm.render(
            "E:", False, (200, 200, 200)
        )

        # Cached numeric surfaces
        self._cached_hp_text: pygame.Surface | None = None
        self._cached_hp_val: int = -1
        self._cached_fps_text: pygame.Surface | None = None
        self._cached_fps_val: int = -1

        self._minimap_bg: pygame.Surface | None = None
        self._minimap_size: int = 120
        self._timer: float = 0

    def bake_minimap(self, game: Game) -> None:
        """Pre-render static minimap geometry (rooms + corridors)."""
        size = self._minimap_size
        self._minimap_bg = pygame.Surface((size, size), pygame.SRCALPHA)
        self._minimap_bg.fill((10, 8, 12, 180))

        gm = game.game_map
        sx = size / gm.width
        sy = size / gm.height

        for room in gm.rooms:
            pts = [(int(v.x * sx), int(v.y * sy)) for v in room.vertices]
            if len(pts) >= 3:
                pygame.draw.polygon(self._minimap_bg, (50, 45, 55), pts)

        for cverts in gm.corridors:
            pts = [(int(v.x * sx), int(v.y * sy)) for v in cverts]
            if len(pts) >= 3:
                pygame.draw.polygon(self._minimap_bg, (50, 45, 55), pts)

        # 1px border
        pygame.draw.rect(self._minimap_bg, (80, 70, 80), (0, 0, size, size), 1)

    def draw(self, window: pygame.Surface, game: Game) -> None:
        dt = game.clock.get_time() * 0.001
        self._timer += dt

        self._draw_health(window, game)
        self._draw_speed_buff(window, game)
        self._draw_portal_indicators(window, game)
        self._draw_minimap(window, game)
        self._draw_crosshair(window)
        self._draw_fps(window, game)

    def _draw_health(self, window: pygame.Surface, game: Game) -> None:
        x, y = 8, 8
        hp = game.player.health
        max_hp = game.player.max_health

        # Label
        window.blit(self._label_hp, (x, y))

        # Bar background + fill (vertically centered with text)
        bar_x = x + 28
        bar_w, bar_h = 100, 8
        bar_y = y + 4
        pygame.draw.rect(window, (40, 20, 20), (bar_x, bar_y, bar_w, bar_h))
        fill_w = max(0, int(bar_w * hp / max_hp))
        fill_color = (220, 50, 50) if hp < 30 else (180, 40, 40)
        if fill_w > 0:
            pygame.draw.rect(window, fill_color, (bar_x, bar_y, fill_w, bar_h))
        pygame.draw.rect(window, (80, 30, 30), (bar_x, bar_y, bar_w, bar_h), 1)

        # Numeric readout (cached)
        if hp != self._cached_hp_val:
            self._cached_hp_val = hp
            self._cached_hp_text = self._font_sm.render(
                str(hp), False, (200, 200, 200)
            )
        assert self._cached_hp_text is not None
        window.blit(self._cached_hp_text, (bar_x + bar_w + 6, y))

    def _draw_speed_buff(self, window: pygame.Surface, game: Game) -> None:
        if game.speed_buff_timer <= 0:
            return

        x, y = 8, 28
        window.blit(self._label_spd, (x, y))

        bar_x = x + 36
        bar_w, bar_h = 60, 6
        bar_y = y + 5
        fill_pct = game.speed_buff_timer / 5.0
        fill_w = max(0, int(bar_w * fill_pct))

        pulse = 0.5 + 0.5 * math.sin(self._timer * 8)
        r = int(180 + 40 * pulse)
        g = int(160 + 40 * pulse)
        color = (r, g, 40)

        pygame.draw.rect(window, (30, 28, 10), (bar_x, bar_y, bar_w, bar_h))
        if fill_w > 0:
            pygame.draw.rect(window, color, (bar_x, bar_y, fill_w, bar_h))

        countdown = self._font_sm.render(
            f"{game.speed_buff_timer:.1f}", False, (220, 200, 40)
        )
        window.blit(countdown, (bar_x + bar_w + 6, y))

    def _draw_portal_indicators(self, window: pygame.Surface, game: Game) -> None:
        y = 692
        portal_q = game.portals[0]
        portal_e = game.portals[1]

        # Q portal
        x = 8
        window.blit(self._label_q, (x, y))
        q_cx, q_cy = x + 26, y + 8
        q_color = (255, 127, 0) if portal_q else (60, 60, 60)
        pygame.draw.circle(window, q_color, (q_cx, q_cy), 5)

        # E portal
        x2 = 56
        window.blit(self._label_e, (x2, y))
        e_cx, e_cy = x2 + 26, y + 8
        e_color = (41, 174, 255) if portal_e else (60, 60, 60)
        pygame.draw.circle(window, e_color, (e_cx, e_cy), 5)

        # Connecting line when both active
        if portal_q and portal_e:
            pygame.draw.line(
                window, (80, 80, 80), (q_cx + 6, q_cy), (e_cx - 6, e_cy), 1
            )

    def _draw_minimap(self, window: pygame.Surface, game: Game) -> None:
        if self._minimap_bg is None:
            self.bake_minimap(game)
        assert self._minimap_bg is not None

        size = self._minimap_size
        mx = int(window.get_width()) - size - 8
        my = 8

        window.blit(self._minimap_bg, (mx, my))

        # Scale factors
        gm = game.game_map
        sx = size / gm.width
        sy = size / gm.height

        # Player dot
        px = mx + int(game.player.pos.x * sx)
        py = my + int(game.player.pos.y * sy)
        pygame.draw.circle(window, (0, 200, 0), (px, py), 2)

        # Portal dots
        if game.portals[0]:
            ox = mx + int(game.portals[0].pos.x * sx)
            oy = my + int(game.portals[0].pos.y * sy)
            pygame.draw.circle(window, (255, 127, 0), (ox, oy), 2)
        if game.portals[1]:
            bx = mx + int(game.portals[1].pos.x * sx)
            by = my + int(game.portals[1].pos.y * sy)
            pygame.draw.circle(window, (41, 174, 255), (bx, by), 2)

    def _draw_crosshair(self, window: pygame.Surface) -> None:
        mx, my = pygame.mouse.get_pos()
        color = (150, 150, 150)
        gap = 3
        arm = 5
        # Horizontal arms
        pygame.draw.line(window, color, (mx - gap - arm, my), (mx - gap, my), 1)
        pygame.draw.line(window, color, (mx + gap, my), (mx + gap + arm, my), 1)
        # Vertical arms
        pygame.draw.line(window, color, (mx, my - gap - arm), (mx, my - gap), 1)
        pygame.draw.line(window, color, (mx, my + gap), (mx, my + gap + arm), 1)

    def _draw_fps(self, window: pygame.Surface, game: Game) -> None:
        fps = int(game.clock.get_fps())
        if fps != self._cached_fps_val:
            self._cached_fps_val = fps
            self._cached_fps_text = self._font_sm.render(
                str(fps), False, (80, 80, 80)
            )
        assert self._cached_fps_text is not None
        fw = self._cached_fps_text.get_width()
        window.blit(
            self._cached_fps_text,
            (int(window.get_width()) - fw - 8, 696),
        )
