"""Replay a finished match.py game on the referee screen, from its log, faster than it was played.
  python replay.py <game.jsonl> [seconds per ply, default 0.35]
Prints exactly what match.py printed live (same lines, the real think-time of each move), with a banner
saying it is a sped-up replay of the log. Recorded with vhs for the video.
"""
import json, sys, time
import chess

B, R, D, X = "\033[1m", "\033[31m", "\033[2m", "\033[0m"
NAME = {"claude-fable-5-2": "FABLE 5.2", "claude-opus-5-5": "OPUS 5.5"}
COL = {"claude-fable-5-2": "\033[38;5;209m", "claude-opus-5-5": "\033[38;5;117m"}
rows = [json.loads(l) for l in open(sys.argv[1])]
step = float(sys.argv[2]) if len(sys.argv) > 2 else 0.35
calls = [r for r in rows if "reply" in r]
white, black = calls[0]["model"], calls[1]["model"]


def show(board):
    print()
    for i, row in enumerate(str(board.unicode(invert_color=True, empty_square="·")).splitlines()):
        print(f"   {D}{8 - i}{X}  " + " ".join(row.split()))
    print(f"      {D}a b c d e f g h{X}\n")


print(f"{B}{COL[white]}{NAME[white]}{X}{B} (White) vs {COL[black]}{NAME[black]}{X}{B} (Black){X}")
print(f"{D}no tools, no code, 3 illegal tries = forfeit{X}")
print(f"{D}replay of the real game log, sped up{X}")
board = chess.Board(); show(board); time.sleep(1.0)
last = None; misses = 0
for r in rows:
    if "result" in r:  # checked first: the result row also has an "illegal" key
        ill = r["illegal"]
        print(f"\n {B}RESULT {r['result']}{X}  {r['why']}   moves: {r['moves']}   "
              f"illegal tries: {NAME[white]} {ill[white]}, {NAME[black]} {ill[black]}")
    elif "reply" in r:
        last = r
    elif "illegal" in r:
        misses = r["tries"]; n = board.fullmove_number; dots = "." if board.turn else "..."
        print(f" {R}{B}ILLEGAL{X}  {COL[r['model']]}{NAME[r['model']]}{X} {n}{dots} {r['illegal'] or '(no move)'}   {D}try {misses}/3{X}")
        time.sleep(step * 2)
    elif "move" in r:
        lines = [l.strip() for l in last["reply"].strip().splitlines() if l.strip()]
        comment = lines[0] if len(lines) > 1 else ""
        mv = chess.Move.from_uci(r["move"]); n = board.fullmove_number; dots = "." if board.turn else "..."
        print(f" {COL[last['model']]}{B}{NAME[last['model']]}{X}  {n}{dots} {board.san(mv)}   {D}{last['secs']}s{X}   \"{comment}\"")
        board.push(mv)
        if board.ply() % 2 == 0 or board.is_game_over():
            show(board)
        time.sleep(step)
time.sleep(4)
