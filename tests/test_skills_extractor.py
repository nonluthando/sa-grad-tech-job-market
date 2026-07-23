from src.skills.extractor import (
    extract_degree_requirements,
    extract_experience_years,
    extract_job_enrichment,
    extract_skills,
)


def skill_names(text: str) -> set[str]:
    return {skill.skill for skill in extract_skills(text)}


def test_extracts_languages_frameworks_and_cloud():
    names = skill_names(
        "Build Java services with Spring Boot, PostgreSQL, Docker and AWS."
    )
    assert {"Java", "Spring Boot", "PostgreSQL", "Docker", "AWS"} <= names


def test_java_does_not_false_match_javascript():
    names = skill_names("Strong JavaScript and TypeScript experience.")
    assert "JavaScript" in names
    assert "TypeScript" in names
    assert "Java" not in names


def test_extracts_data_and_ai_skills():
    names = skill_names(
        "Python, SQL, machine learning, pandas, TensorFlow and Databricks."
    )
    assert {
        "Python", "SQL", "Machine Learning", "Pandas", "TensorFlow", "Databricks"
    } <= names


def test_extracts_degree_requirement_and_fields():
    required, fields = extract_degree_requirements(
        "A bachelor's degree in Computer Science, Statistics or Mathematics is required."
    )
    assert required is True
    assert {"Computer Science", "Statistics", "Mathematics"} <= set(fields)


def test_extracts_experience_range_once():
    minimum, maximum = extract_experience_years(
        "You need 2-3 years of relevant experience."
    )
    assert minimum == 2
    assert maximum == 3


def test_extracts_plus_years():
    minimum, maximum = extract_experience_years(
        "At least 3+ years' experience is expected."
    )
    assert minimum == 3
    assert maximum is None


def test_job_enrichment_reports_missing_description():
    result = extract_job_enrichment("Software Engineer", "")
    assert "missing_description" in result.extraction_warnings
