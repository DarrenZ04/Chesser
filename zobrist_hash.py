import math
import pygame
import sys
import os
import chess
import numpy as np
import chess.polyglot
import random

np.random.seed(718)

NUM_SQUARES = 64
NUM_PIECE_TYPES = 6

# zorbist hash
# pawn, knight, bishop, rook, queen, king
# positions go a1, b1, ..., g8, h8
# access white pawn c1 = white_pieces[3]
white_pieces = np.random.randint(0, 2**64, NUM_PIECE_TYPES * NUM_SQUARES, dtype=np.uint64)
black_pieces = np.random.randint(0, 2**64, NUM_PIECE_TYPES * NUM_SQUARES, dtype=np.uint64)

# indicates castling rights
# left castle is index 1
white_castle = np.random.randint(0, 2**64, 2, dtype=np.uint64)
black_castle = np.random.randint(0, 2**64, 2, dtype=np.uint64)

# blacks turn
black_turn = np.random.randint(0, 2**64, 1, dtype=np.uint64).item()

# en passant active, access by row
en_passant = np.random.randint(0, 2**64, 8, dtype=np.uint64)


def get_board_hash(board):
    hash = np.uint64(0)

    if board.turn == chess.BLACK:
        hash = np.bitwise_xor(hash, black_turn)

    if board.has_kingside_castling_rights(chess.WHITE):
        hash = np.bitwise_xor(hash, white_castle[1])
    if board.has_queenside_castling_rights(chess.WHITE):
        hash = np.bitwise_xor(hash, white_castle[0])
    if board.has_kingside_castling_rights(chess.BLACK):
        hash = np.bitwise_xor(hash, black_castle[1])
    if board.has_queenside_castling_rights(chess.BLACK):
        hash = np.bitwise_xor(hash, black_castle[0])

    for i in range(8):
        for j in range(8):
            # board.piece_at
            square = chess.square(j, i)
            piece = board.piece_at(square)

            if piece == None:
                continue

            piece_hash = get_piece_hash(piece, square)

            hash = np.bitwise_xor(hash, piece_hash)
    
    if board.ep_square is not None:
        file = chess.square_file(board.ep_square)
        hash = np.bitwise_xor(hash, en_passant[file])
    
    return hash

def process_move(hash, board, move):
    origin = move.from_square
    destination = move.to_square
    piece = board.piece_at(origin)
    origin_hash = get_piece_hash(piece, origin)
    destination_hash = get_piece_hash(piece, destination)

    white_move = False
    if board.turn == chess.WHITE:
        white_move = True

    if board.is_en_passant(move):
        # dehash captured pawn
        if white_move:
            en_passant_square = destination - 8
        else:
            en_passant_square = destination + 8

        en_passant_captured = board.piece_at(en_passant_square)
        en_passant_hash = get_piece_hash(en_passant_captured, en_passant_square)

        hash = np.bitwise_xor(hash, en_passant_hash)

    elif board.is_capture(move):
        # dehash the captured piece
        captured = board.piece_at(destination)

        captured_hash = get_piece_hash(captured, destination)

        hash = np.bitwise_xor(hash, captured_hash)
    elif board.is_castling(move):
        if board.is_kingside_castling(move):
            # hash rook movement kingside
            if white_move:
                rook_origin = chess.H1
                rook_destination = chess.F1
            else:
                rook_origin = chess.H8
                rook_destination = chess.F8
        else:
            # hash rook movement queenside
            if white_move:
                rook_origin = chess.A1
                rook_destination = chess.D1
            else:
                rook_origin = chess.A8
                rook_destination = chess.D8
        
        rook = board.piece_at(rook_origin)

        rook_origin_hash = get_piece_hash(rook, rook_origin)
        rook_destination_hash = get_piece_hash(rook, rook_destination)

        hash = np.bitwise_xor(hash, rook_origin_hash)
        hash = np.bitwise_xor(hash, rook_destination_hash)
    
    elif move.promotion != None:
        promoted_piece = chess.Piece(move.promotion, piece.color)
        promoted_hash = get_piece_hash(promoted_piece, destination)
        pawn_hash = get_piece_hash(piece, destination)

        hash = np.bitwise_xor(hash, promoted_hash)
        # special hash, adds pawn at destination location but it is removed by
        # hashing with destination_hash later
        hash = np.bitwise_xor(hash, pawn_hash)

    # remove castling rights
    if piece.piece_type == chess.KING:
        if white_move:
            hash = np.bitwise_xor(hash, white_castle[0])
            hash = np.bitwise_xor(hash, white_castle[1])
        else:
            hash = np.bitwise_xor(hash, black_castle[0])
            hash = np.bitwise_xor(hash, black_castle[1])
    elif piece.piece_type == chess.ROOK:
        if origin == chess.A1:
            hash = np.bitwise_xor(hash, white_castle[0])
        elif origin == chess.H1:
            hash = np.bitwise_xor(hash, white_castle[1])
        elif origin == chess.A8:
            hash = np.bitwise_xor(hash, black_castle[0])
        elif origin == chess.H8:
            hash = np.bitwise_xor(hash, black_castle[1])
    
    # update en passant squares
    if board.ep_square is not None:
        old_file = chess.square_file(board.ep_square)
        hash = np.bitwise_xor(hash, en_passant[old_file])
    
    if piece.piece_type == chess.PAWN and abs(destination - origin) == 16:
        # double pawn push -> en passant square is behind the pawn
        new_ep_file = chess.square_file(destination)
        hash = np.bitwise_xor(hash, en_passant[new_ep_file])


    hash = np.bitwise_xor(hash, origin_hash)
    hash = np.bitwise_xor(hash, destination_hash)

    hash = np.bitwise_xor(hash, black_turn)

    return hash

