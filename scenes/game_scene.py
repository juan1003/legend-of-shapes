from __future__ import annotations

from pathlib import Path

import pygame

import config
from engine.camera import Camera
from engine.input import Input
from engine.renderer3d import Renderer3D
from engine.scene import Scene
from game import constants as C
from game.cutscene import EndingCutscene
from game.entities import (
    Enemy,
    EnemyProjectile,
    Player,
    resolve_combat,
    resolve_enemy_contact,
    try_pickup,
)
from game.interaction import InteractionManager
from game.map_state import MapState, build_map_state
from game.maps import BOSS_DOOR_ID, get_map_definition
from game.npcs import create_npcs
from game.weapons import Projectile, WeaponType
from game.world import GameWorld


class GameScene(Scene):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.current_map_id = C.MAP_OVERWORLD
        self.map_states: dict[str, MapState] = {}
        self.room_1_cleared = False
        self.room_2_cleared = False
        self.boss_defeated = False
        self.boss_timed_out = False
        self.active_boss_map_id: str | None = None
        self.ending_cutscene: EndingCutscene | None = None
        self.transition_cooldown = 0.0
        self.npcs = create_npcs()
        self.interaction = InteractionManager()
        self.message = ""
        self.message_timer = 0.0
        self.font = pygame.font.SysFont(None, 24)
        self.title_font = pygame.font.SysFont(None, 48)
        self.renderer = Renderer3D((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        self.projectiles: list[Projectile] = []
        self.enemy_projectiles: list[EnemyProjectile] = []
        self._load_map(self.current_map_id, spawn_transition=None)

    def _get_or_create_map_state(self, map_id: str, world: GameWorld) -> MapState:
        if map_id not in self.map_states:
            self.map_states[map_id] = build_map_state(
                world,
                spawn_regular_enemies=map_id != C.MAP_OVERWORLD,
            )
        state = self.map_states[map_id]
        if map_id == C.MAP_DUNGEON_HUB and (self.room_1_cleared and self.room_2_cleared):
            state.boss_door_unlocked = True
            world.unlock_boss_door()
        return state

    def _load_map(self, map_id: str, spawn_transition: str | None) -> None:
        self.current_map_id = map_id
        self.world = GameWorld(map_id)
        state = self._get_or_create_map_state(map_id, self.world)
        self.world.apply_opened_doors(state.opened_doors)
        if map_id == C.MAP_DUNGEON_BOSS and any(
            enemy.is_boss and enemy.alive for enemy in state.enemies
        ):
            self.active_boss_map_id = map_id

        if state.boss_door_unlocked:
            self.world.unlock_boss_door()

        if not hasattr(self, "player"):
            self.player = Player(self.world.spawn.player_pos)
        elif spawn_transition is not None:
            self.player.pos = self.world.get_spawn_for_transition(spawn_transition)
        else:
            self.player.pos = self.world.spawn.player_pos.copy()

        self.enemies = state.enemies
        self.pickups = state.pickups
        self.projectiles.clear()
        self.enemy_projectiles.clear()
        self.camera = Camera(self.world.pixel_width, self.world.pixel_height)
        self.camera.follow(self.player.pos)
        self._switch_map_music()

    def _switch_map_music(self) -> None:
        audio = getattr(self.game, "audio", None)
        if audio is None:
            return

        music_root = Path(__file__).resolve().parents[1] / "assets" / "music"
        if self.current_map_id == C.MAP_OVERWORLD:
            filename = "korobeiniki_test.wav"
            volume = 0.3
        elif self.current_map_id == C.MAP_DUNGEON_BOSS:
            filename = "boss_battle_original.wav"
            volume = 0.38
        else:
            filename = "dungeon_castle_original.wav"
            volume = 0.3
        audio.play_music(music_root / filename, volume=volume, fade_ms=500)

    def _current_state(self) -> MapState:
        return self.map_states[self.current_map_id]

    def _sync_current_state(self) -> None:
        state = self._current_state()
        state.opened_doors.update(self.world.opened_doors)
        state.enemies = self.enemies
        state.pickups = self.pickups

    def _compact_current_state(self) -> None:
        state = self._current_state()
        state.enemies = self.enemies
        state.pickups = self.pickups
        state.compact()
        self.enemies = state.enemies
        self.pickups = state.pickups

    def on_enter(self) -> None:
        self._show_message("Find the dungeon entrance south of the village.")

    def _show_message(self, text: str, duration: float = 3.0) -> None:
        self.message = text
        self.message_timer = duration

    def _spawn_overworld_quest_slimes(self) -> None:
        state = self.map_states[C.MAP_OVERWORLD]
        if state.quest_enemies_spawned:
            return

        state.enemies.extend(Enemy(pos) for pos in self.world.spawn.enemy_positions)
        state.quest_enemies_spawned = True
        self._show_message("Slimes have appeared in the southern fields!")

    def _reset_game(self) -> None:
        self.map_states.clear()
        self.room_1_cleared = False
        self.room_2_cleared = False
        self.boss_defeated = False
        self.boss_timed_out = False
        self.active_boss_map_id = None
        self.ending_cutscene = None
        self.transition_cooldown = 0.0
        self.npcs = create_npcs()
        self.interaction.close()
        self.player = Player(pygame.Vector2(0, 0))
        self._load_map(C.MAP_OVERWORLD, spawn_transition=None)
        self._show_message("Find the dungeon entrance south of the village.")

    def _try_map_transition(self) -> None:
        if self.transition_cooldown > 0:
            return

        transition_id = self.world.get_transition_at(self.player.pos)
        if transition_id is None:
            return

        link = self.world.definition.links.get(transition_id)
        if link is None:
            return

        if transition_id == BOSS_DOOR_ID and not self.world.boss_door_unlocked:
            self._show_message("The boss door is sealed. Clear both side rooms first.", 2.5)
            return

        self._sync_current_state()
        self._save_room_progress()
        self._load_map(link.target_map, spawn_transition=link.target_spawn)
        self.transition_cooldown = C.TRANSITION_COOLDOWN

        target_name = get_map_definition(link.target_map).name
        if link.target_map == C.MAP_OVERWORLD:
            self._show_message("Returned to the village.", 2.0)
        elif link.target_map == C.MAP_DUNGEON_HUB:
            self._show_message("Back in the dungeon entrance.", 2.0)
        elif link.target_map == C.MAP_DUNGEON_BOSS:
            self._show_message("The boss chamber awaits...", 2.5)
        else:
            self._show_message(f"Entered {target_name}.", 2.0)

    def _save_room_progress(self) -> None:
        state = self._current_state()
        if self.current_map_id == C.MAP_DUNGEON_ROOM_1:
            self.room_1_cleared = state.is_cleared()
        elif self.current_map_id == C.MAP_DUNGEON_ROOM_2:
            self.room_2_cleared = state.is_cleared()
        elif self.current_map_id == C.MAP_DUNGEON_BOSS:
            boss_alive = any(enemy.is_boss and enemy.alive for enemy in self.enemies)
            if not boss_alive:
                for enemy in self.enemies:
                    if not enemy.is_boss:
                        enemy.alive = False
                self.enemy_projectiles.clear()
                self.boss_defeated = True
                self.active_boss_map_id = None
                if self.ending_cutscene is None:
                    self.ending_cutscene = EndingCutscene()

        if self.room_1_cleared and self.room_2_cleared:
            hub_state = self.map_states.get(C.MAP_DUNGEON_HUB)
            if hub_state is not None:
                hub_state.boss_door_unlocked = True

    def update(self, dt: float, input: Input) -> None:
        if input.is_key_pressed(pygame.K_ESCAPE):
            if self.interaction.is_active:
                self.interaction.close()
            else:
                self.game.quit()
            return

        if self.ending_cutscene is not None:
            self.ending_cutscene.update(dt, input)
            return

        if not self.player.alive:
            if input.is_key_pressed(pygame.K_r):
                self._reset_game()
            return

        if not self._update_boss_timer(dt):
            return

        if self.transition_cooldown > 0:
            self.transition_cooldown -= dt

        if self.message_timer > 0:
            self.message_timer -= dt

        on_overworld = self.current_map_id == C.MAP_OVERWORLD

        if self.interaction.is_active:
            quest_accepted = self.interaction.handle_input(input, self.player)
            if quest_accepted and on_overworld:
                self._spawn_overworld_quest_slimes()
        else:
            if on_overworld and input.is_key_pressed(pygame.K_e):
                self.interaction.try_start(self.player, self.npcs)
            else:
                npc_obstacles = [npc.rect() for npc in self.npcs] if on_overworld else []
                self.projectiles.extend(
                    self.player.update(dt, input, self.world, npc_obstacles)
                )

                new_fireballs: list[EnemyProjectile] = []
                new_summons = []
                for enemy in self.enemies:
                    enemy.update(dt, self.player.pos, self.world)
                    fireballs, summons = enemy.update_boss_abilities(
                        dt,
                        self.player.pos,
                        self.world,
                    )
                    new_fireballs.extend(fireballs)
                    new_summons.extend(summons)
                self.enemy_projectiles.extend(new_fireballs)
                self.enemies.extend(new_summons)

                resolve_combat(self.player, self.enemies, self.world)
                for projectile in self.projectiles:
                    projectile.update(dt, self.world, self.enemies)
                self.projectiles = [
                    projectile for projectile in self.projectiles if projectile.alive
                ]
                for projectile in self.enemy_projectiles:
                    projectile.update(dt, self.world, self.player)
                self.enemy_projectiles = [
                    projectile
                    for projectile in self.enemy_projectiles
                    if projectile.alive
                ]
                resolve_enemy_contact(self.player, self.enemies)
                try_pickup(self.player, self.pickups)
                self._sync_current_state()
                self._try_map_transition()
                self._save_room_progress()
                self._compact_current_state()

        if self.current_map_id == C.MAP_DUNGEON_HUB and self.room_1_cleared and self.room_2_cleared:
            self.world.unlock_boss_door()
            hub_state = self.map_states.get(C.MAP_DUNGEON_HUB)
            if hub_state is not None:
                hub_state.boss_door_unlocked = True

        if self.current_map_id == C.MAP_OVERWORLD:
            self.interaction.update_quest_progress(
                self._current_state().defeated_enemies,
                self.npcs,
            )

        for pickup in self.pickups:
            pickup.bob_timer += dt

        self.camera.follow(self.player.pos)

    def _update_boss_timer(self, dt: float) -> bool:
        if self.active_boss_map_id is None or self.boss_defeated:
            return True

        state = self.map_states.get(self.active_boss_map_id)
        if state is None or state.boss_time_remaining is None:
            return True

        state.boss_time_remaining = max(0.0, state.boss_time_remaining - dt)
        if state.boss_time_remaining > 0:
            return True

        self.boss_timed_out = True
        self.active_boss_map_id = None
        self.player.health = 0
        self.player.alive = False
        self.enemy_projectiles.clear()
        self._show_message("The boss timer expired.", 3.0)
        return False

    def draw(self, screen: pygame.Surface) -> None:
        visible_npcs = self.npcs if self.current_map_id == C.MAP_OVERWORLD else ()
        self.renderer.draw_scene(
            screen=screen,
            world=self.world,
            player=self.player,
            pickups=self.pickups,
            npcs=visible_npcs,
            enemies=self.enemies,
            projectiles=self.projectiles,
            enemy_projectiles=self.enemy_projectiles,
        )
        self._draw_hud(screen)
        self._draw_boss_health_bar(screen)

        if self.current_map_id == C.MAP_OVERWORLD:
            self.interaction.draw(screen, self.player, self.npcs)

        if self.message_timer > 0 and not self.interaction.is_active:
            banner = self.font.render(self.message, True, (240, 230, 180))
            rect = banner.get_rect(center=(config.WINDOW_WIDTH // 2, 90))
            pygame.draw.rect(screen, (30, 30, 40), rect.inflate(20, 10), border_radius=6)
            screen.blit(banner, rect)

        if not self.player.alive:
            self._draw_game_over(screen)
        elif self.ending_cutscene is not None:
            self.ending_cutscene.draw(screen)

    def _draw_hud(self, screen: pygame.Surface) -> None:
        for i in range(self.player.max_health):
            x = 16 + i * 22
            color = (220, 50, 60) if i < self.player.health else (60, 40, 45)
            pygame.draw.circle(screen, color, (x + 8, 20), 8)
            if i < self.player.health:
                pygame.draw.circle(screen, (255, 130, 130), (x + 6, 18), 3)

        rupee_text = self.font.render(f"Rupees: {self.player.rupees}", True, (120, 255, 160))
        screen.blit(rupee_text, (16, 42))

        key_color = (240, 200, 60) if self.player.keys > 0 else (90, 80, 50)
        pygame.draw.circle(screen, key_color, (28, 72), 6)
        key_text = self.font.render(f"x {self.player.keys}", True, (220, 210, 160))
        screen.blit(key_text, (42, 62))

        map_label = self.font.render(self.world.display_name, True, (200, 200, 220))
        screen.blit(map_label, (16, 92))

        weapon_tier = self.player.weapons.tier()
        weapon_text = f"Weapon: {weapon_tier.name}"
        if self.player.weapons.selected == WeaponType.BOW:
            weapon_text += f"  |  Arrows: {self.player.weapons.arrows}"
        weapon_surface = self.font.render(weapon_text, True, (235, 210, 145))
        screen.blit(weapon_surface, (16, 114))

        if self.current_map_id == C.MAP_DUNGEON_HUB:
            status = "Boss door: "
            if self.room_1_cleared and self.room_2_cleared:
                status += "OPEN"
            else:
                cleared = int(self.room_1_cleared) + int(self.room_2_cleared)
                status += f"Sealed ({cleared}/2 rooms cleared)"
            status_surface = self.font.render(status, True, (220, 180, 120))
            screen.blit(status_surface, (16, 136))

        hint = self.font.render(
            "WASD move  |  1/2/3 weapons  |  SPACE attack  |  E talk",
            True,
            (170, 170, 180),
        )
        screen.blit(hint, (config.WINDOW_WIDTH - hint.get_width() - 12, 12))

    def _draw_boss_health_bar(self, screen: pygame.Surface) -> None:
        boss = next(
            (enemy for enemy in self.enemies if enemy.is_boss and enemy.alive),
            None,
        )
        if boss is None:
            return

        bar_width = 560
        bar_height = 18
        bar_x = (config.WINDOW_WIDTH - bar_width) // 2
        bar_y = config.WINDOW_HEIGHT - 42
        health_ratio = max(0.0, min(1.0, boss.health / boss.max_health))

        panel = pygame.Surface((bar_width + 24, 54), pygame.SRCALPHA)
        panel.fill((12, 12, 18, 205))
        screen.blit(panel, (bar_x - 12, bar_y - 27))

        state = self.map_states.get(self.current_map_id)
        seconds_left = (
            state.boss_time_remaining
            if state is not None and state.boss_time_remaining is not None
            else 0
        )
        minutes = int(seconds_left) // 60
        seconds = int(seconds_left) % 60
        label_color = (245, 95, 85) if seconds_left <= 60 else (245, 235, 220)
        label = self.font.render(
            f"{boss.display_name}    {minutes}:{seconds:02d}",
            True,
            label_color,
        )
        screen.blit(label, label.get_rect(center=(config.WINDOW_WIDTH // 2, bar_y - 13)))

        background = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
        pygame.draw.rect(screen, (45, 25, 28), background)
        fill = pygame.Rect(bar_x + 3, bar_y + 3, int((bar_width - 6) * health_ratio), bar_height - 6)
        pygame.draw.rect(screen, (185, 45, 55), fill)
        pygame.draw.line(
            screen,
            (245, 105, 95),
            (fill.left, fill.top),
            (fill.right, fill.top),
            2,
        )
        pygame.draw.rect(screen, (215, 195, 170), background, width=2)

    def _draw_game_over(self, screen: pygame.Surface) -> None:
        overlay = pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        title_text = "TIME'S UP" if self.boss_timed_out else "GAME OVER"
        title = self.title_font.render(title_text, True, (230, 80, 80))
        title_rect = title.get_rect(center=(config.WINDOW_WIDTH // 2, config.WINDOW_HEIGHT // 2 - 20))
        screen.blit(title, title_rect)

        restart = self.font.render("Press R to restart", True, (220, 220, 220))
        restart_rect = restart.get_rect(center=(config.WINDOW_WIDTH // 2, config.WINDOW_HEIGHT // 2 + 24))
        screen.blit(restart, restart_rect)

