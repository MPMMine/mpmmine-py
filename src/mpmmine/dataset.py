import json
import logging
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Optional

from mpmmine.backend import Backend


class MPMMine:
    """
    The main class for MPMMine dataset supporting utility.
    """
    _backend: Backend
    _id_regex = re.compile(
        r"^(MPMMine-)?(?P<problem>P\d{3})(?P<model>M\d{3})?(?P<instance>I\d{3})?(?P<description>D\d{3})?((?P<solution>S\d{5})?|(?P<non_solution>N\d{5})?)$")
    _problem_id_regex = re.compile(r"^P\d{3}$")
    _model_id_regex = re.compile(r"^M\d{3}$")
    _description_id_regex = re.compile(r"^D\d{3}$")
    _instance_id_regex = re.compile(r"^I\d{3}$")
    _solution_id_regex = re.compile(r"^S\d{5}$")
    _non_solution_id_regex = re.compile(r"^N\d{5}$")

    def __init__(self, path_or_backend: Path | Backend):
        """
        Initializes MPMMine.
        :param path_or_backend: path to the MPMMine dataset or an initialized backend.
        """
        if isinstance(path_or_backend, Backend):
            self._backend = path_or_backend
        else:
            self._backend = self._detect_backend(path_or_backend)

    def _detect_backend(self, path: Path) -> Backend:
        try:
            from mpmmine.sqlite_backend import SQLiteBackend
            if SQLiteBackend.matches(path):
                return SQLiteBackend(path)
        except ImportError as e:
            logging.error("Cannot load SQLite backend.", exc_info=e)

        try:
            from mpmmine.zip_backend import ZipBackend
            if ZipBackend.matches(path):
                return ZipBackend(path)
        except ImportError as e:
            logging.error("Cannot load ZIP backend.", exc_info=e)

        try:
            from mpmmine.seven_zip_backend import SevenZipBackend
            if SevenZipBackend.matches(path):
                return SevenZipBackend(path)
        except ImportError as e:
            logging.error("Cannot load 7z backend. Install py7zr package for the use of 7z backend.", exc_info=e)

        try:
            from mpmmine.file_backend import FileBackend
            if FileBackend.matches(path):
                return FileBackend(path)
        except ImportError as e:
            logging.error("Cannot load file backend.", exc_info=e)

        raise ValueError(f"Cannot detect backend for path {path}")

    def __getitem__(self, id: str) -> Problem | Model | Instance | Description | Solution:
        """
        Gets an artifact from MPMMine dataset by its full id.
        :param id: Full id of the artifact.
        :return: The artifact, e.g., `Problem`, `Model`, `Instance`, `Description`, `Solution`, or `Solution`.
        :raises ValueError: if id is invalid
        :raises FileNotFoundError: if id does not exist
        """
        id_parts = self._id_regex.fullmatch(id)
        if id_parts is None:
            raise ValueError(f"Id {id} is invalid")

        problem = self.get_problem(id_parts["problem"])
        if id_parts["model"] is None:
            if any([id_parts["instance"], id_parts["description"], id_parts["solution"], id_parts["non_solution"]]):
                raise ValueError(f"Id {id} is invalid")
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
            if any([id_parts["solution"], id_parts["non_solution"]]):
                raise ValueError(f"Id {id} is invalid")
            return model.get_description(id_parts["description"])

        if any([id_parts["solution"], id_parts["non_solution"]]):
            raise ValueError(f"Id {id} is invalid")
        return model

    @cached_property
    def problems(self) -> list[Problem]:
        """
        The list of available problems.
        This property is lazy-initialized.
        :return: The list of problems.
        """
        out = [
            self._get_problem(path.name.rsplit()[0], path)
            for path in self._backend.sub("problems").glob("P*")
        ]
        out.sort(key=lambda p: p.id)
        return out

    def get_problem(self, id: str) -> Problem:
        """
        Gets a problem by problem-id.
        :param id: Problem id in short form, e.g., P001.
        :return: Problem
        :raises ValueError: if id is invalid
        :raises FileNotFoundError: if id does not exist
        """
        return self._get_problem(id)

    def _get_problem(self, id: str, _path: Backend | None = None) -> Problem:
        if MPMMine._problem_id_regex.fullmatch(id) is None:
            raise ValueError(f"Id {id} is invalid")

        try:
            if _path is not None:
                path = _path
            else:
                path = next(self._backend.sub("problems").glob(f"{id}*"))

            raw = json.loads(path.read("manifest.json"))
            return Problem(**raw, full_id=f"MPMMine-{raw['id']}", _backend=path)
        except (OSError, StopIteration) as err:
            raise FileNotFoundError(f"Problem {id} does not exist") from err


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
    _backend: Backend

    @cached_property
    def models(self) -> list[Model]:
        """
        The list of available models for this problem.
        This property is lazy-initialized.
        :return:
        """
        out = [
            Model(
                id=(id_ := path.name.split()[0]),
                full_id=f"{self.full_id}{id_}",
                _backend=path,
                problem=self
            ) for path in self._backend.sub("models").glob("M*")
        ]
        out.sort(key=lambda m: m.id)
        return out

    def get_model(self, id: str) -> Model:
        """
        Gets a model by model-id.
        This function runs in O(1), contrary to the O(n) id-based lookup in the `models` property.
        :param id: Model id in short form, e.g., M001.
        :raises ValueError: if id is invalid
        :raises FileNotFoundError: if id does not exist
        """
        if MPMMine._model_id_regex.fullmatch(id) is None:
            raise ValueError(f"Id {id} is invalid")
        try:
            return Model(
                id=id,
                full_id=f"{self.full_id}{id}",
                _backend=next(self._backend.sub("models").glob(f"{id}*")),
                problem=self
            )
        except StopIteration:
            raise FileNotFoundError(f"Model {id} does not exist")


