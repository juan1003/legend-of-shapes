from __future__ import annotations

from pathlib import Path

import pygame

import config
from engine.audio import AudioManager
from engine.input import Input
from engine.scene_manager import SceneManager


class Game:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        pygame.display.set_caption(config.WINDOW_TITLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.input = Input()
        self.audio = AudioManager()
        self.scene_manager = SceneManager(self)
        test_music = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "music"
            / "korobeiniki_test.wav"
        )
        self.audio.play_music(test_music, volume=0.3)

    def quit(self) -> None:
        self.running = False

    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(config.TARGET_FPS) / 1000.0, config.MAX_DELTA_TIME)
            events = pygame.event.get()
            self.input.update(events)

            if self.input.quit_requested:
                self.quit()

            self.scene_manager.apply_pending_switch()
            scene = self.scene_manager.current
            if scene is not None:
                scene.update(dt, self.input)
                scene.draw(self.screen)

            pygame.display.flip()

        pygame.quit()
