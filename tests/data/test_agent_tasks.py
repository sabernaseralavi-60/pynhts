"""The agent tasks must stay valid: the reference solutions reproduce the stored oracles."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pytest

import pynhts
from pynhts.core.flags import PynhtsWarning

ROOT = Path(__file__).resolve().parents[2] / "agent_eval"
sys.path.insert(0, str(ROOT))
import grade  # noqa: E402
import reference  # noqa: E402

pytestmark = pytest.mark.data
TASKS = {t["id"]: t for t in grade.load_tasks()}
_CACHE: dict[int, pynhts.NHTSData] = {}


def _load(wave: int) -> pynhts.NHTSData:
    if wave not in _CACHE:
        _CACHE[wave] = pynhts.load(wave, offline=True, replicates=True)
    return _CACHE[wave]


def test_every_task_has_a_reference_and_the_documented_fields():
    assert set(TASKS) == set(reference.REFERENCE)
    for t in TASKS.values():
        assert {"question", "oracle", "tol", "trap", "naive", "source", "unit", "wave"} <= set(t)
        assert not grade.right(t, float(t["naive"])), t["id"]  # the careless answer is wrong


@pytest.mark.parametrize("task_id", sorted(TASKS))
def test_reference_solution_reproduces_the_oracle(task_id):
    with warnings.catch_warnings():
        warnings.simplefilter("error", PynhtsWarning)  # no guard may fire in a correct solution
        value = reference.REFERENCE[task_id](_load)
    assert grade.right(TASKS[task_id], value), (task_id, value, TASKS[task_id]["oracle"])


def test_grader_scores_a_perfect_and_a_careless_answer_sheet():
    perfect = {k: float(t["oracle"]) for k, t in TASKS.items()}
    careless = {k: float(t["naive"]) for k, t in TASKS.items()}
    assert grade.grade(perfect) == len(TASKS)
    assert grade.grade(careless) == 0
