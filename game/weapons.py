from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

import pygame

import config

if TYPE_CHECKING:
    from game.entities import Enemy
    from game.world import GameWorld


class WeaponType(Enum):
    SWORD = "sword"
    BOW = "bow"
    GUN = "gun"


@dataclass(frozen=True)
class WeaponTier:
    name: str
    damage: int
    cooldown: float
    purchase_cost: int
    projectile_speed: float = 0.0
    projectile_range: float = 0.0


WEAPON_TIERS: dict[WeaponType, tuple[WeaponTier, ...]] = {
    WeaponType.SWORD: (
        WeaponTier("Rusty Sword", damage=1, cooldown=0.35, purchase_cost=0),
        WeaponTier("Iron Sword", damage=2, cooldown=0.30, purchase_cost=20),
        WeaponTier("Crystal Sword", damage=3, cooldown=0.24, purchase_cost=45),
    ),
    WeaponType.BOW: (
        WeaponTier(
            "Worn Bow",
            damage=1,
            cooldown=0.58,
            purchase_cost=18,
            projectile_speed=270,
            projectile_range=350,
        ),
        WeaponTier(
            "Hunter Bow",
            damage=2,
            cooldown=0.46,
            purchase_cost=30,
            projectile_speed=320,
            projectile_range=420,
        ),
        WeaponTier(
            "Royal Bow",
            damage=3,
            cooldown=0.34,
            purchase_cost=50,
            projectile_speed=370,
            projectile_range=500,
        ),
    ),
    WeaponType.GUN: (
        WeaponTier(
            "Old Pistol",
            damage=1,
            cooldown=0.44,
            purchase_cost=30,
            projectile_speed=430,
            projectile_range=150,
        ),
        WeaponTier(
            "Steel Revolver",
            damage=2,
            cooldown=0.32,
            purchase_cost=45,
            projectile_speed=480,
            projectile_range=180,
        ),
        WeaponTier(
            "Arc Cannon",
            damage=3,
            cooldown=0.22,
            purchase_cost=70,
            projectile_speed=540,
            projectile_range=220,
        ),
    ),
}

ARROW_PACK_SIZE = 10
ARROW_PACK_COST = 6


def _starting_levels() -> dict[WeaponType, int]:
    ranged_level = 1 if config.UNLOCK_ALL_WEAPONS_FOR_TESTING else 0
    return {
        WeaponType.SWORD: 1,
        WeaponType.BOW: ranged_level,
        WeaponType.GUN: ranged_level,
    }


def _starting_arrows() -> int:
    return config.TEST_STARTING_ARROWS if config.UNLOCK_ALL_WEAPONS_FOR_TESTING else 0


@dataclass
class WeaponInventory:
    levels: dict[WeaponType, int] = field(default_factory=_starting_levels)
    selected: WeaponType = WeaponType.SWORD
    arrows: int = field(default_factory=_starting_arrows)

    def is_unlocked(self, weapon: WeaponType) -> bool:
        return self.levels[weapon] > 0

    def equip(self, weapon: WeaponType) -> bool:
        if not self.is_unlocked(weapon):
            return False
        self.selected = weapon
        return True

    def unlock(self, weapon: WeaponType) -> bool:
        if self.is_unlocked(weapon):
            return False
        self.levels[weapon] = 1
        return True

    def upgrade(self, weapon: WeaponType) -> bool:
        level = self.levels[weapon]
        if level <= 0 or level >= len(WEAPON_TIERS[weapon]):
            return False
        self.levels[weapon] += 1
        return True

    def tier(self, weapon: WeaponType | None = None) -> WeaponTier:
        target = weapon or self.selected
        level = self.levels[target]
        if level <= 0:
            raise ValueError(f"{target.value} is locked")
        return WEAPON_TIERS[target][level - 1]

    def next_tier(self, weapon: WeaponType) -> WeaponTier | None:
        level = self.levels[weapon]
        tiers = WEAPON_TIERS[weapon]
        if level <= 0 or level >= len(tiers):
            return None
        return tiers[level]


@dataclass
class Projectile:
    pos: pygame.Vector2
    velocity: pygame.Vector2
    weapon: WeaponType
    damage: int
    max_range: float
    traveled: float = 0.0
    alive: bool = True

    @property
    def radius(self) -> int:
        return 4 if self.weapon == WeaponType.GUN else 5

    def update(
        self,
        dt: float,
        world: GameWorld,
        enemies: list[Enemy],
    ) -> None:
        if not self.alive:
            return

        movement = self.velocity * dt
        next_pos = self.pos + movement
        hitbox = pygame.Rect(0, 0, self.radius * 2, self.radius * 2)
        hitbox.center = (round(next_pos.x), round(next_pos.y))

        if world.collides_rect(hitbox) or not world.has_line_of_sight(self.pos, next_pos):
            self.alive = False
            return

        self.pos = next_pos
        self.traveled += movement.length()
        if self.traveled >= self.max_range:
            self.alive = False
            return

        for enemy in enemies:
            if enemy.alive and hitbox.colliderect(enemy.rect()):
                enemy.take_damage(
                    self.damage,
                    self.weapon,
                    self.velocity,
                    world,
                )
                self.alive = False
                return

    def draw(self, screen: pygame.Surface, camera_offset: pygame.Vector2) -> None:
        if not self.alive:
            return

        draw_pos = self.pos - camera_offset
        center = (round(draw_pos.x), round(draw_pos.y))
        if self.weapon == WeaponType.BOW:
            direction = self.velocity.normalize()
            back = draw_pos - direction * 11
            pygame.draw.line(
                screen,
                (120, 75, 35),
                (round(back.x), round(back.y)),
                center,
                3,
            )
            side = pygame.Vector2(-direction.y, direction.x) * 4
            tip_back = draw_pos - direction * 4
            pygame.draw.polygon(
                screen,
                (210, 215, 225),
                [
                    center,
                    (round((tip_back + side).x), round((tip_back + side).y)),
                    (round((tip_back - side).x), round((tip_back - side).y)),
                ],
            )
        else:
            pygame.draw.circle(screen, (255, 220, 80), center, self.radius)
            pygame.draw.circle(screen, (255, 250, 200), center, 2)
