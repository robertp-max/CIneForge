"""Shared loader and idempotent asset/story helpers for the bundled Transfiguration project."""
from __future__ import annotations
import base64
import gzip
import hashlib
import json
import zipfile
from pathlib import Path
from uuid import UUID
from sqlalchemy import select
from backend.app.db.base import AuditLog, Character, PlanningMediaAsset, Project, ProjectStoryboardSettings, Story, VoiceProfile, Chapter, Scene, Shot
from backend.app.services import reference_assets
from backend.app.services import storyboard_settings
REPO_ROOT = Path(__file__).resolve().parents[3]
BUNDLE_ROOT = REPO_ROOT / 'examples' / 'projects' / 'transfiguration_5m'
PAYLOAD_PATH = BUNDLE_ROOT / 'project_payload.json.gz'
ASSET_MANIFEST_PATH = BUNDLE_ROOT / 'asset_manifest.json'
PREVIEW_ARCHIVE_PATH = BUNDLE_ROOT / 'assets_preview.zip'

def _read_bundle_bytes(path: Path) -> bytes:
    if path.is_file():
        return path.read_bytes()
    parts = sorted(path.parent.glob(path.name + '.b64.part*'))
    if not parts:
        raise FileNotFoundError(path)
    return base64.b64decode(''.join((part.read_text(encoding='ascii') for part in parts)))

def _load_json(path: Path) -> dict:
    data = _read_bundle_bytes(path)
    if path.suffix == '.gz':
        data = gzip.decompress(data)
    return json.loads(data.decode('utf-8'))

def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {'.jpg', '.jpeg'}:
        return 'image/jpeg'
    if suffix == '.png':
        return 'image/png'
    if suffix == '.webp':
        return 'image/webp'
    raise ValueError(f'Unsupported bundled image extension: {suffix}')

def _upsert_project_and_story(db, payload: dict) -> tuple[Project, Story]:
    project_payload = payload['project']
    story_payload = payload['story']
    project_id = UUID(project_payload['id'])
    story_id = UUID(story_payload['existing_id'])
    project = db.get(Project, project_id)
    if project is None:
        project = Project(id=project_id, name=project_payload['name'], description=project_payload.get('description'))
        db.add(project)
    else:
        project.name = project_payload['name']
        project.description = project_payload.get('description')
    story = db.get(Story, story_id)
    if story is None:
        story = Story(id=story_id, project_id=project_id, title=story_payload['title'], base_story=story_payload['base_story'], target_duration_sec=story_payload['target_duration_sec'])
        db.add(story)
    db.commit()
    db.refresh(project)
    db.refresh(story)
    return (project, story)

def _apply_settings(db, project_id: UUID, values: dict) -> ProjectStoryboardSettings:
    row = db.scalar(select(ProjectStoryboardSettings).where(ProjectStoryboardSettings.project_id == project_id))
    if row is None:
        defaults = storyboard_settings.default_settings_values()
        defaults.update(values)
        row = ProjectStoryboardSettings(project_id=project_id, **defaults)
        db.add(row)
    else:
        for field, value in values.items():
            if hasattr(row, field):
                setattr(row, field, value)
        row.settings_version = int(row.settings_version or 0) + 1
    row.allow_rendering = False
    row.allow_model_download = False
    row.require_production_plan_approval = True
    db.commit()
    db.refresh(row)
    return row


def _manifest_asset_key(asset: PlanningMediaAsset) -> str | None:
    return (asset.metadata_json or {}).get('client', {}).get('asset_key')


def _project_assets_by_key(db, project_id: UUID) -> dict[str, PlanningMediaAsset]:
    rows = list(
        db.scalars(
            select(PlanningMediaAsset).where(PlanningMediaAsset.project_id == project_id)
        )
    )
    return {
        key: asset
        for asset in rows
        if (key := _manifest_asset_key(asset)) is not None
    }


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_archive_entry(
    archive: zipfile.ZipFile,
    *,
    archive_entry: str,
    expected_sha256: str,
    asset_key: str,
) -> bytes:
    try:
        data = archive.read(archive_entry)
    except KeyError as error:
        raise FileNotFoundError(f'Asset archive is missing {archive_entry}') from error
    digest = reference_assets.sha256_bytes(data)
    if digest != expected_sha256:
        raise ValueError(
            f'Asset source hash mismatch for {asset_key}: expected {expected_sha256}, got {digest}'
        )
    return data


