import json

from services.api.app import handler, response


def test_api_response_is_json_with_content_type() -> None:
    result = response(200, {"vehicle_id": "RNT-2041"})

    assert result["statusCode"] == 200
    assert result["headers"] == {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }
    assert json.loads(result["body"]) == {"vehicle_id": "RNT-2041"}


def test_api_alerts_path_does_not_require_a_vehicle_id(monkeypatch) -> None:
    class Table:
        def scan(self) -> dict[str, object]:
            return {"Items": []}

        def query(self, **_kwargs: object) -> dict[str, object]:
            return {"Items": []}

    class DynamoDb:
        def Table(self, _name: str) -> Table:
            return Table()

    class Boto3:
        def resource(self, _name: str) -> DynamoDb:
            return DynamoDb()

    monkeypatch.setenv("EVENTS_TABLE_NAME", "events")
    monkeypatch.setenv("LATEST_TABLE_NAME", "latest")
    monkeypatch.setitem(__import__("sys").modules, "boto3", Boto3())

    result = handler({"rawPath": "/alerts", "pathParameters": None}, None)

    assert result["statusCode"] == 200
    assert json.loads(result["body"]) == {"items": []}