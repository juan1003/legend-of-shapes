from __future__ import annotations

from enum import Enum, auto

import pygame

import config
from engine.input import Input


class EndingStage(Enum):
    ARRIVAL = auto()
    THANKS = auto()
    GIFT = auto()
    END = auto()


class EndingCutscene:
    STAGE_DURATION = 3.5

    def __init__(self) -> None:
        self.stage = EndingStage.ARRIVAL
        self.timer = 0.0
        self.font = pygame.font.SysFont(None, 28)
        self.small_font = pygame.font.SysFont(None, 22)
        self.title_font = pygame.font.SysFont(None, 64)

    @property
    def has_ended(self) -> bool:
        return self.stage == EndingStage.END

    def update(self, dt: float, input: Input) -> None:
        if self.has_ended:
            return

        self.timer += dt
        advance_pressed = input.is_key_pressed(pygame.K_e) or input.is_key_pressed(
            pygame.K_SPACE
        )
        if self.timer >= self.STAGE_DURATION or advance_pressed:
            self._advance()

    def _advance(self) -> None:
        stages = list(EndingStage)
        index = stages.index(self.stage)
        self.stage = stages[min(index + 1, len(stages) - 1)]
        self.timer = 0.0

    def draw(self, screen: pygame.Surface) -> None:
        if self.stage == EndingStage.END:
            self._draw_end_screen(screen)
            return

        overlay = pygame.Surface(
            (config.WINDOW_WIDTH, config.WINDOW_HEIGHT),
            pygame.SRCALPHA,
        )
        overlay.fill((12, 18, 42, 225))
        screen.blit(overlay, (0, 0))

        self._draw_celestial_light(screen)
        self._draw_angel(screen, (config.WINDOW_WIDTH // 2, 230))
        self._draw_player(screen, (config.WINDOW_WIDTH // 2, 435))

        if self.stage == EndingStage.GIFT:
            self._draw_crystal(screen, (config.WINDOW_WIDTH // 2, 345), 22)

        self._draw_dialogue(screen)

    def _draw_celestial_light(self, screen: pygame.Surface) -> None:
        center_x = config.WINDOW_WIDTH // 2
        for offset in (-170, -110, -55, 55, 110, 170):
            pygame.draw.line(
                screen,
                (90, 130, 210),
                (center_x, 40),
                (center_x + offset, 390),
                3,
            )
        pygame.draw.circle(screen, (120, 155, 225), (center_x, 175), 115, 3)

    def _draw_angel(
        self,
        screen: pygame.Surface,
        center: tuple[int, int],
    ) -> None:
        x, y = center

        left_wing = pygame.Rect(x - 112, y - 60, 82, 135)
        right_wing = pygame.Rect(x + 30, y - 60, 82, 135)
        pygame.draw.ellipse(screen, (225, 235, 255), left_wing)
        pygame.draw.ellipse(screen, (225, 235, 255), right_wing)
        pygame.draw.ellipse(screen, (165, 195, 240), left_wing, 3)
        pygame.draw.ellipse(screen, (165, 195, 240), right_wing, 3)

        dress = [
            (x, y - 12),
            (x - 38, y + 92),
            (x + 38, y + 92),
        ]
        pygame.draw.polygon(screen, (238, 240, 255), dress)
        pygame.draw.polygon(screen, (150, 185, 235), dress, 3)

        pygame.draw.circle(screen, (242, 195, 155), (x, y - 44), 23)
        pygame.draw.arc(
            screen,
            (230, 205, 90),
            pygame.Rect(x - 34, y - 92, 68, 25),
            0,
            3.14,
            4,
        )

        hair = pygame.Rect(x - 25, y - 70, 50, 45)
        pygame.draw.arc(screen, (225, 190, 85), hair, 0, 3.14, 8)
        pygame.draw.circle(screen, (70, 85, 120), (x - 8, y - 47), 2)
        pygame.draw.circle(screen, (70, 85, 120), (x + 8, y - 47), 2)

        pygame.draw.line(screen, (242, 195, 155), (x - 12, y), (x - 48, y + 30), 7)
        pygame.draw.line(screen, (242, 195, 155), (x + 12, y), (x + 48, y + 30), 7)

    def _draw_player(
        self,
        screen: pygame.Surface,
        center: tuple[int, int],
    ) -> None:
        x, y = center
        pygame.draw.rect(
            screen,
            (45, 125, 65),
            pygame.Rect(x - 13, y - 8, 26, 32),
            border_radius=5,
        )
        pygame.draw.circle(screen, (238, 190, 140), (x, y - 17), 11)
        pygame.draw.polygon(
            screen,
            (35, 90, 50),
            [(x - 15, y - 28), (x + 15, y - 28), (x, y - 45)],
        )

    def _draw_crystal(
        self,
        screen: pygame.Surface,
        center: tuple[int, int],
        size: int,
    ) -> None:
        x, y = center
        points = [(x, y - size), (x + size, y), (x, y + size), (x - size, y)]
        pygame.draw.polygon(screen, (45, 130, 245), points)
        pygame.draw.polygon(screen, (145, 210, 255), points, 3)
        pygame.draw.polygon(
            screen,
            (110, 190, 255),
            [(x, y - size + 5), (x + 6, y), (x, y + 7), (x - 6, y)],
        )

    def _draw_dialogue(self, screen: pygame.Surface) -> None:
        box = pygame.Rect(90, config.WINDOW_HEIGHT - 105, config.WINDOW_WIDTH - 180, 78)
        pygame.draw.rect(screen, (22, 28, 50), box, border_radius=8)
        pygame.draw.rect(screen, (125, 160, 225), box, width=2, border_radius=8)

        if self.stage == EndingStage.ARRIVAL:
            text = "A radiant figure descends into the silent chamber..."
        elif self.stage == EndingStage.THANKS:
            text = '"Brave hero, thank you. Your courage has restored the light."'
        else:
            text = '"Accept this Azure Crystal, symbol of hope and a world made free."'

        surface = self.font.render(text, True, (235, 240, 255))
        screen.blit(surface, surface.get_rect(center=(box.centerx, box.centery - 7)))

        hint = self.small_font.render("E / SPACE to continue", True, (155, 175, 215))
        screen.blit(hint, hint.get_rect(center=(box.centerx, box.bottom - 14)))

    def _draw_end_screen(self, screen: pygame.Surface) -> None:
        screen.fill((10, 16, 34))
        center_x = config.WINDOW_WIDTH // 2
        self._draw_crystal(screen, (center_x, 215), 42)

        title = self.title_font.render("THE END", True, (220, 235, 255))
        screen.blit(title, title.get_rect(center=(center_x, 320)))

        subtitle = self.font.render(
            "The Azure Crystal shines over a peaceful land.",
            True,
            (115, 175, 245),
        )
        screen.blit(subtitle, subtitle.get_rect(center=(center_x, 372)))

        quit_hint = self.small_font.render("Press ESC to quit", True, (135, 145, 175))
        screen.blit(quit_hint, quit_hint.get_rect(center=(center_x, 445)))
