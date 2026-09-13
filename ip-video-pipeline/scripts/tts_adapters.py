"""Selected-provider TTS. No automatic provider fallback or paid retries."""
import asyncio
import json
import os
import shutil
import urllib.request
import wave
from pathlib import Path
from pipeline import paths, read, save, require, normalize, digest, wav_info, run


def minimax(text, model, voice, speed, target, attempt, timeout):
    key = os.environ.get('MINIMAX_API_KEY')
    require(key, 'Set MINIMAX_API_KEY in the execution environment; do not put it in project.json')
    require(len(text) < 10000, 'MiniMax HTTP requires fewer than 10000 characters; choose a full-text route')
    require(model and voice, 'MiniMax requires an explicitly selected model and voice ID')
    require(not attempt.exists(), 'Prior paid request exists; inspect its status before any new submission')
    payload = {'model': model, 'text': text, 'stream': False, 'output_format': 'hex',
        'language_boost': 'auto', 'voice_setting': {'voice_id': voice, 'speed': speed, 'vol': 1, 'pitch': 0},
        'audio_setting': {'sample_rate': 32000, 'bitrate': 128000, 'format': 'mp3', 'channel': 1}}
    req = urllib.request.Request('https://api.minimax.io/v1/t2a_v2',
        data=json.dumps(payload).encode(), headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}, method='POST')
    record = {'provider': 'minimax', 'model': model, 'voice': voice, 'status': 'submitted-or-unknown'}
    save(attempt, record)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.load(response)
        code = result.get('base_resp', {}).get('status_code')
        record.update(trace_id=result.get('trace_id'), status_code=code)
        require(code == 0, 'MiniMax rejected the request; inspect the recorded status code')
        data = result.get('data') or {}
        require(data.get('status') == 2, 'MiniMax did not return completed audio')
        audio = bytes.fromhex(data.get('audio') or '')
        require(audio, 'MiniMax returned empty audio')
        with target.open('xb') as f: f.write(audio)
        record['status'] = 'audio-received'
        save(attempt, record)
        return {'trace_id': record.get('trace_id'), 'endpoint': 'https://api.minimax.io/v1/t2a_v2'}
    except Exception:
        save(attempt, record)
        raise ValueError('MiniMax request did not finish locally. Inspect audio/provider-attempt.json and provider usage/status; no automatic retry.') from None


def render(a):
    root, script, wav = paths(a.project)
    cfg = read(root / 'project.json')
    selected = cfg.get('tts', {})
    provider = getattr(a, 'provider', None) or selected.get('provider')
    require(provider in ('edge', 'piper', 'minimax', 'import'),
            'Select a TTS route first: --provider edge|piper|minimax|import; see references/providers.md')
    require(shutil.which('ffmpeg'), 'FFmpeg is required before generating audio')
    require(a.timeout > 0, 'Timeout must be positive')
    text = script.read_text(encoding='utf-8').strip()
    require(normalize(text), 'Narration is empty')
    require(not wav.exists() and not any((root / 'audio').glob('tts-source.*')),
            'Audio exists; preserve it and choose a new version/project')
    # Do not reuse another provider's voice/model when switching via CLI.
    chosen = selected if provider == selected.get('provider') else {}
    voice = a.voice or chosen.get('voice')
    model = getattr(a, 'model', None) or chosen.get('model')
    speed = getattr(a, 'speed', None)
    speed = speed if speed is not None else chosen.get('speed', 1.0)
    require(isinstance(speed, (int, float)) and 0.5 <= speed <= 2.0, 'Speed must be between 0.5 and 2')
    source = root / ('audio/tts-source.mp3' if provider in ('edge', 'minimax') else 'audio/tts-source.wav')
    extra = {}
    if provider == 'edge':
        require(speed == 1, 'Use --rate for Edge; --speed is for Piper/MiniMax')
        import edge_tts
        voice = voice or 'zh-CN-XiaoyiNeural'
        rate = a.rate or chosen.get('rate', '+0%')
        async def generate():
            await asyncio.wait_for(edge_tts.Communicate(text, voice, rate=rate).save(str(source)), timeout=a.timeout)
        asyncio.run(generate())
        extra['rate'] = rate
    elif provider == 'minimax':
        require(not a.rate, 'Use --speed for MiniMax, not --rate')
        extra = minimax(text, model, voice, speed, source, root / 'audio/provider-attempt.json', a.timeout)
    elif provider == 'piper':
        require(not a.rate and not voice, 'Piper selects its voice with --model; use --speed for rate')
        require(model, 'Piper requires --model with a downloaded ONNX voice')
        model_path = Path(model).expanduser()
        if not model_path.is_absolute(): model_path = root / model_path
        require(model_path.is_file() and Path(str(model_path) + '.json').is_file(), 'Piper needs both ONNX and adjacent .onnx.json voice configuration')
        from piper import PiperVoice, SynthesisConfig
        engine = PiperVoice.load(str(model_path))
        with wave.open(str(source), 'wb') as out:
            engine.synthesize_wav(text, out, syn_config=SynthesisConfig(length_scale=1 / speed))
        extra['model_sha256'] = digest(model_path)
    else:
        require(not a.rate and speed == 1, 'Import preserves speech timing; do not pass rate/speed')
        require(getattr(a, 'input', None), 'Import requires --input with an existing full narration')
        original = Path(a.input).expanduser().resolve()
        require(original.is_file(), 'Imported audio not found')
        source = root / ('audio/tts-source' + original.suffix.lower())
        require(source != original, 'Import from an external candidate; do not overwrite a source')
        shutil.copyfile(original, source)
        extra['source_sha256'] = digest(original)
    run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', source, '-ar', '44100', '-ac', '1', '-c:a', 'pcm_s16le', wav])
    info = wav_info(wav)
    require(info['sample_count'] > 0, 'Generated audio is empty')
    receipt = {'provider': provider, 'voice': voice, 'model': model, 'speed': speed, **extra,
        'text_verification': 'pending-listening', 'source_path': source.relative_to(root).as_posix(),
        'script_sha256': digest(script), 'audio_sha256': digest(wav), **info}
    save(root / 'audio/tts-receipt.json', receipt)
    cfg['tts'] = {**chosen, 'provider': provider, 'voice': voice, 'model': model, 'speed': speed}
    if provider == 'edge': cfg['tts']['rate'] = extra['rate']
    save(root / 'project.json', cfg)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