@dataclass(frozen=True)
class Model:
    id: str
    full_id: str
    _backend: Backend
    problem: Problem

    @cached_property
    def mzn(self) -> str:
        """
        The MiniZinc code for this model.
        This property is lazy-initialized.
        """
        return self._backend.read("model.mzn")

    @cached_property
    def instances(self) -> list[Instance]:
        """
        The list of instances for this model.
        This property is lazy-initialized.
        :return:
        """
        out = [
            Instance(
                id=(id_ := path.name.split()[0]),
                full_id=f"{self.full_id}{id_}",
                _backend=path,
                model=self
            ) for path in self._backend.sub("instances").glob(f"I*")
        ]
        out.sort(key=lambda i: i.id)
        return out

    def get_instance(self, id: str) -> Instance:
        """
        Gets a model instance by instance-id.
        This function runs in O(1), contrary to the O(n) id-based lookup in the `instances` property.
        :param id: Instance id in short form, e.g., I001.
        :return: Instance
        :raises ValueError: if id is invalid
        :raises FileNotFoundError: if id does not exist
        """
        if MPMMine._instance_id_regex.fullmatch(id) is None:
            raise ValueError(f"Id {id} is invalid")
        try:
            return Instance(
                id=id,
                full_id=f"{self.full_id}{id}",
                _backend=next(self._backend.sub("instances").glob(f"{id}*")),
                model=self
            )
        except StopIteration:
            raise FileNotFoundError(f"Instance {id} does not exist")

    @cached_property
    def descriptions(self) -> list[Description]:
        """
        The list of descriptions for this model.
        This property is lazy-initialized.
        :return:
        """
        out = [
            Description(
                id=(id_ := path.name.split()[0]),
                full_id=f"{self.full_id}{id_}",
                _backend=path,
                model=self
            ) for path in self._backend.sub("descriptions").glob(f"D*")
        ]
        out.sort(key=lambda d: d.id)
        return out

    def get_description(self, id: str) -> Description:
        """
        Gets a description by description-id.
        This function runs in O(1), contrary to the O(n) id-based lookup in the `descriptions` property.
        :param id: Description id in short form, e.g., D001.
        :return: Description
        :raises ValueError: if id is invalid
        :raises FileNotFoundError: if id does not exist
        """
        if MPMMine._description_id_regex.fullmatch(id) is None:
            raise ValueError(f"Id {id} is invalid")
        try:
            return Description(
                id=id,
                full_id=f"{self.full_id}{id}",
                _backend=next(self._backend.sub("descriptions").glob(f"{id}*")),
                model=self
            )
        except StopIteration:
            raise FileNotFoundError(f"Description {id} does not exist")


