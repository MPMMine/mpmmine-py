import re

import pytest

from mpmmine.dataset import MPMMine, Problem, Description, Instance, Solution


# Initialization tests

def test_init_mpmmine(mpmmine: MPMMine):
    assert mpmmine is not None


def test_dataset_version(mpmmine: MPMMine):
    pattern = re.compile(r"\d+.\d+.\d+.20\d\d[0-1]\d[0-3]\d")
    assert pattern.fullmatch(mpmmine.dataset_version)


def test_library_version(mpmmine: MPMMine):
    pattern = re.compile(r"\d+.\d+.\d+.20\d\d[0-1]\d[0-3]\d")
    print(mpmmine.library_version)
    assert pattern.fullmatch(mpmmine.library_version)

# Problem layer tests

def test_MPMMine_problems(mpmmine: MPMMine):
    assert len(mpmmine.problems) >= 16  # as of 2026-07-14
    for i, problem in enumerate(mpmmine.problems, start=1):
        assert problem.id == f"P{i:03d}"


def test_MPMMine_get_problem(mpmmine: MPMMine):
    for id in range(1, 17):
        problem = mpmmine.get_problem(f"P{id:03d}")
        assert problem.id == f"P{id:03d}"
        assert problem.full_id == f"MPMMine-P{id:03d}"

        with pytest.raises(ValueError):
            problem = mpmmine.get_problem(f"MPMMine-P{id:03d}")
            assert problem.id == f"P{id:03d}"
            assert problem.full_id == f"MPMMine-P{id:03d}"
            assert len(problem.name) >= 8
            assert "constraints" in problem.features
            assert "objective" in problem.features
            assert "variables" in problem.features
            assert "optimization" in problem.features
            assert "satisfiability" in problem.features


def test_MPMMine_get_problem_by_invalid_id_raises_value_error(mpmmine: MPMMine):
    for id in range(1, 17):
        with pytest.raises(ValueError):
            mpmmine.get_problem(f"MPMMine-P{id:03d}")

        with pytest.raises(ValueError):
            mpmmine.get_problem(f"M{id:03d}")


def test_MPMMine_get_problem_raises_file_not_found_error(mpmmine: MPMMine):
    with pytest.raises(FileNotFoundError, match="Problem P999 does not exist"):
        mpmmine.get_problem("P999")


def test_MPMMine_get_by_full_id_invalid_raises_value_error(mpmmine: MPMMine):
    invalid_ids = ["", "MPMMine", "MPMMine-", "MPMMine-P", "MPMMine-P9999", "MPMMine-P001M", "MPMMine-P001M0",
                   "MPMMine-P001M0001", "MPMMine-P001I001", "MPMMine-P001D001", "MPMMine-M001P001"]
    for id in invalid_ids:
        with pytest.raises(ValueError):
            item = mpmmine[id]


def test_MPMMine_get_by_full_id_problems(mpmmine: MPMMine):
    for id in range(1, 17):
        problem: Problem = mpmmine[f"P{id:03d}"]
        assert problem.id == f"P{id:03d}"
        assert problem.full_id == f"MPMMine-P{id:03d}"
        assert len(problem.name) >= 8
        assert "constraints" in problem.features
        assert "objective" in problem.features
        assert "variables" in problem.features
        assert "optimization" in problem.features
        assert "satisfiability" in problem.features

        problem: Problem = mpmmine[f"MPMMine-P{id:03d}"]
        assert problem.id == f"P{id:03d}"
        assert problem.full_id == f"MPMMine-P{id:03d}"
        assert len(problem.name) >= 8
        assert "constraints" in problem.features
        assert "objective" in problem.features
        assert "variables" in problem.features
        assert "optimization" in problem.features
        assert "satisfiability" in problem.features


def test_MPMMine_get_by_full_id_problems_raises_not_found_error(mpmmine: MPMMine):
    with pytest.raises(FileNotFoundError, match="Problem P999 does not exist"):
        problem = mpmmine[f"P999"]

    with pytest.raises(FileNotFoundError, match="Problem P999 does not exist"):
        problem = mpmmine[f"MPMMine-P999"]


# Model layer tests

