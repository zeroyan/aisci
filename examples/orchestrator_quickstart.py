"""Quickstart example for BranchOrchestrator multi-branch execution.

This example demonstrates how to use the BranchOrchestrator to run
experiments with multiple parallel branches exploring different variants.
"""

from pathlib import Path
from datetime import datetime

from src.orchestrator.branch_orchestrator import BranchOrchestrator
from src.orchestrator.config import OrchestratorConfig
from src.schemas.research_spec import ResearchSpec, ExperimentPlan
from src.schemas import PlanStep, Baseline, Metric, Constraints


def main() -> None:
    """Run a simple multi-branch experiment."""
    # 1. Create orchestrator configuration (immutable, create new instance)
    base_config = OrchestratorConfig.default()
    config = OrchestratorConfig(
        orchestrator=base_config.orchestrator.model_copy(
            update={
                "num_branches": 3,
                "max_iterations": 10,
            }
        ),
        budget=base_config.budget.model_copy(
            update={
                "max_cost_usd": 10.0,
                "max_time_hours": 2.0,
            }
        ),
        docker=base_config.docker,
        memory=base_config.memory,
        logging=base_config.logging,
    )

    # 2. Define research specification
    spec = ResearchSpec(
        title="Example: Compare Sorting Algorithms",
        research_question="Which sorting algorithm is fastest for random data?",
        hypothesis="QuickSort will outperform BubbleSort on random arrays",
        success_criteria=[
            "Measure execution time for 1000-element arrays",
            "Compare QuickSort vs BubbleSort vs MergeSort",
            "Generate performance comparison chart",
        ],
        constraints=Constraints(
            technical=["Use Python standard library only"],
            data=["Test with random integer arrays"],
        ),
        baseline=Baseline(
            description="No baseline - first implementation",
            metrics={},
        ),
        metrics=[
            Metric(
                name="execution_time",
                description="Average execution time in seconds",
                target_value=0.1,
                higher_is_better=False,
            )
        ],
    )

    # 3. Define experiment plan
    plan = ExperimentPlan(
        approach="Implement three sorting algorithms and benchmark them",
        steps=[
            PlanStep(
                step_number=1,
                description="Create test data generator for random arrays",
                expected_output="data_generator.py",
            ),
            PlanStep(
                step_number=2,
                description="Implement QuickSort algorithm",
                expected_output="quicksort.py",
            ),
            PlanStep(
                step_number=3,
                description="Implement BubbleSort algorithm",
                expected_output="bubblesort.py",
            ),
            PlanStep(
                step_number=4,
                description="Implement MergeSort algorithm",
                expected_output="mergesort.py",
            ),
            PlanStep(
                step_number=5,
                description="Create timing benchmark harness",
                expected_output="benchmark.py",
            ),
            PlanStep(
                step_number=6,
                description="Run benchmarks and collect results",
                expected_output="results.json",
            ),
        ],
        validation_method="Compare execution times across algorithms",
    )

    # 4. Initialize orchestrator
    orchestrator = BranchOrchestrator(config)

    # 5. Run multi-branch experiment
    print("Starting multi-branch experiment...")
    print(f"Branches: {config.orchestrator['num_branches']}")
    print(f"Budget: ${config.budget.max_cost_usd} / {config.budget.max_time_hours}h")
    print()

    run_id = f"quickstart_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    runs_dir = Path("runs")
    runs_dir.mkdir(exist_ok=True)

    result = orchestrator.run(
        spec=spec,
        plan=plan,
        run_id=run_id,
        runs_dir=runs_dir,
    )

    # 6. Display results
    print("\n" + "=" * 60)
    print("Experiment Complete!")
    print("=" * 60)
    print(f"Run ID: {result.run_id}")
    print(f"Status: {result.status}")
    print(f"Total Cost: ${result.total_cost_usd:.2f}")
    print(f"Total Time: {result.total_time_seconds:.1f}s")
    print(f"Iterations: {result.iterations}")
    print()
    print(f"Results saved to: runs/{run_id}/")


if __name__ == "__main__":
    main()
