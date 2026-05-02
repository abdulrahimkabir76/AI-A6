import random
from typing import Dict, List, Optional, Set, Tuple

from flask import Flask, jsonify, render_template, request

# AIMA / aima-python logic tools.
# The code tries the packaged import first, then falls back to a local logic.py
# if the original aima-python repository is cloned next to this file.
import sys
import os

try:
	from aima3.logic import PropKB, expr, pl_resolution
	print("[DEBUG] Successfully imported from aima3.logic")
except ImportError as e:
	print(f"[DEBUG] Failed to import aima3.logic: {e}")
	try:
		# Try local import if aima-python is cloned locally
		sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
		from logic import PropKB, expr, pl_resolution
		print("[DEBUG] Successfully imported from local logic module")
	except ImportError as e2:
		print(f"[ERROR] Failed to import logic from both aima3 and local: {e}, {e2}")
		raise


app = Flask(__name__)


Cell = Tuple[int, int]


# One simple game state for the whole app.
GAME: Dict[str, object] = {}


def in_bounds(r: int, c: int, rows: int, cols: int) -> bool:
	return 1 <= r <= rows and 1 <= c <= cols


def neighbors(r: int, c: int, rows: int, cols: int) -> List[Cell]:
	possible = [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]
	return [(nr, nc) for nr, nc in possible if in_bounds(nr, nc, rows, cols)]


def cell_name(prefix: str, r: int, c: int) -> str:
	return f"{prefix}_{r}_{c}"


