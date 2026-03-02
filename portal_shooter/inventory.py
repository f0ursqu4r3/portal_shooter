from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from portal_shooter.entities.pickup import PickupKind, _COLORS
from portal_shooter.weapons import WEAPON_STATS, WeaponKind

if TYPE_CHECKING:
    from portal_shooter.entities.pickup import Pickup

SLOT_COUNT = 20
MAX_STACK = 16
_STACKABLE = {PickupKind.HEALTH, PickupKind.SPEED, PickupKind.AMMO}


@dataclass
class InventoryItem:
    kind: PickupKind
    weapon_kind: WeaponKind | None
    color: tuple[int, int, int]
    quantity: int = 1

    @property
    def stackable(self) -> bool:
        return self.kind in _STACKABLE

    def matches(self, other: InventoryItem) -> bool:
        return self.kind == other.kind and self.weapon_kind == other.weapon_kind

    @staticmethod
    def from_pickup(pickup: Pickup) -> InventoryItem:
        if pickup.weapon_kind is not None and pickup.kind in (
            PickupKind.WEAPON, PickupKind.AMMO
        ):
            color = WEAPON_STATS[pickup.weapon_kind].color
        else:
            color = _COLORS[pickup.kind]
        return InventoryItem(
            kind=pickup.kind,
            weapon_kind=pickup.weapon_kind,
            color=color,
            quantity=pickup.quantity,
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
        )

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
