from __future__ import annotations

from time import perf_counter
from typing import List, Optional

import typer


app = typer.Typer(add_completion=False, help="ASR benchmarking for multiple models/params over given audio files")


def _load_model(name: str, device: Optional[str]):
    from faster_whisper import WhisperModel  # type: ignore

    return WhisperModel(name, device=device)


def _transcribe_one(model, audio_path: str, *, beam: int, vad: bool, word_ts: bool, language: str):
    segments, info = model.transcribe(
        audio_path,
        beam_size=beam,
        vad_filter=vad,
        word_timestamps=word_ts,
        language=language,
    )
    texts = []
    confidences = []
    for s in segments:
        texts.append(s.text)
        if getattr(s, "avg_logprob", None) is not None:
            confidences.append(float(s.avg_logprob))
    text = " ".join(t.strip() for t in texts).strip()
    avg_conf = (sum(confidences) / len(confidences)) if confidences else None
    return text, avg_conf


@app.command("run")
def run(
    path: List[str] = typer.Option(..., "--path", help="Audio file path (repeat for multiple)"),
    models: str = typer.Option("small,medium", help="Comma-separated model names"),
    beam: int = typer.Option(5, help="Beam size"),
    vad: bool = typer.Option(False, help="Enable VAD filter"),
    word_ts: bool = typer.Option(False, help="Enable word timestamps"),
    language: str = typer.Option("ar", help="Transcription language"),
    device: Optional[str] = typer.Option(None, help="Device override: cpu|cuda|mps"),
    refs: Optional[List[str]] = typer.Option(None, help="Reference transcripts (same order as --path) for WER/CER"),
) -> None:
    model_names = [m.strip() for m in models.split(",") if m.strip()]
    for mname in model_names:
        typer.echo(f"\n=== Model: {mname} | beam={beam} | vad={int(vad)} | word_ts={int(word_ts)} | lang={language} ===")
        model = _load_model(mname, device)
        for i, p in enumerate(path):
            t0 = perf_counter()
            text, avg_conf = _transcribe_one(model, p, beam=beam, vad=vad, word_ts=word_ts, language=language)
            dt = int((perf_counter() - t0) * 1000)
            wer = cer = None
            if refs and i < len(refs) and refs[i]:
                try:
                    from jiwer import wer as _wer, cer as _cer  # type: ignore
                    wer = _wer(refs[i], text)
                    cer = _cer(refs[i], text)
                except Exception:
                    pass
            metrics = f"ms={dt} avg_conf={avg_conf}"
            if wer is not None:
                metrics += f" wer={wer:.3f} cer={cer:.3f}"
            typer.echo(f"\n--- File: {p}\n{metrics}\n{text}\n")


def main() -> None:
    app()


if __name__ == "__main__":
    main()


