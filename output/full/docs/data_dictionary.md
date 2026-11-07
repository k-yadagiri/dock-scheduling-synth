# Data Dictionary

All timestamps are facility-local naive ISO-8601 (`YYYY-MM-DDTHH:MM:SS`); dates `YYYY-MM-DD`; booleans `true/false`; empty = NULL.

## Facility  (`facilities.csv`)
PK: `facility_id`

| Field | Type | Required | Allowed values / pattern | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| facility_id | string | Y | `^FAC-\d{3}$` |  | Y | PK |
| facility_name | string | Y |  |  |  |  |
| city | string | Y |  |  |  |  |
| timezone | string | Y |  |  |  | IANA tz; all timestamps are facility-local naive ISO-8601 |
| open_hour | int | Y |  | hour |  | 0..23 |
| close_hour | int | Y |  | hour |  | > open_hour, <= 23 |
| effective_from | date | Y |  |  |  | <= effective_to |
| effective_to | date | N |  |  |  | NULL = open-ended |
| status | string | Y | ACTIVE, INACTIVE |  |  |  |

## Dock  (`docks.csv`)
PK: `dock_id` | FKs: `facility_id`->Facility.facility_id

| Field | Type | Required | Allowed values / pattern | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| dock_id | string | Y | `^DOCK-FAC-\d{3}-\d{3}$` |  | Y | PK; DOCK-<facility-id>-NNN |
| facility_id | string | Y |  |  |  | FK Facility |
| dock_number | int | Y |  |  |  | >=1; unique within facility |
| dock_type | string | Y | INBOUND, OUTBOUND, FLEX |  |  | appointment direction must equal dock_type or dock_type=FLEX |
| is_refrigerated | bool | Y |  |  |  |  |
| hazmat_certified | bool | Y |  |  |  |  |
| max_vehicle_length_m | float | Y |  | m |  | vehicle.length_m <= this |
| effective_from | date | Y |  |  |  | <= effective_to |
| effective_to | date | N |  |  |  | NULL = open-ended |
| status | string | Y | ACTIVE, MAINTENANCE |  |  |  |

## YardSlot  (`yard_slots.csv`)
PK: `yard_slot_id` | FKs: `facility_id`->Facility.facility_id

| Field | Type | Required | Allowed values / pattern | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| yard_slot_id | string | Y | `^YARD-FAC-\d{3}-\d{2}$` |  | Y | PK |
| facility_id | string | Y |  |  |  | FK Facility |
| slot_type | string | Y | STANDARD, REEFER_PLUG, HAZMAT_ZONE |  |  |  |
| effective_from | date | Y |  |  |  | <= effective_to |
| effective_to | date | N |  |  |  | NULL = open-ended |
| status | string | Y | ACTIVE, MAINTENANCE |  |  |  |

## Carrier  (`carriers.csv`)
PK: `carrier_id`

| Field | Type | Required | Allowed values / pattern | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| carrier_id | string | Y | `^CAR-\d{3}$` |  | Y | PK |
| carrier_name | string | Y |  |  |  |  |
| scac_code | string | Y |  |  | Y | 4 upper-case letters |
| hazmat_certified | bool | Y |  |  |  |  |
| on_time_score | float | Y |  | ratio |  | 0..1; drives no-show/late probability in simulation |
| status | string | Y | ACTIVE, SUSPENDED |  |  |  |

## Vehicle  (`vehicles.csv`)
PK: `vehicle_id` | FKs: `carrier_id`->Carrier.carrier_id

| Field | Type | Required | Allowed values / pattern | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| vehicle_id | string | Y | `^VEH-\d{5}$` |  | Y | PK |
| carrier_id | string | Y |  |  |  | FK Carrier |
| vehicle_type | string | Y | DRY_VAN, REEFER, TANKER, FLATBED |  |  |  |
| is_reefer | bool | Y |  |  |  | true iff vehicle_type=REEFER |
| hazmat_certified | bool | Y |  |  |  | only if carrier hazmat_certified |
| length_m | float | Y |  | m |  |  |
| plate_number | string | Y |  |  | Y |  |

## HandlingRequirement  (`handling_requirements.csv`)
PK: `handling_req_id`

