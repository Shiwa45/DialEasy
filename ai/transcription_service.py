# ai/transcription_service.py
# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 — AI Call Transcription Service
# Uses OpenAI Whisper API for transcription.
# Uses GPT-4o-mini for sentiment, summary, and coaching analysis.
# Called after call recording upload (signal or management command).
# ─────────────────────────────────────────────────────────────────────────────

import json
import logging
import os
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
WHISPER_URL = 'https://api.openai.com/v1/audio/transcriptions'
CHAT_URL = 'https://api.openai.com/v1/chat/completions'

FILLER_WORDS = {
    'um', 'uh', 'hmm', 'basically', 'you know', 'like', 'sort of',
    'kind of', 'actually', 'literally', 'honestly', 'to be honest',
    'right', 'so', 'yeah', 'okay so',
}


def _openai_headers() -> dict:
    return {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'Content-Type': 'application/json',
    }


def _count_filler_words(text: str) -> int:
    text_lower = text.lower()
    count = 0
    for word in FILLER_WORDS:
        count += text_lower.count(word)
    return count


# ─── Step 1: Transcribe ──────────────────────────────────────────────────────

def transcribe_recording(call_log) -> dict:
    """
    Send the call recording to Whisper API for transcription.
    Returns a dict with: full_text, segments, language, duration_seconds.
    Raises on failure.
    """
    if not OPENAI_API_KEY:
        raise ValueError('OPENAI_API_KEY not set in environment.')

    recording_path = call_log.recording.path
    if not os.path.exists(recording_path):
        raise FileNotFoundError(f'Recording file not found: {recording_path}')

    with open(recording_path, 'rb') as audio_file:
        files = {
            'file': (os.path.basename(recording_path), audio_file, 'audio/m4a'),
            'model': (None, 'whisper-1'),
            'response_format': (None, 'verbose_json'),
            'timestamp_granularities[]': (None, 'segment'),
        }
        resp = requests.post(
            WHISPER_URL,
            headers={'Authorization': f'Bearer {OPENAI_API_KEY}'},
            files=files,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

    segments = []
    for seg in data.get('segments', []):
        segments.append({
            'start': round(seg.get('start', 0), 2),
            'end': round(seg.get('end', 0), 2),
            'text': seg.get('text', '').strip(),
            'speaker': 'unknown',  # Diarization requires separate service
        })

    return {
        'full_text': data.get('text', ''),
        'segments': segments,
        'language': data.get('language', 'hi'),
        'duration_seconds': int(data.get('duration', 0)),
    }


# ─── Step 2: Analyse ─────────────────────────────────────────────────────────

ANALYSIS_PROMPT = """
You are a CRM call analysis AI. Analyse this call transcript and return ONLY valid JSON with these exact keys:

{
  "summary": "2-3 sentence plain-English summary of what happened in the call",
  "overall_sentiment": "positive|neutral|negative",
  "sentiment_score": <float between -1.0 and 1.0>,
  "customer_intent": "short phrase describing what the customer wants",
  "objections_detected": ["objection 1", "objection 2"],
  "agent_talk_ratio": <float 0.0-1.0 estimating fraction of time agent spoke>,
  "best_moment": "1 sentence describing best thing agent did",
  "improvement_area": "1 sentence describing main area to improve"
}

Do not include markdown, code blocks, or any text outside the JSON object.

Transcript:
{transcript}
"""


def analyse_transcript(transcript_text: str) -> dict:
    """
    Send transcript to GPT-4o-mini for sentiment, intent, and coaching analysis.
    Returns parsed dict or raises on failure.
    """
    if not OPENAI_API_KEY:
        raise ValueError('OPENAI_API_KEY not set.')

    prompt = ANALYSIS_PROMPT.replace('{transcript}', transcript_text[:8000])

    payload = {
        'model': 'gpt-4o-mini',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.2,
        'max_tokens': 600,
        'response_format': {'type': 'json_object'},
    }
    resp = requests.post(CHAT_URL, headers=_openai_headers(), json=payload, timeout=30)
    resp.raise_for_status()

    content = resp.json()['choices'][0]['message']['content']
    return json.loads(content)


# ─── Step 3: Orchestrate ─────────────────────────────────────────────────────

def process_call_recording(call_log_id: int) -> bool:
    """
    Full AI pipeline for one call recording:
      1. Transcribe via Whisper
      2. Analyse via GPT-4o-mini
      3. Save CallTranscript + CallSentiment
      4. Add summary to LeadActivity

    Returns True on success, False on failure.
    Call this from the management command or a Celery task.
    """
    from leads.models import CallLog, LeadActivity
    from ai.models import CallTranscript, CallSentiment

    try:
        call_log = CallLog.objects.select_related('lead', 'agent').get(pk=call_log_id)
    except CallLog.DoesNotExist:
        logger.error('CallLog %d not found.', call_log_id)
        return False

    if not call_log.recording:
        logger.warning('CallLog %d has no recording — skipping.', call_log_id)
        return False

    # ── Get or create transcript record ──────────────────────────────────────
    transcript, _ = CallTranscript.objects.get_or_create(call_log=call_log)
    if transcript.status == 'done':
        logger.info('CallLog %d already transcribed — skipping.', call_log_id)
        return True

    transcript.status = 'processing'
    transcript.save(update_fields=['status'])

    try:
        # ── Transcription ─────────────────────────────────────────────────────
        logger.info('Transcribing CallLog %d...', call_log_id)
        trans_result = transcribe_recording(call_log)

        transcript.full_text = trans_result['full_text']
        transcript.segments = trans_result['segments']
        transcript.language = trans_result['language']
        transcript.duration_seconds = trans_result['duration_seconds']

        # ── Analysis ──────────────────────────────────────────────────────────
        logger.info('Analysing transcript for CallLog %d...', call_log_id)
        analysis = analyse_transcript(trans_result['full_text'])

        transcript.summary = analysis.get('summary', '')
        transcript.status = 'done'
        transcript.save()

        # ── Sentiment ─────────────────────────────────────────────────────────
        sentiment_score = float(analysis.get('sentiment_score', 0.0))
        filler_count = _count_filler_words(trans_result['full_text'])

        CallSentiment.objects.update_or_create(
            transcript=transcript,
            defaults={
                'overall_sentiment': analysis.get('overall_sentiment', 'neutral'),
                'sentiment_score': max(-1.0, min(1.0, sentiment_score)),
                'customer_intent': analysis.get('customer_intent', ''),
                'objections_detected': analysis.get('objections_detected', []),
                'agent_talk_ratio': analysis.get('agent_talk_ratio'),
                'filler_word_count': filler_count,
                'best_moment': analysis.get('best_moment', ''),
                'improvement_area': analysis.get('improvement_area', ''),
            }
        )

        # ── Lead Activity ─────────────────────────────────────────────────────
        if transcript.summary:
            LeadActivity.objects.create(
                lead=call_log.lead,
                actor=call_log.agent,
                activity_type='call_logged',
                description=f'AI call summary: {transcript.summary}',
                metadata={
                    'call_log_id': call_log_id,
                    'sentiment': analysis.get('overall_sentiment'),
                    'intent': analysis.get('customer_intent'),
                    'transcript_id': transcript.id,
                }
            )

        logger.info('CallLog %d processed successfully.', call_log_id)
        return True

    except Exception as e:
        transcript.status = 'failed'
        transcript.error_message = str(e)
        transcript.save(update_fields=['status', 'error_message'])
        logger.error('AI processing failed for CallLog %d: %s', call_log_id, e)
        return False
