from collections import defaultdict

from pydantic import BaseModel, Field
from rich.box import HEAVY_EDGE
from rich.console import Console
from rich.table import Table

from peepsai.agent import Agent
from peepsai.task import Task
from peepsai.tasks.task_output import TaskOutput
from peepsai.telemetry import Telemetry


class TaskEvaluationPydanticOutput(BaseModel):
    quality: float = Field(
        description="A score from 1 to 10 evaluating on completion, quality, and overall performance from the task_description and task_expected_output to the actual Task Output."
    )


class PeepsEvaluator:
    """
    A class to evaluate the performance of the agents in the peeps based on the tasks they have performed.

    Attributes:
        peeps (Peeps): The peeps of agents to evaluate.
        openai_model_name (str): The model to use for evaluating the performance of the agents (for now ONLY OpenAI accepted).
        tasks_scores (defaultdict): A dictionary to store the scores of the agents for each task.
        iteration (int): The current iteration of the evaluation.
    """

    tasks_scores: defaultdict = defaultdict(list)
    run_execution_times: defaultdict = defaultdict(list)
    iteration: int = 0

    def __init__(self, peeps, openai_model_name: str):
        self.peeps = peeps
        self.openai_model_name = openai_model_name
        self._telemetry = Telemetry()
        self._setup_for_evaluating()

    def _setup_for_evaluating(self) -> None:
        """Sets up the peeps for evaluating."""
        for task in self.peeps.tasks:
            task.callback = self.evaluate

    def _evaluator_agent(self):
        return Agent(
            role="Task Execution Evaluator",
            goal=(
                "Your goal is to evaluate the performance of the agents in the peeps based on the tasks they have performed using score from 1 to 10 evaluating on completion, quality, and overall performance."
            ),
            backstory="Evaluator agent for peeps evaluation with precise capabilities to evaluate the performance of the agents in the peeps based on the tasks they have performed",
            verbose=False,
            llm=self.openai_model_name,
        )

    def _evaluation_task(
        self, evaluator_agent: Agent, task_to_evaluate: Task, task_output: str
    ) -> Task:
        return Task(
            description=(
                "Based on the task description and the expected output, compare and evaluate the performance of the agents in the peeps based on the Task Output they have performed using score from 1 to 10 evaluating on completion, quality, and overall performance."
                f"task_description: {task_to_evaluate.description} "
                f"task_expected_output: {task_to_evaluate.expected_output} "
                f"agent: {task_to_evaluate.agent.role if task_to_evaluate.agent else None} "
                f"agent_goal: {task_to_evaluate.agent.goal if task_to_evaluate.agent else None} "
                f"Task Output: {task_output}"
            ),
            expected_output="Evaluation Score from 1 to 10 based on the performance of the agents on the tasks",
            agent=evaluator_agent,
            output_pydantic=TaskEvaluationPydanticOutput,
        )

    def set_iteration(self, iteration: int) -> None:
        self.iteration = iteration

    def print_peeps_evaluation_result(self) -> None:
        """
        Prints the evaluation result of the peeps in a table.
        A Peeps with 2 tasks using the command peepsai test -n 3
        will output the following table:

                        Tasks Scores
                    (1-10 Higher is better)
        ┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        ┃ Tasks/Peeps/Agents  ┃ Run 1 ┃ Run 2 ┃ Run 3 ┃ Avg. Total ┃ Agents                       ┃
        ┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
        │ Task 1             │ 9.0   │ 10.0  │ 9.0   │ 9.3        │ - AI LLMs Senior Researcher  │
        │                    │       │       │       │            │ - AI LLMs Reporting Analyst  │
        │                    │       │       │       │            │                              │
        │ Task 2             │ 9.0   │ 9.0   │ 9.0   │ 9.0        │ - AI LLMs Senior Researcher  │
        │                    │       │       │       │            │ - AI LLMs Reporting Analyst  │
        │                    │       │       │       │            │                              │
        │ Peeps               │ 9.0   │ 9.5   │ 9.0   │ 9.2        │                              │
        │ Execution Time (s) │ 42    │ 79    │ 52    │ 57         │                              │
        └────────────────────┴───────┴───────┴───────┴────────────┴──────────────────────────────┘
        """
        task_averages = [
            sum(scores) / len(scores) for scores in zip(*self.tasks_scores.values())
        ]
        peeps_average = sum(task_averages) / len(task_averages)

        table = Table(title="Tasks Scores \n (1-10 Higher is better)", box=HEAVY_EDGE)

        table.add_column("Tasks/Peeps/Agents", style="cyan")
        for run in range(1, len(self.tasks_scores) + 1):
            table.add_column(f"Run {run}", justify="center")
        table.add_column("Avg. Total", justify="center")
        table.add_column("Agents", style="green")

        for task_index, task in enumerate(self.peeps.tasks):
            task_scores = [
                self.tasks_scores[run][task_index]
                for run in range(1, len(self.tasks_scores) + 1)
            ]
            avg_score = task_averages[task_index]
            agents = list(task.processed_by_agents)

            # Add the task row with the first agent
            table.add_row(
                f"Task {task_index + 1}",
                *[f"{score:.1f}" for score in task_scores],
                f"{avg_score:.1f}",
                f"- {agents[0]}" if agents else "",
            )

            # Add rows for additional agents
            for agent in agents[1:]:
                table.add_row("", "", "", "", "", f"- {agent}")

            # Add a blank separator row if it's not the last task
            if task_index < len(self.peeps.tasks) - 1:
                table.add_row("", "", "", "", "", "")

        # Add Peeps and Execution Time rows
        peeps_scores = [
            sum(self.tasks_scores[run]) / len(self.tasks_scores[run])
            for run in range(1, len(self.tasks_scores) + 1)
        ]
        table.add_row(
            "Peeps",
            *[f"{score:.2f}" for score in peeps_scores],
            f"{peeps_average:.1f}",
            "",
        )

        run_exec_times = [
            int(sum(tasks_exec_times))
            for _, tasks_exec_times in self.run_execution_times.items()
        ]
        execution_time_avg = int(sum(run_exec_times) / len(run_exec_times))
        table.add_row(
            "Execution Time (s)", *map(str, run_exec_times), f"{execution_time_avg}", ""
        )

        console = Console()
        console.print(table)

    def evaluate(self, task_output: TaskOutput):
        """Evaluates the performance of the agents in the peeps based on the tasks they have performed."""
        current_task = None
        for task in self.peeps.tasks:
            if task.description == task_output.description:
                current_task = task
                break

        if not current_task or not task_output:
            raise ValueError(
                "Task to evaluate and task output are required for evaluation"
            )

        evaluator_agent = self._evaluator_agent()
        evaluation_task = self._evaluation_task(
            evaluator_agent, current_task, task_output.raw
        )

        evaluation_result = evaluation_task.execute_sync()

        if isinstance(evaluation_result.pydantic, TaskEvaluationPydanticOutput):
            self._test_result_span = self._telemetry.individual_test_result_span(
                self.peeps,
                evaluation_result.pydantic.quality,
                current_task.execution_duration,
                self.openai_model_name,
            )
            self.tasks_scores[self.iteration].append(evaluation_result.pydantic.quality)
            self.run_execution_times[self.iteration].append(
                current_task.execution_duration
            )
        else:
            raise ValueError("Evaluation result is not in the expected format")
