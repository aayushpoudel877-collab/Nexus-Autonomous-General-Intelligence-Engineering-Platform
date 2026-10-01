from services.api.app.db.base import Base
from services.api.app.models import (
    ResearchPlan,
    ResearchTask,
    WorkbenchDataset,
    WorkbenchExperiment,
    WorkbenchProject,
)


def test_workbench_and_research_tables_are_registered():
    expected = {
        "workbench_projects",
        "workbench_datasets",
        "workbench_experiments",
        "research_plans",
        "research_tasks",
    }
    assert expected.issubset(Base.metadata.tables)


def test_research_task_model_has_dependency_and_output_fields():
    columns = ResearchTask.__table__.columns
    assert "depends_on" in columns
    assert "output_summary" in columns


def test_research_plan_can_link_to_workbench_project():
    foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in ResearchPlan.__table__.c.workbench_project_id.foreign_keys
    }
    assert "workbench_projects.id" in foreign_keys


def test_workbench_models_are_importable():
    assert WorkbenchProject.__tablename__ == "workbench_projects"
    assert WorkbenchDataset.__tablename__ == "workbench_datasets"
    assert WorkbenchExperiment.__tablename__ == "workbench_experiments"
