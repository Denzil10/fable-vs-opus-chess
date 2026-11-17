"""Claude Fable 5.2 vs Claude Opus 5.5: chess, no tools, no code.

Usage: python match.py <game name> <white model> <black model> <out dir>
  models: claude-fable-5-2 | claude-opus-5-5
Each turn the side to move gets the move list, the FEN and a text diagram (identical prompt for both).
Each call is `claude -p` with every tool disabled, a fresh session, no settings or MCP.
A reply that is not a legal move counts as a try; 3 misses on one move = that side forfeits.
python-chess is the referee. A game still running at move 150 is scored a draw (never reached = not used).
Every call and reply is logged to <out dir>/<game>.jsonl; the PGN to <game>.pgn.
"""
import json, re, subprocess, sys, time, pathlib, datetime
import chess, chess.pgn

game, white, black, out = sys.argv[1], sys.argv[2], sys.argv[3], pathlib.Path(sys.argv[4])
out.mkdir(parents=True, exist_ok=True)
LOG = open(out / f"{game}.jsonl", "a")
NAME = {"claude-fable-5-2": "FABLE 5.2", "claude-opus-5-5": "OPUS 5.5"}
COL = {"claude-fable-5-2": "\033[38;5;209m", "claude-opus-5-5": "\033[38;5;117m"}
B, R, D, X = "\033[1m", "\033[31m", "\033[2m", "\033[0m"


def system(side):
    return (f"You are playing a game of chess as {side} against another AI. You have no tools and no code. "
            "Reply in exactly two lines: line 1, a short comment on your move under 12 words; line 2, only your move in SAN.")


def log(**kw):
    kw["t"] = datetime.datetime.now().isoformat(timespec="seconds"); LOG.write(json.dumps(kw) + "\n"); LOG.flush()


def movelist(board):
    b = chess.Board(); parts = []
    for i, m in enumerate(board.move_stack):
        if i % 2 == 0: parts.append(f"{i // 2 + 1}.")
        parts.append(b.san(m)); b.push(m)
    return " ".join(parts) or "(none, game start)"


def ask(model, board, misses):
    side = "White" if board.turn == chess.WHITE else "Black"
    p = (f"Moves so far: {movelist(board)}\nPosition (FEN): {board.fen()}\n"
         f"Board (White at the bottom, uppercase = White):\n{board}\n")
    for m in misses:
        p += f"You tried {m}, which is not a legal move in this position.\n"
    p += f"You are {side}. Your move."
    t0 = time.time()
    r = subprocess.run(["claude", "-p", "--model", model, "--tools", "", "--no-session-persistence",
                        "--setting-sources", "", "--strict-mcp-config", "--output-format", "json",
                        "--system-prompt", system(side), p], capture_output=True, text=True, timeout=900)
    try:
        j = json.loads(r.stdout); text = j.get("result", ""); used = ",".join(j.get("modelUsage", {}).keys())
    except json.JSONDecodeError:
        text, used = r.stdout + r.stderr, "?"
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    comment = lines[0] if len(lines) > 1 else ""
    raw = lines[-1] if lines else ""
    san = re.sub(r"^\d+\.(\.\.)?\s*", "", raw).strip(" .*`")
    log(ply=board.ply(), side=side, model=model, prompt=p, reply=text, used=used, secs=round(time.time() - t0, 1))
    return comment, san, round(time.time() - t0, 1)


def show(board):
    rows = str(board.unicode(invert_color=True, empty_square="·")).splitlines()
    print()
    for i, row in enumerate(rows):
        print(f"   {D}{8 - i}{X}  " + " ".join(row.split()))
    print(f"      {D}a b c d e f g h{X}\n")


board = chess.Board(); illegal = {white: 0, black: 0}; result = None; forfeit = None
print(f"{B}{COL[white]}{NAME[white]}{X}{B} (White) vs {COL[black]}{NAME[black]}{X}{B} (Black){X}")
print(f"{D}no tools, no code, 3 illegal tries = forfeit{X}")
show(board)
while not board.is_game_over(claim_draw=True) and board.fullmove_number <= 150:
    n = board.fullmove_number
    model = white if board.turn == chess.WHITE else black
    dots = "." if board.turn == chess.WHITE else "..."
    misses = []
    while True:
        comment, san, secs = ask(model, board, misses)
        try:
            mv = board.parse_san(san); break
        except ValueError:
            illegal[model] += 1; misses.append(san)
            print(f" {R}{B}ILLEGAL{X}  {COL[model]}{NAME[model]}{X} {n}{dots} {san or '(no move)'}   {D}try {len(misses)}/3{X}")
            log(ply=board.ply(), model=model, illegal=san, tries=len(misses))
            if len(misses) == 3:
                forfeit = model; break
    if forfeit:
        result = "0-1" if forfeit == white else "1-0"
        print(f"\n {R}{B}THREE ILLEGAL MOVES. {NAME[forfeit]} FORFEITS.{X}"); break
    print(f" {COL[model]}{B}{NAME[model]}{X}  {n}{dots} {board.san(mv)}   {D}{secs}s{X}   \"{comment}\"")
    board.push(mv); log(ply=board.ply(), move=mv.uci(), fen=board.fen())
    if board.ply() % 2 == 0 or board.is_game_over(): show(board)
if result is None:
    result = board.result(claim_draw=True) if board.is_game_over(claim_draw=True) else "1/2-1/2"
outcome = board.outcome(claim_draw=True)
why = f"FORFEIT ({NAME[forfeit]}, 3 illegal moves)" if forfeit else (outcome.termination.name if outcome else "MOVE 150 CAP")
print(f"\n {B}RESULT {result}{X}  {why}   moves: {board.fullmove_number}   "
      f"illegal tries: {NAME[white]} {illegal[white]}, {NAME[black]} {illegal[black]}")
log(result=result, why=why, illegal=illegal, moves=board.fullmove_number)
pg = chess.pgn.Game.from_board(board)
pg.headers.update({"Event": "Claude Fable 5.2 vs Claude Opus 5.5 (no tools)", "White": NAME[white],
                   "Black": NAME[black], "Result": result})
(out / f"{game}.pgn").write_text(str(pg) + "\n")
