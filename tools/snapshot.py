"""Verify/restore the public snapshot without importing project code or loading models."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile

REPO = Path(__file__).resolve().parents[1]


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def safe_path(root, name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or any(':' in x for x in path.parts):
        raise ValueError('Unsafe manifest path: ' + name)
    result = root.joinpath(*path.parts).resolve()
    result.relative_to(root.resolve())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['verify', 'restore', 'join'])
    parser.add_argument('--archive', type=Path, help='Release research-artifacts-20261021.tar.gz')
    parser.add_argument('--output', type=Path, help='New empty directory, required for restore')
    parser.add_argument('--parts',type=Path,help='Downloaded Release parts directory, required for join')
    args = parser.parse_args()
    manifest = json.loads((REPO/'manifests/snapshot.json').read_text('utf-8'))
    summary = json.loads((REPO/'manifests/export-summary.json').read_text('utf-8'))
    if args.mode=='join':
        if not args.parts or not args.archive:
            parser.error('join requires --parts and --archive')
        if args.archive.exists():
            if sha(args.archive)==summary['asset_sha256']:
                print('Existing archive already matches SHA-256');return
            raise ValueError('Archive exists with different content; choose a new output path')
        parts=summary['release_parts']
        for item in parts:
            source=safe_path(args.parts,item['name'])
            if source.stat().st_size!=item['bytes'] or sha(source)!=item['sha256']:
                raise ValueError('Release part mismatch: '+item['name'])
        args.archive.parent.mkdir(parents=True,exist_ok=True)
        temp=args.archive.with_name(args.archive.name+'.assembling')
        with temp.open('xb') as dest:
            for item in parts:
                with safe_path(args.parts,item['name']).open('rb') as source:
                    shutil.copyfileobj(source,dest,1024*1024)
        if sha(temp)!=summary['asset_sha256']:
            raise ValueError('Joined archive SHA-256 mismatch')
        temp.rename(args.archive)
        print('Joined and verified',len(parts),'parts into',args.archive)
        return
    files = manifest['files']
    by_path = {x['path']: x for x in files}
    if len(by_path) != len(files):
        raise ValueError('Duplicate logical paths')
    canonical = {x['path']: x for x in files if 'alias_of' not in x}
    for item in files:
        safe_path(REPO, item['path'])
        if 'alias_of' in item:
            original = canonical[item['alias_of']]
            if original['export_sha256'] != item['export_sha256'] or original['bytes'] != item['bytes']:
                raise ValueError('Invalid duplicate alias: '+item['path'])
    if args.archive:
        if sha(args.archive) != summary['asset_sha256']:
            raise ValueError('Release archive SHA-256 mismatch')
        expected = {'objects/'+x['object']:x for x in canonical.values() if x['storage']=='release'}
        seen=set()
        with tarfile.open(args.archive, 'r|gz') as tar:
            for member in tar:
                name=member.name;safe_path(REPO,name)
                if name not in expected or name in seen or not member.isfile():
                    raise ValueError('Unexpected or duplicated archive member')
                seen.add(name);item=expected[name]
                digest=hashlib.sha256()
                with tar.extractfile(member) as stream:
                    for block in iter(lambda:stream.read(1024*1024), b''):
                        digest.update(block)
                if member.size!=item['bytes'] or digest.hexdigest()!=item['export_sha256']:
                    raise ValueError('Release object mismatch: '+item['path'])
        if seen!=set(expected):
            raise ValueError('Missing archive members')
    for item in canonical.values():
        if item['storage']=='git':
            source=safe_path(REPO,item['path'])
            if not source.is_file() or source.stat().st_size!=item['bytes'] or sha(source)!=item['export_sha256']:
                raise ValueError('Snapshot file mismatch: '+item['path'])
    if args.mode=='restore':
        if not args.output or not args.archive:
            parser.error('restore requires --output and --archive')
        output=args.output.resolve()
        if output.exists() and any(output.iterdir()):
            raise ValueError('Output must be a new or empty directory; existing work will not be overwritten')
        output.mkdir(parents=True,exist_ok=True)
        # Read gzip only once: extracting each object separately would rescan the archive.
        for item in canonical.values():
            if item['storage']=='git':
                target=safe_path(output,item['path']);target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(safe_path(REPO,item['path']),target)
        wanted={'objects/'+x['object']:x for x in canonical.values() if x['storage']=='release'}
        with tarfile.open(args.archive,'r|gz') as sequential:
            for member in sequential:
                item=wanted[member.name];target=safe_path(output,item['path']);target.parent.mkdir(parents=True,exist_ok=True)
                with sequential.extractfile(member) as stream,target.open('wb') as dest:
                    shutil.copyfileobj(stream,dest,1024*1024)
        for item in files:
            if 'alias_of' in item:
                target=safe_path(output,item['path']);target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(safe_path(output,item['alias_of']),target)
        for item in files:
            if sha(safe_path(output,item['path']))!=item['export_sha256']:
                raise ValueError('Restored file mismatch: '+item['path'])
        print('Restored and verified',len(files),'files to',output)
    else:
        print('Verified',len(canonical),'unique entries and',len(files)-len(canonical),'duplicate aliases')
        if not args.archive:
            print('Release artifacts not checked; supply --archive for complete verification')


if __name__=='__main__':
    main()
