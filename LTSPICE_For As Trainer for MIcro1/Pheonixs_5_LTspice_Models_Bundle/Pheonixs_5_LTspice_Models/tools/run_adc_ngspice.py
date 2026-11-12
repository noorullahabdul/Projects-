"""Run the generic ADC exported from Model.asc, not the protected IC models."""
import argparse
import bisect
import csv
import json
import math
from pathlib import Path
from inspect_models import ROOT,adc_netlist
from spiceio import resolve_engine,run_engine


def spectrum(values):
    n=len(values);mean=sum(values)/n;centered=[x-mean for x in values]
    powers=[]
    for k in range(1,n//2+1):
        re=im=0.0
        for index,x in enumerate(centered):
            angle=2*math.pi*k*index/n
            re+=x*math.cos(angle);im-=x*math.sin(angle)
        powers.append((re*re+im*im)*(1 if k==n//2 else 2)/(n*n))
    fundamental=powers[98]  # 9.9 kHz at 100 kS/s, N=1000 -> coherent bin 99.
    residual=sum(p for i,p in enumerate(powers,1) if i!=99)
    largest=max(p for i,p in enumerate(powers,1) if i!=99)
    if min(fundamental,residual,largest)<=0:
        return {"sinad_db":None,"derived_enob_bits":None,"sfdr_db":None,
                "reason":"A nonzero signal and residual are required; no infinite or fabricated score is emitted."}
    sinad=10*math.log10(fundamental/residual)
    return {"method":"Rectangular DFT of 1000 uniformly strobed held codes; DC omitted; coherent bin 99.",
            "sample_rate_hz":100000,"input_frequency_hz":9900,"samples":n,
            "sinad_db":sinad,"derived_enob_bits":(sinad-1.76)/6.02,
            "sfdr_db":10*math.log10(fundamental/largest),
            "scope":"Ideal behavioral model simulation; not ADC hardware or a physical SAR conversion result."}


def main(argv=None):
    parser=argparse.ArgumentParser(description="Execute only the generic behavioral ADC model with ngspice")
    parser.add_argument("--ngspice")
    parser.add_argument("--out",type=Path,default=ROOT/"validation/adc_ngspice")
    args=parser.parse_args(argv)
    try:
        folder=next((ROOT/"models").glob("05_*"))
        deck=adc_netlist(folder).replace(".tran 0 12m 0 50n",".tran 50n 12m 0 50n")
        control='''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
run
linearize v(vin) v(sh_out) v(dgtl_out) v(clk)
wrdata waveform.dat v(vin) v(sh_out) v(dgtl_out) v(clk)
quit
.endc
'''
        deck=deck.rsplit(".end",1)[0]+control+".end\n"
        rows,meta=run_engine(deck,args.out,resolve_engine(args.ngspice),("vmax","vmin"),
                             ("v(vin)","v(sh_out)","v(dgtl_out)","v(clk)"),.012)
        times=[r["time"] for r in rows]
        def at(t,key):
            i=max(0,min(len(rows)-2,bisect.bisect_right(times,t)-1))
            frac=(t-times[i])/(times[i+1]-times[i])
            return rows[i][key]+frac*(rows[i+1][key]-rows[i][key])
        lsb=5/4096;samples=[];errors=[];drops=[]
        for n in range(1000):
            t=.002+n/100000+7.5e-6
            sh,out=at(t,"v(sh_out)"),at(t,"v(dgtl_out)")
            errors.append((sh-out)/lsb)
            drops.append(abs(at(t-1e-6,"v(sh_out)")-at(t+1e-6,"v(sh_out)")))
            samples.append({"time_s":t,"held_v":sh,"quantized_v":out,"code":round(out/lsb)})
        result={"engine":meta,"dataset_type":"EXECUTED_NGSPICE_BEHAVIORAL_ADC_FROM_WORKING_ASC",
                "native_ltspice_executed_here":False,"measured_hardware":False,
                "lsb_v":lsb,"quantization_error_min_lsb":min(errors),
                "quantization_error_max_lsb":max(errors),
                "max_2us_hold_change_v":max(drops),
                "code_min":min(r["code"] for r in samples),"code_max":max(r["code"] for r in samples),
                "quantizer_consistency_pass":min(errors)>=-.001 and max(errors)<=1.001,
                "code_range_pass":all(0<=r["code"]<=4095 for r in samples),
                "input_signal_transfer_pass":max(r["code"] for r in samples)-min(r["code"] for r in samples)>=4000,
                "hold_change_below_0_01_lsb":max(drops)<.01*lsb,
                "spectrum":spectrum([r["quantized_v"] for r in samples])}
        result["all_behavioral_checks_pass"]=all(result[k] for k in ("quantizer_consistency_pass","code_range_pass","input_signal_transfer_pass","hold_change_below_0_01_lsb"))
        with (args.out/"strobed_samples.csv").open("w",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=list(samples[0]));writer.writeheader();writer.writerows(samples)
        (args.out/"result.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
        print(json.dumps({k:v for k,v in result.items() if k!="engine"},indent=2))
        return 0 if result["all_behavioral_checks_pass"] else 1
    except (OSError,ValueError,RuntimeError) as exc:
        print("ADC experiment failed:",exc)
        return 2


if __name__=="__main__":raise SystemExit(main())
