"""中文：核验实际包与已加载控制器。English: declarations are not installation proof."""
import hashlib,sys
from pathlib import Path
from .routing_contract import exact,fail
from .routing_context_contract import safe_file,bounded_bytes
from .payload_integrity import load_manifest,verify_payload
from .path_identity import same_path

def verify_installation(plan):
    descriptor=exact(plan['installation'],{'payload_root','manifest_path','runtime_files'},'SEED_INSTALLATION_FIELDS')
    root=Path(descriptor['payload_root'])
    manifest=load_manifest(safe_file(Path(descriptor['manifest_path'])))
    actual=load_manifest(safe_file(root/'PLUGIN_PAYLOAD_MANIFEST.json'))
    if manifest!=actual:fail('SEED_INSTALLED_MANIFEST_CHANGED')
    verified=verify_payload(root,manifest)
    if verified['payload_digest']!=plan['candidate_payload_digest']:fail('SEED_INSTALLED_PAYLOAD_MISMATCH')
    entries={row['path']:row for row in manifest['files']}
    needed={name for name in entries if name.startswith(('runtime/cp_runtime/','hooks/'))}
    critical={'runtime/cp_runtime/research_seed.py','runtime/cp_runtime/research_bootstrap.py',
       'runtime/cp_runtime/seed_installation.py','runtime/cp_runtime/routing_registry_v5.py',
       'runtime/cp_runtime/routing_hook_v5.py','runtime/cp_runtime/budget_v5.py','hooks/cp_hook.py'}
    if not critical.issubset(needed):fail('SEED_INSTALLATION_REQUIRED_FILES')
    rows=descriptor['runtime_files']
    if not isinstance(rows,list) or len(rows)>256:fail('SEED_RUNTIME_MAP_LIMIT')
    mapped={}
    for row in rows:
        exact(row,{'package_path','live_path'},'SEED_RUNTIME_MAP_FIELDS')
        name=row['package_path']
        if name not in needed or name in mapped:fail('SEED_RUNTIME_MAP_SCOPE')
        path=safe_file(Path(row['live_path']))
        if hashlib.sha256(bounded_bytes(path,1_048_576)).hexdigest()!=entries[name]['sha256']:fail('SEED_LIVE_CONTROLLER_CHANGED')
        mapped[name]=path
    if set(mapped)!=needed:fail('SEED_RUNTIME_MAP_INCOMPLETE')
    # 中文：导入模块必须是映射到的实际执行副本，不能用内容相同但未使用的文件替代。
    # English: Imported modules must be the mapped executing copies, not identical unused files.
    for name,module in tuple(sys.modules.items()):
        if name=='cp_runtime' or name.startswith('cp_runtime.'):
            source=getattr(module,'__file__',None)
            if not source:continue
            spec=getattr(module,'__spec__',None)
            relative='runtime/'+name.replace('.','/')+('/__init__.py' if spec and spec.submodule_search_locations is not None else '.py')
            if relative not in mapped or not same_path(Path(source),mapped[relative]):fail('SEED_LOADED_CONTROLLER_SOURCE')
    main=getattr(sys.modules.get('__main__'),'__file__',None)
    if main and Path(main).name=='cp_hook.py' and not same_path(Path(main),mapped['hooks/cp_hook.py']):fail('SEED_LOADED_HOOK_SOURCE')
    return verified
