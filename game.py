# game.py
from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from typing import List, Optional, Tuple

EMPTY, RED, BLUE = 0, 1, 2
NEI = [(-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0)]

@dataclass(frozen=True)
class Move:
    r: int
    c: int

class HexGame:
    def __init__(self, size: int = 11):
        self.size = size
        self.reset()

    def reset(self):
        self.board: List[List[int]] = [[EMPTY]*self.size for _ in range(self.size)]
        self.current = RED
        self.winner: int = EMPTY
        self.last_move: Optional[Move] = None
        self.moves_played: int = 0

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.size and 0 <= c < self.size

    def legal_moves(self) -> List[Move]:
        if self.winner != EMPTY:
            return []
        out = []
        for r in range(self.size):
            row = self.board[r]
            for c in range(self.size):
                if row[c] == EMPTY:
                    out.append(Move(r, c))
        return out

    def play(self, mv: Move) -> bool:
        if self.winner != EMPTY:
            return False
        if not self.in_bounds(mv.r, mv.c):
            return False
        if self.board[mv.r][mv.c] != EMPTY:
            return False

        p = self.current
        self.board[mv.r][mv.c] = p
        self.last_move = mv
        self.moves_played += 1

        if self.has_won(p):
            self.winner = p
        else:
            self.current = BLUE if self.current == RED else RED
        return True

    def has_won(self, player: int) -> bool:
        n = self.size
        vis = [[False]*n for _ in range(n)]
        q = deque()

        if player == BLUE:
            # left -> right
            for r in range(n):
                if self.board[r][0] == BLUE:
                    vis[r][0] = True
                    q.append((r, 0))
            def is_end(r, c): return c == n - 1
        else:
            # top -> bottom
            for c in range(n):
                if self.board[0][c] == RED:
                    vis[0][c] = True
                    q.append((0, c))
            def is_end(r, c): return r == n - 1

        while q:
            r, c = q.popleft()
            if is_end(r, c):
                return True
            for dr, dc in NEI:
                nr, nc = r + dr, c + dc
                if 0 <= nr < n and 0 <= nc < n and not vis[nr][nc] and self.board[nr][nc] == player:
                    vis[nr][nc] = True
                    q.append((nr, nc))
        return False

    def clone(self) -> "HexGame":
        g = HexGame(self.size)
        g.board = [row[:] for row in self.board]
        g.current = self.current
        g.winner = self.winner
        g.last_move = self.last_move
        g.moves_played = self.moves_played
        return g