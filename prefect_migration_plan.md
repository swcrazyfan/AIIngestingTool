# Prefect Pipeline Migration & Concurrency Implementation Plan

## Current Status
**Progress:** 0/10 components implemented (0% complete)  
**Testing Status:** Not started

---

## High-level Plan

1. ⬜ Evaluate and install Prefect in the project
2. ⬜ Refactor pipeline steps as Prefect tasks
3. ⬜ Write and run tests for each refactored task
4. ⬜ Refactor per-file pipeline as a Prefect flow
5. ⬜ Write and run tests for the per-file flow
6. ⬜ Implement per-file parallelism using Prefect `.map()`
7. ⬜ Write and run tests for parallel execution
8. ⬜ Add step-level concurrency for heavy steps (compression, AI)
9. ⬜ Integrate Prefect flow with CLI
10. ⬜ Add configuration for concurrency (CLI options)
11. ⬜ Test, debug, and document the new pipeline after each phase

---

## Implementation Phases

> **Status Legend**:  
> ⬜ = Waiting / Not Started  
> 🔄 = In Progress  
> ✅ = Completed

### Phase 1: Prefect Setup

- ⬜ **Install Prefect**
  - Add `prefect` to `requirements.txt`
  - Run `pip install prefect`
- ⬜ **Basic Prefect Hello World**
  - Create a simple `@flow` and `@task` to verify installation
- ⬜ **Write and Run Test for Hello World**
  - Add a test to ensure Prefect is installed and basic flow runs

### Phase 2: Refactor Steps as Tasks

- ⬜ **Wrap Each Pipeline Step**
  - Add `@task` decorator to each step function (e.g., `extract_mediainfo_step`, `ai_video_analysis_step`)
  - Ensure all step functions are importable and stateless where possible
- ⬜ **Write and Run Tests for Each Task**
  - Write unit tests for each refactored task to verify correctness

### Phase 3: Refactor Pipeline as Flow

- ⬜ **Create Per-File Flow**
  - Refactor `process_video_file` to a `@flow` function
  - Replace direct function calls with Prefect task calls
  - Pass outputs between tasks as arguments (Prefect tracks dependencies)
- ⬜ **Handle Step Dependencies**
  - Ensure dependent steps (e.g., AI thumbnail selection needs AI analysis) are called in correct order
- ⬜ **Write and Run Tests for Per-File Flow**
  - Write integration tests for the per-file flow

### Phase 4: Add Parallelism

- ⬜ **Implement Per-File Parallelism**
  - Use `process_video_file.map(file_list)` to process multiple files concurrently
  - Set concurrency limits as needed
- ⬜ **Step-Level Concurrency (Optional)**
  - For steps like metadata extraction, use Prefect's built-in parallelism or `wait_for` to run in parallel within a file
- ⬜ **Write and Run Tests for Parallelism**
  - Test that multiple files are processed in parallel and results are correct

### Phase 5: CLI Integration

- ⬜ **Update CLI to Use Prefect Flow**
  - Replace calls to old pipeline with Prefect flow
  - Add CLI options for concurrency (e.g., `--concurrency`, `--ai-workers`)
  - Ensure CLI progress reporting works with Prefect
- ⬜ **Write and Run CLI Tests**
  - Test CLI integration and concurrency options

### Phase 6: Configuration & Error Handling

- ⬜ **Add Configurable Concurrency**
  - Allow user to set number of parallel files and per-step concurrency via CLI or config
- ⬜ **Improve Error Handling**
  - Use Prefect's retry and failure hooks for robust error management
- ⬜ **Write and Run Error Handling Tests**
  - Simulate failures and verify Prefect's error handling and retries

### Phase 7: Testing & Validation

- ⬜ **Unit and Integration Testing**
  - Test pipeline on a small batch of files after each phase
  - Validate concurrency, step dependencies, and output correctness
- ⬜ **Performance Tuning**
  - Adjust concurrency settings for optimal throughput

### Phase 8: Documentation

- ⬜ **Update Documentation**
  - Add usage instructions for new CLI and Prefect-based pipeline
  - Document concurrency options and troubleshooting
- ⬜ **Document Test Coverage**
  - Summarize which tests cover which phases and components

---

## Detailed Component Structure

### Example: Refactored Step as Prefect Task

```python
from prefect import task

@task
def extract_mediainfo_step(data):
    # ... existing logic ...
    return mediainfo_data
```

### Example: Per-File Flow

```python
from prefect import flow

@flow
def process_video_file(file_path):
    data = {'file_path': file_path}
    mediainfo = extract_mediainfo_step(data)
    ffprobe = extract_ffprobe_step(data)
    # ... other steps ...
    compressed = compress_video_step(data)
    ai_result = ai_video_analysis_step(compressed)
    ai_thumbnails = ai_thumbnail_selection_step(ai_result)
    # ... etc.
```

### Example: Parallel Processing of Files

```python
@flow
def main(file_list):
    process_video_file.map(file_list)
```

### CLI Integration

- Add CLI option: `--concurrency N` (default: 2)
- CLI calls `main(file_list, concurrency=N)`

---

## Implementation Guidelines

- **Keep step logic unchanged**; only wrap with `@task`
- **Use Prefect's `.map()`** for per-file parallelism
- **Use Prefect's dependency tracking** for step order
- **Leverage Prefect's error handling and retries** for robustness
- **Write and run tests after each phase and for each new/refactored component**
- **Document all changes and new usage patterns**

---

## Integration Testing

After implementing each component or phase:
1. Write and run tests for the new/refactored code
2. Verify pipeline runs for a single file
3. Verify multiple files are processed in parallel
4. Validate step dependencies (e.g., AI thumbnails wait for AI analysis)
5. Test error handling and retries
6. Confirm CLI options work as expected

---

## Progress Tracker

| Component                        | Status   |
|-----------------------------------|----------|
| Install Prefect                   | ⬜        |
| Hello World test                  | ⬜        |
| Wrap steps as tasks               | ⬜        |
| Task unit tests                   | ⬜        |
| Refactor pipeline as flow         | ⬜        |
| Flow integration tests            | ⬜        |
| Implement per-file parallelism    | ⬜        |
| Parallelism tests                 | ⬜        |
| CLI integration                   | ⬜        |
| CLI tests                         | ⬜        |
| Configurable concurrency          | ⬜        |
| Error handling                    | ⬜        |
| Error handling tests              | ⬜        |
| Testing & documentation           | ⬜        |

---

## References

- [Prefect Documentation](https://docs.prefect.io/)
- [Prefect Flows and Tasks](https://docs.prefect.io/latest/concepts/flows/)
- [Prefect Mapping (Parallelism)](https://docs.prefect.io/latest/concepts/mapping/) 