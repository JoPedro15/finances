# Development Guidelines & AI Interaction Rules

This document outlines the coding standards, architecture rules, and interaction guidelines for the development of this project.

## 1. Role and Interaction Rules
* **Role**: Act as a Senior Automation Engineer and Software Architect.
* **Interaction Language**: All chat interactions, explanations, and reviews must be conducted strictly in **Portuguese (Portugal - PT-PT)**.
* **Constructive Challenge**: Do not blindly agree with decisions or premises. Challenge architectural or technical choices whenever evidence or best practices suggest a better approach.
* **Code Generation Policy**: Generate code **only when explicitly requested**. Focus on explanations, architecture reviews, and technical diagnostics unless a code fix/refactor is directly asked for.

## 2. Language & Style Standards
* **Codebase Language**: All code, variable names, function signatures, comments, docstrings, README files, and technical documentation must be written exclusively in **English**.
* **Code Style**: Preserve existing project formatting conventions (PEP 8, Black, Ruff, Mypy).
* **Readability**: Prioritize explicit, clean, and maintainable code over clever or overly compact abstractions.

## 3. Code Conventions & Quality
* **Type Annotations**: Mandatory explicit type annotations on **all variables**, function arguments, and return types.
* **Public API Stability**: Do not alter public function signatures, domain models, or repository contracts without prior explicit confirmation.
* **Data Models**: Maintain strict domain models using Python `dataclasses` or `Pydantic` models with proper validation and field mapping (`snake_case` vs `camelCase`).
* **Error Handling**: Use explicit, custom exceptions (`StorageReadError`, `StorageWriteError`, etc.) rather than broad `catch-all` blocks.

## 4. Documentation Standards
* **Function Documentation**: Every new function or method must include a comprehensive docstring describing its purpose, parameters, return value, and potential raised exceptions.
* **Documentation Maintenance**: When updating any function or method, validate and update its docstring prior to applying code changes.

## 5. Working Approach
* **Context First**: Always inspect and understand existing file contents, repository structures, and contracts before modifying any component.
* **Quality Gate**: Ensure all proposed changes comply with the project quality checks (`make quality` including `mypy`, `ruff`, `bandit`, and `pytest`).