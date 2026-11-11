"""Retrieve an APEX artifact with a private bearer token, never a public link.

This is a local authorized operator client. It never publishes content or changes
accounts. Store CONTENT_ARTIFACT_TOKEN in your secret manager, not in arguments.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import tempfile
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

BASE_URL = 'https://apex-content-worker-production.up.railway.app'
JOB_ID = re.compile(r'[a-z0-9][a-z0-9-]{2,79}\Z')
ARTIFACTS = {'video.mp4', 'captions.srt', 'manifest.json'}
MAX_BYTES = 100 * 1024 * 1024


class NoRedirects(HTTPRedirectHandler):
    """Never forward the credential to a redirect destination."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def retrieve(job_id, artifact, destination, *, expected_sha256=None, base_url=BASE_URL):
    """Return (saved_path, actual_sha256), with an atomic no-clobber save."""
    if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id):
        raise ValueError('invalid job ID')
    if artifact not in ARTIFACTS:
        raise ValueError('unsupported artifact')
    if expected_sha256 is not None and not re.fullmatch(r'[0-9a-fA-F]{64}', expected_sha256):
        raise ValueError('expected SHA-256 must be 64 hex characters')
    token = os.environ.get('CONTENT_ARTIFACT_TOKEN', '')
    if not token or any(char in token for char in '\r\n'):
        raise ValueError('CONTENT_ARTIFACT_TOKEN is missing or invalid')
    if base_url != BASE_URL and not base_url.startswith('http://127.0.0.1:'):
        raise ValueError('unapproved download origin')
    target = Path(destination)
    if target.exists() or target.is_symlink():
        raise FileExistsError('destination already exists')
    if not target.parent.is_dir():
        raise ValueError('destination directory does not exist')
    url = f'{base_url}/artifacts/{job_id}/{artifact}'
    request = Request(url, headers={'Authorization': 'Bearer ' + token})
    digest = hashlib.sha256()
    temporary = None
    total = 0
    try:
        with build_opener(NoRedirects()).open(request, timeout=20) as response:
            if response.geturl() != url:
                raise ValueError('unexpected artifact origin')
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.apex-artifact-', delete=False) as f:
                temporary = Path(f.name)
                while True:
                    block = response.read(64 * 1024)
                    if not block:
                        break
                    total += len(block)
                    if total > MAX_BYTES:
                        raise ValueError('artifact exceeds download limit')
                    digest.update(block)
                    f.write(block)
        actual = digest.hexdigest()
        if expected_sha256 is not None and actual != expected_sha256.lower():
            raise ValueError('artifact SHA-256 mismatch; nothing saved')
        os.link(temporary, target)  # Fails closed if the destination appeared meanwhile.
        return target, actual
    except HTTPError as exc:
        raise ValueError(f'artifact request rejected (HTTP {exc.code})') from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job_id')
    parser.add_argument('artifact', choices=sorted(ARTIFACTS))
    parser.add_argument('destination')
    parser.add_argument('--sha256', help='Optional pre-recorded expected digest')
    args = parser.parse_args()
    path, digest = retrieve(args.job_id, args.artifact, args.destination, expected_sha256=args.sha256)
    print(f'Saved {path}; SHA-256 {digest}')


if __name__ == '__main__':
    main()
