from __future__ import annotations

from dataclasses import dataclass, field

from game import constants as C
from game.entities import Enemy, Pickup, PickupType, create_boss, create_croc
from game.world import GameWorld


@dataclass
class MapState:
    enemies: list[Enemy] = field(default_factory=list)
    pickups: list[Pickup] = field(default_factory=list)
    boss_door_unlocked: bool = False
    opened_doors: set[tuple[int, int]] = field(default_factory=set)
    defeated_enemies: int = 0
    boss_time_remaining: float | None = None
    quest_enemies_spawned: bool = False

    def is_cleared(self) -> bool:
        return not self.enemies or all(not enemy.alive for enemy in self.enemies)

    def compact(self) -> None:
        defeated_now = sum(1 for enemy in self.enemies if not enemy.alive)
        self.defeated_enemies += defeated_now
        self.enemies = [enemy for enemy in self.enemies if enemy.alive]
        self.pickups = [pickup for pickup in self.pickups if pickup.alive]


def build_map_state(
    world: GameWorld,
    *,
    spawn_regular_enemies: bool = True,
) -> MapState:
    enemies = (
        [Enemy(pos) for pos in world.spawn.enemy_positions]
        if spawn_regular_enemies
        else []
    )
    enemies.extend(create_croc(pos) for pos in world.spawn.croc_positions)
    for pos in world.spawn.boss_positions:
        enemies.append(create_boss(pos))

    pickups: list[Pickup] = []
    for pos in world.spawn.heart_positions:
        pickups.append(Pickup(pos, PickupType.HEART))
    for pos in world.spawn.rupee_positions:
        pickups.append(Pickup(pos, PickupType.RUPEE))
    for pos in world.spawn.key_positions:
        pickups.append(Pickup(pos, PickupType.KEY))

    boss_time_remaining = C.BOSS_TIME_LIMIT if world.spawn.boss_positions else None
    return MapState(
        enemies=enemies,
        pickups=pickups,
        boss_time_remaining=boss_time_remaining,
    )
