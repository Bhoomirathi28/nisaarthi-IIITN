"""Small geometry helpers. Coordinates are (lat, lon) tuples."""
import math

EARTH_R = 6371000.0


def haversine(a, b):
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(h))


def densify(coords, step_m=25.0):
    """Insert points so no segment is longer than step_m (keeps projection accurate)."""
    if len(coords) < 2:
        return list(coords)
    out = [coords[0]]
    for a, b in zip(coords, coords[1:]):
        d = haversine(a, b)
        n = max(1, int(d // step_m))
        for i in range(1, n + 1):
            t = i / n
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def cumulative(coords):
    """Distance from the start (m) at every vertex."""
    cum = [0.0]
    for a, b in zip(coords, coords[1:]):
        cum.append(cum[-1] + haversine(a, b))
    return cum


def project(point, coords, cum):
    """Return (distance_from_route_m, position_along_route_m) using the nearest vertex."""
    best_d, best_i = float("inf"), 0
    for i, c in enumerate(coords):
        d = haversine(point, c)
        if d < best_d:
            best_d, best_i = d, i
    return best_d, cum[best_i]


def bbox(coord_lists, pad_deg=0.004):
    lats = [c[0] for cl in coord_lists for c in cl]
    lons = [c[1] for cl in coord_lists for c in cl]
    return (min(lats) - pad_deg, min(lons) - pad_deg, max(lats) + pad_deg, max(lons) + pad_deg)
