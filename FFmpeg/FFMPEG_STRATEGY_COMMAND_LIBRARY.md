# FFmpeg Strategy and Command Library

Goal: stitch many generated clips with minimal quality loss and maximum recoverability. Use stream copy only when probe data proves compatibility.

## Assembly Matrix

| Assembly Scenario | FFmpeg Method | Re-encode Required? | Pros | Cons | Command Template |
|---|---|---|---|---|---|
| All clips identical codec/resolution/fps/timebase/audio layout | concat demuxer + stream copy | No | Fast, no generational loss | Strict compatibility | `ffmpeg -f concat -safe 0 -i concat.txt -c copy stitched.mp4` |
| Clips differ in fps/resolution/pixel format | Normalize then concat | Yes during normalization | Predictable final assembly | Disk/time cost | See mezzanine command |
| Need crossfades | concat/xfade filter graph | Yes | Smooth transitions | Complex for 180+ clips | Generate segments or use scripted filter graph |
| Add voiceover/music | Mux audio after video assembly | Audio encode usually yes | Keeps video copy if already final | Sync must be managed | `-map 0:v -map 1:a -shortest` |
| Burn subtitles | subtitles filter | Yes | Universal playback | Quality loss from re-encode | `-vf subtitles=...` |
| Soft subtitles | `mov_text` in MP4 | No video re-encode | Editable/disableable | Player support varies | `-c:s mov_text` |

## Probe Inputs

```powershell
ffprobe -v quiet -print_format json -show_format -show_streams input.mp4 > input.probe.json
```

Store probe JSON and reject stream-copy concat unless codec, dimensions, pixel format, fps, time base, audio sample rate, channel layout, and stream counts are compatible.

## Lossless Concat When All Clips Match

`concat.txt`:

```text
file 'clip_001.mp4'
file 'clip_002.mp4'
file 'clip_003.mp4'
```

```powershell
ffmpeg -hide_banner -f concat -safe 0 -i concat.txt -c copy stitched.mp4
```

## Normalize to Mezzanine

Use a high-quality mezzanine when clips differ or when repeated edits are expected.

```powershell
ffmpeg -i input.mp4 -vf "fps=30,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:-1:-1,format=yuv422p10le" -c:v prores_ks -profile:v 3 -c:a pcm_s24le -ar 48000 normalized.mov
```

Local test required: validate Windows FFmpeg build support, disk cost, decode speed, and target editor/player compatibility.

## Normalize to Delivery-Compatible MP4

```powershell
ffmpeg -i input.mp4 -vf "fps=30,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:-1:-1,format=yuv420p" -c:v libx264 -crf 18 -preset medium -c:a aac -b:a 192k -ar 48000 normalized.mp4
```

## Mux Voiceover or Final Mix

```powershell
ffmpeg -i stitched_video.mp4 -i final_mix.wav -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -shortest with_audio.mp4
```

## Loudness Normalization

Pass 1:

```powershell
ffmpeg -i with_audio.mp4 -af "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json" -f null NUL
```

Pass 2:

```powershell
ffmpeg -i with_audio.mp4 -af "loudnorm=I=-16:TP=-1.5:LRA=11:measured_I=<I>:measured_TP=<TP>:measured_LRA=<LRA>:measured_thresh=<THRESH>:offset=<OFFSET>:linear=true:print_format=summary" -c:v copy -c:a aac -b:a 192k final_loudnorm.mp4
```

## Subtitles

Hard burn:

```powershell
ffmpeg -i final_loudnorm.mp4 -vf "subtitles=captions.srt:force_style='FontName=Arial,Fontsize=28,Outline=2'" -c:v libx264 -crf 18 -preset medium -c:a copy final_burned.mp4
```

Soft MP4 subtitles:

```powershell
ffmpeg -i final_loudnorm.mp4 -i captions.srt -map 0:v:0 -map 0:a:0 -map 1:0 -c:v copy -c:a copy -c:s mov_text final_soft_subs.mp4
```

## Final Encode

H.264 compatibility:

```powershell
ffmpeg -i master.mov -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p -c:a aac -b:a 192k final_h264.mp4
```

H.265 smaller files:

```powershell
ffmpeg -i master.mov -c:v libx265 -crf 22 -preset medium -pix_fmt yuv420p10le -c:a aac -b:a 192k final_h265.mp4
```

GPU encoding can be tested later, but do not run NVENC concurrently with active diffusion generation unless telemetry proves no interference.

## Validate Output

```powershell
ffprobe -v quiet -print_format json -show_format -show_streams final.mp4 > final.probe.json
ffmpeg -v error -i final.mp4 -f null NUL
```

Validation checks:

- Duration within tolerance.
- Expected stream count.
- Expected resolution/fps/pixel format.
- Audio present if required.
- No decode errors.
- Output SHA256 recorded.
