from services.api.app.db.base import Base
from services.api.app.models import (
    ResearchPlan,
    ResearchTask,
    WorkbenchDataset,
    WorkbenchExperiment,
    WorkbenchProject,
    MLTrainingRun,
    RegisteredModel,
    ModelEvaluation,
    MultimodalAsset,
)


def test_workbench_and_research_tables_are_registered():
    expected = {
        "workbench_projects",
        "workbench_datasets",
        "workbench_experiments",
        "research_plans",
        "research_tasks",
        "ml_training_runs",
        "registered_models",
        "model_evaluations",
        "multimodal_assets",
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


def test_registered_model_source_constraints_are_defined():
    constraints = {constraint.name for constraint in RegisteredModel.__table__.constraints}
    assert "uq_registered_model_project_name_version" in constraints
    assert "ml_training_runs.id" in {
        foreign_key.target_fullname
        for foreign_key in RegisteredModel.__table__.c.source_training_run_id.foreign_keys
    }
    assert "registered_models.id" in {
        foreign_key.target_fullname
        for foreign_key in ModelEvaluation.__table__.c.model_id.foreign_keys
    }
    assert MLTrainingRun.__tablename__ == "ml_training_runs"


def test_multimodal_asset_model_has_tenant_and_validation_fields():
    assert MultimodalAsset.__tablename__ == "multimodal_assets"
    columns = MultimodalAsset.__table__.columns
    assert {"project_id", "owner_id", "modality", "source_reference", "media_type", "sha256", "metadata"}.issubset(columns.keys())
    foreign_keys = {key.target_fullname for key in columns.project_id.foreign_keys}
    assert "workbench_projects.id" in foreign_keys
