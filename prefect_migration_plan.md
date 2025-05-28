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

> **Phases 3–8 are not strictly sequential; some were completed in parallel or out of order for efficiency.**

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
4. ✅ Structural Refactor
5. ✅ Refactor Pipeline as Prefect Flows
6. ✅ CLI Integration
7. ⬜ Parallelism & Concurrency Controls
8. ⬜ Testing & Error Handling
9. ⬜ Documentation & Final Validation

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

### Phase 3: Structural Refactor

- ✅ Rename `pipeline/` to `flows/` and update all references
- ✅ Rename `steps/` to `tasks/` and update all references
- ✅ Update docstrings and documentation to use new terminology
- ✅ Archive `debug_pipeline.py` and `test_pipeline.py` as `.bak` files
- ✅ Remove or archive the old imperative pipeline, registry, and step registration system
- ✅ All registry and @register_step references removed from tasks. All steps are now pure Prefect tasks.

**Changelog:**
- Project structure now follows Prefect idioms: `flows/` for orchestration, `tasks/` for atomic steps.
- All code, imports, and docstrings updated to match new structure.
- Obsolete debug and registry-based pipeline scripts archived as `.bak`.
- All legacy pipeline/registry code has been archived or removed. Prefect flows are now the only orchestration mechanism.

### Phase 4: Refactor Pipeline as Prefect Flows

- ✅ Create per-file and batch Prefect flows for orchestration
- ✅ Remove all registry/imperative orchestration
- ✅ Ensure all orchestration is handled by Prefect flows
- ✅ Write and run tests for the per-file flow
- ✅ Mark this phase as complete in the migration plan

### Phase 5: CLI Integration

- ✅ Update CLI to use Prefect flows
- ✅ Add CLI options for concurrency, flow selection, etc.
- ✅ Remove any references to old pipeline/registry in CLI
- ✅ Test CLI integration and concurrency options

### Phase 5.5: Refactor Per-File Flow to Orchestrate Each Pipeline Step as a Prefect Task

- ⬜ Refactor the per-file flow so that **each pipeline step is a separate Prefect @task**
- ⬜ Update the per-file flow to **call each step as a task**, passing outputs as needed to enforce dependencies
- ⬜ **Orchestrate parallel and sequential steps within the per-file flow**: launch independent steps in parallel using `.submit()`, and use `.result()` to enforce dependencies for sequential steps
- ⬜ **Apply per-step global concurrency limits to resource-heavy steps (e.g., compression, thumbnail generation, AI analysis, focal length, exposure) using Prefect's `task_run_concurrency` parameter.**
- ⬜ **Document which steps have concurrency limits and their default values in both the config and code.**
- ⬜ **Test that concurrency limits are respected across all files and flows (e.g., only N compressions or AI analyses run at once, regardless of batch size).**
- ⬜ Ensure the **batch flow launches per-file flows** (not monolithic tasks), so each file's steps are visible in the UI
- ⬜ Ensure all step functions have proper docstrings and type annotations
- ⬜ Remove any remaining imperative or monolithic step logic from the per-file flow
- ⬜ Test that the Prefect UI shows each step as a separate task run within the flow
- ⬜ Validate that step dependencies are respected (e.g., AI thumbnail selection waits for AI analysis)
- ⬜ Run integration tests for the new per-file flow
- ⬜ Update documentation and usage notes to reflect the new structure

### Phase 6: Parallelism & Concurrency Controls

- ⬜ Implement per-file parallelism using Prefect `.map()` or `.submit()`
- ⬜ Add concurrency limits and configuration
- ⬜ Test that multiple files are processed in parallel and results are correct

### Phase 7: Testing & Error Handling

- ⬜ Write and run tests for flows and CLI
- ⬜ Add Prefect error handling, retries, etc.
- ⬜ Simulate failures and verify Prefect's error handling and retries

### Phase 8: Documentation & Final Validation

- ⬜ Update docs, usage, and migration notes
- ⬜ Final integration and performance checks

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