"""Sudoku experiment: difficulty curve + judge ablation.

Question: does publishing constraint facts actually help a fuzzy judge, and where does
constraint reasoning alone stop being enough?

Two solution-blind judges over the same puzzles:

* ``local``    — naked/hidden single from the published candidates (the shipped judge);
* ``random``   — uniform pick among the same published candidates (seeded, deterministic),
                 i.e. a judge that ignores the semantics of the facts it is given.

Grid: holes in {40, 45, 50, 55} x 10 episodes each.  Metrics: win rate, mean correct
fills, mean mistakes.

Run:  python3 experiment.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sudoku_game as S
from jev_sudoku import run_episode

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
HOLES = (40, 45, 50, 55)
EPISODES = 10


def random_judge_factory():
    """Uniform pick among published candidates; deterministic overall."""
    rng = random.Random(20260922)

    def judge(request: dict) -> dict:
        cands = list(request['candidates'])
        tried = set(request.get('wrong_digits', {}).get(
            f"{request['cell'][0]},{request['cell'][1]}", []))
        survivors = [c for c in cands if c not in tried] or cands
        return {'digit': str(rng.choice(survivors)) if survivors else '1'}

    return judge


def local_judge(request: dict) -> dict:
    row, col = request['cell']
    cands = list(request['candidates'])

    def unit_cells():
        box_r, box_c = 3 * (row // 3), 3 * (col // 3)
        return (
            [(row, c) for c in range(9)],
            [(r, col) for r in range(9)],
            [(r, c) for r in range(box_r, box_r + 3) for c in range(box_c, box_c + 3)],
        )

    # hidden single: a candidate that fits no other empty cell in its row/column/box
    for digit in cands:
        for unit in unit_cells():
            others = [cell for cell in unit if cell != (row, col)]
            if all(
                digit not in S._candidates(request['_grid'], r, c) for r, c in others
            ):
                return {'digit': str(digit)}
    # guess fallback: never repeat a digit already proven wrong at this cell
    tried = set(request.get('wrong_digits', {}).get(f'{row},{col}', []))
    survivors = [c for c in cands if c not in tried] or cands
    return {'digit': str(survivors[0])}


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    judges = {
        'local_constraint': local_judge,
        'random_candidate': random_judge_factory(),
    }
    report = {'holes_grid': list(HOLES), 'episodes_per_cell': EPISODES, 'cells': {}}

    # judges: (name, judge_fn, trial_memory_flag)
    arms = [
        ("local_constraint", local_judge, False),
        ("local_constraint + trial_memory", local_judge, True),
        ('random_candidate', judges['random_candidate'], False),
        ('random_candidate + trial_memory', judges['random_candidate'], True),
    ]
    print(f"{'holes':>6} {'arm':<34} {'win':>5} {'mean fill':>10} {'mean mistakes':>14}")
    for holes in HOLES:
        for name, judge, memory in arms:
            results = [
                run_episode(seed=1000 + holes * 10 + i, holes=holes, judge=judge,
                            trial_memory=memory)
                for i in range(EPISODES)
            ]
            wins = sum(1 for r in results if r['outcome'] == 'win')
            mean_fill = sum(r['score'] for r in results) / len(results)
            mean_mist = sum(r['mistakes'] for r in results) / len(results)
            report['cells'][f'{holes}_{name}'] = {
                'holes': holes, 'judge': name, 'wins': wins,
                'mean_fill': round(mean_fill, 1), 'mean_mistakes': round(mean_mist, 2),
            }
            print(f"{holes:>6} {name:<34} {wins:>3}/{EPISODES} {mean_fill:>9.1f} {mean_mist:>13.2f}")

    (ARTIFACTS / 'experiment_difficulty.json').write_text(
        json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nwrote {ARTIFACTS / 'experiment_difficulty.json'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
