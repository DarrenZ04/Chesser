$(function () {
  const game = new Chess();
  const board = Chessboard('board', {
    draggable: true,
    position: 'start',
    pieceTheme: '/static/images/{piece}.png',
    onDrop
  });

  // First get a fresh starting position
  $.getJSON('/api/new_game', data => {
    game.load(data.fen);
    board.position(data.fen);
  });

  function onDrop(source, target) {
    // 1) Try the move locally
    const move = game.move({
      from: source,
      to: target,
      promotion: 'q'     // e.g. always queen for simplicity
    });

    // If illegal, revert immediately
    if (!move) return 'snapback';

    // 2) Show the human move instantly
    board.position(game.fen());

    // 3) Now ask your server for the AI’s move
    $.ajax({
      url: '/api/move',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({ fen: game.fen() }),
      success: resp => {
        // apply the engine’s move and redraw
        game.load(resp.fen);
        board.position(resp.fen);
      },
      error: () => {
        // if something went wrong, just snap back to the current FEN
        board.position(game.fen());
      }
    });

    // no need to return anything — we’ve already updated the UI
  }
});