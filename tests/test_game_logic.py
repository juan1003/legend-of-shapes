from types import SimpleNamespace

import pygame
import pytest

import config
from engine.input import Input
from game import constants as C
from game.collision import circle_rect_overlap
from game.cutscene import EndingCutscene, EndingStage
from game.entities import (
    Enemy,
    EnemyProjectile,
    EnemyType,
    Player,
    create_boss,
    resolve_combat,
)
from game.interaction import InteractionManager, InteractionMode
from game.map_state import MapState, build_map_state
from game.maps import MAP_DEFINITIONS
from game.npcs import NPCType, Quest, create_npcs
from game.weapons import Projectile, WEAPON_TIERS, WeaponInventory, WeaponType
from game.world import GameWorld
from scenes.game_scene import GameScene


def test_all_maps_are_rectangular_and_links_resolve():
    for map_id, definition in MAP_DEFINITIONS.items():
        rows = definition.layout.strip().splitlines()
        assert rows
        assert len({len(row) for row in rows}) == 1

        world = GameWorld(map_id)
        assert world.width == len(rows[0])
        assert world.height == len(rows)
        for transition_id, link in definition.links.items():
            assert transition_id in world.spawn.transitions
            assert link.target_map in MAP_DEFINITIONS
            target = GameWorld(link.target_map)
            assert link.target_spawn in target.spawn.spawn_points