def repair_manifest_assets(
    db,
    project_id: UUID,
    manifest: dict,
    *,
    source_archive: Path | None = None,
) -> dict:
    """Verify every manifest row and rehydrate only absent managed bytes.

    This function never creates asset rows or changes hierarchy, approvals,
    prompts, settings, campaigns, or timelines.
    """
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError(f'Project not found: {project_id}')

    if source_archive is not None:
        expected_archive_sha = manifest['source_archive']['sha256']
        actual_archive_sha = _sha256_path(source_archive)
        if actual_archive_sha != expected_archive_sha:
            raise ValueError(
                'Source archive SHA-256 mismatch: '
                f'expected {expected_archive_sha}, got {actual_archive_sha}'
            )

    assets_by_key = _project_assets_by_key(db, project_id)
    source_zip = zipfile.ZipFile(source_archive) if source_archive is not None else None
    bundle_zip = zipfile.ZipFile(PREVIEW_ARCHIVE_PATH)
    results: list[dict] = []
    repaired_asset_ids: list[str] = []
    try:
        for item in manifest['assets']:
            asset_key = item['asset_key']
            asset = assets_by_key.get(asset_key)
            if asset is None:
                raise ValueError(
                    f'Manifest asset database row is missing for {asset_key}; '
                    '--repair-assets-only will not create a replacement row.'
                )

            path = reference_assets.resolve_managed_path(asset)
            if path.exists():
                if not path.is_file():
                    raise ValueError(f'Managed asset path is not a file: {asset_key}')
                actual_sha = reference_assets.sha256_file(path)
                if actual_sha != asset.sha256:
                    reference_assets._record_integrity_failure(
                        db,
                        asset,
                        actual_sha256=actual_sha,
                        operation='repair_assets_only',
                    )
                    raise ValueError(
                        f'Managed asset SHA-256 mismatch for {asset_key}; refusing to overwrite.'
                    )
                results.append(
                    {
                        'asset_key': asset_key,
                        'asset_id': str(asset.id),
                        'status': 'verified',
                        'sha256': actual_sha,
                        'kind': asset.kind,
                    }
                )
                continue

            source_data: bytes | None = None
            source_label: str | None = None
            if source_zip is not None and asset.sha256 == item['source_sha256']:
                source_data = _verified_archive_entry(
                    source_zip,
                    archive_entry=item['source_filename'],
                    expected_sha256=item['source_sha256'],
                    asset_key=asset_key,
                )
                source_label = 'verified_source_archive'
            elif asset.sha256 == item['bundle_sha256']:
                source_data = _verified_archive_entry(
                    bundle_zip,
                    archive_entry=item['bundle_zip_entry'],
                    expected_sha256=item['bundle_sha256'],
                    asset_key=asset_key,
                )
                source_label = 'verified_bundled_archive'

            if source_data is None or source_label is None:
                raise ValueError(
                    f'No verified archive source matches database SHA-256 for missing asset {asset_key}.'
                )

            reference_assets.rehydrate_missing_asset(
                db,
                asset,
                source_data=source_data,
                source_sha256=asset.sha256,
                source_label=source_label,
            )
            repaired_asset_ids.append(str(asset.id))
            results.append(
                {
                    'asset_key': asset_key,
                    'asset_id': str(asset.id),
                    'status': 'rehydrated',
                    'sha256': asset.sha256,
                    'kind': asset.kind,
                    'source': source_label,
                }
            )
    finally:
        bundle_zip.close()
        if source_zip is not None:
            source_zip.close()

    return {
        'asset_count': len(results),
        'verified_count': sum(item['status'] == 'verified' for item in results),
        'repaired_count': len(repaired_asset_ids),
        'repaired_asset_ids': repaired_asset_ids,
        'assets': results,
    }


