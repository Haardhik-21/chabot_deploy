"""Thin wrapper that re-exports compact QA functions.

This keeps backward compatibility while moving heavy logic into small modules.
"""
from qa_core import answer_question_stream
from context import clear_conversation_context

__all__ = ["answer_question_stream", "clear_conversation_context"]

