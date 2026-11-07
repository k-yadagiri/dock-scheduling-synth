CREATE TABLE facilities (
  facility_id TEXT NOT NULL,
  facility_name TEXT NOT NULL,
  city TEXT NOT NULL,
  timezone TEXT NOT NULL,
  open_hour INTEGER NOT NULL,
  close_hour INTEGER NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  status TEXT NOT NULL,
  PRIMARY KEY (facility_id)
);

CREATE TABLE docks (
  dock_id TEXT NOT NULL,
  facility_id TEXT NOT NULL,
  dock_number INTEGER NOT NULL,
  dock_type TEXT NOT NULL,
  is_refrigerated INTEGER NOT NULL,
  hazmat_certified INTEGER NOT NULL,
  max_vehicle_length_m REAL NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  status TEXT NOT NULL,
  PRIMARY KEY (dock_id),
  FOREIGN KEY (facility_id) REFERENCES facilities(facility_id)
);

CREATE TABLE yard_slots (
  yard_slot_id TEXT NOT NULL,
  facility_id TEXT NOT NULL,
  slot_type TEXT NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  status TEXT NOT NULL,
  PRIMARY KEY (yard_slot_id),
  FOREIGN KEY (facility_id) REFERENCES facilities(facility_id)
);

CREATE TABLE carriers (
  carrier_id TEXT NOT NULL,
  carrier_name TEXT NOT NULL,
  scac_code TEXT NOT NULL,
  hazmat_certified INTEGER NOT NULL,
  on_time_score REAL NOT NULL,
  status TEXT NOT NULL,
  PRIMARY KEY (carrier_id)
);

CREATE TABLE vehicles (
  vehicle_id TEXT NOT NULL,
  carrier_id TEXT NOT NULL,
  vehicle_type TEXT NOT NULL,
  is_reefer INTEGER NOT NULL,
  hazmat_certified INTEGER NOT NULL,
  length_m REAL NOT NULL,
  plate_number TEXT NOT NULL,
  PRIMARY KEY (vehicle_id),
  FOREIGN KEY (carrier_id) REFERENCES carriers(carrier_id)
);

CREATE TABLE handling_requirements (
  handling_req_id TEXT NOT NULL,
  temp_class TEXT NOT NULL,
  hazmat_class TEXT NOT NULL,
  base_service_min INTEGER NOT NULL,
  per_pallet_min REAL NOT NULL,
  requires_reefer_dock INTEGER NOT NULL,
  requires_hazmat_dock INTEGER NOT NULL,
  PRIMARY KEY (handling_req_id)
);

CREATE TABLE dock_handling_capabilities (
  dock_id TEXT NOT NULL,
  handling_req_id TEXT NOT NULL,
  effective_from TEXT NOT NULL,
  PRIMARY KEY (dock_id, handling_req_id),
  FOREIGN KEY (dock_id) REFERENCES docks(dock_id),
  FOREIGN KEY (handling_req_id) REFERENCES handling_requirements(handling_req_id)
);

CREATE TABLE labor_shifts (
  shift_id TEXT NOT NULL,
  facility_id TEXT NOT NULL,
  shift_date TEXT NOT NULL,
  shift_code TEXT NOT NULL,
  shift_start TEXT NOT NULL,
  shift_end TEXT NOT NULL,
  crews_available INTEGER NOT NULL,
  status TEXT NOT NULL,
  PRIMARY KEY (shift_id),
  FOREIGN KEY (facility_id) REFERENCES facilities(facility_id)
);

CREATE TABLE appointments (
  appointment_id TEXT NOT NULL,
  facility_id TEXT NOT NULL,
  dock_id TEXT,
  carrier_id TEXT NOT NULL,
  vehicle_id TEXT NOT NULL,
  handling_req_id TEXT NOT NULL,
  direction TEXT NOT NULL,
  request_ts TEXT NOT NULL,
  requested_start TEXT NOT NULL,
  planned_start TEXT,
  planned_end TEXT,
  planned_service_min INTEGER,
  total_pallets INTEGER NOT NULL,
  total_weight_kg REAL NOT NULL,
  status TEXT NOT NULL,
  PRIMARY KEY (appointment_id),
  FOREIGN KEY (facility_id) REFERENCES facilities(facility_id),
  FOREIGN KEY (dock_id) REFERENCES docks(dock_id),
  FOREIGN KEY (carrier_id) REFERENCES carriers(carrier_id),
  FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
  FOREIGN KEY (handling_req_id) REFERENCES handling_requirements(handling_req_id)
);

CREATE TABLE shipments (
  shipment_id TEXT NOT NULL,
  appointment_id TEXT NOT NULL,
  handling_req_id TEXT NOT NULL,
  pallet_count INTEGER NOT NULL,
  weight_kg REAL NOT NULL,
  commodity TEXT NOT NULL,
  PRIMARY KEY (shipment_id),
  FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id),
  FOREIGN KEY (handling_req_id) REFERENCES handling_requirements(handling_req_id)
);

CREATE TABLE check_in_events (
  event_id TEXT NOT NULL,
  appointment_id TEXT NOT NULL,
  event_seq INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  event_ts TEXT NOT NULL,
  dock_id TEXT,
  yard_slot_id TEXT,
  resulting_status TEXT NOT NULL,
  PRIMARY KEY (event_id),
  FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id),
  FOREIGN KEY (dock_id) REFERENCES docks(dock_id),
  FOREIGN KEY (yard_slot_id) REFERENCES yard_slots(yard_slot_id)
);

CREATE TABLE exceptions (
  exception_id TEXT NOT NULL,
  appointment_id TEXT NOT NULL,
  facility_id TEXT NOT NULL,
  exception_type TEXT NOT NULL,
  cause_code TEXT NOT NULL,
  severity TEXT NOT NULL,
  detected_ts TEXT NOT NULL,
  minutes_impact INTEGER NOT NULL,
  description TEXT NOT NULL,
  PRIMARY KEY (exception_id),
  FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id),
  FOREIGN KEY (facility_id) REFERENCES facilities(facility_id)
);
