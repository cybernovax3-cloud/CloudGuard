import math


def validate_sensor_data(data):

    required = [
        "device_id",
        "rainfall",
        "temperature",
        "humidity",
        "pressure",
        "water_level"
    ]

    # Check required fields
    for field in required:
        if field not in data:
            return False, f"Missing field: {field}"

    # Check numeric values
    numeric_fields = [
        "rainfall",
        "temperature",
        "humidity",
        "pressure",
        "water_level"
    ]

    for field in numeric_fields:

        value = data[field]

        if not isinstance(value, (int, float)):
            return False, f"Invalid value for {field}"

        if not math.isfinite(value):
            return False, f"Invalid numeric value for {field}"

    # Reasonable sensor limits
    if not 0 <= data["rainfall"] <= 500:
        return False, "Rainfall value out of range"

    if not -40 <= data["temperature"] <= 80:
        return False, "Temperature value out of range"

    if not 0 <= data["humidity"] <= 100:
        return False, "Humidity value out of range"

    if not 800 <= data["pressure"] <= 1200:
        return False, "Pressure value out of range"

    if not 0 <= data["water_level"] <= 500:
        return False, "Water level out of range"

    return True, "Valid"