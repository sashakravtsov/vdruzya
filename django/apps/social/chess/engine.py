"""Compact chess rules: FEN, legal moves, make_move (no underpromotion variety beyond queen)."""
from __future__ import annotations

from copy import deepcopy

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

FILES = "abcdefgh"
PIECE_UNI = {
    "K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
    "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟",
}


def sq_to_rc(sq: str) -> tuple[int, int]:
    sq = (sq or "").strip().lower()
    if len(sq) != 2 or sq[0] not in FILES or sq[1] not in "12345678":
        raise ValueError("Клетка должна быть вида e2")
    return 8 - int(sq[1]), FILES.index(sq[0])


def rc_to_sq(r: int, c: int) -> str:
    return f"{FILES[c]}{8 - r}"


def parse_fen(fen: str) -> dict:
    parts = (fen or START_FEN).split()
    rows = parts[0].split("/")
    board = [["." for _ in range(8)] for _ in range(8)]
    for r, row in enumerate(rows):
        c = 0
        for ch in row:
            if ch.isdigit():
                c += int(ch)
            else:
                board[r][c] = ch
                c += 1
    return {
        "board": board,
        "turn": parts[1] if len(parts) > 1 else "w",
        "castling": parts[2] if len(parts) > 2 else "KQkq",
        "ep": parts[3] if len(parts) > 3 else "-",
        "half": int(parts[4]) if len(parts) > 4 else 0,
        "full": int(parts[5]) if len(parts) > 5 else 1,
    }


def fen_of(state: dict) -> str:
    rows = []
    for r in range(8):
        empty = 0
        s = ""
        for c in range(8):
            p = state["board"][r][c]
            if p == ".":
                empty += 1
            else:
                if empty:
                    s += str(empty)
                    empty = 0
                s += p
        if empty:
            s += str(empty)
        rows.append(s)
    return " ".join([
        "/".join(rows),
        state["turn"],
        state["castling"] or "-",
        state["ep"] or "-",
        str(state["half"]),
        str(state["full"]),
    ])


def _is_white(p: str) -> bool:
    return p.isupper()


def _enemy(turn: str, p: str) -> bool:
    if p == ".":
        return False
    return (turn == "w" and p.islower()) or (turn == "b" and p.isupper())


def _own(turn: str, p: str) -> bool:
    if p == ".":
        return False
    return (turn == "w" and p.isupper()) or (turn == "b" and p.islower())


def find_king(board, turn: str) -> tuple[int, int]:
    k = "K" if turn == "w" else "k"
    for r in range(8):
        for c in range(8):
            if board[r][c] == k:
                return r, c
    return -1, -1


def attacked(board, r: int, c: int, by_white: bool) -> bool:
    """Is square (r,c) attacked by side by_white?"""
    # pawns
    if by_white:
        for dc in (-1, 1):
            rr, cc = r + 1, c + dc
            if 0 <= rr < 8 and 0 <= cc < 8 and board[rr][cc] == "P":
                return True
    else:
        for dc in (-1, 1):
            rr, cc = r - 1, c + dc
            if 0 <= rr < 8 and 0 <= cc < 8 and board[rr][cc] == "p":
                return True
    # knights
    for dr, dc in ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)):
        rr, cc = r + dr, c + dc
        if 0 <= rr < 8 and 0 <= cc < 8:
            p = board[rr][cc]
            if p == ("N" if by_white else "n"):
                return True
    # king
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == dc == 0:
                continue
            rr, cc = r + dr, c + dc
            if 0 <= rr < 8 and 0 <= cc < 8:
                p = board[rr][cc]
                if p == ("K" if by_white else "k"):
                    return True
    # bishops/queens diagonals
    for dr, dc in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        rr, cc = r + dr, c + dc
        while 0 <= rr < 8 and 0 <= cc < 8:
            p = board[rr][cc]
            if p != ".":
                if by_white and p in "BQ":
                    return True
                if not by_white and p in "bq":
                    return True
                break
            rr += dr
            cc += dc
    # rooks/queens
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        rr, cc = r + dr, c + dc
        while 0 <= rr < 8 and 0 <= cc < 8:
            p = board[rr][cc]
            if p != ".":
                if by_white and p in "RQ":
                    return True
                if not by_white and p in "rq":
                    return True
                break
            rr += dr
            cc += dc
    return False


