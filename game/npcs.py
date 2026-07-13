from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pygame

from game import constants as C
from game.weapons import ARROW_PACK_COST, WEAPON_TIERS, WeaponType

_MARKER_FONT: pygame.font.Font | None = None


def _get_marker_font() -> pygame.font.Font:
    global _MARKER_FONT
    if _MARKER_FONT is None:
        _MARKER_FONT = pygame.font.SysFont(None, 18)
    return _MARKER_FONT


class NPCType(Enum):
    VILLAGER = "villager"
    SHOPKEEPER = "shopkeeper"
    QUEST_GIVER = "quest_giver"
    DINOSAUR = "dinosaur"
    DINOSAUR_SHOPKEEPER = "dinosaur_shopkeeper"


@dataclass
class ShopItem:
    id: str
    label: str
    cost: int
    description: str


@dataclass
class Quest:
    id: str
    title: str
    description: str
    target_count: int
    reward_rupees: int
    reward_hearts: int
    accepted: bool = False
    completed: bool = False
    turned_in: bool = False
    progress: int = 0

    def is_ready_to_turn_in(self) -> bool:
        return self.accepted and not self.turned_in and self.progress >= self.target_count


@dataclass
class NPC:
    id: str
    name: str
    pos: pygame.Vector2
    kind: NPCType
    body_color: tuple[int, int, int]
    accent_color: tuple[int, int, int]
    dialogue_lines: list[str] = field(default_factory=list)
    shop_items: list[ShopItem] = field(default_factory=list)
    quest: Quest | None = None

    def rect(self) -> pygame.Rect:
        if self.kind in (NPCType.DINOSAUR, NPCType.DINOSAUR_SHOPKEEPER):
            return pygame.Rect(0, 0, 40, 24).move(
                int(self.pos.x - 20), int(self.pos.y - 12)
            )
        return pygame.Rect(0, 0, C.NPC_SIZE, C.NPC_SIZE).move(
            int(self.pos.x - C.NPC_SIZE / 2), int(self.pos.y - C.NPC_SIZE / 2)
        )

    def distance_to(self, pos: pygame.Vector2) -> float:
        return self.pos.distance_to(pos)

    def is_in_range(self, pos: pygame.Vector2) -> bool:
        return self.distance_to(pos) <= C.NPC_INTERACT_RANGE

    def draw(self, screen: pygame.Surface, camera_offset: pygame.Vector2) -> None:
        draw_pos = self.pos - camera_offset
        cx, cy = int(draw_pos.x), int(draw_pos.y)

        if self.kind in (NPCType.DINOSAUR, NPCType.DINOSAUR_SHOPKEEPER):
            self._draw_dinosaur(screen, cx, cy)
            return

        if self.kind == NPCType.SHOPKEEPER:
            counter = pygame.Rect(0, 0, 40, 14)
            counter.center = (cx, cy + 14)
            pygame.draw.rect(screen, (120, 80, 45), counter, border_radius=3)
            pygame.draw.rect(screen, (170, 120, 70), counter.inflate(-4, -4), border_radius=2)

        body = pygame.Rect(0, 0, C.NPC_SIZE, C.NPC_SIZE - 6)
        body.center = (cx, cy + 4)
        pygame.draw.rect(screen, self.body_color, body, border_radius=4)
        pygame.draw.rect(screen, self.accent_color, body.inflate(-6, -4), border_radius=3)

        head_center = (cx, cy - 8)
        pygame.draw.circle(screen, (240, 190, 140), head_center, 8)

        if self.kind == NPCType.SHOPKEEPER:
            pygame.draw.rect(screen, (230, 230, 230), pygame.Rect(cx - 10, cy + 2, 20, 12), border_radius=2)
        elif self.kind == NPCType.QUEST_GIVER:
            pygame.draw.rect(screen, (90, 50, 140), pygame.Rect(cx - 10, cy - 12, 20, 8))
            pygame.draw.line(screen, (140, 100, 60), (cx + 10, cy - 4), (cx + 10, cy + 18), 3)
            pygame.draw.circle(screen, (200, 180, 80), (cx + 10, cy - 6), 4)
        else:
            pygame.draw.rect(screen, (100, 70, 40), pygame.Rect(cx - 9, cy - 10, 18, 6))

        self._draw_marker(screen, cx, cy - 28)

    def _draw_dinosaur(self, screen: pygame.Surface, x: int, y: int) -> None:
        if self.kind == NPCType.DINOSAUR_SHOPKEEPER:
            counter = pygame.Rect(x - 30, y + 10, 60, 14)
            pygame.draw.rect(screen, (125, 80, 50), counter, border_radius=3)
            pygame.draw.rect(
                screen,
                (190, 135, 80),
                counter.inflate(-5, -5),
                border_radius=2,
            )

        pygame.draw.ellipse(
            screen,
            self.body_color,
            pygame.Rect(x - 22, y - 10, 38, 22),
        )
        pygame.draw.polygon(
            screen,
            self.body_color,
            [(x - 16, y - 5), (x - 34, y + 2), (x - 16, y + 7)],
        )
        pygame.draw.rect(
            screen,
            self.body_color,
            pygame.Rect(x + 8, y - 24, 10, 25),
            border_radius=4,
        )
        pygame.draw.ellipse(
            screen,
            self.body_color,
            pygame.Rect(x + 8, y - 30, 25, 16),
        )
        pygame.draw.circle(screen, (245, 240, 180), (x + 26, y - 23), 3)
        pygame.draw.circle(screen, (25, 35, 30), (x + 27, y - 23), 1)
        pygame.draw.rect(
            screen,
            self.accent_color,
            pygame.Rect(x - 13, y + 7, 7, 14),
            border_radius=2,
        )
        pygame.draw.rect(
            screen,
            self.accent_color,
            pygame.Rect(x + 6, y + 7, 7, 14),
            border_radius=2,
        )
        for spike_x in (-10, 0, 10):
            pygame.draw.polygon(
                screen,
                self.accent_color,
                [(x + spike_x - 4, y - 8), (x + spike_x, y - 17), (x + spike_x + 4, y - 8)],
            )

        if self.kind == NPCType.DINOSAUR_SHOPKEEPER:
            pygame.draw.circle(screen, (245, 210, 80), (x - 2, y + 1), 6)
            pygame.draw.circle(screen, (95, 55, 35), (x - 2, y + 1), 3)

    def _draw_marker(self, screen: pygame.Surface, x: int, y: int) -> None:
        if self.kind == NPCType.QUEST_GIVER and self.quest is not None:
            quest = self.quest
            if quest.turned_in:
                return
            if quest.is_ready_to_turn_in():
                color = (80, 220, 120)
                label = "!"
            elif quest.accepted:
                color = (200, 200, 100)
                label = "?"
            else:
                color = (240, 210, 60)
                label = "!"
            pygame.draw.circle(screen, color, (x, y), 8)
            text = _get_marker_font().render(label, True, (30, 30, 40))
            screen.blit(text, text.get_rect(center=(x, y)))


