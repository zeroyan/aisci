"""Unit tests for EarlyStopDetector."""


from src.agents.planner.early_stop_detector import EarlyStopDetector


def test_detector_initialization():
    """Test detector initialization."""
    detector = EarlyStopDetector(no_improvement_threshold=2)

    assert detector.no_improvement_threshold == 2
    assert detector.consecutive_no_improvement == 0
    assert detector.best_score == 0.0


def test_no_stop_on_improvement():
    """Test that detector doesn't stop when score improves."""
    detector = EarlyStopDetector(no_improvement_threshold=2)

    should_stop, reason = detector.should_stop(
        current_score=50.0, max_iterations=5, current_iteration=1
    )

    assert not should_stop
    assert reason == ""
    assert detector.best_score == 50.0
    assert detector.consecutive_no_improvement == 0


def test_no_stop_on_single_no_improvement():
    """Test that detector doesn't stop on single no-improvement."""
    detector = EarlyStopDetector(no_improvement_threshold=2)

    # First iteration: improvement
    detector.should_stop(50.0, 5, 1)

    # Second iteration: no improvement
    should_stop, reason = detector.should_stop(45.0, 5, 2)

    assert not should_stop
    assert detector.consecutive_no_improvement == 1


def test_stop_on_consecutive_no_improvement():
    """Test that detector stops after consecutive no-improvements."""
    detector = EarlyStopDetector(no_improvement_threshold=2)

    # Iteration 1: improvement
    detector.should_stop(50.0, 5, 1)

    # Iteration 2: no improvement
    detector.should_stop(45.0, 5, 2)

    # Iteration 3: no improvement (should stop)
    should_stop, reason = detector.should_stop(40.0, 5, 3)

    assert should_stop
    assert "No improvement for 2 consecutive iterations" in reason


def test_reset_counter_on_improvement():
    """Test that counter resets when score improves."""
    detector = EarlyStopDetector(no_improvement_threshold=2)

    # Iteration 1: improvement
    detector.should_stop(50.0, 5, 1)

    # Iteration 2: no improvement
    detector.should_stop(45.0, 5, 2)

    # Iteration 3: improvement (should reset counter)
    should_stop, reason = detector.should_stop(60.0, 5, 3)

    assert not should_stop
    assert detector.consecutive_no_improvement == 0
    assert detector.best_score == 60.0


def test_stop_on_max_iterations():
    """Test that detector stops at max iterations."""
    detector = EarlyStopDetector(no_improvement_threshold=2)

    should_stop, reason = detector.should_stop(50.0, 5, 5)

    assert should_stop
    assert "Reached maximum iterations (5)" in reason


def test_custom_threshold():
    """Test detector with custom threshold."""
    detector = EarlyStopDetector(no_improvement_threshold=3)

    # Set initial score
    detector.should_stop(50.0, 10, 1)

    # 3 consecutive no-improvements needed
    detector.should_stop(45.0, 10, 2)  # 1st no-improvement
    detector.should_stop(40.0, 10, 3)  # 2nd no-improvement
    should_stop, _ = detector.should_stop(35.0, 10, 4)  # 3rd no-improvement

    assert should_stop


def test_reset():
    """Test detector reset."""
    detector = EarlyStopDetector(no_improvement_threshold=2)

    # Set some state
    detector.should_stop(50.0, 5, 1)
    detector.should_stop(45.0, 5, 2)

    # Reset
    detector.reset()

    assert detector.consecutive_no_improvement == 0
    assert detector.best_score == 0.0


def test_equal_score_counts_as_no_improvement():
    """Test that equal score counts as no improvement."""
    detector = EarlyStopDetector(no_improvement_threshold=2)

    # Set initial score
    detector.should_stop(50.0, 5, 1)

    # Same score (no improvement)
    should_stop, _ = detector.should_stop(50.0, 5, 2)

    assert not should_stop
    assert detector.consecutive_no_improvement == 1
