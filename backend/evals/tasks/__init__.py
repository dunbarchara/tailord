from evals.tasks.base import ClassificationTask
from evals.tasks.real import REAL_SECTION_LABEL, REAL_SEMANTIC_TYPE
from evals.tasks.semantic_type import SEMANTIC_TYPE

TASKS: dict[str, ClassificationTask] = {
    t.name: t for t in (SEMANTIC_TYPE, REAL_SEMANTIC_TYPE, REAL_SECTION_LABEL)
}
