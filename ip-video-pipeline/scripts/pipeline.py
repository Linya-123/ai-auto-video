#!/usr/bin/env python3
"""Portable helpers for an agent-driven IP video workflow. Python 3.10+."""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
import sys
import wave
from pathlib import Path


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def save(p, value):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(p)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(args):
    subprocess.run([str(x) for x in args], check=True)


def digest(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def normalize(s):
    return ''.join(c.lower() for c in s if c.isalnum())


def wav_info(p):
    with wave.open(str(p)) as w:
        rate, frames = w.getframerate(), w.getnframes()
        require(w.getcomptype() == 'NONE', 'WAV must be uncompressed PCM')
        return {'sample_rate': rate, 'sample_count': frames,
                'channels': w.getnchannels(), 'duration_ms': round(frames * 1000 / rate)}


def stamp(ms):
    return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}'


def paths(project):
    root = Path(project).resolve()
    return root, root / 'script/narration.txt', root / 'audio/vo-full.wav'


def doctor(_):
    bins = {n: shutil.which(n) for n in ('ffmpeg', 'ffprobe', 'node', 'npx')}
    packages = {n: importlib.util.find_spec(n) is not None for n in ('edge_tts', 'stable_whisper')}
    node_major = None
    if bins['node']:
        node_major = int(subprocess.check_output([bins['node'], '--version'], text=True).strip().lstrip('v').split('.')[0])
    report = {'python': sys.version.split()[0], 'executables': bins,
              'python_packages': packages, 'node_major': node_major,
              'local_helpers_ready': bool(bins['ffmpeg'] and bins['ffprobe']),
              'hyperframes_runtime_ready': node_major is not None and node_major >= 22,
              'note': 'Does not verify image tools, model downloads, network services or HyperFrames installation.'}
    print(json.dumps(report, ensure_ascii=False, indent=2))


def init(a):
    root = Path(a.project).resolve()
    require(not (root / 'project.json').exists(), 'Project exists; resume instead of reinitializing')
    for d in ('identity', 'script', 'audio', 'shots', 'composition', 'deliverables', 'reports'):
        (root / d).mkdir(parents=True, exist_ok=True)
    save(root / 'project.json', {'version': 1, 'topic': a.topic, 'mode': 'auto',
        'width': 1920, 'height': 1080, 'fps': 30, 'language': 'zh',
        'target_duration_seconds': 75, 'tts': {'provider': None, 'voice': None},
        'generation': {'image': {'provider': None}, 'video': {'provider': None}},
        'stages': {}, 'decisions': [], 'max_generation_retries': 1})
    (root / 'STATUS.md').write_text('# 制作状态\n\n已初始化目录。下一步：核对选题和现有 IP/文案/音频，完成首个缺失阶段。\n', encoding='utf-8')
    print(root)


def tts(a):
    from tts_adapters import render
    render(a)


def align(a):
    root, script, wav = paths(a.project)
    require(not (root / 'audio/alignment-acoustic.json').exists(), 'Alignment exists; use a new version or inspect existing result')
    receipt_path = root / 'audio/tts-receipt.json'
    if receipt_path.exists():
        receipt = read(receipt_path)
        require(receipt['script_sha256'] == digest(script) and receipt['audio_sha256'] == digest(wav),
                'TTS source changed; regenerate audio before alignment')
    import stable_whisper
    model = stable_whisper.load_model(a.model)
    result = model.align(str(wav), script.read_text(encoding='utf-8').strip(), language=a.language)
    require(result is not None, 'Aligner returned no result')
    raw_path = root / 'audio/forced-words.json'
    raw_version = 2
    while raw_path.exists():
        raw_path = root / f'audio/forced-words-v{raw_version:02}.json'
        raw_version += 1
    result.save_as_json(str(raw_path))
    raw = read(raw_path)
    words = [w for seg in raw['segments'] for w in seg.get('words', []) if w.get('word', '').strip()]
    require(words, 'Aligner returned no word timestamps')
    source = script.read_text(encoding='utf-8')
    require(normalize(''.join(w['word'] for w in words)) == normalize(source),
            f'Aligned text differs from narration; inspect {raw_path.name}, do not fabricate timestamps')
    # Recover the exact original punctuation/spacing rather than substituting ASR text.
    positions = [i for i, c in enumerate(source) if c.isalnum()]
    count, start_pos, group, rows = 0, 0, [], []
    for i, w in enumerate(words):
        count += len(normalize(w['word']))
        group.append(w)
        group_text = ''.join(x['word'] for x in group)
        boundary = any(c in w['word'] for c in '。！？.!?') or (len(normalize(group_text)) >= 5 and any(c in w['word'] for c in '，；,;')) or i == len(words)-1
        if boundary:
            end_pos = positions[count] if count < len(positions) else len(source)
            rows.append({'text': source[start_pos:end_pos],
                         'acoustic_start_ms': round(group[0]['start'] * 1000),
                         'acoustic_end_ms': round(group[-1]['end'] * 1000)})
            start_pos, group = end_pos, []
    save(root / 'audio/alignment-acoustic.json', rows)
    save(root / 'audio/alignment-provenance.json', {'method': 'stable-ts forced alignment',
         'model': a.model, 'language': a.language, 'raw_path': raw_path.relative_to(root).as_posix(),
         'script_sha256': digest(script), 'audio_sha256': digest(wav)})
    timeline(a)


