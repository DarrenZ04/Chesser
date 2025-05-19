import pygame
import sys
import os
import chess
import numpy as np

# Window settings
WIDTH, HEIGHT = 480, 480
ROWS, COLS = 8, 8
SQ_SIZE = WIDTH // COLS
FPS = 60

# Colors
WHITE = (245, 245, 220)
GRAY = (119, 136, 153)
SELECT_HIGHLIGHT = (186, 202, 68)
MOVE_HIGHLIGHT = (105, 105, 105)

# Map piece symbols to integers for fast board-state access
DTYPE = np.int8
PIECE_MAP = {
    'P':  1, 'N':  2, 'B':  3, 'R':  4, 'Q':  5, 'K':  6,
    'p': -1, 'n': -2, 'b': -3, 'r': -4, 'q': -5, 'k': -6
}

# Load images from 'images/' folder. Names: wp.png, wn.png, ... bn.png, etc.
def load_images():
    images = {}
    base_path = 'images'
    for symbol in PIECE_MAP:
        name = f"{ 'w' if symbol.isupper() else 'b'}{symbol.lower()}"
        for ext in ('png','jpg','jpeg'):
            path = os.path.join(base_path, f"{name}.{ext}")
            if os.path.isfile(path):
                img = pygame.image.load(path)
                images[symbol] = pygame.transform.smoothscale(img, (SQ_SIZE, SQ_SIZE))
                break
        else:
            raise FileNotFoundError(f"Missing image for '{symbol}' in {base_path}")
    return images

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

# Draw the checkerboard
def draw_board(win):
    for r in range(ROWS):
        for c in range(COLS):
            color = WHITE if (r + c) % 2 == 0 else GRAY
            pygame.draw.rect(win, color, (c * SQ_SIZE, r * SQ_SIZE, SQ_SIZE, SQ_SIZE))

# Highlight selected square and legal move squares
def draw_highlights(win, selected, moves):
    if selected is not None:
        r = 7 - chess.square_rank(selected)
        c = chess.square_file(selected)
        pygame.draw.rect(win, SELECT_HIGHLIGHT, (c*SQ_SIZE, r*SQ_SIZE, SQ_SIZE, SQ_SIZE))
    for dest in moves:
        r = 7 - chess.square_rank(dest)
        c = chess.square_file(dest)
        # draw a small circle in center
        center = (c*SQ_SIZE + SQ_SIZE//2, r*SQ_SIZE + SQ_SIZE//2)
        pygame.draw.circle(win, MOVE_HIGHLIGHT, center, SQ_SIZE//6)

# Draw pieces on board
def draw_pieces(win, board, images):
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            sym = piece.symbol()
            r = 7 - chess.square_rank(square)
            c = chess.square_file(square)
            win.blit(images[sym], (c*SQ_SIZE, r*SQ_SIZE))

# Main loop
def main():
    pygame.init()
    win = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('Python Chess')
    clock = pygame.time.Clock()

    board = chess.Board()
    images = load_images()
    board_array = board_to_array(board)

    selected = None
    legal_moves = []

    running = True
    while running:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                c = mx // SQ_SIZE
                r = my // SQ_SIZE
                clicked = chess.square(c, 7 - r)
                piece = board.piece_at(clicked)
                # If no selection yet, select your piece and show moves
                if selected is None:
                    if piece and piece.color == board.turn:
                        selected = clicked
                        # collect dest squares for moves from this square
                        legal_moves = [m.to_square for m in board.legal_moves if m.from_square == selected]
                else:
                    # If clicked on a legal destination, make that move
                    if clicked in legal_moves:
                        # find move object (handle promotions)
                        move = next((m for m in board.legal_moves
                                     if m.from_square == selected and m.to_square == clicked), None)
                        if move:
                            board.push(move)
                            board_array = board_to_array(board)
                    # clear selection in any case
                    selected = None
                    legal_moves = []

        draw_board(win)
        draw_highlights(win, selected, legal_moves)
        draw_pieces(win, board, images)
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    main()
