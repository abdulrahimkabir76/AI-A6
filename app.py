import random
from typing import Dict, List, Optional, Set, Tuple

from flask import Flask, jsonify, render_template, request
import sys
import os
import json
from pathlib import Path

# AIMA / aima-python logic tools. Try packaged import first, then local fallback.
try:
	from aima3.logic import PropKB, expr, pl_resolution
	print("[DEBUG] Successfully imported from aima3.logic")
except ImportError as e:
	print(f"[DEBUG] Failed to import aima3.logic: {e}")
	try:
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
STATE_FILE = Path(__file__).parent / "game_state.json"


def save_game():
	"""Serialize GAME to disk (JSON-friendly)."""
	if not GAME:
		return

	data = dict(GAME)

	# Convert non-serializable types
	if "visited" in data:
		data["visited"] = list(map(list, list(data["visited"])))
	if "safe_cells" in data:
		data["safe_cells"] = list(map(list, list(data["safe_cells"])))
	if "world" in data:
		world = dict(data["world"])
		world["pits"] = list(map(list, list(world.get("pits", []))))
		world["wumpus"] = list(world["wumpus"]) if world.get("wumpus") else None
		data["world"] = world

	# KB sentences list should already be strings
	try:
		with open(STATE_FILE, "w") as f:
			json.dump(data, f)
		print(f"[DEBUG] Game state saved to {STATE_FILE}")
	except Exception as e:
		print(f"[ERROR] Failed to save game state: {e}")


def load_game():
	"""Load GAME from disk back into memory, converting types."""
	if not STATE_FILE.exists():
		return
	try:
		with open(STATE_FILE, "r") as f:
			data = json.load(f)
	except Exception as e:
		print(f"[ERROR] Failed to load game state: {e}")
		return

	GAME.clear()
	GAME.update(data)

	# Convert lists back to sets/tuples where needed
	if "visited" in GAME:
		GAME["visited"] = set(tuple(x) for x in GAME["visited"])
	if "safe_cells" in GAME:
		GAME["safe_cells"] = set(tuple(x) for x in GAME["safe_cells"])
	if "world" in GAME:
		pits = set(tuple(x) for x in GAME["world"].get("pits", []))
		GAME["world"]["pits"] = pits
		GAME["world"]["wumpus"] = tuple(GAME["world"]["wumpus"]) if GAME["world"].get("wumpus") else None

	print(f"[DEBUG] Game state loaded from {STATE_FILE}")


def apply_state_dict(data: Dict[str, object]) -> None:
	"""Load a provided state dict into GAME (used when client supplies state).

	Expects the same structure as make_public_state output, but also accepts
	internal keys like kb_sentences and inference_steps.
	"""
	GAME.clear()
	# Basic copy
	GAME.update(data)

	# Convert lists to proper internal types
	if "visited" in GAME:
		GAME["visited"] = set(tuple(x) for x in GAME["visited"]) if isinstance(GAME["visited"], list) else set()
	if "safe_cells" in GAME:
		GAME["safe_cells"] = set(tuple(x) for x in GAME["safe_cells"]) if isinstance(GAME["safe_cells"], list) else set()
	if "world" in GAME:
		w = GAME["world"]
		if isinstance(w.get("pits"), list):
			GAME["world"]["pits"] = set(tuple(x) for x in w.get("pits", []))
		if w.get("wumpus"):
			GAME["world"]["wumpus"] = tuple(w["wumpus"]) if isinstance(w["wumpus"], list) else w["wumpus"]

	# Ensure kb_sentences list exists
	if "kb_sentences" not in GAME:
		GAME["kb_sentences"] = []

	print("[DEBUG] Applied state from client into GAME keys:", list(GAME.keys()))


def get_kb_from_game() -> PropKB:
	"""Build a fresh PropKB from stored KB sentence strings in GAME."""
	kb = PropKB()
	sentences = GAME.get("kb_sentences", [])
	for s in sentences:
		try:
			kb.tell(expr(s))
		except Exception as e:
			print(f"[ERROR] Failed to tell KB sentence '{s}': {e}")
	return kb


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


def build_kb(rows: int, cols: int) -> List[str]:
	"""Return a list of KB sentence strings (rules linking percepts and hazards)."""
	sentences: List[str] = []

	for r in range(1, rows + 1):
		for c in range(1, cols + 1):
			adj = neighbors(r, c, rows, cols)

			pit_terms = " | ".join(cell_name("P", nr, nc) for nr, nc in adj)
			stench_terms = " | ".join(cell_name("W", nr, nc) for nr, nc in adj)

			# If a cell has no neighbors, then no breeze / stench is possible.
			if pit_terms:
				sentences.append(f"B_{r}_{c} <=> ({pit_terms})")
			else:
				sentences.append(f"~B_{r}_{c}")

			if stench_terms:
				sentences.append(f"S_{r}_{c} <=> ({stench_terms})")
			else:
				sentences.append(f"~S_{r}_{c}")

	# Return list; caller will store and reconstruct PropKB when needed
	return sentences


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
	# Persist sentences so KB can be reconstructed across requests
	s_b = f"B_{r}_{c}" if percepts["breeze"] else f"~B_{r}_{c}"
	s_s = f"S_{r}_{c}" if percepts["stench"] else f"~S_{r}_{c}"

	try:
		kb.tell(expr(s_b))
	except Exception as e:
		print(f"[ERROR] tell_percepts: failed to tell '{s_b}': {e}")
	try:
		kb.tell(expr(s_s))
	except Exception as e:
		print(f"[ERROR] tell_percepts: failed to tell '{s_s}': {e}")

	if "kb_sentences" not in GAME:
		GAME["kb_sentences"] = []
	if s_b not in GAME["kb_sentences"]:
		GAME["kb_sentences"].append(s_b)
	if s_s not in GAME["kb_sentences"]:
		GAME["kb_sentences"].append(s_s)

	save_game()


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
	kb = get_kb_from_game()
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
	kb_sentences = build_kb(rows, cols)

	GAME.clear()
	GAME.update(
		{
			"rows": rows,
			"cols": cols,
			"world": world,
			"kb_sentences": kb_sentences,
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

	# Build KB and assert the start cell safety
	kb = get_kb_from_game()
	for s in ("~P_1_1", "~W_1_1"):
		if s not in GAME["kb_sentences"]:
			GAME["kb_sentences"].append(s)
			try:
				kb.tell(expr(s))
			except Exception as e:
				print(f"[ERROR] initialize_game: failed to tell '{s}': {e}")

	# Sense the start square immediately and persist percepts
	start_percepts = sense(world, 1, 1)
	GAME["percepts"] = start_percepts
	tell_percepts(kb, 1, 1, start_percepts)

	save_game()
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
	state = initialize_game(rows, cols)
	# ensure it's saved
	save_game()
	return jsonify(state)


@app.route("/api/step", methods=["POST"])
def step():
	# Accept optional client-supplied state to avoid relying on server disk persistence
	data = request.get_json(silent=True)
	if data and "state" in data:
		apply_state_dict(data["state"])
	else:
		load_game()

	result = agent_step()
	# Return the updated public state
	return jsonify(result)


@app.route("/api/state", methods=["GET"])
def state():
	load_game()
	if not GAME:
		return jsonify({"ok": False, "message": "No active game."})
	return jsonify(make_public_state())


if __name__ == "__main__":
	app.run(debug=True)
