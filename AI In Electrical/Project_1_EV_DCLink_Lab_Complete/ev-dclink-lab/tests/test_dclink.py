from dataclasses import replace
import csv
import json
import math
from pathlib import Path
import tempfile
import unittest

from dclink_lab.controller import Controller, Inputs, State
from dclink_lab.design import Design, charge_time, charge_voltage, corner_sweep, discharge_time
from dclink_lab.__main__ import main
from dclink_lab.report import table
from dclink_lab.simulation import FAULTS, simulate
from dclink_lab.storage import history, record_run
from dclink_lab.telemetry import REQUIRED, analyze, read_csv, write_csv


class DesignTests(unittest.TestCase):
    def test_analytical_inverse(self):
        for ratio in (0.1, 0.9, 0.93, 0.999):
            t = charge_time(92.047, 0.001, ratio)
            self.assertAlmostEqual(charge_voltage(800, 92.047, 0.001, t), 800 * ratio, places=9)

    def test_expected_energy_and_discharge(self):
        self.assertAlmostEqual(discharge_time(800, 60, 1000, 0.001), 2.5902671654, places=8)
        self.assertEqual(discharge_time(20, 60, 1000, 0.001), 0)

    def test_bad_parameters(self):
        for changes in ({"capacitance_f": 0}, {"pack_v": math.nan}, {"command_ratio": 1},
                        {"sensor_tolerance": -1}, {"pack_min_v": 900}, {"source_ohm": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(Design(), **changes)

    def test_unknown_config_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "design.json"
            p.write_text('{"precharge_ohms":92}')
            with self.assertRaises(ValueError):
                Design.load(p)

    def test_corners_expose_sensor_timing_risk(self):
        rows = corner_sweep(Design())
        self.assertEqual(len(rows), 108)
        self.assertTrue(any(not row["pass"] for row in rows))
        self.assertTrue(all(row["actual_ratio"] >= 0.90 for row in rows))
        self.assertTrue(all(row["initial_current_a"] < 10 for row in rows))

    def test_lower_resistance_allocation_resolves_analytical_timing(self):
        rows = corner_sweep(replace(Design(), precharge_ohm=88))
        self.assertTrue(all(row["pass"] for row in rows))


class ControllerTests(unittest.TestCase):
    def test_bad_dt(self):
        for dt in (0, -1, math.nan, 1):
            with self.subTest(dt=dt), self.assertRaises(ValueError):
                Controller().step(Inputs(dt=dt))

    def test_invalid_sensor_fails_without_discharge(self):
        c = Controller()
        out = c.step(Inputs(vdc=math.nan))
        self.assertEqual(out.fault, "INVALID_SENSOR")
        self.assertFalse(out.discharge_cmd or out.torque_enable)

    def test_shutdown_during_precharge(self):
        c = Controller()
        c.step(Inputs(wake=True))
        c.step(Inputs())
        c.step(Inputs(neg_aux=True))
        out = c.step(Inputs(shutdown=True, neg_aux=True, pre_aux=True, vdc=100))
        self.assertEqual(c.state, State.OPENING)
        self.assertFalse(out.neg_cmd or out.pre_cmd or out.pos_cmd or out.discharge_cmd)

    def test_latched_fault_preserves_first_reason(self):
        c = Controller()
        c.step(Inputs(wake=True))
        c.step(Inputs(hvil=False, pos_aux=True))
        for _ in range(10):
            self.assertEqual(c.step(Inputs(wake=True)).fault, "HV_SAFETY_INPUT")
        self.assertEqual(c.state, State.FAULT)

    def test_run_feedback_loss_inhibits_torque_same_tick(self):
        c = Controller()
        c.state = State.RUN
        out = c.step(Inputs(neg_aux=True, pos_aux=False, vdc=800))
        self.assertFalse(out.torque_enable or out.pos_cmd or out.neg_cmd)
        self.assertEqual(out.fault, "MAIN_FEEDBACK_LOST")

    def test_no_discharge_into_welded_positive(self):
        c = Controller()
        c.fail("WELD")
        out = c.step(Inputs(pos_aux=True, vdc=800))
        self.assertFalse(out.discharge_cmd)

    def test_run_link_collapse_inhibits_torque(self):
        c = Controller()
        c.state = State.RUN
        out = c.step(Inputs(neg_aux=True, pos_aux=True, vdc=600))
        self.assertFalse(out.torque_enable)
        self.assertEqual(out.fault, "RUN_LINK_UNDERVOLTAGE")

    def test_secondary_sensor_prevents_biased_closure(self):
        c = Controller()
        c.state = State.PRECHARGE
        out = c.step(Inputs(neg_aux=True, vdc=750, vdc_secondary=600))
        self.assertEqual(out.fault, "SENSOR_DISAGREEMENT")
        self.assertFalse(out.pos_cmd)


class SimulationTests(unittest.TestCase):
    def test_nominal_cycle(self):
        result = analyze(simulate(Design()), Design())
        self.assertEqual(result["verdict"], "PASS", result)
        self.assertEqual(result["diagnostics"], [])

    def test_injected_faults_are_observed(self):
        for name, expected in FAULTS.items():
            with self.subTest(fault=name):
                rows = simulate(Design(), name)
                observed = next((row["fault"] for row in rows if row["fault"]), "")
                self.assertEqual(observed, expected)
                self.assertFalse(any(row["discharge_cmd"] and (row["pos_aux"] or row["neg_aux"] or row["pre_aux"]) for row in rows))
                if name not in ("none", "discharge_open"):
                    self.assertFalse(any(row["torque_enable"] for row in rows))

    def test_time_step_convergence(self):
        starts = []
        for dt in (0.001, 0.002, 0.004):
            rows = simulate(Design(), dt=dt)
            self.assertEqual(analyze(rows, Design())["verdict"], "PASS")
            starts.append(next(row["time_s"] for row in rows if row["torque_enable"]))
        self.assertLess(max(starts) - min(starts), 0.015)

    def test_short_record_cannot_pass(self):
        result = analyze(simulate(Design(), duration_s=0.05), Design())
        self.assertEqual(result["verdict"], "INCOMPLETE")

    def test_fault_selector_and_work_limit(self):
        for kw in ({"fault": "typo"}, {"duration_s": 1e8}, {"dt": -1}):
            with self.assertRaises(ValueError):
                simulate(Design(), **kw)


class TelemetryTests(unittest.TestCase):
    def roundtrip(self, rows):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.csv"
            write_csv(path, rows)
            return read_csv(path)

    def test_csv_roundtrip(self):
        rows = self.roundtrip(simulate(Design()))
        self.assertEqual(analyze(rows, Design())["verdict"], "PASS")

    def test_nonfinite_and_duplicate_time(self):
        for name, value in (("vdc_v", math.nan), ("time_s", 0), ("pos_aux", 2)):
            rows = simulate(Design(), duration_s=0.01)
            rows[1][name] = value
            with self.subTest(column=name), self.assertRaises(ValueError):
                self.roundtrip(rows)

    def test_missing_header(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.csv"
            path.write_text("time_s,vdc_v\n0,10\n1,20\n")
            with self.assertRaises(ValueError):
                read_csv(path)
            path.write_text(",".join(REQUIRED) + '\n"unclosed')
            with self.assertRaises(csv.Error):
                read_csv(path)

    def test_unsafe_torque_detected(self):
        rows = simulate(Design())
        rows[0]["torque_enable"] = 1
        result = analyze(rows, Design())
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(next(c for c in result["checks"] if "torque interlock" in c["requirement"])["status"], "FAIL")

    def test_gapped_record_incomplete(self):
        rows = simulate(Design())[::25]
        result = analyze(rows, Design())
        self.assertNotEqual(result["verdict"], "PASS")

    def test_html_escape(self):
        self.assertNotIn("<script>", table([{"name": "<script>"}]))

    def test_ledger_hash_and_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "history #1.db"
            run_id = record_run(db, "test", Design(), {"status": "PASS"}, "a" * 64)
            row = history(db)[0]
            self.assertEqual(row["run_id"], run_id)
            self.assertEqual(row["input_sha256"], "a" * 64)
            csvpath = Path(folder) / "trace.csv"
            self.assertEqual(main(["simulate", "--csv", str(csvpath)]), 0)
            self.assertTrue(csvpath.exists())


if __name__ == "__main__":
    unittest.main()
