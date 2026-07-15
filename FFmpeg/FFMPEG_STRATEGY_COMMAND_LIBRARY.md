# FFmpeg Strategy and Command Library

Documentation status: M5 safe-builder checkpoint. This library describes the current allowlisted FFmpeg recipe builders as structured argument-array templates. It is not a shell script, not a set of raw command strings, and not an execution path.

Safety boundary:

- Builders return inert data such as `list[str]` argv arrays, concat manifest text, input paths, input SHA256 values, and optional output paths.
- Recipe catalog records are read-only and declare `command_shape=structured_argument_array`, `executes_from_catalog=false`, and `user_authored_command_allowed=false`.
- User-authored FFmpeg command strings are not part of this library.
- Stream-copy concat is gated by stored probe compatibility and one SHA256 per input.
- Path inputs and outputs are resolved inside the configured storage root before command-array construction.
- No FFmpeg, ComfyUI, GPU, render, or benchmark run is implied by this document.
- This checkpoint did not run FFmpeg, ComfyUI, GPU workloads, renders, or benchmarks.

## M5 Allowlisted Recipe Catalog

| Template ID | Category | Builder/output shape | Main gates | Notes |
|---|---|---|---|---|
| `concat_stream_copy_v1` | assembly | concat manifest text plus input path/hash metadata | at least one path; one probe and one SHA256 per path; matching video/audio stream signatures; storage-root path safety | Manifest builder only; it does not build or execute an FFmpeg argv by itself. |
| `normalize_mezzanine_prores_v1` | normalization | structured argv array | input SHA256; input/output path safety | ProRes mezzanine normalization template. |
| `normalize_delivery_h264_v1` | normalization | structured argv array | input SHA256; input/output path safety | H.264/AAC delivery-normalization template with `+faststart`. |
| `assemble_exact_duration_h264_v1` | assembly | structured argv array from an exact-duration plan | exact timeline duration; one input SHA256 per clip; input/output path safety; allowlisted template id | Deterministic trim/scale/pad/concat filter plan for reviewed clips. |
| `audio_mux_v1` | audio | structured argv array | video SHA256; audio SHA256; input/output path safety | Copies video and encodes reviewed audio/final mix to AAC. |
| `captions_srt_mux_v1` | captions | structured argv array | video SHA256; captions SHA256; `.srt` captions suffix; input/output path safety | Soft-caption mux with `mov_text`; no subtitle burn-in recipe is allowlisted here. |
| `audio_loudness_normalize_v1` | audio | structured argv array | input SHA256; input/output path safety | Single-pass loudnorm template in the current builder. |
| `decode_validate_v1` | validation | structured argv array | input SHA256; input path safety | Full decode-to-null validation template; documentation only, not executed by this checkpoint. |
| `conform_timing_h264_v1` | timing_conform | structured argv array | input SHA256; positive duration/fps/width/height; input/output path safety | Single-input trim/fps/scale/pad conform template. |
| `delivery_package_mp4_faststart_v1` | delivery_packaging | structured argv array | input SHA256; `.mp4` output suffix; input/output path safety | H.264/AAC MP4 packaging template with optional audio map and `+faststart`. |
| `transition_crossfade_h264_v1` | transitions | structured argv array | two input SHA256 values; positive transition duration/offset/fps/width/height; input/output path safety | Two-input xfade template; video-only output in current builder. |

## Structured Argv Template Conventions

The examples below are argv shapes. They are intentionally shown as arrays to reinforce that CineForge builds structured data, not shell-interpolated command text.

Placeholder convention:

- `<safe_input>`, `<safe_output>`, `<safe_video>`, `<safe_audio>`, and `<safe_captions>` mean paths resolved inside the configured storage root.
- `<sha256>` means a validated 64-character hexadecimal SHA256 string stored with the manifest/plan.
- Numeric placeholders such as `<duration>`, `<fps>`, `<width>`, and `<height>` are validated as positive values before insertion into filter strings.
- Filter strings are single argv elements, not shell fragments.

## Concat Stream-copy Manifest Gates

Builder: `FFmpegService.build_stream_copy_concat_manifest(...)`

Output shape:

```json
{
  "manifest": "file '<safe_clip_001>'\nfile '<safe_clip_002>'\n",
  "input_paths": ["<safe_clip_001>", "<safe_clip_002>"],
  "input_hashes": ["<sha256_001>", "<sha256_002>"],
  "compatibility_reason": "all stream signatures match"
}
```

