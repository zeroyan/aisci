# Quickstart: Idea-to-Project Generator

**Feature**: 005-idea-to-project-generator
**Date**: 2026-03-07
**Purpose**: Quick validation scenarios for testing the feature end-to-end

## Prerequisites

1. **Environment Setup**:
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set API keys
export GITHUB_TOKEN="your_github_token"
export DEEPSEEK_API_KEY="your_deepseek_key"
```

2. **Verify Installation**:
```bash
# Check CLI is working
python cli.py --help

# Verify project command exists
python cli.py project --help
```

## Scenario 1: Basic Idea-to-Project (Happy Path)

**Goal**: Generate a complete project from a simple idea

**Steps**:
```bash
# 1. Generate project with interactive mode
python cli.py project generate "I want to improve Transformer speed on long texts"

# Expected: System asks 2-5 clarifying questions
# Answer: Select option 1 for each question (use defaults)

# 2. Verify output files exist
ls runs/proj_*/spec/research_spec.json
ls runs/proj_*/plan/experiment_plan.json
ls runs/proj_*/knowledge/evidence_report.md

# 3. Check generated spec is valid
python -c "
import json
from pathlib import Path
spec_path = list(Path('runs').glob('proj_*/spec/research_spec.json'))[0]
spec = json.loads(spec_path.read_text())
assert 'spec_id' in spec
assert 'objective' in spec
assert 'metrics' in spec
print('✓ ResearchSpec is valid')
"

# 4. Execute generated project
PROJECT_ID=$(ls runs/ | grep proj_ | tail -1)
python cli.py run start $PROJECT_ID

# Expected: Experiment starts successfully
```

**Success Criteria**:
- ✅ Project generated in under 5 minutes
- ✅ All 3 output files created
- ✅ ResearchSpec passes validation
- ✅ Experiment executes without errors

---

## Scenario 2: Non-Interactive Mode

**Goal**: Generate project without user interaction

**Steps**:
```bash
# Generate project with defaults
python cli.py project generate \
  "Optimize inference latency for BERT" \
  --no-interactive \
  --auto-select balanced \
  --budget 50 \
  --max-time 2d

# Verify output
PROJECT_ID=$(ls runs/ | grep proj_ | tail -1)
python cli.py project show $PROJECT_ID

# Check constraints were applied
python -c "
import json
from pathlib import Path
spec_path = list(Path('runs').glob('proj_*/spec/research_spec.json'))[-1]
spec = json.loads(spec_path.read_text())
assert spec['constraints']['max_budget_usd'] == 50.0
assert spec['constraints']['max_runtime_hours'] == 48.0
print('✓ Constraints applied correctly')
"
```

**Success Criteria**:
- ✅ No user interaction required
- ✅ Constraints applied correctly
- ✅ Balanced proposal auto-selected

---

## Scenario 3: Evidence Search and Caching

**Goal**: Verify evidence search and cache functionality

**Steps**:
```bash
# 1. First search (cold cache)
time python cli.py project generate \
  "Improve Transformer attention mechanism" \
  --no-interactive \
  --auto-select conservative

# Note the time taken (should be ~30 seconds)

# 2. Second search (warm cache)
time python cli.py project generate \
  "Optimize Transformer attention for long sequences" \
  --no-interactive \
  --auto-select conservative

# Note the time taken (should be <5 seconds due to cache)

# 3. Verify cache exists
ls scientist/transformer_attention/papers.json
ls scientist/transformer_attention/code.json

# 4. Check cache stats
python cli.py project cache stats

# 5. Force refresh cache
python cli.py project generate \
  "Improve Transformer attention" \
  --force-refresh \
  --no-interactive \
  --auto-select balanced
```

**Success Criteria**:
- ✅ First search takes ~30 seconds
- ✅ Second search takes <5 seconds (80% faster)
- ✅ Cache files created in `scientist/` directory
- ✅ Force refresh updates cache

---

## Scenario 4: Multiple Proposals

**Goal**: Generate and select from multiple candidate proposals

**Steps**:
```bash
# Generate with 3 proposals
python cli.py project generate \
  "Reduce memory usage in large language models" \
  --num-proposals 3

