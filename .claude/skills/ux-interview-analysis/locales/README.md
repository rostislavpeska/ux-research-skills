# Locales

One file per language (`<ISO 639-1>.yaml`). Every fixed text in a deliverable — titles, speaker
labels, transcript markers, table headers — and the language hints for the transcription prompt
come from here. Scripts take `--lang <code>` and never hardcode a language.

## Add a language (e.g. German)

1. Copy `en.yaml` to `de.yaml`, keep every key, translate the values.
2. `prompt.*`: native filler words, false-start examples and non-speech markers — these shape the
   verbatim transcript, so use what a native transcriber would write.
3. Run the scripts with `--lang de`. No code change is needed; a missing key fails loudly.

## Language rule (see `scripts/doc_language.py`)

- All interviews in one language → documentation in that language.
- Interviews in several languages → ask the user, unless the study sets `doc_language`.
- Quotes are evidence: always verbatim in the spoken language, never translated. In a mixed study a
  quote may carry a gloss in the documentation language, marked as a translation.
