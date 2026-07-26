from src.skills.models import ExtractedSkill


def extracted(name: str, category: str) -> ExtractedSkill:
    return ExtractedSkill(
        skill=name,
        category=category,
        evidence=(name,),
    )


def test_legacy_fields_remain_available():
    item = extracted("Python", "programming_language")

    assert item.skill == "Python"
    assert item.category == "programming_language"


def test_programming_language_receives_new_dimensions():
    item = extracted("Python", "programming_language")

    assert item.technology == "Python"
    assert item.technology_category == "language"
    assert item.capability == "Programming"


def test_domain_is_separated_from_concrete_technology():
    item = extracted("Machine Learning", "data_ai")

    assert item.technology_category == "domain"
    assert item.capability == "AI and Machine Learning"


def test_kotlin_is_grouped_under_mobile_capability():
    item = extracted("Kotlin", "programming_language")

    assert item.capability == "Mobile Development"


def test_sql_is_not_reported_as_a_general_programming_language():
    item = extracted("SQL", "programming_language")

    assert item.technology_category == "query_language"
    assert item.capability == "Data Storage"