Required gates:

- At least one input path.
- Exactly one probe per input path.
- Exactly one SHA256 per input path.
- Valid SHA256 hex for every input.
- Storage-root path safety for every clip.
- Stream-copy compatibility across the first video/audio stream signature:
  - video stream count;
  - audio stream count;
  - video codec;
  - width/height;
  - pixel format;
  - frame rate;
  - time base;
  - first audio codec, sample rate, and channel layout.

If probe signatures differ, stream-copy concat is rejected and normalization should be selected instead. The manifest builder does not execute FFmpeg.

## Normalization Builders

### `normalize_delivery_h264_v1`

Builder: `FFmpegService.build_normalize_delivery_h264_command(...)`

Argv shape:

```json
[
  "ffmpeg", "-y", "-i", "<safe_input>",
  "-c:v", "libx264", "-pix_fmt", "yuv420p",
  "-c:a", "aac", "-b:a", "192k",
  "-movflags", "+faststart",
  "<safe_output>"
]
```

### `normalize_mezzanine_prores_v1`

Builder: `FFmpegService.build_normalize_mezzanine_prores_command(...)`

Argv shape:

```json
[
  "ffmpeg", "-y", "-i", "<safe_input>",
  "-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le",
  "-c:a", "pcm_s16le",
  "<safe_output>"
]
```

Both normalization builders require a valid input SHA256 and safe input/output paths. They only build argv arrays.

## Exact Assembly Builder

Template: `assemble_exact_duration_h264_v1`

Planner/builder: `PostProductionService.build_assembly_plan(...)` followed by `PostProductionService.build_command(...)` for an already-approved plan.

Plan gates:

- At least one clip.
- Sum of clip timeline durations must match target duration within the service tolerance.
- Every clip must carry a supplied SHA256 or have an existing file from which the service can compute a SHA256.
- Output path is required before command-array construction.
- Template id is validated against the FFmpeg allowlist.
- All media paths are resolved inside the configured storage root.

Argv shape:

```json
[
  "ffmpeg", "-y",
  "-i", "<safe_clip_001>",
  "-i", "<safe_clip_002>",
  "-filter_complex", "[0:v]trim=0:<clip_001_duration>,setpts=PTS-STARTPTS,fps=<fps>,scale=<width>:<height>:force_original_aspect_ratio=decrease,pad=<width>:<height>:(ow-iw)/2:(oh-ih)/2,setsar=1[v0];[1:v]trim=0:<clip_002_duration>,setpts=PTS-STARTPTS,fps=<fps>,scale=<width>:<height>:force_original_aspect_ratio=decrease,pad=<width>:<height>:(ow-iw)/2:(oh-ih)/2,setsar=1[v1];[v0][v1]concat=n=<clip_count>:v=1:a=0[vout]",
  "-map", "[vout]",
  "-t", "<target_duration>",
  "-r", "<fps>",
  "-c:v", "libx264",
  "-pix_fmt", "yuv420p",
  "-movflags", "+faststart",
  "<safe_output>"
]
```

This is a deterministic video assembly argv builder for reviewed clips. It is not a raw command string.

## Audio Mux Builder

Template: `audio_mux_v1`

Builder: `FFmpegService.build_audio_mux_command(...)`

Argv shape:

```json
[
  "ffmpeg", "-y",
  "-i", "<safe_video>",
  "-i", "<safe_audio>",
  "-map", "0:v:0",
  "-map", "1:a:0",
  "-c:v", "copy",
  "-c:a", "aac", "-b:a", "192k",
  "-shortest",
  "<safe_output>"
]
```

Gates: valid video SHA256, valid audio SHA256, and safe input/output paths. The builder returns data only.

## Captions Mux Builder

Template: `captions_srt_mux_v1`

Builder: `FFmpegService.build_captions_srt_mux_command(...)`

Argv shape:

```json
[
  "ffmpeg", "-y",
  "-i", "<safe_video>",
  "-i", "<safe_captions.srt>",
  "-c:v", "copy",
  "-c:a", "copy",
  "-c:s", "mov_text",
  "<safe_output>"
]
```

Gates: valid video SHA256, valid captions SHA256, `.srt` captions suffix, and safe input/output paths. This M5 allowlist documents soft-caption muxing; hard-burn subtitles are intentionally not represented as an allowlisted M5 builder here.

