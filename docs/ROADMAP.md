# Portals — Roadmap

## Implemented

- [x] Player movement (WASD) with walk sounds
- [x] Portal placement (Q/E) and clearing (Z/X)
- [x] 4 weapon types: Pistol, Shotgun, SMG, Rifle
- [x] Bullet physics with spread, recoil, piercing, ricochets
- [x] Shell casing ejection
- [x] Procedurally generated maps (BSP rooms + corridors + extra connections)
- [x] Fog of war / visibility polygon
- [x] Spatial audio with portal sound propagation
- [x] HUD (health, ammo, weapon)
- [x] Inventory (20 slots, stacking up to 16, right-click split, drag-drop, drop-to-world)
- [x] Pickups: Health, Speed buff, Typed ammo, Weapons
- [x] F-key proximity pickup with world-space tooltip
- [x] F-key to use hovered inventory item
- [x] Camera follow with screen shake

## Planned

### Tier 1 — Core gameplay

- [ ] **Enemies**
  - Melee rusher: pathfinds toward player, deals contact damage
  - Ranged enemy: stops at distance, fires projectiles
  - Enemies traverse portals (reuse existing portal logic on Entity)
  - Spawn per room or wave-based
  - Drop ammo/health on death

- [ ] **Level progression**
  - Key item spawns in a far room, exit door in another
  - Completing a floor regenerates the map with harder params
  - Floor counter on HUD

### Tier 2 — Combat depth

- [ ] **Grenades / throwables**
  - Arc trajectory, bounces off walls, area damage after fuse
  - Can be thrown through portals
  - Inventory slot item, stackable

- [ ] **Dash / dodge roll**
  - Shift to dash in movement direction
  - Short i-frames during dash
  - Cooldown timer (0.5-1s)

- [ ] **Armor / shield pickup**
  - Absorbs damage before health
  - Shown on HUD alongside health

### Tier 3 — Environment

- [ ] **Destructible walls**
  - Marked wall tiles that bullets can break
  - Opens new paths and portal placement spots

- [ ] **Doors and switches**
  - Locked doors requiring key items
  - Pressure plates / switches that open passages

- [ ] **Minimap**
  - Corner overlay showing explored rooms
  - Player position + pickup markers
  - Built from existing room/corridor data

### Tier 4 — Polish

- [ ] **Muzzle flash** — sprite on fire, 1-2 frame duration
- [ ] **Wall impact particles** — sparks where bullets hit (ricochet hook exists)
- [ ] **Blood decals** — player emitter particles stick to floor surface
- [ ] **Damage numbers** — float upward from hit location
- [ ] **Death screen** — slow-mo already works, add restart prompt
- [ ] **Pause menu** — ESC toggles pause instead of quit
- [ ] **Sound variety** — multiple footstep/shot/ricochet samples, random selection