| Field | Type | Required | Allowed values / pattern | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| handling_req_id | string | Y | `^HR-\d{3}$` |  | Y | PK |
| temp_class | string | Y | AMBIENT, CHILLED, FROZEN |  |  |  |
| hazmat_class | string | Y | NONE, FLAMMABLE, CORROSIVE |  |  |  |
| base_service_min | int | Y |  | min |  | >0 |
| per_pallet_min | float | Y |  | min/pallet |  | >0 |
| requires_reefer_dock | bool | Y |  |  |  | temp_class != AMBIENT |
| requires_hazmat_dock | bool | Y |  |  |  | hazmat_class != NONE |

## DockHandlingCapability  (`dock_handling_capabilities.csv`)
PK: `dock_id, handling_req_id` | FKs: `dock_id`->Dock.dock_id, `handling_req_id`->HandlingRequirement.handling_req_id

| Field | Type | Required | Allowed values / pattern | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| dock_id | string | Y |  |  |  | FK Dock |
| handling_req_id | string | Y |  |  |  | FK HandlingRequirement |
| effective_from | date | Y |  |  |  |  |

## LaborShift  (`labor_shifts.csv`)
PK: `shift_id` | FKs: `facility_id`->Facility.facility_id

| Field | Type | Required | Allowed values / pattern | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| shift_id | string | Y | `^SHIFT-FAC-\d{3}-\d{8}-[EL]$` |  | Y | PK |
| facility_id | string | Y |  |  |  | FK Facility |
| shift_date | date | Y |  |  |  |  |
| shift_code | string | Y | EARLY, LATE |  |  |  |
| shift_start | datetime | Y |  |  |  | < shift_end |
| shift_end | datetime | Y |  |  |  |  |
| crews_available | int | Y |  | crews |  | >=0; one crew serves one appointment at a time |
| status | string | Y | SCHEDULED, CANCELLED |  |  |  |

## Appointment  (`appointments.csv`)
PK: `appointment_id` | FKs: `facility_id`->Facility.facility_id, `dock_id`->Dock.dock_id, `carrier_id`->Carrier.carrier_id, `vehicle_id`->Vehicle.vehicle_id, `handling_req_id`->HandlingRequirement.handling_req_id

| Field | Type | Required | Allowed values / pattern | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| appointment_id | string | Y | `^APPT-2026-\d{6}$` |  | Y | PK |
| facility_id | string | Y |  |  |  | FK |
| dock_id | string | N |  |  |  | FK; NULL iff REJECTED; dock facility must equal facility_id |
| carrier_id | string | Y |  |  |  | FK; must equal vehicle.carrier_id |
| vehicle_id | string | Y |  |  |  | FK |
| handling_req_id | string | Y |  |  |  | FK; equals handling_req_id of all child shipments |
| direction | string | Y | INBOUND, OUTBOUND |  |  |  |
| request_ts | datetime | Y |  |  |  | < requested_start |
| requested_start | datetime | Y |  |  |  |  |
| planned_start | datetime | N |  |  |  | >= request_ts; within facility hours |
| planned_end | datetime | N |  |  |  | planned_start + planned_service_min |
| planned_service_min | int | N |  | min |  | ceil5(base_service_min + total_pallets*per_pallet_min) |
| total_pallets | int | Y |  | pallets |  | = SUM(shipment.pallet_count) |
| total_weight_kg | float | Y |  | kg |  | = SUM(shipment.weight_kg) |
| status | string | Y | SCHEDULED, COMPLETED, NO_SHOW, REJECTED |  |  | current state; must equal outcome of last CheckInEvent |

## Shipment  (`shipments.csv`)
PK: `shipment_id` | FKs: `appointment_id`->Appointment.appointment_id, `handling_req_id`->HandlingRequirement.handling_req_id

| Field | Type | Required | Allowed values / pattern | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| shipment_id | string | Y | `^SHP-2026-\d{6}$` |  | Y | PK |
| appointment_id | string | Y |  |  |  | FK |
| handling_req_id | string | Y |  |  |  | FK |
| pallet_count | int | Y |  | pallets |  | >0 |
| weight_kg | float | Y |  | kg |  | >0 |
| commodity | string | Y |  |  |  |  |

## CheckInEvent  (`check_in_events.csv`)
PK: `event_id` | FKs: `appointment_id`->Appointment.appointment_id, `dock_id`->Dock.dock_id, `yard_slot_id`->YardSlot.yard_slot_id

