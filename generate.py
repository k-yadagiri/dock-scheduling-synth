#!/usr/bin/env python3
"""Deterministic synthetic generator: dock/yard/labor appointment scheduling.
Usage: python generate.py --scale full --out output/full [--seed 20261022] [--verify-repro]"""
import argparse, csv, hashlib, itertools, json, math, os, random, shutil, sys, tempfile
from collections import defaultdict
from datetime import datetime, timedelta
import schema as S

BASE = datetime(2026, 9, 1)  # dataset day 0 (Tuesday)
FMT = "%Y-%m-%dT%H:%M:%S"
SCALES = {"full": dict(n_fac=10, docks_per=10, n_appt=20000, days=60),
          "starter": dict(n_fac=3, docks_per=10, n_appt=1000, days=14)}
CITIES = [("Atlanta", "America/New_York"), ("Chicago", "America/Chicago"), ("Dallas", "America/Chicago"), ("Denver", "America/Denver"),
          ("Phoenix", "America/Phoenix"), ("Seattle", "America/Los_Angeles"), ("Columbus", "America/New_York"),
          ("Memphis", "America/Chicago"), ("Reno", "America/Los_Angeles"), ("Newark", "America/New_York")]
HOUR_W = [1, 2.5, 3.5, 3, 2, 1.5, 2, 3, 3, 2.5, 2, 1.2, .8, .6, .4, .2]  # 16 operating hours, AM + early-PM peaks
WD_W = [1.0, 1.0, 1.05, 1.0, 1.1, .6, .35]
COMMODITY = {"AMBIENT": ["dry grocery", "consumer goods", "packaging", "electronics"], "CHILLED": ["dairy", "produce", "deli"],
             "FROZEN": ["frozen meals", "ice cream", "seafood"]}
HAZ_COMM = {"FLAMMABLE": "aerosols/solvents", "CORROSIVE": "cleaning chemicals"}


def tsf(m): return (BASE + timedelta(minutes=int(m))).strftime(FMT)
def dsf(d): return (BASE + timedelta(days=int(d))).strftime("%Y-%m-%d")
def ceil5(x): return int(math.ceil(round(x, 6) / 5.0) * 5)


