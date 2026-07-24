#!/usr/bin/env python3
import os
import json
import subprocess
import re
import argparse
import textwrap
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed



def check_file(checker_path, data, sol_file, solver, expect_feasible, kwargs):
    if "check_objective=true;" in kwargs:
        with open(sol_file, "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(r'_objective\s*=\s*([^;]+);', content)
            
            if match:
                objective_value = match.group(1)
                kwargs.append(f"obj_from_sol={objective_value};")
    else:
        kwargs.append("obj_from_sol=0.0;") # Dummy value for unused variable to be replaced by Error

    # Command: minizinc --solver <solver> <checker> <data> <solution> --statistics
    cmd = ["minizinc", "--solver", solver, str(checker_path), str(data), str(sol_file), "--statistics"] + ([] if not kwargs else ["-D " + kw for kw in  kwargs])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=300)
        
        stdout = res.stdout
        stderr = res.stderr
        
        is_feasible = ("""CORRECT: all constraints hold.""" in stdout)
        is_infeasible = ("ERROR" in stdout) and ("INCORRECT: See error log above for specific violations." in stdout)
        
        if is_feasible:
            status = "PASS" if expect_feasible else "FAIL (Unexpectedly Feasible)"
        elif is_infeasible:
            status = "PASS" if not expect_feasible else "FAIL (Infeasible)"
        else:
            status = "ERROR"

        return status, f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"

    except subprocess.CalledProcessError as e:
            return "ERROR", f"STDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}"
            
    except Exception as e:
        return "ERROR", str(e)

def process_directory(LOG_DIR, checker_path, instance_path, folder_path, solver, workers, is_solution_folder, prob_id, mod_id, kwargs):
    inst_id = instance_path.parent.name
    suffix = "SOLUTIONS" if is_solution_folder else "NON_SOLUTIONS"
    target_type = "VALID" if is_solution_folder else "INVALID"
    
    label = f"{prob_id}_{mod_id}_{inst_id}_{suffix}"
    
    final_log_name = LOG_DIR / f"RESULT_{label}.log"
    temp_log_name = final_log_name.with_suffix(".tmp")

    if final_log_name.exists():
        return "ALREADY_DONE", label

    files = sorted(list(folder_path.glob("*.dzn")))
    total_files = len(files)
    if total_files == 0:
        return "EMPTY", label

    with open(temp_log_name, "w") as f:
        f.write(f"DIRECTORY: {folder_path}\n")
        f.write(f"CHECKER: {checker_path.name}\n")
        f.write(f"EXPECTATION: {target_type}\n")
        f.write("-" * 50 + "\n\n")

    passed_count = 0
    all_passed = True
    
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(check_file, checker_path, instance_path, f, solver, is_solution_folder, kwargs): f for f in files}
        
        for future in as_completed(futures):
            sol_file = futures[future]
            status, output = future.result()
            
            if status == "PASS":
                passed_count += 1
            else:
                all_passed = False

            with open(temp_log_name, "a") as f:
                f.write(f"[{status}] {sol_file.name}\n{output}\n{'-'*30}\n")
                f.flush()

    stats_line = f"STATISTICS: {passed_count} out of {total_files} files were {target_type}\n"
    with open(temp_log_name, "r") as f:
        content = f.read()
    with open(temp_log_name, "w") as f:
        f.write(stats_line + content)

    temp_log_name.rename(final_log_name)
    return "SUCCESS" if all_passed else "FAILED", label

def main():
    parser = argparse.ArgumentParser(
        prog="mpmmine-checker-runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent("""
            Automated MPMMINE Model Conformance & Solution Validation Script
            ================================================================
            Evaluates candidate MiniZinc solutions against specified checker 
            models (`checker.mzn`) across structured problem directories of 
            the MPMMine benchmark dataset.

            The tool recursively discovers models and instances under the target
            root directory, running MiniZinc against both valid ("solutions") 
            and invalid ("non solutions") folders to ensure exact 
            constraint enforcement and objective value verification.

            Examples:
              # Run full validation using all available CPU cores
              python checker_runner.py ./problems

              # Run using 4 processes with the Gurobi solver
              python checker_runner.py ./problems --solver gurobi --workers 4

              # Include objective value parsing and verification
              python checker_runner.py ./problems --with_objective

            Directory Structure Expected:
              MPMMINE/
                └── problems/
                    ├── manifest.json
                    └── models/
                        └── <model_id>/
                            ├── checker.mzn
                            └── instances/
                                └── <instance_id>/
                                    ├── instance.dzn
                                    ├── solutions/*.dzn
                                    └── non solutions/*.dzn
        """)
    )

    parser.add_argument(
        "root",
        type=Path,
        help="Path to the root 'problems' directory containing MPMMine benchmark dataset."
    )
    parser.add_argument(
        "--solver",
        default="gecode",
        metavar="SOLVER",
        help="MiniZinc solver backend to use for running checkers (default: 'gecode')."
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=os.cpu_count(),
        metavar="N",
        help="Number of concurrent worker processes for checking files (default: system CPU count)."
    )
    parser.add_argument(
        "--with_objective",
        action='store_true',
        help="Enable objective function validation for solution files and output logs to 'checker_logs_with_objective'."
    )
    args = parser.parse_args()

    LOG_DIR = Path("checker_logs") if not args.with_objective else Path("checker_logs_with_objective")
    LOG_DIR.mkdir(exist_ok=True)

    for model_mzn in sorted(args.root.glob("**/models/M*/model.mzn")):
        prob_id = model_mzn.parts[-4]
        mod_id = model_mzn.parts[-2]
        manifest_file = str(model_mzn.parent.parent.parent) + "/manifest.json"
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        model_dir = model_mzn.parent

        # if prob_id[:4] not in ["P018"]: continue ## filtering
        # if mod_id not in ["M001"]: continue    ## filtering
        
        checker = model_dir / "checker.mzn"

        for inst_dir in sorted((model_dir / "instances").glob("I*")):
            instance_dzn = inst_dir / "instance.dzn"
            if not instance_dzn.exists(): 
                continue

            for folder_name, is_sol in [("solutions", True), ("non solutions", False)]:
                folder_path = inst_dir / folder_name
                if folder_path.exists():
                    kwargs = []
                    if manifest["features"]["variables"]["continuous"] or prob_id[:4] == "P008":
                        if is_sol:
                            kwargs.append('is_solution=true;')
                        else:
                            kwargs.append('is_solution=false;')

                    if args.with_objective and folder_name == "solutions":
                        kwargs.append('check_objective=true;')
                    else:
                        kwargs.append('check_objective=false;')


                    status, label = process_directory(
                        LOG_DIR,
                        checker, 
                        instance_dzn, 
                        folder_path, 
                        args.solver, 
                        args.workers, 
                        is_sol,
                        prob_id,
                        mod_id,
                        kwargs
                    )
                    print(f"[{status}] {label}")

    print(f"\nDone. Logs available in: {LOG_DIR}")

if __name__ == "__main__":
    main()