def create_world(rows: int, cols: int) -> Dict[str, object]:
	"""Randomly place pits and one Wumpus.

	The start cell [1,1] is kept safe so the agent can begin.
	"""
	all_cells = [(r, c) for r in range(1, rows + 1) for c in range(1, cols + 1)]
	available = [cell for cell in all_cells if cell != (1, 1)]

	# Keep the number of pits small enough for a demo assignment.
	pit_count = max(1, (rows * cols) // 5)
	pit_count = min(pit_count, max(0, len(available) - 1))

	pits: Set[Cell] = set(random.sample(available, pit_count)) if pit_count else set()
	remaining = [cell for cell in available if cell not in pits]
	wumpus: Optional[Cell] = random.choice(remaining) if remaining else None

	return {"rows": rows, "cols": cols, "pits": pits, "wumpus": wumpus}


def build_kb(rows: int, cols: int) -> PropKB:
	"""Create the knowledge base and add the local Breeze/Stench rules.

	These rules are the key AIMA sentences:
	- Bx,y <=> (pit in one of the adjacent cells)
	- Sx,y <=> (Wumpus in one of the adjacent cells)
	"""
	kb = PropKB()

	for r in range(1, rows + 1):
		for c in range(1, cols + 1):
			adj = neighbors(r, c, rows, cols)

			pit_terms = " | ".join(cell_name("P", nr, nc) for nr, nc in adj)
			stench_terms = " | ".join(cell_name("W", nr, nc) for nr, nc in adj)

			# If a cell has no neighbors, then no breeze / stench is possible.
			if pit_terms:
				kb.tell(expr(f"B_{r}_{c} <=> ({pit_terms})"))
			else:
				kb.tell(expr(f"~B_{r}_{c}"))

			if stench_terms:
				kb.tell(expr(f"S_{r}_{c} <=> ({stench_terms})"))
			else:
				kb.tell(expr(f"~S_{r}_{c}"))

	return kb


def sense(world: Dict[str, object], r: int, c: int) -> Dict[str, bool]:
	"""Return the current percepts at the agent's location."""
	rows = int(world["rows"])
	cols = int(world["cols"])
	pits: Set[Cell] = world["pits"]  # type: ignore[assignment]
	wumpus: Optional[Cell] = world["wumpus"]  # type: ignore[assignment]

	adj = neighbors(r, c, rows, cols)
	breeze = any(cell in pits for cell in adj)
	stench = wumpus in adj if wumpus else False
	return {"breeze": breeze, "stench": stench}


def tell_percepts(kb: PropKB, r: int, c: int, percepts: Dict[str, bool]) -> None:
	"""Tell the KB what the agent senses in the current cell."""
	if percepts["breeze"]:
		kb.tell(expr(f"B_{r}_{c}"))
	else:
		kb.tell(expr(f"~B_{r}_{c}"))

	if percepts["stench"]:
		kb.tell(expr(f"S_{r}_{c}"))
	else:
		kb.tell(expr(f"~S_{r}_{c}"))


def cell_is_safe(kb: PropKB, r: int, c: int, state: Dict[str, object]) -> bool:
	"""Ask the KB if a cell is safe using AIMA's pl_resolution.

	We prove the conjunction:
	(~P_r_c & ~W_r_c)
	"""
	state["inference_steps"] = int(state["inference_steps"]) + 1
	try:
		query = expr(f"(~P_{r}_{c} & ~W_{r}_{c})")
		result = pl_resolution(kb, query)
		print(f"[DEBUG] Query pl_resolution for cell [{r},{c}]: {result}")
		return result
	except Exception as e:
		print(f"[ERROR] pl_resolution failed for cell [{r},{c}]: {e}")
		return False


def mark_known_safe(state: Dict[str, object], cell: Cell) -> None:
	safe_cells: Set[Cell] = state["safe_cells"]  # type: ignore[assignment]
	safe_cells.add(cell)

{
  "version": 2,
  "builds": [
    {
      "src": "app.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "app.py"
    }
  ]
}
def agent_step() -> Dict[str, object]:
	"""Move the agent to one adjacent cell that AIMA can prove safe.

	If no adjacent safe cell is provable, the agent stops.
	"""
	if not GAME or "rows" not in GAME:
		print("[ERROR] GAME state not found or not initialized. GAME keys:", list(GAME.keys()))
		return {"ok": False, "message": "No active game. Start a new game first."}

	if GAME.get("game_over"):
		return make_public_state("Game already finished.")

	world = GAME["world"]  # type: ignore[assignment]
	kb = GAME["kb"]  # type: ignore[assignment]
	rows = int(GAME["rows"])
	cols = int(GAME["cols"])
	agent_r, agent_c = GAME["agent"]  # type: ignore[assignment]

	# 1) Sense at the current location and tell the KB.
	current_percepts = sense(world, agent_r, agent_c)
	GAME["percepts"] = current_percepts
	tell_percepts(kb, agent_r, agent_c, current_percepts)
	mark_known_safe(GAME, (agent_r, agent_c))

	# 2) Ask the KB which adjacent cells are provably safe.
	candidates = neighbors(agent_r, agent_c, rows, cols)
	visited: Set[Cell] = GAME["visited"]  # type: ignore[assignment]
	print(f"[DEBUG] Adjacent candidates from [{agent_r},{agent_c}]: {candidates}")

	# Prefer a new safe cell, but backtracking to an already safe cell is okay.
	proven_safe: List[Cell] = []
	for nr, nc in candidates:
		if cell_is_safe(kb, nr, nc, GAME):
			proven_safe.append((nr, nc))
			mark_known_safe(GAME, (nr, nc))

	print(f"[DEBUG] Proven safe cells: {proven_safe}")
	if not proven_safe:
		GAME["stopped"] = True
		GAME["message"] = "No adjacent cell can be proven safe, so the agent stops here."
		return make_public_state(GAME["message"])

	next_cell = None
	for cell in proven_safe:
		if cell not in visited:
			next_cell = cell
			break
	if next_cell is None:
		next_cell = proven_safe[0]

	# 3) Move the agent.
	GAME["agent"] = list(next_cell)
	visited.add(next_cell)

	# 4) Sense in the new location so the UI shows the active percepts.
	new_percepts = sense(world, next_cell[0], next_cell[1])
	GAME["percepts"] = new_percepts
	tell_percepts(kb, next_cell[0], next_cell[1], new_percepts)

	GAME["message"] = f"Moved to {list(next_cell)} after proving it safe with AIMA resolution."
	return make_public_state(GAME["message"])


def initialize_game(rows: int, cols: int) -> Dict[str, object]:
	world = create_world(rows, cols)
	kb = build_kb(rows, cols)

	GAME.clear()
	GAME.update(
		{
			"rows": rows,
			"cols": cols,
			"world": world,
			"kb": kb,
			"agent": [1, 1],
			"visited": {(1, 1)},
			"safe_cells": {(1, 1)},
			"percepts": {"breeze": False, "stench": False},
			"inference_steps": 0,
			"game_over": False,
			"stopped": False,
			"message": "Game initialized.",
		}
	)

	# The start square [1,1] is always safe in Wumpus World.
	kb.tell(expr("~P_1_1"))
	kb.tell(expr("~W_1_1"))

	# Sense the start square immediately.
	start_percepts = sense(world, 1, 1)
	GAME["percepts"] = start_percepts
	tell_percepts(kb, 1, 1, start_percepts)

	return make_public_state("New game started.")


def make_public_state(message: str = "") -> Dict[str, object]:
	"""Return a JSON-friendly snapshot of the current game."""
	if not GAME:
		return {"ok": False, "message": "No active game."}

	world = GAME["world"]  # type: ignore[assignment]
	pits: Set[Cell] = world["pits"]  # type: ignore[assignment]
	wumpus: Optional[Cell] = world["wumpus"]  # type: ignore[assignment]

	agent = GAME["agent"]
	visited = sorted(list(GAME["visited"]))  # type: ignore[assignment]
	safe_cells = sorted(list(GAME["safe_cells"]))  # type: ignore[assignment]
	percepts = GAME["percepts"]  # type: ignore[assignment]

	return {
		"ok": True,
		"rows": GAME["rows"],
		"cols": GAME["cols"],
		"agent": agent,
		"visited": visited,
		"safe_cells": safe_cells,
		"pits": sorted(list(pits)),
		"wumpus": list(wumpus) if wumpus else None,
		"percepts": percepts,
		"inference_steps": GAME["inference_steps"],
		"message": message or GAME.get("message", ""),
		"game_over": GAME.get("game_over", False),
		"stopped": GAME.get("stopped", False),
	}


@app.route("/")
def index() -> str:
	return render_template("index.html")


@app.route("/api/new_game", methods=["POST"])
def new_game():
	data = request.get_json(force=True)
	rows = max(2, int(data.get("rows", 4)))
	cols = max(2, int(data.get("cols", 4)))
	return jsonify(initialize_game(rows, cols))


@app.route("/api/step", methods=["POST"])
def step():
	return jsonify(agent_step())


@app.route("/api/state", methods=["GET"])
def state():
	if not GAME:
		return jsonify({"ok": False, "message": "No active game."})
	return jsonify(make_public_state())


if __name__ == "__main__":
	app.run(debug=True)
