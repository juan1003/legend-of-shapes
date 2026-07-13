from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

import pygame

from engine.input import Input
from game import constants as C
from game.collision import circle_rect_overlap, rects_overlap
from game.weapons import Projectile, WeaponInventory, WeaponType
from game.world import GameWorld


class PickupType(Enum):
    HEART = "heart"
    RUPEE = "rupee"
    KEY = "key"


class EnemyType(Enum):
    SLIME = "slime"
    CROC = "croc"
    BOSS = "boss"


class Pickup:
    def __init__(self, pos: pygame.Vector2, kind: PickupType) -> None:
        self.pos = pos.copy()
        self.kind = kind
        self.radius = 10
        self.alive = True
        self.bob_timer = random.uniform(0, 3.14)

    def rect(self) -> pygame.Rect:
        return pygame.Rect(0, 0, self.radius * 2, self.radius * 2).move(
            int(self.pos.x - self.radius), int(self.pos.y - self.radius)
        )

    def draw(self, screen: pygame.Surface, camera_offset: pygame.Vector2) -> None:
        if not self.alive:
            return

        bob = pygame.Vector2(0, pygame.math.Vector2(1, 0).rotate(self.bob_timer * 120).y * 2)
        draw_pos = self.pos + bob - camera_offset

        if self.kind == PickupType.HEART:
            pygame.draw.circle(screen, (220, 50, 60), (int(draw_pos.x), int(draw_pos.y)), self.radius)
            pygame.draw.circle(screen, (255, 120, 120), (int(draw_pos.x - 2), int(draw_pos.y - 2)), 4)
        elif self.kind == PickupType.RUPEE:
            points = [
                (draw_pos.x, draw_pos.y - self.radius),
                (draw_pos.x + self.radius - 2, draw_pos.y),
                (draw_pos.x, draw_pos.y + self.radius),
                (draw_pos.x - self.radius + 2, draw_pos.y),
            ]
            pygame.draw.polygon(screen, (40, 200, 90), points)
            pygame.draw.polygon(screen, (120, 255, 160), [
                (draw_pos.x, draw_pos.y - self.radius + 4),
                (draw_pos.x + 4, draw_pos.y),
                (draw_pos.x, draw_pos.y + 4),
                (draw_pos.x - 4, draw_pos.y),
            ])
        elif self.kind == PickupType.KEY:
            pygame.draw.circle(screen, (240, 200, 60), (int(draw_pos.x - 3), int(draw_pos.y)), 5)
            pygame.draw.rect(screen, (240, 200, 60), pygame.Rect(draw_pos.x, draw_pos.y - 2, 12, 4))
            pygame.draw.rect(screen, (240, 200, 60), pygame.Rect(draw_pos.x + 8, draw_pos.y - 2, 3, 8))


@dataclass
class EnemyProjectile:
    pos: pygame.Vector2
    velocity: pygame.Vector2
    damage: int = C.BOSS_FIREBALL_DAMAGE
    traveled: float = 0.0
    alive: bool = True

    def update(self, dt: float, world: GameWorld, player: Player) -> None:
        if not self.alive:
            return

        movement = self.velocity * dt
        next_pos = self.pos + movement
        hitbox = pygame.Rect(0, 0, 14, 14)
        hitbox.center = (round(next_pos.x), round(next_pos.y))

        if world.collides_rect(hitbox) or not world.has_line_of_sight(self.pos, next_pos):
            self.alive = False
            return

        self.pos = next_pos
        self.traveled += movement.length()
        if hitbox.colliderect(player.rect()):
            player.take_damage(self.damage)
            self.alive = False
        elif self.traveled >= C.BOSS_FIREBALL_RANGE:
            self.alive = False

    def draw(self, screen: pygame.Surface, camera_offset: pygame.Vector2) -> None:
        if not self.alive:
            return

        draw_pos = self.pos - camera_offset
        center = (round(draw_pos.x), round(draw_pos.y))
        pygame.draw.circle(screen, (235, 65, 25), center, 9)
        pygame.draw.circle(screen, (255, 145, 35), center, 6)
        pygame.draw.circle(screen, (255, 225, 95), center, 3)


