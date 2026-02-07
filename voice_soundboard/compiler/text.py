"""
Text Processing - Tokenization and normalization.

Converts raw text into TokenEvents with proper segmentation.
Handles abbreviations, numbers, and other TTS edge cases.
"""

from __future__ import annotations

import re
from typing import Iterator

from voice_soundboard.graph import TokenEvent


# Sentence-ending punctuation
SENTENCE_END = re.compile(r'([.!?]+)\s*')

# Clause separators (commas, semicolons, etc.)
CLAUSE_SEP = re.compile(r'([,;:—–-]+)\s*')

# Abbreviations that shouldn't end sentences
ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr",
    "st", "ave", "blvd", "rd",
    "inc", "ltd", "corp", "co",
    "vs", "etc", "eg", "ie",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
}

# Number words
ONES = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
TEENS = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
         "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def number_to_words(n: int) -> str:
    """Convert integer to words (0-999999)."""
    if n == 0:
        return "zero"
    if n < 0:
        return "negative " + number_to_words(-n)
    if n < 10:
        return ONES[n]
    if n < 20:
        return TEENS[n - 10]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if n < 1000:
        return ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + number_to_words(n % 100))
    if n < 1000000:
        return number_to_words(n // 1000) + " thousand" + ("" if n % 1000 == 0 else " " + number_to_words(n % 1000))
    return str(n)  # Fallback for large numbers


def normalize_text(text: str) -> str:
    """Normalize text for TTS.
    
    Expands:
    - Numbers: 123 -> one hundred twenty three
    - Currency: $50 -> fifty dollars
    - Abbreviations: Dr. -> Doctor
    - URLs: kept as-is (models handle them)
    """
    # Currency
    text = re.sub(r'\$(\d+)(?:\.(\d{2}))?', lambda m: _expand_currency(m), text)
    
    # Expand common abbreviations
    text = re.sub(r'\bDr\.\s', 'Doctor ', text)
    text = re.sub(r'\bMr\.\s', 'Mister ', text)
    text = re.sub(r'\bMrs\.\s', 'Missus ', text)
    text = re.sub(r'\bMs\.\s', 'Miss ', text)
    text = re.sub(r'\bProf\.\s', 'Professor ', text)
    
    # Numbers (standalone, not part of words)
    text = re.sub(r'\b(\d{1,6})\b', lambda m: number_to_words(int(m.group(1))), text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def _expand_currency(match: re.Match) -> str:
    """Expand $X.XX to words."""
    dollars = int(match.group(1))
    cents = match.group(2)
    
    result = number_to_words(dollars) + " dollar" + ("s" if dollars != 1 else "")
    
    if cents and int(cents) > 0:
        result += " and " + number_to_words(int(cents)) + " cent" + ("s" if int(cents) != 1 else "")
    
    return result


def tokenize(text: str, normalize: bool = True) -> list[TokenEvent]:
    """Convert text to TokenEvents.
    
    Segments text on sentence and clause boundaries for natural pacing.
    
    Args:
        text: Input text
        normalize: Whether to expand numbers/abbreviations (default True)
    
    Returns:
        List of TokenEvents ready for further compilation
    """
    if normalize:
        text = normalize_text(text)
    
    tokens = []
    
    # Split on sentences first
    sentences = _split_sentences(text)
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        # Split sentence into clauses
        clauses = _split_clauses(sentence)
        
        for i, clause in enumerate(clauses):
            clause = clause.strip()
            if not clause:
                continue
            
            # Determine pause based on position
            is_sentence_end = (i == len(clauses) - 1)
            
            # Sentence-ending gets longer pause
            if is_sentence_end and sentence[-1] in '.!?':
                pause = 0.3  # 300ms after sentence
            elif clause[-1] in ',;:':
                pause = 0.15  # 150ms after clause
            else:
                pause = 0.0
            
            tokens.append(TokenEvent(
                text=clause,
                pause_after=pause,
            ))
    
    return tokens


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences, respecting abbreviations."""
    result = []
    current = ""
    
    i = 0
    while i < len(text):
        char = text[i]
        current += char
        
        if char in '.!?':
            # Check if this is an abbreviation
            word_before = re.search(r'\b(\w+)\.$', current)
            if word_before and word_before.group(1).lower() in ABBREVIATIONS:
                # Not a sentence boundary
                i += 1
                continue
            
            # This is a sentence boundary
            result.append(current.strip())
            current = ""
        
        i += 1
    
    if current.strip():
        result.append(current.strip())
    
    return result


def _split_clauses(text: str) -> list[str]:
    """Split sentence into clauses on commas/semicolons."""
    parts = CLAUSE_SEP.split(text)
    
    # Reassemble with punctuation attached to preceding text
    result = []
    current = ""
    
    for part in parts:
        if CLAUSE_SEP.fullmatch(part):
            current += part
        else:
            if current:
                result.append(current)
            current = part
    
    if current:
        result.append(current)
    
    return result if result else [text]


def tokenize_streaming(text_iterator: Iterator[str]) -> Iterator[list[TokenEvent]]:
    """Tokenize incrementally for streaming synthesis.
    
    Yields token batches as they become safe to synthesize
    (i.e., at sentence/clause boundaries).
    
    Args:
        text_iterator: Iterator yielding text chunks
    
    Yields:
        Batches of TokenEvents ready for synthesis
    """
    buffer = ""
    
    for chunk in text_iterator:
        buffer += chunk
        
        # Find safe boundaries
        while True:
            # Look for sentence end
            match = SENTENCE_END.search(buffer)
            if match:
                # Found sentence boundary - yield everything up to it
                sentence_end = match.end()
                complete = buffer[:sentence_end]
                buffer = buffer[sentence_end:]
                
                tokens = tokenize(complete, normalize=True)
                if tokens:
                    yield tokens
            else:
                break
    
    # Yield remaining buffer
    if buffer.strip():
        tokens = tokenize(buffer.strip(), normalize=True)
        if tokens:
            yield tokens
