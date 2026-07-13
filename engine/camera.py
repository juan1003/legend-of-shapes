import pygame

import config


class Camera:
    def __init__(self, world_width: int, world_height: int) -> None:
        self.world_width = world_width
        self.world_height = world_height
        self.offset = pygame.Vector2(0, 0)

    def follow(self, target: pygame.Vector2) -> None:
        if self.world_width <= config.WINDOW_WIDTH:
            self.offset.x = (self.world_width - config.WINDOW_WIDTH) / 2
        else:
            self.offset.x = target.x - config.WINDOW_WIDTH / 2
            self.offset.x = max(0, min(self.offset.x, self.world_width - config.WINDOW_WIDTH))

        if self.world_height <= config.WINDOW_HEIGHT:
            self.offset.y = (self.world_height - config.WINDOW_HEIGHT) / 2
        else:
            self.offset.y = target.y - config.WINDOW_HEIGHT / 2
            self.offset.y = max(0, min(self.offset.y, self.world_height - config.WINDOW_HEIGHT))

    def world_to_screen(self, pos: pygame.Vector2) -> tuple[int, int]:
        return int(pos.x - self.offset.x), int(pos.y - self.offset.y)

    def world_rect_to_screen(self, rect: pygame.Rect) -> pygame.Rect:
        return rect.move(-int(self.offset.x), -int(self.offset.y))
