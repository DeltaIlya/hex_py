# bot.py
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from game import HexGame, Move, EMPTY, RED, BLUE


# 6 соседей для "axial-like" индексации (r, c) как в твоём UI/game
# В Hex на квадратной матрице обычно соседи такие:
NEIGHBORS = [(-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0)]


def in_bounds(n: int, r: int, c: int) -> bool:
    return 0 <= r < n and 0 <= c < n


def other(player: int) -> int:
    return RED if player == BLUE else BLUE


def empty_cells(game: HexGame) -> List[Move]:
    n = game.size
    moves = []
    b = game.board
    for r in range(n):
        for c in range(n):
            if b[r][c] == EMPTY:
                moves.append(Move(r, c))
    return moves


def neighbors(n: int, r: int, c: int):
    for dr, dc in NEIGHBORS:
        rr, cc = r + dr, c + dc
        if in_bounds(n, rr, cc):
            yield rr, cc


def manhattan_like_to_goal(player: int, n: int, r: int, c: int) -> int:
    # RED: top-bottom => distance to nearer of (top/bot) is min(r, n-1-r)
    # BLUE: left-right => min(c, n-1-c)
    if player == RED:
        return min(r, n - 1 - r)
    else:
        return min(c, n - 1 - c)


def count_adjacent_stones(game: HexGame, r: int, c: int, player: int) -> int:
    n = game.size
    cnt = 0
    for rr, cc in neighbors(n, r, c):
        if game.board[rr][cc] == player:
            cnt += 1
    return cnt


def count_adjacent_any(game: HexGame, r: int, c: int) -> int:
    n = game.size
    cnt = 0
    for rr, cc in neighbors(n, r, c):
        if game.board[rr][cc] != EMPTY:
            cnt += 1
    return cnt


def frontier_moves(game: HexGame, max_candidates: int = 30) -> List[Move]:
    """Кандидаты: пустые клетки рядом с занятыми + (если пусто) центр."""
    n = game.size
    b = game.board
    cand_set = set()

    any_stone = False
    for r in range(n):
        for c in range(n):
            if b[r][c] != EMPTY:
                any_stone = True
                for rr, cc in neighbors(n, r, c):
                    if b[rr][cc] == EMPTY:
                        cand_set.add((rr, cc))

    if not any_stone:
        # старт: центр и его соседи (чтобы не начинать со случайного угла)
        mid = n // 2
        cand_set.add((mid, mid))
        for rr, cc in neighbors(n, mid, mid):
            cand_set.add((rr, cc))

    cands = [Move(r, c) for (r, c) in cand_set]

    # если кандидатов мало — расширяем всем полем (но редко)
    if len(cands) < 8:
        return empty_cells(game)

    # отсортируем по простой эвристике (плотность + близость к цели для текущего игрока)
    p = game.current
    def score(m: Move) -> float:
        r, c = m.r, m.c
        adj_p = count_adjacent_stones(game, r, c, p)
        adj_o = count_adjacent_stones(game, r, c, other(p))
        adj_any = count_adjacent_any(game, r, c)
        dist_goal = manhattan_like_to_goal(p, n, r, c)
        # хотим: быть ближе к своей стороне, иметь сцепление, и не давать сопернику лёгкие цепочки
        return 3.2 * adj_p + 1.2 * adj_any + 0.6 * adj_o - 0.35 * dist_goal

    cands.sort(key=score, reverse=True)
    return cands[:max_candidates]


def rollout_policy(game: HexGame, max_candidates: int = 12) -> Move:
    """Эвристический выбор хода в плей-ауте (быстрее, чем полный поиск)."""
    moves = frontier_moves(game, max_candidates=max_candidates)
    p = game.current
    n = game.size

    # softmax/болцман, чтобы сохранять разнообразие (MCTS это любит)
    # но многое решает скоринг
    scores = []
    for m in moves:
        r, c = m.r, m.c
        adj_p = count_adjacent_stones(game, r, c, p)
        adj_any = count_adjacent_any(game, r, c)
        dist_goal = manhattan_like_to_goal(p, n, r, c)
        s = 2.8 * adj_p + 0.9 * adj_any - 0.45 * dist_goal
        scores.append(s)

    # стабилизация
    mx = max(scores)
    exps = [math.exp((s - mx) / 1.0) for s in scores]
    tot = sum(exps) + 1e-12
    r = random.random() * tot
    acc = 0.0
    for m, e in zip(moves, exps):
        acc += e
        if acc >= r:
            return m
    return moves[-1]


