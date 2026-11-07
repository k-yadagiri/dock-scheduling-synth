"""Single source of truth: data dictionary, enums, FKs, lifecycle. Drives generator, SQL, docs and validator."""
DIR = ["INBOUND", "OUTBOUND"]
DOCK_TYPES = ["INBOUND", "OUTBOUND", "FLEX"]
TEMP = ["AMBIENT", "CHILLED", "FROZEN"]
HAZ = ["NONE", "FLAMMABLE", "CORROSIVE"]
YARD_TYPES = ["STANDARD", "REEFER_PLUG", "HAZMAT_ZONE"]
VEH_TYPES = ["DRY_VAN", "REEFER", "TANKER", "FLATBED"]
APPT_STATUS = ["SCHEDULED", "COMPLETED", "NO_SHOW", "REJECTED"]
LIFECYCLE = ["SCHEDULED", "CHECKED_IN", "YARDED", "IN_SERVICE", "SERVICE_COMPLETE", "DEPARTED", "NO_SHOW", "REJECTED"]
EVENT_TYPES = ["SCHEDULED", "CHECK_IN", "YARD_ASSIGNED", "SERVICE_START", "SERVICE_END", "DEPARTED", "NO_SHOW", "REJECTED"]
EVENT_RESULT = dict(zip(EVENT_TYPES, ["SCHEDULED", "CHECKED_IN", "YARDED", "IN_SERVICE", "SERVICE_COMPLETE", "DEPARTED", "NO_SHOW", "REJECTED"]))
TRANSITIONS = {None: {"SCHEDULED", "REJECTED"}, "SCHEDULED": {"CHECKED_IN", "NO_SHOW"}, "CHECKED_IN": {"YARDED"},
               "YARDED": {"IN_SERVICE"}, "IN_SERVICE": {"SERVICE_COMPLETE"}, "SERVICE_COMPLETE": {"DEPARTED"},
               "DEPARTED": set(), "NO_SHOW": set(), "REJECTED": set()}
FINAL_TO_APPT = {"DEPARTED": "COMPLETED", "NO_SHOW": "NO_SHOW", "REJECTED": "REJECTED", "SCHEDULED": "SCHEDULED"}
EXC_TYPES = ["NO_SHOW", "EARLY_ARRIVAL", "LATE_ARRIVAL", "DOCK_CONGESTION", "GATE_CONGESTION", "YARD_FULL", "REJECTED_NO_CAPACITY"]
CAUSE_BY_TYPE = {"NO_SHOW": ["CARRIER_NO_SHOW"], "EARLY_ARRIVAL": ["CARRIER_EARLY"], "LATE_ARRIVAL": ["CARRIER_LATE"],
                 "DOCK_CONGESTION": ["PRIOR_OVERRUN"], "GATE_CONGESTION": ["PEAK_GATE_QUEUE"], "YARD_FULL": ["YARD_CAPACITY"],
                 "REJECTED_NO_CAPACITY": ["NO_DOCK_CAPACITY", "LABOR_CAPACITY"]}
CAUSES = sorted({c for v in CAUSE_BY_TYPE.values() for c in v})
SEV = ["LOW", "MEDIUM", "HIGH"]
ISSUE_TYPES = ["OVERLAPPING_APPOINTMENT_EXCEEDS_DOCK_CAPACITY", "INCOMPATIBLE_LOAD_ASSIGNED",
               "CHECKIN_BEFORE_APPOINTMENT_DATE", "LABOR_SHIFT_NOT_AVAILABLE", "NO_SHOW_NOT_RECORDED"]


def f(name, typ, req=True, allowed=None, unit="", uniq=False, rule="", pat=None):
    return dict(name=name, type=typ, req=req, allowed=allowed, unit=unit, uniq=uniq, rule=rule, pat=pat)


