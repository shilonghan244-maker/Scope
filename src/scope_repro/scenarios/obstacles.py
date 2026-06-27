from __future__ import annotations


def point_in_rectangle(point: tuple[float, float], rect: dict, dilation: float = 0.0) -> bool:
    x, y = point
    return (rect["x"][0] - dilation) <= x <= (rect["x"][1] + dilation) and (
        rect["y"][0] - dilation
    ) <= y <= (rect["y"][1] + dilation)


def point_in_any_obstacle(point: tuple[float, float], obstacles: dict, dilation: float = 0.0) -> bool:
    return any(point_in_rectangle(point, rect, dilation=dilation) for rect in obstacles.values())


def filter_free_points(points: list[tuple[float, float]], obstacles: dict, dilation: float = 0.0) -> list[tuple[float, float]]:
    return [point for point in points if not point_in_any_obstacle(point, obstacles, dilation=dilation)]
