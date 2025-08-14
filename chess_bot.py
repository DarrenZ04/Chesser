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



def min_max(board, depth, alpha, beta, maximizing, current_hash):
    if current_hash in seen_states:
        entry = seen_states[current_hash]
        global hit_count
        hit_count += 1
        return entry["score"]

    if depth == 0 or board.is_game_over():
        if board.is_checkmate():
            return float('-inf') if maximizing else float('inf')
        return evaluate_board(board)

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
        seen_states[current_hash] = {"score": max_score}
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
        seen_states[current_hash] = {"score": min_score}
        return min_score
    
def get_best_move(board, depth = lookahead):
    if board.legal_moves.count() == 0:
        return None

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