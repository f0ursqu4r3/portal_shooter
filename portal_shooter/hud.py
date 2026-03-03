from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from portal_shooter.weapons import WEAPON_STATS, WeaponKind

if TYPE_CHECKING:
    from portal_shooter.game import Game


class HUD:
    __slots__ = [
        "_font_sm",
        "_font_md",
        "_label_hp",
        "_label_spd",
        "_label_ar",
        "_label_q",
        "_label_e",
        "_label_floor",
        "_cached_hp_text",
        "_cached_hp_val",
        "_cached_fps_text",
        "_cached_fps_val",
        "_cached_floor_text",
        "_cached_floor_val",
        "_minimap_bg",
        "_minimap_size",
        "_timer",
        "_weapon_labels",
        "_weapon_labels_dim",
        "_weapon_abbrevs",
        "_select_indicator",
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
        self._label_ar: pygame.Surface = self._font_sm.render(
            "AR", False, (100, 140, 200)
        )
        self._label_q: pygame.Surface = self._font_sm.render(
            "Q:", False, (200, 200, 200)
        )
        self._label_e: pygame.Surface = self._font_sm.render(
            "E:", False, (200, 200, 200)
        )
        self._label_floor: pygame.Surface = self._font_sm.render(
            "FL", False, (180, 180, 180)
        )

        # Cached numeric surfaces
        self._cached_hp_text: pygame.Surface | None = None
        self._cached_hp_val: int = -1
        self._cached_fps_text: pygame.Surface | None = None
        self._cached_fps_val: int = -1
        self._cached_floor_text: pygame.Surface | None = None
        self._cached_floor_val: int = -1

        self._minimap_bg: pygame.Surface | None = None
        self._minimap_size: int = 120
        self._timer: float = 0

        # Weapon HUD
        self._weapon_abbrevs: dict[WeaponKind, str] = {
            WeaponKind.PISTOL: "PST",
            WeaponKind.SHOTGUN: "SHG",
            WeaponKind.SMG: "SMG",
            WeaponKind.RIFLE: "RFL",
            WeaponKind.PORTAL_GUN: "PGL",
        }
        self._weapon_labels: dict[WeaponKind, pygame.Surface] = {
            kind: self._font_sm.render(
                abbr, False, WEAPON_STATS[kind].color
            )
            for kind, abbr in self._weapon_abbrevs.items()
        }
        self._weapon_labels_dim: dict[WeaponKind, pygame.Surface] = {
            kind: self._font_sm.render(
                abbr,
                False,
                tuple(c // 3 for c in WEAPON_STATS[kind].color),  # type: ignore[arg-type]
            )
            for kind, abbr in self._weapon_abbrevs.items()
        }
        self._select_indicator: pygame.Surface = self._font_sm.render(
            ">", False, (200, 200, 200)
        )

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
        self._draw_armor(window, game)
        self._draw_dash_cooldown(window, game)
        self._draw_speed_buff(window, game)
        self._draw_floor(window, game)
        self._draw_weapon(window, game)
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

    def _draw_armor(self, window: pygame.Surface, game: Game) -> None:
        if game.player.armor <= 0:
            return
        x, y = 8, 24
        window.blit(self._label_ar, (x, y))

        bar_x = x + 28
        bar_w, bar_h = 100, 6
        bar_y = y + 5
        pygame.draw.rect(window, (20, 30, 50), (bar_x, bar_y, bar_w, bar_h))
        fill_w = max(0, int(bar_w * game.player.armor / game.player.max_armor))
        if fill_w > 0:
            pygame.draw.rect(window, (80, 120, 200), (bar_x, bar_y, fill_w, bar_h))
        pygame.draw.rect(window, (50, 70, 100), (bar_x, bar_y, bar_w, bar_h), 1)

    def _draw_dash_cooldown(self, window: pygame.Surface, game: Game) -> None:
        x, y = 140, 8
        bar_w, bar_h = 30, 4
        bar_y = y + 6
        # Show as a small bar that fills up as cooldown expires
        if game.player.is_dashing:
            pct = 1.0
            color = (200, 200, 255)
        elif game.player.dash_cooldown > 0:
            from portal_shooter.entities.player import DASH_COOLDOWN
            pct = 1.0 - game.player.dash_cooldown / DASH_COOLDOWN
            color = (80, 80, 90)
        else:
            pct = 1.0
            color = (120, 120, 130)
        pygame.draw.rect(window, (30, 30, 35), (x, bar_y, bar_w, bar_h))
        fill_w = max(0, int(bar_w * pct))
        if fill_w > 0:
            pygame.draw.rect(window, color, (x, bar_y, fill_w, bar_h))

    def _draw_floor(self, window: pygame.Surface, game: Game) -> None:
        if not hasattr(game, "level"):
            return
        floor = game.level.floor
        # Top center
        cx = window.get_width() // 2

        if floor != self._cached_floor_val:
            self._cached_floor_val = floor
            self._cached_floor_text = self._font_sm.render(
                f"FL {floor}", False, (180, 180, 180)
            )
        assert self._cached_floor_text is not None
        fw = self._cached_floor_text.get_width()
        window.blit(self._cached_floor_text, (cx - fw // 2, 8))

        # Key indicator
        if game.level.has_key:
            key_surf = self._font_sm.render("KEY", False, (255, 200, 50))
            window.blit(key_surf, (cx - key_surf.get_width() // 2, 26))

    def _draw_speed_buff(self, window: pygame.Surface, game: Game) -> None:
        if game.speed_buff_timer <= 0:
            return

        x, y = 8, 40
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

    def _draw_weapon(self, window: pygame.Surface, game: Game) -> None:
        owned = sorted(game.owned_weapons)
        n = len(owned)
        row_h = 20
        list_bottom = 685  # 7px gap above portal indicators at y=692

        # Anchor index: current weapon sits at index 1 (or 0 if only 1 weapon)
        anchor = min(1, n - 1)
        cur_idx = owned.index(game.current_weapon) if game.current_weapon in owned else 0

        # Rotate list so current weapon is at the anchor position
        rotation = cur_idx - anchor
        rotated: list[WeaponKind] = []
        for i in range(n):
            rotated.append(owned[(i + rotation) % n])

        x = 8
        top_y = list_bottom - n * row_h

        for i, wk in enumerate(rotated):
            y = top_y + i * row_h
            is_selected = wk == game.current_weapon

            if is_selected:
                window.blit(self._select_indicator, (x, y))
                label = self._weapon_labels[wk]
                ammo_color = (200, 200, 200)
            else:
                label = self._weapon_labels_dim[wk]
                ammo_color = (100, 100, 100)

            label_x = x + 14
            window.blit(label, (label_x, y))

            # Ammo text
            stats = WEAPON_STATS[wk]
            if stats.ammo_per_shot == 0:
                ammo_str = "\u221e"
            elif stats.magazine_size > 0:
                reserve = game._count_reserve_ammo(wk)
                # Flash/dim text while reloading current weapon
                if is_selected and game._reloading:
                    pulse = int(self._timer * 6) % 2
                    ammo_color = (120, 120, 120) if pulse else ammo_color
                ammo_str = f"{game.ammo[wk]}|{reserve}"
            else:
                ammo_str = str(game.ammo[wk])

            ammo_surf = self._font_sm.render(ammo_str, False, ammo_color)
            ammo_x = label_x + label.get_width() + 6
            window.blit(ammo_surf, (ammo_x, y))

            # Reload progress bar for selected weapon
            if is_selected and game._reloading and stats.reload_time > 0:
                bar_y = y + row_h - 3
                bar_w = 40
                bar_h = 2
                progress = 1.0 - game._reload_timer / stats.reload_time
                fill_w = max(0, int(bar_w * progress))
                pygame.draw.rect(window, (40, 40, 40), (ammo_x, bar_y, bar_w, bar_h))
                if fill_w > 0:
                    pygame.draw.rect(window, stats.color, (ammo_x, bar_y, fill_w, bar_h))

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

        # Enemy dots
        if hasattr(game, "enemies"):
            for enemy in game.enemies:
                if enemy.alive:
                    ex = mx + int(enemy.pos.x * sx)
                    ey = my + int(enemy.pos.y * sy)
                    pygame.draw.circle(window, (200, 50, 50), (ex, ey), 1)

        # Exit door dot
        if hasattr(game, "exit_door") and game.exit_door is not None:
            dx = mx + int(game.exit_door.pos.x * sx)
            dy = my + int(game.exit_door.pos.y * sy)
            door_color = (60, 220, 80) if game.exit_door.active else (70, 70, 75)
            pygame.draw.circle(window, door_color, (dx, dy), 2)

        # Switch dots
        for switch in game.switches:
            if not switch.activated:
                swx = mx + int(switch.pos.x * sx)
                swy = my + int(switch.pos.y * sy)
                pygame.draw.circle(window, (180, 100, 50), (swx, swy), 1)

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
        if pygame.mouse.get_visible():
            return
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
