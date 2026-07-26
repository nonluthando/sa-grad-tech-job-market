"""Semantic dimensions layered over the legacy skill taxonomy."""

from __future__ import annotations


CATEGORY_DIMENSIONS: dict[str, tuple[str, str]] = {
    "programming_language": ("language", "Programming"),
    "framework": ("framework", "Application Development"),
    "data_ai": ("domain_or_data_tool", "Data and AI"),
    "cloud": ("cloud_platform", "Cloud"),
    "database": ("database_or_storage", "Data Storage"),
    "devops": ("devops_tool", "DevOps and Platform Engineering"),
    "architecture": ("architecture_or_messaging", "Backend and Architecture"),
    "testing": ("testing_tool_or_practice", "Quality Engineering"),
    "analytics_tool": ("analytics_or_bi_tool", "Analytics and BI"),
    "enterprise_platform": ("enterprise_platform", "Enterprise Technology"),
}


SKILL_DIMENSION_OVERRIDES: dict[str, tuple[str, str]] = {
    "SQL": ("query_language", "Data Storage"),
    "Bash": ("scripting_language", "DevOps and Platform Engineering"),
    "Kotlin": ("language", "Mobile Development"),
    "Swift": ("language", "Mobile Development"),
    "React": ("frontend_framework", "Frontend Development"),
    "Angular": ("frontend_framework", "Frontend Development"),
    "Vue.js": ("frontend_framework", "Frontend Development"),
    "Next.js": ("frontend_framework", "Frontend Development"),
    "Machine Learning": ("domain", "AI and Machine Learning"),
    "Artificial Intelligence": ("domain", "AI and Machine Learning"),
    "Generative AI": ("domain", "AI and Machine Learning"),
    "Large Language Models": ("domain", "AI and Machine Learning"),
    "Natural Language Processing": ("domain", "AI and Machine Learning"),
    "Computer Vision": ("domain", "AI and Machine Learning"),
    "Data Science": ("domain", "Data and Analytics"),
    "Data Engineering": ("domain", "Data Engineering"),
    "ETL": ("data_practice", "Data Engineering"),
    "Apache Spark": ("data_processing_platform", "Data Engineering"),
    "Pandas": ("data_library", "Data and Analytics"),
    "NumPy": ("data_library", "Data and Analytics"),
    "scikit-learn": ("machine_learning_library", "AI and Machine Learning"),
    "TensorFlow": ("machine_learning_framework", "AI and Machine Learning"),
    "PyTorch": ("machine_learning_framework", "AI and Machine Learning"),
    "Databricks": ("data_platform", "Data Engineering"),
    "Snowflake": ("data_platform", "Data Engineering"),
    "dbt": ("data_transformation_tool", "Data Engineering"),
    "BigQuery": ("cloud_data_warehouse", "Data Engineering"),
    "Git": ("version_control", "Software Delivery"),
    "Kafka": ("messaging_platform", "Backend and Architecture"),
    "RabbitMQ": ("messaging_platform", "Backend and Architecture"),
    "REST APIs": ("backend_practice", "Backend and Architecture"),
    "Microservices": ("architecture_pattern", "Backend and Architecture"),
    "Event-driven Architecture": ("architecture_pattern", "Backend and Architecture"),
    "Linux": ("operating_system", "DevOps and Platform Engineering"),
    "CI/CD": ("delivery_practice", "Software Delivery"),
    "Cloud Computing": ("domain", "Cloud"),
}


def classify_skill_dimensions(
    skill: str,
    legacy_category: str,
) -> tuple[str, str]:
    """Return `(technology_category, capability)` for an extracted item."""

    override = SKILL_DIMENSION_OVERRIDES.get(skill)
    if override is not None:
        return override

    return CATEGORY_DIMENSIONS.get(
        legacy_category,
        ("other", "Other"),
    )
