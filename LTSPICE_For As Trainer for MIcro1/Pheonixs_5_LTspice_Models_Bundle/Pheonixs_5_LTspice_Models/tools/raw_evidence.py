"""Read the real, interleaved LTspice transient format present in this upload.

Rejects fastaccess/complex/unrecognized layouts rather than guessing. Previews
are decimated and must not be used for FFT or switching-peak acceptance.
"""
import csv
import hashlib
import math
from pathlib import Path
import re
import struct


def inspect(raw,signals=(),preview_points=3000):
    marker=b"Binary:\n"
    utf16=raw.startswith(b"T\x00i\x00")
    if utf16:marker="Binary:\n".encode("utf-16le")
    position=raw.find(marker)
    if position<0:raise ValueError("Missing binary transient marker")
    header=raw[:position].decode("utf-16le" if utf16 else "utf-8",errors="replace")
    def field(name):
        match=re.search(r"(?m)^"+re.escape(name)+r":\s*(.*)$",header)
        if not match:raise ValueError("Missing header field "+name)
        return match[1].strip()
    flags=field("Flags").lower().split()
    if "real" not in flags or "fastaccess" in flags or "double" in flags:
        raise ValueError("Unsupported RAW layout")
    count=int(field("No. Variables"));points=int(field("No. Points"))
    variables=re.findall(r"(?m)^[ \t]*\d+[ \t]+(\S+)[ \t]+\S+(?:[ \t]+[^\r\n]*)?$",header)
    if len(variables)!=count or variables[0].lower()!="time" or points<2:
        raise ValueError("Expected transient variable list")
    offset=position+len(marker);size=8+4*(count-1)
    if len(raw)-offset!=points*size:raise ValueError("Truncated or unsupported RAW record size")
    selected=[(name,next(i for i,v in enumerate(variables) if v.casefold()==name.casefold())) for name in signals]
    stride=max(1,points//preview_points)
    preview=[];last=-math.inf;negative_times=0
    for index in range(points):
        start=offset+index*size;t=struct.unpack_from("<d",raw,start)[0]
        if not math.isfinite(t) or t<last:raise ValueError("Non-finite/nonmonotone RAW time")
        negative_times+=t<0;last=t
        if index%stride==0 or index==points-1:
            row={"time_s":t}
            for name,column in selected:
                value=struct.unpack_from("<f",raw,start+8+4*(column-1))[0]
                if not math.isfinite(value):raise ValueError("Non-finite preview signal")
                row[name]=value
            preview.append(row)
    summary={"title":field("Title"),"date_in_header":field("Date"),"plot":field("Plotname"),
             "flags":flags,"variables":variables,"samples":points,
             "first_time_s":struct.unpack_from("<d",raw,offset)[0],"last_time_s":last,
             "negative_time_samples":negative_times,"sha256":hashlib.sha256(raw).hexdigest(),
             "source":"USER_UPLOADED_HISTORICAL_LTSPICE_SIMULATION", "measured_hardware":False,
             "preview_decimation_stride":stride,"preview_samples":len(preview)}
    return summary,preview


def save_preview(path,rows):
    with Path(path).open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
