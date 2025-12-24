# main.py
import pygame
from ui import AppUI
from PIL import Image


def create_icon():
    """Создаёт иконку с буквой H на тёмном фоне"""
    # Размер иконки (рекомендуется 32x32 или 64x64)
    size = 64

    # Создаём поверхность с альфа-каналом (прозрачностью)
    icon = pygame.Surface((size, size), pygame.SRCALPHA)

    # Фон: 1e1e23 в RGB = (30, 30, 35)
    icon.fill((30, 30, 35, 255))

    # Создаём шрифт для буквы H
    try:
        # Пробуем загрузить системный шрифт
        font = pygame.font.SysFont("Arial", size - 20, bold=True)
    except:
        # Если не получилось, создаём простой
        font = pygame.font.Font(None, size - 20)

    # Рендерим белую букву H
    text_surface = font.render("H", True, (255, 255, 255))  # Белый цвет

    # Получаем размеры текста
    text_rect = text_surface.get_rect()

    # Центрируем текст на иконке
    text_rect.center = (size // 2, size // 2)

    # Рисуем текст на иконке
    icon.blit(text_surface, text_rect)

    return icon


def main():
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Hex")

    # Создаём и устанавливаем иконку
    icon = create_icon()
    pygame.display.set_icon(icon)

    AppUI(screen).run()


if __name__ == "__main__":
    main()