#!/usr/bin/env python3
"""Read-only inventory of the supplied reformulation corpus; no proof acceptance.

Only the explicitly chosen JSON/Markdown output paths are written. File hashes
identify bytes, not semantics. Report statements and old verifier results are
recorded as untrusted claims, never promoted to kernel certification.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

FAMILIES = {
    'A': 'affine elimination, aliases, complementary coordinates',
    'B': 'forced values, bounds, exact row implication and redundancy',
    'C': 'finite-domain, one-hot and Boolean projection',
    'D': 'conditional bounds, big-M and integer rounding',
    'E': 'one-hot aggregation, conflict cliques and packing',
    'F': 'signed differences, network flow and aggregation',
    'G': 'shared DAG, rank and repeated expression compression',
    'H': 'dominance, normalization and conditional integrality',
    'I': 'arithmetic-progression menu/index encoding',
    'J': 'combinatorial geometry/cardinality theorem',
    'K': 'modular parity and unique feasible-point certification',
}
# 8--48 are read from the actual textbook map; later cases are reviewed report summaries.
LATER = {
49: ('BD','Node-cut rounding plus one dependent balance deletion','Same integer points and objective; strict LP strengthening'),
50: ('BC','Implied integrality, aggregate equalities, opposite rows and empty tautologies','Same feasible vectors and objective in original named variables; LP geometry unchanged'),
51: ('ABCD','Score substitutions, dominance fixing, min-selector projection and comparison tightening','Objective-preserving integer projection; LP strengthened'),
52: ('ABCD','Score domination, fixed selector propagation and threshold/score substitution','Objective-preserving unique integer lifting; LP need not coincide'),
53: ('ABD','Equality-based epigraph sparsification, rounded load bounds and dependent equality','Same mixed-integer points and objective; strict LP strengthening'),
54: ('ABH','Forced values, affine substitutions, box redundancy and monotone endpoint projection','Same retained-coordinate projection and attainable objective values; not bijective on monotone auxiliaries'),
55: ('BCD','Continuous linking-auxiliary projection with certified activation bounds','Same integer projection and objective with simultaneous lift; projected LP not weaker'),
56: ('BDE','Binary zero fixing, paired cardinalities, sparse row replacement and subset redundancy','Integer feasible-set projection and objective preserved; see report for individual LP claims'),
57: ('AB','Bounded binary-sum auxiliary elimination','Objective-preserving affine bijection; original auxiliary bounds must be implied'),
58: ('BFH','Counterflow normalization, activation/parallel dominance and signed network reduction','Feasibility and minimum objective preserved; objective-preserving final-to-original lift'),
59: ('ACI','Arithmetic-progression menu compression and defined auxiliary elimination','Integer option correspondence and objective preservation; aggregate LP projection correspondence'),
60: ('ACI','Activation plus bounded option-index encoding and auxiliary substitution','Objective-preserving integer bijection; aggregate LP projection unchanged'),
61: ('BC','Boolean conjunction/OR private auxiliary elimination using local hull','Integer projection and objective preservation; local hull strengthening'),
62: ('BC','Boolean private auxiliary elimination','Integer projection with complete Boolean reconstruction; see report for LP scope'),
63: ('ABF','Sparse slack-difference coordinate reformulation','Objective-preserving affine feasible-set correspondence; LP correspondence'),
64: ('ABC','Integer alias proofs, ordered fixing and auxiliary substitutions','Integer-equivalent projection and objective; LP equality not assumed'),
65: ('B','Delete 52,554 rows by retained linear implications and nonnegative bounds','Same feasible sets in original coordinates, objective and LP relaxation'),
66: ('DE','Five-cycle matching inequalities with activation gates','Same integer points and objective; strict LP strengthening'),
67: ('BCDE','Graph coloring activation fixing and row/objective substitution','Same integer feasible assignments in original variables and objective'),
68: ('BG','Invertible consecutive differences of balance equalities','Same original-coordinate feasible set, objective and LP relaxation'),
69: ('ABDH','Interval shortening, translation normalization, equality-component reduction and gates','Same projection onto all original binaries and every objective value; endpoint assignments not all retained'),
70: ('BD','Certified aggregate-gate coefficient tightening','Same integer points and objective; valid gate strengthening'),
71: ('EJ','Verified even-parity Hamming geometry and cardinality cut','Same integer points and objective; strict LP strengthening; exact optimum -12'),
72: ('BCEH','Conditional auxiliary completion, integrality relaxation and clique strengthening','Same primary binary projection and minimum completion cost; objective epigraph equivalence'),
73: ('BE','Conflict-clique reformulation and bound redundancy','Same integer assignments and objective; LP contained in source LP'),
74: ('BC','Private binary-auxiliary projection and certified redundancy removal','Exact integer projection and objective; per-block simultaneous lifting'),
75: ('ABC','Affine integer relations, components and leaf definitions','Exact integer projection with unique reconstruction and zero objective'),
76: ('AB','Impossible choice deletion and continuous auxiliary substitution','Objective-preserving feasible-point bijection'),
77: ('AB','Choice-weight substitution and completion/resource-bound implication','Same feasible projection and objective including LP; unique reconstruction'),
78: ('BCH','Count aggregation and one-sided auxiliary integrality relaxation','Same minimum; source-to-target objective preservation and no-worse reverse reconstruction'),
79: ('B','Equality-based sparse row rewriting and exact duplicate deletion','Same feasible set, LP relaxation and objective in original variables'),
80: ('BCH','Certified optimal-face restriction and assignment-component reconstruction','All original optimal solutions bijectively parameterized; optimum -160; suboptimal points excluded'),
81: ('BD','Time-window zero fixing, implication reduction and binary coefficient tightening','Zero-extension integer bijection and objective; strict LP strengthening'),
82: ('BCD','Time-window zero fixing and pairwise binary strengthening','Zero-extension integer projection and objective; LP contained in source LP'),
83: ('ABH','Disjoint-support cost dominance and singleton substitution','Same minimum and optimal recovery; not all source feasible points'),
84: ('BK','Full-rank mod-2 certificates force unique assignment; singleton target','Feasible-set singleton bijection and objective 37; LP equality not asserted'),
85: ('BCE','Zero support propagation, reciprocal binary blocks and row dependence','Binary feasible-set zero-extension bijection and pointwise objective'),
86: ('BD','Incoming-flow cover inequalities','Same integer points and objective; strict LP strengthening'),
87: ('BH','Iterated set-cover singleton, containment, column-cost dominance and empty-column rules','Feasibility and optimal value; non-increasing-cost source map and objective-preserving reverse lift'),
88: ('ABC','Mixed-integer product/absolute-value alias reduction','Objective-preserving integer feasible-set bijection; LP equivalence explicitly not claimed'),
}
EASY = {
40: 'Smallest simple affine case: 120 complementary pairs; 274 source / 154 target variables. audit.substitutions gives y=1-x, and all changed rows are enumerated.',
79: '181 row identities modulo retained equalities plus 15 duplicate pairs; audit.modifications has both equality multipliers. Same coordinates/domains/objective.',
68: 'Consecutive equality differences with explicit prefix-sum inverse; audit.row_transformations and audit.inverse identify both directions.',
33: '90,000 redundant implication rows; audit.certificates lists each retained path of length 3--7. Straight nonnegative sum certificates, useful throughput baseline.',
65: '52,554 redundant inequalities; redundancy_certificates.tsv supplies two retained rows plus two nonnegative bound terms for every deletion.',
}
HARD = [
 {'cases':[28], 'requirement':'Joint multi-commodity reconstruction', 'detail':'Flow aggregation must distribute the complete aggregate, including cycles, to all original commodities while preserving shared capacities and every objective value. Independent existence per output coordinate is insufficient.'},
 {'cases':[38,57,59,60], 'requirement':'Shared expressions and finite-domain reconstruction', 'detail':'Shared DAG recursion and menu/index compression require complete incidence/domain binding and avoid expanding shared affine expressions repeatedly. test60 final target is LP.'},
 {'cases':[47,48,58,69,72,78,80,83,87], 'requirement':'Contract distinctions and non-affine normalization', 'detail':'Dominance, sorting/counting, interval normalization, conditional simplex completions and optimal-face restriction do not all preserve full feasible sets or attainable objectives. Prove exactly the committed contract.'},
 {'cases':[66,67,71], 'requirement':'Graph and coding-theoretic structure', 'detail':'Odd-cycle cuts, coloring activation and Plotkin cardinality need exact coefficient-to-graph/label binding. test71 has 1,024 labels and 523,776 distinct pair relations.'},
 {'cases':[84,88], 'requirement':'Integrality-specific identities', 'detail':'test84 uses 100 mod-2 original-row certificates to force a singleton. test88 alias equalities depend on mixed-integer product blocks, not just duplicate rows.'},
]


def identity(path: Path, relative_to: Path | None = None):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return {'path': str(path.relative_to(relative_to)) if relative_to else str(path),
            'bytes': path.stat().st_size, 'sha256': h.hexdigest()}


def paragraphs(text):
    """Retain exact paragraphs, with their source line numbers, for claim auditing."""
    result = []
    start, current = None, []
    for line_no, line in enumerate(text.splitlines() + [''], 1):
        if line.strip():
            if start is None: start = line_no
            current.append(line)
        elif current:
            result.append({'line': start, 'text': '\n'.join(current)})
            start, current = None, []
    return result


def json_summary(path):
    try:
        data = json.loads(path.read_text())
    except (ValueError, UnicodeDecodeError):
        return {'format': 'not_single_json_object'}
    if not isinstance(data, dict):
        return {'format': type(data).__name__, 'items':len(data) if isinstance(data,list) else None}
    result = {'format': 'json_object', 'top_level_keys': list(data)}
    result['field_shapes'] = {k: {'type':type(v).__name__, 'items':len(v) if isinstance(v,(list,dict)) else None} for k,v in data.items()}
    result['contract_fields'] = {k:v for k,v in data.items() if isinstance(v,str) and re.search(r'claim|equival|proof|projection|commit|modification|decision|scope',k,re.I)}
    hashclaims=[]
    def walk(value, path, depth):
        if isinstance(value,dict) and depth < 5:
            for k,v in value.items():
                if isinstance(v,str) and re.fullmatch(r'[a-fA-F0-9]{64}',v) and re.search(r'sha|hash',k,re.I):
                    hashclaims.append({'json_pointer': '/'+ '/'.join(path+[k]),'sha256':v.lower()})
                elif isinstance(v,dict): walk(v,path+[k],depth+1)
    walk(data,[],0)
    result['claimed_sha256s']=hashclaims
    return result


def textbook_cases(path):
    text=path.read_text()
    result={}
    for line in text.splitlines():
        match=re.match(r'\\hyperref\[case:test(\d+)\]\{test\d+\}\s*&\s*([^&]+)&\s*([^&]+)&\s*(.*?)\\\\',line)
        if match:
            n,fam,transform,contract=match.groups()
            result[int(n)]=(re.findall('[A-H]',fam),transform.strip(),contract.strip())
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runs', type=Path, default=Path('/Users/bhz/Code/reform_test/runs'))
    ap.add_argument('--textbook',type=Path,default=Path('/Users/bhz/Code/reform_test/docs/nomf_textbook/nomf_reformulation_textbook.tex'))
    ap.add_argument('--json',type=Path,default=Path('audit/corpus_inventory.json'))
    ap.add_argument('--markdown',type=Path,default=Path('audit/corpus_audit.md'))
    args=ap.parse_args()
    runs=args.runs.resolve(); book=args.textbook.resolve(); early=textbook_cases(book)
    cases=[]
    directories=sorted((p for p in runs.iterdir() if p.is_dir() and re.match(r'^test\d+(?:-|$)',p.name)),key=lambda p:(int(re.match(r'test(\d+)',p.name).group(1)),p.name))
    for run in directories:
        n=int(re.match(r'test(\d+)',run.name).group(1))
        report=run/'output/report.md'; report_text=report.read_text() if report.exists() else ''
        files=[identity(p,run) for p in sorted(run.rglob('*')) if p.is_file()]
        bypath={f['path']:f for f in files}
        sources=[f for f in files if f['path'].startswith('input/') and Path(f['path']).suffix.lower() in ('.mps','.lp')]
        targets=[f for f in files if f['path'].startswith('output/') and Path(f['path']).suffix.lower() in ('.mps','.lp')]
        if n in LATER:
            family,transform,contract=LATER[n]; family=list(family); summary_origin='reviewed final report (not kernel validation)'
        elif n in early:
            family,transform,contract=early[n];summary_origin='textbook method-map row (not kernel validation)'
        else:
            family=[];transform=report_text.splitlines()[0] if report_text else 'UNREVIEWED';contract='UNREVIEWED';summary_origin='unreviewed'
        ps=paragraphs(report_text)
        claims=[p for p in ps if re.search(r'equival|bijection|preserv|projection|same feasible|same integer|scope|LP.{0,30}(strong|weaker|equal)|relaxation.{0,35}(strong|same|equal)',p['text'],re.I)]
        exploratory=[p for p in ps if re.search(r'reject|not committed|uncommitted|not selected|not justified|falsif|inconclusive|unavailable|not established',p['text'],re.I)]
        jsons={str(p.relative_to(run)):json_summary(p) for p in sorted((run/'output').glob('*.json'))}
        model_hashes={f['sha256'] for f in sources+targets}
        for summary in jsons.values():
            for h in summary.get('claimed_sha256s',[]):h['matches_observed_model_artifact']=h['sha256'] in model_hashes
        scripts=[f['path'] for f in files if f['path'].startswith('output/') and Path(f['path']).suffix=='.py']
        verifier_scripts=[s for s in scripts if 'verif' in Path(s).name.lower()]
        trace=[f['path'] for f in files if Path(f['path']).name in ('session.jsonl','run.json') or '/sessions/' in f['path']]
        missing=[]
        if not sources: missing.append('source model not present')
        if not targets: missing.append('final LP/MPS model not present')
        if not report.exists(): missing.append('final report not present')
        if not trace:missing.append('persisted full execution trajectory not present; final report/audits remain available')
        gaps=['No RPX kernel certification attached by this inventory; report and old verifier PASS claims are untrusted inputs.']
        if any(Path(f['path']).suffix=='.lp' for f in sources+targets):gaps.append('LP input/target requires trusted exact LP parsing or a checked semantics-preserving conversion; an invented MPS replacement is not acceptable.')
        if not verifier_scripts:gaps.append('No standalone persisted verifier found under output/; witness/report/session extraction is required for new proof preparation.')
        cases.append({
          'case_id':f'test{n}', 'run_name':run.name, 'run_directory':str(run),
          'status':'PROOF_NOT_COMPLETED' if sources and targets else 'MATERIAL_MISSING',
          'status_reason':'Inventory establishes artifact availability, not mathematical validity or kernel acceptance.',
          'observed_model_pair_present':bool(sources and targets),
          'source_models':sources,'final_target_models':targets,
          'target_selection_evidence': {'report':bypath.get('output/report.md'),'rule':'Final committed LP/MPS artifact(s) physically present under output/; no exploratory in-memory candidate is counted.','report_title':report_text.splitlines()[0] if report_text else None},
          'families':family,'transformation_summary':transform,'claimed_contract_summary':contract,'summary_provenance':summary_origin,
          'contract_claim_evidence':claims,
          'final_vs_exploratory': {'acceptance_target':'Actual final committed artifact listed above.','exploratory_claims_are_success_targets':False,'report_excerpts':exploratory,'note':'Exploratory proof/failed-hypothesis language is source evidence, not an established kernel status. Explicit intermediate claims remain available in the hashed trajectory and audit.'},
          'witness_material':jsons,
          'witness_requirement':'Extract complete mappings, row/domain/objective obligations, and any family-specific witness from the cited audit/report/trajectory; verify every field against the actual source and target.',
          'reproduction':{'input_artifacts_available':bool(sources and targets),'standalone_output_scripts':scripts,'legacy_verifier_commands':[f'python3 {s}' for s in verifier_scripts], 'legacy_verifier_execution':'NOT_RUN_BY_THIS_INVENTORY','execution_directory':'A disposable copy of the complete run directory; legacy verifiers may write verification.json, so never run them in the immutable corpus.','generation_provenance':trace,'generation_note':'Persisted trajectories are code/provenance, not a deterministic standalone reformulation generator or a trusted theorem. run.json can contain JSON Lines despite its filename.'},
          'missing_material':missing,'proof_or_capability_gaps':gaps,'files':files,
        })
    summary={
        'run_count':len(cases),'case_number_min':min(int(c['case_id'][4:]) for c in cases),'case_number_max':max(int(c['case_id'][4:]) for c in cases),
        'status_counts':dict(Counter(c['status'] for c in cases)),
        'model_pair_present_count':sum(c['observed_model_pair_present'] for c in cases),
        'model_format_pairs':dict(Counter('+'.join(Path(m['path']).suffix[1:] for m in c['source_models'])+'->'+'+'.join(Path(m['path']).suffix[1:] for m in c['final_target_models']) for c in cases)),
        'cases_with_persisted_verifier':sum(bool(c['reproduction']['legacy_verifier_commands']) for c in cases),
        'cases_without_full_trajectory':[c['case_id'] for c in cases if not c['reproduction']['generation_provenance']],
        'file_count':sum(len(c['files']) for c in cases),'file_bytes':sum(f['bytes'] for c in cases for f in c['files']),
        'family_membership_counts':dict(Counter(f for c in cases for f in c['families'])),
    }
    document={'schema':'rpx-corpus-inventory-v1','inventory_tool':identity(Path(__file__).resolve()),'scope':str(runs),
      'semantics':'Read-only artifact inventory. Source claims, prior audits, and SHA-256 equality are not kernel verification.',
      'status_policy':{'VERIFIED':'Reserved for actual kernel acceptance tied to source, target, RPX and full required contract; never emitted by this inventory tool.', 'TRANSFORMATION_REFUTED':'Requires exact counterevidence to the actual relation or explicitly identified mapping, not just a failed proof.', 'PROOF_NOT_COMPLETED':'Actual model pair is present but kernel certification is absent.', 'MATERIAL_MISSING':'Required model absent.', 'CAPABILITY_OR_RESOURCE_GAP':'An independent blocker field; unresolved cases remain in the denominator.'},
      'summary':summary,'textbook':{'file':identity(book),'case_ids':[f'test{n}' for n in sorted(early)],'coverage_note':'Textbook map covers test8--test48 only. Its historical directory count must not replace the current 81-run inventory.'},
      'family_definitions':FAMILIES,'first_candidates':[{'case_id':f'test{n}','rationale':s} for n,s in EASY.items()], 'hard_requirements':HARD,'cases':cases}
    args.json.parent.mkdir(parents=True,exist_ok=True); args.json.write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n')
    md=['# Reformulation corpus audit','',
        'This is an artifact and proof-demand audit, not a certification report. No existing report, Python verifier result, solver claim, or model hash is treated as mathematical authority. All source runs were read only.','',
        f"Observed **{summary['run_count']} runs**, test{summary['case_number_min']}–test{summary['case_number_max']}, with **{summary['model_pair_present_count']} source/final model pairs**. Format pairs: "+', '.join(f'{k}: {v}' for k,v in summary['model_format_pairs'].items())+'.',
        f"Status at inventory generation: **{summary['status_counts'].get('PROOF_NOT_COMPLETED',0)} proof not completed; 0 kernel-verified; 0 refuted by this audit**. These remain the coverage denominator. Artifact availability is not evidence that the claimed transformation is correct.",
        f"Hashed {summary['file_count']} files ({summary['file_bytes']:,} bytes), including source/final models, side audits, standalone scripts and hidden trajectory material. {summary['cases_with_persisted_verifier']} cases have a persisted output verifier. No legacy verifier was executed by this tool.",'',
        'The textbook method map covers test8–test48. Its historical count predates test49–test88 and is not the current corpus count. Reports are preserved as exact paragraph excerpts with source line numbers in the JSON inventory; each model and witness file has an observed SHA-256.','',
        '## Model and reproduction boundaries','',
        '- test8 is LP → LP and has an additional native artifact directory. test60 is MPS → LP. Their actual final targets must be preserved; an exact trusted LP path or checked conversion is needed.',
        '- test8 and test9 lack persisted full execution trajectories in these run directories. Their source/final models and reports are present, and test9 also has audit data and a standalone verifier. Missing trajectory is distinguished from missing model input.',
        '- Every acceptance target is the physically present final model named in its report. Rejected hypotheses, local witnesses and uncommitted alternatives are recorded separately. They are not counted as successful committed transformations.',
        '- Legacy output scripts can overwrite verification files. Reproduce them only in a disposable copy of the complete run directory. A passing legacy script is still not RPX kernel certification.',
        '- The inventory does not execute generation code extracted from trajectories. Case preparation still needs complete RPA/RPX plus the actual canonical source/target models.',
        '- MPS parsing is part of the trusted boundary. Actual files include widened numeric fields, free-format/long names, two coefficient pairs per line, integer markers, LI bounds, empty RANGES and objective constants. Unsupported semantics must be rejected explicitly.','',
        '## First complete-model candidates','']
    for n,s in EASY.items(): md.append(f'- **test{n}**: {s}')
    md+=['','These are candidates for real end-to-end certification, not certified cases. Their model pair and witness availability make them useful before implementing harder reconstruction rules.','','## Hard requirements that cannot be excluded','']
    for item in HARD:md.append('- **'+', '.join('test'+str(n) for n in item['cases'])+' — '+item['requirement']+'**: '+item['detail'])
    md+=['','## Complete final-target ledger','',
        'Family letters are defined below. Every row has status **proof not completed** until actual kernel evidence supersedes it. Contract text summarizes source claims; the JSON retains the original excerpts.','',
        '| Case | Families | Actual final artifact | Claimed contract |',
        '|---|---|---|---|']
    for c in cases:
        target=', '.join(m['path'] for m in c['final_target_models']) or 'MISSING'
        md.append('| '+c['case_id']+' | '+', '.join(c['families'])+' | `'+target+'` | '+c['claimed_contract_summary'].replace('|','\\|')+' |')
    md+=['','## Family definitions','']+[f'- **{f}** ({summary["family_membership_counts"].get(f,0)} cases): {label}.' for f,label in FAMILIES.items()]
    md+=['','Family memberships overlap. Instance coverage and family coverage must both be reported; a supported family does not certify every member automatically.','','## Rebuild this inventory','',
        'Run from the kernel repository:', '', '```sh', 'python3 tools/inventory_corpus.py', '```','',
        'The tool deterministically hashes and reads the supplied corpus, then writes only `audit/corpus_inventory.json` and `audit/corpus_audit.md`. It intentionally does not turn previous PASS fields into verified status. Re-running it returns the inventory baseline; keep kernel certification evidence in a separate acceptance ledger until explicitly merged.','']
    args.markdown.parent.mkdir(parents=True,exist_ok=True);args.markdown.write_text('\n'.join(md))
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
