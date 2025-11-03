Input: { url }
Output:
{
  cleaned_text: string,           # <= 8000 chars
  text_snippet: string,           # <= 3000 chars (prefix of cleaned_text)
  lang: "en"|"es"|"unknown",
  key_sentences: string[],        # 3..5
  hash: "sha1:xxxxxxxx...",
  flags: { truncated: bool, low_lang_conf: bool, sanitized: bool, boilerplate_removed: bool }
}
Determinism requirements:
- Same input -> same output across runs (no randomness).
- Hash computed over normalized pre-translation text.
