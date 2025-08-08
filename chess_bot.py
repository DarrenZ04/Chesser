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

# pawn weights for positional evaluation
PAWN_TABLE = [
    [0,   0,   0,   0,   0,   0,   0,   0],
    [5,   5,   5,   5,   5,   5,   5,   5],
    [1,   1,   2,   3,   3,   2,   1,   1],
    [0.5, 0.5, 1,   2.5, 2.5, 1,   0.5, 0.5],
    [0,   0,   0,   2,   2,   0,   0,   0],
    [0.5,-0.5,-1,   0,   0,  -1, -0.5, 0.5],
    [0.5, 1,   1,  -2,  -2,  1,   1,   0.5],
    [0,   0,   0,   0,   0,   0,   0,   0]
]

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
lookahead = 6
nmp_reduction = 3
#opening book data
BOOK = chess.polyglot.open_reader("openings/book.bin")
# analyzed states
seen_states = {}
hit_count = 0
full_eval_count = 0
nmp_attempt = 0
nmp_success = 0

def min_max(board, depth, alpha, beta, maximizing, current_hash, caching = True):
    if current_hash in seen_states:
        entry = seen_states[current_hash]
        if depth >= entry["depth"]:     
            global hit_count
            hit_count += 1
            return entry["score"]

    if depth == 0 or board.is_game_over():
        if board.is_checkmate():
            return float('-inf') if maximizing else float('inf')
        global full_eval_count
        full_eval_count += 1
        return evaluate_board_fast(board)
    
    if maximizing and depth >= 3:
        board.push(chess.Move.null())
        v = -min_max(board, depth - nmp_reduction, 1 - beta, -beta, not maximizing, get_board_hash(board), False)
        board.pop()
        global nmp_attempt
        nmp_attempt += 1
        
        if v >= beta:
            global nmp_success
            nmp_success += 1
            return v

    if maximizing:
        max_score = float('-inf')
        for move in board.legal_moves:
            new_hash = process_move(current_hash, board, move)

            board.push(move)
            score = min_max(board, depth - 1, alpha, beta, not maximizing, new_hash)
            board.pop()

            max_score = max(max_score, score)
            alpha = max(alpha, score)
            if beta <= alpha:
                break
        if caching:
            seen_states[current_hash] = {
                "score": max_score,
                "depth": depth,
                # "state": get_board_state_hash(board)
            }
        return max_score
    else:
        min_score = float('inf')
        for move in board.legal_moves:
            new_hash = process_move(current_hash, board, move)

            board.push(move)
            score = min_max(board, depth - 1, alpha, beta, not maximizing, new_hash)
            board.pop()

            min_score = min(min_score, score)
            beta = min(beta, score)
            if beta <= alpha:
                break
        if caching:
            seen_states[current_hash] = {
                "score": min_score,
                "depth": depth,
                # "state": get_board_state_hash(board)
            }
        return min_score
    
def get_best_move(board, depth = lookahead):
    if board.legal_moves.count() == 0:
        return None
    
    if len(seen_states) > 0:
        clear_stored_states(board)

    best_move = [m for m in board.legal_moves][0]
    array = board_to_array(board)
    count = 0

    if board.fullmove_number <= 10:           # book for the first 10 moves
        book_move = get_opening_move(board)
        if book_move:
            return book_move
        
    for row in array:
        for num in row:
            if num != 0:
                count += 1
    if board.legal_moves.count() < 15 and count < 8:
        depth = 5

    if board.turn == chess.WHITE:
        best_val = float('-inf')
        for move in board.legal_moves:
            board.push(move)
            hash = get_board_hash(board)
            value = min_max(board, depth - 1, float('-inf'), float('inf'), False, hash)
            board.pop()
            if value > best_val:
                best_val = value
                best_move = move
    else:
        best_val = float('inf')
        for move in board.legal_moves:
            board.push(move)
            hash = get_board_hash(board)
            value = min_max(board, depth - 1, float('-inf'), float('inf'), True, hash)
            board.pop()
            if value < best_val:
                best_val = value
                best_move = move

    print("final score:", best_val)
    print("full eval count", full_eval_count)
    print("hit count:", hit_count)
    print("seen_states size:", len(seen_states))
    print("nmp_attempt", nmp_attempt, "nmp_success:", nmp_success)
    print()
    return best_move

def clear_stored_states(board):
    min_depth = len(board.move_stack)
    keys_to_delete = [key for key, state in seen_states.items() if state["depth"] < min_depth]
    for key in keys_to_delete:
        del seen_states[key]
    
    # board_state_hash = get_board_state_hash(board)
    # keys_to_delete = [key for key, state in seen_states.items() if not board_state_hash == state["state"]]
    # for key in keys_to_delete:
    #     del seen_states[key]

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

# does the same thing as evaluate_board, but does it all at once for speed
# doesn't use functions is all self contained
def evaluate_board_fast(board):
    score = 0
    mat_scores = [0, 0]
    dev_scores = [0, 0]
    pawn_scores = [0, 0]
    array_board = board_to_array(board)

    for r_index, row in enumerate(array_board):
        for c_index, cell in enumerate(row):
            # count material
            if cell > 0:
                mat_scores[0] += piece_to_value(cell)
                # Piece-square table for white pawns
                if abs(cell) == 1:
                    score += PAWN_TABLE[r_index][c_index]
            elif cell < 0:
                mat_scores[1] += piece_to_value(cell)
                # Piece-square table for black pawns (flip table)
                if abs(cell) == 1:
                    score -= PAWN_TABLE[7 - r_index][c_index]

            # development
            if cell > 0 and piece_to_value(cell) == 3: # knights and bishops
                dev_scores[0] += len(board.attacks(chess.square(c_index, r_index)))
            elif cell < 0 and piece_to_value(cell) == 3: # knights and bishops
                dev_scores[1] += len(board.attacks(chess.square(c_index, r_index)))

            # pawn scores
            if cell > 0 and piece_to_value(cell) == 1: # pawns
                if c_index in (3, 5):
                    pawn_scores[0] += 1
                elif c_index == 4:
                    pawn_scores[0] += 2
            elif cell < 0 and piece_to_value(cell) == 1: # pawns
                if c_index in (6, 4):
                    pawn_scores[0] += 1
                elif c_index == 5:
                    pawn_scores[0] += 2

    score += mat_scores[0] - mat_scores[1]
    score += (dev_scores[0] - dev_scores[1]) * 0.1
    score += (pawn_scores[0] - pawn_scores[1]) * 0.1

    return score        


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