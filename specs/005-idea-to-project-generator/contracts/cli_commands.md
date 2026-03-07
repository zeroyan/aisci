# CLI Command Contracts: Idea-to-Project Generator

**Feature**: 005-idea-to-project-generator
**Date**: 2026-03-07
**Contract Type**: Command-line interface

## Overview

This document defines the CLI command interface for the Idea-to-Project Generator. All commands follow the existing `cli.py` structure and use Typer for argument parsing.

## Command: `project generate`

### Signature

```bash
python cli.py project generate <idea> [OPTIONS]
```

### Description

Generate a complete project package (ResearchSpec + ExperimentPlan + Evidence Report) from a natural language research idea.

### Arguments

**Positional**:
- `idea` (str, required): Natural language research idea (1-1000 characters)
  - Can be quoted string or read from stdin with `-`
  - Example: `"I want to improve Transformer speed on long texts"`

### Options

**Basic Options**:
- `--config`, `-c` (str, optional): Path to YAML config file
  - Default: `configs/default.yaml`
  - Example: `--config configs/custom.yaml`

- `--project-id`, `-p` (str, optional): Custom project ID
  - Default: Auto-generated `proj_<timestamp>_<hash>`
  - Example: `--project-id my_transformer_project`

**Constraint Options**:
- `--budget` (float, optional): Maximum budget in USD
  - Default: `100.0`
  - Example: `--budget 50.0`

- `--max-time` (str, optional): Maximum time constraint
  - Default: `"24h"`
  - Format: `<number><unit>` where unit is `h` (hours) or `d` (days)
  - Example: `--max-time 3d`

- `--max-iterations` (int, optional): Maximum experiment iterations
  - Default: `10`
  - Example: `--max-iterations 20`

- `--compute` (str, optional): Compute resource type
  - Default: `"cpu"`
  - Choices: `cpu`, `gpu`, `tpu`
  - Example: `--compute gpu`

**Search Options**:
- `--skip-search` (bool, flag): Skip evidence search, use cached results only
  - Default: `False`
  - Example: `--skip-search`

- `--force-refresh` (bool, flag): Force refresh cached evidence
  - Default: `False`
  - Example: `--force-refresh`

- `--max-papers` (int, optional): Maximum papers to retrieve
  - Default: `10`
  - Range: `1-20`
  - Example: `--max-papers 15`

- `--max-repos` (int, optional): Maximum code repositories to retrieve
  - Default: `5`
  - Range: `1-10`
  - Example: `--max-repos 8`

**Interaction Options**:
- `--interactive`, `-i` (bool, flag): Enable interactive clarification mode
  - Default: `True` (always interactive unless `--no-interactive`)
  - Example: `--interactive`

- `--no-interactive` (bool, flag): Disable interactive mode, use defaults
  - Default: `False`
  - Example: `--no-interactive`

- `--max-questions` (int, optional): Maximum clarifying questions
  - Default: `5`
  - Range: `1-10`
  - Example: `--max-questions 3`

**Proposal Options**:
- `--num-proposals` (int, optional): Number of candidate proposals to generate
  - Default: `3`
  - Range: `1-5`
  - Example: `--num-proposals 2`

- `--auto-select` (str, optional): Auto-select proposal without user input
  - Default: `None` (user selects)
  - Choices: `conservative`, `balanced`, `aggressive`
  - Example: `--auto-select balanced`

**Output Options**:
- `--output-dir`, `-o` (str, optional): Custom output directory
  - Default: `runs/<project_id>/`
  - Example: `--output-dir /path/to/output`

- `--format` (str, optional): Output format for evidence report
  - Default: `"markdown"`
  - Choices: `markdown`, `json`, `both`
  - Example: `--format both`

### Output

