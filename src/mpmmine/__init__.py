import json
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Optional, Generator


class MPMMine:
    path: Path
    id_regex = re.compile(
        r"^(MPMMine-)?(?P<problem>P\d{3})(?P<model>M\d{3})?(?P<instance>I\d{3})?(?P<description>D\d{3})?(?P<solution>S\d{6})?(?P<non_solution>N\d{6})?$")
    model_id_regex = re.compile(r"^M\d{3}$")
    description_id_regex = re.compile(r"^D\d{3}$")
    instance_id_regex = re.compile(r"^I\d{3}$")
    solution_id_regex = re.compile(r"^S\d{6}$")
    non_solution_id_regex = re.compile(r"^N\d{6}$")

    def __init__(self, path: Path):
        """
        Initializes MPMMine
        :param path: to the MPMMine directory
        """
        self.path = path
        if not path.exists():
            raise ValueError(f"Path {path} does not exist!")

    @cached_property
    def problems(self) -> list[Problem]:
        """
        The list of available problems.
        :return:
        """
        return sorted([self.get_problem(path) for path in (self.path / "problems").glob("P*")], key=lambda p: p.id)

    def __getitem__(self, id: str) -> Problem | Model | Instance | Description | Solution:
        id_parts = self.id_regex.fullmatch(id)
        if id_parts is None:
            raise ValueError(f"Id {id} is invalid")

        problem = self.get_problem(id_parts["problem"])
        if id_parts["model"] is None:
            return problem

        model = problem.get_model(id_parts["model"])
        if id_parts["instance"] is not None:
            instance = model.get_instance(id_parts["instance"])
            if id_parts["description"] is not None:
                return instance.get_description(id_parts["description"])
            if id_parts["solution"] is not None:
                return instance.get_solution(id_parts["solution"])
            if id_parts["non_solution"] is not None:
                return instance.get_non_solution(id_parts["non_solution"])
            return instance
        if id_parts["description"] is not None:
            return model.get_description(id_parts["description"])
        return model

    def get_problem(self, id: str | Path) -> Problem:
        match id:
            case str():
                path = next((self.path / "problems").glob(f"{id}*"), None)
            case Path():
                path = id
            case _:
                raise ValueError(f"Invalid argument type {type(id)}")

        if path is None or not path.exists():
            raise ValueError(f"Problem {id} does not exist")

        manifest = path / "manifest.json"
        with open(manifest, "r") as f:
            raw = json.load(f)
            return Problem(**raw, full_id=f"MPMMine-{raw['id']}", path=path)


@dataclass(frozen=True)
class Problem:
    id: str
    name: str
    tags: dict[str, str]
    features: dict[str, str | dict[str, str]]
    alternative_ids: dict[str, str]
    references: list[dict[str, str]]
    links: dict[str, str]
    full_id: str
    path: Path

    @cached_property
    def models(self) -> list[Model]:
        """
        The list of available models for this problem.
        This property is lazy-initialized.
        :return:
        """
        return sorted([
            Model(
                id=(id_ := path.name.split()[0]),
                full_id=f"{self.full_id}{id_}",
                path=path / "model.mzn",
                problem=self
            ) for path in (self.path / "models").glob(f"M*")
        ], key=lambda m: m.id)

    def get_model(self, id: str) -> Model:
        """
        Gets a model by model-id.
        This function runs in O(1), contrary to the O(n) id-based lookup in the models property.
        :param id:
        :return:
        """
        if MPMMine.model_id_regex.fullmatch(id) is None:
            raise ValueError(f"Id {id} is invalid")
        try:
            return Model(
                id=id,
                full_id=f"{self.full_id}{id}",
                path=next((self.path / "models").glob(f"{id}*")) / "model.mzn",
                problem=self
            )
        except StopIteration:
            raise ValueError(f"Model {id} does not exist")


