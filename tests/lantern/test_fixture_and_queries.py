from __future__ import annotations


def test_seeded_fixture_answers_are_deterministic(seeded_store, expected_data: dict) -> None:
    q1 = expected_data["answers"][0]["expected"]
    assessment = seeded_store.current_assessment(
        claim_id=q1["claim_id"], assessor_id=expected_data["assessor_id"], scope_id=expected_data["scope_id"]
    )
    assert assessment is not None
    assert assessment.record_id == q1["assessment_id"]
    assert assessment.payload["disposition"] == "ACCEPTED"

    q4 = expected_data["answers"][3]["expected"]
    status = seeded_store.status()
    review_subjects = sorted(item["subject_record_id"] for item in status["review_required"])
    assert review_subjects == q4["review_required_subject_ids"]

    q3 = expected_data["answers"][2]["expected"]
    trace = seeded_store.decision_trace(q3["decision_id"])
    dependency_ids = sorted(item["target_record_id"] for item in trace["dependencies"])
    assert dependency_ids == sorted(q3["direct_dependencies"])
    assert trace["review_required"] is True


def test_opposition_and_contradiction_are_preserved(seeded_store, expected_data: dict) -> None:
    selected_claim = expected_data["selected_claim_id"]
    rows = seeded_store._connection.execute(
        "select link_type, source_record_id, target_record_id from links where target_record_id=? or source_record_id=? order by link_type",
        (selected_claim, selected_claim),
    ).fetchall()
    link_types = [row["link_type"] for row in rows]
    assert "SUPPORTS" in link_types
    assert "OPPOSES" in link_types
    assert "CONTRADICTS" in link_types
