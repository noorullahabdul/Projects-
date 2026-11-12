"""Static package checks that do not replace a real LTspice simulation run."""
from pathlib import Path
import re

root=Path(__file__).resolve().parent
netlists=['DCLINK_CR004_NOMINAL.cir','DCLINK_CR004_CORNERS.cir','DCLINK_CR004_FAULTS.cir']
required=['Vbat','Rneg_sw','Rpos_sw','Rpre_sw','Rpre','Cdc','Rdis_sw',
          'Bpack_sns','Bdc_sns','Bneg_cmd','Bpos_cmd','Bpre_cmd','Bdis_cmd',
          '.tran','.meas','.end']
for name in netlists:
    text=(root/name).read_text()
    assert text.lower().count('.end')==1, f'{name}: exactly one .end required'
    assert text.count('{')==text.count('}'), f'{name}: unbalanced parameter braces'
    for token in required:
        assert re.search(re.escape(token),text,re.I), f'{name}: missing {token}'
    assert '.include' not in text.lower(), f'{name}: external library dependency found'

corn=(root/'DCLINK_CR004_CORNERS.cir').read_text()
assert all(x in corn for x in ['.step param VPACK','.step param CDC','.step param RPRE25',
                               '.step param TEMPAMB','.step param EPACK',
                               '.step param ELINK','.step param RSOURCE'])
fault=(root/'DCLINK_CR004_FAULTS.cir').read_text()
assert '.step param FAULT list 0 1 2 3 4 5 6 7 8 9' in fault

asc=(root/'DCLINK_CR004_SYSTEM.asc').read_text()
assert asc.startswith('Version 4')
assert asc.count('SYMBOL ')>=18
assert asc.count('SYMATTR InstName')==asc.count('SYMBOL ')
assert all(x in asc for x in ['DCPLUS','DCMINUS','HVP','NEG_CMD','PRE_CMD','POS_CMD','DIS_CMD'])

print('Static LTspice package checks passed.')
print('Netlists: 3; corner runs: 972; fault configurations: 10.')
print('Local LTspice execution is still required for syntax, convergence and waveform validation.')
