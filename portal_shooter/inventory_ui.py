from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame
from pyglm import glm

from portal_shooter.entities.pickup import Pickup, PickupKind
from portal_shooter.inventory import MAX_STACK, Inventory, InventoryItem
from portal_shooter.weapons import AMMO_NAMES, MELEE_WEAPONS, WEAPON_STATS, WeaponKind

if TYPE_CHECKING:
    from portal_shooter.game import Game

# Layout constants (window-space)
PANEL_WIDTH = 200
PANEL_X = 1080  # 1280 - 200
COLS = 4
ROWS = 5
SLOT_SIZE = 40
SLOT_PAD = 4
GRID_X = PANEL_X + 12
GRID_Y = 48  # below title

# Button layout below the grid
_BTN_Y = GRID_Y + ROWS * (SLOT_SIZE + SLOT_PAD) + 8
_BTN_W = 88
_BTN_H = 22
_BTN_PAD = 8
_BTN_MERGE_X = GRID_X
_BTN_ARRANGE_X = GRID_X + _BTN_W + _BTN_PAD

_WEAPON_ABBREVS: dict[WeaponKind, str] = {
    WeaponKind.PISTOL: "PST",
    WeaponKind.SHOTGUN: "SHG",
    WeaponKind.SMG: "SMG",
    WeaponKind.RIFLE: "RFL",
    WeaponKind.MACHINE_GUN: "MG",
    WeaponKind.SNIPER_RIFLE: "SNP",
    WeaponKind.GRENADE_LAUNCHER: "GL",
    WeaponKind.ROCKET_LAUNCHER: "RL",
    WeaponKind.KNIFE: "KNF",
    WeaponKind.SWORD: "SWD",
    WeaponKind.AXE: "AXE",
}


