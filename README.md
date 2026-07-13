# Legend of Shapes

A small top-down action RPG built with Python and Pygame. Explore a village,
talk to NPCs, buy supplies, complete a slime quest, clear dungeon rooms, and
defeat the dungeon boss.

The village also has friendly dinosaur residents, including Linda the pink
dinosaur shopkeeper, while tougher crocodile enemies patrol the dungeon side
rooms.

The current build loops a synthesized test arrangement of the public-domain
folk melody "Korobeiniki" in the overworld. Entering any dungeon map switches
to an original ominous castle chiptune, while entering the boss chamber starts
a separate high-energy boss theme. The overworld music returns when the player
leaves the dungeon. Music playback is managed by `engine/audio.py` and fails
silently when an audio device is unavailable.

## Setup

Python 3.9 or newer is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

For development and tests:

```bash
python -m pip install -r requirements-dev.txt
pytest -q
```

The tests use Pygame's dummy video driver and do not open a game window.

## Controls

- `W`, `A`, `S`, `D`: move
- `Ctrl`: sprint while moving
- `Space`: attack
- `1`, `2`, `3`: equip sword, bow, or gun outside shops
- `E`: talk or advance dialogue
- `1` through `9`: buy the numbered item while a shop is open
- `Y`, `N`: accept or decline a quest
- `Esc`: close dialogue or quit
- `R`: restart after defeat

## Weapons

The current development build starts with a Rusty Sword, Worn Bow, Old Pistol,
and 50 arrows for testing. Set `UNLOCK_ALL_WEAPONS_FOR_TESTING = False` in
`config.py` to restore normal progression, where the player starts with only
the Rusty Sword and buys the bow and gun from Linda.

- Swords make a directional melee swing and never use ammunition.
- Bows fire arrows. Arrows are limited and sold by Linda in packs of 10.
- Guns fire short-range bullets with unlimited ammunition.
- Every weapon has three tiers. Upgrades increase damage and improve attack
  speed; ranged upgrades also increase projectile speed and range.
- Locked weapons cannot be equipped. The HUD shows the current weapon, tier,
  and remaining arrows when the bow is selected.

Enemy weaknesses matter:

- Slimes are immune to arrows and bullets; use a sword.
- Crocodiles are immune to bullets but are defeated instantly by arrows.
- Swords still deal normal damage to crocodiles.
- Bosses inherit their creature archetype's combat rules. The current big
  slime boss is immune to both ranged weapons and must be fought with a sword.
- Boss fights display a wide named health bar. A sword swing can damage a boss
  only once, preventing frame-by-frame multi-hits from deleting its health.
- The Big Slime fires an aimed fireball every 5 seconds and summons a regular
  slime every 10 seconds. Fireballs collide with dungeon terrain and damage the
  player on contact.
- Boss fights have a persistent 10-minute countdown. Leaving the chamber does
  not reset or pause it; reaching zero ends the run with a time-out.

## Project structure

- `engine/`: game loop, input, camera, and scene management
- `game/`: maps, world state, entities, combat, NPCs, shops, and quests
- `scenes/`: top-level game orchestration and presentation
- `tests/`: headless regression tests for gameplay logic
- `main.py`: application entry point

## Map symbols

Maps are defined as fixed-width ASCII layouts in `game/maps.py`.

- `T`: overworld tree/wall
- `G`: grass
- `P`: path
- `W`: water
- `X`: solid town building
- `D`: locked regular door
- `S`: dungeon floor
- `#`: dungeon wall
- `L`: solid lava
- `<`, `>`: map transition
- `1`, `2`: regular dungeon-room doors
- `B`: boss or boss door, depending on the map
- `@`: player start
- `E`: enemy
- `C`: crocodile enemy
- `H`: heart pickup
- `R`: rupee pickup
- `K`: key pickup

Transition destination tiles are declared separately in each `MapDefinition`.
This keeps player spawn positions deterministic and outside transition triggers.

## World-state behavior

Each map has a persistent `MapState`. Defeated enemies, collected pickups,
opened regular doors, and the boss-door unlock survive map transitions. Regular
keys are consumed only when they open a previously closed door.

The overworld starts without slimes. Accepting Elder Elm's cleanup quest spawns
the quest targets in the southern fields, and they are spawned only once.
Willow Town contains no loose keys, rupees, or locked overworld doors; supplies
come from its shopkeepers instead.

Defeating the dungeon boss starts the final cutscene. An angelic woman thanks
the hero and presents the diamond-shaped Azure Crystal before the game remains
on its final `THE END` screen.