def test_Problem_models(mpmmine: MPMMine):
    for problem in mpmmine.problems:
        assert len(problem.models) > 0
        for i, model in enumerate(problem.models, start=1):
            assert model.id == f"M{i:03d}"
            assert model.full_id == f"MPMMine-{problem.id}M{i:03d}"
            assert len(model.mzn) > 50


def test_Problem_get_model(mpmmine: MPMMine):
    P001M001 = mpmmine.get_problem("P001").get_model("M001")
    assert P001M001.id == "M001"
    assert P001M001.full_id == "MPMMine-P001M001"
    assert len(P001M001.mzn) > 50

    P015M002 = mpmmine.get_problem("P015").get_model("M002")
    assert P015M002.id == "M002"
    assert P015M002.full_id == "MPMMine-P015M002"
    assert len(P015M002.mzn) > 50


def test_Problem_get_model_raises_file_not_found_error(mpmmine: MPMMine):
    with pytest.raises(FileNotFoundError, match="Model M999 does not exist"):
        mpmmine.get_problem("P001").get_model("M999")


def test_MPMMine_get_by_full_id_models(mpmmine: MPMMine):
    for id in range(1, 17):
        model = mpmmine[f"P{id:03d}M001"]
        assert model.id == f"M001"
        assert model.full_id == f"MPMMine-P{id:03d}M001"

        model = mpmmine[f"MPMMine-P{id:03d}M001"]
        assert model.id == f"M001"
        assert model.full_id == f"MPMMine-P{id:03d}M001"


def test_MPMMine_get_by_full_id_models_raises_not_found_error(mpmmine: MPMMine):
    with pytest.raises(FileNotFoundError, match="Model M999 does not exist"):
        model = mpmmine[f"P001M999"]

    with pytest.raises(FileNotFoundError, match="Model M987 does not exist"):
        model = mpmmine[f"MPMMine-P002M987"]

    with pytest.raises(FileNotFoundError, match="Model M900 does not exist"):
        model = mpmmine[f"MPMMine-P002M900I001"]


# Problem instance layer tests

def test_Model_instances(mpmmine: MPMMine):
    for problem in mpmmine.problems:
        for model in problem.models:
            assert len(model.instances) > 0
            for i, instance in enumerate(model.instances, start=1):
                assert instance.id == f"I{i:03d}"


def test_Model_get_instance_by_id(mpmmine: MPMMine):
    model = mpmmine[f"P003M002"]
    for i in range(1, 9):
        instance = model.get_instance(f"I{i:03d}")
        assert instance.id == f"I{i:03d}"
        assert instance.full_id == f"MPMMine-P003M002I{i:03d}"
        assert len(instance.dzn) > 50


def test_Model_get_instance_raises_file_not_found_error(mpmmine: MPMMine):
    with pytest.raises(FileNotFoundError, match="Instance I999 does not exist"):
        mpmmine["P001M001"].get_instance("I999")


def test_MPMMine_get_by_full_id_instances(mpmmine: MPMMine):
    for id in range(1, 17):
        instance = mpmmine[f"P{id:03d}M001I001"]
        assert instance.id == f"I001"
        assert instance.full_id == f"MPMMine-P{id:03d}M001I001"
        assert len(instance.dzn) >= 4

        instance = mpmmine[f"MPMMine-P{id:03d}M001I001"]
        assert instance.id == f"I001"
        assert instance.full_id == f"MPMMine-P{id:03d}M001I001"
        assert len(instance.dzn) >= 4


def test_MPMMine_get_by_full_id_instances_raises_not_found_error(mpmmine: MPMMine):
    with pytest.raises(FileNotFoundError, match="Instance I999 does not exist"):
        problem = mpmmine[f"P001M001I999"]

    with pytest.raises(FileNotFoundError, match="Instance I987 does not exist"):
        problem = mpmmine[f"MPMMine-P002M001I987"]


# Description layer tests

def test_Model_descriptions(mpmmine: MPMMine):
    for problem in mpmmine.problems:
        for model in problem.models:
            assert len(model.descriptions) > 0
            for i, description in enumerate(model.descriptions, start=1):
                assert description.id == f"D{i:03d}"
                assert description.full_id == f"{model.full_id}D{i:03d}"
                assert len(description.markdown) > 50


