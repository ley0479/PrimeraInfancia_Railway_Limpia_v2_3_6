from __future__ import annotations

from pathlib import Path
import socket
import time
import uuid

from modules.seguridad.tenant_context import tenant_context

from .repository import IDPRepository
from .services import canonicalize, classify_document, read_document


def process_next(database_path: str, worker_id: str | None=None) -> bool:
    repo=IDPRepository(database_path); identity=worker_id or f'{socket.gethostname()}-{uuid.uuid4().hex[:8]}'
    with tenant_context(None,role='SYSTEM',username=identity,allow_global=True,source='idp-worker'):
        job=repo.claim_job(identity)
    if not job: return False
    tenant_id=int(job['fundacion_id']); document_id=int(job['documento_id'])
    try:
        with tenant_context(tenant_id,role='SYSTEM',username=identity,source='idp-worker'):
            source=repo.queued_document_source(document_id,tenant_id)
            if not source: raise KeyError('Documento encolado no encontrado.')
            path=Path(source['ruta_privada']); raw=read_document(path); classification=classify_document(raw.get('texto') or '',source['nombre_original']); canonical,fields=canonicalize(raw,classification[0]); canonical['fundacion']['id']=tenant_id
            repo.complete_extraction(document_id,tenant_id,raw,canonical,fields,classification,source.get('usuario_carga_id')); repo.finish_job(job['id'],tenant_id)
    except Exception as exc:
        with tenant_context(tenant_id,role='SYSTEM',username=identity,source='idp-worker'):
            final=repo.retry_or_fail_job(job['id'],tenant_id,type(exc).__name__.upper())
            if final: repo.fail_extraction(document_id,tenant_id,type(exc).__name__.upper(),None)
    return True


def run_forever(database_path: str, poll_seconds: float=2.0) -> None:
    identity=f'{socket.gethostname()}-{uuid.uuid4().hex[:8]}'
    while True:
        if not process_next(database_path,identity): time.sleep(max(.5,poll_seconds))