def timeline(a):
    root, script, wav = paths(a.project)
    info = wav_info(wav)
    rows = read(root / 'audio/alignment-acoustic.json')
    require(isinstance(rows, list) and bool(rows), 'Acoustic rows must be a nonempty list')
    provenance = read(root / 'audio/alignment-provenance.json')
    require(provenance['script_sha256'] == digest(script) and provenance['audio_sha256'] == digest(wav),
            'Acoustic alignment is stale for this script/audio')
    source = script.read_text(encoding='utf-8')
    require(''.join(r['text'] for r in rows) == source, 'Acoustic text must reproduce narration exactly, including punctuation/spacing')
    end = 0
    for r in rows:
        s, e = r['acoustic_start_ms'], r['acoustic_end_ms']
        require(type(s) is int and type(e) is int, 'Acoustic times must be integer milliseconds')
        require(end <= s < e <= info['duration_ms'], 'Acoustic timing overlaps, reverses, or exceeds audio; review actual alignment')
        require(bool(normalize(r['text'])), 'Empty acoustic phrase')
        end = e
    boundaries = [0] + [round((x['acoustic_end_ms'] + y['acoustic_start_ms']) / 2) for x, y in zip(rows, rows[1:])] + [info['duration_ms']]
    result = [{'id': f'P{i+1:03}', 'start_ms': boundaries[i], 'end_ms': boundaries[i+1], **r} for i, r in enumerate(rows)]
    require(all(r['end_ms'] > r['start_ms'] for r in result), 'Display interval has zero duration')
    save(root / 'audio/vo-align.json', result)
    save(root / 'audio/timeline-meta.json', {**info, 'script_sha256': digest(script), 'audio_sha256': digest(wav),
        'acoustic_sha256': digest(root / 'audio/alignment-acoustic.json'),
        'timeline_sha256': digest(root / 'audio/vo-align.json'),
        'segment_count': len(result), 'last_end_ms': result[-1]['end_ms'],
        'review_phrase_ids': [r['id'] for r in result if not 5 <= len(normalize(r['text'])) <= 15]})
    (root / 'audio/vo-align.txt').write_text(''.join(f"[{r['start_ms']}ms-{r['end_ms']}ms] {r['text'].strip()}\n" for r in result), encoding='utf-8')
    (root / 'audio/vo-full.srt').write_text('\n\n'.join(f"{i+1}\n{stamp(r['start_ms'])} --> {stamp(r['end_ms'])}\n{r['text'].strip()}" for i, r in enumerate(result))+'\n', encoding='utf-8')
    print(json.dumps(read(root / 'audio/timeline-meta.json'), ensure_ascii=False, indent=2))


def check_project(project, storyboard=False):
    root, script, wav = paths(project)
    info, meta = wav_info(wav), read(root / 'audio/timeline-meta.json')
    require(meta['script_sha256'] == digest(script) and meta['audio_sha256'] == digest(wav), 'Stale timeline: script/audio changed')
    require(meta['acoustic_sha256'] == digest(root / 'audio/alignment-acoustic.json'), 'Acoustic data changed; regenerate timeline')
    require(meta['timeline_sha256'] == digest(root / 'audio/vo-align.json'), 'Timeline edited; regenerate through timeline command')
    rows = read(root / 'audio/vo-align.json')
    require(rows and ''.join(r['text'] for r in rows) == script.read_text(encoding='utf-8'), 'Timeline text differs from script')
    previous = 0
    for r in rows:
        require(type(r['start_ms']) is int and type(r['end_ms']) is int, 'Integer ms required')
        require(r['start_ms'] == previous and r['end_ms'] > previous, 'Timeline gap/overlap/zero interval')
        previous = r['end_ms']
    require(previous == info['duration_ms'], 'Timeline does not cover full audio')
    if storyboard:
        board = read(root / 'storyboard.json')
        require(board['timeline_sha256'] == digest(root / 'audio/vo-align.json'), 'Storyboard uses stale timeline')
        shots = board['shots']
        require(bool(shots), 'Storyboard is empty')
        edges = {r['start_ms'] for r in rows} | {rows[-1]['end_ms']}
        previous = 0
        for i, s in enumerate(shots):
            require(s['id'] == f'S{i+1:03}', 'Shot IDs must be contiguous')
            require(s['start_ms'] == previous and s['end_ms'] > previous and s['end_ms'] in edges, 'Shot boundary invalid')
            require(s['roll'] in ('A', 'B'), 'roll must be A or B')
            require(s['type'] in ('人物', '场景', '真实素材', '信息图形', '文字动效'), 'Unknown shot type')
            expected = ''.join(r['text'] for r in rows if r['start_ms'] >= s['start_ms'] and r['end_ms'] <= s['end_ms'])
            require(s['text'] == expected, 'Shot text does not match its phrases')
            for key in ('intent', 'design', 'change', 'result', 'transition'):
                require(isinstance(s.get(key), str) and bool(s[key].strip()), f'Missing shot {key}')
            previous = s['end_ms']
        require(previous == info['duration_ms'], 'Storyboard does not cover audio')
    return rows, info


