$(function () {
  const game = new Chess();
  let selectedSquare = null;
  let possibleMoves = [];

  const board = Chessboard('board', {
    draggable: true,
    position: 'start',
    pieceTheme: '/static/images/{piece}.png',
    onDrop,
    onDragStart: onDragStart,
    onMouseoverSquare: onMouseoverSquare,
    onMouseoutSquare: onMouseoutSquare,
    onSquareClick: onSquareClick
  });

  // Get current depth from selector
  function getCurrentDepth() {
    return parseInt($('#depth-selector').val());
  }

  // New game function
  function startNewGame() {
    clearMoveIndicators(); // Clear any existing indicators
    $.getJSON('/api/new_game', data => {
      game.load(data.fen);
      board.position(data.fen);
    });
  }

  // First get a fresh starting position
  startNewGame();

  // New game button handler
  $('#new-game-btn').click(startNewGame);

  // Handle piece selection and move highlighting
  function onDragStart(source, piece, position, orientation) {
    // Only allow moves for the current player
    if ((game.turn() === 'w' && piece.search(/^b/) !== -1) ||
      (game.turn() === 'b' && piece.search(/^w/) !== -1)) {
      return false;
    }

    selectedSquare = source;
    showPossibleMoves(source);
    return true;
  }

  function onMouseoverSquare(square, piece) {
    // Show possible moves when hovering over a piece
    if (piece &&
      ((game.turn() === 'w' && piece.search(/^w/) !== -1) ||
        (game.turn() === 'b' && piece.search(/^b/) !== -1))) {
      showPossibleMoves(square);
    }
  }

  function onMouseoutSquare(square, piece) {
    // Clear moves when mouse leaves square (unless it's the selected square)
    if (square !== selectedSquare) {
      clearMoveIndicators();
    }
  }

  function showPossibleMoves(square) {
    clearMoveIndicators();

    const moves = game.moves({
      square: square,
      verbose: true
    });

    possibleMoves = moves;

    // Highlight selected square
    $(`#board .square-${square}`).addClass('square-selected');

    // Add move indicators
    moves.forEach(move => {
      const targetSquare = move.to;
      const isCapture = move.captured !== null;

      const dotClass = isCapture ? 'capture-dot' : 'move-dot';
      $(`#board .square-${targetSquare}`).append(`<div class="${dotClass}"></div>`);
    });
  }

  function clearMoveIndicators() {
    // Remove all move dots
    $('.move-dot, .capture-dot').remove();
    $('.square-selected').removeClass('square-selected');
    selectedSquare = null;
    possibleMoves = [];
  }

  // Click-to-move functionality
  function onSquareClick(square) {
    const piece = game.get(square);

    // If clicking on a piece of the current player
    if (piece &&
      ((game.turn() === 'w' && piece.color === 'w') ||
        (game.turn() === 'b' && piece.color === 'b'))) {
      // Select the piece and show moves
      selectedSquare = square;
      showPossibleMoves(square);
    }
    // If clicking on an empty square or opponent piece with a piece selected
    else if (selectedSquare && possibleMoves.length > 0) {
      // Check if this is a valid move
      const validMove = possibleMoves.find(move => move.to === square);
      if (validMove) {
        // Make the move
        makeMove(selectedSquare, square);
      } else {
        // Deselect if clicking on invalid square
        clearMoveIndicators();
      }
    }
    // If clicking on empty square without selection, deselect
    else if (!piece) {
      clearMoveIndicators();
    }
  }

  function makeMove(from, to) {
    const move = game.move({
      from: from,
      to: to,
      promotion: 'q'
    });

    if (move) {
      // Clear indicators and update board
      clearMoveIndicators();
      board.position(game.fen());

      // Make AI move
      makeAIMove();
    }
  }

  function makeAIMove() {
    $.ajax({
      url: '/api/move',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({
        fen: game.fen(),
        depth: getCurrentDepth()
      }),
      success: resp => {
        // apply the engine's move and redraw
        game.load(resp.fen);
        board.position(resp.fen);
        clearMoveIndicators(); // Clear any remaining indicators
      },
      error: () => {
        // if something went wrong, just snap back to the current FEN
        board.position(game.fen());
      }
    });
  }

  function onDrop(source, target) {
    // 1) Try the move locally
    const move = game.move({
      from: source,
      to: target,
      promotion: 'q'     // e.g. always queen for simplicity
    });

    // If illegal, revert immediately
    if (!move) return 'snapback';

    // 2) Clear move indicators and show the human move instantly
    clearMoveIndicators();
    board.position(game.fen());

    // 3) Make AI move
    makeAIMove();

    // no need to return anything — we’ve already updated the UI
  }
});