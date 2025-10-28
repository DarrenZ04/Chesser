import math
import sys
import os
import chess
import numpy as np
import chess.polyglot
import random

# Pygame is not needed for web deployment
try:
    import pygame
except ImportError:
    pygame = None

from zobrist_hash import get_board_hash, process_move, black_turn

# [-4, -2, -3, -5, -6, -3, -2, -4],  
# [-1, -1, -1, -1, -1, -1, -1, -1],  
# [ 0,  0,  0,  0,  0,  0,  0,  0], 
# [ 0,  0,  0,  0,  0,  0,  0,  0],  
# [ 0,  0,  0,  0,  0,  0,  0,  0], 
# [ 0,  0,  0,  0,  0,  0,  0,  0],
# [ 1,  1,  1,  1,  1,  1,  1,  1], 
# [ 4,  2,  3,  5,  6,  3,  2,  4]

# Window settings (unused for search but kept)
WIDTH, HEIGHT = 480, 480
ROWS, COLS = 8, 8
SQ_SIZE = WIDTH // COLS
FPS = 60

# Colors (unused for search but kept)
WHITE = (245, 245, 220)
GRAY = (119, 136, 153)
SELECT_HIGHLIGHT = (186, 202, 68)
MOVE_HIGHLIGHT = (246, 246, 105)

# Map piece symbols to integers for fast board-state access
DTYPE = np.int8
PIECE_MAP = {
    'P':  1, 'N':  2, 'B':  3, 'R':  4, 'Q':  5, 'K':  6,
    'p': -1, 'n': -2, 'b': -3, 'r': -4, 'q': -5, 'k': -6
}

# ========= Search constants, toggles, & instrumentation =========
lookahead = 3

# Opening book
BOOK = None
try:
    book_path = os.path.join(os.path.dirname(__file__), "openings", "book.bin")
    if os.path.exists(book_path):
        BOOK = chess.polyglot.open_reader(book_path)
except Exception as e:
    print(f"Warning: Could not load opening book: {e}")
    BOOK = None

# Transposition table and helpers
seen_states = {}
hit_count = 0

TT_EXACT = 0
TT_LOWERBOUND = 1
TT_UPPERBOUND = 2

history_heuristic = {}
killer_moves = {}

MAX_QUIESCENCE_DEPTH = 6

# Eval constants
MATE = 10_000_000
def mate_score(ply: int) -> int:
    return MATE - ply

# Safer MVV-LVA values (don’t give king absurd value for ordering)
_MVV_VAL = {
    None: 0,
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 100,
}

# Speed/strength toggles
USE_NULL_MOVE = True
USE_LMR = True
USE_ASPIRATION = True
USE_PVS = True
QS_INCLUDE_CHECKS = False  # keep False for speed

QS_DELTA_MARGIN = 300      # delta pruning margin in QS (up from 100)
QS_BAD_TRADE_MARGIN = 50   # skip captures where attacker >> victim by this
FUTILITY_MARGIN = 250

# Optional instrumentation
nodes = 0
qnodes = 0

# ========= Move ordering =========
def _mvv_lva(board, move):
    if not board.is_capture(move):
        return 0
    victim = board.piece_at(move.to_square)
    attacker = board.piece_at(move.from_square)
    v = _MVV_VAL[victim.piece_type] if victim else 0
    a = _MVV_VAL[attacker.piece_type] if attacker else 0
    return (v * 100) - a