def test_spawn_markers_keep_expected_terrain():
    overworld = GameWorld(C.MAP_OVERWORLD)
    player_tile = (
        int(overworld.spawn.player_pos.x // C.TILE_SIZE),
        int(overworld.spawn.player_pos.y // C.TILE_SIZE),
    )
    assert overworld.get_tile(*player_tile) == C.TILE_PATH

    for pos in overworld.spawn.enemy_positions:
        assert overworld.get_tile(
            int(pos.x // C.TILE_SIZE), int(pos.y // C.TILE_SIZE)
        ) == C.TILE_GRASS


def test_transition_spawn_is_not_on_trigger_tile():
    for definition in MAP_DEFINITIONS.values():
        for link in definition.links.values():
            target = GameWorld(link.target_map)
            spawn = target.get_spawn_for_transition(link.target_spawn)
            assert target.get_transition_at(spawn) is None


def test_opened_regular_door_can_be_restored():
    world = GameWorld(C.MAP_OVERWORLD)
    door_rect = world.tile_rect(14, 17)
    world.tiles[17][14] = C.TILE_DOOR

    opened = world.open_door_at(door_rect)
    assert opened == {(14, 17)}

    state = MapState(opened_doors=opened)
    restored = GameWorld(C.MAP_OVERWORLD)
    restored.tiles[17][14] = C.TILE_DOOR
    restored.apply_opened_doors(state.opened_doors)
    assert restored.get_tile(14, 17) == C.TILE_PATH


def test_player_consumes_one_key_only_for_new_door():
    world = GameWorld(C.MAP_OVERWORLD)
    world.tiles[17][14] = C.TILE_DOOR
    player = Player(pygame.Vector2(14.5 * C.TILE_SIZE, 17.5 * C.TILE_SIZE))
    player.keys = 2

    assert player.try_open_door(world)
    assert player.keys == 1
    assert not player.try_open_door(world)
    assert player.keys == 1


def test_overworld_is_a_town_without_loose_keys_rupees_or_locked_doors():
    world = GameWorld(C.MAP_OVERWORLD)

    assert world.display_name == "Willow Town"
    assert not world.spawn.key_positions
    assert not world.spawn.rupee_positions
    assert all(C.TILE_DOOR not in row for row in world.tiles)
    assert sum(row.count(C.TILE_HOUSE) for row in world.tiles) >= 50

    for npc in create_npcs():
        assert not world.collides_rect(npc.rect())


def test_room_state_tracks_defeated_enemies_after_compaction():
    state = MapState(enemies=[Enemy(pygame.Vector2(10, 10))])
    state.enemies[0].alive = False
    state.compact()

    assert state.enemies == []
    assert state.defeated_enemies == 1
    assert state.is_cleared()


def test_boss_door_unlock_requires_both_rooms():
    hub = GameWorld(C.MAP_DUNGEON_HUB)
    assert not hub.boss_door_unlocked

    room_1 = MapState(enemies=[])
    room_2 = MapState(enemies=[Enemy(pygame.Vector2(10, 10))])
    assert room_1.is_cleared()
    assert not room_2.is_cleared()

    room_2.enemies.clear()
    assert room_2.is_cleared()
    hub.unlock_boss_door()
    assert hub.boss_door_unlocked


def test_quest_readiness_uses_persisted_progress():
    quest = Quest(
        id="test",
        title="Test",
        description="Defeat enemies",
        target_count=4,
        reward_rupees=10,
        reward_hearts=2,
        accepted=True,
    )
    quest.progress = 3
    assert not quest.is_ready_to_turn_in()
    quest.progress = 4
    assert quest.is_ready_to_turn_in()


def test_overworld_slimes_spawn_once_when_elder_quest_is_accepted():
    world = GameWorld(C.MAP_OVERWORLD)
    state = build_map_state(world, spawn_regular_enemies=False)
    elder = next(npc for npc in create_npcs() if npc.id == "elder")
    player = Player(elder.pos)
    interaction = InteractionManager()
    input_state = Input()

    assert state.enemies == []
    assert interaction.try_start(player, [elder])
    input_state.update([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_y)])
    assert interaction.handle_input(input_state, player)

    scene = GameScene.__new__(GameScene)
    scene.world = world
    scene.map_states = {C.MAP_OVERWORLD: state}
    scene.message = ""
    scene.message_timer = 0.0
    scene._spawn_overworld_quest_slimes()
    scene._spawn_overworld_quest_slimes()

    assert state.quest_enemies_spawned
    assert len(state.enemies) == C.QUEST_SLIME_TARGET


def test_collision_helpers_cover_inside_and_outside_cases():
    rect = pygame.Rect(10, 10, 20, 20)
    assert circle_rect_overlap(pygame.Vector2(15, 15), 2, rect)
    assert not circle_rect_overlap(pygame.Vector2(50, 50), 2, rect)


def test_sword_cannot_hit_through_solid_tile():
    world = GameWorld(C.MAP_OVERWORLD)
    world.tiles[10][10] = C.TILE_WALL
    player = Player(pygame.Vector2(9.5 * C.TILE_SIZE, 10.5 * C.TILE_SIZE))
    player.facing = pygame.Vector2(1, 0)
    player.attack_timer = C.SWORD_DURATION
    enemy = Enemy(pygame.Vector2(10.5 * C.TILE_SIZE, 10.5 * C.TILE_SIZE))

    resolve_combat(player, [enemy], world)
    assert enemy.health == C.ENEMY_HEALTH


def test_successful_hits_apply_visible_knockback_and_brief_stagger():
    world = GameWorld(C.MAP_OVERWORLD)
    enemy = Enemy(pygame.Vector2(560, 336))
    start = enemy.pos.copy()

    assert enemy.take_damage(
        1,
        WeaponType.SWORD,
        pygame.Vector2(3, 4),
        world,
    )

    assert enemy.pos.distance_to(start) == pytest.approx(C.ENEMY_KNOCKBACK)
    knocked_position = enemy.pos.copy()
    enemy.update(C.ENEMY_HIT_STAGGER / 2, start, world)
    assert enemy.pos == knocked_position


def test_boss_arena_is_open_and_lava_is_solid():
    world = GameWorld(C.MAP_DUNGEON_BOSS)
    boss_pos = world.spawn.boss_positions[0]
    player_spawn = world.get_spawn_for_transition("from_hub")

    assert world.has_line_of_sight(player_spawn, boss_pos)
    assert world.get_tile(0, 0) == C.TILE_LAVA
    assert world.is_solid(C.TILE_LAVA)

    boss_x = int(boss_pos.x // C.TILE_SIZE)
    boss_y = int(boss_pos.y // C.TILE_SIZE)
    for x, y in (
        (boss_x - 1, boss_y),
        (boss_x + 1, boss_y),
        (boss_x, boss_y - 1),
        (boss_x, boss_y + 1),
    ):
        assert not world.is_solid(world.get_tile(x, y))


def test_dinosaurs_are_friendly_npcs():
    dinosaurs = [npc for npc in create_npcs() if npc.kind == NPCType.DINOSAUR]

    assert {npc.name for npc in dinosaurs} == {
        "Dax the Dinosaur",
        "Fern the Dinosaur",
    }
    assert all(npc.dialogue_lines for npc in dinosaurs)


def test_linda_is_a_pink_dinosaur_shopkeeper():
    linda = next(npc for npc in create_npcs() if npc.id == "linda")
    player = Player(linda.pos)
    interaction = InteractionManager()

    assert linda.kind == NPCType.DINOSAUR_SHOPKEEPER
    assert linda.body_color[0] > linda.body_color[1]
    assert len(linda.shop_items) == 6
    assert interaction.try_start(player, [linda])
    assert interaction.mode == InteractionMode.SHOP


def test_dungeon_rooms_spawn_croc_enemies():
    for map_id in (C.MAP_DUNGEON_ROOM_1, C.MAP_DUNGEON_ROOM_2):
        world = GameWorld(map_id)
        state = build_map_state(world)
        crocs = [enemy for enemy in state.enemies if enemy.kind == EnemyType.CROC]

        assert len(crocs) == 2
        assert all(enemy.health == C.CROC_HEALTH for enemy in crocs)


def test_npc_rect_blocks_player_movement():
    world = GameWorld(C.MAP_OVERWORLD)
    player = Player(pygame.Vector2(200, 200))
    blocker = pygame.Rect(210, 189, C.NPC_SIZE, C.NPC_SIZE)

    player._move(pygame.Vector2(20, 0), world, [blocker])
    assert player.pos == pygame.Vector2(200, 200)


def test_focus_loss_clears_held_input():
    input_state = Input()
    input_state.update([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w)])
    assert input_state.is_key_down(pygame.K_w)

    input_state.update([pygame.event.Event(pygame.WINDOWFOCUSLOST)])
    assert not input_state.is_key_down(pygame.K_w)


def test_ending_cutscene_reaches_the_end_screen():
    cutscene = EndingCutscene()
    input_state = Input()

    assert cutscene.stage == EndingStage.ARRIVAL
    for expected in (EndingStage.THANKS, EndingStage.GIFT, EndingStage.END):
        input_state.update([])
        cutscene.update(cutscene.STAGE_DURATION, input_state)
        assert cutscene.stage == expected

    assert cutscene.has_ended


def test_maps_switch_between_overworld_dungeon_and_boss_music():
    class RecordingAudio:
        def __init__(self):
            self.paths = []

        def play_music(self, path, **kwargs):
            self.paths.append(path)
            return True

    audio = RecordingAudio()
    scene = GameScene.__new__(GameScene)
    scene.game = SimpleNamespace(audio=audio)

    scene.current_map_id = C.MAP_OVERWORLD
    scene._switch_map_music()
    scene.current_map_id = C.MAP_DUNGEON_HUB
    scene._switch_map_music()
    scene.current_map_id = C.MAP_DUNGEON_BOSS
    scene._switch_map_music()

    assert audio.paths[0].name == "korobeiniki_test.wav"
    assert audio.paths[1].name == "dungeon_castle_original.wav"
    assert audio.paths[2].name == "boss_battle_original.wav"


def test_testing_loadout_starts_with_all_base_weapons():
    inventory = WeaponInventory()

    assert inventory.tier().name == "Rusty Sword"
    assert inventory.is_unlocked(WeaponType.SWORD)
    assert inventory.is_unlocked(WeaponType.BOW)
    assert inventory.is_unlocked(WeaponType.GUN)
    assert inventory.arrows == config.TEST_STARTING_ARROWS
    assert inventory.equip(WeaponType.BOW)


def test_linda_sells_weapons_arrows_and_upgrades():
    linda = next(npc for npc in create_npcs() if npc.id == "linda")
    player = Player(linda.pos)
    player.weapons = WeaponInventory(
        levels={
            WeaponType.SWORD: 1,
            WeaponType.BOW: 0,
            WeaponType.GUN: 0,
        },
        arrows=0,
    )
    player.rupees = 200
    interaction = InteractionManager()
    interaction.try_start(player, [linda])

    interaction._buy_item(player, 0)
    assert player.weapons.is_unlocked(WeaponType.BOW)
    assert player.weapons.arrows == 5

    interaction._buy_item(player, 2)
    assert player.weapons.arrows == 15

    interaction._buy_item(player, 1)
    assert player.weapons.is_unlocked(WeaponType.GUN)

    interaction._buy_item(player, 3)
    assert player.weapons.levels[WeaponType.SWORD] == 2
    assert player.weapons.tier(WeaponType.SWORD).name == "Iron Sword"


def test_bow_consumes_arrows_and_gun_has_unlimited_ammo():
    player = Player(pygame.Vector2(200, 200))
    player.facing = pygame.Vector2(1, 0)
    player.weapons.unlock(WeaponType.BOW)
    player.weapons.arrows = 1
    player.weapons.equip(WeaponType.BOW)

    arrow = player.attack()
    assert arrow is not None and arrow.weapon == WeaponType.BOW
    assert player.weapons.arrows == 0
    player.attack_cooldown = 0
    assert player.attack() is None

    player.weapons.unlock(WeaponType.GUN)
    player.weapons.equip(WeaponType.GUN)
    first_bullet = player.attack()
    player.attack_cooldown = 0
    second_bullet = player.attack()
    assert first_bullet is not None and second_bullet is not None
    assert first_bullet.weapon == WeaponType.GUN


def test_number_keys_switch_unlocked_weapons():
    world = GameWorld(C.MAP_OVERWORLD)
    player = Player(world.spawn.player_pos)
    player.weapons.unlock(WeaponType.BOW)
    input_state = Input()
    input_state.update([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2)])

    player.update(0, input_state, world)
    assert player.weapons.selected == WeaponType.BOW


def test_projectiles_expire_hit_enemies_and_stop_at_walls():
    world = GameWorld(C.MAP_OVERWORLD)
    enemy = Enemy(
        pygame.Vector2(200, 200),
        kind=EnemyType.CROC,
    )
    hit = Projectile(
        pos=enemy.pos.copy(),
        velocity=pygame.Vector2(1, 0),
        weapon=WeaponType.BOW,
        damage=1,
        max_range=100,
    )
    hit.update(0, world, [enemy])
    assert enemy.health == 0
    assert not hit.alive

    expiring = Projectile(
        pos=pygame.Vector2(200, 200),
        velocity=pygame.Vector2(10, 0),
        weapon=WeaponType.BOW,
        damage=1,
        max_range=5,
    )
    expiring.update(1, world, [])
    assert not expiring.alive

    world.tiles[6][7] = C.TILE_WALL
    blocked = Projectile(
        pos=pygame.Vector2(6.5 * C.TILE_SIZE, 6.5 * C.TILE_SIZE),
        velocity=pygame.Vector2(40, 0),
        weapon=WeaponType.GUN,
        damage=1,
        max_range=100,
    )
    blocked.update(1, world, [])
    assert not blocked.alive


def test_enemy_weapon_immunities_and_weaknesses():
    slime = Enemy(pygame.Vector2())
    slime.take_damage(99, WeaponType.BOW)
    slime.take_damage(99, WeaponType.GUN)
    assert slime.health == C.ENEMY_HEALTH
    slime.take_damage(1, WeaponType.SWORD)
    assert slime.health == C.ENEMY_HEALTH - 1

    croc = Enemy(pygame.Vector2(), kind=EnemyType.CROC)
    croc.take_damage(99, WeaponType.GUN)
    assert croc.health == C.CROC_HEALTH
    croc.take_damage(1, WeaponType.BOW)
    assert not croc.alive


def test_big_slime_boss_inherits_slime_immunities():
    boss = create_boss(pygame.Vector2())
    starting_health = boss.health

    boss.take_damage(99, WeaponType.BOW)
    boss.take_damage(99, WeaponType.GUN)
    assert boss.health == starting_health
    assert boss.alive

    boss.take_damage(1, WeaponType.SWORD)
    assert boss.health == starting_health - 1


def test_sword_hits_boss_only_once_per_swing():
    world = GameWorld(C.MAP_OVERWORLD)
    player = Player(pygame.Vector2(200, 200))
    player.facing = pygame.Vector2(1, 0)
    boss = create_boss(pygame.Vector2(225, 200))
    player.attack()

    resolve_combat(player, [boss], world)
    resolve_combat(player, [boss], world)

    assert boss.health == boss.max_health - player.weapons.tier(WeaponType.SWORD).damage


def test_boss_health_bar_renders_for_living_boss():
    scene = GameScene.__new__(GameScene)
    scene.enemies = [create_boss(pygame.Vector2())]
    scene.font = pygame.font.SysFont(None, 24)
    scene.current_map_id = C.MAP_DUNGEON_BOSS
    scene.map_states = {
        C.MAP_DUNGEON_BOSS: MapState(
            boss_time_remaining=C.BOSS_TIME_LIMIT,
        )
    }
    screen = pygame.Surface((800, 600), pygame.SRCALPHA)

    scene._draw_boss_health_bar(screen)

    assert pygame.mask.from_surface(screen).count() > 0


def test_boss_timer_expires_after_ten_minutes_even_outside_room():
    scene = GameScene.__new__(GameScene)
    scene.active_boss_map_id = C.MAP_DUNGEON_BOSS
    scene.current_map_id = C.MAP_OVERWORLD
    scene.boss_defeated = False
    scene.boss_timed_out = False
    scene.player = Player(pygame.Vector2())
    scene.enemy_projectiles = []
    scene.map_states = {
        C.MAP_DUNGEON_BOSS: MapState(
            boss_time_remaining=C.BOSS_TIME_LIMIT,
        )
    }

    assert scene._update_boss_timer(C.BOSS_TIME_LIMIT - 1)
    assert scene.map_states[C.MAP_DUNGEON_BOSS].boss_time_remaining == 1
    assert not scene._update_boss_timer(1)
    assert scene.boss_timed_out
    assert not scene.player.alive


def test_big_slime_fires_every_five_seconds_and_summons_every_ten():
    world = GameWorld(C.MAP_DUNGEON_BOSS)
    boss = create_boss(world.spawn.boss_positions[0])
    player_pos = world.get_spawn_for_transition("from_hub")

    fireballs, summons = boss.update_boss_abilities(4.9, player_pos, world)
    assert fireballs == [] and summons == []

    fireballs, summons = boss.update_boss_abilities(0.1, player_pos, world)
    assert len(fireballs) == 1
    assert summons == []

    fireballs, summons = boss.update_boss_abilities(5.0, player_pos, world)
    assert len(fireballs) == 1
    assert len(summons) == 1
    assert summons[0].kind == EnemyType.SLIME


def test_boss_fireball_damages_player():
    world = GameWorld(C.MAP_OVERWORLD)
    player = Player(pygame.Vector2(200, 200))
    fireball = EnemyProjectile(
        pos=player.pos.copy(),
        velocity=pygame.Vector2(1, 0),
    )

    fireball.update(0, world, player)

    assert player.health == C.PLAYER_MAX_HEALTH - C.BOSS_FIREBALL_DAMAGE
    assert not fireball.alive


def test_guns_are_shorter_ranged_than_bows():
    gun_ranges = [tier.projectile_range for tier in WEAPON_TIERS[WeaponType.GUN]]
    bow_ranges = [tier.projectile_range for tier in WEAPON_TIERS[WeaponType.BOW]]

    assert max(gun_ranges) <= 220
    assert all(gun_range < bow_range for gun_range, bow_range in zip(gun_ranges, bow_ranges))


def test_all_sword_tiers_render_idle_and_attacking():
    screen = pygame.Surface((160, 160))
    player = Player(pygame.Vector2(80, 80))
    player.weapons.selected = WeaponType.SWORD

    for level in (1, 2, 3):
        player.weapons.levels[WeaponType.SWORD] = level
        player.attack_timer = 0
        player.draw(screen, pygame.Vector2())
        player.attack_timer = C.SWORD_DURATION
        player.draw(screen, pygame.Vector2())

    assert pygame.mask.from_surface(screen).count() > 0
