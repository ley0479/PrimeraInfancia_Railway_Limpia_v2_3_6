from __future__ import annotations

import os

from app import DATABASE_PATH
from modules.idp_documental.worker import run_forever


if __name__=='__main__':
    run_forever(DATABASE_PATH,float(os.environ.get('IDP_WORKER_POLL_SECONDS','2')))