class Enemy:
    def __init__(
        self,
        pos: pygame.Vector2,
        size: int | None = None,
        health: int | None = None,
        kind: EnemyType = EnemyType.SLIME,
        archetype: EnemyType | None = None,
    ) -> None:
        self.pos = pos.copy()
        self.kind = kind
        self.archetype = archetype or (
            EnemyType.SLIME if kind == EnemyType.BOSS else kind
        )
        default_size = C.CROC_SIZE if kind == EnemyType.CROC else C.ENEMY_SIZE
        default_health = C.CROC_HEALTH if kind == EnemyType.CROC else C.ENEMY_HEALTH
        self.size = size if size is not None else default_size
        self.health = health if health is not None else default_health
        self.max_health = self.health
        self.alive = True
        self.wander_dir = pygame.Vector2(random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)]))
        self.wander_timer = 0.0
        self.hit_flash = 0.0
        self.hit_stagger = 0.0
        self.is_boss = kind == EnemyType.BOSS
        self.speed = C.CROC_SPEED if kind == EnemyType.CROC else C.ENEMY_SPEED
        self.damage = C.CROC_DAMAGE if kind == EnemyType.CROC else C.ENEMY_DAMAGE
        self.chase_range = (
            C.CROC_CHASE_RANGE if kind == EnemyType.CROC else C.ENEMY_CHASE_RANGE
        )
        self.fireball_timer = C.BOSS_FIREBALL_INTERVAL
        self.summon_timer = C.BOSS_SUMMON_INTERVAL
        self.summons_created = 0

    @property
    def display_name(self) -> str:
        if self.is_boss:
            return f"BIG {self.archetype.value.upper()}"
        return self.kind.value.upper()

    def rect(self) -> pygame.Rect:
        return pygame.Rect(0, 0, self.size, self.size).move(
            int(self.pos.x - self.size / 2), int(self.pos.y - self.size / 2)
        )

    def update(self, dt: float, player_pos: pygame.Vector2, world: GameWorld) -> None:
        if not self.alive:
            return

        if self.hit_flash > 0:
            self.hit_flash -= dt

        if self.hit_stagger > 0:
            self.hit_stagger = max(0.0, self.hit_stagger - dt)
            return

        to_player = player_pos - self.pos
        dist = to_player.length()

        if dist < self.chase_range and dist > 0:
            direction = to_player.normalize()
        else:
            self.wander_timer -= dt
            if self.wander_timer <= 0:
                self.wander_timer = random.uniform(1.0, 2.5)
                self.wander_dir = pygame.Vector2(random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)]))
            direction = self.wander_dir

        self._move(direction * self.speed * dt, world)

    def update_boss_abilities(
        self,
        dt: float,
        player_pos: pygame.Vector2,
        world: GameWorld,
    ) -> tuple[list[EnemyProjectile], list[Enemy]]:
        if not self.alive or not self.is_boss:
            return [], []

        fireballs: list[EnemyProjectile] = []
        summons: list[Enemy] = []
        self.fireball_timer -= dt
        self.summon_timer -= dt

        while self.fireball_timer <= 0:
            direction = player_pos - self.pos
            if direction.length_squared() == 0:
                direction = pygame.Vector2(0, 1)
            else:
                direction = direction.normalize()
            fireballs.append(
                EnemyProjectile(
                    pos=self.pos + direction * (self.size / 2 + 8),
                    velocity=direction * C.BOSS_FIREBALL_SPEED,
                )
            )
            self.fireball_timer += C.BOSS_FIREBALL_INTERVAL

        while self.summon_timer <= 0:
            directions = (
                pygame.Vector2(1, 0),
                pygame.Vector2(0, 1),
                pygame.Vector2(-1, 0),
                pygame.Vector2(0, -1),
            )
            for offset_index in range(len(directions)):
                direction = directions[
                    (self.summons_created + offset_index) % len(directions)
                ]
                spawn_pos = self.pos + direction * (self.size / 2 + 28)
                candidate = Enemy(spawn_pos, kind=EnemyType.SLIME)
                if not world.collides_rect(candidate.rect()):
                    summons.append(candidate)
                    self.summons_created += 1
                    break
            self.summon_timer += C.BOSS_SUMMON_INTERVAL

        return fireballs, summons

    def _move(self, velocity: pygame.Vector2, world: GameWorld) -> None:
        new_pos = self.pos + velocity
        rect = pygame.Rect(0, 0, self.size, self.size)
        rect.center = (int(new_pos.x), int(self.pos.y))
        if not world.collides_rect(rect):
            self.pos.x = new_pos.x

        rect.center = (int(self.pos.x), int(new_pos.y))
        if not world.collides_rect(rect):
            self.pos.y = new_pos.y

    def take_damage(
        self,
        amount: int,
        weapon: WeaponType = WeaponType.SWORD,
        knockback_direction: pygame.Vector2 | None = None,
        world: GameWorld | None = None,
    ) -> bool:
        if not self.alive:
            return False

        if self.archetype == EnemyType.SLIME and weapon in (
            WeaponType.BOW,
            WeaponType.GUN,
        ):
            return False

        if self.archetype == EnemyType.CROC:
            if weapon == WeaponType.GUN:
                return False
            if weapon == WeaponType.BOW:
                self.health = 0
                self.hit_flash = C.ENEMY_HIT_FLASH
                self._apply_knockback(knockback_direction, world)
                self.alive = False
                return True

        self.health -= amount
        self.hit_flash = C.ENEMY_HIT_FLASH
        self._apply_knockback(knockback_direction, world)
        if self.health <= 0:
            self.alive = False
        return True

    def _apply_knockback(
        self,
        direction: pygame.Vector2 | None,
        world: GameWorld | None,
    ) -> None:
        if direction is None or world is None or direction.length_squared() == 0:
            return
        self._move(direction.normalize() * C.ENEMY_KNOCKBACK, world)
        self.hit_stagger = C.ENEMY_HIT_STAGGER

    def draw(self, screen: pygame.Surface, camera_offset: pygame.Vector2) -> None:
        if not self.alive:
            return

        draw_pos = self.pos - camera_offset
        if self.is_boss:
            color = (255, 180, 120) if self.hit_flash > 0 else (180, 40, 40)
            body = pygame.Rect(0, 0, self.size + 8, self.size + 4).move(
                int(draw_pos.x - self.size / 2 - 4), int(draw_pos.y - self.size / 2)
            )
            pygame.draw.ellipse(screen, color, body)
            pygame.draw.rect(screen, (120, 20, 20), pygame.Rect(body.x + 8, body.y + 6, body.width - 16, 8))
            eye_y = int(draw_pos.y - 6)
            pygame.draw.circle(screen, (255, 220, 80), (int(draw_pos.x - 8), eye_y), 6)
            pygame.draw.circle(screen, (255, 220, 80), (int(draw_pos.x + 8), eye_y), 6)
            pygame.draw.circle(screen, (40, 10, 10), (int(draw_pos.x - 8), eye_y), 3)
            pygame.draw.circle(screen, (40, 10, 10), (int(draw_pos.x + 8), eye_y), 3)
            return

        if self.kind == EnemyType.CROC:
            self._draw_croc(screen, draw_pos)
            return

        color = (255, 200, 220) if self.hit_flash > 0 else (150, 50, 170)
        pygame.draw.ellipse(
            screen,
            color,
            pygame.Rect(0, 0, self.size + 4, self.size).move(
                int(draw_pos.x - self.size / 2 - 2), int(draw_pos.y - self.size / 2)
            ),
        )
        eye_y = int(draw_pos.y - 3)
        pygame.draw.circle(screen, (255, 255, 255), (int(draw_pos.x - 4), eye_y), 4)
        pygame.draw.circle(screen, (255, 255, 255), (int(draw_pos.x + 4), eye_y), 4)
        pygame.draw.circle(screen, (20, 20, 30), (int(draw_pos.x - 4), eye_y), 2)
        pygame.draw.circle(screen, (20, 20, 30), (int(draw_pos.x + 4), eye_y), 2)

    def _draw_croc(self, screen: pygame.Surface, draw_pos: pygame.Vector2) -> None:
        color = (210, 245, 170) if self.hit_flash > 0 else (55, 130, 65)
        x, y = int(draw_pos.x), int(draw_pos.y)
        body = pygame.Rect(x - 18, y - 9, 30, 18)
        snout = pygame.Rect(x + 7, y - 7, 18, 14)
        pygame.draw.ellipse(screen, color, body)
        pygame.draw.rect(screen, color, snout, border_radius=4)
        pygame.draw.polygon(
            screen,
            (42, 105, 52),
            [(x - 14, y - 3), (x - 28, y), (x - 14, y + 5)],
        )
        pygame.draw.circle(screen, (245, 225, 90), (x + 10, y - 6), 3)
        pygame.draw.circle(screen, (20, 30, 20), (x + 11, y - 6), 1)
        for tooth_x in (x + 13, x + 19):
            pygame.draw.polygon(
                screen,
                (245, 245, 225),
                [(tooth_x, y + 4), (tooth_x + 3, y + 4), (tooth_x + 1, y + 8)],
            )


