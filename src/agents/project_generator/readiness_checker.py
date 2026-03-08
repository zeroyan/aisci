"""Readiness Checker for validating ResearchSpec executability."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from src.schemas.research_spec import ResearchSpec


@dataclass
class ValidationIssue:
    """Single validation issue."""

    category: str  # "metrics", "baseline", "dependencies", "budget", "failure_criteria"
    severity: str  # "error", "warning"
    message: str
    suggestion: str


@dataclass
class ValidationReport:
    """Validation report with issues and overall status."""

    is_ready: bool
    issues: list[ValidationIssue]
    summary: str


class ReadinessChecker:
    """Check if ResearchSpec is ready for execution."""

    def __init__(self, timeout_sec: int = 10):
        """Initialize ReadinessChecker.

        Args:
            timeout_sec: Timeout for external checks (e.g., URL validation)
        """
        self.timeout_sec = timeout_sec

    def check(self, spec: ResearchSpec) -> ValidationReport:
        """Run all validation checks on ResearchSpec.

        Args:
            spec: ResearchSpec to validate

        Returns:
            ValidationReport with issues and readiness status
        """
        issues: list[ValidationIssue] = []

        # Run all checks
        issues.extend(self._check_metrics(spec))
        issues.extend(self._check_baseline(spec))
        issues.extend(self._check_dependencies(spec))
        issues.extend(self._check_budget(spec))
        issues.extend(self._check_failure_criteria(spec))

        # Determine readiness (no errors)
        has_errors = any(issue.severity == "error" for issue in issues)
        is_ready = not has_errors

        # Generate summary
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")

        if is_ready:
            summary = (
                f"✅ ResearchSpec is ready for execution ({warning_count} warnings)"
            )
        else:
            summary = (
                f"❌ ResearchSpec has {error_count} errors and {warning_count} warnings"
            )

        return ValidationReport(
            is_ready=is_ready,
            issues=issues,
            summary=summary,
        )

    def _check_metrics(self, spec: ResearchSpec) -> list[ValidationIssue]:
        """Check if metrics are measurable.

        Args:
            spec: ResearchSpec to check

        Returns:
            List of validation issues
        """
        issues = []

        if not spec.metrics:
            issues.append(
                ValidationIssue(
                    category="metrics",
                    severity="error",
                    message="No metrics defined",
                    suggestion="Add at least one metric (e.g., accuracy, latency, F1-score)",
                )
            )
            return issues

        # Check for vague metrics
        vague_terms = ["better", "improved", "faster", "quality"]
        for metric in spec.metrics:
            metric_name = metric.name if hasattr(metric, "name") else str(metric)
            if any(term in metric_name.lower() for term in vague_terms):
                issues.append(
                    ValidationIssue(
                        category="metrics",
                        severity="warning",
                        message=f"Metric '{metric_name}' is vague",
                        suggestion=f"Use specific metrics like 'accuracy', 'latency_ms', 'f1_score' instead of '{metric_name}'",
                    )
                )

        return issues

    def _check_baseline(self, spec: ResearchSpec) -> list[ValidationIssue]:
        """Check if baseline is accessible.

        Args:
            spec: ResearchSpec to check

        Returns:
            List of validation issues
        """
        issues = []

        # Baseline is stored in evidence_metadata for project generator specs
        if not spec.evidence_metadata:
            return issues

        baseline_method = spec.evidence_metadata.get("baseline_method")
        baseline_reference = spec.evidence_metadata.get("baseline_reference")
        baseline_methods = spec.evidence_metadata.get("baseline_references", [])
        baseline_references = spec.evidence_metadata.get(
            "baseline_paper_references", []
        )

        if not baseline_method and baseline_methods:
            baseline_method = baseline_methods[0]
        if not baseline_reference and baseline_references:
            baseline_reference = baseline_references[0]

        if not baseline_method:
            issues.append(
                ValidationIssue(
                    category="baseline",
                    severity="warning",
                    message="No baseline method specified",
                    suggestion="Consider adding a baseline method for comparison",
                )
            )
            return issues

        # Check if baseline has reference
        if not baseline_reference:
            issues.append(
                ValidationIssue(
                    category="baseline",
                    severity="warning",
                    message=f"Baseline '{baseline_method}' has no reference",
                    suggestion="Add paper URL or code repository for reproducibility",
                )
            )
        else:
            # Validate URL accessibility
            if baseline_reference.startswith("http"):
                if not self._check_url_accessible(baseline_reference):
                    issues.append(
                        ValidationIssue(
                            category="baseline",
                            severity="warning",
                            message=f"Baseline reference URL not accessible: {baseline_reference}",
                            suggestion="Verify the URL or provide an alternative reference",
                        )
                    )

        return issues

    def _check_dependencies(self, spec: ResearchSpec) -> list[ValidationIssue]:
        """Check if dependencies are installable.

        Args:
            spec: ResearchSpec to check

        Returns:
            List of validation issues
        """
        issues = []

        # Dependencies stored in evidence_metadata
        if not spec.evidence_metadata:
            return issues

        required_packages = spec.evidence_metadata.get("required_packages", [])
        if not required_packages:
            return issues

        # Check PyPI availability (simplified check)
        for package in required_packages:
            # Extract package name (remove version specifiers)
            pkg_name = package.split("==")[0].split(">=")[0].split("<=")[0].strip()

            if not self._check_pypi_package(pkg_name):
                issues.append(
                    ValidationIssue(
                        category="dependencies",
                        severity="warning",
                        message=f"Package '{pkg_name}' not found on PyPI",
                        suggestion="Verify package name or provide installation instructions",
                    )
                )

        return issues

    def _check_budget(self, spec: ResearchSpec) -> list[ValidationIssue]:
        """Check if budget is reasonable.

        Args:
            spec: ResearchSpec to check

        Returns:
            List of validation issues
        """
        issues = []

        # Budget stored in constraints
        max_budget = spec.constraints.max_budget_usd if spec.constraints else None

        if not max_budget:
            issues.append(
                ValidationIssue(
                    category="budget",
                    severity="warning",
                    message="No budget estimate provided",
                    suggestion="Add estimated cost for resource planning",
                )
            )
            return issues

        # Check for unrealistic budgets
        if max_budget < 1:
            issues.append(
                ValidationIssue(
                    category="budget",
                    severity="warning",
                    message=f"Budget ${max_budget:.2f} seems too low",
                    suggestion="Typical ML experiments cost $10-$1000 depending on complexity",
                )
            )
        elif max_budget > 10000:
            issues.append(
                ValidationIssue(
                    category="budget",
                    severity="warning",
                    message=f"Budget ${max_budget:.2f} is very high",
                    suggestion="Consider breaking into smaller experiments or verify estimate",
                )
            )

        return issues

    def _check_failure_criteria(self, spec: ResearchSpec) -> list[ValidationIssue]:
        """Check if failure criteria are clear.

        Args:
            spec: ResearchSpec to check

        Returns:
            List of validation issues
        """
        issues = []

        # Failure criteria stored in evidence_metadata
        if not spec.evidence_metadata:
            failure_criteria = []
        else:
            failure_criteria = spec.evidence_metadata.get("failure_criteria", [])

        if not failure_criteria:
            issues.append(
                ValidationIssue(
                    category="failure_criteria",
                    severity="warning",
                    message="No failure criteria defined",
                    suggestion="Define when to stop the experiment (e.g., 'accuracy < 60%', 'training time > 24h')",
                )
            )

        return issues

    def _check_url_accessible(self, url: str) -> bool:
        """Check if URL is accessible.

        Args:
            url: URL to check

        Returns:
            True if accessible, False otherwise
        """
        try:
            response = requests.head(
                url, timeout=self.timeout_sec, allow_redirects=True
            )
            return response.status_code < 400
        except Exception:
            return False

    def _check_pypi_package(self, package_name: str) -> bool:
        """Check if package exists on PyPI.

        Args:
            package_name: Package name to check

        Returns:
            True if exists, False otherwise
        """
        try:
            url = f"https://pypi.org/pypi/{package_name}/json"
            response = requests.get(url, timeout=self.timeout_sec)
            return response.status_code == 200
        except Exception:
            return False
