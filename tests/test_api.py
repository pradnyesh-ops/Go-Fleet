import json

from services.api.app import response


def test_api_response_is_json_with_content_type() -> None:
    result = response(200, {"vehicle_id": "RNT-2041"})

    assert result["statusCode"] == 200
    assert result["headers"] == {"Content-Type": "application/json"}
    assert json.loads(result["body"]) == {"vehicle_id": "RNT-2041"}