from celery import Celery
from fastapi import HTTPException
from sqlalchemy import select

from app.adapters.proxmox import make_adapter
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import configure_logging
from app.models import VM, Job, User, VMRequest
from app.services.configuration import ConfigurationService
from app.services.provisioning import ProvisioningService
from app.services.templates import for_request

configure_logging()
config = settings()
celery = Celery("portal", broker=config.redis_url)
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "dispatch-outbox": {"task": "portal.dispatch", "schedule": 10.0},
        "purge-history": {"task": "portal.purge_history", "schedule": 3600.0},
    },
)


@celery.task(name="portal.dispatch")
def dispatch():
    with SessionLocal() as db:
        from app.services.accounts import AccountService

        for owner_id in db.scalars(
            select(User.id).where(User.status == "deleting")
        ).all():
            AccountService(db).finalize(owner_id)
            db.commit()
        ids = db.scalars(select(Job.id).where(Job.state == "queued").limit(100)).all()
    for job_id in ids:
        execute.delay(job_id)


@celery.task(name="portal.execute", acks_late=True)
def execute(job_id):
    with SessionLocal() as db:
        try:
            runtime = ConfigurationService(db).runtime(lock=True, require_enabled=True)
        except HTTPException as exc:
            if exc.status_code == 409:
                return
            raise
        if runtime.proxmox_mode == "real" and not runtime.provisioning_enabled:
            return
        # Clone and resize with the template fixed when the request was approved.
        job = db.get(Job, job_id)
        vm = db.get(VM, job.vm_id) if job else None
        runtime = for_request(runtime, db.get(VMRequest, vm.request_id) if vm else None)
        adapter = make_adapter(runtime)
        try:
            ProvisioningService(db, adapter, runtime).run(job_id)
        finally:
            adapter.close()


@celery.task(name="portal.purge_history")
def purge_history():
    from app.services.retention import purge_history as purge

    with SessionLocal() as db:
        counts = purge(db)
        db.commit()
        return counts
