"""Reviewer 1 4.7, S0/G0 only. Static inventory; never import project modules.

Reads bytes, OOXML, PDF text, JSON metadata, CSV headers and AST. Does not load
model checkpoints, aggregate training labels, replay predictions, execute DP,
invoke solvers, or write outside the independent --out directory.
"""
from __future__ import annotations

import argparse
import ast
import csv
import difflib
import gzip
import hashlib
import json
import re
import subprocess
import sys
import time
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from lxml import etree
from pypdf import PdfReader


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(2 ** 20), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return Path(path).read_text(encoding='utf-8-sig')


def load(path):
    return json.loads(read(path))


def dump(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def table(path, rows, fields=None):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                        for k, v in row.items()})


def link(path, label=None, line=None):
    p = Path(path).as_posix() + (f':{line}' if line else '')
    return f'[{label or Path(path).name}](<{p}>)'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, choices=['G0'])
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    project = root.parent
    if out == root or not out.is_relative_to(root):
        raise ValueError('Output must be an independent subdirectory of --root')
    audit = out / '00_audit'
    audit.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    events, checks, conflicts, missing, coverage, bindings = [], [], [], [], [], []
    def log(event, **data):
        events.append({'utc': datetime.now(timezone.utc).isoformat(), 'event': event, **data})
        print(json.dumps({'event': event, **data}, ensure_ascii=False), flush=True)
    def check(name, passed, detail):
        checks.append({'check': name, 'status': 'PASS' if passed else 'FAIL', 'detail': detail})
    def conflict(cid, kind, paths, difference, impact, status='VERSION_CONFLICT'):
        conflicts.append({'conflict_id': cid, 'status': status, 'kind': kind,
                          'paths': [str(p) for p in paths], 'difference': difference,
                          'impact_and_disposition': impact})
    home = project / '老家' / 'sci-jcr2区交付'
    train = home / '第二周工作/v2_day2_huber_ensemble'
    week1 = home / '第二周工作/day1_freeze_preprocess/week1_recovery_dataset_v1.0'
    expansion = home / '第二周工作/v2_day1_training_expansion'
    formal = home / '第三周工作/day7_final_method_protocol_freeze_v1.1'
    old = home / '第三周工作/day7_final_method_protocol_freeze'
    day2 = home / '第四周工作/day2_candidate_screening_v1.0'
    day3 = home / '第四周工作/day3_live_ue_methods_v1.0'
    day4 = home / '第四周工作/day4_exact_reference_regret_v1.0'
    snapshot = root / '4.1专项返修_20261026/正式模拟_v2/source_snapshot'
    plan = Path('C:/Users/Wuzeqian.PC-20220914MSMS/Downloads/Reviewer1_4.7_方法可复现性与公式核查_Codex实施方案.md')
    reviewer = Path('E:/微信存储/xwechat_files/wxid_x5h5gu0ixjjx21_e4e5/msg/file/2026-10/Review of Surrogate_Guided_Road_Reopening.pdf')
    manuscript = project / 'Manuscript(1).docx'
    manuscript14 = root / 'Manuscript (14).docx'
    supplement = home / '初稿/Frontiers_Submission_Package_P1_v2.2/Supplementary_Material.docx'
    log('start', stage='G0', root=str(root), out=str(out), python=sys.executable)

    # rg discovery excludes dependencies/caches; no repository script is invoked.
    excluded = ['node_modules', '__pycache__', '.git', '.venv', 'venv', 'site-packages',
                'python_deps', 'runtime_deps', 'runtime_cache', 'browser_profile']
    cmd = ['rg', '--files', '--hidden', str(project)]
    for token in excluded:
        cmd += ['-g', f'!**/{token}/**']
    proc = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace', check=True)
    discovered = sorted({Path(s) for s in proc.stdout.splitlines() if s and not Path(s).is_relative_to(out)})
    records, selected, hashes = [], {}, {}
    formal_dirs = ('day7_final_method_protocol_freeze', 'day1_problem_freeze', 'day2_exact_dp_baseline',
                   'day3_candidate_pool', 'day4_multichannel_screening')
    documentation = re.compile(r'manuscript|supplement|review|response|返稿信|初稿|报告|验收|结论|索引|意见|readme|protocol|协议|freeze|manifest|validation|核对', re.I)
    def classify(p):
        s, n = p.as_posix(), p.name.lower()
        if p.suffix.lower() == '.py':
            return 'source_code'
        if p.suffix.lower() == '.docx' and documentation.search(n):
            return 'manuscript_supplement_or_response'
        if p.suffix.lower() == '.pdf' and re.search(r'Review|Supplement|Manuscript|审稿', n, re.I):
            return 'document_pdf'
        if p.is_relative_to(train):
            return 'original_training_asset'
        if p.is_relative_to(week1) or p.is_relative_to(expansion):
            if n.endswith(('.csv', '.csv.gz', '.json', '.md', '.txt', '.npz', '.log')) and 'ue_checkpoint' not in n:
                return 'training_data_and_sampling_asset'
        if any(x in s for x in formal_dirs) and p.suffix in ('.json', '.txt', '.md', '.log'):
            return 'historical_method_freeze_record'
        if p.is_relative_to(snapshot) and p.suffix.lower() in ('.json', '.pt', '.txt', '.csv', '.tntp'):
            return 'revision_4_1_frozen_snapshot'
        if 'surrogate/final_ensemble' in s and p.suffix.lower() in ('.json', '.pt', '.csv', '.gz', '.npz'):
            return 'ensemble_archived_copy'
        if p.is_relative_to(day2) or p.is_relative_to(day3) or p.is_relative_to(day4):
            if p.suffix.lower() in ('.json', '.log', '.txt', '.md'):
                return 'original_formal_execution_record'
        if (p.is_relative_to(day2) and n in ('candidate_pool.csv.gz', 'screened_candidates.csv', 'primary_candidates.csv')):
            return 'frozen_formal_candidate_output'
        if p.parent == project and p.suffix.lower() == '.zip':
            return 'existing_archive_container'
        if p.suffix.lower() in ('.json', '.md', '.txt', '.csv') and documentation.search(n):
            if re.search(r'/scenario_\d+|/seed_\d+|/models/|/node_modules/', s):
                return None
            return 'prior_revision_or_provenance_record'
        return None
    def priority(p, role):
        s = p.as_posix()
        if p.is_relative_to(train) or p.is_relative_to(day2) or p.is_relative_to(day3) or p.is_relative_to(day4):
            return 'P1_actual_archive_and_hash_binding'
        if p.is_relative_to(formal):
            return 'P2_bound_formal_source'
        if 'reproducibility-v1.0-public/' in s or 'reproducibility-v1.0/' in s:
            return 'P4_current_public_or_release_copy'
        return 'P3_historical_manifest_document_or_revision'
    def add(p, role):
        p = Path(p)
        if not p.is_file():
            return False
        if p not in selected:
            h = sha(p)
            hashes[p] = h
            selected[p] = {'source_id': '', 'path': str(p), 'relative_to_project': str(p.relative_to(project)) if p.is_relative_to(project) else 'EXTERNAL',
                           'sha256': h, 'bytes': p.stat().st_size, 'source_type': role,
                           'evidence_priority': priority(p, role), 'version_context': str(p.parent),
                           'frozen_role': role}
        return True
    for p in discovered:
        role = classify(p)
        records.append({'path': str(p), 'bytes': p.stat().st_size, 'selected': bool(role),
                        'selection_reason': role or 'outside_G0_selected_evidence_scope'})
        if role:
            add(p, role)
    for p, role in [(plan, 'user_execution_protocol'), (reviewer, 'original_reviewer_1_report')]:
        add(p, role)
    table(audit / 'discovery_inventory.csv', records)
    log('discovery_complete', discovered=len(discovered), selected=len(selected))

    def bind(record, key, target, expected, critical=True, referenced_copy=None):
        add(target, 'manifest_bound_asset')
        actual = hashes.get(target, '')
        status = 'PASS' if actual == expected else ('MISSING' if not actual else 'HASH_MISMATCH')
        bindings.append({'record_path': str(record), 'record_key': key, 'target_path': str(target),
                         'expected_sha256': expected, 'actual_sha256': actual,
                         'status': status, 'critical_to_G0': critical,
                         'referenced_stage_copy': str(referenced_copy) if referenced_copy else '',
                         'stage_copy_status': 'NOT_COPIED_IN_PARTIAL_STAGE_ARCHIVE' if referenced_copy else 'DIRECT_PATH',
                         'resolution': 'same_manifest_relative_path_in_original_v1.1_AND_exact_hash' if referenced_copy else 'direct'})
        if status != 'PASS':
            conflict(f'BIND{len(bindings):04d}', status, [record, target], f'expected={expected};actual={actual}',
                     '禁止将不匹配文件作为该记录的已绑定版本；具体来源待确认', status)
    # Original training asset manifest and formal freeze manifests, including historical versions.
    manifest_specs = [(train / 'artifact_manifest.json', train, True)]
    for base in (old, formal, day2 / 'frozen_inputs', day3 / 'frozen_inputs', day4 / 'frozen_inputs'):
        manifest_specs.append((base / 'formal_code_manifest.json', base, base != old))
    for record, base, critical in manifest_specs:
        if not record.is_file():
            missing.append({'item': str(record), 'status': 'MISSING', 'blocked_conclusion': '该版本哈希绑定', 'critical': critical})
            continue
        obj = load(record)
        for relative, value in obj.get('files', {}).items():
            expected = value.get('sha256') if isinstance(value, dict) else value
            if re.fullmatch('[0-9a-f]{64}', str(expected)):
                target = base / relative
                # A copied complete manifest still refers to the original package root.
                # Keep an explicit record of missing partial-stage copies, then resolve
                # only to the original frozen package with exactly the expected hash.
                original_target = formal / relative
                if not target.is_file() and base in (day2 / 'frozen_inputs', day3 / 'frozen_inputs', day4 / 'frozen_inputs') and original_target.is_file() and sha(original_target) == expected:
                    missing.append({'item': str(target), 'status': 'NOT_COPIED_STAGE_ARCHIVE_RESOLVED_BY_HASH',
                                    'blocked_conclusion': '不能声称该阶段目录自包含；完整原冻结版本对应文件已找到并逐字节哈希一致：' + str(original_target), 'critical': False})
                    bind(record, f'files.{relative}', original_target, expected, critical, referenced_copy=target)
                else:
                    bind(record, f'files.{relative}', target, expected, critical)
        for value in obj.get('records', []):
            target = base / value.get('frozen_path', value.get('path', ''))
            expected = value.get('sha256', value.get('frozen_sha256'))
            if expected:
                bind(record, 'records', target, expected, critical)
    combined = load(train / 'combined_training_manifest.json')
    relocation = []
    for key, item in {**combined['source_files'], 'critical_links': combined['critical_links']}.items():
        historical = item['path']
        marker = 'sci-jcr2区交付'
        target = home / historical.split(marker, 1)[1].lstrip('\\/')
        bind(train / 'combined_training_manifest.json', key, target, item['sha256'])
        relocation.append({'role': key, 'historical_path': historical, 'local_path': str(target),
                           'resolution': 'relocated_by_archive_suffix_AND_sha256', 'sha256': hashes.get(target, '')})
    bind(train / 'combined_training_manifest.json', 'preprocessor_sha256', train / 'preprocessor_v2.json', combined['preprocessor_sha256'])
    generation_record = day2 / '02_candidate_pool/generation_freeze_record.json'
    generation = load(generation_record)
    # Explicit formal execution link: generator output -> original online run inputs.
    cfg = load(day3 / 'day3_run_config.json')
    for key, target in [('candidate_pool_sha256', day2 / '02_candidate_pool/candidate_pool.csv.gz'),
                        ('screened_candidates_sha256', day2 / '04_structural_screening/screened_candidates.csv')]:
        bind(day3 / 'day3_run_config.json', key, target, cfg[key])
    for key in ('full_method_entrypoint', 'controls_entrypoint', 'reference_logic', 'interface'):
        target = home / cfg[key].split('sci-jcr2区交付', 1)[1].lstrip('\\/')
        relocation.append({'role': key, 'historical_path': cfg[key], 'local_path': str(target),
                           'resolution': 'relocated_path; source_hash_checked_against_v1.1_manifest', 'sha256': hashes.get(target, '')})
    # Bind original DAY2 actual scripts, not the older copied scaffold.
    for rel, expected in load(day2 / 'artifact_manifest.json').get('files', {}).items():
        h = expected.get('sha256') if isinstance(expected, dict) else expected
        if rel.endswith('.py') and isinstance(h, str):
            bind(day2 / 'artifact_manifest.json', rel, day2 / rel, h)
    for base in (day3, day4):
        record = base / 'artifact_manifest.json'
        file_items = load(record).get('files', {})
        if isinstance(file_items, list):
            file_items = {v['path']: v for v in file_items}
        for rel, value in file_items.items():
            h = value.get('sha256') if isinstance(value, dict) else value
            if rel.endswith('.py') and isinstance(h, str):
                bind(record, rel, base / rel, h)
    gen_script = day2 / '02_candidate_pool/scripts/generate_candidate_pool.py'
    for key, value in generation.items():
        if 'script' in key and 'sha256' in key and isinstance(value, str):
            bind(generation_record, key, gen_script, value)
    surrogate_binding = day2 / 'frozen_inputs/v2_surrogate_manifest.json'
    for rel, value in load(surrogate_binding).get('files', {}).items():
        expected = value.get('sha256') if isinstance(value, dict) else value
        bind(surrogate_binding, rel, train / rel, expected)
    table(audit / 'relocated_paths.csv', relocation)

    # Read-only document inventory: text and field codes are kept separately.
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
          'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math'}
    docs, fields, document_texts = [], [], {}
    extract = audit / 'extracted_documents'
    extract.mkdir(exist_ok=True)
    doc_paths = [p for p in selected if p.suffix.lower() == '.docx']
    for p in sorted(doc_paths):
        try:
            with zipfile.ZipFile(p) as z:
                xml = etree.fromstring(z.read('word/document.xml'))
                paras = [''.join(el.xpath('.//w:t/text()', namespaces=ns)) for el in xml.xpath('//w:p', namespaces=ns)]
                text = '\n'.join(f'P{i:04d}\t{line}' for i, line in enumerate(paras, 1))
                document_texts[p] = text
                label = hashes[p][:16] + '_' + p.stem
                txt = extract / (label + '.txt')
                txt.write_text(text, encoding='utf-8')
                codes = xml.xpath('//w:instrText/text()', namespaces=ns)
                simple = xml.xpath('//w:fldSimple/@w:instr', namespaces=ns)
                for i, value in enumerate(codes + simple, 1):
                    fields.append({'path': str(p), 'field_index': i, 'field_instruction': value,
                                   'category': 'CITATION_KEEP' if 'ZOTERO' in value.upper() else 'EQUATION_OR_OTHER_REVIEW_ONLY'})
                docs.append({'path': str(p), 'sha256': hashes[p], 'paragraphs': len(paras), 'instrText_nodes': len(codes),
                             'fldSimple_nodes': len(simple), 'omml_math_nodes': len(xml.xpath('//m:oMath', namespaces=ns)),
                             'embedded_objects': sum(n.startswith('word/embeddings/') for n in z.namelist()),
                             'text_sha256': hashlib.sha256(text.encode()).hexdigest(), 'extracted_text': str(txt),
                             'visual_status': 'NOT_RUN_G3_REQUIRED'})
        except Exception as e:
            docs.append({'path': str(p), 'error': repr(e), 'visual_status': 'UNREADABLE'})
    table(audit / 'document_inventory.csv', docs)
    table(audit / 'word_field_inventory_readonly.csv', fields)
    reader = PdfReader(str(reviewer))
    pdf_text = '\n'.join(f'\n[PDF_PAGE {i}]\n{page.extract_text() or ""}' for i, page in enumerate(reader.pages, 1))
    (extract / 'Reviewer1_full_report_raw.txt').write_text(pdf_text, encoding='utf-8')
    match = re.search(r'4\.7\s+Several implementation.*?(?=\n5\s+Thematic|\Z)', pdf_text, re.S)
    raw_comment = match.group(0) if match else ''
    (extract / 'Reviewer1_4_7_raw.txt').write_text(raw_comment, encoding='utf-8')
    normalized = raw_comment.translate(str.maketrans({'\x1c': 'fi', '\x1b': 'ff', '\x1e': 'ffi', '\x1d': 'fl'}))
    (extract / 'Reviewer1_4_7_readable.txt').write_text(normalized, encoding='utf-8')
    check('original_review_4_7_extracted', bool(match) and 'early stopping' in normalized, '原始PDF及只读文字提取；未混入第5节主题意见')

    # CSV schema only; no training-label aggregation or epoch-optimum reconstruction in G0.
    schemas, member_rows = [], []
    training_csvs = [p for p in selected if (p.is_relative_to(train) or p.is_relative_to(week1) or p.is_relative_to(expansion))
                     and (p.name.endswith('.csv') or p.name.endswith('.csv.gz'))]
    for p in sorted(training_csvs):
        opener = gzip.open if p.name.endswith('.gz') else open
        with opener(p, 'rt', encoding='utf-8-sig', newline='') as f:
            columns = next(csv.reader(f), [])
        schemas.append({'path': str(p), 'columns': columns, 'scope': 'HEADER_ONLY; G1 label/epoch aggregation NOT_RUN'})
    bootstrap = load(train / 'bootstrap_scenarios_v2.json')
    for member in bootstrap['members']:
        mid = member['member_id']
        history = train / f'histories/{mid}_training_history.csv'
        summary = train / f'summaries/{mid}_summary.json'
        model = train / f'models/{mid}.pt'
        obj = load(summary)
        summary_hash = obj.get('model_hash_sha256', obj.get('model_sha256', obj.get('checkpoint_sha256', '')))
        member_rows.append({'member_id': mid, 'weight_path': str(model), 'weight_sha256': hashes.get(model),
                            'summary_path': str(summary), 'history_path': str(history),
                            'history_present': history.is_file(), 'summary_weight_hash': summary_hash,
                            'weight_hash_matches_summary': summary_hash == hashes.get(model),
                            'declared_best_epoch': obj.get('best_epoch'), 'declared_completed_epochs': obj.get('epochs_completed'),
                            'declared_oob_count': member.get('oob_scenario_count'),
                            'epoch_reconstruction': 'NOT_RUN_G1_REQUIRED', 'checkpoint_deserialization': 'NOT_RUN'})
    table(audit / 'csv_schema_inventory.csv', schemas)
    table(audit / 'member_asset_inventory.csv', member_rows)
    history_schemas = [r for r in schemas if '/histories/' in Path(r['path']).as_posix()]
    check('member_history_monitor_columns_present', len(history_schemas) == 10 and all('oob_weighted_huber' in r['columns'] and 'epoch' in r['columns'] for r in history_schemas),
          '仅核对10份history字段，未重算最优epoch')
    dump(audit / 'training_manifest_declared_anchors_NOT_reaggregated.json', {
        'status': 'DECLARED_METADATA_ONLY_NOT_G1_VERIFIED', 'source': str(train / 'combined_training_manifest.json'),
        'metadata': combined, 'member_epoch_audit': 'NOT_RUN', 'state_masks_and_severity_reaggregation': 'NOT_RUN'})

    # Static AST inventory. Parsing functions is not executing any project code.
    ast_cache, parse_errors, symbols, calls = {}, [], [], []
    bad_names = {'evaluate_proxy_sequence', 'evaluate_ue_sequence'}
    bad_refs = []
    def parse_file(p):
        if p not in ast_cache:
            source = read(p)
            ast_cache[p] = (source, ast.parse(source, filename=str(p)))
        return ast_cache[p]
    def walk_scope(node, scope='module'):
        for child in ast.iter_child_nodes(node):
            child_scope = scope
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                child_scope = (scope + '.' if scope != 'module' else '') + child.name
            yield child, child_scope
            yield from walk_scope(child, child_scope)
    for p in sorted(x for x in selected if x.suffix.lower() == '.py'):
        try:
            source, tree = parse_file(p)
            for node, scope in walk_scope(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append({'path': str(p), 'symbol': scope, 'line': node.lineno, 'end_line': node.end_lineno,
                                    'ast_sha256': hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()})
                if isinstance(node, ast.Call):
                    name = ast.unparse(node.func)
                    if p.is_relative_to(formal) and 'smoke_test' not in p.parts:
                        calls.append({'path': str(p), 'caller': scope, 'line': node.lineno, 'callee': name})
                    if (isinstance(node.func, ast.Attribute) and node.func.attr in bad_names) or (isinstance(node.func, ast.Name) and node.func.id in bad_names):
                        bad_refs.append({'path': str(p), 'caller': scope, 'line': node.lineno, 'callee': name,
                                         'context': 'FORMAL_ENTRY_SET' if p.parent == formal / 'formal_code' else 'OTHER_VERSION_OR_HISTORICAL_TEST'})
                # Dynamic lookup of the legacy names cannot be silently assumed absent.
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('getattr', 'eval', 'exec'):
                    if any(isinstance(x, ast.Constant) and isinstance(x.value, str) and any(b in x.value for b in bad_names) for x in ast.walk(node)):
                        bad_refs.append({'path': str(p), 'caller': scope, 'line': node.lineno,
                                         'callee': ast.unparse(node), 'context': 'DYNAMIC_LEGACY_LOOKUP_REQUIRES_REVIEW'})
        except (SyntaxError, UnicodeError, ValueError) as e:
            parse_errors.append({'path': str(p), 'error': repr(e)})
    table(audit / 'code_symbol_versions.csv', symbols)
    table(audit / 'formal_static_call_inventory.csv', calls)
    table(audit / 'legacy_11_state_call_sites.csv', bad_refs, ['path', 'caller', 'line', 'callee', 'context'])
    table(audit / 'code_parse_exceptions.csv', parse_errors, ['path', 'error'])

    def function(p, qualified):
        source, tree = parse_file(p)
        for node, scope in walk_scope(tree):
            if isinstance(node, ast.FunctionDef) and scope == qualified:
                return node, '\n'.join(source.splitlines()[node.lineno-1:node.end_lineno])
        raise ValueError(f'MISSING symbol {qualified}: {p}')
    excerpts = audit / 'source_excerpts'
    excerpts.mkdir(exist_ok=True)
    evidences = []
    def excerpt(label, p, symbol):
        node, text = function(p, symbol)
        dest = excerpts / (label + '.txt')
        numbered = '\n'.join(f'{n:05d}  {line}' for n, line in enumerate(text.splitlines(), node.lineno))
        dest.write_text(f'SOURCE: {p}\nSHA256: {hashes[p]}\nSYMBOL: {symbol}\n' + numbered + '\n', encoding='utf-8')
        evidences.append({'label': label, 'path': str(p), 'symbol': symbol, 'line': node.lineno,
                          'end_line': node.end_lineno, 'sha256': hashes[p], 'excerpt': str(dest)})
        return text
    ts = train / 'scripts/run_v2_day2_huber_ensemble.py'
    training = excerpt('training_train_member', ts, 'train_member')
    training_main = excerpt('training_main', ts, 'main')
    boot_code = excerpt('training_bootstrap_plan', ts, 'make_bootstrap_plan')
    gp = formal / 'formal_code/generate_candidate_pool.py'
    objective = excerpt('formal_proxy_objective', gp, 'ProxyObjective.evaluate')
    search = formal / 'formal_code/run_full_method_live_ue.py'
    masks = excerpt('formal_search_masks', search, 'BudgetedSearch.masks_for_sequence')
    evaluation = excerpt('formal_search_objective', search, 'BudgetedSearch.evaluate_sequence')
    evaluate_mask = excerpt('formal_state_api_call', search, 'BudgetedSearch.evaluate_mask')
    interface = formal / 'formal_code/interfaces_week3.py'
    legacy_proxy = excerpt('legacy_11_proxy_helper', interface, 'SurrogateV2.evaluate_proxy_sequence')
    legacy_ue = excerpt('legacy_11_ue_helper', interface, 'UEInterface.evaluate_ue_sequence')
    dp = formal / 'formal_code/run_exact_reference_after_method_freeze.py'
    dp_code = excerpt('formal_DP_source_inventory_ONLY', dp, 'exact_dp')
    table(audit / 'high_risk_source_locations.csv', evidences)
    early_ok = all(x in training for x in ['member["oob_scenario_ids"]', 'X_all[oob_mask]', 'y_all[oob_mask]',
                                           'weighted_huber_torch(model(X_oob_tensor)', 'oob_loss < best_loss - MIN_DELTA',
                                           'scheduler.step(oob_loss)', 'model.load_state_dict(best_state)', 'torch.save(checkpoint'])
    # Accept only an explicit order in the archived main body; no claim of dynamic runtime tracing.
    freeze_order = (training_main.find('summary = train_member(') < training_main.find('for split in ("calibration", "internal_id", "internal_severe")')
                    and 'split_frames[split] = load_raw(DATA_FILES[split])' in training_main)
    proxy10 = 'masks = [0]' in objective and 'sequence[:9]' in objective and 'self.member_loss[masks].mean(axis=0)' in objective
    ue10 = 'masks = [0]' in masks and 'sequence[:9]' in masks and 'self.masks_for_sequence(sequence)' in evaluation and 'np.mean(stage_losses)' in evaluation
    actual_helpers = [r for r in bad_refs if r['context'] == 'FORMAL_ENTRY_SET']
    wrapper = formal / 'formal_code/run_final_full_method_live_ue.py'
    wrapper_ok = 'from run_full_method_live_ue import main' in read(wrapper)
    # AST-core equivalence: actual DAY2 generator and actual DAY3 frozen copy vs bound v1.1.
    def core_equal(p, q, symbol):
        n1, _ = function(p, symbol)
        n2, _ = function(q, symbol)
        return ast.dump(n1, include_attributes=False) == ast.dump(n2, include_attributes=False)
    generator_match = hashes.get(gen_script) == hashes.get(gp)
    frozen_search = day3 / 'frozen_inputs/formal_code/run_full_method_live_ue.py'
    frozen_core_ok = all(core_equal(search, frozen_search, s) for s in ('BudgetedSearch.masks_for_sequence', 'BudgetedSearch.evaluate_sequence', 'BudgetedSearch.evaluate_mask'))
    check('early_stopping_OOB_static_mechanism', early_ok, '成员专属OOB加权Huber、MIN_DELTA、scheduler和checkpoint静态代码；G1逐epoch检查尚未执行')
    check('calibration_read_after_all_members_static_order', freeze_order, '主函数训练循环完成后才读取calibration/internal；静态路径与封存资产支持，非新运行追踪')
    check('formal_candidate_10_weighted_stages', proxy10 and generator_match, 'R0及前9次恢复共10状态；实际DAY2生成器SHA等于正式v1.1')
    check('formal_UE_search_10_weighted_stages', ue10 and wrapper_ok and frozen_core_ok, 'wrapper->BudgetedSearch.masks_for_sequence/evaluate_sequence->run_ue；未执行搜索')
    check('legacy_11_helpers_not_called_by_formal_entry_set', not actual_helpers, '逐AST调用点清单；旧11状态接口定义存在，正式代码入口集合无调用点')
    check('legacy_11_helpers_identified', 'range(11)' in legacy_proxy and 'range(11)' in legacy_ue, '记录真实接口语义差异，不掩盖其存在')
    check('all_10_members_assets_present', len(member_rows) == 10 and all(r['history_present'] and r['weight_hash_matches_summary'] for r in member_rows), '权重SHA对摘要；history可读，未重算best epoch')

    # Record code relationships and all same-name/different-content versions of critical sources.
    critical_names = ['run_v2_day2_huber_ensemble.py', 'generate_recovery_dataset.py', 'run_v2_day1_training_expansion.py',
                      'generate_candidate_pool.py', 'screen_primary.py', 'screen_structural_reserve.py',
                      'run_full_method_live_ue.py', 'run_final_full_method_live_ue.py', 'interfaces_week3.py',
                      'run_exact_reference_after_method_freeze.py']
    version_notes = {
        'run_v2_day2_huber_ensemble.py': '原训练、隐藏failed副本、当前public共3版；failed预处理to_numpy是否copy的实现不同，public环境/数据输出根目录改写。train_member及bootstrap函数AST另行对照，未以public替换原训练证据。',
        'generate_candidate_pool.py': '旧版固定SEED=20260805031并从既有v1候选表取GA/local bases及保留候选；实际v1.1采用DEFAULT_SEED_BASE=2026080702/命令行参数，并从本轮registry按代理目标取bases。因此不仅是路径差别，不能互换候选生成流程。ProxyObjective.evaluate的10阶段核心另行AST对照。',
        'screen_primary.py': '旧版固定历史输入/SEED=2026080504；实际v1.1提供输入/输出/情景数/seed-base参数，默认seed base2026080703。不得用旧版随机流替代正式v1.1筛选；渠道/排序逐位重建留G2。',
        'screen_structural_reserve.py': '旧版固定历史目录；v1.1改命令行输入/输出、情景数与freeze检查。完整diff保留；未在G0声称Reserve选择结果逐位等价。',
        'run_full_method_live_ue.py': 'v1.1增加显式cache路径/namespace、依赖参数、prewarmed smoke隔离、physical cache记账和新metadata参数。原正式Day3配置禁止prewarmed cache。masks/evaluate_sequence核心函数AST相同，不推定整份程序完全等价。',
        'run_exact_reference_after_method_freeze.py': '旧版直接worker/solver与固定历史输入；v1.1改状态级interface、方法输出freeze校验和命令行。exact_dp函数AST并非完全相同：v1.1新增1024子集完整性检查；目标递推/零权重末态的数学与数值验收仍留G2。实际Day4归档源码哈希绑定v1.1。',
    }
    versions = []
    for name in critical_names:
        groups = defaultdict(list)
        for p in selected:
            if p.name == name:
                groups[hashes[p]].append(p)
        for h, paths in sorted(groups.items()):
            for p in paths:
                versions.append({'filename': name, 'sha256': h, 'path': str(p), 'distinct_versions': len(groups),
                                 'role': selected[p]['evidence_priority'],
                                 'same_bytes_as_actual_v1_1': h == hashes.get(formal / 'formal_code' / name, ''),
                                 'same_bytes_as_original_training': h == hashes.get(train / 'scripts' / name, '')})
        if len(groups) > 1:
            conflict('CODE_' + name, 'SAME_NAME_DIFFERENT_HASH', [p for paths in groups.values() for p in paths],
                     f'{len(groups)}个字节版本；' + version_notes.get(name, '') + ' 完整哈希和每个路径见code_version_relations.csv。',
                     '正式用途以原执行配置及冻结manifest绑定；历史/当前副本保留，不默默合并')
    table(audit / 'code_version_relations.csv', versions)
    semantic_rows = []
    compared_symbols = {'run_v2_day2_huber_ensemble.py': ['train_member', 'make_bootstrap_plan'],
                        'generate_candidate_pool.py': ['ProxyObjective.evaluate'],
                        'run_full_method_live_ue.py': ['BudgetedSearch.masks_for_sequence', 'BudgetedSearch.evaluate_sequence'],
                        'run_exact_reference_after_method_freeze.py': ['exact_dp']}
    for name, names in compared_symbols.items():
        base = ts if name == ts.name else formal / 'formal_code' / name
        for p in sorted(p for p in selected if p.name == name):
            for symbol in names:
                try:
                    same = core_equal(base, p, symbol)
                    semantic_rows.append({'baseline': str(base), 'compared_path': str(p), 'symbol': symbol,
                                          'AST_exact_equal': same, 'scope': 'same_AST_only; no dynamic or numerical execution'})
                except ValueError as e:
                    semantic_rows.append({'baseline': str(base), 'compared_path': str(p), 'symbol': symbol,
                                          'AST_exact_equal': 'MISSING_SYMBOL', 'scope': str(e)})
    table(audit / 'high_risk_function_AST_comparisons.csv', semantic_rows)
    partial_copies = [r for r in bindings if r.get('referenced_stage_copy')]
    if partial_copies:
        conflict('PARTIAL_STAGE_ARCHIVES', 'FULL_MANIFEST_IN_PARTIAL_COPY', [day2 / 'frozen_inputs', day3 / 'frozen_inputs', day4 / 'frozen_inputs', formal],
                 f'{len(partial_copies)}项在阶段frozen_inputs中没有单独复制，但完整v1.1原冻结目录存在且SHA与manifest完全相同。',
                 '缺失位置逐项保留在missing_files.csv；绑定表同时保留阶段拟引用位置和实际解析位置，不宣称阶段目录完全自包含。',
                 'RESOLVED_BY_ORIGINAL_FROZEN_HASH')
    diffs_dir = audit / 'diffs'
    diffs_dir.mkdir(exist_ok=True)
    for name in critical_names:
        base = ts if name == ts.name else formal / 'formal_code' / name
        if not base.is_file():
            continue
        distinct = {}
        for p in selected:
            if p.name == name and hashes[p] != hashes[base]:
                distinct.setdefault(hashes[p], p)
        for h, p in distinct.items():
            diff = ''.join(difflib.unified_diff(read(base).splitlines(True), read(p).splitlines(True), fromfile=str(base), tofile=str(p)))
            (diffs_dir / f'{name}_{h[:12]}.diff').write_text(diff, encoding='utf-8')
    if hashes.get(manuscript) != hashes.get(manuscript14):
        conflict('DOC_ORIGINAL_IDENTITY', 'SUBMISSION_WORD_IDENTITY_OPEN', [manuscript, manuscript14],
                 'Manuscript(1)与Manuscript (14)二进制/域结构不同；可见文本差异含作者前置信息及Data Availability（待填链接 vs 已列GitHub/Zenodo）；导师分享投稿初稿副本与前者相同。',
                 '并列保留两份；本批不指定后续Word修订主文件。最终投稿系统上传回执/文件哈希未发现，不能确认哪份是系统实际接收件。', 'OPEN_VERSION_IDENTITY')
        text_diff = ''.join(difflib.unified_diff(document_texts.get(manuscript, '').splitlines(True), document_texts.get(manuscript14, '').splitlines(True), fromfile=str(manuscript), tofile=str(manuscript14)))
        (diffs_dir / 'original_word_visible_text.diff').write_text(text_diff, encoding='utf-8')
    conflict('LEGACY11_SEMANTIC', 'OLD_API_VS_FORMAL_OBJECTIVE', [interface, gp, search],
             '旧两个evaluate_*_sequence接口11状态均值；正式ProxyObjective/BudgetedSearch采用10个有权重阶段。',
             '实际DAY2生成器、v1.1入口、DAY3冻结核心及输入池哈希串联；正式入口集合无旧接口调用。全部1024状态预测/DP含终态记录不等于终态参与均值。',
             'CRITICAL_MISMATCH' if actual_helpers else 'RESOLVED_FORMAL_PATH_SEPARATED')

    # Local Git identity only; does not fetch or modify a repository.
    git_rows = []
    for repo in sorted(project.glob('urban-flood-road-reopening-reproducibility*')):
        if not repo.is_dir():
            continue
        git = repo / '.git'
        if git.is_dir():
            head = read(git / 'HEAD').strip()
            commit = head
            if head.startswith('ref: '):
                ref = head[5:]
                commit = read(git / ref).strip() if (git / ref).is_file() else ''
                if not commit and (git / 'packed-refs').is_file():
                    commit = next((line.split()[0] for line in read(git / 'packed-refs').splitlines() if line.endswith(' ' + ref)), '')
            for gp_meta in (git / 'HEAD', git / 'config', git / 'packed-refs'):
                if gp_meta.is_file():
                    add(gp_meta, 'local_git_identity_metadata')
            git_rows.append({'repository': str(repo), 'HEAD': head, 'local_commit': commit, 'remote_verified': False,
                             'note': '仅本机Git标识；不保证工作树与commit无差异；逐文件SHA见来源清单'})
        else:
            git_rows.append({'repository': str(repo), 'HEAD': '', 'local_commit': '', 'remote_verified': False, 'note': 'MISSING local .git'})
    table(audit / 'git_identity.csv', git_rows)

    # Readiness includes code/data accessibility, not G1/G2 mathematical or numerical acceptance.
    required = [('原投稿候选Word_A', manuscript), ('原投稿候选Word_B', manuscript14), ('Supplement', supplement),
                ('Reviewer1PDF', reviewer), ('训练源码', ts), ('训练bootstrap', train / 'bootstrap_scenarios_v2.json'),
                ('训练摘要', train / 'ensemble_training_summary.csv'), ('首批状态抽样源码', home / '第一周工作/week1_recovery_dataset/scripts/generate_recovery_dataset.py'),
                ('扩展状态抽样源码', expansion / 'run_v2_day1_training_expansion.py'), ('候选池实际生成器', gen_script),
                ('Primary正式源码', formal / 'formal_code/screen_primary.py'), ('Reserve正式源码', formal / 'formal_code/screen_structural_reserve.py'),
                ('正式在线入口', wrapper), ('正式搜索核心', search), ('正式DP', dp)]
    for label, p in required:
        ok = p.is_file() and p in selected
        check('required_' + label, ok, str(p))
        if not ok:
            missing.append({'item': label, 'status': 'MISSING', 'blocked_conclusion': str(p), 'critical': True})
    missing.append({'item': '投稿系统实际接收Word的上传回执/校验哈希', 'status': 'MISSING_PROVENANCE',
                    'blocked_conclusion': '无法最终认定Manuscript(1)或Manuscript (14)哪个是系统实际接收件；阻止后续主Word选择，非训练/候选代码证据缺失', 'critical': False})
    missing.append({'item': '原训练进程操作系统级文件访问轨迹/原始控制台stdout（独立于histories）', 'status': 'NOT_LOCATED',
                    'blocked_conclusion': 'G0可确认封存源码读入顺序及资产绑定；不能把静态证据表述为新取得的系统调用运行轨迹', 'critical': False})
    for token, label in [('4.1专项', '4.1'), ('reviewer_4_2', '4.2'), ('reviewer_4_3', '4.3'),
                         ('revision_4_4', '4.4'), ('revision_4_5', '4.5'), ('revision_4_6', '4.6')]:
        paths = [p for p in selected if token in str(p)]
        check('prior_revision_' + label, bool(paths), f'{len(paths)}份已选证据；不重算或修改既有结论')
    critical_binding_bad = [r for r in bindings if r['critical_to_G0'] and r['status'] != 'PASS']
    check('critical_manifest_hash_bindings', not critical_binding_bad, f'{len(bindings)}条绑定；关键不匹配{len(critical_binding_bad)}条')
    formal_parse_errors = [x for x in parse_errors if str(formal / 'formal_code') in x['path'] or x['path'] == str(ts)]
    check('actual_formal_training_AST_readable', not formal_parse_errors, '其他历史脚本解析问题单列，不替换正式源码')

    def cover(topic, paths, locations, status, conclusion, deferred):
        coverage.append({'reviewer_point': topic, 'source_paths': [str(p) for p in paths], 'locations': locations,
                         'G0_status': status, 'evidence_and_limit': conclusion, 'later_gate_NOT_RUN': deferred})
    cover('训练恢复状态抽样（首批/扩展分开）', [required[7][1], required[8][1], train / 'combined_training_manifest.json'],
          '代码已索引，CSV字段已盘点', 'SOURCE_LOCATED', '两个来源分别找到；未把首批规则外推至全部3178条', 'G1配额/状态合法性/生成规则核验')
    cover('训练池强度构成', [week1 / 'recovery_states_train.csv', expansion / 'recovery/v2_new_training_states.csv.gz', train / 'combined_training_manifest.json'],
          'manifest.severity_scenarios/severity_rows', 'DECLARED_ONLY', '50/55/15情景及236/2042/900状态仅为已归档声明，本批不重聚合', 'G1直接聚合实际标签')
    cover('early stopping来源及设置', [ts, train / 'bootstrap_scenarios_v2.json', train / 'ensemble_training_config_v2.json'],
          'train_member; main;10成员histories/summary/model SHA', 'STATIC_PATH_VERIFIED' if early_ok and freeze_order else 'FAIL',
          '成员专属scenario-bootstrap OOB加权Huber；patience100、MIN_DELTA1e-7；校准/内部数据在全成员checkpoint完成后读入；epoch验收待G1', 'G1逐epoch和split防火墙')
    cover('正式候选目标/旧11状态接口', [generation_record, gp, interface, wrapper, search, day3 / 'day3_run_config.json'],
          'source_excerpts + formal_static_call_inventory.csv + manifest_binding_checks.csv',
          'CRITICAL_MISMATCH' if actual_helpers else 'STATIC_FORMAL_PATH_VERIFIED',
          '10个有权重阶段；旧11状态helper未被正式入口集合调用；不是动态重跑或全部历史路径证明', 'G2冻结池目标/disagreement数值反算')
    cover('sequence-level disagreement数学定义', [gp, formal / 'formal_code/screen_primary.py'],
          'ProxyObjective.evaluate;候选member目标.std(ddof=1)', 'SOURCE_LOCATED', '源码定义已定位；本批不读取权重作预测或反算候选', 'G2公式/池值比对')
    cover('Reserve及queue quantile优先级', [formal / 'formal_code/screen_structural_reserve.py', search],
          'QUANTILE_PRIORITY;分组筛选源文件', 'SOURCE_LOCATED', '正式版本已绑定，未重建队列', 'G2分组/取整/字典序逐位核对')
    cover('subset-DP及terminal权重', [dp, day4 / 'day4_execution_record.json'],
          'exact_dp; stage_weight=0.1 if stage<10 else0', 'SOURCE_LOCATED', '11行阶段诊断记录中末态权重0；尚未执行数学测试；exact仅相对给定数值状态表', 'G2证明/穷举与原表复核')
    cover('Word公式编号/域/Eq8/Table1', [manuscript, manuscript14, supplement],
          'document_inventory.csv;word_field_inventory_readonly.csv', 'READONLY_XML_INVENTORIED',
          'MathType/Zotero域分开保存；未渲染、删除域、修改公式或指定主Word', 'G3 Word导出PDF与目视验收')
    cover('既有4.1—4.6结论边界', [root / '审稿人1返稿信', root / 'revision_4_6_tail_inference'],
          'source_manifest.csv中原回应/报告/validation/冻结协议', 'SOURCE_LOCATED', '只读索引，不重算既有数值，不撰写4.7 Response', 'G4统一回复需后续授权')

    # Rehash every selected source after the audit, verifying no source bytes changed.
    unchanged_rows = []
    for p in sorted(selected):
        after = sha(p)
        unchanged_rows.append({'path': str(p), 'sha256_before': hashes[p], 'sha256_after': after, 'unchanged': hashes[p] == after})
    check('all_selected_sources_unchanged', all(r['unchanged'] for r in unchanged_rows), f'{len(unchanged_rows)}个来源前后逐文件重哈希')
    check('G0_only_no_later_stage_outputs', not any((out / x).exists() for x in ['01_training', '02_math', '03_doc', '04_response']),
          '无G1/G2/G3/G4目录；未加载权重、调用原模块、训练、UE、DP或优化')
    table(audit / 'source_immutability_checks.csv', unchanged_rows)
    for i, p in enumerate(sorted(selected), 1):
        selected[p]['source_id'] = f'SRC{i:05d}'
    table(audit / 'source_manifest.csv', list(selected.values()))
    table(audit / 'manifest_binding_checks.csv', bindings)
    table(audit / 'version_conflicts.csv', conflicts)
    table(audit / 'missing_files.csv', missing)
    table(audit / 'evidence_coverage.csv', coverage)
    table(audit / 'automatic_acceptance_checks.csv', checks)
    failed = [x for x in checks if x['status'] == 'FAIL']
    critical_mismatch = bool(actual_helpers)
    validation = {'stage': 'G0', 'status': 'CRITICAL_MISMATCH' if critical_mismatch else ('FAIL' if failed else 'PASS_WITH_OPEN_PROVENANCE_ITEMS'),
                  'G0_evidence_readiness_pass': not failed and not critical_mismatch,
                  'later_gates_pass': False, 'source_count': len(selected), 'discovered_count': len(discovered),
                  'manifest_bindings': len(bindings), 'critical_binding_failures': critical_binding_bad,
                  'checks_total': len(checks), 'checks_passed': len(checks)-len(failed), 'failed_checks': failed,
                  'formal_legacy_helper_call_sites': actual_helpers, 'checks': checks,
                  'operations': {'project_module_imports': 0, 'checkpoint_loads': 0, 'UE_solves': 0, 'new_scenarios': 0,
                                 'model_training': 0, 'formal_optimization': 0, 'prediction_replay': 0, 'DP_execution': 0,
                                 'training_severity_reaggregation': 0, 'epoch_optimum_reconstruction': 0, 'Word_edits': 0},
                  'operations_scope': '本审计程序仅有读取、AST/XML/PDF解析和向独立输出目录写审计文件的路径；计数非系统级历史进程监测',
                  'must_stop_after_G0': True, 'elapsed_seconds': round(time.perf_counter()-started, 3),
                  'audit_script': str(Path(__file__).resolve()), 'audit_script_sha256': sha(Path(__file__)),
                  'python': sys.version, 'protocol_path': str(plan), 'protocol_sha256': hashes.get(plan)}
    dump(audit / 'g0_validation.json', validation)

    # Clear Chinese acceptance report, with bounded claims and open conflicts up front.
    def ev(label):
        row = next(r for r in evidences if r['label'] == label)
        return link(row['path'], row['symbol'], row['line'])
    doc_rows = {r['path']: r for r in docs}
    report = [
        '# Reviewer 1 第4.7条：第一批 S0/G0 中文审计报告', '',
        f'生成时间：{datetime.now().astimezone().isoformat()}。状态：**{validation["status"]}**。', '',
        f'自动检查 {len(checks)-len(failed)}/{len(checks)} 通过；流式SHA256冻结 {len(selected)} 份已选来源，原档前后重哈希核对。此状态仅指G0证据可用性，不代表G1—G4通过。', '',
        '## 1. 本批范围与证据优先级', '',
        '仅执行S0/G0。优先实际产生原稿结果的第四周执行记录、输入/输出哈希及绑定源码，再核对训练原资产与同版正式源码，随后对照原稿/Supplement、历史manifest，最后比较当前公开副本。未执行训练状态聚合、逐epoch早停重算、候选反预测、DP数学测试、Word修订或英文回复。', '',
        f'扫描根目录为 {project}（原Word、老家原档和公开副本在返稿目录之外，故扩大只读发现范围）；工作根目录仍为 {root}。使用rg发现{len(discovered)}个文件，按明确规则选择{len(selected)}个证据；不是整个E盘的全量哈希。', '',
        '依赖目录、缓存、Git对象和本次输出不纳入普通来源扫描；Git标识另读。大规模逐运行数值/UE表不是G0重算对象。完整发现清单保留选择理由。所有选中源文件均有SHA256、大小、实际路径、来源类型、证据级别。未创建压缩包。', '',
        '## 2. 高风险问题一：early stopping', '',
        f'原训练源码 {ev("training_train_member")} 将成员scenario bootstrap的 `oob_scenario_ids` 用于OOB mask，对OOB预测计算加权Huber；用 `oob_loss < best_loss - MIN_DELTA` 保存最佳checkpoint，学习率调度器也读取同一OOB loss。配置/源码给出 patience=100、MIN_DELTA=1e-7、上限1000 epochs，ReduceLROnPlateau(patience=25,factor=0.5,min_lr=1e-6)。', '',
        f'{ev("training_main")} 的10成员训练循环全部完成后，才通过 `load_raw(DATA_FILES[split])` 读取calibration/internal-ID/internal-severe用于冻结模型诊断。{ev("training_bootstrap_plan")}、bootstrap JSON、10份history、10份summary、10个权重及正式V2 surrogate manifest均已定位并作哈希交叉绑定。', '',
        '**G0判定：封存源码支持“成员专属scenario-bootstrap OOB早停，校准集冻结后诊断”，不是用calibration作早停。** 这是源码顺序和资产哈希证据，不冒充系统调用级训练访问轨迹。OOB属于训练池中的袋外开发监控，不能称为外部独立验证集。逐成员split防火墙、best epoch/min_delta/停止epoch重算必须留到G1。本批未反序列化任何.pt。', '',
        '训练manifest的120情景/3178状态、mild/moderate/severe的50/55/15情景及236/2042/900状态仅作为归档声明列出，**尚未直接聚合核实**。首批训练和201—260扩展的采样源码分别定位，规则不能互相外推。训练标签历史UE精度与4.2高精度复核分开，不能据此宣称全部训练标签已经以1e-9重求。', '',
        '## 3. 高风险问题二：10个有权重阶段与旧11状态接口', '',
        f'实际第四周候选池生成记录绑定的生成器，与正式v1.1的 generate_candidate_pool.py SHA256一致：`{hashes[gp]}`。{ev("formal_proxy_objective")} 从空集mask开始，只追加 `sequence[:9]` 的9个前缀，再对这10个成员状态loss作均值，故m=10时为R0—R9。', '',
        f'第四周Day3配置指定 `run_final_full_method_live_ue.py`；该wrapper导入同目录 `run_full_method_live_ue.main`。{ev("formal_search_masks")} 同样只构造10个mask；{ev("formal_search_objective")} 对其loss取均值，{ev("formal_state_api_call")} 调用的是状态级 `UEInterface.run_ue`。Day3冻结副本的这些核心函数AST与v1.1一致。', '',
        f'旧 {ev("legacy_11_proxy_helper")} 和 {ev("legacy_11_ue_helper")} 确有 `range(11)` 和11状态均值。已保存正式源码集合全部AST调用点及全盘发现的旧helper调用位置，**正式v1.1入口集合没有调用这两个helper**。加载interfaces模块不等于调用其序列均值helper。', '',
        '候选池本体和screened_candidates的SHA与Day3实际输入配置匹配，从执行配置、v1.1冻结manifest到实际生成器/池输入形成可追踪证据链。本批不重新运行预测/优化，也不宣称证明所有历史实验路径都未调用旧helper。4.1 source_snapshot单独列版本，不把它自动等同所有原档版本。', '',
        f'DP源码 {ev("formal_DP_source_inventory_ONLY")} 的阶段诊断可记录11行，但stage10权重为0，不能因 `range(11)` 直接判断目标为11状态均值。本批只定位源码，条件DP数值复算和证明在G2。', '',
        '## 4. 原稿与版本冲突', '',
        '|来源|SHA256|instrText节点数|', '|---|---|---|',
        f'|{link(manuscript)}|`{hashes.get(manuscript)}`|{doc_rows.get(str(manuscript),{}).get("instrText_nodes")}|',
        f'|{link(manuscript14)}|`{hashes.get(manuscript14)}`|{doc_rows.get(str(manuscript14),{}).get("instrText_nodes")}|',
        f'|{link(supplement)}|`{hashes.get(supplement)}`|{doc_rows.get(str(supplement),{}).get("instrText_nodes")}|', '',
        '两份原投稿候选Word不能视为同一个字节文件。导师分享中标注“投稿初稿”的副本可支持Manuscript(1)的归档身份，但缺少投稿系统上传回执/哈希，不能替作者最终决定系统实际接收件。两份均只读提取，保留可见文本diff和域清单；不指定后续修订主Word。', '',
        f'关键同名异版本关系见code_version_relations.csv；共{len(conflicts)}条冲突/版本提示见version_conflicts.csv。旧冻结、v1.1、pre-final-acceptance、第四周实际scripts、4.1快照、导师副本、当前public副本分别保留。对不同哈希生成逐版本diff，不能以当前副本替代原执行版本。', '',
        '两份Word的可见文本差异除作者前置信息外，还包括Data Availability：一份留待填公开链接，另一份已列GitHub/Zenodo。此处只记录文稿内容差别，没有联网确认公开存档或DOI。', '',
        f'阶段归档中有{len(partial_copies)}项没有单独复制整套manifest列出的所有脚本。程序保留未复制位置，并仅在完整v1.1目录找到相同相对路径且SHA完全一致时解析到原文件；未补写阶段归档。详见manifest_binding_checks.csv的referenced_stage_copy、target_path和resolution列。', '',
        '原训练脚本还存在隐藏failed目录副本，以及当前public路径适配副本。前者预处理to_numpy(copy=True)相关差异、后者环境/根目录配置改写均保留diff；不能视为同字节文件。高风险函数AST是否完全相同另列high_risk_function_AST_comparisons.csv，不据此推定整份程序完全等价。', '',
        '**需保留的实质版本差异：**旧候选生成器从先前v1候选表选GA/local bases并保留部分已有序列；实际v1.1从本轮registry按代理目标选bases。两者种子/输入机制也不同，不能称为仅路径适配。原正式候选池的生成器SHA及执行记录绑定v1.1，因此本批依据该绑定定位实际版本，同时保留旧版。Primary同样存在固定历史seed与新seed-base参数的区别。', '',
        '旧/新DP的exact_dp函数AST并非完全一致：v1.1新增1024子集完整性检查；整个脚本的求解入口和方法输出冻结校验也不同。实际Day4归档源码与v1.1哈希绑定。这里只报告静态差别，尚未开展递推证明或数值等价验证，不能提前报G2通过。', '',
        '本地Git HEAD/commit仅作版本线索，未联网核对远程；commit本身不保证当前工作树无改动，实际内容以逐文件SHA为准。历史D盘路径按档案后缀定位后再用已记载哈希验证，不把旧机器盘符当成本机缺失。', '',
        '## 5. 缺失、覆盖范围和后续闸口', '',
        'missing_files.csv列出实际缺项或尚未定位证据及其阻止的结论。投稿接收件身份证明和独立系统级访问日志未补造；后者不影响对已封存源码机制的有限判断。自动检查失败项如下：', '',
        *( [f'- {x["check"]}：{x["detail"]}' for x in failed] or ['- 无G0自动检查失败项。开放来源身份问题仍保留，不等同所有审稿点已解决。']), '',
        'evidence_coverage.csv逐项对应训练抽样、强度、OOB、disagreement、Reserve/queue、DP、Word公式/Table1以及4.1—4.6证据。SOURCE_LOCATED只表示已定位，不表示后续内容验收通过。', '',
        'Word仅ZIP/XML只读提取文字、域代码、OMML/嵌入对象数量。SEQ MTEqn、MERGEFORMAT、MACROBUTTON和Zotero引用分开保留；没有执行删除域或修复。没有Word导出PDF和目视验证，因此不报G3 PASS。', '',
        '## 6. 自动程序与停止点', '',
        f'程序：{link(Path(__file__).resolve())}。运行方式：', '',
        '```powershell', f'& "{sys.executable}" "{Path(__file__).resolve()}" --stage G0 --root "{root}" --out "{out}"', '```', '',
        '自动日志、逐项验收、manifest绑定检查和全部选中来源前后重哈希结果随附。G0通过仅表示进入下一批所需基本证据可用，并保留版本/来源身份问题。**本批到此停止，S1—S4全部NOT_RUN，等待作者验收与逐批授权。**', '']
    (audit / 'G0_中文审计报告.md').write_text('\n'.join(report), encoding='utf-8')
    log('audit_finished', status=validation['status'], passed=validation['checks_passed'], total=len(checks), sources=len(selected))
    (audit / 'automatic_audit_log.jsonl').write_text('\n'.join(json.dumps(e, ensure_ascii=False) for e in events)+'\n', encoding='utf-8')
    index = ['# 4.7 第一批 S0/G0 文件索引', '', f'验收状态：{validation["status"]}；本批完成后停止。', '',
             f'- {link(audit / "G0_中文审计报告.md", "中文G0验收报告")}',
             f'- {link(audit / "source_manifest.csv", "全部已选来源及SHA256")}',
             f'- {link(audit / "version_conflicts.csv", "版本冲突表")}',
             f'- {link(audit / "code_version_relations.csv", "代码版本关系")}',
             f'- {link(audit / "evidence_coverage.csv", "审稿点证据覆盖矩阵")}',
             f'- {link(audit / "missing_files.csv", "缺失文件及结论限制")}',
             f'- {link(audit / "g0_validation.json", "自动验收JSON")}',
             f'- {link(audit / "automatic_acceptance_checks.csv", "逐项自动验收")}',
             f'- {link(audit / "automatic_audit_log.jsonl", "运行日志")}',
             f'- {link(audit / "manifest_binding_checks.csv", "冻结manifest与实际文件绑定")}',
             f'- {link(audit / "formal_static_call_inventory.csv", "正式代码静态调用清单")}',
             f'- {link(audit / "legacy_11_state_call_sites.csv", "旧11状态接口调用位置")}',
             f'- {link(audit / "high_risk_source_locations.csv", "高风险源代码行号索引")}',
             f'- {link(audit / "high_risk_function_AST_comparisons.csv", "高风险函数跨版本AST对照")}',
             f'- {link(audit / "member_asset_inventory.csv", "10成员权重与日志资产索引")}',
             f'- {link(audit / "csv_schema_inventory.csv", "训练CSV字段结构")}',
             f'- {link(audit / "document_inventory.csv", "Word文档及提取文字索引")}',
             f'- {link(audit / "word_field_inventory_readonly.csv", "Word原始域代码（只读）")}',
             f'- {link(audit / "source_immutability_checks.csv", "来源前后哈希一致性")}',
             f'- {link(audit / "discovery_inventory.csv", "发现范围及选择理由")}',
             f'- {link(audit / "git_identity.csv", "本机Git版本线索")}',
             f'- {link(extract / "Reviewer1_4_7_readable.txt", "原审稿意见4.7文字")}',
             f'- {link(Path(__file__).resolve(), "可重运行G0自动审计程序")}', '',
             '## 输出目录完整清单', '']
    for p in sorted(audit.rglob('*')):
        if p.is_file():
            index.append(f'- {link(p, str(p.relative_to(out)))}')
    (out / '4.7_G0_文件索引.md').write_text('\n'.join(index)+'\n', encoding='utf-8')
    outputs = [{'path': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(out.rglob('*'))
               if p.is_file() and p.name != 'delivery_output_sha256.csv']
    table(audit / 'delivery_output_sha256.csv', outputs)
    return 1 if failed or critical_mismatch else 0


if __name__ == '__main__':
    raise SystemExit(main())
