import pygame

from engine.renderer3d import PerspectiveCamera, Renderer3D


def test_perspective_camera_centers_its_follow_target() -> None:
    camera = PerspectiveCamera((800, 600))
    target = pygame.Vector2(320, 240)

    camera.follow(target)

    assert camera.project(target.x, 16, target.y) == (400, 288)


def test_perspective_camera_projects_height_upward() -> None:
    camera = PerspectiveCamera((800, 600))
    target = pygame.Vector2(320, 240)
    camera.follow(target)

    ground = camera.project(target.x, 0, target.y)
    elevated = camera.project(target.x, 40, target.y)

    assert elevated[1] < ground[1]


def test_perspective_camera_depth_increases_away_from_camera() -> None:
    camera = PerspectiveCamera((800, 600))
    target = pygame.Vector2(320, 240)
    camera.follow(target)

    near_depth = camera.depth(target.x - 64, 0, target.y - 64)
    far_depth = camera.depth(target.x + 64, 0, target.y + 64)

    assert far_depth > near_depth


def test_color_shading_clamps_channels() -> None:
    assert Renderer3D._shade((250, 100, 20), 1.5) == (255, 150, 30)
