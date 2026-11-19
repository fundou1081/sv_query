#!/usr/bin/env python3
"""P187 bit-level oracle queries for case 2 (DTLB PPN bit-selects)."""
import json, subprocess, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
BUNDLE = Path(__file__).resolve().parents[1]
OUT = BUNDLE / 'results'
OUT.mkdir(exist_ok=True)

CASES = {
 'c2_parent': (BUNDLE / 'fl_c2_parent.f', [
    'p187_mmu_top.u_mmu.lsu_dtlb_ppn_o[PPNWMin - CVA6Cfg.VpnLen / CVA6Cfg.PtLevels:9 + CVA6Cfg.PtLevels]',
    'p187_mmu_top.u_mmu.lsu_dtlb_ppn_o[PPNWMin:12]',
 ]),
 'c2_fix': (BUNDLE / 'fl_c2_fix.f', [
    'p187_mmu_top.u_mmu.lsu_dtlb_ppn_o[0:MegaPageSubstWidth]',
    'p187_mmu_top.u_mmu.lsu_dtlb_ppn_o[PPNWMin - 12:0]',
 ]),
}

summary = {}
for variant, (fl, nodes) in CASES.items():
    summary[variant] = {}
    for i, node in enumerate(nodes):
        for label, argv in [('drv', ['drivers', node, '--evidence']),
                            ('cf', ['controlflow', 'analyze', node, '--evidence'])]:
            cmd = ['python3', 'run_cli.py'] + argv + ['--filelist', fl, '--json']
            t0 = time.time()
            p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
            elapsed = time.time() - t0
            key = f'bit{i}_{label}'
            (OUT / f'{variant}__{key}.json').write_text(p.stdout)
            (OUT / f'{variant}__{key}.err').write_text(p.stderr)
            rec = {'node': node, 'cmd': ' '.join(cmd), 'rc': p.returncode,
                   'elapsed_s': round(elapsed, 3)}
            try:
                d = json.loads(p.stdout); res = d.get('result', {})
                rec['ok'] = d.get('ok'); rec['error_code'] = d.get('error_code')
                sigs = res.get('signals', [])
                if sigs:
                    rec['resolution'] = sigs[0].get('resolution')
                    rec['error'] = sigs[0].get('error')
                    if label == 'drv':
                        rec['driver_exprs'] = [x.get('evidence', {}).get('expression', '')
                                               for x in sigs[0].get('drivers', []) if x.get('evidence')]
                        rec['driver_ids'] = [x.get('id') for x in sigs[0].get('drivers', [])]
                    else:
                        cds = res.get('conditioned_drivers', [])
                        rec['conditions'] = [c.get('expr') for cd in cds for c in cd.get('conditions', [])]
                        rec['warnings'] = res.get('warnings')
            except Exception as e:
                rec['parse_error'] = str(e)
            summary[variant][key] = rec
            print(f'[{variant}/{key}] rc={rec["rc"]} t={rec["elapsed_s"]}s ok={rec.get("ok")} res={rec.get("resolution")}')
(OUT / 'bit_summary.json').write_text(json.dumps(summary, indent=2))
