from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

import pygame

from game import constants as C
from game.entities import EnemyType, PickupType
from game.npcs import NPCType
from game.weapons import WeaponType

if TYPE_CHECKING:
    from game.entities import Enemy, EnemyProjectile, Pickup, Player
    from game.npcs import NPC
    from game.weapons import Projectile
    from game.world import GameWorld

Color = tuple[int, int, int]
Point = tuple[int, int]


@dataclass(frozen=True)
class Box:
    """A colored cuboid in the game's X/Z ground plane."""

    x: float
    z: float
    width: float
    depth: float
    height: float
    color: Color
    elevation: float = 0.0

    @property
    def sort_depth(self) -> float:
        return self.x + self.z


class IsometricCamera:
    """Projects 3D world coordinates to the Pygame display surface."""

    def __init__(
        self,
        viewport_size: tuple[int, int],
        scale: float = 1.0,
    ) -> None:
        self.viewport_size = viewport_size
        self.scale = scale
        self.target = pygame.Vector2()
        self.screen_anchor = pygame.Vector2(
            viewport_size[0] / 2,
            viewport_size[1] * 0.48,
        )

    def follow(self, target: pygame.Vector2) -> None:
        self.target.update(target)

    def project(self, x: float, y: float, z: float) -> Point:
        """Project an X/Y/Z point, where Y is vertical and X/Z is ground."""
        relative_x = x - self.target.x
        relative_z = z - self.target.y
        screen_x = self.screen_anchor.x + (relative_x - relative_z) * self.scale
        screen_y = (
            self.screen_anchor.y
            + (relative_x + relative_z) * self.scale * 0.5
            - y * self.scale
        )
        return round(screen_x), round(screen_y)


