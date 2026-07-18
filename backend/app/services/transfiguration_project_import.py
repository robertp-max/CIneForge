"""Planning-only import service for the bundled five-minute Transfiguration project."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from uuid import UUID, uuid4, uuid5
from sqlalchemy import select
from backend.app.core.config import get_settings
from backend.app.db.base import AuditLog, Campaign, Chapter, Project, ProjectStoryboardSettings, Scene, Shot, Story, StoryboardVersion, TimelineSlot, Track
from backend.app.db.session import SessionLocal
from backend.app.services import storyboard_mutations as mutations
from backend.app.services import storyboard_snapshot
from backend.app.services.transfiguration_project_bundle import ASSET_MANIFEST_PATH, PAYLOAD_PATH, _apply_settings, _bind_existing_ids, _import_assets, _load_json, _resolved_story_payload, _upsert_project_and_story, bind_scene_art_direction_metadata, migrate_legacy_storyboard_assets, repair_manifest_assets
IMPORT_NAMESPACE = UUID('f2ad03b3-124e-4b76-a7c9-53f4a93b16ef')

def _upsert_campaign_timeline(db, payload: dict) -> None:
    project_id = UUID(payload['project']['id'])
    campaign_payload = payload['campaign']
    campaign_id = UUID(campaign_payload['id'])
    track_id = UUID(campaign_payload['track_id'])
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        campaign = Campaign(id=campaign_id, project_id=project_id, name=campaign_payload['name'], target_duration_sec=campaign_payload['target_duration_sec'])
        db.add(campaign)
    else:
        campaign.name = campaign_payload['name']
        campaign.target_duration_sec = campaign_payload['target_duration_sec']
    track = db.get(Track, track_id)
    if track is None:
        track = Track(id=track_id, campaign_id=campaign_id, name='Video', kind='video', sort_order=0)
        db.add(track)
    db.flush()
    previous_slot_id = None
    slot_index = 0
    for chapter in payload['story']['chapters']:
        for scene in chapter['scenes']:
            for shot in scene['shots']:
                slot_id = uuid5(IMPORT_NAMESPACE, f"timeline-slot:{shot['client_id']}")
                slot = db.get(TimelineSlot, slot_id)
                metadata = shot['production_metadata']
                if slot is None:
                    slot = TimelineSlot(id=slot_id, track_id=track_id, slot_index=slot_index, start_sec=metadata['start_sec'], duration_sec=shot['duration_sec'], continuity_source_slot_id=previous_slot_id, notes=f"{shot['title']} | blocked planning slot | {metadata['ltx_latent_frames']} LTX frames")
                    db.add(slot)
                else:
                    slot.slot_index = slot_index
                    slot.start_sec = metadata['start_sec']
                    slot.duration_sec = shot['duration_sec']
                    slot.continuity_source_slot_id = previous_slot_id
                    slot.notes = f"{shot['title']} | blocked planning slot | {metadata['ltx_latent_frames']} LTX frames"
                previous_slot_id = slot_id
                slot_index += 1
    db.commit()

def _apply_story_graph(db, story: Story, payload: dict, assets: dict[str, UUID]) -> dict[str, Shot]:
    story_payload = _resolved_story_payload(payload, assets)
    _bind_existing_ids(db, story, story_payload)
    mutations.upsert_story_fields(story, story_payload)
    story.narrative_objectives_json = story_payload.get('narrative_objectives_json') or {}
    story.pacing_plan_json = story_payload.get('pacing_plan_json') or {}
    story.duration_strategy_json = story_payload.get('duration_strategy_json') or {}
    story.approval_state = 'draft'
    voices = mutations.upsert_voices(db, story.id, story_payload.get('voices') or [])
    characters = mutations.upsert_characters(db, story.id, story_payload.get('characters') or [], voices)
    shots = mutations.upsert_hierarchy(db, story.id, story_payload.get('chapters') or [], characters, voices, replace_identities=True)
    chapters_by_order = {int(row.order_index): row for row in db.scalars(select(Chapter).where(Chapter.story_id == story.id)) if row.archived_at is None}
    for chapter_payload in story_payload.get('chapters') or []:
        chapter = chapters_by_order[int(chapter_payload['order_index'])]
        chapter.summary = chapter_payload.get('summary')
        chapter.narrative_purpose = chapter_payload.get('summary')
        chapter.target_duration_sec = sum((float(shot['duration_sec']) for scene in chapter_payload.get('scenes') or [] for shot in scene.get('shots') or []))
        scenes_by_order = {int(row.order_index): row for row in db.scalars(select(Scene).where(Scene.chapter_id == chapter.id)) if row.archived_at is None}
        for scene_payload in chapter_payload.get('scenes') or []:
            scene = scenes_by_order[int(scene_payload['order_index'])]
            scene.summary = scene_payload.get('summary')
            scene.narrative_purpose = scene_payload.get('narrative_purpose')
            scene.location = scene_payload.get('location')
            scene.conflict_or_beat = scene_payload.get('conflict_or_beat')
            scene.target_duration_sec = sum((float(shot['duration_sec']) for shot in scene_payload.get('shots') or []))
            for shot_payload in scene_payload.get('shots') or []:
                shot = shots[shot_payload['client_id']]
                shot.camera_direction = shot_payload.get('camera_direction')
                shot.motion_direction = shot_payload.get('motion_direction')
                shot.production_status = 'blocked'
                metadata = shot_payload.get('production_metadata') or {}
                shot.blocked_reason = f"Human approval required for character references and a clean single-frame start image; workflow admission/benchmark gates must pass; 2x final upscale required. Planned routes: preview={metadata.get('preview_workflow')}, final={metadata.get('final_workflow')}, control={metadata.get('control_workflow')}, continuity={metadata.get('continuity_workflow')}."
                # Multi-panel scene storyboard boards are planning references,
                # never shot-specific frame-zero candidates.
                shot.starting_image_asset_id = None
                shot.starting_image_required = True
                shot.approval_state = 'draft'
    db.flush()
    db.commit()
    return shots

def _create_or_reuse_draft_version(db, story: Story) -> StoryboardVersion:
    snapshot, digest = storyboard_snapshot.build_snapshot_with_hash(db, story.id)
    latest = db.scalar(select(StoryboardVersion).where(StoryboardVersion.story_id == story.id).order_by(StoryboardVersion.version_number.desc()).limit(1))
    if latest is not None and latest.content_hash == digest:
        story.active_storyboard_version_id = latest.id
        db.commit()
        return latest
    version = StoryboardVersion(id=uuid4(), story_id=story.id, version_number=int(latest.version_number) + 1 if latest else 1, status='draft', snapshot_json=snapshot, created_by='scripts/import_transfiguration_project.py', base_version_id=latest.id if latest else None, content_hash=digest)
    db.add(version)
    db.flush()
    story.active_storyboard_version_id = version.id
    story.approval_state = 'draft'
    db.add(AuditLog(entity_type='storyboard_version', entity_id=version.id, action='bundled_transfiguration_project_imported', details={'story_id': str(story.id), 'content_hash': digest, 'planning_only': True, 'rendering_enabled': False}))
    db.commit()
    db.refresh(version)
    return version

def _dry_run_summary(payload: dict, manifest: dict) -> dict:
    shots = [shot for chapter in payload['story']['chapters'] for scene in chapter['scenes'] for shot in scene['shots']]
    return {'project_id': payload['project']['id'], 'story_id': payload['story']['existing_id'], 'target_duration_sec': payload['story']['target_duration_sec'], 'chapter_count': len(payload['story']['chapters']), 'scene_count': sum((len(chapter['scenes']) for chapter in payload['story']['chapters'])), 'shot_count': len(shots), 'planned_duration_sec': sum((float(shot['duration_sec']) for shot in shots)), 'character_count': len(payload['story']['characters']), 'asset_count': len(manifest['assets']), 'allow_rendering': payload['settings']['allow_rendering']}

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Validate and print without database or asset writes.')
    parser.add_argument('--repair-assets-only', action='store_true', help='Verify managed Transfiguration assets and rehydrate missing bytes without changing hierarchy, shots, prompts, settings, approvals, campaigns, or timelines.')
    parser.add_argument('--source-archive', type=Path, help='Optional path to the original transfiguration.zip. Full-resolution selected images are SHA-verified and preferred over bundled previews.')
    args = parser.parse_args()
    payload = _load_json(PAYLOAD_PATH)
    manifest = _load_json(ASSET_MANIFEST_PATH)
    if args.source_archive is not None:
        args.source_archive = args.source_archive.expanduser().resolve()
        if not args.source_archive.is_file():
            raise SystemExit(f'Source archive not found: {args.source_archive}')
    summary = _dry_run_summary(payload, manifest)
    if summary['shot_count'] != 40 or summary['planned_duration_sec'] != 300.0:
        raise SystemExit(f'Bundle validation failed: {summary}')
    if args.dry_run:
        print(json.dumps({'status': 'dry_run_ok', **summary}, indent=2))
        return
    settings = get_settings()
    configuration = {
        'database_url': settings.database_url,
        'storage_root': str(settings.storage_root.resolve()),
    }
    with SessionLocal() as db:
        if args.repair_assets_only:
            project_id = UUID(payload['project']['id'])
            if db.get(Project, project_id) is None:
                raise SystemExit(f'Transfiguration project not found: {project_id}')
            repair = repair_manifest_assets(
                db,
                project_id,
                manifest,
                source_archive=args.source_archive,
            )
            print(json.dumps({
                'status': 'assets_repaired_or_verified',
                **configuration,
                'project_id': str(project_id),
                **repair,
            }, indent=2))
            return
        project, story = _upsert_project_and_story(db, payload)
        semantic_migration = migrate_legacy_storyboard_assets(db, project.id, manifest)
        _apply_settings(db, project.id, payload['settings'])
        assets = _import_assets(db, project.id, manifest, source_archive=args.source_archive)
        _upsert_campaign_timeline(db, payload)
        shots = _apply_story_graph(db, story, payload, assets)
        bind_scene_art_direction_metadata(db, story, payload, manifest, assets)
        version = _create_or_reuse_draft_version(db, story)
        print(json.dumps({'status': 'imported', **configuration, **summary, 'project_id': str(project.id), 'story_id': str(story.id), 'storyboard_version_id': str(version.id), 'storyboard_version_number': version.version_number, 'managed_asset_ids': {key: str(value) for key, value in assets.items()}, 'shot_ids': {key: str(value.id) for key, value in shots.items()}, 'semantic_migration': semantic_migration, 'rendering_enabled': False, 'next_action': 'Review character references, scene art-direction boards, clean per-shot start frames, narration and workflow benchmark gates in CineForge.'}, indent=2))
if __name__ == '__main__':
    main()
