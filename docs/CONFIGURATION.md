# Configuration Guide

This document summarizes the main environment variables supported by the project.
Values are loaded by `src/config/defaults.py` through `get_config()`.

## Core

- `MODEL_TYPE`: Provider name (ollama, openai, groq, deepseek, anthropic).
- `SELECTED_MODEL`: Optional `provider:model` override.

## Context

- `CONTEXT_LIMITED_SIZE`: Max chars for short context windows.
- `CONTEXT_STANDARD_SIZE`: Max chars for larger context windows.
- `CONTEXT_SAVEPOINT_INTERVAL`: Savepoint interval in sections.
- `CONTEXT_MAX_ACCUMULATION`: Max accumulated context size before trimming.
- `CONTEXT_GLOBAL_LIMIT`: Max chars for global summary context.
- `CONTEXT_ENABLE_MICRO_SUMMARIES`: Enable micro summaries (true/false).
- `CONTEXT_MICRO_SUMMARY_INTERVAL`: Interval for micro summaries in sections.
- `CONTEXT_REQUIRE_DYNAMIC_ANALYZERS`: If true, fails fast when dynamic analyzers are missing.

## Summary Limits

These values centralize limits used in savepoints, chapter summaries, and micro summaries.

- `SUMMARY_SAVEPOINT_SECTION_MAX_CHARS`
- `SUMMARY_SAVEPOINT_MAX_CHARS`
- `SUMMARY_SAVEPOINT_MIN_CHARS`
- `SUMMARY_SAVEPOINT_EMERGENCY_SECTION_CHARS`
- `SUMMARY_CHAPTER_MAX_CHARS`
- `SUMMARY_CHAPTER_MIN_CHARS`
- `SUMMARY_CHAPTER_SEGMENT_LENGTH`
- `SUMMARY_CHAPTER_MAX_SEGMENTS`
- `SUMMARY_CHAPTER_OPTIMIZED_MAX_CHARS`
- `SUMMARY_CHAPTER_OPTIMIZED_PART_CHARS`
- `SUMMARY_CHAPTER_OPTIMIZED_MIDDLE_CHARS`
- `SUMMARY_INTELLIGENT_CHAPTER_MAX_CHARS`
- `SUMMARY_MICRO_PROMPT_MAX_CHARS`
- `SUMMARY_MICRO_MIN_CHARS`
- `SUMMARY_MICRO_BASE_MAX_WORDS`
- `SUMMARY_GLOBAL_CONDENSE_THRESHOLD_CHARS`
- `SUMMARY_GLOBAL_MAX_CHARS`
- `SUMMARY_GLOBAL_TRUNCATE_CHARS`
- `SUMMARY_CURRENT_CHAPTER_CONTEXT_MAX_CHARS`
- `SUMMARY_SECTION_MIN_CHARS`

## Retry and Rate Limit

- `RETRY_MAX_ATTEMPTS`
- `RETRY_TIMEOUT`
- `RETRY_BASE_DELAY`
- `RETRY_MAX_DELAY`
- `RETRY_BACKOFF_STRATEGY`
- `RETRY_JITTER_ENABLED`
- `RATE_LIMIT_DEFAULT_DELAY`
- `RATE_LIMIT_OPENAI_DELAY`
- `RATE_LIMIT_GROQ_DELAY`
- `RATE_LIMIT_DEEPSEEK_DELAY`
- `RATE_LIMIT_ANTHROPIC_DELAY`
- `RATE_LIMIT_OLLAMA_DELAY`

## Few-shot Learning

- `USE_FEW_SHOT_LEARNING`
- `EXAMPLE_QUALITY_THRESHOLD`
- `MAX_EXAMPLES_PER_PROMPT`
- `EXAMPLES_STORAGE_PATH`
- `FEW_SHOT_AUTO_SAVE`

## Streaming

- `STREAMING_WORD_BUFFER_SIZE`
- `STREAMING_WORD_DELIMITERS`

## Logging

- `LOG_LEVEL`
- `LOG_FORMAT` (pretty or json)
- `LOG_FILE_PATH`
- `LOG_ROTATION_SIZE`