# Expected output:
# 1. Conservative: Replicate existing quantization methods
# 2. Balanced: Combine quantization + pruning
# 3. Aggressive: Explore novel compression techniques

# Select option 2 (balanced)

# Verify proposal selection
PROJECT_ID=$(ls runs/ | grep proj_ | tail -1)
python -c "
import json
from pathlib import Path
proposals_path = Path('runs') / '$PROJECT_ID' / 'proposals.json'
proposals = json.loads(proposals_path.read_text())
assert len(proposals) == 3
assert proposals[0]['risk_profile'] == 'conservative'
assert proposals[1]['risk_profile'] == 'balanced'
assert proposals[2]['risk_profile'] == 'aggressive'
print('✓ All 3 proposals generated')
"
```

**Success Criteria**:
- ✅ 3 distinct proposals generated
- ✅ Each proposal has different risk profile
- ✅ Selected proposal used for spec generation

---

## Scenario 5: Evidence Report Quality

**Goal**: Verify evidence report contains useful information

**Steps**:
```bash
# Generate project
python cli.py project generate \
  "Improve training efficiency for vision transformers" \
  --no-interactive \
  --auto-select balanced \
  --format both

# Check evidence report
PROJECT_ID=$(ls runs/ | grep proj_ | tail -1)
cat runs/$PROJECT_ID/knowledge/evidence_report.md

# Verify report structure
python -c "
from pathlib import Path
report_path = Path('runs') / '$PROJECT_ID' / 'knowledge' / 'evidence_report.md'
content = report_path.read_text()

# Check required sections
assert '## Summary' in content
assert '## Key Papers' in content
assert '## Recommended Baselines' in content
assert '## Identified Risks' in content
assert '## Citations' in content

# Check content quality
assert content.count('arxiv:') >= 3  # At least 3 paper citations
assert len(content) >= 1000  # Substantial content

print('✓ Evidence report is complete and detailed')
"
```

**Success Criteria**:
- ✅ Report contains all required sections
- ✅ At least 3 paper citations
- ✅ At least 1 baseline recommendation
- ✅ Risks identified

---

## Scenario 6: Error Handling

**Goal**: Verify graceful error handling

**Steps**:
```bash
# 1. Test invalid idea (too short)
python cli.py project generate "test"
# Expected: Error message about minimum length

# 2. Test contradictory constraints
python cli.py project generate \
  "Achieve 99% accuracy" \
  --budget 1 \
  --max-time 1h \
  --no-interactive
# Expected: Error about infeasible constraints

# 3. Test API failure (invalid GitHub token)
export GITHUB_TOKEN="invalid_token"
python cli.py project generate \
  "Optimize code generation" \
  --no-interactive \
  --auto-select balanced
# Expected: Warning about GitHub API failure, continues with other sources

# 4. Test cache corruption
rm -rf scientist/transformer_attention/
touch scientist/transformer_attention/papers.json
echo "invalid json" > scientist/transformer_attention/papers.json
python cli.py project generate \
  "Improve Transformer attention" \
  --no-interactive \
  --auto-select balanced
# Expected: Falls back to direct API search
```

**Success Criteria**:
- ✅ Clear error messages for invalid input
- ✅ Detects infeasible constraints
- ✅ Graceful fallback on API failures
- ✅ Handles cache corruption

---

## Scenario 7: Integration with Existing Execution

**Goal**: Verify generated projects work with existing execution engines

**Steps**:
```bash
# 1. Generate project
python cli.py project generate \
  "Improve model interpretability" \
  --no-interactive \
  --auto-select balanced

PROJECT_ID=$(ls runs/ | grep proj_ | tail -1)

# 2. Execute with aisci engine (Spec001)
python cli.py run start $PROJECT_ID

# 3. Execute with orchestrator (Spec003)
python cli.py run start $PROJECT_ID --enable-orchestrator --num-branches 2

# 4. Execute with AI-Scientist (Spec004)
python cli.py run start $PROJECT_ID --engine ai-scientist --model deepseek-chat

