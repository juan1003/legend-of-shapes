from __future__ import annotations

from typing import TYPE_CHECKING

from engine.scene import Scene

if TYPE_CHECKING:
    from engine.game import Game


class SceneManager:
    def __init__(self, game: Game) -> None:
        self.game = game
        self._scenes: dict[str, Scene] = {}
        self._current: Scene | None = None
        self._pending_scene: str | None = None

    def register(self, name: str, scene: Scene) -> None:
        self._scenes[name] = scene

    def switch_to(self, name: str) -> None:
        if name not in self._scenes:
            raise KeyError(f"Scene '{name}' is not registered")
        self._pending_scene = name

    def apply_pending_switch(self) -> None:
        if self._pending_scene is None:
            return

        if self._current is not None:
            self._current.on_exit()

        self._current = self._scenes[self._pending_scene]
        self._pending_scene = None
        self._current.on_enter()

    @property
    def current(self) -> Scene | None:
        return self._current
