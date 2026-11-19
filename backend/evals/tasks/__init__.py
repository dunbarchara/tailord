from evals.tasks.base import ClassificationTask
from evals.tasks.semantic_type import SEMANTIC_TYPE

TASKS: dict[str, ClassificationTask] = {SEMANTIC_TYPE.name: SEMANTIC_TYPE}
