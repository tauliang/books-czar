from __future__ import annotations

from behave import given, then, when

from backend.config import get_settings


@given("a clean Books Czar workspace")
def step_clean_workspace(context):
    response = context.client.get("/api/books")
    assert response.status_code == 200
    assert response.json() == []


@given('the books folder contains "{file_name}" with')
@given('the books folder contains "{file_name}" with:')
def step_books_folder_contains(context, file_name: str):
    books_dir = get_settings().books_dir
    books_dir.mkdir(parents=True, exist_ok=True)
    (books_dir / file_name).write_text(context.text, encoding="utf-8")


@when("I scan the books folder")
def step_scan_books_folder(context):
    context.response = context.client.post("/api/books/scan-local")
    assert context.response.status_code == 200
    context.scan_result = context.response.json()


@then("the scan should report {created:d} created book")
def step_scan_reports_created(context, created: int):
    assert context.scan_result["created"] == created


@then('the library should contain a book titled "{title}"')
def step_library_contains_title(context, title: str):
    response = context.client.get("/api/books")
    assert response.status_code == 200
    titles = [book["title"] for book in response.json()]
    assert title in titles


@when("I request available LM Studio models")
def step_request_models(context):
    context.response = context.client.get("/api/models")
    assert context.response.status_code == 200
    context.models_result = context.response.json()


@then('the model options should include "{model}"')
def step_model_options_include(context, model: str):
    assert model in context.models_result["models"]


@when('I save settings with chat model "{chat_model}" and embedding model "{embedding_model}"')
def step_save_settings(context, chat_model: str, embedding_model: str):
    context.response = context.client.put(
        "/api/settings",
        json={
            "lmstudio_base_url": "http://127.0.0.1:1234/v1",
            "chat_model": chat_model,
            "embedding_model": embedding_model,
            "chunk_size": 1200,
            "chunk_overlap": 120,
        },
    )
    assert context.response.status_code == 200


@then('settings should use chat model "{chat_model}"')
def step_settings_use_chat_model(context, chat_model: str):
    response = context.client.get("/api/settings")
    assert response.status_code == 200
    assert response.json()["chat_model"] == chat_model


@then('settings should use embedding model "{embedding_model}"')
def step_settings_use_embedding_model(context, embedding_model: str):
    response = context.client.get("/api/settings")
    assert response.status_code == 200
    assert response.json()["embedding_model"] == embedding_model


@when("I index the library")
def step_index_library(context):
    context.response = context.client.post("/api/index", json={"book_ids": None})
    assert context.response.status_code == 200
    context.index_result = context.response.json()
    assert context.index_result["indexed"] >= 1


@when('I ask "{question}"')
def step_ask_question(context, question: str):
    context.response = context.client.post(
        "/api/chat",
        json={"message": question, "top_k": 3, "book_ids": None},
    )
    assert context.response.status_code == 200
    context.chat_result = context.response.json()


@then('the answer should include "{text}"')
def step_answer_should_include(context, text: str):
    assert text in context.chat_result["answer"]


@then('the answer should cite a source titled "{title}"')
def step_answer_should_cite_source(context, title: str):
    source_titles = [source["title"] for source in context.chat_result["sources"]]
    assert title in source_titles


@then("the model prompt should include retrieved excerpts")
def step_prompt_should_include_retrieved_excerpts(context):
    assert "Excerpts:" in context.fake_lmstudio.last_user_prompt
    assert "lower data leakage risk" in context.fake_lmstudio.last_user_prompt
