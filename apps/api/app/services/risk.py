from __future__ import annotations

from collections.abc import Iterable

SEVERITY_POINTS = {"critical": 46, "high": 29, "medium": 15, "low": 6}


def calculate_risk(
    findings: Iterable[object],
    open_work_orders: int,
    freshness_days: int = 0,
    quality_warning: bool = False,
) -> tuple[int, str, list[dict[str, object]]]:
    score = 8
    drivers: list[dict[str, object]] = []
    finding_list = list(findings)
    if finding_list:
        weighted = 0
        for f in finding_list:
            weighted += int(
                SEVERITY_POINTS.get(getattr(f, "severity", "low"), 6) * getattr(f, "confidence", 0.5)
            )
        contribution = min(58, weighted)
        score += contribution
        drivers.append(
            {
                "driver": "Verified and reviewable findings",
                "impact": contribution,
                "detail": f"{len(finding_list)} evidence-linked finding(s)",
            }
        )
    if open_work_orders:
        impact = min(17, open_work_orders * 5)
        score += impact
        drivers.append(
            {
                "driver": "Open maintenance work",
                "impact": impact,
                "detail": f"{open_work_orders} active work order(s)",
            }
        )
    if freshness_days > 30:
        score += 8
        drivers.append(
            {
                "driver": "Inspection freshness",
                "impact": 8,
                "detail": f"Last capture is {freshness_days} days old",
            }
        )
    if quality_warning:
        score += 6
        drivers.append(
            {"driver": "Capture/data quality", "impact": 6, "detail": "Quality warning limits confidence"}
        )
    score = min(100, score)
    level = "Critical" if score >= 80 else "High" if score >= 60 else "Moderate" if score >= 35 else "Low"
    return score, level, drivers