def in_check(board, turn: str) -> bool:
    kr, kc = find_king(board, turn)
    if kr < 0:
        return True
    return attacked(board, kr, kc, by_white=(turn == "b"))


def _slide(board, r, c, turn, deltas):
    out = []
    for dr, dc in deltas:
        rr, cc = r + dr, c + dc
        while 0 <= rr < 8 and 0 <= cc < 8:
            p = board[rr][cc]
            if p == ".":
                out.append((rr, cc))
            else:
                if _enemy(turn, p):
                    out.append((rr, cc))
                break
            rr += dr
            cc += dc
    return out


def pseudo_moves(board, r, c, turn, castling="-", ep="-"):
    p = board[r][c]
    if p == "." or not _own(turn, p):
        return []
    kind = p.upper()
    moves = []
    if kind == "P":
        dr = -1 if turn == "w" else 1
        start = 6 if turn == "w" else 1
        rr = r + dr
        if 0 <= rr < 8 and board[rr][c] == ".":
            moves.append((rr, c))
            if r == start and board[r + 2 * dr][c] == ".":
                moves.append((r + 2 * dr, c))
        for dc in (-1, 1):
            cc = c + dc
            if 0 <= rr < 8 and 0 <= cc < 8 and _enemy(turn, board[rr][cc]):
                moves.append((rr, cc))
            # en passant
            if ep and ep != "-":
                er, ec = sq_to_rc(ep)
                if rr == er and cc == ec:
                    moves.append((rr, cc))
    elif kind == "N":
        for dr, dc in ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < 8 and 0 <= cc < 8 and not _own(turn, board[rr][cc]):
                moves.append((rr, cc))
    elif kind == "B":
        moves.extend(_slide(board, r, c, turn, ((-1, -1), (-1, 1), (1, -1), (1, 1))))
    elif kind == "R":
        moves.extend(_slide(board, r, c, turn, ((-1, 0), (1, 0), (0, -1), (0, 1))))
    elif kind == "Q":
        moves.extend(_slide(board, r, c, turn, (
            (-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1),
        )))
    elif kind == "K":
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == dc == 0:
                    continue
                rr, cc = r + dr, c + dc
                if 0 <= rr < 8 and 0 <= cc < 8 and not _own(turn, board[rr][cc]):
                    moves.append((rr, cc))
        # castling
        rights = castling or ""
        if turn == "w" and r == 7 and c == 4:
            if "K" in rights and board[7][5] == board[7][6] == "." and board[7][7] == "R":
                if not attacked(board, 7, 4, False) and not attacked(board, 7, 5, False) and not attacked(board, 7, 6, False):
                    moves.append((7, 6))
            if "Q" in rights and board[7][1] == board[7][2] == board[7][3] == "." and board[7][0] == "R":
                if not attacked(board, 7, 4, False) and not attacked(board, 7, 3, False) and not attacked(board, 7, 2, False):
                    moves.append((7, 2))
        if turn == "b" and r == 0 and c == 4:
            if "k" in rights and board[0][5] == board[0][6] == "." and board[0][7] == "r":
                if not attacked(board, 0, 4, True) and not attacked(board, 0, 5, True) and not attacked(board, 0, 6, True):
                    moves.append((0, 6))
            if "q" in rights and board[0][1] == board[0][2] == board[0][3] == "." and board[0][0] == "r":
                if not attacked(board, 0, 4, True) and not attacked(board, 0, 3, True) and not attacked(board, 0, 2, True):
                    moves.append((0, 2))
    return moves