@dataclass(frozen=True)
class Instance:
    id: str
    full_id: str
    _backend: Backend
    model: Model

    @cached_property
    def dzn(self) -> str:
        """
        The instance DZN file contents.
        This property is lazy-initialized.
        """
        return self._backend.read("instance.dzn")

    @property
    def solutions(self) -> list[Solution]:
        """
        The list of solutions for this instance.
        This property is lazy-initialized.
        Caution! This property is not cached; every read causes file system access.
        :return:
        """
        try:
            out = [
                Solution(
                    id=(id_ := path.name.split()[0]),
                    full_id=f"{self.full_id}{id_}",
                    _backend=path,
                    cls=True,
                    instance=self
                ) for path in self._backend.sub("solutions").glob(f"S*")
            ]
            out.sort(key=lambda s: s.id)
            return out
        except FileNotFoundError:
            return []

    def get_solution(self, id: str) -> Solution:
        """
        Gets a solution by solution-id.
        This function runs in O(1), contrary to the O(n) id-based lookup in the `solutions` property.
        :param id: Solution id in short form, e.g., S00001.
        :return: Solution
        :raises ValueError: if id is invalid
        :raises FileNotFoundError: if id does not exist
        """
        if MPMMine._solution_id_regex.fullmatch(id) is None:
            raise ValueError(f"Id {id} is invalid")
        try:
            return Solution(
                id=id,
                full_id=f"{self.full_id}{id}",
                _backend=next(self._backend.sub("solutions").glob(f"{id}*")),
                cls=True,
                instance=self
            )
        except StopIteration:
            raise FileNotFoundError(f"Solution {id} does not exist")

    @property
    def non_solutions(self) -> list[Solution]:
        """
        The list of non solutions for this instance.
        Caution! This property is not cached. Every read causes file system access.
        :return:
        """
        try:
            out = [
                Solution(
                    id=(id_ := path.name.split()[0]),
                    full_id=f"{self.full_id}{id_}",
                    _backend=path,
                    cls=False,
                    instance=self
                ) for path in self._backend.sub("non solutions").glob(f"N*")
            ]
            out.sort(key=lambda s: s.id)
            return out
        except FileNotFoundError:
            return []

    def get_non_solution(self, id: str) -> Solution:
        """
        Gets a non-solution by non-solution-id.
        This function runs in O(1), contrary to the O(n) id-based lookup in the non-solutions property.
        :param id: Non-solution id in short form, e.g., N00001.
        :return: Non-solution
        :raises ValueError: if id is invalid
        :raises FileNotFoundError: if id does not exist
        """
        if MPMMine._non_solution_id_regex.fullmatch(id) is None:
            raise ValueError(f"Id {id} is invalid")
        try:
            return Solution(
                id=id,
                full_id=f"{self.full_id}{id}",
                _backend=next(self._backend.sub("non solutions").glob(f"{id}*")),
                cls=False,
                instance=self
            )
        except StopIteration:
            raise FileNotFoundError(f"Non-solution {id} does not exist")

    @cached_property
    def descriptions(self) -> list[Description]:
        """
        The list of descriptions for this model with instance parameter values set.
        This property is lazy-initialized.
        :return:
        """
        out = [
            Description(
                id=(id_ := path.name.split()[0]),
                full_id=f"{self.full_id}{id_}",
                _backend=path,
                model=self.model,
                instance=self
            ) for path in self._backend.sub("descriptions").glob(f"D*")
        ]
        out.sort(key=lambda d: d.id)
        return out

    def get_description(self, id: str) -> Description:
        """
        Gets by description-id a description of model with instance parameter values set.
        This function runs in O(1), contrary to the O(n) id-based lookup in the `descriptions` property.
        :param id: Description id in short form, e.g., D001.
        :return: Description
        :raises ValueError: if id is invalid
        :raises FileNotFoundError: if id does not exist
        """
        if MPMMine._description_id_regex.fullmatch(id) is None:
            raise ValueError(f"Id {id} is invalid")
        try:
            return Description(
                id=id,
                full_id=f"{self.full_id}{id}",
                _backend=next(self._backend.sub("descriptions").glob(f"{id}*")),
                model=self.model,
                instance=self
            )
        except StopIteration:
            raise FileNotFoundError(f"Description {id} does not exist")


@dataclass(frozen=True)
class Description:
    id: str
    full_id: str
    _backend: Backend
    model: Optional[Model] = None
    instance: Optional[Instance] = None

    @cached_property
    def markdown(self) -> str:
        """
        The description Markdown contents.
        This property is lazy-initialized.
        """
        return self._backend.read()


@dataclass(frozen=True)
class Solution:
    id: str
    full_id: str
    _backend: Backend
    cls: bool
    instance: Instance

    @property
    def dzn(self) -> str:
        """
        The solution/non-solution DZN file contents.
        Caution! Repetitive access to this property may be slow, as it reads the underlying file on each access.
        External caching is recommended for repetitive access.
        """
        return self._backend.read()
