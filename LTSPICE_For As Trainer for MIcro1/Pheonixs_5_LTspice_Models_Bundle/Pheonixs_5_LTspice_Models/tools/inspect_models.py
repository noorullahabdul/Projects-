"""Local dependency and connectivity checks; does not execute LTspice.

Supported ASC records are sufficient for these five flat schematics. Wires
connect at endpoints, pins and flags; unmarked crossings are not joined.
"""
from pathlib import Path
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]


def read_text(path):
    raw=Path(path).read_bytes()
    if raw.startswith(b"\xff\xfe") or b"\x00" in raw[:60]:
        return raw.decode("utf-16le").lstrip("\ufeff")
    try:return raw.decode("utf-8-sig")
    except UnicodeDecodeError:return raw.decode("cp1252")


def transform(x,y,orientation):
    x,y={0:(x,y),90:(-y,x),180:(-x,-y),270:(y,-x)}[int(orientation[1:])]
    if orientation.startswith("M"):x=-x
    return x,y


def symbol(path):
    attrs={};pins=[];geometry=[]
    for line in read_text(path).splitlines():
        if line.startswith("SYMATTR "):
            _,key,value=line.split(" ",2);attrs[key]=value
        elif line.startswith("PIN "):
            t=line.split();pins.append({"point":(int(t[1]),int(t[2]))})
        elif line.startswith("PINATTR "):
            _,key,value=line.split(" ",2);pins[-1][key]=value
        elif line.startswith(("LINE ","RECTANGLE ","CIRCLE ","ARC ","TEXT ")):
            geometry.append(line)
    return attrs,pins,geometry


def schematic(path):
    path=Path(path);text=read_text(path)
    wires=[];flags=[];parts=[];directives=[]
    for line in text.splitlines():
        if line.startswith("WIRE "):
            _,x,y,a,b=line.split();wires.append(((int(x),int(y)),(int(a),int(b))))
        elif line.startswith("FLAG "):
            _,x,y,name=line.split(maxsplit=3);flags.append(((int(x),int(y)),name))
        elif line.startswith("SYMBOL "):
            _,name,x,y,angle=line.split()
            attrs,pins,geometry=symbol(path.parent/(name+".asy"))
            parts.append({"symbol":name,"origin":(int(x),int(y)),"orientation":angle,
                          "attrs":attrs.copy(),"pins":[],"geometry":geometry})
            for pin in pins:
                dx,dy=transform(*pin["point"],angle)
                parts[-1]["pins"].append({**pin,"local":pin["point"],"point":(int(x)+dx,int(y)+dy)})
        elif line.startswith("SYMATTR "):
            _,key,value=line.split(" ",2);parts[-1]["attrs"][key]=value
        elif line.startswith("TEXT ") and "!" in line:
            directives.extend(x.strip() for x in line.split("!",1)[1].split("\\n") if x.strip())
    return {"path":path,"wires":wires,"flags":flags,"parts":parts,"directives":directives}


def connectivity(data):
    points={p for wire in data["wires"] for p in wire}
    points.update(p for p,_ in data["flags"])
    points.update(pin["point"] for part in data["parts"] for pin in part["pins"])
    parent={p:p for p in points}
    def find(p):
        while parent[p]!=p:
            parent[p]=parent[parent[p]];p=parent[p]
        return p
    def union(a,b):
        parent[find(b)]=find(a)
    for a,b in data["wires"]:
        for p in points:
            if (p[0]-a[0])*(b[1]-a[1])==(p[1]-a[1])*(b[0]-a[0]) and min(a[0],b[0])<=p[0]<=max(a[0],b[0]) and min(a[1],b[1])<=p[1]<=max(a[1],b[1]):
                union(a,p)
    by_label={}
    for p,label in data["flags"]:
        label=label.casefold()
        if label in by_label:union(p,by_label[label])
        by_label[label]=p
    node_labels={}
    for p,label in data["flags"]:
        node_labels.setdefault(find(p),[]).append(label)
    pin_nodes={}
    for part in data["parts"]:
        name=part["attrs"]["InstName"]
        pin_nodes[name]={int(pin["SpiceOrder"]):find(pin["point"]) for pin in part["pins"]}
    return find,pin_nodes,{label:find(point) for label,point in by_label.items()},node_labels


