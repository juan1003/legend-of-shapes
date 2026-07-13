import pygame


def rects_overlap(a: pygame.Rect, b: pygame.Rect) -> bool:
    return a.colliderect(b)


def circle_rect_overlap(center: pygame.Vector2, radius: float, rect: pygame.Rect) -> bool:
    closest_x = max(rect.left, min(center.x, rect.right))
    closest_y = max(rect.top, min(center.y, rect.bottom))
    dx = center.x - closest_x
    dy = center.y - closest_y
    return (dx * dx + dy * dy) <= radius * radius
