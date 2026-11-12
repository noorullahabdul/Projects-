from pathlib import Path

from .buck import operating_point
from .config import BuckSpec


def export_buck(s: BuckSpec, path: str | Path) -> None:
    duty = operating_point(s)["duty"]
    text = f"""* Original ideal-switch synchronous buck exploration deck
* Fixed PWM; this is separate from the Python PI-controlled averaged model.
* LTspice execution has not been performed by the bundle builder.
.param VIN={s.vin_v} VOUT={s.vout_v} POUT={s.power_w}
.param FS={s.switching_hz} TS=1/FS DUTY={duty:.12g} TD={s.deadtime_s}
VBAT VIN 0 {{VIN}}
VGH GH 0 PULSE(0 10 {{TD}} 1n 1n {{DUTY*TS-2*TD}} {{TS}})
VGL GL 0 PULSE(0 10 {{DUTY*TS+TD}} 1n 1n {{(1-DUTY)*TS-2*TD}} {{TS}})
SH VIN SW GH 0 HIGH
SL SW 0 GL 0 LOW
DH SW VIN BODY
DL 0 SW BODY
L1 SW LX {s.inductance_h} IC={s.power_w/s.vout_v/2}
RDC LX OUT {s.inductor_dcr_ohm}
RESR OUT CAP {s.capacitor_esr_ohm}
C1 CAP 0 {s.capacitance_f} IC={{VOUT}}
BLOAD OUT 0 I=V(OUT)*if(time<20m,0.5,1)*POUT/(VOUT*VOUT)
.model HIGH SW(Ron={s.high_rds_ohm} Roff=1e9 Vt=5 Vh=0.1)
.model LOW SW(Ron={s.low_rds_ohm} Roff=1e9 Vt=5 Vh=0.1)
.model BODY D(Is=1n Rs=1m N=1)
.tran 0 80m 0 {{TS/30}} UIC
.meas TRAN VOUT_AVG AVG V(OUT) FROM 60m TO 80m
.meas TRAN VOUT_MAX MAX V(OUT) FROM 20m TO 40m
.meas TRAN VOUT_MIN MIN V(OUT) FROM 20m TO 40m
.meas TRAN IL_MAX MAX I(L1) FROM 0 TO 80m
.end
"""
    if duty / s.switching_hz <= 2 * s.deadtime_s or (1-duty) / s.switching_hz <= 2 * s.deadtime_s:
        raise ValueError("PWM pulse is shorter than allocated dead time")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