def tile_pos(col: int, row: int) -> pygame.Vector2:
    return pygame.Vector2(col * C.TILE_SIZE + C.TILE_SIZE / 2, row * C.TILE_SIZE + C.TILE_SIZE / 2)


def create_npcs() -> list[NPC]:
    slime_quest = Quest(
        id="slime_cleanup",
        title="Slime Cleanup",
        description="Clear the slimes from the village fields.",
        target_count=C.QUEST_SLIME_TARGET,
        reward_rupees=C.QUEST_SLIME_REWARD_RUPEES,
        reward_hearts=C.QUEST_SLIME_REWARD_HEARTS,
    )

    return [
        NPC(
            id="pip",
            name="Peddler Pip",
            pos=tile_pos(6, 6),
            kind=NPCType.SHOPKEEPER,
            body_color=(160, 90, 50),
            accent_color=(120, 65, 35),
            dialogue_lines=[
                "Welcome, traveler! I trade hearts and keys for rupees.",
                "Press 1 or 2 to buy. Press E when you're done browsing.",
            ],
            shop_items=[
                ShopItem("heart", "Heart", C.SHOP_HEART_COST, "Restores 2 hearts."),
                ShopItem("key", "Key", C.SHOP_KEY_COST, "Opens locked dungeon doors."),
            ],
        ),
        NPC(
            id="elder",
            name="Elder Elm",
            pos=tile_pos(23, 5),
            kind=NPCType.QUEST_GIVER,
            body_color=(80, 55, 140),
            accent_color=(60, 40, 110),
            dialogue_lines=[
                "Young hero, slimes have overrun our fields.",
                "Defeat them all and I shall reward your courage.",
            ],
            quest=slime_quest,
        ),
        NPC(
            id="lorna",
            name="Lorna",
            pos=tile_pos(10, 7),
            kind=NPCType.VILLAGER,
            body_color=(70, 110, 170),
            accent_color=(50, 85, 140),
            dialogue_lines=[
                "The village used to be so peaceful...",
                "Peddler Pip sells supplies on the path to the west.",
                "Elder Elm by the eastern garden has been worried lately.",
            ],
        ),
        NPC(
            id="tomas",
            name="Tomas",
            pos=tile_pos(8, 14),
            kind=NPCType.VILLAGER,
            body_color=(170, 100, 70),
            accent_color=(130, 75, 50),
            dialogue_lines=[
                "I wouldn't swim in the pond if I were you.",
                "The old dungeon lies beyond the south road.",
                "Buy a key from Pip before exploring its sealed rooms.",
            ],
        ),
        NPC(
            id="dax",
            name="Dax the Dinosaur",
            pos=tile_pos(17, 11),
            kind=NPCType.DINOSAUR,
            body_color=(65, 155, 95),
            accent_color=(38, 105, 70),
            dialogue_lines=[
                "Rawr! Don't worry, that means hello.",
                "The crocodiles moved into the dungeon. They are not as friendly as me.",
            ],
        ),
        NPC(
            id="fern",
            name="Fern the Dinosaur",
            pos=tile_pos(25, 14),
            kind=NPCType.DINOSAUR,
            body_color=(90, 170, 125),
            accent_color=(55, 115, 90),
            dialogue_lines=[
                "I have watched this village since before the oldest trees.",
                "Crocodiles are tough. Strike, retreat, then strike again.",
            ],
        ),
        NPC(
            id="linda",
            name="Linda",
            pos=tile_pos(25, 11),
            kind=NPCType.DINOSAUR_SHOPKEEPER,
            body_color=(235, 105, 165),
            accent_color=(175, 65, 125),
            dialogue_lines=[
                "Welcome to Linda's Lucky Supplies!",
                "Weapons, upgrades, and arrows are all dino-approved.",
            ],
            shop_items=[
                ShopItem(
                    "unlock_bow",
                    WEAPON_TIERS[WeaponType.BOW][0].name,
                    WEAPON_TIERS[WeaponType.BOW][0].purchase_cost,
                    "Unlocks the bow and includes 5 arrows.",
                ),
                ShopItem(
                    "unlock_gun",
                    WEAPON_TIERS[WeaponType.GUN][0].name,
                    WEAPON_TIERS[WeaponType.GUN][0].purchase_cost,
                    "Unlocks a gun with unlimited bullets.",
                ),
                ShopItem(
                    "arrows",
                    "10 Arrows",
                    ARROW_PACK_COST,
                    "A bundle of bow ammunition.",
                ),
                ShopItem("upgrade_sword", "Sword Upgrade", 0, "Upgrade your sword."),
                ShopItem("upgrade_bow", "Bow Upgrade", 0, "Upgrade your bow."),
                ShopItem("upgrade_gun", "Gun Upgrade", 0, "Upgrade your gun."),
            ],
        ),
    ]


def find_npc_in_range(npcs: list[NPC], player_pos: pygame.Vector2) -> NPC | None:
    closest: NPC | None = None
    closest_dist = float("inf")
    for npc in npcs:
        dist = npc.distance_to(player_pos)
        if dist <= C.NPC_INTERACT_RANGE and dist < closest_dist:
            closest = npc
            closest_dist = dist
    return closest