EFF = [f("effective_from", "date", rule="<= effective_to"), f("effective_to", "date", False, rule="NULL = open-ended")]
ENTITIES = {
    "Facility": dict(file="facilities", pk=["facility_id"], fks={}, fields=[
        f("facility_id", "string", uniq=True, pat=r"^FAC-\d{3}$", rule="PK"), f("facility_name", "string"), f("city", "string"),
        f("timezone", "string", rule="IANA tz; all timestamps are facility-local naive ISO-8601"),
        f("open_hour", "int", unit="hour", rule="0..23"), f("close_hour", "int", unit="hour", rule="> open_hour, <= 23")] + EFF +
        [f("status", "string", allowed=["ACTIVE", "INACTIVE"])]),
    "Dock": dict(file="docks", pk=["dock_id"], fks={"facility_id": ("Facility", "facility_id")}, fields=[
        f("dock_id", "string", uniq=True, pat=r"^DOCK-FAC-\d{3}-\d{3}$", rule="PK; DOCK-<facility-id>-NNN"),
        f("facility_id", "string", rule="FK Facility"), f("dock_number", "int", rule=">=1; unique within facility"),
        f("dock_type", "string", allowed=DOCK_TYPES, rule="appointment direction must equal dock_type or dock_type=FLEX"),
        f("is_refrigerated", "bool"), f("hazmat_certified", "bool"),
        f("max_vehicle_length_m", "float", unit="m", rule="vehicle.length_m <= this"), ] + EFF +
        [f("status", "string", allowed=["ACTIVE", "MAINTENANCE"])]),
    "YardSlot": dict(file="yard_slots", pk=["yard_slot_id"], fks={"facility_id": ("Facility", "facility_id")}, fields=[
        f("yard_slot_id", "string", uniq=True, pat=r"^YARD-FAC-\d{3}-\d{2}$", rule="PK"), f("facility_id", "string", rule="FK Facility"),
        f("slot_type", "string", allowed=YARD_TYPES)] + EFF + [f("status", "string", allowed=["ACTIVE", "MAINTENANCE"])]),
    "Carrier": dict(file="carriers", pk=["carrier_id"], fks={}, fields=[
        f("carrier_id", "string", uniq=True, pat=r"^CAR-\d{3}$", rule="PK"), f("carrier_name", "string"), f("scac_code", "string", uniq=True, rule="4 upper-case letters"),
        f("hazmat_certified", "bool"), f("on_time_score", "float", unit="ratio", rule="0..1; drives no-show/late probability in simulation"),
        f("status", "string", allowed=["ACTIVE", "SUSPENDED"])]),
    "Vehicle": dict(file="vehicles", pk=["vehicle_id"], fks={"carrier_id": ("Carrier", "carrier_id")}, fields=[
        f("vehicle_id", "string", uniq=True, pat=r"^VEH-\d{5}$", rule="PK"), f("carrier_id", "string", rule="FK Carrier"),
        f("vehicle_type", "string", allowed=VEH_TYPES), f("is_reefer", "bool", rule="true iff vehicle_type=REEFER"),
        f("hazmat_certified", "bool", rule="only if carrier hazmat_certified"), f("length_m", "float", unit="m"),
        f("plate_number", "string", uniq=True)]),
    "HandlingRequirement": dict(file="handling_requirements", pk=["handling_req_id"], fks={}, fields=[
        f("handling_req_id", "string", uniq=True, pat=r"^HR-\d{3}$", rule="PK"), f("temp_class", "string", allowed=TEMP),
        f("hazmat_class", "string", allowed=HAZ), f("base_service_min", "int", unit="min", rule=">0"),
        f("per_pallet_min", "float", unit="min/pallet", rule=">0"),
        f("requires_reefer_dock", "bool", rule="temp_class != AMBIENT"), f("requires_hazmat_dock", "bool", rule="hazmat_class != NONE")]),
    "DockHandlingCapability": dict(file="dock_handling_capabilities", pk=["dock_id", "handling_req_id"],
        fks={"dock_id": ("Dock", "dock_id"), "handling_req_id": ("HandlingRequirement", "handling_req_id")}, fields=[
        f("dock_id", "string", rule="FK Dock"), f("handling_req_id", "string", rule="FK HandlingRequirement"),
        f("effective_from", "date")]),
    "LaborShift": dict(file="labor_shifts", pk=["shift_id"], fks={"facility_id": ("Facility", "facility_id")}, fields=[
        f("shift_id", "string", uniq=True, pat=r"^SHIFT-FAC-\d{3}-\d{8}-[EL]$", rule="PK"), f("facility_id", "string", rule="FK Facility"),
        f("shift_date", "date"), f("shift_code", "string", allowed=["EARLY", "LATE"]),
        f("shift_start", "datetime", rule="< shift_end"), f("shift_end", "datetime"),
        f("crews_available", "int", unit="crews", rule=">=0; one crew serves one appointment at a time"),
        f("status", "string", allowed=["SCHEDULED", "CANCELLED"])]),
    "Appointment": dict(file="appointments", pk=["appointment_id"], fks={
        "facility_id": ("Facility", "facility_id"), "dock_id": ("Dock", "dock_id"), "carrier_id": ("Carrier", "carrier_id"),
        "vehicle_id": ("Vehicle", "vehicle_id"), "handling_req_id": ("HandlingRequirement", "handling_req_id")}, fields=[
        f("appointment_id", "string", uniq=True, pat=r"^APPT-2026-\d{6}$", rule="PK"), f("facility_id", "string", rule="FK"),
        f("dock_id", "string", False, rule="FK; NULL iff REJECTED; dock facility must equal facility_id"),
        f("carrier_id", "string", rule="FK; must equal vehicle.carrier_id"), f("vehicle_id", "string", rule="FK"),
        f("handling_req_id", "string", rule="FK; equals handling_req_id of all child shipments"), f("direction", "string", allowed=DIR),
        f("request_ts", "datetime", rule="< requested_start"), f("requested_start", "datetime"),
        f("planned_start", "datetime", False, rule=">= request_ts; within facility hours"), f("planned_end", "datetime", False, rule="planned_start + planned_service_min"),
        f("planned_service_min", "int", False, unit="min", rule="ceil5(base_service_min + total_pallets*per_pallet_min)"),
        f("total_pallets", "int", unit="pallets", rule="= SUM(shipment.pallet_count)"),
        f("total_weight_kg", "float", unit="kg", rule="= SUM(shipment.weight_kg)"),
        f("status", "string", allowed=APPT_STATUS, rule="current state; must equal outcome of last CheckInEvent")]),
    "Shipment": dict(file="shipments", pk=["shipment_id"], fks={"appointment_id": ("Appointment", "appointment_id"),
        "handling_req_id": ("HandlingRequirement", "handling_req_id")}, fields=[
        f("shipment_id", "string", uniq=True, pat=r"^SHP-2026-\d{6}$", rule="PK"), f("appointment_id", "string", rule="FK"),
        f("handling_req_id", "string", rule="FK"), f("pallet_count", "int", unit="pallets", rule=">0"),
        f("weight_kg", "float", unit="kg", rule=">0"), f("commodity", "string")]),
    "CheckInEvent": dict(file="check_in_events", pk=["event_id"], fks={"appointment_id": ("Appointment", "appointment_id"),
        "dock_id": ("Dock", "dock_id"), "yard_slot_id": ("YardSlot", "yard_slot_id")}, fields=[
        f("event_id", "string", uniq=True, pat=r"^CHECK-APPT-2026-\d{6}-\d{2}$", rule="PK; CHECK-<appointment-id>-<seq>"),
        f("appointment_id", "string", rule="FK"), f("event_seq", "int", rule="1..n contiguous per appointment"),
        f("event_type", "string", allowed=EVENT_TYPES), f("event_ts", "datetime", rule="non-decreasing in event_seq"),
        f("dock_id", "string", False, rule="FK"), f("yard_slot_id", "string", False, rule="FK; NULL if yard full"),
        f("resulting_status", "string", allowed=LIFECYCLE, rule="must follow TRANSITIONS; append-only, never updated")]),
    "Exception": dict(file="exceptions", pk=["exception_id"], fks={"appointment_id": ("Appointment", "appointment_id"),
        "facility_id": ("Facility", "facility_id")}, fields=[
        f("exception_id", "string", uniq=True, pat=r"^EXC-2026-\d{6}$", rule="PK"), f("appointment_id", "string", rule="FK"),
        f("facility_id", "string", rule="FK"), f("exception_type", "string", allowed=EXC_TYPES),
        f("cause_code", "string", allowed=CAUSES, rule="must be valid for exception_type (CAUSE_BY_TYPE)"),
        f("severity", "string", allowed=SEV), f("detected_ts", "datetime"), f("minutes_impact", "int", unit="min", rule=">=0"),
        f("description", "string")]),
}
RELATIONSHIPS = [
    "Facility 1:N Dock (dock.facility_id) - mandatory", "Facility 1:N YardSlot - mandatory", "Facility 1:N LaborShift - mandatory",
    "Carrier 1:N Vehicle - mandatory", "Dock N:M HandlingRequirement via DockHandlingCapability (bridge)",
    "Facility 1:N Appointment; Dock 1:N Appointment (optional: NULL when REJECTED); Carrier 1:N Appointment; Vehicle 1:N Appointment",
    "HandlingRequirement 1:N Appointment and 1:N Shipment", "Appointment 1:N Shipment (1-2 shipments each, mandatory)",
    "Appointment 1:N CheckInEvent (append-only lifecycle history, 1-6 events)", "CheckInEvent N:1 Dock and N:1 YardSlot (both optional)",
    "Appointment 1:N Exception (0..n, optional); Facility 1:N Exception",
]
PK_COLS = {k: v["pk"] for k, v in ENTITIES.items()}