def create_boss(pos: pygame.Vector2) -> Enemy:
    boss = Enemy(
        pos,
        size=C.BOSS_SIZE,
        health=C.BOSS_HEALTH,
        kind=EnemyType.BOSS,
        archetype=EnemyType.SLIME,
    )
    boss.speed = C.BOSS_SPEED
    boss.damage = C.BOSS_DAMAGE
    boss.chase_range = C.BOSS_CHASE_RANGE
    return boss


def create_croc(pos: pygame.Vector2) -> Enemy:
    return Enemy(pos, kind=EnemyType.CROC)


class Player:
    def __init__(self, pos: pygame.Vector2) -> None:
        self.pos = pos.copy()
        self.health = C.PLAYER_MAX_HEALTH
        self.max_health = C.PLAYER_MAX_HEALTH
        self.rupees = 0
        self.keys = 0
        self.facing = pygame.Vector2(0, 1)
        self.invincible_timer = 0.0
        self.attack_timer = 0.0
        self.attack_cooldown = 0.0
        self.sword_hit_targets: set[int] = set()
        self.weapons = WeaponInventory()
        self.alive = True

    def rect(self) -> pygame.Rect:
        return pygame.Rect(0, 0, C.PLAYER_SIZE, C.PLAYER_SIZE).move(
            int(self.pos.x - C.PLAYER_SIZE / 2), int(self.pos.y - C.PLAYER_SIZE / 2)
        )

    def sword_rect(self) -> pygame.Rect | None:
        if self.attack_timer <= 0 or self.weapons.selected != WeaponType.SWORD:
            return None

        size = C.SWORD_RANGE
        rect = pygame.Rect(0, 0, size, size)
        center = self.pos + self.facing * (C.PLAYER_SIZE / 2 + size / 2)
        rect.center = (int(center.x), int(center.y))
        return rect

    def update(
        self,
        dt: float,
        input: Input,
        world: GameWorld,
        obstacles: Iterable[pygame.Rect] = (),
    ) -> list[Projectile]:
        if not self.alive:
            return []

        if self.invincible_timer > 0:
            self.invincible_timer -= dt
        if self.attack_timer > 0:
            self.attack_timer -= dt
        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt

        if input.is_key_pressed(pygame.K_1):
            self.weapons.equip(WeaponType.SWORD)
        elif input.is_key_pressed(pygame.K_2):
            self.weapons.equip(WeaponType.BOW)
        elif input.is_key_pressed(pygame.K_3):
            self.weapons.equip(WeaponType.GUN)

        direction = pygame.Vector2(0, 0)
        if input.is_key_down(pygame.K_a):
            direction.x -= 1
        if input.is_key_down(pygame.K_d):
            direction.x += 1
        if input.is_key_down(pygame.K_w):
            direction.y -= 1
        if input.is_key_down(pygame.K_s):
            direction.y += 1

        if direction.length_squared() > 0:
            direction = direction.normalize()
            self.facing = direction
            sprinting = input.is_key_down(pygame.K_LCTRL) or input.is_key_down(pygame.K_RCTRL)
            speed = C.PLAYER_SPRINT_SPEED if sprinting else C.PLAYER_SPEED
            self._move(direction * speed * dt, world, obstacles)

        projectiles: list[Projectile] = []
        if input.is_key_pressed(pygame.K_SPACE):
            projectile = self.attack()
            if projectile is not None:
                projectiles.append(projectile)

        self.try_open_door(world)
        return projectiles

    def attack(self) -> Projectile | None:
        if self.attack_cooldown > 0:
            return None

        weapon = self.weapons.selected
        tier = self.weapons.tier()
        self.attack_cooldown = tier.cooldown

        if weapon == WeaponType.SWORD:
            self.attack_timer = C.SWORD_DURATION
            self.sword_hit_targets.clear()
            return None

        if weapon == WeaponType.BOW:
            if self.weapons.arrows <= 0:
                self.attack_cooldown = 0.0
                return None
            self.weapons.arrows -= 1

        direction = self.facing.normalize() if self.facing.length_squared() else pygame.Vector2(0, 1)
        start = self.pos + direction * (C.PLAYER_SIZE / 2 + 6)
        return Projectile(
            pos=start,
            velocity=direction * tier.projectile_speed,
            weapon=weapon,
            damage=tier.damage,
            max_range=tier.projectile_range,
        )

    def try_open_door(self, world: GameWorld) -> bool:
        if self.keys <= 0:
            return False

        probe_offset = self.facing * 8
        probe = self.rect().move(int(probe_offset.x), int(probe_offset.y)).inflate(6, 6)
        opened = world.open_door_at(probe)
        if not opened:
            return False

        self.keys -= 1
        return True

    def _move(
        self,
        velocity: pygame.Vector2,
        world: GameWorld,
        obstacles: Iterable[pygame.Rect] = (),
    ) -> None:
        obstacle_rects = tuple(obstacles)
        new_pos = self.pos + velocity
        rect = pygame.Rect(0, 0, C.PLAYER_SIZE, C.PLAYER_SIZE)
        rect.center = (int(new_pos.x), int(self.pos.y))
        if not world.collides_rect(rect) and not any(rect.colliderect(item) for item in obstacle_rects):
            self.pos.x = new_pos.x

        rect.center = (int(self.pos.x), int(new_pos.y))
        if not world.collides_rect(rect) and not any(rect.colliderect(item) for item in obstacle_rects):
            self.pos.y = new_pos.y

    def take_damage(self, amount: int) -> None:
        if not self.alive or self.invincible_timer > 0:
            return
        self.health -= amount
        self.invincible_timer = C.INVINCIBILITY_TIME
        if self.health <= 0:
            self.health = 0
            self.alive = False

    def heal(self, amount: int) -> None:
        self.health = min(self.max_health, self.health + amount)

    def draw(self, screen: pygame.Surface, camera_offset: pygame.Vector2) -> None:
        if not self.alive:
            return

        draw_pos = self.pos - camera_offset
        visible = self.invincible_timer <= 0 or int(self.invincible_timer * 10) % 2 == 0
        if not visible:
            return

        body = pygame.Rect(0, 0, C.PLAYER_SIZE, C.PLAYER_SIZE - 6)
        body.center = (int(draw_pos.x), int(draw_pos.y + 4))
        pygame.draw.rect(screen, (50, 130, 70), body, border_radius=4)
        pygame.draw.rect(screen, (35, 90, 55), body.inflate(-6, -4), border_radius=3)

        head_center = (int(draw_pos.x), int(draw_pos.y - 8))
        pygame.draw.circle(screen, (240, 190, 140), head_center, 8)
        pygame.draw.rect(screen, (120, 80, 40), pygame.Rect(head_center[0] - 9, head_center[1] - 10, 18, 6))

        if self.weapons.selected == WeaponType.SWORD:
            self._draw_sword(screen, draw_pos, self.attack_timer > 0)
        elif self.weapons.selected == WeaponType.BOW:
            bow_rect = pygame.Rect(int(draw_pos.x + 8), int(draw_pos.y - 7), 14, 24)
            pygame.draw.arc(screen, (135, 82, 38), bow_rect, -1.4, 1.4, 3)
            pygame.draw.line(
                screen,
                (220, 210, 175),
                (bow_rect.centerx, bow_rect.top + 2),
                (bow_rect.centerx, bow_rect.bottom - 2),
                1,
            )
        elif self.weapons.selected == WeaponType.GUN:
            gun = pygame.Rect(int(draw_pos.x + 8), int(draw_pos.y), 17, 7)
            pygame.draw.rect(screen, (85, 90, 105), gun, border_radius=2)
            pygame.draw.rect(
                screen,
                (55, 60, 70),
                pygame.Rect(gun.x + 3, gun.bottom - 1, 5, 8),
                border_radius=1,
            )

    def _draw_sword(
        self,
        screen: pygame.Surface,
        draw_pos: pygame.Vector2,
        attacking: bool,
    ) -> None:
        direction = self.facing.normalize() if self.facing.length_squared() else pygame.Vector2(0, 1)
        if not attacking:
            direction = direction.rotate(-35)

        perpendicular = pygame.Vector2(-direction.y, direction.x)
        reach = C.SWORD_RANGE if attacking else 20
        grip_start = draw_pos + direction * 5
        guard_center = draw_pos + direction * 11
        blade_start = guard_center + direction * 3
        blade_end = guard_center + direction * reach

        level = self.weapons.levels[WeaponType.SWORD]
        blade_colors = {
            1: ((155, 105, 70), (205, 150, 95)),
            2: ((165, 175, 190), (235, 240, 250)),
            3: ((55, 145, 235), (155, 220, 255)),
        }
        blade_color, highlight = blade_colors[level]

        pygame.draw.line(
            screen,
            (95, 55, 30),
            (round(grip_start.x), round(grip_start.y)),
            (round(guard_center.x), round(guard_center.y)),
            5,
        )
        guard_left = guard_center + perpendicular * 7
        guard_right = guard_center - perpendicular * 7
        pygame.draw.line(
            screen,
            (220, 175, 65),
            (round(guard_left.x), round(guard_left.y)),
            (round(guard_right.x), round(guard_right.y)),
            4,
        )

        blade = [
            blade_start + perpendicular * 3,
            blade_end,
            blade_start - perpendicular * 3,
        ]
        pygame.draw.polygon(
            screen,
            blade_color,
            [(round(point.x), round(point.y)) for point in blade],
        )
        highlight_end = blade_end - direction * 3
        pygame.draw.line(
            screen,
            highlight,
            (round(blade_start.x), round(blade_start.y)),
            (round(highlight_end.x), round(highlight_end.y)),
            1,
        )


