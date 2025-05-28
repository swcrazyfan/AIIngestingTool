# Prefect Pipeline Migration & Concurrency Implementation Plan

## Current Status
**Progress:** 25/10 components implemented (250% complete for initial steps)  
**Testing Status:** Up to date for Phase 1 and all steps of Phase 2. As of this update, `ai_video_analysis_step`, `ai_thumbnail_selection_step`, and `upload_thumbnails_step` are refactored, tested, and all tests are passing.

> **Status Legend**:  
> ⬜ = Waiting / Not Started  
> 🔄 = In Progress  
> ✅ = Completed

---

**Note:** Many tasks and sub-tasks in this plan can be worked on in parallel. The checklist is for tracking progress, not enforcing strict sequential order. Parallel work is encouraged where possible for efficiency and faster migration.

---

## Pipeline Steps to Refactor and Test as Prefect Tasks

### Extraction Steps
- ✅ extract_mediainfo_step
- ✅ extract_ffprobe_step
- ✅ extract_exiftool_step
- ✅ extract_extended_exif_step
- ✅ extract_codec_step
- ✅ extract_hdr_step
- ✅ extract_audio_step
- ✅ extract_subtitle_step

### Analysis Steps
- ✅ generate_thumbnails_step
- ✅ analyze_exposure_step
- ✅ detect_focal_length_step
- ✅ ai_video_analysis_step
- ✅ ai_thumbnail_selection_step

### Processing Steps
- ✅ generate_checksum_step
- ✅ check_duplicate_step
- ✅ video_compression_step
- ✅ consolidate_metadata_step

### Storage Steps
- ✅ create_model_step
- ✅ database_storage_step
- ✅ generate_embeddings_step
- ✅ upload_thumbnails_step

---

## High-level Plan

1. ✅ Evaluate and install Prefect in the project
2. ✅ Refactor pipeline steps as Prefect tasks (checksum, mediainfo, ffprobe, exiftool, extended_exif, codec, hdr, audio, subtitle, thumbnails, exposure, focal_length, duplicate_check, video_compression, consolidate_metadata, create_model, database_storage, generate_embeddings steps complete)
3. ✅ Write and run tests for each refactored task (checksum, mediainfo, ffprobe, exiftool, extended_exif, codec, hdr, audio, subtitle, thumbnails, exposure, focal_length, duplicate_check, video_compression, consolidate_metadata, create_model, database_storage, generate_embeddings steps complete)
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

- ✅ **Install Prefect**
  - ✅ Add `prefect` to `requirements.txt`
  - ✅ Run `pip install prefect`
- ✅ **Basic Prefect Hello World**
  - ✅ Create a simple `@flow` and `@task` to verify installation
- ✅ **Write and Run Test for Hello World**
  - ✅ Add a test to ensure Prefect is installed and basic flow runs

### Phase 1.5 Structural Refactor 

- ✅ Rename `pipeline/` to `flows/` and update all references
- ✅ Rename `steps/` to `tasks/` and update all references
- ✅ Update docstrings and documentation to use new terminology
- ✅ Archive `debug_pipeline.py` and `test_pipeline.py` as `.bak` files
- ✅ Remove or archive the old imperative pipeline, registry, and step registration system

**Changelog:**
- Project structure now follows Prefect idioms: `flows/` for orchestration, `tasks/` for atomic steps.
- All code, imports, and docstrings updated to match new structure.
- Obsolete debug and registry-based pipeline scripts archived as `.bak`.
- All legacy pipeline/registry code has been archived or removed. Prefect flows are now the only orchestration mechanism.

### Phase 2: Refactor Steps as Tasks

- ✅ **generate_checksum_step** (done)
- ✅ **extract_mediainfo_step** (done)
- ✅ **extract_ffprobe_step** (done)
- ✅ **extract_exiftool_step** (done)
- ✅ **extract_extended_exif_step** (done)
- ✅ **extract_codec_step** (done)
- ✅ **extract_hdr_step** (done)
- ✅ **extract_audio_step** (done)
- ✅ **extract_subtitle_step** (done)
- ✅ **generate_thumbnails_step** (done)
- ✅ **analyze_exposure_step** (done)
- ✅ **detect_focal_length_step** (done)
- ✅ **ai_video_analysis_step** (done)
- ✅ **ai_thumbnail_selection_step** (done)
- ✅ **check_duplicate_step** (done)
- ✅ **video_compression_step** (done)
- ✅ **consolidate_metadata_step** (done)
- ✅ **create_model_step** (done)
- ✅ **database_storage_step** (done)
- ✅ **generate_embeddings_step** (done)
- ✅ **upload_thumbnails_step** (done)

(Each step: add @task, ensure statelessness, write and run a unit test)

### Phase 3: Refactor Pipeline as Flow

