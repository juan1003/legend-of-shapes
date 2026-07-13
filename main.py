from engine.game import Game
from scenes.game_scene import GameScene


def main() -> None:
    game = Game()
    game.scene_manager.register("game", GameScene(game))
    game.scene_manager.switch_to("game")
    game.run()


if __name__ == "__main__":
    main()
