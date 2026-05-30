Feature: Books Czar local RAG workflows
  Books Czar should let a user discover local books, choose LM Studio models,
  index content, and ask questions with retrieved source context.

  Scenario: Scan the local books folder
    Given a clean Books Czar workspace
    And the books folder contains "strategy.txt" with:
      """
      Local AI strategy depends on a private RAG library and careful source citation.
      """
    When I scan the books folder
    Then the scan should report 1 created book
    And the library should contain a book titled "Strategy"

  Scenario: Pick LM Studio model options
    Given a clean Books Czar workspace
    When I request available LM Studio models
    Then the model options should include "chat-test"
    And the model options should include "text-embedding-test"
    When I save settings with chat model "chat-test" and embedding model "text-embedding-test"
    Then settings should use chat model "chat-test"
    And settings should use embedding model "text-embedding-test"

  Scenario: Ask a question over indexed local content
    Given a clean Books Czar workspace
    And the books folder contains "risk-strategy.txt" with:
      """
      The CDAO should measure lower data leakage risk and faster strategy research.
      """
    When I scan the books folder
    And I index the library
    And I ask "What risk should the CDAO measure?"
    Then the answer should include "RAG answer"
    And the answer should cite a source titled "Risk Strategy"
    And the model prompt should include retrieved excerpts
