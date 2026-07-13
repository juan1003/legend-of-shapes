from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pygame

from engine.input import Input

if TYPE_CHECKING:
    from engine.game import Game


class Scene(ABC):
    def __init__(self, game: Game) -> None:
        self.game = game

    def on_enter(self) -> None:
        pass

    def on_exit(self) -> None:
        pass

    @abstractmethod
    def update(self, dt: float, input: Input) -> None:
        pass

    @abstractmethod
    def draw(self, screen: pygame.Surface) -> None:
        pass
