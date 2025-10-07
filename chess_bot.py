import math
import pygame
import sys
import os
import chess
import numpy as np
import chess.polyglot
import random

from zobrist_hash import *

# [-4, -2, -3, -5, -6, -3, -2, -4],  
# [-1, -1, -1, -1, -1, -1, -1, -1],  
# [ 0,  0,  0,  0,  0,  0,  0,  0], 
# [ 0,  0,  0,  0,  0,  0,  0,  0],  
# [ 0,  0,  0,  0,  0,  0,  0,  0], 
# [ 0,  0,  0,  0,  0,  0,  0,  0],
# [ 1,  1,  1,  1,  1,  1,  1,  1], 
# [ 4,  2,  3,  5,  6,  3,  2,  4]


# Window settings
WIDTH, HEIGHT = 480, 480
ROWS, COLS = 8, 8
SQ_SIZE = WIDTH // COLS
FPS = 60

# Colors
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

#depth of search - 1
lookahead = 4
#opening book data
BOOK = chess.polyglot.open_reader("openings/book.bin")
# analyzed states
seen_states = {}
hit_count = 0

# transposition table entry flags
TT_EXACT = 0
TT_LOWERBOUND = 1
TT_UPPERBOUND = 2

# simple move-ordering helpers
history_heuristic = {}
killer_moves = {}

MAX_QUIESCENCE_DEPTH = 8

