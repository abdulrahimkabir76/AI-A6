const gridEl = document.getElementById('grid');
const rowsEl = document.getElementById('rows');
const colsEl = document.getElementById('cols');
const newGameBtn = document.getElementById('newGameBtn');
const stepBtn = document.getElementById('stepBtn');
const autoBtn = document.getElementById('autoBtn');
const stepsEl = document.getElementById('steps');
const locationEl = document.getElementById('location');
const perceptsEl = document.getElementById('percepts');
const statusEl = document.getElementById('status');

let currentState = null;
let autoTimer = null;

function cellKey(r, c) {
  return `${r},${c}`;
}

function makeSet(list) {
  return new Set((list || []).map(([r, c]) => cellKey(r, c)));
}

function buildGrid(rows, cols) {
  gridEl.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
  gridEl.innerHTML = '';

  for (let r = 1; r <= rows; r++) {
    for (let c = 1; c <= cols; c++) {
      const cell = document.createElement('div');
      cell.className = 'cell unknown';
      cell.id = `cell-${r}-${c}`;
      cell.innerHTML = `<span class="coord">[${r},${c}]</span><span class="content"></span>`;
      gridEl.appendChild(cell);
    }
  }
}

function render(state) {
  if (!state || !state.ok) {
    currentState = null;
    statusEl.textContent = state?.message || 'No state available.';
    stepBtn.disabled = true;
    autoBtn.disabled = true;
    return;
  }

  currentState = state;
  const rows = state.rows;
  const cols = state.cols;
  const visited = makeSet(state.visited);
  const safeCells = makeSet(state.safe_cells);
  const pits = makeSet(state.pits);
  const wumpus = state.wumpus ? cellKey(state.wumpus[0], state.wumpus[1]) : null;
  const agent = cellKey(state.agent[0], state.agent[1]);

  buildGrid(rows, cols);

  for (let r = 1; r <= rows; r++) {
    for (let c = 1; c <= cols; c++) {
      const key = cellKey(r, c);
      const el = document.getElementById(`cell-${r}-${c}`);
      const content = el.querySelector('.content');

      el.className = 'cell';

      if (key === agent) {
        el.classList.add('agent');
      }

      if (pits.has(key) || key === wumpus) {
        el.classList.add('hazard');
        content.textContent = pits.has(key) ? 'PIT' : 'WUMPUS';
      } else if (visited.has(key) || safeCells.has(key)) {
        el.classList.add('safe');
        content.textContent = visited.has(key) ? 'VISITED' : 'SAFE';
      } else {
        el.classList.add('unknown');
        content.textContent = '?';
      }

      if (key === agent) {
        content.textContent = `${content.textContent} \u25CF AGENT`;
      }
    }
  }

  stepsEl.textContent = state.inference_steps;
  locationEl.textContent = `[${state.agent[0]}, ${state.agent[1]}]`;
  perceptsEl.textContent = `Breeze: ${state.percepts.breeze}, Stench: ${state.percepts.stench}`;
  statusEl.textContent = state.message || '';

  stepBtn.disabled = state.game_over || state.stopped;
  autoBtn.disabled = state.game_over || state.stopped;
}

async function startGame() {
  stopAuto();
  const payload = {
    rows: Number(rowsEl.value),
    cols: Number(colsEl.value),
  };

  console.log('[DEBUG] Starting new game with payload:', payload);

  const res = await fetch('/api/new_game', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const state = await res.json();
  console.log('[DEBUG] /api/new_game response:', state);
  render(state);
  
  // Only enable buttons if the game started successfully
  if (state && state.ok) {
    console.log('[DEBUG] Game started successfully');
    stepBtn.disabled = false;
    autoBtn.disabled = false;
  } else {
    console.error('[ERROR] Game failed to start:', state?.message || 'Unknown error');
  }
}

async function stepGame() {
  if (!currentState) {
    console.error('[ERROR] No current state available');
    return;
  }

  console.log('[DEBUG] Stepping agent...');
  const res = await fetch('/api/step', { method: 'POST' });
  const state = await res.json();
  console.log('[DEBUG] /api/step response:', state);
  render(state);
}

function stopAuto() {
  if (autoTimer) {
    clearInterval(autoTimer);
    autoTimer = null;
    autoBtn.textContent = 'Auto Run';
  }
}

async function toggleAuto() {
  if (autoTimer) {
    stopAuto();
    return;
  }

  console.log('[DEBUG] Starting auto run...');
  autoBtn.textContent = 'Stop Auto';
  autoTimer = setInterval(async () => {
    if (!currentState || currentState.game_over || currentState.stopped) {
      console.log('[DEBUG] Auto run stopping. currentState:', currentState);
      stopAuto();
      return;
    }

    console.log('[DEBUG] Auto step iteration...');
    const res = await fetch('/api/step', { method: 'POST' });
    const state = await res.json();
    console.log('[DEBUG] Auto step response:', state);
    render(state);

    if (state.game_over || state.stopped) {
      console.log('[DEBUG] Agent stopped or game over. Stopping auto run.');
      stopAuto();
    }
  }, 700);
}

newGameBtn.addEventListener('click', startGame);
stepBtn.addEventListener('click', stepGame);
autoBtn.addEventListener('click', toggleAuto);

// Start with a default board so the page is immediately useful.
startGame();