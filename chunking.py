import re
import tiktoken

# Initialize the tokenizer
tokenizer = tiktoken.get_encoding("cl100k_base")

# Regex pattern for main headings
MAIN_HEADING_PATTERN = re.compile(r"^# (?!\*)(.+)", re.MULTILINE)

def count_tokens(text):
    return len(tokenizer.encode(text))

def split_text_by_tokens(text, max_tokens):
    tokens = tokenizer.encode(text)
    splits = []
    for i in range(0, len(tokens), max_tokens):
        chunk_tokens = tokens[i:i+max_tokens]
        chunk_text = tokenizer.decode(chunk_tokens)
        splits.append(chunk_text)
    return splits

def parse_markdown(md_text):
    structured_data = []
    parts = re.split(MAIN_HEADING_PATTERN, md_text)
    if not parts or len(parts) < 2:
        return [{"main_heading": "", "content": md_text.strip()}]

    parts = parts[1:]
    for i in range(0, len(parts), 2):
        main_heading = parts[i].strip()
        content = parts[i + 1].strip() if (i + 1) < len(parts) else ""
        structured_data.append({
            "main_heading": main_heading,
            "content": content
        })
    return structured_data

def chunk_content(parsed_data, max_tokens=500):
    chunks = []
    sentence_split_pattern = r'(?<!://)(?<=[.!?])\s+'
    
    for section in parsed_data:
        main_heading = section["main_heading"]
        prefix = f"# {main_heading}\n\n" if main_heading else ""
        prefix_tokens = count_tokens(prefix)
        content = section["content"]

        blocks = re.split(r'\n+', content)
        current_chunk_units = []
        current_chunk_token_count = prefix_tokens

        for block in blocks:
            block = block.strip()
            if not block:
                continue
            block_token_count = count_tokens(block)
            if block_token_count > (max_tokens - prefix_tokens):
                subunits = re.split(sentence_split_pattern, block)
                for subunit in subunits:
                    subunit = subunit.strip()
                    if not subunit:
                        continue
                    subunit_token_count = count_tokens(subunit)
                    if subunit_token_count > (max_tokens - prefix_tokens):
                        token_splits = split_text_by_tokens(subunit, max_tokens - prefix_tokens)
                        for token_split in token_splits:
                            token_split = token_split.strip()
                            unit_tokens = count_tokens(token_split)
                            if current_chunk_token_count + unit_tokens > max_tokens:
                                chunk_text = prefix + " ".join(current_chunk_units).strip()
                                chunks.append({
                                    "text": chunk_text,
                                    "metadata": {"main_heading": main_heading}
                                })
                                current_chunk_units = []
                                current_chunk_token_count = prefix_tokens
                            current_chunk_units.append(token_split)
                            current_chunk_token_count += unit_tokens
                    else:
                        if current_chunk_token_count + subunit_token_count > max_tokens:
                            chunk_text = prefix + " ".join(current_chunk_units).strip()
                            chunks.append({
                                "text": chunk_text,
                                "metadata": {"main_heading": main_heading}
                            })
                            current_chunk_units = []
                            current_chunk_token_count = prefix_tokens
                        current_chunk_units.append(subunit)
                        current_chunk_token_count += subunit_token_count
            else:
                if current_chunk_token_count + block_token_count > max_tokens:
                    chunk_text = prefix + " ".join(current_chunk_units).strip()
                    chunks.append({
                        "text": chunk_text,
                        "metadata": {"main_heading": main_heading}
                    })
                    current_chunk_units = []
                    current_chunk_token_count = prefix_tokens
                current_chunk_units.append(block)
                current_chunk_token_count += block_token_count

        if current_chunk_units:
            chunk_text = prefix + " ".join(current_chunk_units).strip()
            chunks.append({
                "text": chunk_text,
                "metadata": {"main_heading": main_heading}
            })

    return chunks
