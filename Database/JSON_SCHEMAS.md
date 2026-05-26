# JSON Schemas

These schemas are implementation starting points. Add `$schema`, stricter enums, and generated TypeScript/Python types in the app repository.

## Generation Request

```json
{
  "type": "object",
  "required": ["project_id", "clip_id", "workflow_template_id", "model_variant_id", "seed", "width", "height", "frame_count", "fps", "prompt"],
  "properties": {
    "project_id": { "type": "string", "format": "uuid" },
    "clip_id": { "type": "string", "format": "uuid" },
    "workflow_template_id": { "type": "string", "format": "uuid" },
    "model_variant_id": { "type": "string", "format": "uuid" },
    "quantization_id": { "type": "string", "format": "uuid" },
    "text_encoder_id": { "type": "string", "format": "uuid" },
    "vae_id": { "type": "string", "format": "uuid" },
    "lora_combination_id": { "type": ["string", "null"], "format": "uuid" },
    "prompt": { "type": "string" },
    "negative_prompt": { "type": "string" },
    "seed": { "type": "integer" },
    "width": { "type": "integer" },
    "height": { "type": "integer" },
    "frame_count": { "type": "integer" },
    "fps": { "type": "number" },
    "steps": { "type": "integer" },
    "sampler": { "type": "string" },
    "scheduler": { "type": "string" },
    "guidance": { "type": "number" },
    "input_asset_id": { "type": ["string", "null"], "format": "uuid" },
    "output_prefix": { "type": "string" },
    "extra_params": { "type": "object" }
  }
}
```

## Completed Generation Result

```json
{
  "type": "object",
  "required": ["run_id", "prompt_id", "status", "outputs", "metrics"],
  "properties": {
    "run_id": { "type": "string", "format": "uuid" },
    "prompt_id": { "type": "string" },
    "status": { "type": "string", "enum": ["complete", "failed", "interrupted", "timeout", "oom"] },
    "outputs": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["path", "sha256", "kind"],
        "properties": {
          "kind": { "type": "string" },
          "path": { "type": "string" },
          "sha256": { "type": "string" },
          "probe_json_path": { "type": "string" }
        }
      }
    },
    "metrics": {
      "type": "object",
      "properties": {
        "duration_sec": { "type": "number" },
        "peak_vram_mib": { "type": "number" },
        "peak_ram_mib": { "type": "number" },
        "peak_temp_c": { "type": "number" },
        "failure_message": { "type": ["string", "null"] }
      }
    }
  }
}
```

## Model Registry Entry

```json
{
  "type": "object",
  "required": ["family", "name", "variant", "source_url", "evidence_level", "compatible_24gb_status"],
  "properties": {
    "family": { "type": "string" },
    "name": { "type": "string" },
    "variant": { "type": "string" },
    "params_b": { "type": "number" },
    "file_path": { "type": "string" },
    "sha256": { "type": "string" },
    "precision": { "type": "string" },
    "quantization": { "type": "string" },
    "text_encoder": { "type": "string" },
    "vae": { "type": "string" },
    "source_url": { "type": "string" },
    "license": { "type": "string" },
    "evidence_level": { "type": "string" },
    "compatible_24gb_status": { "type": "string" },
    "local_benchmark_required": { "type": "boolean" }
  }
}
```

## LoRA Registry Entry

```json
{
  "type": "object",
  "required": ["name", "base_model", "purpose", "evidence_level"],
  "properties": {
    "name": { "type": "string" },
    "base_model": { "type": "string" },
    "base_variant": { "type": "string" },
    "purpose": { "type": "string" },
    "file_path": { "type": "string" },
    "sha256": { "type": "string" },
    "source_url": { "type": "string" },
    "license": { "type": "string" },
    "loader_node": { "type": "string" },
    "quantized_base_status": { "type": "string", "enum": ["verified", "failed", "unknown"] },
    "tested_strengths": { "type": "array", "items": { "type": "number" } },
    "evidence_level": { "type": "string" }
  }
}
```

## Final Assembly Manifest

```json
{
  "campaign_id": "uuid",
  "target_duration_sec": 1800,
  "video": {
    "fps": 30,
    "width": 1920,
    "height": 1080,
    "pixel_format": "yuv420p",
    "clips": [
      {
        "slot_index": 1,
        "asset_id": "uuid",
        "path": "outputs/clip_001.mp4",
        "start_sec": 0,
        "duration_sec": 10,
        "transition": { "type": "none" }
      }
    ]
  },
  "audio": {
    "voiceover": "audio/vo.wav",
    "music": "audio/music.wav",
    "sfx": []
  },
  "subtitles": {
    "sidecar_srt": "captions/final.srt",
    "burn_in": false
  },
  "ffmpeg_plan": {
    "normalize": true,
    "concat_method": "concat_demuxer_after_normalization",
    "final_codec": "h264"
  }
}
```
