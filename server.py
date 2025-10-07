from flask import Flask, request, jsonify
from flask import Flask, render_template, request, jsonify
import chess
from chess_bot import get_best_move, board_to_array  # import your functions

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/new_game', methods=['GET'])
def new_game():
    board = chess.Board()
    return jsonify({
        'fen': board.fen()
    })

@app.route('/api/move', methods=['POST'])
def make_move():
    data = request.get_json()
    fen = data['fen']              # current position in FEN
    move_uci = data.get('move')    # human's UCI string, e.g. "e2e4", or None if AI to play
    depth = data.get('depth', 3)   # AI lookahead depth, default to 3
    board = chess.Board(fen)

    # Apply human move if provided
    if move_uci:
        board.push_uci(move_uci)

    # Let the AI pick its move with specified depth
    ai_move = get_best_move(board, depth)    # returns a chess.Move
    board.push(ai_move)

    return jsonify({
        'move': ai_move.uci(),         # e.g. "g8f6"
        'fen': board.fen()             # new position
    })

if __name__ == '__main__':
    app.run(debug=True)