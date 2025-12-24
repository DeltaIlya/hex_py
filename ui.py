# ui.py
from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from typing import Optional, Tuple

import pygame
import pygame_gui

from game import HexGame, Move, EMPTY, RED, BLUE
from bot import MCTSBot


# ---------------- geometry helpers ----------------
def hex_corners(center, radius: float):
    cx, cy = center
    pts = []
    for i in range(6):
        ang = math.radians(60 * i - 30)  # pointy-top
        pts.append((cx + radius * math.cos(ang), cy + radius * math.sin(ang)))
    return pts


def axial_to_pixel(r: int, c: int, origin, radius: float):
    ox, oy = origin
    dx = math.sqrt(3.0) * radius
    dy = 1.5 * radius
    x = ox + c * dx + r * (dx * 0.5)
    y = oy + r * dy
    return (x, y)


def point_in_poly(p, poly):
    x, y = p
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cond = ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1)
        if cond:
            inside = not inside
    return inside


# ---------------- color helpers (HSV picker) ----------------
def hsv_to_rgb(h: float, s: float, v: float) -> Tuple[int, int, int]:
    h = h % 360.0
    c = v * s
    x = c * (1.0 - abs(((h / 60.0) % 2.0) - 1.0))
    m = v - c
    if 0 <= h < 60:
        rp, gp, bp = c, x, 0
    elif 60 <= h < 120:
        rp, gp, bp = x, c, 0
    elif 120 <= h < 180:
        rp, gp, bp = 0, c, x
    elif 180 <= h < 240:
        rp, gp, bp = 0, x, c
    elif 240 <= h < 300:
        rp, gp, bp = x, 0, c
    else:
        rp, gp, bp = c, 0, x
    r = int((rp + m) * 255)
    g = int((gp + m) * 255)
    b = int((bp + m) * 255)
    return r, g, b


@dataclass
class Theme:
    bg: Tuple[int, int, int] = (30, 30, 35)
    panel: Tuple[int, int, int] = (24, 24, 28)
    panel_border: Tuple[int, int, int] = (60, 60, 70)

    empty: Tuple[int, int, int] = (210, 210, 210)
    grid: Tuple[int, int, int] = (70, 70, 80)

    red: Tuple[int, int, int] = (220, 70, 70)
    blue: Tuple[int, int, int] = (70, 120, 220)

    side_red: Tuple[int, int, int] = (160, 40, 40)
    side_blue: Tuple[int, int, int] = (40, 80, 160)

    text: Tuple[int, int, int] = (235, 235, 235)
    muted: Tuple[int, int, int] = (180, 180, 190)


