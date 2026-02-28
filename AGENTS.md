```markdown
# AGENTS.md - Guidelines for AI Coding Agents

These guidelines outline the principles and rules for development of AI coding agents within this repository. Adherence to these principles is crucial for maintaining code quality, maintainability, and robustness.

## 1. DRY (Don't Repeat Yourself)

*   All functionalities and logic should be encapsulated within separate, well-documented modules and files.
*   Avoid duplicating code snippets or complex algorithms across multiple files.
*   When a task can be accomplished with a single, reusable component, implement it as a module.

## 2. KISS (Keep It Simple, Stupid)

*   Strive for clarity and simplicity in design.
*   Favor simple solutions over complex ones.
*   Avoid unnecessary abstraction; keep the core logic easy to understand.
*   Minimize the complexity of the code base.

## 3. SOLID Principles

*   **Single Responsibility Principle:** Each class or module should have one, and only one, reason to change.
*   **Open/Closed Principle:** The system should be extensible without being modified.
*   **Liskov Substitution Principle:** Subclasses must be substitutable for their base class without altering the correctness of the program.
*   **Interface Segregation Principle:** Clients shouldn't be forced to implement interfaces they don't use.
*   **Dependency Inversion Principle:** High-level modules should not depend on low-level modules.  Instead, they should depend on abstractions.

## 4. YAGNI (You Aren't Gonna Need It)

*   Only implement features that are explicitly required for the current task.
*   Don't introduce functionality that is not currently needed.
*   Defer implementation until the task's requirements are fully understood.

## 5. Code Style & Formatting

*   Follow the established coding style guidelines [Link to Style Guide - e.g., linters/formatters] as defined in the `style.md` file.
*   Consistent indentation and spacing are mandatory.
*   Use descriptive variable and function names.
*   Adhere to the `formatting.md` file for code formatting.

## 6. File Size Limit (180 Lines Max)

*   Each file should not exceed 180 lines of code.
*   Code must be properly formatted for readability.
*   Comments should be concise and explain the *why*, not just the *what*.

## 7. Testing & Coverage

*   All development must be conducted with a focus on thorough unit testing.
*   Unit tests should cover all critical logic and edge cases.
*   Aim for at least 80% test coverage across all modules.
*   Test cases should be clearly documented.

## 8. Implementation Details

*   All algorithmic logic must be clearly expressed and easily understandable.
*   Data structures used must be appropriately chosen for the task.
*   Error handling must be robust and predictable.
*   Utilize appropriate logging to aid in debugging and monitoring.

## 9. Data Management

*   Data should be treated as immutable and serialized when needed for persistence.
*   Version control should be used for all data-related changes.
*   Consider data validation and sanitization to prevent errors.

## 10. Maintainability & Documentation

*   Code should be written with readability in mind.
*   Use docstrings to document functions and modules.
*   Maintain clear and concise comments explaining complex logic.

## 11.  Requirements & Constraints

*   The AGENTS.md file will document the primary functionalities and potential integrations for the AI coding agents.
*   The repository will adhere to established data structures and organization.
*   All code must be compatible with [Specify Version Control System - e.g., Git] and be easily backported.


```