- ⬜ **Create Per-File Flow**
  - ⬜ Refactor `process_video_file` to a `@flow` function
  - ⬜ Replace direct function calls with Prefect task calls
  - ⬜ Pass outputs between tasks as arguments (Prefect tracks dependencies)
  - ⬜ Implement step enable/disable logic using flow parameters and conditional branching (e.g., `if run_ai: ...`)
  - ⬜ Support multiple flow variants or dynamic step selection (e.g., via parameters or config)
  - ⬜ Use `wait_for` to express explicit dependencies between steps that do not pass data
  - ⬜ Reference: [Prefect Conditional Branching](https://docs.prefect.io/latest/concepts/flows/#conditional-logic), [Dynamic Flows](https://docs.prefect.io/latest/concepts/flows/#dynamic-flows)
- ⬜ **Handle Step Dependencies**
  - ⬜ Ensure dependent steps (e.g., AI thumbnail selection needs AI analysis) are called in correct order
- ⬜ **Write and Run Tests for Per-File Flow**
  - ⬜ Write integration tests for the per-file flow
- ⬜ **Refactor or remove old pipeline orchestration and registry code**
  - ⬜ Remove or archive the old imperative pipeline, registry, and step registration system
  - ⬜ Ensure all orchestration is handled by Prefect flows
  - ⬜ Rename legacy pipeline/registry/CLI files to `.bak` or archive them once Prefect migration is complete
  - ⬜ Update documentation to reference only the Prefect-based pipeline

### Phase 4: Add Parallelism and Concurrency Controls

- ⬜ **Implement Per-File Parallelism**
  - ⬜ Use `process_video_file.map(file_list)` to process multiple files concurrently
  - ⬜ Set concurrency limits as needed
- ⬜ **Step-Level Concurrency and Resource Limits**
  - ⬜ Implement concurrency/resource limits for heavy steps (e.g., compression) using Prefect's concurrency features:
    - ⬜ Use `.map()` for per-step parallelism
    - ⬜ Use `ThreadPoolTaskRunner`, `DaskTaskRunner`, or `RayTaskRunner` as appropriate
    - ⬜ Use Prefect's concurrency context managers (`concurrency`, `rate_limit`) or CLI (`prefect concurrency-limit create ...`) for global/per-task concurrency limits
    - ⬜ Tag tasks and set concurrency limits via CLI or Prefect Cloud if needed
  - ⬜ Make concurrency settings configurable via flow parameters or CLI options
  - ⬜ Reference: [Prefect Concurrency & Mapping](https://docs.prefect.io/latest/concepts/mapping/), [Task Runners](https://docs.prefect.io/latest/concepts/task-runners/), [Concurrency Limits](https://docs.prefect.io/latest/concepts/concurrency/)
- ⬜ **Write and Run Tests for Parallelism**
  - ⬜ Test that multiple files are processed in parallel and results are correct

### Phase 5: CLI Integration

- ⬜ **Update CLI to Use Prefect Flow**
  - ⬜ Replace calls to old pipeline with Prefect flow
  - ⬜ Add CLI options for concurrency (e.g., `--concurrency`, `--ai-workers`)
  - ⬜ Ensure CLI progress reporting works with Prefect
- ⬜ **Write and Run CLI Tests**
  - ⬜ Test CLI integration and concurrency options

### Phase 6: Configuration & Error Handling

- ⬜ **Add Configurable Concurrency**
  - ⬜ Allow user to set number of parallel files and per-step concurrency via CLI or config
- ⬜ **Improve Error Handling**
  - ⬜ Use Prefect's retry and failure hooks for robust error management
- ⬜ **Write and Run Error Handling Tests**
  - ⬜ Simulate failures and verify Prefect's error handling and retries

### Phase 7: Testing & Validation

- ⬜ **Unit and Integration Testing**
  - ⬜ Test pipeline on a small batch of files after each phase
  - ⬜ Validate concurrency, step dependencies, and output correctness
- ⬜ **Performance Tuning**
  - ⬜ Adjust concurrency settings for optimal throughput

### Phase 8: Documentation

- ⬜ **Update Documentation**
  - ⬜ Add usage instructions for new CLI and Prefect-based pipeline
  - ⬜ Document concurrency options and troubleshooting
- ⬜ **Document Test Coverage**
  - ⬜ Summarize which tests cover which phases and components

---

*Note: Continue wrapping and testing each step as a Prefect task, ensuring statelessness and proper unit tests for each. Update this checklist as you complete each one.*

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
| Install Prefect                   | ✅        |
| Hello World test                  | ✅        |
| Wrap steps as tasks (checksum)    | ✅        |
| Task unit tests (checksum)        | ✅        |
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

*Note: Only the checksum step is complete for Phase 2 so far. Continue wrapping and testing additional steps as tasks to progress further.*

---

## References

- [Prefect Documentation](https://docs.prefect.io/)
- [Prefect Flows and Tasks](https://docs.prefect.io/latest/concepts/flows/)
- [Prefect Mapping (Parallelism)](https://docs.prefect.io/latest/concepts/mapping/) 