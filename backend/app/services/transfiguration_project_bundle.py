"""Shared loader and idempotent asset/story helpers for the bundled Transfiguration project."""
from __future__ import annotations
import base64
import gzip
import json
import zipfile
from pathlib import Path
from uuid import UUID
from sqlalchemy import select
from backend.app.db.base import Character, Project, ProjectStoryboardSettings, Story, VoiceProfile, Chapter, Scene, Shot
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

def _import_assets(db, project_id: UUID, manifest: dict, *, source_archive: Path | None=None) -> dict[str, UUID]:
    mapping: dict[str, UUID] = {}
    archive_path = source_archive or PREVIEW_ARCHIVE_PATH
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
            try:
                data = archive.read(archive_entry)
            except KeyError as error:
                raise FileNotFoundError(f'Asset archive is missing {archive_entry}') from error
            digest = reference_assets.sha256_bytes(data)
            if digest != expected_digest:
                raise ValueError(f"Asset hash mismatch: {item['asset_key']}")
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
