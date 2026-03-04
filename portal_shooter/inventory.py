from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from portal_shooter.entities.pickup import PickupKind, _COLORS
from portal_shooter.weapons import AMMO_COLORS, WEAPON_STATS, AmmoType, WeaponKind

if TYPE_CHECKING:
    from portal_shooter.entities.pickup import Pickup

SLOT_COUNT = 20
MAX_STACK = 16
_STACKABLE = {PickupKind.HEALTH, PickupKind.SPEED, PickupKind.AMMO, PickupKind.ARMOR, PickupKind.GRENADE}


@dataclass
class InventoryItem:
    kind: PickupKind
    weapon_kind: WeaponKind | None
    color: tuple[int, int, int]
    quantity: int = 1
    ammo_type: AmmoType | None = None

    @property
    def stackable(self) -> bool:
        return self.kind in _STACKABLE

    def matches(self, other: InventoryItem) -> bool:
        if self.kind != other.kind:
            return False
        if self.kind == PickupKind.AMMO:
            return self.ammo_type == other.ammo_type
        return self.weapon_kind == other.weapon_kind

    @staticmethod
    def from_pickup(pickup: Pickup) -> InventoryItem:
        if pickup.kind == PickupKind.AMMO and pickup.ammo_type is not None:
            color = AMMO_COLORS[pickup.ammo_type]
        elif pickup.weapon_kind is not None and pickup.kind == PickupKind.WEAPON:
            color = WEAPON_STATS[pickup.weapon_kind].color
        else:
            color = _COLORS[pickup.kind]
        return InventoryItem(
            kind=pickup.kind,
            weapon_kind=pickup.weapon_kind,
            color=color,
            quantity=pickup.quantity,
            ammo_type=pickup.ammo_type,
        )


class Inventory:
    __slots__ = ["slots"]

    def __init__(self) -> None:
        self.slots: list[InventoryItem | None] = [None] * SLOT_COUNT

    @property
    def is_full(self) -> bool:
        return all(s is not None for s in self.slots)

    def first_empty(self) -> int | None:
        for i, s in enumerate(self.slots):
            if s is None:
                return i
        return None

    def add(self, item: InventoryItem) -> bool:
        # Try stacking onto an existing matching slot first
        if item.stackable:
            for i, s in enumerate(self.slots):
                if s is not None and s.stackable and s.matches(item):
                    space = MAX_STACK - s.quantity
                    if space >= item.quantity:
                        s.quantity += item.quantity
                        return True
                    elif space > 0:
                        s.quantity = MAX_STACK
                        item.quantity -= space
                        # remaining quantity falls through to empty slot

        # Fall back to empty slot
        idx = self.first_empty()
        if idx is None:
            return False
        self.slots[idx] = item
        return True

    def remove(self, index: int) -> InventoryItem | None:
        item = self.slots[index]
        self.slots[index] = None
        return item

    def remove_one(self, index: int) -> bool:
        item = self.slots[index]
        if item is None:
            return False
        item.quantity -= 1
        if item.quantity <= 0:
            self.slots[index] = None
        return True

    def split_stack(self, index: int) -> InventoryItem | None:
        item = self.slots[index]
        if item is None or item.quantity < 2:
            return None
        split_qty = math.ceil(item.quantity / 2)
        item.quantity -= split_qty
        return InventoryItem(
            kind=item.kind,
            weapon_kind=item.weapon_kind,
            color=item.color,
            quantity=split_qty,
            ammo_type=item.ammo_type,
        )

    def merge_stacks(self) -> None:
        """Merge all matching stackable items into as few stacks as possible."""
        # Collect all items grouped by match key
        groups: dict[tuple[str, ...], list[int]] = {}
        for i, slot in enumerate(self.slots):
            if slot is None or not slot.stackable:
                continue
            if slot.kind == PickupKind.AMMO:
                key = (slot.kind.value, str(slot.ammo_type))
            else:
                key = (slot.kind.value, str(slot.weapon_kind))
            groups.setdefault(key, []).append(i)

        for indices in groups.values():
            if len(indices) < 2:
                continue
            # Sum total quantity
            total = 0
            for i in indices:
                item = self.slots[i]
                assert item is not None
                total += item.quantity
            # Refill from first slot onward
            template = self.slots[indices[0]]
            assert template is not None
            for i in indices:
                if total <= 0:
                    self.slots[i] = None
                else:
                    item = self.slots[i]
                    assert item is not None
                    fill = min(total, MAX_STACK)
                    item.quantity = fill
                    total -= fill
            # Clear any leftover empty slots
            for i in indices:
                item = self.slots[i]
                if item is not None and item.quantity <= 0:
                    self.slots[i] = None

    def arrange(self) -> None:
        """Auto-arrange inventory: merge stacks first, then sort by kind."""
        self.merge_stacks()
        # Collect non-None items
        items = [s for s in self.slots if s is not None]
        # Sort order: weapons first, then ammo, then consumables, then rest
        _kind_order = {
            PickupKind.WEAPON: 0,
            PickupKind.AMMO: 1,
            PickupKind.HEALTH: 2,
            PickupKind.ARMOR: 3,
            PickupKind.SPEED: 4,
            PickupKind.GRENADE: 5,
            PickupKind.KEY: 6,
        }

        def sort_key(item: InventoryItem) -> tuple[int, int, int]:
            primary = _kind_order.get(item.kind, 99)
            # Secondary: weapon_kind int value or ammo_type ordinal
            if item.weapon_kind is not None:
                secondary = int(item.weapon_kind)
            elif item.ammo_type is not None:
                secondary = list(AmmoType).index(item.ammo_type)
            else:
                secondary = 0
            return (primary, secondary, -item.quantity)

        items.sort(key=sort_key)
        self.slots = items + [None] * (SLOT_COUNT - len(items))

    def swap(self, a: int, b: int) -> None:
        item_a = self.slots[a]
        item_b = self.slots[b]
        # Merge stacks if both items match and are stackable
        if (
            item_a is not None
            and item_b is not None
            and item_a.stackable
            and item_b.stackable
            and item_a.matches(item_b)
        ):
            space = MAX_STACK - item_b.quantity
            if space >= item_a.quantity:
                item_b.quantity += item_a.quantity
                self.slots[a] = None
            else:
                item_b.quantity = MAX_STACK
                item_a.quantity -= space
            return
        self.slots[a], self.slots[b] = self.slots[b], self.slots[a]
