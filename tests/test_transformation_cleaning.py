from src.transformation.cleaning import (
    html_to_text,
    join_named_values,
    normalized_key,
)


def test_html_to_text_decodes_escaped_html_and_removes_hidden_content() -> None:
    value = (
        "&lt;p&gt;Build &amp;amp; test&lt;/p&gt;"
        "&lt;script&gt;do not keep&lt;/script&gt;"
        "&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;li&gt;SQL&lt;/li&gt;&lt;/ul&gt;"
    )

    assert html_to_text(value) == "Build & test Python SQL"


def test_normalized_key_preserves_technology_symbols() -> None:
    assert normalized_key("  C# / C++ Developer  ") == "c# c++ developer"


def test_join_named_values_removes_duplicate_names() -> None:
    values = [
        {"name": "Engineering"},
        {"name": "engineering"},
        {"name": "Data"},
        {"other": "ignored"},
    ]

    assert join_named_values(values) == "Engineering, Data"