class InventoryUI:
    __slots__ = [
        "_open",
        "_font",
        "_font_sm",
        "_font_qty",
        "_panel_bg",
        "_title_surf",
        "_drag_from",
        "_drag_item",
        "_drag_offset",
        "_drag_is_split",
        "_hover_slot",
        "_btn_merge_rect",
        "_btn_arrange_rect",
        "_btn_merge_label",
        "_btn_arrange_label",
    ]

    def __init__(self) -> None:
        self._open: bool = False
        self._font: pygame.font.Font = pygame.font.Font("assets/fonts/homespun.ttf", 16)
        self._font_sm: pygame.font.Font = pygame.font.Font(
            "assets/fonts/homespun.ttf", 12
        )
        self._font_qty: pygame.font.Font = pygame.font.Font(
            "assets/fonts/homespun.ttf", 10
        )

        # Pre-render panel background
        self._panel_bg: pygame.Surface = pygame.Surface(
            (PANEL_WIDTH, 720), pygame.SRCALPHA
        )
        self._panel_bg.fill((20, 18, 24, 220))
        pygame.draw.line(self._panel_bg, (60, 55, 70), (0, 0), (0, 720), 1)

        # Title
        self._title_surf: pygame.Surface = self._font.render(
            "INVENTORY", False, (180, 175, 190)
        )

        # Drag state
        self._drag_from: int | None = None
        self._drag_item: InventoryItem | None = None
        self._drag_offset: tuple[int, int] = (0, 0)
        self._drag_is_split: bool = False

        # Hover
        self._hover_slot: int | None = None

        # Buttons
        self._btn_merge_rect: pygame.Rect = pygame.Rect(
            _BTN_MERGE_X, _BTN_Y, _BTN_W, _BTN_H
        )
        self._btn_arrange_rect: pygame.Rect = pygame.Rect(
            _BTN_ARRANGE_X, _BTN_Y, _BTN_W, _BTN_H
        )
        self._btn_merge_label: pygame.Surface = self._font_sm.render(
            "Merge", False, (180, 175, 190)
        )
        self._btn_arrange_label: pygame.Surface = self._font_sm.render(
            "Arrange", False, (180, 175, 190)
        )

    @property
    def is_open(self) -> bool:
        return self._open

    def toggle(self) -> None:
        self._open = not self._open
        if not self._open:
            self._cancel_drag()

    def _cancel_drag(self) -> None:
        self._drag_from = None
        self._drag_item = None
        self._drag_is_split = False

    def slot_rect(self, index: int) -> pygame.Rect:
        col = index % COLS
        row = index // COLS
        x = GRID_X + col * (SLOT_SIZE + SLOT_PAD)
        y = GRID_Y + row * (SLOT_SIZE + SLOT_PAD)
        return pygame.Rect(x, y, SLOT_SIZE, SLOT_SIZE)

    def slot_at_pos(self, mx: int, my: int) -> int | None:
        for i in range(ROWS * COLS):
            if self.slot_rect(i).collidepoint(mx, my):
                return i
        return None

    def is_over_panel(self, mx: int, my: int) -> bool:
        return mx >= PANEL_X

    def handle_key(self, key: int, game: Game) -> bool:
        """Handle a key press while the inventory is open. Returns True if consumed."""
        if not self._open:
            return False
        if key == pygame.K_e:
            mx, my = pygame.mouse.get_pos()
            slot = self.slot_at_pos(mx, my)
            if slot is not None and game.inventory.slots[slot] is not None:
                self._use_item(slot, game)
                return True
        return False

    def handle_event(self, event: pygame.event.Event, game: Game) -> bool:
        if not self._open:
            return False

        mx, my = event.pos
        inv = game.inventory

        # Mouse up outside panel while dragging → drop item
        if not self.is_over_panel(mx, my):
            if event.type == pygame.MOUSEBUTTONUP and self._drag_from is not None:
                if self._drag_is_split:
                    # Drop the split half
                    if self._drag_item is not None:
                        self._drop_item(self._drag_item, game)
                else:
                    # Drop the full stack from the slot
                    item = inv.remove(self._drag_from)
                    if item is not None:
                        self._drop_item(item, game)
                self._cancel_drag()
                return True
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Check buttons first
            if self._btn_merge_rect.collidepoint(mx, my):
                inv.merge_stacks()
                return True
            if self._btn_arrange_rect.collidepoint(mx, my):
                inv.arrange()
                return True
            slot = self.slot_at_pos(mx, my)
            if slot is not None and inv.slots[slot] is not None:
                self._drag_from = slot
                self._drag_item = inv.slots[slot]
                self._drag_is_split = False
                rect = self.slot_rect(slot)
                self._drag_offset = (mx - rect.x, my - rect.y)
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            # Right-click: split stack
            slot = self.slot_at_pos(mx, my)
            if slot is not None and inv.slots[slot] is not None:
                split_half = inv.split_stack(slot)
                if split_half is not None:
                    self._drag_from = slot
                    self._drag_item = split_half
                    self._drag_is_split = True
                    rect = self.slot_rect(slot)
                    self._drag_offset = (mx - rect.x, my - rect.y)
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button in (1, 3):
            if self._drag_from is not None:
                target = self.slot_at_pos(mx, my)
                if self._drag_is_split:
                    self._finish_split_drag(target, inv)
                else:
                    self._finish_normal_drag(target, game)
                self._cancel_drag()
            return True

        return True  # consume all mouse events over panel

    def _finish_normal_drag(self, target: int | None, game: Game) -> None:
        assert self._drag_from is not None
        inv = game.inventory
        if target is not None and target != self._drag_from:
            inv.swap(self._drag_from, target)
        elif target == self._drag_from:
            self._use_item(self._drag_from, game)
        # else: outside grid but over panel → snap back (no-op)

    def _finish_split_drag(self, target: int | None, inv: Inventory) -> None:
        assert self._drag_from is not None
        assert self._drag_item is not None
        if target is not None and target != self._drag_from:
            existing = inv.slots[target]
            if existing is None:
                # Place split half in empty slot
                inv.slots[target] = self._drag_item
            elif (
                existing.stackable
                and existing.matches(self._drag_item)
                and existing.quantity + self._drag_item.quantity <= MAX_STACK
            ):
                # Merge split half into matching stack
                existing.quantity += self._drag_item.quantity
            else:
                # Can't place — return to source
                self._return_split_to_source(inv)
        else:
            # Dropped on same slot or outside grid → return to source
            self._return_split_to_source(inv)

    def _return_split_to_source(self, inv: Inventory) -> None:
        assert self._drag_from is not None
        assert self._drag_item is not None
        source = inv.slots[self._drag_from]
        if source is not None:
            source.quantity += self._drag_item.quantity
        else:
            inv.slots[self._drag_from] = self._drag_item

    def _drop_item(self, item: InventoryItem, game: Game) -> None:
        # Create a Pickup 20px toward cursor from player
        player_pos = game.player.pos
        cursor_world = game.mpos_world
        direction = cursor_world - player_pos
        length = math.sqrt(direction.x**2 + direction.y**2)
        if length > 0:
            direction = direction / length
        else:
            direction = glm.vec2(1, 0)
        drop_pos = glm.vec2(player_pos + direction * 20)
        pickup = Pickup(
            drop_pos,
            item.kind,
            weapon_kind=item.weapon_kind,
            quantity=item.quantity,
            ammo_type=item.ammo_type,
        )
        game.pickups.append(pickup)

    def _use_item(self, slot_index: int, game: Game) -> None:
        item = game.inventory.slots[slot_index]
        if item is None:
            return

        if item.kind == PickupKind.WEAPON:
            wk = item.weapon_kind
            if wk is not None:
                game.owned_weapons.add(wk)
                stats = WEAPON_STATS[wk]
                game.ammo[wk] = stats.magazine_size if stats.magazine_size > 0 else 0
                game.current_weapon = wk
                game._reloading = False
                game.inventory.remove(slot_index)

        elif item.kind == PickupKind.HEALTH:
            if game.player.health < game.player.max_health:
                game.player.health = min(
                    game.player.health + 25, game.player.max_health
                )
                game.inventory.remove_one(slot_index)

        elif item.kind == PickupKind.SPEED:
            game.speed_buff_timer = 5.0
            game.inventory.remove_one(slot_index)

        elif item.kind == PickupKind.ARMOR:
            if game.player.armor < game.player.max_armor:
                game.player.armor = min(game.player.armor + 25, game.player.max_armor)
                game.inventory.remove_one(slot_index)

    def draw(self, window: pygame.Surface, game: Game) -> None:
        if not self._open:
            return

        inv = game.inventory
        mx, my = pygame.mouse.get_pos()

        # Panel background
        window.blit(self._panel_bg, (PANEL_X, 0))

        # Title
        tx = PANEL_X + (PANEL_WIDTH - self._title_surf.get_width()) // 2
        window.blit(self._title_surf, (tx, 16))

        # Slot grid
        hover = self.slot_at_pos(mx, my)
        for i in range(ROWS * COLS):
            rect = self.slot_rect(i)
            # Slot background
            if i == hover and self._drag_from is None:
                bg_color = (50, 45, 55)
            elif self._drag_from is not None and i == hover:
                bg_color = (60, 55, 70)
            else:
                bg_color = (30, 28, 35)
            pygame.draw.rect(window, bg_color, rect)
            pygame.draw.rect(window, (55, 50, 60), rect, 1)

            # Item icon (skip if being dragged and not a split drag)
            item = inv.slots[i]
            if item is not None and (i != self._drag_from or self._drag_is_split):
                self._draw_item_icon(window, item, rect)
                if item.quantity > 1:
                    self._draw_quantity(window, item.quantity, rect)

        # Dragged item at cursor
        if self._drag_item is not None:
            drag_rect = pygame.Rect(
                mx - self._drag_offset[0],
                my - self._drag_offset[1],
                SLOT_SIZE,
                SLOT_SIZE,
            )
            self._draw_item_icon(window, self._drag_item, drag_rect)
            if self._drag_item.quantity > 1:
                self._draw_quantity(window, self._drag_item.quantity, drag_rect)

        # Buttons
        self._draw_button(window, self._btn_merge_rect, self._btn_merge_label, mx, my)
        self._draw_button(window, self._btn_arrange_rect, self._btn_arrange_label, mx, my)

        # Tooltip on hover
        if (
            hover is not None
            and inv.slots[hover] is not None
            and self._drag_from is None
        ):
            hover_item = inv.slots[hover]
            assert hover_item is not None
            self._draw_tooltip(window, hover_item, mx, my)

    def _draw_button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: pygame.Surface,
        mx: int,
        my: int,
    ) -> None:
        hovered = rect.collidepoint(mx, my)
        bg = (50, 45, 55) if hovered else (35, 32, 40)
        border = (80, 75, 90) if hovered else (55, 50, 60)
        pygame.draw.rect(surface, bg, rect)
        pygame.draw.rect(surface, border, rect, 1)
        lx = rect.x + (rect.width - label.get_width()) // 2
        ly = rect.y + (rect.height - label.get_height()) // 2
        surface.blit(label, (lx, ly))

    def _draw_quantity(
        self, surface: pygame.Surface, quantity: int, rect: pygame.Rect
    ) -> None:
        text = self._font_qty.render(str(quantity), False, (255, 255, 255))
        # Bottom-right corner of slot
        x = rect.x + rect.width - text.get_width() - 2
        y = rect.y + rect.height - text.get_height() - 1
        # Dark shadow for readability
        shadow = self._font_qty.render(str(quantity), False, (0, 0, 0))
        surface.blit(shadow, (x + 1, y + 1))
        surface.blit(text, (x, y))

    def _draw_item_icon(
        self, surface: pygame.Surface, item: InventoryItem, rect: pygame.Rect
    ) -> None:
        cx = rect.x + rect.width // 2
        cy = rect.y + rect.height // 2
        color = item.color

        if item.kind == PickupKind.HEALTH:
            # Green cross
            pygame.draw.line(surface, color, (cx - 10, cy), (cx + 10, cy), 3)
            pygame.draw.line(surface, color, (cx, cy - 10), (cx, cy + 10), 3)

        elif item.kind == PickupKind.SPEED:
            # Yellow diamond outline
            d = 10
            pts = [
                (cx, cy - d),
                (cx + d, cy),
                (cx, cy + d),
                (cx - d, cy),
            ]
            pygame.draw.polygon(surface, color, pts, 2)

        elif item.kind == PickupKind.AMMO:
            # Square outline in ammo color
            s = 7
            pygame.draw.rect(surface, color, (cx - s, cy - s, s * 2, s * 2), 2)
            # Ammo type abbreviation below
            if item.ammo_type is not None:
                abbr = AMMO_NAMES.get(item.ammo_type, "???")
                text = self._font_sm.render(abbr, False, color)
                surface.blit(
                    text,
                    (cx - text.get_width() // 2, cy + 10),
                )

        elif item.kind == PickupKind.ARMOR:
            # Shield outline
            d = 8
            pts = [
                (cx - d, cy - d),
                (cx + d, cy - d),
                (cx + d, cy + 2),
                (cx, cy + d),
                (cx - d, cy + 2),
            ]
            pygame.draw.polygon(surface, color, pts, 2)

        elif item.kind == PickupKind.KEY:
            # Key shape
            pygame.draw.circle(surface, color, (cx - 4, cy - 2), 5, 2)
            pygame.draw.line(surface, color, (cx + 1, cy - 2), (cx + 12, cy - 2), 2)
            pygame.draw.line(surface, color, (cx + 8, cy - 2), (cx + 8, cy + 4), 2)
            pygame.draw.line(surface, color, (cx + 11, cy - 2), (cx + 11, cy + 3), 2)

        elif item.kind == PickupKind.GRENADE:
            # Circle + fuse
            pygame.draw.circle(surface, color, (cx, cy + 2), 6, 2)
            pygame.draw.line(surface, color, (cx, cy - 4), (cx + 4, cy - 8), 2)

        elif item.kind == PickupKind.WEAPON:
            if item.weapon_kind is not None and item.weapon_kind in MELEE_WEAPONS:
                # Blade icon: diagonal line
                pygame.draw.line(surface, color, (cx - 8, cy + 8), (cx + 8, cy - 8), 3)
                pygame.draw.line(surface, color, (cx - 8, cy + 8), (cx - 4, cy + 4), 3)
            else:
                # Gun silhouette: barrel + grip
                pygame.draw.line(surface, color, (cx - 12, cy - 2), (cx + 12, cy - 2), 3)
                pygame.draw.line(surface, color, (cx + 4, cy - 2), (cx + 4, cy + 8), 3)
            # Weapon abbreviation
            if item.weapon_kind is not None:
                abbr = _WEAPON_ABBREVS.get(item.weapon_kind, "???")
                text = self._font_sm.render(abbr, False, color)
                surface.blit(
                    text,
                    (cx - text.get_width() // 2, cy + 10),
                )

    def _draw_tooltip(
        self,
        surface: pygame.Surface,
        item: InventoryItem,
        mx: int,
        my: int,
    ) -> None:
        if item.kind == PickupKind.WEAPON and item.weapon_kind is not None:
            name = _WEAPON_ABBREVS.get(item.weapon_kind, "???")
            text = f"Equip {name}"
        elif item.kind == PickupKind.HEALTH:
            text = "Use: +25 HP"
        elif item.kind == PickupKind.SPEED:
            text = "Use: Speed 5s"
        elif item.kind == PickupKind.ARMOR:
            text = "Use: +25 AR"
        elif item.kind == PickupKind.KEY:
            text = "Floor Key"
        elif item.kind == PickupKind.GRENADE:
            text = "Throw: G key"
        elif item.kind == PickupKind.AMMO:
            if item.ammo_type is not None:
                name = AMMO_NAMES.get(item.ammo_type, "???")
                text = f"{name} Reserve"
            else:
                text = "Reserve Ammo"
        else:
            text = "Use"

        if item.quantity > 1:
            text += f" (x{item.quantity})"

        tip = self._font_sm.render(text, False, (200, 200, 200))
        tw, th = tip.get_size()
        pad = 4
        tx = mx - tw - pad * 2 - 4
        ty = my - th - pad * 2 - 4
        # Keep on screen
        if tx < PANEL_X:
            tx = mx + 8
        if ty < 0:
            ty = my + 8
        pygame.draw.rect(surface, (20, 18, 24), (tx, ty, tw + pad * 2, th + pad * 2))
        pygame.draw.rect(surface, (60, 55, 70), (tx, ty, tw + pad * 2, th + pad * 2), 1)
        surface.blit(tip, (tx + pad, ty + pad))
