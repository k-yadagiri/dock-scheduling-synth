#!/usr/bin/env python3
"""Validation + evaluation metrics. Reads ONLY data/*.csv for checks/detectors; ground_truth is used solely to score detectors."""
import csv, json, math, os, re, sys
from collections import defaultdict
from datetime import datetime
import schema as S

FMT = "%Y-%m-%dT%H:%M:%S"


def load(out, sub="data"):
    R = {}
    for n, e in S.ENTITIES.items():
        with open(os.path.join(out, sub, e["file"] + ".csv"), newline="") as fh:
            R[n] = list(csv.DictReader(fh))
    return R


def pm(s): return int(datetime.strptime(s, FMT).timestamp() // 60)  # naive-as-UTC minutes; only differences are used


def typeok(v, t):
    try:
        if t == "int": int(v)
        elif t == "float": float(v)
        elif t == "bool": assert v in ("true", "false")
        elif t == "date": datetime.strptime(v, "%Y-%m-%d")
        elif t == "datetime": datetime.strptime(v, FMT)
        return True
    except Exception:
        return False


def structural(R):
    res = {}

    def rec(name, bad):
        res[name] = dict(status="PASS" if not bad else "FAIL", violations=len(bad), examples=bad[:5])

    bad = []
    for n, e in S.ENTITIES.items():
        seen = set()
        for r in R[n]:
            k = tuple(r[c] for c in e["pk"])
            if k in seen: bad.append(f"{n}:{k}")
            seen.add(k)
        for c in e["fields"]:
            if c["uniq"]:
                vals = [r[c["name"]] for r in R[n]]
                if len(vals) != len(set(vals)): bad.append(f"{n}.{c['name']} not unique")
    rec("primary_key_and_unique_constraints", bad)
    bad = []
    for n, e in S.ENTITIES.items():
        for col, (pe, pc) in e["fks"].items():
            pv = {r[pc] for r in R[pe]}
            bad += [f"{n}.{col}={r[col]}" for r in R[n] if r[col] != "" and r[col] not in pv]
    rec("foreign_key_integrity", bad)
    bad = []
    for n, e in S.ENTITIES.items():
        for r in R[n]:
            for c in e["fields"]:
                v = r[c["name"]]
                if v == "":
                    if c["req"]: bad.append(f"{n}.{c['name']} missing")
                    continue
                if not typeok(v, c["type"]): bad.append(f"{n}.{c['name']} bad {c['type']}: {v}")
                elif c["allowed"] and v not in c["allowed"]: bad.append(f"{n}.{c['name']} enum: {v}")
                elif c["pat"] and not re.match(c["pat"], v): bad.append(f"{n}.{c['name']} pattern: {v}")
    rec("types_required_enums_id_patterns", bad)
    A = {r["appointment_id"]: r for r in R["Appointment"]}
    hr = {r["handling_req_id"]: r for r in R["HandlingRequirement"]}
    dock = {r["dock_id"]: r for r in R["Dock"]}
    fac = {r["facility_id"]: r for r in R["Facility"]}
    veh = {r["vehicle_id"]: r for r in R["Vehicle"]}
    evs = defaultdict(list)
    for r in R["CheckInEvent"]: evs[r["appointment_id"]].append(r)
    for l in evs.values(): l.sort(key=lambda x: int(x["event_seq"]))
    # date ordering
    bad = []
    for n in ("Facility", "Dock", "YardSlot"):
        bad += [f"{n}:{r['effective_from']}>{r['effective_to']}" for r in R[n] if r["effective_to"] and r["effective_from"] > r["effective_to"]]
    bad += [r["shift_id"] for r in R["LaborShift"] if r["shift_start"] >= r["shift_end"]]
    for a in A.values():
        if not a["request_ts"] < a["requested_start"]: bad.append(a["appointment_id"] + " request>=requested")
        if a["planned_start"] and not (a["request_ts"] <= a["planned_start"] < a["planned_end"]): bad.append(a["appointment_id"] + " planned order")
    for aid, l in evs.items():
        if [int(x["event_seq"]) for x in l] != list(range(1, len(l) + 1)): bad.append(aid + " seq gaps")
        if any(l[i]["event_ts"] > l[i + 1]["event_ts"] for i in range(len(l) - 1)): bad.append(aid + " event ts order")
        if l[0]["event_type"] not in ("SCHEDULED", "REJECTED"): bad.append(aid + " first event")
    for x in R["Exception"]:
        if x["detected_ts"] < A[x["appointment_id"]]["request_ts"]: bad.append(x["exception_id"] + " before request")
    rec("date_and_event_time_ordering", bad)
    # arithmetic
    ships = defaultdict(list)
    for s in R["Shipment"]: ships[s["appointment_id"]].append(s)
    bad = []
    for aid, a in A.items():
        sh = ships[aid]
        if not sh: bad.append(aid + " no shipments"); continue
        if sum(int(s["pallet_count"]) for s in sh) != int(a["total_pallets"]): bad.append(aid + " pallets")
        if abs(sum(float(s["weight_kg"]) for s in sh) - float(a["total_weight_kg"])) > .02: bad.append(aid + " weight")
        if any(s["handling_req_id"] != a["handling_req_id"] for s in sh): bad.append(aid + " shipment HR mismatch")
        if veh[a["vehicle_id"]]["carrier_id"] != a["carrier_id"]: bad.append(aid + " carrier!=vehicle.carrier")
        if a["dock_id"]:
            h = hr[a["handling_req_id"]]
            exp = int(math.ceil(round(int(h["base_service_min"]) + int(a["total_pallets"]) * float(h["per_pallet_min"]), 6) / 5) * 5)
            if exp != int(a["planned_service_min"]): bad.append(aid + " service min")
            if pm(a["planned_end"]) - pm(a["planned_start"]) != int(a["planned_service_min"]): bad.append(aid + " end-start")
            if dock[a["dock_id"]]["facility_id"] != a["facility_id"]: bad.append(aid + " dock facility")
        elif a["status"] != "REJECTED": bad.append(aid + " no dock but not rejected")
    for x in R["Exception"]:
        if x["cause_code"] not in S.CAUSE_BY_TYPE[x["exception_type"]]: bad.append(x["exception_id"] + " cause/type")
    for e in R["CheckInEvent"]:
        if e["event_id"] != f"CHECK-{e['appointment_id']}-{int(e['event_seq']):02d}": bad.append(e["event_id"] + " id")
        if S.EVENT_RESULT[e["event_type"]] != e["resulting_status"]: bad.append(e["event_id"] + " type/result")
    rec("arithmetic_reconciliation_and_derived_values", bad)
    # lifecycle
    bad = []
    for aid, l in evs.items():
        prev = None
        for x in l:
            if x["resulting_status"] not in S.TRANSITIONS[prev]: bad.append(f"{aid}: {prev}->{x['resulting_status']}")
            prev = x["resulting_status"]
        if S.FINAL_TO_APPT.get(prev) != A[aid]["status"]: bad.append(f"{aid}: final {prev} vs status {A[aid]['status']}")
    bad += [aid + " no events" for aid in A if aid not in evs]
    rec("lifecycle_transitions", bad)
    # duplicates
    bad, seen = [], set()
    for e in R["CheckInEvent"]:
        k = (e["appointment_id"], e["event_seq"])
        if k in seen: bad.append(str(k))
        seen.add(k)
    vb = defaultdict(list)
    for a in A.values():
        if a["planned_start"]: vb[a["vehicle_id"]].append((a["planned_start"], a["planned_end"], a["appointment_id"]))
    for v, l in vb.items():
        l.sort()
        bad += [f"vehicle {v} double-booked {l[i][2]}/{l[i+1][2]}" for i in range(len(l) - 1) if l[i][1] > l[i + 1][0]]
    rec("duplicates_and_vehicle_double_booking", bad)
    return res


def detectors(R):
    """Business-rule detectors using only input tables."""
    A = {r["appointment_id"]: r for r in R["Appointment"]}
    out = {i: set() for i in S.ISSUE_TYPES}
    byd = defaultdict(list)
    for a in A.values():
        if a["dock_id"]: byd[a["dock_id"]].append(a)
    for l in byd.values():
        l.sort(key=lambda a: a["planned_start"])
        for i, a in enumerate(l):
            for b in l[i + 1:]:
                if b["planned_start"] >= a["planned_end"]: break
                out["OVERLAPPING_APPOINTMENT_EXCEEDS_DOCK_CAPACITY"] |= {a["appointment_id"], b["appointment_id"]}
    cap = {(r["dock_id"], r["handling_req_id"]) for r in R["DockHandlingCapability"]}
    dock = {r["dock_id"]: r for r in R["Dock"]}
    for a in A.values():
        if a["dock_id"] and ((a["dock_id"], a["handling_req_id"]) not in cap or dock[a["dock_id"]]["dock_type"] not in (a["direction"], "FLEX")):
            out["INCOMPATIBLE_LOAD_ASSIGNED"].add(a["appointment_id"])
    cover = {}
    for s in R["LaborShift"]:
        if s["status"] == "SCHEDULED" and int(s["crews_available"]) >= 1:
            k = (s["facility_id"], s["shift_date"]); lo, hi = cover.get(k, (s["shift_start"], s["shift_end"]))
            cover[k] = (min(lo, s["shift_start"]), max(hi, s["shift_end"]))
    evs = defaultdict(list)
    for e in R["CheckInEvent"]: evs[e["appointment_id"]].append(e)
    end = max(s["shift_end"] for s in R["LaborShift"])
    for a in A.values():
        if a["planned_start"]:
            c = cover.get((a["facility_id"], a["planned_start"][:10]))
            if not c or a["planned_start"] < c[0] or a["planned_end"] > c[1]: out["LABOR_SHIFT_NOT_AVAILABLE"].add(a["appointment_id"])
            for e in evs[a["appointment_id"]]:
                if e["event_type"] == "CHECK_IN" and e["event_ts"][:10] < a["planned_start"][:10]: out["CHECKIN_BEFORE_APPOINTMENT_DATE"].add(a["appointment_id"])
            if a["status"] == "SCHEDULED" and a["planned_end"] < end and not any(e["event_type"] in ("CHECK_IN", "NO_SHOW") for e in evs[a["appointment_id"]]):
                out["NO_SHOW_NOT_RECORDED"].add(a["appointment_id"])
    return out


def metrics(R):
    A = {r["appointment_id"]: r for r in R["Appointment"]}
    tm = defaultdict(dict)
    for e in R["CheckInEvent"]: tm[e["appointment_id"]][e["event_type"]] = e
    dates = sorted({s["shift_date"] for s in R["LaborShift"]})
    fac = {f["facility_id"]: f for f in R["Facility"]}
    avail = defaultdict(float); busy = defaultdict(float); hourly = defaultdict(float); tot_av = 0
    for d in R["Dock"]:
        days = sum(1 for x in dates if x >= d["effective_from"])
        f_ = fac[d["facility_id"]]; m = days * (int(f_["close_hour"]) - int(f_["open_hour"])) * 60
        avail[d["facility_id"]] += m; tot_av += m
    waits, dwell, svc = [], [], []
    for aid, a in A.items():
        t = tm[aid]
        if "DEPARTED" in t and "SERVICE_START" in t:
            s, e = pm(t["SERVICE_START"]["event_ts"]), pm(t["SERVICE_END"]["event_ts"])
            busy[a["facility_id"]] += e - s; svc.append(e - s)
            waits.append(s - pm(t["CHECK_IN"]["event_ts"])); dwell.append(pm(t["DEPARTED"]["event_ts"]) - pm(t["CHECK_IN"]["event_ts"]))
            x = s
            while x < e:
                nxt = min(e, (x // 60 + 1) * 60); hourly[(x // 60) % 24] += nxt - x; x = nxt
    q = lambda l, p: round(sorted(l)[int(p * (len(l) - 1))], 1) if l else None
    st = defaultdict(int)
    for a in A.values(): st[a["status"]] += 1
    sched = len(A) - st["REJECTED"]
    ex = defaultdict(int)
    for x in R["Exception"]: ex[f"{x['exception_type']}/{x['cause_code']}"] += 1
    return dict(
        appointments=len(A), status_counts=dict(st), rejection_rate=round(st["REJECTED"] / len(A), 4),
        no_show_rate_of_scheduled=round(st["NO_SHOW"] / max(1, sched), 4),
        early_arrival_rate_of_completed=round(sum(1 for x in R["Exception"] if x["exception_type"] == "EARLY_ARRIVAL") / max(1, st["COMPLETED"]), 4),
        late_arrival_rate_of_completed=round(sum(1 for x in R["Exception"] if x["exception_type"] == "LATE_ARRIVAL") / max(1, st["COMPLETED"]), 4),
        wait_minutes_checkin_to_service=dict(mean=round(sum(waits) / max(1, len(waits)), 1), p50=q(waits, .5), p90=q(waits, .9), max=max(waits, default=None)),
        dwell_minutes_checkin_to_departure=dict(mean=round(sum(dwell) / max(1, len(dwell)), 1), p90=q(dwell, .9)),
        service_minutes_mean=round(sum(svc) / max(1, len(svc)), 1),
        dock_utilization_overall=round(sum(busy.values()) / tot_av, 4),
        dock_utilization_by_facility={f: round(busy[f] / avail[f], 4) for f in sorted(avail)},
        hourly_dock_utilization={h: round(hourly[h] / (len(R["Dock"]) * len(dates) * 60), 4) for h in sorted(hourly)},
        exceptions_by_type_cause=dict(sorted(ex.items())), exceptions_total=len(R["Exception"]), events_total=len(R["CheckInEvent"]))


def run(out):
    R = load(out)
    st = structural(R)
    gt = {}
    with open(os.path.join(out, "ground_truth", "ground_truth.csv"), newline="") as fh:
        for r in csv.DictReader(fh): gt.setdefault(r["issue_type"], set()).add(r["appointment_id"])
    det = detectors(R)
    br = {}
    for i in S.ISSUE_TYPES:
        g, d = gt.get(i, set()), det[i]
        br[i] = dict(ground_truth=len(g), detected=len(d), true_positive=len(g & d), false_positive=len(d - g), false_negative=len(g - d),
                     status="PASS" if g == d else "FAIL")
    ok = all(v["status"] == "PASS" for v in list(st.values()) + list(br.values()))
    summary = dict(overall="PASS" if ok else "FAIL", structural_checks=st, business_rule_detectors_vs_ground_truth=br,
                   note="Structural checks run on baseline+injected data and must be clean (anomalies are semantic, not structural). Each business-rule detector must recover exactly the labelled ground-truth rows.")
    with open(os.path.join(out, "reports", "validation_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=1)
    with open(os.path.join(out, "reports", "metrics_summary.json"), "w") as fh:
        json.dump(metrics(R), fh, indent=1)
    return summary


if __name__ == "__main__":
    s = run(sys.argv[1] if len(sys.argv) > 1 else "output/full")
    print(s["overall"], {k: v["status"] for k, v in s["structural_checks"].items()}, {k: (v["ground_truth"], v["detected"]) for k, v in s["business_rule_detectors_vs_ground_truth"].items()})
    sys.exit(0 if s["overall"] == "PASS" else 1)
