"""Focused checks for the support scripts; no claim of native LTspice runs."""
import copy
import struct
import tempfile
from pathlib import Path
import unittest
from inspect_models import ROOT,transform,schematic,connectivity,validate
from raw_evidence import inspect
from run_ltspice import check_log


class HelperChecks(unittest.TestCase):
    def test_mirrored_vrm_inductor_pin_matches_actual_wire_endpoint(self):
        # M270 in the supplied phase-2 geometry: L2 pin1 at (-1648,-576).
        dx,dy=transform(16,16,"M270")
        self.assertEqual((-1632+dx,-560+dy),(-1648,-576))

    def test_all_five_static_checks(self):
        results=[validate(p) for p in (ROOT/"models").iterdir() if (p/"Model.asc").is_file()]
        self.assertEqual(len(results),5)
        self.assertTrue(all(r["static_status"]=="PASS" for r in results))
        self.assertTrue(all(r["native_ltspice_executed_here"] is False for r in results))

    def test_clock_short_is_detected(self):
        data=schematic(next((ROOT/"models").glob("05_*"))/"Model.asc")
        _,_,labels,_=connectivity(data)
        data["wires"].append((labels["clk"],labels["sh_out"]))
        _,_,broken,_=connectivity(data)
        self.assertEqual(broken["clk"],broken["sh_out"])

    def test_raw_alias_column_is_supported(self):
        header=("Title: fixture\nDate: fixture\nPlotname: Transient Analysis\nFlags: real forward\n"
                "No. Variables: 2\nNo. Points: 2\nVariables:\n\t0\ttime\ttime\n"
                "\t1\tIx(u:1)\tsubckt_current\tIx(u:gnd)\nBinary:\n").encode()
        raw=header+struct.pack("<dfdf",0,1,1e-3,2)
        summary,_=inspect(raw)
        self.assertEqual(summary["samples"],2)
        with self.assertRaises(ValueError):inspect(raw[:-1])

    def test_user_stop_never_passes_from_elapsed_time_alone(self):
        with self.assertRaises(RuntimeError):
            check_log("Simulation stopped by user.\nTotal elapsed time: 1 second.")
        check_log("Gmin stepping succeeded in finding the operating point.\nTotal elapsed time: 1 second.")


if __name__=="__main__":unittest.main()