def migrate_legacy_storyboard_assets(
    db,
    project_id: UUID,
    manifest: dict,
) -> dict:
    """Retag legacy scene boards and remove their shot-start bindings safely."""
    assets_by_key = _project_assets_by_key(db, project_id)
    migrated_asset_ids: list[str] = []
    cleared_shot_ids: list[str] = []

    for item in manifest['assets']:
        if item.get('role') != 'scene_storyboard_reference_board':
            continue
        asset = assets_by_key.get(item['asset_key'])
        if asset is None or asset.kind == 'art_direction_reference':
            continue
        if asset.kind != 'starting_image':
            raise ValueError(
                f"Unexpected legacy kind for {item['asset_key']}: {asset.kind}"
            )

        source_path = reference_assets.resolve_managed_path(asset)
        if not source_path.is_file():
            raise ValueError(
                f"Legacy storyboard bytes are missing for {item['asset_key']}; run repair first."
            )
        actual_sha = reference_assets.sha256_file(source_path)
        if actual_sha != asset.sha256:
            reference_assets._record_integrity_failure(
                db,
                asset,
                actual_sha256=actual_sha,
                operation='migrate_storyboard_asset_kind',
            )
            raise ValueError(
                f"Legacy storyboard SHA-256 mismatch for {item['asset_key']}; refusing migration."
            )

        target_dir = reference_assets.managed_root() / str(project_id) / 'art_direction_reference'
        target_path = (target_dir / source_path.name).resolve()
        target_path.relative_to(reference_assets.managed_root())
        if target_path.exists():
            raise ValueError(
                f"Migration target already exists for {item['asset_key']}; refusing overwrite."
            )
        target_dir.mkdir(parents=True, exist_ok=True)
        source_path.replace(target_path)
        if reference_assets.sha256_file(target_path) != asset.sha256:
            target_path.replace(source_path)
            raise ValueError(f"Post-migration SHA-256 failed for {item['asset_key']}")

        old_kind = asset.kind
        old_uri = asset.managed_uri
        asset.kind = 'art_direction_reference'
        asset.managed_uri = reference_assets.build_managed_uri(
            project_id, 'art_direction_reference', target_path.name
        )
        db.add(
            AuditLog(
                entity_type='planning_media_asset',
                entity_id=asset.id,
                action='scene_storyboard_reclassified_as_art_direction_reference',
                details={
                    'asset_key': item['asset_key'],
                    'old_kind': old_kind,
                    'new_kind': asset.kind,
                    'old_managed_uri': old_uri,
                    'new_managed_uri': asset.managed_uri,
                    'sha256_verified': asset.sha256,
                    'approval_state_preserved': asset.approval_state,
                },
            )
        )
        try:
            db.commit()
        except Exception:
            db.rollback()
            if target_path.exists() and not source_path.exists():
                target_path.replace(source_path)
            raise
        migrated_asset_ids.append(str(asset.id))

    board_asset_ids = {
        asset.id
        for key, asset in assets_by_key.items()
        if key.startswith('scene_') and key.endswith('_storyboard')
    }
    if board_asset_ids:
        linked_shots = list(
            db.scalars(
                select(Shot).where(Shot.starting_image_asset_id.in_(board_asset_ids))
            )
        )
        for shot in linked_shots:
            cleared_shot_ids.append(str(shot.id))
            shot.starting_image_asset_id = None
        if linked_shots:
            db.add(
                AuditLog(
                    entity_type='planning_media_asset',
                    entity_id=None,
                    action='scene_storyboard_shot_start_bindings_cleared',
                    details={
                        'asset_ids': sorted(str(asset_id) for asset_id in board_asset_ids),
                        'shot_ids': sorted(cleared_shot_ids),
                        'reason': 'multi_panel_storyboards_are_planning_references_not_frame_zero',
                    },
                )
            )
            db.commit()

    return {
        'migrated_asset_ids': migrated_asset_ids,
        'cleared_shot_ids': cleared_shot_ids,
    }

def _import_assets(db, project_id: UUID, manifest: dict, *, source_archive: Path | None=None) -> dict[str, UUID]:
    mapping: dict[str, UUID] = {}
    archive_path = source_archive or PREVIEW_ARCHIVE_PATH
    if source_archive is not None:
        expected_archive_sha = manifest['source_archive']['sha256']
        actual_archive_sha = _sha256_path(source_archive)
        if actual_archive_sha != expected_archive_sha:
            raise ValueError(
                'Source archive SHA-256 mismatch: '
                f'expected {expected_archive_sha}, got {actual_archive_sha}'
            )
    archive = zipfile.ZipFile(archive_path)
    try:
        for item in manifest['assets']:
            if source_archive is not None:
                archive_entry = item['source_filename']
                expected_digest = item['source_sha256']
                original_filename = item['source_filename']
                ingest_source = 'user_source_archive_full_resolution'
            else:
                archive_entry = item['bundle_zip_entry']
                expected_digest = item['bundle_sha256']
                original_filename = Path(archive_entry).name
                ingest_source = 'bundled_low_resolution_preview'
            data = _verified_archive_entry(
                archive,
                archive_entry=archive_entry,
                expected_sha256=expected_digest,
                asset_key=item['asset_key'],
            )
            asset, _created = reference_assets.upload_asset(db, project_id=project_id, kind=item['kind'], data=data, original_filename=original_filename, content_type=_content_type(Path(original_filename)), source_type='bundled_project_reference', approval_state='draft', extra_metadata={'asset_key': item['asset_key'], 'role': item['role'], 'character_client_id': item.get('character_client_id'), 'scene_number': item.get('scene_number'), 'generation_use': item.get('generation_use'), 'restrictions': item.get('restrictions'), 'source_filename': item.get('source_filename'), 'source_sha256': item.get('source_sha256'), 'ingest_source': ingest_source})
            mapping[item['asset_key']] = asset.id
    finally:
        archive.close()
    return mapping