# used to get "board states" for irreversible moves
def get_board_state_hash(board):
    hash = np.uint64(0)

    if board.has_kingside_castling_rights(chess.WHITE):
        hash = np.bitwise_xor(hash, white_castle[1])
    if board.has_queenside_castling_rights(chess.WHITE):
        hash = np.bitwise_xor(hash, white_castle[0])
    if board.has_kingside_castling_rights(chess.BLACK):
        hash = np.bitwise_xor(hash, black_castle[1])
    if board.has_queenside_castling_rights(chess.BLACK):
        hash = np.bitwise_xor(hash, black_castle[0])

    if board.ep_square is not None:
        file = chess.square_file(board.ep_square)
        hash = np.bitwise_xor(hash, en_passant[file])
    
    return hash

def get_piece_hash(piece, square_index):
    if piece == None:
        return None

    type = piece.piece_type

    if piece.color == chess.WHITE:
        # print()
        return white_pieces[(type - 1) * NUM_SQUARES + square_index]
    else:
        # print()
        return black_pieces[(type - 1) * NUM_SQUARES + square_index]


################################################################################
# TESTING
################################################################################

# board = chess.Board()

# hash = compute_board_hash(board)
# print(hash)
# print()

# move = chess.Move.from_uci("e2e4")
# hash = process_move(hash, board, move)
# board.push(move)
# print("predicted hash", hash)
# print("true hash", compute_board_hash(board))
# print()

# move = chess.Move.from_uci("d7d5")
# hash = process_move(hash, board, move)
# board.push(move)
# print("predicted hash", hash)
# print("true hash", compute_board_hash(board))
# print()

# move = chess.Move.from_uci("e4d5")
# hash = process_move(hash, board, move)
# board.push(move)
# print("predicted hash", hash)
# print("true hash", compute_board_hash(board))
# print()

# move = chess.Move.from_uci("e7e5")
# board.push(move)
# print(compute_board_hash(board))

# for i in range(8):
#     for j in range(8):
#         # board.piece_at
#         square = chess.square(j, i)

#         piece = board.piece_at(square)
#         if piece == None:
#             continue

#         square_index = chess.parse_square(chess.square_name(square))

#         print(square, piece, compute_piece_index(piece, square_index))
#         # print("hello")