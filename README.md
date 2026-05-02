# Web-based Dynamic Pathfinding Agent (Wumpus World)

A simple, educational knowledge-based agent that navigates a Wumpus World grid using **AIMA's propositional logic** and **automated resolution**. The agent learns about pit and wumpus locations through percepts (breeze and stench) and uses **pl_resolution** to deduce safe cells.

## Features

- **Dynamic Grid**: User-defined grid dimensions (rows × columns).
- **Randomized Hazards**: Pits and one Wumpus placed randomly at startup; agent starts at [1,1].
- **Propositional Logic KB**: AIMA's `PropKB` with biconditional rules linking percepts to adjacent hazards.
- **Automated Resolution**: Uses AIMA's `pl_resolution` to prove cell safety before movement.
- **Real-Time Metrics**: Displays inference step count and active percepts at the agent's location.
- **Visual Grid**: Color-coded cells (green = safe, gray = unknown, red = hazard).
- **Auto-Step Mode**: Watch the agent solve the maze automatically.

## Tech Stack

- **Backend**: Flask + Python
- **AI Logic**: AIMA (aima-python) – specifically `PropKB`, `expr`, and `pl_resolution`
- **Frontend**: Vanilla HTML, CSS (CSS Grid), and JavaScript
- **Deployment**: Vercel (Python runtime)

## Project Structure

```
.
├── app.py                 # Flask backend with AIMA integration
├── requirements.txt       # Python dependencies (for Vercel)
├── templates/
│   └── index.html        # Main HTML page
├── static/
│   └── script.js         # Frontend logic and rendering
├── aima/                 # AIMA library files (included locally)
└── README.md             # This file
```

## Installation & Setup

### Local Development

1. **Clone or navigate to** this project folder.

2. **Ensure AIMA files are present**: The local `aima/` folder should contain the AIMA library files (no need to install via pip since you already have them).

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   
   This installs Flask and other required packages for your local environment.

4. **Start the Flask server**:
   ```bash
   python app.py
   ```

5. **Open your browser** and navigate to:
   ```
   http://localhost:5000
   ```

### Vercel Deployment

- The `requirements.txt` file includes all necessary dependencies for deployment on Vercel.
- AIMA files are included locally in the project, so they will be deployed with the application.
- No additional configuration needed beyond pushing to your repository.

## How to Use

1. **Set grid size** (rows & columns) using the input fields.
2. Click **"Start / Reset"** to initialize a new game with random pit and wumpus placement.
3. Use the control buttons:
   - **Step**: Move the agent one cell (if a safe cell can be proven).
   - **Auto Run**: Automatically step through the solution.
   - **Stop Auto**: Halt the automatic stepping.
4. Watch the grid update with:
   - **Green cells**: Safe cells that the agent has proven through logical inference.
   - **Gray cells**: Unknown/unvisited cells.
   - **Red cells**: Confirmed pits and wumpus locations.

## How It Works

### Knowledge Base Construction

When the game starts:
1. The KB is populated with rules linking breeze/stench to adjacent pits/wumpus.
   - Example: `B_2_2 <=> (P_1_2 | P_3_2 | P_2_1 | P_2_3)`
2. The start cell [1,1] is asserted as safe (`~P_1_1` and `~W_1_1`).

### Agent Logic (Per Step)

1. **Sense**: The agent reads percepts (breeze & stench) at its current location.
2. **Tell**: Percept facts are added to the KB.
3. **Ask & Prove**: For each adjacent cell, the agent queries the KB:
   - Query: `(~P_x_y & ~W_x_y)` – "Is cell (x,y) provably safe?"
   - Method: AIMA's `pl_resolution` performs refutation-based automated theorem proving.
4. **Move**: If a safe cell is proven, the agent moves there. Otherwise, it stops.

### Inference Metrics

- **Inference Steps**: Incremented each time `pl_resolution` is called (each query).
- **Current Location**: Shows the agent's current position in the grid.
- **Active Percepts**: The current breeze & stench status at the agent's location.
- **Status Message**: Provides feedback on the agent's actions and decisions.

## Key AIMA Components Used

- **`PropKB()`**: Propositional Knowledge Base for storing logical sentences.
- **`expr()`**: Parser to convert string expressions into AIMA symbol objects.
- **`pl_resolution(kb, query)`**: Automated refutation-based theorem prover. Returns `True` if the query is entailed by the KB, `False` otherwise.

### Example Logic Sentence

When the agent is at cell [2,2] and senses a breeze:
- The KB learns: `B_2_2 = True`
- The KB also has the rule: `B_2_2 <=> (P_1_2 | P_3_2 | P_2_1 | P_2_3)`
- This means at least one adjacent cell has a pit.
- To query if cell [1,2] is safe, the agent asks: `pl_resolution(kb, (~P_1_2 & ~W_1_2))`
- If this returns `False`, the agent cannot prove cell [1,2] is safe, so it won't move there.

## Troubleshooting

- **"No active game" message**: Click "Start / Reset" to initialize the game.
- **Step/Auto Run buttons not working**: Ensure a game has been successfully started (status should show "New game started.").
- **AIMA import errors**: Verify that the AIMA library files are in the correct location or installed via pip.

## Educational Notes

This project demonstrates:
- **Knowledge representation** in propositional logic.
- **Automated reasoning** via resolution-based theorem proving.
- **Agent perception** and **dynamic belief update**.
- **Planning under uncertainty** with partial information.
- Integration of a **symbolic AI library** (AIMA) with a **web interface**.
- **Web-based deployment** of AI reasoning systems.

Perfect for an AI course assignment on knowledge-based agents and logical inference!

## License

Educational use only. Built for learning purposes.