def _resolved_story_payload(payload: dict, assets: dict[str, UUID]) -> dict:
    story_payload = json.loads(json.dumps(payload['story']))
    for character in story_payload.get('characters', []):
        character['reference_asset_ids'] = [str(assets[key]) for key in character.pop('reference_asset_keys', [])]
    return story_payload


def bind_scene_art_direction_metadata(
    db,
    story: Story,
    payload: dict,
    manifest: dict,
    assets: dict[str, UUID],
) -> None:
    """Persist scene identity in asset metadata without adding a shot binding."""
    chapters = list(
        db.scalars(
            select(Chapter)
            .where(Chapter.story_id == story.id, Chapter.archived_at.is_(None))
            .order_by(Chapter.order_index, Chapter.id)
        )
    )
    scenes_by_chapter: dict[UUID, list[Scene]] = {}
    for chapter in chapters:
        scenes_by_chapter[chapter.id] = list(
            db.scalars(
                select(Scene)
                .where(Scene.chapter_id == chapter.id, Scene.archived_at.is_(None))
                .order_by(Scene.order_index, Scene.id)
            )
        )
    ordered_scenes = [
        scene for chapter in chapters for scene in scenes_by_chapter.get(chapter.id, [])
    ]
    board_items = sorted(
        (
            item
            for item in manifest['assets']
            if item.get('role') == 'scene_storyboard_reference_board'
        ),
        key=lambda item: int(item['scene_number']),
    )
    if len(ordered_scenes) != len(board_items):
        raise ValueError(
            'Cannot bind art-direction references: scene and storyboard counts differ.'
        )
    for item, scene in zip(board_items, ordered_scenes, strict=True):
        asset_id = assets[item['asset_key']]
        asset = db.get(PlanningMediaAsset, asset_id)
        if asset is None or asset.kind != 'art_direction_reference':
            raise ValueError(f"Art-direction asset is unavailable for {item['asset_key']}")
        metadata = dict(asset.metadata_json or {})
        client = dict(metadata.get('client') or {})
        client['scene_id'] = str(scene.id)
        client['scene_number'] = int(item['scene_number'])
        client['generation_use'] = 'planning_reference_only_not_an_approved_frame_zero'
        metadata['client'] = client
        asset.metadata_json = metadata
    db.commit()

def _bind_existing_ids(db, story: Story, story_payload: dict) -> None:
    """Bind client payload nodes to existing rows so repeat imports update, not duplicate."""
    voices_by_name = {row.name: row for row in db.scalars(select(VoiceProfile).where(VoiceProfile.story_id == story.id, VoiceProfile.archived_at.is_(None)))}
    for voice_payload in story_payload.get('voices') or []:
        existing = voices_by_name.get(voice_payload.get('name'))
        if existing is not None:
            voice_payload['existing_id'] = str(existing.id)
    characters_by_name = {row.name: row for row in db.scalars(select(Character).where(Character.story_id == story.id, Character.archived_at.is_(None)))}
    for character_payload in story_payload.get('characters') or []:
        existing = characters_by_name.get(character_payload.get('name'))
        if existing is not None:
            character_payload['existing_id'] = str(existing.id)
    existing_chapters = list(db.scalars(select(Chapter).where(Chapter.story_id == story.id)))
    chapter_by_title = {row.title: row for row in existing_chapters}
    for chapter_payload in story_payload.get('chapters') or []:
        chapter = chapter_by_title.get(chapter_payload.get('title'))
        if chapter is None:
            continue
        chapter_payload['existing_id'] = str(chapter.id)
        existing_scenes = list(db.scalars(select(Scene).where(Scene.chapter_id == chapter.id)))
        scene_by_title = {row.title: row for row in existing_scenes}
        for scene_payload in chapter_payload.get('scenes') or []:
            scene = scene_by_title.get(scene_payload.get('title'))
            if scene is None:
                continue
            scene_payload['existing_id'] = str(scene.id)
            existing_shots = list(db.scalars(select(Shot).where(Shot.scene_id == scene.id)))
            shot_by_title = {row.title: row for row in existing_shots}
            for shot_payload in scene_payload.get('shots') or []:
                shot = shot_by_title.get(shot_payload.get('title'))
                if shot is not None:
                    shot_payload['existing_id'] = str(shot.id)
