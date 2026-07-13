from __future__ import annotations

from enum import Enum

import pygame

from engine.input import Input
from game import constants as C
from game.entities import Player
from game.npcs import NPC, NPCType, find_npc_in_range
from game.weapons import ARROW_PACK_SIZE, WeaponType


class InteractionMode(Enum):
    NONE = "none"
    DIALOGUE = "dialogue"
    SHOP = "shop"
    QUEST_OFFER = "quest_offer"
    QUEST_PROGRESS = "quest_progress"
    QUEST_COMPLETE = "quest_complete"


class InteractionManager:
    def __init__(self) -> None:
        self.mode = InteractionMode.NONE
        self.active_npc: NPC | None = None
        self.dialogue_index = 0
        self.lines: list[str] = []
        self.font = pygame.font.SysFont(None, 24)
        self.small_font = pygame.font.SysFont(None, 20)

    @property
    def is_active(self) -> bool:
        return self.mode != InteractionMode.NONE

    def try_start(self, player: Player, npcs: list[NPC]) -> bool:
        if self.is_active:
            return False

        npc = find_npc_in_range(npcs, player.pos)
        if npc is None:
            return False

        self.active_npc = npc
        self.dialogue_index = 0

        if npc.kind in (NPCType.SHOPKEEPER, NPCType.DINOSAUR_SHOPKEEPER):
            self.mode = InteractionMode.SHOP
            self.lines = npc.dialogue_lines[:1] if npc.dialogue_lines else [f"Welcome to {npc.name}'s shop."]
        elif npc.kind == NPCType.QUEST_GIVER and npc.quest is not None:
            quest = npc.quest
            if quest.turned_in:
                self.mode = InteractionMode.DIALOGUE
                self.lines = ["Thank you again, brave one. The fields are safe now."]
            elif quest.is_ready_to_turn_in():
                self.mode = InteractionMode.QUEST_COMPLETE
                self.lines = [
                    f"Splendid! You've cleared all {quest.target_count} slimes.",
                    f"Take {quest.reward_rupees} rupees and my blessing.",
                ]
            elif quest.accepted:
                self.mode = InteractionMode.QUEST_PROGRESS
                self.lines = [
                    f"Slimes defeated: {quest.progress}/{quest.target_count}",
                    "Keep at it, hero!",
                ]
            else:
                self.mode = InteractionMode.QUEST_OFFER
                self.lines = [
                    quest.description,
                    f"Reward: {quest.reward_rupees} rupees and {quest.reward_hearts} hearts.",
                    "Accept this quest? Press Y to accept, N to decline.",
                ]
        else:
            self.mode = InteractionMode.DIALOGUE
            self.lines = npc.dialogue_lines or ["..."]

        return True

    def handle_input(self, input: Input, player: Player) -> bool:
        if not self.is_active or self.active_npc is None:
            return False

        if self.mode == InteractionMode.QUEST_OFFER:
            if input.is_key_pressed(pygame.K_y) and self.active_npc.quest is not None:
                self.active_npc.quest.accepted = True
                self.mode = InteractionMode.DIALOGUE
                self.dialogue_index = 0
                self.lines = ["The slimes lurk in the fields to the south. Good luck!"]
                return True
            elif input.is_key_pressed(pygame.K_n):
                self.close()
            return False

        if self.mode == InteractionMode.QUEST_COMPLETE:
            if input.is_key_pressed(pygame.K_e) or input.is_key_pressed(pygame.K_SPACE):
                self._turn_in_quest(player)
            return False

        if self.mode == InteractionMode.SHOP:
            shop_keys = (
                pygame.K_1,
                pygame.K_2,
                pygame.K_3,
                pygame.K_4,
                pygame.K_5,
                pygame.K_6,
                pygame.K_7,
                pygame.K_8,
                pygame.K_9,
            )
            for index, key in enumerate(shop_keys):
                if input.is_key_pressed(key):
                    self._buy_item(player, index)
                    return False
            if input.is_key_pressed(pygame.K_e):
                self.close()
            return False

        if input.is_key_pressed(pygame.K_e) or input.is_key_pressed(pygame.K_SPACE):
            self.dialogue_index += 1
            if self.dialogue_index >= len(self.lines):
                self.close()
        return False

    def _buy_item(self, player: Player, index: int) -> None:
        if self.active_npc is None:
            return

        items = self.active_npc.shop_items
        if index >= len(items):
            return

        item = items[index]
        label, cost, description, available = self._shop_offer(player, item)
        if not available:
            self.lines = [description]
            self.dialogue_index = 0
            return

        if player.rupees < cost:
            self.lines = [f"Not enough rupees! {label} costs {cost}."]
            self.dialogue_index = 0
            return

        if item.id == "heart" and player.health >= player.max_health:
            self.lines = ["You're already at full health."]
            self.dialogue_index = 0
            return

        player.rupees -= cost
        if item.id == "heart":
            player.heal(C.HEART_HEAL)
            self.lines = [f"Bought a heart! Health restored. (-{cost} rupees)"]
        elif item.id == "key":
            player.keys += 1
            self.lines = [f"Bought a key! (-{cost} rupees)"]
        elif item.id == "unlock_bow":
            player.weapons.unlock(WeaponType.BOW)
            player.weapons.arrows += 5
            self.lines = ["Bought the Worn Bow! You also received 5 arrows."]
        elif item.id == "unlock_gun":
            player.weapons.unlock(WeaponType.GUN)
            self.lines = ["Bought the Old Pistol! Its bullets are unlimited."]
        elif item.id == "arrows":
            player.weapons.arrows += ARROW_PACK_SIZE
            self.lines = [f"Bought {ARROW_PACK_SIZE} arrows! (-{cost} rupees)"]
        elif item.id.startswith("upgrade_"):
            weapon = WeaponType(item.id.removeprefix("upgrade_"))
            player.weapons.upgrade(weapon)
            self.lines = [f"Upgraded to {player.weapons.tier(weapon).name}!"]
        else:
            self.lines = [f"Bought {label}! (-{cost} rupees)"]
        self.dialogue_index = 0

    def _shop_offer(
        self,
        player: Player,
        item,
    ) -> tuple[str, int, str, bool]:
        if item.id == "unlock_bow":
            if player.weapons.is_unlocked(WeaponType.BOW):
                return item.label, item.cost, "You already own a bow.", False
        elif item.id == "unlock_gun":
            if player.weapons.is_unlocked(WeaponType.GUN):
                return item.label, item.cost, "You already own a gun.", False
        elif item.id == "arrows":
            if not player.weapons.is_unlocked(WeaponType.BOW):
                return item.label, item.cost, "Buy a bow before buying arrows.", False
        elif item.id.startswith("upgrade_"):
            weapon = WeaponType(item.id.removeprefix("upgrade_"))
            if not player.weapons.is_unlocked(weapon):
                return item.label, 0, f"Unlock the {weapon.value} first.", False
            next_tier = player.weapons.next_tier(weapon)
            if next_tier is None:
                return item.label, 0, f"Your {weapon.value} is already at maximum level.", False
            return (
                f"Upgrade to {next_tier.name}",
                next_tier.purchase_cost,
                f"Raises damage to {next_tier.damage}.",
                True,
            )
        return item.label, item.cost, item.description, True

    def _turn_in_quest(self, player: Player) -> None:
        if self.active_npc is None or self.active_npc.quest is None:
            self.close()
            return

        quest = self.active_npc.quest
        player.rupees += quest.reward_rupees
        player.heal(quest.reward_hearts)
        quest.completed = True
        quest.turned_in = True
        self.close()

    def close(self) -> None:
        self.mode = InteractionMode.NONE
        self.active_npc = None
        self.dialogue_index = 0
        self.lines = []

    def update_quest_progress(self, defeated_enemies: int, npcs: list[NPC]) -> None:
        for npc in npcs:
            if npc.quest is None or not npc.quest.accepted or npc.quest.turned_in:
                continue
            npc.quest.progress = defeated_enemies

    def draw(self, screen: pygame.Surface, player: Player, npcs: list[NPC]) -> None:
        nearby = find_npc_in_range(npcs, player.pos)
        if nearby is not None and not self.is_active:
            prompt = self.small_font.render(f"Press E to talk to {nearby.name}", True, (240, 240, 200))
            rect = prompt.get_rect(center=(screen.get_width() // 2, screen.get_height() - 58))
            background_rect = rect.inflate(16, 8)
            background = pygame.Surface(background_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(background, (30, 30, 40, 200), background.get_rect(), border_radius=6)
            screen.blit(background, background_rect)
            screen.blit(prompt, rect)

        if not self.is_active or self.active_npc is None:
            return

        box_height = 140
        if self.mode == InteractionMode.SHOP:
            box_height = max(box_height, 82 + len(self.active_npc.shop_items) * 22)
        box = pygame.Rect(16, screen.get_height() - box_height - 16, screen.get_width() - 32, box_height)
        pygame.draw.rect(screen, (24, 26, 36), box, border_radius=8)
        pygame.draw.rect(screen, (70, 75, 95), box, width=2, border_radius=8)

        name_surface = self.font.render(self.active_npc.name, True, (255, 220, 140))
        screen.blit(name_surface, (box.x + 14, box.y + 10))

        if self.mode == InteractionMode.SHOP:
            self._draw_shop(screen, box, player)
        elif self.mode == InteractionMode.QUEST_OFFER:
            self._draw_text_block(screen, box, self.lines)
        elif self.mode == InteractionMode.QUEST_COMPLETE:
            self._draw_text_block(screen, box, self.lines)
            hint = self.small_font.render("Press E to claim reward", True, (180, 180, 190))
            screen.blit(hint, (box.x + 14, box.bottom - 28))
        else:
            line = self.lines[min(self.dialogue_index, len(self.lines) - 1)]
            self._draw_text_block(screen, box, [line])
            if self.mode != InteractionMode.QUEST_PROGRESS:
                hint = self.small_font.render("Press E to continue", True, (180, 180, 190))
                screen.blit(hint, (box.right - hint.get_width() - 14, box.bottom - 28))

    def _draw_text_block(self, screen: pygame.Surface, box: pygame.Rect, lines: list[str]) -> None:
        y = box.y + 38
        for line in lines:
            surface = self.font.render(line, True, (220, 220, 230))
            screen.blit(surface, (box.x + 14, y))
            y += 26

    def _draw_shop(self, screen: pygame.Surface, box: pygame.Rect, player: Player) -> None:
        y = box.y + 38
        for line in self.lines:
            surface = self.font.render(line, True, (220, 220, 230))
            screen.blit(surface, (box.x + 14, y))
            y += 24

        if self.active_npc is None:
            return

        y += 6
        for index, item in enumerate(self.active_npc.shop_items, start=1):
            label, cost, description, available = self._shop_offer(player, item)
            affordable = available and player.rupees >= cost
            color = (120, 255, 160) if affordable else (150, 100, 100)
            price = f"{cost} rupees" if available else "unavailable"
            text = f"{index}. {label} - {price}  ({description})"
            surface = self.small_font.render(text, True, color)
            screen.blit(surface, (box.x + 14, y))
            y += 22

        hint = self.small_font.render("Press item number to buy  |  E to leave", True, (180, 180, 190))
        screen.blit(hint, (box.x + 14, box.bottom - 28))
