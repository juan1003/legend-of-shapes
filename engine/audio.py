from __future__ import annotations

from pathlib import Path

import pygame


class AudioManager:
    def __init__(self) -> None:
        self.enabled = True
        self.current_music: Path | None = None
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
        except pygame.error:
            self.enabled = False

    def play_music(
        self,
        path: str | Path,
        volume: float = 0.4,
        loops: int = -1,
        fade_ms: int = 350,
    ) -> bool:
        music_path = Path(path).resolve()
        if not self.enabled or not music_path.is_file():
            return False
        if self.current_music == music_path and pygame.mixer.music.get_busy():
            return True

        try:
            pygame.mixer.music.load(str(music_path))
            pygame.mixer.music.set_volume(max(0.0, min(volume, 1.0)))
            pygame.mixer.music.play(loops, fade_ms=fade_ms)
        except pygame.error:
            return False
        self.current_music = music_path
        return True

    def stop_music(self, fade_ms: int = 0) -> None:
        if not self.enabled:
            return
        if fade_ms > 0:
            pygame.mixer.music.fadeout(fade_ms)
        else:
            pygame.mixer.music.stop()
        self.current_music = None