@dataclass(frozen=True)
class Model:
    id: str
    full_id: str
    path: Path
    problem: Problem

    @cached_property
    def mzn(self) -> str:
        """
        The MiniZinc code for this model
        This property is lazy-initialized.
        """
        return self.path.read_text(encoding="utf-8")

    @cached_property
    def instances(self) -> list[Instance]:
        """
        The list of instances for this model.
        This property is lazy-initialized.
        :return:
        """
        return sorted([
            Instance(
                id=(id_ := path.name.split()[0]),
                full_id=f"{self.full_id}{id_}",
                path=path / "instance.dzn",
                model=self
            ) for path in (self.path.with_name("instances")).glob(f"I*")
        ], key=lambda i: i.id)

    def get_instance(self, id: str) -> Instance:
        if MPMMine.instance_id_regex.fullmatch(id) is None:
            raise ValueError(f"Id {id} is invalid")
        try:
            return Instance(
                id=id,
                full_id=f"{self.full_id}{id}",
                path=next((self.path.with_name("instances")).glob(f"{id}*")) / "instance.dzn",
                model=self
            )
        except StopIteration:
            raise ValueError(f"Instance {self.full_id}{id} does not exist")

    @cached_property
    def descriptions(self) -> list[Description]:
        """
        The list of descriptions for this model.
        This property is lazy-initialized.
        :return:
        """
        return [
            Description(
                id=(id_ := path.name.split()[0]),
                full_id=f"{self.full_id}{id_}",
                path=path,
                model=self
            ) for path in (self.path.with_name("descriptions")).glob(f"D*")
        ]

    def get_description(self, id: str) -> Description:
        """
        Gets a description by description-id.
        This function runs in O(1), contrary to the O(n) id-based lookup in the descriptions property.
        :param id:
        :return:
        """
        if MPMMine.description_id_regex.fullmatch(id) is None:
            raise ValueError(f"Id {id} is invalid")
        try:
            return Description(
                id=id,
                full_id=f"{self.full_id}{id}",
                path=next(self.path.with_name("descriptions").glob(f"{id}*")),
                model=self
            )
        except StopIteration:
            raise ValueError(f"Description {id} does not exist")


@dataclass(frozen=True)
class Instance:
    id: str
    full_id: str
    path: Path
    model: Model

    @cached_property
    def dzn(self) -> str:
        """
        The instance DZN file contents
        This property is lazy-initialized.
        """
        return self.path.read_text(encoding="utf-8")

    @property
    def solutions(self) -> Generator[Solution, None, None]:
        """
        The generator of solutions for this instance.
        :return:
        """
        return (
            Solution(
                id=(id_ := path.name.split()[0]),
                full_id=f"{self.full_id}{id_}",
                path=path,
                cls=True,
                instance=self
            ) for path in (self.path.with_name("solutions")).glob(f"S*")
        )

    def get_solution(self, id: str) -> Solution:
        """
        Gets a solution by solution-id.
        This function runs in O(1), contrary to the O(n) id-based lookup in the solutions property.
        :param id:
        :return:
        """
        if MPMMine.solution_id_regex.fullmatch(id) is None:
            raise ValueError(f"Id {id} is invalid")
        try:
            return Solution(
                id=id,
                full_id=f"{self.full_id}{id}",
                path=next(self.path.with_name("solutions").glob(f"{id}*")),
                cls=True,
                instance=self
            )
        except StopIteration:
            raise ValueError(f"Solution {id} does not exist")

    @property
    def non_solutions(self) -> Generator[Solution, None, None]:
        """
        The generator of solutions for this instance.
        :return:
        """
        return (
            Solution(
                id=(id_ := path.name.split()[0]),
                full_id=f"{self.full_id}{id_}",
                path=path,
                cls=False,
                instance=self
            ) for path in (self.path.with_name("non solutions")).glob(f"N*")
        )

    def get_non_solution(self, id: str) -> Solution:
        """
        Gets a non-solution by non-solution-id.
        This function runs in O(1), contrary to the O(n) id-based lookup in the non-solutions property.
        :param id:
        :return:
        """
        if MPMMine.non_solution_id_regex.fullmatch(id) is None:
            raise ValueError(f"Id {id} is invalid")
        try:
            return Solution(
                id=id,
                full_id=f"{self.full_id}{id}",
                path=next((self.path.with_name("non solutions")).glob(f"{id}*")),
                cls=False,
                instance=self
            )
        except StopIteration:
            raise ValueError(f"Non-solution {id} does not exist")

    @cached_property
    def descriptions(self):
        raise NotImplementedError

    def get_description(self, id: str) -> Description:
        raise NotImplementedError


@dataclass(frozen=True)
class Description:
    id: str
    full_id: str
    path: Path
    model: Optional[Model] = None
    instance: Optional[Instance] = None

    @cached_property
    def markdown(self) -> str:
        """
        The description Markdown contents.
        This property is lazy-initialized.
        """
        return self.path.read_text(encoding="utf-8")


@dataclass(frozen=True)
class Solution:
    id: str
    full_id: str
    path: Path
    cls: bool
    instance: Instance

    @property
    def dzn(self) -> str:
        """
        The solution/non-solution DZN file contents
        Caution! Repetitive access to this property may be slow, as it reads the underlying file on each access.
        External caching is recommended for repetitive access.
        """
        return self.path.read_text(encoding="utf-8")