| Field | Type | Required | Allowed values / pattern | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| event_id | string | Y | `^CHECK-APPT-2026-\d{6}-\d{2}$` |  | Y | PK; CHECK-<appointment-id>-<seq> |
| appointment_id | string | Y |  |  |  | FK |
| event_seq | int | Y |  |  |  | 1..n contiguous per appointment |
| event_type | string | Y | SCHEDULED, CHECK_IN, YARD_ASSIGNED, SERVICE_START, SERVICE_END, DEPARTED, NO_SHOW, REJECTED |  |  |  |
| event_ts | datetime | Y |  |  |  | non-decreasing in event_seq |
| dock_id | string | N |  |  |  | FK |
| yard_slot_id | string | N |  |  |  | FK; NULL if yard full |
| resulting_status | string | Y | SCHEDULED, CHECKED_IN, YARDED, IN_SERVICE, SERVICE_COMPLETE, DEPARTED, NO_SHOW, REJECTED |  |  | must follow TRANSITIONS; append-only, never updated |

## Exception  (`exceptions.csv`)
PK: `exception_id` | FKs: `appointment_id`->Appointment.appointment_id, `facility_id`->Facility.facility_id

| Field | Type | Required | Allowed values / pattern | Unit | Unique | Validation rule |
|---|---|---|---|---|---|---|
| exception_id | string | Y | `^EXC-2026-\d{6}$` |  | Y | PK |
| appointment_id | string | Y |  |  |  | FK |
| facility_id | string | Y |  |  |  | FK |
| exception_type | string | Y | NO_SHOW, EARLY_ARRIVAL, LATE_ARRIVAL, DOCK_CONGESTION, GATE_CONGESTION, YARD_FULL, REJECTED_NO_CAPACITY |  |  |  |
| cause_code | string | Y | CARRIER_EARLY, CARRIER_LATE, CARRIER_NO_SHOW, LABOR_CAPACITY, NO_DOCK_CAPACITY, PEAK_GATE_QUEUE, PRIOR_OVERRUN, YARD_CAPACITY |  |  | must be valid for exception_type (CAUSE_BY_TYPE) |
| severity | string | Y | LOW, MEDIUM, HIGH |  |  |  |
| detected_ts | datetime | Y |  |  |  |  |
| minutes_impact | int | Y |  | min |  | >=0 |
| description | string | Y |  |  |  |  |

## Relationships / cardinality

- Facility 1:N Dock (dock.facility_id) - mandatory
- Facility 1:N YardSlot - mandatory
- Facility 1:N LaborShift - mandatory
- Carrier 1:N Vehicle - mandatory
- Dock N:M HandlingRequirement via DockHandlingCapability (bridge)
- Facility 1:N Appointment; Dock 1:N Appointment (optional: NULL when REJECTED); Carrier 1:N Appointment; Vehicle 1:N Appointment
- HandlingRequirement 1:N Appointment and 1:N Shipment
- Appointment 1:N Shipment (1-2 shipments each, mandatory)
- Appointment 1:N CheckInEvent (append-only lifecycle history, 1-6 events)
- CheckInEvent N:1 Dock and N:1 YardSlot (both optional)
- Appointment 1:N Exception (0..n, optional); Facility 1:N Exception

## Lifecycle (CheckInEvent.resulting_status)

Allowed transitions: START -> REJECTED, SCHEDULED; SCHEDULED -> CHECKED_IN, NO_SHOW; CHECKED_IN -> YARDED; YARDED -> IN_SERVICE; IN_SERVICE -> SERVICE_COMPLETE; SERVICE_COMPLETE -> DEPARTED; DEPARTED -> END; NO_SHOW -> END; REJECTED -> END

## ID conventions

`FAC-001`, `DOCK-FAC-001-001`, `YARD-FAC-001-01`, `CAR-001`, `VEH-00001`, `HR-001`, `APPT-2026-000001`, `SHP-2026-000001`, `CHECK-APPT-2026-000001-01`, `EXC-2026-000001`, `SHIFT-FAC-001-20260901-E`. Counters zero-padded, immutable.

## Injected anomalies (ground_truth/ground_truth.csv, never in input tables)

- `OVERLAPPING_APPOINTMENT_EXCEEDS_DOCK_CAPACITY`
- `INCOMPATIBLE_LOAD_ASSIGNED`
- `CHECKIN_BEFORE_APPOINTMENT_DATE`
- `LABOR_SHIFT_NOT_AVAILABLE`
- `NO_SHOW_NOT_RECORDED`