**Success (Exit Code 0)**:
```
🔍 Analyzing idea...
  ✓ Parsed idea type: performance_improvement
  ✓ Extracted entities: task=long_text_processing, model=Transformer

🔍 Searching for evidence...
  ✓ Found 8 papers from arXiv
  ✓ Found 5 code repositories from GitHub
  ✓ Extracted 3 baseline methods

❓ Clarifying questions (2/5):
  Q1: What metric do you want to optimize?
    1. 推理速度
    2. 准确率
    3. 内存占用
  > 1

  Q2: What is your target dataset?
    1. WikiText-103
    2. BookCorpus
    3. Custom dataset
  > 1

📋 Generating proposals...
  ✓ Generated 3 candidate proposals

Please select a proposal:
  1. Conservative: Replicate FlashAttention with small improvements
  2. Balanced: Combine FlashAttention + Sparse Attention
  3. Aggressive: Explore novel attention mechanism
> 2

✅ Project generated successfully!
  Project ID: proj_20260307_a3f8b2c1
  Location: runs/proj_20260307_a3f8b2c1/
  Files:
    - spec/research_spec.json
    - plan/experiment_plan.json
    - knowledge/evidence_report.md

Next steps:
  python cli.py run start proj_20260307_a3f8b2c1
```

**Error Cases**:

1. **Invalid idea (Exit Code 1)**:
```
Error: Idea must be 1-1000 characters
Provided: 0 characters
```

2. **Evidence search failed (Exit Code 1)**:
```
Error: Failed to search for evidence
Reason: API rate limit exceeded
Suggestion: Try again in 60 seconds or use --skip-search with cached results
```

3. **No clarification answers (Exit Code 1)**:
```
Error: Required clarification questions not answered
Missing: metric, baseline
Suggestion: Run with --interactive or provide --no-interactive to use defaults
```

4. **Invalid constraints (Exit Code 1)**:
```
Error: Contradictory constraints detected
Issue: Target accuracy 99% with budget $5 in 1 hour is infeasible
Suggestion: Adjust constraints or use --auto-select balanced
```

### Examples

**Basic usage**:
```bash
python cli.py project generate "I want to improve Transformer speed on long texts"
```

**With constraints**:
```bash
python cli.py project generate "Improve model accuracy" \
  --budget 50 \
  --max-time 3d \
  --compute gpu
```

**Non-interactive mode**:
```bash
python cli.py project generate "Optimize inference latency" \
  --no-interactive \
  --auto-select balanced
```

**Force refresh evidence**:
```bash
python cli.py project generate "Reduce memory usage" \
  --force-refresh \
  --max-papers 15
```

**Custom output location**:
```bash
python cli.py project generate "Improve training speed" \
  --output-dir /path/to/my/project \
  --format both
```

**Read idea from file**:
```bash
cat idea.txt | python cli.py project generate -
```

---

## Command: `project list`

### Signature

```bash
python cli.py project list [OPTIONS]
```

### Description

List all generated projects with their status.

### Options

- `--status` (str, optional): Filter by status
  - Choices: `draft`, `ready`, `running`, `completed`, `failed`
  - Example: `--status ready`

- `--sort-by` (str, optional): Sort order
  - Default: `"created_at"`
  - Choices: `created_at`, `project_id`, `status`
  - Example: `--sort-by status`

### Output

```
Generated Projects:

ID                        Status    Created              Idea
proj_20260307_a3f8b2c1   ready     2026-03-07 10:00:00  Improve Transformer speed...
proj_20260306_x7y9z2     running   2026-03-06 15:30:00  Optimize inference latency...
proj_20260305_m4n5p6     completed 2026-03-05 09:15:00  Reduce memory usage...

Total: 3 projects
```

---

## Command: `project show`

### Signature

```bash
python cli.py project show <project_id> [OPTIONS]
```

### Description

Show detailed information about a generated project.

### Arguments

- `project_id` (str, required): Project ID to display

### Options

- `--format` (str, optional): Output format
  - Default: `"text"`
  - Choices: `text`, `json`, `yaml`
  - Example: `--format json`

### Output

```
Project: proj_20260307_a3f8b2c1

Idea: I want to improve Transformer speed on long texts
Type: performance_improvement
Status: ready

Constraints:
  Budget: $100.00
  Max Time: 24h
  Max Iterations: 10
  Compute: cpu

Evidence:
  Papers: 8
  Code Repos: 5
  Baselines: 3

Selected Proposal: Balanced
  Approach: Combine FlashAttention + Sparse Attention
  Expected Metrics:
    - speed: 1.5x faster than baseline
    - accuracy: 0.95
  Estimated Cost: $45.00
  Estimated Time: 3-5 days

Files:
  - runs/proj_20260307_a3f8b2c1/spec/research_spec.json
  - runs/proj_20260307_a3f8b2c1/plan/experiment_plan.json
  - runs/proj_20260307_a3f8b2c1/knowledge/evidence_report.md

Next Steps:
  python cli.py run start proj_20260307_a3f8b2c1
```

