from protocol.location_lookup import (
    manual_location_value,
    opencage_location_options,
)


def test_opencage_result_uses_the_reference_semantic_shape() -> None:
    values = opencage_location_options(
        {
            "results": [
                {
                    "formatted": "Montréal, Québec, Canada",
                    "geometry": {"lat": 45.5019, "lng": -73.5674},
                    "components": {
                        "city": "Montréal",
                        "state": "Québec",
                        "country": "Canada",
                        "country_code": "ca",
                    },
                    "annotations": {"geohash": "f25dvk"},
                }
            ]
        }
    )

    assert values[0].as_dict() == {
        "display_label": "Montréal, Québec, Canada",
        "locality": "Montréal",
        "region": "Québec",
        "country": "Canada",
        "country_code": "CA",
        "place_id": "f25dvk",
        "latitude": 45.5019,
        "longitude": -73.5674,
    }


def test_manual_location_is_normalized_without_fake_coordinates() -> None:
    value = manual_location_value("Montréal")

    assert value["display_label"] == "Montréal"
    assert value["place_id"].startswith("manual:")
    assert "latitude" not in value
    assert "longitude" not in value
