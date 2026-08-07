def test_csv_export_requires_auth(client):
    r = client.get("/export/sentinel_audit.csv")
    assert r.status_code == 401


def test_csv_export_returns_csv(client, admin_headers):
    r = client.get("/export/sentinel_audit.csv", headers=admin_headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "SENTINEL AUDIT LOG" in r.text
