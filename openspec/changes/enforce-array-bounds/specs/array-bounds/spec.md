# Spec Delta

## Purpose

Defines how the VM sizes declared arrays and enforces index bounds, so that array declarations and accesses behave consistently with their declared length instead of silently degrading to sparse storage.

## ADDED Requirements

### Requirement: Array declarations with a non-negative integer size create fixed-length storage

When a variable is declared with an array size that evaluates to a non-negative integer, the VM SHALL create a fixed-length list of that length, initialised to zero. A size of `0` SHALL produce an empty list.

#### Scenario: Positive size creates a zero-filled list

- **WHEN** the program declares `int buffer[10];`
- **THEN** `buffer` is a list of length 10 whose elements are all `0`

#### Scenario: Zero size creates an empty list

- **WHEN** the program declares `int buffer[0];`
- **THEN** `buffer` is an empty list, not a dictionary

### Requirement: Negative array sizes are rejected

When a variable is declared with an array size that evaluates to a negative integer, the VM SHALL raise a runtime error and the CLI SHALL exit with code 1.

#### Scenario: Negative size fails

- **WHEN** the program declares `int buffer[-1];`
- **THEN** the VM raises a runtime error identifying the invalid array size
- **AND** the CLI exits with code 1

### Requirement: Array reads are bounds-checked

Reading an element of a fixed-length array SHALL raise a runtime error when the index is outside `[0, length)`. The VM SHALL NOT return `0` for an out-of-range index.

#### Scenario: In-range read succeeds

- **WHEN** the program reads `buffer[3]` from a list of length 10
- **THEN** the VM returns the stored element

#### Scenario: Out-of-range read fails

- **WHEN** the program reads `buffer[10]` from a list of length 10
- **THEN** the VM raises a runtime error identifying the out-of-range index
- **AND** the CLI exits with code 1

### Requirement: Array writes are bounds-checked

Writing an element of a fixed-length array SHALL raise a runtime error when the index is outside `[0, length)`. The VM SHALL NOT grow the list to accommodate the index.

#### Scenario: In-range write succeeds

- **WHEN** the program assigns `buffer[3] = 7` on a list of length 10
- **THEN** the element at index 3 becomes `7`

#### Scenario: Out-of-range write fails

- **WHEN** the program assigns `buffer[10] = 7` on a list of length 10
- **THEN** the VM raises a runtime error identifying the out-of-range index
- **AND** the list length remains 10

### Requirement: Non-integer array sizes keep sparse storage

When an array size cannot be evaluated to an integer, the VM SHALL keep the existing sparse dictionary storage so that lenient pseudo-code with an unknown size still runs.

#### Scenario: Unknown size falls back to sparse storage

- **WHEN** the program declares an array whose size expression does not evaluate to an integer
- **THEN** the VM stores the array as a sparse mapping and does not raise an error