def validate(a):
    rows, info = check_project(a.project, a.storyboard)
    report = {'ok': True, **info, 'segment_count': len(rows), 'storyboard_checked': a.storyboard,
              'scope': 'Structural validation only; listen to alignment and inspect visuals separately.'}
    save(Path(a.project) / 'reports/timeline-validation.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def split(a):
    rows, info = check_project(a.project)
    root, _, wav = paths(a.project)
    target = root / 'audio/segments'
    require(not target.exists(), 'Segments exist; inspect/reuse them or choose a new project version')
    target.mkdir()
    manifest = []
    with wave.open(str(wav)) as src:
        params, previous = src.getparams(), 0
        for i, r in enumerate(rows):
            end = info['sample_count'] if i == len(rows)-1 else round(r['end_ms'] * info['sample_rate'] / 1000)
            require(end > previous, 'Empty segment')
            path = target / (r['id'] + '.wav')
            src.setpos(previous)
            with wave.open(str(path), 'wb') as out:
                out.setparams(params)
                out.writeframes(src.readframes(end - previous))
            manifest.append({'id': r['id'], 'path': path.relative_to(root).as_posix(),
                'start_sample': previous, 'end_sample': end, 'text': r['text']})
            previous = end
    save(root / 'audio/segments.json', {'audio_sha256': digest(wav), 'sample_rate': info['sample_rate'], 'segments': manifest})
    print(f'Split {len(rows)} clips; total {previous} samples; original narration remains unchanged.')


def verify_video(a):
    root, _, wav = paths(a.project)
    cfg, info = read(root / 'project.json'), wav_info(wav)
    media = Path(a.video).resolve()
    raw = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(media)], text=True))
    videos = [s for s in raw['streams'] if s['codec_type'] == 'video']
    audios = [s for s in raw['streams'] if s['codec_type'] == 'audio']
    require(bool(videos) and bool(audios), 'Output needs video and audio streams')
    v, audio = videos[0], audios[0]
    require((v['width'], v['height']) == (cfg['width'], cfg['height']), 'Resolution mismatch')
    n, d = map(int, v['avg_frame_rate'].split('/'))
    require(d and abs(n / d - cfg['fps']) < .02, 'Frame rate mismatch')
    actual_ms = float(raw['format']['duration']) * 1000
    require(math.isfinite(actual_ms) and abs(actual_ms - info['duration_ms']) <= max(100, 2000 / cfg['fps']), 'Output duration differs from narration')
    require(v['codec_name'] == 'h264' and audio['codec_name'] == 'aac', 'Expected H.264/AAC delivery')
    run(['ffmpeg', '-v', 'error', '-xerror', '-nostdin', '-i', media, '-f', 'null', '-'])
    report = {'ok': True, 'duration_ms': actual_ms, 'width': v['width'], 'height': v['height'],
              'fps': n / d, 'video_sha256': digest(media), 'decode_ok': True,
              'scope': 'Technical checks only, not visual/speech quality approval.'}
    save(root / 'reports/video-validation.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor').set_defaults(func=doctor)
    p = sub.add_parser('init'); p.add_argument('project'); p.add_argument('--topic', required=True); p.set_defaults(func=init)
    p = sub.add_parser('tts'); p.add_argument('project'); p.add_argument('--voice'); p.add_argument('--rate'); p.add_argument('--timeout', type=int, default=180); p.add_argument('--provider', choices=['edge', 'piper', 'minimax', 'import']); p.add_argument('--input'); p.add_argument('--model'); p.add_argument('--speed', type=float); p.set_defaults(func=tts)
    p = sub.add_parser('align'); p.add_argument('project'); p.add_argument('--model', default='large-v3'); p.add_argument('--language', default='zh'); p.set_defaults(func=align)
    for name, func in [('timeline', timeline), ('validate', validate), ('split', split)]:
        p = sub.add_parser(name); p.add_argument('project'); p.set_defaults(func=func)
        if name == 'validate': p.add_argument('--storyboard', action='store_true')
    p = sub.add_parser('verify-video'); p.add_argument('project'); p.add_argument('video'); p.set_defaults(func=verify_video)
    a = parser.parse_args()
    try:
        a.func(a)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError, ImportError, asyncio.TimeoutError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
