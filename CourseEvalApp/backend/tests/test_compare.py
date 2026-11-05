from datetime import datetime, timedelta, timezone

from compare import term_sort_key
from conftest import auth_header
from models import Report

V_NEW = "2026-10-08.4"


def report_json(overall, topics, prompt_version=V_NEW, pace_dirs=None, ratings=None, general=None):
    categories = []
    for topic, (avg, scored) in topics.items():
        category = {"topic": topic, "average_score": avg, "scored_comment_count": scored, "comments": []}
        if topic == "Pace" and pace_dirs:
            category["direction_counts"] = pace_dirs
        categories.append(category)
    categories.append({"topic": "None of the above / Other", "average_score": None, "scored_comment_count": 0, "comments": []})
    return {
        "overall_score": overall,
        "categories": categories,
        "quantitative": ratings or [],
        "general_sentiment": {"average_score": general},
        "metadata": {"prompt_version": prompt_version, "processed_comments": 40, "model_id": "gpt-test"},
    }


def add_report(db_session, owner_id, course, term, data, days_ago=0):
    with db_session() as db:
        report = Report(owner_id=owner_id, course=course, term=term, report_json=data,
                        overall_score=data["overall_score"], created_at=datetime.now(timezone.utc) - timedelta(days=days_ago))
        db.add(report)
        db.commit()
        return report.id


def test_terms_sort_in_calendar_order():
    terms = ["Fall 2025", "Spring 2025", "F24", "Winter 2026", None, "Summer 2025"]
    assert sorted(terms, key=lambda t: term_sort_key(t, None)) == ["F24", "Spring 2025", "Summer 2025", "Fall 2025", "Winter 2026", None]


def test_compare_orders_by_term_and_reports_changes(client, db_session, make_user):
    owner = make_user("prof@csumb.edu")
    fall = add_report(db_session, owner, "CHEM 110", "Fall 2025",
                      report_json(4.2, {"Pace": (4.0, 10), "Clarity of explanations": (4.6, 12), "Workload": (3.0, 2)},
                                  pace_dirs={"too_fast": 2, "too_slow": 0, "appropriate": 8}, general=4.5,
                                  ratings=[{"question": "Overall rating of the instructor", "mean": 4.4, "n": 80}]))
    spring = add_report(db_session, owner, "CHEM 110", "Spring 2025",
                        report_json(3.6, {"Pace": (2.5, 10), "Clarity of explanations": (4.5, 9), "Workload": (4.0, 3)},
                                    pace_dirs={"too_fast": 9, "too_slow": 0, "appropriate": 1},
                                    ratings=[{"question": "Overall rating of the instructor ", "mean": 4.0, "n": 70}]),
                        days_ago=1)  # created later in time order but earlier term
    headers = auth_header(client, "prof@csumb.edu")
    result = client.get(f"/api/compare?ids={fall},{spring}", headers=headers).json()

    assert [r["term"] for r in result["reports"]] == ["Spring 2025", "Fall 2025"]
    assert result["overall_change"] == 0.6
    pace = next(row for row in result["topics"] if row["topic"] == "Pace")
    assert pace["change"] == 1.5 and pace["change_is_reliable"] is True
    assert result["improved"][0] == {"topic": "Pace", "change": 1.5}
    # Workload rose too, but with fewer than 5 scored comments it is not a highlight
    workload = next(row for row in result["topics"] if row["topic"] == "Workload")
    assert workload["change"] == -1.0 and workload["change_is_reliable"] is False
    assert all(item["topic"] != "Workload" for item in result["improved"] + result["declined"])
    assert all(row["topic"] != "None of the above / Other" for row in result["topics"])
    assert result["reports"][0]["pace_directions"]["too_fast"] == 9
    assert result["ratings"] == [{"question": "Overall rating of the instructor ", "means": [4.0, 4.4], "change": 0.4}]
    assert any("fewer than 5" in w for w in result["warnings"])


def test_warnings_for_different_courses_and_old_pace_scale(client, db_session, make_user):
    owner = make_user("prof@csumb.edu")
    old = add_report(db_session, owner, "CHEM 110", "Fall 2024", report_json(3.5, {"Pace": (2.0, 8)}, prompt_version=None))
    new = add_report(db_session, owner, "CHEM 111", "Fall 2025", report_json(4.0, {"Pace": (4.0, 8)}))
    warnings = client.get(f"/api/compare?ids={old},{new}", headers=auth_header(client, "prof@csumb.edu")).json()["warnings"]
    assert any("different courses" in w for w in warnings)
    assert any("Pace scale" in w for w in warnings)