def validate(folder):
    folder=Path(folder);data=schematic(folder/"Model.asc")
    issues=[];dependencies=[]
    names=[p["attrs"]["InstName"].casefold() for p in data["parts"]]
    if len(set(names))!=len(names):issues.append("Duplicate instance names")
    trans=[s for s in data["directives"] if s.lower().startswith(".tran ")]
    if len(trans)!=1:issues.append("Expected one active transient command")
    for part in data["parts"]:
        attrs=part["attrs"]
        filename=attrs.get("ModelFile")
        if filename:
            file=folder/filename
            if not file.is_file():issues.append("Missing model file: "+filename)
            else:dependencies.append({"file":filename,"sha256":hashlib.sha256(file.read_bytes()).hexdigest(),"protected_vendor_model":b"<Binary File>" in file.read_bytes()[:100]})
        if re.search(r"[/\\]",part["symbol"]):issues.append("Nonlocal symbol reference")
    for directive in data["directives"]:
        match=re.match(r"(?i)^\.(?:include|inc|lib)\s+[\"']?([^\"']+?)[\"']?$",directive)
        if match and not (folder/match[1]).is_file():issues.append("Missing include: "+match[1])
    find,pins,labels,node_labels=connectivity(data)
    checks={}
    key=folder.name
    if key.startswith("04_"):
        out=labels["out"];ground=labels["0"]
        checks["I1_connected_between_OUT_and_ground"]=pins["I1"][1]==out and pins["I1"][2]==ground
        checks["no_extra_Iload_directive"]=not any(re.match(r"(?i)^Iload\s",d) for d in data["directives"])
        checks["four_inductors_join_output"]=all(out in pins[name].values() for name in ("L1","L2","L3","L4"))
        cap=next(p for p in data["parts"] if p["attrs"]["InstName"]=="C2")
        checks["capacitor_bank_explicit"]=cap["attrs"]["Value"]=="1500u" and "Value2" not in cap["attrs"]
    elif key.startswith("05_"):
        sh,clk,vin,ground=(labels[k] for k in ("sh_out","clk","vin","0"))
        checks["clock_distinct_from_sample_node"]=sh!=clk
        checks["switch_connects_input_to_hold_node"]=pins["S1"][1]==sh and pins["S1"][2]==vin
        checks["switch_control_is_clock_to_ground"]=pins["S1"][3]==clk and pins["S1"][4]==ground
        checks["hold_cap_on_sample_node"]=pins["C1"][1]==sh and pins["C1"][2]==ground
        checks["quantizer_output_to_ground"]=pins["B1"][1]==labels["dgtl_out"] and pins["B1"][2]==ground
    for name,passed in checks.items():
        if not passed:issues.append("Connectivity check failed: "+name)
    return {"model":key,"static_status":"PASS" if not issues else "FAIL",
            "native_ltspice_executed_here":False,"electrical_acceptance":"NOT_VERIFIED",
            "component_count":len(names),"active_transient":trans,
            "checks":checks,"dependencies":dependencies,"issues":issues,
            "labels":{label:list(point) for label,point in sorted(labels.items())}}


def adc_netlist(folder):
    data=schematic(Path(folder)/"Model.asc")
    _,pins,labels,node_labels=connectivity(data)
    node_names={point:sorted(set(names))[0] for point,names in node_labels.items()}
    for name,point in labels.items():node_names[point]="0" if name=="0" else node_names.get(point,name)
    for part in data["parts"]:
        for point in pins[part["attrs"]["InstName"]].values():
            if point not in node_names:node_names[point]=f"N{len(node_names):03d}"
    rows=["ADC working schematic connectivity export; no SAR bit trial modeled"]
    for part in data["parts"]:
        attrs=part["attrs"];name=attrs["InstName"]
        if attrs["Prefix"] not in ("R","C","L","V","I","B","S"):
            raise ValueError("ADC exporter does not support this device prefix")
        nodes=" ".join(node_names[pins[name][order]] for order in sorted(pins[name]))
        rows.append(f'{name} {nodes} {attrs["Value"]}')
    rows.extend(data["directives"])
    return "\n".join(rows)+"\n.end\n"


def main():
    results=[validate(folder) for folder in sorted((ROOT/"models").iterdir()) if (folder/"Model.asc").is_file()]
    output=ROOT/"validation";output.mkdir(exist_ok=True)
    (output/"static_checks.json").write_text(json.dumps(results,indent=2)+"\n")
    adc=next((ROOT/"models").glob("05_*"))
    (adc/"Model.cir").write_text(adc_netlist(adc),encoding="utf-8")
    for result in results:
        print(result["model"],result["static_status"],f'({result["component_count"]} components)')
        for issue in result["issues"]:print("  "+issue)
    return 0 if len(results)==5 and all(r["static_status"]=="PASS" for r in results) else 1


if __name__=="__main__":raise SystemExit(main())