def test_Model_get_description_by_id(mpmmine: MPMMine):
    model = mpmmine[f"P003M002"]
    for i in range(1, 20):
        description = model.get_description(f"D{i:03d}")
        assert description.id == f"D{i:03d}"
        assert description.full_id == f"MPMMine-P003M002D{i:03d}"
        assert len(description.markdown) > 50


def test_Model_get_description_raises_file_not_found_error(mpmmine: MPMMine):
    with pytest.raises(FileNotFoundError, match="Description D999 does not exist"):
        mpmmine["P001M001"].get_description("D999")


def test_MPMMine_get_by_full_id_descriptions(mpmmine: MPMMine):
    for id in range(1, 17):
        description = mpmmine[f"P{id:03d}M001D001"]
        assert description.id == f"D001"
        assert description.full_id == f"MPMMine-P{id:03d}M001D001"
        assert len(description.markdown) >= 50

        description = mpmmine[f"MPMMine-P{id:03d}M001D001"]
        assert description.id == f"D001"
        assert description.full_id == f"MPMMine-P{id:03d}M001D001"
        assert len(description.markdown) >= 50


def test_MPMMine_get_by_full_id_descriptions_raises_not_found_error(mpmmine: MPMMine):
    with pytest.raises(FileNotFoundError, match="Description D999 does not exist"):
        description = mpmmine[f"P001M001D999"]

    with pytest.raises(FileNotFoundError, match="Description D987 does not exist"):
        description = mpmmine[f"MPMMine-P002M001D987"]


# Instance description layer

def test_Instance_descriptions(mpmmine: MPMMine):
    instance: Instance = mpmmine[f"P003M002I001"]
    assert len(instance.descriptions) > 0
    for i, description in enumerate(instance.descriptions, start=1):
        assert description.id == f"D{i:03d}"
        assert description.full_id == f"{instance.full_id}D{i:03d}"
        assert len(description.markdown) > 50


def test_Instance_get_description_by_id(mpmmine: MPMMine):
    instance = mpmmine[f"P002M001I002"]
    for i in range(1, 2):
        description: Description = instance.get_description(f"D{i:03d}")
        assert description.id == f"D{i:03d}"
        assert description.full_id == f"MPMMine-P002M001I002D{i:03d}"
        assert len(description.markdown) > 50


def test_Instance_get_description_raises_file_not_found_error(mpmmine: MPMMine):
    with pytest.raises(FileNotFoundError, match="Description D999 does not exist"):
        mpmmine["P001M001I001"].get_description("D999")


def test_MPMMine_get_by_full_id_instance_descriptions(mpmmine: MPMMine):
    description = mpmmine[f"P002M001I002D001"]
    assert description.id == f"D001"
    assert description.full_id == f"MPMMine-P002M001I002D001"
    assert len(description.markdown) >= 50


def test_MPMMine_get_by_full_id_instance_description_raises_not_found_error(mpmmine: MPMMine):
    with pytest.raises(FileNotFoundError, match="Description D999 does not exist"):
        description = mpmmine[f"P002M001I002D999"]

    with pytest.raises(FileNotFoundError, match="Description D987 does not exist"):
        description = mpmmine[f"MPMMine-P002M001I002D987"]


# Solution layer

def test_Instance_solutions(mpmmine: MPMMine):
    exists_for_sure = {"MPMMine-P001M001I001", "MPMMine-P001M001I002", "MPMMine-P001M001I003", "MPMMine-P002M002I001",
                       "MPMMine-P002M001I002"}
    not_exists_for_sure = {"MPMMine-P002M001I003", "MPMMine-P002M001I004", "MPMMine-P002M001I005",
                           "MPMMine-P002M001I007"}

    for problem in mpmmine.problems:
        for model in problem.models:
            for instance in model.instances:
                solutions = instance.solutions

                if instance.full_id in exists_for_sure:
                    assert len(solutions) in range(1, 10001)
                elif instance.full_id in not_exists_for_sure:
                    assert len(solutions) == 0
                else:
                    assert len(solutions) <= 10000

                for i, solution in enumerate(solutions, start=1):
                    assert solution.id == f"S{i:05d}"
                    assert solution.full_id == f"{instance.full_id}S{i:05d}"
                    assert solution.cls
                    assert len(solution.dzn) >= 17


