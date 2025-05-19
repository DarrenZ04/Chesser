import math
import pygame
import sys
import os
import chess
import numpy as np

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

lookahead = 3


def min_max(board, depth, alpha, beta, maximizing):
    if depth == 0 or board.is_game_over():
        if board.is_checkmate():
            return float('-inf') if maximizing else float('inf')
        return evaluate_board(board)

    if maximizing:
        max_score = float('-inf')
        for move in board.legal_moves:
            board.push(move)
            score = min_max(board, depth - 1, alpha, beta, not maximizing)
            board.pop()
            max_score = max(max_score, score)
            alpha = max(alpha, score)
            if beta <= alpha:
                break
        return max_score
    else:
        min_score = float('inf')
        for move in board.legal_moves:
            board.push(move)
            score = min_max(board, depth - 1, alpha, beta, not maximizing)
            board.pop()
            min_score = min(min_score, score)
            alpha = min(alpha, score)
            if beta <= alpha:
                break
        return min_score
    
def get_best_move(board, depth = lookahead):
    best_move = None
    array = board_to_array(board)
    count = 0
    for row in array:
        for num in row:
            if num != 0:
                count += 1
    if board.legal_moves.count() < 15 and count < 10:
        depth = 8


    if board.turn == chess.WHITE:
        best_val = float('-inf')
        for move in board.legal_moves:
            board.push(move)
            value = min_max(board, depth - 1, float('-inf'), float('inf'), False)
            board.pop()
            if value > best_val:
                best_val = value
                best_move = move
    else:
        best_val = float('inf')
        for move in board.legal_moves:
            board.push(move)
            value = min_max(board, depth - 1, float('-inf'), float('inf'), True)
            board.pop()
            if value < best_val:
                best_val = value
                best_move = move
    return best_move

def evaluate_board(board):
    array_board = board_to_array(board)
    scores = count_material(array_board)
    return scores[0] - scores[1]

def count_material(board):
    scores = [0, 0]

    for row in board:
        for piece in row:
            if piece > 0:
                # white case
                scores[0] += piece_to_value(piece)
            elif piece < 0:
                # black case
                scores[1] += piece_to_value(piece)
    
    return scores

def piece_to_value(piece):
    pt = abs(piece)
    if pt == 1:
        return 1
    elif pt == 2 or 3:
        return 3
    elif pt == 4:
        return 5
    elif pt == 5:
        return 9
    elif pt == 6:
        return 10000
    else:
        print("error :)")
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