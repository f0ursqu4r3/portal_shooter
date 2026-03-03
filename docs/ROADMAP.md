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
- [x] HUD (health, ammo, weapon, armor bar, dash cooldown, floor counter, key indicator)
- [x] Inventory (20 slots, stacking up to 16, right-click split, drag-drop, drop-to-world)
- [x] Pickups: Health, Speed buff, Typed ammo, Weapons, Armor, Grenades, Keys
- [x] F-key proximity pickup with world-space tooltip
- [x] F-key to use hovered inventory item
- [x] Camera follow with screen shake
- [x] Minimap with player, portal, enemy, and exit door dots
- [x] **Enemies**
  - Melee rusher: pathfinds toward player, deals contact damage, retreats after hit
  - Ranged enemy: maintains distance, fires projectiles, strafes in range
  - AI state machine: idle, roaming, alert, pursuing, attacking, fleeing, dead
  - Sight-based awareness: enemies must see the player (LOS + range) to pursue
  - Sound-based alerting: gunfire/explosions propagate through walls and portals, alerting nearby enemies to investigate
  - Enemies traverse portals
  - Spawn per room with difficulty scaling
  - Drop ammo/health on death
- [x] **Level progression**
  - Key item spawns in farthest room, exit door in second-farthest
  - Completing a floor regenerates the map with harder params (more enemies, higher health/speed)
  - Floor counter on HUD + key indicator
- [x] **Grenades / throwables**
  - Thrown toward cursor (G key), bounces off walls, area damage after 2s fuse
  - Can be thrown through portals
  - Inventory slot item, stackable
  - Explosion particle effect (two-layer burst)
- [x] **Dash / dodge roll**
  - Shift to dash in movement direction
  - Short i-frames during dash
  - Cooldown timer (0.6s), cooldown bar on HUD
- [x] **Armor / shield pickup**
  - Absorbs damage before health (centralized damage model)
  - Blue bar on HUD when armor > 0
- [x] **Pathfinding**
  - Room-graph BFS for inter-room navigation
  - Line-of-sight raycasting via wall grid
  - Feeler-ray wall avoidance steering

## Planned

### Tier 3 — Environment

- [x] **Destructible crates**
  - Breakable box obstacles scattered in rooms (1-3 per large room)
  - Bullets and grenades damage crates; destroyed crates remove their walls
  - Visual: wooden crate with cross pattern, darkens as damaged, particle burst on break
  - Collision system returns hit wall identity for targeted damage

- [x] **Doors and switches**
  - Doors placed across corridors as blocking wall segments
  - Pressure-plate switches on the floor near doors
  - Walking onto a switch permanently opens the linked door
  - Minimap shows unactivated switch positions (orange dots)

### Tier 4 — Polish

- [x] **Muzzle flash** — bright glow at gun tip, 1-2 frame duration, color matches weapon
- [x] **Wall impact particles** — spark burst where bullets hit walls
- [x] **Damage numbers** — float upward from hit location, fade out
- [x] **Death screen** — slow-mo + "GAME OVER" overlay, R to restart, shows floor reached
- [x] **Pause menu** — ESC toggles pause, Q to quit while paused
- [x] **Sound variety** — play_random selects from available variants (e.g. Ricochet1/Ricochet2)
- [ ] **Blood decals** — player emitter particles stick to floor surface