class Renderer3D:
    """Software-rendered 3D presentation built on Pygame primitives."""

    SKY_COLOR = (28, 38, 57)
    VOID_COLOR = (18, 22, 30)
    FLOOR_RADIUS = 18

    def __init__(self, viewport_size: tuple[int, int]) -> None:
        self.camera = IsometricCamera(viewport_size, scale=1.05)

    def draw_scene(
        self,
        screen: pygame.Surface,
        world: GameWorld,
        player: Player,
        pickups: Iterable[Pickup],
        npcs: Iterable[NPC],
        enemies: Iterable[Enemy],
        projectiles: Iterable[Projectile],
        enemy_projectiles: Iterable[EnemyProjectile],
    ) -> None:
        self.camera.follow(player.pos)
        screen.fill(self.SKY_COLOR)
        self._draw_horizon(screen)
        self._draw_floor(screen, world)

        boxes = list(self._world_boxes(world))
        boxes.extend(self._entity_boxes(player, pickups, npcs, enemies))
        for box in sorted(boxes, key=lambda item: item.sort_depth):
            self._draw_box(screen, box)

        self._draw_projectiles(screen, projectiles, enemy_projectiles)
        self._draw_player_direction(screen, player)

    def _draw_horizon(self, screen: pygame.Surface) -> None:
        horizon_y = round(screen.get_height() * 0.48)
        pygame.draw.rect(
            screen,
            self.VOID_COLOR,
            (0, horizon_y, screen.get_width(), screen.get_height() - horizon_y),
        )

    def _draw_floor(self, screen: pygame.Surface, world: GameWorld) -> None:
        center_x = int(self.camera.target.x // C.TILE_SIZE)
        center_z = int(self.camera.target.y // C.TILE_SIZE)
        start_x = max(0, center_x - self.FLOOR_RADIUS)
        end_x = min(world.width, center_x + self.FLOOR_RADIUS + 1)
        start_z = max(0, center_z - self.FLOOR_RADIUS)
        end_z = min(world.height, center_z + self.FLOOR_RADIUS + 1)

        tiles = (
            (x, z)
            for z in range(start_z, end_z)
            for x in range(start_x, end_x)
        )
        for x, z in sorted(tiles, key=lambda tile: sum(tile)):
            tile = world.get_tile(x, z)
            color = C.TILE_COLORS.get(tile, (80, 80, 80))
            self._draw_ground_tile(screen, x, z, self._floor_color(tile, color))

    def _draw_ground_tile(
        self,
        screen: pygame.Surface,
        tile_x: int,
        tile_z: int,
        color: Color,
    ) -> None:
        x = tile_x * C.TILE_SIZE
        z = tile_z * C.TILE_SIZE
        size = C.TILE_SIZE
        points = (
            self.camera.project(x, 0, z),
            self.camera.project(x + size, 0, z),
            self.camera.project(x + size, 0, z + size),
            self.camera.project(x, 0, z + size),
        )
        pygame.draw.polygon(screen, color, points)
        pygame.draw.polygon(screen, self._shade(color, 0.72), points, width=1)

    def _world_boxes(self, world: GameWorld) -> Iterable[Box]:
        center_x = int(self.camera.target.x // C.TILE_SIZE)
        center_z = int(self.camera.target.y // C.TILE_SIZE)
        start_x = max(0, center_x - self.FLOOR_RADIUS)
        end_x = min(world.width, center_x + self.FLOOR_RADIUS + 1)
        start_z = max(0, center_z - self.FLOOR_RADIUS)
        end_z = min(world.height, center_z + self.FLOOR_RADIUS + 1)

        for z in range(start_z, end_z):
            for x in range(start_x, end_x):
                tile = world.get_tile(x, z)
                height = self._tile_height(tile)
                if height <= 0:
                    continue
                yield Box(
                    x=x * C.TILE_SIZE + C.TILE_SIZE / 2,
                    z=z * C.TILE_SIZE + C.TILE_SIZE / 2,
                    width=C.TILE_SIZE,
                    depth=C.TILE_SIZE,
                    height=height,
                    color=C.TILE_COLORS.get(tile, (80, 80, 80)),
                )

    def _entity_boxes(
        self,
        player: Player,
        pickups: Iterable[Pickup],
        npcs: Iterable[NPC],
        enemies: Iterable[Enemy],
    ) -> Iterable[Box]:
        yield Box(
            player.pos.x,
            player.pos.y,
            C.PLAYER_SIZE,
            C.PLAYER_SIZE,
            30,
            (65, 145, 235) if player.invincible_timer <= 0 else (180, 220, 255),
        )

        for pickup in pickups:
            if not pickup.alive:
                continue
            color = {
                PickupType.HEART: (220, 50, 60),
                PickupType.RUPEE: (40, 210, 90),
                PickupType.KEY: (240, 200, 60),
            }[pickup.kind]
            yield Box(
                pickup.pos.x,
                pickup.pos.y,
                12,
                12,
                16,
                color,
                elevation=7,
            )

        for npc in npcs:
            dinosaur = npc.kind in {
                NPCType.DINOSAUR,
                NPCType.DINOSAUR_SHOPKEEPER,
            }
            yield Box(
                npc.pos.x,
                npc.pos.y,
                34 if dinosaur else C.NPC_SIZE,
                22 if dinosaur else C.NPC_SIZE,
                26 if dinosaur else 34,
                npc.body_color,
            )

        for enemy in enemies:
            if not enemy.alive:
                continue
            if enemy.hit_flash > 0:
                color = (255, 205, 205)
            elif enemy.is_boss:
                color = (180, 40, 40)
            elif enemy.kind == EnemyType.CROC:
                color = (55, 130, 65)
            else:
                color = (150, 50, 170)
            yield Box(
                enemy.pos.x,
                enemy.pos.y,
                enemy.size,
                enemy.size,
                enemy.size * (1.35 if enemy.is_boss else 0.9),
                color,
            )

    def _draw_box(self, screen: pygame.Surface, box: Box) -> None:
        half_width = box.width / 2
        half_depth = box.depth / 2
        bottom = box.elevation
        top = bottom + box.height
        corners = (
            (box.x - half_width, box.z - half_depth),
            (box.x + half_width, box.z - half_depth),
            (box.x + half_width, box.z + half_depth),
            (box.x - half_width, box.z + half_depth),
        )
        bottom_points = [
            self.camera.project(x, bottom, z) for x, z in corners
        ]
        top_points = [self.camera.project(x, top, z) for x, z in corners]

        right_face = (
            bottom_points[1],
            bottom_points[2],
            top_points[2],
            top_points[1],
        )
        left_face = (
            bottom_points[2],
            bottom_points[3],
            top_points[3],
            top_points[2],
        )
        pygame.draw.polygon(screen, self._shade(box.color, 0.62), right_face)
        pygame.draw.polygon(screen, self._shade(box.color, 0.78), left_face)
        pygame.draw.polygon(screen, self._shade(box.color, 1.12), top_points)

        outline = self._shade(box.color, 0.42)
        pygame.draw.polygon(screen, outline, right_face, width=1)
        pygame.draw.polygon(screen, outline, left_face, width=1)
        pygame.draw.polygon(screen, outline, top_points, width=1)

    def _draw_projectiles(
        self,
        screen: pygame.Surface,
        projectiles: Iterable[Projectile],
        enemy_projectiles: Iterable[EnemyProjectile],
    ) -> None:
        for projectile in projectiles:
            if not projectile.alive:
                continue
            color = (
                (205, 170, 90)
                if projectile.weapon == WeaponType.BOW
                else (255, 225, 85)
            )
            center = self.camera.project(
                projectile.pos.x,
                15,
                projectile.pos.y,
            )
            pygame.draw.circle(screen, color, center, projectile.radius + 1)

        for projectile in enemy_projectiles:
            if not projectile.alive:
                continue
            center = self.camera.project(
                projectile.pos.x,
                18,
                projectile.pos.y,
            )
            pygame.draw.circle(screen, (245, 70, 25), center, 8)
            pygame.draw.circle(screen, (255, 190, 55), center, 4)

    def _draw_player_direction(
        self,
        screen: pygame.Surface,
        player: Player,
    ) -> None:
        start = self.camera.project(player.pos.x, 22, player.pos.y)
        end = self.camera.project(
            player.pos.x + player.facing.x * 22,
            22,
            player.pos.y + player.facing.y * 22,
        )
        pygame.draw.line(screen, (235, 245, 255), start, end, width=3)

    @staticmethod
    def _tile_height(tile: int) -> float:
        if tile == C.TILE_HOUSE:
            return 58
        if tile in {
            C.TILE_WALL,
            C.TILE_DUNGEON_WALL,
            C.TILE_DOOR,
            C.TILE_BOSS_DOOR,
            C.TILE_ROOM_DOOR,
        }:
            return 42
        if tile == C.TILE_PORTAL:
            return 5
        return 0

    @staticmethod
    def _floor_color(tile: int, color: Color) -> Color:
        if tile in {
            C.TILE_WALL,
            C.TILE_DUNGEON_WALL,
            C.TILE_HOUSE,
            C.TILE_DOOR,
            C.TILE_BOSS_DOOR,
            C.TILE_ROOM_DOOR,
        }:
            return (75, 75, 82)
        return color

    @staticmethod
    def _shade(color: Color, factor: float) -> Color:
        return tuple(
            max(0, min(255, round(channel * factor)))
            for channel in color
        )