def legal_moves_from(state: dict, fr: str) -> list[str]:
    r, c = sq_to_rc(fr)
    board = state["board"]
    turn = state["turn"]
    out = []
    for tr, tc in pseudo_moves(board, r, c, turn, state.get("castling", "-"), state.get("ep", "-")):
        nb = deepcopy(board)
        piece = nb[r][c]
        nb[tr][tc] = piece
        nb[r][c] = "."
        # castling rook move
        if piece.upper() == "K" and abs(tc - c) == 2:
            if tc == 6:
                nb[tr][5] = nb[tr][7]
                nb[tr][7] = "."
            elif tc == 2:
                nb[tr][3] = nb[tr][0]
                nb[tr][0] = "."
        # en passant capture
        if piece.upper() == "P" and c != tc and board[tr][tc] == ".":
            nb[r][tc] = "."
        # promotion placeholder queen
        if piece == "P" and tr == 0:
            nb[tr][tc] = "Q"
        if piece == "p" and tr == 7:
            nb[tr][tc] = "q"
        if not in_check(nb, turn):
            out.append(rc_to_sq(tr, tc))
    return out


def make_move(fen: str, frm: str, to: str) -> tuple[str, str]:
    """Apply move; returns (new_fen, san_like). Raises ValueError."""
    state = parse_fen(fen)
    legal = legal_moves_from(state, frm)
    if to.lower() not in legal:
        raise ValueError("Такой ход сейчас нельзя")
    r, c = sq_to_rc(frm)
    tr, tc = sq_to_rc(to)
    board = state["board"]
    piece = board[r][c]
    orig = piece
    is_castle = piece.upper() == "K" and abs(tc - c) == 2
    promoted = False
    capture = board[tr][tc] != "."
    # en passant
    if piece.upper() == "P" and c != tc and board[tr][tc] == ".":
        board[r][tc] = "."
        capture = True
    board[tr][tc] = piece
    board[r][c] = "."
    # castling
    if is_castle:
        if tc == 6:
            board[tr][5] = board[tr][7]
            board[tr][7] = "."
        else:
            board[tr][3] = board[tr][0]
            board[tr][0] = "."
    # promotion
    if piece == "P" and tr == 0:
        board[tr][tc] = "Q"
        piece = "Q"
        promoted = True
    if piece == "p" and tr == 7:
        board[tr][tc] = "q"
        piece = "q"
        promoted = True
    # castling rights
    rights = list(state["castling"] if state["castling"] != "-" else "")
    def drop(ch):
        if ch in rights:
            rights.remove(ch)
    if piece in "Kk":
        if state["turn"] == "w":
            drop("K"); drop("Q")
        else:
            drop("k"); drop("q")
    if (r, c) == (7, 0) or (tr, tc) == (7, 0):
        drop("Q")
    if (r, c) == (7, 7) or (tr, tc) == (7, 7):
        drop("K")
    if (r, c) == (0, 0) or (tr, tc) == (0, 0):
        drop("q")
    if (r, c) == (0, 7) or (tr, tc) == (0, 7):
        drop("k")
    # ep
    ep = "-"
    if piece.upper() == "P" and abs(tr - r) == 2:
        ep = rc_to_sq((r + tr) // 2, c)
    state["board"] = board
    state["castling"] = "".join(rights) or "-"
    state["ep"] = ep
    state["half"] = 0 if piece.upper() == "P" or capture else state["half"] + 1
    if state["turn"] == "b":
        state["full"] += 1
    state["turn"] = "b" if state["turn"] == "w" else "w"
    # Algebraic-ish SAN for a professional move list
    if is_castle:
        san = "0-0-0" if tc < c else "0-0"
    elif orig.upper() == "P":
        san = f"{FILES[c]}×{to.lower()}" if capture else to.lower()
        if promoted:
            san += "=Q"
    else:
        letter = {"K": "K", "Q": "Q", "R": "R", "B": "B", "N": "N"}[orig.upper()]
        san = f"{letter}{'×' if capture else ''}{to.lower()}"
    if in_check(board, state["turn"]):
        any_legal = False
        for rr in range(8):
            for cc in range(8):
                if _own(state["turn"], board[rr][cc]):
                    if legal_moves_from(state, rc_to_sq(rr, cc)):
                        any_legal = True
                        break
            if any_legal:
                break
        san += "#" if not any_legal else "+"
    return fen_of(state), san


def board_rows(fen: str, flip: bool = False) -> list[list[dict]]:
    state = parse_fen(fen)
    rows = []
    order_r = range(7, -1, -1) if flip else range(8)
    for r in order_r:
        row = []
        order_c = range(7, -1, -1) if flip else range(8)
        for c in order_c:
            p = state["board"][r][c]
            light = (r + c) % 2 == 0
            row.append({
                "sq": rc_to_sq(r, c),
                "piece": p if p != "." else "",
                "glyph": PIECE_UNI.get(p, ""),
                "light": light,
            })
        rows.append(row)
    return rows


def legal_moves_map(fen: str, side: str | None = None) -> dict[str, list[str]]:
    """Map square -> legal target squares for the side to move (or given side)."""
    state = parse_fen(fen)
    turn = side or state["turn"]
    out: dict[str, list[str]] = {}
    for r in range(8):
        for c in range(8):
            p = state["board"][r][c]
            if not _own(turn, p):
                continue
            sq = rc_to_sq(r, c)
            targets = legal_moves_from(state, sq)
            if targets:
                out[sq] = targets
    return out


def game_status(fen: str) -> str:
    """active | check | checkmate | stalemate"""
    state = parse_fen(fen)
    turn = state["turn"]
    any_legal = False
    for r in range(8):
        for c in range(8):
            if _own(turn, state["board"][r][c]):
                if legal_moves_from(state, rc_to_sq(r, c)):
                    any_legal = True
                    break
        if any_legal:
            break
    chk = in_check(state["board"], turn)
    if not any_legal:
        return "checkmate" if chk else "stalemate"
    return "check" if chk else "active"


_MATERIAL = {"Q": 9, "R": 5, "B": 3, "N": 3, "P": 1, "K": 0}
_START_BAG = {"Q": 1, "R": 2, "B": 2, "N": 2, "P": 8, "K": 1}


def king_square(fen: str, side: str) -> str | None:
    try:
        kr, kc = find_king(parse_fen(fen)["board"], side)
        return rc_to_sq(kr, kc)
    except Exception:
        return None


def material_view(fen: str) -> dict:
    """Captured glyphs + simple material score for the side that is ahead."""
    state = parse_fen(fen)
    have_w = {k: 0 for k in _START_BAG}
    have_b = {k: 0 for k in _START_BAG}
    for r in range(8):
        for c in range(8):
            p = state["board"][r][c]
            if p == ".":
                continue
            key = p.upper()
            if key not in have_w:
                continue
            if p.isupper():
                have_w[key] += 1
            else:
                have_b[key] += 1
    order = ("Q", "R", "B", "N", "P")
    cap_w, cap_b = [], []
    score_w = score_b = 0
    for k in order:
        miss_b = max(0, _START_BAG[k] - have_b[k])  # white captured these
        miss_w = max(0, _START_BAG[k] - have_w[k])
        glyph_w = PIECE_UNI[k.lower()]  # black piece icon captured by white
        glyph_b = PIECE_UNI[k]
        cap_w.extend([glyph_w] * miss_b)
        cap_b.extend([glyph_b] * miss_w)
        score_w += miss_b * _MATERIAL[k]
        score_b += miss_w * _MATERIAL[k]
    adv = score_w - score_b
    return {
        "white_captured": "".join(cap_w),
        "black_captured": "".join(cap_b),
        "white_score": score_w,
        "black_score": score_b,
        "advantage": adv,
        "advantage_label": (f"+{adv}" if adv > 0 else (str(adv) if adv < 0 else "=")),
    }


def pair_moves(moves) -> list[dict]:
    """Group ply list into rows: 1. white black."""
    pairs: list[dict] = []
    cur = None
    for m in moves:
        ply = int(getattr(m, "ply", 0) or 0)
        if ply % 2 == 1:
            cur = {"n": (ply + 1) // 2, "w": m, "b": None}
            pairs.append(cur)
        else:
            n = ply // 2
            if cur and cur["b"] is None and cur["n"] == n:
                cur["b"] = m
            else:
                cur = {"n": n, "w": None, "b": m}
                pairs.append(cur)
    return pairs
