![image](https://github.com/MPMMine/MPMMine/raw/main/docs/assets/banner.png)

# mpmmine-py: A Python package for accessing the MPMMine dataset

The mpmmine-py library provides a Python API for the [MPMMine](https://github.com/MPMMine/MPMMine) benchmark dataset.
By leveraging native Python structures, it simplifies script development and facilitates seamless integration of the
dataset into larger Python projects.
MPMMine is a standardized dataset of benchmark problems for Mathematical
Programming model mining problems. For the details on the dataset, see the corresponding
[repository](https://github.com/MPMMine/MPMMine).

## Getting started

### Installation

```shell
pip install mpmmine
```

### Usage

```python
from mpmmine import MPMMine
from pathlib import Path

mpmmine = MPMMine(Path("~/path/to/MPMMine").expanduser())

print("Available benchmarks and their statistics: ")
for problem in mpmmine.problems:
    for model in problem.models:
        for instance in model.instances:
            print(f"{instance.full_id}: {len(list(instance.solutions))} solutions, and " +
                  f"{len(list(instance.non_solutions))} non-solutions")

print("A reference MiniZinc model for benchmark P016M001:")
model = mpmmine["MPMMine-P016M001"]
print(model.mzn)  # read MiniZinc code

print("Here's the problem description in natural text:")
print(model.get_description("D001").markdown)  # read Markdown

print("Here's another description read using full artifact id:")
print(mpmmine["MPMMine-P016M001D002"].markdown)  # read Markdown

print("Here's I001 instance (model parameters):")
print(model.get_instance("I001").dzn)  # read MiniZinc data 

print("Here's some solutions (variable values):")
for i, solution in enumerate(mpmmine["MPMMine-P016M001I001"].solutions):
    if i >= 3:
        break
    print(f"% {solution.full_id}:\n{solution.dzn}")

print("... and non-solutions:")
for i, non_solution in enumerate(mpmmine["MPMMine-P016M001I001"].non_solutions):
    if i >= 3:
        break
    print(f"% {non_solution.full_id}:\n{non_solution.dzn}")
```


