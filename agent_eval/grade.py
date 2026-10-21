"""Grade answers to the agent tasks, or print/verify the reference solutions.

    python agent_eval/grade.py answers.json      # {"T01": 113101.3, "T02": 24.2, ...}
    python agent_eval/grade.py --reference       # run the reference solutions on the cached data
    python agent_eval/grade.py --tasks           # print the questions (what to give an agent)

An answer is right if it is within the task's relative tolerance of the oracle. The score is the
number of right answers; the output names the trap of each wrong answer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent


def load_tasks() -> list[dict[str, Any]]:
    data = yaml.safe_load((HERE / "tasks.yaml").read_text(encoding="utf-8"))
    tasks: list[dict[str, Any]] = data["tasks"]
    return tasks


def right(task: dict[str, Any], value: float) -> bool:
    oracle, tol = float(task["oracle"]), float(task["tol"])
    return abs(value - oracle) <= tol * abs(oracle)


def grade(answers: dict[str, float]) -> int:
    tasks = load_tasks()
    score = 0
    for t in tasks:
        got = answers.get(str(t["id"]))
        if got is not None and right(t, float(got)):
            score += 1
            print(f"{t['id']}  ok     {got}")
        else:
            print(f"{t['id']}  WRONG  got {got}, expected {t['oracle']} {t['unit']}; "
                  f"trap: {t['trap']}")
    print(f"score {score}/{len(tasks)}")
    return score


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "--tasks":
        for t in load_tasks():
            print(f"{t['id']} [NHTS {t['wave']}, answer in {t['unit']}] {t['question']}")
        return 0
    if argv[0] == "--reference":
        sys.path.insert(0, str(HERE))
        import reference

        import pynhts

        cache: dict[int, pynhts.NHTSData] = {}

        def load(wave: int) -> pynhts.NHTSData:
            if wave not in cache:
                cache[wave] = pynhts.load(wave, replicates=True)
            return cache[wave]

        answers = {k: f(load) for k, f in reference.REFERENCE.items()}
        return 0 if grade(answers) == len(answers) else 1
    raw = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    grade({k: float(v) for k, v in raw.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