def test_Instance_get_solution_by_id(mpmmine: MPMMine):
    instance = mpmmine[f"P004M002I002"]
    for i in range(1, 2049):
        solution: Solution = instance.get_solution(f"S{i:05d}")
        assert solution.id == f"S{i:05d}"
        assert solution.full_id == f"MPMMine-P004M002I002S{i:05d}"
        assert solution.cls
        assert len(solution.dzn) >= 17


def test_Instance_get_solution_raises_file_not_found_error(mpmmine: MPMMine):
    with pytest.raises(FileNotFoundError, match="Solution S99999 does not exist"):
        mpmmine["P001M001I001"].get_solution("S99999")


def test_MPMMine_get_by_full_id_solution(mpmmine: MPMMine):
    solution: Solution = mpmmine[f"P002M001I002S01234"]
    assert solution.id == f"S01234"
    assert solution.full_id == f"MPMMine-P002M001I002S01234"
    assert len(solution.dzn) >= 50


def test_MPMMine_get_by_full_id_solution_raises_not_found_error(mpmmine: MPMMine):
    with pytest.raises(FileNotFoundError, match="Solution S99999 does not exist"):
        solution = mpmmine[f"P002M001I002S99999"]

    with pytest.raises(FileNotFoundError, match="Solution S98765 does not exist"):
        solution = mpmmine[f"MPMMine-P002M001I002S98765"]


# Non-solution layer

def test_Instance_non_solutions(mpmmine: MPMMine):
    exists_for_sure = {"MPMMine-P001M001I001", "MPMMine-P001M001I002", "MPMMine-P001M001I003", "MPMMine-P002M002I001",
                       "MPMMine-P002M001I002"}
    not_exists_for_sure = {"MPMMine-P002M001I003", "MPMMine-P002M001I004", "MPMMine-P002M001I005",
                           "MPMMine-P002M001I007"}

    for problem in mpmmine.problems:
        for model in problem.models:
            for instance in model.instances:
                non_solutions = instance.non_solutions

                if instance.full_id in exists_for_sure:
                    assert len(non_solutions) in range(1, 10001)
                elif instance.full_id in not_exists_for_sure:
                    assert len(non_solutions) == 0
                else:
                    assert len(non_solutions) <= 10000

                for i, solution in enumerate(non_solutions, start=1):
                    assert solution.id == f"N{i:05d}"
                    assert solution.full_id == f"{instance.full_id}N{i:05d}"
                    assert not solution.cls
                    assert len(solution.dzn) >= 17


def test_Instance_get_non_solution_by_id(mpmmine: MPMMine):
    instance = mpmmine[f"P005M001I002"]
    for i in range(1, 4148):
        non_solution: Solution = instance.get_non_solution(f"N{i:05d}")
        assert non_solution.id == f"N{i:05d}"
        assert non_solution.full_id == f"MPMMine-P005M001I002N{i:05d}"
        assert not non_solution.cls
        assert len(non_solution.dzn) >= 20


def test_Instance_get_non_solution_raises_file_not_found_error(mpmmine: MPMMine):
    with pytest.raises(FileNotFoundError, match="Non-solution N99999 does not exist"):
        mpmmine["P001M001I001"].get_non_solution("N99999")


def test_MPMMine_get_by_full_id_non_solution(mpmmine: MPMMine):
    non_solution: Solution = mpmmine[f"P002M001I002N01234"]
    assert non_solution.id == f"N01234"
    assert non_solution.full_id == f"MPMMine-P002M001I002N01234"
    assert not non_solution.cls
    assert len(non_solution.dzn) >= 50


def test_MPMMine_get_by_full_id_non_solution_raises_not_found_error(mpmmine: MPMMine):
    with pytest.raises(FileNotFoundError, match="Non-solution N99999 does not exist"):
        non_solution = mpmmine[f"P002M001I002N99999"]

    with pytest.raises(FileNotFoundError, match="Non-solution N98765 does not exist"):
        non_solution = mpmmine[f"MPMMine-P002M001I002N98765"]