class AppUI:
    HUD_H = 140

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.clock = pygame.time.Clock()

        self.manager = pygame_gui.UIManager(screen.get_size())
        self.ui_elems = []

        self.font = pygame.font.SysFont("consolas", 18)
        self.big_font = pygame.font.SysFont("consolas", 30)

        self.theme = Theme()
        self.size = 11

        self.state = "menu"  # menu/how/settings/game
        self.game = HexGame(self.size)

        self.radius = 22
        self.origin = (80, self.HUD_H + 30)
        self.cells = []  # (r,c,poly,bbox)

        # bot
        self.vs_bot = True
        self.human = RED
        self.bot_player = BLUE
        self.bot = MCTSBot(time_limit_s=1.2)
        self.bot_thread: Optional[threading.Thread] = None
        self.bot_move: Optional[Move] = None
        self.bot_thinking = False

        # settings: color picker state
        self.color_target = "red"  # 'red' or 'blue'
        self.hue = 0.0
        self.sv = (1.0, 1.0)  # (s, v)
        self.hue_bar_rect = pygame.Rect(20, 240, 360, 18)
        self.sv_rect = pygame.Rect(20, 90, 360, 130)
        self.apply_color_btn_rect = pygame.Rect(400, 90, 180, 40)

        self._build_cells()
        self._build_menu()

    # ---------- UI build ----------
    def _clear_ui(self):
        for el in self.ui_elems:
            try:
                el.kill()
            except Exception:
                pass
        self.ui_elems.clear()

    def _build_menu(self):
        self._clear_ui()
        w, _ = self.screen.get_size()

        self.ui_elems.append(pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((w // 2 - 140, 190), (280, 55)),
            text="Играть",
            manager=self.manager,
            object_id="#btn_play",
        ))
        self.ui_elems.append(pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((w // 2 - 140, 260), (280, 55)),
            text="Как играть",
            manager=self.manager,
            object_id="#btn_how",
        ))
        self.ui_elems.append(pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((w // 2 - 140, 330), (280, 55)),
            text="Настройки",
            manager=self.manager,
            object_id="#btn_settings",
        ))
        self.ui_elems.append(pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((w // 2 - 140, 400), (280, 55)),
            text="Выход",
            manager=self.manager,
            object_id="#btn_exit",
        ))

    def _build_how(self):
        self._clear_ui()
        self.ui_elems.append(pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((20, 20), (120, 40)),
            text="Назад",
            manager=self.manager,
            object_id="#btn_back",
        ))

    def _build_settings(self):
        self._clear_ui()

        self.ui_elems.append(pygame_gui.elements.UIButton(
            pygame.Rect((20, 20), (120, 40)), "Назад", self.manager, object_id="#btn_back"
        ))

        self.ui_elems.append(pygame_gui.elements.UILabel(
            pygame.Rect((160, 25), (460, 30)), "Настройки (цвета + бот)", self.manager
        ))

        self.ui_elems.append(pygame_gui.elements.UIButton(
            pygame.Rect((20, 300), (240, 45)),
            "Играть против бота: Да" if self.vs_bot else "Играть против бота: Нет",
            self.manager,
            object_id="#toggle_bot",
        ))
        self.ui_elems.append(pygame_gui.elements.UIButton(
            pygame.Rect((280, 300), (160, 45)),
            "Цвет: Игрок 1",
            self.manager,
            object_id="#pick_red",
        ))
        self.ui_elems.append(pygame_gui.elements.UIButton(
            pygame.Rect((450, 300), (160, 45)),
            "Цвет: Игрок 2",
            self.manager,
            object_id="#pick_blue",
        ))

        self.ui_elems.append(pygame_gui.elements.UILabel(
            pygame.Rect((20, 360), (700, 25)),
            "Выбери цвет кликом по спектру (Hue + S/V), затем нажми «Применить».",
            self.manager
        ))

        self.ui_elems.append(pygame_gui.elements.UIButton(
            pygame.Rect(self.apply_color_btn_rect.topleft, self.apply_color_btn_rect.size),
            "Применить",
            self.manager,
            object_id="#apply_color",
        ))

    def _build_game(self):
        self._clear_ui()

        w, _ = self.screen.get_size()
        pad = 20
        btn_w, btn_h = 160, 40
        x = w - pad - btn_w
        y0 = 20
        gap = 10

        self.ui_elems.append(pygame_gui.elements.UIButton(
            pygame.Rect((x, y0), (btn_w, btn_h)),
            "Меню",
            self.manager,
            object_id="#btn_menu"
        ))
        self.ui_elems.append(pygame_gui.elements.UIButton(
            pygame.Rect((x, y0 + btn_h + gap), (btn_w, btn_h)),
            "Новая игра",
            self.manager,
            object_id="#btn_new"
        ))

    # ---------- geometry ----------
    def _build_cells(self):
        self.cells.clear()
        n = self.game.size
        for r in range(n):
            for c in range(n):
                center = axial_to_pixel(r, c, self.origin, self.radius)
                poly = hex_corners(center, self.radius)
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                bbox = pygame.Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
                self.cells.append((r, c, poly, bbox))

    def _pick_cell(self, pos) -> Optional[Move]:
        mx, my = pos
        for r, c, poly, bbox in self.cells:
            if not bbox.collidepoint(mx, my):
                continue
            if point_in_poly((mx, my), poly):
                return Move(r, c)
        return None

    # ---------- bot async ----------
    def _start_bot_if_needed(self):
        if not self.vs_bot:
            return
        if self.game.winner != EMPTY:
            return
        if self.game.current != self.bot_player:
            return
        if self.bot_thinking:
            return

        self.bot_thinking = True
        self.bot_move = None

        def worker(snapshot: HexGame):
            mv = self.bot.choose(snapshot)
            self.bot_move = mv
            self.bot_thinking = False

        snap = self.game.clone()
        self.bot_thread = threading.Thread(target=worker, args=(snap,), daemon=True)
        self.bot_thread.start()

    # ---------- settings: spectrum picker ----------
    def _handle_color_picker_click(self, pos):
        x, y = pos
        if self.hue_bar_rect.collidepoint(x, y):
            t = (x - self.hue_bar_rect.x) / max(1, self.hue_bar_rect.w - 1)
            self.hue = max(0.0, min(360.0, t * 360.0))
            return True

        if self.sv_rect.collidepoint(x, y):
            sx = (x - self.sv_rect.x) / max(1, self.sv_rect.w - 1)
            sy = (y - self.sv_rect.y) / max(1, self.sv_rect.h - 1)
            s = max(0.0, min(1.0, sx))
            v = max(0.0, min(1.0, 1.0 - sy))
            self.sv = (s, v)
            return True

        return False

    def _current_picker_color(self):
        s, v = self.sv
        return hsv_to_rgb(self.hue, s, v)

    def _apply_picker_color(self):
        col = self._current_picker_color()
        if self.color_target == "red":
            self.theme.red = col
            self.theme.side_red = (max(0, col[0] - 60), max(0, col[1] - 60), max(0, col[2] - 60))
        else:
            self.theme.blue = col
            self.theme.side_blue = (max(0, col[0] - 60), max(0, col[1] - 60), max(0, col[2] - 60))

    # ---------- main loop ----------
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break

                self.manager.process_events(event)

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.state == "settings":
                        self._handle_color_picker_click(event.pos)

                    if self.state == "game" and self.game.winner == EMPTY and not self.bot_thinking:
                        if (not self.vs_bot) or (self.game.current == self.human):
                            mv = self._pick_cell(event.pos)
                            if mv and self.game.play(mv):
                                if self.vs_bot:
                                    try:
                                        self.bot.notify_opponent_moved(mv)
                                    except Exception:
                                        pass
                                self._start_bot_if_needed()

                if event.type == pygame_gui.UI_BUTTON_PRESSED:
                    oid = event.ui_object_id

                    if oid.endswith("#btn_exit"):
                        running = False

                    elif oid.endswith("#btn_play"):
                        self.state = "game"
                        self._build_game()
                        self.game = HexGame(self.size)
                        self.origin = (80, self.HUD_H + 30)
                        self._build_cells()
                        self._start_bot_if_needed()

                    elif oid.endswith("#btn_how"):
                        self.state = "how"
                        self._build_how()

                    elif oid.endswith("#btn_settings"):
                        self.state = "settings"
                        self._build_settings()

                    elif oid.endswith("#btn_back"):
                        self.state = "menu"
                        self._build_menu()

                    elif oid.endswith("#btn_menu"):
                        self.state = "menu"
                        self._build_menu()

                    elif oid.endswith("#btn_new"):
                        self.game.reset()
                        self._start_bot_if_needed()

                    elif oid.endswith("#toggle_bot"):
                        self.vs_bot = not self.vs_bot
                        if self.state == "settings":
                            self._build_settings()

                    elif oid.endswith("#pick_red"):
                        self.color_target = "red"
                    elif oid.endswith("#pick_blue"):
                        self.color_target = "blue"

                    elif oid.endswith("#apply_color"):
                        self._apply_picker_color()

            self.manager.update(dt)

            if self.state == "game" and self.vs_bot and self.bot_move is not None and self.game.winner == EMPTY:
                mv = self.bot_move
                self.bot_move = None
                self.game.play(mv)

            self._render()

        pygame.quit()

    # ---------- rendering ----------
    def _render(self):
        self.screen.fill(self.theme.bg)

        if self.state == "menu":
            title = self.big_font.render("HEX", True, self.theme.text)
            self.screen.blit(title, (self.screen.get_width() // 2 - title.get_width() // 2, 120))

        elif self.state == "how":
            self._draw_top_panel()
            lines = [
                "Цель игры Hex:",
                "Игрок 1 соединяет ВЕРХ и НИЗ.",
                "Игрок 2 соединяет ЛЕВО и ПРАВО.",
                "Игроки по очереди занимают клетки.",
                "Ничьи в Hex не бывает.",
            ]
            y = 80
            for s in lines:
                txt = self.font.render(s, True, self.theme.text)
                self.screen.blit(txt, (20, y))
                y += 26

        elif self.state == "settings":
            self._draw_settings_extras()

        elif self.state == "game":
            self._draw_top_panel()
            self._draw_board()
            self._draw_game_hud()

        self.manager.draw_ui(self.screen)
        pygame.display.flip()

    def _draw_top_panel(self):
        # Добавить условие, чтобы не рисовать панель в режиме "how"
        if self.state == "how":
            return

        panel = pygame.Rect(0, 0, self.screen.get_width(), self.HUD_H)
        pygame.draw.rect(self.screen, self.theme.panel, panel)
        pygame.draw.rect(self.screen, self.theme.panel_border, panel, 1)

    def _draw_settings_extras(self):
        self.screen.fill(self.theme.bg)

        sv = pygame.Surface((self.sv_rect.w, self.sv_rect.h))
        for ix in range(self.sv_rect.w):
            s = ix / max(1, self.sv_rect.w - 1)
            for iy in range(self.sv_rect.h):
                v = 1.0 - (iy / max(1, self.sv_rect.h - 1))
                sv.set_at((ix, iy), hsv_to_rgb(self.hue, s, v))
        self.screen.blit(sv, self.sv_rect.topleft)
        pygame.draw.rect(self.screen, self.theme.panel_border, self.sv_rect, 1)

        hb = pygame.Surface((self.hue_bar_rect.w, self.hue_bar_rect.h))
        for ix in range(self.hue_bar_rect.w):
            h = (ix / max(1, self.hue_bar_rect.w - 1)) * 360.0
            col = hsv_to_rgb(h, 1.0, 1.0)
            pygame.draw.line(hb, col, (ix, 0), (ix, self.hue_bar_rect.h - 1))
        self.screen.blit(hb, self.hue_bar_rect.topleft)
        pygame.draw.rect(self.screen, self.theme.panel_border, self.hue_bar_rect, 1)

        hx = int(self.hue_bar_rect.x + (self.hue / 360.0) * (self.hue_bar_rect.w - 1))
        pygame.draw.line(self.screen, (255, 255, 255),
                         (hx, self.hue_bar_rect.y - 2),
                         (hx, self.hue_bar_rect.y + self.hue_bar_rect.h + 2), 2)

        s, v = self.sv
        mx = int(self.sv_rect.x + s * (self.sv_rect.w - 1))
        my = int(self.sv_rect.y + (1.0 - v) * (self.sv_rect.h - 1))
        pygame.draw.circle(self.screen, (255, 255, 255), (mx, my), 6, 2)

        preview = pygame.Rect(400, 145, 180, 75)
        pygame.draw.rect(self.screen, self._current_picker_color(), preview)
        pygame.draw.rect(self.screen, self.theme.panel_border, preview, 1)

        label = f"Цель: {'Игрок 1' if self.color_target == 'red' else 'Игрок 2'}"
        self.screen.blit(self.font.render(label, True, self.theme.text), (400, 230))

        note = self.font.render("Подсказка: клик по Hue и по квадрату S/V.", True, self.theme.muted)
        self.screen.blit(note, (20, 60))

    def _draw_board(self):
        for r, c, poly, _ in self.cells:
            v = self.game.board[r][c]
            col = self.theme.empty
            if v == RED:
                col = self.theme.red
            elif v == BLUE:
                col = self.theme.blue

            pygame.draw.polygon(self.screen, col, poly)
            pygame.draw.polygon(self.screen, self.theme.grid, poly, width=1)

        if self.game.last_move:
            mv = self.game.last_move
            for r, c, poly, _ in self.cells:
                if r == mv.r and c == mv.c:
                    pygame.draw.polygon(self.screen, (245, 245, 245), poly, width=3)
                    break

        # границы как было: подсветка крайних гексов (внутри поля)
        n = self.game.size
        for r, c, poly, _ in self.cells:
            if r == 0 or r == n - 1:
                pygame.draw.polygon(self.screen, self.theme.side_red, poly, width=3)
            if c == 0 or c == n - 1:
                pygame.draw.polygon(self.screen, self.theme.side_blue, poly, width=3)

    def _draw_game_hud(self):
        x = 20
        y = 70

        def pname(p: int) -> str:
            return "Игрок 1" if p == RED else "Игрок 2"

        turn = self.game.current
        if self.game.winner != EMPTY:
            msg = f"Победил: {pname(self.game.winner)}"
        else:
            msg = f"Ход: {pname(turn)}"

        self.screen.blit(self.big_font.render(msg, True, self.theme.text), (x, 18))

        legend1 = self.font.render("Игрок 1: соединить ВЕРХ ↔ НИЗ", True, self.theme.red)
        legend2 = self.font.render("Игрок 2: соединить ЛЕВО ↔ ПРАВО", True, self.theme.blue)
        self.screen.blit(legend1, (x, y))
        self.screen.blit(legend2, (x, y + 24))

        if self.vs_bot:
            botmsg = "Бот думает..." if self.bot_thinking else "Против бота: Да"
        else:
            botmsg = "Против бота: Нет"
        self.screen.blit(self.font.render(botmsg, True, self.theme.text), (x, y + 52))

        sw1 = pygame.Rect(430, 22, 26, 26)
        sw2 = pygame.Rect(430, 54, 26, 26)
        pygame.draw.rect(self.screen, self.theme.red, sw1)
        pygame.draw.rect(self.screen, self.theme.blue, sw2)
        pygame.draw.rect(self.screen, self.theme.panel_border, sw1, 1)
        pygame.draw.rect(self.screen, self.theme.panel_border, sw2, 1)
        self.screen.blit(self.font.render("Игрок 1", True, self.theme.text), (465, 25))
        self.screen.blit(self.font.render("Игрок 2", True, self.theme.text), (465, 57))