def test_compare_is_owner_only(client, db_session, make_user):
    owner = make_user("prof@csumb.edu")
    make_user("other@csumb.edu")
    a = add_report(db_session, owner, "CHEM 110", "Fall 2024", report_json(3.5, {}))
    b = add_report(db_session, owner, "CHEM 110", "Fall 2025", report_json(4.0, {}))
    response = client.get(f"/api/compare?ids={a},{b}", headers=auth_header(client, "other@csumb.edu"))
    assert response.status_code == 404


def test_compare_needs_two_to_eight_valid_ids(client, db_session, make_user):
    owner = make_user("prof@csumb.edu")
    a = add_report(db_session, owner, "CHEM 110", "Fall 2024", report_json(3.5, {}))
    headers = auth_header(client, "prof@csumb.edu")
    assert client.get(f"/api/compare?ids={a}", headers=headers).status_code == 400
    assert client.get(f"/api/compare?ids={a},{a}", headers=headers).status_code == 400
    assert client.get("/api/compare?ids=1,abc", headers=headers).status_code == 400
    assert client.get("/api/compare?ids=" + ",".join(str(i) for i in range(1, 10)), headers=headers).status_code == 400


def test_edited_scores_are_used(client, db_session, make_user):
    """Ignored comments recalculate averages in the stored report; the comparison uses those numbers."""
    owner = make_user("prof@csumb.edu")
    a = add_report(db_session, owner, "CHEM 110", "Fall 2024", report_json(3.0, {"Pace": (3.0, 6)}))
    b = add_report(db_session, owner, "CHEM 110", "Fall 2025", report_json(3.0, {"Pace": (3.0, 6)}))
    headers = auth_header(client, "prof@csumb.edu")
    edited = client.get(f"/api/reports/{b}", headers=headers).json()["report"]
    edited["categories"][0]["average_score"] = 4.0
    edited["overall_score"] = 3.8
    client.put(f"/api/reports/{b}", json={"report": edited}, headers=headers)
    result = client.get(f"/api/compare?ids={a},{b}", headers=headers).json()
    assert result["overall_change"] == 0.8
    assert result["topics"][0]["change"] == 1.0


def test_compare_handles_many_topics_quickly_and_skips_malformed_entries(client, db_session, make_user):
    """Topic and rating de-duplication is linear, and odd stored entries are skipped instead of crashing."""
    import time
    owner = make_user("prof@csumb.edu")
    many = {f"Topic {i}": (3.0, 6) for i in range(20_000)}
    data = report_json(3.0, many)
    data["categories"] += [{"topic": ["not", "text"]}, "not a category"]
    data["quantitative"] = [{"question": {"x": 1}, "mean": 3.0}, "not a table"]
    a = add_report(db_session, owner, "CHEM 110", "Fall 2024", data)
    b = add_report(db_session, owner, "CHEM 110", "Fall 2025", report_json(3.5, {f"Topic {i}": (3.5, 6) for i in range(20_000)}))
    started = time.perf_counter()
    response = client.get(f"/api/compare?ids={a},{b}", headers=auth_header(client, "prof@csumb.edu"))
    assert response.status_code == 200
    assert len(response.json()["topics"]) == 20_000
    assert time.perf_counter() - started < 10


def test_saved_reports_are_size_checked(client, db_session, make_user):
    owner = make_user("prof@csumb.edu")
    report_id = add_report(db_session, owner, "CHEM 110", "Fall 2025", report_json(3.0, {"Pace": (3.0, 6)}))
    headers = auth_header(client, "prof@csumb.edu")
    put = lambda data: client.put(f"/api/reports/{report_id}", json={"report": data}, headers=headers)

    too_many_topics = report_json(3.0, {f"T{i}": (3.0, 6) for i in range(250)})
    assert put(too_many_topics).status_code == 400
    too_many_comments = report_json(3.0, {"Pace": (3.0, 6)})
    too_many_comments["categories"][0]["comments"] = [{"feedback": "x", "score": 3}] * 20_001
    assert put(too_many_comments).status_code == 400
    too_big = report_json(3.0, {"Pace": (3.0, 6)})
    too_big["notes"] = "x" * 5_000_001
    assert put(too_big).status_code == 400
    bad_topic = report_json(3.0, {"Pace": (3.0, 6)})
    bad_topic["categories"][0]["topic"] = {"nested": True}
    assert put(bad_topic).status_code == 400
    not_a_number = client.put(f"/api/reports/{report_id}", content='{"report": {"overall_score": NaN, "categories": []}}',
                              headers={**headers, "Content-Type": "application/json"})
    assert not_a_number.status_code in (400, 422)
    assert put(report_json(3.2, {"Pace": (3.2, 6)})).status_code == 200