@dataclass
class Node:
    parent: Optional["Node"]
    move: Optional[Move]                # ход, который привёл в этот узел (None для корня)
    player_to_move: int                 # кто ходит в этом состоянии
    untried: List[Move]                 # ещё не раскрытые ходы
    children: Dict[Tuple[int, int], "Node"]
    visits: int = 0
    wins_for_root_player: float = 0.0   # накапливаем "победы" с точки зрения root_player

    def uct_select_child(self, c: float) -> "Node":
        # maximize UCT
        best = None
        best_val = -1e9
        for ch in self.children.values():
            if ch.visits == 0:
                val = 1e9
            else:
                exploit = ch.wins_for_root_player / ch.visits
                explore = c * math.sqrt(math.log(self.visits + 1) / ch.visits)
                val = exploit + explore
            if val > best_val:
                best_val = val
                best = ch
        return best


class MCTSBot:
    def __init__(
        self,
        time_limit_s: float = 1.2,
        uct_c: float = 1.35,
        playout_limit: int = 9999,
        rollout_candidates: int = 12,
        expand_candidates: int = 30,
        seed: Optional[int] = None,
    ):
        self.time_limit_s = time_limit_s
        self.uct_c = uct_c
        self.playout_limit = playout_limit
        self.rollout_candidates = rollout_candidates
        self.expand_candidates = expand_candidates
        self.rng = random.Random(seed)

        # reuse tree
        self.root: Optional[Node] = None
        self.root_player: Optional[int] = None

    def _new_root(self, game: HexGame) -> Node:
        self.root_player = game.current
        untried = frontier_moves(game, max_candidates=self.expand_candidates)
        return Node(parent=None, move=None, player_to_move=game.current, untried=untried, children={})

    def _apply_move_to_tree(self, move: Move):
        """После реального хода пытаемся перейти внутрь текущего дерева."""
        if self.root is None:
            return
        key = (move.r, move.c)
        if key in self.root.children:
            nxt = self.root.children[key]
            nxt.parent = None
            self.root = nxt
        else:
            # если ход был не в дереве — сбрасываем
            self.root = None
            self.root_player = None

    def notify_opponent_moved(self, move: Move):
        """Опционально: вызывай из UI после хода игрока, чтобы дерево не сбрасывалось."""
        self._apply_move_to_tree(move)

    def choose(self, game: HexGame) -> Move:
        # если корень не подходит к текущему состоянию — сброс
        if self.root is None or self.root.player_to_move != game.current:
            self.root = self._new_root(game)
        if self.root_player is None:
            self.root_player = game.current

        # если игра почти пустая и candidates вернут всё поле, ограничим случайно небольшим набором
        if len(self.root.untried) == 0 and len(self.root.children) == 0:
            self.root.untried = frontier_moves(game, max_candidates=self.expand_candidates)

        t_end = time.perf_counter() + self.time_limit_s
        playouts = 0

        while time.perf_counter() < t_end and playouts < self.playout_limit:
            playouts += 1

            # 1) SELECTION
            node = self.root
            state = game.clone()

            # спускаемся пока узел полностью раскрыт и не терминален
            while state.winner == EMPTY and len(node.untried) == 0 and len(node.children) > 0:
                node = node.uct_select_child(self.uct_c)
                state.play(node.move)

            # 2) EXPANSION
            if state.winner == EMPTY and len(node.untried) > 0:
                # берём следующий (лучшие уже наверху списка)
                mv = node.untried.pop(0)
                ok = state.play(mv)
                if not ok:
                    # если по какой-то причине ход оказался нелегальным — пропустим
                    continue
                child_untried = frontier_moves(state, max_candidates=self.expand_candidates)
                child = Node(parent=node, move=mv, player_to_move=state.current, untried=child_untried, children={})
                node.children[(mv.r, mv.c)] = child
                node = child

            # 3) SIMULATION (ROLLOUT)
            # быстрый эвристический плей-аут до конца
            while state.winner == EMPTY:
                mv = rollout_policy(state, max_candidates=self.rollout_candidates)
                state.play(mv)

            winner = state.winner

            # 4) BACKPROP
            # Победа с точки зрения root_player
            result = 1.0 if winner == self.root_player else 0.0
            while node is not None:
                node.visits += 1
                node.wins_for_root_player += result
                node = node.parent

        # выбрать лучший ход: max visits
        if len(self.root.children) == 0:
            # fallback
            moves = frontier_moves(game, max_candidates=self.expand_candidates)
            return moves[0] if moves else empty_cells(game)[0]

        best_child = max(self.root.children.values(), key=lambda ch: ch.visits)
        best_move = best_child.move

        # REUSE: после выбора хода сдвигаем корень
        self._apply_move_to_tree(best_move)
        return best_move