# 5. Execute with hybrid mode (Spec004)
python cli.py run start $PROJECT_ID --engine hybrid --model deepseek-chat
```

**Success Criteria**:
- ✅ Generated spec compatible with Spec001
- ✅ Generated spec compatible with Spec003
- ✅ Generated spec compatible with Spec004
- ✅ All execution modes complete successfully

---

## Scenario 8: Cache Management

**Goal**: Test cache management commands

**Steps**:
```bash
# 1. Generate multiple projects to populate cache
for idea in \
  "Improve Transformer speed" \
  "Optimize BERT inference" \
  "Reduce GPT memory usage"
do
  python cli.py project generate "$idea" \
    --no-interactive \
    --auto-select balanced
done

# 2. List cached topics
python cli.py project cache list

# Expected output:
# transformer_optimization  8  5  1   3
# bert_inference           6  3  1   1
# gpt_memory              7  4  1   1

# 3. Check cache stats
python cli.py project cache stats

# Expected: 3 topics, ~21 papers, ~12 repos

# 4. Clear specific topic
python cli.py project cache clear --topic transformer_optimization

# 5. Clear old cache (>7 days)
python cli.py project cache clear --older-than 7

# 6. Verify cache cleared
python cli.py project cache list
```

**Success Criteria**:
- ✅ Cache list shows all topics
- ✅ Cache stats accurate
- ✅ Specific topic cleared successfully
- ✅ Old cache cleared successfully

---

## Performance Benchmarks

### Expected Timings

| Operation | Cold Cache | Warm Cache | Target |
|-----------|-----------|------------|--------|
| Evidence Search | 25-35s | 2-5s | <30s / <5s |
| Idea Parsing | 1-2s | 1-2s | <3s |
| Question Generation | 2-3s | 2-3s | <5s |
| Proposal Generation | 5-8s | 5-8s | <10s |
| **Total (Interactive)** | **35-50s** | **12-20s** | **<5min** |
| **Total (Non-Interactive)** | **30-45s** | **8-15s** | **<2min** |

### Resource Usage

| Metric | Expected | Limit |
|--------|----------|-------|
| Memory | 200-500 MB | <1 GB |
| Disk (per project) | 1-5 MB | <10 MB |
| Disk (cache, 100 topics) | 50-100 MB | <500 MB |
| API Calls (per project) | 10-20 | <50 |

---

## Troubleshooting

### Issue: Evidence search times out

**Solution**:
```bash
# Increase timeout in config
echo "
project_generator:
  search:
    timeout_seconds: 60
" >> configs/project_generator.yaml

# Or use cached results only
python cli.py project generate "..." --skip-search
```

### Issue: No papers found

**Solution**:
```bash
# Check API keys are set
echo $GITHUB_TOKEN
echo $DEEPSEEK_API_KEY

# Try with more generic query
python cli.py project generate "machine learning optimization"

# Check cache
python cli.py project cache list
```

### Issue: Generated spec fails validation

**Solution**:
```bash
# Check spec file
PROJECT_ID=$(ls runs/ | grep proj_ | tail -1)
cat runs/$PROJECT_ID/spec/research_spec.json | python -m json.tool

# Regenerate with different proposal
python cli.py project generate "..." --auto-select conservative
```

---

## Cleanup

```bash
# Remove all generated projects
rm -rf runs/proj_*

# Clear all cache
python cli.py project cache clear

# Reset environment
unset GITHUB_TOKEN
unset DEEPSEEK_API_KEY
```

---

## Next Steps

After validating these scenarios:

1. **Run full test suite**:
   ```bash
   pytest tests/unit/test_project_generator/ -v
   pytest tests/integration/test_project_generator_e2e.py -v
   ```

2. **Generate tasks**:
   ```bash
   /speckit.tasks specs/005-idea-to-project-generator
   ```

3. **Start implementation**:
   ```bash
   /speckit.implement specs/005-idea-to-project-generator
   ```

---

## Success Metrics

All scenarios should pass with:
- ✅ 100% success rate
- ✅ <5 minute end-to-end time (interactive)
- ✅ <2 minute end-to-end time (non-interactive)
- ✅ 80% cache hit rate after warmup
- ✅ Generated projects execute successfully
- ✅ Evidence reports contain useful information