def order_moves(board, moves, tt_move=None, depth=0):
    scored = []
    for m in moves:
        score = 0
        if tt_move is not None and m == tt_move:
            score += 1_000_000
        if board.is_capture(m):
            score += 10_000 + _mvv_lva(board, m)
        if m.promotion is not None:
            score += 9_000
        # NOTE: we intentionally do NOT call board.gives_check(m) here (slow).
        score += history_heuristic.get((depth, m), 0)
        if depth in killer_moves and m in killer_moves[depth]:
            score += 500
        scored.append((score, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored]

# ========= Alpha-Beta with TT, Null-Move, LMR =========
def min_max(board, depth, alpha, beta, maximizing, current_hash, ply=0):
    global hit_count, nodes
    nodes += 1

    # Probe TT
    if current_hash in seen_states:
        entry = seen_states[current_hash]
        if entry["depth"] >= depth:
            hit_count += 1
            flag = entry["flag"]
            s = entry["score"]
            if flag == TT_EXACT:
                return s
            if flag == TT_LOWERBOUND and s > alpha:
                alpha = s
            elif flag == TT_UPPERBOUND and s < beta:
                beta = s
            if alpha >= beta:
                return s

    # Terminal checks
    if board.is_checkmate():
        return -mate_score(ply) if maximizing else mate_score(ply)
    if board.is_stalemate() or board.can_claim_threefold_repetition() or board.can_claim_fifty_moves():
        return 0

    # Leaf: go to quiescence
    if depth == 0:
        return quiescence(board, alpha, beta, maximizing, current_hash, qdepth=0)

    # Frontier futility at depth == 1 (don’t do it if in check)
    if depth == 1 and not board.is_check():
        sp = evaluate_board(board)
        if maximizing:
            if sp + FUTILITY_MARGIN <= alpha:
                # cannot realistically improve alpha → jump to QS
                return quiescence(board, alpha, beta, maximizing, current_hash, qdepth=0)
        else:
            if sp - FUTILITY_MARGIN >= beta:
                # cannot realistically drop below beta → jump to QS
                return quiescence(board, alpha, beta, maximizing, current_hash, qdepth=0)

    alpha_orig, beta_orig = alpha, beta

    # Null-move pruning (toggle side-to-move Zobrist!)
    if USE_NULL_MOVE and depth >= 3 and not board.is_check():
        board.push(chess.Move.null())
        R = 2 + (depth // 4)
        null_hash = current_hash ^ black_turn
        score = -min_max(board, depth - 1 - R, -beta, -beta + 1, not maximizing, null_hash, ply + 1)
        board.pop()
        if score >= beta:
            return beta

    best_move = seen_states.get(current_hash, {}).get("move")
    legal_moves = list(board.legal_moves)
    moves = order_moves(board, legal_moves, tt_move=best_move, depth=ply)

    if maximizing:
        value = float('-inf')
        for i, move in enumerate(moves):
            new_hash = process_move(current_hash, board, move)
            board.push(move)

            is_tactical = board.is_capture(move) or move.promotion is not None or board.is_check()
            new_depth = depth - 1
            if USE_LMR and depth >= 4 and i >= 4 and not is_tactical and not board.is_check():
                red = 1 + (i // 8)
                score = min_max(board, new_depth - red, alpha, beta, False, new_hash, ply + 1)
                if score > alpha and red >= 1:
                    score = min_max(board, new_depth, alpha, beta, False, new_hash, ply + 1)
            else:
                score = min_max(board, new_depth, alpha, beta, False, new_hash, ply + 1)

            board.pop()

            if score > value:
                value = score
                best_move = move
            if score > alpha:
                alpha = score
                history_heuristic[(ply, move)] = history_heuristic.get((ply, move), 0) + depth * depth
            if alpha >= beta:
                ks = killer_moves.setdefault(ply, [])
                if move not in ks:
                    ks.append(move)
                    if len(ks) > 2:
                        ks.pop(0)
                break

        # Store TT with correct flag (compare to original window)
        if value <= alpha_orig:
            flag = TT_UPPERBOUND
        elif value >= beta_orig:
            flag = TT_LOWERBOUND
        else:
            flag = TT_EXACT
        seen_states[current_hash] = {"score": value, "depth": depth, "flag": flag, "move": best_move}
        return value

    else:
        value = float('inf')
        for i, move in enumerate(moves):

            if depth <= 2 and i >= 16 and not board.is_check():
                break

            new_hash = process_move(current_hash, board, move)
            board.push(move)

            is_tactical = board.is_capture(move) or move.promotion is not None or board.is_check()
            new_depth = depth - 1
            if USE_LMR and depth >= 4 and i >= 4 and not is_tactical and not board.is_check():
                red = 1 + (i // 8)
                score = min_max(board, new_depth - red, alpha, beta, True, new_hash, ply + 1)
                if score < beta and red >= 1:
                    score = min_max(board, new_depth, alpha, beta, True, new_hash, ply + 1)
            else:
                score = min_max(board, new_depth, alpha, beta, True, new_hash, ply + 1)

            board.pop()

            if score < value:
                value = score
                best_move = move
            if score < beta:
                beta = score
                history_heuristic[(ply, move)] = history_heuristic.get((ply, move), 0) + depth * depth
            if alpha >= beta:
                ks = killer_moves.setdefault(ply, [])
                if move not in ks:
                    ks.append(move)
                    if len(ks) > 2:
                        ks.pop(0)
                break

        if value <= alpha_orig:
            flag = TT_UPPERBOUND
        elif value >= beta_orig:
            flag = TT_LOWERBOUND
        else:
            flag = TT_EXACT
        seen_states[current_hash] = {"score": value, "depth": depth, "flag": flag, "move": best_move}
        return value


def quiescence(board, alpha, beta, maximizing, current_hash, qdepth=0):
    global qnodes
    qnodes += 1

    stand_pat = evaluate_board(board)

    if maximizing:
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat
    else:
        if stand_pat <= alpha:
            return alpha
        if stand_pat < beta:
            beta = stand_pat

    if qdepth >= MAX_QUIESCENCE_DEPTH:
        return stand_pat

    tt_move = seen_states.get(current_hash, {}).get("move")

    noisy = []
    for m in board.legal_moves:
        # only captures and promotions (no checks here for speed)
        if not (board.is_capture(m) or m.promotion is not None):
            continue

        # Only consider promotions to a queen (others rarely worth it in QS)
        if m.promotion is not None and m.promotion != chess.QUEEN:
            continue

        # delta pruning for captures: if the best-case gain can’t help, skip
        if board.is_capture(m):
            victim = board.piece_at(m.to_square)
            attacker = board.piece_at(m.from_square)
            v = _MVV_VAL[victim.piece_type] if victim else 0
            a = _MVV_VAL[attacker.piece_type] if attacker else 0

            # Skip obviously bad trades where attacker >> victim by a margin
            if (a - v) > QS_BAD_TRADE_MARGIN and m.promotion is None:
                continue

            # stronger delta margin to cut hopeless captures early
            if maximizing and (stand_pat + v + QS_DELTA_MARGIN <= alpha):
                continue
            if (not maximizing) and (stand_pat - v - QS_DELTA_MARGIN >= beta):
                continue

        noisy.append(m)

    if not noisy:
        return stand_pat

    if maximizing:
        value = stand_pat
        for move in order_moves(board, noisy, tt_move=tt_move):
            new_hash = process_move(current_hash, board, move)
            board.push(move)
            score = quiescence(board, alpha, beta, False, new_hash, qdepth + 1)
            board.pop()
            if score > value:
                value = score
            if value > alpha:
                alpha = value
            if alpha >= beta:
                break
        return value
    else:
        value = stand_pat
        for move in order_moves(board, noisy, tt_move=tt_move):
            new_hash = process_move(current_hash, board, move)
            board.push(move)
            score = quiescence(board, alpha, beta, True, new_hash, qdepth + 1)
            board.pop()
            if score < value:
                value = score
            if value < beta:
                beta = value
            if alpha >= beta:
                break
        return value


# ========= Root driver (ID + aspiration) =========
def get_best_move(board, depth=None):
    if depth is None:
        depth = lookahead
    if board.legal_moves.count() == 0:
        return None

    # Opening book for early moves
    if BOOK is not None and board.fullmove_number <= 10:
        try:
            book_move = get_opening_move(board)
        except Exception:
            book_move = None
        if book_move:
            return book_move

    # Reset/prepare search state per root
    global seen_states, hit_count, history_heuristic, killer_moves, nodes, qnodes
    seen_states = {}
    hit_count = 0
    nodes = 0
    qnodes = 0

    # light decay to keep history bounded
    history_heuristic = {k: int(v * 0.95) for k, v in history_heuristic.items() if v > 1}
    for k in list(killer_moves.keys()):
        if len(killer_moves[k]) > 2:
            killer_moves[k] = list(killer_moves[k])[:2]

    current_hash = get_board_hash(board)
    best_move = None
    best_val = 0  # neutral guess for aspiration

    # Simple endgame depth extension heuristic
    array = board_to_array(board)
    nonzero = int(np.count_nonzero(array))
    if board.legal_moves.count() < 15 and nonzero < 8:
        depth = max(depth, 5)

    # Iterative deepening
    for d in range(1, depth + 1):
        pv_move = seen_states.get(current_hash, {}).get("move")
        moves = list(board.legal_moves)
        ordered = order_moves(board, moves, tt_move=pv_move, depth=0)

        # Aspiration window only for deeper iterations; wider to reduce re-searches
        if USE_ASPIRATION and d >= 5:
            window = 150
            alpha = best_val - window
            beta  = best_val + window
        else:
            alpha = float('-inf')
            beta  = float('inf')

        if board.turn == chess.WHITE:
            best_val_iter = float('-inf')
            best_move_iter = best_move or (ordered[0] if ordered else None)
            for move in ordered:
                new_hash = process_move(current_hash, board, move)
                board.push(move)
                value = min_max(board, d - 1, alpha, beta, False, new_hash, ply=1)
                if value <= alpha or value >= beta:
                    value = min_max(board, d - 1, float('-inf'), float('inf'), False, new_hash, ply=1)
                board.pop()
                if value > best_val_iter:
                    best_val_iter = value
                    best_move_iter = move
                if value > alpha:
                    alpha = value
            best_val = best_val_iter
            best_move = best_move_iter
        else:
            best_val_iter = float('inf')
            best_move_iter = best_move or (ordered[0] if ordered else None)
            for move in ordered:
                new_hash = process_move(current_hash, board, move)
                board.push(move)
                value = min_max(board, d - 1, alpha, beta, True, new_hash, ply=1)
                if value <= alpha or value >= beta:
                    value = min_max(board, d - 1, float('-inf'), float('inf'), True, new_hash, ply=1)
                board.pop()
                if value < best_val_iter:
                    best_val_iter = value
                    best_move_iter = move
                if value < beta:
                    beta = value
            best_val = best_val_iter
            best_move = best_move_iter

        print(f"[depth {d}] nodes={nodes:,} qnodes={qnodes:,} tt_hits={hit_count:,} best={best_move} score={best_val}")

    print("final score:", best_val, "tt_hits:", hit_count, "tt_size:", len(seen_states))
    return best_move

# ========= Opening book =========
def get_opening_move(board: chess.Board) -> chess.Move | None:
    if BOOK is None:
        return None
    try:
        entry = BOOK.weighted_choice(board)
        return entry.move if entry else None
    except Exception:
        return None

# ========= Evaluation =========
def evaluate_board(board):
    # treat draws as neutral to avoid pushing lost positions for 50-move/3fold
    if board.is_stalemate() or board.can_claim_threefold_repetition() or board.can_claim_fifty_moves():
        return 0

    score = 0
    array_board = board_to_array(board)

    material_scores = count_material(array_board)
    development_scores = development(board, array_board)
    pawn_scores = pawn_push(array_board)

    score += material_scores[0] - material_scores[1]
    score += (development_scores[0] - development_scores[1]) * 0.1
    score += (pawn_scores[0] - pawn_scores[1]) * 0.1
    return score

def count_material(array_board):
    scores = [0, 0]
    for row in array_board:
        for piece in row:
            if piece > 0:
                scores[0] += piece_to_value(piece)
            elif piece < 0:
                scores[1] += piece_to_value(piece)
    return scores

def development(board, array_board):
    scores = [0, 0]
    for r_index, row in enumerate(array_board):
        for c_index, cell in enumerate(row):
            if cell == 0:
                continue
            if cell > 0 and piece_to_value(cell) == 3:  # knights/bishops
                # NOTE: array row 0 is rank 8, so invert rank to query board square
                sq = chess.square(c_index, 7 - r_index)
                scores[0] += len(board.attacks(sq))
            elif cell < 0 and piece_to_value(cell) == 3:
                sq = chess.square(c_index, 7 - r_index)
                scores[1] += len(board.attacks(sq))
    return scores

def pawn_push(array_board):
    # reward central files (d/e) for BOTH colors
    scores = [0, 0]
    for r in range(8):
        for c in range(8):
            cell = array_board[r, c]
            if cell == 1:      # white pawn
                if c in (3, 4): scores[0] += 1
            elif cell == -1:   # black pawn
                if c in (3, 4): scores[1] += 1
    return scores

def piece_to_value(piece):
    pt = abs(piece)
    if pt == 1:
        return 1
    elif pt in (2, 3):
        return 3
    elif pt == 4:
        return 5
    elif pt == 5:
        return 9
    elif pt == 6:
        return 10000
    else:
        # fallback (shouldn't happen)
        return 0

# Convert python-chess Board to numpy 8x8 array
def board_to_array(board):
    arr = np.zeros((ROWS, COLS), dtype=DTYPE)
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            sym = piece.symbol()
            r = 7 - chess.square_rank(square)  # row 0 is rank 8
            c = chess.square_file(square)
            arr[r, c] = PIECE_MAP[sym]
    return arr