def try_pickup(player: Player, pickups: list[Pickup]) -> None:
    player_rect = player.rect()
    for pickup in pickups:
        if pickup.alive and circle_rect_overlap(pickup.pos, pickup.radius, player_rect):
            if pickup.kind == PickupType.HEART:
                player.heal(C.HEART_HEAL)
            elif pickup.kind == PickupType.RUPEE:
                player.rupees += C.RUPEE_VALUE
            elif pickup.kind == PickupType.KEY:
                player.keys += 1
            pickup.alive = False


def resolve_combat(player: Player, enemies: list[Enemy], world: GameWorld) -> None:
    sword = player.sword_rect()
    if sword is None:
        return

    for enemy in enemies:
        target_id = id(enemy)
        if (
            enemy.alive
            and target_id not in player.sword_hit_targets
            and rects_overlap(sword, enemy.rect())
            and world.has_line_of_sight(player.pos, enemy.pos)
        ):
            enemy.take_damage(
                player.weapons.tier(WeaponType.SWORD).damage,
                WeaponType.SWORD,
                enemy.pos - player.pos,
                world,
            )
            player.sword_hit_targets.add(target_id)


def resolve_enemy_contact(player: Player, enemies: list[Enemy]) -> None:
    player_rect = player.rect()
    for enemy in enemies:
        if enemy.alive and circle_rect_overlap(enemy.pos, enemy.size / 2 + 4, player_rect):
            player.take_damage(enemy.damage)