def build(seed, n_fac, docks_per, n_appt, days, n_car=40):
    rng = random.Random(seed)
    T = {k: [] for k in S.ENTITIES}
    peak_days = set(rng.sample(range(days), max(1, days // 15)))
    # ---- master data
    facs = []
    for i in range(n_fac):
        o = [6, 6, 6, 5, 7, 6, 6, 5, 7, 6][i % 10]
        c, tz = CITIES[i % 10]
        facs.append(dict(facility_id=f"FAC-{i+1:03d}", facility_name=f"{c} Distribution Center", city=c, timezone=tz, open_hour=o,
                         close_hour=o + 16, effective_from=-400, effective_to=None, status="ACTIVE"))
    T["Facility"] = facs
    pattern = ["INBOUND"] * 3 + ["OUTBOUND"] * 3 + ["FLEX"] * 3 + ["INBOUND"]
    docks, yards, crews = [], [], {}
    for fi, fa in enumerate(facs):
        for n in range(1, docks_per + 1):
            docks.append(dict(dock_id=f"DOCK-{fa['facility_id']}-{n:03d}", facility_id=fa["facility_id"], dock_number=n,
                              dock_type=pattern[(n - 1) % 10], is_refrigerated=n % 3 == 0, hazmat_certified=n in (4, 6, 8, 9),
                              max_vehicle_length_m=14.0 if n % 2 else 17.0,
                              effective_from=20 if (n == 2 and fi % 2 == 1) else -400, effective_to=None, status="ACTIVE"))
        for k, t in enumerate(["STANDARD"] * 10 + ["REEFER_PLUG"] * 4 + ["HAZMAT_ZONE"] * 2, 1):
            yards.append(dict(yard_slot_id=f"YARD-{fa['facility_id']}-{k:02d}", facility_id=fa["facility_id"], slot_type=t,
                              effective_from=-400, effective_to=None, status="ACTIVE"))
        for d in range(days):
            for code, st, en in (("EARLY", fa["open_hour"] * 60, (fa["open_hour"] + 8) * 60), ("LATE", (fa["open_hour"] + 8) * 60, fa["close_hour"] * 60)):
                cr = rng.randint(5, 8)
                crews[(fa["facility_id"], d, code)] = cr
                T["LaborShift"].append(dict(shift_id=f"SHIFT-{fa['facility_id']}-{dsf(d).replace('-', '')}-{code[0]}", facility_id=fa["facility_id"],
                                            shift_date=d, shift_code=code, shift_start=d * 1440 + st, shift_end=d * 1440 + en,
                                            crews_available=cr, status="SCHEDULED"))
    T["Dock"], T["YardSlot"] = docks, yards
    dock_by = {d["dock_id"]: d for d in docks}
    fac_by = {f_["facility_id"]: f_ for f_ in facs}
    carriers = []
    for i in range(n_car):
        carriers.append(dict(carrier_id=f"CAR-{i+1:03d}", carrier_name=f"Carrier {i+1:03d} Freight", hazmat_certified=i % 4 == 0,
                             scac_code="".join(chr(65 + (i // 26 ** p) % 26) for p in (3, 2, 1, 0)),
                             on_time_score=round(rng.uniform(.82, .99), 3), status="ACTIVE"))
    T["Carrier"] = carriers
    vehicles, vid = [], 0
    for ca in carriers:
        for _ in range(rng.randint(6, 14)):
            vid += 1
            vt = rng.choices(S.VEH_TYPES, [.55, .25, .08, .12])[0]
            vehicles.append(dict(vehicle_id=f"VEH-{vid:05d}", carrier_id=ca["carrier_id"], vehicle_type=vt, is_reefer=vt == "REEFER",
                                 hazmat_certified=bool(ca["hazmat_certified"] and vt != "FLATBED" and rng.random() < .7),
                                 length_m=rng.choices([12.2, 13.7, 16.2], [.2, .6, .2])[0], plate_number=f"PL{vid:05d}"))
    T["Vehicle"] = vehicles
    hrs, hrw = [], []
    tw = {"AMBIENT": (20, 2.0, [.55, .045, .035]), "CHILLED": (30, 2.5, [.15, .015, .01]), "FROZEN": (35, 3.0, [.12, .03, .01])}
    for t in S.TEMP:
        for hi, h in enumerate(S.HAZ):
            b, p, w = tw[t]
            hrs.append(dict(handling_req_id=f"HR-{len(hrs)+1:03d}", temp_class=t, hazmat_class=h, base_service_min=b + (15 if hi else 0),
                            per_pallet_min=p + (.5 if hi else 0), requires_reefer_dock=t != "AMBIENT", requires_hazmat_dock=hi > 0))
            hrw.append(w[hi])
    T["HandlingRequirement"] = hrs
    hr_by = {h["handling_req_id"]: h for h in hrs}
    cap = defaultdict(set)
    for d in docks:
        for h in hrs:
            if (not h["requires_reefer_dock"] or d["is_refrigerated"]) and (not h["requires_hazmat_dock"] or d["hazmat_certified"]):
                cap[d["dock_id"]].add(h["handling_req_id"])
                T["DockHandlingCapability"].append(dict(dock_id=d["dock_id"], handling_req_id=h["handling_req_id"], effective_from=d["effective_from"]))
    vb = {h["handling_req_id"]: [v for v in vehicles if (not h["requires_reefer_dock"] or v["is_reefer"]) and
                                 (not h["requires_hazmat_dock"] or v["hazmat_certified"])] for h in hrs}
    veh_by = {v["vehicle_id"]: v for v in vehicles}
    car_by = {c["carrier_id"]: c for c in carriers}

    def dock_ok(d, hr_id, direction, vlen, day):
        return d["dock_type"] in (direction, "FLEX") and hr_id in cap[d["dock_id"]] and vlen <= d["max_vehicle_length_m"] and d["effective_from"] <= day

    # ---- appointment requests
    fw = list(itertools.accumulate(rng.uniform(.7, 1.4) for _ in facs))
    dw = list(itertools.accumulate(WD_W[(BASE + timedelta(days=d)).weekday()] * (1.8 if d in peak_days else 1) for d in range(days)))
    reqs = []
    for i in range(n_appt):
        fa = rng.choices(facs, cum_weights=fw)[0]
        d = rng.choices(range(days), cum_weights=dw)[0]
        h = rng.choices(range(16), HOUR_W)[0]
        rs = d * 1440 + (fa["open_hour"] + h) * 60 + 15 * rng.randint(0, 3)
        direction = rng.choice(S.DIR)
        hr = rng.choices(hrs, hrw)[0]
        veh = rng.choice(vb[hr["handling_req_id"]])
        pallets = rng.randint(6, 30)
        parts = [pallets] if rng.random() >= .3 else [(a := rng.randint(2, pallets - 2)), pallets - a]
        ships = []
        for p in parts:
            cm = HAZ_COMM.get(hr["hazmat_class"]) or rng.choice(COMMODITY[hr["temp_class"]])
            ships.append((p, round(p * rng.randint(250, 650) + rng.random(), 2), cm))
        reqs.append(dict(i=i, fac=fa, day=d, rs=rs, dir=direction, hr=hr, veh=veh, pallets=pallets, ships=ships,
                         rts=rs - rng.randint(2 * 1440, 10 * 1440)))
    reqs.sort(key=lambda r: (r["rts"], r["i"]))

    # ---- allocation against dock / labor / vehicle / time-window constraints
    dock_busy, veh_busy = defaultdict(list), defaultdict(list)
    labor_use, dock_load = defaultdict(int), defaultdict(int)
    fac_docks = {fa["facility_id"]: [d for d in docks if d["facility_id"] == fa["facility_id"]] for fa in facs}

    def free(lst, s, e, buf):
        return all(e + buf <= a or s >= b + buf for a, b, *_ in lst)

    def labor_ok(fa, s, e):
        for sl in range(s // 15, (e + 14) // 15):
            m = sl * 15
            code = "EARLY" if m % 1440 < (fa["open_hour"] + 8) * 60 else "LATE"
            if labor_use[(fa["facility_id"], sl)] >= crews[(fa["facility_id"], m // 1440, code)]:
                return False
        return True

    appts, shipments, ev, ssn = [], [], {}, 0
    for n, r in enumerate(reqs, 1):
        fa, hr, veh = r["fac"], r["hr"], r["veh"]
        aid = f"APPT-2026-{n:06d}"
        svc = ceil5(hr["base_service_min"] + r["pallets"] * hr["per_pallet_min"])
        close = r["day"] * 1440 + fa["close_hour"] * 60
        cands = sorted([d for d in fac_docks[fa["facility_id"]] if dock_ok(d, hr["handling_req_id"], r["dir"], veh["length_m"], r["day"])],
                       key=lambda d: (dock_load[d["dock_id"]], d["dock_number"]))
        got, labor_blocked = None, False
        for t in range(r["rs"], r["rs"] + 360 + 1, 15):
            if t + svc > close:
                break
            if not free(veh_busy[(veh["vehicle_id"], t // 1440)], t, t + svc, 30):
                continue
            dk = [d for d in cands if free(dock_busy[(d["dock_id"], t // 1440)], t, t + svc, 5)]
            if not dk:
                continue
            if not labor_ok(fa, t, t + svc):
                labor_blocked = True
                continue
            got = (t, dk[0])
            break
        a = dict(appointment_id=aid, facility_id=fa["facility_id"], dock_id=None, carrier_id=veh["carrier_id"], vehicle_id=veh["vehicle_id"],
                 handling_req_id=hr["handling_req_id"], direction=r["dir"], request_ts=r["rts"], requested_start=r["rs"], planned_start=None,
                 planned_end=None, planned_service_min=None, total_pallets=r["pallets"], total_weight_kg=round(sum(s[1] for s in r["ships"]), 2),
                 status="SCHEDULED", _day=r["day"], _rej=None)
        if got:
            t, d = got
            a.update(dock_id=d["dock_id"], planned_start=t, planned_end=t + svc, planned_service_min=svc)
            dock_busy[(d["dock_id"], t // 1440)].append((t, t + svc, aid))
            veh_busy[(veh["vehicle_id"], t // 1440)].append((t, t + svc))
            dock_load[d["dock_id"]] += svc
            for sl in range(t // 15, (t + svc + 14) // 15):
                labor_use[(fa["facility_id"], sl)] += 1
        else:
            a["_rej"] = "LABOR_CAPACITY" if labor_blocked else "NO_DOCK_CAPACITY"
        appts.append(a)
        for p, w, cm in r["ships"]:
            ssn += 1
            shipments.append(dict(shipment_id=f"SHP-2026-{ssn:06d}", appointment_id=aid, handling_req_id=hr["handling_req_id"], pallet_count=p, weight_kg=w, commodity=cm))
    T["Shipment"] = shipments

    # ---- simulate check-in, yard, service, departure (+ no-shows, early arrivals, congestion)
    sim, excs = {}, []

    def exc(a, typ, cause, sev, ts, impact, desc):
        excs.append(dict(appointment_id=a["appointment_id"], facility_id=a["facility_id"], exception_type=typ, cause_code=cause,
                         severity=sev, detected_ts=ts, minutes_impact=int(impact), description=desc))

    for a in appts:
        if a["dock_id"] is None:
            continue
        sc = car_by[a["carrier_id"]]["on_time_score"]
        s = dict(noshow=rng.random() < (1 - sc) * .5)
        if not s["noshow"]:
            r = rng.random()
            off = -rng.randint(15, 150) if r < .18 else rng.randint(20, 150) if r < .18 + (1 - sc) * 1.2 else rng.randint(-10, 10)
            s["checkin"] = max(a["planned_start"] + off, a["_day"] * 1440)
            peak = a["_day"] in peak_days and 8 <= (a["planned_start"] % 1440) // 60 <= 15
            s["gate"] = rng.randint(10, 45) if (peak and rng.random() < .3) else rng.randint(2, 6)
            s["dur"] = max(10, round(a["planned_service_min"] * min(1.8, max(.7, rng.lognormvariate(0, .2)))))
            s["depart"] = rng.randint(8, 25)
        sim[a["appointment_id"]] = s
    by_dock = defaultdict(list)
    for a in appts:
        if a["dock_id"] and not sim[a["appointment_id"]]["noshow"]:
            by_dock[a["dock_id"]].append(a)
    for lst in by_dock.values():
        prev = -10 ** 9
        for a in sorted(lst, key=lambda x: (x["planned_start"], x["appointment_id"])):
            s = sim[a["appointment_id"]]
            s["yard_ts"] = s["checkin"] + s["gate"]
            ready = s["yard_ts"] + 8
            s["delay"] = max(0, prev + 5 - max(ready, a["planned_start"]))
            s["start"] = max(ready, a["planned_start"], prev + 5)
            s["end"] = s["start"] + s["dur"]
            s["dep"] = s["end"] + s["depart"]
            prev = s["end"]
    free_at = defaultdict(lambda: -10 ** 9)
    ordered = sorted((a for a in appts if a["dock_id"] and not sim[a["appointment_id"]]["noshow"]),
                     key=lambda x: (sim[x["appointment_id"]]["yard_ts"], x["appointment_id"]))
    yard_by = defaultdict(list)
    for y in yards:
        yard_by[(y["facility_id"], y["slot_type"])].append(y["yard_slot_id"])
    for a in ordered:
        h, s = hr_by[a["handling_req_id"]], sim[a["appointment_id"]]
        typ = "HAZMAT_ZONE" if h["requires_hazmat_dock"] else "REEFER_PLUG" if h["requires_reefer_dock"] else "STANDARD"
        s["yard"] = None
        for ys in yard_by[(a["facility_id"], typ)]:
            if free_at[ys] <= s["yard_ts"]:
                s["yard"], free_at[ys] = ys, s["start"]
                break
    outcomes = []
    for a in appts:
        aid, s = a["appointment_id"], sim.get(a["appointment_id"])
        e = []
        lab = "COMPLETED_ON_TIME"
        flags = dict(is_early=False, is_late=False, is_congested=False)
        if a["dock_id"] is None:
            e.append(("REJECTED", a["request_ts"] + 1, None, None))
            a["status"] = "REJECTED"
            exc(a, "REJECTED_NO_CAPACITY", a["_rej"], "MEDIUM", a["request_ts"] + 1, 0, f"No compatible slot within +6h of requested start ({a['_rej']})")
            lab = "REJECTED_NO_CAPACITY"
        elif s["noshow"]:
            e += [("SCHEDULED", a["request_ts"] + 2, a["dock_id"], None), ("NO_SHOW", a["planned_start"] + 60, a["dock_id"], None)]
            a["status"] = "NO_SHOW"
            exc(a, "NO_SHOW", "CARRIER_NO_SHOW", "HIGH" if hr_by[a["handling_req_id"]]["requires_reefer_dock"] else "MEDIUM",
                a["planned_start"] + 60, a["planned_service_min"], "Vehicle did not arrive within 60-minute grace window")
            lab = "NO_SHOW"
        else:
            dk = a["dock_id"]
            e += [("SCHEDULED", a["request_ts"] + 2, dk, None), ("CHECK_IN", s["checkin"], dk, None), ("YARD_ASSIGNED", s["yard_ts"], dk, s["yard"]),
                  ("SERVICE_START", s["start"], dk, None), ("SERVICE_END", s["end"], dk, None), ("DEPARTED", s["dep"], dk, None)]
            a["status"] = "COMPLETED"
            early, late = a["planned_start"] - s["checkin"], s["checkin"] - a["planned_start"]
            if early >= 30:
                exc(a, "EARLY_ARRIVAL", "CARRIER_EARLY", "LOW", s["checkin"], early, f"Arrived {early} min before planned start"); flags["is_early"] = True
            if late >= 30:
                exc(a, "LATE_ARRIVAL", "CARRIER_LATE", "MEDIUM", s["checkin"], late, f"Arrived {late} min after planned start"); flags["is_late"] = True
            if s["gate"] >= 20:
                exc(a, "GATE_CONGESTION", "PEAK_GATE_QUEUE", "MEDIUM" if s["gate"] < 35 else "HIGH", s["checkin"], s["gate"], f"Gate queue {s['gate']} min on peak day"); flags["is_congested"] = True
            if s["yard"] is None:
                exc(a, "YARD_FULL", "YARD_CAPACITY", "MEDIUM", s["yard_ts"], 0, "No compatible yard slot free at yard assignment"); flags["is_congested"] = True
            if s["delay"] >= 15:
                exc(a, "DOCK_CONGESTION", "PRIOR_OVERRUN", "HIGH" if s["delay"] >= 45 else "MEDIUM", s["start"], s["delay"], f"Dock still occupied by prior appointment; service delayed {s['delay']} min"); flags["is_congested"] = True
            lab = "LATE_ARRIVAL" if flags["is_late"] else "EARLY_ARRIVAL" if flags["is_early"] else "CONGESTED" if flags["is_congested"] else lab
        ev[aid] = [dict(event_id=f"CHECK-{aid}-{q:02d}", appointment_id=aid, event_seq=q, event_type=t, event_ts=ts, dock_id=dk, yard_slot_id=ys,
                        resulting_status=S.EVENT_RESULT[t]) for q, (t, ts, dk, ys) in enumerate(e, 1)]
        outcomes.append(dict(appointment_id=aid, outcome_label=lab, is_no_show=a["status"] == "NO_SHOW", is_rejected=a["status"] == "REJECTED", **flags))

    # ---- labelled anomaly injection (ground truth kept separate)
    gt, used = [], set()
    ab = {a["appointment_id"]: a for a in appts}
    idx = defaultdict(list)
    for a in appts:
        if a["dock_id"]:
            idx[(a["dock_id"], a["planned_start"] // 1440)].append(a["appointment_id"])
    k = max(2, round(n_appt * .002))
    completed = [a for a in appts if a["status"] == "COMPLETED"]
    ex_by = defaultdict(list)
    for x in excs:
        ex_by[x["appointment_id"]].append(x)

    def checkin(a): return next(x["event_ts"] for x in ev[a["appointment_id"]] if x["event_type"] == "CHECK_IN")

    def dock_free(dock, s, e, ignore):
        return all(ab[o]["planned_end"] + 5 <= s or e + 5 <= ab[o]["planned_start"] for o in idx[(dock, s // 1440)] if o not in ignore)

    vl = defaultdict(list)
    for a in appts:
        vl[a["vehicle_id"]].append(a["appointment_id"])

    def can_move(a, ps, dock, ignore=()):
        delta = ps - a["planned_start"]
        pe = ps + a["planned_service_min"]
        if any(ab[o]["planned_start"] is not None and ab[o]["planned_start"] - 30 < pe and ps < ab[o]["planned_end"] + 30
               for o in vl[a["vehicle_id"]] if o != a["appointment_id"]):
            return False
        return (checkin(a) + delta) // 1440 >= ps // 1440 and pe <= ps // 1440 * 1440 + fac_by[a["facility_id"]]["close_hour"] * 60 \
            and dock_free(dock, ps, pe, set(ignore) | {a["appointment_id"]})

    def move(a, ps, dock):
        aid, delta = a["appointment_id"], ps - a["planned_start"]
        idx[(a["dock_id"], a["planned_start"] // 1440)].remove(aid)
        a.update(dock_id=dock, planned_start=ps, planned_end=ps + a["planned_service_min"])
        idx[(dock, ps // 1440)].append(aid)
        for x in ev[aid]:
            if x["event_type"] != "SCHEDULED":
                x["event_ts"] += delta
                x["dock_id"] = dock
        for x in ex_by[aid]:
            x["detected_ts"] += delta

    def add_gt(issue, ent, eid, aid, decision, rule, note=""):
        gt.append(dict(gt_id=f"GT-{len(gt)+1:04d}", issue_type=issue, entity_type=ent, entity_id=eid, appointment_id=aid,
                       expected_decision=decision, rule_violated=rule, notes=note))

    def pool(src):
        p = [a for a in src if a["appointment_id"] not in used]
        rng.shuffle(p)
        return p

    # 1 overlap: A moved into B's window on B's dock (A fits inside B => only 1 conflict)
    fac_comp = defaultdict(list)
    for a in completed:
        fac_comp[a["facility_id"]].append(a)
    done = 0
    for A in pool(completed):
        if done >= k:
            break
        for _ in range(300):
            B = rng.choice(fac_comp[A["facility_id"]])
            if B["appointment_id"] in used or B is A or B["dock_id"] == A["dock_id"] or A["planned_service_min"] > B["planned_service_min"] \
                    or B["planned_start"] < A["request_ts"] + 60 or not dock_ok(dock_by[B["dock_id"]], A["handling_req_id"], A["direction"], veh_by[A["vehicle_id"]]["length_m"], B["_day"]) \
                    or not can_move(A, B["planned_start"], B["dock_id"], [B["appointment_id"]]):
                continue
            move(A, B["planned_start"], B["dock_id"])
            used |= {A["appointment_id"], B["appointment_id"]}
            add_gt("OVERLAPPING_APPOINTMENT_EXCEEDS_DOCK_CAPACITY", "Appointment", A["appointment_id"], A["appointment_id"], "REJECT_OR_RESCHEDULE", "dock capacity = 1 concurrent appointment", f"injected; overlaps {B['appointment_id']} on {B['dock_id']}")
            add_gt("OVERLAPPING_APPOINTMENT_EXCEEDS_DOCK_CAPACITY", "Appointment", B["appointment_id"], B["appointment_id"], "KEEP_ORIGINAL_BOOKING", "dock capacity = 1 concurrent appointment", f"peer of injected {A['appointment_id']}")
            done += 1
            break
    # 2 incompatible load
    done = 0
    for A in pool([a for a in completed if hr_by[a["handling_req_id"]]["requires_reefer_dock"] or hr_by[a["handling_req_id"]]["requires_hazmat_dock"]]):
        if done >= k:
            break
        ds = [d for d in fac_docks[A["facility_id"]] if A["handling_req_id"] not in cap[d["dock_id"]] and d["dock_type"] in (A["direction"], "FLEX")
              and d["effective_from"] <= A["_day"] and veh_by[A["vehicle_id"]]["length_m"] <= d["max_vehicle_length_m"]]
        rng.shuffle(ds)
        for d in ds:
            if can_move(A, A["planned_start"], d["dock_id"]):
                h = hr_by[A["handling_req_id"]]
                move(A, A["planned_start"], d["dock_id"])
                used.add(A["appointment_id"])
                add_gt("INCOMPATIBLE_LOAD_ASSIGNED", "Appointment", A["appointment_id"], A["appointment_id"], "REASSIGN_TO_COMPATIBLE_DOCK",
                       "dock must hold DockHandlingCapability for appointment handling_req_id", f"{h['temp_class']}/{h['hazmat_class']} load on {d['dock_id']} (refrigerated={d['is_refrigerated']}, hazmat={d['hazmat_certified']})")
                done += 1
                break
    # 3 check-in before appointment date
    for A in pool(completed)[:k]:
        d0 = A["planned_start"] // 1440 * 1440
        delta = (d0 - 120) - checkin(A)
        for x in ev[A["appointment_id"]]:
            if x["event_type"] in ("CHECK_IN", "YARD_ASSIGNED"):
                x["event_ts"] += delta
        used.add(A["appointment_id"])
        add_gt("CHECKIN_BEFORE_APPOINTMENT_DATE", "CheckInEvent", f"CHECK-{A['appointment_id']}-02", A["appointment_id"], "FLAG_INVALID_CHECKIN", "check-in date must be >= planned_start date", "check-in moved to 22:00 previous day")
    # 4 labor shift not available (03:00 is outside every shift)
    done = 0
    for A in pool(completed):
        if done >= k:
            break
        ps = A["planned_start"] // 1440 * 1440 + 180
        if can_move(A, ps, A["dock_id"]):
            move(A, ps, A["dock_id"])
            used.add(A["appointment_id"])
            add_gt("LABOR_SHIFT_NOT_AVAILABLE", "Appointment", A["appointment_id"], A["appointment_id"], "RESCHEDULE_INTO_SHIFT", "planned window must lie inside a LaborShift with crews_available>=1", "planned_start moved to 03:00 (no shift)")
            done += 1
    # 5 no-show not recorded
    for A in pool([a for a in appts if a["status"] == "NO_SHOW"])[:k]:
        ev[A["appointment_id"]] = [x for x in ev[A["appointment_id"]] if x["event_type"] != "NO_SHOW"]
        excs[:] = [x for x in excs if not (x["appointment_id"] == A["appointment_id"] and x["exception_type"] == "NO_SHOW")]
        A["status"] = "SCHEDULED"
        used.add(A["appointment_id"])
        add_gt("NO_SHOW_NOT_RECORDED", "Appointment", A["appointment_id"], A["appointment_id"], "RECORD_NO_SHOW(CARRIER_NO_SHOW)", "SCHEDULED appointment past planned_end with no check-in must have NO_SHOW event", "NO_SHOW event/exception removed")

    T["Appointment"] = appts
    T["CheckInEvent"] = [x for a in appts for x in ev[a["appointment_id"]]]
    excs.sort(key=lambda x: (x["detected_ts"], x["appointment_id"], x["exception_type"]))
    for n, x in enumerate(excs, 1):
        x["exception_id"] = f"EXC-2026-{n:06d}"
    T["Exception"] = excs
    gt.sort(key=lambda g: (S.ISSUE_TYPES.index(g["issue_type"]), g["gt_id"]))
    for n, g in enumerate(gt, 1):
        g["gt_id"] = f"GT-{n:04d}"
    return T, gt, outcomes


# ------------------------------------------------------------------ writers
def conv(v, typ):
    if v is None:
        return ""
    if typ == "bool":
        return "true" if v else "false"
    if typ == "datetime" and isinstance(v, int):
        return tsf(v)
    if typ == "date" and isinstance(v, int):
        return dsf(v)
    return str(v)


def write_csv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow([c["name"] for c in cols])
        for r in rows:
            w.writerow([conv(r.get(c["name"]), c["type"]) for c in cols])


def sql_val(s, typ):
    if s == "":
        return "NULL"
    if typ in ("int", "float"):
        return s
    if typ == "bool":
        return "1" if s == "true" else "0"
    return "'" + s.replace("'", "''") + "'"


def write_sql(out, T):
    tm = dict(string="TEXT", int="INTEGER", float="REAL", bool="INTEGER", date="TEXT", datetime="TEXT")
    ddl, seed = [], ["BEGIN;"]
    for name, e in S.ENTITIES.items():
        cols = []
        for c in e["fields"]:
            cols.append(f"  {c['name']} {tm[c['type']]}{' NOT NULL' if c['req'] else ''}")
        cols.append(f"  PRIMARY KEY ({', '.join(e['pk'])})")
        for col, (pe, pc) in e["fks"].items():
            cols.append(f"  FOREIGN KEY ({col}) REFERENCES {S.ENTITIES[pe]['file']}({pc})")
        ddl.append(f"CREATE TABLE {e['file']} (\n" + ",\n".join(cols) + "\n);")
        names = ", ".join(c["name"] for c in e["fields"])
        rows = ["(" + ", ".join(sql_val(conv(r.get(c["name"]), c["type"]), c["type"]) for c in e["fields"]) + ")" for r in T[name]]
        for i in range(0, len(rows), 500):
            seed.append(f"INSERT INTO {e['file']} ({names}) VALUES\n" + ",\n".join(rows[i:i + 500]) + ";")
    seed.append("COMMIT;")
    with open(os.path.join(out, "sql", "schema.sql"), "w") as fh:
        fh.write("\n\n".join(ddl) + "\n")
    with open(os.path.join(out, "sql", "seed.sql"), "w") as fh:
        fh.write("\n".join(seed) + "\n")


def write_docs(path):
    L = ["# Data Dictionary", "", "All timestamps are facility-local naive ISO-8601 (`YYYY-MM-DDTHH:MM:SS`); dates `YYYY-MM-DD`; booleans `true/false`; empty = NULL.", ""]
    for name, e in S.ENTITIES.items():
        L += [f"## {name}  (`{e['file']}.csv`)", f"PK: `{', '.join(e['pk'])}`" + (" | FKs: " + ", ".join(f"`{c}`->{p}.{pc}" for c, (p, pc) in e["fks"].items()) if e["fks"] else ""), "",
              "| Field | Type | Required | Allowed values / pattern | Unit | Unique | Validation rule |", "|---|---|---|---|---|---|---|"]
        for c in e["fields"]:
            al = ", ".join(c["allowed"]) if c["allowed"] else (f"`{c['pat']}`" if c["pat"] else "")
            L.append(f"| {c['name']} | {c['type']} | {'Y' if c['req'] else 'N'} | {al} | {c['unit']} | {'Y' if c['uniq'] else ''} | {c['rule']} |")
        L.append("")
    L += ["## Relationships / cardinality", ""] + [f"- {r}" for r in S.RELATIONSHIPS]
    L += ["", "## Lifecycle (CheckInEvent.resulting_status)", "", "Allowed transitions: " + "; ".join(f"{k or 'START'} -> {', '.join(sorted(v)) or 'END'}" for k, v in S.TRANSITIONS.items()),
          "", "## ID conventions", "", "`FAC-001`, `DOCK-FAC-001-001`, `YARD-FAC-001-01`, `CAR-001`, `VEH-00001`, `HR-001`, `APPT-2026-000001`, `SHP-2026-000001`, `CHECK-APPT-2026-000001-01`, `EXC-2026-000001`, `SHIFT-FAC-001-20260901-E`. Counters zero-padded, immutable.",
          "", "## Injected anomalies (ground_truth/ground_truth.csv, never in input tables)", ""] + [f"- `{i}`" for i in S.ISSUE_TYPES]
    with open(path, "w") as fh:
        fh.write("\n".join(L) + "\n")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def generate(out, seed, params, cmd):
    if os.path.exists(out):
        shutil.rmtree(out)
    for d in ("data", "sql", "ground_truth", "docs", "reports"):
        os.makedirs(os.path.join(out, d))
    T, gt, outcomes = build(seed, **params)
    for name, e in S.ENTITIES.items():
        write_csv(os.path.join(out, "data", e["file"] + ".csv"), e["fields"], T[name])
    write_sql(out, T)
    gcols = [S.f(c, "string") for c in ("gt_id", "issue_type", "entity_type", "entity_id", "appointment_id", "expected_decision", "rule_violated", "notes")]
    write_csv(os.path.join(out, "ground_truth", "ground_truth.csv"), gcols, gt)
    with open(os.path.join(out, "ground_truth", "ground_truth.json"), "w") as fh:
        json.dump(gt, fh, indent=1)
    ocols = [S.f(c, "bool" if c.startswith("is_") else "string") for c in ("appointment_id", "outcome_label", "is_no_show", "is_rejected", "is_early", "is_late", "is_congested")]
    write_csv(os.path.join(out, "ground_truth", "outcome_labels.csv"), ocols, outcomes)
    write_docs(os.path.join(out, "docs", "data_dictionary.md"))
    import validate
    validate.run(out)
    files = sorted(os.path.relpath(os.path.join(r, f_), out) for r, _, fs in os.walk(out) for f_ in fs)
    man = dict(seed=seed, parameters=params, generator_command=cmd, python="stdlib only (no external packages)",
               source_manifest=dict(external_data_used=False, note="Fully synthetic. No public datasets ingested; no personal/confidential data. Domain rules (dock capacity, reefer/hazmat compatibility, labor shifts) are original simplifications."),
               row_counts={e["file"]: len(T[n]) for n, e in S.ENTITIES.items()}, files={f_: sha(os.path.join(out, f_)) for f_ in files})
    with open(os.path.join(out, "manifest.json"), "w") as fh:
        json.dump(man, fh, indent=1)
    return man


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", choices=SCALES, default="full")
    ap.add_argument("--out", default=None)
    ap.add_argument("--seed", type=int, default=20261022)
    for k in ("n_fac", "docks_per", "n_appt", "days"):
        ap.add_argument("--" + k.replace("_", "-"), type=int, dest=k, default=None)
    ap.add_argument("--verify-repro", action="store_true", help="regenerate twice and compare row counts + checksums")
    a = ap.parse_args()
    params = {k: (getattr(a, k) if getattr(a, k) is not None else v) for k, v in SCALES[a.scale].items()}
    out = a.out or f"output/{a.scale}"
    cmd = "python generate.py " + " ".join(sys.argv[1:])
    man = generate(out, a.seed, params, cmd)
    print("rows:", man["row_counts"])
    if a.verify_repro:
        rep = dict(seed=a.seed, parameters=params, runs=[])
        with tempfile.TemporaryDirectory() as tmp:
            for i in (1, 2):
                m = generate(os.path.join(tmp, f"run{i}"), a.seed, params, cmd)
                rep["runs"].append(dict(row_counts=m["row_counts"], checksums=m["files"]))
        r0, r1 = rep["runs"]
        rep["row_counts_match"] = r0["row_counts"] == r1["row_counts"] == man["row_counts"]
        rep["checksums_match"] = r0["checksums"] == r1["checksums"] == man["files"]
        rep["files_compared"] = len(r0["checksums"])
        with open(os.path.join(out, "reproducibility_report.json"), "w") as fh:
            json.dump(rep, fh, indent=1)
        print("reproducible:", rep["row_counts_match"] and rep["checksums_match"], f"({rep['files_compared']} files)")
        if not (rep["row_counts_match"] and rep["checksums_match"]):
            sys.exit(1)


if __name__ == "__main__":
    main()
