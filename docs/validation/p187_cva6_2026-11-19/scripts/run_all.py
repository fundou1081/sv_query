#!/usr/bin/env python3
"""P187 measurement harness: run sv_query queries on 4 CVA6 filelist variants.
Records wall time, exit code and a compact fact extract. Not product code.
"""
import json
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
BUNDLE = Path(__file__).resolve().parents[1]
OUT = BUNDLE / 'results'
OUT.mkdir(exist_ok=True)

VARIANTS = {
    'c1_parent': BUNDLE / 'fl_c1_parent.f',
    'c1_fix': BUNDLE / 'fl_c1_fix.f',
    'c2_parent': BUNDLE / 'fl_c2_parent.f',
    'c2_fix': BUNDLE / 'fl_c2_fix.f',
}

QUERIES = {
    'c1_parent': [
        ('drv_canonical', ['drivers', 'p187_mmu_top.u_mmu.canonical_addr_check', '--evidence']),
        ('df_vaddr_to_canonical', ['dataflow', 'analyze', 'p187_mmu_top.u_mmu.lsu_vaddr_i',
                                   'p187_mmu_top.u_mmu.canonical_addr_check']),
        ('prof_canonical', ['trace', 'profile', 'p187_mmu_top.u_mmu.canonical_addr_check']),
    ],
    'c1_fix': [
        ('drv_canonical', ['drivers', 'p187_mmu_top.u_mmu.canonical_addr_check', '--evidence']),
        ('df_vaddr_to_canonical', ['dataflow', 'analyze', 'p187_mmu_top.u_mmu.lsu_vaddr_i',
                                   'p187_mmu_top.u_mmu.canonical_addr_check']),
        ('prof_canonical', ['trace', 'profile', 'p187_mmu_top.u_mmu.canonical_addr_check']),
    ],
    'c2_parent': [
        ('drv_dtlb_ppn', ['drivers', 'p187_mmu_top.u_mmu.lsu_dtlb_ppn_o', '--evidence']),
        ('cf_dtlb_ppn', ['controlflow', 'analyze', 'p187_mmu_top.u_mmu.lsu_dtlb_ppn_o', '--evidence']),
        ('df_vaddrn_to_ppn', ['dataflow', 'analyze', 'p187_mmu_top.u_mmu.lsu_vaddr_n',
                              'p187_mmu_top.u_mmu.lsu_dtlb_ppn_o']),
    ],
    'c2_fix': [
        ('drv_dtlb_ppn', ['drivers', 'p187_mmu_top.u_mmu.lsu_dtlb_ppn_o', '--evidence']),
        ('cf_dtlb_ppn', ['controlflow', 'analyze', 'p187_mmu_top.u_mmu.lsu_dtlb_ppn_o', '--evidence']),
        ('df_vaddrn_to_ppn', ['dataflow', 'analyze', 'p187_mmu_top.u_mmu.lsu_vaddr_n',
                              'p187_mmu_top.u_mmu.lsu_dtlb_ppn_o']),
    ],
}

summary = {}
for variant, filelist in VARIANTS.items():
    summary[variant] = {}
    for label, argv in QUERIES[variant]:
        cmd = ['python3', 'run_cli.py'] + argv + ['--filelist', filelist, '--json']
        t0 = time.time()
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        elapsed = time.time() - t0
        out = OUT / f'{variant}__{label}.json'
        out.write_text(p.stdout)
        (OUT / f'{variant}__{label}.err').write_text(p.stderr)
        rec = {'cmd': ' '.join(cmd), 'rc': p.returncode, 'elapsed_s': round(elapsed, 3),
               'stdout_bytes': len(p.stdout), 'stderr_bytes': len(p.stderr)}
        try:
            d = json.loads(p.stdout)
            rec['ok'] = d.get('ok')
            rec['error_code'] = d.get('error_code')
            res = d.get('result', {})
            if label.startswith('drv_'):
                sigs = res.get('signals', [])
                rec['driver_count'] = len(sigs[0].get('drivers', [])) if sigs else None
                rec['driver_exprs'] = [x.get('evidence', {}).get('expression', '')
                                       for x in (sigs[0].get('drivers', []) if sigs else [])
                                       if x.get('evidence')]
                rec['driver_ids'] = [x.get('id') for x in (sigs[0].get('drivers', []) if sigs else [])]
            elif label.startswith('cf_'):
                res2 = res.get('result', res)
                cds = res2.get('conditioned_drivers', [])
                rec['conditioned_count'] = len(cds)
                rec['conditions'] = [c.get('expr') for cd in cds for c in cd.get('conditions', [])]
            elif label.startswith('df_'):
                rec['is_reachable'] = res.get('is_reachable')
                rec['search_status'] = res.get('search_status')
                rec['latency'] = res.get('primary_latency_cycles')
                rec['paths_count'] = res.get('paths_count')
                rec['conditions'] = res.get('all_conditions')
                rec['segments'] = [[s.get('from_signal'), s.get('to_signal'), s.get('driver'),
                                    s.get('condition'), s.get('timing')]
                                   for pth in res.get('paths', []) for s in pth.get('segments', [])][:8]
            elif label.startswith('prof_'):
                sigs = res.get('signals', [])
                if sigs:
                    s = sigs[0]
                    rec['resolution'] = s.get('resolution')
                    rec['driver_count'] = s.get('driver_count')
                    rec['load_count'] = s.get('load_count')
                    rec['sequential'] = s.get('sequential')
        except Exception as e:
            rec['parse_error'] = str(e)
        summary[variant][label] = rec
        print(f'[{variant}/{label}] rc={rec["rc"]} t={rec["elapsed_s"]}s ok={rec.get("ok")}')

(OUT / 'summary.json').write_text(json.dumps(summary, indent=2))
print('WROTE', OUT / 'summary.json')