def _mvv_lva(board, move):
    # Most Valuable Victim - Least Valuable Attacker scoring for captures
    if not board.is_capture(move):
        return 0
    victim = board.piece_at(move.to_square)
    attacker = board.piece_at(move.from_square)
    v = piece_to_value(PIECE_MAP[victim.symbol()] if victim else 0) if victim else 0
    a = piece_to_value(PIECE_MAP[attacker.symbol()] if attacker else 0) if attacker else 0
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
        try:
            if board.gives_check(m):
                score += 1_000
        except Exception:
            pass
        score += history_heuristic.get((depth, m), 0)
        if depth in killer_moves and m in killer_moves[depth]:
            score += 500
        scored.append((score, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored]



def min_max(board, depth, alpha, beta, maximizing, current_hash, ply=0):
    # Transposition table probe
    if current_hash in seen_states:
        entry = seen_states[current_hash]
        if entry["depth"] >= depth:
            global hit_count
            hit_count += 1
            flag = entry["flag"]
            if flag == TT_EXACT:
                return entry["score"]
            if flag == TT_LOWERBOUND and entry["score"] > alpha:
                alpha = entry["score"]
            elif flag == TT_UPPERBOUND and entry["score"] < beta:
                beta = entry["score"]
            if alpha >= beta:
                return entry["score"]

    if depth == 0 or board.is_game_over():
        if board.is_checkmate():
            return float('-inf') if maximizing else float('inf')
        # Quiescence search to reduce horizon effect
        return quiescence(board, alpha, beta, maximizing, current_hash, qdepth=0)

    best_move = seen_states.get(current_hash, {}).get("move")

    if maximizing:
        value = float('-inf')
        legal_moves = list(board.legal_moves)
        for move in order_moves(board, legal_moves, tt_move=best_move, depth=ply):
            new_hash = process_move(current_hash, board, move)
            board.push(move)
            score = min_max(board, depth - 1, alpha, beta, False, new_hash, ply+1)
            board.pop()
            if score > value:
                value = score
                best_move = move
            if score > alpha:
                alpha = score
                # update history heuristic on beta-improving moves
                history_heuristic[(ply, move)] = history_heuristic.get((ply, move), 0) + depth * depth
            if alpha >= beta:
                # store killer move
                killer_moves.setdefault(ply, set()).add(move)
                break
        # store TT
        flag = TT_EXACT
        if value <= alpha:
            flag = TT_UPPERBOUND
        elif value >= beta:
            flag = TT_LOWERBOUND
        seen_states[current_hash] = {"score": value, "depth": depth, "flag": flag, "move": best_move}
        return value
    else:
        value = float('inf')
        legal_moves = list(board.legal_moves)
        for move in order_moves(board, legal_moves, tt_move=best_move, depth=ply):
            new_hash = process_move(current_hash, board, move)
            board.push(move)
            score = min_max(board, depth - 1, alpha, beta, True, new_hash, ply+1)
            board.pop()
            if score < value:
                value = score
                best_move = move
            if score < beta:
                beta = score
                history_heuristic[(ply, move)] = history_heuristic.get((ply, move), 0) + depth * depth
            if alpha >= beta:
                killer_moves.setdefault(ply, set()).add(move)
                break
        flag = TT_EXACT
        if value <= alpha:
            flag = TT_UPPERBOUND
        elif value >= beta:
            flag = TT_LOWERBOUND
        seen_states[current_hash] = {"score": value, "depth": depth, "flag": flag, "move": best_move}
        return value

def quiescence(board, alpha, beta, maximizing, current_hash, qdepth=0):
    # Stand pat
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

    # Only consider noisy moves
    tt_move = seen_states.get(current_hash, {}).get("move")
    captures = [m for m in board.legal_moves if board.is_capture(m) or m.promotion is not None]
    if not captures:
        return stand_pat

    if maximizing:
        value = stand_pat
        for move in order_moves(board, captures, tt_move=tt_move):
            new_hash = process_move(current_hash, board, move)
            board.push(move)
            score = quiescence(board, alpha, beta, False, new_hash, qdepth+1)
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
        for move in order_moves(board, captures, tt_move=tt_move):
            new_hash = process_move(current_hash, board, move)
            board.push(move)
            score = quiescence(board, alpha, beta, True, new_hash, qdepth+1)
            board.pop()
            if score < value:
                value = score
            if value < beta:
                beta = value
            if alpha >= beta:
                break
        return value
    
def get_best_move(board, depth=None):
    if depth is None:
        depth = lookahead
    if board.legal_moves.count() == 0:
        return None

    # Opening book for early moves
    if board.fullmove_number <= 10:
        book_move = get_opening_move(board)
        if book_move:
            return book_move

    # Reset/prepare search state per root
    global seen_states, hit_count
    seen_states = {}
    hit_count = 0

    current_hash = get_board_hash(board)
    best_move = None
    best_val = float('-inf') if board.turn == chess.WHITE else float('inf')

    # Simple endgame depth extension heuristic
    array = board_to_array(board)
    nonzero = int(np.count_nonzero(array))
    if board.legal_moves.count() < 15 and nonzero < 8:
        depth = max(depth, 5)

    # Iterative deepening to improve move ordering
    for d in range(1, depth + 1):
        alpha = float('-inf')
        beta = float('inf')
        pv_move = seen_states.get(current_hash, {}).get("move")
        moves = list(board.legal_moves)
        ordered = order_moves(board, moves, tt_move=pv_move, depth=0)
        if board.turn == chess.WHITE:
            best_val_iter = float('-inf')
            best_move_iter = best_move or (ordered[0] if ordered else None)
            for move in ordered:
                new_hash = process_move(current_hash, board, move)
                board.push(move)
                value = min_max(board, d - 1, alpha, beta, False, new_hash, ply=1)
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
                board.pop()
                if value < best_val_iter:
                    best_val_iter = value
                    best_move_iter = move
                if value < beta:
                    beta = value
            best_val = best_val_iter
            best_move = best_move_iter

    print("final score:", best_val, hit_count, len(seen_states))
    return best_move

def get_opening_move(board: chess.Board) -> chess.Move | None:
    """
    Returns a book move for this position, or None if none found.
    """
    try:
        # weighted_choice picks proportionally to entry weights
        entry = BOOK.weighted_choice(board)
        return entry.move if entry else None
    except IndexError:
        return None
    
def evaluate_board(board):
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
                # white case
                scores[0] += piece_to_value(piece)
            elif piece < 0:
                # black case
                scores[1] += piece_to_value(piece)
    return scores

def development(board, array_board):
    scores = [0, 0]

    for r_index, row in enumerate(array_board):
        for c_index, cell in enumerate(row):
            if cell > 0 and piece_to_value(cell) == 3: # knights and bishops
                # white case
                scores[0] += len(board.attacks(chess.square(c_index, r_index)))
            elif cell < 0 and piece_to_value(cell) == 3: # knights and bishops
                # black case
                scores[1] += len(board.attacks(chess.square(c_index, r_index)))
    return scores

def pawn_push(array_board):
    scores = [0, 0]

    for r_index, row in enumerate(array_board):
        for c_index, cell in enumerate(row):
            if cell > 0 and piece_to_value(cell) == 1: # pawns
                # white case
                if c_index in (3, 5):
                    scores[0] += 1
                elif c_index == 4:
                    scores[0] += 2
            elif cell < 0 and piece_to_value(cell) == 1: # pawns
                # black case
                if c_index in (6, 4):
                    scores[0] += 1
                elif c_index == 5:
                    scores[0] += 2
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
        print("error :)", pt)
        exit()

# Convert python-chess Board to numpy 8x8 array
def board_to_array(board):
    arr = np.zeros((ROWS, COLS), dtype=DTYPE)
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            sym = piece.symbol()
            r = 7 - chess.square_rank(square)
            c = chess.square_file(square)
            arr[r, c] = PIECE_MAP[sym]
    return arr