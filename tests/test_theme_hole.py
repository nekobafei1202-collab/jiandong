"""Unit tests for radial theme reveal helpers."""

from __future__ import annotations

from jiandong_ai.app.theme_switch import (
    ease_out_cubic,
    hole_radius_at,
    mask_stops,
    max_radius,
    origin_to_alignment,
)


def test_ease_out_cubic_endpoints() -> None:
    assert ease_out_cubic(0.0) == 0.0
    assert ease_out_cubic(1.0) == 1.0
    assert ease_out_cubic(0.5) > 0.5
    assert ease_out_cubic(-1.0) == 0.0
    assert ease_out_cubic(2.0) == 1.0


def test_max_radius_corners() -> None:
    r = max_radius(100.0, 200.0, 0.0, 0.0)
    assert abs(r - ((100**2 + 200**2) ** 0.5 + 24)) < 1e-6


def test_hole_radius_grows_not_shrinks() -> None:
    R = 400.0
    assert hole_radius_at(0.0, R) == 0.0
    assert hole_radius_at(1.0, R) == R
    samples = [hole_radius_at(t, R) for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
    assert samples == sorted(samples)
    assert all(samples[i] < samples[i + 1] for i in range(len(samples) - 1))


def test_origin_to_alignment_corners() -> None:
    tl = origin_to_alignment(0.0, 0.0, 100.0, 200.0)
    assert tl.x == -1.0 and tl.y == -1.0
    br = origin_to_alignment(100.0, 200.0, 100.0, 200.0)
    assert br.x == 1.0 and br.y == 1.0
    mid = origin_to_alignment(50.0, 100.0, 100.0, 200.0)
    assert mid.x == 0.0 and mid.y == 0.0


def test_mask_stops_hole_grows() -> None:
    assert mask_stops(0.0) == [0.0, 0.0, 0.0]
    assert mask_stops(1.0) == [0.0, 1.0, 1.0]
    edges = [mask_stops(t)[1] for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
    assert edges == sorted(edges)
    assert all(edges[i] < edges[i + 1] for i in range(len(edges) - 1))
