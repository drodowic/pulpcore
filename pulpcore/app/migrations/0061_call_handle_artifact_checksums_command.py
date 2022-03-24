# Generated by Django 2.2.19 on 2021-03-05 18:35
import logging
import os
from gettext import gettext as _

from django.conf import settings
from django.db import migrations

from pulpcore import constants
from pulpcore.app import pulp_hashlib

CHUNK_SIZE = 1024 * 1024  # 1 Mb

_logger = logging.getLogger(__name__)


def handle_artifact_checksums(apps):
    Artifact = apps.get_model("core", "Artifact")
    paths = []

    # set allowed checksums
    for checksum in settings.ALLOWED_CONTENT_CHECKSUMS:
        params = {f"{checksum}__isnull": True}
        artifacts_qs = Artifact.objects.filter(**params)
        artifacts = []
        for a in artifacts_qs.iterator():
            hasher = pulp_hashlib.new(checksum)
            try:
                for chunk in a.file.chunks(CHUNK_SIZE):
                    hasher.update(chunk)
                a.file.close()
                setattr(a, checksum, hasher.hexdigest())
                artifacts.append(a)
            except FileNotFoundError:
                file_path = os.path.join(settings.MEDIA_ROOT, a.file.name)
                paths.append(file_path)

            if len(artifacts) >= 1000:
                Artifact.objects.bulk_update(objs=artifacts, fields=[checksum], batch_size=1000)
                artifacts.clear()

        if artifacts:
            Artifact.objects.bulk_update(objs=artifacts, fields=[checksum], batch_size=1000)

        if paths:
            _logger.warn(
                _(
                    "Missing files needed to update artifact {checksum} checksum: {paths}. "
                    "Please run 'pulpcore-manager handle-artifact-checksums'."
                ).format(checksum=checksum, paths=paths)
            )

        # unset any forbidden checksums
        forbidden_checksums = set(constants.ALL_KNOWN_CONTENT_CHECKSUMS).difference(
            settings.ALLOWED_CONTENT_CHECKSUMS
        )
        for checksum in forbidden_checksums:
            search_params = {f"{checksum}__isnull": False}
            update_params = {f"{checksum}": None}
            artifacts_qs = Artifact.objects.filter(**search_params)
            if artifacts_qs.exists():
                artifacts_qs.update(**update_params)


def run_handle_artifact_checksums(apps, schema_editor):
    try:
        handle_artifact_checksums(apps)
    except Exception as exc:
        _logger.warn(
            _(
                "Failed to update checksums for artifacts: {}. "
                "Please run 'pulpcore-manager handle-artifact-checksums'."
            ).format(exc)
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0060_data_migration_proxy_creds"),
    ]

    operations = [
        migrations.RunPython(
            run_handle_artifact_checksums, reverse_code=run_handle_artifact_checksums, elidable=True
        ),
    ]
