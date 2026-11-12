from dataclasses import replace
import csv
import json
import math
from pathlib import Path
import tempfile
import unittest

from powerlab import buck, inverter, obc
from powerlab.config import BuckSpec, InverterSpec, OBCSpec, load_spec
from powerlab.__main__ import main
from powerlab.spice import export_buck
from powerlab.waveforms import analyze, read_waveform, time_average, write_csv


class BuckTests(unittest.TestCase):
    def test_power_balance(self):
        point = buck.operating_point(BuckSpec())
        loss_keys = ("high_conduction_w", "low_conduction_w", "inductor_w", "switching_w",
                     "deadtime_w", "gate_w", "capacitor_w", "core_w")
        self.assertAlmostEqual(sum(point[k] for k in loss_keys), point["total_loss_w"])
        self.assertAlmostEqual(point["efficiency"] * (1000 + point["total_loss_w"]), 1000)
        self.assertEqual(point["status"], "PASS")

    def test_dc_voltage_balance(self):
        spec = BuckSpec()
        point = buck.operating_point(spec)
        i, d = point["output_current_a"], point["duty"]
        loss_drop = i * (spec.inductor_dcr_ohm + d * spec.high_rds_ohm + (1-d) * spec.low_rds_ohm)
        self.assertAlmostEqual(d * spec.vin_v - loss_drop, spec.vout_v, places=10)

    def test_frequency_tradeoff(self):
        low = buck.operating_point(replace(BuckSpec(), switching_hz=80_000))
        high = buck.operating_point(replace(BuckSpec(), switching_hz=160_000))
        self.assertAlmostEqual(low["ripple_current_pp_a"], 2 * high["ripple_current_pp_a"])
        self.assertAlmostEqual(high["switching_w"], 2 * low["switching_w"])

    def test_load_and_thermal_violations(self):
        point = buck.operating_point(replace(BuckSpec(), power_w=1500))
        self.assertIn("PEAK_CURRENT", point["violations"])
        point = buck.operating_point(replace(BuckSpec(), theta_junction_k_w=10))
        self.assertIn("JUNCTION_TEMPERATURE", point["violations"])
        point = buck.operating_point(replace(BuckSpec(), capacitor_esr_ohm=0.3))
        self.assertIn("OUTPUT_RIPPLE", point["violations"])

    def test_ccm_not_claimed_at_very_light_load(self):
        point = buck.operating_point(replace(BuckSpec(), power_w=1))
        self.assertIn("CCM_ASSUMPTION_INVALID", point["violations"])

    def test_invalid_spec(self):
        for kwargs in ({"vin_v": 8}, {"inductance_h": 0}, {"ambient_c": math.nan},
                       {"deadtime_s": 1}, {"capacitor_esr_ohm": -1}, {"power_w": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                replace(BuckSpec(), **kwargs)

    def test_infeasible_duty(self):
        with self.assertRaises(ValueError):
            buck.operating_point(replace(BuckSpec(), high_rds_ohm=1.0))

    def test_averaged_transient_recovers_and_balances(self):
        s = BuckSpec()
        rows = buck.transient(s)
        result = analyze(rows, s)
        self.assertEqual(result["verdict"], "PASS", result)
        self.assertLess(abs(rows[-1]["inductor_a"] - rows[-1]["load_a"]), 0.02)
        self.assertTrue(all(0 <= r["duty"] <= 0.95 for r in rows))

    def test_biased_sensor_and_duty_faults_detected(self):
        for fault in ("sensor_bias", "duty_drop"):
            with self.subTest(fault=fault):
                result = analyze(buck.transient(BuckSpec(), fault), BuckSpec())
                self.assertEqual(result["verdict"], "FAIL")
                self.assertEqual(next(r for r in result["checks"] if "steady regulation" in r["requirement"])["status"], "FAIL")

    def test_integration_convergence(self):
        coarse = buck.transient(BuckSpec(), dt=10e-6)
        fine = buck.transient(BuckSpec(), dt=5e-6)
        self.assertLess(abs(coarse[-1]["vout_v"] - fine[-1]["vout_v"]), 0.0001)
        self.assertLess(abs(min(r["vout_v"] for r in coarse) - min(r["vout_v"] for r in fine)), 0.005)

    def test_integration_work_and_stability_guards(self):
        for kwargs in ({"dt": 1}, {"duration_s": 1e7}, {"fault": "unknown"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                buck.transient(BuckSpec(), **kwargs)

    def test_complete_sweep(self):
        rows = buck.sweep(BuckSpec())
        self.assertEqual(len(rows), 81)
        self.assertTrue(all(0 < row["efficiency"] < 1 for row in rows))


class InverterTests(unittest.TestCase):
    def test_constant_power_envelope(self):
        s = InverterSpec()
        for rpm in (1, 1000, 4000, 8000, 12000, -8000):
            point = inverter.operating_point(s, 800, rpm, 1000)
            self.assertLessEqual(abs(point["mechanical_power_w"]), s.rated_power_w + 1e-8)
            self.assertLessEqual(abs(point["applied_torque_nm"]), s.maximum_torque_nm)

    def test_regeneration_sign_and_energy_balance(self):
        p = inverter.operating_point(InverterSpec(), 800, 4000, -250)
        self.assertLess(p["dc_current_a"], 0)
        self.assertEqual(p["mode"], "regeneration")
        self.assertLess(abs(p["dc_power_w"]), abs(p["mechanical_power_w"]))
        self.assertAlmostEqual(p["dc_power_w"] - p["mechanical_power_w"],
                               p["motor_copper_loss_w"] + p["motor_core_loss_w"] + p["inverter_loss_w"])
        self.assertTrue(0 < p["efficiency"] < 1)

    def test_reverse_speed_and_torque_motors(self):
        p = inverter.operating_point(InverterSpec(), 800, -4000, -250)
        self.assertEqual(p["mode"], "motoring")
        self.assertGreater(p["dc_current_a"], 0)

    def test_standstill_has_loss_and_no_efficiency_claim(self):
        p = inverter.operating_point(InverterSpec(), 800, 0, 360)
        self.assertEqual(p["mechanical_power_w"], 0)
        self.assertGreater(p["dc_power_w"], 0)
        self.assertIsNone(p["efficiency"])

    def test_voltage_infeasibility_not_hidden(self):
        p = inverter.operating_point(InverterSpec(), 600, 12000, 150)
        self.assertIn("VOLTAGE_LIMIT_ID_ZERO", p["violations"])

    def test_derating_and_shutdown(self):
        s = InverterSpec()
        cold = inverter.operating_point(s, 800, 1000, 360, 100)
        hot = inverter.operating_point(s, 800, 1000, 360, 150)
        shutdown = inverter.operating_point(s, 800, 1000, 360, 170)
        self.assertLess(hot["applied_torque_nm"], cold["applied_torque_nm"])
        self.assertEqual(shutdown["applied_torque_nm"], 0)
        self.assertIn("OVERTEMPERATURE", shutdown["violations"])

    def test_limits_and_bad_inputs(self):
        for voltage, rpm, torque in ((math.nan, 1000, 100), (0, 1000, 100), (800, math.inf, 100)):
            with self.assertRaises(ValueError):
                inverter.operating_point(InverterSpec(), voltage, rpm, torque)
        p = inverter.operating_point(InverterSpec(), 900, 13000, 150)
        self.assertIn("DC_BUS_RANGE", p["violations"])
        self.assertIn("OVERSPEED", p["violations"])

    def test_map_records_true_feasibility(self):
        rows = inverter.sweep(InverterSpec())
        self.assertEqual(len(rows), 240)
        self.assertTrue(any(p["status"] == "FAIL" for p in rows))
        self.assertTrue(any(p["status"] == "PASS" for p in rows))


class OBCTests(unittest.TestCase):
    def test_resonance_unity_gain_across_loads(self):
        s = OBCSpec()
        resonance = 1 / (2 * math.pi * math.sqrt(s.resonant_l_h * s.resonant_c_f))
        for power in (3000, 15000, 30000):
            self.assertAlmostEqual(obc.tank(s, resonance, 800, power)["gain"], 1, places=12)

    def test_frequency_solver_and_input_power_balance(self):
        s = OBCSpec()
        p = obc.operating_point(s, 400, 800, 30000)
        self.assertLess(p["gain_error_fraction"], 1e-10)
        self.assertEqual(p["status"], "PASS")
        input_power = math.sqrt(3) * 400 * p["iac_rms_a"] * s.power_factor
        self.assertAlmostEqual(input_power, 30000 + p["loss_w"], places=7)
        self.assertAlmostEqual(p["efficiency"], 30000 / input_power)
        self.assertEqual(p["zvs_evidence"], "NOT_EVALUATED")

    def test_unreachable_gain_is_a_failure(self):
        p = obc.operating_point(OBCSpec(), 400, 100, 3000)
        self.assertIn("LLC_GAIN_UNREACHABLE", p["violations"])

    def test_line_current_and_boost_headroom(self):
        p = obc.operating_point(OBCSpec(), 200, 800, 30000)
        self.assertIn("LINE_CURRENT", p["violations"])
        p = obc.operating_point(OBCSpec(), 600, 800, 30000)
        self.assertIn("PFC_BOOST_HEADROOM", p["violations"])

    def test_bad_inputs(self):
        for args in ((0, 800, 30000), (120000, -1, 3000), (120000, 800, math.nan)):
            with self.assertRaises(ValueError):
                obc.tank(OBCSpec(), *args)

    def test_map_size(self):
        self.assertEqual(len(obc.sweep(OBCSpec())), 27)


class InputAndWorkflowTests(unittest.TestCase):
    def test_csv_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.csv"
            write_csv(path, buck.transient(BuckSpec()))
            rows = read_waveform(path)
            self.assertEqual(analyze(rows, BuckSpec())["verdict"], "PASS")

    def test_bad_csv_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.csv"
            for name, value in (("time_s", 0), ("vout_v", math.nan), ("duty", 2)):
                rows = buck.transient(BuckSpec(), duration_s=0.025)[:3]
                rows[1][name] = value
                write_csv(path, rows)
                with self.subTest(name=name), self.assertRaises(ValueError):
                    read_waveform(path)
            path.write_text('time_s,vin_v,vout_v,inductor_a,load_a,duty\n"unclosed')
            with self.assertRaises(csv.Error):
                read_waveform(path)

    def test_insufficient_coverage_not_pass(self):
        rows = buck.transient(BuckSpec())[-100:]
        self.assertNotEqual(analyze(rows, BuckSpec())["verdict"], "PASS")

    def test_time_weighted_average_irregular_samples(self):
        rows = [{"time_s": 0, "v": 0}, {"time_s": 1, "v": 2}, {"time_s": 4, "v": 2}]
        self.assertAlmostEqual(time_average(rows, "v"), 1.75)

    def test_unknown_config_and_invalid_motor_spec(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "spec.json"
            path.write_text('{"fsw_typo": 100000}')
            with self.assertRaises(ValueError):
                load_spec(BuckSpec, path)
        with self.assertRaises(ValueError):
            InverterSpec(pole_pairs=2.5)

    def test_native_spice_export_self_contained(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "buck.cir"
            export_buck(BuckSpec(), path)
            text = path.read_text()
            self.assertNotIn(".include", text)
            self.assertIn(".tran", text)
            self.assertIn(".end", text)
            self.assertIn("Fixed PWM", text)

    def test_cli_generates_waveform(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "wave.csv"
            self.assertEqual(main(["simulate", "--csv", str(path)]), 0)
            self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
