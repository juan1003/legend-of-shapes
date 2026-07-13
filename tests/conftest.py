import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pygame
import pytest


@pytest.fixture(scope="session", autouse=True)
def pygame_runtime():
    pygame.init()
    yield
    pygame.quit()
