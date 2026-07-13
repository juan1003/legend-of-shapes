from __future__ import annotations

from dataclasses import dataclass, field

import pygame

import config
from game import constants as C
from game.maps import (
    BOSS_DOOR_ID,
    CHAR_TO_TILE,
    ENTITY_MARKERS,
    RETURN_PORTAL_ID,
    TRANSITION_CHARS,
    get_map_definition,
)


@dataclass
class SpawnData:
    player_pos: pygame.Vector2
    enemy_positions: list[pygame.Vector2] = field(default_factory=list)
    croc_positions: list[pygame.Vector2] = field(default_factory=list)
    boss_positions: list[pygame.Vector2] = field(default_factory=list)
    heart_positions: list[pygame.Vector2] = field(default_factory=list)
    rupee_positions: list[pygame.Vector2] = field(default_factory=list)
    key_positions: list[pygame.Vector2] = field(default_factory=list)
    transitions: dict[str, list[pygame.Vector2]] = field(default_factory=dict)
    spawn_points: dict[str, pygame.Vector2] = field(default_factory=dict)


class GameWorld:
    def __init__(self, map_id: str = C.MAP_OVERWORLD) -> None:
        self.map_id = map_id
        self.definition = get_map_definition(map_id)
        rows = [line for line in self.definition.layout.strip().splitlines()]
        self.height = len(rows)
        self.width = max(len(row) for row in rows) if rows else 0
        self.tiles: list[list[int]] = []
        self.boss_door_unlocked = False
        self.opened_doors: set[tuple[int, int]] = set()
        self._label_font: pygame.font.Font | None = None
        spawn = SpawnData(player_pos=pygame.Vector2(C.TILE_SIZE * 2, C.TILE_SIZE * 2))

        for y, row in enumerate(rows):
            padded_row = row.ljust(self.width, "#" if map_id != C.MAP_OVERWORLD else "T")
            tile_row: list[int] = []
            for x, char in enumerate(padded_row):
                tile_row.append(self._terrain_for_symbol(char))
                world_pos = pygame.Vector2(
                    x * C.TILE_SIZE + C.TILE_SIZE / 2,
                    y * C.TILE_SIZE + C.TILE_SIZE / 2,
                )

                if char == "@":
                    spawn.player_pos = world_pos
                elif char == "E":
                    spawn.enemy_positions.append(world_pos)
                elif char == "C":
                    spawn.croc_positions.append(world_pos)
                elif char == "B" and self.map_id == C.MAP_DUNGEON_BOSS:
                    spawn.boss_positions.append(world_pos)
                elif char == "H":
                    spawn.heart_positions.append(world_pos)
                elif char == "R":
                    spawn.rupee_positions.append(world_pos)
                elif char == "K":
                    spawn.key_positions.append(world_pos)

                transition_id = self._transition_id_for_symbol(char)
                if transition_id is not None:
                    spawn.transitions.setdefault(transition_id, []).append(world_pos)

            self.tiles.append(tile_row)

        for spawn_id, (x, y) in self.definition.spawn_tiles.items():
            spawn.spawn_points[spawn_id] = pygame.Vector2(
                x * C.TILE_SIZE + C.TILE_SIZE / 2,
                y * C.TILE_SIZE + C.TILE_SIZE / 2,
            )

        self.spawn = spawn
        self.pixel_width = self.width * C.TILE_SIZE
        self.pixel_height = self.height * C.TILE_SIZE

    def _terrain_for_symbol(self, char: str) -> int:
        if char in ENTITY_MARKERS:
            if self.map_id == C.MAP_OVERWORLD:
                return C.TILE_PATH if char == "@" else C.TILE_GRASS
            return C.TILE_STONE
        if char == "B" and self.map_id == C.MAP_DUNGEON_BOSS:
            return C.TILE_STONE
        return CHAR_TO_TILE.get(
            char,
            C.TILE_GRASS if self.map_id == C.MAP_OVERWORLD else C.TILE_STONE,
        )

    def _transition_id_for_symbol(self, char: str) -> str | None:
        if char == ">":
            return "dungeon_entrance" if self.map_id == C.MAP_OVERWORLD else RETURN_PORTAL_ID
        if char == "B" and self.map_id == C.MAP_DUNGEON_HUB:
            return BOSS_DOOR_ID
        return TRANSITION_CHARS.get(char)

    @property
    def display_name(self) -> str:
        return self.definition.name

    def get_tile(self, x: int, y: int) -> int:
        if x < 0 or y < 0 or y >= self.height or x >= len(self.tiles[y]):
            return C.TILE_DUNGEON_WALL if self.map_id != C.MAP_OVERWORLD else C.TILE_WALL
        return self.tiles[y][x]

    def is_solid(self, tile: int) -> bool:
        if tile == C.TILE_BOSS_DOOR:
            return not self.boss_door_unlocked
        return tile in (
            C.TILE_WALL,
            C.TILE_WATER,
            C.TILE_DOOR,
            C.TILE_DUNGEON_WALL,
            C.TILE_LAVA,
            C.TILE_HOUSE,
        )

    def tile_rect(self, x: int, y: int) -> pygame.Rect:
        return pygame.Rect(x * C.TILE_SIZE, y * C.TILE_SIZE, C.TILE_SIZE, C.TILE_SIZE)

    def collides_rect(self, rect: pygame.Rect) -> bool:
        left = max(0, rect.left // C.TILE_SIZE)
        right = min(self.width - 1, (rect.right - 1) // C.TILE_SIZE)
        top = max(0, rect.top // C.TILE_SIZE)
        bottom = min(self.height - 1, (rect.bottom - 1) // C.TILE_SIZE)

        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                if self.is_solid(self.get_tile(x, y)):
                    if rect.colliderect(self.tile_rect(x, y)):
                        return True
        return False

    def open_door_at(self, rect: pygame.Rect) -> set[tuple[int, int]]:
        left = max(0, rect.left // C.TILE_SIZE)
        right = min(self.width - 1, (rect.right - 1) // C.TILE_SIZE)
        top = max(0, rect.top // C.TILE_SIZE)
        bottom = min(self.height - 1, (rect.bottom - 1) // C.TILE_SIZE)
        opened: set[tuple[int, int]] = set()

        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                if self.get_tile(x, y) == C.TILE_DOOR:
                    self.tiles[y][x] = C.TILE_PATH
                    self.opened_doors.add((x, y))
                    opened.add((x, y))
        return opened

    def apply_opened_doors(self, opened_doors: set[tuple[int, int]]) -> None:
        for x, y in opened_doors:
            if self.get_tile(x, y) == C.TILE_DOOR:
                self.tiles[y][x] = C.TILE_PATH
                self.opened_doors.add((x, y))

    def unlock_boss_door(self) -> None:
        self.boss_door_unlocked = True
        for y in range(self.height):
            for x in range(self.width):
                if self.tiles[y][x] == C.TILE_BOSS_DOOR:
                    self.tiles[y][x] = C.TILE_PORTAL

    def get_transition_at(self, pos: pygame.Vector2) -> str | None:
        for transition_id, points in self.spawn.transitions.items():
            if transition_id == BOSS_DOOR_ID and not self.boss_door_unlocked:
                continue
            for point in points:
                if pos.distance_to(point) <= C.TILE_SIZE * 0.55:
                    return transition_id
        return None

    def get_spawn_for_transition(self, transition_id: str) -> pygame.Vector2:
        return self.spawn.spawn_points.get(transition_id, self.spawn.player_pos).copy()

    def has_line_of_sight(self, start: pygame.Vector2, end: pygame.Vector2) -> bool:
        left = max(0, int(min(start.x, end.x) // C.TILE_SIZE))
        right = min(self.width - 1, int(max(start.x, end.x) // C.TILE_SIZE))
        top = max(0, int(min(start.y, end.y) // C.TILE_SIZE))
        bottom = min(self.height - 1, int(max(start.y, end.y) // C.TILE_SIZE))
        line = (int(start.x), int(start.y), int(end.x), int(end.y))

        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                if self.is_solid(self.get_tile(x, y)) and self.tile_rect(x, y).clipline(line):
                    return False
        return True

    def draw(self, screen: pygame.Surface, camera_offset: pygame.Vector2) -> None:
        start_x = max(0, int(camera_offset.x // C.TILE_SIZE))
        start_y = max(0, int(camera_offset.y // C.TILE_SIZE))
        end_x = min(self.width, start_x + config.WINDOW_WIDTH // C.TILE_SIZE + 2)
        end_y = min(self.height, start_y + config.WINDOW_HEIGHT // C.TILE_SIZE + 2)

        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                tile = self.get_tile(x, y)
                rect = self.tile_rect(x, y)
                screen_rect = rect.move(-int(camera_offset.x), -int(camera_offset.y))
                pygame.draw.rect(screen, C.TILE_COLORS.get(tile, (80, 80, 80)), screen_rect)
                self._draw_tile_detail(screen, tile, screen_rect)

    def _draw_tile_detail(self, screen: pygame.Surface, tile: int, screen_rect: pygame.Rect) -> None:
        if tile == C.TILE_WALL:
            trunk = screen_rect.inflate(-10, -10)
            pygame.draw.rect(screen, (48, 28, 14), trunk)
            crown = pygame.Rect(0, 0, screen_rect.width - 4, screen_rect.height - 14)
            crown.center = (screen_rect.centerx, screen_rect.top + 10)
            pygame.draw.ellipse(screen, (28, 110, 48), crown)
        elif tile == C.TILE_HOUSE:
            pygame.draw.rect(
                screen,
                (178, 104, 72),
                screen_rect.inflate(-3, -3),
                border_radius=2,
            )
            pygame.draw.line(
                screen,
                (112, 58, 48),
                screen_rect.topleft,
                screen_rect.topright,
                4,
            )
            pygame.draw.rect(
                screen,
                (232, 192, 104),
                pygame.Rect(screen_rect.centerx - 4, screen_rect.centery - 2, 8, 8),
                border_radius=1,
            )
        elif tile == C.TILE_DUNGEON_WALL:
            pygame.draw.rect(screen, (70, 70, 82), screen_rect.inflate(-4, -4), border_radius=2)
            pygame.draw.line(
                screen,
                (45, 45, 55),
                (screen_rect.left + 4, screen_rect.centery),
                (screen_rect.right - 4, screen_rect.centery),
                1,
            )
        elif tile == C.TILE_WATER:
            pygame.draw.circle(
                screen,
                (90, 150, 220),
                (screen_rect.centerx - 4, screen_rect.centery + 2),
                4,
            )
        elif tile == C.TILE_LAVA:
            pygame.draw.line(
                screen,
                (240, 100, 30),
                (screen_rect.left + 3, screen_rect.centery),
                (screen_rect.right - 3, screen_rect.centery - 3),
                3,
            )
            pygame.draw.circle(
                screen,
                (255, 180, 45),
                (screen_rect.centerx + 6, screen_rect.centery + 7),
                3,
            )
        elif tile == C.TILE_DOOR:
            pygame.draw.rect(screen, (160, 110, 60), screen_rect.inflate(-8, -4))
            pygame.draw.circle(screen, (220, 190, 80), (screen_rect.right - 10, screen_rect.centery), 3)
        elif tile == C.TILE_ROOM_DOOR:
            pygame.draw.rect(screen, (130, 90, 50), screen_rect.inflate(-6, -4), border_radius=2)
            pygame.draw.rect(screen, (180, 130, 70), screen_rect.inflate(-12, -8), border_radius=2)
        elif tile == C.TILE_BOSS_DOOR:
            pygame.draw.rect(screen, (100, 25, 25), screen_rect.inflate(-4, -2))
            pygame.draw.rect(screen, (180, 50, 50), screen_rect.inflate(-10, -6))
            if self._label_font is None:
                self._label_font = pygame.font.SysFont(None, 18)
            label = self._label_font.render("B", True, (255, 200, 120))
            screen.blit(label, label.get_rect(center=screen_rect.center))
        elif tile == C.TILE_PORTAL:
            pygame.draw.rect(screen, (70, 55, 40), screen_rect.inflate(-8, -6), border_radius=3)
            pygame.draw.circle(screen, (180, 150, 90), screen_rect.center, 6)
