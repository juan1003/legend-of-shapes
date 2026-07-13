import pygame


class Input:
    def __init__(self):
        self._keys_down: set[int] = set()
        self._keys_pressed: set[int] = set()
        self._keys_released: set[int] = set()
        self._mouse_pos = (0, 0)
        self._mouse_buttons_down: set[int] = set()
        self._mouse_buttons_pressed: set[int] = set()
        self._mouse_buttons_released: set[int] = set()
        self.quit_requested = False

    def update(self, events: list[pygame.event.Event]) -> None:
        self._keys_pressed.clear()
        self._keys_released.clear()
        self._mouse_buttons_pressed.clear()
        self._mouse_buttons_released.clear()

        for event in events:
            if event.type == pygame.QUIT:
                self.quit_requested = True
            elif event.type == pygame.WINDOWFOCUSLOST:
                self._keys_down.clear()
                self._mouse_buttons_down.clear()
            elif event.type == pygame.KEYDOWN:
                if event.key not in self._keys_down:
                    self._keys_pressed.add(event.key)
                self._keys_down.add(event.key)
            elif event.type == pygame.KEYUP:
                self._keys_down.discard(event.key)
                self._keys_released.add(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button not in self._mouse_buttons_down:
                    self._mouse_buttons_pressed.add(event.button)
                self._mouse_buttons_down.add(event.button)
            elif event.type == pygame.MOUSEBUTTONUP:
                self._mouse_buttons_down.discard(event.button)
                self._mouse_buttons_released.add(event.button)

        self._mouse_pos = pygame.mouse.get_pos()

    def is_key_down(self, key: int) -> bool:
        return key in self._keys_down

    def is_key_pressed(self, key: int) -> bool:
        return key in self._keys_pressed

    def is_key_released(self, key: int) -> bool:
        return key in self._keys_released

    def is_mouse_button_down(self, button: int) -> bool:
        return button in self._mouse_buttons_down

    def is_mouse_button_pressed(self, button: int) -> bool:
        return button in self._mouse_buttons_pressed

    @property
    def mouse_pos(self) -> tuple[int, int]:
        return self._mouse_pos