---

## Command: `project delete`

### Signature

```bash
python cli.py project delete <project_id> [OPTIONS]
```

### Description

Delete a generated project and its files.

### Arguments

- `project_id` (str, required): Project ID to delete

### Options

- `--force`, `-f` (bool, flag): Skip confirmation prompt
  - Default: `False`
  - Example: `--force`

### Output

```
⚠️  This will delete project proj_20260307_a3f8b2c1 and all its files.
Continue? [y/N]: y

✓ Project deleted successfully
```

---

## Command: `project cache`

### Signature

```bash
python cli.py project cache <action> [OPTIONS]
```

### Description

Manage knowledge cache for evidence search.

### Arguments

- `action` (str, required): Cache action
  - Choices: `list`, `clear`, `refresh`, `stats`

### Options (for `clear` action)

- `--topic` (str, optional): Specific topic to clear
  - Default: `None` (clear all)
  - Example: `--topic transformer_optimization`

- `--older-than` (int, optional): Clear cache older than N days
  - Default: `30`
  - Example: `--older-than 7`

### Output

**`list` action**:
```
Cached Topics:

Topic                      Papers  Repos  Age (days)  Hit Count
transformer_optimization   8       5      5           12
inference_latency          6       3      15          8
memory_optimization        7       4      28          3

Total: 3 topics, 21 papers, 12 repos
```

**`clear` action**:
```
✓ Cleared cache for topic: transformer_optimization
✓ Freed 2.3 MB
```

**`stats` action**:
```
Cache Statistics:

Total Topics: 15
Total Papers: 120
Total Repos: 60
Total Size: 45.2 MB
Cache Hit Rate: 78%
Avg Age: 12 days
```

---

## Error Handling

All commands follow consistent error handling:

1. **Validation Errors**: Exit code 1, clear error message with suggestion
2. **API Errors**: Exit code 1, retry suggestion or fallback option
3. **User Interruption**: Exit code 130, save partial progress
4. **System Errors**: Exit code 2, detailed error log

## Integration with Existing Commands

The `project generate` command outputs are compatible with:

- `python cli.py run start <project_id>` - Execute generated project
- `python cli.py run status <project_id>` - Check execution status
- `python cli.py run report <project_id>` - View experiment results

## Configuration File Format

Example `configs/project_generator.yaml`:

```yaml
project_generator:
  # Evidence search settings
  search:
    max_papers: 10
    max_repos: 5
    cache_ttl_days: 30
    sources:
      - arxiv
      - semantic_scholar
      - github
      - papers_with_code

  # Clarification settings
  clarification:
    max_questions: 5
    interactive: true
    timeout_seconds: 300

  # Proposal settings
  proposals:
    num_candidates: 3
    risk_profiles:
      - conservative
      - balanced
      - aggressive

  # Default constraints
  defaults:
    budget_usd: 100.0
    max_time_hours: 24
    max_iterations: 10
    compute: cpu
```

## API Keys Configuration

Required environment variables:

```bash
# Optional: arXiv API key (not required, but increases rate limit)
export ARXIV_API_KEY="your_key_here"

# Optional: Semantic Scholar API key (not required for basic usage)
export SEMANTIC_SCHOLAR_API_KEY="your_key_here"

# Required: GitHub token (for code search)
export GITHUB_TOKEN="your_token_here"

# Required: LLM API key (for idea parsing and proposal generation)
export OPENAI_API_KEY="your_key_here"
# OR
export ANTHROPIC_API_KEY="your_key_here"
# OR
export DEEPSEEK_API_KEY="your_key_here"
```

## Backward Compatibility

- All new commands use `project` subcommand to avoid conflicts
- Existing `run`, `plan`, `orchestrator` commands remain unchanged
- Generated projects are compatible with all existing execution engines
