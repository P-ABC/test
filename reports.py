"""reports.py - สร้างรายงาน .txt จำนวน 3 รายงานจากข้อมูล Binary

โครงสร้างของรายงานทุกไฟล์:
1) HEADER    - รายละเอียด/วัตถุประสงค์/แหล่งข้อมูล
2) TABLE     - ตารางหลักของรายงาน
3) SUMMARY   - สรุปผลจากข้อมูลท้ายรายงาน

รายงานทุกไฟล์ใช้ข้อมูลจากอย่างน้อย 2 Binary files คือ
charge_points.dat และ charge_points.log
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence

import models
from report import (
    RECENT_ACTIVITY_LIMIT,
    alignment_mode_name,
    compute_summary,
    format_timestamp,
    render_table,
    set_alignment_mode,
    truncate_to_width,
)


# ---------------------------------------------------------------------------
# Report / source file names
# ---------------------------------------------------------------------------
REPORT_POINTS_NAME = "report_points.txt"
REPORT_STATS_NAME = "report_stats.txt"
REPORT_SYSTEM_NAME = "report_system.txt"
ALL_REPORT_NAMES = (
    REPORT_POINTS_NAME,
    REPORT_STATS_NAME,
    REPORT_SYSTEM_NAME,
)

SOURCE_POINT_FILE = models.DATA_FILE_NAME      # charge_points.dat
SOURCE_LOG_FILE = models.LOG_FILE_NAME         # charge_points.log

MAIN_TABLE_MAX_WIDTH = 150
MAIN_TABLE_LOCATION_WIDTH = 32


_LOCATION_LABELS = {
    "สยามพารากอน ชั้น B1": "Siam Paragon, Level B1",
    "เซ็นทรัลเวิลด์ ลาน P2": "CentralWorld, Parking P2",
    "ICONSIAM ชั้น G": "ICONSIAM, Level G",
    "เมกาบางนา โซน A": "Mega Bangna, Zone A",
    "เซ็นทรัลพระราม 9": "Central Rama 9",
    "บิกกิ้ง สาทร ชั้น 2": "Biking Sathorn, Level 2",
    "ลาดพร้าว ไทยรัฐ 2": "Lat Phrao, Thairath 2",
    "เอเชีย เซนเทอร์ ชั้น G": "Asia Center, Level G",
    "เซ็นทรัล พหมโพธิยา": "Central Phom Phothiya",
    "พารากอน โครงการเก่า": "Paragon, Former Project",
    "สถานีชาร์จไฟฟ้าสยามพารากอนชั้นใต้ดินโครงการใหม่และลานจอดรถ":
        "Siam Paragon EV Station, New Basement Project and Parking Lot",
}


def _full_location(
    point: models.ChargePoint,
    locations: Optional[Dict[int, str]],
) -> str:
    """คืนชื่อสถานที่แบบเต็ม ถ้ามี locations.txt; ไม่มีก็ใช้ค่าใน Binary."""
    if locations:
        full = locations.get(point.point_id)
        if full:
            return full
    return point.location


def english_location_label(location: str) -> Optional[str]:
    """Return a known English location label, or None for custom locations."""
    return _LOCATION_LABELS.get(location)


# ---------------------------------------------------------------------------
# Common report sections
# ---------------------------------------------------------------------------
def _header(
    data_dir: str,
    title: str,
    purpose: str,
    source_files: Sequence[str],
) -> List[str]:
    """ส่วนหัว/รายละเอียดของรายงานในรูปแบบอ่านง่าย"""
    return [
        f"EV Charging Station System - {title} Report",
        f"Generated At : {format_timestamp(models.now_timestamp())}",
        f"App Version  : {models.APP_VERSION}",
        f"Endianness   : {models.BYTE_ORDER_LABEL}",
        f"Encoding     : {models.ENCODING_LABEL} (report file uses UTF-8)",
        f"Data Dir     : {data_dir}",
        f"Purpose      : {purpose}",
        f"Source Files : {', '.join(source_files)}",
    ]


def _table_details(
    title: str,
    purpose: str,
    columns: Sequence[Sequence[str]],
    source_files: Sequence[str],
) -> List[str]:
    """รายละเอียดของรายงานแสดงไว้ใน header แล้ว"""
    return []


def _summary_section(rows: Sequence[Sequence[str]]) -> List[str]:
    """สร้าง Summary แบบหัวข้อ + bullet คล้ายตัวอย่างของอาจารย์"""
    lines = [
        "Summary",
        "",
    ]
    for row in rows:
        if len(row) >= 2:
            lines.append(f"- {row[0]} : {row[1]}")
        elif row:
            lines.append(f"- {row[0]}")
    return lines


def _write_report(path: str, lines: Sequence[str]) -> str:
    """เขียนรายงานเป็น .txt แยกไฟล์"""
    content = "\n".join(lines) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    return content


# ---------------------------------------------------------------------------
# Report 1 - Charging Point Report
# ---------------------------------------------------------------------------
def build_report_points(
    data_dir: str,
    points: Sequence[models.ChargePoint],
    log_entries: Sequence[models.LogEntry],
    index_map: Dict[int, int],
    store_valid: bool = True,
    log_valid: bool = True,
    index_valid: bool = True,
    locations: Optional[Dict[int, str]] = None,
) -> List[str]:
    """รายงานหัวชาร์จรายหัว

    ตารางหลักใช้ charge_points.dat เป็นข้อมูลหลัก และเพิ่ม Last Operation
    จาก charge_points.log เพื่อให้รายงานใช้ข้อมูลจาก 2 Binary files อย่างชัดเจน
    """
    summary = compute_summary(points)

    # หา log ล่าสุดของแต่ละ point จากลำดับใน log
    latest_logs: Dict[int, models.LogEntry] = {}
    for entry in log_entries:
        latest_logs[entry.point_id] = entry

    lines = _header(
        data_dir,
        "Charging Point Summary",
        "สรุปข้อมูลหัวชาร์จ สถานะการจอง และเหตุการณ์ล่าสุด",
        [SOURCE_POINT_FILE, SOURCE_LOG_FILE],
    )
    lines.append("")

    lines.extend(_table_details(
        "Charging point status",
        "แสดงรายละเอียดหัวชาร์จทุก record พร้อมสถานะการจองและเหตุการณ์ล่าสุด",
        [
            ("PtID", "รหัสหัวชาร์จ", SOURCE_POINT_FILE),
            ("Station", "รหัสสถานี", SOURCE_POINT_FILE),
            ("Location", "ตำแหน่งหัวชาร์จ", SOURCE_POINT_FILE),
            ("Plug", "ประเภทหัวต่อ", SOURCE_POINT_FILE),
            ("Power", "กำลังไฟ kW", SOURCE_POINT_FILE),
            ("Price", "ราคา THB/kWh", SOURCE_POINT_FILE),
            ("Status", "สถานะปัจจุบัน", SOURCE_POINT_FILE),
            ("Booked", "สถานะการจอง", SOURCE_POINT_FILE),
            ("Last Operation", "เหตุการณ์ล่าสุด", SOURCE_LOG_FILE),
            ("Updated", "เวลาที่แก้ไขล่าสุด", SOURCE_POINT_FILE),
        ],
        [SOURCE_POINT_FILE, SOURCE_LOG_FILE],
    ))

    rows = []
    long_locations = []

    for point in points:
        location = _full_location(point, locations)
        english_location = english_location_label(location)
        table_location = english_location or location

        if len(table_location) > MAIN_TABLE_LOCATION_WIDTH:
            long_locations.append(
                f"  PtID {point.point_id}: {table_location}"
            )

        latest = latest_logs.get(point.point_id)
        operation = latest.op_name if latest else "-"

        rows.append([
            str(point.point_id),
            point.station_code,
            truncate_to_width(table_location, MAIN_TABLE_LOCATION_WIDTH),
            point.plug_type,
            f"{point.power_kw:.1f}",
            f"{point.price_per_kwh:.2f}",
            point.status_text,
            point.booked_text,
            operation,
            format_timestamp(point.updated_at).replace(" (+07:00)", ""),
        ])

    lines.append("Charging Points")
    lines.append("-" * 62)
    lines.extend(render_table(
        [
            "PtID", "Station", "Location", "Plug", "Power", "Price",
            "Status", "Booked", "Last Operation", "Updated",
        ],
        rows,
        max_width=MAIN_TABLE_MAX_WIDTH,
    ))

    if long_locations:
        lines.append("")
        lines.append("Full location names:")
        lines.extend(long_locations)

    inactive = [
        p for p in points
        if not p.is_deleted and p.status != 1
    ]
    booked_active = [
        p for p in points
        if not p.is_deleted and p.status == 1 and p.is_booked == 1
    ]

    checks_pass = [
        len(points) == summary["total"],
        summary["active"] + len(inactive) + summary["deleted"]
        == summary["total"],
        len(booked_active) + summary["available"] == summary["active"],
    ]

    summary_rows = [
        ["Total point records", str(summary["total"])],
        ["Active points", str(summary["active"])],
        ["Inactive points", str(len(inactive))],
        ["Deleted points", str(summary["deleted"])],
        ["Currently booked", str(summary["booked"])],
        ["Available now", str(summary["available"])],
        [f"Records in {SOURCE_LOG_FILE}", str(len(log_entries))],
        ["Binary files valid",
         "PASS" if store_valid and log_valid else "FAIL"],
        ["Report consistency",
         "PASS" if all(checks_pass) else "CHECK DATA"],
        ["Source files",
         f"{SOURCE_POINT_FILE}, {SOURCE_LOG_FILE}"],
    ]

    lines.append("")
    lines.extend(_summary_section(summary_rows))
    return lines


# ---------------------------------------------------------------------------
# Report 2 - Charging Statistics Report
# ---------------------------------------------------------------------------
def build_report_stats(
    data_dir: str,
    points: Sequence[models.ChargePoint],
    log_entries: Sequence[models.LogEntry],
    index_map: Dict[int, int],
    store_valid: bool = True,
    log_valid: bool = True,
    index_valid: bool = True,
    locations: Optional[Dict[int, str]] = None,
) -> List[str]:
    """รายงานสถิติรวมราคา กำลังไฟ connector และกิจกรรม"""
    active_points = [
        p for p in points
        if not p.is_deleted and p.status == 1
    ]

    powers = [p.power_kw for p in active_points]
    prices = [p.price_per_kwh for p in active_points]
    count = len(active_points)

    avg_power = sum(powers) / count if count else 0.0
    avg_price = sum(prices) / count if count else 0.0
    min_power = min(powers) if powers else 0.0
    max_power = max(powers) if powers else 0.0
    min_price = min(prices) if prices else 0.0
    max_price = max(prices) if prices else 0.0

    plug_counts: Dict[str, int] = {}
    for point in active_points:
        plug_counts[point.plug_type] = plug_counts.get(point.plug_type, 0) + 1

    op_counts = {
        models.OP_ADD: 0,
        models.OP_UPDATE: 0,
        models.OP_DELETE: 0,
        models.OP_VIEW: 0,
    }
    for entry in log_entries:
        if entry.op_code in op_counts:
            op_counts[entry.op_code] += 1

    recent = list(log_entries[-RECENT_ACTIVITY_LIMIT:])
    recent_events = len(recent)

    lines = _header(
        data_dir,
        "Charging Statistics Summary",
        "สรุปสถิติราคา กำลังไฟ ประเภทหัวต่อ และกิจกรรมของระบบ",
        [SOURCE_POINT_FILE, SOURCE_LOG_FILE],
    )
    lines.append("")

    lines.extend(_table_details(
        "Charging statistics",
        "สรุปสถิติหัวชาร์จที่ใช้งาน ราคา กำลังไฟ ประเภท connector และกิจกรรมล่าสุด",
        [
            ("Metric", "หัวข้อของสถิติ", "charge_points.dat"),
            ("Value", "ค่าที่คำนวณได้จากข้อมูล", "charge_points.dat"),
            ("Log events", "จำนวนเหตุการณ์จาก audit log", SOURCE_LOG_FILE),
        ],
        [SOURCE_POINT_FILE, SOURCE_LOG_FILE],
    ))

    # ตารางเดียวรวมสถิติจาก charge_points.dat และ charge_points.log
    stat_rows = [
        ["Active charging points", str(count), SOURCE_POINT_FILE],
        ["Minimum price (THB/kWh)", f"{min_price:.2f}", SOURCE_POINT_FILE],
        ["Maximum price (THB/kWh)", f"{max_price:.2f}", SOURCE_POINT_FILE],
        ["Average price (THB/kWh)", f"{avg_price:.2f}", SOURCE_POINT_FILE],
        ["Minimum power (kW)", f"{min_power:.1f}", SOURCE_POINT_FILE],
        ["Maximum power (kW)", f"{max_power:.1f}", SOURCE_POINT_FILE],
        ["Average power (kW)", f"{avg_power:.1f}", SOURCE_POINT_FILE],
        ["CCS2 count", str(plug_counts.get("CCS2", 0)), SOURCE_POINT_FILE],
        ["Type2 count", str(plug_counts.get("Type2", 0)), SOURCE_POINT_FILE],
        ["CHAdeMO count", str(plug_counts.get("CHAdeMO", 0)), SOURCE_POINT_FILE],
        ["GB-T count", str(plug_counts.get("GB-T", 0)), SOURCE_POINT_FILE],
        ["ADD events", str(op_counts[models.OP_ADD]), SOURCE_LOG_FILE],
        ["UPDATE events", str(op_counts[models.OP_UPDATE]), SOURCE_LOG_FILE],
        ["DELETE events", str(op_counts[models.OP_DELETE]), SOURCE_LOG_FILE],
        ["VIEW events", str(op_counts[models.OP_VIEW]), SOURCE_LOG_FILE],
        ["Total log events", str(len(log_entries)), SOURCE_LOG_FILE],
        ["Recent log events", str(recent_events), SOURCE_LOG_FILE],
    ]

    lines.append("Statistics")
    lines.append("-" * 62)
    lines.extend(render_table(
        ["Metric", "Value", "Source file"],
        stat_rows,
        max_width=MAIN_TABLE_MAX_WIDTH,
    ))

    connector_total = sum(plug_counts.values())
    operation_total = sum(op_counts.values())
    average_ok = bool(prices) and min_price <= avg_price <= max_price
    checks = [
        connector_total == count,
        operation_total == len(log_entries),
        recent_events == len(recent),
        average_ok,
    ]

    most_common_connector = "-"
    if plug_counts:
        most_common_connector = max(
            plug_counts,
            key=plug_counts.get,
        )

    summary_rows = [
        ["Active points used", str(count)],
        ["Average price (THB/kWh)", f"{avg_price:.2f}"],
        ["Average power (kW)", f"{avg_power:.1f}"],
        ["Most common connector", most_common_connector],
        ["Total connector records", str(connector_total)],
        ["Total log events", str(len(log_entries))],
        ["Recent log events", str(recent_events)],
        ["Binary files valid",
         "PASS" if store_valid and log_valid else "FAIL"],
        ["Statistics consistency",
         "PASS" if all(checks) else "CHECK DATA"],
        ["Source files",
         f"{SOURCE_POINT_FILE}, {SOURCE_LOG_FILE}"],
    ]

    lines.append("")
    lines.extend(_summary_section(summary_rows))
    return lines


# ---------------------------------------------------------------------------
# Report 3 - System Report
# ---------------------------------------------------------------------------
def build_report_system(
    data_dir: str,
    points: Sequence[models.ChargePoint],
    log_entries: Sequence[models.LogEntry],
    index_map: Dict[int, int],
    store_valid: bool = True,
    log_valid: bool = True,
    index_valid: bool = True,
    locations: Optional[Dict[int, str]] = None,
) -> List[str]:
    """รายงานสถานะของ Binary files หลัก 2 ไฟล์: data และ log

    index_map/index_valid ยังรับไว้เพื่อให้เข้ากับ main.py เดิม
    แต่จะไม่ถูกนำมาใช้หรือแสดงในรายงาน
    """
    lines = _header(
        data_dir,
        "System Summary",
        "ตรวจสอบสถานะ Binary files หลักและความสัมพันธ์ระหว่างข้อมูลหัวชาร์จกับ audit log",
        [SOURCE_POINT_FILE, SOURCE_LOG_FILE],
    )
    lines.append("")

    lines.extend(_table_details(
        "Binary file status",
        "ตรวจสอบสถานะของ charge_points.dat และ charge_points.log",
        [
            ("File", "ชื่อ Binary file", "Binary file"),
            ("Record size", "ขนาด record ต่อรายการ", "Binary format"),
            ("Count", "จำนวน records ที่อ่านได้", "แต่ละ Binary file"),
            ("Status", "ผลตรวจสอบไฟล์", "แต่ละ Binary file"),
        ],
        [SOURCE_POINT_FILE, SOURCE_LOG_FILE],
    ))

    data_ids = {p.point_id for p in points}
    log_ids = {entry.point_id for entry in log_entries}
    data_without_log = sorted(data_ids - log_ids)

    file_rows = [
        [
            SOURCE_POINT_FILE,
            f"{models.RECORD_SIZE} bytes",
            str(len(points)),
            "PASS" if store_valid else "INVALID",
            "Primary charging-point data",
        ],
        [
            SOURCE_LOG_FILE,
            f"{models.LOG_RECORD_SIZE} bytes",
            str(len(log_entries)),
            "PASS" if log_valid else "INVALID",
            "Audit/history events",
        ],
        [
            "Data vs Log",
            "-",
            str(len(data_without_log)),
            "PASS" if not data_without_log else "CHECK",
            "Point IDs with no log history",
        ],
    ]

    lines.append("System File Status")
    lines.append("-" * 62)
    lines.extend(render_table(
        ["File / Check", "Record size", "Count", "Status", "Meaning"],
        file_rows,
        max_width=MAIN_TABLE_MAX_WIDTH,
    ))

    all_valid = store_valid and log_valid
    summary_rows = [
        [f"{SOURCE_POINT_FILE} records", str(len(points))],
        [f"{SOURCE_LOG_FILE} records", str(len(log_entries))],
        ["Point IDs without log history", str(len(data_without_log))],
        ["Binary file validation", "PASS" if all_valid else "FAIL"],
        ["Data/log validation", "PASS" if not data_without_log else "CHECK DATA"],
        ["Overall system status", "PASS" if all_valid and not data_without_log else "CHECK DATA"],
        ["Source files", f"{SOURCE_POINT_FILE}, {SOURCE_LOG_FILE}"],
    ]

    lines.append("")
    lines.extend(_summary_section(summary_rows))
    return lines


# ---------------------------------------------------------------------------
# Generate all 3 reports
# ---------------------------------------------------------------------------
def generate_all_reports(
    data_dir: str,
    points: Sequence[models.ChargePoint],
    log_entries: Sequence[models.LogEntry],
    index_map: Dict[int, int],
    store_valid: bool = True,
    log_valid: bool = True,
    index_valid: bool = True,
    locations: Optional[Dict[int, str]] = None,
) -> Dict[str, str]:
    """สร้างรายงานทั้ง 3 เป็นไฟล์ .txt แยกกัน โดยรายงานใช้ data + log เป็นแหล่งข้อมูลหลัก"""
    builders = (
        (REPORT_POINTS_NAME, build_report_points),
        (REPORT_STATS_NAME, build_report_stats),
        (REPORT_SYSTEM_NAME, build_report_system),
    )

    created: Dict[str, str] = {}
    previous_alignment = alignment_mode_name()
    set_alignment_mode(True)

    try:
        for file_name, builder in builders:
            path = os.path.join(data_dir, file_name)
            lines = builder(
                data_dir,
                points,
                log_entries,
                index_map,
                store_valid=store_valid,
                log_valid=log_valid,
                index_valid=index_valid,
                locations=locations,
            )
            _write_report(path, lines)
            created[file_name] = path
    finally:
        set_alignment_mode(previous_alignment == "smart")

    return created


def report_uses_multiple_sources(file_name: str) -> bool:
    """รายงานทั้ง 3 ใช้ข้อมูลจากหลาย Binary files"""
    return file_name in ALL_REPORT_NAMES