## Loudness Builder

Template: `audio_loudness_normalize_v1`

Builder: `FFmpegService.build_audio_loudness_normalize_command(...)`

Argv shape:

```json
[
  "ffmpeg", "-y",
  "-i", "<safe_input>",
  "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
  "-c:v", "copy",
  "-c:a", "aac", "-b:a", "192k",
  "<safe_output>"
]
```

Gates: valid input SHA256 and safe input/output paths. This reflects the current builder; a two-pass measured loudness workflow would require a separate future allowlisted builder and validation story.

## Decode Validation Builder

Template: `decode_validate_v1`

Builder: `FFmpegService.build_decode_validate_command(...)`

Argv shape:

```json
[
  "ffmpeg", "-v", "error",
  "-i", "<safe_input>",
  "-f", "null", "NUL"
]
```

Gates: valid input SHA256 and safe input path. This builder constructs a decode-validation argv array; it does not itself submit execution.

## Timing / Conform Builder

Template: `conform_timing_h264_v1`

Builder: `FFmpegService.build_conform_timing_h264_command(...)`

Argv shape:

```json
[
  "ffmpeg", "-y",
  "-i", "<safe_input>",
  "-vf", "trim=0:<target_duration>,setpts=PTS-STARTPTS,fps=<fps>,scale=<width>:<height>:force_original_aspect_ratio=decrease,pad=<width>:<height>:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p",
  "-t", "<target_duration>",
  "-r", "<fps>",
  "-c:v", "libx264", "-preset", "medium", "-crf", "18",
  "-c:a", "aac", "-b:a", "192k",
  "-movflags", "+faststart",
  "<safe_output>"
]
```

Gates: valid input SHA256, safe input/output paths, and positive finite duration/fps/width/height values.

## Delivery Packaging Builder

Template: `delivery_package_mp4_faststart_v1`

Builder: `FFmpegService.build_delivery_package_mp4_faststart_command(...)`

Argv shape:

```json
[
  "ffmpeg", "-y",
  "-i", "<safe_input>",
  "-map", "0:v:0",
  "-map", "0:a:0?",
  "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
  "-c:a", "aac", "-b:a", "192k",
  "-movflags", "+faststart",
  "-f", "mp4",
  "<safe_output.mp4>"
]
```

Gates: valid input SHA256, safe input/output paths, and `.mp4` output suffix.

## Transition Crossfade Builder

Template: `transition_crossfade_h264_v1`

Builder: `FFmpegService.build_transition_crossfade_h264_command(...)`

Argv shape:

```json
[
  "ffmpeg", "-y",
  "-i", "<safe_first_video>",
  "-i", "<safe_second_video>",
  "-filter_complex", "[0:v]fps=<fps>,scale=<width>:<height>:force_original_aspect_ratio=decrease,pad=<width>:<height>:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p[v0];[1:v]fps=<fps>,scale=<width>:<height>:force_original_aspect_ratio=decrease,pad=<width>:<height>:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p[v1];[v0][v1]xfade=transition=fade:duration=<transition_duration>:offset=<transition_offset>,format=yuv420p[v]",
  "-map", "[v]",
  "-an",
  "-r", "<fps>",
  "-c:v", "libx264", "-preset", "medium", "-crf", "18",
  "-movflags", "+faststart",
  "<safe_output>"
]
```

Gates: valid SHA256 values for both videos, safe paths, and positive finite transition duration, transition offset, fps, width, and height. The current builder produces a video-only crossfade output.

## Validation Expectations for Future Execution Work

These checks describe what an executor or reviewer should validate before any future execution path is approved. They are not evidence that execution has happened.

- Manifest/plan records include template id, structured argv array or manifest text, input paths, input SHA256 values, output path when applicable, and `execution_submitted=false` until a separate executor submits work.
- Stream-copy concat has compatible stored probes before any `-c copy` assembly is considered.
- Output validation should include duration tolerance, expected stream count, resolution/fps/pixel format, audio/caption presence when required, full decode validation, output SHA256, and saved probe JSON.
- GPU encoding remains out of scope for this M5 checkpoint and must not overlap with diffusion generation unless separately benchmarked and approved.

## Safety Attestation for This Documentation Checkpoint

This file was updated as documentation only. No source code was edited. No FFmpeg, ffprobe, ComfyUI, GPU job, render, benchmark, or media assembly was run for this checkpoint.
